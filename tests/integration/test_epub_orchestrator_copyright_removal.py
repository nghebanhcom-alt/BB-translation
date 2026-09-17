"""S8 — tu dong loai bo trang claim ban quyen truoc khi dich (EPUB nhanh,
`run_epub_job()`, Architecture.md 6.28.6.2).

R6-02: assert `job.total_units`/chunk unit_start-end/`translations` KHONG
bao gio dung toi doc bi loai. Protocol 5 muc 3: khong mock detector — dung
`scan_units()` that.
"""

from __future__ import annotations

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
from src.models.chunk import Chunk
from src.models.job import Job
from src.services.epub_document import EpubDocument
from tests.integration.test_epub_translate_runner import _FakeEpubProvider

#: Verified thu cong (giong tests/integration/test_job_orchestrator_copyright_removal.py):
#: score >= MIN_SCORE(5), word_count trong [MIN_WORDS(5), MAX_WORDS(600)].
_COPYRIGHT_HTML = (
    "<p>All rights reserved. No part of this publication may be reproduced. "
    "ISBN 978-1-234567-89-0. Library of Congress Cataloging-in-Publication "
    "Data. Copyright © 2020 Test Publisher, first published in this edition.</p>"
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


def _build_epub_with_copyright_doc(path: Path) -> Path:
    """3 tai lieu spine: `chap0.xhtml` (noi dung), `copyright.xhtml` (claim
    ban quyen that, se bi loai), `chap1.xhtml` (noi dung). Khong OPF
    guide/NCX pageTarget — chi item+itemref (du cho rule (a)/(b))."""
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
        "<manifest>"
        '<item id="chap0" href="chap0.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="cop" href="copyright.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>'
        "</manifest>"
        '<spine><itemref idref="chap0"/><itemref idref="cop"/>'
        '<itemref idref="chap1"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf)
        for name, paragraphs in (
            ("chap0.xhtml", "<p>Chapter 0 paragraph 0: flour and water.</p>"),
            ("copyright.xhtml", _COPYRIGHT_HTML),
            ("chap1.xhtml", "<p>Chapter 1 paragraph 0: sugar and yeast.</p>"),
        ):
            xhtml = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<head><title>{name}</title></head><body>{paragraphs}</body></html>"
            )
            zf.writestr(f"OEBPS/{name}", xhtml)
    return path


