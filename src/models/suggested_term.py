import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class SuggestedTerm(SQLModel, table=True):
    """US-20 "Các từ mới" — Architecture.md §6.18.3 (schema) / §6.18.8 (3
    columns added after Domain Expert review: `match_key`, `ngram_size`,
    `noise_flags`).

    Brand-new table (not a new column on an existing one) so it is created by
    the ordinary `SQLModel.metadata.create_all()` in `src/models/database.py`
    — no `_NEW_NULLABLE_COLUMNS`/`ALTER TABLE` entry needed for this file.
    The 2 extra indexes (unique `(job_id, term_en)`, and `(status,
    rank_score)` for the cross-job "Chờ duyệt" listing) are created via raw
    `CREATE INDEX IF NOT EXISTS` in `init_db()`, same pattern already used
    there for `idx_glossary_entries_term_nocase`.
    """

    __tablename__ = "suggested_terms"

    id: str = Field(default_factory=_uuid, primary_key=True)
    job_id: str = Field(foreign_key="jobs.id", index=True)
    term_en: str
    # Chuẩn hoá dùng để so glossary (Architecture.md §6.18.8 T3) — KHÔNG phải
    # để hiển thị. Xem src/core/glossary_matching.normalize_candidate_key().
    match_key: str
    ngram_size: int
    # CSV cac nhan nghi-nhiem: proper_noun | stopword_middle | fragment_suspect
    # | plural_merged. KHONG phai dieu kien loai bo — chi de UI an mac dinh +
    # demote rank_score (Architecture.md §6.18.8 T4).
    noise_flags: str = Field(default="")
    occurrence_count: int
    rank_score: float
    status: str = Field(default="pending")
    # pending | added | dismissed — KHONG co "rejected" toan cuc, dung
    # BR-TERM-04 (user chot: "Bo qua" chi trong pham vi 1 job).
    suggested_term_vi: str | None = Field(default=None)
    # Chi khac None sau khi user bam "Goi y ban dich" (hanh dong DUY NHAT
    # ton tien trong US-20 — Architecture.md §6.18.4).
    translation_cost_usd: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
