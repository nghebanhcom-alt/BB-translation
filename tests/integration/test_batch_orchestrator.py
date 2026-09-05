from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import BatchOrchestrator, JobOrchestrator, JobResult
from src.models.batch import Batch
from src.models.job import Job


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s, session_factory

    await engine.dispose()


async def _create_batch_with_jobs(session: AsyncSession, page_counts: list[int]) -> Batch:
    batch = Batch(total_files=len(page_counts))
    session.add(batch)
    await session.commit()
    await session.refresh(batch)

    for i, pages in enumerate(page_counts):
        job = Job(
            batch_id=batch.id,
            filename=f"book_{i}.pdf",
            file_path=f"/data/uploads/book_{i}.pdf",
            file_size=1024,
            file_hash=f"hash-{i}",
            file_type="pdf_digital",
            model="claude",
            total_pages=pages,
        )
        session.add(job)
    await session.commit()
    return batch


@pytest.mark.asyncio
async def test_run_batch_isolates_a_single_job_failure(db) -> None:
    session, session_factory = db
    batch = await _create_batch_with_jobs(session, page_counts=[10, 20, 5, 15, 8])

    job_orchestrator = AsyncMock(spec=JobOrchestrator)

    async def _run_job(job_id: str, job_session: AsyncSession) -> JobResult:
        job = await job_session.get(Job, job_id)
        if job.filename == "book_2.pdf":  # the shortest job (5 pages) fails
            raise RuntimeError("boom: simulated permanent failure")
        return JobResult(
            job_id=job_id, status="completed", output_path=f"/data/outputs/{job_id}/vi.pdf",
            bilingual_path=None, actual_cost=0.1,
        )

    job_orchestrator.run_job.side_effect = _run_job

    batch_orchestrator = BatchOrchestrator(
        job_orchestrator=job_orchestrator,
        max_concurrent_files=3,
        session_factory=session_factory,
    )

    batch_id = batch.id
    result = await batch_orchestrator.run_batch(batch_id, session)

    assert result.total == 5
    assert result.completed == 4
    assert result.failed == 1

    failed_results = [r for r in result.job_results if r.status == "failed"]
    assert len(failed_results) == 1
    assert "boom" in failed_results[0].error_message

    session.expire_all()  # other sessions committed writes; drop this session's stale identity map
    jobs_result = await session.exec(select(Job).where(Job.batch_id == batch_id))
    jobs = list(jobs_result.all())
    failed_job = next(j for j in jobs if j.filename == "book_2.pdf")
    assert failed_job.status == "failed"
    assert "boom" in failed_job.error_message

    batch = await session.get(Batch, batch_id)
    assert batch.status == "completed"
    assert batch.completed_files == 4
    assert batch.failed_files == 1


@pytest.mark.asyncio
async def test_run_batch_schedules_shortest_job_first(db) -> None:
    session, session_factory = db
    batch = await _create_batch_with_jobs(session, page_counts=[50, 5, 20])

    call_order: list[int] = []
    job_orchestrator = AsyncMock(spec=JobOrchestrator)

    async def _run_job(job_id: str, job_session: AsyncSession) -> JobResult:
        job = await job_session.get(Job, job_id)
        call_order.append(job.total_pages)
        return JobResult(job_id=job_id, status="completed", output_path=None,
                          bilingual_path=None, actual_cost=0.0)

    job_orchestrator.run_job.side_effect = _run_job

    # max_concurrent_files=1 to make scheduling order deterministic/observable.
    batch_orchestrator = BatchOrchestrator(
        job_orchestrator=job_orchestrator, max_concurrent_files=1, session_factory=session_factory
    )

    await batch_orchestrator.run_batch(batch.id, session)

    assert call_order == [5, 20, 50]


@pytest.mark.asyncio
async def test_run_batch_stops_later_files_once_batch_cost_cap_is_exceeded(db) -> None:
    """Architecture.md 6.11.4 Lop 3 + 6.11.7 #1: `max_concurrent_files` only
    ever bounded HOW MANY files ran at once, never how much the whole batch
    could spend — this is the regression test for that specific hole.
    `max_concurrent_files=1` makes file ordering deterministic so the third
    (shortest-job-first-sorted) file can be asserted as never having run.
    """
    session, session_factory = db
    batch = await _create_batch_with_jobs(session, page_counts=[5, 8, 10])
    batch_id = batch.id

    job_orchestrator = AsyncMock(spec=JobOrchestrator)

    async def _run_job(job_id: str, job_session: AsyncSession) -> JobResult:
        # Each "file" costs more than the whole-batch cap on its own —
        # the 2nd file's completion alone must be enough to stop the 3rd.
        return JobResult(
            job_id=job_id, status="completed", output_path=f"/data/outputs/{job_id}/vi.pdf",
            bilingual_path=None, actual_cost=3.0,
        )

    job_orchestrator.run_job.side_effect = _run_job

    settings = Settings(max_cost_per_batch_usd=5.0, cost_cap_enabled=True)
    batch_orchestrator = BatchOrchestrator(
        job_orchestrator=job_orchestrator,
        max_concurrent_files=1,
        session_factory=session_factory,
        settings=settings,
    )

    result = await batch_orchestrator.run_batch(batch_id, session)

    cost_capped_results = [r for r in result.job_results if r.status == "cost_capped"]
    assert len(cost_capped_results) == 1
    # Only 2 of the 3 files actually ran pdf2zh/LLM work through the orchestrator.
    assert job_orchestrator.run_job.await_count == 2

    # Note: the mocked `job_orchestrator.run_job()` above returns a
    # "completed" `JobResult` WITHOUT writing that status to the DB (only
    # the real `JobOrchestrator.run_job()` does that) — so the DB check here
    # only covers the `cost_capped` write, which IS real `BatchOrchestrator`
    # code under test, not part of the mock.
    session.expire_all()
    jobs_result = await session.exec(select(Job).where(Job.batch_id == batch_id))
    jobs = list(jobs_result.all())
    assert sum(1 for j in jobs if j.status == "cost_capped") == 1
