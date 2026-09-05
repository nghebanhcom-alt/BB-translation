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

from src.core.config import Settings
from src.core.cost_estimator import CostEstimate, estimate_job_cost_v2
from src.core.glossary_manager import GlossaryManager
from src.core.job_orchestrator import _count_pdf_pages, _count_text_segments, _extract_full_text
from src.core.prompt_builder import build_prompt_text
from src.services.translation import TranslationProvider


@dataclass
class DetailedCostEstimate:
    estimate: CostEstimate
    total_pages: int
    segment_count: int
    prompt_overhead_chars: int


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
) -> DetailedCostEstimate:
    """`estimate_job_cost_v2()` fed with real measurements from `file_path`
    (Architecture.md 6.11.5 data lineage steps 1-4).

    NOTE — known gap (mirrors the accepted, documented gap in Architecture.md
    6.11.7 #3): for a `pdf_scan` file, `file_path` has no text layer yet (OCR
    hasn't run — it only happens inside `JobOrchestrator.run_job()`), so
    `_extract_full_text()` returns near-empty text here and this estimate
    under-represents the real cost of a scan job. Lop 3's running accumulator
    (checked after every real chunk, regardless of file_type) is what
    actually protects scan jobs; this pre-flight estimate protects born-digital
    jobs at full strength, and scan jobs only after the first chunk.
    """
    full_text = _extract_full_text(file_path)
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
    )
    return DetailedCostEstimate(
        estimate=estimate,
        total_pages=total_pages,
        segment_count=segment_count,
        prompt_overhead_chars=prompt_overhead_chars,
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
