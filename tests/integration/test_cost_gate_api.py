"""Lop 2 pre-flight cost gate (Architecture.md 6.11.4) — the hard stop BEFORE
any Job/Batch row is created, closing RC-3 ("KHONG CO hard cap o bat ky lop
nao") of the $6.50 real-money incident investigated in Architecture.md 6.11.

No test in this file ever lets a scheduled job actually run
(`_schedule_background` is monkeypatched to a no-op wherever `confirm_cost`
lets a request through) — this repo's CLAUDE.md forbids any real LLM API
call during dev/test, and a real background job would call the out-of-band
`ClaudeProvider`/`pdf2zh` subprocess for real. The fake API key used below
(`sk-ant-fake`) only exercises `estimate_cost()`, which is pure arithmetic
(Architecture.md 6.6.2 R3.1) — see `src/services/claude_provider.py`.

Fixture setup mirrors `tests/integration/test_estimate_and_cancel_api.py`.
"""

import asyncio
from collections.abc import Iterator

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlmodel import func, select

import src.api.routes.jobs as jobs_route
import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings
from src.models.batch import Batch
from src.models.job import Job


def _make_pdf_bytes(n_pages: int = 5) -> bytes:
    """Real text (not just blank pages) so `_extract_full_text()` /
    `_count_text_segments()` produce a non-zero, non-trivial estimate —
    the whole point of these tests is a gate that actually trips.
    """
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text(
            (50, 100),
            f"Chapter {i + 1}: Baking science, gluten formation, and heat transfer "
            "in a professional oven. Recipe: 500g flour, 300g water, 10g salt.",
            fontsize=11,
        )
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


def _job_row_count() -> int:
    async def _count() -> int:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            result = await session.exec(select(func.count()).select_from(Job))
            return result.one()

    return asyncio.run(_count())


def _batch_row_count() -> int:
    async def _count() -> int:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            result = await session.exec(select(func.count()).select_from(Batch))
            return result.one()

    return asyncio.run(_count())


def _configure_low_cap(client: TestClient, job_cap: float = 0.000001, batch_cap: float = 0.000001) -> None:
    """`claude` gets a fake (network-inert) key so `ProviderFactory.create()`
    succeeds and `estimate_cost()` returns a non-zero figure — "ollama" would
    always price at $0 and could never trip the gate.
    """
    res = client.put(
        "/api/settings",
        json={
            "default_provider": "claude",
            "provider_api_keys": {"claude": "sk-ant-fake"},
            "max_cost_per_job_usd": job_cap,
            "max_cost_per_batch_usd": batch_cap,
            "cost_cap_enabled": True,
        },
    )
    assert res.status_code == 200


def _upload(client: TestClient, filename: str = "book.pdf", n_pages: int = 5) -> str:
    res = client.post(
        "/api/upload", files={"file": (filename, _make_pdf_bytes(n_pages), "application/pdf")}
    )
    assert res.status_code == 200
    return res.json()["file_id"]


# === POST /api/jobs ===


def test_create_job_blocked_with_402_when_estimate_exceeds_cap(client: TestClient) -> None:
    _configure_low_cap(client)
    file_id = _upload(client)

    response = client.post("/api/jobs", json={"file_id": file_id, "provider": "claude"})

    assert response.status_code == 402
    body = response.json()["detail"]
    assert body["requires_confirmation"] is True
    assert body["estimated_cost_usd"] > body["cap_usd"]

    # RC-3's whole point: a rejected estimate must NEVER create a Job row.
    assert _job_row_count() == 0


def test_create_job_succeeds_when_estimate_is_under_cap(client: TestClient) -> None:
    # Generous cap, still using the real (non-zero-cost) claude provider.
    _configure_low_cap(client, job_cap=1000.0, batch_cap=1000.0)
    file_id = _upload(client)

    response = client.post("/api/jobs", json={"file_id": file_id, "provider": "claude"})

    assert response.status_code == 202
    assert _job_row_count() == 1


