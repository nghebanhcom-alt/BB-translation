import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = Field(default_factory=_uuid, primary_key=True)
    batch_id: str | None = Field(default=None, foreign_key="batches.id", index=True)
    filename: str
    file_path: str
    file_size: int
    file_hash: str = Field(index=True)
    file_type: str
    # pdf_digital | pdf_scan | epub
    job_type: str = Field(default="translate")
    # translate | parse_only — section 6.8 Markdown parse-only mode
    total_pages: int | None = Field(default=None)
    total_units: int | None = Field(default=None)
    # Architecture.md 6.20.6 (US-22 buoc 2/3): so don vi dich (doan van/heading/
    # muc list, tu EpubDocument.units) cua 1 job EPUB — thay cho total_pages
    # (vo nghia voi dinh dang reflow, giu NULL cho EPUB dung nhu thiet ke).
    # NULL cho moi job PDF. Cot moi, them qua `_NEW_NULLABLE_COLUMNS`
    # (src/models/database.py) — GIU DU LIEU DB hien co, khong xoa/tao lai.
    status: str = Field(default="created")
    # created | queued | chunking | parsing | translating |
    # post_processing | merging | completed | failed | cancelled | cost_capped
    # ("parsing" was missing from this comment before Bug #EPUB-3 (Architecture.md
    # §E3.2) even though src/core/job_orchestrator.py assigns it — same class of
    # drift as S15-12's missing `parsing` in web/js/app.js. Keep this list in sync.)
    # "cost_capped" (Architecture.md 6.11.4 Lop 3) — the system stopped the
    # job because accumulated `actual_cost` crossed `effective_cap`. NOT
    # "failed" (nothing errored) and NOT "cancelled" (the user didn't ask) —
    # a distinct, non-error, non-user-initiated stop, so UI must show it
    # differently from both. BREAKING SCHEMA CHANGE for `cost_cap_usd` below,
    # same pattern as prior increments — see docs/CHANGELOG.md.
    cost_cap_usd: float | None = Field(default=None)
    # Per-job override for Architecture.md 6.11.4 Lop 2/3's `effective_cap`
    # (`job.cost_cap_usd` if set, else `settings.max_cost_per_job_usd`). Not
    # exposed on any request model yet in this increment — reserved for a
    # future "custom cap for this job" UI; defaults to None (use the global
    # setting) everywhere until then.
    cancel_requested: bool = Field(default=False)
    # Increment 6 (Nhiem vu 3): dat boi POST /api/jobs/{id}/cancel, doc boi
    # JobOrchestrator.run_job() sau MOI chunk hoan thanh — dung "graceful
    # cancel" (khong force-kill giua chunk), tan dung co che resumable san co
    # (BR-CHUNK-05). BREAKING SCHEMA CHANGE — xem docs/CHANGELOG.md Increment 6.
    progress: float = Field(default=0.0)
    # 0.0 -> 1.0. New in Increment 4: current_chunk/total_chunks — needed by
    # ProgressTracker (US-07: "chunk hien tai/tong") on top of the scalar
    # `progress` ratio already in Architecture.md section 4.2. See
    # docs/CHANGELOG.md "Increment 4" for the rationale.
    current_chunk: int | None = Field(default=None)
    total_chunks: int | None = Field(default=None)
    error_message: str | None = Field(default=None)
    output_path: str | None = Field(default=None)
    bilingual_path: str | None = Field(default=None)
    model: str
    estimated_cost: float | None = Field(default=None)
    actual_cost: float | None = Field(default=None)
    cost_source: str = Field(default="estimated")
    # 'estimated' | 'metered' — v1.0 khong lay duoc token usage that tu pdf2zh (khong
    # xuat ra stdout/stderr), nen actual_cost luon la uoc luong tu do dai text cho den
    # khi metering proxy (Architecture.md 6.6.6 v1.1, chua implement) duoc bat.
    # BREAKING SCHEMA CHANGE — xem docs/CHANGELOG.md "Increment 4 — Fix Round 1".
    ocr_confidence: float | None = Field(default=None)
    # Bug #5 fix (Architecture.md 6.10.7) — BREAKING SCHEMA CHANGE, xem docs/CHANGELOG.md:
    # SQLModel.metadata.create_all() khong them cot vao bang da ton tai, DB dev cu phai
    # xoa/tao lai.
    ocr_bridge_path: str | None = Field(default=None)
    # duong dan data/processing/{job_id}/ocr_bridge/searchable.pdf (resumable, BR-CHUNK-05)
    ocr_dropped_spans: int | None = Field(default=None)
    # tu OcrQuality.dropped_span_count — dung cho ocr_warning (US-11/AC-11.2)
    chunk_size_used: int | None = Field(default=None)
    # Architecture.md 6.12.7 — chunk_size chot 1 LAN cho ca job, ghi lai de
    # resume dung so cu (BR-CHUNK-05). Chi them cot o task nay; logic gan gia
    # tri cold-start/warm cho field nay la task 6.12.7 rieng, NGOAI PHAM VI —
    # None la gia tri mac dinh hop le cho toi khi task do implement.
    parse_method: str | None = Field(default=None)
    # 'txt' | 'ocr' — CHI co y nghia khi job_type=parse_only (Architecture.md
    # 6.21.3). Luu gia tri DA RESOLVE THAT su dung (cung pattern voi
    # chunk_size_used o tren): "auto" (request-level, JobCreateRequest o
    # src/api/routes/jobs.py) khong bao gio duoc ghi vao cot nay — resolve
    # theo file_type xay ra 1 LAN, hoac o create_job() luc tao Job (duong di
    # binh thuong), hoac trong JobOrchestrator.run_parse_only() lam fallback
    # cho Job row cu/tao truc tiep khong qua API (vd test) chua co gia tri.
    # Ghi lai 1 lan roi giu nguyen qua cac lan retry (BR-CHUNK-05-style) —
    # user ep "ocr" cho 1 file pdf_digital khong the tu doi lai "txt" giua
    # chung job do retry.
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    # Architecture.md 6.17.2 (US-19, BR-HIST-01/02) — moc KET THUC cua job o
    # MOI trang thai cuoi (completed | failed | cancelled | cost_capped),
    # rieng biet voi `completed_at` (chi nghia "hoan tat THANH CONG", van la
    # du lieu nghiep vu cua duplicate-detection AC-12.2 + hau to ten file tai
    # ve — KHONG duoc nap them nghia moi vao no, dung loai "troi ngu nghia
    # im lang" Protocol 6 ton tai de chan). Cot moi, them qua
    # `_NEW_NULLABLE_COLUMNS` (src/models/database.py) — GIU DU LIEU DB hien
    # co, khong xoa/tao lai.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
