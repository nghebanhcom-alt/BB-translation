# Escalation Log — US-22 Dịch EPUB, Bước 2/3 (Translation Engine + Cost-gate)

**Ngày escalate**: 2026-09-10
**Lý do**: Chạm giới hạn Protocol 3 (Circuit Breaker) — 5/5 vòng Dev↔QA cho cùng 1 chuỗi vấn đề mà
vẫn chưa đạt `ready_for_release: YES`.

## Tóm tắt vấn đề gốc

QA phát hiện US-22 Bước 2/3 (Dev implement xong, Reviewer đã APPROVE lần đầu) có 2 bug BLOCKING khi
chạy dịch EPUB thật qua DeepSeek:
1. **Bug #EPUB-B2-1** — chi phí/chunk biến thiên bất thường (model "runaway" sinh dư token).
2. **Bug #EPUB-4** — ~30% đoạn dịch bị mất dấu tiếng Việt hoàn toàn ở batch lớn.

## Diễn biến 5 vòng Dev↔QA

| Vòng | Việc | Kết quả |
|---|---|---|
| 1/5 | QA phát hiện Bug #EPUB-B2-1 + #EPUB-4 (2 phiên QA song song, tính chung 1 vòng) | NO — Dev fix, Reviewer APPROVE |
| 2/5 | QA re-verify sau fix: guard runaway PASS, guard mất dấu đúng hướng (0% trên mẫu nhỏ) — nhưng phát hiện **Bug #EPUB-B2-3 MỚI**: DeepSeek đôi khi trả 2+ JSON object rời rạc nối bằng **newline** trong 1 response, code parse cũ vứt bỏ object thứ 2 (10 bản dịch hợp lệ, đã trả tiền) | NO — Dev fix (`_decode_concatenated_json_objects()`), Reviewer APPROVE, kèm golden fixture thật |
| 3/5 | QA chạy full-book đầu tiên với cả 3 fix — tiến xa hơn (4/7 chunk, 45% sách) nhưng phát hiện **Bug #EPUB-B2-4**: biến thể khác — model nối JSON bằng **dấu phẩy** (`}, {`) thay vì newline, fix trước chỉ skip whitespace nên không xử lý được | NO — Dev **tổng quát hoá** thuật toán (tìm ký tự mở JSON tiếp theo bằng regex, không vá riêng ký tự phân cách), Reviewer APPROVE với độ tự tin cao (tự verify độc lập bằng 2 ký tự phân cách chưa từng gặp) |
| 4/5 (Reviewer) | Review fix tổng quát Bug #EPUB-B2-4 | APPROVE |
| 5/5 (CUỐI) | QA chạy full-book lần 3 — tiến xa hơn nữa (chunk 4-5/7, 45-67% sách) nhưng phát hiện **Bug #EPUB-B2-5**: biến thể **HOÀN TOÀN KHÁC** 2 bug trước — response chỉ có **1 dấu `{` nhưng 32 dấu `}`** (model chèn nhầm `}` thừa sau mỗi giá trị thay vì dấu `,` phân cách key). Thuật toán "tìm `{` tiếp theo" của fix B2-4 không cứu được vì không còn `{` thứ 2 nào để tìm — đây là giới hạn cấu trúc của chính cách tiếp cận đó | **NO — CHẠM GIỚI HẠN PROTOCOL 3** |

## Bằng chứng tiến bộ thật (không phải bế tắc hoàn toàn)

