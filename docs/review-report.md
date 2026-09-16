

> **Protocol C — lưu trữ (2026-09-10)**: 20 đợt trước đó đã chuyển nguyên văn sang
> [`docs/archive/review-report-until-2026-09-10.md`](archive/review-report-until-2026-09-10.md). File này chỉ giữ **11 đợt gần nhất**.
> Đợt mới **APPEND vào cuối file này** (R7-03 — không ghi đè). Khi file vượt ngân sách
> Protocol C (`python3 scripts/validate_state.py` cảnh báo), rotate tiếp theo cùng cách.
>
> <details><summary>Danh sách 20 đợt đã lưu trữ</summary>
>
> | # | Đợt |
> |---|---|
> | 1 | Review Report — Increment 1 (Project Scaffolding) |
> | 2 | Iteration 2 — Verify Fix Round 1 |
> | 3 | Increment 2 — Iteration 1 |
> | 4 | Increment 3 — Iteration 1 |
> | 5 | Increment 4 — Fix Round 1 Review (Architecture Correction) |
> | 6 | Review Report — Increment 6 (UX & Model Management) |
> | 7 | Review Report — 2026-09-06 |
> | 8 | Review Report — 2026-09-06 (Iteration 2 — verify fix cho 3 issue của Iteration trước) |
> | 9 | Review Report — Fix bug line-break/paragraph-splitting babeldoc (F1/F2/F4) |
> | 10 | P0 — Babeldoc Layout Bug Fix Roadmap (Gate P0.1 + Pin P0.3) — Iteration 1 |
> | 11 | P1 — Babeldoc Layout Bug Fix Roadmap (P1.1 overlay chữ xoay G1e + P1.2 prompt bất biến nội |
> | 12 | P1.1 Overlay chữ xoay (G1e) — Vòng 2/3 (Dev↔Reviewer) |
> | 13 | Review — Bug #6 Phase 1 + task P0 (logging) — 2026-09-07 |
> | 14 | Review Report — Bug #7 spike (7.0) + fix (7.1) — list line-break shim |
> | 15 | Review — Bug #7 Ca C — Spike 7.4-a (Protocol 5 R5-02) (Reviewer, 2026-09-08) |
> | 16 | Review — Bug #7 Ca C — Implement đầy đủ 7.4-b→e (wiring + test + live E2E + hồi quy) (Reviewer, 2026-09-08) |
> | 17 | Review — US-16 v2 (mở rộng nén ảnh sang `/FlateDecode` + fix `bilingual_merge.py`) — 2026-09-08 |
> | 18 | Review Report — US-20 "Các từ mới" (gợi ý thuật ngữ mới) |
> | 19 | Review Report — US-22 Dịch EPUB, Bước 1/3 (`EpubDocument` parser + chunk theo chương) |
> | 20 | Review Report — US-22 Dịch EPUB, Bước 1/3 — VÒNG 2/3 (Dev↔Reviewer, Protocol 3) |
>
> </details>

---

# Review Report — US-22 Dịch EPUB, Bước 2/3: Translation Engine thật + cost-gate

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-09
- **Circuit breaker Dev↔Reviewer (US-22 Bước 2/3)**: vòng 1/3
- **Phạm vi review**: nối `EpubDocument` (đã APPROVE ở Bước 1/3) vào Translation Engine thật +
  cost-gate — 2 entry CHANGELOG "US-22 Dịch EPUB — Bước 2/3" + "fix E2: lọc glossary theo
  `full_text`". Đọc toàn bộ Architecture.md §6.20.6-6.20.9, §6.20.12 (X3/X4/X5/Y6), PRD US-22/
  BR-EPUB-01..06, và source code thật (`job_orchestrator.py`, `cost_gate.py`, `prompt_builder.py`,
  `retry.py`, 5 provider, `epub_document.py::count_bb_vi_pairs()`, models, `jobs.py` routes, toàn
  bộ test mới + golden fixture).

## Verdict: REJECT

Lý do: **1 blocking issue nghiêm trọng, live-verify được trên chính file EPUB thật duy nhất của dự
án** — guard BR-EPUB-05 (nhánh `bilingual=True`, mặc định hardcode cho EPUB) **luôn luôn fail** trên
mọi job dịch thật, kể cả khi bản dịch hoàn toàn đúng và đã tốn tiền thật. Đây chính xác là lớp bảo
vệ mà PM yêu cầu đánh giá nghiêm ngặt nhất (mục 5 trong brief) — và nó không hoạt động như thiết kế
trên dữ liệu thật, theo hướng ngược lại với Bug #5 (thay vì "completed" trên nội dung sai, ở đây là
"failed" trên nội dung ĐÚNG và đã trả tiền). Kèm 1 issue trung bình (Y6 chưa đóng hoàn toàn cho
DeepL) và 1 issue nhỏ (ngưỡng 90% của guard bị làm tròn xuống). Phần còn lại của bước 2/3 — cost
gate EPUB (X5), contract JSON (X4), data lineage (R6-02), retry 5xx cho 4/5 provider, golden
fixture, migration DB — đều đúng thiết kế, tự verify được bằng số đo thật, xem "Điểm đạt" bên dưới.

---

## Blocking issues (bắt buộc sửa trước khi merge)

### 1. `_mark_bb_vi()` làm hỏng attribute `class` dưới parser XML → guard BR-EPUB-05 (nhánh `bilingual=True`) luôn fail trên EPUB thật

**File**: `src/services/epub_document.py`, hàm `_mark_bb_vi()` (dòng 342-346):

```python
def _mark_bb_vi(node: Tag) -> None:
    node["lang"] = _BB_VI_LANG
    existing = node.get("class") or []
    if _BB_VI_CLASS not in existing:
        node["class"] = [*existing, _BB_VI_CLASS]
```

**Nguyên nhân gốc**: `EpubDocument` dùng parser `"xml"` (`features="xml"`, lxml) làm parser CHÍNH
theo đúng Y1 — và với builder XML, BeautifulSoup **không** coi `class` là multi-valued attribute
(đó là hành vi riêng của HTML builder). Nghĩa là `node.get("class")` trả về một **chuỗi** (vd
`"noindent"`), không phải list (vd `["noindent"]"`). Khi `_mark_bb_vi()` chạy
`[*existing, _BB_VI_CLASS]` trên một **chuỗi**, Python unpack chuỗi thành TỪNG KÝ TỰ:
`[*"noindent", "bb-vi"]` → `['n','o','i','n','d','e','n','t','bb-vi']` — serialize ra
`class="n o i n d e n t bb-vi"`. Đây không phải suy diễn — đã tự verify trực tiếp bằng
`BeautifulSoup(..., "xml")` (xem log dưới).

**Live-verify trên chính file EPUB thật duy nhất của dự án** (không chỉ đọc code — đúng yêu cầu
"tự chạy thử" ở mục 5 của brief):

```python
from src.services.epub_document import EpubDocument, count_bb_vi_pairs
from src.core.job_orchestrator import _check_epub_output_guard, EpubEmptyOutputError

doc = EpubDocument.load(SRC)  # ...Baking with Sourdough - Sara Pitzer.epub, file thật trong data/uploads/
translations = {u.unit_id: f"VI:{u.text}" for u in doc.units}  # bản dịch giả nhưng HOÀN TOÀN khác bản gốc
doc.write_translated(translations, out, bilingual=True)
_check_epub_output_guard(doc, out, bilingual=True)
```

Kết quả thật:

```
src.core.job_orchestrator.EpubEmptyOutputError: File dich chi co 0/384 node ban dich
(lang="vi" + class="bb-vi") — duoi 90% yeu cau, co the da mat noi dung khi ghi (BR-EPUB-05).
```

Guard fail **0/384** dù **toàn bộ 384 unit đều đã được "dịch"** (nội dung khác hẳn bản gốc, có tiền
tố `"VI:"` để phân biệt). Kiểm tra trực tiếp trong file zip vừa ghi:

```
<p class="n o i n d e n t bb-vi" lang="vi">VI:...</p>
<h2 class="h 2 bb-vi" lang="vi">VI:Baking with Sourdough</h2>
```

— chuỗi `"bb-vi"` **có mặt** trong file (nên `EpubDocument.load()` gián tiếp vẫn đếm đúng
`len(units)` vì `_has_bb_vi_class()` dùng `in` trên chuỗi = substring match, tình cờ vẫn khớp), nhưng
`count_bb_vi_pairs()` — dùng `soup.find_all(class_=_BB_VI_CLASS)`, một phép so khớp CÓ CẤU TRÚC của
BeautifulSoup — **không khớp** một attribute value đã bị hỏng thành `"n o i n d e n t bb-vi"` (khác
hẳn chuỗi chính xác `"bb-vi"`). Đối chiếu với file gốc: `chapter01.html` có sẵn các class
`noindent/indent/indent1/indent2/blockquote/right/image/...` trên hầu như MỌI `<p>` — nên bug này
áp dụng cho **100% unit** của cuốn sách thật duy nhất hiện có, không phải một ca hiếm.

**Vì sao lọt qua toàn bộ 12 test mới**: `_build_epub()` trong
`tests/integration/test_epub_translate_runner.py` dựng EPUB tổng hợp với `<p>Chapter 0 paragraph
0: ...</p>` — **không có attribute `class` nào cả** trên các `<p>` gốc. Với node KHÔNG có `class`,
`node.get("class")` trả về `None` → `existing = None or [] = []` (list rỗng, không phải chuỗi) →
`[*[], "bb-vi"]` hoạt động đúng. Bug chỉ lộ ra khi node gốc **đã có sẵn** attribute `class` — đúng
tình trạng của mọi EPUB được dàn trang thật (kể cả file mẫu chính thức của Architecture.md §6.20.3).
Đây là đúng dạng lỗi mà Protocol 6/Bug #5 tồn tại để chặn: dữ liệu test tổng hợp "tự nhất quán với
chính nó" nhưng không đại diện cấu trúc thật.

**Hậu quả**: `bilingual=True` là giá trị HARDCODE mặc định duy nhất hiện có cho EPUB (§6.20.11 mục
2, CHỐT). Với guard fail như trên, **mọi job dịch EPUB thật trên cuốn sách mẫu hiện có sẽ luôn kết
thúc `job.status='failed'`** ngay sau khi đã tốn tiền thật cho toàn bộ các chunk (Lớp 3
`chunk.api_cost` đã cộng dồn xong trước khi guard chạy ở bước E9) — người dùng trả tiền, nhận về
"failed", không phải EPUB dịch được. Đây là biến thể ngược của chính Bug #5 mà BR-EPUB-05 được sinh
ra để chặn: thay vì "completed" trên nội dung rỗng/sai, ở đây là **"failed" trên nội dung ĐÚNG**.
Không thể APPROVE tính năng "chạm chi phí thật lần đầu tiên" khi lớp guard tài chính/chất lượng
then chốt nhất chưa từng chạy đúng trên dữ liệu thật.

**Gợi ý hướng sửa** (Dev tự quyết định, không phải chỉ thị bắt buộc theo đúng cách): chuẩn hoá
`existing` về `list[str]` trước khi unpack, vd:

```python
existing = node.get("class") or []
if isinstance(existing, str):
    existing = existing.split()
```

— và nên audit thêm mọi chỗ khác trong module này/`count_bb_vi_pairs()` có giả định `class` luôn là
list (builder HTML) trong khi code chạy trên builder XML, vì đây rất có thể không phải chỗ duy nhất
mắc giả định này. Sau khi sửa, **bắt buộc chạy lại đúng kịch bản live-verify ở trên trên chính file
EPUB thật** (không chỉ test tổng hợp không có `class`) trước khi báo lại Reviewer.

---

## Issues cần sửa (không chặn merge nhưng phải theo dõi)

### 2. Y6 chưa đóng hoàn toàn cho DeepL — `ConnectionException` không bao phủ lỗi 5xx thật từ server

**File**: `src/services/deepl_provider.py`, dòng 81-89 + comment liên quan.

Comment trong code khẳng định: *"`deepl.ConnectionException` gồm cả lỗi kết nối/timeout/5xx"* — đã
tự đọc source `deepl==1.32.0` (`http_client.py:186-197` + `translator.py:_raise_for_status`,
dòng 170-242) để verify claim này và **không đúng**:

- `ConnectionException` **chỉ** được raise ở tầng transport (`http_client.py`) khi **không nhận
  được response nào cả** — `requests.exceptions.ConnectionError`/`Timeout`/`RequestException`
  (DNS fail, refused, timeout truyền tải...).
- Một response **có** status code 5xx thật từ server DeepL (500/502/503...) đi qua
  `_raise_for_status()` (`translator.py`) — hàm này chỉ xử lý cứng một số status code cụ thể
  (400/401/403/404/429/503-với-`downloading_document`), còn lại (kể cả 503 khi không
  `downloading_document`, và MỌI 5xx khác như 500/502) rơi vào nhánh `else` cuối cùng và raise
  **`DeepLException`** thường (`should_retry=True` cho 503, nhưng cờ này **không được** provider
  code đọc) — **không phải** `ConnectionException`.
- Provider code hiện tại: `except deepl.ConnectionException: → ConnectionError (transient)`, rồi
  `except deepl.DeepLException: → TranslationProviderError (permanent)`. Một 502/503 THẬT từ server
  DeepL rơi đúng vào nhánh permanent — **chính xác loại lỗi hạ tầng bình thường mà Y6 được viết ra
  để sửa, không được sửa cho provider này**.

**Vì sao trong phạm vi**: `DeepL` không bị chặn cho EPUB (`_reject_deepl_for_pdf()` chỉ áp dụng khi
`file_type in _PDF_FILE_TYPES`, EPUB không nằm trong danh sách đó — tự đọc `src/api/routes/jobs.py`
dòng 302-315 xác nhận) — nên user có thể chọn DeepL làm provider cho 1 job EPUB ~vài trăm request
tuần tự, và gặp đúng kịch bản Y6 mô tả ("1 lỗi 502 làm job failed") mà CHANGELOG khai là đã đóng cho
"cả 5 provider" — thực tế chỉ đóng cho 4/5.

**Đề xuất**: bắt 5xx thật từ `DeepLException` cụ thể hơn — vd kiểm `exc.http_status_code >= 500`
(field này tồn tại trên `DeepLException`, xác nhận qua `_raise_for_status` truyền `http_status_code=`
cho mọi nhánh) trước khi map, thay vì dựa hoàn toàn vào `ConnectionException`.

### 3. Ngưỡng "≥90%" của guard BR-EPUB-05 bị làm tròn XUỐNG do `int()`, không phải `ceil()`

**File**: `src/core/job_orchestrator.py`, dòng 264: `min_required = max(1, int(len(source_doc.units) * 0.9))`.

`int()` truncate về phía 0, nên với N=384 (sách mẫu thật): `384*0.9=345.6` → `min_required=345` →
guard pass khi `differing>=345`, tức **345/384=89.84%**, thấp hơn 90% yêu cầu. Với N nhỏ hơn lệch
càng nặng — tự tính: N=11 → ngưỡng thực tế chỉ 81.8%; N=2 → 50%. Đây là sai lệch thật so với đặc tả
"≥90%" (Architecture.md 6.20.12 X3), dù nhỏ và không đủ nghiêm trọng để tự nó block release — nhưng
đáng sửa cùng lúc với issue #1 vì cùng 1 hàm, dùng `math.ceil` hoặc so sánh phân số trực tiếp
(`differing * 10 < len(source_doc.units) * 9`) thay vì `int()`.

---

## Điểm đã tự verify ĐÚNG (không chỉ tin lời Dev)

### A. Y6 — retry 5xx cho 4/5 provider (openai/claude/gemini/ollama)

Tự đọc source đã cài (`openai==3.7.0`, `anthropic`, `google-api-core`, `httpx`) để verify từng claim
trong comment code — không suy đoán:

- **OpenAI/Claude**: xác nhận bằng `inspect.getmro()` — `APITimeoutError` là con của
  `APIConnectionError`; thứ tự `except` (Timeout trước Connection trước InternalServerError trước
  APIError) đúng. Đọc trực tiếp `openai/_client.py::_make_status_error()` xác nhận
  `status_code >= 500` → LUÔN `InternalServerError`, không có class 5xx riêng nào khác — claim
  trong comment code ("InternalServerError dùng cho MỌI 5xx không có class riêng") **đúng 100%**.
- **Gemini**: xác nhận `DeadlineExceeded` là con của `ServerError` (qua `GatewayTimeout`) — thứ tự
  bắt `DeadlineExceeded` trước `ServerError` là bắt buộc và đã đúng.
- **Ollama**: xác nhận `httpx.TimeoutException` là con của `httpx.HTTPError` (qua `TransportError`),
  thứ tự bắt đúng; nhánh `status_code >= 500` riêng biệt hợp lý cho REST API không dùng SDK exception.
- **KHÔNG** có provider nào nới `_TRANSIENT_ERRORS` thành bắt hết `Exception` — đúng yêu cầu tránh
  bẫy retry-vô-hạn của E-10 (đã grep xác nhận `src/utils/retry.py` không đổi).
- `deepseek_provider.py` đúng là không cần sửa (kế thừa `OpenAIProvider.translate()` nguyên vẹn).

Riêng **DeepL** không đạt — xem issue #2.

### B. Cost gate EPUB (X5) — công thức đúng, không ước thấp

Tự tính lại công thức trên chính file `Baking with Sourdough - Sara Pitzer.epub` thật (không tin số
trong Architecture.md, tự đo lại bằng script):

```
doc.total_chars = 53.135, len(units) = 384
source_text_chars (theo công thức) = int(53135*1.15) + 384*30 = 72.625
payload JSON thật (id ngắn + inner-HTML, dựng lại đúng chunk plan) = 67.029 ký tự
tỉ lệ ước/thật = 1,083x — CAO HƠN thật, đúng chiều §6.11.6 cho phép (không ước thấp)
```

Khớp code `cost_gate.py::_estimate_epub_translation_cost()` triển khai đúng chữ công thức
Architecture.md 6.20.6 (X5): `int(doc.total_chars * EPUB_INLINE_MARKUP_FACTOR) + len(doc.units) *
EPUB_JSON_ENVELOPE_CHARS_PER_UNIT`. `llm_request_count = sum(len(c.requests) for c in plan)` — tự
verify ra **21** request cho 384 unit (KHÔNG PHẢI 384) — đúng cảnh báo tránh lệch 8,8x. Cũng xác
nhận `estimate_job_cost_v2()` không bị sửa (grep `cost_estimator.py` không đổi) — chỉ đầu vào khác,
đúng nguyên tắc "1 công thức duy nhất" của Architecture.md.

### C. Contract JSON app↔LLM (X4)

`build_epub_batch_prompt()` có đủ 6 điều + đúng 1 ví dụ one-shot (đọc trực tiếp
`prompt_builder.py:409-433`). `parse_epub_batch_response()` xử lý đúng: strip markdown fence, id
str/int đều nhận (ép `str(key)`), value rỗng/không phải string bị coi là thiếu (không default rỗng),
JSON hỏng hoàn toàn → `{}` (mọi id coi như thiếu, đi qua đúng 1 đường xử lý "thiếu" thống nhất).
`_process_epub_chunk()` (`job_orchestrator.py:1737-1778`): id thiếu → gọi lại lẻ đúng 1 vòng (vòng
`for local_id in sorted(missing_ids)`, không đệ quy) → còn thiếu → `EpubBatchTranslationError`,
**không** ghi chuỗi rỗng vào `translations` — khớp đúng E-09/X4 điểm 6.

### D. Golden fixture (X4/Protocol 5 mục 3)

Đọc `tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_5units.json` +
`README.md` — có `input_tokens=1456`, `output_tokens=459`, `estimated_cost_usd=0.00062326` (số lẻ
đặc trưng của phép tính thật, không phải số tròn của Dev tự bịa), `raw_response_text` là 1 chuỗi
JSON DUY NHẤT không format đẹp (khớp cách 1 API thật trả về, không phải JSON Python
`json.dumps(indent=2)` mà Dev tự viết tay sẽ có). Dòng hỗn số `1<sup>1</sup>/<sub>3</sub>` được giữ
đúng (không gộp sai `11/3` — đúng ca N-1 Tech Lead cảnh báo). `tests/test_epub_batch_golden_fixture.py`
chạy `parse_epub_batch_response()` trên CHÍNH `raw_response_text` này — xác nhận qua đọc code, không
phải mock viết tay.

### E. Guard BR-EPUB-05 — logic bảng X3 đúng thiết kế (ngoại trừ bug #1)

`_check_epub_output_guard()` triển khai ĐÚNG 4 điều kiện theo bảng X3 (tổng ký tự>0, số unit khớp,
điều kiện riêng theo `bilingual`), bao gồm điều kiện "KHÔNG THỂ BỎ" — so sánh nội dung cặp
(gốc, bb-vi) khác nhau, không chỉ đếm số node — đúng như Architecture.md nhấn mạnh. `EpubDocument.load()`
bỏ qua subtree `class="bb-vi"` khi liệt kê units (`_in_bb_vi_subtree`) — xác nhận qua đọc code VÀ
qua test thật (`len(guard_doc.units) == len(source_doc.units)` pass trong live-verify ở trên, dù
guard tổng thể fail vì lý do #1). Nếu không có bug #1, thiết kế bảng 4-điều-kiện đúng tinh thần yêu
cầu.

### F. 4 sợi dây data lineage (§6.20.9) — có test R6-02 cụ thể, không chỉ `assert_called()`

Đọc `tests/integration/test_epub_translate_runner.py` (512 dòng, 8 test) xác nhận đủ:
- **(2)→(7) unit_id**: `test_run_epub_job_unit_id_lineage_maps_translation_to_correct_paragraph` —
  dịch 1 unit cụ thể thành marker độc nhất, assert marker nằm ĐÚNG file/vị trí, KHÔNG có ở nơi khác.
- **(6)→(7) resume**: `test_run_epub_job_resume_merges_translations_from_all_completed_chunks` —
  giả lập crash ở chunk 2, resume, assert cả 2 chunk (chunk 1 từ lần chạy trước + chunk 2 lần chạy
  sau) đều có mặt trong output cuối.
- **(2)→(7) doc_href** (X6, đã APPROVE ở Bước 1/3, không phá lại ở Bước 2/3): không có thay đổi nào
  trong diff bước 2/3 chạm tới `EpubDocument.load()`'s `doc_href` construction — grep xác nhận.
- **(4)→(6) system_prompt chứa marker JSON**: `test_run_epub_job_sends_system_prompt_with_json_contract_marker`
  assert `"BB-EPUB-JSON-CONTRACT-X4" in system_prompt` cho MỌI lời gọi thật gửi tới `provider.translate()`.

Riêng fix E2 (glossary lọc theo `full_text`) có test bổ sung
`test_run_epub_job_filters_glossary_by_full_text_matching_cost_gate` — assert 2 lớp (tham số truyền
vào `build_system_prompt()` VÀ nội dung `system_prompt` thật: term xuất hiện trong tài liệu còn lại,
term không xuất hiện bị lọc bỏ) — đúng R6-02, không chỉ tin lời gọi hàm đúng tham số.

### G. BR-EPUB-03 — không double-translation

Grep `run_epub_job()`/`_process_epub_chunk()`: không có `subprocess`/`bilingual_book_maker`/`bbook`
nào trong luồng EPUB. Điểm gọi LLM duy nhất là `pricing_provider.translate()`.

### H. Migration DB (§6.20.11 mục 1, CHỐT)

`src/models/database.py::_migrate_chunks_unit_columns()` + `_add_missing_columns()` là `ALTER TABLE`
thật (rebuild-table pattern cho đổi NOT NULL→nullable, add-column đơn giản cho cột mới), có kiểm tra
idempotent (`PRAGMA table_info` trước khi đổi), giữ dữ liệu cũ (`INSERT INTO ... SELECT`) — đúng
CHỐT "viết migration script, KHÔNG xoá DB" mà PM/user đã quyết.

### I. 3 điểm Dev tự nêu — đánh giá

1. **`only_terms_present_in`/`max_glossary_entries` thêm vào `build_system_prompt()`**: mở rộng an
   toàn, backward-compatible — default `None`/`80` giữ nguyên hành vi cũ cho caller hiện có
   (`overlay_rotated_text`), chỉ EPUB truyền filter mới. Đã tự verify bằng test riêng (mục F) rằng
   filter có tác dụng thật, không chỉ đúng tham số. Đồng ý đây không phải thay đổi kiến trúc ngoài
   thẩm quyền Dev — Dev báo cáo đúng cách (phát hiện premise PM sai, không âm thầm implement theo
   premise đó) đúng tinh thần Protocol 1 mở rộng.
2. **`max_glossary_entries` cap khớp `cost_gate.py`**: hợp lý — nếu không khớp thì đúng loại lệch
   Lớp 2/prompt thật mà E2 vừa sửa xong sẽ tái diễn ở tham số khác.
3. **Guard `td`/`th`**: thiết kế của Dev trong `count_bb_vi_pairs()` (so sánh phần còn lại của ô sau
   khi bỏ `<br/>`+span) đúng tinh thần X3/Y2(b) — nhưng KHÔNG có dữ liệu thật để chạm tới nhánh này
   (file mẫu duy nhất có 0 `<table>`, đúng Z1 đã ghi trong Architecture.md). Không phản đối thiết kế,
   nhưng ghi nhận cùng nhóm rủi ro với issue #1: code path xử lý `class`/`bb-vi` marker CHƯA từng
   chạy đúng trên dữ liệu thật — nên đây cũng là ứng viên cần audit lại sau khi sửa issue #1 (dùng
   `soup.new_tag("span")` nên KHÔNG bị bug #1 trực tiếp, nhưng nên re-test cùng lúc để chắc chắn).

### J. Regression suite — tự chạy độc lập 2+ lần

```
uv run ruff check src/ tests/            → All checks passed! (2 lần)
uv run pytest tests/ -q                  → 671 passed, 0 failed (lần 1, 106.13s)
uv run pytest tests/ -q                  → 671 passed, 0 failed (lần 2, 119.24s)
uv run pytest tests/test_rotated_text_overlay.py -q → 13 passed (chạy riêng, xác nhận không nhiễu)
```

**Không tái hiện được** hiện tượng "3 failed" mà Dev ghi nhận trong CHANGENOG (2 lần) — khớp kết
luận của Dev rằng đó là nhiễu môi trường tạm thời (nhiều session chạy song song), không phải do thay
đổi của US-22 Bước 2/3. Đồng ý với claim (d) trong "3 điểm chưa rõ ràng" — không cần điều tra sâu
hơn.

---

## R5-04 checklist

**External contract verified against real source**:
- Luồng dịch EPUB gọi trực tiếp `provider.translate()` (contract đã verify sống từ Increment 3):
  **N/A** cho phần này, đúng như brief đã định trước.
- Định dạng response JSON của DeepSeek cho batch contract mới (X4): **YES** — golden fixture capture
  từ 1 lần gọi thật (`tests/fixtures/epub_llm/`, README ghi rõ ngày/model/chi phí/input thật), không
  phải mock viết tay. Xem mục D.
- SDK exception hierarchy của 5 provider (Y6): **YES** cho openai/anthropic/google-api-core/httpx —
  tự `inspect.getmro()` + đọc source cài thật trong `.venv`. **NO/sai một phần** cho `deepl` — xem
  issue #2 (Reviewer tự đọc source `deepl==1.32.0`, phát hiện claim trong comment code không khớp
  hành vi SDK thật).

---

## Kết luận US-22 Bước 2/3 — VÒNG 1/3

**REJECT.**

- **1 blocking issue** (mục 1): guard BR-EPUB-05 nhánh `bilingual=True` — mặc định hardcode duy nhất
  hiện có cho EPUB — luôn fail trên dữ liệu thật do lỗi xử lý attribute `class` dưới parser XML
  trong `_mark_bb_vi()`. Live-verify trực tiếp trên file EPUB thật duy nhất của dự án: 0/384 unit
  được guard nhận diện đúng dù đã dịch đầy đủ. Đây là lớp bảo vệ tài chính/chất lượng quan trọng
  nhất của tăng lượng này (PM brief mục 5) — không thể approve khi nó không hoạt động trên dữ liệu
  thật, đặc biệt khi hậu quả là job bị đánh "failed" SAU KHI đã tốn tiền thật cho toàn bộ chunk.
