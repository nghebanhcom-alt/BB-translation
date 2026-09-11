from itertools import pairwise

import pytest

from src.core.chunking import (
    EPUB_CHUNK_CHAR_BUDGET,
    EPUB_FALLBACK_MAX_RATIO_CHUNK,
    EPUB_FALLBACK_MAX_RATIO_JOB,
    EPUB_MAX_EXTRA_REQUESTS_PER_SLICE,
    EPUB_MAX_SINGLE_ID_RETRIES,
    EPUB_REQUEST_CHAR_BUDGET,
    EPUB_REQUEST_MAX_UNITS,
    EPUB_UNIT_HARD_MAX_CHARS,
    EpubUnitTooLargeError,
    calculate_chunks,
    plan_chunks,
    plan_epub_chunks,
    surviving_page_range,
)
from src.services.epub_document import EpubUnit


def test_plan_chunks_small_file_single_chunk() -> None:
    chunks = plan_chunks(total_pages=30, file_size_bytes=5 * 1024 * 1024)

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 30
    assert chunks[0].overlap_start is None
    assert chunks[0].overlap_end is None


def test_plan_chunks_large_file_chunks_with_overlap() -> None:
    chunks = plan_chunks(total_pages=120, file_size_bytes=5 * 1024 * 1024)

    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 40), (39, 80), (79, 120)]
    assert chunks[0].overlap_start is None
    assert chunks[0].overlap_end is None
    assert chunks[1].overlap_start == 39
    assert chunks[1].overlap_end == 40
    assert chunks[2].overlap_start == 79
    assert chunks[2].overlap_end == 80


def test_plan_chunks_small_page_count_but_large_size_still_chunks() -> None:
    chunks = plan_chunks(total_pages=45, file_size_bytes=25 * 1024 * 1024)

    assert len(chunks) > 1
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 45


def test_calculate_chunks_covers_every_page_without_gaps() -> None:
    chunks = calculate_chunks(total_pages=120, chunk_size=40, overlap=2)

    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 120
    for prev, nxt in pairwise(chunks):
        assert nxt.page_start <= prev.page_end + 1


def test_calculate_chunks_single_page() -> None:
    chunks = calculate_chunks(total_pages=1, chunk_size=40, overlap=2)
    assert chunks == [calculate_chunks(1)[0]]
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1


# ---------------------------------------------------------------------------
# EPUB chunking (Architecture.md 6.20.7/6.20.12) — thuat toan thuan tuy, dung
# EpubUnit gia lap (khong can file EPUB that o day; file that duoc dung o
# tests/test_epub_document.py de kiem con so tren du lieu thuc).
# ---------------------------------------------------------------------------


def _units(doc_href: str, lengths: list[int], *, tag: str = "p") -> list[EpubUnit]:
    return [
        EpubUnit(unit_id=f"{doc_href}#{i}", doc_href=doc_href, tag=tag, ordinal=i, text="a" * n)
        for i, n in enumerate(lengths)
    ]


def test_plan_epub_chunks_empty_returns_empty() -> None:
    assert plan_epub_chunks([]) == []


def test_plan_epub_chunks_small_book_single_chunk_single_request() -> None:
    units = _units("doc.html", [100, 200, 300])
    plans = plan_epub_chunks(units)

    assert len(plans) == 1
    assert plans[0].unit_start == 0
    assert plans[0].unit_end == 2
    assert plans[0].requests == [(0, 2)]


def test_plan_epub_chunks_cuts_inside_one_oversized_document() -> None:
    """Mo phong dung ca Sourdough that: 1 document chiem gan het sach, phai
    cat BEN TRONG no theo ranh gioi unit khi vuot char_budget."""
    units = _units("chapter.html", [3_000] * 7)  # 21_000 ky tu, budget 8_000

    plans = plan_epub_chunks(units, char_budget=8_000)

    assert [(p.unit_start, p.unit_end) for p in plans] == [(0, 2), (3, 5), (6, 6)]
    # Moi chunk lien tuc, khong chong lan, phu het toan bo unit.
    assert plans[0].unit_start == 0
    assert plans[-1].unit_end == len(units) - 1
    for prev, cur in pairwise(plans):
        assert cur.unit_start == prev.unit_end + 1


def test_plan_epub_chunks_prefers_document_boundary_when_budget_already_met() -> None:
    """Cat UU TIEN tai ranh gioi tai lieu: khi running da >= budget DUNG LUC
    chuyen sang tai lieu moi, khong duoc keo 1 phan nho cua tai lieu moi vao
    chunk cu."""
    doc_a = _units("a.html", [8_500])  # tu no da vuot budget
    doc_b = _units("b.html", [100, 100])
    units = doc_a + doc_b

    plans = plan_epub_chunks(units, char_budget=8_000)

    # Chunk dau tien dung lai DUNG tai ranh gioi tai lieu (unit 0, tuc a.html),
    # khong ngoam them unit cua b.html du b.html con thua ngan sach.
    assert plans[0].unit_start == 0
    assert plans[0].unit_end == 0
    assert plans[1].unit_start == 1


