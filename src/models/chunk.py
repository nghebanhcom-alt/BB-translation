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
    page_start: int
    page_end: int
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
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
