"""Tests for 2 features added 2026-09-06 (user request, not tied to any US
in Architecture.md yet): `GET /api/version` and `uploaded_at` on
`POST /api/upload` (used by the frontend to sort "file da upload" newest
first and show a human-readable upload timestamp).

Client/DB fixture pattern copied from
`tests/integration/test_delete_and_download_naming.py`.
"""

import tomllib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings


def _make_pdf_bytes(n_pages: int = 1) -> bytes:
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


# === GET /api/version ===


def test_get_version_matches_pyproject_toml(client: TestClient) -> None:
    pyproject_path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        expected_version = tomllib.load(f)["project"]["version"]

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": expected_version}


# === POST /api/upload — uploaded_at ===


def test_upload_response_includes_uploaded_at(client: TestClient) -> None:
    before = datetime.now(UTC)

    response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["uploaded_at"] is not None
    # ISO 8601 with tzinfo — datetime.fromisoformat() must round-trip it.
    parsed = datetime.fromisoformat(body["uploaded_at"])
    assert parsed >= before


def test_upload_sidecar_metadata_persists_uploaded_at(client: TestClient) -> None:
    from src.api.routes.upload import resolve_upload

    response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")}
    )
    file_id = response.json()["file_id"]

    metadata = resolve_upload(file_id)

    assert metadata.uploaded_at == response.json()["uploaded_at"]


def test_resolve_upload_tolerates_sidecar_without_uploaded_at(client: TestClient) -> None:
    # Sidecar files written before this feature existed have no `uploaded_at`
    # key at all — UploadMetadata(**data) must not raise TypeError for them.
    import json

    from src.api.routes.upload import _metadata_path, resolve_upload

    old_sidecar = {
        "file_id": "legacy-id",
        "filename": "old.pdf",
        "file_path": "data/uploads/legacy-id_old.pdf",
        "file_type": "pdf_digital",
        "size_bytes": 123,
        "file_hash": "abc",
        "page_count": 1,
    }
    _metadata_path("legacy-id").parent.mkdir(parents=True, exist_ok=True)
    _metadata_path("legacy-id").write_text(json.dumps(old_sidecar), encoding="utf-8")

    metadata = resolve_upload("legacy-id")

    assert metadata.uploaded_at == ""
