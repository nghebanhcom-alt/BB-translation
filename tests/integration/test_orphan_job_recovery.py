"""Bug #EPUB-3 (Architecture.md §E3): a job's background `asyncio.Task`
(`src/api/routes/jobs.py:650`/`:766`) lives in the SAME uvicorn process that
runs it — the process dying (crash, deploy, `--reload`) leaves the `Job` row
stuck in a non-terminal status forever, with no background task left to ever
finish it. `src.core.job_recovery.fail_orphaned_jobs()` sweeps those rows to
`failed` on the NEXT server startup so the UI stops showing them as running
and the user can Retry.

Protocol 6 R6-02: tests 5/6 below assert the LINK between "mark orphan" and
"retry resumes correctly" (status values, chunk survival, no re-translate),
not just that each step was "called" in isolation — the exact class of bug
Protocol 6 exists to catch.
"""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings
from src.core.job_recovery import _ORPHAN_JOB_STATUSES, fail_orphaned_jobs
from src.models.chunk import Chunk
from src.models.job import Job
from tests.integration.test_job_orchestrator import session

__all__ = ["session"]

_TERMINAL_STATUSES = ("completed", "failed", "cancelled", "cost_capped")


def _make_job(status: str, **overrides) -> Job:
    defaults = {
        "filename": "book.pdf",
        "file_path": "/nonexistent/book.pdf",
        "file_size": 1234,
        "file_hash": f"hash-{status}",
        "file_type": "pdf_digital",
        "job_type": "translate",
        "model": "ollama",
        "status": status,
    }
    defaults.update(overrides)
    return Job(**defaults)


# === 1. Mark dung tap orphan =================================================


@pytest.mark.asyncio
async def test_marks_every_orphan_status_as_failed(session) -> None:
    jobs = [
        _make_job(status, file_hash=f"hash-{status}") for status in sorted(_ORPHAN_JOB_STATUSES)
    ]
    for job in jobs:
        session.add(job)
    await session.commit()

    count = await fail_orphaned_jobs(session)

    assert count == len(_ORPHAN_JOB_STATUSES) == 7

    for job in jobs:
        await session.refresh(job)
        assert job.status == "failed"
        assert job.error_message is not None
        assert "khoi dong lai" in job.error_message
        assert job.finished_at is not None


# === 2. Khong dung toi trang thai cuoi =======================================


@pytest.mark.asyncio
async def test_does_not_touch_terminal_status_jobs(session) -> None:
    now = datetime.now(UTC)
    jobs = []
    for status in _TERMINAL_STATUSES:
        job = _make_job(
            status,
            file_hash=f"hash-terminal-{status}",
            error_message=f"pre-existing message for {status}",
            finished_at=now,
        )
        session.add(job)
        jobs.append(job)
    await session.commit()
    for job in jobs:
        await session.refresh(job)

    original_error_messages = {job.id: job.error_message for job in jobs}
    original_finished_at = {job.id: job.finished_at for job in jobs}

    count = await fail_orphaned_jobs(session)

    assert count == 0
    for job in jobs:
        await session.refresh(job)
        assert job.status in _TERMINAL_STATUSES
        assert job.error_message == original_error_messages[job.id]
        assert job.finished_at == original_finished_at[job.id]


# === 3. Giu nguyen tien do ====================================================


