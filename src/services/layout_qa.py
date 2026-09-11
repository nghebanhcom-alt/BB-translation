"""Layout QA gate — hau kiem chat luong output PDF da dich (Architecture.md
"Final Decision: Babeldoc Layout Bug Fix Roadmap", U4/P0.1).

5 kiem tra, dung PyMuPDF, khong mock hinh hoc (Protocol 5 R5-03 — moi so do
deu chay tren file PDF that qua `fitz`):

    a. cap block text giao nhau > 5% dien tich block nho hon (DoD-UX-01/UX-A).
       Tai su dung dung nguong + logic da chay that o T3-a.
    b. text vuot qua duong vien ve (`page.get_drawings()`) (DoD-UX-03/UX-B).
    c. text de len anh (`page.get_image_rects()`) (UX-B).
    d. pre-scan chu xoay tren file GOC — `line["dir"]` ngoai 0/90 deg, dung
       sai +-0.1 deg (dung nguong `il_creater.py:968-974` cua babeldoc) —
       day chinh la G1d, xuat danh sach trang + text nghi mat cho QA doc,
       KHONG phai san pham giao nguoi doc cuoi (Architecture.md U4/P1.1).
    e. bao toan thuc the so+don vi: regex tren block GOC, assert xuat hien
       trong block DICH tuong ung (match theo bbox, khong so toan trang).
       Day la heuristic (flag), KHONG phai NLP entity-matching chinh xac
       100% — muc dich la co bao ve QA soi, khong phai khang dinh tuyet doi.

Kiem tra (d) va (e) can file PDF GOC (`source_pdf_path`) — bo qua neu khong
truyen vao (vd khi chi co output, khong con giu file goc).

Output la HANG DOI REVIEW THEO TRANG, xep hang muc nghiem trong — KHONG phai
1 ket qua pass/fail toan tai lieu (yeu cau tuong minh cua Tech Lead, U4/P0.1):
voi tai lieu vai tram trang, muc tieu la QA soi 30-50 trang bi flag, khong
phai doc lai toan bo.

Ket qua duoc luu vao DB (`LayoutQaFinding`, xem `persist_findings`) de so
sanh giua cac lan chay (dieu kien bat buoc cho P0.2 A/B) — day la ly do gate
nay dung TRUOC moi fix, khong phai fix.

Quy uoc `page_number` trong module nay: 1-indexed (khac `fitz.Page.number`
0-indexed), de khop voi cach Architecture.md/UX report goi trang ("trang
67") — tranh nham lan khi doi chieu voi tai lieu.
"""

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

#: DoD-UX-01 / T3-a — nguong giao nhau tinh theo % dien tich block NHO HON.
OVERLAP_AREA_RATIO_THRESHOLD = 0.05

#: Cung nguong voi babeldoc `il_creater.py:968-974` (Architecture.md T-01,
#: verified). Line co goc xoay ngoai 0/90 deg +- nguong nay se bi babeldoc
#: 0.6.4 vut o buoc parse -> mat trang khi dich.
ROTATION_TOLERANCE_DEG = 0.1

#: Nguong IoU toi thieu de coi 1 block dich la "tuong ung vi tri" voi 1 block
#: goc khi doi chieu thuc the (e). Co chu dich long (khong doi 1:1 nhu (a))
#: vi babeldoc/pdf2zh co the dich chuyen block dich khoi toa do goc (chinh
#: RC-T1) — muc tieu chi la tim block GAN NHAT ve vi tri, khong doi hoi trung
#: khop hinh hoc.
_ENTITY_MATCH_MIN_IOU = 0.05

#: check_type dung boi `src/postprocess/rotated_text_overlay.py` (Architecture.md
#: U4/P1.1, U5/U7-E1) khi 1 khoi chu xoay khong vua bbox du da bop toi
#: `MIN_FONT_SCALE` — tai su dung CHINH co che `layout_qa_findings` nay
#: (khong tao bang moi) de QA soi tay, dung nhu (d)/(e) o tren.
ROTATED_OVERLAY_FLAG_CHECK = "rotated_text_overlay_flag"

#: check_type dung boi `src/services/mineru_det_probe.py` (Architecture.md
#: "Final Decision" Bug #6, V6 Phase 1) khi 1 khoi chu xoay tren TRANG SCAN
#: (khac ROTATED_OVERLAY_FLAG_CHECK o tren, danh cho babeldoc lam mat chu xoay
#: tren PDF DIGITAL) duoc MinerU detector phat hien nhung KHONG the tai tao
#: lai goc trong ban dich (Phase 1 chi FLAG, khong sua hinh hoc — xem
#: `angle_deg` trong `detail`).
ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK = "rotated_text_scan_unsupported"

