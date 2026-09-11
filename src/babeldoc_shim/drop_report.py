"""Thuat toan thuan (khong phu thuoc babeldoc) dung boi patch quan sat BL-04
(Architecture.md 6.22.4, "Thiet ke — patch quan sat (observer) trong shim +
file sidecar JSONL"): predicate phat hien drop + dung dict record cho tung
dong JSONL + ham ghi append. Tach rieng module de test duoc KHONG can babeldoc
cai san (Protocol 6 R6-02: test phai goi dung logic production, khong duoc
chep tay lai thuat toan roi test ban chep) — cung pattern voi
`word_wrap.py`/`line_split.py`/`numbered_list_split.py`/`toc_split.py`.

`has_rendered_chars`/`is_dropped` sao chep DUNG dinh nghia cua chinh babeldoc
0.6.4 (`pdf_creater.py:814-831`, Architecture.md 6.22.4 "Predicate phat hien
drop"), khong tu phat minh nguong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Architecture.md 6.22.4 — cat `text_excerpt` toi da 400 ky tu de QA doc de
#: va giu file sidecar nho. KHONG phai nguong nguyen tu ghi (dinh chinh F7,
#: xem doc day du trong Architecture.md).
TEXT_EXCERPT_MAX_CHARS = 400

#: Architecture.md 6.22.4 "Schema moi dong".
SCHEMA = "babeldoc_drop_report/v2"


def has_rendered_chars(paragraph: Any) -> bool:
    """True neu `paragraph` (PdfParagraph babeldoc) co it nhat 1 ky tu DA
    duoc typeset. Sao chep dung `PDFCreater.render_paragraph_to_char`
    (`pdf_creater.py:814-831` ban 0.6.4 da cai)."""
    for comp in paragraph.pdf_paragraph_composition or []:
        if comp.pdf_character is not None:
            return True
        pdf_formula = comp.pdf_formula
        if pdf_formula is not None and pdf_formula.pdf_character:
            return True
    return False


def is_dropped(paragraph: Any) -> bool:
    """`dropped <=> (not has_rendered_chars(p)) and p.unicode and p.debug_id`
    (Architecture.md 6.22.4)."""
    return (
        not has_rendered_chars(paragraph) and bool(paragraph.unicode) and bool(paragraph.debug_id)
    )


def build_header_record(babeldoc_version: str, pid: int) -> dict[str, Any]:
    """Architecture.md 6.22.4 "Dong header" — ghi luc patch duoc ap thanh
    cong (luc import module). Co the co NHIEU dong header (1/process con,
    macOS `mp.set_start_method("spawn")`) — parser chi can >=1 dong hop le."""
    return {
        "type": "header",
        "schema": SCHEMA,
        "babeldoc_version": babeldoc_version,
        "pid": pid,
    }


def build_page_record(
    page_number_1based: int, paragraph_count: int, dropped_count: int
) -> dict[str, Any]:
    """Architecture.md 6.22.4 "Record type=page — vi sao ton tai (F2)" —
    ghi 1 dong MOI trang di qua hook, chung minh hook da chay tren du trang
    (khong chi "da cai")."""
    return {
        "type": "page",
        "page_number_1based": page_number_1based,
        "paragraph_count": paragraph_count,
        "dropped_count": dropped_count,
    }


def _box_tuple(box: Any) -> tuple[float, float, float, float] | None:
    if box is None:
        return None
    return (box.x, box.y, box.x2, box.y2)


def build_drop_record(paragraph: Any, page_number_1based: int) -> dict[str, Any]:
    """Architecture.md 6.22.4 bang "Schema moi dong", cot `drop`."""
    text = paragraph.unicode or ""
    return {
        "type": "drop",
        "page_number_1based": page_number_1based,
        "debug_id": paragraph.debug_id,
        "layout_label": paragraph.layout_label,
        "box": _box_tuple(paragraph.box),
        "optimal_scale": paragraph.optimal_scale,
        "scale": paragraph.scale,
        "text_excerpt": text[:TEXT_EXCERPT_MAX_CHARS],
        "text_len": len(text),
    }


def collect_page_records(
    page: Any, page_number_1based: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Duyet `page.pdf_paragraph`, tra ve `(page_record, drop_records)` —
    dung boi patch trong `sitecustomize.py`. `page_record["dropped_count"]`
    la checksum chinh chu voi so luong `drop_records` tra ve (Architecture.md
    6.22.6 "Checksum cheo trong chinh file sidecar")."""
    drop_records: list[dict[str, Any]] = []
    paragraphs = page.pdf_paragraph or []
    for paragraph in paragraphs:
        if is_dropped(paragraph):
            drop_records.append(build_drop_record(paragraph, page_number_1based))
    page_record = build_page_record(
        page_number_1based=page_number_1based,
        paragraph_count=len(paragraphs),
        dropped_count=len(drop_records),
    )
    return page_record, drop_records


def append_jsonl_record(path: str, record: dict[str, Any]) -> None:
    """Mo file o che do append, ghi DUNG 1 dong JSON roi dong ngay — an toan
    voi multiprocessing `spawn` cua babeldoc (Architecture.md 6.22.4 "Quy tac
    ghi"). `ensure_ascii=False` bat buoc (giu tieng Viet doc duoc thang)."""
    line = json.dumps(record, ensure_ascii=False)
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(line + "\n")
