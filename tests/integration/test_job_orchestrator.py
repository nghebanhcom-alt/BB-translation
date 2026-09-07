import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.chunk import Chunk
from src.models.job import Job
from src.postprocess.image_compress import ImageCompressStats
from src.postprocess.rotated_text_overlay import OverlayResult
from src.services.babeldoc_runner import BabeldocResult, BabeldocRunner
from src.services.mineru_runner import (
    MinerUResult,
    MinerURunner,
    MinerUUnavailableError,
    OcrQuality,
)
from src.services.pdf2zh_runner import Pdf2zhError, Pdf2zhResult, Pdf2zhRunner
from src.services.pdf2zh_service_map import Pdf2zhServiceMapper, UnsupportedForPdfPipelineError

TOTAL_PAGES = 90
# fitz.open().new_page() with no explicit size defaults to A4 (Rect(0,0,595,842)) —
# the fixture middle.json below must match, or the S17 coordinate guard in
# src/preprocess/searchable_pdf.py fails the bridge on purpose.
_PAGE_SIZE = [595.0, 842.0]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _make_pdf(path: Path, n_pages: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((50, 100), f"page {i + 1}", fontsize=10)
    doc.save(path)
    doc.close()


def _fake_pdf2zh_runner(fail_on_call_index: int | None = None) -> Pdf2zhRunner:
    """Real chunks worth of pages get created on disk so post-processing
    (font_shrink, chunk_merge) runs against real PyMuPDF files, not mocks.
    `fail_on_call_index` simulates pdf2zh itself failing on the Nth call
    (0-based) — this is the ONLY thing that should be able to fail a chunk
    now that Job Orchestrator no longer calls `provider.translate()`
    (Architecture.md 6.6.2 R1).

    Bug #7 fix: mirrors the REAL `pdf2zh` output shape (verified against a
    real `pdf2zh` run, see `tests/fixtures/pdf2zh/README.md`) — each call's
    `{stem}-mono.pdf` contains every page of `input_path` (the full source
    document, same across all chunks), not just the `page_range` requested.
    Building it as chunk-scoped (`n_pages=end-start+1`, the old assumption)
    is exactly the un-verified mock shape that hid Bug #7 through every
    prior review/QA round.
    """
    runner = AsyncMock(spec=Pdf2zhRunner)
    call_counter = {"n": 0}

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, **kwargs
    ):
        call_index = call_counter["n"]
        call_counter["n"] += 1
        if fail_on_call_index is not None and call_index == fail_on_call_index:
            raise Pdf2zhError("simulated pdf2zh failure")

        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}-mono.pdf"
        _make_pdf(mono_path, n_pages=total_pages)
        return Pdf2zhResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages
    return runner


class _FakePricingProvider:
    """Out-of-band pricing provider (Architecture.md 6.6.2 R3): only
    `.estimate_cost()` is ever called on it from `JobOrchestrator` now —
    `.translate()` would fail loudly (not implemented here) if the fix
    regressed and something tried to call it again.
    """

    provider_name = "mock"

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round((input_tokens + output_tokens) * 0.0001, 6)


