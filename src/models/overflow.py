import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class OverflowReport(SQLModel, table=True):
    __tablename__ = "overflow_reports"

    id: str = Field(default_factory=_uuid, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", index=True)
    page_number: int
    block_index: int
    original_text: str | None = Field(default=None)
    translated_text: str | None = Field(default=None)
    bbox: str | None = Field(default=None)
    # JSON: {x0, y0, x1, y1}
    font_size_original: float | None = Field(default=None)
    font_size_final: float | None = Field(default=None)
    scaling_applied: float | None = Field(default=None)
    still_overflow: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
