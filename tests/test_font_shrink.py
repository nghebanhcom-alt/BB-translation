from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.font_shrink import (
    CONDENSED_SCALE,
    MAX_FONT_SHRINK_RATIO,
    _shrink_line,
    evaluate_span,
    font_shrink_page,
)


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
