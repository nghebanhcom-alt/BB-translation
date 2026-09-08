# US-15 (Markdown parse-only) — Phản biện độc lập của Domain Expert (2026-09-08)

> **Vai trò**: Domain Expert (đội hình mở rộng, CLAUDE.md global). Phản biện thiết kế của Tech Lead ở
> `docs/Architecture.md` §6.15 (dòng 3719-3826), đối chiếu §6.8 (thiết kế nền), §6.20 (US-22 EPUB),
> `docs/PRD.md` US-15 + BR-PARSE-01..05, `docs/ba-analysis.md` §6.8.
>
> **Kỷ luật bằng chứng**: mọi khẳng định dưới đây thuộc 1 trong 3 loại — (a) đọc trực tiếp source
> code của repo (`file:line`), (b) dữ liệu MinerU thật đã có sẵn trên đĩa (`data/mineru-output/…`),
> (c) **tự chạy thật** trong session này (MinerU 3.4.5 đang chạy ở `localhost:8010`, spike
> `markdownify`/`bs4`/`ebooklib` trong venv scratch riêng, renderer CommonMark thật). Chỗ nào chưa
> verify được ghi rõ `[CHƯA VERIFY]`.
>
> File này KHÔNG sửa `Architecture.md` — PM tự gộp sau.

---

## 0. Tóm tắt kết luận

| # | Điểm PM yêu cầu phản biện | Kết luận | Mức độ |
|---|---|---|---|
| 1a | TOC-split (`babeldoc_toc_split_enabled`) và US-16 v2 (nén ảnh) có ảnh hưởng `parse_only`? | **ĐỒNG Ý với Tech Lead — KHÔNG ảnh hưởng.** Xác nhận bằng code, không suy đoán (§1.1). | — |
| 1b | Tech Lead có **bỏ sót** điểm nào trong 9 điểm S15? | **CÓ, 6 điểm bỏ sót**, trong đó 2 điểm là bug chéo tính năng nếu ship nguyên trạng: `_find_completed_duplicate` không lọc `job_type` (job parse xong sẽ bị coi là "bản dịch đã có"), và `retry_job` chặn `parse_only` + ép qua cost gate (mâu thuẫn trực tiếp với S15-9 "fail sớm khi MinerU chưa chạy" — fail sớm rồi không retry được). Chi tiết §1.2. | **BLOCKING** (2), quan trọng (4) |
| 1c | S15-6 (`parse_method="txt"` → `confidence is None`) | **BÁC BỎ — sai với dữ liệu thật.** Tự chạy `txt` mode qua chính `MinerURunner`: `confidence=0.9976`, 1004 span có `score`, 998 span `score==1.0`. §6.9.5 dòng 1665 cũng giả định sai điểm này. | **BLOCKING** (spec sai) |
| 2 | Nhánh EPUB dùng chung `EpubDocument` (§6.20.5) | **ĐỒNG Ý mục tiêu (1 loader), BÁC BỎ cách làm (1 projection).** `EpubUnit` là projection *đơn vị dịch* — đo trên EPUB thật của user: mất **10/10 ảnh**, 214 bold, 26 italic, 35 link; rule `extract()` bỏ `sup` **phá 6/6 phân số công thức "⅓ cup"** thành "/ cup". Vi phạm 2/4 AC của US-15. Đề xuất tách 2 projection trên cùng 1 loader (§2). Kèm **cảnh báo chéo cho US-22**: rule `sup` này cũng làm hỏng bản dịch EPUB. | **BLOCKING** cho nhánh EPUB; cảnh báo cho US-22 |
| 3 | "Giữ nguyên vị trí" trên tài liệu bánh thật | **Ảnh: ĐÚNG vị trí** (đồng ý). **Bảng: KHÔNG phải Markdown table syntax** như PRD AC — MinerU xuất HTML `<table>` (7/7 bảng, cả `ocr` lẫn `txt`), và **gộp cột** ("POUNDS OUNCES", Table 1.5 4 cột → 2) giống hệt ở 2 mode → lỗi table-structure model, không phải OCR. **List 2 cột bị đảo thứ tự** (1,2,17,3,18,19,4…) và CommonMark **đánh số lại** nên lỗi tàng hình khi render. `txt` mode **mất glyph `=`/`×`** trong công thức (ocr mode giữ đúng). Chi tiết + số liệu §3. | Sửa AC PRD + known limitations |
| 4 | Download ZIP (S15-3/S15-4) | **ĐỒNG Ý** sửa MIME hardcode (`download.py:61`). **BÁC BỎ** "zip lazily trong `download.py`": tạo artifact trong request handler nằm ngoài lineage §6.15.4 và ngoài guard S15-5, thư mục zip cache = thư mục bị nén. Đề xuất zip **eager** trong `run_parse_only()`, `output_path` trỏ `.zip` (§4). | Quan trọng |

Những gì **đồng ý nguyên trạng, không cần sửa**: S15-1 (rẽ theo `job_type` trước, hàm riêng), S15-5
(guard rỗng), S15-7 (lọc `job_type` thay vì bảng riêng), S15-9 (health check + UI nói trước), bảng
lineage §6.15.4 (chỉ cần thêm bước zip), quyết định giữ MinerU làm parser duy nhất cho cả
born-digital (§3.6).

---

## Nguồn xác thực của chính phản biện này

