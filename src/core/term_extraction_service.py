"""US-20 "Các từ mới" — DB/orchestration glue around `term_extractor.py`'s
pure algorithm: data lineage (Architecture.md §6.18.5, Protocol 6 R6-01) and
where/when it runs (§6.18.6, BR-TERM-01).

Kept as a SEPARATE module from `term_extractor.py` on purpose: the algorithm
module has no DB/Job/file-system dependency and can be unit-tested with
plain strings; this module owns everything that touches `Job`/`AsyncSession`
so a lineage mistake (Bug #5's shape: reading the wrong file for a given
`file_type`) is isolated to one small, easy-to-review place.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings, get_settings
from src.core.file_router import FileType
from src.core.glossary_matching import glossary_match_forms
from src.core.job_orchestrator import _extract_full_text
from src.core.term_extractor import extract_terms
from src.models.glossary import Glossary, GlossaryEntry
from src.models.job import Job
from src.models.suggested_term import SuggestedTerm

logger = logging.getLogger(__name__)


class TermExtractionSourceError(RuntimeError):
    """Raised when a job's `source_text` cannot be located — a lineage
    problem (Architecture.md §6.18.5), not an algorithm bug. Callers must
    NOT let this change `job.status` (BR-TERM-01) — see `extract_and_store_terms()`.
    """


async def _extract_source_text_for_terms(job: Job) -> str:
    """Architecture.md §6.18.5 lineage table — the ONLY place US-20 decides
    which file holds this job's English source text. Mirrors the same
    per-`file_type` branching `JobOrchestrator.run_job()`/`run_parse_only()`
    already use, so a future change to where those write their output must
    be mirrored here too (see the table in Architecture.md for the "tuyệt
    đối KHÔNG đọc" column this function is built to avoid).
    """
    if job.job_type == "parse_only":
        if job.output_path is None:
            raise TermExtractionSourceError(
                f"Job {job.id}: job_type=parse_only nhung output_path la None"
            )
        # S15-4: job.output_path tro toi parse_result.zip, KHONG phai .md —
        # file .md that nam CUNG THU MUC voi zip do (xem
        # JobOrchestrator.run_parse_only()).
        md_path = Path(job.output_path).parent / "document.md"
        if not md_path.exists():
            raise TermExtractionSourceError(
                f"Job {job.id}: khong tim thay {md_path} (nguon parse_only)"
            )
        return md_path.read_text(encoding="utf-8")

    if job.file_type == FileType.PDF_SCAN:
        if not job.ocr_bridge_path or not Path(job.ocr_bridge_path).exists():
            raise TermExtractionSourceError(
                f"Job {job.id}: pdf_scan nhung ocr_bridge_path khong ton tai "
                f"({job.ocr_bridge_path!r}) — day chinh la dang bug Bug #5 "
                "(doc nham file_path goc, khong co text layer)."
            )
        return _extract_full_text(Path(job.ocr_bridge_path))

    if job.file_type == FileType.PDF_DIGITAL:
        return _extract_full_text(Path(job.file_path))

    if job.file_type == FileType.EPUB:
        # US-22 chua implement (job_orchestrator.py rejects EPUB truoc khi
        # toi status=completed) nen nhanh nay KHONG THE bi goi qua duong di
        # binh thuong hien tai. Giu ro rang thay vi doc nham file — khi
        # US-22 len production (EpubDocument.load(...).full_text()), sua
        # DUNG cho nhanh nay, KHONG doan.
        raise TermExtractionSourceError(
            f"Job {job.id}: file_type=epub chua co nguon source_text cho US-20 "
            "(cho US-22 hoan thien EpubDocument.full_text(), Architecture.md 6.18.5)"
        )

    raise TermExtractionSourceError(f"Job {job.id}: file_type khong xac dinh: {job.file_type!r}")


def _project_scope(project_id: str) -> str:
    return f"project:{project_id}"


async def _collect_existing_glossary_forms(
    session: AsyncSession, project_id: str | None
) -> set[str]:
    """BR-GLOSS-06: global + project scope. Deliberately NOT calling into
    `GlossaryManager` here — that module is being edited in a separate,
    parallel session/task for an unrelated bug fix
    (`_count_occurrences()`); this queries `GlossaryEntry` directly instead
    of adding a new method to a file this increment was told not to touch.
    """
    scopes = ["global"]
    if project_id:
        scopes.append(_project_scope(project_id))

    statement = (
        select(GlossaryEntry.term_en)
        .join(Glossary, Glossary.id == GlossaryEntry.glossary_id)
        .where(Glossary.scope.in_(scopes))
    )
    result = await session.exec(statement)
    term_ens = result.all()

    forms: set[str] = set()
    for term_en in term_ens:
        forms |= glossary_match_forms(term_en)
    return forms


async def extract_and_store_terms(
    job_id: str, session: AsyncSession, settings: Settings | None = None
) -> int:
    """Architecture.md §6.18.6 — run AFTER `JobOrchestrator.run_job()`
    returns `status == "completed"`, in its own `try/except` so a failure
    here can NEVER change `job.status` (BR-TERM-01). Also reachable directly
    from `POST /api/jobs/{id}/extract-terms` for a manual re-run.

    Idempotent re-run semantics: rows the user already acted on (`status !=
    "pending"`) are left untouched (a re-run must not un-dismiss or
    un-promote a term); stale `pending` rows are replaced with a fresh
    extraction. Returns the number of `pending` rows written.
    """
    settings = settings or get_settings()

    job = await session.get(Job, job_id)
    if job is None:
        raise TermExtractionSourceError(f"Job {job_id} khong ton tai")
    if job.status != "completed":
        raise TermExtractionSourceError(
            f"Job {job_id}: status={job.status!r}, chi trich xuat cho job da completed (BR-TERM-01)"
        )
    if not settings.term_extraction_enabled:
        logger.info("term_extraction_enabled=False — bo qua job %s", job_id)
        return 0

    # Architecture.md §6.26.5 audit buoc #13 (S7 — dich FR->VI), R8-02
    # deny-by-default: `_load_function_words()` (term_extractor.py) chi nap
    # `en_function_words.txt` — hu tu tieng Phap (le/la/des/pour/avec...)
    # khong bi loc, khien ung vien n-gram thanh rac. Chua verify cach hieu
    # chinh cho FR (backlog) -> SKIP, khong chay ra ket qua rac. Guard o
    # DAY (khong phai rieng o jobs.py:537) de ca duong tu dong
    # (_run_job_background) LAN duong thu cong (POST .../extract-terms) deu
    # duoc bao ve nhu nhau — 2 call site, 1 nguon su that.
    if (job.source_lang or "en") != "en":
        logger.info(
            "Job %s: source_lang=%r != 'en' — bo qua trich xuat tu moi (US-20, §6.26.5 buoc #13)",
            job_id,
            job.source_lang,
        )
        return 0

    source_text = await _extract_source_text_for_terms(job)
    existing_forms = await _collect_existing_glossary_forms(session, job.batch_id)
    candidates = extract_terms(source_text, existing_forms, settings)

    decided_result = await session.exec(
        select(SuggestedTerm.term_en).where(
            SuggestedTerm.job_id == job_id, SuggestedTerm.status != "pending"
        )
    )
    decided_terms = set(decided_result.all())

    pending_rows = (
        await session.exec(
            select(SuggestedTerm).where(
                SuggestedTerm.job_id == job_id, SuggestedTerm.status == "pending"
            )
        )
    ).all()
    for row in pending_rows:
        await session.delete(row)

    written = 0
    for candidate in candidates:
        if candidate.term_en in decided_terms:
            continue
        session.add(
            SuggestedTerm(
                job_id=job_id,
                term_en=candidate.term_en,
                match_key=candidate.match_key,
                ngram_size=candidate.ngram_size,
                noise_flags=candidate.noise_flags,
                occurrence_count=candidate.occurrence_count,
                rank_score=candidate.rank_score,
                status="pending",
            )
        )
        written += 1

    await session.commit()
    logger.info("Job %s: trich xuat %d tu goi y moi (pending)", job_id, written)
    return written
