"""Text overflow post-processing (Architecture.md section 6.3, BR-FONT-02/03, US-05).

3-step algorithm applied to every text span on a page:
1. Shrink font size, capped at -20%.
2. If still overflowing, apply horizontal-only condensed scaling to 85%.
3. If still overflowing, leave the text untouched and flag it for user review
   (never truncate/cut text — PRD US-05 step 3).

Implementation note: PyMuPDF has no "resize this span in place" API — a text
span is drawn once into the content stream. To change it we redact the
original glyphs (white-fill over the bbox) and re-insert the text at the same
origin with the new size/matrix.

`font_path` (optional, threaded through from `Settings.noto_font_path` by the
caller) selects which font both measures and redraws the span. When omitted,
this falls back to the PDF base-14 font ("helv") — kept only for callers/tests
that don't care. Production callers MUST pass the real font path: verified
live (2026-09-05) that "helv" silently corrupts Vietnamese characters outside
Latin-1 during `insert_text()` (e.g. "thơm" -> "th·m", the ơ/ư-family glyphs
have no base-14 mapping) and understates real Vietnamese glyph width by
~30-45% in `get_text_length()` (measured: "bánh" at 12pt is 28.9pt wide via
the real Noto font pdf2zh renders with vs. 20.0pt via "helv") — both false-fit
decisions here that let translated text spill past its box, and outright
glyph corruption whenever a span this code touches gets redrawn. `font_path`
must be the SAME file pdf2zh itself rendered the page with (wired via
`NOTO_FONT_PATH` in `Pdf2zhServiceMapper`) — measuring/redrawing against a
different font than what's already on the page would just substitute one
mismatch for another.

Second implementation note: `font_shrink_page`'s outer loop derives the
"allowed width" for a span from that span's own block bbox via
`page.get_text("dict")`. On a page whose text was just rendered by PyMuPDF
(as in a from-scratch test PDF), that bbox is *computed from the same glyphs*
it is being compared against, so it can never actually be narrower than the
text — freshly-rendered text cannot organically "overflow its own bbox".
Real overflow happens when pdf2zh draws the (longer) Vietnamese translation
at a page position sized for the (shorter) original English text; that
narrower "allowed width" is layout metadata from the source document, not
something `page.get_text("dict")` on the already-overflowing output page can
recover on its own. `evaluate_span` (the per-span step of the algorithm) is
exported so it can be unit-tested directly against a real `fitz.Page` with a
deliberately narrow bbox passed in — exercising the real shrink/condense/flag
control flow and the real PyMuPDF redact+reinsert calls — without depending
on being able to organically manufacture a self-overflowing span.
"""

from dataclasses import dataclass

import fitz  # PyMuPDF

#: BR-FONT-02: step 1, shrink font size by at most 20%.
MAX_FONT_SHRINK_RATIO = 0.80
#: BR-FONT-02: step 2, horizontal condensed scaling.
CONDENSED_SCALE = 0.85
_FALLBACK_FONT = "helv"


@dataclass
class OverflowEntry:
    """Plan-level mirror of the `overflow_reports` DB table (Architecture.md
    section 4.2). Kept separate from `src.models.overflow.OverflowReport`
    (the SQLModel table) because this function runs per-page, before a
    `job_id` is known — the caller (Job Orchestrator) maps these into DB rows.
    """

    page_number: int
    original_text: str
    bbox: tuple[float, float, float, float]
    font_size_original: float
    font_size_final: float
    scaling_applied: float
    still_overflow: bool


_NOTO_FONT_ALIAS = "notovi"


async def font_shrink_page(
    page: "fitz.Page",
    overflow_entries: list[OverflowEntry],
    font_path: str | None = None,
) -> list[OverflowEntry]:
    """Scan every text span on `page`; shrink/condense/flag on overflow.

    `overflow_entries` is both mutated in place and returned, so callers can
    pass one shared list across every page of a document and read it once at
    the end. `font_path` (see module docstring) should be the real font
    pdf2zh rendered the page's translated text with — omit only for tests
    that don't care about actual Vietnamese glyph correctness.
    """
    measurer = fitz.Font(fontfile=font_path) if font_path else None
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:  # skip image blocks
            continue
        block_bbox = fitz.Rect(block["bbox"])
        for line in block["lines"]:
            for span in line["spans"]:
                evaluate_span(page, span, block_bbox, overflow_entries, font_path, measurer)
    return overflow_entries


def evaluate_span(
    page: "fitz.Page",
    span: dict,
    block_bbox: "fitz.Rect",
    overflow_entries: list[OverflowEntry],
    font_path: str | None = None,
    measurer: "fitz.Font | None" = None,
) -> None:
    text = span["text"]
    if not text.strip():
        return

    if font_path and measurer is None:
        measurer = fitz.Font(fontfile=font_path)

    def _measure(size: float) -> float:
        if measurer is not None:
            return measurer.text_length(text, fontsize=size)
        return fitz.get_text_length(text, fontname=_FALLBACK_FONT, fontsize=size)

    font_size = span["size"]
    span_bbox = fitz.Rect(span["bbox"])
    bbox_width = block_bbox.width or span_bbox.width

    text_width = _measure(font_size)
    if text_width <= bbox_width:
        return  # fits, nothing to do

    # Step 1: shrink font size, capped at -20%.
    min_size = font_size * MAX_FONT_SHRINK_RATIO
    candidate_size = max(min_size, font_size * (bbox_width / text_width))
    candidate_width = _measure(candidate_size)

    if candidate_width <= bbox_width:
        _redraw_span(page, span_bbox, text, candidate_size, scale=1.0, font_path=font_path)
        return

    # Step 2: horizontal condensed scaling at min font size.
    scaled_width = candidate_width * CONDENSED_SCALE
    if scaled_width <= bbox_width:
        _redraw_span(
            page, span_bbox, text, candidate_size, scale=CONDENSED_SCALE, font_path=font_path
        )
        return

    # Step 3: still overflowing — leave text untouched, flag for review.
    overflow_entries.append(
        OverflowEntry(
            page_number=page.number,
            original_text=text,
            bbox=(block_bbox.x0, block_bbox.y0, block_bbox.x1, block_bbox.y1),
            font_size_original=font_size,
            font_size_final=candidate_size,
            scaling_applied=CONDENSED_SCALE,
            still_overflow=True,
        )
    )


def _redraw_span(
    page: "fitz.Page",
    span_bbox: "fitz.Rect",
    text: str,
    font_size: float,
    scale: float,
    font_path: str | None = None,
) -> None:
    page.add_redact_annot(span_bbox, fill=(1, 1, 1))
    page.apply_redactions()
    origin = fitz.Point(span_bbox.x0, span_bbox.y1 - font_size * 0.2)
    morph = (origin, fitz.Matrix(scale, 1)) if scale != 1.0 else None
    if font_path:
        page.insert_text(
            origin,
            text,
            fontsize=font_size,
            fontname=_NOTO_FONT_ALIAS,
            fontfile=font_path,
            morph=morph,
        )
    else:
        page.insert_text(
            origin,
            text,
            fontsize=font_size,
            fontname=_FALLBACK_FONT,
            morph=morph,
        )