| # | Việc đã làm | Kết quả / vị trí |
|---|---|---|
| V-01 | Đọc `src/core/job_orchestrator.py` toàn bộ `run_job()` + `_build_ocr_bridge()` + `_translator_runner` | `:233-250`, `:252-630`, `:632-686` |
| V-02 | Đọc `src/api/routes/jobs.py` (`create_job`, `create_batch`, `retry_job`, `delete_job`, `_find_completed_duplicate`, `_ACTIVE_JOB_STATUSES`) | `:314-329`, `:424-521`, `:570-618`, `:648-711`, `:809-909` |
| V-03 | Đọc `src/api/routes/download.py` (62 dòng, toàn bộ) | `:20-62` |
| V-04 | Đọc `src/services/mineru_runner.py` (348 dòng, toàn bộ) | `:99-133`, `:260-288`, `:312-348` |
| V-05 | Đọc `web/index.html`, `web/history.html`, `web/js/app.js`, `web/js/history.js` phần status/download | xem §1.2.3 |
| V-06 | Phân tích Markdown + `middle.json` **thật** của MinerU (ocr mode) trên Figoni 1-25 trang | `data/mineru-output/8ea00c49-…/…/ocr/*.md` (660 dòng) + `*_middle.json` |
| V-07 | **Tự chạy live** `MinerURunner.parse_document(parse_method="txt")` trên **cùng file** Figoni 1-25 trang bản `pdf_digital` (`data/uploads/0f92a0d4-…-1-25.pdf`) qua MinerU 3.4.5 thật tại `localhost:8010` | 89.0 s, task `cdbd0988-…`, output tại scratchpad `mineru_txt_figoni25/` (document.md 54.243 ký tự, 23 ảnh, middle.json). Script ở Phụ lục A |
| V-08 | Spike `ebooklib 0.20 + beautifulsoup4 4.15.0 + markdownify` (venv scratch, Python 3.14.7 — đúng Python của `.venv`) trên EPUB thật `Baking with Sourdough - Sara Pitzer.epub`, `ops/xhtml/chapter01.html` | so sánh 2 projection, Phụ lục B |
| V-09 | Test `markdownify` trên đúng shape HTML table MinerU xuất (plain / `rowspan=1 colspan=1` / `colspan=2` thật) và `ol`/`ul` lồng nhau, `<img src="../images/…">` | §3.2, §2.3 |
| V-10 | Render CommonMark thật (`markdown-it-py`) đoạn list 2 cột bị đảo thứ tự | §3.3 |
| V-11 | `curl localhost:8010/health` | `{"status":"healthy","version":"3.4.5","max_concurrent_requests":1,…}` |

---

## 1. Điểm 1 — Chín điểm S15: có bỏ sót không?

### 1.1. TOC-split (Bug #7 Ca C) và US-16 v2 — XÁC NHẬN KHÔNG ẢNH HƯỞNG `parse_only`

Đồng ý với gợi ý của PM, nhưng đây là xác nhận từ code chứ không phải suy đoán:

- `babeldoc_toc_split_enabled` chỉ được đọc **một chỗ duy nhất**: `job_orchestrator.py:248`, bên
  trong property `_translator_runner` (`:233-250`) để dựng `BabeldocRunner`. Property này chỉ được
  gọi từ `_process_chunk()` (theo docstring `:234-236`). `run_parse_only()` theo S15-1 không đi qua
  `_process_chunk()` → không chạm.
- `compress_pdf_images` (US-16/US-16 v2) chỉ được gọi tại `job_orchestrator.py:573-574`, bên trong
  Step 8 của luồng translate, và bị gate `if self._settings.pdf_translate_engine == "babeldoc"`.
  Input của nó là `merged_path` — file PDF do `merge_chunk_pdfs()` ghi. `parse_only` không có
  `merged_path`, không có PDF output → không có gì để nén.
- MinerU `parse_document()` (`mineru_runner.py:99-133`) là HTTP call độc lập, không import gì từ
  `babeldoc_runner.py` / `image_compress.py`.

Kết luận: Tech Lead **không bỏ sót** ở điểm này; §6.15 không nhắc tới 2 thay đổi đó là đúng.
Đề nghị chỉ thêm 1 câu vào §6.15 ghi rõ "đã rà, không liên quan, vì X" để người đọc sau không phải
rà lại.

### 1.2. Sáu điểm Tech Lead THẬT SỰ bỏ sót

#### 1.2.1. [BLOCKING] `_find_completed_duplicate` không lọc `job_type` → bug chéo tính năng

`jobs.py:322-326`:
```python
statement = (
    select(Job)
    .where(Job.file_hash == file_hash, Job.status == "completed")
    .order_by(Job.completed_at.desc())
    .limit(1)
)
```
Hàm này được gọi ở `create_job` `:456-468` khi `job_type == "translate"` và `force=False`. Hiện tại
vô hại vì chưa có job `parse_only` nào `completed`. **Ngay khi US-15 ship**: user parse file X (job
parse_only → `completed`), sau đó bấm "Dịch" cùng file X → API trả `200 duplicate_found` trỏ tới
job parse_only, frontend hiện "đã dịch rồi, tải?" và link tải là ZIP Markdown. Đây đúng kiểu
"cùng một biến, hai ý nghĩa" mà §6.20.7 tự cảnh báo.

**Sửa**: thêm `Job.job_type == "translate"` vào `where`. (Có nên dedupe parse_only riêng không? Không
cần ở v1 — chi phí = 0, chạy lại vô hại.)

#### 1.2.2. [BLOCKING] `retry_job` chặn `parse_only` và ép qua cost gate — mâu thuẫn với S15-9

`jobs.py:585-586`:
```python
if job.job_type == "parse_only":
    raise HTTPException(status_code=400, detail="parse_only chua duoc ho tro, khong the retry")
```
và `:594-605` gọi `_resolve_provider_or_400` + `_enforce_cost_gate` vô điều kiện.

S15-9 thiết kế đúng: `run_parse_only()` gọi `MinerURunner.health()` trước, fail sớm nếu MinerU chưa
chạy. Kịch bản thực tế trên máy user (§6.9.8: `mineru-api` chạy bằng `uv tool`, không phải service
tự bật): user tạo job → fail "MinerU chưa chạy" → user bật MinerU → bấm "Tiếp tục" → **400**. Job
chết vĩnh viễn, phải upload lại. Frontend `index.html:139-140` hiện nút retry cho mọi job `failed`,
nhãn "Tiếp tục dịch" — sai nghĩa cho parse.

**Sửa**: bỏ `:585-586`; với `parse_only` bỏ qua `_resolve_provider_or_400` + `_enforce_cost_gate`
(giống `create_job:475-485` đã làm), đi thẳng `status="queued"` + `_schedule_background`.

#### 1.2.3. `create_batch` cũng gọi `_mark_parse_only_unsupported` — S15-2 chỉ nêu `create_job`

`jobs.py:889-891` (đánh fail từng job) và `:902-907` (đánh cả batch `failed`,
`failed_files = len(parse_only_jobs)`). S15-2 viết "Bỏ `_mark_parse_only_unsupported()`
(`src/api/routes/jobs.py`)" — nếu Dev chỉ sửa `create_job` (nơi duy nhất S15-2 mô tả luồng thay
thế), batch parse_only vẫn chết. Cần ghi rõ cả 2 call site + `:899-907` phải schedule
`_run_batch_background` cho cả 2 `job_type`.

