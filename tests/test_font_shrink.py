from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.font_shrink import (
    CONDENSED_SCALE,
    MAX_FONT_SHRINK_RATIO,
    evaluate_span,
    font_shrink_page,
)


def _span(text: str, font_size: float, bbox: tuple[float, float, float, float]) -> dict:
    return {"text": text, "size": font_size, "font": "helv", "bbox": bbox}


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


_NOTO_FONT_PATH = str(Path(__file__).resolve().parent.parent / "fonts" / "BeVietnamPro-Regular.ttf")


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
async def test_helv_measurement_understates_real_vietnamese_width() -> None:
    """Documents why "helv"-based overflow detection is unreliable for
    Vietnamese: it can report a span as fitting when the font pdf2zh actually
    rendered it with (Noto/Be Vietnam Pro) would overflow the same box."""
    text = "bánh"
    helv_width = fitz.get_text_length(text, fontname="helv", fontsize=12)
    real_width = fitz.Font(fontfile=_NOTO_FONT_PATH).text_length(text, fontsize=12)

    assert real_width > helv_width * 1.2  # >20% understatement, matches live measurement
