"""Job/Batch orchestration — assembles every building block from Increments
1-4 into a runnable pipeline (Architecture.md sections 3.1/3.5, 6.1, 6.6,
US-06/07/08, BR-CHUNK-01..05, BR-BATCH-01..04).

**Increment 4 Fix Round 1** rewrote `run_job()` to close an architecture bug
found after Increment 3+4 were approved: pdf2zh calls the LLM itself
(Architecture.md 6.6.1 F1-F9), so the old flow — which called BOTH
`provider.translate()` (for accounting) AND `pdf2zh_runner.translate_pages()`
(for rendering) per chunk — paid for the same content twice and rendered a
translation that didn't match the one used for cost accounting. See
Architecture.md 6.6.2 (R1-R5) and docs/CHANGELOG.md "Increment 4 — Fix Round
1" for the full rationale. `TranslationProvider` is now strictly out-of-band
(6.6.2 R3): it is never called with `.translate()` from this module, only
`.estimate_cost()` for post-render cost accounting (6.6.6).
"""

import asyncio
import json
import logging
import math
import os
import shutil
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.chunking import EpubChunkPlan, plan_chunks, plan_epub_chunks
from src.core.concurrency_controller import (
    ADAPTIVE_THREAD_FLOOR,
    BABELDOC_THREAD_FLOOR,
    ChunkOutcome,
    classify_chunk_outcome,
    next_thread_count,
)
from src.core.config import Settings, get_settings
from src.core.cost_estimator import estimate_chunk_cost
from src.core.file_router import FileType
from src.core.glossary_manager import GlossaryManager
from src.core.ocr_warning import build_ocr_warning
from src.core.progress_tracker import BroadcastFn, ProgressTracker
from src.core.prompt_builder import (
    build_epub_batch_prompt,
    build_system_prompt,
    parse_epub_batch_response,
    write_babeldoc_prompt_file,
    write_prompt_file,
)
from src.models.batch import Batch
from src.models.chunk import Chunk
from src.models.concurrency_state import ConcurrencyState
from src.models.job import Job
from src.models.overflow import OverflowReport
from src.postprocess.bilingual_merge import create_bilingual_pdf
from src.postprocess.chunk_merge import merge_chunk_pdfs
from src.postprocess.font_shrink import OverflowEntry, font_shrink_page
from src.postprocess.image_compress import compress_pdf_images
from src.postprocess.rotated_text_overlay import overlay_rotated_text
from src.preprocess.searchable_pdf import build_searchable_pdf
from src.services.babeldoc_runner import BabeldocError, BabeldocRunner, BabeldocTimeoutError
from src.services.epub_document import EpubDocument, count_bb_vi_pairs
from src.services.layout_qa import persist_findings
from src.services.mineru_det_probe import probe_and_flag_rotated_text
from src.services.mineru_runner import (
    MinerUCancelledError,
    MinerUError,
    MinerUResult,
    MinerURunner,
    MinerUUnavailableError,
)
from src.services.pdf2zh_runner import Pdf2zhError, Pdf2zhRunner, Pdf2zhTimeoutError
from src.services.pdf2zh_service_map import (
    Pdf2zhService,
    Pdf2zhServiceMapper,
    UnsupportedForPdfPipelineError,
)
from src.services.provider_factory import ProviderFactory
from src.services.translation import TranslationProvider
from src.utils.retry import with_retry

logger = logging.getLogger(__name__)

#: Architecture.md 6.12.7 — `chunk_size` cold-start. Smaller radius while
#: `(provider, model)`'s AIMD state hasn't converged (cheapest mistake),
#: larger once it has (fewer chunks, less overhead). Decided ONCE per job
#: (`Job.chunk_size_used`), never recomputed mid-job — see 6.12.7's
#: "Rang buoc bat buoc" for why (same lineage-break shape as Bug #5).
COLD_START_CHUNK_SIZE = 20
WARM_CHUNK_SIZE = 40


class JobNotFoundError(ValueError):
    pass


class BatchNotFoundError(ValueError):
    pass


class EpubNotSupportedError(NotImplementedError):
    """Raised when a job's pipeline path for EPUB isn't implemented yet.

    US-22 buoc 2/3 (Architecture.md 6.20.8) da implement pipeline dich THAT
    (`run_epub_job()`) — `run_job()` KHONG con raise loi nay cho nhanh
    translate nua. Van con dung DUY NHAT cho nhanh Markdown parse-only
    (`EpubDocument.to_markdown()`, US-15's §6.15.3 S15-8), van ngoai pham vi
    (buoc 3/3 hoac sau). The caller's message says which.
    """


class EpubBatchTranslationError(RuntimeError):
    """US-22 buoc 2/3 (Architecture.md 6.20.8/6.20.12 X4): sau 1 vong goi lai
    RIENG LE cho tung id thieu, van con it nhat 1 unit khong co ban dich.
    E-09's exact shape (bilingual_book_maker/Bug #5): TUYET DOI khong duoc
    ghi chuoi rong cho unit thieu — chunk phai that bai ro rang thay vi vay.
    """


class EpubEmptyOutputError(RuntimeError):
    """BR-EPUB-05 (Architecture.md 6.20.8 + X3 guard sua sau phan bien Domain
    Expert): file EPUB output vua ghi khong qua duoc it nhat 1 trong cac dieu
    kien guard (tong ky tu > 0, so unit khop, noi dung thuc su khac ban goc
    — tuy `bilingual`). Day la ban EPUB cua BR-OCR-03/Pdf2zhEmptyOutputError
    — Bug #5's exact symptom ("completed" + noi dung khong dung), ap dung cho
    dinh dang EPUB.
    """


class ParseOnlyEmptyOutputError(RuntimeError):
    """US-15 §6.15.3 S15-5 — BR-OCR-03's sibling guard for the parse-only
    pipeline: MinerU returned a Markdown file with zero readable characters
    (after `.strip()`) — the job must fail loudly instead of reporting
    "completed" over nothing (Bug #5's exact shape, applied here).
    """


class ParseOnlyZipGuardError(RuntimeError):
    """US-15 §6.15.4 lineage step 5 (added after Domain Expert review of
    S15-3): the eagerly-built ZIP artifact must be re-opened and checked
    against what was actually written to disk before the job is allowed to
    report "completed" — never trust the in-memory belief that the write
    succeeded.
    """


class Pdf2zhEmptyOutputError(RuntimeError):
    """BR-OCR-03 (Architecture.md 6.10.5): the merged translation has zero
    readable characters. Bug #5's exact symptom — a job that reports
    "completed" with an empty `translated_vi.pdf` — so this must fail the
    job instead of letting it through, for ANY `file_type`, not just
    `pdf_scan` (the bridge's own BR-OCR-02 guard already covers the scan
    case earlier in the pipeline; this is the last-resort net for every
    other silent-empty-output mode, e.g. pdf2zh itself changing behavior).
    """


@dataclass
class JobResult:
    job_id: str
    status: str
    output_path: str | None
    bilingual_path: str | None
    actual_cost: float | None
    error_message: str | None = None


@dataclass
class BatchResult:
    batch_id: str
    completed: int
    failed: int
    total: int
    job_results: list[JobResult] = field(default_factory=list)


def _count_pdf_pages(file_path: Path) -> int:
    with fitz.open(file_path) as doc:
        return doc.page_count


