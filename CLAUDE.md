# CLAUDE.md — BB-Translation (Project-specific conventions)

Kế thừa toàn bộ quy ước tại `/Users/hieutt/Vibe Code/CLAUDE.md` (global). File này bổ sung
quy tắc riêng cho BB-Translation: **Protocol 5, 6, 7, 8** (rút ra từ sự cố thật của chính project
này) và **bộ Protocol A–F + mở rộng Protocol 2/3/4** (port từ AB-RnD, 2026-09-10 — xem mục cuối file).

## Bản đồ tài liệu — đọc file nào cho việc gì

| Cần biết | Đọc | Không đọc |
|---|---|---|
| Hệ thống **phải** như thế nào (hợp đồng hiện hành) | `docs/Architecture.md` §1–10, **đúng § được chỉ** | cả file (7.2k dòng) |
| **Vì sao** tới được thiết kế đó (RCA, phản biện, Final Decision) | `docs/design-log.md` | — |
| Yêu cầu nghiệp vụ, User Story, Acceptance Criteria | `docs/PRD.md` | — |
| Trạng thái hiện tại: bước nào đang chạy, ai chặn ai | `project_state.json` (5KB, đọc hết được) | — |
| Lịch sử quyết định trước 2026-09-10 | `docs/decisions-archive.md` | — |
| Đợt review/test gần nhất | `docs/review-report.md`, `docs/test-report.md` | — |
| Đợt review/test cũ | `docs/archive/` | — |
| Vì sao pipeline dừng ở một hạng mục | `docs/escalation-log.md` | — |

**Luật (Protocol C.4)**: brief giao việc phải trỏ tới **§ hoặc dải dòng cụ thể**, không được viết
"đọc Architecture.md". Với tài liệu cỡ này, "đọc cả file" là chỉ thị bất khả thi mà agent sẽ âm thầm
thực hiện dở dang — mỗi vai một mảnh khác nhau. Đó là cơ chế đã sinh ra Bug #5 và Bug #9.

## Đội hình

**Thường trực** (hub-and-spoke, PM là orchestrator): PM (sonnet) · BA (opus) · Tech Lead (opus) ·
Dev (sonnet) · Reviewer (sonnet) · QA (sonnet) — file agent tại `.claude/agents/`.

**Checkpoint expert one-off** (Protocol D, không thường trực, tối đa 2 lần/hạng mục):
Domain Expert PDF/typography (opus) · Critic phản biện độc lập (fable).

**Trước mỗi lần dispatch**, PM chạy: `python3 scripts/validate_state.py`

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

**R5-06 (Chỉ thị "đo lại ở lần chạy live đầu" bắt buộc có owner trong backlog[])**: Bug #EPUB-5
(2026-09-11): §6.20.13.3b đã tự ghi "nếu max ratio lành mạnh > 1,5 → ngưỡng quá sát, phải nâng"
— log của chính lần chạy live đầu tiên đã có sẵn dữ liệu bác bỏ ngưỡng đó, nhưng không ai đọc
lại vì chỉ thị chỉ nằm trong văn xuôi Architecture.md, không gắn với ai phải làm. Root cause là
quy trình, không phải model nào quên: 1 chỉ thị "phải đo lại" không có chủ sở hữu sẽ không bao
giờ được thực thi. Từ nay, mọi chỉ thị dạng `⚠️ ASSUMED — phải đo lại ở lần chạy live đầu tiên`
(hoặc tương đương) viết trong Architecture.md **bắt buộc** đi kèm 1 mục tương ứng trong
`backlog[]` (project_state.json) với `source` là agent/role chịu trách nhiệm đo lại — không được
để chỉ thị đo-lại chỉ tồn tại dưới dạng văn bản không ai theo dõi. PM kiểm tra điều này khi dispatch
Tech Lead ghi `⚠️ ASSUMED` mới vào Architecture.md.

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
`src/`/`web/` mà `docs/review-report.md` không nằm trong cùng commit. **Bổ sung 2026-09-10**: hook
còn chạy `python3 scripts/validate_state.py` và chặn commit nếu `project_state.json` không hợp lệ
(Protocol 4 mở rộng) — bắt được cả trường hợp `loops[]` vượt ngưỡng chưa escalate và
`infra_pending[]` quá 24h chưa có commit (Protocol E). Đây là backstop kỹ thuật
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

