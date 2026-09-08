# Phân tích nghiệp vụ - BB-Translation

> Dự án: Pipeline dịch tài liệu ngành bánh (EN → VI), giữ nguyên layout gốc
> Ngày: 2026-09-03
> Vai trò: Business Analyst

---

## 1. User Stories

### US-01: Upload file tài liệu
**As a** người dịch sách bánh,
**I want** upload file PDF hoặc EPUB lên hệ thống qua giao diện web,
**so that** hệ thống tự động nhận diện loại file và bắt đầu xử lý mà tôi không cần thao tác kỹ thuật.

### US-02: Batch processing nhiều file
**As a** người dịch sách bánh,
**I want** upload và dịch nhiều file cùng lúc (batch),
**so that** tôi tiết kiệm thời gian khi có nhiều tài liệu cần dịch trong cùng dự án.

### US-03: Quản lý glossary chuyên ngành
**As a** người dịch sách bánh,
**I want** import glossary từ file Excel (cột EN → cột VI), chỉnh sửa trực tiếp trên web UI, và export lại,
**so that** các thuật ngữ chuyên ngành bánh được dịch nhất quán xuyên suốt mọi tài liệu.

### US-04: Dịch tự động giữ nguyên layout
**As a** người dịch sách bánh,
**I want** hệ thống dịch nội dung từ tiếng Anh sang tiếng Việt mà giữ nguyên layout, hình ảnh, bảng biểu của file gốc,
**so that** bản dịch có thể dùng ngay mà không cần dàn trang lại thủ công.

### US-05: Xử lý text tràn bounding box
**As a** người dịch sách bánh,
**I want** hệ thống tự động co/nén font hoặc điều chỉnh text khi bản dịch tiếng Việt dài hơn bản gốc,
**so that** text không bị tràn ra ngoài vùng hiển thị gốc và layout vẫn đẹp.

### US-06: Auto-chunking file lớn
**As a** người dịch sách bánh,
**I want** hệ thống tự động chia nhỏ file lớn (200-500 trang) thành các chunk hợp lý,
**so that** quá trình dịch không bị lỗi do giới hạn API token, memory, hoặc file size.

### US-07: Theo dõi tiến trình dịch
**As a** người dịch sách bánh,
**I want** xem tiến trình dịch realtime (% hoàn thành, chunk đang xử lý, thời gian ước tính còn lại),
**so that** tôi biết khi nào file sẽ dịch xong và có thể phát hiện sớm nếu quá trình bị treo.

### US-08: Xử lý lỗi và retry
**As a** người dịch sách bánh,
**I want** hệ thống tự động retry khi gặp lỗi tạm thời (API timeout, rate limit) và thông báo rõ ràng khi lỗi không thể tự khắc phục,
**so that** tôi không mất kết quả dịch đã hoàn thành và biết phải làm gì khi có sự cố.

### US-09: Download kết quả dịch
**As a** người dịch sách bánh,
**I want** download file đã dịch ở định dạng PDF (giữ layout) hoặc file song ngữ (EN-VI cạnh nhau),
**so that** tôi có thể đối chiếu bản dịch với bản gốc và gửi cho khách hàng/nhà xuất bản.

### US-10: Giữ nguyên thuật ngữ gốc (không dịch)
**As a** người dịch sách bánh,
**I want** đánh dấu một số thuật ngữ trong glossary là "giữ nguyên tiếng Anh" (ví dụ: ganache, fondant, meringue),
**so that** các thuật ngữ quốc tế phổ biến trong ngành bánh không bị dịch sai hoặc dịch ngô nghê.

### US-11: Xử lý PDF scan (OCR)
**As a** người dịch sách bánh,
**I want** hệ thống nhận diện và xử lý PDF scan bằng OCR trước khi dịch,
**so that** tôi vẫn dịch được tài liệu scan cũ mà không cần chuyển đổi thủ công.

### US-12: Lịch sử dịch và tái sử dụng
**As a** người dịch sách bánh,
**I want** xem lại lịch sử các file đã dịch và tải lại kết quả,
**so that** tôi không phải dịch lại file đã xử lý trước đó và tiết kiệm chi phí API.

---

## 2. Business Rules

### 2.1. Quy tắc xử lý theo loại input

| Loại file | Công cụ xử lý | Pipeline |
|-----------|---------------|----------|
| PDF born-digital | pdf2zh (PDFMathTranslate) | Extract text trực tiếp → dịch → overlay text mới lên layout gốc |
| PDF scan | MinerU (OCR) → pdf2zh | OCR để extract text → tạo text layer → dịch → rebuild PDF |
| EPUB | bilingual_book_maker | Parse EPUB structure → dịch từng chapter → rebuild EPUB → (tuỳ chọn) convert sang PDF |

**BR-INPUT-01**: Hệ thống phải tự động detect loại file dựa trên extension (.pdf, .epub) và nội dung (PDF born-digital vs scan).

**BR-INPUT-02**: Với PDF, hệ thống kiểm tra text layer. Nếu extract được text > 90% số trang → born-digital. Nếu < 90% → coi là scan, chuyển sang pipeline OCR.

**BR-INPUT-03**: File upload tối đa 500MB. File > 500MB bị reject với thông báo lỗi rõ ràng.

**BR-INPUT-04**: Chỉ chấp nhận file .pdf và .epub. Các định dạng khác bị reject ngay khi upload.

### 2.2. Quy tắc Glossary

**BR-GLOSS-01 (Ưu tiên glossary)**: Khi dịch, hệ thống **PHẢI** kiểm tra glossary trước. Nếu thuật ngữ có trong glossary → dùng bản dịch glossary. Nếu không → dịch tự do bằng Claude API.

**BR-GLOSS-02 (Case-sensitivity)**: Glossary matching mặc định là **case-insensitive** cho tiếng Anh. Ví dụ: "Ganache", "ganache", "GANACHE" đều match cùng entry.

**BR-GLOSS-03 (Conflict resolution)**: Nếu glossary có nhiều entry trùng term gốc (EN), lấy entry được cập nhật gần nhất (last-updated wins).

**BR-GLOSS-04 (Giữ nguyên EN)**: Entry glossary có cột target = "(keep)" hoặc để trống cột VI → giữ nguyên thuật ngữ tiếng Anh trong bản dịch.

**BR-GLOSS-05 (Import/Export format)**: File Excel glossary phải có tối thiểu 2 cột: cột đầu tiên = term EN, cột thứ hai = term VI (hoặc "(keep)"). Cột thứ 3 (tuỳ chọn) = ghi chú/ngữ cảnh.

**BR-GLOSS-06 (Glossary scope)**: Glossary có thể ở 2 cấp:
- **Global glossary**: áp dụng cho mọi file dịch.
- **Project glossary**: áp dụng cho một batch/nhóm file cụ thể. Project glossary override global glossary khi có conflict.

### 2.3. Quy tắc Chunking

**BR-CHUNK-01 (Ngưỡng kích thước)**: File PDF > 50 trang hoặc > 20MB bắt buộc phải chunk. File nhỏ hơn xử lý nguyên khối.

**BR-CHUNK-02 (Đơn vị chunk)**: Ưu tiên chia theo thứ tự:
1. Theo chapter/section (dựa vào heading structure hoặc bookmarks của PDF)
2. Nếu không detect được chapter → chia theo khoảng 30-50 trang/chunk
3. Mỗi chunk không vượt quá 100.000 tokens (ước tính) để nằm trong API limit

**BR-CHUNK-03 (Context overlap)**: Mỗi chunk phải kèm 1-2 trang overlap với chunk trước và chunk sau để đảm bảo context dịch liên tục. Phần overlap chỉ dùng làm context, không dịch lại.

**BR-CHUNK-04 (Merge)**: Sau khi dịch xong tất cả chunk, hệ thống tự động merge lại thành 1 file output hoàn chỉnh, đảm bảo không trùng lặp nội dung ở vùng overlap.

**BR-CHUNK-05 (Resumable)**: Nếu quá trình dịch bị gián đoạn (lỗi, user cancel), hệ thống lưu trạng thái chunk đã dịch xong. Khi retry, chỉ dịch lại từ chunk bị lỗi trở đi.

### 2.4. Quy tắc Batch Processing

**BR-BATCH-01 (Failure isolation)**: Mỗi file trong batch chạy độc lập. 1 file lỗi KHÔNG được ảnh hưởng các file khác trong cùng batch.

**BR-BATCH-02 (Retry policy)**:
- Lỗi tạm thời (API timeout, rate limit 429, network error): retry tối đa 3 lần, mỗi lần cách nhau exponential backoff (2s → 4s → 8s).
- Lỗi vĩnh viễn (file corrupt, format không hỗ trợ, API authentication error): không retry, đánh dấu file là "failed" với lý do cụ thể.

**BR-BATCH-03 (Concurrency)**: Xử lý song song tối đa 3 file cùng lúc (để không vượt Claude API rate limit). Có thể config lại con số này.

**BR-BATCH-04 (Priority)**: Trong batch, file nhỏ hơn xử lý trước (shortest job first) để user có kết quả sớm nhất.

### 2.5. Quy tắc Font và Text Overflow

**BR-FONT-01 (Vietnamese glyph coverage)**: Font dùng cho bản dịch phải hỗ trợ đầy đủ Vietnamese Unicode (các ký tự có dấu: ă, â, ê, ô, ơ, ư, đ và tất cả tổ hợp thanh điệu). Fallback font mặc định: Noto Sans (hỗ trợ Vietnamese đầy đủ).

**BR-FONT-02 (Auto-shrink threshold)**: Khi text dịch vượt bounding box gốc:
1. Bước 1: Giảm font size tối đa 20% so với font gốc.
2. Bước 2: Nếu vẫn tràn sau khi giảm 20%, áp dụng horizontal scaling (condensed) tối đa 85%.
3. Bước 3: Nếu vẫn tràn, flag text block đó để user review thủ công (không cắt text).

**BR-FONT-03 (Chiến lược dịch ngắn gọn)**: System prompt cho Claude API phải yêu cầu dịch súc tích, ưu tiên câu ngắn. Target: bản dịch VI không dài hơn 130% bản gốc EN.

---

## 3. Edge Cases & Risks

### 3.1. Edge Cases

