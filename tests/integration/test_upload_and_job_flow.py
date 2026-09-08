"""Integration test for the full upload -> job creation -> status check flow
(Increment 5).

The happy-path test uses `job_type="parse_only"` deliberately (not
"translate") — needs no API keys (BR-PARSE-01/05: no LLM call at all). US-15
(Architecture.md 6.15.3 S15-2) changed `create_job()` so `parse_only` now
goes through the SAME "queued" + background `JobOrchestrator.run_job()` path
as `translate` (no more synchronous `_mark_parse_only_unsupported()`), so
this test only asserts the synchronous request/response contract — same
convention as `test_estimate_and_cancel_api.py::test_retry_accepts_cancelled_job_and_clears_cancel_flag`,
which also lets a real background task fire off after `retry`/`create_job`
without waiting on or mocking it. What `run_parse_only()` actually DOES with
a real/fake MinerU is covered separately (with `MinerURunner` injected
directly) in `tests/integration/test_job_orchestrator.py`.

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
    # US-15 S15-2: no more synchronous `_mark_parse_only_unsupported()` —
    # parse_only reaches "queued" exactly like translate does.
    assert job_response.json()["status"] == "queued"
    job_id = job_response.json()["job_id"]

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    detail = status_response.json()
    assert detail["job_type"] == "parse_only"
    assert detail["filename"] == "recipe.pdf"
    # Whatever `run_parse_only()` does in the background (MinerU
    # reachable/unreachable) is intentionally NOT asserted here — see the
    # module docstring for why, and test_job_orchestrator.py for coverage
    # with a fake MinerURunner injected directly.

    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_create_job_resolves_parse_method_auto_default_and_explicit_ocr_override(
    client: TestClient,
) -> None:
    """Architecture.md §6.21.3: `POST /api/jobs` accepts an optional
    `parse_method` (`auto`/`txt`/`ocr`), meaningful only for
    `job_type=parse_only`. `_resolve_parse_method()` (src/api/routes/jobs.py)
    resolves it ONCE at job-creation time and writes the result onto
    `Job.parse_method` — same pattern as `Job.chunk_size_used` never storing
    the request-level default literally. Checked directly against the DB row
    (not exposed on `JobDetail` in this increment) using the same
    `database_module.get_session_factory()` pattern as
    `test_create_job_reports_duplicate_of_completed_job_with_same_hash`
    below.
    """
    import asyncio

    import src.models.database as database_module
    from src.models.job import Job

    async def _read_parse_method(job_id: str) -> str | None:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            return job.parse_method

    pdf_bytes = _make_pdf_bytes()

    # 1) Field omitted entirely -> default "auto" -> pdf_digital maps to
    #    "txt" (unchanged S15 behaviour when the caller sends nothing new).
    upload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", pdf_bytes, "application/pdf")}
    )
    file_id = upload_response.json()["file_id"]
    job_response = client.post("/api/jobs", json={"file_id": file_id, "job_type": "parse_only"})
    assert job_response.status_code == 202
    assert asyncio.run(_read_parse_method(job_response.json()["job_id"])) == "txt"

    # 2) Explicit "ocr" override on a pdf_digital file (the checkbox use
    #    case, §6.21.3 L-4) — must be honoured verbatim, NOT silently
    #    coerced back to the file_type mapping.
    upload_response_2 = client.post(
        "/api/upload", files={"file": ("recipe2.pdf", pdf_bytes, "application/pdf")}
    )
    file_id_2 = upload_response_2.json()["file_id"]
    job_response_2 = client.post(
        "/api/jobs",
        json={"file_id": file_id_2, "job_type": "parse_only", "parse_method": "ocr"},
    )
    assert job_response_2.status_code == 202
    assert asyncio.run(_read_parse_method(job_response_2.json()["job_id"])) == "ocr"

    # 3) job_type="translate": the field has no meaning here (per §6.21.3) —
    #    Job.parse_method must stay NULL even if the client sends it anyway.
    #    provider="ollama" needs no API key (same convention used elsewhere
    #    in this file for a translate-type job).
    upload_response_3 = client.post(
        "/api/upload", files={"file": ("recipe3.pdf", pdf_bytes, "application/pdf")}
    )
    file_id_3 = upload_response_3.json()["file_id"]
    job_response_3 = client.post(
        "/api/jobs",
        json={
            "file_id": file_id_3,
            "job_type": "translate",
            "provider": "ollama",
            "parse_method": "ocr",
        },
    )
    assert job_response_3.status_code == 202
    assert asyncio.run(_read_parse_method(job_response_3.json()["job_id"])) is None


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
    file content after a prior TRANSLATE job for it already completed must
    surface `duplicate_of` instead of silently creating another job.

    US-15 S15-10 regression (Architecture.md 6.15.3, found by Domain
    Expert): `_find_completed_duplicate()` used to match ANY completed job
    regardless of `job_type` — a completed `parse_only` job for the same
    file hash would get reported as "already translated" to a later
    `translate` request (download link pointing at a Markdown ZIP, not a
    translation). This test asserts BOTH directions: a completed
    `parse_only` job must NOT count, and a completed `translate` job still
    must.
    """
    import asyncio

    import src.models.database as database_module
    from src.api.routes.upload import resolve_upload
    from src.models.job import Job

    pdf_bytes = _make_pdf_bytes()

    upload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", pdf_bytes, "application/pdf")}
    )
    upload_meta = resolve_upload(upload_response.json()["file_id"])

    async def _insert_completed_job(job_type: str) -> str:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            job = Job(
                filename=upload_meta.filename,
                file_path=upload_meta.file_path,
                file_size=upload_meta.size_bytes,
                file_hash=upload_meta.file_hash,
                file_type=upload_meta.file_type,
                job_type=job_type,
                model="deepseek",
                status="completed",
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job.completed_at = job.created_at
            session.add(job)
            await session.commit()
            return job.id

    # S15-10 regression: a completed PARSE_ONLY job for this hash must NOT
    # be reported as a duplicate to a later TRANSLATE request.
    parse_job_id = asyncio.run(_insert_completed_job("parse_only"))

    reupload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", pdf_bytes, "application/pdf")}
    )
    assert reupload_response.status_code == 200
    file_id_after_parse = reupload_response.json()["file_id"]

    not_duplicate_response = client.post(
        "/api/jobs",
        # "ollama" needs no API key (same convention as
        # test_estimate_and_cancel_api.py) — isolates this assertion from
        # provider config, which isn't what's under test here.
        json={"file_id": file_id_after_parse, "job_type": "translate", "provider": "ollama"},
    )
    assert not_duplicate_response.status_code == 202
    assert not_duplicate_response.json()["status"] == "queued"
    translate_job_id = not_duplicate_response.json()["job_id"]
    assert translate_job_id != parse_job_id

    async def _mark_completed(job_id: str) -> None:
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            job = await session.get(Job, job_id)
            job.status = "completed"
            job.completed_at = job.completed_at or job.created_at
            session.add(job)
            await session.commit()

    # Now mark THAT translate job completed and confirm AC-12.2's original
    # behavior still holds: a completed TRANSLATE job DOES get reported.
    asyncio.run(_mark_completed(translate_job_id))

    reupload_response_2 = client.post(
        "/api/upload", files={"file": ("recipe.pdf", pdf_bytes, "application/pdf")}
    )
    assert reupload_response_2.status_code == 200
    file_id_after_translate = reupload_response_2.json()["file_id"]

    duplicate_check_response = client.post(
        "/api/jobs", json={"file_id": file_id_after_translate, "job_type": "translate"}
    )
    assert duplicate_check_response.status_code == 200
    body = duplicate_check_response.json()
    assert body["status"] == "duplicate_found"
    assert body["duplicate_of"]["job_id"] == translate_job_id

    # `force: true` bypasses the check and creates a real new job.
    forced_response = client.post(
        "/api/jobs",
        json={"file_id": file_id_after_translate, "job_type": "parse_only", "force": True},
    )
    assert forced_response.status_code == 202
    assert forced_response.json()["job_id"] != translate_job_id