## Protocol 8 — Shared Pipeline Assumption Audit

### Bối cảnh (tại sao protocol này tồn tại)

Bug #9 (2026-09-08, phát hiện bởi Domain Expert khi điều tra tiếp Bug #8): §6.14.7 chủ động thiết
kế `_process_chunk()` (`job_orchestrator.py`) dùng CHUNG 1 đường ống cho cả 2 engine dịch
(`pdf2zh`, `babeldoc`), không rẽ nhánh `if engine == ...` trong thân hàm — đúng nguyên tắc để
tránh lặp lại Bug #5 (2 nhánh code lệch nhau khi sửa độc lập). Nguyên tắc này **đúng cho cách gọi**
(`translator_runner.translate_pages(...)`) nhưng bị áp dụng nhầm sang **từng bước hậu kỳ bên
trong** đường ống đó: `font_shrink_page()` được viết ra vì 1 lý do RIÊNG của pdf2zh (pdf2zh vẽ y
nguyên vị trí/cỡ chữ gốc tiếng Anh lên trang, không tự co giãn theo bản dịch tiếng Việt dài hơn —
cần bước co font hậu kỳ để không tràn khung). Khi `babeldoc` được thêm làm engine thứ 2 và đi qua
đúng `_process_chunk()` có sẵn đó, không ai quay lại hỏi "lý do bước `font_shrink_page` tồn tại có
còn đúng với babeldoc không?" — thực tế babeldoc tự bóp cỡ chữ bên trong chính nó (tới tối thiểu
10%, thậm chí bỏ hẳn đoạn nếu vẫn không vừa, KHÔNG BAO GIỜ vẽ tràn ra ngoài box — verify bằng đọc
trực tiếp source `IL/midend/typesetting.py` babeldoc 0.6.4). `font_shrink_page` áp lên output
babeldoc chỉ bắt được SAI SỐ ĐO FLOAT vặt vãnh (median excess đo được = 0.00%) rồi tự ý
redact+insert_text lại — gây Bug #8 (lệch toạ độ MediaBox/CropBox, đã fix) và, nặng hơn, phát hiện
cùng lúc **mất chữ thật** (verify cụ thể trang 26 sách Le Cordon Bleu: 4 dòng nội dung biến mất do
redraw dòng kế tiếp vô tình xoá đè dòng vừa vẽ trước đó).

**Vì sao lọt qua từ lúc thêm babeldoc tới giờ**: bước `rotated_text_overlay` (thêm CÙNG LÚC với
babeldoc) được gate đúng ngay từ đầu (`if pdf_translate_engine == "babeldoc" and ...`,
`job_orchestrator.py:564-566`, kèm comment giải thích lý do). Khác biệt duy nhất giữa 2 bước:
`rotated_text_overlay` là bước MỚI viết cùng lúc với engine mới nên tự nhiên được cân nhắc theo
engine; `font_shrink_page` là bước CÓ SẴN TỪ TRƯỚC babeldoc, "đã chạy ổn từ trước" nên không ai
audit lại khi babeldoc đi ké vào cùng đường ống. **Bước cũ, không phải bước mới, là chỗ dễ bị bỏ
sót nhất** khi mở rộng 1 pipeline dùng chung sang biến thể/engine mới.

### Quy tắc bắt buộc

