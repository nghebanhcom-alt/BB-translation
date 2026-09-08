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
must be the SAME font FILE already on the page — measuring/redrawing against
a different font than what's already there would just substitute one
mismatch for another. For `pdf2zh` this is enforced directly (`NOTO_FONT_PATH`
in `Pdf2zhServiceMapper` pins pdf2zh's own render font to this same path).
For `babeldoc`, `NOTO_FONT_PATH` has no effect — babeldoc always draws with
its own bundled font asset (verified 2026-09-05 by reading
`babeldoc.assets.embedding_assets_metadata`: "vi" resolves to `EN_FONT_FAMILY`,
whose "normal" font is `NotoSerif-Regular.ttf`/`NotoSerif-Bold.ttf`) — so
`Settings.noto_font_path` is instead pointed at a local copy of that SAME
font file, chosen to match what babeldoc already put on the page rather than
to change what babeldoc renders with.

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

Third implementation note (2026-09-05, user-reported v1.2.1 rendering bugs):
the original version of this module decided font size / condensed scale
*per span*, independently. Two spans sitting on the same visual line (e.g.
because the source PDF split one sentence into two font runs) could end up
overflowing by different amounts and therefore land on two different final
font sizes — the "font size lên xuống không đều tại chính 1 đoạn" bug. It
also always re-inserted a shrunk span at its *original* `span_bbox.x0`,
leaving whatever width the smaller font freed up as dead space on the right
— the "co font chữ nhưng khoảng trống lại rất nhiều" bug. `font_shrink_page`
now decides a single shrink ratio per *line* (`_shrink_line`) and, when every
span on that line ends up redrawable, repacks them left-to-right and centers
the whole line in the block's width so the freed-up space is distributed
instead of dangling on one side. `evaluate_span` itself is unchanged (kept
for the existing single-span test surface and for standalone callers) and
now shares its core fit math with the line-level path via `_compute_fit`.
"""

from dataclasses import dataclass

import fitz  # PyMuPDF

from src.utils.pdf_coords import insert_text_origin_fix

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
    """Scan every text line on `page`; shrink/condense/flag on overflow.

    Decides one shrink ratio per line (not per span) so that spans sharing a
    visual line always end up at the same final font size — see the third
    implementation note in the module docstring. `overflow_entries` is both
    mutated in place and returned, so callers can pass one shared list across
    every page of a document and read it once at the end. `font_path` (see
    module docstring) should be the real font pdf2zh rendered the page's
    translated text with — omit only for tests that don't care about actual
    Vietnamese glyph correctness.
    """
    measurer = fitz.Font(fontfile=font_path) if font_path else None
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:  # skip image blocks
            continue
        block_bbox = fitz.Rect(block["bbox"])
        for line in block["lines"]:
            _shrink_line(page, line, block_bbox, overflow_entries, font_path, measurer)
    return overflow_entries


def _compute_fit(
    measure_fn: "callable[[float], float]",
    font_size: float,
    bbox_width: float,
) -> tuple[float, float, bool]:
    """Pure BR-FONT-02 3-step sizing decision, shared by `evaluate_span` (the
    single-span path, kept for the existing test surface) and `_shrink_line`
    (the line-level path). Returns `(final_font_size, scale_applied,
    still_overflow)` — callers decide what to do with that (redraw, flag,
    fold into a line-wide ratio) rather than this function touching the page.
    """
    text_width = measure_fn(font_size)
    if text_width <= bbox_width:
        return font_size, 1.0, False

    # Step 1: shrink font size, capped at -20%.
    min_size = font_size * MAX_FONT_SHRINK_RATIO
    candidate_size = max(min_size, font_size * (bbox_width / text_width))
    candidate_width = measure_fn(candidate_size)

    if candidate_width <= bbox_width:
        return candidate_size, 1.0, False

    # Step 2: horizontal condensed scaling at min font size.
    scaled_width = candidate_width * CONDENSED_SCALE
    if scaled_width <= bbox_width:
        return candidate_size, CONDENSED_SCALE, False

    # Step 3: still overflowing — caller leaves text untouched, flags it.
    return candidate_size, CONDENSED_SCALE, True


def evaluate_span(
    page: "fitz.Page",
    span: dict,
    block_bbox: "fitz.Rect",
    overflow_entries: list[OverflowEntry],
    font_path: str | None = None,
    measurer: "fitz.Font | None" = None,
) -> None:
    """Single-span BR-FONT-02 decision. Kept for standalone callers/tests
    that exercise one span in isolation; `font_shrink_page` itself uses the
    line-level `_shrink_line` below so sibling spans on one line agree on a
    final font size."""
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

    final_size, scale, still_overflow = _compute_fit(_measure, font_size, bbox_width)

    if still_overflow:
        overflow_entries.append(
            OverflowEntry(
                page_number=page.number,
                original_text=text,
                bbox=(block_bbox.x0, block_bbox.y0, block_bbox.x1, block_bbox.y1),
                font_size_original=font_size,
                font_size_final=final_size,
                scaling_applied=CONDENSED_SCALE,
                still_overflow=True,
            )
        )
        return

    if final_size == font_size and scale == 1.0:
        return  # fits at original size, nothing to do

    _redraw_span(page, span_bbox, text, final_size, scale=scale, font_path=font_path)


def _shrink_line(
    page: "fitz.Page",
    line: dict,
    block_bbox: "fitz.Rect",
    overflow_entries: list[OverflowEntry],
    font_path: str | None = None,
    measurer: "fitz.Font | None" = None,
) -> None:
    """Decide a single font-size ratio for every span on `line` (the most
    aggressive shrink any one span needs), then redraw them all at that
    uniform size. When none of the spans need step-3 (still overflowing
    after condensed scaling), also repacks the line left-to-right and centers
    it in `block_bbox`'s width instead of leaving shrunk spans anchored at
    their original (English-layout-sized) x position — see module docstring.
    """
    entries = [(span, span["text"]) for span in line["spans"] if span["text"].strip()]
    if not entries:
        return

    def _measure_for(span: dict, text: str) -> "callable[[float], float]":
        if measurer is not None:
            return lambda size: measurer.text_length(text, fontsize=size)
        return lambda size: fitz.get_text_length(text, fontname=_FALLBACK_FONT, fontsize=size)

    bbox_width = block_bbox.width or fitz.Rect(line["bbox"]).width

    fits = [
        _compute_fit(_measure_for(span, text), span["size"], bbox_width) for span, text in entries
    ]
    line_ratio = min(
        final_size / span["size"] for (span, _), (final_size, _, _) in zip(entries, fits)
    )

    if line_ratio >= 1.0:
        return  # every span already fits at its own size, nothing to do

    # Re-evaluate each span's overflow status at the line's shared ratio
    # (not each span's own, possibly less aggressive, ratio computed above).
    decisions: list[tuple[dict, str, float, float, bool]] = []
    for span, text in entries:
        forced_size = span["size"] * line_ratio
        measure_fn = _measure_for(span, text)
        width_at_forced = measure_fn(forced_size)
        if width_at_forced <= bbox_width:
            decisions.append((span, text, forced_size, 1.0, False))
        elif width_at_forced * CONDENSED_SCALE <= bbox_width:
            decisions.append((span, text, forced_size, CONDENSED_SCALE, False))
        else:
            decisions.append((span, text, forced_size, CONDENSED_SCALE, True))

    if any(still_overflow for *_, still_overflow in decisions):
        # Mixed line (some spans fit at the shared size, at least one still
        # doesn't): keep every span's own original x-position — repacking
        # would have to reason about the untouched span's original width
        # too, which is more risk than this fix is worth. Every span still
        # gets the uniform font size, which is the bug being fixed here.
        for span, text, final_size, scale, still_overflow in decisions:
            span_bbox = fitz.Rect(span["bbox"])
            if still_overflow:
                overflow_entries.append(
                    OverflowEntry(
                        page_number=page.number,
                        original_text=text,
                        bbox=(block_bbox.x0, block_bbox.y0, block_bbox.x1, block_bbox.y1),
                        font_size_original=span["size"],
                        font_size_final=final_size,
                        scaling_applied=CONDENSED_SCALE,
                        still_overflow=True,
                    )
                )
                continue
            _redraw_span(page, span_bbox, text, final_size, scale=scale, font_path=font_path)
        return

    # Every span on the line fits at the shared ratio: repack left-to-right
    # and center the whole line in the block's width instead of leaving each
    # span at its original (English-sized) position.
    widths = [
        _measure_for(span, text)(final_size) * scale
        for span, text, final_size, scale, _ in decisions
    ]
    gaps = []
    for i in range(len(decisions) - 1):
        this_bbox = fitz.Rect(decisions[i][0]["bbox"])
        next_bbox = fitz.Rect(decisions[i + 1][0]["bbox"])
        gaps.append(max(0.0, (next_bbox.x0 - this_bbox.x1)) * line_ratio)

    total_width = sum(widths) + sum(gaps)
    start_x = block_bbox.x0 + max(0.0, (bbox_width - total_width) / 2)

    cursor = start_x
    for i, (span, text, final_size, scale, _) in enumerate(decisions):
        span_bbox = fitz.Rect(span["bbox"])
        origin = fitz.Point(cursor, span_bbox.y1 - final_size * 0.2)
        _redraw_span(
            page, span_bbox, text, final_size, scale=scale, font_path=font_path, origin=origin
        )
        cursor += widths[i]
        if i < len(gaps):
            cursor += gaps[i]


def _redraw_span(
    page: "fitz.Page",
    span_bbox: "fitz.Rect",
    text: str,
    font_size: float,
    scale: float,
    font_path: str | None = None,
    origin: "fitz.Point | None" = None,
) -> None:
    """Erases the glyphs at `span_bbox` (the span's *original* position) and
    re-inserts `text` at `origin` if given, else at `span_bbox`'s own origin
    — `origin` lets `_shrink_line`'s repack path draw the span somewhere
    other than where it used to be, while still erasing the right spot.

    `add_redact_annot` takes `span_bbox` as-is (verified correct regardless
    of MediaBox/CropBox mismatch — see `src.utils.pdf_coords.
    insert_text_origin_fix`'s docstring); only the point handed to
    `insert_text` needs the MediaBox/CropBox correction, since that's the
    PyMuPDF call with the coordinate bug."""
    page.add_redact_annot(span_bbox, fill=(1, 1, 1))
    page.apply_redactions()
    if origin is None:
        origin = fitz.Point(span_bbox.x0, span_bbox.y1 - font_size * 0.2)
    origin = insert_text_origin_fix(page, origin)
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
