"""US-19 (Architecture.md 6.17.2): `jobs.finished_at` is added via
`_add_missing_columns` (src/models/database.py's idempotent `ALTER TABLE ADD
COLUMN` pattern — same one already used for `jobs.chunk_size_used`/
`jobs.parse_method`), NOT by dropping/recreating the DB. This test proves
the migration is additive against a "legacy" jobs table (simulating a real
dev DB from before this column existed) and preserves the existing row.
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.job import Job


async def _create_legacy_chunks_table(conn) -> None:
    """Minimal stand-in so `_add_missing_columns()` (which also migrates
    `chunks.thread_used`/`chunks.rate_limit_hits`) has a real table to ALTER
    — this test only cares about the `jobs.finished_at` entry, but
    `_add_missing_columns()` walks the whole `_NEW_NULLABLE_COLUMNS` list.
    """
    await conn.execute(text("CREATE TABLE chunks (id VARCHAR NOT NULL PRIMARY KEY)"))


async def _create_legacy_jobs_table(conn) -> None:
    """A jobs table shaped like it was right before this task's migration —
    every column up through `parse_method`, but no `finished_at`."""
    await conn.execute(
        text(
            "CREATE TABLE jobs ("
            "id VARCHAR NOT NULL PRIMARY KEY, "
            "batch_id VARCHAR, "
            "filename VARCHAR NOT NULL, "
            "file_path VARCHAR NOT NULL, "
            "file_size INTEGER NOT NULL, "
            "file_hash VARCHAR NOT NULL, "
            "file_type VARCHAR NOT NULL, "
            "job_type VARCHAR NOT NULL, "
            "total_pages INTEGER, "
            "status VARCHAR NOT NULL, "
            "cost_cap_usd FLOAT, "
            "cancel_requested BOOLEAN NOT NULL, "
            "progress FLOAT NOT NULL, "
            "current_chunk INTEGER, "
            "total_chunks INTEGER, "
            "error_message VARCHAR, "
            "output_path VARCHAR, "
            "bilingual_path VARCHAR, "
            "model VARCHAR NOT NULL, "
            "estimated_cost FLOAT, "
            "actual_cost FLOAT, "
            "cost_source VARCHAR NOT NULL, "
            "ocr_confidence FLOAT, "
            "ocr_bridge_path VARCHAR, "
            "ocr_dropped_spans INTEGER, "
            "chunk_size_used INTEGER, "
            "parse_method VARCHAR, "
            "started_at DATETIME, "
            "completed_at DATETIME, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        )
    )
    await conn.execute(
        text(
            "INSERT INTO jobs (id, filename, file_path, file_size, file_hash, "
            "file_type, job_type, status, cancel_requested, progress, model, "
            "cost_source, completed_at, created_at, updated_at) VALUES "
            "('job-legacy-1', 'book.pdf', '/data/uploads/book.pdf', 1024, "
            "'deadbeef', 'pdf_digital', 'translate', 'completed', 0, 1.0, "
            "'deepseek', 'estimated', '2026-08-01T10:20:00', "
            "'2026-08-01T10:00:00', '2026-08-01T10:20:00')"
        )
    )


@pytest.mark.asyncio
async def test_migration_adds_finished_at_column_and_preserves_existing_row(
    tmp_path: Path,
) -> None:
    from src.models.database import _add_missing_columns

    db_path = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await _create_legacy_chunks_table(conn)
        await _create_legacy_jobs_table(conn)
        await _add_missing_columns(conn)

    async with AsyncSession(engine) as session:
        job = await session.get(Job, "job-legacy-1")
        assert job is not None
        # Old data untouched.
        assert job.filename == "book.pdf"
        assert job.status == "completed"
        assert job.completed_at is not None
        # New column exists and defaults to NULL for a pre-existing row
        # (EC-19.1: `_to_detail()` falls back to `completed_at` for this case).
        assert job.finished_at is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_is_idempotent_noop_on_fresh_schema(tmp_path: Path) -> None:
    from sqlmodel import SQLModel

    from src.models.database import _add_missing_columns

    db_path = tmp_path / "fresh.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # finished_at already exists via create_all() on a fresh DB -> no-op.
        await _add_missing_columns(conn)

    async with AsyncSession(engine) as session:
        from datetime import UTC, datetime

        job = Job(
            filename="x.pdf",
            file_path="/data/uploads/x.pdf",
            file_size=10,
            file_hash="h",
            file_type="pdf_digital",
            model="deepseek",
            finished_at=datetime.now(UTC),
        )
        session.add(job)
        await session.commit()

    await engine.dispose()
