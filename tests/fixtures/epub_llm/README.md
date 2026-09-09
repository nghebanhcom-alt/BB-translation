# EPUB batch translate — golden fixture (Protocol 5 mục 3)

Contract JSON app↔LLM (`build_epub_batch_prompt()`/`parse_epub_batch_response()`,
Architecture.md 6.20.12 X4) là **external contract** — định dạng thật LLM trả về không do
team kiểm soát. File dưới đây được capture từ **1 lần gọi thật** tới DeepSeek, KHÔNG viết tay.

## `deepseek_batch_response_sourdough_ch1_5units.json`

- **Ngày chạy**: 2026-09-09.
- **Provider/model**: `deepseek` / `deepseek-chat` (repoint server-side sang `deepseek-v4-flash`,
  xem `src/services/deepseek_provider.py`), qua `ProviderFactory.create("deepseek", settings)` với
  `DEEPSEEK_API_KEY` thật trong `.env`.
- **Nguồn**: 5 unit thật lấy từ `EpubDocument.load()` trên
  `data/uploads/9d436d7b-…_Baking with Sourdough - Sara Pitzer.epub`, `ops/xhtml/chapter01.html`
  ordinal 16/17/18/87/288 — chọn để phủ đúng 6 bước spike a→f của Architecture.md 6.20.10 mục 1:
  1 heading có `<a id="page_4"/>`, 1 danh sách nguyên liệu `<strong>…</strong><br/>` × 4 (bước d),
  1 đoạn văn thường (không markup), 1 dòng phân số thuần `<sup>1</sup>/<sub>3</sub>` và 1 dòng hỗn
  số `1<sup>1</sup>/<sub>3</sub>` (bước c — ca N-1 Tech Lead đã cảnh báo: chỉ đúng nếu `1` đứng
  trước `<sup>` không bị gộp thành `11/3`).
- **Request thật**: đúng payload `build_epub_batch_prompt()` → `provider.translate(payload_json,
  system_prompt, "en", "vi")` qua `with_retry()`, id ngắn cục bộ `0..4` (X4/X5). `system_prompt`
  xác nhận chứa marker `BB-EPUB-JSON-CONTRACT-X4` (`system_prompt_marker_check: true`).
- **Kết quả**: JSON object sạch, KHÔNG có markdown code fence, KHÔNG lời dẫn, đủ 5/5 id, giữ
  nguyên `<strong>`/`<br/>`/`<sup>`/`<sub>`/`<a id=…>` đúng số lượng và vị trí, không đổi số. Dòng
  hỗn số ra đúng `1<sup>1</sup>/<sub>3</sub>` (không bị gộp `11/3`).
- **Chi phí thật đã tốn**: `input_tokens=1456`, `output_tokens=459`,
  **`estimated_cost_usd=0.00062326`** (≈ 0,06 cent USD — script chỉ gọi API đúng 1 lần).
- **Script capture** (không lưu trong repo, chạy 1 lần trong scratchpad phiên Dev): load
  `EpubDocument`, build `payload_json` từ 5 unit trên, `build_system_prompt()` (glossary rỗng —
  DB trống, chỉ cần glossary_prompt thật, không cần glossary entry cụ thể) →
  `build_epub_batch_prompt()`, gọi `provider.translate()` qua `with_retry()`, ghi thẳng
  `TranslationResult.text` (raw, CHƯA parse) vào `raw_response_text` của fixture này.

Dùng bởi `tests/test_epub_batch_golden_fixture.py`: `parse_epub_batch_response()` chạy trên
CHÍNH `raw_response_text` này (không phải chuỗi viết tay), assert đủ 5/5 id, nội dung giữ đúng
`<strong>`/`<sup>`/`<sub>`/`<br/>`, và dòng hỗn số không bị hỏng thành `11/3`.

## `deepseek_batch_response_sourdough_ch1_trailing_garbage.json`

