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
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

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


@pytest.mark.asyncio
async def test_lineage_epub_not_yet_supported_raises_clearly() -> None:
    """US-22 hasn't shipped `EpubDocument.full_text()` yet — this branch
    must fail loudly (not silently return empty text) if ever reached.
    """
    job = _make_job(file_type="epub", file_path="book.epub")

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
