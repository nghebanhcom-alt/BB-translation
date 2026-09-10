"""Fix cho `prompt_overhead_chars` cua nhanh EPUB trong `cost_gate.py`
(Architecture.md 6.20.13.6, fix C-2, Protocol 6 data lineage).

Truoc fix: `_estimate_epub_translation_cost()` do overhead bang
`build_prompt_text()` — prompt cua NHANH PDF (co `${text}` placeholder,
footer rieng cua pdf2zh) — chu KHONG PHAI chuoi that `_process_epub_chunk()`
gui cho LLM. Sau fix: phai do DUNG artifact `build_epub_batch_prompt(
build_system_prompt(...))` ma runtime EPUB thuc su gui — day la "soi day"
Protocol 6 giua Lop 2 (uoc chi phi truoc khi chay) va nhanh thuc thi that.
"""

import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.chunking import plan_epub_chunks
from src.core.config import Settings
from src.core.cost_gate import estimate_translation_cost
from src.core.glossary_manager import GlossaryManager
from src.core.prompt_builder import build_epub_batch_prompt, build_prompt_text, build_system_prompt
from src.models.glossary import Glossary, GlossaryEntry
from src.services.claude_provider import ClaudeProvider
from src.services.epub_document import EpubDocument


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _build_epub(path: Path) -> Path:
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
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter 0</title></head>'
        "<body><p>Mix <strong>2 cups</strong> flour with active dry yeast and let it "
        "rise before baking at 350F.</p></body></html>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/chap0.xhtml", xhtml)
    return path


def _build_epub_multi_unit(path: Path, n_paragraphs: int = 12) -> Path:
    """Nhu `_build_epub()` nhung nhieu `<p>` rieng biet — can thiet cho test
    A-4 (`epub_request_max_units` chi co tac dung khi sach co > 1 unit;
    `_build_epub()` chi co dung 1 unit nen khong bao gio lam segment_count
    thay doi theo `request_max_units`)."""
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
    paragraphs = "".join(
        f"<p>Mix <strong>{i} cups</strong> flour with active dry yeast, step {i}.</p>"
        for i in range(n_paragraphs)
    )
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
async def test_estimate_epub_translation_cost_prompt_overhead_matches_real_runtime_prompt(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 (Architecture.md 6.20.13.6): chuoi ma Lop 2 do phai BANG chuoi
    ma `_process_epub_chunk()` (job_orchestrator.py) thuc su gui cho
    `provider.translate()` tren CUNG 1 job/glossary — khong chi
    `assert_called()`, ma assert GIA TRI CU THE bang nhau."""
    epub_path = _build_epub(tmp_path / "book.epub")
    glossary = Glossary(name="global", scope="global")
    session.add(glossary)
    await session.flush()
    session.add(GlossaryEntry(glossary_id=glossary.id, term_en="flour", term_vi="bot mi"))
    await session.commit()

    provider = ClaudeProvider(api_key="sk-ant-fake")
    detailed = await estimate_translation_cost(
        epub_path,
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="epub",
        settings=Settings(),
    )

    # Chuoi THAT ma job_orchestrator.py::run_epub_job() gui di — CUNG cach
    # goi build_system_prompt() (only_terms_present_in=doc.full_text()).
    doc = EpubDocument.load(epub_path)
    glossary_manager = GlossaryManager(session)
    real_system_prompt = await build_system_prompt(
        glossary_manager,
        project_id=None,
        only_terms_present_in=doc.full_text(),
        max_glossary_entries=80,
    )
    real_prompt = build_epub_batch_prompt(real_system_prompt)

    assert detailed.prompt_overhead_chars == len(real_prompt)


@pytest.mark.asyncio
async def test_estimate_epub_translation_cost_overhead_higher_than_old_pdf_formula(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Bao ve regression cho C-2 (uoc THAP he thong, §6.11.6 cam uoc thap):
    truoc fix, overhead duoc do bang `build_prompt_text()` (prompt pdf2zh,
    co placeholder `${text}` bi tru di) — chuoi nay LUON ngan hon chuoi EPUB
    that (khong co placeholder, cong them `_EPUB_BATCH_CONTRACT` + one-shot
    ~1.400 ky tu). Neu ai vo tinh doi cost_gate.py quay lai dung
    build_prompt_text() cho nhanh EPUB, test nay phai do."""
    epub_path = _build_epub(tmp_path / "book.epub")
    provider = ClaudeProvider(api_key="sk-ant-fake")

    detailed = await estimate_translation_cost(
        epub_path,
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="epub",
        settings=Settings(),
    )

    glossary_manager = GlossaryManager(session)
    old_formula_prompt_text = await build_prompt_text(
        glossary_manager,
        project_id=None,
        only_terms_present_in=EpubDocument.load(epub_path).full_text(),
        max_glossary_entries=80,
    )
    old_formula_overhead = max(len(old_formula_prompt_text) - len("${text}"), 0)

    assert detailed.prompt_overhead_chars > old_formula_overhead


# ---------------------------------------------------------------------------
# Architecture.md §6.20.14.2 A-4 (2026-09-10, Protocol 6 R6-01/R6-02 data
# lineage) — `_estimate_epub_translation_cost()` PHAI goi `plan_epub_chunks()`
# voi CUNG tham so tu `Settings` ma `job_orchestrator.run_epub_job()` dung,
# khong phai gia tri MAC DINH module. Truoc fix: 2 noi TINH CO khop nhau; sau
# khi doi EPUB_REQUEST_CHAR_BUDGET/them EPUB_REQUEST_MAX_UNITS (A-1), hoac
# voi bat ky override .env nao, chung se LECH va uoc THAP chi phi.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_estimate_epub_translation_cost_requires_settings_for_epub(
    session: AsyncSession, tmp_path: Path
) -> None:
    """A-4 khoa cung: khong duoc goi nhanh EPUB voi `settings=None` — day
    chinh la con duong de tinh trang "2 noi tinh co khop nhau" tai dien, vi
    khong truyen settings nghia la dung mac dinh module."""
    epub_path = _build_epub(tmp_path / "book.epub")
    provider = ClaudeProvider(api_key="sk-ant-fake")

    with pytest.raises(ValueError, match="settings"):
        await estimate_translation_cost(
            epub_path,
            provider,
            session,
            batch_id=None,
            max_glossary_entries=80,
            file_type="epub",
        )


