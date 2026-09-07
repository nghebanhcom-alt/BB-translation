"""Thuat toan tach paragraph muc luc (TOC-1 v2, "Bug #7 Ca C") — thuan Python,
KHONG import babeldoc, dung chung boi (tuong lai) `sitecustomize.py` va cong
cu do/test — dung khuon `numbered_list_split.py` cua buoc 7.2 (Protocol 6
R6-02: test/do phai goi DUNG logic production, khong duoc chep tay lai roi
test ban chep).

TRANG THAI: day la SAN PHAM CUA SPIKE 7.4-a (Protocol 5 R5-02) — dac ta chot
o `docs/Architecture.md`, muc "Bug #7 Ca C — Quyet dinh cuoi sau phan bien
Domain Expert + ke hoach spike 7.4-a (Tech Lead, 2026-09-08)", AA4 (thuat
toan) + AA5 (tham so). Module nay CHUA duoc wiring vao `sitecustomize.py`
(patch thu 3) — do la pham vi cua 7.4-c, chi lam sau khi spike PASS gate AA9.

THIET KE (giong het `numbered_list_split.py`): module nay KHONG dam nhiem
viec doc field tu object IL that cua babeldoc hay tu dict JSON dump — do la
viec cua caller (script do cua spike, test, hoac sau nay la
`sitecustomize.py`). Ham o day chi nhan cac kieu du lieu thuan Python
(`TocChar`, tuple toa do) de:
  1. Test/do duoc doc lap voi cau truc object cua babeldoc (khong vo neu
     babeldoc doi ten field o mot noi khong lien quan).
  2. Dung chung 1 y het logic cho ca dump JSON (spike) lan object IL that
     (san sang cho 7.4-c) — chi khac nhau o buoc extract truoc khi goi vao
     day.

Boi canh Ca C (tom tat, xem AA0-AA3 de biet day du): babeldoc gop nhieu muc
muc luc (moi muc 1 dong, ket thuc bang so trang, cach noi dung boi khoang
trang rong do dot-leader) vao 1 `PdfParagraph` duy nhat vi khong co dot-leader
"du day" (< 20 cham) de babeldoc tu tach. Guard hinh hoc theo box layout
`table` (de xuat ban dau cua Domain Expert, Z8-2 muc i) da bi BAC BO (AA3) vi
no giet 5/11 paragraph muc luc that cua Le Cordon Bleu (trang Contents thu 2
bi chinh layout model gan nham nhan `table`) ma khong cuu duoc gi tren 3
trang cong thuc banh. Thay bang deny-list theo `paragraph.layout_label` o
buoc 0 duoi day.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tham so chot — AA5. KHONG doi gia tri o day khi chua co so lieu do lai tren
# tap 8+ fixture cua Architecture.md AA7/AA9 (day la gate PASS/FAIL, khong
# phai tham so tuy chinh tu do).
# ---------------------------------------------------------------------------

TOC_GAP_RATIO = 0.8
"""Nguong `gap / font_size` cua khoang trang cuoi dong truoc so trang (theo
he do `visual_bbox`, KHONG dung advance-width cua PyMuPDF — chot theo Z3).
Da quet 0.5->1.0 tren 12 dump IL that: FP luon = 0 o moi muc, ngung o 0.8 vi
day la muc co nhieu du lieu nhat VA chan duoc slug in an nhan `abandon` co
ratio 0.82-0.93 (AA3/AA5) — KHONG phai vi "khe an toan rong" (dinh chinh AA11,
Y7/Y12 da ghi sai)."""

TOC_MIN_TAIL_LINES = 2
"""So dong toi thieu trong 1 paragraph phai duoc danh dau "duoi muc luc" moi
xet tach — lop chong false-positive CHINH (Y7 + Z3 deu dong y), khong phai
`TOC_GAP_RATIO`."""

TOC_MIN_TAIL_FRACTION = 0.6
"""Ty le toi thieu `so dong danh dau / tong so dong` trong 1 paragraph.
31/31 paragraph muc luc kich hoat thoa nguong nay (AA5)."""

TOC_MIN_BODY_ALPHA_RUNS = 1
"""So cum >= 2 chu cai ASCII toi thieu phai co trong phan than dong (truoc
day so trang) — loai o bang thuan so ("4.0"), folio don le."""

TOC_MAX_DIGITS = 4
"""So chu so toi da cua "so trang" o cuoi dong — sach in <= 9999 trang."""

TOC_REQUIRE_NON_DECREASING = True
"""Bat buoc day so trang cua cac dong danh dau trong 1 paragraph KHONG duoc
giam dan (cho phep bang nhau) — dieu kien cung, khong phai heuristic (Z4)."""

TOC_CONT_INDENT_EM = 1.0
"""Nguong thut dau dong (theo don vi em = `font_size` cua dong danh dau) de
coi 1 dong KHONG danh dau ngay sau la "dong noi" kieu Bo Friberg (Z7-a) va
gop vao group TRUOC no thay vi tach rieng. Da do that: moi ranh gioi "danh
dau -> khong danh dau" trong 31 paragraph kich hoat co delta thut dau dong
trong khoang [-13.0, +0.1] pt — ca xa nguong nay (vi du Friberg dung 6.75 em)
=> luat nay la NO-OP tren du lieu hien co (AA5, AA8 buoc 4 phai tai xac nhan
dieu nay tren du lieu that cua spike)."""

TOC_DOT_LEADER_FALLBACK = False
"""Chua bat: fallback cho dot-leader < 20 cham (TOC-1b). Chua co du lieu that
de thiet ke — bien nay giu cho de ghi lai bien thiet ke tuong minh (AA4), v2
KHONG dung no o dau ca."""

TOC_LAYOUT_LABEL_DENY: frozenset[str] = frozenset(
    {
        "abandon",
        "header",
        "footer",
        "page_header",
        "page_footer",
        "table",
        "table_cell",
        "wired_table_cell",
        "wireless_table_cell",
        "table_cell_hybrid",
        "table_text",
        "table_caption",
        "table_footnote",
        "figure",
        "figure_caption",
        "figure_text",
        "formula",
        "isolate_formula",
        "formula_caption",
    }
)
"""Deny-list theo `paragraph.layout_label` (chuan hoa lower/strip truoc khi
so sanh) — thay the cho de xuat guard hinh hoc theo box `table` cua Domain
Expert, da bi BAC BO o AA3 (giet 5/11 paragraph muc luc that cua Le Cordon
Bleu, khong cuu duoc gi tren 3 trang cong thuc). Nguon nhan: tap hop nhan
layout hop le trong `utils/layout_helper.py:655-690` va `:789-845` cua
babeldoc 0.6.4 da cai — da doc source that (AA4)."""

_ALPHA_RUN_RE = re.compile(r"[A-Za-z]{2,}")
_ASCII_DIGITS = frozenset("0123456789")

REASON_DENY_LAYOUT = "deny_layout"
REASON_TOO_SHORT = "too_short"
REASON_FEW_TAIL_LINES = "few_tail_lines"
REASON_LOW_FRACTION = "low_fraction"
REASON_NOT_MONOTONIC = "not_monotonic"
REASON_NO_CUT_POINTS = "no_cut_points"
REASON_FIRED = "fired"


@dataclass(frozen=True)
class TocChar:
    """1 ky tu cua 1 dong (`pdf_line.pdf_character` cua babeldoc), da rut gon
    ve cac field TOC-1 v2 can — caller (script do / test / sau nay la
    `sitecustomize.py`) chiu trach nhiem doc dung field that tu object IL hay
    tu dict JSON dump roi tao ra `TocChar`, module nay khong biet gi ve
    nguon goc du lieu.

    `x`/`x2` PHAI la `visual_bbox.box.x`/`.x2` (KHONG phai `box.x`/`.x2` hay
    `advance` cua PyMuPDF — chot theo Z3/AA4 buoc 2 muc 5)."""

    x: float
    x2: float
    unicode: str
    font_size: float


@dataclass(frozen=True)
class LineMark:
    """Ket qua danh dau 1 dong la "duoi muc luc" (AA4 buoc 2)."""

    n: int
    """Gia tri so trang doc duoc tu day chu so ASCII cuoi dong."""
    size: float
    """`font_size` cua ky tu cuoi cung phan than dong (ngay truoc chu so dau
    tien) — dung lam mau cho ca `ratio` (buoc 2) lan luat noi dong (buoc 4)."""
    ratio: float
    """`gap / size` da tinh — luon >= `TOC_GAP_RATIO` (ham `mark_toc_tail`
    khong tra ve gia tri duoi nguong)."""
    min_x: float
    """`x` nho nhat trong dong (sau khi bo ky tu khoang trang) — dung lam moc
    thut dau dong o buoc 4."""


@dataclass(frozen=True)
class ContinuationBoundary:
    """1 ranh gioi "dong danh dau -> dong KHONG danh dau ngay sau" duoc xet
    boi luat noi dong (AA4 buoc 4). Ghi lai CA KHI khong duoc gop, phuc vu
    dung do rieng cua AA8 buoc 4 (chung minh luat la no-op tren du lieu
    that, khong chi suy doan)."""

    marked_index: int
    next_index: int
    indent_delta: float
    """`min_x(dong ke tiep) - min_x(dong danh dau)`, don vi pt (KHONG phai
    boi so cua font_size) — day la con so oracle AA1/AA8 bao cao truc tiep
    (vi du "-13.0, -1.1, +0.0, +0.0, +0.0, +0.1 pt")."""
    extended: bool
    """True neu `indent_delta >= TOC_CONT_INDENT_EM * size(dong danh dau)`
    va do do dong ke tiep duoc gop vao group cua dong danh dau."""


@dataclass(frozen=True)
class ParagraphSplitResult:
    """Ket qua danh gia TOC-1 v2 tren 1 paragraph (tat ca 6 buoc AA4)."""

    fired: bool
    cut_after: tuple[int, ...]
    """Chi so composition (trong list `pdf_paragraph_composition` goc) ma
    ranh gioi tach nam NGAY SAU no. Rong khi `fired=False`."""
    reason: str
    """1 trong cac hang `REASON_*` — ly do KHONG tach (hoac `REASON_FIRED`)."""
    tail_marks: int
    """`m` — so dong duoc danh dau la duoi muc luc (buoc 2), bat ke co vuot
    qua cong buoc 3 hay khong."""
    composition_count: int
    """`L` — tong so composition (dong + formula...) cua paragraph."""
    inside_table_box: bool
    """AA3: co True/False rieng, CHI DE LOG (`fired_inside_table_box`),
    KHONG duoc dung de chan bat ky paragraph nao — guard hinh hoc theo box
    `table` da bi bac bo."""
    continuation_boundaries: tuple[ContinuationBoundary, ...]
    """Moi ranh gioi "danh dau -> khong danh dau" da xet o buoc 4, ke ca khi
    khong duoc gop (dung cho AA8 buoc 4)."""


def sort_line_chars(chars: Iterable[TocChar]) -> list[TocChar]:
    """AA4 buoc 1: bo moi ky tu `.isspace()` (gom dummy space babeldoc tu
    chen, `paragraph_finder.py:279`) roi TU sort theo `x` — bat buoc, vi ca 4
    loi goi sort theo x cua chinh babeldoc deu bi comment
    (`paragraph_finder.py:305,696,738,772`, X4-4), nen thu tu ky tu tho
    KHONG duoc dam bao."""
    return sorted((c for c in chars if not c.unicode.isspace()), key=lambda c: c.x)


def mark_toc_tail(sorted_chars: Sequence[TocChar]) -> LineMark | None:
    """AA4 buoc 2: danh dau 1 dong (da qua `sort_line_chars`) la "duoi muc
    luc" neu THOA CA 6 dieu kien. Tra ve `None` neu khong khop bat ky dieu
    kien nao — khong raise, day la duong di binh thuong (da so dong KHONG
    phai duoi muc luc)."""
    if len(sorted_chars) < 2:
        return None

    k = 0
    while k < len(sorted_chars) and sorted_chars[-1 - k].unicode in _ASCII_DIGITS:
        k += 1
    # (1) k=0: khong ket thuc bang chu so. k > MAX_DIGITS: khong phai so
    # trang sach thuc te. k == len(...): CA dong la so (folio/o bang), loai.
    if k == 0 or k > TOC_MAX_DIGITS or k == len(sorted_chars):
        return None

    body = sorted_chars[:-k]
    digits = sorted_chars[-k:]

    # (2) Dung ASCII 0-9, KHONG dung str.isdigit() — '²'.isdigit() la
    # True (Z7-c) se lam sai k o tren; kiem tra lai o day cho chac (phong
    # thu kep, vi vong while da loc theo _ASCII_DIGITS roi).
    body_text = "".join(c.unicode for c in body)
    if not _ALPHA_RUN_RE.search(body_text):
        return None

    n = int("".join(c.unicode for c in digits))
    # (3)
    if not 1 <= n <= 9999:
        return None

    # (4)
    size = body[-1].font_size
    if size <= 0:
        return None

    # (5)+(6) — he do BAT BUOC la visual_bbox (chot theo Z3), khong phai
    # advance-width cua PyMuPDF.
    gap = digits[0].x - body[-1].x2
    ratio = gap / size
    if ratio < TOC_GAP_RATIO:
        return None

    return LineMark(n=n, size=size, ratio=ratio, min_x=sorted_chars[0].x)


def _center_inside_any_box(
    box: tuple[float, float, float, float] | None,
    candidates: Sequence[tuple[float, float, float, float]],
) -> bool:
    """AA3: tam (centroid) cua `box` co nam trong bat ky box nao trong
    `candidates` khong. Dung DUY NHAT de tinh `inside_table_box` phuc vu log
    — KHONG bao gio dung ket qua nay de chan paragraph (guard hinh hoc da bi
    bac bo, xem AA3)."""
    if box is None or not candidates:
        return False
    x, y, x2, y2 = box
    cx, cy = (x + x2) / 2.0, (y + y2) / 2.0
    for bx, by, bx2, by2 in candidates:
        lo_x, hi_x = (bx, bx2) if bx <= bx2 else (bx2, bx)
        lo_y, hi_y = (by, by2) if by <= by2 else (by2, by)
        if lo_x <= cx <= hi_x and lo_y <= cy <= hi_y:
            return True
    return False


def evaluate_paragraph(
    layout_label: str | None,
    line_chars: Sequence[list[TocChar] | None],
    *,
    paragraph_box: tuple[float, float, float, float] | None = None,
    table_boxes: Sequence[tuple[float, float, float, float]] = (),
) -> ParagraphSplitResult:
    """Danh gia toan bo AA4 (buoc 0-4) cho 1 paragraph.

    `line_chars[i]` ung voi composition thu `i` trong
    `pdf_paragraph_composition` goc: `list[TocChar]` neu composition do la
    `pdf_line`, hoac `None` neu KHONG phai (vd `pdf_formula`) — dung quy uoc
    y het `numbered_list_split.find_numbered_list_split_index` (tham so
    `line_texts: list[str | None]`), chi thay `str` bang `list[TocChar]` vi
    TOC-1 v2 can hinh hoc (x, font_size), khong chi can text.

    `paragraph_box`/`table_boxes` CHI dung de tinh `inside_table_box` (log),
    khong anh huong ket qua `fired`/`cut_after`.
    """
    normalized_label = (layout_label or "").strip().lower()
    composition_count = len(line_chars)
    inside_table_box = _center_inside_any_box(paragraph_box, table_boxes)

    # Buoc 0 — cong paragraph.
    if normalized_label in TOC_LAYOUT_LABEL_DENY:
        return ParagraphSplitResult(
            False, (), REASON_DENY_LAYOUT, 0, composition_count, inside_table_box, ()
        )
    if composition_count < 2:
        return ParagraphSplitResult(
            False, (), REASON_TOO_SHORT, 0, composition_count, inside_table_box, ()
        )

    # Buoc 1 + 2 — chuan bi tung dong va thu danh dau.
    sorted_lines: list[list[TocChar] | None] = []
    marks: list[LineMark | None] = []
    for chars in line_chars:
        if chars is None:
            sorted_lines.append(None)
            marks.append(None)
            continue
        sorted_chars = sort_line_chars(chars)
        sorted_lines.append(sorted_chars)
        marks.append(mark_toc_tail(sorted_chars))

    marked_indices = [i for i, mark in enumerate(marks) if mark is not None]
    tail_marks = len(marked_indices)

    # Buoc 3 — cong co ket o muc paragraph (lop chong FP CHINH).
    if tail_marks < TOC_MIN_TAIL_LINES:
        return ParagraphSplitResult(
            False, (), REASON_FEW_TAIL_LINES, tail_marks, composition_count, inside_table_box, ()
        )
    if tail_marks / composition_count < TOC_MIN_TAIL_FRACTION:
        return ParagraphSplitResult(
            False, (), REASON_LOW_FRACTION, tail_marks, composition_count, inside_table_box, ()
        )

    numbers = [marks[i].n for i in marked_indices]  # type: ignore[union-attr]
    if TOC_REQUIRE_NON_DECREASING and any(
        numbers[idx] > numbers[idx + 1] for idx in range(len(numbers) - 1)
    ):
        return ParagraphSplitResult(
            False, (), REASON_NOT_MONOTONIC, tail_marks, composition_count, inside_table_box, ()
        )

    # Buoc 4 — diem tach + luat dong noi (Z7-a).
    cut_after: list[int] = []
    boundaries: list[ContinuationBoundary] = []
    for i in marked_indices:
        mark = marks[i]
        assert mark is not None  # da loc o marked_indices
        j = i
        while True:
            next_idx = j + 1
            if next_idx >= composition_count:
                break
            next_chars = sorted_lines[next_idx]
            if next_chars is None:
                # AA4 buoc 4 (sua theo issue non-blocking #1 cua Reviewer
                # spike 7.4-a): composition khong phai `pdf_line` (vd
                # `pdf_formula`) khong bao gio duoc danh dau VA LUON dinh
                # vao group LIEN TRUOC — giong het 7.2 (`extract_leading_marker`
                # tra ve None cho composition khong phai dong, no khong bao
                # gio la diem tach, tu nhien nam trong group truoc no). Khong
                # co font_size/x de do "thut dau dong" cho mot composition
                # khong phai dong, nen KHONG ghi `ContinuationBoundary` cho no
                # (boundary chi danh cho cap dong-danh-dau -> dong-khong-
                # danh-dau that su, phuc vu dung do rieng cua AA8 buoc 4) —
                # chi don gian keo `j` vuot qua no roi tiep tuc xet composition
                # ke tiep (co the la dong that, hoac 1 composition non-line
                # khac).
                j = next_idx
                continue
            if marks[next_idx] is not None:
                break
            if not next_chars:
                # Dong ton tai nhung sau khi bo khoang trang khong con ky tu
                # nao (bat thuong, chua thay trong du lieu that) — dung fail
                # -safe: coi nhu KHONG the do duoc, dung noi tiep tai day.
                break
            next_min_x = next_chars[0].x
            indent_delta = next_min_x - mark.min_x
            extended = indent_delta >= TOC_CONT_INDENT_EM * mark.size
            boundaries.append(ContinuationBoundary(i, next_idx, indent_delta, extended))
            if not extended:
                break
            j = next_idx
        if j < composition_count - 1:
            cut_after.append(j)

    cut_after_sorted = tuple(sorted(set(cut_after)))
    if not cut_after_sorted:
        return ParagraphSplitResult(
            False,
            (),
            REASON_NO_CUT_POINTS,
            tail_marks,
            composition_count,
            inside_table_box,
            tuple(boundaries),
        )

    return ParagraphSplitResult(
        True,
        cut_after_sorted,
        REASON_FIRED,
        tail_marks,
        composition_count,
        inside_table_box,
        tuple(boundaries),
    )
