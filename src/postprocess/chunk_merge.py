"""Merge translated chunk PDFs back into one file (BR-CHUNK-04, US-06).

Deviation from the literal `merge_chunk_pdfs(chunk_paths: list[Path],
output_path: Path)` signature suggested in the increment brief: "khong trung
lap overlap pages" is impossible to guarantee from bare paths alone — we need
to know how many of a chunk's *leading* pages are overlap-context duplicated
from the previous chunk (BR-CHUNK-03) so they can be skipped on merge. That
information lives on the `Chunk` DB row (`overlap_start`/`overlap_end`), so
this takes `Chunk` records (each carrying its own `output_path`) instead of
raw paths. Documented here per the "PHAI ghi ro ly do" instruction rather
than silently diverging.

Bug #7 fix (Protocol 5 R5-02/R5-03, verified with real `pdf2zh` output — see
`tests/fixtures/pdf2zh/README.md`): each chunk's `{stem}-mono.pdf` is NOT
scoped to that chunk's page range. `pdf2zh --pages A-B` returns the FULL
original document (every page of the source file passed to it), translating
only pages A-B and leaving every other page in the source language. The
previous implementation assumed `chunk_doc.page_count == chunk's own page
range` and sliced by *offset within the chunk file* (`skip_pages` counted
from page 0) — for a multi-chunk job this pulled in dozens of untranslated
trailing pages from every chunk, producing a merged file several times too
long with duplicated/out-of-order content (observed: 239 pages instead of 81
for a 3-chunk job). The fix instead slices by the chunk's *absolute page
numbers in the original document* (`page_start`/`page_end`, minus the
overlap-context pages already emitted by the previous chunk), since the
mono.pdf's page N (0-indexed N-1) always corresponds to the source
document's page N.
"""

from collections.abc import Sequence
from pathlib import Path

import fitz  # PyMuPDF

from src.models.chunk import Chunk


class ChunkMergeError(RuntimeError):
    """Raised when a chunk record is missing its rendered output file."""


async def merge_chunk_pdfs(chunks: Sequence[Chunk], output_path: str | Path) -> None:
    """Concatenate chunk PDFs in `chunk_index` order, dropping each chunk's
    leading overlap pages (already present as the tail of the previous
    chunk) so the merged document has no duplicate pages.

    Each `{stem}-mono.pdf` contains every page of the original source
    document (pdf2zh translates only the `--pages` range it was given, but
    still emits the full file) — so pages are selected by their *absolute*
    1-indexed position in the source document (`page_start`..`page_end`,
    trimmed to `overlap_end + 1`..`page_end` for non-first chunks), not by
    an offset into the chunk's own output file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    output_doc = fitz.open()
    try:
        for position, chunk in enumerate(ordered):
            if not chunk.output_path:
                raise ChunkMergeError(f"Chunk {chunk.chunk_index} has no output_path set")

            actual_start = chunk.page_start
            if (
                position > 0
                and chunk.overlap_start is not None
                and chunk.overlap_end is not None
            ):
                actual_start = chunk.overlap_end + 1

            if actual_start > chunk.page_end:
                continue

            with fitz.open(chunk.output_path) as chunk_doc:
                from_page = actual_start - 1
                to_page = min(chunk.page_end, chunk_doc.page_count) - 1

                if from_page >= chunk_doc.page_count or to_page < from_page:
                    continue
                output_doc.insert_pdf(chunk_doc, from_page=from_page, to_page=to_page)

        output_doc.save(output_path)
    finally:
        output_doc.close()
