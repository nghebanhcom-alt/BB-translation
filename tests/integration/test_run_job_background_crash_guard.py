"""US-19 (Architecture.md 6.17.2): `_run_job_background()`'s last-resort
`except Exception` guard (src/api/routes/jobs.py) — Architecture.md flags
this as "diem de quen nhat" because it lives OUTSIDE `job_orchestrator.py`
entirely: it only fires when `JobOrchestrator.run_job()` raises an exception
that its OWN internal try/except blocks didn't already turn into a graceful
"failed" `JobResult` (e.g. a genuine bug, not a modeled failure mode). This
test forces exactly that shape and asserts `job.finished_at` gets set here
too, not just inside `job_orchestrator.py`.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings
from src.models.job import Job


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    # Same isolation pattern as tests/integration/test_upload_and_job_flow.py.
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


@pytest.mark.asyncio
async def test_background_crash_guard_sets_finished_at(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    import src.api.routes.jobs as jobs_module

    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="book.pdf",
            file_path=str(tmp_path / "book.pdf"),
            file_size=10,
            file_hash="deadbeef",
            file_type="pdf_digital",
            model="deepseek",
            status="queued",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    class _CrashingOrchestrator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def run_job(self, job_id: str, session) -> None:
            raise RuntimeError("unexpected bug, not a modeled JobOrchestrator failure mode")

    monkeypatch.setattr(jobs_module, "JobOrchestrator", _CrashingOrchestrator)

    await jobs_module._run_job_background(job_id)

    async with session_factory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.finished_at is not None
        assert job.finished_at >= job.created_at