| # | Edge Case | Mô tả | Xử lý đề xuất |
|---|-----------|-------|----------------|
| EC-01 | PDF có text dạng hình ảnh (flattened) | PDF born-digital nhưng một số trang chứa text đã bị flatten thành image (ví dụ: trang bìa, trang quảng cáo) | Detect trang không extract được text → chạy OCR riêng cho trang đó, giữ nguyên pipeline born-digital cho trang còn lại (hybrid mode) |
| EC-02 | Bảng công thức phức tạp | Bảng nguyên liệu/công thức có layout nhiều cột, merge cell, đơn vị đo lường lẫn lộn (cups, grams, ml) | Giữ nguyên cấu trúc bảng, chỉ dịch text trong cell. Đơn vị đo lường giữ nguyên hoặc convert theo glossary |
| EC-03 | Text trên hình ảnh | Hình minh hoạ bước làm bánh có annotation text overlay trên ảnh | Không dịch text embedded trong image. Flag ảnh có text cho user biết |
| EC-04 | Font gốc không hỗ trợ tiếng Việt | File gốc dùng decorative font (script, handwriting) không có Vietnamese glyphs | Thay bằng font tương tự có Vietnamese support. Log font thay đổi để user kiểm tra |
| EC-05 | File EPUB có DRM | EPUB mua từ store có DRM protection | Reject file, thông báo user cần gỡ DRM trước khi upload (hệ thống không hỗ trợ bypass DRM) |
| EC-06 | Glossary conflict giữa ngữ cảnh | Cùng một term EN nhưng cần dịch khác nhau tuỳ ngữ cảnh. Ví dụ: "fold" = "gập bột" (kỹ thuật trộn) vs "fold" = "gấp" (gấp giấy bọc) | Glossary cho phép thêm trường "context hint". Claude API dùng context xung quanh để chọn bản dịch phù hợp nhất |
| EC-07 | PDF scan chất lượng thấp | Scan cũ, mờ, nghiêng, có vết bẩn → OCR accuracy thấp | Chạy OCR, tính confidence score trung bình. Nếu < 80% → cảnh báo user "chất lượng OCR thấp, kết quả dịch có thể không chính xác" |
| EC-08 | File > 500 trang | Sách chuyên ngành rất dài, vượt quá ngưỡng chunking thông thường | Tăng số chunk, đảm bảo mỗi chunk vẫn trong giới hạn. Cảnh báo user về thời gian xử lý dự kiến và chi phí API |
| EC-09 | Mixed language trong file gốc | Sách bánh có đoạn tiếng Pháp (thuật ngữ bánh Pháp), tiếng Ý (pasta/pizza), tiếng Nhật (wagashi) xen lẫn tiếng Anh | Chỉ dịch phần tiếng Anh. Thuật ngữ ngôn ngữ khác giữ nguyên. Glossary có thể map cả term tiếng Pháp/Ý → tiếng Việt nếu user muốn |
| EC-10 | Rate limit Claude API khi batch lớn | Dịch batch 10+ file x 300 trang mỗi file → hàng nghìn API calls | Implement token bucket rate limiter. Queue system với priority. Hiển thị estimated wait time cho user |
| EC-11 | Duplex page (trang trái-phải mirror layout) | Sách in thường có layout mirror giữa trang chẵn/lẻ (margin trong vs margin ngoài) | Giữ nguyên layout gốc của từng trang. pdf2zh xử lý theo trang nên không ảnh hưởng |
| EC-12 | Footnote và cross-reference | Sách có footnote, endnote, "xem trang X" → sau dịch số trang có thể thay đổi | Giữ nguyên số trang reference gốc vì layout không thay đổi. Dịch nội dung footnote bình thường |

### 3.2. Risks

| # | Risk | Mức độ | Mitigation |
|---|------|--------|------------|
| R-01 | Chi phí Claude API cao cho file lớn | Cao | Hiển thị estimated cost trước khi dịch. Cho phép user set budget limit. Cache translation cho text lặp lại |
| R-02 | pdf2zh không xử lý tốt layout phức tạp | Trung bình | Có fallback: export text-only nếu layout bị vỡ. Cho user chọn "layout preservation level" |
| R-03 | OCR accuracy thấp cho PDF scan cũ | Trung bình | Cho phép user review/edit OCR output trước khi dịch. Hiển thị confidence score |
| R-04 | Chất lượng dịch thuật ngữ chuyên ngành | Cao | Glossary là tuyến phòng thủ chính. Cho user review + feedback loop để cải thiện system prompt |
| R-05 | Dependency vào tool bên thứ 3 (pdf2zh, MinerU) | Trung bình | Pin version cụ thể. Có integration test cho từng tool. Fallback plan nếu tool không maintain nữa |

---

## 4. Acceptance Criteria

### US-01: Upload file tài liệu

**AC-01.1**
- **Given** user ở trang chính của web UI
- **When** user kéo thả hoặc chọn file .pdf/.epub
- **Then** hệ thống upload file, hiển thị tên file + kích thước + loại file đã detect (born-digital/scan/EPUB), và chuyển sang trạng thái "ready to translate"

**AC-01.2**
- **Given** user upload file không phải .pdf hoặc .epub
- **When** file được gửi lên server
- **Then** hệ thống reject file ngay lập tức với thông báo "Chỉ hỗ trợ file PDF và EPUB"

**AC-01.3**
- **Given** user upload file > 500MB
- **When** file được gửi lên server
- **Then** hệ thống reject với thông báo "File vượt quá giới hạn 500MB"

### US-02: Batch processing nhiều file

**AC-02.1**
- **Given** user đã upload 5 file PDF vào batch
- **When** user bấm "Dịch tất cả"
- **Then** hệ thống bắt đầu xử lý song song (tối đa 3 file), hiển thị tiến trình từng file riêng biệt

**AC-02.2**
- **Given** batch đang chạy và file thứ 3 bị lỗi (ví dụ: file corrupt)
- **When** lỗi xảy ra
- **Then** file thứ 3 được đánh dấu "failed" với lý do, các file còn lại tiếp tục chạy bình thường

### US-03: Quản lý glossary chuyên ngành

**AC-03.1**
- **Given** user có file Excel glossary với cột A = EN term, cột B = VI term
- **When** user import file qua web UI
- **Then** hệ thống parse file, hiển thị preview danh sách thuật ngữ, và cho user confirm trước khi lưu

**AC-03.2**
- **Given** glossary đã có entry "ganache" → "(keep)"
- **When** hệ thống dịch đoạn text chứa từ "ganache"
- **Then** từ "ganache" được giữ nguyên tiếng Anh trong bản dịch

**AC-03.3**
- **Given** user đang ở trang glossary management
- **When** user chỉnh sửa bản dịch của term "buttercream" từ "kem bơ" thành "kem phủ bơ"
- **Then** thay đổi được lưu ngay lập tức, các lần dịch sau sẽ dùng bản dịch mới

**AC-03.4**
- **Given** user muốn xuất glossary
- **When** user bấm "Export"
- **Then** hệ thống tải về file Excel có format giống file import (cột EN, cột VI, cột ghi chú)

### US-04: Dịch tự động giữ nguyên layout

**AC-04.1**
- **Given** user upload PDF born-digital 100 trang có hình ảnh, bảng, header/footer
- **When** quá trình dịch hoàn tất
- **Then** file output PDF có cùng số trang, hình ảnh giữ nguyên vị trí, bảng giữ nguyên cấu trúc, header/footer giữ nguyên (hoặc được dịch)

**AC-04.2**
- **Given** user upload EPUB
- **When** quá trình dịch hoàn tất
- **Then** file output là EPUB đã dịch, giữ nguyên chapter structure và formatting

### US-05: Xử lý text tràn bounding box

**AC-05.1**
- **Given** đoạn text EN gốc chiếm 80% bounding box
- **When** bản dịch VI dài hơn 130% bản gốc và tràn bounding box
- **Then** hệ thống tự động giảm font size (tối đa 20%) để text fit trong bounding box

**AC-05.2**
- **Given** text vẫn tràn sau khi giảm font 20%
- **When** áp dụng thêm horizontal scaling 85%
- **Then** text fit trong bounding box mà vẫn đọc được

**AC-05.3**
- **Given** text vẫn tràn sau cả 2 bước trên
- **When** hệ thống không thể auto-fit
- **Then** text block được flag trong report cuối cùng, user biết cần review thủ công

### US-06: Auto-chunking file lớn

**AC-06.1**
- **Given** user upload PDF 300 trang (> 50 trang)
- **When** hệ thống bắt đầu xử lý
- **Then** file được tự động chia thành các chunk (hiển thị số chunk cho user), mỗi chunk 30-50 trang

**AC-06.2**
- **Given** quá trình dịch bị gián đoạn ở chunk thứ 5/10
- **When** user bấm "Retry"
- **Then** hệ thống tiếp tục từ chunk 5, không dịch lại chunk 1-4

### US-07: Theo dõi tiến trình dịch

**AC-07.1**
- **Given** file đang được dịch
- **When** user ở trang dashboard
- **Then** hiển thị: tên file, % hoàn thành, chunk hiện tại / tổng chunk, thời gian đã chạy, thời gian ước tính còn lại

**AC-07.2**
- **Given** quá trình dịch bị treo > 5 phút không có progress
- **When** hệ thống detect timeout
- **Then** tự động retry chunk hiện tại và thông báo user "Chunk X bị timeout, đang retry"

### US-08: Xử lý lỗi và retry

**AC-08.1**
- **Given** Claude API trả về lỗi 429 (rate limit)
- **When** hệ thống nhận lỗi
- **Then** tự động retry sau exponential backoff (2s → 4s → 8s), tối đa 3 lần

**AC-08.2**
- **Given** retry 3 lần đều thất bại
- **When** hết số lần retry
- **Then** đánh dấu chunk/file là "failed", thông báo user với lý do cụ thể, giữ nguyên kết quả chunk đã dịch thành công

### US-09: Download kết quả dịch

**AC-09.1**
- **Given** file dịch hoàn tất thành công
- **When** user bấm "Download"
- **Then** tải về file PDF đã dịch giữ nguyên layout gốc

