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
#: Z3): ~900 token noi dung + envelope + ~450 token system prompt, xa
#: `max_tokens=8192` mac dinh cua ca 4 provider (Architecture.md 6.20.7 Z3).
EPUB_REQUEST_CHAR_BUDGET = 3_000
#: Y4 (Architecture.md 6.20.12): 1 unit vuot nguong nay -> job phai fail ro
#: rang (khong cat cau o v1) — vuot ~13.000 ky tu EN lam output LLM bi cut,
#: JSON hong, retry le van cut. Chua cham du lieu that (max unit cua file mau
#: chi 989 ky tu), xem Architecture.md 6.20.11 muc 7.
EPUB_UNIT_HARD_MAX_CHARS = 10_000

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
            if req_running > 0 and req_running + unit_len > request_budget:
                requests.append((req_start, i - 1))
                req_start = i
                req_running = 0
            req_running += unit_len
        requests.append((req_start, unit_end))
        plans.append(
            EpubChunkPlan(index=idx, unit_start=unit_start, unit_end=unit_end, requests=requests)
        )

    return plans
