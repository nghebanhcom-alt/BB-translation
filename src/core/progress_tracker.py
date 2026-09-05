"""Progress tracking (US-07), persisted to the DB.

Increment 5 adds an optional broadcast hook: `JobOrchestrator` passes
`ConnectionManager.broadcast_progress` (src/api/websocket.py) in here so the
web dashboard gets a realtime WebSocket push every time `update()` writes to
the DB, instead of only being able to poll `GET /api/jobs/{id}`. No message
queue — this is a single-user, in-process app (Architecture.md 5.2), so a
plain async callable is enough.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.job import Job

#: `(job_id, event_dict) -> None`, awaited after every DB write. See
#: `src.api.websocket.ConnectionManager.broadcast_progress` for the concrete
#: implementation wired up in `src/api/routes/jobs.py`.
BroadcastFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class JobNotFoundError(ValueError):
    pass


class ProgressTracker:
    """Writes chunk progress onto the `Job` row so a dashboard can poll it,
    and optionally broadcasts the same update over WebSocket.
    """

    def __init__(self, broadcaster: BroadcastFn | None = None) -> None:
        self._broadcaster = broadcaster

    async def update(
        self,
        job_id: str,
        current_chunk: int,
        total_chunks: int,
        db_session: AsyncSession,
    ) -> None:
        job = await db_session.get(Job, job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} khong ton tai")

        job.current_chunk = current_chunk
        job.total_chunks = total_chunks
        job.progress = (current_chunk / total_chunks) if total_chunks else 0.0
        job.updated_at = datetime.now(UTC)
        db_session.add(job)
        await db_session.commit()

        if self._broadcaster is not None:
            # Architecture.md 5.2 "progress" event shape.
            await self._broadcaster(
                job_id,
                {
                    "type": "progress",
                    "job_id": job_id,
                    "chunk": current_chunk,
                    "total_chunks": total_chunks,
                    "progress": job.progress,
                    "status": job.status,
                },
            )
