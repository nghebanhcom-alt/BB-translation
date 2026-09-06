import io
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_db_session
from src.api.main import app


@pytest.fixture
async def client() -> AsyncIterator[TestClient]:
    # StaticPool: a single shared connection so every dependency-override call
    # sees the same in-memory SQLite database instead of a fresh empty one.
    engine = create_async_engine(
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
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


def _sample_excel_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["EN", "VI", "Notes"])
    sheet.append(["ganache", "(keep)", "chocolate ganache"])
    sheet.append(["buttercream", "kem bo", None])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_full_glossary_flow(client: TestClient) -> None:
    # 1. Import preview — nothing saved yet.
    excel_bytes = _sample_excel_bytes()
    response = client.post(
        "/api/glossary/import",
        files={
            "file": (
                "glossary.xlsx",
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["count"] == 2
    entries = preview["entries"]
    assert {e["term_en"] for e in entries} == {"ganache", "buttercream"}

    list_before_confirm = client.get("/api/glossary")
    assert list_before_confirm.json()["total"] == 0

    # 2. Confirm import — persists to DB.
    confirm_response = client.post(
        "/api/glossary/import/confirm",
        json={"entries": entries, "scope": "global", "project_id": None},
    )
    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    assert confirm_body["imported"] == 2
    assert confirm_body["updated"] == 0

    # 3. List.
    list_response = client.get("/api/glossary")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 2
    assert all(e["scope"] == "global" for e in list_body["entries"])
    buttercream = next(e for e in list_body["entries"] if e["term_en"] == "buttercream")

    # 4. Edit.
    edit_response = client.put(
        f"/api/glossary/{buttercream['id']}",
        json={"term_vi": "kem phu bo"},
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["term_vi"] == "kem phu bo"

    # 5. Export.
    export_response = client.get("/api/glossary/export")
    assert export_response.status_code == 200
    assert (
        export_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(export_response.content) > 0

    # 6. Delete.
    delete_response = client.delete(f"/api/glossary/{buttercream['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}

    final_list = client.get("/api/glossary")
    assert final_list.json()["total"] == 1


def test_import_rejects_non_excel_file(client: TestClient) -> None:
    response = client.post(
        "/api/glossary/import",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_update_nonexistent_entry_returns_404(client: TestClient) -> None:
    response = client.put("/api/glossary/does-not-exist", json={"term_vi": "x"})
    assert response.status_code == 404


def test_delete_nonexistent_entry_returns_404(client: TestClient) -> None:
    response = client.delete("/api/glossary/does-not-exist")
    assert response.status_code == 404


# === POST /api/glossary — them 1 entry don le (US moi 2026-09-06) ===


def test_create_single_entry(client: TestClient) -> None:
    response = client.post(
        "/api/glossary", json={"term_en": "proofing", "term_vi": "u bot", "notes": "step"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["term_en"] == "proofing"
    assert body["term_vi"] == "u bot"
    assert body["notes"] == "step"
    assert body["scope"] == "global"

    list_response = client.get("/api/glossary")
    assert list_response.json()["total"] == 1


def test_create_single_entry_rejects_blank_term_en(client: TestClient) -> None:
    response = client.post("/api/glossary", json={"term_en": "   "})
    assert response.status_code == 400


def test_create_single_entry_updates_existing_duplicate(client: TestClient) -> None:
    # BR-GLOSS-03 "last-updated-wins": tao lai voi cung term_en (case-insensitive,
    # BR-GLOSS-02) phai CAP NHAT entry cu, khong tao ban trung.
    first = client.post("/api/glossary", json={"term_en": "ganache", "term_vi": "(keep)"})
    assert first.status_code == 201

    second = client.post("/api/glossary", json={"term_en": "Ganache", "term_vi": "sot ganache"})
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["term_vi"] == "sot ganache"

    assert client.get("/api/glossary").json()["total"] == 1