Ghi chú vận hành đi kèm: MinerU thật báo `max_concurrent_requests: 1` (V-11). Batch 3 file
(`max_concurrent_files=3`) sẽ submit 3 task, MinerU xếp hàng server-side. `_poll_until_done`
(`mineru_runner.py:181-226`) đếm `elapsed` **từ lúc submit, tính cả thời gian nằm trong hàng đợi**
→ file thứ 3 của batch có thể hết `mineru_task_timeout_seconds=3600` khi còn chưa được xử lý.
Với 89 s/25 trang đo được (V-07) ≈ 3,6 s/trang, 3 cuốn 400 trang xếp hàng = cuốn cuối chờ ~48 phút
trước khi bắt đầu. Đề xuất: chỉ đếm timeout từ khi `status` chuyển sang trạng thái đang xử lý
(`[CHƯA VERIFY]` tên status thật trước `completed` — Dev đọc `_poll_until_done` payload thật để lấy),
hoặc ghi known limitation "batch parse_only nên ≤ 2 cuốn dày".

#### 1.2.4. Không có status trung gian cho "đang parse" — rủi ro DELETE khi MinerU đang ghi

§6.15 không nói job ở status nào trong lúc MinerU chạy (có thể tới 25 phút). Danh sách status bị
hardcode ở **6 chỗ**:

| Chỗ | Nội dung |
|---|---|
| `jobs.py:648-655` `_ACTIVE_JOB_STATUSES` | guard cho `DELETE /api/jobs/{id}` (`:672-679`); nếu status mới không nằm trong đây, user xoá được job đang chạy → `:708-709` `rmtree(data/processing/{job_id})` **trong lúc `_write_images` đang ghi** |
| `jobs.py:631` `cancel_job` | chỉ chặn `completed/failed/cancelled` — OK |
| `web/js/app.js:16-25` `RESTORABLE_STATUSES` | job không nằm trong đây → **biến mất khỏi UI sau F5** |
| `web/js/app.js:32-38` `CANCELLABLE_STATUSES` | nút "Dừng" |
| `web/index.html:110` | thanh progress chỉ hiện với 5 status liệt kê cứng |
| `web/history.html:23-30` + `history.js:15-27` | filter + badge màu |

Hai lựa chọn Dev có thể tự ý chọn nếu spec im lặng: (a) dùng `"translating"` → hiện "Đang dịch" cho
job không dịch, và `current_chunk/total_chunks` hiện `-/-`; (b) đặt status mới `"parsing"` mà không
sửa 6 chỗ trên → rủi ro rmtree ở trên. **Đề xuất**: chốt status `"parsing"`, và liệt kê 6 chỗ trên
vào S15 như checklist bắt buộc (Reviewer grep `"translating"` để kiểm).

#### 1.2.5. Cancel không có tác dụng với `parse_only`

`cancel_requested` chỉ được đọc sau mỗi chunk (Step 7). `parse_only` = 1 lời gọi MinerU duy nhất
tới 3600 s → nút "Dừng" (`index.html:122`) không làm gì cho tới khi MinerU xong. Tối thiểu phải ghi
known limitation. Tốt hơn: `_poll_until_done` nhận callback `should_cancel` (đọc lại
`job.cancel_requested` mỗi vòng poll) → app ngừng chờ và đánh `cancelled`; MinerU vẫn chạy nốt
server-side vì `[CHƯA VERIFY]` MinerU có endpoint huỷ task hay không (§6.9.2 không liệt kê) — chấp
nhận được vì compute local, chi phí $0.

#### 1.2.6. Ba trường "finalize" chưa được spec, và probe Bug #6 nên nói rõ là KHÔNG chạy

- `completed_at`: `download.py:52-53` dùng nó để tạo hậu tố timestamp tên file. Luồng translate set
  ở `job_orchestrator.py:607`. S15 không nhắc → nếu Dev quên, tên file tải về mất timestamp (rơi
  vào fallback `updated_at`, không sai nhưng lệch hành vi so với PDF).
- `cost_source` / `actual_cost`: event `job_completed` (`:613-621`) gửi `cost_source`; frontend rẽ
  theo giá trị này để hiện cảnh báo "ước tính, có thể sai lệch" (§6.20.8 ghi nhận). Đề xuất
  `actual_cost=0.0`, `cost_source="metered"` (0 là số đo thật: không gọi LLM) — tránh cảnh báo ước
  tính vô nghĩa. PM chốt.
- `job.model`: `create_job:500` ghi `model=provider_name` (= DeepSeek mặc định) cho cả parse_only →
  tab Lịch sử hiện "deepseek" cho job không dùng LLM. Giữ nguyên ở backend (đụng vào sẽ vướng
  `_resolve_provider_or_400` ở retry), chỉ ẩn cột model trên UI khi `job_type == "parse_only"`.
