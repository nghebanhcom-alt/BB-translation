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
            # US-16 v2 W4 (Architecture.md, decision W10-b): per-page
            # insert_pdf duplicates the VI doc's embedded fonts once per
            # page (measured: 9 real font streams -> 592 copies on a
            # 596-page job). `garbage=4` is the parameter that dedupes them
            # (86.97 MiB -> 7.40 MiB measured); `deflate=True` alone gives 0
            # byte benefit here since every stream is already Flate — kept
            # anyway, it's free and matches the save call `compress_pdf_images`
            # uses elsewhere in this pipeline.
            output_doc.save(output_path, garbage=4, deflate=True)
        finally:
            output_doc.close()
