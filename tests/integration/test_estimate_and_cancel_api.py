"""Increment 6 API tests:

- `POST /api/estimate` (Nhiem vu 1a) — must NEVER create a `Job`/`Batch` row,
  unlike the old `estimateCost()` frontend flow that piggybacked on
  `POST /api/jobs` (see docs/CHANGELOG.md "Increment 6" for the root cause).
- `POST /api/jobs/{id}/cancel` (Nhiem vu 3) — flags a running job for
  graceful cancel without stopping it synchronously, and `POST
  /api/jobs/{id}/retry` must accept a `cancelled` job the same way it already
  accepts a `failed` one.

Fixture setup mirrors `tests/integration/test_upload_and_job_flow.py`
(isolated `tmp_path` DB, `TestClient` lifespan) rather than importing it, to
stay consistent with how `test_job_orchestrator.py`/`test_batch_orchestrator.py`
each define their own fixtures in this codebase.
"""

import asyncio
import tempfile
from collections.abc import Iterator
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlmodel import func, select

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_settings
from src.models.job import Job


def _build_valid_epub(path: Path) -> Path:
    """1 EPUB toi thieu nhung hop le ve OCF (mimetype STORED dau file,
    container.xml + OPF + spine dung), khac synthetic `book.epub` cua
    `test_estimate_rejects_malformed_epub()` (thieu rootfile). Cung
    khuon voi `_build_minimal_epub()` trong tests/test_epub_document.py,
    duplicate co chu dich — file test nay tu quan ly fixture rieng, dung
    convention da co cua module (xem docstring dau file)."""
    import zipfile

    container_xml = (
        '<?xml version="1.0"?>\n'
        '<container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
        'unique-identifier="bookid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Test Book</dc:title><dc:language>en</dc:language>"
        '<dc:identifier id="bookid">urn:uuid:test-book</dc:identifier>'
        "</metadata>"
        '<manifest><item id="chap1" href="chap1.xhtml" '
        'media-type="application/xhtml+xml"/>'
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
        '<spine toc="ncx"><itemref idref="chap1"/></spine></package>'
    )
    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        '<head><meta name="dtb:uid" content="urn:uuid:test-book"/></head>'
        "<docTitle><text>Test Book</text></docTitle>"
        '<navMap><navPoint id="np1" playOrder="1"><navLabel><text>Chapter 1</text>'
        '</navLabel><content src="chap1.xhtml"/></navPoint></navMap></ncx>'
    )
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        "<head><title>Chapter 1</title></head>"
        "<body><p>2 cups flour, 1 tsp salt, 350F oven.</p></body></html>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.ncx", ncx)
        zf.writestr("OEBPS/chap1.xhtml", xhtml)
    return path


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


async def _insert_job(
    status: str,
    cancel_requested: bool = False,
    tmp_path: Path | None = None,
    job_type: str = "translate",
    model: str = "ollama",
) -> str:
    # Architecture.md 6.11.4 Lop 2: POST /api/jobs/{id}/retry now runs a real
    # cost-gate estimate (PyMuPDF text extraction over `file_path`), so this
    # fixture needs an actual readable PDF on disk instead of a fake path —
    # "ollama" is used as `model` because it needs no API key (estimate_cost
    # is always 0), keeping this test independent of any provider config.
    file_path = (tmp_path or Path(tempfile.mkdtemp())) / "book.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Recipe: 2 cups flour", fontsize=11)
    doc.save(file_path)
    doc.close()

    session_factory = database_module.get_session_factory()
    async with session_factory() as session:
        job = Job(
            filename="book.pdf",
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
            file_hash="deadbeef",
            file_type="pdf_digital",
            job_type=job_type,
            model=model,
            status=status,
            cancel_requested=cancel_requested,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


# === POST /api/estimate ===


def test_estimate_does_not_create_job_row(client: TestClient) -> None:
    upload_response = client.post(
        "/api/upload", files={"file": ("book.pdf", _make_pdf_bytes(3), "application/pdf")}
    )
    assert upload_response.status_code == 200
    file_id = upload_response.json()["file_id"]

    assert _job_row_count() == 0

    # "ollama" needs no API key (only a non-empty endpoint, which has a
    # `.env`-independent default in Settings) — avoids coupling this test to
    # any provider's key configuration.
    estimate_response = client.post(
        "/api/estimate", json={"file_id": file_id, "provider": "ollama"}
    )
    assert estimate_response.status_code == 200
    body = estimate_response.json()
    assert body["total_pages"] == 3
    assert body["estimated_input_tokens"] > 0
    assert body["cost_source"] == "estimated"

    # The whole point of this endpoint (bug fix): calling it must NEVER
    # create a Job — the old `estimateCost()` frontend flow used to call
    # `POST /api/jobs` for this and silently start a real translation.
    assert _job_row_count() == 0
    assert client.get("/api/jobs").json()["total"] == 0


def test_estimate_unknown_file_id_returns_404(client: TestClient) -> None:
    response = client.post("/api/estimate", json={"file_id": "does-not-exist"})
    assert response.status_code == 404
    assert _job_row_count() == 0


def test_estimate_rejects_malformed_epub(client: TestClient, tmp_path) -> None:
    """Architecture.md 6.20.6 (US-22 buoc 2/3): EPUB khong con bi chan cung o
    day nua (bo 2 nhanh `if file_type == "epub": raise 400` cu) — nhung 1
    EPUB khong doc duoc (thieu `<rootfile full-path=...>` trong
    container.xml) van phai tra 400 qua `EpubParseError` ->
    `_estimate_translation_cost_or_400()`, khong phai 500 tho."""
    import zipfile

    epub_path = tmp_path / "book.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<container></container>")

    upload_response = client.post(
        "/api/upload",
        files={"file": ("book.epub", epub_path.read_bytes(), "application/epub+zip")},
    )
    if upload_response.status_code != 200:
        pytest.skip("Upload rejected this minimal synthetic EPUB before reaching estimate logic")
    file_id = upload_response.json()["file_id"]

    response = client.post("/api/estimate", json={"file_id": file_id, "provider": "ollama"})
    assert response.status_code == 400
    assert _job_row_count() == 0


