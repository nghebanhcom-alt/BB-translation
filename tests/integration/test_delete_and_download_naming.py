"""Tests for 3 endpoints added 2026-09-06 (user request, not tied to any US
in Architecture.md yet): `DELETE /api/upload/{file_id}`,
`DELETE /api/jobs/{job_id}`, and the timestamp suffix on
`GET /api/jobs/{id}/download`'s filename.

Client/DB fixture pattern copied from
`tests/integration/test_upload_and_job_flow.py` (relative "data/..." paths
resolved under `tmp_path` via `monkeypatch.chdir`).
"""

import asyncio
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings
from src.models.batch import Batch
from src.models.chunk import Chunk
from src.models.job import Job
from src.models.overflow import OverflowReport


def _make_pdf_bytes(n_pages: int = 2) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((50, 100), f"Recipe page {i + 1}: 2 cups flour", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    database_module._engine = None
    database_module._session_factory = None

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()
        database_module._engine = None
        database_module._session_factory = None


async def _insert_completed_job(output_dir: Path, completed_at: datetime | None) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "translated_vi.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(output_path)
    doc.close()

    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="book.pdf",
            file_path=str(output_dir / "book.pdf"),
            file_size=1,
            file_hash="deadbeef",
            file_type="pdf_digital",
            model="ollama",
            status="completed",
            output_path=str(output_path),
            completed_at=completed_at,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def _insert_job_with_chunks(status: str) -> str:
    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="book.pdf",
            file_path="data/uploads/does-not-matter.pdf",
            file_size=1,
            file_hash="deadbeef2",
            file_type="pdf_digital",
            model="ollama",
            status=status,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        session.add(Chunk(job_id=job.id, chunk_index=0, page_start=1, page_end=1))
        session.add(
            OverflowReport(
                job_id=job.id,
                page_number=1,
                block_index=0,
                bbox="[]",
                scaling_applied=1.0,
            )
        )
        await session.commit()
        return job.id


async def _insert_job_in_batch(status: str, batch_completed_files: int) -> tuple[str, str]:
    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        batch = Batch(
            status="completed",
            total_files=batch_completed_files + 1,
            completed_files=batch_completed_files,
            failed_files=0,
        )
        session.add(batch)
        await session.commit()
        await session.refresh(batch)

        job = Job(
            filename="book.pdf",
            file_path="data/uploads/does-not-matter.pdf",
            file_size=1,
            file_hash="deadbeef3",
            file_type="pdf_digital",
            model="ollama",
            status=status,
            batch_id=batch.id,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id, batch.id


# === GET /api/jobs/{id}/download — timestamp suffix ===


def test_download_filename_includes_completed_at_timestamp(client: TestClient, tmp_path) -> None:
    completed_at = datetime(2026, 9, 6, 1, 35, 22, tzinfo=UTC)
    job_id = asyncio.run(_insert_completed_job(tmp_path / "out", completed_at))

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "book_vi_20260906-013522.pdf" in disposition


def test_download_filename_falls_back_to_updated_at_when_no_completed_at(
    client: TestClient, tmp_path
) -> None:
    # `Job.updated_at` has a `default_factory` (always set at insert, unlike
    # `completed_at`) — the fallback in download.py's `timestamp_source`
    # picks it, so a suffix is still present, just derived from a different
    # field than the happy-path test above.
    job_id = asyncio.run(_insert_completed_job(tmp_path / "out2", None))

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert re.search(r"book_vi_\d{8}-\d{6}\.pdf", disposition)


# === DELETE /api/upload/{file_id} ===


def test_delete_upload_removes_file_and_metadata(client: TestClient) -> None:
    from src.api.routes.upload import _UPLOAD_DIR, _metadata_path

    upload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")}
    )
    file_id = upload_response.json()["file_id"]
    stored = next(p for p in _UPLOAD_DIR.iterdir() if p.name.startswith(f"{file_id}_"))
    assert stored.exists()
    assert _metadata_path(file_id).exists()

    delete_response = client.delete(f"/api/upload/{file_id}")

    assert delete_response.status_code == 204
    assert not stored.exists()
    assert not _metadata_path(file_id).exists()


def test_delete_upload_404_for_unknown_file_id(client: TestClient) -> None:
    response = client.delete("/api/upload/does-not-exist")
    assert response.status_code == 404


# === DELETE /api/jobs/{job_id} ===


def test_delete_job_removes_row_and_related_rows(client: TestClient) -> None:
    job_id = asyncio.run(_insert_job_with_chunks(status="failed"))

    delete_response = client.delete(f"/api/jobs/{job_id}")
    assert delete_response.status_code == 204

    async def _row_counts() -> tuple[int, int, int]:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            chunks = (await session.exec(select(Chunk).where(Chunk.job_id == job_id))).all()
            overflow = (
                await session.exec(select(OverflowReport).where(OverflowReport.job_id == job_id))
            ).all()
            return (0 if job is None else 1, len(chunks), len(overflow))

    job_count, chunk_count, overflow_count = asyncio.run(_row_counts())
    assert (job_count, chunk_count, overflow_count) == (0, 0, 0)

    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_delete_job_rejects_active_status(client: TestClient) -> None:
    job_id = asyncio.run(_insert_job_with_chunks(status="translating"))

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 400
    assert "dang chay" in response.json()["detail"] or "translating" in response.json()["detail"]
    assert client.get(f"/api/jobs/{job_id}").status_code == 200


def test_delete_job_404_for_unknown_job_id(client: TestClient) -> None:
    response = client.delete("/api/jobs/does-not-exist")
    assert response.status_code == 404


# === DELETE /api/jobs/{job_id} — Batch counter sync (Protocol 6 R6-04) ===
#
# BatchOrchestrator.run_batch() (src/core/job_orchestrator.py) only counts
# status == "completed" into Batch.completed_files and status == "failed"
# into Batch.failed_files. Deleting a job that belonged to a batch must
# decrement the exact counter that would have counted it — asserting the
# concrete post-delete value, not just "the request returned 204" (R6-02).


def test_delete_completed_job_decrements_batch_completed_files(client: TestClient) -> None:
    job_id, batch_id = asyncio.run(
        _insert_job_in_batch(status="completed", batch_completed_files=2)
    )

    response = client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 204

    async def _batch_completed_files() -> int:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            batch = await session.get(Batch, batch_id)
            assert batch is not None
            return batch.completed_files

    assert asyncio.run(_batch_completed_files()) == 1


def test_delete_failed_job_decrements_batch_failed_files(client: TestClient) -> None:
    session_factory_setup = database_module.get_session_factory()

    async def _setup() -> tuple[str, str]:
        async with session_factory_setup() as session:
            batch = Batch(status="completed", total_files=2, completed_files=0, failed_files=2)
            session.add(batch)
            await session.commit()
            await session.refresh(batch)

            job = Job(
                filename="book.pdf",
                file_path="data/uploads/does-not-matter.pdf",
                file_size=1,
                file_hash="deadbeef4",
                file_type="pdf_digital",
                model="ollama",
                status="failed",
                batch_id=batch.id,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job.id, batch.id

    job_id, batch_id = asyncio.run(_setup())

    response = client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 204

    async def _batch_failed_files() -> int:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            batch = await session.get(Batch, batch_id)
            assert batch is not None
            return batch.failed_files

    assert asyncio.run(_batch_failed_files()) == 1


def test_delete_job_without_batch_does_not_error(client: TestClient) -> None:
    job_id = asyncio.run(_insert_job_with_chunks(status="completed"))

    response = client.delete(f"/api/jobs/{job_id}")

    assert response.status_code == 204
