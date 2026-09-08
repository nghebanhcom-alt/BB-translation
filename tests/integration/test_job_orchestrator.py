import hashlib
import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import EpubNotSupportedError, JobOrchestrator
from src.models.chunk import Chunk
from src.models.job import Job
from src.models.layout_qa import LayoutQaFinding
from src.models.overflow import OverflowReport
from src.postprocess.font_shrink import font_shrink_page as _real_font_shrink_page
from src.postprocess.image_compress import ImageCompressStats
from src.postprocess.rotated_text_overlay import OverlayResult
from src.services.babeldoc_runner import BabeldocResult, BabeldocRunner
from src.services.layout_qa import ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK, LayoutQaFindingData
from src.services.mineru_det_probe import MineruDetProbeUnavailableError
from src.services.mineru_runner import (
    MinerUCancelledError,
    MinerUResult,
    MinerURunner,
    MinerUUnavailableError,
    OcrQuality,
)
from src.services.pdf2zh_runner import Pdf2zhError, Pdf2zhResult, Pdf2zhRunner
from src.services.pdf2zh_service_map import Pdf2zhServiceMapper, UnsupportedForPdfPipelineError

#: US-15: golden fixture directory (Protocol 5 mục 3), captured from a real
#: live MinerURunner.parse_document(parse_method="txt") run against MinerU
#: 3.4.5 — see tests/fixtures/mineru/parse_only_txt_figoni25/README.md.
_PARSE_ONLY_FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "mineru" / "parse_only_txt_figoni25"
)

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
    runner.needs_font_shrink = True
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
    tracked_pdf2zh.needs_font_shrink = True
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
    runner.needs_font_shrink = True

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
    runner.needs_font_shrink = False

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
    babeldoc_runner.needs_font_shrink = False

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


# --- Bug #6 Phase 1 (Architecture.md "Final Decision" V6): rotated-text ---
# --- detector probe for pdf_scan jobs — best-effort, correct lineage -----


