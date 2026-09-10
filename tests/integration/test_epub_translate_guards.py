"""Guards MOI cua Architecture.md 6.20.13 (fix Bug #EPUB-B2-1 + Bug #EPUB-4,
sau QA vong 1/5): trong `JobOrchestrator._process_epub_chunk()`.

- 6.20.13.2 (Lop 4): tran chi phi SAU MOI request, khong doi het 1 chunk.
- 6.20.13.3a (fix C-1): tran so request phu cho vong goi lai vi thieu id.
- 6.20.13.3b (fix C-3): phat hien output "runaway" so voi CHINH payload.
- 6.20.13.5: guard mat dau tieng Viet 2 tang (request + unit).
- 6.20.13.7: ghi nhan anomaly vao `chunk_dir/anomalies.json` +
  `chunk_dir/requests.jsonl`.

Dung `_ControllableEpubProvider` (script theo tung LAN GOI) thay vi
`_FakeEpubProvider` cua `test_epub_translate_runner.py` — cac test o day can
kiem soat CHINH XAC `output_tokens` va noi dung tra ve o TUNG lan goi rieng
biet, thu khong lam duoc voi ham transform mac dinh (VI:{html}).
"""

import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.chunking import EPUB_MAX_SINGLE_ID_RETRIES
from src.core.config import Settings
from src.core.job_orchestrator import JobOrchestrator
from src.models.chunk import Chunk
from src.models.job import Job
from src.services.translation import TranslationResult

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _build_epub(path: Path, *, n_paragraphs: int = 2) -> Path:
    """1 tai lieu XHTML that trong spine voi `n_paragraphs` doan van NGAN —
    du de nam GON trong 1 request duy nhat khi budgets dat lon, cho phep cac
    test kiem soat toan bo noi dung TRA VE (`translate_fn`) ma khong phu
    thuoc do dai noi dung nguon."""
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
    paragraphs = "".join(f"<p>Paragraph {j}: flour.</p>" for j in range(n_paragraphs))
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


