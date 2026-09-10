# EPUB batch translate — golden fixture (Protocol 5 mục 3)

Contract JSON app↔LLM (`build_epub_batch_prompt()`/`parse_epub_batch_response()`,
Architecture.md 6.20.12 X4) là **external contract** — định dạng thật LLM trả về không do
team kiểm soát. File dưới đây được capture từ **1 lần gọi thật** tới DeepSeek, KHÔNG viết tay.

## `deepseek_batch_response_sourdough_ch1_5units.json`

- **Ngày chạy**: 2026-09-09.
- **Provider/model**: `deepseek` / `deepseek-chat` (repoint server-side sang `deepseek-v4-flash`,
  xem `src/services/deepseek_provider.py`), qua `ProviderFactory.create("deepseek", settings)` với
  `DEEPSEEK_API_KEY` thật trong `.env`.
- **Nguồn**: 5 unit thật lấy từ `EpubDocument.load()` trên
  `data/uploads/9d436d7b-…_Baking with Sourdough - Sara Pitzer.epub`, `ops/xhtml/chapter01.html`
  ordinal 16/17/18/87/288 — chọn để phủ đúng 6 bước spike a→f của Architecture.md 6.20.10 mục 1:
  1 heading có `<a id="page_4"/>`, 1 danh sách nguyên liệu `<strong>…</strong><br/>` × 4 (bước d),
  1 đoạn văn thường (không markup), 1 dòng phân số thuần `<sup>1</sup>/<sub>3</sub>` và 1 dòng hỗn
  số `1<sup>1</sup>/<sub>3</sub>` (bước c — ca N-1 Tech Lead đã cảnh báo: chỉ đúng nếu `1` đứng
  trước `<sup>` không bị gộp thành `11/3`).
- **Request thật**: đúng payload `build_epub_batch_prompt()` → `provider.translate(payload_json,
  system_prompt, "en", "vi")` qua `with_retry()`, id ngắn cục bộ `0..4` (X4/X5). `system_prompt`
  xác nhận chứa marker `BB-EPUB-JSON-CONTRACT-X4` (`system_prompt_marker_check: true`).
- **Kết quả**: JSON object sạch, KHÔNG có markdown code fence, KHÔNG lời dẫn, đủ 5/5 id, giữ
  nguyên `<strong>`/`<br/>`/`<sup>`/`<sub>`/`<a id=…>` đúng số lượng và vị trí, không đổi số. Dòng
  hỗn số ra đúng `1<sup>1</sup>/<sub>3</sub>` (không bị gộp `11/3`).
- **Chi phí thật đã tốn**: `input_tokens=1456`, `output_tokens=459`,
  **`estimated_cost_usd=0.00062326`** (≈ 0,06 cent USD — script chỉ gọi API đúng 1 lần).
- **Script capture** (không lưu trong repo, chạy 1 lần trong scratchpad phiên Dev): load
  `EpubDocument`, build `payload_json` từ 5 unit trên, `build_system_prompt()` (glossary rỗng —
  DB trống, chỉ cần glossary_prompt thật, không cần glossary entry cụ thể) →
  `build_epub_batch_prompt()`, gọi `provider.translate()` qua `with_retry()`, ghi thẳng
  `TranslationResult.text` (raw, CHƯA parse) vào `raw_response_text` của fixture này.

Dùng bởi `tests/test_epub_batch_golden_fixture.py`: `parse_epub_batch_response()` chạy trên
CHÍNH `raw_response_text` này (không phải chuỗi viết tay), assert đủ 5/5 id, nội dung giữ đúng
`<strong>`/`<sup>`/`<sub>`/`<br/>`, và dòng hỗn số không bị hỏng thành `11/3`.

## `deepseek_batch_response_sourdough_ch1_trailing_garbage.json`

**Bối cảnh**: bắt được khi Dev chạy live E2E full-book (`run_epub_job()` qua `JobOrchestrator`,
không mock) trên chính file Sourdough thật để verify guard BR-EPUB-05 sau khi sửa bug class
`_mark_bb_vi()` (US-22 Bước 2/3, vòng 1/3 review) — KHÔNG nằm trong scope 3 điểm review-report.md
yêu cầu sửa, là 1 phát hiện mới trong lúc verify.