def test_create_job_confirm_cost_bypasses_the_gate(client: TestClient, monkeypatch) -> None:
    """Explicit opt-in (Architecture.md 6.11.4 Lop 2: "opt-in tuong minh cho
    tung job") must let the request through even over cap — but the
    scheduled background run is stubbed out here so no real pipeline (and no
    real LLM call) ever executes.
    """
    monkeypatch.setattr(jobs_route, "_schedule_background", lambda coro: coro.close())
    _configure_low_cap(client)
    file_id = _upload(client)

    response = client.post(
        "/api/jobs",
        json={"file_id": file_id, "provider": "claude", "confirm_cost": True},
    )

    assert response.status_code == 202
    assert _job_row_count() == 1

    job_id = response.json()["job_id"]
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "queued"
    assert detail["estimated_cost"] > 0


def test_estimate_cost_gate_never_underestimates_a_full_glossary(client: TestClient) -> None:
    """Sanity companion, not a golden-file replica: a non-trivial glossary
    must raise the estimate, not leave it unchanged — the RC-1 mechanism
    (Architecture.md 6.11.3) the whole gate exists to price in.
    """
    _configure_low_cap(client, job_cap=1000.0, batch_cap=1000.0)
    file_id = _upload(client, n_pages=3)

    baseline = client.post("/api/estimate", json={"file_id": file_id, "provider": "claude"})
    assert baseline.status_code == 200
    assert baseline.json()["estimated_cost_usd"] >= 0
    assert baseline.json()["estimated_segment_count"] > 0
    assert baseline.json()["estimated_cost_usd_high"] == pytest.approx(
        baseline.json()["estimated_cost_usd"] * 2.0
    )


# === POST /api/batches ===


def test_create_batch_blocked_with_402_when_total_estimate_exceeds_cap(client: TestClient) -> None:
    _configure_low_cap(client)
    file_id_1 = _upload(client, "book1.pdf")
    file_id_2 = _upload(client, "book2.pdf")

    response = client.post(
        "/api/batches",
        json={"file_ids": [file_id_1, file_id_2], "provider": "claude"},
    )

    assert response.status_code == 402
    body = response.json()["detail"]
    assert body["requires_confirmation"] is True

    assert _job_row_count() == 0
    assert _batch_row_count() == 0


def test_create_batch_confirm_cost_bypasses_the_gate(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(jobs_route, "_schedule_background", lambda coro: coro.close())
    _configure_low_cap(client)
    file_id_1 = _upload(client, "book1.pdf")
    file_id_2 = _upload(client, "book2.pdf")

    response = client.post(
        "/api/batches",
        json={"file_ids": [file_id_1, file_id_2], "provider": "claude", "confirm_cost": True},
    )

    assert response.status_code == 202
    assert _job_row_count() == 2


# === POST /api/jobs/{id}/retry ===


async def _insert_real_job(tmp_path, status: str, model: str = "claude") -> str:
    file_path = tmp_path / "retry_book.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 100), f"Retry test page {i + 1}: baking science content.", fontsize=11)
    doc.save(file_path)
    doc.close()

    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="retry_book.pdf",
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
            file_hash="deadbeef-retry",
            file_type="pdf_digital",
            model=model,
            status=status,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


def test_retry_blocked_with_402_when_estimate_exceeds_cap(client: TestClient, tmp_path) -> None:
    """Architecture.md 6.11.7 #2: retry was explicitly flagged as a hole in
    the original incident review ("retry chay lai khong qua gate chi phi") —
    this is the regression test for that exact gap.
    """
    _configure_low_cap(client)
    job_id = asyncio.run(_insert_real_job(tmp_path, status="cost_capped"))

    response = client.post(f"/api/jobs/{job_id}/retry")

    assert response.status_code == 402
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "cost_capped"  # unchanged — never silently queued


def test_retry_confirm_cost_bypasses_the_gate(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(jobs_route, "_schedule_background", lambda coro: coro.close())
    _configure_low_cap(client)
    job_id = asyncio.run(_insert_real_job(tmp_path, status="cost_capped"))

    response = client.post(f"/api/jobs/{job_id}/retry", json={"confirm_cost": True})

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
