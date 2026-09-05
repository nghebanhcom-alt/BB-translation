# CLAUDE.md — BB-Translation (Project-specific conventions)

Kế thừa toàn bộ quy ước tại `/Users/hieutt/Vibe Code/CLAUDE.md` (global). File này chỉ bổ
sung quy tắc riêng cho project BB-Translation.

## Protocol 5 — External Dependency Verification

### Bối cảnh (tại sao protocol này tồn tại)

Trong quá trình build v1.0, Architecture.md đã 2 lần định nghĩa sai contract API/CLI của
tool bên thứ ba (pdf2zh, MinerU) dựa trên kiến thức chung thay vì nguồn xác thực trực tiếp:

1. **pdf2zh**: Architecture.md ban đầu ghi pdf2zh hỗ trợ Claude native qua `-s claude` —
   sai, pdf2zh không có Claude translator, phải dùng `-s openailiked` qua Anthropic
   OpenAI-compat layer. Phát hiện bởi Dev khi implement Increment 4, dẫn tới Tech Lead phải
   research lại trực tiếp source code và viết lại toàn bộ Architecture.md section 6.6.
2. **MinerU**: `MinerURunner` (Increment 2, đã qua Reviewer + QA mà không ai phát hiện) giả
   định endpoint `/ocr` port 8010, trả JSON có field `confidence_score` bắt buộc — thực tế
   MinerU dùng endpoint `/file_parse` port 8000, KHÔNG có field confidence score nào. Mọi
   lần gọi OCR thật sẽ luôn raise lỗi ngay lập tức. Không bị phát hiện qua cả Dev, Reviewer,
   VÀ QA vì tất cả test đều dùng mock xây dựng theo đúng giả định sai đó — mock tự nhất quán
   với chính nó, không nhất quán với thực tế. Chỉ lộ ra khi PM tự cài MinerU thật.

**Root cause chung**: không có bước nào trong quy trình bắt buộc verify giả định về external
tool với nguồn xác thực (source code thật, doc chính thức) TRƯỚC KHI nó lan xuống
Dev → Reviewer → QA. Test pass chỉ chứng minh code khớp với chính giả định, không chứng minh
giả định đúng.

### Quy tắc bắt buộc

**R5-01 (Trích dẫn nguồn khi thiết kế contract)**: Bất kỳ section nào trong Architecture.md
mô tả CLI flag, HTTP endpoint, request/response schema, hay SDK method signature của 1 tool
bên thứ ba PHẢI đi kèm 1 trong hai:
- Trích dẫn nguồn xác thực trực tiếp (link tới source code file/line cụ thể, hoặc doc chính
  thức đã fetch thật qua WebFetch/WebSearch), HOẶC
- Đánh dấu rõ ràng `⚠️ ASSUMED — chưa verify với nguồn thật` nếu Tech Lead chưa có điều kiện
  research sâu tại thời điểm viết.

R5-01 là trường hợp áp dụng cụ thể của kỷ luật gắn nhãn verify (xem "Protocol 1 — mở rộng",
`/Users/hieutt/Vibe Code/CLAUDE.md` global) cho riêng tài liệu Architecture.md. Kỷ luật đó
rộng hơn: áp dụng cho MỌI hình thức giao việc, kể cả brief spawn agent không chính thức —
không chỉ nội dung đã viết vào Architecture.md. Sự cố gốc (2026-09-05): PM brief cho Tech
Lead "pdf2zh log rate-limit ra stderr" như sự thật, không gắn `[CHƯA VERIFY]` — sai (thực tế
ra stdout, xem Architecture.md 6.12.2) — vì claim đó nằm trong brief, chưa từng qua bước
review nào của R5-01 (R5-01 chỉ review nội dung ĐÃ viết vào Architecture.md).

Không được viết 1 contract cụ thể (tên field, endpoint path, flag name) mà không thuộc 1 trong
2 loại trên — mập mờ giữa "đã verify" và "suy đoán" chính là nguyên nhân gốc của cả 2 lần lỗi.