- **Ngày chạy**: 2026-09-09.
- **Provider/model**: `deepseek` / `deepseek-chat`, qua `ProviderFactory.create("deepseek",
  settings)` với `DEEPSEEK_API_KEY` thật trong `.env` — giống hệt cách gọi thật của
  `_process_epub_chunk()`.
- **Nguồn**: 1 unit thật `ops/xhtml/chapter01.html#13` (đoạn văn dài, nhiều `<a href>` có thuộc
  tính `class` đã escape `\"`, số điện thoại, URL) — đúng unit đã làm `run_job()` full-book FAIL
  2 lần liên tiếp với lỗi `EpubBatchTranslationError` ("thieu ban dich cho 1 unit sau 1 vong goi
  lai rieng le") dù nội dung đã dịch đúng.
- **Phát hiện**: `raw_response_text` là 1 JSON object HỢP LỆ (`{"0": "..."}`), nhưng DeepSeek trả
  thừa đúng 1 ký tự `"` NGAY SAU dấu `}` đóng — `json.loads()` fail với `JSONDecodeError: Extra
  data at pos 1098`. Tái hiện **deterministic** (không phải flake) — gọi lại đúng unit này (kể cả
  ở request batch lẫn request retry lẻ trong `_process_epub_chunk()`) cho cùng 1 dạng lỗi cả 2
  lần trong `run_job()` full-book, và lần thứ 3 (capture fixture này) khi gọi tách riêng.
- **Hậu quả trước fix**: `parse_epub_batch_response()` coi TOÀN BỘ phản hồi là hỏng (`{}`, mọi id
  coi như thiếu) — vì lỗi lặp lại y hệt ở CẢ vòng gọi lại lẻ (X4), unit này luôn "thiếu bản dịch
  sau 1 vòng gọi lại riêng lẻ" → `EpubBatchTranslationError` → chunk `failed` → **job tốn tiền
  thật cho các request đã chạy trước đó trong chunk, rồi vẫn kết thúc `failed`** — cùng loại rủi ro
  tài chính mà bug chính của vòng review này (guard BR-EPUB-05) được sinh ra để chặn, chỉ khác điểm
  lỗi trong pipeline.
- **Fix**: `parse_epub_batch_response()` (`src/core/prompt_builder.py`) khi gặp
  `JSONDecodeError` với `msg == "Extra data"`, thử `json.loads()` lại đúng phần văn bản TRƯỚC vị
  trí lỗi (`text[:exc.pos]`) — nếu phần đó tự nó là JSON object hợp lệ thì dùng, nếu không mới trả
  `{}` như cũ. Một `JSONDecodeError` vì lý do KHÁC "Extra data" (vd JSON bị cắt cụt giữa chừng, hết
  `max_tokens`) vẫn trả `{}` như cũ — không nới lỏng cho trường hợp thực sự hỏng.
- **Chi phí thật đã tốn cho riêng fixture này**: `input_tokens=796`, `output_tokens=420`,
  **`estimated_cost_usd=0.00045232`** (~0,045 cent USD, 1 lần gọi). Ngoài ra 2 lần chạy
  `run_job()` full-book (fail ở chunk 0, trước khi phát hiện + sửa bug này) đã tốn thêm chi phí
  thật cho các request đã hoàn tất trong chunk 0 trước điểm fail — số tiền nhỏ, cùng cấp độ với
  golden fixture 5-unit gốc ở trên (~vài phần nghìn USD/request).

Dùng bởi `tests/test_epub_batch_golden_fixture.py` (3 test): xác nhận `raw_response_text` thật
sự làm `json.loads()` thô fail với "Extra data" (không phải fixture đã bị "dọn sạch" trước khi
lưu), và `parse_epub_batch_response()` sau fix trích đúng nội dung đã dịch từ chính response đó.

## `deepseek_batch_response_sourdough_ch1_multi_json_object_partial_capture.json` (ĐÃ XOÁ — xem mục kế tiếp)

**CẬP NHẬT 2026-09-10**: PM đã duyệt 1 lần gọi API DeepSeek thật để hoàn thiện golden fixture đầy
đủ, thay thế hoàn toàn file "partial capture" mô tả bên dưới (file JSON này đã bị XOÁ khỏi
`tests/fixtures/epub_llm/`, cùng các test tham chiếu nó trong `tests/test_epub_batch_golden_fixture.py`).
Xem mục **`deepseek_batch_response_sourdough_ch1_multi_json_object.json`** ở cuối file README này
để biết fixture đầy đủ hiện dùng. Giữ nguyên mô tả gốc bên dưới cho lịch sử (Protocol 1 R7-03 —
không xoá lịch sử handoff), KHÔNG còn áp dụng cho code/test hiện tại.

**⚠️ KHÁC 2 fixture ở trên — đây KHÔNG phải golden fixture đầy đủ đúng nghĩa Protocol 5 mục 3.**
Tự đánh dấu rõ trong field `protocol_5_status` của chính file JSON. Đọc mục này trước khi dùng lại
fixture này cho bất kỳ việc gì khác ngoài phạm vi đã ghi dưới đây.

**Bối cảnh**: Bug #EPUB-B2-3 (`docs/test-report.md`, QA vòng 2/5, 2026-09-10) — DeepSeek trả về 1
batch reply (11 unit, chunk 1, sách Sourdough) dưới dạng NHIỀU object JSON top-level rời rạc nối
tiếp nhau (`{"0": "..."}\n{"1": "..."}\n...\n{"10": "..."}`) thay vì 1 object gồm đủ 11 key. Nhánh
xử lý "Extra data" cũ chỉ giữ object đầu tiên (`"0"`), mất 10 id còn lại — nội dung đã dịch đúng,
đã trả tiền — dẫn tới chunk fail vĩnh viễn (E-09) sau khi gọi lại nguyên request (C-1) tái tạo đúng
lỗi tách-object đó.

**Giới hạn dữ liệu nguồn (lý do fixture này KHÔNG đầy đủ)**: QA log lại vụ này bằng script
`test_live_epub_diagnostic.py` (monkeypatch `parse_epub_batch_response()` để log mỗi lần gọi) tại
`diagnostic_parse_calls.jsonl`, NHƯNG script đó chỉ ghi `raw_text[:300]` và `raw_text[-300:]` cho
mỗi entry — KHÔNG BAO GIỜ ghi toàn bộ `raw_text` (2886 ký tự cho entry khớp mô tả bug này, call_no=5
— 11 id kỳ vọng, `parsed_count=1` trước fix, `missing_ids` = toàn bộ id "1".."10"). Không có nơi nào
khác trong scratchpad phiên QA (`full_run.log`, `tmp_live*/`, `qa.db`) lưu lại full raw text.

Dev đã thử tự chạy 1 lần live call thật để capture đầy đủ theo đúng tinh thần Protocol 5 R5-02
(spike verification) — viết `capture_full_raw.py` (mirror `test_live_epub_diagnostic.py` nhưng log
`raw_text_full` không cắt) — nhưng bị **auto-mode financial-action classifier của Claude Code chặn**
(lệnh gọi API DeepSeek thật tốn tiền thật, cần permission người dùng rõ ràng theo safety rules của
môi trường Dev đang chạy, Dev không được tự tìm cách bypass). Đây là giới hạn môi trường/permission,
không phải Dev bỏ qua bước verify.

**Fixture này giữ được gì THẬT 100% (verbatim, copy nguyên văn từ `diagnostic_parse_calls.jsonl`)**:
- 294 ký tự ĐẦU của giá trị id `"0"` (từ `raw_text_head`).
- Toàn bộ id `"9"` và `"10"` — cả 2 nằm trọn trong 300 ký tự CUỐI (`raw_text_tail`) nên là THẬT
  100%, không thiếu ký tự nào.
- 1 đoạn fragment thật nằm giữa 2 cửa sổ 300-ký-tự (đầu của `raw_text_tail`, thuộc về 1 object nào
  đó KHÔNG xác định được id) — giữ nguyên byte thật, bọc vào 1 key giả
  `_qa_log_tail_fragment_not_an_expected_id` KHÔNG nằm trong `expected_ids` để test xác nhận nó bị
  loại bỏ đúng như mọi id lạ khác (không lẫn vào kết quả).

**Fixture này KHÔNG giữ được (placeholder, tự gắn nhãn `[RECONSTRUCTED - ...]` ngay trong chính giá
trị JSON, không giấu)**: phần đuôi giá trị id `"0"` (sau 294 ký tự đầu) và TOÀN BỘ nội dung id
`"1"` đến `"8"` — không ai (kể cả QA) biết nội dung dịch thật của các id này là gì, vì chưa từng
được lưu lại ở bất kỳ đâu. Cấu trúc "mỗi id 1 object riêng" áp dụng cho id 1-8 trong fixture là suy
diễn ngoại suy từ cấu trúc ĐÃ XÁC NHẬN của id 9/10 (mỗi id đúng là 1 object riêng) — hợp lý nhưng
KHÔNG được xác nhận độc lập cho riêng id 1-8.

**Phạm vi dùng hợp lệ của fixture này**: verify đúng THUẬT TOÁN merge của
`_decode_concatenated_json_objects()` trên hình dạng phản hồi ĐÃ XÁC NHẬN THẬT (N>1 object JSON
top-level rời rạc nối tiếp) và đúng nội dung tại các đoạn THẬT (id 0 prefix, id 9, id 10). KHÔNG
dùng fixture này để khẳng định bất kỳ điều gì về nội dung dịch thật của id 1-8, hay để thay thế yêu
cầu có 1 golden fixture đầy đủ nếu sau này cần verify lại chính xác byte-for-byte.

**Escalate cho PM/Tech Lead** (xem `docs/CHANGELOG.md` mục "Fix Bug #EPUB-B2-3" — 2026-09-10): cần
1 trong hai để có golden fixture đầy đủ đúng chuẩn Protocol 5 — (a) tìm lại full raw text nếu có lưu
ở nơi khác ngoài scratchpad đã kiểm tra, hoặc (b) user cho phép chạy `capture_full_raw.py` (đã viết
sẵn, nằm trong scratchpad phiên Dev) 1 lần thật.

Dùng bởi `tests/test_epub_batch_golden_fixture.py` (4 test) và `tests/test_epub_batch_prompt.py`
(5 test tổng hợp bổ sung, không phụ thuộc fixture này — kiểm logic merge tổng quát: nhiều object,
key trùng, rác thật ở cuối, giá trị JSON không phải object lạc vào giữa).

## `deepseek_batch_response_sourdough_ch1_multi_json_object.json`

**Golden fixture ĐẦY ĐỦ (Protocol 5 mục 3) cho Bug #EPUB-B2-3 — thay thế hoàn toàn fixture
"_partial_capture" ở mục trên (đã xoá).**

- **Ngày chạy**: 2026-09-10. PM đã duyệt riêng 1 lần gọi API DeepSeek thật (hành động tốn tiền
  thật) cho đúng mục đích hoàn thiện fixture này — xem `docs/CHANGELOG.md` mục tương ứng.
- **Provider/model**: `deepseek` / `deepseek-chat` (repoint server-side sang `deepseek-v4-flash`),
  qua `ProviderFactory.create("deepseek", settings)` với `DEEPSEEK_API_KEY` thật trong `.env`.
- **Nguồn**: đúng slice đã làm job thật fail trong QA vòng 2/5 (`docs/test-report.md`,
  Bug #EPUB-B2-3) — `plan_epub_chunks()` trên sách Sourdough thật sinh ra chunk 1, request slice
  unit index (45, 55) = 11 unit liên tiếp `ops/xhtml/chapter01.html#36` .. `#46` (đã xác nhận bằng
  script kiểm tra chunk plan thật, khớp đúng ví dụ QA trích `'ops/xhtml/chapter01.html#37'` —
  chính là unit ordinal thứ 2 trong slice này).
- **Request thật**: đúng payload `[{"id": "0".."10", "html": unit.text}]` → `build_epub_batch_prompt()`
  → `provider.translate(payload_json, system_prompt, "en", "vi")` gọi trực tiếp (không qua
  `with_retry()` — script capture chỉ gọi 1 lần cho mục đích capture, không cần retry logic).
  `system_prompt` xác nhận chứa marker `BB-EPUB-JSON-CONTRACT-X4`.
- **Kết quả tái hiện**: **THÀNH CÔNG ngay ở lần gọi đầu tiên (1/5 attempt cho phép)** — DeepSeek trả
  về đúng 11 object JSON top-level rời rạc nối tiếp nhau bằng dấu xuống dòng
  (`{"0": "..."}\n{"1": "..."}\n...\n{"10": "..."}`), `json.loads()` thô fail với
  `JSONDecodeError: Extra data at pos 802` — đúng y hệt hình dạng lỗi QA đã báo cáo. Toàn bộ 11 id
  đều có nội dung dịch tiếng Việt có dấu đầy đủ, không có placeholder/reconstructed nào — khác hẳn
  fixture "_partial_capture" cũ.
- **Chi phí thật đã tốn**: `input_tokens=1994`, `output_tokens=1279`,
  **`estimated_cost_usd=0.00128282`** (~0,13 cent USD) — đúng 1 lần gọi duy nhất, không cần thử
  lại lần 2-5 vì hiện tượng tách-object lặp lại ngay từ lần đầu.
- **Script capture**: `capture_full_raw.py` (không lưu trong repo, chạy 1 lần trong scratchpad
  phiên Dev) — load `EpubDocument` thật, tính `plan_epub_chunks()` để xác định đúng slice
  (45, 55), build `payload_json` + `system_prompt` giống hệt `_process_epub_chunk()`, gọi
  `provider.translate()` tối đa 5 lần (dừng ngay khi tái hiện được, không gọi thêm để tiết kiệm
  chi phí — chỉ dùng 1/5), ghi thẳng `TranslationResult.text` (raw, CHƯA parse) vào
  `raw_response_text`.

Dùng bởi `tests/test_epub_batch_golden_fixture.py`: `parse_epub_batch_response()` chạy trên CHÍNH
`raw_response_text` này, assert đủ 11/11 id, nội dung khớp đúng (id "0" đầu, id "2" có
`<em>`/`<a id=...>`, id "9"/"10" cuối — khớp đúng câu QA đã trích trong `docs/test-report.md`), và
`unit_ids_in_order[1] == "ops/xhtml/chapter01.html#37"` xác nhận đúng vị trí bug đã báo cáo.

## `deepseek_batch_response_sourdough_comma_separated_json_objects.json`

**Golden fixture THẬT cho Bug #EPUB-B2-4 (`docs/test-report.md`, QA vòng 3/5, 2026-09-10) — CÙNG
họ lỗi với Bug #EPUB-B2-3 ở trên (DeepSeek trả nhiều JSON value top-level rời rạc thay vì 1 object
gộp đủ id) nhưng nối nhau bằng DẤU PHẨY (`}, {`) thay vì xuống dòng.**

- **Ngày lấy fixture**: 2026-09-10 — KHÔNG cần gọi API mới, lấy trực tiếp từ file log chẩn đoán còn
  tồn tại của chính QA vòng 3/5
  (`/private/tmp/.../fdb2c2d6-8d19-46e6-9002-56e408e83320/scratchpad/qa_round3/diagnostic_calls.jsonl`,
  dòng thứ 17, `call_no: 17`) — mỗi dòng trong file này là 1 lần gọi `provider.translate()` THẬT,
  không mock, được QA tự ghi lại trong lúc chạy `run_full_book_diag.py` (full-book live E2E,
  `JobOrchestrator` thật, DeepSeek thật).
- **Provider/model**: `deepseek` / `deepseek-chat`, giống hệt các fixture trên.
- **Phát hiện**: `raw_response_text` là 32 object JSON top-level rời rạc (id `"0"`..`"31"`), nối
  nhau bằng `", "` (dấu phẩy + khoảng trắng) thay vì `"\n"` — fix Bug #EPUB-B2-3 trước đó chỉ skip
  whitespace giữa 2 lần `raw_decode()` nên dừng lại NGAY tại dấu phẩy (không phải whitespace), chỉ
  giữ được object đầu tiên (`"0"`), mất toàn bộ `"1"`..`"31"`. `json.loads()` thô fail với
  `JSONDecodeError: Extra data: line 1 column 482 (char 481)`.
  `raw_response_text` cũng kết thúc bằng 1 dấu `}` thừa sau object cuối cùng (`..."}}`) — vừa là ví
  dụ thật khác về "trailing garbage sau JSON hợp lệ" (giống fixture `..._trailing_garbage.json` ở
  trên nhưng xảy ra SAU khi đã merge nhiều object, không phải chỉ 1 object).
- **Bài học rút ra (ghi rõ trong `docs/CHANGELOG.md`)**: đây là bằng chứng cho thấy "ký tự phân
  cách giữa 2 object nối rời rạc" KHÔNG PHẢI 1 hằng số cố định (đã quan sát ít nhất 2 biến thể khác
  nhau: newline và dấu phẩy) — nên fix lần này KHÔNG vá thêm 1 ký tự cụ thể nữa, mà tổng quát hoá
  toàn bộ thuật toán `_decode_concatenated_json_objects()` (`src/core/prompt_builder.py`): sau mỗi
  lần `raw_decode()` thành công, tìm vị trí ký tự mở JSON tiếp theo (`{`/`[`, qua
  `_NEXT_JSON_VALUE_START_RE`) bất kể ký tự phân cách ở giữa là gì, thay vì chỉ `lstrip()`
  whitespace.
