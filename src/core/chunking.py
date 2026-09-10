"""Page-range chunking algorithm (Architecture.md section 6.1, BR-CHUNK-01..05).

Naming note: the plan-level chunk here is called `ChunkPlan`, not `Chunk` —
`Chunk` is already the SQLModel DB table in `src/models/chunk.py`. Reusing
that name for a plain dataclass would shadow the DB model in any module that
imports both (the Job Orchestrator does).
"""

import re
from dataclasses import dataclass

from src.services.epub_document import EpubUnit

#: BR-CHUNK-01: chunk only when the file exceeds either threshold.
CHUNK_THRESHOLD_PAGES = 50
CHUNK_THRESHOLD_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class ChunkPlan:
    index: int
    page_start: int
    page_end: int
    overlap_start: int | None
    overlap_end: int | None


def calculate_chunks(total_pages: int, chunk_size: int = 40, overlap: int = 2) -> list[ChunkPlan]:
    """Split `total_pages` into overlapping page-range chunks.

    Matches the worked example in Architecture.md section 6.1: 120 pages,
    chunk_size=40, overlap=2 -> chunks [1-40], [39-80], [79-120], where the
    leading `overlap` pages of every chunk after the first (39-40, 79-80) are
    context-only carried over from the previous chunk, not re-translated.

    The literal formula in the Architecture.md code sample (`overlap_start =
    max(1, start - overlap)`) does not reproduce that worked example — e.g. it
    yields overlap_start=37 for chunk 1, not 39. This implementation instead
    derives the formula from the worked example and from the prose right
    below it ("Pages {overlap_start}-{overlap_end} la context ... Chi dich tu
    page {actual_start}"), which requires overlap_start == page_start.
    """
    if total_pages < 1:
        raise ValueError("total_pages must be >= 1")
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    chunks: list[ChunkPlan] = []
    start = 1
    idx = 0
    while start <= total_pages:
        if idx == 0:
            end = min(start + chunk_size - 1, total_pages)
            overlap_start: int | None = None
            overlap_end: int | None = None
        else:
            end = min(start + overlap + chunk_size - 1, total_pages)
            overlap_start = start
            overlap_end = min(start + overlap - 1, end)

        chunks.append(
            ChunkPlan(
                index=idx,
                page_start=start,
                page_end=end,
                overlap_start=overlap_start,
                overlap_end=overlap_end,
            )
        )

        if end >= total_pages:
            break
        start = end - overlap + 1
        idx += 1

    return chunks


def plan_chunks(
    total_pages: int,
    file_size_bytes: int,
    chunk_size: int = 40,
    overlap: int = 2,
) -> list[ChunkPlan]:
    """BR-CHUNK-01: only chunk when the file exceeds 50 pages or 20MB.

    Otherwise the whole file is processed as a single chunk covering every
    page, so downstream code (Job Orchestrator, chunk merge) never needs a
    separate "no-chunking" code path.
    """
    if total_pages <= CHUNK_THRESHOLD_PAGES and file_size_bytes <= CHUNK_THRESHOLD_BYTES:
        return [
            ChunkPlan(
                index=0,
                page_start=1,
                page_end=total_pages,
                overlap_start=None,
                overlap_end=None,
            )
        ]
    return calculate_chunks(total_pages, chunk_size=chunk_size, overlap=overlap)


# ---------------------------------------------------------------------------
# EPUB chunking (Architecture.md 6.20.7, quyết định chốt tại 6.20.12).
# KHÔNG đụng ChunkPlan/calculate_chunks/plan_chunks ở trên — đơn vị đo hoàn
# toàn khác (unit văn bản, không phải trang PDF), và KHÔNG có overlap (một
# unit EPUB là 1 đoạn văn hoàn chỉnh, không có gì bị cắt ngang cần nối lại).
# ---------------------------------------------------------------------------

