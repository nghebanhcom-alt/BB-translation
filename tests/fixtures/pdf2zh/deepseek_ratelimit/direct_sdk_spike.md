# DeepSeek rate-limit spike — direct SDK call — INCONCLUSIVE

Ngày chạy: 2026-09-05

## Bối cảnh / vì sao đổi cách tiếp cận

3 lần thử trước (xem `README.md` cùng thư mục) chạy qua `pdf2zh` thật trên 8-10 trang PDF
(~97-110 đoạn văn) ở `--thread` 64/128/256 — không bao giờ chạm rate limit thật vì số segment
(= trần concurrency thực tế) quá thấp so với ngưỡng tài khoản DeepSeek (theo Architecture.md
6.12.1 S12, quy mô hàng trăm-nghìn). Kết luận INCONCLUSIVE.

Lần này bỏ qua giới hạn "số đoạn văn trong 1 PDF nhỏ" bằng cách gọi thẳng SDK `openai` Python
(đúng SDK pdf2zh dùng nội bộ — `OpenAITranslator` dùng `openai.OpenAI(base_url=...)`, xem
pdf2zh `translator.py`), trỏ `base_url=https://api.deepseek.com`, `model=deepseek-chat` (đúng
model app đang cấu hình mặc định, `src/core/config.py:30`). Mỗi request cực nhỏ: prompt "Say hi
in one word.", `max_tokens=5`, không liên quan gì tới nội dung dịch thật — mục đích duy nhất là
tạo đủ số connection đồng thời thật để có cơ hội chạm ngưỡng rate-limit tài khoản.

## Cách chạy

Script throwaway (không phải code sản phẩm, không nằm trong repo):
`/private/tmp/claude-501/.../scratchpad/spike_deepseek_ratelimit.py` (đã xoá sau khi xong,
xem mục "Dọn dẹp" cuối file).

- `openai.AsyncOpenAI(api_key=..., base_url="https://api.deepseek.com", max_retries=0,
  timeout=30.0)` — `max_retries=0` để không che giấu lỗi thật bằng retry nội bộ của SDK.
- Bắn đồng thời thật bằng `asyncio.gather()` trên N task, N tăng dần theo các bước:
  300 → 600 → 1000 → 1500 → 2000 → 2600.
- Sau mỗi bước, ước tính chi phí luỹ kế bằng đúng bảng giá trong
  `src/services/deepseek_provider.py` (`deepseek-chat` → repoint `deepseek-v4-flash`,
  $0.22/$0.66 mỗi Mtok input/output), giả định ~20 input token + ~5 output token/request
  (prompt siêu ngắn + `max_tokens=5`) — set trần cứng dừng nếu luỹ kế chạm $1 hoặc tổng request
  chạm 8000.
- Bắt exception theo đúng phân cấp SDK `openai`: `RateLimitError` (429) trước, rồi
  `APIStatusError` (lỗi HTTP status khác), rồi `APIError` (bao gồm cả lỗi client-side như
  timeout/connection), rồi exception khác — in `type(exc).__name__` và `repr(exc)` đầy đủ cho
  mỗi loại lỗi gặp phải.

## Kết quả thật (log đầy đủ từ lần chạy)

```
[debug] load_dotenv('/Users/hieutt/Vibe Code/Baking-tools/BB-Translation/.env') -> True

=== STEP concurrency=300 (est step cost $0.0023, cumulative before $0.0000) ===
elapsed=2.9s counts={'ok': 300}
cumulative_requests=300 cumulative_cost=$0.0023

=== STEP concurrency=600 (est step cost $0.0046, cumulative before $0.0023) ===
elapsed=8.9s counts={'ok': 600}
cumulative_requests=900 cumulative_cost=$0.0069

=== STEP concurrency=1000 (est step cost $0.0077, cumulative before $0.0069) ===
elapsed=15.2s counts={'ok': 1000}
cumulative_requests=1900 cumulative_cost=$0.0146

=== STEP concurrency=1500 (est step cost $0.0116, cumulative before $0.0146) ===
elapsed=18.9s counts={'ok': 1500}
cumulative_requests=3400 cumulative_cost=$0.0262

=== STEP concurrency=2000 (est step cost $0.0154, cumulative before $0.0262) ===
elapsed=46.8s counts={'ok': 1308, 'api_error': 692}
  sample[api_error] = APITimeoutError: APITimeoutError('Request timed out.')
cumulative_requests=5400 cumulative_cost=$0.0416

=== STEP concurrency=2600 (est step cost $0.0200, cumulative before $0.0416) ===
elapsed=33.7s counts={'ok': 2588, 'api_error': 12}
  sample[api_error] = APITimeoutError: APITimeoutError('Request timed out.')
cumulative_requests=8000 cumulative_cost=$0.0616

=== SUMMARY ===
concurrency=300  counts={'ok': 300}                       elapsed=2.9s
concurrency=600  counts={'ok': 600}                        elapsed=8.9s
concurrency=1000 counts={'ok': 1000}                       elapsed=15.2s
concurrency=1500 counts={'ok': 1500}                       elapsed=18.9s
concurrency=2000 counts={'ok': 1308, 'api_error': 692}     elapsed=46.8s
concurrency=2600 counts={'ok': 2588, 'api_error': 12}      elapsed=33.7s
TOTAL requests=8000 TOTAL est cost=$0.0616
```

