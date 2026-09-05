"""Lop 3 running cost accumulator (Architecture.md 6.11.4) — the hard stop
DURING a job, for when Lop 2's pre-flight estimate was wrong-low (exactly
what RC-2 was, 4.1x under real cost) and the job would otherwise run past
its cap the way the real $6.50 incident did (RC-3: no cap at any layer).

Reuses `tests/integration/test_job_orchestrator.py`'s fixtures
(`_fake_pdf2zh_runner`, `_make_pdf`, `session`) rather than redefining them,
matching how `tests/integration/test_job_cancel.py` already does this for
the sibling "graceful stop mid-run" feature.
"""

from pathlib import Path

import pytest
from sqlmodel import select

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.chunk import Chunk
from tests.integration.test_job_orchestrator import (
    TOTAL_PAGES,
    _create_job,
    _fake_pdf2zh_runner,
    _FakePricingProvider,
    _make_pdf,
    session,
)

__all__ = ["session"]


class _ExpensivePricingProvider(_FakePricingProvider):
    """Prices high enough that a SINGLE chunk's cost alone crosses a small
    cap — the scenario Architecture.md 6.11.4 Lop 3 documents as its known
    limitation ("granularity nho nhat cua lop nay la 1 chunk").
    """

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round((input_tokens + output_tokens) * 0.01, 6)


@pytest.mark.asyncio
async def test_run_job_stops_with_cost_capped_when_accumulated_cost_exceeds_cap(
    session, tmp_path: Path
) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)  # 90 pages -> 3 chunks (chunk_size=40)
    job = await _create_job(session, source_pdf)

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
    assert result.error_message is not None
    assert "vuot tran" in result.error_message

    await session.refresh(job)
    assert job.status == "cost_capped"
    assert job.actual_cost is not None and job.actual_cost > settings.max_cost_per_job_usd

    # Only the chunk(s) that ran before the cap tripped are "completed" —
    # the rest stay "pending", exactly like the cancel/failed cases, so a
    # later retry can resume from where it stopped (BR-CHUNK-05).
    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert chunks[0].status == "completed"
    assert any(c.status == "pending" for c in chunks)


@pytest.mark.asyncio
async def test_run_job_resumes_after_cost_capped_like_a_cancelled_job(
    session, tmp_path: Path
) -> None:
    """BR-CHUNK-05 companion, mirroring
    `test_job_cancel.py::test_cancelled_job_is_resumable_like_a_failed_job` —
    once the cap is raised (or disabled), a `cost_capped` job must resume
    from the first non-completed chunk, not restart from scratch.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)

    capped_settings = Settings(
        pdf_translate_engine="pdf2zh", max_cost_per_job_usd=0.01, cost_cap_enabled=True
    )
    orchestrator = JobOrchestrator(
        settings=capped_settings,
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_ExpensivePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    first_result = await orchestrator.run_job(job.id, session)
    assert first_result.status == "cost_capped"

    # Mirrors POST /api/jobs/{id}/retry: raise the cap (Settings UI) before resuming.
    orchestrator._settings = Settings(
        pdf_translate_engine="pdf2zh", max_cost_per_job_usd=1000.0, cost_cap_enabled=True
    )
    orchestrator._pdf2zh_runner = _fake_pdf2zh_runner()

    second_result = await orchestrator.run_job(job.id, session)

    assert second_result.status == "completed"
    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert all(c.status == "completed" for c in chunks)


@pytest.mark.asyncio
async def test_cost_cap_disabled_lets_an_expensive_job_run(session, tmp_path: Path) -> None:
    """Architecture.md 6.11.4 Lop 2 table: `cost_cap_enabled=False` must be
    an honored, explicit opt-out — never silently ignored."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)

    settings = Settings(
        pdf_translate_engine="pdf2zh", max_cost_per_job_usd=0.01, cost_cap_enabled=False
    )
    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_ExpensivePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"


@pytest.mark.asyncio
async def test_job_level_cost_cap_override_takes_priority_over_settings(
    session, tmp_path: Path
) -> None:
    """Architecture.md 6.11.4 Lop 3: `effective_cap = job.cost_cap_usd if
    set, else settings.max_cost_per_job_usd`."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    job.cost_cap_usd = 0.01  # stricter than the (generous) global setting
    session.add(job)
    await session.commit()

    settings = Settings(
        pdf_translate_engine="pdf2zh", max_cost_per_job_usd=1000.0, cost_cap_enabled=True
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
