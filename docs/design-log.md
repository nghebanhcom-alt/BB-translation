# Design Log — BB-Translation

> **Nhật ký thiết kế / Root Cause Analysis / Final Decision** — tách khỏi `docs/Architecture.md`
> ngày **2026-09-10** theo **Protocol C** (kỷ luật tài liệu đặc tả, CLAUDE.md).
>
> **Vì sao tách**: `Architecture.md` đã phình lên 12.818 dòng (~238k token — lớn hơn cả context
> window của một agent), trong đó **44% là nhật ký sự kiện** chứ không phải mô tả kiến trúc hiện
> hành. Hệ quả thật: một brief kiểu "Dev đọc Architecture.md trước khi code" **về mặt vật lý không
> thực thi được** — mỗi agent buộc phải đọc chắp vá một mảnh khác nhau. Đây chính là cơ chế đã sinh
> ra Bug #5 và Bug #9.
>
> **Nội dung KHÔNG bị đổi một chữ nào** — chỉ chuyển chỗ nguyên văn. Lịch sử đầy đủ vẫn ở
> `git log -p -- docs/Architecture.md`.
>
> **Ranh giới trách nhiệm giữa 2 file** (bắt buộc, Protocol C):
> - `docs/Architecture.md` = **trạng thái hiện hành**. Hợp đồng đang có hiệu lực: tech stack, data
>   model, API, luồng xử lý, quyết định kiến trúc đang áp dụng. Dev/Reviewer/QA đọc file này để biết
>   *hệ thống PHẢI như thế nào*.
> - `docs/design-log.md` (file này) = **vì sao tới được trạng thái đó**. RCA, phản biện Domain
>   Expert, Final Decision, đo đạc thực nghiệm — theo thứ tự thời gian, chỉ append. Đọc file này khi
>   cần biết *tại sao lại thế*, hoặc trước khi định lật một quyết định cũ.
>
> **Luật ghi mới**: mọi RCA/phản biện/Final Decision mới append vào **cuối file này**. Khi một quyết
> định ở đây làm đổi hợp đồng hệ thống, Tech Lead phải cập nhật phần tương ứng trong
> `Architecture.md` §1–10 — **không để hợp đồng chỉ sống trong nhật ký**.

## Mục lục

> Mục 1–11 đã rotate sang `docs/archive/design-log-until-2026-09-09.md` (2026-09-18), link dưới đây trỏ thẳng vào file lưu trữ.

1. [Root Cause Analysis: Line-break/List Regression (2026-09-06)](archive/design-log-until-2026-09-09.md#root-cause-analysis-line-breaklist-regression-2026-09-06)
2. [Đánh giá hướng Post-Processing cho lỗi gộp dòng Numbered List (2026-09-06)](archive/design-log-until-2026-09-09.md#đánh-giá-hướng-post-processing-cho-lỗi-gộp-dòng-numbered-list-2026-09-06)
3. [Đo lại F1 trên nhiều trang — kết quả live A/B/C (2026-09-06)](archive/design-log-until-2026-09-09.md#đo-lại-f1-trên-nhiều-trang-kết-quả-live-abc-2026-09-06)
4. [US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — thiết kế (2026-09-06)](archive/design-log-until-2026-09-09.md#us-16-nén-ảnh-sau-khi-ghép-compress_pdf_images-thiết-kế-2026-09-06)
5. [Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order trên trang layout phức tạp (2026-09-07)](archive/design-log-until-2026-09-09.md#root-cause-analysis-text-overlap-content-loss-reading-order-trên-trang-layout-phức-tạp-2026-09-07)
6. [Final Decision: Babeldoc Layout Bug Fix Roadmap (sau phản biện Domain Expert, 2026-09-07)](archive/design-log-until-2026-09-09.md#final-decision-babeldoc-layout-bug-fix-roadmap-sau-phản-biện-domain-expert-2026-09-07)
7. [US-16 v2 — Mở rộng phạm vi sang ảnh `/FlateDecode` (2026-09-08)](archive/design-log-until-2026-09-09.md#us-16-v2-mở-rộng-phạm-vi-sang-ảnh-flatedecode-2026-09-08)
8. [US-16 v2 — Phản biện của Domain Expert (2026-09-08)](archive/design-log-until-2026-09-09.md#us-16-v2-phản-biện-của-domain-expert-2026-09-08)
9. [US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08)](archive/design-log-until-2026-09-09.md#us-16-v2-final-decision-sau-phản-biện-domain-expert-2026-09-08)
10. [Bug #9 — `font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc` (2026-09-08)](archive/design-log-until-2026-09-09.md#bug-9-font_shrink_page-phá-output-của-babeldoc-tắt-hẳn-cho-engine-babeldoc-2026-09-08)
11. [Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (`_get_width_before_next_break_point` đếm đôi bề rộng ký tự hiện tại) — thiết kế bản vá (Tech Lead, 2026-09-09)](archive/design-log-until-2026-09-09.md#bug-10-babeldoc-cắt-ngang-từ-tiếng-việt-giữa-chừng-_get_width_before_next_break_point-đếm-đôi-bề-rộng-ký-tự-hiện-tại-thiết-kế-bản-vá-tech-lead-2026-09-09)
12. [Bug #EPUB-3 — Quét job mồ côi (orphan) lúc server startup (Tech Lead, 2026-09-10)](#bug-epub-3-quét-job-mồ-côi-orphan-lúc-server-startup-tech-lead-2026-09-10)
13. [BL-04 — Phát hiện babeldoc tự bỏ đoạn: verify lại R5-05 + Final Decision (Tech Lead, 2026-09-11)](#bl-04-phát-hiện-babeldoc-tự-bỏ-đoạn-verify-lại-r5-05-final-decision-tech-lead-2026-09-11)
14. [Final Decision: Hiếu trả lời HOI-04/HOI-05 (Bug #EPUB-5) — 2026-09-11](#final-decision-hiếu-trả-lời-hoi-04hoi-05-bug-epub-5-2026-09-11)
15. [Rotate Protocol C.3 lần 2 (2026-09-18) — tách nhật ký còn sót khỏi `Architecture.md`](#rotate-protocol-c3-lần-2-2026-09-18--tách-nhật-ký-còn-sót-khỏi-architecturemd)

---

<details>
<summary>Các mục nhật ký 2026-09-06 → 2026-09-09 đã lưu trữ sang <code>docs/archive/design-log-until-2026-09-09.md</code> (rotate Protocol C.2, 2026-09-18)</summary>

1. Root Cause Analysis: Line-break/List Regression (2026-09-06)
2. Đánh giá hướng Post-Processing cho lỗi gộp dòng Numbered List (2026-09-06)
3. Đo lại F1 trên nhiều trang — kết quả live A/B/C (2026-09-06)
4. US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — thiết kế (2026-09-06)
5. Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order trên trang layout phức tạp (2026-09-07)
6. Final Decision: Babeldoc Layout Bug Fix Roadmap (sau phản biện Domain Expert, 2026-09-07)
7. US-16 v2 — Mở rộng phạm vi sang ảnh `/FlateDecode` (2026-09-08)
8. US-16 v2 — Phản biện của Domain Expert (2026-09-08)
9. US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08)
10. Bug #9 — `font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc` (2026-09-08)
11. Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (`_get_width_before_next_break_point` đếm đôi bề rộng ký tự hiện tại) — thiết kế bản vá (Tech Lead, 2026-09-09)

</details>

## Bug #EPUB-3 — Quét job mồ côi (orphan) lúc server startup (Tech Lead, 2026-09-10)

### E3.1. Vấn đề & phạm vi

Background task chạy job (`_schedule_background(_run_job_background(job.id))`,
`src/api/routes/jobs.py:650` và `:766`) là `asyncio.Task` sống trong CHÍNH process uvicorn. Process
chết (crash, deploy, `--reload` reload khi sửa code) → task chết theo, không có `except` nào chạy,
row `jobs` giữ nguyên trạng thái đang chạy VĨNH VIỄN. UI (`web/js/app.js:488`) poll mỗi 3s cho tới
khi status thuộc `TERMINAL_STATUSES` → job kẹt hiển thị "đang dịch" vô thời hạn.

**Không phải bug riêng EPUB** — không có chỗ nào trong đường đi này phụ thuộc `file_type`. Ảnh
hưởng mọi `file_type` (pdf_digital, pdf_scan, epub) và cả `job_type=parse_only` (status `parsing`,
có thể chạy tới ~25 phút).

Gốc rễ: `lifespan()` (`src/api/main.py:80-83`) hiện chỉ có `await init_db()` — **đã đọc code thật,
xác nhận đúng như mô tả**, không có bước quét nào lúc startup.

### E3.2. Tập trạng thái — đọc từ code thật, không suy đoán

`Job.status` là `str` tự do (không phải Enum). Danh sách giá trị thật, gộp từ 3 nguồn:

| Nguồn | Giá trị |
|---|---|
| Comment `src/models/job.py:32-34` | `created`, `queued`, `chunking`, `translating`, `post_processing`, `merging`, `completed`, `failed`, `cancelled`, `cost_capped` |
| Gán thật trong `src/core/job_orchestrator.py` | `translating` (:568, :890), `merging` (:687, :1084), **`parsing`** (:1230, :1469), `completed`, `failed`, `cancelled`, `cost_capped` |
| `src/api/routes/jobs.py` | `queued` (:646 create, :757 retry) |

**Phát hiện 1 (bất ngờ)**: `parsing` **thiếu trong comment liệt kê của `src/models/job.py`** nhưng
được gán thật 2 chỗ trong orchestrator và đã có trong `_ACTIVE_JOB_STATUSES`
(`src/api/routes/jobs.py:832`) + `web/js/app.js:24`. Comment model bị lỗi thời — Dev phải cập nhật
comment đó trong task này (thêm `parsing`), nếu không lần sau lại có người liệt kê thiếu.

**Phát hiện 2**: `chunking` và `post_processing` **KHÔNG BAO GIỜ được gán cho `Job`** ở code hiện
tại (grep toàn `src/`: `post_processing` chỉ gán cho `Chunk` tại `:1884`; `chunking` không xuất
hiện ở vế gán nào). Chúng vẫn nằm trong `_ACTIVE_JOB_STATUSES` như dự phòng. Giữ nguyên trong tập
orphan bên dưới — chi phí bằng 0, và bảo vệ sẵn nếu tương lai có ai dùng lại.

Tập trạng thái cuối (terminal) đã có sẵn tên trong code:
`_TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled", "cost_capped"}`
(`src/api/routes/jobs.py:249`).

### E3.3. Chốt: danh sách trạng thái coi là orphan

```
_ORPHAN_JOB_STATUSES = {
    "created", "queued", "chunking", "parsing",
    "translating", "post_processing", "merging",
}
```

Đúng bằng `_ACTIVE_JOB_STATUSES` (`src/api/routes/jobs.py:821-833`) hiện tại. **Nhưng KHÔNG import
lại set đó** — hai set này trùng giá trị vì trùng ngữ cảnh ("job chưa kết thúc"), không phải vì
cùng một business rule; ghép chúng lại tạo coupling ngầm giữa "cấm xoá job đang chạy" và "quét
orphan lúc startup". Khai báo riêng, kèm comment trỏ chéo sang nhau.

Bao gồm `created`: row ở `created` chỉ sống giữa 2 lần commit trong CÙNG 1 request `POST /api/jobs`
(`src/api/routes/jobs.py:638` → `:646`). Còn `created` sau khi process khởi động lại = request đó
đã chết giữa chừng, KHÔNG có background task nào sẽ nhặt nó lên → là orphan thật.

**Giả định (ghi rõ theo yêu cầu)**: single-process, single-worker. Xác nhận bằng
`.claude/launch.json` — `uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`,
KHÔNG có `--workers`, mặc định uvicorn = 1 worker. Không tìm thấy cấu hình gunicorn/systemd
`--workers > 1` nào trong repo. Do đó: mọi job ở trạng thái "đang chạy" tại thời điểm 1 process MỚI
chạy `lifespan()` chắc chắn là orphan (process cũ phải chết thì mới có process mới) → không có
false positive, không cần lock/transaction chống race.

Với `--reload` ở dev: job thật đang chạy + Dev sửa code → job đó CHÍNH LÀ orphan (task async chết
theo process cũ). Mark failed là ĐÚNG, không phải false positive. Đây là hành vi mong muốn, không
phải tác dụng phụ cần giảm nhẹ.

**Nếu sau này chuyển sang multi-worker** (`--workers N`, hoặc nhiều container cùng 1 SQLite/DB):
thiết kế này SAI ngay lập tức (worker B startup sẽ giết job đang chạy thật của worker A). Lúc đó
phải đổi sang cơ chế heartbeat (`job.heartbeat_at` cập nhật mỗi chunk, quét job có heartbeat cũ hơn
N phút) hoặc owner-token theo process. Ghi lại đây làm điều kiện tiên quyết — ai đổi sang
multi-worker PHẢI đọc lại mục này.

### E3.4. Chốt: hành động — dùng lại `failed`, KHÔNG thêm status mới

Cân nhắc `orphaned` như 1 status thứ 11: **bị loại**. Lý do cụ thể, không phải "cho đơn giản":

- Mỗi status mới phải được thêm ĐỒNG THỜI vào ít nhất 5 chỗ rời rạc:
  `_TERMINAL_JOB_STATUSES`, `_RETRYABLE_STATUSES`, `_ACTIVE_JOB_STATUSES` (loại trừ),
  `TERMINAL_STATUSES`/`ACTIVE_STATUSES` trong `web/js/app.js:16-44`, filter dropdown
  `web/history.html`, cộng mọi nhánh hiển thị badge. Lịch sử repo cho thấy đúng kiểu bỏ sót này đã
  xảy ra 1 lần (S15-12: quên `parsing` trong danh sách JS) — thêm status thứ 11 là tái tạo lại
  đúng rủi ro đó để đổi lấy 1 sắc thái ngữ nghĩa.
- `failed` đã có sẵn toàn bộ hạ tầng: retry được, `finished_at` được tính vào "thời gian dịch"
  (BR-HIST-01), xoá được, hiện badge đỏ, đếm vào `Batch.failed_files`.
- Thông tin "đây là do restart, không phải lỗi dịch" nằm ở `error_message` — vốn đã LUÔN hiển thị
  cạnh status trong UI khi job failed, và câu chữ dưới đây nói thẳng nguyên nhân. Đủ bù đắp.

Với mỗi job orphan tìm được, ghi:

```python
job.status = "failed"
job.error_message = (
    "Job bi gian doan do server khoi dong lai (restart/crash) trong luc dang chay. "
    "Cac chunk da dich xong duoc giu nguyen — bam Retry de chay tiep tu cho dang do."
)
job.finished_at = job.finished_at or datetime.now(UTC)
job.updated_at = datetime.now(UTC)
```

Quy ước câu chữ (khớp code hiện có): `error_message` trong `src/core/job_orchestrator.py:634-638`
và `:1006-1010` viết tiếng Việt **KHÔNG dấu**, cấu trúc "chuyện gì xảy ra — dữ liệu cũ còn nguyên —
làm gì tiếp theo". Câu trên giữ đúng 3 phần đó. **Không đổi sang tiếng Việt có dấu** trong task này
(sẽ lệch với mọi message khác).

`finished_at` bắt buộc gán (US-19/BR-HIST-01/02, §6.17.2): thiếu nó, `_to_detail()`
(`src/api/routes/jobs.py:265-268`) trả `duration_seconds=None` cho job đã ở trạng thái cuối. Dùng
`or` để không đè giá trị cũ nếu vì lý do nào đó đã có.

**KHÔNG đụng tới**: `progress`, `current_chunk`, `total_chunks`, `actual_cost` — giữ nguyên để user
thấy job đã chạy tới đâu trước khi chết. **KHÔNG đụng `Chunk.status`** — xem E3.5.

**KHÔNG quét `Batch`**: `Batch.status` KHÔNG phải chỉ báo tiến độ của user (không hiển thị ở
`web/js/app.js`, không có endpoint list batch), và `created` là trạng thái vĩnh viễn HỢP LỆ của mọi
Batch row sinh ra cho job đơn lẻ (`src/api/routes/jobs.py:478` — mỗi job standalone vẫn tạo 1 Batch
row nhưng `run_batch()` không bao giờ chạy cho nó). Quét batch sẽ mark failed hàng loạt row bình
thường. Ngoài phạm vi task này.

### E3.5. Chunk còn dở — không cần xử lý, đã verify

Resume (BR-CHUNK-05) chỉ skip chunk có `status == "completed"`:
`if chunk.status != "completed":` (`src/core/job_orchestrator.py:578` cho PDF, `:916` cho EPUB), và
bước merge chỉ lấy chunk `completed` CÓ `output_path` (`:1090`). Chunk bị bỏ dở ở `translating`/
`post_processing` sẽ tự được chạy lại ở lần retry, và `_process_chunk()` gán đè
`chunk.status = "translating"` (`:1744`) ngay khi bắt đầu. **Không cần reset Chunk.status về
`pending`** — thêm bước đó là code thừa không đổi hành vi.

### E3.6. Retry sau khi mark orphan — KHÔNG cần sửa gì (đã đọc code xác nhận)

`_RETRYABLE_STATUSES = {"failed", "cancelled", "cost_capped"}` (`src/api/routes/jobs.py:711`) đã
chứa `failed` → job orphan bấm Retry được ngay, **không phải sửa endpoint**. Đường đi retry
(`src/api/routes/jobs.py:714-768`) làm đúng những gì job orphan cần:

1. `job_type == "translate"` → qua lại cost gate (đúng thiết kế §6.11.4 Lớp 3); `parse_only` bỏ qua
   gate (S15-11).
2. `job.status = "queued"`, `job.error_message = None` (xoá câu orphan), `cancel_requested = False`.
3. `_schedule_background(_run_job_background(job.id))` → `run_job()` tự resume từ chunk chưa
   `completed` (BR-CHUNK-05) — **không dịch lại từ đầu**, đúng tinh thần yêu cầu. Với PDF scan,
   `ocr_bridge_path` đã lưu trong DB nên bước OCR cũng không chạy lại.

Lưu ý duy nhất cho Dev: `finished_at` KHÔNG bị reset khi retry (code hiện tại không reset) — hành
vi này đã tồn tại cho mọi retry từ trước, không phải hồi quy do task này, KHÔNG sửa ở đây.

### E3.7. Vị trí code chính xác

**File mới `src/core/job_recovery.py`** (không nhét logic vào `main.py`: để test gọi thẳng hàm với
1 session in-memory, không phải dựng `TestClient` + đè engine global):

```python
_ORPHAN_JOB_STATUSES = {...}  # E3.3

async def fail_orphaned_jobs(session: AsyncSession) -> int:
    """Tra ve so job da mark. Idempotent: chay lai lan 2 tra ve 0."""
```

Thân hàm: `select(Job).where(col(Job.status).in_(_ORPHAN_JOB_STATUSES))` qua SQLModel/AsyncSession
(**không raw SQL** — raw SQL bỏ qua model, dễ lệch tên cột như các migration đã phải xử lý ở
`src/models/database.py`), gán 4 field ở E3.4, `session.add(job)` từng row, `await session.commit()`
MỘT LẦN sau vòng lặp. Ghi log tổng kết:
`logger.warning("Startup: da danh dau %d job mo coi thanh failed (server restart)", count)` — dùng
logger `logging.getLogger(__name__)` (module nằm dưới `src.` nên tự nhận handler từ
`_configure_logging()`).

**`src/api/main.py::lifespan()`** — chèn NGAY SAU `init_db()`, TRƯỚC `yield`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    # Bug #EPUB-3 (Architecture.md §E3): phai chay SAU init_db() (bang/cot
    # phai ton tai truoc khi query) va TRUOC yield (xong truoc khi nhan
    # request dau tien -> khong co race voi job moi tao).
    async with get_session_factory()() as session:
        await fail_orphaned_jobs(session)
    yield
```

Thứ tự bắt buộc: sau `init_db()` (cần bảng + cột đã migrate), trước `yield` (uvicorn chỉ nhận
request sau khi lifespan startup xong → không có job mới nào được tạo song song → không cần
transaction/lock đặc biệt; giả định single-worker ở E3.3).

Không broadcast WebSocket: lúc startup chưa có client nào kết nối, và UI đang mở sẽ nhận qua
polling 3s (`web/js/app.js:488`) trong vòng ≤ 3 giây sau khi server sống lại.

### E3.8. Test bắt buộc (Protocol 6 R6-02 — assert giá trị, không chỉ "đã gọi")

`tests/integration/test_orphan_job_recovery.py`, dùng lại fixture `session` từ
`tests/integration/test_job_orchestrator.py` (pattern y hệt
`tests/integration/test_job_history_finished_at.py`):

1. **Mark đúng tập orphan**: tạo 7 Job, mỗi job 1 status trong `_ORPHAN_JOB_STATUSES`; gọi
   `fail_orphaned_jobs(session)`; assert trả về `7`, và MỌI job có `status == "failed"`,
   `error_message` chứa `"khoi dong lai"`, `finished_at is not None`.
2. **Không đụng trạng thái cuối**: tạo 4 Job ở `completed`/`failed`/`cancelled`/`cost_capped`, mỗi
   job có `error_message` riêng đặt trước; gọi hàm; assert trả về `0` và `error_message` +
   `finished_at` của cả 4 **không đổi** (so sánh giá trị cụ thể, không chỉ `status`).
3. **Giữ nguyên tiến độ**: 1 job `translating` với `progress=0.6`, `current_chunk=3`,
   `total_chunks=5`, `actual_cost=1.23`; sau khi mark, assert 4 giá trị đó **y nguyên**.
4. **Idempotent**: gọi `fail_orphaned_jobs()` 2 lần liên tiếp; lần 2 trả về `0`, và `finished_at`
   của job đã mark ở lần 1 **không bị ghi đè** (assert bằng giá trị đọc được sau lần 1).
5. **Retry được sau khi mark orphan** (đây là assertion nối 2 bước, R6-02): job `translating` →
   `fail_orphaned_jobs()` → gọi `POST /api/jobs/{id}/retry` (hoặc gọi thẳng `retry_job()` với
   session, như `tests/integration/test_job_cancel.py` đang làm) → assert **không** raise
   `HTTPException 400`, và `job.status == "queued"`, `job.error_message is None`,
   `job.cancel_requested is False`.
6. **Chunk completed sống sót qua orphan → retry không dịch lại**: job `translating` có 3 Chunk
   (`completed`, `translating`, `pending`); sau `fail_orphaned_jobs()`, assert `Chunk.status` của
   cả 3 **không đổi** (chứng minh E3.5: hàm không đụng chunk, chunk `completed` vẫn được skip khi
   resume).

Test 5 và 6 là 2 test quan trọng nhất — chúng nối "mark orphan" với "retry resume được", đúng loại
liên kết giữa 2 bước mà Protocol 6 tồn tại để bảo vệ.

### E3.9. Việc KHÔNG làm trong task này

- Không thêm status `orphaned` (lý do E3.4).
- Không quét/sửa `Batch` (lý do E3.4).
- Không thêm heartbeat/owner-token (chỉ cần khi multi-worker — E3.3).
- Không tự động retry job orphan lúc startup (auto-resume): job orphan có thể là job đang tốn tiền
  API; tự chạy lại khi server khởi động = tiêu tiền không có người bấm nút. User bấm Retry.
- Không đổi `error_message` của các nhánh khác sang tiếng Việt có dấu.

## Final Decision: Hiếu trả lời 3 open_questions HOI-01/02/03 + duyệt lại baseline C1/C2 (2026-09-11)

Theo Protocol B (CLARIFY trước, WRITE sau) — cả 3 câu hỏi được PM gộp hỏi một lượt
(`open_questions[]` trong `project_state.json`), Hiếu trả lời trực tiếp trong chat, cả 3 đều
**trùng với mặc định đề xuất**:

- **HOI-01** (cấp API key thật CLAUDE/GEMINI để verify spike rate-limit AIMD?) → **Chưa cấp API
  thật.** Giữ nguyên `[UNVERIFIED]` cho nhánh Claude/Gemini (Architecture.md §6.12.6) — không chặn
  release, DeepSeek/Ollama vẫn là nhánh đã verify dùng cho job thật.
- **HOI-02** (Bug #6: overlay chữ xoay không kích hoạt cho nhánh `pdf_scan` + `babeldoc` — thiết kế
  lại hay chấp nhận giới hạn?) → **Chưa có kế hoạch dùng PDF scan** ở thời điểm hiện tại → chấp
  nhận là giới hạn đã biết của nhánh `pdf_scan` (đã ghi trong PRD.md US-04 "Known limitation Bug #6
  Phase 1"), không mở thêm vòng Dev↔QA để redesign. Nếu sau này có nhu cầu dùng `pdf_scan` thật,
  cần mở lại open_question mới thay vì coi quyết định này là vĩnh viễn.
- **HOI-03** (US-22 EPUB: JSON malformed từ DeepSeek, chọn hướng nào trong 4 phương án ở
  escalation-log.md?) → **Phương án 1**: giảm `EPUB_REQUEST_CHAR_BUDGET` và đo thật trước khi đầu
  tư đổi format request/response.

**Hệ quả**: không có thay đổi code nào cần thiết ngay từ 3 quyết định này — cả 3 đều xác nhận giữ
nguyên hành vi/giới hạn hiện tại, không phải giao việc mới cho Dev. Phương án 1 của HOI-03 (giảm
`EPUB_REQUEST_CHAR_BUDGET`) cần một task đo đạc + điều chỉnh cấu hình riêng, PM sẽ tạo `steps[]`
mới khi bắt tay vào, không tính là đã "làm" chỉ vì đã chọn phương án.

**Đồng thời**, Hiếu duyệt lại baseline cho 2 checkpoint đang `stale` (Protocol C / mở rộng Protocol
2): `docs/PRD.md` và `docs/Architecture.md` ở đúng nội dung hiện tại (2026-09-11) được chốt làm
**Version 2.0** — xem `checkpoints[]` trong `project_state.json` để biết `approved_commit` sau khi
đổi được commit.

---

## BL-04 — Phát hiện babeldoc tự bỏ đoạn: verify lại R5-05 + Final Decision (Tech Lead, 2026-09-11)

**Hợp đồng hiện hành nằm ở `docs/Architecture.md` §6.22** (mục này chỉ ghi *vì sao*, không lặp lại
spec — Protocol C.1). Backlog gốc: `BL-04` trong `project_state.json` → `backlog[]`, phát sinh từ
B9.7 ("khoảng trống đã biết trước — CHẤP NHẬN").

### BL4.1. Việc đầu tiên phải làm là gỡ một nghi vấn version — và nó hoá ra là báo động giả

PM gắn nhãn `[CHƯA VERIFY]` cho một quan sát: trên máy có `babeldoc-0.2.33.dist-info`, khác con số
**0.6.4** mà B9-05 trích dẫn. Ba giả thuyết PM nêu: (a) gõ nhầm lúc ghi design-log, (b) máy đang
chạy bản cũ hơn lúc research, (c) 2 version hành vi khác nhau thật.

Đáp án là **(d) — không có trong danh sách**: máy này có **hai bản babeldoc cài song song, độc lập**.

- `babeldoc` executable → `/Users/hieutt/.local/share/uv/tools/babeldoc/` → **0.6.4**. Đây là bản
  engine `babeldoc` của app thật sự chạy (`BabeldocRunner(executable="babeldoc")`).
- `babeldoc 0.2.33` nằm **bên trong tool env của pdf2zh**, là dependency bắc cầu của
  `pdf2zh v1.9.11`. pdf2zh chỉ dùng nó khi được truyền flag `--babeldoc`; `Pdf2zhRunner` không bao
  giờ truyền flag đó. Bản 0.2.33 là **code chết** với pipeline này.

Chi tiết chuỗi truy vết (5 bước, có lệnh và file:dòng) ở Architecture.md §6.22.1 bảng V-1…V-5.

**Bài học đáng giữ**: nghi vấn version của PM là **đúng quy trình** dù kết luận là báo động giả.
Chi phí để bác bỏ nó: ~10 phút. Chi phí nếu nó đúng mà không ai kiểm: toàn bộ §6.22 xây trên source
của một bản không chạy. Đây đúng là thứ R5-05 sinh ra để mua.

**Một đính chính thật sự có ích rơi ra từ đây**: B9-05 ghi nguồn là `IL/midend/typesetting.py`.
Đường dẫn đó **không tồn tại** trong 0.6.4 — bản 0.6.4 là
`babeldoc/format/pdf/document_il/midend/typesetting.py`, còn layout `babeldoc/document_il/midend/`
(không có tầng `format/pdf/`) lại đúng là layout của **0.2.33**. Không suy ra được là B9-05 đã đọc
nhầm cây source (nội dung kết luận của nó verify lại vẫn đúng, xem BL4.2) — nhiều khả năng chỉ là
ghi tắt đường dẫn. Nhưng đúng bằng cách ghi tắt kiểu này mà một trích dẫn nguồn mất khả năng kiểm
chứng lại. **Trích dẫn nguồn phải là đường dẫn dán được vào `sed -n`, không phải đường dẫn gợi
nhớ.**

### BL4.2. Verify lại B9-05: khớp, nhưng cơ chế "drop" khác với hình dung — và chính chỗ khác đó là lời giải

Đọc lại trực tiếp `typesetting.py` (1.682 dòng) của đúng bản 0.6.4. Cả 3 vế của B9-05 đều **đúng**
(bảng đối chiếu từng vế ở §6.22.2). Nhưng B9-05 mô tả drop như một hành động — "bỏ hẳn đoạn". Thực
tế **không có lệnh drop nào cả**:

`render_paragraph()` **xoá trắng** `paragraph.pdf_paragraph_composition = []` *trước* khi typeset
lại (`typesetting.py:1277`), rồi chỉ ghi nội dung trở lại khi tìm được scale mà mọi unit vừa khung
(`:986-1002`). Không scale nào vừa → composition **ở nguyên trạng thái rỗng**. Đoạn văn không bị
"bỏ" — nó bị **quên ghi lại**.

Khác biệt này nghe như chuyện chữ nghĩa, nhưng nó quyết định toàn bộ thiết kế: một hành động "drop"
thì phải đi tìm chỗ babeldoc gọi hàm drop (không có). Một **trạng thái** "composition rỗng nhưng
`unicode` vẫn còn bản dịch" thì quan sát được ở bất kỳ điểm nào sau typesetting — và hoá ra chính
babeldoc cũng đang kiểm tra đúng trạng thái đó ở `pdf_creater.py:831`.

Hai điều nữa B9-05 không nêu, ghi lại để lần sau khỏi đọc lại:
- Trước khi bỏ cuộc, babeldoc còn **nới rộng chính cái box** (xuống dưới, rồi sang phải) vào vùng đã
  kiểm tra là trống, và cập nhật `paragraph.box` theo (`:1020-1056`). Nên "không vẽ ra ngoài box"
  đúng theo nghĩa "box cuối cùng", không phải "box ban đầu".
- Vòng giảm scale **chỉ chạy quá một vòng khi `paragraph.debug_id` khác rỗng** (`:1008-1009`). Suýt
  kết luận nhầm rằng toàn bộ cơ chế bóp font là code chết ngoài chế độ debug — phải đi kiểm
  `paragraph_finder.py:500` mới thấy `debug_id=generate_base58_id()` được gán cho **mọi** paragraph,
  không phụ thuộc `--debug`. Đây là loại giả định mà nếu tin theo tên biến (`debug_id` → "chỉ có khi
  debug") thì sai hoàn toàn.

### BL4.3. Có tín hiệu quan sát được — hai tín hiệu, và lý do không chọn cái dễ thấy hơn

Câu hỏi Bước 2 có đáp án **CÓ**. Nhưng hai ứng viên không ngang nhau:

**Tín hiệu 1 — log stdout.** `pdf_creater.py:832` gọi `logger.error("Unable to export paragraphs
that have not yet been formatted: {paragraph}")` đúng khi trạng thái ở BL4.2 xảy ra. Đã đo thật
(chạy bằng interpreter của chính tool env babeldoc, dựng lại `basicConfig` + logger name thật, tách
2 luồng): ra **stdout**, stderr 0 byte — cùng đường với tín hiệu rate-limit mà 6.12/6.14.3 đã dùng.

Nhưng đo tiếp thì lộ giới hạn: ở 80 cột, rich bẻ dòng **cắt cả giữa token**, xé câu sentinel thành
`Unable to` / `export paragraphs that have not yet` / `been formatted:`. Neo theo cụm từ sẽ hỏng —
đúng lý do 6.14.3 chọn neo `RATE_LIMIT_LINE_RE` vào **một token duy nhất**. Ở `COLUMNS=200` (giá
trị `BabeldocRunner` **đã set sẵn** từ trước, `babeldoc_runner.py:374`) thì cụm sentinel nằm trọn
một dòng, nhưng `repr(paragraph)` phía sau vẫn wrap và vẫn cắt giữa từ tiếng Việt. Và quan trọng
nhất: **log không chứa số trang**.

Còn một cạm bẫy nữa chỉ lộ ra khi đọc `main.py`: `speed_up_logs()` (`:944`) thay handler bằng
`QueueHandler` trên một `EvictQueue(1000)` **tự vứt bản ghi khi đầy** (`:895-903`). Nghĩa là đếm
theo stdout có thể **thấp hơn thực tế** khi log dồn — một cơ chế đo im lặng bỏ sót chính thứ nó
được giao đo.

**Tín hiệu 2 — shim.** Repo này đã có `src/babeldoc_shim/sitecustomize.py` (744 dòng, dựng cho Bug
#7 và Bug #10): meta-path finder + loader bọc từng module, version gate `0.6.4`, fail-safe rollback
độc lập từng patch. Bọc `PDFCreater.create_render_units_for_page` cho ta **object `page`** — tức số
trang — cùng toàn bộ `paragraph` nguyên vẹn, có cấu trúc, không qua rich.

**Chốt: shim làm nguồn chính, stdout làm nguồn đối chiếu.** Không bỏ hẳn stdout: khi hai con số lệch
nhau, cái lệch đó là cảnh báo về **chính cơ chế đo** (§6.22.6), và đó là thứ Bug #5 đã dạy — một
đường ống không tự kiểm tra thì hỏng im lặng.

**Điều tự đặt giới hạn cho mình**: patch mới **chỉ đọc, không sửa** hành vi typeset — khác hẳn 4
patch hiện có. Ghi thành ràng buộc thiết kế trong §6.22.4 chứ không chỉ là ý định: nếu
implementation cần sửa dữ liệu mới lấy được tín hiệu thì thiết kế sai, dừng và escalate. Bug #9 xảy
ra chính vì một bước "vô hại" hoá ra có ghi.

### BL4.4. Không tái dùng bảng `overflow_reports` — dù đề bài mở đường cho việc đó

Cân nhắc rồi và **bác**. 5/9 field của `OverflowReport` babeldoc không cho biết:
`font_size_original`, `font_size_final`, `scaling_applied`, `still_overflow`, `block_index`. Riêng
`scaling_applied` là chỗ bẫy nhất: có vẻ ánh xạ được sang `paragraph.scale`, nhưng `paragraph.scale`
**chỉ được gán khi apply thành công** (`typesetting.py:989`) — nên ở đúng ca drop nó luôn là `None`.
Ghi `None` vào thì cột vô nghĩa; ghi `0.1` (đoán rằng nó đã bóp tới sàn) thì **bịa số đo**.

Và `still_overflow` thì sai ngữ nghĩa ở mức khái niệm: babeldoc **không tràn**, nó **bỏ**. Nhét dữ
liệu của một hiện tượng vào lược đồ của hiện tượng khác chỉ để khỏi tạo bảng mới là cách tạo ra dữ
liệu *trông như đã đo*.

Chọn `layout_qa_findings` + `persist_findings()` — đúng "nơi đặt tự nhiên" mà B9.7 đã dự đoán từ
2026-09-08, `detail` là JSON tự do nên chứa được đúng những gì đo được, không hơn không kém, và
**không cần migration**.

Hệ quả kèm theo, ghi để khỏi tưởng là bug: `OverflowReport.page_number` đang là **0-based**
(`font_shrink.py:194` dùng `page.number` của PyMuPDF) còn `LayoutQaFinding.page_number` là
**1-based** (`layout_qa.py:403`). Thiết kế này theo 1-based cho khớp bảng nó ghi vào. Thống nhất 2
bảng là việc riêng, đụng dữ liệu lịch sử nhánh pdf2zh — **không** gộp vào đây.

### BL4.5. Ba trạng thái, không phải hai

Điểm dễ hỏng nhất của cả thiết kế, tách riêng để không bị đọc lướt: khi không có record nào, có
**hai** khả năng hoàn toàn khác nhau — *"đã đo, không có đoạn nào bị bỏ"* và *"không đo được"*
(shim tắt, version babeldoc khác 0.6.4, patch fail). Gộp hai cái đó thành "0 drop" là tái tạo lại
Bug #5 ở quy mô nhỏ: hệ thống báo tin tốt trong khi thực ra nó đang mù.

Vì vậy shim ghi một dòng `header` ngay khi patch áp thành công, và trạng thái thiếu header sinh ra
finding riêng `babeldoc_drop_report_unavailable` (`severity="major"`). Ba trạng thái, đối xử khác
nhau — bảng ở §6.22.6.

### BL4.6. Trạng thái verify và điều CHƯA có bằng chứng

| Claim | Mức | Nguồn |
|---|---|---|
| babeldoc engine của app = 0.6.4; 0.2.33 không bao giờ chạy | tự verify | §6.22.1 V-1…V-5 (lệnh + file:dòng) |
| Cơ chế drop = composition rỗng, không có lệnh drop | tự verify (đọc source 0.6.4) | `typesetting.py:1277`, `:986-1002`, `:1064-1076` |
| `logger.error` ở `pdf_creater.py:832` đúng là điều kiện drop | tự verify | `pdf_creater.py:814-836` |
| Log ra **stdout**, không phải stderr | **đo thật** | chạy probe bằng interpreter tool env babeldoc, tách 2 luồng: stderr = 0 byte |
| Rich bẻ dòng cắt giữa token ở 80 cột; sentinel nguyên vẹn ở `COLUMNS=200` | **đo thật** | cùng probe, chạy 3 bề rộng (mặc định / 200 / 400) |
| `page.page_number` = chỉ số 0-based của tài liệu **gốc** tại thời điểm hook | tự verify | `pdf_creater.py:1708` (`pdf[page.page_number].xref`) + thứ tự `:1465-1466` chạy **trước** `:1489-1502` (xoá trang) |
| Hook chạy đúng 1 lần/trang, bản dual không render lại | tự verify | `pdf_creater.py:1465-1466`, `:1559-1574` |
| **Tồn tại một đoạn bị drop thật trong tài liệu đang dùng** | ⚠️ **CHƯA VERIFY** | chưa chạy babeldoc E2E; mọi kết luận trên đều từ đọc source + đo log, **chưa từ một ca drop quan sát được** |

Dòng cuối là giới hạn thật của hạng mục này, không phải thủ tục. Nếu E2E (§6.22.9) không tạo được
ca drop nào, **không** kết luận là thiết kế sai — nhưng phải trình Hiếu quyết giữa: dựng tài liệu ép
drop (khung hẹp + câu dài), hay đóng BL-04 ở mức *"cơ chế đã có, chưa quan sát được ca thật"*.
Không tự chọn hộ.

### BL4.7. Final Decision

1. **BL-04 là khả thi — KHÔNG đóng ở trạng thái "không khả thi".** babeldoc có tín hiệu quan sát
   được, ở hai mức độ tin cậy khác nhau.
2. **Nguồn chính**: shim observer bọc `PDFCreater.create_render_units_for_page`, ghi JSONL sidecar.
   **Nguồn đối chiếu**: đếm sentinel trên stdout. Lệch nhau → finding riêng.
3. **Ghi vào `layout_qa_findings`** (`check_type="babeldoc_paragraph_drop"`), **không** vào
   `overflow_reports`.
4. **Không đụng một dòng nào** vào quyết định Bug #9: `needs_font_shrink` giữ nguyên, khối
   `OverflowReport` hiện có giữ nguyên (audit R8-01 đầy đủ ở §6.22.7).
5. **Capability mới** `reports_own_paragraph_drops: ClassVar[bool]` trên từng runner (R8-03), có
   guard `isinstance(..., bool)` như `_needs_font_shrink` — vì `AsyncMock(spec=...)` copy TÊN chứ
   không copy GIÁ TRỊ, thiếu guard thì test chạy nhầm nhánh mà vẫn PASS.
6. **Gate release**: golden file cho test **phải sinh từ lần chạy thật**, không viết tay (Protocol 5
   mục 3). Live E2E mở PDF ra đối chiếu bằng mắt, không chỉ tin số đếm (R6-03).

---

## BL-04 — Final Decision LẦN 2, sau REJECT của Domain Expert (Tech Lead, 2026-09-11)

**Bối cảnh**: Domain Expert (Protocol D, lượt 1/2) đã tự đọc lại source babeldoc 0.6.4 **độc lập**
— không tin lại trích dẫn của tôi — và xác nhận cơ chế cốt lõi (composition bị xoá trắng,
`all_units_fit`, `paragraph.scale is None` ở ca drop, hook chạy đúng 1 lần/trang) là **ĐÚNG**, nhưng
**REJECT** thiết kế với 4 điểm blocking F1–F4 + 5 điểm nên-sửa F5–F9 + 1 điểm đổi mục tiêu E2E.
Note đầy đủ: `docs/expert-notes/domain-expert-20260911-bl04-babeldoc-overflow.md`.

Đây là **lượt sửa 2/2** theo giới hạn Protocol D. Hợp đồng hiện hành đã cập nhật tại
`docs/Architecture.md` §6.22 (Protocol C.1 — mục này chỉ ghi *vì sao*, không lặp lại spec).

**Nguyên tắc tôi tự áp cho lượt này**: tôi **không** kế thừa trích dẫn của Domain Expert như sự thật
(đúng như DE đã không kế thừa của tôi). Mọi file:dòng dưới đây tôi đã tự mở lại. Chỗ nào tôi đo thêm
ra số khác hoặc sắc thái khác, tôi ghi rõ.

### BL4.8. F1 — Chồng lấn chunk: từ "lỗi tôi không nhìn thấy" thành "tính chất của hệ, phải khoá lại"

**Đã tự verify lại, không tin lại**: `chunking.py:75` (`start = end - overlap + 1`) và `:60-61`
(`overlap_start = start`, `overlap_end = start + overlap - 1`) ⇒ chunk chồng nhau 2 trang.
`chunk_merge.py:85-91` (`actual_start = chunk.overlap_end + 1`) ⇒ bản render 2 trang đầu của mọi
chunk sau chunk đầu **bị vứt**. `typesetting.py:919-935` tôi đọc trực tiếp: `all_paragraphs` gom từ
**mọi trang của `document` trong chính lần gọi đó**, `statistics.multimode(all_scales)`, rồi hạ mọi
`optimal_scale > mode_scale` xuống mode. DE đúng cả 3 vế.

**Vì sao tôi trượt điểm này ở lượt 1**: §6.22.7 (audit Protocol 8) của tôi CÓ liệt kê
`merge_chunk_pdfs` — và tôi đã trả lời **"không liên quan"**, với lý do "số trang trong report đã là
số trang tài liệu nguồn". Lý do đó **đúng về đơn vị đo** nhưng trả lời nhầm câu hỏi: R8-01 hỏi *"bước
cũ này giải quyết vấn đề gì, biến thể mới có vấn đề đó không"*, còn tôi trả lời *"bước cũ có làm sai
đơn vị đo của tôi không"*. `merge_chunk_pdfs` tồn tại để **vứt bỏ trang chồng lấn** — và đó chính là
vấn đề của tôi. Tôi đã chạy đúng thủ tục R8-01 mà vẫn ra kết luận sai vì trả lời sai câu hỏi. Ghi
lại đây vì đó là chế độ hỏng của Protocol 8 mà bối cảnh Bug #9 chưa mô tả: **không chỉ "quên liệt kê
bước cũ", mà còn "liệt kê rồi nhưng trả lời một câu hỏi dễ hơn"**.

**Quyết định**: giữ kết quả của chunk **đứng trước** (chunk có bản render sống sót vào file cuối),
loại mọi record `page_number < overlap_end + 1` của chunk `N > 0`.

**Điều tôi bổ sung thêm mà DE chưa nêu — và nó là thứ khiến quyết định này an toàn**: lọc như vậy
**không tạo lỗ hổng quan sát**, vì các dải sống sót **phủ kín và rời nhau** trên `[1, total_pages]`,
và mỗi chunk quan sát cả dải `[page_start, page_end]` ⊇ dải sống sót của chính nó. Nên mọi trang vật
lý của file cuối vẫn được đo **đúng một lần, bởi đúng lần chạy đã tạo ra trang đó**. Không có điều
này thì "lọc bớt record" nghe như tự bịt mắt; có nó thì đây là phép chọn đúng vật thể để đo. Đã viết
vào §6.22.5.1.

**Hàm dùng chung `surviving_page_range()`** đặt tại `src/core/chunking.py` (nơi định nghĩa luật chồng
lấn), dùng structural typing (`Protocol`) để hợp cả `ChunkPlan` lẫn `models.Chunk` mà **không** kéo
import model vào `core/chunking.py`.

**Một bất biến DE không nêu, tôi phát hiện khi đọc call site**: `chunk_merge` phân biệt chunk đầu
bằng `position` (chỉ số trong list đã sort), còn `_process_chunk` chỉ có `chunk.chunk_index`. Hai thứ
này **chỉ trùng nhau khi merge được gọi với đủ chunk**. Hiện tại đúng (`job_orchestrator.py:693`
truyền nguyên `chunks`), nhưng đó là phụ thuộc vào code khác ⇒ tôi **không** ép hàm chung tự suy
`is_first` từ `overlap_end is not None` (làm vậy sẽ âm thầm đổi hành vi merge trong ca chunk 0 vắng
mặt, hướng **mất trang**), mà giữ `is_first_in_merge` làm tham số tường minh **cộng** một
`logger.warning` trong `merge_chunk_pdfs` khi `position != chunk.chunk_index`. Bất biến được **kiểm**
chứ không được giả định.

**KHÔNG sửa lỗi cùng loại ở nhánh pdf2zh** (`job_orchestrator.py:1901` cũng đếm 2 lần trên ~20
trang/cuốn). DE nói "gần như miễn phí nếu đã tách hàm chung" — đúng về chi phí code, nhưng §6.22.7 đã
chốt "không đụng một dòng nào vào nhánh pdf2zh/Bug #9", và đổi số row `overflow_reports` là đổi dữ
liệu lịch sử + kéo theo test hồi quy của một hạng mục khác. → backlog **BL-07**.

### BL4.9. F2 — `header` chứng minh "patch đã cài", không chứng minh "đã quan sát"

DE đúng, và đúng ở chỗ đau: tôi đã tự nhận trạng thái 3 ("không đo được") là *"điểm dễ sai nhất của
cả thiết kế"* rồi lại xây nó trên một bằng chứng chứng minh nhầm thứ. Header được ghi trong
`_PatchingLoader.exec_module` — **lúc import module**, trước khi render trang nào.

**Đã sửa**: shim ghi thêm 1 record `type="page"` cho **mỗi** trang đi qua hook; runner đối chiếu
`observed_pages` với `expected_pages`; ba trạng thái thành **bốn** (thêm `babeldoc_drop_report_incomplete`,
`severity="major"`). Parser không giả định vị trí/số lượng dòng `header`, và đếm
`malformed_line_count`.

Ta biết trước `expected_pages` là **con số xác định, kiểm được** — không phải suy đoán: `create_il()`
lọc `docs.page` theo `should_translate_page(page.page_number + 1)` (`il_creater.py:1347-1353`, tôi đã
tự mở lại), và runner luôn truyền `page_range=f"{chunk.page_start}-{chunk.page_end}"`
(`job_orchestrator.py:1806`).

**Tôi thêm một thứ DE không nêu**: `page.dropped_count` làm **checksum chéo trong chính file** — số
record `drop` của mỗi trang phải khớp con số trang đó tự khai. Một dòng bị xé/mất khi ghi sẽ lộ ra ở
`detail["checksum_mismatch_pages"]` thay vì âm thầm làm giảm số finding. Chi phí: 1 field.

**Về đa process**: tôi đã tự verify lại thay vì chép nhận định của DE. `main.py:951` đặt
`spawn`; `pdf_creater.py` chỉ tạo process con tại `subset_fonts_in_subprocess` (`:1220`, gọi ở `:1216`
nhánh debug và `:1479`) — bước đó không render paragraph. Vòng render `:1465-1466` chạy ở process
chính ⇒ **chỉ process chính ghi `page`/`drop`**, nhưng **có thể nhiều dòng `header`**. Đã viết vào
§6.22.4 ("Ai ghi file này") kèm `pid` trong header.

### BL4.10. F3 — Thiết kế này chỉ phủ 1 trong ≥3 kênh mất chữ. Đây là điểm nặng nhất.

DE **đo thật**, không suy đoán: trang 19 mất `'History of Pâtisserie in France'`, trang 31 mất
`'A Life and Career in the Pastry Kitchen'`, 52/418 trang có chữ dọc, ký tự dọc 2.303 → 1.327. Tôi tự
mở `il_creater.py` và xác nhận cơ chế: `:969-970` (`aw_font_id is None` → `return`) và `:972-974`
(góc ngoài `[-0.1,0.1] ∪ [89.9,90.1]` → `return`). Ký tự bị loại ở đây **không bao giờ** thành
`PdfCharacter` ⇒ không thuộc paragraph nào ⇒ hook của tôi mù hoàn toàn, và sentinel ở
`pdf_creater.py:831` cũng không kêu.

**Tôi kiểm thêm một vế DE không kiểm, và nó làm vấn đề nặng hơn chứ không nhẹ đi**: có thể phản bác
rằng "kênh (2) đã có `overlay_rotated_text` lo". Tôi đã tự tra: `babeldoc_rotated_text_overlay` mặc
định `True` (`config.py:208`), `.env` **không** override, và bước overlay có từ commit `b9c8952`
ngày **2026-09-07** — tức **trước** job `1ee1fdee` (2026-09-09). Vậy overlay **đã bật và đã chạy**,
mà trang 19/31 vẫn mất chữ **và** `layout_qa_findings` của job đó = **0 row**. ⇒ kênh (2) hiện
**không** được phủ kín, và khi không phủ được nó cũng **không** luôn để lại cờ. Phản bác đó chết.

**Đã sửa (phần bắt buộc)**:
- Đổi tên: `babeldoc_paragraph_drop` → **`babeldoc_paragraph_drop_unfit`**, **cộng** bắt buộc
  `detail["cause"] = "typeset_unfit"` (tên có thể bị ai đó đổi, `cause` khoá ngữ nghĩa lại).
- Đổi tiêu đề §6.22 + thêm khối trích dẫn phạm vi ngay dưới tiêu đề.
- §6.22.6.1 mới: bảng 3 kênh có nguồn xác thực từng dòng + toàn bộ số liệu đo của DE.
- **Ràng buộc hình thức**: hệ thống **không được phép** phát ra chuỗi "0 drop" trần. Định dạng bắt
  buộc luôn kèm mẫu số (`observed=42/42`) **và** câu PHAM VI. Đây là chỗ tôi cứng rắn hơn đề xuất
  của DE: DE đề nghị "thêm 1 đoạn văn vào §6.22.6"; một đoạn văn trong tài liệu 7.900 dòng không
  ngăn được ai đọc log thấy `drops=0` rồi kết luận "sạch". Ràng buộc phải nằm trong **định dạng
  output**, không chỉ trong tài liệu.

**Phần (b) — đếm ký tự bị loại ở `on_lt_char`: QUYẾT ĐỊNH KHÔNG LÀM trong BL-04.** Lý do, theo đúng
R8-02 (deny-by-default) chứ không phải để né việc — tôi đã khảo sát 3 cách và bác từng cách **có
nguồn**:

1. *Patch `on_lt_char` và tự tính lại `get_rotation_angle`*: phải **chép predicate của babeldoc**
   (2 khoảng + hằng số) thành nguồn sự thật thứ hai, đặt trên hàm **nóng nhất của parser** (~100k lời
   gọi cho 1 chunk 42 trang). Project này đã có 2 vết sẹo từ đúng khuôn "hai bản sao rồi lệch nhau"
   (Bug #5, Bug #9).
2. *Đếm theo kết quả (`len(_page_valid_chars_buffer)` trước/sau)*: tôi đã đọc `_collect_valid_char`
   (`il_creater.py:1122-1157`) — nó **còn tự loại thêm** theo `unicodedata.category ∈ {Cc,Cs,Co,Cn}`,
   chuỗi chứa `"(cid:"`, và `font_mapper.has_char()`. Những ca đó **không** phải mất chữ do góc xoay.
   Counter không tách được 2 nguyên nhân = counter sẽ bị bỏ qua sau vài lần báo động giả — đúng chế
   độ hỏng mà chính F1 cảnh báo.
3. *Đếm ký tự IL tại hook đang có*: **sai điểm đo** — hook chạy **sau** dịch, ký tự ở đó là bản VI,
   không so được với nguồn EN.

Thay vì để backlog rỗng, tôi ghi luôn **ứng viên thiết kế đã khảo sát** vào BL-08:
`ILCreater.on_page_end` (`il_creater.py:641-664`) — **1 lời gọi/trang**, đọc `_page_valid_chars_buffer`
trước khi nó bị clear, so với số ký tự trang nguồn qua PyMuPDF. Kèm **điều kiện tiên quyết**: phải
**đo trước** biên độ nhiễu (pdfminer vs PyMuPDF, cộng nhiễu `_collect_valid_char`) rồi mới đặt
ngưỡng. Cấm đặt ngưỡng từ suy đoán.

⚠️ **Rủi ro còn lại tôi KHÔNG che**: sau BL-04, một chunk vẫn có thể mất chữ qua kênh (2)/(3) mà hệ
thống **không** phát ra cảnh báo nào của riêng kênh đó. Thứ BL-04 mua được là hệ thống **không còn
nói dối rằng nó đã kiểm hết** — mọi con số đều đi kèm phạm vi. Đó là một mức bảo đảm yếu hơn "phát
hiện mọi mất chữ", và tôi ghi rõ mức đó thay vì để người đọc tự suy.

### BL4.11. F4 — Không ai đọc `layout_qa_findings`. Câu "đã có UI/QA đọc" là tôi viết sai.

Tôi đã tự chạy lại `grep -rln "LayoutQaFinding\|layout_qa_finding" src/ web/ scripts/ tests/`: 3
writer (`rotated_text_overlay.py`, `layout_qa.py`, `mineru_det_probe.py`), phần còn lại là model/
export/test. **0 route trong `src/api/`, 0 file trong `web/`.** DE đúng, tôi sai. Câu đó lọt vào
Architecture.md vì tôi suy từ *"bảng này sinh ra cho QA soi tay"* (đúng ý định) sang *"đã có UI/QA
đọc"* (sai sự thật) — đúng loại claim mà 6 tháng sau có người sẽ dựa vào mà không kiểm lại.

**Quyết định — chọn (a) + mở (b) thành backlog, KHÔNG chọn (c)**:
- BL-04 **giao** đường đọc tối thiểu: log R-1 (1 dòng/chunk, `WARNING` khi có drop hoặc trạng thái
  3/4), log R-2 (1 dòng/job tại Bước 10 trước `job.status = "completed"`), và câu SQL dán được cho QA
  trong `test-report.md`.
- BL-04 **không giao** route API / badge UI / cột mới trong `JobDetail` → backlog **BL-09** (đã ghi
  sẵn điểm sửa: `jobs.py:702-717`, `_to_detail()` hiện là hàm thuần từ 1 row `Job` nên phải thêm 1
  query).
- **Giới hạn đã biết, ghi thẳng vào hợp đồng**: cảnh báo chỉ tới được **người đọc log server**, chưa
  tới được người dùng qua UI.

Tôi không chọn (c) ("ghi DB rồi thôi, chỉ cần trung thực") vì số liệu của DE làm (c) mất giá trị:
**1 row/cuốn 418 trang**. Đúng như DE nhận xét ở D4 — *chính vì hiếm* mà không ai soi tay ra được, và
*chính vì hiếm* mà khi nó xảy ra thì không cơ chế nào khác bắt. Một cờ hiếm nằm trong bảng không có
reader thì thực tế bằng 0 row.

### BL4.12. F5–F9 — điểm nên-sửa: nhận 5/5, không bỏ điểm nào

| # | Nội dung | Xử lý |
|---|---|---|
| F5 | Mismatch sentinel phải **một chiều** (EvictQueue làm sentinel ≤ structured theo thiết kế) + nói rõ 2 con số **không độc lập** (cùng call site: `logger.error` ở `pdf_creater.py:831` nằm trong `render_paragraph_to_char`, được gọi từ chính `create_render_units_for_page` ở `:852`) | **Nhận**. Đổi `!=` → `>`; ghi rõ giới hạn + số liệu "1 ca drop/418 trang ⇒ phép đối chiếu này gần như luôn `0 == 0`, đừng đầu tư thêm" |
| F6 | Severity phải đăng ký ở `_SEVERITY_BY_CHECK`, không hardcode; danh sách `check_type` của tôi **thiếu 2** giá trị | **Nhận**. Tôi tự mở `layout_qa.py:76-84`: đúng là 7 khoá, tôi liệt kê 5 — thiếu `rotated_text_overlay_flag` và `rotated_text_scan_unsupported`, mà cái đầu lại là giá trị **duy nhất** đang thực sự có trong DB. Đã đính chính + thêm 3 khoá mới của BL-04 vào chính dict đó + thêm test `test_severity_from_registry` |
| F7 | Lý do "400 ký tự cho ghi nguyên tử `O_APPEND`" **sai kỹ thuật** | **Nhận, và tự đo lại thay vì chép con số của DE**: DE ghi `PIPE_BUF` "512B"; tôi chạy `os.pathconf(".", "PC_PIPE_BUF")` trên chính máy này → **512** (Darwin). Đúng. 400 ký tự VI với `ensure_ascii=False` ~1.200 byte ⇒ vượt xa. Chọn phương án 1 của DE: **bỏ lý do sai, giữ 400 với lý do thật** ("đủ để QA nhận ra đoạn, giữ file nhỏ"), và ghi rõ 400 **không** phải bất biến kỹ thuật |
| F8 | `optimal_scale == 0.1` là **marker chẩn đoán** | **Nhận**. Tự verify lại `typesetting.py:1076` (trả `min_scale` khi không fit) + `:929-935` (chỉ **hạ** giá trị lớn hơn mode ⇒ 0.1 sống sót). Đã viết vào cột "Ghi chú" của schema: `== 0.1` ⇒ "đã biết không fit từ bước preprocess"; khác 0.1 ⇒ "từng fit ở preprocess nhưng drop ở lần typeset thật" |
| F9 | Bước dedupe giải quyết vấn đề không tồn tại, và chỉ có thể gây hại (`generate_base58_id(length=5)` có thể trùng ⇒ gộp nhầm) | **Nhận, bỏ hẳn dedupe.** Ghi rõ trong schema rằng `debug_id` **không** phải khoá dedupe (ngẫu nhiên mỗi lần chạy ⇒ vô dụng xuyên chunk; 5 ký tự ⇒ có thể gộp nhầm trong cùng trang). Thứ cần khử là chồng lấn — đã có bộ lọc F1 |
| A9 | Sidecar **phải** nằm trong `chunk_output_dir` vì `_call_translator` `rmtree` mỗi attempt | **Nhận**, và tôi tự verify lại `job_orchestrator.py:1801-1802`. Đã nâng từ "phụ thuộc tình cờ" thành **ràng buộc ghi trong hợp đồng** (§6.22.4 "Vị trí file") + thêm 1 dòng vào bảng audit R8-01 §6.22.7 |

### BL4.13. Gate E2E: đổi mục tiêu từ chunk 0 sang **trang 230 / chunk 5 (`--pages 199-240`)**

Đây là đóng góp có giá trị cao nhất của lượt phản biện, và nó **bác một giả định của tôi bằng dữ
liệu**: tôi đề xuất chunk 0 vì đó là chunk QA đã quen dùng cho Bug #8/#9 — tức tôi chọn theo *tiện*,
không theo *có ca drop hay không*. DE đo cả 418 trang và cho thấy chunk 0 **không có ca drop kiểu (1)
nào** (ứng viên `src > 300` ký tự, tỉ lệ `< 0.75`: **0**). Gate đó sẽ ra "0 drop" và **không chứng
minh được gì** — một gate xanh vô nghĩa còn tệ hơn không có gate, vì nó tạo niềm tin sai.

Ca thật: **trang 230**, sidebar EN 614 ký tự trong khung 271 × 243 pt, font 12 pt, tỉ lệ ký tự ngang
2318 → 1440 = **0.62** (6 trang "mất nhiều nhất" còn lại của cả cuốn đều 0.84–0.88 và đã kiểm là
không block nào vắng mặt — đó là co ngót dịch bình thường). Bằng chứng là **đọc toàn văn** output
trang 230, không phải heuristic.

**Bẫy đã viết vào §6.22.9 bằng chữ đỏ**: KHÔNG được cắt 2-3 trang quanh 230 cho rẻ. `preprocess_document`
ép scale theo mode của **toàn bộ tập trang trong chính lần gọi đó** ⇒ tập trang khác ⇒ ca drop có thể
biến mất. Phải chạy đúng `--pages 199-240` (42 trang). Đây cũng chính là lý do kỹ thuật của F1 — cùng
một cơ chế, hai hệ quả khác nhau.

Assertion gate: `observed_pages == set(range(199,241))` · có record `page_number_1based == 230` ·
`text_excerpt` là bản dịch VI của đoạn feuilletage · **mở PDF trang 230 xác nhận đoạn đó thật sự
vắng** (R6-03) · **không** có finding nào ở trang 199-200 (chứng minh bộ lọc F1 chạy trên dữ liệu
thật) · dòng log R-1 đúng định dạng có `observed=42/42` + câu PHAM VI.

Số test unit/integration: 5 → **10** (thêm `test_drop_report_incomplete`,
`test_overlap_pages_filtered`, `test_surviving_range_shared`, `test_sentinel_mismatch_one_way`,
`test_severity_from_registry`).

### BL4.14. Final Decision lần 2 — thay thế BL4.7 ở các điểm mâu thuẫn

1. Giữ nguyên mọi kết luận của BL4.7 **trừ** các điểm dưới.
2. `check_type` chính đổi thành **`babeldoc_paragraph_drop_unfit`** + bắt buộc
   `detail["cause"] = "typeset_unfit"`; severity **tra từ `_SEVERITY_BY_CHECK`**, không hardcode.
3. **Bốn** trạng thái, không phải ba (thêm `babeldoc_drop_report_incomplete`); bằng chứng "đã quan
   sát" là record `type="page"`, **không** phải dòng `header`.
4. **Bắt buộc lọc dải trang sống sót** bằng `surviving_page_range()` dùng chung với
   `merge_chunk_pdfs`; **bỏ hẳn** dedupe theo `debug_id`.
5. Schema sidecar lên **`babeldoc_drop_report/v2`**; sidecar **phải** nằm trong `chunk_output_dir`.
6. Mismatch sentinel **một chiều** (`>`), có ghi rõ giới hạn của phép đối chiếu.
7. BL-04 giao **đường đọc tối thiểu bằng log** (R-1/R-2/R-3); **không** giao UI. Giới hạn này ghi
   thẳng vào hợp đồng.
8. Gate E2E: **trang 230 / chunk 5 / `--pages 199-240`**, không phải chunk 0.
9. Backlog mở mới: **BL-07** (lỗi chồng lấn cùng loại ở nhánh pdf2zh), **BL-08** (đo kênh (2)/(3) —
   chữ bị lọc ở `on_lt_char`, kèm ứng viên thiết kế `ILCreater.on_page_end` và điều kiện tiên quyết
   phải đo nhiễu trước), **BL-09** (surfacing finding lên API/UI).

**Điều tôi KHÔNG tự tin đã giải quyết triệt để, nói thẳng thay vì mập mờ** (đây là lượt 2/2 theo
Protocol D, nên phần này là để PM quyết chứ không phải để tôi tự trấn an):

- **F3 chỉ được giải quyết ở vế "trung thực", không ở vế "phủ kín"**. Sau BL-04, mất chữ qua kênh
  (2)/(3) vẫn có thể xảy ra mà không có cảnh báo riêng nào — bằng chứng sống là trang 19/31 của job
  `1ee1fdee`. Tôi đã cân nhắc và **chủ động từ chối** làm counter trong BL-04 (lý do ở BL4.10). Nếu
  Hiếu/PM đánh giá rủi ro "mất tiêu đề chương mà không ai biết" là không chấp nhận được ở mức hiện
  tại, thì **BL-08 phải được ưu tiên ngay sau BL-04**, chứ không phải nằm chờ trong backlog. Đó là
  quyết định về khẩu vị rủi ro, không phải quyết định kỹ thuật — tôi không tự quyết hộ.
- **F1 đúng về logic nhưng chưa được kiểm trên dữ liệu thật** — assertion số 5 của gate E2E (không có
  finding ở trang 199-200) là lần đầu tiên nó được kiểm sống. Trước đó nó vẫn là lập luận.
- `docs/Architecture.md` sau lượt này là **7.911 dòng**, sát trần ngân sách 8.000 của Protocol C.3.
  Lượt sửa tiếp theo chạm §6.22 gần như chắc chắn sẽ vượt trần ⇒ PM nên lên lịch rotate/tách trước,
  đừng để validator cảnh báo rồi mới xử lý.

---

### BL4.15. Sửa theo điều kiện Domain Expert xác nhận lần 2 (X1/X6/X7, kèm cả X2–X5/X8)

**Bối cảnh**: Domain Expert APPROVE thiết kế BL-04 ở lượt **2/2 Protocol D** (note đầy đủ:
`docs/expert-notes/domain-expert-20260911-bl04-babeldoc-overflow.md`, section "Xác nhận lần 2"),
**có điều kiện**. Mục này ghi những gì đã sửa. **Đây KHÔNG phải vòng phản biện mới** — không có
thiết kế nào bị lật, không gọi lại expert (đã dùng hết 2/2 lượt cho checkpoint này). Toàn bộ là
sửa tài liệu; **0 dòng code**.

Tôi **không kế thừa trích dẫn của Domain Expert**: mọi địa chỉ file:line dưới đây đã tự đọc lại
source thật ngày 2026-09-11 (gốc babeldoc 0.6.4:
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`; gốc app:
repo này). Đúng nguyên tắc Domain Expert đã dùng ở lượt 2 — và nó lại có ích: nhờ tự grep tôi thấy
`grep -rn "run_layout_qa_gate" src/` thực ra trả về **1 dòng** (chính định nghĩa hàm), không phải
"0 kết quả" như note ghi; kết luận *dead code, 0 call site* thì đúng, chỉ câu chữ cần chính xác hơn
— đã viết lại theo bản tự đo.

#### X1 (bắt buộc) — `ILCreater` không chạy trong luồng dịch. Sai địa chỉ, đúng kết luận.

**Tự verify lại, khớp 100% với Domain Expert**: `high_level.py:902-910` parse bằng
`new_parser/native_parse.py`, và `native_parse.py:53, 57` dựng sink là **`ActiveILCreater`**
(`document_il/frontend/il_creater_active.py`). `grep -rn "ILCreater\|legacy_parse" <BD>` (bỏ
`ActiveILCreater`): `ILCreater` + `legacy_parse.start_parse_il` chỉ còn **một** người dùng thật là
`format/pdf/parse_only.py:5-6, 29` — entry point tách biệt, không nằm trên đường dịch. Phần còn lại
là khai báo `Protocol` (`pdfinterp.py:50`) và `converter.py`, mà `converter.py` cũng chỉ được
`legacy_parse` dùng.

**Kết luận kỹ thuật của §6.22 KHÔNG đổi** — `ActiveILCreater.project_native_char`
(`il_creater_active.py:1292-1300`) có predicate **y hệt** bản legacy (`aw_font_id is None` → return;
`rotation_angle` ngoài `[-0.1, 0.1] ∪ [89.9, 90.1]` → return). Nghĩa là kênh (2)/(3) vẫn nằm ngoài
tầm đo của §6.22, F2/F3 vẫn đứng. Chỉ **địa chỉ** sai.

Đây đúng là loại sai mà nhìn vào thì thấy vô hại (không bug hôm nay — BL-04 chỉ patch
`pdf_creater`, không đụng frontend) nhưng cái giá nằm ở **tương lai gần**: §6.22.6.1 đã ghi sẵn ứng
viên BL-08 là `ILCreater.on_page_end`. Người nhận BL-08 sẽ tin dòng đó và patch thẳng, được một
**no-op im lặng** — không lỗi, không log, và kết luận ngược hẳn sự thật: *"đo rồi, không ký tự nào
bị lọc"*. Cùng khuôn Bug #9 (hành động theo một trích dẫn không còn đúng ngữ cảnh), khác mỗi chỗ nó
chưa kịp xảy ra. Nên phải sửa **trước** khi Dev/người làm BL-08 bắt đầu.

Đã sửa **6 nhóm trích dẫn** trong §6.22 + **1 ngoài §6.22**:

| Vị trí | Cũ (dead) | Mới (luồng dịch thật) |
|---|---|---|
| §6.22 hộp "Phạm vi" | `ILCreater.on_lt_char` | `ActiveILCreater.project_native_char` |
| §6.22.6 trạng thái 3 | `il_creater.py:1347-1353` | `il_creater_active.py:239-245` |
| §6.22.6.1 kênh (2) | `il_creater.py:972-974` | `il_creater_active.py:1295-1297` |
| §6.22.6.1 kênh (3) | `il_creater.py:969-970` | `il_creater_active.py:1293-1294` |
| §6.22.6.1 bảng bác bỏ | `_collect_valid_char` `il_creater.py:1122-1157` | `il_creater_active.py:1439-1466` |
| §6.22.6.1 ứng viên BL-08 | `ILCreater.on_page_end` `il_creater.py:641-664` | **`ActiveILCreater.on_page_end`** `il_creater_active.py:386-407` (buffer: `:230`, `:384`, clear `:407`) |
| §6.22.7 bảng audit R8-01 | `il_creater.py:972-974` | `il_creater_active.py:1295-1297` |
| **§6.14.6 (ngoài §6.22)**, mục "Pin version" babeldoc (`Architecture.md:3687-3697`) | `il_creater.py:968-974` | `il_creater_active.py:1292-1300` |

Dòng cuối bảng nằm **ngoài** phạm vi việc được giao. Tôi vẫn sửa: đó là **cùng một trích dẫn sai,
cùng một cơ chế hỏng**, và để lại nó thì lần sau ai grep `il_creater.py` vẫn ra một địa chỉ dead
được trình bày như sự thật đã verify. Sửa 1 dòng rẻ hơn nhiều lần giải thích sau này.

Thêm vào §6.22.1 một khối **self-correction R5-05** tường minh (không phải một dòng nhét cuối mục):
ghi rõ luồng dịch dùng `_active`, `ILCreater` chỉ thuộc `parse_only.py`, và **luật**: *mọi trích dẫn
frontend trong §6.22 phải trỏ vào bản `_active`*. Kèm ghi chú **midend KHÔNG bị ảnh hưởng**
(`high_level.py:971` `ParagraphFinder(...).process(docs)`, `:1038` `Typesetting(...)`) để không ai
hoảng đi audit lại patch Bug #7/#10 của shim.

Một điểm nhỏ nhưng đáng ghi: lập luận "patch `on_lt_char` là hàm nóng nhất của parser" ở bảng bác bỏ
vẫn **đúng về bản chất** nhưng sai tên hàm — ở `ActiveILCreater`, `on_lt_char` (`:1423-1427`) chỉ là
**vỏ**, chỗ chạy mỗi ký tự là `project_native_char` (`:1292`). Đã sửa cả tên hàm và ghi rõ "vỏ vs
chỗ thật" ngay dưới bảng kênh, vì đây chính là loại chi tiết khiến người sau patch nhầm chỗ.

⚠️ **Lệch còn lại, cố ý không sửa**: note lượt 1 của Domain Expert
(`docs/expert-notes/domain-expert-20260911-...`, phần trước dòng 430) vẫn mang trích dẫn
`il_creater.py` cũ. Đó là **nhật ký của một vai khác**, R7-03 cấm sửa/ghi đè nội dung cũ, và chính
Domain Expert đã tự ghi nhận lỗi này ở section "Xác nhận lần 2" ngay trong cùng file. Hợp đồng hiện
hành (§6.22) là nguồn phải đúng — và giờ nó đúng.

#### X6 (bắt buộc) — BL-08 không được nằm chờ vô thời hạn

Thêm **§6.22.6.1.a** vào Architecture.md (mục mới, nằm trong hợp đồng chứ không chỉ trong nhật ký —
Protocol C.1), chốt 3 điều:

1. **Quy mô kênh (2) LỚN HƠN kênh (1) mà BL-04 đang vá**: ~976 ký tự dọc mất trên 52/418 trang
   (2.303 → 1.327), **gồm 2 tiêu đề chương thật** (trang 19, 31) — so với 614 ký tự / 1 đoạn của
   kênh (1). Con số này là bằng chứng **mới của lượt 2**, lượt 1 chưa có.
2. BL-04 vẫn đi trước (kênh (1) hiện **không có cơ chế nào**, kênh (2) có overlay phủ một phần),
   nhưng **sau BL-04, BL-08 là hạng mục ưu tiên cao nhất còn lại của mảng mất-chữ**. Xếp **ngay
   sau BL-04**. Đẩy lùi → **phải ghi lý do vào design-log**.
3. Điểm khởi đầu đã có sẵn: `run_layout_qa_gate()` (`src/services/layout_qa.py:386`) chứa
   `_check_rotated_text_prescan()` (`:278-310`) quét **file gốc**, bắt mọi dòng chữ xoay kèm bbox +
   text, có test — nhưng là **dead code**: `grep -rn "run_layout_qa_gate" src/ web/ scripts/` trả về
   đúng **1 dòng, chính định nghĩa hàm**, **0 call site**; người gọi duy nhất là
   `tests/test_layout_qa.py:30`. Đó là lý do **thứ hai** (ngoài "overlay không phủ hết") khiến job
   `1ee1fdee` có 0 row `layout_qa_findings` — bộ dò tồn tại nhưng không nằm trên đường chạy.

Và cảnh báo đi kèm, viết thành **cấm** chứ không phải gợi ý: **không được bật nguyên trạng hàm đó**,
kể cả trong BL-08. Trên cuốn này nó sinh **≥52 finding `blocker`/cuốn** cho *mọi* dòng chữ xoay, kể
cả dòng overlay đã khôi phục thành công — đúng loại báo động giả có hệ thống mà QA sẽ học cách bỏ
qua, tức làm hỏng luôn giá trị của cơ chế. Việc thật của BL-08 là biến *"có chữ xoay"* thành *"chữ
xoay **bị mất**"* (đối chiếu gốc ↔ dịch) rồi mới đặt ngưỡng, **sau khi** đo nhiễu.

(Phần `backlog[]` của `project_state.json` do PM cập nhật — tôi chỉ chịu trách nhiệm phần hợp đồng.)

#### X7 (bắt buộc) — R-2 đếm thiếu khi job resume: đổi sang `SELECT COUNT` trên DB

Đây là điểm tôi **sai rõ ràng**, không phải "cách khác cũng được". Tôi viết R-2 là *"đếm từ list đã
map, **không** query lại DB"* với ý tránh chi phí DB. Ba sự thật (tự đọc lại source, khớp Domain
Expert) làm yêu cầu đó sai hướng:

- `_process_chunk()` trả `None` (`job_orchestrator.py:1733-1743`) ⇒ muốn đếm in-memory phải **thêm
  một accumulator mới**, tức thêm một sợi lineage chỉ để phục vụ một dòng log. Bản thân điều đó đã
  là mùi.
- Vòng Bước 7 (`job_orchestrator.py:576-577`) **bỏ qua** chunk đã xong: `if chunk.status != "completed":`.
- ⇒ Job **resume sau crash**: chunk hoàn tất ở lần chạy trước **đã ghi finding vào DB** nhưng không
  đi qua `_process_chunk()` lần này ⇒ accumulator rỗng cho chúng ⇒ R-2 in con số **nhỏ hơn sự thật**,
  ở đúng kịch bản rủi ro cao nhất.

Vì sao đây là hướng sai **tệ nhất có thể**, không phải sai vặt: theo F4 đã chốt, BL-04 **không** giao
UI/API — R-2 là **mặt hiển thị duy nhất** của cả hạng mục. Một mặt hiển thị duy nhất mà báo ít hơn
sự thật tạo ra **an toàn giả**, đúng hình dạng Bug #5 ("status = completed" nhưng output rỗng). Nếu
phải chọn một hướng sai, phải chọn hướng **báo thừa**.

Đã chọn phương án (i) của Domain Expert: **1 câu `SELECT COUNT(...)`** trên `layout_qa_findings` theo
`job_id` + `check_type LIKE 'babeldoc_%'`, chạy **đúng 1 lần/job** tại Bước 10 ngay trước
`job.status = "completed"` (`job_orchestrator.py:807`). Chi phí thực tế bằng không, và nó dùng
**cùng một nguồn sự thật** với câu SQL R-3 đã giao QA — một nguồn, không hai. Viết shape query thẳng
vào §6.22.6.2 kèm ghi chú Dev cần thêm import `func`/`col` (`job_orchestrator.py:31` hiện chỉ
`from sqlmodel import select`) và `LayoutQaFinding` (`src/models/layout_qa.py:11`).

Giữ lại phương án (ii) làm **đường lùi có kỷ luật**, không phải lựa chọn ngang hàng: nếu Dev không
làm được query, **cấm** giữ nhãn "tổng của job" cho con số của riêng lần chạy — bắt buộc đổi tên
trường thành `unfit_drops_this_run=` + `skipped_completed_chunks=K` **và escalate**. Điều không chấp
nhận được là giữ nguyên câu chữ hứa một đằng giao một nẻo.

Thêm test **11** (`test_r2_counts_from_db_on_resume`) vào §6.22.9: chunk 0 đã completed với 3 finding
sẵn trong DB + chunk 1 sinh 1 finding → R-2 phải báo **4**, không phải 1. Test này là cái khoá: ai
đổi ngược về accumulator thì nó đỏ.

#### X2–X5, X8 (nên sửa) — làm **cả 5**

Không có điểm nào bị bỏ. Lý do làm hết: cả 5 đều là sửa câu chữ/spec, rẻ, và mỗi điểm bỏ lại đều có
một đường dẫn cụ thể tới việc Dev hoặc QA đốt công vô ích.

- **X2** — `_ChunkLike.page_start/page_end` đổi `int` → **`int | None`** cho khớp
  `src/models/chunk.py:23-24` (nullable từ 6.20.7 vì EPUB dùng `unit_start`/`unit_end`), + bắt buộc
  **`raise ValueError` tường minh** khi gặp `None`. Hôm nay chưa có bug runtime (EPUB rẽ sang
  `run_epub_job()` tại `job_orchestrator.py:457`, không đi qua `_process_chunk`/`merge_chunk_pdfs`)
  — nhưng khai `int` là **khai sai sự thật** trong hợp đồng, và `None + 1` nổ `TypeError` ở chỗ khác
  thì mất dấu nguyên nhân.
- **X3** — nói rõ hàm chung sở hữu **đúng quy tắc `start`**; phần kẹp `end` theo
  `chunk_doc.page_count` (`chunk_merge.py:95-107`, 2 nhánh full-document/chunk-scoped của Bug #7 vs
  Bug #8) **ở lại** `chunk_merge.py` vì nó phụ thuộc file thật, hàm thuần không biết được. Thêm bảng
  2 quy tắc + lệnh **giữ nguyên guard `overlap_* is not None`** (bỏ guard = đổi hành vi
  `merge_chunk_pdfs`, trái cam kết "giữ nguyên hành vi"). Viết lại **test 5**: assert `start` trả về
  bằng `actual_start` mà `merge_chunk_pdfs` tính, **không** assert bằng số trang thực sự
  `insert_pdf` vào file merge — hai con số có thể khác nhau một cách **hợp lệ**, và câu chữ cũ dễ
  dẫn QA tới một test đỏ oan.
- **X4** — thêm hẳn 1 dòng vào bảng "Chỉ chạy đúng 1 lần / trang" (§6.22.4): bất biến này còn phụ
  thuộc **`--watermark-output-mode ≠ both`**. Tự verify: `high_level.py:1023-1029` gọi
  `generate_first_page_with_watermark()` khi mode là `Both`, hàm đó dựng **PDFCreater thứ hai** và
  gọi `write()` lần nữa (`:1097-1103`) ⇒ trang đầu mỗi chunk có **2 record `page`**. Hôm nay an toàn
  vì `babeldoc_runner.py:350-351` hardcode `no_watermark`. Giá trị của việc ghi: biến một **phụ
  thuộc tình cờ** thành **ràng buộc có tên** — ai đổi cờ sẽ gặp checksum/trạng thái 3 kêu, nhưng kêu
  **sai nguyên nhân**, và sẽ mất nhiều giờ nếu hợp đồng không nói.
- **X5** — `checksum_mismatch_pages` trước đây **không có chỗ đi** khi `observed == expected`: nó chỉ
  nằm trong `detail` của finding trạng thái 3, mà trạng thái 3 lại chỉ kích hoạt khi thiếu trang. Ca
  đáng lo nhất của checksum là **ngược lại** (đủ trang nhưng một dòng `drop` bị xé ⇒
  `dropped_count=3` mà chỉ có 2 dòng) — khi đó hệ thống rơi về trạng thái 2 với **số finding ít hơn
  sự thật**, đúng loại "giảm âm thầm" mà chính checksum sinh ra để chặn. Đã: mở rộng điều kiện
  trạng thái 3 thành `observed != expected` **HOẶC** `checksum_mismatch_pages` khác rỗng; đổi tên
  trạng thái 3 thành "**KHÔNG TRỌN VẸN**" (thiếu trang *hoặc* lệch checksum); siết điều kiện trạng
  thái 1/2 thành "trọn vẹn"; và đưa `checksum_mismatch=M` vào **định dạng log R-1 bắt buộc** để con
  số không biến mất khỏi mọi mặt hiển thị. Thêm test **12**
  (`test_checksum_mismatch_triggers_incomplete`).
- **X8** — hai chỗ, cả hai đều thuộc loại "không ghi thì QA chạy xong mới biết mình đo nhầm vật":
  (1) thêm **assertion 0 (tiền điều kiện)** `job.chunk_size_used == 40` **và** chunk đang đo có
  `page_start == 199 and page_end == 240`. `chunk_size_used` là **thích ứng**
  (`COLD_START_CHUNK_SIZE = 20` / `WARM_CHUNK_SIZE = 40`, `job_orchestrator.py:112-113`, chọn tại
  `:550-561`); hiện đang warm (`concurrency_state`: `consecutive_successes=95,
  observation_count=133`) nên sẽ ra 40, **nhưng một lần fail đưa `consecutive_successes` về 0** ⇒
  chunk_size 20 ⇒ chunk 5 thành `99-120`, trang 230 rơi sang chunk khác, tập trang đổi ⇒ dính đúng
  cái bẫy mode-scale mà chính §6.22.9 cảnh báo. Một dòng assert cứu trọn một vòng chạy thật (tốn
  tiền dịch thật).
  (2) ghi thẳng **harness**: E2E là **integration test gọi thẳng `_process_chunk()`** với
  `BabeldocRunner` thật + DB thật + `Chunk` thật (`chunk_index=5, page_start=199, page_end=240,
  overlap_start=199, overlap_end=200`) — **không** qua `run_job()`, **không** chạy CLI. Đây là tầng
  duy nhất mà 3 nhóm assertion (runner thật / bộ lọc trong `_process_chunk` / log R-1) **và** lời hứa
  "42 trang thay vì 418" cùng thoả. Kèm tuyên bố **KHÔNG phủ**: log R-2 (nằm ở `run_job()` Bước 10)
  và `merge_chunk_pdfs()` — phải nói ra thay vì để QA tự suy là đã phủ, đó chính là loại im lặng đã
  sinh ra Bug #5.

#### Trạng thái sau BL4.15

- §6.22 **sẵn sàng cho Dev implement**. Không còn mục `⚠️ ASSUMED`/`[UNVERIFIED]` nào trong §6.22.
  Phần "chưa verify" còn lại vẫn đúng như BL4.13 đã nêu và **không đổi**: bản thân cơ chế đo (shim +
  sidecar) chưa chạy end-to-end lần nào — đó là việc của gate E2E.
- **Không có thay đổi code nào** trong lượt này ⇒ không kích hoạt Protocol 7 (Reviewer gate).
- ⚠️ **Ngân sách Protocol C.3 đã VƯỢT**: `docs/Architecture.md` từ 7.911 → **8.105 dòng**, trần là
  8.000. BL4.14 đã dự báo đúng ("lượt sửa tiếp theo chạm §6.22 gần như chắc chắn sẽ vượt trần"). Đây
  là cảnh báo **không chặn**, nhưng Protocol C.3 cấm ngó lơ qua nhiều lượt: PM cần lên lịch
  rotate/tách (ứng viên rõ nhất là tách phần nhật ký còn sót trong §6.22 — các khối "Đính chính
  (…)" — sang design-log, giữ §6.22 là hợp đồng thuần).

---

## BL-10 — Chi phí đo thật cho nhánh PDF/babeldoc (Tech Lead, 2026-09-11)

**Hợp đồng tương ứng: `docs/Architecture.md` §6.23 (mới) + §4.2 bảng `chunks` + §6.6.6/§6.6.7 (cập
nhật cross-ref).** Mục này là *vì sao*, không phải hợp đồng.

### Vấn đề

Từ Increment 1, mọi job PDF báo chi phí bằng `estimate_chunk_cost()` — số học trên độ dài text, sai
số công bố ±30–50% — và `jobs.cost_source` **luôn** `'estimated'`. Sự cố $6.50 (§6.11) đã cho thấy
cái giá của việc không có số thật: RC-4 chính là *"số ước lượng bị báo cáo nhầm là số đo thật"*.
Metering proxy (§6.6.6 v1.1) được thiết kế từ lâu nhưng vẫn hoãn vì phải dựng thêm 1 HTTP server
per-chunk.

### Phát hiện làm đổi bài toán

babeldoc 0.6.4 **đã tự đếm token thật** từ `response.usage` (kể cả `prompt_cache_hit_tokens`) và in
ra stdout 4 dòng tổng kết cuối mỗi tiến trình (`main.py:772-784`). App **đã capture stdout** đó và
đã parse nó 2 lần rồi (`RATE_LIMIT_LINE_RE`, `drop_sentinel_count`). Và vì `_process_chunk()` spawn
**1 subprocess babeldoc cho mỗi chunk**, tổng token in ra ứng 1-1 với chunk — tức là đạt được đúng
thứ metering proxy hứa, **không cần proxy**, chỉ cần 1 regex.

### Những chỗ suýt sai (ghi lại để không ai "đơn giản hoá" lại về sau)

1. **`re.IGNORECASE` là bẫy chết người ở đây.** babeldoc in cả `Prompt tokens:` lẫn `Cache hit
   prompt tokens:`. Bật IGNORECASE thì pattern thứ nhất khớp bên trong dòng thứ hai ⇒ `prompt_tokens`
   nhận nhầm số cache-hit, và sai này **im lặng** (vẫn ra một con số hợp lý). Hợp đồng cấm tường
   minh.
2. **`Term extraction tokens:` KHÔNG được cộng.** `main.py:524` cho `term_extraction_translator =
   translator` khi app không truyền 3 flag `--openai-term-extraction-*` ⇒ token term-extraction đã
   nằm trong `Total tokens`. Cộng thêm = đếm 2 lần. Đây là loại lỗi chỉ lộ ra khi đọc source, không
   lộ ra khi nhìn log.
3. **Brief đề xuất 1 field `real_tokens_used: int`** — tôi đổi thành dataclass 4 số vì giá input ≠
   giá output. Chỉ có `total` thì buộc phải **đoán tỷ lệ split**, tức là nhét một ước lượng vào bên
   trong thứ được dán nhãn `'metered'` — đúng bản chất RC-4 mà §6.11 tồn tại để chặn. Tốn thêm 3
   dòng regex, đổi lại nhãn `metered` không nói dối.
4. **`0` vs `None`.** Cache của babeldoc có thể làm `Total tokens: 0` — đó là **số đo thật** (0 lời
   gọi API), khác hẳn "không parse được". Vì vậy sentinel phải là `None`, không được là `0`. Tiền lệ
   đã có ở §6.20 (`actual_cost=0.0` + `metered`).
5. **`chunks.cost_source` phải là cột thật, không suy từ engine của job.** Một job có thể có chunk
   metered lẫn chunk fallback estimated (parse trượt giữa chừng). Nếu chỉ lưu ở cấp job thì con số
   trộn lẫn sẽ được dán một nhãn duy nhất — lại đúng RC-4. Luật gộp chốt: **trộn ⇒ `'estimated'`**
   (một tổng chứa số ước lượng thì bản thân nó là ước lượng). Không tạo giá trị thứ ba `'partial'`
   vì phải đổi hợp đồng ở 3 tầng để mô tả một trạng thái hiếm.
6. **Nhánh EPUB suýt bị hồi quy ngầm.** EPUB đã `job.cost_source='metered'` từ §6.20 nhưng
   `chunks` chưa có cột này. Nếu chỉ thêm cột với default `'estimated'` mà không ghi cho EPUB, thì
   những chunk **duy nhất trong dự án đã đo thật từ trước** lại mang nhãn ước lượng. Đã đưa 1 dòng
   `chunk.cost_source = "metered"` cho `_process_epub_chunk()` vào spec.

### Audit Protocol 8 (R8-01) — kết quả

Liệt kê đủ 7 bước hiện có trong `_process_chunk()` (§6.23.6). Bước bị audit "bắt" chính là bước
**CŨ**: `estimate_chunk_cost()` tồn tại vì *pdf2zh không xuất token* — lý do đó **không còn đúng với
babeldoc**. Đây đúng khuôn Bug #9 (`font_shrink_page` tồn tại vì pdf2zh vẽ tràn, không đúng với
babeldoc), chỉ khác là lần này bắt được **trước** khi có sự cố. Không bước nào rơi vào "chưa rõ" ⇒
không SKIP thêm bước nào (R8-02). Hiện thực bằng capability `reports_token_usage` trên runner
(R8-03), cùng khuôn `needs_font_shrink` / `reports_own_paragraph_drops`, **kèm guard
`isinstance(bool)`** — không có guard thì `AsyncMock(spec=...)` cho truthy và test chạy nhầm nhánh
mà vẫn PASS.

### Ranh giới bằng chứng

- **Verified trực tiếp phiên này** (đọc source bản đã cài + chạy thật): T1–T11 ở §6.23.1, gồm 1 lần
  dựng lại đúng cấu hình logging của babeldoc (`main.py:918-920`) và capture `repr()` của output
  non-tty để chốt định dạng dòng.
- **⚠️ ASSUMED, đã gắn nhãn trong §6.23.1**: (a) dòng `Total tokens:` xuất hiện trong một lần chạy
  **end-to-end thật qua pipeline app** — chưa chạy (tốn API key/thời gian ngoài phạm vi thiết kế),
  R5-02 giao cho Dev làm spike trước khi viết regex; (b) `total == prompt + completion` với DeepSeek
  — thiết kế **không phụ thuộc** vào đẳng thức này, chỉ log WARNING khi lệch.

### Cố ý KHÔNG làm trong lượt này

- **Không sửa bảng giá** `deepseek_provider.py:17-24` (quyết định của Hiếu). Hệ quả trung thực đã
  ghi thành giới hạn đã biết: `'metered'` ở vòng này nghĩa là *"token là số đo thật"*, **không**
  nghĩa *"số tiền chắc chắn đúng"*.
- **Không chiết khấu cache-hit** (đã parse, chưa dùng) ⇒ tính cao hơn thực tế — chiều sai an toàn
  theo §6.11.6.
- **Không đếm token của attempt retry thất bại** ⇒ metered là under-count khi có retry. Ghi rõ thay
  vì để QA tự phát hiện rồi báo là bug.
- Không đưa token vào `BabeldocError`/`BabeldocTimeoutError`: chunk fail không có `api_cost` để ghi.

### Trạng thái

- §6.23 **chưa implement** — chờ Human Checkpoint 2. Không có thay đổi code nào trong lượt này ⇒
  không kích hoạt Protocol 7.
- ⚠️ **Ngân sách Protocol C.3 tiếp tục vượt**: `Architecture.md` 8.105 → **8.477 dòng** (trần
  8.000). §6.23 được viết ở dạng hợp đồng thuần (phần "vì sao" nằm ở chính mục này của design-log),
  nhưng tổng vẫn tăng. PM cần lên lịch rotate như BL4.15 đã nêu.

---

## Bug #EPUB-5 — koboSpan KHÔNG phải nguyên nhân runaway; nguyên nhân thật là phép đo (Tech Lead, 2026-09-11)

**Hợp đồng tương ứng**: `docs/Architecture.md` §6.20.15 (K-1..K-5), cùng 2 sửa tại chỗ ở §6.20.6
(hộp "⚠️ SỬA 2026-09-11") và §6.20.13.3b (hộp "⚠️ ĐÃ ĐO").

### 1. Giả thuyết được giao — và kết quả: BỊ BÁC BỎ

Brief của PM nêu giả thuyết (đã tự gắn nhãn `[CHƯA VERIFY]`, đúng Protocol 1 mở rộng): file EPUB
export từ Kobo có markup `koboSpan` dày đặc; pipeline gửi nguyên inner-HTML cho LLM nên payload thật
lớn hơn nhiều budget đo bằng `_plain_char_len()`, và đó là nguyên nhân runaway.

**Hai nửa của giả thuyết có số phận khác nhau:**

| Nửa | Kết luận |
|---|---|
| "Payload gửi đi chứa nguyên koboSpan, budget lại đo bằng text thuần" | **ĐÚNG, đã verify** (`job_orchestrator.py:2372` + `epub_document.py:786` + `chunking.py:268`) |
| "…và đó là nguyên nhân runaway" | **SAI — bị bác bỏ bằng test đối chứng** |

### 2. Test đối chứng đã bác bỏ giả thuyết

3 job EPUB đều `failed` vì R-b, cùng provider `deepseek-v4-flash`:

| Job | Sách | koboSpan | inner-HTML / text thuần | % request bị gắn runaway | max ratio |
|---|---|---|---|---|---|
| `781b59b0` | Sourdough Culture (Kobo) | **1.963/1.963 unit**, 7.616 thẻ | **2,29×** | **68,2%** (45/66) | 7,57× |
| `88e897af` | Sourdough Discard Recipes | **0** | 1,14× | 63,2% (148/234) | 25,57× |
| `f21c1555` | Sourdough by Science | **0** | 1,21× | 67,2% (334/497) | 32,21× |

Hai cuốn **không có một thẻ koboSpan nào**, markup ratio sát đúng giả định `1.15`, vẫn runaway với
tỉ lệ **không phân biệt được** với cuốn Kobo — và **đuôi phân bố còn tệ hơn nhiều** (p99 ~20× vs
7,6×). Cuốn Kobo thực ra là cuốn *nhẹ* nhất, vì `payload_chars` phình lên nằm ở **mẫu số** của
`runaway_ratio` nên markup rác lại **che bớt** triệu chứng.

Nếu chỉ nhìn 1 job (đúng như brief ban đầu) thì tương quan trông hoàn hảo. Đây là ca sách giáo khoa
"correlation ≠ causation" mà R5-01 tồn tại để chặn: **giả thuyết trông rất thuyết phục, nhưng nhóm
đối chứng đã nằm sẵn trong `data/processing/` và chưa ai mở ra**.

### 3. Nguyên nhân thật

`epub_expected_output_tokens(payload_chars) = payload_chars × 1,16 / 2,0` mô hình hoá **số token của
bản dịch tiếng Việt**. Còn `output_tokens` mà nó bị đem so sánh là
`response.usage.completion_tokens` (`openai_provider.py:116`).

`deepseek-v4-flash` **bật thinking mặc định, effort mặc định `high`** (doc chính thức đã fetch:
<https://api-docs.deepseek.com/guides/thinking_mode/> — *"Thinking mode is enabled by default, with
the default effort being `high`"*). App **không** truyền tham số tắt, và chỉ đọc
`message.content` (bỏ `reasoning_content`). Nên `completion_tokens` ≈ *token thinking + token trả
lời*, trong khi công thức chỉ mô hình hoá vế sau.

**Bằng chứng định lượng độc lập** (không dựa vào doc): ghép `units.json` (bản dịch thật đã nhận) với
`requests.jsonl` (token thật) trên 55 chunk / 3 sách cho **0,23–0,66 ký tự trả về / 1 output token**,
median ~**0,32**. Tiếng Việt NFC tệ nhất cũng chỉ ~3 byte/ký tự, nên ngay cả tokenizer byte-fallback
thuần cũng không thể xuống dưới ~0,33 — và con số 0,25 quan sát được nằm **dưới** giới hạn vật lý đó.
Kết luận: phần lớn `completion_tokens` **không phải nội dung trả về**. Khớp chính xác với S6.

Đối chiếu thêm: `max_tokens = 8192`, max quan sát = **8.099**, **0 request** chạm trần ⇒ không có
truncation. Các response "runaway" không hề bị cắt cụt — chúng chỉ *được đo sai*.

### 4. Vì sao lỗi này giết job (cơ chế, không phải triệu chứng)

`job_orchestrator.py:2398` — `if runaway and missing_ids: raise EpubRequestRunawayError`. Nhánh này
đứng **TRƯỚC** toàn bộ thang cứu hộ (C-1 retry từng-id `:2452`, retry nguyên request `:2470`, Lớp B
salvage, Lớp C fallback).

Với `runaway` gần như luôn `True` (65,4% request, và 100% các request lớn), R-b thoái hoá thành
**"abort cả chunk khi thiếu BẤT KỲ id nào"**. Mọi lớp dung sai xây suốt §6.20.14 (Lớp A/B/C, 3 vòng
Protocol 3, Bug #EPUB-B2-1…B2-5) trở thành **code chết cho provider này** — chúng chưa bao giờ có
cơ hội chạy. Đó là lý do 4/7 chunk của job `781b` phải retry thủ công nhiều lần mới qua: mỗi lần là
một lần R-b bắn nhầm, không phải một lần model hỏng thật.

### 5. Điều §6.20.13.3b đã tự dự đoán — và không ai quay lại kiểm

Chính §6.20.13.3b (viết 2026-09-09) đã ghi: *"Nếu max ratio thật của lần chạy lành mạnh > 1,5 →
ngưỡng 3,0 quá sát, phải nâng và ghi lại. Đây chính là bước 'đo thêm trước khi tự tin vào con số'
của R5-02."* Log `requests.jsonl` đã được implement đúng như yêu cầu và **đã chứa sẵn dữ liệu bác bỏ
ngưỡng** từ lần chạy live đầu tiên. Bước "đọc lại log rồi cập nhật hằng số" thì không có ai sở hữu:
nó không phải task của Dev (đã code xong), không phải của QA (job `failed`, không tới mục đo), không
phải của Tech Lead (không được dispatch lại).

**Bài học quy trình**: một chỉ thị dạng *"lần chạy live đầu tiên phải đo X rồi hiệu chỉnh"* đặt trong
Architecture.md **không có chủ sở hữu** thì không bao giờ được thực thi. Nó cần là một mục
`backlog[]`/`open_questions[]` trong `project_state.json` có người chịu trách nhiệm, hoặc một
assertion trong code (như K-4 đã làm cho `EPUB_INLINE_MARKUP_FACTOR`). Đề xuất PM đưa vào backlog
như một luật chung, không chỉ cho ca này.

### 6. Vì sao K-1 (bóc koboSpan) vẫn đáng làm, dù không sửa được bug

Không phải để sửa runaway — mà vì nó là **một lỗi thật khác, độc lập**:

- `EPUB_INLINE_MARKUP_FACTOR = 1.15` (chốt tại §6.20.6 FD X5(b), đo trên **đúng 1 cuốn**) bị cuốn
  Kobo làm sai **2×** ⇒ cost gate ước **thấp** ⇒ vi phạm §6.11.6 ("được ước cao, CẤM ước thấp") ở
  đúng lớp bảo vệ tài chính. Đây là cùng khuôn lỗi mà FD X5(b) từng bắt Expert vì ước thấp 9% — lần
  này là 100%.
- **50,5% payload là rác**, trả tiền cả chiều vào lẫn chiều ra (model tái tạo y hệt koboSpan trong
  bản dịch — xem `units.json` chunk_0).
- Bóc xong đưa tỉ lệ về **1,13×**, tức **khôi phục tính đúng đắn của hằng số 1.15 hiện có** thay vì
  phải nâng nó lên 2,3 cho mọi EPUB (nâng như thế sẽ ước cao vô lý cho 2 cuốn còn lại).

### 7. Điểm suýt sai khi thiết kế K-1 (ghi lại để không tái diễn)

Phản xạ đầu tiên là bóc markup ở **chỗ build payload** (`job_orchestrator.py:2372`) — nơi vấn đề lộ
ra. Đó sẽ là một Bug #5 mới: `write_translated()` mở **lại zip gốc** và đếm "slot" text trên node
**chưa bóc** (`_apply_translation_untrusted_structure` → `_text_runs_under`), còn bản dịch trả về đã
sạch span ⇒ lệch số slot ⇒ rơi vào nhánh *"Known limitation"*, dồn hết bản dịch vào slot dài nhất và
**giữ nguyên tiếng Anh** ở các slot còn lại. Đo thật: **85/1.963 unit** đi qua nhánh untrusted,
**64** trong đó multi-slot ⇒ 64 unit dịch sót *âm thầm* (BR-EPUB-05 vẫn pass vì 64/1963 = 3,3% < khe
hở 10%).

Đặt phép bóc ở `_parse_xhtml()` — điểm vào **duy nhất** dùng chung bởi `load()`,
`write_translated()`, `count_bb_vi_pairs()`, `to_markdown()` — làm cả 4 đường đọc cùng nhìn một cây.
Số slot/unit giảm từ median 4,0 (max 16) xuống median 1,0 (max 12) ⇒ nhánh rủi ro *an toàn hơn*
hiện trạng. Đây đúng tinh thần R6-01: chọn chỗ sửa theo **lineage**, không theo chỗ triệu chứng lộ ra.

Đã kiểm 0/7.616 `id="kobo.*"` được `href`/`idref`/`src` nào tham chiếu ⇒ bóc an toàn, không phá
`page-list`/nav. Giữ nguyên `<span epub:type="pagebreak">` (khác class, **id của nó CÓ được tham
chiếu**).

### 8. Cố ý KHÔNG làm trong lượt này

- **Không sửa `CHARS_PER_TOKEN_VI` ngay**, dù đã biết nó sai ~6×: số đo hiện tại nhiễm token
  thinking. Hiệu chỉnh bây giờ = khoá cứng cái sai vào hằng số. Xếp thành K-4, sau K-2/K-3 (R8-02
  deny-by-default áp cho chính con số).
- **Không nâng `EPUB_RUNAWAY_OUTPUT_FACTOR`** — nâng ngưỡng là chữa triệu chứng của một phép đo sai
  đơn vị. Sửa tử số (`answer_tokens`) trước, đo lại, rồi mới bàn ngưỡng.
- **Không tổng quát hoá K-1 thành "bóc mọi span rỗng nghĩa"** — chưa đo trên EPUB khác, R8-02.
- **Không đổi signature `provider.translate()`** — ràng buộc kiến trúc từ X4 (§6.20.12), 5 provider
  dùng chung. K-3 hiện thực bằng capability trên class (R8-03), không rẽ nhánh theo tên provider.
- **Không tự chạy job lại để xác minh** — phạm vi lượt này là thiết kế; và spike K-2 phải do Dev làm
  theo R5-02 (capture golden file), không phải Tech Lead làm hộ rồi mô tả lại.

### 9. Trạng thái

- §6.20.15 **chưa implement**. K-2/K-3 mang nhãn ⚠️ ASSUMED ⇒ **chặn Dev implement đúng 2 mục đó**
  cho tới khi spike R5-02 xong; K-1 và K-5 **không** bị chặn.
- Không có thay đổi code nào trong lượt này ⇒ không kích hoạt Protocol 7.
- ⚠️ **Ngân sách Protocol C.3 tiếp tục vượt**: `Architecture.md` 8.477 → ~8.640 dòng (trần 8.000);
  `design-log.md` 6.413 → ~6.520 (trần 8.000). Phần "vì sao" đã dồn hết sang design-log, nhưng
  Architecture.md vẫn tăng. PM cần lên lịch rotate.

---

## Final Decision: Hiếu trả lời HOI-04/HOI-05 (Bug #EPUB-5) — 2026-09-11

**Hợp đồng tương ứng**: `docs/Architecture.md` §6.20.15 (bảng "Trạng thái quyết định", K-1, K-3).
RCA đầy đủ: mục *"Bug #EPUB-5 — koboSpan KHÔNG phải nguyên nhân runaway; nguyên nhân thật là phép
đo (Tech Lead, 2026-09-11)"* ngay phía trên.

Theo Protocol B (CLARIFY trước, WRITE sau) — 2 câu hỏi do Tech Lead nêu sau khi điều tra Bug
#EPUB-5, PM gộp hỏi một lượt (`open_questions[]` HOI-04/HOI-05), Hiếu trả lời trực tiếp qua
`AskUserQuestion` trong chat 2026-09-11. **Cả hai đều trùng với mặc định đề xuất.**

### HOI-04 — Tắt thinking mode của DeepSeek cho nhánh EPUB (K-3)

*Câu hỏi*: tắt thinking mode của `deepseek-v4-flash` cho nhánh EPUB
(`Settings.epub_disable_thinking = True`, §6.20.15 K-3) để `output_tokens` không còn lẫn token suy
luận gây runaway giả?

*Trả lời*: **TẮT thinking cho nhánh EPUB** (= mặc định đề xuất). Hiếu chấp nhận đánh đổi đã nêu:
chi phí output giảm mạnh, chất lượng dịch **câu khó** có thể giảm nhẹ. Cơ sở: dịch câu là tác vụ
không cần CoT, còn effort `high` mặc định (S6, doc chính thức DeepSeek đã fetch) đang chiếm phần
lớn chi phí output và là nguyên nhân trực tiếp làm R-b abort nhầm 65,4% request.

### HOI-05 — Chấp nhận bóc `id="kobo.*"` khỏi output EPUB (K-1)

*Câu hỏi*: chấp nhận việc unwrap `koboSpan` làm biến mất `id="kobo.*"` trong file EPUB đầu ra?
Hệ quả đã đo: **0/7.616** id được `href`/`idref`/`src` nào tham chiếu (S8), chỉ ảnh hưởng tính năng
phân trang lại của riêng máy đọc Kobo.

*Trả lời*: **CHẤP NHẬN bóc** (= mặc định đề xuất). Không id nào bị tham chiếu ⇒ không phá
`nav`/`ncx`/`page-list`, không vi phạm BR-EPUB-01; đổi lại bỏ được **50,5% payload rác** và khôi
phục tính đúng đắn của `EPUB_INLINE_MARKUP_FACTOR = 1.15` thay vì phải nâng hằng số này lên 2,3 cho
mọi EPUB (nâng như vậy sẽ ước cao vô lý cho 2 cuốn không-Kobo).

### Ranh giới của 2 quyết định này — điểm QUAN TRỌNG nhất của mục này

Quyết định của Hiếu là **"làm cái gì"** (chấp nhận đánh đổi nghiệp vụ), **KHÔNG PHẢI** "đã verify
cơ chế kỹ thuật hoạt động đúng như mô tả". Cụ thể:

| Mục | Được duyệt phần nào | Vẫn ⚠️ ASSUMED phần nào |
|---|---|---|
| K-1 | Toàn bộ (hướng + hệ quả mất id) | — (mọi claim có nguồn xác thực S1–S4, S8) |
| K-2 | Không hỏi Hiếu (quyết định kỹ thuật thuần) | `usage.completion_tokens_details.reasoning_tokens` có mặt & khác 0 trên response sống |
| K-3 | **Hướng**: tắt thinking, `epub_disable_thinking=True` mặc định | **Cơ chế**: `extra_body={"thinking": {"type": "disabled"}}` được endpoint DeepSeek chấp nhận (không 400) |

⇒ **R5-02 vẫn chặn Dev implement K-2 và K-3** cho tới khi spike xong (gọi thật 1 request EPUB, in
`response.usage.model_dump()`, lưu golden file `tests/fixtures/epub_llm/deepseek_v4flash_usage.json`
theo R5-03). Không được gỡ nhãn ⚠️ ASSUMED chỉ vì hướng xử lý đã được duyệt — đây đúng là loại
nhầm lẫn "đã quyết = đã verify" mà Protocol 5 tồn tại để chặn.

### Hệ quả

- §6.20.15 được cập nhật tại chỗ: thêm bảng "Trạng thái quyết định", đánh dấu K-1/K-3 **ĐÃ CHỐT**,
  giữ nguyên toàn bộ nội dung kỹ thuật và **giữ nguyên** 2 hộp ⚠️ ASSUMED ở K-2/K-3.
- Thứ tự implement (§6.20.15 *"Thứ tự implement bắt buộc"*) **không đổi**: spike → K-5 → K-2 → K-3
  → chạy live 1 cuốn → K-1 (song song được) → K-4.
- Không có thay đổi code nào trong lượt này ⇒ không kích hoạt Protocol 7.
- HOI-06 (luật quy trình "chỉ thị ⚠️ ASSUMED phải có mục `backlog[]` kèm owner") cũng đã được Hiếu
  chốt cùng lượt, nhưng PM ghi trực tiếp vào `CLAUDE.md` project (R5-06) — không thuộc phạm vi
  thiết kế kỹ thuật của mục này.

## Bug #EPUB-5 — K-1..K-5 implement + live E2E (2026-09-11, Dev) — phát hiện MỚI, chưa fix: guard OCF `mimetype ZIP_STORED` fail trên EPUB thật

Sau khi implement K-5 → K-2 → K-3 (theo đúng thứ tự bắt buộc, spike R5-02 xanh cả 2 câu — xem
`tests/fixtures/epub_llm/deepseek_v4flash_usage.json`), chạy live E2E job thật
(`bfc0ac24-0664-4932-96da-1ac99c1abc10`) trên `Sourdough Culture...epub` (66 chunk, KHÔNG kèm K-1):
**66/66 chunk `completed`, 784 request, 0 abort vì R-b, 0/784 request rò rỉ `reasoning_tokens`**
(K-3 hoạt động đúng trên toàn bộ sách thật) — gate G-2 (Architecture.md §6.20.15) đạt cho chính
phần dịch. Số đo đầy đủ (`chars_per_answer_token`, `runaway_ratio`) đã ghi vào §6.20.15 mục K-4.

**Phát hiện MỚI, KHÔNG thuộc phạm vi Bug #EPUB-5, KHÔNG được fix trong lượt này**: job cuối cùng
báo `status="failed"` ở bước MERGE (sau khi cả 66 chunk đã dịch xong), lỗi:
`"'<path>...epub': entry 'mimetype' khong o dang ZIP_STORED"` — đây là 1 guard OCF-compliance CÓ
SẴN TỪ TRƯỚC trong `EpubDocument.write_translated()` (`src/services/epub_document.py`), kiểm
`infolist[0].compress_type == zipfile.ZIP_STORED`. Verify trực tiếp: file nguồn
`data/uploads/4a752f64-...Sourdough Culture...epub` có entry `mimetype` với
`compress_type=8` (`ZIP_DEFLATED`), KHÔNG phải `0` (`ZIP_STORED`) — vi phạm OCF spec (đa số trình
đọc EPUB bỏ qua vi phạm này, nhưng app hiện từ chối ghi đè lên file không tuân thủ). Bug này tồn
tại ĐỘC LẬP với K-1..K-5 (không do đợt sửa này gây ra — guard này có từ trước), chỉ mới LỘ RA vì đây
là lần đầu tiên 1 job EPUB thật chạy hết toàn bộ 66 chunk tới bước merge mà không bị Bug #EPUB-5
chặn giữa chừng. Không sửa ở đây (ngoài phạm vi brief S4) — báo lại PM/Tech Lead để quyết định có
nên nới guard này (chấp nhận EPUB có `mimetype` compressed nhưng vẫn well-formed OCF về mặt khác)
hay giữ nguyên strict và coi đây là giới hạn đã biết.

---

## S5 — Verify claim "browser tự nhớ thư mục tải lần trước" (Tech Lead, 2026-09-12)

Hiếu chọn phương án "không code logic mới" cho yêu cầu chọn thư mục tải: chỉ thêm UI hint, để browser
lo phần chọn + nhớ thư mục. PM đưa claim "bật tuỳ chọn hỏi-nơi-lưu thì browser sẽ nhớ thư mục lần
trước" vào brief mà chưa verify → Protocol 5 R5-01 buộc Tech Lead verify trước khi nó lan xuống Dev.

Kết quả: claim **ĐÚNG cho cả Chrome và Firefox**, verify bằng source thật (không phải kiến thức chung,
cũng không phải forum — kết quả WebSearch ban đầu chỉ trả về forum/blog, không đủ theo R5-01):
- Chromium `download_target_determiner.cc:333-336` (chọn thư mục khởi tạo = `SaveFilePath()`, kèm
  comment "always prefer the last directory that the user selected") và `:757` (ghi lại thư mục vừa chọn).
  Đáng chú ý: `DownloadFilePicker::FileSelected` KHÔNG ghi pref — việc ghi nằm ở target determiner, nên
  tra nhầm file sẽ ra kết luận ngược ("Chrome không nhớ").
- Firefox `HelperAppDlg.sys.mjs:356-365` + `:399`; `DownloadLastDir.sys.mjs:86-91` cho thấy
  `browser.download.lastDir.savePerSite` mặc định `true` → nhớ **theo site**, không phải toàn cục.

Điểm phải cẩn thận trong wording: (a) nhãn Firefox đã đổi thành "Ask where to save files before
downloading" (`preferences.ftl:617-618`), wording cũ "Always ask you where to save files" là sai với bản
hiện tại; (b) private/incognito không lưu lastDir (`DownloadLastDir.sys.mjs:54-61`) → hint không được
hứa tuyệt đối. Hợp đồng ghi tại Architecture.md §6.24.

---

## BL-12 — RCA: job EPUB thật fail ở bước MERGE CUỐI vì guard OCF `mimetype ZIP_STORED` (Tech Lead, 2026-09-16)

Hợp đồng kết quả: **Architecture.md §6.25** (đọc ở đó nếu chỉ cần biết hệ thống PHẢI làm gì).
Mục này là nhật ký: bằng chứng, phản biện, quyết định.

### 1. Hiện tượng

Job `bfc0ac24-0664-4932-96da-1ac99c1abc10` (`Sourdough Culture …epub`, 66 chunk, 784 request,
$0,588) dịch **thành công 66/66 chunk** — gate G-2 §6.20.15 đạt, xác nhận Bug #EPUB-5 đã hết — rồi
`status="failed"` ở bước cuối với `error_message`:

```
'<path>…Sourdough Culture….epub': entry 'mimetype' khong o dang ZIP_STORED
```

Tiền đã trả, không có file output. Job `781b59b0` của Hiếu bị chặn theo.

### 2. Truy vết — "bước MERGE CUỐI" nằm ở đâu

- `src/core/job_orchestrator.py:1412-1424` — `merged_path = self._output_dir / job.id / "translated_vi.epub"`,
  rồi `doc.write_translated(translations, merged_path, …)`, bọc trong `try/except Exception` →
  `job.status = "failed"; job.error_message = str(exc)` (`:1425-1431`). Đây là nơi lỗi trồi lên.
- Chỗ raise thật: `src/services/epub_document.py:984-991`, **bên trong** `write_translated()`:

```python
infolist = src_zf.infolist()
if not infolist or infolist[0].filename != "mimetype":
    raise EpubParseError(...)                       # :985-989
if infolist[0].compress_type != zipfile.ZIP_STORED:
    raise EpubParseError(f"'{self.path}': entry 'mimetype' khong o dang ZIP_STORED")  # :990-991
```

Nguồn gốc guard: commit `b5dad5e` *"US-22 EPUB — Bước 1/3: EpubDocument parser"*
(`git log -S "khong o dang ZIP_STORED"`) — tức guard **có từ trước** Bug #EPUB-5, không do đợt
K-1..K-5 sinh ra. Nó chỉ chưa bao giờ chạy tới vì trước đó chưa job EPUB thật nào đi hết 66 chunk.

### 3. Root cause — HAI lỗi chồng lên nhau, phải tách bạch

**(a) Lỗi ở dữ liệu vào (có thật, đã verify trực tiếp)**: file nguồn
`data/uploads/4a752f64-…_Sourdough Culture … (z-library.sk, 1lib.sk, z-lib.sk).epub` có entry
`mimetype` **là entry đầu tiên, nội dung đúng `b"application/epub+zip"`, nhưng bị nén DEFLATED**.
Đọc thẳng byte local header: `PK\x03\x04`, `method = 8`, `extra len = 0`, `name = b"mimetype"`;
`infolist()[0].compress_type = 8`, `file_size = 20`, `compress_size = 22` — *nén xong to hơn bản gốc
2 byte*, minh hoạ đúng vì sao OCF bắt STORED. Toàn bộ 63/63 entry đều DEFLATED ⇒ file đã bị re-zip
lại bằng công cụ không biết luật OCF. Vi phạm đúng 1 trong 3 câu MUST của EPUB 3.3 §4.3
(fetch thật, trích nguyên văn ở Architecture.md §6.25.1).

**(b) Lỗi ở thiết kế của chính app (đây mới là root cause thực sự của BL-12)**: app đặt một kiểm
tra thuộc về **chất lượng file OUTPUT** vào đúng bước cuối cùng, dưới dạng **reject** thay vì
**repair**, và **sau** toàn bộ chi phí LLM. Ba sai lầm ghép lại:

1. **Sai chỗ**: `load()` (chạy ở pre-flight cost estimate, `job_orchestrator.py:1143` và
   `cost_gate.py:167`) KHÔNG kiểm gì về `mimetype`; chỉ `write_translated()` kiểm. Tức điều kiện
   tiên quyết để job có thể hoàn tất lại được kiểm ở *bước cuối cùng*. Không có lý do kỹ thuật nào
   — thông tin cần kiểm (`infolist()[0]`) đã sẵn sàng ngay giây đầu tiên mở file.
2. **Sai hành động**: app tự ghi zip output bằng `zipfile`, tức **tự quyết định** thứ tự entry và
   `compress_type` của output. Nó hoàn toàn có thể ép `mimetype` lên đầu + STORED và tạo ra file
   output *tuân thủ hơn cả input*. Từ chối làm việc chỉ vì input không tuân thủ là nhầm lẫn giữa
   "hợp đồng của file tôi ghi ra" và "điều kiện nhập học của file tôi đọc vào".
3. **Sai mức nghiêm khắc**: chính `ebooklib 0.20.0` mà app đang dùng để ĐỌC file đó **đọc được bình
   thường** (`epub.read_epub(<file vi phạm>)` → `spine = 22`). App nghiêm khắc hơn thư viện đọc của
   chính nó, trong khi phần nghiêm khắc đó không mua lại được lợi ích nào cho output.

### 4. Phản biện các phương án (và vì sao loại)

| Phương án | Loại/chọn | Lý do |
|---|---|---|
| **A. Nới guard**: bỏ hẳn 2 nhánh kiểm, ghi output với `compress_type` copy y nguyên input | **LOẠI** | Input DEFLATED ⇒ output cũng DEFLATED (dòng `new_info.compress_type = info.compress_type`, `:1001`) ⇒ app **sinh ra** file vi phạm OCF. Đổi 1 lỗi ồn ào lấy 1 lỗi im lặng |
| **B. Giữ strict, coi là giới hạn đã biết**, báo lỗi rõ hơn | **LOẠI** | Vẫn fail sau khi đã tiêu $0,588. Và "giới hạn đã biết" ở đây nghĩa là từ chối cả một lớp nguồn file phổ biến (z-library/Kobo) vì 20 byte metadata |
| **C. Chuẩn hoá (re-zip) file gốc tại chỗ trong `data/uploads/` trước khi dịch** | **LOẠI** | Sửa file gốc của user = mất bản gốc, khó rollback, và đụng file đang được job/batch khác tham chiếu. Không cần: app đã ghi file mới ở bước merge rồi |
| **D. Normalize khi GHI output + chỉ reject sớm thứ không sửa được** | **CHỌN** | Xem §6.25.2. Output luôn hợp lệ OCF; input vi phạm kiểu sửa được thì sửa; input hỏng kiểu không sửa được (thiếu `mimetype`/sai nội dung) reject ở `load()` ⇒ HTTP 400 **trước** cost gate (`api/routes/jobs.py:376-380` đã map sẵn) |

Ranh giới "sửa được / không sửa được" theo **deny-by-default (R8-02)**: app ĐƯỢC sửa thứ nó tự
quyết định được (thứ tự entry, `compress_type`, extra field); KHÔNG được **chế ra** entry `mimetype`
khi file thiếu hẳn — đó là đoán media-type thay user, và một file zip không có `mimetype` rất có
thể không phải EPUB.

### 5. Spike verify (không suy đoán — R5-01/R5-02)

Chạy thật trên CPython 3.14.7 của `.venv`:

1. Re-zip file vi phạm, ép `mimetype` → `ZIP_STORED`, giữ nguyên thứ tự + `compress_type` 62 entry
   còn lại ⇒ `zipfile.testzip() is None`; `unzip -lv` báo `20 Stored 20 0% … mimetype`; local header
   `method = 0`, `extra len = 0`; `ebooklib.epub.read_epub()` đọc lại đúng `spine = 22`.
2. Đọc source `zipfile` bản đã cài: `_open_to_write()` gán **đè** `zinfo.flag_bits = _MASK_UTF_FILENAME`
   vô điều kiện (`zipfile/__init__.py:1824`), và `writestr()` luôn đi qua `open(zinfo, "w")`
   (`:2037-2038`) ⇒ dòng `new_info.flag_bits = info.flag_bits` (`epub_document.py:1005`) là **dead
   code**. Phát hiện phụ, nhưng đáng xoá: nó tạo ảo giác đang bảo toàn cờ zip của input, trong khi
   nếu Python *có* tôn trọng nó thì việc copy bit 3 (data descriptor) từ 1 input lạ sẽ sinh zip lệch.

### 6. Phạm vi — chung, không cá biệt

8 EPUB thật trong `data/uploads/`: **1 vi phạm (12,5%)**, đúng file của job `bfc0ac24` (bảng đo ở
§6.25.5). File vi phạm mang dấu vết Kobo (`META-INF/com.kobobooks.display-options.xml`, markup
`koboSpan` — cùng file đã dẫn tới K-1 ở §6.20). Nguồn sách qua đường z-library/Kobo bị re-zip toàn
bộ là chuyện thường ⇒ **chắc chắn tái diễn**. Đây không phải sự cố 1 lần.

### 7. Thiệt hại không thu hồi được

Job `bfc0ac24` và `781b59b0` **đã bị xoá khỏi DB** (`select count(*) from jobs/chunks where id like
'bfc0ac24%'` → `0`/`0`; không còn `data/processing/bfc0ac24*`). Cơ chế resume BR-CHUNK-05
(`job_orchestrator.py:1383-1391`, chỉ tái dùng chunk `status="completed"` **còn `output_path`**)
KHÔNG cứu được nữa ⇒ chạy lại sẽ **trả tiền lần hai** (~$0,6/cuốn). Đây là lý do BL-12 phải sửa
theo hướng *fail sớm*, không chỉ *fail rõ ràng hơn*.

### 8. Việc chưa làm / còn treo

- ⚠️ **[UNVERIFIED]** hành vi reading system thật (Apple Books, Calibre, Kobo, Kindle Previewer)
  với `mimetype` bị nén — chưa đo. Không chặn thiết kế (§6.25.2 làm output luôn tuân thủ), nhưng
  chặn mọi claim kiểu "reader nào cũng bỏ qua vi phạm này". Chưa cài `epubcheck` (`which epubcheck`
  → không có) ⇒ chưa có kiểm định OCF độc lập cho output của app. Đề xuất thành backlog riêng.
- Chưa implement — cần Hiếu chốt 2 câu CLARIFY dưới đây trước (Protocol B).

### 9. CLARIFY cho Hiếu (Protocol B — hỏi 1 lượt, đã có mặc định đề xuất)

- **BL-12-Q1** — chọn phương án D (normalize khi ghi + reject sớm) hay giữ strict (B)?
  *Phát sinh từ*: §4 bảng phương án. *Chặn*: toàn bộ implement BL-12 ⇒ chặn `ready_for_release`
  của S4. **Mặc định đề xuất: D.**
- **BL-12-Q2** — với EPUB **thiếu hẳn** `mimetype` hoặc nội dung khác `application/epub+zip`: reject
  sớm (HTTP 400) hay tự chế entry `mimetype` chuẩn rồi dịch tiếp? *Phát sinh từ*: ranh giới
  sửa-được/không-sửa-được ở §4. *Chặn*: nhánh L1 của §6.25.2. **Mặc định đề xuất: reject sớm**
  (deny-by-default R8-02).

### 10. Final Decision (Hiếu, 2026-09-16, qua PM/AskUserQuestion)

- **BL-12-Q1: chọn Phương án D** (= mặc định) — normalize `mimetype` → `ZIP_STORED` khi GHI output;
  chỉ reject sớm ở `load()` thứ không sửa được.
- **BL-12-Q2: reject sớm** (= mặc định) khi EPUB thiếu hẳn `mimetype`/sai content-type — không tự
  chế entry.

Cả 2 câu chọn đúng mặc định Tech Lead đề xuất ⇒ không cần viết lại §6.25 của Architecture.md. Dev
implement thẳng theo §6.25 + Final Decision này. Backlog mới cần thêm (theo mục 8 ở trên, R5-06):
đo hành vi reading system thật (Apple Books/Calibre/Kobo/Kindle Previewer) với `mimetype` bị nén +
cài `epubcheck` để kiểm định output — chưa có owner, PM thêm vào `backlog[]`.

---

## S7 — Dịch FR→VI (thiết kế, Tech Lead, 2026-09-16)

Hợp đồng hiện hành nằm ở `docs/Architecture.md` **§6.26** (§6.26.1–6.26.9). Mục này chỉ ghi *vì sao*
tới được thiết kế đó — không lặp lại nội dung hợp đồng.

### 1. Điều đã verify thật (Protocol 5 R5-01) và điều bất ngờ

Ba câu hỏi contract ban đầu đều trả lời được bằng **đọc source tool đã cài**, không phải suy đoán:

- `pdf2zh v1.9.11` — `lang_in` KHÔNG bị validate, và chỉ đi tới 3 chỗ (cache key, `${lang_in}` của
  file `--prompt`, `source_lang` của provider dịch máy). Font output chọn theo `lang_out` duy nhất.
  ⇒ FR "miễn phí" ở tầng pdf2zh.
- `babeldoc 0.6.4` — **bất ngờ theo hướng tốt**: prompt nó gửi LLM chỉ nói `lang_out`
  (`translator/translator.py:293`), `lang_in` chỉ còn nằm trong `__str__`/cache key. babeldoc vốn đã
  **không quan tâm ngôn ngữ nguồn**. Ngôn ngữ nguồn thật sự chỉ tới LLM qua `--custom-system-prompt`
  của chính app ⇒ chỗ phải sửa là `prompt_builder.py` của mình, không phải tham số CLI.
- `MinerU 3.4.5` — **bất ngờ theo hướng xấu**: `"fr"` KHÔNG nằm trong `PUBLIC_OCR_LANGUAGES` và
  `validate_public_ocr_lang()` raise thẳng. Nếu thiết kế theo phản xạ "map `source_lang` vào mọi
  tham số `lang` của mọi tool", nhánh `pdf_scan` FR sẽ **luôn chết ngay lần gọi đầu** — đúng shape
  sự cố MinerU 2026-09 mà Protocol 5 sinh ra để chặn. Lối đi đúng: giữ `lang="en"`, vì `"en"` là
  **alias** của model `"ch"` mà chính source mô tả là phủ *Latin*.

### 2. Vì sao không thêm thư viện detect ngôn ngữ

Cân nhắc `langdetect`/`lingua`/`fasttext`. Loại, vì mỗi dependency mới là một contract phải verify
theo Protocol 5 — trong khi bài toán chỉ là phân biệt **2 lớp** trên văn bản vài nghìn token.
Prototype hư-từ thuần Python chạy thật trên 6 sách EN trong `data/uploads/` (2026-09-16) cho
`en_share` ∈ [0,143 ; 0,306] và `fr_share` ≤ 0,0007 — **tách biệt > 200 lần**. Không có chỗ cho một
thư viện ngoài cải thiện gì. Chiều FR chưa đo được (không có tài liệu FR thật) ⇒ ⚠️ ASSUMED A-2.

Cũng loại `dc:language` trong OPF của EPUB: chỉ dùng được cho EPUB ⇒ tạo 2 nhánh detect lệch nhau
giữa PDF và EPUB, đúng loại rủi ro §6.14.7 tồn tại để chặn; và metadata của EPUB convert/lậu hay sai.

### 3. Protocol 8 audit — kết quả đáng chú ý nhất

14 bước hậu kỳ được rà (bảng đầy đủ ở §6.26.5). Ba kết luận không hiển nhiên:

- **`font_shrink_page()` KHÔNG phải Bug #9 lần hai.** Câu hỏi đặt ra ban đầu ("giả định bản dịch dài
  hơn X% có còn đúng khi nguồn là FR không?") hoá ra **đặt sai chỗ**: đọc `font_shrink.py:236-247`
  thì bước này **đo bề rộng glyph thật** trên trang output so với `block_bbox`, không có hằng số nào
  suy ra từ độ dài bản gốc. Tỷ lệ giãn chữ chỉ là *động cơ* viết ra bước này, chưa bao giờ là *tham
  số* của nó. Khác hẳn Bug #9, nơi lý do tồn tại (pdf2zh không tự co chữ) **thật sự không còn đúng**
  với babeldoc. ⇒ GIỮ BẬT, không đổi hằng số. Phụ chú: FR dài hơn EN 15–20% ⇒ VI/FR ngắn hơn VI/EN
  ⇒ bước này sẽ kích hoạt *ít* hơn, không nhiều hơn.
- **Guard tỷ lệ dấu tiếng Việt (`text_quality.py`) mới là chỗ thật sự suy yếu.** `_VN_DIACRITIC_CHARS`
  chứa `à á è é ì í ò ó ù ú â ê ô ý` — trùng chữ Pháp thường gặp. Unit FR **chưa dịch** có thể đạt
  ≥ 0,02 ⇒ lọt tầng 2. Nhưng guard này chỉ kích hoạt khi tỷ lệ **THẤP** ⇒ với FR nó chỉ *bỏ sót*,
  không bao giờ *báo nhầm*; và `_check_epub_output_guard()` là lớp phòng thủ độc lập bắt đúng ca này
  bằng so sánh chuỗi. ⇒ GIỮ BẬT không đổi ngưỡng (siết ngưỡng mới là rủi ro), ghi backlog A-4.
- **Bước duy nhất bị SKIP theo R8-02**: gợi ý "Các từ mới" (US-20). `term_extractor` chỉ nạp
  `en_function_words.txt` ⇒ hư từ Pháp không bị lọc, n-gram ứng viên thành rác. Chưa verify cách
  hiệu chỉnh ⇒ deny-by-default, skip cho job FR.

### 4. Điểm dễ sai khi implement (ghi lại để Reviewer soi đúng chỗ)

- Đổi độ dài chuỗi prompt cho nhánh EN = đổi `prompt_overhead_chars` × `segment_count` = đổi cost
  estimate của **mọi job EN đang chạy**. Vì vậy §6.26.6 bắt buộc test "byte-identical cho `en`".
- `cost_gate` và lúc chạy thật phải dùng **cùng một** `source_lang`, nếu không Lớp 2 ước sai (§6.11.6).
- `source_lang` ghi 1 lần rồi giữ nguyên qua resume — cùng lý do với `chunk_size_used`: chunk đã xong
  được sinh theo giá trị cũ.

### 5. Không có câu CLARIFY mới

HOI-09 đã phủ hết 4 trục quyết định (định dạng, glossary, UI, ưu tiên). Hệ quả "glossary EN lọc theo
`term_en` ⇒ gần như rỗng với tài liệu FR" là **hệ quả trực tiếp** của lựa chọn "dùng chung glossary
EN, không làm glossary FR ở v1" mà Hiếu đã chốt — ghi nhận là giới hạn đã biết ở §6.26.5 bước #2,
không hỏi lại (Protocol B: phát hiện giữa lúc WRITE → ghi mặc định, gộp vào đợt CLARIFY sau).

### 6. Bổ sung phạm vi (Hiếu, 2026-09-16, qua PM/AskUserQuestion, trước khi Dev bắt đầu implement)

Vì UI dùng auto-detect (không cho user tự chọn source language), Hiếu yêu cầu thêm: **cột hiển thị
ngôn ngữ nguồn đã detect (EN/FR)** trên UI danh sách job (`web/index.html`) và lịch sử
(`web/history.html`), đọc từ `jobs.source_lang` (đã có trong thiết kế §6.26.2, chỉ chưa expose ra
UI). Lý do: auto-detect có thể sai (xem BL-15, ngưỡng detect chiều FR chưa verify) — user cần thấy
hệ thống đã nhận diện gì để phát hiện detect sai sớm, thay vì chỉ biết sau khi đọc bản dịch. Không
đổi thiết kế backend, chỉ thêm hiển thị — gộp vào cùng phạm vi implement S7, không tách step riêng.

---

## 2026-09-16 — RCA BL-20: "Các từ mới" rỗng cho MỌI job EPUB từ 2026-09-10 (Tech Lead)

**Nguồn phát hiện**: QA, `docs/test-report.md` mục "S7 — Dịch FR→VI … QA live E2E" (2026-09-16).
Phát hiện **tình cờ** khi test S7 — không phải lỗi do S7 gây ra. Hợp đồng sau fix: Architecture.md
**§6.27** (và §6.18.5 đã được sửa lại cho khớp).

### 1. Triệu chứng

Job EPUB chạy xong, `status = "completed"`, file dịch đúng, nhưng panel "Các từ mới" **luôn rỗng**.
Không log lỗi nào tới mắt user, không cờ nào trên UI.

### 2. Chuỗi nguyên nhân (trace tay, R6-04)

1. `src/core/term_extraction_service.py:74-83` — nhánh `if job.file_type == FileType.EPUB:` raise
   `TermExtractionSourceError` **vô điều kiện**, kèm comment:
   *"US-22 chua implement (job_orchestrator.py rejects EPUB truoc khi toi status=completed) nen
   nhanh nay KHONG THE bi goi qua duong di binh thuong hien tai."*
2. Comment đó **đúng tại thời điểm viết**: commit `0dc7663` (2026-09-08, US-20) — xác minh bằng
   `git log -L 74,84:src/core/term_extraction_service.py`.
3. US-22 (dịch EPUB) lên production **2026-09-10**, commit `27d7daa` (v1.3.0) — 2 ngày sau. Tiền đề
   của guard hết hiệu lực; từ giờ phút đó mọi job EPUB `completed` đều đi thẳng vào nhánh raise.
4. Lỗi bị nuốt tại `src/api/routes/jobs.py:545-548`:
   `except Exception: logger.exception("Trich xuat tu moi that bai cho job %s — job VAN completed")`.
   **Đây KHÔNG phải chỗ sai** — đó chính là BR-TERM-01/§6.18.6 ("không tồn tại đường nào khiến lỗi
   trích xuất đổi được `job.status`"). Nhưng nó biến một lỗi lineage thành **im lặng tuyệt đối** với
   user: chỉ còn dấu vết trong log server mà không ai đọc.
5. Đường thủ công `POST /api/jobs/{id}/extract-terms` (`jobs.py:825-828`) **có** trả 400 rõ ràng —
   nhưng user không có lý do gì để bấm, vì UI không nói tính năng đã lỗi.

### 3. Root cause thật — KHÔNG phải Bug #5, là "guard hết hạn ngầm"

Câu hỏi PM đặt ra ("có phải kiểu code viết cho PDF trước, EPUB thêm sau nhưng chưa nối đúng nguồn
dữ liệu không?") — **gần đúng về hình dạng, sai về cơ chế**, và khác biệt này quyết định cách chống
tái diễn:

- Bug #5: hợp đồng lineage **chưa từng được viết**, ai cũng tưởng có người nối.
- BL-20: hợp đồng lineage **đã được viết đúng từ đầu** — §6.18.5 (2026-09-08) ghi chính xác
  `EpubDocument.load(job.file_path).full_text()`, và `full_text()` **đã tồn tại thật** trong code từ
  US-22 (`src/services/epub_document.py:885`). Không ai phải nghĩ ra gì mới. Cái sai là **code cố ý
  lệch khỏi hợp đồng bằng một guard tạm, kèm lời hứa "sửa khi US-22 lên production" không có chủ
  sở hữu** — đúng dạng lỗi quy trình mà R5-06 mô tả (chỉ thị "phải làm lại sau" không nằm trong
  `backlog[]` thì không bao giờ được thực thi).

**Yếu tố làm nó sống lâu**: có một test **bảo vệ chính cái bug** —
`test_lineage_epub_not_yet_supported_raises_clearly`
(`tests/integration/test_term_extraction_service.py:158-167`), docstring:
*"US-22 hasn't shipped `EpubDocument.full_text()` yet"*. Suite xanh liên tục qua 6 ngày và nhiều
đợt Reviewer/QA, vì test khẳng định đúng cái giả định đã chết. Đây là biến thể của cùng một cơ chế
Protocol 5 đã chỉ ra ở sự cố MinerU: **test chứng minh code khớp với giả định, không chứng minh giả
định còn đúng** — lần này giả định không sai lúc viết, nó **hết hạn** sau đó.

Nó cũng là một ca Protocol 8 nhìn từ phía ngược lại: R8-01 lo "bước CŨ không được audit khi thêm
biến thể MỚI". Ở đây biến thể mới (EPUB/US-22) đi vào một bước cũ (`extract_and_store_terms`) mà
không ai audit — chỉ khác là bước cũ *tự khai báo* rằng nó chưa hỗ trợ, và lời khai báo đó bị tin
mãi mãi.

### 4. Mức độ ảnh hưởng — đo thật, không ước lượng

Query `data/bb_translation.db` (2026-09-16):

| Nhóm | Job `completed` | Job có `suggested_terms` | Tổng dòng |
|---|---|---|---|
| `epub` | **8** | **0** | **0** |
| `pdf_digital` | 19 | 9 | 18.359 |
| `pdf_scan` | 1 | 0 | 0 |

Trong 8 job EPUB: **2 là sách thật của user** (`Sourdough Discard Recipes Cookbook` — 2.793 unit;
`Sourdough Every Day` — 1.951 unit), 6 còn lại là fixture QA (`qa_s7_*`, `qa_bl12_*`, 3-7 unit).
⇒ Thiệt hại thật: **2 cuốn sách**, tính năng "Các từ mới" mất trắng. Không mất bản dịch, không mất
dữ liệu — chỉ mất một cơ hội làm giàu glossary, và **có thể lấy lại 100%** (mục 5).

### 5. Phương án fix — chọn (A), không chọn (B)

**(A) Nối đúng nguồn (KHUYẾN NGHỊ)**: thay 4 dòng raise bằng
`EpubDocument.load(Path(job.file_path)).full_text()`, bắt `EpubParseError` → bọc thành
`TermExtractionSourceError` (để endpoint thủ công vẫn trả 400, không 500).

Đã **verify thật trước khi đề xuất** (không suy đoán), chạy `.venv/bin/python` trên chính 2 sách
của user:

| Sách | `len(full_text())` | Thời gian `load()+full_text()` | Ứng viên `extract_terms()` |
|---|---|---|---|
| Sourdough Discard Recipes | 198.514 ký tự | **0,2s** | 2.816 (top: `sourdough discard`, `sourdough waste`, `cup sourdough waste`) |
| Sourdough Every Day | 202.274 ký tự | **0,4s** | 2.709 (top: `active sourdough starter`, `floured work surface`, `plastic wrap`) |

Chất lượng ứng viên **tương đương nhánh PDF** (cùng thuật toán, cùng bộ lọc glossary phía sau) —
đủ để kết luận đây là fix thật, không phải fix hình thức. Chi phí 0,2-0,4s đồng bộ là chấp nhận
được, giữ đúng cách `pdf_digital` đang gọi `_extract_full_text` (không cần `asyncio.to_thread`).

**(B) Tắt hẳn tính năng cho EPUB kèm thông báo — BÁC BỎ**: chỉ hợp lý nếu nguồn text không tồn tại
hoặc chất lượng không dùng được. Cả hai điều kiện đều đã bị bác bằng số đo ở trên: nguồn có sẵn,
rẻ, kết quả tốt. Tắt tính năng ở đây là trả giá bằng chức năng cho một lỗi 4 dòng.

**Không thuộc BL-20 (đừng gộp vào)**: EPUB `source_lang = "fr"` vẫn **không** có "Các từ mới" — đó
là guard cố ý của §6.26.5 bước #13 (hư từ FR chưa lọc được, R8-02 deny-by-default). Fix BL-20
không được phép gỡ guard đó.

**Backfill**: đã kiểm `jobs.file_path` của cả 2 sách còn tồn tại trên đĩa ⇒ sau fix chỉ cần
`POST /api/jobs/{id}/extract-terms` 2 lần. Không migration, không sửa DB tay.

### 6. Chống tái diễn (chi tiết ở §6.27.4)

1. Test khẳng định-bug phải bị **thay bằng test lineage dương** (R6-02), không chỉ xoá.
2. Thêm test R6-02 mức `_run_job_background`: job EPUB completed ⇒ `suggested_terms` ≥ 1 dòng.
3. **Luật mới**: guard dạng "tính năng X chưa có nên nhánh này không thể bị gọi" trong `src/` bắt
   buộc có mục `backlog[]` với `source` là role chịu trách nhiệm gỡ. Đây là R5-06 áp cho **code**,
   không chỉ cho `⚠️ ASSUMED` trong Architecture.md — cùng một root cause: chỉ thị "sửa lại sau"
   không có chủ sở hữu thì không bao giờ được thực thi.

### 7. Câu hỏi cho Hiếu (Protocol B — gộp 1 lượt, không hỏi lẻ)

| # | Câu hỏi | Chặn bước nào | Đề xuất mặc định |
|---|---|---|---|
| 1 | Sau fix có tự động backfill 2 cuốn sách thật (chạy lại trích xuất) không? | Không chặn implement, chặn việc đóng BL-20 | **Có** — 2 lời gọi API, không rủi ro, không ghi đè gì (re-run giữ nguyên dòng user đã duyệt/bỏ qua) |
| 2 | Có muốn UI báo "trích xuất từ mới thất bại" thay vì im lặng (thêm cột `jobs.term_extraction_error`) không? | Không chặn fix BL-20 — là hạng mục riêng | **Tách backlog riêng, chưa làm ngay**: fix (A) làm nguyên nhân biến mất; thêm cột = migration + đổi API + đổi UI cho một trạng thái sau fix gần như không còn xảy ra. Nhưng nếu Hiếu muốn "không bao giờ im lặng nữa" thành nguyên tắc, đây là chỗ đúng để làm |

Câu #2 là quyết định **sản phẩm** (đánh đổi độ ồn vs độ minh bạch), Tech Lead không tự chốt.

### 8. Final Decision (Hiếu, 2026-09-17, qua PM/AskUserQuestion)

- **Câu 1: Có** (= mặc định) — sau khi fix, backfill lại "Các từ mới" cho 2 job thật (Sourdough
  Discard Recipes, Sourdough Every Day) qua `POST /api/jobs/{id}/extract-terms`.
- **Câu 2: Tách backlog riêng, làm sau** (= mặc định) — KHÔNG thêm `jobs.term_extraction_error`
  cùng đợt fix BL-20. Ghi backlog mới (BL-22) cho hạng mục UI báo lỗi minh bạch, chưa có owner
  thời điểm nào implement.

Dev implement fix theo §6.27 + backfill 2 job thật ngay trong cùng task.

---

## S8 — Loại bỏ trang claim bản quyền (thiết kế, Tech Lead, 2026-09-17)

> Hợp đồng hiện hành: `docs/Architecture.md` **§6.28**. Mục này chỉ ghi *vì sao* tới được thiết kế đó.

### 1. Đo trước, chọn hằng số sau (không chọn ngưỡng từ trực giác)

Chạy bộ chấm điểm nháp trên **13 PDF + 7 EPUB thật** trong `data/uploads/` trước khi viết một dòng
hợp đồng nào. Ba điều chỉ lộ ra nhờ đo, không thể suy đoán:

1. **Ca false positive nguy hiểm nhất không phải trang có nhiều từ khoá, mà là trang VỪA có bản
   quyền VỪA có nội dung thật**: `[Baking Heaven]` tạp chí trang 6 đạt **8 điểm** (đủ mọi từ khoá
   mạnh) nhưng thực chất là **mục lục công thức** dài 884 từ. Không ngưỡng điểm nào chặn được nó —
   chỉ **trần số từ** (`MAX_WORDS = 600`) chặn được. Nếu thiết kế theo trực giác "score càng cao càng
   chắc", đây là trang bị xoá mất.
2. **`©` ở footer mọi trang là chuyện thường**: `Better_For_You_Packaged_Food` có `©` trên 11/12
   trang. Vì thế `©` chỉ được 1 điểm, và pattern mạnh phải là `copyright ©` / `© <năm>` cạnh nhau.
3. **Giả định "trang bản quyền ở đầu sách" SAI với 2/6 EPUB thật của chính user**: `Sourdough by
   Science` để ở spine index 40/41, `Sourdough Every Day` ở 79/80. Nếu làm đúng theo chữ "thường ở
   đầu sách" trong HOI-10 thì tính năng hỏng trên 1/3 sách EPUB thật. Đó là lý do §6.28.2 quét **đầu
   + đuôi**.

Tách sạch ở `MIN_SCORE = 5`: dương thật thấp nhất = 5 (`Faster Artisan Breads II`), âm cao nhất = 4
(`17_Photo_Acknowledgements.xhtml`). Biên bằng 0 ở chiều dương → ghi thành `⚠️ ASSUMED S8-A1` kèm
backlog có owner (R5-06), không giấu trong văn xuôi.

Đã cân nhắc rồi **loại** `edition` khỏi danh sách từ khoá yếu: nó chỉ bắn trúng trang nội dung
("previous editions"), không tăng được ca dương thật nào.

### 2. Vì sao cắt trang ở Step 2b, không phải ở cost gate và cũng không phải sau khi dịch

- **Sau khi dịch là sai mục tiêu**: tiền đã tiêu. Cắt phải xảy ra trước `plan_chunks()`, vì chunk là
  đơn vị được gửi cho engine — trang không nằm trong chunk nào thì không bao giờ tới LLM.
- **Trước OCR cũng sai**: file `pdf_scan` chưa có text layer, heuristic không có gì để đọc. Nên
  Step 2b phải đứng **sau** cầu nối OCR.
- **Không đụng `cost_gate.py`**: ước dư đúng phần trang bị cắt (~0,5%) là **chiều an toàn** theo
  §6.11.6, và giữ bán kính thay đổi nhỏ. Sửa cost gate để "ước chính xác hơn" là tự chuốc rủi ro
  ước THẤP — đúng loại lỗi đã gây sự cố $6.50.
- Thực tế tiết kiệm được bao nhiêu: **1–2 trang/cuốn**. Nói thẳng ra đây không phải khoản tiết kiệm
  lớn; giá trị chính là *không trả tiền cho thứ sẽ bị vứt đi* và output sạch. Không tô vẽ con số này.

### 3. Protocol 8 audit — phát hiện đáng giá nhất nằm ở bước CŨ, đúng như Bug #9 đã dạy

Bước duy nhất **hỏng thật sự** vì S8 không phải bước nào mới, mà là `create_bilingual_pdf(merged_path,
file_path)` (`job_orchestrator.py:1070`) — bước có từ Increment đầu, không rẽ nhánh theo engine, "đã
chạy ổn từ trước". Nó ghép **trang i bản VI với trang i bản gốc** (`bilingual_merge.py:18-21`). Cắt
trang ở nguồn dịch mà quên cắt bản gốc ⇒ mọi trang sau trang bản quyền lệch cặp, job vẫn `completed`.
Đây là lý do §6.28.4 bắt buộc có artifact thứ hai `original_pruned.pdf` và test assert tham số này.

Ngược lại, `overlay_rotated_text()` **tự đúng** — vì nó đã đọc biến `translation_source_path` chứ
không đọc `file_path`. Bất biến "chỉ có MỘT biến chỉ nguồn nội dung" của §6.10.5 trả cổ tức ở đây:
bước nào tuân thủ nó thì miễn nhiễm với S8, bước nào đi đường vòng thì hỏng.

Về 2 engine PDF: đọc source cả hai (`pdf2zh/pdf2zh.py:208-217`, `babeldoc/format/pdf/
translation_config.py:394-422` + call site `legacy_parse.py:83`) xác nhận **cả hai đánh số `--pages`
1-based trên chính file input**, không engine nào giữ ánh xạ về file gốc ⇒ cắt trước khi gọi là đối
xứng hoàn toàn, không cần rẽ nhánh. Vẫn khai báo capability `page_numbers_relative_to_input` trên cả
2 runner (R8-03) để engine thứ 3 buộc phải tự trả lời câu hỏi này thay vì im lặng thừa hưởng.

### 4. EPUB: vì sao không chỉ "xoá file khỏi zip"

Đo thật 6 EPUB: một doc bản quyền được trỏ tới từ **tối đa 5 nơi khác nhau** (OPF item + itemref,
NCX `content` + `pageTarget`, nav `<li><a>`) — và **1/6 sách** (`Sourdough Every Day`) còn bị một
**content doc thường** (`mini_toc.xhtml`) trỏ tới. Href là **tương đối theo thư mục file chứa nó** và
có thể kèm **fragment** (`#page_iv`). Xoá entry mà bỏ qua bất kỳ điểm nào ⇒ link chết / spine trỏ vào
hư không — đúng hạng lỗi BL-12.

Hai quyết định để không lặp lại BL-12:
- **Deny-by-default (R8-02)**: gặp tham chiếu không phân loại được (`<img>`, `<iframe>`, navPoint có
  con) ⇒ `structural="skipped"`, **vẫn loại unit khỏi tập dịch** (tiền vẫn tiết kiệm, file vẫn hợp
  lệ, trang chỉ còn nguyên tiếng Anh). Tính năng suy giảm mượt, không đánh đổi bằng file hỏng.
- **Hậu kiểm trước khi `replace()`**: `load()` lại file tạm + quét lại toàn bộ entry để chắc chắn
  không còn tham chiếu nào tới href đã xoá. Fail ⇒ ghi lại output **không xoá gì**. §6.25 đã chốt
  "sửa ở bước GHI, không từ chối ở bước cuối"; ở đây là "tự kiểm ở bước ghi, không xuất file chưa
  qua kiểm".

### 5. Điểm dễ sai khi implement (để Reviewer soi đúng chỗ)

1. `job.total_pages` phải gán **sau** khi cắt, không phải ở Step 2 như hiện tại — nó là input của
   `plan_chunks()`.
2. Gán lại **chính** `translation_source_path`, không thêm biến song song.
3. `create_bilingual_pdf` — tham số thứ 2 (§3 ở trên).
4. Job cũ đang resume (có Chunk row, `copyright_removed_json` NULL) ⇒ **không cắt**, nếu không
   `page_start/page_end` đã ghi sẽ trỏ sai trang.
5. EPUB: `job.total_units` và `plan_epub_chunks()` phải dùng **cùng một** hàm
   `units_excluding(dropped)` — hai bộ lọc viết rời là công thức lệch nhau (§6.20.14.2 A-4).

### 6. CLARIFY cho Hiếu (Protocol B — 1 câu, ngoài phạm vi HOI-10, đã có mặc định để Dev không bị chặn)

**Câu S8-Q1**: HOI-10 chốt "chấp nhận rủi ro" cho *độ chính xác nhận diện*, nhưng không nói gì về ca
EPUB mà việc xoá **có nguy cơ làm hỏng cấu trúc file** (doc bản quyền bị ảnh/iframe/navPoint-có-con
trỏ tới).
- *Mặc định đã viết vào §6.28.6.3*: xoá **có tiền kiểm + hậu kiểm**; không an toàn ⇒ giữ nguyên
  trang trong file (không dịch nó) thay vì xuất file có nguy cơ hỏng.
- *Phương án khác nếu Hiếu muốn triệt để hơn*: luôn xoá, chấp nhận khả năng reader báo lỗi link.
- *Chặn bước nào nếu không trả lời*: không chặn — Dev implement theo mặc định; đổi ý sau chỉ là đổi
  1 nhánh trong `write_translated()`.

Không có câu CLARIFY nào khác. Mọi thứ còn lại nằm gọn trong HOI-10 hoặc đã có nguồn đo thật.

---

## 2026-09-17 — S8-B1 (QA blocking): `total_pages`/`total_units` không phản ánh số trang/unit SAU cắt

**Vai**: Tech Lead. **Nguồn**: `docs/test-report.md` "Kết luận S8" (S8-B1), đọc trực tiếp source
`src/api/routes/jobs.py`, `src/core/job_orchestrator.py`, `src/services/epub_document.py`.

### 1. RCA — vì sao guard `is None` không bao giờ kích hoạt

`POST /api/jobs` (`src/api/routes/jobs.py:648,652`) gán `total_pages=upload.page_count` và
`total_units=cost_estimate.total_units` **ngay lúc tạo Job row**, trước khi orchestrator chạy. Tới
`job_orchestrator.py:941` (`if job.total_pages is None`) và `:1388` (`if job.total_units is None`),
điều kiện luôn False trên đường chạy thật ⇒ dòng ghi lại số sau cắt không bao giờ chạy. Test
integration PASS vì fixture `_create_job()` không gán 2 field này (nhánh `is None` chỉ sống trong
test) — đúng hình dạng lỗi R6-02 mô tả.

Điểm quan trọng khi chọn hướng sửa: **`is None` ở 2 dòng đó KHÔNG phải một bất biến ngữ nghĩa**, nó
chỉ là idiom "compute-if-missing" cho job tạo ngoài API (test, job cũ). Bất biến ngữ nghĩa THẬT nằm
ở chỗ khác và đã được rà hết:

| Nơi dùng | Ngữ nghĩa đang dựa vào | Ảnh hưởng nếu bỏ gán lúc tạo job (phương án (a)) |
|---|---|---|
| `routes/jobs.py:935-940` `GET /{job_id}/cost-estimate` | NULL ⇒ **HTTP 400** "Job chua co total_pages/total_units" | **VỠ**: mọi job mới mất endpoint ước giá |
| `web/js/app.js:135-140` | `job.total_units` hiển thị ngay sau khi tạo job | **VỠ**: UI trống |
| `web/js/history.js:43-46` | `total_pages` NULL = job EPUB (US-19/BR-HIST-02) | **VỠ**: job PDF cũng thành NULL ⇒ lịch sử hiển thị "-" |
| `job_orchestrator.py:3332` `run_batch` (BR-BATCH-04 ngắn-trước) | NULL ⇒ fallback `file_size` | Suy giảm chất lượng sắp xếp |
| `job_orchestrator.py:1822` `run_parse_only` timeout | `total_pages * 6.0` | Đã có guard riêng `:1785`, không vỡ |
| `job_orchestrator.py:1593` ngưỡng fallback JOB EPUB (C-3) | `job.total_units or 0` | Nếu NULL lúc chạy ⇒ ngưỡng = max(1,0)=1 ⇒ fail oan |

⇒ **Phương án (a) bị loại**: nó phá 3 hợp đồng đang chạy (cost-estimate 400, 2 chỗ UI) để sửa 1 bug.

### 2. Phản biện phương án (b) "luôn ghi đè sau Step 2b"

(b) đúng hướng nhưng nếu hiện thực bằng cách bỏ `is None` ở `:941`/`:1388` thành ghi đè vô điều
kiện thì tạo ra 1 đường ghi SAI trong đúng 1 ca resume: kill-switch bị **tắt giữa chừng** sau khi
job đã cắt và đã tạo Chunk row. Lúc đó `_apply_copyright_removal()` return sớm với path CHƯA cắt
(`job_orchestrator.py:759-761` — kill-switch check nằm TRƯỚC nhánh đọc `copyright_removed_json`),
ghi đè vô điều kiện sẽ kéo `total_pages` ngược về số trang gốc trong khi `chunks.page_start/page_end`
đã đánh số theo file ĐÃ cắt ⇒ hai nguồn số trang lệch nhau vĩnh viễn trong cùng 1 job.

### 3. Final Decision — phương án (c): ghi tại đúng chỗ biết cắt đã xảy ra, + replay quyết định đã cam kết

**(c1)** Việc ghi `job.total_pages`/`job.total_units` sau cắt thuộc về **`_apply_copyright_removal()`
/ `_apply_epub_copyright_removal()`** — nơi DUY NHẤT biết tập `removed` và path sau cắt — chứ không
phải 2 dòng guard ở `run_job()`/`run_epub_job()`. Khi (và chỉ khi) có cắt thật sự xảy ra trong lần
chạy này, ghi **vô điều kiện** (không kèm `is None`):
- PDF: `job.total_pages = len(keep_indices)` (bằng `_count_pdf_pages(source_pruned_path)`), ngay
  trước khi return cặp path đã cắt.
- EPUB: `job.total_units = len(doc.units_excluding(removed))` ngay trước khi return tập href.

Guard `is None` ở `:941` / `:1388` **GIỮ NGUYÊN** — nó vẫn là đường compute-if-missing hợp lệ cho
job không đi qua cắt (kill-switch off, parse_only, job tạo ngoài API). Không nơi nào khác trong repo
dựa vào "total_pages == page_count của file gốc" (đã grep toàn `src/`+`web/`, bảng §1 ở trên).

**Idempotent qua resume/retry**: mỗi lần resume, `_apply_copyright_removal()` đọc lại `removed` từ
`copyright_removed_json` (ghi 1 lần, §6.28.3) và tính lại `keep_indices` từ file gốc ⇒ luôn ra
**cùng một** con số, ghi đè bằng chính giá trị cũ. Không có drift. Đây là lý do "ghi đè vô điều kiện
*bên trong nhánh có cắt*" an toàn, khác hẳn "ghi đè vô điều kiện *ở cuối Step 2b*".

**(c2) — sửa kèm, cùng gốc**: kill-switch chỉ được gate **quyết định mới** (lần quét đầu), KHÔNG
được gate **replay một quyết định đã cam kết**. Đổi thứ tự trong `_apply_copyright_removal()` /
`_apply_epub_copyright_removal()`: nếu job đã có Chunk row VÀ `copyright_removed_json.removed` khác
rỗng ⇒ **vẫn cắt** dù `copyright_page_removal_enabled=False`, vì `chunks.page_start/page_end` (hoặc
`unit_start/unit_end`) đã được đánh số theo file đã cắt — không cắt lúc này mới là silent
corruption. Kill-switch vẫn giữ nguyên ý nghĩa "job mới chạy y hệt trước S8" (không có Chunk row ⇒
return sớm như cũ). Muốn huỷ hẳn một job đã cắt: xoá job và tạo lại, không phải lật kill-switch.

### 4. Việc Dev phải làm (kèm test chặn tái diễn)

1. `src/core/job_orchestrator.py` `_apply_copyright_removal()` (~`:740-828`): thêm ghi
   `job.total_pages` + `db_session.add/commit` trong nhánh có cắt; đổi thứ tự kill-switch theo (c2).
2. `src/core/job_orchestrator.py` `_apply_epub_copyright_removal()` (~`:829-880`): tương tự với
   `job.total_units`; hàm cần nhận `doc` (đã có) để gọi `units_excluding`.
3. **KHÔNG** sửa `:941` / `:1388` (giữ `is None`), **KHÔNG** sửa `routes/jobs.py:648,652`.
4. Test bắt buộc (chặn đúng lỗi fixture-vs-production đã để lọt): ít nhất 1 integration test tạo Job
   **có sẵn** `total_pages`/`total_units` giống hệt `POST /api/jobs` (dùng `upload.page_count`), rồi
   assert sau `run_job()`/`run_epub_job()`: `job.total_pages == số trang file output thật` và
   `plan_chunks` nhận đúng con số đó. Thêm 1 test resume: chạy 2 lần, assert giá trị không đổi giữa
   2 lần (idempotent), và 1 test kill-switch-tắt-giữa-chừng (c2) assert vẫn cắt khi đã có Chunk row.
5. Tốt hơn nữa (không bắt buộc): sửa helper `_create_job()` trong
   `tests/integration/test_job_orchestrator.py:204` để **mặc định gán** `total_pages` như route
   thật, ép mọi test cũ chạy đúng nhánh production — đây mới là fix gốc của lý do bug lọt lưới.

### 5. Hai mục non-blocking từ Reviewer — đã đồng bộ cùng lượt

- §6.28.6.3 rule (f): bổ sung ngoại lệ "doc có đóng góp unit ⇒ LUÔN unwrap, không bao giờ xoá cả
  container" (nguồn: `src/services/epub_document.py:1106-1115`, `:1231-1242`).
- §6.28.3 ví dụ JSON: `structural` đổi từ scalar sang `dict[doc_href, "full"|"skipped"]` (nguồn:
  `job_orchestrator.py:_record_epub_structural_result`, `MAX_REMOVED=3` cho phép nhiều doc/job).

---

## 2026-09-17 — BL-21: `/health` trả danh tính code đang chạy (Tech Lead)

**Hợp đồng hiện hành**: `docs/Architecture.md` §5.4 (+ hàng `/health` trong bảng §5.1).

### RCA — tại sao note thủ công không đủ

4 lần chặn QA trong cùng một ngày (BL-12, S7, BL-20, S8) có cùng cơ chế: server chạy
`uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000` không `--reload` (verify `ps aux`,
PID 15918), Dev sửa code, QA test process cũ. Mỗi lần phát hiện bằng cách so `mtime` file với giờ
start — một thao tác thủ công, không ai nhớ làm TRƯỚC khi test, chỉ làm SAU khi kết quả đã lạ. Biện
pháp "ghi note nhắc restart" đã ngầm tồn tại và đã thất bại 4 lần: một chỉ thị không có cơ chế kiểm
tra thì không được thực thi (cùng dạng root cause với R5-06).

### Phản biện với chính đề xuất trong backlog BL-21

BL-21 đề xuất `/health` trả `git_commit`. **Chỉ `git_commit` là KHÔNG đủ cho đúng 4 ca đã xảy ra**:
cả 4 lần code fix đều ở trạng thái **chưa commit** khi QA cần test. `git rev-parse HEAD` trả cùng một
hash cho process cũ lẫn đĩa mới → field đó bằng nhau, không phát hiện được gì. Nếu implement đúng
nguyên văn BL-21, `/health` sẽ báo xanh trong cả 4 ca nó sinh ra để bắt.

→ Trường quyết định là `code_stale`: so fingerprint `(mtime_ns, size)` của `src/**/*.py` + `.env` tại
thời điểm **import module** với fingerprint **lúc gọi `/health`**. `git_commit`/`git_dirty_at_start`
giữ lại vì hữu ích cho việc ghi test-report (truy vết "đợt test này chạy trên commit nào"), nhưng
chúng là thông tin phụ, không phải tín hiệu chính.

`.env` nằm trong tập fingerprint vì `get_settings()` là `@lru_cache` (`src/core/config.py:333-334`)
và không chỗ nào gọi `cache_clear()` (grep toàn `src/`, 0 kết quả) → sửa `.env` cũng cần restart.
Không tạo báo động giả vì `PUT /api/settings` ghi DB chứ không ghi `.env`
(`src/api/routes/settings.py:3-6`). `web/**` bị loại khỏi fingerprint vì `StaticFiles` đọc lại đĩa
mỗi request — đưa vào sẽ làm `code_stale` kêu mỗi lần sửa HTML và tín hiệu sẽ nhanh chóng bị bỏ qua.

### Final Decision — không bật `--reload`

Mặc định Tech Lead, Hiếu có thể lật lại, **không chặn Dev implement `/health`**. Lý do đầy đủ ở
§5.4.5; tóm tắt: job dịch chạy in-process (`jobs.py:69`, `:521`), job có thể dài ~25 phút
(`jobs.py:854-858`), reload giết job giữa chừng → mất tiền LLM đã tiêu (§6.11) mà không có output,
`fail_orphaned_jobs()` chỉ dọn xác chứ không cứu, và AIMD (§6.12) mất trạng thái đã hội tụ. `--reload`
kích hoạt bởi một thao tác vô tình (lưu file) nên rủi ro đó là rủi ro thường trực, không phải ngoại lệ.
Thay bằng `scripts/restart_server.sh` có chốt: từ chối restart khi còn job ở `_ACTIVE_JOB_STATUSES`
(`jobs.py:847-859`), trừ khi `--force`.

Muốn reload khi nghịch UI: dựng process thứ hai port khác, không chạy job trên đó.

### Ghi chú nguồn (R5-01)

Mục §5.4 **không mô tả contract của tool bên thứ ba nào**: toàn bộ field lấy từ stdlib Python
(`os`, `time`, `datetime`, `hashlib`, `subprocess` gọi `git`) và từ source code của chính repo này,
đã trích dẫn file:line tại chỗ. Con số `79 file / 1,4 ms` là đo thật trên máy Hiếu 2026-09-17, không
phải ước lượng. Không có mục nào ở trạng thái `⚠️ ASSUMED` → không phát sinh mục `backlog[]` theo R5-06.

---

## Rotate Protocol C.3 lần 2 (2026-09-18) — tách nhật ký còn sót khỏi `Architecture.md`

**Bối cảnh**: sau lần rotate đầu (2026-09-10, 12.818 → 7.197 dòng), `docs/Architecture.md` tăng lại
lên **9.747 dòng** do các hạng mục mới (S7 §6.26, BL-20 §6.27, S8 §6.28, BL-21 §5.4, BL-04 §6.22,
BL-10 §6.23…) được viết theo lối *thiết kế + nhật ký lẫn nhau*. Lượt này **audit từng §** và chuyển
**76 khối nhật ký** (RCA, điều tra sự cố, phản biện Domain Expert, số đo một lần, gate
kiểm thử đã chạy xong, "cần PM/user quyết định" đã có quyết định, "thứ tự implement" của tính năng
đã ship) sang đây. **Không xoá một quyết định/hợp đồng nào** — mỗi chỗ cũ trong `Architecture.md`
giữ lại tiêu đề § + 1 dòng 📎 trỏ về đúng tiểu mục dưới đây, và phần hợp đồng/kết luận được giữ lại
(một số chỗ được tóm tắt lại thành các gạch đầu dòng "hợp đồng còn hiệu lực" ngay tại chỗ).

Kết quả: `Architecture.md` **9.747 → 7.947 dòng** (dưới ngân sách 8.000 của Protocol C.3).
Cùng lượt, 11 mục nhật ký 2026-09-06 → 2026-09-09 của chính file này được rotate sang
`docs/archive/design-log-until-2026-09-09.md` (Protocol C.2 — chuyển chỗ, không xoá).

**Mục lục khối đã chuyển** (theo thứ tự xuất hiện trong `Architecture.md` cũ):

1. 5.4.5. Quyết định: KHÔNG bật `--reload`, kể cả trên máy Dev/Hiếu
2. 6.7. EPUB Handling
3. 6.9.7. Can PM/user quyet dinh (anh huong PRD — Tech Lead KHONG tu sua)
4. 6.10.0. Van de
5. 6.10.2. Danh gia 3 huong — ket qua research
6. 6.11.0. Su co
7. 6.11.8. Thu tu implement cho Dev
8. 6.12.0. Su co
9. 6.12.10. Trang thai verify va gate release
10. 6.13. Prompt caching cho luong dich that (Claude qua `openailiked`) — dieu tra & khuyen nghi
11. 6.14.6. QA gate (R5-03 + R6-03) — E2E song song 2 engine tren cung file that
12. 6.15.1. Nguồn xác thực (Protocol 5 R5-01)
13. 6.15.2. Phần của §6.8 CÒN DÙNG ĐƯỢC nguyên trạng
14. 6.15.6. Gate release bổ sung cho US-15 (Protocol 5 R5-03 + Protocol 6 R6-03)
15. 6.15.7. Cập nhật S15-8 sau khi US-22 hoàn tất (2026-09-10) — spec thi hành cho nhánh EPUB→Markdown
16. 6.16.1. Nguồn xác thực (đo thật trên chính stack của project)
17. 6.17.1. Phát hiện chặn thiết kế: `updated_at` KHÔNG dùng làm mốc kết thúc được
18. 6.18.1. Mâu thuẫn phải giải: BR-TERM-03 ($0 mặc định) vs "thuật ngữ chuyên môn" (cần LLM)
19. 6.18.7. Cần PM/user quyết định (Tech Lead KHÔNG tự sửa)
20. T0. Số đo nền (kế thừa từ phản biện, Tech Lead KHÔNG đo lại)
21. T7. Những điểm của Expert tôi KHÔNG làm theo (kèm lý do)
22. T8. Gate release bổ sung cho US-20
23. 6.20.2. Sự thật đã verify về `bbook-maker==1.1.0`
24. 6.20.3. Sự thật đã đo về cấu trúc EPUB thật và về `ebooklib`
25. 6.20.4. So sánh 2 phương án
26. 6.20.10. Gate release (Protocol 5 R5-03 + Protocol 6 R6-03)
27. 6.20.11. Cần PM/user quyết định (Tech Lead KHÔNG tự sửa)
28. Ranh giới bằng chứng (ai đã verify cái gì)
29. Z1..Z3
30. Điểm của Expert tôi KHÔNG làm theo (kèm lý do)
31. Trạng thái §6.20 sau mục này
32. 6.20.13.0. Ba điều Tech Lead tự verify khi thiết kế (đọc source thật, không suy đoán)
33. 6.20.13.1. Phân tích lại Bug #EPUB-B2-1 — tách 3 nguyên nhân KHÁC NHAU bị gộp làm một
34. 6.20.13.9. Thứ tự implement bắt buộc cho Dev
35. 6.20.13.10. Gate release bổ sung cho vòng QA kế tiếp
36. 6.20.14.0. Nguồn xác thực cho mọi con số dưới đây
37. 6.20.14.1. Chẩn đoán lại: vì sao hướng vá cũ KHÔNG hội tụ
38. 6.20.14.5. Tương tác với các guard đang có — bảng kiểm bắt buộc đọc trước khi code
39. 6.20.14.7. Thứ tự implement bắt buộc
40. 6.20.14.8. Đã cân nhắc và HOÃN (giữ lại để không mất dấu vết suy nghĩ)
41. 6.20.14.9. Gate release cho vòng QA kế tiếp (cộng vào §6.20.10 và §6.20.13.10, không thay thế)
42. Nguồn xác thực (R5-01)
43. Thứ tự implement bắt buộc
44. Gate release (cộng vào §6.20.10/§6.20.13.10/§6.20.14.9, không thay thế)
45. 6.22.3. Tín hiệu quan sát được (Bước 2) — 3 phương án đã cân đo
46. 6.22.6.1.a. BL-08 — thứ tự ưu tiên và điểm khởi đầu (Domain Expert X6, 2026-09-11)
47. 6.22.8. Vị trí sửa (spec cho Dev — CHƯA implement)
48. 6.22.9. Gate kiểm thử
49. 6.23.7. Gate kiểm thử
50. 6.23.9. Vị trí sửa (spec cho Dev — CHƯA implement)
51. 6.27.1. Trạng thái trước fix (sự thật đo được 2026-09-16)
52. 6.12.2 — spike phát hiện stdout/stderr (log capture)
53. 6.12.3.1 — bối cảnh + lý do chọn default
54. 6.12.3.1 — 4 lý do chi tiết
55. 6.15 — 5 điểm bỏ sót phát hiện sau phản biện Domain Expert (S15-10..S15-14)
56. 6.18.8 — bối cảnh Final Decision US-20
57. 6.20.13.3b — thiết kế phát hiện runaway bản gốc + số đo bác bỏ ngưỡng (đã bị §6.20.15 K-2/K-4 thay)
58. 6.20.15 K-4 — lý do cấm hiệu chỉnh hằng số trước khi có số đo hậu K-2/K-3
59. 6.20.15 K-4 — 4 lý do giữ nguyên 3 hằng số
60. 6.21.4 — gate bắt buộc cho §6.21 (đã chạy xong cùng US-15)
61. 6.24 — nguồn xác thực hành vi nhớ thư mục tải của Chrome/Firefox
62. 6.25.6 — test bắt buộc khi implement BL-12 (đã implement + QA PASS)
63. 6.26.8 — test bắt buộc khi implement S7 (đã implement)
64. 6.28.9 — test bắt buộc khi implement S8 (đã implement)
65. 9.2 — Cloud Migration Path v2.0+ (định hướng, không phải hợp đồng đang chạy)
66. 6.20.12 X2 — số đo inner-HTML trên chapter01.html
67. 6.20.12 X6 — dump ebooklib 0.20 xác nhận doc_href
68. 6.20.13.3b — lý do hardcode 2 hằng số runaway ngoài .env
69. 6.20.13.4 — ranh giới bằng chứng cho giả thuyết prompt gây mất dấu
70. 6.20.13.5 — cơ sở chọn 4 ngưỡng diacritic (corpus nội bộ)
71. 6.20.13.5 — so sánh E-09 vs mất dấu + ước tính overhead guard
72. 6.20.13.6 — phần C-2 chưa giải thích được + task đo chars/token DeepSeek (đã đóng bởi §6.20.15 K-4)
73. 6.28.6.1 — bản đồ tham chiếu đo thật trên 2 EPUB mẫu
74. 6.9.5 — số đo bác bỏ câu "confidence is None ở txt mode"
75. 6.22.6.1 — số đo kênh (2) trên job Le Cordon Bleu
76. 6.22.6.1 — 3 cách đếm ký tự bị lọc đã bác + ứng viên thiết kế cho BL-08

---

### [Architecture.md cũ] 5.4.5. Quyết định: KHÔNG bật `--reload`, kể cả trên máy Dev/Hiếu

#### 5.4.5. Quyết định: KHÔNG bật `--reload`, kể cả trên máy Dev/Hiếu

**Quyết định (Tech Lead, mặc định — Hiếu có thể lật lại, không chặn Dev implement `/health`)**:
server trên port 8000 **không dùng `--reload`** trong mọi môi trường. Lý do, theo thứ tự nặng dần:

1. **Job chạy in-process.** `_schedule_background()` / `_run_job_background()`
   (`src/api/routes/jobs.py:69`, `:521`) chạy job dịch ngay trong process uvicorn, không phải worker
   riêng. `--reload` giết worker mỗi khi bất kỳ file watch được thay đổi → job đang dịch chết giữa
   chừng. Một job có thể dài ~25 phút (comment về `parsing`/MinerU, `jobs.py:854-858`).
2. **Chết giữa chừng = mất tiền thật.** Các chunk đã gọi LLM trước lúc reload đã bị tính phí và đã
   ghi vào sổ chi tiêu (§6.11), nhưng output thì mất. Reload là hành động vô tình (chỉ cần lưu file);
   đánh đổi "tiện tay" lấy rủi ro tiêu tiền là sai chiều.
3. **`fail_orphaned_jobs()` chỉ dọn dẹp, không cứu.** Nó chạy lúc startup (`lifespan`,
   `src/api/main.py`) và đánh job mồ côi thành `failed` — đúng, nhưng nghĩa là mỗi lần reload nhầm là
   một job hỏng phải chạy lại từ đầu.
4. **Reset state trong bộ nhớ.** AIMD concurrency controller (§6.12) và `@lru_cache` các loại mất
   trạng thái đã hội tụ sau mỗi reload → hành vi đo được trong lúc QA không còn ổn định để so sánh.

`--reload` giải quyết đúng một triệu chứng — "quên restart" — mà `/health` + `restart_server.sh` giải
quyết **không kèm 4 rủi ro trên**, với cái giá là một lệnh tường minh. Đây là đánh đổi có chủ đích:
ưu tiên job không bị ngắt hơn tiện tay của người sửa code.

Muốn có reload khi nghịch UI/route: chạy **process thứ hai, port khác** (ví dụ `--reload --port 8001`)
và **không chạy job dịch trên đó**. Không bao giờ bật `--reload` cho instance mà QA đang dùng.


### [Architecture.md cũ] 6.7. EPUB Handling

### 6.7. EPUB Handling

> ⛔ **SECTION NÀY ĐÃ BỊ SUPERSEDE HOÀN TOÀN BỞI §6.20 (2026-09-08). KHÔNG IMPLEMENT THEO ĐÂY.**
>
> Giữ nguyên câu chữ bên dưới **chỉ để đối chiếu lịch sử** (đúng kỷ luật R7-03: không xoá nội
> dung cũ). Toàn bộ §6.7 vi phạm Protocol 5 R5-01: mọi contract CLI của `bilingual_book_maker`
> và `ebook-convert` ở đây được viết **không có mục "Nguồn xác thực"**, khác hẳn §6.9.1/§6.10.1/
> §6.11.1/§6.12.1/§6.14.1. Khi Tech Lead verify thật (§6.20.1 — cài `bbook-maker==1.1.0` thật,
> đọc source thật, chạy thật), kết quả là:
> - Cờ `--model claude` / `--claude_key` / `--prompt` **có tồn tại** trong bản PyPI 1.1.0 (may mắn
>   đúng), nhưng đường Claude **hỏng hoàn toàn** với `anthropic` SDK hiện tại và hỏng **im lặng
>   với exit code 0** (§6.20.2 E-06/E-07) — tức là claim "khac biet co loi so voi pdf2zh:
>   bilingual_book_maker **co** backend Claude native" ở dưới, dù đúng về mặt chữ, dẫn tới một
>   kết luận thiết kế SAI.
> - `bilingual_book_maker` **không có** backend DeepSeek (provider mặc định của app) — §6.20.2 E-03.
> - Nhánh Calibre `ebook-convert` **ra khỏi scope** theo BR-EPUB-01 (PRD amendment 2026-09-08:
>   output EPUB-only, không tự convert PDF). 6 cờ liệt kê bên dưới **chưa từng được verify** và
>   không được dùng lại nếu sau này mở lại tính năng convert PDF.
>
> Quyết định thay thế: **Phương án B — `ebooklib` parse + Translation Engine nội bộ của app**,
> xem §6.20.3/§6.20.4.

**Flow**: bilingual_book_maker dich EPUB → EPUB dich → (optional) Calibre convert sang PDF.

> **Ap dung cung nguyen tac 6.6.2 R1**: bilingual_book_maker cung la tool all-in-one — no tu goi
> LLM qua `--model claude --claude_key ...` / `--model gemini` / `--model deepseek`. Orchestrator
> **khong** duoc goi `provider.translate()` song song voi no. Quy tac dich di qua `--prompt` cua
> bilingual_book_maker. Cost cung tinh theo phuong an uoc luong o 6.6.6 (`cost_source = 'estimated'`).
> Khac biet co loi so voi pdf2zh: bilingual_book_maker **co** backend Claude native (`--model claude`)
> → khong can di qua OpenAI-compat layer. Chi tiet mapping cho EPUB se chot o increment EPUB.

**Ly do tach rieng khoi PDF pipeline**:
- EPUB co structure khac (HTML chapters, CSS styling)
- bilingual_book_maker da optimize cho EPUB flow
- pdf2zh khong xu ly EPUB

**EPUB → PDF conversion**:
```bash
ebook-convert input.epub output.pdf \
    --pdf-page-margin-top 72 \
    --pdf-page-margin-bottom 72 \
    --pdf-default-font-size 12 \
    --embed-all-fonts \
    --pdf-page-numbers
```


### [Architecture.md cũ] 6.9.7. Can PM/user quyet dinh (anh huong PRD — Tech Lead KHONG tu sua)

#### 6.9.7. Can PM/user quyet dinh (anh huong PRD — Tech Lead KHONG tu sua)

**Van de**: PRD AC-11.2 viet "OCR confidence score < 80%". Ban PRD do ngam dinh MinerU tra ve 1
con so confidence cap tai lieu. **Con so do khong ton tai.** Cai ta thay the la mot dai luong
KHAC: trung binh confidence recognition cua cac span da qua OCR, do BB-Translation tu tinh.

Vi MinerU da vut san moi span < 0.5, phan bo cua dai luong moi bi don ve phia cao; nguong 0.80
tren dai luong cu **khong tuong duong** 0.80 tren dai luong moi. Chua co du lieu that de calibrate.

**Khuyen nghi cua Tech Lead** (can PM xac nhan voi user, khong tu ap):
1. **Giu tinh nang canh bao** (khong bo theo Option B) — no van co gia tri that, chi la doi
   dinh nghia phep do.
2. **Giu nguong 0.80 lam gia tri khoi diem**, dat trong setting `ocr_confidence_threshold` de
   chinh duoc sau, khong phai hang so trong code.
3. **PM cap nhat cau chu AC-11.2** tu "OCR confidence score (tu MinerU)" thanh "diem tin cay OCR
   tong hop do BB-Translation tinh tu span-level recognition score cua MinerU (Architecture 6.9.5)",
   va ghi ro nguong 0.80 la **provisional, se recalibrate sau khi co >= 10 file scan that**.
4. Bo sung 1 trang thai thu ba vao AC-11.2: **`ocr_confidence = NULL`** (khong span nao qua OCR)
   → khong canh bao. Hien AC-11.2 chi co 2 nhanh, thieu nhanh nay.
5. Cannh bao nen hien thi kem `dropped_span_count` ("MinerU da bo qua N vung chu khong doc duoc")
   — cu the va huu ich cho user hon mot con so %.

**Neu user khong muon nhan them scope**: fallback la Option B — bo canh bao khoi v1.0, ghi
AC-11.2 thanh known limitation giong US-15. Tech Lead **khong khuyen nghi** huong nay vi chi phi
thuc thi cua khuyen nghi tren chi la ~40 dong `_compute_quality()`.


### [Architecture.md cũ] 6.10.0. Van de

#### 6.10.0. Van de

QA Vong 3 (`docs/test-report.md` → "Bug #5") chung minh bang E2E that: voi 1 job `pdf_scan`,
MinerU chay dung, OCR chinh xac 100%, `ocr_confidence = 0.9908` luu dung DB — nhung
`translated_vi.pdf` **trong hoan toan** (`text_len = 0` moi trang), job van bao `completed`.

Root cause kien truc (khong phai 1 cho thieu wire): `run_job()` chi lay
`ocr_result.quality.confidence`; moi buoc doc noi dung sau do — `_extract_full_text()`,
`_extract_chunk_text()`, `_count_text_segments()`, va quan trong nhat
`pdf2zh_runner.translate_pages(input_path=...)` — deu dung lai `job.file_path`, tuc **file scan
goc khong co text layer**. Ket qua OCR (`document.md`, `middle.json`) khong bao gio di vao luong
dich. Giua `MinerUResult` (Markdown + JSON) va `pdf2zh` (chi an **file PDF**) **chua co cau noi**.


### [Architecture.md cũ] 6.10.2. Danh gia 3 huong — ket qua research

#### 6.10.2. Danh gia 3 huong — ket qua research

**Huong B — de pdf2zh tu OCR: BAC BO (khong kha thi).**
pdf2zh 1.9.11 khong chua tu "ocr" nao trong source (S12); no doc text bang pdfminer.six tren
content stream (S13). OCR duy nhat trong cay phu thuoc la RapidOCR cho *table detection* cua
babeldoc (S14), khong phai page text recognition, va duong babeldoc mac dinh khong bat. Khong co
flag `--ocr`. => Khong ton tai duong nao de pdf2zh tu doc chu tu anh. Day chinh la ly do co hoc
khien Bug #5 im lang: pdf2zh nhan file khong co text object → khong co gi de dich → exit 0.

**Huong A nguyen ban — MinerU tu xuat searchable PDF: BAC BO (tinh nang khong ton tai).**
Da doc het danh sach file MinerU ghi ra (S10): `_layout.pdf` va `_span.pdf` la **anh visualization
ve bbox** (`draw_layout_bbox`/`draw_span_bbox`), `_origin.pdf` la **ban sao file goc**. Khong co
output nao la PDF da nhung lai text layer. `return_original_file` khong phai thu ta tuong (S11).
=> MinerU **khong** lam ho ta buoc nay.

**Huong C — render lai PDF tu Markdown: KHONG CHON (con phuong an tot hon).**
Mat toan bo layout goc — vi pham yeu cau cot loi PRD US-04 ("giu nguyen layout"), va tao ra
duong code thu hai hoan toan khac cho `pdf_scan` (chunking, font-shrink, bilingual merge, cost
accounting deu phai viet lai). Chi dung lam fallback neu A' that bai — A' da duoc chung minh la
khong that bai (6.10.3).


### [Architecture.md cũ] 6.11.0. Su co

#### 6.11.0. Su co

User cung cap screenshot OpenAI dashboard ngay **2026-09-04**:

| Chi so OpenAI bao | Gia tri |
|---|---|
| Chi phi | **$6.50** |
| So request | **2,989** |
| Token | **1,548,096** |

Trong khi do toan bo bao cao QA cong lai (`docs/test-report.md`) chi ra ~**$0.007**:
Vong 4 `actual_cost=$0.0019`, Vong 5 "chi phi thuc te ~$0.0053", Vong 6 $0 (het credit).
Lech **~1000 lan**.

#### 6.11.1. Nguon xac thuc (Protocol 5 R5-01)

Toan bo ket luan duoi day doc truc tiep tu **cache SQLite that cua pdf2zh** con
nguyen tren may tai thoi diem dieu tra:

- **S1** — `~/.cache/pdf2zh/cache.v1.db` (23 MB, mtime `2026-09-04 19:00`), bang
  `_translationcache`, schema:
  `(id INTEGER PK, translate_engine VARCHAR(20), translate_engine_params TEXT,
  original_text TEXT, translation TEXT)` — **khong co cot timestamp**, nen moc
  thoi gian suy ra tu `id` tang dan + mtime file, khong phai tu cot ngay thang.
- **S2** — File nguon that:
  `/Users/hieutt/Downloads/Figoni, Paula - How baking works_ exploring the
  fundamentals of baking science (2007_2008, Wiley) - libgen.li.pdf`,
  **415 trang** (do bang PyMuPDF).
- **S3** — `docs/test-report.md` muc "QA Vong 5" va "QA Vong 6".
- **S4** — `src/core/cost_estimator.py`, `src/core/job_orchestrator.py`
  (`_count_text_segments`, `_extract_chunk_text`), `src/services/pdf2zh_service_map.py`.

#### 6.11.2. Ket luan dieu tra — nguon con $6.50

**Gia thuyet ban dau cua PM (job 81 trang cua QA Vong 5) la SAI.** Bang chung phan bac:

Truy van S1 nhom theo model:

| engine | model | so dong | id range | tong `original_text` |
|---|---|---|---|---|
| openai | **gpt-4o** | **2,941** | 2 → 2,988 | 699,103 chars |
| openai | gpt-4o-mini | 39 | rai rac 1 → 2,677 | 1,398 chars |
| google | (null) | 6 | 2,989 → 2,994 | 174 chars |

**Ba bang chung doc lap xac dinh thu pham la job dich SACH THAT, chay bang `gpt-4o`:**

1. **Noi dung cache la sach that, khong phai file test QA.** Cac dong dau tien:
   `"HOW BAKING WORKS"`, `"S E C O N D   E D I T I O N"`,
   `"Exploring the Fundamentals of Baking Science"` — chinh la trang bia cua S2.
   File test cua QA Vong 5/6 chi chua 5 cau lap lai
   (`"Page N. Today the oven is very hot."`) — dung 39 dong `gpt-4o-mini`
   (dedup cache lam 81 trang lap chi con 39 chuoi duy nhat, khop hoan hao voi
   bao cao QA Vong 5 `api_tokens_used` tong 30,925).
2. **Model la `gpt-4o`, khong phai `gpt-4o-mini`.** 2,941/2,986 dong dung `gpt-4o`
   — dat hon `gpt-4o-mini` **16.67 lan**. Day la default cu truoc khi Increment 6
   doi default sang `gpt-4o-mini`.
3. **Pham vi da dich**: marker in-an trong cache (`c01.indd` … `c11.indd`, so trang
   `1` → `248`) cho thay job da dich het chuong 1–11, tuong ung ~**270 trang PDF**
   tren tong 415 — tuc job chay duoc ~65% cuon sach thi het credit.

**Doi chieu so hoc (tinh tu S1, khong goi API moi):**

```
requests (dong cache gpt-4o)      = 2,941        [OpenAI bao 2,989 — lech 1.6%, la cac
                                                  request loi/retry khong vao cache]
tong prompt_chars (lap moi request)= 3,864,474    (1,314 chars/request)
tong original_text chars           =   699,103
tong translation chars             =   809,717

input_tokens  ≈ (3,864,474 + 699,103)/4 = 1,140,894
output_tokens ≈ 809,717 / 2.0 (tieng Viet co dau ~2 chars/token) = 404,858
TONG                                     = 1,545,753 token
```

**OpenAI bao 1,548,096 token — lech 0.15%.**

```
Chi phi @ gia gpt-4o ($2.50/MTok in, $10.00/MTok out):
  input  1,140,894 × 2.50/1e6 = $2.85
  output   404,858 × 10.0/1e6 = $4.05
  TONG                        = $6.90
```

**OpenAI bao $6.50 — lech 6%.** Cung 1 bo du lieu tai tao doc lap ca **so request**,
**so token** va **so tien** trong sai so vai phan tram. Ket luan la chac chan.

> **Neu cung job do chay bang `gpt-4o-mini`: $0.414.** Tuc rieng viec chon nham model
> da nhan chi phi len **16.7 lan**.

#### 6.11.3. Root cause — 4 loi doc lap cong don

**RC-1 (chinh, ~85% chi phi): prompt file duoc gui lai NGUYEN VAN cho TUNG SEGMENT.**
Da ghi trong 6.6.1 finding F6 va 6.6.5, nhung **chua bao gio duoc dinh gia bang so that**.
Do tu S1: prompt = **1,314 chars ≈ 328 token**, `original_text` trung binh chi **238 chars
≈ 59 token**. Tuc **84.7% toan bo input token la prompt boilerplate lap lai**, chi 15.3%
la noi dung that can dich.

> **Canh bao khuyech dai chua duoc mo hinh hoa**: job nay chay voi **0 glossary entry**
> (`"(Khong co glossary entry nao ap dung cho tai lieu nay.)"`, xac nhan trong
> `translate_engine_params` cua S1). Voi cap **80 entry** cua 6.6.5, moi dong glossary
> ~35–45 chars → prompt phinh len ~4,500 chars ≈ **1,125 token/segment**, tuc input
> token **tang ~3.4 lan** so voi lan chay da do. Dung use-case that cua user (sach nganh
> banh + glossary day du) se **DAT HON** lan chay $6.50 nay, khong phai re hon.

**RC-2: cong thuc uoc tinh TRUOC JOB (`estimate_job_cost`) sai bac do lon.**
`src/core/cost_estimator.py::AVG_INPUT_TOKENS_PER_PAGE = 500` — hang so **chua tung
duoc do tu tai lieu that** (docstring tu thua nhan: *"Not measured from real documents
yet"*). Thuc te do duoc: `1,140,894 input token / ~270 trang` = **4,225 token/trang**
→ heuristic thap hon thuc te **8.4 lan**.

Ngoai ra `estimate_job_cost()` **hoan toan khong biet den F6** — no khong co tham so
`segment_count`, khong nhan prompt overhead, chi nhan `total_pages`. Tuc chinh con so
duy nhat user nhin thay TRUOC KHI bam Dich duoc tinh bang cong thuc bo qua nguyen nhan
chiem 85% chi phi that.

Ap len ca cuon sach 415 trang:

| | input tok | output tok | @gpt-4o | @gpt-4o-mini |
|---|---|---|---|---|
| `estimate_job_cost` hien tai (500/trang) | 207,500 | 269,750 | **$3.22** | $0.19 |
| Ngoai suy tu so do that (S1) | 2,607,524 | 665,000 | **~$13.2** | ~$0.79 |
| Sai so | | | **thap hon 4.1×** | thap hon 4.2× |

**RC-3: KHONG CO hard cap o bat ky lop nao.** Ra soat toan bo `src/`:
`estimated_cost` chi duoc **ghi vao DB va hien thi**, khong co nhanh code nao so sanh
no voi mot nguong va tu choi chay. Khong co bien dem chi phi tich luy trong khi chay.
Khong co gioi han cap batch. `max_concurrent_files = 3` (`src/core/config.py:62`) gioi
han **so file song song**, khong gioi han **tien**. Job chi dung khi (a) user bam cancel
thu cong, (b) `pdf2zh` timeout 3600s/chunk, hoac (c) **het sach credit** — day chinh
xac la cach job nay dung lai.

**RC-4: `actual_cost`/`api_tokens_used` la UOC LUONG nhung bi bao cao nham la SO DO THAT.**
`job_orchestrator.py:582-583` gan `chunk.api_tokens_used` tu ket qua
`estimate_chunk_cost()` — thuan tuy so hoc tren do dai text, **khong he cham vao
`response.usage` cua OpenAI** (dung nhu 6.6.6 da thiet ke, `cost_source="estimated"`).
Nhung `docs/test-report.md` muc "QA Vong 5" viet:

> *"tong `api_tokens_used` 3 chunk = 14551+15286+1088 = 30,925 token that da dung,
> **lay tu `response.usage` OpenAI that, khong phai uoc luong**"*

**Cau nay SAI.** Con so do la uoc luong, va viec no bi trinh bay nhu so do dem that la
ly do bao cao QA duoc tin tuong qua muc, khong ai truy tiep. (`docs/test-report.md`
QA Vong 6 cung ghi sai tuong tu: *"~2980 dong cache cu (tu QA Vong 3/4 truoc do)"* —
thuc te QA Vong 3/4 chi dich 1–2 trang; 2,941 dong do la job sach that.)

**Danh gia lai `estimate_chunk_cost()` (khac han — cong thuc nay DUNG huong):**
No **co** nhan `segment_count × prompt_overhead_chars`, tuc **co** mo hinh hoa F6.
Kiem chung nguoc lai so do that (pages 1–270 cua S2):

| | Cong thuc du doan | Thuc te do (S1) | Lech |
|---|---|---|---|
| input tokens | 1,671,165 | 1,140,894 | **+46%** (an toan, du cao) |
| output tokens | 360,172 | 404,858 | **−11%** (thieu, can sua) |
| tong | 2,031,337 | 1,545,753 | +31% (an toan) |

→ `estimate_chunk_cost()` la **nen mong dung**, chi can hieu chinh `vi_token_factor`.
`estimate_job_cost()` moi la ham phai viet lai.

**Do chinh xac cua `_count_text_segments()`** (`job_orchestrator.py:127`): dem
non-empty PyMuPDF blocks. Do tren S2: pages 1–270 → **4,525 blocks** vs **2,989 request
that** → uoc luong **cao hon 1.51 lan**. Sai lech theo huong AN TOAN (over-estimate) —
dung ban chat can co cho mot ham dung de chan chi tieu. Giu nguyen, khong "toi uu" cho
sat hon.


### [Architecture.md cũ] 6.11.8. Thu tu implement cho Dev

#### 6.11.8. Thu tu implement cho Dev

1. **Lop 0** (UI/nhan/canh bao) — effort thap nhat, chan ngay kieu nham model.
2. **Lop 1 + golden file 6.11.6** — phai xong truoc Lop 2, vi Lop 2 dung ket qua cua no.
3. **Lop 2** (pre-flight gate, job + batch + retry).
4. **Lop 3** (running accumulator + status `cost_capped`).
5. **Lop 4** (`LLMMeteringProxy`) — increment rieng.

**Gate release (R5-03 + R6-03)**: QA **khong duoc** `ready_for_release` cho tinh nang
nao trong section nay neu chua co it nhat 1 lan chay that chung minh **cap thuc su chan
duoc job** (dat tran that thap, chay 1 job that, xac nhan job dung o `cost_capped` va
chi phi thuc te khong vuot xa tran). Mock-only **khong du** — day chinh xac la kieu
xac nhan ma su co $6.50 da chung minh la khong dang tin.

---



### [Architecture.md cũ] 6.12.0. Su co

#### 6.12.0. Su co

Job dich "How baking works" (Figoni, Paula) fail:
`Chunk 0 that bai: pdf2zh vuot qua timeout 3600s ... (trang 1-40)`.

Nguyen nhan: `Pdf2zhRunner.translate_pages()` (`src/services/pdf2zh_runner.py:63-77`) dung
argv **khong bao gio** chua flag `--thread`, nen pdf2zh luon chay o mac dinh cua chinh no
la 4 luong. Voi sach dac chu (~7063 doan van uoc tinh cho ca cuon; 1 chunk 40 trang chua
hang tram doan), 4 luong khong du de ve dich trong 3600s.

Section nay chot thiet ke 1 **AIMD adaptive concurrency controller**: hoc dan muc `--thread`
an toan nhat cho tung cap `(provider, model)` qua ket qua that cua tung chunk, thay vi
hardcode 1 con so doan mo.

---


### [Architecture.md cũ] 6.12.10. Trang thai verify va gate release

#### 6.12.10. Trang thai verify va gate release

| Hang muc | Trang thai | Chan gi |
|---|---|---|
| `--thread` flag, default 4, mapping sang `ThreadPoolExecutor` | VERIFIED (S1, S2) | — |
| Retry + log line cua `OpenAITranslator` | VERIFIED (S3) | — |
| DeepSeek ke thua retry | VERIFIED (S4) | — |
| Log ra **stdout** chu khong stderr; wrap 80 cot cat chuoi; `COLUMNS=200` sua duoc | VERIFIED bang chay that (S9, S10, S11) | — |
| Gioi han concurrency DeepSeek 500/2500 | VERIFIED (S12) | — |
| Gioi han cho **`deepseek-chat`** cu the | `[UNVERIFIED]` (S13) | Khong chan implement (floor 8 an toan doc lap voi so nay). Chan viec **vien dan** 500/2500 de nang floor deepseek len cao hon. |
| Anthropic compat 429 -> `openai.RateLimitError`? | `[UNVERIFIED]` (S6) | **CHAN** viec bat AIMD cho provider `claude`. Claude = thread co dinh 4 cho toi khi spike 6.12.6 xanh. |
| Google compat 429 -> `openai.RateLimitError`? | `[UNVERIFIED]` (S5) | **CHAN** viec nang floor gemini tu 4 len 8. Khong chan AIMD cho gemini o floor 4. |

**Thu tu implement cho Dev:**

1. **6.12.3 + 6.12.2 D1/D2** (capture stdout, `COLUMNS=200`, `_drain`, exception mang tin
   hieu). Blocker tuyet doi — moi thu con lai vo nghia neu bo dem luon bang 0.
2. **Golden file** (Protocol 5 muc 3): chay pdf2zh that o `--thread` cao voi DeepSeek cho
   toi khi cham 429, luu stdout that vao `tests/fixtures/pdf2zh/deepseek_ratelimit/`.
   Moi mock cua buoc 3-5 sinh tu file nay.
3. **6.12.8** (schema: bang `concurrency_state`, 3 cot moi, 2 setting moi).
4. **6.12.4** (`src/core/concurrency_controller.py` — thuan logic, khong I/O, de unit test).
5. **6.12.7** (`chunk_size` cold-start + `Job.chunk_size_used`).
6. **6.12.6** (Ollama fixed thread; Claude khoa o floor).
7. Spike Claude + spike Gemini (6.12.6) — increment rieng, sau khi 1-6 xanh.

**Gate release (R5-03 + R6-03):** QA **khong duoc** `ready_for_release` cho section nay neu
chua co it nhat 1 lan chay **xuyen suot** that: 1 job that >= 3 chunk voi DeepSeek, roi mo DB
xac nhan (a) `chunks.thread_used` **thay doi giua cac chunk** dung theo luat 6.12.4, (b)
`concurrency_state.current_thread` cuoi cung khac gia tri floor ban dau, (c) file PDF output
co chu that. Chi kiem tra `job.status == "completed"` la **khong du** — day dung la kieu xac
nhan da bo lot Bug #5.

---


### [Architecture.md cũ] 6.13. Prompt caching cho luong dich that (Claude qua `openailiked`) — dieu tra & khuyen nghi

### 6.13. Prompt caching cho luong dich that (Claude qua `openailiked`) — dieu tra & khuyen nghi

> Nguon goc: yeu cau dieu tra "co dang lam prompt caching cho Claude tren duong pdf2zh
> khong, vi RC-1 (6.11.3) cho thay 84.7–95% input token la boilerplate lap lai (prompt +
> glossary)". Ket luan: **KHONG lam** — co 2 rao can doc lap, moi cai da du de chan, va
> `default_provider` hien tai (DeepSeek) da tu dong huong loi tuong duong ma khong can sua
> gi. Ghi lai day du de khong ai dieu tra lai cau hoi nay lan nua.

#### 6.13.1. Nguon xac thuc (Protocol 5 R5-01 / global CLAUDE.md muc "gan nhan verify")

| # | Claim | Nguon xac thuc |
|---|---|---|
| V1 | Anthropic OpenAI-compat layer (`https://api.anthropic.com/v1/`, dung qua `-s openailiked`) **khong ho tro prompt caching**. Nguyen van: *"Prompt caching is not supported, but it is supported in the Anthropic SDKs"*. | Fetch truc tiep `https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk` (redirect tu `docs.claude.com/en/api/openai-sdk`) ngay 2026-09-05, muc "Important OpenAI compatibility limitations" → "API behavior". Doc hien tai con neu ro compat layer *"not considered a long-term or production-ready solution for most use cases"* — dung y da ghi o F4 (6.6.1), nay verify lai truc tiep tu doc goc thay vi suy doan. |
| V2 | Bang header cua cung trang tren (`Header compatibility`) chi liet ke cac header rate-limit chuan (`x-ratelimit-*`, `retry-after`, `request-id`, ...). **Khong co header nao lien quan `cache_control` hay tuong duong** de "lach" gioi han V1 qua `extra_headers`. | Cung nguon voi V1, bang "Header compatibility" doc day du. |
| V3 | `pdf2zh` v1.9.11 (`translator.py`, class `OpenAITranslator.do_translate()`, ke thua boi `OpenAIlikedTranslator` dung cho Claude — 6.6.3): goi `self.client.chat.completions.create(model=self.model, **self.options, messages=...)` voi `self.options = {"temperature": 0}` **co dinh, khong nhan them tham so nao**. Khong co `extra_headers`, `extra_body`, hay bat ky co che nao cho phep chen `cache_control` vao request. | Doc truc tiep source da cai: `~/.local/share/uv/tools/pdf2zh/lib/python3.12/site-packages/pdf2zh/translator.py` dong ~398-431 (constructor + `do_translate`). |
| V4 | `pdf2zh` khong co co che config/env/`--config` nao cho phep tiem them request param tuy y vao loi goi API — `ConfigManager` (`pdf2zh/config.py`) chi quan ly key-value don gian (API key, base URL, model...) cho tung translator, khong co "extra params" passthrough. | Doc truc tiep source `pdf2zh/config.py` (toan bo file, khong co bat ky `extra_headers`/`extra_body`/generic-param nao). |
| V5 | DeepSeek context caching (dung mac dinh o `default_provider = "deepseek"`, `src/core/config.py:71`) **tu dong hoan toan, khong can header/tham so gi tu client**. Nguyen van: *"The DeepSeek API Context Caching on Disk Technology is enabled by default for all users, allowing them to benefit without needing to modify their code."* Co the kiem chung qua `usage.prompt_cache_hit_tokens` / `usage.prompt_cache_miss_tokens` trong response. | Fetch truc tiep `https://api-docs.deepseek.com/guides/kv_cache` ngay 2026-09-05. Xac nhan claim `[CHUA VERIFY]` da ghi trong `config.py` comment (PRD US-14) la **DUNG**. |

#### 6.13.2. Ket luan — 2 rao can doc lap, ca hai deu chan hoan toan (khong phai 1 cai de vuot qua)

1. **Rao can phia Anthropic (V1, V2)**: day la gioi han **server-side** cua Anthropic, khong
   phai gioi han client co the cau hinh de vuot qua. Compat layer tu choi ap dung caching bat
   ke request gui gi — khong co header/param "lach" nao duoc liet ke.
2. **Rao can phia `pdf2zh` (V3, V4)**: ke ca **neu** V1 sai (Anthropic co ho tro), `pdf2zh`
   hien tai van khong co duong nao de app truyen `cache_control` vao request ma khong **fork**
   `OpenAITranslator.do_translate()` — day la thay doi vuot qua muc "config fix", tuong duong
   viet lai 1 phan `pdf2zh`, ke thua toan bo rui ro bao tri (update `pdf2zh` version se mat
   patch, phai re-apply — dung kieu rui ro ma 6.6.7 muc 1 da canh bao cho ca nhanh Claude).

Ca hai rao can deu **doc lap va deu du de tu minh chan giai phap** — khong ton tai "fix don
gian, an toan, khong fork" nhu cau hoi dat ra ban dau da hy vong.

#### 6.13.3. Uoc tinh chi phi bi bo lo (chi de tra loi "co dang lam khong", KHONG dung de bao cao)

Ngoai suy tu so do that S1 (6.11.2, job 0-glossary, 2,941 request `gpt-4o`) + he so phinh
prompt do 80-entry glossary (~3.4 lan, da tinh o RC-1 6.11.3), ap cho **quy mo do PM cung cap
cho task nay (~7,063 segment cho 1 cuon sach)** — day la so **[CHUA VERIFY]** rieng, PM chua
dua nguon do dac (khac voi S1/RC-1 la so do that):

```
prompt_chars/segment (co glossary 80 entry, ngoai suy RC-1) ~ 4,500 → ~1,125 token (cache-able,
    la phan template+glossary CO DINH, khong doi giua cac segment cung 1 job)
original_text/segment (do that S1)                           ~ 238 chars → ~59.5 token (KHONG
    cache-able — la noi dung that can dich, khac nhau moi request)

7,063 segment:
  tong input token          ~ 7,063 * (1,125 + 59.5)         ~ 8,367,000 token
  phan CO THE cache (prefix)~ 7,063 * 1,125                  ~ 7,946,000 token (~95% input)
```

Neu Anthropic prompt caching hoat dong tren duong nay (KHONG hoat dong — xem 6.13.2), muc
giam gia cache-hit theo tai lieu Anthropic cong bo la **toi da ~90% gia input** cho phan
cache-hit. Ap dung ly thuyet (khong the do that vi khong the bat duoc):

```
Gia Claude dung lam vi du minh hoa (KHONG phai gia dang dung — provider mac dinh la DeepSeek,
xem 6.13.4), lay Claude Sonnet ~$3/MTok input lam moc tham khao:
  Khong cache: 8,367,000 token * $3/1e6                      ~ $25.1 (chi phan input)
  Co cache (90% off cho ~95% input, sau request dau):
      cached ~7,946,000 * $0.30/1e6                          ~ $2.38
      uncached ~421,000 * $3/1e6                             ~ $1.26
      tong                                                    ~ $3.64
  Tiet kiem ly thuyet                                         ~ $21.5 (~86% phan input)
```

Con so nay **chi mang tinh minh hoa muc do "dang gia" ve nguyen tac** — khong dung de len ke
hoach ngan sach that, vi (a) 7,063 segment/cuon la so `[CHUA VERIFY]` PM cung cap chua co
nguon do dac, (b) he so phinh 3.4 lan la ngoai suy RC-1 chua duoc do lai tren 1 job glossary
day du that, (c) **quan trong nhat**: khong the trien khai (6.13.2) nen day mai mai la so ly
thuyet, khong bao gio thanh so that.

#### 6.13.4. Khuyen nghi cuoi cung

**KHONG dau tu build prompt caching cho nhanh Claude.** Ly do tong hop:

1. Khong co giai phap ky thuat kha thi ma khong fork `pdf2zh` (6.13.2) — vi pham nguyen tac
   "khong fix don gian, an toan" la dieu kien de task nay chuyen sang implement (xem yeu cau
   goc cua task).
2. `default_provider = "deepseek"` (`src/core/config.py:71`) — Claude **khong phai** duong
   dich mac dinh cua app. Nhanh Claude da duoc 6.6.2 xep hang **te nhat trong 6 provider tren
   duong pdf2zh** vi F6 (glossary lap lai + khong caching), va 6.6.7 da canh bao day la
   "duong phu thuoc rui ro".
3. DeepSeek — provider mac dinh, re nhat — **da tu dong huong loi context caching phia
   server ma khong can sua code gi** (V5, xac nhan tu `[CHUA VERIFY]` thanh **verified**).
   Dau tu rieng cho Claude, trong khi provider mac dinh da co san co che tuong duong mien
   phi, la uu tien sai.
4. Neu tuong lai co nhu cau that su chuyen sang Claude lam mac dinh (vd chat luong thuat ngu
   nganh banh), giai phap dung la **khong dung `-s openailiked` qua `pdf2zh` nua** ma xay
   1 duong dich rieng goi thang Anthropic Messages API native (nhu `ClaudeProvider` da co san
   o `src/services/claude_provider.py`, hien chi dung cho `cost_estimator.py`) — day la quyet
   dinh kien truc lon (bo qua toan bo co che chunking/cache/glossary cua `pdf2zh`, tu implement
   lai), **ngoai pham vi task nghien cuu nay**, can PRD + Architecture rieng neu duoc uu tien.

**Trang thai cac claim trong muc nay**: V1–V5 (6.13.1) da verify tu nguon that, ghi ro cach
verify. Uoc tinh 6.13.3 dung input `[CHUA VERIFY]` (segment count 7,063 do PM cung cap, chua
co nguon do dac) — **khong** duoc trich dan nhu so that o bat ky noi nao khac trong tai lieu
nay hay brief cho Dev/QA.

---



### [Architecture.md cũ] 6.14.6. QA gate (R5-03 + R6-03) — E2E song song 2 engine tren cung file that

#### 6.14.6. QA gate (R5-03 + R6-03) — E2E song song 2 engine tren cung file that

**File test**: `data/uploads/898a567a-5034-41ed-8a95-7fc7dc1b4ca9_Figoni, Paula - How baking
works_ exploring the fundamentals of baking science (2007_2008, Wiley) - libgen.li-1-25.pdf`,
**trang 14** (dung file va dung trang cua research CHANGELOG va cua ca 2 spike B6/B10 — khong
duoc doi sang file khac, moi so lieu doi chieu deu gan voi no).

**Bat buoc chay that, khong mock** (R5-03): provider that (DeepSeek — la provider mac dinh va co
key that trong `.env`), qua **`JobOrchestrator` cua app**, khong phai goi CLI bang tay.

| # | Buoc | Tieu chi PASS |
|---|---|---|
| 1 | Tao job voi `PDF_TRANSLATE_ENGINE=pdf2zh`, trang 14 | job `completed`, `translated_vi.pdf` ton tai |
| 2 | Tao job voi `PDF_TRANSLATE_ENGINE=babeldoc`, **cung file, cung trang** | job `completed` |
| 3 | Mo **ca hai** file output bang PyMuPDF, `get_text()` | ca hai `len(text) > 0`; text cua ban babeldoc chua **chu tieng Viet co dau** thuc su (khong phai `""`, khong phai text EN nguyen ban). Day chinh la kieu kiem tra da tim ra Bug #5 — **khong duoc dung o field `status`** |
| 4 | Dem so trang cua `mono_path` tung chunk | bang `page_end - page_start + 1` (chan bay B8) |
| 5 | Dem so muc danh sach xuong dong dung tren trang 14 cua ca 2 output | babeldoc **≥ 25/35** (research bang tay dat 31/35; nguong 25 de duong bien cho khac biet moi truong), pdf2zh giu nguyen ~0/35. Neu babeldoc < 25 → **khong release**, escalate: nghia la pipeline cua app lam mat tac dung cua `--split-short-lines` |
| 6 | Kiem tra khong con loi cat ngang tu (`"điện t"` / `"ử"`) trong output babeldoc | 0 truong hop |
| 7 | Ghi lai `chunk.rate_limit_hits`, `chunk.thread_used`, `duration_seconds` cua **ca hai** lan chay vao `docs/test-report.md` | So lieu that dau tien de tune 6.14.5 — **bat buoc bao cao ve Tech Lead** du PASS |
| 8 | Job `pdf_scan` (E2E OCR → dich, R6-03): 1 file scan that, `PDF_TRANSLATE_ENGINE=babeldoc` | Output co chu tieng Viet **that** (khong trong). Day la lan duy nhat chung minh cau noi 6.10 con dung voi engine moi |

**Golden files** (Protocol 5 muc 3): stdout/stderr that cua ca 2 lan chay luu vao
`tests/fixtures/babeldoc/` — moi mock ve sau phai sinh tu day. Spike B6/B10 cua Tech Lead cung
nen duoc Dev capture lai vao day o increment dau tien.

**Khoi tao moi truong** (R5-03): `babeldoc` phai cai bang venv **rieng** Python 3.12
(`uv tool install --python 3.12 "babeldoc==0.6.4"`) — Python 3.14 crash vi dung API private
`concurrent.futures.thread._WorkItem` (CHANGELOG). Neu tren may QA khong cai duoc, QA ghi dung
cau: `"release blocked pending live verification: babeldoc"`.

**Pin version (P0.1/P0.3, Final Decision U1/U4/V-4)**: lenh cai dat o tren PHAI ghim dung
`babeldoc==0.6.4`, khong duoc de trong (`uv tool install --python 3.12 babeldoc` se tu keo
version moi nhat tren PyPI trong tuong lai). Ly do: toan bo so do o T3/U1/U2 va toan bo thiet
ke G1e (overlay `insert_text(morph=…)`, U3) deu gan chat voi hanh vi cua dung ban 0.6.4 nay
(nguong goc xoay `il_creater_active.py:1292-1300` — dia chi da sua 2026-09-11 theo R5-05, bản
truoc ghi `il_creater.py:968-974` la class KHONG chay trong luong dich, xem 6.22.1; thu tu
"gian truoc bop sau" cua `typesetting.py`) —
doi version ma khong biet la doi silent, co the lam sai lech moi ket luan da verify. Repo nay
chua co script/CI tu dong hoa viec cai `babeldoc` (khong tim thay trong README, script setup,
hay Dockerfile — xem `docker/Dockerfile` va `docs/Architecture.md` section 7 cho danh sach day
du cac buoc cai dat thu cong); day la lenh huong dan THU CONG duy nhat, nen viec pin o day la
đủ cho toan bo project (khong can them file cai dat rieng). Neu sau nay them script tu dong
hoa (CI, Dockerfile), phai pin cung dung `==0.6.4` o do, khong duoc de mac dinh "latest".

---


### [Architecture.md cũ] 6.15.1. Nguồn xác thực (Protocol 5 R5-01)

#### 6.15.1. Nguồn xác thực (Protocol 5 R5-01)

| # | Claim | Nguồn |
|---|---|---|
| P-01 | `Job.job_type` (`translate` \| `parse_only`) **đã tồn tại** trong DB, không cần thêm cột | đọc trực tiếp `src/models/job.py` (field `job_type: str = Field(default="translate")`) |
| P-02 | `POST /api/jobs` đã nhận `job_type`, đã bỏ qua cost gate cho `parse_only`, nhưng gọi `_mark_parse_only_unsupported()` đánh `failed` ngay | đọc `src/api/routes/jobs.py::create_job` + `_mark_parse_only_unsupported()` |
| P-03 | `MinerURunner.parse_document(file_path, output_dir, parse_method="ocr"\|"txt", lang, start_page_id, end_page_id) -> MinerUResult(markdown_path, images_dir, quality, task_id, middle_json_path)` | đọc trực tiếp `src/services/mineru_runner.py` (interface nội bộ của team, contract MinerU đã VERIFIED ở §6.9.1) |
| P-04 | `run_job()` reject EPUB ở **Step 1**, TRƯỚC mọi rẽ nhánh khác | đọc `src/core/job_orchestrator.py::run_job` Step 1 |
| P-05 | `GET /api/jobs/{id}/download` trả **1 file đơn** qua `FileResponse`, media_type hardcode `application/pdf` | đọc `src/api/routes/download.py` |
| P-06 | `ebooklib` / `beautifulsoup4` / `markdownify` **không có** trong `.venv` của project | `importlib.metadata.distributions()` trên `.venv` thật — 0 kết quả cho cả 3 |
| P-07 | `ebooklib==0.20` + `beautifulsoup4==4.15.0` **cài và import được trên Python 3.14.7** (đúng Python của `.venv` project) | tự cài vào venv scratch riêng bằng `uv venv --python 3.14` + chạy `import ebooklib, bs4; epub.read_epub` — PASS |


### [Architecture.md cũ] 6.15.2. Phần của §6.8 CÒN DÙNG ĐƯỢC nguyên trạng

#### 6.15.2. Phần của §6.8 CÒN DÙNG ĐƯỢC nguyên trạng

- Quyết định lõi: `parse_only` chạy Parsing Engine (MinerU) rồi **dừng**, skip Translation Engine +
  Glossary + Unit Conversion (BR-PARSE-01). Không mâu thuẫn với bất kỳ thay đổi nào sau đó.
- Cột `job_type` — đã có sẵn (P-01), §6.8 không cần "ALTER TABLE" nữa.
- Mapping input → tham số MinerU: `pdf_digital` → `parse_method="txt"`, `pdf_scan` → `parse_method="ocr"`,
  cả hai qua HTTP async task flow của §6.9.3 (không gọi CLI `mineru`). Khớp 1:1 với P-03.
- Cấu trúc output `output/{job_id}/document.md` + `images/` (BR-PARSE-03). **Lưu ý (2026-09-08)**:
  cây thư mục đúng, nhưng **ví dụ tên file ảnh ở §6.8:1474-1481 (`page_003_img_01.png`) sai thực
  tế** — tên thật là SHA-256 + `.jpg` (xem L-6, §6.15.5). Không được viết test/AC theo mẫu tên đó.
- Chi phí LLM = 0 (BR-PARSE-05).

**Đã rà, KHÔNG liên quan tới `parse_only`** (ghi lại để người đọc sau không phải rà lại — xác nhận
bằng code chứ không suy đoán, Domain Expert kiểm độc lập cùng kết luận 2026-09-08):
- `babeldoc_toc_split_enabled` (Bug #7 Ca C) chỉ được đọc **một chỗ duy nhất**:
  `job_orchestrator.py:248`, bên trong property `_translator_runner`, mà property này chỉ được gọi
  từ `_process_chunk()`. `run_parse_only()` (S15-1) không đi qua `_process_chunk()`.
- `compress_pdf_images()` (US-16 / US-16 v2) chỉ được gọi tại `job_orchestrator.py:573-574` trong
  Step 8 của luồng translate, gate bởi `pdf_translate_engine == "babeldoc"`, input là `merged_path`.
  `parse_only` không có `merged_path` và không sinh PDF output → không có gì để nén.
- `MinerURunner.parse_document()` là HTTP call độc lập, không import gì từ `babeldoc_runner.py` /
  `image_compress.py`.


### [Architecture.md cũ] 6.15.6. Gate release bổ sung cho US-15 (Protocol 5 R5-03 + Protocol 6 R6-03)

#### 6.15.6. Gate release bổ sung cho US-15 (Protocol 5 R5-03 + Protocol 6 R6-03)

1. **R5-03 `txt` mode**: đã có **1 lần live** (run của Expert, task `cdbd0988-…`). QA vẫn **phải
   tự chạy lại qua `run_parse_only()` thật** của app, không qua script của Expert.
2. **R6-03 E2E**: tải ZIP về, **giải nén**, mở `document.md` → có chữ thật (**không chỉ tin
   `status`**); đếm `![](images/…)` và **mở ít nhất 1 ảnh thật**; kiểm 1 bảng HTML và **1 list 2
   cột trong Markdown thô** (L-3).
3. **Golden fixture (Protocol 5 mục 3)**: `tests/test_mineru_runner.py` hiện **không** trỏ tới
   `tests/fixtures/mineru/` (grep `fixtures/mineru|golden` → 0 kết quả) → mock đang là **viết
   tay**. Dev phải capture từ run thật vào
   `tests/fixtures/mineru/parse_only_txt_figoni25/` (`document.md`, `summary.json`, `middle.json`)
   và test S15-6 **phải** dùng chính `middle.json` này (998 span `score=1.0`).
4. **Regression chéo S15-10**: file đã có job `parse_only completed` → `create_job(translate)` phải
   ra **202 + job mới**.
5. **§6.21 (công thức)**: bắt buộc chạy đủ 5 case của bảng "Gate bắt buộc" ở §6.21.4.


### [Architecture.md cũ] 6.15.7. Cập nhật S15-8 sau khi US-22 hoàn tất (2026-09-10) — spec thi hành cho nhánh EPUB→Markdown

#### 6.15.7. Cập nhật S15-8 sau khi US-22 hoàn tất (2026-09-10) — spec thi hành cho nhánh EPUB→Markdown

S15-8 (§6.15.3) và §6.20.5 được viết **trước** khi US-22 implement xong. Mục này ghi lại các điểm
spec cũ **đã lệch với code thật** và là **spec thi hành** cho Dev. Ở đâu mâu thuẫn, **mục này
thắng**; phần S15-8 không bị mục này nhắc tới thì vẫn còn hiệu lực nguyên trạng (đặc biệt: quyết
định "MỘT loader, HAI projection", lý do bác `units_to_markdown()`, và toàn bộ §6.21.2).

**Nguồn xác thực (Protocol 5 R5-01)**: đọc trực tiếp code thật ở commit hiện tại —
`src/services/epub_document.py` (toàn file), `src/core/job_orchestrator.py:1208-1444`,
`src/api/routes/jobs.py:318-352, 575-600, 1018-1040`, `src/core/config.py`, `pyproject.toml:26`,
`uv.lock:1082`, và chạy thật `.venv/bin/python -c "import importlib.metadata as m;
print(m.version('markdownify'))"` → **`1.2.3`, đã cài, import được**.

##### A. Điểm LỆCH #1 (chặn implement thẳng theo spec cũ): `spine_documents` KHÔNG tồn tại

S15-8 giả định `EpubDocument` phơi ra `.spine_documents -> list[tuple[str, BeautifulSoup]]`. Code
thật **không có** thuộc tính này (grep `spine_documents` trong `src/` → 0 kết quả). Cấu trúc thật
của class (`epub_document.py:524-528`) chỉ có:

```
@dataclass
class EpubDocument:
    path: Path                      # đường dẫn file .epub gốc (giữ lại, đọc lại zip được)
    opf_dir: str                    # thư mục chứa .opf, từ META-INF/container.xml
    _units: list[EpubUnit]          # projection DỊCH, expose qua property `units`
```

`load()` (`:530-596`) parse soup của từng document trong spine **bên trong vòng lặp cục bộ rồi vứt
đi** — không giữ lại soup nào, và **không giữ lại cả danh sách `doc_href` theo thứ tự spine**.

**Spec đã cập nhật — Dev làm như sau** (rẻ hơn và ít rủi ro bộ nhớ hơn spec cũ):

1. Thêm field `_spine_hrefs: list[str] = field(default_factory=list)` + property công khai
   `spine_hrefs -> list[str]`. `load()` **append `doc_href` vào list này ngay sau guard X6**
   (`epub_document.py:566-573`, chỗ đã raise nếu `doc_href` không có trong zip) — tức thứ tự spine
   được tính **đúng MỘT lần**, ở **đúng loader chung**, thoả tinh thần "MỘT loader" của S15-8 mà
   **không** phải giữ toàn bộ soup của cả cuốn sách trong RAM.
2. `to_markdown(images_out_dir)` **mở lại `zipfile.ZipFile(self.path)`** và với mỗi href trong
   `self._spine_hrefs` gọi lại `_parse_xhtml(zf.read(href))` — dùng lại đúng helper `_parse_xhtml`
   đã có (`:323`, Y1: `features="xml"` + fallback có kiểm chứng), **không** viết parser thứ hai.
3. **KHÔNG** expose `spine_documents` như spec cũ. Lý do: 1 EPUB sách bánh vài trăm trang giữ đồng
   thời hàng trăm soup lxml là chi phí bộ nhớ vô ích khi consumer duy nhất (`to_markdown`) duyệt
   tuần tự một lần.
4. Ràng buộc R6-02 của S15-8 **vẫn giữ nguyên**: `to_markdown()` phải chạy trên **cùng một
   instance** đã `load()` (đọc `self._spine_hrefs`, `self.path`) — cấm gọi `load()` lần thứ hai bên
   trong `to_markdown()`. Đây chính là sợi dây lineage Reviewer phải trace.

##### B. Điểm LỆCH #2: `to_markdown()` phải tự đọc ảnh từ zip — `EpubDocument` hiện KHÔNG có API ảnh nào

`load()` chỉ đọc `META-INF/container.xml` + các XHTML trong spine. **Không có** method nào liệt kê
hay đọc ảnh. `to_markdown()` phải tự làm, và **điểm dễ sai nhất là gốc đường dẫn tương đối**:

- `src` của `<img>` là tương đối so với **chính file XHTML chứa nó**, **KHÔNG** phải so với
  `opf_dir`. Cách tính đúng:
  `zip_entry = posixpath.normpath(posixpath.join(posixpath.dirname(doc_href), src))`
  (`doc_href` ở đây đã là đường dẫn tuyệt đối trong zip, vì `load()` đã join `opf_dir` theo X6 —
  `:565`). Dùng lại đúng công thức này, đừng join `opf_dir` lần nữa (sẽ ra sai).
- Ghi bytes ra `images_out_dir / <basename>`, và rewrite `img["src"] = f"images/{basename}"`
  **trên soup, TRƯỚC khi gọi `markdownify`** (để `markdownify` tự sinh `![alt](images/x.jpg)`).
- **Trùng tên basename giữa 2 thư mục khác nhau** trong zip (ví dụ `ch1/img/f01.jpg` và
  `ch2/img/f01.jpg`): nếu tên đích đã tồn tại **và** bytes khác nhau → thêm hậu tố tăng dần
  (`f01_2.jpg`). Không được ghi đè im lặng (mất ảnh) và không được để 2 link Markdown trỏ nhầm nhau.
- `src` là URL tuyệt đối (`http://…`) hoặc `data:` URI → **giữ nguyên, không copy**.
- Entry không tồn tại trong zip → **không raise** (không được để 1 ảnh hỏng làm hỏng cả job
  parse-only); bỏ `src` về nguyên trạng và ghi 1 dòng log warning. Khác hẳn guard X6 của `load()`
  (ở đó lệch href = Bug #5 tái sinh, phải raise).

##### C. §6.21.2 (`normalize_sup_sub`) — CHƯA có code nào, KHÔNG có gì để tái dùng

Đã grep `src/` (`normalize_sup_sub|sup_sub|vulgar|fraction|6\.21`): **0 implementation**. Đây
**không** phải thiếu sót — nhánh PDF→Markdown của US-15 (đã xong) không hề chuẩn hoá gì, vì
Markdown do MinerU sinh, app không chen được vào (đúng như §6.21.3 đã ghi). Nghĩa là:

- Nhánh EPUB→Markdown là **consumer ĐẦU TIÊN** của §6.21.2 → Dev **phải viết mới** `normalize_sup_sub(soup)`
  đúng theo spec §6.21.2 (Bước 1 phân số + guard hỗn số, Bước 2 Unicode/ASCII fallback, 2 bảng ánh
  xạ). Đặt trong `src/services/epub_document.py` như §6.21.2 chỉ định.
- Bảng 7 dòng "Kết quả đã chạy thật" ở §6.21.2 là **bảng kỳ vọng test bắt buộc**, không phải ví dụ
  minh hoạ.
- Setting `markdown_supsub_style` (§6.21.2) **chưa tồn tại** trong `src/core/config.py` → Dev thêm
  mới: `markdown_supsub_style: Literal["unicode", "pandoc"] = "unicode"`, **`.env`-only**, KHÔNG
  thêm vào `SETTINGS_DB_OVERRIDABLE_FIELDS`.
- `normalize_sup_sub()` chạy trên **bản soup của `to_markdown()`**. Nó **không được** đụng tới
  luồng `units`/`write_translated()` của US-22 (EPUB→EPUB giữ `<sup>`/`<sub>` nguyên vẹn theo X2 —
  `tests/test_epub_document.py:275-289` đang assert đúng điều đó; làm hỏng assert này = phá US-22).

##### D. `markdownify` — ĐÃ CÀI, nhưng chưa pin đúng như S15-8 yêu cầu

`pyproject.toml:26` khai `markdownify>=1.2.3`; `uv.lock` khoá `1.2.3`; `.venv` cài `1.2.3`
(đã chạy thật). Không cần thêm dependency. **Nhưng** S15-8 ràng buộc "pin version" và hiện đang là
`>=` — vì `normalize_sup_sub()` đã xử lý xong `sup`/`sub` **trước** khi `markdownify` nhìn thấy,
rủi ro `sup_symbol` đổi mặc định đã bị vô hiệu hoá, **nhưng** hành vi `ol`/`ul` lồng/`img`/
`figcaption` vẫn phụ thuộc thư viện. Chốt: **giữ `>=1.2.3`** (không siết `==`, tránh xung đột
resolve về sau) và bù bằng **golden test bắt buộc** trên `ops/xhtml/chapter01.html` như S15-8 đã
yêu cầu — đổi version mà output đổi thì golden test đỏ ngay.

##### E. Wiring — vị trí sửa chính xác

| # | File / vị trí hiện tại | Việc phải làm |
|---|---|---|
| W-1 | `src/api/routes/jobs.py:318-332` `_reject_epub_parse_only()` | **XOÁ hàm** + 2 call site (`:588` trong `create_job`, `:1027` trong `create_batch`). Đây chính là chốt chặn 400 cần gỡ |
| W-2 | `src/api/routes/jobs.py:334-351` `_resolve_parse_method()` | Hiện `("auto", "epub")` → `"ocr"` — **vô nghĩa cho EPUB** (không có MinerU trong nhánh này). Sửa: trả **`None`** cho `file_type == "epub"`, và call site `:637-640` giữ `None` cho EPUB. `Job.parse_method` là cột nullable, `None` đúng nghĩa "không áp dụng" |
| W-3 | `src/core/job_orchestrator.py:1216-1227` (nhánh `if job.file_type == FileType.EPUB: raise EpubNotSupportedError`) | **Thay** bằng `return await self._run_epub_parse_only(job, db_session)`. Phải đặt **trước** `_count_pdf_pages()` (`:1231`) và trước guard/health MinerU (`:1241-1245`) — EPUB không dùng MinerU, và `job.total_pages` **luôn NULL** cho EPUB (`upload.page_count`, §6.20.6) |
| W-4 | `src/core/job_orchestrator.py:124` `EpubNotSupportedError` | Sau W-3 không còn call site nào → xoá class + import trong `tests/integration/test_job_orchestrator.py:15` và test `:1674` (test đó phải được **thay** bằng test nhánh mới, không xoá trắng) |
| W-5 | `web/index.html:91-96` (checkbox `parse_force_ocr`) | Ẩn khi `f.file_type === 'epub'` — đó là lựa chọn MinerU `txt`/`ocr`, không có nghĩa với EPUB. `web/js/app.js:300` gửi `parse_method` → phải gửi `undefined` cho EPUB |
| W-6 | `src/api/routes/download.py:65-67` | **Không phải sửa** — đã branch theo `job.job_type == "parse_only"` → `.zip`, không quan tâm `file_type`. Đây là lý do §6.15/S15-8 bắt output EPUB phải **giống hệt** cây output PDF |

##### F. `_run_epub_parse_only()` — hình dạng bắt buộc (R6-01 data lineage)

Method mới trên `JobOrchestrator`, **song song** với `_run_parse_only_pipeline()` (nhánh PDF), KHÔNG
nhét thêm `if` vào trong nhánh PDF (nhánh PDF gắn chặt với MinerU từ đầu tới cuối). Bắt buộc tái sử
dụng **nguyên xi** phần "đóng gói" của nhánh PDF (`job_orchestrator.py:1362-1444`) để 2 nhánh không
trôi khác nhau — Dev tách phần đó thành helper dùng chung
`_finalize_parse_only_output(job, markdown_text, image_files, db_session)`:

```
job.status = "parsing"; commit                     # KHÔNG gọi MinerU health, KHÔNG parse_method
doc = EpubDocument.load(Path(job.file_path))       # raise EpubDrmError/EpubParseError -> job failed
output_dir   = self._output_dir / job.id
images_dir   = output_dir / "images";  images_dir.mkdir(parents=True, exist_ok=True)
markdown_text = doc.to_markdown(images_out_dir=images_dir)     # <-- SỢI DÂY LINEAGE (R6-01)
_finalize_parse_only_output(...)   # ghi document.md, guard đọc lại, zip eager, guard zip,
                                   # output_path, actual_cost=0.0/"metered", completed, broadcast
```

Lineage tường minh (R6-01) — **artifact nào, ai đọc field nào**:

| Bước | Sinh ra | Bước sau đọc |
|---|---|---|
| `EpubDocument.load(job.file_path)` | instance `doc` (`_spine_hrefs`, `path`, `opf_dir`) | `doc.to_markdown()` đọc **chính instance này**, cấm `load()` lại |
| `doc.to_markdown(images_out_dir=output_dir/"images")` | **giá trị trả về** = chuỗi Markdown; **side effect** = các file ảnh trong `images_dir` | `_finalize_parse_only_output` ghi chuỗi đó vào `output_dir/"document.md"`, zip `document.md` + `images/*` |
| `output_dir/"parse_result.zip"` | file zip | `job.output_path`, rồi `download.py` |

Guard bắt buộc, **giống nhánh PDF, không được bỏ**: Markdown rỗng sau strip → raise
`ParseOnlyEmptyOutputError`; đọc **lại** `document.md` từ đĩa để kiểm (không tin biến trong RAM);
`zipfile.testzip()` + đếm entry `images/` khớp số file thật → `ParseOnlyZipGuardError`.

**Không** có cancel/timeout polling ở nhánh EPUB (không có tác vụ dài bên ngoài để poll — parse
thuần local, xong trong vài giây); `_should_cancel`/`MinerUCancelledError` là chuyện riêng của
MinerU. Guard `EpubDrmError`/`EpubParseError` đã có sẵn hình dạng HTTP 400 tương ứng ở
`jobs.py:365-390` cho luồng translate — ở đây rơi vào `except Exception` của `run_parse_only()`
(`:1294`) → `job.status="failed"` + `error_message`, đúng contract sẵn có.

##### G. Test bắt buộc (bổ sung cho §6.15.6)

1. **R6-02 nối 2 projection** (S15-8 đã yêu cầu, giữ nguyên): từ **một** `load()`, assert số
   `h2`/`h3` trong `to_markdown()` **==** số unit có `tag in {"h2","h3"}`. ⚠️ Lưu ý đã kiểm:
   `_is_droppable_content()` (`:282`) có thể **drop** một heading toàn chữ số (ví dụ `<h2>1</h2>`)
   khỏi `units` trong khi `to_markdown()` vẫn giữ nó → nếu file mẫu có ca này, assert phải trừ đúng
   số đó và **ghi rõ lý do trong test**, không được nới assert thành `>=` cho qua chuyện.
2. **Golden test** `to_markdown()` trên `ops/xhtml/chapter01.html` (S15-8): 10 `<img>`, 214
   `<strong>`, 26 `<em>`, 2 `h2`, 34 `h3` — các số này lấy từ chính bảng đo của S15-8.
3. **Bảng §6.21.2 7 dòng** cho `normalize_sup_sub()`, đặc biệt ca hỗn số N-1 (`1 1/3`, KHÔNG phải
   `11/3`).
4. **Không hồi quy US-22**: `tests/test_epub_document.py` phải **xanh nguyên** — `units` vẫn chứa
   `<sup>1</sup>/<sub>3</sub>` thô.
5. **R6-03 live E2E**: upload EPUB thật → `job_type=parse_only` → tải zip → giải nén → `document.md`
   có chữ thật + **mở được ít nhất 1 file trong `images/`**, và link `![](images/…)` trong Markdown
   trỏ đúng file tồn tại (không chỉ tin `status="completed"` — đây đúng là cách Bug #5 bị bắt).

---


### [Architecture.md cũ] 6.16.1. Nguồn xác thực (đo thật trên chính stack của project)

#### 6.16.1. Nguồn xác thực (đo thật trên chính stack của project)

Không suy đoán về SQLite/SQLAlchemy — chạy thật trên `.venv` của project (SQLAlchemy 2.0.52,
SQLModel 0.0.42, aiosqlite 0.22.1, Python 3.14.7) với đúng model `GlossaryEntry` hiện có:

| # | Đo được | Kết quả thật |
|---|---|---|
| G-01 | `col(GlossaryEntry.term_en).contains("ganache")` sinh SQL `term_en LIKE '%' \|\| 'ganache' \|\| '%'` | khớp row `"Ganache"` → **LIKE của SQLite case-insensitive cho ASCII, mặc định, không cần `lower()`** |
| G-02 | `.ilike("%GANACHE%")` sinh `lower(term_en) LIKE lower('%GANACHE%')` | cũng khớp — nhưng `lower()` của SQLite **cũng chỉ ASCII** |
| G-03 | `.ilike("%đường%")` trên row `"Đường Nâu"` | **0 kết quả**. `.ilike("%Đường%")` → 1 kết quả. Xác nhận EC-18.2 của BA là ĐÚNG: chữ Việt có dấu KHÔNG được fold hoa/thường |
| G-04 | `.ilike("%_%")` (gạch dưới thô) trên bảng 7 dòng | trả về **cả 7 dòng** — `_` là wildcard, không escape là lỗi thật, không phải lý thuyết |
| G-05 | `.contains("50%", autoescape=True)` sinh `term_en LIKE '%' \|\| '50/%' \|\| '%' ESCAPE '/'` | khớp đúng 1 dòng `"50% hydration"` — **`autoescape=True` là API đúng để dùng** |
| G-06 | `count_statement` và `list_statement` dùng **cùng 1 biểu thức điều kiện** OR `(term_en LIKE ... OR term_vi LIKE ...)` | `total` khớp đúng số dòng trả về (3/3) |


### [Architecture.md cũ] 6.17.1. Phát hiện chặn thiết kế: `updated_at` KHÔNG dùng làm mốc kết thúc được

#### 6.17.1. Phát hiện chặn thiết kế: `updated_at` KHÔNG dùng làm mốc kết thúc được

PRD US-19 giả định đây là thay đổi thuần tầng response ("các cột này ĐÃ có trong `Job` table, chỉ
thiếu ở tầng serialize"). Đúng cho `total_pages` và `started_at`. **Sai cho mốc kết thúc.**

Đo thật (grep toàn `src/`, đọc `src/models/job.py`):

| # | Sự thật | Hệ quả |
|---|---|---|
| H-01 | `Job.completed_at` chỉ được gán ở **đúng 1 chỗ**: nhánh thành công cuối `run_job()` (Step 10) | job `failed`/`cancelled`/`cost_capped` có `completed_at = NULL` |
| H-02 | `Job.updated_at` **không có `onupdate=`**, và chỉ có **1 writer duy nhất** trong toàn `src/`: `ProgressTracker.update()` (`src/core/progress_tracker.py`) — gọi sau MỖI chunk xong | với job `failed`, `updated_at` = lúc chunk **cuối cùng THÀNH CÔNG**, không phải lúc fail |
| H-03 | Nhánh fail của Step 7 `return` **trước** `progress_tracker.update()` | job fail ngay ở chunk 0 → `updated_at` vẫn bằng `created_at` → "thời gian dịch ≈ 0 giây" cho một job chạy 20 phút rồi chết |

Fallback `completed_at or updated_at` (cách làm hiển nhiên nhất) vì thế **cho ra con số sai một
cách im lặng** đúng ở kịch bản AC-19.2 của BA quan tâm nhất ("nó chạy bao lâu rồi mới chết?").


### [Architecture.md cũ] 6.18.1. Mâu thuẫn phải giải: BR-TERM-03 ($0 mặc định) vs "thuật ngữ chuyên môn" (cần LLM)

#### 6.18.1. Mâu thuẫn phải giải: BR-TERM-03 ($0 mặc định) vs "thuật ngữ chuyên môn" (cần LLM)

PM nêu đúng mâu thuẫn: rule-based miễn phí nhưng không phân biệt được `flour` (từ thường) với
`laminated dough` (thuật ngữ); LLM-based chính xác hơn nhưng tốn 1 lượt gọi/job kể cả khi user
không cần — vi phạm BR-TERM-03.

**Cách gỡ: đây không phải bài toán phân loại nhị phân, mà là bài toán XẾP HẠNG cho một danh sách
người duyệt.** Khu vực "Chờ duyệt" theo thiết kế của chính user là nơi user **triage bằng mắt** —
mỗi dòng có 2 nút "Thêm" / "Bỏ qua". Với giao diện đó, chi phí của một false-positive là **một cú
bấm**, còn chi phí của một false-negative là **thuật ngữ đó vĩnh viễn không bao giờ được gợi ý**.
Hai loại lỗi không hề đối xứng. Vậy nên tiêu chí đúng cho v1 là **recall cao + xếp hạng tốt**,
không phải precision cao.

Rule-based đạt được điều đó với chi phí $0. LLM không mua thêm được recall (nó chỉ lọc bớt), nên
trả tiền cho nó ở bước liệt kê là trả tiền cho thứ không cần thiết.

**Quyết định: rule-based cho bước LIỆT KÊ (mặc định, $0, đúng BR-TERM-03). LLM chỉ xuất hiện ở
nút "Gợi ý bản dịch" người dùng chủ động bấm.**

Chốt thêm 2 điều để rule-based không thành rác:
1. **N-gram 1–3 từ, không phải chỉ từ đơn** — EC-20.6 của BA đúng: `baker's percentage`,
   `double boiler`, `laminated dough` là nhóm giá trị nhất và trích xuất theo từ đơn bỏ sót toàn bộ.
2. ~~**Có bộ lọc từ phổ thông tiếng Anh**~~ — **ĐIỂM NÀY ĐÃ BỊ BÁC BỎ, xem §6.18.8.**

> ### ⚠️ §6.18.1 và §6.18.2 (bản 2026-09-08 sáng) ĐÃ BỊ THAY THẾ MỘT PHẦN
>
> **Khung tư duy** của §6.18.1 (đây là bài toán XẾP HẠNG cho người duyệt, không phải phân loại
> nhị phân; recall > precision; rule-based $0 mặc định, LLM chỉ khi user bấm) **giữ nguyên hiệu
> lực** — Domain Expert đã phản biện độc lập và đồng ý với khung này.
>
> **Hai thứ bị thay thế**, do (a) phản biện Domain Expert 2026-09-08 với số đo trên sách thật, và
> (b) **quyết định mới của user cùng ngày**:
> - **điểm 2 ở trên** (bộ lọc `en_common.txt` ~3.000 từ) — bị bác bỏ hoàn toàn, xem §6.18.8 mục T2;
> - **bước 6 của §6.18.2** (cắt cứng còn 40 term) — bị bác bỏ, xem §6.18.8 mục T1.
>
> Ví dụ minh hoạ "`flour` bị loại" trong đoạn văn trên **cũng sai với dữ liệu thật**: với danh
> sách phổ thông tiêu biểu (google-10000), `flour` xếp hạng **9751** nên **KHÔNG** bị lọc, trong
> khi `proof` (2933), `score` (1154), `cream` (2966), `rest` (1539), `turn`, `cup` — **đều là
> glossary entry thật của user** — thì **BỊ** lọc. Bộ lọc chạy ngược đúng hướng xấu nhất.
>
> Dev đọc **§6.18.8 trước**, rồi mới đọc §6.18.2 để lấy phần chưa bị thay thế.


### [Architecture.md cũ] 6.18.7. Cần PM/user quyết định (Tech Lead KHÔNG tự sửa)

#### 6.18.7. Cần PM/user quyết định (Tech Lead KHÔNG tự sửa)

1. **BR-TERM-04 (phạm vi "Bỏ qua")** — user đã chốt per-job. Tech Lead **thực hiện đúng** như chốt,
   nhưng ghi lại rủi ro đã đo được: cuốn thứ hai cùng chủ đề sẽ gợi ý lại đúng những từ user đã từ
   chối ở cuốn thứ nhất. Nếu sau 2-3 cuốn user thấy phiền, việc nâng lên "nhớ toàn cục" chỉ là đổi
   `UNIQUE(job_id, term_en)` thành một bảng `dismissed_terms(term_en)` riêng — không phá gì đã có.
   **Không cần quyết định lại bây giờ**, chỉ cần biết đường lùi tồn tại.
2. **EC-20.1 (từ đã có trong glossary nhưng tài liệu dùng bản dịch khác)** — v1 **không** phát hiện
   được (app không có cặp EN↔VI cho nhánh PDF, xem §6.6.2 R1). Đây là "đề xuất SỬA", khác hẳn "từ
   MỚI", và trộn chung sẽ khiến user vô tình ghi đè entry đã curate. **Ngoài scope US-20.** Ghi
   nhận: khi US-22 (§6.20) lên production, EPUB **sẽ có** cặp EN↔VI thật → tính năng "đề xuất sửa
   bản dịch" trở nên khả thi, nhưng chỉ cho EPUB.
3. **EC-20.5 (rác OCR leo vào danh sách)** — ~~`term_min_occurrences=3` lọc được phần lớn (lỗi OCR
   hiếm khi lặp y hệt 3 lần)~~. **SỬA 2026-09-08**: lập luận này **sai với lỗi hệ thống**. Đo
   thật trên Figoni: `avor` xuất hiện **638 lần**, `rst` 147 lần — artifact của tầng trích xuất
   text lặp lại hàng trăm lần, `min_occurrences` không phải phòng tuyến cho loại này. Phòng tuyến
   đúng là bước chuẩn hoá ở T2 (§6.18.8). `min_occurrences` vẫn giữ, nhưng chỉ với đúng vai trò
   "sàn tần suất", không phải "chống rác OCR".


### [Architecture.md cũ] T0. Số đo nền (kế thừa từ phản biện, Tech Lead KHÔNG đo lại)

##### T0. Số đo nền (kế thừa từ phản biện, Tech Lead KHÔNG đo lại)

Ghi rõ ranh giới kế thừa để Reviewer/QA biết cái gì đã được verify và bởi ai. Nguồn: Figoni *How
Baking Works* 415 trang (1.149.727 ký tự) + Cauvain *Baking Problems Solved* 298 trang, cả hai
trích bằng **chính `_extract_full_text()` của app** (`src/core/job_orchestrator.py:131`); glossary
thật 114 entry đọc từ `data/bb_translation.db`.

| Đo được | Figoni | Cauvain |
|---|---|---|
| Pool ứng viên sau lọc + khử lồng (`min_occ=3`) | **5.177** | 2.343 |
| Term user đã tự curate, xuất hiện ≥3 lần trong sách | 60 | 29 |
| **Median tần suất** của các term đó | **13** | 11 |
| Tần suất thấp nhất lọt top-40 theo spec cũ | ≥172 | ≥68 |
| **recall@40** (spec cũ) | **1/60** | 5/29 |
| recall@500 | 18/60 | 14/29 |

Kết luận không thể tránh: **term user thật sự muốn nằm rải rác từ hạng #11 tới #4438** — không có
công thức xếp hạng nào cứu được một con số trần cứng bằng 40. Đó là lý do quyết định (b) của user
là đúng về kỹ thuật, không chỉ là sở thích.


### [Architecture.md cũ] T7. Những điểm của Expert tôi KHÔNG làm theo (kèm lý do)

##### T7. Những điểm của Expert tôi KHÔNG làm theo (kèm lý do)

| Đề xuất Expert | Quyết định | Lý do |
|---|---|---|
| FD-2: giữ `en_common.txt` + thêm `baking_sense_allowlist.txt` | **Làm mạnh hơn: bỏ hẳn list** | Xem T2. Không phải bất đồng về phát hiện (phát hiện đúng 100%), mà là chọn cách sửa triệt để hơn — allowlist là vá lỗ cho một bộ lọc mà lý do tồn tại đã biến mất sau quyết định (b) của user |
| FD-3 (a)(c): **lọc bỏ** n-gram có hư từ ở giữa và tên riêng | **Đổi thành demote + ẩn mặc định** (T4) | Dưới luật mới, xoá vĩnh viễn vì lý do ngoài "đã có trong glossary" là thêm luật thứ hai; và `Swiss meringue`/`Silpat`/`Fahrenheit` là glossary entry thật lại đúng dạng tên riêng |
| FD-6: `max_suggested_terms_per_job = 500` (trần lưu) + UI phân trang 40 | **Trần lưu 20.000, UI phân trang 50** | 500 vẫn cắt mất **4.677/5.177** ứng viên của Figoni — vẫn là một con số tuỳ ý, đúng thứ user vừa bác. Giữ trần chỉ để chống tràn |
| FD-6: sàn tần suất theo số trang | **Đổi sang số token** | `total_pages` NULL cho EPUB theo thiết kế (§6.20.6) |
| FD-7: PM hỏi user đổi "trần 40" → "pool + phân trang" | **User đã trả lời rồi** (nguồn (b)) | Không hỏi lại |
| FD-7 (tuỳ chọn): nút trả phí thứ hai "Lọc bằng LLM" chạy trên pool | **KHÔNG làm ở v1** | Trực tiếp mâu thuẫn với luật user vừa chốt: điều kiện lọc **duy nhất** là glossary. Thêm một bộ lọc LLM là đưa lại đúng thứ vừa bị bỏ, lần này còn tốn tiền. (Số giá DeepSeek Expert nêu cũng còn `[CHƯA VERIFY]` phần alias `deepseek-chat`.) |
| FD-8: PM hỏi lại user về phạm vi BR-TERM-04, kèm số đo 17/40 dòng trùng nhau giữa 2 cuốn | **Đã hỏi, user giữ nguyên per-job** | User trả lời trực tiếp: *"Chỉ gợi ý các từ không có trong glossary"* cho cả câu hỏi về trùng lặp giữa nhiều cuốn. **Rủi ro Expert đo được vẫn ghi nhận nguyên trạng**: top-40 của Figoni và Cauvain (khác tác giả, khác nước, cách nhau 7 năm) trùng **17/40 dòng** — user sẽ gặp lại cùng bộ từ đó ở mọi cuốn nếu không bấm "Thêm". Giảm nhẹ: T1 (không còn top-40 nên 17 dòng đó không còn chiếm 40% màn hình đầu) + BR-TERM-02 (mỗi từ đã "Thêm" biến mất vĩnh viễn). Đường lùi vẫn nguyên: bảng `dismissed_terms(term_en)` riêng, không phá gì đã có |


### [Architecture.md cũ] T8. Gate release bổ sung cho US-20

##### T8. Gate release bổ sung cho US-20

1. **R6-02**: test lineage `pdf_scan` phải assert đọc **đúng `job.ocr_bridge_path`** (đã có ở
   §6.18.5), **và** test lineage `parse_only` phải assert đọc
   `Path(job.output_path).parent / "document.md"` — **không** phải `job.output_path` (nay là file
   `.zip`, S15-4).
2. **R6-03 live cho nhánh `pdf_scan`** `[CHƯA VERIFY]`: DB hiện chỉ có 9 job `pdf_digital`
   completed, **không còn `searchable.pdf` nào trên đĩa** → chưa ai đo được text layer của file
   cầu nối có mang lỗi OCR lặp (kiểu `ganaehe`) hay không. QA **phải** chạy 1 job `pdf_scan` thật
   và **mở danh sách gợi ý ra xem**, không chỉ tin là có rows.
3. **Test T3 với glossary THẬT**: assert `pound`, `ounce`, `bloom`, `tempering`, `whipping`,
   `kneading`, `teaspoon`, `crusts`, `meringues`, `mousses` **KHÔNG** xuất hiện trong danh sách
   gợi ý khi glossary thật (114 entry) đang được áp — đây là bài kiểm trực tiếp cho luật duy nhất
   user chốt.

---


### [Architecture.md cũ] 6.20.2. Sự thật đã verify về `bbook-maker==1.1.0`

#### 6.20.2. Sự thật đã verify về `bbook-maker==1.1.0`

| # | Sự thật | Nguồn | Hệ quả |
|---|---|---|---|
| E-01 | Cờ `--model`, `--claude_key`, `--openai_key`, `--prompt`, `--test`, `--test_num`, `--resume`, `--proxy`, `--api_base`, `--single_translate`, `--only_filelist`, `--exclude_filelist`, `--translate-tags`, `--accumulated_num`, `--use_context`, `--temperature`, `--block_size`, `--model_list`, `--interval` **đều tồn tại** | `bbook_maker --help` chạy thật | §6.7 cũ tình cờ đúng tên cờ |
| E-02 | `--single_translate` = "output translated book, no bilingual"; cài đặt: `insert_trans()` chèn `<p>` dịch ngay sau `<p>` gốc rồi `p.extract()` xoá bản gốc | `--help` + `loader/helper.py:19-31` | Ra được bản **đơn ngữ** — điểm §6.7 cũ đánh dấu `[CHƯA VERIFY]` |
| E-03 | `MODEL_DICT` = `{openai, chatgptapi, gpt4, gpt4omini, gpt4o, o1preview, o1, o1mini, o3mini, google, caiyun, deepl, deeplfree, claude, claude-3-5-*, gemini, geminipro, groq, tencentransmart, customapi, xai, qwen, qwen-mt-*}`. **KHÔNG có `deepseek`. KHÔNG có `ollama`** (ollama đi qua `--model chatgptapi --ollama_model <name>`) | `translator/__init__.py:14-42` | **Provider mặc định của app (DeepSeek) không được hỗ trợ native.** Phải lách qua `--model openai --model_list deepseek-chat --api_base https://api.deepseek.com/v1 --openai_key <deepseek key>` |
| E-04 | Output ghi **cạnh file input**, tên **cố định** `f"{input_stem}_bilingual.epub"` — kể cả khi `--single_translate`. **Không có cờ `--output`** nào | `loader/epub_loader.py:546,551` + `--help` (không có `--output`) | Runner phải copy input vào thư mục tạm riêng mỗi chunk (đúng bài học F9 của pdf2zh) |
| E-05 | `--only_filelist 'a.html,b.html'`: file **không** nằm trong danh sách thì `process_item()` `return` **mà KHÔNG gọi `new_book.add_item(item)`** | `loader/epub_loader.py:384-387` (đối chiếu: nhánh `exclude_filelist` ở `:388-391` **có** `add_item`) | EPUB output **bị thiếu hẳn** các chương không được chọn → không thể dùng làm cơ chế chunk nếu không tự ghép lại |
| E-06 | `make_bilingual_book()` bọc toàn bộ trong `except (KeyboardInterrupt, Exception) as e: print(e); … sys.exit(0)` | `loader/epub_loader.py:553-560` | **Mọi lỗi dịch thoát với exit code 0.** Runner kiểm `returncode` sẽ tưởng thành công |
| E-07 | **Chạy thật**: `bbook_maker --model claude --claude_key sk-ant-fake … --single_translate --test --test_num 2` → **EXIT CODE 0**, stdout in `Messages.create() got an unexpected keyword argument 'temperature'`, không sinh `book_bilingual.epub`, chỉ sinh `book_bilingual_temp.epub` + `.book.temp.bin` + thư mục `log/` | tự chạy, log giữ tại scratchpad | Xác nhận E-06 bằng thực nghiệm. Đồng thời: **đường Claude của tool HỎNG** với `anthropic` SDK hiện tại — `claude_translator.py:101` truyền `temperature=` vào `messages.create()`, mà SDK `anthropic` 1.3.0 (trong `.venv` project) và 1.4.0 (mới nhất) **đều không còn tham số này** (`inspect.signature` kiểm thật). `Requires-Dist: anthropic` **không pin version** → lỗi này sẽ tự tái diễn |
| E-08 | `ChatGPTAPI.translate()`: `except Exception as e: print(str(e)); return` → trả **`None`** cho từng đoạn lỗi (chỉ `RateLimitError` mới retry, tối đa 3 lần) | `translator/chatgptapi_translator.py:213-216` | Lỗi cấp-đoạn bị nuốt im lặng, không đếm được |
| E-09 | `insert_trans()`: `if text is None: text = ""` — rồi vẫn chèn `<p>` **rỗng** và (với `--single_translate`) **xoá bản gốc** | `loader/helper.py:19-31` | Kịch bản Bug #5 ở quy mô nguyên cuốn: chương trống, exit 0 |
| E-10 | `helper.translate_with_backoff` = `@backoff.on_exception(backoff.expo, Exception, …)` **không có `max_tries`/`max_time`** | `loader/helper.py:35-41` | Retry **vô hạn** trên nhánh `--accumulated_num > 1`. Với `--model claude` nó gọi `translate(text, context_flag)` (2 tham số) trong khi `Claude.translate(self, text)` chỉ nhận 1 → `TypeError` mỗi lần → vòng lặp không thoát |
| E-11 | **Không có bất kỳ token/usage/cost accounting nào** trong toàn package (grep `usage` trên `translator/`, `loader/`, `cli.py`, `utils.py` → 0 kết quả) | grep source đã cài | `cost_source` sẽ mãi là `'estimated'`, y hệt pdf2zh (§6.6.6) |
| E-12 | `--prompt` nhận chuỗi template / chuỗi JSON / đường dẫn `.txt`/`.json`/`.md`; placeholder là **`{text}`** và **`{language}`**, thay bằng `str.format()` | `cli.py::parse_prompt_arg` + `claude_translator.py:47-52` | Khác pdf2zh (`string.Template`, `${text}`): ở đây mọi dấu `{`/`}` trong glossary phải escape thành `{{`/`}}`. Prompt file của app **không dùng lại được** |
| E-13 | Trạng thái resume là 1 file **pickle** `.{stem}.temp.bin` cạnh input, chứa list bản dịch theo **chỉ số tuyến tính toàn sách** | `loader/epub_loader.py:115-120, 562-567, 613-618` | Không tương thích với chunk theo `--only_filelist` (chỉ số lệch nhau giữa các lần chạy khác tập file) |
| E-14 | `--model chatgptapi` với key sai → `set_gpt35_models()` gọi `models.list()` ngay lúc khởi tạo → **exit code 1** kèm traceback thật | tự chạy `--openai_key sk-fake-…` | Đây là nhánh DUY NHẤT fail-fast; nó xảy ra **trước** `make_bilingual_book()` nên không bị `sys.exit(0)` nuốt |


### [Architecture.md cũ] 6.20.3. Sự thật đã đo về cấu trúc EPUB thật và về `ebooklib`

#### 6.20.3. Sự thật đã đo về cấu trúc EPUB thật và về `ebooklib`

| # | Đo được trên file thật | Con số |
|---|---|---|
| B-01 | Số `ITEM_DOCUMENT` (tài liệu XHTML) trong cả cuốn | **5** (spine cũng 5) |
| B-02 | Phân bố ký tự văn bản theo tài liệu | `cover.html` 0 · `title.html` 32 · `copyright.html` 1.438 · **`chapter01.html` 50.899** · `backmatter01.html` 0 |
| B-03 | Tỉ lệ nội dung nằm trong 1 tài liệu duy nhất | **50.899 / 52.369 = 97,2%** |
| B-04 | Số đơn vị dịch (`p,h1..h6,li,blockquote,td,th`, bỏ đoạn rỗng/toàn số) | **384** (373 trong đó thuộc `chapter01.html`) |
| B-05 | `ebooklib==0.20` + `bs4` cài & chạy được trên **Python 3.14.7** (đúng Python của `.venv` project) | PASS |
| B-06 | `epub.write_epub()` round-trip: **dời toàn bộ thư mục** `ops/…` → `EPUB/…`, đổi tên OPF thành `content.opf`, ghi lại `container.xml`, và **ghi lại toàn bộ XHTML + `toc.ncx`** (bs4/lxml serialize lại) | 28 entry vào / 28 entry ra, ảnh + font + CSS giữ **byte-identical** (20/20), nhưng **mọi đường dẫn đổi** |
| B-07 | **Ghi đè tại chỗ bằng `zipfile`** (chỉ thay đúng entry XHTML đã dịch, giữ nguyên thứ tự entry, giữ `mimetype` là entry đầu + `ZIP_STORED`) | **27/27 entry còn lại byte-identical**, thứ tự entry giữ nguyên, `ebooklib` đọc lại OK (5 docs, spine 5) |
| B-08 | Không có `META-INF/encryption.xml` trong file mẫu | không DRM |

~~**B-03 là con số quyết định cả section này.**~~

> **SỬA SAU PHẢN BIỆN DOMAIN EXPERT (2026-09-08) — B-03 KHÔNG được phép là con số quyết định.**
> Expert tái lập độc lập toàn bộ B-01..B-08 bằng **stdlib** (`zipfile` + `html.parser` +
> `ElementTree`, không dùng chung code path với tôi) và xác nhận **mọi số đều đúng** (B-03 đo lại
> = 97,4%, lệch <0,3% do parser khác). **Nhưng** Expert đọc `ops/9781603424073.opf` và tìm ra
> điều tôi bỏ sót: `<dc:format>35 Pages</dc:format>`, `<dc:publisher>Storey Publishing</dc:publisher>`,
> mô tả *"Storey's Country Wisdom Bulletins"* — **đây là một bulletin 35 trang, N=1, KHÔNG đại
> diện cho sách thương mại**. NCX có đúng 1 navPoint nội dung; 34 "chương" thật (công thức) là
> `<h3>` **bên trong** 1 file XHTML. Một cookbook thương mại 200–400 trang thường tách 1 XHTML
> mỗi chương — trên sách như vậy `--only_filelist` của phương án A *có thể* chọn từng chương.
>
> Tức là **B-03 chỉ chứng minh A thất bại trên file này**, không chứng minh A thất bại nói chung.
> **Quyết định chọn phương án B KHÔNG đổi** (xem §6.20.4 đã sắp xếp lại thứ tự lý do) — nhưng
> Dev/QA phải biết ranh giới bằng chứng: mọi con số cấu trúc EPUB trong §6.20.3 là **N=1 trên một
> bulletin mỏng**. Xem thêm §6.20.11 mục 7 (xin user 1 EPUB sách dày thật trước spike).


### [Architecture.md cũ] 6.20.4. So sánh 2 phương án

#### 6.20.4. So sánh 2 phương án

| Tiêu chí | **A — `bilingual_book_maker` all-in-one** | **B — `ebooklib` parse + Translation Engine nội bộ** |
|---|---|---|
| Đơn vị chunk nhỏ nhất khả thi | **1 tài liệu XHTML** (`--only_filelist`, E-05) | **1 nhóm đoạn văn**, ngưỡng theo số ký tự — ta tự quyết |
| Áp lên sách thật (B-03) | 1 chunk chứa **97,2%** nội dung → Lớp 3 gần như **vô hiệu**, đúng thứ BR-EPUB-02 cấm | 52.369 ký tự → **7 chunk** (ngưỡng 8.000 ký tự), cân đối |
| Ghép lại sau khi chunk | Phải tự ghép: E-05 nói tài liệu ngoài `--only_filelist` **bị xoá khỏi output** | Không cần ghép EPUB — chỉ gộp mapping `unit_id → text` rồi ghi 1 lần |
| Resume (BR-CHUNK-05) | Pickle theo chỉ số toàn sách (E-13), **không tương thích** với chunk | Tái dùng nguyên `chunks` table đã có |
| Cost metering | **Không có gì** (E-11) → `cost_source='estimated'` vĩnh viễn | `provider.translate()` trả token thật → **`cost_source='metered'`** — pipeline ĐẦU TIÊN của dự án làm được |
| Provider mặc định (DeepSeek) | **Không hỗ trợ native** (E-03), phải lách qua `--model openai --model_list` | Hỗ trợ sẵn từ Increment 3 |
| Provider Claude | **Hỏng** với SDK hiện tại (E-07), hỏng **im lặng** | Hoạt động (Increment 3, `ClaudeProvider` riêng của app) |
| Hành vi khi lỗi | **exit 0** (E-06/E-07) + đoạn rỗng thay bản gốc (E-09) + retry vô hạn (E-10) | Exception Python bình thường, đi qua `with_retry` đã có |
| Glossary injection | Qua `--prompt` `{text}`/`{language}` (E-12) — phải viết prompt builder thứ 2 | `build_system_prompt()` đã có, dùng nguyên |
| Cancel giữa chừng | Không có (chỉ Ctrl-C) | Tái dùng `cancel_requested` đã verify sống ở QA Vòng 5 |
| Công phải tự viết | Runner + parse output + prompt builder riêng + tự ghép EPUB từ các phần | ~~Parse XHTML → unit, ghi ngược, chunk plan (~1 module)~~ → **đánh giá lại 2026-09-08: 1 module + contract JSON app↔LLM (X4) + giữ inline markup (X2) + guard bilingual (X3). Phần khó thật nằm ở đó, KHÔNG phải "vài chục dòng BeautifulSoup"** |
| Rủi ro Protocol 5 tồn dư | Cao — mọi hành vi phụ thuộc 1 tool không pin, đang đổi CLI (§6.20.1) | Thấp — `ebooklib`/`bs4` là thư viện Python thuần, dùng API core |

**4 tiêu chí BỔ SUNG sau phản biện Domain Expert (2026-09-08)** — Expert đọc source A và đo trên
chính file thật; 3 dòng đầu là **bằng chứng mới chống A**, dòng cuối là **chỗ tôi từng đánh giá B
quá lạc quan**:

| Tiêu chí (mới) | A | B (spec cũ) | B (sau khi sửa X1/X2) |
|---|---|---|---|
| Inline markup trong đoạn (`<strong>`, `<em>`, `<br/>`, `<a id>`) | **Mất hết**: A gán `new_p.string = text`; và A gửi `new_p.text` (`epub_loader.py:156`) — `.text` của bs4 nối string con **không có dấu cách**, trên đoạn nguyên liệu thật ra `'4 cups unbleached white flour2 teaspoons salt2 tablespoons honey…'` | **Mất hết** (spec cũ: "thay nội dung text của node") | Giữ được — gửi inner-HTML |
| Phân số `<sup>1</sup>/<sub>3</sub>` | **Phá** — A mặc định `exclude_translate_tags="sup"` (`cli.py:288`, `epub_loader.py:55`) | **Phá** (spec cũ mượn đúng rule đó của A) | Đúng — xem X1 + §6.21 |
| Dịch heading công thức | A mặc định `--translate-tags "p"` → **34 `<h3>` tiêu đề công thức KHÔNG được dịch** | dịch (danh sách tag gồm `h1..h6`) | như B |
| Chất lượng prompt | `DEFAULT_PROMPT` của A (`chatgptapi_translator.py:69`) là **đúng 1 câu** generic. Luận điểm "cộng đồng đã tối ưu prompt riêng cho EPUB" (nêu trong brief cho Expert) **không có thật** — Expert đọc source xác nhận | `build_system_prompt()` có glossary + unit conversion + typography rules | B hơn hẳn, **với điều kiện** có contract JSON (X4) |

Hệ quả: §6.20.11 mục 6 ("chất lượng dịch khác, không hiển nhiên tốt/xấu hơn") là **quá dè dặt
theo hướng có lợi cho A** — A không có ưu thế prompt nào. Đã sửa tại chỗ ở mục đó.

**Điều KHÔNG so sánh được (và tại sao nó không cứu được phương án A)**: A có ưu thế thật là "đã
tối ưu sẵn cho EPUB" — nhưng đọc source rồi thì phần "tối ưu" đó cụ thể là: chọn tag để dịch,
chèn `<p>` dịch cạnh `<p>` gốc, và giữ item không phải văn bản. Cả ba đều là vài chục dòng
`BeautifulSoup`. Đây **khác hẳn** lý do §6.6.2 R5 từ chối tự viết cho PDF: ở PDF, phần tự viết là
**layout engine** (line-breaking, reflow, font fallback, formula placeholder) — hàng tuần công.
EPUB là HTML reflow, **không có bài toán typeset nào cả**. Sự bất đối xứng đó là lý do quyết định
ở đây ngược với quyết định ở §6.6.2 mà không hề mâu thuẫn với nó.


### [Architecture.md cũ] 6.20.10. Gate release (Protocol 5 R5-03 + Protocol 6 R6-03)

#### 6.20.10. Gate release (Protocol 5 R5-03 + Protocol 6 R6-03)

Bắt buộc trước `ready_for_release` cho US-22:
1. **R5-02 (Dev spike, làm TRƯỚC khi implement đầy đủ)**: `ebooklib` + `bs4` + `markdownify` cài vào
   `.venv` thật của project, `EpubDocument.load()` + `write_translated()` chạy trên file EPUB thật
   trong `data/uploads/`, assert lại **B-07** (27/27 entry byte-identical, thứ tự entry giữ nguyên,
   `mimetype` đầu file + STORED). Nếu số đo khác §6.20.3 → escalate Tech Lead, **không** tự sửa
   thiết kế.

   **THỨ TỰ BẮT BUỘC trong spike (bổ sung sau phản biện Domain Expert 2026-09-08)** — 6 bước dưới
   đây phải xanh TRƯỚC khi viết implementation đầy đủ; mỗi bước là 1 điểm chặn X/Y đã biết, làm sai
   thứ tự thì lỗi chỉ lộ ra sau khi đã code xong:

   | # | Bước | Kỳ vọng (số đo đã có, Dev phải tái lập) |
   |---|---|---|
   | a | `doc_href` ∈ `zip.namelist()` cho **100%** unit (X6) | 5/5 document. Đo trước khi sửa: `item.file_name` **0/5**; sau khi join `opf_dir`: **5/5** |
   | b | Round-trip `chapter01.html` qua parser `xml` → `ET.fromstring()` OK (Y1) | 5/5 XHTML well-formed; `viewBox` **không** bị hạ thành `viewbox` |
   | c | 6 dòng `<sup>1</sup>/<sub>3</sub>` ra đúng (X1, §6.21) | `1/3 cup soy grits` ×5 **và** `1 1/3 cups unbleached white flour` ×1 — **không** phải `11/3` |
   | d | Đoạn nguyên liệu 4 `<br/>` ra đúng 4 dòng + giữ bold (X2) | inner-HTML giữ nguyên `<strong>…</strong><br/>×3` |
   | e | 1 request THẬT tới DeepSeek với payload JSON → **capture golden fixture** (X4) | `tests/fixtures/epub_llm/deepseek_batch_response_*.json`. **Cấm viết mock tay** — định dạng output LLM là external contract theo tinh thần Protocol 5 |
   | f | So ước tính (đã có X5) với `actual_cost` metered | tỉ lệ **≥ 1,0×** (được cao, cấm thấp — §6.11.6) |
2. **R5-03 (live, không mock)**: 1 job EPUB thật, provider thật (DeepSeek — rẻ nhất, đã verify sống
   nhiều lần), chạy hết. Xác nhận `cost_source='metered'` và `actual_cost` là **số đo thật khác 0**
   (đây là điểm khác biệt lớn nhất so với PDF; nếu nó ra `'estimated'` thì thiết kế đã bị hiểu sai).
3. **R6-03 (E2E xuyên suốt, kiểm NỘI DUNG output)**: **mở file `.epub` output ra**, đọc lại bằng
   `EpubDocument`, xác nhận có **tiếng Việt thật, đúng nghĩa** trong ít nhất 3 chương/đoạn khác
   nhau — không chỉ tin `status='completed'`. Đây đúng cách QA Vòng 3 tìm ra Bug #5.
4. **Cost gate sống**: hạ `max_cost_per_job_usd` xuống dưới ước tính đã biết của file đó → xác nhận
   **HTTP 402** và **không có `Job` row nào được tạo** (đếm bằng SQL, đúng cách QA Vòng 7 đã làm).
   Rồi `confirm_cost=true` + trần thấp → xác nhận job dừng ở `cost_capped` **giữa chừng**, tức
   **`chunk_index > 0`** — đây chính là điều BR-EPUB-02 yêu cầu và là điều phương án A không làm được.
5. **DRM**: upload 1 file EPUB có `META-INF/encryption.xml` (tự dựng bằng `zipfile`) → xác nhận
   400 với đúng câu tiếng Việt của AC-22.3, và file mẫu thật (B-08, không DRM) vẫn qua bình thường.
6. **Mở bằng reader THẬT (bổ sung sau phản biện Domain Expert 2026-09-08)** — bước 3 ở trên đọc lại
   bằng chính `EpubDocument`, tức là **app tự chấm điểm bài của app**; đúng thứ phản biện US-16 v2
   đã chỉ ra là không đủ. QA phải mở file output bằng **Apple Books hoặc Calibre viewer** và kiểm
   bằng mắt **1 công thức có phân số + danh sách nguyên liệu**: phân số phải là `1/3`/`1 1/3` (X1),
   4 nguyên liệu phải nằm **4 dòng** và còn in đậm (X2), bản VI nằm ngay dưới bản EN (bilingual).
   Trang trắng = triệu chứng XHTML không well-formed (Y1) — reader strict không báo lỗi.
7. **`epubcheck` nếu cài được** — bắt `duplicate id` (Y2: bản copy phải strip `id`; file thật có
   **32 unit** chứa `<a id="page_N"/>`) và well-formedness. `⚠️ ASSUMED, chưa verify`: chưa ai kiểm
   `epubcheck` có cài được trên máy này không. **Không cài được → không chặn release**, nhưng QA
   phải ghi rõ trong `test-report.md`: *"release blocked pending live verification: epubcheck"* nếu
   mục 6 cũng không chạy được (R5-03).


### [Architecture.md cũ] 6.20.11. Cần PM/user quyết định (Tech Lead KHÔNG tự sửa)

#### 6.20.11. Cần PM/user quyết định (Tech Lead KHÔNG tự sửa)

> **PM/user đã chốt (2026-09-08, qua AskUserQuestion, xem project_state.json)**: mục 1 và 2
> dưới đây ĐÃ CÓ quyết định — giữ nguyên phần phân tích của Tech Lead làm hồ sơ, nhưng Dev
> triển khai theo quyết định cuối trong dòng "→ CHỐT" của từng mục, không phải theo đề xuất
> nghiêng-về ban đầu.

1. **Thêm 3 cột DB → phải xoá/tạo lại DB dev.** `Job.finished_at` (§6.17.2), `Job.total_units`
   (§6.20.6), `Chunk.unit_start`/`unit_end` + đổi `Chunk.page_start`/`page_end` thành nullable
   (§6.20.7), cộng bảng mới `suggested_terms` (§6.18.3). Đây là tiền lệ đã có nhiều lần trong dự án
   (`SQLModel.metadata.create_all()` không thêm cột vào bảng đã tồn tại), nhưng **user sẽ mất lịch
   sử job hiện có**. Cần xác nhận: xoá DB dev, hay Dev viết 1 script migration `ALTER TABLE` nhỏ để
   giữ lịch sử? Tech Lead nghiêng về **script migration** lần này, vì tab Lịch sử vừa được đầu tư
   thêm tính năng ở chính đợt này (US-19) — xoá sạch lịch sử ngay khi vừa làm nó đẹp hơn là một
   trải nghiệm tệ.
   → **CHỐT: viết migration script (`ALTER TABLE`), KHÔNG xoá DB.** Xác nhận có dữ liệu thật cần
   giữ (`sqlite3 data/bb_translation.db "SELECT COUNT(*) FROM jobs, glossary_entries"` → 10 job đã
   dịch, 114 glossary entry đã curate, đo trực tiếp 2026-09-08) — đủ giá trị thực tế để bắt buộc
   theo hướng migration, không phải chỉ là sở thích. Dev phải viết script `ALTER TABLE` cho đúng 4
   thay đổi liệt kê ở trên trước khi chạm `SQLModel.metadata.create_all()`.
2. **`bilingual` cho EPUB** — `_OUTPUT_MODE_MAP` hiện có `monolingual`/`bilingual`, và §6.20.5 hỗ
   trợ cả hai với chi phí gần bằng 0. Nhưng PRD US-22 chỉ nói "output là 1 file `.epub` đã dịch".
   BA cũng đã hỏi (BA-Q6 câu phụ) và **chưa có câu trả lời**. Đề xuất: **bật `bilingual` cho EPUB
   luôn** (nó chỉ là chèn thêm `<p>` thay vì thay thế, không thêm chi phí LLM nào). Cần user xác nhận.
   → **CHỐT: bật `bilingual=True` mặc định cho EPUB.** Cập nhật PRD US-22 tương ứng (xem PRD.md).
3. **`EPUB_CHUNK_CHAR_BUDGET = 8.000` là con số CHỌN, chưa được kiểm chứng ở quy mô lớn.** Đo trên
   đúng 1 cuốn (B-04) cho 7 chunk — hợp lý cho việc chặn chi phí. Nhưng N=1, giống hệt tình trạng
   hằng số AIMD của babeldoc (xem `blockers` trong `project_state.json`). Đây là setting `.env`
   chỉnh được, không phải hằng số chôn trong code; ghi nhận là ⚠️ chưa kiểm chứng trên sách lớn.
4. **US-15 nhánh EPUB phụ thuộc §6.20** (S15-8). Nếu PM muốn US-15 ra trước US-22, nhánh EPUB của
   US-15 phải hoãn và trả 400 rõ ràng. Cần PM chốt thứ tự increment.
5. **`--single_translate`/Calibre/`ebook-convert` chính thức RA KHỎI scope.** Không cài Calibre,
   không có đường EPUB→PDF ở đợt này (BR-EPUB-01). Nếu sau này mở lại, 6 cờ `ebook-convert` trong
   §6.7 cũ **chưa từng được verify** và phải làm lại từ đầu theo R5-01.
6. **Rủi ro tồn dư của phương án B cần PM biết**: bản dịch EPUB đi qua **prompt của chính app**,
   nghĩa là chất lượng dịch EPUB sẽ **khác** chất lượng dịch PDF (PDF đi qua prompt của
   pdf2zh/babeldoc với ràng buộc riêng của chúng). ~~Không tốt hơn hay xấu hơn một cách hiển nhiên —
   chỉ là **khác**~~ → **SỬA 2026-09-08 sau phản biện Domain Expert: câu này quá dè dặt theo hướng
   có lợi cho phương án A, và sai với bằng chứng.** Expert đọc source A: `DEFAULT_PROMPT` của A
   (`chatgptapi_translator.py:69`) là **đúng 1 câu generic**, không có glossary, không có unit
   conversion, không có typography rule. **A không có ưu thế prompt nào** — luận điểm "cộng đồng đã
   tối ưu prompt riêng cho EPUB" (nêu trong brief) là **không có thật**. Rủi ro tồn dư thật của B
   nằm ở chỗ khác và đã được đóng ở §6.20.12: **contract JSON app↔LLM (X4)** — đây mới là phần app
   lần đầu tự chịu trách nhiệm, và là phần babeldoc đã phải viết cả một "mandatory per-paragraph
   JSON output contract" để giải. Đề nghị QA đọc kỹ nội dung 1 chương ở gate R6-03 (mục 3 của
   §6.20.10) **và mở bằng reader thật** (mục 6, mới), không chỉ đếm ký tự.
7. **[MỚI, cần PM xin user] Z1 — chỉ có đúng 1 file EPUB thật để làm bằng chứng.** Toàn bộ số đo
   §6.20.3 là **N=1 trên một bulletin 35 trang** (§6.20.3 đã ghi), và Expert xác nhận đây là file
   EPUB thật **duy nhất** trên máy (`~/Downloads/…Sourdough….epub` **byte-identical** với bản trong
   `data/uploads/`, `cmp` xác nhận). Hệ quả cụ thể: **Y2 và Y4 hiện là phòng thủ lý thuyết** — file
   mẫu có **0 `<table>`**, **0 `<ol>`/`<ul>`**, max unit chỉ **989 ký tự**, nên các rule cho bảng
   lồng, list lồng và unit quá khổ **chưa từng chạm dữ liệu thật lần nào**. Đề nghị PM xin user
   **≥1 EPUB cookbook dày thật** (nhiều chương) TRƯỚC spike R5-02, để Dev đo: số XHTML, có `<table>`
   không, nested list, max unit, SVG có text, EPUB3 `nav.xhtml`. **Không chặn v1** (guard X3 + Y4
   fail rõ ràng thay vì hỏng im lặng), nhưng nếu không có file này thì `EPUB_CHUNK_CHAR_BUDGET`,
   `EPUB_UNIT_HARD_MAX_CHARS` và toàn bộ Y2 phải vào known limitations của PRD với nhãn
   **⚠️ N=1, chưa kiểm chứng trên sách thương mại**.


### [Architecture.md cũ] Ranh giới bằng chứng (ai đã verify cái gì)

##### Ranh giới bằng chứng (ai đã verify cái gì)

| Nhóm | Ai đo | Tech Lead có đo lại không |
|---|---|---|
| B-01..B-08, E-03/05/06/09/10/11/13 | Expert, bằng stdlib + đọc source, **không dùng chung code path** với Tech Lead | Không — lặp lần 3 không tạo thêm thông tin |
| X1 (`sup` phá phân số), X2 (census inline markup), X6 (`doc_href`) | Expert đo trước | **CÓ, đo lại độc lập** — xem bảng dưới, và tìm thêm 3 điều Expert bỏ sót |
| X5 (envelope JSON) | Expert đo trên text thuần | **CÓ, đo lại + mở rộng** — Expert thiếu số hạng inner-HTML (§6.20.6) |
| X4 (không có contract JSON), Y6 (`with_retry` không retry 5xx) | Expert đọc code | **CÓ, tự đọc lại** `prompt_builder.py`, `openai_provider.py:66-93`, `retry.py:14-22` — xác nhận đúng |

**Ba điều Expert BỎ SÓT, Tech Lead tìm thêm khi tự đo (đây là lý do phải đo lại, không chỉ đọc):**

| # | Phát hiện mới | Số đo |
|---|---|---|
| N-1 | **Đề xuất sửa X1 của Expert (dùng `markdownify` mặc định) vẫn SAI ở ca hỗn số.** Expert chỉ đo dòng phân số thuần. Trên dòng thật `1<sup>1</sup>/<sub>3</sub> cups unbleached white flour`, `markdownify` mặc định cho ra **`11/3 cups`** — mười một phần ba thay vì một-và-một-phần-ba, **sai 8,25×** lượng bột. Cùng lớp lỗi với `/3 cup` mà Expert bác bỏ, chỉ khác cơ chế | tự chạy `markdownify==1.2.3` trên 6 dòng thật; 5/6 đúng, **1/6 sai**. Xem §6.21 |
| N-2 | **X2 (inner-HTML) có chi phí tiền bạc mà không ai tính**: nội dung gửi đi tăng **+9,3%** (57.247 vs 52.369 ký tự). Cộng với envelope thì tổng ước thấp là **29,0%**, không phải 19,6% như công thức của Expert | §6.20.6, bảng 3 dòng |
| N-3 | **Y1 (parser `xml`) đòi thêm dependency `lxml` — chưa có trong `.venv` project.** `BeautifulSoup(..., "xml")` không dùng được nếu thiếu `lxml` | tự dựng venv sạch chỉ có `beautifulsoup4==4.15.0` → `FeatureNotFound: Couldn't find a tree builder with the features you requested: xml`. Kiểm `.venv` project: **không có `lxml`, `bs4`, `ebooklib`, `markdownify`** |


### [Architecture.md cũ] Z1..Z3

##### Z1..Z3

- **Z1** (N=1, xin thêm EPUB dày) → chuyển thành **§6.20.11 mục 7**, việc của PM/user.
- **Z2** (bổ sung 4 dòng vào bảng so sánh, bỏ ngầm định "prompt cộng đồng") → **đã làm** tại
  §6.20.4 bảng "4 tiêu chí BỔ SUNG" + §6.20.11 mục 6.
- **Z3** (gọi đúng tên 2 ngân sách) → **đã làm** tại §6.20.7.


### [Architecture.md cũ] Điểm của Expert tôi KHÔNG làm theo (kèm lý do)

##### Điểm của Expert tôi KHÔNG làm theo (kèm lý do)

| Đề xuất Expert | Quyết định | Lý do |
|---|---|---|
| §6 mục 3(c): kỳ vọng spike "6 dòng `<sup>` ra đúng `1/3`" | **Siết chặt hơn**: 5 dòng ra `1/3` **và** 1 dòng ra `1 1/3` | N-1: chính `markdownify` mà Expert đề xuất cho ra `11/3` ở dòng hỗn số. Kỳ vọng như Expert viết sẽ **pass** cho một implementation vẫn sai |
| X2 "phương án tối thiểu nếu PM muốn giảm scope": `get_text("\n")` + tái tạo `<br/>` | **Từ chối phương án giảm scope** | Cứu dòng nhưng mất 214 `<strong>` — nửa nạc nửa mỡ của đúng Bug #7 vừa đóng, sẽ phải làm lại lần 2. Chi phí bản đầy đủ đã đo được là +9,3% token |
| FD X5(b): `EPUB_JSON_ENVELOPE_CHARS_PER_UNIT = 26` | **Đổi thành 30, và thêm `EPUB_INLINE_MARKUP_FACTOR = 1.15`** | 26 là số đo trần trụi (26,7 làm tròn **xuống**) và thiếu hẳn số hạng inner-HTML (N-2). Công thức của Expert vẫn ước thấp ~9% — vi phạm §6.11.6 ở đúng lớp bảo vệ tài chính mà chính Expert đang bảo vệ |
| Y1: "fallback `html.parser` khi XML parse fail" | **Nhận, nhưng thêm điều kiện** | Fallback chỉ được dùng khi **output sau fallback vẫn qua `ET.fromstring()`**. Fallback im lặng sang parser hạ-chữ-hoa-attribute là cách hỏng SVG mà không ai biết |


### [Architecture.md cũ] Trạng thái §6.20 sau mục này

##### Trạng thái §6.20 sau mục này

**Đủ điều kiện giao Dev**, với 2 điều kiện đi kèm: (a) spike R5-02 chạy đúng thứ tự 6 bước a→f của
§6.20.10 mục 1 **trước** khi viết implementation đầy đủ; (b) `lxml` + `ebooklib` + `bs4` +
`markdownify` được thêm vào `pyproject.toml` và **pin version** trong cùng commit đầu tiên.


### [Architecture.md cũ] 6.20.13.0. Ba điều Tech Lead tự verify khi thiết kế (đọc source thật, không suy đoán)

##### 6.20.13.0. Ba điều Tech Lead tự verify khi thiết kế (đọc source thật, không suy đoán)

| # | Sự thật | Nguồn xác thực (đọc trực tiếp trong phiên này) |
|---|---|---|
| **V-1** | **One-shot example của contract X4 đang dạy model trả về tiếng Việt KHÔNG DẤU.** `_EPUB_BATCH_ONE_SHOT_EXAMPLE` (`src/core/prompt_builder.py:427-433`) có `'Dau ra: {"0": "<strong>2 cups</strong> bot mi, 1<sup>1</sup>/<sub>3</sub> tsp muoi, nuong o 350F."}'` — `bot mi`, `muoi`, `nuong o` là tiếng Việt không dấu. Quét toàn khối `_EPUB_BATCH_CONTRACT` + one-shot (dòng 409-433): **0 ký tự có dấu tiếng Việt**, ký tự non-ASCII duy nhất là dấu gạch ngang `—` | tự chạy script đếm ký tự trên `src/core/prompt_builder.py` dòng 409-433 |
| **V-2** | **`max_tokens=8192` là trần CHO MỖI REQUEST** (`deepseek_provider.py:37` → `OpenAIProvider`), nên **134.274 token của 1 chunk KHÔNG THỂ đến từ 1 request duy nhất**. Chunk 0 (31 unit, ~3 request theo `EPUB_CHUNK_CHAR_BUDGET=8.000`/`EPUB_REQUEST_CHAR_BUDGET=3.000`) chỉ có thể đạt con số đó qua **vòng gọi lại RIÊNG LẺ** ở `job_orchestrator.py:1758-1774` — vòng này hiện **không có trần số lần**: 1 response hỏng/cụt → `parse_epub_batch_response()` trả `{}` → **mọi** id thiếu → tối đa `len(slice_units)` ≈ 18 request phụ **cho mỗi request hỏng**, mỗi request phụ lại gánh nguyên system prompt | đọc `job_orchestrator.py:1742-1783`, `deepseek_provider.py:29-47`, `prompt_builder.py:455-493` |
| **V-3** | **`TranslationResult` KHÔNG có `finish_reason`** (`src/services/translation.py:27-32`), và §6.20.12 X4 cấm đổi signature `provider.translate()` (interface chung 5 provider). ⇒ Mọi cơ chế phát hiện runaway ở mục này **bắt buộc** chỉ được dùng `input_tokens`/`output_tokens` đã có, KHÔNG được dựa vào cờ truncation của SDK | đọc `src/services/translation.py:27-46` |


### [Architecture.md cũ] 6.20.13.1. Phân tích lại Bug #EPUB-B2-1 — tách 3 nguyên nhân KHÁC NHAU bị gộp làm một

##### 6.20.13.1. Phân tích lại Bug #EPUB-B2-1 — tách 3 nguyên nhân KHÁC NHAU bị gộp làm một

Brief giao việc mô tả B2-1 như "hành vi ngẫu nhiên của model". Đọc lại số liệu QA thì đó chỉ là
**1 trong 3** thành phần, và **2 thành phần còn lại là tất định** (deterministic), lặp lại ở mọi
lần chạy:

| Thành phần | Bằng chứng | Tính chất |
|---|---|---|
| **C-1. Khuếch đại bởi vòng gọi lại từng-id không giới hạn** | V-2 ở trên: 1 response hỏng → tối đa ~18 request phụ. Đây là con đường DUY NHẤT (do trần `max_tokens`) để 1 chunk 31 unit đạt 134.274 token | Tất định **khi** có 1 response hỏng; hiện không có trần |
| **C-2. Ước tính THẤP có hệ thống, không phải chỉ ở lần chạy bất thường** | Lần chạy full-book **bình thường** (không có sự cố): `actual = $0,0626` cho cả 7 chunk vs `estimate = $0,034` → **1,84× ước tính**. Vi phạm trực tiếp §6.11.6 ("được ước cao, **cấm** ước thấp"). Brief nói "không có bằng chứng công thức sai" — số liệu của chính QA nói ngược lại | **Tất định**, xem §6.20.13.6 |
| **C-3. Model sinh dư/lặp output (runaway) ở 1 request cụ thể** | Không tái hiện ở lần 2 | Ngẫu nhiên, chỉ chặn được bằng heuristic |

**Hệ quả cho thứ tự ưu tiên fix**: C-1 và C-2 phải fix trước và **không cần ngưỡng đoán mò nào**;
C-3 mới là chỗ phải dùng heuristic có ngưỡng ⚠️ ASSUMED. Nếu chỉ fix C-3 (đúng nguyên văn brief)
thì phần tất định — vốn là phần chắc chắn tái diễn mỗi lần chạy — vẫn còn nguyên.


### [Architecture.md cũ] 6.20.13.9. Thứ tự implement bắt buộc cho Dev

##### 6.20.13.9. Thứ tự implement bắt buộc cho Dev

1. §6.20.13.4 (sửa one-shot + rule 7) — rẻ nhất, có thể tự nó xoá phần lớn Bug #EPUB-4.
2. §6.20.13.6 (`prompt_overhead_chars`) — phải làm **cùng lúc** với (1), vì (1) đổi độ dài prompt.
3. §6.20.13.2 (Lớp 4 trần chi phí per-request) — cost-safety, không phụ thuộc ngưỡng đoán.
4. §6.20.13.3a (trần số request phụ) → 3b (runaway detect).
5. §6.20.13.5 (guard dấu 2 tầng) → §6.20.13.7 (anomalies/requests log).
6. Task đo `chars/token` thật của DeepSeek (§6.20.13.6, dùng dữ liệu QA đã giữ, **không tốn API**).


### [Architecture.md cũ] 6.20.13.10. Gate release bổ sung cho vòng QA kế tiếp

##### 6.20.13.10. Gate release bổ sung cho vòng QA kế tiếp

Cộng vào checklist §6.20.10 (không thay thế):
- **G-1 (R6-03)**: chạy live full-book 1 lần, rồi đo lại **tỉ lệ unit mất dấu** trên file output
  bằng đúng script QA vòng 1/5 đã dùng. **Tiêu chí pass: 0 unit** thoả `letters ≥ 40 và
  ratio < 0,02`. Đây là điều kiện đóng Bug #EPUB-4, không phải "có tiếng Việt là được".
- **G-2 (R5-03)**: nộp `requests.jsonl` thật vào `test-report.md`, gồm **max output-ratio** và
  **p1/p5 của `diacritic_ratio`** đo được. Không có 2 số này → **không được** đánh dấu
  `ready_for_release`: mọi ngưỡng ở §6.20.13 vẫn còn là ⚠️ ASSUMED cho tới khi có chúng.
- **G-3 (cost)**: so `actual_cost` metered với `estimated_cost` của **cùng file đó** sau khi sửa
  §6.20.13.6. Tiêu chí §6.11.6: tỉ lệ `actual/estimate` phải **≤ 1,0** (được ước cao, cấm ước
  thấp). Lần đo trước fix là **1,84** — nếu vẫn > 1,0 thì phần C-2 chưa đóng, ghi rõ số đo và
  escalate Tech Lead thay vì tự chỉnh hằng số.
- **G-4 (Lớp 4)**: đặt `cost_cap` thấp hơn chi phí **1 request** → xác nhận job dừng
  `cost_capped` **giữa chừng 1 chunk** (chunk đó `failed`, `api_cost` khác 0, `output_path` là
  `NULL`), và file output **không** chứa bản dịch dở của chunk đó.

---


### [Architecture.md cũ] 6.20.14.0. Nguồn xác thực cho mọi con số dưới đây

##### 6.20.14.0. Nguồn xác thực cho mọi con số dưới đây

Toàn bộ số liệu trong section này **tự đo lại** từ golden fixture THẬT đã có trong repo
(`tests/fixtures/epub_llm/*.json`) + `docs/test-report.md` (QA vòng 3/5, 5/5) — **không gọi thêm API
lần nào**, đúng tinh thần "tiết kiệm". Cách đo: đọc `request_payload` của từng fixture, `json.dumps(...,
ensure_ascii=False)` để lấy đúng số ký tự payload thật đã gửi, đối chiếu `input_tokens`/`output_tokens`/
`estimated_cost_usd` do chính provider trả về.

**(a) Bảng tương quan "kích thước response ↔ JSON hỏng"** — mọi dòng đều là dữ liệu thật đã capture:

| Fixture / nguồn | Số unit | Payload chars | `output_tokens` | Kết quả JSON |
|---|---|---|---|---|
| `..._ch1_trailing_garbage.json` | 1 | 997 | 420 | Hỏng NHẸ (thừa đúng 1 dấu `"`) — cứu được |
| `..._ch1_5units.json` | 5 | 1.061 | 459 | **SẠCH hoàn toàn** |
| `..._ch1_multi_json_object.json` (B2-3) | 11 | 3.209 | 1.279 | Hỏng NẶNG — 11 object rời |
| `..._comma_separated_json_objects.json` (B2-4) | 32 | ~4.425 (suy từ `input_tokens`) | 1.392 | Hỏng NẶNG — 32 object rời, nối bằng `, ` |
| `..._single_object_spurious_closing_braces.json` (B2-5) | 32 | ~4.425 | 1.398 | Hỏng NẶNG — 1 `{`, 32 `}` |

**Giả thuyết chốt (⚠️ ASSUMED, chưa đủ mẫu để coi là quy luật)**: xác suất DeepSeek sinh JSON hỏng
NẶNG tăng theo ĐỘ DÀI OUTPUT, không theo độ dài input. Bằng chứng ủng hộ: cả 3 biến thể thảm hoạ đều
xảy ra ở `output_tokens ≥ 1.279`; chưa từng quan sát biến thể thảm hoạ nào ở `output_tokens ≤ 459`.
**Bằng chứng NGƯỢC lại phải ghi rõ, không được giấu**: QA vòng 5/5 lần chạy 2 có **14 lần gọi THÀNH
CÔNG** cho chunk 0-3 (173/384 unit → trung bình ~12,4 unit/request) — tức batch ~12 unit KHÔNG phải
lúc nào cũng hỏng. Vậy đây là quan hệ **xác suất**, không phải ngưỡng cứng: giảm batch làm GIẢM tần
suất lỗi, **không** loại bỏ được lỗi. Đó chính là lý do Lớp A một mình là không đủ và phải có Lớp B + C.

**(b) Đơn giá DeepSeek thật, suy ngược từ 2 fixture** (giải hệ 2 phương trình từ `input_tokens`,
`output_tokens`, `estimated_cost_usd` của `_ch1_5units` và `_multi_json_object`):

```
input  ≈ $0,22 / 1M token
output ≈ $0,66 / 1M token
```
Kiểm chứng độc lập trên fixture thứ 3 (B2-4, không dùng để giải hệ):
`2.299 × 2,2e-7 + 1.392 × 6,6e-7 = $0,0014245` — **khớp tuyệt đối** với `estimated_cost_usd` đã ghi
trong fixture. Hai đơn giá này do đó là VERIFIED, không phải suy đoán.

**(c) Chi phí cố định mỗi request (system prompt overhead)** — đây là con số quyết định "giảm batch
size tốn thêm bao nhiêu". Giải hệ `input_tokens = O + payload_chars / k` trên 2 fixture cùng đời
prompt (5 unit và 11 unit):

```
k ≈ 3,99 ký tự / token   (payload EN + markup)
O ≈ 1.190 input token / request   →  ≈ $0,000262 / request
```

---


### [Architecture.md cũ] 6.20.14.1. Chẩn đoán lại: vì sao hướng vá cũ KHÔNG hội tụ

##### 6.20.14.1. Chẩn đoán lại: vì sao hướng vá cũ KHÔNG hội tụ

Cả 3 fix B2-3/B2-4/B2-5 đều thuộc cùng một họ giả định: *"response là N giá trị JSON HỢP LỆ, chỉ khác
nhau ở thứ nối giữa chúng"*. B2-5 phá đúng giả định nền đó (chỉ có 1 dấu `{` trong toàn bộ response),
nên `_decode_concatenated_json_objects()` — dù đã tổng quát hoá đúng phạm vi nó nhắm tới — không thể
cứu được, đúng như Reviewer đã tiên liệu.

**Nhận định gốc**: `json.JSONDecoder` là công cụ **kiểm tra ngữ pháp**, mà thứ đang hỏng chính là ngữ
pháp. Mọi fix xây trên nó đều phải đoán trước hình dạng hỏng. Nội dung cần lấy ra thì lại **không hề
hỏng** ở cả 3 biến thể: 31/32 bản dịch của B2-5 đều đúng nghĩa, đủ dấu, đã trả tiền (QA tự mắt kiểm
tra `raw_text`). Điều BẤT BIẾN qua cả 3 biến thể — và là thứ duy nhất đáng dựa vào — là:

> mỗi bản dịch luôn xuất hiện dưới dạng một cặp `"<id>" : "<chuỗi JSON hợp lệ>"`, id nằm trong tập
> id ngắn cục bộ đã gửi đi.

Lớp B (§6.20.14.3) xây đúng trên bất biến đó và **không giả định gì về dấu ngoặc, dấu phẩy, hay cấu
trúc lồng nhau** — đó là điểm khác biệt về bản chất so với 3 fix trước, không phải "vá biến thể thứ 4".

---


### [Architecture.md cũ] 6.20.14.5. Tương tác với các guard đang có — bảng kiểm bắt buộc đọc trước khi code

##### 6.20.14.5. Tương tác với các guard đang có — bảng kiểm bắt buộc đọc trước khi code

Theo tinh thần Protocol 8 R8-01 (audit TỪNG bước có sẵn khi thêm hành vi mới vào một đường ống dùng
chung), không chỉ bước mới:

| Bước có sẵn | Có bị Lớp A/B/C ảnh hưởng? | Kết luận |
|---|---|---|
| Guard runaway C-3 (`is_runaway_output`) | Có — tỉ lệ tính trên `payload_chars` của chính request, batch nhỏ ⇒ `expected` nhỏ ⇒ ngưỡng có `EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS` che | **KHÔNG sửa** (floor đã đúng vai trò này). QA phải đo lại số false-positive từ `requests.jsonl` |
| Guard mất dấu tầng 1 (request) | Có — request ít unit hơn ⇒ `request_letters` nhỏ hơn ⇒ dễ tụt dưới `EPUB_DIACRITIC_MIN_LETTERS_REQUEST` ⇒ guard **im lặng bỏ qua** nhiều request hơn | **KHÔNG sửa ngưỡng** ở vòng này (tầng 2 mức unit không đổi, vẫn phủ). Ghi vào gate: QA báo số request bị bỏ qua vì thiếu chữ |
| Guard mất dấu tầng 2 (unit) | Không — đo trên từng unit, không phụ thuộc kích thước batch | Giữ nguyên |
| BR-EPUB-05 (output guard) | Có — unit fallback = giống bản gốc | Đã tính: ngưỡng job 5% < khe hở 10% (C-2) |
| Lớp 4 trần chi phí per-request | Có — nhiều request hơn ⇒ kiểm nhiều lần hơn, mỗi lần rẻ hơn | Tốt hơn, không sửa |
| Resume BR-CHUNK-05 | Không — checkpoint vẫn theo chunk | Giữ nguyên; C-3 đọc lại file để đếm đúng sau resume |
| Cost gate Lớp 2 | **Có — sẽ SAI nếu quên A-4** | Bắt buộc sửa cùng lúc |

---


### [Architecture.md cũ] 6.20.14.7. Thứ tự implement bắt buộc

##### 6.20.14.7. Thứ tự implement bắt buộc

1. **Lớp B trước** — offline hoàn toàn, 0 đồng API, verify ngay được trên 5 golden fixture đã có
   (gồm B2-5 hiện chưa có test nào). Đây là lớp duy nhất cứu được tiền đã trả cho response hỏng.
2. **A-4** (lineage cost gate) — làm cùng lúc với A-1/A-2, không được tách ra sau.
3. **A-1, A-2, A-3** — thuần config + 1 điều kiện cắt; test `plan_epub_chunks()` bằng unit giả có
   nhiều tag ngắn (tái hiện đúng ca 32 unit) ⇒ assert không request nào quá 6 unit.
4. **Lớp C** — C-1 → C-2 → C-3 → C-4 → C-5, theo đúng thứ tự đó (C-1 sai thứ tự sẽ làm guard mất dấu
   retry nhầm unit fallback).
5. Test R6-02 cho Lớp C: giả lập provider luôn trả thiếu đúng 1 id ⇒ assert job **completed**, file
   output chứa unit EN đó **có class `bb-untranslated`**, và `untranslated_units.json` có đúng 1 dòng.
   Giả lập trả thiếu 100% ⇒ assert vẫn `EpubBatchTranslationError` (E-09 chưa chết).

---


### [Architecture.md cũ] 6.20.14.8. Đã cân nhắc và HOÃN (giữ lại để không mất dấu vết suy nghĩ)

##### 6.20.14.8. Đã cân nhắc và HOÃN (giữ lại để không mất dấu vết suy nghĩ)

- **Bỏ JSON, dùng delimiter dạng `<<<ID>>>…<<<END>>>`** (hướng 2 của escalation-log): về lý thuyết xoá
  hẳn lớp lỗi "JSON syntax". Hoãn vì: phải viết lại contract prompt + parser + toàn bộ golden fixture
  (5 file, capture lại tốn API thật), và Lớp B đã lấy được ~90% lợi ích đó với ~30 dòng code, 0 đồng.
  Nếu sau khi có A+B+C mà tỉ lệ `salvaged_count > 0` vẫn cao trên dữ liệu live, đây là hướng tiếp theo.
- **`response_format={"type": "json_object"}` của DeepSeek** (hướng 3): hấp dẫn nhưng
  `TranslationProvider.translate()` là interface CHUNG cho 5 provider (Increment 3) — thêm tham số
  riêng cho 1 provider là sửa contract chéo, và bản thân khả năng hỗ trợ **chưa verify** với nguồn thật
  (R5-01). Không có số đo nào chứng minh nó tốt hơn A+B. Hoãn.
- **Chấp nhận rủi ro, dựa vào Retry của user** (hướng 4): bị chính chỉ đạo "ưu tiên nhanh" loại — QA đã
  chạy 3 lần full-book và không lần nào xong.

---


### [Architecture.md cũ] 6.20.14.9. Gate release cho vòng QA kế tiếp (cộng vào §6.20.10 và §6.20.13.10, không thay thế)

##### 6.20.14.9. Gate release cho vòng QA kế tiếp (cộng vào §6.20.10 và §6.20.13.10, không thay thế)

- **H-1 (R6-03, quan trọng nhất)**: chạy live full-book Sourdough **1 lần**, yêu cầu `job.status =
  completed` và **mở file `.epub` output ra xem chữ thật** — không tin field `status`.
- **H-2**: báo cáo từ `requests.jsonl`: tổng số request, phân bố `output_tokens` (max/p95), **số
  request có `salvaged_count > 0`**. Đây là bộ số duy nhất chốt được các ngưỡng ⚠️ ASSUMED ở
  §6.20.14.6 — thiếu nó thì mọi hằng số trên vẫn là giả định.
- **H-3**: báo cáo tổng số unit fallback (`untranslated_units.json`) và tỉ lệ trên 384 unit. **Tiêu chí
  pass đề xuất: ≤ 2%** cho lần chạy đầu tiên; > 5% thì job đã tự fail theo C-2 và phải escalate lại.
- **H-4 (cost)**: `actual/estimate` phải **≤ 1,0** (§6.11.6). Sau A-4, `estimate` sẽ tăng theo số
  request — nếu tỉ lệ này lần đầu tiên xuống dưới 1,0 thì đó chính là bằng chứng A-4 đã đóng đúng
  phần còn lại của C-2.
- **H-5**: diacritic ratio đo trên **384/384 unit** (mục tiêu 3 vòng QA trước chưa lần nào đạt vì job
  chưa từng chạy xong) — tiêu chí giữ nguyên: 0 unit thoả `letters ≥ 40 và ratio < 0,02`.

---


### [Architecture.md cũ] Nguồn xác thực (R5-01)

##### Nguồn xác thực (R5-01)

| # | Claim | Nguồn |
|---|---|---|
| S1 | Payload gửi LLM là `unit.text` = inner-HTML **nguyên trạng**, không có bước strip markup nào | `src/core/job_orchestrator.py:2372` (`payload = [{"id": str(i), "html": u.text} ...]`); `src/services/epub_document.py:786` (`text=_inner_html(own)` → `Tag.decode_contents()`) |
| S2 | Contract X4 **yêu cầu model tái tạo** `span` đúng số lượng/vị trí | `src/core/prompt_builder.py:418-419` (điều 3, `span` nằm trong danh sách) |
| S3 | Model **đã tái tạo đúng** koboSpan trong bản dịch | `data/processing/781b59b0-…/chunk_0/units.json` — mỗi giá trị dịch vẫn chứa `<span class="koboSpan" id="kobo.N.1" xmlns="…">` |
| S4 | `EPUB_REQUEST_CHAR_BUDGET` đo bằng **text thuần** (strip tag), không đo payload thật | `src/core/chunking.py:268-275` (`_plain_char_len()` = `_TAG_RE.sub("", unit.text)`) |
| S5 | `output_tokens` = `usage.completion_tokens` | `src/services/openai_provider.py:116` (DeepSeekProvider kế thừa, `deepseek_provider.py:29`) |
| S6 | DeepSeek V4 Flash: **thinking BẬT mặc định, effort mặc định `high`**; tắt bằng `{"thinking": {"type": "disabled"}}` (OpenAI format) | doc chính thức đã fetch 2026-09-11: <https://api-docs.deepseek.com/guides/thinking_mode/> — *"Thinking mode is enabled by default, with the default effort being `high`"* |
| S7 | Có `usage.completion_tokens_details.reasoning_tokens` để tách token thinking | doc chính thức DeepSeek (fetch 2026-09-11). **Chưa tự đọc field này trên response thật** → xem K-2 ⚠️ |
| S8 | 0 tham chiếu `href`/`idref`/`src` nào trỏ tới `id="kobo.*"` trong toàn bộ zip | quét thật `Sourdough Culture.epub`: 0/7.616 |
| S9 | Số đo phân bố `ratio` / `chars-per-output-token` | `data/processing/*/chunk_*/requests.jsonl` + `units.json` (797 request, 55 chunk, 3 sách) — số liệu ở design-log |


### [Architecture.md cũ] Thứ tự implement bắt buộc

##### Thứ tự implement bắt buộc

1. **Spike R5-02** (K-2/K-3): 1 request thật, capture `usage` → golden file. **Chặn** K-2, K-3.
2. K-5 (thuần logic, không phụ thuộc spike) → K-2 → K-3.
3. Chạy live 1 cuốn, thu số đo.
4. K-1 (độc lập hoàn toàn, có thể song song, nhưng **không** được báo là "fix Bug #EPUB-5").
5. K-4 cuối cùng, dựa trên số đo bước 3.


### [Architecture.md cũ] Gate release (cộng vào §6.20.10/§6.20.13.10/§6.20.14.9, không thay thế)

##### Gate release (cộng vào §6.20.10/§6.20.13.10/§6.20.14.9, không thay thế)

- **G-1**: golden file `usage` thật tồn tại, có `reasoning_tokens` (R5-03).
- **G-2**: sau K-2/K-3/K-5, chạy hết **1 cuốn** (`Sourdough Culture`, 66 chunk) không abort vì R-b;
  ghi `max(runaway_ratio)` vào `test-report.md`.
- **G-3** (R6-02): test assert `write_translated()` và `load()` dùng **cùng** hàm unwrap — cụ thể
  mở file output và assert `koboSpan` không còn xuất hiện, **và** `len(guard_doc.units) ==
  len(source_doc.units)`.
- **G-4** (R6-03): mở EPUB output thật, xác nhận có chữ tiếng Việt CÓ DẤU, không chỉ tin
  `status = completed`.

---


### [Architecture.md cũ] 6.22.3. Tín hiệu quan sát được (Bước 2) — 3 phương án đã cân đo

#### 6.22.3. Tín hiệu quan sát được (Bước 2) — 3 phương án đã cân đo

**(a) Log ra stdout — CÓ, đã đo thật.**
`pdf_creater.py:831-835` (bên trong `PDFCreater.render_paragraph_to_char`):

```python
if not chars and paragraph.unicode and paragraph.debug_id:
    logger.error(
        f"Unable to export paragraphs that have "
        f"not yet been formatted: {paragraph}",
    )
```

Đây **chính xác** là điều kiện drop ở 6.22.2 (composition rỗng → `chars` rỗng, nhưng `unicode` vẫn
còn bản dịch). Cấu hình log: `main.py:918-920` — `logging.basicConfig(level=logging.INFO,
handlers=[RichHandler()])`, và `RichHandler` mặc định ghi ra **stdout** (đo thật, xem dưới) — cùng
đường với tín hiệu rate-limit mà 6.12/6.14.3 đã dùng.

Đo thật (chạy bằng chính interpreter của tool env babeldoc, dựng lại đúng `basicConfig` + `logger`
name + một `PdfParagraph` thật, rồi tách stdout/stderr):

- `stderr` rỗng **0 byte**; toàn bộ dòng nằm ở `stdout`. ✅
- Ở bề rộng mặc định (80 cột) rich **bẻ dòng và cắt cả giữa token** — câu sentinel bị xé thành
  `Unable to` / `export paragraphs that have not yet` / `been formatted:`. Neo theo cụm từ sẽ HỎNG.
- Ở `COLUMNS=200` — đúng giá trị `BabeldocRunner` **đã set sẵn** (`babeldoc_runner.py:374`:
  `env = {**os.environ, **service.envs, "COLUMNS": "200"}`) — cụm sentinel
  `Unable to export paragraphs that have not yet been formatted:` **nằm trọn trên 1 dòng**; chỉ
  phần `repr(paragraph)` phía sau bị wrap sang các dòng tiếp theo (và có thể cắt giữa từ tiếng
  Việt).

⇒ stdout dùng được để **ĐẾM** số lần drop, nhưng **không** dùng được để trích payload
(`unicode`, `box`, `debug_id`) một cách tin cậy, và **không** chứa số trang.

**(b) Structure/metadata trả về từ Python — KHÔNG có đường trực tiếp.**
App gọi babeldoc bằng `asyncio.create_subprocess_exec` ở một venv `uv tool` riêng
(`babeldoc_runner.py:392-398`), không import babeldoc trong process app. CLI không có flag nào xuất
báo cáo drop; `PDFCreater.write()` trả về đường dẫn file, không trả thống kê.
**NHƯNG** repo này đã có sẵn cơ chế can thiệp hợp lệ: **shim `PYTHONPATH`**
(`src/babeldoc_shim/sitecustomize.py`, 744 dòng — dựng cho Bug #7 và Bug #10), gồm meta-path finder
+ loader bọc từng module babeldoc, có **version gate** (`_EXPECTED_BABELDOC_VERSION = "0.6.4"`) và
fail-safe (patch lỗi → log cảnh báo, chạy hành vi gốc). Đây là đường lấy dữ liệu **có cấu trúc**,
đúng tiền lệ đã qua review của chính project.

**(c) Heuristic gián tiếp trên PDF output — có nhưng KHÔNG chọn làm nguồn chính.**
So độ dài text input/output (PyMuPDF) chỉ cho tín hiệu mức trang, lẫn với nhiều nguyên nhân khác
(chữ xoay bị bỏ — đã có `overlay_rotated_text` xử lý; text trong ảnh; tiếng Việt ngắn/dài hơn bản
gốc). Không phân biệt được "drop vì không fit" với "dịch cô đọng hơn". Giữ làm ghi chú, không
implement.

**Chốt**: nguồn chính = **(b) shim**, nguồn đối chiếu = **(a) đếm sentinel trên stdout**.


### [Architecture.md cũ] 6.22.6.1.a. BL-08 — thứ tự ưu tiên và điểm khởi đầu (Domain Expert X6, 2026-09-11)

##### 6.22.6.1.a. BL-08 — thứ tự ưu tiên và điểm khởi đầu (Domain Expert X6, 2026-09-11)

**BL-08 KHÔNG phải mục "nice to have" treo vô thời hạn trong backlog.** Ghi vào hợp đồng để quyết
định này không tồn tại dưới dạng nhật ký:

- **Quy mô đo được của kênh (2) LỚN HƠN kênh (1) mà BL-04 đang vá** — trên cùng cuốn Le Cordon Bleu
  (job `1ee1fdee`, 418 trang): kênh (2) làm mất **~976 ký tự dọc** trên **52/418 trang** (2.303 ký
  tự dọc nguồn → 1.327 ở output), **gồm 2 tiêu đề chương thật** (trang 19: *"History of Pâtisserie
  in France"*; trang 31: *"A Life and Career in the Pastry Kitchen"*). Kênh (1) mà BL-04 vá: **614
  ký tự**, 1 đoạn (trang 230).
- BL-04 vẫn đi trước vì kênh (1) hiện **hoàn toàn không có cơ chế nào** phát hiện, còn kênh (2) có
  `overlay_rotated_text` phủ **một phần**. Nhưng điều đó có nghĩa: sau BL-04, **BL-08 là hạng mục
  ưu tiên cao nhất còn lại của mảng mất-chữ**. Xếp **ngay sau BL-04**.
- Nếu BL-08 bị đẩy lùi sau một hạng mục khác, **phải ghi lý do vào `docs/design-log.md`** — không
  được im lặng trôi xuống cuối backlog.

**Điểm khởi đầu đã có sẵn — đừng bắt đầu từ số 0** (đã verify, Domain Expert X6c):
`run_layout_qa_gate()` (`src/services/layout_qa.py:386`) đã chứa sẵn `_check_rotated_text_prescan()`
(`:278-310`) — quét **file GỐC**, bắt mọi dòng chữ xoay kèm `bbox` + text đầy đủ, severity
`blocker`, có test (`tests/test_layout_qa.py:116+`). Nhưng nó là **dead code trong production**:
`grep -rn "run_layout_qa_gate" src/ web/ scripts/` (tự chạy lại 2026-09-11) chỉ trả về **đúng 1
dòng — chính định nghĩa hàm** (`layout_qa.py:386`), **0 call site**; người gọi duy nhất là
`tests/test_layout_qa.py:30`. Đó là lý
do **thứ hai** (ngoài "overlay không phủ hết") khiến job `1ee1fdee` có 0 row `layout_qa_findings`:
bộ dò đã tồn tại nhưng **không nằm trên đường chạy**.

⚠️ **KHÔNG được bật nguyên trạng hàm đó — kể cả trong BL-08, kể cả "cho nhanh"**: trên cuốn này nó
sẽ sinh **≥52 finding `blocker`/cuốn** cho **mọi** dòng chữ xoay, kể cả những dòng
`overlay_rotated_text` đã khôi phục thành công ⇒ đúng loại báo động giả có hệ thống mà QA sẽ học
cách bỏ qua. Việc thật của BL-08 là biến *"có chữ xoay"* thành *"chữ xoay **bị mất**"* (đối chiếu
gốc ↔ dịch) và đặt ngưỡng **sau khi** đo nhiễu. **BL-04 không bật, không sửa, không gọi
`run_layout_qa_gate()`.**


### [Architecture.md cũ] 6.22.8. Vị trí sửa (spec cho Dev — CHƯA implement)

#### 6.22.8. Vị trí sửa (spec cho Dev — CHƯA implement)

| File | Việc |
|---|---|
| `src/babeldoc_shim/sitecustomize.py` | thêm `_PDF_CREATER_MODULE_NAME`, `_drop_report_enabled()`, `_build_patched_create_render_units_for_page()`, `_apply_pdf_creater_patch()`, và **1 lời gọi `_install_patch_hook(...)` thứ ba** trong `_install_hook_if_version_matches()` |
| `src/babeldoc_shim/drop_report.py` (mới) | hàm thuần: predicate `_has_rendered_chars`, dựng dict record `header`/`page`/`drop`, ghi append 1 dòng JSONL. Tách module để test được không cần babeldoc — cùng pattern `word_wrap.py`/`line_split.py` |
| `src/core/chunking.py` | **mới**: `surviving_page_range(chunk, *, is_first_in_merge)` + Protocol `_ChunkLike` (6.22.5.1). Đặt ở đây vì đây là module định nghĩa luật chồng lấn (`calculate_chunks`); dùng structural typing nên **không** import `src.models.chunk`. `page_start`/`page_end` khai **`int \| None`** khớp model nullable, và **raise `ValueError`** khi gặp `None` (X2) |
| `src/postprocess/chunk_merge.py` | thay khối `:85-91` bằng lời gọi `surviving_page_range(...)` (**giữ nguyên hành vi**, **giữ nguyên guard `overlap_* is not None`**); **KHÔNG** chuyển phần kẹp `end` theo `chunk_doc.page_count` (`:95-107`) vào hàm chung — X3; thêm `logger.warning` khi `position != chunk.chunk_index` (bất biến ở 6.22.5.1) |
| `src/services/babeldoc_runner.py` | 2 dataclass mới (`BabeldocDroppedParagraph`, `BabeldocDropReport` — shape đầy đủ ở 6.22.5); `drop_report_enabled` trong `__init__`; set 2 env var; **tạo `drop_report_path` TRONG `output_dir`** (ràng buộc 6.22.4); parse file sau `process.wait()` (không giả định vị trí dòng header, đếm `malformed_line_count`); đếm sentinel; thêm `drop_report` vào `BabeldocResult`; `reports_own_paragraph_drops: ClassVar[bool] = True` |
| `src/services/pdf2zh_runner.py` | `reports_own_paragraph_drops: ClassVar[bool] = False` |
| `src/services/layout_qa.py` | 3 hằng số `check_type` mới + **3 khoá mới trong `_SEVERITY_BY_CHECK`** (`:76-84`) — F6, nguồn sự thật duy nhất cho severity |
| `src/core/job_orchestrator.py` | property `_reports_own_paragraph_drops` (đặt ngay sau `_needs_font_shrink`); trong `_process_chunk()`, **sau** khối `OverflowReport` hiện có: lọc dải trang sống sót (6.22.5.1) → đối chiếu `observed_pages` (6.22.6 trạng thái 3) → map sang `LayoutQaFindingData` (severity tra từ `_SEVERITY_BY_CHECK`) → `persist_findings(...)` → **log R-1**; trong `run_job()` Bước 10 thêm **log R-2** trước `job.status = "completed"` (`:807`), đếm bằng **1 câu `SELECT COUNT` trên DB** — **KHÔNG** đếm từ list in-memory (X7, xem 6.22.6.2). Toàn bộ bọc `try/except` best-effort giống `:749-770` |
| `src/core/config.py` | `babeldoc_drop_report_enabled: bool = True` |

**KHÔNG sửa**: `src/postprocess/font_shrink.py`, `src/models/overflow.py`, schema `overflow_reports`,
và **vòng `for page_num in range(chunk.page_start - 1, …)` tại `job_orchestrator.py:1901`** (lỗi
chồng lấn cùng loại của nhánh pdf2zh — backlog BL-07, xem 6.22.5.1). `layout_qa_findings` **không
cần migration** (`check_type` là cột `str` tự do).


### [Architecture.md cũ] 6.22.9. Gate kiểm thử

#### 6.22.9. Gate kiểm thử

**Unit / integration (R6-02 — assert giá trị, không assert "đã gọi")**:
1. `test_drop_report_parse`: từ **golden file** JSONL (`tests/fixtures/babeldoc/drop_report_v2.jsonl`,
   sinh từ lần chạy thật ở E2E dưới, **không viết tay**) → assert đúng số record, đúng
   `page_number`, đúng `text_excerpt`, đúng `observed_pages`.
2. `test_drop_report_unavailable`: file không tồn tại → `available=False` → orchestrator ghi **đúng
   1** finding `babeldoc_drop_report_unavailable` và **0** finding drop. Test chống silent failure.
3. `test_drop_report_incomplete` (**mới, F2**): golden file bị **cắt bớt** record `type="page"` của
   vài trang → `observed_pages != expected_pages` → ghi đúng 1 finding
   `babeldoc_drop_report_incomplete` với `detail["missing"]` đúng danh sách trang thiếu, **đồng
   thời** vẫn ghi các finding drop đã quan sát được. Đây là test chứng minh "patch đã cài" không bị
   nhầm thành "đã quan sát".
4. `test_overlap_pages_filtered` (**mới, F1**): chunk `page_start=39, page_end=80, overlap_end=40`,
   `chunk_index=1`, drop report có record ở trang 39, 40 **và** 55 → chỉ **1** finding được ghi, và
   `page_number == 55`. Assert cả `suppressed_overlap_count == 2`.
5. `test_surviving_range_shared` (**mới, F1**): `surviving_page_range()` cho toàn bộ chunk plan của
   một tài liệu 418 trang → các dải **rời nhau và hợp lại đúng `[1, 418]`**; và với mỗi chunk, giá
   trị `start` trả về **bằng đúng `actual_start`** mà `merge_chunk_pdfs()` tính ra (đảm bảo bằng
   cách refactor cho `merge_chunk_pdfs` gọi chính hàm chung, không chép công thức vào test).
   ⚠️ **KHÔNG** assert dải này bằng số trang thực sự được `insert_pdf` vào file merge — X3: phần
   kẹp `end` theo `chunk_doc.page_count` (`chunk_merge.py:95-107`) **ở lại** `chunk_merge.py` và
   **không** thuộc phạm vi hàm chung, nên hai con số có thể khác nhau một cách hợp lệ khi file
   chunk ngắn hơn dự kiến.
6. `test_lineage`: `persist_findings` được gọi với finding có `page_number` bắt nguồn từ **đúng file
   sidecar** mà runner đã truyền qua env — không phải giá trị hằng trong test.
7. `test_pdf2zh_branch_untouched`: `pdf_translate_engine="pdf2zh"` → 0 finding `babeldoc_*`, và
   `OverflowReport` **vẫn** được ghi như cũ (hồi quy Bug #9).
8. `test_capability_guard`: `AsyncMock(spec=BabeldocRunner)` không set
   `reports_own_paragraph_drops` → `pytest.raises(TypeError)`.
9. `test_sentinel_mismatch_one_way` (**mới, F5**): `stdout_sentinel_count < len(dropped)` → **0**
   finding `babeldoc_drop_report_mismatch` (EvictQueue làm sentinel ≤ structured là bình thường);
   `>` → đúng 1 finding.
10. `test_severity_from_registry` (**mới, F6**): monkeypatch `_SEVERITY_BY_CHECK` → severity của
    finding đổi theo; chứng minh orchestrator **không** hardcode chuỗi severity.
11. `test_r2_counts_from_db_on_resume` (**mới, X7**): dựng job có 2 chunk, chunk 0 đã
    `status="completed"` với **3** row `layout_qa_findings` `babeldoc_*` sẵn trong DB (mô phỏng lần
    chạy trước đã crash sau chunk 0), chunk 1 chạy trong lần này sinh **1** finding → log R-2 phải
    báo **4**, không phải 1. Đây là test chứng minh R-2 đếm từ DB chứ không từ list in-memory; nếu
    ai đó đổi ngược lại thành accumulator, test này đỏ.
12. `test_checksum_mismatch_triggers_incomplete` (**mới, X5**): golden file có
    `page.dropped_count = 2` nhưng chỉ **1** dòng `drop` cho trang đó, **và** `observed_pages ==
    expected_pages` → vẫn ghi đúng 1 finding `babeldoc_drop_report_incomplete` với
    `detail["checksum_mismatch_pages"] == [<trang đó>]`, `detail["missing"] == []`. Chứng minh
    checksum không rơi vào hư không khi đủ trang.

**Live E2E (R5-03 + R6-03)** — bắt buộc trước `ready_for_release`.

⚠️ **Mục tiêu E2E đã ĐỔI (2026-09-11)**: bản trước nhắm "chunk 0 — 40 trang đầu Le Cordon Bleu".
**Sai mục tiêu** — Domain Expert đã đo toàn bộ 418 trang của job `1ee1fdee` và xác nhận **chunk 0
không có ca drop kiểu (1) nào** (tỉ lệ ký tự out/src trên 40 trang: min 0.80 tại trang 17 với vỏn
vẹn 30 ký tự; ứng viên "mất chữ" với `src > 300` ký tự và tỉ lệ `< 0.75`: **0**). Chạy gate trên
chunk 0 sẽ ra `available=True, dropped=[]` và **không chứng minh được gì**.

**Ca drop thật, đã đo, dùng làm gate**:

| Hạng mục | Giá trị |
|---|---|
| Tài liệu | `data/uploads/f07b3194-4d26-…-Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf` (418 trang) |
| Chunk | **chunk 5**, `--pages 199-240` (42 trang) |
| Trang có drop | **230** (1-based, tài liệu nguồn) |
| Đoạn bị mất | sidebar EN, bbox `(61.5, 223.6, 332.3, 466.6)` ⇒ khung **271 × 243 pt**, 13 dòng, font `BernhardModernStd-Roman` **12 pt**, **614 ký tự**: *"The term feuilletage appeared in the 15th century and some attribute its invention to Feuillet, the pâtissier to the Marshall of Conde. … including Carême who innovated the fifth turn of the dough!"* |
| Bằng chứng | đọc **toàn văn** output trang 230 (1.126 ký tự) — không chứa bất kỳ dấu vết nào của đoạn này (không "feuilletage" theo nghĩa lịch sử, không Feuillet / Conde / Le Lorrain / Médicis / Carême), trong khi **mọi** block khác của trang đều có bản dịch |
| Vì sao chắc đây là kênh (1) chứ không phải co ngót dịch | tỉ lệ ký tự **ngang** 2318 → 1440 = **0.62**, trong khi 6 trang "mất nhiều nhất" còn lại của cả cuốn đều 0.84–0.88 và đã kiểm là số block nguồn/đích khớp, không block nào vắng mặt |

🚨 **BẪY BẮT BUỘC TRÁNH — không được cắt nhỏ dải trang cho rẻ**: phải chạy **đúng `--pages 199-240`**
(42 trang), **KHÔNG** cắt lấy 2-3 trang quanh 230. Lý do có nguồn xác thực (đã tự đọc
`typesetting.py:919-935`): `preprocess_document` gom `optimal_scale` của **mọi** paragraph trên
**toàn bộ tập trang của chính lần gọi đó**, lấy `statistics.multimode(...)` rồi **hạ** mọi giá trị
lớn hơn mode xuống mode. Tập trang khác ⇒ mode khác ⇒ đoạn ở trang 230 có thể **fit** và ca drop
**biến mất**. Đây cũng chính là lý do kỹ thuật của bộ lọc chồng lấn ở 6.22.5.1.

**Harness bắt buộc (X8, 2026-09-11) — KHÔNG chạy qua `run_job()`, KHÔNG chạy CLI thủ công**: gate
này là một **integration test gọi THẲNG `JobOrchestrator._process_chunk()`** với `BabeldocRunner`
**thật** (không mock), DB session thật, và một `Chunk` thật
(`chunk_index=5, page_start=199, page_end=240, overlap_start=199, overlap_end=200`).

Lý do phải ghi rõ, thay vì để QA tự chọn: ba yêu cầu của gate chỉ **đồng thời thoả** ở đúng tầng
này — assertion 1-3 cần `BabeldocRunner` thật chạy babeldoc thật; assertion 5 cần bộ lọc dải trang
sống sót nằm **trong** `_process_chunk()`; assertion 6 cần log R-1 cũng nằm trong `_process_chunk()`;
và lời hứa *"chi phí 42 trang thay vì 418"* chỉ đúng khi **không** đi qua `run_job()` (chạy
`run_job()` sẽ dịch cả 418 trang — tốn tiền thật, và biên chunk lại phụ thuộc trạng thái thích ứng,
xem assertion 0).

⚠️ **Harness này KHÔNG phủ 2 thứ — nói ra để QA không tưởng là đã phủ**: (a) log **R-2** (nó nằm ở
`run_job()` Bước 10, không chạy trong harness này) và (b) `merge_chunk_pdfs()`. Hai thứ đó vẫn phải
được phủ bằng test ở mục "Unit / integration" trên (R-2: test riêng với DB có sẵn finding của 2 lần
chạy giả lập resume — đúng ca X7; merge: test 5).

**Assertion cho gate (R6-02 — assert giá trị, không đếm suông)**:
0. **TIỀN ĐIỀU KIỆN — kiểm TRƯỚC khi tin bất cứ assertion nào phía dưới**: `job.chunk_size_used == 40`
   **và** chunk đang đo có `page_start == 199 and page_end == 240`. Lý do có nguồn xác thực:
   `chunk_size_used` là **thích ứng**, `COLD_START_CHUNK_SIZE = 20` hoặc `WARM_CHUNK_SIZE = 40`
   (`job_orchestrator.py:112-113`), chọn tại `:550-561` theo
   `state.observation_count >= 3 and state.consecutive_successes >= 3`. Đo thật bảng
   `concurrency_state` ngày 2026-09-11: `('babeldoc','deepseek','deepseek:deepseek-v4-flash',
   consecutive_successes=95, observation_count=133)` ⇒ **đang warm**, sẽ ra 40. **Nhưng
   `consecutive_successes` về 0 sau MỘT lần fail** ⇒ chunk_size 20 ⇒ chunk 5 thành `99-120`, trang
   230 rơi sang chunk khác, **và** tập trang đổi ⇒ dính đúng cái bẫy mode-scale cảnh báo ngay trên.
   Một dòng assert này cứu trọn một vòng chạy thật.
1. `drop_report.available is True` **và** `observed_pages == set(range(199, 241))` (42/42 trang).
2. Tồn tại record với `page_number_1based == 230`.
3. `text_excerpt` của record đó là bản dịch VI của đoạn feuilletage (soi tay **một** lần, rồi chốt
   vào golden file `tests/fixtures/babeldoc/drop_report_v2.jsonl`).
4. **Mở `translated_vi.pdf` trang 230 và xác nhận đoạn đó thật sự vắng** — không chỉ tin số đếm
   (R6-03).
5. **KHÔNG** có finding nào ở trang **199-200** (2 trang chồng lấn bị `merge_chunk_pdfs` vứt bỏ) —
   đây là assertion chứng minh bộ lọc F1 hoạt động trên dữ liệu thật.
6. Dòng log R-1 (6.22.6.2) xuất hiện, đúng định dạng có `observed=42/42`, `checksum_mismatch=…` và
   câu PHAM VI.

Lần chạy này **là** nguồn sinh golden file cho test 1/3/4. Chi phí: 42 trang thay vì 418.

**Nếu không tái hiện được** (bản dịch lần này ngắn hơn, vừa khung): **không** kết luận thiết kế sai.
Theo thứ tự ưu tiên: (a) chạy lại nguyên cuốn với **cùng model/prompt** như job `1ee1fdee`
(`deepseek`) — cuốn này nhiều sidebar khung hẹp nên xác suất ra ít nhất 1 ca drop là cao;
(b) dựng tài liệu ép drop **sao chép đúng hình học đã đo**: 1 trang, **một** text box ~270 × 240 pt,
~650 ký tự EN ở 12 pt. (b) **không phải "bịa ca test"** — nó là bản sao hình học của một ca thật đã
đo trên trang 230.

⚠️ **Vẫn chưa verify tại thời điểm viết**: bản thân **cơ chế đo** (shim + sidecar) chưa chạy
end-to-end lần nào — mọi kết luận ở 6.22.1–6.22.4 là từ đọc source + đo log thật. Khác với bản
trước, **sự tồn tại của một ca drop thật thì KHÔNG còn là giả thuyết** (trang 230 đã đo trên output
có sẵn). Điều chưa verify còn lại, hẹp hơn nhiều: chạy **lại** babeldoc trên `--pages 199-240` có
drop **đúng đoạn đó** không — dịch máy không tất định.

---


### [Architecture.md cũ] 6.23.7. Gate kiểm thử

#### 6.23.7. Gate kiểm thử

**R5-02 — spike BẮT BUỘC trước khi viết regex chính thức.** Đây là increment ĐẦU TIÊN app dựa vào
contract *"babeldoc in token ra stdout"*; trước đây app chỉ dựa vào contract *"babeldoc in cảnh
báo rate-limit ra stdout"*. Dev **phải** làm trước khi implement:
1. Chạy babeldoc thật qua đúng đường app gọi (1 file PDF ngắn, `--pages` 1 trang, API key thật,
   **có** `--no-auto-extract-glossary`), redirect stdout ra file (non-tty), rồi
   `grep -n "Total tokens" <file>`.
2. So đúng 4 dòng thu được với 6.23.1 T4/T7. **Lệch bất kỳ điểm nào** (mất tiền tố
   `INFO:babeldoc.main:`, đổi nhãn, có dấu phân cách nghìn, in nhiều lần) ⇒ **escalate Tech Lead**,
   không tự sửa regex theo phỏng đoán (R5-02).
3. Lưu stdout thu được thành **golden file** `tests/fixtures/babeldoc/token_usage_stdout.txt`
   (đã khử API key nếu có). Mọi test dưới đây đọc từ golden file này — **cấm viết tay** chuỗi
   stdout theo mô tả trong Architecture.md (Protocol 5 mục 3: mock viết tay = test tự xác nhận
   giả định).

**Unit / integration (R6-02 — assert GIÁ TRỊ, không assert "đã gọi"):**
1. `test_parse_token_usage_golden`: từ golden file → `total_tokens`/`prompt_tokens`/
   `completion_tokens`/`cache_hit_prompt_tokens` **bằng đúng** các số trong file.
2. `test_parse_token_usage_no_cache_hit_confusion`: stdout chứa `Prompt tokens: 111` **và**
   `Cache hit prompt tokens: 999` → `prompt_tokens == 111` (chống bẫy 6.23.2 mục 1).
3. `test_parse_token_usage_missing_lines`: stdout không có dòng nào (hoặc chỉ có `Total tokens:`)
   → trả `None`, **không raise**.
4. `test_metered_chunk_lineage` (**test trung tâm, R6-02**): mock `BabeldocRunner` trả
   `BabeldocResult(..., real_token_usage=BabeldocTokenUsage(total=30925, prompt=20000,
   completion=10925, cache_hit_prompt=0))` → sau `_process_chunk()`:
   `chunk.api_tokens_used == 30925` **VÀ** `chunk.cost_source == "metered"` **VÀ**
   `chunk.api_cost == pytest.approx(provider.estimate_cost(20000, 10925))` (tính lại bằng chính
   provider, **không** hard-code số tiền — bảng giá sẽ đổi ở task khác, 6.23.8).
5. `test_estimated_fallback_when_no_token_line`: cùng mock nhưng `real_token_usage=None` →
   `chunk.cost_source == "estimated"` và `chunk.api_tokens_used` **bằng đúng** kết quả
   `estimate_chunk_cost()` như trước ⇒ chứng minh **không silent-break** test hiện có.
6. `test_pdf2zh_never_metered`: runner có `reports_token_usage = False` →
   `chunk.cost_source == "estimated"`, và `parse_babeldoc_token_usage` **không** được gọi.
7. `test_reports_token_usage_guard`: `AsyncMock(spec=BabeldocRunner)` không set thuộc tính →
   property raise `TypeError` (cùng khuôn test đã có cho `needs_font_shrink`).
8. `test_rollup_cost_source`: 3 chunk metered → job `'metered'`; 2 metered + 1 estimated →
   job **`'estimated'`**; 0 chunk có `api_cost` → `'estimated'`.

**Live E2E (R5-03 + R6-03 — bắt buộc trước release):** chạy **1 job PDF thật** (≥2 chunk) với
`pdf_translate_engine=babeldoc`, rồi mở DB kiểm **nội dung**, không chỉ `status`:
- mọi `chunks.cost_source == 'metered'`, `api_tokens_used > 0` (trừ trường hợp cache-hit toàn
  phần của babeldoc → `0`, hợp lệ, xem 6.23.8);
- `jobs.cost_source == 'metered'` và `actual_cost == sum(chunks.api_cost)`;
- đối chiếu `sum(chunks.api_tokens_used)` với **tổng 4 dòng token in trong log của từng chunk**
  (đọc log app) — 2 con số phải **khớp tuyệt đối**, đây là phép kiểm lineage cuối cùng;
- chạy lại **1 job PDF bằng pdf2zh** xác nhận vẫn `'estimated'` (chống hồi quy).


### [Architecture.md cũ] 6.23.9. Vị trí sửa (spec cho Dev — CHƯA implement)

#### 6.23.9. Vị trí sửa (spec cho Dev — CHƯA implement)

| File | Việc |
|---|---|
| `src/services/babeldoc_runner.py` | `BabeldocTokenUsage` (dataclass frozen), `_TOKEN_LINE_RES`, `parse_babeldoc_token_usage()`; gọi parse ngay sau `drop_sentinel_count` (`:577`); thêm `real_token_usage` vào `BabeldocResult`; `reports_token_usage: ClassVar[bool] = True` |
| `src/services/pdf2zh_runner.py` | `reports_token_usage: ClassVar[bool] = False` (chỉ 1 dòng + docstring) |
| `src/core/job_orchestrator.py` | property `_reports_token_usage` (đặt ngay sau `_reports_own_paragraph_drops`, **có** guard `isinstance`); thay khối `:2202-2214` bằng 2 nhánh ở 6.23.4; `rollup_cost_source()` + áp tại `:848` và `:1022`; sửa câu `error_message` nhánh cost-cap theo 6.23.5; `_process_epub_chunk()` ghi thêm `chunk.cost_source = "metered"` |
| `src/models/chunk.py` | `cost_source: str = Field(default="estimated")` kèm docstring trỏ 6.23 |
| `src/models/database.py` | thêm `("chunks", "cost_source", "TEXT NOT NULL DEFAULT 'estimated'")` vào `_NEW_NULLABLE_COLUMNS` (`:61-77`) — SQLite cho phép `ADD COLUMN NOT NULL` khi có DEFAULT hằng; sửa comment của list cho khớp ("cột mới: nullable **hoặc** có DEFAULT hằng") |
| `tests/fixtures/babeldoc/token_usage_stdout.txt` | golden file sinh từ spike R5-02, **không viết tay** |

**KHÔNG sửa**: `src/services/deepseek_provider.py` (bảng giá — task riêng),
`estimate_chunk_cost()`/`estimate_job_cost_v2()`, pre-flight gate Lớp 2, `RATE_LIMIT_LINE_RE`,
`font_shrink_page()`, và mọi đường ghi của nhánh EPUB ngoài 1 dòng `chunk.cost_source` nêu trên.

---


### [Architecture.md cũ] 6.27.1. Trạng thái trước fix (sự thật đo được 2026-09-16)

#### 6.27.1. Trạng thái trước fix (sự thật đo được 2026-09-16)

`src/core/term_extraction_service.py:74-83` raise `TermExtractionSourceError` cho **mọi** job
`file_type == epub`, với lý do "US-22 chưa implement nên nhánh này không thể bị gọi". US-22 đã lên
production 2026-09-10 (commit `27d7daa`, v1.3.0) → tiền đề của guard **hết hiệu lực** nhưng guard
không ai gỡ. Lỗi bị nuốt tại `src/api/routes/jobs.py:545-548` (`except Exception: logger.exception`
— **đúng theo BR-TERM-01/§6.18.6**, không phải lỗi ở đây), nên job vẫn `completed` và panel "Các từ
mới" rỗng, không có bất kỳ tín hiệu nào tới user.

Đo trên `data/bb_translation.db` (2026-09-16): **8 job EPUB `completed`, 0 dòng `suggested_terms`**
(so với `pdf_digital`: 9 job có dữ liệu, 18.359 dòng). Trong 8 job đó, **2 là sách thật của user**
(`Sourdough Discard Recipes Cookbook`, `Sourdough Every Day`), 6 là fixture QA.


### [Architecture.md cũ] 6.12.2 — spike phát hiện stdout/stderr (log capture)

Gia dinh ban dau khi mo thiet ke nay la "grep **stderr** tim dong `RateLimitError, retrying`".
Gia dinh do **SAI**. Da verify bang cach chay that (Protocol 5 R5-02, spike truoc khi thiet ke):

```
$ ~/.local/share/uv/tools/pdf2zh/bin/python -c "
import logging
from rich.logging import RichHandler
logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])
logging.getLogger('pdf2zh.translator').warning(
    'RateLimitError, retrying in 3.5 seconds... (Attempt 7/100)')
" > out.txt 2> err.txt
$ wc -c out.txt err.txt
     243 out.txt
       0 err.txt
```

**Hai loi chi mang, ca hai deu du de lam AIMD im lang sai:**

1. **Sai stream.** 243 byte ra stdout, **0 byte ra stderr**. `Pdf2zhRunner` hien tai vut bo
   stdout (`_stdout_bytes, stderr_bytes = await ...communicate()` —
   `pdf2zh_runner.py:90-92`) va chi giu `stderr`. Neu Dev implement dung theo gia dinh cu,
   bo dem tin hieu se **luon bang 0**, AIMD se luon tang thread cho toi tran roi timeout —
   te hon ca hien trang. Nguon: S8 + S9.

2. **Sai ca khi da doc dung stream.** Khi stdout khong phai TTY, rich wrap o 80 cot va cat
   doi chinh chuoi can grep:

```
[09/05/26 06:06:25] WARNING  WARNING:pdf2zh.translator:RateLimitError <string>:6
                             , retrying in 3.5 seconds... (Attempt
                             7/100)
```

   `grep "RateLimitError, retrying"` -> **0 match**, du dong log co that. Ca so attempt
   (`7/100`) cung bi tach sang dong khac.


### [Architecture.md cũ] 6.12.3.1 — bối cảnh + lý do chọn default

**Boi canh:** spec tren khong noi ro 2 field moi co default hay khong. Dev escalate theo
R5-02: neu de no-default, 16 test integration co san (`tests/integration/test_job_orchestrator.py`
2 cho, `test_job_cancel.py` 1 cho, `test_cost_capped_orchestrator.py` dung lai fixture cua
file dau) fail ngay, du chung khong lien quan gi den rate-limit.


### [Architecture.md cũ] 6.12.3.1 — 4 lý do chi tiết

**Ly do:**

1. **Trong production khong ton tai code path nao roi vao default.** `translate_pages()` tinh
   `rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))` **mot lan, truoc
   moi nhanh re** (`pdf2zh_runner.py`), roi truyen tuong minh vao ca 3 loi ra: return
   `Pdf2zhResult(...)`, `raise Pdf2zhTimeoutError(...)`, `raise Pdf2zhError(...)`. Day la
   **producer duy nhat** cua 3 kieu nay trong `src/`. Default vi vay chi cham toi test stub.
2. **No-default KHONG mua duoc su an toan ma Dev lo.** Rui ro that su la "`rate_limit_hits=0`
   gia khien AIMD phan loai nham `success` va **tang** thread (+2) dung luc dang bi throttle"
   (6.12.4). Nhung bat buoc truyen tuong minh khong chan duoc dieu do — mot call site sai van
   go duoc so `0` vao. No chi doi loi im lang thanh loi go tay, khong doi thanh loi bi chan.
3. **Lop phong thu that nam o cho khac va da duoc quy dinh:** test #2/#3 tai 6.12.9 (R6-02)
   assert `rate_limit_hits` **bat nguon tu `stdout` cua ket qua buoc truoc** (golden file), va
   R6-04 buoc Reviewer trace tay. Do la co che duy nhat bat duoc gia tri 0 gia; kieu du lieu
   thi khong.
4. **Chi phi cua no-default la thuc va lech huong:** sua 16 test khong lien quan chi de go
   `stdout=""`, `rate_limit_hits=0` vao — dung cai gia tri ma default da cho — la thay doi
   thuan tuy nghi thuc, lam nhieu diff cua increment AIMD va tang be mat merge conflict, doi
   lai zero bao ve them (xem 2).


### [Architecture.md cũ] 6.15 — 5 điểm bỏ sót phát hiện sau phản biện Domain Expert (S15-10..S15-14)

##### Bổ sung sau phản biện Domain Expert (2026-09-08) — 5 điểm §6.15 bản gốc BỎ SÓT

**S15-10 [BLOCKING] — `_find_completed_duplicate()` phải lọc `job_type`.**
`src/api/routes/jobs.py:322-326` chỉ lọc `Job.file_hash == file_hash, Job.status == "completed"`
(tự đọc lại code, xác nhận Expert đúng). Hiện **vô hại vì chưa có job `parse_only` nào
`completed`** — nhưng **ngay khi US-15 ship**: user parse file X xong (job parse_only →
`completed`), sau đó bấm "Dịch" chính file X → API trả `200 duplicate_found` trỏ tới **job
parse-only**, frontend hiện "đã dịch rồi, tải?" và link tải là ZIP Markdown. Đây đúng cái bẫy
"cùng một biến, hai ý nghĩa" mà §6.20.7 tự cảnh báo.
**Sửa**: thêm `Job.job_type == "translate"` vào `where`. **Không** dedupe cho parse_only ở v1 —
chi phí = $0, chạy lại vô hại, thêm nhánh là thêm bề mặt lỗi.
**Test regression bắt buộc**: `create_job(job_type="translate")` trên file đã có 1 job
`parse_only` `completed` → phải ra **202 + job mới**, không phải `200 duplicate_found`.

**S15-11 [BLOCKING] — `retry_job()` đang chặn `parse_only`, mâu thuẫn trực tiếp với S15-9.**
`jobs.py:585-586` raise 400 `"parse_only chua duoc ho tro, khong the retry"`, và `:594-605` gọi
`_resolve_provider_or_400` + `_enforce_cost_gate` **vô điều kiện**. Kịch bản thật trên máy user
(§6.9.8 — `mineru-api` chạy tay bằng `uv tool`, không phải service tự bật): tạo job → S15-9 fail
sớm đúng như thiết kế → user bật MinerU → bấm "Tiếp tục" → **400, job chết vĩnh viễn, phải upload
lại**. Fail sớm mà không retry được thì fail sớm là một cái bẫy.
**Sửa**: bỏ `:585-586`; với `parse_only` **bỏ qua** `_resolve_provider_or_400` +
`_enforce_cost_gate` (giống hệt `create_job:475-485` đã làm) → đặt thẳng `status="queued"` +
`_schedule_background`. Nhãn nút retry trên `web/index.html:139-140` hiện là "Tiếp tục dịch" →
rẽ theo `job_type` thành "Chạy lại" cho job parse.

**S15-12 [BLOCKING] — Thiếu status riêng `"parsing"`, rủi ro `rmtree` trong lúc MinerU đang ghi.**
§6.15 bản gốc không nói job ở status nào trong lúc MinerU chạy (có thể tới ~25 phút, xem S15-14).
Nếu Dev tự chọn: (a) mượn `"translating"` → UI hiện "Đang dịch" cho job không dịch, và
`current_chunk/total_chunks` hiện `-/-`; (b) đặt `"parsing"` mà **không** sửa các chỗ hardcode
danh sách status → user xoá được job đang chạy và `DELETE` sẽ `rmtree(data/processing/{job_id})`
**trong lúc `_write_images()` đang ghi**.
**Chốt: thêm status `"parsing"`**, kèm **checklist bắt buộc 6 chỗ** (Reviewer grep `"translating"`
để kiểm, R6-04):

| # | Vị trí | Hậu quả nếu quên |
|---|---|---|
| 1 | `jobs.py:648-655` `_ACTIVE_JOB_STATUSES` | guard `DELETE /api/jobs/{id}` (`:672-679`) hở → `rmtree` khi đang ghi (`:708-709`) |
| 2 | `jobs.py:631` `cancel_job` | (đang chặn `completed/failed/cancelled` → **đã đúng**, chỉ cần xác nhận không đụng) |
| 3 | `web/js/app.js:16-25` `RESTORABLE_STATUSES` | job biến mất khỏi UI sau F5 |
| 4 | `web/js/app.js:32-38` `CANCELLABLE_STATUSES` | mất nút "Dừng" |
| 5 | `web/index.html:110` | thanh progress không hiện |
| 6 | `web/history.html:23-30` + `web/js/history.js:15-27` | filter + badge màu thiếu trạng thái |

**S15-13 — Cancel hiện VÔ HIỆU với `parse_only`; và `_run_rotated_text_probe` KHÔNG chạy.**
- `cancel_requested` chỉ được đọc sau mỗi chunk (Step 7); `parse_only` là **1 lời gọi MinerU duy
  nhất** tới 3600s → nút "Dừng" không có tác dụng. **Sửa**: `_poll_until_done()`
  (`mineru_runner.py:181-226`) nhận thêm callback `should_cancel: Callable[[], Awaitable[bool]]`,
  gọi mỗi vòng poll; `True` → ngừng chờ, job `cancelled`. **Known limitation**: MinerU vẫn chạy
  nốt task server-side — `⚠️ ASSUMED, chưa verify` MinerU 3.4.5 có endpoint huỷ task hay không
  (§6.9.2 không liệt kê). Chấp nhận được: compute local, chi phí $0.
- `_run_rotated_text_probe` (Bug #6 Phase 1, `job_orchestrator.py:680`) **không chạy** cho
  parse_only: theo `mineru_det_probe.py:11-17` chữ xoay vẫn được nhận dạng (chỉ mất góc), và
  Markdown không có khái niệm góc. Ghi tường minh vì `run_parse_only()` cho `pdf_scan` sẽ **chép
  lại một phần** `_build_ocr_bridge()` — R6-01 đòi nói rõ bước nào được tái dùng, bước nào không.
  **Sửa cấu trúc**: tách `job_orchestrator.py:658-665` (gọi MinerU + ghi quality + cảnh báo) thành
  helper `_run_mineru_and_record_quality()` dùng chung cho cả 2 nhánh — **một** định nghĩa duy
  nhất cho "gọi OCR" (đúng tinh thần Protocol 6, và cũng là chỗ áp rule rẽ theo `file_type` của
  S15-6 để 2 nhánh không thể lệch nhau).

**S15-14 — 3 trường "finalize" chưa spec + timeout tính theo số trang.**
- `completed_at` **phải** được set (như `job_orchestrator.py:607` của nhánh translate) — nếu
  quên, tên file tải về rơi vào fallback `updated_at` (`download.py:52-53`), lệch hành vi so với PDF.
- `actual_cost = 0.0`, `cost_source = "metered"`. Lý do chọn `metered` chứ không phải `estimated`:
  **0 là số đo thật** (không có lời gọi LLM nào), và frontend rẽ theo `cost_source` để hiện cảnh
  báo "ước tính, có thể sai lệch" (§6.11.4 Lop 0 mục 2) — hiện cảnh báo ước tính cho một con số
  chắc chắn bằng 0 là nhiễu vô nghĩa.
- `job.model`: `create_job:500` ghi `model=provider_name` (DeepSeek mặc định) cho **cả** parse_only
  → tab Lịch sử hiện "deepseek" cho job không dùng LLM. **Giữ nguyên backend** (đụng vào sẽ vướng
  `_resolve_provider_or_400` ở đường retry), chỉ **ẩn cột model trên UI** khi
  `job_type == "parse_only"`.
- **Timeout**: `mineru_task_timeout_seconds = 3600` là hằng số cho mọi file. Đo thật: 89 s / 25
  trang ≈ **3,6 s/trang** → sách 415 trang ≈ 25 phút, Le Cordon Bleu 418 trang/277 MB **sát trần
  3600s**. Chốt: timeout cho `parse_only` = `max(600, pages × 6)` giây (hệ số 6 = 3,6 đo được ×
  1,65 biên an toàn), và BR-PARSE-05 ("thời gian ước tính" trên UI) dùng hệ số 3,6 s/trang.
- **Batch**: MinerU thật báo `max_concurrent_requests: 1` (`curl localhost:8010/health` →
  `{"status":"healthy","version":"3.4.5","max_concurrent_requests":1,…}`). Batch 3 file
  (`max_concurrent_files=3`) submit 3 task, MinerU **xếp hàng server-side**, mà `_poll_until_done`
  đếm `elapsed` **từ lúc submit — tính cả thời gian nằm trong hàng đợi** → file thứ 3 có thể hết
  timeout khi còn chưa được xử lý. Chốt v1: **known limitation "batch parse_only nên ≤ 2 cuốn
  dày"** + timeout theo số trang ở trên. Không đổi cách đếm timeout ở v1 vì tên status "đang xử
  lý" của MinerU là `⚠️ ASSUMED, chưa verify` (§6.9.2 chỉ liệt kê `completed`/`failed`) — sửa theo
  giả định về payload của tool bên thứ ba là đúng thứ Protocol 5 cấm.


### [Architecture.md cũ] 6.18.8 — bối cảnh Final Decision US-20

#### 6.18.8. Final Decision sau phản biện Domain Expert + quyết định mới của user (2026-09-08)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement.
**Quan hệ tài liệu**: mục này **thay thế (supersede)** — §6.18.1 điểm 2, §6.18.2 **bước 1, 3, 4,
5, 6** và bảng config, §6.18.5 bước 3, §6.18.7 mục 3. Mọi phần khác của §6.18 **giữ nguyên hiệu
lực**. Khi mâu thuẫn, **mục này thắng**.

**Hai nguồn thay đổi, phải phân biệt rõ**:
- **(a) Phản biện Domain Expert** — 4 lỗi đo được trên dữ liệu thật của user (2 cuốn sách đã dịch
  + 1 bản OCR MinerU + 114 glossary entry thật).
- **(b) Quyết định MỚI của user cùng ngày** (trả lời trực tiếp 2 câu hỏi Expert đặt cho PM):
  *"Chỉ khuyến nghị từ mới khi từ đó không có trong glossary. CÓ thể mở pool nếu cần nhưng thoả
  mãn điều kiện trước"* và *"Chỉ gợi ý các từ không có trong glossary"*. Tức: **điều kiện lọc DUY
  NHẤT là "không có trong glossary"** — không trần số lượng tuỳ ý, và **BR-TERM-04 giữ nguyên
  per-job** (không thêm cơ chế nhớ "đã bỏ qua" xuyên nhiều cuốn).

Quyết định (b) làm **đổi trọng tâm kỹ thuật của cả US-20**: trước đây trọng tâm là "chọn con số
trần và công thức xếp hạng cho vừa 40 slot"; bây giờ trọng tâm là **làm cho phép so khớp "đã có
trong glossary" thật sự chính xác** (T3) và **làm cho ứng viên sạch ngay từ tầng token** (T2) —
vì mọi thứ qua được 2 cửa đó đều sẽ hiển thị.


### [Architecture.md cũ] 6.20.13.3b — thiết kế phát hiện runaway bản gốc + số đo bác bỏ ngưỡng (đã bị §6.20.15 K-2/K-4 thay)

**(b) Phát hiện runaway per-request (C-3).** Helper MỚI, **đặt trong `src/core/cost_estimator.py`**
(không phải `job_orchestrator.py`) — vì nó phải dùng lại **đúng 2 hằng số của estimator**, và để 2
công thức không bao giờ trôi khỏi nhau (cùng lý do §6.11.4 mục 3):

```python
# src/core/cost_estimator.py
EPUB_RUNAWAY_OUTPUT_FACTOR = 3.0        # ⚠️ ASSUMED — xem "Cơ sở chọn ngưỡng"
EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS = 1_500  # ⚠️ ASSUMED — chống false-positive ở payload nhỏ

def is_runaway_output(payload_chars: int, output_tokens: int) -> bool:
    """True khi output_tokens vuot xa muc ky vong cho CHINH payload nay
    (Architecture.md 6.20.13.3b). Dung DUNG 2 hang so cua estimator
    (VI_CHAR_EXPANSION, CHARS_PER_TOKEN_VI) — khong duoc viet cong thuc thu 2.
    """
    expected = int(payload_chars * VI_CHAR_EXPANSION / CHARS_PER_TOKEN_VI)
    return output_tokens > max(EPUB_RUNAWAY_OUTPUT_FACTOR * expected,
                               EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS)
```

Gọi tại `_process_epub_chunk()` **ngay sau dòng 1752** (sau khi cộng token/cost, trước
`parse_epub_batch_response`), với `payload_chars = len(payload_json)` — tức là so với **input của
chính request đó**, không phải ước tính cả sách (đúng yêu cầu brief).

**Cơ sở chọn `EPUB_RUNAWAY_OUTPUT_FACTOR = 3.0` — `⚠️ ASSUMED, chỉ có 1 điểm dữ liệu`:**
- Mức kỳ vọng lấy từ chính công thức đã dùng cho cost gate: `output ≈ chars × VI_CHAR_EXPANSION
  (1,16) / CHARS_PER_TOKEN_VI (2,0)` = `chars × 0,58`. Payload đầy 3.000 ký tự → kỳ vọng ~1.740
  output token.
- **Trần vật lý** `max_tokens = 8192` (V-2) → tỉ lệ tối đa mà 1 request đầy có thể đạt là
  `8192 / 1740 = 4,7×`. Chọn **3,0×** để cơ chế **kích hoạt TRƯỚC khi chạm trần** (bắt được runaway
  lúc nó còn đang sinh, không phải sau khi đã bị cắt cụt), mà vẫn còn biên **≥ 3×** so với dao động
  bình thường (công thức estimator vốn ước **cao**, nên tỉ lệ thật của 1 response lành mạnh kỳ vọng
  **< 1,0×**).
- **Ngưỡng này CHƯA được đo trên phân bố thật.** Không ai có `output_tokens` per-request của lần
  chạy bình thường (QA chỉ ghi tổng theo chunk). **Bắt buộc**: lần chạy live đầu tiên sau khi Dev
  implement phải log `(payload_chars, output_tokens, ratio)` cho **mọi** request vào
  `chunk_dir/requests.jsonl`, và QA ghi vào `test-report.md` giá trị **max ratio quan sát được**.
  Nếu max ratio thật của lần chạy lành mạnh > 1,5 → ngưỡng 3,0 quá sát, phải nâng và ghi lại.
  Đây chính là bước "đo thêm trước khi tự tin vào con số" của R5-02.

> ### ⚠️ ĐÃ ĐO — 2026-09-11: điều kiện cảnh báo ở gạch đầu dòng trên ĐÃ XẢY RA. §6.20.13.3b **hết
> hiệu lực nguyên trạng**, đọc **§6.20.15** cho hợp đồng hiện hành.
>
> 797 request thật / 3 cuốn sách / `deepseek-v4-flash`: `ratio` **median 4,4× · p90 11,2× · p99
> 20,3×**; **65,4% số request** vượt ngưỡng 3,0×. Ngưỡng dự báo "response lành mạnh < 1,0×" sai
> khoảng **4–6×**. Nguyên nhân **không phải** model runaway mà là `output_tokens` (=
> `usage.completion_tokens`) của DeepSeek V4 Flash **bao gồm cả token thinking** (thinking bật mặc
> định, effort `high`) trong khi `epub_expected_output_tokens()` chỉ mô hình hoá phần **bản dịch**.
>
> Hệ quả trực tiếp (đây là thứ đang giết job, không phải markup): vì `runaway` gần như **luôn**
> `True`, nhánh **R-b** (`if runaway and missing_ids: raise`) biến thành *"abort ngay khi thiếu BẤT
> KỲ id nào"* — toàn bộ thang cứu hộ C-1/Lớp B/Lớp C ở phía dưới trở thành **code chết** cho provider
> này. Bản vá: §6.20.15 K-2/K-3.


### [Architecture.md cũ] 6.20.15 K-4 — lý do cấm hiệu chỉnh hằng số trước khi có số đo hậu K-2/K-3

`CHARS_PER_TOKEN_VI = 2.0` hiện **sai nặng**: đo thật trên 55 chunk cho **0,23–0,66 ký tự/token**
(median ~0,32) — và đây còn là **cận trên** (mẫu số bỏ qua token của retry). Nhưng **CẤM sửa hằng số
này trong cùng lượt với K-2/K-3**: số đo hiện tại đã bị ô nhiễm bởi token thinking, hiệu chỉnh theo
nó là khoá cứng cái sai vào hằng số. Thứ tự bắt buộc:

1. Làm K-2 (+K-3), chạy live **1 cuốn**, thu `requests.jsonl` có `answer_tokens`.
2. Tính `chars_per_answer_token` thật; cập nhật `CHARS_PER_TOKEN_VI` **và** `VI_CHAR_EXPANSION`,
   ghi số đo + ngày vào §6.20.15 này (không để ⚠️ ASSUMED trần).
3. Chỉ khi đó mới xét lại `EPUB_RUNAWAY_OUTPUT_FACTOR = 3.0`. Tiêu chí giữ nguyên §6.20.13.3b:
   **max ratio của lần chạy lành mạnh phải ≤ 1,5×**; nếu không, ngưỡng vẫn sai.


### [Architecture.md cũ] 6.20.15 K-4 — 4 lý do giữ nguyên 3 hằng số

- Số đo live ở trên chỉ cho ra **1 tỉ số gộp** `chars_per_answer_token`
  (= `CHARS_PER_TOKEN_VI / VI_CHAR_EXPANSION` theo đúng công thức `epub_expected_output_tokens()`),
  KHÔNG tách được thành 2 hằng số độc lập — tách bằng cách "đoán" 1 trong 2 rồi suy hằng số kia là
  đúng loại suy diễn Protocol 5 cấm.
- `VI_CHAR_EXPANSION` là hằng số **DÙNG CHUNG** với `estimate_job_cost_v2()` (ước lượng chi phí
  TỔNG QUÁT cho cả PDF, Architecture.md 6.11.4), đo gốc từ **ký tự văn bản thuần** (`total_chars`
  tiếng Anh nguồn / tiếng Việt dịch, S1 6.11.2). `payload_chars` ở phép đo K-4 này là
  `len(payload_json)` — ĐÃ GỒM markup HTML + overhead cấu trúc JSON (`{"id":...,"html":...}`), KHÔNG
  phải ký tự văn bản thuần. Ghi đè `VI_CHAR_EXPANSION` bằng tỉ số đo trên cơ sở khác sẽ làm sai lệch
  `estimate_job_cost_v2()` (rủi ro ước lượng SAI cho các job PDF không liên quan gì tới K-2/K-3/K-5)
  — đúng loại lỗi tổng quát hoá nhầm ngữ cảnh mà Protocol 8 R8-02 cảnh báo.
- Bản thân công thức HIỆN TẠI đã an toàn: `max_ratio=0,9119 < 1,5×` (tiêu chí bước 3) VÀ
  `<< EPUB_RUNAWAY_OUTPUT_FACTOR=3,0` — không có bằng chứng false-positive nào cần sửa gấp. Vì phép
  đo gộp không tách được 2 hằng số mà không suy đoán, giữ nguyên cả 3 hằng số là lựa chọn AN TOÀN
  HƠN (tránh làm hỏng `VI_CHAR_EXPANSION` dùng chung) so với sửa dựa trên suy diễn.
- Backlog cho lần đo sau (nếu muốn tách chính xác 2 hằng số): cần đo riêng
  `len(translated_plain_text) / len(source_plain_text)` (cho `VI_CHAR_EXPANSION`, từ `units.json` +
  `doc.units[i].text` đã strip tag, KHÔNG dùng `payload_json`) và
  `len(translated_plain_text) / answer_tokens` (cho `CHARS_PER_TOKEN_VI`) riêng biệt — chưa làm ở
  lượt này vì không nằm trong phạm vi brief S4 (chỉ có `requests.jsonl`, không map ngược được sang
  `units.json` theo từng request slice mà không đọc lại toàn bộ `EpubDocument`).


### [Architecture.md cũ] 6.21.4 — gate bắt buộc cho §6.21 (đã chạy xong cùng US-15)

#### 6.21.4. Gate bắt buộc (§6.15.6 mục 5 trỏ tới đây)

5 case dưới đây phải xanh trước khi US-15 hoặc US-22 được `ready_for_release`. Mỗi case là một lỗi
**đã đo được trên dữ liệu thật**, không phải case tưởng tượng.

| # | Case | Kỳ vọng | Chặn cái gì |
|---|---|---|---|
| F-1 | 5 dòng `<sup>1</sup>/<sub>3</sub> cup …` của `chapter01.html` | `1/3 cup …` | rule `extract()` cũ (ra `/ 3 cup`) |
| F-2 | Dòng `1<sup>1</sup>/<sub>3</sub> cups unbleached white flour` | **`1 1/3 cups …`** | `markdownify` mặc định (ra `11/3`) — **case quan trọng nhất, và là case duy nhất phân biệt được thiết kế đúng với đề xuất của Expert** |
| F-3 | `x<sup>2</sup>`, `10<sup>-6</sup>` | `x²`, `10⁻⁶` | mất số mũ (ra `x2`, `10-6` — đọc thành phép trừ) |
| F-4 | `H<sub>2</sub>O`, `Ca(OH)<sub>2</sub>`, `SO<sub>4</sub><sup>2-</sup>` | `H₂O`, `Ca(OH)₂`, `SO₄²⁻` | mất chỉ số dưới |
| F-5 | **US-22**: dịch 1 chunk chứa 6 dòng `<sup>` rồi mở lại file EPUB output | 6 dòng vẫn có **đúng 6 `<sup>` và 6 `<sub>`**, con số không đổi | LLM tự ý "dọn dẹp" markup; và rule `extract()` nếu Dev quên xoá |

F-5 phải chạy **trên file EPUB output thật**, không phải trên chuỗi trả về của LLM — đúng tinh thần
R6-03 ("mở file ra xem chữ thật"). Đây cũng là case duy nhất bắt được nếu `write_translated()` ghi
đúng nhưng LLM sửa markup.

---


### [Architecture.md cũ] 6.24 — nguồn xác thực hành vi nhớ thư mục tải của Chrome/Firefox

Tên setting đã verify (nguồn thật, fetch 2026-09-12):
- **Chrome**: Settings → Downloads → **"Ask where to save each file before downloading"** — nhãn UI trích
  từ https://support.google.com/chrome/answer/95759 (fetch 2026-09-12).
- **Firefox**: Settings → General → Downloads → **"Ask where to save files before downloading"** —
  nhãn hiện hành (`download-always-ask-where2`) trong mozilla-central
  `browser/locales/en-US/browser/preferences/preferences.ftl:617-618`. Nhãn cũ "Always ask you where to
  save files" đã đổi; **không** dùng wording cũ trong hint.

Hành vi "nhớ thư mục lần trước" — **ĐÚNG cho cả 2**, verify bằng source, không suy đoán:
- Chrome/Chromium `chrome/browser/download/download_target_determiner.cc:333-336` — khi cần prompt, thư mục
  khởi tạo lấy từ `download_prefs_->SaveFilePath()` kèm comment *"If the user is going to be prompted and the
  user has been prompted before, then always prefer the last directory that the user selected"*; thư mục user
  vừa chọn được ghi lại tại cùng file `:757` (`SetSaveFilePath(virtual_path_.DirName())`).
- Firefox `toolkit/mozapps/downloads/HelperAppDlg.sys.mjs:356-365` — `picker.displayDirectory` mặc định là
  thư mục tải mặc định, rồi **ghi đè bằng `lastDir`** nếu hợp lệ; thư mục vừa chọn lưu lại ở `:399`
  (`gDownloadLastDir.setFile(...)`). Lưu ý: `browser.download.lastDir.savePerSite` mặc định `true`
  (`toolkit/mozapps/downloads/DownloadLastDir.sys.mjs:86-91`) → Firefox nhớ **theo từng site**; với app này
  (cùng 1 origin) hiệu quả vẫn là "nhớ thư mục lần trước".


### [Architecture.md cũ] 6.25.6 — test bắt buộc khi implement BL-12 (đã implement + QA PASS)

#### 6.25.6. Test bắt buộc khi implement

- Fixture EPUB tối thiểu **có `mimetype` nén DEFLATED** (sinh bằng `zipfile`, không viết tay) —
  assert `write_translated()` **thành công** và output có `infolist()[0].filename == "mimetype"`,
  `compress_type == ZIP_STORED`, `extra == b""`.
- Fixture EPUB có `mimetype` **KHÔNG phải entry đầu** → output vẫn phải đưa `mimetype` lên đầu.
- Fixture thiếu `mimetype` / sai nội dung → `EpubDocument.load()` raise `EpubParseError`
  (L1), và `POST` route tương ứng trả **400**, chứ không phải fail ở merge.
- R6-02: assert output của merge nằm ở `merged_path` được sinh từ `doc` đã `load(job.file_path)`
  — giữ nguyên các assert lineage sẵn có của §6.20.

---


### [Architecture.md cũ] 6.26.8 — test bắt buộc khi implement S7 (đã implement)

#### 6.26.8. Test bắt buộc khi implement

- **R6-02 (lineage, không chỉ "đã gọi")**: `translator_runner.translate_pages.assert_called_with(..., lang_in="fr", ...)`
  cho job có `source_lang="fr"`, và `lang_in="en"` cho `source_lang=None` (job cũ). Assert
  `prompt_path.read_text()` chứa `"tieng Phap"` — tức prompt file thật sự sinh **từ** `job.source_lang`.
- Regression EN: 6 tài liệu EN trong `data/uploads/` (danh sách ở §6.26.3) phải cho `detect == "en"`.
- Byte-identical: prompt `source_lang="en"` khớp chuỗi cũ (§6.26.6).
- Bước #13: job `source_lang="fr"` ⇒ `extract_and_store_terms` **không** được gọi.
- Bước #1: với `pdf_scan` FR, assert `mineru_runner.parse_document` được gọi với `lang="en"` —
  **không** phải `"fr"` (nếu truyền `"fr"` MinerU raise, §6.26.1).
- **R6-03 (live E2E)**: ít nhất 1 lần chạy xuyên suốt 1 PDF FR thật + 1 EPUB FR thật, mở file output
  kiểm tra **có chữ Việt thật**, không chỉ tin `status == "completed"`.


### [Architecture.md cũ] 6.28.9 — test bắt buộc khi implement S8 (đã implement)

#### 6.28.9. Test bắt buộc khi implement

- **Golden theo tài liệu thật** (Protocol 5 tinh thần "không mock viết tay"): test tham số hoá chạy
  `scan_units()` trên các file thật trong `data/uploads/` và assert **đúng bảng §6.28.2** — gồm cả 2
  ca âm bắt buộc: `[Baking Heaven]` (score 8, 884 từ → **không xoá**) và `Better_For_You` (© mọi
  trang → **không xoá**). Nếu file thật không có trên máy CI, test `skip` có lý do, nhưng phải chạy
  xanh ở máy Dev trước khi đóng task.
- **R6-02 lineage PDF** (không chỉ "đã gọi"):
  `translator_runner.translate_pages.assert_called_with(input_path=pruned_path, page_range="1-40", ...)`
  với `pruned_path` là file cắt **sinh ra từ** `translation_source_path`, và assert
  `fitz.open(pruned_path).page_count == total_pages_goc - len(removed)`.
- **Chống lặp lại Bug #9 ở bước cũ**: assert `create_bilingual_pdf` được gọi với
  `en_pdf_path=original_pruned_path`, **không** phải `job.file_path`; và assert file song ngữ có số
  trang = 2 × số trang bản dịch, trang chẵn/lẻ đúng cặp (mở bằng PyMuPDF, so text).
- **Đối xứng 2 engine**: chạy đúng bộ test lineage trên với `pdf_translate_engine="pdf2zh"` **và**
  `"babeldoc"` (parametrize), assert cả 2 nhận CÙNG `input_path` và CÙNG `page_range`.
- **pdf_scan**: assert Step 2b chạy **sau** `_build_ocr_bridge` — quét trên text của cầu nối, và
  `original_pruned.pdf` được cắt từ `job.file_path` với **cùng tập chỉ số**.
- **Resume**: job có sẵn `copyright_removed_json` + Chunk rows ⇒ `scan_units` **không** được gọi lại
  (`assert_not_called`), `total_pages` không đổi.
- **EPUB cấu trúc**: trên EPUB thật `Sourdough Every Day` (ca khó nhất — nav + mini_toc + NCX):
  output không còn entry `OEBPS/cop.xhtml`, OPF không còn `item`/`itemref`, **không entry nào còn
  chuỗi `cop.xhtml`**, `EpubDocument.load(output)` chạy được, `mimetype` vẫn `ZIP_STORED` ở vị trí
  đầu. Và 1 test cho nhánh `structural="skipped"` (fixture có `<img src>` trỏ vào doc bản quyền) ⇒
  file output **giống hệt** nhánh không xoá.
- **Kill-switch**: `copyright_page_removal_enabled=False` ⇒ output byte-identical với hành vi trước
  S8 (không tạo thư mục `pruned/`, không ghi `copyright_removed_json`).
- **R6-03 live E2E**: ít nhất 1 PDF thật + 1 EPUB thật chạy xuyên suốt, **mở file output** xác nhận
  (a) không còn trang bản quyền, (b) trang kế tiếp trang bị xoá vẫn còn đủ chữ tiếng Việt, (c) bản
  song ngữ ghép đúng cặp — không chỉ tin `status == "completed"`.


### [Architecture.md cũ] 9.2 — Cloud Migration Path v2.0+ (định hướng, không phải hợp đồng đang chạy)

### 9.2. Cloud Migration Path (v2.0+)

Khi chuyen len cloud (VPS/AWS/GCP), can thay doi:

| Component | Local (v1.0) | Cloud (v2.0+) |
|-----------|-------------|---------------|
| **Database** | SQLite file | PostgreSQL (nhieu user dong thoi) |
| **Task Queue** | asyncio in-process | Celery + Redis (distributed workers) |
| **File Storage** | Docker volume | S3 / GCS (scalable, CDN) |
| **Auth** | Khong co | JWT + OAuth (multi-user) |
| **Container** | docker-compose | Kubernetes hoac ECS |
| **Monitoring** | Log file | Prometheus + Grafana |
| **OCR** | MinerU container | GPU instance (A10G) cho throughput cao |
| **Concurrency** | Semaphore(3) | Celery worker pool, auto-scale |
| **Cost tracking** | Per-job SQLite | Billing system, per-user quotas |

**Nhung gi KHONG doi**:
- FastAPI API layer (chi them auth middleware)
- Translation pipeline logic
- Prompt templates
- Post-processing (font shrink, merge)
- Frontend (them login page)

**Migration steps**:
1. Thay SQLite → PostgreSQL (SQLModel ho tro ca hai, chi doi connection string)
2. Thay asyncio queue → Celery (tach job_orchestrator thanh Celery tasks)
3. Thay local file storage → S3 (abstract FileStorage interface tu dau)
4. Them auth middleware (FastAPI dependency injection)
5. Deploy tren Kubernetes voi Helm chart

---


### [Architecture.md cũ] 6.20.12 X2 — số đo inner-HTML trên chapter01.html

Số đo tự tái lập trên `ops/xhtml/chapter01.html`: **373 unit, 263 unit (70%) có ít nhất 1 thẻ con**;
phân bố `{strong: 214, a: 32, em: 26, br: 6, sup: 6, sub: 6, small: 1}` (Expert đo 273/383 = 71% —
lệch nhỏ do khác rule đếm node lồng, kết luận giống hệt).

Ca tệ nhất, đo trên đoạn thật:
```
RAW  : <p class="blockquote"><strong>4 cups unbleached white flour</strong><br/><strong>2 teaspoons salt</strong><br/>…
get_text(" ", strip=True) → '4 cups unbleached white flour 2 teaspoons salt 2 tablespoons honey 4 cups potato water'
```
4 nguyên liệu gộp thành 1 dòng, mất bold. **Đây chính xác là Bug #7** (line-break/list bị gộp) —
lỗi vừa tốn 8 vòng QA + 6 lần review để đóng ở nhánh PDF — tái sinh ở EPUB ngay increment đầu tiên,
trên đúng nội dung quan trọng nhất của sách bánh.


### [Architecture.md cũ] 6.20.12 X6 — dump ebooklib 0.20 xác nhận doc_href

Tự chạy `ebooklib==0.20` trên chính file EPUB thật, xác nhận Expert đúng và bổ sung cách sửa đã đo:

```
container.xml → rootfile/@full-path = 'ops/9781603424073.opf' → opf_dir = 'ops'
item.file_name (5 document) có trong zip.namelist() as-is : 0/5
posixpath.normpath(posixpath.join(opf_dir, item.file_name)) : 5/5
book.opf_dir                                               : KHÔNG TỒN TẠI (AttributeError)
```


### [Architecture.md cũ] 6.20.13.3b — lý do hardcode 2 hằng số runaway ngoài .env

**Trả lời câu hỏi 3 của brief (cấu hình được hay hardcode)**: `EPUB_RUNAWAY_OUTPUT_FACTOR` và
`EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS` **hardcode** ở `cost_estimator.py` (tiền lệ BR-IMGCOMP-03), KHÔNG
đưa vào `.env`. Lý do: đây là **ngưỡng chẩn đoán nội bộ chưa có dữ liệu**, không phải chính sách
tài chính của user — chính sách tài chính là `max_cost_per_job_usd` (đã cấu hình được, và Lớp 4 ở
§6.20.13.2 đã làm nó có hiệu lực sớm hơn ~2,7×). Đưa 1 hằng số chưa đo vào `.env` là mời user chỉnh
một con số mà chính team chưa hiểu, rồi khó lần lại được nguyên nhân khi sự cố tái diễn. Khi có đủ
dữ liệu đo (yêu cầu log ở trên) → xem lại quyết định này, ghi vào §6.20.13 vòng sau.


### [Architecture.md cũ] 6.20.13.4 — ranh giới bằng chứng cho giả thuyết prompt gây mất dấu

> **Ranh giới bằng chứng (R5-01)**: sự thật "prompt không có dấu, one-shot demo output không dấu"
> là **ĐÃ VERIFY** (đọc + quét ký tự trên `prompt_builder.py:409-433`). Còn "đó **là** nguyên nhân
> của 30-37% unit mất dấu" là **`⚠️ ASSUMED`** — chưa có A/B test. Nó **giải thích được** đặc điểm
> QA quan sát: batch lớn → tỉ lệ instruction/example (không dấu) so với ngữ cảnh sinh ra càng lớn,
> và mất dấu xuất hiện theo **cụm liên tiếp trong cùng 1 request** (QA đo được), tức là hiện tượng
> ở mức **response**, đúng chỗ one-shot example tác động.


### [Architecture.md cũ] 6.20.13.5 — cơ sở chọn 4 ngưỡng diacritic (corpus nội bộ)

**Cơ sở chọn ngưỡng — `⚠️ ASSUMED, chưa đo trên corpus tiếng Việt thật của ngành bánh`:**
- Đo được trong phiên này: 1.084 đoạn văn tiếng Việt trong `docs/PRD.md` + `docs/Architecture.md`
  (corpus tiếng Việt **duy nhất** có sẵn tại chỗ, **đã lẫn nhiều code/bảng/thuật ngữ Anh** nên
  thiên **thấp**): median `0,219`, mean `0,216`, **p5 = `0,122`**, min `0,053` (min rơi đúng vào 1
  dòng bảng Markdown gần như toàn tiếng Anh).
- Ngưỡng request `0,08` = **thấp hơn p5 của corpus ~1,5×** và thấp hơn median ~2,7× → biên an toàn
  rộng cho các unit hợp lệ giàu thuật ngữ Anh (`sourdough starter`, `450F`, tên riêng).
- Ngưỡng unit `0,02` với sàn 40 chữ cái ≈ "gần như không có dấu nào", cùng tinh thần với tiêu chí
  **QA đã dùng và đã kiểm bằng mắt** (`0 ký tự có dấu`, ≥3 chữ cái) — nhưng nâng sàn từ 3 lên 40
  chữ cái để loại đúng lớp false-positive brief cảnh báo (`"2 tsp"`, tên riêng, `"350F"`, số liệu).
  QA đo 116-143 unit dương tính bằng tiêu chí lỏng hơn và **xác nhận bằng mắt là dương tính thật**
  → tiêu chí này gần như không có false-positive, chỉ có thể sót (false-negative), và sót là chiều
  an toàn: sót chỉ mất chất lượng 1 unit, false-positive tốn tiền thật.
- **Corpus dùng để chốt là docs của chính dự án, KHÔNG phải văn bản dịch xuất bản.** Trước khi
  release, QA phải đo lại `diacritic_ratio` trên **các unit ĐÃ dịch tốt** của lần chạy live (dữ
  liệu này QA đã có sẵn: `chunk_N/units.json` của lần full-book thành công) và ghi phân vị p1/p5
  thật vào `test-report.md`. Nếu p1 thật < 0,10 → phải hạ ngưỡng request xuống dưới p1.


### [Architecture.md cũ] 6.20.13.5 — so sánh E-09 vs mất dấu + ước tính overhead guard

**Trả lời câu hỏi 2 của brief (retry 1 lần vẫn thiếu dấu thì sao) — CHỐT: (a) chấp nhận + ghi
nhận, KHÔNG fail chunk.** Lý do, so trực tiếp với E-09/`EpubBatchTranslationError`:

| | E-09 (thiếu bản dịch) | Mất dấu |
|---|---|---|
| Nội dung | **Không tồn tại** — ghi vào file là **phá huỷ** nội dung gốc | Tồn tại, đúng nghĩa (QA xác nhận), chỉ kém chất lượng |
| Người dùng có cứu được không | Không — chữ đã mất | Có — đọc vẫn hiểu, có thể dịch lại chương đó sau |
| Fail cứng thì mất gì | Không mất gì thêm | Vứt cả chunk **đã trả tiền**, và với bug tái phát nhiều lần thì **sách không bao giờ dịch xong** |

Fail cứng vì mất dấu biến 1 lỗi chất lượng cục bộ thành 1 lỗi chặn toàn job, đúng lúc user đã trả
tiền — sai hướng đánh đổi. Ghi nhận thay vì chặn (§6.20.13.7), và để BR-EPUB-05 tiếp tục giữ vai
trò lớp fail-cứng cho lớp lỗi phá huỷ nội dung.

**Trả lời câu hỏi 3 của brief (overhead)**: phần **đo** là `O(số ký tự)` thuần Python, không gọi
LLM — chạy cho **mọi** unit vẫn không đáng kể (~57.000 ký tự/sách, < 50 ms tổng). Chi phí chỉ phát
sinh khi **phải retry**. Ước tính worst case theo đúng số QA đo (30% unit hỏng, mất dấu theo cụm
trong ~30% request): tầng 1 bắt hầu hết → **~+30% số request** (≈ +6 request/sách ≈ **+$0,003**
với DeepSeek). Nếu §6.20.13.4 sửa đúng gốc thì tầng 1 gần như không bao giờ kích hoạt → overhead
≈ 0. **Không cần cơ chế "chỉ check khi nghi ngờ"** — không có phép đo nào rẻ hơn phép đo này.


### [Architecture.md cũ] 6.20.13.6 — phần C-2 chưa giải thích được + task đo chars/token DeepSeek (đã đóng bởi §6.20.15 K-4)

**Phần CÒN LẠI của C-2 — chưa giải thích được, cấm đoán bừa.** Sau khi cộng ~6.300 input token bị
sót, số học vẫn không khớp: để đạt `actual = $0,0626` thì output thật phải ~83.000 token, so với
42.122 đã ước → **output thật ~2× ước tính**. Giả thuyết mạnh nhất, **`⚠️ ASSUMED, CHƯA VERIFY`**:
`CHARS_PER_TOKEN_VI = 2,0` được đo trên **`cl100k_base` (OpenAI)** cho sự cố pdf2zh
(`cost_estimator.py:36-42` ghi rõ nguồn), rồi được áp cho **DeepSeek** — tokenizer **khác**, chưa
ai đo. Nếu DeepSeek tokenize tiếng Việt có dấu ở ~1,0-1,2 ký tự/token thì output token gấp đôi,
khớp đúng độ lệch quan sát được.

**KHÔNG đổi `CHARS_PER_TOKEN_VI` trong đợt này.** Thay vào đó, 1 task đo **rẻ và tất định** cho Dev,
dùng **dữ liệu QA đã giữ lại** (không tốn thêm 1 đồng API nào):
> Với lần chạy full-book thành công: `chars = tổng độ dài mọi value trong mọi `chunk_N/units.json``;
> `tokens = sum(chunk.api_tokens_used)` trừ phần input ước được. Tính `chars/token` **thật của
> DeepSeek trên tiếng Việt**, ghi vào Architecture.md kèm nguồn. Nếu < 2,0 → thêm hằng số
> **theo provider** (không sửa hằng số dùng chung của nhánh PDF — nhánh đó đã được verify bằng
> golden file `cost_golden_howbakingworks.json`, đổi nó là phá bằng chứng cũ).


### [Architecture.md cũ] 6.28.6.1 — bản đồ tham chiếu đo thật trên 2 EPUB mẫu

##### 6.28.6.1. Bản đồ tham chiếu đo thật (nền tảng của mọi quyết định bên dưới)

| Sách thật | Doc bản quyền | OPF `item`/`itemref` | NCX `content` | NCX `pageTarget` | nav doc `<a>` | Content doc khác trỏ tới |
|---|---|---|---|---|---|---|
| `Baking with Sourdough` | `ops/xhtml/copyright.html` | ✔ | ✔ | — | — | — |
| `Sourdough Culture` | `OEBPS/xhtml/04_Copyright01.xhtml` | ✔ | ✔ | ✔ (`#page_iv`) | ✔ (2, có `#page_iv`) | — |
| `Sourdough Discard` (EPUB) | `index_split_001.html` | ✔ | — | — | — | — |
| `Sourdough Every Day` | `OEBPS/cop.xhtml` | ✔ | ✔ | — | ✔ (2, có `epub:type`) | **✔ `OEBPS/mini_toc.xhtml`** |
| `Sourdough by Science` | `OEBPS/xhtml/Copyright.xhtml` | ✔ | ✔ | ✔ | ✔ (2) | — |
| `Bread-A-Global-History` | `04_copy.xhtml` | ✔ | ✔ | — | — | — |

Hai điều bắt buộc rút ra: (a) href trong tham chiếu là **tương đối theo thư mục của file chứa nó**
(nav ở gốc ghi `OEBPS/cop.xhtml`, nav trong `OEBPS/xhtml/` ghi `Copyright.xhtml`) ⇒ phải
`posixpath.normpath(posixpath.join(posixpath.dirname(referrer), href))` rồi mới so; (b) href có thể
kèm **fragment** (`#page_iv`) ⇒ phải cắt `#...` trước khi so. Bỏ qua 1 trong 2 điều này = để lại
link chết = lỗi cấu trúc kiểu BL-12.


### [Architecture.md cũ] 6.9.5 — số đo bác bỏ câu "confidence is None ở txt mode"

> **SUA SAU PHAN BIEN DOMAIN EXPERT (2026-09-08)** — cau cu o dong nay viet `confidence is None`
> nghia la "khong co span nao qua OCR (file thuc ra co text layer)". **Cau do SAI voi du lieu
> that.** Domain Expert tu chay `MinerURunner.parse_document(parse_method="txt")` that qua MinerU
> 3.4.5 tren chinh file Figoni 1-25 trang ban `pdf_digital` (`data/uploads/0f92a0d4-…-1-25.pdf`,
> task `cdbd0988-1182-456d-bf23-791e03490bc6`, 89.0s): ket qua `confidence = 0.997628187250996`,
> `ocr_span_count = 1004` — **KHONG phai None**. Phan bo score trong `middle.json`: 1002 span
> `text` + 2 span `inline_equation` **deu co key `score`**; 998 span co `score == 1.0`, 6 span
> `< 1.0`. Nghia la MinerU 3.4.5 gan `score = 1.0` cho span lay tu text layer chu khong bo trong
> key `score`.
>
> **He qua bat buoc**: o `parse_method="txt"`, `confidence` (a) gan nhu khong bao gio `None`, va
> (b) **khong mang y nghia chat luong OCR** — no la trung binh bi pha loang boi 998 so 1.0. Moi
> noi tieu thu gia tri nay PHAI re theo `job.file_type` chu khong theo gia tri runner tra ve; xem
> S15-6 (da sua) o §6.15.3. Gia tri `None` van co the xay ra (tai lieu khong co span nao co key
> `score`) nen nhanh `None` trong `_compute_quality()` giu nguyen, khong sua code runner.


### [Architecture.md cũ] 6.22.6.1 — số đo kênh (2) trên job Le Cordon Bleu

Kênh (2) **không phải giả thuyết — đã ĐO trên output thật** (Domain Expert, job
`1ee1fdee-746e-4d3b-a54c-d27f7f2aa763`, Le Cordon Bleu 418 trang, chạy 2026-09-09 bằng babeldoc sau
khi Bug #9 tắt `font_shrink`):

- Trang 19 nguồn có 2 block: `'1'` (ngang) và `'History of Pâtisserie in France'`
  (bbox `(599.4, 156.4, 633.0, 528.3)`, `dir = (0.0, 1.0)` theo `page.get_texttrace()`, 31pt).
  Trang 19 **output chỉ còn `'1'`**.
- Trang 31: y hệt — mất `'A Life and Career in the Pastry Kitchen'` (bbox `(591.4, 156.4, 625.0, 643.7)`).
- Quy mô: **52/418 trang** của cuốn này có chữ dọc; tổng ký tự dọc nguồn **2.303** → output **1.327**.
- Và `layout_qa_findings` cho job đó = **0 row**, dù `babeldoc_rotated_text_overlay` mặc định `True`
  (`src/core/config.py:208`) và bước overlay đã tồn tại từ commit `b9c8952` ngày **2026-09-07**, tức
  **trước** ngày chạy job. ⇒ `overlay_rotated_text` **không phủ hết** kênh (2), và nó cũng không
  luôn để lại cờ khi không phủ được.


### [Architecture.md cũ] 6.22.6.1 — 3 cách đếm ký tự bị lọc đã bác + ứng viên thiết kế cho BL-08

**Quyết định về "đếm luôn ký tự bị loại ở `on_lt_char`" — KHÔNG làm trong BL-04 (R8-02
deny-by-default)**. Đã cân nhắc 3 cách và bác cả 3 **có lý do đo được**, không phải bác cho nhanh:

| Cách | Vì sao KHÔNG làm trong BL-04 |
|---|---|
| Patch `ActiveILCreater.project_native_char` (`il_creater_active.py:1292`), tự tính lại `get_rotation_angle(char.matrix)` rồi so với 2 khoảng chấp nhận | Phải **chép lại predicate của babeldoc** (2 khoảng + hằng số) thành nguồn sự thật thứ hai, trên **hàm nóng nhất của parser** — `project_native_char` chạy **mỗi ký tự** (~100k lời gọi/chunk 42 trang). Đúng khuôn hai-bản-sao-sẽ-lệch mà project này đã có sẹo (Bug #5, Bug #9) |
| Đếm theo **kết quả**: so `len(self._page_valid_chars_buffer)` trước/sau mỗi lời gọi | Nhiễu **không tách được**: `_collect_valid_char` (`il_creater_active.py:1439-1466`, đã đọc) còn tự loại thêm theo `unicodedata.category ∈ {Cc,Cs,Co,Cn}`, chuỗi chứa `"(cid:"`, và `font_mapper.has_char()` — những ca này **không** phải mất chữ do góc xoay. Một counter không phân biệt được 2 nguyên nhân là một counter sẽ bị bỏ qua sau vài lần báo động giả |
| Đếm ký tự trong IL tại chính hook đang có (`create_render_units_for_page`) rồi so với trang nguồn | **Sai điểm đo**: hook chạy **sau** dịch, ký tự ở đó là bản **VI**, không so được với nguồn EN. Muốn đếm ký tự IL *trước dịch* thì phải hook `ActiveILCreater` — quay lại 2 dòng trên |

⇒ Kênh (2)/(3) được ghi nhận thành backlog **BL-08**, kèm **ứng viên thiết kế đã khảo sát sẵn** để
người sau không phải làm lại phân tích: hook **`ActiveILCreater.on_page_end`**
(`<BD>/format/pdf/document_il/frontend/il_creater_active.py:386-407` — **1 lời gọi/trang**, không
phải mỗi ký tự, nên rẻ) đọc `self._page_valid_chars_buffer` (khởi tạo `:230`, gán `[]` ở `:384`, bị
clear ở `:407`) **trước khi** nó bị clear, so với số ký tự của trang nguồn qua PyMuPDF.

🚨 **Địa chỉ hook này đã được SỬA 2026-09-11 (Domain Expert X1)**. Bản trước ghi ứng viên là
`ILCreater.on_page_end` (`il_creater.py:641-664`). Patch class đó trong luồng dịch là **no-op**:
không ném lỗi, không ghi gì, và người implement sẽ kết luận sai *"đã đo, không ký tự nào bị lọc"* —
một **false negative im lặng**, đúng khuôn Bug #9. Ai nhận BL-08 phải patch bản `_active`; xem
self-correction R5-05 ở §6.22.1 để biết vì sao.

**Điều kiện tiên quyết của BL-08**: phải **đo trước** biên độ nhiễu giữa 2 bộ trích xuất (pdfminer
của babeldoc vs PyMuPDF) và nhiễu của `_collect_valid_char` (`il_creater_active.py:1439-1466`) trên
tài liệu thật, **rồi mới** đặt ngưỡng — cấm đặt ngưỡng từ suy đoán.