async def _create_epub_job(
    session: AsyncSession, epub_path: Path, *, output_mode: str = "monolingual"
) -> Job:
    """S8-B1 fix (docs/design-log.md 2026-09-17): `total_units` gan ngay luc
    tao job, GIONG HET `POST /api/jobs` (`routes/jobs.py:652`,
    `total_units=cost_estimate.total_units`) — cost estimate luon tinh tren
    TOAN BO doc (truoc Step 2b loai trang ban quyen), nen dung
    `len(EpubDocument.load(...).units)` (chua loai) o day, khong phai
    `units_excluding(...)`. Khong dung so lieu nay se lam sai lech data
    lineage voi production (R6-02).
    """
    total_units = len(EpubDocument.load(epub_path).units)
    batch = Batch(total_files=1, output_mode=output_mode, model="deepseek")
    session.add(batch)
    await session.flush()
    job = Job(
        batch_id=batch.id,
        filename=epub_path.name,
        file_path=str(epub_path),
        file_size=epub_path.stat().st_size,
        file_hash="deadbeef-epub-s8",
        file_type="epub",
        model="deepseek",
        total_units=total_units,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@pytest.mark.asyncio
async def test_copyright_doc_excluded_from_total_units_and_translations(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub_with_copyright_doc(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path)
    provider = _FakeEpubProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(copyright_page_removal_enabled=True),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    await session.refresh(job)
    assert job.total_units == 2  # 3 doan goc - 1 doan (copyright.xhtml)

    removed_data = json.loads(job.copyright_removed_json)
    assert removed_data["removed"] == ["OEBPS/copyright.xhtml"]
    assert removed_data["mode"] == "epub_docs"
    assert removed_data["structural"] == {"OEBPS/copyright.xhtml": "full"}

    # Provider chi bao gio nhan noi dung 2 chuong con lai — TUYET DOI khong
    # bao gio thay "ISBN"/"Library of Congress" trong bat ky payload nao.
    for payload_json, _system_prompt in provider.calls:
        assert "ISBN" not in payload_json
        assert "Library of Congress" not in payload_json

    with zipfile.ZipFile(job.output_path) as zf:
        assert "OEBPS/copyright.xhtml" not in zf.namelist()
        for name in zf.namelist():
            assert b"copyright.xhtml" not in zf.read(name)

    guard_doc = EpubDocument.load(Path(job.output_path))
    assert len(guard_doc.spine_hrefs) == 2


@pytest.mark.asyncio
async def test_kill_switch_disabled_epub_byte_identical_behavior(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub_with_copyright_doc(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path)
    provider = _FakeEpubProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(copyright_page_removal_enabled=False),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    await session.refresh(job)
    assert job.copyright_removed_json is None
    assert job.total_units == 3  # khong loai gi ca

    with zipfile.ZipFile(job.output_path) as zf:
        assert "OEBPS/copyright.xhtml" in zf.namelist()


@pytest.mark.asyncio
async def test_apply_epub_copyright_removal_idempotent_across_resume_calls(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S8-B1 fix (docs/design-log.md 2026-09-17, phuong an c, luat 5) —
    doi xung voi nhanh PDF: goi `_apply_epub_copyright_removal()` 2 LAN lien
    tiep tren CUNG 1 job phai ra DUNG CUNG 1 `total_units` va CUNG tap
    `dropped_doc_hrefs`."""
    epub_path = _build_epub_with_copyright_doc(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path)

    orchestrator = JobOrchestrator(
        settings=Settings(copyright_page_removal_enabled=True),
        provider=_FakeEpubProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    dropped_1 = await orchestrator._apply_epub_copyright_removal(
        job, EpubDocument.load(epub_path), session
    )
    await session.refresh(job)
    assert dropped_1 == {"OEBPS/copyright.xhtml"}
    assert job.total_units == 2
    removed_json_1 = job.copyright_removed_json

    dropped_2 = await orchestrator._apply_epub_copyright_removal(
        job, EpubDocument.load(epub_path), session
    )
    await session.refresh(job)

    assert dropped_2 == dropped_1
    assert job.total_units == 2
    assert job.copyright_removed_json == removed_json_1


@pytest.mark.asyncio
async def test_kill_switch_disabled_midway_epub_still_replays_committed_decision(
    session: AsyncSession, tmp_path: Path
) -> None:
    """c2 (S8-B1 fix, docs/design-log.md 2026-09-17) — doi xung voi nhanh
    PDF: kill-switch tat GIUA CHUNG sau khi job DA loai doc that va DA co
    Chunk row -> van phai loai lai dung theo quyet dinh da cam ket."""
    epub_path = _build_epub_with_copyright_doc(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path)

    orchestrator_on = JobOrchestrator(
        settings=Settings(copyright_page_removal_enabled=True),
        provider=_FakeEpubProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    dropped = await orchestrator_on._apply_epub_copyright_removal(
        job, EpubDocument.load(epub_path), session
    )
    await session.refresh(job)
    assert dropped == {"OEBPS/copyright.xhtml"}
    assert job.total_units == 2

    # Mo phong Chunk row da duoc tao tu lan chay truoc (danh so unit theo
    # danh sach DA loai doc ban quyen).
    existing_chunk = Chunk(job_id=job.id, chunk_index=0, unit_start=0, unit_end=1)
    session.add(existing_chunk)
    await session.commit()

    orchestrator_off = JobOrchestrator(
        settings=Settings(copyright_page_removal_enabled=False),
        provider=_FakeEpubProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    dropped_2 = await orchestrator_off._apply_epub_copyright_removal(
        job, EpubDocument.load(epub_path), session
    )

    assert dropped_2 == {"OEBPS/copyright.xhtml"}
    await session.refresh(job)
    assert job.total_units == 2