**Bối cảnh**: bắt được khi Dev chạy live E2E full-book (`run_epub_job()` qua `JobOrchestrator`,
không mock) trên chính file Sourdough thật để verify guard BR-EPUB-05 sau khi sửa bug class
`_mark_bb_vi()` (US-22 Bước 2/3, vòng 1/3 review) — KHÔNG nằm trong scope 3 điểm review-report.md
yêu cầu sửa, là 1 phát hiện mới trong lúc verify.

- **Ngày chạy**: 2026-09-09.
- **Provider/model**: `deepseek` / `deepseek-chat`, qua `ProviderFactory.create("deepseek",
  settings)` với `DEEPSEEK_API_KEY` thật trong `.env` — giống hệt cách gọi thật của
  `_process_epub_chunk()`.
- **Nguồn**: 1 unit thật `ops/xhtml/chapter01.html#13` (đoạn văn dài, nhiều `<a href>` có thuộc
  tính `class` đã escape `\"`, số điện thoại, URL) — đúng unit đã làm `run_job()` full-book FAIL
  2 lần liên tiếp với lỗi `EpubBatchTranslationError` ("thieu ban dich cho 1 unit sau 1 vong goi
  lai rieng le") dù nội dung đã dịch đúng.
- **Phát hiện**: `raw_response_text` là 1 JSON object HỢP LỆ (`{"0": "..."}`), nhưng DeepSeek trả
  thừa đúng 1 ký tự `"` NGAY SAU dấu `}` đóng — `json.loads()` fail với `JSONDecodeError: Extra
  data at pos 1098`. Tái hiện **deterministic** (không phải flake) — gọi lại đúng unit này (kể cả
  ở request batch lẫn request retry lẻ trong `_process_epub_chunk()`) cho cùng 1 dạng lỗi cả 2
  lần trong `run_job()` full-book, và lần thứ 3 (capture fixture này) khi gọi tách riêng.
- **Hậu quả trước fix**: `parse_epub_batch_response()` coi TOÀN BỘ phản hồi là hỏng (`{}`, mọi id
  coi như thiếu) — vì lỗi lặp lại y hệt ở CẢ vòng gọi lại lẻ (X4), unit này luôn "thiếu bản dịch
  sau 1 vòng gọi lại riêng lẻ" → `EpubBatchTranslationError` → chunk `failed` → **job tốn tiền
  thật cho các request đã chạy trước đó trong chunk, rồi vẫn kết thúc `failed`** — cùng loại rủi ro
  tài chính mà bug chính của vòng review này (guard BR-EPUB-05) được sinh ra để chặn, chỉ khác điểm
  lỗi trong pipeline.
- **Fix**: `parse_epub_batch_response()` (`src/core/prompt_builder.py`) khi gặp
  `JSONDecodeError` với `msg == "Extra data"`, thử `json.loads()` lại đúng phần văn bản TRƯỚC vị
  trí lỗi (`text[:exc.pos]`) — nếu phần đó tự nó là JSON object hợp lệ thì dùng, nếu không mới trả
  `{}` như cũ. Một `JSONDecodeError` vì lý do KHÁC "Extra data" (vd JSON bị cắt cụt giữa chừng, hết
  `max_tokens`) vẫn trả `{}` như cũ — không nới lỏng cho trường hợp thực sự hỏng.
- **Chi phí thật đã tốn cho riêng fixture này**: `input_tokens=796`, `output_tokens=420`,
  **`estimated_cost_usd=0.00045232`** (~0,045 cent USD, 1 lần gọi). Ngoài ra 2 lần chạy
  `run_job()` full-book (fail ở chunk 0, trước khi phát hiện + sửa bug này) đã tốn thêm chi phí
  thật cho các request đã hoàn tất trong chunk 0 trước điểm fail — số tiền nhỏ, cùng cấp độ với
  golden fixture 5-unit gốc ở trên (~vài phần nghìn USD/request).

Dùng bởi `tests/test_epub_batch_golden_fixture.py` (3 test): xác nhận `raw_response_text` thật
sự làm `json.loads()` thô fail với "Extra data" (không phải fixture đã bị "dọn sạch" trước khi
lưu), và `parse_epub_batch_response()` sau fix trích đúng nội dung đã dịch từ chính response đó.