def test_plan_epub_chunks_merges_small_documents_up_to_budget() -> None:
    """KHONG bi rang buoc boi ranh gioi tai lieu: nhieu tai lieu nho gop
    chung 1 chunk mien con trong ngan sach."""
    units = (
        _units("small1.html", [100]) + _units("small2.html", [100]) + _units("small3.html", [100])
    )

    plans = plan_epub_chunks(units, char_budget=8_000)

    assert len(plans) == 1
    assert plans[0].unit_start == 0
    assert plans[0].unit_end == 2


def test_plan_epub_chunks_no_gaps_no_overlap_covers_all_units() -> None:
    units = _units("chapter.html", [500] * 40)  # 20_000 ky tu

    plans = plan_epub_chunks(units, char_budget=8_000)

    covered = []
    for plan in plans:
        covered.extend(range(plan.unit_start, plan.unit_end + 1))
    assert covered == list(range(len(units)))


def test_plan_epub_chunks_requests_never_split_a_single_unit_across_two_requests() -> None:
    units = _units("chapter.html", [1_200] * 20)  # request_budget mac dinh 3_000

    plans = plan_epub_chunks(units)

    for plan in plans:
        indices_in_requests = [i for r in plan.requests for i in range(r[0], r[1] + 1)]
        assert indices_in_requests == list(range(plan.unit_start, plan.unit_end + 1))


def test_plan_epub_chunks_request_budget_grouping() -> None:
    """Truyen `request_budget=3_000` tuong minh (KHONG con la default sau
    Architecture.md §6.20.14.2 A-1 — default gio la 1.100) de kiem RIENG
    logic cat theo NGAN SACH KY TU, doc lap voi tran so unit moi (A-1/A-2,
    xem `test_plan_epub_chunks_request_max_units_cuts_before_char_budget`)."""
    units = _units("chapter.html", [1_000, 1_000, 1_500, 1_000])

    plans = plan_epub_chunks(units, char_budget=100_000, request_budget=3_000)

    assert len(plans) == 1
    # 1000+1000=2000 (<=3000), +1500 se la 3500>3000 -> cat; unit con lai
    # (1500, 1000) gop tiep vi 1500+1000=2500<=3000.
    assert plans[0].requests == [(0, 1), (2, 3)]


def test_plan_epub_chunks_request_max_units_cuts_before_char_budget() -> None:
    """Architecture.md §6.20.14.2 A-1/A-2 (MOI) — tai hien dung ca 32 unit
    Bug #EPUB-B2-5: nhieu tag HTML NGAN (it ky tu thuan) van phai bi cat theo
    SO UNIT du con rat xa ngan sach ky tu, vi so KHOA JSON moi la thu model
    phai giu dung cu phap."""
    units = _units("chapter.html", [10] * 32)  # 320 ky tu tong, RAT xa budget

    plans = plan_epub_chunks(
        units, char_budget=100_000, request_budget=100_000, request_max_units=6
    )

    assert len(plans) == 1
    for r_start, r_end in plans[0].requests:
        assert r_end - r_start + 1 <= 6
    # Phu het 32 unit, khong trung, khong thieu.
    covered = [i for r in plans[0].requests for i in range(r[0], r[1] + 1)]
    assert covered == list(range(32))


def test_plan_epub_chunks_request_max_units_default_caps_at_six() -> None:
    """Default `request_max_units` (khong truyen tuong minh) phai la
    `EPUB_REQUEST_MAX_UNITS` (=6) — dung gia tri MOI cua §6.20.14.2 A-1."""
    units = _units("chapter.html", [10] * 32)

    plans = plan_epub_chunks(units, char_budget=100_000, request_budget=100_000)

    for r_start, r_end in plans[0].requests:
        assert r_end - r_start + 1 <= EPUB_REQUEST_MAX_UNITS


def test_plan_epub_chunks_oversized_unit_sent_alone_in_its_own_request() -> None:
    units = _units("chapter.html", [500, 4_000, 500])  # unit giua > request_budget (3_000)

    plans = plan_epub_chunks(units, char_budget=100_000)

    assert len(plans) == 1
    requests = plans[0].requests
    assert (1, 1) in requests  # unit qua kho duoc gui MOT MINH
    for r_start, r_end in requests:
        if r_start == r_end == 1:
            continue
        assert r_end < 1 or r_start > 1  # khong gop chung voi unit qua kho


def test_plan_epub_chunks_raises_for_unit_over_hard_max() -> None:
    units = _units("chapter.html", [EPUB_UNIT_HARD_MAX_CHARS + 1])

    with pytest.raises(EpubUnitTooLargeError) as exc_info:
        plan_epub_chunks(units)
    assert exc_info.value.unit_id == "chapter.html#0"
    assert exc_info.value.char_len == EPUB_UNIT_HARD_MAX_CHARS + 1