Vòng lặp escalate dừng đúng lúc `cumulative_requests` chạm trần 8000 (giới hạn cứng của task),
KHÔNG tiếp tục lên mức cao hơn.

## Phân loại lỗi gặp phải

Không hề gặp `openai.RateLimitError` (HTTP 429) ở bất kỳ mức concurrency nào (300 → 2600).

Lỗi duy nhất gặp phải là `openai.APITimeoutError` (subclass của `APIConnectionError` →
`APIError`, KHÔNG phải `APIStatusError`), xuất hiện ở mức 2000 (692/2000 request, 34.6%) và
2600 (12/2600 request, 0.5%). Đây là lỗi **client-side timeout** (client chờ response quá 30s
mà không nhận được) — không phải HTTP status code trả về từ server, nên không chứng minh được
account có bị 429 hay không; nhiều khả năng là do bão hoà local connection pool/network hoặc
DeepSeek server xử lý chậm dưới tải cao, không phải tín hiệu rate-limit chính thức.

`repr()` đầy đủ mẫu lỗi bắt được: `APITimeoutError('Request timed out.')` — không có thêm
thông tin status code vì đây là lỗi phía client trước khi nhận được response.

## Kết luận: INCONCLUSIVE (không phải PASS/FAIL)

- **Không tìm ra ngưỡng concurrency thật gây 429** cho `deepseek-chat` trong phạm vi đã thử
  (300-2600 concurrent, dừng ở đúng 8000 request tích luỹ theo trần task).
- **Không xác nhận được** hành vi `openai.RateLimitError` cho DeepSeek — vì chưa từng gặp 429
  thật để quan sát exception type.
- Lỗi duy nhất gặp phải (`APITimeoutError`) là khác loại, không đủ để kết luận gì về cơ chế
  retry `retry_if_exception_type(openai.RateLimitError)` trong `pdf2zh/translator.py:436-444`
  có hoạt động đúng với DeepSeek hay không.
- Tăng concurrency thêm nữa (>2600) có khả năng gặp *nhiều* `APITimeoutError` hơn (xu hướng đã
  thấy: 34.6% ở mức 2000, tuy giảm lại ở 2600 — không đơn điệu, có thể do biến động mạng/server
  tại thời điểm chạy, không phải do đã "qua" ngưỡng timeout) trước khi chạm 429 thật, hoặc có
  thể 429 thật nằm ở mức cao hơn nữa — không có đủ dữ liệu để suy đoán.

## Chi phí thực tế đã tiêu

Tổng 8000 request, ước tính theo bảng giá `deepseek-chat` (repoint `deepseek-v4-flash`,
$0.22/$0.66 mỗi Mtok) với ~20 input token + ~5 output token/request (prompt "Say hi in one
word." + `max_tokens=5`):

**Tổng chi phí ước tính đã tiêu: ~$0.062 USD** — còn rất xa trần cứng $1 đã duyệt cho task này.
Không có số token thật trả về từ response (script không parse `usage` field trong response
thành công để tối giản, chỉ ước tính) — cùng cách ước tính over-estimate như README.md gốc.

## Hành động tiếp theo / không hành động

- **KHÔNG sửa `docs/Architecture.md`** (S13 mục 6.12.1, dòng tương ứng 6.12.10) — vẫn giữ
  `[UNVERIFIED]` vì đây là INCONCLUSIVE, không phải PASS.
- Floor `deepseek = 8` ở Architecture.md 6.12.5/6.12.10 KHÔNG thay đổi — quyết định đó vốn đã
  độc lập với con số ngưỡng thật (an toàn dù ngưỡng là bao nhiêu).
- Nếu cần verify tiếp: cần escalate xin duyệt trần chi phí/số request cao hơn (>8000) để có cơ
  hội leo thang concurrency vượt qua vùng nhiễu timeout hiện tại, HOẶC escalate xin verify qua
  kênh khác (vd. liên hệ support DeepSeek hỏi thẳng ngưỡng `deepseek-chat`, đọc lại doc chính
  thức xem có cập nhật thêm entry cho legacy alias `deepseek-chat` hay chưa) — không tự ý mở
  rộng phạm vi trong task này.
- Test tích hợp KHÔNG được dùng log này làm golden file cho mock "DeepSeek trả 429 →
  `RateLimitError`" — vì chưa có bằng chứng thật nào về hành vi đó. Mock 429 cho DeepSeek (nếu
  cần trước khi có golden file PASS thật) phải đánh dấu rõ `⚠️ ASSUMED` theo Protocol 5 mục 1.

## Dọn dẹp

Script throwaway
`/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/00684168-9e9a-4d91-850e-af48c793ba42/scratchpad/spike_deepseek_ratelimit.py`
đã bị xoá sau khi hoàn thành spike (nằm ngoài repo, chỉ để chạy 1 lần, không cần giữ lại).