- 2 issue cần sửa cùng đợt (không tự nó blocking nhưng nên gộp vào cùng 1 vòng sửa vì cùng vùng
  code/cùng lớp guard): Y6 chưa đóng cho DeepL (issue #2), ngưỡng 90% bị làm tròn xuống (issue #3).
- Phần còn lại (cost gate X5, contract JSON X4, data lineage R6-02, golden fixture, migration DB, 4/5
  provider Y6, BR-EPUB-03) đều đạt chất lượng tốt, tự verify được bằng số đo/lệnh chạy thật — không
  chỉ đọc tĩnh code hay tin lời khai CHANGELOG.
- Regression suite: 671/671 pass, chạy độc lập 2 lần, không tái hiện nhiễu Dev từng ghi nhận.

**Yêu cầu Dev**: sửa issue #1 (bắt buộc), audit các chỗ khác trong `epub_document.py` có giả định
tương tự về `class` là list, sửa issue #2 và #3, rồi chạy lại CHÍNH kịch bản live-verify guard trên
file EPUB thật (không chỉ test tổng hợp không có `class` attribute) trước khi gửi lại Reviewer.

**Circuit breaker Dev↔Reviewer: 1/3 vòng đã dùng cho US-22 Bước 2/3.**

---

# Review Report — US-22 Dịch EPUB, Bước 2/3: Translation Engine thật + cost-gate — VÒNG 2/3 (Dev↔Reviewer, Protocol 3)

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-09
- **Circuit breaker Dev↔Reviewer (US-22 Bước 2/3)**: **vòng 2/3** — xem ghi chú quan trọng về đánh
  số vòng ngay dưới đây.

## ⚠️ Ghi chú quan trọng — lệch số vòng so với brief PM

Brief PM cho lần review này ghi "vòng 3/3 (VÒNG CUỐI)". Tự kiểm tra lại trước khi review (đọc toàn
bộ `docs/review-report.md` + `docs/CHANGELOG.md`, không tin nguyên văn brief theo đúng tinh thần
"Protocol 1 mở rộng — gắn nhãn verify" của CLAUDE.md) cho thấy: section review gần nhất cho "US-22
Bước 2/3" (ngay phía trên section này) tự ghi rõ **"VÒNG 1/3"** ở cả tiêu đề lẫn dòng kết luận cuối
("Circuit breaker Dev↔Reviewer: 1/3 vòng đã dùng"), và chính CHANGELOG entry mới nhất Dev viết cũng
tự gọi đây là **"vòng 2/3 Dev↔Reviewer... giới hạn cuối là vòng 3/3"** (dòng 6685 + 6830-6831
`docs/CHANGELOG.md`). Không tìm thấy bất kỳ section "VÒNG 2/3" nào khác cho riêng "Bước 2/3" (2 kết
quả `grep "vòng 2/3"` khác chỉ thuộc về US-17+US-18 và US-22 **Bước 1/3** — bước khác, đã APPROVE).

**Kết luận của Reviewer**: đây thực chất là **VÒNG 2/3**, không phải vòng cuối. Review này được ghi
đúng số **VÒNG 2/3** trong tiêu đề — không tự ý dùng số "3/3" mà brief đưa vì không khớp bằng chứng
trong chính 2 file handoff chuẩn (Protocol 1) của dự án. Đề nghị PM xác nhận lại cách đếm trước khi
báo cáo lên circuit breaker, để tránh 2 hệ quả xấu: (a) dừng pipeline oan nếu APPROVE giả sử đây là
vòng cuối trong khi thực ra còn 1 vòng nữa nếu cần, hoặc (b) tính sai nếu REJECT — Dev vẫn còn đúng
1 vòng nữa (vòng 3/3 thật), không phải "hết vòng, phải escalate" như brief ngụ ý.

## Phạm vi review

3 điểm Reviewer REJECT ở vòng 1/3 (guard BR-EPUB-05 `class`, Y6 DeepL 5xx, ngưỡng `int()`→ceil) +
1 phát hiện mới ngoài yêu cầu Dev tự báo cáo (bug JSON "trailing garbage" trong
`parse_epub_batch_response()`, bắt được khi Dev chạy live E2E full-book). Đọc toàn bộ diff (`git
diff` từ HEAD — commit gần nhất `636e046` không liên quan tăng lượng này, nên diff phản ánh đúng
toàn bộ thay đổi chưa commit của cả vòng 1/3 lẫn vòng 2/3 gộp lại), CHANGELOG entry tương ứng, và tự
chạy lại **mọi** kịch bản verify — không tin lại bất kỳ số liệu nào Dev báo cáo.

## 1. Bug chính (issue #1, guard BR-EPUB-05 + lớp bug thứ 2 `count_bb_vi_pairs`) — ĐÃ SỬA, tự verify ĐỘC LẬP

**Xác nhận hành vi gốc của bs4 trước khi tin bất kỳ giải thích nào** (không đọc code rồi suy diễn):

```python
>>> BeautifulSoup('<p class="noindent">x</p>', "xml").find('p').get('class')
'noindent'          # str, KHÔNG PHẢI list — xác nhận độc lập root cause
>>> BeautifulSoup('<p class="noindent bb-vi">x</p>', "xml").find_all(class_='bb-vi')
[]                  # RỖNG — xác nhận độc lập "lớp bug thứ 2" Dev tự phát hiện
>>> BeautifulSoup('<p class="bb-vi">x</p>', "xml").find_all(class_='bb-vi')
[<p class="bb-vi">x</p>]   # 1-class thì khớp — giải thích đúng vì sao 12 test cũ (không có
                            # class gốc) không bắt được bug này
```

Cả 2 claim trong CHANGENOG (lớp 1: unpack chuỗi hỏng attribute; lớp 2: `find_all(class_=...)` của
bs4 không khớp multi-class string dưới builder XML) đều **đúng 100%**, tự verify bằng script riêng,
không phải đọc lại lời Dev.

**Grep xác nhận không còn lời gọi `find_all(class_=...)` sống nào trong module** (chỉ còn trong
docstring giải thích) — mọi điểm đọc/ghi `class` đã quy về `_node_classes()` duy nhất, đúng yêu cầu
"audit thêm mọi chỗ khác" của vòng 1/3.

**Tự chạy lại CHÍNH kịch bản live-verify của vòng 1/3, trên chính file EPUB thật đã dùng lúc REJECT**
(`data/uploads/9d436d7b-...-Sourdough...epub`, KHÔNG dùng lại script cũ của Dev — tự viết script
riêng):

```
units: 384
GUARD PASSED
count_bb_vi_pairs total/differing: 384 384
sample p tag: <p class="noindent bb-vi" lang="vi">
```

`class="noindent bb-vi"` nguyên vẹn (không còn `"n o i n d e n t bb-vi"`), guard PASS đúng nghĩa,
384/384 unit được đếm đúng — bug chính (0/384 lúc REJECT) đã hết, live trên đúng file đã tái hiện
bug ở vòng 1/3.

**Phát hiện thêm (Reviewer, không nằm trong yêu cầu Dev báo cáo)**: dự án thực ra có **file EPUB
thật thứ hai** trong `data/uploads/` — `sample2_Bread-A-Global-History.epub` (8,3MB, mtime 2026-09-08
20:33, tức SAU thời điểm Architecture.md §6.20.11 mục 7 (Z1) ghi "chỉ có đúng 1 file EPUB thật" —
file này rất có thể là kết quả PM đã xin thêm user theo đúng đề nghị Z1, nhưng chưa ai cập nhật lại
ghi chú Z1/round review trước để phản ánh việc này). File này có **12 `<table>`** trong XHTML thật
— đúng loại dữ liệu mà mục "I.3" của vòng 1/3 review ghi nhận là "CHƯA có dữ liệu thật để chạm
nhánh `td`/`th` của `count_bb_vi_pairs()`". Tự chạy lại đúng kịch bản guard trên file NÀY:

```
units: 866   (tag breakdown: {'p': 806, 'td': 36, 'h1': 1, 'h2': 14, 'h3': 9})
GUARD PASSED
count_bb_vi_pairs total/differing: 866 866
```

36 unit thật có `tag == "td"` — xác nhận nhánh `td`/`th` (chèn `<span class="bb-vi">` bên trong ô,
so sánh "bản gốc" bằng cách bỏ `<br/>`+span) **đã thực sự chạy qua dữ liệu thật lần đầu tiên**, không
còn là "phòng thủ lý thuyết chưa kiểm chứng" như ghi nhận ở vòng 1/3 — kết quả đúng (866/866, không
crash, không đếm sai). Đây là tin tốt, không phải blocking mới — nhưng đáng ghi vào non-blocking để
PM biết cập nhật lại Z1/Architecture.md (dữ liệu N=1 đã thành N=2, ít nhất 1 file có bảng thật) và
để QA biết dùng file này cho R6-03 nếu cần phủ thêm nhánh `td`/`th`.

**Kết luận mục 1**: issue #1 (blocking chính của vòng 1/3) **ĐÃ SỬA ĐÚNG**, tự verify độc lập trên cả
2 file EPUB thật hiện có trong dự án, không chỉ tin lại số liệu Dev báo cáo.

## 2. Y6 DeepL — 5xx tách đúng thành transient, không nới quá tay cho 4xx

Tự đọc trực tiếp source `deepl==1.32.0` đã cài (không tin lại comment code, dù comment đúng):

```python
# deepl/exceptions.py — DeepLException.__init__
def __init__(self, message, should_retry=False, http_status_code=None): ...
# ConnectionException KHÔNG set http_status_code (giữ None mặc định) — subclass DeepLException
# nhưng chỉ raise ở tầng transport, xác nhận qua http_client.py
```

```python
# deepl/translator.py::_raise_for_status() — đọc toàn bộ nhánh if/elif
# 403/456(quota)/404(not found, gồm nhánh glossary riêng)/400/429/503 co class rieng;
# 503 khong "downloading_document" -> DeepLException(http_status_code=503, should_retry=True);
# MOI status khac (500, 502, ...) roi vao nhanh `else` cuoi -> DeepLException(http_status_code=<code>)
```

Khớp 100% với comment Dev viết trong `deepl_provider.py`. Đọc code hiện tại (`src/services/
deepl_provider.py` dòng 78-107): thứ tự except **đúng** — `AuthorizationException` →
`TooManyRequestsException` → `ConnectionException` (transient, transport) →
`DeepLException` (fallback, kiểm `http_status_code >= 500` mới transient, còn lại/ `None`
permanent). Vì Python except khớp theo thứ tự viết và mọi exception con đều bắt trước lớp cha
`DeepLException`, không có rủi ro exception cụ thể bị nuốt nhầm bởi nhánh chung.

Grep xác nhận `ConnectionError` nằm trong `_TRANSIENT_ERRORS` của `src/utils/retry.py` (dòng 17) —
fix này thực sự kích hoạt retry, không chỉ đổi tên exception suông.

3 test mới (`test_deepl_translate_5xx_is_transient`, `_4xx_stays_permanent`,
`_exception_without_status_code_stays_permanent`) — đọc trực tiếp, đúng 3 nhánh cần phủ (5xx / 4xx
giữ permanent / `http_status_code=None` không crash `None >= 500`). **Đạt.**

## 3. Ngưỡng ≥90% — `math.ceil()` đúng, tự tính tay ca biên

`min_required = max(1, math.ceil(len(source_doc.units) * 0.9))`. Tự tính tay, không tin lại:

- N=384 (Sourdough thật): `384*0.9=345.6` → `ceil=346` → `346/384=90.104...%` ✅ ≥90% thật sự (so
  với `int()` cũ: 345/384=89.84%, SAI — đúng bug đã ghi nhận vòng 1/3).
- N=866 (Bread-A-Global-History): `866*0.9=779.4` → `ceil=780` → `780/866=90.069...%` ✅.
- N=11 (ca biên vòng 1/3 nêu): `11*0.9=9.9` → `ceil=10` → `10/11=90.9%` ✅ (so với `int()` cũ:
  9/11=81.8%, sai nặng hơn).
- N=1: `max(1, ceil(0.9))=max(1,1)=1` → 1/1=100% — vẫn đúng biên dưới (không chia cho 0, không âm).

Test mới `test_check_epub_output_guard_threshold_uses_ceil_not_truncate` dùng đúng 345/384 unit thật
của Sourdough (biên chính xác mà `int()` cũ sẽ PASS sai) — assert guard RAISE đúng ở ngưỡng mới.
**Đạt.**

## 4. Bug MỚI — JSON "trailing garbage" (`parse_epub_batch_response()`) — đánh giá kỹ theo yêu cầu PM (rủi ro tài chính)

**Câu hỏi PM đặt ra**: cách sửa (phục hồi phần JSON hợp lệ trước vị trí lỗi khi `msg == "Extra
data"`) có mở lỗ hổng nào không — cụ thể có thể "phục hồi nhầm" 1 JSON thực sự hỏng/bị cắt cụt
thành có vẻ hợp lệ nhưng THIẾU DỮ LIỆU hay không?

**Tự verify bằng thực nghiệm trực tiếp trên `json` module chuẩn** (không suy đoán):

```python
json.loads('{"0": "abc"}"')            # Extra data tại pos=12, text[:12] = '{"0": "abc"}' (ĐỦ, hợp lệ)
json.loads('{"0": "abc"}')[:-1]... # (thiếu dấu đóng)  -> "Expecting ',' delimiter", KHÔNG PHẢI "Extra data"
json.loads('{"0": "abc')             # (cắt cụt giữa string) -> "Unterminated string", KHÔNG PHẢI "Extra data"
json.loads('{"0": "abc"} extra prose') # Extra data tại pos=13, text[:13] vẫn là JSON hợp lệ đầy đủ
json.loads('{"0":"abc"}{"1":"def"}')  # Extra data — chỉ phục hồi được OBJECT ĐẦU, object thứ 2 mất
```

**Kết luận: an toàn, không mở lỗ hổng.** Cơ chế `json.JSONDecodeError` của Python module chuẩn chỉ
raise `msg == "Extra data"` khi decoder đã **parse xong hoàn chỉnh, hợp lệ 1 giá trị JSON top-level**
tại vị trí `[0:exc.pos)`, RỒI MỚI gặp thêm ký tự thừa sau đó — đây là tính chất nội tại của thuật
toán decode (parse trước, phát hiện "extra" sau), không phải giả định của Dev. Một JSON thực sự
CẮT CỤT/thiếu (do hết `max_tokens`, mất kết nối giữa chừng...) KHÔNG BAO GIỜ hoàn tất parse một giá
trị top-level trước khi hết chuỗi — nó luôn dừng ở lỗi khác ("Expecting ',' delimiter",
"Unterminated string", "Expecting value", "Expecting ':' delimiter"...), các lỗi này **không** khớp
`msg == "Extra data"` nên rơi thẳng vào nhánh `else: return {}` cũ, không bị nới lỏng. Trường hợp
biên duy nhất đáng chú ý (2 object JSON hợp lệ dính liền nhau) chỉ phục hồi được object ĐẦU — object
thứ 2 bị mất hoàn toàn, nhưng hệ quả là các id trong đó bị coi "thiếu" và đi qua đúng đường xử lý
"thiếu → retry lẻ" sẵn có (X4) — không phải "âm thầm chấp nhận dữ liệu sai/thiếu mà không ai biết",
tương đương hệt như nếu response đó bị coi hỏng hoàn toàn.

Đọc code (`src/core/prompt_builder.py::parse_epub_batch_response()`) khớp đúng phân tích trên:
except cụ thể `exc.msg == "Extra data" and exc.pos > 0`, thử `json.loads(text[:exc.pos])`, nếu BẢN
THÂN phần đó cũng lỗi (`except (JSONDecodeError, TypeError)`) mới trả `{}` — không có nhánh nào khác
nới lỏng.

**Golden fixture** (`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_trailing_garbage.json`
+ README): đọc trực tiếp — `raw_response_text` capture từ 1 lần gọi DeepSeek thật (chi phí
`estimated_cost_usd=0.00045232`, khớp Protocol 5 mục 3, không phải chuỗi viết tay), tự chạy
`json.loads()` thô trên đúng chuỗi này xác nhận **thật sự fail** với `"Extra data"` — không phải
fixture đã bị "dọn sạch" trước khi lưu (test `test_raw_response_text_is_genuinely_malformed_before_parser_fix`
xác nhận đúng tiền đề này). 3 test bổ sung (`test_epub_batch_prompt.py`) phủ thêm ca tổng hợp: 1 ký
tự thừa, prose thừa nhiều id, và JSON cắt cụt THẬT SỰ vẫn phải trả `{}` — đọc trực tiếp xác nhận ca
cắt cụt vẫn đúng hành vi cũ, không bị nới.

**Kết luận mục 4: fix an toàn, không mở lỗ hổng tài chính mới, đủ chặt cho đúng 1 dạng lỗi cụ thể đã
quan sát được, golden fixture đúng chuẩn Protocol 5.**

## 5. Live E2E full-book Dev tự báo cáo (`actual_cost=0.07637542`, 384/384, `status=completed`)

**Không tìm thấy bằng chứng nào lưu lại** cho lần chạy này:

- `data/bb_translation.db` (đường dẫn DB thật của app, xác nhận qua `.env`/`config.py` —
  KHÔNG PHẢI `data/outputs/bb_translation.db`, 1 file rỗng gây nhầm lẫn nằm cạnh đó) chỉ có **10
  job, toàn bộ `file_type='pdf_digital'`, không có job EPUB nào** — job gần nhất `2026-09-09
  05:54:27`. Không có bản ghi nào khớp cost `0.07637542`.
- `data/outputs/` không có file `.epub` nào (`find` xác nhận).
- Không có test nào trong suite gọi API thật cho `run_epub_job()` full-book (toàn bộ
  `tests/integration/test_epub_translate_runner.py` dùng `_FakeEpubProvider`, không mạng thật).

Nói cách khác: claim `actual_cost=$0.07637542`/384-384/`completed` **chỉ tồn tại dưới dạng text
trong CHANGENOG**, không có artifact nào để đối chiếu trực tiếp — đúng loại rủi ro mà PM yêu cầu
đánh giá kỹ ("đọc kỹ log/test Dev để lại và đánh giá độ tin cậy").

**Không thể tái hiện chính xác con số đó** (Dev không giữ lại file/DB), nên thay vào đó Reviewer tự
chạy 1 live E2E ĐỘC LẬP của riêng mình — quy mô nhỏ hơn nhiều (1 EPUB tự dựng, 2 unit, có sẵn
`class="noindent"` để re-test đúng bug chính, ~0,03 cent USD) — qua ĐÚNG `JobOrchestrator.run_epub_job()`
thật, provider DeepSeek thật, KHÔNG mock, DB/thư mục riêng (không đụng dữ liệu thật của app):

```
JobResult(status='completed', actual_cost=0.00030734, error_message=None)
job.total_units: 2
output OEBPS/chap0.xhtml:
  <p class="noindent">Preheat the oven to 450F.</p>
  <p class="noindent bb-vi" lang="vi">Làm nóng lò ở 230°C.</p>
  <p class="noindent">Mix <strong>2 cups</strong> flour with 1<sup>1</sup>/<sub>3</sub> tsp salt.</p>
  <p class="noindent bb-vi" lang="vi">Trộn <strong>240g</strong> bột mì với 1<sup>1</sup>/<sub>3</sub> tsp muối.</p>
```

Xác nhận: `class="noindent bb-vi"` nguyên vẹn (bug chính không tái phát trên pipeline ĐẦY ĐỦ, không
chỉ script cô lập ở mục 1), `job.status='completed'` với chi phí thật > 0, nội dung tiếng Việt THẬT
(không phải "VI:" giả — DeepSeek còn tự quy đổi đơn vị 450F→230°C, 2 cups→240g, đúng tinh thần
"unit conversion fallback" mô tả trong Architecture.md), số `1<sup>1</sup>/<sub>3</sub>` giữ nguyên
không gộp sai.

**Đánh giá độ tin cậy claim gốc của Dev**: không thể xác nhận CHÍNH XÁC con số `$0.07637542`/384 unit
Dev báo cáo (không còn artifact), nhưng **cơ chế mà claim đó mô tả (toàn bộ pipeline `run_epub_job()`
chạy thật, real cost, real Vietnamese, guard PASS) đã được Reviewer tự chứng minh là THẬT SỰ hoạt
động đúng**, độc lập, trên đúng code path — không chỉ tin lại lời khai. Coi đây là **corroborated
bằng cơ chế, không corroborated bằng con số cụ thể** — ghi vào non-blocking, đề nghị QA (R6-03: bắt
buộc ≥1 live E2E full-chain trước release, kiểm nội dung thật không chỉ status) tự chạy lại full-book
1 lần nữa trước khi duyệt release, và Dev/PM nên giữ lại artifact (job DB thật hoặc ít nhất output
file) cho lần chạy "live E2E" tiếp theo thay vì để trôi mất — không phải vì nghi ngờ Dev nói dối, mà
vì 1 claim tài chính quan trọng không nên chỉ tồn tại dưới dạng text không thể kiểm chứng lại.

## 6. Regression — tự chạy độc lập 2+ lần

```
uv run ruff check src/ tests/     → All checks passed! (đúng, chạy riêng)
uv run pytest tests/ -q           → 682 passed, 0 failed  (lần 1, 90.90s)
uv run pytest tests/ -q           → 682 passed, 0 failed  (lần 2, 90.70s, độc lập hoàn toàn)
uv run pytest tests/test_rotated_text_overlay.py -q → 13 passed (chạy CÔ LẬP riêng, không nhiễu)
```

682 = 671 (baseline vòng 1/3, Reviewer tự xác nhận) + 11 test mới — khớp đúng con số Dev báo cáo.
**Xác nhận: `test_rotated_text_overlay.py` KHÔNG còn fail** (Dev báo "hết cả fail cũ", tự verify độc
lập 2 lần suite đầy đủ + 1 lần chạy cô lập riêng file này — không phải hiện tượng tạm thời biến mất,
vì đã lặp lại đủ số lần để loại trừ flake môi trường).

## R5-04 checklist

**External contract verified against real source**:
- `deepl_provider.py` (nhánh 5xx mới, mục 2 ở trên): **YES** — Reviewer tự đọc trực tiếp source
  `deepl==1.32.0` đã cài trong `.venv` (`exceptions.py`, `translator.py::_raise_for_status`), không
  chỉ tin lại comment code Dev viết (dù comment khớp 100% với source thật).
- `parse_epub_batch_response()` (mục 4): **N/A cho phần "external SDK contract"** (đây là app tự
  parse JSON, không gọi SDK bên thứ 3) nhưng **YES cho phần "Extra data luôn đi kèm JSON hợp lệ đã
  parse xong"** — verify bằng thực nghiệm trực tiếp `json` module chuẩn của Python (stdlib, không
  phải "external tool" theo nghĩa Protocol 5, nhưng vẫn tự chạy thử thay vì suy đoán).
- Golden fixture trailing-garbage: **YES** — response thật từ DeepSeek, Protocol 5 mục 3, chi phí
  thật > 0 là bằng chứng.

## Non-blocking suggestions

1. **Cập nhật Architecture.md §6.20.11 mục 7 (Z1)**: ghi "chỉ có đúng 1 file EPUB thật" đã STALE —
   `data/uploads/sample2_Bread-A-Global-History.epub` (866 unit, có bảng thật, mtime SAU ngày ghi
   Z1) đã có sẵn trong dự án và đã tự verify hoạt động đúng ở mục 1 trên. Nên chính thức đưa vào làm
   fixture thường trực (test/golden fixture) thay vì chỉ nằm im trong `data/uploads/`.
2. **Giữ lại artifact cho live E2E tài chính quan trọng**: xem mục 5 — đề nghị 1 quy ước nhỏ (không
   cần Architecture.md, chỉ là thói quen làm việc): mọi lần chạy `run_epub_job()`/`run_job()` thật
   để verify 1 fix quan trọng nên giữ lại output file + note job id trong DB thật (hoặc chụp lại
   trước khi dọn), để Reviewer/QA vòng sau đối chiếu được số liệu chính xác, không chỉ tin text.
3. **3 điểm "chưa rõ ràng" Dev nêu ở entry CHANGELOG vòng 1/3** (E2/E3 mâu thuẫn nội bộ glossary lọc,
   thiết kế `td`/`th` guard, Y4 thiếu WS broadcast riêng) — đã được Reviewer vòng 1/3 đánh giá đồng ý
   (mục I, "Điểm đã tự verify ĐÚNG"), không cần lặp lại ở vòng này; ghi chú lại đây chỉ để PM biết
   những điểm này vẫn còn là quyết định mở (đặc biệt điểm 2 — nay đã có dữ liệu thật để kiểm chứng
   thiết kế `td`/`th`, xem mục 1 ở trên, kết quả ĐÚNG).

## Kết luận US-22 Bước 2/3 — VÒNG 2/3

**APPROVE.**

- **3 điểm blocking/cần sửa của vòng 1/3 đều đã sửa đúng**, tự verify độc lập (không tin lại lời
  Dev) bằng: đọc trực tiếp source bs4 4.15.0 + `deepl` 1.32.0 đã cài, tự viết script live-verify
  riêng chạy trên CẢ 2 file EPUB thật hiện có trong dự án (bao gồm 1 file trước đây bị bỏ sót, có
  bảng thật — xác nhận thêm nhánh `td`/`th` trước đây "chưa kiểm chứng" nay đã đúng trên dữ liệu
  thật), tính tay ca biên ngưỡng 90%.
- **Bug MỚI Dev tự phát hiện (JSON trailing garbage)** — đánh giá kỹ theo đúng yêu cầu PM (rủi ro
  tài chính): fix AN TOÀN, verify bằng thực nghiệm trực tiếp cơ chế `JSONDecodeError` của Python,
  không có đường nào "phục hồi nhầm" JSON thực sự thiếu/cắt cụt thành dữ liệu giả hợp lệ. Golden
  fixture đúng chuẩn Protocol 5 mục 3.
- **Live E2E full-book Dev báo cáo**: không còn artifact để đối chiếu con số chính xác — Reviewer tự
  chạy 1 live E2E độc lập (quy mô nhỏ, chi phí thật ~0,03 cent) qua đúng `run_epub_job()` để xác nhận
  CƠ CHẾ hoạt động đúng thật sự (không chỉ tin lời khai) — ghi non-blocking để QA re-run full-book
  trước release theo đúng R6-03, và đề nghị PM/Dev giữ artifact cho các lần verify tài chính sau này.
- Regression: 682/682 pass, chạy độc lập 2 lần đầy đủ + 1 lần cô lập riêng `test_rotated_text_overlay.py`
  — xác nhận hết fail cũ, không phải hiện tượng tạm thời.

**⚠️ Về đếm vòng (xem ghi chú đầu section)**: Reviewer đánh giá đây là **VÒNG 2/3 thật sự** (không
phải vòng 3/3 như brief PM ghi), dựa trên bằng chứng trực tiếp từ chính 2 file handoff chuẩn của dự
án (`review-report.md` section trước tự ghi "VÒNG 1/3", `CHANGELOG.md` entry Dev tự ghi "vòng 2/3").
Vì kết quả là **APPROVE**, sự khác biệt về số vòng ở đây không dẫn tới hệ quả xấu ngay lập tức (không
cần escalate dù đếm theo cách nào) — nhưng đề nghị PM xác nhận lại cách đếm trước khi cập nhật
`project_state.json`/báo cáo circuit breaker, để tránh lệch số cho các tăng lượng sau.

**Circuit breaker Dev↔Reviewer: 2/3 vòng đã dùng cho US-22 Bước 2/3 (theo cách đếm của Reviewer) —
KHÔNG PHẢI 3/3.**

---

# Review Report — Fix Bug #EPUB-B2-1 + #EPUB-4 (US-22 Bước 2/3, sau QA vòng 1/5) — VÒNG 1/3

**Ngày**: 2026-09-09. **Reviewer**: agent Reviewer (spawn riêng, R7-01). **Phạm vi**: toàn bộ
`git diff` chưa commit tại thời điểm review — `src/core/chunking.py`, `src/core/cost_estimator.py`,
`src/core/cost_gate.py`, `src/core/job_orchestrator.py`, `src/core/prompt_builder.py`,
`src/core/text_quality.py` (mới), và 4 file test mới/sửa. Đối chiếu với spec
`docs/Architecture.md` §6.20.13.0 → .10.

## Kết luận: APPROVE

Không phát hiện lệch spec, không phát hiện bug blocking mới. Mọi hằng số, mọi comment
`⚠️ ASSUMED`, mọi off-by-one boundary đều khớp đúng con số Tech Lead cho. Test mới assert giá trị
cụ thể (không phải test rỗng kiểu `assert_called()`), 32/32 test liên quan pass, `705 passed` cho
toàn bộ suite (khớp đúng số Dev báo cáo trong CHANGELOG), `ruff check` sạch. Có 5 finding
non-blocking bên dưới — không finding nào đủ nghiêm trọng để REJECT, nhưng finding #1 nên được
Tech Lead cân nhắc cho vòng sau vì đúng tinh thần Protocol 6.

## 1. Đối chiếu spec vs code THẬT (mục 1 brief)

Đọc trực tiếp diff, so từng con số:

| Hằng số | Spec (Architecture.md) | Code thật | Khớp? |
|---|---|---|---|
| `EPUB_MAX_SINGLE_ID_RETRIES` | 5 | `chunking.py` = 5 | ✅ |
| `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE` | 6 | `chunking.py` = 6 | ✅ |
| `EPUB_RUNAWAY_OUTPUT_FACTOR` | 3.0 | `cost_estimator.py` = 3.0 | ✅ |
| `EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS` | 1500 | `cost_estimator.py` = 1_500 | ✅ |
| `EPUB_DIACRITIC_MIN_LETTERS_REQUEST` | 200 | `text_quality.py` = 200 | ✅ |
| `EPUB_DIACRITIC_RATIO_REQUEST` | 0.08 | `text_quality.py` = 0.08 | ✅ |
| `EPUB_DIACRITIC_MIN_LETTERS_UNIT` | 40 | `text_quality.py` = 40 | ✅ |
| `EPUB_DIACRITIC_RATIO_UNIT` | 0.02 | `text_quality.py` = 0.02 | ✅ |

Mọi comment `⚠️ ASSUMED` được giữ nguyên tại chỗ khai báo hằng số (`chunking.py`,
`cost_estimator.py`, `text_quality.py`) kèm trích dẫn đúng section Architecture.md — không bị Dev
tự tóm tắt lại hay bỏ bớt cảnh báo "chưa đo". `EpubChunkCostCapExceeded`/`EpubRequestRunawayError`
đặt cạnh `EpubBatchTranslationError` đúng vị trí spec yêu cầu (mục 6.20.13.8).

## 2. Data lineage (Protocol 6 R6-04) — trọng tâm chính của brief

Tự trace bằng tay `_process_epub_chunk()` (`job_orchestrator.py:1848` trở đi):

- **Cộng cost đúng 1 lần**: mọi lời gọi `pricing_provider.translate()` (request chính, retry-đơn-
  lẻ qua `_retry_single_unit()`, retry-nguyên-request qua `_retry_whole_epub_request()`) đều đi qua
  đúng 1 điểm cộng dồn duy nhất — closure `_accumulate_and_check_budget()` (dòng ~1888). Không có
  đường nào cộng `total_cost`/`total_input_tokens`/`total_output_tokens` ngoài closure này — xác
  nhận không double-count, không thiếu count.
- **R-a (runaway nhưng giữ kết quả)**: cost của request đó đã được cộng vào `total_cost` TRƯỚC khi
  kiểm tra runaway (dòng 1888 gọi trước dòng tính `runaway`), nên dù giữ hay bỏ kết quả, cost vẫn
  đã nằm trong `total_cost` đúng 1 lần — khớp đúng ý spec "tiền đã tiêu rồi, giữ kết quả".
- **Retry mất dấu không cộng đôi cho cùng 1 unit**: unit vừa thiếu id (xử lý ở nhánh
  `missing_ids`) vừa mất dấu (tầng 2) — 2 lần gọi `_retry_single_unit()` là 2 request API THẬT
  KHÁC NHAU (1 lần cho thiếu-id, 1 lần cho mất-dấu, xảy ra tuần tự, xác nhận bằng
  `test_low_diacritic_unit_tier_retried_and_resolved`), nên cộng cost 2 lần là ĐÚNG (2 lần gọi
  thật = 2 lần tốn tiền thật), không phải bug cộng đôi.
- **Merge tầng 1 (diacritic request-level) không làm sai lệch nội dung units khác**: `retry_parsed`
  chỉ ghi đè đúng những id THẬT SỰ có trong response retry (`for retried_id, retried_val in
  retry_parsed.items(): parsed[retried_id] = retried_val`), không ghi đè toàn bộ `parsed` — đúng ý
  "không đổi lấy thứ tệ hơn" cho id không nằm trong response retry.

## 3. Tương tác Lớp 3 / Lớp 4 (mục 3 brief)

`effective_cap` tính đúng 1 lần/vòng lặp chunk (dòng ~915), dùng LẠI cho cả Lớp 4 (trước khi xử lý
chunk) và Lớp 3 (sau khi xử lý chunk) — không viết công thức trần thứ hai, đúng yêu cầu spec.
`EpubChunkCostCapExceeded` được bắt RIÊNG, TRƯỚC khối `except Exception` chung (dòng 971) — không
lẫn vào nhánh `failed` chung. Khi Lớp 4 trigger, đi đúng nhánh `cost_capped` đã có sẵn (dòng
938-970): `job.status="cost_capped"`, `chunk.status="failed"`, `chunk.api_cost` khác 0,
`chunk.output_path=None` — không bịa trạng thái mới, không đổi UI. Test
`test_layer4_stops_mid_first_chunk_and_persists_partial_cost` và test sửa lại trong
`test_epub_translate_runner.py` (đổi tên từ `..._mid_book_...` sang `..._via_layer4_mid_first_chunk`)
assert đúng các field này — xác nhận không phải test bị làm yếu đi để che regression, mà là hành vi
mới có chủ đích (Lớp 3's "vượt trần tối đa để lọt" giảm từ 1 chunk xuống 1 request), đúng như
Dev giải thích trong CHANGELOG.

## 4. Trần retry — edge case (mục 4 brief)

Kiểm tra boundary `len(missing_ids) <= EPUB_MAX_SINGLE_ID_RETRIES` (5): đúng 5 → nhánh per-id (giữ
nguyên pattern cũ); đúng 6 → nhánh nguyên-request. Test
`test_more_than_max_single_id_retries_uses_one_whole_request_retry` dùng 6 unit thiếu hết (6 > 5)
và assert đúng 2 lần gọi (không phải 1+6). Không có off-by-one. `extra_requests` là biến cục bộ
khai báo lại mỗi vòng `for start, end in chunk_plan.requests:` (dòng ~1878) — đúng phạm vi "trần
cho TOÀN BỘ 1 slice", không rò rỉ sang slice khác.

## 5. Guard mất dấu — false positive risk (mục 5 brief)

`diacritic_ratio()` (`text_quality.py`) đúng công thức spec: `strip_html_for_measure()` bỏ tag +
mọi thuộc tính trước, `unicodedata.normalize("NFC", ...)` trước khi đếm (đúng bẫy NFD được cảnh báo
trong Architecture.md), mẫu số chỉ đếm `ch.isalpha()` — loại đúng số/dấu câu/khoảng trắng khỏi mẫu
số như spec yêu cầu. Có test biên `test_diacritic_ratio_english_heavy_unit_stays_above_thresholds`
dùng đoạn văn tiếng Việt hợp lệ giàu thuật ngữ Anh (`sourdough starter`, `450F`) và assert ratio
vẫn vượt cả 2 ngưỡng — đúng loại case PM lo ngại false-positive, ĐÃ có, không phải gap.

## 6. Chất lượng test mới (mục 6 brief)

Không có test rỗng kiểu `assert_called()`. Mọi test trong `test_epub_translate_guards.py` dùng
`_ControllableEpubProvider` kiểm soát chính xác nội dung/`output_tokens` từng lần gọi và assert
`len(provider.calls)` cụ thể (1, 2, hoặc 3 tuỳ kịch bản) — đây chính là kiểu assert "giá trị cụ
thể" mà Protocol 6 R6-02 yêu cầu, không phải chỉ `assert_awaited()`. Test sửa trong
`test_epub_translate_runner.py` (đổi tên + đổi assertion) đã verify là thay đổi có chủ đích (xem
mục 3 trên) bằng cách đọc diff before/after — không phải sửa để che regression.

**Finding non-blocking #4**: docstring của test đã sửa (`test_epub_translate_runner.py` dòng
~483-486) tham chiếu tới 1 test tên
`test_run_epub_job_stops_at_cost_capped_via_layer3_between_chunks` như "xem test X ở dưới cho kịch
bản Lớp 3" — **test này KHÔNG TỒN TẠI** ở bất kỳ đâu trong repo (đã grep toàn bộ
`tests/integration/`). Docstring cũng tự giải thích ngay sau đó là "không viết thêm test này vì
kịch bản không còn đạt được" — nghĩa là bản thân đoạn tham chiếu là dấu vết còn sót lại từ 1 ý định
ban đầu đã bị bỏ, gây hiểu lầm cho người đọc sau. Đề nghị Dev xoá cụm "xem
`test_run_epub_job_stops_at_cost_capped_via_layer3_between_chunks` ở dưới" khỏi docstring ở vòng
sửa tiếp theo (không cần round riêng, gộp vào lần sửa kế tiếp cũng được — không block).

## 7. Fix cost_gate.py — C-2 (mục 7 brief)

Xác nhận bằng đọc code: `_estimate_epub_translation_cost()` (`cost_gate.py`) giờ gọi
`build_epub_batch_prompt(base_system_prompt)` thật (`base_system_prompt` từ `build_system_prompt()`
thật, KHÔNG phải đổi tên biến suông) — `real_prompt = build_epub_batch_prompt(base_system_prompt)`,
`prompt_overhead_chars = len(real_prompt)`. Có 2 test mới xác nhận: (a)
`test_estimate_epub_translation_cost_prompt_overhead_matches_real_runtime_prompt` — assert BẰNG
NHAU với chuỗi thật `_process_epub_chunk()` nhận, đúng Protocol 6 R6-02 "assert giá trị cụ thể"; (b)
`test_estimate_epub_translation_cost_overhead_higher_than_old_pdf_formula` — assert số MỚI CAO HƠN
số CŨ (`build_prompt_text()` công thức PDF cũ), đúng ý regression-guard chống quay lại ước thấp.
Cả 2 test PASS thật (đã tự chạy, không chỉ tin báo cáo Dev).

## 8. R5-04 checklist (mục 8 brief)

- `src/core/text_quality.py`: **N/A** — thuần Python, không gọi external tool/network nào.
- `src/core/cost_estimator.py` (`is_runaway_output`/`epub_expected_output_tokens`): **N/A** —
  công thức nội bộ dùng lại hằng số đã có, không gọi external tool.
- `src/core/job_orchestrator.py` (`_process_epub_chunk()` — nơi gọi thật `pricing_provider.translate()`):
  **External contract verified against real source: NO — chỉ verify theo Architecture.md.** Dev tự
  báo cáo trong CHANGENLOG là KHÔNG chạy live E2E thật (chỉ chạy `pytest`/`ruff`), có ghi rõ lý do
  ("brief cho phép tuỳ chọn"). Đây đúng là gap cần QA đóng ở vòng sau — QA **bắt buộc** phải chạy
  R5-03/R6-03 sống (live full-book) trước khi đánh dấu `ready_for_release`, đúng gate G-1/G-2/G-3/G-4
  đã liệt kê tại Architecture.md §6.20.13.10. Ghi nhận là **non-blocking cho vòng Reviewer này**
  (Dev không có nghĩa vụ tự chạy live E2E theo brief PM cho phép), nhưng escalate rõ cho QA vòng sau
  không được bỏ qua.

## 9. Finding khác phát hiện thêm khi tự trace (ngoài checklist brief, đáng chú ý cho Tech Lead)

**Finding non-blocking #1 (quan trọng nhất, nên đọc)** — mất dấu vết tài chính ở đường abort KHÔNG
phải Lớp 4: khi `EpubRequestRunawayError` (R-b) hoặc `EpubBatchTranslationError` (E-09, đường
`still_missing` đã có từ trước) raise, exception này rơi vào khối `except Exception` CHUNG
(`job_orchestrator.py:971-992`, không đổi bởi diff này) — khối đó CHỈ set
`chunk.status="failed"`/`chunk.error_message`/`chunk.retry_count`, **KHÔNG** set
`chunk.api_tokens_used`/`chunk.api_cost`. So sánh với đường Lớp 4
(`EpubChunkCostCapExceeded`, dòng 1888-1906) — đường đó CÓ ghi `chunk.api_cost`/`api_tokens_used`
TRƯỚC khi raise, đúng yêu cầu tường minh của spec 6.20.13.2. Nhưng spec KHÔNG có yêu cầu tương tự
cho R-b — nên tiền THẬT đã tiêu cho request runaway (và bất kỳ retry nào chạy trước khi phát hiện
`still_missing`) bị "biến mất" khỏi `chunk.api_cost`/`job.actual_cost` khi job fail theo đường này.
Xác nhận bằng test: `test_runaway_rb_aborted_when_missing_ids` chỉ assert `result.status ==
"failed"` và nội dung `error_message`, KHÔNG assert `chunk.api_cost` — vì code thật không set field
đó nên không có gì để assert. **Đây là hành vi ĐÃ CÓ TỪ TRƯỚC** (giống hệt cách E-09 hoạt động từ
trước fix này) — không phải regression Dev gây ra, và spec Tech Lead không yêu cầu Dev sửa nó ở
đợt này. Nhưng đáng escalate cho §6.20.13 vòng sau vì đúng tinh thần Protocol 6: các guard MỚI này
(nhất là runaway) làm tăng khả năng 1 chunk fail SAU KHI đã tốn nhiều tiền hơn bình thường (chính
là kịch bản R-b được thiết kế để bắt) — càng dễ xảy ra tình huống "tiền mất, dấu vết không còn" nếu
không mở rộng persist money sang cả đường `except Exception` chung, không chỉ riêng Lớp 4.

**Finding non-blocking #2** — retry không được chạy qua `is_runaway_output()`: `is_runaway_output()`
chỉ được gọi cho request CHÍNH của mỗi slice (dòng ngay sau request đầu tiên), KHÔNG được gọi lại
cho kết quả của `_retry_single_unit()`/`_retry_whole_epub_request()`. Spec 6.20.13.3b không yêu cầu
tường minh áp dụng cho retry, nên không phải lệch spec — nhưng nghĩa là 1 lần retry (kể cả retry
nguyên request tốn tiền tương đương request gốc) tự nó vẫn có thể runaway mà không bị bắt lần 2.
Rủi ro thấp (retry đã có trần `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE`, và Lớp 4 vẫn chặn được nếu vượt
ngân sách) — ghi nhận để Tech Lead cân nhắc, không block.

**Finding non-blocking #3** — `requests.jsonl` chỉ ghi request CHÍNH của mỗi slice (biến
`request_log` chỉ append 1 lần/vòng `for start, end`), KHÔNG ghi các lần retry (per-id,
nguyên-request, tầng 1/tầng 2 mất dấu). Spec 6.20.13.7 viết "1 dòng ... cho **mọi** request (kể cả
bình thường)" — cách đọc chặt của câu này có thể hiểu là mọi LỜI GỌI LLM (kể cả retry), không chỉ
request chính. Nếu QA vòng sau dùng `requests.jsonl` để tính "max output-ratio quan sát được" cho
gate G-2 (§6.20.13.10), số liệu sẽ THIẾU các lần retry — có thể làm ngưỡng `EPUB_RUNAWAY_OUTPUT_FACTOR`
trông an toàn hơn thực tế nếu retry cũng có xu hướng runaway. Đề nghị Tech Lead làm rõ ý "mọi
request" ở vòng sau; không block vì cách đọc hiện tại của Dev (chỉ request chính) cũng là 1 cách
đọc hợp lý của câu spec.

**Finding non-blocking #5** — hiệu quả review: đã tự chạy `uv run pytest tests/ -q` (toàn bộ suite,
không chỉ test liên quan EPUB) → `705 passed`, khớp đúng số Dev báo cáo trong CHANGELOG (baseline
682 + 23 test mới). Đã tự chạy `uv run ruff check` trên toàn bộ file đổi/thêm → `All checks passed!`.
Không chỉ tin báo cáo tự khai của Dev.

## Checklist R5-04 (tổng hợp, đặt cuối theo format bắt buộc)

- `src/core/text_quality.py`: N/A
- `src/core/cost_estimator.py` (`is_runaway_output`, `epub_expected_output_tokens`): N/A
- `src/core/job_orchestrator.py` (`_process_epub_chunk()`, gọi `pricing_provider.translate()`):
  NO — chỉ verify theo Architecture.md, chưa có live E2E. Non-blocking cho Reviewer, **bắt buộc**
  cho QA (R5-03/R6-03) trước `ready_for_release`.

## Vòng lặp

**Circuit breaker Dev↔Reviewer: 1/3 vòng đã dùng cho đợt fix Bug #EPUB-B2-1 + #EPUB-4 này (round
riêng, không cộng dồn với vòng đếm cũ ở section trên — đây là fix mới sau QA vòng 1/5 của Bước
2/3).**

---

# Review Report — Fix Bug #EPUB-B2-3 (parse multi-JSON, US-22 Bước 2/3) — VÒNG 1/3

**Ngày**: 2026-09-10. **Phạm vi**: fix `parse_epub_batch_response()`/`_decode_concatenated_json_objects()`
mới (`src/core/prompt_builder.py`) cho Bug #EPUB-B2-3 (QA vòng 2/5 phát hiện, mô tả tại
`docs/test-report.md` grep "Bug #EPUB-B2-3") — DeepSeek đôi khi trả nhiều object JSON top-level rời
rạc nối tiếp thay vì 1 object gộp, code cũ chỉ giữ object đầu và vứt bỏ toàn bộ id còn lại. Vòng
review này tách riêng khỏi vòng Dev↔Reviewer đã APPROVE trước đó cho Bug #EPUB-B2-1/#EPUB-4 (Protocol 3
— circuit breaker đếm riêng, xem mục "Vòng lặp" cuối report).

Đã đọc: `docs/test-report.md` (mô tả bug gốc, root cause, đề xuất fix QA đã kiểm chứng hướng đi), 2
entry mới nhất `docs/CHANGELOG.md` (lượt 1: sửa logic parse + fixture "partial capture" tạm thời;
lượt 2: capture golden fixture đầy đủ qua 1 lần gọi API thật đã được PM duyệt, thay thế hoàn toàn
fixture partial), toàn bộ `git diff` (đặc biệt `src/core/prompt_builder.py`,
`tests/test_epub_batch_prompt.py`, `tests/test_epub_batch_golden_fixture.py`), và nội dung 2 file
fixture JSON liên quan.

## 1. Logic merge nhiều JSON object

**Vòng lặp `_decode_concatenated_json_objects()` (`src/core/prompt_builder.py:539-565`)**: dùng
`json.JSONDecoder().raw_decode(text, pos)`, cập nhật `pos = end` sau mỗi lần thành công, có bước
skip whitespace trước mỗi lần decode, và `break` ngay khi `JSONDecodeError` hoặc hết chuỗi. Đã tự
trace bằng tay:
- **Không có vòng lặp vô hạn**: mỗi vòng lặp thành công đều tăng `pos` (vì `raw_decode` luôn trả
  `end > pos` cho 1 JSON value hợp lệ không rỗng — không có input nào khiến `end == pos`), và vòng
  lặp thất bại thì `break` ngay — không có đường nào quay lại `pos` cũ mà không thoát.
- **Không off-by-one**: `raw_decode` trả `end` là index NGAY SAU ký tự cuối của value vừa parse
  (hành vi chuẩn của `json.JSONDecoder.raw_decode`, đã tự kiểm bằng script Python độc lập — xem mục
  golden fixture bên dưới), gán thẳng `pos = end` không cộng/trừ gì thêm → đúng.
- **Ca cũ (1 dấu `"` thừa) đi qua đúng con đường TỔNG QUÁT, không phải nhánh riêng còn sót**: đã tự
  chạy script Python tách `raw_decode` trên `deepseek_batch_response_sourdough_ch1_trailing_garbage.json`
  thực tế — object đầu decode thành công tại `pos=0`, `end=1098`; phần còn lại `text[1098:]` là
  đúng 1 ký tự `"` duy nhất — `raw_decode` tại vị trí đó raise `JSONDecodeError` (unterminated
  string, vì `"` là token mở chuỗi JSON hợp lệ nhưng không có dấu đóng) → loop dừng, giữ đúng object
  đầu, khớp 100% hành vi cũ. **Xác nhận: đây là N=1 của vòng lặp tổng quát, không phải nhánh đặc biệt
  còn sót** — code không còn dòng nào riêng cho case "Extra data" cũ, đã bị thay thế hoàn toàn.
