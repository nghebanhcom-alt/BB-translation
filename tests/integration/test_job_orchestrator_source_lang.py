"""S7 — dich FR->VI (Architecture.md §6.26.4/6.26.5/6.26.8).

R6-02: assert GIA TRI CU THE truyen giua cac buoc (lang_in cua
translate_pages, noi dung prompt file, lang cua MinerU) — khong chi
`assert_called()`.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.job import Job
from src.services.mineru_runner import MinerUResult, MinerURunner, OcrQuality
from src.services.pdf2zh_runner import Pdf2zhResult, Pdf2zhRunner
from tests.test_language_detector import _EN_TEXT, _FR_TEXT

_PAGE_SIZE = [595.0, 842.0]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _make_pdf(path: Path, n_pages: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((50, 100), f"page {i + 1}", fontsize=10)
    doc.save(path)
    doc.close()


def _make_pdf_with_real_text(path: Path, text: str) -> None:
    doc = fitz.open()
    words = text.split()
    page_size = 120
    for start in range(0, len(words), page_size):
        page = doc.new_page()
        page.insert_textbox(
            (36, 36, 560, 780), " ".join(words[start : start + page_size]), fontsize=9
        )
    doc.save(path)
    doc.close()


class _FakePricingProvider:
    provider_name = "mock"

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round((input_tokens + output_tokens) * 0.0001, 6)


async def _create_job(
    session: AsyncSession,
    source_pdf: Path,
    *,
    model: str = "deepseek",
    file_type: str = "pdf_digital",
    source_lang: str | None = None,
) -> Job:
    job = Job(
        filename="book.pdf",
        file_path=str(source_pdf),
        file_size=source_pdf.stat().st_size,
        file_hash="deadbeef",
        file_type=file_type,
        model=model,
        source_lang=source_lang,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


def _fake_pdf2zh_runner() -> Pdf2zhRunner:
    runner = AsyncMock(spec=Pdf2zhRunner)
    runner.needs_font_shrink = True
    runner.reports_own_paragraph_drops = False
    runner.reports_token_usage = False

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, **kwargs
    ):
        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}-mono.pdf"
        _make_pdf(mono_path, n_pages=total_pages)
        return Pdf2zhResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages
    return runner


def _middle_json_for(n_pages: int, *, confidence: float = 0.92) -> dict:
    return {
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
                                        "content": f"OCR text page {i + 1}",
                                        "bbox": [50.0, 50.0, 300.0, 70.0],
                                        "score": confidence,
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


def _fake_mineru_runner(tmp_path: Path, *, confidence: float = 0.92) -> MinerURunner:
    runner = AsyncMock(spec=MinerURunner)

    async def _parse_document(file_path, output_dir, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "document.md"
        markdown_path.write_text("ocr text", encoding="utf-8")
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        with fitz.open(file_path) as doc:
            n_pages = doc.page_count

        middle = _middle_json_for(n_pages, confidence=confidence)
        middle_json_path = output_dir / "middle.json"
        middle_json_path.write_text(json.dumps(middle), encoding="utf-8")

        return MinerUResult(
            markdown_path=markdown_path,
            images_dir=images_dir,
            quality=OcrQuality(
                confidence=confidence,
                ocr_span_count=n_pages,
                dropped_span_count=1,
                source="middle_json_span_scores",
            ),
            task_id="fake-task-id",
            middle_json_path=middle_json_path,
        )

    runner.parse_document.side_effect = _parse_document
    return runner


@pytest.mark.asyncio
async def test_translate_pages_receives_lang_in_fr_for_pinned_fr_job(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02: job.source_lang="fr" (da chot san, mo phong cost_gate da detect
    luc tao job) -> `translate_pages()` PHAI nhan `lang_in="fr"`, VA prompt
    file THAT su chua 'tieng Phap' (khong chi ham build_* tra ve dung)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, source_lang="fr")

    pdf2zh_runner = _fake_pdf2zh_runner()
    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert pdf2zh_runner.translate_pages.await_args_list
    for call in pdf2zh_runner.translate_pages.await_args_list:
        assert call.kwargs["lang_in"] == "fr"

    await session.refresh(job)
    assert job.source_lang == "fr"  # giu nguyen, khong bi ghi de


@pytest.mark.asyncio
async def test_translate_pages_receives_lang_in_en_for_null_source_lang(
    session: AsyncSession, tmp_path: Path
) -> None:
    """job.source_lang=None (job cu truoc S7) -> coi nhu "en" (deny-by-default,
    R8-02) — VA `run_job()` Step 3 tu detect + persist "en" (fallback, van
    la EN thuc su o day)."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, source_lang=None)

    pdf2zh_runner = _fake_pdf2zh_runner()
    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    for call in pdf2zh_runner.translate_pages.await_args_list:
        assert call.kwargs["lang_in"] == "en"

    await session.refresh(job)
    assert job.source_lang == "en"


