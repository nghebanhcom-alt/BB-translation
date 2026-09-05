"""Real PyMuPDF round-trip tests for the OCR-to-translate bridge
(Architecture.md 6.10.4, Bug #5 fix). Deliberately NOT mocked — this module
IS the experiment Tech Lead already ran live (6.10.3 T1-T4); the whole point
is that a real `fitz.Document` gets real invisible text pdfminer/pdf2zh can
read back, so these tests build a real "scan-like" PDF (no text layer) and
extract text back with real PyMuPDF, matching Protocol 5 R5-02's spirit of
not trusting a hand-rolled fixture shape.
"""

import json
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.preprocess.searchable_pdf import SearchablePdfError, build_searchable_pdf

PAGE_WIDTH = 300.0
PAGE_HEIGHT = 150.0


def _make_scan_like_pdf(
    path: Path, *, page_size: tuple[float, float] = (PAGE_WIDTH, PAGE_HEIGHT)
) -> None:
    """A page with NO text layer — draws a rectangle to stand in for a
    scanned image, exactly like a real `pdf_scan` upload would look to
    pdf2zh before the bridge is built (Bug #5's failure mode).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=page_size[0], height=page_size[1])
    page.draw_rect(
        fitz.Rect(0, 0, page_size[0], page_size[1]), color=(0.9, 0.9, 0.9), fill=(0.9, 0.9, 0.9)
    )
    doc.save(path)
    doc.close()


def _middle_json_dict(
    *,
    page_idx: int = 0,
    page_size: tuple[float, float] = (PAGE_WIDTH, PAGE_HEIGHT),
    spans: list[dict] | None = None,
    discarded_spans: list[dict] | None = None,
) -> dict:
    if spans is None:
        spans = [
            {
                "type": "text",
                "content": "Blind bake the tart shell",
                "bbox": [20.0, 20.0, 220.0, 40.0],
                "score": 0.95,
            },
            {
                "type": "text",
                "content": "Fold in the lemon curd gently",
                "bbox": [20.0, 60.0, 240.0, 80.0],
                "score": 0.88,
            },
        ]
    return {
        "pdf_info": [
            {
                "page_idx": page_idx,
                "page_size": list(page_size),
                "preproc_blocks": [
                    {"lines": [{"spans": spans}]},
                ],
                "discarded_blocks": (
                    [{"lines": [{"spans": discarded_spans}]}] if discarded_spans else []
                ),
            }
        ]
    }


def _write_middle_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_build_searchable_pdf_writes_readable_invisible_text(tmp_path: Path) -> None:
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)

    # Reproduce Bug #5's exact symptom on the ORIGINAL scan first: no text layer.
    with fitz.open(source_pdf) as doc:
        assert doc[0].get_text().strip() == ""

    middle_json_path = _write_middle_json(tmp_path / "middle.json", _middle_json_dict())
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    result = build_searchable_pdf(source_pdf, middle_json_path, output_path)

    assert result.path == output_path
    assert result.page_count == 1
    assert result.span_count == 2
    assert result.extracted_chars > 0

    # Independent real extraction — same idea as T1/T4 (Architecture.md
    # 6.10.3): a real PDF reader must find the OCR'd text at the bridge, not
    # find nothing like it would on the original scan.
    with fitz.open(output_path) as doc:
        extracted = doc[0].get_text()
    assert "Blind bake the tart shell" in extracted
    assert "Fold in the lemon curd gently" in extracted


def test_whiteout_covers_original_span_area(tmp_path: Path) -> None:
    """6.10.3's stated reason buoc 1 is mandatory: without it, the invisible
    VI overlay pdf2zh draws later would sit UNDER visible original glyphs.
    Whiting out the bbox is what makes the region behind the invisible text
    blank instead of showing whatever was rendered there before.
    """
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)
    middle_json_path = _write_middle_json(tmp_path / "middle.json", _middle_json_dict())
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    build_searchable_pdf(source_pdf, middle_json_path, output_path)

    with fitz.open(output_path) as doc:
        page = doc[0]
        # Sample a pixel inside the first span's bbox — should now be white,
        # not the grey (0.9, 0.9, 0.9) the "scan" rectangle originally had.
        pix = page.get_pixmap(clip=fitz.Rect(25, 25, 30, 30))
        sample = pix.pixel(0, 0)
    assert sample == (255, 255, 255)


def test_images_and_tables_are_left_untouched(tmp_path: Path) -> None:
    """Only text/inline_equation spans are whited out — image/table spans
    must keep their original pixels (Architecture.md 6.10.3 tradeoffs)."""
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)
    middle = _middle_json_dict(
        spans=[
            {
                "type": "text",
                "content": "Recipe title",
                "bbox": [20.0, 20.0, 150.0, 40.0],
                "score": 0.9,
            },
            {
                "type": "image",
                "content": "ignored",
                "bbox": [20.0, 60.0, 150.0, 100.0],
                "score": 0.9,
            },
        ]
    )
    middle_json_path = _write_middle_json(tmp_path / "middle.json", middle)
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    result = build_searchable_pdf(source_pdf, middle_json_path, output_path)

    assert result.span_count == 1  # only the text span was written
    with fitz.open(output_path) as doc:
        page = doc[0]
        pix = page.get_pixmap(clip=fitz.Rect(25, 65, 30, 70))
        sample = pix.pixel(0, 0)
    # Image-area pixel keeps the original grey "scan" fill, not whited out.
    assert sample != (255, 255, 255)


def test_discarded_blocks_are_not_whited_out(tmp_path: Path) -> None:
    """`discarded_blocks` (headers/footers/watermarks MinerU already flagged
    as not-content) must be ignored entirely — whiting them out would erase
    page furniture that was never meant to be translated (Architecture.md
    6.10.4 step 2a).
    """
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)
    middle = _middle_json_dict(
        discarded_spans=[
            {"type": "text", "content": "Page 3", "bbox": [10.0, 130.0, 40.0, 145.0], "score": 0.9}
        ]
    )
    middle_json_path = _write_middle_json(tmp_path / "middle.json", middle)
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    result = build_searchable_pdf(source_pdf, middle_json_path, output_path)

    assert result.span_count == 2  # only the 2 preproc_blocks spans
    with fitz.open(output_path) as doc:
        extracted = doc[0].get_text()
    assert "Page 3" not in extracted


def test_raises_when_middle_json_has_no_pdf_info(tmp_path: Path) -> None:
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)
    middle_json_path = _write_middle_json(tmp_path / "middle.json", {"pdf_info": []})
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    with pytest.raises(SearchablePdfError, match="pdf_info"):
        build_searchable_pdf(source_pdf, middle_json_path, output_path)


def test_raises_br_ocr_02_when_no_text_layer_produced(tmp_path: Path) -> None:
    """BR-OCR-02: every span on the page is non-text (image/table), so the
    bridge would end up with zero readable characters — must fail here, not
    downstream at pdf2zh (that silent path IS Bug #5).
    """
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)
    middle = _middle_json_dict(
        spans=[
            {"type": "image", "content": "photo", "bbox": [20.0, 20.0, 150.0, 100.0], "score": 0.9}
        ]
    )
    middle_json_path = _write_middle_json(tmp_path / "middle.json", middle)
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    with pytest.raises(SearchablePdfError):
        build_searchable_pdf(source_pdf, middle_json_path, output_path)


def test_raises_when_coordinate_systems_disagree(tmp_path: Path) -> None:
    """S17 guard: middle.json's page_size must match PyMuPDF's page.rect
    within 2pt — a silent mismatch would draw whiteout/text at the wrong
    coordinates while still "succeeding" (exactly the failure mode Protocol 5
    exists to catch).
    """
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf, page_size=(PAGE_WIDTH, PAGE_HEIGHT))
    middle = _middle_json_dict(page_size=(PAGE_WIDTH * 2, PAGE_HEIGHT * 2))
    middle_json_path = _write_middle_json(tmp_path / "middle.json", middle)
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    with pytest.raises(SearchablePdfError, match="He toa do lech"):
        build_searchable_pdf(source_pdf, middle_json_path, output_path)


def test_skips_page_idx_out_of_range(tmp_path: Path) -> None:
    source_pdf = tmp_path / "scan.pdf"
    _make_scan_like_pdf(source_pdf)
    middle = _middle_json_dict(page_idx=5)  # doc only has 1 page (idx 0)
    middle_json_path = _write_middle_json(tmp_path / "middle.json", middle)
    output_path = tmp_path / "ocr_bridge" / "searchable.pdf"

    with pytest.raises(SearchablePdfError):
        # No page ever gets a text layer -> BR-OCR-02 fires.
        build_searchable_pdf(source_pdf, middle_json_path, output_path)
