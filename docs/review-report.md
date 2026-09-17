

> **Protocol C — lưu trữ**: 35 đợt trước 2026-09-18 đã chuyển nguyên văn sang 2 file archive
> (chuyển theo thời gian, không đè lên nhau): 20 đợt đầu tại
> [`docs/archive/review-report-until-2026-09-10.md`](archive/review-report-until-2026-09-10.md),
> 15 đợt tiếp theo tại
> [`docs/archive/review-report-until-2026-09-18.md`](archive/review-report-until-2026-09-18.md).
> File này chỉ giữ **8 đợt gần nhất**. Đợt mới **APPEND vào cuối file này** (R7-03 — không ghi
> đè). Khi file vượt ngân sách Protocol C (`python3 scripts/validate_state.py` cảnh báo), rotate
> tiếp theo cùng cách: đọc file hiện có trước, chuyển nguyên văn các đợt cũ nhất sang archive mới,
> cập nhật khối `<details>` này, KHÔNG xoá nội dung.
>
> <details><summary>Danh sách 35 đợt đã lưu trữ (2 đợt rotate)</summary>
>
> **Tới 2026-09-10** (`archive/review-report-until-2026-09-10.md`):
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
> **Tới 2026-09-18** (`archive/review-report-until-2026-09-18.md`):
>
> | # | Đợt |
> |---|---|
> | 21 | Review Report — US-22 Dịch EPUB, Bước 2/3: Translation Engine thật + cost-gate — VÒNG 1/3 |
> | 22 | Review Report — US-22 Dịch EPUB, Bước 2/3: Translation Engine thật + cost-gate — VÒNG 2/3 |
> | 23 | Review Report — Fix Bug #EPUB-B2-1 + #EPUB-4 (US-22 Bước 2/3, sau QA vòng 1/5) — VÒNG 1/3 |
> | 24 | Review Report — Fix Bug #EPUB-B2-3 (parse multi-JSON, US-22 Bước 2/3) — VÒNG 1/3 |
> | 25 | Review Report — Fix tổng quát Bug #EPUB-B2-4 (parse JSON multi-separator, US-22 Bước 2/3) — VÒNG 1/3 |
> | 26 | Review Report — Chiến lược mới 3 lớp (§6.20.14) sau khi chạm giới hạn Protocol 3 — US-22 Bước 2/3 — VÒNG 1/3 |
> | 27 | Review Report — US-22 Bước 3/3 (5 việc hoàn thiện AC) — VÒNG 1/3 |
> | 28 | Review Report — Fix UI Alpine template (N đoạn/trang/Tải lên) + đóng US-22 toàn bộ — VÒNG 1/3 |
> | 29 | Review Report — US-15 nhánh EPUB (to_markdown, sau khi US-22 unblock) — VÒNG 1/3 |
> | 30 | Review Report — Bump pyproject.toml version 1.2.9→1.3.1 (fix quên bump ở 2 release trước) — VÒNG 1/3 |
> | 31 | Review Report — Fix Bug #EPUB-3 (job mồ côi khi server restart) — VÒNG 1/3 |
> | 32 | Review Report — Port Protocol A–F + mở rộng 2/3/4 từ AB-RnD (hạ tầng quy trình) — VÒNG 1/3 |
> | 33 | Review Report — Fix backlog BL-01/02/03/05 — VÒNG 1/3 |
> | 34 | Review Report — Port Protocol A–F (fix 2 blocking) — VÒNG 2/3 |
> | 35 | Review Report — BL-04 Implementation (babeldoc drop report) — VÒNG 1/3 |
>
> </details>

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

---

## BL-20 — Fix guard hết hạn ngầm chặn "Các từ mới" cho job EPUB (Reviewer, 2026-09-17)

Phạm vi: `src/core/term_extraction_service.py`, `tests/integration/test_term_extraction_service.py`.
Đọc trước khi review: `docs/Architecture.md` §6.27 (8671-8747), `docs/design-log.md` mục "2026-09-16 —
RCA BL-20" (6881-6987, gồm Final Decision Hiếu 2026-09-17), `docs/CHANGELOG.md` đoạn BL-20
(8420-8481).

### 1. Guard EPUB FR (§6.26.5 #13) — có bị gỡ nhầm cùng lúc không? (yêu cầu quan trọng nhất)

Đọc trực tiếp `src/core/term_extraction_service.py:147-161` — guard
`if (job.source_lang or "en") != "en": ... return 0` **VẪN CÒN NGUYÊN**, đúng vị trí (trong
`extract_and_store_terms()`, không phải riêng ở `jobs.py`), đúng comment tham chiếu §6.26.5 #13 +
R8-02. `git diff HEAD -- src/core/term_extraction_service.py` xác nhận hunk sửa CHỈ nằm ở nhánh
`if job.file_type == FileType.EPUB:` (dòng 75-85, trong `_extract_source_text_for_terms()`) — không
chạm dòng 147-161. Test `test_extract_and_store_terms_skips_for_source_lang_fr` (đã có từ trước, PDF
fixture) tự chạy xanh không cần sửa, xác nhận độc lập việc guard FR không bị ảnh hưởng. **Đạt.**

### 2. Test khẳng-định-bug đã bị xoá thật chưa?

`grep -rn "test_lineage_epub_not_yet_supported_raises_clearly\|US-22 hasn't shipped" tests/ src/` →
0 kết quả. Không còn tồn tại dưới bất kỳ hình thức nào (không đổi tên, không `@pytest.mark.skip`,
không comment-out). **Đạt.**

### 3. 3 test mới — assert cụ thể, không chỉ "đã gọi"

Đọc trực tiếp `tests/integration/test_term_extraction_service.py`:

- `test_lineage_epub_reads_full_text_not_inner_html` (dòng 200-218): dựng EPUB thật bằng `zipfile`
  (không mock `EpubDocument` — đúng R5-03), có `<strong>` trong đoạn văn; assert text trả về **có**
  câu thật `"Laminated dough rests overnight in the fridge."` VÀ **không** chứa `"<strong"`/`"<p"`.
  Đây là assert giá trị cụ thể, phân biệt được đọc `full_text()` (text thuần) với đọc
  `EpubUnit.text` (inner-HTML) — đúng tinh thần R6-02.
- `test_lineage_epub_bad_file_raises_term_extraction_source_error` (220-233): file zip hỏng →
  assert raise đúng `TermExtractionSourceError` (không phải `EpubParseError` lộ ra ngoài).
- `test_extract_and_store_terms_writes_pending_rows_for_completed_epub_job` (265-295): EPUB thật 3
  đoạn lặp "Laminated dough" → gọi `extract_and_store_terms()` (mức tương đương route thật gọi),
  assert `written > 0`, VÀ assert `"laminated dough" in {row.match_key for row in rows}` — đúng như
  Dev báo, đây chính là assert R6-02 mức end-to-end (không chỉ `assert_awaited()`).

Cả 3 test đã tự chạy xanh (mục 6). **Đạt.**

### 4. Correctness `EpubDocument.load()` + xử lý `EpubParseError`

`_extract_source_text_for_terms()` dòng 75-85: `try: return EpubDocument.load(Path(job.file_path)
).full_text() except EpubParseError as exc: raise TermExtractionSourceError(...) from exc`. Bọc
đúng loại exception cụ thể (`EpubParseError`, không phải `except Exception` chụp bừa), giữ
`from exc` cho traceback gốc không mất khi debug log. Route `POST /{job_id}/extract-terms`
(`src/api/routes/jobs.py:815-828`) chỉ bắt `TermExtractionSourceError` → 400 — khớp đúng, không có
exception lạ nào khác từ `EpubDocument.load()` có thể lọt ra ngoài để rơi vào nhánh 500 mặc định của
FastAPI, vì mọi lỗi parse hợp lệ của thư viện đã được chuẩn hoá thành `EpubParseError` ở tầng dưới
(đã đọc `src/services/epub_document.py`, `load()` không raise loại exception nào khác ngoài
`EpubParseError`/`FileNotFoundError` — `FileNotFoundError` cho path không tồn tại KHÔNG được bọc,
nhưng đây là hành vi đã có từ trước BL-20 cho mọi `file_type` khác (`pdf_digital`/`pdf_scan` cũng
không bọc `FileNotFoundError` của `_extract_full_text`), không phải regression riêng của fix này —
ghi non-blocking bên dưới thay vì blocking, vì phạm vi brief BL-20 là guard EPUB, không phải audit
lại toàn bộ exception handling của 4 nhánh `file_type`). **Đạt** cho phạm vi BL-20.

### 5. Backfill — script gọi thẳng `extract_and_store_terms()` có tương đương đường API thật không?

Đọc `src/api/routes/jobs.py:815-828` (`extract_terms_manual`): route CHỈ làm 2 việc ngoài gọi hàm —
(a) `settings = await get_effective_settings(session)` (KHÔNG phải `get_settings()`/`Settings()`
mặc định — `get_effective_settings` layer thêm override lưu trong bảng `settings` DB lên trên
`.env`, xem `src/core/config.py:385-405`), (b) bọc `TermExtractionSourceError` → HTTP 400. Không có
side-effect nào khác ở tầng route (không ghi audit log riêng, không đổi `job.status`, response chỉ
là `{job_id, written}`).

