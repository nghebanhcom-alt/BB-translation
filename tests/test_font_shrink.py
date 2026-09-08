from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.font_shrink import (
    CONDENSED_SCALE,
    MAX_FONT_SHRINK_RATIO,
    _redraw_span,
    _shrink_line,
    evaluate_span,
    font_shrink_page,
)
from src.utils.pdf_coords import insert_text_origin_fix


def _span(text: str, font_size: float, bbox: tuple[float, float, float, float]) -> dict:
    return {"text": text, "size": font_size, "font": "helv", "bbox": bbox}


def _line_sizes(page: "fitz.Page") -> list[float]:
    sizes = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    sizes.append(round(span["size"], 3))
    return sizes


@pytest.mark.asyncio
async def test_evaluate_span_shrinks_font_when_20pct_reduction_fits() -> None:
    doc = fitz.open()
    page = doc.new_page()
    text = "Kem phu bo ganache"
    font_size = 14.0
    full_width = fitz.get_text_length(text, fontname="helv", fontsize=font_size)
    # Just slightly narrower than full width -> a small shrink (< 20%) fits.
    narrow_bbox = fitz.Rect(50, 50, 50 + full_width * 0.95, 70)

    entries: list = []
    evaluate_span(page, _span(text, font_size, tuple(narrow_bbox)), narrow_bbox, entries)

    assert entries == []  # fit after step 1, no overflow report
    # The redraw actually ran against a real page (not mocked).
    assert text in page.get_text()
    doc.close()


@pytest.mark.asyncio
async def test_evaluate_span_applies_condensed_scale_when_shrink_alone_not_enough() -> None:
    doc = fitz.open()
    page = doc.new_page()
    text = "Ganache chocolate thom ngon dam da huong vi"
    font_size = 14.0
    full_width = fitz.get_text_length(text, fontname="helv", fontsize=font_size)
    min_width_after_shrink = fitz.get_text_length(
        text, fontname="helv", fontsize=font_size * MAX_FONT_SHRINK_RATIO
    )
    # Narrower than the -20% shrunk width, but still wide enough that an
    # extra 85% condensed scale brings it under the bbox.
    bbox_width = min_width_after_shrink * (CONDENSED_SCALE + 0.05)
    assert bbox_width < min_width_after_shrink
    narrow_bbox = fitz.Rect(50, 50, 50 + bbox_width, 70)

    entries: list = []
    evaluate_span(page, _span(text, font_size, tuple(narrow_bbox)), narrow_bbox, entries)

    assert entries == []
    assert full_width > bbox_width  # sanity: original text truly wouldn't have fit
    doc.close()


@pytest.mark.asyncio
async def test_evaluate_span_flags_overflow_when_still_too_wide() -> None:
    doc = fitz.open()
    page = doc.new_page()
    text = "Day la mot doan text rat dai khong the nao vua duoc trong khung nho xiu"
    font_size = 14.0
    tiny_bbox = fitz.Rect(50, 50, 60, 70)  # 10pt wide: nothing fits here

    entries: list = []
    evaluate_span(page, _span(text, font_size, tuple(tiny_bbox)), tiny_bbox, entries)

    assert len(entries) == 1
    report = entries[0]
    assert report.still_overflow is True
    assert report.original_text == text
    assert report.scaling_applied == CONDENSED_SCALE
    doc.close()


@pytest.mark.asyncio
async def test_evaluate_span_skips_blank_text() -> None:
    doc = fitz.open()
    page = doc.new_page()
    tiny_bbox = fitz.Rect(50, 50, 51, 51)

    entries: list = []
    evaluate_span(page, _span("   ", 14.0, tuple(tiny_bbox)), tiny_bbox, entries)

    assert entries == []
    doc.close()


@pytest.mark.asyncio
async def test_font_shrink_page_full_scan_no_overflow_for_normal_text() -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Short line", fontsize=12)

    entries = await font_shrink_page(page, [])

    assert entries == []
    doc.close()


_NOTO_FONT_PATH = str(Path(__file__).resolve().parent.parent / "fonts" / "NotoSerif-Regular.ttf")


@pytest.mark.asyncio
async def test_redraw_with_font_path_does_not_corrupt_vietnamese_glyphs() -> None:
    """Regression for the live bug (2026-09-05): redrawing an overflowing
    span with the base-14 "helv" font silently corrupts any Vietnamese
    character outside Latin-1 (verified: "thơm" -> "th·m"). Passing the real
    `font_path` must round-trip the text unchanged."""
    doc = fitz.open()
    page = doc.new_page()
    text = "bánh mì thơm ngọn"
    font_size = 14.0
    real_width = fitz.Font(fontfile=_NOTO_FONT_PATH).text_length(text, fontsize=font_size)
    # Just slightly narrower than the real rendered width -> a small step-1
    # shrink fits, same margin as test_evaluate_span_shrinks_font_...  above.
    narrow_bbox = fitz.Rect(50, 50, 50 + real_width * 0.95, 70)

    entries: list = []
    evaluate_span(
        page,
        _span(text, font_size, tuple(narrow_bbox)),
        narrow_bbox,
        entries,
        font_path=_NOTO_FONT_PATH,
    )

    assert text in page.get_text()
    doc.close()


