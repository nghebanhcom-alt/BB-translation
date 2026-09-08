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


def test_create_single_entry_force_true_updates_existing_duplicate(client: TestClient) -> None:
    # BR-GLOSS-03 "last-updated-wins" van dung KHI da xac nhan ghi de
    # (force=true, BR-GLOSS-07): tao lai voi cung term_en (case-insensitive,
    # BR-GLOSS-02) + force=true phai CAP NHAT entry cu, khong tao ban trung.
    first = client.post("/api/glossary", json={"term_en": "ganache", "term_vi": "(keep)"})
    assert first.status_code == 201

    second = client.post(
        "/api/glossary",
        json={"term_en": "Ganache", "term_vi": "sot ganache", "force": True},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["term_vi"] == "sot ganache"

    assert client.get("/api/glossary").json()["total"] == 1


# === US-17 / BR-GLOSS-07 (Architecture.md 6.16.3) — xac nhan ghi de khi trung ===


def test_create_single_entry_duplicate_without_force_returns_409_with_existing_entry(
    client: TestClient,
) -> None:
    first = client.post(
        "/api/glossary", json={"term_en": "ganache", "term_vi": "(keep)", "notes": "chocolate"}
    )
    assert first.status_code == 201
    existing_id = first.json()["id"]

    # Khac hoa/thuong (BR-GLOSS-02 case-insensitive match).
    response = client.post(
        "/api/glossary", json={"term_en": "GANACHE", "term_vi": "sot ganache moi"}
    )
    assert response.status_code == 409
    body = response.json()
    detail = body["detail"]
    assert detail["requires_confirmation"] is True
    assert detail["existing"]["entry_id"] == existing_id
    assert detail["existing"]["term_en"] == "ganache"
    assert detail["existing"]["term_vi"] == "(keep)"
    assert detail["existing"]["notes"] == "chocolate"

    # R6-02: assert gia tri cu the, khong chi status_code — dong nghiep du
    # lieu that (SELECT lai qua API), khong duoc ghi gi vao DB tren nhanh 409.
    list_body = client.get("/api/glossary").json()
    assert list_body["total"] == 1
    unchanged = list_body["entries"][0]
    assert unchanged["id"] == existing_id
    assert unchanged["term_vi"] == "(keep)"
    assert unchanged["notes"] == "chocolate"


def test_create_single_entry_duplicate_with_force_overwrites(client: TestClient) -> None:
    first = client.post("/api/glossary", json={"term_en": "ganache", "term_vi": "(keep)"})
    assert first.status_code == 201
    existing_id = first.json()["id"]

    response = client.post(
        "/api/glossary",
        json={"term_en": "GANACHE", "term_vi": "sot ganache moi", "force": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == existing_id
    assert body["term_vi"] == "sot ganache moi"

    list_body = client.get("/api/glossary").json()
    assert list_body["total"] == 1
    assert list_body["entries"][0]["term_vi"] == "sot ganache moi"


# === US-18 / BR-GLOSS-08 (Architecture.md 6.16.2) — GET /api/glossary?q= ===


def _seed_search_entries(client: TestClient) -> None:
    client.post("/api/glossary", json={"term_en": "Ganache", "term_vi": "sot ganache"})
    client.post("/api/glossary", json={"term_en": "Buttercream", "term_vi": "kem bo"})
    client.post("/api/glossary", json={"term_en": "Proofing", "term_vi": "u bot"})


def test_search_matches_term_en(client: TestClient) -> None:
    _seed_search_entries(client)
    response = client.get("/api/glossary", params={"q": "ganache"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["entries"]) == body["total"]
    assert body["entries"][0]["term_en"] == "Ganache"


def test_search_matches_term_vi(client: TestClient) -> None:
    _seed_search_entries(client)
    response = client.get("/api/glossary", params={"q": "kem bo"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["entries"]) == body["total"]
    assert body["entries"][0]["term_en"] == "Buttercream"


def test_search_no_match_returns_empty_total_zero(client: TestClient) -> None:
    _seed_search_entries(client)
    response = client.get("/api/glossary", params={"q": "does-not-exist-anywhere"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["entries"] == []


def test_search_combines_with_scope_filter(client: TestClient) -> None:
    _seed_search_entries(client)
    response = client.get("/api/glossary", params={"q": "ganache", "scope": "global"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["entries"]) == 1

    # scope khac "global" (khong ton tai trong data seed) phai loai het,
    # chung minh q AND scope, khong ghi de len nhau (EC-18.3).
    response_other_scope = client.get(
        "/api/glossary", params={"q": "ganache", "scope": "some-project-scope"}
    )
    assert response_other_scope.status_code == 200
    assert response_other_scope.json()["total"] == 0


def test_search_escapes_percent_and_underscore_wildcards(client: TestClient) -> None:
    # Architecture.md 6.16.1 G-04/G-05: `_`/`%` la wildcard trong LIKE thuong,
    # `.contains(autoescape=True)` phai tu escape chung. Neu thieu escape,
    # q="_" se tra ca bang (regression y het bug da do o Architecture.md).
    client.post("/api/glossary", json={"term_en": "50% hydration", "term_vi": "(keep)"})
    client.post("/api/glossary", json={"term_en": "sour_dough", "term_vi": "(keep)"})
    client.post("/api/glossary", json={"term_en": "buttercream", "term_vi": "kem bo"})

    percent_response = client.get("/api/glossary", params={"q": "50%"})
    assert percent_response.status_code == 200
    percent_body = percent_response.json()
    assert percent_body["total"] == 1
    assert percent_body["entries"][0]["term_en"] == "50% hydration"

    underscore_response = client.get("/api/glossary", params={"q": "_"})
    assert underscore_response.status_code == 200
    underscore_body = underscore_response.json()
    assert underscore_body["total"] == 1
    assert underscore_body["entries"][0]["term_en"] == "sour_dough"


def test_search_empty_string_returns_full_list(client: TestClient) -> None:
    _seed_search_entries(client)
    response = client.get("/api/glossary", params={"q": ""})
    assert response.status_code == 200
    assert response.json()["total"] == 3