- `_run_rotated_text_probe` (Bug #6 Phase 1, `job_orchestrator.py:680`): **không cần** cho
  parse_only — theo `mineru_det_probe.py:11-17`, chữ xoay VẪN được nhận dạng, chỉ mất góc; Markdown
  không có khái niệm góc. Tech Lead không nhắc, nhưng vì `run_parse_only()` cho `pdf_scan` sẽ chép
  lại 1 phần `_build_ocr_bridge()` (`:658-665`: gọi MinerU + ghi confidence + warning), R6-01 đòi
  ghi tường minh **bước nào của `_build_ocr_bridge` được tái dùng, bước nào không** (không probe,
  không `build_searchable_pdf`). Đề xuất tách `:658-665` thành helper `_run_mineru_and_record_quality()`
  dùng chung 2 nhánh — 1 định nghĩa duy nhất cho "gọi OCR", đúng tinh thần S15-8.

### 1.3. [BLOCKING] S15-6 sai với dữ liệu thật: `txt` mode KHÔNG trả `confidence is None`

S15-6 (`Architecture.md:3783-3784`): *"`parse_method="txt"` (born-digital) → MinerU không chạy OCR
→ `quality.confidence is None` → đúng theo §6.9.5, ghi NULL, không cảnh báo."* §6.9.5 dòng 1665 cũng
viết *"`confidence is None` nghĩa là không có span nào qua OCR (file thực ra có text layer)"*.

Tôi chạy thật (V-07), cùng file Figoni 1-25 trang, bản `pdf_digital`, `parse_method="txt"`:

```
"confidence": 0.997628187250996,
"ocr_span_count": 1004,
"quality_source": "middle_json_span_scores"
```

Phân bố `score` trong `middle.json` (Phụ lục A): **1002 span `text` + 2 `inline_equation` đều có key
`score`**; 998 span `score == 1.0`, 6 span `< 1.0` (0.993, 0.993, 0.606, 0.542, 0.485, 0.0). Tức là
MinerU 3.4.5 pipeline gán `score: 1.0` cho span lấy từ text layer, và vẫn OCR vài vùng ảnh (6 span).
`_compute_quality()` (`mineru_runner.py:312-348`) gom mọi span có key `score` → count ≠ 0 → không
bao giờ `None` ở txt mode. Giá trị 0.9976 là trung bình bị pha loãng bởi 998 số 1.0 — **không phải
tín hiệu chất lượng OCR**, nhưng sẽ được ghi vào `jobs.ocr_confidence`, hiện lên `JobDetail`
(`jobs.py:240`) như thể file đã được OCR.

§6.9 chỉ được verify ở `ocr` mode (mọi thư mục `data/mineru-output/*/…/ocr/`); `txt` mode chưa từng
có dữ liệu thật trước run này → đây đúng lớp lỗi Protocol 5 (contract suy ra, chưa verify ở mode
mới).

**Sửa S15-6**: trong `run_parse_only()`, rẽ theo `file_type` chứ không theo giá trị runner trả về:
`pdf_scan` → ghi `ocr_confidence`/`ocr_dropped_spans` + `_emit_ocr_warning_if_low()`;
`pdf_digital` → **ép `ocr_confidence = None`, `ocr_dropped_spans = None`, không gọi warning**, bất kể
`quality.confidence` là gì. Đồng thời sửa câu ở §6.9.5:1665 thành "…`None` chỉ khi không span nào có
key `score` — ở `parse_method=txt` MinerU 3.4.5 gán `score=1.0` cho span text layer nên giá trị
KHÔNG `None` và KHÔNG có ý nghĩa OCR". Test: fixture golden từ run này (Phụ lục A) — assert
`run_parse_only` ghi NULL dù runner trả 0.9976.

---

## 2. Điểm 2 — `EpubDocument` dùng chung cho cả dịch lẫn parse-only?

### 2.1. Tech Lead đúng ở mục tiêu, sai ở phương tiện

Lập luận Protocol 6 của S15-8 ("2 parser EPUB cho cùng 1 file = cấu hình sinh bug 2 nhánh lệch
nhau") **đúng và tôi ủng hộ**. Nhưng S15-8 áp dụng nó vào **sai tầng**: thứ phải dùng chung là
*loader* (mở zip, DRM check, thứ tự spine, XHTML → soup), không phải *projection*. `EpubUnit`
(§6.20.5:4355-4361) được thiết kế có chủ đích là **danh sách đơn vị DỊCH**: chỉ text đã strip, chỉ
các tag có chữ, bỏ `sup/code/pre`, bỏ unit toàn số/URL/ISBN, chỉ lấy node ngoài cùng. Mọi quy tắc
đó đều hợp lý cho dịch và đều **phá** mục tiêu "giữ nguyên" của parse-only.

### 2.2. Số đo trên EPUB thật của user (V-08, `ops/xhtml/chapter01.html` — 97,2% nội dung cuốn sách)

| Thành phần trong XHTML nguồn | Số lượng | (A) `EpubUnit` → `units_to_markdown()` | (B) full-DOM `markdownify` |
|---|---|---|---|
| `<img>` | **10** | **0** | 10 |
| `<h2>` / `<h3>` | 2 / 34 | 2 / 34 | 2 / 34 |
| `<strong>` (tên nguyên liệu + định lượng in đậm) | **214** | 0 | 214 |
| `<em>` | 26 | 0 | 26 |
| `<a>` | 35 | 0 | 2 (còn lại là anchor nội bộ không href → text) |
| `<sup>…</sup>/<sub>…</sub>` | 6 | **bị `extract()`** | giữ dạng `1/3` |
| `<ol>`/`<ul>`/`<table>` | 0 / 0 / 0 | — | — |

Với AC US-15 (`PRD.md:179-184`):
- AC dòng 182 *"ảnh được extract ra thư mục riêng, Markdown chèn link ảnh đúng vị trí gốc"* —
  projection (A) **mất 100% ảnh** (ảnh không phải đơn vị dịch nên không bao giờ là `EpubUnit`).
  Với sách dạy làm bánh, BA đã nhận định ảnh-gắn-bước chính là ý user (ba-analysis §6.8.2 (ii)).
- AC dòng 181 *"đúng loại list"* — `EpubUnit.tag == "li"` không biết cha là `ol` hay `ul`; S15-8 map
  mọi `li` → `- ` → numbered steps thành bullet. File mẫu không có list, nhưng cookbook EPUB nói
  chung dùng `<ol>` cho bước làm.
- AC dòng 180 *"giữ nguyên cấu trúc bảng"* — `td`/`th` là unit phẳng, không có ranh giới `tr`/`table`
  → "map `td/th` → hàng bảng" (S15-8) không dựng lại được cột.
- Rule *"bỏ unit toàn chữ số"* (§6.20.5:4389) — với bảng công thức kiểu Figoni Table 1.4, mọi ô
  `3000`, `60%`, `6` là **unit toàn số → bị bỏ** → bảng chỉ còn cột tên nguyên liệu. (File mẫu không
  có bảng nên chưa đo được; đây là suy luận trực tiếp từ rule, không phải phỏng đoán về tool.)

### 2.3. [CẢNH BÁO CHÉO CHO US-22] Rule `extract()` bỏ `sup` phá phân số công thức

Trong `chapter01.html`, **6/6 `<sup>`** là **tử số phân số**, **0/6** là footnote marker (Phụ lục B):

```html
<p class="indent2"><strong><sup>1</sup>/<sub>3</sub> cup soy grits</strong></p>
<p class="indent2"><strong>1<sup>1</sup>/<sub>3</sub> cups unbleached white flour</strong></p>
```

Cùng file dùng 107 ký tự phân số unicode (¼ ½ ¾ …) ở chỗ khác, nhưng ⅓ được dựng bằng
`<sup>/<sub>` — chuẩn typesetting phổ biến vì U+2153 không có trong nhiều font. Với rule §6.20.5,
text của unit trở thành `/ cup soy grits` và `1/ cups unbleached white flour` — **định lượng nguyên
liệu bị xoá âm thầm**, rồi được gửi đi dịch. Đây không phải vấn đề của riêng US-15: **US-22 sẽ dịch
sai công thức** ở đúng những đoạn này, và guard BR-EPUB-05 (đếm ký tự, % unit đổi) không bắt được.

Đề xuất cho §6.20.5: **không `extract()` `sup`/`sub`**; thay bằng flatten thành text
(`<sup>1</sup>/<sub>3</sub>` → `1/3`). Nếu thật sự cần bỏ footnote marker, chỉ bỏ `sup` khi (i) nội
dung là số/ký hiệu ngắn **và** (ii) không đứng cạnh `/` + `<sub>`. `code`/`pre`: giữ nguyên rule bỏ
cho *dịch*, nhưng parse-only phải giữ.

### 2.4. Đề xuất kiến trúc thay S15-8

```
src/services/epub_document.py
  EpubDocument.load(path)                      # CHUNG: zip, DRM check, spine order, soup mỗi doc
    .spine_documents -> list[tuple[href, BeautifulSoup]]   # MỚI, public, thứ tự spine
    .units -> list[EpubUnit]                    # projection DỊCH (§6.20.5, sửa rule sup)
    .write_translated(...)                      # §6.20.5, không đổi
    .to_markdown(images_out_dir) -> str         # projection PARSE-ONLY (US-15), MỚI
```

`to_markdown()`: duyệt `spine_documents` theo đúng thứ tự spine, mỗi doc → `markdownify(soup,
heading_style="ATX")`, nối bằng `\n\n---\n\n` (ranh giới tài liệu), rewrite mọi `src` ảnh từ đường
dẫn trong zip (`../images/f0003-01.jpg`) thành `images/f0003-01.jpg` và copy bytes từ zip ra
`images_out_dir`. Hai projection đọc **cùng một** `spine_documents` → Protocol 6 thoả ở tầng loader;
test R6-02: `len(doc.units)` và số heading trong `to_markdown()` phải cùng đếm được từ cùng soup.

Về dependency `markdownify` (Tech Lead muốn tránh): tôi đã test hành vi thật (V-09) —
`ol` → `1. 2. 3.`, `ul` lồng → `   * `, `<img>` → `![alt](src)`, `<figure>/<figcaption>` → ảnh +
dòng caption, table → pipe table (mất `colspan`, xem §3.2 — nhưng EPUB hiếm khi có merged cell, và
với EPUB ta *có thể* giữ HTML table nếu muốn bằng `markdownify(..., convert=[...])`). Thư viện thuần
Python, chỉ phụ thuộc `bs4` (đã cài cho US-22). Tự viết walker ~100 dòng cũng được, nhưng phải
tự test lại đúng những case trên — không rẻ hơn.

### 2.5. Thứ tự increment

Đồng ý với S15-8 "hệ quả thứ tự làm việc": nếu US-15 ra trước US-22, `parse_only + epub` → **400 rõ
ràng tại `create_job`/`create_batch`** (không tạo Job row). PDF born-digital + scan làm ngay.

---

## 3. Điểm 3 — "Giữ nguyên vị trí" trên tài liệu bánh thật

Dữ liệu: Figoni *How Baking Works* 25 trang đầu, **cùng file** ở 2 mode — `ocr` (đã có trên đĩa từ
job trước, lúc file còn bị phân loại `pdf_scan` trước fix `file_router.py:50-69`) và `txt` (tôi chạy
live, V-07). So sánh cùng file, cùng MinerU 3.4.5 → tách được "lỗi do OCR" khỏi "lỗi do layout/table
model".

### 3.1. Ảnh — ĐÚNG VỊ TRÍ, đồng ý với thiết kế

- Markdown: `![](images/<sha256>.jpg)` — 16 tham chiếu, **16/16 có file trên đĩa** ở cả 2 mode
  (`image_refs_missing_on_disk: []`). Đường dẫn relative `images/` khớp BR-PARSE-03 và khớp cách
  `_write_images` (`mineru_runner.py:286-287`, `Path(name).name`) đặt tên → không cần rewrite.
- Vị trí: ảnh nằm **giữa** đoạn văn và heading kế tiếp đúng như trang gốc (ocr-mode md dòng 289-293:
  đoạn văn → `![](…d9e4e124….jpg)` → `## A NOTE ABOUT TEMPERATURE…`; dòng 301-305 tương tự). Không
  dồn xuống cuối.
- 23 file ảnh được ghi nhưng chỉ 16 được tham chiếu — 7 file mồ côi là **crop của 7 bảng** (MinerU
  lưu ảnh bảng dù đã xuất HTML; `middle.json` có đúng 7 block `table`). Vô hại, ZIP sẽ chứa chúng;
  ghi vào spec để QA không báo bug "ảnh thừa".
- Sửa §6.8:1474-1481: ví dụ tên `page_003_img_01.png` **không đúng thực tế** (tên là SHA-256 + `.jpg`,
  không có số trang). §6.15.2 nói cấu trúc này "còn dùng được nguyên trạng" — cây thư mục đúng,
  ví dụ tên file sai; QA không được assert theo tên đó.
- Alt text luôn rỗng `![]()` — MinerU không sinh caption vào alt; `image_caption` (1 block trong
  middle.json) được đặt thành dòng text kế ảnh. Chấp nhận.

### 3.2. Bảng — KHÔNG phải Markdown table syntax, và cột bị gộp ở CẢ HAI mode

**(a) Định dạng.** 7/7 bảng ở cả `ocr` lẫn `txt` là **HTML `<table>` một dòng**, 0 dòng pipe-table
(`pipe_table_rows: 0`). Ví dụ dòng 569 (ocr) có thuộc tính `rowspan=1 colspan=1` — MinerU xuất HTML
chính vì cần merged cell. PRD AC `:180` viết *"Markdown output giữ nguyên cấu trúc bảng (Markdown
table syntax)"* → **sai với thực tế MinerU**, QA sẽ fail AC hoặc Dev sẽ viết converter.

Tôi test `markdownify` (V-09) trên đúng shape MinerU: bảng thường → pipe table nhưng **thêm 1 hàng
header rỗng** (MinerU dùng `<td>` cho header, không `<th>`); bảng có `colspan=2` thật → **mất span**
(`| Header spanning 2 | |`). Pipe table không biểu diễn được merged cell theo spec GFM.

**Đề xuất**: **giữ nguyên HTML `<table>`** trong `document.md` (GFM và mọi renderer phổ biến đều
render HTML table inline). Sửa AC `:180` thành *"giữ nguyên cấu trúc bảng (dạng HTML table nhúng
trong Markdown, chuẩn GFM; giữ được merged cell)"*. Không convert ở v1.