**AC-09.2**
- **Given** file dịch hoàn tất thành công
- **When** user chọn "Download bản song ngữ"
- **Then** tải về file PDF/EPUB có cả text EN và VI (format tuỳ thuộc tool hỗ trợ)

### US-10: Giữ nguyên thuật ngữ gốc

**AC-10.1**
- **Given** glossary có entry: "fondant" → "(keep)", "meringue" → "(keep)"
- **When** dịch câu "Spread the fondant evenly over the meringue."
- **Then** kết quả: "Trải fondant đều lên meringue." (giữ nguyên 2 thuật ngữ)

### US-11: Xử lý PDF scan

**AC-11.1**
- **Given** user upload PDF scan (không có text layer)
- **When** hệ thống detect đây là scan
- **Then** tự động chạy OCR (MinerU), hiển thị thông báo "Đang OCR...", sau đó chuyển sang pipeline dịch

**AC-11.2**
- **Given** OCR confidence score < 80%
- **When** OCR hoàn tất
- **Then** cảnh báo user "Chất lượng OCR thấp (X%), kết quả dịch có thể không chính xác. Bạn có muốn tiếp tục?"

### US-12: Lịch sử dịch và tái sử dụng

**AC-12.1**
- **Given** user đã dịch 10 file trong tháng qua
- **When** user vào trang "Lịch sử"
- **Then** hiển thị danh sách file đã dịch: tên, ngày dịch, trạng thái, kích thước, nút download

**AC-12.2**
- **Given** user upload lại file đã dịch trước đó (trùng hash)
- **When** hệ thống detect file trùng
- **Then** thông báo "File này đã được dịch vào [ngày]. Bạn muốn dùng kết quả cũ hay dịch lại?"

---

## 5. Cau hoi can clarify

### Uu tien cao (anh huong architecture)

1. **Output format cho EPUB**: Khi dịch EPUB, user muốn output là EPUB (giữ nguyên) hay convert sang PDF? Hay cả hai tuỳ chọn?

2. **Bản song ngữ**: User có cần bản song ngữ (EN-VI) không? Nếu có, format mong muốn là gì? (EN bên trái - VI bên phải? EN trên - VI dưới? Hay highlight text đã dịch?)

3. **Authentication/Multi-user**: Hệ thống chỉ 1 user dùng (cá nhân) hay nhiều người dùng chung? Có cần đăng nhập không?

4. **Claude API key**: User tự cung cấp API key hay hệ thống dùng key chung? (Ảnh hưởng đến cost tracking và rate limit)

5. **Hosting**: Hệ thống chạy local (trên máy user) hay deploy lên server (cloud)? Ảnh hưởng đến file storage, processing power, và concurrent users.

### Uu tien trung binh (anh huong UX)

6. **Đơn vị đo lường**: Khi dịch công thức, có cần tự động convert đơn vị (cups → ml, °F → °C) không? Hay giữ nguyên đơn vị gốc?

7. **Review/Edit trước khi xuất**: User có muốn xem và chỉnh sửa bản dịch trước khi download không? Hay chấp nhận kết quả auto?

8. **Notification**: Khi dịch file lớn mất vài chục phút, user muốn nhận thông báo qua kênh nào? (Web notification? Email?)

### Uu tien thap (nice-to-have)

9. **Translation memory**: Ngoài glossary (thuật ngữ), có cần translation memory (lưu cả câu/đoạn đã dịch) để tái sử dụng cho file khác không?

10. **Version control cho glossary**: Cần undo/redo khi chỉnh glossary không? Hay chỉ cần version hiện tại?

---

*Document version: 1.0*
*Author: BA Agent*
*Status: Draft - Pending user review*

---

## 6. Phan tich 7 tinh nang moi (2026-09-08)

> Bối cảnh: sau release v1.2.7, user đưa 7 nhóm yêu cầu mới. Section này là bước BA
> **trước** khi PM viết PRD và Tech Lead viết Architecture (Protocol 1/2).
> Đánh số tiếp: các section 1-5 ở trên dừng ở US-12; PRD.md hiện dừng ở US-16 → user story
> mới bắt đầu từ **US-17**.
>
> **Quy ước gắn nhãn verify (Protocol 1 mở rộng, CLAUDE.md global)**: mọi claim về code
> trong section này đều kèm `file:line` mà BA đã **đọc trực tiếp**. Claim về hành vi tool
> bên thứ ba mà BA chưa chạy/chưa đọc source được gắn `[CHƯA VERIFY]`.

### 6.0. Nguyên văn yêu cầu user

1. Trong tab Glossary bổ sung nút "thêm từ mới"
2. Bổ sung tính năng search trong Glossary
3. Trong tab Lịch sử, bổ sung: thời gian dịch, số trang, xóa mục glossary trong "lịch sử"
4. Thêm mục "Các từ mới", là các từ mang tính chuyên môn xuất phát từ tài liệu vừa dịch,
   giao diện sẵn sàng để cập nhật vào glossary hiện tại.
5. Hiện phiên bản của BB-Translation
6. Dịch epub
7. Convert định dạng markdown, giữ nguyên vị trí (ưu tiên)

**Tín hiệu ưu tiên**: user chỉ đánh dấu "(ưu tiên)" duy nhất cho mục #7. PM cần xác nhận
đây là ưu tiên **cao nhất trong 7 mục** hay chỉ là "ưu tiên hơn #6".

### 6.1. Đính chính 2 điểm trong brief của PM (BA tự đọc source, không suy đoán)

**Đ-01 — `JobDetail` KHÔNG hề expose `total_pages` / `started_at` / `completed_at`.**
PM viết "các field này đã có trong response API (`JobOut`/`JobListResponse`,
`src/api/routes/jobs.py:87` có `completed_at`)". Sai. `jobs.py:87` là field của
`DuplicateJobInfo` (dùng cho duplicate-detection AC-12.2), không phải của `JobDetail`.
BA đã đọc trọn `JobDetail` (`src/api/routes/jobs.py:119-146`) và `_to_detail()`
(`src/api/routes/jobs.py:216-245`): **không có** `total_pages`, `started_at`,
`completed_at`. Hệ quả: nhóm #3 **không phải việc frontend thuần** như brief giả định —
bắt buộc sửa backend (thêm 3 field vào `JobDetail` + `_to_detail`).

**Đ-02 — Tab Lịch sử ĐÃ CÓ nút xoá job.** PM viết "hiện tab Lịch sử chỉ có nút
'+ Glossary' (thêm), KHÔNG có cách nào xem/xoá". Thực tế `deleteJob()` đã tồn tại
(`web/js/history.js:80-89`) và nút "Xoá" đã render (`web/history.html:62`), làm từ
2026-09-06 theo đúng backlog PRD mục #4(c). Điểm này thay đổi hoàn toàn cách hiểu câu #3
— xem BA-Q1 ở 6.10.

### 6.2. Nhóm #1 — Nút "thêm từ mới" trong tab Glossary

**US-17**: **As a** người dịch sách bánh, **I want** thêm 1 thuật ngữ mới trực tiếp từ tab
Glossary, **so that** tôi không phải tạo file Excel hay đi vòng qua tab Lịch sử chỉ để thêm
1 từ.

**Yêu cầu ẩn phát hiện được**:
- **YA-1.1 (nguy cơ mất dữ liệu — quan trọng nhất)**: `POST /api/glossary` không tạo entry
  mới mà gọi `GlossaryManager.bulk_import()` (`src/api/routes/glossary.py:130-134`), tức là
  chạy luật **BR-GLOSS-03 "last-updated-wins"**. Nếu user gõ 1 term_en đã tồn tại, bản dịch
  VI đang có sẽ bị **ghi đè im lặng**, không cảnh báo. Với glossary đã curate hàng trăm từ,
  đây là mất dữ liệu thật. Form thêm mới **phải** kiểm tra trùng và hỏi trước
  (thêm mới / cập nhật / huỷ).
- **YA-1.2 (scope)**: endpoint hardcode `scope="global"` (`glossary.py:132`, docstring nói
  rõ "UI hien tai chua co lua chon project glossary") nhưng tab Glossary **đã có** bộ lọc
  scope (`web/js/glossary.js:9,23`). Nếu user đang lọc theo project scope rồi bấm "thêm từ
  mới", entry rơi vào global và **biến mất khỏi danh sách đang xem** → user tưởng nút hỏng.
- **YA-1.3 (thiếu 2 trường nghiệp vụ)**: model `GlossaryEntry` có `notes` và `context_hint`
  (`src/models/glossary.py:32-33`). `notes` được API nhận (`GlossaryEntryIn`), `context_hint`
  thì **không** — dù EC-06 (fold = gập bột / gấp) và BR-GLOSS-05 (cột ghi chú) đều phụ thuộc
  nó. Form mới là cơ hội tự nhiên để bổ sung cả hai.
- **YA-1.4 ("(keep)" phải là lựa chọn tường minh)**: BR-GLOSS-04 quy định `term_vi` rỗng =
  giữ nguyên tiếng Anh. Nếu form chỉ có 1 ô text để trống, user **vô tình** bỏ trống sẽ tạo
  ra quy tắc "không dịch từ này" mà không hề biết. Cần 1 checkbox/radio "Giữ nguyên tiếng
  Anh (không dịch)" thay vì để suy ra từ ô trống.

**Edge case đáng lo**:
| # | Edge case | Rủi ro |
|---|-----------|--------|
| EC-17.1 | term_en chỉ khác nhau ở hoa/thường hoặc khoảng trắng thừa ("Ganache", " ganache ") | BR-GLOSS-02 là case-insensitive, nhưng `create_entry` chỉ `.strip()` term_en (`glossary.py:125`), không normalize khoảng trắng giữa từ → sinh entry "gần trùng" |
| EC-17.2 | Thêm từ xong, danh sách đang ở trang 3 của phân trang | Entry mới sắp theo `term_en` (`glossary.py:149`) có thể nằm ở trang khác → user không thấy, tưởng lỗi |
| EC-17.3 | Term đa từ ("baker's percentage", dấu nháy đơn) | Cần xác nhận matching glossary xử lý cụm nhiều từ ra sao (ngoài scope US-17 nhưng ảnh hưởng kỳ vọng của user) |

