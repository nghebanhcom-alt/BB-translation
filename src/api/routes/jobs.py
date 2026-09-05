"""Job/Batch HTTP API (Architecture.md section 5.1, US-01/02/07/09/12/14).

Wires the HTTP layer onto `JobOrchestrator`/`BatchOrchestrator`
(src/core/job_orchestrator.py), which existed since Increment 4 but had no
endpoint calling them until this increment.

**Background execution decision** (see docs/CHANGELOG.md "Increment 5" for
the full rationale): jobs are scheduled with `asyncio.create_task()`, not
FastAPI `BackgroundTasks`. A translation job can run for many minutes
(Architecture.md 9.1: "PDF born-digital 100 trang: ~5-10 phut"), and
`BackgroundTasks` ties task lifetime to the request/response object that
created it — nothing else in the app can observe or reason about it once the
response is sent. `asyncio.create_task()` gives a task we can hold a
reference to (`_background_tasks`, to survive Python's "task may be
garbage-collected mid-flight" pitfall) independent of any request, which
matches a job outliving the HTTP call that started it.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import func, select

from src.api.deps import SessionDep
from src.api.routes.upload import UploadNotFoundError, resolve_upload
from src.api.websocket import connection_manager
from src.core.config import Settings, get_effective_settings
from src.core.cost_gate import check_cap, estimate_translation_cost, gate_error_detail
from src.core.job_orchestrator import BatchOrchestrator, JobOrchestrator
from src.core.ocr_warning import build_ocr_warning
from src.models.batch import Batch
from src.models.database import get_session_factory
from src.models.job import Job
from src.services.mineru_runner import MinerURunner
from src.services.pdf2zh_service_map import Pdf2zhServiceMapper, UnsupportedForPdfPipelineError
from src.services.provider_factory import ProviderConfigError, ProviderFactory, UnknownProviderError

logger = logging.getLogger(__name__)

router = APIRouter()

_PDF_FILE_TYPES = {"pdf_digital", "pdf_scan"}
_OUTPUT_MODE_MAP = {"monolingual": "vi_only", "bilingual": "bilingual"}

#: Holds references to in-flight background tasks so they are never garbage
#: collected mid-run (a bare `asyncio.create_task()` result with nothing
#: keeping it alive can be collected before it finishes — a well-known
#: asyncio footgun).
_background_tasks: set[asyncio.Task] = set()


def _schedule_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# === Request/response models (never expose the SQLModel Job/Batch directly) ===


class JobCreateRequest(BaseModel):
    file_id: str
    job_type: str = "translate"  # translate | parse_only
    provider: str | None = None
    output_mode: str = "monolingual"  # monolingual | bilingual
    glossary_project_id: str | None = None
    # AC-12.2 (Bug #3 fix, QA Round 1): the client sets this to `True` to
    # proceed with a fresh translation after the user has already been shown
    # `duplicate_of` on a prior call and chosen "dịch lại" over the cached
    # result.
    force: bool = False
    # Architecture.md 6.11.4 Lop 2: explicit opt-in to bypass the pre-flight
    # cost gate for THIS request only — never a remembered/default choice
    # (the frontend must never persist this across jobs).
    confirm_cost: bool = False


class DuplicateJobInfo(BaseModel):
    job_id: str
    completed_at: datetime


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    # AC-12.2 (Bug #3 fix, QA Round 1): populated instead of creating a new
    # Job row when `file_id` hashes to a file already translated to
    # completion. `status` is "duplicate_found" in that case and `job_id`
    # points at the EXISTING completed job (so a client that only reads
    # `job_id`/`status`, ignoring the new field, still gets something
    # usable) rather than a newly created one.
    duplicate_of: DuplicateJobInfo | None = None


class BatchCreateRequest(BaseModel):
    file_ids: list[str]
    job_type: str = "translate"
    provider: str | None = None
    output_mode: str = "monolingual"
    glossary_project_id: str | None = None
    # Architecture.md 6.11.4 Lop 2 — same explicit, one-shot opt-in as
    # `JobCreateRequest.confirm_cost`, applied to the whole-batch cap.
    confirm_cost: bool = False


class BatchCreateResponse(BaseModel):
    batch_id: str
    job_ids: list[str]
    status: str


class JobDetail(BaseModel):
    id: str
    batch_id: str | None
    filename: str
    file_type: str
    job_type: str
    model: str
    status: str
    progress_percent: float
    current_chunk: int | None
    total_chunks: int | None
    cost_source: str
    estimated_cost: float | None
    actual_cost: float | None
    error_message: str | None
    output_path: str | None
    bilingual_path: str | None
    created_at: datetime
    updated_at: datetime
    # Bug #5 fix (Architecture.md 6.10.6) — backward-compatible, tat ca optional.
    ocr_confidence: float | None = None
    ocr_dropped_spans: int | None = None
    ocr_warning: str | None = None  # chi khac None khi confidence < ocr_confidence_threshold
    # Increment 6 (Nhiem vu 3): True tu luc user bam "Dung" cho toi khi
    # JobOrchestrator thuc su dat status="cancelled" sau chunk hien tai —
    # frontend dung field nay de hien "Dang dung...".
    cancel_requested: bool = False


class JobListResponse(BaseModel):
    jobs: list[JobDetail]
    total: int
    limit: int
    offset: int


class RetryRequest(BaseModel):
    # Architecture.md 6.11.4 Lop 2 — retry must go through the same gate as
    # job creation (explicitly called out: "Retry cung phai qua gate"); this
    # is the same one-shot opt-in as `JobCreateRequest.confirm_cost`.
    confirm_cost: bool = False


class RetryResponse(BaseModel):
    job_id: str
    status: str


class CancelResponse(BaseModel):
    job_id: str
    status: str
    cancel_requested: bool


class CostEstimateResponse(BaseModel):
    total_pages: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    provider_name: str
    cost_source: str
    # Architecture.md 6.11.4 Lop 0 point 3: "hien ro so segment uoc tinh
    # (khong chi so trang)" — the number the team and the user both failed to
    # picture before the $6.50 incident ("moi doan van la 1 request LLM rieng").
    estimated_segment_count: int = 0
    # Lop 0 point 2: UI must show a RANGE, not a single number
    # ("$X (estimated)" was the misleading label before this section).
    estimated_cost_usd_high: float = 0.0


class EstimateRequest(BaseModel):
    """POST /api/estimate (Nhiem vu 1a): xem chi phi TRUOC KHI tao Job that.

    Root cause bug goc: `estimateCost()` phia frontend truoc day goi
    `createJob()` khi file chua co job — tao 1 `Job` row that va trigger
    `asyncio.create_task()` dich that ngay lap tuc (xem `create_job()` o tren)
    chi de xem uoc tinh chi phi, vi pham PRD R-01 ("hien thi estimated cost
    TRUOC KHI dich"). Endpoint nay dung `estimate_job_cost_v2()`
    (src/core/cost_estimator.py, Architecture.md 6.11.4) qua
    `src/core/cost_gate.py::estimate_translation_cost()`, nhung KHONG dam vao
    `JobOrchestrator`/tao `Job`/`Batch` row nao ca.
    """

    file_id: str
    provider: str | None = None
    #: Nhan de giu API shape doi xung voi POST /api/jobs, nhung khong anh
    #: huong toi so tien uoc tinh (cost chi phu thuoc total_pages + provider,
    #: khong phu thuoc output_mode) — chua dung toi trong `estimate_cost()`.
    output_mode: str = "monolingual"
    #: Architecture.md 6.11.4 Lop 1 point 2: scopes the glossary filter used
    #: to measure `prompt_overhead_chars` — a project glossary can be much
    #: bigger than global, so omitting this would silently under-estimate
    #: for any file meant to join an existing glossary_project_id.
    glossary_project_id: str | None = None


def _to_detail(job: Job, ocr_confidence_threshold: float) -> JobDetail:
    # 1 nguon su that voi WebSocket `ocr_warning` (src/core/job_orchestrator.py
    # `_emit_ocr_warning_if_low`) — ca hai goi cung `build_ocr_warning()`.
    ocr_warning = build_ocr_warning(
        job.ocr_confidence, job.ocr_dropped_spans, ocr_confidence_threshold
    )
    return JobDetail(
        id=job.id,
        batch_id=job.batch_id,
        filename=job.filename,
        file_type=job.file_type,
        job_type=job.job_type,
        model=job.model,
        status=job.status,
        progress_percent=round(job.progress * 100, 1),
        current_chunk=job.current_chunk,
        total_chunks=job.total_chunks,
        cost_source=job.cost_source,
        estimated_cost=job.estimated_cost,
        actual_cost=job.actual_cost,
        error_message=job.error_message,
        output_path=job.output_path,
        bilingual_path=job.bilingual_path,
        created_at=job.created_at,
        updated_at=job.updated_at,
        ocr_confidence=job.ocr_confidence,
        ocr_dropped_spans=job.ocr_dropped_spans,
        ocr_warning=ocr_warning,
        cancel_requested=job.cancel_requested,
    )


async def _reject_deepl_for_pdf(job_type: str, provider: str, file_type: str) -> None:
    """US-14 / BR-PROVIDER-01 / Architecture.md 6.6.7 #1: fail at the API
    layer, before a `Job` row (or any subprocess) exists, when translate +
    DeepL + PDF are combined — reuses `Pdf2zhServiceMapper` so the rejection
    reason is defined in exactly one place (src/services/pdf2zh_service_map.py).
    """
    if job_type != "translate" or file_type not in _PDF_FILE_TYPES:
        return
    from src.core.config import get_settings

    try:
        Pdf2zhServiceMapper().map(provider, get_settings())
    except UnsupportedForPdfPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_provider_or_400(provider_name: str, settings: Settings):
    try:
        return ProviderFactory.create(provider_name, settings)
    except (UnknownProviderError, ProviderConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _enforce_cost_gate(
    session: SessionDep,
    file_path: str,
    provider,
    settings: Settings,
    batch_id: str | None,
    confirm_cost: bool,
    scope: str,
    job_cap_override: float | None = None,
):
    """Architecture.md 6.11.4 Lop 2 pre-flight gate — call BEFORE creating any
    `Job`/`Batch` row or scheduling `JobOrchestrator`/`BatchOrchestrator`.
    Raises HTTP 402 (never creates anything) unless the estimate is under cap
    or the caller explicitly opted in with `confirm_cost=True` for this one
    call (RC-3 fix: no cap existed anywhere before this).
    """
    detailed = await estimate_translation_cost(
        Path(file_path),
        provider,
        session,
        batch_id,
        settings.max_glossary_entries_in_prompt,
    )
    cap = job_cap_override if job_cap_override is not None else settings.max_cost_per_job_usd
    result = check_cap(detailed.estimate, cap, settings)

    if result.exceeded and not confirm_cost:
        raise HTTPException(status_code=402, detail=gate_error_detail(result, scope))

    if result.exceeded and confirm_cost:
        # Explicit bypass — logged, never silent (Architecture.md 6.11.4 Lop 2:
        # "day la opt-in tuong minh cho tung job ... va khong duoc phep 'nho'
        # lua chon nay cho job sau").
        logger.warning(
            "Cost gate BYPASSED (confirm_cost=true) for %s: estimated $%.2f > cap $%.2f (%s)",
            file_path,
            detailed.estimate.estimated_cost_usd,
            cap,
            scope,
        )

    return detailed


async def _find_completed_duplicate(session: SessionDep, file_hash: str) -> Job | None:
    """AC-12.2 (Bug #3 fix, QA Round 1): most recent `completed` job whose
    upload hashed to the same content, if any. Checked in `POST /api/jobs`
    (not `POST /api/upload`) because the hash alone isn't a duplicate
    translation until a job actually finished against it — the same file
    re-uploaded while a previous job is still `translating`/`failed` should
    not block a new attempt.
    """
    statement = (
        select(Job)
        .where(Job.file_hash == file_hash, Job.status == "completed")
        .order_by(Job.completed_at.desc())
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first()


async def _resolve_batch(
    session: SessionDep,
    glossary_project_id: str | None,
    total_files: int,
    output_mode: str,
    provider: str,
) -> Batch:
    """`JobOrchestrator` scopes project glossary lookups to `job.batch_id`
    (Architecture.md 3.4: scope `project:{batch_id}`) and reads
    `Batch.output_mode` to decide on bilingual output (`_wants_bilingual()`)
    — there is no separate `glossary_project_id`/output-mode field on `Job`
    itself. So a standalone `POST /api/jobs` call still needs a `Batch` row
    to carry those two settings; `glossary_project_id`, when given, must name
    an existing batch to attach to instead of creating a new one (this is
    the deviation documented in docs/CHANGELOG.md "Increment 5" — no new DB
    schema was added for it, reusing the existing `Batch` concept instead).
    """
    if glossary_project_id:
        batch = await session.get(Batch, glossary_project_id)
        if batch is None:
            raise HTTPException(
                status_code=404, detail=f"glossary_project_id '{glossary_project_id}' khong ton tai"
            )
        return batch

    batch = Batch(
        total_files=total_files,
        output_mode=_OUTPUT_MODE_MAP.get(output_mode, "vi_only"),
        model=provider,
    )
    session.add(batch)
    await session.commit()
    await session.refresh(batch)
    return batch


def _build_mineru_runner(settings: Settings) -> MinerURunner:
    """Bug #2 fix (QA Round 1): `JobOrchestrator` has supported OCR via
    `mineru_runner` since Increment 4 (`job_orchestrator.py`: `file_type ==
    pdf_scan and self._mineru_runner is not None`), but this API layer never
    constructed one to pass in — every `pdf_scan` job silently skipped OCR
    and went straight to `pdf2zh` with no text layer, producing an empty/
    garbage translation with no warning. The bug was a missing wire, not a
    missing branch: the "if pdf_scan, run OCR first" logic already existed
    and only needed a real `MinerURunner` injected here.
    """
    return MinerURunner(
        base_url=settings.mineru_endpoint,
        task_timeout_seconds=settings.mineru_task_timeout_seconds,
        request_timeout_seconds=settings.mineru_request_timeout_seconds,
    )


async def _run_job_background(job_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        settings = await get_effective_settings(session)
        orchestrator = JobOrchestrator(
            settings=settings,
            mineru_runner=_build_mineru_runner(settings),
            progress_broadcaster=connection_manager.broadcast_progress,
        )
        try:
            await orchestrator.run_job(job_id, session)
        except Exception as exc:  # last-resort guard for the background task
            logger.exception("Job %s crashed in background task", job_id)
            job = await session.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)
                session.add(job)
                await session.commit()


async def _run_batch_background(batch_id: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        settings = await get_effective_settings(session)
        job_orchestrator = JobOrchestrator(
            settings=settings,
            mineru_runner=_build_mineru_runner(settings),
            progress_broadcaster=connection_manager.broadcast_progress,
        )
        batch_orchestrator = BatchOrchestrator(
            job_orchestrator, session_factory=session_factory, settings=settings
        )
        try:
            await batch_orchestrator.run_batch(batch_id, session)
        except Exception:  # last-resort guard for the background task
            logger.exception("Batch %s crashed in background task", batch_id)


def _mark_parse_only_unsupported(job: Job) -> None:
    """`JobOrchestrator.run_job()` (Increment 4) only implements the
    `translate` flow — Markdown parse-only (US-15, Architecture.md 6.8) needs
    its own MinerU-only branch that does not exist yet. Rather than silently
    leaving a `parse_only` job stuck at `status="created"` forever, or
    changing `JobOrchestrator`'s architecture from this increment (out of
    scope — see the "KHONG lam" list), it is marked `failed` immediately with
    a clear reason so `GET /api/jobs/{id}` reports something honest. See
    docs/CHANGELOG.md "Increment 5" — known limitation, not a bug.
    """
    job.status = "failed"
    job.error_message = (
        "job_type=parse_only chua duoc JobOrchestrator ho tro (Increment 5 chi lap API "
        "cho luong translate; Markdown parse-only can 1 nhanh MinerU-only rieng, xem "
        "Architecture.md 6.8 va docs/CHANGELOG.md Increment 5)."
    )


@router.post("", response_model=JobCreateResponse, status_code=202)
async def create_job(
    request: JobCreateRequest, session: SessionDep, response: Response
) -> JobCreateResponse:
    try:
        upload = resolve_upload(request.file_id)
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if request.job_type not in {"translate", "parse_only"}:
        raise HTTPException(
            status_code=400, detail="job_type phai la 'translate' hoac 'parse_only'"
        )

    if request.job_type == "translate" and not request.force:
        duplicate = await _find_completed_duplicate(session, upload.file_hash)
        if duplicate is not None:
            # 200, not the route default 202: no Job was created/scheduled,
            # so "accepted for background processing" would be misleading.
            response.status_code = 200
            return JobCreateResponse(
                job_id=duplicate.id,
                status="duplicate_found",
                duplicate_of=DuplicateJobInfo(
                    job_id=duplicate.id, completed_at=duplicate.completed_at
                ),
            )

    settings = await get_effective_settings(session)
    provider_name = request.provider or settings.default_provider

    await _reject_deepl_for_pdf(request.job_type, provider_name, upload.file_type)

    if request.job_type == "translate":
        provider = _resolve_provider_or_400(provider_name, settings)
        cost_estimate = await _enforce_cost_gate(
            session,
            upload.file_path,
            provider,
            settings,
            request.glossary_project_id,
            request.confirm_cost,
            scope="job nay",
        )

    batch = await _resolve_batch(
        session, request.glossary_project_id, 1, request.output_mode, provider_name
    )

    job = Job(
        batch_id=batch.id,
        filename=upload.filename,
        file_path=upload.file_path,
        file_size=upload.size_bytes,
        file_hash=upload.file_hash,
        file_type=upload.file_type,
        job_type=request.job_type,
        total_pages=upload.page_count,
        model=provider_name,
        estimated_cost=cost_estimate.estimate.estimated_cost_usd
        if request.job_type == "translate"
        else None,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    if request.job_type == "parse_only":
        _mark_parse_only_unsupported(job)
        session.add(job)
        await session.commit()
        return JobCreateResponse(job_id=job.id, status=job.status)

    job.status = "queued"
    session.add(job)
    await session.commit()

    _schedule_background(_run_job_background(job.id))

    return JobCreateResponse(job_id=job.id, status=job.status)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session: SessionDep, status: str | None = None, limit: int = 50, offset: int = 0
) -> JobListResponse:
    count_statement = select(func.count()).select_from(Job)
    list_statement = select(Job).order_by(Job.created_at.desc())
    if status is not None:
        # Increment 6 (Nhiem vu 1b): frontend can khoi phuc danh sach job
        # dang chay/gan day sau khi F5/chuyen tab, can loc theo NHIEU status
        # cung luc (vd "queued,translating,completed") trong 1 lan goi thay
        # vi 1 request/status. 1 status don le (khong co dau phay) van hoat
        # dong y het truoc day.
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            count_statement = count_statement.where(Job.status == statuses[0])
            list_statement = list_statement.where(Job.status == statuses[0])
        elif statuses:
            count_statement = count_statement.where(Job.status.in_(statuses))
            list_statement = list_statement.where(Job.status.in_(statuses))

    total_result = await session.exec(count_statement)
    total = total_result.one()

    result = await session.exec(list_statement.limit(limit).offset(offset))
    settings = await get_effective_settings(session)
    jobs = [_to_detail(job, settings.ocr_confidence_threshold) for job in result.all()]
    return JobListResponse(jobs=jobs, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, session: SessionDep) -> JobDetail:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job khong ton tai")
    settings = await get_effective_settings(session)
    return _to_detail(job, settings.ocr_confidence_threshold)


#: Increment 6 (Nhiem vu 3): retry phai chap nhan ca "cancelled" (job user
#: chu dong dung), khong chi "failed" — cung dua vao co che resumable
#: BR-CHUNK-05 y het nhau (chunk da "completed" duoc skip, chi chay tiep tu
#: chunk dang do). Architecture.md 6.11.4 Lop 3 them "cost_capped" — cung
#: resumable y het, chi khac ly do dung lai.
_RETRYABLE_STATUSES = {"failed", "cancelled", "cost_capped"}


@router.post("/{job_id}/retry", response_model=RetryResponse)
async def retry_job(job_id: str, session: SessionDep, request: RetryRequest | None = None) -> RetryResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job khong ton tai")
    if job.status not in _RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Chi retry duoc job dang 'failed', 'cancelled' hoac 'cost_capped', "
                f"job nay dang '{job.status}'"
            ),
        )
    if job.job_type == "parse_only":
        raise HTTPException(status_code=400, detail="parse_only chua duoc ho tro, khong the retry")

    # Architecture.md 6.11.7 #2 ("POST /api/jobs/{id}/retry chay lai khong
    # qua gate chi phi" — HO, explicitly called out) + 6.11.4 Lop 3 ("retry
    # PHAI di qua lai Lop 2 gate truoc khi resume"): a retry must never be
    # able to bypass the cap that a `cost_capped`/prior gate rejection put in
    # place, or the gate is decorative.
    confirm_cost = request.confirm_cost if request is not None else False
    settings = await get_effective_settings(session)
    provider = _resolve_provider_or_400(job.model, settings)
    await _enforce_cost_gate(
        session,
        job.file_path,
        provider,
        settings,
        job.batch_id,
        confirm_cost,
        scope="retry job nay",
        job_cap_override=job.cost_cap_usd,
    )

    job.status = "queued"
    job.error_message = None
    # Xoa co cancel cu — neu khong, run_job() se doc thay cancel_requested
    # con True tu lan cancel truoc va dung ngay sau chunk dau tien.
    job.cancel_requested = False
    session.add(job)
    await session.commit()

    # BR-CHUNK-05: run_job() resumes from the first non-completed chunk on its own.
    _schedule_background(_run_job_background(job.id))

    return RetryResponse(job_id=job.id, status=job.status)


@router.post("/{job_id}/cancel", response_model=CancelResponse)
async def cancel_job(job_id: str, session: SessionDep) -> CancelResponse:
    """Nhiem vu 3: dat co `cancel_requested`, KHONG dung job ngay lap tuc.
    `JobOrchestrator.run_job()` tu kiem tra co nay SAU MOI chunk hoan thanh
    (graceful cancel, theo dung quyet dinh cua user — khong force-kill giua
    chunk) va dat `status="cancelled"` khi thay co bat.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job khong ton tai")
    if job.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail=f"Job dang '{job.status}', khong the dung (chi dung duoc job dang chay)",
        )

    job.cancel_requested = True
    session.add(job)
    await session.commit()

    return CancelResponse(job_id=job.id, status=job.status, cancel_requested=True)


