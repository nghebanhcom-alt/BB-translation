"""US-20 "Các từ mới" — data lineage (Architecture.md §6.18.5, Protocol 6
R6-01/R6-02) and the DB/orchestration glue in
`src/core/term_extraction_service.py`.

Protocol 6 R6-02: these tests assert the SPECIFIC file each `file_type`
branch actually read (not just "extraction was called") — the dedicated
lineage tests below each set up a decoy file that would silently succeed if
the wrong path were read, exactly the shape of bug Bug #5 was.
"""

import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.term_extraction_service import (
    TermExtractionSourceError,
    _extract_source_text_for_terms,
    extract_and_store_terms,
)
from src.models.database import _create_composite_indexes
from src.models.glossary import Glossary, GlossaryEntry
from src.models.job import Job
from src.models.suggested_term import SuggestedTerm

_REAL_GLOSSARY_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "term_extraction"
    / "real_glossary_114.json"
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    # Reviewer BL-20 rerun-bug review (2026-09-17): must share the same
    # index-creation code path as init_db() (_create_composite_indexes),
    # not just create_all() — otherwise the test DB is missing the
    # UNIQUE (job_id, term_en) constraint production always has, and a
    # rerun test can pass without ever hitting the IntegrityError it's
    # meant to guard against.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await _create_composite_indexes(conn)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _make_pdf(path: Path, text: str) -> None:
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 100), text, fontsize=10)
        doc.save(path)


def _make_job(**overrides: object) -> Job:
    defaults: dict[str, object] = {
        "filename": "book.pdf",
        "file_path": "unused.pdf",
        "file_size": 100,
        "file_hash": "hash",
        "file_type": "pdf_digital",
        "job_type": "translate",
        "model": "deepseek",
        "status": "completed",
    }
    defaults.update(overrides)
    return Job(**defaults)


# --- Lineage (Architecture.md §6.18.5) --------------------------------------


@pytest.mark.asyncio
async def test_lineage_pdf_digital_reads_file_path(tmp_path: Path) -> None:
    pdf_path = tmp_path / "digital.pdf"
    _make_pdf(pdf_path, "laminated dough gluten development")
    job = _make_job(file_type="pdf_digital", file_path=str(pdf_path))

    text = await _extract_source_text_for_terms(job)

    assert "laminated dough gluten development" in text


@pytest.mark.asyncio
async def test_lineage_pdf_scan_reads_ocr_bridge_path_not_file_path(tmp_path: Path) -> None:
    """R6-02: file_path deliberately points at a DECOY PDF with different
    text — a wrong-file bug must fail this assertion, not just "was called".
    """
    decoy_path = tmp_path / "scan_original.pdf"
    _make_pdf(decoy_path, "THIS MUST NEVER BE READ FOR PDF SCAN")
    bridge_path = tmp_path / "searchable.pdf"
    _make_pdf(bridge_path, "gluten development after ocr bridge")

    job = _make_job(
        file_type="pdf_scan", file_path=str(decoy_path), ocr_bridge_path=str(bridge_path)
    )

    text = await _extract_source_text_for_terms(job)

    assert "gluten development after ocr bridge" in text
    assert "THIS MUST NEVER BE READ" not in text


@pytest.mark.asyncio
async def test_lineage_pdf_scan_missing_ocr_bridge_path_raises_instead_of_silent_empty(
    tmp_path: Path,
) -> None:
    """Bug #5's exact shape: reading `job.file_path` (the raw scan, 0
    readable characters) instead of the bridge would silently produce an
    empty suggestion list. This must raise loudly instead.
    """
    job = _make_job(file_type="pdf_scan", file_path="unused.pdf", ocr_bridge_path=None)

    with pytest.raises(TermExtractionSourceError):
        await _extract_source_text_for_terms(job)


@pytest.mark.asyncio
async def test_lineage_parse_only_reads_document_md_sibling_of_zip_not_the_zip_bytes(
    tmp_path: Path,
) -> None:
    """S15-4: `job.output_path` for parse_only now points at
    `parse_result.zip`, NOT `.md` — the lineage function must read
    `document.md` from the SAME directory, never the zip's raw bytes.
    """
    output_dir = tmp_path / "outputs" / "job1"
    output_dir.mkdir(parents=True)
    md_path = output_dir / "document.md"
    md_path.write_text("# Chapter\n\nlaminated dough content here", encoding="utf-8")
    zip_path = output_dir / "parse_result.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(md_path, arcname="document.md")

    job = _make_job(job_type="parse_only", output_path=str(zip_path))

    text = await _extract_source_text_for_terms(job)

    assert "laminated dough content here" in text
    # A wrong-file bug (reading the zip's raw bytes as text) would decode
    # garbage instead of clean Markdown — assert we got real text, not that.
    assert "PK" != text[:2]


