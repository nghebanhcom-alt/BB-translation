# Review Report — Increment 1 (Project Scaffolding)

- **increment_number**: 1
- **iteration**: 1
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-03

## Verdict: REJECT

Lý do reject: 1 blocking issue (vị trí file `database.py` sai so với Architecture.md section 8, đã được xác nhận không phải judgment call hợp lý). Phần còn lại của scaffolding (data models, config, Docker, FastAPI skeleton) đạt chất lượng tốt, verify chạy được thực tế (không chỉ đọc tĩnh) — xem phần "Kết quả verify" bên dưới.

---

## Blocking issues (bắt buộc sửa trước khi merge)

### 1. `src/core/database.py` sai vị trí — phải là `src/models/database.py`

**File**: `src/core/database.py`
**Vấn đề**: Architecture.md section 8 (dòng 1304–1306) quy định rõ ràng:
```
├── models/                  # Data models (SQLModel + Pydantic)
│   ├── __init__.py
│   ├── database.py          # SQLite engine, session factory
│   ├── batch.py
│   ...
```
Dev đã đặt DB bootstrap (engine, session factory, `init_db()`) tại `src/core/database.py` thay vì `src/models/database.py`. CHANGELOG.md liệt kê đây là "deviation #1" với lý do "task spec của increment 1 yêu cầu rõ đặt tại `src/core/database.py`" — nhưng Architecture.md là spec chuẩn của dự án (đã qua Human Checkpoint 2) và không có gì mơ hồ ở đây; đây không phải là judgment call hợp lý, mà là sai lệch cần sửa.

**Cách sửa**:
1. Di chuyển nội dung `src/core/database.py` → `src/models/database.py`.
2. Cập nhật import trong `src/api/main.py` dòng 8:
   ```python
   from src.core.database import init_db
   ```
   → 
   ```python
   from src.models.database import init_db
   ```
3. Cập nhật comment tham chiếu trong `src/models/settings.py` dòng 14 (`# ... see src/core/database.py:`) → trỏ đúng `src/models/database.py`.
4. Xoá `src/core/database.py` và file `.pyc` cache tương ứng (`src/core/__pycache__/database.cpython-314.pyc`).
5. Chạy lại `ruff check src/`, import test (`from src.models import *`), và boot test (`TestClient` + `GET /health`) để xác nhận không có import nào còn trỏ sai — đã verify grep hiện tại chỉ có 2 chỗ tham chiếu `src.core.database` (main.py import + comment trong settings.py), nên fix gọn.

Sau khi Dev sửa xong, chỉ cần re-verify các bước trên (không cần review lại toàn bộ) để đóng vòng lặp này.

---

## Non-blocking suggestions (có thể để increment sau)

1. **`docker-compose.yml` đặt ở root thay vì `docker/docker-compose.yml`**: Architecture.md section 8 liệt kê `docker-compose.yml` nằm trong thư mục `docker/` cùng `Dockerfile`. Dev đặt file này ở root (`build.context: .`, `dockerfile: docker/Dockerfile`) — về mặt vận hành vẫn chạy tốt (`docker compose up -d` từ root là quy ước phổ biến, README cũng hướng dẫn vậy) và không gây lỗi kỹ thuật, nhưng đây là một sai lệch so với cây thư mục spec **không được ghi vào danh sách deviation trong CHANGELOG**. Đề nghị: hoặc di chuyển vào `docker/docker-compose.yml`, hoặc nếu giữ ở root (khuyến nghị vì đúng convention Docker Compose thực tế), bổ sung ghi chú deviation vào CHANGELOG để Tech Lead xác nhận và Architecture.md được cập nhật lại cho khớp thực tế.

2. **`src/api/routes/jobs.py` không khớp tên file trong spec**: Architecture.md section 8 liệt kê các route module riêng biệt: `upload.py`, `translate.py`, `history.py`, `download.py`, `settings.py` (+ `glossary.py`). Dev tạo `jobs.py` (chưa có trong spec) thay vì các file trên. Vì router hiện đang rỗng (chưa có handler), không phải blocking, nhưng nên là điểm cần làm rõ trước increment sau — hoặc đổi tên theo đúng spec, hoặc cập nhật Architecture.md nếu nhóm quyết định gộp thành `jobs.py`. Tương tự, `src/api/deps.py` và `src/api/websocket.py` trong spec vẫn chưa được tạo (chấp nhận được ở increment scaffolding-only, chỉ cần đảm bảo được tạo đúng lúc increment cần đến).

3. **`tests/` chỉ có `__init__.py`**: `pyproject.toml` đã cấu hình `pytest`/`pytest-asyncio` đầy đủ nhưng chưa có test thật nào (kể cả smoke test cho `/health` hoặc `init_db()`). Chấp nhận được vì increment này không có business logic, nhưng 1-2 smoke test (health check, `init_db` tạo đủ bảng) sẽ giúp increment sau có baseline CI ngay từ đầu.

4. **File thừa ở root không liên quan increment 1**: `glossarystarter.xlsx` và `repo-dịch.rtf` ở root project, và `data/glossary-starter.xlsx` (trong thư mục `data/` đã gitignore) — không nằm trong danh sách file Dev tạo theo CHANGELOG, có vẻ là file làm việc/tham khảo còn sót lại. Không blocking (không ảnh hưởng build/run) nhưng nên dọn dẹp khỏi root repo cho gọn.

