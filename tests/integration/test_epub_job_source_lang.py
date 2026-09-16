"""S7 — dich FR->VI, nhanh EPUB (Architecture.md §6.26.4 bang dong "EPUB —
build_system_prompt()"/"EPUB retry — pricing_provider.translate()").

R6-02: assert `source_lang` THAT truyen vao `provider.translate()` cho MOI
lan goi (chinh + retry), khong chi assert job hoan thanh.
"""

import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.batch import Batch
from src.models.job import Job
from src.services.translation import TranslationResult
from tests.test_language_detector import _FR_TEXT


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _build_epub(path: Path, paragraphs: list[str]) -> Path:
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
        "<dc:title>Test Book</dc:title><dc:language>fr</dc:language>"
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


async def _create_epub_job(
    session: AsyncSession, epub_path: Path, *, source_lang: str | None
) -> Job:
    batch = Batch(total_files=1, output_mode="bilingual", model="deepseek")
    session.add(batch)
    await session.flush()
    job = Job(
        batch_id=batch.id,
        filename=epub_path.name,
        file_path=str(epub_path),
        file_size=epub_path.stat().st_size,
        file_hash="deadbeef-epub-fr",
        file_type="epub",
        model="deepseek",
        source_lang=source_lang,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


class _FakeEpubProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        # (payload_json, source_lang, target_lang) cho MOI lan goi.
        self.calls: list[tuple[str, str, str]] = []

    async def translate(
        self, text: str, glossary_prompt: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        self.calls.append((text, source_lang, target_lang))
        payload = json.loads(text)
        reply = {item["id"]: f"VI:{item['html']}" for item in payload}
        reply_text = json.dumps(reply, ensure_ascii=False)
        return TranslationResult(
            text=reply_text,
            input_tokens=len(text),
            output_tokens=len(reply_text),
            estimated_cost_usd=0.000001 * (len(text) + len(reply_text)),
            provider_name="fake",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0


@pytest.mark.asyncio
async def test_epub_translate_calls_receive_source_lang_fr_for_pinned_fr_job(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub(tmp_path / "book.epub", ["Le pain est bon.", "La levure leve."])
    job = await _create_epub_job(session, epub_path, source_lang="fr")
    provider = _FakeEpubProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(epub_chunk_char_budget=8_000, epub_request_char_budget=3_000),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert provider.calls
    for _payload, source_lang, target_lang in provider.calls:
        assert source_lang == "fr"
        assert target_lang == "vi"

    await session.refresh(job)
    assert job.source_lang == "fr"


@pytest.mark.asyncio
async def test_epub_translate_calls_receive_source_lang_en_for_null_source_lang(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub(tmp_path / "book.epub", ["Mix flour and yeast.", "Bake at 350F."])
    job = await _create_epub_job(session, epub_path, source_lang=None)
    provider = _FakeEpubProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(epub_chunk_char_budget=8_000, epub_request_char_budget=3_000),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    for _payload, source_lang, _target_lang in provider.calls:
        assert source_lang == "en"


@pytest.mark.asyncio
async def test_epub_run_detects_source_lang_from_real_french_text_when_null(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 end-to-end: EPUB voi van ban FR THAT (>= 500 token), job tao
    KHONG qua cost_gate (source_lang=None) -> `run_epub_job()` tu detect va
    persist "fr", VA moi lan goi `provider.translate()` dung dung gia tri do."""
    paragraphs = [p for p in _FR_TEXT.split("\n\n") if p.strip()]
    epub_path = _build_epub(tmp_path / "book_fr.epub", paragraphs)
    job = await _create_epub_job(session, epub_path, source_lang=None)
    provider = _FakeEpubProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(epub_chunk_char_budget=8_000, epub_request_char_budget=3_000),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)
    assert job.source_lang == "fr"
    assert provider.calls
    for _payload, source_lang, _target_lang in provider.calls:
        assert source_lang == "fr"