@pytest.mark.asyncio
async def test_shrink_line_forces_uniform_font_size_across_spans() -> None:
    """Regression for the v1.2.1 bug: two spans on the same visual line that
    overflow by different amounts must not end up at two different final
    font sizes. `span_a` alone would fit untouched at 14pt; `span_b` needs
    the full -20% shrink plus condensed scaling. Both must land at the same
    (span_b-driven) final size."""
    doc = fitz.open()
    page = doc.new_page()
    font_size = 14.0
    text_a = "Kem phu bo ganache"
    text_b = "Ganache chocolate thom ngon dam da huong vi"

    # bbox_width == 90% of text_b's natural width: span_b needs a step-1-only
    # shrink to ~12.6pt (above the -20% floor, so scale stays 1.0 and
    # PyMuPDF's reported "size" is undistorted — a condensed/morphed span's
    # reported "size" is sqrt(scale)-distorted, not directly comparable).
    bbox_width = fitz.get_text_length(text_b, fontname="helv", fontsize=font_size) * 0.9 * 1.001
    full_width_a = fitz.get_text_length(text_a, fontname="helv", fontsize=font_size)
    assert full_width_a < bbox_width  # sanity: span_a alone needs no shrink at all

    span_a_bbox = (50, 50, 50 + full_width_a, 70)
    span_b_bbox = (50 + full_width_a + 2, 50, 50 + full_width_a + 2 + bbox_width, 70)
    line = {
        "bbox": (50, 50, span_b_bbox[2], 70),
        "spans": [
            _span(text_a, font_size, span_a_bbox),
            _span(text_b, font_size, span_b_bbox),
        ],
    }
    block_bbox = fitz.Rect(50, 50, 50 + bbox_width, 70)

    entries: list = []
    _shrink_line(page, line, block_bbox, entries)

    assert entries == []
    assert text_a in page.get_text()
    assert text_b in page.get_text()
    sizes = _line_sizes(page)
    assert sizes  # something was actually redrawn
    # PyMuPDF may coalesce the two adjacent same-style runs into one span,
    # so assert on whatever spans came back rather than requiring exactly
    # two: every one of them must share the same, actually-shrunk, size.
    assert all(size == pytest.approx(sizes[0]) for size in sizes)
    assert sizes[0] < font_size  # actually shrunk, not left at the original 14pt
    doc.close()


@pytest.mark.asyncio
async def test_shrink_line_centers_freed_up_space_instead_of_anchoring_left() -> None:
    """Regression for the v1.2.1 bug: after shrinking, the freed-up width
    must be distributed around the line, not left dangling entirely on the
    right of a left-anchored span."""
    doc = fitz.open()
    page = doc.new_page()
    font_size = 14.0
    text = "Ganache chocolate thom ngon dam da huong vi"

    min_width_after_shrink = fitz.get_text_length(
        text, fontname="helv", fontsize=font_size * MAX_FONT_SHRINK_RATIO
    )
    bbox_width = min_width_after_shrink * (CONDENSED_SCALE + 0.05)
    span_bbox = (50, 50, 50 + bbox_width, 70)
    line = {"bbox": span_bbox, "spans": [_span(text, font_size, span_bbox)]}
    block_bbox = fitz.Rect(*span_bbox)

    entries: list = []
    _shrink_line(page, line, block_bbox, entries)

    assert entries == []
    rendered = page.get_text("dict")["blocks"][0]["lines"][0]["spans"][0]["bbox"]
    left_margin = rendered[0] - block_bbox.x0
    right_margin = block_bbox.x1 - rendered[2]
    assert left_margin > 0  # not simply left-anchored at the block's edge
    assert right_margin >= 0
    doc.close()


@pytest.mark.asyncio
async def test_helv_measurement_understates_real_vietnamese_width() -> None:
    """Documents why "helv"-based overflow detection is unreliable for
    Vietnamese: it can report a span as fitting when the font pdf2zh/babeldoc
    actually rendered it with (Noto Serif) would overflow the same box."""
    text = "bánh"
    helv_width = fitz.get_text_length(text, fontname="helv", fontsize=12)
    real_width = fitz.Font(fontfile=_NOTO_FONT_PATH).text_length(text, fontsize=12)

    assert real_width > helv_width * 1.2  # >20% understatement, matches live measurement