**AC-17.1**
- **Given** user ở tab Glossary
- **When** user bấm "Thêm từ mới", nhập term_en = "poolish", term_vi = "bột cái lỏng", bấm Lưu
- **Then** entry được tạo, danh sách reload và **hiển thị được** entry vừa tạo (nhảy tới
  trang chứa nó hoặc highlight), không cần F5

**AC-17.2**
- **Given** glossary đã có "ganache" → "sốt sô cô la"
- **When** user thêm mới "Ganache" (viết hoa) với bản dịch khác
- **Then** hệ thống **cảnh báo trùng** và hỏi rõ "Cập nhật bản dịch cũ hay huỷ?" — không
  ghi đè im lặng

**AC-17.3**
- **Given** user tick "Giữ nguyên tiếng Anh (không dịch)"
- **When** lưu
- **Then** entry lưu với `term_vi` rỗng/`(keep)` theo BR-GLOSS-04, và danh sách hiển thị rõ
  nhãn "giữ nguyên EN" chứ không phải ô trống trơn

### 6.3. Nhóm #2 — Search trong Glossary

**US-18**: **As a** người dịch sách bánh, **I want** tìm nhanh 1 thuật ngữ trong glossary
theo cả tiếng Anh lẫn tiếng Việt, **so that** tôi kiểm tra được "từ này đã có trong glossary
chưa" trước khi thêm trùng.

**Yêu cầu ẩn phát hiện được**:
- **YA-2.1 (bắt buộc server-side, không được filter client-side)**: `glossaryApp.load()`
  phân trang **phía server** (`web/js/glossary.js:19-27`, mặc định `limit=25`). Nếu làm
  search bằng cách lọc mảng `entries` ở client, nó chỉ lọc **25 dòng đang xem** — glossary
  1000 từ sẽ "không tìm thấy" từ nằm ở trang 8. Đây là bug kinh điển, phải chốt ngay ở PRD:
  search là **query param của `GET /api/glossary`**.
- **YA-2.2 (count phải lọc cùng điều kiện)**: `list_entries()` xây `count_statement` và
  `list_statement` **riêng biệt** (`src/api/routes/glossary.py:145-155`). Rất dễ chỉ thêm
  điều kiện search vào `list_statement` mà quên `count_statement` → `total` sai → nút
  "Trước/Sau" và dòng "N từ" hiển thị sai. Cần AC riêng cho việc này.
- **YA-2.3 (search phải reset `offset` về 0)**: nếu đang ở offset 50 rồi gõ search, kết quả
  chỉ còn 3 dòng thì trang hiện tại rỗng.
- **YA-2.4 (phạm vi tìm)**: user nói "search trong Glossary" — tìm trong `term_en` thôi hay
  cả `term_vi` và `notes`? Người dịch thường tìm ngược (nhớ bản dịch VI, quên từ EN gốc) nên
  BA nghiêng về tìm cả 2 cột chính.

**Edge case đáng lo**:
| # | Edge case | Rủi ro |
|---|-----------|--------|
| EC-18.1 | Tìm tiếng Việt **không dấu**: gõ "kem bo" mong ra "kem bơ" | SQLite `LIKE` không bỏ dấu. Nếu không xử lý, search VI gần như vô dụng với người gõ nhanh không dấu |
| EC-18.2 | Tìm tiếng Việt **viết hoa**: gõ "ĐƯỜNG" mong ra "đường" | SQLite `LIKE` chỉ case-insensitive cho ASCII; ký tự Việt có dấu **không** được fold → "Đ" không match "đ" |
| EC-18.3 | Search kết hợp bộ lọc scope đang có | Phải AND với nhau, không được ghi đè nhau |
| EC-18.4 | Ký tự `%`, `_` trong từ khoá | Là wildcard của `LIKE` → phải escape, nếu không "50%" trả về cả bảng |
| EC-18.5 | Không có kết quả | Cần empty state rõ ràng + gợi ý "Thêm từ mới này?" (bắc cầu sang US-17) |

**AC-18.1**
- **Given** glossary có 500 entry, "meringue" nằm ở trang 12 theo thứ tự alphabet
- **When** user gõ "meringue" vào ô search
- **Then** kết quả hiện ra ngay ở trang 1, `total` = số entry khớp (không phải 500)

**AC-18.2**
- **Given** glossary có entry term_vi = "kem bơ"
- **When** user gõ "kem bo" (không dấu)
- **Then** *(phụ thuộc BA-Q3)* — nếu chốt hỗ trợ không dấu: entry vẫn hiện ra

### 6.4. Nhóm #3 — Lịch sử: thời gian dịch, số trang, "xóa mục glossary"

**US-19**: **As a** người dịch sách bánh, **I want** nhìn thấy thời gian dịch và số trang
của từng job trong lịch sử, **so that** tôi ước lượng được lần sau dịch cuốn tương tự mất
bao lâu và đối chiếu chi phí trên mỗi trang.

**Yêu cầu ẩn phát hiện được** (tất cả đều BA đọc trực tiếp source):
- **YA-3.1 (backend bắt buộc phải sửa)**: xem Đ-01 ở 6.1.
- **YA-3.2 ("thời gian dịch" đo từ mốc nào — ảnh hưởng đúng/sai con số)**: `job.started_at`
  được gán ở **Step 6** (`src/core/job_orchestrator.py:371`), tức là **SAU** bước đếm trang
  và **SAU toàn bộ OCR** cho `pdf_scan` (`job_orchestrator.py:265-275`). Với 1 cuốn scan,
  OCR MinerU có thể mất nhiều phút và sẽ **hoàn toàn vô hình** trong con số "thời gian dịch".
  User nhìn thấy "6 phút" trong khi thực tế chờ 20 phút → mất niềm tin vào số liệu.
  → Cần chốt: đo `created_at → completed_at` (thời gian chờ thực tế của user) hay
  `started_at → completed_at` (thời gian LLM chạy thuần)? BA nghiêng về **hiện thời gian
  chờ thực tế**, và nếu muốn chi tiết thì hiện thêm phần OCR tách riêng.