def test_download_before_completion_returns_404(client: TestClient) -> None:
    upload_response = client.post(
        "/api/upload", files={"file": ("recipe.pdf", _make_pdf_bytes(), "application/pdf")}
    )
    file_id = upload_response.json()["file_id"]
    job_response = client.post("/api/jobs", json={"file_id": file_id, "job_type": "parse_only"})
    job_id = job_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/download")
    assert response.status_code == 404


def _minimal_epub_bytes(tmp_path) -> bytes:
    # Reuses the same minimal-EPUB trick as
    # test_estimate_and_cancel_api.py::test_estimate_rejects_epub — a real
    # valid EPUB is annoying to synthesize; the zip magic bytes are enough
    # to pass `detect_file_type()`.
    import zipfile

    epub_path = tmp_path / "book.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<container></container>")
    return epub_path.read_bytes()


def test_create_job_rejects_epub_parse_only_before_creating_job_record(
    client: TestClient, tmp_path
) -> None:
    """US-15 §6.15.3 S15-8 "he qua thu tu lam viec": the EPUB branch of
    parse-only depends on `EpubDocument.to_markdown()` (US-22, out of scope
    for this increment) — a `parse_only` request for an `.epub` file must
    get a clear HTTP 400 with NO `Job` row created, not a job that gets
    created and then fails/hangs inside `JobOrchestrator`.
    """
    upload_response = client.post(
        "/api/upload",
        files={"file": ("book.epub", _minimal_epub_bytes(tmp_path), "application/epub+zip")},
    )
    if upload_response.status_code != 200:
        pytest.skip("Upload rejected this minimal synthetic EPUB before reaching job creation")
    file_id = upload_response.json()["file_id"]

    response = client.post("/api/jobs", json={"file_id": file_id, "job_type": "parse_only"})

    assert response.status_code == 400
    assert "EPUB" in response.json()["detail"]
    assert client.get("/api/jobs").json()["total"] == 0


