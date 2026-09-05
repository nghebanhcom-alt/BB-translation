from pathlib import Path

import fitz
import pytest

from src.core.file_router import (
    FileType,
    InvalidFileError,
    UnsupportedFileTypeError,
    detect_file_type,
)


def _make_digital_pdf(path: Path) -> None:
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "Recipe: 480ml flour, 240ml milk.")
    doc.save(path)
    doc.close()


def _make_scan_pdf(path: Path) -> None:
    """Simulate a scanned PDF: pages carry only a blank image, no text layer."""
    doc = fitz.open()
    pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 100, 100), False)
    pixmap.set_rect(pixmap.irect, (255, 255, 255))
    for _ in range(3):
        page = doc.new_page()
        page.insert_image(page.rect, pixmap=pixmap)
    doc.save(path)
    doc.close()


def test_detect_pdf_digital(tmp_path: Path) -> None:
    pdf_path = tmp_path / "digital.pdf"
    _make_digital_pdf(pdf_path)

    assert detect_file_type(pdf_path) == FileType.PDF_DIGITAL


def test_detect_pdf_scan(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    _make_scan_pdf(pdf_path)

    assert detect_file_type(pdf_path) == FileType.PDF_SCAN


def test_detect_pdf_mixed_below_threshold(tmp_path: Path) -> None:
    """9/10 pages with text = 90% exactly, not > 90% -> still scan."""
    doc = fitz.open()
    for i in range(10):
        page = doc.new_page()
        if i < 9:
            page.insert_text((72, 72), "Some digital text.")
    pdf_path = tmp_path / "mixed.pdf"
    doc.save(pdf_path)
    doc.close()

    assert detect_file_type(pdf_path) == FileType.PDF_SCAN


def test_detect_pdf_digital_with_a_few_image_only_pages(tmp_path: Path) -> None:
    """Bug thuc te 2026-09-05 ("How Baking Works"): mot cuon sach born-digital
    that (21/25 trang co text) van bi phan loai nham thanh pdf_scan chi vi 4
    trang bia/phan chuong la anh nguyen trang khong co chu. Trang anh nguyen
    trang khong co gi de dich nen khong duoc tinh la "thieu text".
    """
    doc = fitz.open()
    pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 100, 100), False)
    pixmap.set_rect(pixmap.irect, (255, 255, 255))
    for i in range(25):
        page = doc.new_page()
        if i in (0, 5, 12, 20):  # 4 trang la anh nguyen trang, khong co chu
            page.insert_image(page.rect, pixmap=pixmap)
        else:
            page.insert_text((72, 72), "Recipe: 480ml flour, 240ml milk.")
    pdf_path = tmp_path / "digital_with_covers.pdf"
    doc.save(pdf_path)
    doc.close()

    assert detect_file_type(pdf_path) == FileType.PDF_DIGITAL


def test_detect_epub(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(b"fake epub content")

    assert detect_file_type(epub_path) == FileType.EPUB


def test_detect_unsupported_extension(tmp_path: Path) -> None:
    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("hello")

    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type(txt_path)


def test_detect_pdf_type_rejects_fake_pdf(tmp_path: Path) -> None:
    """Bug #1 (QA Round 1): a `.pdf` extension with non-PDF content must
    raise a clear `InvalidFileError`, not let PyMuPDF's `RuntimeError` bubble
    up uncaught.
    """
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_text("this is just plain text, not a real PDF")

    with pytest.raises(InvalidFileError):
        detect_file_type(fake_pdf)
