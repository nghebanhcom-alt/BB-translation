import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class TranslationCache(SQLModel, table=True):
    __tablename__ = "translation_cache"

    id: str = Field(default_factory=_uuid, primary_key=True)
    source_hash: str = Field(unique=True, index=True)
    # SHA-256 cua (source_text + model + glossary_hash)
    source_text: str
    translated_text: str
    model: str
    glossary_hash: str | None = Field(default=None)
    tokens_used: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
