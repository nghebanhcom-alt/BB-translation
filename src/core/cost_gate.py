"""Pre-flight cost gate — Architecture.md 6.11.4 Lop 2.

Closes RC-3 of the $6.50 real-money incident (Architecture.md 6.11.3):
"KHONG CO hard cap o bat ky lop nao ... `estimated_cost` chi duoc ghi vao DB
va hien thi, khong co nhanh code nao so sanh no voi mot nguong va tu choi
chay." This module is that missing branch — call `estimate_translation_cost()`
then `check_cap()` BEFORE any `Job`/`Batch` row is created or
`JobOrchestrator`/`BatchOrchestrator` is triggered (`POST /api/jobs`,
`POST /api/batches`, `POST /api/jobs/{id}/retry`).

Reuses `JobOrchestrator`'s own text-extraction/segment-counting helpers
(`_extract_full_text`, `_count_text_segments`, `_count_pdf_pages`) rather
than re-implementing them, per Architecture.md 6.11.5's data-lineage
requirement that the pre-job estimate and the real render path stay backed
by the same measurements.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.chunking import (
    EPUB_INLINE_MARKUP_FACTOR,
    EPUB_JSON_ENVELOPE_CHARS_PER_UNIT,
    plan_epub_chunks,
)
from src.core.config import Settings
from src.core.cost_estimator import CostEstimate, estimate_job_cost_v2
from src.core.glossary_manager import GlossaryManager
from src.core.job_orchestrator import _count_pdf_pages, _count_text_segments, _extract_full_text
from src.core.language_detector import detect_source_lang
from src.core.prompt_builder import build_epub_batch_prompt, build_prompt_text, build_system_prompt
from src.services.epub_document import EpubDocument
from src.services.translation import TranslationProvider


@dataclass
class DetailedCostEstimate:
    estimate: CostEstimate
    #: Architecture.md 6.20.6 (US-22 buoc 2/3): NULL cho EPUB — dinh dang
    #: reflow khong co "trang", bia so gia se lap lai chinh loai loi da sinh
    #: ra Bug #5. `total_units` la dai luong tuong duong cho EPUB.
    total_pages: int | None
    segment_count: int
    prompt_overhead_chars: int
    total_units: int | None = None
    #: Architecture.md §6.26.4 (S7 — dich FR->VI): ket qua CHINH THUC cua
    #: `detect_source_lang()` cho job nay — "en" | "fr" | None. `create_job()`
    #: (jobs.py) ghi thang gia tri nay vao `Job.source_lang` KHONG doi thanh
    #: "en" o day: nhanh pdf_scan co `full_text` gan rong (chua OCR) nen
    #: detect tra None co chu dich, de `run_job()` Step 3 detect LAI tren
    #: cau noi searchable PDF sau OCR — ghi "en" som se khoa cung gia tri sai.
    source_lang: str | None = None


@dataclass
class CostGateResult:
    estimate: CostEstimate
    cap_usd: float
    exceeded: bool


async def estimate_translation_cost(
    file_path: Path,
    provider: TranslationProvider,
    db_session: AsyncSession,
    batch_id: str | None,
    max_glossary_entries: int,
    file_type: str = "pdf_digital",
    settings: Settings | None = None,
) -> DetailedCostEstimate:
    """`estimate_job_cost_v2()` fed with real measurements from `file_path`
    (Architecture.md 6.11.5 data lineage steps 1-4 for PDF; 6.20.6 for EPUB).

    `file_type` re nhanh o DUNG 1 CHO (Architecture.md 6.20.6: "Ren nhanh
    theo file_type o dung 1 cho — ham nay — roi goi CUNG MOT
    estimate_job_cost_v2()") — KHONG viet cong thuc chi phi thu hai. Default
    "pdf_digital" giu nguyen hanh vi cu cho moi call site chua duoc cap nhat
    truyen file_type rieng.

    `settings` (Architecture.md §6.20.14.2 A-4, MOI — Protocol 6 R6-01 data
    lineage): CHI duoc doc boi nhanh EPUB (`_estimate_epub_translation_cost()`)
    de `plan_epub_chunks()` dung DUNG cung tham so ma
    `job_orchestrator.run_epub_job()` dung khi chay that — truoc fix nay,
    ham nay goi `plan_epub_chunks(doc.units)` VOI THAM SO MAC DINH trong khi
    orchestrator goi voi gia tri tu `Settings`, khien 2 ben lech nhau sau khi
    doi `EPUB_REQUEST_CHAR_BUDGET`/them `EPUB_REQUEST_MAX_UNITS` (§6.20.14.2
    A-1) — `llm_request_count` (chinh la `segment_count` cua
    `estimate_job_cost_v2()`) se bi UOC THAP, vi pham §6.11.6 ("duoc uoc cao,
    CAM uoc thap"). `None` chi hop le cho nhanh PDF (khong dung); nhanh EPUB
    BAT BUOC truyen `settings` that (call site: `jobs.py` da co san).

    NOTE — known gap (mirrors the accepted, documented gap in Architecture.md
    6.11.7 #3): for a `pdf_scan` file, `file_path` has no text layer yet (OCR
    hasn't run — it only happens inside `JobOrchestrator.run_job()`), so
    `_extract_full_text()` returns near-empty text here and this estimate
    under-represents the real cost of a scan job. Lop 3's running accumulator
    (checked after every real chunk, regardless of file_type) is what
    actually protects scan jobs; this pre-flight estimate protects born-digital
    jobs at full strength, and scan jobs only after the first chunk.
    """
    if file_type == "epub":
        if settings is None:
            raise ValueError(
                "estimate_translation_cost(file_type='epub') can 'settings' that "
                "(Architecture.md §6.20.14.2 A-4) de dong bo tham so plan_epub_chunks() "
                "voi job_orchestrator.run_epub_job() — khong duoc dung mac dinh module."
            )
        return await _estimate_epub_translation_cost(
            file_path, provider, db_session, batch_id, max_glossary_entries, settings
        )

    full_text = _extract_full_text(file_path)
    # Architecture.md §6.26.4 point 1: detect 1 LAN o day. `file_path` cua
    # 1 job pdf_scan CHUA co text layer (OCR chua chay — chi chay trong
    # `JobOrchestrator.run_job()`) nen `full_text` gan rong -> `token_count`
    # < 500 -> `detection.lang is None` co chu dich (KHONG ep "en" o day —
    # xem docstring `DetailedCostEstimate.source_lang`).
    detection = detect_source_lang(full_text)
    source_lang = detection.lang or "en"
    glossary_manager = GlossaryManager(db_session)
    prompt_text = await build_prompt_text(
        glossary_manager,
        project_id=batch_id,
        only_terms_present_in=full_text,
        max_glossary_entries=max_glossary_entries,
    )
    prompt_overhead_chars = max(len(prompt_text) - len("${text}"), 0)

    total_pages = _count_pdf_pages(file_path)
    segment_count = _count_text_segments(file_path, 1, total_pages)

    estimate = estimate_job_cost_v2(
        source_text_chars=len(full_text),
        segment_count=segment_count,
        prompt_overhead_chars=prompt_overhead_chars,
        provider=provider,
        source_lang=source_lang,
    )
    return DetailedCostEstimate(
        estimate=estimate,
        total_pages=total_pages,
        segment_count=segment_count,
        prompt_overhead_chars=prompt_overhead_chars,
        total_units=None,
        source_lang=detection.lang,
    )


async def _estimate_epub_translation_cost(
    file_path: Path,
    provider: TranslationProvider,
    db_session: AsyncSession,
    batch_id: str | None,
    max_glossary_entries: int,
    settings: Settings,
) -> DetailedCostEstimate:
    """Architecture.md 6.20.6 nhanh EPUB — goi CUNG `estimate_job_cost_v2()`
    voi 2 dau vao khac PDF:
    - `source_text_chars`: `doc.total_chars` UOC THAP 29,0% neu dung thang
      (X5) — nhan `EPUB_INLINE_MARKUP_FACTOR` + cong envelope JSON/unit.
    - `segment_count`: SO REQUEST LLM (`sum(len(c.requests) for c in plan)`),
      KHONG PHAI so unit — lech 8,8x da do duoc neu dung nham (6.20.6).

    `prompt_overhead_chars` (fix C-2, Architecture.md 6.20.13.6, Protocol 6
    data lineage): TRUOC fix nay ham do bang `build_prompt_text()` — prompt
    cua NHANH PDF (co placeholder `${text}`, footer rieng cua pdf2zh),
    KHONG PHAI chuoi thuc su gui cho LLM o nhanh EPUB. Prompt THAT ma
    `_process_epub_chunk()` gui (`job_orchestrator.py`) la
    `build_epub_batch_prompt(build_system_prompt(...))`. Sua: do dung
    CHINH artifact do — khong con tru `len("${text}")` vi chuoi EPUB
    KHONG co placeholder nay.

    `plan_epub_chunks(...)` (fix A-4, Architecture.md §6.20.14.2, Protocol 6
    R6-01): PHAI goi VOI DUNG cac tham so tu `settings` — GIONG HET cach
    `job_orchestrator.run_epub_job()` goi — thay vi tham so MAC DINH module.
    Truoc fix nay 2 noi goi TINH CO khop nhau; sau khi doi
    `EPUB_REQUEST_CHAR_BUDGET`/them `EPUB_REQUEST_MAX_UNITS` (A-1), va voi
    bat ky override `.env` nao, chung se LECH — ma `llm_request_count` chinh
    la `segment_count` cua `estimate_job_cost_v2()`, lech so request se uoc
    THAP chi phi, vi pham §6.11.6.
    """
    doc = EpubDocument.load(file_path)
    full_text = doc.full_text()

    # Architecture.md §6.26.4 point 1 — cung 1 lan detect nhu nhanh PDF o tren.
    detection = detect_source_lang(full_text)
    source_lang = detection.lang or "en"

    glossary_manager = GlossaryManager(db_session)
    base_system_prompt = await build_system_prompt(
        glossary_manager,
        project_id=batch_id,
        only_terms_present_in=full_text,
        max_glossary_entries=max_glossary_entries,
        source_lang=source_lang,
    )
    real_prompt = build_epub_batch_prompt(base_system_prompt)
    prompt_overhead_chars = len(real_prompt)

    plan = plan_epub_chunks(
        doc.units,
        char_budget=settings.epub_chunk_char_budget,
        request_budget=settings.epub_request_char_budget,
        request_max_units=settings.epub_request_max_units,
    )
    llm_request_count = sum(len(c.requests) for c in plan)
    source_text_chars = (
        int(doc.total_chars * EPUB_INLINE_MARKUP_FACTOR)
        + len(doc.units) * EPUB_JSON_ENVELOPE_CHARS_PER_UNIT
    )

    estimate = estimate_job_cost_v2(
        source_text_chars=source_text_chars,
        segment_count=llm_request_count,
        prompt_overhead_chars=prompt_overhead_chars,
        provider=provider,
        source_lang=source_lang,
    )
    return DetailedCostEstimate(
        estimate=estimate,
        total_pages=None,
        segment_count=llm_request_count,
        prompt_overhead_chars=prompt_overhead_chars,
        total_units=len(doc.units),
        source_lang=detection.lang,
    )


def check_cap(estimate: CostEstimate, cap_usd: float, settings: Settings) -> CostGateResult:
    """`cost_cap_enabled=False` is an explicit, visible opt-out (Architecture.md
    6.11.4 Lop 2 table: "Tat duoc, nhung phai tat tuong minh") — never a silent
    default.
    """
    exceeded = settings.cost_cap_enabled and estimate.estimated_cost_usd > cap_usd
    return CostGateResult(estimate=estimate, cap_usd=cap_usd, exceeded=exceeded)


def gate_error_detail(result: CostGateResult, scope: str) -> dict:
    """Body shape mandated by Architecture.md 6.11.4 Lop 2: `{"detail": ...,
    "estimated_cost_usd": X, "cap_usd": Y, "requires_confirmation": true}` —
    passed as the `detail=` of an `HTTPException(status_code=402, ...)`.
    """
    return {
        "detail": (
            f"Chi phi uoc tinh ${result.estimate.estimated_cost_usd:.2f} vuot tran "
            f"${result.cap_usd:.2f} cho {scope}. Dat confirm_cost=true de dich du sao "
            "(opt-in tuong minh cho lan nay), hoac tang tran trong Settings."
        ),
        "estimated_cost_usd": result.estimate.estimated_cost_usd,
        "cap_usd": result.cap_usd,
        "requires_confirmation": True,
    }