@pytest.mark.asyncio
async def test_estimate_epub_translation_cost_llm_request_count_changes_with_settings(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 (khong chi `assert_called()`, ma assert GIA TRI CU THE thay
    doi): doi `epub_request_max_units` trong `Settings` phai lam
    `estimated_input_tokens` (bat nguon tu `segment_count` =
    `llm_request_count`) THAY DOI theo — neu ham nay van dung tham so mac
    dinh module (bo qua Settings), gia tri se KHONG doi du Settings da doi,
    tai dien dung bug A-4 da mo ta."""
    epub_path = _build_epub_multi_unit(tmp_path / "book.epub", n_paragraphs=12)
    provider = ClaudeProvider(api_key="sk-ant-fake")

    # request_max_units=1: MOI unit thanh 1 request rieng -> so request lon
    # hon han so voi request_max_units rong (100, se gom het 12 unit vao 1
    # request vi request_char_budget rong cung).
    settings_wide = Settings(epub_request_max_units=100, epub_request_char_budget=100_000)
    settings_narrow = Settings(epub_request_max_units=1, epub_request_char_budget=100_000)

    detailed_wide = await estimate_translation_cost(
        epub_path,
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="epub",
        settings=settings_wide,
    )
    detailed_narrow = await estimate_translation_cost(
        epub_path,
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="epub",
        settings=settings_narrow,
    )

    assert detailed_narrow.segment_count > detailed_wide.segment_count
    assert (
        detailed_narrow.estimate.estimated_input_tokens
        > detailed_wide.estimate.estimated_input_tokens
    )


@pytest.mark.asyncio
async def test_estimate_epub_translation_cost_segment_count_matches_orchestrator_plan(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Soi day lineage that su (khong chi so sanh 2 lan goi estimate voi
    nhau): `segment_count` do Lop 2 tra ve phai KHOP CHINH XAC voi so request
    ma `plan_epub_chunks()` sinh ra khi goi VOI DUNG tham so tu CUNG 1
    `Settings` — dung cach `job_orchestrator.run_epub_job()` goi."""
    epub_path = _build_epub(tmp_path / "book.epub")
    provider = ClaudeProvider(api_key="sk-ant-fake")
    settings = Settings(epub_request_char_budget=50, epub_request_max_units=2)

    detailed = await estimate_translation_cost(
        epub_path,
        provider,
        session,
        batch_id=None,
        max_glossary_entries=80,
        file_type="epub",
        settings=settings,
    )

    doc = EpubDocument.load(epub_path)
    plan = plan_epub_chunks(
        doc.units,
        char_budget=settings.epub_chunk_char_budget,
        request_budget=settings.epub_request_char_budget,
        request_max_units=settings.epub_request_max_units,
    )
    expected_llm_request_count = sum(len(c.requests) for c in plan)

    assert detailed.segment_count == expected_llm_request_count