async def _create_epub_job(session: AsyncSession, epub_path: Path, model: str = "deepseek") -> Job:
    job = Job(
        filename=epub_path.name,
        file_path=str(epub_path),
        file_size=epub_path.stat().st_size,
        file_hash="deadbeef-epub-guard",
        file_type="epub",
        model=model,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


class _ControllableEpubProvider:
    """`script[i]` la callable `(payload: list[dict]) -> (reply_dict_or_None,
    output_tokens_override_or_None)` cho LAN GOI THU `i` (0-indexed). Lan goi
    vuot qua `len(script)` lap lai phan tu CUOI CUNG."""

    provider_name = "fake"

    def __init__(self, script) -> None:
        self.calls: list[str] = []
        self._script = script

    async def translate(
        self, text: str, glossary_prompt: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        idx = min(len(self.calls), len(self._script) - 1)
        self.calls.append(text)
        payload = json.loads(text)
        reply, output_tokens_override = self._script[idx](payload)
        reply_text = "{}" if reply is None else json.dumps(reply, ensure_ascii=False)
        output_tokens = (
            output_tokens_override if output_tokens_override is not None else len(reply_text)
        )
        return TranslationResult(
            text=reply_text,
            input_tokens=len(text),
            output_tokens=output_tokens,
            estimated_cost_usd=0.000001 * (len(text) + output_tokens),
            provider_name="fake",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0


def _make_orchestrator(
    tmp_path: Path, provider, settings: Settings | None = None
) -> JobOrchestrator:
    return JobOrchestrator(
        settings=settings or Settings(epub_chunk_char_budget=5_000, epub_request_char_budget=5_000),
        provider=provider,
        output_dir=tmp_path / "outputs",
        processing_dir=tmp_path / "processing",
    )


# --- 6.20.13.3a: tran so request phu (fix C-1) -----------------------------


async def test_more_than_max_single_id_retries_uses_one_whole_request_retry(
    session: AsyncSession, tmp_path: Path
) -> None:
    """>EPUB_MAX_SINGLE_ID_RETRIES id thieu -> KHONG goi lai tung id (se la
    6 request phu), ma goi lai NGUYEN request 1 lan duy nhat."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=6)
    job = await _create_epub_job(session, epub_path)
    # Architecture.md §6.20.14.2 A-3 (2026-09-10): HA tu 5 xuong 2 — slice
    # chi con toi da EPUB_REQUEST_MAX_UNITS (=6) unit sau A-1/A-2, nen tran 5
    # gan nhu luon nam trong nhanh "retry tung id". Test nay van dung logic
    # ">EPUB_MAX_SINGLE_ID_RETRIES id thieu -> goi lai NGUYEN request", chi
    # gia tri tran doi.
    assert EPUB_MAX_SINGLE_ID_RETRIES == 2

    def _first_call(payload: list[dict]) -> tuple[dict, None]:
        # Thieu ca 6/6 id (> EPUB_MAX_SINGLE_ID_RETRIES=2) -> nhanh goi lai
        # NGUYEN request, khong phai retry tung id rieng le.
        return {}, None

    def _second_call(payload: list[dict]) -> tuple[dict, None]:
        return {item["id"]: f"VI:{item['html']}" for item in payload}, None

    provider = _ControllableEpubProvider([_first_call, _second_call])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    # Dung 2 lan goi: request chinh (thieu het) + 1 lan goi lai NGUYEN
    # request — KHONG phai 1 + 6 (goi le tung id).
    assert len(provider.calls) == 2


async def test_still_missing_after_whole_request_retry_fails_chunk_over_ratio(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md §6.20.14.4 (Lop C, 2026-09-10) DOI hanh vi cu o day co
    chu dich (ten test cu la "...fails_chunk", khong con dung sau Lop C): 1
    unit thieu ban dich sau vong goi lai KHONG con tu dong lam chunk fail —
    no duoc giu nguyen tieng Anh (fallback), chunk chi that bai khi so unit
    fallback VUOT han muc CHUNK (20%). O day CA 6/6 unit deu thieu (100% >
    20%) nen chunk van fail — dung E-09 vai tro moi ("chot chan bat thuong"),
    khong phai "1 unit thieu la fail ngay" nhu truoc."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=6)
    job = await _create_epub_job(session, epub_path)

    def _always_missing_all(payload: list[dict]) -> tuple[dict, None]:
        # Luon thieu HET id -> qua nua batch thieu (6 unit, thieu 6 -> >2),
        # goi lai nguyen request 1 lan, van thieu ca 6/6 -> vuot han muc
        # chunk 20% (cho phep toi da 2/6) -> fail (E-09, vai tro moi).
        return {}, None

    provider = _ControllableEpubProvider([_always_missing_all])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    await session.refresh(job)
    assert "vuot han muc" in job.error_message
    assert "fallback" in job.error_message
    # Dung 2 lan goi (request chinh + 1 lan goi lai nguyen request), khong
    # phai vo han.
    assert len(provider.calls) == 2


async def test_missing_ids_within_chunk_ratio_fallback_to_english_job_completes(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md §6.20.14.4 (Lop C) — hanh vi MOI trung tam: 1 unit
    thieu ban dich sau vong goi lai NHUNG trong han muc chunk/job (1/20 = 5%
    <= 20% chunk VA <= 5% job) -> job VAN completed, unit do giu nguyen
    tieng Anh (fallback), duoc danh dau `bb-untranslated` trong output, va co
    mat trong `untranslated_units.json` cap job.

    20 unit (khong phai 6 nhu cac test khac trong file nay) — can THEM de
    BR-EPUB-05 (guard co san, >=90% node bb-vi) khong tu no fail: 1/6 fallback
    (~16,7%) da vuot khe ho 10% cua BR-EPUB-05 du van trong han muc rieng cua
    Lop C; 1/20 (5%) thi khong (dung dung tinh toan Architecture.md §6.20.14.5
    "nguong job 5% < khe ho 10% BR-EPUB-05").
    """
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=20)
    job = await _create_epub_job(session, epub_path)

    def _missing_one_id(payload: list[dict]) -> tuple[dict, None]:
        # Thieu dung 1/20 id ("0") — trong han muc CA chunk (20%) LAN job (5%).
        return {item["id"]: f"VI:{item['html']}" for item in payload if item["id"] != "0"}, None

    provider = _ControllableEpubProvider([_missing_one_id])
    orchestrator = _make_orchestrator(
        tmp_path,
        provider,
        settings=Settings(
            epub_chunk_char_budget=5_000,
            epub_request_char_budget=5_000,
            epub_request_max_units=100,  # giu dung 1 request cho toan bo 20 unit
        ),
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    await session.refresh(job)

    untranslated_path = Path(tmp_path / "outputs" / job.id / "untranslated_units.json")
    assert untranslated_path.exists()
    fallback_entries = json.loads(untranslated_path.read_text(encoding="utf-8"))
    assert len(fallback_entries) == 1
    assert fallback_entries[0]["unit_id"] == "OEBPS/chap0.xhtml#0"
    assert fallback_entries[0]["reason"] == "missing_after_retry"

    merged_epub_path = Path(job.output_path)
    with zipfile.ZipFile(merged_epub_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    assert "bb-untranslated" in chap0
    assert 'lang="en"' in chap0


async def test_fallback_exceeding_job_ratio_fails_job_after_accumulating_across_chunks(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md §6.20.14.4 C-3 — nguong JOB (5%) cong don qua NHIEU
    chunk (khong chi 1 chunk), doc lai `fallback_units.json` cua tung chunk
    dir thay vi chi dua vao bien dem trong bo nho — day chinh la co che song
    sot qua resume (BR-CHUNK-05). Sach 20 unit, chia 4 chunk x5 unit; chunk 0
    va chunk 1 moi chunk fallback dung 1 unit (trong han muc CHUNK rieng —
    20% cua 5 = 1) nhung CONG DON 2 unit > han muc JOB (5% cua 20 = 1) ->
    job phai fail NGAY SAU chunk 1, KHONG xu ly tiep chunk 2/3 (tiet kiem
    tien, dung tinh than Lop 3/4 da co)."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=20)
    job = await _create_epub_job(session, epub_path)

    def _missing_id_zero_if_present(payload: list[dict]) -> tuple[dict, None]:
        # Bat ke goi chinh (5 item) hay goi lai rieng le (1 item), luon thieu
        # dung id "0" neu no co mat trong payload nay — moi chunk deu co 1
        # unit local id "0" (unit dau tien cua chunk).
        return {item["id"]: f"VI:{item['html']}" for item in payload if item["id"] != "0"}, None

    provider = _ControllableEpubProvider([_missing_id_zero_if_present])
    orchestrator = _make_orchestrator(
        tmp_path,
        provider,
        settings=Settings(
            epub_chunk_char_budget=100,  # ep 4 chunk x5 unit (~21 ky tu/unit)
            epub_request_char_budget=5_000,
            epub_request_max_units=100,  # giu dung 1 request/chunk
        ),
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    await session.refresh(job)
    assert "fallback" in job.error_message
    assert "5%" in job.error_message or "unit" in job.error_message

    chunks_result = await session.exec(
        select(Chunk).where(Chunk.job_id == job.id).order_by(Chunk.chunk_index)
    )
    all_chunks = list(chunks_result.all())
    assert len(all_chunks) == 4  # xac nhan dung ca that 4 chunk (khong phai 1)
    completed_chunks = [c for c in all_chunks if c.status == "completed"]
    # Fail NGAY SAU chunk thu 2 (index 1) — chunk 2/3 KHONG duoc xu ly.
    assert len(completed_chunks) == 2


async def test_fallback_job_ratio_survives_resume_across_orchestrator_instances(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md §6.20.14.4 C-3 — kiem thu THAT su "song sot qua
    resume" (khong chi cong don trong 1 vong lap cua CUNG 1 instance): chunk
    0 hoan thanh voi 1 fallback unit (trong han muc), roi orchestrator
    THU NHAT crash o chunk 1 (RuntimeError gia lap) TRUOC khi kip fallback
    gi — job that bai binh thuong (khong phai do Lop C). Resume bang 1
    JobOrchestrator MOI HOAN TOAN (khong con bien nao trong bo nho tu lan
    chay truoc) — o lan chay nay chunk 1 lai co 1 fallback unit khac, cong
    don voi fallback cua chunk 0 (da ghi tren dia tu lan chay truoc) VUOT
    han muc JOB -> job that bai, dung boi doc lai `fallback_units.json` tu
    DIA, khong phai bo dem trong bo nho (vi instance moi khong the co bo dem
    do)."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=20)
    job = await _create_epub_job(session, epub_path)
    settings = Settings(
        epub_chunk_char_budget=100,  # ep 4 chunk x5 unit
        epub_request_char_budget=5_000,
        epub_request_max_units=100,
    )

    call_count = {"n": 0}

    def _first_run_script(payload: list[dict]) -> tuple[dict, None]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Chunk 0: fallback dung 1 unit (id "0"), trong han muc CHUNK
            # (20% cua 5 = 1) VA trong han muc JOB rieng no (5% cua 20 = 1).
            return {item["id"]: f"VI:{item['html']}" for item in payload if item["id"] != "0"}, None
        if call_count["n"] == 2:
            # Chunk 0 retry-rieng-le cho id "0" — van thieu (deterministic).
            return {}, None
        # Chunk 1: crash NGAY, mo phong loi ha tang giua chung (RuntimeError
        # thong thuong, KHONG lien quan Lop C).
        raise RuntimeError("simulated crash mid-chunk 1")

    provider1 = _ControllableEpubProvider([_first_run_script])
    orchestrator1 = _make_orchestrator(tmp_path, provider1, settings=settings)
    first_result = await orchestrator1.run_job(job.id, session)
    assert first_result.status == "failed"

    chunks_result = await session.exec(
        select(Chunk).where(Chunk.job_id == job.id).order_by(Chunk.chunk_index)
    )
    all_chunks = list(chunks_result.all())
    assert all_chunks[0].status == "completed"
    assert all_chunks[1].status == "failed"

    # Resume: dung CACH y het `retry_job()` cua API layer + test resume co
    # san trong test_epub_translate_runner.py — reset chunk 'failed' ->
    # 'pending', tao JobOrchestrator MOI.
    for c in all_chunks:
        if c.status == "failed":
            c.status = "pending"
            session.add(c)
    job.status = "translating"
    session.add(job)
    await session.commit()

    def _second_run_missing_id_zero(payload: list[dict]) -> tuple[dict, None]:
        # Chunk 1 (va cac chunk sau, neu co chay toi) o LAN CHAY THU HAI:
        # lai thieu dung id "0" — cong don voi fallback cua chunk 0 (da ghi
        # tren dia tu lan chay TRUOC, KHONG con trong bo nho cua instance
        # MOI nay) se vuot han muc job (2 > 1).
        return {item["id"]: f"VI:{item['html']}" for item in payload if item["id"] != "0"}, None

    provider2 = _ControllableEpubProvider([_second_run_missing_id_zero])
    orchestrator2 = _make_orchestrator(tmp_path, provider2, settings=settings)
    second_result = await orchestrator2.run_job(job.id, session)

    assert second_result.status == "failed"
    await session.refresh(job)
    assert "fallback" in job.error_message

    chunks_result = await session.exec(
        select(Chunk).where(Chunk.job_id == job.id).order_by(Chunk.chunk_index)
    )
    all_chunks = list(chunks_result.all())
    # Chunk 0 (tu lan chay truoc) + chunk 1 (lan nay) completed; chunk 2/3
    # KHONG duoc xu ly (fail som ngay sau chunk 1 o lan chay thu hai).
    completed_chunks = [c for c in all_chunks if c.status == "completed"]
    assert len(completed_chunks) == 2


# --- 6.20.13.3b: phat hien runaway output (fix C-3) -------------------------


def _big_payload_paragraphs() -> int:
    # Du unit de payload_json dat ~ vai nghin ky tu, cho 3.0x/1500-floor deu
    # co the kich hoat mot cach thuc te (khong chi dua vao floor).
    return 10


async def test_runaway_ra_kept_when_parse_succeeds(session: AsyncSession, tmp_path: Path) -> None:
    """R-a (Architecture.md 6.20.13.3b bang): runaway NHUNG parse du id, hop
    le -> GIU ket qua, chi ghi nhan anomaly — KHONG retry, KHONG fail."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=_big_payload_paragraphs())
    job = await _create_epub_job(session, epub_path)

    def _runaway_but_complete(payload: list[dict]) -> tuple[dict, int]:
        reply = {item["id"]: f"VI:{item['html']}" for item in payload}
        # output_tokens gia tao rat lon -> chac chan vuot EPUB_RUNAWAY_OUTPUT_FACTOR.
        return reply, 50_000

    provider = _ControllableEpubProvider([_runaway_but_complete])
    # Architecture.md §6.20.14.2 A-1 them EPUB_REQUEST_MAX_UNITS (default 6)
    # — voi 10 paragraph (_big_payload_paragraphs()) se tach thanh 2 request
    # neu dung default, lam nhiem muc dich CO LAP cua test nay (kiem RIENG
    # logic runaway R-a, khong lien quan Lop A). Nang `epub_request_max_units`
    # de giu dung 1 request nhu truoc A-1.
    orchestrator = _make_orchestrator(
        tmp_path,
        provider,
        settings=Settings(
            epub_chunk_char_budget=5_000,
            epub_request_char_budget=5_000,
            epub_request_max_units=100,
        ),
    )

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    # KHONG retry -> dung 1 lan goi duy nhat.
    assert len(provider.calls) == 1

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunk = chunks_result.one()
    anomalies_path = Path(
        tmp_path / "processing" / job.id / f"chunk_{chunk.chunk_index}" / "anomalies.json"
    )
    assert anomalies_path.exists()
    anomalies = json.loads(anomalies_path.read_text(encoding="utf-8"))
    assert len(anomalies["runaway_requests"]) == 1
    assert anomalies["runaway_requests"][0]["action"] == "kept"

    requests_jsonl_path = anomalies_path.parent / "requests.jsonl"
    assert requests_jsonl_path.exists()
    lines = requests_jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    logged = json.loads(lines[0])
    assert logged["output_tokens"] == 50_000


async def test_runaway_rb_aborted_when_missing_ids(session: AsyncSession, tmp_path: Path) -> None:
    """R-b (Architecture.md 6.20.13.3b bang): runaway VA thieu id/hong ->
    abort NGAY, KHONG chay vong goi lai (moi retry sau 1 runaway hong la con
    duong khuech dai C-1)."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=_big_payload_paragraphs())
    job = await _create_epub_job(session, epub_path)

    def _runaway_and_broken(payload: list[dict]) -> tuple[dict, int]:
        # Thieu id cuoi cung + output_tokens gia tao rat lon.
        reply = {item["id"]: f"VI:{item['html']}" for item in payload[:-1]}
        return reply, 50_000

    provider = _ControllableEpubProvider([_runaway_and_broken])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "failed"
    await session.refresh(job)
    assert "EpubRequestRunawayError" in job.error_message or "runaway" in job.error_message
    # KHONG chay vong goi lai nao ca -> dung 1 lan goi duy nhat.
    assert len(provider.calls) == 1


# --- 6.20.13.5: guard mat dau tieng Viet 2 tang -----------------------------


_VI_LONG_NO_DAU = (
    "day la ban dich hoan toan khong co dau tieng viet du da co du chu cai "
    "de vuot qua nguong toi thieu can thiet cho phep do o muc request " * 2
)
_VI_LONG_WITH_DAU = (
    "đây là bản dịch đầy đủ dấu tiếng việt, đủ chữ cái để vượt qua ngưỡng "
    "tối thiểu cần thiết cho phép đo ở mức request " * 2
)


async def test_low_diacritic_request_retried_and_improved_is_used(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Tang 1 (muc REQUEST): ratio thap -> goi lai NGUYEN request 1 lan; ban
    retry co ratio CAO HON -> dung ban retry."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=1)
    job = await _create_epub_job(session, epub_path)

    def _no_dau(payload: list[dict]) -> tuple[dict, None]:
        return {item["id"]: _VI_LONG_NO_DAU for item in payload}, None

    def _with_dau(payload: list[dict]) -> tuple[dict, None]:
        return {item["id"]: _VI_LONG_WITH_DAU for item in payload}, None

    provider = _ControllableEpubProvider([_no_dau, _with_dau])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert len(provider.calls) == 2  # 1 goi chinh + 1 goi lai nguyen request

    with zipfile.ZipFile(result.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    assert "đây là bản dịch" in chap0


async def test_low_diacritic_request_retried_but_not_improved_keeps_original(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Ban retry KHONG co ratio cao hon -> giu ban dau, dung doi lay thu te
    hon (Architecture.md 6.20.13.5)."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=1)
    job = await _create_epub_job(session, epub_path)

    def _no_dau(payload: list[dict]) -> tuple[dict, None]:
        return {item["id"]: _VI_LONG_NO_DAU for item in payload}, None

    provider = _ControllableEpubProvider([_no_dau, _no_dau, _no_dau])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    # KHONG fail chunk (chap nhan + ghi nhan, khong phai loi chan cung).
    assert result.status == "completed"
    # 1 request chinh + 1 goi lai tang 1 (khong cai thien, giu ban dau) +
    # 1 goi lai tang 2 (unit van con thap sau tang 1 khong doi gi) = 3.
    assert len(provider.calls) == 3


async def test_low_diacritic_unit_tier_retried_and_resolved(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Tang 2 (muc UNIT): 1 unit rieng le mat dau trong khi ca request van
    tren nguong (nho unit con lai giau dau) -> chi unit do duoc goi lai
    RIENG LE, dung CHUNG helper voi X4/C-1."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=2)
    job = await _create_epub_job(session, epub_path)

    # Unit "0" giau dau (~300 chu cai, > 90% co dau) de KEO ty le TOAN BO
    # request vuot qua nguong tang 1 (0,08) mac du unit "1" khong dau.
    unit0_rich_diacritics = ("được nướng vàng đều, thơm phức và mềm mịn " * 8).strip()
    unit1_no_dau = ("day la mot doan van khong dau du dai qua nguong toi thieu " * 2).strip()
    unit1_fixed = ("đây là một đoạn văn có dấu đủ dài qua ngưỡng tối thiểu " * 2).strip()

    def _first_call(payload: list[dict]) -> tuple[dict, None]:
        return {"0": unit0_rich_diacritics, "1": unit1_no_dau}, None

    def _retry_unit1(payload: list[dict]) -> tuple[dict, None]:
        # Retry rieng le chi co 1 phan tu trong payload (id "1").
        assert len(payload) == 1
        return {payload[0]["id"]: unit1_fixed}, None

    provider = _ControllableEpubProvider([_first_call, _retry_unit1])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"
    assert len(provider.calls) == 2

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunk = chunks_result.one()
    anomalies_path = Path(
        tmp_path / "processing" / job.id / f"chunk_{chunk.chunk_index}" / "anomalies.json"
    )
    assert anomalies_path.exists()
    anomalies = json.loads(anomalies_path.read_text(encoding="utf-8"))
    assert len(anomalies["low_diacritic_units"]) == 1
    assert anomalies["low_diacritic_units"][0]["retried"] is True
    assert anomalies["low_diacritic_units"][0]["resolved"] is True
    # Tang 1 khong duoc kich hoat (ty le toan request van tren nguong).
    assert anomalies["low_diacritic_requests"] == []

    with zipfile.ZipFile(result.output_path) as zf:
        chap0 = zf.read("OEBPS/chap0.xhtml").decode("utf-8")
    assert "đây là một đoạn văn" in chap0


async def test_low_diacritic_unit_tier_retried_but_unresolved_is_accepted_not_failed(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Sau retry van con mat dau -> CHAP NHAN + ghi nhan, KHONG fail chunk
    (Architecture.md 6.20.13.5's quyet dinh (a))."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=2)
    job = await _create_epub_job(session, epub_path)

    unit0_rich_diacritics = ("được nướng vàng đều, thơm phức và mềm mịn " * 8).strip()
    unit1_no_dau = ("day la mot doan van khong dau du dai qua nguong toi thieu " * 2).strip()

    def _reply(payload: list[dict]) -> tuple[dict, None]:
        if len(payload) == 1:
            return {payload[0]["id"]: unit1_no_dau}, None
        return {"0": unit0_rich_diacritics, "1": unit1_no_dau}, None

    provider = _ControllableEpubProvider([_reply, _reply])
    orchestrator = _make_orchestrator(tmp_path, provider)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "completed"

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunk = chunks_result.one()
    anomalies_path = Path(
        tmp_path / "processing" / job.id / f"chunk_{chunk.chunk_index}" / "anomalies.json"
    )
    anomalies = json.loads(anomalies_path.read_text(encoding="utf-8"))
    assert anomalies["low_diacritic_units"][0]["retried"] is True
    assert anomalies["low_diacritic_units"][0]["resolved"] is False


# --- 6.20.13.2: Lop 4 — tran chi phi SAU MOI request ------------------------


async def test_layer4_stops_mid_first_chunk_and_persists_partial_cost(
    session: AsyncSession, tmp_path: Path
) -> None:
    """G-4 (Architecture.md 6.20.13.10): cap thap hon chi phi 1 request ->
    job dung `cost_capped` GIUA CHUNG 1 chunk (chunk do `failed`, `api_cost`
    khac 0, `output_path` la NULL) — muc "vuot tran toi da de lot" tut xuong
    con chi phi 1 REQUEST, khong phai 1 chunk."""
    epub_path = _build_epub(tmp_path / "book.epub", n_paragraphs=2)
    job = await _create_epub_job(session, epub_path)
    job.cost_cap_usd = 0.0000001  # thap hon bat ky chi phi that nao
    session.add(job)
    await session.commit()

    settings = Settings(
        epub_chunk_char_budget=5_000, epub_request_char_budget=5_000, cost_cap_enabled=True
    )

    def _reply(payload: list[dict]) -> tuple[dict, None]:
        return {item["id"]: f"VI:{item['html']}" for item in payload}, None

    provider = _ControllableEpubProvider([_reply])
    orchestrator = _make_orchestrator(tmp_path, provider, settings=settings)

    result = await orchestrator.run_job(job.id, session)

    assert result.status == "cost_capped"
    await session.refresh(job)
    assert job.status == "cost_capped"
    assert job.cost_source == "metered"
    assert job.actual_cost is not None
    assert job.actual_cost > 0

    chunks_result = await session.exec(select(Chunk).where(Chunk.job_id == job.id))
    chunks = list(chunks_result.all())
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.status == "failed"
    assert chunk.api_cost is not None
    assert chunk.api_cost > 0
    assert chunk.output_path is None
    # Chi 1 lan goi duy nhat -> Lop 4 dung NGAY sau request dau tien, khong
    # doi het chunk (dung 6.20.13.2's "hieu qua dinh luong").
    assert len(provider.calls) == 1
