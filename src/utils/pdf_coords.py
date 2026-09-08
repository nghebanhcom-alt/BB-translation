"""Shared PyMuPDF coordinate fix for `page.insert_text()` (Bug #8, 2026-09-08
"chữ nhảy lung tung", Le Cordon Bleu Patisserie and Baking Foundations).

Extracted from `src/postprocess/font_shrink.py` (round-1 fix) into its own
module during round-2 review (`docs/review-report.md`, "Bug #8 ... review
`font_shrink.py` MediaBox/CropBox fix", issue Blocking #1): the reviewer
proved by live reproduction against `tests/fixtures/babeldoc/toc_sources/
lcb_toc.pdf` that TWO OTHER call sites of `page.insert_text()`
(`src/postprocess/rotated_text_overlay.py::_draw_block` and
`src/preprocess/searchable_pdf.py::_insert_invisible_text`) hit the exact
same PyMuPDF bug and needed the exact same correction — a single shared
function is required so the three call sites can't drift out of sync with
one another the way copy-pasted logic would.
"""

import fitz  # PyMuPDF


def insert_text_origin_fix(page: "fitz.Page", origin: "fitz.Point") -> "fitz.Point":
    """Corrects the point passed to `page.insert_text()` for pages whose
    CropBox is not fully contained in their MediaBox.

    Root cause (verified 2026-09-08 by reading the installed PyMuPDF 1.28.2
    source at `.venv/lib/python3.14/site-packages/pymupdf/__init__.py` and by
    live reproduction against real fixture files — not guessed):
    `page.insert_text()` delegates to `Shape.insert_text` (class `Shape`,
    defined ~L15021). `Shape.__init__` (~L15044-15056) sets
    `self.height = page.mediabox_size.y` (`mediabox.y1`) and
    `self.x, self.y = page.cropbox_position` (`page.cropbox_position` is
    `page.cropbox.tl`, taken as-is, NOT intersected with MediaBox).
    `Shape.insert_text` (~L15382+) then computes the actual PDF
    content-stream position as `left = point.x + self.x` and
    `top = self.height - point.y - self.y` — i.e. it offsets by the page's
    raw **CropBox** top-left corner.

    `page.get_text("dict")` bbox/origin values and `page.add_redact_annot()`
    (both verified live: an *uncorrected* `add_redact_annot(span_bbox)`
    still erases a span at its true, on-page location) are instead anchored
    to `page.rect` (`Page.bound()`, ~L11006), which is the *intersection* of
    CropBox and MediaBox, normalized to start at (0, 0) — this is the PDF
    spec's definition of a page's effective visible area, since a
    conforming CropBox must be `⊆` MediaBox. Whenever CropBox actually is
    `⊆` MediaBox (the spec-conforming case — includes CropBox absent/equal
    to MediaBox, *and* CropBox strictly smaller as a legitimate margin/trim
    box, e.g. `job3594a7a3_chunk0_sample_mono.pdf`'s
    `mediabox=(0,0,684,855)` / `cropbox=(36,36,648,819)`), the intersection
    IS the CropBox, so `cropbox_position` already equals that intersection's
    top-left corner and `Shape.insert_text`'s formula is correct — verified
    live: a plain, uncorrected `page.insert_text(Point(200,400), ...)` round
    trips through `get_text("dict")` as exactly `(200, 400)` on that file.

    It breaks precisely when CropBox is NOT `⊆` MediaBox — invalid per the
    PDF spec, but exactly the real, live state of every page in Le Cordon
    Bleu's pdf2zh output (an artifact of pdf2zh/babeldoc's own PDF assembly,
    not something this repo controls): `mediabox=(33,33,681,816)` but
    `cropbox=(0,-33,714,816)`, bigger than MediaBox on every side. There,
    `page.rect`'s intersection collapses back down to MediaBox itself (since
    MediaBox ⊆ that oversized CropBox), but `Shape.insert_text` still offsets
    by the raw, un-intersected `cropbox_position = (0, -33)` instead of the
    effective `(33, 0)` — a live-measured (-33, -33)-ish misplacement.

    General fix: correct by however far CropBox's top-left corner sits
    *outside* MediaBox's, in each direction independently, via
    `max(..., 0)` (zero whenever CropBox is properly contained on that
    side — the legitimate-margin-box case above must get a zero correction,
    not `mediabox.x0 - cropbox_position.x` unconditionally, which is what an
    earlier, INCORRECT version of this function did and which broke
    `job3594a7a3_chunk0_sample_mono.pdf`'s valid margin CropBox by
    "correcting" a mismatch that wasn't actually a bug there):
        dx = max(mediabox.x0 - cropbox_position.x, 0.0)
        dy = max(-cropbox_position.y, 0.0)
    (mediabox's own top-left is always `(mediabox.x0, 0)` in
    `cropbox_position`'s coordinate convention — x raw/unflipped, y flipped
    so MediaBox's top edge is always 0 — so these are exactly
    `max(mediabox_top_left - cropbox_position, 0)` per axis.)

    Live-verified (2026-09-08) against
    `tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf` (real Le Cordon Bleu
    excerpt, oversized CropBox) and
    `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf` (real
    excerpt from a different book, valid smaller-margin CropBox): see
    `tests/test_font_shrink.py::test_redraw_span_lands_on_its_own_bbox_despite_mediabox_cropbox_offset`,
    parameterized over both files — redrawing a real span lands back on the
    exact origin `get_text("dict")` reports for that span in both cases.
    Re-verified round-2 (`docs/review-report.md` Bug #8 review) against the
    same `lcb_toc.pdf` fixture for the two additional call sites that use
    this shared function: `rotated_text_overlay.py::_draw_block` (see
    `tests/test_rotated_text_overlay.py::test_draw_block_lands_on_pivot_despite_mediabox_cropbox_offset`)
    and `searchable_pdf.py::_insert_invisible_text`.
    """
    mediabox = page.mediabox
    cropbox_position = page.cropbox_position
    dx = max(mediabox.x0 - cropbox_position.x, 0.0)
    dy = max(-cropbox_position.y, 0.0)
    if dx == 0 and dy == 0:
        return origin
    return fitz.Point(origin.x + dx, origin.y + dy)