def test_estimate_accepts_valid_epub(client: TestClient, tmp_path) -> None:
    """Architecture.md 6.20.6: a well-formed EPUB now estimates successfully
    (no total_pages, but total_units + a real, non-zero cost estimate) —
    this is the exact case the 2 hard-coded 400s used to block outright."""
    epub_path = _build_valid_epub(tmp_path / "book.epub")

    upload_response = client.post(
        "/api/upload",
        files={"file": ("book.epub", epub_path.read_bytes(), "application/epub+zip")},
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["page_count"] is None
    file_id = upload_response.json()["file_id"]

    response = client.post("/api/estimate", json={"file_id": file_id, "provider": "ollama"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_pages"] is None
    assert body["total_units"] == 1
    assert body["estimated_input_tokens"] > 0
    assert _job_row_count() == 0


# === POST /api/jobs/{id}/cancel + retry(cancelled) ===


def test_cancel_flags_a_running_job_without_changing_status_synchronously(
    client: TestClient,
) -> None:
    job_id = asyncio.run(_insert_job(status="translating"))

    response = client.post(f"/api/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["cancel_requested"] is True
    # Graceful cancel: the flag is set, but JobOrchestrator (not this
    # endpoint) is what eventually flips status -> "cancelled", after the
    # chunk in flight finishes.
    assert body["status"] == "translating"

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["cancel_requested"] is True
    assert detail["status"] == "translating"


def test_cancel_rejects_a_terminal_job(client: TestClient) -> None:
    job_id = asyncio.run(_insert_job(status="completed"))

    response = client.post(f"/api/jobs/{job_id}/cancel")
    assert response.status_code == 400


def test_cancel_unknown_job_returns_404(client: TestClient) -> None:
    response = client.post("/api/jobs/does-not-exist/cancel")
    assert response.status_code == 404


def test_retry_accepts_cancelled_job_and_clears_cancel_flag(client: TestClient) -> None:
    job_id = asyncio.run(_insert_job(status="cancelled", cancel_requested=True))

    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["cancel_requested"] is False


def test_retry_still_rejects_a_non_terminal_job(client: TestClient) -> None:
    job_id = asyncio.run(_insert_job(status="translating"))

    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 400


def test_retry_accepts_failed_parse_only_job_without_cost_gate(client: TestClient) -> None:
    """US-15 S15-11 regression (Architecture.md 6.15.3, found by Domain
    Expert): `retry_job()` used to unconditionally reject `parse_only`
    (400) AND run every retry through `_resolve_provider_or_400` +
    `_enforce_cost_gate` — directly contradicting S15-9's own design ("fail
    fast when MinerU isn't running, let the user retry once it's up"): a
    parse_only job would fail fast as designed, then be permanently stuck
    (400 forever on retry), forcing a fresh upload. `model=
    "totally-bogus-provider"` here would fail `_resolve_provider_or_400`
    if that code path still ran — proving the cost gate is actually
    skipped for parse_only, not just that the 400 rejection was removed.
    """
    job_id = asyncio.run(
        _insert_job(status="failed", job_type="parse_only", model="totally-bogus-provider")
    )

    response = client.post(f"/api/jobs/{job_id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["job_type"] == "parse_only"
    assert detail["status"] == "queued"
    assert detail["error_message"] is None


def test_retry_translate_job_still_goes_through_cost_gate(client: TestClient) -> None:
    """Companion negative test: a `translate` retry with the same bogus
    `model` must still be rejected — proves the skip above is scoped to
    `job_type == "parse_only"`, not a blanket removal of the cost gate.
    """
    job_id = asyncio.run(
        _insert_job(status="failed", job_type="translate", model="totally-bogus-provider")
    )

    response = client.post(f"/api/jobs/{job_id}/retry")

    assert response.status_code == 400
