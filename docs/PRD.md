# PRD — BB-Translation

> Pipeline dịch tài liệu ngành bánh (EN → VI), giữ nguyên layout gốc
> Version gốc: 1.0 | Ngày: 2026-09-03 | Phase gốc: Planning (build từ đầu)
> **Cập nhật 2026-09-08**: sản phẩm đã release tới **v1.2.7** (xem `project_state.json`) — §1
> dưới đây là bản ghi GỐC lúc lên kế hoạch xây từ đầu, giữ nguyên làm tài liệu tham chiếu lịch
> sử, KHÔNG mô tả trạng thái hiện tại. Nội dung mới nhất (US-15 kích hoạt lại, US-17→US-22 ở
> §3, business rules §4.10-4.12, backlog §9) là **bổ sung tính năng lên trên nền đã release**,
> không phải build lại. Xem `docs/CHANGELOG.md` cho lịch sử đầy đủ giữa 2 mốc.

---

## 1. Tổng quan

> ⚠️ Toàn bộ §1.1/§1.2 là bản ghi GỐC (2026-09-03), mô tả yêu cầu lúc sản phẩm CHƯA có gì.
> Đọc để hiểu bối cảnh ban đầu, không dùng để suy ra sản phẩm hiện có đúng như vậy — nhiều thứ
> đã đổi qua các increment (vd EPUB output không còn convert PDF, xem US-22).

### 1.1. Bản user *(nguyên văn 2026-09-03, lúc chưa có sản phẩm)*
Tôi cần một công cụ dịch sách/tạp chí ngành bánh (200-500 trang) từ tiếng Anh sang tiếng Việt. File dịch phải giữ nguyên layout gốc, tiếng Việt hiển thị đúng font không lệch dòng. Có danh sách thuật ngữ chuyên ngành (glossary) import từ Excel, sửa trên web. Chạy batch nhiều file, tự chia nhỏ file lớn.