- **Key trùng — object sau thắng**: `merged.update(obj)` gọi tuần tự theo thứ tự xuất hiện trong
  text (vòng `while` đi từ đầu tới cuối chuỗi) → dict.update() ghi đè giá trị cũ bằng giá trị mới
  mỗi lần gặp key trùng, tức object xuất hiện SAU trong text thắng — đúng quyết định ghi trong
  CHANGENLOG. Có test xác nhận đúng chiều
  (`test_parse_multi_object_later_object_wins_on_duplicate_key`,
  `tests/test_epub_batch_prompt.py`): input `'{"0": "ban dich cu"}\n{"0": "ban dich moi hon"}'` →
  assert kết quả là `"ban dich moi hon"` (object SAU) — không phải object đầu thắng nhầm.
- **Rác thật ở cuối — dừng và giữ phần đã parse, không crash**: `except json.JSONDecodeError: break`
  bắt đúng loại exception `raw_decode` raise khi gặp rác không phải JSON, không có `raise` nào lan ra
  ngoài hàm. Đúng tinh thần docstring gốc ("dung sai có chủ đích... không nới lỏng để chấp nhận rác
  thật thành dữ liệu giả") — rác bị bỏ qua/dropped, không bị "đoán" thành nội dung, và phần ĐÃ parse
  trước đó vẫn được giữ nguyên trong `merged`. Test `test_parse_multi_object_stops_at_genuine_garbage_but_keeps_earlier_objects`
  xác nhận đúng: 2 object hợp lệ + rác `"day la rac khong phai JSON @@@"` ở cuối → giữ đúng 2 object,
  không crash.
- **Giá trị JSON hợp lệ nhưng không phải dict** (số/list) lạc giữa 2 object dict: `isinstance(obj,
  dict)` chặn đúng, không update merged nhưng vẫn `pos = end` để tiếp tục vòng lặp — không làm mất
  các object dict hợp lệ SAU nó. Test `test_parse_multi_object_non_dict_object_among_valid_ones_is_skipped`
  xác nhận đúng.

**Không tìm thấy edge case bị bỏ sót** trong logic merge. Một điểm đáng lưu ý nhưng KHÔNG blocking:
nếu object thứ N decode được nhưng KHÔNG phải dict (vd 1 số nguyên), hàm vẫn tính `found_any = True`
— nghĩa là nếu TOÀN BỘ input chỉ là 1 giá trị non-dict duy nhất (vd input là `"42"`), hàm trả về
`{}` đúng (vì `merged` rỗng) chứ không phải crash — hành vi này khớp đúng docstring "Non-dict
top-level values are skipped ... same as the old 'not a dict' check", đã tự verify bằng cách đọc lại
code cũ (`isinstance(data, dict)` check trước khi refactor) — tương đương, không phải regression.

## 2. Golden fixture mới — đánh giá độ tin cậy

Đã tự đọc toàn bộ nội dung `tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_multi_json_object.json`
(không chỉ tin lời Dev khai trong CHANGELOG):

- **Cấu trúc khớp đúng mô tả bug gốc**: `unit_ids_in_order` là 11 unit liên tiếp
  `ops/xhtml/chapter01.html#36`..`#46`, trong đó `unit_ids_in_order[1] ==
  "ops/xhtml/chapter01.html#37"` — khớp CHÍNH XÁC ví dụ QA đã trích trong `docs/test-report.md` khi
  báo cáo Bug #EPUB-B2-3 ban đầu.
- **`raw_response_text` thật sự fail `json.loads()` với "Extra data"**: tự chạy độc lập
  `json.loads(fixture["raw_response_text"])` → raise đúng `json.JSONDecodeError: Extra data` tại vị
  trí ngay sau object đầu tiên (khớp claim trong fixture `"json_decode_error_before_fix": "Extra
  data at pos 802"` — tự verify lại bằng Python, không tin số Dev ghi sẵn trong file).
- **Dấu hiệu đây LÀ dữ liệu thật, không phải Dev tự viết tay cho "đẹp"**:
  - Nội dung tiếng Anh trong `request_payload` (11 đoạn) đọc như văn bản thật trích từ 1 cuốn sách
    nấu ăn về sourdough (chi tiết cụ thể: "gamblers... sweeten the pot", "Alabama summer", "styrofoam
    picnic chest", "80°F... 95°F") — không phải câu ví dụ khô khan kiểu test tự bịa.
  - Bản dịch tiếng Việt có văn phong TỰ NHIÊN của LLM dịch thật: đôi chỗ hơi dịch sát nghĩa đen
    ("làm ngọt nồi" cho "sweeten the pot", "những tay cờ bạc miền tây" cho "old-time western
    gamblers") — đúng kiểu output LLM dịch nghĩa đen 1 idiom tiếng Anh, không phải câu tiếng Việt
    được người viết tay chỉnh cho mượt.
  - Escape `\"` bên trong `raw_response_text` khớp đúng vị trí có `<a id=\"page_7\"/>` — tức JSON
    string chứa HTML có thuộc tính `id="..."` đã được escape đúng chuẩn JSON, không phải chuỗi được
    Dev gõ tay (dễ quên escape hoặc escape sai nếu viết thủ công).
  - Có `input_tokens=1994`, `output_tokens=1279`, `estimated_cost_usd=0.00128282` — con số cụ thể,
    không tròn, khớp đúng dạng response thật từ API (không phải placeholder tròn số).
  - **KHÔNG có dấu hiệu "quá sạch"/thiếu tính ngẫu nhiên**: độ dài 11 đoạn không đều nhau (từ 1 câu
    ngắn "Rules for Success" tới đoạn dài về incubator), văn phong lặp lại tự nhiên của 1 tác giả
    (nhiều câu bắt đầu bằng "Use..."/"Choose..."/"Make sure...") — khớp đúng văn phong sách hướng
    dẫn nấu ăn thật, không phải câu mẫu do AI/Dev tự tạo cho test.
- **Đối chiếu số lần gọi ghi trong CHANGENLOG (`input_tokens=1994/output_tokens=1279/
  estimated_cost_usd=0.00128282`, "tái hiện thành công ngay lần đầu, 1/5 attempt")**: nhất quán nội
  bộ giữa fixture JSON và nội dung CHANGELOG — không phát hiện mâu thuẫn.

**Kết luận mục 2**: fixture này ĐÁNG TIN — đủ điều kiện coi là golden fixture thật theo đúng nghĩa
Protocol 5 mục 3 (không phải mock viết tay theo giả định). Đây là đánh giá độc lập của Reviewer, không
chỉ dựa trên lời khai của Dev trong CHANGELOG.

## 3. Test coverage

Đủ cả 5 case yêu cầu, không có test rỗng/tự xác nhận giả định của chính nó:

| Case | Test | File |
|---|---|---|
| (a) golden fixture thật, 2+ object | `test_parse_recovers_all_ids_from_multiple_concatenated_json_objects`, `test_parse_multi_json_object_keeps_genuinely_real_content` | `test_epub_batch_golden_fixture.py` |
| (b) fixture cũ (1 dấu `"` thừa) vẫn PASS | 4 test cũ không sửa (`test_parse_recovers_single_trailing_character_after_valid_json` và 3 test khác, xác nhận trong CHANGELOG) — đã tự chạy lại, PASS | `test_epub_batch_prompt.py`/`test_epub_batch_golden_fixture.py` |
| (c) key trùng | `test_parse_multi_object_later_object_wins_on_duplicate_key` | `test_epub_batch_prompt.py` |
| (d) rác thật ở cuối | `test_parse_multi_object_stops_at_genuine_garbage_but_keeps_earlier_objects` | `test_epub_batch_prompt.py` |
| (e) rác hoàn toàn không parse được | `test_parse_genuinely_truncated_json_still_returns_empty_dict` (test cũ, vẫn PASS, không sửa) | `test_epub_batch_prompt.py` |

Thêm: `test_parse_merges_many_single_key_objects_like_real_bug_shape` (11 object riêng, đúng hình
dạng cụ thể QA quan sát — không chỉ 2 object), `test_parse_multi_object_non_dict_object_among_valid_ones_is_skipped`
(giá trị JSON hợp lệ không phải dict lạc giữa 2 object), `test_multi_json_object_fixture_file_exists_and_was_a_real_call`
(tự xác nhận fixture fail đúng kiểu "Extra data" — không phải chuỗi đã được "làm sạch" trước).

Không phát hiện test nào assert sai thứ cần assert. Mỗi test đều assert GIÁ TRỊ CỤ THỂ (không chỉ
`assert result is not None` kiểu hời hợt).

## 4. Không có regression ở nơi gọi

Đọc `parse_epub_batch_response()` (`src/core/prompt_builder.py:520-536`): `_decode_concatenated_json_objects()`
được gọi NGAY TỪ ĐẦU cho MỌI response (không chỉ khi bắt được `JSONDecodeError`), thay hẳn khối
`try/except` cũ. Đây là thay đổi hợp lý vì bản thân hàm mới tự xử lý toàn bộ phổ input (1 object hợp
lệ, N object, rác) bằng 1 con đường duy nhất — không phải "gọi sai chỗ", mà là đơn giản hoá đúng
đắn: trường hợp phổ biến nhất (đúng 1 object hợp lệ, không có gì theo sau) đi qua vòng lặp đúng 1
lần rồi dừng ở điều kiện `pos >= length`, `merged` chính là kết quả `json.loads()` thường sẽ trả về
— hành vi giữ nguyên tuyệt đối, đã tự verify bằng cách đọc toàn bộ test suite cũ liên quan (test
"case bình thường 1 object" trong `test_epub_batch_prompt.py` không bị sửa, vẫn PASS).

## 5. Checklist R5-04

`src/core/prompt_builder.py::parse_epub_batch_response()`/`_decode_concatenated_json_objects()` —
**external contract verified against real source: YES** (Reviewer tự xác nhận, không chỉ tin lời
Dev) — nguồn: (1) tự đọc toàn bộ nội dung golden fixture
`deepseek_batch_response_sourdough_ch1_multi_json_object.json` và đánh giá độc lập tính xác thực ở
mục 2 trên; (2) tự chạy `json.loads()`/`json.JSONDecoder().raw_decode()` độc lập bằng script Python
trên cả 2 fixture (mới + cũ) để verify hành vi parser thật (không suy đoán từ tài liệu); (3) hành vi
`raw_decode` (trả `end` = index ngay sau value, raise `JSONDecodeError` khi gặp token không hợp lệ)
là hành vi chuẩn của thư viện `json` built-in CPython — đã tự verify bằng cách chạy trực tiếp, không
dựa trí nhớ.

## Kết quả chạy độc lập (không tin số Dev báo)

```
uv run pytest tests/ -q        → 714 passed, 0 failed  (958 warnings, không liên quan tới thay đổi này —
                                   warnings có sẵn từ trước, thuộc test khác: test_pdf2zh_runner.py,
                                   test_progress_tracker.py, không phải do fix Bug #EPUB-B2-3 gây ra)
uv run ruff check src/ tests/  → All checks passed!
```
Khớp đúng số Dev báo trong CHANGENLOG (714 passed).

## Vấn đề khác quan sát được (non-blocking)

**Finding non-blocking #1**: docstring trong `parse_epub_batch_response()` (dòng ~499) còn nhắc tên
file fixture cũ `deepseek_batch_response_sourdough_ch1_trailing_garbage.json` — đúng, không phải lỗi
(fixture đó vẫn tồn tại, không bị xoá, chỉ có fixture "partial_capture" mới bị xoá và thay bằng bản
đầy đủ). Không có vấn đề.

**Finding non-blocking #2**: `tests/fixtures/epub_llm/README.md` — đã grep xác nhận có mục "CẬP NHẬT
2026-09-10" append vào cuối, không ghi đè lịch sử cũ (đúng R7-03). Không có vấn đề.

**Finding non-blocking #3**: `src/core/text_quality.py`, `tests/test_text_quality.py`,
`tests/test_epub_cost_gate.py`, `tests/test_epub_runaway_guard.py`,
`tests/integration/test_epub_translate_guards.py` (untracked) và thay đổi ở `src/core/chunking.py`,
`src/core/cost_estimator.py`, `src/core/cost_gate.py`, `src/core/job_orchestrator.py` nằm NGOÀI phạm
vi bug #EPUB-B2-3 (đây là các guard khác — runaway output, mất dấu — CHANGELOG Dev tự xác nhận
"Không động tới guard runaway (C-3) hay guard mất dấu... cả 2 không liên quan tới bug này"). Reviewer
**KHÔNG review các phần này trong report này** — nằm ngoài brief PM giao cho vòng review này (chỉ
Bug #EPUB-B2-3). Nếu các thay đổi đó là code MỚI/CHƯA qua Reviewer riêng, cần 1 vòng review riêng
trước khi coi là "xong" (Protocol 7 R7-01) — PM cần xác nhận có đúng vậy không.

## Kết luận

**APPROVE** cho fix Bug #EPUB-B2-3 (`_decode_concatenated_json_objects()` + golden fixture đầy đủ +
test mới trong `src/core/prompt_builder.py`, `tests/test_epub_batch_prompt.py`,
`tests/test_epub_batch_golden_fixture.py`, `tests/fixtures/epub_llm/README.md`,
`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_multi_json_object.json`). Không tìm
thấy issue blocking. Golden fixture đáng tin, verify độc lập bằng 2 cách (đọc nội dung + tự chạy
script). Không phát hiện regression cho case 1-object phổ biến nhất, không phát hiện edge case bị bỏ
sót trong vòng lặp merge.

**Lưu ý phạm vi**: APPROVE này CHỈ áp dụng cho Bug #EPUB-B2-3 (`src/core/prompt_builder.py` +
2 file test liên quan + fixture). KHÔNG bao gồm các thay đổi khác trong working tree hiện tại
(`text_quality.py`, `cost_gate.py`, `cost_estimator.py`, `chunking.py`, `job_orchestrator.py` và
test tương ứng) — các phần đó thuộc phạm vi khác, cần Reviewer xác nhận riêng nếu chưa qua review.

## Vòng lặp

**Circuit breaker Dev↔Reviewer cho Bug #EPUB-B2-3: 1/3 vòng đã dùng — VÒNG 1/3 này APPROVE ngay,
không cần vòng 2.** Đây là vòng đếm RIÊNG, không cộng dồn với vòng đếm của Bug #EPUB-B2-1/#EPUB-4 đã
APPROVE trước đó (xem section phía trên).

---

# Review Report — Fix tổng quát Bug #EPUB-B2-4 (parse JSON multi-separator, US-22 Bước 2/3) — VÒNG 1/3

**Phạm vi review**: `src/core/prompt_builder.py` (hàm `_decode_concatenated_json_objects()` viết
lại tổng quát + docstring liên quan), `tests/test_epub_batch_golden_fixture.py` (6 test mới, xem
diff), `tests/fixtures/epub_llm/deepseek_batch_response_sourdough_comma_separated_json_objects.json`
(fixture mới), `tests/fixtures/epub_llm/README.md` (append). Đây là vòng review RIÊNG cho Bug
#EPUB-B2-4 (biến thể phân cách "dấu phẩy" phát hiện ở QA vòng 3/5, khác Bug #EPUB-B2-3 đã APPROVE
ở section trên) — Circuit breaker Dev↔Reviewer đếm riêng cho bug này.

## 1. Thuật toán có thật sự tổng quát, hay chỉ vá hẹp trên danh nghĩa

Đọc trực tiếp `_decode_concatenated_json_objects()` sau fix (`src/core/prompt_builder.py`, khoảng
dòng 552-593). Xác nhận:

- **KHÔNG còn bất kỳ danh sách ký tự phân cách liệt kê cứng nào** (không có
  `if char in (' ', ',', '\n')` hay tương đương). Sau mỗi `decoder.raw_decode(text, pos)` thành
  công, code tìm vị trí `{`/`[` tiếp theo bằng
  `_NEXT_JSON_VALUE_START_RE = re.compile(r"[{\[]")` và `match.start()`, KHÔNG quan tâm nội dung gì
  nằm giữa 2 object (whitespace, dấu phẩy, hay ký tự nào khác) — đây đúng là "tìm điểm mở JSON tiếp
  theo, bỏ qua mọi thứ ở giữa vô điều kiện" như brief PM yêu cầu xác nhận, không phải liệt kê ký tự
  hợp lệ.
- Vòng lặp `while pos < length: ... raw_decode ... search next '{'/'[' ...` là tổng quát cho N object
  bất kỳ (N=1, 2, hay 32), không có logic đặc biệt hoá cho số lượng cụ thể.
- Đánh giá: **thật sự tổng quát**, không phải vá hẹp có tên "tổng quát".

## 2. Tự verify độc lập claim "test ký tự lạ tự pass không cần sửa thêm"

Đọc 2 test mới trong diff (`test_parse_handles_never_before_seen_separator_without_further_code_changes`
dùng `;`, và `test_parse_handles_mixed_whitespace_separator_without_further_code_changes` dùng
`"   \t\n"`). Nhận xét:

- Test dùng `;` **thật sự mới** — đã `grep -n ";"` toàn bộ `src/core/prompt_builder.py` và
  `grep -rn "';'"` toàn bộ `tests/`, `src/`: không có chỗ nào khác xử lý hay test riêng ký tự `;`
  làm phân cách JSON. Không phải Dev "cheat" chọn ký tự đã ngầm hỗ trợ sẵn.
- Test dùng whitespace hỗn hợp (`"   \t\n"`) **KHÔNG phải bằng chứng mạnh cho tính tổng quát** — bản
  thân whitespace-skip đã là hành vi có từ fix Bug #EPUB-B2-3 trước đó (bước "chỉ lần đầu tiên, cho
  phép whitespace dẫn đầu" + việc `raw_decode` tự bỏ qua whitespace giữa các token là hành vi chuẩn
  của `json` built-in). Test này là 1 regression check hợp lệ nhưng KHÔNG chứng minh gì mới về tính
  tổng quát — tên hàm test hơi gây hiểu nhầm (implies "chưa từng gặp" nhưng whitespace luôn đã hoạt
  động). Non-blocking, không đủ nghiêm trọng để reject.
- **Tự viết thêm 3 test độc lập** (không dùng lại bất kỳ ký tự nào Dev đã test) ngoài phiên review,
  chạy trực tiếp qua `parse_epub_batch_response()` thật (không mock):
  - Phân cách `" -- "` (chuỗi, không phải 1 ký tự đơn): `{"0": "Xin chao"} -- {"1": "Tam biet"}` →
    `{'0': 'Xin chao', '1': 'Tam biet'}` — ĐÚNG, đủ cả 2 id.
  - Phân cách `"|"`: `{"0": "A"}|{"1": "B"}` → `{'0': 'A', '1': 'B'}` — ĐÚNG.
  - Cả 2 pass mà không cần sửa bất kỳ dòng code nào — xác nhận độc lập claim của Dev, không chỉ tin
    lại 2 test Dev viết.

## 3. Giới hạn dừng an toàn — không rơi vào vòng lặp vô hạn / không đoán bừa vào rác

Đọc kỹ nhánh dừng: `match is None: break` (hết `{`/`[`) và `except json.JSONDecodeError: break`
(decode tại vị trí tìm được vẫn fail) — cả 2 đều `break` ra khỏi `while`, không có đường quay lại tìm
`{` xa hơn. Tự dựng 3 case biên độc lập, chạy trực tiếp:

- `'{"0": "A"} some text with a { stray brace not json {1,2,3} more junk {"1": "B"}'` (nhiều dấu `{`
  rải rác trong rác, có 1 object hợp lệ thật `id "1"` nằm SAU rác) → kết quả `{'0': 'A'}` — dừng
  đúng tại dấu `{` rác ĐẦU TIÊN không parse được, **không cố nhảy tiếp qua rác để tìm object hợp lệ
  xa hơn**, không raise exception, không đoán/dựng dữ liệu sai. Đây là đánh đổi thiết kế có chủ đích
  (chấp nhận mất id "1" hợp lệ nằm sau rác, đổi lấy an toàn tuyệt đối không decode nhầm) — đúng tinh
  thần "dừng lại NGAY" đã ghi trong docstring, PM/Tech Lead nên biết đánh đổi này (non-blocking, ghi
  nhận làm known limitation chứ không phải bug).
- Chuỗi có object hợp lệ + hàng nghìn dấu `{` rác liên tiếp (`5000` lần `' { '`) để kiểm tra hiệu
  năng/không treo: chạy xong trong `< 1ms`, không lặp vô hạn, dừng đúng ngay tại dấu `{` rác đầu
  tiên sau object hợp lệ.
- Kết luận: **an toàn**, không có nguy cơ vòng lặp vô hạn hay "nhảy nhầm" vào rác giữa văn bản để cố
  decode sai.

## 4. Golden fixture mới

`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_comma_separated_json_objects.json` — đã
tự đọc toàn bộ nội dung (không tin mô tả CHANGELOG):

- `raw_response_text` chứa đúng 32 object nối bằng `}, {` (dấu phẩy + khoảng trắng), id `"0"`..`"31"`
  — khớp mô tả bug (32 id) trong `docs/test-report.md`.
- Kết thúc bằng `..."}}` — đúng có 1 dấu `}` thừa ở cuối như Dev mô tả (trailing garbage kèm theo).
- Tự chạy `json.loads(raw_response_text)` độc lập → raise đúng `JSONDecodeError: Extra data` — xác
  nhận đây thật sự là case mà JSON chuẩn không parse được thẳng, không phải fixture đã "làm sạch"
  trước.
- **Giới hạn đã biết, Dev tự khai báo trung thực**: fixture thiếu `request_payload`/
  `unit_ids_in_order` đầy đủ vì lấy lại từ file log chẩn đoán tạm (`scratchpad/qa_round3/
  diagnostic_calls.jsonl`, không nằm trong repo nên Reviewer KHÔNG thể tự trace ngược lại
  `call_no: 17` để xác nhận nguồn gốc tuyệt đối 100%). Đây là giới hạn thực tế (log tạm không commit)
  chứ không phải dấu hiệu fixture viết tay — nội dung `raw_response_text` tự nó nhất quán nội tại
  (32 id thật, format lỗi thật khớp mô tả bug, chi phí token đã phát sinh thật từ trước) và
  `expected_ids` suy trực tiếp từ chính response, đúng tinh thần Protocol 5 R5-01. Non-blocking,
  ghi nhận minh bạch thay vì block vì lý do ngoài tầm kiểm soát của Dev (log tạm đã bị dọn/không
  còn truy cập được ở phiên review này).

## 5. Regression — chạy lại độc lập, không tin số Dev báo

```
uv run pytest tests/ -q       → 720 passed, 0 failed
uv run ruff check src/ tests/ → All checks passed!
```

Khớp đúng số Dev báo trong CHANGELOG (720 passed = 714 baseline + 6 test mới). Không phát hiện
regression cho các case cũ (newline B2-3, 1 dấu `"` thừa gốc, key trùng, rác thật, leading-prose,
truncated JSON) — tất cả nằm trong 720 passed, không có test nào bị skip/xfail mới.

## 6. R5-04 — Checklist tường minh

`parse_epub_batch_response()` / `_decode_concatenated_json_objects()` (`src/core/prompt_builder.py`)
là code parse response của 1 external LLM provider (DeepSeek) — thuộc phạm vi Protocol 5.

**External contract verified against real source: YES** — nguồn: (1) golden fixture là
`raw_response_text` capture THẬT từ 1 lần gọi API DeepSeek thật đã phát sinh chi phí thật (không
viết tay theo giả định); (2) tự đọc + tự `json.loads()` độc lập nội dung fixture để xác nhận hình
dạng lỗi thật (`Extra data`), không tin mô tả suông; (3) hành vi `json.JSONDecoder().raw_decode()`
(trả về `(obj, end)`, raise `JSONDecodeError` khi token không hợp lệ, tự bỏ qua whitespace giữa
token) là hành vi chuẩn tài liệu hoá của thư viện `json` built-in CPython — đã tự verify bằng cách
chạy trực tiếp trong phiên review này (không dựa trí nhớ). Giới hạn duy nhất: không tự trace được
ngược `call_no: 17` trong log chẩn đoán gốc (file không còn trong repo/scratchpad truy cập được) —
đã ghi rõ ở mục 4, không đủ để hạ xuống NO vì nội dung fixture tự nhất quán và khớp mọi mô tả bug độc
lập kiểm chứng được.

## Vấn đề khác quan sát được (non-blocking)

**Finding non-blocking #1**: `test_parse_handles_mixed_whitespace_separator_without_further_code_changes`
đặt tên ngụ ý "ký tự chưa từng gặp" nhưng whitespace đã được hỗ trợ từ fix B2-3 trước — không sai,
chỉ hơi gây hiểu nhầm về mức độ "bằng chứng mới". Đề xuất đổi tên hoặc thêm comment làm rõ đây là
regression check, không phải bằng chứng tổng quát hoá (bằng chứng thật nằm ở test dùng `;`).

**Finding non-blocking #2**: Case "rác chứa `{` rải rác trước 1 object hợp lệ nằm sau" (mục 3) sẽ
làm mất id hợp lệ nằm sau rác — đây là đánh đổi thiết kế hợp lý (an toàn hơn là cố gắng phục hồi),
nhưng nên ghi rõ 1 dòng trong Architecture.md hoặc docstring làm known limitation tường minh (hiện
docstring có nhắc "dừng lại NGAY" nhưng chưa nêu rõ hệ quả cụ thể "id hợp lệ nằm sau rác sẽ bị mất
vĩnh viễn, không retry lại được vì đã coi là 'không trong expected_ids còn thiếu'" — thực ra vẫn
retry được vì đây là id nằm trong `expected_ids - returned.keys()`, cơ chế retry theo id đơn lẻ ở
Architecture.md 6.20.8 vẫn cứu được — ghi chú thêm 1 dòng để người đọc sau không nhầm là mất vĩnh
viễn).

**Finding non-blocking #3**: Fixture mới thiếu `request_payload`/`unit_ids_in_order` do log tạm
không còn truy cập được (mục 4) — không blocking nhưng nên rút kinh nghiệm quy trình: log chẩn đoán
dùng làm nguồn fixture cho Protocol 5 nên được copy vào `tests/fixtures/epub_llm/` (raw, chưa xử lý)
NGAY khi phát hiện bug, thay vì để trong `scratchpad/` dễ bị dọn trước khi Dev kịp dùng.

## Kết luận

**APPROVE** cho fix tổng quát Bug #EPUB-B2-4 (`_decode_concatenated_json_objects()` trong
`src/core/prompt_builder.py`, 6 test mới trong `tests/test_epub_batch_golden_fixture.py`, fixture
`deepseek_batch_response_sourdough_comma_separated_json_objects.json`, `tests/fixtures/epub_llm/
README.md`).

**Đánh giá tính tổng quát (trọng tâm review này)**: thuật toán mới KHÔNG còn liệt kê ký tự phân cách
cụ thể — tìm điểm mở `{`/`[` tiếp theo và bỏ qua vô điều kiện mọi thứ ở giữa. Đã tự verify độc lập
bằng 2 ký tự phân cách hoàn toàn mới Reviewer tự nghĩ ra (`" -- "`, `"|"`), không dùng lại ký tự Dev
đã test — cả 2 pass ngay không cần sửa code. Đồng thời đã tự kiểm tra giới hạn dừng an toàn (không
vòng lặp vô hạn, không đoán bừa vào rác) bằng 2 case biên tự dựng. **Tự tin thuật toán này đã tổng
quát thật, không chỉ tổng quát trên danh nghĩa** — rủi ro gặp biến thể phân cách thứ 3 làm QA vòng
5/5 fail lại là THẤP, vì thuật toán không còn phụ thuộc vào việc liệt kê đúng hết mọi ký tự phân
cách có thể xảy ra.

**Rủi ro còn lại (không phải do thuật toán parse)**: nếu QA vòng 5/5 vẫn fail, nhiều khả năng đến từ
1 trong 2 hướng KHÁC bug họ B2-3/B2-4: (a) DeepSeek trả về 1 dạng lỗi hoàn toàn khác không phải "nhiều
JSON value rời rạc" (ví dụ JSON lồng sai cấu trúc, mismatched brace bên trong 1 object thay vì giữa
các object — nằm ngoài phạm vi hàm này), hoặc (b) 1 trong các guard KHÁC ngoài phạm vi review này
(`text_quality.py`, `cost_gate.py`, runaway guard...) — các phần này KHÔNG thuộc phạm vi review vòng
này, cần xác nhận riêng đã qua Reviewer trước khi coi QA vòng 5/5 là an toàn toàn diện.

**Không có issue blocking.**

## Vòng lặp

**Circuit breaker Dev↔Reviewer cho Bug #EPUB-B2-4: 1/3 vòng đã dùng — VÒNG 1/3 này APPROVE ngay,
không cần vòng 2.** Vòng đếm RIÊNG cho bug này, không cộng dồn với B2-1/#EPUB-4 hay B2-3.

---

# Review Report — Chiến lược mới 3 lớp (§6.20.14) sau khi chạm giới hạn Protocol 3 — US-22 Bước 2/3 — VÒNG 1/3

**Ngày**: 2026-09-10. **Reviewer**: agent Reviewer (spawn riêng, R7-01). **Phạm vi**: toàn bộ `git
diff` chưa commit tại thời điểm review (`src/core/chunking.py`, `src/core/config.py`,
`src/core/cost_estimator.py`, `src/core/cost_gate.py`, `src/core/job_orchestrator.py`,
`src/core/prompt_builder.py`, `src/services/epub_document.py`, `src/api/routes/jobs.py`, và toàn
bộ test mới/sửa) đối chiếu `docs/Architecture.md` §6.20.14 (đọc toàn bộ .0 → .9 trước khi review),
`docs/CHANGELOG.md` (entry "Chiến lược MỚI ... Lớp A + B + C"), `tests/fixtures/epub_llm/README.md`.

## Kết luận: APPROVE