#: Z3 (Architecture.md 6.20.7): granularity cua checkpoint chi phi (Lop 3) —
#: KHONG phai gioi han context. Muc "vuot tran" toi da ma Lop 3 co the de lot
#: = dung 1 chunk. Ca 3 hang so nay cung ton tai trong `Settings`
#: (`src/core/config.py::epub_chunk_char_budget` v.v.) de override qua
#: `.env`; module constant o day la GIA TRI MAC DINH dung khi goi truc tiep
#: (vd trong test), giong het pattern CHUNK_THRESHOLD_PAGES/BYTES o tren.
EPUB_CHUNK_CHAR_BUDGET = 8_000
#: Gioi han kich thuoc 1 loi goi LLM (khac muc dich voi hang so tren — xem
#: Z3). Architecture.md §6.20.14.2 A-1 (2026-09-10, sau khi cham gioi han
#: Protocol 3 voi Bug #EPUB-B2-5): HA tu 3.000 xuong 1.100 — suy tu so lieu
#: THAT (§6.20.14.0a): muc tieu giu `output_tokens` moi request ve vung DA
#: QUAN SAT la sach (<= ~600 token). ⚠️ ASSUMED ve HIEU QUA giam tan suat loi
#: (xac suat, khong phai nguong cung — xem §6.20.14.0 "bang chung NGUOC").
EPUB_REQUEST_CHAR_BUDGET = 1_100
#: MOI (Architecture.md §6.20.14.2 A-1) — tran thu HAI theo SO UNIT, khong
#: chi ky tu: `EPUB_REQUEST_CHAR_BUDGET` do bang ky tu VAN BAN THUAN
#: (`_plain_char_len()`, strip tag), nen 1 request co the chua rat nhieu unit
#: ma van "trong ngan sach" neu moi unit chi la 1 dong tag HTML ngan (vd
#: `<strong>1 cup starter</strong>`) — chinh xac hinh dang cua batch 32 unit
#: da gay Bug #EPUB-B2-5. So KHOA JSON (= so unit) moi la thu model phai giu
#: dung cu phap, khong phai so ky tu. ⚠️ ASSUMED.
EPUB_REQUEST_MAX_UNITS = 6
#: Y4 (Architecture.md 6.20.12): 1 unit vuot nguong nay -> job phai fail ro
#: rang (khong cat cau o v1) — vuot ~13.000 ky tu EN lam output LLM bi cut,
#: JSON hong, retry le van cut. Chua cham du lieu that (max unit cua file mau
#: chi 989 ky tu), xem Architecture.md 6.20.11 muc 7.
EPUB_UNIT_HARD_MAX_CHARS = 10_000

#: X5 (Architecture.md 6.20.6/6.20.12, US-22 buoc 2/3) — `doc.total_chars`
#: (text thuan qua bs4) UOC THAP chi phi that gui cho LLM 29,0% neu dung
#: thang, vi pham §6.11.6 ("duoc uoc cao, CAM uoc thap"). Hai so hang bi
#: thieu, do that tren 384 unit cua "Baking with Sourdough":
#:   1. X2 chuyen unit sang inner-HTML (khong phai text thuan) — content
#:      chars 57.247 vs 52.369 (+9,3%, N-2 — Expert KHONG do so hang nay).
#:      1.15 lam tron LEN tu 1.093 do duoc.
#:   2. Envelope JSON (`{"id": "...", "html": "..."}` cho id ngan 0..N) cong
#:      them ~26,7 ky tu/unit do duoc, lam tron LEN thanh 30.
#: Kiem chung: 52.369 * 1.15 + 384 * 30 = 71.744 vs payload that 67.577 ->
#: 1.06x — cao hon that, dung chieu §6.11.6 cho phep. Dat CANH
#: EPUB_CHUNK_CHAR_BUDGET nhu Architecture.md yeu cau ("2 hang so co ten,
#: dat canh EPUB_CHUNK_CHAR_BUDGET"). KHONG sua estimate_job_cost_v2() —
#: chi doi dau vao source_text_chars cua no (cost_gate.py).
EPUB_INLINE_MARKUP_FACTOR = 1.15
EPUB_JSON_ENVELOPE_CHARS_PER_UNIT = 30

