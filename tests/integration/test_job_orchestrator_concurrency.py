"""AIMD concurrency wiring (Architecture.md 6.12.4/6.12.6/6.12.9) — Protocol 6
R6-02: every test here asserts a concrete VALUE crossing the seam between
`ConcurrencyState` and `Pdf2zhRunner.translate_pages()`, never just
`assert_called()`/`assert_awaited()`. `classify_chunk_outcome()` and
`next_thread_count()` themselves are unit-tested in
`tests/test_concurrency_controller.py` — this file only covers the wiring in
`JobOrchestrator._process_chunk()`.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.concurrency_controller import ADAPTIVE_THREAD_FLOOR
from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.chunk import Chunk
from src.models.concurrency_state import ConcurrencyState
from src.services.pdf2zh_runner import Pdf2zhResult, Pdf2zhRunner
from tests.integration.test_job_orchestrator import _create_job, _FakePricingProvider, _make_pdf


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Same shape as `tests.integration.test_job_orchestrator.session` —
    duplicated rather than imported so the fixture name doesn't collide with
    an import (ruff F811); every other integration test file in this repo
    (e.g. `test_job_cancel.py`'s `file_db`) also defines its own session
    fixture rather than importing one.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "pdf2zh" / "richhandler_wrapped"

# Noi dung nay la output that cua RichHandler khi log dong RateLimitError
# (verified 6.12.2 S9-S11), KHONG phai tu 1 lan 429 that cua DeepSeek — golden
# file that cho truong hop do van dang INCONCLUSIVE (xem
# tests/fixtures/pdf2zh/deepseek_ratelimit/). See README.md next to the
# fixture for the full provenance note.
GOLDEN_RATE_LIMITED_STDOUT = _FIXTURE_DIR.joinpath("stdout.txt").read_text(encoding="utf-8")

_SMALL_PAGES = 5


def _fake_runner_returning(result_factory) -> Pdf2zhRunner:
    """Single-chunk fake runner that records the kwargs of its one call and
    returns whatever `result_factory(output_dir, input_path)` builds. Mirrors
    `tests.integration.test_job_orchestrator._fake_pdf2zh_runner` but lets
    each concurrency test control the exact `Pdf2zhResult` returned.
    """
    runner = AsyncMock(spec=Pdf2zhRunner)

    async def _translate_pages(input_path, output_dir, page_range, service, **kwargs):
        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}-mono.pdf"
        _make_pdf(mono_path, n_pages=total_pages)
        return result_factory(mono_path)

    runner.translate_pages.side_effect = _translate_pages
    return runner


async def _single_chunk(session: AsyncSession, tmp_path: Path) -> Chunk:
    result = await session.exec(select(Chunk))
    chunks = result.all()
    assert len(chunks) == 1
    return chunks[0]


@pytest.mark.asyncio
async def test_thread_passed_to_pdf2zh_comes_from_concurrency_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Test 1 (6.12.9): the `--thread` value handed to `translate_pages()`
    must come from `ConcurrencyState.current_thread`, not a hardcoded
    constant. Pre-seed state at 12 (neither the floor 8 nor the pdf2zh
    default 4) so the assertion can't pass by coincidence.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")

    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"deepseek:{settings.deepseek_model}"
    session.add(ConcurrencyState(provider="deepseek", model=model_key, current_thread=12))
    await session.commit()

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",
            duration_seconds=0.01,
            stdout="",
            rate_limit_hits=0,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    runner.translate_pages.assert_awaited_once()
    assert runner.translate_pages.await_args.kwargs["thread"] == 12

    chunk = await _single_chunk(session, tmp_path)
    assert chunk.thread_used == 12


@pytest.mark.asyncio
async def test_rate_limit_hits_from_stdout_updates_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Test 2 (6.12.9): `rate_limit_hits` used to update `ConcurrencyState`
    must come from the SAME `Pdf2zhResult` this chunk's call returned, and
    the golden RichHandler stdout (containing "RateLimitError") must drive a
    multiplicative decrease: 20 -> max(floor=8, 20 // 2) = 10.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")

    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"deepseek:{settings.deepseek_model}"
    session.add(ConcurrencyState(provider="deepseek", model=model_key, current_thread=20))
    await session.commit()

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",
            duration_seconds=0.01,
            stdout=GOLDEN_RATE_LIMITED_STDOUT,
            rate_limit_hits=1,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    state = await session.get(ConcurrencyState, ("pdf2zh", "deepseek", model_key))
    assert state is not None
    assert state.current_thread == 10  # 20 -> x0.5, NOT still 20

    chunk = await _single_chunk(session, tmp_path)
    assert chunk.rate_limit_hits == 1


@pytest.mark.asyncio
async def test_regression_signal_must_not_come_from_stderr_alone(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Test 3 (6.12.9) — the most important regression test in this section
    per Architecture.md: `stderr` is EMPTY on this result (exactly the shape
    a pre-6.12.2 bug would see as "no signal") while `stdout` (and the
    already-computed `.rate_limit_hits`) carries the golden RateLimitError
    line. If `_process_chunk()` ever regresses to reading only `.stderr`
    instead of trusting `Pdf2zhResult.rate_limit_hits`, `current_thread`
    would incorrectly stay at 20 (or increase) instead of dropping below it.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")

    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"deepseek:{settings.deepseek_model}"
    session.add(ConcurrencyState(provider="deepseek", model=model_key, current_thread=20))
    await session.commit()

    assert "RateLimitError" in GOLDEN_RATE_LIMITED_STDOUT

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",  # deliberately empty -- signal lives ONLY in stdout
            duration_seconds=0.01,
            stdout=GOLDEN_RATE_LIMITED_STDOUT,
            rate_limit_hits=1,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    state = await session.get(ConcurrencyState, ("pdf2zh", "deepseek", model_key))
    assert state is not None
    assert state.current_thread < 20  # FAILS if the orchestrator only reads stderr


@pytest.mark.asyncio
async def test_claude_locked_at_floor_does_not_increase_on_success(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.12.6: Claude AIMD is disabled ([UNVERIFIED] S6) —
    `current_thread` must stay at the floor (4) even after a `success`
    outcome that would normally trigger +2 additive increase.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="claude")

    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"openailiked:{settings.claude_model}"

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",
            duration_seconds=0.01,
            stdout="",
            rate_limit_hits=0,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    assert runner.translate_pages.await_args.kwargs["thread"] == ADAPTIVE_THREAD_FLOOR["claude"]

    state = await session.get(ConcurrencyState, ("pdf2zh", "claude", model_key))
    assert state is not None
    assert state.current_thread == ADAPTIVE_THREAD_FLOOR["claude"]  # locked, whatever the floor is
    assert state.last_outcome == "success"  # observed, just never acted on


@pytest.mark.asyncio
async def test_gemini_aimd_increases_on_success(session: AsyncSession, tmp_path: Path) -> None:
    """Architecture.md 6.12.6: unlike `claude`, `gemini` keeps running normal
    AIMD while `[UNVERIFIED]` (floor 4, ceiling 32 still bound it) — a
    `success` outcome must apply the full +2 additive increase, NOT stay
    locked at the floor.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="gemini")

    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"gemini:{settings.gemini_model}"
    floor = ADAPTIVE_THREAD_FLOOR["gemini"]
    assert floor == 4

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",
            duration_seconds=0.01,
            stdout="",
            rate_limit_hits=0,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    assert runner.translate_pages.await_args.kwargs["thread"] == floor

    state = await session.get(ConcurrencyState, ("pdf2zh", "gemini", model_key))
    assert state is not None
    assert state.current_thread == floor + 2 == 6  # AIMD acted on it, unlike claude
    assert state.last_outcome == "success"


