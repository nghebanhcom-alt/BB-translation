import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class Batch(SQLModel, table=True):
    __tablename__ = "batches"

    id: str = Field(default_factory=_uuid, primary_key=True)
    status: str = Field(default="created")
    # created | processing | completed | failed
    total_files: int = Field(default=0)
    completed_files: int = Field(default=0)
    failed_files: int = Field(default=0)
    model: str = Field(default="claude")
    output_mode: str = Field(default="vi_only")
    # vi_only | bilingual
    glossary_scope: str = Field(default="global")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