@pytest.mark.asyncio
async def test_lineage_parse_only_missing_document_md_raises(tmp_path: Path) -> None:
    zip_path = tmp_path / "parse_result.zip"
    zip_path.write_bytes(b"not a real zip, document.md missing")
    job = _make_job(job_type="parse_only", output_path=str(zip_path))

    with pytest.raises(TermExtractionSourceError):
        await _extract_source_text_for_terms(job)


def _build_epub(path: Path, paragraphs: list[str]) -> Path:
    """Real EPUB bytes written directly with `zipfile` (same pattern as
    `tests/integration/test_epub_job_source_lang.py::_build_epub`) — NOT a
    hand-written mock of `EpubDocument`, so `EpubDocument.load()` parses a
    genuine zip/OPF/spine structure (R5-03).
    """
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
        '<manifest><item id="chap0" href="chap0.xhtml" media-type="application/xhtml+xml"/>'
        "</manifest>"
        '<spine><itemref idref="chap0"/></spine></package>'
    )
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter 0</title></head>'
        f"<body>{body}</body></html>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/chap0.xhtml", xhtml)
    return path


@pytest.mark.asyncio
async def test_lineage_epub_reads_full_text_not_inner_html(tmp_path: Path) -> None:
    """BL-20 (Architecture.md §6.27.2): must read
    `EpubDocument.load(job.file_path).full_text()` — plain text with inline
    tags stripped, NOT `EpubUnit.text` (inner-HTML), and NOT
    `job.output_path` (the translated file).
    """
    epub_path = tmp_path / "book.epub"
    _build_epub(
        epub_path,
        ["Laminated <strong>dough</strong> rests overnight in the fridge."],
    )
    job = _make_job(file_type="epub", file_path=str(epub_path))

    text = await _extract_source_text_for_terms(job)

    assert "Laminated dough rests overnight in the fridge." in text
    assert "<strong" not in text
    assert "<p" not in text


@pytest.mark.asyncio
async def test_lineage_epub_bad_file_raises_term_extraction_source_error(tmp_path: Path) -> None:
    """`EpubDocument.load()` raises `EpubParseError` for a corrupt file —
    the lineage function must wrap it as `TermExtractionSourceError` so
    `POST /api/jobs/{id}/extract-terms` returns 400, not an unwrapped 500
    (Architecture.md §6.18.6/§6.27.2).
    """
    bad_path = tmp_path / "book.epub"
    bad_path.write_bytes(b"not a real zip file")
    job = _make_job(file_type="epub", file_path=str(bad_path))

    with pytest.raises(TermExtractionSourceError):
        await _extract_source_text_for_terms(job)


# --- extract_and_store_terms() end to end -----------------------------------


@pytest.mark.asyncio
async def test_extract_and_store_terms_writes_pending_rows(
    tmp_path: Path, session: AsyncSession
) -> None:
    pdf_path = tmp_path / "book.pdf"
    text = (
        "Laminated dough rests overnight in the fridge. "
        "Laminated dough needs careful folding technique. "
        "Laminated dough is used for croissants here."
    )
    _make_pdf(pdf_path, text)

    job = _make_job(id="job1", file_type="pdf_digital", file_path=str(pdf_path))
    session.add(job)
    await session.commit()

    written = await extract_and_store_terms("job1", session, Settings())

    assert written > 0
    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    assert len(rows) == written
    assert all(row.status == "pending" for row in rows)
    keys = {row.match_key for row in rows}
    assert "laminated dough" in keys