@pytest.mark.asyncio
async def test_pdf_scan_runs_rotated_text_det_probe_with_correct_lineage(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """R6-01/R6-02: the probe must read the RAW scan (`job.file_path`, same
    variable Step 2 passes to `_build_ocr_bridge()` — NOT the searchable-PDF
    bridge, which has already had its OCR'd spans whited out, so a detector
    run against it would find nothing) and THIS job's own `middle.json`
    (written by `_fake_mineru_runner()` under `ocr_output/middle.json`, same
    path `build_searchable_pdf()` itself consumes). Also asserts a real
    finding row lands in `layout_qa_findings`, not just that the mock was
    called (R6-02)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    fake_finding = LayoutQaFindingData(
        page_number=1,
        check_type=ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK,
        severity="blocker",
        detail={"angle_deg": -11.0, "bbox": [0.0, 0.0, 10.0, 10.0], "matched_texts": ["x"]},
    )
    probe_spy = mocker.patch(
        "src.core.job_orchestrator.probe_and_flag_rotated_text",
        new=AsyncMock(return_value=[fake_finding]),
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", mineru_det_probe_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    probe_spy.assert_awaited_once()
    called_file_path = probe_spy.await_args.args[0]
    called_middle_json_path = probe_spy.await_args.args[1]
    assert Path(called_file_path) == Path(job.file_path)
    expected_middle_json = tmp_path / "processing" / job.id / "ocr_output" / "middle.json"
    assert Path(called_middle_json_path) == expected_middle_json

    rows = (
        await session.exec(
            select(LayoutQaFinding).where(
                LayoutQaFinding.job_id == job.id,
                LayoutQaFinding.check_type == ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK,
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].page_number == 1


@pytest.mark.asyncio
async def test_pdf_scan_det_probe_failure_does_not_fail_job(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """Bug #6 V6 step 6 explicit instruction: a det-probe bug (e.g. the
    MinerU interpreter isn't installed) must be logged (task P0) and
    swallowed — never fail an otherwise-successful OCR/translation job."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    mocker.patch(
        "src.core.job_orchestrator.probe_and_flag_rotated_text",
        new=AsyncMock(side_effect=MineruDetProbeUnavailableError("interpreter khong ton tai")),
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", mineru_det_probe_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"

    rows = (
        await session.exec(
            select(LayoutQaFinding).where(
                LayoutQaFinding.check_type == ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK
            )
        )
    ).all()
    assert rows == []


@pytest.mark.asyncio
async def test_pdf_scan_det_probe_disabled_by_flag(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """`mineru_det_probe_enabled=False` is the instant-rollback switch
    (matching `babeldoc_rotated_text_overlay`'s pattern) — must skip the
    probe call entirely, not just discard its result."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    probe_spy = mocker.patch(
        "src.core.job_orchestrator.probe_and_flag_rotated_text",
        new=AsyncMock(return_value=[]),
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", mineru_det_probe_enabled=False),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=_fake_mineru_runner(tmp_path),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    probe_spy.assert_not_awaited()


# --- US-15 (Architecture.md 6.15.3) — Markdown parse-only, PDF branch -----


async def _create_parse_only_job(
    session: AsyncSession,
    source_pdf: Path,
    file_type: str = "pdf_digital",
    parse_method: str | None = None,
) -> Job:
    """`parse_method=None` (default) mirrors a Job row that never went
    through `POST /api/jobs`'s `_resolve_parse_method()` — exercises
    `run_parse_only()`'s fallback mapping (unchanged S15 behaviour). Pass an
    explicit `"txt"`/`"ocr"` to simulate a job created WITH a resolved
    override already on it (Architecture.md 6.21.3), same as
    `Job.chunk_size_used` never being "auto" in the DB.
    """
    job = Job(
        filename="book.pdf",
        file_path=str(source_pdf),
        file_size=source_pdf.stat().st_size,
        file_hash="deadbeef-parse",
        file_type=file_type,
        job_type="parse_only",
        parse_method=parse_method,
        model="deepseek",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def _fake_mineru_runner_for_parse_only(
    *,
    markdown_text: str = "# Chuong 1\n\nNoi dung mau.\n",
    n_images: int = 2,
    confidence: float = 0.997628187250996,
    ocr_span_count: int = 1004,
    dropped_span_count: int = 6,
    capture_calls: list[dict] | None = None,
    health_error: Exception | None = None,
) -> MinerURunner:
    """US-15 parse-only fixture: unlike `_fake_mineru_runner()` above (built
    for the translate/OCR-bridge tests, which only needs a placeholder
    `document.md` and no image files), this writes REAL Markdown content and
    REAL image files, since S15-3's ZIP packaging step reads them off disk.
    `capture_calls` records every `parse_document()` kwargs dict — used for
    R6-02-style assertions on `parse_method`/`task_timeout_seconds`, not
    just `assert_awaited()`.
    """
    runner = AsyncMock(spec=MinerURunner)

    if health_error is not None:
        runner.health.side_effect = health_error
    else:
        runner.health.return_value = {"status": "healthy"}

    async def _parse_document(file_path, output_dir, **kwargs):
        if capture_calls is not None:
            capture_calls.append(kwargs)

        should_cancel = kwargs.get("should_cancel")
        if should_cancel is not None and await should_cancel():
            raise MinerUCancelledError("cancelled mid-poll (fake)")

        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "document.md"
        markdown_path.write_text(markdown_text, encoding="utf-8")
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        for i in range(n_images):
            (images_dir / f"img{i}.jpg").write_bytes(b"\xff\xd8\xff fake jpeg bytes")

        return MinerUResult(
            markdown_path=markdown_path,
            images_dir=images_dir,
            quality=OcrQuality(
                confidence=confidence,
                ocr_span_count=ocr_span_count,
                dropped_span_count=dropped_span_count,
                source="middle_json_span_scores",
            ),
            task_id="fake-parse-task-id",
            middle_json_path=None,
        )

    runner.parse_document.side_effect = _parse_document
    return runner


@pytest.mark.asyncio
async def test_run_parse_only_pdf_digital_completes_and_forces_ocr_confidence_none(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-6 (rewritten after Domain Expert review): `parse_method="txt"`
    does NOT mean the runner returns `confidence is None` (MinerU 3.4.5
    assigns `score=1.0` to text-layer spans) — `run_parse_only()` must
    explicitly FORCE `ocr_confidence`/`ocr_dropped_spans` to `None` for
    `pdf_digital` regardless of what the runner reports. Also covers
    S15-3/S15-4 (eager ZIP, explicit file list) and S15-14 (`cost_source=
    "metered"`, `actual_cost=0.0`, `completed_at` set, floor-timeout branch
    of S15-14: 5 pages -> `max(600, 5*6) == 600`).
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    calls: list[dict] = []
    mineru_runner = _fake_mineru_runner_for_parse_only(
        markdown_text="# Chuong 1\n\nNoi dung mau.\n", n_images=2, capture_calls=calls
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert result.bilingual_path is None
    zip_path = Path(result.output_path)
    assert zip_path.name == "parse_result.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert names == {"document.md", "images/img0.jpg", "images/img1.jpg"}
        assert zf.read("document.md").decode("utf-8") == "# Chuong 1\n\nNoi dung mau.\n"
        assert zf.testzip() is None

    await session.refresh(job)
    assert job.status == "completed"
    # THE assertion S15-6 exists for: forced None despite the fake runner
    # "reporting" 0.9976.
    assert job.ocr_confidence is None
    assert job.ocr_dropped_spans is None
    assert job.actual_cost == 0.0
    assert job.cost_source == "metered"
    assert job.completed_at is not None
    assert job.progress == pytest.approx(1.0)

    assert len(calls) == 1
    assert calls[0]["parse_method"] == "txt"
    assert calls[0]["task_timeout_seconds"] == pytest.approx(600.0)  # S15-14 floor


@pytest.mark.asyncio
async def test_run_parse_only_pdf_scan_records_real_ocr_confidence(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-6's OTHER branch: `pdf_scan` (`parse_method="ocr"`) DOES record
    the runner's real confidence/dropped-span-count — only `pdf_digital` is
    forced to `None`."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_scan")

    calls: list[dict] = []
    mineru_runner = _fake_mineru_runner_for_parse_only(
        confidence=0.55, dropped_span_count=9, capture_calls=calls
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)
    assert job.ocr_confidence == pytest.approx(0.55)
    assert job.ocr_dropped_spans == 9

    assert len(calls) == 1
    assert calls[0]["parse_method"] == "ocr"


@pytest.mark.asyncio
async def test_run_parse_only_pdf_digital_ocr_override_still_forces_confidence_none(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.21.3 (§6.21.3's explicit warning, mirrored in
    CLAUDE.md Protocol 5/6): a user CAN override `parse_method` to `"ocr"`
    for a `pdf_digital` file (to read math/chem symbols correctly instead of
    the text-layer font-mapping bug, L-4) — but the S15-6 rule that forces
    `jobs.ocr_confidence`/`ocr_dropped_spans` to `None` for `pdf_digital`
    MUST stay keyed off `job.file_type`, NOT `job.parse_method`. This is the
    exact regression the brief warned about: if S15-6's branch were
    accidentally changed to check `parse_method == "ocr"` instead of
    `file_type == FileType.PDF_DIGITAL`, this test would catch it —
    `ocr_confidence` would leak the fake runner's 0.81 instead of staying
    `None`. R6-02: assert the concrete persisted value, not just that
    `parse_document()` was awaited.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 5)
    # Simulates a Job row created via POST /api/jobs with
    # {"job_type": "parse_only", "parse_method": "ocr"} on a pdf_digital
    # upload — `_resolve_parse_method()` already wrote "ocr" onto the row
    # (not "auto"), same as `Job.chunk_size_used` never storing "auto".
    job = await _create_parse_only_job(
        session, source_pdf, file_type="pdf_digital", parse_method="ocr"
    )

    calls: list[dict] = []
    mineru_runner = _fake_mineru_runner_for_parse_only(
        confidence=0.81, dropped_span_count=3, capture_calls=calls
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)

    # The override itself DID take effect: MinerU was actually called with
    # "ocr", not silently coerced back to the file_type default ("txt").
    assert len(calls) == 1
    assert calls[0]["parse_method"] == "ocr"
    assert job.parse_method == "ocr"

    # THE regression assertion: still forced None, exactly like the
    # un-overridden pdf_digital case — file_type, not parse_method, decides
    # this.
    assert job.ocr_confidence is None
    assert job.ocr_dropped_spans is None


@pytest.mark.asyncio
async def test_run_parse_only_pdf_digital_forces_none_using_golden_mineru_fixture(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Protocol 5 mục 3 (golden file, NOT a hand-typed mock): loads the REAL
    `middle.json` captured from a live `MinerURunner.parse_document(
    parse_method="txt")` run against MinerU 3.4.5 (Figoni 1-25p —
    tests/fixtures/mineru/parse_only_txt_figoni25/), fed through the REAL
    `MinerURunner._compute_quality()` (not a hardcoded number) to get the
    exact confidence a real run produces. A test that hand-typed
    `OcrQuality(confidence=None, ...)` would pass "for the wrong reason" —
    exactly the Protocol 5 failure mode this fixture exists to catch.
    """
    middle = json.loads((_PARSE_ONLY_FIXTURE_DIR / "middle.json").read_text(encoding="utf-8"))
    real_quality = MinerURunner._compute_quality(middle)
    assert real_quality.confidence == pytest.approx(0.997628187250996)
    assert real_quality.ocr_span_count == 1004
    assert real_quality.source == "middle_json_span_scores"

    markdown_text = (_PARSE_ONLY_FIXTURE_DIR / "document.md").read_text(encoding="utf-8")

    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 25)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    runner = AsyncMock(spec=MinerURunner)
    runner.health.return_value = {"status": "healthy"}

    async def _parse_document(file_path, output_dir, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "document.md"
        markdown_path.write_text(markdown_text, encoding="utf-8")
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        return MinerUResult(
            markdown_path=markdown_path,
            images_dir=images_dir,
            quality=real_quality,
            task_id="cdbd0988-1182-456d-bf23-791e03490bc6",
            middle_json_path=None,
        )

    runner.parse_document.side_effect = _parse_document

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)
    assert job.ocr_confidence is None  # forced None despite the golden fixture's real 0.9976
    assert job.ocr_dropped_spans is None


@pytest.mark.asyncio
async def test_run_parse_only_data_lineage_processing_to_outputs_to_zip(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.15.4 lineage table, rows (1)->(2) and (2)->(4)
    (Protocol 6 R6-02): the exact path MinerU wrote to under
    `data/processing/`, the exact path `document.md` gets copied to under
    `data/outputs/`, and the exact bytes inside `parse_result.zip` must all
    agree with each other — not just "MinerU was awaited" / "a zip exists
    somewhere"."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    mineru_runner = _fake_mineru_runner_for_parse_only(markdown_text="# Doc\n\nNoi dung that.\n")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    # (1): MinerU wrote into data/processing/{job_id}/parse_output/.
    expected_processing_md = tmp_path / "processing" / job.id / "parse_output" / "document.md"
    assert expected_processing_md.exists()
    assert expected_processing_md.read_text(encoding="utf-8") == "# Doc\n\nNoi dung that.\n"

    # (2): copied into data/outputs/{job_id}/document.md — the ONLY thing
    # later steps (guard, zip) are allowed to read from here on.
    expected_output_md = tmp_path / "outputs" / job.id / "document.md"
    assert expected_output_md.exists()
    assert expected_output_md.read_text(encoding="utf-8") == "# Doc\n\nNoi dung that.\n"

    # (4): job.output_path is exactly this zip, and the document.md entry
    # inside it is byte-identical to (2) — not re-derived from (1) or from
    # an in-memory string.
    assert result.output_path == str(tmp_path / "outputs" / job.id / "parse_result.zip")
    with zipfile.ZipFile(result.output_path) as zf:
        assert zf.read("document.md") == expected_output_md.read_bytes()


@pytest.mark.asyncio
async def test_run_parse_only_empty_markdown_fails_job(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-5 — BR-OCR-03's sibling guard for the parse branch: a Markdown
    file with 0 readable characters (after strip()) must fail the job, not
    report "completed" over nothing (Bug #5's exact shape)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    mineru_runner = _fake_mineru_runner_for_parse_only(markdown_text="   \n\t  \n")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    assert "rong" in result.error_message

    await session.refresh(job)
    assert job.status == "failed"


@pytest.mark.asyncio
async def test_run_parse_only_zip_guard_fails_job_on_corrupt_zip(
    session: AsyncSession, tmp_path: Path, mocker
) -> None:
    """§6.15.4 lineage step 5 (new guard added after Domain Expert review of
    S15-3): re-opening the just-written ZIP and finding it broken must fail
    the job — proves the guard is load-bearing, not decorative."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    mineru_runner = _fake_mineru_runner_for_parse_only()
    mocker.patch("zipfile.ZipFile.testzip", return_value="images/broken.jpg")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    assert "ZIP" in result.error_message

    await session.refresh(job)
    assert job.status == "failed"


@pytest.mark.asyncio
async def test_run_parse_only_cancelled_via_should_cancel_callback(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-13: `cancel_requested` (set by `POST /api/jobs/{id}/cancel` while
    MinerU is mid-poll) must reach `MinerURunner.parse_document()`'s
    `should_cancel` callback and result in `status="cancelled"` — NOT
    "failed" — with the job resumable/retryable exactly like a cancelled
    translate job.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")
    job.cancel_requested = True
    session.add(job)
    await session.commit()

    calls: list[dict] = []
    mineru_runner = _fake_mineru_runner_for_parse_only(capture_calls=calls)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "cancelled"
    assert calls[0]["should_cancel"] is not None

    await session.refresh(job)
    assert job.status == "cancelled"


@pytest.mark.asyncio
async def test_run_parse_only_mineru_unavailable_raises_before_touching_job_status(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-9 (YA-7.3): parse_only for pdf_digital ALSO requires MinerU to be
    reachable — health() failing must raise loudly (same uncaught-exception
    shape `_build_ocr_bridge()` already uses for `mineru_runner is None`,
    Architecture.md 6.10.5/BR-OCR-01) rather than let a job silently sit for
    up to the full timeout. Job status must be untouched — the API layer's
    `_run_job_background()` wrapper is what turns this into "failed".
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")
    status_before = job.status

    mineru_runner = _fake_mineru_runner_for_parse_only(
        health_error=MinerUUnavailableError("MinerU khong ket noi duoc (fake)")
    )

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with pytest.raises(MinerUUnavailableError):
        await orchestrator.run_job(job.id, session)

    mineru_runner.parse_document.assert_not_awaited()
    await session.refresh(job)
    assert job.status == status_before


@pytest.mark.asyncio
async def test_run_parse_only_epub_raises_without_calling_mineru(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-8 "he qua thu tu lam viec": the EPUB branch of parse-only is out
    of scope for this increment. `create_job()`/`create_batch()` already
    block this at the API layer (HTTP 400, no Job row) — this is the second,
    defensive layer inside `JobOrchestrator` itself, for a Job row that
    reaches `run_job()` some other way. Must raise WITHOUT ever calling
    MinerU (no 3600s hang, no wasted OCR compute).
    """
    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(b"fake epub bytes")
    job = await _create_parse_only_job(session, epub_path, file_type="epub")

    mineru_runner = _fake_mineru_runner_for_parse_only()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with pytest.raises(EpubNotSupportedError):
        await orchestrator.run_job(job.id, session)

    mineru_runner.health.assert_not_awaited()
    mineru_runner.parse_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_parse_only_timeout_scales_with_page_count(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S15-14: `mineru_task_timeout_seconds=3600` fixed for every file was
    measured to be wrong (89s/25p live run ~= 3.6s/page -> a 415-page book
    needs ~25 min, and a 418-page/277MB book sits right at the 3600s wall).
    `parse_only`'s timeout must be `max(600, total_pages * 6)`, not the
    fixed constant `_build_ocr_bridge()` uses for translate/pdf_scan.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 200)  # -> max(600, 200*6) == 1200
    job = await _create_parse_only_job(session, source_pdf, file_type="pdf_digital")

    calls: list[dict] = []
    mineru_runner = _fake_mineru_runner_for_parse_only(capture_calls=calls)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        mineru_runner=mineru_runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert calls[0]["task_timeout_seconds"] == pytest.approx(1200.0)

    await session.refresh(job)
    assert job.total_pages == 200


# --- Bug #9 (Architecture.md "Bug #9") -- needs_font_shrink gate ------------


@pytest.mark.asyncio
async def test_babeldoc_engine_skips_font_shrink_leaves_output_untouched(
    session: AsyncSession, tmp_path: Path
) -> None:
    """T9-1 (Architecture.md B9.6 / Bug #9): babeldoc self-fits (B9-05) --
    running `font_shrink_page()` on its output is pure risk with 0 benefit
    (B9-06: median excess measured at 0.00%) and provably deletes real
    glyphs (B9-07). `_needs_font_shrink` must gate the whole
    `with fitz.open(...)` block off for `BabeldocRunner`
    (`needs_font_shrink=False`), so `chunk.output_path` must come out
    byte-identical to what `BabeldocRunner.translate_pages()` produced, and
    zero `OverflowReport` rows must be written. Asserts the real file bytes
    and DB row count (Protocol 6 R6-02) -- deliberately NOT `assert_called()`
    per Architecture.md B9.6 T9-1.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    babeldoc_runner = _fake_babeldoc_runner()
    produced_hashes: dict[str, str] = {}
    original_side_effect = babeldoc_runner.translate_pages.side_effect

    async def _translate_pages_capture(*args, **kwargs):
        result = await original_side_effect(*args, **kwargs)
        produced_hashes[str(result.mono_path)] = hashlib.sha256(
            result.mono_path.read_bytes()
        ).hexdigest()
        return result

    babeldoc_runner.translate_pages.side_effect = _translate_pages_capture

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="babeldoc"),
        babeldoc_runner=babeldoc_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with patch(
        "src.core.job_orchestrator.font_shrink_page",
        new=AsyncMock(wraps=_real_font_shrink_page),
    ) as font_shrink_spy:
        result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert produced_hashes  # sanity: the capture wrapper actually ran

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = chunks_result.all()
    assert chunks
    for chunk in chunks:
        after_hash = hashlib.sha256(Path(chunk.output_path).read_bytes()).hexdigest()
        assert after_hash == produced_hashes[chunk.output_path]

    overflow_result = await session.exec(
        select(OverflowReport).where(OverflowReport.job_id == job.id)
    )
    assert overflow_result.all() == []
    # Belt-and-suspenders on top of the hash/DB-count proof above (which is
    # the assertion Architecture.md B9.6 T9-1 actually requires): the real
    # font_shrink_page implementation itself must never even be entered for
    # a babeldoc chunk.
    font_shrink_spy.assert_not_awaited()


@pytest.mark.asyncio
async def test_pdf2zh_engine_still_runs_font_shrink_regression(
    session: AsyncSession, tmp_path: Path
) -> None:
    """T9-2 (Architecture.md B9.6 / Bug #9, regression guard): the
    babeldoc-skip fix in `_process_chunk()` must NOT accidentally turn
    font_shrink off for `pdf2zh` too (`Pdf2zhRunner.needs_font_shrink=True`)
    -- pdf2zh draws the translation at the ORIGINAL English layout position
    (B9-04) and genuinely needs this step. `font_shrink_page` is patched
    with `wraps=` (spies on the call, still runs the real implementation --
    not a behavior-replacing mock), so `await_count` reflects real
    invocations against real chunk output pages, not just a boolean
    `assert_called()`. Expected count is derived from the real chunk count
    the run actually produced (`_fake_pdf2zh_runner()`'s mono output always
    re-embeds every source page, per its own docstring), not hardcoded.
    """
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with patch(
        "src.core.job_orchestrator.font_shrink_page",
        new=AsyncMock(wraps=_real_font_shrink_page),
    ) as font_shrink_spy:
        result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = chunks_result.all()
    assert chunks
    # 3 source pages -> each chunk's fake pdf2zh mono output re-embeds all 3.
    assert font_shrink_spy.await_count == len(chunks) * 3


@pytest.mark.asyncio
async def test_needs_font_shrink_property_isinstance_guard_catches_unset_mock(
    tmp_path: Path,
) -> None:
    """T9-3 (Architecture.md B9.6 / Bug #9): proves the `isinstance` guard in
    `_needs_font_shrink` is load-bearing, not defensive filler.
    `AsyncMock(spec=BabeldocRunner)` copies the ATTRIBUTE NAME
    `needs_font_shrink` from the spec class but NOT its class-attribute
    VALUE -- a plain child `Mock` is truthy by default. A test author who
    forgets `runner.needs_font_shrink = False` (exactly the mistake this
    guard exists to catch) must get a loud `TypeError`, not a silently-wrong
    `True` that reruns the destructive pdf2zh font_shrink branch against
    babeldoc output. (Manually verified during implementation: removing the
    `isinstance` check from `_needs_font_shrink` makes this test fail, as
    expected -- guard restored afterward.)
    """
    runner = AsyncMock(spec=BabeldocRunner)  # deliberately NOT setting needs_font_shrink

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="babeldoc"),
        babeldoc_runner=runner,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with pytest.raises(TypeError, match="needs_font_shrink"):
        _ = orchestrator._needs_font_shrink