### 1.2. Bản dev (PM translation)
Xây dựng document-translation pipeline xử lý PDF/EPUB 200-500 trang chứa layout phức tạp (bảng baker's percentage, công thức, ảnh kỹ thuật). Pipeline phải:
- Giữ nguyên spatial layout (vị trí text/ảnh/bảng) qua overlay rendering
- Đảm bảo Vietnamese Unicode glyph coverage đầy đủ trên embedded font
- Xử lý text-length expansion (VI dài hơn EN ~20-40%) bằng concise translation prompt + auto font-shrink (chỉ engine pdf2zh — babeldoc tự fit, xem US-05 cập nhật 2026-09-09)
- Hỗ trợ domain-specific glossary (Excel import/export + web CRUD) inject vào translation prompt
- Batch orchestration với failure isolation + resumable chunking
- Auto-convert imperial → metric units trong baking formulas
- Multi-model support: Claude, OpenAI, Gemini, DeepSeek, DeepL, Ollama (local)
- Chế độ "Markdown parse-only": xuất Markdown giữ nguyên layout/công thức, KHÔNG dịch
- Containerized (Docker) cho local deployment, sẵn sàng migrate lên cloud

---

## 2. Yêu cầu đã xác nhận từ user

| # | Yêu cầu | Chi tiết |
|---|---------|----------|
| 1 | Input formats | PDF born-digital (chủ yếu), EPUB, đôi khi PDF scan |
| 2 | Output format | PDF giữ nguyên layout (cả khi input là EPUB → convert sang PDF) |
| 3 | Song ngữ | Tuỳ chọn: (a) chỉ tiếng Việt, hoặc (b) song ngữ trang trái VI - trang phải EN |
| 4 | Chống tràn text | Dịch ngắn gọn + co/nén font tự động |
| 5 | Glossary | Import/export Excel, sửa trực tiếp trên web UI |
| 6 | Batch processing | Nhiều file cùng lúc, failure isolation |
| 7 | Auto-chunking | Tự chia file lớn, tránh API/memory limit |
| 8 | Đơn vị đo | Auto-convert sang metric (cups→ml, °F→°C, oz→g) |
| 9 | LLM models | Hỗ trợ nhiều model: Claude, OpenAI, Gemini, DeepSeek, DeepL, Ollama... không chỉ Claude |
| 10 | Hosting | Docker local trước (M1 Pro 32GB), sau lên cloud |
| 11 | Quy mô | Pipeline tái sử dụng dài hạn |
| 12 | User | 1 người dùng cá nhân, không cần auth |
| 13 | Markdown parse-only | Tuỳ chọn xuất Markdown giữ nguyên layout/công thức, không qua bước dịch |

> **Amendment 2026-09-08 (thay đổi mục #2)**: output EPUB v1 CHỈ là EPUB đã dịch, KHÔNG tự
> động convert PDF nữa — xem US-22 để biết lý do (rủi ro layout lộn xộn khi Calibre tự đoán
> chỗ ngắt trang cho nội dung reflow). Convert PDF cho EPUB có thể xét lại sau như tính năng
> optional riêng.

---

## 3. User Stories & Acceptance Criteria

### US-01: Upload file tài liệu
**As a** người dịch sách, **I want** upload file PDF/EPUB qua web UI, **so that** hệ thống tự detect loại file và sẵn sàng dịch.

**Acceptance Criteria:**
- **Given** user kéo thả/chọn file .pdf/.epub → **Then** hiển thị tên, kích thước, loại (born-digital/scan/EPUB)
- **Given** file không phải .pdf/.epub → **Then** reject: "Chỉ hỗ trợ PDF và EPUB"
- **Given** file > 500MB → **Then** reject: "File vượt quá 500MB"

### US-02: Batch processing
**As a** người dịch sách, **I want** upload và dịch nhiều file cùng lúc, **so that** tiết kiệm thời gian.

**Acceptance Criteria:**
- **Given** 5 file trong batch → **Then** xử lý song song tối đa 3 file, tiến trình riêng từng file
- **Given** file thứ 3 lỗi → **Then** đánh dấu "failed" + lý do, các file khác tiếp tục chạy
- File nhỏ hơn xử lý trước (shortest job first)

### US-03: Quản lý glossary chuyên ngành
**As a** người dịch sách, **I want** import glossary Excel (EN→VI), sửa trên web, export lại, **so that** thuật ngữ bánh được dịch nhất quán.

**Acceptance Criteria:**
- **Given** file Excel cột A=EN, cột B=VI → **Then** parse, preview, confirm trước khi lưu
- **Given** entry "ganache" → "(keep)" → **Then** giữ nguyên "ganache" khi dịch
- **Given** sửa "buttercream" từ "kem bơ" → "kem phủ bơ" → **Then** lưu ngay, lần dịch sau dùng bản mới
- **Given** bấm Export → **Then** tải Excel có format giống import (EN, VI, ghi chú)

### US-04: Dịch tự động giữ nguyên layout
**As a** người dịch sách, **I want** dịch EN→VI giữ nguyên layout gốc, **so that** bản dịch dùng ngay không cần dàn trang.

**Acceptance Criteria:**
- **Given** PDF born-digital 100 trang → **Then** output cùng số trang, ảnh/bảng/header giữ nguyên vị trí
- **Given** EPUB → **Then** output là file EPUB đã dịch, giữ cấu trúc chapter/HTML gốc (⚠️ **thay đổi 2026-09-08** — dòng AC gốc "output PDF đã dịch" đã bị supersede, xem US-22 để biết lý do và quyết định đầy đủ)
- **Given** PDF scan → **Then** tự động OCR (MinerU) trước, rồi dịch

**Known limitation (nhánh PDF scan, xem Architecture.md 6.10)**: pdf2zh không tự OCR được và MinerU không xuất PDF có sẵn text layer — pipeline phải tự dựng "searchable PDF" làm cầu nối: tô nền trắng phẳng đè lên vùng chữ tiếng Anh gốc (dựa theo bounding box MinerU nhận diện), sau đó ghi text đã dịch lên đúng vị trí. Ảnh/bảng/hình minh hoạ trong trang scan giữ nguyên pixel gốc, KHÔNG bị ảnh hưởng — chỉ vùng chữ thuần bị thay nền phẳng, mất texture/màu nền gốc của giấy tại đúng vị trí chữ. Đây là đánh đổi chất lượng đã được user chấp nhận sau khi xác nhận 2 hướng khác (pdf2zh tự OCR / MinerU tự xuất PDF có text layer) đều không khả thi qua thực nghiệm.

Job PDF scan bắt buộc phải fail rõ ràng (không báo "completed") nếu sau khi ghép, file output có 0 ký tự đọc được — không được để lọt silent failure như Bug #5 (xem BR-OCR-03).

**Known limitation (Bug #6 Phase 1, xem Architecture.md "Final Decision" mục V6)**: với PDF scan, hệ thống giờ **phát hiện và FLAG** (ghi vào `layout_qa_findings`, check_type `rotated_text_scan_unsupported`) các khối chữ xoay (caption, pull-quote, nhãn nghiêng...) để QA/PM soát tay thủ công, nhưng **chưa tái tạo lại đúng góc xoay** trong bản dịch — bản dịch vẫn vẽ chữ đã dịch nằm ngang tại đúng vị trí. Nguyên nhân gốc nằm ở tầng OCR: endpoint HTTP của MinerU (`mineru_endpoint`) làm phẳng góc xoay trước khi trả `middle.json`, không có field nào chứa lại góc gốc (chi tiết đầy đủ + nguồn verify tại Architecture.md 6.13.1 S-M3 và mục V1/V4). Phase 2 (tái tạo hình học thật, thiết kế đã chốt nhưng CHƯA implement) sẽ kích hoạt khi có job `pdf_scan` thật trong production sinh ra finding này.

### US-05: Xử lý text tràn
**As a** người dịch sách, **I want** hệ thống tự co/nén font khi text VI tràn, **so that** layout không vỡ.

**Cập nhật phạm vi (2026-09-09, sau Bug #9 — xem `docs/Architecture.md` mục "Bug #9",
`docs/CHANGELOG.md` mục "Bug #9", Protocol 8 trong `CLAUDE.md`)**: acceptance criteria dưới đây
**chỉ còn áp dụng khi engine dịch là `pdf2zh`** (`Settings.pdf_translate_engine == "pdf2zh"`).
Với engine `babeldoc` (mặc định từ 2026-09-05, xem 6.14.7) — babeldoc tự co giãn/bóp cỡ chữ bên
trong chính nó (tới tối thiểu 10%, bỏ hẳn đoạn nếu vẫn không vừa) TRƯỚC khi trả output; app **không
còn can thiệp thêm** bước co font hậu kỳ nào cho babeldoc nữa (đã verify: chạy hậu kỳ này trên
output babeldoc chỉ gây lỗi thật — Bug #8 lệch toạ độ + mất chữ, cả 2 đã fix bằng cách tắt hẳn bước
này cho babeldoc thay vì sửa tiếp). Hệ quả: app **không đo và không flag** trường hợp babeldoc âm
thầm bỏ 1 đoạn không vừa khung (khoảng trống đã biết, chưa vá — xem `project_state.json`
`blockers`).

**Acceptance Criteria (chỉ áp dụng cho pdf2zh):**
- Bước 1: giảm font size tối đa 20%
- Bước 2: horizontal scaling (condensed) tối đa 85%
- Bước 3: nếu vẫn tràn → flag cho user review (không cắt text)

**Acceptance criteria cho babeldoc**: không có bước hậu kỳ nào của app — chống tràn khung là trách
nhiệm nội bộ của babeldoc, ngoài tầm kiểm soát/đo lường của pipeline này.

### US-06: Auto-chunking file lớn
**As a** người dịch sách, **I want** hệ thống tự chia file lớn thành chunk, **so that** không bị lỗi do limit.

**Acceptance Criteria:**
- **Given** PDF > 50 trang → **Then** tự chia chunk 30-50 trang, hiển thị số chunk
- **Given** dịch bị gián đoạn ở chunk 5/10 → **Then** retry từ chunk 5, không dịch lại 1-4
- Chunk có 1-2 trang overlap để giữ context liên tục

### US-07: Theo dõi tiến trình
**As a** người dịch sách, **I want** xem realtime % hoàn thành, chunk hiện tại, thời gian còn lại.

**Acceptance Criteria:**
- Dashboard hiển thị: tên file, %, chunk X/Y, thời gian chạy, ETA
- Timeout > 5 phút → auto retry chunk + thông báo

### US-08: Xử lý lỗi và retry
**Acceptance Criteria:**
- API timeout/rate limit → retry exponential backoff (2s→4s→8s), max 3 lần
- Hết retry → đánh dấu "failed", giữ nguyên kết quả chunk đã thành công

### US-09: Download kết quả
**Acceptance Criteria:**
- Tuỳ chọn 1: PDF đơn ngữ (chỉ tiếng Việt, giữ layout gốc)
- Tuỳ chọn 2: PDF song ngữ (trang trái VI, trang phải EN)

### US-10: Giữ nguyên thuật ngữ gốc
**Acceptance Criteria:**
- Glossary entry "fondant" → "(keep)" → kết quả: "Trải fondant đều lên lớp meringue."

### US-11: PDF scan (OCR)
**Acceptance Criteria:**
- Detect scan → auto OCR (MinerU) → thông báo "Đang OCR..."
- **OCR confidence (định nghĩa đã verify với MinerU thật, xem Architecture.md 6.9.5)**: confidence không phải 1 điểm số tổng thể MinerU trả về (MinerU không cung cấp field này), mà là **trung bình có trọng số theo số đoạn text (span) đã qua OCR**, lấy từ `middle_json` cấp span. Ba nhánh:
  - `ocr_confidence ≥ 0.80` → tiếp tục bình thường, không cảnh báo
  - `ocr_confidence < 0.80` → cảnh báo user "Chất lượng OCR thấp (X%), kết quả dịch có thể không chính xác." (v1.0: thông báo **không chặn job** — job vẫn tự động chạy tiếp, cảnh báo chỉ hiển thị qua WebSocket `ocr_warning` event + field trong response API để user biết mà tự kiểm tra output sau. Cơ chế pause/resume-do-user-quyết-định là scope v1.1, xem Architecture.md 6.10.6)
  - `ocr_confidence = NULL` (không có span nào đi qua OCR — ví dụ trang chỉ toàn hình ảnh không có text nhận dạng được) → cảnh báo riêng "Không xác định được chất lượng OCR cho trang này", cùng cơ chế thông báo-không-chặn như nhánh trên (v1.0)

### US-12: Lịch sử dịch
**Acceptance Criteria:**
- Danh sách file đã dịch: tên, ngày, trạng thái, nút download
- Upload file trùng hash → thông báo "File đã dịch ngày X. Dùng kết quả cũ hay dịch lại?"

### US-13: Auto-convert đơn vị đo lường
**As a** người dịch sách, **I want** hệ thống tự convert imperial→metric trong công thức, **so that** người đọc VN dễ hiểu.

**Acceptance Criteria:**
- "2 cups flour" → "480ml bột mì" (hoặc "480g" tuỳ nguyên liệu)
- "350°F" → "175°C"
- "8 oz butter" → "225g bơ"
- Bảng conversion chuẩn cho các nguyên liệu bánh phổ biến

### US-14: Hỗ trợ nhiều LLM model
**As a** người dịch sách, **I want** chọn model dịch (Claude, OpenAI, Gemini, DeepSeek, DeepL, Ollama local), **so that** tối ưu chi phí và chất lượng.

**Acceptance Criteria:**
- UI cho phép chọn model trước khi dịch
- Mỗi model cần config riêng (API key, endpoint, model name)
- Glossary injection hoạt động đúng với mọi model **áp dụng cho pipeline EPUB**. Với pipeline PDF, glossary injection hoạt động đúng với Claude, OpenAI, Gemini, DeepSeek, Ollama.
- **Giới hạn đã biết (BR-PROVIDER-01)**: DeepL KHÔNG hỗ trợ custom prompt/glossary khi dịch PDF (do ràng buộc kỹ thuật của pdf2zh — DeepL không nhận custom prompt qua tool này). UI **ẩn DeepL khỏi danh sách chọn khi input là PDF** (born-digital hoặc scan), chỉ hiện DeepL khi input là EPUB hoặc khi dùng để test kết nối/estimate cost.
- **Provider mặc định**: DeepSeek (chi phí thấp nhất, hỗ trợ native qua pdf2zh, có context caching phía server). User có thể đổi provider khác trước khi chạy job.

### US-15: Xuất Markdown parse-only (không dịch) — ✅ NHÁNH PDF DONE (2026-09-08, chờ commit), nhánh EPUB chờ US-22
**As a** người dịch sách, **I want** xuất file gốc sang Markdown giữ nguyên layout, bảng, công thức mà KHÔNG qua bước dịch, **so that** tôi có thể tự kiểm tra chất lượng parse trước khi tốn chi phí dịch, hoặc dùng Markdown này cho mục đích khác (lưu trữ, đưa vào hệ tri thức, tự dịch thủ công).

**Xác nhận lại phạm vi (2026-09-08)**: user xác nhận (mục #7 trong yêu cầu mới, trả lời trực tiếp PM) đây là Markdown của **bản GỐC chưa dịch** — đúng định nghĩa cũ, KHÔNG phải Markdown của bản đã dịch. Thiết kế/AC dưới đây giữ nguyên, không cần viết lại. "Giữ nguyên vị trí" (từ user dùng) được hiểu là: giữ đúng cấp heading + loại list + cấu trúc bảng (AC dòng 3) VÀ ảnh chèn đúng chỗ gốc trong nội dung (AC dòng 4) — KHÔNG phải toạ độ tuyệt đối kiểu PDF (Markdown không có khái niệm đó). Nếu hiểu sai ý này, cần user xác nhận lại trước khi Tech Lead bắt đầu.

**Known limitation (mang từ v1.0 sang, vẫn đúng tại 2026-09-08)**: API chấp nhận `job_type=parse_only` nhưng `JobOrchestrator` chưa có nhánh xử lý riêng (chỉ mới lắp luồng `translate` qua pdf2zh/babeldoc) — mọi job `parse_only` hiện tại fail ngay với thông báo rõ ràng, không giả vờ thành công. Cần 1 nhánh `MinerU-only` riêng trong `JobOrchestrator` (đọc Architecture.md section 6.8, đã có thiết kế sẵn — Tech Lead cần rà lại xem còn khớp code hiện tại không trước khi giao Dev, vì Architecture.md 6.8 viết từ thời điểm trước nhiều thay đổi lớn như AIMD/babeldoc).

**Acceptance Criteria:**
- **Given** user upload file (PDF born-digital, PDF scan, hoặc EPUB) và chọn chế độ "Chỉ xuất Markdown (không dịch)" → **Then** hệ thống chạy MinerU parse (OCR nếu cần) và xuất file `.md` + thư mục ảnh liên quan, KHÔNG gọi bất kỳ LLM translation API nào
- **Given** file gốc có bảng công thức nhiều cột → **Then** Markdown output giữ nguyên cấu trúc bảng, số liệu/đơn vị giữ nguyên y hệt bản gốc, không convert đơn vị. **Sửa 2026-09-08 (Domain Expert tự chạy MinerU thật phát hiện)**: MinerU thực tế xuất bảng dạng HTML `<table>` nhúng trong file `.md` (GitHub-Flavored Markdown cho phép HTML thô), KHÔNG phải Markdown table syntax (`| a | b |`) thuần — bảng vẫn hiển thị đúng khi mở bằng renderer hỗ trợ GFM, chỉ khác cú pháp so với kỳ vọng ban đầu. Xem Architecture.md §6.15 cho chi tiết.
- **Given** file gốc có heading nhiều cấp, bullet/numbered list → **Then** Markdown output giữ đúng cấp heading (`#`, `##`, `###`...) và đúng loại list
- **Given** file gốc có hình ảnh minh hoạ → **Then** ảnh được extract ra thư mục riêng, Markdown chèn link ảnh đúng vị trí gốc
- Chế độ này bỏ qua hoàn toàn Translation Engine và Glossary injection — chỉ chạy Parsing Engine (MinerU)
- Vì không gọi LLM dịch, chi phí = 0 (chỉ tốn compute local cho OCR/parse)

### US-16: Nén ảnh sau khi ghép (giảm dung lượng output)
**As a** người dịch sách, **I want** file PDF dịch xong có dung lượng nhỏ gọn, **so that** dễ lưu trữ/chia sẻ (case thật: 1 job 415 trang engine babeldoc ra file 808MB do ảnh minh hoạ bị nhúng lại dạng bitmap thô thay vì JPEG gốc).

**Quyết định phạm vi (chốt 2026-09-06, PM hỏi trực tiếp user)**:
- Chỉ áp dụng cho job dùng engine `babeldoc` (engine mặc định hiện tại — `src/core/config.py:135`). Engine `pdf2zh` giữ nguyên hành vi, không đổi.
- Mức nén JPEG **cố định quality=85**, không lộ ra config/UI.
- Dedupe ảnh trùng lặp (cùng ảnh, nhiều xref khác nhau): **có điều kiện** — chỉ đưa vào implementation chính thức nếu spike đo được dedupe mang lại mức giảm dung lượng **thêm ≥ 20%** so với chỉ nén JPEG (không dedupe), đo trên dữ liệu thật. Nếu spike cho kết quả < 20%, dừng ở bước nén JPEG, ghi lại kết quả đo vào `docs/Architecture.md` và defer dedupe về backlog.

**Acceptance Criteria:**
- **Given** job dùng engine `babeldoc` và file PDF đã ghép (`merge_chunk_pdfs()` output) chứa ảnh raw/uncompressed (`Filter: null`) → **Then** hệ thống re-encode các ảnh đó sang JPEG quality=85 trước khi ghi file output cuối cùng, dung lượng file giảm rõ rệt so với hiện tại
- **Given** job dùng engine `pdf2zh` → **Then** KHÔNG áp dụng bước nén này, hành vi merge giữ nguyên như hiện tại
- **Given** ảnh trong file đã ở dạng đã nén sẵn (`DCTDecode`/JPEG) → **Then** giữ nguyên, không re-encode lại (tránh generation loss do nén JPEG chồng JPEG)
- **Given** bước nén chạy xong → **Then** file PDF output vẫn mở được, số trang không đổi, nội dung/text không bị mất (không phải lỗi tương tự Bug #7/#8 ở `chunk_merge.py`)
- Nếu spike dedupe đạt ngưỡng ≥ 20%: **Given** cùng 1 ảnh xuất hiện ở nhiều trang với xref khác nhau → **Then** hệ thống gộp về 1 xref dùng chung, không nhúng lại nhiều bản sao

### US-17: Thêm từ mới trực tiếp trong tab Glossary
**As a** người dịch sách, **I want** có nút "Thêm từ mới" ngay trong tab Glossary, **so that** tôi không phải vòng qua tab Lịch sử chỉ để thêm 1 thuật ngữ.

**Acceptance Criteria:**
- **Given** user ở tab Glossary, bấm "Thêm từ mới" → **Then** hiện modal nhập `term_en` (bắt buộc), `term_vi` (optional), `notes` (optional)
- **Given** `term_en` trùng (case-insensitive, đúng BR-GLOSS-02) với 1 entry đã có → **Then** hệ thống hỏi xác nhận "Từ '<term_en>' đã có trong glossary với bản dịch '<term_vi cũ>'. Ghi đè?" trước khi lưu (xem BR-GLOSS-07 — thay hành vi ghi đè âm thầm hiện tại)
- **Given** lưu thành công → **Then** entry mới/vừa cập nhật xuất hiện ngay trong bảng, không cần reload trang
- Tái sử dụng nguyên `POST /api/glossary` đã có (`src/api/routes/glossary.py:126`) — chỉ cần sửa backend cho phần check trùng (BR-GLOSS-07), còn lại là việc frontend

### US-18: Tìm kiếm trong Glossary
**As a** người dịch sách, **I want** gõ từ khoá để lọc bảng glossary theo cả tiếng Anh lẫn tiếng Việt, **so that** tìm nhanh 1 thuật ngữ trong danh sách dài mà không phải lật từng trang.

**Acceptance Criteria:**
- **Given** gõ 1 chuỗi vào ô search → **Then** bảng chỉ hiện entry có `term_en` HOẶC `term_vi` chứa chuỗi đó (case-insensitive, substring match)
- **Given** xoá hết ô search → **Then** hiện lại toàn bộ danh sách theo scope/phân trang hiện tại
- Search cộng dồn với filter `scope` đã có, và reset về trang đầu (`offset=0`) mỗi khi đổi từ khoá
- `GET /api/glossary` thêm param `q` (optional, filter theo `term_en`/`term_vi`)

**Known limitation (chấp nhận cho v1 của tính năng này)**: search KHÔNG bỏ dấu tiếng Việt (accent-insensitive) — gõ "kem bo" sẽ không ra "kem bơ". SQLite không có unaccent built-in, thêm cơ chế này phát sinh độ phức tạp mới không cần thiết cho nhu cầu hiện tại; có thể nâng cấp sau nếu thực tế dùng thấy bất tiện.

### US-19: Lịch sử dịch — thời gian dịch, số trang, dọn UI trùng chức năng
**As a** người dịch sách, **I want** thấy tài liệu đã mất bao lâu để dịch và có bao nhiêu trang ngay trong tab Lịch sử, **so that** tôi ước lượng được thời gian cho các file tương tự lần sau.

**Acceptance Criteria:**
- **Given** job đã kết thúc (`completed`/`failed`/`cancelled`/`cost_capped`) → **Then** hiển thị "thời gian dịch" = khoảng cách từ `created_at` đến mốc kết thúc job đó
- **Given** job có `total_pages` → **Then** hiển thị số trang; **given** `total_pages` là NULL → **Then** hiện "-"
- **Given** job đang `translating`/`queued`/`chunking` → **Then** không hiện thời gian dịch (chưa có mốc kết thúc)
- Bỏ nút "+ Glossary" khỏi mỗi dòng trong tab Lịch sử — chức năng thêm thuật ngữ đã chuyển hẳn sang tab Glossary (US-17), tránh 2 nơi làm cùng 1 việc

**Known limitation cần Dev xử lý trước (không phải việc thuần frontend)**: `JobDetail`/`JobListResponse` hiện tại (`src/api/routes/jobs.py:119-146`, `_to_detail()` dòng 216-245) KHÔNG trả `total_pages`/`started_at`/`completed_at` — field `completed_at` ở dòng 87 thuộc `DuplicateJobInfo` (model khác, dùng cho cảnh báo trùng hash), không phải response job list/detail. Phải sửa response model backend trước khi frontend có gì để hiển thị.

**Quyết định phạm vi (PM chốt theo mặc định hợp lý, 2026-09-08 — user có thể yêu cầu đổi)**: tính "thời gian dịch" từ `created_at`, KHÔNG dùng `started_at`, vì `job_orchestrator.py:371` hiện gán `started_at` SAU khi OCR xong — nếu dùng `started_at` làm mốc, job PDF scan sẽ hiện thời gian ngắn hơn thực tế cảm nhận (thiếu mất đoạn OCR). Nếu Tech Lead thấy lý do kỹ thuật để giữ `started_at`, phải nêu rõ đánh đổi trong Architecture.md trước khi Dev implement khác quyết định này.

### US-20: Gợi ý thuật ngữ mới từ tài liệu vừa dịch ("Các từ mới")
**As a** người dịch sách, **I want** sau khi dịch xong, hệ thống tự gợi ý các thuật ngữ chuyên môn xuất hiện trong tài liệu mà glossary chưa có, **so that** tôi bổ sung glossary nhanh mà không phải tự đọc lại cả cuốn để tìm từ mới.

**Acceptance Criteria:**
- **Given** job dịch hoàn tất (`status=completed`) → **Then** hệ thống chạy bước trích xuất thuật ngữ, kết quả nằm trong tab Glossary, khu vực riêng "Chờ duyệt"
- **Given** 1 từ trong danh sách gợi ý đã có trong glossary (so khớp case-insensitive, đúng BR-GLOSS-02) → **Then** KHÔNG hiện từ đó trong "Chờ duyệt" — lọc trùng bắt buộc, đúng yêu cầu user
- Mỗi entry "Chờ duyệt" mặc định CHỈ có `term_en` (miễn phí, không gọi LLM) kèm số lần xuất hiện trong tài liệu; user tự gõ `term_vi` khi duyệt, HOẶC bấm nút riêng "Gợi ý bản dịch" (tốn 1 lượt gọi LLM — UI phải nói rõ đây là hành động phát sinh chi phí trước khi bấm, không tự động chạy ngầm)
- **Given** user bấm "Thêm vào glossary" trên 1 entry Chờ duyệt → **Then** entry chuyển thành glossary entry chính thức (gọi `POST /api/glossary`, áp dụng BR-GLOSS-07 nếu lỡ trùng do có job khác thêm trước), biến mất khỏi khu vực Chờ duyệt
- **Given** user bấm "Bỏ qua" → **Then** entry biến mất khỏi Chờ duyệt cho job đó; KHÔNG cấm từ đó xuất hiện lại nếu 1 job khác trong tương lai cũng chứa nó

**Known limitation/quyết định còn để ngỏ cho Tech Lead**: cơ chế trích xuất thuật ngữ (rule-based theo tần suất + danh sách từ chuyên ngành cố định, hay LLM-based đọc toàn văn) CHƯA được chốt — đây là quyết định kiến trúc có đánh đổi chi phí/độ chính xác/độ trễ khác nhau, PM không tự quyết thay Tech Lead. Giới hạn số lượng từ gợi ý tối đa/tài liệu (đề xuất khởi điểm: 30-50 từ, xếp theo tần suất) cũng cần Tech Lead chốt trong Architecture.md.

### US-21: Hiển thị phiên bản BB-Translation
**As a** người dùng, **I want** thấy đang chạy bản nào của BB-Translation, **so that** biết chắc mình đã cập nhật bản mới nhất khi báo lỗi hoặc so sánh thay đổi giữa các lần release.

**Acceptance Criteria:**
- **Given** user mở bất kỳ trang nào trong web UI → **Then** hiện version (vd "v1.2.7") ở vị trí cố định, dễ thấy (đề xuất: góc nav bar, cạnh tên "BB-Translation")
- Version lấy từ `GET /api/version` đã có sẵn (`src/api/main.py:110-112`, đọc trực tiếp `pyproject.toml`) — KHÔNG hardcode chuỗi version trong JS, tránh lệch số với `pyproject.toml` ở lần release sau

### US-22: Dịch EPUB (hoàn thiện pipeline, hiện đang bị chặn cứng)
**As a** người dịch sách, **I want** dịch được file EPUB giống như PDF, **so that** không phải tự tìm công cụ khác convert EPUB sang định dạng khác trước khi dùng BB-Translation.

**Hiện trạng**: `job_orchestrator.py` chủ động raise `EpubNotSupportedError` ngay khi `file_type == EPUB` (`src/core/job_orchestrator.py:257-260`) — mọi job EPUB fail ngay lập tức, dù `file_router.py` đã detect đúng loại file. Đây là hoàn thiện 1 tính năng đã cam kết trong PRD gốc (§8 "Trong scope v1.0"), không phải feature hoàn toàn mới.

**Cập nhật 2026-09-08 — Architecture đã xong (Human Checkpoint 2)**: Tech Lead đã research thật `bilingual_book_maker` (cài bản thật, đọc source, chạy thử) và **BÁC BỎ** hướng dùng tool này làm pipeline chính — lý do: (a) chỉ chia được việc dịch ở cấp CẢ TÀI LIỆU, trên EPUB thật của user 97,2% nội dung nằm trong 1 tài liệu duy nhất nên không thể chunk để chặn chi phí giữa chừng (vi phạm BR-EPUB-02 ngay từ đầu); (b) khi lỗi thật vẫn thoát exit code 0 (xác nhận bằng chạy thật) — sẽ tái diễn kiểu silent-failure của Bug #5; (c) đường Claude của tool đang hỏng do gọi SDK với tham số đã bị Anthropic bỏ, không hỗ trợ DeepSeek (provider mặc định). Hướng đã chọn: tự parse cấu trúc EPUB bằng `ebooklib`, dịch qua chính Translation Engine nội bộ đã có (tái dùng chunk/resume/cancel/cost-gate của PDF). Xem Architecture.md §6.15-§6.20 cho toàn bộ thiết kế + bằng chứng verify.

**Acceptance Criteria:**
- **Given** upload file `.epub` → **Then** hệ thống ước tính chi phí trước khi chạy (như PDF), có chia nhỏ theo chương để hỗ trợ đặt trần chi phí + dừng/tiếp tục giữa chừng (xem BR-EPUB-02)
- **Given** job EPUB hoàn tất → **Then** output là 1 file `.epub` đã dịch, giữ cấu trúc chapter/HTML gốc, **mặc định bật bản song ngữ** (đoạn VI chèn ngay sau đoạn EN gốc, không thay thế — chi phí LLM phát sinh = 0) — **KHÔNG** tự động convert PDF (xem quyết định thay đổi bên dưới)
- **Given** glossary có entry áp dụng → **Then** injection hoạt động đúng (kế thừa AC của US-14 đã có)
- **Given** job EPUB hoàn tất → **Then** file output mở lại được, không mất chương, và có nội dung tiếng Việt thật trong ít nhất vài đoạn khác nhau (không chỉ tin `status=completed` — xem BR-EPUB-05)

**Quyết định thay đổi so với PRD gốc (2026-09-08, user xác nhận trực tiếp qua PM)**: output EPUB v1 CHỈ trả về EPUB đã dịch, KHÔNG tự động convert PDF như §2 mục 2 / US-04 bản gốc quy định. Lý do: EPUB là định dạng reflow (không có trang cố định — trình đọc tự ngắt dòng/trang theo màn hình), nên Calibre `ebook-convert` phải TỰ ĐOÁN chỗ ngắt trang khi ép vào khổ PDF cố định → rủi ro layout lộn xộn thật (tiêu đề mồ côi cuối trang, ảnh công thức tách khỏi bước làm) mà PDF born-digital (vốn đã có trang cố định sẵn) không gặp phải. User đã tự đặt câu hỏi này và đồng ý hướng giảm rủi ro. Convert PDF cho EPUB có thể cân nhắc lại như 1 tính năng optional RIÊNG sau khi thấy chất lượng bản dịch EPUB ổn — không nằm trong scope đợt này. **Điều này supersede §2 mục 2 và dòng AC "output PDF đã dịch" trong US-04 bản gốc.**

**Quyết định cost-safety (2026-09-08, user chọn phương án đầu tư đầy đủ thay vì làm nhanh)**: EPUB phải có cơ chế ước tính + chặn chi phí ngang hàng với PDF (Lớp 2/Lớp 3, Architecture.md §6.11), KHÔNG được release ở dạng "gọi 1 lần cho cả cuốn, không chunk" như phác thảo cũ ở Architecture.md §6.7. BA xác nhận thiết kế cũ đó khiến `total_pages=None` cho EPUB (`src/api/routes/upload.py:127-134` cố ý không đếm trang) → Lớp 2 hiện **vô hiệu hoá hoàn toàn** cho EPUB (`src/api/routes/jobs.py:724-725` raise 400 "chua co total_pages" thay vì chặn đúng cách bằng ước tính); không có chunk nên Lớp 3 (running accumulator giữa chừng) cũng vô hiệu. Nếu làm y theo §6.7 cũ, rủi ro lặp lại sự cố $6.50 (Architecture.md §6.11) nhưng ở quy mô nguyên cuốn sách gọi 1 lần, không có điểm dừng giữa chừng. Tech Lead phải thiết kế lại: đơn vị chunk = chương (đơn vị tự nhiên của EPUB, khác PDF chunk theo range trang).

**Protocol 5 R5-01 — ĐÃ ĐÓNG (2026-09-08)**: Tech Lead đã tự cài `bbook_maker==1.1.0` thật, đọc source đã cài, chạy `--help` + chạy thật 3 lần trên EPUB thật (14 claim E-01..E-14, mỗi claim kèm `file:line` hoặc log chạy thật, xem Architecture.md §6.20.2). Kết quả verify chính là lý do dẫn tới quyết định BÁC BỎ tool này ở trên. `ebooklib`/`bs4` (hướng thay thế đã chọn) cũng đã verify thật trên Python 3.14.7. Còn đúng 1 điểm `⚠️ ASSUMED` cần Dev tự làm R5-02 spike trước khi implement đầy đủ: cài `ebooklib`+`bs4` vào `.venv` chính thức của project và đo lại việc ghi ngược EPUB (byte-identical cho phần không đổi) — xem Architecture.md §6.20.11 mục 3 cho chi tiết.

**DB migration — CHỐT 2026-09-08**: batch này thêm cột/bảng mới (`Job.finished_at`, `Job.total_units`, `Chunk.unit_start`/`unit_end`, bảng `suggested_terms`). DB hiện có **10 job đã dịch + 114 glossary entry thật đã curate** (đo trực tiếp) — KHÔNG xoá DB, Dev viết migration script `ALTER TABLE` giữ nguyên dữ liệu này.

---

## 4. Business Rules

### 4.1. Input Detection
- **BR-INPUT-01**: Auto-detect loại file qua extension + nội dung
- **BR-INPUT-02**: PDF có text layer > 90% trang → born-digital. < 90% → scan → OCR pipeline
- **BR-INPUT-03**: File tối đa 500MB
- **BR-INPUT-04**: Chỉ .pdf và .epub

### 4.2. Glossary
- **BR-GLOSS-01**: Glossary match ưu tiên trước dịch tự do
- **BR-GLOSS-02**: Case-insensitive matching cho EN
- **BR-GLOSS-03**: Trùng term → last-updated wins
- **BR-GLOSS-04**: Target = "(keep)" hoặc để trống → giữ nguyên EN
- **BR-GLOSS-05**: Excel format: cột 1 = EN, cột 2 = VI, cột 3 = ghi chú (optional)
- **BR-GLOSS-06**: 2 cấp scope: Global glossary (mọi file) + Project glossary (per batch, override global)
- **BR-GLOSS-07** *(mới, 2026-09-08)*: Khi thêm 1 entry mới (qua US-17 hoặc duyệt từ US-20) mà `term_en` đã trùng (case-insensitive, BR-GLOSS-02) với entry hiện có, hệ thống PHẢI hỏi xác nhận ghi đè, hiện rõ bản dịch cũ, trước khi lưu — **thay thế hành vi ghi đè âm thầm hiện tại** của `bulk_import()`/`GlossaryManager` (last-updated-wins theo BR-GLOSS-03 vẫn đúng cho import Excel hàng loạt, nhưng KHÔNG còn áp dụng "âm thầm" cho luồng thêm-1-entry-đơn-lẻ qua UI). Lý do: glossary là dữ liệu đã curate thủ công, ghi đè nhầm không cảnh báo là rủi ro mất dữ liệu thật.
- **BR-GLOSS-08** *(mới, 2026-09-08)*: Search (US-18) lọc theo CẢ `term_en` lẫn `term_vi`, không giới hạn chỉ cột EN.

### 4.3. Chunking
- **BR-CHUNK-01**: File > 50 trang hoặc > 20MB → bắt buộc chunk
- **BR-CHUNK-02**: Ưu tiên chia theo chapter/section, fallback 30-50 trang/chunk
- **BR-CHUNK-03**: Overlap 1-2 trang giữa các chunk cho context
- **BR-CHUNK-04**: Auto-merge sau khi dịch, không trùng nội dung
- **BR-CHUNK-05**: Resumable — lưu state chunk đã xong, retry từ chunk lỗi

### 4.4. Batch Processing
- **BR-BATCH-01**: Failure isolation — 1 file lỗi không ảnh hưởng file khác
- **BR-BATCH-02**: Retry: transient error → exponential backoff 3 lần; permanent error → fail + log
- **BR-BATCH-03**: Concurrency tối đa 3 file song song (configurable)
- **BR-BATCH-04**: Shortest job first

### 4.5. Font & Text Overflow
- **BR-FONT-01**: Font phải hỗ trợ đầy đủ Vietnamese Unicode. Default: Noto Sans/Serif
- **BR-FONT-02**: Auto-shrink 3 bước: giảm font 20% → condensed 85% → flag user review. **Chỉ áp
  dụng cho engine `pdf2zh`** kể từ Bug #9 (2026-09-09) — babeldoc tự fit bên trong nó, app không
  chạy bước này cho babeldoc nữa (xem chi tiết ở US-05 và `docs/Architecture.md` mục "Bug #9")
- **BR-FONT-03**: System prompt yêu cầu dịch súc tích, target VI ≤ 130% độ dài EN

### 4.6. Typography & Structure Preservation
- **BR-TYPO-01**: Font size theo cấp heading phải tương đồng với bản gốc. Nếu gốc H1=24pt, H2=18pt, H3=14pt → bản dịch giữ nguyên tỷ lệ size đó. Không được tự ý thay đổi size heading giữa các cấp.
- **BR-TYPO-02**: Cấu trúc list/bullet phải được bảo toàn 1:1. Nếu bản gốc là bullet list → bản dịch phải là bullet list. Nếu gốc là numbered list → dịch cũng numbered list. Không được flatten list thành paragraph hoặc ngược lại.
- **BR-TYPO-03**: Bold, italic, underline và các text decoration khác phải giữ nguyên vị trí tương ứng trong bản dịch.
- **BR-TYPO-04**: Indentation level của nested list/sub-items phải giữ nguyên cấp bậc so với bản gốc.

### 4.7. Unit Conversion
- **BR-UNIT-01**: Auto-detect đơn vị imperial trong context công thức bánh
- **BR-UNIT-02**: Convert theo bảng chuẩn ngành bánh (cups→ml/g tuỳ nguyên liệu, °F→°C, oz→g)
- **BR-UNIT-03**: Chỉ convert trong context công thức/recipe, không convert trong prose thông thường
- **BR-UNIT-04**: Ở chế độ Markdown parse-only (US-15), KHÔNG áp dụng convert đơn vị — giữ nguyên số liệu gốc 100% vì mục đích là parse thuần, không dịch/biến đổi nội dung

### 4.8. Markdown Parse-only Mode
- **BR-PARSE-01**: Chế độ này chỉ chạy Parsing Engine (MinerU), bỏ qua hoàn toàn Translation Engine, Glossary injection, và Unit Conversion
- **BR-PARSE-02**: Áp dụng được cho cả 3 loại input: PDF born-digital, PDF scan (qua OCR), EPUB (convert cấu trúc HTML sang Markdown)
- **BR-PARSE-03**: Output gồm 1 file `.md` + 1 thư mục `images/` chứa ảnh extract kèm theo, đường dẫn ảnh trong Markdown là relative path
- **BR-PARSE-04**: Không tính vào "translation history" (US-12) vì không phải bản dịch — lưu riêng vào "parse history"
- **BR-PARSE-05**: Không tốn chi phí LLM API — chỉ hiển thị thời gian xử lý ước tính, không hiển thị estimated cost
- **BR-PARSE-06** *(mới, 2026-09-08, theo yêu cầu user)*: Số mũ, chỉ số dưới, phân số (không riêng công thức bánh — áp dụng chung cho nội dung toán/lý/hoá nếu tài liệu chứa) PHẢI giữ đúng ký hiệu khi chuyển sang Markdown, không được làm mất/hiểu sai nghĩa (vd "½" hoặc `<sup>1</sup>/<sub>2</sub>` không được rút gọn thành "/2"). Thiết kế kỹ thuật dùng chung với BR-EPUB-06, xem Architecture.md §6.21.

### 4.9. Image Compression (US-16)
- **BR-IMGCOMP-01**: Chỉ áp dụng cho job dùng engine `babeldoc` (`settings.pdf_translate_engine == "babeldoc"`). Job dùng `pdf2zh` không đổi hành vi.
- **BR-IMGCOMP-02**: Chạy sau `merge_chunk_pdfs()`, trước khi file được coi là `job.output_path` cuối cùng. Chỉ re-encode ảnh đang ở dạng raw/uncompressed (`Filter: null`); ảnh đã là JPEG (`DCTDecode`) giữ nguyên, không nén chồng lần 2. — ⏸ **Đề xuất mở rộng phạm vi 2026-09-08, xem BR-IMGCOMP-02b bên dưới** (giữ nguyên câu chữ gốc để đối chiếu lịch sử, không xoá).
- **BR-IMGCOMP-03**: Mức nén JPEG cố định quality=85, không cấu hình qua `.env` hay UI.
- **BR-IMGCOMP-04**: Dedupe ảnh trùng lặp (nhiều xref cùng nội dung ảnh) là tính năng có điều kiện — chỉ implement chính thức nếu spike đo trên dữ liệu thật cho thấy mức giảm dung lượng thêm ≥ 20% so với chỉ nén JPEG. Kết quả spike (đạt hay không đạt ngưỡng) phải được ghi vào Architecture.md kèm số liệu đo, không được quyết định bằng suy đoán (theo tinh thần Protocol 5 R5-02 của project — dù PyMuPDF là thư viện nội bộ không thuộc phạm vi Protocol 5 bắt buộc, nguyên tắc "đo thật trước khi quyết định" vẫn nên áp dụng vì đây là ngưỡng số liệu cụ thể user đặt ra).

**Sửa đổi đề xuất 2026-09-08 (US-16 v2) — ⏸ CHỜ USER DUYỆT (Protocol 2), Dev chưa được implement:**

- **BR-IMGCOMP-02b** (thay thế phạm vi của BR-IMGCOMP-02, các phần khác của 02 giữ nguyên): re-encode ảnh đang ở dạng raw/uncompressed (`Filter: null`) **HOẶC nén lossless bằng zlib (`Filter: /FlateDecode`)**. Ảnh đã ở codec nén ảnh chuyên dụng (`DCTDecode`, `CCITTFaxDecode`, `JPXDecode`, `JBIG2Decode`) vẫn **giữ nguyên tuyệt đối, không nén chồng lần 2** — phần này của BR-IMGCOMP-02 không đổi. Lý do sửa: `/FlateDecode` là nén **lossless** nên với ảnh chụp nó gần như không giảm được dung lượng; đo trên job thật `78674af9` (30 trang, 46.87 MB): 57 ảnh Flate chiếm 28.72 MB, re-encode JPEG q85 còn 7.04 MB → file 46.87 MB → 25.19 MB (−46.3%), text và số trang giữ nguyên 100%, sai khác pixel trung bình 0.0613/255. Số liệu đầy đủ + guard bắt buộc: `docs/Architecture.md` mục "US-16 v2".
- **BR-IMGCOMP-02c** (guard an toàn đi kèm 02b, bắt buộc — **bản cập nhật 2026-09-08 sau phản biện Domain Expert**): chỉ re-encode ảnh có `BitsPerComponent = 8` và colorspace thuộc nhóm Gray/RGB/CMYK (kể cả `ICCBased`). Ảnh 1-bit bilevel (bản scan đen trắng, line art), ảnh `Indexed`/`Separation`/`DeviceN`, ảnh có `/SMask`, `/ImageMask` **hoặc `/Mask`** (color-key hay stencil), ảnh còn kênh alpha sau khi giải mã, và ảnh nhỏ hơn 4 KB đều **giữ nguyên**. Điều khoản "ảnh `Indexed` giữ nguyên" phải được thực thi bằng **allowlist họ colorspace đọc từ PDF dict trước khi giải mã ảnh** — guard dựa trên colorspace của ảnh đã giải mã KHÔNG bao giờ nhìn thấy `Indexed` (đo thật: 2 ảnh Indexed lọt qua, xem `docs/Architecture.md` mục "US-16 v2 — Final Decision" W1). Khi re-encode **không được ghi đè `/ColorSpace`** — giữ nguyên ICC profile gốc (ghi đè ICCBased→DeviceCMYK gây lệch màu 4.4–7.0/255 trên macOS Preview/Quartz; hai điều khoản này **ràng buộc nhau, phải làm cùng nhau**, xem W2.2). Guard "JPEG ra to hơn bản gốc thì bỏ qua" của BR-IMGCOMP-02 giữ nguyên.
- **Sửa lỗi kèm theo (không phải thay đổi business rule, là sửa lỗi tiềm ẩn của code đang chạy)**: khi ghi đè stream ảnh phải xoá key `/Decode` nếu có — pixel đã được áp dụng `/Decode` một lần lúc giải mã, để lại key sẽ khiến viewer áp lần thứ hai và ảnh thành âm bản. Chưa phát tác trên dữ liệu đã có vì mọi `/Decode` đo được đều là identity.
- **Cập nhật trạng thái 2026-09-08 (Domain Expert, sau phản biện độc lập — chi tiết + số đo tại `docs/Architecture.md` mục "US-16 v2 — Phản biện của Domain Expert")**: câu chữ BR-IMGCOMP-02b/02c **giữ nguyên**, nhưng cần Tech Lead bổ sung 2 ý vào 02c trước khi trình user: (1) ảnh có key `/Mask` (color-key hoặc stencil) cũng **giữ nguyên** — code v1 hiện drop alpha rồi để nguyên `/Mask`; (2) khi re-encode **không ghi đè `/ColorSpace`** (giữ ICC profile gốc) — đo trên macOS Preview/Quartz: ghi ICCBased→DeviceCMYK gây lệch màu trung bình 4.4–7.0/255, MuPDF không phát hiện được (0.00). Ngoài ra điều khoản "ảnh `Indexed` giữ nguyên" của 02c là **đúng nhưng thuật toán V5 hiện tại KHÔNG thực hiện được** (guard theo `Pixmap.colorspace.name` không bao giờ thấy Indexed — chạy thật 2 ảnh Indexed lọt qua) → Tech Lead sửa V5 trước. Trạng thái: vẫn ⏸ chờ user duyệt, **sau khi** Tech Lead sửa 5 điểm ở mục X9 của phản biện.
- **Chốt thiết kế 2026-09-08 (Tech Lead, `docs/Architecture.md` mục "US-16 v2 — Final Decision sau phản biện Domain Expert")**: đã sửa đủ 5 điểm X9 (chấp nhận toàn bộ, không bác điểm nào); câu chữ 02c ở trên đã được cập nhật tương ứng. Thiết kế **sẵn sàng trình user (Protocol 2)** với đúng **2 câu hỏi cần user quyết**: **(a)** có duyệt mở rộng phạm vi BR-IMGCOMP-02 → 02b (re-encode cả `/FlateDecode`) hay không; **(b)** `src/postprocess/bilingual_merge.py` chọn (A) để backlog hay (B) sửa kèm (`save(..., garbage=4, deflate=True)`, đo được 86.97 → 7.40 MB, pixel-diff 0.0/255 tuyệt đối, nhưng chạm code path chung của cả 2 engine). Các sửa lỗi tiềm ẩn của code đang chạy (xoá `/Decode`, không ghi đè `/ColorSpace` + allowlist colorspace đi kèm, guard `/Mask`) **không phụ thuộc (a)/(b)** — áp dụng trong mọi kịch bản.

### 4.10. Lịch sử dịch — mở rộng (US-19)
- **BR-HIST-01**: "Thời gian dịch" hiển thị = `completed_at (hoặc mốc kết thúc tương ứng) - created_at`, KHÔNG dùng `started_at` làm mốc bắt đầu (lý do: `started_at` hiện gán sau bước OCR, xem US-19).
- **BR-HIST-02**: Chỉ hiển thị thời gian dịch cho job đã có mốc kết thúc (`completed`/`failed`/`cancelled`/`cost_capped`); job đang chạy không hiển thị con số này.
- **BR-HIST-03**: Action "+ Glossary" bị loại bỏ khỏi tab Lịch sử — mọi thao tác thêm thuật ngữ đi qua tab Glossary (US-17) hoặc khu vực "Chờ duyệt" (US-20).

### 4.11. Gợi ý thuật ngữ mới — "Các từ mới" (US-20)
- **BR-TERM-01**: Bước trích xuất thuật ngữ chạy sau khi job chuyển `status=completed`, không chặn/làm chậm luồng dịch chính.
- **BR-TERM-02**: Danh sách gợi ý PHẢI lọc bỏ mọi từ đã tồn tại trong glossary (case-insensitive, đúng BR-GLOSS-02) trước khi hiển thị cho user.
- **BR-TERM-03**: Mặc định không gọi LLM để sinh bản dịch VI cho từ gợi ý (chi phí = 0). Gợi ý bản dịch chỉ chạy khi user chủ động bấm, và phải hiện rõ đây là hành động phát sinh chi phí.
- **BR-TERM-04**: "Bỏ qua" 1 từ gợi ý chỉ ẩn nó khỏi danh sách Chờ duyệt của CHÍNH job đó — không tạo ra 1 "blacklist" toàn cục chặn từ đó xuất hiện lại ở job khác trong tương lai.

### 4.12. Dịch EPUB (US-22)
- **BR-EPUB-01**: Output v1 là EPUB đã dịch, giữ nguyên cấu trúc chapter/HTML gốc. KHÔNG tự động convert PDF (supersede quyết định gốc ở §2 mục 2 / US-04).
- **BR-EPUB-02**: EPUB PHẢI có ước tính chi phí trước khi chạy (Lớp 2) và cơ chế dừng khi vượt trần giữa chừng (Lớp 3), ngang hàng PDF — không được release ở dạng gọi 1 lần cho cả cuốn không chunk. Đơn vị chunk = chương.
- **BR-EPUB-03**: Không được đi qua `provider.translate()` song song với tool dịch EPUB đã chọn cho cùng nội dung (double-translation) — áp dụng nguyên tắc Architecture.md §6.6.2 R1 đã dùng cho PDF.
- **BR-EPUB-04**: Contract CLI/API của tool dịch EPUB bên thứ 3 PHẢI được verify theo Protocol 5 R5-01 (nguồn xác thực trực tiếp) trước khi Tech Lead viết Architecture.md §6.7 chính thức — không kế thừa nguyên trạng bản phác thảo cũ. *(Đã đóng — xem Architecture.md §6.20.2, dẫn tới quyết định chọn hướng `ebooklib` + Translation Engine nội bộ thay vì `bilingual_book_maker`.)*
- **BR-EPUB-05** *(mới, đề xuất bởi Tech Lead 2026-09-08, PM chấp nhận)*: Job EPUB bắt buộc phải fail rõ ràng (không báo "completed") nếu sau khi ghép, file output mất chương hoặc không có nội dung tiếng Việt thật — bản EPUB tương ứng của BR-OCR-03 (đã áp dụng cho PDF scan). Không được để lọt silent failure.
- **BR-EPUB-06** *(mới, 2026-09-08, theo yêu cầu user — dùng chung với BR-PARSE-06)*: Số mũ, chỉ số dưới, phân số trong nội dung gốc (công thức bánh, hoá học, toán học...) PHẢI giữ đúng ký hiệu qua bước dịch, không được đơn giản hoá gây hiểu lầm. Phát hiện bởi Domain Expert khi phản biện thiết kế: rule bóc `<sup>`/`<sub>` ban đầu làm "⅓ cup" thành "/3 cup" — đã sửa, xem Architecture.md §6.21 + §6.20.12 (X1).

---

## 5. Pipeline xử lý theo loại input

```
┌─────────────────────────────────────────────────────────────────┐
│                        WEB UI (Upload + Config)                 │
│  • Upload files (drag & drop / batch)                           │
│  • Chọn model (Claude / OpenAI / DeepL / Ollama)                │
│  • Chọn glossary (global / project)                             │
│  • Chọn output mode (đơn ngữ VI / song ngữ VI-EN)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ File Router  │ ← Auto-detect loại file
                    └──┬───┬───┬──┘
                       │   │   │
          ┌────────────┘   │   └────────────┐
          ▼                ▼                 ▼
    ┌───────────┐   ┌───────────┐   ┌──────────────┐
    │PDF born-  │   │ PDF scan  │   │    EPUB      │
    │digital    │   │           │   │              │
    └─────┬─────┘   └─────┬─────┘   └──────┬───────┘
          │               │                 │
          │         ┌─────▼─────┐    ┌──────▼───────┐
          │         │  MinerU   │    │ EPUB Parser  │
          │         │  (OCR)    │    │ → Markdown   │
          │         └─────┬─────┘    └──────┬───────┘
          │               │                 │
          ▼               ▼                 ▼
    ┌─────────────────────────────────────────────┐
    │           Chunking Engine                    │
    │  (chia theo chapter/section/page range)      │
    └──────────────────┬──────────────────────────┘
                       │
                       ▼
    ┌─────────────────────────────────────────────┐
    │         Translation Engine                   │
    │  • Inject glossary vào prompt                │
    │  • Inject unit conversion rules              │
    │  • Gọi LLM (Claude/OpenAI/DeepL/Ollama)     │
    │  • Dịch súc tích (target ≤ 130% EN)          │
    └──────────────────┬──────────────────────────┘
                       │
                       ▼
    ┌─────────────────────────────────────────────┐
    │          Rendering Engine                    │
    │  • pdf2zh: overlay text VI lên layout gốc   │
    │  • Auto-shrink font nếu tràn                │
    │  • Embed Noto font (Vietnamese full)         │
    │  • Merge chunks → 1 file hoàn chỉnh         │
    └──────────────────┬──────────────────────────┘
                       │
                ┌──────▼──────┐
                │ Output Mode │
                └──┬───────┬──┘
                   │       │
         ┌─────────┘       └─────────┐
         ▼                           ▼
  ┌──────────────┐          ┌────────────────┐
  │ PDF đơn ngữ  │          │ PDF song ngữ   │
  │ (chỉ VI)     │          │ (trang trái VI  │
  │              │          │  trang phải EN) │
  └──────────────┘          └────────────────┘
```

---

## 6. Edge Cases & Risks

### 6.1. Edge Cases

| # | Case | Xử lý |
|---|------|-------|
| EC-01 | PDF born-digital có trang bị flatten (bìa, quảng cáo) | Hybrid: OCR riêng trang đó, pipeline born-digital cho trang còn lại |
| EC-02 | Bảng công thức nhiều cột, merge cell | Giữ cấu trúc bảng, chỉ dịch text trong cell |
| EC-03 | Text overlay trên ảnh (annotation) | Không dịch, flag cho user biết |
| EC-04 | Font gốc decorative không có Vietnamese glyphs | Thay font tương tự có Vietnamese, log thay đổi |
| EC-05 | EPUB có DRM | Reject, thông báo cần gỡ DRM trước |
| EC-06 | Cùng term EN dịch khác theo ngữ cảnh ("fold") | Glossary hỗ trợ context hint, LLM dùng context xung quanh |
| EC-07 | PDF scan chất lượng thấp (mờ, nghiêng) | OCR + confidence score, cảnh báo nếu < 80% |
| EC-08 | File > 500 trang | Tăng chunk, cảnh báo thời gian + chi phí |
| EC-09 | Mixed language (EN + Pháp/Ý/Nhật) | Dịch phần EN, giữ nguyên ngôn ngữ khác trừ khi glossary map |
| EC-10 | Rate limit khi batch lớn | Token bucket rate limiter + queue + estimated wait time |
| EC-11 | Unit conversion sai context | Chỉ convert trong recipe block, không trong prose |
| EC-12 | Footnote/cross-reference | Giữ nguyên số trang reference (layout không đổi) |

### 6.2. Risks

| # | Risk | Mức | Mitigation |
|---|------|-----|------------|
| R-01 | Chi phí API cao cho file lớn | Cao | Hiển thị estimated cost trước dịch, cache translation, hỗ trợ model rẻ hơn/local |
| R-02 | pdf2zh layout vỡ với tài liệu phức tạp | TB | Fallback text-only export, tuỳ chọn layout preservation level |
| R-03 | OCR accuracy thấp cho scan cũ | TB | Confidence score + cảnh báo + cho user review OCR trước dịch |
| R-04 | Chất lượng dịch thuật ngữ chuyên ngành | Cao | Glossary là tuyến phòng thủ chính + system prompt tuỳ chỉnh |
| R-05 | Dependency tool bên thứ 3 | TB | Pin version, integration test, fallback plan |

---

## 7. Cấu hình máy & Yêu cầu hệ thống

### 7.1. Máy hiện tại (đáp ứng tốt)
- Apple M1 Pro, 10 cores, 16-core GPU
- 32GB RAM
- 381GB free disk
- macOS 26.5

### 7.2. Cần cài thêm
- Docker Desktop for Mac (Apple Silicon)
- Python 3.11+ (qua pyenv hoặc uv)
- uv (package manager)
- Homebrew (optional, hỗ trợ cài tools)

### 7.3. Yêu cầu tối thiểu cho pipeline
- RAM: 16GB+ (MinerU OCR cần ~4-8GB, pdf2zh cần ~2-4GB)
- Disk: 10GB+ cho Docker images + models
- Internet: cần cho API calls (Claude/OpenAI/DeepL), không cần cho Ollama

---

## 8. Phạm vi version 1.0

### Trong scope (v1.0)
- [ ] Pipeline dịch PDF born-digital (pdf2zh + LLM)
- [ ] Pipeline dịch EPUB (parse → dịch → convert PDF)
- [ ] Pipeline OCR cho PDF scan (MinerU → dịch)
- [ ] Glossary management (web UI + Excel import/export)
- [ ] Batch processing với failure isolation
- [ ] Auto-chunking (page range based)
- [ ] Multi-model support (Claude, OpenAI, Gemini, DeepSeek, DeepL, Ollama)
- [ ] Output đơn ngữ VI
- [ ] Output song ngữ (trang trái VI, trang phải EN)
- [ ] Auto-convert imperial → metric
- [ ] Progress tracking dashboard
- [ ] Translation history + cache
- [ ] Docker deployment
- [ ] Auto font-shrink cho text overflow

### Đợt mới — lên kế hoạch 2026-09-08 (chưa code, đang chờ duyệt PRD)
> Project đã release tới v1.2.7 (xem `project_state.json`), khung "v1.0/v1.1" dưới đây giữ nguyên
> vì lý do lịch sử — đợt việc này KHÔNG chờ 1 version mới cụ thể, chỉ là batch tính năng tiếp theo.
> **Không bắt đầu implement (Dev) cho tới khi user xác nhận đã xong fix lỗi nén ảnh đang chạy
> song song ở session khác, VÀ user duyệt PRD này (Human Checkpoint 1, Protocol 2).**

- [ ] US-15 Markdown parse-only — kích hoạt lại từ trạng thái hoãn, xác nhận đúng là bản gốc chưa dịch
- [ ] US-17 Thêm từ mới trong tab Glossary
- [ ] US-18 Search trong Glossary
- [ ] US-19 Lịch sử: thời gian dịch + số trang, bỏ action Glossary trùng lặp
- [ ] US-20 "Các từ mới" — gợi ý thuật ngữ chờ duyệt trong tab Glossary
- [ ] US-21 Hiển thị phiên bản BB-Translation
- [ ] US-22 Dịch EPUB (hoàn thiện pipeline) — **rủi ro/độ phức tạp cao nhất trong đợt này**, vướng Protocol 5 R5-01 (chưa verify contract `bilingual_book_maker`) và cần thiết kế cost-safety mới (chunk theo chương)

### Ngoài scope (v2.0+)
- Multi-user + authentication
- Cloud deployment (VPS)
- Translation memory (sentence-level reuse)
- Glossary version control (undo/redo)
- User edit/review bản dịch trước xuất
- PDF annotation/highlight differences
- Mobile responsive UI
- Webhook/email notification

---

## 9. Backlog — đề xuất chưa triển khai (ghi nhận 2026-09-06)

User liệt kê 8 mục dưới đây để **ghi nhớ, chưa yêu cầu làm ngay, không xếp theo thứ tự ưu
tiên**. PM dịch sang dev language kèm bản gốc để đối chiếu; mỗi mục cần BA/Tech Lead làm rõ
thêm trước khi lên kế hoạch implement.

| # | User nói (nguyên văn) | Dev language (PM tóm tắt) | Ghi chú |
|---|---|---|---|
| 1 | Nén ảnh lại sau khi ghép | **→ ĐÃ CHỐT thành US-16 + §4.9 (BR-IMGCOMP-01..04), 2026-09-06** — chỉ áp dụng engine babeldoc, quality cố định 85, dedupe có điều kiện (cần spike ≥20% mới implement). Xem chi tiết ở §3/§4.9. |
| 2 | Trong tab Glossary bổ sung nút "thêm từ mới" | **→ ĐÃ CHỐT thành US-17, 2026-09-08.** |
| 3 | Bổ sung tính năng search trong Glossary | **→ ĐÃ CHỐT thành US-18, 2026-09-08.** |
| 4 | Trong tab Lịch sử, bổ sung: thời gian dịch, số trang, xóa mục | **→ ĐÃ CHỐT thành US-19, 2026-09-08.** "Xóa mục" xác nhận nghĩa là bỏ action "+ Glossary" khỏi tab Lịch sử (chức năng chuyển hẳn sang tab Glossary qua US-17) — KHÔNG phải xoá job (action đó đã có sẵn từ trước, `history.js:80-89`). |
| 5 | Thêm mục "Các từ mới" — thuật ngữ chuyên môn rút ra từ tài liệu vừa dịch, sẵn sàng để thêm vào glossary hiện tại | **→ ĐÃ CHỐT thành US-20, 2026-09-08.** Đặt trong tab Glossary, khu vực "Chờ duyệt", lọc trùng với glossary hiện có. Mặc định miễn phí (chỉ liệt kê EN), có nút riêng "Gợi ý bản dịch" tốn phí khi bấm. Cơ chế trích xuất cụ thể (rule-based hay LLM-based) còn để ngỏ cho Tech Lead. |
| 6 | Hiện phiên bản của BB-Translation | **→ ĐÃ CHỐT thành US-21, 2026-09-08.** Backend `GET /api/version` xác nhận đã có sẵn (`src/api/main.py:110`) — chỉ còn thiếu UI hiển thị. |
| 7 | Dịch EPUB | **→ ĐÃ CHỐT thành US-22, 2026-09-08.** Rủi ro/độ phức tạp cao nhất đợt này — output đổi thành EPUB-only (không tự convert PDF), cần cost-safety chunk theo chương, và vướng gap Protocol 5 R5-01 (contract `bilingual_book_maker` chưa verify) phải đóng trước khi Tech Lead viết Architecture.md §6.7. |
| 8 | Convert định dạng Markdown, giữ nguyên vị trí | **→ ĐÃ CHỐT: kích hoạt lại US-15 nguyên trạng, 2026-09-08.** User xác nhận trực tiếp: đây là Markdown của bản GỐC chưa dịch (không phải bản đã dịch) — đúng định nghĩa cũ đã thiết kế ở Architecture.md §6.8, không cần thiết kế lại. |

*Tất cả 7 mục trên đã qua PM tóm tắt + BA phân tích (`docs/ba-analysis.md` mục 6) + user
trả lời clarifying questions trực tiếp (2026-09-08). Đã lên PRD (US-15, US-17→US-22) ở trên,
đang chờ Human Checkpoint 1 (Protocol 2) trước khi giao Tech Lead viết Architecture.md. Dev
KHÔNG được bắt đầu code cho tới khi (a) PRD này được duyệt VÀ (b) user xác nhận công việc fix
lỗi nén ảnh đang chạy song song ở session khác đã hoàn tất.*

---

*Document version: 1.2 (2026-09-08 — Human Checkpoint 1 [PRD] đã qua; Architecture.md §6.15-§6.20 đã xong (Tech Lead), Human Checkpoint 2 [thiết kế] đã qua với 2 quyết định chốt: migration script giữ dữ liệu thật, bilingual mặc định cho EPUB)*
*Author: PM (tổng hợp từ BA analysis + Tech Lead architecture) + user clarifying answers 2026-09-08*
*Status: PRD + Architecture đã duyệt. Dev VẪN CHƯA bắt đầu code — chờ user xác nhận fix lỗi nén ảnh (session song song, `src/postprocess/image_compress.py`/`bilingual_merge.py` đang có thay đổi chưa commit) đã hoàn tất.*
