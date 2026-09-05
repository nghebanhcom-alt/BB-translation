"""`chunk_size` cold-start (Architecture.md 6.12.7): `Job.chunk_size_used`
must be decided ONCE per job from `(provider, model)`'s `ConcurrencyState`
(cold=20 unless warm, i.e. `observation_count >= 3 AND consecutive_successes
>= 3`, then 40) and reused verbatim on resume — never recomputed from
`self._chunk_size` or from a possibly-since-changed `ConcurrencyState`.

Per R6-02, every test asserts the concrete value `plan_chunks()` is called
with, not just `assert_called()` — the whole point of 6.12.7 is that
`self._chunk_size` must stop being that value's source for `run_job()`.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core import job_orchestrator as job_orchestrator_module
from src.core.chunking import plan_chunks as real_plan_chunks
from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.concurrency_state import ConcurrencyState
from tests.integration.test_job_orchestrator import (
    _create_job,
    _fake_pdf2zh_runner,
    _FakePricingProvider,
    _make_pdf,
)

_SMALL_PAGES = 5


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Same shape as `tests.integration.test_job_orchestrator.session` —
    duplicated rather than imported, per this repo's existing convention
    (see `test_job_orchestrator_concurrency.py`'s identical fixture) so the
    fixture name doesn't collide with an import (ruff F811).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _orchestrator(settings: Settings, tmp_path: Path, *, runner=None) -> JobOrchestrator:
    return JobOrchestrator(
        settings=settings,
        pdf2zh_runner=runner or _fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
        chunk_size=999,  # deliberately wrong: must never reach plan_chunks()
    )


@pytest.mark.asyncio
async def test_cold_start_uses_20_when_no_concurrency_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """First-ever job for a `(provider, model)` pair: no `ConcurrencyState`
    row exists yet, so it must be treated as cold (not warm) -> 20.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")
    settings = Settings(pdf_translate_engine="pdf2zh")

    with patch.object(job_orchestrator_module, "plan_chunks", side_effect=real_plan_chunks) as spy:
        result = await orchestrator_run(session, tmp_path, job, settings)

    assert result.status == "completed"
    spy.assert_called_once_with(job.total_pages, job.file_size, 20, orchestrator_overlap())
    await session.refresh(job)
    assert job.chunk_size_used == 20


@pytest.mark.asyncio
async def test_cold_start_uses_20_when_observation_count_below_threshold(
    session: AsyncSession, tmp_path: Path
) -> None:
    """`ConcurrencyState` exists but hasn't converged yet (`observation_count
    < 3`) -> still cold, still 20.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")
    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"deepseek:{settings.deepseek_model}"
    session.add(
        ConcurrencyState(
            provider="deepseek",
            model=model_key,
            current_thread=16,
            observation_count=2,
            consecutive_successes=2,
        )
    )
    await session.commit()

    with patch.object(job_orchestrator_module, "plan_chunks", side_effect=real_plan_chunks) as spy:
        result = await orchestrator_run(session, tmp_path, job, settings)

    assert result.status == "completed"
    spy.assert_called_once_with(job.total_pages, job.file_size, 20, orchestrator_overlap())
    await session.refresh(job)
    assert job.chunk_size_used == 20


@pytest.mark.asyncio
async def test_warm_state_uses_40_for_new_job(session: AsyncSession, tmp_path: Path) -> None:
    """`(provider, model)` has learned: `observation_count >= 3` AND
    `consecutive_successes >= 3` -> a brand-new job for that pair gets 40.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")
    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"deepseek:{settings.deepseek_model}"
    session.add(
        ConcurrencyState(
            provider="deepseek",
            model=model_key,
            current_thread=32,
            observation_count=5,
            consecutive_successes=4,
        )
    )
    await session.commit()

    with patch.object(job_orchestrator_module, "plan_chunks", side_effect=real_plan_chunks) as spy:
        result = await orchestrator_run(session, tmp_path, job, settings)

    assert result.status == "completed"
    spy.assert_called_once_with(job.total_pages, job.file_size, 40, orchestrator_overlap())
    await session.refresh(job)
    assert job.chunk_size_used == 40


