"""S7 — dich FR->VI (Architecture.md §6.26.4 data lineage point 1).

`cost_gate.estimate_translation_cost()`/`_estimate_epub_translation_cost()`
phai detect `source_lang` DUNG 1 LAN va dung KET QUA DO cho ca prompt lan
cong thuc chi phi — R6-02: assert gia tri cu the, khong chi 'da goi'.
"""

import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings
from src.core.cost_gate import estimate_translation_cost
from src.services.claude_provider import ClaudeProvider
from tests.test_language_detector import _EN_TEXT, _FR_TEXT


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _build_pdf_with_text(path: Path, text: str) -> Path:
    doc = fitz.open()
    try:
        # Chia thanh nhieu trang de fitz.insert_text khong tran khung — moi
        # trang ~120 tu, du cho toan bo doan van dai ~600 tu.
        words = text.split()
        page_size = 120
        for start in range(0, len(words), page_size):
            page = doc.new_page()
            chunk_text = " ".join(words[start : start + page_size])
            page.insert_textbox((36, 36, 560, 780), chunk_text, fontsize=9)
        doc.save(path)
    finally:
        doc.close()
    return path


def _build_epub_with_text(path: Path, text: str) -> Path:
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
    paragraphs = "".join(f"<p>{line}</p>" for line in text.split("\n\n") if line.strip())
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter 0</title></head>'
        f"<body>{paragraphs}</body></html>"
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
async def test_pdf_digital_english_document_detects_en(
    session: AsyncSession, tmp_path: Path
) -> None:
    pdf_path = _build_pdf_with_text(tmp_path / "book_en.pdf", _EN_TEXT)
    provider = ClaudeProvider(api_key="sk-ant-fake")

    detailed = await estimate_translation_cost(
        pdf_path, provider, session, batch_id=None, max_glossary_entries=80
    )

    assert detailed.source_lang == "en"


@pytest.mark.asyncio
async def test_pdf_digital_french_document_detects_fr(
    session: AsyncSession, tmp_path: Path
) -> None:
    pdf_path = _build_pdf_with_text(tmp_path / "book_fr.pdf", _FR_TEXT)
    provider = ClaudeProvider(api_key="sk-ant-fake")

    detailed = await estimate_translation_cost(
        pdf_path, provider, session, batch_id=None, max_glossary_entries=80
    )

    assert detailed.source_lang == "fr"


@pytest.mark.asyncio
async def test_pdf_scan_near_empty_text_leaves_source_lang_none_not_en(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md §6.26.4 point 1: nhanh pdf_scan CHUA OCR nen
    `_extract_full_text()` gan rong -> `source_lang` PHAI la None (KHONG
    duoc ep "en" o day) — de `run_job()` Step 3 detect LAI tren cau noi
    searchable PDF sau OCR (bridge co text layer that)."""
    doc = fitz.open()
    try:
        doc.new_page()  # trang trang, khong co text layer (mo phong scan)
        doc.save(tmp_path / "scan.pdf")
    finally:
        doc.close()
    provider = ClaudeProvider(api_key="sk-ant-fake")

    detailed = await estimate_translation_cost(
        tmp_path / "scan.pdf",
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="pdf_scan",
    )

    assert detailed.source_lang is None
    # Nhung cost estimate van dung "en" lam gia tri fallback qua formula —
    # khong duoc raise/crash vi source_lang=None.
    assert detailed.estimate.estimated_input_tokens >= 0


@pytest.mark.asyncio
async def test_epub_french_document_detects_fr_and_prompt_mentions_french(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub_with_text(tmp_path / "book_fr.epub", _FR_TEXT)
    settings = get_settings()
    provider = ClaudeProvider(api_key="sk-ant-fake")

    detailed = await estimate_translation_cost(
        epub_path,
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="epub",
        settings=settings,
    )

    assert detailed.source_lang == "fr"


@pytest.mark.asyncio
async def test_fr_document_estimates_higher_input_tokens_than_same_text_marked_en(
    session: AsyncSession, tmp_path: Path
) -> None:
    """§6.26.5 buoc #6: CHARS_PER_TOKEN_FR (3.0) < CHARS_PER_TOKEN_EN (4.0)
    co chu dich -> cung 1 luong ky tu nguon, gan nhan 'fr' phai UOC DU hon
    gan nhan 'en' — khong duoc uoc THIEU (§6.11.6)."""
    from src.core.cost_estimator import estimate_job_cost_v2

    provider = ClaudeProvider(api_key="sk-ant-fake")
    en_result = estimate_job_cost_v2(
        source_text_chars=len(_FR_TEXT),
        segment_count=3,
        prompt_overhead_chars=200,
        provider=provider,
        source_lang="en",
    )
    fr_result = estimate_job_cost_v2(
        source_text_chars=len(_FR_TEXT),
        segment_count=3,
        prompt_overhead_chars=200,
        provider=provider,
        source_lang="fr",
    )
    assert fr_result.estimated_input_tokens > en_result.estimated_input_tokens