#: Architecture.md 6.20.13.3a (fix C-1) — tran so lan goi lai TUNG-ID rieng le
#: khi 1 response bi thieu id. HA tu 5 xuong 2 boi §6.20.14.2 A-3
#: (2026-09-10): voi slice chi con toi da `EPUB_REQUEST_MAX_UNITS` (=6) unit
#: sau A-1, tran 5 gan nhu luon roi vao nhanh "retry TUNG id" (>=3/6 thieu
#: van con duoi tran 5) — dat hon han 1 lan goi lai NGUYEN request. ⚠️ ASSUMED.
EPUB_MAX_SINGLE_ID_RETRIES = 2
#: Tran CUNG cho TOAN BO 1 slice (1 request trong `chunk_plan.requests`),
#: dung CHUNG quota cho ca retry vi thieu id (tren) VA retry vi mat dau
#: (Architecture.md 6.20.13.5) — 2 co che khong cong don. HA tu 6 xuong 3 boi
#: §6.20.14.2 A-3 (dong bo voi slice nho hon sau A-1/A-2). ⚠️ ASSUMED.
EPUB_MAX_EXTRA_REQUESTS_PER_SLICE = 3

#: Architecture.md §6.20.14.4 C-2 (Lop C — E-09 tu "luat mac dinh" thanh
#: "chot chan bat thuong"). Ngan CHUNK: 20% so unit cua chinh chunk do, cho
#: phep toi thieu 1 unit (`allowed = max(1, ceil(0.20 * n_units_in_chunk))`)
#: — sau Lop A, 1 chunk co ~55 unit / ~7-9 request; 1 request mat TRON VEN =
#: 6 unit ~ 11% chunk, nen 20% chiu duoc 2 request hong hoan toan trong 1
#: chunk nhung "ca chunk hong" van fail ngay. ⚠️ ASSUMED — PHAI do lai bang du
#: lieu live.
EPUB_FALLBACK_MAX_RATIO_CHUNK = 0.20
#: Ngan JOB: 5% cong don tren toan sach. KHONG phai cam tinh — bi BR-EPUB-05
#: (guard output §6.20.12 X3, fail khi < 90% unit khac ban goc) ep: unit
#: fallback giu nguyen EN == giong het ban goc == dem vao dung 10% khe ho do.
#: Dat tran o 5% de con nguyen mot nua khe ho cho cac nguyen nhan khac. Dat
#: >= 10% se khien Lop C tu tay lam BR-EPUB-05 fail. ⚠️ ASSUMED (gia tri cu
#: the), nhung TRAN TREN (< 10%) la bat buoc toan hoc, khong duoc tu y nang.
EPUB_FALLBACK_MAX_RATIO_JOB = 0.05

_TAG_RE = re.compile(r"<[^>]+>")


class EpubUnitTooLargeError(ValueError):
    """Y4: 1 `EpubUnit.text` (inner-HTML) vuot `EPUB_UNIT_HARD_MAX_CHARS` ky
    tu — caller (Job Orchestrator, buoc 2/3) phai danh dau job `failed` voi
    dung `unit_id` nay, KHONG duoc tu cat ngan noi dung."""

    def __init__(self, unit_id: str, char_len: int) -> None:
        super().__init__(
            f"Unit '{unit_id}' co {char_len} ky tu, vuot EPUB_UNIT_HARD_MAX_CHARS "
            f"({EPUB_UNIT_HARD_MAX_CHARS})"
        )
        self.unit_id = unit_id
        self.char_len = char_len


@dataclass(frozen=True)
class EpubChunkPlan:
    index: int
    unit_start: int  # chi so unit TOAN SACH, 0-based, INCLUSIVE
    unit_end: int  # INCLUSIVE
    requests: list[tuple[int, int]]  # cac lat (start, end) INCLUSIVE trong pham vi chunk nay


