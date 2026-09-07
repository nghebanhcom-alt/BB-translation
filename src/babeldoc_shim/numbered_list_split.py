"""Thuat toan tach paragraph theo marker numbered-list tang dan (thuan Python,
khong phu thuoc babeldoc), dung chung boi `sitecustomize.py` (patch that su,
chay trong subprocess babeldoc) VA test (`tests/test_babeldoc_numbered_list_split.py`,
chay trong process app — Protocol 6 R6-02: test phai goi dung logic
production, khong duoc chep tay lai thuat toan roi test ban chep).

Boi canh (Architecture.md "Bug #7/#8 — Final Decision sau phan bien Domain
Expert (2026-09-07)", X5 D7-3 buoc 7.2 — Ca A): sau khi tang dong da duoc
sua (7.1), mot so paragraph van con GOM CHUNG nhieu muc numbered-list vao
1 paragraph duy nhat (vd 8 muc "8./9./10.../15." dinh lien trong 1
paragraph — xac nhan bang spike song tren du lieu thuc, khong suy doan).
Ham nay tim diem tach: dong dau tien cua paragraph la "marker neo"
(vd "8."), diem tach la dong DAU TIEN xuat hien sau do co marker dung
bang marker neo + 1 (vd "9."). Khong cap nhat lai marker neo theo cac
marker KHONG khop giua duong — day la co che chinh chan false-positive
(Architecture.md yeu cau: phai loai duoc ca "2 cups" trong cong thuc).
"""

from __future__ import annotations

import re

_MARKER_RE = re.compile(r"^\s*(\d{1,3})[.)]\s+\S")


def extract_leading_marker(text: str | None) -> int | None:
    """Tra ve so thu tu neu `text` mo dau bang marker numbered-list
    (vd "1. ", "12) ") kem it nhat 1 ky tu noi dung sau marker, nguoc lai
    tra ve None.

    Yeu cau `[.)]` roi KHOANG TRANG ngay sau chu so (khong phai chu so
    khac) — day la ly do "2.5 cups" hay "2,5" KHONG khop (khong co khoang
    trang ngay sau dau `.`), va "2 cups" KHONG khop (khong co `.`/`)` ngay
    sau chu so). Da verify song tren du lieu thuc (spike, khong suy doan):
    quet toan bo trang "QUESTIONS FOR REVIEW" (p74) + danh sach 35-muc
    "EQUIPMENT AND SMALLWARES" — 0 false-positive tren cac muc co dinh
    kem so luong nhu "1½ quart", "2- and 4-quart sizes", "2" or 2½"".
    """
    if not text:
        return None
    m = _MARKER_RE.match(text)
    return int(m.group(1)) if m else None


def find_numbered_list_split_index(line_texts: list[str | None]) -> int | None:
    """Tim vi tri tach 1 paragraph co nhieu dong (moi phan tu cua
    `line_texts` la text da sort theo x cua 1 `pdf_paragraph_composition`,
    hoac None neu composition do khong phai `pdf_line` — vd `pdf_formula`).

    Tra ve index `j >= 1` de tach: giu `composition[:j]` o paragraph goc,
    chuyen `composition[j:]` sang paragraph moi (dung nguyen mau tach cua
    babeldoc `process_independent_paragraphs`, paragraph_finder.py:868-925
    — tai su dung, khong chep lai logic typeset). Tra ve None neu khong
    tim thay diem tach nao.

    Marker neo lay tu dong DAU TIEN (`line_texts[0]`) — neu dong dau khong
    phai marker thi KHONG tach gi ca (paragraph nay khong bat dau bang 1
    muc numbered-list, tranh bat nham marker xuat hien ngau nhien giua 1
    doan van xuoi khong lien quan).
    """
    if not line_texts:
        return None

    anchor_marker = extract_leading_marker(line_texts[0])
    if anchor_marker is None:
        return None

    target = anchor_marker + 1
    for idx in range(1, len(line_texts)):
        if extract_leading_marker(line_texts[idx]) == target:
            return idx
    return None


def split_paragraph_lines(line_texts: list[str | None]) -> list[list[str | None]]:
    """Tach 1 paragraph (bieu dien boi `line_texts`, moi phan tu ung voi 1
    `pdf_paragraph_composition`) thanh danh sach cac nhom LIEN TIEP, moi nhom
    la 1 paragraph ket qua sau khi tach — bang cach goi lap
    `find_numbered_list_split_index` (chinh xac tuong duong voi vong lap
    ngoai cua `process_independent_paragraphs` goc cua babeldoc: tach 1
    diem, roi tiep tuc tim diem tach tiep theo TRONG phan con lai).

    Tra ve `[line_texts]` (1 nhom duy nhat == nguyen ban) neu khong co diem
    tach nao ca — goi noi dung khong tach ai het.

    Day la HAM DUY NHAT quyet dinh ranh gioi tach — `sitecustomize.py` chi
    dung ket qua nay de cat `pdf_paragraph_composition` thuc (khong tu
    quyet dinh gi them), va test golden fixture goi dung ham nay (Protocol 6
    R6-02).
    """
    if not line_texts:
        return [line_texts]

    groups: list[list[str | None]] = []
    remaining = line_texts
    while True:
        split_idx = find_numbered_list_split_index(remaining)
        if split_idx is None:
            groups.append(remaining)
            return groups
        groups.append(remaining[:split_idx])
        remaining = remaining[split_idx:]


def build_sorted_line_text(chars: list[tuple[float, str]]) -> str:
    """Ghep ky tu thanh text theo dung thu tu x tang dan (Architecture.md
    X4-4: cac loi goi sort theo x trong babeldoc 0.6.4 deu bi comment —
    `paragraph_finder.py:305,696,738,772` — nen thu tu ky tu trong
    `pdf_character` KHONG duoc dam bao, wrapper phai tu sort truoc khi
    ghep chuoi di tim marker).

    `chars` la danh sach `(x, char_unicode)` — trong `sitecustomize.py`,
    `x` la `char.visual_bbox.box.x` cua PdfCharacter that.
    """
    return "".join(ch for _x, ch in sorted(chars, key=lambda item: item[0]))
