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
