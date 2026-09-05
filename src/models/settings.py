from datetime import datetime

from sqlmodel import Field, SQLModel


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Default settings (seeded on first init_db, see src/models/database.py):
# max_concurrent_files: 3
# default_model: claude
# default_chunk_size: 40
# font_shrink_max_percent: 20
# font_condensed_min: 85
# api_keys: {claude: "", openai: "", deepl: ""}  (encrypted)
