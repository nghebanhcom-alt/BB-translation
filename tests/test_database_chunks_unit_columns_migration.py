"""`_migrate_chunks_unit_columns` (src/models/database.py) — Architecture.md
6.20.7 (US-22 buoc 2/3): `chunks.page_start`/`page_end` doi thanh nullable
(NULL cho chunk EPUB) va them 2 cot moi `unit_start`/`unit_end` (NULL cho
chunk PDF). SQLite khong `ALTER TABLE ... ADD COLUMN` de bo mot rang buoc NOT
NULL da co — day la 1 "rebuild bang" giong het pattern
`_migrate_concurrency_state_engine_key` da dung cho PK cua concurrency_state
(xem tests/test_database_concurrency_state_migration.py), kiem tra end-to-end
tren 1 SQLite that (temp-file), bao gom migrate 1 hang du lieu that co san TU
TRUOC khi 2 cot moi ton tai.
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.chunk import Chunk


async def _create_legacy_chunks_table(conn) -> None:
    """Mo phong 1 dev DB truoc US-22 buoc 2/3: `chunks` ton tai voi
    page_start/page_end NOT NULL, khong co unit_start/unit_end, va 1 hang du
    lieu PDF that da co san."""
    await conn.execute(
        text(
            "CREATE TABLE chunks ("
            "id VARCHAR NOT NULL PRIMARY KEY, "
            "job_id VARCHAR NOT NULL, "
            "chunk_index INTEGER NOT NULL, "
            "page_start INTEGER NOT NULL, "
            "page_end INTEGER NOT NULL, "
            "overlap_start INTEGER, "
            "overlap_end INTEGER, "
            "status VARCHAR NOT NULL DEFAULT 'pending', "
            "retry_count INTEGER NOT NULL DEFAULT 0, "
            "error_message VARCHAR, "
            "output_path VARCHAR, "
            "api_tokens_used INTEGER, "
            "api_cost FLOAT, "
            "thread_used INTEGER, "
            "rate_limit_hits INTEGER, "
            "started_at DATETIME, "
            "completed_at DATETIME, "
            "created_at DATETIME NOT NULL)"
        )
    )
    await conn.execute(
        text(
            "INSERT INTO chunks "
            "(id, job_id, chunk_index, page_start, page_end, status, retry_count, "
            "api_tokens_used, api_cost, created_at) "
            "VALUES ('chunk-1', 'job-1', 0, 1, 40, 'completed', 0, 1000, 0.5, "
            "'2026-09-01T00:00:00')"
        )
    )


@pytest.mark.asyncio
async def test_migration_relaxes_page_range_and_adds_unit_columns(tmp_path: Path) -> None:
    from src.models.database import _migrate_chunks_unit_columns

    db_path = tmp_path / "legacy_chunks.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await _create_legacy_chunks_table(conn)
        await _migrate_chunks_unit_columns(conn)

    async with AsyncSession(engine) as session:
        chunk = await session.get(Chunk, "chunk-1")
        assert chunk is not None
        # Du lieu PDF cu duoc GIU NGUYEN qua migration.
        assert chunk.page_start == 1
        assert chunk.page_end == 40
        assert chunk.status == "completed"
        assert chunk.api_tokens_used == 1000
        assert chunk.unit_start is None
        assert chunk.unit_end is None

        # Rang buoc NOT NULL that su da duoc go — 1 chunk EPUB (page_start/
        # page_end NULL, unit_start/unit_end co gia tri) ghi duoc binh thuong.
        session.add(
            Chunk(
                id="chunk-2",
                job_id="job-2",
                chunk_index=0,
                page_start=None,
                page_end=None,
                unit_start=0,
                unit_end=41,
            )
        )
        await session.commit()

        epub_chunk = await session.get(Chunk, "chunk-2")
        assert epub_chunk is not None
        assert epub_chunk.page_start is None
        assert epub_chunk.unit_start == 0
        assert epub_chunk.unit_end == 41

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_is_idempotent_noop_on_fresh_schema(tmp_path: Path) -> None:
    from sqlmodel import SQLModel

    from src.models.database import _migrate_chunks_unit_columns

    db_path = tmp_path / "fresh_chunks.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # page_start da nullable tu create_all() — phai la no-op.
        await _migrate_chunks_unit_columns(conn)

    async with AsyncSession(engine) as session:
        session.add(
            Chunk(id="c1", job_id="j1", chunk_index=0, unit_start=0, unit_end=5)
        )
        await session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_noop_when_table_does_not_exist_yet(tmp_path: Path) -> None:
    """`create_all()` always runs before this migration in `init_db()`, so
    the table-missing branch should be unreachable in production — still
    covered here since it's a real early-return path in the function."""
    from src.models.database import _migrate_chunks_unit_columns

    db_path = tmp_path / "empty.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await _migrate_chunks_unit_columns(conn)  # must not raise

    await engine.dispose()
