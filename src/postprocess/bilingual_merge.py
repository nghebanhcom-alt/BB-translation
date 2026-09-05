"""Bilingual output: interleave VI and EN pages (Architecture.md section 6.4, US-09)."""

from pathlib import Path

import fitz  # PyMuPDF


async def create_bilingual_pdf(
    vi_pdf_path: str | Path, en_pdf_path: str | Path, output_path: str | Path
) -> None:
    """Interleave translated (VI) and original (EN) pages: VI 1, EN 1, VI 2, EN 2, ..."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with fitz.open(vi_pdf_path) as vi_doc, fitz.open(en_pdf_path) as en_doc:
        output_doc = fitz.open()
        try:
            for i in range(len(vi_doc)):
                output_doc.insert_pdf(vi_doc, from_page=i, to_page=i)
                if i < len(en_doc):
                    output_doc.insert_pdf(en_doc, from_page=i, to_page=i)
            output_doc.save(output_path)
        finally:
            output_doc.close()