- **YA-3.3 (job không thành công thì cột này rỗng)**: `job.completed_at` **chỉ** được gán
  trong nhánh thành công (`job_orchestrator.py:607`, xác nhận bằng grep toàn `src/`: không
  có chỗ gán nào khác). Job `failed` / `cancelled` / `cost_capped` sẽ có `completed_at =
  NULL` → cột "thời gian dịch" trống đúng lúc user cần biết nhất ("nó chạy bao lâu rồi mới
  chết?"). Cần fallback sang `updated_at` hoặc gán `completed_at` ở mọi nhánh kết thúc.
- **YA-3.4 (job resume làm sai lệch nghiêm trọng)**: `job.started_at = job.started_at or
  datetime.now(UTC)` (`job_orchestrator.py:371`) — giữ nguyên mốc bắt đầu **lần đầu**. 1 job
  bị `cost_capped`, để 3 ngày rồi user nâng trần và bấm Tiếp tục → "thời gian dịch" hiển thị
  **3 ngày**. Cần quyết định: cộng dồn thời gian chạy thật, hay ghi rõ "có gián đoạn".
- **YA-3.5 ("số trang" không tồn tại cho EPUB)**: `upload.py:127-134` chỉ đếm `page_count`
  khi `file_type != FileType.EPUB` → mọi job EPUB có `total_pages = None`. Cột "số trang" sẽ
  trống cho toàn bộ nhóm #6. Cần thống nhất trước: EPUB hiện "-" , hiện số chương, hay hiện
  số trang sau khi convert PDF.
- **YA-3.6 (job đang chạy)**: job `translating` chưa có `completed_at`. Hiện "-" hay đếm
  tiến (now − started_at)? Nếu đếm tiến thì cần refresh định kỳ.

**Edge case đáng lo**:
| # | Edge case | Rủi ro |
|---|-----------|--------|
| EC-19.1 | Job cũ trong DB tạo trước khi có 3 field này | `started_at`/`total_pages` = NULL → UI phải chịu được, không được vỡ |
| EC-19.2 | Đơn vị hiển thị | "342 giây" khó đọc; nên "5 phút 42 giây". Với job 415 trang có thể tới hàng giờ |
| EC-19.3 | `total_pages` của job scan | Đây là số trang PDF, không phải số trang OCR thành công — có thể lệch nếu vài trang bị drop (`ocr_dropped_spans`) |

**AC-19.1**
- **Given** 1 job PDF born-digital đã completed, 65 trang, chạy hết 8 phút 12 giây
- **When** user mở tab Lịch sử
- **Then** dòng job hiện "65 trang" và "8 phút 12 giây" (đúng theo mốc đã chốt ở BA-Q2)

**AC-19.2**
- **Given** 1 job `failed` sau 3 phút
- **When** user mở tab Lịch sử
- **Then** cột thời gian vẫn hiện "≈3 phút" (không để trống), có thể kèm dấu hiệu "dừng giữa
  chừng"

---

**"Xóa mục glossary trong lịch sử" — mơ hồ nghiêm trọng, BA đọc được 2 nghĩa trái ngược.**

Ngữ cảnh cần biết trước: backlog PRD trước đây (`docs/PRD.md:414` mục #4) ghi user nói
**"xóa mục"** (không có chữ "glossary") và PM đã hiểu là "xoá 1 job khỏi lịch sử" — việc đó
**đã làm xong** 2026-09-06 (Đ-02). Lần này user nói lại với **thêm chữ "glossary"**. Việc
thêm chữ này là tín hiệu có ý nghĩa, không nên bỏ qua.

- **Nghĩa (A) — Gỡ bỏ mục glossary khỏi tab Lịch sử** *(BA đánh giá khả năng cao hơn)*:
  đọc thuần tiếng Việt, "xóa mục glossary trong lịch sử" = "bỏ cái mục glossary đang nằm
  trong tab lịch sử đi". Hiện tab Lịch sử có nút "+ Glossary" trên mỗi dòng job
  (`web/history.html:61`) mở modal thêm thuật ngữ (`web/js/history.js:43-66`). Ngay khi
  nhóm #1 đưa chức năng "thêm từ mới" về đúng chỗ của nó (tab Glossary), nút này thành
  **thừa và đặt sai chỗ**. Đọc cả 7 yêu cầu như một chỉnh trang IA thì #1 và #3 khớp nhau
  hoàn hảo: chuyển chức năng sang tab đúng (#1) rồi dọn chỗ cũ (#3).
- **Nghĩa (B) — Thêm khả năng xoá thuật ngữ đã thêm từ 1 job** *(cách PM hiểu)*: hiện không
  có đường nào xem lại "job này đã thêm những từ nào". Muốn làm nghĩa (B) thì
  `GlossaryEntry` (`src/models/glossary.py:24-35`) **không có field nào truy vết job nguồn**
  → phải thêm cột `source_job_id` (breaking schema change, theo tiền lệ project là phải xoá
  và tạo lại DB dev), và cột đó chỉ có giá trị cho entry tạo **từ nay trở đi** — mọi entry
  cũ vĩnh viễn không truy vết được.

Chênh lệch công sức giữa 2 nghĩa là **rất lớn** (nghĩa A: xoá ~25 dòng HTML/JS; nghĩa B:
đổi schema + API + UI mới). Đây là câu hỏi clarify **ưu tiên cao nhất** của cả đợt này.

Lưu ý thêm: nếu chốt **nghĩa (A)** thì cần hỏi tiếp — có giữ lại đường tắt nào từ Lịch sử
sang Glossary không, vì tính năng #4 ("Các từ mới") nhiều khả năng sẽ **đặt đúng vào chỗ
vừa dọn đi** (xem 6.5).

### 6.5. Nhóm #4 — Mục "Các từ mới" (term extraction)

**US-20**: **As a** người dịch sách bánh, **I want** sau khi dịch xong 1 tài liệu, hệ thống
gợi ý danh sách thuật ngữ chuyên môn xuất hiện trong tài liệu đó mà glossary chưa có,
**so that** tôi bổ sung glossary dần theo từng cuốn sách thay vì phải ngồi soạn thủ công.

**Tính năng mới hoàn toàn — chưa có DB table / API / UI nào** (BA xác nhận lại bằng grep:
không có `suggested_term`, `candidate_term`, `term_extraction` nào trong `src/`).

**Yêu cầu ẩn phát hiện được — mục này nhiều yêu cầu ẩn nhất trong 7 nhóm**:

- **YA-4.1 (RÀO CẢN KIẾN TRÚC LỚN NHẤT — app không hề có cặp EN↔VI đã dịch)**: glossary là
  cặp EN→VI. Nhưng theo Architecture.md 6.6.2 R1, pdf2zh/babeldoc là tool **all-in-one tự
  gọi LLM trong subprocess riêng** — app **không bao giờ nhìn thấy** từng đoạn EN và bản
  dịch VI tương ứng. Bằng chứng gián tiếp trong chính DB: `job.cost_source` buộc phải là
  `"estimated"` vì "pdf2zh khong xuat token that" (`src/models/job.py:58-61`). Vậy nên
  "các từ mới" **không thể** lấy miễn phí từ log dịch. Chỉ còn 4 hướng, cần Tech Lead cân:
  (a) 1 lượt LLM riêng chạy trên text nguồn EN (tốn tiền thêm, có VI ngay);
  (b) rule-based trên text nguồn EN (miễn phí, nhưng **không có bản dịch VI** → user phải
  tự gõ từng từ);
  (c) đọc ngược text từ PDF đã dịch rồi căn chỉnh EN↔VI (mong manh, dễ sai);
  (d) chỉ bật cho **luồng dịch Markdown** ở nhóm #7 nếu luồng đó dùng Translation Engine
  nội bộ — khi đó app **có** cặp EN↔VI thật, gần như miễn phí. → **Đây là điểm giao rất
  đáng giá giữa #4 và #7**, PM nên cân nhắc làm #7 trước.
- **YA-4.2 (trạng thái "đã bỏ qua" là bắt buộc, không phải nice-to-have)**: nếu chỉ có
  "thêm vào glossary" mà không có "bỏ qua vĩnh viễn", thì cuốn sách thứ hai cùng chủ đề sẽ
  gợi ý lại y hệt những từ user đã cố tình từ chối ở cuốn thứ nhất. Sau 3-4 cuốn, danh sách
  gợi ý thành rác và user bỏ dùng tính năng. Cần tối thiểu 3 trạng thái:
  `pending / accepted / rejected`, và `rejected` phải có phạm vi **toàn cục** (không chỉ
  trong 1 job).
- **YA-4.3 (phải trừ đi glossary hiện có, kể cả case-insensitive)**: user viết rõ "sẵn sàng
  để cập nhật vào glossary hiện tại" → hàm ý danh sách chỉ nên chứa từ **chưa có**. Lọc
  phải theo BR-GLOSS-02 (case-insensitive), nếu không "Ganache" sẽ bị gợi ý dù đã có
  "ganache".
- **YA-4.4 (chi phí — nhạy cảm sau sự cố $6.50)**: nếu chọn hướng (a), đây là **lượt LLM
  phát sinh thêm mà user không chủ động yêu cầu**. Toàn bộ Cost Safety Lớp 0-3
  (Architecture.md 6.11) hiện chỉ tính chi phí **dịch**. Chi phí extraction phải: (i) hiện
  trước cho user, (ii) cộng vào `actual_cost` hay tách riêng field mới (quyết định nghiệp
  vụ, ảnh hưởng báo cáo chi phí), (iii) đi qua cùng cơ chế trần chi phí. **Không được** để
  1 tính năng phụ trợ đẻ ra chi phí ẩn.
- **YA-4.5 (thất bại của extraction không được làm hỏng job dịch)**: job dịch đã ra file
  đúng rồi. Nếu bước trích xuất lỗi (timeout/rate limit) thì job **vẫn phải** là `completed`
  và file vẫn tải được; chỉ mục "Các từ mới" báo lỗi riêng. Nếu ghép chung status, ta tạo ra
  đúng loại bug "job báo sai trạng thái" mà Protocol 6 sinh ra để chống.
- **YA-4.6 (ngưỡng chống spam)**: 1 cuốn 415 trang có thể sinh hàng trăm ứng viên. Cần
  ngưỡng: tối đa N từ/job (BA đề xuất 30-50), xếp hạng theo tần suất xuất hiện, và bỏ từ chỉ
  xuất hiện 1 lần (nhiều khả năng là tên riêng/lỗi OCR).
- **YA-4.7 (định nghĩa "thuật ngữ chuyên môn" — nghiệp vụ ngành bánh)**: cần chốt loại nào
  **được** gợi ý: (i) kỹ thuật/quy trình (autolyse, poolish, lamination, docking);
  (ii) nguyên liệu (fondant, ganache, tant pour tant); (iii) dụng cụ (bench scraper,
  couche, banneton); (iv) thuật ngữ đo lường (baker's percentage, hydration).
  Và loại nào **không**: tên riêng người/tiệm/vùng, tên món cụ thể, từ tiếng Anh phổ thông.
  Đặc thù ngành bánh: rất nhiều thuật ngữ là **tiếng Pháp/Ý** (EC-09) và thường nên để
  `(keep)` chứ không dịch → hệ thống nên **gợi ý sẵn** `(keep)` cho nhóm này.
- **YA-4.8 (vị trí trong IA)**: user gọi là "mục" → có thể là **tab thứ 5** trên nav (hiện
  có 4: Dịch tài liệu / Glossary / Lịch sử / Cài đặt), hoặc 1 khu vực trong tab Glossary
  (hợp lý về mặt nghiệp vụ vì đích đến là glossary), hoặc mở từ dòng job trong Lịch sử
  (đúng chỗ vừa dọn ở nghĩa (A) của 6.4). Cả 3 đều hợp lý → phải hỏi user.

**Edge case đáng lo**:
| # | Edge case | Rủi ro |
|---|-----------|--------|
| EC-20.1 | Từ đã có trong glossary nhưng tài liệu dùng bản dịch **khác** | Đây là "đề xuất sửa", không phải "từ mới" — trộn chung vào 1 danh sách sẽ khiến user vô tình ghi đè entry đã curate (nối tiếp YA-1.1) |
| EC-20.2 | "Chấp nhận tất cả" | Kết hợp BR-GLOSS-03 last-updated-wins → 1 cú bấm có thể ghi đè hàng chục entry cũ. Phải chặn hoặc cảnh báo rõ |
| EC-20.3 | Job `cost_capped` / `failed` giữa chừng | Có trích xuất từ phần đã dịch không? Nếu có, chất lượng thấp hơn |
| EC-20.4 | Job `parse_only` (không dịch) | Không có bản VI → chỉ gợi ý được từ EN |
| EC-20.5 | Tài liệu scan OCR sai chính tả | Rác OCR sẽ leo vào danh sách gợi ý ("ganaehe"). Nên hạ ưu tiên hoặc cảnh báo khi `ocr_confidence` thấp |
| EC-20.6 | Cụm nhiều từ ("baker's percentage", "double boiler") | Trích xuất theo từ đơn sẽ bỏ sót toàn bộ nhóm này — mà đây lại là nhóm thuật ngữ giá trị nhất |
| EC-20.7 | Xoá job khỏi lịch sử (đã có, Đ-02) trong khi còn từ gợi ý `pending` | Xoá theo (cascade) hay giữ lại? Nếu cascade, user mất danh sách chưa kịp duyệt |

**AC-20.1**
- **Given** 1 job vừa dịch xong 1 cuốn sách bánh mì
- **When** user mở mục "Các từ mới" của job đó
- **Then** hiện danh sách ≤ N thuật ngữ **chưa có** trong glossary, mỗi dòng có term EN,
  bản dịch VI đề xuất (nếu có), số lần xuất hiện, và 2 hành động rõ ràng: "Thêm vào
  glossary" / "Bỏ qua"

**AC-20.2**
- **Given** user đã bấm "Bỏ qua" cho từ "sourdough starter" ở job A
- **When** user dịch job B (cuốn khác) có chứa chính từ đó
- **Then** từ đó **không** xuất hiện lại trong gợi ý của job B

**AC-20.3**
- **Given** bước trích xuất từ mới lỗi (LLM timeout)
- **When** user xem tab Lịch sử
- **Then** job vẫn là `completed`, file dịch vẫn tải được bình thường; chỉ mục "Các từ mới"
  báo lỗi và cho phép chạy lại

### 6.6. Nhóm #5 — Hiện phiên bản BB-Translation

**US-21**: **As a** người dùng, **I want** nhìn thấy phiên bản app đang chạy, **so that** khi
báo lỗi hoặc đọc changelog tôi biết chắc mình đang dùng bản nào.

**Yêu cầu ẩn phát hiện được**:
- **YA-5.1 (đang có 2 nguồn version mâu thuẫn)**: `GET /api/version` đọc `pyproject.toml`
  → trả "1.2.7" (`src/api/main.py:64-76`, `pyproject.toml:3`). Nhưng `FastAPI(title=...,
  version="0.1.0")` (`src/api/main.py:86`) hardcode **0.1.0** và đây chính là số hiện trên
  `/docs` (OpenAPI). Phải gộp về 1 nguồn, nếu không sẽ có ngày ai đó đọc nhầm.
- **YA-5.2 (4 trang HTML tĩnh, không có template engine)**: nav lặp lại nguyên si ở
  `index.html`, `glossary.html`, `history.html` (`web/history.html:12-18`), `settings.html`.
  Nếu chèn version thủ công vào từng file thì lần sau sẽ có file bị quên. Nên nạp bằng JS
  dùng chung, gọi `/api/version` 1 lần.
- **YA-5.3 (cache trình duyệt)**: user cập nhật app xong mở lại vẫn thấy UI cũ do cache
  `web/js/*.js`. Lúc đó version hiển thị (lấy từ API, luôn mới) sẽ **mâu thuẫn với UI đang
  chạy (cũ)** — tệ hơn là không hiện gì. Nên cân nhắc cache-busting theo version.
- **YA-5.4 (fallback "unknown")**: `_read_app_version()` trả `"unknown"` khi không đọc được
  `pyproject.toml` (`main.py:74-76`). Chạy trong Docker/wheel không kèm `pyproject.toml` là
  đúng kịch bản đó. UI phải hiển thị tử tế, không để trống hay hiện "undefined".

**Edge case**: `/api/version` lỗi mạng → không được để lỗi JS chặn phần còn lại của trang.

**AC-21.1**
- **Given** app đang chạy version 1.2.7
- **When** user mở **bất kỳ** trang nào trong 4 trang
- **Then** thấy "v1.2.7" ở vị trí nhất quán (footer hoặc cạnh logo)

### 6.7. Nhóm #6 — Dịch EPUB

**US-22**: **As a** người dịch sách bánh, **I want** dịch được file EPUB, **so that** tôi xử
lý được ebook mua/tải về chứ không chỉ PDF.

**Trạng thái hiện tại**: `job_orchestrator.py:257-260` chủ động raise
`EpubNotSupportedError` ngay Step 1. `file_router.py:29-30` đã detect được `.epub`, upload đã
chấp nhận `.epub` (`upload.py:32`) — nghĩa là user **upload được rồi mới fail**, một trải
nghiệm tệ đang tồn tại.

#### 6.7.1. GAP Protocol 5 R5-01 — cần Tech Lead research lại từ đầu

Architecture.md §6.7 (dòng 1364-1383) mô tả contract của `bilingual_book_maker`
(`--model claude --claude_key`, `--prompt`) và Calibre (`ebook-convert` với 6 flag cụ thể)
**mà không có mục "Nguồn xác thực" nào** — khác hẳn §6.9/6.10/6.11/6.12 vốn đều trích dẫn
nguồn rõ ràng (§6.9 ghi thẳng "trang thai R5-01: toan bo section nay VERIFIED truc tiep tren
source code MinerU"). Bản thân §6.7 tự thừa nhận "Chi tiet mapping cho EPUB se chot o
increment EPUB".

Cụ thể các claim **chưa có nguồn** trong §6.7 — Tech Lead **không được** kế thừa as-is:
- `[CHƯA VERIFY]` bilingual_book_maker có backend Claude native qua `--model claude`
- `[CHƯA VERIFY]` cờ `--claude_key`, `--prompt` tồn tại và có ngữ nghĩa như mô tả
- `[CHƯA VERIFY]` 6 flag `ebook-convert` (`--pdf-page-margin-top`, `--embed-all-fonts`...)
- `[CHƯA VERIFY]` bilingual_book_maker xuất được bản **chỉ tiếng Việt** (tên tool là
  "bilingual" — mặc định nhiều khả năng là song ngữ, cần cờ riêng để ra bản đơn ngữ)

BA đã kiểm tra: **không có** `bilingual_book_maker`/`bbook_maker` hay `ebook-convert` trong
`.venv/bin` của repo (chạy `ls .venv/bin | grep -i ...`, 0 kết quả) → tool **chưa hề được
cài**, nên chưa từng có ai chạy `--help` để đối chiếu. Theo R5-02, Dev phải spike verify
**trước khi** implement, và theo R5-01 Tech Lead phải viết lại §6.7 kèm nguồn.

#### 6.7.2. Yêu cầu ẩn — nghiêm trọng nhất: EPUB hiện KHÔNG có lớp bảo vệ chi phí nào

Đây là phát hiện quan trọng nhất của BA trong cả đợt này.

- **YA-6.1 (Lớp 2 — pre-flight cost gate — không chạy được cho EPUB)**: `upload.py:127-134`
  cố ý **không** đếm `page_count` cho EPUB → `total_pages = None`. Trong khi
  `estimate_translation_cost()` gọi `_count_pdf_pages(file_path)` (`src/core/cost_gate.py:75`)
  và `jobs.py:724-725` raise 400 "Job chua co total_pages, khong the uoc tinh". Tức là với
  EPUB, gate ước tính chi phí hoặc **báo lỗi** hoặc **cho qua với số 0**.
- **YA-6.2 (Lớp 3 — running accumulator — cũng không áp dụng được)**: Lớp 3 cộng dồn chi phí
  **sau mỗi chunk** (Architecture.md 6.11.4, `job_orchestrator.py` Step 7). Nhưng thiết kế
  §6.7 gọi bilingual_book_maker **1 lần cho cả cuốn sách** — không có chunk nào để cộng dồn.
- **Kết luận YA-6.1 + YA-6.2**: nếu implement EPUB theo đúng §6.7 hiện tại, **cả hai lớp
  chặn chi phí đều vô hiệu** — đúng kịch bản đã gây sự cố mất $6.50 tiền thật, lần này với 1
  cuốn sách nguyên vẹn. **BA đề xuất coi đây là điều kiện chặn (blocking)**: không được
  release EPUB cho tới khi có mô hình ước tính chi phí + trần chi phí hoạt động thật cho
  EPUB.
- **YA-6.3 (mất luôn 4 tính năng vận hành đã có)**: các cơ chế sau đều gắn với chunk và sẽ
  **không hoạt động** cho EPUB kiểu 1-phát-cả-cuốn: tiến trình % thật (US-07), Dừng giữa
  chừng (Increment 6), Resume sau lỗi (BR-CHUNK-05), AIMD adaptive concurrency
  (Architecture.md 6.12). Cần chốt tường minh: chấp nhận EPUB "chạy là chạy tới cùng, không
  dừng được, lỗi là mất hết", hay đầu tư chunk theo **chương** (đơn vị tự nhiên của EPUB).
- **YA-6.4 (glossary injection)**: BR-GLOSS-01 là tuyến phòng thủ chất lượng chính. Đưa
  glossary vào bilingual_book_maker qua `--prompt` `[CHƯA VERIFY]`. Ngoài ra bước lọc
  glossary theo tài liệu (`only_terms_present_in=full_text`, `cost_gate.py:64`) cần trích
  text từ EPUB — hiện **chưa có** hàm nào làm việc đó (`_extract_full_text` dùng PyMuPDF cho
  PDF).
- **YA-6.5 (EPUB→PDF mâu thuẫn giá trị cốt lõi)**: giá trị cốt lõi của dự án là "giữ nguyên
  layout gốc". EPUB là **reflowable** — không có layout cố định. Convert sang PDF bằng
  Calibre là **sinh ra layout mới hoàn toàn**, không phải "giữ nguyên" gì cả. Nếu user chọn
  "muốn PDF", cần nói rõ để user không kỳ vọng nhầm. Ngoài ra Calibre là dependency nặng
  (bộ cài rất lớn) chỉ để phục vụ 1 bước phụ.
- **YA-6.6 (DRM)**: EC-05/BR đã quy định reject EPUB có DRM, nhưng **chưa có code nào kiểm
  tra** — hiện sẽ fail với lỗi khó hiểu từ tool bên thứ ba.
- **YA-6.7 (`output_mode` mapping)**: app có `monolingual`/`bilingual`
  (`jobs.py:50 _OUTPUT_MODE_MAP`). Cần chốt map sang cờ nào của bilingual_book_maker
  `[CHƯA VERIFY]`.

**Edge case đáng lo**:
| # | Edge case | Rủi ro |
|---|-----------|--------|
| EC-22.1 | EPUB có DRM | YA-6.6 |
| EC-22.2 | EPUB 3 với audio/video/MathML nhúng | Tool có giữ được không, hay hỏng file |
| EC-22.3 | EPUB "số trang" | Không có khái niệm trang → cột #3 trống (YA-3.5) |
| EC-22.4 | Font tiếng Việt trong EPUB | Reader tự chọn font → BR-FONT-01/02 gần như không áp dụng (điểm **thuận lợi** của EPUB) |
| EC-22.5 | Trùng hash (AC-12.2) | Cơ chế duplicate dùng file_hash, độc lập định dạng → dùng lại được |
| EC-22.6 | EPUB rất lớn (>100MB, sách ảnh) | US-16 nén ảnh hiện chỉ chạy cho PDF/babeldoc |

**AC-22.1**
- **Given** user upload 1 file EPUB hợp lệ, không DRM
- **When** bấm Dịch
- **Then** trước khi chạy, hệ thống hiện **ước tính chi phí** (theo mô hình chốt ở BA-Q7) và
  vẫn tôn trọng trần chi phí như PDF

**AC-22.2**
- **Given** EPUB đã dịch xong
- **When** user bấm Tải
- **Then** nhận đúng (các) định dạng đã chốt ở BA-Q6

**AC-22.3**
- **Given** EPUB có DRM
- **When** upload
- **Then** báo lỗi tiếng Việt rõ ràng "File EPUB có DRM, cần gỡ DRM trước khi dịch" —
  không phải stack trace của tool bên thứ ba

### 6.8. Nhóm #7 — Convert Markdown, "giữ nguyên vị trí" (user đánh dấu ưu tiên)

**Đây là yêu cầu mơ hồ nhất nhưng lại được user đánh dấu "(ưu tiên)"** → phải clarify trước
tiên, không được đoán.

#### 6.8.1. Mơ hồ 1 — Markdown của bản GỐC hay bản ĐÃ DỊCH?

Thiết kế US-15 / Architecture.md §6.8 hiện tại nói rõ: `parse_only` **"SKIP hoan toan
Translation Engine, Glossary Injection, va Unit Conversion"** (`docs/Architecture.md:1392`)
→ output là Markdown **tiếng Anh, chưa dịch**, chi phí LLM = 0.

Nghi ngờ của PM là có cơ sở và BA đồng tình: câu #7 nằm ngay sau "#6 Dịch epub" trong một
danh sách toàn về **dịch**, và động từ user dùng là "convert **định dạng**" (đổi format),
không phải "trích xuất để kiểm tra chất lượng parse" như lý do gốc của US-15. 3 cách hiểu:

- **(A) Markdown bản gốc EN, không dịch** — đúng US-15 §6.8 hiện có. Chi phí $0. Tận dụng
  lại được gần hết thiết kế cũ. Độ phức tạp **trung bình** (MinerU đã VERIFIED ở §6.9).
- **(B) Markdown bản đã dịch (VI)** — 1 **định dạng đầu ra mới** bên cạnh PDF. Nếu đúng
  nghĩa này thì §6.8 **sai mục tiêu**, không tái dùng được, phải thiết kế lại.
- **(C) Markdown song ngữ EN+VI xen kẽ** — để đối chiếu (nối tiếp AC-09.2).

**Ghi chú kỹ thuật quan trọng cho Tech Lead nếu chốt (B) hoặc (C)**: bản dịch hiện nay do
babeldoc/pdf2zh sinh ra **dạng PDF trong subprocess riêng** — app không giữ Markdown đã dịch
ở bất kỳ đâu. Hai hướng:
- (B-1) MinerU parse **ngược** file PDF đã dịch → Markdown. Không tốn thêm LLM, nhưng là
  parse lần 2 và thừa hưởng mọi lỗi layout của bước dịch.
- (B-2) Luồng riêng: MinerU parse EN → Markdown → dịch Markdown **bằng Translation Engine
  nội bộ** (`provider.translate()`, Increment 3) → Markdown VI. Đây là **trường hợp duy nhất
  trong toàn dự án** mà app tự dịch thay vì giao cho tool all-in-one → tự động có lại:
  glossary injection đúng chuẩn BR-GLOSS, cost metering **thật** (`cost_source="metered"`
  thay vì `"estimated"`), chunk/resume/cancel/AIMD, **và cặp EN↔VI đã căn chỉnh** —
  tức là giải luôn YA-4.1 của tính năng #4. Đắt hơn về công sức nhưng mở khoá nhiều thứ.

#### 6.8.2. Mơ hồ 2 — "giữ nguyên vị trí" nghĩa là gì trong Markdown?

Markdown **không có** khái niệm toạ độ/layout. 3 cách hiểu:
- **(i) Giữ đúng cấu trúc**: cấp heading (`#`/`##`/`###`), thứ tự và loại list, cấu trúc
  bảng, thứ tự đoạn văn — **khả thi**, và chính là AC của US-15 hiện có (`docs/PRD.md:163-165`).
- **(ii) Giữ ảnh đúng vị trí trong dòng chảy nội dung**: ảnh minh hoạ bước làm bánh nằm
  đúng giữa 2 đoạn văn như bản gốc, không bị dồn hết xuống cuối — **khả thi**, MinerU xuất
  link ảnh inline (`docs/Architecture.md:1440-1447`). BA cho rằng với sách dạy làm bánh
  (ảnh gắn chặt với từng bước) thì **đây rất có thể là ý user thật sự**.
- **(iii) Giữ toạ độ/pixel như PDF**: **bất khả thi** trong Markdown thuần. Muốn vậy phải
  xuất HTML/CSS định vị tuyệt đối — một sản phẩm khác hẳn.

**Yêu cầu ẩn khác**:
- **YA-7.1 (đóng gói khi tải về)**: output là `document.md` **+ thư mục `images/`**
  (`Architecture.md:1440-1447`). Người dùng bấm "Tải" phải nhận **1 file `.zip`**, không thể
  tải 1 file `.md` với link ảnh gãy. Endpoint download hiện trả 1 file đơn.
- **YA-7.2 (EPUB → Markdown lệ thuộc nhóm #6)**: §6.8 nói EPUB parse bằng
  `ebooklib` + `BeautifulSoup` + `markdownify` (`Architecture.md:1438`) — BA kiểm tra
  `pip list`: **chưa cài** package nào trong 3 cái đó. Nếu user muốn Markdown cho cả EPUB,
  #7 phụ thuộc một phần vào #6.
- **YA-7.3 (`parse_only` cho PDF born-digital vẫn phải qua MinerU)**: theo §6.8, PDF
  born-digital dùng MinerU `backend=pipeline` + `parse_method=txt` → **bắt buộc phải có
  MinerU chạy** (Docker), kể cả khi file không hề cần OCR. Với user chỉ có PDF thường, đây
  là 1 dependency nặng bất ngờ cần nói trước.
- **YA-7.4 (chi phí)**: cách hiểu (A) = $0 (chỉ compute local). Cách hiểu (B)/(C) = tốn LLM
  ngang bằng dịch PDF. Chênh lệch quá lớn để đoán mò — phải hỏi.

**AC-23.1** *(soạn theo cách hiểu (i)+(ii), độc lập với A/B/C)*
- **Given** file gốc có heading 3 cấp, bảng công thức 4 cột, và ảnh minh hoạ nằm giữa bước 3
  và bước 4
- **When** xuất Markdown
- **Then** Markdown giữ đúng 3 cấp heading, bảng ở dạng Markdown table đúng số cột, và link
  ảnh nằm đúng giữa bước 3 và bước 4 — không dồn ảnh xuống cuối file

**AC-23.2**
- **Given** job Markdown hoàn tất
- **When** user bấm Tải
- **Then** nhận 1 file `.zip` gồm `document.md` + thư mục `images/`, mở ra link ảnh hoạt động

### 6.9. Đề xuất chia increment

Tham chiếu quy mô: `project_state.json → iterations.by_increment` cho thấy 1 increment
thường là 1 lớp chức năng trọn vẹn (ví dụ `increment_5_job_upload_api_websocket_frontend`
gồm API + WebSocket + toàn bộ frontend), và các chuỗi sửa lỗi lớn (`bug7_...`) được tách
riêng thành đơn vị độc lập.

| Increment | Gồm | Phức tạp | Rủi ro | Phụ thuộc |
|---|---|---|---|---|
| **INC-7 — Quick wins UI/UX** | #1, #2, #3, #5 (US-17,18,19,21) | **Thấp** | **Thấp** | Không |
| **INC-8 — Markdown output** | #7 (US-23) | **TB** nếu (A) / **Cao** nếu (B)/(C) | TB — MinerU đã VERIFIED, nhưng cần MinerU chạy thật | Chốt BA-Q8/Q9 |
| **INC-9 — "Các từ mới"** | #4 (US-20) | **TB-Cao** | TB — schema mới + chi phí LLM mới | Rẻ hơn nhiều nếu làm SAU INC-8 phương án (B-2) |
| **INC-10a — EPUB spike (R5-02)** | Verify contract bilingual_book_maker + chốt mô hình cost cho EPUB | **TB** | **Cao** | Chặn INC-10b |
| **INC-10b — EPUB pipeline** | #6 (US-22) | **Cao** | **Cao** | INC-10a phải xong và §6.7 phải viết lại kèm nguồn |

**Lý do xếp thứ tự này**:
1. **INC-7 đi trước** dù user đánh ưu tiên cho #7: 4 tính năng, không phụ thuộc tool ngoài,
   không phát sinh chi phí LLM, giá trị nhìn thấy ngay, và **chỉ cần 1 câu trả lời clarify**
   (BA-Q1). Đưa được giá trị ra sớm trong lúc chờ user trả lời các câu khó hơn.
2. **INC-8 (#7) ngay sau** để tôn trọng dấu "(ưu tiên)" của user — với điều kiện BA-Q8/Q9 đã
   có câu trả lời trước khi Tech Lead bắt đầu.
3. **INC-9 (#4) sau INC-8** vì nếu INC-8 chốt phương án (B-2), tính năng #4 gần như được
   tặng kèm cặp EN↔VI (YA-4.1) — làm ngược thứ tự sẽ phải xây rồi đập.
4. **INC-10 (#6 EPUB) sau cùng**: phức tạp nhất, rủi ro cao nhất, **và đang có 1 lỗ hổng
   chi phí có thể gây mất tiền thật** (YA-6.1/6.2) cần thiết kế lại trước khi viết dòng code
   nào. Tách spike (10a) khỏi implement (10b) đúng theo R5-02.

**Rủi ro tổng thể cần PM ghi vào PRD**:
| # | Rủi ro | Mức | Giảm thiểu |
|---|---|---|---|
| R-06 | EPUB chạy không có lớp chặn chi phí nào → lặp lại sự cố $6.50 ở quy mô 1 cuốn sách | **Cao** | Coi là điều kiện chặn release; INC-10a phải chốt mô hình ước tính cho EPUB trước |
| R-07 | §6.7 EPUB vi phạm R5-01 (contract không nguồn) → lặp lại đúng 2 lần lỗi pdf2zh/MinerU | **Cao** | Tech Lead viết lại §6.7 kèm nguồn; Dev spike theo R5-02 trước khi implement |
| R-08 | #7 bị hiểu sai (A vs B) → thiết kế lại từ đầu sau khi đã code | **Cao** | Chặn INC-8 tới khi có câu trả lời BA-Q8 |
| R-09 | #4 sinh chi phí LLM ẩn user không lường trước | TB | Hiện chi phí trước, đi qua cost gate, hoặc chạy rule-based miễn phí |
| R-10 | #4 spam gợi ý → user bỏ dùng sau vài cuốn | TB | Trạng thái `rejected` toàn cục + ngưỡng N từ/job (YA-4.2, YA-4.6) |
| R-11 | Search glossary làm client-side → sai âm thầm với glossary lớn | TB | Chốt server-side ngay ở PRD (YA-2.1) |
| R-12 | Thêm từ mới ghi đè entry đã curate (BR-GLOSS-03) | TB | Cảnh báo trùng bắt buộc (YA-1.1) |

### 6.10. Cau hoi can clarify

#### Uu tien cao (chan thiet ke, khong tra loi thi khong viet duoc PRD/Architecture)

**BA-Q1 — "Xóa mục glossary trong lịch sử" nghĩa là gì?** *(nhóm #3)*
Hai cách hiểu chênh nhau rất xa về công sức (xem 6.4):
- (A) **Gỡ bỏ** nút "+ Glossary" khỏi tab Lịch sử, vì tab Glossary sắp có nút thêm từ riêng
  (yêu cầu #1) → sửa ~25 dòng, xong trong INC-7.
- (B) **Thêm** khả năng xem/xoá những thuật ngữ đã thêm từ 1 job cụ thể → phải đổi DB schema
  (thêm `source_job_id`), entry cũ không truy vết được.
- (C) Ý khác (xoá cả glossary? xoá cột nào đó?).
*(Lưu ý cho PM: nút "Xoá job" đã tồn tại từ 2026-09-06 nên chắc chắn user không nói về nó.)*

**BA-Q2 — "Thời gian dịch" tính từ mốc nào?** *(nhóm #3)*
- (A) **Tổng thời gian chờ**: từ lúc tạo job đến lúc xong (bao gồm cả OCR) — con số user
  thực sự cảm nhận.
- (B) **Chỉ thời gian dịch thuần**: bỏ qua OCR — hiện code đang đo kiểu này, và với file
  scan sẽ **thiếu mất toàn bộ thời gian OCR** (có thể vài chục phút).
- (C) Hiện cả hai (tổng + tách riêng OCR).
*(Kèm 1 câu phụ: job thất bại/bị dừng có muốn thấy "đã chạy bao lâu" không, hay để trống?)*

**BA-Q3 — Search glossary tìm trong những cột nào, và có cần tìm không dấu?** *(nhóm #2)*
- (A) Chỉ `term_en`.
- (B) Cả `term_en` + `term_vi` *(BA đề xuất — người dịch hay tìm ngược từ bản dịch VI)*.
- (C) Cả 3: `term_en` + `term_vi` + ghi chú.
- Phụ: gõ **"kem bo"** có cần ra **"kem bơ"** không? (có = thêm việc kỹ thuật, không = search
  VI phải gõ đủ dấu)

**BA-Q4 — Mục "Các từ mới" đặt ở đâu?** *(nhóm #4)*
- (A) **Tab mới thứ 5** trên thanh nav, gom từ mới của tất cả tài liệu.
- (B) **Trong tab Glossary**, một khu vực "Chờ duyệt" ngay cạnh danh sách chính.
- (C) **Trong tab Lịch sử**, mở từ từng dòng job (đúng chỗ nút "+ Glossary" hiện tại — hợp
  với phương án (A) của BA-Q1).

**BA-Q5 — Danh sách "Các từ mới" cần có bản dịch VI sẵn không?** *(nhóm #4, ảnh hưởng chi phí)*
- (A) **Có, hệ thống dịch sẵn** → cần thêm 1 lượt gọi LLM sau mỗi job (tốn thêm tiền, ước
  tính nhỏ so với tiền dịch nhưng **là chi phí mới**), user chỉ việc duyệt.
- (B) **Không, chỉ liệt kê từ tiếng Anh** → miễn phí hoàn toàn, nhưng user phải tự gõ bản
  dịch cho từng từ.
- (C) Cho user chọn từng lần ("gợi ý bản dịch" là 1 nút riêng, bấm mới tốn tiền).
- Phụ: mỗi tài liệu tối đa bao nhiêu từ gợi ý là hợp lý? (BA đề xuất 30-50, xếp theo số lần
  xuất hiện)

**BA-Q6 — Dịch EPUB xong muốn nhận file gì?** *(nhóm #6)*
- (A) **Chỉ EPUB đã dịch** (đọc trên máy đọc sách/điện thoại).
- (B) **Chỉ PDF** — *cảnh báo thẳng: EPUB không có layout cố định, nên PDF này là layout do
  máy sinh mới hoàn toàn, KHÔNG phải "giữ nguyên layout gốc" như với PDF. Ngoài ra phải cài
  thêm Calibre (bộ cài rất nặng).*
- (C) **Cả hai**.
- Phụ: bản song ngữ EN-VI cho EPUB có cần không?

**BA-Q7 — Chấp nhận rủi ro chi phí cho EPUB thế nào?** *(nhóm #6 — BA khuyến nghị mạnh)*
Hiện tại **cả 2 lớp chặn chi phí đều không áp dụng được cho EPUB** (6.7.2): không đếm được
số trang để ước tính trước, và không chia chunk để cộng dồn chi phí trong lúc chạy. Nghĩa là
1 cuốn EPUB dày có thể chạy tới khi hết tiền mà không có phanh nào — đúng kịch bản đã gây
sự cố mất $6.50.
- (A) **Đầu tư làm chunk theo chương** cho EPUB → có ước tính, có trần chi phí, dừng được,
  chạy lại được. Tốn công hơn, an toàn.
- (B) Làm nhanh trước, chấp nhận **không có trần chi phí** cho EPUB, chỉ cảnh báo bằng chữ.
- (C) Trung gian: chỉ ước tính thô theo dung lượng file + bắt user xác nhận trước khi chạy.

**BA-Q8 — "Convert Markdown" là bản GỐC tiếng Anh hay bản ĐÃ DỊCH tiếng Việt?** *(nhóm #7 — câu quan trọng nhất của mục được user đánh ưu tiên)*
- (A) **Bản gốc tiếng Anh, không dịch** — để tự kiểm tra chất lượng bóc tách trước khi tốn
  tiền dịch, hoặc để tự dịch tay / đưa vào hệ thống khác. Chi phí $0.
- (B) **Bản đã dịch tiếng Việt** — coi Markdown là **một định dạng xuất mới** bên cạnh PDF.
  Tốn tiền dịch như bình thường.
- (C) **Song ngữ**, Anh và Việt xen kẽ để đối chiếu.
*(Thiết kế cũ trong tài liệu đang là (A). Nếu user muốn (B) thì phải thiết kế lại từ đầu —
đó là lý do phải hỏi trước khi làm.)*

**BA-Q9 — "Giữ nguyên vị trí" trong Markdown nghĩa là gì?** *(nhóm #7)*
- (A) **Giữ đúng cấu trúc**: cấp tiêu đề, thứ tự và loại danh sách, bảng đúng số cột.
- (B) **Giữ ảnh đúng chỗ**: ảnh minh hoạ nằm đúng giữa các bước như sách gốc, không bị dồn
  xuống cuối *(BA đoán đây là ý chính với sách dạy làm bánh)*.
- (C) **Cả A và B**.
- (D) Giữ y hệt vị trí như trang PDF (toạ độ) — *cần nói rõ: Markdown không làm được, muốn
  vậy phải xuất HTML, là một sản phẩm khác*.

#### Uu tien trung binh (anh huong UX, khong chan kien truc)

**BA-Q10 — Thêm từ mới vào Glossary: gặp từ đã tồn tại thì xử lý sao?** *(nhóm #1)*
Hiện tại backend **ghi đè im lặng** bản dịch cũ (BR-GLOSS-03 last-updated-wins).
- (A) Cảnh báo "Từ này đã có: <bản dịch cũ>" và hỏi Ghi đè / Huỷ *(BA đề xuất)*.
- (B) Luôn ghi đè, không hỏi (giữ nguyên hành vi hiện tại).
- (C) Chặn hẳn, bắt user vào sửa entry cũ.
- Phụ: form thêm từ có cần ô "ghi chú" và ô "ngữ cảnh" không (để phân biệt *fold* = gập bột
  vs gấp giấy), hay chỉ cần 2 ô Anh–Việt cho nhanh?

**BA-Q11 — Version hiển thị ở đâu và có cần thông tin gì thêm?** *(nhóm #5)*
- (A) Footer nhỏ ở cuối mọi trang.
- (B) Cạnh chữ "BB-Translation" trên thanh nav.
- Phụ: có cần thêm ngày build / mã commit để tiện báo lỗi không, hay chỉ "v1.2.7" là đủ?

**BA-Q12 — "Bỏ qua" một từ gợi ý có nhớ vĩnh viễn không?** *(nhóm #4)*
- (A) **Có, nhớ toàn cục** — đã từ chối thì không bao giờ gợi ý lại ở tài liệu khác
  *(BA đề xuất — nếu không, sau vài cuốn danh sách sẽ thành rác)*.
- (B) Chỉ bỏ qua trong phạm vi tài liệu đó.

#### Uu tien thap (co the chot sau, khong chan increment nao)

**BA-Q13** — Xoá 1 job khỏi lịch sử trong khi job đó còn "từ mới" chưa duyệt: xoá luôn danh
sách gợi ý hay giữ lại? *(nhóm #4, EC-20.7)*

**BA-Q14** — Markdown cho EPUB có cần không, hay chỉ cần cho PDF? *(nhóm #7, YA-7.2 — nếu
cần thì #7 phụ thuộc một phần vào #6)*

**BA-Q15** — Trong danh sách "Các từ mới", các thuật ngữ tiếng Pháp/Ý (ngành bánh rất nhiều:
*tant pour tant*, *pâte à choux*, *biga*) có nên được đề xuất sẵn là "giữ nguyên, không
dịch" theo BR-GLOSS-04 không? *(nhóm #4, YA-4.7)*

---

*Section 6 — version 1.0*
*Author: BA Agent*
*Ngày: 2026-09-08*
*Status: Draft — chờ user trả lời BA-Q1..Q9 trước khi PM viết PRD (Protocol 2, Human
Checkpoint 1)*