- **Khác biệt so với 2 fixture trên**: KHÔNG có `request_payload`/`unit_ids_in_order`/
  `local_id_to_unit_id` đầy đủ — script chẩn đoán của QA vòng 3/5 chỉ log
  `call_no`/`payload_chars`/`input_tokens`/`output_tokens`/`estimated_cost_usd`/`raw_text` cho mỗi
  lần gọi (không log lại request payload đi kèm). `expected_ids` trong fixture được suy ra trực
  tiếp từ chính các id `"0"`..`"31"` xuất hiện trong `raw_response_text` thật — vẫn đủ điều kiện cho
  mục đích test parser (Protocol 5 R5-01 chỉ yêu cầu `raw_response_text` là byte-for-byte thật,
  không viết tay — không bắt buộc mọi field phụ trợ khác phải đầy đủ).
- **Chi phí**: `input_tokens=2299`, `output_tokens=1392`, `estimated_cost_usd=0.0014245` — chi phí
  này đã phát sinh THẬT trong phiên QA vòng 3/5 (không phải phát sinh mới ở bước lấy fixture này, vì
  fixture lấy lại từ log cũ, không gọi API mới).

Dùng bởi `tests/test_epub_batch_golden_fixture.py` (5 test): xác nhận `raw_response_text` thật sự
làm `json.loads()` thô fail với "Extra data" (dấu phẩy, khác vị trí lỗi so với ca newline), sau fix
`parse_epub_batch_response()` gộp đủ 32/32 id, nội dung id `"0"`/`"31"` khớp đúng, và xác nhận có
dấu `}` thừa ở cuối. `tests/test_epub_batch_golden_fixture.py` còn có thêm 2 test TỔNG HỢP (không
phụ thuộc fixture này) dùng ký tự phân cách CHƯA TỪNG gặp (`;`, và khoảng trắng+tab+xuống dòng trộn
lẫn) để tự chứng minh thuật toán mới tổng quát thật — 2 test đó PASS mà không cần sửa thêm bất kỳ
dòng code nào ngoài fix tổng quát đã mô tả ở trên.

