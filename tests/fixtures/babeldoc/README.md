# babeldoc golden fixtures (Bug #8, Protocol 5 R5-02/R5-03)

`job3594a7a3_chunk0_sample_mono.pdf` / `job3594a7a3_chunk1_sample_mono.pdf` are small
extracts (via PyMuPDF `insert_pdf`, no hand-typed text) taken directly from the real
`translate_pages()` output of a completed production job that used
`pdf_translate_engine="babeldoc"`.

## Nguồn xác thực

- **Job**: `3594a7a3-8b72-4390-9d9b-159769a2a215` (real book, 415 pages, 11 chunks,
  `actual_cost=$2.08`, `status=completed`), DB row read from `data/bb_translation.db`
  on 2026-09-06.
- **Real chunk files** (verified live with PyMuPDF `fitz.open(...).page_count`):
  - `chunk_0` (`page_start=1, page_end=40`): real file has exactly 40 pages.
  - `chunk_1` (`page_start=39, page_end=80`, overlap `39-40`): real file has exactly
    42 pages.
- This is the observation behind Bug #8: `chunk_doc.page_count` equals
  `page_end - page_start + 1` (this chunk's own range), NOT the source document's
  total page count (415) — the opposite shape from the `tests/fixtures/pdf2zh/`
  fixtures, which verified raw `pdf2zh` CLI emits the FULL document per chunk.

## Sample contents

- `job3594a7a3_chunk0_sample_mono.pdf` (5 pages): local pages 0-2 (== absolute source
  pages 1-3) plus local pages 38-39 (== absolute source pages 39-40, the overlap tail
  chunk 1 re-translates).
- `job3594a7a3_chunk1_sample_mono.pdf` (4 pages): local pages 0-3 (== absolute source
  pages 39-42).

Used by `tests/test_chunk_merge.py::test_merge_chunk_pdfs_golden_fixture_real_babeldoc_output`
to assert `merge_chunk_pdfs` correctly auto-detects the chunk-scoped shape and slices by
offset relative to `chunk.page_start`, instead of the absolute-indexing formula that
caused Bug #8.
