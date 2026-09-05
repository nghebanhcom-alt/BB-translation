"""Unit tests for `ConnectionManager` (Architecture.md 5.2, US-07).

Exercises the manager directly against fake `WebSocket`-shaped objects
rather than going through a real ASGI WebSocket handshake — `connect()`/
`disconnect()`/`broadcast_progress()` are pure bookkeeping + fan-out logic
that doesn't need a live socket to verify.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket

from src.api.websocket import ConnectionManager


def _fake_websocket() -> AsyncMock:
    return AsyncMock(spec=WebSocket)


@pytest.mark.asyncio
async def test_connect_registers_socket_and_calls_accept() -> None:
    manager = ConnectionManager()
    ws = _fake_websocket()

    await manager.connect("job-1", ws)

    ws.accept.assert_awaited_once()
    assert manager.connection_count("job-1") == 1


@pytest.mark.asyncio
async def test_disconnect_removes_socket() -> None:
    manager = ConnectionManager()
    ws = _fake_websocket()
    await manager.connect("job-1", ws)

    manager.disconnect("job-1", ws)

    assert manager.connection_count("job-1") == 0


def test_disconnect_unknown_job_is_a_noop() -> None:
    manager = ConnectionManager()
    # Should not raise even though "job-1" was never connected.
    manager.disconnect("job-1", _fake_websocket())


@pytest.mark.asyncio
async def test_broadcast_reaches_only_sockets_for_that_job() -> None:
    manager = ConnectionManager()
    ws_job1_a = _fake_websocket()
    ws_job1_b = _fake_websocket()
    ws_job2 = _fake_websocket()

    await manager.connect("job-1", ws_job1_a)
    await manager.connect("job-1", ws_job1_b)
    await manager.connect("job-2", ws_job2)

    payload = {"type": "progress", "job_id": "job-1", "chunk": 1, "total_chunks": 3}
    await manager.broadcast_progress("job-1", payload)

    ws_job1_a.send_json.assert_awaited_once_with(payload)
    ws_job1_b.send_json.assert_awaited_once_with(payload)
    ws_job2.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_to_job_with_no_connections_does_not_raise() -> None:
    manager = ConnectionManager()
    await manager.broadcast_progress("does-not-exist", {"type": "progress"})


@pytest.mark.asyncio
async def test_broadcast_drops_dead_socket_without_raising() -> None:
    manager = ConnectionManager()
    dead = _fake_websocket()
    dead.send_json.side_effect = RuntimeError("connection closed")
    alive = _fake_websocket()

    await manager.connect("job-1", dead)
    await manager.connect("job-1", alive)

    await manager.broadcast_progress("job-1", {"type": "progress"})

    alive.send_json.assert_awaited_once()
    assert manager.connection_count("job-1") == 1
