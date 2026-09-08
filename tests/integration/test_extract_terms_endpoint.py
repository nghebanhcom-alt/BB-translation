"""US-20 — `POST /api/jobs/{id}/extract-terms` (manual re-run, Architecture.md
§6.18.6) and `DELETE /api/jobs/{id}` cascading `suggested_terms` cleanup
(Architecture.md §6.18.3: "KHONG duoc tin ON DELETE CASCADE").
"""

from collections.abc import AsyncIterator
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_db_session
from src.api.main import app
from src.models.job import Job
from src.models.suggested_term import SuggestedTerm


@pytest.fixture
async def db() -> AsyncIterator[tuple[TestClient, async_sessionmaker[AsyncSession]]]:
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    with TestClient(app) as test_client:
        yield test_client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


def _make_pdf(path: Path, text: str) -> None:
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 100), text, fontsize=10)
        doc.save(path)


@pytest.mark.asyncio
async def test_manual_extract_terms_endpoint_writes_rows(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]], tmp_path: Path
) -> None:
    client, session_factory = db
    pdf_path = tmp_path / "book.pdf"
    _make_pdf(
        pdf_path,
        "Laminated dough rests overnight in the fridge. "
        "Laminated dough needs careful folding technique. "
        "Laminated dough is used for croissants here.",
    )

    async with session_factory() as session:
        session.add(
            Job(
                id="job1",
                filename="book.pdf",
                file_path=str(pdf_path),
                file_size=1,
                file_hash="h",
                file_type="pdf_digital",
                model="deepseek",
                status="completed",
            )
        )
        await session.commit()

    response = client.post("/api/jobs/job1/extract-terms")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job1"
    assert body["written"] > 0

    async with session_factory() as session:
        rows = (
            await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))
        ).all()
        assert len(rows) == body["written"]


@pytest.mark.asyncio
async def test_manual_extract_terms_endpoint_400_on_lineage_error(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    async with session_factory() as session:
        session.add(
            Job(
                id="job1",
                filename="book.pdf",
                file_path="unused.pdf",
                file_size=1,
                file_hash="h",
                file_type="pdf_scan",
                model="deepseek",
                status="completed",
                ocr_bridge_path=None,
            )
        )
        await session.commit()

    response = client.post("/api/jobs/job1/extract-terms")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_job_cascades_suggested_terms(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    async with session_factory() as session:
        session.add(
            Job(
                id="job1",
                filename="book.pdf",
                file_path="unused.pdf",
                file_size=1,
                file_hash="h",
                file_type="pdf_digital",
                model="deepseek",
                status="completed",
            )
        )
        session.add(
            SuggestedTerm(
                job_id="job1",
                term_en="laminated dough",
                match_key="laminated dough",
                ngram_size=2,
                occurrence_count=5,
                rank_score=1.0,
            )
        )
        await session.commit()

    response = client.delete("/api/jobs/job1")
    assert response.status_code == 204

    async with session_factory() as session:
        rows = (
            await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))
        ).all()
        assert rows == []