---

## `deepseek_batch_response_sourdough_single_object_spurious_closing_braces.json` (APPEND, QA vòng 5/5, 2026-09-10 — Bug #EPUB-B2-5, MỚI, chưa fix)

- **Ngày lấy fixture**: 2026-09-10 — lấy trực tiếp từ file log chẩn đoán của chính QA vòng 5/5
  (`/private/tmp/.../fdb2c2d6-8d19-46e6-9002-56e408e83320/scratchpad/qa_round5/diagnostic_calls.jsonl`,
  `call_no: 16` — lần GỌI LẠI/retry nguyên request cho chunk 4, thất bại giống hệt cấu trúc với
  `call_no: 15` là request gốc), ghi lại trong lúc chạy `run_full_book_diag.py` (full-book live E2E
  lần thứ 3 liên tiếp trên cùng file mẫu, `JobOrchestrator` thật, DeepSeek thật, SAU KHI fix Bug
  #EPUB-B2-4 đã được Reviewer APPROVE).
- **Provider/model**: `deepseek` / `deepseek-chat`.
- **Phát hiện — BIẾN THỂ MỚI, KHÁC CẢ B2-3 VÀ B2-4**: `raw_response_text` chỉ có **DUY NHẤT 1 ký tự
  `{`** (mở đầu response) nhưng có **32 ký tự `}`** (đếm trực tiếp bằng `text.count("{")`/
  `text.count("}")`, không suy đoán). Model rõ ràng định trả về 1 object gộp
  `{"0": "...", "1": "...", ..., "31": "..."}` nhưng chèn NHẦM 1 dấu `}` thừa ngay sau MỖI giá trị
  (thay vì dấu `,` phân cách key), rồi mới đóng object thật ở cuối — khác hẳn B2-3 (N object riêng
  biệt nối bằng newline, mỗi object có `{` riêng) và B2-4 (N object riêng biệt nối bằng dấu phẩy,
  mỗi object vẫn có `{` riêng). `json.loads()` thô fail với `Extra data: line 1 column 482
  (char 481)` — CÙNG vị trí lỗi với fixture B2-4 (trùng hợp ngẫu nhiên do cùng payload gốc tương tự,
  không phải cùng nguyên nhân).
- **Vì sao fix B2-4 (tìm `{`/`[` tiếp theo) KHÔNG cứu được ca này**: sau khi `raw_decode()` decode
  xong key `"0"` tại vị trí dấu `}` THỪA ĐẦU TIÊN (hợp lệ về cú pháp JSON thuần, dù sai ý định của
  model), thuật toán B2-4 tìm ký tự `{`/`[` tiếp theo trong phần còn lại của chuỗi — nhưng KHÔNG CÒN
  `{` NÀO NỮA (chỉ có đúng 1 `{` trong toàn bộ response, đã dùng hết). Vòng lặp dừng ngay, chỉ giữ
  được `1/32` key — mất `31/32` bản dịch đã trả tiền, đúng nghĩa, có dấu đầy đủ (tự mắt kiểm tra nội
  dung `raw_response_text` xác nhận). Đây là **giới hạn cấu trúc của chính hướng tiếp cận "tìm
  `{`/`[` tiếp theo"**, không phải lỗi triển khai sai fix B2-4 — Reviewer đã APPROVE đúng phạm vi
  fix B2-4 giải quyết (xem `docs/review-report.md`, "Rủi ro còn lại" đã tiên liệu đúng khả năng (a):
  "DeepSeek trả về 1 dạng lỗi hoàn toàn khác... JSON lồng sai cấu trúc, mismatched brace bên trong 1
  object thay vì giữa các object").
- **Khác biệt so với các fixture trên**: KHÔNG có `request_payload`/`unit_ids_in_order` đầy đủ (cùng
  lý do B2-4 fixture — script chẩn đoán không log payload gửi đi). `expected_ids` suy trực tiếp từ
  32 id `"0"`..`"31"` xuất hiện thật trong `raw_response_text`.
- **Chi phí**: đã phát sinh THẬT trong phiên QA vòng 5/5 (không gọi API mới ở bước lấy fixture này).

**CHƯA có test nào dùng fixture này** — đây là bằng chứng RAW cho Dev ở vòng fix tiếp theo (nếu PM
quyết định mở vòng mới sau khi escalate người dùng theo Protocol 3), lưu lại NGAY để không bị mất
theo đúng bài học rút ra từ Finding non-blocking #3 (`docs/review-report.md`, review Bug #EPUB-B2-4)
— log chẩn đoán ở `scratchpad/` dễ bị dọn trước khi Dev kịp dùng.