**R8-01 (Audit toàn bộ bước hậu kỳ, không chỉ bước mới thêm)**: Khi thêm 1 engine/backend/biến thể
mới vào 1 pipeline đã dùng chung code (theo đúng nguyên tắc "không rẽ nhánh if engine=="), Tech
Lead phải liệt kê TỪNG bước xử lý hiện có trong pipeline đó — **kể cả bước có từ TRƯỚC biến thể
mới, không chỉ bước mới thêm cùng lúc** — và với mỗi bước trả lời tường minh trong Architecture.md:
"bước này tồn tại để giải quyết vấn đề gì của biến thể cũ, biến thể mới có cùng vấn đề đó không?"
Câu trả lời phải có nguồn xác thực (đọc source biến thể mới, hoặc đo thật) — không suy đoán "chắc
ổn vì đang dùng chung code nên an toàn".

**R8-02 (Deny-by-default khi chưa verify)**: Câu trả lời "chưa rõ/chưa verify" cho 1 bước → bước đó
PHẢI mặc định SKIP cho biến thể mới cho tới khi verify xong. Không được mặc định "cứ để chạy chung
cho an toàn, có sao sửa sau" — chính tư duy đó là nguyên nhân Bug #9.

**R8-03 (Hiện thực bằng capability trên object đại diện biến thể, không rẽ nhánh cứng)**: Cách hiện
thực "skip có điều kiện" vẫn phải giữ đúng tinh thần "không rẽ nhánh if engine==" của §6.14.7 —
khai báo 1 thuộc tính/property năng lực trên chính class đại diện biến thể (ví dụ
`Runner.needs_font_shrink: bool`), để pipeline hỏi object đó thay vì tự đoán theo tên biến thể rải
rác trong thân hàm.

### Phạm vi áp dụng

Áp dụng khi thêm engine dịch mới (`src/services/*_runner.py`), thêm provider OCR/LLM mới, hoặc bất
kỳ biến thể nào khác được route qua 1 hàm/pipeline dùng chung đã tồn tại từ trước trong
`src/core/job_orchestrator.py` hoặc pipeline tương tự. Không áp dụng khi biến thể mới có pipeline
xử lý hoàn toàn riêng, không đi qua code dùng chung nào.

---

# Protocols riêng project — bộ A–F (port từ AB-RnD, áp dụng 2026-09-10)

> **Nguồn gốc**: dự án `Anela-bakeworks/RnD-app` (AB-RnD) đã làm một vòng phản biện độc lập về quy
> trình (Domain Expert chạy model Fable), Hiếu duyệt 2026-09-10, kết quả nằm ở commit `510e511` của
> repo đó. Bộ Protocol A–F + phần mở rộng Protocol 2/3/4 dưới đây được **port sang BB-Translation
> có adapt**: BB là pipeline Python/FastAPI đã release v1.3.1 (không phải project mới bootstrap,
> không có Supabase), nên Protocol E đổi đối tượng từ "migration Supabase" sang "môi trường chạy
> thật + version tool bên thứ ba".
>
> **Đánh chữ cái A–F** (không đánh số) để không va chạm với Protocol 1–8 ở global CLAUDE.md và
> Protocol 5–8 riêng của project này. Bộ A–F **bổ sung**, không thay thế gì cả.
>
> **Cuối mỗi phase, PM tổng kết** vào `docs/decisions-archive.md`: Protocol nào đáng đẩy lên global
> `/Users/hieutt/Vibe Code/CLAUDE.md`, Protocol nào chỉ hợp với riêng BB-Translation.

## Mở rộng Protocol 2 (Human Checkpoints) — checkpoint hết hạn ngầm

Mỗi checkpoint đã duyệt (`checkpoints[]` trong `project_state.json`) gắn với một `approved_version`
+ `approved_commit` cụ thể, và **tự chuyển `status: stale`** khi xảy ra 1 trong 3 điều kiện:

- (a) một mục có nhãn nguồn owner quyết trực tiếp (`[Hiếu ...]`) bị đổi nội dung kể từ bản duyệt;
- (b) tài liệu tăng ≥3 phiên bản nhỏ kể từ bản duyệt;
- (c) `git diff --stat <approved_commit> HEAD -- <file>` ≥20% tổng dòng của bản duyệt.

