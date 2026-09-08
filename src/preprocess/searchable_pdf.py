"""OCR-to-translate bridge for `pdf_scan` jobs (Bug #5 fix, Architecture.md 6.10).

Neither MinerU nor pdf2zh can build this on their own (verified against real
source, Architecture.md 6.10.1/6.10.2, sources S10-S16): MinerU does not emit
a searchable/text-layer PDF among its output files, and pdf2zh has no OCR
path at all — it only reads text objects already present in the content
stream (pdfminer.six). So BB-Translation builds the bridge itself, on a copy
of the original scan, per page:

1. Whiteout the original glyph pixels under every OCR'd text span's bbox.
2. Write that span's OCR text back at the same bbox as an INVISIBLE text
   object (`render_mode=3`) — real text objects pdfminer.six (and therefore
   pdf2zh) reads normally (verified experimentally, Architecture.md 6.10.3 T1),
   but nothing a human sees on top of the (now blanked) scan image.

The result is a PDF pdf2zh treats exactly like a born-digital one. Images,
tables, and figures are left untouched — only text-span bboxes are painted
over, so anything MinerU classified as non-text keeps its original pixels.

Defense-in-depth (bug thuc te 2026-09-05, "How Baking Works" — verify song
bang PyMuPDF tren file output that): mot file duoc `file_router.py` phan
loai la `pdf_scan` van co the co NHUNG TRANG rieng le da co text object that
(vd router phan loai sai o muc CA FILE, hoac 1 vai trang trong 1 file scan
that su lai co lop text an tu truoc). Neu buoc 1 (whiteout) chi xoa PIXEL
ma khong xoa text object goc, va buoc 2 (chen text OCR) van chen them 1 lop
INVISIBLE text nua len tren, thi trang do se co 2 lop text object cung ton
tai — pdfminer.six (va do do babeldoc/pdf2zh) doc ca 2 lop, dich va ve ca
hai (quan sat that: 21/25 trang co 2 ho font Viet chong nhau, moi doan van
xuat hien 2 lan lech vi tri/co chu). `build_searchable_pdf` vi vay BO QUA
HOAN TOAN buoc whiteout+chen OCR cho bat ky trang nao DA CO text object that
(`page.get_text().strip()` khong rong) — giu nguyen lop text goc cua trang
do, khong phu thuoc vao file_router.py co phan loai dung hay khong.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from src.utils.pdf_coords import insert_text_origin_fix

logger = logging.getLogger(__name__)

_TEXT_SPAN_TYPES = {"text", "inline_equation"}
_COORD_TOLERANCE_PT = 2.0


class SearchablePdfError(RuntimeError):
    """The bridge could not be built usably — the job MUST fail here, never
    fall back to the original scan (that fallback is exactly how Bug #5
    happened: a silent "translate the file with no text layer" path)."""


@dataclass(frozen=True)
class SearchablePdfResult:
    path: Path
    span_count: int
    page_count: int
    extracted_chars: int


def build_searchable_pdf(
    source_pdf: Path,
    middle_json_path: Path,
    output_path: Path,
    *,
    whiteout_padding: float = 1.5,
    font_name: str = "helv",
    min_font_size: float = 1.0,
) -> SearchablePdfResult:
    middle: dict[str, Any] = json.loads(middle_json_path.read_text(encoding="utf-8"))
    pages = middle.get("pdf_info") or []
    if not pages:
        raise SearchablePdfError(f"middle.json khong co pdf_info: {middle_json_path}")

    span_count = 0

    with fitz.open(source_pdf) as doc:
        for page_info in pages:
            page_idx = page_info.get("page_idx")
            if page_idx is None or page_idx >= doc.page_count:
                logger.warning(
                    "middle.json page_idx=%s ngoai pham vi (doc co %d trang), bo qua",
                    page_idx,
                    doc.page_count,
                )
                continue

            page = doc[page_idx]

            # Defense-in-depth — xem ghi chu trong module docstring. Trang
            # da co text object that thi GIU NGUYEN, khong whiteout+chen OCR
            # de len, bat ke file_router.py co phan loai file nay dung hay
            # khong.
            if page.get_text().strip():
                logger.info(
                    "Trang %d da co text object that (khong phai scan) — "
                    "bo qua chen lop OCR de tranh nhan doi noi dung",
                    page_idx,
                )
                continue

            spans = _collect_text_spans(page_info)
            if not spans:
                continue

            _check_coordinate_system(page, page_info, page_idx)

            # Two passes: whiteout every span first, THEN write text — doing
            # both per-span would let one span's whiteout rect paint over the
            # invisible text object of a span drawn just before it.
            for _, bbox in spans:
                x0, y0, x1, y1 = bbox
                page.draw_rect(
                    fitz.Rect(
                        x0 - whiteout_padding,
                        y0 - whiteout_padding,
                        x1 + whiteout_padding,
                        y1 + whiteout_padding,
                    ),
                    color=None,
                    fill=(1, 1, 1),
                    overlay=True,
                )

            for content, bbox in spans:
                if _insert_invisible_text(page, content, bbox, font_name, min_font_size):
                    span_count += 1

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)

    extracted_chars = _count_extracted_chars(output_path)
    if extracted_chars == 0:
        raise SearchablePdfError(
            "Cau noi OCR khong tao ra text layer nao — khong the dich file scan nay"
        )

    with fitz.open(output_path) as result_doc:
        page_count = result_doc.page_count

    return SearchablePdfResult(
        path=output_path,
        span_count=span_count,
        page_count=page_count,
        extracted_chars=extracted_chars,
    )


def _collect_text_spans(
    page_info: dict[str, Any],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """`preproc_blocks` only — deliberately NOT `discarded_blocks` (headers,
    footers, watermarks MinerU already flagged as not-content). Whiting those
    out would erase page furniture that was never meant to be translated.
    """
    spans: list[tuple[str, tuple[float, float, float, float]]] = []

    def _walk_block(block: dict[str, Any]) -> None:
        for line in block.get("lines", []) or []:
            for span in line.get("spans", []) or []:
                span_type = span.get("type")
                content = span.get("content")
                if span_type not in _TEXT_SPAN_TYPES:
                    continue
                if not isinstance(content, str) or not content.strip():
                    continue
                bbox = span.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                try:
                    x0, y0, x1, y1 = (float(v) for v in bbox)
                except (TypeError, ValueError):
                    continue
                if x1 <= x0 or y1 <= y0:
                    continue
                spans.append((content, (x0, y0, x1, y1)))
        for nested in block.get("blocks", []) or []:
            _walk_block(nested)

    for block in page_info.get("preproc_blocks", []) or []:
        _walk_block(block)

    return spans


def _check_coordinate_system(page: "fitz.Page", page_info: dict[str, Any], page_idx: int) -> None:
    """S17: `middle.json` bbox coordinates are in the same PDF-point,
    top-left-origin space as PyMuPDF's `page.rect` — no DPI conversion
    needed, PROVIDED the page sizes actually agree. A mismatch means the
    bbox coordinates would silently land in the wrong place — the exact kind
    of quiet-success-with-wrong-output Protocol 5 exists to catch, so this
    fails loudly instead of guessing a scale factor.
    """
    page_size = page_info.get("page_size")
    if not page_size or len(page_size) != 2:
        return
    mid_w, mid_h = page_size
    if (
        abs(mid_w - page.rect.width) > _COORD_TOLERANCE_PT
        or abs(mid_h - page.rect.height) > _COORD_TOLERANCE_PT
    ):
        raise SearchablePdfError(
            f"He toa do lech qua {_COORD_TOLERANCE_PT}pt o trang {page_idx}: "
            f"middle.json page_size={page_size} vs PyMuPDF page.rect="
            f"({page.rect.width}, {page.rect.height})"
        )


def _insert_invisible_text(
    page: "fitz.Page",
    content: str,
    bbox: tuple[float, float, float, float],
    font_name: str,
    min_font_size: float,
) -> bool:
    x0, y0, x1, y1 = bbox
    h = y1 - y0
    font_size = max(h * 0.85, min_font_size)
    text_length = fitz.get_text_length(content, fontname=font_name, fontsize=font_size)
    if text_length > 0:
        font_size = max(font_size * min(1.0, (x1 - x0) / text_length), min_font_size)

    try:
        # Bug #8 round-2 (docs/review-report.md, issue non-blocking #2): same
        # MediaBox/CropBox `page.insert_text()` coordinate bug as
        # `font_shrink.py::_redraw_span` — `(x0, y1 - h * 0.15)` is page-space
        # (docstring above, S17), the space `insert_text_origin_fix` corrects
        # for before handing a point to `page.insert_text()`.
        origin = insert_text_origin_fix(page, fitz.Point(x0, y1 - h * 0.15))
        page.insert_text(
            origin,
            content,
            fontname=font_name,
            fontsize=font_size,
            render_mode=3,  # invisible — real text object, nothing painted (S15, S18)
        )
    except Exception:  # noqa: BLE001 — e.g. char outside the base-14 font encoding
        logger.warning("Bo qua 1 span khong ghi duoc text layer: %r", content[:50])
        return False
    return True


def _count_extracted_chars(output_path: Path) -> int:
    with fitz.open(output_path) as doc:
        return sum(len(page.get_text().strip()) for page in doc)
