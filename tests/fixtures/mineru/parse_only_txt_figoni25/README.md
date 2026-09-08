# US-15 (Markdown parse-only) golden fixture — `parse_method="txt"` (S15-6)

Captured from a real, live `MinerURunner.parse_document(parse_method="txt")` call against
the running MinerU 3.4.5 service at `localhost:8010` (Protocol 5 mục 3 — golden file, not a
hand-typed mock).

## Nguồn xác thực

- **File**: `data/uploads/0f92a0d4-7230-4465-abf6-3e11d66bae74_Figoni, Paula - How baking
  works_..._-1-25.pdf` (Figoni *How Baking Works*, 25 trang đầu, `file_type=pdf_digital`).
- **Task**: `cdbd0988-1182-456d-bf23-791e03490bc6`, `parse_method="txt"`, `elapsed_s=89.0`.
- **Ngày chạy**: 2026-09-08 (Domain Expert, phản biện US-15 §6.15, V-07 —
  `docs/expert-review-us15-markdown.md` Phụ lục A).
- **Nội dung**: `document.md` là output Markdown thật (54.243 ký tự, 660 dòng, 7 bảng HTML,
  16 ảnh tham chiếu). `middle.json` là output `middle_json` thật của MinerU cho lần chạy này
  (1004 span có key `score`: 998 span `score==1.0`, 6 span `<1.0`, min `0.0`).

## Vì sao fixture này tồn tại (S15-6)

Bản gốc của Architecture.md §6.15 S15-6 giả định `parse_method="txt"` (born-digital) khiến
`quality.confidence is None` — **sai với dữ liệu thật**. `middle.json` trong fixture này chứng
minh MinerU 3.4.5 gán `score: 1.0` cho hầu hết span lấy từ text layer ở chế độ `txt`, nên
`_compute_quality()` (`src/services/mineru_runner.py`) trả về `confidence=0.997628187250996`,
KHÔNG phải `None`. `jobs.ocr_confidence` cho `pdf_digital` phải được **ép `None` tường minh**
trong `JobOrchestrator.run_parse_only()` bất kể giá trị này — cột này chỉ có một ý nghĩa duy
nhất trong toàn app ("độ tin cậy OCR thật"), và giá trị ở đây không đến từ OCR.

`tests/integration/test_job_orchestrator.py` dùng `middle.json` này (qua
`MinerURunner._compute_quality()` thật, không phải số hardcode) để dựng `OcrQuality` cho fake
`MinerURunner.parse_document()`, rồi assert `run_parse_only()` ghi `jobs.ocr_confidence IS
NULL` cho `file_type=pdf_digital` dù runner trả `0.9976` — đúng loại assertion Protocol 5 tồn
tại để chặn ("mock tự nhất quán với chính giả định sai", không phải "mock khớp thực tế").

## `summary.json`

Bản tóm tắt số đo runner script ghi ra ngay sau khi chạy (đường dẫn tuyệt đối trỏ vào
scratchpad phiên chạy — không còn hợp lệ, chỉ giữ lại các số liệu, xem
`docs/expert-review-us15-markdown.md` Phụ lục A cho bản đầy đủ đã diễn giải).

## Không copy vào đây

`images/` (23 file JPEG, ~340KB) — không cần cho test S15-6 (chỉ cần `document.md` +
`middle.json` cho guard nội dung rỗng + tính `ocr_confidence`), giữ fixture nhẹ. Nếu 1 test sau
này cần assert việc copy ảnh, trích lại từ `MinerURunner.parse_document()` thật hoặc dựng ảnh
giả tối thiểu (PNG 1x1) — không cần ảnh thật cho mục đích đó.