PM kiểm 3 điều kiện này **trước mỗi lần dispatch** một bước phụ thuộc checkpoint đó. Stale → không
dispatch, trình Hiếu **bản tóm tắt khác biệt** (không phải cả tài liệu). Xác nhận lại chỉ cần một
câu "OK" nhưng phải tường minh — **im lặng không tính là đồng ý**.

*Trạng thái khi port (2026-09-10)*: `C1` (PRD.md) và `C2` (Architecture.md) đều `stale` — cả hai
header vẫn ghi `Version 1.0 | Phase: Planning` trong khi sản phẩm đã ở v1.3.1 và Architecture.md đã
tăng từ bản duyệt gốc lên 12.818 dòng. Không truy vết được mốc duyệt nào. Cần Hiếu đặt lại baseline
(duyệt bản hiện tại là 2.0) trước khi có checkpoint thật để so.

## Mở rộng Protocol 3 (Circuit Breaker) — mọi cặp agent, không chỉ Dev↔Reviewer/QA

Bất kỳ cặp agent nào trả việc qua lại trên cùng một item đều có bộ đếm riêng trong
`project_state.json` → `loops[]`:

| Loại cặp | Ví dụ | Ngưỡng |
|---|---|---|
| Thi công ↔ Review | Dev↔Reviewer, Tech Lead↔Reviewer | 3 |
| Thi công ↔ Kiểm thử | Dev↔QA | 5 |
| Viết-spec ↔ Hỏi-Hiếu (đợt CLARIFY, Protocol B) | BA↔Hiếu qua PM | 2 |
| Tổng hợp ↔ Nguồn | PM↔agent bị yêu cầu làm lại | 2 |
| Chưa phân loại | — | 3 |

Vượt ngưỡng mà chưa escalate → PM dừng **đúng cặp đó** (không chặn cặp/item khác), ghi
`docs/escalation-log.md`. Reject do vi phạm **Protocol 5** (`[UNVERIFIED]`, mock không có golden
file) và vi phạm **Protocol 7** (thiếu Reviewer thật) **KHÔNG tính** vào bộ đếm này — vi phạm quy
trình không được phép ăn mòn quota sửa lỗi kỹ thuật.

## Mở rộng Protocol 4 (Shared Context) — state phải hợp lệ theo schema

`project_state.json` phải hợp lệ theo `project_state.schema.json`, kiểm bằng:

```bash
python3 scripts/validate_state.py
```

PM chạy lệnh này **trước mỗi lần dispatch**. Fail → sửa state cho hợp lệ TRƯỚC khi làm bất cứ việc
gì khác.

Luật kèm theo:
- **Không còn trường văn xuôi tự do.** Mô tả sự kiện/lý do thuộc `docs/CHANGELOG.md`,
  `docs/design-log.md`, `docs/decisions-archive.md`, `docs/escalation-log.md`.
- `blockers[]` **chỉ chứa id** trỏ tới `open_questions[]` / `infra_pending[]` / `checkpoints[]` —
  không chứa câu văn.
- `steps[].status = done` chỉ hợp lệ khi có `output`; nếu bước chạm môi trường thật thì phải có cả
  `closed_commit`.
- Finding non-blocking của Reviewer/QA vào `backlog[]` — **không được im lặng biến mất**, cũng không
  được nhét vào `blockers[]` để rồi chặn nhầm release.

*Vá lần đầu 2026-09-10*: state cũ là văn xuôi tự do 70.513 ký tự (~17.6k token **mỗi lần mỗi agent
đọc**), gồm 19 `notes[]` + 12 `blockers[]` + 23 `iterations.by_increment[]` mà gần như toàn bộ là
lịch sử increment đã đóng. Đã archive nguyên văn 100% vào `docs/decisions-archive.md` (kèm bảng ánh
xạ từng mục) và dựng lại state có cấu trúc còn 5.409 ký tự — **giảm 13 lần**.

## Protocol A — Ranh giới vai PM