**(b) Chất lượng cấu trúc.** Cùng bảng, cùng kết quả sai ở 2 mode:

| Bảng | Nguồn (PDF) | MinerU `ocr` | MinerU `txt` |
|---|---|---|---|
| Table 1.4 header | INGREDIENT · POUNDS · OUNCES · GRAMS · BAKER'S % | `INGREDIENT` · **`POUNDS OUNCES`** · `GRAMS` · `BAKER'S %` (4 cột, gộp 2) | **giống hệt** (dòng 603) |
| Table 1.4 hàng Water | 5 · 10.0 · 2800 · 56% | `Water` · **`5 10.0`** · `2800` · `56%` | giống hệt |
| Table 1.5 | 4 cột | **2 cột**: `INGREDIENT POUNDS` · `GRAMS BAKER'S %`; ô `Dates 6` · `3000 100%` | giống hệt (dòng 608) |

Kết luận: đây là **giới hạn của table-structure model** MinerU (SLANet/RapidTable qua
`table_enable=true`) trên layout bảng công thức có cột hẹp — **không phải lỗi OCR**, born-digital
không cứu được. AC-23.1 của BA (ba-analysis `:863-868`: *"bảng ở dạng Markdown table đúng số cột"*)
**sẽ FAIL trên Figoni Table 1.5**. PM phải chốt: ghi known limitation (đề xuất), hoặc mở spike
riêng dùng PyMuPDF `page.find_tables()` làm nguồn bảng cho born-digital (ngoài scope US-15; là
parser thứ 2 → cần cân nhắc Protocol 6).

