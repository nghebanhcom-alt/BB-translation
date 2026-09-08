from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.bilingual_merge import create_bilingual_pdf

_NOTO_FONT_PATH = str(Path(__file__).parent.parent / "fonts" / "NotoSerif-Regular.ttf")


def _make_pdf(path: Path, labels: list[str]) -> None:
    doc = fitz.open()
    for label in labels:
        page = doc.new_page()
        page.insert_text((50, 100), label, fontsize=14)
    doc.save(path)
    doc.close()


def _make_pdf_with_embedded_font(path: Path, n_pages: int) -> None:
    """Base14 fonts (used by `_make_pdf` above) are referenced by name, not
    embedded — they can't reproduce the font-duplication bug this file's
    regression test targets. A real embedded TTF is needed (Architecture.md
    "US-16 v2 — Final Decision" W4/X6: the bug is `insert_pdf` copying the
    VI doc's embedded font once per page)."""
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text(
            (50, 100),
            f"Trang {i} - chu tieng Viet",
            fontsize=14,
            fontname="notoserif",
            fontfile=_NOTO_FONT_PATH,
        )
    doc.save(path)
    doc.close()


def _count_length1_font_streams(path: Path) -> int:
    """`/Length1` only appears on embedded font program streams — counting
    it is how Architecture.md W4/X6 tells "9 real fonts" apart from "592
    duplicated copies of the same 9 fonts"."""
    count = 0
    with fitz.open(path) as doc:
        for xref in range(1, doc.xref_length()):
            key_type, _value = doc.xref_get_key(xref, "Length1")
            if key_type != "null":
                count += 1
    return count


@pytest.mark.asyncio
async def test_create_bilingual_pdf_interleaves_vi_and_en_pages(tmp_path: Path) -> None:
    vi_path = tmp_path / "vi.pdf"
    en_path = tmp_path / "en.pdf"
    output_path = tmp_path / "bilingual.pdf"

    _make_pdf(vi_path, ["VI-1", "VI-2"])
    _make_pdf(en_path, ["EN-1", "EN-2"])

    await create_bilingual_pdf(vi_path, en_path, output_path)

    with fitz.open(output_path) as merged:
        assert merged.page_count == 4
        texts = [page.get_text().strip() for page in merged]

    assert texts == ["VI-1", "EN-1", "VI-2", "EN-2"]


@pytest.mark.asyncio
async def test_create_bilingual_pdf_handles_shorter_en_doc(tmp_path: Path) -> None:
    vi_path = tmp_path / "vi.pdf"
    en_path = tmp_path / "en.pdf"
    output_path = tmp_path / "bilingual.pdf"

    _make_pdf(vi_path, ["VI-1", "VI-2", "VI-3"])
    _make_pdf(en_path, ["EN-1"])

    await create_bilingual_pdf(vi_path, en_path, output_path)

    with fitz.open(output_path) as merged:
        texts = [page.get_text().strip() for page in merged]

    assert texts == ["VI-1", "EN-1", "VI-2", "VI-3"]


@pytest.mark.asyncio
async def test_create_bilingual_pdf_does_not_duplicate_embedded_fonts(tmp_path: Path) -> None:
    """US-16 v2 W4 (Architecture.md "US-16 v2 — Final Decision", decision
    W10-b): per-page `insert_pdf` copies the VI doc's embedded font once per
    page — a real 596-page job measured 592 duplicated font streams (9 real
    fonts x ~65 copies), 86.97 MB -> 7.40 MB after this fix. The correct
    fix is `garbage=4` (dedupes identical streams); `deflate=True` ALONE
    gives 0 byte benefit here (Architecture.md X6) — a size-only assertion
    would NOT catch a "helpful" simplification down to `deflate=True` alone,
    so this asserts the font stream count directly, per W4's explicit
    requirement."""
    vi_path = tmp_path / "vi.pdf"
    en_path = tmp_path / "en.pdf"
    output_path = tmp_path / "bilingual.pdf"

    _make_pdf_with_embedded_font(vi_path, 20)
    _make_pdf_with_embedded_font(en_path, 20)

    real_font_stream_count = _count_length1_font_streams(vi_path)
    assert real_font_stream_count >= 1

    await create_bilingual_pdf(vi_path, en_path, output_path)

    # Without garbage=4, this would be 40 (20 pages x 2 docs, each page's
    # insert_pdf call re-embedding the font) — verified by temporarily
    # reverting the fix and re-running this test during implementation.
    assert _count_length1_font_streams(output_path) <= real_font_stream_count