@router.get("/{job_id}/cost-estimate", response_model=CostEstimateResponse)
async def get_cost_estimate(job_id: str, session: SessionDep) -> CostEstimateResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job khong ton tai")
    if job.file_type == "epub":
        raise HTTPException(
            status_code=400,
            detail="Uoc tinh chi phi cho EPUB chua duoc ho tro (pipeline EPUB chua implement)",
        )
    if job.total_pages is None:
        raise HTTPException(status_code=400, detail="Job chua co total_pages, khong the uoc tinh")

    settings = await get_effective_settings(session)
    provider = _resolve_provider_or_400(job.model, settings)

    # Architecture.md 6.11.4 Lop 1 point 1: this endpoint must route through
    # estimate_job_cost_v2(), not the deprecated estimate_job_cost() (RC-2).
    detailed = await estimate_translation_cost(
        Path(job.file_path),
        provider,
        session,
        job.batch_id,
        settings.max_glossary_entries_in_prompt,
    )
    estimate = detailed.estimate

    job.estimated_cost = estimate.estimated_cost_usd
    session.add(job)
    await session.commit()

    return CostEstimateResponse(
        total_pages=job.total_pages,
        estimated_input_tokens=estimate.estimated_input_tokens,
        estimated_output_tokens=estimate.estimated_output_tokens,
        estimated_cost_usd=estimate.estimated_cost_usd,
        provider_name=estimate.provider_name,
        cost_source=estimate.cost_source,
        estimated_segment_count=detailed.segment_count,
        estimated_cost_usd_high=estimate.estimated_cost_usd * 2.0,
    )


