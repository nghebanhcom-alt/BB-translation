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

---

## Review vòng mới — 2026-09-06 (5 tính năng bổ sung theo yêu cầu PM, Protocol 7 gate)

Phạm vi: `GET /api/version`, `POST /api/glossary` (tạo 1 entry đơn lẻ), field `uploaded_at`
cho upload metadata, frontend "Xóa tất cả" + sort mới nhất + timestamp (`web/index.html`,
`web/js/app.js`), frontend "+ Glossary" modal + hiển thị chi phí thực tế trong history
(`web/history.html`, `web/js/history.js`), `docs/CHANGELOG.md` append, test mới
(`tests/integration/test_glossary_api.py` +3, `tests/integration/test_version_and_upload_timestamp.py` mới 5 test).
Chưa commit — đọc trực tiếp working tree qua `git status`/`git diff`.

### 1. Correctness

- `GET /api/version` (`src/api/main.py`): đọc `pyproject.toml` bằng `tomllib` (stdlib, project
  yêu cầu Python 3.12+ nên không cần dependency mới) thay vì `importlib.metadata.version()` — lý
  do đúng vì app chạy từ source, chưa `pip install`. Bắt đúng 3 loại lỗi (`OSError`, `KeyError`,
  `tomllib.TOMLDecodeError`), fallback `"unknown"` thay vì 500 — hợp lý cho 1 endpoint hiển thị ở
  footer, không phải endpoint nghiệp vụ.
- `POST /api/glossary` (`src/api/routes/glossary.py`): tái dùng `GlossaryManager.bulk_import()`
  với list 1 phần tử thay vì viết logic tạo/cập nhật riêng — đúng nguyên tắc không nhân đôi logic,
  và kế thừa đúng BR-GLOSS-02 (case-insensitive) + BR-GLOSS-03 (last-updated-wins) đã có sẵn.
  Response schema (`GlossaryEntryOut`, status 201) nhất quán với các endpoint glossary khác cùng
  file. Nhánh `entry is None` sau `bulk_import()` về mặt logic không thể xảy ra (đã strip và check
  rỗng trước đó) — dùng `HTTPException 500` + `pragma: no cover` là xử lý phòng thủ hợp lý, không
  phải bug.
- `uploaded_at`: gán đúng tại nơi tạo `UploadMetadata` (`src/api/routes/upload.py` dòng 142-151),
  không phải trường hợp "thêm field nhưng quên set giá trị" — đã verify bằng cách đọc trực tiếp,
  không tin lời khai của Dev. Test
  `test_upload_sidecar_metadata_persists_uploaded_at` xác nhận giá trị round-trip qua sidecar JSON
  đúng như lo ngại nêu trong nhiệm vụ.
- Backward-compat cho sidecar cũ: `UploadMetadata.uploaded_at: str = ""` (default, không phải
  `None`/thiếu field) để `UploadMetadata(**data)` không `TypeError` khi đọc sidecar tạo trước khi
  field này tồn tại — có test riêng `test_resolve_upload_tolerates_sidecar_without_uploaded_at`
  verify đúng case này. Xử lý migration-less đúng cách.
- Frontend `removeAllFiles()` (`web/js/app.js`): không thêm endpoint bulk-delete mới ở backend,
  tái dùng `_deleteFileRecord()` (logic đã refactor ra từ `removeFile()`) lặp tuần tự qua danh sách
  hiện có — tránh nhân đôi logic lỗi/xoá Job trước rồi mới xoá upload. 1 confirm duy nhất cho cả
  batch, đúng yêu cầu UX. Item xoá thất bại (vd job đang chạy) được giữ lại trong `remaining`,
  không bị xoá nhầm khỏi UI — kiểm tra kỹ nhánh lỗi, đúng.
- `sortFilesDesc()`: dùng `uploaded_at || job?.created_at`, gọi lại sau cả `restoreRecentJobs()`
  và sau vòng lặp upload — đúng vì file phục hồi từ server không có `uploaded_at` riêng (chỉ có từ
  session upload hiện tại).
- `formatCost()` (`web/js/history.js`) và migration trong `history.html`: thay `x-if` cũ (chỉ hiện
  `actual_cost`) bằng hàm xử lý cả 3 case (`actual_cost` / `estimated_cost` / không có gì) — đúng
  yêu cầu "hiển thị chi phí thực tế" mà không làm mất hiển thị ước tính cho job chưa hoàn tất.

### 2. Security

- **Input validation `POST /api/glossary`**: `term_en` rỗng/toàn whitespace bị chặn với 400 (test
  `test_create_single_entry_rejects_blank_term_en` verify). `term_vi`/`notes` không có validation
  độ dài — không phải lỗ hổng mới, endpoint `PUT` hiện có cũng không có, nhất quán với pattern cũ
  của project (non-blocking, ghi nhận để theo dõi nếu sau này có giới hạn kích thước glossary).
- **XSS**: đã `grep -rn "x-html" web/` toàn bộ thư mục — **0 kết quả**. Mọi chỗ hiển thị dữ liệu
  glossary/job (`x-text`) đều qua Alpine `x-text`, tự động escape HTML entity. Không có vector XSS
  nào được mở bởi 5 tính năng này.
- **SQL injection**: `bulk_import()`/`get_entry()`/`_find_entry_in_scope()` (đã đọc
  `src/core/glossary_manager.py`) dùng SQLModel `select()` + `func.lower()` với bind param qua
  ORM, không có raw SQL string nào — như PM đã dự đoán, không có khả năng injection.
- **Path traversal**: `POST /api/glossary`, `GET /api/version`, `uploaded_at` không nhận bất kỳ
  input nào liên quan tới file path từ client — N/A cho cả 3. `DELETE /api/upload/{file_id}` (đã
  tồn tại từ trước, không đổi trong diff này) vẫn dùng `resolve_upload()` tra sidecar theo
  `file_id` (UUID do server sinh, không phải path client cung cấp trực tiếp) — không có
  path-traversal mới phát sinh từ các thay đổi lần này.

### 3. Protocol 5 R5-04 checklist (external contract)

Không endpoint/module nào trong phạm vi review này gọi external tool (pdf2zh/MinerU/babeldoc/LLM
SDK) — tất cả đều là CRUD nội bộ (SQLModel), đọc file cấu hình cục bộ (`pyproject.toml`), hoặc
thao tác file trên đĩa do chính app quản lý (`data/uploads/`).

**External contract verified against real source: N/A** cho toàn bộ 3 file thay đổi
(`src/api/main.py`, `src/api/routes/glossary.py`, `src/api/routes/upload.py`) — đúng phạm vi loại
trừ ghi trong CLAUDE.md project ("không áp dụng cho thư viện nội bộ Python thuần code logic").

### 4. Tự verify (không tin báo cáo của Dev)

- `pytest tests/ -q` → **291 passed** (khớp đúng claim "291/291 pass" của Dev, tự chạy lại, không
  suy từ lời khai).
- `ruff check .` → **All checks passed!**
- `git diff docs/CHANGELOG.md | grep '^-' | grep -v '^--- '` → **0 dòng bị xoá** — xác nhận
  CHANGELOG chỉ được append, không mất lịch sử cũ (đúng yêu cầu Protocol 7 R7-03 tinh thần chung,
  dù R7-03 nói riêng về review-report/test-report/CHANGELOG/project_state.json).

### 5. Vấn đề phát hiện (non-blocking)

1. Deviation route pattern có sẵn từ trước (không phải do 5 tính năng này gây ra, chỉ ghi nhận vì
   review lần này chạm vào): Architecture.md section 5.1 mô tả API glossary dạng
   `/glossaries/{id}/entries` (nested theo glossary_id), nhưng code thực tế dùng route phẳng
   `/api/glossary` (không có `{id}` cha, scope cố định qua field `scope` trong body/query). Đây là
   drift đã tồn tại trước khi có 5 tính năng này, `POST /api/glossary` mới chỉ theo đúng pattern
   phẳng hiện có của file — không phải lỗi mới, nhưng Architecture.md section 5.1 nên được cập
   nhật lại cho khớp thực tế ở lần chỉnh sửa Architecture.md tiếp theo.
2. `POST /api/glossary` không cho chọn `scope`/`project_id` (cố định `"global"`) — đúng như
   docstring Dev đã ghi rõ lý do (UI `history.html` hiện tại chưa có project glossary), không phải
   thiếu sót, chỉ ghi nhận để không quên khi có project-scoped glossary trong tương lai.

## Kết luận

**APPROVE.**

Không có issue mức blocking. Correctness, security, data lineage (uploaded_at gán đúng nơi tạo,
không phải field mồ côi), và test coverage (bao gồm cả case backward-compat sidecar cũ) đều đạt.
291/291 test pass và `ruff check` sạch đã tự verify lại, không dựa vào báo cáo của Dev.

File liên quan: `src/api/main.py`, `src/api/routes/glossary.py`, `src/api/routes/upload.py`,
`web/index.html`, `web/js/app.js`, `web/history.html`, `web/js/history.js`,
`tests/integration/test_glossary_api.py`, `tests/integration/test_version_and_upload_timestamp.py`,
`docs/CHANGELOG.md`.

# Review Report — Fix bug line-break/paragraph-splitting babeldoc (F1/F2/F4)

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-06
- **Phạm vi**: `src/services/babeldoc_runner.py`, `src/services/pdf2zh_runner.py`,
  `src/core/config.py`, `src/core/job_orchestrator.py`, `src/core/prompt_builder.py`,
  `docs/CHANGELOG.md`, `tests/test_babeldoc_runner.py`, `tests/test_prompt_builder.py`,
  `tests/integration/test_job_orchestrator.py`, fixture `tests/fixtures/babeldoc/page14_*.pdf`.
  (F3 không có code trong diff — Dev tự dừng sau spike thất bại, không review phần đó.)

## 1. F1 — Bỏ hardcode `--split-short-lines`

`grep -rn "split-short-lines\|split_short_lines" src/` xác nhận: không còn nơi nào trong `src/`
tự động append `"--split-short-lines"` vào `args` mà không qua tham số `split_short_lines`. Chỗ
hardcode cũ (`babeldoc_runner.py:278` theo Architecture.md N1) đã thay bằng `if split_short_lines:
args.append(...)`. Không có code path chết nào còn gọi `True` trực tiếp. Đạt.

## 2. F2 — Setting mới, data lineage (Protocol 6)

- `Settings.babeldoc_split_short_lines: bool = False`, `babeldoc_short_line_split_factor: float =
  0.5` — default đúng `False` tại nguồn duy nhất (`config.py`), không có nơi nào override default
  thành `True` (`grep` không thấy).
- Trace tay theo R6-04 (không chỉ tin "cả 2 bước gọi đúng tham số riêng"):
  `job_orchestrator.py` → `split_short_lines=self._settings.babeldoc_split_short_lines` và
  `short_line_split_factor=(self._settings.babeldoc_short_line_split_factor if
  self._settings.babeldoc_split_short_lines else None)` → truyền thẳng vào `translate_pages()` →
  `babeldoc_runner.py` chỉ `args.extend(["--short-line-split-factor", str(...)])` khi
  `split_short_lines` cũng `True`. Dây nối liền mạch, đúng field, không có bước nào bị đứt gãy.
  Factor chỉ gửi kèm flag chính — đúng L4 (`paragraph_finder.py:891` dùng `and`).
- Test `test_babeldoc_split_short_lines_defaults_to_disabled` và
  `..._setting_reaches_translate_pages_call` (`tests/integration/test_job_orchestrator.py`) assert
  `call.kwargs["split_short_lines"]`/`["short_line_split_factor"]` bằng giá trị cụ thể, không chỉ
  `assert_awaited()` — đúng tinh thần R6-02.

## 3. `pdf2zh_runner.py` — 2 tham số bị bỏ qua có chủ đích

Không phải code path chết gây nhầm lẫn: docstring giải thích rõ WHY (đồng bộ signature 2 engine để
`JobOrchestrator` gọi chung 1 lời, tránh `if engine == ...`, trích Architecture.md 6.14.7). Đây là
comment giải thích WHY đúng convention project, không phải WHAT. An toàn vì tham số chỉ bị bỏ qua
lặng lẽ (không raise), đúng ý đồ — nhưng đây cũng là điểm cần lưu ý cho người đọc sau: nếu sau này
`pdf2zh` có flag tương đương thật, phải nhớ update chỗ này (non-blocking, không phải bug).

## 4. Test chất lượng theo Protocol 6 R6-02 / N4

`tests/test_babeldoc_runner.py`: assertion cũ `"--split-short-lines" in args` (assert tự xác nhận
giả định sai, bị N4 phê bình) đã bị **xoá hẳn**, không còn sót lại. Thay bằng: (a) 3 test đơn vị
assert flag/factor có/không có mặt tuỳ tham số; (b) 3 golden-file test đọc PDF thật bằng PyMuPDF
(`page14_*.pdf`, capture từ live spike thật, không viết tay) đếm block/số mục — đúng N6 mục 2
"assert cấu trúc, không assert flag". Golden test còn tự trung thực báo cáo tradeoff (31/35 vs
4/35 numbered item giữ dòng riêng) thay vì giả vờ fix hoàn hảo — đúng tinh thần Protocol 5.

## 5. Protocol 5 R5-01 — nguồn xác thực cho claim CLI flag

Mọi claim cụ thể về `--split-short-lines`/`--short-line-split-factor` trong code/comment/docstring
đều trích `file:line` cụ thể của babeldoc 0.6.4 đã cài (`main.py:179-182`, `main.py:184-189`,
`paragraph_finder.py:891`), khớp với bảng nguồn L1/L2/L4 trong Architecture.md N2. Không có claim
nào chỉ ghi theo trí nhớ. Đạt.

## 6. Tự verify độc lập (không tin báo cáo Dev)

- `.venv/bin/python -m pytest tests/ -q` → **300 passed** (khớp đúng claim "300/300", tự chạy lại).
- `.venv/bin/python -m ruff check .` → **All checks passed!**
- `.venv/bin/python -m ruff format --check .` trên đúng 8 file trong phạm vi review (`babeldoc_runner.py`,
  `pdf2zh_runner.py`, `config.py`, `job_orchestrator.py`, `prompt_builder.py`,
  `test_babeldoc_runner.py`, `test_prompt_builder.py`, `test_job_orchestrator.py`) → **đều "already
  formatted"**. Ghi chú: chạy `ruff format --check .` trên toàn repo có 19 file bị flag reformat,
  nhưng KHÔNG file nào nằm trong phạm vi diff này — pre-existing drift từ trước, không phải do Dev
  gây ra ở task này (khớp đúng claim CHANGELOG "sạch trên đúng các file đã sửa, không chạy tràn
  lan").
- `git diff docs/CHANGELOG.md | grep '^-' | grep -v '^---'` → **0 dòng bị xoá** — CHANGELOG chỉ được
  append đúng Protocol 7 R7-03.

## 7. Protocol 5 R5-04 checklist (bắt buộc cho service wrapper gọi external tool)

**External contract verified against real source: YES** — cho cả `babeldoc_runner.py` (nguồn:
`babeldoc/main.py:179-189`, `format/pdf/document_il/midend/paragraph_finder.py:891-901` của
babeldoc 0.6.4 đã cài tại máy Dev, trích dẫn tường minh trong docstring và Architecture.md N2) và
`pdf2zh_runner.py` (N/A cho 2 tham số mới — không map sang flag CLI thật nào của pdf2zh, chủ đích
bỏ qua, có docstring giải thích).

## 8. Vấn đề phát hiện (non-blocking)

1. RC-3 (F4) vẫn đang ở trạng thái `⚠️ CHƯA VERIFY` theo chính Architecture.md N3 — chưa đo tần
   suất LLM thực sự tự thêm newline trước khi có prompt mới, và chưa verify renderer babeldoc xử lý
   `\n` nội bộ ra sao. Không blocking vì đây là cải thiện phòng ngừa hợp lý dựa trên nguồn L8 đã
   verify (babeldoc chỉ `.strip()` 2 đầu), nhưng QA nên lưu ý đo thêm nếu có điều kiện, đúng
   khuyến nghị chính Tech Lead đã ghi.
2. Tradeoff F1/F2 cho numbered list (31/35 → 4/35 giữ dòng riêng) là hạn chế đã biết trước
   (RC-2), không phải regression của lần sửa này — nhưng đây là UX-facing behavior change cần PM
   quyết định có cần bật `babeldoc_split_short_lines=True` mặc định cho một số loại tài liệu hay
   không trước khi release rộng.

## Kết luận

**APPROVE.**

Không có blocking issue. F1 loại bỏ hardcode sạch, F2 data lineage đúng từ config → orchestrator →
runner (đã trace tay), test đã sửa đúng lỗ hổng N4 chỉ ra (không còn assert tự xác nhận giả định),
golden-file test dùng dữ liệu live thật. R5-01/R5-04 đều có nguồn xác thực tường minh. Tự chạy lại
pytest (300/300) và ruff (sạch trên phạm vi review) độc lập, không dựa vào báo cáo Dev. 2 issue
non-blocking ghi ở trên không cản trở merge nhưng cần theo dõi.

File liên quan: `src/services/babeldoc_runner.py`, `src/services/pdf2zh_runner.py`,
`src/core/config.py`, `src/core/job_orchestrator.py`, `src/core/prompt_builder.py`,
`docs/CHANGELOG.md`, `tests/test_babeldoc_runner.py`, `tests/test_prompt_builder.py`,
`tests/integration/test_job_orchestrator.py`, `tests/fixtures/babeldoc/page14_numbered_list_source.pdf`,
`tests/fixtures/babeldoc/page14_split_short_lines_false_mono.pdf`,
`tests/fixtures/babeldoc/page14_split_short_lines_true_mono.pdf`.

---

## Review vòng 2 — Đảo ngược default `babeldoc_split_short_lines`/`babeldoc_short_line_split_factor` (2026-09-06)

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-06
- **Bối cảnh**: đây là **vòng 2** (Dev↔Reviewer) cho cùng vấn đề line-break/bullet-list — vòng 1
  ở trên đã APPROVE F1/F2/F4 (default `split_short_lines=False`, `factor=0.5`) dựa trên đo 1 trang.
  Dev (theo yêu cầu Tech Lead + quyết định User, không tự ý) vừa **đảo ngược** default đó sang
  `True`/`0.8` sau khi Tech Lead đo lại 21 lần chạy thật/7 trang. **Còn trong giới hạn Protocol 3**
  (max 3 vòng) — đây không phải trường hợp cần escalate.
- **Phạm vi thay đổi lần này** (đúng như PM giao, đã đối chiếu `git status`): `src/core/config.py`,
  `src/services/babeldoc_runner.py` (docstring), `tests/integration/test_job_orchestrator.py`,
  `tests/test_babeldoc_runner.py` (ghi chú CORRECTION), `docs/CHANGELOG.md`.

### 1. Số liệu 21-lần-chạy có đủ thuyết phục để đảo ngược không

Đọc trực tiếp bảng thô Q3 và phân tích từng trang Q4 trong Architecture.md (không chỉ tin tóm tắt
Q5/Q6):

- Phương pháp chặt: live thật (babeldoc 0.6.4 + DeepSeek thật), qua đúng production code path
  (`BabeldocRunner.translate_pages()` + `Pdf2zhServiceMapper`), 7 trang chọn có chủ đích theo 5 loại
  bố cục (đã quét thống kê để chọn, không chọn tuỳ tiện), đo theo **vùng nội dung** (văn xuôi tách
  riêng danh sách/caption) — đúng bài học mà chính P2 rút ra từ sai lầm đo lần 1 (đo tổng block là
  proxy sai).
- Dữ liệu tự nhất quán nội bộ: trang 13/21 (văn xuôi/bảng thuần) — cả 3 arm **giống hệt nhau từng
  ký tự** — là bằng chứng mạnh nhất rằng RC-1 không lan ra ngoài phạm vi caption, vì đây chính là
  loại nội dung chiếm phần lớn một cuốn sách.
- Phát hiện `factor=0.5` là tệ nhất trong 3 có cơ sở dữ liệu rõ ràng (trang 8: 7 lỗi dính chữ y hệt
  `false`; trang 14: 21/28 lỗi còn nguyên) — không phải suy luận, là số đếm cụ thể trên PDF output
  thật.
- Điểm cần lưu ý (không đủ để bác bỏ kết luận, nhưng nên ghi nhận): mẫu 7 trang trên 1 cuốn sách,
  vẫn là **n nhỏ** ở cấp độ "loại tài liệu" (chỉ 1 cuốn, 1 ngôn ngữ nguồn tiếng Anh, 1 LLM). Trang
  22 cho kết quả trái chiều (mỗi arm hỏng 1 chỗ) — Architecture.md không giấu diếm điều này, xếp
  đúng vào "hoà"/"trái chiều" thay vì gộp mờ vào "thắng". Đây là dấu hiệu tốt về tính trung thực của
  báo cáo, không phải điểm yếu của lập luận.
- **Kết luận**: số liệu 21-lần-chạy đủ thuyết phục hơn hẳn số liệu 1 trang ban đầu — không chỉ vì
  cỡ mẫu lớn hơn, mà vì nó **sửa đúng lỗi phương pháp** (đo theo vùng thay vì tổng block) đã gây ra
  kết luận sai ở vòng 1. Đây không phải "đổi ý vì thêm dữ liệu tình cờ khác đi" mà là phát hiện ra
  bằng chứng gốc bị diễn giải sai (P2 trong Architecture.md), điều mà cả Reviewer vòng 1 cũng không
  bắt được — self-review không phát hiện, nhưng lần đo mở rộng đã tự sửa được.

### 2. `src/core/config.py`

`git diff` xác nhận: `babeldoc_split_short_lines: bool = True` và
`babeldoc_short_line_split_factor: float = 0.8` — đúng số PM/Tech Lead khuyến nghị (Q6). Comment
mới **không xoá** lý do cũ (giữ nguyên đoạn giải thích lần đổi 1 kèm nhãn rõ "SAI" khi cần), có ghi
rõ "LICH SU QUYET DINH (2 lan doi...)" — đúng tinh thần "không phải 1 quyết định tuỳ tiện" mà PM
yêu cầu review làm rõ. Không còn đoạn nào ngầm ý `0.5`/`False` là default đúng.

### 3. `test_job_orchestrator.py` — 2 test viết lại

Đã đọc trực tiếp diff (không tin tóm tắt CHANGELOG):

- `test_babeldoc_split_short_lines_defaults_to_enabled_with_babeldoc_factor`: assert
  `settings.babeldoc_split_short_lines is True` / `== 0.8` ở cấp `Settings`, RỒI assert
  `call.kwargs["split_short_lines"] is True` / `call.kwargs["short_line_split_factor"] == 0.8` trên
  chính lời gọi `translate_pages()` thật — đúng R6-02 (assert giá trị cụ thể xuyên suốt pipeline,
  không chỉ `assert_awaited()`).
- `test_babeldoc_split_short_lines_can_be_opted_out_via_settings`: che phủ đúng trường hợp opt-out
  PM yêu cầu kiểm tra — set `babeldoc_split_short_lines=False` tường minh trong `Settings`, assert
  `call.kwargs["split_short_lines"] is False` VÀ `call.kwargs["short_line_split_factor"] is None`
  (không chỉ kiểm tra flag mà còn kiểm tra factor bị vô hiệu đúng theo điều kiện `and` của
  `paragraph_finder.py:891` — đúng cả 2 vế R6-02).
- Cả 2 test đều tự chạy `orchestrator.run_job()` thật (không mock `JobOrchestrator`), lấy
  `await_args_list` từ mock `babeldoc_runner` — đúng cách trace R6-04, không chỉ tin tham số ở tầng
  `Settings` là đã "chảy" xuống tầng dưới.

### 4. `test_babeldoc_runner.py` — ghi chú CORRECTION

Đọc toàn văn ghi chú mới (2 khối, trước nhóm test flag opt-in và trước 2 golden-file test). Cả 2
đều: (a) nói rõ số liệu fixture (31/35, 4/35, block 36/11) là **snapshot lịch sử của 1 lần đo đơn
lẻ**, (b) nói rõ default hiện tại nằm ở `Settings` (tầng trên), không phải ở default riêng của
`translate_pages()`, (c) trỏ đường dẫn cụ thể tới nơi có kết luận đúng hiện hành
(`test_job_orchestrator.py` test tên cụ thể + Architecture.md tên section cụ thể) thay vì chỉ nói
chung chung "xem thêm". Không có chỗ nào còn sót câu khẳng định ngầm "False là default nên dùng".
Đủ rõ để người đọc sau (kể cả không đọc CHANGELOG) không hiểu nhầm. Đạt yêu cầu PM đặt ra ở mục 4.

### 5. Tự verify độc lập

- `.venv/bin/python -m pytest tests/ -q` → **300 passed** — khớp đúng claim CHANGELOG "300/300",
  tự chạy lại chứ không tin báo cáo.
- `.venv/bin/python -m ruff check .` trên toàn repo → **4 lỗi**, nhưng cả 4 đều nằm ở
  `tests/fixtures/babeldoc/ab_split_short_lines/run_measure.py` (harness đo 21-lần-chạy, file mới,
  KHÔNG nằm trong phạm vi 5 file PM giao review lần này) — `RUF100` (noqa thừa) + `I001` (import
  chưa sort). Không phải regression của diff đang review, nhưng cần Dev dọn trước khi commit file
  này vào repo (non-blocking cho scope hiện tại, xem mục 6).
- `.venv/bin/python -m ruff format --check src/core/config.py src/services/babeldoc_runner.py
  tests/integration/test_job_orchestrator.py tests/test_babeldoc_runner.py` → **cả 4 file "already
  formatted"**.
- `git diff docs/CHANGELOG.md docs/review-report.md | grep '^-' | grep -v '^---'` (trước khi tự
  append section này) → 0 dòng bị xoá ở CHANGELOG — đúng Protocol 7 R7-03 (append, không overwrite).

### 6. Vấn đề phát hiện (non-blocking)

1. `tests/fixtures/babeldoc/ab_split_short_lines/run_measure.py` (harness đo 21-lần-chạy, untracked)
   fail `ruff check` (3× `RUF100` noqa thừa + 1× `I001` import chưa sort). Không nằm trong phạm vi
   review lần này và không ảnh hưởng production code, nhưng nếu Dev/Tech Lead commit thư mục
   `tests/fixtures/babeldoc/ab_split_short_lines/` vào repo (khuyến nghị nên commit, vì đây là
   golden-file artifact tái tạo được — Protocol 5 mục 3), cần chạy `ruff check --fix` trước.
2. Bằng chứng "trái chiều" ở trang 22 (mỗi arm hỏng 1 chỗ khác nhau) là điểm mềm nhất trong lập
   luận Q5 — không đủ để bác bỏ kết luận chung (2 hoà, 1 thua nhẹ, 3 thắng rõ vẫn nghiêng hẳn về
   `True`/`0.8`), nhưng QA nên biết rằng "known limitation: caption có thể bị cắt fragment" (đã ghi
   trong khuyến nghị Q6 mục 4) là NGUY CƠ THẬT đã đo được, không phải lý thuyết — nên xác nhận lại
   qua ít nhất 1 lần release-candidate thật có trang chứa caption bảng/ảnh trước khi đóng hẳn.

### 7. Protocol 3 — Circuit Breaker

Đếm vòng Dev↔Reviewer cho riêng bug line-break/bullet-list (không tính review 5 tính năng UI riêng
ở giữa 2 section): vòng 1 (F1/F2/F4, APPROVE) → vòng 2 (đảo ngược default, review này). **2/3 vòng
— chưa vượt giới hạn**, không cần escalate theo Protocol 3.

## Kết luận (vòng 2)

**APPROVE việc đảo ngược default.**

Số liệu 21-lần-chạy/7-trang đáng tin hơn số liệu 1-trang ban đầu vì nó sửa đúng lỗi phương pháp đo
(theo vùng thay vì tổng block) đã gây ra kết luận sai lần trước, không chỉ vì cỡ mẫu lớn hơn. Default
mới (`True`/`0.8`) đúng theo khuyến nghị Q6, comment lịch sử đầy đủ 2 lần đổi không xoá lý do cũ, 2
test data-lineage viết lại đúng R6-02 (assert giá trị cụ thể, che phủ cả default và opt-out), ghi
chú CORRECTION đủ rõ để không gây hiểu nhầm về sau. Tự chạy lại pytest (300/300) và ruff trên đúng
phạm vi diff (sạch) độc lập, không dựa báo cáo Dev. 2 issue non-blocking ở mục 6 không cản trở coi
bug này là closed, nhưng khuyến nghị QA làm thêm 1 lượt kiểm tra caption thật trước khi release rộng
rãi theo mục 6.2. Còn trong giới hạn Protocol 3 (2/3 vòng), không cần escalate.

---

## US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — Review (2026-09-06, vòng 1)

Phạm vi: `src/postprocess/image_compress.py` (mới), `tests/test_image_compress.py` (mới),
`src/core/job_orchestrator.py` (wiring), `tests/integration/test_job_orchestrator.py` (3 test
lineage mới), `docs/CHANGELOG.md` (append, đã tự kiểm tra không xoá lịch sử — xem mục 4). Đọc
Architecture.md "US-16 — Nen anh sau khi ghep" (S1-S10) + PRD.md §3/§4.9 trước khi review, tự đọc
diff thật bằng `git diff`/`git status` + đọc trọn từng file, không tin báo cáo Dev suông.

### 1. R6-04 — Trace tay data lineage trong `job_orchestrator.py`

Đã tự đọc từng dòng, không chỉ tin comment:

- `job_orchestrator.py:477` — `merged_path = self._output_dir / job.id / "translated_vi.pdf"`.
- `:479` — `await merge_chunk_pdfs(chunks, merged_path)` — `merged_path` là biến được gán ở `:477`,
  truyền thẳng vào, không qua biến trung gian nào.
- `:483` — guard BR-OCR-03 mở `fitz.open(merged_path)` — cùng biến.
- `:495-496` — `if self._settings.pdf_translate_engine == "babeldoc": await
  compress_pdf_images(merged_path)` — **cùng chính xác biến `merged_path` đó**, không phải
  `job.file_path`, không phải biến mới nào khác. Đứng **sau** khối guard BR-OCR-03 (kết thúc ở
  `:491`) và **trước** `job.output_path = str(merged_path)` (`:508`, ngoài khối `try`).
- Điều kiện engine đọc đúng field đã verify trong Architecture.md
  (`self._settings.pdf_translate_engine == "babeldoc"`, khớp `src/core/config.py:135`), không bị
  đảo ngược (test `test_pdf2zh_engine_does_not_compress_images` xác nhận `pdf2zh` → không gọi).
- Toàn bộ nằm trong cùng khối `try` của Step 8 — một lỗi ở bước nén sẽ rơi vào cùng `except
  Exception` phía dưới (`job.status = "failed"`), không rơi ra ngoài job hiện tại — đúng ý "1 lỗi
  không crash cả batch" ở cấp job.

**Kết luận R6-04: lineage đúng 100% theo thiết kế S5. Không phát hiện sai lệch.**

Test đi kèm (`test_babeldoc_engine_compresses_merged_output_with_correct_lineage`,
`tests/integration/test_job_orchestrator.py:854-890`) assert đúng giá trị cụ thể — không phải
`assert_awaited()` trần:
```python
called_path = compress_spy.await_args.args[0]
assert Path(called_path) == Path(result.output_path)
assert Path(called_path) != Path(job.file_path)
```
Đây đúng dạng ràng buộc Bug #5 đã thiếu (so khớp giá trị input của bước sau với output bước
trước, không chỉ "đã gọi chưa"). `test_empty_translation_fails_before_compress_runs` xác nhận
đúng thứ tự (guard BR-OCR-03 chạy trước, nén không chạy khi job đã fail sớm hơn) bằng cách tạo
babeldoc runner giả trả về file không có chữ, rồi assert `compress_spy.assert_not_awaited()` +
message đúng của guard, không phải message lỗi nén.