#: BL-04 (Architecture.md 6.22.6) — babeldoc tu bo han 1 doan van vi khong
#: vua khung sau khi da bop toi `min_scale=0.1` (kenh KHAC voi Bug #9/
#: font_shrink — xem audit 6.22.7). Hau to `_unfit` BAT BUOC: co che nay CHI
#: do kenh "khong vua khung", KHONG do 2 kenh mat noi dung khac cua babeldoc
#: (loc theo goc xoay / thieu font id — xem 6.22.6.1, backlog BL-08).
BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK = "babeldoc_paragraph_drop_unfit"

#: BL-04 — khong co dong `header` hop le nao trong file sidecar (shim tat /
#: version babeldoc khac 0.6.4 / patch that bai) -> KHONG do duoc, KHONG duoc
#: quy ve "0 drop" (Architecture.md 6.22.6 "BON trang thai").
BABELDOC_DROP_REPORT_UNAVAILABLE_CHECK = "babeldoc_drop_report_unavailable"

#: BL-04 — do duoc NHUNG khong tron ven: thieu trang so voi
#: `expected_pages`, HOAC checksum (`page.dropped_count` vs so dong `drop`
#: thuc te) lech nhau (X5, 2026-09-11) — 2 dieu kien deu kich hoat CUNG 1
#: check_type nay.
BABELDOC_DROP_REPORT_INCOMPLETE_CHECK = "babeldoc_drop_report_incomplete"

#: BL-04 — doi chieu 1 CHIEU (F5): so lan xuat hien sentinel tren stdout
#: NHIEU HON so record `drop` co cau truc trong sidecar (nguoc lai la binh
#: thuong — `EvictQueue` tu vut bot log khi day, khong phai loi).
BABELDOC_DROP_REPORT_MISMATCH_CHECK = "babeldoc_drop_report_mismatch"

_SEVERITY_BY_CHECK: dict[str, str] = {
    "overlap": "critical",
    "text_over_drawing": "critical",
    "text_over_image": "critical",
    "rotated_text_prescan": "blocker",
    "entity_loss": "blocker",
    ROTATED_OVERLAY_FLAG_CHECK: "blocker",
    ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK: "blocker",
    # BL-04 (Architecture.md 6.22.6 F6) — nguon su that DUY NHAT cho severity
    # cua 4 check_type nay; `job_orchestrator` phai TRA DICT nay, khong tu
    # dien chuoi severity (2 nguon su that cho cung 1 anh xa la cach chac
    # chan de chung lech nhau).
    BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK: "critical",
    BABELDOC_DROP_REPORT_UNAVAILABLE_CHECK: "major",
    BABELDOC_DROP_REPORT_INCOMPLETE_CHECK: "major",
    BABELDOC_DROP_REPORT_MISMATCH_CHECK: "minor",
}

_SEVERITY_WEIGHT: dict[str, int] = {"blocker": 3, "critical": 2, "major": 1, "minor": 0}

#: 4 loai thuc the so+don vi theo dung spec P0.1-e (Architecture.md U4):
#: nhiet do, khoi luong/the tich, thoi gian, phan so.
_ENTITY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\d+\s?°C"),
    re.compile(r"\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b", re.IGNORECASE),
    re.compile(r"\d+\s?(?:phút|phut|min|giờ|gio|h)\b", re.IGNORECASE),
    re.compile(r"\d+/\d+"),
]


@dataclass
class LayoutQaFindingData:
    """Plan-level mirror cua `src.models.layout_qa.LayoutQaFinding` (SQLModel
    table) — tach rieng vi ham check chay truoc khi biet `job_id`/`run_label`,
    giong pattern `OverflowEntry` trong `src/postprocess/font_shrink.py`."""

    page_number: int
    check_type: str
    severity: str
    detail: dict[str, Any]


@dataclass
class PageQueueEntry:
    """1 trang trong hang doi review, xep hang theo `severity_score` giam dan."""

    page_number: int
    severity_score: int
    findings: list[LayoutQaFindingData]


@dataclass
class LayoutQaReport:
    findings: list[LayoutQaFindingData]
    page_queue: list[PageQueueEntry]
    source_checked: bool
    # True khi (d)/(e) da chay (tuc source_pdf_path duoc truyen vao).


def _rect_area(rect: "fitz.Rect") -> float:
    return max(0.0, rect.x1 - rect.x0) * max(0.0, rect.y1 - rect.y0)