estimate_router = APIRouter()


@estimate_router.post("", response_model=CostEstimateResponse)
async def estimate_cost_without_job(
    request: EstimateRequest, session: SessionDep
) -> CostEstimateResponse:
    try:
        upload = resolve_upload(request.file_id)
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if upload.file_type == "epub":
        raise HTTPException(
            status_code=400,
            detail="Uoc tinh chi phi cho EPUB chua duoc ho tro (pipeline EPUB chua implement)",
        )
    if upload.page_count is None:
        raise HTTPException(
            status_code=400, detail="Khong xac dinh duoc so trang cua file, khong the uoc tinh"
        )

    settings = await get_effective_settings(session)
    provider_name = request.provider or settings.default_provider
    provider = _resolve_provider_or_400(provider_name, settings)

    # Architecture.md 6.11.4 Lop 1 point 1: route through estimate_job_cost_v2()
    # (RC-2 fix), not the deprecated page-count-only estimate_job_cost().
    detailed = await estimate_translation_cost(
        Path(upload.file_path),
        provider,
        session,
        request.glossary_project_id,
        settings.max_glossary_entries_in_prompt,
    )
    estimate = detailed.estimate

    return CostEstimateResponse(
        total_pages=upload.page_count,
        estimated_input_tokens=estimate.estimated_input_tokens,
        estimated_output_tokens=estimate.estimated_output_tokens,
        estimated_cost_usd=estimate.estimated_cost_usd,
        provider_name=estimate.provider_name,
        cost_source=estimate.cost_source,
        estimated_segment_count=detailed.segment_count,
        estimated_cost_usd_high=estimate.estimated_cost_usd * 2.0,
    )