def _plain_char_len(unit: EpubUnit) -> int:
    """Uoc luong so ky tu VAN BAN THUAN cua 1 unit, dung lam thuoc do cho
    ngan sach chunk/request — CHI dung cho muc dich cat ranh gioi (checkpoint
    spacing), KHONG dung cho cong thuc chi phi (do o cost_gate, buoc 2/3, dua
    tren `EpubDocument.total_chars` that qua bs4, khong qua regex nay).
    Regex tag-strip la du chinh xac o day vi sai lech vai % khong anh huong
    gi den tinh dung dan — no chi doi vi tri cat 1 chunk di vai unit."""
    return len(_TAG_RE.sub("", unit.text))


def plan_epub_chunks(
    units: list[EpubUnit],
    char_budget: int = EPUB_CHUNK_CHAR_BUDGET,
    request_budget: int = EPUB_REQUEST_CHAR_BUDGET,
    request_max_units: int = EPUB_REQUEST_MAX_UNITS,
) -> list[EpubChunkPlan]:
    """Chunk = 1 day unit LIEN TIEP theo thu tu spine (units da o dung thu tu
    do, vi EpubDocument.load() duyet spine truoc khi tra ve).

    Cat UU TIEN tai ranh gioi tai lieu (khong buoc mot phan nho cua tai lieu
    ke tiep vao chunk da du ngan sach), nhung KHONG bi rang buoc boi no: neu
    1 tai lieu tu no da vuot ngan sach (vd chapter01.html chiem 97% cuon
    Sourdough that), cat tiep BEN TRONG no theo dung ranh gioi unit — khong
    bao gio cat giua 1 doan van.

    Trong moi chunk, gom tiep cac unit lien tiep thanh REQUEST theo
    `request_budget` (Architecture.md 6.20.7/6.20.8) — day la muc goi LLM
    thuc su se dung o buoc 2/3, KHAC voi `char_budget` (checkpoint Lop 3).

    `request_max_units` (Architecture.md §6.20.14.2 A-1/A-2, MOI): tran THU
    HAI theo SO UNIT, cat request tai bat ky dieu kien nao (ky tu HOAC so
    unit) cham truoc — can thiet vi `request_budget` do bang ky tu van ban
    THUAN (`_plain_char_len()`), nen 1 request nhieu unit ma moi unit chi la
    1 doan tag HTML ngan (vd 32 dong `<strong>1 cup starter</strong>`) van co
    the "trong ngan sach ky tu" du sinh ra rat nhieu KHOA JSON — chinh xac
    hinh dang batch da gay Bug #EPUB-B2-5.
    """
    if not units:
        return []

    lengths = [_plain_char_len(u) for u in units]
    for unit, length in zip(units, lengths, strict=True):
        if length > EPUB_UNIT_HARD_MAX_CHARS:
            raise EpubUnitTooLargeError(unit.unit_id, length)

    # Buoc 1: xac dinh ranh gioi CHUNK (checkpoint Lop 3).
    chunk_bounds: list[tuple[int, int]] = []
    start = 0
    running = 0
    prev_doc_href = units[0].doc_href
    for i, unit in enumerate(units):
        if i > 0 and unit.doc_href != prev_doc_href and running >= char_budget:
            chunk_bounds.append((start, i - 1))
            start = i
            running = 0
        running += lengths[i]
        prev_doc_href = unit.doc_href
        if running >= char_budget:
            chunk_bounds.append((start, i))
            start = i + 1
            running = 0
    if start <= len(units) - 1:
        chunk_bounds.append((start, len(units) - 1))

    # Buoc 2: trong moi chunk, gom unit lien tiep thanh REQUEST.
    plans: list[EpubChunkPlan] = []
    for idx, (unit_start, unit_end) in enumerate(chunk_bounds):
        requests: list[tuple[int, int]] = []
        req_start = unit_start
        req_running = 0
        for i in range(unit_start, unit_end + 1):
            unit_len = lengths[i]
            req_units = i - req_start  # so unit DA gom vao request dang mo
            if req_units > 0 and (
                req_running + unit_len > request_budget or req_units >= request_max_units
            ):
                requests.append((req_start, i - 1))
                req_start = i
                req_running = 0
            req_running += unit_len
        requests.append((req_start, unit_end))
        plans.append(
            EpubChunkPlan(index=idx, unit_start=unit_start, unit_end=unit_end, requests=requests)
        )

    return plans