PM là orchestrator, **không phải worker dự phòng**. Chi tiết đầy đủ (được LÀM gì / KHÔNG được làm
gì, vòng làm việc chuẩn 9 bước) nằm ở `.claude/agents/pm.md` — file đó **chính là phần thực thi**
của Protocol này, đọc ở đó thay vì lặp lại ở đây. File `pm.md` là system prompt của PM **kể cả khi
PM chạy trong session chính, không được spawn qua Agent tool**.

Protocol A và **Protocol 7** (Mandatory Reviewer Gate) là hai mặt của cùng một vấn đề: Protocol 7
cấm PM *tự review*; Protocol A cấm PM *tự thi công* ngay từ đầu. Sự cố 2026-09-06 (PM tự viết 2
tính năng UI rồi tự review) vi phạm cả hai.

## Protocol B — CLARIFY trước, WRITE sau

Agent ghi quyết định của Hiếu vào tài liệu sống (PRD, Architecture, design-log) làm **2 pha tách
bạch**:

1. **CLARIFY** — liệt kê hết câu hỏi hệ quả dự đoán được, mỗi câu kèm: phát sinh từ đâu, chặn bước
   nào nếu không trả lời, **đề xuất mặc định**. Ghi vào `open_questions[]`. PM gộp lại, hỏi Hiếu
   **một lần** bằng một bảng đánh số (một lượt `AskUserQuestion` nhiều câu — không hỏi lẻ từng câu
   rồi dispatch lại).
2. **WRITE** — chỉ viết khi mọi câu ở CLARIFY đã `answered`/`deferred`, viết **một lần** toàn bộ
   phần bị ảnh hưởng.

Một item tối đa **2 đợt CLARIFY** (`open_questions[].clarify_rounds` ≤ 2 — validator chặn cứng).
Phát hiện câu hỏi mới giữa lúc WRITE → **không hỏi ngay**: ghi `default`, viết tiếp theo mặc định,
gộp vào đợt CLARIFY sau. Ngoại lệ hỏi lẻ: chỉ khi mọi mặc định khả dĩ đều buộc phải xoá/viết lại
>30% phần đang viết, và phải nêu rõ lý do.

**Vì sao**: hỏi lẻ từng câu là dạng lãng phí kín đáo nhất — mỗi lần hỏi là một lần Hiếu phải nạp lại
ngữ cảnh, và mỗi lần dispatch lại là một lần agent phải đọc lại toàn bộ tài liệu.

## Protocol C — Kỷ luật tài liệu đặc tả

`docs/PRD.md` và `docs/Architecture.md` **chỉ chứa trạng thái hiện hành** — hợp đồng đang có hiệu
lực. Nhật ký (RCA, phản biện, Final Decision, đo đạc) sống ở `docs/design-log.md`.

1. **Tách lịch sử khỏi hợp đồng.** `docs/Architecture.md` = *hệ thống PHẢI như thế nào*;
   `docs/design-log.md` = *vì sao tới được như thế* (chỉ append, theo thời gian). Một quyết định
   trong design-log làm đổi hợp đồng → **bắt buộc** cập nhật §1–10 của Architecture.md; không để
   hợp đồng chỉ tồn tại dưới dạng nhật ký.
2. **Rotate report theo đợt.** `docs/review-report.md` và `docs/test-report.md` chỉ giữ các đợt gần
   nhất; đợt cũ chuyển nguyên văn sang `docs/archive/<tên>-until-<ngày>.md` kèm mục lục, và file
   sống giữ 1 khối `<details>` liệt kê đợt đã lưu trữ. **Chuyển chỗ, không xoá** — R7-03 vẫn nguyên
   giá trị.
3. **Ngân sách kích thước.** `scripts/validate_state.py` cảnh báo khi vượt: Architecture.md 8.000
   dòng · design-log.md 8.000 · CHANGELOG.md 8.000 · review-report.md 4.000 · test-report.md 4.000
   · PRD.md 2.000. Cảnh báo **không chặn**, nhưng PM phải xử lý (rotate/tách) chứ không được ngó lơ
   qua nhiều lượt.
