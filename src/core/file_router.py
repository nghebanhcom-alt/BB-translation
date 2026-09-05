from enum import StrEnum
from pathlib import Path

import fitz  # PyMuPDF

# BR-INPUT-02: PDF with text layer on > 90% of pages -> born-digital, otherwise scan.
_DIGITAL_TEXT_PAGE_RATIO = 0.9


class FileType(StrEnum):
    PDF_DIGITAL = "pdf_digital"
    PDF_SCAN = "pdf_scan"
    EPUB = "epub"


class UnsupportedFileTypeError(ValueError):
    """Raised for extensions other than .pdf / .epub (BR-INPUT-04)."""


class InvalidFileError(ValueError):
    """Raised when a file has an accepted extension (e.g. `.pdf`) but its
    content is not actually a readable file of that type (corrupt, truncated,
    or a renamed file of a different format) — Bug #1, QA Round 1.
    """


def detect_file_type(file_path: Path) -> FileType:
    suffix = file_path.suffix.lower()
    if suffix == ".epub":
        return FileType.EPUB
    if suffix == ".pdf":
        return _detect_pdf_type(file_path)
    raise UnsupportedFileTypeError(f"Chi ho tro PDF va EPUB, nhan duoc: {suffix or '(no extension)'}")


def _detect_pdf_type(file_path: Path) -> FileType:
    # PyMuPDF raises RuntimeError (e.g. `pymupdf.FileDataError`) for a `.pdf`
    # extension whose content isn't actually a valid PDF — corrupt, truncated,
    # or a renamed file of a different format. Left uncaught, this surfaced
    # as a raw 500 all the way to the client (Bug #1, QA Round 1) instead of
    # the same 400 contract every other reject path in this module already
    # follows.
    try:
        with fitz.open(file_path) as doc:
            total_pages = doc.page_count
            if total_pages == 0:
                return FileType.PDF_SCAN
            pages_with_text = sum(1 for page in doc if page.get_text().strip())
    except RuntimeError as exc:
        raise InvalidFileError("File PDF bi hong hoac khong doc duoc, vui long kiem tra lai file") from exc

    ratio = pages_with_text / total_pages
    return FileType.PDF_DIGITAL if ratio > _DIGITAL_TEXT_PAGE_RATIO else FileType.PDF_SCAN