### 3.3. List 2 cột bị đảo thứ tự — và lỗi trở nên TÀNG HÌNH khi render

Trang "EQUIPMENT AND SMALLWARES" (2 cột, 31 mục). Cả 2 mode xuất thứ tự
`1, 2, 17, 3, 18, 19, 4, 20, 21, 5, 22, 6, 23, 7, 8, 24, 25, 9, 26, 10, 27, 11, 28, 12, 29, 13, 14, 30, 31…`
(ocr md dòng 339-395; txt md giống hệt) — reading-order của layout model trộn 2 cột theo hàng
ngang. Tệ hơn: mỗi mục là 1 paragraph `N. …` cách nhau dòng trống → CommonMark coi là 1 ordered list;
tôi render thật bằng `markdown-it` (V-10): `1.` `2.` `17.` `3.` → `<ol>` 4 `<li>` **đánh số lại
1-2-3-4**, số 17 gốc biến mất. Người xem bản render thấy danh sách "đẹp", không biết thứ tự sai.

Đề xuất: known limitation (*"list/bảng dàn 2 cột có thể bị trộn thứ tự theo hàng"*), và QA phải
kiểm **Markdown thô**, không chỉ bản render (đúng tinh thần R6-03 "mở file ra xem chữ thật").

### 3.4. Heading — cấp có, nhưng có 3 lỗi nhỏ, và `txt` mode MẤT GLYPH ký hiệu

- `middle.json` `title` block có `level` 1 và 2 (6 + 43) ở cả 2 mode → `#`/`##` đúng cấp. Không có
  `###` trong 25 trang này (sách chỉ có 2 cấp ở phần đầu) — QA cần trang có 3 cấp thật để kiểm AC
  `:181`.
- Mất khoảng trắng khi nối dòng: `## CHAPTER 4SENSORY PROPERTIESOF FOOD 49` (dòng 103, cả 2 mode).
- Sidebar/formula bị nhận thành heading: `## HELPFUL HINT` (x2), `## Smallest quantity to be weighed
  = scale readability × 10` (dòng 505).
- **`txt` mode mất glyph**: cùng dòng 505, `ocr` → `= scale readability × 10` (đúng), `txt` →
  `  scale readability - 10` — dấu `=` thành trống, **`×` thành `-`** (nhân → trừ). Nguồn gốc là font
  ký hiệu không map Unicode trong text layer; OCR đọc từ pixel nên đúng. Không có nghĩa `txt` kém
  hơn nói chung (chữ thường `txt` sạch hơn, và không có rủi ro nhận nhầm chữ), nhưng đủ để ghi known
  limitation *"công thức/ký hiệu toán trong PDF born-digital có thể sai glyph; nếu tài liệu nhiều công
  thức, cân nhắc ép `ocr`"*. Gợi ý mở rộng nhỏ (không bắt buộc v1): cho `parse_only` nhận tham số
  `parse_method` override (`auto`/`txt`/`ocr`, MinerU hỗ trợ cả 3 theo §6.9.2:1531) — mapping mặc định
  theo `file_type` giữ nguyên.

### 3.5. Footnote / header / footer — ĐÚNG như mong muốn

`middle.json`: `discarded_blocks` = `header` 30, `footer` 4, `page_number` 16 → **bị loại khỏi
`md_content`** (đúng: không muốn "JOHN WILEY & SONS" lặp mỗi trang trong Markdown). `table_footnote`
(1 block) được giữ ngay dưới bảng: dòng 605 *"Note: Metric measures in this table…"* nằm đúng sau
Table 1.4. Không có edge case nào hở ở 25 trang này.

### 3.6. Có nên bỏ MinerU cho born-digital? — KHÔNG, đồng ý với Tech Lead (YA-7.3/S15-9)