def _text_blocks(page: "fitz.Page") -> list[tuple]:
    """`get_text("blocks")` loc con lai block type 0 (text) — bo block anh."""
    return [b for b in page.get_text("blocks") if b[6] == 0]


def _check_overlap(page: "fitz.Page", page_number: int) -> list[LayoutQaFindingData]:
    """(a) DoD-UX-01/UX-A — cap block text giao nhau > 5% dien tich block nho
    hon. Cung logic + nguong voi script T3-a da chay that."""
    blocks = _text_blocks(page)
    findings: list[LayoutQaFindingData] = []
    for i in range(len(blocks)):
        rect_a = fitz.Rect(blocks[i][:4])
        area_a = _rect_area(rect_a)
        if area_a <= 0:
            continue
        for j in range(i + 1, len(blocks)):
            rect_b = fitz.Rect(blocks[j][:4])
            area_b = _rect_area(rect_b)
            if area_b <= 0:
                continue
            inter_area = _rect_area(rect_a & rect_b)
            if inter_area <= 0:
                continue
            ratio = inter_area / min(area_a, area_b)
            if ratio > OVERLAP_AREA_RATIO_THRESHOLD:
                findings.append(
                    LayoutQaFindingData(
                        page_number=page_number,
                        check_type="overlap",
                        severity=_SEVERITY_BY_CHECK["overlap"],
                        detail={
                            "block_a_bbox": list(rect_a),
                            "block_b_bbox": list(rect_b),
                            "block_a_text": blocks[i][4].strip()[:200],
                            "block_b_text": blocks[j][4].strip()[:200],
                            "overlap_ratio": round(ratio, 4),
                        },
                    )
                )
    return findings


def _check_text_over_drawings(page: "fitz.Page", page_number: int) -> list[LayoutQaFindingData]:
    """(b) DoD-UX-03/UX-B — text vuot qua duong vien ve. Chi xet drawing co
    net ve (stroke, `"s"` trong `type`) lam duong vien; text block giao
    KHONG TRON VEN voi vien (tuc mot phan nam ngoai) va phan giao > 5% dien
    tich block -> flag "text tran qua vien"."""
    drawings = page.get_drawings()
    text_blocks = _text_blocks(page)
    findings: list[LayoutQaFindingData] = []
    for drawing in drawings:
        if "s" not in (drawing.get("type") or ""):
            continue
        rect = drawing.get("rect")
        if rect is None:
            continue
        border_rect = fitz.Rect(rect)
        if _rect_area(border_rect) <= 0:
            continue
        for block in text_blocks:
            text_rect = fitz.Rect(block[:4])
            text_area = _rect_area(text_rect)
            if text_area <= 0:
                continue
            inter_area = _rect_area(text_rect & border_rect)
            if inter_area <= 0:
                continue
            fully_inside = inter_area >= text_area - 1e-6
            ratio = inter_area / text_area
            if not fully_inside and ratio > OVERLAP_AREA_RATIO_THRESHOLD:
                findings.append(
                    LayoutQaFindingData(
                        page_number=page_number,
                        check_type="text_over_drawing",
                        severity=_SEVERITY_BY_CHECK["text_over_drawing"],
                        detail={
                            "text_bbox": list(text_rect),
                            "border_bbox": list(border_rect),
                            "text": block[4].strip()[:200],
                            "inside_ratio": round(ratio, 4),
                        },
                    )
                )
    return findings


def _check_text_over_images(page: "fitz.Page", page_number: int) -> list[LayoutQaFindingData]:
    """(c) UX-B — text de len anh, dung `page.get_image_rects()` dung theo
    spec (khong dung `get_image_info()` du gon hon, de bam sat script T3)."""
    text_blocks = _text_blocks(page)
    findings: list[LayoutQaFindingData] = []
    for image in page.get_images(full=True):
        xref = image[0]
        for image_rect in page.get_image_rects(xref):
            img_rect = fitz.Rect(image_rect)
            img_area = _rect_area(img_rect)
            if img_area <= 0:
                continue
            for block in text_blocks:
                text_rect = fitz.Rect(block[:4])
                text_area = _rect_area(text_rect)
                if text_area <= 0:
                    continue
                inter_area = _rect_area(text_rect & img_rect)
                if inter_area <= 0:
                    continue
                ratio = inter_area / text_area
                if ratio > OVERLAP_AREA_RATIO_THRESHOLD:
                    findings.append(
                        LayoutQaFindingData(
                            page_number=page_number,
                            check_type="text_over_image",
                            severity=_SEVERITY_BY_CHECK["text_over_image"],
                            detail={
                                "text_bbox": list(text_rect),
                                "image_bbox": list(img_rect),
                                "text": block[4].strip()[:200],
                                "overlap_ratio": round(ratio, 4),
                            },
                        )
                    )
    return findings


