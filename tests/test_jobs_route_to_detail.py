"""US-19 (Architecture.md 6.17.3): `_to_detail()` (src/api/routes/jobs.py) —
maps `Job` -> `JobDetail`, including the new `total_pages`/`finished_at`/
`duration_seconds` fields. Pure-function unit tests (no DB, no orchestrator)
so the "job dang chay -> response van hop le, khong co finished_at" case
(BR-HIST-02) can be exercised directly, without needing to freeze a real job
mid-run (not observable from outside `JobOrchestrator.run_job()`'s single
`await`, see tests/integration/test_job_history_finished_at.py's note).
"""

from datetime import UTC, datetime, timedelta

from src.api.routes.jobs import _to_detail
from src.models.job import Job

_OCR_THRESHOLD = 0.85


def _make_job(**overrides) -> Job:
    created_at = overrides.pop("created_at", datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC))
    defaults = {
        "filename": "book.pdf",
        "file_path": "/data/uploads/book.pdf",
        "file_size": 1024,
        "file_hash": "deadbeef",
        "file_type": "pdf_digital",
        "model": "deepseek",
        "created_at": created_at,
        "updated_at": created_at,
    }
    defaults.update(overrides)
    return Job(**defaults)


# --- (e) total_pages truyen thang qua response ------------------------------


def test_completed_job_response_has_correct_total_pages() -> None:
    job = _make_job(status="completed", total_pages=273)
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.total_pages == 273


def test_epub_job_with_null_total_pages_shows_none_not_error() -> None:
    """AC US-19: `total_pages` NULL (vd EPUB, chua co logic dem trang o dot
    nay) phai ra `None` trong response, khong duoc lam JobDetail construction
    that bai.
    """
    job = _make_job(status="completed", total_pages=None)
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.total_pages is None


# --- BR-HIST-01: duration = finished_at - created_at, khong dung started_at -


def test_completed_job_duration_uses_created_at_not_started_at() -> None:
    created_at = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
    started_at = created_at + timedelta(minutes=5)  # OCR delay before started_at is set
    finished_at = created_at + timedelta(minutes=20)
    job = _make_job(
        status="completed",
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        completed_at=finished_at,
    )
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.duration_seconds == 20 * 60
    assert detail.duration_seconds != (finished_at - started_at).total_seconds()


def test_failed_job_early_chunk_duration_is_not_zero() -> None:
    """6.17.1's exact concern: a job that failed on chunk 0 after running for
    a while must NOT report ~0s just because some OTHER field (`updated_at`)
    never moved. `finished_at` is what `_to_detail()` must use.
    """
    created_at = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
    finished_at = created_at + timedelta(minutes=18)
    job = _make_job(
        status="failed",
        created_at=created_at,
        updated_at=created_at,  # simulates 6.17.1 H-02/H-03: updated_at never moved
        finished_at=finished_at,
    )
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.duration_seconds == 18 * 60


def test_cancelled_job_duration_uses_finished_at() -> None:
    created_at = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
    finished_at = created_at + timedelta(minutes=7)
    job = _make_job(status="cancelled", created_at=created_at, finished_at=finished_at)
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.duration_seconds == 7 * 60


def test_cost_capped_job_duration_uses_finished_at() -> None:
    created_at = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
    finished_at = created_at + timedelta(minutes=3)
    job = _make_job(status="cost_capped", created_at=created_at, finished_at=finished_at)
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.duration_seconds == 3 * 60


# --- (d) job dang chay: response hop le, duration_seconds = None -----------


def test_in_progress_job_has_no_duration_and_no_finished_at() -> None:
    created_at = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
    for status in ("queued", "chunking", "translating", "parsing", "merging"):
        job = _make_job(status=status, created_at=created_at, finished_at=None, total_pages=100)
        detail = _to_detail(job, _OCR_THRESHOLD)
        assert detail.finished_at is None, status
        assert detail.duration_seconds is None, status
        # Response construction itself must not raise (Pydantic validation ok).
        assert detail.status == status


# --- EC-19.1: hang cu truoc migration (finished_at NULL) -------------------


def test_legacy_completed_job_without_finished_at_falls_back_to_completed_at() -> None:
    """Hang DB tu truoc khi cot `finished_at` ton tai: `finished_at` la NULL
    nhung `completed_at` (cot cu) van co gia tri that — fallback phai dung
    no, KHONG hien "-" mot cach khong can thiet.
    """
    created_at = datetime(2026, 9, 1, 8, 0, 0, tzinfo=UTC)
    completed_at = created_at + timedelta(minutes=12)
    job = _make_job(
        status="completed",
        created_at=created_at,
        finished_at=None,
        completed_at=completed_at,
    )
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.duration_seconds == 12 * 60


def test_legacy_failed_job_without_finished_at_or_completed_at_shows_none() -> None:
    """EC-19.1: hang cu, terminal (`failed`), CA `finished_at` LAN
    `completed_at` deu NULL (that vao thoi diem chua co field nao trong ca 2)
    -> duration phai la `None` ("-" o UI) — KHONG duoc doan bang `updated_at`
    (6.17.2, ro rang cam trong Architecture.md).
    """
    created_at = datetime(2026, 9, 1, 8, 0, 0, tzinfo=UTC)
    job = _make_job(
        status="failed",
        created_at=created_at,
        updated_at=created_at + timedelta(minutes=99),  # must be ignored
        finished_at=None,
        completed_at=None,
    )
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.duration_seconds is None


# === S7 — dich FR->VI (Architecture.md §6.26 mo rong pham vi, 2026-09-16) ==
# UI (web/index.html, web/history.html) doc `source_lang` qua JobDetail —
# field nay phai duoc serialize dung tu Job.


def test_job_detail_passes_through_source_lang_fr() -> None:
    job = _make_job(source_lang="fr")
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.source_lang == "fr"


def test_job_detail_passes_through_source_lang_none() -> None:
    """Job cu truoc S7 (cot moi, NULL) -> API tra ve None, UI coi nhu EN->VI
    (deny-by-default, khong crash)."""
    job = _make_job(source_lang=None)
    detail = _to_detail(job, _OCR_THRESHOLD)
    assert detail.source_lang is None
