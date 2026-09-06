# PRD — BB-Translation

> Pipeline dịch tài liệu ngành bánh (EN → VI), giữ nguyên layout gốc
> Version: 1.0 | Ngày: 2026-09-03 | Phase: Planning

---

## 1. Tổng quan

### 1.1. Bản user
Tôi cần một công cụ dịch sách/tạp chí ngành bánh (200-500 trang) từ tiếng Anh sang tiếng Việt. File dịch phải giữ nguyên layout gốc, tiếng Việt hiển thị đúng font không lệch dòng. Có danh sách thuật ngữ chuyên ngành (glossary) import từ Excel, sửa trên web. Chạy batch nhiều file, tự chia nhỏ file lớn.

### 1.2. Bản dev (PM translation)
Xây dựng document-translation pipeline xử lý PDF/EPUB 200-500 trang chứa layout phức tạp (bảng baker's percentage, công thức, ảnh kỹ thuật). Pipeline phải:
- Giữ nguyên spatial layout (vị trí text/ảnh/bảng) qua overlay rendering
- Đảm bảo Vietnamese Unicode glyph coverage đầy đủ trên embedded font
- Xử lý text-length expansion (VI dài hơn EN ~20-40%) bằng concise translation prompt + auto font-shrink
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
- **Given** EPUB → **Then** output PDF đã dịch, giữ layout ổn định
- **Given** PDF scan → **Then** tự động OCR (MinerU) trước, rồi dịch

**Known limitation (nhánh PDF scan, xem Architecture.md 6.10)**: pdf2zh không tự OCR được và MinerU không xuất PDF có sẵn text layer — pipeline phải tự dựng "searchable PDF" làm cầu nối: tô nền trắng phẳng đè lên vùng chữ tiếng Anh gốc (dựa theo bounding box MinerU nhận diện), sau đó ghi text đã dịch lên đúng vị trí. Ảnh/bảng/hình minh hoạ trong trang scan giữ nguyên pixel gốc, KHÔNG bị ảnh hưởng — chỉ vùng chữ thuần bị thay nền phẳng, mất texture/màu nền gốc của giấy tại đúng vị trí chữ. Đây là đánh đổi chất lượng đã được user chấp nhận sau khi xác nhận 2 hướng khác (pdf2zh tự OCR / MinerU tự xuất PDF có text layer) đều không khả thi qua thực nghiệm.

Job PDF scan bắt buộc phải fail rõ ràng (không báo "completed") nếu sau khi ghép, file output có 0 ký tự đọc được — không được để lọt silent failure như Bug #5 (xem BR-OCR-03).

### US-05: Xử lý text tràn
**As a** người dịch sách, **I want** hệ thống tự co/nén font khi text VI tràn, **so that** layout không vỡ.

**Acceptance Criteria:**
- Bước 1: giảm font size tối đa 20%
- Bước 2: horizontal scaling (condensed) tối đa 85%
- Bước 3: nếu vẫn tràn → flag cho user review (không cắt text)

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

### US-15: Xuất Markdown parse-only (không dịch) — ⚠️ HOÃN sang v1.1
**As a** người dịch sách, **I want** xuất file gốc sang Markdown giữ nguyên layout, bảng, công thức mà KHÔNG qua bước dịch, **so that** tôi có thể tự kiểm tra chất lượng parse trước khi tốn chi phí dịch, hoặc dùng Markdown này cho mục đích khác (lưu trữ, đưa vào hệ tri thức, tự dịch thủ công).

**Known limitation (v1.0)**: API chấp nhận `job_type=parse_only` nhưng `JobOrchestrator` chưa có nhánh xử lý riêng (chỉ mới lắp luồng `translate` qua pdf2zh ở Increment 4-5) — mọi job `parse_only` hiện tại fail ngay với thông báo rõ ràng, không giả vờ thành công. Cần 1 nhánh `MinerU-only` riêng trong `JobOrchestrator` (đọc Architecture.md section 6.8) để hoàn thiện. Quyết định: hoãn sang v1.1, không chặn release v1.0 vì đây không phải tính năng lõi (dịch thuật) mà là tiện ích phụ.

**Acceptance Criteria:**
- **Given** user upload file (PDF born-digital, PDF scan, hoặc EPUB) và chọn chế độ "Chỉ xuất Markdown (không dịch)" → **Then** hệ thống chạy MinerU parse (OCR nếu cần) và xuất file `.md` + thư mục ảnh liên quan, KHÔNG gọi bất kỳ LLM translation API nào
- **Given** file gốc có bảng công thức nhiều cột → **Then** Markdown output giữ nguyên cấu trúc bảng (Markdown table syntax), số liệu/đơn vị giữ nguyên y hệt bản gốc, không convert đơn vị
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
- **BR-FONT-02**: Auto-shrink 3 bước: giảm font 20% → condensed 85% → flag user review
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

### 4.9. Image Compression (US-16)
- **BR-IMGCOMP-01**: Chỉ áp dụng cho job dùng engine `babeldoc` (`settings.pdf_translate_engine == "babeldoc"`). Job dùng `pdf2zh` không đổi hành vi.
- **BR-IMGCOMP-02**: Chạy sau `merge_chunk_pdfs()`, trước khi file được coi là `job.output_path` cuối cùng. Chỉ re-encode ảnh đang ở dạng raw/uncompressed (`Filter: null`); ảnh đã là JPEG (`DCTDecode`) giữ nguyên, không nén chồng lần 2.
- **BR-IMGCOMP-03**: Mức nén JPEG cố định quality=85, không cấu hình qua `.env` hay UI.
- **BR-IMGCOMP-04**: Dedupe ảnh trùng lặp (nhiều xref cùng nội dung ảnh) là tính năng có điều kiện — chỉ implement chính thức nếu spike đo trên dữ liệu thật cho thấy mức giảm dung lượng thêm ≥ 20% so với chỉ nén JPEG. Kết quả spike (đạt hay không đạt ngưỡng) phải được ghi vào Architecture.md kèm số liệu đo, không được quyết định bằng suy đoán (theo tinh thần Protocol 5 R5-02 của project — dù PyMuPDF là thư viện nội bộ không thuộc phạm vi Protocol 5 bắt buộc, nguyên tắc "đo thật trước khi quyết định" vẫn nên áp dụng vì đây là ngưỡng số liệu cụ thể user đặt ra).

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

### Hoãn sang v1.1
- Markdown parse-only mode (US-15) — API đã có field `job_type=parse_only`, nhưng `JobOrchestrator` chưa có nhánh MinerU-only để xử lý thật. Xem known limitation ghi trong US-15.

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
| 2 | Trong tab Glossary bổ sung nút "thêm từ mới" | Thêm nút "Add new term" trên Glossary UI (`web/index.html` hoặc trang glossary riêng), mở form/modal tạo 1 glossary entry mới (source term + target term + note), gọi API tạo (`src/api/routes/glossary.py`). |
| 3 | Bổ sung tính năng search trong Glossary | Thêm ô search/filter trên Glossary UI, lọc theo source hoặc target term (client-side filter hoặc query param cho API list). |
| 4 | Trong tab Lịch sử, bổ sung: thời gian dịch, số trang, xóa mục | 3 việc riêng trên trang History (`web/history.html`/`web/js/history.js`): (a) hiển thị thời gian dịch (`started_at`→`completed_at` hoặc duration tính từ đó), (b) hiển thị `total_pages` của job, (c) thêm action xoá 1 job khỏi lịch sử (cần API DELETE job + xác nhận trước khi xoá, vì đây là destructive action). |
| 5 | Thêm mục "Các từ mới" — thuật ngữ chuyên môn rút ra từ tài liệu vừa dịch, sẵn sàng để thêm vào glossary hiện tại | Tính năng mới, cần thiết kế riêng: sau khi job dịch xong, chạy 1 bước trích xuất thuật ngữ chuyên ngành (LLM-based term extraction) từ nội dung đã dịch, hiển thị danh sách candidate terms trên UI kèm action "Add to glossary" cho từng từ. Cần BA làm rõ: tiêu chí "thuật ngữ chuyên môn" là gì, extract từ bước nào trong pipeline (trước/sau dịch), cost/latency phát sinh. |
| 6 | Hiện phiên bản của BB-Translation | Hiển thị version string (vd đọc từ `pyproject.toml` hoặc 1 hằng số `APP_VERSION`) ở đâu đó trên UI (footer hoặc header) — lưu ý: `tests/integration/test_version_and_upload_timestamp.py` đã tồn tại (untracked) trong working tree, có thể đã có code liên quan dở dang, cần Dev kiểm tra lại trước khi làm mới. |
| 7 | Dịch EPUB | Đã có trong scope v1.0 (mục "Pipeline dịch EPUB" ở §8) nhưng **CHƯA implement thật** — job thật gần nhất với `.epub` bị fail với lỗi `"EPUB pipeline (bilingual_book_maker) chua duoc implement trong increment nay"` (xem job `971b7c0a-45e4-4f3f-b079-4d042ab41624`, 2026-09-05). Đây là hoàn thiện tính năng đã cam kết, không phải feature mới. |
| 8 | Convert định dạng Markdown, giữ nguyên vị trí | Liên quan US-15 (§3, "Xuất Markdown parse-only") — đã **HOÃN sang v1.1** theo quyết định trước đó. "Giữ nguyên vị trí" cần BA làm rõ nghĩa là gì trong context Markdown (Markdown không có khái niệm vị trí/layout như PDF) — có thể user đang muốn giữ nguyên cấu trúc heading/section thay vì layout toạ độ. |

*Không mục nào ở trên đã bắt đầu implement. Khi user yêu cầu làm 1 mục cụ thể, PM cần đưa qua
BA (nếu cần làm rõ nghiệp vụ) rồi Tech Lead trước khi Dev bắt tay vào, theo Protocol 1/2 chuẩn.*

---

*Document version: 1.0*
*Author: PM (tổng hợp từ BA analysis)*
*Status: Draft — Pending user review (Human Checkpoint 1)*
