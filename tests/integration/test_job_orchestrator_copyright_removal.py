"""S8 — tu dong loai bo trang claim ban quyen truoc khi dich (PDF nhanh).

R6-02: assert GIA TRI CU THE truyen giua cac buoc (input_path/page_range cua
translate_pages, en_pdf_path cua create_bilingual_pdf), khong chi
`assert_called()`. Protocol 5 muc 3: khong viet mock/fixture tay theo gia
dinh — dung `scan_units()` that (khong mock detector) tren PDF dung PyMuPDF
that dung.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.batch import Batch
from src.models.chunk import Chunk
from src.services.mineru_runner import MinerUResult, MinerURunner, OcrQuality
from tests.integration.test_job_orchestrator import (
    _PAGE_SIZE,
    _create_job,
    _fake_babeldoc_runner,
    _fake_pdf2zh_runner,
    _FakePricingProvider,
)

#: Score 16 (>= MIN_SCORE=5), 28 tu (trong khoang [MIN_WORDS=5, MAX_WORDS=600])
#: — verified thu cong bang copyright_detector._score() truoc khi viet test
#: nay (Protocol 5 R5-03 tinh than: khong bia so lieu, do that qua module).
_COPYRIGHT_TEXT = (
    "All rights reserved. No part of this publication may be reproduced. "
    "ISBN 978-1-234567-89-0. Library of Congress Cataloging-in-Publication "
    "Data. Copyright © 2020 Test Publisher, first published in this edition."
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


def _make_pdf_with_copyright_page(path: Path, n_pages: int, *, copyright_page_1based: int) -> None:
    """`n_pages` trang thuong (dung `_make_pdf`'s text shape) + 1 trang o vi
    tri `copyright_page_1based` chua noi dung claim ban quyen that (do duoc
    bang `_score()` — xem `_COPYRIGHT_TEXT` o tren)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        if (i + 1) == copyright_page_1based:
            page.insert_textbox((36, 36, 560, 780), _COPYRIGHT_TEXT, fontsize=10)
        else:
            page.insert_text((50, 100), f"page {i + 1}", fontsize=10)
    doc.save(path)
    doc.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["pdf2zh", "babeldoc"])