# --- Regression: "chữ nhảy lung tung" (2026-09-08, CropBox not contained
# in MediaBox -- NOT the simpler "MediaBox origin != (0,0)" theory; see
# `src.utils.pdf_coords.insert_text_origin_fix`'s docstring for why that
# simpler theory is wrong) ---
#
# Real, live-captured fixtures (Protocol 5 mục 3 -- no hand-typed mocks of
# PyMuPDF's coordinate behavior): both PDFs below are genuine excerpts from
# real books already committed for the TOC/babeldoc work, not fabricated for
# this bug.
#   - `toc_sources/lcb_toc.pdf`: Le Cordon Bleu itself. Its pages carry
#     pdf2zh's malformed CropBox (bigger than MediaBox, invalid per the PDF
#     spec) that triggered the live bug: mediabox=(33,33,681,816),
#     cropbox=(0,-33,714,816).
#   - `job3594a7a3_chunk0_sample_mono.pdf`: a different book, whose CropBox
#     is a legitimate, spec-valid, *smaller* margin box
#     (mediabox=(0,0,684,855), cropbox=(36,36,648,819)) -- proves the fix is
#     general (works for a real "just cropped margins" page too), not
#     special-cased to the oversized-CropBox case alone.
_LCB_TOC_FIXTURE = str(
    Path(__file__).resolve().parent / "fixtures" / "babeldoc" / "toc_sources" / "lcb_toc.pdf"
)
_MARGIN_CROP_FIXTURE = str(
    Path(__file__).resolve().parent / "fixtures" / "babeldoc" / "job3594a7a3_chunk0_sample_mono.pdf"
)


def _first_nontrivial_span(page: "fitz.Page") -> dict:
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if len(span["text"].strip()) > 3:
                    return span
    raise AssertionError("no suitable (non-trivial) text span found on fixture page")


def _span_with_origin_near(
    page: "fitz.Page", origin: tuple[float, float], tol: float = 0.5
) -> dict | None:
    ox, oy = origin
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if not span["text"].strip():
                    continue
                sx, sy = span["origin"]
                if abs(sx - ox) <= tol and abs(sy - oy) <= tol:
                    return span
    return None


def test_insert_text_origin_fix_is_noop_when_cropbox_matches_mediabox() -> None:
    """The common case (Figoni-style books, CropBox absent/equal to
    MediaBox): the correction must not move the point at all."""
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    page = doc[0]
    origin = fitz.Point(120.1, 300.0)

    assert insert_text_origin_fix(page, origin) == origin
    doc.close()


@pytest.mark.parametrize("fixture_path", [_LCB_TOC_FIXTURE, _MARGIN_CROP_FIXTURE])
def test_redraw_span_lands_on_its_own_bbox_despite_mediabox_cropbox_offset(
    fixture_path: str,
) -> None:
    """Regression for the live "chữ nhảy lung tung" bug: `_redraw_span` must
    redraw a span at the position `page.get_text("dict")` itself reports for
    that span's own bbox -- even when the page's CropBox origin diverges from
    its MediaBox origin. Before the `insert_text_origin_fix` correction,
    PyMuPDF's `Shape.insert_text` (which backs `page.insert_text`) silently
    offsets by the *CropBox* origin instead of the MediaBox origin, so the
    redrawn glyphs land exactly `(mediabox.x0 - cropbox_position.x,
    -cropbox_position.y)` away from where they should be -- text overlapping
    whatever else already occupies that other position on the page. This
    test FAILS on the pre-fix code (verified via `git stash` on
    `src/postprocess/font_shrink.py`) and PASSES after it."""
    doc = fitz.open(fixture_path)
    page = doc[0]
    mediabox_origin = (page.mediabox.x0, 0.0)
    cropbox_position = (page.cropbox_position.x, page.cropbox_position.y)
    assert cropbox_position != mediabox_origin, (
        "fixture sanity check failed: this test only proves anything when "
        "the page's CropBox origin actually diverges from its MediaBox "
        f"origin (got cropbox_position={cropbox_position}, "
        f"mediabox origin={mediabox_origin})"
    )

    span = _first_nontrivial_span(page)
    span_bbox = fitz.Rect(span["bbox"])
    final_size = span["size"] * MAX_FONT_SHRINK_RATIO  # simulate a real BR-FONT-02 shrink
    expected_origin = (span_bbox.x0, span_bbox.y1 - final_size * 0.2)

    _redraw_span(page, span_bbox, span["text"], final_size, scale=1.0)

    redrawn = _span_with_origin_near(page, expected_origin)
    assert redrawn is not None, (
        f"no span redrawn near the expected origin {expected_origin} -- it "
        "landed somewhere else on the page (the exact 'chữ nhảy lung tung' "
        "symptom: text drawn at the wrong position, overlapping other "
        "content instead of replacing the original span in place)"
    )
    assert redrawn["origin"][0] == pytest.approx(expected_origin[0], abs=0.05)
    assert redrawn["origin"][1] == pytest.approx(expected_origin[1], abs=0.05)
    doc.close()