@pytest.mark.asyncio
async def test_ollama_uses_fixed_thread_and_never_touches_concurrency_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.12.6: Ollama never runs AIMD — `--thread` must come
    straight from `settings.ollama_thread`, and NO `ConcurrencyState` row may
    be created for it (there is no countable signal to learn from).
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="ollama")

    settings = Settings(pdf_translate_engine="pdf2zh", ollama_thread=3)

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",
            duration_seconds=0.01,
            stdout="",
            rate_limit_hits=0,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    assert runner.translate_pages.await_args.kwargs["thread"] == 3

    all_states = (await session.exec(select(ConcurrencyState))).all()
    assert all_states == []


@pytest.mark.asyncio
async def test_adaptive_disabled_uses_fixed_floor_and_never_touches_concurrency_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.12.8 safe-rollback path: with the kill switch off,
    every chunk gets `ADAPTIVE_THREAD_FLOOR[provider]` fixed, and no
    `ConcurrencyState` row is read or written at all.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")

    settings = Settings(pdf_translate_engine="pdf2zh", adaptive_concurrency_enabled=False)

    runner = _fake_runner_returning(
        lambda mono_path: Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=None,
            stderr="",
            duration_seconds=0.01,
            stdout="",
            rate_limit_hits=0,
        )
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    assert runner.translate_pages.await_args.kwargs["thread"] == ADAPTIVE_THREAD_FLOOR["deepseek"]

    all_states = (await session.exec(select(ConcurrencyState))).all()
    assert all_states == []
