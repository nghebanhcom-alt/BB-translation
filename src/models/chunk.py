import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"

    id: str = Field(default_factory=_uuid, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", index=True)
    chunk_index: int
    # Architecture.md 6.20.7 (US-22 buoc 2/3): page_start/page_end doi thanh
    # NULLABLE (NULL cho chunk EPUB) thay vi muon nghia sang chi so unit —
    # "cung 1 bien, hai y nghia" da la nguyen nhan Bug #5 va RC-4 cua
    # cost_source. unit_start/unit_end la 2 cot MOI (NULL cho chunk PDF).
    # Rebuild bang qua `_migrate_chunks_unit_columns()`
    # (src/models/database.py) cho DB dev hien co — GIU DU LIEU, khong xoa.
    page_start: int | None = Field(default=None)
    page_end: int | None = Field(default=None)
    unit_start: int | None = Field(default=None)
    # chi so unit TOAN SACH, 0-based, INCLUSIVE (EpubChunkPlan.unit_start)
    unit_end: int | None = Field(default=None)
    # INCLUSIVE (EpubChunkPlan.unit_end)
    overlap_start: int | None = Field(default=None)
    overlap_end: int | None = Field(default=None)
    status: str = Field(default="pending")
    # pending | translating | post_processing | completed | failed
    retry_count: int = Field(default=0)
    error_message: str | None = Field(default=None)
    output_path: str | None = Field(default=None)
    api_tokens_used: int | None = Field(default=None)
    api_cost: float | None = Field(default=None)
    thread_used: int | None = Field(default=None)
    # `--thread` value passed to THIS chunk's pdf2zh call (Architecture.md
    # 6.12.4/6.12.9 R6-01 lineage) — written BEFORE translate_pages() runs, so
    # a crash mid-chunk still leaves the value that was actually attempted.
    rate_limit_hits: int | None = Field(default=None)
    # Copied from Pdf2zhResult/Pdf2zhTimeoutError/Pdf2zhError.rate_limit_hits
    # AFTER the call (Architecture.md 6.12.8) — the same count the AIMD
    # controller used to update ConcurrencyState for this chunk.
    # BL-10 (Architecture.md 6.23.5). 'estimated' | 'metered' — 'metered' CHI
    # khi con so o api_tokens_used/api_cost la do that (babeldoc stdout parse
    # hoac TranslationResult EPUB), khong phai uoc luong tu do dai van ban.
    # `server_default` (khac vai tro voi `default` cua Field) BAT BUOC o day:
    # `_migrate_chunks_unit_columns()` (src/models/database.py) rebuild bang
    # `chunks` bang `create_all()` roi INSERT SELECT DUNG danh sach cot CU
    # (khong co `cost_source`, cot moi hoan toan) — thieu server_default,
    # SQLite se raise NOT NULL constraint failed vi INSERT khong dien gia tri
    # cho cot nay va khong co DEFAULT o muc SQL de tu dien.
    cost_source: str = Field(default="estimated", sa_column_kwargs={"server_default": "estimated"})
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
