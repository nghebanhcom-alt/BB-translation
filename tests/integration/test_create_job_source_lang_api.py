"""S7 — dich FR->VI: `POST /api/jobs` phai ghi `Job.source_lang` tu ket qua
`estimate_translation_cost()` (Architecture.md §6.26.4 point 1), va API
`GET /api/jobs/{id}` phai serialize field nay ra (§6.26 mo rong pham vi UI,
2026-09-16).

Khong de background pipeline chay that (cung ky luat voi test_cost_gate_api.py
— khong goi LLM/subprocess that trong test).
"""

import asyncio
from collections.abc import Iterator

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

import src.api.routes.jobs as jobs_route
import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings
from src.models.job import Job
from tests.test_language_detector import _EN_TEXT, _FR_TEXT


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


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    words = text.split()
    page_size = 120
    for start in range(0, len(words), page_size):
        page = doc.new_page()
        page.insert_textbox(
            (36, 36, 560, 780), " ".join(words[start : start + page_size]), fontsize=9
        )
    data = doc.tobytes()
    doc.close()
    return data


def _configure_generous_cap(client: TestClient) -> None:
    res = client.put(
        "/api/settings",
        json={
            "default_provider": "claude",
            "provider_api_keys": {"claude": "sk-ant-fake"},
            "max_cost_per_job_usd": 1000.0,
            "max_cost_per_batch_usd": 1000.0,
            "cost_cap_enabled": True,
        },
    )
    assert res.status_code == 200


def _upload(client: TestClient, pdf_bytes: bytes, filename: str = "book.pdf") -> str:
    res = client.post("/api/upload", files={"file": (filename, pdf_bytes, "application/pdf")})
    assert res.status_code == 200
    return res.json()["file_id"]


def _get_job_source_lang(job_id: str) -> str | None:
    async def _fetch() -> str | None:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            return job.source_lang

    return asyncio.run(_fetch())


def test_create_job_persists_source_lang_fr_detected_by_cost_gate(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(jobs_route, "_schedule_background", lambda coro: coro.close())
    _configure_generous_cap(client)
    file_id = _upload(client, _make_pdf_bytes(_FR_TEXT), filename="book_fr.pdf")

    response = client.post("/api/jobs", json={"file_id": file_id, "provider": "claude"})

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert _get_job_source_lang(job_id) == "fr"

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["source_lang"] == "fr"


def test_create_job_persists_source_lang_en_detected_by_cost_gate(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(jobs_route, "_schedule_background", lambda coro: coro.close())
    _configure_generous_cap(client)
    file_id = _upload(client, _make_pdf_bytes(_EN_TEXT), filename="book_en.pdf")

    response = client.post("/api/jobs", json={"file_id": file_id, "provider": "claude"})

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert _get_job_source_lang(job_id) == "en"

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["source_lang"] == "en"


def test_create_job_parse_only_leaves_source_lang_none(client: TestClient, monkeypatch) -> None:
    """§6.26.4: source_lang chi co y nghia cho job_type=translate (di qua
    cost gate) — parse_only KHONG qua estimate_translation_cost()."""
    monkeypatch.setattr(jobs_route, "_schedule_background", lambda coro: coro.close())
    file_id = _upload(client, _make_pdf_bytes(_FR_TEXT), filename="book_fr.pdf")

    response = client.post("/api/jobs", json={"file_id": file_id, "job_type": "parse_only"})

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert _get_job_source_lang(job_id) is None