async def _create_job(
    session: AsyncSession, source_pdf: Path, model: str = "deepseek", file_type: str = "pdf_digital"
) -> Job:
    job = Job(
        filename="book.pdf",
        file_path=str(source_pdf),
        file_size=source_pdf.stat().st_size,
        file_hash="deadbeef",
        file_type=file_type,
        model=model,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def _middle_json_for(n_pages: int, *, confidence: float = 0.92) -> dict:
    """Shape copied from the real `middle_json` contract (Architecture.md
    6.9.2/6.10.4/S17), not reinvented from memory (Protocol 5 R5-02): one
    text span per page, `page_size` matching `_PAGE_SIZE` so the coordinate
    guard in `build_searchable_pdf()` passes.
    """
    return {
        "pdf_info": [
            {
                "page_idx": i,
                "page_size": _PAGE_SIZE,
                "preproc_blocks": [
                    {
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "type": "text",
                                        "content": f"OCR text page {i + 1}",
                                        "bbox": [50.0, 50.0, 300.0, 70.0],
                                        "score": confidence,
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "discarded_blocks": [],
            }
            for i in range(n_pages)
        ]
    }


def _fake_mineru_runner(
    tmp_path: Path, *, confidence: float = 0.92, no_text_spans: bool = False
) -> MinerURunner:
    """Bug #2 (QA Round 1): mocked the same way `_fake_pdf2zh_runner()` mocks
    pdf2zh above — `parse_document()` must be awaited (writing a confidence
    score onto the job) before any `pdf2zh_runner.translate_pages()` call for
    a `pdf_scan` job. `middle_json_path` is a REAL file with real span shape
    (Protocol 5 R5-02) so `build_searchable_pdf()` runs for real against it —
    the bridge is exactly what Bug #5's fix depends on, not a detail safe to
    mock away. `no_text_spans=True` simulates a scan MinerU could not read at
    all (BR-OCR-02).
    """
    runner = AsyncMock(spec=MinerURunner)

    async def _parse_document(file_path, output_dir, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "document.md"
        markdown_path.write_text("ocr text", encoding="utf-8")
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        with fitz.open(file_path) as doc:
            n_pages = doc.page_count

        middle = _middle_json_for(n_pages, confidence=confidence)
        if no_text_spans:
            for page in middle["pdf_info"]:
                for block in page["preproc_blocks"]:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            span["type"] = "image"

        middle_json_path = output_dir / "middle.json"
        middle_json_path.write_text(json.dumps(middle), encoding="utf-8")

        return MinerUResult(
            markdown_path=markdown_path,
            images_dir=images_dir,
            quality=OcrQuality(
                confidence=confidence,
                ocr_span_count=n_pages,
                dropped_span_count=1,
                source="middle_json_span_scores",
            ),
            task_id="fake-task-id",
            middle_json_path=middle_json_path,
        )

    runner.parse_document.side_effect = _parse_document
    return runner


@pytest.mark.asyncio
async def test_run_job_completes_with_three_chunks(session: AsyncSession, tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    # Pin chunk_size_used=40 (Architecture.md 6.12.7): this test is about
    # chunk completion/merge, not cold-start sizing -- without this, a
    # fresh (provider, model) with no ConcurrencyState defaults to cold
    # (20), which would split TOTAL_PAGES=90 into 5 chunks, not 3.
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
    assert result.output_path is not None
    assert result.bilingual_path is None  # no batch -> vi_only default

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert len(chunks) == 3
    assert [c.status for c in chunks] == ["completed", "completed", "completed"]
    assert all(c.api_tokens_used is not None and c.api_tokens_used > 0 for c in chunks)
    assert all(c.api_cost is not None and c.api_cost >= 0 for c in chunks)
    # F9: every chunk rendered to its own output dir, no overwriting.
    assert len({c.output_path for c in chunks}) == 3

    await session.refresh(job)
    assert job.status == "completed"
    assert job.actual_cost == pytest.approx(sum(c.api_cost for c in chunks))
    assert job.cost_source == "estimated"
    assert job.current_chunk == 3
    assert job.total_chunks == 3

    with fitz.open(result.output_path) as merged:
        assert merged.page_count == TOTAL_PAGES

    # Prompt file was written once for the whole job (Architecture.md 6.6.4/6.6.5).
    prompt_path = tmp_path / "processing" / job.id / "prompt.txt"
    assert prompt_path.exists()
    assert "${text}" in prompt_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_job_is_resumable_after_a_chunk_fails(
    session: AsyncSession, tmp_path: Path
) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, TOTAL_PAGES)
    job = await _create_job(session, source_pdf)
    # See test_run_job_completes_with_three_chunks: pin chunk_size_used so
    # this resumability test isn't coupled to cold-start sizing (6.12.7).
    job.chunk_size_used = 40
    session.add(job)
    await session.commit()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(fail_on_call_index=1),  # chunk index 1 fails
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    first_result = await orchestrator.run_job(job.id, session)
    assert first_result.status == "failed"

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert [c.status for c in chunks] == ["completed", "failed", "pending"]

    # Resume: only the failed/pending chunks should hit pdf2zh again.
    resumed_runner = _fake_pdf2zh_runner()
    orchestrator._pdf2zh_runner = resumed_runner

    second_result = await orchestrator.run_job(job.id, session)

    assert second_result.status == "completed"
    assert resumed_runner.translate_pages.await_count == 2  # chunk 1 + chunk 2, not chunk 0 again

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = sorted(chunks_result.all(), key=lambda c: c.chunk_index)
    assert len(chunks) == 3
    assert all(c.status == "completed" for c in chunks)


@pytest.mark.asyncio
async def test_run_job_with_deepl_fails_before_any_subprocess_call(
    session: AsyncSession, tmp_path: Path
) -> None:
    """The bug this fix targets: DeepL cannot receive glossary/prompt on the
    PDF pipeline (Architecture.md 6.6.7 #1, PRD BR-PROVIDER-01). `run_job()`
    must reject it via `Pdf2zhServiceMapper` BEFORE calling pdf2zh, not crash
    inside the subprocess or silently ignore the glossary.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)  # small, single-chunk job
    job = await _create_job(session, source_pdf, model="deepl")

    pdf2zh_runner = _fake_pdf2zh_runner()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    assert "DeepL" in result.error_message
    pdf2zh_runner.translate_pages.assert_not_awaited()

    await session.refresh(job)
    assert job.status == "failed"
    assert "DeepL" in job.error_message


@pytest.mark.asyncio
async def test_run_job_calls_mineru_before_pdf2zh_for_pdf_scan(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Bug #2 (QA Round 1): a `pdf_scan` job must run MinerU OCR before
    handing pages to `pdf2zh` — otherwise a scanned PDF with no text layer
    silently translates to empty/garbage output with no warning.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    call_order: list[str] = []
    pdf2zh_runner = _fake_pdf2zh_runner()

    async def _tracked_translate_pages(*args, **kwargs):
        call_order.append("pdf2zh")
        return await pdf2zh_runner.translate_pages.side_effect(*args, **kwargs)

    mineru_runner = _fake_mineru_runner(tmp_path)

    async def _tracked_parse_document(*args, **kwargs):
        call_order.append("mineru")
        return await mineru_runner.parse_document.side_effect(*args, **kwargs)

    tracked_pdf2zh = AsyncMock(spec=Pdf2zhRunner)
    tracked_pdf2zh.translate_pages.side_effect = _tracked_translate_pages
    tracked_mineru = AsyncMock(spec=MinerURunner)
    tracked_mineru.parse_document.side_effect = _tracked_parse_document

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=tracked_pdf2zh,
        mineru_runner=tracked_mineru,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    tracked_mineru.parse_document.assert_awaited_once()
    assert call_order[0] == "mineru"
    assert "pdf2zh" in call_order

    await session.refresh(job)
    assert job.ocr_confidence == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_run_job_does_not_call_mineru_for_pdf_digital(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Companion to the pdf_scan test above: a born-digital PDF already has a
    text layer, so OCR must be skipped even though a `mineru_runner` is
    injected.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    tracked_mineru = AsyncMock(spec=MinerURunner)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=tracked_mineru,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    tracked_mineru.parse_document.assert_not_awaited()

    await session.refresh(job)
    assert job.ocr_confidence is None


def _fake_pdf2zh_runner_empty_output() -> Pdf2zhRunner:
    """BR-OCR-03 fixture: pdf2zh "succeeds" but the mono PDF it writes has no
    text on any page — the exact shape of Bug #5's original symptom
    (`status="completed"`, 0 readable characters).
    """
    runner = AsyncMock(spec=Pdf2zhRunner)

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, **kwargs
    ):
        start, end = (int(x) for x in page_range.split("-"))
        mono_path = output_dir / f"{input_path.stem}-mono.pdf"
        mono_path.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open()
        for _ in range(end - start + 1):
            doc.new_page()  # no insert_text -> zero extractable characters
        doc.save(mono_path)
        doc.close()
        return Pdf2zhResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages
    return runner


@pytest.mark.asyncio
async def test_pdf_scan_translates_bridge_not_original(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 (CLAUDE.md Protocol 6): the test Bug #5 needed all along —
    assert the ACTUAL VALUE passed to `pdf2zh_runner.translate_pages()`, not
    just that it was called. Must be the searchable-PDF bridge built from the
    OCR result, and must NOT be `job.file_path` (the original scan with no
    text layer) — that substitution is exactly what silently broke
    translation in Bug #5.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    pdf2zh_runner = _fake_pdf2zh_runner()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    expected_bridge = tmp_path / "processing" / job.id / "ocr_bridge" / "searchable.pdf"
    for call in pdf2zh_runner.translate_pages.await_args_list:
        assert call.kwargs["input_path"] == expected_bridge
        assert call.kwargs["input_path"] != Path(job.file_path)
    assert expected_bridge.exists()

    await session.refresh(job)
    assert job.ocr_bridge_path == str(expected_bridge)


def _fake_babeldoc_runner() -> BabeldocRunner:
    """Same shape as `_fake_pdf2zh_runner()` but returning `BabeldocResult`
    with babeldoc's own filename pattern (Architecture.md 6.14.1 B7)."""
    runner = AsyncMock(spec=BabeldocRunner)

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, lang_out="vi", **kwargs
    ):
        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}.no_watermark.{lang_out}.mono.pdf"
        _make_pdf(mono_path, n_pages=total_pages)
        return BabeldocResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages
    return runner


@pytest.mark.asyncio
async def test_babeldoc_engine_writes_babeldoc_prompt_contract_not_pdf2zh(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Regression guard for the confirmed root cause (2026-09-05): when
    `pdf_translate_engine="babeldoc"`, the `prompt_file` Job Orchestrator
    hands to `BabeldocRunner.translate_pages()` must be built by
    `write_babeldoc_prompt_file()` (no `${...}` template tokens, no pdf2zh
    `Source Text:/Translated Text:` footer) — NOT `write_prompt_file()`'s
    pdf2zh-only content, which babeldoc has no substitution mechanism for and
    which contradicts babeldoc's own JSON-array output contract, previously
    causing silently dropped paragraphs. This asserts the actual FILE
    CONTENT the babeldoc subprocess would receive, not just that the runner
    was called (Architecture.md Protocol 6 R6-02 style: data lineage, not
    call-count)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    babeldoc_runner = _fake_babeldoc_runner()
    settings = Settings(pdf_translate_engine="babeldoc")

    orchestrator = JobOrchestrator(
        settings=settings,
        babeldoc_runner=babeldoc_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert babeldoc_runner.translate_pages.await_args_list
    for call in babeldoc_runner.translate_pages.await_args_list:
        prompt_content = call.kwargs["prompt_file"].read_text(encoding="utf-8")
        assert "${lang_in}" not in prompt_content
        assert "${text}" not in prompt_content
        assert "Source Text:" not in prompt_content
        assert "Translated Text:" not in prompt_content
        assert "chi in ra ban dich" not in prompt_content.lower()


@pytest.mark.asyncio
async def test_babeldoc_split_short_lines_defaults_to_enabled_with_babeldoc_factor(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md "Root Cause Analysis: Line-break/List Regression" +
    "Đo lại F1 trên nhiều trang — kết quả live A/B/C" (2026-09-06): `Settings`
    default flipped TWICE based on 2 real measurements — first to
    `False`/`0.5` (1-page spike suggested RC-1 harm was broad), then to
    `True`/`0.8` (a 21-run/7-page live A/B/C study found the OPPOSITE:
    `factor=0.5` was the WORST of the 3 configurations measured — it kept
    almost all of `False`'s list-merging harm while still paying nearly the
    full RC-1 cost; `factor=0.8`, babeldoc's OWN built-in default, fixed
    numbered lists/TOC far more (e.g. the 35-item list page: 28 glued spots
    -> 3) while RC-1's real damage turned out to be narrow — limited to a
    handful of table/image captions, never ordinary body text, across all 7
    pages tested). This asserts the CURRENT correct production default is
    ENABLED with `factor=0.8` — asserting the actual kwargs `JobOrchestrator`
    passes to the real call (Protocol 6 R6-02), not just that the runner was
    awaited."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    babeldoc_runner = _fake_babeldoc_runner()
    settings = Settings(pdf_translate_engine="babeldoc")
    # Default, sanity check — these are the values Architecture.md's live
    # A/B/C study recommends, NOT the safer-looking `False`/`0.5` shipped
    # in the first round (measured to be the worst of 3 configurations).
    assert settings.babeldoc_split_short_lines is True
    assert settings.babeldoc_short_line_split_factor == 0.8

    orchestrator = JobOrchestrator(
        settings=settings,
        babeldoc_runner=babeldoc_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert babeldoc_runner.translate_pages.await_args_list
    for call in babeldoc_runner.translate_pages.await_args_list:
        assert call.kwargs["split_short_lines"] is True
        assert call.kwargs["short_line_split_factor"] == 0.8


@pytest.mark.asyncio
async def test_babeldoc_split_short_lines_can_be_opted_out_via_settings(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Same lineage guard as above, opposite direction: an operator who
    explicitly sets `Settings.babeldoc_split_short_lines=False` (e.g. for a
    document type where the narrow RC-1 caption-cutting cost matters more
    than the list-merging benefit) must have that override actually reach
    `BabeldocRunner.translate_pages()` — asserting the concrete kwargs
    value, not merely that the setting field exists on `Settings`. When
    disabled, `short_line_split_factor` must be `None` (has no effect on its
    own per babeldoc's own `and` condition, `paragraph_finder.py:891`) even
    if a non-default factor happens to be configured alongside it."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    babeldoc_runner = _fake_babeldoc_runner()
    settings = Settings(
        pdf_translate_engine="babeldoc",
        babeldoc_split_short_lines=False,
        babeldoc_short_line_split_factor=0.5,
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        babeldoc_runner=babeldoc_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert babeldoc_runner.translate_pages.await_args_list
    for call in babeldoc_runner.translate_pages.await_args_list:
        assert call.kwargs["split_short_lines"] is False
        assert call.kwargs["short_line_split_factor"] is None


@pytest.mark.asyncio
async def test_pdf_scan_babeldoc_engine_translates_bridge_not_original(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 companion for the babeldoc engine (Architecture.md 6.14.4): the
    SAME lineage guarantee `test_pdf_scan_translates_bridge_not_original`
    checks for pdf2zh must hold when `pdf_translate_engine="babeldoc"` —
    `BabeldocRunner.translate_pages()` must receive the OCR searchable-PDF
    bridge, NEVER `job.file_path` (the Bug #5 mistake, reintroducible on this
    brand-new code path if `source_path` were swapped back to the original
    scan inside the babeldoc branch).
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    babeldoc_runner = _fake_babeldoc_runner()
    settings = Settings(pdf_translate_engine="babeldoc")

    orchestrator = JobOrchestrator(
        settings=settings,
        babeldoc_runner=babeldoc_runner,
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    expected_bridge = tmp_path / "processing" / job.id / "ocr_bridge" / "searchable.pdf"
    assert babeldoc_runner.translate_pages.await_args_list  # engine was actually used
    for call in babeldoc_runner.translate_pages.await_args_list:
        assert call.kwargs["input_path"] == expected_bridge
        assert call.kwargs["input_path"] != Path(job.file_path)
    assert expected_bridge.exists()

    await session.refresh(job)
    assert job.ocr_bridge_path == str(expected_bridge)


@pytest.mark.asyncio
async def test_pdf_scan_babeldoc_overlay_uses_bridge_not_original(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """R6-04 (review-report.md, vong 1 REJECT): `pdf_translate_engine=babeldoc`
    is independent of `job.file_type` — a PDF_SCAN job with the babeldoc
    engine is a valid, common production combination, and
    `overlay_rotated_text()` must read the SAME OCR searchable-PDF bridge
    Step 7 feeds `babeldoc_runner.translate_pages()`, never the raw scan
    (`job.file_path`/`file_path`) which has no text layer for
    `scan_rotated_lines()` to find anything in. Reading the raw scan doesn't
    raise — it silently returns zero rotated lines every time, so this bug
    has the exact Bug #5 shape (status="completed", feature silently never
    runs). Companion to `test_pdf_scan_babeldoc_engine_translates_bridge_not_original`
    above, same lineage guarantee, one step later in the pipeline."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    babeldoc_runner = _fake_babeldoc_runner()
    settings = Settings(pdf_translate_engine="babeldoc", babeldoc_rotated_text_overlay=True)

    overlay_spy = mocker.patch(
        "src.core.job_orchestrator.overlay_rotated_text",
        new=AsyncMock(
            return_value=OverlayResult(findings=[], overlaid_block_count=0, flagged_block_count=0)
        ),
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        babeldoc_runner=babeldoc_runner,
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    expected_bridge = tmp_path / "processing" / job.id / "ocr_bridge" / "searchable.pdf"
    overlay_spy.assert_awaited_once()
    called_source = overlay_spy.await_args.kwargs["source_pdf_path"]
    assert Path(called_source) == expected_bridge
    assert Path(called_source) != Path(job.file_path)


@pytest.mark.asyncio
async def test_pdf_digital_still_uses_original(session: AsyncSession, tmp_path: Path) -> None:
    """No-regression companion to the bridge test above: a born-digital job
    has no bridge, so pdf2zh must receive `job.file_path` unchanged."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    pdf2zh_runner = _fake_pdf2zh_runner()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    for call in pdf2zh_runner.translate_pages.await_args_list:
        assert call.kwargs["input_path"] == Path(job.file_path)


@pytest.mark.asyncio
async def test_bilingual_uses_original_scan_not_bridge(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """Architecture.md 6.10.5 point 3: the bilingual output's EN side must be
    the real original scan (what a human actually needs to see), not the
    bridge with its glyph areas painted over.
    """
    from src.models.batch import Batch

    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)

    batch = Batch(total_files=1, output_mode="bilingual", model="deepseek")
    session.add(batch)
    await session.commit()
    await session.refresh(batch)

    job = Job(
        batch_id=batch.id,
        filename="book.pdf",
        file_path=str(source_pdf),
        file_size=source_pdf.stat().st_size,
        file_hash="deadbeef",
        file_type="pdf_scan",
        model="deepseek",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    bilingual_spy = mocker.patch("src.core.job_orchestrator.create_bilingual_pdf", new=AsyncMock())

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    bilingual_spy.assert_awaited_once()
    call = bilingual_spy.await_args
    assert call.args[1] == source_pdf  # EN side == original scan, not the bridge


@pytest.mark.asyncio
async def test_empty_translation_fails_job(session: AsyncSession, tmp_path: Path) -> None:
    """BR-OCR-03: even if every chunk "succeeds", a merged output with zero
    readable characters must fail the job — never report "completed" over an
    empty translation (Bug #5's exact symptom)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner_empty_output(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    assert "khong chua chu nao" in result.error_message

    await session.refresh(job)
    assert job.status == "failed"


@pytest.mark.asyncio
async def test_pdf_scan_without_mineru_configured_fails_before_pdf2zh(
    session: AsyncSession, tmp_path: Path
) -> None:
    """BR-OCR-01: this exact silent fallback (scan job, no MinerU configured,
    translate the original file anyway) is how Bug #5 happened. Must raise
    loudly and never reach `pdf2zh_runner`."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    pdf2zh_runner = _fake_pdf2zh_runner()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        mineru_runner=None,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with pytest.raises(MinerUUnavailableError):
        await orchestrator.run_job(job.id, session)

    pdf2zh_runner.translate_pages.assert_not_awaited()


@pytest.mark.asyncio
async def test_ocr_warning_emitted_when_confidence_below_threshold(
    session: AsyncSession, tmp_path: Path
) -> None:
    """US-11 / AC-11.2 (Architecture.md 6.10.6): low confidence must emit the
    WebSocket `ocr_warning` event but NOT block the job."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    events: list[dict] = []

    async def _broadcast(job_id: str, event: dict) -> None:
        events.append(event)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=_fake_mineru_runner(tmp_path, confidence=0.5),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
        progress_broadcaster=_broadcast,
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    warning_events = [e for e in events if e.get("type") == "ocr_warning"]
    assert len(warning_events) == 1
    assert warning_events[0]["confidence"] == pytest.approx(0.5)


def test_pdf2zh_service_mapper_rejects_deepl_directly() -> None:
    """Unit-level companion to the job-orchestrator test above: the mapper
    itself must raise, independent of any orchestration around it."""
    from src.core.config import Settings

    mapper = Pdf2zhServiceMapper()
    with pytest.raises(UnsupportedForPdfPipelineError):
        mapper.map("deepl", Settings())


@pytest.mark.asyncio
async def test_babeldoc_engine_compresses_merged_output_with_correct_lineage(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """US-16/BR-IMGCOMP-01 + Protocol 6 R6-02: a bare `assert_awaited()` would
    have missed Bug #5's exact failure class (right call, wrong/no data
    lineage). This asserts `compress_pdf_images` is called with the SAME path
    `merge_chunk_pdfs()` just wrote — `merged_path`, which becomes
    `result.output_path` — never `job.file_path` (the pre-merge source) or
    any other stand-in (Architecture.md US-16 S5 lineage table)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    babeldoc_runner = _fake_babeldoc_runner()
    settings = Settings(pdf_translate_engine="babeldoc")

    compress_spy = mocker.patch(
        "src.core.job_orchestrator.compress_pdf_images",
        new=AsyncMock(return_value=ImageCompressStats()),
    )

    orchestrator = JobOrchestrator(
        settings=settings,
        babeldoc_runner=babeldoc_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    compress_spy.assert_awaited_once()
    called_path = compress_spy.await_args.args[0]
    assert Path(called_path) == Path(result.output_path)
    assert Path(called_path) != Path(job.file_path)


@pytest.mark.asyncio
async def test_pdf2zh_engine_does_not_compress_images(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """BR-IMGCOMP-01: `pdf2zh` jobs must not change behavior at all — image
    compression is gated strictly to `pdf_translate_engine == "babeldoc"`."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    compress_spy = mocker.patch(
        "src.core.job_orchestrator.compress_pdf_images",
        new=AsyncMock(return_value=ImageCompressStats()),
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    compress_spy.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_translation_fails_before_compress_runs(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """Architecture.md US-16 S5: compression must run AFTER the BR-OCR-03
    empty-text guard, so a compression bug never gets misdiagnosed as "no
    text found" and vice versa. A job whose merged output has zero readable
    characters must fail with the BR-OCR-03 message, and `compress_pdf_images`
    must never be reached for it — even with `pdf_translate_engine=babeldoc`."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    compress_spy = mocker.patch(
        "src.core.job_orchestrator.compress_pdf_images",
        new=AsyncMock(return_value=ImageCompressStats()),
    )

    babeldoc_runner = AsyncMock(spec=BabeldocRunner)

    async def _translate_pages_empty(
        input_path, output_dir, page_range, service, prompt_file=None, lang_out="vi", **kwargs
    ):
        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}.no_watermark.{lang_out}.mono.pdf"
        mono_path.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open()
        for _ in range(total_pages):
            doc.new_page()  # no text inserted -> BR-OCR-03 guard trips
        doc.save(mono_path)
        doc.close()
        return BabeldocResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    babeldoc_runner.translate_pages.side_effect = _translate_pages_empty

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="babeldoc"),
        babeldoc_runner=babeldoc_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    assert "khong chua chu nao" in result.error_message
    compress_spy.assert_not_awaited()