@pytest.mark.asyncio
async def test_resumed_job_reuses_persisted_chunk_size_verbatim(
    session: AsyncSession, tmp_path: Path
) -> None:
    """A job that already ran once (`chunk_size_used` persisted, e.g. from a
    cold-start run) must NOT recompute on resume, even if `ConcurrencyState`
    has since warmed up past the threshold — recomputing would desync the
    already-persisted `Chunk.page_start`/`page_end` rows from a new plan
    (Bug #5-shaped lineage break, per 6.12.7's "Rang buoc bat buoc").
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")
    job.chunk_size_used = 20
    session.add(job)
    settings = Settings(pdf_translate_engine="pdf2zh")
    model_key = f"deepseek:{settings.deepseek_model}"
    # State has since warmed up -- must be ignored because chunk_size_used
    # is already set.
    session.add(
        ConcurrencyState(
            provider="deepseek",
            model=model_key,
            current_thread=40,
            observation_count=10,
            consecutive_successes=10,
        )
    )
    await session.commit()

    with patch.object(job_orchestrator_module, "plan_chunks", side_effect=real_plan_chunks) as spy:
        result = await orchestrator_run(session, tmp_path, job, settings)

    assert result.status == "completed"
    spy.assert_called_once_with(job.total_pages, job.file_size, 20, orchestrator_overlap())
    await session.refresh(job)
    assert job.chunk_size_used == 20


@pytest.mark.asyncio
async def test_ollama_gets_cold_start_20_without_reading_concurrency_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Ollama never participates in AIMD (6.12.6/6.12.7): it must get the
    cold-start 20 permanently, and — the invariant this test really guards —
    must not read or create a `ConcurrencyState` row on the way there
    (`ADAPTIVE_THREAD_FLOOR` has no "ollama" key; creating one would
    `KeyError`).
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="ollama")
    settings = Settings(pdf_translate_engine="pdf2zh")

    with patch.object(job_orchestrator_module, "plan_chunks", side_effect=real_plan_chunks) as spy:
        result = await orchestrator_run(session, tmp_path, job, settings)

    assert result.status == "completed"
    spy.assert_called_once_with(job.total_pages, job.file_size, 20, orchestrator_overlap())
    await session.refresh(job)
    assert job.chunk_size_used == 20
    assert (await session.exec(select(ConcurrencyState))).all() == []


@pytest.mark.asyncio
async def test_adaptive_disabled_gets_cold_start_20_without_reading_concurrency_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    """The `adaptive_concurrency_enabled=False` kill switch is the safe
    rollback path (6.12.8): no `ConcurrencyState` read/write at all, so there
    is no warm signal to promote to 40 — chunk_size stays at the conservative
    20. An already-warm row must be ignored, not consulted.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, _SMALL_PAGES)
    job = await _create_job(session, source_pdf, model="deepseek")
    settings = Settings(pdf_translate_engine="pdf2zh", adaptive_concurrency_enabled=False)
    session.add(
        ConcurrencyState(
            provider="deepseek",
            model=f"deepseek:{settings.deepseek_model}",
            current_thread=32,
            observation_count=10,
            consecutive_successes=10,
        )
    )
    await session.commit()

    with patch.object(job_orchestrator_module, "plan_chunks", side_effect=real_plan_chunks) as spy:
        result = await orchestrator_run(session, tmp_path, job, settings)

    assert result.status == "completed"
    spy.assert_called_once_with(job.total_pages, job.file_size, 20, orchestrator_overlap())
    await session.refresh(job)
    assert job.chunk_size_used == 20


def orchestrator_overlap() -> int:
    """`JobOrchestrator.__init__`'s default `overlap`, used by
    `orchestrator_run()` below -- kept as a named constant so the
    `spy.assert_called_once_with(...)` calls above read as "whatever
    `_orchestrator()` was built with", not a magic number.
    """
    return 2


async def orchestrator_run(session: AsyncSession, tmp_path: Path, job, settings: Settings):
    orchestrator = _orchestrator(settings, tmp_path)
    return await orchestrator.run_job(job.id, session)
