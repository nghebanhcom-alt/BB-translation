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

## Fixtures cho US-16 v2 (2026-09-08)

`docs/Architecture.md` mục "US-16 v2 — Final Decision sau phản biện Domain Expert" (W8) yêu cầu
2 fixture vàng mới trích trực tiếp từ output job thật (Protocol 5 R5-03 / Protocol 6 R6-02),
dùng bởi `tests/test_image_compress.py`.

### `job78674af9_flate_sample.pdf`

- **Job**: `78674af9-ce15-4d39-bba5-7f8d1e2804fe` (30 trang, 46.87 MB, `status=completed`) —
  chính job motivate US-16 v2 (Architecture.md V1: chạy `compress_pdf_images()` v1 trên job này
  cho `recompressed=0` vì 85% dung lượng nằm ở ảnh `/FlateDecode`, filter mà v1 coi là "đã nén,
  bỏ qua").
- **Nguồn**: `data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf`.
- **Trang gốc (0-based)**: 22 và 25.
- **Ngày trích**: 2026-09-08.
- **Lệnh trích** (PyMuPDF, không chỉnh sửa tay):
  ```python
  import fitz
  doc = fitz.open("data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf")
  out = fitz.open()
  out.insert_pdf(doc, from_page=22, to_page=22)
  out.insert_pdf(doc, from_page=25, to_page=25)
  out.save("tests/fixtures/babeldoc/job78674af9_flate_sample.pdf", garbage=4, deflate=True)
  ```
- **Nội dung xác nhận sau khi trích** (đọc trực tiếp bằng `get_page_images(..., full=True)` +
  `xref_get_key`): 1.75 MB, 2 trang, 3 ảnh — xref 10 `/FlateDecode` `ICCBased` (Gray, ~122 KB,
  khắc nét/engraving), xref 51 `/FlateDecode` `ICCBased` (CMYK, ~835 KB, ảnh chụp), xref 13
  `/DCTDecode` `DeviceGray` (đã nén sẵn, phải giữ nguyên byte). Đúng như mô tả tại
  Architecture.md V10.1 (chênh lệch byte nhỏ so với số đo gốc của Tech Lead là do 2 lần trích
  độc lập, không ảnh hưởng tới nội dung/guard được test).
- **Dùng để test**: eligibility filter mở rộng sang `/FlateDecode`, guard colorspace giữ
  `ICCBased`, không ghi đè `/ColorSpace`, dọn `/Decode`, guard `/Mask` (qua inject).

### `job136645f9_indexed_sample.pdf`

- **Job**: `136645f9-ffe8-4927-afb2-b725236ede44` (418 trang, 520.14 MB).
- **Nguồn**: `data/outputs/136645f9-ffe8-4927-afb2-b725236ede44/translated_vi.pdf`.
- **Trang gốc (0-based)**: 168.
- **Ngày trích**: 2026-09-08.
- **Lệnh trích**:
  ```python
  import fitz
  doc = fitz.open("data/outputs/136645f9-ffe8-4927-afb2-b725236ede44/translated_vi.pdf")
  out = fitz.open()
  out.insert_pdf(doc, from_page=168, to_page=168)
  out.save("tests/fixtures/babeldoc/job136645f9_indexed_sample.pdf", garbage=4, deflate=True)
  ```
- **Nội dung xác nhận sau khi trích**: 1.15 MB, 1 trang, 12 ảnh — 5 ảnh `/FlateDecode` colorspace
  `Indexed` (373–432 byte raw) + 6 ảnh `/DCTDecode` `DeviceCMYK` + 1 ảnh `/FlateDecode`
  `DeviceCMYK` (82 byte, bị guard nở file chặn ở `min_recompress_bytes=0`).
- **Dùng để test (W8 #9 — BLOCKING)**: đây là bằng chứng dữ liệu thật DUY NHẤT rằng guard
  colorspace allowlist đọc `info[5]` (không phải `Pixmap.colorspace.name`) thực sự chặn được ảnh
  `Indexed` — `Pixmap.colorspace.name` không bao giờ trả `'Indexed(...)'` vì PyMuPDF tự expand
  Indexed sang base colorspace ngay khi dựng `Pixmap` (Architecture.md W1/X2). Test gọi với
  `min_recompress_bytes=0` để cô lập đúng guard colorspace, không lẫn với guard kích thước.

### `drop_report_v2.jsonl`

- **Job**: live E2E gate BL-04 (Architecture.md 6.22.9, X8 harness) — `JobOrchestrator._process_chunk()`
  gọi TRỰC TIẾP (không qua `run_job()`), `chunk_index=5, page_start=199, page_end=240,
  overlap_start=199, overlap_end=200`, engine `babeldoc` 0.6.4, model `deepseek`, nguồn
  `data/uploads/f07b3194-b98e-4227-9516-198c6c91ff75_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations
  (1).pdf` (418 trang) — script tái tạo: `scripts/bl04_live_e2e_chunk5.py`.
- **Ngày trích**: 2026-09-11.
- **Nguồn**: copy nguyên văn sidecar JSONL thật do `BabeldocRunner` ghi ra (không sửa tay) tại
  `data/bl04_live_e2e/processing/<job_id>/chunk_5/<stem>.199-240.drops.jsonl` sau khi
  `process.wait()`.
- **Nội dung xác nhận**: 4 dòng `header` (multiprocessing worker, `pid` khác nhau — đúng thiết kế
  "không giả định chỉ 1 dòng header", Architecture.md 6.22.4), 42 dòng `page` (199-240 đủ 42/42,
  `dropped_count=0` cho MỌI trang kể cả trang 230). **Không có dòng `type=drop` nào** — lần chạy
  live này KHÔNG tái hiện được ca drop kênh (1) mà Domain Expert từng đo trên job `1ee1fdee` (xem
  Architecture.md 6.22.9 "Nếu không tái hiện được... không kết luận thiết kế sai", dịch máy không
  tất định). **Đã xác nhận bằng PyMuPDF** (mở `chunk.output_path`, trang index 31 = trang nguồn
  230): đoạn sidebar 614 ký tự ("The term feuilletage appeared in the 15th century...") THẬT SỰ
  vắng mặt khỏi bản dịch — nhưng đây là kênh (2) (BL-08, ngoài phạm vi BL-04), KHÔNG phải kênh (1)
  mà file sidecar này đo — khớp với `dropped_count=0` ở trang 230 trong chính file này và với ghi
  chú phạm vi trong log R-1 ("chữ bị lọc ở `ActiveILCreater.project_native_char`... KHÔNG được đo
  bởi cơ chế này"). Đã thử thêm 1 lần live fallback (b) — `scripts/bl04_live_e2e_synthetic_drop.py`,
  PDF 1 trang tái tạo đúng hình học (bbox 61.5,223.6,332.3,466.6, 271×243pt) + đúng 614 ký tự gốc —
  babeldoc KHÔNG dịch trang này (giữ nguyên tiếng Anh, `dropped_count=0`), nhiều khả năng do trang
  đơn lẻ không có ngữ cảnh layout xung quanh khiến bộ phân loại layout của babeldoc xử lý khác đi;
  không kết luận được gì thêm từ lần thử này, không lặp lại thêm (chi phí gọi API thật).
- **Dùng để test**: gate test 1 (`test_drop_report_parse`, §6.22.9) — CHỈ phủ được nhánh
  `header`/`page`/`observed_pages`/`available=True` từ dữ liệu thật; nhánh `type=drop` (field
  `text_excerpt`, v.v.) vẫn dựa vào unit test hiện có
  (`test_parse_drop_report_file_reads_real_written_file`,
  `tests/test_babeldoc_runner.py`) — dùng dữ liệu MÔ PHỎNG đúng schema đã verify qua source
  (Architecture.md 6.22.4/6.22.5, R5-01), không phải byte live-capture, vì 2 lần thử live ở trên
  đều không tạo ra dòng `drop` thật nào để capture.