Vấn đề: `term_extraction_enabled` **NẰM TRONG** `SETTINGS_DB_OVERRIDABLE_FIELDS`
(`src/core/config.py:362`) — nghĩa là nếu user từng tắt tính năng này qua UI settings (ghi vào bảng
`settings` DB), `get_effective_settings(session)` sẽ trả `False`, còn `Settings()`/`get_settings()`
mặc định (chỉ đọc `.env`) sẽ KHÔNG thấy override đó, vẫn trả `True`. CHANGELOG mô tả backfill "chạy
bằng script gọi thẳng `extract_and_store_terms(job_id, session, settings)`" nhưng **không nêu rõ
`settings` được tạo bằng `get_effective_settings(session)` hay `Settings()` mặc định**, và script đó
**không được lưu lại trong repo** (không tìm thấy file nào khớp `*backfill*`/`*bl20*` ngoài
`docs/`) — không thể tự đọc source để xác nhận độc lập, chỉ có thể xác nhận KẾT QUẢ: đã tự
`sqlite3 data/bb_translation.db "select job_id, count(*) from suggested_terms where job_id in
(...) group by job_id"` → đúng khớp CHANGELOG (`88e897af…` = 2765, `217097fd…` = 2650) — nghĩa là
trên thực tế `term_extraction_enabled` đã là `True` dù script dùng nguồn settings nào, nên kết quả
lần này không sai. Nhưng đây vẫn là một **khoảng hở audit thật**: nếu DB có override khác `.env`
sau này (ví dụ `default_provider`, dù không ảnh hưởng `extract_and_store_terms` hiện tại), một
script backfill viết tay không tái sử dụng đúng `get_effective_settings()` có thể âm thầm lệch khỏi
hành vi API thật. Ghi non-blocking bên dưới — không block APPROVE vì (a) phạm vi hiện tại
(`term_extraction_enabled`) đã verify bằng kết quả thật khớp, (b) đây là kỷ luật cho backfill script
tương lai, không phải lỗi trong code đã review.

### 6. Tự chạy lại test — không chỉ tin số Dev báo

```
.venv/bin/python -m pytest tests/integration/test_term_extraction_service.py -q
  → 16 passed, 272 warnings in 1.47s

.venv/bin/python -m pytest -q   (toàn repo)
  → 883 passed, 1199 warnings in 107.69s
```

Khớp đúng số Dev báo trong CHANGELOG (16 passed / 883 passed). `.venv/bin/ruff check` +
`.venv/bin/ruff format --check` trên 2 file đã sửa: sạch, không vi phạm.

Backfill DB (tự query độc lập, không tin CHANGELOG):
`sqlite3 data/bb_translation.db` → `suggested_terms` có đúng 2765 dòng cho
`88e897af-e19f-470c-9248-922fbc79596f` và 2650 dòng cho `217097fd-6d72-4560-949d-439a4dbc60ec`, cả
2 job đều `file_type=epub, status=completed` — khớp chính xác CHANGELOG.

### 7. Checklist bắt buộc theo brief Reviewer (CLAUDE.md)

- **R5-04**: `term_extraction_service.py` không phải `*_runner.py`/`*_provider.py` (gọi tool bên thứ
  3 qua subprocess/HTTP) — nó gọi `EpubDocument.load()` là thư viện nội bộ Python thuần (không phải
  external network/subprocess service, đúng "Phạm vi áp dụng" Protocol 5 loại trừ tường minh case
  này). → **N/A**.
- **R6-04**: đây không phải `*_orchestrator.py` gọi tuần tự nhiều service — `extract_and_store_terms()`
  đọc source text rồi trích n-gram trong cùng 1 hàm, không có bước N+1 nhận input từ return value của
  1 external call trước đó theo nghĩa Protocol 6. Đã tự trace tay việc `source_text` (return của
  `_extract_source_text_for_terms`) được truyền thẳng vào `extract_terms(source_text, ...)` ở dòng
  163-165 — đúng lineage, không đứt gãy kiểu Bug #5. → **Đạt** (không N/A hoàn toàn vì vẫn có 1 mối nối
  nội bộ đáng trace, đã trace xong).
- **R8-01**: EPUB không phải "biến thể mới đi qua pipeline dùng chung" theo nghĩa Protocol 8 (engine
  dịch/provider mới) — đây là nhánh `file_type` đã tồn tại trong bảng lineage từ §6.18.5, chỉ bị
  guard tạm chặn sai thời điểm. Tech Lead đã tự làm đúng dạng audit R8-01 ở §6.27.3 (liệt kê đủ 6
  bước có sẵn trong `extract_and_store_terms()`, kết luận không bước nào cần SKIP cho EPUB) — đã đọc
  và xác nhận bảng đó đầy đủ, khớp code thật. → **Đạt**.
- **Protocol 5 R5-03**: không có mock nào cho `EpubDocument` trong 2 test EPUB mới — cả 2 dùng
  `_build_epub()` dựng zip/OPF/spine thật bằng `zipfile` (cùng pattern
  `test_epub_job_source_lang.py::_build_epub`, không viết tay theo giả định) → `EpubDocument.load()`
  parse dữ liệu thật. Backfill (mục 5) dùng `data/bb_translation.db` + file EPUB thật trên đĩa, không
  phải mock. → **Đạt**, không có mock nào cần golden file backing riêng cho tăng này.

### Kết luận

**APPROVE.** Guard EPUB FR không bị đụng (mục 1, verify bằng đọc code + `git diff` trực tiếp). Test
khẳng-định-bug đã xoá sạch (mục 2). 3 test mới có assert giá trị cụ thể đúng R6-02 (mục 3).
`EpubParseError` được bọc đúng thành `TermExtractionSourceError`, khớp hợp đồng 400 (mục 4). Backfill
2 sách thật verify độc lập qua query DB, số dòng khớp chính xác CHANGELOG (mục 5, 6). Toàn bộ 883 test
tự chạy lại xanh, ruff sạch. Không có blocking issue.

**Backlog / non-blocking (PM đưa vào `project_state.json` `backlog[]` nếu áp dụng):**

1. **Script backfill không được lưu lại trong repo** (`scripts/` hoặc tương đương) — không thể audit
   độc lập việc nó dùng `get_effective_settings(session)` hay `Settings()` mặc định khi gọi
   `extract_and_store_terms()`. Lần này không gây sai lệch (verify bằng kết quả DB thật, mục 5), nhưng
   là thói quen nên sửa: mọi script backfill chạm production DB nên được lưu vào `scripts/` (dù chỉ
   chạy 1 lần, xoá sau) để có thể review/audit như code thường, tránh lặp lại kiểu "không ai đọc được
   nó đã làm gì" — nhất là khi hàm mục tiêu (`extract_and_store_terms`) phụ thuộc `Settings` có thể có
   override DB. `source: "dev"`.
2. `_extract_source_text_for_terms()` không bọc `FileNotFoundError` thành `TermExtractionSourceError`
   cho bất kỳ nhánh `file_type` nào (kể cả nhánh EPUB mới sửa) — nếu `job.file_path` bị xoá khỏi đĩa
   sau khi job `completed` (ví dụ user dọn dẹp thủ công), `POST /extract-terms` sẽ trả 500 thay vì 400
   có thông báo. Đây là hành vi đã có từ trước BL-20 cho mọi nhánh, không phải regression của tăng
   này, nhưng đáng gộp vào cùng 1 lần dọn dẹp lineage error-handling nếu Tech Lead thấy đáng làm.
   `source: "tech-lead"`.
3. Server uvicorn dev chưa được restart để xác nhận thêm qua đường HTTP thật
   (`POST /api/jobs/{id}/extract-terms`) — Dev đã tự flag đúng trong CHANGELOG, không tự nhận đã verify
   trọn vẹn qua route. Không block APPROVE (đã verify tương đương qua gọi hàm trực tiếp + kết quả DB),
   nhưng PM/Hiếu nên quyết định thời điểm restart an toàn để có 1 lần xác nhận qua route thật, đúng
   tinh thần R5-03 "tối thiểu 1 lần gọi thật".

## Fix — rerun `extract_and_store_terms()` UNIQUE constraint (2026-09-17), review vòng 2 dev-qa cho BL-20

Reviewer review fix của Dev cho bug QA phát hiện khi verify BL-20 (`docs/test-report.md` mục
"BL-20 — QA gate cuối (2026-09-17)"): `POST /api/jobs/{id}/extract-terms` gọi lần 2 (rerun) trên
job đã có `suggested_terms` toàn `pending` → HTTP 500 `IntegrityError` UNIQUE
`(job_id, term_en)` do SQLAlchemy emit INSERT trước DELETE trong cùng 1 flush. Đọc trước
`docs/CHANGELOG.md` mục "Fix — rerun `extract_and_store_terms()` UNIQUE constraint (2026-09-17)"
(đoạn Dev vừa append cuối file, trước section này).

### 1. Vị trí `session.flush()` — đúng chỗ, có tác dụng thực

Đọc `src/core/term_extraction_service.py:174-207` (`extract_and_store_terms()`): vòng lặp
`for row in pending_rows: await session.delete(row)` (dòng 181-182) chạy xong, `await
session.flush()` (dòng 189) đặt ngay sau, TRƯỚC vòng lặp `for candidate in candidates: ...
session.add(SuggestedTerm(...))` (dòng 192-207). Không có early-return, `continue`, hay nhánh
điều kiện nào giữa 2 vòng lặp có thể khiến `flush()` bị bỏ qua trong đường đi bình thường (đường
đi sớm-return duy nhất, kill switch `term_extraction_enabled=False`, đã return ở dòng 145, TRƯỚC
cả vòng lặp delete — không đụng đoạn này). `flush()` ép SQLAlchemy emit SQL DELETE thật xuống
SQLite ngay tại điểm gọi thay vì gộp chung 1 lượt unit-of-work lúc `commit()` cuối hàm (dòng 209)
— đúng cơ chế fix mô tả trong CHANGELOG, verify bằng đọc code trực tiếp, không chỉ tin comment.
Comment dòng 184-188 giải thích đúng root cause, khớp với hành vi SQLAlchemy thật (unit-of-work
mặc định sắp INSERT trước DELETE trong cùng 1 flush — đây là hành vi ORM core đã biết, không phải
claim cần verify nguồn ngoài).

### 2. Test mới — KHÔNG thực sự tái hiện được bug (blocking, phát hiện bằng verify độc lập)

Đọc `tests/integration/test_term_extraction_service.py:359-433`, cả 2 test khác nhau đúng ở điểm
Dev mô tả (test cũ dismiss 1 row trước khi rerun nên `decided_terms` chặn candidate trùng tên
không cho `session.add()`; test mới để mọi row `pending`, không chặn gì) — về mặt LOGIC ứng dụng,
mô tả trong CHANGELOG đúng.

Nhưng tự verify độc lập bằng cách tạm bỏ dòng `await session.flush()` (copy file, sửa, chạy lại,
restore ngay sau) và chạy lại đúng 2 test rerun này:

```
pytest tests/integration/test_term_extraction_service.py -q -k rerun
```

→ **2 passed** — kể cả KHÔNG có `flush()`, test mới `test_extract_and_store_terms_rerun_with_all_
rows_still_pending_does_not_raise` vẫn PASS. Test này không hề tái hiện được `IntegrityError` mà cả
CHANGELOG lẫn tên test đều khẳng định nó bảo vệ.

**Root cause của việc này (đã trace tiếp, không dừng ở "lạ")**: `UNIQUE (job_id, term_en)` —
đúng constraint gây bug gốc — được tạo bằng raw SQL trong `init_db()`
(`src/models/database.py:184-188`, `CREATE UNIQUE INDEX IF NOT EXISTS idx_suggested_terms_job_term
ON suggested_terms(job_id, term_en)`), comment dòng 179-183 giải thích rõ: `SuggestedTerm` là bảng
mới nên phần cột được tạo bởi `SQLModel.metadata.create_all()`, nhưng 2 index tổng hợp (kể cả
UNIQUE này) phải tạo riêng bằng raw SQL "vì SQLModel không có declarative composite-index/unique-
constraint pattern nào khác trong repo để theo". Fixture `session` của file test
(`tests/integration/test_term_extraction_service.py:40-50`) chỉ gọi
`await conn.run_sync(SQLModel.metadata.create_all)` — **không bao giờ gọi `init_db()`** hay tạo
riêng index này. Tự chạy 1 script độc lập xác nhận: DB in-memory dựng đúng kiểu fixture có
`SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%suggested_terms%'` → **rỗng**,
0 index nào trên bảng `suggested_terms` trong toàn bộ test suite của file này. Nghĩa là UNIQUE
constraint mà production DB (qua `init_db()` lúc app khởi động) chắc chắn có, **không hề tồn tại
trong bất kỳ test nào của file này** — kể cả 15 test cũ đã pass từ trước. Đây không phải regression
riêng của fix này, nhưng chính nó là lý do bug gốc (BL-20 QA phát hiện) không hề bị bắt bởi 883 test
cũ, và giờ là lý do test "chứng minh fix" mới cũng vô tác dụng ở tầng DB constraint.

### 3. Side-effect của `flush()` giữa transaction

`flush()` chỉ đẩy SQL xuống connection hiện tại trong cùng transaction đang mở, KHÔNG commit —
transaction SQLite vẫn chưa kết thúc, chưa release lock, chưa ghi WAL checkpoint bền vững. Nếu có
exception giữa `flush()` (dòng 189) và `commit()` (dòng 209) — ví dụ lỗi validate dữ liệu candidate
bất ngờ trong vòng lặp add — session vẫn ở trạng thái "dirty", chưa commit. Truy vết vòng đời
session: `src/models/database.py:49-52` (`get_session()`) dùng `async with session_factory() as
session: yield session` — `AsyncSession.__aexit__` khi có exception sẽ gọi `close()`, và
`close()` của SQLAlchemy Session/AsyncSession discard connection kèm rollback bất kỳ transaction
chưa commit nào (hành vi core của SQLAlchemy, không phải hành vi cần verify riêng theo Protocol 5
vì đây là thư viện Python thuần import trực tiếp — đúng phạm vi loại trừ). Route caller
(`src/api/routes/jobs.py:815-830`, `extract_terms_manual`) chỉ bắt riêng
`TermExtractionSourceError` để trả 400; exception khác (kể cả lỗi giữa flush/commit) đi lên thành
500 — nhưng vì `close()` đã rollback DELETE đã flush, DB không bị để lại ở trạng thái nửa vời
(dòng đã xoá mất, dòng mới chưa thêm). Không có vấn đề rollback nào bị bỏ sót.

### 4. Verify độc lập qua DB thật

Không tin lời Dev, tự chạy:

```
select job_id, term_en, count(*) from suggested_terms group by job_id, term_en having count(*) > 1
```

trên `data/bb_translation.db` (bảng có `suggested_terms`, `data/outputs/bb_translation.db` không
có bảng này, bỏ qua) → **rỗng**, không có duplicate. Lưu ý: brief PM mô tả Dev "đã tự verify qua
HTTP thật (gọi endpoint 2 lần liên tiếp, cả 2 đều `200 {"written":31}`)" — đọc lại
`docs/CHANGELOG.md` mục fix này (đoạn "Chưa làm / cần theo dõi") thì Dev **KHÔNG** claim đã verify
qua HTTP thật, mà ghi rõ: "Chưa tự verify lại qua HTTP thật (server có thể cần restart để chạy code
fix mới) — để PM quyết định thời điểm restart an toàn". Số `written: 31` tìm thấy trong repo
(`docs/test-report.md:3157,3206`) là kết quả QA verify lúc **phát hiện bug** (trước fix), không
phải Dev verify **sau fix**. → **Brief PM không khớp với báo cáo thật của Dev** — không phải lỗi
của Dev, nhưng cần PM lưu ý: chưa có xác nhận HTTP thật nào cho fix này, chỉ có xác nhận qua gọi
hàm Python trực tiếp (test integration) + query DB.

### 5. Test suite + lint

- `pytest tests/integration/test_term_extraction_service.py -q` → 17 passed.
- `pytest -q` (toàn repo) → **884 passed**, khớp đúng Dev báo trong CHANGELOG.
- `ruff check src/core/term_extraction_service.py tests/integration/test_term_extraction_service.py`
  → All checks passed.
- `ruff format --check` cùng 2 file → đã format sẵn (2 files already formatted).

### 6. Checklist bắt buộc theo brief Reviewer (CLAUDE.md)

- **R5-04**: `term_extraction_service.py` không phải `*_runner.py`/`*_provider.py` — không gọi
  external tool qua subprocess/HTTP trong đoạn fix này (chỉ gọi `session.flush()`/`session.delete()`
  của SQLAlchemy, thư viện nội bộ). → **N/A**.
- **R6-04**: fix này không phải `*_orchestrator.py` gọi tuần tự service — chỉ là thứ tự
  flush/delete/add trong 1 transaction DB nội bộ, không có lineage giữa external call. → **N/A**.
- **R8-01**: không có biến thể/engine mới nào đi qua pipeline trong fix này — bug tổng quát cho mọi
  `file_type` (PDF lẫn EPUB đều bị, theo đúng mô tả CHANGENLOG root cause), không phải case
  biến-thể-mới-dùng-chung-pipeline-cũ theo nghĩa Protocol 8. → **N/A**.
- **Protocol 5 R5-03**: test mới không mock gì (dùng `_make_pdf`, PDF thật ghi ra `tmp_path`, DB
  session thật qua fixture `session`) — không có mock cần golden file backing. → **Đạt**.

### Kết luận