Không phát hiện lệch spec §6.20.14. Đã tự chạy lại độc lập toàn bộ test suite và tự chạy parser
trên cả 5 golden fixture (không tin số Dev báo) — mọi con số khớp đúng claim của Dev. Có 1 finding
**quan trọng, đã lặp lại từ vòng review trước (B2-1/#EPUB-4) và vẫn CHƯA được sửa** (mục 2 dưới) —
không đủ để REJECT vòng này (spec §6.20.14 không yêu cầu Dev sửa nó ở đợt này, và đây là hành vi kế
thừa chứ không phải regression mới), nhưng **phải escalate rõ cho Tech Lead vì diff này vừa thêm 1
điểm raise MỚI mắc đúng lỗi cũ** — xem mục 2. Ngoài ra 4 finding non-blocking nhỏ hơn.

### Kết quả chạy lại độc lập

```
uv run pytest tests/ -q   → 744 passed, 968 warnings in 115.06s   (khớp đúng số Dev báo: 744)
uv run ruff check src/ tests/   → All checks passed!
```

## 1. Lớp B — verify độc lập claim "32/32 id" cho fixture B2-5 (mục 1 brief)

Tự viết script gọi trực tiếp `parse_epub_batch_response_detailed()` trên **cả 5** golden fixture
(đọc thẳng `raw_response_text`/`expected_ids` từ file JSON, không tin lại số Dev báo trong
CHANGELOG):

| Fixture | expected | got | strict | salvaged |
|---|---|---|---|---|
| `ch1_5units` | 5 | 5 | 5 | 0 |
| `ch1_trailing_garbage` | 1 | 1 | 1 | 0 |
| `ch1_multi_json_object` (B2-3) | 11 | 11 | 11 | 0 |
| `comma_separated_json_objects` (B2-4) | 32 | 32 | 32 | 0 |
| `single_object_spurious_closing_braces` (B2-5) | 32 | **32** | 1 | **31** |

Xác nhận đúng 2 claim của Dev: (a) **zero regression cho 4 fixture cũ** — `salvaged_ids` rỗng,
đường salvage không hề kích hoạt vì parser chặt đã đủ (đúng ngữ nghĩa "chỉ khi còn thiếu" của B-2);
(b) **B2-5 cứu được 32/32**, với id `"0"` đến từ đường JSON chuẩn (không bị salvage ghi đè — đúng
"KHÔNG BAO GIỜ để lên giá trị đã parse chặt"), 31 id còn lại đến từ salvage.

**Nội dung không bị cắt/hỏng ký tự đặc biệt** — tự kiểm tra thêm (không có trong claim gốc của
Dev, tự đào sâu theo yêu cầu brief "đọc kỹ implementation"):
- `outcome.translations["31"] == "<strong>¼ cup hạt cắt nhỏ</strong>"` — khớp CHÍNH XÁC giá trị
  Architecture.md §6.20.14.3 B-4 yêu cầu (dấu `¼`, tiếng Việt có dấu, thẻ HTML nguyên vẹn).
- `outcome.translations["3"] == '<a id="page_21"/>BÁNH KẾP KIỀU MẠCH MEN CHUA'` — giá trị này nằm
  ngay sau 1 escape `\"` thật trong `raw_response_text` (`<a id=\"page_21\"/>`), và
  `json.decoder.scanstring` đã unescape đúng thành `"` — xác nhận claim "escape xử lý đúng như JSON
  thật" của B-1 tính chất 2.

**Đọc kỹ `_salvage_epub_id_pairs()` (`src/core/prompt_builder.py`)**: dùng `json.decoder.scanstring`
đúng cách — gọi `scanstring(text, match.end())` với `match.end()` là vị trí NGAY SAU dấu `"` mở
(khớp docstring `scanstring` thật: tham số thứ 2 là vị trí sau dấu nháy mở). Khi 1 cặp hỏng giữa
chừng (`scanstring` raise `ValueError`/`JSONDecodeError`), code `except (ValueError,
json.JSONDecodeError): pos = match.end(); continue` — **không crash cả hàm**, chỉ bỏ qua đúng cặp
đó và `re.search(text, pos)` tiếp tục quét từ ngay sau vị trí bắt đầu cặp hỏng (không phải từ đầu
lại) — 3 test tổng hợp `test_layer_b_does_not_create_fake_pair_from_substring_inside_translated_
value`, `test_layer_b_keeps_complete_pairs_before_a_truncated_tail`,
`test_layer_b_ignores_id_outside_expected_ids` (`tests/test_epub_batch_golden_fixture.py:483-517`)
verify đúng 3 tính chất này bằng chuỗi tổng hợp, không phụ thuộc fixture. Đã tự đọc + chạy lại cả 3
test — pass, assertion cụ thể (không phải `assert_called()`).

## 2. Data lineage — `chunk.api_cost`/`api_tokens_used` khi rơi vào Lớp C (mục 2 brief) — ⚠️ CHƯA SỬA, đã lặp lại từ finding cũ

**Đây là câu hỏi trọng tâm nhất của brief PM, và câu trả lời là: VẤN ĐỀ CŨ (finding non-blocking #1,
vòng review Bug #EPUB-B2-1/#EPUB-4, xem phần "# Review Report — Fix Bug #EPUB-B2-1 + #EPUB-4" ở
trên trong chính file này) VẪN CÒN NGUYÊN, và diff này vừa thêm 1 điểm raise MỚI mắc đúng lỗi đó.**

Đọc trực tiếp `job_orchestrator.py`:

- `EpubChunkCostCapExceeded` (Lớp 4, dòng ~1976-1978, code CŨ từ vòng trước): **CÓ** ghi
  `chunk.api_tokens_used`/`chunk.api_cost` TRƯỚC khi raise — đúng yêu cầu tường minh Protocol 6.
- `EpubRequestRunawayError` (R-b, `job_orchestrator.py:2028`, code CŨ từ vòng trước, không đổi bởi
  diff này): raise mà **KHÔNG** ghi `chunk.api_cost`/`api_tokens_used` trước.
- `EpubBatchTranslationError` do vượt ngưỡng CHUNK 20% (C-2, `job_orchestrator.py:2228`, **code MỚI
  của chính diff đang review**): raise mà **CŨNG KHÔNG** ghi `chunk.api_cost`/`api_tokens_used`
  trước — **đây là điểm mới**, không phải kế thừa nguyên xi, vì C-2 là logic hoàn toàn mới của
  §6.20.14.4.

Cả 2 exception trên rơi vào khối `except Exception as exc:` chung ở `run_epub_job()` (dòng
979-992) — khối đó chỉ set `chunk.status = "failed"`/`chunk.error_message`/`chunk.retry_count`,
**không đụng `chunk.api_cost`/`api_tokens_used`**. Hệ quả: khi 1 chunk fail vì vượt ngưỡng C-2 (ví
dụ request chính + retry nguyên request + có thể cả retry đơn lẻ đã chạy, mỗi lần đều tốn tiền
thật, đã cộng vào biến cục bộ `total_cost` bên trong `_process_epub_chunk()`), `total_cost` đó
**không bao giờ được ghi vào `chunk.api_cost`** trước khi hàm raise và thoát — tiền đã trả cho
những request đó "biến mất" khỏi `job.actual_cost` (được tính bằng `sum(c.api_cost or 0.0 for c in
chunks[:position])`, và chunk fail này có `api_cost = None`/0).

**Xác nhận bằng test**: `test_still_missing_after_whole_request_retry_fails_chunk_over_ratio`
(`tests/integration/test_epub_translate_guards.py:186`) và
`test_run_epub_job_still_missing_after_retry_fails_chunk_no_empty_write`
(`tests/integration/test_epub_translate_runner.py:419`) — cả 2 test đúng kịch bản kích hoạt C-2 —
chỉ assert `result.status == "failed"` và nội dung `error_message`, **không có bất kỳ assertion nào
trên `chunk.api_cost`/`job.actual_cost`** sau khi fail. Tự thêm tạm 1 dòng debug
(`print(chunk.api_cost)` sau khi chạy `test_still_missing_after_whole_request_retry_fails_chunk_
over_ratio`, không commit) xác nhận `chunk.api_cost is None` dù `provider.calls` cho thấy 2 lệnh
gọi API thật (2 lần `translate()`) đã xảy ra trước khi raise — xác nhận claim trên bằng thực nghiệm,
không chỉ đọc code suông.

**Mức độ nghiêm trọng**: Spec §6.20.14 KHÔNG yêu cầu Dev sửa đường `except Exception` chung ở đợt
này (không có mục nào trong §6.20.14.4/.6/.7 nhắc tới việc này), nên **không phải lệch spec** —
giữ nguyên xếp loại **non-blocking** như vòng review trước đã xếp cho cùng lớp vấn đề (R-b). Nhưng
khác vòng trước ở chỗ: (a) lúc đó vấn đề mới chỉ tồn tại ở nhánh R-b (hiếm khi trigger — cần vừa
runaway vừa thiếu id); giờ nó tồn tại thêm ở nhánh C-2 — nhánh này chính là "lối thoát chính thức"
mới của toàn bộ chiến lược §6.20.14 khi Lớp C thất bại, nên **khả năng trigger cao hơn hẳn** so với
R-b; (b) đây là finding ĐÃ được escalate rõ ràng cho "vòng sau" ở review trước, và vòng này chính là
"vòng sau" đó nhưng Dev không đụng tới. **Đề nghị mạnh**: Tech Lead thêm vào §6.20.14 (hoặc mục
riêng kế tiếp) yêu cầu tường minh mọi nhánh raise bên trong `_process_epub_chunk()`
(`EpubBatchTranslationError` C-2, `EpubRequestRunawayError` R-b) đều phải ghi `chunk.api_tokens_
used`/`chunk.api_cost` TRƯỚC khi raise, đúng pattern `EpubChunkCostCapExceeded` đã làm đúng — không
để lại cho "sửa sau có cơ hội".

**Phần lineage KHÁC vẫn đúng** (đối chiếu lại toàn bộ, không chỉ phần bị flag ở trên): khi chunk
**không** fail (job hoàn tất bình thường, kể cả có fallback trong hạn mức), `total_cost` được ghi
đúng vào `chunk.api_cost` ở cuối `_process_epub_chunk()` (dòng 2283-2285) — bao gồm cả chi phí của
những request đã "hỏng" nhưng unit của nó rơi vào fallback (vì `_accumulate_and_check_budget()`
cộng dồn TRƯỚC khi biết parse thành công hay không, ngay sau mỗi lệnh gọi `translate()`) — đây
chính xác là hành vi PM brief hỏi ("tiền đã trả cho request hỏng đó vẫn phải được ghi nhận") và nó
ĐÚNG cho đường "job hoàn tất" — chỉ sai cho đường "chunk fail qua C-2/R-b" như trên.

## 3. Ngưỡng chunk 20%/job 5% — verify tính cộng dồn qua resume (mục 3 brief)

Đọc kỹ `test_fallback_job_ratio_survives_resume_across_orchestrator_instances`
(`tests/integration/test_epub_translate_guards.py:319`) — xác nhận đây **THẬT SỰ** mô phỏng 1 job
bị gián đoạn rồi resume, không phải "2 instance không liên quan":

1. `orchestrator1` chạy, chunk 0 hoàn tất với 1 fallback unit (trong hạn mức riêng nó), chunk 1
   **crash thật** bằng `RuntimeError("simulated crash mid-chunk 1")` do script provider tự ném ra —
   mô phỏng lỗi hạ tầng giữa chừng, không liên quan Lớp C. `first_result.status == "failed"`, DB
   xác nhận `chunks[0].status == "completed"`, `chunks[1].status == "failed"`.
2. Test tự set `chunk.status = "pending"` cho chunk fail — **đúng cách `retry_job()` API layer làm**
   (đối chiếu code thật, không phải Dev tự bịa cách resume riêng cho test).
3. `orchestrator2` là **instance `JobOrchestrator` HOÀN TOÀN MỚI** (không share bất kỳ biến Python
   nào với `orchestrator1` — object mới, không có tham chiếu tới đối tượng cũ), chạy lại từ đầu qua
   `run_job()` — chunk 1 lần này lại thiếu 1 unit khác (id `"0"`), fallback.
4. Assertion cuối: `job.error_message` chứa "fallback" và `completed_chunks == 2` — job fail NGAY
   SAU chunk 1 vì `1 (chunk 0, đọc lại từ file trên đĩa) + 1 (chunk 1, lần chạy này) = 2 > ngưỡng
   job = max(1, ceil(0.05 × 20)) = 1`.

Cơ chế cộng dồn xác nhận đúng bằng đọc code: `_collect_epub_fallback_units()`
(`job_orchestrator.py`) chỉ lọc `db_chunk.status == "completed"` rồi **đọc lại file
`fallback_units.json` từ đĩa** (`self._processing_dir / job.id / f"chunk_{db_chunk.chunk_index}" /
"fallback_units.json"`) — không dùng bất kỳ biến đếm trong bộ nhớ nào của `_process_epub_chunk()`.
Vì `orchestrator2` không hề có tham chiếu tới `chunks` list của `orchestrator1`, việc nó vẫn đếm
đúng 2 (1 từ đĩa + 1 mới) chứng minh cơ chế sống sót qua resume THẬT, không phải test tự tạo giả
định trùng hợp. Ngưỡng job cũng xác nhận tính **trên `job.total_units`** (= 20, tổng unit CẢ SÁCH),
không phải tổng unit đã xử lý tới thời điểm đó — đúng yêu cầu brief.

Test song song `test_fallback_exceeding_job_ratio_fails_job_after_accumulating_across_chunks`
(dòng 271, cùng 1 instance nhưng 4 chunk) verify thêm: fail dừng lại **NGAY SAU chunk vượt ngưỡng**
(`completed_chunks == 2`, không xử lý tiếp chunk 2/3) — tiết kiệm tiền đúng tinh thần Lớp 3/4.

## 4. A-4 — mọi call site đã cập nhật `settings`? (mục 4 brief)

`grep -rn "estimate_translation_cost(" src tests` → chỉ **1 call site production**:
`src/api/routes/jobs.py:377` (`_estimate_translation_cost_or_400()`), đã truyền `settings=settings`
đúng. Xác nhận thêm: `job_orchestrator.py` **không hề gọi** `estimate_translation_cost()` (chỉ có 1
dòng comment tham chiếu tới `_estimate_epub_translation_cost()`, không phải lời gọi thật) — orchestrator
tính chi phí THẬT trực tiếp từ `TranslationResult`, không đi qua estimator, nên không có nguy cơ
lệch tham số ở phía orchestrator. 6 call site còn lại đều trong `tests/test_epub_cost_gate.py`, đã
tự đọc — cả 6 đều truyền `settings=Settings(...)` tường minh (không có test nào gọi thiếu `settings`
cho nhánh `file_type="epub"` mà không catch `ValueError`). Có 1 test riêng xác nhận đúng hành vi
raise: dòng 220 của file đó gọi thiếu `settings` và `pytest.raises(ValueError)` — verify guard `A-4`
hoạt động đúng, không chỉ tin code không crash vì không ai test đường lỗi.

## 5. Ba điểm Dev tự flag (mục 5 brief)

- **2 test nới lỏng trong `test_epub_batch_prompt.py`** (`test_parse_strips_leading_prose`,
  `test_parse_genuinely_truncated_json_recovers_only_the_complete_pair`) — đọc kỹ: đây đúng là NỚI
  LỎNG CÓ CHỦ ĐÍCH, hệ quả tự nhiên của Lớp B ("chỉ cần 1 cặp `"id": "giá trị"` còn nguyên vẹn, bất
  kể có prose trước hay bị cắt cụt ở id khác"). Cả 2 test đều có docstring giải thích rõ vì sao hành
  vi cũ không còn đúng và trích dẫn đúng §6.20.14.3 — không phải nới lỏng để che giấu regression
  (test thứ 2 vẫn giữ `assert "1" not in result` — id thật sự bị cắt cụt vẫn KHÔNG được cứu, đúng
  giới hạn đã biết của Lớp B).
- **3 test E-09 đổi ngưỡng** — đã đọc + tự verify số: `test_still_missing_after_whole_request_
  retry_fails_chunk_over_ratio` (6/6 unit thiếu, 100% > 20%), `test_missing_ids_within_chunk_
  ratio_fallback_to_english_job_completes` (1/20 = 5%, ≤ 20% chunk và ≤ 5% job, cố ý chọn 20 unit
  thay vì 6 để tránh tự làm fail BR-EPUB-05's khe hở 10% — có giải thích số học ngay trong
  docstring), `test_run_epub_job_still_missing_after_retry_fails_chunk_no_empty_write` (2/2 = 100%).
  Cả 3 dùng đúng 2 hằng số `EPUB_FALLBACK_MAX_RATIO_CHUNK=0.20`/`_JOB=0.05` đã chốt trong
  `chunking.py`, không phải số Dev tự chọn riêng cho test.
- **Chưa có live E2E full-book** — xác nhận đúng, Dev ghi rõ trong CHANGENLOG. Ghi vào gate release
  bên dưới, bắt buộc QA verify sống theo R5-03/R6-03/H-1 (§6.20.14.9) trước `ready_for_release`.

## 6. Rủi ro "Lớp B cứu nhầm rác thành dữ liệu giả" (mục 6 brief)

**Đánh giá: rủi ro có thật về mặt lý thuyết nhưng bị chặn khá chặt bởi thiết kế, và lưới an toàn Lớp
C (ngưỡng 20%/5%) chỉ là lớp phòng thủ CUỐI, không phải lớp duy nhất.**

Cơ chế tự nó đã giảm rủi ro đáng kể trước khi cần tới Lớp C:
1. Khoá phải khớp `expected_ids` — tập id ngắn cục bộ `"0".."N"` (N ≤ `EPUB_REQUEST_MAX_UNITS` = 6
   sau Lớp A) do CHÍNH app sinh cho request đó, không phải chuỗi bất kỳ. Rác ngẫu nhiên phải trùng
   khớp CHÍNH XÁC 1 trong tối đa 6 con số cụ thể + đúng vị trí cú pháp `"<số>": "` — không gian rác
   hợp lệ rất hẹp.
2. Giá trị phải qua được `json.decoder.scanstring` — rác ngẫu nhiên có xác suất cao chứa ký tự phá
   vỡ escape JSON (dấu `"` không escaped, `\` lẻ loi) khiến `scanstring` raise và bị loại ngay.
3. **Nội dung salvage luôn là byte THẬT của response** (tính chất B-1 #4) — Lớp B không "đoán" hay
   tự sinh nội dung, nên rủi ro thực sự không phải "sinh dữ liệu giả" mà là "gán SAI id cho 1 đoạn
   text thật nằm sai chỗ trong response" (ví dụ prose giải thích của model vô tình chứa
   `"3": "câu gì đó"` không phải bản dịch id 3 thật) — đây là rủi ro THẬT, không phải suy diễn quá
   xa, vì DeepSeek đã được quan sát chèn prose dẫn đầu (`test_parse_strips_leading_prose`).

**Lớp C có đủ làm lưới an toàn cuối không?** Có, với 1 giới hạn cần ghi rõ: ngưỡng 20%/5% chặn được
trường hợp salvage **thất bại** (không đủ số lượng id cứu được) hoặc **excess** (số unit fallback
quá nhiều), nhưng **không** chặn được trường hợp salvage "thành công về số lượng" nhưng SAI NỘI
DUNG (đủ 32/32 id nhưng 1 vài id gán nhầm text) — loại lỗi này không tạo ra fallback unit nào (nó
KHÔNG rơi vào nhánh `still_missing`) nên hoàn toàn nằm ngoài phạm vi đo của ngưỡng chunk/job. Lưới
an toàn thực sự cho loại lỗi này là 2 tầng guard mất dấu (`diacritic_ratio`, đã có từ vòng trước,
không đổi bởi diff này) — nếu salvage gán nhầm 1 đoạn tiếng Anh/rác vào 1 id tiếng Việt, guard mất
dấu tầng unit (`EPUB_DIACRITIC_MIN_LETTERS_UNIT=40`, `EPUB_DIACRITIC_RATIO_UNIT=0.02`) có cơ hội
bắt được NẾU đoạn gán nhầm đủ dài và thiếu dấu — nhưng nếu đoạn rác gán nhầm lại là tiếng Việt có
dấu hợp lệ (ví dụ salvage vô tình lấy nhầm 1 đoạn dịch của unit KHÁC gán cho id sai), **không có
guard nào trong toàn bộ pipeline phát hiện được** — đây là giới hạn thật, không phải giả thuyết
suông, nhưng KHÔNG PHẢI gap riêng của đợt Lớp B này: guard mất dấu vốn dĩ đã không bao giờ phát
hiện được "dịch đúng ngữ pháp nhưng sai NỘI DUNG/lạc chỗ" ngay cả trước khi có Lớp B. **Kết luận:
rủi ro "cứu nhầm rác thành dữ liệu giả theo nghĩa đen" (text không phải bản dịch thật) là THẤP** nhờ
3 lớp chặn ở trên; rủi ro "gán đúng text thật nhưng sai id" là **có thật nhưng không mới** (cùng
hạng mục rủi ro con người/model dịch sai nội dung đã tồn tại từ trước, không phải rủi ro Lớp B tạo
ra) — không đủ để REJECT, nhưng **đề nghị non-blocking**: khi QA vòng sau chạy live E2E full-book
(H-1), ngoài kiểm `job.status`/mở file xem có chữ, nên tự tay đối chiếu 1 vài id có `salvaged_
count > 0` (từ `requests.jsonl`) với đúng vị trí unit gốc trong sách, xác nhận nội dung KHỚP ĐÚNG vị
trí — không chỉ khớp có-chữ-tiếng-Việt.

## Checklist R5-04

- `src/core/prompt_builder.py` (`_salvage_epub_id_pairs`, `parse_epub_batch_response_detailed`):
  **N/A** — thuần Python, dùng `json.decoder.scanstring` (stdlib), không gọi external tool/network.
- `src/core/chunking.py`/`src/core/config.py` (hằng số Lớp A/C): **N/A** — thuần cấu hình nội bộ.
- `src/core/cost_gate.py`/`src/core/cost_estimator.py` (A-4): **N/A** — không gọi external tool,
  chỉ đồng bộ tham số nội bộ giữa 2 lời gọi hàm cùng 1 codebase.
- `src/core/job_orchestrator.py` (`_process_epub_chunk()`, nơi gọi thật
  `pricing_provider.translate()`): **NO — chỉ verify theo Architecture.md, chưa có live E2E ở vòng
  này.** Giữ nguyên gap đã ghi ở vòng review trước — **bắt buộc** QA đóng theo R5-03/R6-03/H-1
  trước `ready_for_release`, chưa có gì thay đổi so với khuyến nghị vòng trước.

## Tổng hợp finding

**Finding quan trọng (không block vòng này, phải escalate cho Tech Lead vòng sau)**:
1. (mục 2) `chunk.api_cost`/`api_tokens_used` không được ghi trước khi raise ở 2 đường
   `EpubBatchTranslationError` (C-2, MỚI) và `EpubRequestRunawayError` (R-b, cũ) — tiền thật "biến
   mất" khỏi sổ sách khi chunk fail qua 2 đường này. Lặp lại finding non-blocking #1 của vòng review
   trước, CHƯA được sửa, và C-2 là đường MỚI của chính diff này nên đáng lẽ nên được xử lý cùng lúc.

**Finding non-blocking nhỏ hơn**:
2. (mục 6) Guard hiện có không phát hiện được salvage "gán đúng text thật nhưng lạc id" (đã tồn tại
   từ trước Lớp B, không phải gap riêng của Lớp B) — đề nghị QA đối chiếu thủ công vài id salvaged
   khi chạy live E2E (H-1).
3. `job.error_message` cho đường C-2/job-level (§6.20.14.4 C-3, `job_orchestrator.py` dòng
   ~1042-1057) không có test nào assert message chứa đúng con số `job_fallback_allowed`/tổng unit —
   test hiện có (`test_fallback_exceeding_job_ratio_fails_job_after_accumulating_across_chunks`)
   chỉ assert `"fallback" in job.error_message` và `"5%" in ... or "unit" in ...` (kiểm tra lỏng,
   OR thay vì AND) — không chặn merge vì message thật (đọc code) đúng có đủ số liệu, chỉ là test
   chưa siết assertion tới mức đó.
4. `_retry_single_unit()`/`_retry_whole_epub_request()` (2 helper mới) không được `is_runaway_output()`
   kiểm tra lại — kế thừa nguyên xi finding non-blocking #2 của vòng review trước (chưa đổi bởi diff
   này, không phải regression).

## Vòng lặp

**Circuit breaker Dev↔Reviewer cho chiến lược 3 lớp §6.20.14 này: 1/3 vòng đã dùng — VÒNG 1/3 này
APPROVE ngay, không cần vòng 2.** Vòng đếm RIÊNG, không cộng dồn với B2-1/#EPUB-4, B2-3, hay B2-4.
Lưu ý: đây là vòng đếm review CODE (Protocol 3 Dev↔Reviewer) — KHÔNG liên quan tới việc Protocol 3
Dev↔QA đã chạm giới hạn 5/5 trước đó (đã ghi trong `docs/escalation-log.md`, đã được user quyết định
đổi chiến lược, không phải lỗi của vòng review này).

---

# Review Report — US-22 Bước 3/3 (5 việc hoàn thiện AC) — VÒNG 1/3

**Phạm vi**: working tree chưa commit — `src/core/job_orchestrator.py`,
`tests/integration/test_epub_translate_runner.py`, `web/index.html`, `web/js/app.js`,
`docs/CHANGELOG.md` (entry "US-22 EPUB — Bước 3/3"). Đọc trực tiếp `git diff`, không dựa vào mô tả
trong CHANGELOG.

## 1. Salvage telemetry (việc 1)

Xác nhận CẢ 4 lời gọi parse trong `job_orchestrator.py` đã đổi sang `parse_epub_batch_response_detailed()`:
main request (`_process_epub_chunk()`, dòng ~2045), `_retry_single_unit()` (dòng ~1915),
`_retry_whole_epub_request()` (dòng ~1942), và grep xác nhận không còn lời gọi nào tới
`parse_epub_batch_response()` (bản rút gọn) trong `job_orchestrator.py` — chỉ còn import
`EpubParseOutcome` + `parse_epub_batch_response_detailed`. Cả 2 helper retry đều nhận thêm
`job_id`/`chunk_index` keyword-only đúng như CHANGELOG mô tả, và cả 4 call site gọi 2 helper này
(2 vị trí retry-đơn-unit, 2 vị trí retry-nguyên-request) đều truyền đủ 2 tham số mới.

`_log_epub_parse_salvage()`: `salvaged_count > 0` → WARNING kèm đủ `job_id`, `chunk_index`,
`salvaged_count`, `salvaged_ids` (sorted) — đủ thông tin để trace đúng chunk/unit nào cần cứu hộ,
đúng yêu cầu brief. `== 0` → INFO, không gây nhiễu log ở đường chuẩn. Không phát hiện vấn đề.

## 2. output_mode cho EPUB (TRỌNG TÂM CHÍNH)

**Đây là điểm quan trọng nhất của vòng review này — đã verify kỹ, KHÔNG có gap thật.**

- `_wants_bilingual()` (`job_orchestrator.py:2517-2520`):
  ```python
  async def _wants_bilingual(self, job: Job, db_session: AsyncSession) -> bool:
      if not job.batch_id:
          return False
      batch = await db_session.get(Batch, job.batch_id)
      return bool(batch and batch.output_mode == "bilingual")
  ```
  Xác nhận đúng như brief cảnh báo: nếu `job.batch_id` falsy, trả `False` ngay (im lặng thành
  monolingual). Đây chính là rủi ro brief yêu cầu verify.

- Đã trace TOÀN BỘ đường tạo `Job` trong production code (`grep -rln "Job(" src/` → chỉ
  `src/models/job.py` (định nghĩa) và `src/api/routes/jobs.py` có khởi tạo `Job(...)`). Chỉ có
  DUY NHẤT 1 chỗ khởi tạo `Job` thật trong `create_job()` (dòng ~622-645), và nó LUÔN đi qua
  `batch = await _resolve_batch(...)` trước đó (dòng 622) rồi gán `batch_id=batch.id` (dòng 624) —
  không có nhánh nào bỏ qua `_resolve_batch()`. `_resolve_batch()` (dòng 463-494) luôn trả về 1
  `Batch` hợp lệ: nếu có `glossary_project_id` thì lấy Batch có sẵn (404 nếu không tồn tại — không
  bao giờ trả `None`), nếu không thì tạo mới `Batch` và commit trước khi trả về. Endpoint
  `create_batch()` (dòng 1007+) cũng qua `_resolve_batch()` tương tự. `retry_job()` (dòng 727) chỉ
  reset job hiện có, không tạo `Job` mới nên không tạo `batch_id` mới nào.
  → **Kết luận: không có kịch bản nào trong production tạo được 1 Job EPUB (hay bất kỳ file type
  nào) với `batch_id=None`.** Đánh giá của Dev trong CHANGENLOG ("đây là gap thật của test helper,
  không phải gap production") là ĐÚNG, đã tự verify độc lập bằng cách đọc source, không dựa vào mô
  tả của Dev.
- `write_translated(bilingual=False)`: đọc `src/services/epub_document.py:617-686+` — logic ghi
  THAY THẾ tại chỗ (không chèn node `bb-vi` mới) khi `bilingual=False`, đúng thiết kế "monolingual
  = thay thế, bilingual = chèn thêm". Test
  `test_run_epub_job_monolingual_output_mode_has_no_english_original` assert đúng và chặt: không chỉ
  check thiếu `bb-vi`, mà còn đếm số lần xuất hiện của cụm gốc `"Chapter 0 paragraph 0"` — kỳ vọng
  đúng 1 lần (câu tiếng Anh gốc chỉ còn tồn tại NHƯ MỘT CHUỖI CON của bản dịch `"VI:Chapter 0..."`,
  không phải node riêng), so với bilingual mặc định là 2 lần (node gốc + node `bb-vi`). Đây là cách
  assert đúng bản chất "thay thế" thay vì chỉ đếm số dòng dịch — không phải test hời hợt. Ngoài ra
  còn assert `len(output_doc.units) == 6` (không mất chương ở monolingual).
- Regression case mặc định: helper `_create_epub_job()` giữ `output_mode: str = "bilingual"` làm
  default — mọi test EPUB cũ gọi `_create_epub_job()` không truyền `output_mode` vẫn tạo `Batch`
  với `output_mode="bilingual"`, giữ đúng kỳ vọng cũ. Chạy `uv run pytest tests/ -q` độc lập xác
  nhận không có test EPUB nào cũ bị fail.
- `web/js/app.js` `defaultOutputMode = body.file_type === "epub" ? "bilingual" : "monolingual"` chỉ
  áp dụng khi `lastOutputMode` (localStorage) rỗng — đúng tinh thần "mặc định, không phải cố định",
  và không ảnh hưởng gì tới việc `_wants_bilingual()` phía backend đọc `Batch.output_mode` (2 lớp
  độc lập: UI chỉ set giá trị mặc định hiển thị/gửi lên, backend là nguồn sự thật cuối).

## 3. UI `total_units` (việc 3)

`web/index.html` dòng mới: `<template x-if="!f.page_count && epubTotalUnits(f)">` — chỉ kích hoạt
khi KHÔNG có `page_count`, an toàn cho PDF (PDF luôn có `page_count` nên template PDF không bao giờ
hiện đè). `epubTotalUnits(f)` trong `app.js`:
```js
epubTotalUnits(f) {
  return f.job?.total_units ?? f.costEstimate?.total_units ?? null;
}
```
Dùng optional chaining (`?.`) và `??` nên khi `f.job`/`f.costEstimate` là `undefined`/`null`, hoặc
khi cả 2 field `total_units` đều `null`/`undefined`, hàm trả `null` — Alpine `x-if` với `null` là
falsy nên template không hiện, không crash. Không phát hiện vấn đề.

## 4. Data lineage (Protocol 6)

Đọc `run_epub_job()`: `bilingual = await self._wants_bilingual(...)` được gọi SAU khi toàn bộ
`translations` (kết quả dịch qua LLM, chi phí đã tính ở `chunk.api_cost` trong `_process_epub_chunk()`
mỗi chunk) đã hoàn tất — biến `bilingual` chỉ được dùng ở bước `doc.write_translated(...)` và
`_check_epub_output_guard(...)`, không quay lại ảnh hưởng số lần gọi LLM hay `chunk.api_cost` nào.
Xác nhận đúng như Architecture.md đã ghi: đổi `output_mode` không phát sinh chi phí LLM thêm.

## 5. Kết quả chạy lại độc lập

```
uv run ruff check src/ tests/   → All checks passed!
uv run pytest tests/ -q         → 746 passed, 0 failed (100.51s)
```
Khớp đúng con số Dev báo cáo.

## Checklist R5-04 (Protocol 5, external contract)

`job_orchestrator.py`/test file trong diff này: N/A — không có claim contract API/CLI/SDK bên thứ 3
mới nào (dùng lại contract JSON X4 đã verify ở Bước 2/3, `web/*` không gọi external tool).

## Kết luận

**APPROVE.**

Không có issue blocking. Trả lời thẳng câu hỏi trọng tâm của brief: **KHÔNG có job EPUB thật nào
trong production có thể thiếu `batch_id`** — mọi đường tạo `Job` (kể cả EPUB) đều đi qua
`_resolve_batch()` trước, luôn gán `batch_id` hợp lệ. Gap chỉ tồn tại ở test helper cũ (thiếu tạo
`Batch`/gán `batch_id`), đã được Dev sửa đúng trong diff này, và sửa đó không che giấu gap production
nào — đã tự trace bằng tay toàn bộ call site tạo `Job`, không suy đoán.

**Finding non-blocking (không chặn merge, ghi lại để theo dõi)**:
1. `_wants_bilingual()` không tự log/warn khi `job.batch_id` falsy trước khi trả `False` — hiện tại
   vô hại vì production luôn có `batch_id`, nhưng nếu tương lai có thêm 1 đường tạo `Job` mới (vd
   qua script migration, seed data, hoặc endpoint mới) quên gọi `_resolve_batch()`, lỗi sẽ lại im
   lặng y hệt kịch bản Bug #5/#9 (silent wrong-default) mà không có log nào báo hiệu. Đề nghị Tech
   Lead cân nhắc thêm 1 dòng `logger.warning` khi `not job.batch_id` ở nhánh sớm return, hoặc raise
   thay vì âm thầm `False` — không blocking vòng này vì đây là phòng ngừa cho tương lai, không phải
   bug hiện tại.
2. Test mới `test_run_epub_job_logs_salvaged_count_when_layer_b_engages` dùng `_SpuriousBracesProvider`
   tự viết tay để mô phỏng hình dạng bug, không phải golden fixture capture từ response thật — Dev
   đã tự giải thích rõ trong docstring rằng đây là mô phỏng CÙNG HÌNH DẠNG với golden fixture đã có
   ở cấp parser (`tests/test_epub_batch_golden_fixture.py`), chỉ chạy lại ở cấp orchestrator, nên
   không vi phạm Protocol 5 R5-03 (không phải claim contract mới của LLM thật, mà là test lại logic
   nội bộ `_process_epub_chunk()` với input đã biết hình dạng từ golden fixture) — chấp nhận được,
   ghi lại để QA lưu ý không nhầm đây là smoke test thay thế cho live E2E.

## Vòng lặp

Circuit breaker Dev↔Reviewer cho US-22 Bước 3/3: **1/3 vòng đã dùng — APPROVE ngay ở VÒNG 1/3**,
không cần vòng 2. Vòng đếm riêng, không cộng dồn với các vòng review trước của US-22 Bước 1/3, 2/3
hay các bug #5/#8/#9 trước đó.

---

---

# Review Report — Fix UI Alpine template (N đoạn/trang/Tải lên) + đóng US-22 toàn bộ — VÒNG 1/3

- **Reviewer**: Reviewer Agent (Sonnet)
- **Phạm vi**: PM tự sửa trực tiếp `web/index.html` (3 dòng, không qua Dev) theo Protocol 7 R7-01 —
  bắt buộc Reviewer thật trước khi coi xong, bất kể thay đổi nhỏ. Đối tượng review: diff 3 dòng +
  toàn bộ bằng chứng PM ghi trong `docs/test-report.md` section "US-22 Dịch EPUB — Bổ sung: đóng gap
  'Apple Books' + fix bug UI 'N đoạn' (PM, 2026-09-10)".
- **External contract verified against real source**: N/A — thay đổi này không gọi tool bên thứ ba
  nào (chỉ Alpine.js client-side template + đọc file EPUB tĩnh), Protocol 5 không áp dụng.

## 1. Diff thực tế (`git diff web/index.html`)

```html
-                <template x-if="f.page_count"> · <span x-text="f.page_count"></span> trang</template>
-                <template x-if="formatUploadDate(f)"> · Tải lên: <span x-text="formatUploadDate(f)"></span></template>
+                <template x-if="f.page_count"><span> · <span x-text="f.page_count"></span> trang</span></template>
+                <template x-if="!f.page_count && epubTotalUnits(f)"><span> · <span x-text="epubTotalUnits(f)"></span> đoạn</span></template>
+                <template x-if="formatUploadDate(f)"><span> · Tải lên: <span x-text="formatUploadDate(f)"></span></span></template>
```

Khớp đúng với mô tả "3 dòng" trong test-report.md (thực chất 2 dòng sửa + 1 dòng thêm mới — dòng
"N đoạn" vốn đã tồn tại trước đó theo cùng pattern lỗi, nay được sửa cùng lúc; không lệch với bối
cảnh brief).

## 2. Root cause + tính đúng đắn của fix — tự verify độc lập, KHÔNG dựa lời PM

Tự dựng 1 trang test Alpine.js tối giản, tách biệt hoàn toàn khỏi app thật (không đụng server dev,
không đụng dữ liệu user), tại
`/private/tmp/.../scratchpad/reviewer_check/alpine_template_test.html`, dùng Alpine 3.x qua CDN
(`cdn.jsdelivr.net`), phục vụ qua `python3 -m http.server 8765` (localhost, không phải `file://` vì
Claude Browser MCP không exec JS trên file cục bộ) và mở bằng Claude Browser MCP:

```html
<div id="broken">
  BROKEN: <span x-text="'x'"></span>
  <template x-if="cond"> · <span x-text="val"></span> đoạn</template>
</div>
<div id="fixed">
  FIXED: <span x-text="'x'"></span>
  <template x-if="cond"><span> · <span x-text="val"></span> đoạn</span></template>
</div>
```

`get_page_text` trả về thật (encoding hiển thị lệch do thiếu `<meta charset>` trong file test, không
ảnh hưởng tới việc so sánh có/không có text):

```
BROKEN: x 10
FIXED: x · 10 đoạn
```

**Xác nhận độc lập, khớp chính xác root cause PM mô tả**: bản BROKEN (pattern cũ, `<template x-if>`
có text node " · " và " đoạn" làm ANH EM của `<span>`) chỉ render số "10" trần trụi, mất hoàn toàn
dấu "·" và nhãn — đúng y hệt bug QA vòng trước phát hiện. Bản FIXED (bọc `<span>` bao ngoài) render
đầy đủ "· 10 đoạn". Đây là hành vi đã biết của Alpine `x-if`/`<template>`: engine dùng
`template.content.firstElementChild` để clone nội dung khi expand, nên chỉ 1 root element duy nhất
được xử lý đúng — text node anh em bị bỏ qua. Bọc `<span>` bao ngoài là cách sửa chuẩn, không phải
workaround tạm bợ.

**Ảnh hưởng CSS/layout**: `<span>` là phần tử inline mặc định, không có style riêng được gán (không
set `display`, `class`) → không ảnh hưởng flow/wrapping của `<p class="text-xs text-gray-500">` cha.
Tự kiểm tra bằng mắt qua trang test: text "· 10 đoạn" nằm cùng dòng, không xuống dòng lạ, không đổi
kích thước font. **Không có rủi ro layout.**

## 3. Cả 3 template có nhất quán không

`grep -n "template x-if" web/index.html` → đúng 3 kết quả (dòng 52-54), cả 3 đều đã bọc `<span>` bao
ngoài theo đúng 1 pattern. Không có template `x-if` nào khác trong file bị sót. **Nhất quán.**

## 4. Verify qua browser thật trên server dev (PM tự làm) — đánh giá độ tin cậy

PM báo cáo mở `http://localhost:8000` (server dev đang chạy, dữ liệu PDF thật, CHỈ ĐỌC) và xác nhận
12 file PDF hiển thị đúng "· Tải lên: ...". Đây là bằng chứng hợp lệ cho nhánh "trang" +
"Tải lên:" (2/3 template) vì PDF thật chắc chắn có `page_count`. **Không tự lặp lại bước này** (vì
brief nói server có thể không còn chạy trong phiên Reviewer, và việc này không đổi kết luận — đã có
bằng chứng độc lập mạnh hơn ở mục 2 phía trên chứng minh đúng cơ chế chung).

## 5. Đánh giá riêng: "N đoạn dùng chung pattern nên chắc chắn đúng" — suy luận PM có đủ tin cậy không?

PM tự nhận KHÔNG upload EPUB test lên server thật (đúng, tránh nhiễu data production) và chỉ suy
luận nhánh "N đoạn" dùng đúng 1 pattern y hệt "trang"/"Tải lên" nên chắc chắn đúng.

**Đánh giá: suy luận này ĐÚNG VỀ KẾT LUẬN, nhưng bản thân "suy luận suông" (không kèm bằng chứng độc
lập nào) là chưa đủ chặt để tự nó đứng vững** — đây chính xác là loại rủi ro Protocol 8/R8-01 cảnh
báo ("chắc ổn vì dùng chung code" không tự động đúng, cần verify tường minh). Tuy nhiên khác với
Protocol 8 (áp dụng cho pipeline nhiều BƯỚC xử lý có ý nghĩa nghiệp vụ khác nhau giữa các biến thể),
ở đây cả 3 nhánh là **cùng 1 cấu trúc HTML, cùng 1 cơ chế Alpine engine xử lý y hệt nhau** (khác
nhau duy nhất ở biểu thức điều kiện và text hiển thị, không khác ở cấu trúc DOM quyết định bug) —
mức độ rủi ro "biến thể lệch nhau" thấp hơn nhiều so với bối cảnh Protocol 8 gốc (engine dịch khác
nhau về hành vi nghiệp vụ).

Để đóng dứt điểm, Reviewer đã **tự verify thay PM** bằng trang test độc lập ở mục 2 (dùng chính
biểu thức `<template x-if="cond"><span> · <span x-text="val"></span> đoạn</span></template>` — cùng
hệt cấu trúc dòng "N đoạn" thật, chỉ đổi tên biến) → xác nhận render đúng "· 10 đoạn" không mất chữ.
**Kết luận: nhánh "N đoạn" ĐÃ được verify gián tiếp nhưng chắc chắn (cùng cấu trúc DOM, cùng engine,
khác biến số) — không còn là suy luận suông nữa sau review này.** Khuyến nghị PM: lần sau nếu tự
nhận "suy luận dùng chung pattern" thay vì verify trực tiếp, nên chủ động tạo 1 test độc lập như
Reviewer vừa làm (rẻ, nhanh, không đụng data thật) thay vì để lại cho vòng Reviewer, để rút ngắn
Protocol 3 vòng lặp.

## 6. Apple Books (X1/X2) — tự đối chiếu lại độc lập, không tin lời PM

Tự giải nén `/tmp/qa_apple_books_check/sourdough_translated.epub` (md5 khớp file trong scratchpad
QA gốc, cùng kích thước 2.040.751 byte) và đọc trực tiếp `ops/xhtml/chapter01.html`:

- **X1 (phân số)**: `grep`/`grep -o` xác nhận nguồn dùng ký tự Unicode phân số trực tiếp (`¼ ½ ¾
  1¼ 1½ 2½ 4½ 6 ½`), không phải `<sup>/<sub>`. Đối chiếu nhiều dòng cụ thể, ví dụ dòng 77:
  `<strong>1¼ cups unbleached white flour</strong>` → `<strong>1¼ cups bột mì trắng chưa tẩy
  trắng</strong>` — ký tự phân số giữ nguyên vẹn, không có ca nào bị hỏng/gộp sai thành dạng số
  nguyên liền (kiểu "11/4"). Đếm được hàng chục lần xuất hiện `¼/½/¾/1¼/1½` rải khắp file, tất cả
  đều giữ nguyên ở cả câu EN gốc và câu VI dịch đi kèm.
- **X2 (danh sách nguyên liệu)**: dòng 27 xác nhận đúng cấu trúc PM mô tả:
  `<strong>4 cups unbleached white flour</strong><br/><strong>2 teaspoons salt</strong><br/>
  <strong>2 tablespoons honey</strong><br/><strong>4 cups potato water</strong>` → dịch giữ ĐÚNG 4
  dòng `<strong>`+`<br/>` riêng biệt, in đậm giữ nguyên ở cả bản EN và bản VI theo sau
  (`class="blockquote bb-vi" lang="vi"`). Kiểm tra thêm nhiều khối `<strong>...</strong><br/>` khác
  trong file (dòng 32, 37-38...) — cùng pattern giữ nguyên đúng.

**Kết luận mục 6: bằng chứng byte-level của PM ĐÚNG, tự đối chiếu độc lập khớp 100%.** Đây là bằng
chứng cấu trúc HTML (không phải visual rendering qua reader thật) — đúng như PM tự nhận trong
test-report.md, không phóng đại thành "đã verify bằng mắt qua Apple Books". Chấp nhận được làm bằng
chứng thay thế vì: (a) Books.app bị chặn cứng ở tầng policy công cụ agent, không phải do agent lười
thử, (b) rủi ro cụ thể X1/X2 nhắm tới ("phân số/danh sách bị hỏng cấu trúc") là rủi ro ở tầng HTML
generation, không phải rủi ro riêng của CSS/font rendering trong 1 reader cụ thể — bằng chứng cấu
trúc HTML đã đủ loại trừ rủi ro chính, phần dàn trang thị giác còn lại là rủi ro thấp hơn và PM đã
minh bạch ghi rõ giới hạn này cho user tự quyết định thêm nếu muốn.

## 7. Type hints / error handling / security

Không áp dụng — thay đổi thuần HTML template (Alpine.js markup), không có Python function signature
mới, không có I/O/API call mới, không có input người dùng nào được xử lý thêm.

## Kết luận

**APPROVE.**

- Fix đúng root cause, xác nhận bằng verify độc lập (trang test Alpine tách biệt, không dựa lời PM).
- Cả 3 template nhất quán, không sót.
- Không ảnh hưởng CSS/layout.
- Bằng chứng Apple Books (X1/X2) đối chiếu độc lập khớp 100% với báo cáo PM.
- Suy luận "N đoạn dùng chung pattern" của PM về kết luận là đúng, nhưng bản thân suy luận đó (không
  kèm bằng chứng) chưa đủ chặt để tự đứng — Reviewer đã bổ sung bằng chứng độc lập để đóng dứt điểm
  trong vòng này, không cần vòng lặp Dev↔Reviewer nào thêm.

**Non-blocking, khuyến nghị cho lần sau (không chặn approve)**:
1. Khi PM/Dev tự nhận "suy luận dùng chung pattern thay vì verify trực tiếp" cho 1 thay đổi UI rẻ để
   test độc lập, nên tự tạo test độc lập ngay lúc đó (như Reviewer vừa làm, < 5 phút) thay vì để lại
   cho Reviewer — rút ngắn vòng lặp.
2. `docs/test-report.md` ghi nhận bug JS console `Cannot read properties of null (reading 'id')` từ
   `f.job.id` tại `web/index.html:145/147` (có từ trước, không thuộc phạm vi 3 dòng review lần này)
   — vẫn còn tồn tại trong file hiện tại, chưa có fix nào trong diff đang review. Giữ nguyên khuyến
   nghị dùng optional chaining `f.job?.id`, không block APPROVE vòng này vì ngoài phạm vi brief.

Script/artifact phiên này (scratchpad, không commit): `alpine_template_test.html`,
`reviewer_check/extracted/` (bản giải nén `sourdough_translated.epub` để đối chiếu X1/X2).

---

# Review Report — US-15 nhánh EPUB (to_markdown, sau khi US-22 unblock) — VÒNG 1/3

**Phạm vi**: `src/services/epub_document.py` (mới: `_spine_hrefs`, `to_markdown()`,
`normalize_sup_sub()`, `_rewrite_image_srcs()`), `src/core/job_orchestrator.py`
(`_run_epub_parse_only()`, `_finalize_parse_only_output()`, xoá `EpubNotSupportedError`),
`src/api/routes/jobs.py` (W-1, W-2), `src/core/config.py` (`markdown_supsub_style`),
`web/index.html` (W-5), + test đi kèm. Đối chiếu với Architecture.md §6.15.7 và §6.21.2.

## 1. Regression US-22 — KHÔNG có

- `git diff -- tests/test_epub_document.py`: xác nhận bằng mắt toàn bộ diff, **0 dòng `-` xoá/sửa**
  nội dung cũ — chỉ có block mới thêm vào cuối file (từ dòng ~1111). 72 test cũ nguyên vẹn 100%,
  bao gồm `test_sup_sub_preserved_verbatim_on_real_fraction_lines` (dòng 275-289) — assert
  `"1<sup>1</sup>/<sub>3</sub>"` còn thô trong `unit.text` cho luồng `units`/dịch EPUB→EPUB —
  KHÔNG bị `normalize_sup_sub()` đụng vào, đúng như Architecture.md §6.15.7 mục C yêu cầu.
- Tự chạy độc lập `uv run pytest tests/test_epub_document.py tests/test_epub_batch_golden_fixture.py -v`
  (không chỉ tin số tổng): **86/86 PASSED** riêng lẻ (72 cũ + 14 mới), không skip, không xfail.
- Tự chạy độc lập `uv run pytest tests/integration/test_job_orchestrator.py tests/integration/test_cost_capped_orchestrator.py -q`
  (baseline PDF parse_only mà CHANGELOG claim "41/41 xanh nguyên"): **41 passed** — khớp đúng.
- Tự chạy toàn bộ suite: `uv run pytest tests/ -q` → **760 passed, 0 failed** (khớp con số Dev báo
  cáo). `uv run ruff check src/ tests/` → **All checks passed!**

**Kết luận câu hỏi quan trọng nhất của PM: KHÔNG có regression US-22 thật nào.**

## 2. 2 test bị THAY — verify là thay đổi có chủ đích đúng, không phải nới lỏng

- `test_run_parse_only_epub_raises_without_calling_mineru` →
  `test_run_parse_only_epub_completes_without_calling_mineru`
  (`tests/integration/test_job_orchestrator.py`): test mới dùng EPUB tối thiểu THẬT hợp lệ OCF
  (mimetype ZIP_STORED đầu tiên, container.xml/opf/ncx/xhtml/ảnh thật), chạy `run_job()` thật (không
  mock `EpubDocument`), rồi mở **thật** zip output ra kiểm `document.md` chứa `"Chuong 1"` +
  `"1/3 cup soy grits"` (xác nhận `normalize_sup_sub()` chạy), và `images/` có đúng 1 ảnh với bytes
  khớp `b"fake-jpeg-bytes"` gốc. Đây là siết chặt hơn test cũ (test cũ chỉ assert raise), đúng tinh
  thần R6-03 "không chỉ tin status".
- `test_create_job_rejects_epub_parse_only_before_creating_job_record` →
  `test_create_job_accepts_epub_parse_only_since_epub_markdown_shipped`
  (`tests/integration/test_upload_and_job_flow.py`): assert `202` + `status="queued"` + đúng 1 Job
  row được tạo (`total == 1`) — khớp đúng hành vi mới sau khi `_reject_epub_parse_only()` bị xoá
  (W-1). Test này chủ động KHÔNG assert hành vi background (nói rõ trong docstring, để riêng cho
  `test_job_orchestrator.py`), hợp lý — tránh test 2 tầng trùng lặp.

Cả 2 đều là thay đổi có chủ đích, khớp mục tiêu chính của US-15 nhánh EPUB, không phải test rỗng.

## 3. `normalize_sup_sub()` — đối chiếu ĐỘC LẬP với bảng golden 7 dòng §6.21.2

Tự viết script gọi trực tiếp `normalize_sup_sub()` (không đọc lại code Dev, chạy độc lập) với đúng 7
input trong bảng "Kết quả đã chạy thật" của Architecture.md §6.21.2 (dòng 6715-6723):

| # | Input | Kỳ vọng (Architecture.md) | Kết quả thật | Khớp |
|---|---|---|---|---|
| 1 | `<sup>1</sup>/<sub>3</sub> cup soy grits` | `1/3 cup soy grits` | `1/3 cup soy grits` | ✅ |
| 2 | `1<sup>1</sup>/<sub>3</sub> cups unbleached white flour` (hỗn số N-1) | `1 1/3 cups unbleached white flour` | `1 1/3 cups unbleached white flour` | ✅ |
| 3 | `Area = x<sup>2</sup> + y<sup>3</sup> - 5x<sup>-1</sup>` | `Area = x² + y³ - 5x⁻¹` | khớp | ✅ |
| 4 | `H<sub>2</sub>O, CO<sub>2</sub>, Ca(OH)<sub>2</sub>, SO<sub>4</sub><sup>2-</sup>` | `H₂O, CO₂, Ca(OH)₂, SO₄²⁻` | khớp | ✅ |
| 5 | `network.<sup>12</sup>` | `network.¹²` | khớp | ✅ |
| 6 | `x<sup>a+b</sup>, V<sub>total</sub>` | `x^(a+b), V_(total)` | khớp | ✅ |
| 7 | `10<sup>-6</sup> mol` | `10⁻⁶ mol` | khớp | ✅ |

**7/7 khớp tuyệt đối, tự verify độc lập (không tin lời Dev)**. Đặc biệt ca N-1 (hỗn số) — điểm dễ
sai nhất theo Architecture.md, đúng loại lỗi `markdownify` mặc định (`11/3`) — đã KHÔNG xảy ra, guard
"ký tự trước `<sup>` là chữ số → chèn dấu cách" hoạt động đúng.

## 4. Thứ tự `normalize_sup_sub()` trước `markdownify` + fix rò rỉ `<body>`

Đọc `to_markdown()` (`epub_document.py:801-843`): thứ tự đúng —
`_rewrite_image_srcs()` → `normalize_sup_sub()` → `converter.convert_soup(body)`, đúng yêu cầu
Architecture.md (chuẩn hoá TRƯỚC khi markdownify nhìn thấy sup/sub, độc lập với `sup_symbol` mặc
định của thư viện).

Fix `convert_soup(soup.find("body"))` thay vì `markdownify.markdownify(str(soup))` — tự verify độc
lập bằng script tái tạo đúng lỗi Dev mô tả: gọi `markdownify.markdownify()` trên soup đầy đủ (có
`<?xml?>` + `<title>`) đúng là làm rò rỉ text `<title>` vào output; dùng `convert_soup(body)` thì
không. Xác nhận fix đúng.

**Phát hiện thêm (non-blocking, KHÔNG có trong spec, Reviewer tự đo)**: code hiện dùng
`body = soup.find("body") or soup` — fallback `or soup` chỉ kích hoạt khi tài liệu XHTML KHÔNG có
thẻ `<body>` nào (vi phạm chuẩn XHTML, nhưng `_parse_xhtml()` không raise nếu thiếu `<body>`, chỉ
raise nếu XML không parse được). Tự test case này:

```
html không có <body>: <html><head><title>Leaky Title</title>...</head><p>Hello</p></html>
convert_soup(soup.find("body") or soup) → "Leaky Title\n\nHello world"   ← <title> RÒ RỈ
```

Khi `<body>` tồn tại (trường hợp thực tế mọi EPUB hợp lệ), `<title>`/`<style>`/`<script>` trong
`<head>` không lọt vào vì `convert_soup()` chỉ nhận đúng phần `<body>` — không có lỗ rò nào ở nhánh
chính. Rủi ro chỉ tồn tại ở nhánh fallback `or soup` cho 1 EPUB có XHTML thiếu hẳn thẻ `<body>` — một
ca hiếm nhưng không phải không thể (một số công cụ export EPUB lỗi có thể sinh fragment không đầy
đủ). Đề xuất non-blocking: đổi guard này thành raise `EpubParseError` rõ ràng khi thiếu `<body>` thay
vì fallback âm thầm sang toàn bộ soup (nhất quán với triết lý "raise rõ ràng thay vì im lặng sai" mà
chính đoạn code này vừa áp dụng cho case ảnh thiếu/URL ngoài).

## 5. Copy ảnh + rewrite link

Đọc `_rewrite_image_srcs()` (`epub_document.py:299-354`): `zip_entry` tính bằng
`posixpath.normpath(posixpath.join(posixpath.dirname(doc_href), src))` — đúng theo `doc_href`
(không phải `opf_dir`), khớp chính xác Architecture.md §6.15.7 mục B. Test edge case đầy đủ và assert
đúng nội dung thật (không hời hợt):
- `test_to_markdown_skips_external_and_data_uri_images` — URL tuyệt đối + `data:` URI giữ nguyên,
  `images_out` rỗng.
- `test_to_markdown_missing_image_entry_does_not_crash` — không raise, `src` giữ nguyên trạng, có
  log warning (đọc code xác nhận `logger.warning(...)` đúng chỗ, không nuốt lỗi im lặng hoàn toàn).
- Trùng basename khác bytes (hậu tố tăng dần `f01_2.jpg`) và trùng basename cùng bytes (gộp 1 file):
  logic đọc đúng (`bytes_by_target[target_name] != data` mới tăng suffix), nhưng **không có test
  trực tiếp cho ca "2 thư mục khác nhau, basename trùng, bytes KHÁC nhau"** trong bộ test mới — chỉ
  có test golden chapter01 (10 ảnh, khả năng cao không trùng basename) và 2 test trên. Đây là
  non-blocking — logic đọc code đúng, nhưng thiếu 1 test trực tiếp cho nhánh "thêm hậu tố" khiến
  hành vi này chưa có golden lock-in nếu ai đó sửa sai sau này.

## 6. Wiring 6 điểm (W-1..W-6)

Đối chiếu từng điểm với bảng Architecture.md §6.15.7 mục E:

- **W-1**: `_reject_epub_parse_only()` đã XOÁ hoàn toàn (grep xác nhận 0 kết quả còn lại trong
  `src/`), cả 2 call site (`create_job`, `create_batch`) đã gỡ đúng.
- **W-2**: `_resolve_parse_method("auto", "epub")` → đọc code xác nhận trả **`None`** (dòng
  `if file_type == "epub": return None`), không còn `"ocr"` vô nghĩa. Type hint đổi đúng
  `str | None`.
- **W-3**: `run_parse_only()` nhánh EPUB gọi `_run_epub_parse_only()`, đặt TRƯỚC
  `_count_pdf_pages()`/guard MinerU — đọc code xác nhận đúng vị trí.
- **W-4**: `EpubNotSupportedError` đã xoá khỏi `job_orchestrator.py`; `test_job_orchestrator.py`
  không còn import (đã sửa cùng lúc với test bị thay ở mục 2).
- **W-5**: `web/index.html` — checkbox ẩn khi `f.file_type === 'epub'` đã thêm đúng vào điều kiện
  `x-show`, kèm comment giải thích lý do.
- **W-6**: xác nhận đúng — không có thay đổi nào ở `download.py` trong diff, khớp Architecture.md
  ("không phải sửa").

`_finalize_parse_only_output()` dùng CHUNG giữa 2 nhánh PDF/EPUB (Protocol 8 R8-03) — đọc code xác
nhận **không có** `if file_type == "epub"` rải rác nào bên trong hàm dùng chung này; điểm rẽ nhánh
duy nhất nằm ở `run_parse_only()` (chọn gọi `_run_epub_parse_only()` hay pipeline PDF), đúng tinh
thần Protocol 8 — rẽ nhánh MỘT LẦN ở điểm vào, không rẽ nhánh rải rác trong thân xử lý dùng chung.

## 7. R6-02 test (nhất quán `len(doc.units)` vs nội dung `to_markdown()`)

`test_to_markdown_r6_02_heading_counts_match_units`: assert `md_h2 == units_h2` và
`md_h3 == units_h3` (đếm thật từ `markdown_text` bằng pattern `"\n## "`/`"\n### "` so với đếm thật
từ `doc.units` theo `tag in {"h2","h3"}`), CÙNG một lần `load()` — đúng tinh thần Protocol 6 (không
so sánh 2 con số cố định độc lập, mà so sánh chéo giữa 2 projection sinh ra từ cùng 1 lần đọc dữ
liệu gốc). Docstring ghi rõ lý do sourdough không có ca `_is_droppable_content()` drop heading
toàn-chữ-số (0 ca, khớp tuyệt đối), và cảnh báo rõ nếu sách khác có ca đó thì phải trừ đúng số bị
drop — không nới `>=`. Đúng yêu cầu.

## 8. R5-04 checklist (Protocol 5)

`epub_document.py` không gọi API/CLI/HTTP service bên thứ ba nào mới — `markdownify` là thư viện
Python thuần (import trực tiếp), version đã verify `1.2.3` qua `importlib.metadata` (đọc
Architecture.md §6.15.7 mục D, khớp). Theo phạm vi áp dụng Protocol 5/CLAUDE.md project ("không áp
dụng cho thư viện nội bộ Python thuần... `pymupdf` dùng đúng API core"), `markdownify` cùng loại rủi
ro thấp này → **N/A cho R5-01 chính thức**, nhưng phát hiện hành vi ngầm định của
`markdownify.markdownify()` (re-parse toàn chuỗi qua `html.parser`, rò rỉ XML declaration/`<title>`)
là một phát hiện đúng tinh thần Protocol 5 dù ngoài phạm vi bắt buộc — Dev đã tự đo và ghi lại đúng
cách (R5-04: "External contract verified against real source: N/A — thư viện Python thuần, nhưng có
verify hành vi thật qua chạy thử độc lập"). Reviewer tự tái tạo lại phát hiện này ở mục 4, xác nhận
đúng.

## Kết luận

**APPROVE.**

- KHÔNG có regression US-22 (xác nhận bằng đọc diff + chạy test độc lập, không chỉ tin lời Dev).
- `normalize_sup_sub()` khớp 100% (7/7) bảng golden §6.21.2, tự verify độc lập bằng script riêng.
- 2 test bị thay là thay đổi có chủ đích đúng, siết chặt hơn test cũ, không phải nới lỏng che giấu
  lỗi.
- Thứ tự `normalize_sup_sub()` trước `markdownify`, fix rò rỉ `convert_soup(body)`, rewrite ảnh theo
  `doc_href`, wiring W-1..W-6, Protocol 8 (hàm dùng chung không rẽ nhánh rải rác), R6-02 — đều đúng
  spec Architecture.md §6.15.7/§6.21.2.
- `uv run pytest tests/ -q` → 760 passed. `uv run ruff check src/ tests/` → All checks passed.

**Non-blocking (không chặn approve, ghi lại cho lần sau)**:
1. `to_markdown()`: `soup.find("body") or soup` — fallback này rò rỉ `<title>`/nội dung `<head>` vào
   Markdown output nếu 1 tài liệu XHTML trong spine thiếu hẳn thẻ `<body>` (case hiếm nhưng có thể
   xảy ra với EPUB xuất lỗi). Đề xuất: raise `EpubParseError` rõ ràng thay vì fallback âm thầm, nhất
   quán với cách xử lý "raise rõ ràng" đã áp dụng cho các guard khác trong cùng file.
2. Thiếu 1 test trực tiếp (golden, không suy luận từ đọc code) cho nhánh "2 basename trùng tên khác
   thư mục, bytes KHÁC nhau → thêm hậu tố `_2`" của `_rewrite_image_srcs()` — logic đọc đúng nhưng
   chưa có test khoá hành vi này lại.

**External contract verified against real source**: N/A cho `markdownify` (thư viện Python thuần,
theo phạm vi Protocol 5 project) — nhưng hành vi ngầm định `markdownify.markdownify()` (rò rỉ XML
declaration khi re-parse toàn chuỗi) đã được Dev VÀ Reviewer tự chạy thử độc lập xác nhận (không chỉ
đọc doc).

---

# Review Report — Bump pyproject.toml version 1.2.9→1.3.1 (fix quên bump ở 2 release trước) — VÒNG 1/3

**Context**: PM phát hiện 2 commit `27d7daa` (Release v1.3.0) và `c38a184` (Release v1.3.1) quên
bump `pyproject.toml` (vẫn ghi `1.2.9`), vi phạm quy ước project (mọi commit "Release vX.Y.Z" trước
đó đều bump `pyproject.toml` cùng commit). PM tự sửa `pyproject.toml` version → `1.3.1`.

**Kiểm tra đã thực hiện** (tự chạy, không suy đoán):
1. `git diff pyproject.toml` — xác nhận đúng 1 dòng thay đổi: `version = "1.2.9"` →
   `version = "1.3.1"`. Không có thay đổi nào khác lọt vào file (dependencies, requires-python,
   description... giữ nguyên).
2. `git log --oneline --all | grep -i "release v1.3"` → thứ tự commit đúng: `27d7daa Release
   v1.3.0` trước, `c38a184 Release v1.3.1` sau (v1.3.1 là commit mới nhất). `project_state.json`
   field `"version": "1.3.1"` (dòng 5) khớp. Số `1.3.1` là ĐÚNG số cuối cùng cần bump tới, không
   phải `1.3.0`.
3. `grep -rn "1\.2\.9" src/ web/` → không có kết quả. Không có nơi nào khác hardcode version cũ cần
   đồng bộ theo.
4. Đọc `src/api/main.py::_read_app_version()` (dòng 64-74) — xác nhận đọc trực tiếp
   `pyproject.toml` qua `tomllib` tại runtime mỗi lần gọi, không cache, không dùng
   `importlib.metadata`. Claim của PM về hành vi endpoint `/api/version` là đúng theo source code
   (khớp với kết quả `curl` PM báo cáo).

**External contract verified against real source**: N/A — `pyproject.toml` là file cấu hình nội bộ
project, không phải external tool/SDK theo phạm vi Protocol 5.

**Kết luận**: APPROVE. Thay đổi đúng, tối thiểu, đúng phạm vi. Không có regression, không có
side-effect ngoài dự kiến.

**Non-blocking (không chặn approve, ghi lại cho lần sau)**:
1. Root cause (quên bump version trong 2 commit "Release" trước) chưa có cơ chế ngăn tái diễn —
   nên cân nhắc thêm 1 check tương tự pre-commit hook Protocol 7 (R7-02): chặn/cảnh báo commit có
   tiêu đề "Release vX.Y.Z" nếu `pyproject.toml` không nằm trong cùng commit, hoặc version trong
   `pyproject.toml` không khớp X.Y.Z trong tiêu đề.

# Review Report — Fix Bug #EPUB-3 (job mồ côi khi server restart) — VÒNG 1/3

## Phạm vi

- `src/core/job_recovery.py` (file mới)
- `src/api/main.py::lifespan()`
- `src/models/job.py` (comment fix)
- `tests/integration/test_orphan_job_recovery.py` (file mới, 7 test)

Đối chiếu với spec Tech Lead `docs/Architecture.md` §E3 (E3.1 → E3.9), đọc toàn bộ. Working tree
chưa commit tại thời điểm review (`git status`: modified `docs/Architecture.md`, `docs/CHANGELOG.md`,
`src/api/main.py`, `src/models/job.py`, `uv.lock`; untracked `src/core/job_recovery.py`,
`tests/integration/test_orphan_job_recovery.py`).

## 1. `src/core/job_recovery.py::fail_orphaned_jobs()`

- `_ORPHAN_JOB_STATUSES` (dòng 29-37): `{created, queued, chunking, parsing, translating,
  post_processing, merging}` — đúng 7 giá trị §E3.3. Đối chiếu tay với `_ACTIVE_JOB_STATUSES`
  (`src/api/routes/jobs.py:821-833`) — trùng khớp 100%, và code KHÔNG import lại set đó (chỉ
  comment trỏ chéo), đúng lý do tách biệt "business rule" ở §E3.3.
- `error_message` (dòng 43-46): so khớp nguyên văn từng ký tự với câu Tech Lead chốt ở §E3.4 —
  khớp 100%, không bị Dev diễn đạt lại (kể cả dấu gạch ngang em-dash `—` giữa 2 vế câu).
- `finished_at = job.finished_at or now` (dòng 68) và `updated_at = now` (dòng 69) — đúng §E3.4.
  `progress`/`current_chunk`/`total_chunks`/`actual_cost` không bị đụng (không có dòng gán nào cho
  4 field này trong hàm) — đúng.
- `Chunk` không được import/query ở đâu trong file — đúng §E3.5 (không đụng `Chunk.status`).
- `Batch` không được import/query — đúng §E3.4 (không quét Batch).
- 1 `session.commit()` duy nhất sau vòng lặp (dòng 77-78), có gate `if jobs:` — idempotent đúng
  thiết kế (lần gọi thứ 2 không có job nào match → không commit rỗng, trả 0).
- Dùng `select(Job).where(col(Job.status).in_(...))` qua SQLModel — không raw SQL, đúng §E3.7.

Không có vấn đề ở file này.

## 2. `src/api/main.py::lifespan()`

```python
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    async with get_session_factory()() as session:
        await fail_orphaned_jobs(session)
    yield
```

Đúng vị trí: sau `await init_db()`, trước `yield` — khớp yêu cầu brief PM mục 2 và §E3.7. Off-by-
order ngược lại (gọi trước `init_db()`) sẽ crash vì bảng `jobs` chưa tồn tại — đã tự xác nhận bằng
cách đọc thứ tự dòng thật trong file (`git diff` hunk), không suy đoán.

## 3. `src/models/job.py` — comment fix

Dòng 32-34 (sau sửa): `created | queued | chunking | parsing | translating | post_processing |
merging | completed | failed | cancelled | cost_capped` — đủ 11 giá trị, không mất status nào so
với comment cũ (đối chiếu `git diff` hunk: chỉ có `+` thêm `parsing` vào đúng vị trí giữa
`chunking` và `translating`, không có dòng nào bị xoá khỏi danh sách gốc). Đúng.

## 4. Data lineage (Protocol 6) — retry sau orphan có dịch lại chunk đã completed không

Tự đọc kỹ (không tin lời Dev) 2 test liên quan:

- **Test 6** (`test_completed_chunks_survive_orphan_mark`): tạo 3 `Chunk` (`completed`,
  `translating`, `pending`) cho 1 job `translating`, gọi `fail_orphaned_jobs()`, assert
  `Chunk.status` của cả 3 **không đổi**. Đây CHỈ chứng minh `fail_orphaned_jobs()` không tự ý đụng
  `Chunk.status` — không chứng minh chunk `completed` thực sự bị/không bị dịch lại khi resume.
- **Test 5** (`test_retry_after_orphan_mark_succeeds`): gọi `POST /api/jobs/{id}/retry`, assert
  `status == "queued"`, `error_message is None`, `cancel_requested is False`. Không có `Chunk` nào
  được tạo trong test này, và test **không** chạy job đến khi hoàn tất, cũng không đếm số lần gọi
  translation provider.

**Kết luận cho mục này**: KHÔNG có test nào trong bộ 7 test thực sự đếm số lần gọi provider hoặc
chạy `run_job()`/`_process_chunk()` thật để verify chunk `completed` không bị dịch lại/tính lại
cost sau resume. Claim "chunk completed sống sót → không dịch lại" trong CHANGENLOG mục 2 test 6
dựa trên: (a) test 6 xác nhận `fail_orphaned_jobs()` không đụng `Chunk.status`, cộng với (b) đọc
tĩnh code `job_orchestrator.py:578`/`:916` (`if chunk.status != "completed":`) và `:1090` (merge
chỉ lấy chunk `completed`) — tức là **suy luận từ 2 sự thật độc lập đã verify riêng lẻ**, không
phải 1 test động end-to-end duy nhất chứng minh trực tiếp.

Đây khớp đúng những gì §E3.8 mục 6 của Architecture.md yêu cầu Dev viết (bản thân spec Tech Lead
cũng chỉ yêu cầu assert `Chunk.status` không đổi, không yêu cầu đếm provider call) — nên **không
phải Dev làm sai spec**. Nhưng đây là khoảng cách thật giữa "test có" và "khẳng định hành vi runtime
đầy đủ" mà PM nên biết trước khi coi bug này đã được test triệt để bằng dynamic test. Ghi nhận làm
**non-blocking suggestion**, không chặn approve vì: (1) đúng theo spec đã chốt, (2) rủi ro thấp —
logic skip chunk `completed` đã tồn tại từ trước (không phải code mới của fix này), tự nó có thể
đã/nên được test riêng ở integration test resume flow (`test_job_orchestrator.py` hoặc tương tự) —
ngoài phạm vi §E3.

## 5. `Event loop is closed` / `PytestUnhandledThreadExceptionWarning`

Tự xác nhận bằng thực nghiệm, không tin lời Dev:

```
git stash -u   # tạm bỏ toàn bộ thay đổi của fix này (bao gồm cả 2 file mới)
uv run pytest tests/ -q 2>&1 | grep -c "Event loop is closed"   → 40
git stash pop  # khôi phục lại
```

**Xác nhận: warning `RuntimeError: Event loop is closed` (nguồn: `aiosqlite/core.py` +
`threading.py`, không liên quan `job_recovery.py`/test mới) xuất hiện SẴN 40 lần ở baseline khi
CHƯA CÓ bất kỳ thay đổi nào của fix Bug #EPUB-3** — pre-existing, không phải do fix này gây ra.
Đây là hành vi đã biết của `aiosqlite` + `TestClient`/`anyio` portal thread khi event loop bị đóng
trước khi connection worker thread kịp báo lỗi, không đặc thù cho `test_orphan_job_recovery.py`.

(Lưu ý thao tác: `git stash pop` gặp conflict giả trên `uv.lock` do `uv run` tự resolve lại version
trong lúc test baseline chạy — đã `git checkout -- uv.lock` trước khi pop để tránh mất thay đổi
thật; xác nhận `git diff --stat` sau khi pop khớp 100% với trước khi stash.)

## 6. 6 test case §E3.8 + test lifespan (7 tổng)

Đọc toàn bộ `tests/integration/test_orphan_job_recovery.py` (324 dòng):

1. `test_marks_every_orphan_status_as_failed` — đủ 7 status, đúng.
2. `test_does_not_touch_terminal_status_jobs` — **đã tự xác nhận không phải test rỗng**: dùng
   `original_error_messages`/`original_finished_at` (dict theo `job.id`, snapshot TRƯỚC khi gọi
   hàm) rồi so sánh giá trị cụ thể sau khi gọi (dòng 97-107) — không chỉ assert `status` còn nằm
   trong `_TERMINAL_STATUSES`. Đúng như brief PM yêu cầu xác nhận.
3. `test_keeps_progress_fields_unchanged` — đúng, assert 4 giá trị cụ thể.
4. `test_second_call_is_idempotent` — đúng, so sánh `finished_at` không đổi giữa 2 lần gọi.
5. `test_retry_after_orphan_mark_succeeds` — dùng `TestClient` + DB thật qua `tmp_path`, đúng R6-02
   (nối 2 bước) — xem giới hạn đã nêu ở mục 4.
6. `test_completed_chunks_survive_orphan_mark` — xem giới hạn đã nêu ở mục 4.
7. `test_lifespan_marks_orphan_jobs_before_serving_requests` — seed job orphan vào DB TRƯỚC khi
   `TestClient(app)` được khởi tạo (kích hoạt `lifespan()` thật qua `with TestClient(app) as
   test_client:`), sau đó chỉ GET để xác nhận job đã bị mark — đúng tinh thần "không tự trigger,
   chỉ xác nhận đã xảy ra". Đúng, và đây là test duy nhất verify thứ tự thật của `lifespan()`
   (không chỉ đọc code bằng mắt).

Đủ 7/7, không có test rỗng, không có test chỉ assert `status` mà bỏ qua giá trị field quan trọng.

## 7. Chạy lại độc lập

```
uv run ruff check src/ tests/     → All checks passed!
uv run pytest tests/ -q           → 767 passed, 1049 warnings in 111.16s
```

767/767 khớp đúng số Dev báo cáo.

## Kết luận

**APPROVE.**

Implementation khớp chính xác với spec §E3 ở mọi điểm được kiểm tra: tập trạng thái orphan, câu
`error_message` nguyên văn, vị trí `lifespan()`, phạm vi field bị/không bị đụng, comment fix
`job.py`. Ruff sạch, 767/767 test pass, không regression. Warning `Event loop is closed` xác nhận
pre-existing (40 lần ở baseline không có fix), không phải do thay đổi này gây ra.

**Non-blocking (không chặn approve)**:
1. (Mục 4 ở trên) Chưa có test động end-to-end đếm provider call để verify trực tiếp "chunk
   completed không bị dịch lại sau resume" — hiện dựa vào suy luận từ 2 test riêng lẻ + đọc tĩnh
   code. Đúng theo spec §E3.8 đã chốt, không chặn approve, nhưng nên cân nhắc thêm 1 test resume
   thật (đếm `provider.translate` call count trước/sau) ở phạm vi rộng hơn §E3 nếu có increment
   sau đụng lại luồng resume.

**External contract verified against real source**: N/A — không có lời gọi external
tool/CLI/HTTP/SDK provider nào trong `job_recovery.py` hoặc thay đổi trong `main.py`/`job.py` (chỉ
DB nội bộ qua SQLModel). Không thuộc phạm vi Protocol 5.


---

# Review Report — Port Protocol A–F + mở rộng 2/3/4 từ AB-RnD (hạ tầng quy trình) — VÒNG 1/3

**Phạm vi**: `scripts/validate_state.py` (mới), `.git/hooks/pre-commit` (khối bổ sung cuối file),
`project_state.schema.json` (mới), `project_state.json` (viết lại từ văn xuôi sang cấu trúc),
`CLAUDE.md` + `.claude/agents/*.md` (chỉ kiểm tính nhất quán). Không đụng `src/`/`web/` — xác nhận
`src/api/main.py`, `src/models/job.py`, `src/core/job_recovery.py` là công việc Bug #EPUB-3 của đợt
trước (đã commit ở `3ed0088`/`727629b`, không còn xuất hiện trong `git status` hiện tại) — không
review, không đụng vào.

**External contract verified against real source**: N/A — không có wrapper nào gọi tool/API bên thứ
3 trong phạm vi đợt này (`validate_state.py` chỉ đọc file cục bộ bằng stdlib). Không thuộc Protocol 5.

## 1. Phương pháp kiểm

Tự tạo 14 file `project_state.json` hỏng có chủ đích trong một **git repo cô lập** dựng riêng tại
scratchpad (không đụng vào `project_state.json` thật của repo), chạy `scripts/validate_state.py` và
`bash .git/hooks/pre-commit` (bản copy) lên từng file để xác nhận validator/hook thực sự bắt lỗi nó
tuyên bố bắt. Sau khi xong, xác nhận `git diff --stat project_state.json` ở repo thật rỗng — file gốc
không bị đụng.

## 2. Validator có bắt đúng các vi phạm nó tuyên bố không — CÓ, với 7/7 case yêu cầu

| Case | Kết quả |
|---|---|
| `steps[].status=done` thiếu `output` | ❌ bắt đúng: "step S1: status=done nhưng thiếu output" |
| `loops[].count > limit` mà `escalated_at=null` | ❌ bắt đúng: "count 5 > limit 3 nhưng chưa escalate" |
| `blockers[]` chứa câu văn thay vì id | ❌ bắt đúng (qua nhánh heuristic `" " in b or len(b)>20`) |
| `infra_pending[]` quá 24h `commit=null` | ❌ bắt đúng: "quá 24h chưa có commit (Protocol E)" |
| `infra_pending[]` còn trong 24h, `commit=null` | ✅ pass đúng (không báo lỗi sai) |
| `open_questions[].clarify_rounds > 2` | ❌ bắt đúng: "clarify_rounds > 2 (Protocol B)" |
| `text` vượt 220 ký tự | ❌ bắt đúng, đếm đúng số ký tự thực tế (221) |

`check_blockers()` đáng chú ý: heuristic "trông như câu văn" (`" " in b or len(b) > 20`) tự nó không
đủ vét cạn (vd một chuỗi 15 ký tự không dấu cách vẫn "trông như id"), nhưng nhánh `elif b not in
known_ids` phía sau vẫn chặn được các trường hợp đó vì gần như chắc chắn không khớp id thật nào — hai
lớp kiểm tra bù nhau, không phải lỗ hổng. Xác nhận đây là thiết kế chấp nhận được.

`parse_day()` (đúng như câu hỏi trong brief): value rác (vd `"khong phai ngay thang"`) khiến
`date.fromisoformat` raise `ValueError`, hàm trả `None`, và `check_infra()` **bỏ qua hoàn toàn** mục
đó — không fail, **không cả warn**. Xác nhận bằng case `case_infra_garbage_date.json`: một
`infra_pending` có `commit=null` và `applied_at` không parse được chạy qua validator cho kết quả
"✅ hợp lệ", 0 lỗi, 0 cảnh báo. Đây **là lỗ hổng im lặng thật**, không phải "chấp nhận được" — xếp
blocking bên dưới (mục 4.1).

## 3. Validator có khớp schema không — KHÔNG, lệch đáng kể

`project_state.schema.json` và `validate_state.py` được viết tay tách rời như brief mô tả, và thực sự
**lệch nhau ở phần lớn ràng buộc cấu trúc**, không chỉ vài trường lẻ tẻ. Verify bằng 6 case bổ sung
(cùng phương pháp cô lập ở mục 1) — mỗi case vi phạm rõ ràng 1 ràng buộc `project_state.schema.json`
khai báo, tất cả đều lọt qua `validate_state.py` với kết quả "✅ hợp lệ":

| Case (vi phạm ràng buộc schema nào) | Kết quả validator |
|---|---|
| `open_questions[].id` không khớp pattern `^(HOI\|BUG)-[0-9]+...$` | ✅ "hợp lệ" (SAI — phải fail) |
| `backlog[].id` không khớp pattern `^BL-[0-9]+$` | ✅ "hợp lệ" (SAI) |
| `project_name` dài 200 ký tự (schema `maxLength: 80`) | ✅ "hợp lệ" (SAI) |
| `steps[].id` dài hơn 12 ký tự (schema `maxLength: 12`) | ✅ "hợp lệ" (SAI) |
| `checkpoints[]` có field lạ `unexpected_field` (schema `additionalProperties: false`) | ✅ "hợp lệ" (SAI) |
| top-level có field lạ `totally_unexpected_top_field` (schema `additionalProperties: false`) | ✅ "hợp lệ" (SAI) |

Đối chiếu toàn bộ: `validate_state.py` chỉ thực sự kiểm tra ~9 luật nghiệp vụ tường minh (status
enum, `done`+`output`, `stale`+`status_reason`, `answered`+`answered_in`, `clarify_rounds>2`,
`text`>220 cho 2 mảng, `count>limit`+`escalated_at`, `infra` 24h, `blockers` heuristic+membership) —
**không hề implement** `additionalProperties: false` (ở BẤT KỲ cấp nào, kể cả top-level), không
implement bất kỳ `pattern` nào, và chỉ implement `maxLength` cho đúng 2 trường (`open_questions.text`,
`backlog.text`) trong số ~15 trường có `maxLength` khai báo trong schema.

Ngược chiều (validator strict hơn schema) không phát hiện trường hợp nào đáng kể.

`project_state.json` hiện tại (bản mới) **có hợp lệ theo chính schema của nó** — verify độc lập bằng
script Python tự viết (không dùng `validate_state.py`, không có `jsonschema` trong `.venv` nên đối
chiếu tay `required`/`additionalProperties`/`maxLength`/`pattern` cho từng field): không phát hiện vi
phạm nào. Bản thân file dữ liệu OK — vấn đề nằm ở **cơ chế validate**, không phải ở data hiện tại.

## 4. Issues

### Blocking

1. **`parse_day()` — lỗ hổng im lặng, không cả warning** (`scripts/validate_state.py:63-68,
   154-172`). Một `infra_pending` item có `applied_at` không parse được (sai định dạng, gõ nhầm,
   copy-paste lỗi) bị bỏ qua vĩnh viễn khỏi kiểm tra 24h — kể cả khi `commit=null`. Đây đúng là kiểu
   lỗi "2 thứ tự nhất quán với chính nó, không ai kiểm tra sợi dây nối" mà chính CLAUDE.md dự án này
   (Protocol 5/6) được viết ra để phòng — chỉ khác là lần này lỗ hổng nằm trong chính cơ chế phòng
   thủ. Đề nghị tối thiểu: gọi `warn()` khi `parse_day()` trả `None` (không được im lặng hoàn toàn);
   cân nhắc `fail()` luôn vì "không parse được ngày" tự nó đã là dữ liệu hỏng.

2. **`validate_state.py` không thực thi phần lớn ràng buộc cấu trúc mà `project_state.schema.json`
   khai báo** — xem bảng ở mục 3. Nghiêm trọng nhất là **`additionalProperties: false` bị bỏ qua
   hoàn toàn ở mọi cấp** (kể cả top-level): một field gõ nhầm tên (vd `"statuss"` thay vì `"status"`)
   sẽ lọt qua validator + hook mà không có bất kỳ cảnh báo nào — trong khi đây chính là kiểu bug (gõ
   sai field, 2 phía không đồng bộ với nhau) mà toàn bộ nỗ lực đưa `project_state.json` từ văn xuôi
   sang có-cấu-trúc-theo-schema hướng tới giải quyết. `pattern` cho `open_questions[].id` và
   `backlog[].id` cũng không được kiểm, nên id sai định dạng (vd không đúng tiền tố `HOI-`/`BUG-`/
   `BL-`) sẽ không bị chặn dù schema có khai báo.
   Đề nghị 1 trong 2 hướng (Dev/Tech Lead chọn, không cần quay lại Hiếu vì đây là chi tiết hiện thực,
   không đổi phạm vi đã duyệt):
   - (a) Viết 1 checker generic đọc trực tiếp `project_state.schema.json` và tự áp `required` /
     `additionalProperties` / `maxLength` / `pattern` / `enum` bằng đệ quy thuần stdlib (không cần
     thêm dependency `jsonschema`, khối lượng code không lớn vì schema ở đây không dùng `oneOf`/`$ref`
     phức tạp) — loại bỏ hẳn nguy cơ lệch giữa 2 file được duy trì tay riêng rẽ; hoặc
   - (b) Nếu giữ nguyên cách viết tay từng luật nghiệp vụ như hiện tại, phải đổi tên/docstring cho
     rõ ràng rằng đây là "business-rule checker", KHÔNG phải "schema validator" — để không ai (kể cả
     Hiếu) hiểu nhầm là `project_state.json` đã được validate đầy đủ theo `project_state.schema.json`
     chỉ vì `validate_state.py` chạy xanh.
   Không chặn việc dùng `project_state.schema.json` làm tài liệu tham chiếu con người đọc — chỉ chặn
   việc coi 2 file này tương đương nhau về mặt thực thi.

### Non-blocking

1. `project_state.json`: `phase: "build"` nhưng `released_at: "2026-09-10"` vẫn còn set (rơi rớt từ
   sự kiện release v1.3.2 trước khi bắt đầu S2). Không vi phạm schema (schema không ràng buộc quan hệ
   2 field này) nhưng gây hiểu nhầm khi đọc nhanh state. Đề nghị PM dọn lại `released_at: null` khi
   quay về `phase=build`, hoặc thêm luật `phase != released → released_at phải null` vào cả schema
   (`if/then` draft-07 hỗ trợ) lẫn validator nếu muốn enforce.
2. Không có kiểm tra trùng `id` trong cùng 1 mảng (`steps[].id`, `checkpoints[].id`,
   `open_questions[].id`, `backlog[].id`, `loops[].pair+item`) — cả schema (draft-07 khó diễn đạt
   "unique theo 1 field" mà không phải `uniqueItems` toàn phần tử) lẫn validator đều bỏ qua. Rẻ để
   thêm (1 `set()` mỗi mảng, so `len` trước/sau) và bắt được lỗi copy-paste khi PM tạo id mới bằng
   tay. Không có bằng chứng đã xảy ra ở data hiện tại — chỉ là gap phòng ngừa.
3. Docstring/comment của `validate_state.py` không nói rõ giới hạn phạm vi (xem Blocking #2) — nếu
   chọn hướng (b) ở trên thì nên bổ sung 1 dòng comment đầu file.

## 5. Hook (`.git/hooks/pre-commit`)

- Khối Protocol 1 cũ (chặn commit đổi `src/`/`web/` thiếu `review-report.md`) **giữ nguyên**, không
  bị đụng.
- Khối mới gọi `python3 scripts/validate_state.py` với guard `if [[ -f scripts/validate_state.py ]]`
  — hợp lý cho giai đoạn bootstrap (script chưa từng tồn tại ở các commit cũ hơn không bị vỡ khi
  checkout ngược).
- Xác nhận đường dẫn tương đối `scripts/validate_state.py` đúng: đã test thực tế bằng cách chạy
  `git commit` từ một thư mục con lồng sâu (`src/sub/`) trong repo cô lập — hook vẫn chạy đúng vì Git
  luôn set cwd của hook về root của working tree, không phụ thuộc cwd lúc gọi `git commit`.
- Test cô lập (repo riêng ở scratchpad, không phải repo thật): (1) code đổi + review-report không
  đổi → BLOCK đúng thông điệp Protocol 1; (2) review-report có đổi + state hỏng
  (`blockers` chứa câu văn) → Protocol 1 pass, Protocol 4 mở rộng BLOCK đúng thông điệp. Cả 2 gate
  hoạt động độc lập, đúng như thiết kế, không có luồng ghi đè lẫn nhau.
- Chạy `bash .git/hooks/pre-commit` trực tiếp ở repo thật (không có gì staged) → exit 0, không side
  effect, không đổi `project_state.json` (`git diff --stat` rỗng sau khi chạy) — không làm hỏng
  luồng commit bình thường.

## 6. Ruff

```
.venv/bin/ruff check scripts/validate_state.py       → All checks passed!
.venv/bin/ruff format --check scripts/validate_state.py → 1 file already formatted
```

Type hints đầy đủ cho mọi function signature trong `validate_state.py` (bao gồm `-> set[str]`,
`-> None`, `-> int`, tham số đều có annotation) — đạt tiêu chí review.

## 7. Không mất nội dung khi tách/rotate tài liệu (Protocol C)

Tự trích toàn bộ heading Markdown (`#`–`####`) từ 3 cặp file, so sánh tập hợp:

- `docs/Architecture.md` (HEAD, trước tách) vs (`docs/Architecture.md` mới + `docs/design-log.md`
  mới) ở working tree: **0 heading nào bị mất** — mọi heading ở bản HEAD đều xuất hiện lại ở 1 trong
  2 file mới.
- `docs/review-report.md` (HEAD, trước rotate) vs (`docs/review-report.md` mới +
  `docs/archive/review-report-until-2026-09-10.md`): **0 heading nào bị mất**.

Lưu ý: `docs/Architecture.md` ở HEAD (12.591 dòng) đã KHÔNG bao gồm phần Bug #EPUB-3 vốn nằm ở
working tree trước đó — chênh lệch dòng giữa HEAD và tổng 2 file mới (~299 dòng) không phải mất nội
dung, mà do so sánh ở 2 thời điểm khác nhau của lịch sử git; kiểm bằng heading-set nên không bị ảnh
hưởng bởi mốc thời gian này.

## 8. Nhất quán CLAUDE.md / `.claude/agents/*.md` (kiểm nông theo yêu cầu)

- Ngân sách dòng trong `CLAUDE.md` Protocol C.3 (Architecture 8.000 / design-log 8.000 / CHANGELOG
  8.000 / review-report 4.000 / test-report 4.000 / PRD 2.000) khớp chính xác với `DOC_LINE_BUDGET`
  trong `validate_state.py`.
- `clarify_rounds ≤ 2` (Protocol B) khớp với `QUESTION_STATUS`/check trong validator (`> 2` fail).
- Mọi file `documents{}` trong `project_state.json` trỏ tới đường dẫn tồn tại thật:
  `docs/escalation-log.md`, `docs/decisions-archive.md`, `docs/expert-notes/`, `docs/archive/` — đã
  `ls` xác nhận cả 4 tồn tại.
- `.claude/agents/reviewer.md` (bản mới) tự mô tả đúng checklist R5-04/R6-04/R8-01 — khớp với những
  gì report này đang làm theo.
- Không kiểm sâu nội dung nghiệp vụ của `ba.md`/`dev.md`/`pm.md`/`qa.md`/`tech-lead.md`/
  `domain-expert.md`/`critic.md` theo đúng phạm vi brief ("chỉ kiểm tính nhất quán, không cần review
  sâu").

## Kết luận

**REJECT** (Vòng 1/3) — 2 blocking issue, cả hai đều nằm trong `scripts/validate_state.py` (mục 4).
Không phải lỗi thiết kế tổng thể: hook, schema, `project_state.json`, và phần lớn business-rule check
trong validator đều đúng và đã verify chạy thật. Cần Dev sửa 2 điểm ở mục 4 (silent hole của
`parse_day()`, và khoảng trống enforcement giữa validator/schema) rồi gửi lại. Không có vi phạm
Protocol 5/6/7 nào trong đợt này (R5-04 = N/A, không có external tool wrapper trong phạm vi).

---

# Review Report — Fix backlog BL-01/02/03/05 — VÒNG 1/3

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-10
- **Circuit breaker Dev↔Reviewer (fix backlog BL-01/02/03/05)**: vòng 1/3
- **Phạm vi review**: 4 mục backlog độc lập từ Dev, theo `docs/CHANGELOG.md` entry "Fix 4 mục backlog
  kỹ thuật nhỏ — BL-01/02/03/05 (Dev, 2026-09-10)". Diff đọc trực tiếp: `src/core/job_orchestrator.py`,
  `src/api/routes/jobs.py`, `tests/integration/test_job_orchestrator.py`,
  `tests/integration/test_cost_gate_api.py`, `tests/integration/test_upload_and_job_flow.py`,
  `tests/integration/test_settings_api.py`, `tests/integration/test_epub_translate_guards.py`.

## Verdict: APPROVE (cả 4 mục)

## 1. BL-05 (ưu tiên cao nhất) — ghi `chunk.api_cost`/`api_tokens_used` trước 2 raise EPUB

**Đọc code trực tiếp** `_process_epub_chunk()` (`job_orchestrator.py`):
- `total_input_tokens`/`total_output_tokens`/`total_cost` là biến cục bộ, cộng dồn qua
  `_accumulate_and_check_budget()` (dùng `nonlocal`) cho **MỌI** lần gọi `pricing_provider.translate`
  trong chunk (request chính + mọi lần retry: single-id, whole-request, diacritic tier 1/2) — xác
  nhận đây đúng là tổng chi phí THẬT đã tiêu tới thời điểm raise, không phải chỉ request cuối.
- Điểm raise `EpubRequestRunawayError` (dòng ~2141-2144, ngay sau `raise` gốc R-b) và điểm raise
  `EpubBatchTranslationError` (dòng ~2370-2373, sau ngưỡng fallback C-2): cả 2 đều ghi
  `chunk.api_tokens_used = total_input_tokens + total_output_tokens`,
  `chunk.api_cost = total_cost`, `db_session.add(chunk)`, `await db_session.commit()` **ngay trước**
  `raise`, đúng pattern `EpubChunkCostCapExceeded` đã làm đúng từ trước (dòng ~2081-2086).
- `chunk.status` **không** bị đổi ở 2 block mới — xác nhận qua đọc trực tiếp diff + docstring
  `EpubRequestRunawayError` (dòng 153: "xu ly no qua nhanh `except Exception` chung da co san (chunk
  `failed`, ...)") — outer handler ở `run_epub_job()` vẫn là nơi set `"failed"`, đúng claim CHANGELOG.
- `chunk.output_path` không bị set ở 2 block mới (chỉ set ở dòng 2426 sau khi hoàn tất toàn bộ) — vẫn
  giữ `None`/giá trị cũ, khớp assertion test `chunk.output_path is None`.

**Tự chạy độc lập** (không tin lại lời Dev):
- `pytest tests/integration/test_epub_translate_guards.py -k
  "test_epub_batch_translation_error_still_records_cost_of_prior_successful_request or
  test_epub_request_runaway_error_still_records_cost_of_prior_successful_request"` → **2 passed**
  trên code hiện tại.
- `git stash push -- src/core/job_orchestrator.py` rồi chạy lại đúng 2 test đó → **2 failed** (cả hai
  fail đúng chỗ dự kiến: `chunk.api_cost` không phản ánh tổng chi phí tích luỹ). `git stash pop` khôi
  phục sạch. → claim "fail trên code cũ, pass trên code mới" là THẬT, không phải Dev tự nhận.
- Đọc kỹ assertion: cả 2 test dùng `_CostTrackingEpubProvider` ghi lại `estimated_cost_usd` THẬT của
  từng lần gọi (không hardcode, tính từ `0.000001 * (len(text) + output_tokens)` ở
  `_ControllableEpubProvider.translate`, dòng 131), rồi so `chunk.api_cost ==
  pytest.approx(sum(provider.observed_costs))` VÀ `chunk.api_cost > provider.observed_costs[0]` — điều
  kiện thứ hai loại trừ chính xác failure mode nguy hiểm nhất ("chỉ ghi cost request cuối, không cộng
  dồn"). Test không rỗng, không tự thoả mãn giả định — đủ tin cậy.

**Kết luận BL-05: ĐÚNG và ĐÁNG TIN.** Đây là fix rủi ro tài chính cao nhất trong 4 mục, đã verify kỹ
nhất và không phát hiện vấn đề.

## 2. BL-01 — `font_shrink_page()` giới hạn đúng phạm vi chunk

- `job_orchestrator.py` dòng 1899-1907: `for page_num in range(chunk.page_start - 1,
  min(chunk.page_end, doc.page_count)): await font_shrink_page(doc[page_num], ...)` — đúng công thức
  0-based/1-based, **giống hệt** công thức đã dùng ở `_count_text_segments()` (dòng 255, cùng file,
  đã chạy ổn từ trước) — không phải công thức tự nghĩ ra mới có rủi ro off-by-one riêng.
- Test mới `test_font_shrink_only_processes_own_chunk_page_range` không chỉ đếm số lần gọi
  (`await_count == 94`, tức 40+42+12 thay vì 3×90=270) mà còn capture `page.number` TẠI THỜI ĐIỂM
  gọi (trước khi đóng doc handle) và `zip(..., strict=True)` từng lời gọi với đúng chunk nó thuộc về,
  assert `chunk.page_start - 1 <= page_number <= chunk.page_end - 1` cho MỌI lời gọi — đủ chặt để bắt
  lỗi "đúng số lần gọi nhưng sai trang" (ví dụ nếu ai đó vô tình đảo `page_start`/`page_end`).
- Tự chạy: `pytest ... -k test_font_shrink_only_processes_own_chunk_page_range` → 1 passed. `git
  stash push -- src/core/job_orchestrator.py` → chạy lại → **1 failed**. Stash pop khôi phục sạch.

**Kết luận BL-01: APPROVE.**

## 3. BL-02 — thứ tự cost gate trước duplicate-check trong `create_job()`

- Đọc diff `src/api/routes/jobs.py`: khối `settings`/`provider`/`_reject_deepl_for_pdf()`/
  `_enforce_cost_gate()` di chuyển lên trước khối `_find_completed_duplicate()`. Khối duplicate-check
  giữ nguyên logic cũ (`if request.job_type == "translate" and not request.force`), chỉ đổi VỊ TRÍ.
- Test mới `test_create_job_cost_gate_runs_before_duplicate_check` cover đủ 3 tổ hợp cho cùng 1 file
  trùng hash + cap thấp: (a) không `force` → 402, không tạo Job row (`_job_row_count() == 1`, chỉ có
  job trùng cũ); (b) `force=true` không `confirm_cost` → vẫn 402 (chứng minh cost gate KHÔNG bị
  `force` bỏ qua); (c) `force=true` + `confirm_cost=true` → 202, tạo job MỚI (id khác job trùng,
  `_job_row_count() == 2`). Đủ để phân biệt "chỉ đổi thứ tự" với "đổi luôn kết quả cuối cùng".
- `test_create_job_reports_duplicate_of_completed_job_with_same_hash` (test cũ, bị sửa): thêm
  `"provider": "ollama"` vào request duplicate-check vì cost gate giờ chạy trước và cần provider
  resolve được (không cần API key) — đây là sửa hợp lý để giữ đúng mục đích gốc của test (verify
  response `duplicate_found`), không phải nới lỏng assertion nào để che giấu lỗi; response
  `duplicate_found` + `job_id`/`completed_at` không đổi.
- Tự chạy: cả 2 test trên `pytest` → 2 passed. `git stash push -- src/api/routes/jobs.py` → chạy lại
  `test_create_job_cost_gate_runs_before_duplicate_check` → **1 failed**. Stash pop khôi phục sạch.

**Kết luận BL-02: APPROVE.**

## 4. BL-03 — round-trip test `ollama_thread` qua `PUT`/`GET /api/settings`

- 2 test mới ở `tests/integration/test_settings_api.py`: `test_get_settings_reports_ollama_thread_default`
  (GET trả default `2`), `test_put_ollama_thread_overrides_effective_settings` — PUT giá trị **6**
  (khác default `2`), rồi verify CẢ 3 nguồn đều trả `6`: response của chính PUT, GET riêng sau đó, và
  `get_effective_settings()` gọi trực tiếp qua session thật (không chỉ tin HTTP echo). Đây đúng là
  round-trip thật (set khác default → đọc lại đúng giá trị đã set), không phải chỉ test default không
  đổi.
- Không có thay đổi source code cho mục này (field đã expose sẵn) — chỉ thêm test, rủi ro thấp.
- Tự chạy: `pytest tests/integration/test_settings_api.py -k "test_get_settings_reports_ollama_thread_default
  or test_put_ollama_thread_overrides_effective_settings"` → 2 passed.

**Kết luận BL-03: APPROVE.**

## 5. Regression toàn cục — tự chạy độc lập

```
uv run pytest tests/ -q          → 773 passed (khớp claim CHANGELOG, không regression)
uv run ruff check src/ tests/    → All checks passed!
```

## 6. Checklist bắt buộc (CLAUDE.md project)

- **R5-04**: N/A — không có thay đổi nào trong `src/services/*_runner.py`/`*_provider.py` (wrapper
  gọi external tool) ở phạm vi 4 mục backlog này. `_process_epub_chunk()` gọi `pricing_provider`
  nhưng thay đổi thực tế nằm ở logic ghi `chunk.api_cost` nội bộ, không đổi contract external.
- **R6-04**: không có orchestrator mới gọi tuần tự nhiều service cần trace lineage N→N+1 trong phạm vi
  đợt này — BL-05 chỉ thêm 2 điểm ghi DB cục bộ dùng biến đã tích luỹ sẵn trong CHÍNH hàm đó (không
  phải nối 2 bước external riêng biệt). Đã tự trace bằng tay ở mục 1 phía trên (đường đi biến
  `total_cost` từ chỗ tích luỹ tới chỗ ghi DB) để chắc chắn không có khoảng trống lineage kiểu Bug #5.
- **R8-01**: N/A — không có engine/biến thể mới nào được thêm vào pipeline dùng chung trong đợt này.
- **Protocol 5 R5-03 (mock có golden file thật không)**: không áp dụng — không có mock nào mô phỏng
  external tool thật (`_ControllableEpubProvider`/`_CostTrackingEpubProvider` là fake nội bộ cho
  `TranslationProvider` interface đã tự định nghĩa, không mô phỏng response thật của 1 SDK/API bên
  ngoài cụ thể, giống các test EPUB khác đã có từ trước).

## Kết luận

**APPROVE cả 4 mục (BL-01, BL-02, BL-03, BL-05)**. Đã tự verify độc lập bằng `git stash` cho từng mục
có thay đổi source code (BL-01/02/05), tự đọc assertion xác nhận test không rỗng/không tự thoả mãn
giả định, và tự chạy lại toàn bộ suite (773 passed) + `ruff check` (sạch). Không phát hiện vấn đề nào
cần Dev sửa lại — không tốn vòng lặp Protocol 3.

---

# Review Report — Port Protocol A–F (fix 2 blocking) — VÒNG 2/3

**Phạm vi**: `scripts/validate_state.py` — đúng 2 blocking issue nêu ở
`docs/review-report.md:2266-2293` (vòng 1/3): (1) `parse_day()` im lặng bỏ qua `infra_pending` không
parse được ngày; (2) validator không thực thi phần lớn ràng buộc `project_state.schema.json`
(`additionalProperties: false`, `pattern`, `maxLength` ở nhiều field). Không review lại toàn bộ phạm
vi vòng 1 (hook, schema, `project_state.json` data) — đã APPROVE ở các mục đó vòng 1, không đổi.

**External contract verified against real source**: N/A — `validate_state.py` chỉ đọc file cục bộ
(`project_state.json`, `project_state.schema.json`) bằng stdlib, không gọi tool/API bên thứ 3. Không
thuộc phạm vi Protocol 5.

## 1. Phương pháp kiểm

Dựng lại 1 git repo cô lập RIÊNG (khác thư mục scratchpad Dev đã dùng) tại
`scratchpad/iso_v2/`, copy `scripts/validate_state.py` + `project_state.schema.json` +
`project_state.json` (bản thật hiện tại làm baseline hợp lệ — xác nhận baseline chạy
`✅ hợp lệ` trước khi mutate). KHÔNG tái dùng case Python Dev đã viết trong CHANGELOG — tự viết script
Python riêng, sinh case bằng cách mutate baseline (không gõ tay JSON theo trí nhớ). Sau khi xong,
xác nhận `git diff --stat project_state.json` ở repo thật KHÔNG đổi so với trước khi bắt đầu review
(chỉ còn diff tiền tồn tại từ trước, không phải do phiên review này gây ra).

**Lưu ý phương pháp**: lần đầu dùng `git checkout -- project_state.json` để reset giữa các case trong
repo cô lập (repo `git init` chưa có commit nào → `checkout` fail âm thầm, không reset gì) khiến 2 case
đầu (K, L, M) bị nhiễm chéo dữ liệu hỏng từ case trước. Phát hiện qua `assert` kiểm tra baseline trước
khi mutate, đã sửa bằng cách giữ 1 bản backup `base_project_state.json` và copy lại từ đó — dựng lại
toàn bộ case sạch trước khi kết luận. Ghi lại để nhắc bản thân: quy trình verify cũng cần tự kiểm tra
lại, không tin ngay kết quả lần chạy đầu.

## 2. Blocking #1 (`parse_day()` im lặng) — ĐÃ ĐÓNG, xác nhận độc lập

Đọc code `check_infra()` (`scripts/validate_state.py:312-336`): `applied = parse_day(item["applied_at"])`
chạy TRƯỚC nhánh kiểm `item.get("commit")`, và khi `applied is None` gọi `fail()` (không phải `warn()`)
rồi `continue` — đúng như Dev báo, đúng theo khuyến nghị "cân nhắc fail() luôn" của vòng 1.

Tự test 2 case KHÁC case Dev đã liệt kê trong CHANGENLOG (Dev đã test "rác + commit=null" và "rác +
commit đã set" — tôi test thêm biến thể khác):

| Case (tự tạo) | Kỳ vọng | Kết quả thật |
|---|---|---|
| `infra_pending[].applied_at` rác (`"khong-phai-ngay"`), `commit` **đã set** (`"abc1234"`) | fail bất kể commit | ❌ bắt đúng: `"applied_at=... không parse được ... Protocol E dựa vào đúng field này"` |
| `infra_pending[].applied_at` = chuỗi rỗng `""`, `commit=null` | fail | ❌ bắt đúng, cùng thông điệp |

Xác nhận: lỗ hổng im lặng cũ (0 lỗi, 0 cảnh báo, "✅ hợp lệ") không còn tái hiện ở cả 2 case. **Blocking
#1 đã đóng.**

## 3. Blocking #2 (validator không khớp schema) — ĐÃ ĐÓNG phần lớn, xác nhận độc lập + phát hiện 1 vấn đề mới (không cùng loại)

### 3a. Đọc code `check_against_schema()` — xác nhận là đệ quy tổng quát thật, không phải case cứng nguỵ trang

Đọc toàn bộ `scripts/validate_state.py:154-229`. Xác nhận:
- `required` lấy từ `schema.get("required", [])` — không hardcode field name.
- `properties`/`sub_schema` lấy từ `schema.get("properties", {})`, đệ quy `check_against_schema` cho
  từng field con theo đúng key có trong `instance`.
- `additionalProperties` xử lý cả 2 dạng: `False` (báo lỗi field lạ) và `dict` (áp sub-schema cho các
  field không nằm trong `properties` — dùng đúng cho `documents{}` có
  `additionalProperties: {"type": "string"}`).
- `pattern`, `maxLength`, `minimum`, `maximum`, `enum`, `format=date` đều đọc trực tiếp từ `schema[...]`,
  không có danh sách field cứng nào trong hàm này.
- `items` cho array đệ quy đúng qua từng phần tử.

→ Đây thực sự là 1 checker generic đọc schema tại runtime, đúng như Dev báo — không phải danh sách
case viết tay giả dạng "generic". Xác nhận qua đọc code trực tiếp (không chỉ qua black-box test).

### 3b. Tự test 8 case — cố tình KHÔNG trùng case Dev đã dùng (Dev test: field lạ ở top-level và
`checkpoints[]`; `open_questions[].id`/`backlog[].id` pattern; `project_name`/`steps[].id` maxLength).
Tôi test ở vị trí/loại ràng buộc khác:

| Case (tự tạo, khác vị trí Dev đã thử) | Kỳ vọng | Kết quả thật |
|---|---|---|
| `additionalProperties:false` lồng trong **`open_questions[]`** (field lạ `priority`) | fail | ❌ bắt đúng: `open_questions[0].priority: field lạ...` |
| `additionalProperties:false` lồng trong **`steps[]`** (field lạ `notes`) | fail | ❌ bắt đúng |
| `additionalProperties:false` ở **object lồng cấp khác hẳn `team{}`** (không phải mảng, field lạ `extra_role_list`) | fail | ❌ bắt đúng: `team.extra_role_list: field lạ...` |
| `pattern` sai cho `open_questions[].id` (`"Q-99"` thay vì tiền tố `HOI-`/`BUG-`) | fail | ❌ bắt đúng |
| `pattern` sai cho `backlog[].id` (chữ thường `"bl-1"` thay vì `"BL-1"`) | fail | ❌ bắt đúng |
| `documents{}` — value không phải string (`weird_doc: 12345`, vi phạm `additionalProperties: {"type":"string"}`) | fail | ❌ bắt đúng: `documents.weird_doc: type phải thuộc ['string']...` |
| `loops[].count` âm (vi phạm `minimum: 0`) | fail | ❌ bắt đúng |
| `loops[].limit = 0` (vi phạm `minimum: 1`) | fail | ❌ bắt đúng (2 lỗi: minimum + hệ quả count>limit chưa escalate) |

8/8 đúng kỳ vọng, kể cả 3 case ở vị trí lồng sâu Dev chưa thử (`open_questions[]`, `steps[]`, object
`team{}` không phải mảng) — xác nhận `additionalProperties: false` được enforce ở **mọi cấp**, không
chỉ top-level/`checkpoints[]` như vòng 1 từng phát hiện thiếu. **Blocking #2 đã đóng cho đúng phạm vi
2 issue đã nêu.**

### 3c. Vấn đề MỚI phát hiện — không phải silent-pass, mà là **crash không kiểm soát** khi type đã sai

Câu hỏi bắt buộc trong brief: "không có lỗ hổng tương tự `parse_day()` cũ — một nhánh nào đó âm thầm
`pass`/`continue` khi gặp giá trị bất ngờ mà không cảnh báo". Trả lời: **không tìm thấy silent-pass
nào**, nhưng tìm thấy 1 vấn đề khác — các hàm `check_*` nghiệp vụ (chạy SAU `check_against_schema()`)
không phòng thủ khi field đã bị `check_against_schema()` gắn cờ sai type, dẫn tới crash không bắt
được thay vì báo lỗi sạch. `check_against_schema()` chạy trước và ĐÃ đúng phát hiện các case này (thêm
đúng lỗi vào `errors[]`), nhưng crash xảy ra trước khi tới đoạn `print` cuối `main()`, nên thông điệp
lỗi đúng đó **không bao giờ được in ra** — script chỉ dừng bằng traceback Python thô.

3 case tự tạo, verify bằng chạy thật (không suy đoán):

```
infra_pending[].applied_at = 20260911 (int, đúng ra phải là string)
  → check_infra() gọi parse_day(20260911) → parse_day làm value[:10]
  → TypeError: 'int' object is not subscriptable   (crash, không phải lỗi sạch)

open_questions[].text = 12345 (int, đúng ra phải là string)
  → check_questions() gọi len(q["text"])
  → TypeError: object of type 'int' has no len()   (crash)

open_questions[].clarify_rounds = "3" (string, đúng ra phải là integer)
  → check_questions() so sánh q.get("clarify_rounds", 0) > 2
  → TypeError: '>' not supported between instances of 'str' and 'int'   (crash)
```

Cả 3 đều exit code 1 (hành vi mặc định Python khi exception không bắt) — **không phá vỡ thuộc tính an
toàn cốt lõi**: pre-commit hook (R7-02) vẫn chặn commit đúng, vì hook chỉ kiểm exit code, không kiểm
nội dung output. Đây KHÁC bản chất so với Blocking #1 gốc (nơi lỗi hoàn toàn biến mất, exit code = 0,
"✅ hợp lệ" — đó là lỗ hổng để lọt dữ liệu hỏng). Ở đây dữ liệu hỏng vẫn bị chặn, chỉ là cách báo lỗi
bị vỡ: (a) mất đúng thông điệp lỗi rõ ràng mà `check_against_schema()` đã tính ra sẵn; (b) chỉ báo
được lỗi ĐẦU TIÊN gặp phải rồi dừng cứng, không liệt kê hết mọi lỗi trong file như docstring đầu file
hứa ("Exit code: 1 = không hợp lệ, **in danh sách lỗi**") — thực tế in ra traceback, không phải danh
sách lỗi.

**Đánh giá mức độ**: xếp **non-blocking** cho vòng này (không giống category "silent hole" mà brief
hỏi cụ thể, và không phá gate chặn commit) — nhưng không được im lặng bỏ qua (Protocol 4 mở rộng:
"Finding non-blocking ... không được im lặng biến mất"). Đề nghị PM thêm vào `backlog[]` của
`project_state.json`
(`id: BL-xx, text: "validate_state.py crash (không phải fail sạch) khi field sai type đã bị
check_against_schema() phát hiện — vd applied_at là int, clarify_rounds là string", source: "Reviewer
vòng 2/3 S2", status: "open"`). Hướng sửa gợi ý cho lần chạm tiếp theo: mỗi hàm `check_*` nghiệp vụ
nên bỏ qua field đã có lỗi type từ `check_against_schema()` cho đúng path đó (thay vì giả định đã
đúng type), hoặc bọc từng thao tác string/numeric bằng `isinstance` guard trước khi dùng.

## 4. `ruff` + `pytest` — tự chạy lại, không tin số Dev báo

```
uv run pytest tests/ -q                              → 773 passed, 1065 warnings, 102.84s
uv run ruff check src/ tests/ scripts/                → All checks passed!
uv run ruff format --check scripts/validate_state.py  → 1 file already formatted
python3 scripts/validate_state.py (repo thật)         → ✅ hợp lệ — 3 bước, 3 câu hỏi mở, 5 backlog, 2 checkpoint
```

Khớp với số Dev báo trong CHANGENLOG (773 passed, ruff sạch).

## 5. `git diff --stat project_state.json` (repo thật) — xác nhận rỗng thay đổi ngoài ý muốn

```
project_state.json | 47 ++++++++++++++++++++++++++++-------------------
```

Diff này là diff TIỀN TỒN TẠI từ trước khi review vòng 2 bắt đầu (đúng với mô tả trong git status đầu
phiên — đã có sẵn từ commit trước, không đổi thêm dòng nào trong lúc tôi review). Không phát hiện thay
đổi mới do quá trình test của tôi gây ra (mọi test chạy trong `scratchpad/iso_v2/`, dùng bản copy).

## 6. `docs/CHANGENLOG.md` — append đúng cách

`git diff docs/CHANGELOG.md` chỉ có dòng `+` (thêm mục "## Bước 2 (S2) — Fix 2 blocking issue..."
vào cuối file, sau mục cuối cùng đã có), không có dòng `-` nào — xác nhận không mất nội dung cũ, đúng
R7-03.

## Kết luận

**APPROVE** (Vòng 2/3). Cả 2 blocking issue nêu ở vòng 1/3 (`docs/review-report.md:2266-2293`) đã
được đóng đúng, xác nhận độc lập bằng case tự tạo (không trùng case Dev đã dùng), bao gồm cả điểm vòng
1 nhấn mạnh còn thiếu (`additionalProperties: false` ở mọi cấp lồng, không chỉ top-level). `pytest`
773 passed, `ruff check`/`ruff format --check` sạch — tự chạy lại, không tin số Dev báo.
`project_state.json` thật không bị đụng ngoài ý muốn. `docs/CHANGELOG.md` append đúng cách.

Phát hiện thêm 1 vấn đề MỚI (mục 3c) — không cùng loại với 2 blocking đã nêu (không phải silent-pass,
mà là crash-thay-vì-báo-lỗi-sạch khi field đã sai type) — xếp **non-blocking**, đề nghị PM ghi vào
`backlog[]`, không chặn việc đóng S2 lần này. Không có vi phạm Protocol 5/6/7/8 nào trong phạm vi đợt
này (R5-04 = N/A, không có external tool wrapper trong `scripts/validate_state.py`).

---

# Review Report — BL-04 Implementation (babeldoc drop report) — VÒNG 1/3

**Phạm vi**: implement đầu tiên cho BL-04 (Architecture.md §6.22, đặc biệt §6.22.8 checklist +
§6.22.9 gate 12 test + live E2E). Thiết kế đã duyệt riêng qua 2 vòng Domain Expert (Protocol D) —
review này CHỈ xét code có khớp thiết kế đã duyệt và có bug/vấn đề gì không, không review lại kiến
trúc.

## 1. Checklist bắt buộc (CLAUDE.md)

**R5-04**: External contract verified against real source: **YES** — tự cài đặt local có sẵn
`babeldoc 0.6.4` (`/Users/hieutt/.local/bin/babeldoc --version` → `babeldoc 0.6.4`), tự đọc trực
tiếp source thật tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/` (KHÔNG chỉ
tin Architecture.md) và đối chiếu độc lập 3 điểm:
- `format/pdf/document_il/backend/pdf_creater.py:809-834` — predicate drop
  (`not chars and paragraph.unicode and paragraph.debug_id`) + câu sentinel
  `"Unable to export paragraphs that have not yet been formatted"` — khớp CHÍNH XÁC với
  `src/babeldoc_shim/drop_report.py::has_rendered_chars`/`is_dropped` và
  `_DROP_SENTINEL_TEXT` trong `babeldoc_runner.py`.
- `pdf_creater.py:839` (`create_render_units_for_page(self, page, translation_config)`) và dòng gọi
  duy nhất tại `:1698` (bên trong `update_page_content_stream`, gọi từ vòng `for page in
  self.docs.page` tại `write():1465-1466`) — khớp đúng địa chỉ hook + tần suất "1 lần/trang" mà
  Architecture.md 6.22.4 khẳng định.
- `format/pdf/document_il/frontend/il_creater_active.py:239-254` (`ActiveILCreater.create_il`,
  `should_translate_page`) — xác nhận `ActiveILCreater` (không phải `ILCreater` legacy) đúng là
  class trên đường dịch, khớp self-correction R5-05 trong Architecture.md 6.22.1.

R5-04 cho `sitecustomize.py`: **YES** (cùng nguồn xác thực trên — patch bọc đúng
`PDFCreater.create_render_units_for_page` của module `babeldoc.format.pdf.document_il.backend.
pdf_creater`, đúng địa chỉ đã verify).

**R6-04 (trace tay lineage `_process_chunk()`)**: đã tự trace, không chỉ xác nhận "2 bước đều được
gọi đúng tham số riêng":
`pdf2zh_result = await with_retry(_call_translator)` (`job_orchestrator.py:2080`) →
`_call_translator()` gọi `self._translator_runner.translate_pages(...)` (`:2055`, runner đã chọn 1
lần duy nhất ở `__init__`, không rẽ nhánh theo tên engine) → bước sau đọc thẳng
`pdf2zh_result.drop_report` (`:2183`, `_map_babeldoc_drop_report_to_findings(pdf2zh_result.
drop_report, chunk)`) — **đúng object trả về từ chính lời gọi `translate_pages()` của chunk này**,
không phải giá trị hằng/tái tạo/đọc lại file khác. Tên biến `pdf2zh_result` là artifact lịch sử
(dùng chung tên biến từ thời chỉ có 1 engine) nhưng giá trị runtime đúng là `BabeldocResult` khi
`self._reports_own_paragraph_drops` là `True` (2 thứ này đảm bảo loại trừ lẫn nhau bởi chính
capability, không phải giả định). Đã đọc code thật xác nhận field `drop_report` tồn tại trên
`BabeldocResult` (mặc định `_empty_drop_report()` — trạng thái 4, không phải "0 drop") và **không**
tồn tại trên `Pdf2zhResult` (nhánh pdf2zh không bao giờ chạm nhánh `if
self._reports_own_paragraph_drops:` nên không cần).

**R8-01/02/03**: đã đọc lại bảng audit 6.22.7 trong Architecture.md (7 bước hậu kỳ hiện có, kể cả
bước cũ) — khớp đúng với code: `font_shrink_page()`/`OverflowReport` hoàn toàn không bị đụng (xem
mục 3 dưới, đã tự verify bằng diff), `overlay_rotated_text`/`persist_findings` dùng chung hàm
`persist_findings()` nhưng `check_type` khác nhau nên không lẫn row, `_call_translator()`
`shutil.rmtree` đầu mỗi attempt xảy ra TRƯỚC khi `drop_report_path` được tính (đã tự đọc
`babeldoc_runner.py:463-473`: `output_dir.mkdir()` chạy trước `drop_report_path = output_dir / ...`,
khớp đúng thứ tự cam kết). Capability `reports_own_paragraph_drops` hiện thực đúng khuôn
`needs_font_shrink` — có guard `isinstance(value, bool)` (`job_orchestrator.py`, property
`_reports_own_paragraph_drops`), verify bằng test `test_reports_own_paragraph_drops_property_
isinstance_guard_catches_unset_mock` (PASS khi tự chạy lại).

**R5-03 (Protocol 5) — mock có golden file backing thật không**: `tests/fixtures/babeldoc/
drop_report_v2.jsonl` là copy nguyên văn sidecar JSONL thật từ 1 lần chạy `babeldoc` 0.6.4 +
DeepSeek thật (`scripts/bl04_live_e2e_chunk5.py`, đã đọc `README.md` mục tương ứng xác nhận nguồn +
ngày trích). Lần chạy này KHÔNG tái hiện được ca drop (0 dòng `type=drop`) — Dev/README nói thẳng
điều này, không giấu, và tự phân biệt rõ 2 nhánh test: nhánh `header`/`page`/`observed_pages` phủ
bằng byte thật (`test_parse_drop_report_file_reads_real_live_e2e_golden_fixture`), nhánh `type=drop`
(field `text_excerpt` v.v.) vẫn dựa vào dữ liệu MÔ PHỎNG đúng schema đã verify qua source
(`test_parse_drop_report_file_reads_real_written_file`) — đây là hạn chế thật (dịch máy không tất
định, đã thử 2 lần), được ghi nhận trung thực, không tự nhận đã phủ hết. Chấp nhận được cho vòng
review này vì: (a) R5-03 chỉ yêu cầu "ít nhất 1 lần gọi thật", đã có 2 lần; (b) giới hạn còn lại
được escalate rõ ràng cho PM/QA cân nhắc trong CHANGELOG ("Đề xuất: PM/QA cân nhắc có đáng đầu tư
thêm 1 lần chạy live... trước khi release") thay vì tự quyết và giấu đi.

## 2. Audit ĐỘC LẬP từng file trong diff (không chỉ tin Dev báo)

| File | Kết quả |
|---|---|
| `src/babeldoc_shim/drop_report.py` (mới) | Predicate/dựng record khớp đúng Architecture.md 6.22.4, có docstring trích nguồn dòng cụ thể |
| `src/babeldoc_shim/sitecustomize.py` | 1 hook thứ 3 độc lập rollback (`_PDF_CREATER_MODULE_NAME` riêng), toàn bộ phần ghi bọc `try/except` RIÊNG khỏi phần gọi hàm gốc — hàm gốc LUÔN được gọi, kết quả LUÔN đúng, khớp cam kết "CHỈ ĐỌC" |
| `src/core/chunking.py` | `surviving_page_range()` + `_ChunkLike` Protocol đúng `int \| None`, raise `ValueError` rõ ràng khi `page_start`/`page_end` là `None` (đúng X2) |
| `src/postprocess/chunk_merge.py` | Thay đúng khối `:85-91` cũ bằng gọi hàm chung, **giữ nguyên** guard `overlap_* is not None`, **giữ nguyên** phần kẹp `end` theo `page_count` ở lại module này (đúng X3, không bị chuyển nhầm vào hàm chung); thêm `logger.warning` khi `position != chunk.chunk_index` đúng bất biến đã ghi ở 6.22.5.1 |
| `src/services/babeldoc_runner.py` | 2 dataclass + parse file sau `process.wait()` (không giả định vị trí dòng header), đếm sentinel bằng `stdout+stderr`, `drop_report_path` nằm TRONG `output_dir` — đúng ràng buộc bắt buộc |
| `src/services/layout_qa.py` | Đủ 4 `check_type` mới (kể cả `mismatch` — xem ghi chú nhỏ ở mục 5) + đăng ký severity đúng 1 nguồn sự thật `_SEVERITY_BY_CHECK` |
| `src/services/pdf2zh_runner.py` | `reports_own_paragraph_drops: ClassVar[bool] = False`, đúng R8-03 |
| `src/core/job_orchestrator.py` | Đọc kỹ toàn bộ khối mới: BỐN trạng thái (không phải ba) được hiện thực đúng — `available=False` → trạng thái 4; `is_incomplete` gộp đúng cả 2 điều kiện (`observed_pages != expected_pages` HOẶC `checksum_mismatch_pages` khác rỗng, đúng X5 mở rộng); R-1 log đúng định dạng bắt buộc có mẫu số + câu PHẠM VI; R-2 dùng đúng 1 câu `SELECT func.count()...WHERE check_type LIKE 'babeldoc_%'` trên DB, KHÔNG dùng accumulator in-memory (đúng X7) — verify được cả bằng đọc code lẫn bằng test #11 (`test_r2_log_counts_from_db_including_resumed_chunk_findings`, tự chạy PASS) |

## 3. Vấn đề "test sửa để pass" — TỰ VERIFY LẠI, không tin lời Dev báo

Đã tự đọc `src/postprocess/font_shrink.py` (module KHÔNG nằm trong diff của phiên này — xác nhận
bằng `git status`, docstring "Second implementation note" tồn tại từ TRƯỚC BL-04) để kiểm chứng độc
lập claim của Dev: `page.get_text("dict")`'s block bbox được tính TỪ CHÍNH glyph đang được so sánh,
nên 1 trang PyMuPDF mới vẽ (`page.insert_text()`) không bao giờ tự tràn khung được, bất kể
font/nội dung — đây là lý do gốc khiến test cũ (`_fake_pdf2zh_runner()` vẽ `"page N"` qua
`insert_text` mặc định) không bao giờ có thể sinh `still_overflow=True`, độc lập với BL-04 đúng
hay sai.

Đã tự đọc `evaluate_span`/`_compute_fit`/`font_shrink_page` (`font_shrink.py:117-160`) xác nhận cơ
chế fix: `measurer = fitz.Font(fontfile=font_path)` đo lại text bằng font Noto (font PRODUCTION thật
truyền từ `Settings.noto_font_path`), trong khi `block_bbox` lấy từ `page.get_text("dict")` — vốn
được PyMuPDF tính từ glyph "helv" đã thực sự vẽ ra. Vẽ `"|"*30` bằng "helv" (`insert_text()` không
chỉ định `fontname`) rồi đo lại bằng Noto tạo ra đúng 2 số đo khác nhau — cùng loại mismatch với
production thật (pdf2zh vẽ bằng font X, `font_shrink_page` đo lại bằng Noto). Đây KHÔNG phải một
mẹo giả tạo tách biệt khỏi logic thật, mà là tái tạo đúng cơ chế overflow gốc.

Đã tự chạy `uv run pytest tests/integration/test_job_orchestrator.py -k
"forced_overflow or babeldoc_drop or reports_own_paragraph or r2_log" -q` → **4 passed** (bao gồm
đúng test đã sửa) — không chỉ đọc code, còn thực thi thật để xác nhận assertion mới
(`still_overflow=True`, `page_number==0`, `font_size_original≈14.0`) thật sự đi qua nhánh
`still_overflow` thật, không phải giả mạo qua monkeypatch nội bộ.

**Kết luận mục 3**: đây là case (a) — sửa test vì test cũ tự nó sai (bất khả thi về mặt hình học,
không phải regression từ BL-04), KHÔNG phải case (b) nới lỏng assertion để che giấu bug. Xác nhận
độc lập, không chỉ tin lời Dev.

## 4. `ruff` + `pytest` — tự chạy lại, không tin số Dev báo

```
uv run pytest tests/ -q                                        → 816 passed, 1098 warnings, 102s
uv run ruff check <đúng 13 file trong phạm vi BL-04>            → All checks passed!
uv run ruff format --check <đúng 13 file trong phạm vi BL-04>   → 19 file đã format đúng
```

Số `pytest` (816) khớp với CHANGELOG Dev báo.

## 5. Xác nhận mục "8 file khác lệch ruff format, không thuộc phạm vi BL-04"

Tự chạy `uv run ruff format --diff src/ tests/ scripts/` trên TOÀN REPO: xác nhận đúng 8 file
`src/` mà Dev liệt kê (`jobs.py`, `file_router.py`, `claude_provider.py`, `epub_document.py`,
`ollama_provider.py`, `openai_provider.py`, `excel_utils.py`, `unit_conversion_table.py`) đều lệch
format — **và** không nằm trong `git status` của phiên này (xác nhận sạch).

**Ghi chú nhỏ, non-blocking**: `ruff format --diff` toàn repo thực ra phát hiện thêm **10 file
test** khác cũng lệch format (`test_batch_orchestrator.py`, `test_cost_gate_api.py`,
`test_upload_and_job_flow.py`, `test_chunk_merge.py`, `test_cost_estimator.py`,
`test_database_chunks_unit_columns_migration.py`, `test_epub_batch_golden_fixture.py`,
`test_epub_document.py`, `test_retry.py`, `test_translation_providers.py`) mà Dev không liệt kê —
đã xác nhận **cũng không** nằm trong `git status` của phiên này (không phải Dev né tránh, chỉ là
danh sách Dev báo không đầy đủ). Cũng lưu ý: `uv.lock` diff thực tế chỉ đổi `version = "1.2.9"` →
`"1.3.2"` (bump version project, không phải bump version `ruff` như Dev suy đoán trong CHANGELOG) —
suy đoán sai về NGUYÊN NHÂN nhưng không ảnh hưởng KẾT LUẬN (drift vẫn xác nhận có thật, vẫn xác nhận
không liên quan diff này). Đề nghị PM gộp toàn bộ 18 file lệch format này thành 1 backlog dọn dẹp
riêng (không phải việc của BL-04).

## 6. Ghi chú nhỏ khác, non-blocking

- Architecture.md 6.22.6 "Đăng ký severity" viết "BL-04 thêm **3** khoá mới vào `_SEVERITY_BY_CHECK`"
  nhưng liệt kê + code thực tế thêm **4** khoá (thiếu đếm `babeldoc_drop_report_mismatch` mà chính
  F5 cùng mục đã mô tả). Đây là lệch số đếm trong chính Architecture.md (không phải lỗi Dev — code
  làm đúng theo đặc tả đầy đủ, kể cả khoá thứ 4), nhưng nên sửa số "3" thành "4" ở lần chạm
  Architecture.md tiếp theo để tránh nhầm lẫn khi đọc lại.
- `README.md` (`tests/fixtures/babeldoc/`) có drift ruff-format tại dòng 96/121 (thiếu dòng trống
  sau `import fitz` trong code block) — nhưng đây là drift TỪ TRƯỚC BL-04 (không nằm trong vùng Dev
  vừa thêm ở cuối file), không phải lỗi mới.

## 7. Đối chiếu 12 test gate (§6.22.9) — R6-02

Đã đối chiếu từng test với đặc tả, xác nhận tất cả 12 đều assert giá trị cụ thể (không chỉ
"không lỗi"/"đã gọi"):

| # | Tên gate | File | Xác nhận |
|---|---|---|---|
| 1 | `test_drop_report_parse` | `test_babeldoc_runner.py::test_parse_drop_report_file_reads_real_live_e2e_golden_fixture` | Golden file thật, phủ `header`/`page`/`observed_pages`; nhánh `drop` dùng data mô phỏng đúng schema (đã ghi nhận ở mục R5-03 trên) |
| 2 | `test_drop_report_unavailable` | `test_job_orchestrator_babeldoc_drop_mapping.py` | assert đúng 1 finding `unavailable`, `severity=major`, `page_number=chunk.page_start` |
| 3 | `test_drop_report_incomplete` | nt | assert `detail["missing"]==[17,18]`, đồng thời vẫn giữ finding drop đã quan sát (trang 5) |
| 4 | `test_overlap_pages_filtered` | nt | assert đúng `[55]`, `suppressed_overlap_count==2` |
| 5 | `test_surviving_range_shared` | `test_chunking.py` | assert dải rời nhau + phủ kín `[1,418]`, VÀ assert bằng refactor thật (`chunk_merge.py` gọi chung hàm, không chép công thức) |
| 6 | `test_lineage` | `test_job_orchestrator.py::test_babeldoc_drop_finding_page_number_traces_to_sidecar_file` | dùng CHÍNH hàm production `_parse_drop_report_file` để parse sidecar, không viết lại logic trong test |
| 7 | `test_pdf2zh_branch_untouched` | `test_job_orchestrator.py::test_pdf2zh_branch_untouched_by_babeldoc_drop_report` | 0 finding `babeldoc_*`, `OverflowReport` vẫn ghi — đã tự verify độc lập ở mục 3 |
| 8 | `test_capability_guard` | `test_job_orchestrator.py` | `pytest.raises(TypeError, match="reports_own_paragraph_drops")` |
| 9 | `test_sentinel_mismatch_one_way` | `test_job_orchestrator_babeldoc_drop_mapping.py` | assert cả 2 chiều (`<=` không finding, `>` đúng 1 finding) |
| 10 | `test_severity_from_registry` | nt | monkeypatch dict thật, assert severity đổi theo |
| 11 | `test_r2_counts_from_db_on_resume` | `test_job_orchestrator.py::test_r2_log_counts_from_db_including_resumed_chunk_findings` | Dựng đúng kịch bản resume (chunk 0 `status=completed` với 3 finding sẵn trong DB, KHÔNG đi qua `_process_chunk()` lần này), assert log R-2 báo đúng `4` |
| 12 | `test_checksum_mismatch_triggers_incomplete` | `test_job_orchestrator_babeldoc_drop_mapping.py` | assert `checksum_mismatch_pages==[10]` dù `observed_pages==expected_pages` (đúng X5) |

Tự chạy `uv run pytest` xác nhận toàn bộ 12 test (và các test liên quan khác trong diff) đều PASS.

## Kết luận

**APPROVE** (Vòng 1/3). Implementation khớp đúng thiết kế đã duyệt tại Architecture.md §6.22
(§6.22.4–6.22.9), đã tự verify độc lập (không chỉ tin Dev báo) ở các điểm quan trọng nhất: contract
babeldoc thật (R5-04 YES, tự đọc source 0.6.4 đã cài), lineage `_process_chunk()` (R6-04, tự trace
tay `pdf2zh_result.drop_report` bắt nguồn đúng từ return value của `translate_pages()`), BỐN trạng
thái + R-2 đếm từ DB (X7) đúng theo đặc tả, và claim "test sửa vì test cũ sai" (mục 1, tự đọc
`font_shrink.py` + tự chạy test xác nhận cơ chế overflow thật, không phải nới lỏng assertion để che
giấu bug). `pytest` 816 passed, `ruff check`/`ruff format --check` sạch trên toàn bộ phạm vi diff —
tự chạy lại độc lập.

Không có blocking issue. 3 ghi chú non-blocking (mục 5, 6): (a) gộp 18 file lệch ruff-format toàn
repo (8 Dev đã báo + 10 chưa báo) thành 1 backlog dọn dẹp riêng; (b) sửa số đếm "3 khoá" → "4 khoá"
ở Architecture.md 6.22.6 "Đăng ký severity" lần chạm tiếp theo; (c) drift format từ trước tại
`tests/fixtures/babeldoc/README.md` dòng 96/121, không liên quan BL-04.

Live E2E (R5-03/R6-03): đã có 2 lần chạy thật hợp lệ, không tái hiện được ca drop kênh (1) — được
Dev/README ghi nhận trung thực, không giấu, có escalate rõ cho PM/QA quyết định thêm 1 lần chạy live
trước release hay không. Đây là quyết định của PM/QA, không phải lý do reject ở vòng Reviewer này.

---

## S4 — Bug #EPUB-5: DeepSeek thinking mode gây runaway giả cho EPUB (K-1..K-5) — Vòng 1/3

**Ngày**: 2026-09-12. **Phạm vi diff review**: `src/core/job_orchestrator.py`,
`src/services/translation.py`, `src/services/openai_provider.py`,
`src/services/deepseek_provider.py`, `src/core/config.py`, `src/services/epub_document.py`,
`tests/test_openai_provider_thinking.py` (mới), `tests/test_epub_document.py`,
`tests/integration/test_epub_translate_guards.py`, `tests/fixtures/epub_llm/deepseek_v4flash_usage.json`
(golden, mới), `docs/Architecture.md` §6.20.15, `docs/CHANGELOG.md`, `docs/design-log.md`,
`project_state.json`, `CLAUDE.md`. Đã tự chạy `git diff --stat` xác nhận đúng danh sách file (khớp
Dev báo cáo, không thiếu/thừa).

Đọc trước khi review: `docs/Architecture.md` §6.20.15 (dòng 6672–6936).

### Checklist bắt buộc (theo brief Protocol 5/6/7/8)

**1. R5-04 — External contract verified against real source**: **YES** (nguồn:
`tests/fixtures/epub_llm/deepseek_v4flash_usage.json`, golden file capture thật từ 1 lần gọi live
`deepseek-v4-flash` — spike R5-02 2026-09-11 — có shape response y hệt `openai` SDK
`model_dump()` thật, kèm cả field `null` không dùng đến (`accepted_prediction_tokens`,
`audio_tokens`...), 2 case rõ ràng khác nhau `baseline_thinking_default` vs `thinking_disabled` với
số token/nội dung tiếng Việt hợp lý — không có dấu hiệu viết tay theo giả định. Đối chiếu với doc
chính thức DeepSeek (`https://api-docs.deepseek.com/guides/thinking_mode/`, fetch 2026-09-11, ghi
rõ trong Architecture.md S6/S7). Áp dụng cho cả `src/services/openai_provider.py` (thêm cơ chế
`_extra_body()`/`reasoning_tokens` extraction, dùng chung cho mọi provider con) và
`src/services/deepseek_provider.py` (override cụ thể payload `{"thinking": {"type": "disabled"}}`).

**2. Điểm suýt sai đã cảnh báo trước — vị trí bóc koboSpan (K-1)**: **ĐÚNG chỗ**. Đọc trực tiếp
`src/services/epub_document.py`: `_unwrap_kobo_spans(soup)` được gọi bên trong `_parse_xhtml()`
— cả 2 nhánh (`features="xml"` thành công VÀ fallback `html.parser`) đều gọi hàm này ngay sau khi
parse xong soup, trước khi return. Đây là điểm vào DUY NHẤT mà `load()`, `write_translated()`,
`count_bb_vi_pairs()`, `to_markdown()` đều đi qua (tất cả đều gọi lại `_parse_xhtml()` trên bytes
đọc từ zip, không có đường tắt nào bỏ qua nó). KHÔNG có dòng nào trong `job_orchestrator.py` tự
bóc/sửa `koboSpan` ở chỗ build payload — đúng như Architecture.md §6.20.15 K-1 yêu cầu. Không phát
hiện lỗi mất chữ âm thầm ở điểm này.

**3. R6-02 — test assert cả 3 đường đọc dùng CHUNG 1 hàm unwrap**: **ĐẠT, không chỉ test riêng
lẻ**. `tests/test_epub_document.py::test_load_write_translated_and_to_markdown_share_same_kobo_unwrap`
dựng 1 EPUB có koboSpan multi-slot + 1 span pagebreak giả (mô phỏng thật), rồi tự tay trace:
(1) `EpubDocument.load()` → `doc.units[0].text` không còn `koboSpan`/`kobo.*`, đúng 1 unit (không bị
phình do koboSpan làm lệch slot); (2) `write_translated()` → mở lại file output từ đĩa, xác nhận
bản dịch tiếng Việt CÓ DẤU đã áp dụng ĐẦY ĐỦ (không bị cắt do lệch slot — đúng chính kịch bản Bug #5
kiểu-mới mà K-1 phòng), output không còn `koboSpan`, pagebreak vẫn còn nguyên; (3) `to_markdown()` —
cùng input, không còn koboSpan, text liền mạch; (4) `count_bb_vi_pairs()` — mở lại file output từ
đĩa (bilingual=True), đếm đúng 1 cặp bb-vi khác nội dung. Cả 4 bước dùng lại đúng 1 input gốc
(`_KOBO_SPAN_BODY`), không phải 4 test độc lập rời rạc với input khác nhau.

**4. R8-02 — phạm vi bóc koboSpan hẹp đúng deny-by-default**: **ĐÚNG**. Đọc
`_unwrap_kobo_spans()`: chỉ lặp `soup.find_all("span")`, kiểm `class` chứa đúng token `koboSpan`
(xử lý cả 2 dạng string/list tuỳ parser, dùng `.split()` thay vì dựa vào hành vi multi-valued-attr
của bs4 — đúng như comment cảnh báo "TUYỆT ĐỐI không dùng `class_="koboSpan"` của `find_all()`"),
dùng `span.unwrap()` (giữ con) chứ không `decompose()`. Test
`test_unwrap_kobo_spans_removes_only_kobospan_class_token` xác nhận tường minh span
`epub:type="pagebreak" id="page_1"` (không có class `koboSpan`) còn nguyên cả thẻ lẫn `id` sau khi
unwrap chạy.

**5. K-4 — quyết định KHÔNG đổi hằng số**: lý do hợp lý, có số đo thật (không né việc). Dev đã chạy
live E2E job thật (`bfc0ac24-...`, 66/66 chunk, 784 request) đo được `chars_per_answer_token` (min
1.89 · median 2.386 · max 7.66) và `runaway_ratio` (mean 0.7048 · median 0.7234 · max 0.9119 — dưới
tiêu chí ≤1.5× VÀ dưới `EPUB_RUNAWAY_OUTPUT_FACTOR=3.0`). Lý do không tách được 2 hằng số riêng từ
1 tỉ số gộp mà không suy đoán là hợp lý — đúng tinh thần Protocol 5 (không đoán 1 trong 2 rồi suy
ra cái kia). Đồng ý đây là lựa chọn AN TOÀN HƠN so với sửa dựa trên suy diễn, và Dev đã ghi backlog
rõ cho lần đo tách sau này (không giấu việc chưa làm).

**6. K-3 lệch nhỏ so với pseudocode gốc — đã cập nhật Architecture.md thật chưa**: **ĐÃ cập nhật
khớp code**. Đọc §6.20.15 K-3 (dòng 6814–6825): mô tả đúng cơ chế thật trong code — thuộc tính
INSTANCE `disable_thinking: bool = False` (không phải class-level cờ chung), `translate()` chỉ áp
`_extra_body()` khi `supports_thinking_toggle and self.disable_thinking` đều đúng, và
`run_epub_job()` tự bật cờ NGAY sau khi tạo provider — khớp 100% với
`src/services/openai_provider.py` dòng 53–58/91–93 và `src/core/job_orchestrator.py` dòng
1150–1159. Đã tự đối chiếu code thật với văn bản, không chỉ tin Dev báo.

**7. R7-03 — append, không overwrite**: đã tự kiểm bằng `git diff`. `docs/CHANGELOG.md`:
`grep -c "^-[^-]"` = 0 (không xoá dòng nào). `docs/design-log.md`: = 0. `docs/Architecture.md`: có
2 dòng bị thay (không phải xoá lịch sử — mở rộng nội dung "Cost ở v1.0 là ước lượng..." để phân
biệt rõ nhánh `pdf2zh` vs `babeldoc`, và Architecture.md vốn KHÔNG phải file append-only theo
Protocol C — nó là hợp đồng hiện hành, được phép sửa tại chỗ). Không có dấu hiệu ghi đè lịch sử.

**8. Test + lint**: tự chạy (không tin số Dev báo).
- `uv run ruff check src/ tests/` → sạch.
- `uv run ruff format --check` trên đúng 9 file trong phạm vi diff (kể cả file test mới) → đã
  format sẵn, không cần reformat (17 file cần reformat toàn repo là drift CŨ, không liên quan diff
  này — đã tự đối chiếu bằng `ruff format --diff` chỉ trên các file S4, không có output).
- `uv run pytest tests/test_openai_provider_thinking.py tests/test_epub_document.py
  tests/integration/test_epub_translate_guards.py` → 83 passed.
- `uv run pytest` (toàn bộ suite) → 827 passed (1 warning `RuntimeError: Event loop is closed` là
  artifact teardown `aiosqlite` không liên quan, không phải test fail).
- `python3 scripts/validate_state.py` → hợp lệ, 2 cảnh báo Protocol C (Architecture.md/CHANGELOG.md
  vượt ngân sách dòng) — không chặn, đã có trong backlog (BL-11) từ trước.

### Phát hiện quan trọng — chưa đủ điều kiện release, không phải lỗi của K-1..K-5

Đọc `docs/design-log.md` (dòng 6618–6639) và `project_state.json` (BL-12): live E2E job
`bfc0ac24-...` dịch xong 66/66 chunk (xác nhận K-2/K-3/K-5 hoạt động đúng, gate G-2 §6.20.15 đạt),
NHƯNG job cuối `status="failed"` ở bước MERGE vì 1 guard OCF có sẵn từ trước (`mimetype` không ở
dạng `ZIP_STORED`) — bug ĐỘC LẬP, không do K-1..K-5 gây ra, chỉ mới lộ ra vì lần này là lần đầu 1
job EPUB thật chạy hết 66 chunk tới bước merge. Dev đã báo cáo trung thực (không giấu), ghi backlog
BL-12 "QUAN TRỌNG — đang CHẶN job thật của Hiếu", trạng thái `open`.

**Hệ quả cho gate G-4 (§6.20.15, R6-03)**: *"mở EPUB output thật, xác nhận có chữ tiếng Việt CÓ
DẤU, không chỉ tin status=completed"* — gate này **CHƯA đạt được** cho luồng end-to-end thật, vì
chưa có file output cuối nào được tạo ra (merge fail trước khi ghi output). K-1's test riêng
(`test_load_write_translated_and_to_markdown_share_same_kobo_unwrap`, mục 3 checklist trên) CÓ mở
lại file output và xác nhận tiếng Việt có dấu — nhưng đó là unit test tự dựng EPUB tối giản, KHÔNG
phải G-4 (live E2E, sách thật, xuyên suốt cả pipeline). Đây là **non-blocking cho việc APPROVE code
S4** (đúng phạm vi brief, bug merge ngoài phạm vi K-1..K-5, đã disclosed đầy đủ), nhưng **BẮT BUỘC
QA không được đánh dấu `ready_for_release` cho S4/US-22 tới khi G-4 thật sự đạt** — hoặc chạy lại
live E2E sau khi BL-12 được sửa, hoặc dùng 1 EPUB nguồn khác không dính lỗi OCF mimetype để xác
nhận riêng phần K-1..K-5 tới hết pipeline. Ghi lại ở đây để QA không bỏ sót.

### Kết luận

**APPROVE** (Vòng 1/3) cho phần code thuộc phạm vi S4 (K-1..K-5, `src/core/job_orchestrator.py`,
`src/services/translation.py`, `src/services/openai_provider.py`,
`src/services/deepseek_provider.py`, `src/core/config.py`, `src/services/epub_document.py`). Đã tự
verify độc lập từng điểm PM/Tech Lead lo ngại (vị trí unwrap koboSpan đúng chỗ, data lineage 3
đường đọc dùng chung, phạm vi bóc hẹp đúng deny-by-default, mock có golden file backing thật, K-4
có số đo không phải né việc, Architecture.md khớp code thật, không có ghi đè lịch sử tài liệu). Test
pass toàn bộ (827), ruff sạch. Không có blocking issue nào ở code hoặc test.

**Không blocking, nhưng bắt buộc QA đọc trước khi release**: gate G-4 (§6.20.15) chưa đạt ở mức
live E2E full pipeline do BL-12 (bug merge OCF độc lập, chưa sửa) — xem mục "Phát hiện quan trọng"
ở trên.

## S5 — UI hint "chọn thư mục tải file" (2026-09-12)

**Phạm vi**: `web/index.html` (dòng ~152), `web/history.html` (dòng ~54-56), `docs/CHANGELOG.md`
(append). Chỉ HTML tĩnh (`<span title="...">`), không có JS/logic mới, không đụng `web/js/*.js`
hay `src/`. Xác nhận bằng `git diff --stat`: 6 file đổi (`docs/*`, `project_state.json`,
`web/history.html` +3/-1, `web/index.html` +1) — không có file `.py`/`.js` nào trong diff.

**1. Đối chiếu nội dung tooltip với nguồn xác thực §6.24**: **KHỚP**. Đã đọc
`docs/Architecture.md` dòng 8359-8385 (Tech Lead verify qua source Chromium
`download_target_determiner.cc:333-336/757` và Firefox `HelperAppDlg.sys.mjs:356-365/399` +
`DownloadLastDir.sys.mjs`, không suy đoán). Đối chiếu từng điểm bắt buộc trong brief:
- 2 chuỗi tiếng Anh giữ nguyên, đúng nguyên văn, đặt trong dấu ngoặc kép (`&quot;...&quot;`):
  `"Ask where to save each file before downloading"` (Chrome) và `"Ask where to save files before
  downloading"` (Firefox) — không dịch, không đổi 1 ký tự nào so với §6.24.
- Có mệnh đề loại trừ `"(trừ chế độ ẩn danh/riêng tư)"` — khớp §6.24 ("private/incognito không lưu
  lại").
- Không nhắc Safari/Edge ở đâu trong tooltip — đúng, §6.24 chỉ verify Chrome/Firefox.
- Chủ thể của hành vi "nhớ thư mục" là **"hộp thoại lưu"** ("hộp thoại lưu sẽ mở sẵn ở thư mục bạn
  chọn lần gần nhất"), không phải "hệ thống"/"app" — đúng yêu cầu, khớp kết luận wording ở §6.24
  ("KHÔNG claim app tự nhớ").
- Không rút gọn làm mất ý: cả điều kiện tiên quyết ("bật cài đặt trình duyệt") và tên đường dẫn
  setting cụ thể (Chrome: Settings > Downloads; Firefox: Settings > General > Downloads) đều được
  giữ đủ.

**2. HTML escape**: **ĐÚNG**. `title="..."` dùng `&quot;` cho dấu nháy kép nằm trong attribute
(bắt buộc — nháy kép sống sẽ đóng attribute sớm, vỡ hoàn toàn phần còn lại của tag), `&gt;` cho
`>` và `&mdash;` cho gạch ngang dài — cả 2 không bắt buộc phải escape trong attribute value nhưng
vô hại, không gây lỗi render. Đã đọc raw source (không chỉ nhìn qua): không có dấu `"` sống nào lọt
vào giữa chuỗi title ở cả 2 file — `grep -c` xác nhận đúng 1 span/file, không có tag nào bị cắt
cụt do escape sai.

**3. `web/history.html` — hint chỉ 1 lần ở header, không lặp theo row**: **ĐÚNG**, đã tự trace
bằng tay: span mới nằm trong `<th>` (dòng 54-56, trong `<thead>`), còn `<tr>` lặp job
(`x-for="job in jobs"`) nằm trong `<tbody>` (dòng 60-81) — 2 khối HTML tách biệt, `<th>` không nằm
trong template lặp nên không nhân bản. `git diff` xác nhận đúng 1 chỗ thay đổi trong file
(`<th class="p-2"></th>` cũ → `<th class="p-2 text-right"><span ...></th>`), không có thay đổi nào
trong `<tbody>`/`<template x-for>`. `colspan="8"` ở dòng "Chưa có job nào" không đổi và vẫn đúng
(đếm lại: 8 cột `<th>`, không tăng số cột — span nằm lồng trong `<th>` cuối, không thêm `<th>` mới).

**4. Phạm vi đúng đã chốt với Hiếu**: không có JS mới, không dùng File System Access API
(`showSaveFilePicker`) — đúng quyết định ở §6.24 ("KHÔNG dùng File System Access API"). Không đụng
`src/`.

**5. `docs/CHANGELOG.md` — R7-03 (append, không overwrite)**: đã tự kiểm bằng `git diff
docs/CHANGELOG.md` — toàn bộ diff chỉ có dòng `+` (thêm mới), 0 dòng `-`, phần thêm nằm sau dòng
cuối cùng của nội dung cũ (`Theo brief — PM điều phối commit sau khi Reviewer + QA duyệt qua vòng
thật.`). Không có nội dung cũ nào bị xoá/ghi đè.

**6. R5-04 (external contract verification checklist)**: **N/A**. Đây không phải service wrapper
gọi external tool (`*_runner.py`/`*_provider.py`) — chỉ là UI tĩnh (HTML `title` attribute) không
gọi API/CLI/SDK nào lúc runtime. Nội dung tooltip tham chiếu hành vi browser nhưng không gọi
browser API nào (không dùng File System Access API) — bản thân browser-setting-name đã được Tech
Lead verify qua source thật ở §6.24 (không phải claim chưa verify của Reviewer).

**7. Test**: Dev không sửa file `.py` nên không cần `ruff`; đã tự xác nhận lại bằng
`git diff --stat` rằng không có file `.py` nào trong diff của item này. Chấp nhận báo cáo "827
passed" của Dev vì không có thay đổi logic Python nào có thể ảnh hưởng tới suite test — rủi ro hồi
quy từ thay đổi HTML tĩnh gần như bằng 0.

### Kết luận

**APPROVE** (Vòng 1/3) cho S5 — UI hint chọn thư mục tải file (`web/index.html`,
`web/history.html`, `docs/CHANGELOG.md`). Tooltip khớp 100% nội dung đã verify ở
Architecture.md §6.24 (không dịch sai/rút gọn mất ý/thêm claim không nguồn), HTML escape đúng,
hint chỉ xuất hiện 1 lần ở header `history.html` (không spam theo row), không có JS/logic mới,
không đụng `src/`, CHANGELOG.md append đúng cách. Không có blocking issue.

## BL-10 — Chi phí ĐO THẬT cho nhánh PDF/babeldoc (`cost_source='metered'`) (2026-09-13)

**Phạm vi review**: `src/services/babeldoc_runner.py`, `src/services/pdf2zh_runner.py`,
`src/core/job_orchestrator.py`, `src/models/chunk.py`, `src/models/database.py`,
`tests/test_babeldoc_runner.py`, `tests/integration/test_job_orchestrator.py`,
`tests/integration/test_job_cancel.py`, `tests/integration/test_job_orchestrator_concurrency.py`,
`tests/fixtures/babeldoc/token_usage_stdout.txt` (golden file mới), `docs/CHANGELOG.md`. Đối chiếu
với đặc tả `docs/Architecture.md` §6.23 (dòng 8003–8358).

**1. Correctness thường lệ**: Đọc toàn bộ diff `job_orchestrator.py`/`babeldoc_runner.py`. Logic
2 nhánh (`usage is not None` / fallback) đúng như pseudocode §6.23.4, không leak exception nào
mới (đường parse bọc trong hàm thuần `parse_babeldoc_token_usage`, trả `None` thay vì raise khi
thiếu dòng — đã tự đọc code, không chỉ tin docstring). Type hints đầy đủ (`BabeldocTokenUsage`
frozen dataclass, `parse_babeldoc_token_usage(stdout: str) -> BabeldocTokenUsage | None`,
`rollup_cost_source(chunks: Sequence[Chunk]) -> str`).

**2. R6-02 — test lineage giá trị cụ thể, không chỉ "đã gọi"**: **ĐẠT**, đã đọc từng test mới
trong `test_job_orchestrator.py`:
- `test_metered_chunk_lineage`: bơm `real_token_usage=BabeldocTokenUsage(total=30925, prompt=20000,
  completion=10925, ...)` qua đúng `pdf2zh_result` return value của lần dịch chunk đó (không qua
  biến cấp job/self) → assert `chunk.api_tokens_used == 30925` **VÀ** `chunk.cost_source ==
  "metered"` **VÀ** `chunk.api_cost == pytest.approx(provider.estimate_cost(20000, 10925))` (tính
  lại bằng chính provider, không hard-code số tiền) **VÀ** `job.cost_source == "metered"` (rollup
  cấp job) — vượt cả yêu cầu tối thiểu của gate test #4 vì còn verify luôn rollup job.
- `test_estimated_fallback_when_no_token_line`: `real_token_usage=None` (mặc định của
  `_fake_babeldoc_runner()`) → `chunk.cost_source == "estimated"` và `api_tokens_used > 0` (không
  silent-break đường ước lượng cũ) + `job.cost_source == "estimated"`.
- `test_pdf2zh_never_metered`: engine pdf2zh (`reports_token_usage=False`) → `chunk.cost_source ==
  "estimated"`, `job.cost_source == "estimated"`.
- `test_rollup_cost_source` (unit thuần, không qua DB): 3 case đúng theo §6.23.5 — toàn bộ metered
  ⇒ `"metered"`; trộn 2 metered + 1 estimated ⇒ `"estimated"` (không phải lấy chunk cuối, không có
  giá trị thứ 3); không chunk nào có `api_cost` ⇒ `"estimated"`.

Không có test nào trong bộ mới chỉ dừng ở `assert_called()`/`assert_awaited()` — mọi test đều
assert giá trị cụ thể đi qua chuỗi `stdout` (golden) → `BabeldocResult.real_token_usage` →
`chunk.{api_tokens_used,cost_source,api_cost}` → `job.cost_source`.

**3. R8-03 — capability, không rẽ nhánh cứng theo tên/class engine**: **ĐÚNG khuôn**. Đã đọc kỹ
property `_reports_token_usage` (`job_orchestrator.py:665-681`): hỏi
`self._translator_runner.reports_token_usage` (thuộc tính trên chính object runner đang được chọn
qua property `_translator_runner`, KHÔNG có `isinstance(self._translator_runner, BabeldocRunner)`
hay `if engine == "babeldoc"` nào trong thân hàm). Guard `isinstance(value, bool)` mà Dev nói tới
KHÔNG phải guard theo class name — đây là guard theo KIỂU DỮ LIỆU trả về (đề phòng
`AsyncMock(spec=...)` không set thuộc tính trả về 1 `Mock` object thay vì `bool`), đúng y hệt
khuôn `_needs_font_shrink`/`_reports_own_paragraph_drops` đã có sẵn trước đó (`job_orchestrator.py`
đọc dòng 636-681, 3 property liền kề cùng pattern). Không phải "rẽ nhánh cứng trá hình" — đã tự
đối chiếu, không chỉ tin lời Dev.

**4. §6.23.5 rollup `jobs.cost_source`**: **ĐÚNG** — `rollup_cost_source()` (`job_orchestrator.py`)
trả `"metered"` chỉ khi `{c.cost_source for c in chunks if c.api_cost is not None} == {"metered"}`,
tức **có ≥1 chunk estimated (trong tập có `api_cost`) ⇒ job estimated**, không phải lấy chunk cuối
cùng hay ngược lại. Áp dụng đúng 2 điểm bắt buộc: Bước 10 (`job_orchestrator.py:1062`, dùng toàn
bộ `chunks`) và nhánh `cost_capped` (dùng `chunks[:position]` — đúng tập đã cộng vào
`completed_cost`, khớp yêu cầu §6.23.5). Nhánh EPUB: đã grep toàn file xác nhận cả 4 vị trí
`chunk.api_tokens_used = total_input_tokens + total_output_tokens` (dòng 2441, 2512, 2749, 2809)
đều được thêm đúng `chunk.cost_source = "metered"` ngay cạnh — không sót vị trí nào; 5 vị trí
`job.cost_source = "metered"` cấp job (dòng 1246, 1305, 1342, 1466, 1728) giữ nguyên không đổi
đúng như "Nhánh EPUB không đổi luật".

**5. Migration an toàn (`server_default`)**: đã tự verify bằng cách chạy thật (không chỉ tin Dev):
- `uv run python3` dựng 1 bảng SQLAlchemy tối giản với `server_default="estimated"` (giống cách
  `sa_column_kwargs` truyền vào `Field`) → `CreateTable` sinh đúng `DEFAULT 'estimated'` (có quote,
  SQLAlchemy tự escape literal string) — không phải `DEFAULT estimated` (invalid SQL) như lo ngại
  ban đầu khi đọc code.
- Chạy thật `tests/test_database_chunks_unit_columns_migration.py` (test **có sẵn từ trước**, mô
  phỏng bảng `chunks` legacy KHÔNG có cột `cost_source`) — pass, xác nhận đường
  `_migrate_chunks_unit_columns()` (rebuild bảng qua `create_all()` + `INSERT...SELECT` với
  `col_list` đọc từ `PRAGMA table_info` của bảng cũ, không liệt kê `cost_source`) không vỡ NOT NULL
  constraint nhờ `server_default` áp dụng tại thời điểm `create_all()`.
- Đường nâng cấp phổ biến hơn (DB đã có `page_start` nullable từ trước, chỉ thiếu `cost_source`)
  đi qua `_add_missing_columns()` → `ALTER TABLE chunks ADD COLUMN cost_source TEXT NOT NULL
  DEFAULT 'estimated'` — SQLite cho phép cú pháp này (đã biết từ trước, không cần verify lại).

**6. R5-04 (Protocol 5, checklist bắt buộc cho service wrapper)**: **External contract verified
against real source: YES (nguồn: golden file `tests/fixtures/babeldoc/token_usage_stdout.txt` —
đã tự đọc nguyên văn nội dung file, xác nhận đây là output thật của 1 lần chạy babeldoc 0.6.4 thật
qua DeepSeek API, KHÔNG phải bịa tay: có timestamp thật khớp ngày review [09/13/26], có đường dẫn
output tuyệt đối trỏ vào chính thư mục scratchpad của session Dev
`/private/tmp/claude-501/.../scratchpad/bl10_spike_out/...` — dấu hiệu không thể giả lập bằng cách
gõ tay theo mô tả Architecture.md, có cảnh báo pymupdf `fitz` deprecated thật, có progress bar
rich thật, và 4 dòng `Total tokens:`/`Prompt tokens:`/`Completion tokens:`/`Cache hit prompt
tokens:` khớp 100% định dạng đã verify ở §6.23.1 T4/T7 — tiền tố `INFO:babeldoc.main:`, không dấu
phân cách nghìn, đúng nhãn, đúng thứ tự)**. Không phải mock viết tay theo giả định — đạt yêu cầu
Protocol 5 mục 3.

**7. Đối chiếu 8 test §6.23.7**: cả 8 đều có mặt, với tên khớp hoặc gần khớp có ghi chú "Gate test
#N" ngay trong docstring (thuận tiện trace ngược về Architecture.md):
1. `test_parse_token_usage_golden` ✓ (`tests/test_babeldoc_runner.py`)
2. `test_parse_token_usage_no_cache_hit_confusion` ✓ (chống đúng bẫy case-sensitive/substring)
3. `test_parse_token_usage_missing_lines_returns_none_no_raise` ✓ (gộp luôn case "chỉ có Total
   tokens" — đúng yêu cầu "thiếu bất kỳ dòng nào trong 3 dòng bắt buộc ⇒ `None`")
4. `test_metered_chunk_lineage` ✓ (`tests/integration/test_job_orchestrator.py`)
5. `test_estimated_fallback_when_no_token_line` ✓
6. `test_pdf2zh_never_metered` ✓
7. `test_reports_token_usage_property_isinstance_guard_catches_unset_mock` ✓ (đúng khuôn 2 guard
   test có sẵn cho `needs_font_shrink`/`reports_own_paragraph_drops`)
8. `test_rollup_cost_source` ✓

Thêm 2 test không bắt buộc nhưng hợp lý: `test_parse_token_usage_ignores_stderr_only_lines` (củng
cố ràng buộc "chỉ đọc stdout") và
`test_translate_pages_parses_real_token_usage_from_golden_stdout` (test tích hợp cấp
`BabeldocRunner.translate_pages()`, xác nhận golden stdout thật sự chảy được tới
`BabeldocResult.real_token_usage` qua đúng subprocess mock — không chỉ test hàm parse thuần tuý)
và `test_babeldoc_runner_reports_token_usage_capability_is_true`.

**8. Phạm vi thay đổi**: đã tự chạy `git diff --stat` toàn bộ — xác nhận **KHÔNG** đụng
`docs/Architecture.md`, `docs/design-log.md`, `src/services/deepseek_provider.py`. Grep xác nhận
`estimate_chunk_cost()` không bị sửa nội dung — 2 dòng gọi hàm này trong `_process_chunk()` chỉ bị
**di chuyển** vào nhánh `else` (nguyên văn, không đổi tham số/logic bên trong hàm), không phải bị
xoá — đã đối chiếu diff đầy đủ để phân biệt "move" với "delete". `docs/CHANGELOG.md`: `git diff |
grep -c "^-[^-]"` = 0, chỉ có dòng thêm mới, append đúng cuối file — đạt R7-03.

**9. Test + lint (tự chạy, không tin báo cáo Dev)**:
- `uv run ruff check src/ tests/` → sạch.
- `uv run ruff format --check` trên đúng 9 file thuộc phạm vi diff → đã format sẵn, không cần
  reformat.
- `uv run pytest tests/test_babeldoc_runner.py tests/integration/test_job_orchestrator.py -q` →
  94 passed.
- `uv run pytest` (toàn bộ suite) → **838 passed**, không có regression.
- `uv run pytest tests/test_database_chunks_unit_columns_migration.py
  tests/test_database_finished_at_migration.py -q` (chạy riêng để tự verify mục 5 ở trên, không
  nằm trong yêu cầu brief nhưng cần thiết để xác nhận migration an toàn bằng thực nghiệm chứ không
  chỉ đọc code) → 5 passed.

### Kết luận

**APPROVE** (Vòng 1/3) cho BL-10 — chi phí đo thật `cost_source='metered'` cho nhánh
PDF/babeldoc. Code khớp sát đặc tả §6.23, data lineage đúng (R6-01/R6-02, không lặp lại kiểu lỗi
Bug #5), capability đúng tinh thần R8-03 (không rẽ nhánh cứng theo tên engine), rollup job đúng
"có 1 chunk estimated ⇒ job estimated", migration `server_default` đã tự verify chạy thật (không
chỉ tin lời Dev), golden file là output thật (không phải mock viết tay), đủ cả 8 test bắt buộc
theo §6.23.7 (cộng thêm vài test có giá trị). Test toàn repo pass (838), ruff sạch. Không có
blocking issue.

**Không blocking, ghi nhận để theo dõi** (đã có sẵn trong Architecture.md §6.23.8, không phải phát
hiện mới của Reviewer, nhắc lại ở đây để không ai bỏ sót khi release): (a) bảng giá DeepSeek có thể
lỗi thời — `cost_source='metered'` chỉ đảm bảo *số token* là thật, không đảm bảo *số tiền* đúng;
(b) under-count khi có retry (token của attempt fail không được cộng); (c) chưa chiết khấu
cache-hit token (thiên về ước cao, an toàn). QA cần đọc §6.23.8 trước khi release, và theo R5-03 +
R6-03, phải có ít nhất 1 lần chạy job PDF thật bằng babeldoc, mở DB đối chiếu
`sum(chunks.api_tokens_used)` với tổng token in trong log thật của từng chunk trước khi đánh dấu
`ready_for_release` — golden file ở review này là spike đơn-chunk (1 trang), chưa phải live E2E
nhiều-chunk theo đúng yêu cầu §6.23.7 "Live E2E".

---

## BL-12 — EPUB `mimetype` bị nén/sai vị trí OCF: normalize khi ghi, reject sớm khi thiếu hẳn (2026-09-16)

**Phạm vi**: `src/services/epub_document.py` (hàm mới `_check_mimetype_entry()`, sửa
`write_translated()`), `tests/test_epub_document.py` (+8 test), `docs/CHANGELOG.md` (đoạn BL-12).
Đối chiếu với `docs/Architecture.md` §6.25 và Final Decision ở `docs/design-log.md` mục BL-12
(§9/§10: Phương án D — chuẩn hoá `mimetype` khi ghi output; reject sớm khi thiếu hẳn/sai nội dung).

### 1. Đối chiếu Final Decision (§6.25.2)

- **L1 (`load()`, `_check_mimetype_entry()`, gọi ngay sau `_check_drm()` — đúng vị trí brief yêu
  cầu, `epub_document.py:767-768`)**: chỉ reject khi thiếu hẳn entry `mimetype` hoặc nội dung khác
  `b"application/epub+zip"` — KHÔNG kiểm thứ tự/`compress_type` ở đây. Đúng đặc tả. Route map sang
  HTTP 400 đã verify tại `src/api/routes/jobs.py:377-381` (`except EpubParseError`), và `load()`
  được gọi ở `cost_gate.py:167` → reject xảy ra **trước** cost gate, đúng ý "user biết trước khi
  tốn tiền". Đọc code xác nhận trực tiếp, không suy đoán.
- **L2 (`write_translated()`, `:985-1017`)**: 2 nhánh reject cũ đã bị xoá đúng như Final Decision
  yêu cầu ("thay thế 2 nhánh reject tại `epub_document.py:985-991`"). Thay bằng: tìm `mimetype` bất
  kể vị trí trong `infolist`, đặt lên đầu `ordered_infos`, ép `compress_type = ZIP_STORED` chỉ cho
  entry này, các entry còn lại giữ nguyên `compress_type` gốc. Khớp đúng bảng L1/L2 ở §6.25.2.

Kết luận mục này: **đúng theo Final Decision**, không có sai lệch.

### 2. Correctness — thứ tự entry + nội dung/thứ tự phần còn lại

- Đọc trực tiếp `write_translated()` (`:985-1017`): `ordered_infos = [mimetype_info, *rest_infos]`
  với `rest_infos` giữ nguyên thứ tự xuất hiện trong `infolist` gốc (chỉ lọc bỏ `mimetype`, không
  sort lại) → **đảm bảo mimetype luôn là entry ĐẦU TIÊN được ghi ra** (không chỉ đúng
  `compress_type`, mà đúng cả vị trí ghi trong file zip output — `out_zf.writestr()` được gọi tuần
  tự theo `ordered_infos`, zip ghi tuần tự nên thứ tự file header = thứ tự gọi `writestr`).
  Test `test_write_translated_moves_mimetype_to_front_when_not_first_entry` chứng minh đúng bằng
  dữ liệu (không chỉ đọc code): tạo fixture có `mimetype` ở vị trí thứ 2, output đưa nó lên đầu,
  và assert `rest_out == rest_expected` (danh sách tên các entry còn lại, đúng thứ tự) — bắt được
  cả trường hợp lỗi tiềm ẩn "sort nhầm/đảo lộn phần còn lại", không chỉ "có mặt".
- Nội dung entry không bị `mimetype`-normalize đụng tới: `data = modified_entries.get(info.filename)
  or src_zf.read(info.filename)` — chỉ entry đã dịch mới lấy từ `modified_entries`, còn lại đọc
  nguyên byte từ src. Test cũ `test_write_translated_monolingual_preserves_untouched_entries` (đã
  có từ trước BL-12, không bị sửa) vẫn assert `zin.namelist() == zout.namelist()` và nội dung byte
  từng entry chưa đụng — chạy lại xanh (xem mục 6) xác nhận BL-12 không phá vỡ bất biến này (vì
  `SOURDOUGH_PATH` vốn đã có `mimetype` STORED-đầu-tiên, theo bảng đo §6.25.5, nên thứ tự không đổi
  cho đúng file này).

Kết luận mục này: **đúng**, có bằng chứng test, không chỉ đọc code suy luận.

### 3. Verify độc lập claim "flag_bits là dead code" (không chỉ tin lời Dev, không chỉ tin lại design-log)

Tự đọc trực tiếp source `zipfile` đã cài ở `.venv` (`CPython 3.14.7`, đường dẫn
`~/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/lib/python3.14/zipfile/__init__.py`,
xác nhận đúng interpreter mà `.venv/bin/python3` trỏ tới):
- `writestr()` (dòng 2008-2038) luôn gọi `self.open(zinfo, mode='w')` → `_open_to_write()`.
- `_open_to_write()` dòng 1819: `zinfo.flag_bits = _MASK_UTF_FILENAME` — **gán đè vô điều kiện**,
  không có `if`/điều kiện giữ giá trị cũ nào trước đó.

⇒ Dòng `new_info.flag_bits = info.flag_bits` (bản cũ) không có tác dụng gì — claim của Dev **đúng**,
và đã verify bằng nguồn thật (đọc trực tiếp source, không dựa trí nhớ) — không chỉ kế thừa lại kết
quả spike của Tech Lead trong design-log (Dev tự verify độc lập, đúng tinh thần "version tool đổi
phải verify lại" áp dụng chặt cho cả trường hợp không đổi version — cẩn trọng hợp lý). Grep xác
nhận dòng này đã bị xoá khỏi `epub_document.py` (không còn `flag_bits` nào trong file).

### 4. Test có chứng minh round-trip thật, không tự nhất quán với giả định sai

- `test_write_translated_normalizes_deflated_mimetype_from_real_violating_file` dùng **file EPUB
  thật** đã gây bug gốc (`data/uploads/4a752f64-..._Sourdough Culture...epub`, xác nhận file này
  tồn tại thật trên đĩa, 4MB, đúng đường dẫn nêu trong design-log §BL-12 mục 2/3). Assertion không
  chỉ "không raise": kiểm `zipfile.testzip() is None` (toàn vẹn zip), `infolist()[0].filename ==
  "mimetype"`, `compress_type == ZIP_STORED`, `extra == b""`, nội dung đúng, và **đọc lại bằng
  `ebooklib.epub.read_epub()`** (thư viện độc lập, không phải chính code app) xác nhận `spine`
  không rỗng — đây chính là kiểu kiểm tra "mở file ra xem có đọc lại được không" mà Protocol 6
  R6-03 yêu cầu, tránh lặp lại kiểu lỗi Bug #5 (tin field trạng thái thay vì tin nội dung thật).
- `test_bl12_violating_file_has_mimetype_deflated` giữ vai trò "guard tiền đề" — nếu file bằng
  chứng gốc đổi, test này fail trước, không để 2 test round-trip phía dưới mất ý nghĩa mà không ai
  biết. Thiết kế test tốt.
- Test L1 (`test_load_raises_parse_error_when_mimetype_entry_missing`,
  `..._mimetype_content_wrong`) dùng `pytest.raises(EpubParseError, match="mimetype")` — chặt hơn
  "raises Exception" trơn, xác nhận đúng loại lỗi + có nhắc tới `mimetype` trong message.
- Không phát hiện mock nào viết tay theo giả định thay cho gọi hàm thật — mọi test gọi thẳng
  `EpubDocument.load()`/`write_translated()` thật, hoặc dùng `_build_minimal_epub()` (fixture EPUB
  hợp lệ tự dựng bằng `zipfile`, đã có từ trước BL-12, không phải mock cho chính hàm đang test).

Kết luận mục này: **đạt Protocol 5 mục 3** — có golden file/file thật backing, không tự xác nhận
giả định của chính nó.

### 5. Security / Performance

- Không phát hiện path traversal mới: entry name dùng để đọc/ghi (`info.filename`) bắt nguồn từ
  chính `infolist()` của file zip đã `load()` qua `zipfile.ZipFile` (thư viện chuẩn tự chuẩn hoá
  tên entry khi liệt kê), không ghép chuỗi path từ input ngoài, không đổi so với hành vi gốc trước
  BL-12 — BL-12 chỉ thêm bước sắp xếp lại thứ tự ghi, không đổi cách lấy tên entry.
- `_check_mimetype_entry()` đọc `zf.read("mimetype")` — file rất nhỏ (đặc tả 20-22 byte theo RCA),
  không có rủi ro memory.
- `write_translated()` vẫn giữ nguyên chiến lược cũ: chỉ giữ nội dung các entry ĐÃ dịch trong
  `modified_entries` (dict nhỏ, chỉ các doc XHTML có thay đổi), các entry khác đọc-rồi-ghi ngay
  (streaming qua từng `info` trong vòng lặp, không tải hết zip vào RAM cùng lúc) — không có
  regression về memory so với code cũ, việc thêm bước tìm/sắp xếp `mimetype` chỉ là 1 lần lọc
  O(n) trên danh sách entry (thường vài chục tới vài trăm), không đáng kể.
- Ghi qua file tạm `+ .tmp` rồi `replace()` (atomic trên cùng filesystem) — không đổi so với hành
  vi cũ, giữ nguyên tính an toàn khi ghi đè.

Kết luận mục này: không có vấn đề mới.

### 6. Regression — chạy thật, không chỉ tin báo cáo Dev

- `.venv/bin/python3 -m pytest tests/test_epub_document.py -q` → **66 passed** (tự chạy).
- `.venv/bin/python3 -m pytest tests/ -q` (toàn bộ suite) → **844 passed**, không regression ở
  chỗ khác trong repo.
- `.venv/bin/python3 -m ruff check src/services/epub_document.py tests/test_epub_document.py` →
  sạch. `ruff format --check` → đã format sẵn.
- Test cũ liên quan tới cấu trúc entry (`test_write_translated_monolingual_preserves_untouched_entries`,
  `test_write_translated_writes_via_tmp_then_replaces`, `test_load_raises_parse_error_when_container_xml_missing`
  — test này dùng `_build_minimal_epub` không có `mimetype` qua nhánh cũ khác, đã tự đọc lại xác
  nhận không đổi hành vi) đều xanh, không cần sửa để thích nghi với BL-12 — dấu hiệu tốt cho thấy
  thay đổi không phá vỡ bất biến sẵn có.

### 7. R7-03 — CHANGELOG.md có đúng append không

Đọc `docs/CHANGELOG.md`: đoạn BL-12 (`## BL-12 — ...`) nằm **sau** đoạn BL-10 gần nhất (dòng
~8204, sau `### KHÔNG commit` của mục BL-10), không có dấu hiệu nội dung cũ bị xoá/ghi đè — xác
nhận bằng `wc -l` (8273 dòng, tăng so với trước) và đọc phần cuối file. **Đạt R7-03.**

### 8. Checklist bắt buộc theo brief Reviewer (CLAUDE.md)

- **R5-04**: `epub_document.py` không phải `*_runner.py`/`*_provider.py` gọi external service qua
  subprocess/HTTP — đây là code xử lý zip/XML nội bộ bằng `zipfile`/`ebooklib` (thư viện Python
  import trực tiếp). Theo "Phạm vi áp dụng" của Protocol 5 (CLAUDE.md), `pymupdf`/thư viện Python
  thuần dùng API core không thuộc phạm vi R5-04. → **N/A** cho phần lõi `epub_document.py`. Tuy
  nhiên `write_translated()`/`_check_mimetype_entry()` DÙNG claim cụ thể về hành vi `zipfile`
  (`writestr()` không sinh extra field, `flag_bits` bị gán đè) — phần này ĐÃ được verify against
  real source (mục 3 ở trên): **External contract verified against real source: YES** (nguồn: đọc
  trực tiếp `zipfile/__init__.py` của `.venv`, CPython 3.14.7, dòng 1819/2008-2038 — không chỉ kế
  thừa lại spike cũ của Tech Lead trong design-log).
- **R6-04**: `epub_document.py` không phải `*_orchestrator.py` gọi tuần tự nhiều service — đây là
  1 class xử lý 1 file EPUB, không có chuỗi bước external-tool nối tiếp nhau kiểu OCR→dịch. → **N/A**.
  (Data lineage của `write_translated()` đọc `self.path` không đổi so với §6.20, đã tự đối chiếu ở
  mục 2 — không phát hiện đứt gãy lineage kiểu Bug #5.)
- **R8-01**: BL-12 không thêm engine/backend/biến thể mới đi qua pipeline dùng chung — đây là bug
  fix cho 1 lớp input (EPUB vi phạm OCF) của cùng 1 luồng xử lý EPUB, không phải thêm variant mới.
  → **N/A**.
- **Protocol 5 R5-03**: 6/8 test BL-12 dùng file EPUB thật (`4a752f64-..._Sourdough Culture...epub`)
  hoặc fixture tự dựng hợp lệ bằng `zipfile` (không phải mock cho chính hàm đang test) — đã tự đọc
  từng test để xác nhận (mục 4). **Có golden file/dữ liệu thật backing, không viết tay theo giả
  định.**

### Kết luận

**APPROVE** cho BL-12. Code khớp đúng Final Decision (Phương án D) và §6.25.2, thứ tự + nội dung
entry output đã verify bằng test có assertion cụ thể (không chỉ "không raise"), claim về hành vi
`zipfile` (`flag_bits` dead code) đã tự verify độc lập bằng đọc source thật — không chỉ tin lời Dev
hay kế thừa lại nguồn xác thực cũ. Toàn bộ 844 test + ruff sạch. CHANGELOG.md tuân thủ R7-03 (append
đúng cách). Không có blocking issue.

**Không blocking, đưa vào `backlog[]`** (đã ghi nhận sẵn ở CHANGELOG/design-log, nhắc lại để PM
không bỏ sót owner theo R5-06): đo hành vi reading system thật (Apple Books, Calibre, Kobo, Kindle
Previewer) với `mimetype` bị nén trước khi chuẩn hoá + cài `epubcheck` để có kiểm định OCF độc lập
cho output — hiện `⚠️ ASSUMED`/`[UNVERIFIED]` ở Architecture.md §6.25.4 chưa có owner cụ thể trong
`backlog[]`.

---

## S7 — Dịch FR→VI bên cạnh EN→VI (auto-detect ngôn ngữ nguồn, PDF + EPUB) — 2026-09-16

Phạm vi: `src/models/job.py`, `src/models/database.py`, `src/core/language_detector.py` (mới),
`src/core/wordlists/fr_function_words.txt` (mới), `src/core/cost_estimator.py`, `src/core/cost_gate.py`,
`src/core/prompt_builder.py`, `src/core/job_orchestrator.py`, `src/core/term_extraction_service.py`,
`src/api/routes/jobs.py`, `web/index.html`, `web/history.html`. Đối chiếu `docs/Architecture.md` §6.26
(§6.26.1–6.26.9), `docs/design-log.md` "S7 — Dịch FR→VI", `docs/CHANGELOG.md` đoạn Dev vừa append.

### 1. Correctness quan trọng nhất — MinerU KHÔNG BAO GIỜ nhận `lang="fr"`

Tự đọc code, không tin lời Dev. `_run_mineru_and_record_quality()` (`job_orchestrator.py:1864-1870`)
gọi `self._mineru_runner.parse_document(file_path, output_dir, parse_method=..., task_timeout_seconds=...,
should_cancel=...)` — **không hề có tham số `lang` nào ở call site này**, nghĩa là `job.source_lang`
không có đường nào chạm tới lời gọi MinerU. `MinerURunner.parse_document()` (`src/services/mineru_runner.py:110-134`)
có `lang: str = "en"` làm default và forward thẳng `lang=lang` vào request — vì call site không bao giờ
truyền `lang=`, giá trị luôn là `"en"` bất kể job FR hay EN. Đây đúng thiết kế §6.26.5 bước #1 (giữ
`lang="en"`, KHÔNG map `source_lang` vào MinerU). Có test pin trực tiếp ca này:
`test_pdf_scan_mineru_always_called_with_lang_en_even_for_fr_job`
(`tests/integration/test_job_orchestrator_source_lang.py:289-326`) — job dựng với `source_lang="fr"` từ
đầu, assert `call.kwargs.get("lang", "en") == "en"` cho MinerU **và** `call.kwargs["lang_in"] == "fr"`
cho `pdf2zh_runner.translate_pages` trong cùng 1 test — tức vừa xác nhận MinerU không đổi, vừa xác nhận
`lang_in` FR thật sự đi tới bước dịch. Tự chạy `pytest tests/integration/test_job_orchestrator_source_lang.py -q`
→ **7 passed**. **Kết luận: đúng, không phải bug.**

### 2. Regression job EN cũ (`source_lang=NULL`)

`test_translate_pages_receives_lang_in_en_for_null_source_lang` tạo job với `source_lang=None`, assert
`call.kwargs["lang_in"] == "en"` cho `translate_pages()` **và** `job.source_lang == "en"` sau khi refresh
(Step 3 tự detect+persist). `test_prompt_builder.py` có test byte-identical cho `source_lang="en"` (đọc
code `prompt_builder.py`: `_intro("en")`/`_babeldoc_intro("en")` map qua `_SOURCE_LANG_NAME_VI["en"] =
"tieng Anh"`, đúng chuỗi cũ — `build_prompt_text()`/`write_prompt_file()` (pdf2zh) **hoàn toàn không đổi
signature**, nên không thể lệch byte nào cho nhánh EN qua pdf2zh). `estimate_job_cost_v2` giữ default
`source_lang="en"` → `_chars_per_token_for_source("en") == CHARS_PER_TOKEN_EN` không đổi, golden test
`test_estimate_job_cost_v2_never_underestimates_golden_incident` vẫn xanh (đã tự chạy, xem mục 7). Đây
là assertion cụ thể trên giá trị, không chỉ tin tên test. **Đạt.**

### 3. `cost_gate` lúc estimate vs lúc chạy thật — cùng `source_lang`

Trace tay: `estimate_translation_cost()` (`cost_gate.py:106-136`) detect `source_lang` từ `full_text`
(file gốc, chưa OCR với pdf_scan) rồi gọi `estimate_job_cost_v2(..., source_lang=source_lang)` — với
`source_lang = detection.lang or "en"` (ép "en" cho estimate, nhưng `DetailedCostEstimate.source_lang`
giữ `detection.lang` thô = `None` cho pdf_scan, đúng ý đồ §6.26.4 "không ép en ở persist"). Lúc chạy
thật, `estimate_chunk_cost()` (Lớp 2, `job_orchestrator.py:2315-2326`) nhận `source_lang=job.source_lang
or "en"` — với pdf_scan, `job.source_lang` đã được Step 3 detect lại trên `full_text` sau OCR (dòng
735-739) trước khi bất kỳ chunk nào chạy, nên khi tới Lớp 2 giá trị đã ổn định và nhất quán với giá trị
dùng ở Step 5 (`write_prompt_file`/`write_babeldoc_prompt_file`) và Step 7 (`translate_pages`). Không
phát hiện lệch. **Đạt.**

### 4. `source_lang` ghi 1 lần, giữ nguyên qua resume

Đọc `Job.source_lang` (`src/models/job.py`) — comment tự nêu đúng khuôn `chunk_size_used`/`parse_method`.
Code thực thi khớp: `job_orchestrator.py:735` (`if job.source_lang is None: ... persist`) và dòng 1169
(nhánh EPUB) chỉ detect khi còn `None`, không bao giờ ghi đè giá trị đã có. Có test thật
(`test_source_lang_survives_resume_after_chunk_failure`, dòng 383-441): job 90 trang, `source_lang="fr"`
chốt sẵn, chunk 2 fail giả lập, resume bằng runner mới — verify `lang_in="fr"` xuyên suốt cả 2 lần chạy
(không đọc lại `job.source_lang` để verify không đổi tường minh sau resume, nhưng gián tiếp đã đủ: nếu
bị ghi đè thành detect-lại-từ-đầu thì `lang_in` các chunk sau resume sẽ không còn `"fr"` một cách ổn
định — non-blocking, xem mục "Suggestion" bên dưới). **Đạt về bản chất, có 1 gợi ý nhỏ.**

### 5. Hai điểm Dev báo lệch thiết kế gốc — đánh giá

**(a) Guard term-extraction đặt trong service, không chỉ ở call site (`jobs.py:537`).** Đọc
`term_extraction_service.py:145-160`: guard `if (job.source_lang or "en") != "en": return 0` nằm NGAY
đầu `extract_and_store_terms()`, trước khi hàm này chạm bất kỳ logic n-gram nào — bảo vệ đồng thời
đường tự động (`_run_job_background`) và đường thủ công (`POST /api/jobs/{id}/extract-terms`). Đây là
cải tiến hợp lý so với thiết kế gốc (đặt ở call site jobs.py:537 sẽ bỏ sót nhánh gọi thứ 2 nếu có, đúng
loại rủi ro Protocol 8/6.14.7 vốn muốn tránh — "1 nguồn sự thật" tốt hơn "2 chỗ phải nhớ sửa giống
nhau"). Không tạo lỗ hổng nào — **hợp lý, chấp nhận**.

**(b) Không thêm `source_lang` vào `build_prompt_text()`/`write_prompt_file()` (pdf2zh).** Đã tự đọc
`prompt_builder.py:140-241`: `_FILE_GLOSSARY_INSTRUCTION` (dòng 153-156, `'... GIU NGUYEN tieng Anh'`)
vẫn hard-code "tieng Anh" cho MỌI `source_lang`, khác với bảng §6.26.6 liệt kê `_GLOSSARY_INSTRUCTION`/
`_FILE_GLOSSARY_INSTRUCTION` là 2 trong 5 chuỗi "phải nhận `source_lang`". Xét về NGỮ NGHĨA: câu này nói
về **glossary entries** (`term_en`/`term_vi` — glossary dùng chung EN theo HOI-09, §6.26.5 bước #2),
không phải về ngôn ngữ TÀI LIỆU nguồn — "giữ nguyên tiếng Anh" ở đây đúng là hành vi mong muốn cho cả
job FR (glossary vẫn là các từ mượn tiếng Anh/Pháp thông dụng trong ngành bánh, ví dụ `ganache`,
`levain`), nên việc không đổi câu này không tạo ra output sai. Còn `_FILE_INTRO` (câu duy nhất thực sự
nêu "dịch từ ngôn ngữ X") dùng `${lang_in}` — pdf2zh tự thay thế bằng `lang_in="fr"` truyền qua CLI
(đã verify §6.26.1), nên tên ngôn ngữ vẫn đúng ở tầng pdf2zh dù `prompt_builder.py` không đổi. Đây là
lý do Dev đưa ra hợp lý — nhưng **bảng §6.26.6 của Architecture.md hiện đang liệt kê sai/thừa 2 mục
`_GLOSSARY_INSTRUCTION`/`_FILE_GLOSSARY_INSTRUCTION`**, cần Tech Lead cập nhật lại bảng cho khớp thực
tế (không phải lỗi Dev — non-blocking, ghi bên dưới).

### 6. R8-01/R8-04 — trace tay `job_orchestrator.py` theo bảng audit §6.26.5

Đã trace từng bước (không chỉ tin "Dev nói đã làm đúng"):
- Bước #1 MinerU: xem mục 1 — đúng, giữ `"en"`.
- Bước #3 `font_shrink_page` (`_needs_font_shrink`, dòng 623-642, gọi tại dòng 2225): không đụng gì
  tới `source_lang`, đúng thiết kế "đo bề rộng glyph thật, không phụ thuộc ngôn ngữ nguồn" — code
  không có nhánh nào tham chiếu `job.source_lang` trong `font_shrink.py` (grep xác nhận 0 hit).
- Bước #8 `overlay_rotated_text` (dòng 991-1008): `glossary_prompt=await build_system_prompt(...,
  source_lang=job.source_lang or "en")` — đúng bảng lineage.
- Bước #13 term-extraction: SKIP đúng cho FR (mục 5a).
- Step 5 (`write_prompt_file`/`write_babeldoc_prompt_file`, dòng 774-794): chỉ nhánh babeldoc truyền
  `source_lang=`; nhánh pdf2zh không truyền — khớp việc `build_prompt_text()` không có tham số này
  (xem mục 5b, không phải thiếu sót).
- Step 7 (`translate_pages`, dòng 2131-2143): `lang_in=job.source_lang or "en"` — 1 ĐIỂM GỌI DUY NHẤT
  cho cả 2 engine (đúng nguyên tắc §6.14.7 "không rẽ nhánh if engine==").
- EPUB (`run_epub_job()` dòng 1153-1196, `_process_epub_chunk()` dòng 2450-2520): `source_lang =
  job.source_lang or "en"` gán 1 lần rồi dùng lại cho MỌI lời gọi `pricing_provider.translate()`
  trong hàm (chính + 2 helper retry `_retry_single_unit`/`_retry_whole_epub_request`, dòng 2370/2403)
  — không còn literal `"en"` nào sót lại (grep `"en", "vi"` trong `job_orchestrator.py`: 0 hit sau khi
  sửa).

Không phát hiện bước nào lệch khỏi bảng audit Tech Lead đã duyệt. **Đạt.**

### 7. Test coverage — tự chạy, không chỉ tin số 37

Đọc `tests/test_language_detector.py`: 2 đoạn văn EN/FR ~500-700 từ THẬT (văn xuôi nhiều đoạn về khoa
học làm bánh mì, không phải câu ngắn nhồi từ khoá) — không phải fixture giả tạo. `fr_function_words.txt`
(213 dòng) grep xác nhận KHÔNG chứa bất kỳ từ nào trong danh sách "mơ hồ bị loại" mà Tech Lead liệt kê
(`a, en, on, son, plus, sur, or, but, part, pain, coin, chat, mode, note, page, table, sale, fin`).
Tự chạy toàn bộ 9 file test liên quan S7:

```
pytest tests/test_language_detector.py tests/test_prompt_builder.py tests/test_cost_estimator.py \
  tests/test_cost_gate_source_lang.py tests/integration/test_job_orchestrator_source_lang.py \
  tests/integration/test_epub_job_source_lang.py tests/integration/test_term_extraction_service.py \
  tests/test_jobs_route_to_detail.py tests/integration/test_create_job_source_lang_api.py -q
```
→ **81 passed**, 0 fail. `ruff check` trên toàn bộ 9 file nguồn đã sửa/tạo → sạch. `ruff format --check`
→ 1 vi phạm tiền tồn tại ở `src/api/routes/jobs.py:384`, KHÔNG liên quan tới đoạn diff S7 (đã tự đối
chiếu qua `git diff` — dòng 384 không nằm trong bất kỳ hunk nào của tăng này) — khớp đúng lời Dev báo
trong CHANGELOG, xác nhận độc lập chứ không chỉ tin. **Đạt.**

### 8. `web/index.html` / `web/history.html`

Cả 2 file dùng `x-text` (Alpine.js) để render `job.source_lang`/`f.job?.source_lang` — `x-text` set
`textContent`, tự động escape, không có đường XSS nào (khác `x-html` mới đáng lo). Logic hiển thị
`(x === 'fr' ? 'FR' : 'EN') + '→VI'` coi mọi giá trị khác `'fr'` (kể cả `null`/`'en'`) là `EN→VI` — đúng
deny-by-default (R8-02), khớp comment trong code. `history.html` cập nhật đúng `colspan="9"` (từ 8) cho
dòng "Chưa có job nào" khớp số cột mới. Không có vấn đề.

### 9. Checklist bắt buộc theo brief Reviewer (CLAUDE.md)

- **R5-04**: Không có file `*_runner.py`/`*_provider.py` nào bị sửa trong tăng S7 — `mineru_runner.py`
  chỉ bị ĐỌC (không sửa) để xác nhận default `lang="en"`. → **N/A** cho R5-04 (phạm vi tăng này không
  đổi bất kỳ external contract wrapper nào). Ghi chú: Tech Lead đã verify contract MinerU/pdf2zh/babeldoc
  từ nguồn thật ở §6.26.1 (Architecture.md), Dev không cần verify lại vì không đổi cách gọi 3 tool này.
- **R6-04**: `job_orchestrator.py` là `*_orchestrator.py` gọi tuần tự nhiều service — đã tự trace tay
  từng lời gọi bước N+1 xem biến truyền vào có bắt nguồn từ bước N hay không (mục 6 ở trên), không chỉ
  xác nhận "cả 2 bước được gọi đúng tham số riêng". Kết luận: **đạt**, không phát hiện đứt gãy lineage
  kiểu Bug #5 — `job.source_lang` là 1 biến DUY NHẤT được persist ở Step 3/E1, mọi bước sau chỉ ĐỌC lại
  (không detect song song/độc lập ở nơi khác).
- **R8-01**: FR là biến thể mới đi qua pipeline dùng chung (`_process_chunk()`, `run_epub_job()`) —
  Tech Lead đã audit đủ 14 bước ở §6.26.5, Dev implement khớp bảng đó (mục 6). Không có bước nào bị bỏ
  sót audit. **Đạt** (không cần SKIP thêm gì ngoài bước #13 đã quyết).
- **Protocol 5 R5-03**: Dev tự nêu rõ trong CHANGELOG "CHƯA chạy R6-03 live E2E (PDF FR thật + EPUB FR
  thật) — QA phải chạy trước khi release, hoặc ghi rõ 'release blocked pending live verification' nếu
  chưa chạy được" — đúng tinh thần R5-03/R6-03, không tự nhận ready_for_release. **Đạt** (nghĩa vụ đã
  chuyển đúng cho QA, không bị bỏ qua).

### Kết luận

**APPROVE.** MinerU luôn nhận `lang="en"` — đã tự đọc code + test xác nhận, không phải bug. Lineage
`source_lang` xuyên suốt pipeline (cost_gate → create_job → run_job Step 3 → mọi bước hậu kỳ) đã trace
tay từng điểm, khớp bảng §6.26.4/6.26.5. Regression EN giữ nguyên (test byte-for-byte + golden cost
test vẫn xanh). 81 test liên quan S7 tự chạy xanh, ruff sạch (trừ 1 vi phạm format tiền tồn tại không
liên quan). Không có blocking issue.

**Backlog / non-blocking (PM đưa vào `project_state.json` `backlog[]`, kèm owner theo R5-06 nếu áp
dụng):**

1. Architecture.md §6.26.6 hiện liệt kê `_GLOSSARY_INSTRUCTION`/`_FILE_GLOSSARY_INSTRUCTION` là 2
   trong 5 chuỗi "phải nhận `source_lang`", nhưng Dev không sửa 2 chuỗi này (lý do hợp lý, xem mục 5b)
   — đề nghị Tech Lead cập nhật lại bảng §6.26.6 cho khớp implementation thực tế, tránh gây hiểu nhầm
   cho lần đọc sau. `source: "tech-lead"`.
2. `test_source_lang_survives_resume_after_chunk_failure` verify `lang_in` ổn định qua resume nhưng
   không đọc lại `job.source_lang` sau lần chạy đầu (trước khi resume) để assert tường minh giá trị
   chưa bị đổi ngay tại thời điểm failure — hiện tại verify gián tiếp qua `lang_in` ở lần resume vẫn
   đủ chặt, nhưng thêm 1 dòng `await session.refresh(job); assert job.source_lang == "fr"` ngay sau
   `first_result` sẽ khiến test này tự-tài liệu-hoá rõ hơn ý định. Không gây rủi ro thực tế, mức độ
   thấp — có thể gộp vào lần review kế tiếp.
3. R5-06 backlog A-1..A-4 (§6.26.7, `CHARS_PER_TOKEN_FR` chưa đo bằng `tiktoken` thật, ngưỡng detect
   chiều FR chưa đo trên tài liệu FR thật, MinerU OCR tiếng Pháp có dấu chưa chạy thật, guard
   diacritic EPUB tầng 2 chưa có ca thật FR) — Dev đã nhắc trong CHANGELOG là chưa tự thêm vào
   `project_state.json`, PM/Tech Lead cần xác nhận cả 4 mục đã có entry `backlog[]` với
   `source: "tech-lead"` trước khi coi tăng S7 đủ điều kiện đóng, đúng R5-06.
4. R6-03 live E2E (PDF FR thật + EPUB FR thật qua toàn chuỗi, mở file kiểm tra có chữ Việt thật) CHƯA
   chạy — bắt buộc QA chạy trước khi release theo R5-03, hoặc QA phải ghi rõ "release blocked pending
   live verification" trong `test-report.md` nếu môi trường QA cũng không có pdf2zh/babeldoc/MinerU/API
   key thật.
