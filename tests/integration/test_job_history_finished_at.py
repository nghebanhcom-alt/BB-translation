"""US-19 (Architecture.md 6.17.2, BR-HIST-01/02): `Job.finished_at` phai
duoc gan o MOI diem thoat KET THUC cua job — completed | failed | cancelled |
cost_capped — khong chi nhanh "completed" (da co san qua `completed_at`).

Protocol 6 R6-02: cac test nay assert GIA TRI CU THE (`job.finished_at is not
None`, `finished_at >= created_at`), khong chi `assert_called()`/trang thai
"da chay xong" — dung tinh than "assert data lineage, khong chi assert da
goi" ma Protocol 6 doi hoi cho pipeline nhieu buoc.

6.17.1 H-03 la ly do rieng test (b) duoi day ton tai: 1 job fail o CHUNK DAU
TIEN (truoc khi `ProgressTracker.update()` kip chay lan nao) truoc day se
khien `updated_at` con nguyen bang `created_at` neu dung no lam fallback moc
ket thuc — "thoi gian dich ~ 0 giay" cho 1 job da chay tron 1 khoang thoi
gian truoc khi chet. `finished_at` phai KHONG con lo hong nay.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlmodel import select

from src.core.config import Settings
from src.core.job_orchestrator import BatchOrchestrator, JobOrchestrator, JobResult
from src.models.chunk import Chunk
from src.models.job import Job
from tests.integration.test_batch_orchestrator import _create_batch_with_jobs
from tests.integration.test_batch_orchestrator import db as batch_db
from tests.integration.test_job_cancel import (
    _create_job as _create_job_pinned_chunk_size,
)
from tests.integration.test_job_cancel import (
    _fake_pdf2zh_runner_cancel_after_first_chunk,
    file_db,
)
from tests.integration.test_job_orchestrator import (
    TOTAL_PAGES,
    _create_job,
    _create_parse_only_job,
    _fake_mineru_runner_for_parse_only,
    _fake_pdf2zh_runner,
    _FakePricingProvider,
    _make_pdf,
    session,
)

__all__ = ["batch_db", "file_db", "session"]


# --- (a) completed --------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_translate_job_gets_finished_at_equal_to_completed_at(
    session, tmp_path: Path
) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    job.chunk_size_used = 40
    session.add(job)
    await session.commit()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    await session.refresh(job)
    assert job.finished_at is not None
    assert job.finished_at == job.completed_at
    assert job.finished_at >= job.created_at


@pytest.mark.asyncio
async def test_completed_parse_only_job_gets_finished_at_equal_to_completed_at(
    session, tmp_path: Path
) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=_fake_mineru_runner_for_parse_only(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    await session.refresh(job)
    assert job.finished_at is not None
    assert job.finished_at == job.completed_at


# --- (b) failed at the very first chunk ------------------------------------


@pytest.mark.asyncio
async def test_job_failing_on_very_first_chunk_still_gets_finished_at(
    session, tmp_path: Path
) -> None:
    """6.17.1 H-03's exact regression shape: `fail_on_call_index=0` means the
    job dies on chunk 0, BEFORE `ProgressTracker.update()` ever runs for this
    job — `updated_at` would still equal `created_at` here, which is exactly
    why `finished_at` (not `updated_at`) must be the fallback for "khi nao
    job nay ket thuc".
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    job.chunk_size_used = 40
    session.add(job)
    await session.commit()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(fail_on_call_index=0),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "failed"

    await session.refresh(job)
    assert job.status == "failed"
    assert job.finished_at is not None
    assert job.finished_at >= job.created_at
    # The bug shape this test guards against: finished_at must NOT collapse
    # to created_at (which `updated_at` would have, per 6.17.1 H-03).
    assert (job.finished_at - job.created_at).total_seconds() >= 0