@pytest.mark.asyncio
async def test_babeldoc_prompt_file_contains_tieng_phap_for_fr_job(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02: prompt FILE THAT (khong phai chi build_babeldoc_prompt_text()
    tra ve dung chuoi) phai chua 'tieng Phap' khi job.source_lang == 'fr'."""
    from src.services.babeldoc_runner import BabeldocResult, BabeldocRunner

    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, source_lang="fr")

    runner = AsyncMock(spec=BabeldocRunner)
    runner.needs_font_shrink = False
    runner.reports_own_paragraph_drops = True
    runner.reports_token_usage = True

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, lang_out="vi", **kwargs
    ):
        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}.no_watermark.{lang_out}.mono.pdf"
        _make_pdf(mono_path, n_pages=total_pages)
        return BabeldocResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="babeldoc"),
        babeldoc_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert runner.translate_pages.await_args_list
    for call in runner.translate_pages.await_args_list:
        prompt_content = call.kwargs["prompt_file"].read_text(encoding="utf-8")
        assert "tieng Phap" in prompt_content
        assert call.kwargs["lang_in"] == "fr"


@pytest.mark.asyncio
async def test_pdf_scan_mineru_always_called_with_lang_en_even_for_fr_job(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md §6.26.1/§6.26.5 buoc #1 — MinerU 3.4.5 raise
    ValueError voi lang='fr' (khong nam trong PUBLIC_OCR_LANGUAGES). Job
    pdf_scan co source_lang='fr' (da chot san) VAN phai goi MinerU voi
    lang mac dinh 'en' ('en' la alias cho model 'ch' phu Latin) — TUYET DOI
    KHONG duoc truyen job.source_lang vao MinerU."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 3)
    job = await _create_job(session, source_pdf, file_type="pdf_scan", source_lang="fr")

    pdf2zh_runner = _fake_pdf2zh_runner()
    mineru_runner = _fake_mineru_runner(tmp_path)

    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        mineru_runner=mineru_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert mineru_runner.parse_document.await_args_list
    for call in mineru_runner.parse_document.await_args_list:
        # Orchestrator KHONG duoc truyen "lang" nao khac "en" — mac dinh
        # cua MinerURunner.parse_document() la "en", va o day PHAI khong bi
        # ghi de boi job.source_lang="fr".
        assert call.kwargs.get("lang", "en") == "en"

    # Nhung buoc dich (translate_pages) van dung dung "fr" — chi MinerU la
    # ngoai le.
    for call in pdf2zh_runner.translate_pages.await_args_list:
        assert call.kwargs["lang_in"] == "fr"


@pytest.mark.asyncio
async def test_run_job_detects_source_lang_from_real_french_text_when_null(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 end-to-end: job tao KHONG qua cost_gate (source_lang=None, vd
    test/tao truc tiep) -> `run_job()` Step 3 tu detect tren van ban FR
    THAT (khong phai gia dinh) va PERSIST vao job.source_lang."""
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_real_text(source_pdf, _FR_TEXT)
    job = await _create_job(session, source_pdf, source_lang=None)

    pdf2zh_runner = _fake_pdf2zh_runner()
    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)
    assert job.source_lang == "fr"
    for call in pdf2zh_runner.translate_pages.await_args_list:
        assert call.kwargs["lang_in"] == "fr"


@pytest.mark.asyncio
async def test_run_job_detects_source_lang_from_real_english_text_when_null(
    session: AsyncSession, tmp_path: Path
) -> None:
    source_pdf = tmp_path / "source.pdf"
    _make_pdf_with_real_text(source_pdf, _EN_TEXT)
    job = await _create_job(session, source_pdf, source_lang=None)

    pdf2zh_runner = _fake_pdf2zh_runner()
    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh"),
        pdf2zh_runner=pdf2zh_runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)
    assert job.source_lang == "en"


@pytest.mark.asyncio
async def test_source_lang_survives_resume_after_chunk_failure(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Cung nguyen tac voi chunk_size_used (Architecture.md §6.26.2): mot
    job resume giua chung KHONG duoc doi ngon ngu nguon — chunk da xong da
    sinh theo prompt cu."""
    from src.services.pdf2zh_runner import Pdf2zhError

    source_pdf = tmp_path / "source.pdf"
    _make_pdf(source_pdf, 90)
    job = await _create_job(session, source_pdf, source_lang="fr")
    job.chunk_size_used = 40
    session.add(job)
    await session.commit()

    call_counter = {"n": 0}
    runner = AsyncMock(spec=Pdf2zhRunner)
    runner.needs_font_shrink = True
    runner.reports_own_paragraph_drops = False
    runner.reports_token_usage = False

    async def _translate_pages(
        input_path, output_dir, page_range, service, prompt_file=None, **kwargs
    ):
        idx = call_counter["n"]
        call_counter["n"] += 1
        if idx == 1:
            raise Pdf2zhError("simulated failure")
        with fitz.open(input_path) as source_doc:
            total_pages = source_doc.page_count
        mono_path = output_dir / f"{input_path.stem}-mono.pdf"
        _make_pdf(mono_path, n_pages=total_pages)
        return Pdf2zhResult(
            success=True, mono_path=mono_path, dual_path=None, stderr="", duration_seconds=0.01
        )

    runner.translate_pages.side_effect = _translate_pages

    # cost_cap_enabled=False: bai test nay ve lineage cua source_lang qua
    # resume, khong phai ve cost cap — job.source_lang="fr" dung
    # CHARS_PER_TOKEN_FR (thap hon EN, co chu dich) nen token uoc tinh cao
    # hon, co the cham tran $2 mac dinh tren 90 trang khong lien quan gi
    # toi hanh vi dang test o day.
    orchestrator = JobOrchestrator(
        settings=Settings(pdf_translate_engine="pdf2zh", cost_cap_enabled=False),
        pdf2zh_runner=runner,
        provider=_FakePricingProvider(),
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    first_result = await orchestrator.run_job(job.id, session)
    assert first_result.status == "failed"

    resumed_runner = _fake_pdf2zh_runner()
    orchestrator._pdf2zh_runner = resumed_runner
    second_result = await orchestrator.run_job(job.id, session)

    assert second_result.status == "completed"
    for call in resumed_runner.translate_pages.await_args_list:
        assert call.kwargs["lang_in"] == "fr"

    await session.refresh(job)
    assert job.source_lang == "fr"
