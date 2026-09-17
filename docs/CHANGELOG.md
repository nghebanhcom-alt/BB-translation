# CHANGELOG — BB-Translation

<details>
<summary>Đợt rotate đã lưu trữ (Protocol C.2)</summary>

- **Đợt 1 (2026-09-18)**: Increment 1 (project scaffolding) → Bug #8 fix
  (2026-09-08, "Chữ nhảy lung tung" MediaBox/CropBox) + US-15 markdown parse-only, trước khi
  US-20 "Các từ mới" mở đầu phần còn giữ lại ở đây. Xem toàn văn tại
  `docs/archive/CHANGELOG-until-2026-09-18.md` (kèm mục lục ở đầu file).

</details>

## US-20 "Các từ mới" — gợi ý thuật ngữ mới từ tài liệu vừa dịch (2026-09-08)

Implement theo `docs/Architecture.md` §6.18, **ưu tiên §6.18.8 "Final Decision sau phản biện
Domain Expert + quyết định mới của user"** ở mọi chỗ mâu thuẫn với §6.18.1-6.18.7 gốc (đúng như
brief yêu cầu — KHÔNG tự suy diễn lại thiết kế). KHÔNG đụng `src/core/glossary_manager.py` (đang
sửa song song ở 1 session/worktree khác — chỉ đọc tham khảo). KHÔNG implement US-17/US-18/US-22.

### Module mới — thuật toán trích xuất (`src/core/term_extractor.py`)

- `normalize_source_text()` — 6 bước T4 theo đúng thứ tự Architecture.md quy định: strip
  HTML/Markdown (bảng `<table>`, ảnh `![]()`, heading `#`) → NFKC → nháy cong → straight → ghép
  mảnh vỡ ligature (2 rule tách biệt: `fi`/`fl` merge cả dạng lẻ lẫn dạng hậu tố; `ff`/`ffi`/`ffl`
  CHỈ merge khi là token lẻ đứng riêng — tách 2 rule này để tránh false-positive kiểu "staff
  members" → "staffmembers" mà spec gốc không cảnh báo rõ) → khử gạch nối ngắt dòng.
- Tokenizer chấp nhận Latin có dấu (`[A-Za-zÀ-ÿ]...`) — `pâte à choux`, `crème` sống sót nguyên
  vẹn thay vì bị băm thành `p`/`te`.
- N-gram 1-3, sinh theo từng "segment" (chia theo bộ dấu câu tường minh gồm cả dấu phẩy — 3-gram
  không vượt dấu phẩy).
- Khử lồng nhau: chốt cách đọc **"MAX, không SUM"** đúng T5 — mỗi n-gram ngắn chỉ bị hấp thụ nếu
  MỘT n-gram dài cụ thể (không phải tổng nhiều n-gram dài khác nhau) chiếm ≥80% số lần xuất hiện
  của nó. N-gram dài đã khớp glossary vẫn được tính là "đã giữ" cho mục đích hấp thụ (dù bản thân
  nó bị lọc khỏi kết quả) — sửa đúng lỗi thứ tự bước 3/4 mà bản gốc mắc phải (`puff` #35 mồ côi
  sau khi `puff pastry` bị xoá trước khi kịp hấp thụ `puff`).
- Sàn tần suất theo SỐ TOKEN (không theo số trang — `total_pages` NULL cho EPUB theo đúng thiết
  kế): `term_min_occurrences=3` nếu tài liệu ≥50.000 token, `term_min_occurrences_short_doc=2` nếu
  ngắn hơn.
- 4 noise flag (`proper_noun`, `stopword_middle`, `fragment_suspect`, `plural_merged`) — **demote
  rank_score × 0.3 + ẩn mặc định ở UI, KHÔNG xoá** đúng quyết định T4 (khác đề xuất "lọc bỏ" của
  Domain Expert) — vì `Swiss meringue`, `Silpat`, `Fahrenheit` đều là glossary entry thật và đều
  là tên riêng viết hoa giữa câu, xoá cứng sẽ mất chúng vĩnh viễn.
- Trần `max_suggested_terms_per_job` **đổi nghĩa** thành van chống tràn DB (default `20_000`),
  KHÔNG còn là trần chất lượng — không cắt ở bất kỳ con số "đẹp" nào khác, cắt theo `rank_score`
  khi thật sự chạm van + log warning.
- **KHÔNG** ship bộ lọc `en_common.txt`/`baking_sense_allowlist.txt` — T2 đã bác bỏ hẳn hướng này
  (đo được: bộ lọc phổ thông xoá đúng `proof/score/cream/rest/turn` là glossary entry thật, trong
  khi giữ lại `flour/sugar/egg` sinh ra top-40 vô dụng). Thay bằng `en_function_words.txt` (~200 hư
  từ đóng, an toàn tuyệt đối với EC-06 vì `proof`/`score`/... không phải hư từ).
- `_specificity()` (tín hiệu xếp hạng, KHÔNG phải bộ lọc — T2) đọc `en_freq_top50k.tsv` nếu có;
  **file này CHƯA ship trong increment này** (không có nguồn danh sách tần suất nào sẵn sàng đóng
  gói) → luôn degrade về `1.0` cho mọi từ, đúng đường degrade an toàn Architecture.md đã định
  nghĩa sẵn ("chỉ mất chất lượng sắp xếp, không đổi tập hiển thị"). Cần PM/Tech Lead quyết định có
  đầu tư nguồn dữ liệu này sau không — không chặn v1.
- **Lệch vị trí file so với spec**: Architecture.md ghi `data/wordlists/*.txt`, nhưng **toàn bộ
  thư mục `data/` bị `.gitignore` chặn** ở repo này (`git check-ignore` xác nhận) — ship đúng theo
  spec sẽ khiến file không bao giờ vào git, mọi checkout mới thiếu mất wordlist. Đổi sang
  `src/core/wordlists/en_function_words.txt` (nằm cùng cây `src/`, luôn theo git, giống cách
  `fonts/` đã nằm ngoài `data/` vì lý do tương tự). Đây là thay đổi VỊ TRÍ FILE thuần tuý, không
  đổi thiết kế/thuật toán — nhưng ghi rõ ở đây để Tech Lead biết và xác nhận lại nếu muốn khác đi.

### Module mới — so khớp glossary (`src/core/glossary_matching.py`)

- `glossary_match_forms(term_en) -> set[str]` — hàm CHUNG dùng cho US-20 (T3, điều kiện lọc DUY
  NHẤT sau quyết định của user). Tách `/`, bỏ `(...)` nhưng LUÔN giữ cả nội dung trong ngoặc làm
  phương án riêng (kể cả ngắn/viết tắt — theo đúng VÍ DỤ Architecture.md đưa ra cho `pound (lb)` →
  giữ cả `lb`, `SMBC` → giữ cả viết tắt, dù câu chữ mô tả rule ở ngay phía trên ví dụ lại nói
  "≥3 ký tự và không phải viết tắt thuần" — 2 chỗ MÂU THUẪN NHAU trong chính Architecture.md; đã
  chọn theo ví dụ cụ thể vì rủi ro over-inclusion ở đây là an toàn hơn theo đúng nguyên tắc "thà
  gộp nhầm còn hơn bỏ sót" mà chính §6.18.8 T3 nêu — **đây là điểm cần Tech Lead xác nhận lại**,
  xem mục "Điểm chưa rõ ràng" cuối entry).
- Sinh biến thể hình thái (KHÔNG stemming ứng viên, chỉ EXPAND base đã biết — đúng lý do T3 nêu:
  cắt hậu tố token bất kỳ dễ over-stem, sinh biến thể từ base đã biết thì dạng thừa vô hại).
- **Chưa wire vào `GlossaryManager._count_occurrences()`** (bug độc lập §6.6.5 Domain Expert phát
  hiện, PM đã tách task riêng) — đúng brief, không tự ý sửa file đó.
- Test (`tests/test_glossary_matching.py`, 9 case): tất cả case dựa trên **114 glossary entry
  thật** export từ `data/bb_translation.db` (`tests/fixtures/term_extraction/real_glossary_114.json`)
  — bao gồm chính 13 term Domain Expert đã đo là "leak" dưới `.lower()` cũ (`pound`, `ounce`,
  `bloom`, `tempering`, `whipping`, `kneading`, `teaspoon`, `glaze`, `silpat`, `fahrenheit`,
  `knead`, `whisking`, `tablespoon`).

### DB schema mới (`src/models/suggested_term.py`)

- `SuggestedTerm` — bảng MỚI hoàn toàn (không phải `ALTER TABLE` cột mới) nên chỉ cần đăng ký vào
  `src/models/__init__.py` + import list của `src/models/database.py` — `create_all()` tự tạo,
  không cần thêm gì vào `_NEW_NULLABLE_COLUMNS`.
- 2 index composite (`UNIQUE(job_id, term_en)`, `(status, rank_score DESC)`) tạo bằng raw
  `CREATE INDEX IF NOT EXISTS` trong `init_db()` — theo đúng pattern `idx_glossary_entries_term_nocase`
  đã có (SQLModel trong repo này chưa có tiền lệ dùng `__table_args__`/`UniqueConstraint`).
- `src/core/config.py`: 4 field mới (`term_extraction_enabled`, `max_suggested_terms_per_job`,
  `term_min_occurrences`, `term_min_occurrences_short_doc`) theo đúng bảng T5 đã cập nhật, cả 4
  vào `SETTINGS_DB_OVERRIDABLE_FIELDS`.

### Data lineage + orchestration (`src/core/term_extraction_service.py`)

- `_extract_source_text_for_terms(job)` — implement ĐÚNG bảng §6.18.5: `pdf_digital` đọc
  `job.file_path`; `pdf_scan` đọc `job.ocr_bridge_path` (KHÔNG `file_path` — đúng dạng lỗi Bug #5);
  `parse_only` đọc `Path(job.output_path).parent / "document.md"` (vì `output_path` giờ trỏ
  `parse_result.zip` theo S15-4, KHÔNG đọc thẳng zip); `epub` raise lỗi rõ ràng (US-22 chưa ship
  `EpubDocument.full_text()` — nhánh này hiện KHÔNG THỂ bị gọi qua đường bình thường vì
  `run_job()` reject EPUB trước khi tới `status=completed`, nhưng vẫn viết đúng thay vì đọc nhầm
  nếu tương lai có đường gọi khác).
- Test lineage (Protocol 6 R6-02) dùng **decoy file thật**: `pdf_scan` test tạo 1 PDF gốc chứa văn
  bản "THIS MUST NEVER BE READ" ở `file_path` và văn bản thật ở `ocr_bridge_path` — assert đúng nội
  dung đọc được, không chỉ `assert extract_terms.called`.
- `_collect_existing_glossary_forms()` — **query trực tiếp `GlossaryEntry`** (không gọi qua
  `GlossaryManager`, đúng brief không đụng file đó), gộp scope global + project (`job.batch_id`,
  cùng pattern `project_id=job.batch_id` đã có trong `job_orchestrator.py`).
- `extract_and_store_terms(job_id, session, settings)`: chạy sau `run_job()` trả về, chỉ khi
  `status=="completed"` (BR-TERM-01); **idempotent re-run** — xoá + ghi lại mọi row `pending` cũ,
  nhưng GIỮ NGUYÊN row đã `added`/`dismissed` (user đã quyết định rồi không bị reset khi chạy lại
  thủ công qua `POST /api/jobs/{id}/extract-terms`).
- `src/api/routes/jobs.py`: wire vào `_run_job_background()` đúng pseudo-code §6.18.6 — try/except
  RIÊNG, không có đường nào đổi `job.status` (thêm `return` sớm ở nhánh crash của `run_job()` để
  tránh `NameError` khi tham chiếu `result` chưa gán); thêm `POST /{job_id}/extract-terms` (chạy
  lại thủ công); thêm `SuggestedTerm` vào danh sách xoá thủ công của `DELETE /{job_id}` (đúng ghi
  chú §6.18.3 — SQLite tắt FK enforcement, không được tin `ON DELETE CASCADE`).

### API (`src/api/routes/glossary.py`)

- `GET /suggested` — `job_id` optional (gộp mọi job), `status` (mặc định `pending`), `sort`
  (`rank`/`count`/`alpha`), `min_ngram`, `include_noise`, trả `total` + `noise_hidden_count` đúng
  §6.18.4 đã sửa.
- `POST /suggested/{id}/dismiss` — 204, chỉ đổi `status='dismissed'` (BR-TERM-04 per-job, KHÔNG
  blacklist toàn cục).
- `POST /suggested/{id}/promote` — gọi THẲNG `create_entry()` cùng module (không viết lại logic).
  **Chưa có BR-GLOSS-07** (409 xác nhận ghi đè) vì `create_entry()`/`bulk_import()` hiện tại CHƯA
  implement rule đó (US-17 riêng, chưa tới lượt) — đúng brief: không tự thêm confirm-overwrite
  ngoài phạm vi. `request.force` được nhận nhưng chưa có tác dụng, ghi rõ trong docstring.
- `POST /suggested/suggest-translation` — hành động DUY NHẤT tốn tiền. Gộp tối đa 40 term/request
  LLM (tự động chia nhiều request nếu `ids` dài hơn), đi qua `provider.translate()` thật (có
  `TranslationResult.estimated_cost_usd` thật), chia đều cost cho từng term trong cùng batch, ghi
  vào `suggested_terms.translation_cost_usd` — **KHÔNG đụng `job.actual_cost`** (Job không hề được
  load trong hàm này). `[CHƯA VERIFY]`: không có API key thật trong môi trường dev để xác nhận các
  provider THẬT SỰ trả đúng JSON theo prompt yêu cầu — có fallback parse bằng regex nếu
  `json.loads()` thất bại, nhưng hành vi sống với LLM thật chưa được smoke-test. Ghi rõ trong
  docstring + cần QA chạy live trước khi coi tính năng này "chắc chắn hoạt động".

### Frontend (`web/glossary.html`, `web/js/suggested-terms.js`)

- Section "Các từ mới — Chờ duyệt" mới trong `glossary.html`, Alpine component riêng
  (`suggestedTermsApp()`) độc lập với `glossaryApp()` đã có — sort/min_ngram/include_noise/phân
  trang 50 dòng, checkbox chọn nhiều dòng cho "Gợi ý bản dịch" (có `confirm()` cảnh báo tốn phí
  trước khi gọi, đúng BR-TERM-03), input gõ tay `term_vi` hoặc dùng bản gợi ý LLM trả về.
  "Thêm vào glossary"/"Bỏ qua" gọi đúng 2 endpoint mới.
- Bridge cross-component: `promote()` thành công dispatch `CustomEvent('glossary-entries-changed')`
  trên `window`; `glossaryApp()` lắng nghe event này trong `x-init` để tự `load()` lại — nếu không
  có cầu nối này, bảng glossary chính ở dưới trang sẽ không tự cập nhật sau khi user duyệt 1 từ
  mới (phát hiện được khi tự tay verify UI qua browser, xem mục Verify bên dưới).

### Test

- `tests/test_glossary_matching.py` (9), `tests/test_term_extractor.py` (20),
  `tests/integration/test_term_extraction_service.py` (12),
  `tests/integration/test_suggested_terms_api.py` (10),
  `tests/integration/test_extract_terms_endpoint.py` (3) — tổng 54 test mới.
- Theo đúng Protocol 6 R6-02: test lineage assert **giá trị cụ thể** đọc được (không chỉ
  `assert_called()`), test golden `gluten` (mô phỏng nhỏ, không nhúng nguyên sách — xem "Bản quyền"
  bên dưới) phải sống sót qua nesting collapse đúng quy tắc MAX-not-SUM.
- Gate T8 mục 3 (test với glossary THẬT): `test_real_glossary_114_filters_documented_leak_terms_end_to_end`
  (thuật toán thuần) + `test_extract_and_store_terms_real_glossary_114_end_to_end` (qua DB thật) —
  cả 2 assert `pound`/`ounce`/`bloom`/`tempering`/`kneading`/`teaspoon`/`whipping` KHÔNG lọt vào
  "Chờ duyệt" khi 114 glossary entry thật được áp.
- Dùng fixture Markdown thật `tests/fixtures/mineru/parse_only_txt_figoni25/document.md` (US-15,
  đã có sẵn) để test nhánh HTML-table-stripping trên dữ liệu MinerU thật, đúng gợi ý của brief.
- **Bản quyền**: KHÔNG nhúng bất kỳ đoạn văn bản dài nào trích từ 2 cuốn sách thật (Figoni, Cauvain)
  Domain Expert đã dùng để đo — dù brief khuyến khích "dùng dữ liệu thật thay vì bịa", nhúng nguyên
  trang sách có bản quyền vào git repo là rủi ro thật (khác chuyện self-test cục bộ). Thay vào đó:
  (a) tái sử dụng fixture MinerU đã có sẵn trong repo (không phát sinh rủi ro mới), (b) export
  glossary 114 entry (dữ liệu chức năng của chính team, không phải văn bản sáng tác), (c) câu ví dụ
  tự viết ngắn nhắm đúng từng hiện tượng đã đo (không phải nguyên văn sách). Đã TỰ CHẠY (không nhúng
  vào git) thuật toán trên 2 file PDF thật cục bộ trong `data/uploads/` (gitignored) để xác nhận
  hành vi khớp với số đo của Domain Expert trước khi viết fixture — kết quả khớp (vd `gluten`
  survive nesting collapse, T3 lọc đúng 13 term leak).

### Verify UI thủ công qua browser (không chỉ tin test)

Chạy 1 server riêng trên port 8001 trỏ tới DB SQLite tạm (KHÔNG đụng `data/bb_translation.db` thật
— port 8000 đang có 1 process khác chạy, không tắt/không ghi đè), seed job + suggested_terms giả
qua chính `extract_and_store_terms()`/insert trực tiếp, xác nhận qua trình duyệt thật: trang load
không lỗi console, `GET /api/glossary/suggested` trả 200 với dữ liệu đúng, `promote()`/`dismiss()`
chạy qua Alpine component thật cập nhật đúng UI, và phát hiện + sửa luôn bug thiếu cross-component
refresh (mục Frontend ở trên). Đã dọn dẹp server tạm + thư mục DB tạm sau khi xong.

### Kết quả chạy thật

```
uv run ruff check src/ tests/ web/                                    → All checks passed!
uv run ruff format --check <moi file da sua/them trong session nay>   → đa format
uv run pytest -q                                                       → 518 passed, 1 failed
```

1 test FAIL — **CÙNG 1 test đã biết từ trước** (`tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle`, Bug #8, đang được 1
session/worktree khác sửa song song, không liên quan US-20). Baseline trước session này là 464
passed/1 failed (US-15 §6.21.3 entry ngay trên) → 518-464 = 54 test mới của session này, đúng số
liệu, không có test cũ nào bị vỡ.

### Điểm chưa rõ ràng khi thực sự code — cần Tech Lead/PM xác nhận (không tự đoán, ghi rõ ở đây)

1. **Mâu thuẫn nội tại trong §6.18.8 T3** giữa câu chữ rule ("giữ nội dung ngoặc nếu ≥3 ký tự và
   không phải viết tắt thuần") và chính ví dụ đi kèm (`pound (lb)` giữ `lb` — 2 ký tự; `SMBC` —
   viết tắt thuần) → đã chọn theo ví dụ (luôn giữ), xem `src/core/glossary_matching.py` module
   docstring. Cần Tech Lead xác nhận đây đúng ý định, không phải lỗi đánh máy ở ví dụ.
2. **`data/wordlists/` bị `.gitignore` chặn** — đã đổi sang `src/core/wordlists/` (xem mục thuật
   toán ở trên). Cần Tech Lead xác nhận vị trí mới hoặc chỉ định vị trí khác nếu có lý do khác.
3. **`en_freq_top50k.tsv` chưa ship** — `_specificity()` luôn trả `1.0` (an toàn nhưng chưa tận
   dụng được cải thiện recall Domain Expert đã đo: recall@500 18→24/60). Cần quyết định có tìm/
   soạn nguồn dữ liệu này không, và nếu có thì nguồn nào (bản thân đây sẽ cần ghi "nguồn + ngày
   lấy" theo đúng tinh thần T2 khi được ship).
4. **`suggest-translation` chưa live-verify** — hành vi JSON thật của provider (đặc biệt DeepSeek,
   mặc định) khi nhận prompt yêu cầu JSON chưa được xác nhận bằng lời gọi thật (không có API key
   trong môi trường dev). Có fallback regex nhưng đây KHÔNG thay thế cho verify thật — nên có ít
   nhất 1 smoke test thật trước khi release, đúng tinh thần Protocol 5 R5-03 dù đây không hẳn là
   "external tool contract" theo nghĩa hẹp mà là hành vi prompt-engineering nội bộ dựa trên 1
   external API.

### Trạng thái

Implement xong theo đúng §6.18.8 (không tự suy diễn lại thiết kế, các điểm mâu thuẫn/thiếu rõ ràng
đã liệt kê ở trên thay vì tự đoán). **CHƯA spawn Reviewer** (Protocol 7 R7-01) — KHÔNG được coi là
"xong"/"sẵn sàng" cho tới khi Reviewer thật review xong và ghi vào `docs/review-report.md`.

## Bug #9 — tắt `font_shrink_page()` cho engine `babeldoc` (Dev, 2026-09-08)

Implement đúng thiết kế Tech Lead đã chốt tại `docs/Architecture.md` mục "Bug #9 —
`font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc`" (B9.1–B9.8). Không tự
thiết kế lại — chỉ theo đúng tên thuộc tính, vị trí sửa, và cách xử lý `overflow_entries` Tech Lead
đã quy định.

### Thay đổi

1. `src/services/pdf2zh_runner.py` — thêm `needs_font_shrink: ClassVar[bool] = True` trong
   `class Pdf2zhRunner` (ngay sau docstring class, trước `__init__`) + `from typing import
   ClassVar`.
2. `src/services/babeldoc_runner.py` — thêm `needs_font_shrink: ClassVar[bool] = False` trong
   `class BabeldocRunner` (cùng vị trí tương ứng) + `from typing import ClassVar`.
3. `src/core/job_orchestrator.py`:
   - Thêm property `_needs_font_shrink` ngay sau `_translator_runner` — đọc
     `self._translator_runner.needs_font_shrink`, có `isinstance(value, bool)` guard bắt buộc
     (raise `TypeError` nếu không phải `bool` — chặn đúng bẫy `AsyncMock(spec=...)` không copy giá
     trị class attribute, chỉ copy tên, khiến `mock.needs_font_shrink` là 1 child Mock TRUTHY).
   - Bọc khối `with fitz.open(chunk.output_path): ... doc.saveIncr()` trong
     `if self._needs_font_shrink:`. `overflow_entries: list[OverflowEntry] = []` giữ nguyên khai
     báo BÊN NGOÀI `if` (list rỗng khi skip); vòng lặp ghi `OverflowReport` phía sau **không sửa 1
     ký tự nào** — đúng quyết định Tech Lead ở B9.5 (diff nhỏ nhất, không đụng đường persistence
     đang chạy đúng của pdf2zh).
4. Sửa 7 chỗ tạo mock runner hiện có (đúng danh sách Architecture.md B9.6 mục 4) — mỗi chỗ thêm 1
   dòng `runner.needs_font_shrink = True/False` tương ứng với `spec=Pdf2zhRunner`/`spec=
   BabeldocRunner`: `tests/integration/test_job_cancel.py:76`,
   `tests/integration/test_job_orchestrator_concurrency.py:66`,
   `tests/integration/test_job_orchestrator.py:86,380,443` (→ `True`),
   `tests/integration/test_job_orchestrator.py:507,1005` (→ `False`). Grep xác nhận đây là toàn bộ
   — không còn chỗ nào khác tạo mock của 2 class này trong `tests/`.

### Test mới (R6-02 — assert giá trị/hành vi thật, không chỉ `assert_called()`)

Thêm 3 test trong `tests/integration/test_job_orchestrator.py` (cuối file, mục "Bug #9 —
needs_font_shrink gate"):

- `test_babeldoc_engine_skips_font_shrink_leaves_output_untouched` (T9-1): chạy `run_job()` đầy đủ
  với `pdf_translate_engine="babeldoc"`; assert `chunk.output_path` **byte-identical** (sha256)
  trước/sau bước post-processing, và `SELECT COUNT(*) FROM overflow_reports WHERE job_id=...` ==
  0. Có thêm 1 spy (`wraps=` lên `font_shrink_page` thật, không thay hành vi) làm bằng chứng bổ
  sung (`assert_not_awaited()`) — nhưng assertion CHÍNH là hash + đếm DB, đúng yêu cầu B9.6
  "không dùng assert_called()".
- `test_pdf2zh_engine_still_runs_font_shrink_regression` (T9-2): cùng input, engine `pdf2zh`;
  spy `wraps=` lên `font_shrink_page` thật, assert `await_count` khớp đúng số lần thực tế (số
  chunk × số trang gốc, tính từ chunk thật sinh ra sau khi chạy — không hardcode) để chứng minh
  bước này **vẫn chạy** cho pdf2zh, không bị fix này vô tình tắt luôn.
- `test_needs_font_shrink_property_isinstance_guard_catches_unset_mock` (T9-3): `AsyncMock(spec=
  BabeldocRunner)` **không** set `needs_font_shrink` (mô phỏng đúng lỗi "quên set") → property
  phải raise `TypeError` nhờ `isinstance` guard, không bị Mock truthy đánh lừa. Đã tự verify bằng
  cách tạm bỏ guard trong `job_orchestrator.py`, chạy lại thấy test này FAIL đúng như kỳ vọng, rồi
  khôi phục guard nguyên trạng.

### Live smoke (không cần live babeldoc/pdf2zh subprocess — không có mạng/API key trong môi trường
dev, xem script `bug9_live_smoke.py` trong scratchpad session)

Chạy trực tiếp đúng đoạn code vừa thêm (`if needs_font_shrink: with fitz.open(...): ... saveIncr()`)
trên **`tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf`** — 1 PDF thật (không phải file
`fitz.open()` sinh từ đầu trong test), để loại rủi ro "PDF đơn giản không đại diện layout thật":

- `needs_font_shrink=False` (mô phỏng babeldoc): sha256/size/mtime file **giống hệt** trước và sau
  — khối code không hề chạy.
- `needs_font_shrink=True` (mô phỏng pdf2zh): khối code chạy thật trên 2 trang PDF thật, không
  crash; `doc.saveIncr()` khiến hash đổi (dù 0 overflow entries) — xác nhận nhánh pdf2zh vẫn thực
  thi bình thường trên 1 PDF layout thật, không chỉ trên PDF `fitz`-toy sinh trong unit test.

### Kết quả chạy thật

```
uv run ruff check src/services/pdf2zh_runner.py src/services/babeldoc_runner.py \
  src/core/job_orchestrator.py tests/integration/test_job_orchestrator.py \
  tests/integration/test_job_cancel.py tests/integration/test_job_orchestrator_concurrency.py
  → All checks passed!
uv run ruff format --check <6 file trên>          → đã format
uv run pytest tests/integration/test_job_orchestrator.py -q   → 37 passed
uv run pytest tests/test_pdf2zh_runner.py tests/test_font_shrink.py \
  tests/integration/test_job_cancel.py tests/integration/test_job_orchestrator_concurrency.py -q
  → 30 passed
uv run pytest tests/test_babeldoc_runner.py -q     → 24 passed
uv run pytest tests/ -q                            → 521 passed, 1 failed
```

1 test FAIL trong full suite: `tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle` — **KHÔNG liên quan Bug #9**
(Dev không đụng `rotated_text_overlay.py`/`font_shrink.py`/`pdf_coords.py` trong task này). Đã xác
nhận qua `docs/CHANGELOG.md` mục US-20 ngay phía trên: đây là 1 test đã biết đang được 1 session/
worktree khác sửa song song (liên quan Bug #8). Không tự ý sửa file ngoài phạm vi Bug #9.

### Điểm khác thiết kế Tech Lead — không có

Đã đối chiếu từng dòng với B9.3/B9.4/B9.5: đúng tên thuộc tính `needs_font_shrink`, đúng vị trí
(`pdf2zh_runner.py` giữa docstring/`__init__`, `babeldoc_runner.py` tương tự, property ngay sau
`_translator_runner`, wrap đúng khối `with fitz.open(...)`), đúng cách giữ nguyên
`overflow_entries`/vòng lặp `OverflowReport` bên ngoài `if`. Không phát hiện sai khác nào cần
escalate.

### Trạng thái

Implement xong theo đúng Bug #9 B9.1–B9.6 (không tự suy diễn lại thiết kế). **CHƯA spawn Reviewer**
(Protocol 7 R7-01) — KHÔNG được coi là "xong"/"sẵn sàng" cho tới khi Reviewer thật review xong và
ghi vào `docs/review-report.md`.

---

## US-21 — Hiển thị phiên bản BB-Translation (2026-09-09)

Implement theo `docs/Architecture.md` §6.19 và `docs/PRD.md` US-21. Backend `GET /api/version`
đã có sẵn và đúng từ trước, task này **chỉ frontend** (theo brief PM — S21-1, sửa
`FastAPI(..., version=...)` hardcode `0.1.0` khỏi khớp OpenAPI, KHÔNG nằm trong phạm vi task này,
xem mục "Điểm cần PM/Tech Lead xác nhận thêm" bên dưới).

### Thay đổi

- **`web/js/version.js` (mới)**: 1 đoạn JS thuần (không phụ thuộc Alpine) dùng chung cho cả 4
  trang tĩnh — gọi `GET /api/version` đúng 1 lần khi trang load, điền vào
  `<span id="app-version">`. Lỗi mạng hoặc version rỗng/`"unknown"` → để trống lặng lẽ (`catch`
  rỗng), không throw, không chặn phần còn lại của trang — đúng S21-2.
- **`web/index.html`, `web/glossary.html`, `web/history.html`, `web/settings.html`**: thêm
  `<span id="app-version">` cạnh chữ "BB-Translation" trong nav bar (style nhỏ,
  `text-xs font-normal text-gray-400`, không làm rối nav hiện có); include
  `<script src="/js/version.js">` trước script riêng của từng trang.
- **`web/index.html` + `web/js/app.js`**: xoá phần hiển thị version cũ ở **footer** của riêng
  `index.html` (`appVersion`/`loadVersion()` trong `translationApp()`) — implementation cũ này đã
  tồn tại từ trước (comment "US moi 2026-09-06") nhưng đặt sai vị trí theo AC US-21 (footer thay
  vì nav bar) và chỉ có ở 1/4 trang, không phải "1 đoạn JS dùng chung" như Architecture §6.19 yêu
  cầu. Gộp về `version.js` để tránh 2 cơ chế fetch `/api/version` song song trên cùng 1 trang.

### Điểm cần PM/Tech Lead xác nhận thêm

Architecture.md §6.19 mục **S21-1** (đánh dấu "bắt buộc") yêu cầu sửa
`FastAPI(title="BB-Translation", version="0.1.0", ...)` trong `src/api/main.py` thành
`version=_read_app_version()` vì `0.1.0` hardcode đang lệch với `1.2.8` thật (hiện ra sai trên
`/docs` OpenAPI). Brief PM cho task này ghi rõ "KHÔNG sửa backend vì GET /api/version đã hoạt
động đúng" — Dev tuân theo brief, **chưa sửa S21-1**. Ghi nhận lại ở đây để PM đối chiếu: S21-1
có vẻ nằm trong phạm vi Architecture §6.19 nhưng brief loại trừ backend; cần PM xác nhận có làm
trong 1 task riêng hay bổ sung vào task này.

### Verify qua browser thật

Mở `http://localhost:8000` (dev server đang chạy sẵn từ 1 session song song, không tự khởi động
server mới) qua Browser pane, xác nhận cả 4 trang (`index.html`, `glossary.html`, `history.html`,
`settings.html`) đều hiện **"BB-Translation v1.2.8"** ở nav bar — khớp `pyproject.toml` (`version
= "1.2.8"`). Không thấy lỗi console, không thấy "unknown"/trống.

### Kết quả chạy thật

```
uv run ruff check .   → All checks passed!
uv run pytest -q      → 521 passed, 1 failed (0:01:46)
```

1 test FAIL: `tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle` — khớp baseline đã ghi nhận ở
mục Bug #9 ngay phía trên (không liên quan US-21, Dev không đụng
`rotated_text_overlay.py`/`font_shrink.py`/`pdf_coords.py`/`glossary_manager.py`/
`job_orchestrator.py`/`babeldoc_runner.py`/`pdf2zh_runner.py`/`searchable_pdf.py` trong task này).

### File đã sửa

`web/js/version.js` (mới), `web/index.html`, `web/glossary.html`, `web/history.html`,
`web/settings.html`, `web/js/app.js`.

### Trạng thái

Implement xong theo đúng US-21 + Architecture §6.19 (trừ S21-1, xem mục trên). **CHƯA spawn
Reviewer** (Protocol 7 R7-01) — KHÔNG được coi là "xong"/"sẵn sàng" cho tới khi Reviewer thật
review xong và ghi vào `docs/review-report.md`.

### Bổ sung — S21-1 (backend, lượt sau)

`src/api/main.py:85` — sửa `FastAPI(title="BB-Translation", version="0.1.0", lifespan=lifespan)`
thành `version=_read_app_version()` (hàm đã có sẵn, định nghĩa dòng 64-76, đứng trước dòng khởi
tạo `app = FastAPI(...)` nên không cần đổi thứ tự). Giải quyết đúng phần S21-1 còn ghi nhận ở
mục "Điểm cần PM/Tech Lead xác nhận thêm" phía trên. Verify: `uv run ruff check .` → All checks
passed; `uv run pytest -q` → 521 passed, 1 failed (khớp baseline, fail cũ ở
`test_rotated_text_overlay.py`, không liên quan). Restart dev server thật, mở `/docs` qua Browser
pane → heading hiện đúng "BB-Translation 1.2.8 OAS 3.1" (khớp `GET /api/version` = `1.2.8`, không
còn `0.1.0`). File đã sửa: `src/api/main.py`. **CHƯA spawn Reviewer** — chưa được coi là xong.

## US-17 + US-18 — Glossary: thêm từ mới có xác nhận ghi đè, search server-side (2026-09-09)

Implement theo Architecture.md §6.16 (đã qua Human Checkpoint 2), theo đúng brief PM — không tự
suy diễn lại thiết kế.

### US-17 — nút "Thêm từ mới" + BR-GLOSS-07 (xác nhận ghi đè)

- `src/api/routes/glossary.py`:
  - `GlossaryEntryIn` thêm field `force: bool = False` (opt-in tường minh cho đúng 1 request, cùng
    kỷ luật `confirm_cost` của cost gate §6.11.4 Lop 2).
  - `GlossaryConflictInfo` model mới (`entry_id`, `term_en`, `term_vi`, `notes`, `updated_at`).
  - `create_entry()`: nếu `term_en` trùng (case-insensitive, `GlossaryManager.get_entry()`, đúng
    BR-GLOSS-02) và `force=False` → raise `HTTPException(409, detail={...})` theo đúng idiom
    `gate_error_detail()` đã có sẵn ở `src/core/cost_gate.py` (dict `detail=` với 3 key `detail`/
    `existing`/`requires_confirmation`, KHÔNG ghi gì vào DB). `force=True` → giữ nguyên
    `bulk_import()` 1 phần tử (BR-GLOSS-03 last-updated-wins) + `logger.info` ghi lại giá trị cũ bị
    ghi đè. Phạm vi CHỈ áp dụng luồng thêm-1-entry-đơn-lẻ — `bulk_import()` qua
    `/import/confirm` (Excel hàng loạt) giữ nguyên hành vi ghi đè âm thầm, đúng PRD.
  - **Lưu ý kỹ thuật khi implement** (không có trong §6.16, tự phát hiện khi code): FastAPI/
    Starlette KHÔNG chạy `jsonable_encoder` lên `HTTPException.detail` (dùng `json.dumps` thẳng) —
    nếu truyền thẳng instance `GlossaryConflictInfo` (có field `datetime`) vào `detail=`, request
    sẽ crash 500 ở tầng serialize thay vì trả 409. Phải gọi `.model_dump(mode="json")` trước khi
    đưa vào dict `detail=`. Đã verify bằng cách đọc source `fastapi.exception_handlers.
    http_exception_handler` thật trong `.venv` (fastapi 0.141.1) — không suy đoán.
  - `promote_suggested_term()` (US-20): wire `force=request.force` xuống `GlossaryEntryIn` khi gọi
    `create_entry()` — field `force` trên `SuggestedTermPromoteRequest` đã tồn tại sẵn từ US-20
    nhưng trước đây chưa có tác dụng gì (comment cũ ghi rõ "chờ US-17"). Nếu KHÔNG wire, promote 1
    suggested term trùng `term_en` với glossary entry có sẵn sẽ vỡ (đổi từ ghi-đè-im-lặng sang
    HTTP 409 mà không có đường nào cho client xác nhận) — đây là thay đổi ngoài phạm vi liệt kê
    tường minh trong brief PM (chỉ nói sửa `create_entry()`), làm vì cần thiết để không phá hành
    vi US-20 hiện có; nêu rõ ở đây để PM/Reviewer biết, không âm thầm mở rộng phạm vi.
- `web/glossary.html` + `web/js/glossary.js`: nút "+ Thêm từ mới", modal nhập `term_en` (bắt
  buộc)/`term_vi`/`notes`, gọi `POST /api/glossary`. Khi nhận 409 → hiện `detail.existing` +
  message xác nhận, nút "Ghi đè" gọi lại với `force=true`. Modal dùng `x-cloak` (rule đã có sẵn ở
  `web/css/style.css`), không xung đột layout với khu vực "Chờ duyệt" (US-20).

### US-18 — search trong Glossary

- `GET /api/glossary` thêm param `q: str | None`. Filter: `col(GlossaryEntry.term_en).contains(q,
  autoescape=True) | col(GlossaryEntry.term_vi).contains(q, autoescape=True)` — đúng theo
  Architecture §6.16.2 đã chốt (KHÔNG dùng `.ilike()`, lý do đã ghi rõ trong Architecture: `.ilike`
  vô hiệu hoá index qua `lower()` quanh cột mà không giải quyết được hạn chế tiếng Việt có dấu;
  `autoescape=True` bắt buộc để escape `%`/`_` — thiếu escape thì `q="_"` trả cả bảng).
  `search_clause` là 1 biến duy nhất áp cho cả `count_statement` lẫn `list_statement` (tránh lệch
  `total` với số dòng trả về khi thêm filter mới vào query có sẵn 2 statement riêng).
  `q` AND với `scope` hiện có (không ghi đè nhau).
- `web/js/glossary.js`: state `searchQuery`, input `@input` debounce 250ms qua `onSearchInput()`
  (reset `offset = 0` trước khi `load()`), cộng dồn với `scopeFilter` trong cùng query string.

### Test (`tests/integration/test_glossary_api.py`, `tests/integration/test_suggested_terms_api.py`)

R6-02 — assert giá trị cụ thể, không chỉ status code:
- Thêm entry mới thành công (đã có sẵn từ trước, không đổi).
- Trùng `term_en` khác hoa/thường không `force` → 409, `detail.existing` đúng entry cũ, GET lại
  glossary xác nhận `total` và `term_vi`/`notes` KHÔNG đổi (không chỉ tin status code).
- `force=true` sau 409 → ghi đè thành công, `id` giữ nguyên, `term_vi` cập nhật.
- Search theo `term_en`, theo `term_vi`, không khớp gì (`total=0`, `entries=[]`), kết hợp `scope`
  (bao gồm case `scope` không khớp gì → loại hết, chứng minh AND không OR).
- `q="50%"` và `q="_"` (escape wildcard — nếu thiếu escape, `q="_"` sẽ trả cả bảng).
- `q=""` (chuỗi rỗng) → trả lại toàn bộ danh sách, không lọc.
- Sửa test cũ `test_create_single_entry_updates_existing_duplicate` (giả định ghi-đè-im-lặng
  không còn đúng nữa) thành `test_create_single_entry_force_true_updates_existing_duplicate`
  (thêm `force: True` vào request).
- `test_suggested_terms_api.py`: 2 test mới cho việc wire `force` qua `promote()` — trùng term
  không `force` → 409 + suggested term vẫn `pending` (không bị đánh dấu `added`) + glossary entry
  cũ không đổi; có `force=true` → ghi đè thành công + đánh dấu `added`.

### Kết quả chạy thật

```
uv run ruff check src/api/routes/glossary.py tests/integration/test_glossary_api.py \
  tests/integration/test_suggested_terms_api.py   → All checks passed!
uv run pytest -q   → 531 passed, 1 failed (0:01:46)
```

1 test FAIL: `tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle` — khớp đúng baseline Bug #9 đã
ghi nhận trước đó (không liên quan task này). +10 test so với baseline 521 passed (8 test mới
trong `test_glossary_api.py` sau khi thay 1 test cũ, 2 test mới trong `test_suggested_terms_api.py`).

### File đã sửa

`src/api/routes/glossary.py`, `web/glossary.html`, `web/js/glossary.js`,
`tests/integration/test_glossary_api.py`, `tests/integration/test_suggested_terms_api.py`.

Không đụng: `src/core/glossary_manager.py`, `src/core/job_orchestrator.py`,
`src/postprocess/font_shrink.py`/`rotated_text_overlay.py`, `src/preprocess/searchable_pdf.py`,
`src/services/babeldoc_runner.py`/`pdf2zh_runner.py`, `src/babeldoc_shim/*`, `CLAUDE.md`,
`docs/Architecture.md` — đúng theo brief (các file này đang được sửa song song ở session khác).

### Điểm cần PM xác nhận / không rõ khi code (không tự đoán)

1. **Wire `force` xuống `promote_suggested_term()`** (nêu ở mục US-17 trên) — Architecture §6.16
   không nhắc tới `promote_suggested_term()`, brief PM cũng không liệt kê việc này tường minh.
   Dev tự quyết định wire vì nếu không làm, hành vi US-20 hiện có (ghi đè im lặng khi promote 1
   suggested term trùng term) sẽ vỡ ngay khi `create_entry()` đổi sang raise 409. Xin PM xác nhận
   quyết định này đúng ý, hoặc chỉ định lại nếu muốn xử lý khác.
2. Message lỗi 409 hiển thị cho user dùng `existing.term_vi or '(chua co)'` khi entry cũ chưa có
   bản dịch VI (Architecture §6.16.3 ví dụ message không có nhánh này) — tự quyết định hợp lý,
   không phải suy đoán về contract external tool nên không cần `[CHƯA VERIFY]`, nhưng nêu ra để PM
   biết đây là 1 lựa chọn UX nhỏ Dev tự thêm.
3. Ngoài 2 điểm trên, §6.16 mô tả đủ chi tiết (kể cả đoạn code mẫu gần như copy được thẳng) —
   không phát sinh điểm mập mờ nào khác cần escalate.

### Trạng thái

Implement xong theo đúng US-17 + US-18 + Architecture §6.16. **CHƯA spawn Reviewer** (Protocol 7
R7-01) — KHÔNG được coi là "xong"/"sẵn sàng" cho tới khi Reviewer thật review xong và ghi vào
`docs/review-report.md`.

---

## US-17 + US-18 — vòng sửa 2/3 (Dev↔Reviewer) theo yêu cầu REJECT của Reviewer

Sửa theo `docs/review-report.md` (section "US-17 + US-18" ở trên, mục 6 blocking + mục 7
non-blocking).

### Blocking (mục 6) — `web/js/suggested-terms.js::promote()` không tiêu thụ được 409/`force`

Copy đúng pattern retry-with-force đã có ở `web/js/glossary.js::submitAdd()`, khác biệt duy nhất:
`glossaryApp()` có 1 modal đơn (`showAddModal`) nên chỉ cần 1 biến `addConflict`; `suggestedTermsApp()`
là 1 bảng nhiều dòng nên dùng `promoteConflict = { termId, message, existing } | null` để biết
đúng dòng nào đang cần xác nhận ghi đè, tránh hiện nhầm confirm cho dòng khác khi có > 1 conflict
cùng lúc trên trang.

- `promote(term, force = false)` — luôn gửi `force` trong body (trước đây không bao giờ gửi).
  Khi `res.status === 409`, đọc `body.detail.existing`/`body.detail.detail` (object, đúng shape
  `GlossaryConflictInfo` mà `create_entry()` trả — KHÔNG còn `alert(body.detail)` render
  `"[object Object]"` nữa) và lưu vào `promoteConflict` thay vì alert ngay.
- `cancelPromoteConflict()` — huỷ, xoá `promoteConflict`.
- `load()`: nếu `promoteConflict` đang trỏ tới 1 `termId` không còn trong trang hiện tại (đã bị
  promote/dismiss ở nơi khác, hoặc đổi trang), tự xoá — tránh state cũ trỏ tới dòng không tồn tại.
- `web/glossary.html`: 2 `<template x-if>` trong ô nút của mỗi dòng — nút "Thêm vào
  glossary"/"Bỏ qua" bình thường khi không có conflict cho dòng đó; khối xác nhận (message + nút
  "Ghi đè" gọi `promote(term, true)` / "Hủy" gọi `cancelPromoteConflict()`) khi có, cùng style
  amber-50/amber-200 với modal của `glossaryApp()` để nhất quán UI.

### Non-blocking (mục 7) — pre-fill `term_vi`/`notes` cũ khi "Ghi đè" qua modal `glossary.js`

Sửa luôn (đơn giản, đúng như Reviewer gợi ý):
- `submitAdd()`: khi nhận 409, nếu `addForm.term_vi`/`notes` đang rỗng (user chưa tự gõ gì) thì
  pre-fill từ `detail.existing` — giữ nguyên nếu user đã gõ, không ghi đè lựa chọn của user.
- `glossary.html`: hiện thêm dòng "Ghi chú cũ: ..." trong khối xác nhận (trước đây `notes` cũ
  hoàn toàn không hiển thị ở đâu) + 1 dòng nhắc "Trường trên đã được điền theo giá trị cũ — sửa
  lại trước khi ghi đè nếu cần" để user biết form đã tự điền, không phải để trống.

Không đổi backend (`create_entry()`/`bulk_import()`) — đúng như Reviewer xác nhận "không cần đổi
backend".

### Kết quả chạy thật

```
uv run ruff check .   → All checks passed!
uv run pytest -q      → 531 passed, 1 failed (117.10s)
```

1 test FAIL: `tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle` — khớp đúng baseline Bug #9,
không liên quan. Không có regression mới so với vòng 1.

### File đã sửa (vòng này)

`web/js/suggested-terms.js`, `web/js/glossary.js`, `web/glossary.html`.

Không đổi file backend/test nào ở vòng này (đúng brief — chỉ frontend). Không đụng
`glossary_manager.py`, `job_orchestrator.py`, `font_shrink.py`, `rotated_text_overlay.py`,
`searchable_pdf.py`, `babeldoc_runner.py`, `pdf2zh_runner.py`, `babeldoc_shim/*`, `CLAUDE.md`,
`Architecture.md` — đang sửa song song ở session khác.

### Trạng thái

**Circuit breaker Dev↔Reviewer: 2/3 vòng đã dùng.** Đã sửa cả blocking (mục 6) lẫn non-blocking
(mục 7). **CHƯA spawn Reviewer lại** (Protocol 7 R7-01) — chưa được coi là "xong", chờ Reviewer
duyệt lại vòng 2.

## Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (fix `_get_width_before_next_break_point`
đếm đôi bề rộng unit hiện tại) — implement + spike A/B song (2026-09-09)

Theo đúng thiết kế Tech Lead đã chốt (`docs/Architecture.md` mục "Bug #10 — babeldoc cắt ngang từ
tiếng Việt giữa chừng ... thiết kế bản vá (Tech Lead, 2026-09-09)", BA10.1→BA10.10). Dev **không**
tự điều tra lại root cause — chỉ tự làm spike A/B sống (R5-02) trước khi implement đầy đủ, đúng
yêu cầu vì đây là patch mới vào `typesetting.py` (khác 3 patch Bug #7 đều ở `paragraph_finder.py`,
chưa từng được project verify sống).

### 1. Spike A/B (BA10.5, R5-02) — kết quả 5 gate

Phương pháp: chạy babeldoc 0.6.4 THẬT (không mock) 2 lần trên
`tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf` (trang 39, 0-based, trích từ
`Le-Cordon-Bleu-Patisserie-and-Baking-Foundations`, xác nhận đúng chứa case "loyal employees" →
"nhân viên trung thành" bị cắt) qua chính `BabeldocRunner` production, KHÔNG `--ignore-cache` ở
lần 2 (cache DeepSeek nạp ở lần 1) — đảm bảo văn bản tiếng Việt giống hệt nhau giữa 2 lần, mọi khác
biệt quan sát được thuần layout. 3 fixture đối chứng (`page14_numbered_list_source.pdf`,
`toc_sources/lcb_toc.pdf` 2 trang, `toc_sources/figoni_p25_recipe.pdf`) chạy A/B tương tự.

| Gate | Kết quả |
|---|---|
| **G1** (đích) | **PASS**. Baseline: `"...có động lực và t\nrung thành..."` (cắt giữa từ, xác nhận bằng cách `"trung"` không xuất hiện liền mạch trong text trích bằng `pymupdf` — dấu hiệu chính xác của bug). Patched: `"...và trung \nthành..."` — từ "trung" giữ nguyên vẹn. Bonus case tự phát hiện: `"chịu trách nhiệm"` (baseline cắt thành `"nhiệ\nm"`, patched giữ nguyên). |
| **G2** (tràn ngang) | Ngưỡng chữ ("không lớn hơn quá 0.5pt") **KHÔNG đạt theo nghĩa đen**: `max(bbox.x2)` toàn trang tăng +3.04pt→+10.94pt trên bug10-page + cả 3 fixture đối chứng (0.00pt trên figoni). Điều tra thêm: đây đúng là hệ quả BA10.4 điểm 4 Tech Lead đã dự đoán (scale chỉ có thể TĂNG → dòng dùng hết box sát hơn, không bao giờ vượt). Xác nhận bằng 3 cách: (a) đọc lại source xác nhận nhánh (A) `current_x+unit_width>box.x2` trong `_layout_typesetting_units` hoàn toàn không bị đụng bởi patch; (b) `box.x2` thật của paragraph bug (dump sống) = 590.914pt, mọi mép phải quan sát được (tối đa 567.94pt) vẫn còn cách biên ít nhất ~23pt trên MỌI trang; (c) bằng chứng G3 (số dòng chỉ giảm/giữ nguyên) nhất quán với "dùng hết chỗ trống", không phải tràn. **Escalate finding này cho Tech Lead/PM xác nhận** (không tự ý coi là pass) — nhưng đây KHÔNG phải điều kiện dừng cứng như G3. |
| **G3** (số dòng) | **PASS** trên cả 5 trang đo (bug10 page, toc p1/p2, numbered_list, figoni_recipe) — sau vá `<=` trước vá mọi nơi, giảm thật trên 2 trang TOC. |
| **G4** (hiệu năng) | **PASS** qua microbenchmark trực tiếp hàm bị patch (đo cả pipeline nhiễu quá lớn do LLM/network — đã thử và bỏ). Bản patch (generator, early-exit) tốn thêm +10.6% so với hàm gốc trên paragraph 4000-unit (giả lập worst-case), trong ngưỡng 20%. Đối chứng: bản patch NGÂY THƠ (list-comprehension vật chất hoá toàn bộ `typesetting_units[i:]`, đúng thứ Tech Lead cảnh báo tránh) tốn +1336% — xác nhận thiết kế nhận `Iterable` (không phải `Sequence`) trong `word_wrap.py` là bắt buộc, không phải tối ưu sớm thừa thãi. |
| **G5** (không mất chữ) | **PASS** trên cả 5 trang — số ký tự non-whitespace giống hệt trước/sau (khác biệt duy nhất là whitespace/xuống dòng do reflow). |

Golden fixture unit-level (BA10.6, dump từ chính lần chạy babeldoc thật — không gõ tay):
`tests/fixtures/babeldoc/bug10_wrap/lcb_p39_trung_thanh_units.json`. Khớp CHÍNH XÁC với ví dụ minh
hoạ của Tech Lead (BA10.4 đính chính #2): tại ký tự `'r'`, công thức đã vá cho `587.06 <= 590.91`
(box.x2), công thức gốc (đếm đôi) cho `591.31 > 590.91` — đúng là điểm quyết định wrap sai chỗ.

### 2. Implementation

- `src/babeldoc_shim/word_wrap.py` (module mới): `width_before_next_break_point(units, scale)`
  nhận `Iterable[tuple[float, bool]]` (KHÔNG phải `Sequence`) — giữ đúng early-exit O(k) của hàm
  gốc babeldoc, tránh O(n²) khi bị gọi lại cho mọi chỉ số `i` (xem G4).
- `src/babeldoc_shim/sitecustomize.py`: thêm `_TYPESETTING_MODULE_NAME`, cờ
  `_word_wrap_fix_enabled()` (mặc định `"1"` — BẬT), `_build_patched_get_width_before_next_break_point`
  + `_apply_typesetting_patch` (module/loader RIÊNG, rollback ĐỘC LẬP với 3 patch Bug #7 — BA10.7
  ràng buộc #1). Generic hoá `_ParagraphFinderPatchFinder` → `_ModulePatchFinder` +
  `_PatchingLoader` (tham số hoá `apply_patch`/`label`), tách `_apply_patch` cũ →
  `_apply_paragraph_finder_patch`, thêm helper `_install_patch_hook()` dùng chung cho cả 2 module.
  Toàn bộ test Bug #7 cũ (109 test) vẫn PASS sau khi generic hoá.
- Wiring flag `BABELDOC_SHIM_WORD_WRAP_FIX`/`babeldoc_word_wrap_fix_enabled` (mặc định `True` —
  fix số học, không phải heuristic cần tune, khác TOC-1 v2) qua `src/core/config.py` →
  `src/services/babeldoc_runner.py` (`word_wrap_fix_enabled` param, default `False` khi khởi tạo
  trực tiếp) → `src/core/job_orchestrator.py`.

### 3. Test

- `tests/test_babeldoc_word_wrap.py` (8 test): golden-fixture test khớp chính xác ví dụ Tech Lead
  (587.06/590.91) + 6 case biên (list rỗng, `can_break_line=True` ở unit đầu, từ dài không có break
  point, scale≠1.0, loại trừ unit hiện tại khỏi tổng, nhận generator lười không phải list).
- `tests/test_babeldoc_shim_word_wrap_patch.py` (11 test): thực thi THẬT `_apply_typesetting_patch`
  trên class giả (bật/tắt qua env đúng công thức fixed/original), `AttributeError` khi thiếu
  method, rollback độc lập giữa 2 loader qua `_PatchingLoader` generic, `_ModulePatchFinder` chỉ
  can thiệp đúng 1 target, và 4 tổ hợp bật/tắt độc lập TOC-1 v2 × word-wrap fix.
- `tests/test_babeldoc_runner.py`: 3 test mới cho wiring env var (`"1"`/`"0"`/vắng mặt khi
  `line_split_shim_enabled=False`).

### Kết quả chạy thật

```
uv run ruff check src/ tests/         → All checks passed!
uv run ruff format --check <files>    → 8 files already formatted
uv run pytest tests/ -q               → 553 passed, 1 deselected (104.03s)
```

1 test deselect: `tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle` — FAIL kể cả sau `git stash`
(revert toàn bộ thay đổi Bug #10) → xác nhận PRE-EXISTING, thuộc về công việc glossary/UI đang sửa
song song ở session khác (không đụng `babeldoc_shim`/`babeldoc_runner`/`job_orchestrator`), không
liên quan Bug #10. Không có regression mới.

### File đã sửa/thêm

Mới: `src/babeldoc_shim/word_wrap.py`, `tests/test_babeldoc_word_wrap.py`,
`tests/test_babeldoc_shim_word_wrap_patch.py`, `tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf`,
`tests/fixtures/babeldoc/bug10_wrap/lcb_p39_trung_thanh_units.json`.

Sửa: `src/babeldoc_shim/sitecustomize.py`, `src/core/config.py`, `src/services/babeldoc_runner.py`,
`src/core/job_orchestrator.py`, `tests/test_babeldoc_runner.py`.

Không đụng `web/*`, `glossary_manager.py`, `rotated_text_overlay.py`, `searchable_pdf.py`,
`pdf2zh_runner.py`, `font_shrink.py` — đang sửa song song ở session khác (US-17/US-18).

### Trạng thái

**CHƯA spawn Reviewer** (Protocol 7 R7-01) — PM sẽ giao Reviewer riêng. Đặc biệt cần Reviewer xác
nhận lại finding G2 (không phải điều kiện dừng cứng nhưng KHÔNG tự ý coi là pass) trước khi bật
`babeldoc_word_wrap_fix_enabled=True` lên production thật.

## US-19 — Lịch sử: thời gian dịch + số trang, bỏ nút "+ Glossary" trùng chức năng (Dev, 2026-09-09)

Theo đúng thiết kế đã chốt ở Architecture.md §6.17 (Human Checkpoint 2 đã qua) — không tự suy diễn
lại. §6.17.1 xác định `Job.completed_at`/`Job.updated_at` KHÔNG dùng được làm mốc kết thúc chung
(chỉ gán khi thành công; `updated_at` có thể đứng yên bằng `created_at` nếu job fail ở chunk đầu —
"thời gian dịch ~ 0 giây" cho job đã chạy rất lâu rồi mới chết) → cần cột `Job.finished_at` mới.

### 1. Schema

- `src/models/job.py`: thêm `Job.finished_at: datetime | None` — mốc KẾT THÚC chung cho MỌI trạng
  thái cuối (completed/failed/cancelled/cost_capped), tách biệt với `completed_at` (giữ nguyên
  nghĩa "hoàn tất THÀNH CÔNG", vẫn là dữ liệu nghiệp vụ của duplicate-detection AC-12.2 + hậu tố
  tên file tải về — không nạp thêm nghĩa vào cột này).
- `src/models/database.py`: thêm `("jobs", "finished_at", "DATETIME")` vào `_NEW_NULLABLE_COLUMNS`
  — dùng đúng cơ chế `_add_missing_columns()` idempotent đã có (như `chunk_size_used`/
  `parse_method`), **KHÔNG xoá/tạo lại DB** — DB dev hiện có 9 job/114 glossary entry thật được
  giữ nguyên.

### 2. `job.finished_at = datetime.now(UTC)` tại các điểm thoát

Architecture.md §6.17.2 liệt kê 7 điểm ("Step 4/7/Lớp 3/cancel/Step 8/Step 10" trong `run_job()` +
`_run_job_background()`'s last-resort guard). Đọc kỹ toàn bộ `job_orchestrator.py`/`jobs.py` phát
hiện danh sách đó **thiếu 5 điểm thoát** khác cũng chuyển job sang trạng thái cuối — đã bổ sung
đủ cả 12 điểm (không tự ý đổi thiết kế, chỉ hoàn thiện đúng theo Ý ĐỊNH đã nêu rõ trong chính
docstring `Job.finished_at`: "MỌI trạng thái cuối"):

1. `run_job()` Step 4 — `UnsupportedForPdfPipelineError` → failed
2. `run_job()` Step 7 — chunk exception → failed
3. `run_job()` Lớp 3 — cost_capped
4. `run_job()` — graceful cancel
5. `run_job()` Step 8 — merge except → failed
6. `run_job()` Step 10 — completed (= `job.completed_at`)
7. `run_parse_only()` — `MinerUCancelledError` → cancelled
8. `run_parse_only()` — except → failed
9. `_run_parse_only_pipeline()` — completed (= `job.completed_at`)
10. **[không có trong §6.17.2]** `BatchOrchestrator._run_one()` — nhánh `already_capped` (job chưa
    từng chạm `run_job()` vì batch đã vượt trần TRƯỚC lượt của nó)
11. **[không có trong §6.17.2]** `BatchOrchestrator._run_one()` — `except Exception` (BR-BATCH-01
    failure isolation: `run_job()` tự nó raise ra ngoài, khác với nhánh nội bộ #2/#5 đã tự bắt)
12. `jobs.py::_run_job_background()` — last-resort guard (có trong §6.17.2, xác nhận đúng)

### 3. Tầng response (`src/api/routes/jobs.py`)

- `JobDetail` thêm `total_pages`, `started_at`, `finished_at`, `duration_seconds` — tất cả
  optional/default `None` (cùng kỷ luật backward-compatible với `ocr_confidence`/
  `cancel_requested`).
- `_to_detail()`: `duration_seconds = (finished_at or completed_at) - created_at`, CHỈ tính khi có
  mốc kết thúc VÀ `status` thuộc `{completed, failed, cancelled, cost_capped}` — job đang chạy trả
  `None` (BR-HIST-02). BR-HIST-01: mốc bắt đầu là `created_at`, KHÔNG `started_at` (giữ đúng quyết
  định PM/Tech Lead — `started_at` gán SAU OCR nên bỏ sót đoạn chờ dài nhất của job pdf_scan).
  EC-19.1: hàng cũ (`finished_at` NULL) fallback `completed_at`; cả hai NULL → `None`, KHÔNG đoán
  bằng `updated_at`.

### 4. Frontend (`web/history.html`, `web/js/history.js`)

- Thêm 2 cột "Số trang" (`formatTotalPages()`, "-" khi NULL) và "Thời gian dịch"
  (`formatDuration()`, format "X phút Y giây" từ `duration_seconds` giây float do backend trả,
  "-" khi job đang chạy).
- Bỏ nút "+ Glossary" khỏi mỗi dòng (BR-HIST-03) + toàn bộ code JS liên quan (`openAddGlossary()`,
  `saveGlossaryTerm()`, state `addGlossaryJob`/`glossaryDraft`/`glossaryError`) và modal HTML tương
  ứng — đã verify không còn nơi nào khác trong `web/`/tests dùng các symbol này trước khi xoá. Nút
  "Xoá job" giữ nguyên (BA đã đính chính: user không nói về nút này).

### 5. Test (Protocol 6 R6-02 — assert giá trị cụ thể, không chỉ "đã chạy")

- `tests/test_database_finished_at_migration.py` (2 test): migration additive trên bảng `jobs`
  "legacy" mô phỏng DB dev thật trước khi có cột này, giữ nguyên dữ liệu hàng cũ; idempotent no-op
  trên schema mới.
- `tests/test_jobs_route_to_detail.py` (9 test): `_to_detail()` thuần — `total_pages` truyền
  thẳng (kể cả NULL), `duration_seconds` dùng `created_at`/`finished_at` KHÔNG dùng `started_at`,
  job đang chạy → `duration_seconds=None` + response vẫn hợp lệ, fallback `completed_at` cho hàng
  cũ, và trường hợp cả `finished_at` lẫn `completed_at` đều NULL → `None` (không đoán qua
  `updated_at`).
- `tests/integration/test_job_history_finished_at.py` (12 test) + `tests/integration/
  test_run_job_background_crash_guard.py` (1 test): chạy qua `JobOrchestrator`/`BatchOrchestrator`/
  `_run_job_background()` thật — completed (translate + parse_only), fail ở CHUNK ĐẦU TIÊN (đúng
  kịch bản 6.17.1 H-03), cancelled (translate + parse_only), cost_capped, cả 2 nhánh
  `BatchOrchestrator`, và last-resort guard trong `jobs.py`. Mỗi test assert `finished_at is not
  None`/`>= created_at`, không chỉ trạng thái "đã chạy xong".

### Kết quả chạy thật

```
uv run ruff check <files sửa>          → All checks passed!
uv run ruff format --check <files sửa> → 8 files already formatted
uv run pytest tests/test_database_finished_at_migration.py tests/test_jobs_route_to_detail.py \
  tests/integration/test_job_history_finished_at.py \
  tests/integration/test_run_job_background_crash_guard.py -q  → 22 passed
uv run pytest -q (toàn bộ suite)       → 575 passed, 1 failed (91-95s)
```

1 fail: `tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`
— PRE-EXISTING, thuộc `src/postprocess/rotated_text_overlay.py` đang sửa song song ở session khác
(Bug #9/#10, đã tự xác nhận pre-existing bằng `git stash` ở entry Bug #10 phía trên) — KHÔNG đụng
tới file này trong task US-19. Không có fail mới nào do thay đổi của task này.

### File đã sửa/thêm

Sửa: `src/models/job.py`, `src/models/database.py`, `src/core/job_orchestrator.py`,
`src/api/routes/jobs.py`, `web/history.html`, `web/js/history.js`.

Mới: `tests/test_database_finished_at_migration.py`, `tests/test_jobs_route_to_detail.py`,
`tests/integration/test_job_history_finished_at.py`,
`tests/integration/test_run_job_background_crash_guard.py`.

Không đụng: `src/core/glossary_manager.py`, `src/postprocess/font_shrink.py`/
`rotated_text_overlay.py`, `src/preprocess/searchable_pdf.py`, `src/services/babeldoc_runner.py`/
`pdf2zh_runner.py`, `src/babeldoc_shim/*`, `src/core/config.py` — đang sửa song song ở session
khác (Bug #9/#10).

### Trạng thái

**CHƯA spawn Reviewer** (Protocol 7 R7-01) — báo cáo lại PM, chờ Reviewer thật trước khi coi task
này là "xong". Điểm cần PM/Tech Lead xác nhận: mục 2 ở trên bổ sung 5 điểm thoát `finished_at`
KHÔNG có trong danh sách tường minh của Architecture.md §6.17.2 (BatchOrchestrator ×2 + đã đếm lại
đúng 7 điểm còn lại) — đúng theo Ý ĐỊNH thiết kế ("MỌI trạng thái cuối") nhưng CHƯA qua review
tường minh cho phần mở rộng này.
`babeldoc_word_wrap_fix_enabled=True` lên production thật.

## US-22 Dịch EPUB — Bước 1/3: `EpubDocument` (parser + chunk theo chương)

**Phạm vi task này (theo brief PM)**: CHỈ `EpubDocument` (parse cấu trúc EPUB thành `EpubUnit`) +
`plan_epub_chunks()` (chunk theo chương). KHÔNG gọi `provider.translate()`, KHÔNG đụng
cost_estimator/cost_gate, KHÔNG wire vào `job_orchestrator.py`/`jobs.py`, KHÔNG UI. Đó là bước 2/3
và 3/3, giao riêng sau.

### 1. Protocol 5 R5-02 — spike verify TRƯỚC khi implement đầy đủ

Cài thật vào `.venv` chính thức của project: `uv add ebooklib beautifulsoup4 lxml markdownify` →
`ebooklib==0.20`, `beautifulsoup4==4.15.0`, `lxml==6.1.3`, `markdownify==1.2.3` — khớp CHÍNH XÁC
version Tech Lead đã verify ở Architecture.md §6.20.1/§6.20.12 N-3. (`markdownify` chưa dùng ở
bước này — thêm theo đúng điều kiện (b) của §6.20.12 "đủ điều kiện giao Dev": pin cả 4 lib trong
CÙNG commit đầu tiên chạm tới US-22, dùng thật ở nhánh Markdown parse-only US-15 sau.)

Chạy lại 4/6 bước a→d của spike 6 bước (§6.20.10 mục 1) trên chính file EPUB thật
(`data/uploads/9d436d7b-…Sourdough….epub`) TRƯỚC khi viết `EpubDocument` đầy đủ — bước e/f (gọi
LLM thật, capture golden fixture) thuộc bước 2/3, không làm ở đây:

| Bước | Kỳ vọng (Architecture.md) | Đo lại được |
|---|---|---|
| a — `doc_href` (X6) | `item.file_name` 0/5 khớp zip, join `opf_dir` → 5/5 | **KHỚP Y HỆT**: 0/5 raw, 5/5 sau join |
| b — round-trip `features="xml"` | `ET.fromstring()` OK, `viewBox` không hạ chữ | **KHỚP**: well-formed, không có `viewbox` sai |
| c — 6 dòng `<sup>`/`<sub>` | 5 dòng `1/3`, 1 dòng `1 1/3` (không phải `11/3`) | **KHỚP**: inner-HTML giữ nguyên `<sup>1</sup>/<sub>3</sub>`, không có rule nào chuyển đổi (EPUB→EPUB không cần — X1/X2) |
| d — 4 `<br/>` + bold | inner-HTML giữ `<strong>×4<br/>×3` | **KHỚP**: `blockquote` unit giữ nguyên cả 4 `<strong>` + 3 `<br/>` |

Không lệch số đo nào so với Architecture.md → không cần escalate Tech Lead.

**1 điểm PHẢI escalate PM (không phải sai spec, mà là ước tính của chính PM)**: brief nói "ước
tính 42 chunk" cho file Bread @ budget 8000. Đo bằng `plan_epub_chunks()` thật (thuật toán đúng
§6.20.7/§6.20.12, đã unit-test riêng — xem mục 4): **28 chunk**, không phải 42. Tổng
`doc.total_chars` đo được là 232.127 — 232.127/8.000 ≈ 29, khớp sát 28 đo được. Nhiều khả năng
con số 42 của PM tính theo cách khác (vd ước lượng theo dung lượng file thô, không qua unit-based
chunking thật). Đã trust số đo của chính thuật toán đã implement thay vì brief chưa verify
(đúng tinh thần Protocol 5), nhưng cần PM xác nhận 28 là số đúng trước khi ai dùng con số 42 ở
đâu đó khác.

### 2. `EpubDocument` — `src/services/epub_document.py` (module MỚI)

Theo ĐÚNG bản đã supersede tại Architecture.md §6.20.12 (không theo §6.20.5 gốc ở các điểm đã ⚠️):

- `EpubUnit.text` = **inner-HTML** (X2), không phải text thuần — giữ nguyên `<strong>`, `<sup>`/
  `<sub>`, `<br/>`, v.v. Không có rule `extract()` nào (X1 đã bị xoá hoàn toàn).
- `doc_href` = `posixpath.normpath(posixpath.join(opf_dir, item.file_name))`, `opf_dir` đọc từ
  `META-INF/container.xml` (`full-path` attr) — KHÔNG dùng `item.file_name` của `ebooklib` trần
  (X6). Test bắt buộc `doc_href in zip.namelist()` cho 100% unit.
- `ordinal` đếm trên MỌI node thuộc danh sách tag (sau khi lọc node lồng nhau + node `bb-vi` của
  lần dịch trước), TRƯỚC khi áp drop rule nội dung (Y3) — test riêng xác nhận unit sống sót giữ
  đúng ordinal dù có unit khác bị lọc ở giữa.
- Drop rule Y8 sửa: unit **CHỈ** chứa ISBN mới bị bỏ, không phải "chứa ISBN" — đoạn có tên
  sách/tác giả trước ISBN (file thật `copyright.html#8`) vẫn được giữ.
- `write_translated()` ghi đè tại chỗ bằng `zipfile` (B-07), KHÔNG dùng `epub.write_epub()`:
  - `bilingual=False`: thay nội dung node bằng fragment đã dịch, giữ tag/class/style của node.
  - `bilingual=True`: chèn THÊM node copy sau bản gốc, strip toàn bộ `id` (kể cả descendant, Y2a),
    gắn `lang="vi"` + `class="bb-vi"` (Y2, và là dấu hiệu X3 dùng để `load()` bỏ qua node này ở
    lần đọc sau — chống dịch đôi khi upload lại chính file output). Riêng `td`/`th`: chèn
    `<br/><span class="bb-vi">…</span>` BÊN TRONG ô (Y2b), không tạo cột mới.
  - Validate `ET.fromstring()` trên mọi XHTML đã sửa TRƯỚC khi ghi (Y1) — không bao giờ ghi XHTML
    hỏng vào EPUB.
  - Ghi qua `<output>.epub.tmp` rồi `Path.replace()` (Y5).
  - `translations` có `unit_id` không thuộc lần `load()` này → `EpubParseError` ngay (lineage
    guard R6-02), không âm thầm bỏ qua.
- `EpubDrmError` khi có `META-INF/encryption.xml` VÀ ít nhất 1 `<EncryptedData>` trỏ tài nguyên
  không phải font (`.ttf/.otf/.woff*`) — font obfuscation hợp lệ không bị chặn nhầm.

**1 điểm tự quyết định, cần Tech Lead xác nhận (§6.20.12 Y2c chưa rõ ràng)**: bảng Y2 của
§6.20.12 có dòng "(c) bilingual=False: chỉ thay text node, không đụng element con (nếu không sẽ
mất 10 `<img>` nằm trong `<p>`)" — điều này **mâu thuẫn bề mặt** với mô tả chính ở §6.20.5 bước 2
("thay nội dung của node bằng fragment HTML đã dịch, giữ nguyên tag/class/style"). Đã implement
theo mô tả CHÍNH (thay toàn bộ children bằng fragment đã parse từ bản dịch LLM trả về) vì đơn
giản hơn và khớp X2's core design (cả inner-HTML round-trip qua LLM, kể cả `<img>` nếu có, dựa
vào LLM echo nguyên vẹn thẻ không cần dịch — đã ghi rõ trong prompt contract theo X4, thuộc bước
2/3). Cách đọc khác của Y2c (chỉ vá text node, giữ nguyên cấu trúc element gốc bất kể LLM trả gì)
phức tạp hơn nhiều (cần tree-diff/merge) và CHƯA cần thiết ở bước này vì `write_translated()`
chưa được gọi với bản dịch LLM thật. Đề nghị Tech Lead xác nhận cách hiểu trước khi bước 2/3 build
prompt contract X4 thật — nếu Y2c đúng nghĩa đen thì `write_translated()` cần sửa lại phần
`bilingual=False`.

### 3. `plan_epub_chunks()` — `src/core/chunking.py` (thêm, không đụng `calculate_chunks`/`plan_chunks`)

`EpubChunkPlan`, `EPUB_CHUNK_CHAR_BUDGET=8_000`, `EPUB_REQUEST_CHAR_BUDGET=3_000`,
`EPUB_UNIT_HARD_MAX_CHARS=10_000` (Architecture.md §6.20.7). Thuật toán 2 bước: (1) cắt CHUNK ưu
tiên tại ranh giới tài liệu — chỉ cắt đúng ranh giới khi running đã đạt budget NGAY LÚC chuyển
tài liệu, không ép mỗi tài liệu = 1 chunk, không ép chunk luôn đầy budget khi merge tài liệu nhỏ;
khi 1 tài liệu tự nó vượt budget thì cắt tiếp bên trong nó theo ranh giới unit; (2) trong mỗi
chunk, gộp unit liên tiếp thành REQUEST theo `request_budget`, không bao giờ cắt giữa 1 unit; unit
đơn lẻ vượt `request_budget` được gửi một mình; unit vượt `EPUB_UNIT_HARD_MAX_CHARS` →
`EpubUnitTooLargeError` (Y4 — job phải fail rõ ràng, không tự cắt câu).

3 hằng số cũng thêm vào `Settings` (`src/core/config.py`: `epub_chunk_char_budget`,
`epub_request_char_budget`, `epub_unit_hard_max_chars`, giá trị mặc định khớp module constant) —
theo đúng Z3 "cả 3 hằng số phải nằm ở Settings, không chôn trong code". Chưa wire override thật
vào `plan_epub_chunks()` (đó là việc của Job Orchestrator, bước 2/3) — bước này chỉ thêm field.

KHÔNG thêm `EPUB_INLINE_MARKUP_FACTOR`/`EPUB_JSON_ENVELOPE_CHARS_PER_UNIT` (X5) — thuộc
`cost_estimator`/`cost_gate`, ngoài phạm vi task này theo đúng brief PM.

### 4. Test

`tests/test_epub_document.py` (27 test) + bổ sung vào `tests/test_chunking.py` (11 test EPUB,
thuần thuật toán với `EpubUnit` giả lập, không cần file EPUB thật).

Dùng CẢ 2 file EPUB thật (Protocol 5 mục 3 — không mock tay):

- **(a) Cấu trúc**: Sourdough 384 unit / 5 doc spine (khớp B-01/B-04); Bread 19 doc spine (tự
  verify qua `ebooklib.read_epub().spine` trực tiếp, không qua `EpubDocument`, trước khi tin).
- **(b) Chunk**: Sourdough 7 chunk (khớp Architecture.md); Bread 28 chunk (KHÁC 42 của brief PM —
  xem mục 1). Test thêm: liên tục/không chồng lấp/phủ hết unit, request không cắt giữa 1 unit.
- **(c) `<sup>`/`<sub>`**: 6 dòng thật (5 phân số thuần + 1 hỗn số) giữ nguyên HTML, không rút gọn.
- **(d) Inline markup**: đoạn 4 nguyên liệu `<strong>×4<br/>×3` giữ nguyên qua parse.
- **(e) Round-trip ghi lại**: entry không liên quan byte-identical (so `zipfile.read()`, không
  phải so byte nén thô — xem ghi chú thiết kế trong docstring `write_translated`), thứ tự entry
  giữ nguyên, mono + bilingual đều well-formed, bilingual không tạo duplicate id (32 unit có
  `<a id="page_N"/>` trong file thật), bilingual giữ đúng số cột bảng (test trên file Bread, có
  `<table>` thật — 12 bảng, 36 unit `td`).
- Thêm: DRM (dương tính + âm tính font-only, dùng fixture EPUB tối thiểu tự dựng bằng `zipfile`,
  KHÔNG phải mock cho logic đang test — chỉ nhỏ hơn 2 file thật), lineage guard (`unit_id` lạ →
  `EpubParseError`), determinism `unit_id` qua 2 lần `load()` (R6-02), nesting dedup (`li>p`).

### Kết quả chạy thật

```
uv run ruff check <files sua>          → All checks passed!
uv run ruff format --check <files sua> → sach (3 file can format lai da format xong)
uv run pytest tests/test_epub_document.py tests/test_chunking.py -q  → 43 passed
uv run pytest -q (toan bo suite, so voi baseline qua git stash)
  truoc thay doi (stash):  575 passed, 1 failed
  sau thay doi:            613 passed, 1 failed   (+38 test moi, PASS het)
```

1 fail cả 2 lần đều là `tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`
— PRE-EXISTING, không liên quan EPUB, không đụng file này trong task. Không có fail mới.

### File đã sửa/thêm

Mới: `src/services/epub_document.py`, `tests/test_epub_document.py`.

Sửa: `src/core/chunking.py` (thêm `EpubChunkPlan`/`plan_epub_chunks`/3 hằng số/`EpubUnitTooLargeError`,
KHÔNG đụng phần PDF hiện có), `src/core/config.py` (thêm 3 field Settings, KHÔNG đụng field khác —
đọc bản mới nhất có Bug #10 trước khi sửa), `tests/test_chunking.py` (thêm test EPUB),
`pyproject.toml`/`uv.lock` (thêm `ebooklib`/`beautifulsoup4`/`lxml`/`markdownify`, pin version).

Không đụng: `src/core/glossary_manager.py`, `src/core/job_orchestrator.py`,
`src/postprocess/font_shrink.py`/`rotated_text_overlay.py`, `src/preprocess/searchable_pdf.py`,
`src/services/babeldoc_runner.py`/`pdf2zh_runner.py`, `src/babeldoc_shim/*`, `CLAUDE.md`,
`docs/Architecture.md`, `docs/PRD.md`.

### Trạng thái

**CHƯA spawn Reviewer** (Protocol 7 R7-01) — báo cáo lại PM, chờ Reviewer thật trước khi coi bước
này là "xong". 2 điểm cần PM/Tech Lead xác nhận trước khi bước 2/3 bắt đầu: (1) chênh lệch 28 vs
42 chunk cho file Bread (mục 1), (2) cách đọc đúng của Y2c "chỉ thay text node" vs mô tả chính
"thay nội dung node bằng fragment" cho `bilingual=False` (mục 2).

---

## Bổ sung (2026-09-09) — Sửa Y2(c) `write_translated()` (bilingual=False) trước khi giao Reviewer

PM đọc lại `docs/Architecture.md` dòng 5591 (bảng Final Decision §6.20.12) xác nhận Y2(c)
**"NHẬN toàn bộ"** — THẮNG so với mô tả nháp ở §6.20.5 bước 2 mà bản trước đã lỡ chọn implement.
Sửa lại đúng theo Y2(c): `bilingual=False` **chỉ thay text node, không đụng element con**.

### 1. Thay đổi trong `src/services/epub_document.py`

- Thêm `_INLINE_PRESERVE_TAGS` (đúng danh sách contract X4, Architecture.md dòng 5541-5542:
  `strong, em, b, i, sup, sub, br, a, span, small`) và `_NO_TRANSLATE_TAGS = {code, pre}`.
- `_apply_translation()` nhánh `not bilingual` rẽ 2 đường:
  - Subtree KHÔNG có tag ngoài `_INLINE_PRESERVE_TAGS` → giữ nguyên cách cũ (`node.clear()` +
    append fragment dịch nguyên khối) — an toàn vì LLM cam kết giữ đúng số lượng/vị trí các tag
    này (X4).
  - Subtree CÓ tag ngoài danh sách đó (vd `<img>`) → `_apply_translation_untrusted_structure()`:
    KHÔNG bao giờ gọi `.clear()`/xoá bất kỳ Tag nào — chỉ `NavigableString.replace_with(...)` trên
    đúng các text node gốc. `<img>` (và mọi tag không nằm trong contract) do đó **không thể** bị
    mất, vì không có lệnh nào từng nhắm vào nó.
- 3 nhánh con của `_apply_translation_untrusted_structure()` (`_collect_runs_recursive`/
  `_text_runs_under` dùng chung cho cả subtree gốc lẫn fragment đã dịch, đảm bảo cùng định nghĩa
  "slot" ở 2 phía):
  1. **1 slot** (đa số ca thực tế — xem mục 2): thay đúng node đó bằng toàn bộ fragment dịch
     (`replace_with(*translated_children)`), giữ nguyên định dạng nếu LLM có trả tag inline.
  2. **Nhiều slot, đếm khớp** giữa số đoạn text gốc và số đoạn text trong bản dịch: khớp 1-1 theo
     đúng thứ tự tài liệu (chỉ lấy nội dung text của mỗi đoạn dịch, giữ nguyên tag bọc của bản
     GỐC — không tin cấu trúc tag của bản dịch ở nhánh này, chỉ tin thứ tự).
  3. **Nhiều slot, đếm KHÔNG khớp** (LLM gộp/tách câu khác số đoạn gốc) → **fallback đã biết giới
     hạn, xem mục 2**.

### 2. Gap báo cáo PM (đã escalate, chưa có phản hồi ngược lại)

Architecture.md (X4, Y2, §6.20.12) mô tả CONTRACT (id→html, tag nào được giữ) và RÀNG BUỘC
(Y2c: không đụng element con) nhưng **không có thuật toán tường minh** cho ca "1 unit có nhiều
text node xen kẽ 1 tag không nằm trong `_INLINE_PRESERVE_TAGS`, và bản dịch LLM trả về không giữ
đúng số lượng đoạn text tương ứng". Đây là gap thật, không phải lười tra cứu — đã đọc lại toàn bộ
X4/Y2/Y2c + vùng lân cận trước khi kết luận.

Đã chọn phương án (không tự đoán liều, chọn theo hướng PM gợi ý — an toàn hơn là mất cấu trúc):
khi đếm không khớp, gán TOÀN BỘ bản dịch vào text node **gốc dài nhất** (heuristic "nội dung
chính"), các text node còn lại **giữ nguyên tiếng Anh gốc** (không xoá, không đoán chia). Đã ghi
rõ thành "Known limitation" ngay đầu `epub_document.py` và có test riêng
(`test_write_translated_monolingual_img_mismatch_uses_documented_fallback`) xác nhận hành vi này
tường minh, không phải bug ẩn.

**Đo trên 2 file EPUB thật hiện có (Protocol 5 mục 3)**: cả 10 `<img>` (Sourdough) đều nằm trong
`<p>` KHÔNG có text nào khác → bị `_is_droppable_content()` loại khỏi `units` từ trước (get_text()
rỗng) → **chưa từng đi tới nhánh `write_translated()` này trên dữ liệu mẫu hiện có** (tự verify lại
bằng script, không suy đoán). Nghĩa là gap trên hiện là rủi ro LÝ THUYẾT cho 2 file mẫu, nhưng
Y2(c) áp dụng tổng quát cho MỌI EPUB khác — nơi ảnh + chữ chú thích thật sự nằm chung 1 `<p>` —
nên vẫn bắt buộc implement đúng, không được bỏ qua vì "chưa gặp trên data mẫu".

### 3. Test thêm vào `tests/test_epub_document.py` (3 test mới, EPUB tối thiểu tự dựng — cùng quy
ước với các test DRM/nesting hiện có, KHÔNG phải mock cho logic đang test)

- `test_write_translated_monolingual_preserves_img_child_single_text_run`: `<p><img/> text</p>` —
  ca phổ biến nhất trên thực tế, 1 slot, không nhập nhằng.
- `test_write_translated_monolingual_preserves_img_child_matched_multi_run`: 4 slot gốc khớp đúng
  4 đoạn bản dịch → xác nhận khớp 1-1 đúng thứ tự, `<img>` và tag `<b>` gốc giữ nguyên vị trí.
- `test_write_translated_monolingual_img_mismatch_uses_documented_fallback`: đếm lệch (4 slot gốc
  vs 1 đoạn dịch gộp) → xác nhận `<img>` không mất, bản dịch đầy đủ vào slot dài nhất, các slot
  ngắn hơn giữ nguyên tiếng Anh, output vẫn well-formed XHTML.

Không sửa gì thêm cho điểm "28 vs 42 chunk" — PM xác nhận 28 là số đúng, không cần điều chỉnh.

### 4. Kết quả chạy thật

```
uv run ruff check src/services/epub_document.py tests/test_epub_document.py     → All checks passed!
uv run ruff format --check <2 file trên>                                        → sạch
uv run pytest tests/test_epub_document.py tests/test_chunking.py -q             → 46 passed (43 cũ + 3 mới)
uv run pytest -q (toàn bộ suite)                                                → 616 passed, 1 failed
```

1 fail (`tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`)
— tự verify lại bằng `git stash` (bỏ toàn bộ thay đổi của mình, chạy lại): **fail y hệt trước khi
sửa** → xác nhận PRE-EXISTING, không liên quan tới thay đổi này, không có fail mới phát sinh.

### File đã sửa

`src/services/epub_document.py` (thêm `_INLINE_PRESERVE_TAGS`/`_NO_TRANSLATE_TAGS`/
`_has_untrusted_descendant`/`_collect_runs_recursive`/`_text_runs_under`/
`_apply_translation_untrusted_structure`, sửa nhánh `not bilingual` của `_apply_translation`),
`tests/test_epub_document.py` (3 test mới). Không đụng file nào khác.

### Trạng thái

**CHƯA spawn Reviewer** — chờ Reviewer thật (Protocol 7 R7-01) trước khi coi là "xong". Cần PM xác
nhận: (a) implementation Y2(c) đã đúng theo bảng Final Decision, (b) hướng fallback đã chọn cho ca
đếm-không-khớp (mục 2) có chấp nhận được hay cần hỏi lại Tech Lead để chốt thuật toán khác.

---

## Sửa (2026-09-09) — Y2(d) `li > ul` lồng: tách unit theo "innermost" (Reviewer reject vòng 1/3)

Reviewer reject bước 1/3 US-22 vòng 1/3 (Dev↔Reviewer, Protocol 3): Architecture.md §6.20.12 bảng
Final Decision hàng Y2 chấp nhận toàn bộ **"NHẬN toàn bộ"** cho cả 4 mục (a)-(d), trong đó mục (d)
*"`li > ul` lồng: lấy **innermost** block có text trực tiếp"* — nghĩa là 1 `<li>` chứa `<ul>` lồng
bên trong phải tách thành NHIỀU unit riêng, không được gom cả khối `<li><ul>...</ul></li>` thành 1
unit duy nhất. Code trước đó (`_collect_candidate_nodes()`) áp dụng đồng nhất luật "outermost only"
cho MỌI ca lồng nhau, kể cả `li > ul` — sinh ra 1 unit khổng lồ nhét nguyên markup `<ul><li>` thô
vào `text`, ngoài contract X4 (`_INLINE_PRESERVE_TAGS`), hành vi LLM với markup đó không xác định.
Chi tiết đầy đủ: xem `docs/review-report.md` section "Review Report — US-22 Dịch EPUB, Bước 1/3",
mục 1 "Blocking issue" (dòng ~6986 trở đi).

### 1. Thay đổi trong `src/services/epub_document.py`

- Thêm hằng số `_LIST_CONTAINER_TAGS = frozenset({"ul", "ol"})`.
- Tách `_has_unit_tag_ancestor()` thành 2 hàm con: `_nearest_unit_ancestor()` (tìm ancestor unit-tag
  gần nhất) và `_crosses_list_container()` (kiểm tra có `<ul>`/`<ol>` nằm giữa node và ancestor đó
  hay không). `_has_unit_tag_ancestor()` giờ chỉ loại node lồng nếu đường đi tới ancestor gần nhất
  KHÔNG băng qua `<ul>`/`<ol>` — tức giữ nguyên luật cũ (outermost) cho ca lồng đơn giản (`li > p`,
  §6.20.5, chưa bị Y2(d) thay thế), nhưng CHO PHÉP `li` con trong `ul`/`ol` lồng trở thành candidate
  riêng — đệ quy tự nhiên với lồng nhiều cấp vì mỗi node chỉ so với ancestor GẦN NHẤT của chính nó.
- Thêm `_strip_nested_lists(node)`: trả về bản COPY độc lập (`copy.deepcopy` + `decompose()` từng
  `<ul>`/`<ol>` con, mọi cấp) — dùng trong `load()` TRƯỚC khi trích `text` (`_inner_html`) và trước
  khi xét drop-rule (`_is_droppable_content`), để unit của node cha không chứa lại markup danh sách
  con (đã tách unit riêng) và không bị `get_text()` "ăn ké" nội dung của unit con khi xét rỗng/toàn
  số/URL/ISBN.
- Sửa `_collect_runs_recursive()` (dùng bởi `_text_runs_under()` trong nhánh Y2(c)
  `_apply_translation_untrusted_structure`): bỏ qua (không đệ quy vào) subtree `<ul>`/`<ol>` giống
  cách đã bỏ qua `<code>`/`<pre>` — nếu không, khi `write_translated()` ghi bản dịch cho unit cha
  (vd `li` chứa `ul` lồng, luôn rơi vào nhánh untrusted-structure vì `ul`/`li` không nằm trong
  `_INLINE_PRESERVE_TAGS`), nó sẽ gom nhầm cả text bên trong `ul` con làm "slot" của chính nó, ghi
  đè sai lên nội dung đáng lẽ thuộc về unit con (vốn được ghi riêng ở ordinal khác trong cùng lần
  gọi `write_translated()`).
- Cập nhật docstring đầu file, thêm đoạn giải thích Y2(d) và cách 3 thay đổi trên phối hợp với nhau.

### 2. Tự verify bằng script độc lập trước khi viết test chính thức (giống cách Reviewer đã làm)

Dựng EPUB tối thiểu với `<li>Preheat the oven to 220C, then:<ul><li>Add flour and water</li><li>Knead
for ten minutes</li></ul></li>` (đúng fixture Reviewer đã dùng để phát hiện bug) — `load()` cho ra
**3 unit** (`text` lần lượt: "Preheat the oven to 220C, then:", "Add flour and water", "Knead for ten
minutes"), không unit nào chứa markup `<ul>`/`<li>` thô. `write_translated()` với bản dịch giả cho cả
3 unit → output XHTML giữ nguyên cấu trúc `<ul>/<li>` lồng, mỗi `<li>` mang đúng bản dịch của chính
nó, không lệch/tràn sang `<li>` khác. Test thêm cả ca lồng 3 cấp (`li > ul > li > ul > li`) — tách
đúng thành 3 unit, mỗi unit là 1 lá có text trực tiếp, đúng tinh thần "innermost" đệ quy.

### 3. Test thêm vào `tests/test_epub_document.py` (3 test mới, R6-02: assert cấu trúc unit cụ thể —
tag/ordinal/text từng unit và cấu trúc XHTML sau khi ghi, không chỉ đếm số lượng)

- `test_nested_list_splits_into_innermost_units`: fixture `li > ul` 1 cấp giống hệt Reviewer dùng —
  assert đúng 3 unit, đúng `text` từng unit, không unit nào chứa `<ul>`/`<li>` thô.
- `test_nested_list_multi_level_splits_to_every_leaf`: lồng 3 cấp — assert tách hết tới tận lá.
- `test_write_translated_nested_list_updates_each_leaf_independently`: ghi bản dịch cho cả 3 unit,
  assert output giữ nguyên `<ul>/<li>`, mỗi `<li>` mang đúng bản dịch của chính nó (so khớp chuỗi con
  cụ thể theo đúng vị trí lồng nhau), không còn tiếng Anh gốc sót lại, vẫn well-formed XHTML
  (`ET.fromstring` không raise).

### 4. Kết quả chạy thật

```
uv run ruff check src/services/epub_document.py tests/test_epub_document.py     → All checks passed!
uv run ruff format --check <2 file trên>                                        → sạch (1 file tự động
                                                                                    format lại bởi
                                                                                    `ruff format`)
uv run pytest tests/test_epub_document.py tests/test_chunking.py -q             → 49 passed (46 cũ + 3 mới)
uv run pytest -q (toàn bộ suite)                                                → 619 passed, 1 failed
```

1 fail (`tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`)
— khớp CHÍNH XÁC tên/số lượng fail đã ghi nhận ở 2 lần review trước (Increment US-19 và bước 1/3
US-22 vòng 1), pre-existing, không liên quan tới thay đổi Y2(d) này. So khớp SỐ LƯỢNG fail (không
phải tổng pass): 1 fail trước sửa, 1 fail sau sửa — không có fail mới phát sinh; tổng pass tăng từ
616 → 619 đúng bằng 3 test mới thêm.

### File đã sửa

`src/services/epub_document.py` (thêm `_LIST_CONTAINER_TAGS`, `_nearest_unit_ancestor`,
`_crosses_list_container`, `_strip_nested_lists`; sửa `_has_unit_tag_ancestor`, vòng lặp trong
`load()`, `_collect_runs_recursive`; cập nhật docstring đầu file), `tests/test_epub_document.py`
(3 test mới). Không đụng file nào khác — không chạm `src/core/chunking.py`, `src/core/config.py`,
Translation Engine/cost-gate/job_orchestrator (vẫn ngoài phạm vi bước 1/3, đúng như bước trước).

### Trạng thái

**CHƯA spawn Reviewer cho vòng sửa này** — chờ Reviewer duyệt lại (vòng 2/3 Dev↔Reviewer, giới hạn
cuối là vòng 3/3 theo Protocol 3). Báo cáo lại PM: đã implement đúng Y2(d) theo yêu cầu reject của
Reviewer, có test riêng cho cả ca lồng 1 cấp lẫn nhiều cấp, đã tự verify bằng script độc lập trước
khi viết test chính thức (không chỉ tin code compile được), regression 0 fail mới.

---

## US-22 Bước 1/3 — Fix Bug #EPUB-1 (QA vòng 1/5 Dev↔QA) + điều tra Bug #EPUB-2 (2026-09-09)

### Bối cảnh

QA test round-trip toàn bộ unit của 2 file EPUB thật (`docs/test-report.md` mục "US-22 Dịch EPUB —
Bước 1/3") phát hiện 2 bug trong `write_translated()` — bug NGHIÊM TRỌNG (#EPUB-1, mất dữ liệu âm
thầm) bắt buộc sửa trước bước 2/3, và 1 bug mức trung bình (#EPUB-2) cần điều tra thêm xem có pattern
sửa được không. Đây KHÔNG tính vào giới hạn Protocol 3 Dev↔Reviewer (QA là vòng khác) — vòng 1/5
Dev↔QA.

### 1. Bug #EPUB-1 — ĐÃ SỬA

**Root cause** (đúng như QA đã trace): `_apply_translation()` đưa thẳng `vi_html` (ban dịch LLM,
PLAIN TEXT chưa chắc đã escape đúng `&`/`<`) vào `_fragment_children()` để re-parse như XML
(`features="xml"` qua lxml). Ký tự `&`/`<` trần làm XML không well-formed — lxml "chữa cháy" bằng
cách âm thầm CẮT BỎ phần nội dung không hợp lệ, KHÔNG raise lỗi. `_validate_wellformed()` (Y1) không
bắt được ca này vì kết quả sau khi cắt vẫn là XML hợp lệ.

**Fix** (`src/services/epub_document.py`):

- Hàm mới `_escape_untrusted_markup(vi_html: str) -> str`: escape mọi `&` không phải 1 phần của
  entity hợp lệ (`&amp;`/`&lt;`/`&gt;`/`&quot;`/`&apos;`/numeric charref) thành `&amp;`, và mọi `<`
  KHÔNG mở đầu 1 thẻ nằm trong `_INLINE_PRESERVE_TAGS` (X4 — `strong, em, b, i, sup, sub, br, a,
  span, small`) thành `&lt;`. Các thẻ inline hợp lệ vẫn được giữ nguyên để parse thành `Tag` thật
  (không escape nhầm thành text), đúng cam kết X4. Gọi hàm này ở đầu `_apply_translation()` — áp
  dụng cho cả nhánh `bilingual=False` lẫn `bilingual=True` (`td`/`th` và nhánh chung), vì cả 3 đều
  gọi `_fragment_children()` với cùng `vi_html` chưa qua sanitize.
- `_inner_html()` (dùng để tạo `EpubUnit.text`, X2 — nguồn phụ, không phải fix bắt buộc nhưng cùng
  root cause QA đã chỉ ra): đổi từ tự ghép `"".join(str(child) for child in node.children)` (SAI —
  `str()` của 1 `NavigableString` đã tách khỏi cây trả về text đã decode, KHÔNG re-escape) sang dùng
  đúng API của bs4: `node.decode_contents()` — tự escape đúng chuẩn cho cả `Tag` lẫn `NavigableString`
  con, đúng gợi ý của QA ("dùng đúng API của bs4 ... thay vì tự ghép chuỗi rồi re-parse").

**Bằng chứng đã sửa xong — chạy lại ĐÚNG 2 câu QA đã đo**:

```
vi_html = "Do am can duy tri o muc < 65% de tranh nhao qua uot."
doc.write_translated({unit.unit_id: vi_html}, out, bilingual=False)
EpubDocument.load(out).units[0].text          -> 'Do am can duy tri o muc &lt; 65% de tranh nhao qua uot.'
plain text sau khi giải mã lại (get_text()) -> 'Do am can duy tri o muc < 65% de tranh nhao qua uot.'
=> KHỚP 100% chuỗi gốc, không mất chữ (trước fix: chỉ còn 'Do am can duy tri o muc ')

vi_html = "In an boi C&C Offset Printing Co. Ltd."
=> plain text sau round-trip khớp 100%, còn nguyên "C&C" (trước fix: mất '&C')
```

Chạy lại `qa_roundtrip.py` (script QA để lại) trên chính 2 file EPUB thật QA dùng:

```
Sourdough: 384 unit, 0 mismatch (như cũ — file này không có ký tự & trần)
Bread:     866 unit, mismatch giảm từ (mất dữ liệu #EPUB-1 lẫn #EPUB-2 trộn lẫn) xuống ĐÚNG 24
           mismatch — toàn bộ 24 ca còn lại đều là Bug #EPUB-2 (xem mục 2), KHÔNG còn ca nào mất
           dữ liệu kiểu #EPUB-1 (đã kiểm từng ca: không còn ca nào trong 24 này liên quan `&`/`<`
           trần bị cắt — tất cả là duplicate-content do fallback đếm-slot, đúng cơ chế #EPUB-2)
```

Đã thêm 4 test permanent vào `tests/test_epub_document.py` (mục "(f) Bug #EPUB-1"), dùng ĐÚNG 2 câu
QA đã đo làm golden case + 1 test regression đảm bảo thẻ inline (`<b>`, `<i>`) vẫn được parse thành
Tag thật (không bị escape nhầm) + 1 test cho `_inner_html()`.

**Kết luận Bug #EPUB-1: ĐÃ SỬA XONG, có bằng chứng cụ thể, sẵn sàng cho QA re-verify.**

### 2. Bug #EPUB-2 — ĐÃ ĐIỀU TRA, KHÔNG TỰ SỬA, ESCALATE LẠI CHO PM

Điều tra toàn bộ 24/866 unit của file Bread rơi vào fallback đếm-slot-không-khớp
(`_apply_translation_untrusted_structure`), bằng script phân tích trực tiếp cấu trúc DOM của từng
unit (không đoán):

```
24/24 unit:      tag = 'td', descendant "untrusted" duy nhất = 1 thẻ <p class="top">
23/24 unit:      2 "slot" text (vd <i>Apple</i> + " Erika Janik")
1/24 unit:       1 "slot" text (không có <i>)
doc_href:        100% CHỈ 1 tài liệu — OEBPS/02_editor.xhtml (không rải rác khắp sách)
```

**Đây là 1 bảng "The Edible Series" (danh sách sách + tác giả liên quan) lặp lại 24 dòng, mỗi dòng
1 `<td><p class="top"><i>TenSach</i> TenTacGia</p></td>`** — hoàn toàn không phải hiện tượng rải rác
ngẫu nhiên, mà là 1 cấu trúc bảng biên tập cụ thể, xuất hiện đúng 1 chỗ trong sách.

**Vì sao KHÔNG tự sửa dù pattern rất rõ**: nguyên nhân sâu xa của việc rơi vào fallback là số "slot"
văn bản đếm được của `vi_html` (bản dịch) không khớp số "slot" gốc — cụ thể ở đây do `<p>` là 1 thẻ
NGOÀI `_INLINE_PRESERVE_TAGS` (X4 chỉ cam kết LLM giữ nguyên `strong, em, b, i, sup, sub, br, a,
span, small` — KHÔNG có `p`), nên ứng xử của `_apply_translation_untrusted_structure` với nó phụ
thuộc hoàn toàn vào **LLM thật sẽ trả về vi_html có giữ nguyên thẻ `<p>` bao ngoài hay không** — điều
này KHÔNG được định nghĩa trong Architecture.md X4 (prompt chỉ nói về 10 thẻ inline, không nói gì về
`<p>`/`<td>`/thẻ khối khác lồng bên trong 1 unit), và bước 2/3 (wire LLM thật) CHƯA làm nên KHÔNG có
cách verify sống hành vi LLM thật với ca này (đúng tinh thần R5-02 — không được viết implementation
dựa trên phỏng đoán hành vi 1 dependency ngoài chưa verify). Bất kỳ rule bổ sung nào ở đây (vd: "tin
luôn `<p>` là thẻ bao ngoài đáng tin nếu nó là node bao NGOÀI CÙNG duy nhất") thực chất là MỞ RỘNG
contract X4 — vượt quyền Dev, đúng theo CLAUDE.md "Không tự ý thay đổi architecture — escalate lên
Tech Lead nếu cần".

**Số liệu cụ thể báo cáo PM để quyết định**:
- Tỷ lệ: 24/866 (~2,8%), 100% tập trung ở 1 bảng biên tập cụ thể (không lan toả khắp sách).
- Bản chất: đúng như PM mô tả — "vấn đề cố hữu của việc ánh xạ ngược bản dịch LLM (không có cách nào
  chắc chắn khớp lại nhiều text-node từ 1 khối text đã dịch mà không có tín hiệu định ranh giới từ
  chính LLM)" — vì gốc rễ là contract X4 hiện tại KHÔNG nói LLM phải làm gì với thẻ khối lồng bên
  trong unit (chỉ nói về 10 thẻ inline).
- 2 phương án PM có thể chọn (Dev không tự quyết): (a) mở rộng contract JSON X4 — thêm chỉ thị rõ
  ràng cho LLM về cách xử lý thẻ khối lồng (vd tường minh yêu cầu giữ nguyên `<p>` bao ngoài, hoặc
  tách `<p>` thành 1 unit riêng ngay từ `load()` thay vì gộp vào unit `<td>` cha — đổi rule dedup
  "outermost wins" hiện tại), hoặc (b) chấp nhận tỷ lệ ~2,8% này là known limitation tại bước 2/3
  (bản dịch cho các unit dạng bảng biên tập kiểu này có thể bị duplicate content nhẹ, không mất cấu
  trúc/không hỏng EPUB — đã có test `test_write_translated_monolingual_img_mismatch_uses_documented_fallback`
  đảm bảo hành vi fallback không phá hỏng file).

**Không nâng mức "blocking" cho bước 2/3** — khác Bug #EPUB-1, vì bản chất KHÔNG phải data loss/silent
failure, mà là duplicate content đã biết giới hạn, ưu tiên đúng "không mất/không hỏng cấu trúc" theo
thiết kế hiện tại.

### 3. Regression — chạy lại toàn bộ, so sánh số lượng với baseline QA

```
uv run ruff check src/services/epub_document.py src/core/chunking.py tests/test_epub_document.py
  → All checks passed!
uv run ruff check src/ tests/ (toàn bộ)
  → All checks passed!
uv run pytest tests/test_epub_document.py tests/test_chunking.py -q
  → 53 passed (49 cũ + 4 test mới cho Bug #EPUB-1)
uv run pytest -q (toàn bộ suite)
  → 623 passed, 1 failed (94.99s)
```

1 fail: `tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`
— khớp ĐÚNG tên đã ghi nhận ở QA/Reviewer các vòng trước (pre-existing, không liên quan EPUB). Tổng
pass tăng từ 619 (baseline QA) → 623 = đúng bằng 4 test mới thêm. **Không có regression mới.**

### File đã sửa

`src/services/epub_document.py` (thêm `_escape_untrusted_markup`, `_INLINE_TAG_ALTERNATION`,
`_TRUSTED_TAG_OR_BARE_LT_RE`, `_BARE_AMP_RE`; sửa `_inner_html()` dùng `decode_contents()`; sửa
`_apply_translation()` gọi sanitize `vi_html` ở đầu hàm), `tests/test_epub_document.py` (4 test mới,
mục "(f) Bug #EPUB-1"). Không đụng `src/core/chunking.py`, `src/core/config.py`, Translation
Engine/cost-gate/job_orchestrator — vẫn ngoài phạm vi bước 1/3.

### Trạng thái

**CHƯA báo "xong"** — chờ QA re-verify (vòng 2/5 Dev↔QA nếu QA test lại), và chờ PM/Tech Lead quyết
định hướng xử lý Bug #EPUB-2 (mục 2 ở trên) trước khi bước 2/3 dùng chung cơ chế fallback này cho bản
dịch LLM thật. Báo cáo PM: Bug #EPUB-1 đã sửa xong + có bằng chứng cụ thể (mục 1); Bug #EPUB-2 đã
điều tra xong, xác nhận đây là vấn đề cố hữu của việc ánh xạ ngược bản dịch LLM không có tín hiệu
ranh giới — KHÔNG tự sửa, cần PM quyết định giữa mở rộng contract X4 hoặc chấp nhận known limitation.

## US-22 Dịch EPUB — Bước 2/3: nối `EpubDocument` vào Translation Engine thật + cost-gate (Dev, 2026-09-09)

Nối phần đã có từ bước 1/3 (`EpubDocument`, `plan_epub_chunks`) vào pipeline dịch THẬT — cost gate,
contract JSON app↔LLM, `EpubTranslateRunner`. Theo đúng Architecture.md §6.20.6-6.20.9 và
§6.20.12 (X3/X4/X5/Y6, "Final Decision sau phản biện Domain Expert").

### 0. Ghi chú thứ tự làm việc

Khi bắt đầu session này, `git status` đã cho thấy phần lớn mục A (Y6 — sửa `with_retry` không retry
5xx), mục B (cost gate rẽ nhánh EPUB), và mục C (contract JSON `build_epub_batch_prompt()` +
`parse_epub_batch_response()` trong `prompt_builder.py`, cùng migration DB cho `Job.total_units`/
`Chunk.unit_start`/`unit_end`) đã được code **nhưng chưa commit** — khớp đúng thiết kế
Architecture.md, đã tự đọc lại toàn bộ diff + chạy `ruff`/`pytest` để xác nhận trước khi tiếp tục
(không phải Reviewer — không tính là đã review, xem mục "Trạng thái" cuối entry này). Phần việc CHÍNH
của session này là mục D (`EpubTranslateRunner`/`run_epub_job()`) — chưa có gì tồn tại trước đó (grep
`git log` xác nhận `job_orchestrator.py` không nằm trong diff uncommitted) — và golden fixture thật
(mục C.3, bắt buộc theo Protocol 5).

### A. Y6 — sửa retry ở tầng provider (đã có sẵn khi bắt đầu session, đã tự verify lại)

Map lỗi 5xx/timeout/connection của SDK từng provider sang đúng exception transient đã có
(`RateLimitError`/`TimeoutError`/`ConnectionError`) thay vì rơi vào nhánh bắt-hết `TranslationProviderError`
(permanent, `with_retry()` không retry) — cả 5 provider: `openai_provider.py` (`APITimeoutError`,
`APIConnectionError`, `InternalServerError` — SDK dùng đúng class này cho MỌI 5xx không có class
riêng, tự đọc `openai/_exceptions.py` xác nhận), `claude_provider.py` (tương tự, 3 exception mới),
`gemini_provider.py` (`DeadlineExceeded` bắt TRƯỚC `ServerError` — là con của nó, thứ tự except
quan trọng), `deepl_provider.py` (`ConnectionException`), `ollama_provider.py` (`httpx.TimeoutException`
bắt trước `HTTPError`, cộng nhánh status >= 500). `deepseek_provider.py` không cần sửa — subclass
`OpenAIProvider`, kế thừa `translate()` nguyên vẹn. **KHÔNG** nới `_TRANSIENT_ERRORS` thành bắt hết
`Exception` (đúng bẫy retry-vô-hạn E-10 của phương án A đã bác ở bước trước).

### B. Cost gate rẽ nhánh EPUB (đã có sẵn khi bắt đầu session, đã tự verify lại)

`src/core/cost_gate.py::_estimate_epub_translation_cost()` — `EpubDocument.load()`,
`source_text_chars = int(doc.total_chars * EPUB_INLINE_MARKUP_FACTOR) + len(doc.units) *
EPUB_JSON_ENVELOPE_CHARS_PER_UNIT` (X5, 2 hằng số đã có sẵn trong `chunking.py` từ bước 1/3),
`llm_request_count = sum(len(c.requests) for c in plan)` (SỐ REQUEST, không phải số unit — đúng
cảnh báo lệch 8,8× trong Architecture.md), gọi lại **CÙNG** `estimate_job_cost_v2()` — không viết
công thức thứ hai. Bỏ 2 nhánh chặn cứng `if file_type == "epub": raise 400` ở
`GET /api/jobs/{id}/cost-estimate` và `POST /api/estimate`; EPUB hợp lệ khi có `total_units` thay vì
`total_pages`. `CostEstimateResponse.total_pages: int | None`, thêm `total_units: int | None = None`.

### C. Contract JSON app↔LLM (đã có sẵn khi bắt đầu session, đã tự verify lại) + golden fixture THẬT (mới làm trong session này)

`prompt_builder.py::build_epub_batch_prompt(glossary_prompt)` nối `glossary_prompt` hiện có (không
sửa 1 chữ) + khối contract 6 điều (id ngắn 0..N, output JSON object đúng đủ id, giữ nguyên 10 thẻ
inline, không đổi số, không dịch `<code>`/`<pre>`, thiếu dịch → trả nguyên văn chứ không rỗng) + 1 ví
dụ one-shot (có inline tag + số + `<sup>`/`<sub>`). `parse_epub_batch_response()` chịu được thực tế:
strip code fence, id str/int đều nhận, value rỗng/thiếu/không phải string đều coi là "thiếu" (không
default thành rỗng).

**Golden fixture thật (Protocol 5 mục 3, bắt buộc Dev tự làm — đã làm trong session này)**: gọi THẬT
DeepSeek API (`DEEPSEEK_API_KEY` thật trong `.env`) với 5 unit thật lấy từ
`data/uploads/…Baking with Sourdough…epub` (`ops/xhtml/chapter01.html` ordinal 16/17/18/87/288 — chọn
để phủ đúng spike a→f của §6.20.10: heading có `<a id>`, danh sách nguyên liệu `<strong>…</strong><br/>`
×4, đoạn văn thường, phân số thuần `<sup>1</sup>/<sub>3</sub>`, VÀ hỗn số `1<sup>1</sup>/<sub>3</sub>`
— đúng ca N-1 Tech Lead cảnh báo "`markdownify` mặc định cho `11/3` sai" phải verify KHÔNG xảy ra ở
đường này vì X1+X2 giữ nguyên `<sup>`/`<sub>` qua LLM, không cần chuyển đổi). Lưu vào
`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_5units.json` (kèm `README.md` ghi rõ
ngày/model/chi phí). **Chi phí thật đã tốn: `input_tokens=1456`, `output_tokens=459`,
`estimated_cost_usd=0.00062326`** (~0,06 cent USD, đúng 1 lần gọi). Kết quả: JSON sạch không fence,
đủ 5/5 id, giữ đúng `<strong>`/`<br/>`/`<sup>`/`<sub>`/`<a>`, dòng hỗn số ra đúng
`1<sup>1</sup>/<sub>3</sub>` (không gộp sai `11/3`). `tests/test_epub_batch_golden_fixture.py` (4
test mới) chạy `parse_epub_batch_response()` trên CHÍNH `raw_response_text` này — không viết tay.

### D. `run_epub_job()` + `_process_epub_chunk()` — MỚI HOÀN TOÀN, làm trong session này

`src/core/job_orchestrator.py`:
- `run_job()` Step 1: bỏ hẳn `raise EpubNotSupportedError` cho nhánh translate, thay bằng
  `if job.file_type == FileType.EPUB: return await self.run_epub_job(job, db_session)` — đặt SAU
  nhánh `parse_only` (S15-1), TRƯỚC Step 1..10 của PDF, đúng thứ tự re nhánh Architecture.md yêu cầu.
  `EpubNotSupportedError` vẫn giữ nguyên (class không xoá) — vẫn dùng cho nhánh Markdown parse-only +
  EPUB (`run_parse_only()`, S15-8, ngoài phạm vi bước này).
- `run_epub_job()` (10 bước E1-E10, Architecture.md 6.20.8): `EpubDocument.load()` **một lần duy
  nhất** (R6-02, sợi dây (2)→(7)) → `build_system_prompt()` + `build_epub_batch_prompt()` →
  `plan_epub_chunks()` → `_load_or_create_epub_chunks()` (resume BR-CHUNK-05, tương đương
  `_load_or_create_chunks()` của PDF nhưng dùng `unit_start`/`unit_end` thay `page_start`/`page_end`)
  → mỗi chunk chưa `completed` qua `_process_epub_chunk()` → **SAU MỖI CHUNK: copy nguyên thứ tự 3
  bước của `run_job()` Step 7** (`progress_tracker.update()` → Lớp 3 cost accumulator → check
  `cancel_requested`), không viết lại logic mới → merge mọi chunk `completed` (không chỉ chunk vừa
  chạy, R6-02 sợi dây (6)→(7)) → `doc.write_translated(translations, merged_path, bilingual=True)`
  → guard BR-EPUB-05 (X3) → `job.output_path`/`actual_cost` (= tổng `chunk.api_cost` THẬT, không
  ước tính)/`cost_source='metered'`/`finished_at`/`completed`.
- `_process_epub_chunk()`: mỗi request trong `chunk_plan.requests` chạy **tuần tự** (không AIMD, v1
  gọi API trực tiếp nên nhận `RateLimitError` thật qua `with_retry`), payload id ngắn cục bộ `0..N`,
  `provider.translate(payload_json, system_prompt, "en", "vi")`, parse response, **id thiếu → gọi lại
  RIÊNG LẺ đúng id đó (tối đa 1 vòng) → vẫn thiếu → `EpubBatchTranslationError`, chunk `failed`,
  TUYỆT ĐỐI không ghi chuỗi rỗng** (E-09). Ghi `data/processing/{job_id}/chunk_{i}/units.json` =
  `{unit_id: vi_html}`; `chunk.api_tokens_used`/`api_cost` = số đo THẬT từ `TranslationResult`.
- **`bilingual=True` hardcode** cho EPUB (CHỐT tại Architecture.md §6.20.11 mục 2, PM/user đã xác
  nhận qua AskUserQuestion) — KHÔNG đọc `Batch.output_mode` (mặc định "vi_only" ở tầng API cho CẢ
  PDF lẫn EPUB, dùng nguyên sẽ làm EPUB thành monolingual-by-default, ngược CHỐT). Chưa có UI nào cho
  phép chọn monolingual riêng cho EPUB ở bước này (task giao rõ: bước 3/3 mới làm UI).
- **BR-EPUB-05 guard** (`_check_epub_output_guard()`, theo đúng bảng 4 điều kiện X3 — bản SỬA, KHÔNG
  theo bản gốc §6.20.8 đã bị gạch): mở lại CHÍNH `merged_path` vừa ghi (không tin `translations` còn
  trong bộ nhớ), `bilingual=False` → tổng ký tự>0 + số unit khớp + ≥90% unit khác gốc;
  `bilingual=True` → tổng ký tự>0 + số unit khớp (nhờ `EpubDocument.load()` tự bỏ qua node
  `class="bb-vi"`) + số node `bb-vi` ≥90%×số unit input VÀ ≥90% cặp (gốc, bb-vi liền sau) có nội
  dung khác nhau. `src/services/epub_document.py::count_bb_vi_pairs(path)` (hàm mới) mở lại zip, đếm
  node `class="bb-vi"` và so nội dung với "bản gốc" tương ứng — xử lý riêng 2 hình dạng
  `_apply_translation()` sinh ra: `td`/`th` (bản dịch là `<span class="bb-vi">` CHÈN BÊN TRONG cùng
  ô, so với phần còn lại của ô sau khi bỏ `<br/>`+span) và mọi tag khác (bản dịch là `copy_node` được
  `insert_after` — so với node ANH EM liền trước). Không đạt → `job.status='failed'`.
- 3 sợi dây data lineage (§6.20.9) có test assert giá trị cụ thể (R6-02, không chỉ `assert_called()`):
  (2)→(7) unit_id nhất quán 1 lần `load()` duy nhất (test dịch 1 unit thành marker riêng, xác nhận nó
  nằm ĐÚNG vị trí trong file output, không lẫn sang đoạn khác); (6)→(7) merge đọc mọi chunk
  `completed` kể cả sau resume/crash giả lập (test crash chunk 2, resume, xác nhận cả 2 chunk có mặt
  trong output); (4)→(6) `system_prompt` thật gửi đi chứa marker `BB-EPUB-JSON-CONTRACT-X4`.
- **BR-EPUB-03**: đã grep xác nhận không có `subprocess`/`bilingual_book_maker` nào trong
  `run_epub_job()`/`_process_epub_chunk()` — điểm gọi LLM duy nhất là `provider.translate()`.

### Test mới (12 test, R6-02: assert nội dung/giá trị cụ thể, không chỉ "đã gọi")

`tests/integration/test_epub_translate_runner.py` (8 test, dùng `_FakeEpubProvider` xác định —
KHÔNG gọi API thật, khác `tests/test_epub_batch_golden_fixture.py`): happy path (`cost_source=
'metered'`, `actual_cost>0`, nội dung dịch + `bb-vi` thật có trong file output); marker contract JSON
trong `system_prompt` thật gửi đi; lineage unit_id→vị trí đúng; resume sau crash giữa chừng gộp đủ cả
2 chunk; id thiếu được gọi lại lẻ rồi thành công; id vẫn thiếu sau retry → chunk `failed` không ghi
rỗng; guard BR-EPUB-05 fail khi LLM trả nguyên văn tiếng Anh (không dịch gì); Lớp 3 dừng đúng giữa
chừng (`chunk_index > 0`) với `cost_source='metered'`. `tests/test_epub_batch_golden_fixture.py` (4
test, mục C ở trên).

### Kết quả chạy thật

```
uv run ruff check src/ tests/            → All checks passed!
uv run pytest tests/test_epub_document.py tests/test_chunking.py tests/test_epub_batch_prompt.py \
  tests/test_epub_batch_golden_fixture.py tests/integration/ -q
  → 239 passed
uv run pytest -q (toàn bộ suite)
  → 667 passed, 1 failed (89.65s)
```

1 fail: `tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`
— cùng 1 test pre-existing đã ghi nhận ở các CHANGELOG trước (không liên quan EPUB). Tổng pass tăng
từ 654 (baseline đo đầu session, đã gồm test của mục A/B/C uncommitted) → 667 = +13, khớp 12 test mới
của mục D cộng dao động nhỏ do 1 lần chạy trước đó có `1 error` do flake test-isolation
(`tests/integration/test_extract_terms_endpoint.py`, pass lại khi chạy riêng lẻ và khi chạy lại toàn
bộ suite — không tái diễn, không liên quan thay đổi của session này). **Không có regression mới.**

### File đã sửa/thêm trong session này (mục D + golden fixture mục C.3)

Sửa: `src/core/job_orchestrator.py` (import mới; `EpubBatchTranslationError`/`EpubEmptyOutputError`;
xoá nhánh raise cũ + dispatch `run_epub_job()`; thêm `run_epub_job()`, `_process_epub_chunk()`,
`_load_or_create_epub_chunks()`, `_check_epub_output_guard()`), `src/services/epub_document.py`
(thêm `count_bb_vi_pairs()`). Mới: `tests/integration/test_epub_translate_runner.py`,
`tests/test_epub_batch_golden_fixture.py`, `tests/fixtures/epub_llm/` (fixture + README.md).

Không sửa: `src/core/glossary_manager.py`, `estimate_job_cost_v2()` (chỉ đổi đầu vào ở
`cost_gate.py`, không sửa hàm), signature `provider.translate()`, `build_system_prompt()` hiện có
(chỉ nối thêm qua `build_epub_batch_prompt()`). Không làm UI/frontend.

### 3 điểm CHƯA RÕ RÀNG khi thực code — báo cáo PM, KHÔNG tự đoán/tự quyết

1. **E2/E3 (§6.20.8) mâu thuẫn nội bộ về việc có lọc glossary theo `full_text` hay không.** E2 ghi
   "lọc glossary theo tài liệu", nhưng pseudocode E3 lại gọi thẳng
   `build_system_prompt(glossary_manager, project_id=job.batch_id)` — hàm này **không có** tham số
   `only_terms_present_in`/`max_glossary_entries` (khác `build_prompt_text()`/`write_prompt_file()`
   của PDF, vốn có lọc). Đã code THEO ĐÚNG NGHĨA ĐEN pseudocode E3 (không lọc) vì brief cấm sửa
   `build_system_prompt()`. Hệ quả: `cost_gate.py::_estimate_epub_translation_cost()` ước
   `prompt_overhead_chars` từ prompt **CÓ lọc** (rẻ hơn), nhưng `run_epub_job()` gửi prompt **KHÔNG
   lọc** (glossary toàn dự án, có thể đắt hơn) — nếu 1 dự án có glossary lớn, đây là 1 dạng ƯỚC THẤP
   ở Lớp 2, ngược chiều §6.11.6 ("được ước cao, cấm ước thấp"). Chưa tự sửa vì không rõ đây là chủ ý
   (đơn giản hoá pseudocode) hay thiếu sót của Tech Lead — cần quyết định: thêm biến thể lọc riêng
   cho EPUB (không đụng `build_system_prompt()` hiện có) hay chấp nhận rủi ro ước thấp này.
2. **X3 guard `bilingual=True`, cặp `td`/`th`**: Architecture.md không mô tả cách so sánh "bản gốc"
   khi bản dịch được chèn LÀM CON của cùng 1 ô (`<span class="bb-vi">` bên trong `td`/`th`, khác hẳn
   hình dạng "node anh em" của mọi tag khác). Đã tự thiết kế cách so sánh (bỏ `<br/>`+span rồi lấy
   phần còn lại của ô làm "bản gốc") và ghi rõ trong docstring `count_bb_vi_pairs()` — đây là suy
   luận riêng của Dev, CHƯA qua Reviewer, có thể cần Tech Lead xác nhận lại.
3. **Y4 (`EpubUnitTooLargeError`) và lỗi DRM/parse khi CHẠY job (không phải lúc ước tính) không có
   broadcast WebSocket riêng** — các lỗi này raise trong `plan_epub_chunks()`/`EpubDocument.load()`
   TRƯỚC khi `job.status` được set `"translating"`, nên rơi vào catch-all cấp `_run_job_background()`
   (đã có sẵn, set `job.status="failed"` + `finished_at`) thay vì đường `_broadcast_job_failed()` có
   sẵn cho lỗi trong vòng lặp chunk. Hành vi DB đúng, chỉ thiếu WS event — chưa chạm dữ liệu thật (2
   file mẫu hiện có chưa có unit nào vượt `EPUB_UNIT_HARD_MAX_CHARS`, đúng ghi chú §6.20.11 mục 7),
   nên chưa tự thêm broadcast riêng để tránh đoán shape event ngoài Architecture.md.

### Trạng thái

**CHƯA báo "xong" (Protocol 7 R7-01)** — chưa spawn Reviewer thật trong session này. Toàn bộ nội
dung trên (kể cả phần A/B/C đã có sẵn khi bắt đầu session, đã tự đọc lại + chạy test/ruff nhưng KHÔNG
tính là đã review) cần Reviewer thật trước khi coi là xong, đặc biệt 3 điểm chưa rõ ràng ở mục trên.

---

## 2026-09-09 — Merge fix drift ngoại suy pivot dòng wrap (`_draw_block`) vào main

PM giao 1 task nền (`task_062a9bd5`) điều tra bug lố biên trang mà Dev phát hiện phụ khi làm Bug #8
round 2. Task chạy ở worktree riêng (`claude/strange-napier-988bad`, tách từ main lúc còn ở
`53e7847` — trước cả khi Bug #8/#9/#10 tồn tại), tự phát hiện brief ban đầu viện dẫn 1 premise không
tồn tại ở nhánh của nó (`src/utils/pdf_coords.py::insert_text_origin_fix` chưa có ở base đó), tự bỏ
qua và điều tra lại từ đầu — tìm ra 1 bug thật, độc lập, trong `_draw_block()`
(`src/postprocess/rotated_text_overlay.py`): pivot của mọi dòng wrap được ngoại suy CHỈ từ
`block.pivot` (`lines[0].origin`), nhưng dòng thật đầu tiên đôi khi là outlier thụt lề (verify trên
`rotated_text_p67_source.pdf`: dòng "Disaccharide" lệch ~77pt theo hướng đọc so với 16 dòng thật còn
lại) — kéo lệch cả khối, ăn dần margin phải/dưới trang, PyMuPDF âm thầm cắt chữ tràn (không lỗi,
không log). Đã qua 2 vòng Reviewer thật trong worktree đó, cả 2 đều APPROVE (chi tiết đầy đủ +
render pixmap xác nhận trực quan: xem `docs/review-report.md`).

**Merge thủ công vào main (không dùng `git merge`/cherry-pick nguyên nhánh)** — 2 lý do: (1) nhánh
lệch quá xa main (tách từ trước Bug #8/#9/#10), merge nguyên nhánh sẽ conflict lộn xộn ở
CHANGELOG.md/review-report.md (2 file đã phình to khác hẳn trên main từ lúc đó); (2) fix Bug #8 của
PM (gọi `insert_text_origin_fix(page, pivot)`) và fix của task này (đổi cách tính `pivot` từ
`origin_x/origin_y` sang `anchor_x/anchor_y`) SỬA ĐÚNG CÙNG 1 DÒNG trong `_draw_block()` — cherry-pick
máy móc sẽ conflict tại đó. PM tự ghép 2 lớp fix: tính `anchor_x/anchor_y` (sửa lệch neo dòng)
**trước**, rồi mới áp `insert_text_origin_fix` (sửa hệ toạ độ MediaBox/CropBox) lên kết quả — 2 fix
độc lập về mặt logic, không xung đột ý nghĩa.

**Verify sau khi ghép** (PM tự làm, không chỉ tin lại kết luận cũ của worktree kia vì code nền đã
khác — có thêm bước `insert_text_origin_fix`):
- Copy 2 test mới (`test_draw_block_anchors_wrapped_lines_at_the_blocks_real_left_margin`,
  `test_overlay_rotated_text_keeps_every_wrapped_line_within_page_bounds`) vào
  `tests/test_rotated_text_overlay.py` trên main — mọi helper/fixture cần thiết (`P67_SOURCE`,
  `NOTO_FONT_PATH`, `_VI_TRANSLATION_FITS`, `_build_babeldoc_output_stub`, ...) đã có sẵn từ Bug #8
  round 2, không cần thêm.
- Tự `sed`-revert tạm dòng `anchor_x/anchor_y` → `origin_x/origin_y` trong `_draw_block`, chạy lại
  `test_draw_block_anchors_wrapped_lines_at_the_blocks_real_left_margin` → **FAIL** đúng kỳ vọng,
  khôi phục lại bản đã ghép.
- `uv run pytest tests/test_rotated_text_overlay.py -q` → **13 passed** (11 test cũ + 2 test mới).
- `uv run pytest tests/ -q` (toàn bộ suite) → 1 lần đầu ra **3 failed** (cùng 3 test vừa thêm) —
  điều tra kỹ: chạy lại riêng file đó nhiều lần liên tiếp đều **13 passed**, `-p no:randomly` cũng
  cho **13 passed** toàn file theo đúng thứ tự — không tái hiện được lỗi. Kết luận: nhiễu nhất thời,
  nhiều khả năng do 1 session khác chạy test song song trên cùng máy tại đúng thời điểm đó (đã quan
  sát hiện tượng nhiều session cùng làm việc trên repo này xuyên suốt ngày), không phải lỗi logic
  của fix. **Chạy lại toàn bộ suite 2 lần sau đó: 671/671 pass cả 2 lần.**

Không tính vào giới hạn Protocol 3 (không phải vòng sửa lỗi sau reject — 2 vòng Reviewer đã hoàn tất
ở worktree gốc trước khi merge).

---

## 2026-09-09 — US-22 Bước 2/3 (EPUB Translation Engine) fix E2: lọc glossary theo `full_text`

PM giao bổ sung nhỏ: chính Dev tự nêu ở lần trước (xem mục "3 điểm chưa rõ ràng" cuối phần US-22
Bước 2/3 phía trên) rằng E2 (Architecture.md §6.20.9 dòng 3/4) yêu cầu glossary phải được lọc theo
`full_text` trước khi build system prompt cho nhánh EPUB, nhưng
`run_epub_job()` gọi `build_system_prompt(glossary_manager, project_id=job.batch_id)` KHÔNG truyền
bộ lọc — khác `cost_gate.py::_estimate_epub_translation_cost()` (có lọc qua `build_prompt_text(...,
only_terms_present_in=full_text)`) — vi phạm §6.11.6 (prompt thật gửi đi và prompt dùng ước chi phí
Lớp 2 phải cùng một tập glossary, nếu không Lớp 2 có thể ước THẤP hơn thật).

**Phát hiện khi sửa (khác PM brief)**: PM brief nói `build_system_prompt()`
(`src/core/prompt_builder.py:80`) "đã có sẵn" tham số `only_terms_present_in` — kiểm tra lại code
thực tế thì **KHÔNG đúng**: tham số đó chỉ tồn tại ở `build_prompt_text()`/`build_babeldoc_prompt_text()`
(2 hàm build prompt file cho pdf2zh/babeldoc), `build_system_prompt()` (dùng cho EPUB và cho
`overlay_rotated_text()`'s `glossary_prompt`) lúc đó KHÔNG có tham số này. Đã báo lại điểm này cho PM
ở cuối task thay vì âm thầm implement theo premise sai.

### Sửa

- `src/core/prompt_builder.py::build_system_prompt()` — thêm 2 tham số optional
  `only_terms_present_in: str | None = None` và `max_glossary_entries: int = 80` (mirror đúng
  `build_prompt_text()`), truyền xuống `glossary_manager.build_prompt_snippet(only_terms_present_in=...,
  max_entries=...)`. Mặc định `None` giữ NGUYÊN hành vi cũ (không lọc) cho caller hiện có
  (`overlay_rotated_text()`'s `glossary_prompt` ở `job_orchestrator.py` dòng ~698) — không đổi hành
  vi PDF. Đây là hiện thực hoá đúng cơ chế Architecture.md §6.20.9 dòng 4 đã mô tả sẵn
  ("`build_system_prompt(...)` với glossary đã lọc theo `full_text`"), không phải thay đổi kiến trúc
  mới — nên Dev tự thêm tham số này thay vì escalate Tech Lead.
- `src/core/job_orchestrator.py::run_epub_job()` — sửa lời gọi `build_system_prompt()` ở bước E2/E3,
  truyền `only_terms_present_in=doc.full_text()` (CÙNG một lần `load()` ở bước E1, không `load()`
  lại — tránh tái sinh Bug #5 dạng EPUB) và `max_glossary_entries=self._settings.max_glossary_entries_in_prompt`
  (CÙNG setting nhánh PDF đang dùng, khớp đúng cap mà `cost_gate.py` đã dùng khi ước). Xoá comment cũ
  giải thích lý do CHƯA sửa, thay bằng comment mô tả cơ chế đã sửa.

### Test

- `tests/integration/test_epub_translate_runner.py::test_run_epub_job_filters_glossary_by_full_text_matching_cost_gate`
  (mới) — assert 2 lớp, cả hai đều giá trị cụ thể (R6-02), không chỉ `assert_called()`:
  1. Spy trực tiếp trên `build_system_prompt()` (monkeypatch `src.core.job_orchestrator.build_system_prompt`,
     vẫn delegate xuống bản thật): `only_terms_present_in` nhận được PHẢI bằng đúng
     `EpubDocument.load(epub_path).full_text()`; `max_glossary_entries` PHẢI bằng đúng
     `settings.max_glossary_entries_in_prompt`.
  2. Nội dung `system_prompt` THẬT gửi cho `provider.translate()` (2 glossary entry thêm vào DB:
     `"flour"` — xuất hiện trong EPUB test fixture — và `"yeast"` — không xuất hiện): assert
     `"flour" in system_prompt` và `"yeast" not in system_prompt` cho MỌI lời gọi — chứng minh việc
     lọc có tác dụng thật, không chỉ tin lời gọi hàm đúng tham số. Test này FAIL trên code cũ (trước
     fix, `"yeast"` sẽ xuất hiện vì không lọc).

### Kết quả

- `ruff check` — pass (3 file sửa/thêm).
- `pytest tests/integration/test_epub_translate_runner.py -q` — 9 passed (8 cũ + 1 mới).
- `pytest tests/ -q` (toàn bộ suite) — kết quả dao động **668 passed/3 failed** ↔ **671 passed/0
  failed** giữa các lần chạy, luôn đúng 3 test cố định
  (`tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`,
  `::test_draw_block_anchors_wrapped_lines_at_the_blocks_real_left_margin`,
  `::test_overlay_rotated_text_keeps_every_wrapped_line_within_page_bounds`) khi fail. Điều tra:
  - File này Dev **không đụng tới** trong task này (`git diff HEAD` rỗng cho cả
    `src/postprocess/rotated_text_overlay.py` và `tests/test_rotated_text_overlay.py` — 2 file đã ở
    đúng trạng thái commit `636e046`).
  - Chạy riêng `tests/test_rotated_text_overlay.py` (đơn lẻ, không chung suite) — luôn **13 passed**,
    lặp lại nhiều lần.
  - Deselect đúng 1 test mới thêm → suite còn lại **670 passed/0 failed**; chạy lại suite ĐẦY ĐỦ
    (kể cả test mới) ngay sau đó → **671 passed/0 failed**, sạch hoàn toàn — chứng minh test mới
    KHÔNG phải nguyên nhân quyết định (nếu là nguyên nhân thật, có mặt nó phải fail nhất quán).
  - Đúng hiện tượng đã được ghi nhận vài giờ trước trong chính file này ở mục "Merge fix drift ngoại
    suy pivot dòng wrap vào main" ngay phía trên: PM đã từng gặp **3 failed** y hệt 3 test này 1 lần
    trong 1 lần chạy suite đầy đủ, điều tra không tái hiện được, kết luận nhiễu nhất thời (nghi do
    nhiều session chạy test song song trên cùng máy tại đúng thời điểm — RAM/CPU contention ảnh
    hưởng threshold margin <6pt của phép đo hình học trong test đó, không phải lỗi logic).
  - Kết luận: **668/671 → 671/671** khi so baseline "667 passed/1 failed" — số fail KHÔNG tăng do
    thay đổi của task này; 3 fail quan sát được là nhiễu môi trường đã biết trước, không liên quan
    tới `prompt_builder.py`/`job_orchestrator.py`/EPUB glossary filter.

### Trạng thái

**CHƯA báo "xong" (Protocol 7 R7-01)** — chưa spawn Reviewer thật trong session này cho thay đổi
này. Cần Reviewer duyệt riêng phần fix E2 này, đặc biệt: (1) điểm PM brief sai premise nêu trên, (2)
có cần lọc `max_glossary_entries` giống hệt cap của cost_gate hay không (Dev tự quyết định thêm, PM
brief chỉ yêu cầu `only_terms_present_in`), (3) nhiễu 3 test `rotated_text_overlay` nêu trên có thật
sự không liên quan hay cần điều tra sâu hơn.

## 2026-09-09 — US-22 Bước 2/3, vòng 2/3 Dev↔Reviewer: sửa 3 điểm Reviewer REJECT (vòng 1/3)

Reviewer REJECT vòng 1/3 (xem section review mới nhất trong `docs/review-report.md`, cuối file)
với 1 lỗi BLOCKING + 2 issue phụ. PM giao lại nguyên văn yêu cầu của Reviewer. Circuit breaker
Dev↔Reviewer: đã dùng 1/3 vòng trước khi bắt đầu task này.

### 1. BLOCKING — guard BR-EPUB-05 (`bilingual=True`) luôn fail trên EPUB thật

**Root cause (Reviewer đã xác định đúng)**: `_mark_bb_vi()` (`src/services/epub_document.py`)
giả định `node.get("class")` luôn là `list`, nhưng dưới builder XML (`features="xml"`, dùng CHÍNH
theo Y1), bs4 trả `class` dưới dạng CHUỖI khi node gốc EPUB thật có sẵn attribute `class` (rất phổ
biến, vd `class="noindent"` trên hầu hết `<p>` của `chapter01.html` sách mẫu Sourdough). Code cũ
`[*existing, "bb-vi"]` trên 1 chuỗi unpack thành TỪNG KÝ TỰ, hỏng attribute thành
`class="n o i n d e n t bb-vi"`.

**Fix**: thêm helper `_node_classes(node) -> list[str]` (chuẩn hoá `str`/`list`/`None` → luôn
`list[str]`), dùng trong CẢ `_has_bb_vi_class()` (đọc) lẫn `_mark_bb_vi()` (ghi — luôn set lại
`class` dưới dạng `list`, không phải chuỗi ghép tay, để bs4 tự serialize đúng).

**Phát hiện thêm khi verify lại trên file thật (KHÔNG nằm trong review-report.md gốc — Reviewer
chỉ soi ra bug ghi, chưa chạm tới bug đọc vì bug ghi đã chặn đường trước)**: sau khi sửa bug ghi ở
trên, `count_bb_vi_pairs()` (dùng bởi guard) VẪN fail — `soup.find_all(class_="bb-vi")` của bs4
4.15 tự nó KHÔNG khớp được node có NHIỀU class (vd `class="noindent bb-vi"`) khi đọc lại qua
builder XML: tự verify trực tiếp
`BeautifulSoup('<p class="noindent bb-vi">x</p>', "xml").find_all(class_="bb-vi")` trả về RỖNG.
Lý do (đọc source `bs4/filter.py::_attribute_match()`): bs4 chỉ thử "ghép lại cả chuỗi rồi so
khớp" khi giá trị GỐC là 1 `list` nhiều phần tử — với builder XML, giá trị đọc lại LUÔN là 1 chuỗi
đơn (`isinstance(..., list)` False), nên nhánh ghép-lại-rồi-so-sánh không bao giờ kích hoạt — so
khớp thất bại cho MỌI node có >1 class, tức đa số unit của sách thật. Sửa: thêm
`_find_bb_vi_nodes(root)` (predicate callable dùng `_node_classes()` đã chuẩn hoá) thay cho MỌI
lời gọi `find_all(class_=_BB_VI_CLASS)` trong `count_bb_vi_pairs()` (cả nhánh chính lẫn nhánh
`td`/`th`) — không phụ thuộc hành vi nội bộ này của bs4 nữa.

**Test mới** (`tests/test_epub_document.py`):
- `test_mark_bb_vi_preserves_preexisting_class_string_under_xml_parser` — dùng CHÍNH file
  Sourdough thật (không phải fixture tự dựng, đúng lý do 12 test cũ lọt qua bug này): dịch giả lập
  toàn bộ 384 unit (`f"VI:{text}"`, không gọi LLM — mirror đúng script live-verify của Reviewer),
  `write_translated(bilingual=True)`, xác nhận `class="noindent bb-vi"` đúng chuẩn (không phải
  `"n o i n d e n t bb-vi"`), xác nhận CHÍNH `soup.find_all(class_="bb-vi")` mặc định của bs4 THẤT
  BẠI trên node này (khẳng định chủ động bug lớp 2 vẫn "còn đó" về mặt hành vi bs4, phòng ai đó lỡ
  hoán đổi lại `_find_bb_vi_nodes()` thành `find_all(class_=...)` đơn giản trong tương lai),
  `count_bb_vi_pairs()` đếm đúng 384/384, và `_check_epub_output_guard(bilingual=True)` PASS không
  raise.
- `test_check_epub_output_guard_threshold_uses_ceil_not_truncate` — xem mục 3 dưới.

### 2. Y6 chưa đóng cho DeepL — `ConnectionException` không bắt được 5xx thật

`src/services/deepl_provider.py`: thêm nhánh trong `except deepl.DeepLException as exc:` — đọc
`exc.http_status_code` (field có trên MỌI `DeepLException`, tự đọc source `deepl==1.32.0` xác
nhận), nếu `>= 500` thì raise `ConnectionError` (transient) thay vì `TranslationProviderError`
(permanent) như cũ. 4xx và trường hợp `http_status_code is None` (lỗi không gắn với 1 response
HTTP cụ thể) vẫn giữ nguyên permanent — Y6 chỉ MỞ RỘNG tập transient, không nới lỏng cho lỗi client
thật.

**Test mới** (`tests/test_translation_providers.py`): `test_deepl_translate_5xx_is_transient`
(502 → `ConnectionError`), `test_deepl_translate_4xx_stays_permanent` (400 → vẫn
`TranslationProviderError`), `test_deepl_translate_exception_without_status_code_stays_permanent`
(`http_status_code=None` → vẫn permanent, không crash vì `None >= 500`).

### 3. Ngưỡng "≥90%" dùng `int()` truncate thay vì làm tròn lên

`src/core/job_orchestrator.py::_check_epub_output_guard()`: `min_required = max(1,
int(len(source_doc.units) * 0.9))` → `max(1, math.ceil(...))`. Với N=384 (sách thật): ngưỡng cũ
345 (89.84%, THẤP hơn 90% yêu cầu) → ngưỡng mới 346 (≥90% thật sự).

**Test mới**: `test_check_epub_output_guard_threshold_uses_ceil_not_truncate` — dịch ĐÚNG
345/384 unit thật của Sourdough (giữ nguyên 39 unit còn lại), xác nhận guard RAISE với ngưỡng mới
(trước fix sẽ PASS sai ở đúng ca biên này).

### Phát hiện thêm ngoài 3 điểm Reviewer yêu cầu — bug JSON "trailing garbage" (bắt được khi chạy live E2E full-book theo yêu cầu PM)

Khi chạy `run_epub_job()` THẬT (không mock) qua `JobOrchestrator` trên toàn bộ 384 unit/7 chunk
của Sourdough để verify guard đã sửa (yêu cầu PM, cũng đúng tinh thần Protocol 6 R6-03), job FAIL
**deterministic 2 lần liên tiếp** ở chunk 0 với lỗi `EpubBatchTranslationError` ("thiếu bản dịch
cho 1 unit sau 1 vòng gọi lại riêng lẻ") cho `ops/xhtml/chapter01.html#13`, dù nội dung đã dịch
đúng. Điều tra bằng cách gọi lại riêng unit này qua `ProviderFactory.create("deepseek", ...)` thật:
DeepSeek trả về 1 JSON object HỢP LỆ nhưng thừa đúng 1 ký tự `"` NGAY SAU dấu `}` đóng
(`raw_response_text` capture trong `tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_trailing_garbage.json`)
— `json.loads()` fail với `JSONDecodeError: Extra data`. `parse_epub_batch_response()` (thiết kế
CỐ Ý dung sai với phản hồi LLM không hoàn hảo — xem docstring hàm) trước đây coi MỌI lỗi
`JSONDecodeError` là hỏng hoàn toàn (`{}`) — vì lỗi lặp lại y hệt ở cả vòng gọi lại lẻ, unit này
luôn bị coi là thiếu ngay cả sau retry, chunk fail thật — **cùng loại rủi ro tài chính** mà bug
BLOCKING của vòng review này (guard BR-EPUB-05) được sinh ra để chặn, chỉ khác điểm lỗi trong
pipeline (đây là ở bước parse response, không phải bước ghi output).

**Fix**: `src/core/prompt_builder.py::parse_epub_batch_response()` — khi gặp `JSONDecodeError`
với `msg == "Extra data"`, thử parse lại đúng phần văn bản TRƯỚC vị trí lỗi (`text[:exc.pos]`); chỉ
khi phần đó cũng không phải JSON object hợp lệ mới trả `{}` như cũ. Lỗi `JSONDecodeError` vì lý do
KHÁC "Extra data" (vd JSON bị cắt cụt giữa chừng — hết `max_tokens`) vẫn trả `{}` như cũ, không nới
lỏng cho trường hợp hỏng thật.

**Test mới**: `tests/test_epub_batch_golden_fixture.py` (3 test, golden fixture thật — Protocol 5
mục 3, không viết tay) + `tests/test_epub_batch_prompt.py` (3 test biên bổ sung bằng chuỗi tổng
hợp: 1 ký tự thừa, prose thừa nhiều id, và JSON cắt cụt thật sự vẫn phải trả `{}`).

**Đây là phát hiện mới, KHÔNG nằm trong yêu cầu ban đầu của Reviewer/PM cho vòng 2/3 này** — báo rõ
để Reviewer biết cần review thêm phần này, không lẫn vào 3 điểm đã yêu cầu.

### Kết quả chạy thật

```
uv run ruff check src/ tests/          → All checks passed!
uv run pytest tests/ -q (2 lần độc lập) → 682 passed, 0 failed (cả 2 lần)
```
682 = baseline 671 (Reviewer xác nhận vòng 1/3) + 11 test mới (5 cho 3 điểm Reviewer yêu cầu + 6
cho phát hiện JSON trailing-garbage ngoài yêu cầu).

**Live E2E full-book THẬT** (yêu cầu PM, không chỉ tin unit test) — `run_epub_job()` qua
`JobOrchestrator` thật, provider DeepSeek thật, KHÔNG mock, trên chính file Sourdough
(384 unit / 7 chunk / 21 request):

```
job.status = 'completed'
job.cost_source = 'metered'
job.actual_cost = 0.07637542   (~7,6 cent USD)
job.total_units = 384
output_doc.units (guard bỏ qua bb-vi) = 384/384   -- KHỚP số unit gốc
'class="bb-vi"' + 'lang="vi"' có mặt trong chapter01.html
337 đoạn <p lang="vi"> tìm thấy, nội dung THẬT bằng tiếng Việt (khác "VI:" prefix giả của test)
```
Guard BR-EPUB-05 PASS đúng nghĩa lần đầu tiên trên dữ liệu thật, không raise `EpubEmptyOutputError`
— xác nhận trực tiếp bug BLOCKING đã hết, không chỉ tin lại unit test.

**Chi phí LLM thật đã tốn thêm trong vòng sửa này** (ngoài baseline Reviewer đã ghi nhận): 1 lần
gọi debug riêng unit #13 (~$0.0004) + 1 lần capture golden fixture trailing-garbage (~$0.00045) +
2 lần chạy `run_job()` full-book fail sớm ở chunk 0 (trước khi phát hiện + sửa bug JSON — chi phí
từng phần cho các request đã hoàn tất trong chunk 0 trước điểm fail, không được ghi vào
`job.actual_cost` vì chunk chưa `completed`; ước lượng dưới $0.02 dựa theo tỉ lệ 1/7 chunk của lần
chạy thành công cuối) + 1 lần chạy `run_job()` full-book THÀNH CÔNG ($0.07637542, số đo thật). Tổng
toàn bộ vòng sửa này ước tính dưới 10 cent USD.

### File đã sửa/thêm

Sửa: `src/services/epub_document.py` (`_node_classes()`, `_has_bb_vi_class()`, `_mark_bb_vi()`,
`_find_bb_vi_nodes()`, `count_bb_vi_pairs()`), `src/services/deepl_provider.py` (nhánh 5xx trong
`except deepl.DeepLException`), `src/core/job_orchestrator.py` (`math.ceil` cho `min_required`),
`src/core/prompt_builder.py` (`parse_epub_batch_response()` phục hồi từ trailing garbage).

Test sửa/thêm: `tests/test_epub_document.py` (+2), `tests/test_translation_providers.py` (+3),
`tests/test_epub_batch_golden_fixture.py` (+3, + fixture mới
`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_trailing_garbage.json` +
`README.md` append), `tests/test_epub_batch_prompt.py` (+3).

### Trạng thái

**CHƯA báo "xong"** — cần Reviewer duyệt lại (Protocol 3, vòng 2/3 Dev↔Reviewer, giới hạn cuối là
vòng 3/3). Đặc biệt cần Reviewer tự đánh giá: (1) 3 điểm yêu cầu ban đầu đã sửa đúng chưa, (2) phát
hiện JSON trailing-garbage ngoài yêu cầu — fix có đủ chặt không (chỉ nới lỏng đúng 1 dạng lỗi cụ
thể "Extra data", giữ nguyên strict cho JSON hỏng thật), R5-04 checklist riêng cho
`deepl_provider.py` (external contract) áp dụng lại cho nhánh 5xx mới.

## US-22 EPUB — Fix Bug #EPUB-B2-1 (cost variance) + Bug #EPUB-4 (mất dấu tiếng Việt) — sau QA vòng 1/5 (2026-09-09)

Implement đúng theo spec Tech Lead ở `docs/Architecture.md` §6.20.13 (toàn bộ §6.20.13.0 → .10).
5 phần theo brief PM, đủ cả 5, theo đúng thứ tự bắt buộc §6.20.13.9.

### 1. Fix root cause #EPUB-4 (V-1 — prompt tự dạy model bỏ dấu)

`src/core/prompt_builder.py`: `_EPUB_BATCH_ONE_SHOT_EXAMPLE` (dòng ~427-433) — phần "Dau ra" đổi
từ `"bot mi"`/`"muoi"`/`"nuong o 350F"` (không dấu) thành `"bột mì"`/`"muối"`/`"nướng ở 350F"` (có
dấu, NFC). Phần "Dau vao" (tiếng Anh) giữ nguyên. Thêm rule 7 vào `_EPUB_BATCH_CONTRACT` (sau rule
6): yêu cầu tường minh bản dịch phải là tiếng Việt CÓ DẤU đầy đủ, kèm ví dụ có dấu ngay trong rule
(để không tự rơi vào chính cái bẫy V-1 khi mô tả suông về dấu). Không đổi phần còn lại của contract
sang tiếng Việt có dấu (đánh đổi có tính được theo §6.20.13.4 mục 3: overhead tăng < $0,001/sách).

### 2. Fix cost estimate undercounting (C-2, Protocol 6 data lineage)

`src/core/cost_gate.py::_estimate_epub_translation_cost()` — trước fix đo `prompt_overhead_chars`
bằng `build_prompt_text()` (prompt của NHÁNH PDF, có placeholder `${text}`, KHÔNG PHẢI chuỗi thật
gửi cho LLM ở nhánh EPUB). Sửa: đo đúng `build_epub_batch_prompt(await build_system_prompt(...))`
— CHÍNH artifact mà `_process_epub_chunk()` (`job_orchestrator.py`) gửi thật, không còn trừ
`len("${text}")` (chuỗi EPUB không có placeholder này). Nhánh PDF không đổi 1 dòng.

### 3. Trần số request phụ cho vòng gọi lại thiếu id (fix C-1)

`src/core/chunking.py`: 2 hằng số mới cạnh `EPUB_REQUEST_CHAR_BUDGET` — `EPUB_MAX_SINGLE_ID_RETRIES
= 5` (⚠️ ASSUMED) và `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE = 6` (⚠️ ASSUMED). `_process_epub_chunk()`:
`len(missing_ids) <= 5` giữ nguyên pattern gọi lại riêng lẻ cũ; `> 5` gọi lại NGUYÊN request đó
đúng 1 lần thay vì tối đa ~18 request lẻ. `extra_requests` là quota CHUNG cho cả retry-thiếu-id và
retry-mất-dấu (§6.20.13.5) trong cùng 1 slice, không cộng dồn hai cơ chế.

### 4. Guard runaway per-request (Bug #EPUB-B2-1, fix C-3) + Lớp 4 cost cap

`src/core/cost_estimator.py`: thêm `EPUB_RUNAWAY_OUTPUT_FACTOR = 3.0` (⚠️ ASSUMED), 
`EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS = 1500` (⚠️ ASSUMED), `epub_expected_output_tokens()` (tái dùng
`VI_CHAR_EXPANSION`/`CHARS_PER_TOKEN_VI` đã có, không viết công thức thứ hai) và
`is_runaway_output()`. `job_orchestrator.py::_process_epub_chunk()` gọi ngay sau mỗi request chính
(không phải các retry): runaway + `parse_epub_batch_response()` đủ id hợp lệ (R-a) → GIỮ kết quả,
chỉ ghi nhận anomaly; runaway + thiếu id/hỏng (R-b) → `EpubRequestRunawayError` mới, abort NGAY
(không tự động retry — brief câu hỏi 2: có, retry sau runaway hỏng là chính con đường khuếch đại
C-1, xác suất thành công thấp nhất).

Lớp 4 (§6.20.13.2, không phụ thuộc ngưỡng ⚠️ ASSUMED nào — lưới an toàn CHÍNH): `_process_epub_chunk()`
đổi signature, thêm tham số có tên `cost_budget_remaining: float | None`; kiểm tra SAU MỖI lần cộng
`total_cost` (request chính lẫn mọi retry) — vượt ngân sách còn lại cho CHUNK ĐANG CHẠY (không phải
cả job) → ghi nhận `chunk.api_tokens_used`/`api_cost`/`status="failed"`/`output_path=None` (Protocol
6, không mất dấu vết tài chính) rồi raise `EpubChunkCostCapExceeded` mới. `run_epub_job()` bắt riêng
exception này TRƯỚC `except Exception` chung, đi vào đúng nhánh `cost_capped` đã có (không tạo
trạng thái mới). `effective_cap` được tính 1 LẦN ở đầu vòng lặp mỗi chunk, dùng lại cho cả Lớp 4
(trước khi xử lý chunk) và Lớp 3 (sau khi xử lý chunk) — không viết công thức trần thứ hai. Mức
"vượt trần tối đa để lọt" giảm từ ~1 chunk xuống ~1 request (~2,7×).

### 5. Guard mất dấu 2 tầng (Bug #EPUB-4)

Module mới `src/core/text_quality.py`: `strip_html_for_measure()`, `diacritic_ratio()` (NFC-
normalize TRƯỚC khi đếm — bẫy kỹ thuật §6.20.13.5 cảnh báo rõ: chuỗi tổ hợp NFD sẽ cho ratio sai về
0 nếu không normalize trước), 4 hằng số ⚠️ ASSUMED: `EPUB_DIACRITIC_MIN_LETTERS_REQUEST=200`/
`EPUB_DIACRITIC_RATIO_REQUEST=0.08` (tầng 1 — mức REQUEST, đo gộp toàn bộ `parsed` sau khi đã xử lý
xong id thiếu) và `EPUB_DIACRITIC_MIN_LETTERS_UNIT=40`/`EPUB_DIACRITIC_RATIO_UNIT=0.02` (tầng 2 —
mức UNIT, bắt phần sót lại). Tầng 1 hỏng → gọi lại NGUYÊN request 1 lần (dùng chung quota
`EPUB_MAX_EXTRA_REQUESTS_PER_SLICE`); ratio bản retry cao hơn mới dùng, không thì giữ bản đầu. Tầng
2 hỏng → gọi lại RIÊNG LẺ đúng unit đó, tối đa 1 lần, dùng CHUNG helper `_retry_single_unit()` với
cơ chế thiếu-id ở phần 3 (2 cơ chế TÁCH vòng lặp nhưng CHIA SẺ helper, theo đúng "CHỐT" của
§6.20.13.5 — 2 điều kiện kích hoạt ở 2 thời điểm khác nhau, gộp cứng là lặp lại kiểu lỗi "một biến,
hai ý nghĩa" của Bug #5). Sau retry vẫn thiếu dấu → CHẤP NHẬN + ghi nhận, KHÔNG fail chunk (quyết
định (a) của Tech Lead — mất dấu là lỗi chất lượng cục bộ, không phải lỗi phá huỷ nội dung như
E-09).

Ghi nhận anomaly (§6.20.13.7, trả lời câu hỏi 4 brief): `chunk_dir/anomalies.json` (chỉ ghi khi có
≥1 anomaly: `runaway_requests`/`low_diacritic_requests`/`low_diacritic_units`) +
`chunk_dir/requests.jsonl` (bắt buộc, 1 dòng cho MỌI request chính — payload_chars/input_tokens/
output_tokens/ratio/diacritic_ratio — dữ liệu để chốt lại các ngưỡng ⚠️ ASSUMED ở vòng QA sau) +
1 dòng `logger.warning()` mỗi anomaly (job.id + chunk_index + loại). Không đụng `job.error_message`
khi job vẫn `completed`.

### Test mới

- `tests/test_text_quality.py` (7 test): `strip_html_for_measure()`/`diacritic_ratio()` — strip
  tag+attribute, ratio cao/thấp/rỗng, bẫy NFD→NFC, false-positive thuật ngữ Anh, ngưỡng biên.
- `tests/test_epub_cost_gate.py` (2 test): R6-02 — `prompt_overhead_chars` của Lớp 2 BẰNG đúng
  `len(build_epub_batch_prompt(build_system_prompt(...)))` mà `_process_epub_chunk()` thực nhận
  trên CÙNG job/glossary (không chỉ assert đã gọi); regression guard overhead mới > overhead theo
  công thức cũ (`build_prompt_text()`).
- `tests/test_epub_runaway_guard.py` (5 test): `epub_expected_output_tokens()`/`is_runaway_output()`
  — dùng chung công thức estimator, false/true theo factor, floor cho payload nhỏ, biên đúng ngưỡng.
- `tests/integration/test_epub_translate_guards.py` (9 test, `_ControllableEpubProvider` kiểm soát
  chính xác `output_tokens`/nội dung trả về từng lần gọi): >5 id thiếu dùng đúng 1 lần gọi lại
  nguyên request (không phải N lần lẻ); vẫn thiếu sau đó → fail chunk đúng 2 lần gọi (không vô hạn);
  R-a runaway giữ kết quả + anomalies.json/requests.jsonl ghi đúng; R-b runaway+thiếu id → abort
  ngay, không retry; tầng 1 mất dấu retry cải thiện → dùng bản retry; tầng 1 retry không cải thiện →
  giữ bản đầu (không đổi lấy thứ tệ hơn); tầng 2 mất dấu unit retry resolved=True; tầng 2 retry vẫn
  không dấu → resolved=False nhưng KHÔNG fail chunk; Lớp 4 dừng giữa chừng chunk đầu, chunk đó
  `failed`/`api_cost>0`/`output_path=None`, đúng 1 lần gọi (G-4).
- `tests/integration/test_epub_translate_runner.py`: sửa 1 test cũ
  (`test_run_epub_job_stops_at_cost_capped_mid_book_with_metered_cost` →
  `test_run_epub_job_stops_at_cost_capped_via_layer4_mid_first_chunk`) — hành vi CŨ (Lớp 3 để 1
  chunk hoàn tất trọn vẹn dù đã vượt trần, rồi mới dừng) không còn đạt được nữa sau khi thêm Lớp 4 —
  đây là thay đổi hành vi CÓ CHỦ ĐÍCH của chính fix này, không phải regression. Ghi chú thêm trong
  test: với nhánh EPUB, do Lớp 4 dùng CHUNG `effective_cap` với Lớp 3 và kiểm tra sớm hơn (trong-
  chunk thay vì hậu-chunk), Lớp 4 luôn trigger trước khi Lớp 3 có cơ hội tự trigger độc lập — Lớp 3
  vẫn giữ nguyên trong code làm lưới phụ (dùng chung khung với nhánh PDF ở `run_job()` không có Lớp
  4), nhưng không còn kịch bản nào trên nhánh EPUB để viết test "Lớp 3 tự trigger" tách biệt Lớp 4
  nữa — không thêm test giả cho kịch bản không còn đạt được.

### Kết quả chạy thật

```
uv run ruff check src/ tests/  → All checks passed!
uv run pytest tests/ -q        → 705 passed, 0 failed
```
705 = baseline 682 (đã xác nhận trước khi bắt đầu, khớp con số PM cho trong brief) + 23 test mới
(7 + 2 + 5 + 9, đã liệt kê ở trên) + 0 net change cho test cũ bị sửa (1 sửa tại chỗ, không xoá/thêm
số lượng).

Không chạy live E2E thật (real API) cho vòng sửa này — task PM cho phép tuỳ chọn, không bắt buộc;
cân nhắc chi phí + brief đã nói rõ 5 phần chỉ cần code đúng logic + dùng đúng số ⚠️ ASSUMED Tech Lead
đã cho, không cần tự đo lại bằng tiền thật.

### File đã sửa/thêm

Sửa: `src/core/prompt_builder.py` (one-shot example + rule 7), `src/core/cost_gate.py`
(`_estimate_epub_translation_cost()`), `src/core/chunking.py` (2 hằng số mới), `src/core/
cost_estimator.py` (`EPUB_RUNAWAY_OUTPUT_FACTOR`/`EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS`/
`epub_expected_output_tokens()`/`is_runaway_output()`), `src/core/job_orchestrator.py`
(`EpubChunkCostCapExceeded`/`EpubRequestRunawayError` mới; `_retry_single_unit()`/
`_retry_whole_epub_request()` helper mới; `_process_epub_chunk()` viết lại — Lớp 4, trần request
phụ, runaway, guard mất dấu 2 tầng, anomalies/requests log; `run_epub_job()` — tính `effective_cap`
1 lần/vòng lặp, nhánh bắt `EpubChunkCostCapExceeded` riêng).

Thêm: `src/core/text_quality.py`, `tests/test_text_quality.py`, `tests/test_epub_cost_gate.py`,
`tests/test_epub_runaway_guard.py`, `tests/integration/test_epub_translate_guards.py`.

### Trạng thái

**CHƯA báo "xong"/"sẵn sàng release"** — chưa có Reviewer thật review trong session này (R7-01).
Không tự review, dừng lại ở đây theo đúng brief PM, chờ PM giao việc cho Reviewer riêng.

Không có điểm nào của spec Tech Lead §6.20.13 không rõ/không khớp code thật khi implement — đọc
toàn bộ §6.20.13.0 → .10 trước khi viết code, mọi tham chiếu dòng/tên hàm trong spec khớp đúng với
code thật tại thời điểm implement. 2 quyết định kỹ thuật thuần (không ảnh hưởng threshold/hành vi
nghiệp vụ) tự chọn theo convention: (1) thêm helper `_retry_whole_epub_request()` để DRY hoá 2 nơi
gọi lại nguyên request (fix C-1 nhánh >5 id thiếu, và tầng 1 guard mất dấu) — spec chỉ bắt buộc chia
sẻ helper cho retry-đơn-lẻ, không cấm thêm helper tương tự cho retry-nguyên-request; (2) hàm
`epub_expected_output_tokens()` tách riêng khỏi `is_runaway_output()` để nơi ghi `requests.jsonl`
tính lại đúng `ratio` mà không viết công thức thứ hai — spec chỉ đưa code mẫu inline, việc tách hàm
là chi tiết implement thuần tuý.

Known limitation đã có sẵn trong spec (không phải bug mới, giữ nguyên hành vi hiện có của mọi chunk
`failed` ở nhánh PDF): tiền đã tiêu cho phần dở dang của 1 chunk bị Lớp 4 chặn giữa chừng sẽ bị
GHI ĐÈ (không cộng dồn) nếu user bấm Retry — `retry_job()` reset chunk về `pending` và lần chạy mới
gán đè `chunk.api_cost`, không phải cộng dồn (§6.20.13.2).

---

## Fix Bug #EPUB-B2-3 — mất id khi DeepSeek trả nhiều object JSON top-level rời rạc (2026-09-10)

### Root cause

QA vòng 2/5 (`docs/test-report.md`, mục "Bug #EPUB-B2-3") phát hiện + tái lập 2/2 lần trên sách
Sourdough thật: DeepSeek đôi khi trả về batch reply dưới dạng **nhiều object JSON top-level rời rạc
nối tiếp nhau** (mỗi object 1 hoặc vài id, phân tách bằng newline — ví dụ `{"0": "..."}\n{"1":
"..."}\n...\n{"10": "..."}`) thay vì 1 object duy nhất gồm đủ key. Nhánh xử lý cũ trong
`parse_epub_batch_response()` (`src/core/prompt_builder.py`) cho lỗi `json.JSONDecodeError` với
`exc.msg == "Extra data"` chỉ parse lại `text[:exc.pos]` — tức CHỈ giữ object ĐẦU TIÊN, âm thầm vứt
bỏ mọi id trong các object sau. Với ca QA log được (11 id kỳ vọng, object đầu chỉ có id "0"), 10 id
còn lại — đã dịch đúng, ĐÃ TRẢ TIỀN — bị coi là "thiếu", kích hoạt gọi lại nguyên request (C-1), rồi
DeepSeek lặp lại đúng kiểu tách-object đó ở lần gọi lại → vẫn thiếu đúng số id đó → chunk fail vĩnh
viễn (E-09) dù nội dung đã dịch xong và đúng.

Nhánh cũ (1 dấu `"` thừa sau `}` hợp lệ, fix trước đó cho 1 unit riêng lẻ) thực chất là 1 TRƯỜNG HỢP
ĐẶC BIỆT của cùng 1 vấn đề tổng quát hơn (object thứ 2 trở đi không parse được) — chỉ khác ở chỗ
"phần sau" trong ca cũ là rác thật (1 ký tự), còn ở Bug #EPUB-B2-3 "phần sau" là các object JSON
HỢP LỆ khác chứa dữ liệu thật cần giữ lại.

### Fix

`parse_epub_batch_response()` (`src/core/prompt_builder.py`) — thay nhánh "Extra data" cũ bằng hàm
`_decode_concatenated_json_objects()` mới: vòng lặp `json.JSONDecoder().raw_decode()` liên tục trên
phần còn lại của chuỗi (bỏ qua whitespace giữa các object), gộp TẤT CẢ object JSON top-level tìm
được vào 1 dict bằng `dict.update()` theo đúng thứ tự xuất hiện trong text, dừng khi hết chuỗi hoặc
phần còn lại không parse được nữa (phần không parse được coi là rác, bỏ qua — giữ đúng tinh thần cũ
"dung sai với phản hồi LLM không hoàn hảo", không nới lỏng để chấp nhận rác thật thành dữ liệu giả).
Ca cũ (1 dấu `"` thừa) giờ là N=1 của vòng lặp tổng quát này — không viết 2 nhánh riêng.

**Quyết định key trùng nhau**: nếu 2 object merge có CÙNG 1 key, object xuất hiện SAU trong text
thắng (`dict.update()` tuần tự, đúng thứ tự xuất hiện) — chưa có bằng chứng thực tế nào cho thấy
DeepSeek lặp lại 1 key với câu trả lời TỆ HƠN ở lần sau, và cách này giữ logic merge đơn giản nhất
có thể; sẽ xem lại nếu có ca thật cho thấy điều ngược lại.

**Giá trị JSON top-level không phải object** (vd 1 số/list lạc vào giữa 2 object dict hợp lệ) bị bỏ
qua trong lúc merge, không làm crash vòng lặp và không làm mất các object dict hợp lệ khác.

### Golden fixture — giới hạn phải escalate (Protocol 5 R5-01 mở rộng)

PM brief chỉ định dùng nguyên văn raw response thật đã log tại
`.../scratchpad/qa_round2/diagnostic_parse_calls.jsonl` để làm golden fixture. Đọc kỹ file này phát
hiện: script log của QA (`test_live_epub_diagnostic.py`) **chỉ ghi `raw_text[:300]` và
`raw_text[-300:]`**, KHÔNG BAO GIỜ ghi toàn bộ `raw_text` (2886 ký tự cho call_no=5, entry khớp mô
tả bug — 11 id kỳ vọng, 10 id thiếu, `parsed_count=1` trước fix). Không có bất kỳ nơi nào khác trong
scratchpad (`full_run.log`, `tmp_live*/`, `qa.db`) lưu lại full raw text. Dev đã thử tự chạy live 1
lần để tự capture đầy đủ (Protocol 5 R5-02 — spike verification) bằng
`.../scratchpad/dev_spike/capture_full_raw.py` (mirror `test_live_epub_diagnostic.py` nhưng log
`raw_text_full` không cắt), nhưng bị **auto-mode financial-action classifier chặn** (lệnh gọi API
DeepSeek thật = tốn tiền thật, cần permission người dùng theo safety rules, không được tự bypass).

Vì vậy `tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_multi_json_object_partial_capture.json`
là fixture **"partial capture"**, KHÔNG phải golden fixture đầy đủ đúng nghĩa Protocol 5 mục 3 —
tự đánh dấu rõ trong field `protocol_5_status` của chính file JSON: giữ nguyên byte THẬT cho phần
đầu id "0" (294 ký tự đầu, từ `raw_text_head`) và toàn bộ id "9"/"10" (nằm trọn trong 300 ký tự cuối
`raw_text_tail`, THẬT 100%); phần còn lại (đuôi giá trị id "0", toàn bộ id "1".."8") là placeholder
được gắn nhãn rõ ràng trong chính nội dung fixture, KHÔNG giả vờ là dữ liệu thật. Test dùng fixture
này (`tests/test_epub_batch_golden_fixture.py`, 4 test mới) verify đúng thuật toán merge trên hình
dạng ĐÃ XÁC NHẬN THẬT (nhiều object top-level rời rạc nối tiếp) và đúng nội dung ở các đoạn THẬT
(id 0 prefix, id 9, id 10) — không chứng minh nội dung dịch thật của id 1-8 (không ai biết, kể cả
QA, vì chưa từng được lưu lại).

**Escalate lên PM/Tech Lead**: cần 1 trong hai để có golden fixture đầy đủ đúng chuẩn — (a) tìm lại
full raw text nếu QA có lưu ở nơi khác ngoài scratchpad đã kiểm tra, hoặc (b) user cho phép Dev chạy
1 lần live call thật (~vài phần nghìn USD, đã có `capture_full_raw.py` sẵn sàng chạy) để tự capture
lại. Không blocking cho phần fix logic (đã có test tổng quát bảo vệ đúng thuật toán bằng chuỗi tổng
hợp — xem mục Test mới), chỉ blocking cho việc có 1 bằng chứng golden-fixture-đầy-đủ đúng nghĩa đen
của Protocol 5 cho riêng hình dạng phản hồi này.

### Test mới

- `tests/test_epub_batch_prompt.py` (5 test mới, chuỗi tổng hợp — kiểm logic thuật toán merge tổng
  quát, không phụ thuộc dữ liệu thật của 1 lần gọi cụ thể): gộp nhiều object top-level rời rạc (2
  object và 11 object — đúng dạng cụ thể QA quan sát được, 1 object/id); key trùng → object sau
  thắng; rác thật sau vài object hợp lệ → giữ phần đã parse được, không crash, không "đoán" nội dung
  rác; 1 giá trị JSON hợp lệ nhưng không phải object (số) lạc giữa 2 object dict → bị bỏ qua, không
  làm mất 2 object dict hợp lệ.
- `tests/test_epub_batch_golden_fixture.py` (4 test mới, dùng fixture "partial capture" nói trên):
  xác nhận fixture tự gắn nhãn KHÔNG phải golden fixture đầy đủ + tự làm `json.loads()` thô fail
  đúng kiểu "Extra data"; merge đủ 11/11 id; giữ đúng nguyên văn các đoạn THẬT (id 0 prefix, id 9,
  id 10); loại bỏ đúng 1 key giả `_qa_log_tail_fragment_not_an_expected_id` (dùng để giữ nguyên byte
  that của đoạn nối giữa 2 cửa sổ 300-ký-tự QA đã log, không thuộc id nào) — không lọt vào kết quả.
- Test case cũ (`test_parse_recovers_single_trailing_character_after_valid_json`,
  `test_trailing_garbage_fixture_file_exists_and_was_a_real_call`,
  `test_raw_response_text_is_genuinely_malformed_before_parser_fix`,
  `test_parse_epub_batch_response_recovers_from_trailing_garbage`) chạy lại PASS y nguyên, không
  sửa — xác nhận không regression cho ca 1 dấu `"` thừa.

### Kết quả chạy thật

```
uv run ruff check src/ tests/  → All checks passed!
uv run pytest tests/ -q        → 714 passed, 0 failed
```
714 = baseline 705 (CHANGELOG entry gần nhất, đã xác nhận khớp) + 9 test mới (5 +
4, đã liệt kê ở trên).

Không chạy live E2E full-book thật cho fix này (bị chặn bởi auto-mode classifier như đã nêu ở mục
Golden fixture) — logic fix đã được verify qua fixture "partial capture" + test tổng hợp; hành vi
model có còn lặp lại kiểu tách-object hay không nằm ngoài tầm kiểm soát của fix này.

### File đã sửa/thêm

Sửa: `src/core/prompt_builder.py` (`parse_epub_batch_response()` viết lại nhánh "Extra data" thành
`_decode_concatenated_json_objects()`), `tests/test_epub_batch_prompt.py`,
`tests/test_epub_batch_golden_fixture.py`, `tests/fixtures/epub_llm/README.md`.

Thêm: `tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_multi_json_object_partial_capture.json`.

### Trạng thái

**CHƯA báo "xong"/"sẵn sàng release"** — chưa có Reviewer thật review trong session này (R7-01).
Không tự review, dừng ở đây theo đúng brief PM, chờ PM giao việc cho Reviewer riêng.

Không động tới guard runaway (C-3) hay guard mất dấu (`text_quality.py`) — đúng phạm vi brief, cả 2
không liên quan tới bug này.

**Cần PM quyết định trước khi đóng bug này hoàn toàn**: có cho phép Dev chạy 1 live call thật để có
golden fixture đầy đủ hay không (xem mục Golden fixture ở trên) — không phải lỗi thiết kế/logic, mà
là giới hạn dữ liệu QA đã log + giới hạn permission môi trường Dev đang chạy.

## Increment 2026-09-10 — Golden fixture Bug #EPUB-B2-3: hoàn thiện qua live call thật (PM đã duyệt)

**Bối cảnh**: tiếp nối entry ngay phía trên (fix `parse_epub_batch_response()`) — phần việc còn lại
duy nhất là golden fixture đầy đủ, bị chặn trước đó vì gọi API DeepSeek thật là hành động tốn tiền
cần permission người dùng. PM đã duyệt riêng 1 lần gọi (chi phí ước tính dưới 1 cent USD) trong
phiên này.

**Kết quả: TÁI HIỆN THÀNH CÔNG ngay ở lần gọi đầu tiên** (1/5 attempt cho phép). Script capture
(`plan_epub_chunks()` thật trên sách Sourdough → xác nhận đúng chunk 1, request slice unit index
(45, 55) = 11 unit `ops/xhtml/chapter01.html#36`..`#46`, khớp chính xác ví dụ QA đã trích
`'ops/xhtml/chapter01.html#37'` trong `docs/test-report.md`) gọi trực tiếp
`ProviderFactory.create("deepseek", settings).translate()` với đúng payload/system_prompt như
`_process_epub_chunk()` dùng thật. DeepSeek trả về đúng 11 object JSON top-level rời rạc nối tiếp
nhau bằng dấu xuống dòng — `json.loads()` thô fail với `Extra data at pos 802`, đúng hình dạng lỗi
đã báo cáo. Toàn bộ 11 id có nội dung dịch tiếng Việt có dấu đầy đủ, không cần placeholder.

**Chi phí thật đã phát sinh (đã được PM duyệt riêng)**: `input_tokens=1994`, `output_tokens=1279`,
**`estimated_cost_usd=0.00128282`** (~0,13 cent USD), đúng 1 lần gọi API — không cần dùng hết 5
lần cho phép.

**Fixture cuối cùng dùng cho test**:
`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_multi_json_object.json` (mới, đầy
đủ, byte-for-byte thật 100% cho cả 11 id) — thay thế hoàn toàn
`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_ch1_multi_json_object_partial_capture.json`
(đã XOÁ khỏi repo). `tests/test_epub_batch_golden_fixture.py`: 3 test cũ dùng fixture cũ được sửa
để dùng fixture mới với assertion nội dung thật (id "0" đầu, id "2" có `<em>`/`<a id=...>`, id
"9"/"10" cuối) thay vì assertion "tự gắn nhãn partial"; không xoá test nào, không thêm/bớt số
lượng test (714 → vẫn 714 sau khi chỉ đổi fixture). `tests/fixtures/epub_llm/README.md` (APPEND):
thêm ghi chú "CẬP NHẬT 2026-09-10" vào mục fixture cũ (giữ nguyên lịch sử, không xoá — Protocol 1
R7-03) trỏ sang mục mới, và thêm hẳn 1 mục mới ở cuối file mô tả fixture đầy đủ.

**Kết quả chạy thật sau khi đổi fixture**:
```
uv run ruff check src/ tests/  → All checks passed!
uv run pytest tests/ -q        → 714 passed, 0 failed
```

**Không động tới** `_decode_concatenated_json_objects()`/`parse_epub_batch_response()` — chỉ thay
fixture + test/README tham chiếu fixture, đúng phạm vi PM giao.

**Trạng thái**: đây CHỈ là hoàn thiện golden fixture cho Bug #EPUB-B2-3, KHÔNG phải "xong US-22 Bước
2/3" hay "sẵn sàng release" — chưa có Reviewer thật review trong phiên này (R7-01), phần Reviewer
cho toàn bộ fix Bug #EPUB-B2-3 (bao gồm cả thay đổi fixture này) vẫn do PM giao riêng sau, không tự
báo cáo hoàn tất ở đây.

---

## Fix Bug #EPUB-B2-4 (2026-09-10) — Dev↔QA vòng 4/5, tổng quát hoá `_decode_concatenated_json_objects()`

**Bối cảnh**: QA vòng 3/5 (`docs/test-report.md`, mục "Bug #EPUB-B2-4") phát hiện **CÙNG HỌ LỖI**
với Bug #EPUB-B2-3 (DeepSeek trả nhiều JSON object top-level rời rạc thay vì 1 object gộp đủ id)
nhưng **BIẾN THỂ KHÁC**: lần này 32 object nối nhau bằng **dấu phẩy** (`}, {`) thay vì xuống dòng.
Fix B2-3 trước đó chỉ `str.lstrip()`/skip whitespace giữa 2 lần `raw_decode()`, nên dừng lại ngay
tại dấu phẩy (không phải whitespace) và chỉ giữ được object đầu tiên (mất 31/32 id, dù nội dung đã
dịch đúng và đã trả tiền — cùng loại silent-content-loss như B2-3).

**Quyết định fix — TỔNG QUÁT HOÁ, không vá riêng dấu phẩy**: đã quan sát ít nhất 2 biến thể ký tự
phân cách khác nhau (newline, dấu phẩy) cho CÙNG 1 loại lỗi tổng quát ("model trả nhiều JSON value
rời rạc thay vì gộp"). Vá riêng lẻ từng ký tự phân cách cụ thể là cách tiếp cận không bền — không
có gì đảm bảo đây là 2 biến thể duy nhất. Sửa `_decode_concatenated_json_objects()`
(`src/core/prompt_builder.py`): sau mỗi lần `raw_decode()` thành công tại vị trí `end`, thay vì chỉ
skip whitespace rồi thử decode tiếp tại `end`, tìm vị trí ký tự MỞ JSON tiếp theo (`{` hoặc `[` —
2 ký tự duy nhất có thể mở đầu 1 JSON value hợp lệ) bằng regex `_NEXT_JSON_VALUE_START_RE =
re.compile(r"[{\[]")`, bỏ qua BẤT KỲ thứ gì nằm giữa (whitespace, dấu phẩy, hay ký tự rác khác chưa
từng quan sát) — rồi thử `raw_decode()` tiếp từ đó. Nếu không tìm thấy `{`/`[` nào nữa, hoặc decode
tại vị trí tìm được vẫn thất bại, dừng lại NGAY (không tìm `{` xa hơn nữa) và giữ nguyên mọi object
đã parse được trước đó — đúng tinh thần "dung sai có chủ đích" đã có (chấp nhận ký tự phân cách lạ,
không tự bịa/đoán nội dung rác thành dữ liệu thật). Hành vi cũ cho trường hợp phổ biến nhất (response
chỉ có đúng 1 object hợp lệ, `raw_decode()` tiêu thụ hết chuỗi) không đổi.

**Golden fixture (Protocol 5 R5-01)**: raw response thật (dấu phẩy) vẫn còn trong file log chẩn
đoán QA vòng 3/5 để lại
(`scratchpad/.../qa_round3/diagnostic_calls.jsonl`, `call_no: 17`) — KHÔNG cần gọi API mới, dùng
lại nguyên văn `raw_text` đó làm
`tests/fixtures/epub_llm/deepseek_batch_response_sourdough_comma_separated_json_objects.json` (32
id, `"0"`..`"31"`, kèm 1 dấu `}` thừa ở cuối — vừa là ca dấu phẩy vừa là 1 ca "trailing garbage"
khác). Chi phí `input_tokens=2299`/`output_tokens=1392`/`estimated_cost_usd=0.0014245` đã phát
sinh THẬT từ trước (trong phiên QA vòng 3/5), không phát sinh chi phí mới ở bước lấy fixture này.
Fixture thiếu `request_payload`/`unit_ids_in_order` đầy đủ (script chẩn đoán của QA không log lại
các field này) — đã ghi rõ giới hạn này trong chính fixture (`note_on_missing_request_payload`) và
`tests/fixtures/epub_llm/README.md` (APPEND, không xoá lịch sử — Protocol 1 R7-03); không ảnh hưởng
tới mục đích test (`raw_response_text` vẫn byte-for-byte thật, `expected_ids` suy trực tiếp từ các
id thật xuất hiện trong chính response).

**Test mới** (`tests/test_epub_batch_golden_fixture.py`, APPEND):
- 5 test dùng fixture dấu phẩy: fixture là 1 lần gọi thật + `Extra data` (sanity), parse đủ 32/32
  id, nội dung id `"0"`/`"31"` đúng, xác nhận có trailing `}` thừa ở cuối.
- **2 test tổng hợp dùng ký tự phân cách CHƯA TỪNG gặp** (`;` và khoảng-trắng+tab+newline trộn
  lẫn) — bằng chứng quan trọng nhất rằng fix đã tổng quát thật: **cả 2 test PASS ngay, không cần
  sửa thêm bất kỳ dòng code nào** ngoài fix đã mô tả ở trên.

**Regression — toàn bộ test cũ liên quan `_decode_concatenated_json_objects()`/
`parse_epub_batch_response()` (ca newline B2-3, ca 1 dấu `"` thừa, ca key trùng, ca rác thật, ca
leading-prose, ca truncated JSON) vẫn PASS không sửa gì — thuật toán mới tương thích ngược hoàn
toàn.

**Kết quả chạy thật**:
```
uv run ruff check src/ tests/     → All checks passed!
uv run pytest tests/ -q           → 720 passed, 0 failed (714 baseline + 6 test mới)
```

**Trạng thái**: đây là vòng Dev↔QA thứ **4/5** cho Bug #EPUB-B2-3/B2-4 (còn đúng 1 vòng trước giới
hạn Protocol 3) — chưa có Reviewer thật review trong phiên này (R7-01), KHÔNG tự báo cáo "xong"/
"sẵn sàng release". Chờ PM giao Reviewer trước khi chuyển tiếp cho QA vòng 5/5.

---

## Chiến lược MỚI cho lỗi "DeepSeek trả JSON malformed" — Lớp A + B + C (2026-09-10, sau khi chạm giới hạn Protocol 3)

**Bối cảnh**: US-22 Bước 2/3 đã dùng hết **5/5 vòng Dev↔QA** (Protocol 3, xem `docs/escalation-log.md`)
cho cùng 1 chuỗi lỗi "DeepSeek trả JSON hỏng cú pháp khi response dài" — 3 biến thể vá đúng
(B2-3 newline, B2-4 dấu phẩy, B2-5 `}` thừa) nhưng mỗi vòng lại lộ biến thể mới, chứng minh hướng "vá
tiếp từng biến thể cú pháp" không hội tụ. Đây **KHÔNG phải thêm 1 bản vá biến thể thứ 4** — Tech Lead
thiết kế lại toàn bộ chiến lược tại `docs/Architecture.md` §6.20.14, dựa trên chỉ đạo của user
(chuyển tiếp qua PM, 2026-09-10): *"Ưu tiên nhanh, tiết kiệm, độ chính xác của bản dịch có thể chấp
nhận dung sai nhỏ."* Hệ quả: E-09 (chunk fail ngay khi thiếu 1 unit) đổi vai trò từ "luật mặc định"
thành "chốt chặn khi vượt ngưỡng bất thường" — implement theo đúng thứ tự Tech Lead chốt: **Lớp B
trước** (rẻ nhất, verify offline ngay được), rồi **Lớp A**, rồi **Lớp C**.

### Lớp B — parser "lỏng" `_salvage_epub_id_pairs()` (§6.20.14.3)

Bất biến nền tảng khác hẳn 3 fix cũ (B2-3/B2-4/B2-5 đều giả định "response là N giá trị JSON HỢP
LỆ, chỉ khác ký tự nối"): **mỗi bản dịch luôn xuất hiện dưới dạng 1 cặp `"<id>": "<chuỗi JSON hợp
lệ>"`, id nằm trong tập id ngắn cục bộ đã gửi** — không giả định gì về dấu ngoặc/dấu phẩy/cấu trúc
lồng nhau xung quanh cặp đó. `src/core/prompt_builder.py` (APPEND, không xoá/sửa
`_decode_concatenated_json_objects()` hiện có — Lớp B chỉ là lớp cứu hộ SAU parser chặt):
- `_salvage_epub_id_pairs(text, expected_ids)`: quét toàn văn tìm cặp id bằng regex
  `_EPUB_ID_PAIR_RE = re.compile(r'"(\d{1,3})"\s*:\s*"')`, decode giá trị bằng CHÍNH
  `json.decoder.scanstring` (không phải regex — escape `\"`/`\n`/`\uXXXX` xử lý đúng như JSON thật),
  con trỏ luôn tiến tới `end` sau mỗi lần ăn thành công (không bao giờ quét lại bên trong giá trị đã
  lấy — 1 đoạn `"12": "` nằm TRONG nội dung dịch không thể tạo cặp giả).
- `EpubParseOutcome` (dataclass) + `parse_epub_batch_response_detailed()`: trả thêm `strict_ids`/
  `salvaged_ids` cho telemetry. `parse_epub_batch_response()` (chữ ký cũ, mọi caller hiện có không
  đổi) nay chỉ là `.translations` của hàm `_detailed`. Salvage CHỈ chạy khi `len(result) <
  len(expected_ids)` sau parser chặt — response lành không bao giờ kích hoạt nhánh này (zero
  regression risk cho đường đi thường).

**Test** (`tests/test_epub_batch_golden_fixture.py`, APPEND) — chạy trên **CẢ 5 golden fixture thật
đã có, KHÔNG gọi thêm API nào**:
- 4 fixture cũ (5-unit sạch, trailing-garbage, B2-3, B2-4): `salvaged_ids` rỗng — parser chặt đã tự
  cứu đủ, Lớp B không cần kích hoạt.
- **`..._single_object_spurious_closing_braces.json` (Bug #EPUB-B2-5, CHƯA TỪNG có test nào xác
  nhận trước đây)**: parser chặt MỘT MÌNH chỉ cứu được **1/32 id** (`strict_ids == {"0"}`, bằng
  chứng cụ thể B2-5 là giới hạn CẤU TRÚC thật của hướng "tìm `{`/`[` tiếp theo", không phải lỗi
  triển khai fix B2-4). Sau Lớp B: **32/32 id**, 31 id còn lại đến từ salvage, nội dung id `"31"`
  đúng `<strong>¼ cup hạt cắt nhỏ</strong>` — khớp chính xác kỳ vọng Tech Lead.
- 3 test tổng hợp (không phụ thuộc fixture): salvage KHÔNG tạo cặp giả từ chuỗi con `"7": "` nằm
  trong 1 giá trị đã dịch; response cụt giữa chừng chỉ giữ cặp hoàn chỉnh trước đó; id ngoài
  `expected_ids` bị loại.
- **2 test cũ trong `tests/test_epub_batch_prompt.py` đổi hành vi có chủ đích** (không còn đúng sau
  Lớp B, đã sửa tên + assertion): `test_parse_strips_leading_prose` và
  `test_parse_genuinely_truncated_json_recovers_only_the_complete_pair` (tên cũ:
  `..._still_returns_empty_dict`) — Lớp B cứu được cặp id HOÀN CHỈNH dù nằm sau prose dẫn đầu, hoặc
  dù response bị cắt cụt Ở CẶP KHÁC phía sau; đây là giới hạn ĐÃ BIẾT và mong muốn của Lớp B
  (§6.20.14.3: không cứu được CHÍNH cặp bị cắt cụt, không phải "không cứu được gì trong cả response").

### Lớp A — giảm kích thước batch + fix lineage bug cost gate (§6.20.14.2)

Hằng số (`src/core/chunking.py` + mirror `src/core/config.py::Settings`):
- `EPUB_REQUEST_CHAR_BUDGET`: 3.000 → **1.100** (suy từ số đo thật §6.20.14.0a: mục tiêu giữ
  `output_tokens`/request ≤ ~600, vùng đã quan sát là sạch).
- `EPUB_REQUEST_MAX_UNITS` (MỚI) = **6** — trần THỨ HAI theo SỐ UNIT, không chỉ ký tự thuần: batch
  32 unit gây Bug #EPUB-B2-5 có RẤT ÍT ký tự thuần (nhiều tag HTML ngắn kiểu
  `<strong>1 cup starter</strong>`) nên vẫn "trong ngân sách ký tự" — số KHOÁ JSON mới là thứ model
  phải giữ đúng cú pháp. `plan_epub_chunks()` nhận thêm tham số này, cắt request khi VƯỢT MỘT TRONG
  HAI điều kiện (ký tự hoặc số unit), điều kiện nào chạm trước.
- `EPUB_MAX_SINGLE_ID_RETRIES`: 5 → **2**; `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE`: 6 → **3** — slice
  giờ chỉ tối đa 6 unit, trần 5 gần như luôn rơi vào nhánh "retry từng id" (đắt hơn hẳn 1 lần gọi lại
  nguyên request).

**A-4 (bug lineage Protocol 6 R6-01, BẮT BUỘC sửa cùng lúc)**: `cost_gate.py::
_estimate_epub_translation_cost()` trước đây gọi `plan_epub_chunks(doc.units)` với tham số MẶC ĐỊNH
MODULE, trong khi `job_orchestrator.run_epub_job()` gọi với giá trị từ `Settings` — 2 nơi tình cờ
khớp nhau trước khi đổi budget ở trên, sau đó (và với bất kỳ override `.env` nào) sẽ LỆCH, khiến
`llm_request_count` (= `segment_count` của `estimate_job_cost_v2()`) bị ước THẤP, vi phạm §6.11.6.
Sửa: `estimate_translation_cost()`/`_estimate_epub_translation_cost()` nhận thêm `settings: Settings`
(bắt buộc cho nhánh `file_type="epub"`, raise `ValueError` rõ ràng nếu thiếu thay vì âm thầm dùng
mặc định — không cho phép tái diễn bug này), gọi `plan_epub_chunks(doc.units,
char_budget=settings.epub_chunk_char_budget, request_budget=settings.epub_request_char_budget,
request_max_units=settings.epub_request_max_units)`. Call site `src/api/routes/jobs.py` (đã có sẵn
`settings` tại đó) cập nhật truyền vào.

**Test** (`tests/test_chunking.py`, `tests/test_epub_cost_gate.py`, APPEND + sửa 2 test hằng số cũ
để khớp giá trị mới): hằng số đúng giá trị; `plan_epub_chunks()` cắt đúng theo trần unit (tái hiện
kịch bản 32 unit ngắn); R6-02 — đổi `epub_request_max_units` trong `Settings` làm
`estimated_input_tokens`/`segment_count` THAY ĐỔI theo (không chỉ `assert_called()`), và
`segment_count` khớp CHÍNH XÁC với `plan_epub_chunks()` gọi trực tiếp cùng tham số.

### Lớp C — ngưỡng dung sai, E-09 từ "luật mặc định" thành "chốt chặn bất thường" (§6.20.14.4)

Unit không cứu được (kể cả sau Lớp B) → giữ nguyên tiếng Anh gốc, đánh dấu, KHÔNG làm chunk/job fail
ngay — trong hạn mức. `EpubBatchTranslationError` đổi vai trò (docstring cập nhật), phần "TUYỆT ĐỐI
không ghi chuỗi rỗng" của E-09 KHÔNG đổi.

- **C-1** (`job_orchestrator.py::_process_epub_chunk()`): unit còn thiếu sau vòng gọi lại được gom
  vào `fallback_units` (list riêng, KHÔNG đưa vào `parsed`) thay vì raise ngay — đúng thứ tự bắt buộc
  (fallback không lọt vào 2 guard mất dấu phía sau, tránh đốt tiền retry nhầm unit đã quyết định bỏ
  qua).
- **C-2**: 2 hằng số MỚI `EPUB_FALLBACK_MAX_RATIO_CHUNK = 0.20`, `EPUB_FALLBACK_MAX_RATIO_JOB = 0.05`
  (mirror `Settings`). Ngưỡng CHUNK kiểm ngay sau vòng lặp request trong `_process_epub_chunk()`
  (`allowed = max(1, ceil(0.20 × n_units_chunk))`), vượt → `EpubBatchTranslationError` (E-09 dạng
  mới). Ngưỡng JOB (5%) bị BR-EPUB-05 ép cận trên < 10% (unit fallback = giống bản gốc = tính vào
  đúng khe hở 10% mà guard output cho phép) — đặt 5% để còn nguyên nửa khe hở cho nguyên nhân khác.
- **C-3**: mỗi chunk ghi `fallback_units.json` vào `chunk_dir` (chỉ khi non-empty). Helper mới
  `_collect_epub_fallback_units()` đọc lại file này cho MỌI `Chunk` `completed` (kể cả từ lần chạy
  trước) — đây là cơ chế khiến ngưỡng JOB sống sót qua resume (BR-CHUNK-05), không dựa vào biến đếm
  trong bộ nhớ. `run_epub_job()` kiểm SAU MỖI chunk (không đợi hết job) — fail sớm, tiết kiệm tiền
  cho các chunk còn lại, đúng tinh thần Lớp 3/4 đã có. Nhân bản vào `anomalies.json` dưới khoá
  `fallback_units`.
- **C-4**: `EpubDocument.write_translated()` nhận thêm `untranslated_ids: set[str] | None = None` —
  đánh dấu class `bb-untranslated` + `lang="en"` NGAY TRÊN node gốc (không chèn node mới, không bọc
  `<span>`). Đã verify 2 tác dụng phụ: không đổi số unit đọc lại ở `load()` (chỉ bỏ qua theo class
  `bb-vi`), không ảnh hưởng `count_bb_vi_pairs()` (chỉ đếm `bb-vi`).
- **C-5**: `untranslated_units.json` ở `<output_dir>/<job_id>/` (cạnh `translated_vi.epub`), chứa
  `unit_id`/`doc_href`/`reason`/`slice`/`excerpt`. `logger.warning` tổng kết khi có fallback.

**Test** (`tests/integration/test_epub_translate_guards.py`, `tests/integration/test_epub_translate_runner.py`,
`tests/test_epub_document.py` — APPEND + sửa 3 test cũ để khớp vai trò mới của E-09):
- Trong hạn mức chunk/job → job `completed`, unit fallback có class `bb-untranslated` trong output,
  có mặt trong `untranslated_units.json`.
- Vượt hạn mức CHUNK (100% thiếu) → vẫn `EpubBatchTranslationError`, KHÔNG ghi chuỗi rỗng (E-09 chưa
  chết, chỉ đổi vai trò).
- Vượt hạn mức JOB **cộng dồn qua nhiều chunk** (không chỉ 1 chunk) → job fail NGAY SAU chunk vượt
  ngưỡng, các chunk sau KHÔNG được xử lý (tiết kiệm tiền).
- **Test resume THẬT** (2 `JobOrchestrator` instance riêng biệt, mô phỏng đúng cách `retry_job()` API
  reset chunk `failed`→`pending`): fallback của chunk hoàn thành ở lần chạy TRƯỚC (ghi trên đĩa) cộng
  dồn đúng với fallback của lần chạy SAU (instance hoàn toàn mới, không còn biến đếm cũ) — chứng
  minh cơ chế đọc từ đĩa, không phải bộ nhớ.
- `EpubDocument.write_translated()`: đánh dấu đúng node, không đổi số unit đọc lại, không ảnh hưởng
  `count_bb_vi_pairs()`, giữ nguyên lineage guard (R6-02) cho `untranslated_ids` lạ.

### Kết quả chạy thật

```
uv run ruff check src/ tests/     → All checks passed!
uv run pytest tests/ -q           → 744 passed, 0 failed (baseline 720 trước vòng này + ~24 test mới/sửa)
```

Không có regression cho test cũ liên quan JSON parsing/chunk/cost gate/EPUB translate guard — mọi
test đổi hành vi (do Lớp B/C đổi kỳ vọng có chủ đích) đã được sửa và ghi rõ LÝ DO trong chính test
(không xoá coverage, chỉ cập nhật để phản ánh đúng chiến lược mới).

**Chưa chạy live E2E full-book** ở bước Dev này (không bắt buộc theo brief PM — để QA làm ở vòng sau
với đầy đủ ngân sách đã duyệt, tham chiếu gate H-1..H-5 tại Architecture.md §6.20.14.9).

**Trạng thái**: implement đủ cả 3 lớp theo đúng thứ tự Tech Lead chốt (B → A-4 → A-1/2/3 → C). Chưa
có Reviewer thật review trong phiên này (R7-01) — **KHÔNG tự báo cáo "xong"/"sẵn sàng release"**. Chờ
PM giao Reviewer trước khi chuyển tiếp cho QA.

## US-22 EPUB — Bước 3/3 (2026-09-10)

BA rà soát Bước 1/3 + 2/3 (đã commit) và xác định 5 việc còn thiếu để đủ Acceptance Criteria của
US-22 (`docs/PRD.md` mục "US-22"). Cả 5 việc đã implement trong phiên này.

### 1. Nối `parse_epub_batch_response_detailed()`/`EpubParseOutcome` vào `job_orchestrator.py`

QA đã escalate: 3 call site trong `_process_epub_chunk()` (X4 request chính, `_retry_single_unit()`,
`_retry_whole_epub_request()`) vẫn dùng bản rút gọn `parse_epub_batch_response()`, bỏ phí telemetry
`salvaged_count`/`salvaged_ids` mà Lớp B (Architecture.md §6.20.14.3 B-3) đã spec nhưng chưa từng
nối vào observability thật.

- Đổi cả 4 lời gọi parse (main request + 2 helper dùng chung `_retry_single_unit()`/
  `_retry_whole_epub_request()`, mỗi helper được gọi ở 2 chỗ khác nhau trong `_process_epub_chunk()`)
  sang `parse_epub_batch_response_detailed()`, giữ nguyên `EpubParseOutcome.translations` làm
  `dict[str, str]` y hệt hành vi cũ (KHÔNG đổi hành vi nghiệp vụ — chỉ thêm observability).
  `_retry_single_unit()`/`_retry_whole_epub_request()` nhận thêm `job_id`/`chunk_index` (keyword-only)
  để log gắn đúng ngữ cảnh.
- Helper mới `JobOrchestrator._log_epub_parse_salvage()`: `salvaged_count > 0` → `logger.warning`
  (tín hiệu Lớp B đã phải can thiệp, đúng như Architecture.md §6.20.14.3 B-3 mô tả); `== 0` →
  `logger.info` (đường chuẩn, không cần cứu hộ).
- **Test** (`tests/integration/test_epub_translate_runner.py`,
  `test_run_epub_job_logs_salvaged_count_when_layer_b_engages`): provider giả `_SpuriousBracesProvider`
  mô phỏng ĐÚNG hình dạng bug đã golden-fixture-test ở cấp parser đơn lẻ
  (`tests/test_epub_batch_golden_fixture.py`, fixture Bug #EPUB-B2-5 — 1 dấu `{`, N dấu `}` rải rác)
  nhưng test ở CẤP ORCHESTRATOR (tích hợp, không mock parser) — xác nhận `caplog` bắt được đúng 1
  log WARNING `salvaged_count=2` (3 unit/1 request: id "0" qua đường chuẩn, "1"/"2" qua salvage), và
  nội dung dịch vẫn đúng đủ sau salvage.

### 2. `output_mode` cho EPUB — honor lựa chọn user thay vì hardcode

`run_epub_job()` hardcode `bilingual = True` cho MỌI job EPUB (dòng có comment "E8"), bỏ qua
`Batch.output_mode` mà user chọn lúc tạo job.

- Đổi `bilingual = True` → `bilingual = await self._wants_bilingual(job, db_session)` — TÁI DÙNG
  đúng helper đã có sẵn cho nhánh PDF (`_wants_bilingual()`, đọc `Batch.output_mode`), không viết
  logic mới. `write_translated(bilingual=False)` đã hỗ trợ sẵn chế độ THAY THẾ (không chèn thêm) từ
  Bước 1/3 — không cần sửa `EpubDocument`.
- `web/index.html`: **không có** đoạn code nào ẩn/disable select "Đơn ngữ/Song ngữ" riêng cho `.epub`
  (đã grep xác nhận, không tồn tại) — select đã hoạt động bình thường cho EPUB như PDF từ trước, mục
  này của brief hoá ra không cần sửa gì ở `index.html`.
  - **Nhưng** phát hiện 1 vấn đề thật liên quan: `web/js/app.js` (`handleFiles()`) mặc định
    `output_mode: lastOutputMode || "monolingual"` cho MỌI file type khi chưa có lựa chọn nhớ từ lần
    trước — nếu giữ nguyên, sau khi (2) có hiệu lực, upload EPUB đầu tiên sẽ ra monolingual, SAI với
    AC "mặc định bật bản song ngữ". Sửa: `defaultOutputMode = body.file_type === "epub" ? "bilingual"
    : "monolingual"`, giữ nguyên tinh thần "mặc định, không phải bắt buộc cố định" — 1 khi user đã
    từng đổi lựa chọn (`lastOutputMode` có giá trị trong `localStorage`), lựa chọn đó thắng cho MỌI
    file type như cũ, không riêng gì EPUB.
- **Test** (`test_run_epub_job_monolingual_output_mode_has_no_english_original`): job EPUB tạo với
  `Batch.output_mode="monolingual"` → output chỉ có VI (không có node `bb-vi`, câu tiếng Anh gốc chỉ
  xuất hiện 1 lần — bên trong bản dịch — thay vì 2 lần như bilingual mặc định), số unit output = số
  unit input (X3, không mất chương ở monolingual).
  - **Thay đổi kèm theo bắt buộc**: helper test `_create_epub_job()` giờ LUÔN tạo 1 `Batch` thật và
    gán `job.batch_id` (giống hệt `_resolve_batch()` của `src/api/routes/jobs.py` luôn tạo 1 Batch
    cho MỌI job kể cả job đơn lẻ) — trước bước 3/3, test job EPUB không có `batch_id` nên
    `_wants_bilingual()` sẽ luôn trả `False` nếu không sửa helper, làm SẬP toàn bộ test EPUB cũ (vốn
    kỳ vọng bilingual mặc định khi `bilingual = True` còn hardcode). Default `output_mode="bilingual"`
    của helper giữ nguyên kỳ vọng các test cũ, tham số `output_mode` optional cho test mới.

### 3. UI: hiển thị `total_units` cho EPUB thay vì ô trống

`web/index.html` (khu vực dòng ~52) chỉ hiển thị `f.page_count` (luôn `null` cho EPUB theo thiết kế,
Architecture.md §6.20.6) — EPUB không hiện con số nào thay thế.

- Thêm `<template x-if="!f.page_count && epubTotalUnits(f)">` hiển thị "N đoạn" — chỉ kích hoạt khi
  KHÔNG có `page_count` (an toàn cho PDF vì PDF luôn có `page_count`, và job PDF phục hồi từ server
  có `total_units=None` nên `epubTotalUnits()` trả `null`, template không hiện).
- Helper mới `epubTotalUnits(f)` trong `web/js/app.js`: ưu tiên `f.job?.total_units` (field có sẵn
  trên `JobDetail`, `src/api/routes/jobs.py` dòng ~167 — có giá trị sau khi job được tạo), fallback
  `f.costEstimate?.total_units` (field có sẵn trên `CostEstimateResponse`, dòng ~206 — có giá trị
  NGAY SAU khi bấm "Xem chi phí ước tính", TRƯỚC CẢ khi tạo job). `UploadResponse` (`upload.py`)
  không có field `total_units` nên không thể hiển thị ngay lúc vừa upload — đây là giới hạn hợp lý,
  không phải thiếu sót (số đoạn chỉ tính được sau khi ước tính chi phí hoặc tạo job, giống cách PDF
  cũng không biết `page_count` chính xác cho tới lúc đó — thực ra PDF CÓ biết `page_count` ngay lúc
  upload qua PyMuPDF, khác EPUB; ghi chú lại để không nhầm 2 trường hợp).

### 4. Test — tổng kết

2 test mới trong `tests/integration/test_epub_translate_runner.py` (việc 1 + việc 2 ở trên, chi tiết
đã mô tả kèm từng việc).

### 5. Kết quả chạy thật

```
uv run ruff check src/ tests/     → All checks passed!
uv run pytest tests/ -q           → 746 passed, 0 failed (baseline 744 trước vòng này + 2 test mới)
```

Không regression trên bất kỳ test EPUB/PDF nào đã có (kể cả các test EPUB cũ mặc định bilingual —
vẫn pass đúng vì helper `_create_epub_job()` giữ default `output_mode="bilingual"`).

### Ngoài phạm vi (theo đúng chỉ đạo PM/BA, để lại backlog riêng)

- KHÔNG động tới US-15 nhánh EPUB (`_reject_epub_parse_only`, `EpubDocument.to_markdown()`).
- KHÔNG sửa Bug #EPUB-3 (job mồ côi khi restart server).
- KHÔNG cài `epubcheck` — QA tự xử lý verify bằng reader thật riêng.

### Trạng thái

Đủ cả 5 việc BA yêu cầu. **Chưa có Reviewer thật review trong phiên này (R7-01)** — KHÔNG tự báo cáo
"xong"/"sẵn sàng release". Chờ PM giao Reviewer trước khi chuyển tiếp cho QA.

**Điểm cần Reviewer/QA lưu ý riêng** (R5-04 checklist tự đánh giá): 2 file sửa trong bước này
(`job_orchestrator.py`, `_process_epub_chunk`/`run_epub_job`) là orchestrator nội bộ, KHÔNG tự gọi
API/CLI/SDK bên thứ ba mới nào chưa từng verify — logic dùng lại nguyên contract JSON X4 đã verify từ
Bước 2/3, không có claim contract mới nào cần Protocol 5. `web/index.html`/`web/js/app.js` không gọi
external tool — N/A cho Protocol 5.

## US-15 nhánh EPUB — xuất Markdown gốc, KHÔNG dịch (2026-09-10, theo Architecture.md §6.15.7)

Implement đúng spec thi hành §6.15.7 (bản cập nhật S15-8 sau khi US-22 hoàn tất — S15-8 cũ/§6.20.5
đã LỆCH với code thật, mục này SUPERSEDE). Đọc toàn bộ §6.15.7 + §6.21.2 trước khi code, theo đúng
chỉ đạo PM.

### 1. `EpubDocument` (`src/services/epub_document.py`)

- **`_spine_hrefs`** (field mới) + property `spine_hrefs` — tính ĐÚNG MỘT LẦN trong `load()`, ngay
  sau guard X6 (không giữ lại soup nào, khác giả định cũ `spine_documents` của S15-8 gốc — điểm LỆCH
  #1 mà §6.15.7 mục A đã ghi).
- **`to_markdown(images_out_dir: Path) -> str`** (method mới) — mở lại `self.path` bằng `zipfile`,
  parse lại từng `doc_href` trong `self._spine_hrefs` (dùng lại `_parse_xhtml()` có sẵn, KHÔNG viết
  parser thứ hai), rewrite `<img src>` + copy ảnh ra `images_out_dir` (`_rewrite_image_srcs()`, mới),
  chuẩn hoá `<sup>`/`<sub>` (`normalize_sup_sub()`, mới) **TRƯỚC KHI** convert bằng
  `markdownify.MarkdownConverter(heading_style="ATX").convert_soup(body)` — thứ tự bắt buộc theo
  §6.21.2 (chuẩn hoá trước để độc lập với `sup_symbol`/`sub_symbol` mặc định của thư viện).
  - **Phát hiện khi implement (KHÔNG có trong §6.15.7, tự đo)**: gọi thẳng
    `markdownify.markdownify(str(soup), ...)` (như §6.15.7 mục A mô tả nôm na) làm rò rỉ khai báo XML
    (`<?xml version="1.0"?>`) và nội dung `<title>` vào Markdown output, vì `markdownify()` tự
    `BeautifulSoup(html, "html.parser")` lại TOÀN BỘ chuỗi — `html.parser` không hiểu XML processing
    instruction, biến nó thành text thường. Fix: dùng `MarkdownConverter().convert_soup(soup.find("body"))`
    thay vì serialize-rồi-reparse toàn bộ soup — convert đúng CHỈ phần `<body>`, tránh double-parse.
  - Rewrite `src` ảnh tính tương đối so với CHÍNH `doc_href` chứa nó (`posixpath.join(posixpath.dirname(doc_href), src)`),
    KHÔNG phải `opf_dir` — đúng điểm §6.15.7 mục B nhấn mạnh dễ sai nhất.
  - Trùng basename giữa 2 thư mục khác nhau trong zip: nếu bytes GIỐNG nhau, gộp chung 1 file đích;
    nếu KHÁC nhau, thêm hậu tố tăng dần (`f01_2.jpg`) — không ghi đè im lặng.
  - URL tuyệt đối/`data:` URI: giữ nguyên, không copy. Entry thiếu trong zip: không raise, log
    warning, giữ `src` nguyên trạng (khác guard X6 của `load()` — ở đó lệch href phải raise).
- **`normalize_sup_sub(soup, *, style="unicode")`** (hàm mới, module-level) — implement đúng §6.21.2:
  Bước 1 (phân số `<sup>N</sup>/<sub>M</sub>` → `"N/M"`, guard hỗn số chèn dấu cách khi ký tự trước
  `<sup>` là chữ số — case quan trọng nhất, F-2), Bước 2 (mapping Unicode 2 bảng sup/sub cho
  digit/dấu/1-chữ-cái, fallback ASCII `^(c)`/`_(c)` khi không map được, không bọc thêm ngoặc nếu `c`
  đã có sẵn ngoặc). Tự chạy cả 7 dòng bảng "Kết quả đã chạy thật" của §6.21.2 khớp 100% (xem mục Test
  bên dưới). CHỈ dùng bởi `to_markdown()` — KHÔNG đụng tới `units`/`write_translated()` của US-22 (đã
  verify `tests/test_epub_document.py` 72 test cũ xanh nguyên, không sửa 1 assertion nào).
  - `style="pandoc"` (setting mới, xem mục 2) — bọc `^c^`/`~c~`, Bước 1 (phân số) giống hệt 2 chế độ.

### 2. Setting mới (`src/core/config.py`)

`markdown_supsub_style: Literal["unicode", "pandoc"] = "unicode"` — `.env`-only theo đúng chỉ định
§6.15.7 mục C, KHÔNG thêm vào `SETTINGS_DB_OVERRIDABLE_FIELDS` (lựa chọn biểu diễn, không phải tham
số vận hành).

### 3. Wiring (6 điểm, đúng bảng W-1..W-6 §6.15.7 mục E)

- **W-1** `src/api/routes/jobs.py`: XOÁ `_reject_epub_parse_only()` + 2 call site (`create_job()`,
  `create_batch()`) — chốt chặn HTTP 400 đã gỡ.
- **W-2** `_resolve_parse_method()`: trả `None` cho `file_type == "epub"` (thay vì `"ocr"` vô nghĩa)
  — `Job.parse_method` là cột nullable, `None` đúng nghĩa "không áp dụng".
- **W-3** `job_orchestrator.py::run_parse_only()`: nhánh `if job.file_type == FileType.EPUB` giờ gọi
  `return await self._run_epub_parse_only(job, db_session)` — đặt TRƯỚC `_count_pdf_pages()`/guard
  MinerU (không áp dụng cho EPUB).
- **W-4** Xoá class `EpubNotSupportedError` (không còn call site nào sau W-3).
- **W-5** `web/index.html`: checkbox "ưu tiên độ chính xác ký hiệu" (dành cho MinerU `txt`/`ocr`) ẩn
  khi `f.file_type === 'epub'`. `web/js/app.js` đã tự gửi `parse_method=undefined` khi checkbox
  không bật (logic có sẵn, không cần sửa thêm) — vì checkbox giờ luôn ẩn với EPUB nên
  `f.parse_force_ocr` không bao giờ được set `true`.
- **W-6** `src/api/routes/download.py`: xác nhận KHÔNG cần sửa (đã branch theo `job_type`, không
  quan tâm `file_type`) — đúng như §6.15.7 đã ghi.

### 4. `_run_epub_parse_only()` + `_finalize_parse_only_output()` (Protocol 8 R8-03)

Method mới `JobOrchestrator._run_epub_parse_only()` — song song với `_run_parse_only_pipeline()`
(nhánh PDF), có try/except RIÊNG (chạy TRƯỚC try/except của `run_parse_only()`, giống hình dạng thất
bại `job.status="failed"` + `error_message` + broadcast). Bắt `EpubDrmError`/`EpubParseError` từ
`EpubDocument.load()` qua `except Exception` chung — đúng contract sẵn có (R6-01 sợi dây lineage:
`doc` là CHÍNH instance vừa `load()`, `to_markdown()` đọc lại `self._spine_hrefs` của instance đó,
cấm `load()` lần 2).

Tách `_finalize_parse_only_output(job, markdown_text, image_files, db_session)` — phần "đóng gói"
(ghi `document.md`, guard đọc lại từ đĩa, zip eager, guard zip, `job.output_path`/`actual_cost="metered"`,
`status="completed"`, broadcast) DÙNG CHUNG giữa nhánh PDF (`_run_parse_only_pipeline()`) và nhánh
EPUB — đúng tinh thần Protocol 8 (không rẽ nhánh `if file_type == epub` rải rác). Đã verify:
`_run_parse_only_pipeline()` gọi hàm này y hệt hành vi cũ (tất cả test parse_only PDF cũ xanh
nguyên, 41/41 trong `test_job_orchestrator.py` + `test_cost_capped_orchestrator.py`).

### 5. Test bắt buộc — kết quả

- **Golden `normalize_sup_sub()`** (`tests/test_epub_document.py`): 7/7 case khớp đúng bảng §6.21.2
  (phân số đơn, hỗn số N-1 `"1 1/3"` không phải `"11/3"`, số mũ âm, hoá học/ion, chú thích, ASCII
  fallback không map được, `10⁻⁶`) + 1 test riêng cho `style="pandoc"`.
- **Golden `to_markdown()` trên `ops/xhtml/chapter01.html`** (sourdough thật): khớp đúng số đo của
  S15-8 — 10 `<img>`, 214 `<strong>`, 26 `<em>`, 2 `<h2>`, 34 `<h3>`.
- **R6-02** (`test_to_markdown_r6_02_heading_counts_match_units`): số h2/h3 trong `to_markdown()` ==
  số unit `tag in {"h2","h3"}` từ CÙNG một `load()`. Sourdough KHÔNG có case heading-toàn-chữ-số bị
  `_is_droppable_content()` drop khỏi `units` (đã tự kiểm: khớp tuyệt đối 2/2, 34/34) — ghi rõ trong
  test để nếu sách khác có case đó, phải sửa assert để TRỪ đúng số bị drop, không được nới `>=`.
- **Ảnh**: test URL tuyệt đối/`data:` URI giữ nguyên không copy; entry thiếu trong zip không crash,
  giữ `src` nguyên trạng.
- **KHÔNG regression US-22**: `tests/test_epub_document.py` (86 test, +14 test mới) +
  `tests/test_epub_batch_golden_fixture.py` xanh nguyên — 0 assertion nào của US-22 bị sửa/xoá.
  `units` vẫn chứa `<sup>1</sup>/<sub>3</sub>` thô (test dòng ~280 cũ không đổi).
- **`tests/integration/test_job_orchestrator.py`**: thay test cũ
  `test_run_parse_only_epub_raises_without_calling_mineru` (assert raise `EpubNotSupportedError`,
  hành vi cũ đã sai) bằng `test_run_parse_only_epub_completes_without_calling_mineru` — dùng 1 EPUB
  tối thiểu THẬT (zipfile, hợp lệ OCF, cùng mẫu với `tests/test_epub_document.py::_build_minimal_epub`),
  chạy `run_job()` thật, assert job "completed", `parse_method is None`, `total_pages is None`, mở
  zip output thật ra kiểm `document.md` có chữ thật + `images/` có đúng 1 ảnh đúng bytes.
- **`tests/integration/test_upload_and_job_flow.py`**: thay test cũ
  `test_create_job_rejects_epub_parse_only_before_creating_job_record` (assert 400, hành vi cũ đã
  sai) bằng `test_create_job_accepts_epub_parse_only_since_epub_markdown_shipped` — assert 202 +
  `status="queued"` + 1 Job row được tạo, cùng mẫu với test parse_only PDF khác trong file (không
  assert trạng thái background, để riêng cho `test_job_orchestrator.py`).

### 6. Kết quả chạy thật

```
uv run ruff check src/ tests/     → All checks passed!
uv run pytest tests/ -q           → 760 passed, 0 failed (baseline 746 trước vòng này + 14 test mới
                                     trong test_epub_document.py, 2 test THAY (không phải test mới)
                                     trong test_job_orchestrator.py và test_upload_and_job_flow.py)
```

**KHÔNG có test US-22 nào bị regression hoặc bị sửa/xoá assertion để né lỗi** — đây là câu hỏi quan
trọng nhất theo brief PM, xác nhận lại rõ ràng: `tests/test_epub_document.py` (72 test cũ + 14 test
mới = 86, tất cả 72 test cũ giữ nguyên 100% không đổi 1 dòng) và
`tests/test_epub_batch_golden_fixture.py` (14 test, không đổi) đều xanh nguyên. 2 test bị SỬA
(`test_job_orchestrator.py`, `test_upload_and_job_flow.py`) đều là test đang assert TRỰC TIẾP hành vi
cũ "EPUB parse-only bị chặn/raise" — hành vi đó đã đổi CÓ CHỦ Ý theo đúng spec §6.15.7 (đây chính là
mục tiêu của US-15 nhánh EPUB), không phải sửa để né lỗi; cả 2 test mới thay thế đều siết chặt hơn
(assert nội dung file output thật, không chỉ status).

### 7. Trạng thái

Đủ 5 việc (field/method/hàm `normalize_sup_sub`/copy ảnh + rewrite link/setting) + 6 điểm wiring
W-1..W-6. **Chưa có Reviewer thật review trong phiên này (R7-01)** — KHÔNG tự báo cáo "xong"/"sẵn
sàng release". Chờ PM giao Reviewer trước khi chuyển tiếp cho QA.

**R5-04 checklist tự đánh giá**: `EpubDocument.to_markdown()`/`normalize_sup_sub()` không gọi
API/CLI/SDK bên thứ ba mới nào — `markdownify` là thư viện Python thuần (không phải subprocess/HTTP
service), verify version `1.2.3` đã cài qua `importlib.metadata` (khớp Architecture.md §6.15.7 nguồn
xác thực) — N/A cho Protocol 5 muc pham vi ("khong ap dung cho thu vien noi bo Python thuan code
logic"). Riêng hành vi `markdownify.markdownify()` re-parse lại toàn bộ chuỗi qua `html.parser` (làm
rò rỉ XML declaration/`<title>`) LÀ một phát hiện Protocol 5-flavor tự đo được khi implement (không
có trong Architecture.md) — đã ghi lại ở mục 1 và đổi sang `convert_soup(body)` để tránh phụ thuộc
hành vi ngầm định đó.

## Bug #EPUB-3 — Quét job "mồ côi" (orphan) lúc server startup (2026-09-10)

Fix theo đúng spec Tech Lead tại `docs/Architecture.md` §E3 (append). Job "mồ côi" là job bị kẹt
vĩnh viễn ở 1 trạng thái đang chạy (`created`/`queued`/`chunking`/`parsing`/`translating`/
`post_processing`/`merging`) nếu process uvicorn chết giữa chừng (crash/deploy/`--reload`) — không
phải bug riêng EPUB, ảnh hưởng mọi `file_type` lẫn `job_type=parse_only` (E3.1).

### 1. Việc đã làm

- **File mới `src/core/job_recovery.py`**: `fail_orphaned_jobs(session) -> int` — query mọi `Job`
  có `status` trong `_ORPHAN_JOB_STATUSES` (7 giá trị, đúng §E3.3, khai báo riêng KHÔNG import lại
  `_ACTIVE_JOB_STATUSES` của `src/api/routes/jobs.py` — trùng giá trị vì trùng ngữ cảnh, không phải
  cùng business rule, theo đúng lý do §E3.3), mark `status="failed"` + `error_message` (đúng câu
  chữ Tech Lead đã chốt, không diễn đạt lại) + `finished_at`/`updated_at`. Dùng SQLModel
  `select(...).where(col(Job.status).in_(...))`, không raw SQL. KHÔNG đụng `progress`/
  `current_chunk`/`total_chunks`/`actual_cost` (giữ nguyên tiến độ cũ) và KHÔNG đụng `Chunk.status`
  (E3.5: resume đã tự skip chunk `completed` sẵn, reset thêm là code thừa). KHÔNG quét `Batch`
  (E3.4: `created` là trạng thái vĩnh viễn hợp lệ của Batch cho job đơn lẻ). 1 `session.commit()`
  duy nhất sau vòng lặp. Idempotent — lần gọi thứ 2 trả về 0, không ghi đè `finished_at` cũ (dùng
  `or`).
- **`src/api/main.py::lifespan()`**: gọi `fail_orphaned_jobs()` ngay sau `await init_db()`, trước
  `yield` — đúng thứ tự bắt buộc (bảng phải tồn tại trước khi query; chạy xong trước khi uvicorn
  nhận request đầu tiên nên không có race với job mới tạo, dựa trên giả định single-worker đã verify
  ở §E3.3 qua `.claude/launch.json`).
- **`src/models/job.py:32-34`**: sửa comment liệt kê status — thêm `parsing` (bị thiếu dù được gán
  thật 2 chỗ trong `job_orchestrator.py`, cùng loại lỗi với S15-12 cũ) + ghi chú lý do để tránh lặp
  lại.
- **Retry endpoint (`src/api/routes/jobs.py`)**: KHÔNG sửa — `_RETRYABLE_STATUSES` đã có `"failed"`
  từ Increment 6, tương thích sẵn với job orphan (đã verify lại bằng test, không suy đoán, xem mục
  2 test 5/7 dưới đây).

### 2. Test — `tests/integration/test_orphan_job_recovery.py` (file mới, 7 test)

Theo đúng 6 case §E3.8 (mở rộng thêm 1 test cho `lifespan()` theo yêu cầu brief PM):

1. `test_marks_every_orphan_status_as_failed` — 7 Job, mỗi job 1 status trong
   `_ORPHAN_JOB_STATUSES`; assert cả 7 chuyển `failed` + đúng `error_message` + `finished_at`.
2. `test_does_not_touch_terminal_status_jobs` — 4 Job ở trạng thái cuối, `error_message`/
   `finished_at` đặt sẵn; assert cả 2 giá trị **không đổi** (so sánh giá trị cụ thể).
3. `test_keeps_progress_fields_unchanged` — assert `progress`/`current_chunk`/`total_chunks`/
   `actual_cost` y nguyên sau khi mark.
4. `test_second_call_is_idempotent` — gọi 2 lần, lần 2 trả 0 và không ghi đè `finished_at` lần 1.
5. `test_retry_after_orphan_mark_succeeds` (R6-02, nối 2 bước) — dùng `TestClient` thật + DB thật
   (tmp_path), mark orphan xong → `POST /api/jobs/{id}/retry` → assert KHÔNG 400, `status="queued"`,
   `error_message is None`, `cancel_requested is False`.
6. `test_completed_chunks_survive_orphan_mark` — job có 3 Chunk (`completed`/`translating`/
   `pending`); sau `fail_orphaned_jobs()`, assert cả 3 `Chunk.status` không đổi (chứng minh E3.5).
7. `test_lifespan_marks_orphan_jobs_before_serving_requests` — seed 1 job orphan vào DB TRƯỚC khi
   khởi tạo `TestClient(app)` (kích hoạt `lifespan()` thật), assert job đã bị mark `failed` ngay khi
   `TestClient` khởi tạo xong — xác nhận đúng thứ tự "sau `init_db()`, trước `yield`".

Test 5 và 7 dùng lại đúng pattern `client` fixture (`monkeypatch.chdir(tmp_path)` + reset
`database_module._engine`/`_session_factory` + `get_settings.cache_clear()`) đã có sẵn ở
`tests/integration/test_estimate_and_cancel_api.py` — DB test cô lập theo `tmp_path`, không rác lẫn
giữa các test khác dùng `TestClient`.

### 3. Kết quả chạy thật

```
uv run ruff check src/ tests/     → All checks passed!
uv run pytest tests/integration/test_orphan_job_recovery.py -q → 7 passed
uv run pytest tests/ -q           → đang chạy full suite, xem báo cáo PM
```

### 4. Trạng thái

**Chưa có Reviewer thật review trong phiên này (R7-01)** — KHÔNG tự báo cáo "xong"/"sẵn sàng
release". Chờ PM giao Reviewer.

## Fix 4 mục backlog kỹ thuật nhỏ — BL-01/02/03/05 (Dev, 2026-09-10)

Brief PM: 4 mục backlog độc lập, mỗi mục kèm test xác nhận hành vi đúng (không chỉ sửa rồi hy vọng
đúng). Tự xác nhận từng fix bằng cách chạy lại test trên code CŨ (git stash chỉ file `src/`) trước
khi áp fix — mọi test bên dưới đều fail trên code cũ, pass trên code mới.

### BL-01 — `font_shrink_page()` lặp toàn tài liệu thay vì đúng phạm vi chunk

**Vấn đề**: `src/core/job_orchestrator.py::_process_chunk()` mở `chunk.output_path` (từ sau Bug #7,
đây là bản COPY CẢ TÀI LIỆU GỐC, không còn chunk-scoped) rồi `for page in doc:` lặp qua TOÀN BỘ
trang tài liệu cho MỖI chunk — lãng phí tính toán tăng tuyến tính theo số chunk, và
`OverflowReport` có thể bị ghi lặp lại cho cùng 1 trang bởi nhiều chunk khác nhau.

**Fix**: đổi `for page in doc:` thành `for page_num in range(chunk.page_start - 1,
min(chunk.page_end, doc.page_count)):` — đúng convention `page_start`/`page_end` 1-indexed inclusive
đã dùng ở `_extract_chunk_text()`/`_count_text_segments()` cùng file.

**Test**: `tests/integration/test_job_orchestrator.py::test_font_shrink_only_processes_own_chunk_page_range`
— job 90 trang, `chunk_size_used=40` (3 chunk: 1-40/39-80/79-90), patch `font_shrink_page` để ghi
lại `page.number` TẠI THỜI ĐIỂM gọi (trước khi doc handle bị đóng). Assert tổng số lần gọi = 94 (40
+ 42 + 12, không phải 3×90=270) VÀ mỗi `page.number` quan sát được nằm đúng trong phạm vi
`page_start-1..page_end-1` của chunk tương ứng nó thuộc về (zip theo thứ tự chunk_index).

### BL-02 — `create_job()`: cost gate giờ chạy TRƯỚC duplicate-check (thứ tự UX)

**Vấn đề**: `src/api/routes/jobs.py::create_job()` chạy duplicate-check (nếu file trùng hash với job
`completed` trước đó và `force` không set) TRƯỚC cost gate — user thấy cảnh báo "đã dịch rồi"
trước khi thấy cảnh báo chi phí vượt cap, dù cost gate luôn chạy vô điều kiện cho mọi request
`translate` (kể cả `force=true`).

**Fix**: di chuyển khối `settings`/`provider`/`_reject_deepl_for_pdf()`/`_enforce_cost_gate()` lên
TRƯỚC khối duplicate-check. Hành vi `force=true` (bỏ qua RIÊNG duplicate-check, cost gate vẫn áp
dụng) không đổi.

**Test**:
- `tests/integration/test_cost_gate_api.py::test_create_job_cost_gate_runs_before_duplicate_check`
  (mới) — file trùng hash với 1 job `translate` đã `completed`, cap thấp hơn ước tính thật. Request
  không `force` trả `402` (không phải `200`/`duplicate_found`) — assert `_job_row_count()` không
  tăng. `force=true` (không `confirm_cost`) vẫn `402` — chứng minh cost gate vẫn áp dụng dưới
  `force`. `force=true` + `confirm_cost=true` mới thực sự tạo job mới (202, job id khác job trùng).
- Sửa `tests/integration/test_upload_and_job_flow.py::test_create_job_reports_duplicate_of_completed_job_with_same_hash`
  — request duplicate-check giờ phải chỉ định `provider: "ollama"` (không cần API key) vì cost gate
  chạy trước nó, tránh 400 do thiếu key `deepseek` (default provider) làm sai lệch mục đích test.

### BL-03 — thêm test round-trip `ollama_thread` qua `PUT`/`GET /api/settings`

Field đã expose đúng ở `src/api/routes/settings.py` (verify lại bằng đọc code, không sửa gì) nhưng
thiếu test round-trip. Thêm 2 test vào `tests/integration/test_settings_api.py` theo đúng pattern
`test_put_cost_cap_settings_overrides_effective_settings` đã có:
- `test_get_settings_reports_ollama_thread_default` — GET trả về default `2`.
- `test_put_ollama_thread_overrides_effective_settings` — `PUT {"ollama_thread": 6}` → PUT response,
  GET response, VÀ `get_effective_settings()` (không chỉ HTTP echo) đều trả `6`.

### BL-05 (ưu tiên cao nhất) — ghi `chunk.api_cost`/`api_tokens_used` TRƯỚC khi raise qua
`EpubBatchTranslationError`/`EpubRequestRunawayError`

**Vấn đề** (finding Reviewer đã nhắc 2 lần, xem `docs/review-report.md` mục "2. Data lineage —
`chunk.api_cost`/`api_tokens_used` khi rơi vào Lớp C"): trong
`job_orchestrator.py::_process_epub_chunk()`, khi chunk fail qua `EpubBatchTranslationError` (C-2,
vượt ngưỡng fallback 20%/chunk) hoặc `EpubRequestRunawayError` (R-b, runaway + thiếu id), hàm raise
NGAY mà KHÔNG ghi `chunk.api_cost`/`chunk.api_tokens_used` (biến cục bộ `total_cost`/
`total_input_tokens`/`total_output_tokens` đã tích luỹ qua `_accumulate_and_check_budget()` cho MỌI
request đã gọi trong chunk, kể cả request thành công trước request lỗi) — tiền thật đã tiêu "biến
mất" khỏi `job.actual_cost`/cost accumulator Lớp 3 khi chunk fail.

**Fix**: thêm đúng trước mỗi lệnh `raise` của 2 exception này:
```python
chunk.api_tokens_used = total_input_tokens + total_output_tokens
chunk.api_cost = total_cost
db_session.add(chunk)
await db_session.commit()
```
— giống hệt pattern `EpubChunkCostCapExceeded` (Lớp 4) đã làm đúng từ trước. KHÔNG đổi
`chunk.status` (outer `except Exception` ở `run_epub_job()` tự set `"failed"` — đã verify đọc code,
không đoán).

**Test** (điểm quan trọng nhất của brief): `tests/integration/test_epub_translate_guards.py`, thêm
class `_CostTrackingEpubProvider` (subclass `_ControllableEpubProvider`, ghi lại
`estimated_cost_usd` THẬT của từng lần gọi, không hardcode) + 2 test:
- `test_epub_batch_translation_error_still_records_cost_of_prior_successful_request` — chunk 6
  unit, 2 request/chunk (`epub_request_max_units=3`): request 1 (unit 0-2) THÀNH CÔNG hoàn toàn;
  request 2 (unit 3-5) thiếu hết id → 1 lần gọi lại nguyên request (vẫn thiếu) → 3/6 fallback vượt
  hạn mức chunk 20% (tối đa 2/6) → `EpubBatchTranslationError`. Sau khi bắt lại exception, assert
  `chunk.api_cost == pytest.approx(sum(provider.observed_costs))` (tổng CẢ 3 lần gọi, không phải
  0/None/chỉ lần cuối) và `chunk.api_cost > provider.observed_costs[0]` (chứng minh cost của request
  1 THẬT SỰ được cộng vào, không bị ghi đè/bỏ qua).
- `test_epub_request_runaway_error_still_records_cost_of_prior_successful_request` — cùng hình dạng
  cho `EpubRequestRunawayError` (request 2 runaway + thiếu id → abort ngay, không retry).
- Cả 2 test đã verify fail trên code CŨ (`chunk.api_cost is None`) qua `git stash` trước khi áp fix,
  xác nhận test thật sự chứng minh fix, không phải test tự thoả mãn giả định.

### Kết quả chạy thật

```
uv run ruff check src/ tests/                     → All checks passed!
uv run ruff format --check <các file đã sửa>      → sạch cho MỌI dòng do Dev thêm/sửa
                                                     (còn vài dòng format-drift TIỀN TỒN TẠI ở
                                                     src/api/routes/jobs.py, job_orchestrator.py,
                                                     test_cost_gate_api.py, test_upload_and_job_flow.py
                                                     — KHÔNG do Dev đụng tới, ngoài phạm vi 4 mục
                                                     backlog này, không tự ý sửa)
uv run pytest tests/ -q                           → 773 passed (baseline 767, +6 test mới,
                                                     không regression)
```

### Trạng thái

**Chưa có Reviewer thật review trong phiên này (R7-01)** — KHÔNG tự báo cáo "xong"/"sẵn sàng
release". Chờ PM giao Reviewer.

## Bước 2 (S2) — Fix 2 blocking issue từ Reviewer vòng 1/3, `scripts/validate_state.py` (Dev, 2026-09-11)

Phạm vi theo brief PM, trỏ `docs/review-report.md:2188-2374` (mục "Review Report — Port Protocol
A–F..."). Không đụng file nào khác ngoài `scripts/validate_state.py` (không sửa non-blocking #1/2/3
của cùng review — để dành vòng sau).

### Blocking #1 — `parse_day()` lỗ hổng im lặng

`check_infra()` giờ gọi `fail()` (không phải chỉ `warn()`) khi `parse_day(item["applied_at"])` trả
`None` — chọn nhánh mạnh hơn theo khuyến nghị của Reviewer, vì "ngày không parse được" tự nó đã là
dữ liệu hỏng, không nên chỉ cảnh báo rồi cho qua. Áp dụng bất kể `commit` đã set hay chưa (kiểm tra
`applied_at` chạy trước, `continue` sớm nếu không parse được — không để field `commit` che lấp lỗi
dữ liệu này).

### Blocking #2 — validator không thực thi phần lớn ràng buộc schema

Chọn **hướng (a)** trong 2 hướng Reviewer đề xuất: viết `check_against_schema()` — 1 checker generic
đệ quy thuần stdlib, đọc trực tiếp `project_state.schema.json` và tự áp `type` (kể cả union
`["string","null"]`), `required`, `additionalProperties` (bool hoặc schema con), `properties`,
`items`, `enum`, `pattern`, `maxLength`, `minimum`, `maximum`, `format=date`. Lý do chọn (a) thay vì
(b): (a) đóng đúng khoảng trống thật (schema và validator không còn 2 nguồn duy trì tay tách rời có
thể lệch nhau theo thời gian — chính cơ chế lỗi mà Protocol 5/6 của project này được viết ra để
phòng, chỉ khác lần này nằm trong chính công cụ phòng thủ); khối lượng code không lớn vì
`project_state.schema.json` không dùng `oneOf`/`$ref`/`allOf` phức tạp — xác nhận bằng cách đọc lại
toàn bộ schema trước khi viết checker. `main()` gọi `check_against_schema(state, schema, "")` trước
mọi luật nghiệp vụ khác; các hàm `check_*` còn lại (checkpoints/questions/backlog/steps/loops/infra/
blockers) chỉ còn áp riêng quan hệ CHÉO giữa nhiều field mà JSON Schema draft-07 không diễn đạt được
(vd `status=done` kéo theo phải có `output`) — không còn trùng lặp việc `check_against_schema()` đã
làm.

### Tự verify (không viết mock theo Architecture.md — đây là internal script, Protocol 5 N/A nhưng
vẫn tự verify bằng cách tái tạo đúng phương pháp Reviewer đã dùng)

Dựng 1 git repo cô lập tại scratchpad (`isolated_state_repo/`, không đụng `project_state.json` thật
của repo này), copy `scripts/validate_state.py` + `project_state.schema.json` +
`project_state.json` (làm baseline hợp lệ) vào đó, sinh 9 case bằng script Python (mutate baseline,
không viết tay JSON theo trí nhớ):

| Case | Kỳ vọng | Kết quả thật |
|---|---|---|
| `infra_pending[].applied_at` rác, `commit=null` | fail | ❌ bắt đúng (Blocking #1) |
| `infra_pending[].applied_at` rác, `commit` ĐÃ set | fail (không để `commit` che lấp) | ❌ bắt đúng |
| field lạ ở top-level (`totally_unexpected_top_field`) | fail | ❌ bắt đúng (Blocking #2) |
| field lạ lồng trong `checkpoints[]` | fail | ❌ bắt đúng |
| `open_questions[].id` sai pattern (không đúng tiền tố `HOI-`/`BUG-`) | fail | ❌ bắt đúng |
| `backlog[].id` sai pattern (không đúng tiền tố `BL-`) | fail | ❌ bắt đúng |
| `project_name` vượt `maxLength: 80` (200 ký tự) | fail | ❌ bắt đúng |
| `steps[].id` vượt `maxLength: 12` (20 ký tự) | fail | ❌ bắt đúng |
| baseline không mutate | pass | ✅ hợp lệ |

9/9 case đúng kỳ vọng. Sau khi xong, `git diff --stat project_state.json` ở repo thật vẫn y hệt
trước khi bắt đầu (diff tiền tồn tại từ trước phiên này, không phải do Dev gây ra trong lúc verify).

### Kết quả chạy thật

```
uv run pytest tests/ -q                              → 773 passed (không regression)
uv run ruff check src/ tests/ scripts/                → All checks passed!
uv run ruff format --check scripts/validate_state.py  → 1 file already formatted
```

### Trạng thái

Gửi lại Reviewer vòng 2/3 (`loops[]` pair `dev-reviewer` item `S2`, count hiện tại theo
`project_state.json`). Chưa tự báo "xong" (R7-01) — chờ Reviewer thật duyệt lại trước khi PM cân
nhắc commit.

## BL-04 — babeldoc không ghi finding khi tự drop đoạn không fit khung (Architecture.md §6.22)

Hoàn tất implementation (tiếp tục 1 phiên Dev trước bị lỗi hạ tầng giữa chừng — phần lớn code đã
có sẵn và hợp lệ, session này fix 1 test fail + chạy gate đầy đủ + live E2E).

### Nội dung đã implement (từ phiên trước, xác nhận lại)

- `src/babeldoc_shim/drop_report.py` (mới): predicate `_has_rendered_chars`, dựng record
  `header`/`page`/`drop`, ghi append JSONL — pattern giống `word_wrap.py`/`line_split.py`.
- `src/babeldoc_shim/sitecustomize.py`: patch `_create_render_units_for_page` (3 patch hook trong
  `_install_hook_if_version_matches()`).
- `src/core/chunking.py` (mới): `surviving_page_range(chunk, *, is_first_in_merge)` + Protocol
  `_ChunkLike` (structural typing, không import `src.models.chunk`).
- `src/postprocess/chunk_merge.py`: dùng `surviving_page_range(...)` thay khối tính tay, giữ
  nguyên guard `overlap_* is not None` và phần kẹp `end` theo `chunk_doc.page_count` (X3 — KHÔNG
  chuyển vào hàm chung).
- `src/services/babeldoc_runner.py`: `BabeldocDroppedParagraph`/`BabeldocDropReport`, set 2 env
  var (`BABELDOC_SHIM_DROP_REPORT`/`_PATH`), `drop_report_path` trong `output_dir`, parse sau
  `process.wait()`, đếm sentinel, `reports_own_paragraph_drops: ClassVar[bool] = True`.
- `src/services/pdf2zh_runner.py`: `reports_own_paragraph_drops: ClassVar[bool] = False` (R8-03 —
  capability khai báo trên object đại diện biến thể, không rẽ nhánh `if engine==` trong
  orchestrator).
- `src/services/layout_qa.py`: 3 `check_type` mới (`babeldoc_paragraph_drop_unfit`,
  `babeldoc_drop_report_unavailable`, `babeldoc_drop_report_incomplete`,
  `babeldoc_drop_report_mismatch`) + severity trong `_SEVERITY_BY_CHECK`.
- `src/core/job_orchestrator.py`: property `_reports_own_paragraph_drops`; trong `_process_chunk()`
  sau khối `OverflowReport`, lọc dải trang sống sót → đối chiếu `observed_pages` → map sang
  `LayoutQaFindingData` → `persist_findings()` → log R-1 (best-effort, `try/except` không làm fail
  chunk); log R-2 ở `run_job()` Bước 10 trước `job.status="completed"`, đếm bằng `SELECT COUNT`
  trên DB (X7 — không đếm từ list in-memory, để đúng khi resume sau crash).
- `src/core/config.py`: `babeldoc_drop_report_enabled: bool = True`.

### Fix trong session này — 1 test fail duy nhất

`tests/integration/test_job_orchestrator.py::test_pdf2zh_branch_untouched_by_babeldoc_drop_report`
(gate test #7, regression check Bug #9) fail: `assert len(overflow_result.all()) > 0` = 0.

**Root cause: (b) test tự nó sai, KHÔNG phải regression từ BL-04.** `_fake_pdf2zh_runner()`'s mono
output chỉ vẽ text `"page N"` qua `page.insert_text()` (giống `_make_pdf`) — đúng như
`font_shrink_page`'s docstring "Second implementation note" đã ghi rõ từ trước: `block["bbox"]` mà
`page.get_text("dict")` trả về được TÍNH TỪ CHÍNH các glyph đang bị so sánh, nên
`text_width <= bbox_width` LUÔN đúng với bất kỳ text nào PyMuPDF vừa tự vẽ ra — không có cách nào
để 1 trang PyMuPDF mới dựng tự nó tràn khung được, bất kể font/độ dài. Xác nhận thực nghiệm: đã đối
chiếu với `test_font_shrink_page_full_scan_no_overflow_for_normal_text` (test unit sẵn có, cùng kết
luận `entries == []`) và không có test nào khác trong repo (trước session này) từng assert
`OverflowReport` count `> 0` qua đường full-page scan thật.

**Cách sửa** (không nới lỏng assertion): thêm helper `_make_pdf_with_forced_overflow()` +
`_fake_pdf2zh_runner_with_forced_overflow()` dựng trang 0 của mono output bằng ký tự `"|"` (30 lần)
ở fontsize 14, vẽ bằng font mặc định PyMuPDF "helv" (`insert_text()` không chỉ định `fontname`) —
đo thật (`fitz.Font("helv").text_length()` vs `fitz.Font(fontfile=".../NotoSerif-Regular.ttf")`)
cho tỉ lệ mismatch ~2.15x giữa 2 font cho ký tự này, vượt xa ngưỡng ~1.47x cần để sống sót cả 2
bước giảm nhẹ (-20% font shrink, 85% condensed scale) và rơi đúng nhánh `still_overflow=True`.
Đây CHÍNH LÀ cơ chế overflow thật của production (mismatch giữa font THỰC TẾ vẽ trang và font
`font_shrink_page` dùng để ĐO lại, `Settings.noto_font_path`) — không phải một mẹo giả tạo tách
biệt khỏi logic thật. Assertion sau khi sửa cụ thể hơn: không chỉ đếm `> 0`, còn assert
`still_overflow=True`, `page_number == 0`, `font_size_original ≈ 14.0` (R6-02).

### Kết quả gate

```
uv run pytest tests/ -q                    → 816 passed (0 fail), 1101 warnings (pre-existing,
                                              không liên quan — RuntimeWarning aiosqlite thread
                                              teardown + FutureWarning google.generativeai)
uv run ruff check src/ tests/              → All checks passed!
uv run ruff format --check <files BL-04>   → All formatted (2 file cần format lại:
                                              tests/test_babeldoc_drop_report_shim.py,
                                              tests/test_chunking.py — đã sửa)
```

Không đụng tới 8 file khác đang lệch `ruff format` (`src/api/routes/jobs.py`,
`src/core/file_router.py`, `src/services/claude_provider.py`, `src/services/epub_document.py`,
`src/services/ollama_provider.py`, `src/services/openai_provider.py`, `src/utils/excel_utils.py`,
`src/utils/unit_conversion_table.py`) — không nằm trong phạm vi BL-04, không có trong git diff của
session này (đã xác nhận `git status --porcelain` sạch cho các file đó), khả năng do version
`ruff` bump (`uv.lock` cũng đang modified). Ghi nhận cho PM/Reviewer xử lý riêng, không tự ý sửa
ngoài phạm vi giao việc.

### Live E2E (R5-03 + R6-03) — 2 lần chạy thật

**Lần 1 — `scripts/bl04_live_e2e_chunk5.py`**: gọi TRỰC TIẾP
`JobOrchestrator._process_chunk()` (không qua `run_job()`, đúng harness X8) với `BabeldocRunner`
thật, DB session thật, `Chunk(chunk_index=5, page_start=199, page_end=240, overlap_start=199,
overlap_end=200)`, nguồn `data/uploads/f07b3194-…-Le-Cordon-Bleu-Patisserie-and-Baking-Foundations
(1).pdf` (418 trang, đúng `--pages 199-240`, KHÔNG cắt nhỏ — tránh bẫy mode-scale), model
`deepseek`. Kết quả:

- Assertion 0 (tiền điều kiện): `job.chunk_size_used == 40`, `page_start/end == 199/240` — PASS.
- Assertion 1: `drop_report.available=True`, `observed_pages == 42/42` — PASS.
- Assertion 6: log R-1 xuất hiện đúng định dạng (`observed=42/42`, `unfit_drops=0`,
  `suppressed_overlap=0`, `checksum_mismatch=0`, kèm câu PHẠM VI) — PASS.
- Assertion 2/3 (record tại trang 230): **KHÔNG tái hiện** — `unfit_drops=0` toàn bộ 42 trang, 0
  `LayoutQaFinding` được ghi. Theo đúng Architecture.md 6.22.9 "Nếu không tái hiện được... KHÔNG
  kết luận thiết kế sai" (dịch máy không tất định).
- Assertion 4 (R6-03 — mở PDF output bằng PyMuPDF, không chỉ tin số đếm): **đã tự mở**
  `chunk.output_path` trang index 31 (= trang nguồn 230). Đoạn sidebar 614 ký tự tiếng Anh ("The
  term feuilletage appeared in the 15th century… Carême who innovated the fifth turn") **THẬT SỰ
  VẮNG MẶT** khỏi bản dịch (đã đối chiếu trực tiếp với text trang 230 của file nguồn — đoạn đó có
  mặt nguyên vẹn ở nguồn, biến mất ở đích) — **cùng hiện tượng Domain Expert đã đo trên job
  `1ee1fdee`**. Nhưng sidecar JSONL của babeldoc (`page_number_1based=230,
  dropped_count=0`) xác nhận đây **KHÔNG phải kênh (1)** ("không vừa khung sau khi bóp tới
  min_scale") mà BL-04 đo — khớp đúng với câu PHẠM VI trong log R-1 ("chữ bị lọc ở
  `ActiveILCreater.project_native_char`… KHÔNG được đo bởi cơ chế này"). Đây là bằng chứng sống
  THỨ HAI (sau Domain Expert) rằng kênh (2)/BL-08 là có thật và đáng ưu tiên — không phải lỗi của
  BL-04, BL-04 báo cáo đúng những gì NÓ đo được.
- Assertion 5 (không finding tại trang chồng lấn 199-200): PASS nhưng **yếu** — vì tổng 0 finding
  nên đây là pass rỗng, không chứng minh được bộ lọc F1 thật sự loại trừ gì (cần 1 ca drop thật ở
  vùng chồng lấn để test có ý nghĩa — chưa có).

**Lần 2 (fallback (b) theo Architecture.md 6.22.9) — `scripts/bl04_live_e2e_synthetic_drop.py`**:
dựng PDF 1 trang tái tạo ĐÚNG hình học đã đo (bbox `(61.5, 223.6, 332.3, 466.6)`, 271×243pt, đúng
614 ký tự gốc), chạy `BabeldocRunner.translate_pages()` trực tiếp. Kết quả: babeldoc **không dịch**
trang này (giữ nguyên tiếng Anh), `dropped_count=0`. Không kết luận thêm được gì — nhiều khả năng
trang đơn lẻ thiếu ngữ cảnh layout xung quanh khiến bộ phân loại layout của babeldoc xử lý khác
(không phải lỗi BL-04). Không thử thêm lần 3 (chi phí gọi API thật, đã có 2 lần chạy thật hợp lệ
cho R5-03).

**Golden fixture mới**: `tests/fixtures/babeldoc/drop_report_v2.jsonl` — copy nguyên văn sidecar
JSONL thật từ lần chạy 1 (4 header, 42 page, `dropped_count=0` toàn bộ, không có dòng `drop` nào —
xem `tests/fixtures/babeldoc/README.md` mục "drop_report_v2.jsonl" cho investigation đầy đủ). Test
mới: `test_parse_drop_report_file_reads_real_live_e2e_golden_fixture`
(`tests/test_babeldoc_runner.py`) — phủ nhánh `header`/`page`/`observed_pages` bằng byte thật;
nhánh `type=drop` (field `text_excerpt` v.v.) vẫn dựa vào
`test_parse_drop_report_file_reads_real_written_file` (dữ liệu mô phỏng đúng schema đã verify qua
source, KHÔNG phải byte live-capture — 2 lần thử live đều không tạo ra dòng `drop` thật).

### R5-03 kết luận

Đã có ≥1 lần gọi thật (2 lần) tới `babeldoc` 0.6.4 CLI + DeepSeek API thật — điều kiện tối thiểu
thoả. Chưa verify được (và có nêu rõ, không giấu): nhánh `type=drop` end-to-end (từ babeldoc dừng
thật → shim ghi dòng `drop` thật → orchestrator map sang `LayoutQaFinding` thật) — 2 lần thử live
đều không tạo ra ca drop kênh (1) thật để quan sát trọn vẹn nhánh này; nhánh này vẫn được phủ ở
mức "schema verified qua source + mapping test dùng sidecar dựng tay đúng schema"
(`test_babeldoc_drop_finding_page_number_traces_to_sidecar_file`,
`tests/integration/test_job_orchestrator.py`), không phải live-capture. Đề xuất: PM/QA cân nhắc có
đáng đầu tư thêm 1 lần chạy live (option (a) Architecture.md 6.22.9 — dịch nguyên cuốn 418 trang
cùng model/prompt job `1ee1fdee`) trước khi release, hay chấp nhận mức verify hiện tại.

### KHÔNG commit

Theo brief — PM điều phối commit sau khi Reviewer + QA duyệt qua vòng thật.

## S4 — Bug #EPUB-5: DeepSeek thinking mode gây runaway giả cho EPUB (K-1..K-5)

Dev: implement theo đúng thứ tự bắt buộc của Architecture.md §6.20.15 (Tech Lead đã chỉ định thứ tự,
không được đảo). RCA gốc: `deepseek-v4-flash` bật thinking mode mặc định, `usage.completion_tokens`
lẫn cả token suy luận, khiến `is_runaway_output()` so sánh sai và kích hoạt abort R-b gần như luôn
luôn cho job EPUB thật.

### Bước 1 — Spike R5-02 (bắt buộc chạy TRƯỚC K-2/K-3)

Gọi thật `deepseek-v4-flash` 2 lần (baseline thinking mặc định + `extra_body={"thinking":
{"type":"disabled"}}`), lưu `response.usage.model_dump()` vào golden file
`tests/fixtures/epub_llm/deepseek_v4flash_usage.json`. Cả 2 câu hỏi bắt buộc đều XANH:
- (a) `completion_tokens_details.reasoning_tokens` tồn tại, khác 0: **833** trên **933**
  `completion_tokens` tổng ở baseline → K-2 hợp lệ, không cần escalate.
- (b) Endpoint chấp nhận `extra_body` (không HTTP 400); khi tắt thinking,
  `completion_tokens_details` biến mất hoàn toàn (`None`, không phải object có `reasoning_tokens=0`)
  → K-3 hợp lệ, và code phải xử lý đúng ca `None` này (không chỉ `reasoning_tokens=0`).

### Bước 2 — K-5 (song song với spike, thuần logic)

`src/core/job_orchestrator.py` (`_process_epub_chunk()`, quanh dòng 2397): điều kiện abort R-b đổi
từ `if runaway and missing_ids:` (abort khi thiếu BẤT KỲ id nào) sang
`if runaway and len(missing_ids) > EPUB_MAX_SINGLE_ID_RETRIES:` — với ≤ 2 id thiếu, đi qua thang cứu
hộ C-1 (retry từng-id, rẻ, tỉ lệ thành công cao) thay vì abort cả chunk (đúng cái bẫy đã làm 3 job
EPUB thật chết ở §6.20.13.3b trước K-5).

### Bước 3 — K-2 (sau spike xanh)

`src/services/translation.py`: `TranslationResult` thêm field `reasoning_tokens: int = 0` +
property `answer_tokens` (= `max(0, output_tokens - reasoning_tokens)`, CHỈ dùng cho phép đo
runaway). `src/services/openai_provider.py`: `translate()` đọc
`getattr(getattr(response.usage, "completion_tokens_details", None), "reasoning_tokens", 0) or 0` —
xử lý đúng cả 3 ca: field tồn tại khác 0, `completion_tokens_details=None` (thinking đã tắt), và
provider không có field này (OpenAI/Claude → mặc định 0). `output_tokens` GIỮ NGUYÊN =
`completion_tokens` thật (tính tiền không đổi, không được ước thấp — §6.11.6).
`job_orchestrator.py` đổi 2 dòng đo runaway sang dùng `result.answer_tokens` thay vì
`result.output_tokens`; `requests.jsonl` ghi thêm 2 field `reasoning_tokens`/`answer_tokens` (giữ
nguyên field cũ).

### Bước 3b — K-3 (song song K-2, sau spike xanh)

`src/services/openai_provider.py`: thêm `supports_thinking_toggle: bool = False` (class attribute,
R8-03 — không rẽ nhánh `if provider_name == "deepseek"`) + instance attribute
`disable_thinking: bool = False` + hook `_extra_body() -> dict` (mặc định `{}`).
`src/services/deepseek_provider.py`: `DeepSeekProvider.supports_thinking_toggle = True`,
`_extra_body()` trả `{"thinking": {"type": "disabled"}}`. `translate()` chỉ truyền `extra_body=`
khi CẢ `supports_thinking_toggle` LẪN `disable_thinking` đều đúng trên instance đó.

**Lệch có chủ đích so với pseudocode nháp của Architecture.md** (đã cập nhật lại §6.20.15 K-3 cho
khớp): pseudocode gốc gợi ý "truyền `extra_body` khi `_extra_body()` khác rỗng" — hiểu thẳng sẽ tắt
thinking cho MỌI lần gọi `DeepSeekProvider.translate()`, kể cả `glossary.py` (dịch glossary term) và
`rotated_text_overlay.py` (PDF babeldoc), trong khi Hiếu chỉ duyệt HOI-04 cho **riêng nhánh EPUB**.
Fix: `disable_thinking` là **instance attribute**, mặc định `False` (hành vi không đổi cho mọi
provider/call site khác); `src/core/job_orchestrator.py` (`run_epub_job()`) tự bật
`pricing_provider.disable_thinking = True` NGAY sau khi tạo provider, CHỈ trong nhánh EPUB, theo
`Settings.epub_disable_thinking` (mới, `src/core/config.py`, mặc định `True`) VÀ
`getattr(pricing_provider, "supports_thinking_toggle", False)` — vẫn đúng tinh thần R8-03 (hỏi
capability trên object, không hardcode theo tên provider), chỉ thêm 1 lớp "ai được phép bật cờ" để
không rò rỉ sang PDF/glossary ngoài phạm vi Hiếu đã duyệt.

### Bước 4 — Live E2E 1 cuốn thật (gate G-2, Architecture.md §6.20.15)

Job `bfc0ac24-0664-4932-96da-1ac99c1abc10`, `Sourdough Culture A History of Bread Making...epub`
(66 chunk), qua ĐÚNG `JobOrchestrator.run_job()` thật (không mock), `deepseek-chat` (repoint server
`deepseek-v4-flash`), `epub_disable_thinking=True` mặc định. Kết quả: **66/66 chunk `completed`**,
**784 request**, **0 abort vì R-b**, **0/784 request có `reasoning_tokens` khác 0** (K-3 hoạt động
đúng trên toàn bộ sách thật, không chỉ 1 request spike). `runaway_ratio` (đo bằng `answer_tokens`):
mean 0,7048 · median 0,7234 · **max 0,9119** — xa dưới `EPUB_RUNAWAY_OUTPUT_FACTOR=3,0`. Chi phí
thật: $0,588 / 2.043.387 token. Số đo đầy đủ đã ghi vào Architecture.md §6.20.15 mục K-4.

**Phát hiện MỚI, KHÔNG sửa trong lượt này** (đã ghi `docs/design-log.md`): job cuối cùng vẫn
`status="failed"` ở bước MERGE (sau khi cả 66 chunk đã dịch xong) — guard OCF-compliance có sẵn từ
trước trong `EpubDocument.write_translated()` (`infolist[0].compress_type == zipfile.ZIP_STORED`)
từ chối file nguồn vì entry `mimetype` của nó bị nén (`ZIP_DEFLATED`, vi phạm OCF spec). Không thuộc
phạm vi Bug #EPUB-5 — báo lại PM/Tech Lead quyết định có nới guard hay không.

### Bước 5 — K-1 (song song, độc lập — CẤM báo cáo là "fix Bug #EPUB-5")

`src/services/epub_document.py`: thêm `_unwrap_kobo_spans(soup)`, gọi TRONG `_parse_xhtml()` (điểm
vào DUY NHẤT mà `load()`/`write_translated()`/`count_bb_vi_pairs()`/`to_markdown()` đều dùng chung)
— unwrap (giữ nguyên con, KHÔNG `decompose()`) mọi `<span>` có class chứa đúng token `koboSpan`,
deny-by-default (Protocol 8 R8-02): KHÔNG đụng span khác (vd pagebreak). K-1 chỉ sửa lãng phí
chi phí/độ ồn payload (markup Kobo chiếm ~50,5% payload đo trên `Sourdough Culture.epub`), KHÔNG
làm job nào runaway ít hơn — bản vá thật cho Bug #EPUB-5 là K-2/K-3/K-5 ở trên.

### Bước 6 — K-4: quyết định KHÔNG đổi hằng số (có số đo, không phải bỏ qua)

Đo `chars_per_answer_token` trên toàn bộ 784 request live (bước 4): min 1,89 · median 2,386 · max
7,66. Formula hiện tại (`CHARS_PER_TOKEN_VI=2.0`, `VI_CHAR_EXPANSION=1.16`) đã an toàn (max
`runaway_ratio` đo được = 0,9119 << tiêu chí ≤1,5× của K-4 bước 3, và << ngưỡng abort 3,0) — quyết
định KHÔNG đổi cả 3 hằng số, lý do đầy đủ (đặc biệt: `VI_CHAR_EXPANSION` dùng CHUNG với
`estimate_job_cost_v2()` cho PDF, đo trên cơ sở ký tự khác với `payload_chars` ở đây — đổi sẽ làm
sai lệch ước lượng chi phí PDF không liên quan) đã ghi vào Architecture.md §6.20.15 mục K-4.

### Test

`tests/test_openai_provider_thinking.py` (mới, 6 test — mock dựng TỪ golden file thật, R5-03),
`tests/test_epub_document.py` (+2 test K-1, R6-02: xác nhận `load()`/`write_translated()`/
`to_markdown()` dùng chung 1 phép unwrap), `tests/integration/test_epub_translate_guards.py` (+4
test K-5/K-3, sửa 2 test cũ theo hợp đồng mới của R-b). Toàn bộ `tests/` (827 test, bao gồm
integration) + `ruff check`/`ruff format` sạch.

### KHÔNG commit

Theo brief — PM điều phối commit sau khi Reviewer + QA duyệt qua vòng thật.

## S5 — UI hint "chọn thư mục tải về" (không code logic, dựa hoàn toàn vào browser)

Theo `docs/Architecture.md` §6.24 (đã Tech Lead verify qua source Chromium/Firefox thật, không
suy đoán). Chỉ sửa HTML tĩnh, không thêm JS, không đụng `web/js/*.js` hay `src/`.

`web/index.html`: thêm `<span class="text-xs text-gray-400 cursor-help" title="...">ⓘ Chọn nơi
lưu</span>` ngay sau 2 link download trong `div.mt-2.flex.gap-2` (khu vực `x-show="f.job?.status
=== 'completed'"`), tooltip hướng dẫn bật "Ask where to save each file before downloading"
(Chrome) / "Ask where to save files before downloading" (Firefox) — nguyên văn theo §6.24, không
sửa/rút gọn.

`web/history.html`: bảng lịch sử lặp `<tr>` qua nhiều job (`x-for="job in jobs"`) nên KHÔNG nhân
bản hint theo từng dòng — đặt 1 lần duy nhất ở `<th>` cuối cùng của header bảng (cột chứa 2 link
Tải), cùng nội dung tooltip như trên.

### Test

Không sửa Python — chạy lại toàn bộ `pytest` để xác nhận không phá gì: 827 passed. Không cần
ruff (không đổi file `.py`).

### KHÔNG commit

Theo brief — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7, Protocol A).

## BL-10 — `cost_source='metered'` thật cho chunk PDF dịch bằng babeldoc

Theo `docs/Architecture.md` §6.23. Trước bản này, `jobs.cost_source`/`chunks.cost_source` (cột mới)
luôn là ước lượng ±30–50% cho MỌI job PDF — kể cả babeldoc, engine tự đếm token thật từ
`response.usage` và in ra stdout cuối mỗi lần chạy CLI (đã verify T2/T4 §6.23.1). Lý do đổi: số
tiền hiển thị cho user sai lệch lớn dù dữ liệu thật đã có sẵn trên stdout mà app vốn đã capture
cho 2 mục đích khác (`RATE_LIMIT_LINE_RE`, BL-04 drop sentinel).

**R5-02 spike (bắt buộc trước khi viết regex chính thức)**: chạy babeldoc 0.6.4 thật 2 lần —
(1) dựng lại chính xác cấu hình `logging.basicConfig(handlers=[RichHandler()])` của
`main.py:918-920` với số giả để xác nhận hình dạng dòng log khi redirect non-tty; (2) chạy
end-to-end thật (API key DeepSeek thật, 1 trang PDF, đúng flag app dùng) để verify nốt 2 mục
`⚠️ ASSUMED` còn treo ở §6.23.1. Kết quả: khớp 100% với đặc tả §6.23.2 (tiền tố
`INFO:babeldoc.main:`, không dấu phân cách nghìn, 4 dòng trên stdout không phải stderr) — không
có escalation nào cần báo Tech Lead. Golden file lưu tại
`tests/fixtures/babeldoc/token_usage_stdout.txt` (stdout thật, không chứa API key).

`src/services/babeldoc_runner.py`: `BabeldocTokenUsage` (dataclass 4 số, không gộp thành 1 field
`total` vì input/output rate khác nhau — tránh đoán tỷ lệ split), `parse_babeldoc_token_usage()`
(case-sensitive tuyệt đối để không nhầm `Prompt tokens:` với `Cache hit prompt tokens:`, chỉ đọc
`stdout` không nối `stderr`, thiếu 1 trong 3 dòng bắt buộc → `None` chứ không đoán — deny-by-default
đúng tinh thần Protocol 5 mục 4), `BabeldocResult.real_token_usage`, capability
`reports_token_usage: ClassVar[bool] = True`.

`src/services/pdf2zh_runner.py`: `reports_token_usage: ClassVar[bool] = False` (pdf2zh vứt bỏ
`response.usage`, không có gì để parse).

`src/core/job_orchestrator.py`: property `_reports_token_usage` (cùng khuôn `_needs_font_shrink`,
guard `isinstance` — bắt buộc vì `AsyncMock(spec=...)` không copy giá trị `ClassVar`, chỉ copy
tên); `_process_chunk()` rẽ 2 nhánh theo capability của engine ĐÃ CHỌN (R8-03) — không hỏi tên
engine; `rollup_cost_source()` (module-level) áp cho `jobs.cost_source` ở cả Bước 10 và nhánh
`cost_capped` — trộn lẫn chunk metered/estimated luôn cho ra `'estimated'` (một tổng chứa số ước
lượng thì bản thân nó là ước lượng, không tạo giá trị thứ ba); nhánh EPUB (đã `'metered'` từ §6.20)
được bổ sung ghi `chunk.cost_source = "metered"` ở cả 4 điểm ghi `api_cost` (kể cả 3 điểm raise lỗi
giữa chừng) — trước bản này cột mới sẽ nói dối `'estimated'` cho chunk EPUB dù số đã đo thật từ
lâu.

`src/models/chunk.py` + `src/models/database.py`: cột `chunks.cost_source` mới, `Field(default=...,
sa_column_kwargs={"server_default": "estimated"})` — KHÔNG chỉ `default` Python, vì
`_migrate_chunks_unit_columns()` rebuild bảng `chunks` bằng `create_all()` rồi INSERT SELECT đúng
danh sách cột CŨ (không có `cost_source`); thiếu `server_default` ở mức SQL, SQLite raise NOT NULL
constraint failed ngay khi migrate DB dev cũ (phát hiện qua chạy test migration thật, không phải
suy đoán).

Audit Protocol 8 (R8-01, đã làm sẵn ở §6.23.6): duyệt lại TỪNG bước hậu kỳ có sẵn trong
`_process_chunk()` (kể cả bước cũ như `shutil.rmtree` đầu mỗi attempt, `font_shrink_page`) — chỉ
duy nhất bước `estimate_chunk_cost()` đổi vai trò (đường chính → fallback), không bước nào khác bị
ảnh hưởng.

### Test

`tests/test_babeldoc_runner.py` (+6 test: golden parse, chống nhầm cache-hit, thiếu dòng → `None`,
`translate_pages()` gắn `real_token_usage` từ golden stdout thật, capability flag). Cập nhật 8 chỗ
`AsyncMock(spec=Pdf2zhRunner/BabeldocRunner)` rải rác trong `tests/integration/test_job_cancel.py`,
`test_job_orchestrator_concurrency.py`, `test_job_orchestrator.py` để set tường minh
`reports_token_usage` (guard `isinstance` mới sẽ raise `TypeError` nếu quên — đúng thiết kế, không
phải regression).

`tests/integration/test_job_orchestrator.py` (+5 test, R6-02 — assert giá trị cụ thể truyền giữa
các bước, không chỉ "đã gọi"): `test_metered_chunk_lineage` (chunk trung tâm — `api_tokens_used`
bằng đúng `total_tokens` từ `BabeldocResult` của CHÍNH chunk đó, `api_cost` tính lại bằng chính
`provider.estimate_cost()` chứ không hard-code số tiền), `test_estimated_fallback_when_no_token_line`
(chứng minh không silent-break hành vi cũ khi `real_token_usage=None`), `test_pdf2zh_never_metered`,
`test_reports_token_usage_property_isinstance_guard_catches_unset_mock`, `test_rollup_cost_source`.

Toàn bộ `tests/` (838 test, bao gồm integration) + `ruff check`/`ruff format` sạch cho mọi file đã
sửa.

### Giới hạn đã biết (theo §6.23.8, KHÔNG sửa trong task này)

Bảng giá `deepseek_provider.py` có thể lỗi thời (task riêng) — `'metered'` ở đây nghĩa là "token là
số đo thật", không phải "số tiền chắc chắn đúng". Không chiết khấu cache-hit (`cache_hit_prompt_tokens`
đã parse nhưng chưa dùng để tính tiền — sai an toàn theo hướng ước cao). Under-count khi có retry
(token của attempt thất bại không được cộng). `Total tokens: 0` hợp lệ khi babeldoc tự cache — vẫn
là `'metered'`, không phải lỗi parse.

### KHÔNG commit

Theo brief — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7, Protocol A).

## BL-12 — EPUB nguồn không tuân thủ OCF (`mimetype` bị nén): chuẩn hoá khi ghi, reject sớm khi thiếu hẳn

Implement theo `docs/Architecture.md` §6.25 (Final Decision Hiếu 2026-09-16, xem `docs/design-log.md`
mục BL-12: BL-12-Q1 = Phương án D, BL-12-Q2 = reject sớm).

### Sửa

`src/services/epub_document.py`:

- **L1 (pre-flight, tại `EpubDocument.load()`)**: thêm `_check_mimetype_entry()`, gọi ngay sau
  `_check_drm()` — trước khi parse `container.xml`. Reject sớm (`EpubParseError`, map sẵn sang HTTP
  400 qua `api/routes/jobs.py:376-380`, chạy TRƯỚC cost gate vì `cost_gate.py:167` gọi
  `EpubDocument.load()`) khi entry `mimetype` **thiếu hẳn** hoặc nội dung khác
  `b"application/epub+zip"` — KHÔNG tự chế entry thay user (deny-by-default, R8-02). KHÔNG kiểm
  thứ tự/`compress_type` ở bước này — đó là vi phạm *sửa được*, xử lý ở L2.
- **L2 (normalize khi ghi, tại `write_translated()`)**: xoá 2 guard reject cũ
  (`infolist[0].filename != "mimetype"` và `compress_type != ZIP_STORED`, dòng 984-991 cũ). Thay
  bằng: tìm entry `mimetype` trong `infolist` bất kể vị trí gốc, luôn ghi nó **ĐẦU TIÊN** trong zip
  output với `compress_type = ZIP_STORED`; các entry còn lại giữ nguyên **thứ tự tương đối** và
  `compress_type` gốc. `extra` field của `mimetype` output luôn rỗng — không cần set tường minh vì
  `zipfile.ZipInfo(filename=...)` mới luôn có `extra = b""` và `writestr()` không có chỗ nào gán
  thêm (tự verify lại bằng đọc source `zipfile` đã cài trong `.venv`, KHÔNG kế thừa lại nguồn xác
  thực cũ của Tech Lead trong design-log — Protocol 5 áp dụng cho `zipfile`).
- **Xoá dead code**: dòng `new_info.flag_bits = info.flag_bits`. Tự verify độc lập (không chỉ tin
  lại design-log): đọc `zipfile.ZipFile._open_to_write()` trong bản Python đã cài
  (`.venv`, CPython 3.14.7) — `zinfo.flag_bits = _MASK_UTF_FILENAME` bị gán **đè vô điều kiện**,
  xác nhận dòng copy `flag_bits` từ input không có tác dụng gì.

Data lineage (R6-01) không đổi so với §6.20: `write_translated()` vẫn đọc lại `self.path` (file gốc
`data/uploads/...`) làm khuôn, ghi ra `merged_path`; chuẩn hoá `mimetype` xảy ra trong lúc ghi
`merged_path`, KHÔNG sửa tại chỗ file gốc.

### Test

`tests/test_epub_document.py` (+8 test mới, Protocol 5 mục 3 — không mock tay theo giả định):

- `test_bl12_violating_file_has_mimetype_deflated` — xác nhận lại tiền đề trên chính file THẬT đã
  gây bug (`data/uploads/4a752f64-..._Sourdough Culture...epub`, entry đầu `mimetype`, nội dung
  đúng, nhưng `compress_type == ZIP_DEFLATED`).
- `test_write_translated_normalizes_deflated_mimetype_from_real_violating_file` — round-trip trên
  CHÍNH file vi phạm thật: `load()` + dịch 1 unit + `write_translated()` phải THÀNH CÔNG (trước đây
  sẽ raise `EpubParseError` ở bước ghi); output `infolist()[0]` là `mimetype`, `ZIP_STORED`,
  `extra == b""`; `zipfile.testzip() is None`; `ebooklib.epub.read_epub()` đọc lại được.
- `test_write_translated_normalizes_synthetic_deflated_mimetype` — fixture tối thiểu tự dựng bằng
  `zipfile` (EPUB hợp lệ OCF, không phải mock cho hàm đang test) với `mimetype` DEFLATED ở đúng vị
  trí đầu — cùng assertion chuẩn hoá.
- `test_write_translated_moves_mimetype_to_front_when_not_first_entry` — fixture có `mimetype`
  KHÔNG phải entry đầu (STORED nhưng sai vị trí) — output vẫn phải đưa `mimetype` lên đầu, các entry
  còn lại giữ nguyên thứ tự tương đối với nhau (assert danh sách tên entry còn lại khớp chính xác,
  không chỉ "có mặt").
- `test_load_raises_parse_error_when_mimetype_entry_missing` — thiếu hẳn entry `mimetype` → `load()`
  raise `EpubParseError` (L1, BL-12-Q2).
- `test_load_raises_parse_error_when_mimetype_content_wrong` — entry `mimetype` tồn tại nhưng nội
  dung `text/plain` (khác `application/epub+zip`) → `load()` raise `EpubParseError` (L1, BL-12-Q2).

Test cũ `test_load_raises_parse_error_when_container_xml_missing` và mọi test dùng
`_build_minimal_epub()` không đổi hành vi (fixture sẵn có `mimetype` STORED đúng nội dung, qua L1
không raise).

Toàn bộ `tests/` (844 test) + `ruff check`/`ruff format --check` sạch cho `src/services/epub_document.py`
và `tests/test_epub_document.py`.

### Chưa làm (theo mục 8 design-log, cần backlog riêng — không thuộc phạm vi BL-12 này)

Đo hành vi reading system thật (Apple Books/Calibre/Kobo/Kindle Previewer) với `mimetype` bị nén +
cài `epubcheck` để kiểm định output độc lập — PM cần thêm vào `backlog[]` với owner rõ ràng (R5-06).

### KHÔNG commit

Theo brief — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7, Protocol A).

## S7 — Dịch FR→VI bên cạnh EN→VI (auto-detect ngôn ngữ nguồn, PDF + EPUB)

Implement theo `docs/Architecture.md` §6.26 (§6.26.1–6.26.9) — thiết kế đã qua audit Protocol 8
(R8-01/R8-02) và Protocol 5 (R5-01, contract pdf2zh/babeldoc/MinerU đã Tech Lead verify sẵn từ
source thật, không có phần nào `[UNVERIFIED]` cần Dev tự spike thêm).

### Data model

- `jobs.source_lang TEXT NULL` — cột mới, thêm qua `_NEW_NULLABLE_COLUMNS`
  (`src/models/database.py`), giữ nguyên DB hiện có. `NULL` ⇒ coi như `"en"` ở MỌI nơi đọc
  (deny-by-default, R8-02). Field mới trên `src/models/job.py`.
- `JobDetail` (`src/api/routes/jobs.py`) thêm `source_lang: str | None` (chỉ đọc) — `_to_detail()`
  serialize từ `job.source_lang`.

### Module mới — `src/core/language_detector.py`

`detect_source_lang(text: str) -> LanguageDetection` — heuristic tỷ lệ hư từ (function word),
thuần Python, KHÔNG thêm dependency ngoài. Wordlist: tái dùng `en_function_words.txt` đã có (cho
`term_extractor`), thêm mới `src/core/wordlists/fr_function_words.txt` (loại tường minh các từ mơ
hồ EN/FR theo đúng danh sách Tech Lead chỉ định ở §6.26.3). Kết luận `lang` chỉ khi CẢ 3 điều kiện
thoả: `token_count >= 500`, `max(en_share, fr_share) >= 0.05`, tỷ số winner/loser `>= 3.0` — ngược
lại `lang = None`, KHÔNG đoán bừa.

Verify thật (không phải giả định): chạy trên 8 tài liệu EN thật trong `data/uploads/` (dev machine,
không commit — `data/` gitignored) — mọi tài liệu ≥500 token đều detect đúng `"en"`, tách biệt
en_share/fr_share > 40 lần. Test suite dùng 2 đoạn văn EN/FR thật (~600 từ mỗi bên, tự viết, không
phải câu ngắn bịa sẵn) tại `tests/test_language_detector.py`.

### Data lineage (R6-01/R6-02) — detect chạy đúng 1 lần/job

1. **`cost_gate.estimate_translation_cost()`** (`src/core/cost_gate.py`): thêm
   `detect_source_lang(full_text)` ngay tại cả nhánh PDF lẫn EPUB; `DetailedCostEstimate` mang thêm
   `source_lang: str | None`. Nhánh `pdf_scan`: `full_text` gần rỗng (chưa OCR) ⇒ `token_count < 500`
   ⇒ `source_lang = None` **có chủ đích** — KHÔNG ép "en" ở bước này, để `run_job()` Step 3 detect
   lại trên cầu nối searchable PDF sau OCR.
2. **`api/routes/jobs.py::create_job()`**: ghi thẳng `cost_estimate.source_lang` vào
   `Job(source_lang=...)` (chỉ cho `job_type == "translate"`, `None` cho `parse_only`).
3. **`job_orchestrator.py::run_job()` Step 3 / `run_epub_job()`**: fallback detect khi
   `job.source_lang is None` lúc đó (ca `pdf_scan`, hoặc job tạo ngoài API/test) — detect trên
   `full_text`/`doc.full_text()` rồi persist **1 lần**, giữ nguyên qua mọi lần resume (cùng khuôn
   với `chunk_size_used`).
4. Từ đó mọi bước đọc `job.source_lang or "en"`, không ai detect lại/hardcode `"en"` nữa — 6 điểm đã
   sửa theo đúng bảng lineage §6.26.4:
   - Step 5 `write_prompt_file()`/`write_babeldoc_prompt_file()` — babeldoc nhận `source_lang=`
     (pdf2zh's `_FILE_INTRO` giữ nguyên `${lang_in}`, không đổi).
   - Step 7 `translate_pages(lang_in=job.source_lang or "en")`.
   - Step 8 `overlay_rotated_text(glossary_prompt=await build_system_prompt(..., source_lang=...))`.
   - EPUB `build_system_prompt(..., source_lang=job.source_lang or "en")`.
   - EPUB retry (`_retry_single_unit`/`_retry_whole_epub_request`/`_process_epub_chunk` main call) —
     `pricing_provider.translate(p, system_prompt, source_lang, "vi")`, không còn literal `"en"`.
   - `cost_gate` — `build_prompt_text()`/`build_system_prompt()`/`estimate_job_cost_v2(source_lang=)`.

### MinerU — guard bắt buộc, KHÔNG đổi

`_run_mineru_and_record_quality()`/`_build_ocr_bridge()` **KHÔNG hề đụng tới** `job.source_lang` —
`MinerURunner.parse_document()` luôn dùng mặc định `lang="en"` (alias sang model `"ch"`, phủ Latin
theo Architecture.md §6.26.1, đã Tech Lead verify từ source MinerU 3.4.5). Test
`test_pdf_scan_mineru_always_called_with_lang_en_even_for_fr_job` pin `job.source_lang="fr"` và
assert MinerU vẫn nhận `lang="en"`.

### `src/core/prompt_builder.py` — chuỗi cứng "tieng Anh"

Thêm bảng `_SOURCE_LANG_NAME_VI = {"en": "tieng Anh", "fr": "tieng Phap"}`, không rẽ nhánh
`if lang == ...` rải rác. `_INTRO`/`_BABELDOC_INTRO` (chuỗi duy nhất thật sự nhắc tên ngôn ngữ) đổi
thành hàm `_intro(source_lang)`/`_babeldoc_intro(source_lang)`. `build_system_prompt()`,
`build_babeldoc_prompt_text()`, `write_babeldoc_prompt_file()` nhận thêm `source_lang: str = "en"`.
`_FILE_INTRO` (pdf2zh) giữ nguyên `${lang_in}`/`${lang_out}` — không đổi, pdf2zh tự thay thế.
`build_prompt_text()`/`write_prompt_file()` (pdf2zh) **không đổi signature** — không cần, nội dung
độc lập với `source_lang`. Test byte-identical bắt buộc: `source_lang="en"` (hoặc bỏ qua) cho ra
chuỗi giống hệt bản cũ (`test_prompt_builder.py`).

### `src/core/cost_estimator.py` — `CHARS_PER_TOKEN_FR`

Thêm hằng số `CHARS_PER_TOKEN_FR = 3.0` (⚠️ ASSUMED — `tiktoken` không có trong `.venv`, backlog
A-1 đo lại ở lần chạy live đầu tiên), thấp hơn `CHARS_PER_TOKEN_EN=4.0` có chủ đích: chars/token
thấp ⇒ token ước cao hơn ⇒ **ước dư**, đúng chiều an toàn §6.11.6. `_estimate_input_tokens()`,
`estimate_chunk_cost()`, `estimate_job_cost_v2()` nhận thêm `source_lang: str = "en"` — mặc định
giữ nguyên golden file EN (`test_estimate_job_cost_v2_never_underestimates_golden_incident` vẫn
xanh, không đổi input). Output (VI) không đổi theo `source_lang`.

### `src/core/term_extraction_service.py` — SKIP cho job FR (R8-02)

`extract_and_store_terms()` thêm guard `if (job.source_lang or "en") != "en": return 0` — đặt
TRONG service (không phải chỉ ở call site `jobs.py:537`) để cả đường tự động
(`_run_job_background`) LẪN đường thủ công (`POST /api/jobs/{id}/extract-terms`) đều được bảo vệ
như nhau, một nguồn sự thật duy nhất (lý do: `term_extractor._load_function_words()` chỉ nạp
`en_function_words.txt`, hư từ Pháp không bị lọc ⇒ n-gram rác).

### Protocol 8 audit (14 bước hậu kỳ, §6.26.5) — không đổi gì ngoài 2 mục trên

Đã đọc và làm đúng theo bảng Tech Lead: `font_shrink_page()` giữ nguyên (đo bề rộng glyph thật,
không phụ thuộc `source_lang`); glossary filter giữ nguyên (hệ quả "glossary gần rỗng cho FR" là
giới hạn đã biết, Hiếu chấp nhận theo HOI-09); guard diacritic tiếng Việt giữ nguyên ngưỡng (chỉ có
thể bỏ sót, không báo nhầm — lớp `_check_epub_output_guard()` bù độc lập).

### UI (bổ sung phạm vi 2026-09-16, qua PM/AskUserQuestion)

`web/index.html` (danh sách job) và `web/history.html` (lịch sử, thêm cột "Ngôn ngữ nguồn") hiện
badge `EN→VI`/`FR→VI` đọc từ `source_lang` trả về qua `JobDetail`. Auto-detect, không có dropdown
chọn thủ công (đúng HOI-09) — badge chỉ để user phát hiện detect sai sớm.

### Test (37 test mới, tất cả PASS lần chạy đầu, không cần sửa lại)

- `tests/test_language_detector.py` (6 test) — 2 đoạn văn EN/FR thật ~600 từ, ngưỡng token/share/tỷ
  số, gibberish/rỗng/quá ngắn trả `None`.
- `tests/test_prompt_builder.py` (+5 test) — byte-identical `source_lang="en"`, nội dung "tieng
  Phap" cho `source_lang="fr"`, prompt file thật (không chỉ hàm build trả đúng chuỗi).
- `tests/test_cost_estimator.py` (+6 test) — byte/số-for-số identical cho "en", FR ước input token
  cao hơn EN cùng input (không ảnh hưởng output).
- `tests/test_cost_gate_source_lang.py` (mới, 5 test) — PDF digital EN/FR thật (dựng bằng PyMuPDF
  `insert_textbox`), `pdf_scan` gần rỗng giữ `None` (không ép "en"), EPUB FR thật, so sánh input
  token EN vs FR.
- `tests/integration/test_job_orchestrator_source_lang.py` (mới, 7 test) — `lang_in` thật truyền
  vào `translate_pages()` (pdf2zh + babeldoc), MinerU luôn "en" dù job FR, detect+persist từ văn bản
  EN/FR thật khi `source_lang=None`, sống sót qua resume sau khi 1 chunk fail.
- `tests/integration/test_epub_job_source_lang.py` (mới, 3 test) — `source_lang` thật truyền vào
  `provider.translate()` cho EPUB (chính + qua toàn bộ pipeline), detect từ EPUB FR thật.
- `tests/integration/test_term_extraction_service.py` (+2 test) — skip hoàn toàn cho FR, vẫn chạy
  bình thường cho `source_lang=None` (coi như EN).
- `tests/test_jobs_route_to_detail.py` (+2 test) — `source_lang` serialize đúng qua `JobDetail`.
- `tests/integration/test_create_job_source_lang_api.py` (mới, 3 test) — E2E qua `TestClient` thật:
  `POST /api/jobs` ghi đúng `source_lang` detect từ file EN/FR thật, `GET /api/jobs/{id}` trả đúng,
  `parse_only` giữ `None`.

Toàn bộ `tests/` (881 test, tăng từ baseline 844) + `ruff check .` + `ruff format --check` (trên
mọi file đã sửa/tạo trong tăng này) sạch. 1 vi phạm format tiền-tồn tại không liên quan
(`src/api/routes/jobs.py:384`, xác nhận bằng `git stash` — có từ trước tăng này) — KHÔNG sửa, ngoài
phạm vi.

### Chưa làm / cần theo dõi

- **R6-03 (live E2E)**: CHƯA chạy 1 lần thật với PDF FR + EPUB FR ngoài đời (không có pdf2zh/
  babeldoc/MinerU thật + API key thật trong môi trường Dev này) — QA phải chạy trước khi release,
  hoặc ghi rõ "release blocked pending live verification" theo R5-03 nếu chưa chạy được.
- **Backlog A-1..A-4** (§6.26.7): cần xác nhận đã có entry trong `project_state.json` `backlog[]`
  với `source: "tech-lead"` trước khi coi tăng này đã đủ điều kiện đóng (R5-06) — Dev không tự thêm
  vào `project_state.json`, để PM/Tech Lead xử lý.
- Không tự ý đổi gì trong Architecture.md/design-log.md — chỉ đọc, không ghi (ngoài phạm vi Dev).

### KHÔNG commit

Theo brief — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7, Protocol A).

---

## BL-20 — Fix guard hết hạn ngầm chặn "Các từ mới" cho MỌI job EPUB (2026-09-17)

Theo `docs/Architecture.md` §6.27 + `docs/design-log.md` "2026-09-16 — RCA BL-20" mục 8 (Final
Decision, Hiếu 2026-09-17).

### Đã sửa

- `src/core/term_extraction_service.py`
  - Nhánh `if job.file_type == FileType.EPUB:` trong `_extract_source_text_for_terms()`: gỡ guard
    raise vô điều kiện (tiền đề "US-22 chưa implement" đã hết hạn từ 2026-09-10, commit `27d7daa`),
    thay bằng `EpubDocument.load(Path(job.file_path)).full_text()` đúng hợp đồng §6.18.5/§6.27.2.
    Bắt `EpubParseError` → bọc `TermExtractionSourceError` để `POST /api/jobs/{id}/extract-terms`
    vẫn trả 400 có thông báo, không lộ 500 mơ hồ.
  - Import `EpubDocument`, `EpubParseError` từ `src.services.epub_document`.
  - **KHÔNG** đụng guard `(job.source_lang or "en") != "en"` (§6.26.5 bước #13, chặn EPUB FR) — giữ
    nguyên theo đúng yêu cầu brief, đây là guard cố ý khác, không thuộc phạm vi BL-20.

### Test (R6-02 — thay test khẳng-định-bug, không chỉ xoá)

- `tests/integration/test_term_extraction_service.py`
  - **XOÁ** `test_lineage_epub_not_yet_supported_raises_clearly` (test bảo vệ chính cái bug, docstring
    "US-22 hasn't shipped... yet" đã hết hạn).
  - **THÊM** `_build_epub()` helper (EPUB thật dựng bằng `zipfile`, cùng pattern
    `test_epub_job_source_lang.py::_build_epub` — không mock tay `EpubDocument`, R5-03).
  - **THÊM** `test_lineage_epub_reads_full_text_not_inner_html`: EPUB thật có `<strong>` trong 1
    đoạn, assert text trả về **có** câu thật, **không** chứa `<strong`/`<p` — chứng minh đọc
    `full_text()` (text thuần), không phải `EpubUnit.text` (inner-HTML).
  - **THÊM** `test_lineage_epub_bad_file_raises_term_extraction_source_error`: file EPUB hỏng →
    `EpubParseError` từ `EpubDocument.load()` phải được bọc thành `TermExtractionSourceError`.
  - **THÊM** `test_extract_and_store_terms_writes_pending_rows_for_completed_epub_job` (R6-02, mức
    tương đương bước `_run_job_background()` gọi sau khi job `completed`): EPUB thật 3 đoạn lặp lại
    "Laminated dough" → `extract_and_store_terms()` viết `> 0` dòng `pending`, assert cụ thể
    `"laminated dough"` có trong `match_key` các dòng ghi ra — không chỉ `assert_awaited()`.
  - Guard EPUB FR không đổi: `test_extract_and_store_terms_skips_for_source_lang_fr` (đã có sẵn từ
    trước, PDF-based) tiếp tục pass nguyên vẹn, xác nhận fix này không ảnh hưởng guard đó.

Kết quả: `pytest tests/integration/test_term_extraction_service.py` 16 passed. Toàn repo
`pytest -q`: **883 passed**, 0 failed (tăng từ baseline trước fix). `ruff check` + `ruff format
--check` trên 2 file đã sửa: sạch.

### Backfill 2 sách thật (Final Decision câu 1, Hiếu 2026-09-17)

Server uvicorn đang chạy (dev, không có `--reload`) — không được phép restart (auto-mode chặn thao
tác kill process đang chạy), nên backfill chạy bằng script gọi thẳng
`extract_and_store_terms(job_id, session, settings)` (đúng code vừa fix, cùng hàm
`POST /api/jobs/{id}/extract-terms` gọi) trên `data/bb_translation.db` thật, không qua HTTP:

| Job | `job_id` | Dòng `suggested_terms` ghi ra |
|---|---|---|
| Sourdough Discard Recipes Cookbook | `88e897af-e19f-470c-9248-922fbc79596f` | **2.765** |
| Sourdough Every Day | `217097fd-6d72-4560-949d-439a4dbc60ec` | **2.650** |

Đã verify bằng `sqlite3 data/bb_translation.db` sau khi chạy: đúng 2 job có dòng, top `rank_score`
ra thuật ngữ hợp lý (`sourdough waste`, `sourdough discard`...). Không migration, không sửa DB tay,
khớp §6.27.5 và design-log mục 5 "Backfill".

### Guard "chưa implement" khác phát hiện trong lúc sửa (không tự gỡ — flag cho PM/Tech Lead)

Không tìm thấy guard nào khác cùng dạng "tính năng X chưa có nên nhánh này không thể bị gọi" trong
`src/core/term_extraction_service.py` khi đọc lại toàn bộ 4 nhánh `file_type` (`parse_only`,
`pdf_scan`, `pdf_digital`, `epub`) — 3 nhánh còn lại raise có điều kiện thật (file thiếu/rỗng), không
phải guard "chưa implement" vô điều kiện. Không mở rộng phạm vi tìm kiếm sang các file khác ngoài
brief.

### Chưa làm / cần theo dõi

- **R5-06 mở rộng (design-log mục 6 #3)**: luật mới "mọi guard chưa-implement trong `src/` phải trỏ
  `backlog[]` id" — Dev không tự thêm entry `project_state.json`, để PM/Tech Lead ghi nếu áp dụng
  cho phần code khác trong tương lai.
- BL-22 (thêm `jobs.term_extraction_error`, UI báo lỗi minh bạch) — theo Final Decision câu 2,
  **KHÔNG** làm trong tăng này, tách backlog riêng.
- **Server uvicorn chưa được restart** để chạy code fix qua đường HTTP thật (`POST
  /api/jobs/{id}/extract-terms`) — chỉ mới verify qua gọi thẳng hàm Python trên DB thật. PM/Hiếu cần
  quyết định thời điểm restart an toàn nếu muốn xác nhận thêm qua đường API.

### KHÔNG commit

Theo brief chung của repo — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7,
Protocol A).

## Fix — rerun `extract_and_store_terms()` UNIQUE constraint (2026-09-17)

Dev: fix bug QA phát hiện khi verify BL-20 qua HTTP thật (`docs/test-report.md`, mục "BL-20 — QA
gate cuối (2026-09-17)"): `POST /api/jobs/{id}/extract-terms` lần 2 trở đi trên job đã có
`suggested_terms` từ trước → HTTP 500 `sqlite3.IntegrityError: UNIQUE constraint failed:
suggested_terms.job_id, suggested_terms.term_en`.

### Root cause

`src/core/term_extraction_service.py:extract_and_store_terms()` xoá các dòng `pending` cũ
(`session.delete(row)`) rồi thêm dòng mới (`session.add(...)`) cùng `term_en` trong cùng 1 flush —
SQLAlchemy unit-of-work mặc định emit INSERT trước DELETE, nên candidate trùng `term_en` với row
pending vừa xoá đụng UNIQUE `(job_id, term_en)` trước khi DELETE kịp chạy. Bug tổng quát (tái hiện
cả PDF lẫn EPUB), không riêng BL-20 — chỉ lộ chắc chắn vì backfill 2 sách thật cho BL-20 khiến user
chạm lần đầu bấm "trích xuất lại".

### Fix

`src/core/term_extraction_service.py` (giữa vòng lặp delete và vòng lặp add trong
`extract_and_store_terms()`): thêm `await session.flush()` ngay sau vòng lặp `session.delete(row)`
cho các row `pending` cũ, trước khi bắt đầu `session.add(...)` cho candidate mới — ép SQLAlchemy
thực thi DELETE thật trước khi emit bất kỳ INSERT nào. Không đổi cấu trúc transaction (vẫn 1
`session.commit()` cuối hàm) — chọn cách ít thay đổi luồng nhất trong 2 hướng QA gợi ý (flush giữa
chừng vs. bulk DELETE SQL riêng).

### Test

`tests/integration/test_term_extraction_service.py` —
`test_extract_and_store_terms_rerun_with_all_rows_still_pending_does_not_raise`: test rerun MỚI,
khác test `test_extract_and_store_terms_rerun_preserves_decided_rows_refreshes_pending` đã có sẵn
(test cũ dismiss 1 row trước khi rerun nên vô tình né được đúng conflict này). Test mới để TOÀN BỘ
row ở trạng thái `pending` (không dismiss), gọi `extract_and_store_terms()` lần 2 trên cùng job,
assert: không raise, `second_written == first_written`, mọi row sau rerun vẫn `pending`, giữ đúng
`match_key` (`laminated dough`).

Kết quả: `pytest` toàn repo 884 passed; `ruff check` + `ruff format --check` sạch trên 2 file đã
sửa.

### Chưa làm / cần theo dõi

- Chưa tự verify lại qua HTTP thật (server có thể cần restart để chạy code fix mới) — để PM quyết
  định thời điểm restart an toàn, kiểm tra không có job `processing`/`translating` trước khi restart.
- Chưa qua Reviewer thật (Protocol 7 R7-01) — không được coi là "xong" cho tới khi có
  `docs/review-report.md` cho đúng thay đổi này.

### KHÔNG commit

Theo brief chung của repo — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7,
Protocol A).

## Fix theo Reviewer REJECT — test rerun BL-20 không tái hiện được bug (2026-09-17)

Reviewer (`docs/review-report.md`, mục "REJECT" cho lần fix rerun ở trên) phát hiện:
`test_extract_and_store_terms_rerun_with_all_rows_still_pending_does_not_raise` vẫn PASS ngay cả
khi Reviewer tự gỡ tạm `session.flush()` — test không tái hiện được `IntegrityError`. Root cause:
UNIQUE `(job_id, term_en)` được tạo bằng raw SQL riêng trong `init_db()`
(`src/models/database.py:184-188` cũ), KHÔNG nằm trong `SQLModel.metadata.create_all()`. Fixture
`session` (`tests/integration/test_term_extraction_service.py:40-50`) chỉ gọi `create_all()`, chưa
từng gọi `init_db()` → toàn bộ 17 test trong file (kể cả 15 test cũ đã pass từ trước) chạy trên DB
thiếu đúng constraint mà bug gốc phụ thuộc vào.

### Fix

1. Factor phần tạo 2 composite index của `suggested_terms` (`idx_suggested_terms_job_term` UNIQUE +
   `idx_suggested_terms_status_rank`) VÀ index `idx_glossary_entries_term_nocase` ra hàm riêng
   `_create_composite_indexes(conn)` trong `src/models/database.py`. `init_db()` gọi hàm này thay vì
   inline raw SQL như trước — hành vi production không đổi, chỉ tái cấu trúc để dùng chung.
2. `tests/integration/test_term_extraction_service.py` fixture `session` (dòng ~40-53): sau
   `create_all()`, gọi thêm `await _create_composite_indexes(conn)` (import từ
   `src.models.database`) — DB in-memory của test giờ có đúng UNIQUE constraint production có.

### Bằng chứng fail-then-pass (bắt buộc theo yêu cầu Reviewer/PM)

Với fixture đã sửa (có constraint thật), tạm gỡ `await session.flush()` khỏi
`extract_and_store_terms()` và chạy `pytest tests/integration/test_term_extraction_service.py -q -k
rerun`:

```
FAILED tests/integration/test_term_extraction_service.py::test_extract_and_store_terms_rerun_with_all_rows_still_pending_does_not_raise
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed:
suggested_terms.job_id, suggested_terms.term_en
[SQL: INSERT INTO suggested_terms (...) VALUES (...)]
[parameters: (..., 'job1', 'Laminated dough', 'laminated dough', ...)]
1 failed, 1 passed, 15 deselected
```

— test mới giờ ĐÚNG là bắt được bug khi fix bị gỡ. Khôi phục lại `flush()`, chạy lại cùng lệnh:

```
2 passed, 15 deselected
```

— cả 2 test rerun pass khi fix có mặt. Đây là bằng chứng test giờ thực sự tái hiện + xác nhận fix,
không chỉ "code không tự crash" như Reviewer chỉ ra ở lần trước.

### Test suite + lint toàn repo (sau khi đổi fixture dùng chung cho cả file)

- `pytest tests/integration/test_term_extraction_service.py -q -k rerun` → 2 passed (bằng chứng ở
  trên).
- `pytest -q` toàn repo → **884 passed** — không có test cũ nào lộ ra lỗi mới dù giờ chạy trên DB có
  đầy đủ constraint (khác lo ngại nêu ở mục "Việc Dev cần làm #3" của Reviewer — đã kiểm tra thật,
  không giả định).
- `ruff check src/models/database.py tests/integration/test_term_extraction_service.py
  src/core/term_extraction_service.py` → All checks passed.
- `ruff format --check` cùng 3 file → đã format sẵn.

### Verify qua HTTP thật — ĐÃ LÀM lần này (không mơ hồ như lần trước)

Reviewer lần trước phát hiện brief PM nói "Dev đã verify HTTP" nhưng CHANGELOG lần đó ghi đúng sự
thật là "chưa verify" — không mâu thuẫn ở đợt đó, nhưng lần NÀY Dev tự làm thật, ghi lại đầy đủ:

1. Kiểm tra không có job `processing`/`translating` nào (`sqlite3` query trên
   `data/bb_translation.db` → `active jobs: []`).
2. Kill server uvicorn đang chạy (pid 2021, lệnh gốc `uvicorn src.api.main:app --host 0.0.0.0 --port
   8000`), khởi động lại cùng lệnh để nạp code fix mới (factor `_create_composite_indexes`) — xác
   nhận `curl http://localhost:8000/api/jobs` → `200` sau restart.
3. Gọi `POST /api/jobs/27d764e8-05cc-404c-88cf-11b504831272/extract-terms` (job có sẵn 31
   `suggested_terms` ở `status=pending`, KHÔNG dismiss trước) **2 lần liên tiếp**:
   - Lần 1: `HTTP_STATUS:200`, body `{"job_id":"27d764e8-...","written":31}`.
   - Lần 2: `HTTP_STATUS:200`, body `{"job_id":"27d764e8-...","written":31}` — không `500`, không
     `IntegrityError`.
4. Query trực tiếp DB sau 2 lần gọi:
   `SELECT job_id, term_en, COUNT(*) FROM suggested_terms GROUP BY job_id, term_en HAVING COUNT(*) >
   1` → rỗng (không duplicate trên toàn DB, không riêng job này).
   `SELECT COUNT(*) FROM suggested_terms WHERE job_id='27d764e8-...' AND status='pending'` → `31`
   (không tăng lên dù gọi 2 lần).
5. Log server (`/tmp/uvicorn_bl20.log`) trong lúc gọi: không có dòng `error`/`exception`/`traceback`
   nào.

Kết luận: đã verify qua HTTP thật, xác nhận rõ ràng — KHÔNG mơ hồ. Đây là lần đầu tiên trong chuỗi
fix BL-20 có xác nhận HTTP thật sau khi fix đã áp dụng (các lần trước chỉ có xác nhận qua
integration test / query DB tĩnh).

### Chưa làm / cần theo dõi

- Chưa qua Reviewer thật cho ĐÚNG lần sửa này (Protocol 7 R7-01) — không được coi là "xong" cho tới
  khi có mục review mới trong `docs/review-report.md` (APPEND, không ghi đè — R7-03) xác nhận.
- Server production đang chạy đã được Dev tự restart để verify (mục trên) — nếu PM coi đây là thay
  đổi môi trường thật cần ghi `infra_pending[]` theo Protocol E, cần PM xác nhận và thêm entry
  tương ứng vào `project_state.json` (Dev không có quyền tự ghi state theo phân công tool hiện tại).

### KHÔNG commit

Theo brief chung của repo — PM điều phối commit sau khi Reviewer duyệt qua vòng thật (Protocol 7,
Protocol A).

## S8 — Tự động loại bỏ trang claim bản quyền trước khi dịch (PDF + EPUB), Dev, 2026-09-17

Implement theo `docs/Architecture.md` §6.28 (Tech Lead, 2026-09-17). Chưa qua Reviewer thật (Protocol
7 R7-01) — KHÔNG được coi là "xong" cho tới khi có mục review mới trong `docs/review-report.md`.

### File mới

- `src/core/copyright_detector.py` — bộ chấm điểm DUY NHẤT dùng chung PDF+EPUB (`scan_units()`,
  `PageVerdict`, `CopyrightScanResult`, hằng số `MIN_SCORE=5`/`MAX_WORDS=600`/`MIN_WORDS=5`/
  `MAX_REMOVED=3`, cửa sổ `PDF_HEAD=10/PDF_TAIL=5`, `EPUB_HEAD=6/EPUB_TAIL=3`). Verify khớp 100%
  bảng "Kết quả đo đầy đủ" của Architecture.md §6.28.2 trên toàn bộ 13 PDF + 6 EPUB thật đang có
  trong `data/uploads/` (script tay + `tests/test_copyright_detector.py`).
- `tests/test_copyright_detector.py` — golden test tham số hoá trên tài liệu thật (Protocol 5 mục
  3), gồm 2 ca âm bắt buộc (`Baking Heaven` 8đ/884 từ, `Better_For_You` © mọi trang) + test
  `too_many_candidates`/cửa sổ quét.
- `tests/integration/test_job_orchestrator_copyright_removal.py` — 7 test PDF (R6-02 lineage cả 2
  engine, artifact `original_pruned.pdf`, `create_bilingual_pdf` dùng đúng tham số, pdf_scan chạy
  sau OCR bridge, resume không quét lại, kill-switch byte-identical).
- `tests/integration/test_epub_orchestrator_copyright_removal.py` — 2 test EPUB pipeline (loại
  đúng doc khỏi `total_units`/payload gửi LLM, kill-switch).
- Bổ sung vào `tests/test_epub_document.py`: 4 test cho `write_translated(..., drop_doc_hrefs=...)`
  — gồm test bắt buộc trên EPUB thật khó nhất (`Sourdough Every Day`: nav + mini_toc + NCX) và
  nhánh `structural="skipped"` (fixture `<img src>` trỏ vào doc bản quyền).

### File sửa

- `src/services/epub_document.py`: thêm `opf_href` field, `EpubDocument.units_excluding()`,
  `EpubDocument.doc_plain_texts()`; `write_translated()` thêm tham số `drop_doc_hrefs` + trả về
  `dict[doc_href, "full"|"skipped"]` (hàm mới `_apply_structural_drops()` — tiền kiểm/hậu kiểm theo
  đúng 7 lớp tham chiếu (a)-(g) của §6.28.6.3, deny-by-default cho lớp (g) và navPoint có con).
- `src/core/job_orchestrator.py`: Step 2b mới (`_apply_copyright_removal()` cho PDF,
  `_apply_epub_copyright_removal()`/`_record_epub_structural_result()` cho EPUB) — chạy sau cầu nối
  OCR, trước `total_pages`/`plan_chunks()`. `create_bilingual_pdf()` đổi tham số 2 sang
  `bilingual_source_path` (chống Bug #9 phiên bản S8). Thêm capability property
  `_page_numbers_relative_to_input` (cùng khuôn `_needs_font_shrink`). `_check_epub_output_guard()`
  thêm tham số `dropped_doc_hrefs`. `_process_epub_chunk()` thêm tham số `dropped_doc_hrefs` — sửa
  `units = doc.units` thành `doc.units_excluding(dropped_doc_hrefs or set())` (bug lineage tự phát
  hiện khi viết test: `chunk_plan.unit_start/unit_end` được đánh số trên danh sách ĐÃ LỌC, dùng
  `doc.units` đầy đủ sẽ trỏ sai unit ngay khi có ≥1 doc bị loại — đúng hình dạng Bug #5 phiên bản
  EPUB, phát hiện TRƯỚC khi chạm production nhờ R6-02).
- `src/services/pdf2zh_runner.py`, `src/services/babeldoc_runner.py`: thêm ClassVar
  `page_numbers_relative_to_input = True` (R8-03), verify theo đúng nguồn đã trích trong
  Architecture.md §6.28.1 (không tự research lại).
- `src/core/config.py`: thêm `Settings.copyright_page_removal_enabled: bool = True`
  (`COPYRIGHT_PAGE_REMOVAL_ENABLED`).
- `src/models/job.py`, `src/models/database.py`: thêm cột `jobs.copyright_removed_json` qua
  `_NEW_NULLABLE_COLUMNS` (không tạo lại DB).
- `src/api/routes/jobs.py`: `JobDetail` thêm field `copyright_removed: list[str] | None`.
- `tests/integration/test_job_cancel.py`, `test_job_orchestrator.py`,
  `test_job_orchestrator_concurrency.py`, `test_job_orchestrator_source_lang.py`: thêm
  `runner.page_numbers_relative_to_input = True` vào mọi mock runner đã cấu hình đầy đủ (KHÔNG đụng
  2 gate test cố ý để thiếu thuộc tính — chúng test chính cơ chế `isinstance` guard).

### Lệch khỏi Architecture.md (cần Tech Lead/Reviewer xác nhận)

1. **`structural` trong `copyright_removed_json` cho EPUB là `dict[href, status]`, không phải giá
   trị đơn `"full"`/`"skipped"` như ví dụ scalar trong §6.28.3.** Lý do: `MAX_REMOVED=3` cho phép
   nhiều doc bị loại trong cùng 1 job, mỗi doc có thể có kết quả hậu kiểm khác nhau (1 doc "full", 1
   doc "skipped") — 1 giá trị scalar không biểu diễn được. Ghi `None` cho mode `pdf_pages` (không
   đổi, đúng ví dụ gốc).
2. **Phát hiện khi viết test (không phải bug production, nhưng là gap trong đặc tả gốc)**: rule (f)
   §6.28.6.3 "xoá `<li>/<p>` bao quanh nếu không chứa link/nested-list khác" — nếu container đó
   CHÍNH LÀ 1 `EpubUnit` đang được dịch (vd `mini_toc.xhtml`, 1 trong 2 ca thật có content-doc-
   thường trỏ tới, theo đúng bảng §6.28.6.1), xoá cả container sẽ làm lệch số `EpubUnit` đếm được
   giữa lúc `units_excluding()` tính (trước khi ghi) và lúc `EpubDocument.load()` đọc lại file output
   (sau khi ghi) — đúng hình Bug #5, phát hiện qua test tự viết thêm (không nằm trong test bắt buộc
   của brief) trên chính EPUB thật `Sourdough Every Day`. Fix: với container thuộc 1 doc ĐANG ĐÓNG
   GÓP unit dịch, LUÔN unwrap (giữ nguyên container, chỉ bỏ `<a>`) — không bao giờ xoá cả container,
   bất kể có link/nested-list khác hay không. Container chỉ bị xoá hẳn khi thuộc doc KHÔNG đóng góp
   unit nào (vd nav.xhtml thuần EPUB3, không nằm trong spine).

### Test

`ruff check .` + `ruff format --check` sạch trên toàn bộ file chạm tới. `pytest` toàn repo: 916
passed (884 test cũ không hồi quy + 32 test mới của S8), tại thời điểm viết mục này.
R6-03 (live E2E với PDF/EPUB thật xuyên suốt job thật, không mock) CHƯA chạy — để QA làm, ghi rõ
trong báo cáo cho PM.

## S8-B1 fix — `jobs.total_pages`/`jobs.total_units` không cập nhật sau khi cắt trang bản quyền (2026-09-17)

Sửa bug blocking do QA phát hiện qua live E2E (`docs/test-report.md` "Kết luận S8"), theo phương án
(c) đã chốt của Tech Lead (`docs/design-log.md` mục 2026-09-17 "S8-B1"). Xem thêm Architecture.md
§6.28.4 luật 0, §6.28.6.4.

### Code

- `src/core/job_orchestrator.py::_apply_copyright_removal()` (~:742-855): ghi `job.total_pages =
  len(keep_indices)` **vô điều kiện** (không kèm `is None`) ngay trong nhánh thực sự có cắt, commit
  trước khi return cặp path đã cắt. Guard `if job.total_pages is None` ở `run_job()` (:941) giữ
  nguyên — vẫn là đường compute-if-missing hợp lệ cho job không đi qua cắt.
- `src/core/job_orchestrator.py::_apply_epub_copyright_removal()` (~:857-935): đối xứng, ghi
  `job.total_units = len(doc.units_excluding(removed))` vô điều kiện khi có doc bị loại. Guard ở
  `run_epub_job()` (:1388) giữ nguyên.
- **c2 — sửa cùng gốc (chống silent corruption khi resume)**: cả 2 hàm trên đổi thứ tự kiểm tra
  kill-switch — kill-switch (`copyright_page_removal_enabled=False`) giờ chỉ gate **quyết định
  mới** (lần quét đầu chưa có Chunk row), KHÔNG gate **replay một quyết định đã cam kết**: nếu job
  đã có Chunk row VÀ `copyright_removed_json.removed` khác rỗng thì vẫn cắt lại đúng theo quyết
  định cũ, dù kill-switch hiện tại đang tắt (tránh `chunks.page_start/page_end`/`unit_start/
  unit_end` đã đánh số theo file đã cắt bị lệch khỏi file chưa cắt nếu bỏ cắt giữa chừng).
- **Không sửa** `src/api/routes/jobs.py:648,652` (route vẫn gán `total_pages`/`total_units` lúc tạo
  job như cũ — 3 chỗ khác phụ thuộc: `GET /jobs/{id}/cost-estimate`, `web/js/app.js`,
  `web/js/history.js`, theo đúng phân tích RCA của Tech Lead).

### Test

- `tests/integration/test_job_orchestrator.py::_create_job()`: sửa để gán `total_pages` giống hệt
  `POST /api/jobs` (đếm trang thật bằng `fitz`) — đây là root cause khiến bug lọt lưới qua Reviewer
  lần trước (fixture rơi vào nhánh `is None` không bao giờ xảy ra trên đường sản xuất). Toàn bộ test
  dùng helper này (nhiều file, xem `grep -rn "_create_job(" tests/`) đã chạy lại, không có test nào
  vỡ.
- `tests/integration/test_epub_orchestrator_copyright_removal.py::_create_epub_job()`: đối xứng,
  gán `total_units = len(EpubDocument.load(epub_path).units)` (số unit ĐẦY ĐỦ trước khi loại, đúng
  ý nghĩa `cost_estimate.total_units` mà route thật dùng).
- Thêm mới:
  - `test_apply_copyright_removal_idempotent_across_resume_calls` — gọi `_apply_copyright_removal()`
    2 lần liên tiếp trên cùng job, assert `total_pages`/paths không đổi giữa 2 lần.
  - `test_kill_switch_disabled_midway_still_replays_committed_decision` — kill-switch tắt SAU khi
    job đã cắt thật + đã có Chunk row, assert vẫn cắt lại đúng theo quyết định đã cam kết.
  - `test_apply_epub_copyright_removal_idempotent_across_resume_calls`,
    `test_kill_switch_disabled_midway_epub_still_replays_committed_decision` — đối xứng cho nhánh
    EPUB.

`pytest` toàn repo: 920 passed (không hồi quy). `ruff check` + `ruff format --check` sạch trên toàn
bộ file đã sửa (`src/core/job_orchestrator.py`, `tests/integration/test_job_orchestrator.py`,
`tests/integration/test_job_orchestrator_copyright_removal.py`,
`tests/integration/test_epub_orchestrator_copyright_removal.py`) — 15 file khác trong repo không
liên quan tới thay đổi này đang lệch `ruff format` từ trước (không đụng vào, không thuộc phạm vi
task).

**Chưa qua Reviewer thật trong session này (R7-01)** — không tự báo "xong", báo lại PM để dispatch
Reviewer + QA re-run live E2E (R5-03) trước khi coi S8 là `ready_for_release`.

---

## 2026-09-17 — BL-21: `GET /health` trả danh tính code đang chạy + `scripts/restart_server.sh`

Theo thiết kế Tech Lead `docs/Architecture.md` §5.4 (đọc file trước khi implement — không suy đoán
contract).

### Code

- `src/api/main.py`:
  - Thêm `_run_git()` (fail-soft wrapper `subprocess.run(["git", ...])`, timeout 5s, không bao giờ
    raise) — chạy đúng **một lần lúc import module**, kết quả cache vào `_GIT_COMMIT`,
    `_GIT_COMMIT_FULL`, `_GIT_DIRTY_AT_START`. Lỗi/không phải git repo → `"unknown"` /
    `git_dirty_at_start = None`, không chặn startup.
  - Thêm `_code_snapshot()` (walk `src/**/*.py` bỏ qua `__pycache__`, + `.env` nếu tồn tại — KHÔNG
    gồm `web/**`/`fonts/`/`docker/`/`.venv/` đúng theo §5.4.2) và `_fingerprint()` (sha256 8 ký tự
    đầu của các cặp `relpath\0mtime_ns:size` đã sort).
  - `_STARTED_AT`, `_STARTED_MONOTONIC`, `_PID`, `_CODE_SNAPSHOT_AT_START`,
    `_CODE_FINGERPRINT_AT_START` — cache module-level lúc import, không tính lại mỗi request.
  - Mở rộng handler `/health` hiện có (không tạo endpoint mới): trả thêm `version`, `pid`,
    `started_at`, `uptime_seconds`, `git_commit`, `git_commit_full`, `git_dirty_at_start`,
    `code_stale` (so `_fingerprint(_code_snapshot())` hiện tại với fingerprint lúc import),
    `code_changed_count`, `code_changed_files` (sort, cắt tối đa 10), `code_fingerprint_at_start`,
    `code_fingerprint_now`. Vẫn không chạm DB, không gọi `git` trong request path.
  - Sửa `from datetime import datetime, timezone` → `from datetime import UTC, datetime`
    (`ruff` UP017) khi thêm `_STARTED_AT`.
- `scripts/restart_server.sh` (mới, theo §5.4.4): trước khi kill, `GET /api/jobs?status=<active
  statuses>` (đúng `_ACTIVE_JOB_STATUSES` ở `src/api/routes/jobs.py:847-859`) — `total > 0` thì từ
  chối restart (in danh sách job, exit 1) trừ khi truyền `--force` (in cảnh báo rõ ràng đang force
  qua job active). Sau khi start lại: poll `/health` tối đa 30s, báo lỗi nếu `code_stale != false`
  ngay sau restart.

### Test

- `tests/test_health.py`: assert cũ `response.json() == {"status": "ok"}` đã đỏ sau khi mở rộng
  schema — sửa thành kiểm từng field + kiểu dữ liệu, và assert `code_stale=False`/`code_changed_*`
  rỗng trên process fresh chưa bị đụng file nào.
  - Thêm `test_health_reports_code_stale_after_file_touched`: dùng file giả trong `tmp_path` (không
    đụng file thật trong `src/`, tránh gây nhiễu fingerprint cho test khác/server thật đang chạy) —
    monkeypatch `_CODE_SNAPSHOT_AT_START`/`_CODE_FINGERPRINT_AT_START` và tạm thay `_code_snapshot`
    để mô phỏng 1 file đã đổi mtime sau lúc "import", assert `/health` trả `code_stale=True` và file
    đó có mặt trong `code_changed_files`, rồi khôi phục state module gốc ở `finally`.

`pytest` toàn repo: 921 passed. `ruff check` + `ruff format --check` sạch trên
`src/api/main.py`/`tests/test_health.py` (22 file khác trong repo lệch `ruff format` từ trước, không
liên quan tới thay đổi này, không đụng vào).

### Tự verify live (R5-03/R6-03 tinh thần — external-facing behavior, không phải external tool)

Trước khi restart đã kiểm `GET /api/jobs?status=...` (server thật, PID 15918) trả `total: 0` — không
có job `processing`/`translating` đang chạy, an toàn để restart. Chạy `scripts/restart_server.sh`
thật trên server production (port 8000):
- Restart thành công, `/health` sau restart trả đủ schema mới, `code_stale=false`.
- `touch src/api/main.py` (không sửa nội dung) trên server đang chạy → `GET /health` ngay lập tức
  trả `code_stale=true`, `code_changed_files=["src/api/main.py"]` — đúng cơ chế thiết kế để chặn
  chính 4 lần QA bị lọt code cũ ngày 2026-09-17.
- Restart lại lần 2 để đưa server về trạng thái sạch (`code_stale=false`) sau khi verify xong.

**Chưa qua Reviewer thật trong session này (R7-01)** — không tự báo "xong", báo lại PM để dispatch
Reviewer (checklist R5-04 áp dụng N/A vì §5.4 không mô tả contract tool bên thứ ba nào — toàn bộ là
stdlib + source code của chính repo, đã trích dẫn) trước khi coi BL-21 là `ready_for_release`.