**REJECT.** `session.flush()` đặt đúng vị trí, khớp cơ chế SQLAlchemy mô tả trong CHANGELOG, và
nhiều khả năng đúng là fix hợp lý cho bug gốc (mục 1, mục 3 không có vấn đề side-effect nào). Tự
verify DB production thật cũng không thấy duplicate (mục 4). Nhưng **blocking issue ở mục 2**: test
mới `test_extract_and_store_terms_rerun_with_all_rows_still_pending_does_not_raise` — chính test
được CHANGELOG dẫn ra làm bằng chứng fix đúng — **không tái hiện được bug**, xác nhận bằng cách tự
gỡ tạm `flush()` và chạy lại: test vẫn PASS. Nguyên nhân: fixture `session` của file test không gọi
`init_db()`, nên `UNIQUE (job_id, term_en)` (tạo bằng raw SQL riêng trong `init_db()`, không phải
`SQLModel.metadata.create_all()`) không tồn tại trong DB test — test không có cách nào gặp
`IntegrityError` dù code có bug hay không. Đây đúng dạng lỗi Protocol 6 R6-02 cảnh báo ("mock/test tự
nhất quán với chính nó, không nhất quán với ràng buộc DB thật") ở mức nghiêm trọng hơn: không phải
mock sai giả định, mà là **thiếu hẳn 1 phần schema thật** trong toàn bộ test suite của file này —
tất cả 17 test cũ + mới trong file đều chạy trên DB thiếu UNIQUE constraint mà production luôn có.
Vì lý do gate cuối của bug này (BL-20 QA phát hiện) chính là do gọi HTTP thật trên DB thật — nơi có
constraint — nên "test xanh" trong CHANGELOG không chứng minh được gì về fix, chỉ chứng minh code
không tự crash khi không có constraint nào cản.

Fix bản thân `flush()` gần như chắc chắn đúng hướng (chuẩn SQLAlchemy, đúng root cause đọc từ code),
nhưng theo đúng tinh thần Protocol 5/6 của repo ("test pass chỉ chứng minh code khớp giả định, không
chứng minh giả định đúng thực tế") — reject để Dev fix lại TEST trước khi coi fix là "xong", không
phải vì nghi ngờ đúng-sai của chính đoạn code fix.

**Việc Dev cần làm (không tính vòng lặp riêng theo Protocol 5/6 — xem "Quyền reject không tính vòng
lặp" trong brief Reviewer, vì đây là reject do vi phạm nguyên tắc test/verify, không phải lỗi logic
thường)**:

1. Sửa fixture `session` (`tests/integration/test_term_extraction_service.py:40-50`) để DB test có
   đúng `UNIQUE (job_id, term_en)` như production — cách đơn giản nhất: gọi thẳng
   `src.models.database.init_db()`-style raw SQL (hoặc factor phần tạo 2 index đó ra 1 hàm dùng
   chung giữa `init_db()` và fixture, tránh lệch nhau lần sau) thay vì chỉ
   `SQLModel.metadata.create_all()`.
2. Xác nhận lại: gỡ tạm `flush()`, chạy lại `test_extract_and_store_terms_rerun_with_all_rows_
   still_pending_does_not_raise` — PHẢI fail (`IntegrityError`) lần này; khôi phục `flush()`, chạy
   lại — phải pass. Ghi rõ 2 kết quả này vào CHANGELOG lần fix tiếp theo, không chỉ ghi "N passed".
3. Chạy lại toàn bộ 17 test trong file + toàn repo — với UNIQUE constraint giờ có thật trong test
   DB, có khả năng lộ ra thêm chỗ khác trong 15 test cũ từng "pass" nhờ thiếu constraint này; nếu
   có test nào fail mới, xử lý luôn trong cùng lần sửa.
4. Vẫn nên có 1 lần xác nhận qua HTTP thật (`POST /api/jobs/{id}/extract-terms` gọi 2 lần liên tiếp
   trên job completed) trước khi đóng BL-20 hẳn — xem mục 4, brief PM mô tả Dev đã làm việc này
   nhưng CHANGELOG cho thấy chưa, cần PM đính chính khi báo lại Hiếu.

**Non-blocking (giữ nguyên, không đổi do reject ở test, không phải ở đoạn logic này)**:

1. Đây là vòng dev-qa thứ 2 cho BL-20 (bug do QA phát hiện ở gate cuối, Dev fix, Reviewer reject vì
   test không tái hiện được bug) — trong giới hạn Protocol 3 (max 5), và theo brief Reviewer "Quyền
   reject không tính vòng lặp" cũng áp dụng được ở đây (reject do vi phạm nguyên tắc verify của
   Protocol 6 R6-02, tương tự tinh thần Protocol 5) — PM cân nhắc không tính vòng này vào giới hạn 3
   của Dev↔Reviewer.

## Review lần 2 — Fix theo Reviewer REJECT, test rerun BL-20 (2026-09-17)

Phạm vi: `src/models/database.py` (hàm `_create_composite_indexes()` mới, `init_db()` refactor gọi
hàm này), `tests/integration/test_term_extraction_service.py` (fixture `session` dòng ~40-53 gọi
thêm `_create_composite_indexes(conn)`), `src/core/term_extraction_service.py` (giữ nguyên
`flush()` từ lần trước). Đọc lại mục REJECT ngay phía trên (lần review trước) và mục CHANGELOG
"Fix theo Reviewer REJECT — test rerun BL-20..." trước khi bắt đầu, đúng brief PM.

### 1. Tự verify độc lập fail-then-pass (không tin lời Dev)

Copy `src/core/term_extraction_service.py` ra backup, tự sửa để gỡ đúng đoạn `await session.flush()`
(dòng 189 cũ) trước vòng lặp `for candidate in candidates:`, chạy:

```
pytest tests/integration/test_term_extraction_service.py -q -k rerun
```

→ **1 failed, 1 passed** — `test_extract_and_store_terms_rerun_with_all_rows_still_pending_does_not_raise`
FAIL đúng với:

```
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed:
suggested_terms.job_id, suggested_terms.term_en
```

Khôi phục lại file bằng backup, `diff` xác nhận **giống hệt bản gốc** (không sai sót khi restore),
chạy lại cùng lệnh → **2 passed, 15 deselected**. Khớp chính xác với 2 khối log Dev dán trong
CHANGELOG (cả message lỗi lẫn số lượng test). **Xác nhận: test mới giờ tái hiện đúng bug thật —
điểm blocking của lần review trước đã được giải quyết.**

### 2. `_create_composite_indexes()` — đối chiếu với `init_db()` production

Đọc `git diff src/models/database.py`: đây là phép chuyển nguyên văn (copy-paste), không đổi 1 ký
tự nào trong 3 câu lệnh raw SQL (`idx_glossary_entries_term_nocase`, `idx_suggested_terms_job_term`
UNIQUE trên đúng `(job_id, term_en)`, `idx_suggested_terms_status_rank`) — chỉ khác vị trí đặt code
(tách thành hàm riêng, gọi ở cuối `init_db()` thay vì inline). Thứ tự gọi trong `init_db()` không
đổi tương đối so với các bước khác (`create_all` → `_migrate_concurrency_state_engine_key` →
`_migrate_chunks_unit_columns` → `_add_missing_columns` → `PRAGMA journal_mode=WAL` →
`_create_composite_indexes`, đúng thứ tự cũ, chỉ 5 dòng cuối gộp thành 1 lời gọi hàm). Không có
thay đổi hành vi production — xác nhận bằng đọc diff trực tiếp, không chỉ tin comment Dev viết.

Fixture `session` (test file, dòng ~40-53) gọi đúng `_create_composite_indexes(conn)` sau
`create_all()` — cùng 1 hàm, cùng 1 nguồn sự thật với `init_db()`, không có khả năng lệch tên
cột/bảng giữa test và production nữa (đúng yêu cầu #1 của lần reject trước).

### 3. Ảnh hưởng tới test khác trong repo

`pytest -q` toàn repo → **884 passed** (không giảm/tăng số test so với báo cáo của Dev, và khớp con
số 884 mà lần review trước đã ghi nhận trước khi có fix này — nghĩa là việc thêm UNIQUE constraint
thật vào DB test của riêng file `test_term_extraction_service.py` không làm lộ ra lỗi tiềm ẩn nào ở
15 test cũ trong cùng file, đúng như Dev báo ở CHANGELOG mục "Việc Dev cần làm #3" — đã kiểm tra
thật, không suy đoán). Các file test khác không đụng `_create_composite_indexes` (không import,
không dùng fixture `session` của file này) nên không có đường ảnh hưởng nào khác cần xét thêm.

### 4. Verify độc lập qua DB thật

```
sqlite3 data/bb_translation.db "select job_id, term_en, count(*) from suggested_terms group by job_id, term_en having count(*) > 1;"
```

→ **rỗng**, không có duplicate `(job_id, term_en)` nào trong DB production hiện tại.

### 5. Đoạn CHANGELOG về verify HTTP thật — đối chiếu nhất quán

Lần trước Reviewer phát hiện brief PM nói "Dev đã verify HTTP" trong khi CHANGENLOG ghi đúng sự
thật là "chưa verify" — không phải Dev sai, mà brief PM lệch với báo cáo thật của Dev. Lần này đọc
kỹ mục "Verify qua HTTP thật — ĐÃ LÀM lần này" trong CHANGELOG: liệt kê tuần tự 5 bước cụ thể (check
không có job đang chạy → kill/restart uvicorn để nạp code fix mới → gọi `POST .../extract-terms` 2
lần liên tiếp trên cùng 1 job đã có sẵn 31 `suggested_terms` pending, không dismiss trước → query DB
xác nhận không tăng số dòng + không duplicate → đọc log server không có exception). Không có câu nào
mơ hồ kiểu "chắc đã ổn" — mọi khẳng định đều kèm bằng chứng cụ thể (status code, body JSON, số dòng
DB, tên file log). Đây đúng là lần đầu trong chuỗi fix BL-20 có xác nhận HTTP thật SAU KHI fix áp
dụng — nhất quán với chính CHANGELOG tự nhận ("các lần trước chỉ có xác nhận qua integration
test/query DB tĩnh"). **Không phát hiện mâu thuẫn nào giữa các đoạn CHANGENLOG lần này.**

Lưu ý cho PM (không phải lỗi Dev, chỉ ghi lại theo đúng CHANGELOG mục "Chưa làm / cần theo dõi"):
Dev tự restart server uvicorn đang chạy để verify — đây là thay đổi chạm môi trường thật
(Protocol E, đối tượng có thể tính là "code fix mới đã áp dụng lên môi trường chạy thật"). Dev tự
ghi rõ mình không có quyền ghi `project_state.json`/`infra_pending[]` theo phân công tool hiện tại
(Protocol F) và đã bàn giao đúng cho PM — cần PM xác nhận có cần thêm entry `infra_pending[]` hay
không trước khi coi bước này là đóng.

### 6. Test suite + lint (tự chạy lại, không tin số Dev báo)

- `pytest tests/integration/test_term_extraction_service.py -q -k rerun` → 2 passed (mục 1).
- `pytest -q` toàn repo → 884 passed, khớp đúng Dev báo trong CHANGELOG.
- `ruff check src/models/database.py tests/integration/test_term_extraction_service.py
  src/core/term_extraction_service.py` → All checks passed!
- `ruff format --check` cùng 3 file → 3 files already formatted.

### 7. Checklist bắt buộc theo brief Reviewer (CLAUDE.md)

- **R5-04**: không có `*_runner.py`/`*_provider.py` nào trong phạm vi fix này — chỉ
  `src/models/database.py` (raw SQL nội bộ SQLite qua SQLAlchemy, thư viện Python thuần import trực
  tiếp) và test fixture. → **N/A**.
- **R6-04**: không có `*_orchestrator.py` nào gọi tuần tự nhiều external service trong phạm vi fix
  này. → **N/A**.
- **R8-01**: không có biến thể/engine mới nào đi qua pipeline trong fix này. → **N/A**.
- **Protocol 5 R5-03**: test không mock gì liên quan tới fix (PDF thật, DB in-memory thật qua
  fixture `session`, giờ có đúng schema production nhờ dùng chung `_create_composite_indexes`). →
  **Đạt**.

### Kết luận

**APPROVE.** Điểm blocking duy nhất của lần review trước (test không tái hiện được bug do fixture
thiếu UNIQUE constraint) đã được xử lý đúng cách: factor phần tạo index/constraint ra hàm dùng
chung `_create_composite_indexes()`, cả `init_db()` production lẫn fixture test giờ đi qua đúng 1
nguồn sự thật — không còn khả năng lệch nhau giữa "constraint test có" và "constraint production
có" như đã gây ra lỗ hổng lần trước. Tự verify độc lập (không tin lời Dev) xác nhận đúng
fail-then-pass: gỡ `flush()` → FAIL với `IntegrityError` y hệt bug gốc; khôi phục `flush()` → PASS.
`git diff` xác nhận refactor `database.py` là copy nguyên văn, không đổi hành vi `init_db()`
production. 884 test toàn repo pass, DB production thật không có duplicate, `ruff` sạch. Đoạn
CHANGELOG về verify HTTP thật lần này rõ ràng, có bằng chứng cụ thể từng bước, không mơ hồ như lần
trước.

Duy nhất 1 điểm PM cần xử lý ngoài phạm vi Reviewer (không phải điều kiện approve/reject): xác nhận
Protocol E có áp dụng cho việc Dev tự restart server production để verify hay không, và thêm
`infra_pending[]` tương ứng nếu cần.

---

## S8 — Tự động loại bỏ trang claim bản quyền trước khi dịch (PDF + EPUB), Reviewer, 2026-09-17

Phạm vi: `src/core/copyright_detector.py` (mới), `src/core/job_orchestrator.py`,
`src/services/epub_document.py`, `src/services/pdf2zh_runner.py`, `src/services/babeldoc_runner.py`,
`src/core/config.py`, `src/models/job.py`, `src/models/database.py`, `src/api/routes/jobs.py`,
`tests/test_copyright_detector.py`, `tests/integration/test_job_orchestrator_copyright_removal.py`,
`tests/integration/test_epub_orchestrator_copyright_removal.py`, 4 test mới trong
`tests/test_epub_document.py`. Đối chiếu với `docs/Architecture.md` §6.28 (toàn bộ), `docs/design-log.md`
mục "S8 — Loại bỏ trang claim bản quyền (thiết kế, Tech Lead, 2026-09-17)", và
`docs/CHANGELOG.md` mục "S8 — Tự động loại bỏ trang claim bản quyền trước khi dịch (PDF + EPUB), Dev,
2026-09-17".

### 1. Chống lặp lại Bug #9 (bước cũ `create_bilingual_pdf`) — điểm quan trọng nhất

Trace tay `job_orchestrator.py`:

- `_apply_copyright_removal()` (dòng 742-829) trả về `(translation_source_path, bilingual_source_path)`.
  `bilingual_source_path` mặc định = `file_path` gốc (dòng 757), chỉ đổi thành
  `original_pruned_path` (dòng 825-829) khi thực sự cắt trang — và `original_pruned.pdf` được cắt
  từ **chính `file_path` gốc** (dòng 827: `_select_pdf_pages(file_path, keep_indices,
  original_pruned_path)`), dùng **cùng `keep_indices`** với `source_pruned.pdf` (dòng 826) — đúng
  §6.28.4 luật 2.
- Dòng 937-939: `translation_source_path, bilingual_source_path = await
  self._apply_copyright_removal(job, file_path, translation_source_path, db_session)` — gán lại
  đúng 2 biến, không tạo biến song song thứ ba (đúng luật 1).
- Dòng 1292: `await create_bilingual_pdf(merged_path, bilingual_source_path, bilingual_path)` —
  **xác nhận dùng `bilingual_source_path`, KHÔNG phải `job.file_path`/`file_path`**. Đây chính xác
  là bước cũ mà `docs/design-log.md` mục 3 gọi là "bước duy nhất hỏng thật sự" nếu không sửa.
- Test `test_create_bilingual_pdf_uses_original_pruned_not_file_path` (tự chạy lại, PASS) không chỉ
  assert đã gọi mà mở cả 3 file bằng PyMuPDF, so `get_text()` từng cặp trang — chứng minh
  `bi_doc[2*i]`/`bi_doc[2*i+1]` khớp đúng `vi_doc[i]`/`en_doc[i]`, không lệch cặp.

**Kết luận: đạt yêu cầu #1 của brief, không lặp lại Bug #9.**

### 2. Đối xứng 2 engine (R8-03)

- `Pdf2zhRunner.page_numbers_relative_to_input: ClassVar[bool] = True`
  (`src/services/pdf2zh_runner.py:103`), `BabeldocRunner.page_numbers_relative_to_input: ClassVar[bool]
  = True` (`src/services/babeldoc_runner.py:442`) — cả hai khai báo, đúng nguồn đã trích trong
  Architecture.md §6.28.1 (pdf2zh `pdf2zh.py:208-217`, babeldoc `translation_config.py:394-422`).
- `job_orchestrator.py` dòng 722-740: property `_page_numbers_relative_to_input` hỏi
  `self._translator_runner.page_numbers_relative_to_input` qua `isinstance` guard (cùng khuôn
  `_needs_font_shrink`/`_reports_own_paragraph_drops`) — pipeline hỏi capability, không rẽ nhánh
  cứng theo tên engine (đúng R8-03).
- Test `test_copyright_page_pruned_before_translate_pages_both_engines` (tự chạy lại, PASS) chạy
  parametrize `["pdf2zh", "babeldoc"]`, cả hai assert `call.kwargs["input_path"] == pruned_path` —
  đúng cùng input, cùng cơ chế.

**Đạt.**

### 3. Resume — guard không quét lại

`_apply_copyright_removal()` dòng 768-774 và `_apply_epub_copyright_removal()` dòng 842-848: cả hai
đều query `Chunk` đã tồn tại trước, nếu có Chunk row NHƯNG `copyright_removed_json` còn `NULL` (job
cũ trước S8 đang resume) → return ngay, không cắt. Nếu `copyright_removed_json` đã có giá trị (dòng
776-777 PDF, dòng 850-851 EPUB) → đọc lại `removed` từ JSON đã lưu, **không gọi lại `scan_units()`**.
Test `test_resume_does_not_rescan_when_copyright_removed_json_already_set` patch thẳng
`src.core.job_orchestrator.scan_units` và `mock_scan.assert_not_called()` — tự chạy lại, PASS.

**Đạt, đúng §6.28.3 "ghi đúng MỘT LẦN rồi giữ nguyên qua mọi lần resume/retry".**

### 4. EPUB structural fix của Dev (rule (f) — container đang là EpubUnit đang dịch)

Đọc `_apply_structural_drops()` (`epub_document.py:1094-1311`), đoạn xử lý rule (f)/(g) dòng
1208-1242: khi tìm container bao quanh `<a>`, nếu `name` (doc chứa container đó) nằm trong
`unit_producing_hrefs` → **luôn unwrap** (dòng 1238-1242, giữ nguyên container, chỉ gỡ `<a>`), bất
kể container có link/nested-list khác hay không; chỉ khi doc đó KHÔNG đóng góp unit (ví dụ
`nav.xhtml` thuần EPUB3) mới xét xoá hẳn container theo luật gốc (dòng 1231-1237).

Đây đúng tinh thần Protocol 6 lineage: nếu container bị xoá hẳn khi nó thuộc 1 doc đang được
`units_excluding()` tính vào tập dịch, thì số node ứng viên/dịch của chính doc đó lúc tính TRƯỚC
khi ghi sẽ không khớp số node thực tế còn lại SAU khi ghi — đúng hình dạng "2 phép đếm khác nhau ra
2 con số khác nhau" của Bug #5. Cách sửa (luôn unwrap cho container thuộc doc đang dịch) loại bỏ
khả năng lệch số mà không cần thay đổi gì ở phía `units_excluding()`/đếm unit.

Tự chạy `test_units_excluding_matches_write_translated_drop` trên EPUB thật `Sourdough Every Day`
(ca có `mini_toc.xhtml`, khó nhất theo bảng §6.28.6.1) — PASS. Assertion chặt: không chỉ so số
lượng, còn xác nhận `all(u.doc_href != "OEBPS/cop.xhtml" for u in units)` trước khi ghi, rồi
`len(guard_doc.units) == len(units)` sau khi `load()` lại file output thật (không tin bộ nhớ, đúng
R6-02). Cũng đã chạy `test_write_translated_drop_doc_hrefs_removes_hardest_real_fixture` (PASS) —
xác nhận `cop.xhtml` bị xoá hẳn khỏi mọi entry (kể cả `mini_toc.xhtml` đã unwrap link, không còn
chuỗi `cop.xhtml` ở đâu cả), `mimetype` vẫn `ZIP_STORED` ở vị trí đầu.

**Đạt.** Lưu ý non-blocking: `docs/Architecture.md` §6.28.6.3 rule (f) hiện chưa mô tả tường minh
ngoại lệ "container thuộc doc đang đóng góp unit → luôn unwrap" — hợp đồng viết trong Architecture.md
và code hiện đã lệch nhau (code đúng hơn, đã có test thật xác nhận). Nên đưa vào backlog để Tech Lead
cập nhật §6.28.6.3 khớp với implementation đã verify, tránh Dev sau đọc Architecture.md rồi viết lại
sai theo bản cũ.

### 5. Kill-switch byte-identical

- PDF: `test_kill_switch_disabled_byte_identical_to_pre_s8` — `copyright_page_removal_enabled=False`
  ⇒ không tạo `pruned/`, `translate_pages` nhận thẳng `input_path == source_pdf` gốc,
  `job.copyright_removed_json is None`, `job.total_pages == 6` (không đổi). Tự chạy lại, PASS.
- EPUB: `test_kill_switch_disabled_epub_byte_identical_behavior` — tương tự,
  `job.total_units == 3` (không loại gì), `copyright.xhtml` vẫn còn trong output. Tự chạy lại, PASS.

**Đạt.**

### 6. Điểm Dev báo lệch khỏi Architecture.md

**#1 — `structural` là `dict[href, status]` thay vì scalar**: hợp lý. §6.28.3 ví dụ JSON viết
`"structural": "full"` như 1 giá trị đơn cho EPUB, nhưng `MAX_REMOVED=3` (đã ghi rõ trong chính
§6.28.2) cho phép tối đa 3 doc bị loại trong cùng 1 job, mỗi doc có thể có kết quả hậu kiểm khác
nhau (ví dụ 1 doc "full", 1 doc "skipped") — 1 giá trị scalar không biểu diễn được, đây thực sự là
gap trong ví dụ minh hoạ của Architecture.md, không phải Dev tự ý đổi hợp đồng. `mode="pdf_pages"`
vẫn giữ `structural: None` đúng ví dụ gốc (xác nhận qua code `job_orchestrator.py:809`). Không phá
vỡ gì ở phía đọc (`src/api/routes/jobs.py` chỉ đọc field `removed`, không đọc `structural`). Đồng ý
với Dev — cần Tech Lead cập nhật ví dụ JSON trong §6.28.3 cho khớp dict schema thật (non-blocking,
đưa vào backlog).

**#2 — EPUB structural fix (rule (f) container)**: đã review kỹ ở mục 4 trên — đúng, có test thật
chứng minh trên EPUB thật khó nhất. Đây là ví dụ tốt của R6-02 bắt được bug TRƯỚC khi chạm production
(Dev tự phát hiện khi viết test bổ sung ngoài yêu cầu tối thiểu của brief).

### 7. Guard `_check_epub_output_guard` chỉ đếm doc `"full"` (finding Dev tự nêu)

Đọc `job_orchestrator.py` dòng 1684-1693: `fully_dropped_doc_hrefs = {href for href, status in
structural_result.items() if status == "full"}`, truyền vào `_check_epub_output_guard(...,
dropped_doc_hrefs=fully_dropped_doc_hrefs)`. Đọc docstring + logic guard (dòng 497-528): guard so
`len(guard_doc.units)` (unit đọc lại từ file output thật) với `len(source_units)` = 
`source_doc.units_excluding(dropped_doc_hrefs or set())`.

Đây **đúng ý đồ thiết kế**: doc `structural="skipped"` vẫn còn nguyên trong file output (chỉ không
được dịch — theo đúng §6.28.6.3 "unit của doc đó VẪN bị loại khỏi tập dịch... trang bản quyền chỉ
đơn giản còn nguyên bản tiếng Anh"), nên **phải** tính unit của nó vào `source_units` khi so với
`guard_doc.units` đọc từ output — nếu loại cả `"skipped"` ra khỏi phép đếm, guard sẽ thấy
`len(guard_doc.units) > len(source_units)` giả tạo (vì doc "skipped" thực tế vẫn còn trong output)
và báo lỗi sai. Ngược lại `dropped_doc_hrefs` truyền cho `units_excluding()` ở Step E4/`total_units`
(dòng 1389, 1428) dùng đúng **toàn bộ** `dropped_doc_hrefs` (cả full lẫn skipped) vì unit của cả
2 loại đều KHÔNG được gửi cho LLM để dịch — 2 tập hợp khác nhau phục vụ 2 mục đích khác nhau, dùng
đúng chỗ.

**Đạt, không phải bug.**

### 8. Golden test (Protocol 5 mục 3 — không mock viết tay)

Tự chạy `pytest tests/test_copyright_detector.py -v`: **20/20 PASS**, dùng file thật trong
`data/uploads/` (không skip). Xác nhận đúng 2 ca âm bắt buộc:
`test_epub_golden_scan_matches_architecture_table[...Baking Heaven...]` và
`...Better_For_You_Packaged_Food...]` — PASS, khớp bảng "Kết quả đo đầy đủ" §6.28.2. Đây đúng tinh
thần Protocol 5 mục 3: golden test chạy trên output thật, không phải mock viết tay theo giả định.

### 9. Test suite + lint (tự chạy lại)

- `pytest -q` toàn repo → **916 passed** (151.86s), khớp đúng số Dev báo trong CHANGENLOG (884 cũ +
  32 mới S8).
- `pytest tests/test_epub_document.py -k "drop_doc_hrefs or units_excluding" -v` → 3/3 PASS (bao
  gồm `Sourdough Every Day` thật).
- `ruff check .` → All checks passed.
- `ruff format --check .` → 22 file "would be reformatted", nhưng **xác nhận bằng cách kiểm tra
  từng file trong diff/untracked của S8** (`git status --porcelain`): không file nào trong 20 file
  Dev đã sửa/tạo cho S8 nằm trong danh sách 22 file chưa format — các file chưa format là nợ kỹ
  thuật có từ trước (ví dụ file test `gemini_provider`), ngoài phạm vi S8. Kết luận Dev báo đúng
  cho phạm vi thay đổi của mình.

### 10. Checklist bắt buộc (CLAUDE.md)

- **R5-04**: `src/services/pdf2zh_runner.py`, `src/services/babeldoc_runner.py` chỉ thêm 1 dòng
  `ClassVar[bool] = True` mỗi file, không viết contract mới nào (CLI flag/endpoint/schema) — nguồn
  đã được Tech Lead trích dẫn từ trước trong Architecture.md §6.28.1 (đọc source `pdf2zh.py:208-217`,
  `translation_config.py:394-422`), Dev không tự research lại (đúng ghi nhận trong CHANGELOG). External
  contract verified against real source: **YES (nguồn: Architecture.md §6.28.1, trích dẫn trực tiếp
  source code `pdf2zh` v1.9.11 và `babeldoc` 0.6.4 đã cài, do Tech Lead verify trước khi Dev
  implement)**.
- **R6-04**: đã trace tay toàn bộ chuỗi `_apply_copyright_removal()` →
  `translation_source_path`/`bilingual_source_path` → `translate_pages(input_path=...)` →
  `create_bilingual_pdf(merged_path, bilingual_source_path, ...)` ở mục 1-3 trên — biến truyền vào
  bước N+1 xác nhận bắt nguồn từ return value bước N, không chỉ xác nhận "gọi đúng tham số riêng".
- **R8-01**: đã đối chiếu bảng Protocol 8 audit đầy đủ 18 bước của Tech Lead (§6.28.5) qua code thật
  — xác nhận đúng bước #14 (`create_bilingual_pdf`) là bước CŨ bị sửa, các bước khác giữ nguyên đúng
  như bảng audit đã quyết định. Không phát hiện bước nào bị bỏ sót audit.
- **Protocol 5 R5-03**: golden test dùng file PDF/EPUB thật trong `data/uploads/` (không phải mock
  viết tay) — mục 8 trên. Integration test dùng `scan_units()` thật (không mock detector), chỉ mock
  `translate_pages`/pricing provider (đúng phạm vi — đây không phải external tool contract, là
  logic nội bộ). **Đạt.**

### 11. R6-03 live E2E — CHƯA làm, đúng như Dev tự báo

CHANGELOG mục "Test" ghi rõ: "R6-03 (live E2E với PDF/EPUB thật xuyên suốt job thật, không mock)
CHƯA chạy — để QA làm". Xác nhận đây là phân công đúng theo CLAUDE.md (R6-03 là trách nhiệm QA,
không phải Reviewer) — không phải thiếu sót của Dev, nhưng **QA không được đánh dấu
`ready_for_release` cho tới khi làm xong R6-03 + R5-03 mở rộng cho `data/uploads` thật**, và 5 mục
`⚠️ ASSUMED` (S8-A1..E1, đã có backlog BL-25..BL-29 với owner đúng theo R5-06) cũng cần QA/Tech Lead
theo dõi ở lần chạy live đầu tiên.

### Kết luận

**APPROVE.**

Không có issue blocking. Toàn bộ 5 yêu cầu review cụ thể trong brief (chống Bug #9, đối xứng 2
engine, resume guard, EPUB structural fix, kill-switch) đều xác nhận đúng bằng cách trace tay code
thật + tự chạy lại test thật (không tin lời Dev báo). Golden test 20/20 PASS trên tài liệu thật,
toàn bộ 916 test repo PASS, `ruff` sạch cho phạm vi S8.

Non-blocking findings (đưa vào `backlog[]`):
1. `docs/Architecture.md` §6.28.6.3 rule (f) cần cập nhật để mô tả tường minh ngoại lệ "container
   thuộc doc đang đóng góp unit → luôn unwrap, không bao giờ xoá cả container" — hiện văn bản
   Architecture.md và code đã lệch nhau (code đúng hơn, có test thật xác nhận), owner: tech-lead.
2. `docs/Architecture.md` §6.28.3 ví dụ JSON `"structural": "full"` cần đổi thành ví dụ dict
   `{"href": "full"|"skipped", ...}` để khớp schema thật khi `MAX_REMOVED > 1` doc bị loại cùng lúc,
   owner: tech-lead.
3. R6-03 (live E2E PDF+EPUB thật xuyên suốt) và 5 mục `⚠️ ASSUMED` S8-A1..E1 (đã có backlog
   BL-25..BL-29) là điều kiện bắt buộc trước khi QA release — nhắc lại để không bị bỏ sót ở bước
   tiếp theo.

---

## 2026-09-17 — Review S8-B1 fix (`jobs.total_pages`/`jobs.total_units` không cập nhật sau cắt trang bản quyền)

**Phạm vi**: fix bug blocking do QA phát hiện qua live E2E (`docs/test-report.md` "Kết luận S8"),
theo phương án (c) Tech Lead đã chốt (`docs/design-log.md` mục 2026-09-17 "S8-B1"). File review:
`src/core/job_orchestrator.py::_apply_copyright_removal()`/`_apply_epub_copyright_removal()`,
helper `_create_job()`/`_create_epub_job()`, 4 test mới (idempotent + kill-switch-replay, PDF+EPUB).

### 1. Ghi `total_pages`/`total_units` vô điều kiện trong nhánh có cắt thật

Đọc trực tiếp `job_orchestrator.py:845-853` (PDF) và `:930-934` (EPUB, cả 2 nhánh: quyết định mới
`:889-895`+`:932`, replay quyết định cũ `:889-895`). Xác nhận:

- PDF: `job.total_pages = len(keep_indices)` nằm SAU `_select_pdf_pages()` thật, KHÔNG có điều kiện
  `is None` bao quanh, chỉ chạy khi đã qua nhánh `if not removed: return ...` (tức có cắt thật).
- EPUB: `job.total_units = len(doc.units_excluding(removed))` xuất hiện ở CẢ HAI nhánh — nhánh
  replay (`committed_removed is not None`, dòng 889-895) VÀ nhánh quyết định mới (dòng 928-934) —
  cả hai đều gated bởi `if removed:` (không ghi khi `removed` rỗng). Đối xứng đúng với PDF, không bỏ
  sót nhánh replay như có thể nhầm khi chỉ đọc lướt.

**Đạt yêu cầu #1.**

### 2. Guard `is None` ở `run_job()`/`run_epub_job()` giữ nguyên

`grep -n "total_pages is None\|total_units is None"` ra 3 chỗ: `:994` (`run_job()`, PDF),
`:1441` (`run_epub_job()`, EPUB), `:1838` (`run_parse_only()`/`_run_parse_only_pipeline()`, nhánh
parse_only không liên quan S8). Brief nói `:941`/`:1388` — lệch số dòng do các sửa đổi khác chèn
thêm dòng phía trên, nhưng đối chiếu nội dung xác nhận đây đúng 2 chỗ Tech Lead chỉ, cả hai **giữ
nguyên `if ... is None:`**, không có gì bị xoá/đổi logic. **Đạt yêu cầu #2.**

### 3. `routes/jobs.py:648,652` không bị đụng

Đọc trực tiếp — `total_pages=upload.page_count`, `total_units=cost_estimate.total_units if ...`
còn nguyên như RCA của Tech Lead mô tả, không có diff nào ở file này theo `git diff` phạm vi S8-B1
(chỉ `job_orchestrator.py` + test files bị đổi, xem CHANGELOG "Code"/"Test"). **Đạt yêu cầu #3.**

### 4. Logic c2 (kill-switch replay) — trace tay từng nhánh + tự nghĩ thêm edge case

Đọc kỹ `:769-790` (PDF) và `:869-887` (EPUB) — cùng khuôn:

```
replaying_committed_decision = existing_chunk is not None
    and committed_removed is not None
    and len(committed_removed) > 0

if not enabled and not replaying_committed_decision: return (no cut)
if existing_chunk is not None and copyright_removed_json is None: return (no cut, job cũ)
```

Trace các case:
- **Kill-switch tắt từ đầu, job chưa từng cắt** (case brief yêu cầu tự nghĩ): `existing_chunk=None`
  → `replaying=False` → điều kiện đầu `True` → return sớm, KHÔNG cắt. Đúng.
- **Kill-switch bật, job cũ có `removed=[]`** (lần trước quét không thấy gì — case brief yêu cầu tự
  nghĩ, để kiểm tra không bị nhầm thành "đang replay"): `committed_removed=()` (tuple/set rỗng,
  KHÔNG phải None) → `len(committed_removed) > 0` là `False` → `replaying=False`. Vì kill-switch
  đang BẬT (`not enabled` = False) nên điều kiện đầu False, không return sớm ở đó — nhưng rơi tiếp
  xuống `if committed_removed is not None: removed = committed_removed` (rỗng) → `if not removed:
  return` → không cắt. Kết quả đúng ("không cắt"), và quan trọng hơn: **không hề đi qua bất kỳ
  đường nào gán lại `total_pages`/`total_units`** — không bị nhầm thành "đang replay". Đúng.
- **Case chính brief nêu — kill-switch tắt SAU khi đã cắt thật + có Chunk row +
  `removed != []`**: `replaying=True` → điều kiện đầu `False` (không return) → guard "job cũ"
  cũng `False` (`copyright_removed_json` không None) → rơi xuống nhánh `committed_removed is not
  None` → `removed` = giá trị đã cam kết (khác rỗng) → chạy tiếp cắt thật (`_select_pdf_pages`
  PDF / doc.units_excluding EPUB) → ghi `total_pages`/`total_units` vô điều kiện. Đúng theo thiết
  kế (c2) — đã xác nhận bằng test thật ở mục 5 dưới, không chỉ đọc code suông.
- Thứ tự 2 guard (kill-switch trước, "job cũ" sau) không gây sai lệch cho bất kỳ case nào ở trên vì
  2 điều kiện không bao giờ cùng dẫn tới kết quả khác nhau khi hoán đổi thứ tự (đã tự kiểm bằng
  bảng chân trị 4 tổ hợp `existing_chunk × copyright_removed_json`, không chỉ tin comment code).

**Đạt yêu cầu #4 — logic đúng, kể cả 2 edge case tự nghĩ thêm.**

### 5. Idempotent — tự chạy lại, xác nhận gọi hàm 2 lần thật

Đọc + tự chạy `test_apply_copyright_removal_idempotent_across_resume_calls` và
`test_kill_switch_disabled_midway_still_replays_committed_decision` (PDF) +
`test_apply_epub_copyright_removal_idempotent_across_resume_calls` +
`test_kill_switch_disabled_midway_epub_still_replays_committed_decision` (EPUB): cả 4 test gọi
`_apply_copyright_removal()`/`_apply_epub_copyright_removal()` **2 lần thật** trên cùng object
`job`/`session` (không phải gọi 1 lần rồi giả định lần 2), `await session.refresh(job)` giữa 2 lần
để đọc lại từ DB thật (không đọc object Python cache), và assert **giá trị cụ thể**
(`job.total_pages == 5`, `job.copyright_removed_json == removed_json_1`, `dropped_2 == dropped_1`)
— không chỉ `assert_called()`. Đúng tinh thần R6-02. `pytest -q
tests/integration/test_job_orchestrator_copyright_removal.py
tests/integration/test_epub_orchestrator_copyright_removal.py -v` → tất cả pass, 2 test mới mỗi
file thực thi và pass. **Đạt yêu cầu #5.**

### 6. Sửa helper `_create_job()`/`_create_epub_job()` — kiểm tra không che lấp test khác

Helper mới gán `total_pages`/`total_units` giống hệt route thật (đọc trực tiếp code, đúng như
CHANGELOG mô tả). Tự chạy lại 5 file Dev liệt kê:

```
pytest -q tests/integration/test_job_orchestrator_chunk_size_cold_start.py \
  tests/integration/test_job_cancel.py tests/integration/test_job_history_finished_at.py \
  tests/integration/test_cost_capped_orchestrator.py \
  tests/integration/test_job_orchestrator_concurrency.py
→ 30 passed
```

Không có test nào phụ thuộc `total_pages is None` để làm đường chạy (đã đọc qua các file, không
thấy assertion nào dựa vào giá trị NULL của 2 field này trước/sau `run_job()`). **Đạt yêu cầu #6** —
không phát hiện test nào bị che lấp bug.

### 7. Chạy toàn repo

```
pytest -q  → 920 passed, 1240 warnings in 149.56s   (khớp đúng số Dev báo)
ruff check .  → All checks passed!
ruff format --check src/core/job_orchestrator.py tests/integration/test_job_orchestrator.py \
  tests/integration/test_job_orchestrator_copyright_removal.py \
  tests/integration/test_epub_orchestrator_copyright_removal.py  → 4 files already formatted
```

**Đạt yêu cầu #7.** (Không kiểm `ruff format --check .` toàn repo — Dev đã báo rõ 15 file khác lệch
format từ trước, không thuộc phạm vi S8-B1, đúng như CHANGELOG ghi; không phải việc của review này.)

### Checklist bắt buộc (CLAUDE.md)

- **R5-04**: N/A — `_apply_copyright_removal()`/`_apply_epub_copyright_removal()` không phải wrapper
  gọi external tool (`*_runner.py`/`*_provider.py`), là logic nội bộ đọc/ghi DB + gọi
  `scan_units()`/`fitz` nội bộ. Không áp dụng.
- **R6-04**: đã trace tay ở mục 4 trên — biến `removed`/`keep_indices` dùng để ghi
  `total_pages`/`total_units` xác nhận bắt nguồn đúng từ `committed_removed` (đọc lại từ
  `job.copyright_removed_json`, chính là artifact bước quét trước) hoặc từ kết quả `scan_units()`
  vừa chạy trong cùng lần gọi — không có đường nào ghi giá trị không bắt nguồn từ quyết định cắt
  thật.
- **R8-01**: N/A cho lần fix này — không thêm engine/biến thể mới, chỉ sửa lỗi lineage trong 2 hàm
  đã có.
- **Protocol 5 R5-03**: N/A — không có external tool call nào trong phạm vi fix này.

### Kết luận

**APPROVE.**

Không phát hiện issue blocking. Cả 7 yêu cầu review trong brief đều xác nhận đúng bằng cách đọc
code trực tiếp + tự chạy lại test thật (không tin số liệu Dev báo mà không verify). Logic c2 đúng ở
cả 2 edge case tự nghĩ thêm ngoài case chính brief nêu. `pytest` toàn repo 920 passed khớp báo cáo
Dev, `ruff` sạch trong phạm vi sửa.

Non-blocking findings (đưa vào `backlog[]`):
1. Brief trỏ số dòng `:941`/`:1388` cho 2 guard `is None`, thực tế đúng vị trí là `:994`/`:1441` (số
   dòng đã dịch do các sửa đổi khác chèn thêm ở trên) — không phải lỗi Dev, chỉ là brief PM viết từ
   thời điểm trước khi Tech Lead viết thêm docstring/comment vào `_apply_copyright_removal()`. Nhắc
   PM cẩn thận số dòng cụ thể dễ lệch giữa lúc viết brief và lúc Dev thực thi — owner: pm (lưu ý quy
   trình, không cần action code).
2. `docs/CHANGELOG.md` "S8-B1 fix" chưa nhắc lại rõ 3 mục non-blocking cũ (Architecture.md
   §6.28.6.3/§6.28.3, R6-03 chưa chạy) vẫn còn treo từ đợt review S8 trước — không phải lỗi của fix
   này nhưng cần QA/PM đảm bảo không bị quên khi đóng S8 hẳn — owner: qa/tech-lead (đã có trong mục
   findings đợt trước, nhắc lại để không lạc mất qua 2 đợt review).

---

## 2026-09-17 — Review BL-21: `GET /health` mở rộng (`git_commit`/`code_stale`) + `scripts/restart_server.sh`

**Phạm vi**: `src/api/main.py` (`_run_git`, `_code_snapshot`, `_fingerprint`, hằng module-level,
handler `/health` mở rộng), `scripts/restart_server.sh` (mới), `tests/test_health.py`. Đối chiếu với
`docs/Architecture.md` §5.4 (đọc §5.4.1–§5.4.6, dòng ~829–990) và `docs/design-log.md` mục "BL-21"
cuối file.

### 1. `code_stale` fingerprint — tập file đưa vào/loại trừ

Đọc trực tiếp `_code_snapshot()` (`src/api/main.py:108-133`): walk `src_dir = _PROJECT_ROOT / "src"`
bằng `rglob("*.py")`, bỏ qua mọi path có `__pycache__` trong `path.parts`, cộng thêm `.env` nếu tồn
tại. Không có bất kỳ tham chiếu nào tới `web/`, `fonts/`, `docker/`, `.venv/` trong hàm — các thư mục
này bị loại trừ **tự nhiên** (không nằm trong `src/`), đúng đặc tả §5.4.2, không phải loại trừ bằng
blacklist dễ viết sai pattern. Đã tự đếm `find src -name "*.py" -not -path "*/__pycache__/*" | wc -l`
→ **79**, khớp chính xác con số Tech Lead đo trong Architecture.md §5.4.2. Đạt yêu cầu #1.

### 2. Git subprocess chỉ chạy 1 lần lúc import

`_GIT_COMMIT`, `_GIT_COMMIT_FULL`, `_GIT_DIRTY_AT_START` được gán ở top-level module
(`src/api/main.py:145-150`), ngoài mọi hàm — chạy đúng 1 lần lúc Python import `src.api.main`. Handler
`/health` (`:187-216`) chỉ đọc lại 3 biến module này, không gọi `_run_git()` hay `subprocess` gì
trong request path — xác nhận bằng đọc code, không có lời gọi `subprocess`/`_run_git` nào bên trong
`async def health()`. Đạt yêu cầu #2, không cần đo hiệu năng thêm vì cấu trúc code loại trừ khả năng
gọi lại theo thiết kế (không phải do timing may rủi).

### 3. Fail-soft khi thiếu `git`/không phải repo

`_run_git()` (`:86-105`) bọc `subprocess.run` trong `try/except (OSError, subprocess.TimeoutExpired)`
→ trả `None`; đồng thời trả `None` nếu `returncode != 0`. Không có nhánh nào raise ra ngoài hàm. Đã tự
verify sống (không chỉ đọc code): chạy Python import `src.api.main` với `PATH` không có `git` (dùng
`uv run --no-project python3 -c "..."` với `PATH` trỏ tới thư mục fake không chứa `git`) →
```
GIT_COMMIT= unknown
GIT_COMMIT_FULL= unknown
GIT_DIRTY_AT_START= None
```
Import module thành công, không crash — khớp đúng contract "fail-soft" ở §5.4.1. Do 3 biến git chỉ
được tính lúc import (mục 2), patch `_run_git` sau khi module đã import sẽ không mô phỏng đúng ca
thật (git thật sự biến mất lúc SERVER khởi động) — nên đã chọn cách verify đúng bản chất hơn là giả
lập ở đúng thời điểm import, thay vì monkeypatch `_run_git` rồi gọi `/health` (không có ý nghĩa vì
`/health` không gọi lại `_run_git`). Đạt yêu cầu #3.

### 4. `scripts/restart_server.sh` — race condition khi kiểm job active

Đọc kỹ logic dòng 29-48: script `curl` `/api/jobs?status=<active>` lấy `total`, nếu `>0` thì từ chối
(trừ `--force`). Xác nhận có race condition thật: giữa lúc script đọc xong `ACTIVE_TOTAL=0` (dòng 30)
và lúc `pkill -f "$APP_PATTERN"` thực thi (dòng 53), có một khoảng hở — nếu một job mới chuyển sang
trạng thái active (ví dụ do 1 request `POST /api/jobs` khác chạy song song) đúng trong khoảng hở đó,
job sẽ bị kill giữa chừng mà script không phát hiện được, vì không có lock nào giữa bước kiểm tra và
bước kill.

**Đánh giá mức độ rủi ro**: THẤP, không blocking. Lý do: (a) script này chạy thủ công bởi Dev/PM
ngay sau khi sửa code xong, không phải cron/automation — cửa sổ race chỉ vài trăm ms giữa 2 lệnh
`curl` (round-trip HTTP nội bộ localhost) và không có traffic nền tự động tạo job mới trong quy trình
hiện tại (không có scheduler tạo job); (b) hậu quả nếu xảy ra trùng đúng khoảnh khắc đó là mất 1 job
đang chạy — đúng loại rủi ro mà `--force` documented đã chấp nhận có thể xảy ra có chủ đích, ở đây
chỉ là vô tình với xác suất cực thấp; (c) khắc phục triệt để (lock ở DB, hoặc kiểm tra lại NGAY TRƯỚC
`pkill`) là khả thi nhưng brief đã nói rõ "không cần fix race condition tuyệt đối". Ghi 1 non-blocking
suggestion vào backlog thay vì block PR — xem mục Non-blocking findings bên dưới.

### 5. Test `code_stale` mới (`tests/test_health.py::test_health_reports_code_stale_after_file_touched`)

Đọc kỹ: test tạo `fake_file` trong `tmp_path` (không đụng file thật `src/`), lưu
`original_snapshot`/`original_fingerprint`, tạm ghi đè `main_module._CODE_SNAPSHOT_AT_START` để coi
như file giả đã có mặt từ lúc "import" (với stat cũ), rồi sửa nội dung file giả (đổi mtime), tạm thay
`main_module._code_snapshot` bằng lambda merge kết quả thật + entry file giả với stat MỚI, gọi
`/health`, assert `code_stale=True` và file giả có trong `code_changed_files`, khôi phục cả 2 biến
module ở `finally`. Đây không phải `monkeypatch` fixture chuẩn của pytest (dùng `try/finally` thủ
công thay vì fixture `monkeypatch`) nhưng đạt đúng hiệu quả tương đương — không rò rỉ state sang test
khác (đã tự chạy `pytest tests/test_health.py -v` 2 lần liên tiếp, cả 2 lần `test_health` (chạy sau
trong file) vẫn PASS với `code_stale=False`, xác nhận state được khôi phục đúng). Test có ý nghĩa
thật: nó lắp cả 2 phía (snapshot "at start" giả lập + snapshot "now" giả lập) nên đang test đúng logic
so sánh diff trong handler `/health`, không phải giả lập kết quả mong muốn sẵn rồi assert lại chính nó
— nếu handler tính sai (`current_fingerprint` không so đúng `_CODE_FINGERPRINT_AT_START`, hoặc
`changed_files` tính sai) test này sẽ đỏ. Đạt yêu cầu #5.

### 6. Tự chạy lại test + lint

```
uv run pytest tests/test_health.py -v   → 2 passed
uv run pytest -q                         → 921 passed, 1246 warnings in 142.17s   (khớp đúng số Dev báo)
uv run ruff check src/api/main.py tests/test_health.py       → All checks passed!
uv run ruff format --check src/api/main.py tests/test_health.py → 2 files already formatted
```

Đạt yêu cầu #6. (`ruff check`/`format` không áp dụng được cho `scripts/restart_server.sh` — đó là
shell script, không phải Python; không có `shellcheck` cài trên máy này để lint riêng, ghi nhận là
giới hạn của lần review này chứ không phải bỏ qua.)

### 7. Thư mục `logs/` untracked

`git status` cho thấy `logs/` (chứa `uvicorn.log` do `restart_server.sh` sinh ra, dòng 15/62/79) là
runtime artifact, không nên track. Đã tự thêm `logs/` vào `.gitignore` (việc nhỏ, đúng tinh thần được
phép tự làm khi không cần hỏi lại). Đạt yêu cầu #7.

### Checklist bắt buộc (CLAUDE.md)

- **R5-04**: N/A cho `_run_git()`/`_code_snapshot()` — đây không phải wrapper gọi *external tool cần
  verify contract* theo nghĩa Protocol 5 (pdf2zh/MinerU/LLM SDK); `git` chỉ được dùng như tiện ích
  đọc metadata versioning, output (`rev-parse`, `status --porcelain`) là hành vi git cơ bản đã biết
  rõ, không có schema phức tạp nào bị suy đoán. design-log.md (mục BL-21, đoạn "Ghi chú nguồn R5-01")
  cũng đã tự xác nhận đúng điều này. Xác nhận N/A hợp lý, không phải im lặng bỏ qua.
- **R6-04**: N/A — `/health` không phải orchestrator gọi tuần tự nhiều service với dữ liệu chuyền
  qua nhau; toàn bộ field trong response đọc độc lập từ biến module/filesystem, không có bước N+1
  nào tiêu thụ output của bước N theo nghĩa Protocol 6.
- **R8-01**: N/A — không có biến thể/engine mới đi qua pipeline dùng chung nào trong phạm vi BL-21.
- **Protocol 5 R5-03**: N/A cho phần code — không có external tool call nào cần smoke test riêng
  ngoài `git` (đã tự verify fail-soft ở mục 3). Live verify tinh thần R6-03 cho chính tính năng
  `/health`/`restart_server.sh` đã được Dev tự làm trên server thật và ghi lại trong CHANGELOG (touch
  file → `code_stale=true` → restart → `code_stale=false`) — đã đọc log đó, hợp lý.

### Kết luận

**APPROVE.**

Không phát hiện issue blocking. Cả 7 yêu cầu review trong brief đều xác nhận đúng bằng cách đọc code
trực tiếp + tự chạy lại test/lint thật + tự verify sống fail-soft bằng cách import module với `git`
bị ẩn khỏi `PATH` (không chỉ đọc code suông). `pytest` toàn repo 921 passed khớp báo cáo Dev, `ruff`
sạch trong phạm vi sửa.

Non-blocking findings (đưa vào `backlog[]`):
1. `scripts/restart_server.sh` có race condition giữa bước kiểm `total` job active và bước `pkill`
   (mục 4 ở trên) — rủi ro thấp (thao tác thủ công, cửa sổ hở rất hẹp), nhưng nếu muốn khắc phục
   triệt để: kiểm tra lại `/api/jobs?status=...` một lần nữa NGAY TRƯỚC dòng `pkill` (dòng 53), hoặc
   thêm 1 giây `sleep` + double-check. Không blocking — owner: dev (khi có thời gian rảnh, không cần
   gấp).
2. `scripts/restart_server.sh` chưa có công cụ lint tự động (`shellcheck` không cài trên máy review)
   — nếu project muốn giữ chuẩn lint cho shell script tương lai (đã có thêm 1 script mới trong repo),
   cân nhắc thêm `shellcheck` vào toolchain — owner: tech-lead (quyết định có đáng đầu tư hay không,
   hiện tại chỉ có 1 script).
