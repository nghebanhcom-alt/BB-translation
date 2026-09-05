"""`_migrate_concurrency_state_engine_key` (src/models/database.py) —
Architecture.md 6.14.5: `ConcurrencyState`'s primary key gains `engine`
(`(provider, model)` -> `(engine, provider, model)`). A composite PK change
needs SQLite's "rebuild the table" pattern, not `ALTER TABLE ADD COLUMN`
(SQLite cannot alter a PK in place) — this test exercises that rebuild
end-to-end against a real (temp-file) SQLite DB, including migrating a
pre-existing row that predates the `engine` column.
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.concurrency_state import ConcurrencyState


async def _create_legacy_table(conn) -> None:
    """Simulate a pre-6.14.5 dev DB: `concurrency_state` exists with the OLD
    `(provider, model)` primary key and one row already in it."""
    await conn.execute(
        text(
            "CREATE TABLE concurrency_state ("
            "provider VARCHAR NOT NULL, "
            "model VARCHAR NOT NULL, "
            "current_thread INTEGER NOT NULL, "
            "consecutive_successes INTEGER NOT NULL DEFAULT 0, "
            "observation_count INTEGER NOT NULL DEFAULT 0, "
            "last_outcome VARCHAR NOT NULL DEFAULT 'none', "
            "last_rate_limit_hits INTEGER NOT NULL DEFAULT 0, "
            "last_duration_seconds FLOAT, "
            "updated_at DATETIME NOT NULL, "
            "PRIMARY KEY (provider, model))"
        )
    )
    await conn.execute(
        text(
            "INSERT INTO concurrency_state "
            "(provider, model, current_thread, consecutive_successes, "
            "observation_count, last_outcome, last_rate_limit_hits, updated_at) "
            "VALUES ('deepseek', 'deepseek:deepseek-chat', 12, 3, 5, 'success', 0, "
            "'2026-09-01T00:00:00')"
        )
    )


@pytest.mark.asyncio
async def test_migration_adds_engine_column_and_backfills_pdf2zh(tmp_path: Path) -> None:
    from src.models.database import _migrate_concurrency_state_engine_key

    db_path = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await _create_legacy_table(conn)
        await _migrate_concurrency_state_engine_key(conn)

    async with AsyncSession(engine) as session:
        state = await session.get(
            ConcurrencyState, ("pdf2zh", "deepseek", "deepseek:deepseek-chat")
        )
        assert state is not None
        assert state.current_thread == 12
        assert state.consecutive_successes == 3
        assert state.observation_count == 5
        assert state.last_outcome == "success"

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_allows_distinct_engines_for_same_provider_model(
    tmp_path: Path,
) -> None:
    """The whole point of 6.14.5: after migration, a babeldoc row and a
    pdf2zh row for the SAME (provider, model) must coexist without a PK
    collision — proof the real PK is now 3-wide, not just an ORM-level
    convention on top of a still-2-wide SQLite constraint."""
    from src.models.database import _migrate_concurrency_state_engine_key

    db_path = tmp_path / "legacy2.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await _create_legacy_table(conn)
        await _migrate_concurrency_state_engine_key(conn)

    async with AsyncSession(engine) as session:
        session.add(
            ConcurrencyState(
                engine="babeldoc",
                provider="deepseek",
                model="deepseek:deepseek-chat",
                current_thread=4,
            )
        )
        await session.commit()

        pdf2zh_state = await session.get(
            ConcurrencyState, ("pdf2zh", "deepseek", "deepseek:deepseek-chat")
        )
        babeldoc_state = await session.get(
            ConcurrencyState, ("babeldoc", "deepseek", "deepseek:deepseek-chat")
        )
        assert pdf2zh_state is not None and pdf2zh_state.current_thread == 12
        assert babeldoc_state is not None and babeldoc_state.current_thread == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_is_idempotent_noop_on_fresh_schema(tmp_path: Path) -> None:
    from src.models.database import _migrate_concurrency_state_engine_key

    db_path = tmp_path / "fresh.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Should be a no-op: the `engine` column already exists.
        await _migrate_concurrency_state_engine_key(conn)

    async with AsyncSession(engine) as session:
        session.add(
            ConcurrencyState(engine="pdf2zh", provider="deepseek", model="m", current_thread=8)
        )
        await session.commit()

    await engine.dispose()