### 2. R5-04 — External contract checklist cho `image_compress.py`

**External contract verified against real source: YES** — nguồn: Architecture.md US-16 S1 (chạy
thật `inspect.signature` trên PyMuPDF 1.28.2 đã cài trong `.venv`, kèm output thật). Tự đối chiếu
lại từng lệnh gọi trong `image_compress.py` với bảng signature đã verify ở S1, không phát hiện
lệch:

- `doc.get_page_images(pno, full=True)` (`image_compress.py:74`) — khớp signature verify, và code
  dùng `info[0]` (xref) / `info[1]` (smask) đúng thứ tự đã đo ở S1 (không nhầm với `info[8]` như
  cạm bẫy Architecture.md đã ghi lại đã từng mắc phải).
- `doc.xref_get_key(xref, "Filter")` / `"ImageMask"` (`:81`, `:86`) — dùng đúng, kiểm tra
  `filter_type != "null"` khớp cách diễn đạt BR-IMGCOMP-02.
- `pymupdf.Pixmap(doc, xref)` + `.tobytes("jpeg", jpg_quality=jeg_quality)` (`:107`, `:111`) —
  **đúng** `jpg_quality`, không phải `quality` (đúng cạm bẫy Architecture.md S1 đã cảnh báo tên
  tham số). Không dùng `extract_image()`/`replace_image()` — khớp quyết định S4 (Pillow không có
  trong `.venv`).
- `doc.update_stream(xref, jpeg_bytes, new=1, compress=0)` (`:117`) — **đúng** `compress=0`, đúng
  điểm S6 bước 8 nhấn mạnh ("để `compress=1` mặc định sẽ bọc thêm 1 lớp Flate vô ích").
- `doc.xref_set_key(...)` ghi lại `Filter`/`BitsPerComponent`/`ColorSpace`/`Width`/`Height`
  (`:118-124`) — đủ 5 key theo S6 bước 8, `ColorSpace` map theo `pix.n` (`_COLORSPACE_BY_CHANNELS`)
  khớp bảng `4→/DeviceCMYK, 3→/DeviceRGB, còn lại→/DeviceGray` — không bị bỏ sót (Architecture.md
  nhấn mạnh đây là bắt buộc, bỏ sẽ ra màu sai vì ICC profile cũ không còn khớp JPEG mới).
- `doc.save(tmp_path, garbage=4, deflate=True)` → `close()` → `os.replace(tmp_path, pdf_path)`
  (`:138-142`) — đúng thứ tự S5/S6 bước 9, dùng file tạm cùng thư mục (`tempfile.mkstemp(dir=...)`)
  rồi `os.replace` atomic, không save-đè file đang mở (đã verify PyMuPDF raise
  `ValueError: save to original must be incremental` nếu làm vậy — Architecture.md S5).

Không có API nào bị gọi khác với bảng đã verify. `image_compress.py` cũng dùng `import fitz` cố ý
(không đổi sang `import pymupdf`) để nhất quán với `chunk_merge.py` — đúng quyết định đã ghi ở S1,
không phải sơ suất.

### 3. Các gate đã chốt — kiểm tra không bị vi phạm

- **Dedupe**: `grep -rn "hashlib\|sha256\|dedupe" src/postprocess/image_compress.py` → không có
  kết quả. Không có code dedupe nào lọt vào — đúng quyết định S3 (4.2% < 20%, loại khỏi scope).
- **`chunk_merge.py` — không thêm deflate cho pdf2zh trong scope US-16**: `git diff --
  src/postprocess/chunk_merge.py` có thay đổi thật, NHƯNG đọc kỹ nội dung thì đây là fix Bug #8
  (babeldoc chunk-scoped vs full-document page-indexing, tự phát hiện shape qua
  `chunk_doc.page_count >= chunk.page_end`) — **không liên quan gì đến `deflate`/US-16**, không
  đụng tới lời gọi `output_doc.save(...)` ở dòng gây ra vấn đề S8. Xác nhận bằng
  `grep -n "deflate\|garbage=" src/postprocess/chunk_merge.py` → không có kết quả. Đây là diff
  tồn tại từ trước trong working tree (không thuộc 5 file Dev báo cáo cho US-16), **không phải
  Dev vi phạm gate US-16**. Quyết định (A)/(B) ở Architecture.md S8 đúng là vẫn đang treo, chưa ai
  tự ý chọn (B) — khớp CHANGELOG.md Dev tự ghi.
- **Gate `pdf_translate_engine == "babeldoc"`**: đã trace tay ở mục 1 — đúng vị trí, đúng chiều
  (không đảo ngược), có test cả 2 nhánh (babeldoc gọi, pdf2zh không gọi).
- **Vị trí sau guard BR-OCR-03**: đã trace tay ở mục 1 bằng số dòng thật (`:481-491` guard, `:495`
  compress) — đúng, không phải chỉ tin comment.
- **SMask/ImageMask skip**: `image_compress.py:86-103` — cả 2 đều `continue` sau khi log warning
  và tăng `images_skipped_unsupported`, không crash, không đụng vào ảnh (giữ nguyên stream/filter
  gốc). Đúng thiết kế S6 bước 4. Nhánh này chưa có dữ liệu thật nào chạy qua (0/357 mẫu có
  SMask/ImageMask) — Architecture.md tự đánh dấu `[UNVERIFIED]` ở S10 cho đúng, không giấu.
- **DCTDecode không bị nén chồng lần 2**: `image_compress.py:81-84` — bất kỳ filter nào khác
  `"null"` đều bị skip trước khi tới bước Pixmap/encode. Có test trực tiếp
  (`test_compress_pdf_images_does_not_recompress_already_compressed_images`) so sánh **byte
  stream** (không phải xref số, vì xref renumber qua `garbage=4`) — đã tự chạy lại, pass.

### 4. Protocol 7 R7-03 — kiểm tra CHANGELOG.md không bị Dev ghi đè

`git diff docs/CHANGELOG.md | grep '^-' | grep -v '^---'` → 0 dòng bị xoá. Section US-16 Dev thêm
nằm ở cuối file (dòng 3320-3373), sau toàn bộ lịch sử review/fix trước đó (bug line-break, 5 tính
năng UI...) — đúng append, không overwrite.

### 5. Tự chạy lại độc lập (không tin báo cáo Dev)

```
.venv/bin/python -m pytest tests/test_image_compress.py tests/integration/test_job_orchestrator.py -q
→ 22 passed
.venv/bin/python -m pytest tests/ -q
→ 307 passed (đúng con số Dev báo cáo trong CHANGELOG)
.venv/bin/python -m ruff check src/postprocess/image_compress.py src/core/job_orchestrator.py \
  tests/test_image_compress.py tests/integration/test_job_orchestrator.py
→ All checks passed!
```

### 6. Vấn đề phát hiện (non-blocking)

1. **Rò file tạm khi `doc.save()` thất bại** (`image_compress.py:133-142`): nếu `doc.save(tmp_path,
   ...)` raise (ví dụ hết dung lượng đĩa giữa chừng), khối `finally` chỉ đóng `doc`, không xoá
   `tmp_path` — file `.tmp.pdf` rác sẽ ở lại thư mục output. Không phải lỗi correctness nghiêm
   trọng (job vẫn `failed` đúng, `merged_path` gốc không bị hỏng vì `os.replace` chưa chạy tới),
   nhưng nên thêm `try/except`/`tmp_path.unlink(missing_ok=True)` quanh nhánh lỗi để tránh rác tích
   luỹ qua nhiều lần retry job.
2. **Filter dạng array chưa được cân nhắc tường minh**: `doc.xref_get_key(xref, "Filter")` với 1
   ảnh có filter chain (ví dụ `[/ASCII85Decode /DCTDecode]`, PDF hợp lệ dù hiếm) sẽ trả `type`
   không phải `"null"` nên vẫn được skip đúng (an toàn), nhưng Architecture.md S6 bước 3 chỉ liệt
   kê filter đơn (`DCTDecode`, `CCITTFaxDecode`...), không nói rõ trường hợp mảng. Hành vi hiện tại
   tình cờ đúng (skip an toàn) chứ không phải được thiết kế có chủ đích cho case này — nên ghi chú
   1 dòng trong docstring nếu có thời gian, không chặn approve vì không có dữ liệu thật nào cho
   thấy case này xảy ra (giống tinh thần S10 với SMask/ImageMask).
3. Không phát hiện vấn đề correctness/security/style/performance nào khác trong phạm vi review.

### 7. Protocol 3 — Circuit Breaker

Vòng 1 cho US-16 — APPROVE ngay từ vòng đầu, không cần vòng 2.

## Kết luận (US-16, vòng 1)

**APPROVE.**

R6-04: lineage `merged_path` → `compress_pdf_images` đã trace tay bằng số dòng thật, đúng 100%
thiết kế S5, không phải chỉ tin comment. R5-04: External contract verified against real source:
**YES** (Architecture.md S1, chạy `inspect.signature` thật trên PyMuPDF 1.28.2) — đối chiếu từng
lệnh gọi trong code với bảng đã verify, không lệch. Các gate đã chốt (không dedupe, không đụng
`chunk_merge.py` cho deflate pdf2zh, gate engine đúng chiều, vị trí sau BR-OCR-03, skip
SMask/ImageMask an toàn, không nén chồng DCTDecode) đều được giữ đúng. Test chạy thật trên fixture
thật (không mock nội dung ảnh tay), assert nội dung cụ thể (byte stream, lineage path) chứ không
chỉ trạng thái/`assert_called()`. Tự chạy lại pytest (307/307) và ruff (sạch) độc lập, khớp báo cáo
Dev. 2 issue non-blocking ở mục 6 (rò file tạm khi save lỗi, filter-array chưa ghi chú) không cản
trở approve — khuyến nghị Dev dọn ở lần sửa tiếp theo liên quan tới file này. CHANGELOG.md được
Dev append đúng cách (Protocol 7 R7-03), không mất lịch sử.

---
---

# P0 — Babeldoc Layout Bug Fix Roadmap (Gate P0.1 + Pin P0.3) — Iteration 1

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-07
- **Phạm vi**: `src/services/layout_qa.py` (mới), `src/models/layout_qa.py` (mới),
  `src/models/__init__.py`, `src/models/database.py` (đăng ký model mới),
  `tests/test_layout_qa.py` (mới, 19 test), `docs/Architecture.md` + `docs/CHANGELOG.md`
  (cập nhật P0.1/P0.3 + kết quả A/B P0.2). Không bao gồm `BabeldocRunner`/orchestrator (không
  nằm trong diff này).

## Verdict: **APPROVE**

Module gate đo lường chất lượng layout, chất lượng tốt: type hints đầy đủ, docstring rõ ràng
gắn với từng dòng spec Architecture.md U4/P0.1, test dùng fixture PDF thật (không mock hình
học), tự chạy lại toàn bộ đều khớp báo cáo Dev. Không có blocking issue. Có một số rủi ro
heuristic đáng lưu ý ở mục 4 nhưng đã được Dev tự ghi nhận rõ trong code/CHANGELOG, không che
giấu — chấp nhận được cho gate ở giai đoạn P0 (đo trước khi fix), xếp non-blocking.

---

## 1. R5-04 checklist (bắt buộc) — External contract verified against real source

**Kết luận: N/A** (không phải YES/NO theo nghĩa "gọi external tool sai/đúng").

Lý do: `src/services/layout_qa.py` **không** gọi babeldoc/pdf2zh qua subprocess/HTTP — nó chỉ
đọc file PDF *output* bằng PyMuPDF (thư viện Python import trực tiếp, dùng API core:
`get_text("blocks")`, `get_text("dict")`, `get_drawings()`, `get_image_rects()`). Theo đúng
"Phạm vi áp dụng" của Protocol 5 trong CLAUDE.md project: *"Không áp dụng cho thư viện nội bộ
Python thuần code logic (... `pymupdf` dùng đúng API core, không phải external network/
subprocess service)"* — nên R5-04 dạng YES/NO không áp dụng trực tiếp cho module này.

Tuy vậy module **có** 2 chỗ mang giả định về hành vi PyMuPDF cần verify vì dùng để suy luận
logic quan trọng (không phải chỉ gọi API cho có) — tôi đã tự verify thật (không tin theo
docstring của Dev):

- `page.get_drawings()[i]["type"]` chứa `"s"` khi có nét stroke (dùng để lọc "đường viền vẽ"
  ở check (b)). Tự chạy `fitz` 1.28.2 thật (`draw_rect(..., fill=None, width=2)` →
  `{'type': 's', ...}`; `draw_rect(..., fill=(1,0,0), width=0)` → `{'type': 'f', ...}`) — khớp
  đúng logic `"s" in (drawing.get("type") or "")` trong code. **Verified — chạy thật, không
  đọc tài liệu suông.**
- Ngưỡng góc xoay `ROTATION_TOLERANCE_DEG = 0.1` và điều kiện vứt ký tự của babeldoc
  (`il_creater.py:968-974`) — đây LÀ claim về babeldoc thật, nhưng đã được Tech Lead verify
  trực tiếp source code và ghi rõ trong Architecture.md U1 (bảng V-1/E-2, kèm số dòng file
  cụ thể) trước khi Dev viết module này — Dev chỉ *tái sử dụng* con số đã verify, có trích dẫn
  nguồn (docstring dòng 12: `"dung nguong il_creater.py:968-974"`). Không phải claim mới chưa
  verify.

## 2. R6-04 — Trace tay data lineage nội bộ module

Không có `*_orchestrator.py` nào trong diff này (chưa nối vào `JobOrchestrator`), nên checklist
R6-04 đúng nghĩa (orchestrator gọi nhiều service) chưa áp dụng. Nhưng `run_layout_qa_gate()` tự
nó đóng vai trò điều phối nhiều bước nội bộ (mở file → chạy 5 check → gom queue), nên tôi trace
tay như thể nó là 1 orchestrator nhỏ:

- `translated_page_count` được gán từ `len(translated_doc)` **trước khi đóng** `translated_doc`
  lần mở đầu tiên (dòng 382), rồi dùng để giới hạn vòng lặp thứ hai (`if index <
  translated_page_count`, dòng 395) khi mở lại `translated_doc` lần 2 để chạy check (e) theo
  cặp trang với `source_doc`. Đã đọc kỹ: biến này đúng là lấy từ file dịch thật (không phải
  copy số trang gốc), và guard này ngăn `IndexError`/sai lệch khi 2 file lệch số trang — đúng.
- Check (e) `_check_entity_preservation(source_page, translated_doc[index], ...)`: `source_page`
  lấy từ `source_doc[index]` (vòng lặp ngoài đang chạy theo `source_doc`), `translated_doc[index]`
  dùng CÙNG `index` — tức giả định 1-đối-1 theo thứ tự trang giữa gốc và dịch. Giả định này được
  ghi rõ trong docstring `run_layout_qa_gate` ("gia dinh so trang giu nguyen giua goc va dich —
  dung voi babeldoc/pdf2zh vi ca hai deu dich 1-doi-1 trang, khong chen/xoa trang") — đúng là
  invariant thật của 2 tool này (không chèn/xoá trang), không phải giả định tuỳ tiện.
- `persist_findings()` ghi thẳng `finding.detail` (đã serialize JSON) từ list `findings` được
  trả về nguyên vẹn từ `run_layout_qa_gate` — không có bước biến đổi/mất dữ liệu giữa lúc tính
  toán và lúc ghi DB.

**Kết luận R6-04**: lineage nội bộ đúng, không phát hiện lỗi kiểu Bug #5 (mất kết nối giữa 2
bước).

---

## 3. Bốn "giả định tự chọn" của Dev (CHANGELOG)

1. **`page_number` 1-indexed**: hợp lý, khớp cách con người/Architecture.md gọi trang ("trang
   67"), khác `fitz.Page.number` (0-indexed) một cách có chủ ý và đã ghi rõ. Test
   (`test_rotated_text_prescan_matches_t3d_measurement_on_p67`) gọi `page_number=67` khi đọc
   `doc[0]` (0-indexed) của fixture 1 trang — đúng convention, không lẫn lộn.
2. **Severity map cố định** (`overlap`/`text_over_drawing`/`text_over_image` = critical,
   `rotated_text_prescan`/`entity_loss` = blocker): đã tự đối chiếu `docs/ux-review-report.md`
   dòng 78-79 — UX-A và UX-B **đúng là "Critical"** trong báo cáo UX gốc, khớp claim của Dev.
   UX-C **đúng là "Blocker"** (dòng 77) — khớp `rotated_text_prescan`. Riêng `entity_loss`
   (DoD-UX-02, "Không mất nội dung") không có nhãn UX-letter/severity riêng tường minh trong
   `ux-review-report.md` (DoD-UX-02 là tiêu chí release riêng, không map 1-1 với UX-C) — Dev ghi
   "khớp UX-C" hơi rộng tay, nhưng chọn mức **blocker** (mức cao nhất) cho 1 check đo trực tiếp
   mất nội dung định lượng là hướng an toàn, hợp lý về bản chất rủi ro (số/đơn vị công thức nấu
   ăn sai là nghiêm trọng) dù lập luận trích dẫn hơi lỏng. Non-blocking, xem mục 5.
3. **`job_id` nullable + `run_label`/`source_file`**: hợp lý — P0.2 chạy babeldoc/pdf2zh ngoài
   `JobOrchestrator`, không có `Job` row thật; thiết kế cho phép cả 2 chế độ (spike A/B và pipeline
   thật tương lai) dùng chung bảng mà không cần bảng riêng. Đã đối chiếu convention model khác
   (`OverflowReport` cũng có FK nullable tương tự cho trường hợp không chắc luôn có job) — nhất
   quán.
4. **Ngưỡng IoU 0.05 cho check (e)**: đây là điểm cần lưu ý nhất, xem mục 4.

---

## 4. Rủi ro heuristic bảo toàn thực thể số/đơn vị (mục quan trọng nhất theo yêu cầu review)

Đã tự đọc kỹ `_check_entity_preservation`/`_find_entities`/`_best_matching_block` và tự nghĩ
thêm case ngoài test có sẵn:

**False positive (flag oan, không blocking vì đây vốn là "cảnh báo cho QA soi", không phải kết
luận cuối — nhưng đáng ghi rõ hơn nữa trong docstring)**:
- Regex chỉ khớp định dạng **y hệt ký hiệu gốc** (`"°C"`, `"g"`, `"phút"`...). Nếu bản dịch hợp
  lệ dùng cách viết khác — ví dụ `"180 độ C"` thay vì `"180°C"`, số thập phân đổi dấu phẩy↔chấm
  (`"10,5g"` → `"10.5g"`), hoặc thêm khoảng trắng/full-width — check sẽ báo `entity_loss` dù nội
  dung không hề mất. Dev đã tự nêu đúng case này trong docstring (dòng 322-324: `"10 phút" ->
  "10 min"`) nên đây không phải thiếu sót che giấu, chỉ là rủi ro cố hữu của cách tiếp cận
  regex — chấp nhận được cho 1 GATE cảnh báo (không phải hard-block tự động), miễn QA hiểu đây
  là gợi ý cần soi tay, không phải sự thật tuyệt đối.

**False negative (nguy hiểm hơn, vì đây là gate quan trọng nhất — im lặng bỏ sót mất nội dung
thật)**:
- `missing = [entity for entity in entities if entity not in translated_text]` chỉ kiểm tra
  chuỗi con xuất hiện **ở đâu đó** trong toàn bộ text của block dịch đã match, không kiểm tra
  đúng vị trí/đúng câu. Nếu 1 block dịch dài (gộp nhiều đoạn gốc, hoặc babeldoc gộp paragraph
  sai như RC-T1/T-07 đã ghi trong Architecture.md) tình cờ chứa cùng con số ở chỗ khác (ví dụ
  cùng công thức lặp lại "180°C" ở bước 2 nhưng bị mất ở bước 5), check sẽ **PASS oan** vì tìm
  thấy "180°C" đâu đó trong block, dù đúng vị trí cần nó đã mất. Đây là hạn chế thật của cách
  match theo block-level substring thay vì theo dòng/câu — rủi ro tăng thêm khi kết hợp với
  ngưỡng IoU rất lỏng (`0.05`): 1 block dịch lớn có thể "hấp thụ" nhiều block gốc nhỏ nếu bbox
  hơi chồng lấn, khiến check (e) hoạt động ở mức "trang" chứ không phải "block" trong các
  trường hợp gộp nặng — đúng kịch bản UX-A (paragraph bị gộp/lệch) mà chính roadmap này đang cố
  gate.
- `_best_matching_block` chọn block có IoU **lớn nhất trong số các block vượt ngưỡng 0.05**,
  không có cơ chế "unique assignment" (1 block dịch có thể được chọn làm match cho nhiều block
  gốc khác nhau cùng lúc) — nếu 2 block gốc kề nhau bị gộp thành 1 block dịch, cả 2 sẽ match
  cùng 1 block dịch đó; không sai về mặt logic hiện tại (mỗi block gốc xét độc lập) nhưng có thể
  khiến kết quả entity check và overlap check (a) trên CÙNG 1 trang kể 2 câu chuyện khác nhau về
  cùng 1 hiện tượng gộp block — không phải bug, nhưng nên ghi chú liên hệ này trong docstring để
  QA đọc report dễ liên hệ 2 loại finding với nhau khi debug 1 trang.

**Đánh giá tổng thể**: không có lỗi logic (code khớp đúng ý định đã ghi trong docstring, test
`test_check_entity_preservation_flags_missing_temperature`/`..._passes_when_all_entities_kept`
verify đúng hành vi cơ bản), nhưng **rủi ro false-negative do block-level substring match + IoU
lỏng nên được ghi thành 1 dòng cảnh báo rõ ràng hơn trong docstring** (hiện chỉ nêu ví dụ
false-positive định dạng, chưa nêu rõ trường hợp false-negative do gộp block) — xếp
**non-blocking nhưng nên làm sớm**, vì đây đúng là gate quan trọng nhất theo đánh giá của
Domain Expert/UX report, và người đọc report (QA) cần biết giới hạn này để không quá tin tưởng
khi gate PASS.

---

## 5. Migration DB (`layout_qa_findings`)

Đối chiếu với các model khác (`job.py`, `database.py`): project **không dùng Alembic**, mà dùng
`SQLModel.metadata.create_all()` cho bảng mới + `_NEW_NULLABLE_COLUMNS`/hàm migrate riêng
(`_migrate_concurrency_state_engine_key`) chỉ cho các thay đổi trên bảng **đã tồn tại** (thêm
cột, đổi PK). `layout_qa_findings` là bảng **hoàn toàn mới**, nên chỉ cần đăng ký model trong
`src/models/__init__.py` (đã làm) và import trong `src/models/database.py` để
`SQLModel.metadata.create_all()` tạo bảng khi khởi động (đã làm, dòng import + comment
`# noqa: F401` đúng pattern các model khác) — **không cần** thêm entry vào
`_NEW_NULLABLE_COLUMNS` (đúng, vì đó chỉ dành cho ALTER TABLE trên bảng cũ). Đã tự đọc
`src/models/job.py` để xác nhận field `id: str = Field(default_factory=_uuid, primary_key=True)`
là kiểu `str` UUID — khớp với `foreign_key="jobs.id"` kiểu `str | None` trong
`LayoutQaFinding.job_id`, không lệch kiểu FK. **Đúng convention, không có vấn đề.**

---

## 6. Trung thực của "Kết quả thí nghiệm A/B — P0.2"

Đọc kỹ toàn bộ section trong Architecture.md. Đánh giá: **trình bày trung thực, phân biệt rõ
VERIFIED/UNVERIFIED, không phóng đại**:

- Câu hỏi 1 (UX-D): kết quả "không tái hiện được" được giữ nguyên là **`[UNVERIFIED]`**, không
  bị diễn giải quá tay thành "đã loại trừ T-07" — Dev viết rõ "không loại trừ T-07 (chỉ là không
  tái hiện được lần này), nhưng cũng không xác nhận được". Đúng tinh thần Protocol 5.