5. **`greenlet` dependency (deviation #2 trong CHANGELOG)**: Approve — lý do kỹ thuật hợp lý (SQLAlchemy async engine cần greenlet để chạy `engine.begin()`), đã ghi rõ trong CHANGELOG. Không cần sửa.

---

## Checklist verify (đã tự chạy, không chỉ đọc tĩnh)

| Hạng mục | Kết quả |
|---|---|
| Vị trí file theo Architecture.md §8 | 1 sai lệch blocking (`database.py`) + 2 sai lệch non-blocking (`docker-compose.yml`, route file naming) — chi tiết ở trên |
| Data models đúng schema (§4.2) | Đối chiếu từng field/type/index của `Batch`, `Job`, `Chunk`, `OverflowReport`, `Glossary`, `GlossaryEntry`, `TranslationCache`, `Setting` với SQL DDL trong Architecture.md — khớp đầy đủ. `Job.job_type` có mặt, default `"translate"`, comment đúng `translate \| parse_only` theo §6.8/BR-PARSE |
| Security | `config.py` không hardcode secret (đọc từ `.env` qua `pydantic-settings`); `.env.example` không có giá trị thật; `.gitignore` đủ `.env`, `*.db`, `*.db-shm`, `*.db-wal`, `__pycache__/`, `.venv/`, `data/` |
| Docker setup (§7) | `docker-compose.yml` khớp env vars, volumes, resource limits (16G/6cpu app, 8G/4cpu mineru), healthcheck đúng spec (vị trí file là sai lệch non-blocking, xem trên). `Dockerfile` khớp base image, `calibre`, `uv sync --frozen --no-dev`, COPY src/web/fonts, tạo `/data/*` dirs, CMD đúng |
| Type hints & code style | Đọc qua toàn bộ `src/`: type hints đầy đủ trên function signature, `snake_case` cho function/field, `PascalCase` cho class — tuân thủ convention |
| FastAPI skeleton | `lifespan` gọi `init_db()` đúng cách; CORS giới hạn `localhost:8000`/`127.0.0.1:8000` hợp lý cho dev; `GET /health` hoạt động — verify bằng `TestClient` thực tế: `200 {"status": "ok"}` |
| `ruff check src/` | **All checks passed** (chạy thực tế qua `.venv/bin/ruff`) |
| `from src.models import *` | Import thành công, không lỗi |
| Boot test qua `TestClient` (lifespan → `init_db()`) | `GET /health` → `200 {"status": "ok"}`; DB tạo đủ 8 bảng: `batches`, `jobs`, `chunks`, `overflow_reports`, `glossaries`, `glossary_entries`, `translation_cache`, `settings`; `PRAGMA journal_mode` → `wal` xác nhận WAL mode bật đúng |

Tất cả claim "Kết quả verify" trong CHANGELOG.md của Dev đã được review tự chạy lại và xác nhận đúng (không chỉ tin theo báo cáo).

---

## Next step

Dev sửa blocking issue #1 (di chuyển `database.py`), cập nhật CHANGELOG.md ghi lại lần sửa, gửi lại Reviewer để đóng iteration 1. Circuit breaker Dev↔Reviewer: hiện tại 1/3 vòng.

---
---

# Iteration 2 — Verify Fix Round 1

- **increment_number**: 1
- **iteration**: 2
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-03

## Verdict: APPROVE

Đây là vòng verify fix (không phải review toàn diện lại), đối chiếu với danh sách Dev báo cáo trong `docs/CHANGELOG.md` mục "Increment 1 — Fix Round 1". Tất cả các điểm đã được tự chạy verify thực tế (không chỉ đọc tĩnh) và đều đạt.

## Kết quả verify

### 1. Blocking issue #1 — vị trí `database.py`

| Kiểm tra | Kết quả |
|---|---|
| `find . -iname "database.py"` | Chỉ còn `./src/models/database.py`, `src/core/database.py` không còn tồn tại |
| `grep -rn "src\.core\.database"` trên toàn repo (`*.py`) | Không có match nào — chỉ còn nhắc tới trong CHANGELOG.md/review-report.md (lịch sử), đúng như dự kiến |
| `src/api/main.py` dòng 8 | `from src.models.database import init_db` — đã sửa đúng |
| `src/models/settings.py` dòng 14 | Comment đã trỏ đúng `see src/models/database.py` |
| `src/core/` | Chỉ còn `config.py` + `__init__.py`, không xoá nhầm gì khác |
| `.venv/bin/python -c "from src.models import *"` | Chạy thực tế: **thành công**, in `models OK` |
| `.venv/bin/python -c "from src.api.main import app"` | Chạy thực tế: **thành công**, in `app OK` — xác nhận toàn bộ import chain (main → models.database → models) hoạt động đúng |

**Kết luận**: Blocking issue #1 đã fix đúng, đầy đủ, không sót reference nào trong code.

### 2. `docker-compose.yml` — vị trí và path tương đối

- File đã ở đúng vị trí `docker/docker-compose.yml` theo Architecture.md section 8.
- Đọc nội dung và tính tay lại path tương đối so với vị trí file mới (`docker/`):
  - `build.context: ..` → trỏ về repo root — đúng.
  - `build.dockerfile: docker/Dockerfile` → được resolve tương đối theo `context` (repo root), tức `<root>/docker/Dockerfile` — đúng, đúng là file Dockerfile hiện có.
  - `volumes: ../data:/data` → từ `docker/` đi lên 1 cấp ra `<root>/data` — đúng, khớp thư mục `data/` ở repo root.
  - `volumes: ../fonts:/app/fonts` → từ `docker/` đi lên 1 cấp ra `<root>/fonts` — đúng theo cấu trúc dự kiến (thư mục fonts ở root, Dockerfile cũng `COPY fonts/ ./fonts/` từ root build context).
  - Service `mineru` cũng dùng `../data:/data` — nhất quán.
- Không có Docker trên máy Reviewer để chạy `docker compose config` xác nhận runtime, nhưng việc tính tay xác nhận mọi path tương đối đều resolve đúng vị trí thực tế trên đĩa (đã đối chiếu bằng `ls`/`find`).

**Kết luận**: Đạt, path tương đối chính xác cho vị trí file mới.

### 3. File dọn dẹp

| Kiểm tra | Kết quả |
|---|---|
| `glossarystarter.xlsx` ở root | Đã xoá — không còn xuất hiện trong `find . -iname "*glossary*"` |
| `data/glossary-starter.xlsx` | Vẫn còn nguyên |
| `repo-dịch.rtf` ở root | Vẫn còn nguyên, không bị đụng vào |

**Kết luận**: Đạt, đúng như báo cáo của Dev.

### 4. Smoke test

`.venv/bin/python -m pytest tests/ -v` → **1 passed** (`tests/test_health.py::test_health`), không có lỗi/warning nghiêm trọng (chỉ có 1 DeprecationWarning vô hại từ `starlette.testclient` không liên quan tới code của Dev).

### 5. Regression check

`.venv/bin/ruff check src/` → **All checks passed**. Không có gì gãy trong lúc sửa.

## Non-blocking items còn tồn đọng (không chặn approve, đã ghi nhận từ iteration 1)

Các suggestion #2 (tên file route `jobs.py` vs spec) không nằm trong scope fix round này (Dev đã nêu rõ "để increment sau, theo chỉ đạo") — chấp nhận được, không phải blocking cho increment scaffolding.

## Next step

Increment 1 (Project Scaffolding) **APPROVED**. Circuit breaker Dev↔Reviewer: đóng ở 2/3 vòng (không cần vòng 3). Sẵn sàng chuyển cho QA hoặc bắt đầu increment tiếp theo.

---
---

# Increment 2 — Iteration 1

- **increment_number**: 2
- **iteration**: 1
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-03

## Verdict: APPROVE

Review toàn bộ File Router, service wrappers (pdf2zh/MinerU), Excel I/O, GlossaryManager, và API glossary. Chất lượng tốt, business logic cốt lõi (BR-GLOSS-01→06, BR-INPUT-02) đúng và có test thực chứng minh (không chỉ đọc tĩnh). Không có blocking issue — các điểm tìm được đều là gap/hoàn thiện có thể xử lý ở increment sau mà không rủi ro cho pipeline dịch thật (vì `job_orchestrator`/`pdf_digital.py`/`pdf_scan.py` chưa gọi tới các wrapper này).

---

## 1. Verify riêng: thay đổi `src/models/database.py` (AsyncSession)

Dev đổi `class_=AsyncSession` từ `sqlalchemy.ext.asyncio.AsyncSession` sang `sqlmodel.ext.asyncio.session.AsyncSession`. Tự kiểm chứng (không tin lời Dev):

- Đọc source `sqlmodel/ext/asyncio/session.py`: `AsyncSession` của SQLModel là subclass thật sự của `sqlalchemy.ext.asyncio.AsyncSession`, chỉ **thêm** method `.exec()` (wrap `.execute()` + trả `ScalarResult`/model instances thay vì `Row`) — không override/xoá method nào của lớp cha. Đây đúng là mở rộng, không phải thay thế hành vi.
- Chạy lại `pytest tests/test_health.py -v` (route duy nhất còn lại thuần từ Increment 1, đi qua `init_db()` → `get_engine()`/WAL/index): **PASS**, `GET /health` → `200 {"status": "ok"}`.
- Chạy lại toàn bộ `pytest tests/ -v`: **27 passed**, không có test nào lộ vỡ do đổi session class.
- `init_db()` không đổi logic (vẫn dùng raw `conn.execute(text(...))` qua `AsyncEngine`, không qua session) → WAL mode và index `idx_glossary_entries_term_nocase` không bị ảnh hưởng bởi thay đổi này.

**Kết luận**: Claim "tương thích ngược 100%" của Dev là **đúng**, đã tự verify bằng cách đọc source lớp con + chạy lại toàn bộ test suite, không chỉ tin lời báo cáo. Đây là thay đổi hợp lý và cần thiết (code nghiệp vụ dùng `.exec()` khắp nơi trong `GlossaryManager`/routes, không thể chạy được với `AsyncSession` gốc của SQLAlchemy). Không cần escalate lại cho Tech Lead — đúng như Dev tự đánh giá, vì đây là cách dùng chuẩn của ORM đã chọn (SQLModel), không phải đổi kiến trúc.

---

## 2. File Router (BR-INPUT-02)

`src/core/file_router.py`: ngưỡng `> 0.9` (strictly greater, đúng "> 90%" trong BR-INPUT-02), "trang có text" = `page.get_text().strip()` non-empty — hợp lý, xử lý đúng whitespace-only page như scan.

Test (`tests/test_file_router.py`, 5 case) chạy PASS thật (tự tạo PDF bằng PyMuPDF, không cần fixture ngoài):
- Toàn text → digital — đúng
- Toàn ảnh, không text → scan — đúng
- Biên 9/10 = 90% chẵn → vẫn scan (đúng vì không `>` 90%, đây là test case biên tốt nhất trong bộ, hơn cả yêu cầu "50/50" gốc)
- `.epub` → EPUB
- extension lạ → `UnsupportedFileTypeError`

**Gap về coverage** (non-blocking, xem mục Suggestions): thiếu test PDF corrupt/không mở được (`fitz.open()` sẽ raise exception thô, không wrap thành lỗi rõ ràng), thiếu test mixed ngay-trên-ngưỡng (vd 91%) để chứng minh nhánh digital của tỷ lệ không tròn số.

---

## 3. Service wrappers

### `pdf2zh_runner.py`
- Raise `Pdf2zhError` kèm `stderr` khi `returncode != 0` — rõ ràng, không che giấu lỗi.
- Test mock `asyncio.create_subprocess_exec` cho cả success/failure — verify args build đúng (`--pages`, `--prompt`) khớp Architecture.md 3.1[3b].
- **Gap đáng chú ý (non-blocking nhưng nên sửa sớm)**: không tạo `output_path.parent` trước khi gọi subprocess. Nếu `job_orchestrator` (increment sau) không tự tạo thư mục `chunks/` trước, lệnh `pdf2zh --output <dir không tồn tại>` có thể fail tuỳ hành vi thực tế của CLI — chưa verify được vì chưa cài pdf2zh thật trên máy dev. Đề nghị thêm `output_path.parent.mkdir(parents=True, exist_ok=True)` phòng thủ, giống cách `mineru_runner.py` đã làm đúng với `output_dir.mkdir(...)`.
- Không bắt riêng `FileNotFoundError` (executable `pdf2zh` không có trong PATH) — sẽ propagate ra ngoài dưới dạng `OSError` thô thay vì `Pdf2zhError` rõ ràng. Không phải che giấu lỗi (traceback vẫn đủ thông tin) nhưng thiếu nhất quán.

### `mineru_runner.py`
- Đúng theo Architecture.md section 7.1 (MinerU là HTTP sidecar container, không phải CLI local) — deviation #3 trong CHANGELOG hợp lý, có căn cứ rõ trong Architecture (dù section 3.2 mô tả CLI, section 7.1 mô tả container/port — Dev chọn diễn giải nhất quán với docker-compose, cần Tech Lead xác nhận lại theo đúng như Dev đã tự đề xuất, không phải lỗi).
- Lỗi HTTP status và connection error đều raise `MinerUError` rõ ràng, không nuốt exception (`httpx.HTTPError` caught và wrap có kèm nguyên nhân gốc qua `raise ... from exc`).
- `response.json()` không được try/except riêng — nếu MinerU trả về body không phải JSON hợp lệ sẽ raise lỗi thô `json.JSONDecodeError` thay vì `MinerUError`. Nhỏ, không blocking.
- Test mock `httpx.AsyncClient` đúng cho cả 3 case (success, HTTP 500, connection error) — verify thực.

Cả 2 wrapper đều đủ interface (input path, output path/dir, trả dataclass result rõ ràng) để `pdf_digital.py`/`pdf_scan.py` cắm vào ở increment sau mà không cần đổi signature.

---

## 4. GlossaryManager (BR-GLOSS-01 → 06)

Đọc kỹ + tự nghĩ thêm case ngoài test có sẵn để kiểm chứng:

- **BR-GLOSS-02 (case-insensitive)**: dùng `func.lower(GlossaryEntry.term_en) == term.lower()` ở tầng SQL — đúng, không phụ thuộc collation của cột (dù `init_db()` cũng đã tạo index `COLLATE NOCASE` riêng cho tối ưu tốc độ). Tự test case "GANACHE" (import bằng "Fondant", query "fONDANT") đã pass — thử thêm nhẩm case "GANACHE" toàn hoa cũng sẽ đúng vì `func.lower()` áp dụng cả hai vế, không phụ thuộc cách nhập.
- **BR-GLOSS-06 (project override global)**: `get_entry()` check scope `project:{id}` trước, fallback `global` — đúng. Test còn kiểm tra dự án khác (`batch-999`) không có override vẫn fallback global đúng — tốt hơn yêu cầu tối thiểu.
- **BR-GLOSS-03 (last-updated-wins)**: `bulk_import()` overwrite trực tiếp field + `updated_at = datetime.now(UTC)` khi tìm thấy entry cùng scope+term — đúng, vì lần ghi sau luôn là lần ghi gần nhất (tự nhiên thoả last-write-wins, đúng như Dev giải thích). Đã tự verify test update giá trị mới thắng.
- **`build_prompt_snippet()`**: format khớp with ví dụ Architecture.md 6.2 (`| EN | VI |` header + `|---|---|`), xử lý target rỗng/"(keep)" đúng BR-GLOSS-04 → ghi rõ "(keep) - GIU NGUYEN tieng Anh" thay vì để trống — rõ ràng hơn bản gốc Architecture (dùng để LLM hiểu chắc chắn), hợp lý. `project_id` override đúng khi build cho 1 project cụ thể — verify bằng test.

Không tìm được lỗ hổng logic nào trong `GlossaryManager` sau khi tự nghĩ thêm case.

---

## 5. Excel roundtrip (BR-GLOSS-04, 05)

Test `test_export_then_import_roundtrip` xác nhận export→import giữ nguyên `term_en`/`term_vi`/`notes`, kể cả case `(keep)`. `import_glossary_from_excel` trim whitespace, skip dòng rỗng, raise `GlossaryExcelError` khi thiếu cột A/B hoặc file rỗng — verify chạy thật, pass. Entry `"(keep)"` xử lý đúng: giữ nguyên chuỗi `"(keep)"` qua excel_utils (không tự convert thành `None`), và `GlossaryManager.build_prompt_snippet()` coi cả `None` lẫn `"(keep)"` là "giữ nguyên" (`_KEEP_MARKERS`) — nhất quán đúng BR-GLOSS-04.

---

## 6. API endpoints (US-03, AC-03.1 → AC-03.4)

- **AC-03.1** (parse Excel → preview → confirm): đúng, `POST /import` không đụng DB (verify bằng test `list_before_confirm.total == 0` trước khi confirm), `POST /import/confirm` mới ghi.
- **AC-03.3** (sửa entry, lưu ngay): `PUT /{entry_id}` cập nhật + `updated_at` mới — đúng.
- **AC-03.4** (export Excel format giống import): đúng, dùng lại `export_glossary_to_excel`.
- **Flow 2 bước không có staging `import_id` ở server**: client tự giữ danh sách entries giữa `/import` và `/import/confirm`, tức là **ai cũng có thể POST thẳng vào `/import/confirm` mà không cần gọi `/import` trước** (không có token/id ràng buộc 2 bước phải đi cùng nhau). Đánh giá theo đúng ngữ cảnh: đây là app 1-user nội bộ, không có khái niệm "user khác" cần cô lập, và hậu quả tối đa nếu ai đó bypass là tự ghi glossary sai vào DB của chính mình — **chấp nhận được**, không phải lỗ hổng bảo mật thực sự trong ngữ cảnh này. Đã ghi rõ trong CHANGELOG deviation #2, hợp lý.
- **Gap**: `GET /api/glossary` (list) **không có tham số `scope`/`project_id`** và response `GlossaryEntryOut` **không trả về `scope`** — liệt kê lẫn lộn toàn bộ entry ở mọi glossary (global + mọi project) không phân biệt được. Không vi phạm trực tiếp AC-03.1→03.4 (các AC này không yêu cầu filter theo scope), và logic dịch thật (`GlossaryManager.get_entry`/`build_prompt_snippet`) vẫn đúng BR-GLOSS-06 vì không đi qua endpoint này. Nhưng đây là gap cần xử lý **trước khi làm frontend glossary UI** (increment sau) — nếu không, user sẽ thấy 1 danh sách phẳng, sửa nhầm entry global tưởng là project hoặc ngược lại. Xếp vào non-blocking suggestion quan trọng, không chặn increment này vì chưa có frontend nào phụ thuộc vào nó.
- **Gap phụ**: không có endpoint tạo 1 entry thủ công (`POST /api/glossary` thêm 1 term đơn lẻ, không qua Excel) — Architecture.md 5.1 có liệt kê (`POST /glossaries/{id}/entries`) nhưng AC-03 không yêu cầu rõ (workflow chính là Excel import). Chấp nhận được cho increment này, nên bổ sung khi làm frontend nếu cần "thêm nhanh 1 từ mới" mà không phải qua Excel.

---

## 7. Security (đánh giá theo ngữ cảnh 1-user internal tool)

- Extension check `.xlsx`/`.xlsm` trước khi parse — chặn được file rác cơ bản. Không check magic bytes, nhưng `openpyxl.load_workbook()` sẽ tự raise lỗi rõ ràng (400) nếu file không phải OOXML thật, nên rủi ro thấp.
- **Không có giới hạn kích thước file** cho glossary Excel upload (khác với PDF/EPUB đã có `MAX_UPLOAD_SIZE_MB` trong `config.py`, nhưng chưa được áp dụng ở route glossary import — thực ra chưa route nào dùng `max_upload_size_mb` cả, kể cả cho PDF, vì `upload.py` chưa được viết). Với glossary (< 500 entries theo Architecture.md), rủi ro DoS thấp cho 1-user local app — chấp nhận được, nhưng nên thêm 1 giới hạn nhỏ (vd 5-10MB) khi viết `upload.py`/glossary route hoàn chỉnh sau này để phòng thân.
- Temp file dùng `tempfile.NamedTemporaryFile`/`tempfile.mkstemp` đúng cách, có `unlink`/không để rác lại (trừ file export — `FileResponse` trả về path tạm, không tự xoá sau khi stream xong; rò rỉ file tạm nhỏ theo thời gian chấp nhận được cho 1-user local, nhưng đáng ghi chú cho tương lai nếu chuyển cloud).

---

## 8. Type hints, style, test count

- `ruff check src/`: chạy thực tế → **All checks passed**, khớp báo cáo Dev.
- `ruff check src/ tests/` (mở rộng cả tests, Dev không claim phần này): 1 lỗi `PYI034` trong `tests/test_mineru_runner.py:31` (`__aenter__` nên return `Self` thay vì tên class dạng string) — không nằm trong scope claim của Dev (`ruff check src/`), không blocking, nhưng nên dọn khi có dịp.
- `pytest tests/ -v`: chạy thực tế → **27 passed**, khớp chính xác con số Dev báo cáo (5 file_router + 2 pdf2zh_runner + 3 mineru_runner + 4 excel_utils + 8 glossary_manager + 4 integration API + 1 test_health).
- Type hints đầy đủ trên toàn bộ function signature đã đọc, `snake_case`/`PascalCase` đúng convention.

---

## Blocking issues

**Không có.** Không tìm thấy lỗi nào đủ nghiêm trọng để chặn merge — business logic cốt lõi (File Router, GlossaryManager) đúng và có test thực chứng minh; các gap tìm được (mkdir phòng thủ, scope filter ở API list, thiếu size limit, thiếu 1-2 test case biên) đều không ảnh hưởng chức năng đã cam kết trong AC-03/BR-INPUT-02/BR-GLOSS-01→06 của increment này, và không có rủi ro dây chuyền sang code khác vì `job_orchestrator`/pipelines chưa được viết để gọi tới các wrapper này.

## Non-blocking suggestions

1. **`pdf2zh_runner.py`**: thêm `output_path.parent.mkdir(parents=True, exist_ok=True)` trước khi gọi subprocess (phòng thủ, giống `mineru_runner.py` đã làm) — nên làm trước khi increment nối `job_orchestrator` vào wrapper này.
2. **`pdf2zh_runner.py`**: bắt riêng `FileNotFoundError`/`OSError` khi executable không tồn tại, wrap thành `Pdf2zhError` cho nhất quán với case exit-code lỗi.
3. **`mineru_runner.py`**: bọc `response.json()` trong try/except, raise `MinerUError` rõ ràng thay vì để lộ `JSONDecodeError` thô khi MinerU trả body không hợp lệ.
4. **`GET /api/glossary`**: thêm query param `scope`/`project_id` để filter, và trả `scope` trong `GlossaryEntryOut` — cần làm trước khi bắt đầu frontend glossary UI (increment sau) để tránh user nhầm lẫn global/project entry.
5. Cân nhắc thêm `POST /api/glossary` (thêm 1 entry thủ công, không qua Excel) nếu frontend cần "thêm nhanh 1 từ" mà không mở luôn Excel.
6. Thêm giới hạn kích thước file cho glossary Excel import (vd 5-10MB) khi hoàn thiện route upload chung.
7. Thêm test: PDF corrupt (fitz mở lỗi) cho `file_router.py`, và case tỷ lệ ngay trên ngưỡng (vd 91%) để chứng minh nhánh digital hoạt động đúng với số lẻ.
8. `ruff check` cho `tests/` cũng nên chạy trong CI (không chỉ `src/`) — hiện có 1 lỗi `PYI034` nhỏ ở `test_mineru_runner.py:31`.
9. `FileResponse` cho `/export` không dọn file tạm sau khi stream — chấp nhận được cho local 1-user, ghi chú lại nếu triển khai cloud multi-request sau này.

## Next step

Increment 2 (File Router + Parsing wrappers + Glossary Management) **APPROVED** tại iteration 1/3. Không cần vòng sửa nào — các suggestion ở trên có thể gộp xử lý ở increment tiếp theo (Job Orchestrator/Chunking hoặc Frontend Glossary UI) khi tiện, không cần vòng riêng cho increment này.

---
---

# Increment 3 — Iteration 1

- **increment_number**: 3
- **iteration**: 1
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-04

## Verdict: APPROVE

Review toàn bộ Translation Engine đa provider (Claude/OpenAI/DeepSeek/Gemini/DeepL/Ollama), Prompt Builder, Unit Conversion Table, Cost Estimator, Provider Factory, config, và 2 gap fix từ Increment 2. Không có blocking issue. Deviation `TranslationResult` được đánh giá là hợp lý và **APPROVE**, có căn cứ rõ trong DB schema. `57 passed` đã tự chạy lại và xác nhận đúng, không tin số Dev báo cáo suông.

---

## 1. Deviation `TranslationProvider.translate()` trả `TranslationResult` thay vì `str`

Đối chiếu bảng `jobs` trong Architecture.md section 4.2 (dòng 441–445):

```sql
model           TEXT NOT NULL,
estimated_cost  REAL,              -- USD
actual_cost     REAL,
ocr_confidence  REAL,
```

`jobs.actual_cost` tồn tại thật trong schema đã duyệt (Human Checkpoint 2), và `chunks` table cũng có sẵn `api_tokens_used`/`api_cost` (dòng 467–468) — tức là schema gốc của chính Tech Lead đã ngụ ý cần token/cost thực tế per-call, chỉ là code mẫu ở section 6.6 (viết sau, minh hoạ nhanh) quên khớp lại với interface đầy đủ ở section 5.3 — nơi `TranslationResult` đã được định nghĩa đúng với các field `tokens_input/tokens_output/cost_usd/model/cached` từ đầu. Vậy thực chất đây không phải Dev tự sáng tạo field mới, mà là chọn đúng phiên bản interface đã có sẵn trong Architecture.md (section 5.3) thay vì bản rút gọn ở section 6.6 — hai chỗ trong cùng 1 file mâu thuẫn nhau, và Dev đã chọn đúng bản khớp với DB schema.

**Kết luận: APPROVE deviation này.** Đây là lựa chọn đúng, không phải over-engineering/scope creep — nếu chọn `str` như section 6.6, `actual_cost`/`api_tokens_used`/`api_cost` trong DB sẽ không có cách nào lấy được dữ liệu ở increment Job Orchestrator, buộc phải quay lại sửa signature này sau, tốn thêm 1 vòng thay đổi interface giữa chừng. Không cần escalate lên Tech Lead — nêu rõ trong CHANGELOG đã đủ minh bạch. Duy nhất 1 điểm nhỏ nên sửa (non-blocking): field name trong code (`text`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `provider_name`) khác tên field so với dataclass mẫu ở Architecture.md 5.3 (`translated_text`, `tokens_input`, `tokens_output`, `cost_usd`, `model`, `cached`) — không sai về mặt chức năng (đây vẫn là interface nội bộ, không phải API công khai), nhưng nên ghi thêm 1 dòng trong CHANGELOG/docstring giải thích rõ tên field cũng đổi khác so với 5.3, không chỉ nói "đổi return type", để tránh Tech Lead đọc lướt và tưởng field name giữ nguyên.

---

## 2. Sáu provider implementations

| Provider | Error handling nhất quán | Ghi chú |
|---|---|---|
| Claude | `AuthenticationError`/`RateLimitError`/`TranslationProviderError` đúng phân loại theo BR-BATCH-02 (permanent vs transient) | Đạt |
| OpenAI | Idem, dùng `self.provider_name` (không hardcode `"openai"`) nên message lỗi tự đúng khi subclass hoá bởi DeepSeek | Đạt |
| DeepSeek | Kế thừa `OpenAIProvider` đúng cách: chỉ override `provider_name`, `__init__` (đổi default `model`/`base_url`), và `estimate_cost()` (pricing riêng) — **không duplicate** logic `translate()`, gọi `super().__init__()` đúng, không copy-paste code gọi API | Đạt, đúng như Architecture.md 6.6 dự kiến |
| Gemini | Map đúng `Unauthenticated`/`PermissionDenied` → `AuthenticationError`, `ResourceExhausted`/`TooManyRequests` → `RateLimitError`, còn lại → `TranslationProviderError` | Đạt |
| Ollama | Không có khái niệm auth (local server) nên không raise `AuthenticationError` — đúng, có giải thích rõ trong docstring. HTTP 429 → `RateLimitError`, còn lại → `TranslationProviderError` | Đạt |
| DeepL | `AuthorizationException` → `AuthenticationError`, `TooManyRequestsException` → `RateLimitError`, `DeepLException` còn lại → `TranslationProviderError` | Đạt |

**DeepL — `glossary_id=None` gọi `translate_text(..., glossary=None)`**: đã tự kiểm tra chữ ký `deepl.Translator.translate_text` — tham số `glossary` là optional, `None` là giá trị mặc định hợp lệ của chính SDK (nghĩa là "không áp dụng glossary"), không phải giá trị đặc biệt cần Provider tự xử lý riêng. Tức là gọi `DeepLProvider` mà không truyền `glossary_id` sẽ **dịch bình thường, không có ràng buộc glossary, không crash** — hành vi graceful, đúng kỳ vọng, không gây confusion cho code gọi. TODO glossary sync để lại cho increment Job Orchestrator được document rất rõ ràng trong module docstring của `deepl_provider.py` (kèm luôn API cần gọi sau này — `translator.create_glossary(...)`), đủ chi tiết để increment sau không cần đọc lại code mới hiểu được scope còn thiếu.

---

## 3. Prompt Builder

Đọc `src/core/prompt_builder.py` + `src/utils/unit_conversion_table.py`, verify từng phần bắt buộc có mặt trong `build_system_prompt()`:

1. Glossary table — có, tái dùng `GlossaryManager.build_prompt_snippet()` (Increment 2), fallback rõ ràng khi glossary trống thay vì để trống gây prompt mơ hồ.
2. Unit conversion table — có, `build_unit_conversion_section()` bao gồm cả 6 rule chuyển đổi (cups/tbsp/tsp/oz/°F/inches) lẫn bảng nguyên liệu 9 dòng, khớp 1:1 với Architecture.md 6.2.
3. Chỉ dẫn súc tích ≤130% — có (`_CONCISENESS_RULE`, đúng số thứ tự "2." khớp Architecture.md).
4. Chỉ dẫn giữ typography (BR-TYPO-01→04) — có, `_TYPOGRAPHY_RULES` liệt kê đủ cả 4 rule (heading size ratio, list type, bold/italic/underline vị trí, indentation level nested list) — đây là phần **mở rộng thêm so với Architecture.md 6.2** (bản gốc chỉ có 3 mục: glossary/conciseness/unit, không có mục typography) nhưng đúng theo PRD section 4.6 (BR-TYPO) — hợp lý, không phải scope creep vì đây là business rule đã duyệt, chỉ là Architecture.md 6.2 viết thiếu.

Đọc `tests/test_prompt_builder.py` (2 test): `test_system_prompt_contains_all_required_sections` assert đủ cả glossary/unit/conciseness/typography xuất hiện trong output string; `test_system_prompt_handles_empty_glossary` verify fallback không raise lỗi khi glossary rỗng. Coverage đủ cho phạm vi increment này (chưa test integration thật với LLM, nhưng đó là kỳ vọng đúng — prompt builder chỉ ghép string).

---

## 4. Cost Estimator

`estimate_job_cost()`: `estimated_input_tokens = total_pages * 500`, `estimated_output_tokens = int(input * 1.3)`, sau đó gọi `provider.estimate_cost(input, output)` — nhân đúng qua interface provider (không tự tính giá riêng, tái dùng logic pricing đã có ở từng provider, tránh duplicate 2 nơi tính giá). Test (`tests/test_cost_estimator.py`, 4 test — không đọc trực tiếp nhưng suite pass xác nhận qua chạy thật) cùng với `estimate_cost()` verify riêng ở từng provider trong `test_translation_providers.py::test_claude_estimate_cost`. Công thức hợp lý cho mục đích heuristic ước lượng trước khi dịch (PRD R-01), có `ValueError` guard khi `total_pages < 0`. Docstring ghi rõ "Not measured from real documents yet" — không gây hiểu lầm là số chính xác.

---

## 5. Giả định giá OpenAI/Gemini/DeepL

| Provider | Giá | Ghi chú rõ ràng? |
|---|---|---|
| OpenAI | $2.5/$10 per MTok (gpt-4o) | Có — docstring module + comment inline đều ghi "not specified in Architecture.md... reference only, may change" |
| Gemini | $1.25/$10 per MTok (Gemini 2.5 Pro) | Có — tương tự, ghi rõ "not given in Architecture.md... reference only" |
| DeepL | $25/1M ký tự, quy đổi ~4 ký tự/token | Có — ghi rõ đây là xấp xỉ vì DeepL tính theo ký tự chứ không theo token, khuyến nghị "confirm against the real DeepL account plan before relying on this number" |

Đánh giá: đây là judgment call hợp lý cho increment này — không có số liệu chính thức trong Architecture.md, Dev không thể block cả increment chỉ vì thiếu giá tham khảo, và mọi chỗ đều ghi chú rõ ràng ở cả docstring module lẫn CHANGELOG để không ai nhầm là số liệu chính xác/cam kết. Risk R-01 (PRD) về "chi phí API cao" vẫn được mitigate đúng tinh thần vì đây chỉ là ước lượng hiển thị trước khi dịch, không phải billing thật.

---

## 6. Hai gap fix từ Increment 2

### 6.1. `GET /api/glossary` thiếu field `scope`

Đọc `src/api/routes/glossary.py`: `GlossaryEntryOut` đã có field `scope: str`; `list_entries` join `GlossaryEntry` với `Glossary` lấy đúng `scope`, hỗ trợ filter `?scope=` qua `where(Glossary.scope == scope)` áp dụng cho cả `count_statement` lẫn `list_statement` (không bị lệch số `total` so với danh sách trả về — kiểm tra kỹ vì đây là lỗi thường gặp khi thêm filter). `update_entry` cũng query lại `Glossary` theo `entry.glossary_id` để trả đúng `scope` sau khi sửa. Đúng như mô tả trong CHANGELOG.

### 6.2. `pdf2zh_runner.py` thiếu `mkdir` phòng thủ

Đọc `src/services/pdf2zh_runner.py` dòng 55: `output_path.parent.mkdir(parents=True, exist_ok=True)` được gọi **trước** khi spawn subprocess — đúng vị trí, đúng pattern đã dùng ở `mineru_runner.py` từ Increment 2. Test `test_translate_pages_creates_output_parent_dir` (`tests/test_pdf2zh_runner.py`) verify bằng cách trỏ `output_path` vào 1 thư mục con chưa tồn tại, chạy `pytest` thật xác nhận PASS.

---

## 7. Tự chạy lại (không tin số Dev báo cáo)

```
.venv/bin/ruff check src/       → All checks passed!
.venv/bin/pytest tests/ -v      → 57 passed, 55 warnings in 1.41s
```

Đếm chi tiết khớp đúng CHANGELOG: 27 test cũ (Increment 1+2) + 30 test mới (9 test_provider_factory + 15 test_translation_providers + 2 test_prompt_builder + 4 test_cost_estimator, còn lại pdf2zh mkdir + glossary scope nằm trong 2 file test đã tồn tại từ trước nên không cộng thêm file mới) = 57. Không có test nào bị skip/xfail ẩn.

Warning đáng chú ý (không blocking): `google.generativeai` phát `FutureWarning` deprecated, đúng như Dev đã ghi trong CHANGELOG — chấp nhận được, để Tech Lead quyết định migrate `google-genai` ở increment sau.

---

## 8. Security — API key logging

Grep toàn bộ `src/services/` và `src/core/` cho `print(`, `logging.`, `logger.`: **không có kết quả nào** — chưa có logging layer nào được thêm ở increment này, nghĩa là không có chỗ nào vô tình log ra `api_key`. Các exception message (`f"Claude authentication failed: {exc}"`, v.v.) chỉ echo lại message từ SDK gốc (`anthropic.AuthenticationError`, `openai.AuthenticationError`...) — các SDK này không đưa API key vào nội dung exception message theo thiết kế chuẩn (chỉ báo "invalid API key" chung chung), nên không có rò rỉ key qua log/traceback ở tầng code Dev viết. `provider_factory.py` chỉ đọc `settings.xxx_api_key` để truyền vào constructor, không print/log giá trị. **Không tìm thấy lỗi bảo mật.**

---

## Blocking issues

**Không có.**

## Non-blocking suggestions

1. Ghi rõ hơn trong CHANGELOG (hoặc docstring `translation.py`) rằng tên field của `TranslationResult` cũng khác so với dataclass mẫu ở Architecture.md section 5.3 (`text` vs `translated_text`, `input_tokens` vs `tokens_input`, v.v.), không chỉ nói "đổi return type" — tránh Tech Lead hiểu nhầm chỉ có kiểu trả về đổi còn field name giữ nguyên.
2. `TranslationResult` chưa có field `cached` như dataclass mẫu Architecture.md 5.3 (dùng cho `translation_cache` table) — chưa cần thiết ở increment này vì cache logic chưa implement, nhưng nên flag cho increment Job Orchestrator vì đó là lúc `translation_cache` được nối vào.
3. `GeminiProvider` dùng `genai.configure()` global (đã tự nêu trong CHANGELOG) — chấp nhận được cho 1-user hiện tại, nhưng nên thêm 1 test riêng xác nhận không có race-condition rõ ràng nếu 2 job Gemini chạy đồng thời trong Job Orchestrator (increment sau, khi có `asyncio.Semaphore(3)` thật).
4. Cân nhắc migrate `google-generativeai` → `google-genai` sớm hơn increment sau, vì package đã ngừng nhận bugfix hoàn toàn (không chỉ deprecated), rủi ro breaking change nếu Google gỡ package khỏi PyPI.
5. `DeepLProvider.estimate_cost()` heuristic 4 ký tự/token chỉ là xấp xỉ hai lớp (ước lượng cost dựa trên token ước lượng từ ký tự) — đã ghi chú rõ, nhưng nên verify lại với hóa đơn DeepL thật sớm nhất có thể vì đây là provider duy nhất tính phí khác cơ chế token, sai số cộng dồn có thể lớn hơn các provider khác.

## Next step

Increment 3 (Translation Engine — Multi-Provider) **APPROVED** tại iteration 1/3. Circuit breaker Dev↔Reviewer: 0/3 vòng cho increment này (không cần vòng sửa). Sẵn sàng chuyển cho QA hoặc bắt đầu increment tiếp theo (Job Orchestrator).

---
---

# Increment 4 — Fix Round 1 Review (Architecture Correction)

- **increment_number**: 4 (fix round 1 — eliminate double-translation)
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-04
- **Bối cảnh**: Đây KHÔNG phải review thường. Increment 3 và Increment 4 gốc đã được
  Reviewer (tôi, phiên trước) APPROVE, nhưng sau đó phát hiện lỗi kiến trúc nghiêm trọng:
  `JobOrchestrator.run_job()` gọi CẢ `provider.translate()` (Increment 3) LẪN
  `pdf2zh_runner.translate_pages()` cho cùng một đoạn nội dung, trong khi pdf2zh TỰ gọi
  LLM API bên trong — nếu chạy thật sẽ tính phí 2 lần + tạo ra 2 bản dịch không nhất
  quán. Tech Lead đã research trực tiếp source code `Byaidu/PDFMathTranslate` và viết
  lại Architecture.md section 6.6 hoàn toàn (cộng 2.2, 3.1, 4.2, 5.2, 5.3, 6.1, 6.2, 6.7,
  8). Review này đối chiếu implementation với spec mới, nghiêm ngặt hơn review thường vì
  rủi ro đã hiện thực hoá một lần.

## Verdict: **APPROVE**

## 1. Đối chiếu implementation với Architecture.md 6.6 — từng file

| File | Spec (Architecture.md) | Code | Kết luận |
|---|---|---|---|
| `src/services/pdf2zh_service_map.py` | 6.6.3, 6.6.8 — bảng map 6 provider → `-s` + envs; `claude` → `openailiked:{model}` qua Anthropic compat layer (KHÔNG PHẢI `-s claude`); `deepl` luôn reject | `Pdf2zhServiceMapper.map()` — đúng từng dòng: `_build_claude` dùng `openailiked:{settings.claude_model}` + `OPENAILIKED_BASE_URL=https://api.anthropic.com/v1/`; `_build_deepl` luôn `raise UnsupportedForPdfPipelineError` với message giải thích rõ F7; 4 provider còn lại dùng `-s` native đúng bảng 6.6.3 | Khớp 100% |
| `src/services/pdf2zh_runner.py` | 6.6.1 F5/F9, 6.6.8 — `output_dir` (không phải `output_path`), `prompt_file: Path` (không phải string), `Pdf2zhResult.mono_path`/`dual_path`, `ignore_cache`, `timeout_seconds` | Signature khớp đúng dataclass `Pdf2zhResult` trong spec; `prompt_file` bị bỏ qua khi `supports_custom_prompt=False` (defense in depth, đúng 6.6.8 ghi chú); `timeout_seconds` dùng `asyncio.wait_for` + kill process khi timeout; env = `{**os.environ, **service.envs}`, API key KHÔNG bao giờ vào `args`/argv | Khớp, đã tự đọc code xác nhận argv không chứa key (xem mục 8) |
| `src/core/job_orchestrator.py` | 6.6.8 — 10 bước, KHÔNG còn `provider.translate()`, `service_mapper.map()` fail sớm ở bước 4, mỗi chunk 1 output dir riêng | Đọc trực tiếp `run_job()`: đúng thứ tự 10 bước, `provider` (constructor param) chỉ dùng làm `pricing_provider` truyền vào `estimate_chunk_cost()`, KHÔNG có lời gọi `.translate()` nào (xem mục 2) | Khớp |
| `src/core/glossary_manager.py` (`build_prompt_snippet`) | 6.6.5 — filter theo `only_terms_present_in` (word-boundary, case-insensitive), cap `max_entries` ưu tiên tần suất cao | Đúng: `_count_occurrences` dùng regex `\b{term}\b` IGNORECASE; filter trước (`frequencies[id] > 0`) rồi mới cap — thứ tự đúng nghĩa là filter theo tài liệu chạy TRƯỚC cap cứng, không phải ngược lại (xem mục 5 để phân tích edge case) | Khớp |
| `src/core/prompt_builder.py` (`write_prompt_file`) | 6.6.4 — file chứa `${lang_in}`/`${lang_out}`/`${text}` nguyên văn (không tự substitute), escape `$$` cho nội dung động, kết thúc bằng `Source Text: ${text}` | Đúng: `_escape_dollar` chỉ áp cho `glossary_block`/`unit_block` (nội dung động), KHÔNG áp cho các hằng số chứa token `${lang_in}` v.v. (nếu áp nhầm sẽ phá token); `_FILE_FOOTER = "Source Text: ${text}\nTranslated Text:"` đúng vị trí cuối; guard `ValueError` nếu thiếu `${text}` | Khớp |
| `src/core/cost_estimator.py` (`estimate_chunk_cost`) | 6.6.6 — công thức nhân `prompt_overhead_chars` với `segment_count` (không cộng 1 lần, vì F6: prompt lặp lại mỗi segment) | Đúng công thức từng dấu ngoặc so với pseudocode Architecture.md 6.6.6 | Khớp |
| `src/models/job.py` (`cost_source`) | 4.2 — `Job.cost_source: str = 'estimated' | 'metered'`, default `'estimated'` | Field có default, không có caller nào construct `Job(...)` dựa vào positional args cứng nhắc (xem mục 7) | Khớp |
| `src/core/config.py` | 6.6.8 config model — `pdf_pipeline.*` (max_glossary_entries_in_prompt=80, pdf2zh_ignore_cache, pdf2zh_timeout_seconds=3600, vi_expansion_factor=1.3, vi_token_factor=1.5, metering_proxy_enabled), `default_provider="deepseek"` | Tất cả field có mặt đúng tên, đúng default | Khớp |

Không phát hiện chỗ nào Dev tự diễn giải sai hoặc bỏ sót so với Architecture.md 6.6 khi
đọc trực tiếp cả hai phía (spec + code), không dựa vào tóm tắt CHANGELOG.

## 2. Verify KHÔNG còn double-translation

```
grep -rn "\.translate(" src/ | grep -v "translate_pages\|def translate"
```
→ chỉ ra 5 dòng, toàn bộ là **docstring/comment** (`job_orchestrator.py` dòng 13, 162,
343; `prompt_builder.py` dòng 7; `translation.py` dòng 3) — **không có lời gọi thực thi
nào**. Đọc trực tiếp `JobOrchestrator.run_job()`/`_process_chunk()`: biến
`pricing_provider` (từ `self._provider` hoặc `ProviderFactory.create()`) chỉ xuất hiện
đúng 1 lần, truyền vào `estimate_chunk_cost(..., provider=pricing_provider, ...)` ở bước
7c — đây là lời gọi `.estimate_cost()` thuần tính toán, đúng vai trò out-of-band R3, không
phải render. Lời gọi LLM duy nhất trên đường render là `self._pdf2zh_runner.translate_pages()`
trong `_call_pdf2zh()` (dòng 341-352), có comment ngay tại chỗ: "DAY LA LAN GOI LLM DUY
NHAT... Khong goi provider.translate()".

**Xác nhận: double-translation đã bị loại bỏ hoàn toàn.**

## 3. Verify DeepL bị chặn đúng cách

`test_run_job_with_deepl_fails_before_any_subprocess_call` (`tests/integration/test_job_orchestrator.py`):
- Tạo job PDF thật (5 trang) với `model="deepl"`
- `pdf2zh_runner` là `AsyncMock(spec=Pdf2zhRunner)` — mock thật, không phải stub rỗng
- Assert `result.status == "failed"`, `"DeepL" in result.error_message`, và quan trọng
  nhất: **`pdf2zh_runner.translate_pages.assert_not_awaited()`** — verify đúng thứ cần
  verify (không có subprocess call nào xảy ra), không phải test giả tạo cho pass
- `_FakePricingProvider` trong cùng file test **chỉ implement `.estimate_cost()`**,
  không có `.translate()` — nếu code có regression gọi lại `provider.translate()`, test sẽ
  crash với `AttributeError` ngay lập tức thay vì fail âm thầm

Tự chạy lại riêng:
```
uv run pytest tests/integration/test_job_orchestrator.py -v -k deepl
→ 2 passed (test trên + test_pdf2zh_service_mapper_rejects_deepl_directly, unit-level
  companion verify Pdf2zhServiceMapper tự nó cũng reject, độc lập với orchestration)
```
Test hợp lệ, verify đúng behavior cần verify.

## 4. Verify prompt file contract

`write_prompt_file()` (`src/core/prompt_builder.py`):
- Template dùng token literal `${lang_in}`/`${lang_out}`/`${text}` — KHÔNG tự
  `Template.substitute()`, để nguyên cho pdf2zh tự làm per-segment (đúng 6.6.4)
- `_FILE_FOOTER = "Source Text: ${text}\nTranslated Text:"` — kết thúc đúng bằng
  `Source Text: ${text}` như spec yêu cầu (6.6.4 điểm 1)
- `_escape_dollar()` áp dụng cho `glossary_block` và `unit_block` (nội dung ĐỘNG, có thể
  chứa `$` từ dữ liệu glossary như giá tiền) — KHÔNG áp cho các hằng số template chứa
  `${lang_in}` v.v., nếu áp nhầm sẽ phá chính token cần giữ nguyên. Đây là điểm dễ sai
  nhất trong toàn bộ increment này và Dev đã làm đúng.
- Test `test_write_prompt_file_escapes_stray_dollar_signs` verify bằng regex
  `(?<!\$)\$(?!\$)(?!\{)` — xác nhận không còn `$` đơn lẻ nào sót lại (ngoại trừ `${...}`
  hợp lệ), cách verify chặt hơn so với chỉ check `"$$5" in content`

Khớp đúng contract.

## 5. Verify glossary filtering

`GlossaryManager.build_prompt_snippet(only_terms_present_in, max_entries)`:
- Tự đọc lại logic: dòng 165-170 filter `ordered` xuống chỉ còn entry có
  `frequencies[entry.id] > 0` **TRƯỚC KHI** áp `max_entries` — đúng thứ tự cần thiết.
- Đã tự nghĩ edge case theo yêu cầu review: glossary 200 entry, chỉ 5 term xuất hiện
  trong đoạn text ngắn → sau bước filter, `ordered` chỉ còn 5 phần tử → điều kiện
  `len(ordered) > max_entries` (80) là `5 > 80` = `False` → **không cap thêm, kết quả
  đúng 5 entry**, không bị ép lên/xuống 80. Xác nhận bằng test
  `test_build_prompt_snippet_filters_to_terms_present_in_document` và
  `test_build_prompt_snippet_caps_at_max_entries_by_frequency` (2 test riêng biệt, đúng 2
  nhánh logic).
- Word-boundary regex (`\b{term}\b`) tránh false-positive substring — có test riêng
  `test_build_prompt_snippet_word_boundary_not_substring`.

Logic đúng, edge case xử lý đúng.

## 6. Verify chunking output dir

`job_orchestrator.py` dòng 339: `chunk_output_dir = self._processing_dir / job.id /
f"chunk_{chunk.chunk_index}"` — mỗi chunk có thư mục riêng biệt trước khi gọi
`pdf2zh_runner.translate_pages(output_dir=chunk_output_dir, ...)`. `Pdf2zhRunner` tự
`mkdir(parents=True, exist_ok=True)` thư mục này. Không còn khả năng ghi đè giữa các
chunk (F9 đã được xử lý đúng ở cả 2 lớp: Job Orchestrator tạo dir riêng + Runner tạo
thư mục nếu chưa có).

## 7. Breaking schema change (`cost_source`)

`Job.cost_source: str = Field(default="estimated")` — có default, additive-only. Grep
`Job(` trong toàn repo (`src/` + `tests/`) chỉ thấy class definition + 3 chỗ test tạo
`Job(...)` bằng keyword argument (không dùng positional args), không có nơi nào constructor
bị phá vỡ bởi field mới. "BREAKING" trong CHANGELOG đúng nghĩa "cần xoá tạo lại DB dev"
(SQLite dev chưa có Alembic migration, chấp nhận được vì DB dev "chưa có data thật quan
trọng" — task brief cho phép), không phải "breaking code call site". Hợp lý.

## 8. Tự chạy lại toàn bộ, không tin số liệu Dev báo cáo

```
uv run ruff check src/                                  → All checks passed!
uv run pytest tests/ -v                                 → 108 passed, 138 warnings
uv run pytest tests/integration/test_job_orchestrator.py -v -k deepl  → 2 passed
python -c "from src.api.main import app"                → không lỗi
```
Số liệu khớp đúng CHANGELOG (108 passed). Warning duy nhất đáng chú ý là
`google.generativeai` FutureWarning deprecated — đã biết từ Increment 3, không blocking,
không liên quan tới fix round này.

## 9. Đánh giá deviation Dev tự quyết: không inject `GlossaryManager`/`cost_estimator`/`prompt_builder` qua constructor

CHANGELOG: Dev giữ nguyên pattern cũ — `GlossaryManager(db_session)` tạo mới bên trong
`run_job()` thay vì inject qua `__init__`; `cost_estimator`/`prompt_builder` gọi trực
tiếp như pure function, không qua DI.

**Đánh giá: hợp lý, chấp nhận được.**
- `GlossaryManager` cần `AsyncSession` — session chỉ tồn tại tại thời điểm gọi
  `run_job(job_id, db_session)`, không thể có tại thời điểm `JobOrchestrator.__init__()`
  (constructor chạy 1 lần khi orchestrator được tạo, session là per-call). Inject qua
  constructor sẽ ép phải tạo `JobOrchestrator` mới cho mỗi job — vô lý vì các dependency
  khác (`pdf2zh_runner`, `service_mapper`, `mineru_runner`, `provider_factory`) đều
  stateless/long-lived và đã được inject đúng cách qua constructor.
- `cost_estimator.estimate_chunk_cost()` và `prompt_builder.write_prompt_file()` là pure
  function (không có I/O ngoài cần mock độc lập — I/O duy nhất là ghi file prompt, không
  cần fake riêng vì test dùng `tmp_path` thật), không khác gì `font_shrink_page()` hay
  `merge_chunk_pdfs()` đã có sẵn trong cùng module và cũng được gọi trực tiếp không qua
  DI. Áp DI cho các hàm này sẽ không mang lại lợi ích testability nào (không cần mock
  chúng để test `JobOrchestrator` — test hiện tại vẫn chạy logic thật của chúng qua
  `tmp_path`/PyMuPDF thật) mà chỉ thêm boilerplate.
- Pseudocode Architecture.md 6.6.8 liệt kê các tham số này trong constructor signature,
  nhưng đó là gợi ý cấp cao, không phải hợp đồng bắt buộc — bản chất kiến trúc quan trọng
  (loại bỏ `translation_provider` khỏi render path, R1) đã được tuân thủ đúng. Deviation
  này không ảnh hưởng tới đúng-sai của fix chính.

Không có vấn đề gì cần Dev sửa lại ở điểm này.

## Blocking issues

**Không có.**

## Non-blocking suggestions

1. `Pdf2zhServiceMapper._KNOWN_PROVIDERS` hard-code danh sách 6 provider song song với
   `ProviderFactory` — đúng như Architecture.md 6.6.8 ghi nhận ("2 registry song song,
   thêm provider mới phải sửa cả hai"), nhưng nên cân nhắc 1 test cấp integration ở
   increment sau đảm bảo 2 danh sách provider luôn đồng bộ (vd so `Pdf2zhServiceMapper._KNOWN_PROVIDERS`
   với danh sách provider của `ProviderFactory`), tránh trường hợp thêm provider mới ở 1
   registry mà quên registry kia.
2. `_count_text_segments()` (ước lượng segment count cho cost estimate) dùng PyMuPDF text
   block count làm proxy — đã ghi rõ là xấp xỉ trong docstring, chấp nhận được cho v1.0,
   nhưng nên revisit khi có dữ liệu job thật để biết sai số bao xa so với segment thật
   của pdf2zh.
3. Cân nhắc thêm 1 dòng cảnh báo UI/log khi `cost_source == "estimated"` VÀ job có
   `pdf2zh_ignore_cache == False` mà chạy lại (rerun) — theo Architecture.md 6.6.6, cache
   hit sẽ làm cost thực tế thấp hơn nhiều so với ước lượng hiển thị, dễ gây hiểu lầm nếu
   user rerun nhiều lần. Không blocking vì đã ghi trong Architecture.md là "ghi rõ trong
   tooltip UI" — chưa có UI ở increment này.

## Next step

Increment 4 — Fix Round 1 (Architecture correction) **APPROVED**. Circuit breaker
Dev↔Reviewer: 1 vòng cho fix round này (0/3 — không cần sửa lại). Double-translation bug
đã được xác nhận loại bỏ hoàn toàn qua đọc code trực tiếp + grep xác nhận không còn lời
gọi `.translate()` nào trên đường render + test `assert_not_awaited()` cho nhánh DeepL.
Sẵn sàng cho QA hoặc increment tiếp theo.

## Increment 5 — Iteration 1

- **increment_number**: 5
- **iteration**: 1/3
- **Reviewer**: Reviewer (Sonnet)
- **Verdict**: **REJECT** (1 blocking issue — path traversal trong `POST /api/upload`)

### Bối cảnh

Review API layer (upload/jobs/batches/download/settings) + WebSocket progress +
frontend Alpine.js lắp lên trên `JobOrchestrator`/`BatchOrchestrator` (Increment 4).
PM đã tự test tay 2 phát hiện trước khi giao — cả hai đã được xác minh lại độc lập bằng
cách đọc code trực tiếp (không chỉ tin theo mô tả), kết quả bên dưới. Ngoài ra, review tự
phát hiện thêm 1 lỗi bảo mật nghiêm trọng không nằm trong 2 phát hiện PM đưa ra.

### Phát hiện 1 (PM) — US-15 parse_only: XÁC NHẬN đúng như PM mô tả, KHÔNG blocking

Đọc `src/api/routes/jobs.py` (`_mark_parse_only_unsupported()`, dòng 241-256) và
`docs/PRD.md` US-15 (dòng 148-151, 207, 355):

- `POST /api/jobs`/`POST /api/batches` với `job_type=parse_only` tạo `Job` row rồi đánh
  dấu `status="failed"` NGAY LẬP TỨC (đồng bộ, trong cùng request) với
  `error_message` giải thích rõ ràng bằng tiếng Việt không dấu: "job_type=parse_only chua
  duoc JobOrchestrator ho tro..." — không phải silent fail, không phải crash 500, không
  treo ở `status=created` vô thời hạn.
- PRD US-15 đã có mục "Known limitation (v1.0)" mô tả đúng y hệt hành vi thật của code
  (dòng 151: "mọi job `parse_only` hiện tại fail ngay với thông báo rõ ràng, không giả vờ
  thành công"), và mục "Chưa làm" trong CHANGELOG Increment 5 cũng ghi lại đúng. Tài liệu
  và code nhất quán — đây là known limitation đã được document, không phải bug ẩn.
- `tests/integration/test_upload_and_job_flow.py` có test end-to-end cho path này (upload
  → tạo job `parse_only` → verify status). Verify thủ công của Dev trong CHANGELOG (dòng
  924-926) khớp với hành vi đọc được từ code.

**Kết luận**: đúng như PM mô tả, không cần Dev làm gì thêm ở vòng này.

### Phát hiện 2 (PM) — `excel_utils.py` dùng `workbook.active`: XÁC NHẬN là bug thật, CẦN FIX

Đọc `src/utils/excel_utils.py` dòng 22-24:

```python
def import_glossary_from_excel(file_path: Path) -> list[GlossaryEntryData]:
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    sheet = workbook.active
```

Đây là bug thật, không phải "chấp nhận được vì PRD không yêu cầu multi-sheet":
- BR-GLOSS-05 (đọc trong PRD) chỉ đặc tả FORMAT của 1 sheet dữ liệu (cột A=EN, B=VI,
  C=notes) — không cấm/không loại trừ file Excel có nhiều sheet. `workbook.active` phụ
  thuộc vào sheet nào được **lưu lần cuối** là active trong file Excel (thuộc tính
  `tabSelected`/`activeTab` trong XML), một thuộc tính hoàn toàn ngẫu nhiên với người
  dùng cuối — họ không biết và không kiểm soát được nó khi tạo/sửa file bằng Excel/Google
  Sheets thông thường.
- Hậu quả thực tế đã tái hiện được: `data/glossary-starter.xlsx` (chính file mẫu do dự án
  cung cấp cho user, có sheet "Hướng dẫn" đặt trước sheet "Glossary") fail với lỗi "Thieu
  cot bat buoc" — trong khi file hoàn toàn hợp lệ theo BR-GLOSS-05. Đây là false negative
  ngay trên chính use case chuẩn của sản phẩm (user import file mẫu chính chủ), không
  phải edge case hiếm.
- Không có test nào trong `tests/test_excel_utils.py` cover trường hợp multi-sheet — 4
  test hiện có (`test_excel_utils.py`) đều dùng workbook 1-sheet tự tạo trong test, nên
  gap này không bị bắt bởi test suite.

**Đề xuất fix** (đồng ý với hướng PM gợi ý): sửa `import_glossary_from_excel()` ưu tiên
tìm sheet tên `"Glossary"` (case-insensitive, so khớp `sheet.title.strip().lower() ==
"glossary"`) trong `workbook.sheetnames`; nếu không tìm thấy, fallback về `workbook.active`
(giữ nguyên tương thích ngược 100% cho file 1-sheet đơn giản, không có sheet nào tên
"Glossary" rõ ràng). Thêm ít nhất 1 test mới trong `tests/test_excel_utils.py`: workbook 2
sheet ("Hướng dẫn" active + "Glossary" chứa data) → import phải đọc đúng từ sheet
"Glossary" bất kể sheet nào đang active.

**Đây là BLOCKING issue** — liệt kê ở mục "Blocking issues" bên dưới cho vòng fix tiếp
theo. Không tự sửa (đúng vai trò Reviewer, việc của Dev).

### Phát hiện 3 (Reviewer, ngoài phạm vi PM đưa ra) — Path traversal nghiêm trọng trong `POST /api/upload`

`src/api/routes/upload.py` dòng 83: `dest_path = _UPLOAD_DIR / f"{file_id}_{file.filename}"`
— `file.filename` là tên file client tự khai trong multipart request (hoàn toàn do
client kiểm soát, FastAPI/Starlette KHÔNG sanitize giá trị này), chỉ được validate phần
**suffix** (dòng 74-76: `.pdf`/`.epub`), không hề validate các ký tự `/`/`..` bên trong.

Verify bằng cách chạy thử logic ghép path thật (không phải suy đoán):

```
>>> from pathlib import Path
>>> Path("data/uploads") / "abc123_../../../../tmp/evil.pdf"
PosixPath('data/uploads/abc123_../../../../tmp/evil.pdf')
>>> import os
>>> os.path.normpath("data/uploads/abc123_../../../../tmp/evil.pdf")
'tmp/evil.pdf'
```

Vì `dest_path.open("wb")` (dòng 88) mở file bằng path chưa normalize/chưa validate, hệ
điều hành tự resolve các `..` trong path khi mở file — kết quả: client upload 1 file với
`filename="../../../../../../etc/cron.d/evil.pdf"` (hoặc bất kỳ path nào khác) sẽ khiến
server **ghi file ra ngoài `data/uploads/`, tới bất kỳ vị trí nào process có quyền ghi**
— chỉ cần đuôi file kết thúc bằng `.pdf`/`.epub` để qua được check extension (đuôi file
không nằm ở đầu path nên không bị chặn). Đây là **path traversal / arbitrary file write**
(CWE-22), mức độ nghiêm trọng cao dù app hiện tại chạy local 1-user (Architecture.md 9.1
không loại trừ nguy cơ này — 1-user vẫn có thể bị tấn công qua 1 trang web độc hại khiến
browser gửi request tới `localhost` nếu CORS không chặn kỹ, hoặc đơn giản là 1 client
tool/script vô tình gửi filename có `..`).

Không có test nào trong `tests/integration/test_upload_and_job_flow.py` cover trường hợp
filename chứa `/` hoặc `..`.

**Đề xuất fix**: sanitize `file.filename` trước khi ghép vào `dest_path` — lấy
`Path(file.filename).name` (chỉ giữ basename cuối cùng, loại bỏ mọi thư mục cha/`..`)
thay vì dùng `file.filename` nguyên văn, ví dụ:
```python
safe_name = Path(file.filename).name
dest_path = _UPLOAD_DIR / f"{file_id}_{safe_name}"
```
Sau khi sửa, nên thêm assert `dest_path.resolve().is_relative_to(_UPLOAD_DIR.resolve())`
(defense in depth) và 1 test mới verify filename có `../` bị vô hiệu hoá (file vẫn được
lưu, nhưng luôn nằm trong `data/uploads/`, không traversal ra ngoài).

**Đây là BLOCKING issue.**

### Checklist còn lại (API design, background task, WebSocket, DB settings, frontend, batch ẩn)

1. **API endpoints đúng thiết kế**: đối chiếu `src/api/routes/{upload,jobs,download,settings}.py`
   với Architecture.md section 5 và PRD AC liên quan — khớp. `POST /api/jobs` trả 202 +
   `job_id`/`status`, `GET /api/jobs`/`GET /api/jobs/{id}` đúng shape, `POST
   /api/jobs/{id}/retry` chặn đúng (chỉ cho `status=failed`, chặn `parse_only`),
   `GET /api/jobs/{id}/cost-estimate` chặn đúng EPUB + job thiếu `total_pages`.
2. **DeepL+PDF reject sớm ở API layer**: xác nhận `_reject_deepl_for_pdf()` (dòng 154-167)
   gọi TRƯỚC khi tạo `Job` row (cả đường đơn `create_job` dòng 272 lẫn đường batch
   `create_batch` dòng 412, đều gọi trước `_resolve_batch`/vòng lặp tạo `Job`), dùng lại
   `Pdf2zhServiceMapper.map()` — đúng yêu cầu, không duplicate logic. Test
   `test_upload_and_job_flow.py` verify `GET /api/jobs` `total=0` sau reject — đã đọc
   test, khớp mô tả.
3. **Background task = `asyncio.create_task()`**: giữ reference trong module-level
   `_background_tasks: set[asyncio.Task]` + `add_done_callback` để discard đúng cách —
   xử lý đúng bug kinh điển "task bị GC giữa chừng". Rủi ro "không có supervision nếu
   server restart" (job đang chạy mất, không resume tự động khi khởi động lại) là thật,
   nhưng chấp nhận được cho app 1-user local hiện tại — không có persistent queue theo
   đúng Architecture.md 9.1, và `BR-CHUNK-05` (resumable qua `POST /retry`) vẫn cho phép
   user tự resume thủ công sau khi server crash mất giữa chừng. Không blocking.
4. **`ConnectionManager`** (`src/api/websocket.py`): đọc code — broadcast đúng theo
   `job_id` (dict theo key), không leak connection giữa các job (`disconnect()` chỉ xoá
   đúng socket khỏi đúng `job_id`, xoá key rỗng khỏi dict). `pytest
   tests/test_websocket_connection_manager.py -v`: **6/6 passed**.
5. **DB settings override `.env`** (`get_effective_settings()`, `src/core/config.py` dòng
   117-139): đọc code xác nhận — không cache, tạo `Settings(**data)` mới mỗi lần gọi,
   `_cast_setting_value()` xử lý đúng thứ tự `bool` trước `int` (tránh bug `isinstance`
   quen thuộc vì `bool` là subclass của `int`). Verify riêng bằng cách đọc code (không chỉ
   tin CHANGELOG) `src/api/routes/settings.py` dòng 51-56: `_build_response()` chỉ trả
   `ProviderStatus(has_key=bool(getattr(settings, field)))` — KHÔNG có đường nào trả giá
   trị API key thật ra response. Xác nhận an toàn.
6. **Frontend** (`web/*.html`, `web/js/*.js`): `grep -rn "x-html\|innerHTML\|v-html"` trên
   toàn bộ `web/` — không có kết quả, không dùng `x-html`/`innerHTML` ở đâu cả nên không
   có XSS risk rõ ràng qua route này. Code style hợp lý, tách file theo trang
   (`app.js`/`glossary.js`/`history.js`), có polling fallback khi WS lỗi. 1 điểm nhỏ
   không blocking: `trackJob()` (`web/js/app.js` dòng 145-181) luôn gọi `poll()` ngay sau
   khi mở WebSocket (dòng 180, chạy vô điều kiện, không nằm trong `ws.onerror`) — nghĩa là
   polling 3s luôn chạy song song với WebSocket kể cả khi socket kết nối thành công, không
   thực sự là "fallback chỉ khi lỗi" như mô tả trong CHANGELOG. Không sai chức năng (WS +
   polling đều cùng cập nhật state, không xung đột), chỉ dư request không cần thiết —
   để non-blocking suggestion bên dưới.
7. **Batch ẩn cho job đơn lẻ**: đọc `_resolve_batch()` (dòng 170-203) — thiết kế hợp lý,
   không phải workaround che giấu vấn đề: tái sử dụng đúng khái niệm `Batch` đã có sẵn
   trong schema (Architecture.md 4.2) thay vì thêm field mới trùng lặp lên `Job`, và có
   xử lý đúng trường hợp `glossary_project_id` được cung cấp (attach vào batch đã tồn tại,
   404 nếu không tìm thấy) thay vì luôn tạo mới. Nhất quán với cách `JobOrchestrator` đọc
   `output_mode`/glossary scope từ `Batch` (Increment 4, không đổi ở increment này).
8. **Chạy lại toàn bộ**:
   - `uv run ruff check src/`: **All checks passed**.
   - `uv run pytest tests/ -v`: **121 passed** (đúng số Dev báo cáo).
   - `python -c "from src.api.main import app"`: import thành công, không lỗi.

### Blocking issues

1. **`src/utils/excel_utils.py` — `import_glossary_from_excel()` dùng `workbook.active`
   không có fallback tìm sheet tên "Glossary"** (Phát hiện 2). File Excel nhiều sheet với
   sheet dữ liệu không phải sheet active (như chính `data/glossary-starter.xlsx`) sẽ fail
   import với lỗi gây hiểu lầm ("Thieu cot bat buoc") dù file hợp lệ. Fix: ưu tiên tìm
   sheet tên "Glossary" (case-insensitive) trong `workbook.sheetnames`, fallback
   `workbook.active` nếu không có. Thêm test multi-sheet mới.
2. **`src/api/routes/upload.py` dòng 83 — path traversal qua `file.filename` chưa
   sanitize** (Phát hiện 3, CWE-22). `dest_path = _UPLOAD_DIR / f"{file_id}_{file.filename}"`
   dùng thẳng filename client gửi mà không lấy basename — filename chứa `../` cho phép ghi
   file ra ngoài `data/uploads/`. Fix: `safe_name = Path(file.filename).name` trước khi
   ghép path; thêm test verify.

### Non-blocking suggestions

1. `web/js/app.js` `trackJob()` — polling 3s chạy song song vô điều kiện với WebSocket
   thay vì chỉ khi `ws.onerror`, gây dư request không cần thiết khi WS hoạt động tốt.
   Không sai chức năng, cân nhắc sửa ở increment sau nếu muốn giảm tải server.
2. `PUT /api/settings` (`src/api/routes/settings.py`) không validate `default_provider`
   khớp danh sách provider hợp lệ (`ALL_PROVIDERS` phía frontend) trước khi ghi DB — 1
   giá trị sai chính tả sẽ chỉ lộ ra sau, khi `ProviderFactory.create()` raise
   `UnknownProviderError` ở bước tạo job/cost-estimate. Cân nhắc validate ngay tại
   `PUT /api/settings` để fail sớm hơn, thông báo rõ hơn cho user.

## Next step

Increment 5 — Iteration 1 **REJECTED**, 2 blocking issue (path traversal trong upload +
excel_utils.py multi-sheet). Circuit breaker Dev↔Reviewer: **1/3** cho increment này. Dev
cần sửa cả 2 blocking issue, chạy lại `ruff check` + `pytest tests/ -v` (kỳ vọng vẫn pass
hết + thêm ít nhất 2 test mới cho 2 fix), rồi gửi lại Reviewer vòng 2.

---
---

## Increment 5 — Iteration 2 (Fix Round 1 Verify)

- **increment_number**: 5
- **iteration**: 2/3
- **Reviewer**: Reviewer (Sonnet)
- **Verdict**: **APPROVE**

### Bối cảnh đặc biệt

Đây không phải verify thông thường: agent Dev fix bị user interrupt (kill) giữa chừng,
TRƯỚC bước verify cuối bằng curl. PM tự đọc code, tự chạy verify sống, và tự viết mục
CHANGELOG "Fix Round 1" thay Dev. Vì mục CHANGELOG này không phải Dev tự báo cáo, review
vòng này được thực hiện độc lập kỹ hơn bình thường: tự đọc lại toàn bộ code (không tin mô
tả CHANGELOG), tự chạy lại test có sẵn, và tự tạo case verify KHÁC với case PM đã dùng cho
cả 2 fix.

### 1. Path Traversal fix (`src/api/routes/upload.py`) — XÁC NHẬN ĐÚNG

Đọc trực tiếp `src/api/routes/upload.py` dòng 83-89:

```python
safe_name = Path(file.filename).name
dest_path = _UPLOAD_DIR / f"{file_id}_{safe_name}"
if not dest_path.resolve().is_relative_to(_UPLOAD_DIR.resolve()):
    raise HTTPException(status_code=400, detail="Ten file khong hop le")
```

- `Path(file.filename).name` được áp dụng **đúng chỗ**: trước khi ghép `dest_path`, không
  phải sau — đúng thứ tự bắt buộc để fix có tác dụng (nếu ghép trước rồi mới `.name` thì vô
  nghĩa).
- Có check `is_relative_to()` defense-in-depth ngay sau đó, đúng như đề xuất ở Iteration 1.
- Comment tại chỗ (dòng 83-85) giải thích đúng CWE-22 và lý do fix, không phải comment thừa.
- Grep `\.filename` toàn `src/`: `jobs.py` (dòng 135, 280, 423) và `download.py` (dòng 44)
  chỉ dùng `upload.filename`/`job.filename` làm **giá trị hiển thị** (`Job.filename` field,
  `Content-Disposition` filename của `FileResponse`) — KHÔNG dùng để ghép path ghi/đọc file
  trên đĩa; path thật (`file_path`) luôn lấy từ `upload.file_path` (đã được sanitize sẵn ở
  upload.py). `glossary.py` dòng 83 chỉ check đuôi file, path ghi file dùng
  `tempfile.NamedTemporaryFile(suffix=".xlsx")` (tên file do OS sinh ngẫu nhiên, không liên
  quan tới `file.filename` client gửi) — an toàn, không cần sanitize thêm. **Xác nhận
  `upload.py` là chỗ DUY NHẤT cần fix, và Dev không bỏ sót chỗ nào khác.**

Test có sẵn:
```
pytest tests/integration/test_upload_and_job_flow.py::test_upload_sanitizes_path_traversal_filename -v
→ 1 passed
```

**Tự verify sống độc lập (2 biến thể KHÁC PM đã dùng — PM dùng
`../../../../../../tmp/pwned.pdf`)**: khởi động uvicorn thật (`uv run uvicorn
src.api.main:app --port 8123`), gửi 2 request curl multipart khác:

| Biến thể | Request | Kết quả |
|---|---|---|
| Absolute path filename | `filename=/tmp/absolute_evil_test.pdf` | HTTP 200, `file_id_absolute_evil_test.pdf` lưu đúng trong `data/uploads/`; `/tmp/absolute_evil_test.pdf` **không được tạo** (`ls` xác nhận "No such file or directory") |
| URL-encoded traversal (literal, không decode) | `filename=..%2f..%2f..%2ftmp%2fetc_passwd_test.pdf` | HTTP 200, lưu với tên chứa nguyên văn `..%2f...` (Starlette không tự URL-decode filename multipart, và ngay cả nếu bị coi là 1 basename lạ thì cũng không tách được thư mục) trong `data/uploads/`; `/tmp/etc_passwd_test.pdf` **không được tạo** |

Cả 2 biến thể đều bị chặn triệt để, không chỉ chặn đúng 1 pattern cụ thể (`../`) mà chặn cả
absolute path (vì `Path(...).name` lấy basename bất kể input là relative hay absolute) và
input không chứa ký tự `/` thật (URL-encoded literal). Dọn dẹp file test tạm sau khi verify
xong (`data/uploads/{2 file_id mới}*`, `/tmp/minimal.pdf`, `/tmp/absolute_evil_test.pdf`,
`/tmp/etc_passwd_test.pdf`).

**Kết luận: Fix #1 đúng, đầy đủ, defense-in-depth hợp lý, không sót chỗ nào khác trong
codebase.**

### 2. Excel multi-sheet fix (`src/utils/excel_utils.py`) — XÁC NHẬN ĐÚNG

Đọc `_select_data_sheet()` (dòng 23-31):
```python
def _select_data_sheet(workbook: Workbook) -> Worksheet:
    for name in workbook.sheetnames:
        if name.strip().lower() == "glossary":
            return workbook[name]
    return workbook.active
```
Đúng logic: case-insensitive match tên "Glossary" (dùng `.strip().lower()`, không chỉ
`.lower()` — xử lý luôn cả trường hợp tên sheet có khoảng trắng thừa), fallback `active`
nếu không tìm thấy — giữ tương thích ngược cho file 1-sheet đơn giản.

Test có sẵn:
```
pytest tests/test_excel_utils.py -v
→ 5 passed (gồm test_import_finds_glossary_sheet_when_not_active)
```

**Tự verify sống độc lập với file Excel khác** (PM dùng active="Notes" trỏ sai + data ở
sheet "Glossary" viết hoa-thường chuẩn): tự tạo workbook 3 sheet — `Intro` (active, sheet
đầu tiên), `Notes` (sheet giữa, không phải data), `GLOSSARY` (viết HOA hoàn toàn, sheet
CUỐI, chứa data thật: `Butter/Bo/Test entry`, `sugar/duong/None`). Gọi trực tiếp
`import_glossary_from_excel()`:
```
GlossaryEntryData(term_en='Butter', term_vi='Bo', notes='Test entry')
GlossaryEntryData(term_en='sugar', term_vi='duong', notes=None)
```
Đọc đúng 2 entry từ sheet `GLOSSARY` dù active sheet trỏ vào `Intro` và tên sheet viết hoa
hết — xác nhận case-insensitive match hoạt động đúng với biến thể case khác (không chỉ
đúng với case Title-case "Glossary" mà PM đã test).

**Kết luận: Fix #2 đúng, case-insensitive match hoạt động chính xác với mọi biến thể case,
không phụ thuộc vị trí sheet hay active sheet.**

### 3. Regression check toàn diện

```
uv run ruff check src/                              → All checks passed!
uv run pytest tests/ -v                              → 123 passed, 146 warnings
```
- Đúng 123 passed như CHANGENLOG báo cáo (121 cũ + 2 test mới:
  `test_upload_sanitizes_path_traversal_filename`,
  `test_import_finds_glossary_sheet_when_not_active`).
- Grep output pytest cho "skip"/"xfail": chỉ khớp tên test có chữ "skip" trong tên
  (`test_import_skips_empty_rows...`, `test_evaluate_span_skips_blank_text`,
  `test_write_prompt_file_skips_unit_conversion...`) — đây là tên test bình thường, KHÔNG
  phải test bị đánh dấu `@pytest.mark.skip`/`xfail`. Không có test nào bị ẩn/skip thật.
- `uv run python -c "from src.api.main import app"` → `app OK`, không lỗi.

**Đối chiếu CHANGENLOG "Fix Round 1" với code thật**: từng câu mô tả (vị trí sanitize,
defense-in-depth `is_relative_to`, `_select_data_sheet()` ưu tiên tên "Glossary" rồi
fallback active, `export_glossary_to_excel()` không cần sửa vì luôn 1-sheet mới tạo, số
lượng test 123 = 121+2) đều khớp chính xác với code đọc được — **không có mô tả nào sai
hoặc phóng đại**.

### 4. Kiểm tra không có regression ở chỗ khác

- `grep -rn "\.filename" src/`: đã liệt kê & phân tích đầy đủ ở mục 1 — không có chỗ nào
  khác cần sanitize (tất cả chỉ dùng filename gốc làm giá trị hiển thị, không ghép path).
- `grep -rn "workbook.active\|\.active\b" src/`: chỉ còn 2 chỗ trong `excel_utils.py`
  (`_select_data_sheet()` dòng 31 — fallback hợp lệ; `export_glossary_to_excel()` dòng 75 —
  đúng như CHANGELOG giải thích, hàm này luôn tạo `Workbook()` mới nên `.active` chính là
  sheet vừa tạo, không có ambiguity, không cần sửa). Không sót chỗ nào khác dùng
  `workbook.active` mà cần áp fix tương tự.

### Blocking issues

**Không có.**

### Next step

Increment 5 — Fix Round 1 **APPROVED** tại iteration 2/3. Cả 2 blocking issue từ iteration
1 đã được fix đúng, đầy đủ, verify độc lập bằng test case khác với PM đã dùng (absolute
path + URL-encoded filename cho path traversal; sheet "GLOSSARY" viết hoa hết + active
trỏ sheet đầu cho Excel) đều cho kết quả đúng như kỳ vọng. 123/123 test pass, ruff sạch,
không regression ở chỗ khác trong codebase. Circuit breaker Dev↔Reviewer: đóng ở **2/3**

---

## MinerU Rewrite — Protocol 5 Review

**Ngày**: 2026-09-04. **Phạm vi**: `src/services/mineru_runner.py` viết lại hoàn toàn theo
Architecture.md 6.9 (contract MinerU thật, thay cho contract sai của Increment 2 — sự cố gốc
sinh ra Protocol 5, xem CLAUDE.md Protocol 5 mục 2).

### R5-04 — Checklist bắt buộc

**External contract verified against real source: YES.**

Nguồn:
1. **Architecture.md 6.9.1 (S1–S9)** — Tech Lead trích dẫn trực tiếp source code MinerU thật
   (`mineru/cli/fast_api.py`, `mineru/cli/api_request.py`,
   `mineru/backend/pipeline/model_json_to_middle_json.py`, `mineru/utils/ocr_utils.py`,
   `mineru/backend/pipeline/pipeline_analyze.py`, docs chính thức, `docker/compose.yaml`,
   Docker Hub API) — không có contract cụ thể nào trong 6.9 thiếu trích dẫn nguồn hay bị bỏ
   sót đánh dấu `⚠️ ASSUMED`. Đúng tinh thần R5-01.
2. **Live verification của PM + Dev** (ghi trong CHANGELOG.md mục "MinerU Rewrite (Protocol 5
   fix)" → "Live verification (Protocol 5 R5-02 + R5-03)") — PM verify `/health` qua
   `MinerURunner.health()` thật, Dev verify full round-trip `parse_document()` thật (task_id
   `3372d38a-...`, confidence=0.986). Cả 2 đều qua chính class `MinerURunner`, không chỉ curl
   thủ công — đúng yêu cầu của prompt review này.
3. **Reviewer tự tái hiện live test độc lập lúc review** (không chỉ tin lời kể):
   - `curl http://127.0.0.1:8010/health` → server MinerU thật vẫn đang chạy (`mineru-api`,
     version 3.4.5, `completed_tasks: 3` — tăng dần đúng với 2 lần PM/Dev đã chạy trước đó).
   - Tự viết script độc lập (`/private/tmp/.../scratchpad/live_test.py`), tạo 1 PDF 1 trang
     mới bằng `pymupdf`, gọi thẳng `MinerURunner("http://127.0.0.1:8010")` — **không mock** —
     qua `.venv/bin/python` của project. Kết quả: `task_id` MỚI
     (`59b089dd-1ac9-4239-9fb2-2a1a7d446a8b`, khác cả 2 task_id PM/Dev đã dùng),
     `markdown_path` tồn tại, nội dung đúng text đã insert, `quality=OcrQuality(
     confidence=0.999, ocr_span_count=1, dropped_span_count=0,
     source='middle_json_span_scores')`. Xác nhận submit → poll → fetch result → decode
     `middle_json` string → tính confidence theo span score hoạt động đúng với MinerU thật,
     độc lập với báo cáo của PM/Dev.

Kết luận R5-04: **YES, verified against real source — 3 lớp độc lập (trích dẫn source code +
PM run + Dev run + Reviewer tự run lại lúc review)**. Đây là mức bằng chứng cao hơn hẳn mức
tối thiểu Protocol 5 R5-03 yêu cầu.

### Đối chiếu code với Architecture.md 6.9 (đọc trực tiếp `mineru_runner.py`)

| Spec 6.9 | Code | Kết quả |
|---|---|---|
| 6.9.3 async flow `/tasks` → poll → `/tasks/{id}/result`, không dùng `/file_parse` | `parse_document()` gọi đúng `_submit_task` → `_poll_until_done` → `_fetch_result`; không còn bất kỳ tham chiếu nào tới `/ocr` hay `/file_parse` (grep xác nhận) | Đúng |
| 6.9.6 bước 2: `files` số nhiều, `backend=pipeline`, `lang_list`, cờ `return_*` | `_submit_task()` dùng đúng field `files` (multipart), `data["backend"] = self._backend` (default `"pipeline"`), `lang_list=lang`, `return_md/return_images/return_middle_json="true"`, `return_content_list/return_model_output/response_format_zip="false"` | Đúng, khớp từng field |
| 6.9.6 bước 3: poll 2s→x1.5→cap 15s, timeout, 404→lost, failed→error | `_poll_until_done()`: `interval = min(interval*1.5, poll_max_seconds)`, `elapsed >= task_timeout_seconds` → `MinerUTimeoutError`, `404` → `MinerUError("...lost...")`, `status=="failed"` → `MinerUError(payload["error"])` | Đúng |
| 6.9.6 bước 4: `/result` 202→race retry, 409→error | `_fetch_result()` xử lý đúng cả 3 status (200/202 đệ quy gọi lại poll/fetch/409) | Đúng |
| 6.9.6 bước 5: `_select_result_entry()` ưu tiên tên file thật, fallback 1-phần-tử, không hardcode key | `_select_result_entry()` đúng thứ tự: khớp tên → nếu `len(results)==1` lấy phần tử đó → ngược lại `MinerUError` liệt kê key thật (`sorted(results.keys())`) | Đúng, không hardcode |
| 6.9.6 bước 6: `md_content` là field bắt buộc duy nhất | `_write_markdown()` raise nếu rỗng/None, field khác không bắt buộc | Đúng |
| 6.9.6 bước 7: `images` dict base64 data-URI, tách sau dấu phẩy, `base64.b64decode()`, `Path(name).name` chống path traversal, entry dị dạng → log warning bỏ qua không hỏng job | `_write_images()` check `data_uri.startswith("data:")` + `"," in data_uri`, `partition(",")`, `base64.b64decode()` trong `try/except (ValueError, base64.binascii.Error)`, `safe_name = Path(name).name` | Đúng — không còn `bytes.fromhex()` nào (grep xác nhận sạch), path traversal chặn đúng như bug đã fix ở `upload.py` |
| 6.9.6 bước 8: `middle_json` là JSON string, `json.loads()`, phòng hờ server trả sẵn dict, không raise khi thiếu | `_write_middle_json()`: `json.loads(raw) if isinstance(raw, str) else raw`, bắt `(json.JSONDecodeError, TypeError)` → trả `OcrQuality(None, 0, 0, "unavailable")`, không raise | Đúng |
| 6.9.5 công thức confidence: weighted theo SỐ SPAN (không phải ký tự), gồm cả span score=0.0 trong mẫu số, `None` khi không có span | `_compute_quality()`: `scores.append(span["score"])` cho mọi span có key `"score"` (không lọc `score>0`), `confidence = sum(scores)/len(scores)`, `if not scores: return OcrQuality(None, 0, 0, "unavailable")` | Đúng — đã tự kiểm bằng test live (1 span, confidence=0.999=chính điểm span đó, không bị pha loãng bởi ký tự) |
| Duyệt cả `preproc_blocks` và `discarded_blocks`, đệ quy qua block lồng nhau (bảng) | `_walk_block()` đệ quy qua `block["blocks"]`, gọi cho cả `("preproc_blocks", "discarded_blocks")` mỗi trang, dùng `.get(..., []) or []` xuyên suốt | Đúng |

**Tự nghĩ 1 edge case và verify bằng đọc code**: `middle_json` có `discarded_blocks` nhưng
không có `preproc_blocks` nào chứa span (ví dụ trang toàn text-layer, MinerU không OCR gì,
chỉ có vài block bị discard do lý do khác — không phải OCR). Trace code: vòng lặp
`for block_group_key in ("preproc_blocks", "discarded_blocks")` chạy độc lập cho từng nhóm,
`preproc_blocks=[]` → `_walk_block` không được gọi lần nào cho nhóm này, `discarded_blocks`
vẫn được duyệt bình thường qua `_walk_block`. Nếu không block nào trong `discarded_blocks` có
span mang key `"score"` (discard vì lý do khác OCR, ví dụ header/footer bị loại theo layout),
`scores` rỗng → `OcrQuality(None, 0, 0, "unavailable")`, **không crash, không raise** — đúng
theo spec "không có span nào có score → hợp lệ". Đã có test tương đương
(`test_confidence_none_when_no_span_has_score`) dùng `preproc_blocks: []` + `discarded_blocks:
[]` (cả hai rỗng) — case tôi tự nghĩ ra (discarded_blocks CÓ phần tử nhưng phần tử đó không
có span điểm số) là một biến thể chưa có test riêng, nhưng đã verify đúng qua đọc code (không
phải suy đoán) nên không phải blocking — ghi vào non-blocking suggestion bên dưới.

### Các chỗ gọi `MinerURunner` — verify đồng bộ

- `src/api/routes/jobs.py::_build_mineru_runner()` (dòng 242-256): dùng đúng
  `task_timeout_seconds=settings.mineru_task_timeout_seconds`,
  `request_timeout_seconds=settings.mineru_request_timeout_seconds` — khớp signature mới
  2-timeout của `MinerURunner.__init__`.
- `src/core/job_orchestrator.py` dòng 203: `job.ocr_confidence = ocr_result.quality.confidence`
  — đã đổi từ `confidence_score` cũ, xử lý `None` đúng thiết kế (comment tại chỗ giải thích rõ
  không raise, không cảnh báo giả).
- `src/core/config.py`: `mineru_task_timeout_seconds=3600.0`,
  `mineru_request_timeout_seconds=120.0`, `ocr_confidence_threshold=0.80` — có mặt đúng tên,
  đúng giá trị mặc định theo spec. Field `mineru_timeout_seconds` cũ đã xoá (grep xác nhận
  không còn tham chiếu nào trong `src/`).
- Grep toàn `src/` cho `confidence_score`, `/ocr\b`, `fromhex`, `mineru_timeout_seconds` (tên
  cũ không hậu tố) — **không còn kết quả nào** ngoài dòng docstring của `mineru_runner.py` tự
  mô tả lại sự cố cũ (mang tính lịch sử, không phải code sống).

**Quan sát non-blocking**: `ocr_confidence_threshold` được định nghĩa trong `config.py` nhưng
grep toàn `src/` không tìm thấy nơi nào thực sự so sánh `job.ocr_confidence` với ngưỡng này để
sinh cảnh báo 3 nhánh cho user (PRD US-11 AC). Có thể đây là phần UI/route chưa thuộc scope của
lần rewrite này (rewrite chỉ tập trung `MinerURunner` + wiring), nhưng nếu US-11 được coi là
"đã xong" thì nhánh cảnh báo user-facing vẫn còn thiếu — cần Tech Lead/PM xác nhận đây có phải
phạm vi của increment kế tiếp hay không.

### Test coverage — `tests/test_mineru_runner.py`

Đếm được đúng **16 test** như Dev báo cáo. Coverage đủ các edge case quan trọng:
task failed (`test_task_status_failed_raises_mineru_error`), task lost/404
(`test_task_lost_404_raises_mineru_error`), timeout
(`test_task_timeout_raises_mineru_timeout_error`), confidence=None cả 2 trường hợp (không span
nào có score, và thiếu hẳn `middle_json`), malformed image bị bỏ qua không hỏng job
(`test_malformed_image_entry_skipped_not_fatal`), key kết quả ambiguous
(`test_result_entry_ambiguous_key_mismatch_raises`), `/health` cả 3 nhánh (200/503/connection
error), submit lỗi field/status khác 202, connection error khi submit. Fixture
`_mineru_result_payload()` / `_middle_json_with_scores()` dựng đúng shape thật
(`results[<name>]` keyed theo tên file, `images` dict data-URI, `middle_json` là JSON string)
— không phải mock tự chế theo trí nhớ, đúng tinh thần Protocol 5 (docstring đầu file tự nêu rõ
điều này).

`tests/integration/test_job_orchestrator.py::_fake_mineru_runner()` đã cập nhật đúng
`MinerUResult`/`OcrQuality` mới, không còn field `confidence_score`/`success` cũ.

### Regression check

```
.venv/bin/python -m pytest tests/ -q   → 141 passed, 160 warnings (0 failed)
.venv/bin/python -m ruff check src/ tests/   → All checks passed!
.venv/bin/python -c "from src.api.main import app"   → import OK (chỉ có warning
    deprecation không liên quan: pymupdf `fitz` alias, `google.generativeai` — cả 2 đã biết
    từ trước, không phải regression của lần rewrite này)
```

### PRD US-11 — đối chiếu câu chữ với logic thật

3 nhánh trong PRD (`docs/PRD.md` dòng 122-125) khớp đúng với code:
- `ocr_confidence ≥ 0.80` — khớp `_compute_quality()` trả `confidence` là số thực, so sánh
  ngưỡng 0.80 (`ocr_confidence_threshold`) — **nhưng xem quan sát non-blocking ở trên**: bản
  thân phép so sánh + cảnh báo UI chưa thấy trong `src/`, chỉ có việc lưu đúng giá trị.
- `ocr_confidence < 0.80` — tương tự, giá trị được tính và lưu đúng, cảnh báo UI chưa xác nhận.
- `ocr_confidence = NULL` khi không span nào qua OCR — khớp chính xác với
  `OcrQuality(confidence=None, ...)` khi `scores` rỗng, PRD mô tả đúng nguyên nhân ("trang chỉ
  toàn hình ảnh không có text nhận dạng được" ≈ không có span nào có key `score`).

Câu chữ định nghĩa confidence trong PRD ("trung bình có trọng số theo số đoạn text (span) đã
qua OCR") khớp chính xác với `_compute_quality()` — không có sai lệch.

### Verdict: APPROVE

Không có blocking issue. `MinerURunner` khớp Architecture.md 6.9 từng phần đã đối chiếu, R5-04
trả lời YES với 3 lớp bằng chứng độc lập (source code + PM run + Dev run + Reviewer tự tái hiện
lúc review), 141/141 test pass, ruff sạch, import sạch. Non-blocking suggestion duy nhất: xác
nhận phạm vi của nhánh cảnh báo UI so sánh `ocr_confidence_threshold` (có thể đã nằm ngoài scope
của increment rewrite `MinerURunner`).

### Khuyến nghị vòng QA tiếp theo (không tự quyết thay QA)

Đây là thay đổi lớn trên 1 pipeline chính (OCR cho toàn bộ nhánh `pdf_scan`), và dù Reviewer đã
tự chạy live smoke test độc lập thành công, Protocol 5 R5-03 quy định **QA** là bên gate
`ready_for_release`, không phải Reviewer. Đề xuất: **cần thêm 1 vòng QA xác nhận** trước khi
đổi `project_state.json.status` sang `ready_for_release`, vì:
1. R5-03 yêu cầu smoke test thật trước khi QA đánh dấu ready — Reviewer đã cung cấp bằng chứng
   đó nhưng chưa phải QA tự thực hiện theo đúng vai trò được phân trong Protocol 4.
2. QA Round 1/2 trước đó (test-report.md) test toàn bộ luồng `pdf_scan` với `MinerURunner` cũ
   qua **fake server tự viết** (port 8021, `confidence_score` cũ) — chưa từng test qua
   `JobOrchestrator` thật với `MinerURunner` MỚI end-to-end (chỉ có unit test
   `test_mineru_runner.py` + integration test dùng `AsyncMock(spec=MinerURunner)`, chưa có test
   nào chạy `run_job()` thật với MinerU server thật cho 1 job `pdf_scan` hoàn chỉnh, gồm cả
   bước ghi `jobs.ocr_confidence` vào DB và các bước sau đó của pipeline).
3. Non-blocking suggestion về `ocr_confidence_threshold` ở trên nên được QA xác nhận có phải
   known limitation cần ghi rõ hay là bug thực sự trước khi release.

`project_state.json` được cập nhật `status` sang `pending_qa_reverify_mineru_rewrite` thay vì
`ready_for_release` trực tiếp — chờ PM quyết định có bỏ qua vòng QA này hay không.
(không cần vòng 3). Sẵn sàng chuyển cho QA.

---

## Bug #5 Fix — Protocol 6 Review

- **Ngày**: 2026-09-04
- **Reviewer**: Reviewer (Sonnet)
- **Phạm vi**: fix cho Bug #5 (OCR-to-Translate Bridge) — `src/preprocess/searchable_pdf.py`
  (mới), `src/core/job_orchestrator.py` (`run_job()`, `_build_ocr_bridge()`), `src/models/job.py`
  (2 cột mới), Architecture.md 6.10 (8 tiểu mục), PRD US-04/US-11, CHANGELOG mục "Bug #5 Fix".
  Ghi chú ngữ cảnh: mục CHANGELOG này do **PM** viết thay Dev (Dev bị interrupt giữa chừng) —
  review này được thực hiện độc lập hơn bình thường theo đúng yêu cầu, tự đọc code + tự chạy lại
  toàn bộ, không suy ra kết luận từ nội dung CHANGELOG.

### Verdict: **APPROVE**

Không có blocking issue. Cả 4 tiêu chí bắt buộc của Protocol 6 (R6-01, R6-02, R6-04) và guard
BR-OCR-01/02/03 đều đạt, có bằng chứng cụ thể bên dưới. Reviewer tự verify sống độc lập với nội
dung khác PM đã dùng — kết quả khớp claim trong CHANGENLOG.

### 1. R6-01 — Data lineage khai báo trong Architecture.md 6.10.5/6.10.8

**Đạt.** Bảng lineage tại 6.10.8 liệt kê tường minh 7 bước, mỗi dòng nêu đúng tên biến/field cụ
thể — không mô tả mập mờ kiểu "dịch file":
- Bước 3 ghi rõ: `build_searchable_pdf(file_path, ocr_result.middle_json_path, bridge_path)` →
  output `SearchablePdfResult.path` → biến tiêu thụ ở bước 5 là **`translation_source_path =
  bridge.path`**, có chú thích "soi day tung bi dut o Bug #5".
- Bước 5 ghi rõ input của `pdf2zh_runner.translate_pages` là `translation_source_path`, **KHÔNG
  PHẢI** `job.file_path` — nêu rõ cả 2 khả năng để phân biệt.
- Bước 7 (bilingual) ghi rõ ngoại lệ có chủ đích: dùng `merged_path` + `file_path` **gốc**,
  không phải `translation_source_path`/bridge — đúng khớp code (`create_bilingual_pdf(merged_path,
  file_path, ...)` tại `job_orchestrator.py:350`, dùng biến `file_path` chứ không phải
  `translation_source_path`).
6.10.5 cũng liệt kê bảng "vị trí hiện tại → đổi thành" cho từng lời gọi cụ thể, và bảng riêng
"3 chỗ VẪN dùng file gốc — có chủ đích" (đếm trang, gọi MinerU, mặt EN bilingual) kèm lý do cho
từng chỗ. Đạt yêu cầu R6-01.

### 2. R6-04 — Tự trace tay biến trong `job_orchestrator.py`

Đã đọc trực tiếp toàn bộ `run_job()`, `_build_ocr_bridge()`, `_process_chunk()` (không dựa vào
CHANGELOG). Grep `job.file_path` và `file_path` trong file:

```
199: file_path = Path(job.file_path)                                   # gán 1 lần đầu run_job()
206: job.total_pages = _count_pdf_pages(file_path)                     # (1) đếm trang — file gốc, đúng
208: translation_source_path = file_path        # pdf_digital: khong doi
210-211: if PDF_SCAN: translation_source_path = await self._build_ocr_bridge(job, file_path, db_session)
216: full_text = _extract_full_text(translation_source_path)           # dùng biến lineage — ĐÚNG
279: await self._process_chunk(job, chunk, translation_source_path, ...) # truyền biến lineage — ĐÚNG
350: await create_bilingual_pdf(merged_path, file_path, bilingual_path) # (3) mặt EN bilingual — file gốc, có chủ đích, đúng
```
Trong `_build_ocr_bridge()`:
```
405: ocr_result = await self._mineru_runner.parse_document(file_path, ocr_dir)  # (2) MinerU đọc ảnh gốc — đúng
419: bridge = build_searchable_pdf(file_path, ocr_result.middle_json_path, bridge_path)
423: return bridge.path                                                 # trả về CHÍNH bridge, không phải file_path
```
Trong `_process_chunk(self, job, chunk, source_path, ...)`: tham số được đặt tên `source_path`
(không phải đọc lại `job.file_path`), và **mọi** lời gọi tiêu thụ nội dung bên trong hàm này đều
dùng `source_path`:
```
494: input_path=source_path                    # pdf2zh_runner.translate_pages — ĐÚNG
531: source_text = _extract_chunk_text(source_path, chunk)      # ĐÚNG
532: segment_count = _count_text_segments(source_path, ...)      # ĐÚNG
```
Xác nhận: **không còn chỗ nào** trong đường đọc nội dung (text extraction, cost estimate, gọi
pdf2zh) dùng lại `job.file_path`/`file_path` gốc ngoài 3 ngoại lệ đã liệt kê ở Architecture.md
6.10.5, và cả 3 ngoại lệ đó đúng như trace tay ở trên (đếm trang, OCR đọc ảnh gốc, mặt EN
bilingual). `_build_ocr_bridge()` không có nhánh nào fallback về `file_path` khi bridge build
thất bại — `build_searchable_pdf()` raise `SearchablePdfError` (subclass `RuntimeError`), không
bị nuốt ở đây, lan thẳng lên `run_job()` và rơi vào nhánh `except Exception` của Step 7/8 → job
fail. Đây chính xác là thứ Bug #5 thiếu (một cái "quên" duy nhất khiến job vẫn chạy tiếp trên
file gốc) — code hiện tại không còn đường lùi nào về `file_path` cho nội dung dịch.

**Kết luận R6-04**: đạt, đã tự trace tay từng dòng, không chỉ tin xác nhận "cả 2 bước đều được
gọi đúng tham số theo spec riêng của nó".

### 3. R6-02 — Test assert giá trị cụ thể

**Đạt — tìm thấy đúng test yêu cầu.** `tests/integration/test_job_orchestrator.py`:

- `test_pdf_scan_translates_bridge_not_original` (dòng 421-455): assert **giá trị cụ thể**, không
  chỉ `assert_awaited()`:
  ```python
  expected_bridge = tmp_path / "processing" / job.id / "ocr_bridge" / "searchable.pdf"
  for call in pdf2zh_runner.translate_pages.await_args_list:
      assert call.kwargs["input_path"] == expected_bridge
      assert call.kwargs["input_path"] != Path(job.file_path)
  assert expected_bridge.exists()
  await session.refresh(job)
  assert job.ocr_bridge_path == str(expected_bridge)
  ```
  Đây đúng dạng ví dụ R6-02 trong CLAUDE.md yêu cầu — assert cả giá trị dương (bằng bridge path)
  **và** giá trị âm (khác `job.file_path`), cộng thêm assert file bridge thực sự tồn tại trên đĩa
  (không phải giả định) — mạnh hơn yêu cầu tối thiểu của Protocol 6.
- `test_pdf_digital_still_uses_original` (dòng 459-479): test đối chứng no-regression, assert
  `input_path == Path(job.file_path)` cho nhánh `pdf_digital` — đúng vai trò "test #2" nêu ở
  6.10.8.
- `test_bilingual_uses_original_scan_not_bridge` (dòng 483-528): assert
  `call.args[1] == source_pdf` (không phải bridge) cho mặt EN của bilingual — đúng "test #3" nêu
  ở 6.10.8, xác nhận ngoại lệ có chủ đích không bị đổi nhầm thành bridge.
- Bổ sung ngoài yêu cầu tối thiểu: `test_pdf_scan_without_mineru_configured_fails_before_pdf2zh`
  (BR-OCR-01) và `test_empty_translation_fails_job` (BR-OCR-03) — cả hai đều assert hành vi cụ
  thể (raise đúng exception / `result.status == "failed"` + message), không phải chỉ smoke test.

**Kết luận R6-02**: đạt đầy đủ — đây chính là loại test Protocol 6 sinh ra để bắt Bug #5, và nó
thực sự fail trên code cũ (theo lineage table, đã được Dev/PM xác nhận).

### 4. Guard BR-OCR-01, BR-OCR-02, BR-OCR-03

| Guard | Vị trí | Xác nhận |
|---|---|---|
| BR-OCR-01 | `job_orchestrator.py:391-396` (`_build_ocr_bridge`) | `if self._mineru_runner is None: raise MinerUUnavailableError(...)` — raise **trước** khi có bất kỳ lời gọi `pdf2zh_runner` nào (hàm này được gọi ở Step 2, trước Step 5-7). Test: `test_pdf_scan_without_mineru_configured_fails_before_pdf2zh` — `pytest.raises(MinerUUnavailableError)` + `pdf2zh_runner.translate_pages.assert_not_awaited()`. Chạy pass. |
| BR-OCR-02 | `src/preprocess/searchable_pdf.py:107-111` | Sau `doc.save(output_path)`, đếm lại `_count_extracted_chars(output_path)` bằng PyMuPDF thật (đọc lại file vừa ghi, không tin biến đếm nội bộ) — `== 0` → `raise SearchablePdfError(...)`. Test: `tests/preprocess/test_searchable_pdf.py` (đọc thấy có test `no_text_spans=True` dùng trong `_fake_mineru_runner` của integration test, và bridge module có test riêng dùng PyMuPDF thật, không mock — đúng tinh thần "test bridge module bằng PyMuPDF THẬT" ghi trong CHANGELOG). |
| BR-OCR-03 | `job_orchestrator.py:319-327` | Ngay sau `merge_chunk_pdfs()` ở Step 8, mở lại `merged_path`, cộng `len(page.get_text().strip())` toàn bộ trang — `== 0` → `raise Pdf2zhEmptyOutputError(...)`, rơi vào `except Exception` cùng khối → `job.status = "failed"`, **không** phải `"completed"`. Áp dụng cho **mọi** `file_type` (đặt sau merge, không có điều kiện `if file_type == PDF_SCAN`) — đúng yêu cầu 6.10.5 "áp dụng cho MỌI file_type". Test: `test_empty_translation_fails_job` dùng `_fake_pdf2zh_runner_empty_output()` (chunk "thành công" nhưng PDF không có text nào) trên nhánh `pdf_digital` — cố ý chọn `pdf_digital` để chứng minh guard không chỉ áp dụng cho `pdf_scan`. |

Cả 3 test trên đã tự chạy lại (`uv run pytest tests/ -q`, xem mục 7) — pass.

### 5. Tự verify sống độc lập (không tin PM đã làm)

MinerU server thật vẫn đang chạy — `curl http://127.0.0.1:8010/health` trả
`{"status":"healthy","version":"3.4.5",...}`.

Đã tự tạo 1 PDF scan-like **MỚI**, nội dung khác hoàn toàn PM đã dùng ("Macaron shells...") và
khác Dev dùng trong test cố định:

> **"Croissant lamination requires 3 folds of cold butter into detrempe dough overnight."**

Quy trình tự chạy (script riêng, không dùng lại code PM/Dev đã chạy):
1. Render text thành ảnh (không có text layer) → nhúng vào 1 trang PDF — mô phỏng đúng dạng file
   scan-like mà Tech Lead dùng cho T1-T4.
2. Gọi `MinerURunner(base_url=settings.mineru_endpoint).parse_document()` **thật** (HTTP task
   flow thật, không mock) → `confidence=0.987`, `dropped_span_count=0`,
   `middle_json_path` tồn tại thật trên đĩa.
3. Gọi `build_searchable_pdf()` **thật** trên kết quả OCR thật → `SearchablePdfResult(span_count=1,
   page_count=1, extracted_chars=83)`.
4. Verify **bằng chính Python của pdf2zh** (`/Users/hieutt/.local/share/uv/tools/pdf2zh/bin/python`,
   không phải venv của project):
   ```python
   from pdfminer.high_level import extract_text
   extract_text('.../searchable.pdf')
   # → 'Croissant lamination requires 3 folds of cold butter into detrempe dough overnight.\n\n\x0c'
   # len (đã strip) = 83 — khớp CHÍNH XÁC 100% nội dung gốc
   ```
5. Đối chứng: `extract_text()` trên **file scan gốc** (chưa qua bridge) → `''` — tái hiện đúng
   triệu chứng Bug #5 gốc, chứng minh bridge là thứ thực sự sửa vấn đề chứ không phải trùng hợp.
6. Kiểm tra whiteout có phạm vi đúng thiết kế (không xoá sạch ảnh): `page.get_images()` → 1 ảnh
   (ảnh scan gốc còn nguyên), `page.get_drawings()` → 1 hình chữ nhật trắng (đúng 1 span text
   trong fixture này) — không phải xoá trắng toàn trang.

**Kết luận verify sống**: khớp hoàn toàn với claim trong CHANGELOG (PM dùng nội dung khác, kết
quả cùng bản chất: extract rỗng ở file gốc, extract đúng 100% ở bridge). Independent double-check
thành công.

### 6. Schema breaking change

`src/models/job.py` dòng 50-53:
```python
ocr_bridge_path: str | None = Field(default=None)
ocr_dropped_spans: int | None = Field(default=None)
```
Cả 2 đều `str | None` / `int | None` với `default=None` — đúng yêu cầu 6.10.7 "cả hai nullable,
mặc định `None`". Comment tại chỗ nhắc đúng rủi ro breaking schema (`SQLModel.metadata.create_all()`
không tự thêm cột vào bảng cũ) và trỏ đến CHANGELOG.

### 7. Regression toàn diện

- `uv run ruff check src/` → **All checks passed**.
- Xoá `data/bb_translation.db`, `data/bb_translation.db-shm`, `data/bb_translation.db-wal` (DB dev
  cũ, thiếu 2 cột mới) rồi chạy lại từ đầu:
  `uv run pytest tests/ -q` → **159 passed**, 0 failed (179 warnings, toàn bộ là deprecation
  warnings không liên quan — `fitz`/PyMuPDF legacy import, `google.generativeai` deprecated,
  `datetime.utcnow()` — đã tồn tại từ trước, không phải do fix này).
- `uv run python -c "from src.api.main import app"` → import thành công, không lỗi.

### External contract verified against real source (CLAUDE.md R5-04)

`src/preprocess/searchable_pdf.py` không tự nó gọi HTTP/subprocess ra ngoài (chỉ dùng PyMuPDF —
thư viện Python nội bộ, ngoài phạm vi Protocol 5 theo đúng "Phạm vi áp dụng" của CLAUDE.md) →
**N/A** cho R5-04 xét riêng module này. Nhưng nó tiêu thụ trực tiếp `middle_json` — sản phẩm của
`MinerURunner` (đã verify ở review round trước, xem phần "Increment 4/MinerU rewrite" phía trên
file này) — và mục 6.10.1 của Architecture.md dẫn nguồn xác thực S10-S18 cho từng giả định về
format `middle_json`/hành vi pdf2zh, kèm theo 4 thí nghiệm chạy thật (T1-T4). Trả lời: **External
contract verified against real source: YES** (nguồn: source code `mineru`/`pdf2zh`/`pdfminer` đã
cài thật trên máy dev, trích dẫn file:line cụ thể tại 6.10.1, cộng với Reviewer tự tái hiện lại
độc lập ở mục 5 phía trên bằng nội dung khác).

### Non-blocking suggestions

1. **PRD US-11 / Architecture.md 6.10.7 mục 2-3 — điểm còn treo, đã được Tech Lead tự nêu, chưa
   thấy PM/user trả lời chính thức trong PRD.md**: Architecture.md 6.10.6 quyết định cảnh báo OCR
   confidence thấp là **thông báo không chặn job** ("Khong chan job de cho user xac nhan... v1.0
   job chay background, chua co co che pause/resume"), nhưng PRD.md US-11 (dòng 128) vẫn còn viết
   nguyên văn "cảnh báo... cho user chọn tiếp tục hoặc huỷ" — đọc như thể job **có** dừng chờ xác
   nhận. Đây là mâu thuẫn giữa PRD và Architecture hiện tại, bản thân Architecture.md 6.10.7 mục 2
   đã tự flag đúng điểm này ("cần PM/user quyết định — Tech Lead KHÔNG tự sửa PRD"). Không block
   review này (code khớp đúng quyết định mới nhất ở Architecture 6.10.6 — non-blocking, chạy đúng
   thiết kế), nhưng đề nghị PM chốt và cập nhật câu chữ US-11 trong PRD.md trước khi coi tính năng
   này là "đã chốt xong tài liệu" — nếu không sửa, tài liệu cho user cuối (PRD) và hành vi thực tế
   (code) sẽ lệch nhau.
2. **`docs/CHANGELOG.md` mục Bug #5 Fix nói "Chưa test được luồng dịch LLM thật đầu-cuối"** — đúng,
   Reviewer cũng không test được (không có API key thật khả dụng trong phiên review này). Đây là
   giới hạn đã biết, không phải lỗi của fix này, nhưng nhắc lại để QA vòng tiếp theo lưu ý: R6-03
   (CLAUDE.md) yêu cầu ít nhất 1 lần chạy XUYÊN SUỐT toàn bộ chuỗi OCR→dịch với dữ liệu thật, kiểm
   tra nội dung output cuối cùng — phần "xuyên suốt tới bản dịch tiếng Việt thật" (qua pdf2zh gọi
   LLM thật) vẫn **chưa** được ai chạy (chỉ chạy tới bước bridge/OCR). Đề nghị ghi rõ trong
   test-report.md của QA vòng tới: `"release blocked pending live verification: pdf2zh LLM
   translation end-to-end"` nếu QA cũng chưa chạy được, theo đúng R5-03/R6-03 — không nên coi
   verify của Reviewer (chỉ tới bước bridge) là đủ điều kiện release.

### Kết luận

APPROVE cho fix Bug #5. Toàn bộ yêu cầu bắt buộc của Protocol 6 (R6-01, R6-02, R6-04) đạt với
bằng chứng cụ thể ở trên, cả 3 guard BR-OCR-01/02/03 đúng vị trí đúng logic và có test pass, và
Reviewer tự tái hiện thành công toàn bộ chuỗi OCR→bridge sống với dữ liệu hoàn toàn mới, độc lập
với những gì PM đã chạy. Còn 1 việc **chưa** nằm trong phạm vi review này và **không** được coi
là đã "release-ready" chỉ vì review này APPROVE: R6-03 (live E2E tới tận bản dịch tiếng Việt qua
LLM thật) vẫn cần QA thực hiện trước khi đóng `ready_for_release` — xem non-blocking suggestion #2.

---

# Review Report — Increment 6 (UX & Model Management)

- **increment_number**: 6
- **iteration**: 1/3
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-04

## Verdict: APPROVE

## Tóm tắt

Increment 6 sửa 6 vấn đề UX/tính năng do user phát hiện khi dùng app thật để dịch 1 cuốn sách
415 trang: (1) bug root cause "estimate cost tạo job thật", (2) khôi phục state khi chuyển tab,
(3) chọn model + API key qua UI, đổi default `openai_model` `gpt-4o`→`gpt-4o-mini`, (4) cancel
job graceful, (5) dịch từng file riêng, (6) phân trang glossary + nhớ lựa chọn provider/model qua
localStorage. Không đổi kiến trúc pipeline dịch (job_orchestrator core flow, pdf2zh, MinerU).

## 2 điểm quan trọng nhất — verify độc lập, không chỉ tin CHANGELOG

### 1. `POST /api/estimate` KHÔNG tạo Job/Batch row thật — XÁC NHẬN ĐÚNG

Đọc `src/api/routes/jobs.py::estimate_cost_without_job()` (dòng 560-595): chỉ gọi
`resolve_upload()` (đọc sidecar JSON từ upload trước đó, không đụng DB `jobs`/`batches`) rồi
`estimate_job_cost()` (`src/core/cost_estimator.py`, hàm thuần, không có side effect DB) — không
có `Job(...)`, không có `session.add()`, không có `_schedule_background()` nào trong toàn bộ
handler này.

Tự verify sống (không chỉ đọc code, không chỉ tin test): khởi động `uvicorn` thật với DB tạm
riêng (`/tmp/bbt_verify`), tạo PDF 3 trang thật bằng PyMuPDF, gọi `POST /api/upload` →
`GET /api/jobs` (`total: 0`) → `POST /api/estimate {file_id, provider:"ollama"}` → 200,
`total_pages:3`, `estimated_cost_usd:0.0` → `GET /api/jobs` lại (`total: 0`, không đổi). Kết quả
khớp 100% với những gì CHANGELOG mô tả. Đồng thời `web/js/app.js::estimateCost()` đã sửa đúng
(gọi `/api/estimate` thay vì `this.createJob(f)` cũ) — root cause bug được xử lý cả ở backend lẫn
chỗ gọi frontend gây ra bug ban đầu, không phải chỉ thêm endpoint mới rồi bỏ quên chỗ gọi cũ.

### 2. Cancel dừng ĐÚNG SAU chunk hiện tại, không phải giữa chừng — XÁC NHẬN ĐÚNG (Protocol 6)

Tự trace tay `job_orchestrator.py::run_job()` Step 7 (dòng 268-330): vòng lặp `for chunk in
chunks` gọi `_process_chunk()` (dịch + post-process + tính cost cho TOÀN BỘ chunk đó) trước, rồi
mới `progress_tracker.update()`, rồi mới `await db_session.refresh(job)` + kiểm tra
`job.cancel_requested`. Vị trí check nằm SAU khi `_process_chunk()` đã return (chunk đã
`status="completed"` trong DB) — không có chỗ nào ngắt `_process_chunk()` giữa chừng, không
force-kill subprocess `pdf2zh` đang chạy dở. Việc `await db_session.refresh(job)` tường minh
trước khi đọc cờ là bắt buộc và đúng — session này dùng `expire_on_commit=False` nên sẽ không tự
thấy write từ session khác (request `POST .../cancel`) nếu thiếu refresh; đây chính xác là loại
lỗi Protocol 6 nhắm tới (nối 2 bước qua state DB, không phải chỉ "cả 2 đều được gọi").

Bằng chứng test không chỉ là `assert_called()` mà assert đúng tinh thần R6-02:
`tests/integration/test_job_cancel.py::test_run_job_stops_gracefully_after_cancel_requested_mid_run`
mock đặt `cancel_requested=True` qua 1 session RIÊNG (mô phỏng đúng race của 1 request HTTP khác)
NGAY SAU KHI chunk 1 render xong, rồi assert `pdf2zh_runner.translate_pages.await_count == 1`
(chunk 2 chưa bao giờ được gọi) VÀ `[c.status for c in chunks] == ["completed", "pending",
"pending"]` — xác nhận đúng vị trí dừng bằng giá trị cụ thể, không chỉ "đã gọi/không gọi". Test
thứ 2 (`test_cancelled_job_is_resumable_like_a_failed_job`) verify tiếp: sau cancel, resume lại
chỉ render đúng 2 chunk còn lại (`await_count == 2`), không render lại chunk đã completed — resumable
thật, không chỉ lý thuyết.

`retry_job()` (dòng 472-496): `_RETRYABLE_STATUSES = {"failed", "cancelled"}` — xác nhận đã đổi
đúng, và có 1 dòng dễ bị quên nhưng Dev đã xử lý đúng: `job.cancel_requested = False` được reset
trước khi lên lịch chạy lại — nếu thiếu bước này, `run_job()` chạy lại sẽ đọc thấy cờ cũ còn
`True` và tự cancel lại ngay sau chunk đầu tiên (bug tự tạo ra). Status trả về sau cancel là
`"cancelled"`, không phải `"failed"` (dòng 314, đúng distinct status, `error_message` không bị
set — đúng vì đây là user chủ động dừng).

Đây là 1 pattern review tốt cần giữ nguyên cho các increment sau: test không chỉ mock 2 lời gọi
độc lập rồi assert riêng lẻ, mà mock CÙNG state DB (session khác nhau, giống race thật) và assert
số lần gọi/trạng thái cụ thể sau cancel — đúng tinh thần R6-02, không lặp lại kiểu lỗi Bug #5.

## Checklist chi tiết

| # | Hạng mục | Kết quả |
|---|----------|---------|
| 1 | Estimate không tạo Job/Batch | PASS — xem mục 1 trên, verify sống qua curl |
| 2 | Cancel đúng vị trí (Protocol 6) | PASS — xem mục 2 trên, trace tay + test cụ thể |
| 3 | `get_effective_settings()`/`provider_models` override đúng field | PASS — đọc `src/api/routes/settings.py` `_PROVIDER_MODEL_FIELDS` map đúng provider→field (`claude_model`/`openai_model`/`deepseek_model`/`gemini_model`, `deepl` cố ý không có model); `openai_model` default xác nhận `"gpt-4o-mini"` trong `src/core/config.py` dòng 24 |
| 4 | Breaking schema change `Job.cancel_requested` | PASS — cột có `default=False` (không crash code Python khi thiếu giá trị), nhưng đúng như Dev tự ghi: `SQLModel.metadata.create_all()` không ALTER bảng cũ, DB `data/*.db` cũ thiếu cột sẽ lỗi khi query — đây là hành vi SQLite/SQLModel mong đợi (đã từng xảy ra y hệt ở Increment 4), không phải bug code, chỉ cần README/CHANGELOG nhắc rõ (đã có) |
| 5 | Frontend — không lộ API key thật | PASS — `web/js/settings.js::load()` luôn set `apiKeyDrafts[name] = ""`, không bao giờ gán từ response; chỉ hiển thị qua `has_key` boolean. `grep localStorage` toàn bộ `web/js/*.js` chỉ thấy `bb_last_provider`/`bb_last_output_mode` (tên provider + output_mode) — không có API key nào ghi vào localStorage |
| 6 | Test coverage | PASS, đủ edge case chính — xem "Test coverage" bên dưới |
| 7 | Regression | PASS — `ruff check`, import chain, glossary roundtrip, DeepL PDF block đều chạy lại thật |

## Test coverage — đánh giá

Đọc `tests/integration/test_job_cancel.py` (3 test), `tests/integration/test_estimate_and_cancel_api.py`
(8 test — không phải khớp CHANGELOG ghi "8 test", đếm lại đúng 8), `tests/integration/test_settings_api.py`
(4 test). Edge case đã có:
- Cancel job đã `completed` → 400 (`test_cancel_rejects_a_terminal_job`).
- Estimate cho `file_id` không tồn tại → 404, không tạo Job (`test_estimate_unknown_file_id_returns_404`).
- Estimate cho EPUB → 400 (`test_estimate_rejects_epub`).
- Retry job đang chạy (không phải failed/cancelled) → vẫn 400 (`test_retry_still_rejects_a_non_terminal_job`).
- `provider_models` với tên provider lạ → không crash, không tạo `Setting` row rác
  (`test_put_provider_models_ignores_unknown_provider_name`).
- `PUT .../provider_models` verify qua `get_effective_settings()` thật, không chỉ tin response
  echo (`test_put_provider_models_overrides_effective_settings`) — đúng thói quen tốt đã hình
  thành từ Protocol 5/6.

Non-blocking gap nhỏ (không đủ nghiêm trọng để block): chưa có test cho double-cancel (gọi
`POST .../cancel` 2 lần liên tiếp trên job đang chạy) — endpoint hiện tại không reject, chỉ ghi
đè `cancel_requested=True` lần 2 (vô hại vì idempotent), nhưng nên có 1 test xác nhận tường minh
hành vi này thay vì để ngầm định.

## Regression đã tự chạy lại

- `uv run ruff check src/ tests/`: All checks passed.
- Xoá `data/*.db*` cũ trước khi chạy (breaking schema change) → `uv run pytest tests/ -q`: **174
  passed**, khớp CHANGELOG.
- `uv run python -c "from src.api.main import app"`: OK.
- `uv run pytest tests/integration/test_glossary_api.py -q`: 4 passed (US-03 roundtrip không bị
  ảnh hưởng).
- `uv run pytest -q -k "deepl or DeepL"`: 8 passed, bao gồm
  `test_run_job_with_deepl_fails_before_any_subprocess_call` (US-14 DeepL+PDF block vẫn đúng).
- Verify sống qua `uvicorn` thật (DB tạm, không đụng `data/` máy dev) — xem mục 1 trên.

## Non-blocking suggestions

1. **Double-cancel chưa có test tường minh** — xem "Test coverage" trên. Đề xuất thêm 1 test gọi
   `cancel` 2 lần, assert vẫn 200 lần 2 (idempotent), không phải để increment sau tự suy luận.
2. **`JobDetail.cancel_requested` mặc định `False`** (dòng 134 `src/api/routes/jobs.py`) —
   backward-compatible đúng, nhưng lưu ý field này SẼ sai (`None`→`False` implicit) nếu 1 job cũ
   trong DB được tạo TRƯỚC breaking schema change này bằng cách nào đó lọt qua (không nên xảy ra
   nếu làm đúng hướng dẫn "xoá `data/*.db*`", chỉ ghi chú phòng hờ).
3. **R6-03 (CLAUDE.md) vẫn treo từ increment trước**: cancel graceful mới chỉ verify được ở cấp
   `JobOrchestrator` (test thật, không mock DB session) và cấp API (set cờ/reject đúng) — CHƯA
   verify được "cancel giữa 1 job dịch LLM thật đang chạy nhiều chunk" (cần Docker + API key thật
   + file đủ lớn), đúng như Dev tự ghi trong CHANGELOG. Đây PHẢI là 1 hạng mục QA re-verify trước
   khi đóng `ready_for_release` cho increment này — nếu chưa verify được, test-report.md phải ghi
   rõ `"release blocked pending live verification: cancel mid-real-translation"` theo đúng R5-03.

## External contract checklist (CLAUDE.md R5-04)

Increment này không sửa bất kỳ `*_runner.py`/`*_provider.py` nào (không đụng `pdf2zh_runner.py`,
`mineru_runner.py`, hay các provider SDK) — không có external contract mới nào được viết trong
increment này. **N/A.**

## Kết luận

APPROVE. 2 điểm quan trọng nhất (estimate không tạo job thật, cancel dừng đúng chỗ) đều verify
được bằng chứng cụ thể — không chỉ tin CHANGELOG — và đều PASS. Test coverage đủ edge case quan
trọng, có pattern tốt (assert giá trị cụ thể liên kết giữa các bước thay vì chỉ `assert_called()`)
đúng tinh thần Protocol 6 sau bài học Bug #5. 3 non-blocking suggestion trên không chặn merge,
nhưng suggestion #3 (R6-03) cần QA xử lý trước khi tuyên bố `ready_for_release`.

## Bug #7+#8 Fix — Protocol 5 Review

- **increment_number**: 6 (fix cho Bug #7/#8, QA Vòng 5)
- **iteration**: Dev↔QA circuit breaker 4/5 — vòng review này cần kỹ hơn bình thường
- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-04

### Verdict: APPROVE (kèm 1 non-blocking finding mới, xem mục 6)

### 1. Golden-file — tự verify độc lập, không tin lời kể

Mở trực tiếp cả 3 file bằng PyMuPDF (`.venv/bin/python`, không qua Dev/README):

```
6page_range1-3_mono.pdf  pages=6
  1 'Trang 1 điểm đánh dấu duy nhất abc1xyz.'   (đã dịch)
  2 'Trang 2 điểm đánh dấu duy nhất abc2xyz.'   (đã dịch)
  3 'Trang 3 điểm đánh dấu duy nhất abc3xyz.'   (đã dịch)
  4 'Page 4 unique marker abc4xyz.'             (tiếng Anh gốc)
  5 'Page 5 unique marker abc5xyz.'             (tiếng Anh gốc)
  6 'Page 6 unique marker abc6xyz.'             (tiếng Anh gốc)

6page_range3-6_mono.pdf  pages=6
  1-2: tiếng Anh gốc, 3-6: đã dịch tiếng Việt
```

Khớp 100% với bảng "Quan sát thật" trong `tests/fixtures/pdf2zh/README.md` — không có sai lệch
nào giữa lời kể của Dev và nội dung file thật. `README.md` ghi rõ nguồn xác thực (`pdf2zh
v1.9.11`, `uv tool install`, ngày 2026-09-04, lệnh CLI chính xác đã chạy `-s google` để tránh tốn
tiền LLM thật) — đạt yêu cầu Protocol 5 R5-02 (spike verification trước khi implement) và R5-01
(trích dẫn nguồn xác thực). Xác nhận: cả 2 file đều **6 trang = toàn bộ tài liệu gốc**, không
phải riêng phạm vi `--pages` yêu cầu — đúng root cause QA Vòng 5 đã trace, KHÔNG phải Dev tự suy
diễn thêm để hợp lý hoá fix.

### 2. Tự tính tay logic merge mới (`src/postprocess/chunk_merge.py`)

Trace tay với đúng kịch bản QA Vòng 5 (81 trang, `chunk_size=40, overlap=2` →
`calculate_chunks()` cho `[1-40], [39-80], [79-81]`, `overlap_start/overlap_end` = `[None,None]`,
`[39,40]`, `[79,80]`):

- **Chunk 0** (`position=0`): `actual_start = chunk.page_start = 1` (không trừ overlap vì là
  chunk đầu). `from_page = 0`, `to_page = min(40, 81) - 1 = 39` → lấy trang absolute 1-40 (0-index
  0-39). Đúng — đây chính là phạm vi chunk 0 chịu trách nhiệm dịch.
- **Chunk 1** (`position=1`, câu hỏi cụ thể task yêu cầu tính tay): `overlap_start=39,
  overlap_end=40` không `None` → `actual_start = overlap_end + 1 = 41`. `from_page = 41 - 1 = 40`
  (0-index), `to_page = min(80, 81) - 1 = 79` (0-index) → lấy trang **absolute 41-80** (0-index
  40-79), tức 40 trang. Vì file mono của chunk 1 chứa đủ 81 trang và trang absolute N (1-index)
  nằm ở index N-1 trong file đó (đã verify ở mục 1 — không có dịch chuyển offset nào), index 40
  trong file 81-trang của chunk 1 = trang 41 thật = đúng nội dung "trang 41" mong đợi, KHÔNG lấy
  nhầm trang overlap 39-40 (context, đã có ở đuôi chunk 0) và KHÔNG lấy nhầm sang phần tiếng Anh
  chưa dịch của trang 81 (thuộc chunk 2).
- **Chunk 2** (`position=2`): `overlap_start=79, overlap_end=80` → `actual_start=81`.
  `from_page=80`, `to_page=min(81,81)-1=80` → đúng 1 trang absolute 81 (0-index 80).
- **Tổng**: 40 (chunk 0: trang 1-40) + 40 (chunk 1: trang 41-80) + 1 (chunk 2: trang 81) = **81**,
  khớp chính xác số trang gốc và khớp assertion `texts == [f"P{n}-translated" for n in
  range(1, 82)]` trong `test_merge_chunk_pdfs_golden_shape_three_chunks`. Logic mới **đúng**,
  không chỉ đúng theo test tự viết mà đúng theo tính tay độc lập.

Đối chiếu Architecture.md 6.1: "Khi merge: chỉ lấy pages từ actual_start → actual_end của mỗi
chunk (BR-CHUNK-04)" — code mới (`actual_start`/`chunk.page_end` làm `actual_end` ngầm định) khớp
đúng tinh thần này, đúng thiết kế overlap gốc (overlap chỉ còn ý nghĩa "biên an toàn khi merge",
không phải context cho LLM — đã ghi rõ trong Architecture.md 6.1 phần "CẬP NHẬT Increment 4
review").

### 3. Test coverage

- `tests/test_chunk_merge.py` viết lại hoàn toàn, mock `_make_full_doc_mono_pdf` tạo **đủ
  `total_pages`** cho MỖI "chunk mono.pdf" (không còn chunk-scoped) — đúng khớp shape thật đã
  verify ở mục 1. Không phải mock kiểu khác nhưng vẫn tự bịa: mock chính là mô phỏng lại đúng
  golden fixture (tag "translated"/"original" theo range, giống cấu trúc file thật).
- `test_merge_chunk_pdfs_golden_fixture_real_pdf2zh_output` dùng **trực tiếp** 2 file golden-file
  thật (`tests/fixtures/pdf2zh/6page_range*_mono.pdf`) làm input, không qua mock — đã tự chạy lại
  (`pytest tests/test_chunk_merge.py -v`): **4 passed**, gồm cả test này.
- `tests/integration/test_job_orchestrator.py::_fake_pdf2zh_runner()` đã sửa đúng: mở
  `input_path` bằng PyMuPDF, đọc `total_pages` thật, tạo mono.pdf đủ số trang đó — không còn
  `n_pages=end-start+1` (giả định cũ sai). `test_run_job_completes_with_three_chunks` (90 trang,
  3 chunk) đã tự chạy lại: **PASSED**, `merged.page_count == 90` được assert trực tiếp trên file
  PDF thật (không chỉ tin `status=="completed"`) — đúng tinh thần Protocol 6 R6-03.

### 4. Bug #8 — giá OpenAI

`_PRICING_PER_MTOK` (`src/services/openai_provider.py`): `gpt-4o: (2.5, 10.0)`,
`gpt-4o-mini: (0.15, 0.60)` — đúng khớp con số Dev/QA đã dẫn. `estimate_cost()` đọc qua
`self._model` bằng `_cost_per_mtok()`, fallback `_DEFAULT_PRICING` (= giá `gpt-4o`, tức đắt hơn,
an toàn theo hướng không đánh giá thấp chi phí cho model lạ) thay vì hardcode 1 model.

Tự tính tay 1 ví dụ (không chỉ tin assertion sẵn có): input=30,925 token, output=5,000 token
(khớp đúng dữ liệu QA Vòng 5 đo thật) —
- `gpt-4o-mini`: `30925/1e6*0.15 + 5000/1e6*0.60 = 0.0046388 + 0.003 = 0.0076388`
- `gpt-4o`: `30925/1e6*2.5 + 5000/1e6*10.0 = 0.0773125 + 0.05 = 0.1273125`
- Tỉ lệ: `0.1273125 / 0.0076388 = 16.666...` = đúng `2.5/0.15 = 16.666...` — khớp chính xác con số
  16.67x QA Vòng 5 đã đo, và khớp `test_estimate_cost_gpt4o_mini_is_cheaper_than_gpt4o_for_same_tokens`.
  Đã tự chạy lại `pytest tests/test_openai_provider.py -v`: **5 passed**.
- `DeepSeekProvider` không bị ảnh hưởng — đã đọc code, xác nhận subclass override
  `estimate_cost()` riêng, không đi qua `_PRICING_PER_MTOK`.

**External contract checklist (CLAUDE.md R5-04)** cho `src/services/openai_provider.py`:
**External contract verified against real source: NO** — giá niêm yết lấy từ trí nhớ/public
pricing page tại thời điểm viết code (đúng như comment Dev tự ghi trong module docstring: "Reference
values below are public OpenAI pricing at time of writing — may change"), KHÔNG kèm link/trích dẫn
trực tiếp đã fetch qua WebFetch/WebSearch. Đây không phải lỗi nghiêm trọng (giá tiền không phải
CLI flag/schema — sai chỉ ảnh hưởng số hiển thị, không crash/mất dữ liệu, và không thuộc phạm vi
gốc đã gây ra Bug #2/#5 = hiểu sai API contract), nhưng theo đúng R5-04 phải ghi nhận tường minh
làm non-blocking suggestion: nên `WebFetch` trang pricing chính thức của OpenAI 1 lần để xác nhận
2 con số `$0.15/$0.60` và `$2.5/$10` còn đúng tại thời điểm release, ghi nguồn vào comment.

### 5. Regression toàn diện — tự chạy lại

- `.venv/bin/python -m ruff check src/`: **All checks passed.**
- Xoá `data/*.db*`, `.venv/bin/python -m pytest tests/ -q`: **180 passed**, 0 failed — khớp đúng
  CHANGELOG.
- `.venv/bin/python -c "from src.api.main import app"`: **OK**.
- Chạy riêng 3 file liên quan (`test_chunk_merge.py`, `test_openai_provider.py`,
  `test_job_orchestrator.py`) ở chế độ `-v`: toàn bộ **PASSED**, không có test nào silently
  skip/xfail.

### 6. Tìm thêm lỗi tương tự (Protocol 5 — giả định sai output shape của pdf2zh) — TÌM THẤY 1

Rà lại mọi chỗ code tiêu thụ `chunk.output_path`/`{stem}-mono.pdf` (grep toàn bộ
`src/core/job_orchestrator.py`), vì đây chính xác là bề mặt Bug #7 đã lộ:

- **`bilingual_merge.py::create_bilingual_pdf()`**: KHÔNG bị ảnh hưởng. Nó nhận `vi_pdf_path` =
  `merged_path` (file ĐÃ được `merge_chunk_pdfs()` cắt đúng, không phải mono.pdf thô của 1 chunk
  riêng lẻ) và `en_pdf_path` = `job.file_path` gốc (đọc đúng theo lineage table Architecture.md
  6.10.8, dòng "7." — không phải chunk output). Không có giả định shape nào về pdf2zh ở đây.
- **`font_shrink.py`**: bản thân module không giả định gì về số trang — nó nhận 1 `fitz.Page` đã
  mở sẵn từ caller và xử lý per-span. Giả định sai nằm ở **caller**, xem finding dưới.

**Finding mới [NON-BLOCKING nhưng nên sửa sớm]** — `src/core/job_orchestrator.py` dòng 550-554:

```python
with fitz.open(chunk.output_path) as doc:
    for page in doc:
        await font_shrink_page(page, overflow_entries)
    doc.saveIncr()
```

Đoạn này lặp `for page in doc` trên **TOÀN BỘ** `chunk.output_path` — sau fix Bug #7, đây chính
là mono.pdf **của cả tài liệu gốc** (đã verify ở mục 1), KHÔNG còn scoped theo `chunk.page_start`
`chunk.page_end` như code này ngầm giả định khi được viết (thời điểm đó `chunk.output_path` vẫn
còn được tin là chunk-scoped). Hệ quả với job nhiều chunk (vd 81 trang/3 chunk như QA Vòng 5):

1. **Lãng phí tính toán**: mỗi chunk tự chạy `font_shrink_page` trên toàn bộ N trang tài liệu
   thay vì chỉ ~40 trang của chính nó — với job 3 chunk là ~3x công việc thừa, tăng tuyến tính
   theo số chunk (job càng nhiều chunk, càng lãng phí).
2. **`OverflowReport` khả năng bị nhân bản / sai phạm vi**: `page.number` (dùng làm
   `OverflowEntry.page_number`, xem `src/postprocess/font_shrink.py` dòng 121) là số trang
   **absolute trong file mono.pdf** — tức trang absolute của TÀI LIỆU GỐC, không phải trang riêng
   của chunk. Với 3 chunk cùng xử lý qua 1 vòng lặp toàn bộ 81 trang, nếu có overflow thật xảy ra
   ở 1 trang X, cả 3 chunk (mỗi chunk sở hữu 1 bản copy riêng chứa trang X, vì mono.pdf luôn đầy
   đủ) đều có khả năng tạo ra `OverflowReport(page_number=X, ...)` — dữ liệu overflow hiển thị
   cho user (US-05 known limitations) có nguy cơ bị đếm/hiển thị trùng lặp lên tới 3 lần cho cùng
   1 trang thật, tuỳ trang đó thuộc bao nhiêu chunk (kể cả trang KHÔNG thuộc chunk đang xử lý,
   nếu trang đó tình cờ overflow trong bản dịch của chunk khác đã ghi vào cùng vị trí — không xảy
   ra ở đây vì mỗi chunk mở file RIÊNG, nhưng vẫn có rủi ro cho các trang trong vùng overlap được
   2 chunk liền kề cùng đếm).
3. **Đã grep xác nhận không có test nào assert số lượng/nội dung `OverflowReport`** rows
   (`grep -rn "OverflowReport" tests/` → 0 kết quả match từ khoá "overflow" ngoài import) — đây
   là 1 điểm mù thật sự, không phải suy đoán: bug này (nếu có overflow thật xảy ra) sẽ không bị
   bất kỳ test hiện tại nào bắt được.

**Không chặn merge lần này** vì: (a) không ảnh hưởng NỘI DUNG bản dịch cuối cùng — `merge_chunk_pdfs()`
vẫn cắt đúng phạm vi tuyệt đối bất kể `font_shrink_page` đã chạy thừa trên các trang khác; (b)
kịch bản QA Vòng 5 dùng câu ngắn 6 từ/trang, khó kích hoạt overflow thật nên chưa có bằng chứng
sống về nhân bản `OverflowReport`; (c) đây là hạng mục MỚI phát hiện, không phải Dev bỏ sót yêu
cầu đã giao — sửa ngay sẽ tốn thêm 1 vòng Dev↔QA trong lúc circuit breaker đang ở 4/5. Đề xuất:
mở 1 task riêng (không thuộc vòng fix Bug #7/#8 này) để giới hạn vòng lặp `font_shrink_page` theo
đúng `chunk.page_start`/`chunk.page_end` (trừ phần overlap-context để tránh đếm trùng ở biên), và
thêm ít nhất 1 test assert số lượng `OverflowReport` sinh ra cho 1 job nhiều chunk có overflow thật.

### Kết luận

**APPROVE** cho fix Bug #7 + Bug #8. Cả 2 đã được verify bằng golden-file thật (không tin lời kể),
logic merge mới đã tự tính tay đối chiếu đúng với kịch bản QA Vòng 5 và đúng thiết kế
Architecture.md 6.1, test coverage đủ (bao gồm 1 test dùng golden-file thật trực tiếp, không chỉ
mock), regression 180/180 pass, không phá vỡ bất kỳ luồng nào khác (`bilingual_merge.py` không bị
ảnh hưởng bởi thay đổi shape). 1 finding non-blocking mới (`font_shrink_page` lặp thừa trên toàn
bộ mono.pdf do hệ quả của chính fix Bug #7) đã được ghi lại rõ ràng theo đúng yêu cầu "liệt kê
không bỏ sót" — không đủ nghiêm trọng để REJECT lần này, nhưng PHẢI đưa vào backlog, không được
lặng lẽ bỏ qua.

---

## Cost Safety Lớp 0-3 — Review

- **Ngày**: 2026-09-04
- **Reviewer**: Reviewer (Sonnet)
- **Phạm vi**: Architecture.md 6.11 (Financial Safety, sau sự cố $6.50 tiền thật), CHANGELOG.md
  "Cost Safety — Lớp 0-3 (sau sự cố $6.50)". Mức độ nghiêm ngặt: TỐI ĐA — đây là code an toàn
  tài chính, sai sót có thể khiến user mất tiền thật lần nữa.

### Verdict: APPROVE

Toàn bộ 8 mục checklist đã được **tự kiểm tra độc lập** (không tin số Dev báo), không tìm thấy
lỗ hổng blocking nào. Chi tiết dưới đây.

### 1. Golden-file test — verify độc lập

Tự đọc `tests/fixtures/pdf2zh/cost_golden_howbakingworks.json` và
`estimate_job_cost_v2()`/`_estimate_input_tokens()` trong `src/core/cost_estimator.py`, tự tính
tay lại bằng script Python độc lập (không chạy `pytest`, tính trực tiếp từ công thức + dữ liệu
JSON):

```
source_text_chars = 699,103; segment_count = 2,989 (requests_openai_billed);
prompt_overhead_chars = 1,314 (prompt_chars_per_request)
input_tokens  = 699,103/4 + 2,989×1,314/4 = 1,156,662
output_tokens = 699,103×1.16/2.0           =   405,479
tổng ước tính                              = 1,562,141
tổng thật (openai_reported_tokens)         = 1,548,096
tỉ lệ = 1,562,141 / 1,548,096 = 1.0091×
```

**Kết quả tự tính khớp với báo cáo của Dev (1.009×)**, nằm trong khoảng bắt buộc **[1.0×, 1.6×]**
và ở phía an toàn (ước cao hơn thực tế, không thấp hơn). Đây là điều kiện quan trọng nhất của
toàn bộ section — nếu ra dưới 1.0× sẽ là blocking nghiêm trọng nhất có thể có, nhưng không xảy ra.

Cũng xác nhận `test_estimate_job_cost_v2_never_underestimates_golden_incident` dùng đúng
`requests_openai_billed` (không phải `requests_cached`) làm `segment_count` — lựa chọn đúng vì
đây là con số `_count_text_segments()` cần xấp xỉ trước job (bao gồm cả request lỗi/retry được
tính tiền thật).

### 2. Pre-flight gate (Lớp 2)

- **`POST /api/jobs`** (`create_job`, `src/api/routes/jobs.py`): gọi `_enforce_cost_gate()` ngay
  sau khi resolve provider, **TRƯỚC KHI** `Job(...)` được tạo và `session.add(job)`/commit. Xác
  nhận bằng đọc code trực tiếp — thứ tự đúng.
- **`POST /api/batches`** (`create_batch`): loop qua từng file trong batch gọi
  `estimate_translation_cost()`, cộng dồn `total_estimated`, so với `max_cost_per_batch_usd`
  **TRƯỚC** `_resolve_batch()` (nơi tạo `Batch` row) và trước loop tạo `Job` con. Đóng đúng lỗ
  hổng Architecture.md 6.11.7 #1 (`max_concurrent_files` chỉ giới hạn file song song, không giới
  hạn tiền).
- **`retry_job()`**: tự trace tay kỹ theo cảnh báo của Tech Lead — xác nhận `_enforce_cost_gate()`
  được gọi **TRƯỚC** khi `job.status = "queued"` và `_schedule_background(...)`. Dùng
  `job_cap_override=job.cost_cap_usd` đúng để tôn trọng override riêng của job. Không có đường
  nào trong `retry_job()` bỏ qua gate — không phải lỗ hổng như 2 lần trước (Protocol 5/6 đã từng
  bị bỏ sót ở đúng dạng chỗ nối này).
- **`confirm_cost` bypass**: là field `bool = False` trên từng request (`JobCreateRequest`,
  `BatchCreateRequest`, `RetryRequest`) — không phải cờ lưu trên Job/Settings, nên chỉ có hiệu
  lực **đúng 1 lần cho request đó**, không phải bypass vĩnh viễn. Xác nhận có
  `logger.warning(...)` rõ ràng khi bypass xảy ra (cả 3 chỗ: job/batch/retry), không im lặng.
- **HTTP 402 + không tạo row**: tự đọc `tests/integration/test_cost_gate_api.py` — đã có sẵn
  assertion đúng yêu cầu (`_job_row_count() == 0`, `_batch_row_count() == 0` sau khi bị 402, dùng
  `select(func.count()).select_from(Job/Batch)` đếm thật trong DB, không phải giả định). Không
  cần viết script riêng vì test đã làm đúng việc "đếm row trước/sau" — đã tự chạy lại toàn bộ
  suite (`pytest tests/ -q`) và xác nhận các test này pass thật (200 passed).

### 3. Running accumulator (Lớp 3) — trace tay theo Protocol 6

`job_orchestrator.py::run_job()` (dòng ~304-345): điểm check cost tích lũy nằm **SAU** khi
`_process_chunk()` hoàn thành (dòng 269-304, kể cả `progress_tracker.update()`), và **TRƯỚC**
điểm check `cancel_requested` (dòng 353-371) — đúng như spec yêu cầu, dùng cùng vị trí với
`cancel_requested` đã verify sống trước đó, không thêm điểm dừng mới. `completed_cost` tính từ
`sum(c.api_cost or 0.0 for c in chunks[:position])` — chỉ tính chunk đã thực sự hoàn thành, không
lẫn chunk đang chạy dở.

Status `cost_capped` được set riêng, code trả về `JobResult(status="cost_capped", ...)` ngay,
**không** rơi vào nhánh `except Exception` (không lẫn `failed`) và **không** đi qua nhánh
`cancel_requested` (không lẫn `cancelled`) — 2 nhánh này nằm tách biệt rõ trong code, đã đọc kỹ
xác nhận không có đường nào chồng lấn.

`BatchOrchestrator.run_batch()` (dòng 707-806): dùng `spent = {"total": 0.0}` + `asyncio.Lock`
dùng chung giữa các task `_run_one()`. Trace tay: nếu file 1 vượt cap giữa chừng, `spent["total"]`
được cộng dồn SAU khi file 1 hoàn thành (dòng 785-786) — các file đang chờ semaphore ở thời điểm
đó sẽ thấy `already_capped=True` khi tới lượt chạy và bị đánh dấu `cost_capped` ngay, không chạy
`JobOrchestrator`. **Hạn chế đã được ghi nhận đúng, không bị giấu**: vì `max_concurrent_files`
cho phép chạy song song, các file đã lọt qua kiểm tra và đang chạy cùng lúc với file vượt trần sẽ
được chạy hết (graceful, đúng triết lý "không force-kill giữa chừng" đã áp dụng nhất quán cho
cancel/cost_capped) — không phải lỗ hổng logic, là giới hạn granularity đã biết và có tài liệu.

### 4. `retry_job()` cho status `cost_capped`

- Resume đúng chunk dở dang: `run_job()` dùng `_load_or_create_chunks()` (kế thừa cơ chế
  BR-CHUNK-05 từ Increment 4, đã verify trước đó) — chunk `status == "completed"` được skip, chỉ
  chạy tiếp từ chunk dở dang. Test `test_run_job_resumes_after_cost_capped_like_a_cancelled_job`
  (`tests/integration/test_cost_capped_orchestrator.py`) verify trực tiếp hành vi này, assert
  `all(c.status == "completed" for c in chunks)` sau khi resume — không chỉ lý thuyết.
- Đi qua gate Lớp 2 lại từ đầu: đã xác nhận ở mục 2 — `retry_job()` gọi `_enforce_cost_gate()`
  trước khi set `status="queued"`, không phải tự động resume bỏ qua kiểm tra.

### 5. Data lineage (Protocol 6 R6-01)

`src/core/cost_gate.py::estimate_translation_cost()` gọi `build_prompt_text(glossary_manager,
project_id=batch_id, only_terms_present_in=full_text, max_glossary_entries=...)`
(`src/core/prompt_builder.py`), hàm này gọi tiếp `GlossaryManager.build_prompt_snippet()` THẬT
với `only_terms_present_in` = text thật trích từ chính file đang ước tính — không phải hằng số.
`prompt_overhead_chars = len(prompt_text) - len("${text}")` đo trên chuỗi prompt thật này. Xác
nhận đúng yêu cầu Architecture.md 6.11.5 bước 2→4 — soi dây nối "dễ đứt nhất" theo lời Tech Lead
đã được nối đúng, không dùng hằng số.

### 6. Frontend Lớp 0

Đọc `web/index.html` + `web/js/app.js` + `web/history.html` + `web/js/history.js`:

- Ô ước tính hiện **khoảng** `$X – $Y` (dùng `estimated_cost_usd` và `estimated_cost_usd_high`,
  `Y = X × 2.0`), không phải 1 số đơn — kèm câu "đây là khoảng ước tính, chi phí thật có thể cao
  hơn".
- Cảnh báo model đắt: `isExpensiveModel(f)` + `EXPENSIVE_OPENAI_MODELS = new Set(["gpt-4o"])`
  trong `app.js`, hiện "⚠ Model này đắt hơn ~16.7× so với gpt-4o-mini".
- Hiện số đoạn văn ước tính (`estimated_segment_count`) kèm giải thích "mỗi đoạn văn là 1 request
  LLM riêng".
- `cost_capped` có badge màu tím riêng (`bg-purple-100 text-purple-700`) phân biệt rõ với
  `failed`/`cancelled` ở cả `index.html` và `history.html`, kèm câu giải thích riêng "không phải
  lỗi, không phải bạn hủy".
- Kill switch "Dừng tất cả job" (`stopAllJobs()`) có mặt, tái dùng `cancel_requested`/`cancelJob`.

Toàn bộ 4 điểm bắt buộc của Lớp 0 đều có mặt.

### 7. Regression toàn diện

- `ruff check src/ tests/`: **All checks passed** (tự chạy lại).
- Xoá `data/*.db*`, chạy `pytest tests/ -q`: **200 passed**, 0 failed (tự chạy lại, không tin số
  Dev báo).
- `python -c "from src.api.main import app"`: OK, không lỗi import.

### 8. Xác nhận KHÔNG có API call thật

Đọc qua `tests/integration/test_cost_gate_api.py`, `tests/integration/
test_cost_capped_orchestrator.py`, `tests/test_cost_estimator.py`: toàn bộ dùng
`ClaudeProvider(api_key="sk-ant-fake")` hoặc provider giả tự định nghĩa trong test
(`_FakePricingProvider`, `_ExpensivePricingProvider`) — các API key giả chỉ chạm
`estimate_cost()` (thuần arithmetic, không có network call, xác nhận qua đọc
`src/services/claude_provider.py`). Mọi test để `confirm_cost=true` lọt qua gate đều monkeypatch
`_schedule_background` thành no-op — xác nhận trực tiếp trong code test, pipeline thật
(pdf2zh/LLM) không bao giờ chạy. `grep` toàn bộ `tests/` tìm `api.openai.com`/`api.anthropic.com`/
`httpx.AsyncClient()` trần không thấy call thật nào, chỉ có 1 dòng assertion so sánh chuỗi config
(`OPENAILIKED_BASE_URL == "https://api.anthropic.com/v1/"`), không phải lời gọi mạng.

### Kết luận

Không tìm thấy lỗ hổng blocking nào ở Lớp 0-3. Golden-file ratio đúng như báo cáo (1.009×, trong
khoảng an toàn [1.0×, 1.6×]). Cả 3 entry point (`POST /api/jobs`, `POST /api/batches`,
`retry_job()`) đều đi qua gate đúng thứ tự (trước khi tạo row / trước khi schedule). Running
accumulator đặt đúng vị trí, tách biệt rõ khỏi `failed`/`cancelled`. Batch-level cap hoạt động
đúng thiết kế "graceful" đã tài liệu hoá (không phải lỗ hổng ẩn). Data lineage cho glossary
overhead đúng, dùng số đo thật. Frontend đủ 4 điểm Lớp 0. Regression 200/200 pass. Không có API
call thật nào trong test.

**Non-blocking, ghi lại cho backlog (không chặn approve)**:
- Hạn chế granularity của Lớp 3 (1 chunk có thể vượt trần trước khi bị chặn) đã được Dev ghi rõ,
  đúng như Architecture.md 6.11.4 đã cảnh báo trước — đây là quyết định thiết kế đã chốt (Lớp 4
  `LLMMeteringProxy` mới chặn được ở granularity request), không phải thiếu sót của Dev.
- Gate Lớp 2 không chặn được job `pdf_scan` hiệu quả trước khi chạy (text chưa có do OCR chưa
  chạy) — đã ghi nhận đúng như Architecture.md 6.11.7 #3, được Lớp 3 bù đắp sau chunk đầu tiên.
  Chấp nhận cho v1.0, cần theo dõi ở increment OCR cost sau này.
- **QA phải tự chạy live verification thật trước khi release** (Architecture.md 6.11.8 gate
  release + R5-03/R6-03) — đặt trần thật thấp, chạy 1 job thật, xác nhận dừng đúng ở
  `cost_capped` và chi phí không vượt xa trần. Review này CHỈ xác nhận code đúng thiết kế + test
  mock, KHÔNG thay thế được yêu cầu live-run bắt buộc của QA.

---

## AIMD Adaptive Concurrency Controller (Architecture.md 6.12) — Review bước 6

- **Ngày**: 2026-09-05
- **Bối cảnh**: sau sự cố `Chunk 0 that bai: pdf2zh vuot qua timeout 3600s` (file "How baking
  works", 2026-09-04), điều tra ra `Pdf2zhRunner` chưa bao giờ truyền `--thread` cho pdf2zh
  (luôn chạy ở default 4 luồng của chính pdf2zh). Tech Lead thiết kế AIMD controller
  (Architecture.md 6.12.1-6.12.10, 7 bước), Dev implement tuần tự qua nhiều vòng, mỗi vòng đều
  qua Tech Lead xác nhận các điểm escalate (R5-02). Review này tập trung riêng bước 6
  (`docs/Architecture.md` 6.12.6 — xử lý riêng Claude/Ollama) sau khi bước 1,3,4,5 đã xong.

### Đối chiếu 3 điểm bắt buộc của 6.12.6

**Điểm 1 — Ollama fixed thread: ĐÃ ĐỦ (backend), THIẾU (UI) tại thời điểm review, đã đóng sau đó.**
`ollama_thread: int = 2` (`src/core/config.py:93`), nằm trong `SETTINGS_DB_OVERRIDABLE_FIELDS`
(`config.py:131`) — đúng ngoại lệ duy nhất của cả section 6.12. Wiring
(`job_orchestrator.py:786`) trả thẳng `self._settings.ollama_thread`, không đọc/tạo
`ConcurrencyState`. Test `test_ollama_uses_fixed_thread_and_never_touches_concurrency_state`
assert giá trị cụ thể, không chỉ `assert_called`. Tại thời điểm review, `web/settings.html`
KHÔNG có field `ollama_thread`/helper text — đã giao Dev task riêng đóng ngay sau, xác nhận
qua `pytest tests/ -q` = 240 passed.

**Điểm 2 — Claude khóa cứng floor, không tăng dù outcome=success: ĐÃ ĐỦ.**
`job_orchestrator.py:791-793`: `mode = "claude" if provider == "claude" else "aimd"`.
`_observe_chunk_outcome` (`job_orchestrator.py:835-841`) chỉ gọi `next_thread_count()` khi
`mode == "aimd"` — nhánh `claude` không có code nào tăng thread. Test
`test_claude_locked_at_floor_does_not_increase_on_success` assert cả thread truyền cho runner
VÀ `state.current_thread` không đổi VÀ `last_outcome == "success"` — đúng R6-02 (assert giá
trị, không chỉ assert_called). Đây là điểm rủi ro cao nhất của cả section, có test bảo vệ tốt
nhất.

**Điểm 3 — Gemini chạy AIMD bình thường ở floor riêng: ĐÚNG THEO CODE, thiếu test trực tiếp tại
thời điểm review, đã đóng sau đó.** Logic đúng: `mode="aimd"` áp dụng cho mọi provider khác
`claude` (gồm gemini), không có nhánh nào nhầm khóa Claude sang Gemini. Thiếu 1 test riêng xác
nhận trực tiếp — đã giao Dev bổ sung `test_gemini_aimd_increases_on_success` ngay sau, assert
`state.current_thread == floor(4) + 2 == 6`.

### Checklist R5-04

External contract verified against real source — **N/A**: đây là logic nội bộ AIMD (thuần
Python, không phải wrapper gọi trực tiếp external tool). Phần liên quan tới hành vi 429 thật
của Anthropic/Google qua OpenAI-compat layer (S5, S6) vẫn `[UNVERIFIED]` đúng như thiết kế —
code đã khóa đúng theo trạng thái unverified đó (Claude cố định thread, Gemini floor thận
trọng), không đi trước bằng chứng.

### Kết luận

Không có blocking issue. 2 gap non-blocking phát hiện tại thời điểm review (UI thiếu field,
thiếu 1 test Gemini) đã được đóng ngay trong cùng ngày, xác nhận qua `pytest tests/ -q` =
240 passed, `ruff check`/`format --check` sạch.

**Cập nhật 2026-09-06 (ghi lại ở đây để có sử liệu đầy đủ, không phải nội dung review gốc)**:
Sau review này, người dùng yêu cầu QA chạy gate release live thật (R5-03/R6-03) — xem
`docs/test-report.md` mục "QA Gate Release — Architecture.md 6.12" — PASS cả 3 tiêu chí trên
job thật với DeepSeek. Riêng floor Claude sau đó được người dùng chủ động nâng 4→8 làm **quyết
định chấp nhận rủi ro**, KHÔNG phải kết quả spike PASS (spike Claude/Gemini đều bị chặn do
thiếu API key thật) — ghi rõ trong `src/core/concurrency_controller.py` và Architecture.md
6.12.5, cần Reviewer/Tech Lead re-visit khi có key thật để verify chính thức.

---

## `BabeldocRunner` — Engine dịch PDF thứ hai (Architecture.md 6.14) — Iteration 1

- **Ngày**: 2026-09-05
- **Phạm vi**: `src/services/babeldoc_runner.py` (mới), `tests/test_babeldoc_runner.py` (mới),
  `tests/test_database_concurrency_state_migration.py` (mới), `tests/fixtures/babeldoc/` (golden
  files mới), sửa `src/core/config.py`, `src/core/concurrency_controller.py`,
  `src/core/job_orchestrator.py`, `src/models/concurrency_state.py`, `src/models/database.py`,
  `tests/integration/test_job_orchestrator.py`, `tests/integration/test_job_orchestrator_concurrency.py`,
  `docs/CHANGELOG.md`. Xác nhận `src/services/pdf2zh_runner.py` không bị sửa (diff = 0, theo
  `ls -la` timestamp và không match trong grep thay đổi).
- **Vòng lặp Dev↔Reviewer**: 1/3 (Protocol 3).

### 1. Golden files — R5-04 + Protocol 5 mục 3

Mở trực tiếp `tests/fixtures/babeldoc/`:
- `spike1_ok_stdout.log` / `spike1_ok_stderr.log` / `spike1_ok_requests.jsonl` (48 request that,
  header `user-agent: OpenAI/Python 3.8.0`, `x-stainless-*` — đúng shape client SDK `openai`
  thật, không phải data bịa tay).
- `spike2_429_stdout.log` / `spike2_429_stderr.log` / `spike2_429_requests.jsonl`: đã tự
  `grep -c "RateLimitError"` — **12 trên stdout, 0 trên stderr**, đúng khớp con số Architecture.md
  6.14.1 B10/B11 công bố (40 lần 429 ép buộc → 12 dòng log). Log có định dạng `rich`/`tenacity`
  bị bẻ dòng thật (không phải chuỗi viết tay đơn giản).
- `spike_output_listing.txt`: liệt kê đúng 2 file `...no_watermark.vi.mono.pdf` /
  `...no_watermark.vi.dual.pdf` — khớp pattern B7.

`tests/test_babeldoc_runner.py::test_translate_pages_counts_rate_limit_hits_from_golden_stdout`
đọc thẳng `spike2_429_stdout.log`/`stderr.log` qua `_read_fixture()`, không viết tay chuỗi giả —
đúng yêu cầu Protocol 5 mục 3. `test_golden_mono_output_filename_matches_live_spike_listing` đọc
`spike_output_listing.txt` để khẳng định pattern tên file, cũng không viết tay.

**External contract verified against real source: YES** (nguồn: `tests/fixtures/babeldoc/spike1_ok_*`
và `spike2_429_*`, capture từ 2 spike sống của Tech Lead trên `babeldoc` 0.6.4 cài thật, đối
chiếu số liệu 12/0/40 khớp Architecture.md 6.14.1 B10/B11 và pattern tên file khớp B7). Đây là câu
trả lời R5-04 cho `src/services/babeldoc_runner.py`.

### 2. Flag bắt buộc (6.14.2/6.14.3) — đọc `translate_pages()` dòng 151-183

Đủ cả 8 flag bắt buộc, hardcode, không optional: `--openai`/`--openai-base-url`/`--openai-api-key`/
`--openai-model` (149-168), `--pool-max-workers` (169-170), `--watermark-output-mode no_watermark`
(171-172), `--only-include-translated-page` (173), `--no-auto-extract-glossary` (174),
`--skip-scanned-detection` (175), `--split-short-lines` (176). `--custom-system-prompt` nhận
`prompt_file.read_text()` (nội dung), không phải path (181) — đúng 6.14.2. Không có nhánh nào bỏ
qua các flag này khi thành công — tất cả nằm ngoài mọi `if`, trừ `--custom-system-prompt` (đúng
đặc tả: bỏ qua khi `prompt_file is None`) và `--ignore-cache` (đúng đặc tả: tùy chọn).

### 3. `rate_limit_hits` — dòng 219

`len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))` — import trực tiếp
`RATE_LIMIT_LINE_RE` từ `src.core.concurrency_controller` (dòng 7), không viết regex mới. Đúng
yêu cầu 3 của brief.

### 4. Data lineage (R6-04) — tự trace bằng tay, không tin lời Dev

Trace biến `translation_source_path` xuyên suốt `job_orchestrator.py`:
- Gán tại dòng 259 (`= file_path` cho `pdf_digital`) hoặc dòng 262
  (`= await self._build_ocr_bridge(...)` cho `pdf_scan`).
- Truyền làm tham số vị trí thứ 3 vào `self._process_chunk(job, chunk, translation_source_path, ...)`
  tại dòng 352.
- Nhận vào tham số `source_path` của `_process_chunk` (dòng 649), dùng làm `input_path=source_path`
  tại lời gọi `self._translator_runner.translate_pages(...)` dòng 697-698.
- `self._translator_runner` (property dòng 224-237) là **điểm chọn engine duy nhất** — trả về
  `BabeldocRunner` hoặc `self._pdf2zh_runner` tùy `settings.pdf_translate_engine`, không có
  nhánh `if engine == ...` nào khác trong `_process_chunk()`.

Kết luận: `BabeldocRunner.translate_pages(input_path=...)` nhận **đúng** `translation_source_path`
(cầu nối searchable PDF cho `pdf_scan`, file gốc cho `pdf_digital`), **không phải** `job.file_path`
đọc lại — không tái diễn Bug #5. Xác nhận thêm bằng test tích hợp (mục 5).

### 5. R6-02 — test lineage có assert giá trị cụ thể, không chỉ `assert_awaited()`

`tests/integration/test_job_orchestrator.py::test_pdf_scan_babeldoc_engine_translates_bridge_not_original`
(dòng 502-540): tạo job `pdf_scan`, chạy qua `JobOrchestrator` thật với `babeldoc_runner` mock,
sau đó:
```python
expected_bridge = tmp_path / "processing" / job.id / "ocr_bridge" / "searchable.pdf"
for call in babeldoc_runner.translate_pages.await_args_list:
    assert call.kwargs["input_path"] == expected_bridge
    assert call.kwargs["input_path"] != Path(job.file_path)
```
Đây là assert **giá trị cụ thể** (bằng `expected_bridge`, khác `job.file_path`), đúng tinh thần
R6-02 — mạnh hơn `assert_called_with(input_path=translation_source_path)` nêu trong brief vì so
sánh cả 2 chiều (đúng cầu nối VÀ khác file gốc). `test_pdf_digital_still_uses_original` (dòng
543+) là companion no-regression cho nhánh `pdf_digital`. Cả 2 test đều nằm trong 261 test pass.

### 6. `ConcurrencyState` key migration — không mất dữ liệu AIMD cũ

`src/models/concurrency_state.py`: PK đổi thành `(engine, provider, model)`, `engine` có
`default="pdf2zh"`. `src/models/database.py:_migrate_concurrency_state_engine_key()` (dòng 74-107):
dùng đúng pattern SQLite "rebuild table" (rename → `create_all` tạo bảng mới đúng schema →
`INSERT ... SELECT 'pdf2zh', provider, model, ...` copy toàn bộ cột cũ → drop bảng cũ) — không
có `DROP` nào chạy trước khi `INSERT` xác nhận thành công, không mất bản ghi. Idempotent: no-op
nếu cột `engine` đã tồn tại (dòng 87-88), kể cả DB mới tinh (đã có sẵn `engine` từ `create_all`
đầu tiên). 3 test trong `tests/test_database_concurrency_state_migration.py` xác nhận trên SQLite
thật (temp-file, không mock): migrate + backfill đúng giá trị cũ, 2 engine cùng
`(provider, model)` coexist không đụng PK, và no-op trên schema mới. Đủ chứng minh không mất dữ
liệu AIMD đã học của pdf2zh hiện có.

### 7. Feature flag

`pdf_translate_engine: Literal["pdf2zh", "babeldoc"] = "pdf2zh"` (`config.py:118`) — default
đúng, **không** nằm trong `SETTINGS_DB_OVERRIDABLE_FIELDS` (đối chiếu danh sách dòng 137-183,
không thấy field này). Điểm chọn engine: property `_translator_runner` (mục 4) là **1 chỗ duy
nhất** — grep `pdf_translate_engine` trong `job_orchestrator.py` ra thêm 3 chỗ khác (dòng 327,
466, 670, 815) nhưng đều KHÔNG phải nhánh gọi `translate_pages`: dòng 327/670 chỉ đọc string để
làm khóa `ConcurrencyState`/tham số `_resolve_thread`, dòng 466 chỉ nội suy tên engine vào thông
báo lỗi, dòng 815 chọn bảng floor (`BABELDOC_THREAD_FLOOR` vs `ADAPTIVE_THREAD_FLOOR`) — đây là
hành vi AIMD đặc tả rõ ở 6.14.5, không phải nhánh dịch trùng lặp. Không có `if engine ==` nào rải
trong luồng gọi `translate_pages`.

### 8. `_resolve_openai_compat()` — điểm Dev tự flag

Đối chiếu từng provider với Architecture.md 6.14.1 B14 và các nguồn đã có:
- `openai`/`openailiked` (claude qua compat): đọc thẳng 3 key có sẵn trong `service.envs` —
  không suy đoán gì, đúng dữ liệu `Pdf2zhServiceMapper` đã tạo.
- `gemini`: dùng `_GEMINI_OPENAI_COMPAT_BASE_URL` = đúng giá trị đã verify sống ở B14 (WebFetch
  doc chính thức Google, đã đối chiếu khớp shape client babeldoc phát ra ở B6) — **verified**,
  không phải suy đoán.
- `deepseek`: hardcode `_DEEPSEEK_BASE_URL = "https://api.deepseek.com"`, trùng
  `Settings.deepseek_base_url` (`config.py:29`) đã có sẵn và qua review trước. **Vấn đề**:
  `deepseek_base_url` NẰM TRONG `SETTINGS_DB_OVERRIDABLE_FIELDS` (`config.py:145`) — tức đây là
  1 giá trị người dùng CÓ THỂ đổi qua DB override. `_resolve_openai_compat()` không nhận
  `Settings` làm tham số nên không thể đọc lại giá trị đã override — nếu người dùng đổi
  `deepseek_base_url` (ví dụ trỏ qua proxy nội bộ), nhánh `pdf2zh` sẽ theo giá trị mới nhưng
  nhánh `babeldoc` vẫn dùng hằng số hardcode cũ → 2 engine lệch nhau âm thầm. Đây đúng là kiểu
  "second source of truth" mà Architecture.md 6.14.3 cảnh báo (dù đoạn đó nói về bảng mapping
  provider→field, không nói thẳng về giá trị field), và đúng root-cause pattern CLAUDE.md dự án
  này đã liệt kê 2 lần trước (giá trị đúng tại thời điểm viết nhưng có thể trôi so với nguồn thật
  theo thời gian). **Không phải lỗi logic sai ngay bây giờ** (giá trị hiện khớp), nên đây là
  **non-blocking suggestion**, không phải lý do reject.
- `ollama`: suy ra `{OLLAMA_HOST}/v1` — Architecture.md đã tự đánh dấu `⚠️ ASSUMED` cho toàn bộ
  đường Ollama (chưa cài được để verify), và code không hề che giấu điều đó thành "verified" —
  đúng kỷ luật. Chuỗi api-key giả `"ollama"` là placeholder hợp lý cho 1 đường đã biết là chưa
  verify.

Kết luận điểm 8: không có giả định nào bị che giấu thành "verified" khi chưa verify. Riêng
`_DEEPSEEK_BASE_URL` là smell đáng sửa nhưng không sai — xem Non-blocking suggestions.

### 9. Test suite

`uv run pytest -q` → **261 passed** (khớp báo cáo của Dev), `uv run ruff check` trên toàn bộ file
liên quan → sạch. Không có test nào skip/xfail trong phạm vi review.

### Non-blocking suggestions

1. **`_DEEPSEEK_BASE_URL` hardcode trùng `Settings.deepseek_base_url` overridable** (mục 8) —
   nên sửa `_resolve_openai_compat()` nhận thêm `settings: Settings` và đọc
   `settings.deepseek_base_url` thay vì hằng số riêng, để tránh 2 nguồn sự thật có thể trôi nhau
   khi ai đó đổi override qua DB/UI. Rủi ro thấp (DeepSeek base_url hiếm khi bị đổi), không chặn
   increment này.
2. **`⚠️ ASSUMED` Gemini/Ollama end-to-end thật** (Architecture.md 6.14.1) vẫn chưa được verify
   sống qua `JobOrchestrator` — đúng phạm vi của QA gate 6.14.6 (R5-03/R6-03), không phải việc
   của Dev/Reviewer ở increment implement này, nhắc lại để không quên trước khi release.

### Checklist R5-04 (tổng hợp)

`src/services/babeldoc_runner.py`: **YES** (nguồn: `tests/fixtures/babeldoc/spike1_ok_*` +
`spike2_429_*`, đối chiếu số liệu 12/0/40 và pattern tên file khớp Architecture.md 6.14.1
B7/B10/B11).

### Kết luận

**APPROVE.** Không có blocking issue. Lineage (R6-04), flag bắt buộc, `rate_limit_hits` tái sử
dụng regex, migration `ConcurrencyState`, feature flag default/scope, và golden file backing đều
đúng đặc tả Architecture.md 6.14 và đúng nguồn xác thực đã trích dẫn (không suy đoán mới). 1
non-blocking suggestion (`_DEEPSEEK_BASE_URL` nên đọc từ `Settings` thay vì hardcode) ghi lại cho
Dev cân nhắc, không cần sửa trước khi merge. QA gate 6.14.6 (live E2E 2 engine, R5-03/R6-03) vẫn
là điều kiện bắt buộc riêng trước khi đổi default hoặc release — review này KHÔNG thay thế yêu
cầu đó.

---

# Review Report — 2026-09-06

## Phạm vi review

Toàn bộ working tree chưa commit, 2 nguồn:
- Tech Lead: `src/services/babeldoc_runner.py`, `tests/test_babeldoc_runner.py`,
  `src/core/config.py`, `tests/integration/test_settings_api.py`,
  `docs/CHANGELOG.md`, `pyproject.toml`, `uv.lock`.
- PM (tính năng UI theo yêu cầu trực tiếp user): `src/api/routes/upload.py`,
  `src/api/routes/jobs.py`, `src/api/routes/download.py`, `web/index.html`,
  `web/history.html`, `web/js/app.js`, `web/js/history.js`,
  `tests/integration/test_delete_and_download_naming.py`.

## Kết quả tự chạy lại (không tin số báo cáo trước)

- `.venv/bin/python -m pytest tests/ -q` → **281 passed** (khớp con số PM báo).
- `.venv/bin/ruff check <các file đổi>` → All checks passed.
- `.venv/bin/ruff format --check <các file đổi>` → 7/8 file đã format đúng;
  `tests/integration/test_settings_api.py` cần reformat ở 2 chỗ — **không phải
  do diff của session này gây ra** (drift có sẵn từ trước, dòng không nằm
  trong hunk mới), nhưng vẫn tồn tại trong working tree → non-blocking.

## R5-04 checklist (External Dependency Verification)

**`src/services/babeldoc_runner.py`** — External contract verified against
real source: **YES**.
- Lý do: đọc trực tiếp source `babeldoc/translator/translator.py` (dòng cụ thể
  324, 253-255) để xác nhận `max_tokens=2048` hardcode và cú pháp
  `--openai-thinking`; gọi thật API DeepSeek (`api.deepseek.com`) và Gemini
  OpenAI-compat endpoint với batch thật ~30 đoạn để đo `reasoning_tokens`,
  `finish_reason`, và test `json.loads()` — số liệu đo được (thinking=0 vs
  2104 vs 1963, 404 cho model cũ) được ghi lại nguyên văn trong docstring
  `_thinking_args`/`_GEMINI_VERIFIED_SAFE_MODELS`. Đây đúng tinh thần R5-02
  (spike verify trước khi implement đầy đủ) chứ không phải suy đoán từ trí
  nhớ. Tôi (Reviewer) không tự gọi lại API thật để re-verify con số (không có
  key trong phiên review), nhưng bằng chứng được trích dẫn đủ cụ thể (số liệu
  đo, dòng source, ngày verify) để phân biệt với "lời kể miệng không nguồn" —
  đúng yêu cầu R5-01.

**`src/api/routes/upload.py`, `jobs.py`, `download.py`** — N/A cho R5-04 (đây
không phải wrapper gọi external tool/service, chỉ là CRUD nội bộ trên
DB/filesystem của chính app).

## Đánh giá theo Protocol 6 (Data Lineage)

- **R6-04 (trace tay orchestrator)**: `DELETE /api/jobs/{job_id}` không phải
  orchestrator gọi tuần tự external tool, nhưng áp dụng tinh thần tương tự:
  đã tự grep `foreign_key="jobs.id"` toàn repo → chỉ có `Chunk` và
  `OverflowReport` tham chiếu `jobs.id`; cả hai đều được xoá tay đúng trước
  khi xoá `Job` (không có SQLite `ON DELETE CASCADE`, code tự xoá thủ công —
  khớp docstring). Guard `_ACTIVE_JOB_STATUSES` (6 giá trị) khớp CHÍNH XÁC với
  comment enum đầy đủ trong `src/models/job.py` (9 giá trị: 6 active + 4
  terminal, trừ đi 1 trùng "completed" tính cả 2 phía) — không thiếu status
  nào, đã tự đối chiếu bằng grep `job.status = "..."` trên toàn bộ
  `job_orchestrator.py`/`jobs.py`.
- Phát hiện 1 lỗ hổng data-lineage nhỏ: **không đồng bộ lại `Batch` counters**
  khi xoá 1 `Job` thuộc batch — xem finding chi tiết trong danh sách issue
  (non-blocking, không phải data corruption, chỉ là con số đếm hiển thị sai).
- **R6-02 (test assert giá trị cụ thể, không chỉ assert "đã gọi")**: cả 2 phía
  đều tuân thủ tốt:
  - `tests/test_babeldoc_runner.py`: assert vị trí cặp flag/value cụ thể
    (`args.index("--openai-thinking") + 1 == "disabled"`), assert model string
    cụ thể trong exception message, assert `create_exec.assert_not_awaited()`
    trước khi raise — không chỉ `assert_called()`.
  - `tests/integration/test_delete_and_download_naming.py`: assert số lượng
    row cụ thể còn lại sau xoá (`(0, 0, 0)`), assert tên file tải về có đúng
    timestamp format bằng regex, assert file thật trên đĩa còn/mất — không
    chỉ tin status code.

## Security / correctness khác đã kiểm tra

- Path traversal qua `file_id`/`job_id`: cả hai đều là UUID server sinh, không
  nhận trực tiếp làm path segment tuỳ ý mà phải match được row đã tồn tại
  trong DB (`job_id`) hoặc sidecar JSON đã tồn tại (`file_id`) trước khi bất kỳ
  thao tác xoá nào chạy — không có cách nào để giá trị "độc hại" (`../../etc`)
  vượt qua bước lookup/exists-check này. Không có validate format tường minh
  (regex UUID) trên input, nhưng rủi ro thực tế thấp vì Starlette route
  matching cho path segment mặc định loại `/` (không thể tạo request path
  chứa `/` để traversal qua nhiều cấp thư mục). Không blocking.
- `web/js/app.js` `removeFile()`: thứ tự xoá Job trước rồi mới xoá upload file
  là đúng — nếu xoá Job thất bại (400 do job đang active) thì hàm return sớm,
  không tiếp tục xoá file gốc và không xoá khỏi `this.files` — không có race
  condition rõ ràng.
- Tên file cũ `translated_vi.pdf`/`{stem}_vi.pdf` chỉ là tên file NỘI BỘ trên
  đĩa (`data/outputs/{job_id}/...`) và tên hiển thị Content-Disposition khi
  tải — cả 2 nơi đều KHÔNG bị đổi ở đường dẫn lưu trữ, chỉ thêm hậu tố
  timestamp vào tên file trả về trình duyệt → không phá hợp đồng nào khác
  trong `job_orchestrator.py`/Architecture.md (đã grep xác nhận).

## Danh sách issue

Đã gửi qua `ReportFindings` (3 mục, tất cả non-blocking):
1. `uv.lock` version (1.2.4) lệch với `pyproject.toml` (1.2.5) — chạy `uv lock`
   để đồng bộ.
2. `tests/integration/test_settings_api.py` chưa qua `ruff format` (drift có
   sẵn, không phải do diff lần này).
3. `DELETE /api/jobs/{job_id}` không đồng bộ lại `Batch.total_files` /
   `completed_files` / `failed_files` khi job xoá thuộc về 1 batch — counter
   của batch sẽ sai sau khi xoá (không gây mất dữ liệu, chỉ sai số hiển thị).

Không phát hiện issue blocking nào (không có security vulnerability, không có
data lineage bug gây mất dữ liệu, không có external contract chưa verify mà
vẫn được implement như thật).

## Kết luận

**APPROVE** — cho phép merge/tiếp tục. 3 issue trên là non-blocking, có thể
xử lý ở increment sau hoặc kèm 1 fix nhỏ (đặc biệt khuyến nghị chạy `uv lock`
trước khi release, vì lệch version lock file dễ gây nhầm lẫn về sau).

---

# Review Report — 2026-09-06 (Iteration 2 — verify fix cho 3 issue của Iteration trước)

## Phạm vi review

Chỉ phần Dev vừa sửa (3 issue non-blocking từ vòng review trước ở trên), không review lại từ
đầu toàn bộ đợt thay đổi lớn (Tech Lead babeldoc fix + PM 2 tính năng UI) — phần đó đã APPROVE.

## Đã tự chạy lại (không tin số Dev báo)

```
.venv/bin/python -m pytest tests/ -q  → 284 passed  (281 vòng 1 + 3 test mới cho batch counter)
.venv/bin/ruff check <8 file .py đổi>  → All checks passed
.venv/bin/ruff format --check <8 file .py đổi>  → 8 files already formatted (bao gồm test_settings_api.py — issue #2 đã hết)
```

## Issue #1 — `uv.lock` version sync

`git diff uv.lock` chỉ có đúng 2 dòng: `version = "1.2.3"` → `"1.2.5"` cho package
`bb-translation` (`pyproject.toml` cũng 1.2.5). Không có dependency nào khác bị bump/hạ version.
**Đúng.**

## Issue #2 — format lại `test_settings_api.py`

`git diff tests/integration/test_settings_api.py` có 2 hunk thuần whitespace (tách
`client.put(...)` thành multi-line) + 1 hunk đổi
`assert effective.gemini_model == "gemini-2.5-pro"` → `"gemini-3.1-flash-lite"` kèm comment giải
thích. Hunk thứ 3 không phải whitespace nhưng đã đối chiếu `git diff src/core/config.py` xác nhận
default `gemini_model` đã đổi (do Google trả 404, verified ở vòng review trước) — đây là hệ quả
bắt buộc của thay đổi Tech Lead đã approve trước đó, không phải Dev tự ý đổi assertion ngoài
phạm vi. **Đúng.**

## Issue #3 — `delete_job()` đồng bộ `Batch` counters (trọng tâm)

Đã tự đọc `BatchOrchestrator.run_batch()` (`src/core/job_orchestrator.py:1080-1089`):
```python
completed = sum(1 for r in job_results if r.status == "completed")
failed = sum(1 for r in job_results if r.status == "failed")
batch.completed_files = completed
batch.failed_files = failed
```
Chỉ 2 status `"completed"`/`"failed"` được đếm; `"cost_capped"` và `"cancelled"` không rơi vào
bên nào. `delete_job()` (`src/api/routes/jobs.py:697-711`) khớp **chính xác**: chỉ giảm
`completed_files` khi `job.status == "completed"`, chỉ giảm `failed_files` khi
`job.status == "failed"` — không có case nào coi `cancelled`/`cost_capped` là `failed`.

### Race condition — CÓ THẬT, ghi lại tường minh (không im lặng bỏ qua theo R6)

`run_batch()` không cộng dồn incremental mà **ghi đè toàn bộ** `batch.completed_files`/
`failed_files` ở cuối, tính lại từ `job_results` (danh sách in-memory nó tự thu thập trong lần
gọi đó, không đọc lại DB). Nếu user gọi `DELETE /api/jobs/{job_id}` cho 1 job đã `completed`
**trong lúc batch vẫn đang chạy** các job khác (guard `_ACTIVE_JOB_STATUSES` chỉ chặn theo status
của CHÍNH job đó, không chặn theo status của batch), trình tự có thể là:
1. `delete_job()` đọc `batch.completed_files=N`, ghi `N-1`, commit.
2. `run_batch()` (đang chạy song song) sau đó chạy xong, ghi đè `batch.completed_files = completed`
   (tính từ `job_results` nội bộ, không biết job đã bị xoá) — **giá trị `N-1` bị mất tác dụng**,
   quay lại như chưa xoá.

Race thật, không phải suy đoán — do `run_batch()` dùng "recompute + overwrite" thay vì
"increment/decrement", hai writer ghi cùng field mà không có coordination. Impact: chỉ sai số
hiển thị (không mất Job/Chunk row, không crash), window hẹp (chỉ trong lúc batch đang chạy, tự
"lành" sau khi batch xong vì `run_batch()` chỉ overwrite đúng 1 lần ở cuối).

**Đề xuất: non-blocking**, khuyến nghị fix bằng cách đổi `run_batch()` sang increment thay vì
overwrite, hoặc chỉ overwrite nếu batch chưa bị ai sửa counter kể từ lúc bắt đầu — để lại cho
increment sau.

### Clamp `max(0, ...)`

Có thật trong code (`batch.completed_files = max(0, batch.completed_files - 1)`,
`jobs.py:715,718`). Cần thiết trong tình huống race ở trên: nếu `run_batch()` overwrite counter
xuống thấp hơn thực tế sau đó lại có thêm 1 lần xoá dựa trên giá trị đã sai, phép trừ có thể chạm
0 hoặc âm nếu không clamp — phòng thủ hợp lý, không thừa.

### Test mới

`tests/integration/test_delete_and_download_naming.py` có 3 test assert **giá trị cụ thể**
(`test_delete_completed_job_decrements_batch_completed_files` assert `== 1` sau khi giảm từ 2;
`test_delete_failed_job_decrements_batch_failed_files` tương tự;
`test_delete_job_without_batch_does_not_error` cho case `batch_id is None`) — đúng tinh thần
R6-02, không chỉ assert status code 204.

## Kết luận

**APPROVE.**

Danh sách issue:
- Non-blocking (đã fix đúng, không còn vấn đề): issue #1, #2 gốc.
- Non-blocking (mới phát hiện ở vòng này, cần ghi vào report, không được bỏ qua): race condition
  giữa `delete_job()` decrement và `run_batch()` overwrite counter khi xoá job giữa lúc batch còn
  đang chạy các job khác — khuyến nghị đổi `run_batch()` sang cộng dồn/increment thay vì tính lại
  từ đầu, xử lý ở increment sau.

File liên quan: `src/api/routes/jobs.py` (dòng ~672-717),
`src/core/job_orchestrator.py` (dòng 1080-1089),
`tests/integration/test_delete_and_download_naming.py`,
`tests/integration/test_settings_api.py`, `uv.lock`, `pyproject.toml`.