- Diacritic ratio (Bug #EPUB-4 gốc): 30% → 0% → 0% → **0/107 unit (0,00%) trên 67% sách**, nhất quán
  qua 3 lần đo độc lập — **fix này đáng tin cậy**.
- Cost estimate accuracy: actual/estimate 1,84× → 1,15× → **1,09×** — cải thiện liên tục.
- Job tiến được xa hơn qua từng vòng: fail ở 8% sách → 45% sách → 67% sách — mỗi vòng fix đều xử lý
  đúng 1 biến thể lỗi thật, không phải "sửa vô ích".
- 720/720 test pass, ruff sạch ở mọi vòng — không có regression nào trong suốt quá trình.
- Guard runaway (Bug #EPUB-B2-1): PASS, verify chắc chắn, không tái phát ở bất kỳ vòng nào.

## Bản chất vấn đề còn lại

DeepSeek (khi phải trả về JSON cho batch ~15-18 đơn vị dịch cùng lúc, response dài) có xu hướng **đôi
khi tạo ra JSON KHÔNG hợp lệ cú pháp theo nhiều CÁCH KHÁC NHAU** khi output dài — đây là hành vi
ngẫu nhiên/không ổn định của model ở mức "malformed JSON generation" cho response lớn, không phải 1
lỗi cụ thể có thể vá dứt điểm bằng cách xử lý từng dạng lỗi cú pháp riêng lẻ. Mỗi vòng fix đều đúng
cho ĐÚNG biến thể đã quan sát được, nhưng model liên tục tạo ra biến thể MỚI mà code chưa từng thấy.

**3 biến thể đã quan sát được cho tới nay**:
1. 2 object JSON hợp lệ nối bằng newline.
2. 2 object JSON hợp lệ nối bằng dấu phẩy.
3. 1 object nhưng cú pháp bên trong hỏng (`}` thừa lặp lại thay vì `,`).

## Khuyến nghị hướng đi tiếp theo (cần người quyết định)

Vá tiếp theo từng biến thể lỗi cú pháp cụ thể **nhiều khả năng sẽ tiếp tục lộ ra biến thể thứ 4, thứ
5...** — đây là dấu hiệu cần đổi CHIẾN LƯỢC thay vì tiếp tục vá tại tầng parse response. Một số hướng
khả thi để cân nhắc:

1. **Giảm kích thước batch/request** (`EPUB_REQUEST_CHAR_BUDGET`, hiện ~3.000 ký tự/~15-18 đơn vị) —
   giả thuyết: request nhỏ hơn → model ít có khả năng tạo JSON dài hỏng cú pháp. Cần đo thật (R5-02)
   để xác nhận có giảm tỉ lệ lỗi không, đánh đổi: nhiều request hơn → chi phí/thời gian tăng.
2. **Không dùng JSON làm format phản hồi** — chuyển sang format ít lỗi hơn cho model (ví dụ delimiter
   đơn giản dạng `<<<ID>>>nội_dung<<<END>>>` thay vì JSON) — tránh hẳn lớp lỗi "JSON syntax" nhưng là
   thay đổi kiến trúc lớn, cần Tech Lead thiết kế lại contract + prompt.
3. **Dùng tính năng "structured output"/"JSON mode" của DeepSeek nếu API hỗ trợ** (cần Protocol 5
   R5-01 verify — hiện chưa xác nhận DeepSeek OpenAI-compat layer có hỗ trợ `response_format=
   {"type": "json_object"}` ép model tuân thủ JSON nghiêm ngặt hơn hay không).
4. **Chấp nhận rủi ro có kiểm soát**: giữ nguyên cơ chế hiện tại (đã xử lý được 3/N biến thể), dựa
   vào tính resumable (BR-CHUNK-05) — khi job fail vì 1 biến thể JSON hỏng chưa từng gặp, user bấm
   Retry, và HY VỌNG lần retry model không lặp lại đúng lỗi đó (thực tế đã quan sát được: có lúc model
   LẶP LẠI lỗi ở lần gọi lại, có lúc không — không nhất quán). Rủi ro: trải nghiệm user kém (job có
   thể fail nhiều lần liên tiếp cho cùng 1 sách), nhưng không mất tiền ngoài kiểm soát và không cần
   thêm code.

**Đề xuất của tôi (PM)**: hướng 1 (giảm batch size) là rẻ nhất để thử trước — có thể đo nhanh bằng
cách chạy lại full-book với `EPUB_REQUEST_CHAR_BUDGET` nhỏ hơn (ví dụ giảm 1 nửa) xem tỉ lệ lỗi JSON
có giảm rõ rệt không, trước khi quyết định đầu tư vào hướng 2/3 (thay đổi kiến trúc lớn hơn).

## Chi phí thật đã phát sinh cho toàn bộ chuỗi 5 vòng

Ước tính tổng cộng (cộng dồn tất cả các lần chạy live qua các vòng): **~$0.35-0.45 USD**.
