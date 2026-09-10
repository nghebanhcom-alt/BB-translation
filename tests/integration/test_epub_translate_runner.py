"""`JobOrchestrator.run_epub_job()` (Architecture.md 6.20.8, US-22 buoc 2/3).

Uses a FAKE `TranslationProvider` (no real API calls — those live in
`tests/test_epub_batch_golden_fixture.py`, Protocol 5 muc 3) so these tests
can assert exact data lineage (R6-02, Architecture.md 6.20.9): NOT just
"provider.translate() was awaited", but that the id/content flowing between
`EpubDocument.load()` -> payload -> LLM reply -> `write_translated()` ->
merged file stays correctly wired end to end, survives resume, and that the
BR-EPUB-05 guard (X3) actually fires on a broken pipeline.
"""

import json
import logging
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.core.prompt_builder import build_system_prompt
from src.models.batch import Batch
from src.models.chunk import Chunk
from src.models.glossary import Glossary, GlossaryEntry
from src.models.job import Job
from src.services.epub_document import EpubDocument
from src.services.translation import TranslationResult


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _build_epub(path: Path, *, paragraphs_per_doc: int = 3, n_docs: int = 2) -> Path:
    """2 tai lieu XHTML that trong spine, moi tai lieu co `paragraphs_per_doc`
    doan van — du de test chunk boundary (uu tien cat tai ranh gioi tai lieu,
    Architecture.md 6.20.7) va nhieu request/chunk."""
    container_xml = (
        '<?xml version="1.0"?>\n'
        '<container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    manifest_items = "".join(
        f'<item id="chap{i}" href="chap{i}.xhtml" media-type="application/xhtml+xml"/>'
        for i in range(n_docs)
    )
    spine_items = "".join(f'<itemref idref="chap{i}"/>' for i in range(n_docs))
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
        'unique-identifier="bookid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Test Book</dc:title><dc:language>en</dc:language>"
        '<dc:identifier id="bookid">urn:uuid:test-book</dc:identifier>'
        "</metadata>"
        f"<manifest>{manifest_items}</manifest>"
        f"<spine>{spine_items}</spine></package>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf)
        for i in range(n_docs):
            paragraphs = "".join(
                f"<p>Chapter {i} paragraph {j}: <strong>{j} cups</strong> flour.</p>"
                for j in range(paragraphs_per_doc)
            )
            xhtml = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<head><title>Chapter {i}</title></head><body>{paragraphs}</body></html>"
            )
            zf.writestr(f"OEBPS/chap{i}.xhtml", xhtml)
    return path


