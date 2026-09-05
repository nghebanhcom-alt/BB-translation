# DeepSeek rate-limit golden file — INCONCLUSIVE

Ngày chạy: 2026-09-05
Model: `deepseek-chat` (config mặc định của app, `src/core/config.py:30`; DeepSeek server-side
repoint alias này sang `deepseek-v4-flash`, xem `src/services/deepseek_provider.py`).
Service arg dùng đúng format nội bộ app build ra (`src/services/pdf2zh_service_map.py`
`_build_deepseek`): `pdf2zh -s deepseek:deepseek-chat`, env `DEEPSEEK_API_KEY`,
`DEEPSEEK_MODEL=deepseek-chat`, `COLUMNS=200` (D2, Architecture.md 6.12.2).

## Kết quả: KHÔNG bắt được rate limit thật (INCONCLUSIVE, không phải PASS/FAIL)

Đây là INCONCLUSIVE đúng theo nhánh xử lý ở Architecture.md 6.12.6 mục 6 (áp dụng tương tự
cho spike DeepSeek ở 6.12.10 bước 2): chạy nhiều lần ở `--thread` cao mà không bao giờ chạm
rate limit thật thì kết quả là INCONCLUSIVE, không được coi là "đã verify tín hiệu rate-limit
hoạt động cho DeepSeek". Không dùng các file `inconclusive_*` này làm golden file để build mock
retriever "khi có 429 thì log dòng X" — chưa có bằng chứng dòng đó xuất hiện thật với DeepSeek.

## Các lần thử (tổng cộng 3, đúng giới hạn tối đa cho phép)

| # | Trang | `--thread` | `--ignore-cache` | Số request POST thật tới `api.deepseek.com` | Kết quả |
|---|-------|-----------|-------------------|----------------------------------------------|---------|
| 1 | 8 (trang 21-28, cắt từ "How baking works", dày chữ) | 64  | không (cache lạnh, lần đầu) | 97  | Toàn bộ 200 OK, không có dòng `RateLimitError` |
| 2 | 8 (cùng file trang 21-28) | 128 | có | 98  | Toàn bộ 200 OK, không có dòng `RateLimitError` |
| 3 | 10 (trang 21-30) | 256 | có | 110 | Toàn bộ 200 OK, không có dòng `RateLimitError` |

File `inconclusive_stdout.txt` / `inconclusive_stderr.txt` = output đầy đủ của lần thử CUỐI
(#3, thread 256, 10 trang). File `inconclusive_attempt1_thread64_stdout.txt` và
`inconclusive_attempt2_thread128_stdout.txt` giữ lại thêm 2 lần thử trước để tham khảo (không
bắt buộc theo task nhưng hữu ích cho lần verify sau, tránh lặp lại đúng cấu hình đã biết là
không đủ để chạm rate limit).

## Vì sao khả năng cao không bao giờ chạm được rate limit trong giới hạn 5-10 trang

Số segment (đoạn văn/request) pdf2zh tách ra cho 8-10 trang chỉ khoảng 97-110 — đây cũng chính
là trần đồng thời tối đa có thể đạt được, bất kể set `--thread` cao tới đâu (thread 128 và 256
đều không tạo thêm request đồng thời nào so với thread 64, vì không đủ segment để lấp đầy pool).
Theo Architecture.md 6.12.10, giới hạn concurrency DeepSeek được ghi nhận ở mức 500/2500 (dòng
"Gioi han concurrency DeepSeek 500/2500" — verified S12, không phải riêng cho `deepseek-chat`
theo S13 `[UNVERIFIED]`). Nếu ngưỡng thật cho `deepseek-chat` cũng ở quy mô hàng trăm trở lên,
thì một tài liệu chỉ 5-10 trang về cấu trúc không đủ tải để vượt ngưỡng đó, dù đẩy `--thread`
cao tới đâu. Để có cơ hội thật sự chạm rate limit sẽ cần tài liệu nhiều trang hơn (tăng tổng số
segment) — nhưng việc đó vượt giới hạn "5-10 trang" và trần chi phí $1 đã được duyệt trước cho
task này, nên KHÔNG tự ý mở rộng phạm vi.

## Chi phí thực tế đã tiêu (ước tính)

Không có số token thật (pdf2zh không log usage trả về từ response — chỉ log status HTTP).
Ước tính bằng `src/core/cost_estimator.estimate_chunk_cost()` + `DeepSeekProvider.estimate_cost()`
(pricing `deepseek-chat` → repoint `deepseek-v4-flash`: $0.22/$0.66 mỗi Mtok, nguồn xác thực đã
ghi tại `src/services/deepseek_provider.py`):

| Lần | Trang | Segment | Input tokens (ước tính) | Output tokens (ước tính) | Cost (USD, ước tính) |
|-----|-------|---------|--------------------------|----------------------------|------------------------|
| 1   | 8     | 97      | ~15,075                  | ~10,481                    | ~$0.0102               |
| 2   | 8     | 98      | ~15,175                  | ~10,481                    | ~$0.0103               |
| 3   | 10    | 110     | ~17,750                  | ~13,162                    | ~$0.0126               |
| **Tổng** |   |         |                          |                             | **~$0.033**            |

Tổng chi phí thực tế ước tính đã tiêu: **~$0.03 USD**, còn rất xa trần cứng $1 đã duyệt. Dừng
lại đúng ở lần thử thứ 3 (đủ 3 lần thử tối đa cho phép theo nhiệm vụ), không thử thêm.

## Kết luận / hành động tiếp theo

- KHÔNG gỡ `[UNVERIFIED]` nào dựa trên bộ fixture này — vì đây là INCONCLUSIVE, không phải PASS.
- Nếu cần verify tín hiệu rate-limit cho DeepSeek thật, lần sau cần escalate: xin duyệt tăng
  phạm vi tài liệu thử (nhiều trang hơn) hoặc tăng trần chi phí, KHÔNG tự ý làm trong task này.
- Test tích hợp (6.12.9 R6-02, test #2/#3) **không được** dùng các file `inconclusive_*` này để
  mock giả lập tình huống "DeepSeek trả 429" — vì không có bằng chứng dòng `RateLimitError`
  thật nào xuất hiện với DeepSeek. Nếu cần mock 429 cho DeepSeek trước khi có golden file PASS
  thật, phải đánh dấu rõ trong test đó là dựa trên giả định (theo tinh thần Protocol 5 mục 1 —
  `⚠️ ASSUMED`), không được ngụy trang là "sinh từ golden file thật".