4. **Brief phải trỏ tới đoạn, không trỏ tới file.** Khi giao việc, PM ghi rõ `docs/Architecture.md`
   **§6.14.7** hoặc dải dòng cụ thể, kèm gợi ý `sed -n '<from>,<to>p'` — **không viết "đọc
   Architecture.md"**. Đây là luật, không phải lời khuyên: với tài liệu cỡ này, "đọc cả file" là một
   chỉ thị bất khả thi mà agent sẽ âm thầm thực hiện dở dang, mỗi agent một mảnh khác nhau.

**Bối cảnh (vì sao Protocol này tồn tại)**: 2026-09-10, `Architecture.md` đạt **12.818 dòng
(~238k token)** — lớn hơn context window của một agent, trong đó 44% là nhật ký chứ không phải kiến
trúc. `review-report.md` đạt 9.576 dòng, tích luỹ liên tục từ Increment 1 không rotate. Nghĩa là mọi
brief kiểu *"Dev đọc Architecture.md trước khi code"* đã **không thể thực thi được** từ lâu — và đây
chính là cùng một cơ chế đã sinh ra Bug #5 (không ai nối OCR→dịch) và Bug #9 (không ai audit lại
bước hậu kỳ cũ): **mỗi vai nhìn một mảnh khác nhau của cùng một tài liệu**.

*Vá lần đầu 2026-09-10*: tách 12 khối nhật ký (5.650 dòng) từ Architecture.md sang `design-log.md`
(Architecture.md còn 7.197 dòng, có bảng ánh xạ tiêu đề cũ → vị trí mới để `grep` cũ vẫn tra ra);
rotate 20 đợt review cũ sang `docs/archive/review-report-until-2026-09-10.md` (review-report.md còn
2.183 dòng).

## Protocol D — Checkpoint expert one-off, giới hạn tần suất

Hai vai **không thường trực**, không tham gia vòng lặp Dev↔Reviewer/QA. Chỉ được gọi tại đúng
checkpoint, ra một bản phản biện, rồi kết thúc — không giữ context xuyên suốt pipeline.

| Vai | Model | Agent file | Gọi khi nào |
|---|---|---|---|
| Domain Expert — PDF/typography/dịch thuật | Opus | `.claude/agents/domain-expert.md` | (1) Sau khi Tech Lead thiết kế xong một hạng mục chạm layout/typography/chất lượng dịch, **trước** khi Dev implement. (2) Khi một bug về chất lượng đầu ra tái diễn qua ≥2 vòng Dev↔QA |
| Critic — phản biện độc lập | Fable | `.claude/agents/critic.md` | Sau khi Tech Lead ra thiết kế cho hạng mục phức tạp, **trước** Human Checkpoint 2. Phản biện độc lập, **không đồng thuận ngầm** với Tech Lead |

Giới hạn: tối đa **2 lần cho mỗi (hạng mục, checkpoint)** — lần 1 phản biện, lần 2 xác nhận bản đã
sửa. Lần 3+ chỉ khi PM ghi tường minh lý do vào `docs/expert-notes/`: (a) bản nhận xét trước **tự
mâu thuẫn** (phải chỉ rõ 2 điểm mâu thuẫn), hoặc (b) **phạm vi hạng mục đã đổi thật** (trỏ dòng
history). Không có lý do → không gọi.

Cùng một expert bị gọi cho ≥4 hạng mục liên tiếp trong 1 phase → PM đề xuất Hiếu cân nhắc thêm vai
thường trực tương ứng (dấu hiệu vai đó đã hết tính "one-off").

Kết quả mỗi lần gọi ghi vào `docs/expert-notes/<role>-<YYYYMMDD>-<chủ đề>.md`. PM tổng hợp điểm cần
sửa vào Architecture.md/design-log.md **trước khi** trình Hiếu.