async def test_copyright_page_pruned_before_translate_pages_both_engines(
    session: AsyncSession, tmp_path: Path, engine: str
) -> None:
    """R6-02 + Protocol 8 doi xung 2 engine: ca pdf2zh va babeldoc phai nhan
    CUNG mot `input_path` (file da cat) va CUNG `page_range` — cat trang xay
    ra TRUOC diem chon engine (Architecture.md 6.28.4/6.28.5)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    runner = _fake_pdf2zh_runner() if engine == "pdf2zh" else _fake_babeldoc_runner()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine=engine, copyright_page_removal_enabled=True),
        pdf2zh_runner=runner if engine == "pdf2zh" else None,
        babeldoc_runner=runner if engine == "babeldoc" else None,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    pruned_path = tmp_path / "processing" / job.id / "pruned" / "source_pruned.pdf"
    assert pruned_path.exists()
    with fitz.open(pruned_path) as pruned_doc:
        assert pruned_doc.page_count == 5  # 6 trang goc - 1 trang ban quyen

    calls = runner.translate_pages.await_args_list
    assert len(calls) >= 1
    for call in calls:
        assert call.kwargs["input_path"] == pruned_path

    await session.refresh(job)
    assert job.total_pages == 5
    removed_data = json.loads(job.copyright_removed_json)
    assert removed_data["removed"] == ["2"]
    assert removed_data["mode"] == "pdf_pages"


@pytest.mark.asyncio
async def test_original_pruned_pdf_cut_from_original_file_same_indices(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Chong lap lai Bug #9 (bai hoc §6.28.4 luat 2): phai co artifact thu 2
    `original_pruned.pdf` cat TU `file_path` GOC (khong phai file da OCR/da
    dich) voi CUNG tap chi so voi `source_pruned.pdf`."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    original_pruned_path = tmp_path / "processing" / job.id / "pruned" / "original_pruned.pdf"
    assert original_pruned_path.exists()
    with fitz.open(original_pruned_path) as pruned_doc, fitz.open(source_pdf) as src_doc:
        assert pruned_doc.page_count == 5
        # trang 1 (index 0) cua ban goc phai khop trang 1 cua original_pruned
        # (trang 2, index 1, la trang bi cat) — so text de xac nhan DUNG noi
        # dung, khong chi dung so trang.
        assert pruned_doc[0].get_text().strip() == src_doc[0].get_text().strip()
        assert pruned_doc[1].get_text().strip() == src_doc[2].get_text().strip()


@pytest.mark.asyncio
async def test_create_bilingual_pdf_uses_original_pruned_not_file_path(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Chong lap lai Bug #9 — assert `create_bilingual_pdf` duoc goi voi
    `original_pruned.pdf`, KHONG phai `job.file_path`, va file song ngu co
    dung so trang = 2 x so trang ban dich, trang chan/le dung cap."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    batch = Batch(output_mode="bilingual")
    session.add(batch)
    await session.commit()
    await session.refresh(batch)
    job.batch_id = batch.id
    session.add(job)
    await session.commit()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"
    assert result.bilingual_path is not None

    original_pruned_path = tmp_path / "processing" / job.id / "pruned" / "original_pruned.pdf"
    with fitz.open(result.output_path) as vi_doc, fitz.open(result.bilingual_path) as bi_doc:
        assert bi_doc.page_count == 2 * vi_doc.page_count
        with fitz.open(original_pruned_path) as en_doc:
            for i in range(vi_doc.page_count):
                assert bi_doc[2 * i].get_text().strip() == vi_doc[i].get_text().strip()
                assert bi_doc[2 * i + 1].get_text().strip() == en_doc[i].get_text().strip()


def _fake_mineru_runner_with_copyright_page(*, copyright_page_1based: int) -> MinerURunner:
    """Bien the cua `_fake_mineru_runner()` (test_job_orchestrator.py) —
    span content cua trang `copyright_page_1based` la `_COPYRIGHT_TEXT` thay
    vi "OCR text page N", de cau noi searchable PDF co du text cho
    `scan_units()` cham diem (Step 2b chay SAU cau noi OCR)."""
    runner = AsyncMock(spec=MinerURunner)

    async def _parse_document(file_path, output_dir, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "document.md"
        markdown_path.write_text("ocr text", encoding="utf-8")
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        with fitz.open(file_path) as doc:
            n_pages = doc.page_count

        middle = {
            "pdf_info": [
                {
                    "page_idx": i,
                    "page_size": _PAGE_SIZE,
                    "preproc_blocks": [
                        {
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "type": "text",
                                            "content": (
                                                _COPYRIGHT_TEXT
                                                if (i + 1) == copyright_page_1based
                                                else f"OCR text page {i + 1}"
                                            ),
                                            "bbox": [50.0, 50.0, 300.0, 70.0],
                                            "score": 0.92,
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                    "discarded_blocks": [],
                }
                for i in range(n_pages)
            ]
        }
        middle_json_path = output_dir / "middle.json"
        middle_json_path.write_text(json.dumps(middle), encoding="utf-8")

        return MinerUResult(
            markdown_path=markdown_path,
            images_dir=images_dir,
            quality=OcrQuality(
                confidence=0.92,
                ocr_span_count=n_pages,
                dropped_span_count=0,
                source="middle_json_span_scores",
            ),
            task_id="fake-task-id",
            middle_json_path=middle_json_path,
        )

    runner.parse_document.side_effect = _parse_document
    return runner


@pytest.mark.asyncio
async def test_pdf_scan_copyright_removal_runs_after_ocr_bridge(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Step 2b (Architecture.md 6.28.4) phai chay SAU cau noi OCR — quet
    tren text cua cau noi (chua co text layer truoc OCR), va
    `original_pruned.pdf` van cat TU `job.file_path` (file scan goc) voi
    CUNG tap chi so."""
    source_pdf = tmp_path / "source.pdf"
    # `_make_pdf()` chen text THAT NHIN THAY duoc -> `build_searchable_pdf()`
    # bo qua chen lop OCR cho trang da co text object that (defense-in-depth,
    # searchable_pdf.py). Trang scan THAT khong co text nao ca — dung
    # `fitz.open()` + `new_page()` TRAN, giong dung fixture goc cua chinh
    # `build_searchable_pdf` (khong phai mock viet tay theo gia dinh).
    blank_doc = fitz.open()
    for _ in range(6):
        blank_doc.new_page()
    blank_doc.save(source_pdf)
    blank_doc.close()
    job = await _create_job(session, source_pdf, file_type="pdf_scan")

    mineru_runner = _fake_mineru_runner_with_copyright_page(copyright_page_1based=2)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        mineru_runner=mineru_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    pruned_path = tmp_path / "processing" / job.id / "pruned" / "source_pruned.pdf"
    original_pruned_path = tmp_path / "processing" / job.id / "pruned" / "original_pruned.pdf"
    assert pruned_path.exists()
    assert original_pruned_path.exists()
    with fitz.open(pruned_path) as p, fitz.open(original_pruned_path) as o:
        assert p.page_count == 5
        assert o.page_count == 5