@pytest.mark.asyncio
async def test_extract_and_store_terms_writes_pending_rows_for_completed_epub_job(
    tmp_path: Path, session: AsyncSession
) -> None:
    """BL-20 (Architecture.md §6.27, design-log "RCA BL-20" mục 6 #2): R6-02
    end-to-end at the level `_run_job_background()` (`src/api/routes/jobs.py`)
    calls after a job reaches `status == "completed"` — asserts the SPECIFIC
    value (`suggested_terms` rows derived from the real EPUB source text),
    not just that the call happened.
    """
    epub_path = tmp_path / "book.epub"
    _build_epub(
        epub_path,
        [
            "Laminated dough rests overnight in the fridge.",
            "Laminated dough needs careful folding technique.",
            "Laminated dough is used for croissants here.",
        ],
    )
    job = _make_job(id="job1", file_type="epub", file_path=str(epub_path))
    session.add(job)
    await session.commit()

    written = await extract_and_store_terms("job1", session, Settings())

    assert written > 0
    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    assert len(rows) == written
    assert all(row.status == "pending" for row in rows)
    keys = {row.match_key for row in rows}
    assert "laminated dough" in keys


@pytest.mark.asyncio
async def test_extract_and_store_terms_only_runs_for_completed_status(
    session: AsyncSession,
) -> None:
    job = _make_job(id="job1", status="translating")
    session.add(job)
    await session.commit()

    with pytest.raises(TermExtractionSourceError):
        await extract_and_store_terms("job1", session, Settings())


@pytest.mark.asyncio
async def test_extract_and_store_terms_disabled_by_kill_switch_writes_nothing(
    tmp_path: Path, session: AsyncSession
) -> None:
    pdf_path = tmp_path / "book.pdf"
    _make_pdf(pdf_path, "laminated dough laminated dough laminated dough")
    job = _make_job(id="job1", file_path=str(pdf_path))
    session.add(job)
    await session.commit()

    written = await extract_and_store_terms(
        "job1", session, Settings(term_extraction_enabled=False)
    )

    assert written == 0
    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_extract_and_store_terms_filters_against_real_glossary_scoped_global(
    tmp_path: Path, session: AsyncSession
) -> None:
    """BR-GLOSS-06 (global + project scope) — glossary entries stored in the
    DB (not passed in directly) must actually be applied.
    """
    glossary = Glossary(name="global", scope="global")
    session.add(glossary)
    await session.flush()
    session.add(
        GlossaryEntry(glossary_id=glossary.id, term_en="laminated dough", term_vi="bot cuon lop")
    )
    await session.commit()

    pdf_path = tmp_path / "book.pdf"
    text = " ".join(["Laminated dough needs careful folding technique here."] * 3)
    _make_pdf(pdf_path, text)
    job = _make_job(id="job1", file_path=str(pdf_path))
    session.add(job)
    await session.commit()

    await extract_and_store_terms("job1", session, Settings())

    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    keys = {row.match_key for row in rows}
    assert "laminated dough" not in keys


@pytest.mark.asyncio
async def test_extract_and_store_terms_rerun_preserves_decided_rows_refreshes_pending(
    tmp_path: Path, session: AsyncSession
) -> None:
    """BR-TERM-04-adjacent idempotency: a manual re-run (POST
    .../extract-terms) must not un-dismiss/un-add a term the user already
    decided on, but SHOULD refresh stale 'pending' rows.
    """
    pdf_path = tmp_path / "book.pdf"
    text = (
        "Laminated dough rests overnight in the fridge. "
        "Laminated dough needs careful folding technique. "
        "Laminated dough is used for croissants here."
    )
    _make_pdf(pdf_path, text)
    job = _make_job(id="job1", file_path=str(pdf_path))
    session.add(job)
    await session.commit()

    await extract_and_store_terms("job1", session, Settings())
    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    target = next(row for row in rows if row.match_key == "laminated dough")
    target.status = "dismissed"
    session.add(target)
    await session.commit()

    await extract_and_store_terms("job1", session, Settings())

    rows_after = (
        await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))
    ).all()
    dismissed_rows = [r for r in rows_after if r.match_key == "laminated dough"]
    assert len(dismissed_rows) == 1
    assert dismissed_rows[0].status == "dismissed"


