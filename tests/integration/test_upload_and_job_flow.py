"""Integration test for the full upload -> job creation -> status check flow
(Increment 5).

The happy-path test uses `job_type="parse_only"` deliberately (not
"translate") — per docs/CHANGELOG.md "Increment 5", `JobOrchestrator`
(Increment 4) has no parse_only branch yet, so `create_job()` marks a
parse_only job `failed` synchronously inside the request instead of
scheduling it onto a background `asyncio.Task`. That means this test needs
no API keys AND no waiting/polling for eventual consistency — the whole flow
completes within one request/response cycle, which is exactly why the task
brief calls out parse_only as the no-API-key path for manual verification.

The DeepL-for-PDF rejection test is the other required case: verify it
happens at the API layer (400, no `Job` row created) before anything reaches
`JobOrchestrator`.
"""

from collections.abc import Iterator

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings


def _make_pdf_bytes(n_pages: int = 3) -> bytes:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((50, 100), f"Recipe page {i + 1}: 2 cups flour, 350F", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    # Relative "data/..." paths (DB, uploads, processing, outputs — all
    # default in config.py / upload.py / job_orchestrator.py) resolve under
    # tmp_path instead of the real project's data/ directory. aiosqlite
    # opens the DB file lazily (first query, not at engine construction) but
    # will not create a missing parent directory, so "data/" must exist
    # before the app's lifespan calls init_db().
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    database_module._engine = None
    database_module._session_factory = None

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        # try/finally: a fixture-setup error (e.g. lifespan failing to open
        # the DB) must not leave the cached Settings / global engine
        # pointing at this test's tmp_path for every test that runs after
        # this one in the same process.
        get_settings.cache_clear()
        database_module._engine = None
        database_module._session_factory = None


def test_upload_then_create_parse_only_job_and_check_status(client: TestClient) -> None:
    upload_response = client.post(
        "/api/upload",
        files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")},
    )
    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    assert upload_body["file_type"] == "pdf_digital"
    assert upload_body["page_count"] == 3
    file_id = upload_body["file_id"]

    job_response = client.post("/api/jobs", json={"file_id": file_id, "job_type": "parse_only"})
    assert job_response.status_code == 202
    job_id = job_response.json()["job_id"]

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    detail = status_response.json()
    assert detail["job_type"] == "parse_only"
    assert detail["filename"] == "recipe.pdf"
    # Known limitation (docs/CHANGELOG.md "Increment 5"): no parse_only
    # branch in JobOrchestrator yet -> a clear, immediate failure rather than
    # a silent hang.
    assert detail["status"] == "failed"
    assert "parse_only" in detail["error_message"]

    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_upload_rejects_non_pdf_epub_extension(client: TestClient) -> None:
    response = client.post(
        "/api/upload", files={"file": ("notes.txt", b"hello world", "text/plain")}
    )
    assert response.status_code == 400


def test_upload_sanitizes_path_traversal_filename(client: TestClient) -> None:
    """CWE-22 regression: a client-supplied filename containing "../" must
    never make the server write outside data/uploads/.
    """
    from src.api.routes.upload import _UPLOAD_DIR

    response = client.post(
        "/api/upload",
        files={
            "file": ("../../../../../../tmp/evil.pdf", _make_pdf_bytes(), "application/pdf")
        },
    )
    assert response.status_code == 200
    file_id = response.json()["file_id"]

    upload_dir_resolved = _UPLOAD_DIR.resolve()
    stored_files = [
        p
        for p in _UPLOAD_DIR.iterdir()
        if p.name.startswith(f"{file_id}_") and p.suffix != ".json"
    ]
    assert len(stored_files) == 1
    dest_path = stored_files[0]

    assert dest_path.resolve().is_relative_to(upload_dir_resolved)
    assert ".." not in dest_path.name
    assert "/" not in dest_path.name.removeprefix(f"{file_id}_")


def test_upload_rejects_fake_pdf_with_400_not_500(client: TestClient) -> None:
    """Bug #1 (QA Round 1): a `.pdf`-named file whose content isn't a real
    PDF must return a clear 400, not an unhandled 500.
    """
    response = client.post(
        "/api/upload",
        files={
            "file": (
                "fake.pdf",
                b"this is just plain text pretending to be a pdf",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 400
    assert "hong" in response.json()["detail"] or "hỏng" in response.json()["detail"]

    from src.api.routes.upload import _UPLOAD_DIR

    leftover = [p for p in _UPLOAD_DIR.iterdir() if p.name.endswith("_fake.pdf")]
    assert leftover == []


def test_upload_rejects_oversized_file(client: TestClient, monkeypatch) -> None:
    from src.api.routes import upload as upload_route

    monkeypatch.setattr(upload_route, "get_settings", lambda: _TinyLimitSettings())

    response = client.post(
        "/api/upload",
        files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 400
    assert "MB" in response.json()["detail"]


class _TinyLimitSettings:
    max_upload_size_mb = 0.0001  # a few bytes — any real PDF exceeds this


def test_create_job_rejects_deepl_for_pdf_before_creating_job_record(client: TestClient) -> None:
    upload_response = client.post(
        "/api/upload", files={"file": ("book.pdf", _make_pdf_bytes(), "application/pdf")}
    )
    file_id = upload_response.json()["file_id"]

    job_response = client.post(
        "/api/jobs",
        json={"file_id": file_id, "job_type": "translate", "provider": "deepl"},
    )
    assert job_response.status_code == 400
    assert "DeepL" in job_response.json()["detail"]

    # Reject-early contract: no Job row created for the rejected request.
    jobs_list = client.get("/api/jobs")
    assert jobs_list.json()["total"] == 0


def test_get_job_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404


def test_create_job_unknown_file_id_returns_404(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"file_id": "does-not-exist"})
    assert response.status_code == 404


def test_create_job_reports_duplicate_of_completed_job_with_same_hash(
    client: TestClient,
) -> None:
    """AC-12.2 / Bug #3 (QA Round 1): re-uploading and re-submitting the same
    file content after a prior job for it already completed must surface
    `duplicate_of` instead of silently creating another job.
    """
    import asyncio

    import src.models.database as database_module
    from src.models.job import Job

    pdf_bytes = _make_pdf_bytes()

    upload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", pdf_bytes, "application/pdf")}
    )
    file_id = upload_response.json()["file_id"]

    job_response = client.post(
        "/api/jobs", json={"file_id": file_id, "job_type": "parse_only"}
    )
    job_id = job_response.json()["job_id"]

    async def _mark_completed() -> None:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            job.status = "completed"
            job.completed_at = job.completed_at or job.created_at
            session.add(job)
            await session.commit()

    asyncio.run(_mark_completed())

    reupload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", pdf_bytes, "application/pdf")}
    )
    assert reupload_response.status_code == 200
    new_file_id = reupload_response.json()["file_id"]
    assert new_file_id != file_id  # a fresh file_id, same content/hash

    duplicate_check_response = client.post(
        "/api/jobs", json={"file_id": new_file_id, "job_type": "translate"}
    )
    assert duplicate_check_response.status_code == 200
    body = duplicate_check_response.json()
    assert body["status"] == "duplicate_found"
    assert body["duplicate_of"]["job_id"] == job_id

    # `force: true` bypasses the check and creates a real new job.
    forced_response = client.post(
        "/api/jobs",
        json={"file_id": new_file_id, "job_type": "parse_only", "force": True},
    )
    assert forced_response.status_code == 202
    assert forced_response.json()["job_id"] != job_id


def test_download_before_completion_returns_404(client: TestClient) -> None:
    upload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")}
    )
    file_id = upload_response.json()["file_id"]
    job_response = client.post("/api/jobs", json={"file_id": file_id, "job_type": "parse_only"})
    job_id = job_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/download")
    assert response.status_code == 404