**R5-02 (Spike verification trước khi implement đầy đủ)**: Khi Dev bắt đầu increment đầu tiên
tích hợp với 1 external tool CHƯA từng được verify (đánh dấu ASSUMED theo R5-01), Dev phải làm
1 bước spike NHỎ trước: tự tra cứu/verify contract thật (đọc source code tool đó nếu có sẵn
trên GitHub, hoặc research qua WebSearch/WebFetch) TRƯỚC KHI viết implementation đầy đủ + test.
Nếu phát hiện sai lệch với Architecture.md, escalate ngay cho Tech Lead — không tự âm thầm sửa
theo phỏng đoán của Dev, và không tiếp tục implement trên giả định đã biết là sai.

**R5-03 (Gate release — real dependency smoke test)**: QA không được đánh dấu
`ready_for_release` cho bất kỳ tính năng nào phụ thuộc external tool/service nếu chưa có ÍT
NHẤT 1 lần gọi thật (không mock) tới tool/service đó, dù chỉ là smoke test đơn giản (verify
đúng endpoint tồn tại, đúng shape response cơ bản). Nếu tool chưa cài được tại thời điểm QA
(ví dụ do thiếu Docker/hardware), QA PHẢI ghi rõ trong test-report.md:
`"release blocked pending live verification: <tool name>"` — không được coi mock-only test là
đủ điều kiện release cho phần phụ thuộc external tool đó.

**R5-04 (Checklist tường minh trong review-report.md / test-report.md)**: Mỗi lần Reviewer
hoặc QA review 1 service wrapper gọi external tool (dạng `src/services/*_runner.py`,
`*_provider.py`), phải trả lời tường minh 1 dòng: "External contract verified against real
source: YES (nguồn: ...) / NO — chỉ verify theo Architecture.md / N/A". Nếu câu trả lời là NO,
đây tự động là 1 non-blocking suggestion ghi vào report, không được im lặng bỏ qua.

### Phạm vi áp dụng

Áp dụng cho mọi tool bên thứ ba app gọi qua subprocess/HTTP mà bản thân app không kiểm soát
source: `pdf2zh`, `MinerU`, `bilingual_book_maker`, Calibre `ebook-convert`, và mọi SDK
LLM provider (`anthropic`, `openai`, `google-generativeai`, `deepl` — kể cả các SDK chính
thức, vì version SDK có thể lệch với giả định lúc viết Architecture.md, như trường hợp
`google.generativeai` đã bị Reviewer flag deprecated ở Increment 5).

Không áp dụng cho thư viện nội bộ Python thuần code logic (`fastapi`, `sqlmodel`, `pymupdf`
dùng đúng API core, không phải external network/subprocess service) — rủi ro sai lệch contract
thấp hơn nhiều vì đây là thư viện Python được import trực tiếp, lỗi type sẽ lộ ngay khi chạy
test.

## Protocol 6 — Cross-Step Data Lineage Verification

### Bối cảnh (tại sao protocol này tồn tại)

Bug #5 (QA Vòng 3, sau khi MinerU rewrite theo Protocol 5 đã APPROVE): OCR (MinerU) chạy đúng,
tính đúng confidence, lưu đúng vào DB. Bước dịch (`pdf2zh_runner.translate_pages()`) cũng được
gọi đúng cách, đúng tham số theo Architecture.md. **Nhưng không ai nối kết quả OCR (Markdown
đã parse) vào input của bước dịch** — `JobOrchestrator` vẫn truyền thẳng `job.file_path` (file
scan gốc, không có text layer) cho pdf2zh, thay vì dùng nội dung/file đã qua OCR. Job báo
"completed" nhưng bản dịch hoàn toàn trống — silent failure.

**Khác Protocol 5**: đây KHÔNG phải lỗi hiểu sai contract của tool bên ngoài (MinerU/pdf2zh đều
được gọi đúng, riêng lẻ mỗi cái đều hoạt động thật, đã verify sống). Đây là lỗi **không có ai
nối 2 bước pipeline nội bộ lại với nhau** — 1 loại lỗi khác hẳn, cần cơ chế phòng khác.

