from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.bilingual_merge import create_bilingual_pdf


def _make_pdf(path: Path, labels: list[str]) -> None:
    doc = fitz.open()
    for label in labels:
        page = doc.new_page()
        page.insert_text((50, 100), label, fontsize=14)
    doc.save(path)
    doc.close()


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
