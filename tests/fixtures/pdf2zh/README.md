# pdf2zh golden fixtures (Protocol 5 R5-02/R5-03/R6-02)

Bug #7 fix: `src/postprocess/chunk_merge.py` từng giả định mỗi chunk's `{stem}-mono.pdf`
chỉ chứa đúng số trang trong phạm vi `--pages` yêu cầu. Đây là giả định KHÔNG được verify
với `pdf2zh` thật (Dev vòng trước chỉ viết mock tự bịa theo giả định đó). Các file dưới đây
là output THẬT từ `pdf2zh` CLI, dùng làm golden-file cho `tests/test_chunk_merge.py`.

## Nguồn xác thực

- **pdf2zh version**: `pdf2zh v1.9.11` (`pdf2zh --version`, cài qua `uv tool install`,
  binary tại `/Users/hieutt/.local/share/uv/tools/pdf2zh/bin/pdf2zh`)
- **Ngày tạo**: 2026-09-04
- **Translator dùng**: `-s google` (Google Translate, miễn phí, không cần API key) — tránh
  tốn tiền LLM thật chỉ để verify shape output.

## Cách tạo

1. Tạo file nguồn `6page_source.pdf` (6 trang, mỗi trang 1 câu ngắn khác nhau
   `Page {n} unique marker abc{n}xyz.`) bằng PyMuPDF:

   ```python
   import fitz
   doc = fitz.open()
   for n in range(1, 7):
       page = doc.new_page()
       page.insert_text((72, 100), f"Page {n} unique marker abc{n}xyz.", fontsize=16)
   doc.save("6page_source.pdf")
   ```

2. Chạy pdf2zh THẬT với 2 range chồng lấn, mô phỏng đúng overlap logic của
   `calculate_chunks()` (`src/core/chunking.py`):

   ```bash
   pdf2zh 6page_source.pdf -li en -lo vi -s google --pages 1-3 --output out_range1
   pdf2zh 6page_source.pdf -li en -lo vi -s google --pages 3-6 --output out_range2
   ```

3. Copy `{stem}-mono.pdf` từ mỗi output dir:
   - `out_range1/6page-mono.pdf` → `6page_range1-3_mono.pdf`
   - `out_range2/6page-mono.pdf` → `6page_range3-6_mono.pdf`

   (`{stem}-dual.pdf` không cần, chunk_merge chỉ dùng `-mono.pdf`.)

## Quan sát thật (đã verify bằng PyMuPDF `get_text()` từng trang)

`6page_range1-3_mono.pdf` (chạy `--pages 1-3`):

| Trang | Nội dung |
|---|---|
| 1 | "Trang 1 điểm đánh dấu duy nhất abc1xyz." (đã dịch) |
| 2 | "Trang 2 điểm đánh dấu duy nhất abc2xyz." (đã dịch) |
| 3 | "Trang 3 điểm đánh dấu duy nhất abc3xyz." (đã dịch) |
| 4 | "Page 4 unique marker abc4xyz." (**tiếng Anh gốc, CHƯA dịch**) |
| 5 | "Page 5 unique marker abc5xyz." (tiếng Anh gốc) |
| 6 | "Page 6 unique marker abc6xyz." (tiếng Anh gốc) |

`6page_range3-6_mono.pdf` (chạy `--pages 3-6`):

| Trang | Nội dung |
|---|---|
| 1 | "Page 1 unique marker abc1xyz." (tiếng Anh gốc) |
| 2 | "Page 2 unique marker abc2xyz." (tiếng Anh gốc) |
| 3 | "Trang 3 điểm đánh dấu duy nhất abc3xyz." (đã dịch) |
| 4 | "Trang 4 điểm đánh dấu duy nhất abc4xyz." (đã dịch) |
| 5 | "Trang 5 điểm đánh dấu duy nhất abc5xyz." (đã dịch) |
| 6 | "Trang 6 điểm đánh dấu duy nhất abc6xyz." (đã dịch) |

**Kết luận xác nhận đúng root cause QA Vòng 5 (Bug #7)**: `{stem}-mono.pdf` do `pdf2zh`
xuất ra LUÔN chứa **toàn bộ N trang của tài liệu gốc** (ở đây N=6), không phải chỉ riêng
phạm vi `--pages` đã yêu cầu — chỉ các trang trong phạm vi `--pages` được dịch, các trang
còn lại giữ nguyên ngôn ngữ nguồn. `merge_chunk_pdfs()` phải cắt đúng phạm vi
`page_start`/`page_end` (trừ overlap) của từng chunk từ file `mono.pdf` đầy đủ này, không
được dùng `chunk_doc.page_count` để suy luận phạm vi.

## Verify lại

Nếu đổi version `pdf2zh`, phải chạy lại đúng 2 lệnh ở bước 2 và so sánh lại bảng quan sát
trên (Protocol 5 R5-05: đổi version tool bên thứ 3 phải verify lại toàn bộ contract liên
quan, không kế thừa nguồn xác thực cũ).