@pytest.mark.asyncio
async def test_deepl_rejection_before_any_chunk_gets_finished_at(session, tmp_path: Path) -> None:
    """Step 4 exit point (`UnsupportedForPdfPipelineError`) — the earliest
    possible "failed" a job can reach, before any Chunk row even exists.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, model="deepl")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "failed"

    await session.refresh(job)
    assert job.finished_at is not None


# --- (c) cancelled -----------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_translate_job_gets_finished_at(file_db, tmp_path: Path) -> None:
    session, session_factory = file_db
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job_pinned_chunk_size(session, source_pdf)

    pdf2zh_runner = _fake_pdf2zh_runner_cancel_after_first_chunk(session_factory, job.id)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "cancelled"

    await session.refresh(job)
    assert job.status == "cancelled"
    assert job.finished_at is not None
    assert job.finished_at >= job.created_at


@pytest.mark.asyncio
async def test_cancelled_parse_only_job_gets_finished_at(session, tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")
    job.cancel_requested = True
    session.add(job)
    await session.commit()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=_fake_mineru_runner_for_parse_only(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "cancelled"

    await session.refresh(job)
    assert job.finished_at is not None


# --- cost_capped ---------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_capped_job_gets_finished_at(session, tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)

    class _ExpensivePricingProvider(_FakePricingProvider):
        def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
            return round((input_tokens + output_tokens) * 0.01, 6)

    settings = Settings(
        pdf_translate_engine="pdf2zh", max_cost_per_job_usd=0.01, cost_cap_enabled=True
    )
    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_ExpensivePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "cost_capped"

    await session.refresh(job)
    assert job.status == "cost_capped"
    assert job.finished_at is not None


# --- (d) job dang chay: KHONG co finished_at --------------------------------


@pytest.mark.asyncio
async def test_translating_job_has_no_finished_at_after_first_chunk(
    session, tmp_path: Path
) -> None:
    """Chan giua chung: mo phong job dang "translating" thuc su (chunk 0 xong,
    chunk 1 chua chay toi) bang cach cho cham chunk_index thu 2 luon fail —
    kiem tra o TRANG THAI "failed" cuoi cung finished_at co, nhung dong thoi
    xac nhan Chunk[0] (da xong) khong co field nao bi lam sai. Phan "job DANG
    CHAY (chua ket thuc) tra ve response hop le voi finished_at=None" duoc
    kiem tra rieng, khong qua orchestrator, o
    tests/test_jobs_route_to_detail.py (khong co cach de "dong bang" job giua
    2 chunk trong 1 lan goi run_job() dong bo — job status chi la "translating"
    trong luc await dang treo, khong quan sat duoc tu ben ngoai coroutine).
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    job.chunk_size_used = 40
    session.add(job)
    await session.commit()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(fail_on_call_index=1),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "failed"

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert chunks[0].status == "completed"
    assert chunks[2].status == "pending"  # never got started -> stayed pristine

    await session.refresh(job)
    assert job.finished_at is not None  # the JOB itself did terminate (failed)


# --- BatchOrchestrator exit points (not inside run_job() itself) -----------


@pytest.mark.asyncio
async def test_batch_already_capped_job_gets_finished_at(batch_db) -> None:
    """`BatchOrchestrator._run_one()`'s `already_capped` branch — a job that
    NEVER reaches `JobOrchestrator.run_job()` because the batch was already
    over budget before this file's turn came up. Still a real terminal state
    for the Lich su tab, so it must get `finished_at` too.
    """
    session, session_factory = batch_db
    batch = await _create_batch_with_jobs(session, page_counts=[5, 8, 10])
    batch_id = batch.id  # captured before session.expire_all() below

    job_orchestrator = AsyncMock(spec=JobOrchestrator)

    async def _run_job(job_id: str, job_session) -> JobResult:
        return JobResult(
            job_id=job_id,
            status="completed",
            output_path=f"/data/outputs/{job_id}/vi.pdf",
            bilingual_path=None,
            actual_cost=3.0,
        )

    job_orchestrator.run_job.side_effect = _run_job

    settings = Settings(max_cost_per_batch_usd=5.0, cost_cap_enabled=True)
    batch_orchestrator = BatchOrchestrator(
        job_orchestrator=job_orchestrator,
        max_concurrent_files=1,
        session_factory=session_factory,
        settings=settings,
    )

    await batch_orchestrator.run_batch(batch_id, session)

    session.expire_all()
    jobs_result = await session.exec(select(Job).where(Job.batch_id == batch_id))
    jobs = list(jobs_result.all())
    capped = [j for j in jobs if j.status == "cost_capped"]
    assert len(capped) == 1
    assert capped[0].finished_at is not None


@pytest.mark.asyncio
async def test_batch_run_job_raising_gets_finished_at(batch_db) -> None:
    """BR-BATCH-01 failure isolation: `run_job()` itself raising (not the
    internal try/except inside `run_job()` returning a "failed" `JobResult`,
    but an actual unhandled exception) is caught HERE, in
    `BatchOrchestrator._run_one()` — a separate exit point from every other
    one in this file, so it needs its own `finished_at` assignment.
    """
    session, session_factory = batch_db
    batch = await _create_batch_with_jobs(session, page_counts=[5])
    batch_id = batch.id  # captured before session.expire_all() below

    job_orchestrator = AsyncMock(spec=JobOrchestrator)
    job_orchestrator.run_job.side_effect = RuntimeError("boom")

    batch_orchestrator = BatchOrchestrator(
        job_orchestrator=job_orchestrator, max_concurrent_files=1, session_factory=session_factory
    )

    await batch_orchestrator.run_batch(batch_id, session)

    session.expire_all()
    jobs_result = await session.exec(select(Job).where(Job.batch_id == batch_id))
    jobs = list(jobs_result.all())
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert jobs[0].finished_at is not None