def test_epub_budget_constants_match_architecture_values() -> None:
    """Architecture.md §6.20.14.2/§6.20.14.4/§6.20.14.6 (2026-09-10, sau khi
    cham gioi han Protocol 3) — khoa lai bang test de doi gia tri phai la 1
    quyet dinh co chu dich, khong phai vo tinh. `EPUB_REQUEST_CHAR_BUDGET` HA
    tu 3.000 xuong 1.100 (A-1); `EPUB_REQUEST_MAX_UNITS` MOI = 6 (A-1);
    `EPUB_MAX_SINGLE_ID_RETRIES` HA tu 5 xuong 2, `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE`
    HA tu 6 xuong 3 (A-3); `EPUB_FALLBACK_MAX_RATIO_CHUNK`/`_JOB` MOI (C-2)."""
    assert EPUB_CHUNK_CHAR_BUDGET == 8_000
    assert EPUB_REQUEST_CHAR_BUDGET == 1_100
    assert EPUB_REQUEST_MAX_UNITS == 6
    assert EPUB_UNIT_HARD_MAX_CHARS == 10_000
    assert EPUB_MAX_SINGLE_ID_RETRIES == 2
    assert EPUB_MAX_EXTRA_REQUESTS_PER_SLICE == 3
    assert EPUB_FALLBACK_MAX_RATIO_CHUNK == 0.20
    assert EPUB_FALLBACK_MAX_RATIO_JOB == 0.05


# --- BL-04 (Architecture.md 6.22.5.1) — surviving_page_range() -------------
#
# Gate test #5 (6.22.9): dai song sot cua toan bo 1 chunk plan 418 trang
# phai ROI NHAU va HOP LAI dung [1, 418], va gia tri `start` phai bang dung
# `actual_start` ma `merge_chunk_pdfs()` tinh ra — dam bao bang REFACTOR
# (`src/postprocess/chunk_merge.py` goi CHINH ham nay, khong chep lai cong
# thuc), khong phai bang cach test tinh lai cong thuc mot lan nua.


def test_surviving_range_raises_for_epub_chunk_without_page_range() -> None:
    """X2 (2026-09-11) — `page_start`/`page_end` la `None` cho chunk EPUB
    (6.20.7). Phai raise `ValueError` ro rang, KHONG de `None + 1` no
    `TypeError` mat dau vet o mot cho khac."""

    class _EpubLikeChunk:
        page_start = None
        page_end = None
        overlap_start = None
        overlap_end = None

    with pytest.raises(ValueError, match="page_start"):
        surviving_page_range(_EpubLikeChunk(), is_first_in_merge=True)


def test_surviving_range_first_chunk_starts_at_page_start() -> None:
    plan = calculate_chunks(total_pages=418, chunk_size=40, overlap=2)[0]
    assert plan.page_start == 1
    start, end = surviving_page_range(plan, is_first_in_merge=True)
    assert (start, end) == (1, 40)


def test_surviving_range_subsequent_chunk_starts_after_overlap_end() -> None:
    plan = calculate_chunks(total_pages=418, chunk_size=40, overlap=2)[1]
    assert (plan.page_start, plan.page_end, plan.overlap_start, plan.overlap_end) == (
        39,
        80,
        39,
        40,
    )
    start, end = surviving_page_range(plan, is_first_in_merge=False)
    assert (start, end) == (41, 80)


def test_surviving_range_covers_whole_418_page_document_disjointly() -> None:
    """Gate test #5 — dai song sot cua TOAN BO chunk plan phai ROI NHAU va
    HOP LAI dung [1, total_pages] (Architecture.md 6.22.5.1 "Vi sao loai ma
    KHONG de lai lo hong quan sat")."""
    plans = calculate_chunks(total_pages=418, chunk_size=40, overlap=2)

    ranges = [surviving_page_range(plan, is_first_in_merge=(plan.index == 0)) for plan in plans]

    # Roi nhau + lien tuc: end cua dai truoc + 1 == start cua dai sau.
    for (_, prev_end), (next_start, _) in pairwise(ranges):
        assert next_start == prev_end + 1

    assert ranges[0][0] == 1
    assert ranges[-1][1] == 418
    covered = sum(end - start + 1 for start, end in ranges)
    assert covered == 418


def test_surviving_range_matches_merge_chunk_pdfs_actual_start() -> None:
    """`merge_chunk_pdfs()` (`src/postprocess/chunk_merge.py`) da duoc
    refactor de goi CHINH `surviving_page_range()` thay vi tu tinh
    `actual_start` — nen gia tri `start` tra ve o day CHINH LA gia tri
    `merge_chunk_pdfs()` se dung, khong phai mot cong thuc chep lai. Kiem tra
    tuong duong nay bang cach doc source (khong the "assert code goi ham
    nao" tu test) — xem `src/postprocess/chunk_merge.py` dong goi
    `surviving_page_range(chunk, is_first_in_merge=(position == 0))`.
    """
    import inspect

    from src.postprocess import chunk_merge

    source = inspect.getsource(chunk_merge.merge_chunk_pdfs)
    assert "surviving_page_range(chunk, is_first_in_merge=(position == 0))" in source
    assert "actual_start = chunk.page_start" not in source  # cong thuc CU da bi thay the
