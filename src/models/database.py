from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel, text
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings

# Import models so their tables register on SQLModel.metadata before create_all.
from src.models import (  # noqa: F401
    Batch,
    Chunk,
    ConcurrencyState,
    Glossary,
    GlossaryEntry,
    Job,
    LayoutQaFinding,
    OverflowReport,
    Setting,
    SuggestedTerm,
    TranslationCache,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


# Architecture.md 6.12.8: new columns (nullable OR with a constant DEFAULT,
# BL-10 6.23.9) on tables that already exist in a dev DB. SQLite has no
# "ADD COLUMN IF NOT EXISTS", and
# `SQLModel.metadata.create_all()` never alters an existing table (same
# limitation noted in `src/models/job.py` for `ocr_confidence`/`ocr_bridge_path`
# — those increments told the dev to just delete the dev DB). 6.12.8 asks for
# an actual `ALTER TABLE` this time, so this stays additive/idempotent instead.
_NEW_NULLABLE_COLUMNS: list[tuple[str, str, str]] = [
    ("chunks", "thread_used", "INTEGER"),
    ("chunks", "rate_limit_hits", "INTEGER"),
    ("jobs", "chunk_size_used", "INTEGER"),
    # Architecture.md 6.21.3 (US-15 parse_method override): 'txt'/'ocr' da
    # resolve, khong bao gio 'auto' — xem src/models/job.py.
    ("jobs", "parse_method", "TEXT"),
    # Architecture.md 6.17.2 (US-19, BR-HIST-01/02): moc KET THUC chung cho
    # MOI trang thai cuoi cua job — xem docstring day du o src/models/job.py.
    ("jobs", "finished_at", "DATETIME"),
    # Architecture.md 6.20.6 (US-22 buoc 2/3) — xem docstring day du o
    # src/models/job.py. `chunks.unit_start`/`unit_end` KHONG o day — chung
    # can `_migrate_chunks_unit_columns()` duoi day (rebuild bang, vi
    # page_start/page_end doi NOT NULL -> nullable, SQLite khong ALTER duoc
    # constraint nay bang ADD COLUMN don thuan).
    ("jobs", "total_units", "INTEGER"),
    # BL-10 (Architecture.md 6.23.9). SQLite cho phep `ADD COLUMN NOT NULL`
    # khi co DEFAULT hang — cot moi o list nay: nullable HOAC co DEFAULT hang.
    ("chunks", "cost_source", "TEXT NOT NULL DEFAULT 'estimated'"),
]


async def _add_missing_columns(conn) -> None:
    for table, column, sql_type in _NEW_NULLABLE_COLUMNS:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing_columns = {row[1] for row in result.all()}
        if column not in existing_columns:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


async def _migrate_concurrency_state_engine_key(conn) -> None:
    """Architecture.md 6.14.5: `ConcurrencyState`'s primary key gains `engine`
    (was `(provider, model)`, now `(engine, provider, model)`). Unlike
    `_add_missing_columns` above, this is NOT a plain `ALTER TABLE ADD COLUMN`
    — a composite PRIMARY KEY change needs SQLite's standard "rebuild the
    table" pattern, because SQLite cannot alter a PK in place. Old rows are
    migrated with `engine='pdf2zh'` (the only engine that ever wrote this
    table before this increment). Idempotent: a no-op once the `engine`
    column already exists (including a brand-new DB, where `create_all`
    above already built the table with the new schema directly).
    """
    result = await conn.execute(text("PRAGMA table_info(concurrency_state)"))
    columns = {row[1] for row in result.all()}
    if not columns or "engine" in columns:
        return

    await conn.execute(text("ALTER TABLE concurrency_state RENAME TO concurrency_state_old"))
    # Re-run create_all so the NEW concurrency_state table (correct PK, from
    # the current ConcurrencyState model) gets created fresh alongside the
    # renamed old one.
    await conn.run_sync(SQLModel.metadata.create_all)
    await conn.execute(
        text(
            "INSERT INTO concurrency_state "
            "(engine, provider, model, current_thread, consecutive_successes, "
            "observation_count, last_outcome, last_rate_limit_hits, "
            "last_duration_seconds, updated_at) "
            "SELECT 'pdf2zh', provider, model, current_thread, consecutive_successes, "
            "observation_count, last_outcome, last_rate_limit_hits, "
            "last_duration_seconds, updated_at "
            "FROM concurrency_state_old"
        )
    )
    await conn.execute(text("DROP TABLE concurrency_state_old"))


async def _migrate_chunks_unit_columns(conn) -> None:
    """Architecture.md 6.20.7 (US-22 buoc 2/3): `chunks.page_start`/`page_end`
    doi thanh NULLABLE (NULL cho chunk EPUB) va them 2 cot moi (nullable)
    `unit_start`/`unit_end` (NULL cho chunk PDF). Khac `_add_missing_columns`
    o tren — RELAX mot rang buoc NOT NULL da co, ma SQLite khong `ALTER TABLE
    ... ADD COLUMN` lam duoc (cung han che da ghi o
    `_migrate_concurrency_state_engine_key` cho PK). Dung LAI dung pattern
    "rebuild bang" cua ham do: doi ten bang cu, de `create_all()` dung
    `Chunk` model HIEN TAI dung bang moi, copy MOI cot ma bang cu THAT SU CO
    (doc dong tu PRAGMA truoc khi doi ten, khong hardcode danh sach — mien
    nhiem voi bat ky cot nao tu increment truoc da/chua duoc them), roi xoa
    bang cu. Idempotent: no-op ngay khi `page_start` da nullable (ke ca DB
    hoan toan moi, noi `create_all()` o tren da dung schema moi tu dau).
    """
    result = await conn.execute(text("PRAGMA table_info(chunks)"))
    rows = result.all()
    if not rows:
        return  # bang chua ton tai — create_all() o tren se tao no

    # index 1 = ten cot, index 3 = co "NOT NULL" (1) hay khong (0).
    page_start_row = next((row for row in rows if row[1] == "page_start"), None)
    if page_start_row is None or page_start_row[3] == 0:
        return  # da nullable (hoac cot khong ton tai vi ly do khac) — xong

    old_column_names = [row[1] for row in rows]
    await conn.execute(text("ALTER TABLE chunks RENAME TO chunks_old"))
    await conn.run_sync(SQLModel.metadata.create_all)
    col_list = ", ".join(old_column_names)
    await conn.execute(text(f"INSERT INTO chunks ({col_list}) SELECT {col_list} FROM chunks_old"))
    await conn.execute(text("DROP TABLE chunks_old"))


async def init_db() -> None:
    """Create tables and enable WAL mode. Idempotent — safe to call on every startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await _migrate_concurrency_state_engine_key(conn)
        await _migrate_chunks_unit_columns(conn)
        await _add_missing_columns(conn)
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        # BR-GLOSS-02: case-insensitive EN term matching.
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_glossary_entries_term_nocase "
                "ON glossary_entries(term_en COLLATE NOCASE)"
            )
        )
        # Architecture.md 6.18.3 (US-20): suggested_terms is a brand-new
        # table (created above by create_all()) but its 2 composite indexes
        # need the same raw-SQL pattern as idx_glossary_entries_term_nocase
        # (SQLModel has no declarative composite-index/unique-constraint
        # usage elsewhere in this codebase to follow instead).
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_suggested_terms_job_term "
                "ON suggested_terms(job_id, term_en)"
            )
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_suggested_terms_status_rank "
                "ON suggested_terms(status, rank_score DESC)"
            )
        )