def line_angle_deg(direction: tuple[float, float]) -> float:
    """Goc (deg) cua 1 `line["dir"]` PyMuPDF. Public — tai su dung boi
    `src/postprocess/rotated_text_overlay.py` (Architecture.md U4/P1.1, R6-01:
    "TAI SU DUNG logic detect da co o check (d), KHONG viet lai tu dau")."""
    dx, dy = direction
    return math.degrees(math.atan2(dy, dx))


def is_rotated(angle_deg: float, tolerance_deg: float = ROTATION_TOLERANCE_DEG) -> bool:
    """True neu goc lech ca 0 deg lan 90 deg qua `tolerance_deg` — dung dung
    dieu kien babeldoc dung de vut ky tu (Architecture.md T-01). Public — tai
    su dung boi `src/postprocess/rotated_text_overlay.py` (U4/P1.1)."""
    normalized = angle_deg % 180
    dist_to_0 = min(normalized, 180 - normalized)
    dist_to_90 = abs(normalized - 90)
    return dist_to_0 > tolerance_deg and dist_to_90 > tolerance_deg


# Aliases nguyen ten cu cho code noi bo module nay (khong doi loi goi ben duoi).
_line_angle_deg = line_angle_deg
_is_rotated = is_rotated


def _check_rotated_text_prescan(
    source_page: "fitz.Page", page_number: int
) -> list[LayoutQaFindingData]:
    """(d) G1d — pre-scan chu xoay tren file GOC. Day la PHU LUC cho QA khi
    UX-C chua duoc fix (P1.1 chua xong) — KHONG phai san pham giao nguoi
    doc, chi la canh bao truoc + text day du de QA doi chieu (Architecture.md
    U4/P1.1 va G1d trong T6)."""
    findings: list[LayoutQaFindingData] = []
    text_dict = source_page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            angle = _line_angle_deg(line["dir"])
            if not _is_rotated(angle):
                continue
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if not text.strip():
                continue
            findings.append(
                LayoutQaFindingData(
                    page_number=page_number,
                    check_type="rotated_text_prescan",
                    severity=_SEVERITY_BY_CHECK["rotated_text_prescan"],
                    detail={
                        "dir": list(line["dir"]),
                        "angle_deg": round(angle, 3),
                        "bbox": list(line["bbox"]),
                        "text": text,
                    },
                )
            )
    return findings


