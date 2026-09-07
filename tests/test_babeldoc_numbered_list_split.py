"""Test Bug #7 fix buoc 7.2 — Ca A (Architecture.md "Bug #7/#8 — Final Decision
sau phản biện Domain Expert (2026-09-07)", X5 D7-3 buoc "7.2") — tach paragraph
tai cac dong mo dau bang marker numbered-list tang dan dung 1 don vi (vd "8."
roi "9."), CHI ap dung sau khi tang dong (7.1) da sua xong.

Protocol 6 R6-02: test KHONG duoc chi assert "chay khong loi". Test nay goi
dung logic production (`src.babeldoc_shim.numbered_list_split`) — cung ham ma
`sitecustomize.py` dung khi patch `ParagraphFinder.process` trong subprocess
babeldoc thuc — tren 2 golden fixture ghi lai TU babeldoc 0.6.4 thuc chay
`--debug` (PYTHONPATH shim 7.1 dang bat, TRUOC khi co code 7.2), roi assert
SO PARAGRAPH KET QUA VA NOI DUNG TUNG PARAGRAPH cu the — khong suy dien.

Golden fixture nguon:
- `paragraph_finder_numbered_list_post71_dump.json.gz`: babeldoc 0.6.4 thuc
  tren `page14_numbered_list_source.pdf` (danh sach 35 muc "EQUIPMENT AND
  SMALLWARES"), co flag production `--split-short-lines
  --short-line-split-factor 0.8`. Xac nhan song (spike): 4/35 muc van con
  gom chung tung cap (11+12, 23+24+"1½ quart", 31+32, 33+34) SAU KHI 7.1 da
  chay — day chinh la Ca A residual can 7.2 xu ly.
- `paragraph_finder_p74_77_post71_dump.json.gz`: babeldoc 0.6.4 thuc tren 4
  trang p74-77 cua "How baking works" (Figoni), cung flag production. Trang
  "QUESTIONS FOR REVIEW" (muc 1-17) con 1 paragraph gom CHUNG 8 muc lien tiep
  (8..15) SAU KHI 7.1 da chay.

KHONG viet mock tay theo gia dinh (Protocol 5 muc 3) — text oracle duoi day
la COPY NGUYEN tu du lieu doc ra tu chinh 2 fixture nay (da doi chieu bang
tay truoc khi viet test).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from src.babeldoc_shim.numbered_list_split import (
    extract_leading_marker,
    find_numbered_list_split_index,
    split_paragraph_lines,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "babeldoc"


def _load_dump(name: str) -> dict:
    with gzip.open(_FIXTURES_DIR / name, "rt", encoding="utf-8") as f:
        return json.load(f)


def _paragraph_line_texts(paragraph: dict) -> list[str | None]:
    """Sao y dung logic `sitecustomize.py::_split_numbered_list_paragraphs_on_page`:
    sort ky tu theo `visual_bbox.box.x` (X4-4 — cac loi goi sort cua chinh
    babeldoc deu bi comment nen thu tu ky tu tho KHONG duoc dam bao), ghep
    thanh text; composition khong phai `pdf_line` (vd `pdf_formula`) -> None.
    """
    texts: list[str | None] = []
    for comp in paragraph["pdf_paragraph_composition"]:
        line = comp.get("pdf_line")
        if line is None:
            texts.append(None)
            continue
        chars = sorted(line["pdf_character"], key=lambda c: c["visual_bbox"]["box"]["x"])
        texts.append("".join(c["char_unicode"] for c in chars))
    return texts


def _find_paragraph_starting_with(dump: dict, prefix: str) -> list[str | None]:
    for page in dump["page"]:
        for paragraph in page["pdf_paragraph"]:
            texts = _paragraph_line_texts(paragraph)
            if texts and texts[0] is not None and texts[0].startswith(prefix):
                return texts
    raise AssertionError(f"khong tim thay paragraph nao bat dau bang {prefix!r}")


# ---------------------------------------------------------------------------
# Unit test cho extract_leading_marker — cac ca chong false-positive ma
# Architecture.md X5 D7-3 yeu cau ro ("phai loai duoc false-positive kieu
# '2 cups' trong cong thuc").
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.      Explain what is meant…", 1),
        ("12.    Foo bar", 12),
        ("1)  Foo bar", 1),
        ("2 cups flour", None),  # thieu dau `.`/`)` ngay sau chu so
        ("2.5 cups flour", None),  # khong co khoang trang ngay sau `.`
        ("1½ quart", None),  # ky tu sau chu so khong phai `.`/`)`
        ("2- and 4-quart sizes", None),
        ("", None),
        (None, None),
        ("   ", None),
        ("1.", None),  # khong co noi dung sau marker
    ],
)
def test_extract_leading_marker(text: str | None, expected: int | None) -> None:
    assert extract_leading_marker(text) == expected


# ---------------------------------------------------------------------------
# Unit test cho find_numbered_list_split_index — logic "marker neo + 1"
# ---------------------------------------------------------------------------


def test_find_split_index_no_anchor_marker_returns_none() -> None:
    assert find_numbered_list_split_index(["Just prose.", "2. looks like item"]) is None


def test_find_split_index_simple_pair() -> None:
    assert find_numbered_list_split_index(["1. a", "2. b"]) == 1


def test_find_split_index_skips_continuation_line() -> None:
    assert find_numbered_list_split_index(["1. a", "continuation", "2. b"]) == 2


def test_find_split_index_ignores_non_consecutive_marker() -> None:
    # "5." khong bang anchor(1)+1=2 -> khong duoc coi la diem tach; tiep tuc
    # quet toi "2." moi la diem tach dung.
    assert find_numbered_list_split_index(["1. a", "5. unrelated", "2. b"]) == 2


def test_find_split_index_recipe_quantity_not_confused_with_marker() -> None:
    # "2 cups flour" khong khop marker (khong co dau `.`/`)`) nen duoc coi la
    # dong tiep noi cua muc 1; diem tach dung van la truoc "2. Preheat".
    assert find_numbered_list_split_index(["1. Mix batter", "2 cups flour", "2. Preheat oven"]) == 2


def test_find_split_index_no_match_returns_none() -> None:
    assert find_numbered_list_split_index(["1. a", "still item 1", "more of item 1"]) is None


def test_find_split_index_empty_or_single_line() -> None:
    assert find_numbered_list_split_index([]) is None
    assert find_numbered_list_split_index(["1. a"]) is None


# ---------------------------------------------------------------------------
# split_paragraph_lines — cascading tren du lieu tong hop (hinh dang giong
# thuc te da quan sat, nhung KHONG phai golden fixture nen chi dung de test
# logic cascade thuan, khong dung de xac nhan hanh vi tren tai lieu thuc)
# ---------------------------------------------------------------------------


def test_split_paragraph_lines_no_split_needed() -> None:
    lines = ["Just one prose paragraph, no list markers at all."]
    assert split_paragraph_lines(lines) == [lines]


def test_split_paragraph_lines_cascades_through_long_chain() -> None:
    lines = [f"{n}. item {n}" for n in range(8, 16)]  # 8..15, 8 muc
    groups = split_paragraph_lines(lines)
    assert groups == [[line] for line in lines]


def test_split_paragraph_lines_keeps_continuation_with_its_item() -> None:
    lines = ["23. Spatulas, heat-resistant silicone", "24. Stainless steel saucepans", "1½ quart"]
    groups = split_paragraph_lines(lines)
    assert groups == [
        ["23. Spatulas, heat-resistant silicone"],
        ["24. Stainless steel saucepans", "1½ quart"],
    ]


# ---------------------------------------------------------------------------
# Golden fixture — numbered_list_source.pdf (35-muc "EQUIPMENT AND SMALLWARES")
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def numbered_list_dump() -> dict:
    return _load_dump("paragraph_finder_numbered_list_post71_dump.json.gz")


def test_golden_fixture_11_12_still_merged_pre_72(numbered_list_dump: dict) -> None:
    """Xac nhan CHINH XAC hien tuong bug con lai SAU 7.1 (input cho 7.2) —
    khong suy dien, doc thang tu golden fixture."""
    texts = _find_paragraph_starting_with(numbered_list_dump, "11.")
    assert texts == ["11.    Ovens (conventional, reel, deck, etc.)", "12.    Stovetop burners"]


def test_golden_fixture_splits_11_12(numbered_list_dump: dict) -> None:
    texts = _find_paragraph_starting_with(numbered_list_dump, "11.")
    groups = split_paragraph_lines(texts)
    assert len(groups) == 2
    assert extract_leading_marker(groups[0][0]) == 11
    assert extract_leading_marker(groups[1][0]) == 12


def test_golden_fixture_splits_23_24_keeps_quart_continuation(numbered_list_dump: dict) -> None:
    texts = _find_paragraph_starting_with(numbered_list_dump, "23.")
    assert len(texts) == 3  # xac nhan dung input: 23, 24, "1½ quart" gom 1 paragraph
    groups = split_paragraph_lines(texts)
    assert len(groups) == 2
    assert groups[0] == ["23.    Spatulas, heat-resistant silicone"]
    assert extract_leading_marker(groups[1][0]) == 24
    assert groups[1][-1] == "1½ quart"  # dong tiep noi PHAI o lai voi muc 24, khong bi mat


def test_golden_fixture_splits_31_32_and_33_34(numbered_list_dump: dict) -> None:
    for prefix in ("31.", "33."):
        texts = _find_paragraph_starting_with(numbered_list_dump, prefix)
        groups = split_paragraph_lines(texts)
        assert len(groups) == 2
        first_marker = extract_leading_marker(groups[0][0])
        assert extract_leading_marker(groups[1][0]) == first_marker + 1


def test_golden_fixture_full_page_all_35_items_become_own_group(numbered_list_dump: dict) -> None:
    """Assert tren TOAN BO trang: sau khi tach, moi paragraph ket qua co
    TOI DA 1 dong bat dau bang marker (khong con paragraph nao gom >=2 muc),
    va tong so muc marker-dau-dong dung bang 35 (R6-03 style — doc noi dung,
    khong tin flag/status)."""
    marker_starts_total = 0
    for page in numbered_list_dump["page"]:
        for paragraph in page["pdf_paragraph"]:
            texts = _paragraph_line_texts(paragraph)
            groups = split_paragraph_lines(texts)
            for group in groups:
                n_markers_in_group = sum(
                    1 for line in group if extract_leading_marker(line) is not None
                )
                assert n_markers_in_group <= 1, f"van con gom nhieu marker: {group}"
                marker_starts_total += n_markers_in_group
    assert marker_starts_total == 35


# ---------------------------------------------------------------------------
# Golden fixture — p74_77.pdf, trang "QUESTIONS FOR REVIEW" (17 muc)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def p74_77_dump() -> dict:
    return _load_dump("paragraph_finder_p74_77_post71_dump.json.gz")


def test_golden_fixture_questions_for_review_8_to_15_still_merged_pre_72(
    p74_77_dump: dict,
) -> None:
    texts = _find_paragraph_starting_with(p74_77_dump, "8.")
    markers = [extract_leading_marker(t) for t in texts]
    assert [m for m in markers if m is not None] == [8, 9, 10, 11, 12, 13, 14, 15]


def test_golden_fixture_questions_for_review_cascades_to_8_items(p74_77_dump: dict) -> None:
    texts = _find_paragraph_starting_with(p74_77_dump, "8.")
    groups = split_paragraph_lines(texts)
    assert len(groups) == 8
    assert [extract_leading_marker(g[0]) for g in groups] == [8, 9, 10, 11, 12, 13, 14, 15]
    # muc 15 co dong tiep noi ("usual?") — phai o lai dung nhom cua no, khong
    # bi mat hay bi tach rieng (copy nguyen tu golden fixture).
    assert groups[-1] == [
        "15.    How does the perception of sweetness change when food is served colder than",
        "usual?",
    ]


def test_golden_fixture_pair_4_5_keeps_continuation(p74_77_dump: dict) -> None:
    texts = _find_paragraph_starting_with(p74_77_dump, "4.")
    groups = split_paragraph_lines(texts)
    assert len(groups) == 2
    assert extract_leading_marker(groups[0][0]) == 4
    assert extract_leading_marker(groups[1][0]) == 5
    assert len(groups[1]) == 2  # muc 5 co 1 dong tiep noi, phai giu lai


def test_golden_fixture_page0_no_residual_merge_after_split(p74_77_dump: dict) -> None:
    page0 = next(p for p in p74_77_dump["page"] if p["page_number"] == 0)
    for paragraph in page0["pdf_paragraph"]:
        texts = _paragraph_line_texts(paragraph)
        for group in split_paragraph_lines(texts):
            n_markers = sum(1 for line in group if extract_leading_marker(line) is not None)
            assert n_markers <= 1