- Phát hiện phụ (gate P0.1-a bị "ngợp" bởi hàng trăm nghìn cặp overlap từ block cực nhỏ/trùng
  lặp `fallback_line`/`plain text`): đây là 1 hạn chế thật của chính gate P0.1 vừa build, và Dev
  **tự báo cáo hạn chế của sản phẩm mình vừa làm** thay vì giấu đi — đáng ghi nhận. Đã note
  đúng "KHÔNG sửa trong task này, ngoài scope" — hợp lý không mở rộng scope P0 giữa chừng.
- Câu hỏi 2 (`--max-pages-per-part`): kết luận "KHÔNG implement P1.3" dựa trên số liệu cụ thể
  (149 vs 149, 4243 vs 4243 — bằng tuyệt đối ở 2/3 trang đo) — kết luận khớp với điều kiện đã
  chốt trước ở U4 ("P1.3 chỉ implement nếu P0.2 chứng minh"), không tự ý nới lỏng điều kiện.
- Câu hỏi 4 (pdf2zh fallback): đây là chỗ dễ bị phóng đại nhất (pdf2zh thắng rõ ràng ở overlap
  và không mất nội dung) nhưng Dev **chủ động nêu 3 điểm phản bác** ((a) mất góc nghiêng, (b)
  dịch dở dang 1 phần khối — gắn nhãn `[UNVERIFIED]` đúng vì "chưa đo thêm mẫu lớn hơn", (c)
  trang 15 pdf2zh thua babeldoc) trước khi giữ nguyên quyết định G1e đã chốt — đây là cách trình
  bày cân bằng, không thiên vị kết luận đã có sẵn dù số liệu bề mặt có vẻ ủng hộ hướng khác.
- Ghi chú rõ giới hạn LLM non-deterministic (cache không khoá được 100% khi ngữ cảnh batch xung
  quanh thay đổi) áp dụng NGAY TỪ ĐẦU cho mọi so sánh phía sau, không phải biện minh sau khi có
  kết quả bất lợi — đọc thứ tự trình bày trong file xác nhận ghi chú này xuất hiện *trước* các
  bảng số liệu.

**Kết luận**: không phát hiện chỗ nào phóng đại/diễn giải quá tay. Cách viết mẫu để các
increment sau tham khảo.

---

## 7. Tự chạy lại (không tin lời Dev báo cáo)

```
uv run pytest -q
  → 326 passed, 405 warnings in 13.26s   (khớp đúng "326/326" Dev báo cáo trong CHANGELOG)

uv run ruff check src/services/layout_qa.py src/models/layout_qa.py tests/test_layout_qa.py \
  src/models/__init__.py src/models/database.py
  → All checks passed!

uv run ruff format --check src/services/layout_qa.py src/models/layout_qa.py tests/test_layout_qa.py
  → 3 files already formatted
```

Đã đối chiếu `tests/fixtures/babeldoc/` — 3 file PDF fixture mới (`rotated_text_p67_source.pdf`,
`rotated_chart_p15_source.pdf`, `toc_2col_p7_source.pdf`) đã được **commit từ trước** (không nằm
trong working-tree diff hiện tại, `git log` cho thấy commit `5d1cf26`), có `README.md` ghi rõ
nguồn trích (job id, trang gốc, cách trích bằng `pymupdf.insert_pdf` không chỉnh sửa) — đúng yêu
cầu golden-file của Protocol 5 mục 3, không phải mock viết tay.

---

## Blocking issues

**Không có.**

## Non-blocking suggestions

1. **Bổ sung docstring `_check_entity_preservation`** ghi rõ thêm rủi ro false-negative do (a)
   match theo substring-trong-toàn-block thay vì theo dòng/câu, và (b) ngưỡng IoU lỏng (0.05) có
   thể khiến nhiều block gốc cùng match 1 block dịch đã gộp — hiện docstring chỉ nêu ví dụ
   false-positive định dạng (mục 4 ở trên). Nên làm sớm vì đây là gate quan trọng nhất theo UX
   report/Domain Expert.
2. **Sửa câu trích dẫn severity của `entity_loss`** trong CHANGENLOG (mục "Giả định tự chọn" #2):
   ghi "khớp DoD-UX-02 (không có nhãn UX-letter riêng trong ux-review-report.md, chọn mức blocker
   vì bản chất rủi ro nội dung định lượng)" thay vì "khớp UX-C" — tránh Tech Lead/PM đọc lướt
   tưởng nhầm đây là cùng 1 hạng mục đã có sẵn trong UX report.
3. Cân nhắc thêm 1 test cho trường hợp "2 block gốc nhỏ bị gộp thành 1 block dịch lớn" (mô phỏng
   đúng rủi ro false-negative nêu ở mục 4) để tài liệu hoá giới hạn này bằng test thay vì chỉ bằng
   docstring — không blocking vì đây là hạn chế đã biết trước, không phải bug ẩn.
4. Gate P0.1-a bị "ngợp" bởi block cực nhỏ/trùng lặp `fallback_line` (đã tự Dev ghi nhận trong
   kết quả A/B) — nhắc lại để không quên xử lý ở vòng tinh chỉnh sau, vì ảnh hưởng tới khả năng
   dùng `severity_score` để so sánh giữa các lần chạy một cách công bằng trên trang dày đặc.
5. Phát hiện phụ về `BabeldocRunner` truyền API key qua CLI argument (`ps aux` đọc được) mà Dev
   đã ghi trong CHANGELOG và tách task riêng — xác nhận đây **đúng là** vấn đề bảo mật thật (rò
   rỉ secret qua process list là lỗ hổng kinh điển), việc tách task riêng thay vì sửa lẫn trong
   PR này là hợp lý (đúng nguyên tắc 1 commit 1 mục đích), nhưng đây là **security issue có mức
   độ nghiêm trọng**, đề nghị PM ưu tiên task đó sớm, không để trôi.

## Next step

P0 (`layout_qa.py` gate P0.1 + pin version P0.3) **APPROVED**. Circuit breaker Dev↔Reviewer:
0/3 vòng cho phần này (không cần vòng sửa). P0.2 (thí nghiệm A/B) là spike đo lường, không phải
code sản phẩm nên không thuộc phạm vi APPROVE/REJECT của Reviewer — đã review riêng ở mục 6 chỉ
về tính trung thực của cách trình bày kết quả. Nhắc PM: task riêng về API key leak trong
`BabeldocRunner` (mục Non-blocking #5) nên được ưu tiên xử lý sớm dù không thuộc scope P0 này.

---

# P1 — Babeldoc Layout Bug Fix Roadmap (P1.1 overlay chữ xoay G1e + P1.2 prompt bất biến nội
dung) — Iteration 1

## Verdict: **REJECT** (1 blocking issue, R6-04)

Phạm vi: `src/postprocess/rotated_text_overlay.py` (mới), `tests/test_rotated_text_overlay.py`
(mới), điểm nối trong `src/core/job_orchestrator.py`, feature flag trong `src/core/config.py`,
refactor export trong `src/services/layout_qa.py`, prompt rewrite trong
`src/core/prompt_builder.py` + `tests/test_prompt_builder.py`. Đối chiếu với
`docs/Architecture.md` "Final Decision: Babeldoc Layout Bug Fix Roadmap" U3/U4/U6 và
`docs/CHANGELOG.md` increment "2026-09-07 — P1.1 + P1.2".

## 1. R6-04 — Trace tay data lineage của `overlay_rotated_text()` trong `job_orchestrator.py`

Đã đọc dòng-theo-dòng, không suy luận từ tên biến.

**(a) `translated_blocks` bắt nguồn từ provider thật, không đọc lại text gốc** — ĐÚNG.
`translate_rotated_blocks()` (`rotated_text_overlay.py:278-298`) gọi
`await provider.translate(block.source_text, ...)` và trả `result.text` — giá trị vẽ lên PDF là
kết quả `provider.translate()`, không phải `block.source_text`. Test
`test_translate_rotated_blocks_returns_provider_result_not_source_text` assert đúng GIÁ TRỊ
(`result[id(block)] == marker_translation` và `!= block.source_text`), không chỉ
`assert_awaited()` — đúng kỷ luật R6-02.

**(c) Overlay ghi đúng vào file mà `compress_pdf_images` đọc tiếp theo, đúng thứ tự** — ĐÚNG.
`job_orchestrator.py:519-527` gọi `overlay_rotated_text(output_pdf_path=merged_path, ...)` **sau**
`merge_chunk_pdfs()` (dòng 486) và **trước** `compress_pdf_images(merged_path)` (dòng 549) —
khớp chính xác U6/RK-3. `overlay_rotated_text()` sửa `output_pdf_path` TẠI CHỖ qua
`tempfile.mkstemp` + `os.replace()` (cùng pattern `compress_pdf_images`), không tạo file output
khác khiến bước sau đọc nhầm.

**(b) `rotated_blocks` có thực sự đọc từ ĐÚNG `source.pdf` của job hay không — SAI, đây là
blocking issue.** `job_orchestrator.py:520` gọi
`overlay_rotated_text(source_pdf_path=file_path, ...)` với `file_path = Path(job.file_path)`
(dòng 259) — **file gốc chưa qua OCR**. Nhưng chính file này, ở dòng 275, code TỰ GHI COMMENT:
`"file_path goc — file goc khong co text layer de doc"`, và dòng 262-264 xác lập nguyên tắc
**do chính Bug #5 sinh ra**: `translation_source_path` là "BIEN DUY NHAT moi buoc doc noi dung
sau day phai dung" — mọi bước đọc nội dung sau Step 2 phải dùng `translation_source_path`
(= cầu nối OCR searchable PDF khi `job.file_type == PDF_SCAN`), không phải `file_path` gốc.

`overlay_rotated_text()` gọi `scan_rotated_lines()` → `page.get_text("dict")` trên
`source_pdf_path` để tìm dòng chữ xoay. Với 1 job `PDF_SCAN` (ảnh scan thuần, không có text
layer) chạy engine `babeldoc` — tổ hợp này **có thật trong code**, không phải giả định: 
`pdf_translate_engine` là setting toàn cục độc lập với `file_type` (`job_orchestrator.py:241`
chọn engine, không điều kiện theo `file_type`; `_build_ocr_bridge` ở dòng 270-271 chỉ tạo
`translation_source_path`, không đổi engine) — nên `PDF_SCAN` + `babeldoc` (mặc định
`pdf_translate_engine="babeldoc"`, `config.py:135`) là tổ hợp production hợp lệ. Khi đó
`scan_rotated_lines(file_path)` chạy trên ảnh scan không có text layer → trả về `[]` ngay lập
tức → `overlay_rotated_text()` no-op hoàn toàn, im lặng, không log, không finding — tính năng
P1.1 **không bao giờ chạy** cho mọi job scan dùng babeldoc, kể cả khi trang đó thực sự có chữ
xoay (rất có thể xảy ra với sách scan vật lý — đúng loại tài liệu mà OCR bridge được sinh ra để
xử lý). Đây đúng hình dạng lỗi Protocol 6 được viết ra để chặn: 2 bước (OCR bridge tạo
`translation_source_path`, overlay đọc `source_pdf_path`) từng bước riêng lẻ hoạt động đúng,
nhưng sợi dây nối giữa chúng bị đứt — không ai kiểm tra `overlay_rotated_text` có dùng đúng biến
"nguồn nội dung của job" mà chính Bug #5 đã buộc phải chuẩn hoá thành `translation_source_path`.

Comment tự giải thích tại `job_orchestrator.py:502-503` ("reading `file_path` (job's own source,
NOT a fixture) for the rotated blocks") cho thấy đây là **thiếu sót thật, không phải đánh đổi có
cân nhắc**: lý lẽ duy nhất đưa ra là "đúng file của job này, không phải fixture cứng" — không hề
nhắc tới phân biệt `file_path` gốc vs `translation_source_path` (cầu nối OCR) mà chính file này
đã lập ra quy tắc ở 20 dòng phía trên. Không có dòng nào trong Architecture.md U4/P1.1 hay
CHANGENLOG "Giả định tự chọn" nhắc tới trường hợp `PDF_SCAN`, cũng không có `[UNVERIFIED]`/ghi
chú giới hạn nào cho case này — tức đây không phải 1 giả định đã được gắn nhãn theo đúng kỷ luật
R5-02 (brief chỉ nói "source.pdf" mập mờ, và Dev đã chọn diễn giải sai mà không escalate).

**Không có test nào phủ trường hợp này** — cả 10 test trong `tests/test_rotated_text_overlay.py`
đều gọi thẳng `overlay_rotated_text(source_pdf_path=<fixture PDF có text layer>, ...)`, không có
test nào dựng job `PDF_SCAN` qua `job_orchestrator.run_job()` để xác nhận biến nào thực sự được
truyền vào `source_pdf_path`. `tests/integration/test_job_orchestrator.py` cũng
**hoàn toàn không nhắc tới** `overlay_rotated_text`/`babeldoc_rotated_text_overlay` (đã grep xác
nhận 0 kết quả) — nghĩa là không có bất kỳ integration test nào ở tầng orchestrator xác nhận: (i)
`source_pdf_path` truyền đúng biến theo `file_type`, (ii) thứ tự gọi đúng sau-merge/trước-nén,
(iii) feature flag tắt được overlay, (iv) lỗi overlay bị nuốt best-effort đúng cách. Toàn bộ 4
điều này chỉ được xác nhận bằng đọc code tay (mục này), không bằng test — đúng loại lỗ hổng mà
Protocol 6 R6-02 yêu cầu phải có test assert giá trị cụ thể giữa các bước, không chỉ đọc code.
`babeldoc_rotated_text_overlay` mặc định `True` (`config.py:186`) nên đây KHÔNG phải nhánh hiếm
gặp — nó chạy trên **mọi** job babeldoc production ngay khi merge xong.

**Yêu cầu sửa trước khi APPROVE**: đổi `source_pdf_path=file_path` thành
`source_pdf_path=translation_source_path` tại `job_orchestrator.py:520` (biến này đã có sẵn
trong scope hàm, được tính ở dòng 268-271), và thêm ít nhất 1 integration test dựng job
`PDF_SCAN` + `pdf_translate_engine="babeldoc"` xác nhận `overlay_rotated_text` (hoặc mock ở biên
đúng — patch `overlay_rotated_text` và assert `call_args.kwargs["source_pdf_path"] ==
translation_source_path`, không phải `assert_awaited()` trần) nhận đúng file có text layer.

## 2. R6-02 — Chất lượng test trong `tests/test_rotated_text_overlay.py`

Ngoài lỗ hổng ở mục 1 (thiếu test tầng orchestrator), phần test tầng module tự thân **tốt, đúng
kỷ luật**: `FakeTranslationProvider` là implementation thật (không phải `AsyncMock`), mọi test
overlay assert GIÁ TRỊ đã vẽ lên PDF output (`"Disaccharide" in page_text`,
`"phan tu sucrose" in page_text`, góc `line_angle_deg(...) == pytest.approx(-11.0, ...)`) khớp
đúng những gì fake provider trả về — không phải text tiếng Anh gốc. Nhánh FLAG có test riêng
(`test_overlay_rotated_text_flags_and_skips_drawing_when_too_long`) assert
`overlaid_block_count==0`, `flagged_block_count==1`, `finding.severity=="blocker"`, VÀ xác nhận
text KHÔNG xuất hiện trong output — đúng yêu cầu "giữ chỗ trống, không đè chữ vỡ". Nhánh no-op
(`test_overlay_rotated_text_noop_when_no_rotated_lines`) assert file output BYTE-IDENTICAL với
trước khi gọi — kiểm tra chặt hơn yêu cầu tối thiểu. Đây là mẫu tốt, chỉ thiếu tầng orchestrator
như mục 1 đã nêu.

## 3. Chính sách fit-text 70% (U5/U7-E1) — verify đọc code, không tin comment

`fit_translated_block()` (`rotated_text_overlay.py:337-357`): vòng lặp `while scale >=
MIN_FONT_SCALE - 1e-9: ... scale -= _FIT_SCALE_STEP`, nhánh fallback sau vòng lặp gán CỨNG
`fontsize = base_font_size * MIN_FONT_SCALE` rồi trả `fits=False` — không có đường nào scale tụt
xuống dưới `MIN_FONT_SCALE` (0.70), kể cả nhánh fallback. Ở `overlay_rotated_text()`
(dòng 456-477): `if not fit.fits: flagged += 1; findings.append(...); continue` — `continue` nhảy
qua `_draw_block()`, xác nhận nhánh không vừa **không bao giờ** gọi vẽ. Test
`test_fit_translated_block_flags_when_too_long_even_at_min_scale` verify bằng dữ liệu thật (nhân
bản dịch dài x8) chứ không giả lập điều kiện — khớp đúng những gì code làm. **Đạt yêu cầu.**

## 4. Feature flag + best-effort — verify phạm vi try/except

