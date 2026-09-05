"""Cancel flow (Increment 6, Nhiem vu 3): graceful cancel — dung SAU chunk
hien tai, khong force-kill, va van resumable (BR-CHUNK-05) sau do.

Dung file-based SQLite (khong phai `:memory:`) qua `tmp_path`, giong
`tests/integration/test_batch_orchestrator.py` — can NHIEU session doc-thay
duoc write cua nhau de mo phong dung tinh huong that: 1 request
`POST /api/jobs/{id}/cancel` (session rieng) dat co trong luc
`JobOrchestrator.run_job()` (session khac) dang chay job do.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.chunk import Chunk
from src.models.job import Job
from src.services.pdf2zh_runner import Pdf2zhResult, Pdf2zhRunner
from tests.integration.test_job_orchestrator import (
    TOTAL_PAGES,
    _fake_pdf2zh_runner,
    _FakePricingProvider,
    _make_pdf,
)


@pytest.fixture
async def file_db(tmp_path: Path):
    db_path = tmp_path / "cancel_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s, session_factory

    await engine.dispose()


async def _create_job(session: AsyncSession, source_pdf: Path, model: str = "deepseek") -> Job:
    job = Job(
        filename="book.pdf",
        file_path=str(source_pdf),
        file_size=source_pdf.stat().st_size,
        file_hash="deadbeef",
        file_type="pdf_digital",
        model=model,
        # Pin chunk_size_used=40 (Architecture.md 6.12.7): these tests are
        # about cancellation, not cold-start sizing -- without this, a fresh
        # (provider, model) with no ConcurrencyState defaults to cold (20),
        # which would split TOTAL_PAGES=90 into 5 chunks, not the 3 these
        # tests assume.
        chunk_size_used=40,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def _fake_pdf2zh_runner_cancel_after_first_chunk(
    session_factory: async_sessionmaker[AsyncSession], job_id: str
) -> Pdf2zhRunner:
    """Renders each chunk normally (real PDF on disk, same as
    `_fake_pdf2zh_runner`), but after the FIRST chunk's render call
    completes, uses a brand-new session — standing in for the separate HTTP
    request `POST /api/jobs/{id}/cancel` would use — to set
    `Job.cancel_requested = True` mid-run.
    """
    runner = AsyncMock(spec=Pdf2zhRunner)
    call_counter = {"n": 0}

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, **kwargs
    ):
        call_index = call_counter["n"]
        call_counter["n"] += 1

        start, end = (int(x) for x in page_range.split("-"))
        mono_path = output_dir / f"{input_path.stem}-mono.pdf"
        _make_pdf(mono_path, n_pages=end - start + 1)

        if call_index == 0:
            async with session_factory() as other_session:
                other_job = await other_session.get(Job, job_id)
                other_job.cancel_requested = True
                other_session.add(other_job)
                await other_session.commit()

        return Pdf2zhResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages
    return runner


@pytest.mark.asyncio
async def test_run_job_stops_gracefully_after_cancel_requested_mid_run(
    file_db, tmp_path: Path
) -> None:
    session, session_factory = file_db
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)  # 90 pages -> 3 chunks (chunk_size=40)
    job = await _create_job(session, source_pdf)

    pdf2zh_runner = _fake_pdf2zh_runner_cancel_after_first_chunk(session_factory, job.id)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    # Cancel must not be reported as a failure — no error_message, distinct status.
    assert result.status == "cancelled"
    assert result.error_message is None
    # Only the first chunk's translate_pages() call happened — the loop
    # stopped BEFORE starting chunk 2, not mid-chunk (graceful, not force-kill).
    assert pdf2zh_runner.translate_pages.await_count == 1

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert [c.status for c in chunks] == ["completed", "pending", "pending"]

    await session.refresh(job)
    assert job.status == "cancelled"
    assert job.cancel_requested is True


@pytest.mark.asyncio
async def test_cancelled_job_is_resumable_like_a_failed_job(file_db, tmp_path: Path) -> None:
    """BR-CHUNK-05 companion: a cancelled job must resume from the first
    non-completed chunk, exactly like a failed job — this is the whole point
    of choosing "graceful cancel after the current chunk" over force-kill.
    """
    session, session_factory = file_db
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)

    pdf2zh_runner = _fake_pdf2zh_runner_cancel_after_first_chunk(session_factory, job.id)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    first_result = await orchestrator.run_job(job.id, session)
    assert first_result.status == "cancelled"

    # Mirrors what POST /api/jobs/{id}/retry does (src/api/routes/jobs.py):
    # clear the cancel flag before resuming, or run_job() would immediately
    # cancel again after the very next chunk.
    await session.refresh(job)
    job.cancel_requested = False
    session.add(job)
    await session.commit()

    resumed_runner = _fake_pdf2zh_runner()
    orchestrator._pdf2zh_runner = resumed_runner

    second_result = await orchestrator.run_job(job.id, session)

    assert second_result.status == "completed"
    # Chunk 0 already completed before cancel — only chunks 1+2 re-render.
    assert resumed_runner.translate_pages.await_count == 2

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert all(c.status == "completed" for c in chunks)


@pytest.mark.asyncio
async def test_run_job_completes_normally_when_cancel_never_requested(
    file_db, tmp_path: Path
) -> None:
    """No-regression companion: a job with `cancel_requested` never set must
    complete exactly as before this feature existed."""
    session, _session_factory = file_db
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    assert job.cancel_requested is False

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
