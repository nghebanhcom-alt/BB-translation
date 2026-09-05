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

            pages_with_text = 0
            # Bug thuc te 2026-09-05 ("How Baking Works", verify song bang
            # PyMuPDF tren file upload that): mot cuon sach born-digital that
            # (font nhung Palatino/Futura, doc duoc ngay bang pdfminer) van
            # co the co vai trang KHONG CO CHU DE DICH hop le — bia, trang
            # phan chuong trang trong voi hinh minh hoa (anh nguyen trang HOAC
            # chi ve vector, khong chu). Cong thuc cu (`pages_with_text /
            # total_pages`) tinh nhung trang do la "thieu text", keo ty le
            # xuong duoi nguong va phan loai NHAM ca file thanh `pdf_scan`
            # (do thuc te: 21/25 trang co text, 4 trang khong chu -> ty le
            # 0.84 < 0.9). Trang khong text nhung CO anh hoac CHI CO hinh ve
            # vector (`get_drawings()`) thi loai khoi mau so — khong the OCR
            # ra chu vi khong co chu that su (anh la trang trai/minh hoa,
            # hinh ve vector khong phai anh quet), nen khong nen tinh la
            # "thieu text can OCR". Lan tai hien 2026-09-06 (live A/B qua
            # babeldoc + MinerU that): 4/25 trang chi co drawings (vd trang
            # phan chuong) van lot qua nhanh `pages_image_only` cu (chi check
            # anh) va keo file vao OCR bridge oan, gay mat doan van + typeset
            # sai (heading gay giua tu) khi babeldoc render ban OCR-reconstruct
            # thay vi PDF goc — xac nhan bang cach dich truc tiep PDF goc
            # (khong qua OCR bridge) cho ra output dung/du hoan toan.
            pages_without_translatable_content = 0
            for page in doc:
                if page.get_text().strip():
                    pages_with_text += 1
                elif page.get_images(full=False) or page.get_drawings():
                    pages_without_translatable_content += 1
    except RuntimeError as exc:
        raise InvalidFileError("File PDF bi hong hoac khong doc duoc, vui long kiem tra lai file") from exc

    countable_pages = total_pages - pages_without_translatable_content
    # countable_pages == 0 nghia la MOI trang deu khong co chu de dich (khong
    # con trang nao de xet ty le) — vd 1 cuon sach quet tung trang thanh anh
    # nguyen trang, dung la pdf_scan that su.
    ratio = pages_with_text / countable_pages if countable_pages > 0 else 0.0
    return FileType.PDF_DIGITAL if ratio > _DIGITAL_TEXT_PAGE_RATIO else FileType.PDF_SCAN