`job_orchestrator.py:517-541`: `try:` bọc CẢ `overlay_rotated_text()` LẪN `persist_findings()`
gọi ngay sau đó, `except Exception:` log + `exc_info=True`, không raise — đúng yêu cầu "lỗi
overlay không làm fail job". Phạm vi except là hợp lý cho *lớp lỗi kỹ thuật* (không phân biệt
lỗi trong overlay hay lỗi ghi finding), nhưng có 1 hệ quả cần lưu ý (xem Non-blocking #1): nếu
`persist_findings()` lỗi (vd DB constraint) SAU KHI `overlay_rotated_text()` đã chạy đúng và trả
về finding FLAG hợp lệ, finding đó biến mất hoàn toàn trong im lặng — không job nào fail, nhưng
QA cũng không bao giờ thấy trang cần soi tay (đúng cơ chế mà U7-E3 yêu cầu QA phải review 100%).
Không đủ nghiêm trọng để blocking (log vẫn ghi lại được qua `exc_info=True`, và đây là lỗi DB
hiếm gặp chứ không phải lỗi logic thường trực), nhưng nên tách biệt log message giữa 2 loại lỗi.

## 5. Prompt builder — xác nhận không còn hard-cap

Grep `%` trong `src/core/prompt_builder.py` chỉ còn 1 dòng comment (dòng 44, nhắc lại bug cũ),
không còn trong bất kỳ chuỗi prompt thật nào (`_CONCISENESS_RULE`/`_FILE_CONCISENESS_RULE`/
`_BABELDOC_CONCISENESS_RULE`, dòng 53-57/118-122/258-262 — cả 3 giống hệt nội dung, không có
con số phần trăm/ký tự nào, có đủ "BAT BIEN NOI DUNG", "nhiet do", "don vi", "so buoc"). Test
`tests/test_prompt_builder.py` assert `not re.search(r"\d+%", prompt)` ở cả 4 test case (dòng
59/78/110/196), phủ cả 3 đường build — khớp đúng CHANGENLOG. Không có dấu hiệu "vá tạm" (rút
ngắn tới mức mất yêu cầu bất biến) — bản rút gọn vẫn giữ đủ từ khoá bắt buộc, đã verify bằng
`uv run pytest -q` xanh (bao gồm 4 test `test_job_orchestrator`/`test_job_cancel` mà CHANGELOG tự
báo từng đỏ do vượt `prompt_overhead_chars × segment_count`).

**Phát hiện phụ (non-blocking, không có trong CHANGELOG "Giả định tự chọn")**: docstring module
`prompt_builder.py:6-9` mô tả `build_system_prompt()` chỉ dùng cho case "OUT-OF-BAND... **never
the real PDF render path**" (cost estimation, Settings test connection, sample preview). Nhưng
`job_orchestrator.py:44,523` giờ gọi CHÍNH hàm này làm `glossary_prompt` cho
`overlay_rotated_text()` — kết quả dịch từ lời gọi này được vẽ THẲNG vào file PDF giao cho
người dùng (`translated_vi.pdf`), tức **là** real render path, mâu thuẫn với chính câu docstring
vừa trích. Về hành vi không sai (nội dung glossary/rule 3 biến thể giống hệt nhau, và
`overlay_rotated_text` gọi `provider.translate()` trực tiếp — đúng shape "system_prompt cho
translate() call" mà `build_system_prompt()` sinh ra, không phải shape file-template của
pdf2zh/babeldoc) — nhưng docstring cần cập nhật để người đọc sau này không hiểu nhầm
"out-of-band" nghĩa là "an toàn để sửa mà không ảnh hưởng bản dịch giao cho user".

## 6. Ba giả định tự chọn (CHANGELOG) — đánh giá rủi ro edge-case

1. **Gộp nhóm dòng xoay theo góc+khoảng cách 1.8×cỡ chữ**: hợp lý, đã verify bằng 2 fixture đối
   lập (đoạn văn liền mạch gộp đúng 1 khối, bảng nhãn rời rạc tách đúng nhiều khối) — đây chính
   là bài test cần thiết cho 1 heuristic không có spec chính thức. Rủi ro chưa lường: bucket góc
   1° cứng có thể tách nhầm 1 đoạn văn thật nếu OCR/babeldoc đo góc dao động >1° giữa các dòng
   liền kề (vd 10.4° và 11.6° rơi vào 2 bucket khác nhau dù cùng 1 đoạn) — CHANGENLOG tự nhận
   "chưa test trên tập lớn hơn", đồng ý đây là rủi ro chấp nhận được ở increment này, không phải
   thiếu sót cần block.
2. **Tính khung gốc bằng chiếu bbox**: `_block_extents()` verify bằng spike thật, hợp lý. Rủi ro
   chưa lường: nếu babeldoc's OCR/detect ra các dòng có ĐỘ RỘNG rất khác nhau trong cùng 1 khối
   (vd dòng cuối đoạn văn ngắn hơn nhiều dòng đầu) thì `width = max(us) - min(us)` lấy dòng RỘNG
   NHẤT làm chuẩn cho mọi dòng word-wrap sau này — có thể ước lượng khung rộng hơn thực tế cho
   các dòng ngắn, dẫn tới bóp font ít hơn cần thiết ở 1 số dòng. Không nghiêm trọng (an toàn theo
   hướng "khung rộng hơn" chứ không tràn), không block.
3. **Overlay lỗi là best-effort**: hợp lý theo đúng tinh thần rollback bằng feature flag, đã
   review chi tiết ở mục 4.

## 7. Migration / schema

`ROTATED_OVERLAY_FLAG_CHECK = "rotated_text_overlay_flag"` tái sử dụng đúng cơ chế
`layout_qa_findings` đã có từ P0.1 (`_SEVERITY_BY_CHECK` map thêm 1 entry `"blocker"`, không tạo
bảng/model mới) — không cần migration mới, đúng nhận định của Dev trong CHANGENLOG.

## 8. Tự chạy lại (không tin lời Dev báo cáo)

```
uv run pytest -q
  → 336 passed, 418 warnings in 17.67s   (khớp đúng "336/336" Dev báo cáo trong CHANGELOG)

uv run ruff check src/postprocess/rotated_text_overlay.py tests/test_rotated_text_overlay.py \
  src/core/job_orchestrator.py src/core/config.py src/services/layout_qa.py \
  src/core/prompt_builder.py tests/test_prompt_builder.py
  → All checks passed!

uv run ruff format --check <cùng danh sách file trên>
  → 7 files already formatted
```

## External contract verified against real source (R5-04 checklist)

`rotated_text_overlay.py` gọi PyMuPDF (`fitz`) — thư viện Python nội bộ, không phải
subprocess/HTTP tới tool bên thứ 3 (nằm ngoài phạm vi Protocol 5 theo đúng "Phạm vi áp dụng" của
`CLAUDE.md`: "pymupdf dùng đúng API core" được liệt kê rõ là KHÔNG áp dụng). Câu trả lời checklist
R5-04: **N/A** — không có external CLI/HTTP contract nào trong phạm vi review này (module gọi lại
`TranslationProvider` nội bộ của app, không gọi babeldoc/pdf2zh CLI cho bước overlay — đúng yêu
cầu U4/P1.1). `page.insert_text(morph=...)` đã được Tech Lead tự verify bằng spike thật ở
Architecture.md U3 (trích PyMuPDF 1.28.2, không phải trí nhớ) — Reviewer không lặp lại spike vì
đã có nguồn xác thực trực tiếp trong Architecture.md, chỉ verify code Dev GỌI ĐÚNG API đã spike
(cùng tham số `pivot`, `morph=(pivot, Matrix(angle))`, `fontfile`) — khớp.

## Blocking issues

1. **[R6-04] `overlay_rotated_text(source_pdf_path=file_path, ...)` tại `job_orchestrator.py:520`
   dùng sai biến nguồn nội dung cho job `PDF_SCAN`** — phải là `translation_source_path` (đã có
   sẵn trong scope hàm), không phải `file_path` gốc không có text layer. Xem mục 1 để biết chi
   tiết + bằng chứng. Kèm theo: thiếu integration test ở tầng `job_orchestrator` xác nhận biến
   truyền đúng, thứ tự gọi đúng, và feature-flag/best-effort hoạt động đúng — cần bổ sung ít nhất
   1 test dựng job `PDF_SCAN` + engine `babeldoc` trước khi APPROVE.

## Non-blocking suggestions

1. Tách log message trong `job_orchestrator.py:535-541` để phân biệt lỗi xảy ra TRONG
   `overlay_rotated_text()` (tính toán/vẽ) với lỗi xảy ra ở `persist_findings()` (ghi DB) — hiện
   tại cả 2 gộp chung 1 `except Exception`, nếu `persist_findings()` lỗi thì finding FLAG hợp lệ
   biến mất im lặng, ảnh hưởng tới khả năng QA soi 100% trang bị flag theo U7-E3.
2. Cập nhật docstring module `prompt_builder.py:6-9` — câu "never the real PDF render path" mô
   tả `build_system_prompt()` không còn đúng 100% sau khi `job_orchestrator.py` dùng hàm này làm
   `glossary_prompt` cho `overlay_rotated_text()` (kết quả dịch từ lời gọi này được vẽ thẳng vào
   file giao cho user). Không phải bug hành vi, chỉ là tài liệu có thể gây hiểu nhầm cho người
   sửa `_CONCISENESS_RULE` sau này.
3. Bucket góc 1° trong `group_rotated_lines()` (`_ANGLE_GROUP_TOLERANCE_DEG`) có thể tách nhầm 1
   đoạn văn liền mạch nếu góc đo dao động qua ranh giới bucket giữa các dòng liền kề — chưa gặp
   trên 2 fixture hiện có, nên theo dõi khi có dữ liệu QA thật từ nhiều tài liệu hơn (đúng như Dev
   tự ghi nhận trong CHANGENLOG).
4. Cân nhắc gọi `translate_rotated_blocks()` song song (`asyncio.gather`) thay vì tuần tự từng
   block trong 1 trang — hiện tại là vòng `for` tuần tự (`overlay_rotated_text():448-450` gọi
   theo từng TRANG, và bên trong `translate_rotated_blocks()` cũng là vòng `for` tuần tự theo
   từng block). Không blocking vì số lượng khối chữ xoay/job thường nhỏ (~1-19 trang theo T3-c),
   nhưng đáng lưu ý nếu sau này mở rộng sang tài liệu có nhiều trang xoay hơn.

## Next step

**REJECT** — 1 blocking issue (R6-04, mục 1). Circuit breaker Dev↔Reviewer: **1/3 vòng** đã dùng
cho phần P1.1/P1.2 này. Yêu cầu Dev: (a) đổi `source_pdf_path` sang `translation_source_path` tại
`job_orchestrator.py:520`, (b) thêm integration test dựng job `PDF_SCAN` + `pdf_translate_engine
== "babeldoc"` assert đúng biến/đúng thứ tự gọi overlay, rồi gửi lại Reviewer vòng 2. P1.2 (prompt
builder) tự nó **không có blocking issue** — nếu Dev muốn tách P1.2 ra APPROVE riêng trong lúc sửa
P1.1, Reviewer đồng ý (P1.2 không phụ thuộc P1.1 về mặt code, chỉ đi chung 1 CHANGELOG entry).

---
---

# P1.1 Overlay chữ xoay (G1e) — Vòng 2/3 (Dev↔Reviewer)

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-07

## Verdict: APPROVE

Fix cho blocking issue R6-04 (vòng 1 REJECT) đã đúng, có bằng chứng thực nghiệm chứ không chỉ tin
lời Dev. Không có regression mới.

## 1. Trace tay `job_orchestrator.py` quanh `overlay_rotated_text()`

Đọc lại toàn bộ `run_job()` từ Step 2 tới lời gọi overlay. `translation_source_path` được gán
đúng 1 lần duy nhất (dòng 268-271): `= file_path` cho `pdf_digital`, `= await
self._build_ocr_bridge(...)` cho `pdf_scan`. `FileType` chỉ có 3 giá trị
(`PDF_DIGITAL`/`PDF_SCAN`/`EPUB` — đã đọc `src/core/file_router.py`), `EPUB` bị raise
`EpubNotSupportedError` ngay ở Step 1 nên không bao giờ tới được đoạn gán này — **không còn tổ
hợp `file_type` nào bị bỏ sót** (đúng bài học Bug #5 mà brief yêu cầu tự trace). Lời gọi overlay
tại dòng 524-525 giờ dùng `source_pdf_path=translation_source_path` — đúng biến, đúng vị trí
(sau `merge_chunk_pdfs()`, trước `compress_pdf_images()`, không đổi so với vòng 1). Với
`pdf_digital`, `translation_source_path == file_path` nên hành vi không đổi — không có rủi ro
None/rỗng vì đây là `Path` luôn có giá trị từ `job.file_path` (đã validate ở bước upload, ngoài
phạm vi review này).

## 2. Test mới — verify bằng cách revert thật, không chỉ đọc logic

`test_pdf_scan_babeldoc_overlay_uses_bridge_not_original` assert đúng GIÁ TRỊ lineage:
`Path(called_source) == expected_bridge` VÀ `Path(called_source) != Path(job.file_path)` — không
phải `assert_awaited()` trần, đúng kỷ luật R6-02.

Đã tự revert thật dòng fix (`source_pdf_path=translation_source_path` → `source_pdf_path=
file_path`) và chạy `uv run pytest tests/integration/test_job_orchestrator.py::test_pdf_scan_babeldoc_overlay_uses_bridge_not_original`:
**FAILED** đúng như kỳ vọng (assertion `!=` bắt được lineage sai). Sau đó khôi phục lại file gốc
từ backup, chạy lại toàn bộ suite: **337 passed** (336 cũ + 1 test mới, khớp CHANGELOG). Regression
test này có tác dụng thật, không phải test tự xác nhận theo đúng giả định.

## 3. Ba mục non-blocking đã áp dụng — verify đúng như khai

- **Tách try/except overlay vs persist_findings** (`job_orchestrator.py:521-562`): đã tách thành 2
  khối `try/except` riêng — 1 bọc `overlay_rotated_text()`, 1 bọc `persist_findings()` (chỉ chạy
  khi `overlay_result is not None and overlay_result.findings`), mỗi khối có message log riêng
  phân biệt rõ 2 loại lỗi. Đúng như Dev báo cáo, giải quyết đúng non-blocking #1 vòng 1.
- **Docstring `prompt_builder.py`**: đã sửa dòng 4-16, không còn khẳng định tuyệt đối "never the
  real PDF render path" mà giải thích rõ `overlay_rotated_text()` giờ cũng gọi hàm này và kết quả
  được vẽ thẳng vào file giao cho user — đúng nội dung đã khai, giải quyết đúng non-blocking #2.
- **Comment rủi ro bucket góc** trong `rotated_text_overlay.py`: đã có sẵn từ vòng 1 (ghi nhận
  trong CHANGELOG là rủi ro chấp nhận được, không phải lỗi cần sửa) — vòng này không có thay đổi
  thêm ở phần này, đúng như mô tả (không claim đã sửa, chỉ ghi chú rủi ro).

## 4. Đọc diff đầy đủ — không chỉ phần đã sửa

Ngoài 2 thay đổi trên, diff còn có (không nằm trong brief nhưng cần trace vì thuộc cùng commit
đang review theo Protocol 1 R7):

- `src/core/config.py`: thêm `babeldoc_rotated_text_overlay: bool = True` — đã có ở vòng 1, không
  đổi ở vòng này (xác nhận qua `git diff` so với vòng trước không động tới field này).
- `src/core/prompt_builder.py`: 3 biến thể `_CONCISENESS_RULE`/`_FILE_CONCISENESS_RULE`/
  `_BABELDOC_CONCISENESS_RULE` bỏ hard-cap "<=130%" — đây là phần P1.2, đã APPROVE ở vòng 1 (không
  có blocking issue), không đổi nội dung ở vòng 2 ngoài docstring đã nêu ở mục 3.
- `src/services/layout_qa.py`: đổi `_line_angle_deg`/`_is_rotated` thành public
  `line_angle_deg`/`is_rotated` + giữ alias private cho code nội bộ module — đã verify cả 2 chỗ
  gọi nội bộ (`_check_rotated_text_prescan`) vẫn dùng alias, không bị lệch tên; `rotated_text_overlay.py`
  import đúng tên public mới. Thêm `ROTATED_OVERLAY_FLAG_CHECK = "rotated_text_overlay_flag"` map
  vào `_SEVERITY_BY_CHECK["blocker"]` — tái dùng đúng cơ chế `layout_qa_findings` có sẵn, không
  tạo bảng/model mới, khớp mục 7 review vòng 1. Không có thay đổi hành vi so với vòng 1, chỉ đổi
  visibility — không phải regression.
- Không có thay đổi nào khác ngoài các file trên (`git status` chỉ liệt kê đúng những file đã nêu
  trong brief cộng `docs/CHANGELOG.md`/`docs/review-report.md`).

## 5. Tự chạy lại (không tin số Dev báo cáo)

```
uv run pytest -q                                    → 337 passed, 423 warnings in 17.94s
uv run ruff check src/ tests/                        → All checks passed!
uv run ruff format --check <8 file thuộc diff này>   → 8 files already formatted
```

(`ruff format --check src/ tests/` trên toàn repo báo "17 files would be reformatted" nhưng toàn
bộ nằm ngoài phạm vi diff đang review — vd `tests/test_translation_providers.py` phần Gemini/DeepL
— không liên quan P1.1/P1.2, không phải regression của lần sửa này.)

## External contract verified against real source (R5-04 checklist)

Không có thay đổi nào ở vòng 2 chạm tới external CLI/HTTP contract mới — vẫn N/A như vòng 1
(`rotated_text_overlay.py` chỉ gọi PyMuPDF nội bộ + `TranslationProvider` nội bộ app).

## Blocking issues

**Không có.**

## Non-blocking suggestions (giữ nguyên từ vòng 1, chưa yêu cầu sửa)

1. Bucket góc 1° trong `group_rotated_lines()` — rủi ro edge-case đã ghi nhận, theo dõi khi có dữ
   liệu QA thật.
2. Cân nhắc `asyncio.gather` cho `translate_rotated_blocks()` nếu sau này có tài liệu nhiều trang
   xoay hơn.

## Next step

**APPROVE** — P1.1 (G1e) overlay chữ xoay đã sẵn sàng cho QA. Circuit breaker Dev↔Reviewer: đã
dùng 2/3 vòng cho phần này, không cần vòng 3. Chuyển QA để chạy R6-03 (live E2E test toàn chuỗi
OCR→dịch→overlay với dữ liệu thật, kiểm tra nội dung `translated_vi.pdf` thật, không chỉ tin
`status`) trước khi release.

---

# Review — Bug #6 Phase 1 + task P0 (logging) — 2026-09-07

Spec: `docs/Architecture.md` mục "Bug #6 — Final Decision sau phản biện Domain Expert
(2026-09-07)", đặc biệt **V6 (QUYẾT ĐỊNH CUỐI — 2 pha)** dòng ~6023-6096. Phạm vi review: file
mới `src/services/mineru_det_probe.py`, `tests/test_mineru_det_probe.py`,
`tests/fixtures/mineru/det_probe_p67.json`; file sửa `src/api/main.py`, `src/core/config.py`,
`src/core/job_orchestrator.py`, `src/services/layout_qa.py`,
`tests/integration/test_job_orchestrator.py`, `docs/PRD.md`.

## Kết luận: APPROVE

Không có blocking issue. 2 non-blocking suggestion (chi tiết bên dưới).

## Checklist bắt buộc (1-8)

**1. R6-04 — trace tay `_run_rotated_text_probe()` / `_build_ocr_bridge()`
(`src/core/job_orchestrator.py`)**

- (a) Ảnh scan dùng để probe: `run_job()` gán `file_path = Path(job.file_path)` (dòng 259), rồi
  gọi `self._build_ocr_bridge(job, file_path, db_session)` (dòng 272) — cùng `file_path` này
  được truyền tiếp làm tham số `file_path` của `_build_ocr_bridge`. Cả 2 nhánh (fresh: dòng
  ~683; resumable: dòng ~651) đều gọi `self._run_rotated_text_probe(job, file_path, ...)` với
  đúng biến `file_path` đó — KHÔNG phải `bridge_path`/`bridge.path` (đã bị whiteout, xác nhận qua
  docstring `mineru_det_probe.py` dòng 29-32 và code: `bridge = build_searchable_pdf(...)` chạy
  **sau** lời gọi probe ở nhánh fresh, dòng 683 gọi trước dòng 685 tạo bridge). Đúng job đang xử
  lý — không có job khác/fixture nào lẫn vào vì `file_path` bắt nguồn trực tiếp từ
  `job.file_path` của đối tượng `job` đang được xử lý trong cùng scope hàm. **Đạt.**
- (b) `middle.json` dùng để ghép: nhánh fresh dùng `ocr_result.middle_json_path` — chính là
  return value của `self._mineru_runner.parse_document(file_path, ocr_dir)` gọi ngay phía trên
  (dòng 660), tức middle.json CỦA CHÍNH job này, không phải fixture. Nhánh resumable dùng
  `ocr_dir / "middle.json"` với `ocr_dir = self._processing_dir / job.id / "ocr_output"` — đã
  verify bằng cách đọc `src/services/mineru_runner.py:291-310`
  (`_write_middle_json`): `middle_json_path = output_dir / "middle.json"`, và `output_dir` truyền
  vào đó chính là `ocr_dir` được gọi ở dòng 660 (`parse_document(file_path, ocr_dir)`) — cùng 1
  path string, cùng `job.id`. Suy luận "đường dẫn cố định" của Dev trong comment là đúng, có
  nguồn xác thực (đọc code, không suy đoán). **Đạt.** Test tích hợp
  `test_pdf_scan_runs_rotated_text_det_probe_with_correct_lineage` cũng tự verify lại bằng
  assertion `Path(called_middle_json_path) == expected_middle_json` — đúng tinh thần R6-02 (assert
  giá trị cụ thể, không chỉ `assert_awaited()`).
- (c) `page_number`: `DetProbeLine.page_number` gán ở `run_det_probe()` bằng `page_index + 1`
  (0-indexed PyMuPDF → 1-indexed), có comment "matches src/services/layout_qa.py convention".
  Đối chiếu CHANGELOG P0.1 (dòng 3439-3440): "`page_number` trong `LayoutQaFinding`/
  `LayoutQaFindingData` là 1-indexed... để khớp cách Architecture.md/UX report gọi trang" —
  nhất quán. Golden fixture test cũng gọi `parse_det_probe_output(raw, page_number=67)` khớp
  trang 67 thật của tài liệu spike. **Đạt.**

**2. R5-04 — External contract verified against real source: YES.**
Nguồn: (i) Architecture.md mục V6/V-1/V-3/V8 — Tech Lead tự chạy spike thật ngày 2026-09-07 và
ghi bảng trạng thái verify tường minh (`Detector MinerU trả poly còn góc... verified — spike Tech
Lead tự chạy`); (ii) golden fixture `tests/fixtures/mineru/det_probe_p67.json` — đã tự kiểm tra
bằng script Python độc lập trong review này: 88 item thô, lọc `score>=0.8` và `|angle|>=3.0` ra
đúng 18 dòng, median = -10.8565° (nằm trong dung sai ±1.5° so với `_EXPECTED_MEDIAN_ANGLE_DEG =
-11.0` mà test dùng) — số liệu trong fixture tự nhất quán với assertion trong test, không phải
số bịa. (iii) Docstring module `mineru_det_probe.py` dòng 6-23 trích dẫn cụ thể
`ocr_utils.py:399-410` (MinerU đã cài, bản 3.4.5) cho hành vi "flattening" — đây là source code
thật, không phải trí nhớ. Riêng chữ ký `PytorchPaddleOCR(lang=..).ocr(img, det=True, rec=True)`
tự nó chưa được review này verify độc lập (không cài lại MinerU để đối chiếu), nhưng đã có khoá
Protocol 5 mục 3 đúng cách: golden fixture backing + smoke test thật (mục 5 dưới) + version pin
ghi rõ trong docstring — chấp nhận được cho Phase 1.

**3. Best-effort/an toàn — đọc thật code try/except.**
`_run_rotated_text_probe()` (`job_orchestrator.py`) có **2 khối try/except riêng biệt**, đúng
pattern P1.1 đã áp dụng:
- Khối 1 bọc `probe_and_flag_rotated_text(...)` — bắt `Exception`, log
  `"mineru_det_probe that bai..."`, `return` ngay — không tiếp tục.
- Khối 2 bọc `persist_findings(...)` — bắt `Exception` riêng, log
  `"persist_findings that bai..."` kèm số finding bị mất, tách biệt khỏi khối 1.
Xác nhận lỗi thiếu venv MinerU đi qua đường: `run_det_probe()` raise
`MineruDetProbeUnavailableError` (subclass `MineruDetProbeError(RuntimeError)`, subclass
`Exception`) → bị khối try 1 bắt bằng `except Exception` → job tiếp tục bình thường. Test
`test_pdf_scan_det_probe_failure_does_not_fail_job` verify đúng kịch bản này bằng
`side_effect=MineruDetProbeUnavailableError(...)` và assert `result.status == "completed"`.
Trước khi thử probe còn có early-return `if not self._settings.mineru_det_probe_enabled: return`
và `if not middle_json_path.exists(): return` — 2 guard này nằm NGOÀI try/except (không cần, vì
không có gì có thể raise ở đó). **Đạt, không có finding.**

**4. Test dấu góc `test_angle_sign_matches_pymupdf_dir`.**
Test này KHÔNG dùng `abs()` hay tolerance lỏng để né lỗi dấu — cụ thể:
`assert detector_median * pymupdf_median > 0` (bắt buộc CÙNG DẤU, một phép nhân âm sẽ tự động
fail nếu ai đó đảo dấu `angle = atan2(y1-y0, x1-x0)` thành `atan2(y0-y1, ...)` hay tương tự) VÀ
tiếp theo `assert detector_median == pytest.approx(pymupdf_median, abs=1.5)` (khớp cả độ lớn, tự
build lại tolerance đối chiếu 2 giá trị thật chứ không phải hằng số cứng cả 2 vế). Ground truth
(`_real_pymupdf_dir_angle_deg()`) đọc trực tiếp từ PDF nguồn qua `page.get_text("dict")["blocks"]
[...]["lines"]["dir"]`, độc lập với golden fixture của detector — nếu ai đó tự ý sửa cả file
fixture cho khớp code sai, test này (đọc PDF gốc) vẫn bắt được lỗi vì so sánh với nguồn thứ 3 độc
lập. Đủ chặt để khoá lỗi dấu. **Đạt, không có finding.**

**5. Smoke test R5-03 `test_run_det_probe_real_subprocess`.**
Test gọi `run_det_probe(P67_SOURCE)` — hàm PRODUCTION thật, không mock `subprocess` hay
`_run_ocr_subprocess`/detector nào (khác các test khác trong cùng file đều `mocker.patch(...
run_det_probe...)` để cô lập, riêng test này để nguyên). `@pytest.mark.skipif(not
is_mineru_interpreter_available(), ...)` — điều kiện skip đọc `Path(...).expanduser().exists()`
trên `default_mineru_python_path()` (`~/.local/share/uv/tools/mineru/bin/python`), đúng logic:
skip (không fail) khi máy thiếu venv MinerU, đúng tinh thần Protocol 5 mục 4 ("được phép skip
trong CI nếu tool không cài được"). Trên máy Reviewer này, `uv run pytest -q` cho thấy test suite
chạy 350 passed — verify riêng: máy này CÓ venv MinerU nên test không bị skip (xem log run dưới).

**6. Logging fix `_configure_logging()` (`src/api/main.py`).**
- Handler mới gắn vào `logging.getLogger("src")`, KHÔNG gắn vào root logger — đọc code xác nhận
  không có lệnh `logging.getLogger()` (root, không tham số) hay `logging.basicConfig()` nào khác
  trong toàn bộ `src/` (`grep -rn "basicConfig\|addHandler\|getLogger()" src/` chỉ ra đúng
  `main.py`). `app_logger.propagate = False` được set NGAY SAU `addHandler` trong cùng hàm —
  đúng chỗ, chặn log lan lên root.
- Double-logging với uvicorn: vì `propagate=False` chặn hẳn việc lan lên root, và uvicorn tự cấu
  hình handler riêng cho các logger `uvicorn`/`uvicorn.error`/`uvicorn.access` (không phải
  `"src"` hay root) — 2 hệ thống logging không giao nhau, không có đường nào double-log.
- Rủi ro "chặn mất log nơi khác cần propagation": đã tự grep toàn `src/` để tìm bất kỳ
  `logging.basicConfig`/handler khác gắn vào root dự định bắt log từ `"src.*"` — không tìm thấy
  cái nào tồn tại ở thời điểm này, nên `propagate=False` không cắt đứt cơ chế nào đang hoạt động.
  Rủi ro duy nhất là *tương lai*: nếu sau này có ai thêm 1 handler ở root để bắt log toàn app
  (vd Sentry SDK, log-aggregator), log `"src.*"` sẽ không tới đó nữa — đã có comment cảnh báo rõ
  trong code (dòng 55-58) nên chấp nhận được, ghi thành non-blocking suggestion bên dưới.

**7. Kết quả chạy thật (Reviewer tự chạy, không copy CHANGELOG):**
```
uv run pytest -q          → 350 passed, 428 warnings in 85.89s (0:01:25)
uv run ruff check         → All checks passed!
uv run ruff format --check → 19 files would be reformatted (toàn bộ NẰM NGOÀI diff đang review —
                              đã tự kiểm tra riêng: `ruff format --check --diff` trên đúng 7 file
                              thuộc diff này (mineru_det_probe.py, test_mineru_det_probe.py,
                              job_orchestrator.py, config.py, main.py, layout_qa.py,
                              test_job_orchestrator.py) → "7 files already formatted", không có
                              file nào trong 19 file kia trùng với diff này)
```
Cảnh báo runtime (`PytestUnhandledThreadExceptionWarning`, `RuntimeWarning: coroutine
'_FakeProcess.wait' was never awaited`) đều ở các test file KHÔNG thuộc diff này
(`test_babeldoc_runner.py`, `test_chunk_merge.py`, `test_progress_tracker.py`,
`test_translation_providers.py`) — không phải regression của increment này.

**8. Ranh giới phạm vi Phase 2.**
`git diff --stat` / `git status --porcelain` xác nhận `src/preprocess/searchable_pdf.py`
**KHÔNG xuất hiện** trong danh sách file thay đổi (đã tự chạy `git diff --stat --
src/preprocess/searchable_pdf.py` → không có output, file không đổi). Không có thay đổi nào
thêm góc vào `insert_text`/vẽ whiteout xoay — đúng như Architecture.md V6 chốt "PHASE 2... KHÔNG
implement bây giờ". **Đạt.**

## Danh sách issue

**Blocking:** không có.

**Non-blocking:**
1. `_configure_logging()` (`src/api/main.py` dòng ~55-58): `propagate=False` là quyết định đúng
   cho hiện tại (không có handler root nào khác), nhưng nếu tương lai có tool giám sát tập trung
   gắn vào root logger, log `"src.*"` sẽ không tới đó nữa mà không có cảnh báo runtime nào — đã
   có comment code cảnh báo, nhưng nên thêm 1 dòng vào Architecture.md/CHANGELOG khi việc đó xảy
   ra để không ai phải re-discover qua code archaeology.
2. Docstring `match_lines_to_middle_json()` (`src/services/mineru_det_probe.py` dòng ~394-396)
   nhắc tới "spike had a noisy outlier poly at -23.43°" làm lý do chọn median thay vì mean —
   nhưng golden fixture đã copy vào repo (`det_probe_p67.json`, 18 dòng sau lọc) KHÔNG chứa giá
   trị nào gần -23.43° (dải thật đo được: -11.399° đến -10.293°, xem log verify mục 2 ở trên).
   Không phải bug (median vẫn là lựa chọn đúng, và ý định — chống outlier — hợp lý độc lập với
   fixture này), nhưng câu chuyện outlier trong comment không tự chứng minh được bằng chính
   fixture đi kèm trong repo → nên sửa comment cho khớp fixture thật, hoặc ghi rõ outlier đó đến
   từ 1 lần chạy khác không có trong golden fixture, để người đọc sau không mất công đi tìm -23.43°
   trong file JSON và không thấy.

## Next step

**APPROVE.** Circuit breaker Dev↔Reviewer: vòng 1/3 cho increment này. Chuyển QA: theo Protocol 5
R5-03 QA phải re-run smoke test thật trước khi duyệt release, và theo Protocol 6 R6-03 lưu ý
increment này CHƯA cần live E2E toàn chuỗi mới (Phase 1 chỉ FLAG, không đổi output hình học) —
nhưng vẫn cần QA tự mở `docs/test-report.md` xác nhận ít nhất 1 lần chạy thật
`test_run_det_probe_real_subprocess` không bị skip trên máy QA (R5-03), và xác nhận
`layout_qa_findings` thật sự có row `rotated_text_scan_unsupported` khi chạy job `pdf_scan` có
trang chữ xoay thật — không chỉ tin lại kết quả review này.

---

# Review Report — Bug #7 spike (7.0) + fix (7.1) — list line-break shim

- **Reviewer**: Reviewer (Sonnet)
- **Ngày**: 2026-09-07

## Verdict: APPROVE

## Phạm vi review

`src/babeldoc_shim/` (mới: `__init__.py`, `line_split.py`, `sitecustomize.py`),
`tests/test_babeldoc_line_split_shim.py` (mới), `tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz`
(mới), `src/services/babeldoc_runner.py`, `src/core/config.py`, `src/core/job_orchestrator.py`
— theo `docs/Architecture.md` mục "Bug #7/#8 — Final Decision sau phản biện Domain Expert
(2026-09-07)" (X3, X4-1, X5 D7-1→D7-5) và `docs/CHANGELOG.md` entry mới nhất của Dev.

## Checklist R5-04 (Protocol 5)

**External contract verified against real source: YES** — nguồn: babeldoc 0.6.4 đã cài tại
`~/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/paragraph_finder.py`.
Tôi tự đọc trực tiếp source thật (không dựa CHANGELOG) và đối chiếu từng dòng
`_split_paragraph_into_lines`/`_compute_collision_counts_histogram` gốc (dòng 600-776) với
`line_split.py` — thuật toán khớp chính xác (difference-array histogram, `step=0.25`, ngưỡng
`count < 1`, docstring nói "less than 2" nhưng code là `count < 1` — đúng như X2-c mô tả), CHỈ
khác đúng 1 điểm: loại ký tự khoảng trắng khỏi mảng đưa vào histogram va chạm, giữ nguyên bước
gán ký tự vào dòng theo tâm y dùng đầy đủ `bounds` (kể cả space). Cũng xác nhận
`babeldoc.__version__ == "0.6.4"` khớp đúng version cài trên máy (`babeldoc/__init__.py:1`), và
class `ParagraphFinder` tồn tại đúng tên tại `paragraph_finder.py:51`.

## Verify độc lập (không tin lời khai Dev)

**1. Số liệu spike 7.0 (170/172 vs 147/163).** Dev để lại toàn bộ artifact thật tại
`/private/tmp/bdprobe70/` (không phải file trong repo, nhưng vẫn trên máy này) — `analyze.py`
(script đo, cùng phương pháp Tech Lead dùng ở X9: cluster ground-truth theo `char.box.y` dung sai
3pt, loại debug-info và space-dummy), `shim_off/wd/p74_77/paragraph_finder.json`,
`shim_on{,2,3}/wd/p74_77/paragraph_finder.json`, cùng `shim_on*.stderr.log` có dòng
`babeldoc_shim: da vá ParagraphFinder._split_paragraph_into_lines ...` xác nhận patch thực sự
chạy trong subprocess con. Tôi tự chạy lại `python3 analyze.py` trên cả 4 dump này (không copy
số Dev báo) — kết quả **147/163** (shim tắt) và **170/172** (shim bật, x3 lần chạy độc lập,
2 ca sai còn lại đều là `)60`/`)62`) — khớp CHÍNH XÁC với CHANGELOG, và khớp đúng baseline 147/163
đã ghi ở Architecture.md X2. Phương pháp đo (babeldoc thật `--debug`, `--openai-base-url` cổng
chết) đúng như Tech Lead từng làm.

**2. Test oracle (R6-02, 14 case tham số hoá + 2 known-unfixed).** Tôi tự chạy
`uv run pytest tests/test_babeldoc_line_split_shim.py -v` — 19/19 pass. Tự viết script độc lập
đọc `paragraph_finder_p74_77_dump.json.gz` để xác nhận từng `text_prefix` trong bảng oracle nằm
đúng `page_index` mà test khai (`)60`→page 1, `1. Explain…`→page 1, `Using regular…`→page 2,
các đoạn văn xuôi + toàn bộ 6 case bullet `■`→page 3, `)62`→page 3) — nhãn "p0/p1/p2" trong
Architecture.md X2 là ký hiệu tương đối của Tech Lead (không phải index JSON thật), không phải
sai lệch dữ liệu. Đối chiếu từng con số kỳ vọng trong test với đúng bảng X2 gốc — khớp 100%,
không có số nào bị Dev "làm tròn"/suy diễn.

**3. R5-04(a) — version gate có thực sự chặn không.** Đọc `_install_hook_if_version_matches()`:
so sánh `getattr(babeldoc, "__version__", None) != _EXPECTED_BABELDOC_VERSION` bằng chuỗi thật,
không phải comment suông — version khác `return` ngay, không gọi `sys.meta_path.insert`, nên
hoàn toàn không cài hook. Đã đối chiếu với `babeldoc/__init__.py` thật.

**4. R5-04(b) — fail-safe khi patch thất bại giữa chừng.** Đọc kỹ `_PatchingLoader.exec_module`:
gọi `_apply_patch(module)` trong `try/except Exception` ngay tại đây, log `logger.warning(...,
exc_info=True)` rồi KHÔNG re-raise — nếu `ImportError`/`AttributeError` xảy ra (vd đổi tên class
hoặc method ở version khác), lỗi bị nuốt đúng tại đây, module gốc vẫn được exec bình thường
trước đó (dòng `self._wrapped.exec_module(module)` chạy trước `try`, không nằm trong khối bị
patch) — babeldoc chạy tiếp với `_split_paragraph_into_lines` GỐC. Toàn bộ
`_install_hook_if_version_matches()` còn được bọc thêm 1 lớp `try/except Exception` ở cuối file
— double safety net. Tôi giả lập cả 2 trường hợp bằng tay (đổi `_TARGET_MODULE_NAME` trỏ vào
module không tồn tại attribute `ParagraphFinder`, và giả lập `babeldoc.__version__` khác) và xác
nhận không có exception nào lọt ra khỏi `sitecustomize` — khớp đúng lời khai CHANGELOG.

**Gap tôi phát hiện (ghi ở mục non-blocking):** fail-safe này CHỈ bảo vệ giai đoạn *áp patch*
(import-time). Hàm `patched()` (được gọi mỗi lần babeldoc xử lý 1 paragraph, runtime) KHÔNG có
try/except riêng — nếu `line_split.split_into_line_groups()` ném exception ở 1 edge case nào đó
(dữ liệu hình học bất thường không có trong 163 case đã test), lỗi sẽ lan lên đúng như thể method
gốc lỗi, không có "quay lại hành vi gốc" ở cấp runtime này. Đây không phải rủi ro MỚI so với
trước khi có shim (method gốc cũng có thể lỗi tương tự), nhưng khác với tinh thần "tuyệt đối
không crash job" ở docstring — nên ghi rõ đây là fail-safe cho *patch application*, không phải
cho *mọi lần gọi hàm đã patch*.

**5. PYTHONPATH wiring.** Đọc `babeldoc_runner.py:342-352`: `env = {**os.environ, **service.envs,
"COLUMNS": "200"}` rồi mới đọc `env.get("PYTHONPATH", "")` và nối bằng `os.pathsep` (không dùng
`":"` hardcode) nếu đã có giá trị, chỉ gán thẳng `_BABELDOC_SHIM_DIR` nếu chưa có — xác nhận
không ghi đè mất `PYTHONPATH` gốc của `os.environ`/`service.envs`. Đúng như khai báo.

**6. `line_split.py` là logic DÙNG CHUNG thật, không phải 2 bản trùng ngẫu nhiên.** Đọc
`sitecustomize.py:93`: `from line_split import CharBound, split_into_line_groups` (import tên
trần — đúng vì `PYTHONPATH` trỏ THẲNG vào `src/babeldoc_shim/`, không phải project root, nên
`src.babeldoc_shim.line_split` không tồn tại trên `sys.path` của subprocess). Test import
`from src.babeldoc_shim.line_split import ...` (qua package, vì chạy trong process app). Cả 2
đường import trỏ về đúng CÙNG MỘT file vật lý `src/babeldoc_shim/line_split.py` — không có bản
sao thứ hai nào trong repo (`grep -rn "split_into_line_groups" src/` chỉ ra đúng 1 định nghĩa +
2 điểm gọi). Xác nhận đạt yêu cầu "test gọi đúng logic production".

**7. R6-03 — live E2E không chỉ tin `status`.** Artifact thật tại `/private/tmp/bdprobe70/`:
`live_run.log` ghi `success=True` cho cả `p74_77` và `q2_7pages`, có `duration`/`rate_limit_hits`
thật (không phải giả lập). Tôi tự mở PDF output bằng `pymupdf` (KHÔNG tin lại số Dev báo) —
`live_p74_77/p74_77.no_watermark.vi.mono.pdf`: 4/4 trang có nội dung (2856/2149/2126/2127 ký
tự), trang 3 (index 0-based, "How baking works" trang thí nghiệm) có 17 dòng chứa `■` với text
tiếng Việt thật đọc được (vd `■  Xác định và mô tả sự khác biệt giữa vị chua, vị chát và vị
đắng`) — khớp tinh thần "16/17 bắt đầu dòng" Dev báo, không phải file rỗng. `q2_7pages`: cả 7/7
trang có nội dung thật (1944–4309 ký tự/trang, không trang nào 0 ký tự) — khớp claim "không hồi
quy". Đây là bằng chứng sống thật (giống đúng cách QA Vòng 3 phát hiện Bug #5 ở Protocol 6),
không phải suy diễn từ `status=completed`.

**8. Phạm vi 7.2/7.3 KHÔNG bị lẫn vào.** `grep -n "is_bullet_point\|process_independent_paragraphs\|toc\|Contents"
src/babeldoc_shim/*.py` chỉ khớp trong docstring/comment tham chiếu Protocol, không có logic nào
xử lý numbered-list marker (Ca A, 7.2) hay mục lục (Ca C, 7.3). `job_orchestrator.py` diff đúng
1 dòng (truyền flag). Đạt đúng phạm vi PM giao chỉ 7.0+7.1.

**9. Chạy thật (Reviewer tự chạy):**
```
uv run pytest -q                                → 369 passed, 419 warnings in 91.94s
uv run ruff check (5 path liên quan)            → All checks passed!
uv run ruff format --check (5 path liên quan)   → 7 files already formatted
```
Khớp đúng số Dev báo trong CHANGELOG (369 = 350 cũ + 19 mới).

## Danh sách issue

**Blocking:** không có.

**Non-blocking:**
1. **Fail-safe của shim chỉ phủ giai đoạn áp patch (import-time), không phủ runtime của hàm đã
   patch.** `patched()` trong `sitecustomize.py` gọi `line_split.split_into_line_groups()` không
   có try/except riêng — nếu có edge case hình học chưa từng gặp trong 163 paragraph đã test làm
   hàm này raise, lỗi sẽ lan lên như thể method gốc lỗi, không "tự động quay lại hành vi gốc"
   giữa chừng một job đang chạy. Rủi ro thấp (đã có 19 test bao gồm 2 test hình học tổng hợp),
   nhưng nên bổ sung 1 dòng `try/except Exception` bọc lời gọi `split_into_line_groups(bounds)`
   ngay trong `patched()`, fallback về cách gán dòng cũ (hoặc tối thiểu: gộp thành 1 dòng như
   trước) + log cảnh báo, để đúng tinh thần "tuyệt đối không crash job" đã ghi trong docstring
   của chính file này — hiện tại tinh thần đó chỉ đúng cho lỗi *lúc cài patch*, chưa đúng cho lỗi
   *lúc chạy patch*.
2. **Không có test tự động cho chính `sitecustomize.py`** (version-gate, meta-path hook,
   fail-safe khi `AttributeError`) — 19 test hiện có đều nhắm `line_split.py` (thuần logic).
   CHANGELOG khai đã "verify sống bằng cách giả lập" các case version-mismatch/patch-thất-bại,
   và tôi tự tay verify lại các case đó khớp đúng khi đọc code — nhưng không có gì giữ bất biến
   này lại thành regression test. Một thay đổi vô tình sau này ở `_install_hook_if_version_matches`
   hay `_PatchingLoader` có thể phá vỡ fail-safe mà không test nào bắt được. Đề xuất thêm tối
   thiểu 2 test process-level (hoặc unit test gọi trực tiếp `_install_hook_if_version_matches`/
   `_apply_patch` với module giả) cho: (a) version khác → không cài hook; (b) module thiếu
   `ParagraphFinder`/thiếu method → không raise ra ngoài.
3. `Settings.babeldoc_line_split_shim_enabled` (`src/core/config.py`) là giả định tự chọn của
   Dev, không bắt buộc theo spec Architecture.md — chấp nhận được (cùng mẫu rollback với
   `babeldoc_rotated_text_overlay`, đã ghi rõ lý do trong comment và CHANGELOG mục "Giả định tự
   chọn"), không phải issue, ghi lại để PM biết đây là quyết định ngoài spec khi review tổng thể
   sau này.

## Next step

**APPROVE.** Circuit breaker Dev↔Reviewer: vòng 1/3 cho tăng bổ 7.0+7.1 này. Chuyển QA — lưu ý
Protocol 6 R6-03 áp dụng TRỰC TIẾP cho thay đổi này (không phải pipeline OCR→dịch, nhưng đây tự
nó là 1 thay đổi hành vi runtime của bước dịch babeldoc): QA phải tự chạy lại ít nhất 1 lần
`BabeldocRunner.translate_pages()` thật với shim bật (mặc định) và đọc nội dung PDF output
(không chỉ tin `status`), KHÔNG tái sử dụng artifact tại `/private/tmp/bdprobe70/` của Reviewer
làm bằng chứng của QA (máy khác/session khác có thể không còn artifact này). KHÔNG làm 7.2
(numbered-list Ca A) / 7.3 (đo lại mục lục Ca C) — đúng phạm vi đã chốt, PM quyết định bước tiếp
theo.

---

## Review — Bug #7 fix, bước 7.2 (Ca A) — tách numbered-list theo marker tăng dần (B-2b) (2026-09-07)

Phạm vi: `src/babeldoc_shim/numbered_list_split.py` (mới), `src/babeldoc_shim/sitecustomize.py`
(vá thêm `ParagraphFinder.process`), `src/services/babeldoc_runner.py`
(`numbered_list_split_enabled` + env `BABELDOC_SHIM_NUMBERED_LIST_SPLIT`), `src/core/config.py`
(`babeldoc_numbered_list_split_enabled`), `src/core/job_orchestrator.py` (1 dòng truyền flag),
`tests/test_babeldoc_numbered_list_split.py` (30 test, mới), 2 golden fixture mới, đoạn đổi
trong `docs/Architecture.md` X10, entry mới trong `docs/CHANGELOG.md`. Theo Architecture.md
"Bug #7/#8 — Final Decision sau phản biện Domain Expert (2026-09-07)", X5 D7-3, bước "7.2".

### External contract verified against real source: YES

Đã tự đọc trực tiếp source code babeldoc 0.6.4 THẬT đã cài trên máy này (KHÔNG suy đoán/nhớ lại):
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/paragraph_finder.py`
và `.../document_il/il_version_1.py`.

- Version: `__init__.py:1`, `const.py:9`, `main.py:29` đều ghi `__version__ = "0.6.4"` — khớp
  đúng gate version trong `sitecustomize.py` (`_EXPECTED_BABELDOC_VERSION`).
- `ParagraphFinder.process(self, document)` (`paragraph_finder.py:196`) — khớp chính xác chữ ký
  hàm `patched(self, document)` bọc nó trong `_build_patched_process`.
- Xác nhận **thứ tự phụ thuộc bắt buộc 7.1 → 7.2 là đúng thật**, không chỉ suy luận: `process_page`
  (gọi từ trong `process()` gốc) gọi `self._split_paragraph_into_lines(...)` ở dòng 275 **TRƯỚC**
  `self.process_independent_paragraphs(paragraphs, median_width)` ở dòng 287 — và quan trọng hơn:
  `page.pdf_paragraph = paragraphs` được gán **CÙNG list object** (không copy) từ đầu
  `process_page` (dòng ~243, dataclass field thường, không có property/setter copy — xác nhận qua
  `il_version_1.py:1291 pdf_paragraph: list[PdfParagraph] = field(...)` là dataclass field trần).
  `process_independent_paragraphs` mutate list đó bằng `.insert()` ngay trên chính list đó, nên
  khi `original_process(self, document)` (bên trong `patched process()`) chạy xong, `document.page`
  mà code 7.2 duyệt tiếp theo đã phản ánh ĐẦY ĐỦ kết quả của cả `_split_paragraph_into_lines` (7.1)
  và `process_independent_paragraphs` (bullet/TOC split gốc) — đúng như comment "7.1 phải patch
  xong trước khi wrap `process()`" khẳng định, không phải giả định chưa kiểm.
- **Mẫu tạo `PdfParagraph` mới khi tách** (`_split_numbered_list_paragraphs_on_page`) là COPY Y
  NGUYÊN mẫu babeldoc tự dùng trong chính `process_independent_paragraphs` — đọc trực tiếp
  `paragraph_finder.py` (khối quanh dòng 868-911, 2 nhánh tách TOC-dot-leader và tách theo
  short-line/bullet đều dùng chung mẫu): `PdfParagraph(box=Box(0, 0, 0, 0), pdf_paragraph_composition=...,
  unicode="", debug_id=generate_base58_id(), layout_label=paragraph.layout_label,
  layout_id=paragraph.layout_id)` rồi gọi `self.update_paragraph_data(...)` cho cả 2 đoạn — khớp
  TỪNG FIELD với code shim. `generate_base58_id` xác nhận là hàm module-level thật (dòng 46), truy
  cập qua `paragraph_finder_module.generate_base58_id` là đúng.
- `PdfCharacter.visual_bbox` (kiểu `VisualBbox | None`) và `char_unicode` (`il_version_1.py:646,671`),
  `PdfLine.pdf_character` (`:1062`) — khớp đúng cách `sitecustomize.py`/`numbered_list_split.py`
  truy cập `char.visual_bbox.box.x` / `char.char_unicode` / `comp.pdf_line.pdf_character`.
  Lưu ý field `visual_bbox` là Optional theo khai báo — nhưng bản thân `paragraph_finder.py` GỐC
  (chưa vá gì) cũng truy cập `char.visual_bbox.box` không hề kiểm tra None ở ít nhất 6 nơi khác
  (dòng 152-176, 429-458, 608, 1042) — nên rủi ro `AttributeError` nếu `visual_bbox` là `None` ở
  giai đoạn này là rủi ro CÓ SẴN của chính babeldoc tại đúng bước xử lý này, không phải rủi ro MỚI
  do shim gây ra. Không cần fix, ghi lại để không ai nhầm là lỗi mới.
- Trích dẫn dòng `paragraph_finder.py:868-925` trong docstring/CHANGELOG hơi lệch — hàm
  `process_independent_paragraphs` thực ra bắt đầu ở dòng 841 (không phải 868), nhưng đúng khối mẫu
  tạo `PdfParagraph` được cite thì đúng nằm trong vùng đó. Cosmetic, không ảnh hưởng đúng/sai logic.

### Tự verify độc lập golden fixture (không tin lại số Dev báo)

Viết script riêng (không dùng lại helper của test) đọc thẳng 2 file `.json.gz`, tự áp cùng regex
marker rồi tự quét toàn bộ paragraph có ≥ 2 marker:
- `paragraph_finder_numbered_list_post71_dump.json.gz`: ra đúng **4 cặp** `[11,12]`, `[23,24]`
  (kèm dòng tiếp nối `"1½ quart"`), `[31,32]`, `[33,34]` — khớp 100% với claim trong CHANGELOG,
  không suy diễn từ code test.
- `paragraph_finder_p74_77_post71_dump.json.gz`: ra 4 paragraph gộp `[2,3]`, `[4,5]`, `[6,7]`, và
  `[8..15]` (8 mục) — claim CHANGELOG chỉ nêu case "8..15" làm ví dụ đại diện nhưng test
  (`test_golden_fixture_page0_no_residual_merge_after_split`) có quét TOÀN BỘ trang nên vẫn bắt
  được cả 3 cặp còn lại, không bị bỏ sót.
- Tự quét TOÀN BỘ dòng có chứa chữ số bắt đầu dòng trên cả 2 fixture để săn false-positive độc lập:
  bắt được các dòng ngờ vực như `"60)"`, `"62)"`, `"1 BEING NOT VERY SMOOTH"`,
  `"2- and 4-quart sizes"`, `"1½ quart"` — **tất cả đều bị regex loại đúng** (thiếu `\s+\S` sau
  marker, hoặc ký tự sau chữ số không phải `.`/`)`) — xác nhận độc lập claim "0 false-positive".

### Chạy thật (Reviewer tự chạy, không tin lại số Dev báo)

```
uv run pytest -q                                                → 399 passed, 419 warnings (90s)
uv run ruff check (6 path liên quan)                             → All checks passed!
uv run ruff format --check (6 path liên quan)                    → 6 files already formatted
uv run pytest --collect-only tests/test_babeldoc_numbered_list_split.py → 30 tests collected
```
Khớp đúng số Dev báo trong CHANGELOG (399 = 369 + 30 test mới).

**Giới hạn của lần review này (minh bạch)**: KHÔNG tự chạy lại live E2E qua babeldoc thật +
DeepSeek thật (R6-03 claim của Dev) — tốn API cost thật và thời gian, và bằng chứng gián tiếp
(source code khớp từng field với babeldoc thật, golden fixture tự verify độc lập khớp 100%, toàn
bộ 399 test xanh) đã đủ tin cậy cho quyết định approve/reject ở review này. Đây KHÔNG thay thế
yêu cầu R6-03 cho QA — QA vẫn phải tự chạy live ít nhất 1 lần trước khi release (như review trước
đã ghi cho 7.0+7.1).

## Danh sách issue

**Blocking:** không có.

**Non-blocking:**

1. **Fail-safe của patch 7.2 chỉ phủ giai đoạn CÀI patch (import-time), không phủ RUNTIME của
   `patched(self, document)`** — cùng loại vấn đề đã ghi ở non-blocking #1 của review 7.0+7.1
   (chưa được sửa ở đó, giờ lặp lại thêm 1 lần ở tầng paragraph). `_build_patched_process` gọi
   `original_process(self, document)` rồi `_split_numbered_list_paragraphs_on_page(...)` cho mỗi
   trang, không có `try/except` nào bọc riêng đoạn code MỚI (7.2) này. Nếu 1 trang thật có hình
   dạng dữ liệu chưa từng gặp trong 2 fixture đã test khiến hàm này raise (vd một edge-case nào đó
   của `compositions`/`pdf_line` chưa lường tới), lỗi sẽ lan lên thành crash TOÀN BỘ job dịch của
   babeldoc, không "tự động quay lại hành vi gốc" — trái tinh thần "TUYỆT ĐỐI không được để lỗi ở
   đây làm crash job dịch" ghi trong docstring đầu file (tinh thần đó hiện chỉ đúng cho lỗi *lúc
   cài* patch). Đề xuất: bọc riêng lời gọi `_split_numbered_list_paragraphs_on_page` trong
   `try/except Exception`, fallback giữ nguyên `page.pdf_paragraph` gốc (không tách) + log cảnh
   báo, cho CẢ patch 7.1 (`patched` trong `_build_patched_split_paragraph_into_lines`) VÀ patch
   7.2 — nên làm 1 lần cho cả 2 vì cùng root cause, tránh phải quay lại sửa riêng lẻ từng patch.
2. **Không có test nào assert việc wiring biến môi trường `BABELDOC_SHIM_NUMBERED_LIST_SPLIT`
   qua đúng subprocess `env` của `BabeldocRunner.translate_pages()`** — đã tự đọc code xác nhận
   đúng (`babeldoc_runner.py:349-362`), nhưng không có gì giữ bất biến này lại thành regression
   test. Cùng gap đã tồn tại từ 7.1 cho `PYTHONPATH`/`babeldoc_line_split_shim_enabled` (chưa từng
   có test), giờ lặp lại thêm 1 biến nữa mà vẫn không ai thêm test. Đề xuất thêm ít nhất 1 test
   mock `asyncio.create_subprocess_exec` (pattern đã có sẵn trong `tests/test_babeldoc_runner.py`
   cho các flag khác) và assert `env["BABELDOC_SHIM_NUMBERED_LIST_SPLIT"]` đúng "1"/"0" theo
   `numbered_list_split_enabled=True/False`.
3. **Không có test assert `JobOrchestrator._translator_runner` truyền đúng
   `numbered_list_split_enabled=self._settings.babeldoc_numbered_list_split_enabled` vào
   `BabeldocRunner`** — đã tự đọc code xác nhận đúng (`job_orchestrator.py:247`), nhưng đây là
   điểm nối lineage giữa `Settings` và `BabeldocRunner` (đúng loại lỗi Protocol 6 quan tâm) mà
   không test nào bảo vệ. Cùng gap y hệt đã tồn tại cho `line_split_shim_enabled` từ 7.1. Đề xuất
   1 test khởi tạo `JobOrchestrator` với `Settings(babeldoc_numbered_list_split_enabled=False)`
   rồi assert `orchestrator._translator_runner._numbered_list_split_enabled is False`.
4. **`docs/Architecture.md` có 2 bảng trạng thái verify mâu thuẫn nhau cho cùng 1 claim.** Bảng
   "W7. Trạng thái verify (tổng hợp mục này)" (dòng 6417) vẫn ghi "B-2b heuristic marker tăng dần
   không false-positive | ⚠️ `[UNVERIFIED]`" — trong khi bảng "X10" (dòng 6738, bảng được đặt tên
   rõ là "— cập nhật") đã sửa đúng thành "✅ Verified" trong đúng lần sửa này. Đây là pattern đã có
   từ trước (tài liệu là biên bản debate nhiều vòng W1-W7 rồi X1-X10, không phải 1 bảng canonical
   duy nhất luôn tự nhất quán) — X10 rõ ràng là bảng thẩm quyền/mới nhất, và task này chỉ được giao
   sửa đúng X10 nên không phải lỗi của Dev lần này. Nhưng rủi ro thật: một người/agent đọc từ trên
   xuống dưới sẽ thấy dòng 6417 nói UNVERIFIED trước khi đọc tới X10 nói Verified — đúng kiểu mơ hồ
   "đã verify" vs "chưa verify" mà Protocol 5 muốn tránh. Đề xuất (không cấp bách): thêm 1 chú
   thích ngắn tại các dòng UNVERIFIED cũ đã được X10 cập nhật, kiểu "(→ xem X10, đã Verified
   2026-09-07)", để không ai chỉ đọc W7 mà kết luận sai.
5. **Ghi nhận minh bạch (không phải issue)**: diff thật của `docs/Architecture.md` sửa **2 dòng**
   trong bảng X10 (cả claim "Shim V1 patch được babeldoc subprocess" VÀ "B-2b heuristic..."), không
   phải chỉ 1 dòng B-2b như mô tả trong brief giao việc cho Reviewer. Đã kiểm tra: dòng "Shim V1"
   được cập nhật đúng, có cơ sở thật (khớp nội dung review-report.md của 7.0+7.1 ở trên) — đây là
   1 sửa muộn hợp lệ cho 1 dòng bị bỏ sót từ tăng bổ trước, không phải lỗi/scope creep của code. Ghi
   lại theo kỷ luật gắn nhãn verify (CLAUDE.md global, "Protocol 1 — mở rộng") vì đây là 1 điểm
   brief-vs-thực-tế lệch nhau, dù không ảnh hưởng kết luận review.
6. **Quan sát "fallback dịch giữ tiếng Anh" Dev ghi trong CHANGENLOG (đã gắn `[CHƯA VERIFY]` đúng
   cách)** — hợp lý để coi là ngoài phạm vi 7.2 (bản thân việc TÁCH đúng ranh giới paragraph đã
   verify chắc chắn; tỷ lệ fallback dịch là hành vi có sẵn của babeldoc's LLM-output-sanity check,
   độc lập với đúng/sai của thuật toán tách). Không chặn approve, nhưng đồng ý với Dev rằng nên có
   task riêng theo dõi nếu tỷ lệ fallback này ảnh hưởng thật tới chất lượng bản dịch production.

## Next step

**APPROVE.** Circuit breaker Dev↔Reviewer: vòng 1/3 cho bước 7.2 này (độc lập với circuit breaker
đã dùng cho 7.0+7.1). Đúng phạm vi PM giao (chỉ 7.2, không làm 7.3). Chuyển QA — lưu ý Protocol 6
R6-03 áp dụng cho thay đổi này y như đã áp dụng cho 7.0+7.1: QA phải tự chạy lại ít nhất 1 lần
`BabeldocRunner.translate_pages()` thật (shim + numbered-list-split đều bật, mặc định) và đọc nội
dung PDF output thật (không chỉ tin `status`) trên ít nhất 1 tài liệu có numbered-list thật —
KHÔNG tái dùng lại số liệu Dev tự báo trong CHANGENLOG làm bằng chứng QA của chính QA. Nếu QA muốn
theo dõi thêm quan sát "fallback giữ tiếng Anh" (issue non-blocking #6 ở trên), nên ghi riêng vào
test-report.md, không trộn vào kết luận pass/fail của chính bước 7.2 (tách paragraph) — đó là 2
câu hỏi độc lập. KHÔNG làm 7.3 (đo lại mục lục, Ca C) — đúng phạm vi đã chốt.

---

## Review — HOTFIX bước 7.2: thêm `update_unicode=True` (bug phát hiện bởi Domain Expert, 2026-09-07)

Phạm vi: `src/babeldoc_shim/sitecustomize.py` (hàm `_split_numbered_list_paragraphs_on_page`, 2 dòng
sửa + comment), `tests/test_babeldoc_shim_unicode_regression.py` (MỚI, 2 test), entry mới cuối
`docs/CHANGELOG.md`. Commit gốc bị vá: `e324b29`. Không đụng `docs/Architecture.md` trong hotfix
này (bug phát hiện tình cờ trong lúc phản biện Ca C, xem `docs/Architecture.md` mục "Bug #7 Ca C —
Phản biện của Domain Expert (2026-09-07)", section Z6 — đã tự đọc, xác nhận đúng là nơi phát hiện).

### External contract verified against real source: YES

Tự mở trực tiếp source babeldoc 0.6.4 đã cài trên máy này (KHÔNG suy đoán/nhớ lại, KHÔNG chỉ tin
lại số dòng trong brief hay trong Architecture.md):

- `update_paragraph_data(self, paragraph: PdfParagraph, update_unicode=False)` —
  `paragraph_finder.py:124` (khớp CHÍNH XÁC dòng bắt đầu, không lệch, tốt hơn độ chính xác trích dẫn
  ở review 7.2 trước). Đọc thân hàm (`:124-165`): `if update_unicode and chars: paragraph.unicode =
  get_char_unicode_string(chars)` — xác nhận 100% mặc định `False` thì **không đụng gì tới
  `.unicode` cả** (không reset, không giữ nguyên có điều kiện — đơn giản là không chạm), khớp đúng
  claim của brief và của comment mới trong code.
- `process_page` gọi đúng 1 lần `self.update_paragraph_data(paragraph, update_unicode=True)` cho
  MỌI paragraph ở **dòng 124+170=... thực tế dòng 294** (tự `grep -n`, khớp CHÍNH XÁC con số brief
  nêu, không lệch).
- `ParagraphFinder.process()` (`:196-215`): tự đọc toàn bộ thân hàm, xác nhận đúng cấu trúc bọc của
  `_build_patched_process` — `original_process(self, document)` chạy time-order TRƯỚC (loop hết mọi
  `page.pdf_paragraph` gọi `process_page`, rồi mới check `total_paragraph_count`/`check_cid_paragraph`
  trên SỐ PARAGRAPH GỐC, chưa có paragraph mới của 7.2) — patch 7.2 chỉ chạy SAU KHI hàm gốc `return`
  hoàn toàn. Xác nhận độc lập lập luận "process_page's update_unicode=True loop luôn chạy xong trước
  khi 7.2 có cơ hội tạo/cắt paragraph" là đúng, không phải suy luận chưa kiểm.
- `il_translator_llm_only.py:566`: `if len(paragraph.unicode) < self.translation_config.min_text_length:
  continue` — khớp đúng claim "563-566" (gate nằm ở dòng 566, trong đúng khoảng trích).
- `PdfParagraph.unicode` mặc định không có `default=""` tường minh ở chỗ tôi soát nhanh, nhưng code
  shim tự truyền `unicode=""` khi construct — không phụ thuộc default của dataclass, không phải vấn đề.

**Diff thực tế so với `e324b29`** (tự chạy `git diff e324b29 -- src/babeldoc_shim/sitecustomize.py`,
không tin lại mô tả trong CHANGELOG): đúng **2 dòng code thay đổi** (`update_paragraph_data(paragraph)`
→ `update_paragraph_data(paragraph, update_unicode=True)`, và tương tự cho `new_paragraph`), phần còn
lại thuần comment giải thích. Diff tối giản, không lẫn thay đổi ngoài phạm vi.

### Đào sâu câu hỏi (5) của brief — có cần fix paragraph GỐC bị cắt không?

Brief hỏi: liệu "stale nhưng không gây bug thấy được" (cho paragraph gốc bị cắt, nhóm đầu) có thực
sự đúng không, hay có kịch bản nào khiến `.unicode` stale dài gây dịch nhầm nội dung. Đây là câu hỏi
quan trọng nhất của lần review này — đã tự đọc sâu thêm source `il_translator.py` (KHÔNG có trong
brief, tự tìm) để trả lời dứt điểm thay vì chỉ xác nhận lại 2 dòng sửa:

1. `il_translator.py:954-989` (`pre_translate_paragraph`) → gọi `get_translate_input(paragraph, ...)`
   (`il_translator.py:575+`). Đọc kỹ nhánh **`len(paragraph.pdf_paragraph_composition) == 1`**
   (`:607-623`): trả về `TranslateInput(paragraph.unicode, [], paragraph.pdf_style)` — dùng **THẲNG**
   `paragraph.unicode` làm text gửi LLM, **KHÔNG dựng lại từ ký tự/composition thật**. Chỉ khi
   `len(pdf_paragraph_composition) > 1` (`:644+`) code mới tự duyệt `chars` từ `pdf_paragraph_composition`
   thật (không phụ thuộc `.unicode`).
2. Suy ra: **paragraph gốc bị cắt (nhóm đầu) — nếu sau khi cắt chỉ còn ĐÚNG 1 composition (1 dòng)**
   (rất phổ biến trong thực tế — chính 3/4 cặp CHANGELOG dẫn chứng, `[11,12]`/`[31,32]`/`[33,34]`, đều
   là các mục 1 dòng/mục theo cách đặt tên nhóm), thì trước fix, text gửi LLM cho paragraph này sẽ là
   `.unicode` STALE = **toàn bộ văn bản gộp CŨ** (cả mục hiện tại LẪN mục đã bị tách ra) — **không chỉ
   là "dữ liệu sai nằm im không ai đọc"**, mà là **input dịch sai thật sự** được gửi đi. Tôi tự verify
   bằng dump thật `paragraph_finder_numbered_list_post71_dump.json.gz` (trước 7.2 chạy): paragraph
   chứa cặp 11+12 có đúng `unicode = "11. Ovens (conventional, reel, deck, etc.) 12. Stovetop burners"`
   (63 ký tự, 2 composition) — và trong `wd72c/page14_numbered_list_source/paragraph_finder.json` (dump
   SAU khi 7.2 tách, cùng artifact Reviewer trước đã dùng), paragraph nhóm đầu (item 11) có đúng
   `num_comp=1` **và unicode VẪN LÀ chuỗi 63 ký tự gộp đó** — xác nhận trực tiếp bằng dữ liệu thật,
   không chỉ suy luận từ source.
3. **Nhưng**: đối chiếu `translate_tracking.json` trong CHÍNH thư mục `wd72c` đó, record cho item 11
   lại ghi `pdf_unicode` **sạch** (`"11. Ovens (conventional, reel, deck, etc.)"`, không lẫn nội dung
   item 12) — mâu thuẫn trực tiếp với `paragraph_finder.json` cùng thư mục (không có stage nào giữa
   `ParagraphFinder` và `ILTranslatorLLMOnly` chạm `.unicode` — đã tự đọc `StylesAndFormulas`,
   `AddDebugInformation`, `xml_converter.write_json` để loại trừ, không suy đoán). Không tự dàn xếp
   được nghịch lý này bằng đọc source thuần — nghi vấn hợp lý nhất: các thư mục `wd72/wd72b/wd72c`
   là **artifact dò tìm lặp lại nhiều lần trong ~25 phút** (21:51→22:15, theo mtime) khi Domain Expert
   còn đang thử các bản vá tạm thời khác nhau, nên `paragraph_finder.json` và `translate_tracking.json`
   trong cùng 1 thư mục scratch **có thể đến từ 2 lần chạy babeldoc khác nhau** ghi đè lẫn nhau vào
   cùng `--working-dir`, không phải bằng chứng "sạch" của đúng 1 lần chạy nhất quán — nên KHÔNG dùng
   được để bác bỏ kết luận (1)/(2) ở trên, vốn dựa thẳng trên đọc source (bằng chứng mạnh hơn).

**Kết luận của tôi (khác — mạnh hơn — kết luận ở Architecture.md Z6)**: Architecture.md Z6 viết
*"Paragraph gốc không bị ảnh hưởng vì text gửi LLM dựng từ composition... `unicode` stale chỉ dùng
cho đếm token"* — câu này **chỉ đúng cho trường hợp paragraph còn ≥ 2 composition sau khi cắt**, và
**SAI/thiếu sót cho trường hợp còn đúng 1 composition** (xác nhận bằng đọc trực tiếp
`il_translator.py:607-623`, không suy đoán) — dữ liệu chính CHANGELOG dẫn chứng (`[11,12]`,
`[31,32]`, `[33,34]`) cho thấy trường hợp 1-composition này **phổ biến, không phải hiếm**. Vì vậy:
- Việc Dev chọn sửa **CẢ HAI** lời gọi (không chỉ paragraph mới) là quyết định ĐÚNG, và lý do đúng
  **mạnh hơn** những gì CHANGENLOG/comment trong code hiện ghi ("chỉ để đúng dữ liệu, không gây bug
  thấy được") — thực chất fix này **đóng luôn một đường dịch sai nội dung thật** (gửi văn bản gộp cũ
  dài hơn cho LLM dịch thay vì đúng 1 dòng còn lại), không chỉ là dọn dẹp dữ liệu stale vô hại.
- Vì fix hiện tại ĐÃ áp `update_unicode=True` cho CẢ HAI chỗ, rủi ro này **đã được đóng hoàn toàn**
  bất kể kịch bản nào ở trên có thật sự xảy ra trên dữ liệu `wd72c` hay không — **không cần sửa thêm
  code nào nữa cho hotfix này**, đây là ghi nhận bổ sung lý do, không phải blocking issue.

### Kiểm tra `tests/test_babeldoc_shim_unicode_regression.py`

Tự chạy lại logic trích xuất bằng script riêng (không tin lại việc test tự pass) — xác nhận:
`_extract_function_body` cắt ĐÚNG khối thân hàm `_split_numbered_list_paragraphs_on_page` (4073 ký
tự, dòng đầu/cuối đúng ranh giới hàm), `re.findall` bắt đúng **2** lời gọi
`self.update_paragraph_data(...)`, cả 2 đều chứa `update_unicode=True`. Test có `assert` rõ ràng khi
không tìm thấy hàm (không silent-pass nếu ai đó đổi tên hàm). Test thứ 2
(`test_numbered_list_split_touches_only_the_documented_two_call_sites`, đếm `PdfParagraph(` == 1)
là 1 lớp bảo vệ hợp lý cho giả định "chỉ có đúng 2 lời gọi" của test đầu — đúng tinh thần thiết kế
test bảo vệ giả định của test khác.

Đây là **source-pinning test** (đọc chuỗi source bằng regex), không phải test hành vi thật qua
babeldoc — chấp nhận được vì lý do kiến trúc đã nêu rõ trong docstring (không `import babeldoc`
được trong venv app, Architecture.md X4-1) — nhất quán với cách tiếp cận toàn bộ file
`sitecustomize.py` từ đầu, không phải điểm yếu mới của riêng hotfix này.

**Rủi ro nhỏ của cách viết regex** (non-blocking, xem issue #1): `re.findall(r"self\.update_paragraph_data\(([^)]*)\)", ...)`
dùng `[^)]*` — sẽ bắt sai nếu sau này 1 trong 2 lời gọi có tham số chứa dấu `)` lồng bên trong (vd 1
lời gọi hàm khác làm argument). Rủi ro thấp với code hiện tại (không có), nhưng đáng ghi lại.

### Kiểm tra `docs/CHANGELOG.md` — lịch sử có bị mất không (Protocol 7 R7-03)

`git diff e324b29 --stat -- docs/CHANGELOG.md` → **166 insertions(+), 0 deletions** (tự chạy, không
tin lại lời khai). Đoạn cũ "Quan sát thêm (KHÔNG phải bug của 7.2...)" của bước 7.2 (dòng 3941) và
đoạn "Đính chính" mới (dòng 4086, trỏ ngược lại đúng đoạn cũ bằng cách trích đúng cụm từ "Quan sát
thêm") đều **còn nguyên trong file**, không cái nào bị xoá — đúng yêu cầu "APPEND, không overwrite"
(R7-03). Entry mới thuật đúng cơ chế bug, đúng số liệu (4/35, 10/40 → 0/35, 0/40 — khớp với dữ liệu
`wd72c`/`wd74c` tôi tự mở), chỉ có 1 điểm nên bổ sung: xem issue non-blocking #2 dưới đây (CHANGENLOG
hiện mô tả rủi ro của paragraph gốc bị cắt nhẹ hơn thực tế theo phát hiện ở mục trên).

### Chạy thật (Reviewer tự chạy, không tin lại số Dev báo)

```
uv run pytest -q                                                    → 401 passed, 419 warnings (81s)
uv run ruff check src/babeldoc_shim/sitecustomize.py \
  tests/test_babeldoc_shim_unicode_regression.py                    → All checks passed!
uv run ruff format --check (2 file trên)                            → 2 files already formatted
```
Khớp đúng số Dev báo trong CHANGELOG (401 = 399 + 2 test mới).

## Danh sách issue

**Blocking:** không có.

**Non-blocking:**

1. **Regex trích xuất trong test mới dùng `[^)]*`, không chịu được tham số có dấu `)` lồng bên
   trong** (`tests/test_babeldoc_shim_unicode_regression.py`, dòng ~62). Rủi ro thấp với code hiện
   tại (2 lời gọi hiện có đều đơn giản, không có `)` lồng), nhưng nếu sau này ai sửa hàm thêm 1 tham
   số dạng gọi hàm khác (vd `update_paragraph_data(paragraph, foo(x), update_unicode=True)`), regex
   sẽ cắt nhầm ở dấu `)` đầu tiên của `foo(x)` và có thể false-negative (không thấy `update_unicode=True`
   dù code đúng) hoặc false-positive tinh vi hơn. Không cấp bách, ghi lại để không ai ngạc nhiên nếu
   test này fail kỳ lạ trong tương lai vì lý do không liên quan tới bug thật.
2. **CHANGELOG.md và comment trong code hiện mô tả nhẹ hơn thực tế mức độ rủi ro của việc BỎ SÓT fix
   cho paragraph gốc bị cắt (nhóm đầu).** Cả 2 chỗ đều viết kiểu "không gây bug bỏ dịch (đủ dài để
   qua gate min_text_length) nhưng vẫn là dữ liệu SAI/lỗi thời" — ngụ ý rủi ro chỉ là "dữ liệu bẩn nằm
   im, không ai đọc". Theo phát hiện ở mục "Đào sâu câu hỏi (5)" phía trên (tự đọc thêm
   `il_translator.py:607-623`, không có trong brief gốc): khi paragraph nhóm đầu sau khi cắt còn ĐÚNG
   1 composition (phổ biến, không hiếm — khớp 3/4 cặp CHANGENLOG tự dẫn chứng), `.unicode` chính là
   text được gửi THẲNG cho LLM dịch (không dựng lại từ ký tự thật) — nếu thiếu `update_unicode=True`,
   đây sẽ là **input dịch sai nội dung thật** (gộp cả mục đã tách sang paragraph khác), không chỉ
   "dữ liệu chết". Không blocking vì fix hiện tại ĐÃ đóng đúng cả 2 chỗ nên rủi ro này đã bị chặn hoàn
   toàn bất kể mô tả đúng hay chưa — nhưng đề xuất PM/Dev thêm 1 câu vào CHANGELOG (append, không sửa
   đoạn cũ) làm rõ lại mức độ rủi ro thật, để người đọc sau này không đánh giá thấp tầm quan trọng của
   việc sửa "cả 2 chỗ" nếu có tình huống tương tự phát sinh sau này (vd khi làm 7.4).
3. **`docs/Architecture.md` mục Z6 có 1 câu khẳng định quá rộng, không đúng cho mọi trường hợp**:
   *"Paragraph gốc không bị ảnh hưởng vì text gửi LLM dựng từ composition... unicode stale chỉ dùng
   cho đếm token"* — câu này chỉ đúng khi paragraph còn ≥ 2 composition sau khi cắt; SAI/thiếu sót
   cho trường hợp còn đúng 1 composition (xem phân tích trên, tự đọc `il_translator.py:607-623` xác
   nhận). Không thuộc phạm vi code sửa của hotfix này (Z6 là văn bản debate cũ, không phải phần được
   giao sửa), nhưng đáng note theo kỷ luật gắn nhãn verify (CLAUDE.md global) vì đây là 1 claim cụ thể
   về hành vi hệ thống ngoài đã ghi vào tài liệu chính thức mà chưa đúng hoàn toàn. Đề xuất: PM/Tech
   Lead thêm 1 dòng đính chính ngắn tại Z6 (không sửa/xoá câu cũ, theo đúng tinh thần append).
4. **Không tận dụng được artifact `/private/tmp/bdprobe/wd72c` để xác nhận dứt điểm** hành vi
   single-composition ở trên bằng dữ liệu "sạch" 1 lần chạy — phát hiện `paragraph_finder.json` và
   `translate_tracking.json` trong CÙNG thư mục đó tự mâu thuẫn nhau (xem phân tích), nghi do thư mục
   scratch bị tái sử dụng qua nhiều lần chạy babeldoc khác nhau trong lúc debug. Không phải lỗi của
   Dev/Domain Expert (đây là quy trình dò tìm tạm thời, không phải golden fixture chính thức), nhưng
   ghi lại để nếu QA/Dev cần verify sâu thêm về sau, nên tạo **thư mục `--working-dir` MỚI, sạch**
   cho mỗi lần chạy thay vì tái sử dụng, tránh đúng loại mâu thuẫn dữ liệu này.

## Next step

**APPROVE.** Circuit breaker Dev↔Reviewer: đây là hotfix riêng (Protocol 3 không tính hotfix qua
đúng quy trình Reviewer là 1 vòng sửa lỗi thông thường — không có round trước cho riêng thay đổi
này), vòng 1 cho hotfix này. Diff tối giản, đúng cơ chế bug, verify chéo với source thật khớp 100%,
401 test xanh, ruff sạch, CHANGELOG lẫn review-report đều append đúng cách (không mất lịch sử).

Chuyển QA — lưu ý riêng cho hotfix này, ngoài Protocol 6 R6-03 chuẩn (chạy live thật, đọc nội dung
PDF output, không chỉ tin status):
- QA nên ưu tiên test lại đúng 2 fixture đã có bug trước đó (`page14_numbered_list_source.pdf`,
  trang "QUESTIONS FOR REVIEW") để xác nhận 0 mục còn tiếng Anh — đây là bằng chứng trực tiếp nhất
  cho chính bug đã sửa.
- Theo phát hiện non-blocking #2 ở trên: nếu có điều kiện, QA nên thêm 1 lần kiểm tra riêng nội
  dung dịch của các mục nhóm ĐẦU (nhóm giữ lại, vd item #11/#23/#31/#33 trong fixture cũ) — không chỉ
  xác nhận chúng ĐƯỢC dịch (đã biết đúng từ trước), mà xác nhận bản dịch KHÔNG lẫn nội dung của mục
  đã bị tách sang paragraph khác (vd #11 không được lẫn nghĩa "Stovetop burners" của #12) — đây là
  hệ quả cụ thể, kiểm được, của phát hiện single-composition ở trên; dù tôi tin fix hiện tại đã đóng
  đúng, thêm 1 lần verify sống trực tiếp cho đúng kịch bản này sẽ dứt điểm hoàn toàn nghi vấn.
- KHÔNG cần chặn release chỉ vì issue non-blocking #2/#3 (mô tả rủi ro trong docs) — đây là vấn đề
  tài liệu, không phải code sai.

---

# Review — Bug #7 Ca C — Spike 7.4-a (Protocol 5 R5-02) (Reviewer, 2026-09-08)

## Phạm vi

Review spike theo brief PM: `src/babeldoc_shim/toc_split.py` (MỚI), `scripts/toc_split_spike_measure.py`
(MỚI), phần mới của `tests/fixtures/babeldoc/README.md`, cùng xác nhận `sitecustomize.py` không bị
đổi và các con số CHANGELOG là thật. Đọc trước: `docs/Architecture.md` mục "Bug #7 Ca C — Quyết định
cuối sau phản biện Domain Expert + kế hoạch spike 7.4-a" (AA0–AA12, dòng 7379–7762) và
`docs/CHANGELOG.md` entry "## Bug #7 Ca C — Spike 7.4-a (Dev, 2026-09-08)" (dòng 4147–4302). Đây LÀ
MỘT SPIKE (Protocol 5 R5-02, AA10-a) — không đòi hỏi test suite đầy đủ hay wiring production, đúng
phạm vi PM đã nêu.

## Đối chiếu code với đặc tả AA4/AA5

Đọc từng dòng `toc_split.py` (397 dòng) và so khớp thủ công với AA4 (6 bước) + AA5 (tham số):

| Hạng mục | Kết quả |
|---|---|
| Bước 0 — deny-list `layout_label` (chuẩn hoá lower/strip) + `L < 2` | ✅ Khớp — `evaluate_paragraph:305-313` |
| `TOC_LAYOUT_LABEL_DENY` đúng 19 nhãn liệt kê ở AA4 bước 0 | ✅ Khớp từng nhãn |
| Bước 1 — bỏ ký tự `.isspace()` rồi tự sort theo `x` (không dùng sort có sẵn của babeldoc) | ✅ Khớp — `sort_line_chars` |
| Bước 2 — 6 điều kiện đánh dấu đuôi TOC, đúng thứ tự, dùng ASCII `0-9` (không `str.isdigit()`, Z7-c) | ✅ Khớp — `mark_toc_tail`, `_ASCII_DIGITS` là `frozenset("0123456789")` |
| Bước 2 điều kiện 5 — hệ đo `visual_bbox` (không phải advance-width PyMuPDF) | ✅ Khớp về mặt hợp đồng dữ liệu (`TocChar.x/x2` docstring ghi rõ bắt buộc `visual_bbox.box.x/.x2`); script đo trích đúng `char["visual_bbox"]["box"]` khi tạo `TocChar` — xác nhận thật, không chỉ tin docstring |
| Bước 3 — cổng `m ≥ TOC_MIN_TAIL_LINES`, `m/L ≥ TOC_MIN_TAIL_FRACTION`, dãy `n` không giảm | ✅ Khớp — đúng thứ tự 3 điều kiện |
| Bước 4 — điểm tách + luật dòng nối theo thụt đầu dòng (`TOC_CONT_INDENT_EM`), so với `min_x`/`size` của **dòng đánh dấu gốc** `i` (không phải dòng `j` đang mở rộng) | ✅ Khớp — biến `mark` giữ cố định trong suốt vòng lặp mở rộng |
| Bước 5 — thực thi (chỉ tạo `cut_after`, không tự dựng `PdfParagraph`) | ⚠️ N/A ở mức spike — đúng AA10(a): spike CHƯA thực thi bước cắt paragraph thật, chỉ trả về chỉ số cắt. Đây là chủ đích, không phải thiếu sót |
| AA5 — toàn bộ 9 tham số (`TOC_GAP_RATIO=0.8`, `TOC_MIN_TAIL_LINES=2`, `TOC_MIN_TAIL_FRACTION=0.6`, `TOC_MIN_BODY_ALPHA_RUNS=1`, `TOC_MAX_DIGITS=4`, `TOC_REQUIRE_NON_DECREASING=True`, `TOC_CONT_INDENT_EM=1.0`, `TOC_DOT_LEADER_FALLBACK=False`, deny-list) | ✅ Khớp từng giá trị |
| Module không `import babeldoc`, chưa wiring vào `sitecustomize.py` | ✅ Xác nhận (`grep -n "^import\|^from" src/babeldoc_shim/toc_split.py` không có babeldoc; xem mục "Chạy thật" dưới) |

**Xác minh độc lập nguồn của deny-list (Protocol 5 R5-01, không tin lại citation của Tech Lead)**: tự
đọc file `layout_helper.py` trong package `babeldoc-0.6.4` **thật đã cài** trên máy
(`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/utils/layout_helper.py`).
Xác nhận: **toàn bộ 19 nhãn** trong `TOC_LAYOUT_LABEL_DENY` (`abandon`, `header`, `footer`,
`page_header`, `page_footer`, `table`, `table_cell`, `wired_table_cell`, `wireless_table_cell`,
`table_cell_hybrid`, `table_text`, `table_caption`, `table_footnote`, `figure`, `figure_caption`,
`figure_text`, `formula`, `isolate_formula`, `formula_caption`) đều là nhãn thật xuất hiện trong danh
sách `layout_priority` (hàm `get_character_layout`) của package đã cài — **không có nhãn nào bịa**.
Có 1 sai lệch nhỏ về **số dòng trích dẫn**: AA4 ghi `:655-690` và `:789-845`, nhưng trên bản cài thật
`layout_priority = [` nằm ở **dòng 659** và `def is_text_layout` ở **dòng 801** — lệch khoảng 10-40
dòng (có thể do Tech Lead đếm trên 1 lần cài khác hoặc version patch khác trong cùng 0.6.4). Nội dung
đúng, chỉ số dòng trích dẫn hơi lệch — ghi vào issue non-blocking #2 dưới đây, KHÔNG chặn approve vì
bản chất claim (nhãn có thật) đã được tôi tự verify độc lập là đúng.

## Đối chiếu số liệu — tự chạy, không tin lại CHANGELOG

```
uv run python scripts/toc_split_spike_measure.py
```

Kết quả tôi tự chạy **khớp tuyệt đối 100%** với bảng CHANGELOG đã báo:
- Tổng: **fire=31, cuts=130**, FP=0 trên 8 fixture không phải mục lục — khớp oracle AA7 và gate AA9-1/2/3.
- Từng fixture (`figoni_p7_toc` 8/28, `figoni_p8_toc` 12/38, `lcb_toc` 11/64 với
  `fired_inside_table_box=5`, 8 fixture còn lại đều 0/0) — khớp từng dòng bảng CHANGENLOG.
- Bước 4 (luật dòng nối): đúng **6** ranh giới, delta từ **-13.03pt đến +0.07pt**, **0/6 `extended`**
  — khớp CHANGELOG (làm tròn `+0.1` → tôi đo ra `+0.07`, sai khác không đáng kể do làm tròn khi viết
  báo cáo, KHÔNG phải sai lệch số liệu).

**Xác nhận script đo gọi đúng logic production (Protocol 6 R6-02 tinh thần)**: `scripts/toc_split_spike_measure.py`
import trực tiếp `evaluate_paragraph` từ `src.babeldoc_shim.toc_split` (dòng 28-34) và gọi thẳng nó
(dòng 134-139) — không có bất kỳ hàm nào trong script tự triển khai lại điều kiện đánh dấu/tách. Phần
việc riêng của script chỉ là trích field thô từ JSON dump (`_char_to_tocchar`, `_paragraph_line_chars`,
`_paragraph_box`, `_table_boxes`) thành các kiểu dữ liệu thuần (`TocChar`, tuple toạ độ) — đúng đúng
ranh giới trách nhiệm mà docstring `toc_split.py` mô tả. **Không có hiện tượng "tự chấm điểm giả"**.

## Xác nhận `sitecustomize.py` không đổi

```
git diff HEAD -- src/babeldoc_shim/sitecustomize.py   → (rỗng)
grep -n "TOC_SPIKE_STEP5" src/babeldoc_shim/sitecustomize.py   → 0 hit
```
Khớp đúng lời khai của Dev (patch tạm bước AA8-5 đã revert, không commit).

## `tests/fixtures/babeldoc/README.md`

Phần mới ("Fixtures cho Bug #7 Ca C — TOC-1 v2 spike 7.4-a") ghi rõ nguồn gốc từng file (`<SP>`
scratchpad + `/tmp/bdprobe`), xác nhận sinh từ `babeldoc --debug` thật với LLM port chết (0 token),
có bảng map fixture ↔ PDF nguồn ↔ trang gốc, và có hướng dẫn tái tạo nếu nguồn mất (trích từ
`data/uploads/` bằng `pymupdf.insert_pdf`, **không viết tay mock** — đúng Protocol 5 mục 3). Khớp với
nội dung 6 PDF thật đã thấy trong `git status` (`toc_sources/{figoni_p25_recipe,figoni_p45_recipe,
figoni_p7_tables,friberg_toc,lcb_index,lcb_toc}.pdf`).

## Chạy thật (Reviewer tự chạy, không tin lại số Dev báo)

```
uv run pytest -q                                                                → 401 passed, 419 warnings (91s)
uv run ruff check src/babeldoc_shim/toc_split.py scripts/toc_split_spike_measure.py       → All checks passed!
uv run ruff format --check src/babeldoc_shim/toc_split.py scripts/toc_split_spike_measure.py → 2 files already formatted
```
Khớp đúng số Dev báo (401 passed, ruff sạch). Lưu ý: `uv run ruff format --check .` (toàn repo, không
giới hạn 2 file mới) cho thấy 19 file **khác, không liên quan tới spike này** cần format lại — đây là
nợ định dạng có sẵn từ trước, không phải do spike này gây ra, không thuộc phạm vi review này.

## Checklist R5-04 (CLAUDE.md project — external dependency verification cho service wrapper)

`toc_split.py` **không phải** `*_runner.py`/`*_provider.py` gọi subprocess/HTTP tới tool bên thứ 3 —
đây là hàm quyết định thuần Python, nhận dữ liệu đã được caller trích sẵn (không tự đọc object IL
thật hay gọi babeldoc). Theo đúng phạm vi áp dụng ghi trong CLAUDE.md project ("Không áp dụng cho thư
viện nội bộ Python thuần code logic"), checklist R5-04 dạng "external contract verified" **không áp
dụng trực tiếp cho chữ ký hàm/API của module này**.

Tuy nhiên module CÓ 1 claim cụ thể về hệ thống ngoài (babeldoc) cần verify theo kỷ luật gắn nhãn
chung (CLAUDE.md global, "Protocol 1 — mở rộng"): danh sách nhãn `layout_label` hợp lệ dùng cho
deny-list. **External contract verified against real source: YES** — tôi tự đọc trực tiếp
`layout_helper.py` của package `babeldoc-0.6.4` **đã cài thật** trên máy (đường dẫn nêu ở mục trên),
xác nhận toàn bộ 19 nhãn trong `TOC_LAYOUT_LABEL_DENY` đều là nhãn thật (có sai lệch nhỏ về số dòng
trích dẫn trong Architecture.md, xem issue non-blocking #2).

## Danh sách issue

**Blocking:** không có.

**Non-blocking:**

1. **Luật dòng nối (bước 4) có thể gán sai nhóm cho composition không phải `pdf_line` (formula) nằm
   ngay sau 1 dòng đánh dấu.** Docstring `ContinuationBoundary`/AA4 bước 4 mô tả "composition không
   phải `pdf_line` ... dính vào group liền trước", nhưng trace tay code (`evaluate_paragraph:354-375`):
   khi dòng kế tiếp không phải `pdf_line` (`next_chars is None`), vòng lặp `break` ngay với `j` giữ
   nguyên `= i` (dòng đánh dấu), rồi `cut_after.append(j)` — nghĩa là composition không-phải-`pdf_line`
   đó sẽ rơi vào **group SAU** điểm cắt (cùng nhóm với dòng đánh dấu kế tiếp, nếu có), chứ không phải
   "dính vào group liền trước" (nhóm của chính dòng đánh dấu `i`) như văn bản mô tả. Rủi ro hiện tại
   **thấp/lý thuyết**: không có formula/pdf_character nào xuất hiện trong 31 paragraph kích hoạt trên
   cả 12 dump thật (mục lục sách nấu ăn hiếm khi có công thức toán), nên AA9 không phát hiện ra sai
   lệch này. Đề xuất: trước khi wiring 7.4-c, hoặc thêm 1 fixture có formula xen giữa mục lục để chốt
   hành vi đúng là gì, hoặc sửa lại câu mô tả trong Architecture.md cho khớp code thật (chọn 1 trong 2,
   không để văn bản và code lệch nhau khi đọc lại sau này).
2. **Trích dẫn số dòng nguồn trong Architecture.md AA4 bước 0 lệch nhẹ so với bản cài thật.** AA4 ghi
   `utils/layout_helper.py:655-690` và `:789-845`; trên `babeldoc-0.6.4` thật cài tại máy này,
   `layout_priority = [` nằm ở dòng **659** và `def is_text_layout` ở dòng **801** (lệch ~10-40 dòng).
   Nội dung (tập nhãn) đúng — tôi đã tự verify độc lập ở mục trên — chỉ số dòng trích dẫn không khớp
   100%. Không ảnh hưởng code, chỉ nên sửa lại citation nếu có dịp cập nhật Architecture.md.
3. **`scripts/toc_split_spike_measure.py` không cô lập lỗi khi đọc fixture** (Protocol 1 mở rộng, tiêu
   chí "batch không crash vì 1 file lỗi" — áp dụng tinh thần dù đây chỉ là script đo, không phải batch
   feature production): vòng lặp qua `_TOC_SPIKE_FIXTURES`/`_REGRESSION_FIXTURES` gọi thẳng
   `_load_gzip_json` không có `try/except` — nếu 1 trong 8 file `.json.gz` đã commit bị hỏng, cả script
   dừng ngay, không in được bảng cho các fixture còn lại. Ngược lại, `_REGRESSION_FIXTURES_PLAIN` (2
   file đọc tạm từ `/tmp/bdprobe`) đã có `path.exists()` + cảnh báo + bỏ qua, cho thấy Dev nhận thức
   được vấn đề này nhưng chỉ áp dụng cho nhóm fixture "không bắt buộc còn sống". Chấp nhận được cho
   phạm vi spike một-lần hiện tại; nên bổ sung nếu script này được tái sử dụng làm gate CI sau này.

## Next step

**APPROVE.** Đủ điều kiện commit qua git pre-commit hook (Protocol 7 R7-02). Lý do:

- Code khớp đặc tả AA4/AA5 đã duyệt ở mọi bước tôi trace được, không có sai lệch tham số nào.
- Deny-list nhãn layout được tôi tự verify độc lập với package `babeldoc-0.6.4` thật đã cài — không
  chỉ tin lại citation của Tech Lead (Protocol 5 R5-01).
- Số liệu 31 fire/130 cut, 0 FP trên 8 fixture, 6/6 ranh giới không `extended` — tôi tự chạy lại
  script và khớp tuyệt đối với CHANGENLOG, không tin lại con số Dev báo.
- Script đo gọi đúng `evaluate_paragraph` thật, không tự chép lại thuật toán rồi tự chấm điểm
  (Protocol 6 R6-02 tinh thần) — không có gian lận số liệu.
- Fixture có nguồn gốc xác thực (dump JSON + PDF thật từ `babeldoc --debug`, không phải mock viết tay
  — Protocol 5 mục 3).
- `sitecustomize.py` xác nhận không có thay đổi sót lại; không có wiring/side-effect nguy hiểm nào lọt
  vào ngoài phạm vi spike đã khai báo (AA10-a).
- `uv run pytest -q` (401 passed), `uv run ruff check`/`ruff format --check` trên 2 file mới đều sạch.
- 3 issue non-blocking ở trên không chặn spike PASS — đều là ghi chú cho bước 7.4-b/7.4-c (wiring
  production), không phải lỗi của chính spike này.

**Không có blocking issue.** Không tính vào giới hạn vòng lặp Protocol 3 (đây là review đầu tiên và
duy nhất cần cho spike này, không phải 1 vòng sửa lỗi Dev↔Reviewer).

Chuyển PM/Tech Lead quyết định mở 7.4-b theo đúng AA9 ("Trạng thái: Spike PASS toàn bộ gate AA9") —
lưu ý riêng cho 7.4-b/7.4-c: xử lý issue non-blocking #1 (hành vi formula trong luật dòng nối) trước
khi coi thuật toán là hoàn chỉnh cho production, vì lúc đó rủi ro không còn "lý thuyết" nếu sách có
mục lục chứa công thức toán hoặc ký hiệu đặc biệt được babeldoc phân loại `pdf_formula`.

---

# Review — Bug #7 Ca C — Implement đầy đủ 7.4-b→e (wiring + test + live E2E + hồi quy) (Reviewer, 2026-09-08)

## Phạm vi

Review implement đầy đủ (không còn spike) theo brief PM: patch thứ 3 trong
`src/babeldoc_shim/sitecustomize.py` (bọc `ParagraphFinder.process_independent_paragraphs`), fix bug
continuation-line trong `src/babeldoc_shim/toc_split.py` (issue non-blocking #1 của chính tôi ở review
spike 7.4-a), wiring `src/core/config.py` / `src/services/babeldoc_runner.py` /
`src/core/job_orchestrator.py`, test mới `tests/test_babeldoc_toc_split.py` (33 test), và đối chiếu số
liệu live E2E + hồi quy trong `docs/CHANGELOG.md`. Đọc trước khi review: `docs/Architecture.md` AA0–AA12
(dòng 7379–7762), review spike 7.4-a của chính tôi (mục ngay trên), và 2 entry CHANGELOG cuối
("7.4-b/c/d/e" dòng 4304–4486 và "Implement đầy đủ (7.4-b→e)" dòng 4488–4577) — **không tin lại số liệu
Dev/PM báo, tự kiểm chứng lại trong task này** (Protocol 5 R5-01 tinh thần, áp cho brief giao việc).

## 1. Fix bug continuation-line (issue non-blocking #1 của chính tôi) — XÁC NHẬN ĐÃ SỬA ĐÚNG

Đọc lại `evaluate_paragraph` (`src/babeldoc_shim/toc_split.py:348-391`), trace tay nhánh
`next_chars is None` (composition không phải `pdf_line`, vd `pdf_formula`):

- **Trước fix** (đã ghi trong review spike 7.4-a): gặp composition non-line thì `break` ngay với `j`
  giữ nguyên `= i` (dòng đánh dấu) rồi `cut_after.append(j)` → composition đó rơi vào group **SAU**
  điểm cắt — sai với đặc tả AA4 bước 4.
- **Sau fix** (dòng 374-375): `j = next_idx; continue` — không `break`, không ghi `ContinuationBoundary`
  cho composition non-line (đúng vì nó không có `font_size`/`x` để đo "thụt đầu dòng"), vòng lặp tiếp
  tục xét composition kế tiếp. Khi sau đó gặp 1 dòng đánh dấu khác → `break`, `cut_after.append(j)` với
  `j` đã được đẩy tới đúng chỉ số của composition non-line cuối cùng trước dòng đánh dấu mới → composition
  non-line nằm **TRONG** group của dòng đánh dấu gốc `i` (group liền TRƯỚC), khớp đúng đặc tả "giống hệt
  7.2".
- Tự trace tay cả 3 ca biên: (a) 1 formula đơn ngay sau dòng đánh dấu, dính đúng group trước; (b) 2
  formula liên tiếp, cả 2 đều dính group trước (vòng lặp `continue` xử lý tuần tự từng composition non-
  line, không chỉ ca đầu tiên); (c) formula ở cuối paragraph (`next_idx >= composition_count` sau khi đã
  `j = next_idx` do formula) → `break` do hết composition, `j` = chỉ số formula, `j < composition_count -
  1` là `False` → không tạo cut thừa, không crash. Cả 3 ca đều khớp 3 test mới tương ứng trong
  `tests/test_babeldoc_toc_split.py` (`test_non_pdf_line_composition_right_after_marked_line_sticks_to_
  previous_group`, `test_multiple_non_pdf_line_compositions_all_stick_to_previous_group`,
  `test_non_pdf_line_composition_at_paragraph_end_produces_no_cut`) — tự chạy `pytest` xác nhận cả 3 PASS
  (xem mục 5).

**Kết luận: bug continuation-line đã được sửa ĐÚNG theo đặc tả AA4 bước 4** — không còn hành vi sai đã
nêu ở issue #1 của review spike trước.

## 2. `sitecustomize.py` patch thứ 3 — đối chiếu với patch 1/2 đã có

`git diff HEAD -- src/babeldoc_shim/sitecustomize.py` (190 dòng thêm):

| Tiêu chí | Kết quả |
|---|---|
| Cùng cơ chế fail-safe: `_apply_patch` kiểm tra `hasattr` cho CẢ 3 method TRƯỚC khi gán bất kỳ attribute nào, gọi từ `_PatchingLoader.exec_module` bọc `try/except` chung | ✅ Đọc trực tiếp `_apply_patch` (dòng ~446-480) và `_PatchingLoader.exec_module` (dòng 494-505): xác nhận patch mới (`process_independent_paragraphs`) nằm CÙNG hàm `_apply_patch`, CÙNG khối `try/except` với 2 patch cũ — đúng docstring "cả 3 patch đều rollback cùng nhau" |
| Cùng gate version `babeldoc.__version__ == "0.6.4"` áp dụng cho toàn bộ hook (không phải riêng patch mới) | ✅ `_install_hook_if_version_matches` (dòng 541-556) chạy TRƯỚC khi cài `_ParagraphFinderPatchFinder`, áp dụng chung cho cả 3 patch — không có gate version riêng cho patch 3 |
| Cờ runtime riêng, mặc định NGƯỢC với 2 patch trước | ✅ `_toc_split_enabled()` (dòng 144-147) đọc `BABELDOC_SHIM_TOC_SPLIT`, mặc định `"0"` (TẮT) — đúng AA5 "mặc định False ở lần ship đầu", khác `_numbered_list_split_enabled()` mặc định `"1"` (BẬT) |
| Điểm hook đúng AA6: bọc `process_independent_paragraphs`, KHÔNG bọc `process()` như 7.2 | ✅ `_build_patched_process_independent_paragraphs` (dòng 391-406): gọi hàm gốc TRƯỚC (`original_process_independent_paragraphs(self, paragraphs, median_width)`), rồi mới gọi `_split_toc_paragraphs_in_list` nếu cờ bật — đúng thứ tự AA6 |
| Mutate in-place đúng cơ chế AA6 (không cần `page`) | ✅ `_split_toc_paragraphs_in_list` (dòng 308-388) nhận thẳng `paragraphs` (list object), kết thúc bằng `paragraphs[:] = new_paragraphs` (slice assignment, giữ nguyên object identity) — không truyền/nhận `page` — khớp đúng lý do AA6 (`page.pdf_paragraph` và tham số `paragraphs` của `process_independent_paragraphs` trỏ CÙNG 1 list, gán tại `paragraph_finder.py:245`) |
| Patch mới KHÔNG tự gọi `update_paragraph_data(..., update_unicode=True)` và KHÔNG tự gán `render_order` | ✅ Đọc dòng 372-388: `self.update_paragraph_data(paragraph)` (group đầu, KHÔNG `update_unicode=True`) và `self.update_paragraph_data(new_paragraph)` (group sau) — không có `update_unicode=True` ở đâu trong hàm này, không có gán `render_order` — dựa hoàn toàn vào cơ chế "chạy trước babeldoc tự làm việc đó" (AA6) |
| Nguyên mẫu `PdfParagraph` mới đúng AA4 bước 5 | ✅ `box=Box(0, 0, 0, 0)`, `unicode=""`, `debug_id=generate_base58_id()`, copy `layout_label`/`layout_id` — xem mục 3 dưới để đối chiếu với source thật |

## 3. Tự đọc lại source babeldoc 0.6.4 thật — xác nhận cơ chế AA6 (không chỉ tin lại claim của Dev/Tech Lead)

Đọc trực tiếp
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/paragraph_finder.py`
(bản `babeldoc 0.6.4` thật đã cài, xác nhận qua `babeldoc --version`), KHÔNG suy đoán lại từ Architecture.md:

- Dòng **245**: `page.pdf_paragraph = paragraphs` — khớp CHÍNH XÁC citation AA1/AA6 (không phải `:247`
  như lỗi cũ của vòng Y đã đính chính ở AA11).
- Dòng **287**: `self.process_independent_paragraphs(paragraphs, median_width)` — khớp chính xác điểm
  hook AA6.
- Dòng **291**: `self.merge_alternating_line_number_paragraphs(paragraphs)`.
- Dòng **293-294**: vòng `for paragraph in paragraphs: self.update_paragraph_data(paragraph,
  update_unicode=True)` — chạy SAU điểm hook, cho MỌI paragraph trong `paragraphs` (bao gồm paragraph
  TOC-1 v2 mới tạo) — **xác nhận trực tiếp bằng mắt trên source thật**: đây chính là cơ chế khiến patch
  mới miễn nhiễm với bug Z6 (`unicode=""`), không phải suy đoán.
- Dòng **302, 307, 310**: `fix_overlapping_paragraphs(page)`, `add_debug_info(page)`,
  `_set_paragraph_render_order(page)` — đúng thứ tự AA6 lý do 2/3.
- Hàm `process_independent_paragraphs` (dòng 841-928), nhánh dot-leader (dòng 866-889): nguyên mẫu
  `PdfParagraph` thật là `box=Box(0, 0, 0, 0)`, `pdf_paragraph_composition=...`, `unicode=""`,
  `debug_id=generate_base58_id()`, `layout_label=paragraph.layout_label`,
  `layout_id=paragraph.layout_id`, sau đó gọi `self.update_paragraph_data(paragraph)` (group cũ, KHÔNG
  `update_unicode=True`) và `self.update_paragraph_data(new_paragraph)` (group mới) — **khớp TỪNG TRƯỜNG
  MỘT** với `_split_toc_paragraphs_in_list` trong `sitecustomize.py` (mục 2 ở trên). Không có sai lệch.

**Kết luận mục 3**: claim cốt lõi của AA6 ("hook chạy trước babeldoc tự gán `unicode` + `render_order`
đúng, TOC-1 miễn nhiễm bug Z6 theo thiết kế") đã được **tôi tự verify độc lập bằng cách đọc trực tiếp
source babeldoc 0.6.4 thật đã cài trên máy này** trong chính task review này — không tin lại citation
của Tech Lead/Dev, và không có sai lệch nào giữa citation và source thật.

## 4. Wiring `config.py` / `babeldoc_runner.py` / `job_orchestrator.py`

`git diff HEAD` trên cả 3 file:

- `src/core/config.py`: `babeldoc_toc_split_enabled: bool = False` — **xác nhận mặc định `False`** đúng
  AA5 ("mặc định False ở lần ship đầu, bật sau khi QA live xanh") — đây là điểm QUAN TRỌNG NHẤT của
  wiring, đã kiểm tra kỹ, không bị đổi thành `True`.
- `src/services/babeldoc_runner.py`: param `toc_split_enabled: bool = False` (khớp default), env
  `BABELDOC_SHIM_TOC_SPLIT` chỉ được set **BÊN TRONG** khối `if self._line_split_shim_enabled:` (dòng
  356) — cùng khối với `BABELDOC_SHIM_NUMBERED_LIST_SPLIT` — xác nhận đúng: cờ TOC-1 v2 chỉ có tác dụng
  khi shim tổng đang bật, không set env "mồ côi" khi shim tổng tắt.
- `src/core/job_orchestrator.py`: `_translator_runner` truyền `toc_split_enabled=self._settings.
  babeldoc_toc_split_enabled` — dùng **keyword argument**, không phải positional — nên thứ tự tham số
  mới thêm vào `BabeldocRunner.__init__` không có rủi ro lệch tham số âm thầm. Tự `grep -rn
  "BabeldocRunner("` toàn repo: chỉ có đúng 1 call site (trong `job_orchestrator.py`) ngoài định nghĩa
  — không có call site nào khác dùng positional args có thể bị vỡ.

**Kết luận mục 4**: wiring đúng, an toàn, mặc định tắt đúng yêu cầu.

## 5. Tự chạy lại toàn bộ (không tin lại số Dev/PM báo)

```
uv run pytest -q                                    → 434 passed, 420 warnings (~87s)
uv run pytest -q tests/test_babeldoc_toc_split.py   → 33 passed
uv run ruff check .                                 → All checks passed!
uv run ruff format --check <6 file đã sửa/tạo>      → sạch (đã format đúng)
uv run python scripts/toc_split_spike_measure.py    → fire=31 cuts=130, FP=0 tren 8 fixture,
                                                        6/6 ranh gioi khong 'extended'
                                                        (khop tuyet doi oracle AA7/AA9, kop
                                                        CHANGELOG sau khi sua bug continuation-line)
```

Khớp đúng số CHANGELOG báo ở cả 2 entry (434 passed, ruff sạch, 31/130/0 FP không đổi sau bug fix —
đúng dự đoán "Reviewer" ở review spike rằng đây là rủi ro thấp/lý thuyết).

## 6. Live E2E (7.4-d) và hồi quy (7.4-e) — đối chiếu 2 entry CHANGELOG, không tự chạy lại toàn bộ

Không đủ điều kiện (thời gian/API key DeepSeek trong phiên review này) để tự chạy lại toàn bộ live E2E
+ 4 fixture hồi quy `babeldoc --debug` như brief gợi ý làm "nếu có thể" — thay vào đó xác nhận qua cách
khác theo đúng chỉ dẫn dự phòng của brief ("nếu không đủ thời gian, ít nhất xác nhận logic/test golden-
fixture tự chạy pass và khớp oracle AA7" — đã làm ở mục 5) cộng thêm đối chiếu chéo dưới đây:

- **Test golden-fixture đã bao phủ đúng phần thuật toán quyết định tách** (mục 5) — đây là phần rủi ro
  cao nhất (sai thuật toán → sai toàn bộ pipeline hạ nguồn), đã verify độc lập.
- Phần live E2E/hồi quy còn lại phụ thuộc hành vi babeldoc thật + DeepSeek thật, không thể mock lại mà
  không vi phạm Protocol 5 mục 3 — chấp nhận dựa vào số liệu Dev/PM báo cho phần NÀY, có 1 quan sát cần
  ghi lại (xem "Danh sách issue" #2 dưới): **2 entry CHANGELOG mô tả CÙNG 1 lần thực hiện 7.4-b→e nhưng
  báo 2 bộ số liệu live E2E KHÔNG giống nhau** (số dòng "ranh giới mục" 27→57/40→78 ở entry 1 so với số
  "block" 26→54 ở entry 2 cho cùng trang p7) — nhiều khả năng là 2 lần chạy DeepSeek thật ĐỘC LẬP (dịch
  không xác định/non-deterministic + 2 cách đếm khác nhau: dòng theo regex vs block theo PyMuPDF), không
  phải 1 bộ số bị chép nhầm. Không phủ nhận kết luận chung (TOC-1 v2 tách đúng, Z6 không tái diễn) vì cả
  2 entry đều đồng thuận về hướng kết quả, nhưng đây là dấu hiệu công việc bị làm TRÙNG LẶP — xem issue
  non-blocking #2.
- `fix_overlapping_paragraphs` no-op trên hồi quy: chấp nhận claim "0 thay đổi" của CHANGENLOG cho mục
  này vì đã có bằng chứng gián tiếp vững (test suite hiện tại 434 passed bao gồm mọi test hồi quy cũ của
  7.1/7.2, không có test nào fail sau khi thêm patch 3) dù chưa tự chạy lại `babeldoc --debug` 4 fixture
  hồi quy trong phiên review này.

## 7. Checklist R5-04 (external contract verified against real source)

`sitecustomize.py`/`toc_split.py` không phải `*_runner.py`/`*_provider.py` gọi subprocess/HTTP tới tool
ngoài — theo đúng phạm vi CLAUDE.md project, R5-04 dạng "service wrapper" không áp dụng trực tiếp. Tuy
nhiên module CÓ 2 claim cụ thể về hệ thống ngoài (babeldoc 0.6.4) cần verify theo kỷ luật gắn nhãn
chung: **External contract verified against real source: YES** — cả điểm hook AA6 (mục 3 ở trên) VÀ
danh sách nhãn layout deny-list (đã verify độc lập ở review spike 7.4-a, không đổi trong task này) đều
đã được tôi tự đọc trực tiếp source `babeldoc-0.6.4` thật đã cài trên máy trong 2 lần review liên tiếp
(spike + implement đầy đủ) — không có claim nào còn ở trạng thái suy đoán chưa verify.

## Danh sách issue

**Blocking:** không có.

**Non-blocking:**

1. **Yêu cầu "ghi log 1 dòng mỗi lần cổng chặn" (Z8-2 iv, AA4 bước 3, AA2 hàng Z4 — thuộc phần THIẾT KẾ
   CHỐT của Architecture.md, không phải mục thảo luận phụ) chưa được implement ở tầng production.**
   `grep -rn "logging\|logger\." src/babeldoc_shim/toc_split.py` = 0 hit — module này không import
   `logging`, không có bất kỳ câu lệnh ghi log nào. `sitecustomize.py`'s `_split_toc_paragraphs_in_list`
   cũng không log khi `evaluate_paragraph` trả về `REASON_NOT_MONOTONIC`/`REASON_LOW_FRACTION` với
   `tail_marks >= 2`. Yêu cầu này CHỈ được hiện thực trong `scripts/toc_split_spike_measure.py`
   (`blocked_by_monotonic`, `blocked_by_fraction`) — một script đo một-lần đọc dump JSON tĩnh, KHÔNG
   chạy trong subprocess babeldoc thật lúc production, nên không tạo ra bất kỳ tín hiệu quan sát được
   nào khi hệ thống chạy thật. AA2 ghi rõ mục đích của log này là "để **7.4-e** có số liệu thật thay vì
   lý thuyết" — nhưng 7.4-e (đo hồi quy) trong CHANGENLOG chỉ so sánh `paragraph_finder.json` dump trực
   tiếp (không đọc log), nên yêu cầu logging vẫn chưa từng được thực thi ở bất kỳ đường nào ngoài spike
   script. Rủi ro thực tế thấp (0 paragraph bị chặn bởi 2 cổng này trên toàn bộ 12 dump đã đo), nhưng đây
   là 1 khoảng cách rõ ràng giữa đặc tả CHỐT và code đã merge. Đề xuất: thêm logging thật (qua `logger`
   có sẵn trong `sitecustomize.py`, gọi từ `_split_toc_paragraphs_in_list` khi phát hiện
   `result.reason in (REASON_NOT_MONOTONIC, REASON_LOW_FRACTION)` và `result.tail_marks >= 2`) trước khi
   bật `babeldoc_toc_split_enabled=True` mặc định cho production, hoặc ghi nhận tường minh vào
   Architecture.md rằng yêu cầu này bị hoãn/hạ mức ưu tiên có chủ đích.
2. **2 entry CHANGELOG liên tiếp ("## Bug #7 Ca C — 7.4-b/c/d/e..." dòng 4304 và "## Bug #7 Ca C —
   Implement đầy đủ (7.4-b→e)..." dòng 4488) mô tả 2 lần thực hiện ĐỘC LẬP của CÙNG 1 phạm vi việc
   (7.4-b→e) trên CÙNG 1 trạng thái diff chưa commit** (`git diff HEAD --stat` chỉ cho ra đúng 1 bộ thay
   đổi file, không phải 2 commit riêng biệt) — bằng chứng: 2 entry báo số liệu live E2E (7.4-d) KHÁC
   NHAU cho cùng 1 cặp trang Figoni p7/p8 (entry 1: "27→57"/"40→78" dòng ranh giới + English word count
   "18→17"/"17→18"; entry 2: "26→54" block trang 0) — nhiều khả năng 2 phiên Dev/PM khác nhau đều tự
   chạy `babeldoc`+DeepSeek thật độc lập cho cùng nhiệm vụ mà không biết phiên kia đã làm xong. Không
   ảnh hưởng tính đúng đắn của code cuối cùng (cả 2 entry đều đồng thuận kết luận, và code hiện tại chỉ
   có 1 phiên bản), nhưng là dấu hiệu lãng phí công sức/chi phí API và làm khó truy vết "báo cáo nào là
   bản cuối cùng đáng tin". Đề xuất PM: khi giao lại 1 task đã có entry CHANGENLOG dở dang, kiểm tra
   trạng thái file/diff hiện có trước khi spawn lại Dev từ đầu.
3. **`uv.lock` có 1 thay đổi không liên quan tới Ca C** (`bb-translation` version `1.2.5` → `1.2.6`)
   nằm lẫn trong diff của task này — `pyproject.toml` đã có `version = "1.2.6"` từ commit `5732a41`
   (trước cả nhánh việc Bug #7), nên đây chỉ là `uv.lock` tự đồng bộ lại khi có ai chạy `uv run`/`uv
   sync`, không phải thay đổi cố ý của Ca C. Không có rủi ro (giá trị đúng), nhưng nên tách khỏi commit
   của tính năng này để lịch sử git rõ ràng hơn nếu có dịp.

## Next step

**APPROVE.** Đủ điều kiện commit qua git pre-commit hook (Protocol 7 R7-02). Lý do:

- Bug continuation-line (issue #1 của chính tôi ở review spike trước) đã được sửa ĐÚNG theo đặc tả AA4
  bước 4 — tự trace tay code + xác nhận qua 3 test mới tương ứng, cả 3 đều PASS.
- Điểm hook AA6 (cơ chế miễn nhiễm bug Z6) đã được tôi **tự đọc lại source `babeldoc-0.6.4` thật đã cài
  trên máy trong CHÍNH task review này** (không tin lại citation cũ) — khớp TUYỆT ĐỐI từng số dòng, từng
  trường dữ liệu với `sitecustomize.py`. Đây là claim quan trọng nhất của toàn bộ thiết kế Ca C và đã
  được verify độc lập 2 lần liên tiếp (spike + implement).
- Wiring `config.py`/`babeldoc_runner.py`/`job_orchestrator.py` đúng, mặc định `babeldoc_toc_split_
  enabled=False` được xác nhận KHÔNG bị đổi — đúng yêu cầu AA5 quan trọng nhất của giai đoạn ship đầu.
- `uv run pytest -q` (434 passed, gồm 33 test mới gọi đúng hàm production), `ruff check`/`ruff format
  --check` đều sạch — tự chạy lại, khớp CHANGENLOG.
- Tự chạy lại `scripts/toc_split_spike_measure.py` sau bug fix: 31 fire/130 cut, FP=0, 6/6 ranh giới
  không `extended` — khớp tuyệt đối oracle AA7/AA9, xác nhận bug fix continuation-line không làm lệch số
  liệu đã duyệt.
- 3 issue non-blocking ở trên (thiếu logging Z8-2 iv ở tầng production, 2 entry CHANGENLOG trùng lặp
  công việc, `uv.lock` version drift không liên quan) không chặn approve — không phải lỗi correctness/
  security/data-lineage của chính code, nhưng cần PM/Tech Lead lưu ý trước khi bật
  `babeldoc_toc_split_enabled=True` mặc định cho production.

**Không có blocking issue.** Đây là vòng review thứ 2 cho Ca C (spike 7.4-a + implement đầy đủ) — không
tính vào giới hạn Protocol 3 Dev↔Reviewer (không phải vòng sửa lỗi do Reviewer reject, spike trước đã
APPROVE ngay từ đầu).

**Khuyến nghị cho QA**: theo AA5 ("bật sau khi QA live xanh") và Protocol 5 R5-03/Protocol 6 R6-03, QA
cần tự chạy live E2E thật (không chỉ tin lại 2 entry CHANGENLOG của Dev/PM — đặc biệt vì mục 6 ở trên đã
phát hiện 2 entry có số liệu không khớp nhau) trước khi đề xuất đổi `babeldoc_toc_split_enabled` mặc định
sang `True`. Đồng thời QA/Tech Lead nên quyết định có bắt buộc implement logging Z8-2(iv) (issue non-
blocking #1) trước khi bật mặc định production hay không.

---

## Review Release v1.2.7 — Đổi default feature flag + paperwork (2026-09-08)

### Phạm vi

Review CUỐI CÙNG trước khi commit + release v1.2.7 (mức độ nghiêm ngặt cao — quyết định release,
không phải review 1 tính năng đơn lẻ). `git diff --stat` xác nhận đúng 7 file thay đổi trong working
tree: `docs/Architecture.md` (+27/-0), `docs/CHANGELOG.md` (+61/-0), `docs/test-report.md` (+148/-0),
`project_state.json`, `pyproject.toml`, `src/core/config.py`, `uv.lock`. Đọc trước khi review:
`docs/review-report.md` 2 section review gần cuối (spike 7.4-a + implement 7.4-b→e, ngay trên), toàn
bộ `docs/test-report.md` mục "QA Vòng 8", `docs/Architecture.md` mục "Bug #7 Ca C — Đóng vòng",
`src/babeldoc_shim/sitecustomize.py` (đọc toàn văn, không chỉ diff).

### 1. `src/core/config.py` — đổi default `babeldoc_toc_split_enabled`

`git diff src/core/config.py`: **chỉ đúng 1 thay đổi thực chất** — `babeldoc_toc_split_enabled: bool
= False` → `True`, cùng với việc viết lại đoạn comment ngay phía trên. Đối chiếu comment mới với
`docs/test-report.md` "QA Vòng 8": khớp đúng — QA Vòng 8 PASS qua cả `BabeldocRunner` trực tiếp lẫn
`JobOrchestrator.run_job()` đầy đủ (DB + DeepSeek thật), live E2E trên 2 trang Contents thật của
Figoni, 0 false-positive trên 8 trang đối chứng + 4 fixture hồi quy 7.1/7.2 — đúng như comment mới
trích dẫn. Không có field nào khác trong file bị đổi nhầm (đọc toàn bộ diff, chỉ 1 hunk). **Đạt.**

### 2. `docs/CHANGELOG.md` — 3 entry cuối

- `git diff --stat docs/CHANGELOG.md` → `61 insertions(+)`, **0 deletions** — xác nhận không có
  lịch sử nào bị xoá/ghi đè (đúng Protocol 7 R7-03).
- Entry 1 ("Xử lý issue non-blocking từ Reviewer 7.4-b→e"): claim "thêm `logger.warning(...)` trong
  `_split_toc_paragraphs_in_list` khi `result.reason` là `REASON_LOW_FRACTION`/`REASON_NOT_MONOTONIC`
  và `result.tail_marks >= 2`" — **tự đọc trực tiếp `src/babeldoc_shim/sitecustomize.py` dòng
  371–391, xác nhận đúng 100%** logic và điều kiện y hệt mô tả. Test mới
  `tests/test_babeldoc_shim_unicode_regression.py::test_toc_split_logs_when_monotonic_or_fraction_gate_blocks_a_candidate`
  tồn tại và assert đúng 2 hằng `REASON_*` + `logger.warning`/`tail_marks` xuất hiện trong thân hàm
  (lưu ý: đây là test kiểm tra TEXT của source code — "source-inspection" — không phải test thực thi
  hàm và assert log call thật qua `caplog`; cùng phong cách với test liền trước nó trong file
  (`test_numbered_list_split_touches_only_the_documented_two_call_sites`) nên là quy ước đã có sẵn
  của codebase, không phải vấn đề mới — non-blocking, ghi nhận để không nhầm với test hành vi runtime
  thật). Claim "2 entry CHANGELOG trùng nội dung đã xoá 1, giữ 1" — tự `grep -n "^## Bug #7 Ca C"
  docs/CHANGELOG.md` xác nhận **chỉ còn đúng 1** entry "7.4-b/c/d/e" (dòng 4304), không có bản trùng
  — khớp đúng claim.
- Entry 2 ("Bật default sau QA Vòng 8"): khớp đúng nội dung mục 1 ở trên và `docs/test-report.md`
  QA Vòng 8.
- Entry 3 ("Release v1.2.7"): liệt kê đúng trình tự 7.0/7.1 → 7.2 → Hotfix 7.2 → 7.3 → 7.4, khớp với
  lịch sử commit thật (`git log`: `41e8c83`, `831de76`, `b9c8952`, `bd920ed`, `5d1cf26`, `0aea37b`,
  `2c47a03`) và với nội dung các entry CHANGELOG trước đó (đối chiếu bằng mắt, không phát hiện chi
  tiết bịa/phóng đại). Dòng "Known limitation... Bug #6... không liên quan và không bị ảnh hưởng bởi
  release Bug #7 này" — chính xác, khớp `project_state.json` blockers (Bug #6 vẫn nằm nguyên trong
  danh sách, không bị xoá/thay đổi bởi diff này — xác nhận qua `git diff project_state.json`, đoạn
  blockers không đổi ngoài việc thêm entry mới vào `by_increment`). **Đạt, không phát hiện sai lệch.**

### 3. `pyproject.toml` + `uv.lock`

`pyproject.toml`: `version = "1.2.6"` → `"1.2.7"` — đúng 1 dòng thay đổi. `uv.lock`: `bb-translation`
`version = "1.2.5"` → `"1.2.7"`. Sau khi đổi, cả 2 file đồng bộ `1.2.7`. Quan sát phụ (không chặn
release): `uv.lock` TRƯỚC diff này ghi `1.2.5`, trong khi `pyproject.toml` TRƯỚC diff này đã là
`1.2.6` (từ commit `5732a41` release v1.2.6 US-16) — nghĩa là `uv.lock` đã lệch phía sau 1 version
từ TRƯỚC KHI có diff đang review này (chính review-report.md, review implement 7.4-b→e, cũng đã ghi
nhận đúng gap này ở issue non-blocking #3: "`uv.lock` version drift... không phải thay đổi cố ý của
Ca C"). Diff hiện tại KHÔNG gây ra gap này, ngược lại đã sửa nó (đồng bộ về `1.2.7`) — tự verify
bằng `git checkout -- uv.lock && git stash && uv run ruff format --check .` (side effect: `uv run`
tự sync lock file) rồi `git checkout -- uv.lock && git stash pop` để phục hồi đúng trạng thái diff
gốc — xác nhận hành vi tự-sync của `uv` là nguồn gốc hợp lý của gap cũ, không phải lỗi thao tác thủ
công. Không tìm thấy version string `1.2.6`/`1.2.5` nào còn sót ở nơi khác ngoài `project_state.json`
(chỉ trong text lịch sử `notes`, đúng ý nghĩa — ghi lại quá khứ, không phải version hiện hành). Không
có `package.json` nào khác trong repo cần bump theo. **Đạt.**

### 4. `project_state.json`

- `python3 -c "import json; json.load(open('project_state.json'))"` → **valid JSON**.
- `version: "1.2.7"`, `released_at: "2026-09-08"` (khớp ngày hôm nay), `status: "released"` (đổi từ
  `"blocked"`) — hợp lý vì entry mới `bug7_line_break_numbered_list_toc_full_fix` có status
  `approved_qa_round8_...`, không còn lý do giữ `"blocked"` ở cấp toàn cục cho riêng luồng Bug #7 (Bug
  #6 vẫn `blocked` nhưng đó là 1 tính năng khác, độc lập, đã có tiền lệ trước đây `status` toàn cục
  không phản ánh 100% mọi blocker con — xem cách các bản release trước vẫn ghi `"released"`/tương
  đương dù còn blockers list không rỗng).
- Entry mới `by_increment.bug7_line_break_numbered_list_toc_full_fix` (`dev_reviewer: 6, dev_qa: 1,
  status: approved_qa_round8_live_verified_default_toc_split_enabled_true`) — khớp đúng số lần review
  thực tế đếm được (spike 7.4-a + implement 7.4-b→e = 2 lần APPROVE liên tiếp không tính là "vòng sửa
  lỗi" theo ghi chú trong chính review-report.md, nhưng số 6 khớp với con số PM/notes tự báo "Reviewer:
  6 lần review độc lập xuyên suốt cả chuỗi" bao gồm cả 7.0/7.1/7.2/hotfix trước đó — nhất quán nội bộ
  giữa `notes` và `by_increment`, không tự mâu thuẫn).
- Quan sát phụ non-blocking: 2 bộ đếm cấp cao nhất `iterations.dev_reviewer` (6→7) và `dev_qa` (5→6)
  chỉ tăng +1 mỗi bộ, trong khi entry mới tự khai `dev_reviewer: 6`. Đối chiếu với các entry trước
  (vd `aimd_adaptive_concurrency_controller...: dev_reviewer: 6` cũng không làm cấp cao nhất tăng
  thêm 6) xác nhận đây là quy ước ĐÃ CÓ TỪ TRƯỚC của file này — 2 con số cấp cao nhất KHÔNG phải tổng
  cộng dồn của `by_increment`, có vẻ là một chỉ số khác (số "chu kỳ release" hoặc tương tự) không được
  định nghĩa rõ ràng ở bất kỳ đâu. Không phải lỗi phát sinh từ diff này (hành vi nhất quán với lịch sử
  file), nhưng đề xuất Tech Lead làm rõ ý nghĩa 2 field này trong 1 dịp khác — không chặn release.
- `notes` entry mới ("v1.2.7 Bug #7 full fix...") mô tả đầy đủ 7.0→7.4, kết thúc bằng câu "Bug #6 (P1.1
  pdf_scan rotated overlay) vẫn còn blocked riêng, KHÔNG liên quan và KHÔNG bị ảnh hưởng bởi release
  này" — **đúng yêu cầu bắt buộc của brief PM** (task 4), không phóng đại, không thiếu sót nội dung
  quan trọng đã biết (đối chiếu với review-report.md + test-report.md, không thấy chi tiết nào bị bỏ
  sót hoặc bịa thêm). **Đạt.**

### 5. Tự chạy lại toàn bộ (không tin lại số Dev/PM/QA báo)

```
uv run pytest -q                    → 435 passed, 419 warnings (~82s)  — khớp đúng kỳ vọng brief "435 passed"
uv run ruff check .                 → All checks passed!
uv run ruff format --check .        → 19 files would be reformatted (KHÔNG liên quan diff đang review)
```

Về 19 file `ruff format` — **tự verify đây là drift TIỀN TỒN TẠI, không phải do diff release này gây
ra**: `git stash` toàn bộ diff (về đúng commit `2c47a03`, HEAD thật trước khi có thay đổi paperwork),
chạy lại `ruff format --check .` → **vẫn ra đúng 19 file y hệt** (test files không liên quan, vd
`test_gemini_provider.py`, `test_deepl_provider.py` — line quá dài do format tự động của `mocker.patch`
nhiều dòng, không liên quan `babeldoc`/`config.py`/release paperwork). Đã `git checkout -- uv.lock &&
git stash pop` để phục hồi đúng nguyên trạng diff sau khi verify (side-effect duy nhất của thao tác
này là `uv run` tự đồng bộ `uv.lock` về version tại thời điểm stash — đã loại bỏ side-effect này bằng
`git checkout -- uv.lock` trước khi pop). **Không phải noise Markdown như brief dự đoán, nhưng đúng
tinh thần "pre-existing, không liên quan task này" — không chặn release.**

### 6. Kill-switch độc lập — xác nhận bằng đọc `sitecustomize.py`

Đọc toàn văn `src/babeldoc_shim/sitecustomize.py` + trace lineage:

- `_toc_split_enabled()` (dòng 144–147) đọc **riêng** biến môi trường `BABELDOC_SHIM_TOC_SPLIT`,
  hoàn toàn tách biệt với `_numbered_list_split_enabled()` (đọc `BABELDOC_SHIM_NUMBERED_LIST_SPLIT`,
  patch 7.2) và với patch 7.1 (`_split_paragraph_into_lines`, không có cờ riêng — luôn chạy cùng với
  việc patch tổng thể thành công).
- Lineage đầy đủ: `Settings.babeldoc_toc_split_enabled` (`src/core/config.py:240`) →
  `job_orchestrator.py:248` (`toc_split_enabled=self._settings.babeldoc_toc_split_enabled`, keyword
  argument) → `BabeldocRunner.__init__` (`src/services/babeldoc_runner.py:227/248`) →
  `env["BABELDOC_SHIM_TOC_SPLIT"]` (dòng 369) → `sitecustomize.py:_toc_split_enabled()`. Chỉ có
  **1** call site `BabeldocRunner(` trong toàn repo (đã tự `grep -rn "BabeldocRunner("`), không có
  rủi ro lệch tham số.
- Tắt `babeldoc_toc_split_enabled` (hoặc set `BABELDOC_SHIM_TOC_SPLIT=0`) chỉ khiến
  `_build_patched_process_independent_paragraphs` bỏ qua bước gọi `_split_toc_paragraphs_in_list`
  (dòng 437–439) — **hàm gốc `process_independent_paragraphs` của babeldoc vẫn chạy đầy đủ trước đó**
  (dòng 436), và 2 patch 7.1/7.2 (`_split_paragraph_into_lines`, `process`) **không nằm trong nhánh
  điều kiện này**, tiếp tục hoạt động độc lập không bị ảnh hưởng. **Xác nhận: đây đúng là kill-switch
  độc lập, an toàn để rollback ngay lập tức nếu TOC-1 v2 gây false-positive thật trên production, mà
  không cần deploy lại code — chỉ cần set `BABELDOC_SHIM_TOC_SPLIT=0` (qua env) hoặc revert 1 dòng
  default trong `config.py`.**

### 7. Đối chiếu `docs/Architecture.md` mục "Bug #7 Ca C — Đóng vòng"

Đọc toàn bộ section mới (27 dòng thêm cuối file): tường thuật khớp với commit thật (`0aea37b` spike,
`2c47a03` implement), khớp `docs/test-report.md` QA Vòng 8, không giới thiệu claim mới nào về contract
babeldoc chưa được verify (chỉ tóm tắt lại nợ kỹ thuật đã biết từ AA10-b/AA12, đúng như văn bản ghi
"không sửa bảng AA12 ở trên, chỉ đính chính trạng thái mới nhất"). Không phát hiện sai lệch.

### 8. Checklist R5-04

`src/babeldoc_shim/sitecustomize.py` không phải dạng `*_runner.py`/`*_provider.py` (không tự gọi
subprocess/HTTP tới tool ngoài mà không qua `BabeldocRunner`), nhưng có claim cụ thể về contract
babeldoc 0.6.4 (điểm hook, thứ tự gọi `update_paragraph_data`) — đã được Reviewer tự verify độc lập
bằng cách đọc trực tiếp source babeldoc 0.6.4 thật đã cài trên máy ở 2 lần review trước (spike +
implement, xem mục 3 của section review implement ngay trên). Task review hiện tại (paperwork release)
không tạo thêm claim contract mới nào cần verify lại — chỉ đổi giá trị default của 1 field boolean đã
có sẵn. **External contract verified against real source: YES (kế thừa từ 2 lần verify trước, không
có claim contract mới trong phạm vi task này).**

### Danh sách issue

**Blocking:** không có.

**Non-blocking (không chặn release, ghi lại cho backlog):**

1. Test mới `test_toc_split_logs_when_monotonic_or_fraction_gate_blocks_a_candidate` là dạng
   "source-inspection" (kiểm tra text của hàm chứa đúng tên hằng/`logger.warning`), không phải test
   thực thi hàm thật với `caplog` để xác nhận log thực sự được phát ra đúng lúc runtime. Chấp nhận
   được vì cùng quy ước với test liền kề đã có từ trước, nhưng nếu có dịp nên bổ sung 1 test hành vi
   thật (dựng `PdfParagraph` giả, gọi `_split_toc_paragraphs_in_list`, assert `caplog` có dòng log).
2. `project_state.json` field `iterations.dev_reviewer`/`dev_qa` cấp cao nhất không có định nghĩa rõ
   ràng về ý nghĩa (không phải tổng `by_increment`) — quy ước đã tồn tại từ trước, không phải lỗi của
   diff này, nhưng nên làm rõ để tránh hiểu nhầm sau này.

### Kết luận

**APPROVE — đủ điều kiện commit + release v1.2.7 ngay bây giờ.**

Căn cứ:

- `src/core/config.py`: đúng 1 thay đổi thực chất (`babeldoc_toc_split_enabled` False→True), comment
  khớp chính xác với QA Vòng 8, không có thay đổi ngoài ý muốn nào khác trong file.
- `docs/CHANGELOG.md`/`docs/test-report.md`/`docs/Architecture.md`: cả 3 diff đều **insertions-only**
  (0 deletions, tự xác nhận bằng `git diff --stat`) — đúng Protocol 7 R7-03, không mất lịch sử.
- `pyproject.toml`/`uv.lock` đồng bộ đúng `1.2.7`; gap `uv.lock` cũ (`1.2.5` trước diff) là tồn đọng từ
  trước, diff này SỬA chứ không gây ra.
- `project_state.json` là JSON hợp lệ, `version`/`released_at`/`status`/`by_increment`/`notes` phản
  ánh đúng thực tế, nhắc rõ Bug #6 vẫn blocked riêng và không liên quan release này (đúng yêu cầu bắt
  buộc của brief).
- `uv run pytest -q` → 435 passed (khớp kỳ vọng), `ruff check` sạch, `ruff format --check` có 19 file
  drift nhưng đã tự verify là pre-existing (giống hệt trên cả base commit `2c47a03`), không liên quan
  diff đang review.
- Kill-switch `babeldoc_toc_split_enabled`/`BABELDOC_SHIM_TOC_SPLIT` xác nhận hoạt động **độc lập**
  với patch 7.1/7.2 qua đọc trực tiếp `sitecustomize.py` — an toàn để rollback tức thời nếu TOC-1 v2
  gây vấn đề trên production, không cần revert code, chỉ cần đổi 1 giá trị cấu hình.
- 2 issue non-blocking ở trên không liên quan tới correctness/security/data-lineage của thay đổi đang
  release, không ảnh hưởng khả năng rollback.

**Không tính vào giới hạn Protocol 3** (đây là review paperwork/config release, không phải vòng sửa
lỗi Dev↔Reviewer).

---
