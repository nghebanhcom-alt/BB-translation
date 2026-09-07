"""Test Bug #7 fix buoc 7.4-c — Ca C (Architecture.md muc "Bug #7 Ca C — Quyet
dinh cuoi sau phan bien Domain Expert + ke hoach spike 7.4-a (Tech Lead,
2026-09-08)", AA4/AA5/AA7/AA9) — tach paragraph gom nhieu muc muc luc KHONG
co dot-leader "du day" (< 20 cham), TOC-1 v2.

Protocol 6 R6-02: test KHONG duoc chi assert "chay khong loi". Moi test o day
goi DUNG logic production `src.babeldoc_shim.toc_split` — cung module ma
`sitecustomize.py` dung khi patch `ParagraphFinder.process_independent_
paragraphs` trong subprocess babeldoc that (xem `_split_toc_paragraphs_in_list`)
— khong chep lai bat ky phan nao cua thuat toan quyet dinh tach/danh dau.

2 nhom test:
1. Unit test tren du lieu tong hop (synthetic `TocChar`) cho tung dieu kien
   cua AA4 (buoc 0-4), dac biet cac ca chong false-positive named trong
   AA4/AA7 (folio dung rieng, o bang so, van xuoi ket thuc bang so lieu) VA
   luat dong noi SAU KHI da sua bug continuation-line (issue non-blocking #1
   cua Reviewer, review-report.md "Review spike 7.4-a").
2. Golden-fixture test tren 8 fixture da commit
   (`tests/fixtures/babeldoc/toc_*_dump.json.gz`, sinh tu babeldoc 0.6.4 that
   qua `--debug`, KHONG phai mock tay — Protocol 5 muc 3) — assert dung bang
   oracle AA7 (31 fire / 130 cut tong, 0 fire tren 5 fixture khong phai muc
   luc trong so 8 fixture da commit) bang cach goi DUNG ham production
   `evaluate_paragraph`, dung y het cach `scripts/toc_split_spike_measure.py`
   da lam (da qua Reviewer xac nhan khong "tu cham diem gia", review-report.md).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from src.babeldoc_shim.toc_split import (
    REASON_DENY_LAYOUT,
    REASON_FEW_TAIL_LINES,
    REASON_FIRED,
    REASON_LOW_FRACTION,
    REASON_NOT_MONOTONIC,
    REASON_TOO_SHORT,
    TOC_CONT_INDENT_EM,
    TocChar,
    evaluate_paragraph,
    mark_toc_tail,
    sort_line_chars,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "babeldoc"


def _load_dump(name: str) -> dict:
    with gzip.open(_FIXTURES_DIR / name, "rt", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helper de dung tay 1 dong ky tu (TocChar) tu 1 chuoi hien thi (khong khoang
# trang — dung y het dau vao thuc te cua `mark_toc_tail`, vi `sort_line_chars`
# da loai khoang trang o buoc 1 TRUOC do), voi kha nang chen 1 khoang cach tuy
# y truoc phan duoi so (mo phong khoang trang rong do thieu dot-leader).
# ---------------------------------------------------------------------------


def _line(
    body: str,
    tail_digits: str = "",
    *,
    font_size: float = 10.0,
    char_width: float = 6.0,
    gap: float | None = None,
    start_x: float = 0.0,
) -> list[TocChar]:
    chars: list[TocChar] = []
    x = start_x
    for ch in body:
        chars.append(TocChar(x=x, x2=x + char_width, unicode=ch, font_size=font_size))
        x += char_width
    if tail_digits:
        x = (x + gap) if gap is not None else x
        for ch in tail_digits:
            chars.append(TocChar(x=x, x2=x + char_width, unicode=ch, font_size=font_size))
            x += char_width
    return chars


# ---------------------------------------------------------------------------
# sort_line_chars — buoc 1 AA4
# ---------------------------------------------------------------------------


def test_sort_line_chars_removes_whitespace_and_sorts_by_x() -> None:
    chars = [
        TocChar(x=20.0, x2=26.0, unicode="b", font_size=10.0),
        TocChar(x=8.0, x2=14.0, unicode=" ", font_size=10.0),  # dummy space, phai bi loai
        TocChar(x=0.0, x2=6.0, unicode="a", font_size=10.0),
    ]
    result = sort_line_chars(chars)
    assert [c.unicode for c in result] == ["a", "b"]


# ---------------------------------------------------------------------------
# mark_toc_tail — buoc 2 AA4, tung dieu kien 1 (6 dieu kien) + false-positive
# named cua AA4/AA7.
# ---------------------------------------------------------------------------


def test_mark_toc_tail_matches_simple_toc_line() -> None:
    # "Introduction" + khoang rong lon (thieu dot-leader) + "12"
    chars = _line("Introduction", "12", gap=10.0)  # ratio = 10/10 = 1.0 >= 0.8
    mark = mark_toc_tail(chars)
    assert mark is not None
    assert mark.n == 12
    assert mark.ratio == pytest.approx(1.0)


def test_mark_toc_tail_rejects_folio_alone_all_digits() -> None:
    """AA4 buoc 2 dieu kien 1: `k == len(sorted_chars)` — ca dong la so
    (folio dung rieng 1 minh tren trang, hoac o bang thuan so) — PHAI bi loai."""
    chars = _line("", "42")
    assert mark_toc_tail(chars) is None


def test_mark_toc_tail_rejects_table_cell_numeric() -> None:
    """O bang so kieu "4.0" — sau khi bo khoang trang (khong co trong vi du
    nay), phan than dong "4." khong chua cum >= 2 chu cai ASCII nao (dieu
    kien 2) nen bi loai, du van ket thuc bang chu so ("0")."""
    chars = _line("4.", "0", gap=0.0)
    assert mark_toc_tail(chars) is None


def test_mark_toc_tail_rejects_prose_ending_in_number() -> None:
    """Van xuoi ket thuc bang so lieu (vd "...in the year 2024") co khoang
    cach TRUOC so chi bang 1 khoang trang thuong (~0.3 em) — RAT xa nguong
    TOC_GAP_RATIO=0.8 — phai bi loai o dieu kien 5/6, khong duoc coi la duoi
    muc luc."""
    chars = _line("in the year", "2024", gap=3.0)  # ratio = 3/10 = 0.3 < 0.8
    assert mark_toc_tail(chars) is None


def test_mark_toc_tail_rejects_out_of_range_page_number() -> None:
    # n=0 (khong hop le) va n co 5 chu so (> TOC_MAX_DIGITS=4).
    assert mark_toc_tail(_line("Chapter", "0", gap=10.0)) is None
    assert mark_toc_tail(_line("Chapter", "12345", gap=10.0)) is None


def test_mark_toc_tail_rejects_zero_font_size() -> None:
    chars = _line("Chapter", "12", gap=10.0, font_size=0.0)
    assert mark_toc_tail(chars) is None


def test_mark_toc_tail_rejects_short_line() -> None:
    assert mark_toc_tail([TocChar(x=0.0, x2=6.0, unicode="1", font_size=10.0)]) is None
    assert mark_toc_tail([]) is None


def test_mark_toc_tail_uses_ascii_digits_not_str_isdigit() -> None:
    """Z7-c: '²'.isdigit() la True nhung KHONG phai ASCII digit — dong ket
    thuc bang sieu chi so khong duoc coi la so trang."""
    chars = _line("Area", "m²", gap=10.0)
    assert mark_toc_tail(chars) is None


# ---------------------------------------------------------------------------
# evaluate_paragraph — buoc 0, 3, 4 AA4 (cong paragraph + luat dong noi).
# ---------------------------------------------------------------------------


def _toc_paragraph_lines(pages: list[int], *, gap: float = 10.0) -> list[list[TocChar] | None]:
    # Cot y KHONG nhung chu so vao "body" (vd "Chapter 1") — chu so cuoi cua
    # body se bi thuat toan gop chung voi day so trang o `tail_digits` (ca
    # hai deu la ky tu ASCII digit lien tiep tu cuoi dong), lam sai lech ca
    # `gap`/`ratio` lan gia tri `n` do duoc. Dung mot nhan chu ("Chapter")
    # khong doi cho moi dong.
    return [_line("Chapter", str(page), gap=gap) for page in pages]


def test_evaluate_paragraph_denies_layout_label() -> None:
    lines = _toc_paragraph_lines([1, 2, 3])
    result = evaluate_paragraph("table", lines)
    assert result.fired is False
    assert result.reason == REASON_DENY_LAYOUT
    # Deny-list phai chuan hoa lower/strip.
    assert evaluate_paragraph(" Table \n", lines).reason == REASON_DENY_LAYOUT
    assert evaluate_paragraph("ABANDON", lines).reason == REASON_DENY_LAYOUT


def test_evaluate_paragraph_too_short() -> None:
    result = evaluate_paragraph("plain text", _toc_paragraph_lines([1]))
    assert result.fired is False
    assert result.reason == REASON_TOO_SHORT


def test_evaluate_paragraph_few_tail_lines() -> None:
    # Chi 1 dong khop dinh dang muc luc trong so 3 dong -> m=1 < TOC_MIN_TAIL_LINES=2.
    lines = [_line("Chapter", "11", gap=10.0), _line("just prose here"), _line("more prose")]
    result = evaluate_paragraph("plain text", lines)
    assert result.fired is False
    assert result.reason == REASON_FEW_TAIL_LINES
    assert result.tail_marks == 1


def test_evaluate_paragraph_low_fraction() -> None:
    # 2 dong khop / 6 dong tong = 0.33 < TOC_MIN_TAIL_FRACTION=0.6.
    lines = [
        _line("Chapter", "11", gap=10.0),
        _line("Chapter", "22", gap=10.0),
        _line("prose a"),
        _line("prose b"),
        _line("prose c"),
        _line("prose d"),
    ]
    result = evaluate_paragraph("plain text", lines)
    assert result.fired is False
    assert result.reason == REASON_LOW_FRACTION
    assert result.tail_marks == 2


def test_evaluate_paragraph_not_monotonic() -> None:
    # Trang giam dan (3 -> 1) vi pham Z4 (dieu kien cung, khong phai heuristic).
    lines = _toc_paragraph_lines([3, 1, 2])
    result = evaluate_paragraph("plain text", lines)
    assert result.fired is False
    assert result.reason == REASON_NOT_MONOTONIC


def test_evaluate_paragraph_fires_simple_toc() -> None:
    lines = _toc_paragraph_lines([1, 2, 3])
    result = evaluate_paragraph("plain text", lines)
    assert result.fired is True
    assert result.reason == REASON_FIRED
    assert result.tail_marks == 3
    # 3 dong deu tach rieng: cat sau dong 0 va dong 1, dong cuoi (j==L-1)
    # khong tao diem tach (AA4 buoc 4 "bo neu j == L-1").
    assert result.cut_after == (0, 1)


def test_evaluate_paragraph_allows_equal_page_numbers() -> None:
    # `TOC_REQUIRE_NON_DECREASING` cho phep BANG nhau (khong chi tang chat).
    lines = _toc_paragraph_lines([5, 5, 6])
    result = evaluate_paragraph("plain text", lines)
    assert result.fired is True


# ---------------------------------------------------------------------------
# Luat dong noi (AA4 buoc 4, Z7-a) — ca extended=True/False + FIX bug
# continuation-line cho composition KHONG PHAI pdf_line (issue non-blocking
# #1, review-report.md "Review spike 7.4-a"): composition do KHONG BAO GIO
# duoc danh dau va PHAI dinh vao group LIEN TRUOC, giong het 7.2 — TRUOC ban
# fix, code cu dat diem cat NGAY SAU dong danh dau (j=i khong doi), day
# composition khong-phai-dong do sang group SAU thay vi group truoc.
# ---------------------------------------------------------------------------


def test_continuation_line_merges_when_indent_meets_threshold() -> None:
    mark_line = _line("Chapter", "11", gap=10.0, start_x=0.0)
    # indent_delta = 10.0 - 0.0 = 10.0 = 1.0 * font_size(10.0) -> >= nguong -> gop.
    cont_line = _line("continued heading", start_x=10.0)
    tail_line = _line("Chapter", "22", gap=10.0, start_x=0.0)
    result = evaluate_paragraph("plain text", [mark_line, cont_line, tail_line])
    assert result.fired is True
    assert len(result.continuation_boundaries) == 1
    boundary = result.continuation_boundaries[0]
    assert boundary.marked_index == 0
    assert boundary.next_index == 1
    assert boundary.extended is True
    # Diem cat nam SAU ca dong noi (index 1), khong phai ngay sau dong danh
    # dau (index 0) — dong noi thuoc group cua dong danh dau.
    assert result.cut_after == (1,)


def test_continuation_line_not_merged_below_indent_threshold() -> None:
    mark_line = _line("Chapter", "11", gap=10.0, start_x=0.0)
    # indent_delta = 5.0 < 1.0 * 10.0 -> KHONG gop.
    small_indent_line = _line("stray line", start_x=5.0)
    tail_line = _line("Chapter", "22", gap=10.0, start_x=0.0)
    result = evaluate_paragraph("plain text", [mark_line, small_indent_line, tail_line])
    assert result.fired is True
    boundary = result.continuation_boundaries[0]
    assert boundary.extended is False
    assert boundary.indent_delta == pytest.approx(5.0)
    # Khong gop -> diem cat nam NGAY SAU dong danh dau (index 0), dong
    # "stray line" roi vao group SAU (cung group voi Chapter 2).
    assert result.cut_after == (0,)


def test_continuation_line_uses_configured_em_threshold() -> None:
    """Xac nhan hang so `TOC_CONT_INDENT_EM` (khong hardcode gia tri khac
    trong test) dung dung nguong 1.0 em nhu AA5 da chot."""
    assert TOC_CONT_INDENT_EM == 1.0


def test_non_pdf_line_composition_right_after_marked_line_sticks_to_previous_group() -> None:
    """FIX cho issue non-blocking #1 (Reviewer, review spike 7.4-a): 1
    composition KHONG PHAI `pdf_line` (vd `pdf_formula`, bieu dien bang
    `None` trong `line_chars` — dung quy uoc cua `numbered_list_split`)
    dung NGAY SAU 1 dong danh dau khong bao gio duoc danh dau VA phai dinh
    vao group LIEN TRUOC (AA4 buoc 4) — KHONG phai group sau diem cat nhu
    hanh vi SAI truoc khi sua."""
    mark_line = _line("Chapter", "11", gap=10.0)
    tail_line = _line("Chapter", "22", gap=10.0)
    result = evaluate_paragraph("plain text", [mark_line, None, tail_line])
    assert result.fired is True
    assert result.tail_marks == 2
    # Diem cat PHAI nam SAU composition formula (index 1) de no dinh vao
    # group cua dong danh dau (index 0), KHONG phai cat ngay sau index 0
    # (se day formula sang group cua Chapter 2 — hanh vi SAI truoc khi sua).
    assert result.cut_after == (1,)
    # Khong co ContinuationBoundary nao duoc ghi cho composition non-line
    # (khong co font_size/x de do "thut dau dong" cho no).
    assert result.continuation_boundaries == ()


def test_multiple_non_pdf_line_compositions_all_stick_to_previous_group() -> None:
    """Nhieu composition khong-phai-dong lien tiep (vd 2 formula lien nhau)
    deu phai dinh vao group truoc, khong chi composition dau tien. Dung 3
    dong danh dau (thay vi 2) de m/L = 3/5 = 0.6 vua du nguong
    TOC_MIN_TAIL_FRACTION — 2 dong danh dau se cho 2/4 = 0.5 < 0.6 va bi
    chan som o buoc 3, khong toi duoc buoc 4 dang can test."""
    mark_line1 = _line("Chapter", "11", gap=10.0)
    mark_line2 = _line("Chapter", "22", gap=10.0)
    mark_line3 = _line("Chapter", "33", gap=10.0)
    result = evaluate_paragraph("plain text", [mark_line1, None, None, mark_line2, mark_line3])
    assert result.fired is True
    assert result.tail_marks == 3
    # 2 formula (index 1,2) dinh vao group cua mark_line1 -> cat sau index 2.
    # mark_line2 (index 3) tach rieng -> cat sau index 3. mark_line3 (index 4,
    # cuoi paragraph) khong tao diem tach (j == L-1).
    assert result.cut_after == (2, 3)


def test_non_pdf_line_composition_at_paragraph_end_produces_no_cut() -> None:
    """Formula dung o CUOI paragraph (sau dong danh dau cuoi cung) khong tao
    diem tach nao (AA4 buoc 4 "bo neu j == L-1") — khong crash, khong tao
    group rong."""
    mark_line1 = _line("Chapter", "11", gap=10.0)
    mark_line2 = _line("Chapter", "22", gap=10.0)
    result = evaluate_paragraph("plain text", [mark_line1, mark_line2, None])
    assert result.fired is True
    # Diem cat sau dong danh dau dau tien (index 0); dong danh dau thu 2
    # (index 1) mo rong toi formula (index 2, dinh vao group truoc no) nen
    # j chay toi index 2 == L-1 -> khong tao diem tach cho no.
    assert result.cut_after == (0,)


# ---------------------------------------------------------------------------
# Golden-fixture test — 8 fixture da commit (AA7/AA9), goi DUNG ham
# production tren du lieu that (KHONG mock tay — Protocol 5 muc 3).
# ---------------------------------------------------------------------------


def _char_to_tocchar(char: dict) -> TocChar:
    box = char["visual_bbox"]["box"]
    return TocChar(
        x=box["x"],
        x2=box["x2"],
        unicode=char["char_unicode"] or "",
        font_size=(char.get("pdf_style") or {}).get("font_size") or 0.0,
    )


def _paragraph_line_chars(paragraph: dict) -> list[list[TocChar] | None]:
    out: list[list[TocChar] | None] = []
    for comp in paragraph["pdf_paragraph_composition"]:
        line = comp.get("pdf_line")
        if line is None:
            out.append(None)
            continue
        out.append([_char_to_tocchar(c) for c in line["pdf_character"]])
    return out


def _evaluate_dump(dump: dict) -> tuple[int, int]:
    """Tra ve (tong fire, tong cut) tren toan bo dump — goi DUNG
    `evaluate_paragraph` production, khong tu viet lai dieu kien nao."""
    fire = 0
    cuts = 0
    for page in dump["page"]:
        for paragraph in page["pdf_paragraph"]:
            result = evaluate_paragraph(
                paragraph.get("layout_label"), _paragraph_line_chars(paragraph)
            )
            if result.fired:
                fire += 1
                cuts += len(result.cut_after)
    return fire, cuts


# (ten fixture, file, fire ky vong, cut ky vong) — dung y het bang oracle AA7
# cho 8 fixture DA COMMIT cua spike 7.4-a (da qua Reviewer tu chay lai va
# khop tuyet doi, review-report.md "Doi chieu so lieu").
_GOLDEN_FIXTURES = [
    ("figoni_p7_toc", "toc_figoni_contents_p7_dump.json.gz", 8, 28),
    ("figoni_p8_toc", "toc_figoni_contents_p8_dump.json.gz", 12, 38),
    ("lcb_toc", "toc_lcb_contents_p6_p7_dump.json.gz", 11, 64),
    ("friberg_toc", "toc_friberg_contents_dump.json.gz", 0, 0),
    ("lcb_index", "toc_lcb_index_dump.json.gz", 0, 0),
    ("figoni_p25_recipe", "toc_figoni_p25_recipe_dump.json.gz", 0, 0),
    ("figoni_p45_recipe", "toc_figoni_p45_recipe_dump.json.gz", 0, 0),
    ("figoni_p7_tables", "toc_figoni_tables_dump.json.gz", 0, 0),
]


@pytest.mark.parametrize(
    ("name", "filename", "expected_fire", "expected_cuts"),
    _GOLDEN_FIXTURES,
    ids=[row[0] for row in _GOLDEN_FIXTURES],
)
def test_golden_fixture_matches_oracle_aa7(
    name: str, filename: str, expected_fire: int, expected_cuts: int
) -> None:
    dump = _load_dump(filename)
    fire, cuts = _evaluate_dump(dump)
    assert (fire, cuts) == (expected_fire, expected_cuts), (
        f"{name}: fire/cuts = {fire}/{cuts}, ky vong {expected_fire}/{expected_cuts} (oracle AA7)"
    )


def test_golden_fixtures_total_matches_oracle_aa7() -> None:
    total_fire = 0
    total_cuts = 0
    for _name, filename, _ef, _ec in _GOLDEN_FIXTURES:
        fire, cuts = _evaluate_dump(_load_dump(filename))
        total_fire += fire
        total_cuts += cuts
    assert (total_fire, total_cuts) == (31, 130)


def test_golden_fixtures_zero_false_positive_on_non_toc_pages() -> None:
    """AA9 dieu kien 3: FP = 0 TUYET DOI tren cac fixture KHONG phai muc luc
    — bat ky kich hoat nao o day la FAIL, khong co nguong "chap nhan duoc"."""
    non_toc_names = {
        "friberg_toc",
        "lcb_index",
        "figoni_p25_recipe",
        "figoni_p45_recipe",
        "figoni_p7_tables",
    }
    for name, filename, _ef, _ec in _GOLDEN_FIXTURES:
        if name not in non_toc_names:
            continue
        fire, _cuts = _evaluate_dump(_load_dump(filename))
        assert fire == 0, f"{name}: FP thuc su (fire={fire}), vi pham AA9 dieu kien 3"


def test_golden_fixture_lcb_toc_all_fires_are_plain_text_layout() -> None:
    """AA1: 31/31 paragraph kich hoat tren toan bo 4 trang muc luc deu co
    `layout_label == 'plain text'` — bang chung recall cho deny-list (AA3)
    khong mat diem nao. Kiem tra rieng tren `lcb_toc` (fixture co
    `fired_inside_table_box` > 0, truong hop de vo tinh mat neu deny-list
    sai)."""
    dump = _load_dump("toc_lcb_contents_p6_p7_dump.json.gz")
    for page in dump["page"]:
        for paragraph in page["pdf_paragraph"]:
            result = evaluate_paragraph(
                paragraph.get("layout_label"), _paragraph_line_chars(paragraph)
            )
            if result.fired:
                label = (paragraph.get("layout_label") or "").strip().lower()
                assert label == "plain text", f"paragraph kich hoat co layout_label={label!r}"