async def _create_epub_job(
    session: AsyncSession,
    epub_path: Path,
    model: str = "deepseek",
    *,
    # US-22 buoc 3/3: `run_epub_job()` gio doc `Batch.output_mode` qua
    # `_wants_bilingual()` (Architecture.md 6.20.11 muc 2) thay vi hardcode
    # `bilingual = True` — nen job test PHAI co `batch_id` tro toi 1 `Batch`
    # that voi `output_mode` mong muon, giong het cach PDF (`_resolve_batch()`
    # o src/api/routes/jobs.py) luon tao 1 Batch cho MOI job, ke ca job don
    # le. Mac dinh "bilingual" o day = dung PRD US-22 AC "mac dinh bat ban
    # song ngu", giu nguyen ky vong cua cac test EPUB da co TRUOC buoc 3/3.
    output_mode: str = "bilingual",
) -> Job:
    batch = Batch(total_files=1, output_mode=output_mode, model=model)
    session.add(batch)
    await session.flush()
    job = Job(
        batch_id=batch.id,
        filename=epub_path.name,
        file_path=str(epub_path),
        file_size=epub_path.stat().st_size,
        file_hash="deadbeef-epub",
        file_type="epub",
        model=model,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


class _FakeEpubProvider:
    """Deterministic transform: mirrors `build_epub_batch_prompt()`/
    `parse_epub_batch_response()`'s real JSON contract without any network
    call. `translate_fn(payload: list[dict]) -> dict[str, str] | None`
    controls the reply per call (`None` -> malformed JSON, to test the
    missing-id retry/failure paths); default mirrors X1/X2 by prefixing
    "VI:" onto each `html` value so lineage assertions can tell translated
    content apart from the English original.
    """

    provider_name = "fake"

    def __init__(self, translate_fn=None) -> None:
        self.calls: list[tuple[str, str]] = []  # (payload_json, system_prompt)
        self._translate_fn = translate_fn or self._default_translate

    @staticmethod
    def _default_translate(payload: list[dict]) -> dict[str, str]:
        return {item["id"]: f"VI:{item['html']}" for item in payload}

    async def translate(
        self, text: str, glossary_prompt: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        self.calls.append((text, glossary_prompt))
        payload = json.loads(text)
        reply = self._translate_fn(payload)
        reply_text = "{}" if reply is None else json.dumps(reply, ensure_ascii=False)
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
async def test_run_epub_job_completes_with_metered_cost_and_real_translated_content(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path)
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
    assert job.status == "completed"
    # E10: cost_source PHAI la 'metered' (chi phi THAT), khac PDF ('estimated').
    assert job.cost_source == "metered"
    assert job.actual_cost is not None
    assert job.actual_cost > 0
    assert job.total_units == 6  # 2 doc x 3 doan
    assert job.output_path is not None

    output_doc = EpubDocument.load(Path(job.output_path))
    # bilingual=True mac dinh (Architecture.md 6.20.11 muc 2) -> load() bo
    # qua node bb-vi, so unit khop dung file goc.
    assert len(output_doc.units) == 6

    with zipfile.ZipFile(job.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    assert "VI:" in chap0
    assert 'class="bb-vi"' in chap0
    assert 'lang="vi"' in chap0
    # Ban goc tieng Anh van con (bilingual = chen them, khong thay the).
    assert "Chapter 0 paragraph 0" in chap0


@pytest.mark.asyncio
async def test_run_epub_job_sends_system_prompt_with_json_contract_marker(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 (Architecture.md 6.20.9 soi day thu 4, (4)->(6)): assert NOI
    DUNG that gui cho provider.translate() — khong chi "da goi"."""
    epub_path = _build_epub(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path)
    provider = _FakeEpubProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    await orchestrator.run_job(job.id, session)

    assert provider.calls, "provider.translate() phai duoc goi it nhat 1 lan"
    for _payload_json, system_prompt in provider.calls:
        assert "BB-EPUB-JSON-CONTRACT-X4" in system_prompt


@pytest.mark.asyncio
async def test_run_epub_job_filters_glossary_by_full_text_matching_cost_gate(
    session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2/E3 fix (Architecture.md 6.20.9 dong 3/4, §6.11.6): nhanh EPUB phai
    goi `build_system_prompt()` voi `only_terms_present_in=doc.full_text()` —
    CUNG full_text ma `cost_gate.py::_estimate_epub_translation_cost()` dung
    de loc glossary khi uoc chi phi Lop 2. Truoc fix, nhanh EPUB goi
    `build_system_prompt(glossary_manager, project_id=...)` KHONG loc, nen
    prompt that gui di se chua CA glossary entry KHONG xuat hien trong tai
    lieu — Lop 2 (co loc) va prompt that (khong loc) lech nhau, vi pham
    §6.11.6.

    Assert 2 lop, ca hai deu la gia tri CU THE (R6-02), khong chi
    assert_called():
    1. Spy truc tiep tren `build_system_prompt()`: `only_terms_present_in`
       nhan duoc PHAI bang dung `doc.full_text()`.
    2. Noi dung prompt THAT gui cho `provider.translate()`: glossary entry co
       term xuat hien trong tai lieu ("flour") PHAI con lai; entry KHONG xuat
       hien ("yeast") PHAI bi loc bo — day la hau qua quan sat duoc cua diem
       (1), khong chi tin loi goi ham.
    """
    epub_path = _build_epub(tmp_path / "book.epub")
    expected_full_text = EpubDocument.load(epub_path).full_text()
    assert "flour" in expected_full_text.lower()
    assert "yeast" not in expected_full_text.lower()

    glossary = Glossary(name="global", scope="global")
    session.add(glossary)
    await session.flush()
    session.add(GlossaryEntry(glossary_id=glossary.id, term_en="flour", term_vi="bot mi"))
    session.add(GlossaryEntry(glossary_id=glossary.id, term_en="yeast", term_vi="men"))
    await session.commit()

    job = await _create_epub_job(session, epub_path)
    provider = _FakeEpubProvider()
    settings = Settings()

    orchestrator = JobOrchestrator(
        settings=settings,
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    real_build_system_prompt = build_system_prompt
    captured: dict[str, object] = {}

    async def _spy_build_system_prompt(glossary_manager, **kwargs):
        captured["only_terms_present_in"] = kwargs.get("only_terms_present_in")
        captured["max_glossary_entries"] = kwargs.get("max_glossary_entries")
        return await real_build_system_prompt(glossary_manager, **kwargs)

    monkeypatch.setattr("src.core.job_orchestrator.build_system_prompt", _spy_build_system_prompt)

    await orchestrator.run_job(job.id, session)

    assert captured["only_terms_present_in"] == expected_full_text
    assert captured["max_glossary_entries"] == settings.max_glossary_entries_in_prompt

    assert provider.calls, "provider.translate() phai duoc goi it nhat 1 lan"
    for _payload_json, system_prompt in provider.calls:
        assert "flour" in system_prompt
        assert "yeast" not in system_prompt


@pytest.mark.asyncio
async def test_run_epub_job_unit_id_lineage_maps_translation_to_correct_paragraph(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 (soi day (2)->(7)): moi unit phai nhan DUNG ban dich cua CHINH
    no, khong bi lech vi tri — kiem tra bang cach dich MOT unit CU THE thanh
    1 chuoi danh dau doc nhat va xac nhan no nam DUNG cho trong file output,
    khong phai o mot doan khac."""
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=3, n_docs=2)
    job = await _create_epub_job(session, epub_path)

    def _translate_fn(payload: list[dict]) -> dict[str, str]:
        out = {}
        for item in payload:
            if "paragraph 1" in item["html"] and "Chapter 1" in item["html"]:
                out[item["id"]] = "MARKER-UNIQUE-TRANSLATION-XYZ"
            else:
                out[item["id"]] = f"VI:{item['html']}"
        return out

    provider = _FakeEpubProvider(_translate_fn)
    orchestrator = JobOrchestrator(
        settings=Settings(),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    result = await orchestrator.run_job(job.id, session)
    assert result.status == "completed"

    await session.refresh(job)
    with zipfile.ZipFile(job.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
        chap1 = zf.read("OEBPS/chap1.xhtml").decode("utf-8")

    assert "MARKER-UNIQUE-TRANSLATION-XYZ" not in chap0
    assert "MARKER-UNIQUE-TRANSLATION-XYZ" in chap1


@pytest.mark.asyncio
async def test_run_epub_job_resume_merges_translations_from_all_completed_chunks(
    session: AsyncSession, tmp_path: Path
) -> None:
    """R6-02 (soi day (6)->(7)): gia lap crash sau chunk dau, chay lai — merge
    phai doc lai TAT CA chunk `completed` (ke ca chunk hoan thanh TU LAN
    CHAY TRUOC), khong chi chunk vua chay lan nay."""
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=2, n_docs=2)
    job = await _create_epub_job(session, epub_path)

    # Ngan sach nho -> moi tai lieu la 1 chunk rieng (uu tien cat tai ranh
    # gioi tai lieu, Architecture.md 6.20.7) -> 2 chunk cho 2 tai lieu (moi
    # tai lieu 2 unit x 36 ky tu THUAN/unit sau khi strip tag, khop dung
    # char_budget=72 -> cat dung tai ranh gioi tai lieu, moi chunk = 1
    # request duy nhat -> "call thu N" anh xa 1-1 voi "chunk thu N").
    settings = Settings(epub_chunk_char_budget=72, epub_request_char_budget=72)

    call_count = {"n": 0}

    def _fail_on_second_chunk(payload: list[dict]) -> dict[str, str] | None:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated crash mid-chunk")
        return {item["id"]: f"VI:{item['html']}" for item in payload}

    provider = _FakeEpubProvider(_fail_on_second_chunk)
    orchestrator = JobOrchestrator(
        settings=settings,
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    first_result = await orchestrator.run_job(job.id, session)
    assert first_result.status == "failed"

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = list(chunks_result.all())
    assert any(c.status == "completed" for c in chunks)
    assert any(c.status == "failed" for c in chunks)

    # Resume: retry_job() cua API layer reset chunk 'failed' -> 'pending' va
    # goi lai run_job(); mo phong dung cach do o day.
    for c in chunks:
        if c.status == "failed":
            c.status = "pending"
            session.add(c)
    job.status = "translating"
    session.add(job)
    await session.commit()

    provider2 = _FakeEpubProvider()  # lan nay khong loi nua
    orchestrator2 = JobOrchestrator(
        settings=settings,
        provider=provider2,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    second_result = await orchestrator2.run_job(job.id, session)
    assert second_result.status == "completed"

    with zipfile.ZipFile(second_result.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
        chap1 = zf.read("OEBPS/chap1.xhtml").decode("utf-8")
    # Ca 2 tai lieu (chunk 0 hoan thanh lan dau, chunk 1 hoan thanh sau
    # resume) deu phai co mat trong file merge cuoi cung.
    assert "VI:" in chap0
    assert "VI:" in chap1


@pytest.mark.asyncio
async def test_run_epub_job_missing_id_retried_individually_then_succeeds(
    session: AsyncSession, tmp_path: Path
) -> None:
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=2, n_docs=1)
    job = await _create_epub_job(session, epub_path)

    call_count = {"n": 0}

    def _translate_fn(payload: list[dict]) -> dict[str, str]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Batch dau: bo sot id "1" (E-09 shape) -> phai duoc goi lai rieng.
            return {item["id"]: f"VI:{item['html']}" for item in payload if item["id"] != "1"}
        return {item["id"]: f"VI:{item['html']}" for item in payload}

    provider = _FakeEpubProvider(_translate_fn)
    orchestrator = JobOrchestrator(
        settings=Settings(),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    with zipfile.ZipFile(result.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    assert "VI:Chapter 0 paragraph 0" in chap0
    assert "VI:Chapter 0 paragraph 1" in chap0
    # >= 2 goi: batch dau + it nhat 1 lan goi le cho id "1".
    assert len(provider.calls) >= 2


@pytest.mark.asyncio
async def test_run_epub_job_still_missing_after_retry_fails_chunk_no_empty_write(
    session: AsyncSession, tmp_path: Path
) -> None:
    """E-09/X4 diem 6, VAI TRO DOI boi Architecture.md §6.20.14.4 (Lop C,
    2026-09-10): id van thieu sau vong goi lai KHONG con tu dong lam chunk
    that bai (xem `test_epub_translate_guards.py` cho ca "trong han muc,
    van completed") — chunk chi that bai khi so unit fallback VUOT han muc
    CHUNK (20%). O day CA 2/2 id deu thieu (100% > 20%) nen van fail, dung
    E-09 vai tro moi ("chot chan bat thuong"), KHONG duoc ghi chuoi rong."""
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=2, n_docs=1)
    job = await _create_epub_job(session, epub_path)

    def _translate_fn(payload: list[dict]) -> dict[str, str]:
        return {}  # thieu ca 2/2 id -> vuot han muc chunk 20% (cho phep toi da 1)

    provider = _FakeEpubProvider(_translate_fn)
    orchestrator = JobOrchestrator(
        settings=Settings(),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    await session.refresh(job)
    assert "vuot han muc" in job.error_message
    assert "fallback" in job.error_message
    assert job.output_path is None


@pytest.mark.asyncio
async def test_run_epub_job_guard_fails_when_llm_returns_untranslated_text(
    session: AsyncSession, tmp_path: Path
) -> None:
    """BR-EPUB-05/X3 (bilingual=True): LLM tra NGUYEN VAN tieng Anh cho moi
    unit (khong dich gi ca) -> guard phai fail job, KHONG bao 'completed'
    tren noi dung chua dich (dung shape Bug #5, chi doi tu 'rong' sang 'chua
    dich')."""
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=3, n_docs=2)
    job = await _create_epub_job(session, epub_path)

    def _echo_back(payload: list[dict]) -> dict[str, str]:
        return {item["id"]: item["html"] for item in payload}  # KHONG dich gi

    provider = _FakeEpubProvider(_echo_back)
    orchestrator = JobOrchestrator(
        settings=Settings(),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    await session.refresh(job)
    assert job.status == "failed"
    assert "BR-EPUB-05" in job.error_message


@pytest.mark.asyncio
async def test_run_epub_job_stops_at_cost_capped_via_layer4_mid_first_chunk(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.20.13.2 (Lop 4, them sau QA vong 1/5): voi 1 tran
    THAP HON CA CHI PHI 1 REQUEST, Lop 4 bat truoc khi Lop 3 co co hoi chay —
    job dung ngay GIUA CHUNG DAU (chunk 0 khong con kip "completed" nua, ma
    'failed' voi `api_cost` da ghi nhan va `output_path=None`), khac hanh vi
    CU (truoc 6.20.13.2) khi Lop 3 chi kiem SAU KHI 1 chunk hoan tat toan bo
    — xem `test_run_epub_job_stops_at_cost_capped_via_layer3_between_chunks`
    o duoi cho kich ban Lop 3 van hoat dong DOC LAP khi tran nam GIUA 2
    chunk (khong bi Lop 4 chan truoc)."""
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=2, n_docs=2)
    job = await _create_epub_job(session, epub_path)
    job.cost_cap_usd = 0.0000001  # thap hon bat ky chi phi 1 request nao cua fake provider
    session.add(job)
    await session.commit()

    settings = Settings(
        epub_chunk_char_budget=80, epub_request_char_budget=80, cost_cap_enabled=True
    )
    provider = _FakeEpubProvider()
    orchestrator = JobOrchestrator(
        settings=settings,
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )
    result = await orchestrator.run_job(job.id, session)

    assert result.status == "cost_capped"
    await session.refresh(job)
    assert job.status == "cost_capped"
    assert job.cost_source == "metered"
    assert job.actual_cost is not None
    assert job.actual_cost > 0

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = list(chunks_result.all())
    # G-4 (Architecture.md 6.20.13.10): Lop 4 dung GIUA chunk 0 -> chunk do
    # KHONG con "completed", ma "failed" voi chi phi da ghi nhan va
    # output_path=None (khong lam mat dau vet tai chinh, Protocol 6).
    chunk0 = next(c for c in chunks if c.chunk_index == 0)
    assert chunk0.status == "failed"
    assert chunk0.api_cost is not None
    assert chunk0.api_cost > 0
    assert chunk0.output_path is None

    # NOTE (Dev, Architecture.md 6.20.13.2): voi nhanh EPUB, Lop 4 kiem tra
    # SAU MOI request trong 1 chunk bang CHINH bieu thuc `effective_cap` ma
    # Lop 3 dung — vi vay bat ky truong hop nao Lop 3 (hau-chunk) se trigger
    # thi Lop 4 (trong-chunk) DA trigger truoc do roi (Lop 4 la refinement
    # chat hon, khong phai co che song song doc lap). Lop 3's check ben duoi
    # trong `run_epub_job()` van GIU NGUYEN lam luoi phu (vd. cho nhanh PDF
    # dung chung khung — `run_job()`'s Step 7 — noi KHONG co Lop 4), nhung
    # tren nhanh EPUB no tro thanh khong con duong nao con lai de tu minh
    # trigger truoc Lop 4 nua. Khong viet them test "Lop 3 rieng trigger
    # doc lap tren EPUB" vi kich ban do khong con dat duoc sau fix nay.


class _SpuriousBracesProvider:
    """Mo phong DUNG hinh dang Bug #EPUB-B2-5 (Architecture.md §6.20.14.3,
    fixture that da golden-fixture-test o CAP PARSER don le trong
    `tests/test_epub_batch_golden_fixture.py`:
    `deepseek_batch_response_sourdough_single_object_spurious_closing_braces.json`
    — dung 1 dau '{' o dau nhung N dau '}' rai rac sau moi cap id/gia tri).
    Test nay dung lai CHINH hinh dang bug do nhung o CAP ORCHESTRATOR
    (tich hop, khong mock `parse_epub_batch_response_detailed()`) de xac
    nhan US-22 buoc 3/3 viec 1: `_process_epub_chunk()` da noi that
    `EpubParseOutcome`/`salvaged_count` vao logging, khong chi ham rut gon
    `parse_epub_batch_response()`.

    Voi payload N unit: id "0" luon cuu duoc qua duong JSON chuan (nam
    trong doi tuong `{...}` DUY NHAT), moi id con lai (1..N-1) CHI cuu duoc
    qua Lop B salvage — dung y het ty le cua fixture that (1/32 qua strict,
    31/32 qua salvage).
    """

    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def translate(
        self, text: str, glossary_prompt: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        self.calls.append(text)
        payload = json.loads(text)
        parts: list[str] = []
        for i, item in enumerate(payload):
            escaped_value = json.dumps(f"VI:{item['html']}", ensure_ascii=False)
            if i == 0:
                parts.append(f'{{"{item["id"]}": {escaped_value}}}')
            else:
                parts.append(f'"{item["id"]}": {escaped_value}}}')
        reply_text = "".join(parts)
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
async def test_run_epub_job_logs_salvaged_count_when_layer_b_engages(
    session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """US-22 buoc 3/3, viec 1 (BA escalate): 3 call site trong
    `_process_epub_chunk()` phai dung `parse_epub_batch_response_detailed()`
    va ghi log `salvaged_count` muc WARNING khi > 0 (Architecture.md
    §6.20.14.3 B-3 — `salvaged_count > 0` la tin hieu Lop B da phai can
    thiep). Chunk co dung 3 unit trong 1 request duy nhat (payload nho, du
    han muc `epub_request_char_budget` mac dinh) -> id "0" qua duong
    chuan, id "1"/"2" qua salvage -> `salvaged_count=2`.
    """
    epub_path = _build_epub(tmp_path / "book.epub", paragraphs_per_doc=3, n_docs=1)
    job = await _create_epub_job(session, epub_path)
    provider = _SpuriousBracesProvider()

    orchestrator = JobOrchestrator(
        settings=Settings(),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )

    with caplog.at_level(logging.WARNING, logger="src.core.job_orchestrator"):
        result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"

    salvage_logs = [r for r in caplog.records if "EPUB parse salvage" in r.getMessage()]
    assert salvage_logs, "phai co it nhat 1 log WARNING salvage khi Lop B can thiep"
    assert any(r.levelno == logging.WARNING for r in salvage_logs)
    assert any("salvaged_count=2" in r.getMessage() for r in salvage_logs)

    # Noi dung van dich dung du (salvage khong lam mat/sai ban dich), chi
    # khac cach parse ra duoc no.
    with zipfile.ZipFile(result.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    assert "VI:Chapter 0 paragraph 0" in chap0
    assert "VI:Chapter 0 paragraph 1" in chap0
    assert "VI:Chapter 0 paragraph 2" in chap0


@pytest.mark.asyncio
async def test_run_epub_job_monolingual_output_mode_has_no_english_original(
    session: AsyncSession, tmp_path: Path
) -> None:
    """US-22 buoc 3/3, viec 2: `output_mode=monolingual` phai duoc HONOR cho
    EPUB (truoc day hardcode `bilingual = True`, bo qua lua chon user) —
    output CHI co VI, KHONG chen them doan tieng Anh goc. Doi chieu voi
    `test_run_epub_job_completes_with_metered_cost_and_real_translated_content`
    (mac dinh bilingual): file .bb-vi node KHONG duoc them, va van ban tieng
    Anh goc KHONG con trong output (thay the, khong chen them).
    """
    epub_path = _build_epub(tmp_path / "book.epub")
    job = await _create_epub_job(session, epub_path, output_mode="monolingual")
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
    assert job.status == "completed"

    with zipfile.ZipFile(job.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    # Ban dich VI co mat.
    assert "VI:Chapter 0 paragraph 0" in chap0
    # bilingual=False -> THAY THE, khong chen them: khong co node bb-vi. Vi
    # ban dich la "VI:" + nguyen van goc, doan goc van xuat hien nhu 1 CHUOI
    # CON trong ban dich — phep so sanh dung la DEM so lan xuat hien: THAY
    # THE -> dung 1 lan (chi trong ban dich); CHEN THEM (bilingual) se la 2
    # lan (node goc + node bb-vi). Doi chieu voi test bilingual macdinh o
    # tren (dung "Chapter 0 paragraph 0" con NGUYEN trong output, tuc 2 lan).
    assert 'class="bb-vi"' not in chap0
    assert chap0.count("Chapter 0 paragraph 0") == 1

    # `load()` khong bo qua gi ca o che do monolingual (khong co bb-vi de
    # bo qua) -> so unit output = so unit input (khong mat chuong, X3).
    output_doc = EpubDocument.load(Path(job.output_path))
    assert len(output_doc.units) == 6
