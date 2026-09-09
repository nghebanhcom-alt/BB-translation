"""Overlay rotated text babeldoc drops back onto its merged output
(Architecture.md "Final Decision: Babeldoc Layout Bug Fix Roadmap", U3/U4
P1.1 -- G1e).

Root cause (V-1, verified against installed babeldoc 0.6.4 source,
Architecture.md U1): `PdfCharacter` (`IL/il_version_1.py:627-663`) has no
rotation field at all, and `IL/backend/pdf_creater.py:111-120` only ever
emits an axis-aligned or vertical `Tm` matrix -- babeldoc's backend cannot
render an arbitrary rotation angle. `il_creater.py:968-974` silently drops
(`return`, no log -- E-2) every character whose line angle falls outside
0/90 deg +-0.1 deg. That is UX-C content-loss, not a cosmetic issue: this
module re-draws that lost text back onto the page babeldoc already produced,
using PyMuPDF's `insert_text(morph=...)`, spiked and verified working in
Architecture.md U3 (`dir` read back after drawing matched the source block's
`dir` exactly).

Data lineage (R6-01, Architecture.md U4/P1.1 -- must hold exactly):

    rotated_blocks <- source.pdf (scan with PyMuPDF, `line["dir"]` outside
        0/90 deg +-0.1 deg -- SAME threshold/detector as
        `src/services/layout_qa.py` check (d); reused via
        `line_angle_deg()`/`is_rotated()`, NOT re-implemented)
        --> translated_blocks <- the app's OWN LLM provider
        (`TranslationProvider.translate()`, injected by the caller --
        NEVER babeldoc/pdf2zh CLI for this step, per Architecture.md U4/P1.1
        explicit instruction)
        --> overlay onto babeldoc_output.pdf via
        `page.insert_text(pivot, text, morph=(pivot, Matrix(angle)), ...)`

`overlay_rotated_text()` reads `translated_blocks` (the dict returned by
`translate_rotated_blocks()`) to draw -- it never re-reads `source_pdf_path`
for content a second time. This is the exact discipline Protocol 6 (Bug #5)
exists to enforce: OCR output and translation output both individually
correct is not enough if nothing hands the first's result to the second.

Fit policy (U5/U7-E1, "khối chữ xoay" row -- Tech Lead's proposal, treated as
PM-approved for the purpose of implementing this roadmap): shrink font down
to `MIN_FONT_SCALE` (70%) at most, NEVER lower. If translated text still does
not fit the original bbox at 70%, do NOT overlay -- leave babeldoc's blank
space alone (broken/overlapping text overlaid on top would be worse) and
FLAG the block via the SAME `layout_qa_findings` mechanism P0.1 already
writes to (`ROTATED_OVERLAY_FLAG_CHECK`), for QA to review by hand.

RK-3 (Architecture.md U6): the caller MUST invoke `overlay_rotated_text()`
AFTER `merge_chunk_pdfs()` and BEFORE `compress_pdf_images()` -- see
`JobOrchestrator.run_job()` Step 8 (`src/core/job_orchestrator.py`). Doing it
after compress would mean recompressing the newly drawn text's containing
image region is a no-op (text is drawn as vector glyphs, not raster), but
doing it BEFORE merge would mean drawing on per-chunk files that then get
re-paginated/renumbered by the merge step -- merge must go first so page
numbers here match the final output.

Grouping assumption (Giả định tự chọn -- no formal spec exists for this,
flagged explicitly per this task's brief instead of silently guessing):
babeldoc's own paragraph-to-line split means a single rotated PARAGRAPH (the
Architecture.md U3 example: "16 dòng nghiêng -11° ở trang 67") shows up in
PyMuPDF's `get_text("dict")` as many separate 1-line blocks, each shifted
along the paragraph's own "next line" axis. `group_rotated_lines()` clusters
consecutive same-angle lines into one logical block using a distance
heuristic (`_PARAGRAPH_GAP_FONT_MULTIPLE`) chosen so a genuine multi-line
paragraph (tightly packed, `rotated_text_p67_source.pdf`) merges into one
block while scattered same-angle labels on a rotated chart/table
(`rotated_chart_p15_source.pdf`) do NOT get concatenated into one nonsense
paragraph. This has not been validated against a wide sample -- it is this
increment's spike answer for the risk Architecture.md U3 explicitly flagged
as unresolved ("insert_text KHÔNG tự xuống dòng... phải tự tách dòng").
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from src.services.layout_qa import (
    ROTATED_OVERLAY_FLAG_CHECK,
    LayoutQaFindingData,
    is_rotated,
    line_angle_deg,
)
from src.services.translation import TranslationProvider
from src.utils.pdf_coords import insert_text_origin_fix

logger = logging.getLogger(__name__)

#: DoD-UX-03 / U5/U7-E1 policy floor -- shrink font at most to this ratio of
#: the ORIGINAL source font size, never lower. Below this, babeldoc's own
#: `min_scale` behaviour (down to 0.1, Architecture.md E-1) is exactly the
#: "cố nhét chữ bằng mọi giá" failure mode this policy exists to avoid.
MIN_FONT_SCALE = 0.70

#: Same alias `src/postprocess/font_shrink.py` uses for the same font FILE
#: (`Settings.noto_font_path`) -- intentionally reused so PyMuPDF resolves
#: to the same embedded font object instead of embedding it twice in the
#: same output document.
_NOTO_FONT_ALIAS = "notovi"

#: Grouping heuristic (see module docstring "Giả định tự chọn"): two
#: consecutive same-angle-bucket lines merge into one block only if the gap
#: between them, projected onto the block's own "next line" axis, is at
#: most this multiple of the larger line's font size.
_PARAGRAPH_GAP_FONT_MULTIPLE = 1.8

#: Angle bucket width (deg) for grouping lines into the same rotation family
#: before the distance-based merge above is applied.
#:
#: Known risk (non-blocking, review-report.md mục 6.1): a hard 1° bucket can
#: split ONE real paragraph into two blocks if OCR/babeldoc measures adjacent
#: lines' angles on opposite sides of a bucket boundary (e.g. 10.4° and
#: 11.6° land in different buckets despite being the same rotated paragraph).
#: Not observed on the two fixtures backing this module's tests; revisit if a
#: real QA sample shows a paragraph split across two overlay blocks.
_ANGLE_GROUP_TOLERANCE_DEG = 1.0

#: Approximate leading (line-height / font-size) used both to estimate how
#: much vertical room the ORIGINAL block occupied and to lay out our own
#: word-wrapped replacement lines. Matches common single-spaced body text.
_LINE_HEIGHT_FACTOR = 1.2

#: Font-size search step used by `fit_translated_block()`'s scale search.
_FIT_SCALE_STEP = 0.02


@dataclass
class RotatedLine:
    """1 dòng chữ xoay đọc trực tiếp từ `page.get_text("dict")`."""

    bbox: tuple[float, float, float, float]
    dir: tuple[float, float]
    angle_deg: float
    text: str
    font_size: float
    origin: tuple[float, float]


@dataclass
class RotatedBlock:
    """1 nhóm dòng xoay cùng góc, gộp lại thành 1 đoạn văn để dịch + overlay
    như MỘT khối (Architecture.md U3: "16 dòng nghiêng -11° ở trang 67" là
    một khối duy nhất, không phải 16 khối rời)."""

    page_number: int  # 1-indexed, khớp quy ước src/services/layout_qa.py
    lines: list[RotatedLine]

    @property
    def angle_deg(self) -> float:
        return self.lines[0].angle_deg

    @property
    def direction(self) -> tuple[float, float]:
        return self.lines[0].dir

    @property
    def source_text(self) -> str:
        return " ".join(line.text.strip() for line in self.lines if line.text.strip())

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        x0 = min(line.bbox[0] for line in self.lines)
        y0 = min(line.bbox[1] for line in self.lines)
        x1 = max(line.bbox[2] for line in self.lines)
        y1 = max(line.bbox[3] for line in self.lines)
        return (x0, y0, x1, y1)

    @property
    def avg_font_size(self) -> float:
        sizes = [line.font_size for line in self.lines if line.font_size > 0]
        return sum(sizes) / len(sizes) if sizes else 11.0

    @property
    def pivot(self) -> tuple[float, float]:
        # Rotate around the FIRST line's own baseline start point -- matches
        # the Architecture.md U3 spike (pivot at the text's own origin).
        return self.lines[0].origin


@dataclass
class FitResult:
    fits: bool
    scale: float
    font_size: float
    wrapped_lines: list[str]


@dataclass
class OverlayResult:
    """Kết quả 1 lần chạy `overlay_rotated_text()` trên 1 file PDF."""

    findings: list[LayoutQaFindingData]
    overlaid_block_count: int
    flagged_block_count: int


def _line_font_size(line: dict) -> float:
    spans = line.get("spans", [])
    sizes = [s.get("size", 0.0) for s in spans if s.get("size")]
    return sum(sizes) / len(sizes) if sizes else 0.0


def _line_origin(line: dict) -> tuple[float, float]:
    spans = line.get("spans", [])
    if spans and "origin" in spans[0]:
        return tuple(spans[0]["origin"])
    x0, y0, _x1, _y1 = line["bbox"]
    return (x0, y0)


def scan_rotated_lines(page: fitz.Page) -> list[RotatedLine]:
    """Quét 1 trang PyMuPDF, trả về mọi dòng chữ xoay -- TÁI SỬ DỤNG đúng
    logic/ngưỡng của `layout_qa._check_rotated_text_prescan` (R6-01, không
    viết lại từ đầu) qua `line_angle_deg()`/`is_rotated()`."""
    lines: list[RotatedLine] = []
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            angle = line_angle_deg(line["dir"])
            if not is_rotated(angle):
                continue
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if not text.strip():
                continue
            lines.append(
                RotatedLine(
                    bbox=tuple(line["bbox"]),
                    dir=tuple(line["dir"]),
                    angle_deg=angle,
                    text=text,
                    font_size=_line_font_size(line) or 11.0,
                    origin=_line_origin(line),
                )
            )
    return lines


def _perpendicular_projection(line: RotatedLine, direction: tuple[float, float]) -> float:
    """Chiếu tâm bbox của `line` lên trục vuông góc với `direction` -- dùng
    làm trục "dòng kế tiếp" để sắp thứ tự/gộp nhóm (xem "Giả định tự chọn"
    trong module docstring)."""
    dx, dy = direction
    nx, ny = -dy, dx
    cx = (line.bbox[0] + line.bbox[2]) / 2
    cy = (line.bbox[1] + line.bbox[3]) / 2
    return cx * nx + cy * ny


def group_rotated_lines(lines: list[RotatedLine], page_number: int) -> list[RotatedBlock]:
    """Gộp các dòng xoay liên tiếp, cùng góc, thành 1 `RotatedBlock` (đoạn
    văn) để dịch + overlay như MỘT khối. Xem "Giả định tự chọn" trong module
    docstring cho lý do chọn `_PARAGRAPH_GAP_FONT_MULTIPLE`."""
    if not lines:
        return []

    buckets: dict[float, list[RotatedLine]] = {}
    for line in lines:
        bucket_key = round(line.angle_deg / _ANGLE_GROUP_TOLERANCE_DEG) * _ANGLE_GROUP_TOLERANCE_DEG
        buckets.setdefault(bucket_key, []).append(line)

    blocks: list[RotatedBlock] = []
    for bucket_lines in buckets.values():
        direction = bucket_lines[0].dir
        ordered = sorted(bucket_lines, key=lambda ln: _perpendicular_projection(ln, direction))

        current: list[RotatedLine] = [ordered[0]]
        prev_proj = _perpendicular_projection(ordered[0], direction)
        for line in ordered[1:]:
            proj = _perpendicular_projection(line, direction)
            gap = proj - prev_proj
            threshold = _PARAGRAPH_GAP_FONT_MULTIPLE * max(line.font_size, current[-1].font_size)
            if gap <= threshold:
                current.append(line)
            else:
                blocks.append(RotatedBlock(page_number=page_number, lines=current))
                current = [line]
            prev_proj = proj
        blocks.append(RotatedBlock(page_number=page_number, lines=current))

    return blocks


async def translate_rotated_blocks(
    blocks: list[RotatedBlock],
    provider: TranslationProvider,
    glossary_prompt: str,
    source_lang: str = "en",
    target_lang: str = "vi",
) -> dict[int, str]:
    """R6-02 data lineage: mỗi giá trị trả về BẮT NGUỒN TỪ kết quả gọi thật
    `provider.translate()` -- KHÔNG đọc lại `source.pdf` lần 2 (đây chính là
    kỷ luật Protocol 6/Bug #5 được ghi trong Architecture.md yêu cầu).

    Trả về dict khoá bằng `id(block)` (không phải index) vì `blocks` có thể
    được lọc/lặp theo thứ tự khác ở caller.
    """
    translations: dict[int, str] = {}
    for block in blocks:
        result = await provider.translate(
            block.source_text, glossary_prompt, source_lang, target_lang
        )
        translations[id(block)] = result.text
    return translations


def _wrap_text(text: str, font: fitz.Font, fontsize: float, max_width: float) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.text_length(candidate, fontsize=fontsize) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _block_extents(block: RotatedBlock) -> tuple[float, float]:
    """Chiếu 4 góc bbox của mỗi dòng lên trục dọc theo hướng chữ (`u`, độ
    rộng khả dụng cho 1 dòng) và trục vuông góc (`n`, tổng chiều cao khả
    dụng của cả khối) -- xấp xỉ kích thước khung GỐC mà bản dịch phải vừa
    vào, dùng chung hướng `u`/`n` với `group_rotated_lines()`."""
    dx, dy = block.direction
    nx, ny = -dy, dx
    us: list[float] = []
    ns: list[float] = []
    for line in block.lines:
        x0, y0, x1, y1 = line.bbox
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            us.append(cx * dx + cy * dy)
            ns.append(cx * nx + cy * ny)
    width = max(us) - min(us)
    height = max(ns) - min(ns)
    return width, height


def fit_translated_block(block: RotatedBlock, translated_text: str, font: fitz.Font) -> FitResult:
    """Tìm scale lớn nhất trong `[MIN_FONT_SCALE, 1.0]` sao cho word-wrap của
    `translated_text` vừa khung gốc (U5/U7-E1 policy). Không vừa dù đã bóp
    tới `MIN_FONT_SCALE` -> trả về `fits=False` để caller FLAG thay vì đè
    chữ vỡ lên trang (chính sách "giữ chỗ trống babeldoc để lại, tốt hơn đè
    chữ vỡ")."""
    base_font_size = block.avg_font_size
    width, height = _block_extents(block)

    scale = 1.0
    while scale >= MIN_FONT_SCALE - 1e-9:
        fontsize = base_font_size * scale
        wrapped = _wrap_text(translated_text, font, fontsize, width)
        needed_height = len(wrapped) * fontsize * _LINE_HEIGHT_FACTOR
        if needed_height <= height + 1e-6:
            return FitResult(fits=True, scale=scale, font_size=fontsize, wrapped_lines=wrapped)
        scale -= _FIT_SCALE_STEP

    fontsize = base_font_size * MIN_FONT_SCALE
    wrapped = _wrap_text(translated_text, font, fontsize, width)
    return FitResult(fits=False, scale=MIN_FONT_SCALE, font_size=fontsize, wrapped_lines=wrapped)


def _draw_block(page: fitz.Page, block: RotatedBlock, fit: FitResult, font_path: str) -> None:
    """Vẽ `fit.wrapped_lines` lên `page`, xoay đúng góc `block.angle_deg`
    quanh pivot của dòng đầu (Architecture.md U3 spike). PyMuPDF's
    `Matrix(angle)` xoay NGƯỢC chiều `atan2`-based `angle_deg` (đã xác nhận ở
    spike U3: `Matrix(11)` cho ra `dir` ứng với góc đo được là -11 deg), nên
    dùng `-block.angle_deg` để khớp đúng góc `line_angle_deg()` đã đo.

    `pivot` is computed in page-space (`block.pivot`, sourced from
    `page.get_text("dict")` — see `RotatedBlock.pivot`), the SAME space
    `src.utils.pdf_coords.insert_text_origin_fix` corrects for before handing
    a point to `page.insert_text()` — Bug #8 round-2 review found this call
    site hits the exact same MediaBox/CropBox `page.insert_text()` coordinate
    bug as `font_shrink.py::_redraw_span` (live-reproduced against
    `tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf`, `docs/review-report.md`
    Bug #8 review, issue Blocking #1). The corrected `pivot` is used for BOTH
    the insertion point and the `morph` rotation anchor, matching how
    `_redraw_span` fixes `origin` once before it flows into its own `morph`
    tuple."""
    dx, dy = block.direction
    nx, ny = -dy, dx
    origin_x, origin_y = block.pivot
    line_height = fit.font_size * _LINE_HEIGHT_FACTOR
    rotation_degrees = -block.angle_deg

    # `block.pivot` (lines[0].origin) is often NOT where the paragraph's real
    # left margin sits -- a first line that is short or carries a typographic
    # indent (verified against rotated_text_p67_source.pdf: line 0
    # "Disaccharide" projects ~77pt further along the reading direction than
    # every other real line's own origin, all of which cluster tightly
    # together) sits further along the reading direction (`dx, dy`) than the
    # body. Extrapolating every wrapped line from that outlier drags the
    # WHOLE translated block that much further along too, eating into the
    # page's margin on every subsequent line -- confirmed to already leave a
    # <6pt margin on the real fixture even before any other change, and to
    # push the last 1-2 wrapped lines' trailing characters off the page (get
    # clipped silently by PyMuPDF) once translated text runs a line or two
    # longer. Anchor along the reading direction at the real block's own left
    # margin (min projection across every real line's own baseline origin)
    # instead, keeping line 0's own row (perpendicular position) unchanged.
    line0_u = origin_x * dx + origin_y * dy
    block_left_u = min(ln.origin[0] * dx + ln.origin[1] * dy for ln in block.lines)
    delta_u = line0_u - block_left_u
    anchor_x = origin_x - delta_u * dx
    anchor_y = origin_y - delta_u * dy

    for i, text in enumerate(fit.wrapped_lines):
        pivot = fitz.Point(anchor_x + nx * line_height * i, anchor_y + ny * line_height * i)
        pivot = insert_text_origin_fix(page, pivot)
        page.insert_text(
            pivot,
            text,
            fontsize=fit.font_size,
            fontname=_NOTO_FONT_ALIAS,
            fontfile=font_path,
            morph=(pivot, fitz.Matrix(rotation_degrees)),
        )


async def overlay_rotated_text(
    *,
    source_pdf_path: Path,
    output_pdf_path: Path,
    provider: TranslationProvider,
    glossary_prompt: str,
    font_path: Path,
    source_lang: str = "en",
    target_lang: str = "vi",
) -> OverlayResult:
    """Entry point cho `JobOrchestrator` (U6/RK-3: gọi hàm này SAU
    `merge_chunk_pdfs()`, TRƯỚC `compress_pdf_images()`, CHỈ khi
    `settings.pdf_translate_engine == "babeldoc"` -- pdf2zh không cần overlay
    này, V-2 đã verify pdf2zh không vứt chữ nghiêng).

    `output_pdf_path` là file babeldoc ĐÃ merge -- bị sửa TẠI CHỖ (cùng
    pattern với `compress_pdf_images()`/`chunk_merge.py`: ghi ra file tạm
    trong cùng thư mục rồi `os.replace()`, không để lộ file dở dang nếu tiến
    trình bị ngắt giữa chừng).

    Nếu `source_pdf_path` không có dòng chữ xoay nào (tài liệu văn xuôi
    thường), hàm no-op và KHÔNG mở/ghi lại `output_pdf_path` -- tránh 1 lần
    resave vô ích trên mọi job babeldoc.
    """
    findings: list[LayoutQaFindingData] = []
    overlaid = 0
    flagged = 0

    source_doc = fitz.open(source_pdf_path)
    try:
        rotated_by_page: dict[int, list[RotatedBlock]] = {}
        for index in range(len(source_doc)):
            page_number = index + 1
            lines = scan_rotated_lines(source_doc[index])
            if not lines:
                continue
            blocks = group_rotated_lines(lines, page_number)
            if blocks:
                rotated_by_page[index] = blocks
    finally:
        source_doc.close()

    if not rotated_by_page:
        return OverlayResult(findings=[], overlaid_block_count=0, flagged_block_count=0)

    font = fitz.Font(fontfile=str(font_path))
    font_path_str = str(font_path)

    output_doc = fitz.open(output_pdf_path)
    try:
        page_count = len(output_doc)
        for index, blocks in rotated_by_page.items():
            if index >= page_count:
                # Merged output has fewer pages than source (shouldn't happen
                # for babeldoc's 1-to-1 page mapping, but do not crash the
                # job over a cosmetic overlay step if it ever does).
                logger.warning(
                    "overlay_rotated_text: source page %s ngoai pham vi output "
                    "(%s trang) -- bo qua",
                    index + 1,
                    page_count,
                )
                continue

            translations = await translate_rotated_blocks(
                blocks, provider, glossary_prompt, source_lang, target_lang
            )

            output_page = output_doc[index]
            for block in blocks:
                translated_text = translations[id(block)]
                fit = fit_translated_block(block, translated_text, font)
                if not fit.fits:
                    flagged += 1
                    findings.append(
                        LayoutQaFindingData(
                            page_number=block.page_number,
                            check_type=ROTATED_OVERLAY_FLAG_CHECK,
                            severity="blocker",
                            detail={
                                "source_bbox": list(block.bbox),
                                "angle_deg": round(block.angle_deg, 3),
                                "source_text": block.source_text[:300],
                                "translated_text": translated_text[:300],
                                "attempted_scale": fit.scale,
                                "reason": (
                                    "khong vua bbox goc du da bop toi MIN_FONT_SCALE "
                                    f"({MIN_FONT_SCALE}) -- GIU NGUYEN cho trong babeldoc "
                                    "de lai, KHONG overlay de len (U5/U7-E1 policy)."
                                ),
                            },
                        )
                    )
                    continue
                _draw_block(output_page, block, fit, font_path_str)
                overlaid += 1

        fd, tmp_name = tempfile.mkstemp(
            dir=str(output_pdf_path.parent),
            prefix=f".{output_pdf_path.stem}-rotoverlay-",
            suffix=".tmp.pdf",
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            output_doc.save(tmp_path, garbage=4, deflate=True)
        finally:
            output_doc.close()
        os.replace(tmp_path, output_pdf_path)
    except Exception:
        if not output_doc.is_closed:
            output_doc.close()
        raise

    return OverlayResult(
        findings=findings, overlaid_block_count=overlaid, flagged_block_count=flagged
    )