batches_router = APIRouter()


@batches_router.post("", response_model=BatchCreateResponse, status_code=202)
async def create_batch(request: BatchCreateRequest, session: SessionDep) -> BatchCreateResponse:
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="Can it nhat 1 file_id")
    if request.job_type not in {"translate", "parse_only"}:
        raise HTTPException(
            status_code=400, detail="job_type phai la 'translate' hoac 'parse_only'"
        )

    settings = await get_effective_settings(session)
    provider_name = request.provider or settings.default_provider

    uploads = []
    for file_id in request.file_ids:
        try:
            uploads.append(resolve_upload(file_id))
        except UploadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    for upload in uploads:
        await _reject_deepl_for_pdf(request.job_type, provider_name, upload.file_type)

    if request.job_type == "translate":
        # Architecture.md 6.11.4 Lop 2 + 6.11.7 #1: "max_concurrent_files=3
        # gioi han file, KHONG gioi han tien" was flagged as an open hole —
        # the cap here applies to the SUM of every file's estimate, computed
        # BEFORE the first file runs, closing exactly that gap.
        provider = _resolve_provider_or_400(provider_name, settings)
        total_estimated = 0.0
        for upload in uploads:
            detailed = await estimate_translation_cost(
                Path(upload.file_path),
                provider,
                session,
                request.glossary_project_id,
                settings.max_glossary_entries_in_prompt,
            )
            total_estimated += detailed.estimate.estimated_cost_usd

        batch_cap = settings.max_cost_per_batch_usd
        batch_exceeded = settings.cost_cap_enabled and total_estimated > batch_cap
        if batch_exceeded and not request.confirm_cost:
            raise HTTPException(
                status_code=402,
                detail={
                    "detail": (
                        f"Tong chi phi uoc tinh ca batch ${total_estimated:.2f} vuot tran "
                        f"${batch_cap:.2f}. Dat confirm_cost=true de dich du sao, hoac tang "
                        "tran trong Settings."
                    ),
                    "estimated_cost_usd": total_estimated,
                    "cap_usd": batch_cap,
                    "requires_confirmation": True,
                },
            )
        if batch_exceeded and request.confirm_cost:
            logger.warning(
                "Batch cost gate BYPASSED (confirm_cost=true): estimated $%.2f > cap $%.2f",
                total_estimated,
                batch_cap,
            )

    batch = await _resolve_batch(
        session, request.glossary_project_id, len(uploads), request.output_mode, provider_name
    )

    job_ids: list[str] = []
    parse_only_jobs: list[Job] = []
    for upload in uploads:
        job = Job(
            batch_id=batch.id,
            filename=upload.filename,
            file_path=upload.file_path,
            file_size=upload.size_bytes,
            file_hash=upload.file_hash,
            file_type=upload.file_type,
            job_type=request.job_type,
            total_pages=upload.page_count,
            model=provider_name,
        )
        if request.job_type == "parse_only":
            _mark_parse_only_unsupported(job)
            parse_only_jobs.append(job)
        else:
            job.status = "queued"
        session.add(job)
        job_ids.append(job.id)

    await session.commit()

    if request.job_type == "translate":
        _schedule_background(_run_batch_background(batch.id))
        batch_status = "processing"
    else:
        batch.status = "failed"
        batch.failed_files = len(parse_only_jobs)
        session.add(batch)
        await session.commit()
        batch_status = batch.status

    return BatchCreateResponse(batch_id=batch.id, job_ids=job_ids, status=batch_status)
