from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.progress_tracker import JobNotFoundError, ProgressTracker
from src.models.job import Job


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_update_writes_progress_fields(session: AsyncSession) -> None:
    job = Job(
        filename="book.pdf",
        file_path="/data/uploads/book.pdf",
        file_size=1024,
        file_hash="abc",
        file_type="pdf_digital",
        model="claude",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    tracker = ProgressTracker()
    await tracker.update(job.id, current_chunk=2, total_chunks=4, db_session=session)

    await session.refresh(job)
    assert job.current_chunk == 2
    assert job.total_chunks == 4
    assert job.progress == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_update_raises_for_unknown_job(session: AsyncSession) -> None:
    tracker = ProgressTracker()
    with pytest.raises(JobNotFoundError):
        await tracker.update("does-not-exist", current_chunk=1, total_chunks=1, db_session=session)