@pytest.mark.asyncio
async def test_resume_does_not_rescan_when_copyright_removed_json_already_set(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Resume (Architecture.md 6.28.3): job co san Chunk rows +
    `copyright_removed_json` -> `scan_units` KHONG duoc goi lai."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    job.copyright_removed_json = (
        '{"version": 1, "mode": "pdf_pages", "removed": ["2"], "verdicts": [], '
        '"structural": null, "aborted_reason": null}'
    )
    job.total_pages = 5
    job.chunk_size_used = 40
    session.add(job)
    await session.commit()

    existing_chunk = Chunk(job_id=job.id, chunk_index=0, page_start=1, page_end=5)
    session.add(existing_chunk)
    await session.commit()

    with patch("src.core.job_orchestrator.scan_units") as mock_scan:
        orchestrator = JobOrchestrator(
            settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=True),
            pdf2zh_runner=_fake_pdf2zh_runner(),
            provider=_FakePricingProvider(),
            output_dir=tmp_path / "outputs",
            processing_dir=tmp_path / "processing",
        )
        result = await orchestrator.run_job(job.id, session)
        mock_scan.assert_not_called()

    assert result.status == "completed"
    await session.refresh(job)
    assert job.total_pages == 5


@pytest.mark.asyncio
async def test_kill_switch_disabled_byte_identical_to_pre_s8(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Kill-switch tat -> khong tao thu muc pruned/, khong ghi
    copyright_removed_json, `translate_pages` nhan thang `file_path` goc
    (byte-identical voi hanh vi truoc S8)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    runner = _fake_pdf2zh_runner()

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=False),
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    pruned_dir = tmp_path / "processing" / job.id / "pruned"
    assert not pruned_dir.exists()

    for call in runner.translate_pages.await_args_list:
        assert call.kwargs["input_path"] == source_pdf

    await session.refresh(job)
    assert job.copyright_removed_json is None
    assert job.total_pages == 6


@pytest.mark.asyncio
async def test_apply_copyright_removal_idempotent_across_resume_calls(
    session: AsyncSession, tmp_path: Path
) -> None:
    """S8-B1 fix (docs/design-log.md 2026-09-17, phuong an c, luat 5): goi
    `_apply_copyright_removal()` 2 LAN lien tiep tren CUNG 1 job (mo phong
    resume) phai ra DUNG CUNG 1 con so `total_pages` va CUNG duong dan file
    da cat — khong drift giua cac lan chay lai."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    source_pruned_1, original_pruned_1 = await orchestrator._apply_copyright_removal(
        job, source_pdf, source_pdf, session
    )
    await session.refresh(job)
    assert job.total_pages == 5
    removed_json_1 = job.copyright_removed_json

    source_pruned_2, original_pruned_2 = await orchestrator._apply_copyright_removal(
        job, source_pdf, source_pdf, session
    )
    await session.refresh(job)

    assert job.total_pages == 5
    assert job.copyright_removed_json == removed_json_1
    assert source_pruned_2 == source_pruned_1
    assert original_pruned_2 == original_pruned_1
    with fitz.open(source_pruned_2) as p:
        assert p.page_count == 5


@pytest.mark.asyncio
async def test_kill_switch_disabled_midway_still_replays_committed_decision(
    session: AsyncSession, tmp_path: Path
) -> None:
    """c2 (S8-B1 fix, docs/design-log.md 2026-09-17): kill-switch tat GIUA
    CHUNG sau khi job DA cat that va DA co Chunk row -> van phai cat lai
    dung theo quyet dinh da cam ket, KHONG duoc kill-switch hien tai chan
    (chunks.page_start/page_end da danh so theo file DA cat tu lan chay
    truoc, bo cat luc nay se lam lech chi so trang)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_copyright_page(source_pdf, n_pages=6, copyright_page_1based=2)
    job = await _create_job(session, source_pdf, file_type="pdf_digital")

    orchestrator_on = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=True),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    await orchestrator_on._apply_copyright_removal(job, source_pdf, source_pdf, session)
    await session.refresh(job)
    assert job.total_pages == 5
    assert json.loads(job.copyright_removed_json)["removed"] == ["2"]

    # Mo phong Chunk row da duoc tao tu lan chay truoc (danh so theo file
    # DA cat, dung `page_start/page_end` trong he quy chieu 5 trang).
    existing_chunk = Chunk(job_id=job.id, chunk_index=0, page_start=1, page_end=5)
    session.add(existing_chunk)
    await session.commit()

    orchestrator_off = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", copyright_page_removal_enabled=False),
        pdf2zh_runner=_fake_pdf2zh_runner(),
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    source_pruned, original_pruned = await orchestrator_off._apply_copyright_removal(
        job, source_pdf, source_pdf, session
    )

    assert source_pruned.name == "source_pruned.pdf"
    assert original_pruned.name == "original_pruned.pdf"
    with fitz.open(source_pruned) as p:
        assert p.page_count == 5

    await session.refresh(job)
    assert job.total_pages == 5