def test_create_batch_schedules_parse_only_jobs_instead_of_marking_failed(
    client: TestClient, monkeypatch
) -> None:
    """US-15 S15-2 "MO RONG sau phan bien Domain Expert" (Architecture.md
    6.15.3): the original S15-2 fix only covered `create_job()` —
    `create_batch()` had its OWN, separate call to
    `_mark_parse_only_unsupported()` per job plus `batch.status = "failed"`,
    so a batch of `parse_only` jobs still died even after the single-job fix.
    Both jobs must reach "queued" and the batch must reach "processing", with
    exactly one `_run_batch_background()` scheduled — not the old immediate
    `batch.status="failed"` + `failed_files=len(jobs)`.
    """
    import src.api.routes.jobs as jobs_route

    scheduled: list[object] = []
    monkeypatch.setattr(
        jobs_route,
        "_schedule_background",
        lambda coro: (scheduled.append(coro), coro.close()),
    )

    file_ids = []
    for name in ("recipe1.pdf", "recipe2.pdf"):
        upload_response = client.post(
            "/api/upload", files={"file": (name, _make_pdf_bytes(), "application/pdf")}
        )
        assert upload_response.status_code == 200
        file_ids.append(upload_response.json()["file_id"])

    response = client.post(
        "/api/batches", json={"file_ids": file_ids, "job_type": "parse_only"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert len(body["job_ids"]) == 2
    assert len(scheduled) == 1  # exactly one _run_batch_background(), not per-job

    for job_id in body["job_ids"]:
        detail = client.get(f"/api/jobs/{job_id}").json()
        assert detail["job_type"] == "parse_only"
        assert detail["status"] == "queued"