@pytest.mark.asyncio
async def test_keeps_progress_fields_unchanged(session) -> None:
    job = _make_job(
        "translating",
        progress=0.6,
        current_chunk=3,
        total_chunks=5,
        actual_cost=1.23,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    count = await fail_orphaned_jobs(session)

    assert count == 1
    await session.refresh(job)
    assert job.status == "failed"
    assert job.progress == 0.6
    assert job.current_chunk == 3
    assert job.total_chunks == 5
    assert job.actual_cost == 1.23


# === 4. Idempotent =============================================================


@pytest.mark.asyncio
async def test_second_call_is_idempotent(session) -> None:
    job = _make_job("translating")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    first_count = await fail_orphaned_jobs(session)
    assert first_count == 1
    await session.refresh(job)
    first_finished_at = job.finished_at
    assert first_finished_at is not None

    second_count = await fail_orphaned_jobs(session)
    assert second_count == 0

    await session.refresh(job)
    assert job.finished_at == first_finished_at


# === 5. Retry duoc sau khi mark orphan (R6-02) ================================


def _make_pdf_bytes(n_pages: int = 1) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((50, 100), f"Recipe page {i + 1}: 2 cups flour", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    database_module._engine = None
    database_module._session_factory = None

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()
        database_module._engine = None
        database_module._session_factory = None


async def _insert_translating_job(tmp_path: Path, status: str = "translating") -> str:
    # model="ollama": needs no API key, estimate_cost is always 0 — keeps this
    # test independent of any provider config, mirroring
    # tests/integration/test_estimate_and_cancel_api.py::_insert_job.
    file_path = tmp_path / "book.pdf"
    file_path.write_bytes(_make_pdf_bytes())

    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="book.pdf",
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
            file_hash="orphan-retry-hash",
            file_type="pdf_digital",
            job_type="translate",
            model="ollama",
            status=status,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


def test_retry_after_orphan_mark_succeeds(client: TestClient, tmp_path: Path) -> None:
    job_id = asyncio.run(_insert_translating_job(tmp_path))

    # TestClient's lifespan already ran fail_orphaned_jobs() once on startup
    # (before this job existed), so mark it orphan explicitly now — mirrors
    # "job was running, server restarted" without needing a 2nd TestClient
    # startup cycle.
    async def _mark_orphan() -> None:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            await fail_orphaned_jobs(session)

    asyncio.run(_mark_orphan())

    detail_before = client.get(f"/api/jobs/{job_id}").json()
    assert detail_before["status"] == "failed"
    assert "khoi dong lai" in detail_before["error_message"]

    retry_response = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_response.status_code == 200, retry_response.text
    assert retry_response.json()["status"] == "queued"

    detail_after = client.get(f"/api/jobs/{job_id}").json()
    assert detail_after["status"] == "queued"
    assert detail_after["error_message"] is None
    assert detail_after["cancel_requested"] is False


# === 6. Chunk completed song sot qua orphan (khong dich lai) ==================


@pytest.mark.asyncio
async def test_completed_chunks_survive_orphan_mark(session) -> None:
    job = _make_job("translating")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    chunks = [
        Chunk(job_id=job.id, chunk_index=0, status="completed", output_path="/tmp/c0.pdf"),
        Chunk(job_id=job.id, chunk_index=1, status="translating"),
        Chunk(job_id=job.id, chunk_index=2, status="pending"),
    ]
    for chunk in chunks:
        session.add(chunk)
    await session.commit()
    for chunk in chunks:
        await session.refresh(chunk)

    original_statuses = {chunk.id: chunk.status for chunk in chunks}

    count = await fail_orphaned_jobs(session)
    assert count == 1

    result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    refreshed = {chunk.id: chunk.status for chunk in result.all()}
    assert refreshed == original_statuses


# === 7. lifespan() goi fail_orphaned_jobs() sau init_db(), truoc yield ========


async def _seed_orphan_job_before_startup() -> str:
    # init_db() is idempotent (Architecture.md §E3.7 / src/models/database.py
    # docstring) — safe to call once here to create tables before TestClient's
    # own lifespan calls it again.
    await database_module.init_db()
    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="book.pdf",
            file_path="/nonexistent/book.pdf",
            file_size=1,
            file_hash="pre-startup-orphan",
            file_type="pdf_digital",
            job_type="translate",
            model="ollama",
            status="translating",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


def test_lifespan_marks_orphan_jobs_before_serving_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    database_module._engine = None
    database_module._session_factory = None

    job_id = asyncio.run(_seed_orphan_job_before_startup())

    try:
        # Entering the TestClient context runs FastAPI's lifespan startup
        # (init_db() then fail_orphaned_jobs(), per src/api/main.py) BEFORE
        # any request can be served — the read below is just confirming that
        # already happened, not triggering it.
        with TestClient(app) as test_client:
            response = test_client.get(f"/api/jobs/{job_id}")
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "failed"
            assert "khoi dong lai" in body["error_message"]
    finally:
        get_settings.cache_clear()
        database_module._engine = None
        database_module._session_factory = None