Phương án thay thế duy nhất đáng cân nhắc là PyMuPDF (`pymupdf4llm`/`find_tables`) — nhẹ, không cần
service. Nhưng: (i) heading level ở PyMuPDF là heuristic cỡ font, không có layout model; (ii) là
**parser thứ hai** cho cùng loại input → đúng thứ Protocol 6 cấm; (iii) MinerU đã chạy sẵn trên máy
user (V-11) và đã verify sống. Giữ MinerU. Đo thật: 89 s/25 trang → ước ~25 phút cho sách 415 trang,
sát `mineru_task_timeout_seconds=3600` với Le Cordon Bleu 418 trang/277 MB → UI "thời gian ước tính"
(BR-PARSE-05) nên dùng hệ số ~3,6 s/trang này, và timeout cho `parse_only` nên tính theo số trang
thay vì hằng 3600.

---

## 4. Điểm 4 — Download ZIP

### 4.1. Đồng ý

- `download.py:61` hardcode `media_type="application/pdf"` — đúng như P-05. Suy từ suffix là đúng
  hướng: `{".pdf": "application/pdf", ".zip": "application/zip", ".epub": "application/epub+zip"}`
  (US-22 cũng cần).
- Tên `{stem}_markdown_{timestamp}.zip` nhất quán với pattern `_vi`/`_bilingual` + timestamp `:52-60`.
- `DELETE /api/jobs/{id}` (`jobs.py:708-709`) xoá theo thư mục `data/outputs/{job_id}` → không cần
  học gì mới, đúng như S15-4 lập luận.

### 4.2. Bác bỏ "ZIP tạo lazily lần tải đầu trong `download.py`" (S15-3)

Ba lý do, theo thứ tự nặng:

1. **Nằm ngoài lineage và ngoài guard.** Bảng §6.15.4 có 4 bước, bước 4 "ZIP dựng từ
   `Path(job.output_path).parent`" — nhưng không bước nào *tạo* zip; nó được tạo trong request
   handler, sau khi job đã `completed`, sau guard S15-5. Nếu zip lỗi (thư mục `images/` bị xoá tay,
   quyền ghi, đĩa đầy) thì job vẫn "completed" mà không tải được — đúng shape "báo xong, output không
   dùng được" của Bug #5, chỉ chuyển từ bước dịch sang bước tải.
2. **Zip cache nằm trong chính thư mục bị nén.** `Path(job.output_path).parent` =
   `data/outputs/{job_id}/`; S15-3 đặt cache tại `data/outputs/{job_id}/parse_result.zip` → lần dựng
   lại (cache bị xoá dở, hoặc Dev đổi điều kiện cache) sẽ nén cả `parse_result.zip` vào chính nó.
3. **Crash giữa chừng để lại zip hỏng được serve mãi** (kiểm `exists()` → trả file dở).

### 4.3. Đề xuất thay S15-3/S15-4

Trong `run_parse_only()`, sau guard S15-5, thêm bước **"Đóng gói"** (eager):

```
data/outputs/{job_id}/
├── document.md
├── images/…
└── parse_result.zip      # zipfile.ZipFile(..., ZIP_DEFLATED), DANH SÁCH FILE TƯỜNG MINH:
                          #   document.md + images/* (không walk thư mục → không tự nén mình)
```

- `job.output_path = ".../parse_result.zip"` (đổi S15-4: trỏ `.zip`, không phải `.md`). Lý do:
  `download.py` chỉ cần đổi MIME + tên file, không cần biết `parse_only`; consumer nào cần `.md` sau
  này (preview) derive `Path(output_path).parent / "document.md"`.
- Bước lineage mới **(5) Guard zip**: mở lại **chính file zip vừa ghi**, `testzip() is None`,
  `"document.md" in namelist()`, số entry `images/` == số file trong thư mục `images/`. Fail → job
  `failed`, không `completed`.
- Ghi zip ra tên tạm rồi `os.replace()` → không bao giờ có zip dở mang tên thật.
- UI: `index.html:134` "Tải bản VI" và `history.html:59` "Tải VI" phải rẽ theo `job_type` → "Tải
  Markdown (.zip)"; ẩn link song ngữ.

---

## 5. Gate release bổ sung (Protocol 5 R5-03 + Protocol 6 R6-03)

1. **R5-03 `txt` mode**: đã có 1 lần live trong phản biện này (V-07) — QA vẫn phải tự chạy lại qua
   `run_parse_only()` thật (không qua script của tôi).
2. **R6-03 E2E**: tải ZIP về, giải nén, mở `document.md` → có chữ thật (**không chỉ `status`**), đếm
   `![](images/…)` và mở ≥ 1 ảnh thật; kiểm 1 bảng HTML và **1 list 2 cột trong Markdown thô**.