**Vì sao lọt qua mọi vòng review/test trước**: mọi test (kể cả integration test) đều mock
riêng từng lời gọi bên ngoài (`mineru_runner.parse_document` và `pdf2zh_runner.translate_pages`)
và chỉ assert "được gọi chưa", KHÔNG assert "gọi với đúng dữ liệu bắt nguồn từ bước trước hay
không". Hai mock tự nhất quán với chính chúng, không ai kiểm tra sợi dây nối giữa chúng. Bug
này cũng bị "khoá kín" (latent) suốt từ Increment 4 đến giờ vì trước khi Protocol 5 fix xong,
MinerU luôn fail ngay từ bước gọi đầu tiên (Bug #2) — code nhánh xử lý kết quả OCR chưa từng
thực thi tới nơi, nên không ai có cơ hội phát hiện nó sai từ lúc viết.

### Quy tắc bắt buộc

**R6-01 (Khai báo data lineage tường minh trong Architecture.md)**: Khi Architecture.md mô tả
1 pipeline có nhiều bước tuần tự phụ thuộc nhau (bước N tạo ra artifact, bước N+1 tiêu thụ
artifact đó), phải ghi RÕ RÀNG: artifact cụ thể là gì (tên field/file path/biến), và bước N+1
đọc field/file nào — không được mô tả mập mờ kiểu "sau đó dịch file" mà không nói rõ dịch FILE
NÀO (file gốc hay file đã qua bước trước biến đổi).

**R6-02 (Test phải assert data lineage, không chỉ assert "đã gọi")**: Test (kể cả dùng mock)
cho 1 pipeline nhiều bước phải assert được **giá trị cụ thể truyền giữa các bước**, không chỉ
`assert_called()`/`assert_awaited()`. Ví dụ đúng (theo thiết kế thật đã chốt ở Architecture.md
6.10 — cầu nối "searchable PDF", KHÔNG phải dùng thẳng `markdown_path`, vì pdf2zh không nhận
input dạng Markdown):
`pdf2zh_runner.translate_pages.assert_called_with(input_path=translation_source_path, ...)`
với `translation_source_path` là file cầu nối được tạo TỪ `ocr_result` (không phải
`job.file_path` gốc) khi `job.file_type == PDF_SCAN` — không chỉ
`pdf2zh_runner.translate_pages.assert_awaited()`. Nếu 2 mock trong cùng 1 test không có bất kỳ
assertion nào liên kết input của mock B với output của mock A, đây là dấu hiệu cảnh báo cần
Reviewer flag.

**R6-03 (Bắt buộc ít nhất 1 live E2E test cho MỌI pipeline nhiều bước trước release)**: Ngoài
Protocol 5 R5-03 (live test cho từng external tool riêng lẻ), với bất kỳ pipeline nào có ≥ 2
bước phụ thuộc external tool nối tiếp nhau (OCR → dịch, parse → render...), QA phải có ít nhất
1 lần chạy XUYÊN SUỐT toàn bộ chuỗi với dữ liệu thật, kiểm tra **nội dung output cuối cùng**
(không chỉ status "completed") — ví dụ: mở file PDF dịch ra, xác nhận có chữ thật trong đó,
không chỉ tin field `status`. Đây chính xác là cách QA Vòng 3 phát hiện ra Bug #5 — mở file
output và thấy `text_len = 0`, chứ không chỉ tin "job status = completed".

**R6-04 (Reviewer checklist cho pipeline orchestrator)**: Khi review code kiểu
`*_orchestrator.py` gọi tuần tự nhiều service/runner, Reviewer phải tự trace bằng tay: với mỗi
lời gọi bước N+1, biến/field truyền vào có thực sự bắt nguồn từ return value của bước N hay
không (đọc code, theo dõi tên biến từ chỗ gán tới chỗ dùng) — không chỉ xác nhận "cả 2 bước
đều được gọi đúng tham số theo spec của riêng nó".

### Phạm vi áp dụng

Áp dụng cho mọi chuỗi xử lý nhiều bước trong `src/core/job_orchestrator.py` và các pipeline
tương tự sau này (`src/pipelines/*.py`) — bất cứ đâu output của 1 lời gọi (external tool hay
internal function) trở thành input của lời gọi tiếp theo.
test thay vì chỉ lộ khi có input thật.

## Protocol 7 — Mandatory Reviewer Gate

### Bối cảnh (tại sao protocol này tồn tại)

Sự cố (2026-09-06): qua nhiều session liên tiếp, PM (Sonnet) tự viết code (2 tính năng UI:
xoá file đã upload, thêm timestamp vào tên file tải về) rồi tự review bằng cách đọc lại diff +
chạy test, KHÔNG spawn agent `Reviewer` riêng — bỏ qua hoàn toàn handoff "Reviewer →
`docs/review-report.md`" mà Protocol 1 (global CLAUDE.md) đã mô tả. User phát hiện bằng cách tự
hỏi "sao không thấy Reviewer?" — không có cơ chế nào trong hệ thống tự phát hiện ra lỗ hổng này.

**Root cause**: Protocol 1 mô tả handoff như 1 quy trình ("Reviewer → review-report.md"), không
viết dưới dạng **cấm đoán tường minh**. Một mô tả quy trình dễ bị agent tự diễn giải là "tuỳ chọn
khi việc phức tạp" thay vì bắt buộc mọi lần — đặc biệt dưới áp lực ẩn "làm nhanh, đừng hỏi lặt
vặt" của auto mode. Đây là lỗi hệ thống (CLAUDE.md viết chưa đủ chặt), không phải lỗi 1 lần của
riêng model nào.

### Quy tắc bắt buộc

**R7-01 (Cấm tự báo cáo code hoàn tất khi thiếu Reviewer thật)**: PM/Dev **KHÔNG ĐƯỢC PHÉP** báo
cáo bất kỳ thay đổi code nào (backend, frontend, script, config ảnh hưởng hành vi) là "xong"/"đã
review"/"sẵn sàng" nếu chưa có ít nhất 1 lần spawn agent `Reviewer` (Agent tool, `subagent_type:
"Reviewer"`) TRONG CHÍNH session đó, và kết quả được ghi vào `docs/review-report.md`. Tự đọc lại
diff, tự chạy test, tự chạy `ruff` — dù kỹ đến đâu — KHÔNG được tính là thay thế Reviewer. Ngoại
lệ DUY NHẤT: thay đổi chỉ gồm comment/docs không ảnh hưởng hành vi (Reviewer có thể tự xác nhận
`N/A` cho trường hợp này thay vì skip hoàn toàn).

**R7-02 (Gate kỹ thuật, không chỉ dựa trí nhớ)**: Repo này có 1 git pre-commit hook
(`.git/hooks/pre-commit`, cài 2026-09-06) tự động chặn `git commit` nếu commit đó đổi file trong
`src/`/`web/` mà `docs/review-report.md` không nằm trong cùng commit. Đây là backstop kỹ thuật
cho R7-01 — không phụ thuộc agent có "nhớ" quy tắc hay không. Giới hạn đã biết: hook chỉ kiểm tra
file `review-report.md` có được touch hay không, KHÔNG kiểm tra được nội dung review có nghiêm
túc hay không — R7-01 vẫn là quy tắc chính, R7-02 chỉ là lưới an toàn cho trường hợp quên hoàn
toàn.

### Phạm vi áp dụng

Áp dụng cho MỌI thay đổi code trong repo này, bất kể do PM tự viết trực tiếp hay do Dev/Tech Lead
(agent con) viết — không có ngoại lệ "việc nhỏ nên bỏ qua". Không áp dụng cho thay đổi thuần
`docs/*.md` (trừ chính `review-report.md`/`test-report.md`), `.env`, hoặc file cấu hình không
ảnh hưởng hành vi runtime.

**R7-03 (Append, không overwrite, vào các file handoff dùng chung)**: Sự cố (2026-09-06): 1 agent
Reviewer được giao ghi kết quả vào `docs/review-report.md` đã GHI ĐÈ toàn bộ file (2054 dòng lịch
sử review từ Increment 1 tới thời điểm đó bị mất, chỉ còn lại report của riêng nó) thay vì đọc
file hiện có và append thêm section mới — vì agent mới không có ký ức về việc file này đã có lịch
sử, chỉ được giao "ghi kết quả vào file X". Bất kỳ ai giao việc ghi vào `docs/review-report.md`,
`docs/test-report.md`, `docs/CHANGELOG.md`, hoặc `project_state.json` cho 1 agent (Reviewer, QA,
Dev, Tech Lead) PHẢI nói rõ trong brief: "đọc file hiện có trước, APPEND section mới vào cuối,
KHÔNG được xoá/ghi đè nội dung cũ" — không được mặc định agent tự hiểu ý này.