def _find_entities(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _ENTITY_PATTERNS:
        found.extend(match.group(0) for match in pattern.finditer(text))
    return found


def _best_matching_block(
    source_rect: "fitz.Rect", translated_blocks: list[tuple]
) -> tuple[tuple | None, float]:
    """Tim block dich co IoU bbox lon nhat voi `source_rect`. Tra ve
    `(None, 0.0)` neu khong block nao dat `_ENTITY_MATCH_MIN_IOU`."""
    best_block: tuple | None = None
    best_iou = 0.0
    for block in translated_blocks:
        rect = fitz.Rect(block[:4])
        inter_area = _rect_area(source_rect & rect)
        union_area = _rect_area(source_rect) + _rect_area(rect) - inter_area
        if union_area <= 0:
            continue
        iou = inter_area / union_area
        if iou > best_iou:
            best_iou = iou
            best_block = block
    if best_iou < _ENTITY_MATCH_MIN_IOU:
        return None, best_iou
    return best_block, best_iou


def _check_entity_preservation(
    source_page: "fitz.Page", translated_page: "fitz.Page", page_number: int
) -> list[LayoutQaFindingData]:
    """(e) DoD-UX-02 — bao toan thuc the so+don vi. HEURISTIC, khong phai NLP
    entity-matching chinh xac 100%: match block theo vi tri bbox (IoU), roi
    kiem tra chuoi con `in` — co the co false positive (vd don vi bi doi
    format nhe, "10 phút" -> "10 min") va false negative (block bi tach/gop
    lai khac so voi goc). Muc dich la CO BAO cho QA soi, khong phai ket luan
    cuoi cung."""
    findings: list[LayoutQaFindingData] = []
    source_blocks = _text_blocks(source_page)
    translated_blocks = _text_blocks(translated_page)
    for block in source_blocks:
        entities = _find_entities(block[4])
        if not entities:
            continue
        source_rect = fitz.Rect(block[:4])
        match, iou = _best_matching_block(source_rect, translated_blocks)
        translated_text = match[4] if match is not None else ""
        missing = [entity for entity in entities if entity not in translated_text]
        if missing:
            findings.append(
                LayoutQaFindingData(
                    page_number=page_number,
                    check_type="entity_loss",
                    severity=_SEVERITY_BY_CHECK["entity_loss"],
                    detail={
                        "source_bbox": list(source_rect),
                        "source_text": block[4].strip()[:300],
                        "matched_translated_bbox": (
                            list(fitz.Rect(match[:4])) if match is not None else None
                        ),
                        "matched_translated_text": (
                            translated_text.strip()[:300] if match is not None else None
                        ),
                        "match_iou": round(iou, 4),
                        "expected_entities": entities,
                        "missing_entities": missing,
                    },
                )
            )
    return findings


def run_layout_qa_gate(
    translated_pdf_path: Path, source_pdf_path: Path | None = None
) -> LayoutQaReport:
    """Chay ca 5 kiem tra tren `translated_pdf_path` (+ `source_pdf_path` neu
    co) va tra ve hang doi review theo trang, xep hang muc nghiem trong.

    (a)/(b)/(c) chi can file dich, chay tren MOI trang cua no. (d)/(e) can
    file goc — bo qua (khong loi) neu `source_pdf_path` la None; khi co, chay
    theo tung cap trang GOC/DICH cung chi so (gia dinh so trang giu nguyen
    giua goc va dich — dung voi babeldoc/pdf2zh vi ca hai deu dich 1-doi-1
    trang, khong chen/xoa trang).
    """
    findings: list[LayoutQaFindingData] = []

    translated_doc = fitz.open(translated_pdf_path)
    try:
        for index, page in enumerate(translated_doc):
            page_number = index + 1
            findings.extend(_check_overlap(page, page_number))
            findings.extend(_check_text_over_drawings(page, page_number))
            findings.extend(_check_text_over_images(page, page_number))
        translated_page_count = len(translated_doc)
    finally:
        translated_doc.close()

    source_checked = source_pdf_path is not None
    if source_pdf_path is not None:
        source_doc = fitz.open(source_pdf_path)
        translated_doc = fitz.open(translated_pdf_path)
        try:
            for index in range(len(source_doc)):
                page_number = index + 1
                source_page = source_doc[index]
                findings.extend(_check_rotated_text_prescan(source_page, page_number))
                if index < translated_page_count:
                    findings.extend(
                        _check_entity_preservation(source_page, translated_doc[index], page_number)
                    )
        finally:
            source_doc.close()
            translated_doc.close()

    page_queue = _build_page_queue(findings)
    return LayoutQaReport(findings=findings, page_queue=page_queue, source_checked=source_checked)


def _build_page_queue(findings: list[LayoutQaFindingData]) -> list[PageQueueEntry]:
    """Gom finding theo trang, tinh `severity_score` (tong trong so muc
    nghiem trong), sap xep GIAM DAN — dung yeu cau "hang doi review theo
    trang, xep hang muc nghiem trong" (khong phai 1 ket qua pass/fail)."""
    by_page: dict[int, list[LayoutQaFindingData]] = defaultdict(list)
    for finding in findings:
        by_page[finding.page_number].append(finding)

    entries: list[PageQueueEntry] = []
    for page_number, page_findings in by_page.items():
        score = sum(_SEVERITY_WEIGHT.get(f.severity, 0) for f in page_findings)
        page_findings.sort(key=lambda f: -_SEVERITY_WEIGHT.get(f.severity, 0))
        entries.append(
            PageQueueEntry(page_number=page_number, severity_score=score, findings=page_findings)
        )
    entries.sort(key=lambda e: (-e.severity_score, e.page_number))
    return entries


async def persist_findings(
    session: Any,
    findings: list[LayoutQaFindingData],
    *,
    job_id: str | None = None,
    run_label: str | None = None,
    source_file: str | None = None,
) -> None:
    """Ghi `findings` vao bang `layout_qa_findings` de so sanh giua cac lan
    chay (dieu kien bat buoc cho P0.2 A/B — Architecture.md U4/P0.1).
    `session` la 1 `AsyncSession` (SQLModel/SQLAlchemy) da mo san — ham nay
    KHONG tu mo/dong session, giong convention cac service khac trong
    `src/services/` khong tu quan ly session cua rieng minh.
    """
    from src.models.layout_qa import LayoutQaFinding

    for finding in findings:
        session.add(
            LayoutQaFinding(
                job_id=job_id,
                run_label=run_label,
                source_file=source_file,
                page_number=finding.page_number,
                check_type=finding.check_type,
                severity=finding.severity,
                detail=json.dumps(finding.detail, ensure_ascii=False),
            )
        )
    await session.commit()
