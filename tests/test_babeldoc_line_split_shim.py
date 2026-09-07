"""Test Bug #7 fix (Architecture.md "Bug #7/#8 — Final Decision sau phản
biện Domain Expert (2026-09-07)", X5 D7-5) — loại ký tự khoảng trắng khỏi
phép đếm va chạm dùng để tìm khe giữa 2 dòng trong `_split_paragraph_into_lines`
của babeldoc, GIỮ NGUYÊN ngưỡng gốc `count < 1`.

Protocol 6 R6-02: test KHÔNG được chỉ assert "hàm chạy không lỗi". Test này
gọi đúng logic production (`src/babeldoc_shim/line_split.split_into_line_groups`
— cùng hàm mà `sitecustomize.py` monkey-patch vào `ParagraphFinder` khi chạy
trong subprocess babeldoc thật) trên chính golden fixture
`tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz` và assert SỐ
DÒNG CỤ THỂ của từng paragraph theo đúng bảng oracle X2 trong Architecture.md
— KHÔNG suy diễn, copy nguyên số liệu.

Golden fixture nguồn: babeldoc 0.6.4 `--debug` thật trên 4 trang p74-77 của
"How baking works" (Figoni), `--openai-base-url` trỏ cổng chết (0 token LLM).
Dump được ghi TRƯỚC bước dịch, dùng đúng `ParagraphFinder._split_paragraph_into_lines`
GỐC (chưa patch) — nên mỗi paragraph bị bug gộp dòng trong dump này có ĐÚNG 1
`pdf_line` chứa toàn bộ ký tự đã bị gộp sai. Test dùng lại chính tập ký tự đó
làm input cho thuật toán ĐÃ SỬA, để kiểm tra thuật toán sửa có tách đúng số
dòng theo ground truth hay không.

KHÔNG viết mock tay theo giả định (Protocol 5 mục 3) — mọi số liệu ở đây đọc
trực tiếp từ golden fixture đã có sẵn trong repo.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from src.babeldoc_shim.line_split import CharBound, split_into_line_groups

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "babeldoc" / "paragraph_finder_p74_77_dump.json.gz"
)


def _load_dump() -> dict:
    with gzip.open(_FIXTURE_PATH, "rt", encoding="utf-8") as f:
        return json.load(f)


def _gather_raw_chars(comp_list: list[dict]) -> list[dict]:
    """Gom tat ca PdfCharacter (dang dict tho tu JSON) tu 1
    `pdf_paragraph_composition`. Cung logic voi `analyze.py` da dung o spike
    7.0 (khong duplicate thuat toan tach dong — chi doc du lieu tho)."""
    chars: list[dict] = []
    for comp in comp_list:
        if comp.get("pdf_character") is not None:
            chars.append(comp["pdf_character"])
        elif comp.get("pdf_line") is not None:
            chars.extend(comp["pdf_line"].get("pdf_character") or [])
        elif comp.get("pdf_formula") is not None:
            chars.extend(comp["pdf_formula"].get("pdf_character") or [])
        elif comp.get("pdf_same_style_characters") is not None:
            chars.extend(comp["pdf_same_style_characters"].get("pdf_character") or [])
    return chars


def _is_debug_info_only(comp_list: list[dict]) -> bool:
    return any(
        isinstance(c.get("pdf_same_style_unicode_characters"), dict)
        and c["pdf_same_style_unicode_characters"].get("debug_info")
        for c in comp_list
    )


def _effective_y_bounds(char: dict) -> tuple[float, float]:
    """`ParagraphFinder._get_effective_y_bounds` cua babeldoc 0.6.4 co dead
    code sau `return` dau tien (verified, Architecture.md X2-c:
    `paragraph_finder.py:608-613`) — luon tra ve `visual_bbox.box`, khong
    bao gio roi xuong nhanh IoU/`pdf_box`. Test dung dung hanh vi that do."""
    visual_bbox = char.get("visual_bbox") or {}
    box = visual_bbox.get("box") or char["box"]
    return box["y"], box["y2"]


def _char_to_bound(char: dict) -> CharBound:
    y1, y2 = _effective_y_bounds(char)
    unicode_ = char.get("char_unicode") or ""
    return CharBound(y1=y1, y2=y2, is_space=bool(unicode_) and unicode_.isspace())


def _find_paragraph(dump: dict, page_index: int, text_prefix: str) -> dict:
    page = dump["page"][page_index]
    matches = [
        p
        for p in page.get("pdf_paragraph", []) or []
        if (p.get("unicode") or "").startswith(text_prefix)
    ]
    assert len(matches) == 1, (
        f"Ky vong dung 1 paragraph tren page {page_index} bat dau bang "
        f"{text_prefix!r}, tim thay {len(matches)}"
    )
    return matches[0]


def _predicted_line_count(paragraph: dict) -> int:
    chars = _gather_raw_chars(paragraph["pdf_paragraph_composition"])
    bounds = [_char_to_bound(c) for c in chars]
    return len(split_into_line_groups(bounds))


# Bang oracle X2 (Architecture.md) — KHONG suy dien, copy nguyen so lieu.
# (page_index trong golden dump, text_prefix, so dong GROUND TRUTH ky vong
# SAU KHI fix).
_ORACLE_CASES = [
    (1, "1. Explain what is meant by products having differences in their chemical", 3),
    (1, "2. Explain what is meant by products having differences in their physical", 3),
    (2, "Using regular (water-soluble) blue food coloring", 7),
    (2, "Compare the texture of properly stored", 5),
    (2, "Compare the texture of two products of your choice", 7),
    (3, "Apple juice is a relatively mild-tasting juice", 5),
    (3, "Work slowly through this exercise", 3),
    (3, "While diluted apple juice is used", 3),
    (3, "■ To identify and describe differences", 2),
    (3, "■ To demonstrate how sugar affects", 6),
    (3, "■ Sugar and acid ■ Other", 5),
    (3, "■ No additions (control product)", 3),
    (3, "■ Tannin powder ■ Caffeine", 2),
    (3, "■ Apple juice, 6 quarts (liters) or more", 2),
]

# `)60` (page 1) va `)62` (page 3) — nhan `abandon` (so trang, page furniture).
# X2 xac nhan day la 2/163 ca CON LAI SAI ke ca SAU fix cua Expert (GT=2
# nhung ca "loai ky tu trang" van cho 1) — KHONG phai hoi quy cua fix nay,
# KHONG dang xu ly (X2: "2 ca con sai deu la nhan abandon, khong dang xu
# ly"). Test rieng ben duoi de ghi lai dung trang thai da biet nay, tranh
# lam oracle chinh "gia dinh sai" la fix nay sua duoc ca 163/163.
_KNOWN_UNFIXED_CASES = [
    (1, ")60", 1),
    (3, ")62", 1),
]


@pytest.fixture(scope="module")
def dump() -> dict:
    return _load_dump()


@pytest.mark.parametrize("page_index,text_prefix,expected_lines", _ORACLE_CASES)
def test_fixed_split_matches_oracle_line_count(
    dump: dict, page_index: int, text_prefix: str, expected_lines: int
) -> None:
    paragraph = _find_paragraph(dump, page_index, text_prefix)
    assert _predicted_line_count(paragraph) == expected_lines


@pytest.mark.parametrize("page_index,text_prefix,expected_lines", _KNOWN_UNFIXED_CASES)
def test_known_unfixed_page_furniture_cases_documented(
    dump: dict, page_index: int, text_prefix: str, expected_lines: int
) -> None:
    """X2: 2/163 paragraph (`)60`/`)62`, nhan `abandon` — so trang) van con
    sai SAU KHI fix (khong lien quan gi den ky tu trang/descender — nguyen
    nhan khac, ngoai pham vi Bug #7). Ghi lai tuong minh de bat ky ai vo
    tinh "sua" duoc case nay trong tuong lai biet ma cap nhat oracle, va de
    khong ai nham lan coi day la hoi quy cua fix hien tai."""
    paragraph = _find_paragraph(dump, page_index, text_prefix)
    assert _predicted_line_count(paragraph) == expected_lines


def test_fixed_split_does_not_regress_single_char_line() -> None:
    """X2-b: `count<2` gay hoi quy voi dong dung 1 ky tu (o so hep trong
    bang). Cach loai ky tu trang KHONG duoc phep co hoi quy nay — dung theo
    dung ca tong hop cua Architecture.md X2-b bang 1."""
    # 1 chu so dung rieng 1 dong (font 10pt, line pitch 12pt — cung kich
    # thuoc voi ca that trong X3) + 1 dong van xuoi ben duoi, cach nhau du
    # xa de khong co ky tu trang nao bac cau qua khe (khac voi ca that trong
    # X3, o day khong co descender/space chen giua).
    bounds = [
        CharBound(y1=100.0, y2=110.0, is_space=False),  # dong 1: "5" don doc
        CharBound(y1=80.0, y2=90.0, is_space=False),  # dong 2: chu dau van xuoi
        CharBound(y1=80.0, y2=90.0, is_space=False),
    ]
    assert len(split_into_line_groups(bounds)) == 2


def test_fixed_split_ignores_bridging_space_but_keeps_it_on_its_line() -> None:
    """X3: ky tu trang khong glyph, visual_bbox cao bang font_size, lap gan
    het khe that giua 2 dong -> bat ky ky tu co descender nao cham vao phan
    con lai la du khien count khong ve 0. Sau fix: loai space khoi phep dem,
    khe duoc phat hien dung; nhung space VAN duoc gan dung vao dong cua no
    (khong bi loai khoi output, chi khong duoc dem).

    Hinh hoc: dong 1 (than chu 92-102 + duoi descender 88-92, cham nhau tai
    92) va dong 2 (76-86) co khe THAT (chi tinh ky tu co muc) la 86-88 (2pt,
    dung ty le voi X3). 1 ky tu khoang trang (85-95, cao ~bang font_size)
    lap CHONG LEN dung vung khe that do — neu bi dem, khe bien mat.
    """
    line1_body = CharBound(y1=92.0, y2=102.0, is_space=False)
    line1_descender = CharBound(y1=88.0, y2=92.0, is_space=False)  # duoi cua "g"
    bridging_space = CharBound(y1=85.0, y2=95.0, is_space=True)  # space cao = font_size (X3)
    line2_body = CharBound(y1=76.0, y2=86.0, is_space=False)

    bounds = [line1_body, line1_descender, bridging_space, line2_body]
    groups = split_into_line_groups(bounds)

    assert len(groups) == 2, "Loai space khoi phep dem phai tach duoc 2 dong (X3)"

    # Space (index 2 trong `bounds`) van phai xuat hien trong 1 trong 2 nhom
    # (khong bi mat noi dung) — gan theo tam y nhu binh thuong.
    all_assigned_indices = sorted(i for group in groups for i in group)
    assert all_assigned_indices == [0, 1, 2, 3]


def test_original_unfixed_behavior_collapses_to_single_line_as_documented() -> None:
    """Tai hien dung hien tuong X3 mo ta khi KHONG loai ky tu trang (hanh vi
    GOC cua babeldoc 0.6.4, chua fix) — cung hinh hoc voi test tren nhung
    `is_space=False` cho ca ky tu von la space, mo phong `count<1` tinh CA
    khoang trang. Xac nhan bug that su ton tai truoc khi fix, khong phai
    hien tuong tu dung ra cua fixture."""
    line1_body = CharBound(y1=92.0, y2=102.0, is_space=False)
    line1_descender = CharBound(y1=88.0, y2=92.0, is_space=False)
    # Neu KHONG loai space khoi phep dem (hanh vi goc), no van tham gia dem
    # va cham binh thuong -> ham nay mo phong bang is_space=False cho space.
    bridging_space_counted = CharBound(y1=85.0, y2=95.0, is_space=False)
    line2_body = CharBound(y1=76.0, y2=86.0, is_space=False)

    bounds = [line1_body, line1_descender, bridging_space_counted, line2_body]
    groups = split_into_line_groups(bounds)

    assert len(groups) == 1, (
        "Khi khong loai ky tu trang khoi phep dem, khe bi bac cau boi "
        "descender + space -> ca 2 dong gop thanh 1 (dung Bug #7 that, X3)"
    )