3. **Golden fixture (Protocol 5 #3)**: `tests/test_mineru_runner.py` hiện có `md_content` nhưng không
   trỏ tới `tests/fixtures/mineru/` (grep `fixtures/mineru|golden` → 0) → mock viết tay. Dev phải
   capture từ run thật: đề xuất `tests/fixtures/mineru/parse_only_txt_figoni25/` gồm `document.md`,
   `summary.json`, `middle.json` (đã có sẵn ở scratchpad của session này — Phụ lục A, hoặc chạy lại
   script). Test S15-6 phải dùng `middle.json` này (998 span `score=1.0`) để chứng minh
   `ocr_confidence` bị ép `None` cho `pdf_digital`.
4. **Regression chéo**: test `create_job(translate)` trên file đã có job `parse_only completed` →
   **202 + job mới**, không phải `200 duplicate_found` (§1.2.1).

---

## 6. Final Decision (đề xuất — PM/Tech Lead chốt)

| ID | Thay đổi so với §6.15 | Thay cho |
|---|---|---|
| FD-1 | S15-2 mở rộng: bỏ `_mark_parse_only_unsupported` ở **cả** `create_job:509-513` **và** `create_batch:889-907`; `retry_job` bỏ `:585-586` và skip provider/cost-gate cho `parse_only` | S15-2 |
| FD-2 | `_find_completed_duplicate` thêm `Job.job_type == "translate"` | (bỏ sót) |
| FD-3 | Status mới `"parsing"`; cập nhật `jobs.py:648-655`, `app.js:16-25`, `app.js:32-38`, `index.html:110`, `history.html:23-30`, `history.js:15-27` (checklist cho Reviewer) | (bỏ sót) |
| FD-4 | ZIP tạo **eager** trong `run_parse_only()` bằng danh sách file tường minh; `output_path` = `.zip`; thêm bước lineage (5) guard zip; `download.py` chỉ đổi MIME theo suffix + tên `_markdown_` | S15-3, S15-4 |
| FD-5 | `ocr_confidence`/`ocr_dropped_spans` rẽ theo `file_type`, **ép `None` cho `pdf_digital`** bất kể runner trả gì; sửa câu §6.9.5:1665; không chạy `_run_rotated_text_probe`; tách helper `_run_mineru_and_record_quality()` dùng chung với `_build_ocr_bridge:658-665` | S15-6 |
| FD-6 | `EpubDocument` giữ **1 loader** (`load`, `spine_documents`), **2 projection**: `units` (dịch) + `to_markdown()` (parse-only, `markdownify` full-DOM, copy ảnh từ zip, rewrite `src`). **Sửa §6.20.5**: không `extract()` `sup`/`sub` (flatten thành text) — bug tiềm ẩn của US-22 | S15-8 + §6.20.5 |
| FD-7 | PRD: AC `:180` đổi "Markdown table syntax" → "HTML table nhúng, chuẩn GFM"; thêm known limitations: cột hẹp bị gộp, list/bảng 2 cột trộn thứ tự (CommonMark đánh số lại), glyph ký hiệu ở `txt` mode, 7 ảnh crop bảng mồ côi; sửa ví dụ tên ảnh §6.8 | PRD + §6.8 |
| FD-8 | Cancel: `_poll_until_done` nhận `should_cancel`; known limitation MinerU vẫn chạy nốt server-side `[CHƯA VERIFY]` có API huỷ | (bỏ sót) |
| FD-9 | Set `completed_at`; `actual_cost=0.0`, `cost_source="metered"` (PM chốt); UI ẩn cột model cho parse job; timeout MinerU cho `parse_only` tính theo số trang (~3,6 s/trang đo thật) và không đếm thời gian nằm hàng đợi `[CHƯA VERIFY tên status hàng đợi]` | (bỏ sót) |

Giữ nguyên: S15-1, S15-5, S15-7, S15-9, §6.15.4 (thêm bước 5), kết luận TOC-split/US-16 không liên
quan, MinerU là parser duy nhất cho PDF.

---

## Phụ lục A — Live run `parse_method="txt"` (V-07)

Script (chạy bằng `.venv/bin/python` của project, gọi đúng `src/services/mineru_runner.py`):

```python
runner = MinerURunner("http://localhost:8010", task_timeout_seconds=1800)
result = await runner.parse_document(PDF, OUT, parse_method="txt", lang="en")
```

Kết quả (`summary.json`):
```json
{"parse_method": "txt", "elapsed_s": 89.0, "task_id": "cdbd0988-1182-456d-bf23-791e03490bc6",
 "markdown_chars": 54243, "markdown_lines": 660, "images_written": 23, "image_refs_in_md": 16,
 "html_tables": 7, "pipe_table_rows": 0, "h1": 6, "h2": 43, "h3": 0,
 "confidence": 0.997628187250996, "ocr_span_count": 1004,
 "quality_source": "middle_json_span_scores", "image_refs_missing_on_disk": []}
```

Phân bố `score` trong `middle.json` (txt mode):
```
spans WITH score by type: {'text': 1002, 'inline_equation': 2}   # image/table span: không có score
score==1.0: 998   score<1.0: 6   min: 0.0
buckets: [(1.0, 998), (0.993, 2), (0.542, 1), (0.485, 1), (0.606, 1), (0.0, 1)]
```

Đối chiếu ocr mode cùng file (đã có trên đĩa): `title` level `{1: 6, 2: 43}`, block
`{title 49, text 197, image 16, table 7, image_caption 1, table_footnote 1}`, discarded
`{header 30, footer 4, page_number 16}`.

Vị trí output: `/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/bb6eecef-c929-4946-84d5-375bde5e3612/scratchpad/mineru_txt_figoni25/` (scratchpad session — copy vào `tests/fixtures/mineru/` nếu muốn dùng làm golden; nếu không, Dev chạy lại script ở trên).

## Phụ lục B — Spike EPUB projection (V-08)

Venv scratch: `uv venv --python 3.14` → Python 3.14.7; `ebooklib 0.20`, `beautifulsoup4 4.15.0`,
`markdownify` (bản mới nhất PyPI 2026-09-08), `markdown-it-py`. File:
`data/uploads/9d436d7b-…_Baking with Sourdough - Sara Pitzer.epub`, doc `ops/xhtml/chapter01.html`.

```
SOURCE XHTML: {img 10, h2 2, h3 34, p 347, strong 214, em 26, sup 6, a 35, ol 0, ul 0, table 0}
(A) EpubUnit projection: {chars 51774, images 0, h2 2, h3 34, bold 0, italic 0, links 0}
(B) markdownify full DOM: {chars 53123, images 10, h2 2, h3 34, bold 214, italic 26, links 2}
```

Toàn bộ 6 `<sup>` trong chapter01.html:
```
<strong><sup>1</sup>/<sub>3</sub> cup soy grits</strong>
<strong><sup>1</sup>/<sub>3</sub> cup raw wheat germ</strong>
<strong><sup>1</sup>/<sub>3</sub> cup butter</strong>
<strong><sup>1</sup>/<sub>3</sub> cup brown sugar</strong>
<strong><sup>1</sup>/<sub>3</sub> cup flour</strong>
<strong>1<sup>1</sup>/<sub>3</sub> cups unbleached white flour</strong>
```
`markdownify` cho ra `**1/3 cup soy grits**`; projection (A) với rule `extract(sup)` cho ra
`/ cup soy grits`.

`markdownify` trên `<ol><li>Mix flour</li><li>Add water<ul><li>cold</li>…</ul></li><li>Knead</li></ol>`
→ `1. Mix flour / 2. Add water /    * cold /    * warm / 3. Knead`. Trên
`<figure><img alt="Images" src="../images/f0003-01.jpg"/><figcaption>Fig 1</figcaption></figure>`
→ `![Images](../images/f0003-01.jpg)` + `Fig 1`. Trên bảng MinerU `colspan=2` thật →
`| Header spanning 2 | |` (mất span).
