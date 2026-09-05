"""WebSocket progress streaming (Architecture.md section 5.2, US-07).

`ConnectionManager` keeps a set of live `WebSocket` connections per `job_id`.
`JobOrchestrator` never imports this module directly — it only receives a
plain async callable (`ProgressTracker.BroadcastFn`) so the core pipeline
stays decoupled from the web layer; `src/api/routes/jobs.py` is what wires
`connection_manager.broadcast_progress` into a `JobOrchestrator` instance
when it schedules a background job.

Single-user, in-process app (Architecture.md section 1: "asyncio + in-process
queue... du an 1 user") — a plain `dict[str, set[WebSocket]]` is enough, no
pub/sub broker needed.
"""

import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Tracks WebSocket connections grouped by `job_id` and broadcasts to them."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[job_id].add(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(job_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(job_id, None)

    def connection_count(self, job_id: str) -> int:
        return len(self._connections.get(job_id, ()))

    async def broadcast_progress(self, job_id: str, data: dict[str, Any]) -> None:
        """Send `data` to every socket subscribed to `job_id`. Never raises —
        a dead socket is dropped rather than failing the caller (the caller is
        usually mid-way through persisting job progress and must not be
        blocked by a client that vanished without closing cleanly).
        """
        connections = list(self._connections.get(job_id, ()))
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception:  # dead/broken socket, drop it
                logger.debug("Dropping dead WebSocket for job %s", job_id, exc_info=True)
                self.disconnect(job_id, websocket)


#: Module-level singleton — the whole app shares one connection registry
#: (single-user tool, one FastAPI process, Architecture.md section 9.1).
connection_manager = ConnectionManager()


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str) -> None:
    await connection_manager.connect(job_id, websocket)
    try:
        while True:
            # Client sends nothing meaningful; this just blocks until the
            # client disconnects (or sends a ping-like keepalive we ignore).
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(job_id, websocket)
