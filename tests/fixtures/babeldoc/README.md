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

## Fixtures cho RCA "Text Overlap, Content-Loss & Reading-Order" (2026-09-07)

Trích trực tiếp từ `data/uploads/f88282bb-…_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf`
(job `136645f9-ffe8-4927-afb2-b725236ede44`) bằng `pymupdf.insert_pdf`, KHÔNG chỉnh sửa.

| File | Trang gốc (0-index) | Dùng để tái hiện |
|------|--------------------|------------------|
| `rotated_text_p67_source.pdf` | 66 | Khối chú giải nghiêng ~-11° (`dir=(0.982,-0.191)`) bị babeldoc 0.6.4 loại bỏ hoàn toàn (`il_creater.py:968-974`) |
| `rotated_chart_p15_source.pdf` | 14 | Bảng quy đổi đặt nghiêng — mất 39/58 block |
| `toc_2col_p7_source.pdf` | 6 | Mục lục 2 cột; render ĐÚNG khi chạy 1 trang, SAI trong production → dùng cho A/B ở G3 |

Xem `docs/Architecture.md` section "Root Cause Analysis: Text Overlap, Content-Loss &
Reading-Order trên trang layout phức tạp (2026-09-07)".

## Fixtures cho Bug #7 Ca C — TOC-1 v2 spike 7.4-a (Dev, 2026-09-08)

8 file `toc_*_dump.json.gz` + 6 PDF nguồn trong `toc_sources/`, dùng để đo lại đúng oracle
"Bug #7 Ca C — Quyết định cuối..." AA7/AA8/AA9 trong `docs/Architecture.md`. Nguồn gốc (theo
AA8 bước 1 — artifact tạm ở `/tmp`/scratchpad phiên trước, đã kiểm tra còn sống 2026-09-08
trước khi commit):

| Fixture (`.json.gz`) | Nguồn `paragraph_finder.json` | PDF nguồn (`toc_sources/`) |
|---|---|---|
| `toc_lcb_contents_p6_p7_dump.json.gz` | `<SP>/wd/lcb_toc/lcb_toc/` | `lcb_toc.pdf` (LCB idx 6-7) |
| `toc_friberg_contents_dump.json.gz` | `<SP>/wd/friberg_toc/friberg_toc/` | `friberg_toc.pdf` (Friberg idx 6) |
| `toc_lcb_index_dump.json.gz` | `<SP>/wd/lcb_index/lcb_index/` | `lcb_index.pdf` (LCB idx 408) |
| `toc_figoni_p25_recipe_dump.json.gz` | `<SP>/wd/figoni_p25_recipe/.../` | `figoni_p25_recipe.pdf` (Figoni idx 40) |
| `toc_figoni_p45_recipe_dump.json.gz` | `<SP>/wd/figoni_p45_recipe/.../` | `figoni_p45_recipe.pdf` (Figoni idx 60) |
| `toc_figoni_tables_dump.json.gz` | `<SP>/wd/figoni_p7_tables/.../` | `figoni_p7_tables.pdf` (Figoni idx 22) |
| `toc_figoni_contents_p7_dump.json.gz` | `/tmp/bdprobe/wd_toc/figoni_p7_toc/` | (không copy PDF riêng — trùng nguồn Figoni đầy đủ, xem log spike) |
| `toc_figoni_contents_p8_dump.json.gz` | `/tmp/bdprobe/wd_toc2/figoni_p8_toc/` | (như trên) |

`<SP>` = `/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad`.
Tất cả sinh từ `babeldoc --debug` thật (flag production của `BabeldocRunner`), LLM port chết
(`http://127.0.0.1:1/v1`) ⇒ **0 token** tốn, `--ignore-cache`. Lệnh tái tạo đầy đủ: xem
`<SP>/run_all.sh` (2 fixture `figoni_p7_toc`/`figoni_p8_toc` dùng lệnh tương tự, working-dir
`wd_toc`/`wd_toc2`, không có trong `run_all.sh` vì chạy ở phiên trước đó).

Nếu nguồn gốc `<SP>`/`/tmp/bdprobe` đã mất: trích lại trang bằng `pymupdf.insert_pdf` từ
`data/uploads/` — Figoni bản đầy đủ idx 40/60/22 (0-index), Le Cordon Bleu idx 6-7/408,
Bo Friberg idx 6 — rồi chạy lại `babeldoc --debug` với flag production ở trên. **Tuyệt đối
không viết tay mock nội dung** (Protocol 5 mục 3) — dump JSON phải là output thật của babeldoc.

Dùng bởi `scripts/toc_split_spike_measure.py` (script đo, không phải test chính thức — 7.4-c
sẽ có `tests/test_babeldoc_toc_split.py` viết trên đúng các fixture này sau khi spike PASS).