*Tiền lệ BB*: chính vai này (chạy model Fable) đã tìm ra **Bug #9** — `font_shrink_page()` phá
output của babeldoc, kèm mất chữ thật ở trang 26. 3 file `docs/expert-review-*.md` hiện có là các
lần gọi kiểu ad-hoc trước khi có Protocol D.

## Protocol E — Đồng bộ môi trường thật ↔ git

Thay đổi đã áp dụng lên **môi trường chạy thật** phải có commit tương ứng trong **24 giờ**. Với
BB-Translation, "môi trường thật" gồm:

- `.env` — API key, `pdf_translate_engine`, model/provider mặc định, ngưỡng cost gate
- `data/bb_translation.db` — migration schema (kể cả migration idempotent chạy lúc startup)
- **Version tool bên thứ ba** đã cài trong `.venv` — `pdf2zh`, `babeldoc`, `MinerU`,
  `bilingual_book_maker`, SDK provider (đổi version → Protocol 5 R5-05: verify lại toàn bộ contract
  liên quan, **không kế thừa nguồn xác thực cũ**)
- `fonts/` — font đang được nhúng vào PDF đầu ra
- `docker/` — cấu hình service đang chạy thật

Áp dụng xong → ghi ngay `infra_pending[]` (`applied_at`, `target`, `description`, `commit: null`).
Quá hạn 24h chưa có commit → `validate_state.py` **fail**, PM không dispatch bước nào chạm cùng
`target`. Đóng bước (`steps[].status = done`) chỉ khi: Dev báo commit hash, PM xác minh bằng
`git log`, và Reviewer/QA đã pass.

**Luật bổ sung (bài học AB-RnD 2026-09-10)**: trước khi đóng một `infra_pending[]` (điền `commit`),
phải chạy `grep -rn "chưa apply\|chua apply\|\[UNVERIFIED\]" docs/` và sửa hết chỗ liên quan tới
đúng thay đổi đó — không chỉ điền `commit` rồi coi là xong. Nguyên nhân gốc của việc tài liệu nói
sai trạng thái là **đóng infra_pending mà không cập nhật tài liệu mô tả bước đó**.

## Protocol F — Ma trận tool ↔ trách nhiệm

Mỗi agent được cấp **đúng và đủ** tool cho output mà nhiệm vụ của nó yêu cầu:

| Vai | Tool | Ghi chú |
|---|---|---|
| PM | Read, Grep, Glob, Write, Edit, Bash*, Agent | `Bash` **chỉ read-only**: `git status/log/diff/show`, `python3 scripts/validate_state.py`. Không commit/push/test/deploy |
| BA | Read, Grep, Glob, Write, Edit | Ghi PRD Business Rules |
| Tech Lead | Read, Grep, Glob, Write, Edit, Bash, WebSearch, WebFetch | Cần web để verify contract tool bên thứ 3 (Protocol 5 R5-01) |
| Dev | Read, Grep, Glob, Write, Edit, Bash | Chạy được test/ruff |
| Reviewer | Read, Grep, Glob, Bash, **Write, Edit** | Vai chỉ-đọc **vẫn cần Write** vì output là `docs/review-report.md` |
| QA | Read, Grep, Glob, Bash, **Write, Edit** | Cần Edit để **append** từng đợt vào `docs/test-report.md` |
| Domain Expert / Critic | Read, Grep, Glob, Bash, Write | Ghi `docs/expert-notes/` |

Giới hạn phạm vi ghi bằng **luật viết trong chính file agent** ("chỉ được ghi vào
`docs/review-report.md`"), **không** bằng cách cắt tool — cắt `Write` của Reviewer chỉ khiến nó báo
kết quả trong chat và vi phạm Protocol 1 (đúng lỗi AB-RnD đã gặp và phải vá).

Mọi brief giao việc cho agent ghi vào file dùng chung (`review-report.md`, `test-report.md`,
`CHANGELOG.md`, `design-log.md`, `project_state.json`) **bắt buộc** nhắc lại R7-03: *"đọc file hiện
có trước, APPEND section mới vào cuối, KHÔNG xoá/ghi đè nội dung cũ"*.
