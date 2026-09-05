import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class Glossary(SQLModel, table=True):
    __tablename__ = "glossaries"

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    scope: str = Field(default="global")
    # 'global' hoac 'project:{batch_id}'
    description: str | None = Field(default=None)
    entry_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GlossaryEntry(SQLModel, table=True):
    __tablename__ = "glossary_entries"

    id: str = Field(default_factory=_uuid, primary_key=True)
    glossary_id: str = Field(foreign_key="glossaries.id", index=True)
    term_en: str = Field(index=True)
    term_vi: str | None = Field(default=None)
    # NULL hoac "(keep)" = giu nguyen EN
    context_hint: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