def _extract_full_text(file_path: Path) -> str:
    """Whole-document EN text (PyMuPDF), used to filter the glossary down to
    terms that actually occur in this document (Architecture.md 6.6.5) before
    the prompt file is written.
    """
    with fitz.open(file_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def _extract_chunk_text(file_path: Path, chunk: Chunk) -> str:
    """Pull the raw EN text for a chunk's page range — the `source_text` input
    to `estimate_chunk_cost()` (Architecture.md 6.6.6), not a real translation
    call (pdf2zh does that internally; see module docstring).
    """
    with fitz.open(file_path) as doc:
        page_texts = [
            doc[page_num].get_text()
            for page_num in range(chunk.page_start - 1, min(chunk.page_end, doc.page_count))
        ]
    return "\n".join(page_texts)


def _count_text_segments(file_path: Path, page_start: int, page_end: int) -> int:
    """Approximate how many segments pdf2zh's layout analysis will split a
    chunk's page range into, for `estimate_chunk_cost()`'s `segment_count`
    (Architecture.md 6.6.6: the prompt file is re-sent once per segment, F6).

    pdf2zh's actual segment boundaries only exist inside its own layout
    analysis and aren't observable from outside the subprocess. This counts
    non-empty PyMuPDF text blocks per page as a stand-in — an approximation,
    documented here and in CHANGELOG rather than left silent, since
    Architecture.md 6.6.6 specifies the formula but not how `segment_count`
    itself is measured.
    """
    count = 0
    with fitz.open(file_path) as doc:
        for page_num in range(page_start - 1, min(page_end, doc.page_count)):
            blocks = doc[page_num].get_text("blocks")
            count += sum(1 for block in blocks if block[4].strip())
    return max(count, 1)


def _check_epub_output_guard(
    source_doc: EpubDocument, merged_path: Path, *, bilingual: bool
) -> None:
    """BR-EPUB-05 (Architecture.md 6.20.8, sua tai X3 sau phan bien Domain
    Expert 2026-09-08) — ban EPUB cua BR-OCR-03/`Pdf2zhEmptyOutputError`.

    Doc LAI CHINH `merged_path` vua ghi (khong tin `translations` con trong
    bo nho — R6-02) qua 1 lan `EpubDocument.load()` MOI (rieng biet voi
    `source_doc`, vi `load()` cua chinh no da tu bo qua node `class="bb-vi"`
    — day la ly do X3 chon `bilingual=True` KHONG lam guard nay vo hieu: so
    unit doc lai van khop so unit goc).

    4 dieu kien theo dung bang X3 (Architecture.md 6.20.12):
    - `bilingual=False`: tong ky tu > 0, so unit khop, >=90% unit khac ban goc.
    - `bilingual=True`: tong ky tu > 0, so unit khop (nho `load()` bo qua
      bb-vi), so node `bb-vi` >= 90% so unit goc, VA >=90% cap (goc, bb-vi
      lien sau) co noi dung khac nhau — dieu kien CUOI la thu KHONG THE BO:
      thieu no, 1 job LLM tra nguyen van tieng Anh cho moi unit van qua
      guard (du so node/du ky tu) — dung shape "completed, noi dung sai"
      cua Bug #5, chi doi tu "rong" sang "chua dich".
    """
    guard_doc = EpubDocument.load(merged_path)

    if guard_doc.total_chars <= 0:
        raise EpubEmptyOutputError(
            f"File dich '{merged_path.name}' khong con ky tu nao doc duoc — "
            "job that bai thay vi tra ve file rong (BR-EPUB-05)."
        )

    if len(guard_doc.units) != len(source_doc.units):
        raise EpubEmptyOutputError(
            f"File dich '{merged_path.name}' co {len(guard_doc.units)} unit, khac "
            f"{len(source_doc.units)} unit cua file goc — co the da mat noi dung "
            "khi ghi (BR-EPUB-05)."
        )

    # Issue #3 (US-22 Buoc 2/3, vong 1/3 review): `int()` LUON truncate ve
    # phia 0, khong phai lam tron dung nghia "toi thieu 90%" -- vd N=384:
    # `int(384*0.9)=345` cho phep guard pass khi chi 345/384=89.84% (< 90%
    # yeu cau thuc). `math.ceil()` moi dam bao nguong LUON >= 90% that su.
    min_required = max(1, math.ceil(len(source_doc.units) * 0.9))

    if not bilingual:
        differing = sum(
            1
            for orig, new in zip(source_doc.units, guard_doc.units, strict=True)
            if orig.text.strip() != new.text.strip()
        )
        if differing < min_required:
            raise EpubEmptyOutputError(
                f"Chi {differing}/{len(source_doc.units)} unit khac noi dung ban goc — "
                "duoi 90% yeu cau, co the LLM da tra ve nguyen van tieng Anh (BR-EPUB-05)."
            )
        return

    bb_vi_count, differing_pairs = count_bb_vi_pairs(merged_path)
    if bb_vi_count < min_required:
        raise EpubEmptyOutputError(
            f"File dich chi co {bb_vi_count}/{len(source_doc.units)} node ban dich "
            '(lang="vi" + class="bb-vi") — duoi 90% yeu cau, co the da mat noi dung '
            "khi ghi (BR-EPUB-05)."
        )
    if differing_pairs < min_required:
        raise EpubEmptyOutputError(
            f"Chi {differing_pairs}/{bb_vi_count} cap (ban goc, ban dich) khac noi dung "
            "nhau — duoi 90% yeu cau, co the LLM da tra ve nguyen van tieng Anh "
            "(BR-EPUB-05)."
        )


class JobOrchestrator:
    """Runs one translation job end to end: chunk -> render (pdf2zh, which
    calls the LLM itself) -> post-process -> merge -> (optional) bilingual
    output -> estimate cost.

    Every external dependency (pdf2zh, MinerU, the pricing `TranslationProvider`)
    is injected so tests can run the full flow against mocks without
    Docker/API keys.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        pdf2zh_runner: Pdf2zhRunner | None = None,
        babeldoc_runner: BabeldocRunner | None = None,
        service_mapper: Pdf2zhServiceMapper | None = None,
        mineru_runner: MinerURunner | None = None,
        provider: TranslationProvider | None = None,
        provider_factory: type[ProviderFactory] = ProviderFactory,
        chunk_size: int = 40,
        overlap: int = 2,
        output_dir: Path | None = None,
        processing_dir: Path | None = None,
        progress_broadcaster: BroadcastFn | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._pdf2zh_runner = pdf2zh_runner or Pdf2zhRunner()
        self._service_mapper = service_mapper or Pdf2zhServiceMapper()
        self._mineru_runner = mineru_runner
        # Architecture.md 6.14.7: `babeldoc_runner` injectable rieng cho test
        # giong `pdf2zh_runner`, lazily xay dung neu khong duoc truyen vao va
        # engine dang la "babeldoc" (khong spawn/kiem tra executable babeldoc
        # khi khong can den no) — xem property `_translator_runner` duoi day.
        self._babeldoc_runner = babeldoc_runner
        #: Out-of-band pricing provider (Architecture.md 6.6.2 R3) — used ONLY
        #: for `.estimate_cost()` in `_process_chunk()`, never `.translate()`.
        self._provider = provider
        self._provider_factory = provider_factory
        #: Fallback ONLY for tests that call internal helpers (e.g.
        #: `plan_chunks()`) directly without going through `run_job()`. Real
        #: jobs get `Job.chunk_size_used` from cold/warm ConcurrencyState
        #: instead (Architecture.md 6.12.7) — this is no longer the source of
        #: truth for `run_job()`.
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._output_dir = output_dir or Path("data/outputs")
        self._processing_dir = processing_dir or Path("data/processing")
        #: Architecture.md 6.3 — same font file pinned via `NOTO_FONT_PATH`
        #: for pdf2zh itself (`Pdf2zhServiceMapper`). `None` (falls back to
        #: "helv" inside `font_shrink_page`) only when the file genuinely
        #: isn't provisioned yet, e.g. a fresh checkout before `fonts/` is
        #: populated — never silently swallowed once it exists.
        noto_path = Path(self._settings.noto_font_path)
        self._noto_font_path = str(noto_path.resolve()) if noto_path.exists() else None
        #: Increment 5: pushed into `ProgressTracker` so DB writes also fan
        #: out over WebSocket (src/api/websocket.py). `None` in every test
        #: from Increment 4 — the flow is unchanged without it.
        self._progress_broadcaster = progress_broadcaster

    @property
    def _translator_runner(self) -> Pdf2zhRunner | BabeldocRunner:
        """Architecture.md 6.14.7 — DIEM CHON ENGINE DUY NHAT. `_process_chunk()`
        goi `self._translator_runner.translate_pages(...)` mot cach duy nhat
        cho ca 2 engine, khong rai `if engine == ...` trong than ham (moi
        nhanh re la 1 co hoi de lech nhau, dung kieu Bug #5). Resolved LAZILY
        (property, khong cache trong `__init__`) de test co the doi
        `orchestrator._pdf2zh_runner` sau khi khoi tao (pattern resumable-job
        da co tu Increment 4) ma van duoc `run_job()` lan sau nhin thay.
        """
        if self._settings.pdf_translate_engine == "babeldoc":
            return self._babeldoc_runner or BabeldocRunner(
                executable=self._settings.babeldoc_executable,
                deepseek_base_url=self._settings.deepseek_base_url,
                line_split_shim_enabled=self._settings.babeldoc_line_split_shim_enabled,
                numbered_list_split_enabled=self._settings.babeldoc_numbered_list_split_enabled,
                toc_split_enabled=self._settings.babeldoc_toc_split_enabled,
                word_wrap_fix_enabled=self._settings.babeldoc_word_wrap_fix_enabled,
            )
        return self._pdf2zh_runner

    @property
    def _needs_font_shrink(self) -> bool:
        """Bug #9 — hoi NANG LUC cua engine da chon, khong hoi TEN engine.
        Cung ky luat 6.14.7: chi `_translator_runner` biet engine nao dang
        chay; than `_process_chunk()` chi doc 1 boolean.

        `isinstance` guard la CO CHU DICH, khong phai phong thu thua:
        production luon tra ve `bool` that (ClassVar tren ca 2 runner), nen
        nhanh raise chi voi toi duoc tu test dung `AsyncMock(spec=...Runner)`
        — mock KHONG copy GIA TRI cua class attribute, chi copy TEN, nen
        `mock.needs_font_shrink` la 1 child Mock TRUTHY. Khong co guard nay,
        mot test babeldoc quen set thuoc tinh se am tham chay nhanh pdf2zh va
        van PASS — dung loai "mock tu nhat quan voi chinh no" ma Protocol 5/6
        sinh ra de chan.
        """
        value = self._translator_runner.needs_font_shrink
        if not isinstance(value, bool):
            raise TypeError(
                f"{type(self._translator_runner).__name__}.needs_font_shrink phai la bool, "
                f"nhan duoc {value!r}. Neu day la test dung AsyncMock(spec=...), phai set "
                "tuong minh `runner.needs_font_shrink = True/False` cho dung nhanh dang test "
                "(Architecture.md Bug #9 B9.4)."
            )
        return value

    async def run_job(self, job_id: str, db_session: AsyncSession) -> JobResult:
        job = await db_session.get(Job, job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} khong ton tai")

        # US-15 S15-1 (Architecture.md 6.15.3): re theo job_type TRUOC, roi
        # moi re theo file_type. Thu tu goc ("Step 1" duoi day tung reject
        # EPUB truoc MOI nhanh khac) khien 1 job parse_only tren file EPUB
        # chet oan du nhanh parse chang lien quan gi toi bilingual_book_maker
        # — day la ly do S15 goc bi phat hien la sai kien truc. `run_parse_only()`
        # la HAM RIENG, khong nhoi `if job_type == ...` rai rac vao 10 Step
        # duoi day (cung ly ly do 6.14.7 chon engine 1 lan duy nhat: moi cho
        # re nhanh la 1 co hoi de 2 luong lech nhau, dung kieu Bug #5).
        if job.job_type == "parse_only":
            return await self.run_parse_only(job, db_session)

        # Step 1 (US-22 buoc 2/3, Architecture.md 6.20.8): EPUB co pipeline
        # RIENG (khong dung bilingual_book_maker o bat ky dau — BR-EPUB-03),
        # tach het khoi Step 2..10 duoi day (chi danh cho PDF) giong het cach
        # `run_parse_only()` da tach o tren — moi cho re nhanh la 1 co hoi de
        # 2 luong lech nhau (6.14.7).
        if job.file_type == FileType.EPUB:
            return await self.run_epub_job(job, db_session)

        file_path = Path(job.file_path)

        # Step 2: dem total_pages; pdf_scan -> OCR + cau noi searchable PDF
        # (Architecture.md 6.10.5). `translation_source_path` la BIEN DUY NHAT
        # moi buoc doc noi dung sau day phai dung — day la fix cho Bug #5
        # (silent failure: OCR chay dung nhung ket qua khong bao gio toi pdf2zh).
        if job.total_pages is None:
            job.total_pages = _count_pdf_pages(file_path)

        translation_source_path = file_path  # pdf_digital: khong doi

        if job.file_type == FileType.PDF_SCAN:
            translation_source_path = await self._build_ocr_bridge(job, file_path, db_session)

        # Step 3: extract text EN toan file -> dung de LOC glossary (6.6.5).
        # Dung translation_source_path (cau noi neu la pdf_scan), KHONG phai
        # file_path goc — file goc khong co text layer de doc.
        full_text = _extract_full_text(translation_source_path)

        # Step 4: map provider -> pdf2zh service. DeepL (va bat ky provider
        # khong ho tro) fail NGAY o day, truoc khi cham toi subprocess.
        try:
            service = self._service_mapper.map(job.model, self._settings)
        except UnsupportedForPdfPipelineError as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
            db_session.add(job)
            await db_session.commit()
            await self._broadcast_job_failed(job, completed_chunks=0, total_chunks=0)
            return JobResult(
                job_id=job.id,
                status="failed",
                output_path=job.output_path,
                bilingual_path=job.bilingual_path,
                actual_cost=job.actual_cost,
                error_message=job.error_message,
            )

        # Step 5: build + write prompt file (1 lan/job, tai su dung moi chunk).
        # RE NHANH BAT BUOC theo engine tu day: pdf2zh doc file nay qua
        # `string.Template` (${lang_in}/${lang_out}/${text}) MOI SEGMENT,
        # babeldoc nhan noi dung file lam 1 CHUOI TINH cho `--custom-system-
        # prompt`, khong co co che template nao (prompt_builder.py, xem
        # `write_babeldoc_prompt_file()`). Dung chung 1 file/1 builder cho
        # ca 2 engine tung nhoi contract cua pdf2zh (${text}, "chi in ban
        # dich khong giai thich") vao prompt cua babeldoc — mau thuan voi
        # JSON contract rieng cua babeldoc, xac nhan la nguyen nhan khien
        # babeldoc am tham bo sot doan van (root-cause investigation,
        # 2026-09-05).
        glossary_manager = GlossaryManager(db_session)
        prompt_path = self._processing_dir / job.id / "prompt.txt"
        if self._settings.pdf_translate_engine == "babeldoc":
            await write_babeldoc_prompt_file(
                glossary_manager,
                path=prompt_path,
                project_id=job.batch_id,
                only_terms_present_in=full_text,
                max_glossary_entries=self._settings.max_glossary_entries_in_prompt,
            )
            prompt_overhead_chars = len(prompt_path.read_text(encoding="utf-8"))
        else:
            await write_prompt_file(
                glossary_manager,
                path=prompt_path,
                project_id=job.batch_id,
                only_terms_present_in=full_text,
                max_glossary_entries=self._settings.max_glossary_entries_in_prompt,
            )
            prompt_overhead_chars = max(
                len(prompt_path.read_text(encoding="utf-8")) - len("${text}"), 0
            )

        # Out-of-band provider, dung DUY NHAT cho estimate_cost() o buoc 7c.
        pricing_provider = self._provider or self._provider_factory.create(
            job.model, self._settings
        )

        # Step 6: plan_chunks() -> load/create Chunk rows (BR-CHUNK-05 resumable).
        # chunk_size_used is decided ONCE per job and persisted (Architecture.md
        # 6.12.7): a first run picks cold/warm from ConcurrencyState; a resumed
        # job reuses its already-persisted value so page_start/page_end already
        # written for existing Chunk rows stay consistent with the plan below
        # (changing chunk_size mid-job is the exact lineage break Bug #5 was).
        if job.chunk_size_used is None:
            provider = job.model
            model_key = service.service_arg
            # Same two conditions, same order, as _resolve_thread()'s guard:
            # neither branch may touch ConcurrencyState (6.12.6/6.12.8), and
            # ollama would KeyError anyway since ADAPTIVE_THREAD_FLOOR has no
            # "ollama" key. They stay at 20 permanently by design — 6.12.7:
            # ollama_thread defaults to 2, so a 40-page chunk there is the
            # worst wall-clock case in the system, and the kill-switch branch
            # is the safe rollback path.
            if provider == "ollama" or not self._settings.adaptive_concurrency_enabled:
                job.chunk_size_used = COLD_START_CHUNK_SIZE
            else:
                state = await self._get_or_create_concurrency_state(
                    self._settings.pdf_translate_engine, provider, model_key, db_session
                )
                warm = state.observation_count >= 3 and state.consecutive_successes >= 3
                job.chunk_size_used = WARM_CHUNK_SIZE if warm else COLD_START_CHUNK_SIZE
            db_session.add(job)
            await db_session.commit()

        chunk_plan = plan_chunks(job.total_pages, job.file_size, job.chunk_size_used, self._overlap)
        chunks = await self._load_or_create_chunks(job, chunk_plan, db_session)

        job.status = "translating"
        job.started_at = job.started_at or datetime.now(UTC)
        db_session.add(job)
        await db_session.commit()

        progress_tracker = ProgressTracker(broadcaster=self._progress_broadcaster)
        total_chunks = len(chunks)

        # Step 7: voi moi chunk chua completed.
        for position, chunk in enumerate(chunks, start=1):
            if chunk.status != "completed":
                try:
                    await self._process_chunk(
                        job,
                        chunk,
                        translation_source_path,
                        service,
                        prompt_path,
                        prompt_overhead_chars,
                        pricing_provider,
                        db_session,
                    )
                except Exception as exc:  # noqa: BLE001 — any chunk failure fails the job
                    chunk.status = "failed"
                    chunk.error_message = str(exc)
                    chunk.retry_count += 1
                    db_session.add(chunk)

                    job.status = "failed"
                    job.error_message = f"Chunk {chunk.chunk_index} that bai: {exc}"
                    job.finished_at = datetime.now(
                        UTC
                    )  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
                    db_session.add(job)
                    await db_session.commit()

                    await self._broadcast_job_failed(job, position, total_chunks)

                    return JobResult(
                        job_id=job.id,
                        status="failed",
                        output_path=job.output_path,
                        bilingual_path=job.bilingual_path,
                        actual_cost=job.actual_cost,
                        error_message=job.error_message,
                    )

            await progress_tracker.update(job.id, position, total_chunks, db_session)

            # Financial Safety Lop 3 (Architecture.md 6.11.4): running cost
            # accumulator, checked at the SAME point as the cancel_requested
            # check below (verified live at QA Vong 5, reused rather than
            # adding a new stop point). Pre-flight (Lop 2) alone is not
            # enough — an under-estimate (like RC-2 was, 4.1x low) would
            # still let a job run away, exactly how the $6.50 incident
            # happened with no cap at any layer (RC-3).
            completed_cost = sum(c.api_cost or 0.0 for c in chunks[:position])
            effective_cap = (
                job.cost_cap_usd
                if job.cost_cap_usd is not None
                else self._settings.max_cost_per_job_usd
            )
            if self._settings.cost_cap_enabled and completed_cost > effective_cap:
                job.actual_cost = completed_cost
                job.cost_source = "estimated"
                job.status = "cost_capped"
                job.error_message = (
                    f"Job dung o chunk {chunk.chunk_index}: chi phi uoc tinh tich luy "
                    f"${completed_cost:.2f} da vuot tran ${effective_cap:.2f}. Cac chunk da "
                    "dich duoc giu nguyen — tang tran trong Settings roi bam Retry de chay tiep."
                )
                job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
                db_session.add(job)
                await db_session.commit()

                await self._broadcast_job_cost_capped(job, position, total_chunks)

                # KHONG raise loi — day la he thong CHU DONG bao ve tai chinh
                # user, khong phai loi (khac "failed") va khong phai user tu
                # dung (khac "cancelled"). Resumable giong het 2 trang thai
                # kia: chunk da "completed" duoc giu nguyen, retry_job() phai
                # di qua lai Lop 2 gate truoc khi chay tiep.
                return JobResult(
                    job_id=job.id,
                    status="cost_capped",
                    output_path=job.output_path,
                    bilingual_path=job.bilingual_path,
                    actual_cost=job.actual_cost,
                    error_message=job.error_message,
                )

            # Nhiem vu 3 (Increment 6): graceful cancel — kiem tra NGAY SAU KHI
            # chunk hien tai xong (dung `chunk.status == "completed"` da co san
            # tu resumable skip o tren, khong force-kill giua chunk). `job` co
            # the da bi 1 request/session KHAC (POST /.../cancel) dat co trong
            # luc chunk nay dang chay — phai refresh tu DB truoc khi doc, vi
            # session nay chi commit `job` khi CHINH no sua field.
            await db_session.refresh(job)
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
                db_session.add(job)
                await db_session.commit()

                await self._broadcast_job_cancelled(job, position, total_chunks)

                # KHONG raise loi — day la user chu dong dung, khong phai
                # that bai. Job van resumable sau nay (BR-CHUNK-05, giong het
                # "failed": retry_job() chap nhan ca 2 status, chi chay tiep
                # tu chunk chua completed).
                return JobResult(
                    job_id=job.id,
                    status="cancelled",
                    output_path=job.output_path,
                    bilingual_path=job.bilingual_path,
                    actual_cost=job.actual_cost,
                )

        # Step 8: merge chunks.
        job.status = "merging"
        db_session.add(job)
        await db_session.commit()

        merged_path = self._output_dir / job.id / "translated_vi.pdf"
        try:
            await merge_chunk_pdfs(chunks, merged_path)

            # BR-OCR-03: last-resort net against ANY silent-empty-output job
            # (not just pdf_scan — this is exactly the symptom Bug #5 had:
            # status="completed" with a 0-character translated_vi.pdf).
            with fitz.open(merged_path) as merged_doc:
                if sum(len(page.get_text().strip()) for page in merged_doc) == 0:
                    raise Pdf2zhEmptyOutputError(
                        f"Ban dich khong chua chu nao ({merged_path.name}) — engine dich "
                        f"'{self._settings.pdf_translate_engine}' khong tim thay text de dich. "
                        "Job that bai thay vi tra ve file trong."
                    )

            # U3/U4 P1.1 (G1e) + U6/RK-3: babeldoc silently drops rotated text
            # (V-1, verified — backend has no rotation field). This overlay
            # re-draws it back using the app's OWN LLM provider (pricing_provider,
            # NEVER babeldoc/pdf2zh — R6-01 data lineage), reading
            # `translation_source_path` (SAME variable Step 7 uses to feed the
            # engine — Bug #5's exact mistake was reading `file_path`, the
            # scan with no text layer, instead of this bridge; R6-04 review
            # vòng 1 caught this exact regression here) for the rotated
            # blocks. Order is
            # load-bearing per U6/RK-3: MUST run on `merged_path` AFTER
            # merge_chunk_pdfs() (so page numbers match final output) and BEFORE
            # compress_pdf_images() below (so the compress step's image re-encode
            # never has to reconcile with text this step is still about to add).
            # Only babeldoc gets this — pdf2zh doesn't drop rotated text (V-2).
            # Chosen assumption (Giả định tự chọn, no spec covers this):
            # best-effort — a bug in this new overlay step is logged and
            # swallowed rather than failing an otherwise-successful job, matching
            # the rollback-by-feature-flag intent of `babeldoc_rotated_text_overlay`.
            if (
                self._settings.pdf_translate_engine == "babeldoc"
                and self._settings.babeldoc_rotated_text_overlay
            ):
                overlay_result = None
                try:
                    overlay_font_path = Path(self._noto_font_path or self._settings.noto_font_path)
                    overlay_result = await overlay_rotated_text(
                        source_pdf_path=translation_source_path,
                        output_pdf_path=merged_path,
                        provider=pricing_provider,
                        glossary_prompt=await build_system_prompt(
                            glossary_manager, project_id=job.batch_id
                        ),
                        font_path=overlay_font_path,
                    )
                except Exception:
                    logger.warning(
                        "overlay_rotated_text that bai cho job %s — tiep tuc "
                        "khong co overlay chu xoay (best-effort, khong lam fail job)",
                        job.id,
                        exc_info=True,
                    )

                # Non-blocking #1 (review-report.md, R6-04 vong 1): log
                # persist_findings() that bai RIENG voi overlay_rotated_text()
                # that bai — gop chung 1 except lam finding FLAG hop le (overlay
                # da chay dung) bien mat im lang, QA se khong bao gio thay trang
                # can soi tay (U7-E3 doi hoi soi 100% trang co flag).
                if overlay_result is not None and overlay_result.findings:
                    try:
                        await persist_findings(
                            db_session,
                            overlay_result.findings,
                            job_id=job.id,
                            source_file=file_path.name,
                        )
                    except Exception:
                        logger.warning(
                            "persist_findings that bai cho job %s sau khi overlay_rotated_text "
                            "da tra ve %d finding — cac finding nay se KHONG duoc QA thay "
                            "(best-effort, khong lam fail job)",
                            job.id,
                            len(overlay_result.findings),
                            exc_info=True,
                        )

            # US-16/BR-IMGCOMP-01: only babeldoc jobs get the raw-image ->
            # JPEG re-encode (Architecture.md S5 data lineage — this must run
            # on `merged_path`, the file merge_chunk_pdfs() just wrote, and
            # AFTER the BR-OCR-03 guard above so a compression bug reports as
            # a compression failure instead of a false "no text" diagnosis).
            if self._settings.pdf_translate_engine == "babeldoc":
                await compress_pdf_images(merged_path)
        except Exception as exc:  # noqa: BLE001 — same failure shape as Step 7
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
            db_session.add(job)
            await db_session.commit()

            await self._broadcast_job_failed(job, total_chunks, total_chunks)

            return JobResult(
                job_id=job.id,
                status="failed",
                output_path=job.output_path,
                bilingual_path=job.bilingual_path,
                actual_cost=job.actual_cost,
                error_message=job.error_message,
            )

        job.output_path = str(merged_path)

        # Step 9: bilingual output (neu user chon).
        if await self._wants_bilingual(job, db_session):
            bilingual_path = self._output_dir / job.id / "bilingual_vi_en.pdf"
            await create_bilingual_pdf(merged_path, file_path, bilingual_path)
            job.bilingual_path = str(bilingual_path)

        # Step 10: finalize cost (UOC LUONG — pdf2zh khong xuat token that, 6.6.6).
        job.actual_cost = sum(chunk.api_cost or 0.0 for chunk in chunks)
        job.cost_source = "estimated"
        job.status = "completed"
        job.progress = 1.0
        job.current_chunk = total_chunks
        job.total_chunks = total_chunks
        job.completed_at = datetime.now(UTC)
        job.finished_at = job.completed_at  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
        db_session.add(job)
        await db_session.commit()

        if self._progress_broadcaster is not None:
            # Architecture.md 5.2 "job_completed" event shape.
            await self._progress_broadcaster(
                job.id,
                {
                    "type": "job_completed",
                    "job_id": job.id,
                    "output_path": job.output_path,
                    "actual_cost": job.actual_cost,
                    "cost_source": job.cost_source,
                },
            )

        return JobResult(
            job_id=job.id,
            status="completed",
            output_path=job.output_path,
            bilingual_path=job.bilingual_path,
            actual_cost=job.actual_cost,
        )

    async def run_epub_job(self, job: Job, db_session: AsyncSession) -> JobResult:
        """US-22 buoc 2/3 (Architecture.md 6.20.8, sua boi 6.20.12): dich EPUB
        qua chinh Translation Engine noi bo — KHONG dung bilingual_book_maker
        o bat ky dau (BR-EPUB-03). Cung khung xuong voi `run_job()`'s Step 7
        (progress_tracker -> Lop 3 cost accumulator -> cancel check, COPY
        NGUYEN thu tu, khong viet lai logic moi) de moi co che da verify song
        (resume BR-CHUNK-05, cost gate Lop 3, cancel) duoc tai su dung nguyen
        trang cho EPUB.
        """
        file_path = Path(job.file_path)

        # E1 (Architecture.md 6.20.8/6.20.9 buoc 2): `load()` DUY NHAT MOT
        # LAN — moi buoc sau (payload dich, merge, guard BR-EPUB-05) deu doc
        # lai CHINH `doc` nay. R6-02 soi day (2)->(7): load() lan thu hai voi
        # bo loc/trang thai khac se lam unit_id lech, Bug #5 tai sinh dang EPUB.
        doc = EpubDocument.load(file_path)
        if job.total_units is None:
            job.total_units = len(doc.units)
            db_session.add(job)
            await db_session.commit()

        # E2/E3 (Architecture.md 6.20.9 bang dong 3/4, §6.11.6): glossary
        # PHAI duoc loc theo `full_text` truoc khi build system prompt, cung
        # 1 co che loc voi `cost_gate.py::_estimate_epub_translation_cost()`
        # (goi `glossary_manager.build_prompt_snippet(only_terms_present_in=...)`
        # qua `build_prompt_text()`) — neu khong Lop 2 uoc chi phi tren tap
        # glossary da loc trong khi prompt THAT gui di khong loc, co the uoc
        # THAP hon request that (vi pham "cam uoc thap"). Fix: truyen thang
        # `doc.full_text()` (CUNG mot lan `load()` o buoc E1 phia tren, khong
        # load() lai) vao `build_system_prompt()` qua tham so
        # `only_terms_present_in` (them moi, xem prompt_builder.py) +
        # `max_glossary_entries` lay tu CUNG settings PDF dang dung
        # (`self._settings.max_glossary_entries_in_prompt`) de khop dung cap
        # ma `cost_gate.py` da dung khi uoc.
        glossary_manager = GlossaryManager(db_session)
        base_system_prompt = await build_system_prompt(
            glossary_manager,
            project_id=job.batch_id,
            only_terms_present_in=doc.full_text(),
            max_glossary_entries=self._settings.max_glossary_entries_in_prompt,
        )
        system_prompt = build_epub_batch_prompt(base_system_prompt)

        # E4: plan_epub_chunks() + resume-aware Chunk rows (BR-CHUNK-05).
        chunk_plan = plan_epub_chunks(
            doc.units,
            char_budget=self._settings.epub_chunk_char_budget,
            request_budget=self._settings.epub_request_char_budget,
        )
        chunks = await self._load_or_create_epub_chunks(job, chunk_plan, db_session)
        plan_by_index: dict[int, EpubChunkPlan] = {p.index: p for p in chunk_plan}

        job.status = "translating"
        job.started_at = job.started_at or datetime.now(UTC)
        db_session.add(job)
        await db_session.commit()

        # Out-of-band -> khong con out-of-band cho EPUB: day CHINH LA provider
        # goi that (khong co bilingual_book_maker/pdf2zh o giua) — nhung van
        # tai su dung provider_factory injection giong PDF (test co the mock).
        pricing_provider = self._provider or self._provider_factory.create(
            job.model, self._settings
        )

        progress_tracker = ProgressTracker(broadcaster=self._progress_broadcaster)
        total_chunks = len(chunks)

        # E5/E6: voi moi chunk chua completed — COPY NGUYEN thu tu 3 buoc cua
        # run_job() Step 7 (progress -> Lop 3 -> cancel) sau MOI chunk.
        for position, chunk in enumerate(chunks, start=1):
            if chunk.status != "completed":
                try:
                    await self._process_epub_chunk(
                        job,
                        chunk,
                        doc,
                        plan_by_index[chunk.chunk_index],
                        system_prompt,
                        pricing_provider,
                        db_session,
                    )
                except Exception as exc:  # noqa: BLE001 — same failure shape as run_job() Step 7
                    chunk.status = "failed"
                    chunk.error_message = str(exc)
                    chunk.retry_count += 1
                    db_session.add(chunk)

                    job.status = "failed"
                    job.error_message = f"Chunk {chunk.chunk_index} that bai: {exc}"
                    job.finished_at = datetime.now(
                        UTC
                    )  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
                    db_session.add(job)
                    await db_session.commit()

                    await self._broadcast_job_failed(job, position, total_chunks)

                    return JobResult(
                        job_id=job.id,
                        status="failed",
                        output_path=job.output_path,
                        bilingual_path=job.bilingual_path,
                        actual_cost=job.actual_cost,
                        error_message=job.error_message,
                    )

            await progress_tracker.update(job.id, position, total_chunks, db_session)

            # Financial Safety Lop 3 (Architecture.md 6.11.4), y het Step 7
            # cua run_job() — KHAC 1 diem CO CHU DICH: `chunk.api_cost` o day
            # la chi phi THAT (tu `TranslationResult`, khong phai
            # `estimate_chunk_cost()`), nen `cost_source` duoi day la
            # "metered" thay vi "estimated" — dung voi ban chat cua con so.
            completed_cost = sum(c.api_cost or 0.0 for c in chunks[:position])
            effective_cap = (
                job.cost_cap_usd
                if job.cost_cap_usd is not None
                else self._settings.max_cost_per_job_usd
            )
            if self._settings.cost_cap_enabled and completed_cost > effective_cap:
                job.actual_cost = completed_cost
                job.cost_source = "metered"
                job.status = "cost_capped"
                job.error_message = (
                    f"Job dung o chunk {chunk.chunk_index}: chi phi THAT tich luy "
                    f"${completed_cost:.4f} da vuot tran ${effective_cap:.2f}. Cac chunk da "
                    "dich duoc giu nguyen — tang tran trong Settings roi bam Retry de chay tiep."
                )
                job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
                db_session.add(job)
                await db_session.commit()

                await self._broadcast_job_cost_capped(job, position, total_chunks)

                return JobResult(
                    job_id=job.id,
                    status="cost_capped",
                    output_path=job.output_path,
                    bilingual_path=job.bilingual_path,
                    actual_cost=job.actual_cost,
                    error_message=job.error_message,
                )

            await db_session.refresh(job)
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
                db_session.add(job)
                await db_session.commit()

                await self._broadcast_job_cancelled(job, position, total_chunks)

                return JobResult(
                    job_id=job.id,
                    status="cancelled",
                    output_path=job.output_path,
                    bilingual_path=job.bilingual_path,
                    actual_cost=job.actual_cost,
                )

        # E7: gop MOI chunk `completed` (khong chi cac chunk vua chay o vong
        # nay — R6-02 soi day (6)->(7): resume phai doc lai chunk da xong tu
        # truoc, khong chi chunk moi).
        job.status = "merging"
        db_session.add(job)
        await db_session.commit()

        translations: dict[str, str] = {}
        for db_chunk in chunks:
            if db_chunk.status == "completed" and db_chunk.output_path:
                chunk_translations = json.loads(
                    Path(db_chunk.output_path).read_text(encoding="utf-8")
                )
                translations.update(chunk_translations)

        # E8: `bilingual=True` mac dinh cho EPUB (CHOT, Architecture.md
        # 6.20.11 muc 2 — PM/user da xac nhan qua AskUserQuestion). Chua co
        # duong UI nao cho phep chon monolingual rieng cho EPUB o buoc nay
        # (bang task, buoc 3/3 moi lam UI) nen hardcode True thay vi doc
        # `Batch.output_mode` (mac dinh "vi_only" cho CA PDF lan EPUB o tang
        # API — dung nguyen no se lam EPUB thanh monolingual-by-default,
        # nguoc voi CHOT nay).
        bilingual = True
        merged_path = self._output_dir / job.id / "translated_vi.epub"
        merged_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            doc.write_translated(translations, merged_path, bilingual=bilingual)
            # E9 — Guard BR-EPUB-05 (X3): doc lai CHINH `merged_path` vua ghi,
            # KHONG tin `translations` con trong bo nho.
            _check_epub_output_guard(doc, merged_path, bilingual=bilingual)
        except Exception as exc:  # noqa: BLE001 — same failure shape as run_job() Step 7/8
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
            db_session.add(job)
            await db_session.commit()

            await self._broadcast_job_failed(job, total_chunks, total_chunks)

            return JobResult(
                job_id=job.id,
                status="failed",
                output_path=job.output_path,
                bilingual_path=job.bilingual_path,
                actual_cost=job.actual_cost,
                error_message=job.error_message,
            )

        job.output_path = str(merged_path)

        # E10: `cost_source='metered'` — lan dau tien trong du an, chi phi
        # THAT tu `TranslationResult` cua tung request, khong phai uoc tinh
        # hau-render nhu PDF (Architecture.md 6.20.8).
        job.actual_cost = sum(c.api_cost or 0.0 for c in chunks)
        job.cost_source = "metered"
        job.status = "completed"
        job.progress = 1.0
        job.current_chunk = total_chunks
        job.total_chunks = total_chunks
        job.completed_at = datetime.now(UTC)
        job.finished_at = job.completed_at  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
        db_session.add(job)
        await db_session.commit()

        if self._progress_broadcaster is not None:
            # Architecture.md 5.2 "job_completed" event shape (same as PDF's
            # run_job() Step 10).
            await self._progress_broadcaster(
                job.id,
                {
                    "type": "job_completed",
                    "job_id": job.id,
                    "output_path": job.output_path,
                    "actual_cost": job.actual_cost,
                    "cost_source": job.cost_source,
                },
            )

        return JobResult(
            job_id=job.id,
            status="completed",
            output_path=job.output_path,
            bilingual_path=job.bilingual_path,
            actual_cost=job.actual_cost,
        )

    async def run_parse_only(self, job: Job, db_session: AsyncSession) -> JobResult:
        """US-15 (Architecture.md 6.15.3): Markdown parse-only — runs the
        Parsing Engine (MinerU) only, skips Translation Engine, Glossary
        injection and Unit Conversion entirely (BR-PARSE-01). Only the PDF
        branch (`pdf_digital`/`pdf_scan`) is implemented — the EPUB branch
        depends on `EpubDocument.to_markdown()` (US-22, §6.15.3 S15-8), out
        of scope for this increment.
        """
        if job.file_type == FileType.EPUB:
            # S15-8 "he qua thu tu lam viec": API layer (create_job()/
            # create_batch() in src/api/routes/jobs.py) already rejects
            # job_type=parse_only + file_type=epub with HTTP 400 BEFORE any
            # Job row is created — that is the primary guard. This is a
            # second, defensive layer only (e.g. a Job row created by some
            # future/other path) so such a job can never silently "run" or
            # hang for up to `mineru_task_timeout_seconds`.
            raise EpubNotSupportedError(
                "Markdown parse-only cho EPUB chua duoc ho tro, se co khi tinh nang dich "
                "EPUB hoan thien (Architecture.md 6.15.3 S15-8)."
            )

        file_path = Path(job.file_path)

        if job.total_pages is None:
            job.total_pages = _count_pdf_pages(file_path)
            db_session.add(job)
            await db_session.commit()

        # S15-9 (YA-7.3): parse_only cho CA pdf_digital cung bat buoc MinerU
        # dang chay — fail SOM voi thong bao ro rang thay vi de user cho het
        # timeout (duoi day) trong vo ich. Cung mau hinh nhu guard
        # `_mineru_runner is None` cua `_build_ocr_bridge()` — khong duoc
        # chay tiep khi khong co MinerU (Bug #5's class of error).
        if self._mineru_runner is None:
            raise MinerUUnavailableError(
                "File can MinerU de parse nhung MinerU chua duoc cau hinh (MINERU_ENDPOINT)"
            )
        await self._mineru_runner.health()

        job.status = "parsing"
        job.started_at = job.started_at or datetime.now(UTC)
        # Architecture.md 6.21.3: `job.parse_method` is normally already
        # resolved at job-creation time (POST /api/jobs's `_resolve_parse_method()`
        # — "auto" mapped to file_type ONCE, or an explicit user override
        # like forcing "ocr" on a pdf_digital file for L-4). This is only a
        # fallback for a Job row that reached here without going through
        # that path (an older row created before this column existed, or a
        # Job built directly in a test) — same original S15 mapping as
        # before, now persisted so it never has to be recomputed again for
        # THIS job (a retry reuses the exact value written here).
        job.parse_method = job.parse_method or (
            "txt" if job.file_type == FileType.PDF_DIGITAL else "ocr"
        )
        db_session.add(job)
        await db_session.commit()

        parse_method = job.parse_method
        # S15-14: hang so 3600s co dinh khong hop ly cho moi file — do that
        # 89s/25 trang (~3.6s/trang, Architecture.md 6.15.3 S15-14) => sach
        # 415 trang ~25 phut. He so 6 = 3.6 x ~1.65 bien an toan.
        timeout_seconds = max(600.0, job.total_pages * 6.0)

        async def _should_cancel() -> bool:
            # S15-13: doc lai tu DB moi vong poll — 1 request KHAC (POST
            # .../cancel) co the da dat co nay trong luc task nay dang cho
            # MinerU tra ket qua (co the toi ~25 phut).
            await db_session.refresh(job)
            return job.cancel_requested

        try:
            result = await self._run_parse_only_pipeline(
                job, file_path, parse_method, timeout_seconds, _should_cancel, db_session
            )
        except MinerUCancelledError:
            job.status = "cancelled"
            job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
            db_session.add(job)
            await db_session.commit()
            await self._broadcast_job_cancelled(job, 0, 1)
            return JobResult(
                job_id=job.id,
                status="cancelled",
                output_path=job.output_path,
                bilingual_path=None,
                actual_cost=job.actual_cost,
            )
        except Exception as exc:  # noqa: BLE001 — same failure shape as run_job() Step 7/8
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
            db_session.add(job)
            await db_session.commit()
            await self._broadcast_job_failed(job, 0, 1)
            return JobResult(
                job_id=job.id,
                status="failed",
                output_path=job.output_path,
                bilingual_path=None,
                actual_cost=job.actual_cost,
                error_message=job.error_message,
            )

        return result

    async def _run_parse_only_pipeline(
        self,
        job: Job,
        file_path: Path,
        parse_method: str,
        timeout_seconds: float,
        should_cancel: Callable[[], Awaitable[bool]],
        db_session: AsyncSession,
    ) -> JobResult:
        """The part of `run_parse_only()` that runs once the job is already
        `status="parsing"` — kept as a separate method so `run_parse_only()`
        can wrap it in ONE try/except (mirrors `run_job()` Step 7/8's shape:
        once a job has started mutating state, failures are caught locally
        and turned into a graceful JobResult, not left to propagate).
        """
        processing_dir = self._processing_dir / job.id / "parse_output"

        # S15-6 (rewritten after Domain Expert review — the original spec was
        # WRONG): `parse_method="txt"` does NOT mean `quality.confidence is
        # None`. MinerU 3.4.5 assigns `score=1.0` to every text-layer span in
        # txt mode (verified live against Figoni 1-25p — see
        # tests/fixtures/mineru/parse_only_txt_figoni25/) — a number, not a
        # real OCR quality signal. `jobs.ocr_confidence` has exactly ONE
        # meaning everywhere else in the app ("OCR recognition confidence"),
        # so this branch must NEVER let a txt-mode value reach it — record
        # only for pdf_scan (real OCR), force None for pdf_digital below.
        ocr_result = await self._run_mineru_and_record_quality(
            job,
            file_path,
            processing_dir,
            parse_method=parse_method,
            task_timeout_seconds=timeout_seconds,
            should_cancel=should_cancel,
            record_confidence=(job.file_type == FileType.PDF_SCAN),
        )

        if job.file_type == FileType.PDF_DIGITAL:
            job.ocr_confidence = None
            job.ocr_dropped_spans = None

        markdown_text = ocr_result.markdown_path.read_text(encoding="utf-8")
        if len(markdown_text.strip()) == 0:
            raise ParseOnlyEmptyOutputError(
                f"MinerU parse ra Markdown rong (0 ky tu doc duoc) cho file '{job.filename}' "
                "— job that bai thay vi tra ve file rong (tuong duong BR-OCR-03 cho nhanh parse)."
            )

        # Buoc 2 (Architecture.md 6.15.4 lineage): copy tu data/processing/
        # sang data/outputs/{job_id}/ — TU DAY VE SAU chi doc/ghi trong thu
        # muc nay, khong quay lai doc `ocr_result.markdown_path`/`images_dir`.
        output_dir = self._output_dir / job.id
        output_dir.mkdir(parents=True, exist_ok=True)
        final_md_path = output_dir / "document.md"
        final_md_path.write_text(markdown_text, encoding="utf-8")

        final_images_dir = output_dir / "images"
        final_images_dir.mkdir(exist_ok=True)
        image_files: list[Path] = []
        if ocr_result.images_dir.exists():
            for image_file in sorted(ocr_result.images_dir.iterdir()):
                if image_file.is_file():
                    target = final_images_dir / image_file.name
                    shutil.copyfile(image_file, target)
                    image_files.append(target)

        # Buoc 3 (guard S15-5): doc lai CHINH file `document.md` vua ghi o
        # Buoc 2 — khong tin bien `markdown_text` trong bo nho (dung tinh
        # than R6-02 rut ra tu Bug #5: assert/guard tren artifact THAT).
        if len(final_md_path.read_text(encoding="utf-8").strip()) == 0:
            raise ParseOnlyEmptyOutputError(
                "document.md rong sau khi ghi vao data/outputs — job that bai."
            )

        # Buoc 4 (S15-3, ZIP EAGER trong luc xu ly job, KHONG lazy trong
        # download.py): danh sach file TUONG MINH, khong os.walk() thu muc
        # dich — walk la duong duy nhat khien zip tu nen chinh no (ly do 2
        # trong phan bien cua Domain Expert, Architecture.md 6.15.3 S15-3).
        zip_path = output_dir / "parse_result.zip"
        tmp_zip_path = output_dir / "parse_result.zip.tmp"
        with zipfile.ZipFile(tmp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(final_md_path, arcname="document.md")
            for image_file in image_files:
                zf.write(image_file, arcname=f"images/{image_file.name}")
        os.replace(tmp_zip_path, zip_path)  # khong bao gio ton tai zip do mang ten that

        # Buoc 5 (guard ZIP, them sau phan bien cua Domain Expert): mo lai
        # CHINH file zip vua ghi, khong tin trang thai trong bo nho.
        with zipfile.ZipFile(zip_path) as zf:
            bad_entry = zf.testzip()
            names = zf.namelist()
            images_in_zip = sum(1 for name in names if name.startswith("images/"))
        if bad_entry is not None or "document.md" not in names or images_in_zip != len(image_files):
            raise ParseOnlyZipGuardError(
                "ZIP output bi loi sau khi dong goi (testzip/thieu document.md/lech so anh "
                f"— zip co {images_in_zip} entry images/, thu muc co {len(image_files)} file) "
                "— job that bai."
            )

        job.output_path = str(zip_path)
        # S15-14: 0.0 la so do THAT (khong goi LLM nao) — dung "metered" chu
        # khong phai "estimated" de frontend khong hien canh bao "uoc tinh co
        # the sai lech" cho 1 con so chac chan bang 0.
        job.actual_cost = 0.0
        job.cost_source = "metered"
        job.status = "completed"
        job.progress = 1.0
        job.completed_at = datetime.now(UTC)
        job.finished_at = job.completed_at  # US-19/BR-HIST-01/02, Architecture.md 6.17.2
        db_session.add(job)
        await db_session.commit()

        if self._progress_broadcaster is not None:
            # Architecture.md 5.2 "job_completed" event shape (same as
            # run_job() Step 10) — frontend's WS handler only branches on
            # `type`, so reusing the shape needs no frontend-side special case.
            await self._progress_broadcaster(
                job.id,
                {
                    "type": "job_completed",
                    "job_id": job.id,
                    "output_path": job.output_path,
                    "actual_cost": job.actual_cost,
                    "cost_source": job.cost_source,
                },
            )

        return JobResult(
            job_id=job.id,
            status="completed",
            output_path=job.output_path,
            bilingual_path=None,
            actual_cost=job.actual_cost,
        )

    async def _run_mineru_and_record_quality(
        self,
        job: Job,
        file_path: Path,
        output_dir: Path,
        *,
        parse_method: str = "ocr",
        task_timeout_seconds: float | None = None,
        should_cancel: Callable[[], Awaitable[bool]] | None = None,
        record_confidence: bool = True,
    ) -> MinerUResult:
        """US-15 §6.15.3 S15-13: THE single call site for "submit a MinerU
        parse/OCR task and write jobs.ocr_confidence/ocr_dropped_spans + emit
        the US-11 warning" — shared by `_build_ocr_bridge()` (translate,
        pdf_scan, always `parse_method="ocr"`, no custom timeout/cancel) and
        `_run_parse_only_pipeline()` (both `parse_method` values, per-page
        timeout, cancel support). One definition means the two call sites
        cannot silently drift the way Bug #5's OCR-to-translation wiring did.

        `record_confidence=False` (S15-6, `run_parse_only()`'s pdf_digital
        branch): the caller still gets back the real `MinerUResult` (it needs
        `quality` for its own guard checks upstream) but this helper does NOT
        write `ocr_result.quality` onto `job` — the caller is responsible for
        explicitly forcing the field to `None` itself, so a confidence number
        with no real OCR behind it can never leak through this shared path
        onto `jobs.ocr_confidence`.
        """
        ocr_result = await self._mineru_runner.parse_document(
            file_path,
            output_dir,
            parse_method=parse_method,
            task_timeout_seconds=task_timeout_seconds,
            should_cancel=should_cancel,
        )
        if record_confidence:
            job.ocr_confidence = ocr_result.quality.confidence
            job.ocr_dropped_spans = ocr_result.quality.dropped_span_count
            await self._emit_ocr_warning_if_low(job)
        return ocr_result

    async def _build_ocr_bridge(self, job: Job, file_path: Path, db_session: AsyncSession) -> Path:
        """Architecture.md 6.10.5: OCR the scan (or reuse a prior run's
        result, BR-CHUNK-05) and turn it into a searchable-PDF bridge. Returns
        the bridge path — the ONLY thing `run_job()` should treat as
        `translation_source_path` for a `pdf_scan` job from here on.
        """
        if self._mineru_runner is None:
            # BR-OCR-01: KHONG duoc chay tiep bang file goc — do chinh la
            # Bug #5 (job "completed" tren file khong co text layer).
            raise MinerUUnavailableError(
                "File scan can OCR nhung MinerU chua duoc cau hinh (MINERU_ENDPOINT)"
            )

        bridge_path = self._processing_dir / job.id / "ocr_bridge" / "searchable.pdf"
        ocr_dir = self._processing_dir / job.id / "ocr_output"

        if job.ocr_bridge_path and Path(job.ocr_bridge_path).exists():
            # BR-CHUNK-05 resumable: da OCR + dung cau noi o lan chay truoc.
            # Bug #6 Phase 1: middle.json cua lan chay truoc van con tren dia
            # (cung thu muc `ocr_dir` ma `_write_middle_json` da ghi vao,
            # xem src/services/mineru_runner.py) — chay probe o day thay vi
            # bo qua no tren job resumable, giu dung tinh chat "best-effort,
            # doc lap voi trang thai resumable" cua tinh nang nay.
            await self._run_rotated_text_probe(job, file_path, ocr_dir / "middle.json", db_session)
            return Path(job.ocr_bridge_path)

        # `quality.confidence` is `None` when no span went through OCR at all
        # (e.g. an image-only page) — a valid state, not an error
        # (Architecture.md 6.9.5). `jobs.ocr_confidence` stores NULL then.
        # US-15 S15-13: THE single call site for "submit a MinerU task +
        # write jobs.ocr_confidence/ocr_dropped_spans + emit the US-11
        # warning" — shared with `run_parse_only()`'s pdf_scan branch below,
        # so the two flows cannot silently drift on how OCR quality gets
        # recorded (Bug #5's class of error).
        ocr_result = await self._run_mineru_and_record_quality(
            job, file_path, ocr_dir, parse_method="ocr"
        )

        if ocr_result.middle_json_path is None:
            raise MinerUError(
                "MinerU khong tra middle.json — khong dung duoc text layer cho file scan"
            )

        # Bug #6 Phase 1 (Architecture.md "Final Decision" V6, step 6): CHI
        # danh cho pdf_scan (ham nay chi duoc goi cho pdf_scan — xem
        # run_job() Step 2), doc lap voi engine dich (chay TRUOC diem re
        # nhanh pdf2zh/babeldoc o run_job()). Data lineage (R6-01): dung
        # DUNG `file_path` (anh scan GOC cua CHINH job nay, chua bi whiteout)
        # + `ocr_result.middle_json_path` (middle.json CUA CHINH job nay) —
        # KHONG dung `bridge.path` (da bi whiteout, detector se khong thay
        # gi de phat hien).
        await self._run_rotated_text_probe(job, file_path, ocr_result.middle_json_path, db_session)

        bridge = build_searchable_pdf(file_path, ocr_result.middle_json_path, bridge_path)
        job.ocr_bridge_path = str(bridge.path)
        db_session.add(job)
        await db_session.commit()
        return bridge.path

    async def _run_rotated_text_probe(
        self, job: Job, file_path: Path, middle_json_path: Path, db_session: AsyncSession
    ) -> None:
        """Bug #6 Phase 1 (Architecture.md "Final Decision" V6): best-effort,
        SAME failure-handling shape as `overlay_rotated_text()`'s call site
        below (2 separate try/except blocks — detection failure and persist
        failure are logged distinctly, so a persist bug never silently
        swallows an already-successful detection the way the pre-R6-04
        single-except version did for the overlay feature). Never raises —
        a bug here must never fail an otherwise-successful OCR/translation
        job (Architecture.md V6 step 6 explicit instruction).
        """
        if not self._settings.mineru_det_probe_enabled:
            return
        if not middle_json_path.exists():
            return

        findings = None
        try:
            findings = await probe_and_flag_rotated_text(
                file_path, middle_json_path, python_path=self._settings.mineru_python_path
            )
        except Exception:  # best-effort — see docstring, must never fail the job
            logger.warning(
                "mineru_det_probe that bai cho job %s — bo qua flag chu xoay tren "
                "trang scan (best-effort, khong lam fail job)",
                job.id,
                exc_info=True,
            )
            return

        if not findings:
            return

        try:
            await persist_findings(db_session, findings, job_id=job.id, source_file=file_path.name)
        except Exception:
            logger.warning(
                "persist_findings that bai cho job %s sau khi mineru_det_probe tra ve "
                "%d finding rotated_text_scan_unsupported — cac finding nay se KHONG "
                "duoc QA thay (best-effort, khong lam fail job)",
                job.id,
                len(findings),
                exc_info=True,
            )

    async def _emit_ocr_warning_if_low(self, job: Job) -> None:
        """US-11 / AC-11.2 (Architecture.md 6.10.6): the only defense line
        against OCR that *ran* but *misread* — the bridge still ends up with
        SOME text, so guards BR-OCR-02/03 never fire, but the translation may
        be wrong. Non-blocking: v1.0 jobs run in the background with no
        pause/resume-by-user, so this is a notice, not a gate.
        """
        warning = build_ocr_warning(
            job.ocr_confidence, job.ocr_dropped_spans, self._settings.ocr_confidence_threshold
        )
        if warning is None or self._progress_broadcaster is None:
            return
        # Architecture.md 5.2 "ocr_warning" event shape.
        await self._progress_broadcaster(
            job.id,
            {
                "type": "ocr_warning",
                "job_id": job.id,
                "confidence": job.ocr_confidence,
                "dropped_span_count": job.ocr_dropped_spans,
                "message": warning,
            },
        )

    async def _broadcast_job_failed(
        self, job: Job, completed_chunks: int, total_chunks: int
    ) -> None:
        if self._progress_broadcaster is None:
            return
        # Architecture.md 5.2 "job_failed" event shape.
        await self._progress_broadcaster(
            job.id,
            {
                "type": "job_failed",
                "job_id": job.id,
                "error": job.error_message,
                "completed_chunks": completed_chunks,
                "total_chunks": total_chunks,
            },
        )

    async def _broadcast_job_cancelled(
        self, job: Job, completed_chunks: int, total_chunks: int
    ) -> None:
        if self._progress_broadcaster is None:
            return
        # Khong co shape san trong Architecture.md 5.2 cho "cancel" — dung
        # cung 1 dang voi "job_failed"/"job_completed" (type + job_id + so
        # chunk) de frontend xu ly deu, khac o `type` va khong co `error`.
        await self._progress_broadcaster(
            job.id,
            {
                "type": "job_cancelled",
                "job_id": job.id,
                "completed_chunks": completed_chunks,
                "total_chunks": total_chunks,
            },
        )

    async def _broadcast_job_cost_capped(
        self, job: Job, completed_chunks: int, total_chunks: int
    ) -> None:
        if self._progress_broadcaster is None:
            return
        # Same event shape as "job_failed"/"job_cancelled" (Architecture.md
        # 5.2 has no pre-existing shape for this — Increment 6 already
        # established the pattern of reusing it for a new terminal type).
        await self._progress_broadcaster(
            job.id,
            {
                "type": "job_cost_capped",
                "job_id": job.id,
                "actual_cost": job.actual_cost,
                "error": job.error_message,
                "completed_chunks": completed_chunks,
                "total_chunks": total_chunks,
            },
        )

    async def _process_chunk(
        self,
        job: Job,
        chunk: Chunk,
        source_path: Path,
        service: Pdf2zhService,
        prompt_file: Path,
        prompt_overhead_chars: int,
        pricing_provider: TranslationProvider,
        db_session: AsyncSession,
    ) -> None:
        chunk.status = "translating"
        chunk.started_at = datetime.now(UTC)
        db_session.add(chunk)
        await db_session.commit()

        # --- AIMD concurrency (Architecture.md 6.12) ----------------------
        # Key = (job.model, service.service_arg) per Architecture.md 6.12.4.1,
        # which settled the escalation over 6.12.4's original `job.model_provider`
        # (a field that never existed): `Job.model` IS the provider identifier
        # everywhere else in this codebase, and `service_arg` is the exact
        # backend+model string handed to `pdf2zh -s`, so distinct models keep
        # distinct state without a second `Job` column or a `split(":")` parse.
        provider = job.model
        model_key = service.service_arg
        engine = self._settings.pdf_translate_engine
        concurrency_mode, thread, concurrency_state = await self._resolve_thread(
            engine, provider, model_key, db_session
        )

        # R6-01: written BEFORE the subprocess call, so lineage is explicit
        # even if the call itself crashes.
        chunk.thread_used = thread
        db_session.add(chunk)
        await db_session.commit()

        # `source_path` == `translation_source_path` from `run_job()` — the
        # OCR bridge for pdf_scan, the original file otherwise. NOT read back
        # from `job.file_path` here: that re-introduces Bug #5 (Architecture.md
        # 6.10.5 lineage table).
        # F9: 1 output dir rieng biet cho MOI chunk — pdf2zh dat ten output theo
        # ten file input, dung chung dir se ghi de giua cac chunk.
        chunk_output_dir = self._processing_dir / job.id / f"chunk_{chunk.chunk_index}"

        async def _call_translator():
            # DAY LA LAN GOI LLM DUY NHAT cho noi dung cua chunk nay — nam BEN
            # TRONG pdf2zh/babeldoc (Architecture.md 6.6.2 R1 / 6.14.3). Khong
            # goi provider.translate(). `self._translator_runner` la 1 trong 2
            # (`Pdf2zhRunner` hoac `BabeldocRunner`), chon 1 lan duy nhat trong
            # `__init__` (6.14.7) — khong co `if engine == ...` o day.
            # `input_path=source_path` == `translation_source_path` cua
            # `run_job()`, TUYET DOI KHONG `job.file_path` (Bug #5, 6.14.4).
            #
            # Bug (2026-09-05, QA thuc te tren "How Baking Works"): `chunk_output_dir`
            # la duong dan CO DINH, khong doi giua cac lan goi ham nay — ca khi
            # `with_retry` (ngay ben duoi) tu retry trong CUNG 1 lan `_process_chunk()`
            # (vd rate limit) lan khi ca job bi crash/cancel giua chung roi resume o
            # Buoc 7 (`chunk.status != "completed"` — dong ~348 — chay lai TU DAU
            # chunk nay, tuc goi lai ham nay vao DUNG thu muc cu con file
            # `{stem}-mono.pdf` cua (mot phan) lan chay truoc). Da xac nhan song
            # bang PyMuPDF tren file output that: trang co doan van dich LAP 2 LAN
            # o 2 vi tri/co chu khac nhau + PDF co 3 content stream thay vi 1 —
            # dau hieu pdf2zh/babeldoc ghi chong len file cu thay vi bat dau tu
            # file nguon sach se. Xoa thu muc o DAU MOI LAN GOI (khong phai 1 lan
            # truoc `with_retry`) de moi attempt — ke ca cac attempt retry ngam
            # ben trong `with_retry` — deu ghi vao thu muc rong, khong phu thuoc
            # gia dinh ve hanh vi ghi-de noi bo cua pdf2zh/babeldoc (external
            # tool, khong kiem soat duoc source).
            if chunk_output_dir.exists():
                shutil.rmtree(chunk_output_dir)
            return await self._translator_runner.translate_pages(
                input_path=source_path,
                output_dir=chunk_output_dir,
                page_range=f"{chunk.page_start}-{chunk.page_end}",
                service=service,
                prompt_file=prompt_file,
                ignore_cache=self._settings.pdf2zh_ignore_cache,
                timeout_seconds=self._settings.pdf2zh_timeout_seconds,
                thread=thread,
                # F2 (Architecture.md "Root Cause Analysis: Line-break/List
                # Regression"): tham so nay chi co y nghia voi BabeldocRunner
                # (Pdf2zhRunner nhan roi bo qua — xem docstring
                # `pdf2zh_runner.translate_pages()`), nhung van truyen dong
                # nhat cho ca 2 engine, khong re nhanh `if engine == ...` o
                # day (6.14.7 "DIEM CHON ENGINE DUY NHAT").
                split_short_lines=self._settings.babeldoc_split_short_lines,
                short_line_split_factor=(
                    self._settings.babeldoc_short_line_split_factor
                    if self._settings.babeldoc_split_short_lines
                    else None
                ),
            )

        timeout_budget = self._settings.pdf2zh_timeout_seconds
        try:
            pdf2zh_result = await with_retry(_call_translator)
        except (Pdf2zhTimeoutError, Pdf2zhError, BabeldocTimeoutError, BabeldocError) as exc:
            # R6-02/R6-04: `rate_limit_hits` here is `exc.rate_limit_hits` —
            # the SAME count `Pdf2zhRunner` derived from `stdout + stderr` of
            # THIS call (Architecture.md 6.12.2 D1), never recomputed from a
            # narrower slice. `exit_code=None` for a timeout (no process exit
            # occurred, it was killed — see `classify_chunk_outcome` docstring);
            # any non-None placeholder for `Pdf2zhError`, since that exception
            # never carries the literal exit code, only that it was != 0.
            chunk.rate_limit_hits = exc.rate_limit_hits
            db_session.add(chunk)
            await db_session.commit()

            is_timeout = isinstance(exc, (Pdf2zhTimeoutError, BabeldocTimeoutError))
            outcome = classify_chunk_outcome(
                exit_code=None if is_timeout else 1,
                rate_limit_hits=exc.rate_limit_hits,
                duration_seconds=timeout_budget,
                timeout_seconds=timeout_budget,
            )
            await self._observe_chunk_outcome(
                engine,
                concurrency_mode,
                concurrency_state,
                provider,
                outcome,
                exc.rate_limit_hits,
                timeout_budget,
                db_session,
            )
            raise

        chunk.output_path = str(pdf2zh_result.mono_path)
        # R6-02/R6-04: from `Pdf2zhResult.rate_limit_hits`, which
        # `Pdf2zhRunner.translate_pages()` computed from `stdout + stderr` of
        # THIS exact call — NOT re-derived from `.stderr` alone here (that
        # regression is exactly what 6.12.2 D1 exists to prevent).
        chunk.rate_limit_hits = pdf2zh_result.rate_limit_hits

        outcome = classify_chunk_outcome(
            exit_code=0,
            rate_limit_hits=pdf2zh_result.rate_limit_hits,
            duration_seconds=pdf2zh_result.duration_seconds,
            timeout_seconds=timeout_budget,
        )
        await self._observe_chunk_outcome(
            engine,
            concurrency_mode,
            concurrency_state,
            provider,
            outcome,
            pdf2zh_result.rate_limit_hits,
            pdf2zh_result.duration_seconds,
            db_session,
        )

        chunk.status = "post_processing"
        db_session.add(chunk)
        await db_session.commit()

        overflow_entries: list[OverflowEntry] = []
        # Bug #9 (Architecture.md "Bug #9", Protocol 2 2026-09-08): CHI engine
        # nao tu no khong fit text vao box moi can buoc nay. Voi babeldoc, mo
        # file ra redact + insert_text lai la thao tac thuan rui ro: khong sua
        # duoc gi ma xoa mat chu that.
        if self._needs_font_shrink:
            with fitz.open(chunk.output_path) as doc:
                for page in doc:
                    await font_shrink_page(page, overflow_entries, font_path=self._noto_font_path)
                doc.saveIncr()

        for entry in overflow_entries:
            db_session.add(
                OverflowReport(
                    job_id=job.id,
                    page_number=entry.page_number,
                    block_index=0,
                    original_text=entry.original_text,
                    bbox=str(entry.bbox),
                    font_size_original=entry.font_size_original,
                    font_size_final=entry.font_size_final,
                    scaling_applied=entry.scaling_applied,
                    still_overflow=entry.still_overflow,
                )
            )

        source_text = _extract_chunk_text(source_path, chunk)
        segment_count = _count_text_segments(source_path, chunk.page_start, chunk.page_end)
        input_tokens, output_tokens, cost_usd = estimate_chunk_cost(
            source_text=source_text,
            segment_count=segment_count,
            prompt_overhead_chars=prompt_overhead_chars,
            provider=pricing_provider,
            vi_expansion=self._settings.vi_expansion_factor,
            vi_token_factor=self._settings.vi_token_factor,
        )

        chunk.api_tokens_used = input_tokens + output_tokens
        chunk.api_cost = cost_usd
        chunk.status = "completed"
        chunk.completed_at = datetime.now(UTC)
        db_session.add(chunk)
        await db_session.commit()

    async def _process_epub_chunk(
        self,
        job: Job,
        chunk: Chunk,
        doc: EpubDocument,
        chunk_plan: EpubChunkPlan,
        system_prompt: str,
        pricing_provider: TranslationProvider,
        db_session: AsyncSession,
    ) -> None:
        """US-22 buoc 2/3 (Architecture.md 6.20.8 `_process_epub_chunk()`).
        Moi lat request trong `chunk_plan.requests` chay TUAN TU (khong AIMD
        — app goi API TRUC TIEP, nhan `RateLimitError` THAT qua `with_retry`,
        khac PDF phai *doan* tin hieu tu stdout subprocess, Architecture.md
        6.20.8 "Concurrency"). Id ngan cuc bo `0..N` trong TUNG request
        (X4/X5) — map nguoc sang `unit_id` that ngay tai day, KHONG bao gio
        ghi id ngan vao `translations`/`units.json`.
        """
        chunk.status = "translating"
        chunk.started_at = datetime.now(UTC)
        db_session.add(chunk)
        await db_session.commit()

        units = doc.units
        translations: dict[str, str] = {}
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        for start, end in chunk_plan.requests:
            slice_units = units[start : end + 1]
            payload = [{"id": str(i), "html": u.text} for i, u in enumerate(slice_units)]
            expected_ids = {str(i) for i in range(len(slice_units))}
            payload_json = json.dumps(payload, ensure_ascii=False)

            result = await with_retry(
                lambda p=payload_json: pricing_provider.translate(p, system_prompt, "en", "vi")
            )
            total_input_tokens += result.input_tokens
            total_output_tokens += result.output_tokens
            total_cost += result.estimated_cost_usd
            parsed = parse_epub_batch_response(result.text, expected_ids)

            # X4 (Architecture.md 6.20.12): id thieu -> goi lai RIENG LE, toi
            # da 1 vong. E-09: TUYET DOI khong ghi chuoi rong cho id thieu.
            missing_ids = expected_ids - parsed.keys()
            for local_id in sorted(missing_ids):
                unit = slice_units[int(local_id)]
                single_payload = json.dumps(
                    [{"id": local_id, "html": unit.text}], ensure_ascii=False
                )
                retry_result = await with_retry(
                    lambda p=single_payload: pricing_provider.translate(
                        p, system_prompt, "en", "vi"
                    )
                )
                total_input_tokens += retry_result.input_tokens
                total_output_tokens += retry_result.output_tokens
                total_cost += retry_result.estimated_cost_usd
                retry_parsed = parse_epub_batch_response(retry_result.text, {local_id})
                if local_id in retry_parsed:
                    parsed[local_id] = retry_parsed[local_id]

            still_missing = expected_ids - parsed.keys()
            if still_missing:
                missing_unit_ids = [slice_units[int(i)].unit_id for i in sorted(still_missing)]
                raise EpubBatchTranslationError(
                    f"Chunk {chunk.chunk_index}: thieu ban dich cho {len(missing_unit_ids)} "
                    f"unit sau 1 vong goi lai rieng le (vd '{missing_unit_ids[0]}') — "
                    "TUYET DOI khong ghi chuoi rong, chunk that bai (E-09)."
                )

            for local_id, vi_html in parsed.items():
                unit = slice_units[int(local_id)]
                translations[unit.unit_id] = vi_html

        # F9 (chung bai hoc voi pdf2zh_runner): 1 thu muc rieng cho MOI chunk.
        chunk_dir = self._processing_dir / job.id / f"chunk_{chunk.chunk_index}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        units_json_path = chunk_dir / "units.json"
        units_json_path.write_text(
            json.dumps(translations, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        chunk.output_path = str(units_json_path)
        # Chi phi THAT tu TranslationResult (khong phai estimate_chunk_cost())
        # — day chinh la diem `cost_source='metered'` bat nguon tu (6.20.8).
        chunk.api_tokens_used = total_input_tokens + total_output_tokens
        chunk.api_cost = total_cost
        chunk.status = "completed"
        chunk.completed_at = datetime.now(UTC)
        db_session.add(chunk)
        await db_session.commit()

    def _thread_floor(self, engine: str, provider: str) -> int:
        """Architecture.md 6.14.5: babeldoc dung floor RIENG (=
        ceil(floor_pdf2zh / 2)) vi don vi `rate_limit_hits` cua no khac pdf2zh
        (SDK openai ben trong tu nuot ~3 lan 429 truoc khi tenacity thay
        duoc). `next_thread_count()` (thuat toan AIMD) khong doi — chi doi
        floor dau vao."""
        floors = BABELDOC_THREAD_FLOOR if engine == "babeldoc" else ADAPTIVE_THREAD_FLOOR
        return floors[provider]

    async def _resolve_thread(
        self, engine: str, provider: str, model_key: str, db_session: AsyncSession
    ) -> tuple[str, int, ConcurrencyState | None]:
        """Decide `--thread`/`--pool-max-workers` for the next chunk
        (Architecture.md 6.12.4/6.12.6/6.12.8, floor engine-aware theo 6.14.5)
        and which branch `_observe_chunk_outcome()` should take afterwards.
        Returns `(mode, thread, state)`:

        - `"ollama"`: fixed `settings.ollama_thread` cho ca 2 engine (6.14.5
          muc 4 — Ollama local khong AIMD, khong ConcurrencyState).
        - `"disabled"`: `adaptive_concurrency_enabled=False` kill switch —
          fixed floor cua engine hien tai, no `ConcurrencyState` read/write
          (the safe rollback path, 6.12.8).
        - `"claude"`: state IS read/created (so `current_thread` has a stable
          value to report/debug), but AIMD is disabled ([UNVERIFIED] S6,
          6.12.6; van TAT voi babeldoc, 6.14.5 muc 5) —
          `_observe_chunk_outcome()` must never raise it above the floor.
        - `"aimd"`: normal AIMD for `deepseek`/`openai`/`gemini`.
        """
        if provider == "ollama":
            return "ollama", self._settings.ollama_thread, None

        if not self._settings.adaptive_concurrency_enabled:
            return "disabled", self._thread_floor(engine, provider), None

        state = await self._get_or_create_concurrency_state(engine, provider, model_key, db_session)
        mode = "claude" if provider == "claude" else "aimd"
        return mode, state.current_thread, state

    async def _get_or_create_concurrency_state(
        self, engine: str, provider: str, model: str, db_session: AsyncSession
    ) -> ConcurrencyState:
        state = await db_session.get(ConcurrencyState, (engine, provider, model))
        if state is None:
            state = ConcurrencyState(
                engine=engine,
                provider=provider,
                model=model,
                current_thread=self._thread_floor(engine, provider),
            )
            db_session.add(state)
            await db_session.commit()
            await db_session.refresh(state)
        return state

    async def _observe_chunk_outcome(
        self,
        engine: str,
        mode: str,
        state: ConcurrencyState | None,
        provider: str,
        outcome: ChunkOutcome,
        rate_limit_hits: int,
        duration_seconds: float,
        db_session: AsyncSession,
    ) -> None:
        """Step 3 of the per-chunk lifecycle (Architecture.md 6.12.4): update
        `ConcurrencyState` from this chunk's classified outcome and commit —
        the NEXT chunk's `_resolve_thread()` call reads back exactly this
        write (6.12.9 lineage table, row 3).
        """
        if mode in ("ollama", "disabled") or state is None:
            return

        state.last_outcome = outcome.value
        state.last_rate_limit_hits = rate_limit_hits
        state.last_duration_seconds = duration_seconds
        state.observation_count += 1
        state.consecutive_successes = (
            state.consecutive_successes + 1 if outcome is ChunkOutcome.SUCCESS else 0
        )
        if mode == "aimd":
            state.current_thread = next_thread_count(
                outcome, state.current_thread, self._thread_floor(engine, provider)
            )
        # mode == "claude": current_thread khong doi — AIMD bi TAT cho Claude
        # ([UNVERIFIED] S6, Architecture.md 6.12.6; van TAT voi babeldoc,
        # 6.14.5 muc 5) cho toi khi spike xanh; khoa cung o floor du outcome
        # la gi.
        state.updated_at = datetime.now(UTC)
        db_session.add(state)
        await db_session.commit()

    async def _load_or_create_chunks(
        self, job: Job, chunk_plan: list, db_session: AsyncSession
    ) -> list[Chunk]:
        result = await db_session.exec(select(Chunk).where(Chunk.job_id == job.id))
        existing = list(result.all())
        if existing:
            return sorted(existing, key=lambda c: c.chunk_index)

        chunks = [
            Chunk(
                job_id=job.id,
                chunk_index=plan.index,
                page_start=plan.page_start,
                page_end=plan.page_end,
                overlap_start=plan.overlap_start,
                overlap_end=plan.overlap_end,
            )
            for plan in chunk_plan
        ]
        for db_chunk in chunks:
            db_session.add(db_chunk)
        await db_session.commit()
        for db_chunk in chunks:
            await db_session.refresh(db_chunk)
        return chunks

    async def _load_or_create_epub_chunks(
        self, job: Job, chunk_plan: list[EpubChunkPlan], db_session: AsyncSession
    ) -> list[Chunk]:
        """EPUB tuong duong cua `_load_or_create_chunks()` — dung
        `unit_start`/`unit_end` (NULL `page_start`/`page_end`) thay vi trang
        PDF (Architecture.md 6.20.7). BR-CHUNK-05 resume: neu `job` da co
        Chunk row (chay lai sau crash/cancel), TAI SU DUNG nguyen, khong tao
        lai — cung logic voi ban PDF.
        """
        result = await db_session.exec(select(Chunk).where(Chunk.job_id == job.id))
        existing = list(result.all())
        if existing:
            return sorted(existing, key=lambda c: c.chunk_index)

        chunks = [
            Chunk(
                job_id=job.id,
                chunk_index=plan.index,
                unit_start=plan.unit_start,
                unit_end=plan.unit_end,
            )
            for plan in chunk_plan
        ]
        for db_chunk in chunks:
            db_session.add(db_chunk)
        await db_session.commit()
        for db_chunk in chunks:
            await db_session.refresh(db_chunk)
        return chunks

    async def _wants_bilingual(self, job: Job, db_session: AsyncSession) -> bool:
        if not job.batch_id:
            return False
        batch = await db_session.get(Batch, job.batch_id)
        return bool(batch and batch.output_mode == "bilingual")


class BatchOrchestrator:
    """Runs every job in a batch with bounded concurrency, failure isolation,
    and shortest-job-first scheduling (BR-BATCH-01..04).

    Each concurrent job gets its own DB session (via `session_factory`)
    rather than sharing the `db_session` passed into `run_batch` — SQLAlchemy
    `AsyncSession` is not safe for concurrent use by multiple coroutines at
    once, and `asyncio.Semaphore(max_concurrent_files)` still allows several
    jobs in flight simultaneously.
    """

    def __init__(
        self,
        job_orchestrator: JobOrchestrator,
        max_concurrent_files: int | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._job_orchestrator = job_orchestrator
        settings = settings or get_settings()
        self._settings = settings
        self._max_concurrent_files = max_concurrent_files or settings.max_concurrent_files
        self._session_factory = session_factory

    async def run_batch(self, batch_id: str, db_session: AsyncSession) -> BatchResult:
        batch = await db_session.get(Batch, batch_id)
        if batch is None:
            raise BatchNotFoundError(f"Batch {batch_id} khong ton tai")

        result = await db_session.exec(select(Job).where(Job.batch_id == batch_id))
        jobs = list(result.all())

        # BR-BATCH-04: shortest job first.
        jobs.sort(key=lambda j: j.total_pages if j.total_pages is not None else j.file_size)

        batch.status = "processing"
        db_session.add(batch)
        await db_session.commit()

        session_factory = self._session_factory or _default_session_factory()
        semaphore = asyncio.Semaphore(self._max_concurrent_files)

        # Financial Safety Lop 3 for batches (Architecture.md 6.11.4 Lop 3,
        # "Voi BatchOrchestrator: kiem tra tuong tu giua cac file, dung ca
        # batch khi tong actual_cost moi file vuot max_cost_per_batch_usd") —
        # closes RC-3's other gap: `max_concurrent_files` only ever bounded
        # HOW MANY files run at once, never how much money the whole batch
        # could spend. Files already in flight when the cap trips are left to
        # finish (same "graceful, don't force-kill in-flight work" choice as
        # the per-job cancel/cost_capped flows) — only files that have not
        # started yet are skipped.
        batch_cap = self._settings.max_cost_per_batch_usd
        cost_cap_enabled = self._settings.cost_cap_enabled
        spent = {"total": 0.0}
        spent_lock = asyncio.Lock()

        async def _run_one(job: Job) -> JobResult:
            async with semaphore, session_factory() as job_session:
                async with spent_lock:
                    already_capped = cost_cap_enabled and spent["total"] > batch_cap

                if already_capped:
                    capped_job = await job_session.get(Job, job.id)
                    message = (
                        f"Batch dung o file nay: tong chi phi cac file truoc "
                        f"${spent['total']:.2f} da vuot tran batch ${batch_cap:.2f}. "
                        "File nay chua chay — tang tran trong Settings roi retry job "
                        "nay rieng le neu muon tiep tuc."
                    )
                    if capped_job is not None:
                        capped_job.status = "cost_capped"
                        capped_job.error_message = message
                        # US-19/BR-HIST-01/02, Architecture.md 6.17.2 — job
                        # nay chua bao gio vao run_job() (batch da vuot tran
                        # TRUOC khi no bat dau), nhung day van la 1 trang thai
                        # KET THUC that su cho hang Lich su.
                        capped_job.finished_at = datetime.now(UTC)
                        job_session.add(capped_job)
                        await job_session.commit()
                    return JobResult(
                        job_id=job.id,
                        status="cost_capped",
                        output_path=None,
                        bilingual_path=None,
                        actual_cost=0.0,
                        error_message=message,
                    )

                try:
                    result = await self._job_orchestrator.run_job(job.id, job_session)
                except Exception as exc:  # noqa: BLE001 — BR-BATCH-01 failure isolation
                    logger.warning("Job %s failed in batch %s: %s", job.id, batch_id, exc)
                    failed_job = await job_session.get(Job, job.id)
                    if failed_job is not None:
                        failed_job.status = "failed"
                        failed_job.error_message = str(exc)
                        # US-19/BR-HIST-01/02, Architecture.md 6.17.2 — nhanh
                        # nay bat loi ma run_job() TU NO khong bat duoc (BR-
                        # BATCH-01 failure isolation), nen phai tu gan
                        # finished_at o day, khong the tin run_job() da lam.
                        failed_job.finished_at = datetime.now(UTC)
                        job_session.add(failed_job)
                        await job_session.commit()
                    result = JobResult(
                        job_id=job.id,
                        status="failed",
                        output_path=None,
                        bilingual_path=None,
                        actual_cost=None,
                        error_message=str(exc),
                    )

                async with spent_lock:
                    spent["total"] += result.actual_cost or 0.0
                return result

        job_results = list(await asyncio.gather(*(_run_one(job) for job in jobs)))

        completed = sum(1 for r in job_results if r.status == "completed")
        failed = sum(1 for r in job_results if r.status == "failed")

        batch.completed_files = completed
        batch.failed_files = failed
        batch.status = "completed"
        db_session.add(batch)
        await db_session.commit()

        return BatchResult(
            batch_id=batch.id,
            completed=completed,
            failed=failed,
            total=len(jobs),
            job_results=job_results,
        )


def _default_session_factory() -> async_sessionmaker[AsyncSession]:
    from src.models.database import get_session_factory

    return get_session_factory()
