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
`tests/fixtures/pdf2zh/README.md`): at the time, each chunk's `{stem}-mono.pdf`
was NOT scoped to that chunk's page range. `pdf2zh --pages A-B` returned the
FULL original document (every page of the source file passed to it),
translating only pages A-B and leaving every other page in the source
language. The fix at the time switched from slicing by *offset within the
chunk file* to slicing by the chunk's *absolute page numbers in the original
document*, since the mono.pdf's page N (0-indexed N-1) matched the source
document's page N.

Bug #8 fix (found 2026-09-06 re-merging a real 415-page/11-chunk job run with
`pdf_translate_engine="babeldoc"` — Architecture.md 6.14.7 default: output had
only 42 pages instead of 415): the Bug #7 assumption does not hold for every
engine. `babeldoc`'s CLI (unlike raw `pdf2zh` v1.9.11, which the Bug #7
fixture verified) scopes each chunk's rendered output to just that chunk's
own page range (`chunk_doc.page_count == page_end - page_start + 1`), so page
N of the chunk file is *not* the source document's page N; it's
`page_start + N`. Indexing with the Bug #7 formula (absolute page number
minus 1) into a chunk-scoped file grabbed the wrong 1-2 trailing pages from
every chunk after the first instead of the intended 40.

`JobOrchestrator._translator_runner` can select either engine per job
(Architecture.md 6.14.7), and nothing here is told which one produced a given
chunk's file, so this function detects the shape per chunk instead of
assuming one: if `chunk_doc.page_count >= chunk.page_end`, the file holds the
full source document (Bug #7 shape, absolute indexing); otherwise it holds
only this chunk's own range (Bug #8 shape, indexing relative to
`chunk.page_start`). This can't misfire except when `chunk.page_start == 1`
(only the first chunk of a job), where the two formulas agree by
construction (`page_end - page_start + 1 == page_end` when `page_start == 1`,
so a chunk-scoped file also satisfies `page_count >= page_end`) and produce
the same slice either way. A per-engine golden fixture under
`tests/fixtures/` for each shape (Protocol 5 R5-03) is what should have
caught this before a real job ran on it — `tests/fixtures/pdf2zh/` only ever
covered the pdf2zh shape.
"""

import logging
from collections.abc import Sequence
from pathlib import Path

import fitz  # PyMuPDF

from src.core.chunking import surviving_page_range
from src.models.chunk import Chunk

logger = logging.getLogger(__name__)


class ChunkMergeError(RuntimeError):
    """Raised when a chunk record is missing its rendered output file."""


async def merge_chunk_pdfs(chunks: Sequence[Chunk], output_path: str | Path) -> None:
    """Concatenate chunk PDFs in `chunk_index` order, dropping each chunk's
    leading overlap pages (already present as the tail of the previous
    chunk) so the merged document has no duplicate pages.

    Each chunk's rendered file is either scoped to just that chunk's own page
    range (babeldoc) or contains the full source document (raw pdf2zh) — see
    Bug #7/#8 notes above — so the indexing scheme is auto-detected per chunk
    from `chunk_doc.page_count` rather than assumed.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ordered = sorted(chunks, key=lambda c: c.chunk_index)
    output_doc = fitz.open()
    try:
        for position, chunk in enumerate(ordered):
            if not chunk.output_path:
                raise ChunkMergeError(f"Chunk {chunk.chunk_index} has no output_path set")

            # BL-04 (Architecture.md 6.22.5.1): `position != chunk.chunk_index`
            # would mean `surviving_page_range(..., is_first_in_merge=(position
            # == 0))` disagrees with the SAME call
            # `JobOrchestrator._process_chunk()` makes with `is_first_in_merge
            # =(chunk.chunk_index == 0)` — a bug of a missing chunk, not
            # something to silently tolerate. Same warning style as the
            # "contributed 0 pages" case below.
            if position != chunk.chunk_index:
                logger.warning(
                    "merge_chunk_pdfs: chunk order mismatch — position=%s nhung "
                    "chunk_index=%s (Architecture.md 6.22.5.1 bat bien 'du chunk, "
                    "khong thieu'). surviving_page_range() dung is_first_in_merge="
                    "(position==0), co the SAI neu thieu chunk.",
                    position,
                    chunk.chunk_index,
                )

            actual_start, _ = surviving_page_range(chunk, is_first_in_merge=(position == 0))

            if actual_start > chunk.page_end:
                continue

            with fitz.open(chunk.output_path) as chunk_doc:
                if chunk_doc.page_count >= chunk.page_end:
                    # Full-document shape (Bug #7, raw pdf2zh): chunk_doc page
                    # N-1 IS absolute source page N.
                    from_page = actual_start - 1
                    to_page = min(chunk.page_end, chunk_doc.page_count) - 1
                else:
                    # Chunk-scoped shape (Bug #8, babeldoc): chunk_doc page 0
                    # is absolute source page `chunk.page_start`.
                    from_page = actual_start - chunk.page_start
                    to_page = (
                        min(chunk.page_end, chunk.page_start + chunk_doc.page_count - 1)
                        - chunk.page_start
                    )

                if from_page >= chunk_doc.page_count or to_page < from_page:
                    # Reviewer note (2026-09-06, chunk_merge Bug #8 fix): a
                    # silent `continue` here is the exact failure mode class
                    # that let Bug #8 through undetected until someone
                    # manually counted pages — log it so it surfaces sooner.
                    logger.warning(
                        "merge_chunk_pdfs: chunk %s contributed 0 pages "
                        "(from_page=%s, to_page=%s, chunk_doc.page_count=%s, "
                        "page_start=%s, page_end=%s) — output_path=%s",
                        chunk.chunk_index,
                        from_page,
                        to_page,
                        chunk_doc.page_count,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.output_path,
                    )
                    continue
                output_doc.insert_pdf(chunk_doc, from_page=from_page, to_page=to_page)

        output_doc.save(output_path)
    finally:
        output_doc.close()