@pytest.mark.asyncio
async def test_extract_and_store_terms_rerun_with_all_rows_still_pending_does_not_raise(
    tmp_path: Path, session: AsyncSession
) -> None:
    """QA test-report.md "BL-20 — QA gate cuoi (2026-09-17)": calling
    `extract_and_store_terms()` a 2nd time while EVERY existing row is still
    `pending` (nobody accepted/dismissed anything yet — the common case for a
    plain "extract again" rerun) must NOT raise `sqlite3.IntegrityError` on
    the `(job_id, term_en)` UNIQUE constraint. The older rerun test above
    dismisses its target row before rerunning, which accidentally sidesteps
    this exact conflict — this test deliberately leaves every row `pending`.
    """
    pdf_path = tmp_path / "book.pdf"
    text = (
        "Laminated dough rests overnight in the fridge. "
        "Laminated dough needs careful folding technique. "
        "Laminated dough is used for croissants here."
    )
    _make_pdf(pdf_path, text)
    job = _make_job(id="job1", file_path=str(pdf_path))
    session.add(job)
    await session.commit()

    first_written = await extract_and_store_terms("job1", session, Settings())
    assert first_written > 0
    first_rows = (
        await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))
    ).all()
    assert all(row.status == "pending" for row in first_rows)

    second_written = await extract_and_store_terms("job1", session, Settings())

    assert second_written == first_written
    rows_after = (
        await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))
    ).all()
    assert len(rows_after) == second_written
    assert all(row.status == "pending" for row in rows_after)
    keys = {row.match_key for row in rows_after}
    assert "laminated dough" in keys


@pytest.mark.asyncio
async def test_extract_and_store_terms_real_glossary_114_end_to_end(
    tmp_path: Path, session: AsyncSession
) -> None:
    """Architecture.md §6.18.8 T8 gate #3, run through the FULL service
    (DB glossary read + extraction), not just the pure algorithm.
    """
    real_terms = json.loads(_REAL_GLOSSARY_PATH.read_text(encoding="utf-8"))
    glossary = Glossary(name="global", scope="global")
    session.add(glossary)
    await session.flush()
    for term_en in real_terms:
        session.add(GlossaryEntry(glossary_id=glossary.id, term_en=term_en, term_vi=None))
    await session.commit()

    pdf_path = tmp_path / "book.pdf"
    text = " ".join(
        [
            "Weigh one pound of butter and one ounce of chocolate for the bloom test.",
            "Tempering the chocolate takes patience; kneading the dough builds gluten.",
            "Use a teaspoon of vanilla. Whipping cream is folded in gently.",
        ]
        * 3
    )
    _make_pdf(pdf_path, text)
    job = _make_job(id="job1", file_path=str(pdf_path))
    session.add(job)
    await session.commit()

    await extract_and_store_terms("job1", session, Settings())

    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    surfaces_lower = {row.term_en.lower() for row in rows}
    for leaked_term in ("pound", "ounce", "bloom", "tempering", "kneading", "teaspoon", "whipping"):
        assert leaked_term not in surfaces_lower


# === S7 — dich FR->VI (Architecture.md §6.26.5 audit buoc #13, R8-02) ======
#
# `term_extractor._load_function_words()` chi nap en_function_words.txt — hu
# tu tieng Phap khong bi loc, ung vien n-gram thanh rac. SKIP cho job FR
# (deny-by-default), guard dat trong `extract_and_store_terms()` (khong phai
# rieng jobs.py:537) de ca duong tu dong LAN duong thu cong /extract-terms
# deu duoc bao ve.


@pytest.mark.asyncio
async def test_extract_and_store_terms_skips_for_source_lang_fr(
    tmp_path: Path, session: AsyncSession
) -> None:
    pdf_path = tmp_path / "book_fr.pdf"
    _make_pdf(pdf_path, "levain levain levain croissant croissant croissant")
    job = _make_job(id="job1", file_path=str(pdf_path), source_lang="fr")
    session.add(job)
    await session.commit()

    written = await extract_and_store_terms("job1", session, Settings())

    assert written == 0
    rows = (await session.exec(select(SuggestedTerm).where(SuggestedTerm.job_id == "job1"))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_extract_and_store_terms_runs_for_source_lang_none_treated_as_en(
    tmp_path: Path, session: AsyncSession
) -> None:
    """NULL == "en" (deny-by-default cho FR, KHONG deny cho job EN cu/chua
    detect) — job truoc S7 khong bi mat tinh nang US-20."""
    pdf_path = tmp_path / "book.pdf"
    _make_pdf(pdf_path, "laminated dough laminated dough laminated dough")
    job = _make_job(id="job1", file_path=str(pdf_path), source_lang=None)
    session.add(job)
    await session.commit()

    written = await extract_and_store_terms("job1", session, Settings())

    assert written > 0
