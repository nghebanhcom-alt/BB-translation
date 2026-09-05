# CHANGELOG — BB-Translation

## Increment 1 — Project Scaffolding

Dev: dựng khung sườn project (structure, dependency management, data models, config,
DB bootstrap, FastAPI skeleton, Docker setup). Không có business logic dịch/OCR/glossary
matching trong increment này.

### File đã tạo

**Project structure** (theo Architecture.md section 8):
- `src/api/`, `src/api/routes/` — FastAPI web server
- `src/core/` — config, database bootstrap
- `src/pipelines/`, `src/services/`, `src/postprocess/` — thư mục rỗng (chỉ `__init__.py`),
  chờ increment sau
- `src/models/` — SQLModel data models
- `src/utils/` — thư mục rỗng, chờ increment sau
- `web/`, `web/css/`, `web/js/` — thư mục rỗng, chờ increment frontend
- `docker/`, `tests/`, `tests/integration/`

**Dependency management**
- `pyproject.toml` — Python 3.12+, `uv`, dependencies theo Tech Stack (Architecture.md
  section 1): fastapi, sqlmodel, aiosqlite, pymupdf, openpyxl, anthropic, openai,
  google-generativeai, deepl, python-multipart, uvicorn, websockets, pydantic-settings.
  Dev: pytest, pytest-asyncio, ruff.
- `uv.lock` — lockfile, đã resolve thành công (72 packages)

**Data Models** (`src/models/`, theo Architecture.md section 4.2)
- `batch.py` — `Batch`
- `job.py` — `Job` (bao gồm cột `job_type` cho parse_only mode, section 6.8)
- `chunk.py` — `Chunk`
- `overflow.py` — `OverflowReport`
- `glossary.py` — `Glossary`, `GlossaryEntry`
- `cache.py` — `TranslationCache`
- `settings.py` — `Setting`
- `__init__.py` — export tất cả model

**Config & Database**
- `src/core/config.py` — `Settings` (pydantic-settings), đọc `.env`: CLAUDE_API_KEY,
  OPENAI_API_KEY, DEEPL_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY, OLLAMA_ENDPOINT,
  DATABASE_URL, MAX_CONCURRENT_FILES, MAX_UPLOAD_SIZE_MB, NOTO_FONT_PATH
- `src/core/database.py` — async engine (aiosqlite), session factory, `init_db()` tạo
  tables từ SQLModel metadata + enable WAL mode + tạo index `COLLATE NOCASE` cho
  `glossary_entries.term_en` (BR-GLOSS-02)

**FastAPI skeleton**
- `src/api/main.py` — app init, lifespan gọi `init_db()`, CORS (localhost dev),
  `GET /health` → `{"status": "ok"}`, mount router rỗng `/api/jobs`, `/api/glossary`
- `src/api/routes/jobs.py`, `src/api/routes/glossary.py` — router rỗng, handler để
  increment sau

**Docker**
- `docker/Dockerfile` — Python 3.12-slim, cài `uv`, `calibre`, `uv sync --frozen --no-dev`
- `docker-compose.yml` (root) — service `app` + service `mineru` (profile `ocr`), env vars
  đúng theo Architecture.md section 7.3
- `.env.example` — template đầy đủ biến môi trường, không điền giá trị thật

**Root files**
- `.gitignore` — `.env`, `__pycache__`, `.venv`, `data/`, `*.db`, `.pytest_cache`, ...
- `README.md` — mô tả ngắn, hướng dẫn `docker compose up`, link tới PRD/Architecture

### Quyết định kỹ thuật đáng chú ý / deviation

1. **`src/core/database.py` thay vì `src/models/database.py`**: Task spec của increment 1
   (mục 5) yêu cầu rõ đặt DB bootstrap tại `src/core/database.py`, khác với vị trí liệt kê
   trong Architecture.md section 8 (`src/models/database.py`). Ưu tiên theo task spec vì
   cụ thể hơn cho increment này — cần Tech Lead xác nhận lại vị trí chuẩn ở increment sau
   nếu muốn đổi.
2. **Thêm dependency `greenlet`**: SQLAlchemy async (dùng bởi SQLModel + aiosqlite) cần
   `greenlet` để chạy `engine.begin()` — không có trong danh sách Tech Stack gốc nhưng là
   dependency bắt buộc để async engine hoạt động, không phải lựa chọn kiến trúc.
3. **Build backend `hatchling`, `packages = ["src"]`**: Chưa được đặc tả trong
   Architecture.md, chọn hatchling vì đơn giản, chuẩn với `uv`. Package name `src` giữ
   nguyên để khớp cách import `from src.models import ...` như spec yêu cầu.
4. **`.env.example` dùng `DATABASE_URL=sqlite+aiosqlite:///data/bb_translation.db`**
   (relative, cho dev local); `docker-compose.yml` override thành đường dẫn tuyệt đối
   `sqlite+aiosqlite:////data/bb_translation.db` khớp volume mount `/data` trong container.
5. Chưa implement bất kỳ handler nghiệp vụ nào (upload, translate, glossary CRUD, OCR,
   chunking, provider dịch...) — đúng phạm vi increment 1, để lại cho các increment sau.

### Kết quả verify
- `uv sync`: thành công, resolve 72 packages, tạo `uv.lock`
- `python -c "from src.models import *"`: import thành công, không lỗi cú pháp
- Khởi động FastAPI qua `TestClient` (lifespan chạy `init_db()`): `GET /health` → `200
  {"status": "ok"}`; DB tạo đủ 8 bảng (`batches`, `jobs`, `chunks`, `overflow_reports`,
  `glossaries`, `glossary_entries`, `translation_cache`, `settings`); WAL mode xác nhận
  qua file `.db-wal`/`.db-shm`
- `ruff check src/`: All checks passed

## Increment 1 — Fix Round 1

Dev: xử lý blocking issue + các non-blocking suggestion từ `docs/review-report.md` (iteration 1).

### Blocking issue đã sửa

1. **`database.py` chuyển về đúng vị trí spec**: di chuyển `src/core/database.py` →
   `src/models/database.py` (khớp Architecture.md section 8, dòng 1304–1306). Cập nhật:
   - `src/api/main.py` dòng 8: `from src.core.database import init_db` →
     `from src.models.database import init_db`
   - `src/models/settings.py` dòng 14: comment tham chiếu trỏ lại
     `src/models/database.py`
   - Xoá `src/core/__pycache__/database.cpython-314.pyc`
   - Grep toàn repo xác nhận không còn reference code nào tới `src.core.database`
     (chỉ còn nhắc tới trong lịch sử CHANGELOG/review-report/project_state, giữ nguyên
     làm record)
   - `src/core/` giữ nguyên (còn `config.py`), không xoá thư mục

### Non-blocking suggestions đã xử lý

1. **`docker-compose.yml` chuyển vào `docker/`**: `docker-compose.yml` (root) →
   `docker/docker-compose.yml`. Sửa `build.context: .` → `..`, giữ
   `dockerfile: docker/Dockerfile` (relative theo context mới = repo root); volumes
   `./data:/data`, `./fonts:/app/fonts` → `../data:/data`, `../fonts:/app/fonts`
   (relative theo vị trí file compose mới). Cập nhật `README.md` hướng dẫn chạy thành
   `docker compose -f docker/docker-compose.yml up -d`. Không có Docker trên máy dev để
   chạy `docker compose config` xác nhận, đã tự kiểm tra lại path tương đối thủ công.
2. **File thừa ở root**: `glossarystarter.xlsx` (root) là bản trùng byte-for-byte với
   `data/glossary-starter.xlsx` (đã xác nhận bằng `cmp`) — xoá bản thừa ở root, giữ bản
   trong `data/`. `repo-dịch.rtf` giữ nguyên (tài liệu research của user).
3. **Smoke test**: thêm `tests/test_health.py` — dùng `TestClient` để test `GET /health`
   trả `200 {"status": "ok"}`.

### Không xử lý (để increment sau, theo chỉ đạo)
- Tên file trong `src/api/routes/` (`jobs.py` vs `upload.py`/`translate.py`/...)
- `src/api/deps.py`, `src/api/websocket.py` chưa tạo

### Kết quả verify (fix round 1)
- `ruff check src/`: All checks passed
- `python -c "from src.models import *"`: import thành công
- `pytest tests/`: **1 passed** (`tests/test_health.py::test_health`)

## Increment 2 — Parsing & Glossary

Dev: implement File Router, service wrapper cho pdf2zh/MinerU (mock-tested, chưa cài
Docker/MinerU/pdf2zh thật trên máy dev), và toàn bộ Glossary Management (Excel I/O,
GlossaryManager, API CRUD + import/export).

### File đã tạo

**File Router** (BR-INPUT-01, BR-INPUT-02)
- `src/core/file_router.py` — `FileType` enum (`PDF_DIGITAL`, `PDF_SCAN`, `EPUB`),
  `detect_file_type()`: detect qua extension trước, với `.pdf` dùng PyMuPDF đếm % trang
  có text (`ratio > 0.9` → digital, ngược lại → scan, đúng biên "> 90%" theo BR-INPUT-02).
  `.epub` → EPUB thẳng. Extension khác → `UnsupportedFileTypeError`.
- `tests/test_file_router.py` — 5 test, tự tạo PDF bằng PyMuPDF trong lúc test (không cần
  file mẫu ngoài): toàn text (digital), toàn ảnh trắng không text (scan), biên đúng 90%
  (9/10 trang có text → vẫn scan vì không `>` 90%), epub, extension không hỗ trợ.

**Service wrappers** (`src/services/`)
- `pdf2zh_runner.py` — `Pdf2zhRunner.translate_pages()` gọi `pdf2zh` CLI qua
  `asyncio.create_subprocess_exec`, trả `Pdf2zhResult` (success/output_path/stderr/
  duration_seconds); return code != 0 → raise `Pdf2zhError` kèm stderr.
- `mineru_runner.py` — `MinerURunner.parse_document()` POST file qua `httpx.AsyncClient`
  tới endpoint OCR của container MinerU (theo Architecture.md section 7.1, MinerU chạy
  như HTTP sidecar chứ không phải CLI local), trả `MinerUResult` (markdown_path,
  images_dir, confidence_score, success); lỗi HTTP status hoặc connection error → raise
  `MinerUError` rõ ràng.
- `tests/test_pdf2zh_runner.py`, `tests/test_mineru_runner.py` — mock
  `asyncio.create_subprocess_exec` / `httpx.AsyncClient` bằng `pytest-mock`, test cả
  success và failure (non-zero exit code, HTTP 500, connection error). Không cần
  pdf2zh/MinerU thật cài trên máy.

**Glossary Excel I/O** (`src/utils/excel_utils.py`, BR-GLOSS-05)
- `GlossaryEntryData` dataclass, `import_glossary_from_excel()` (openpyxl, cột A=EN,
  B=VI, C=notes optional, skip header + dòng rỗng, trim whitespace, raise
  `GlossaryExcelError` nếu thiếu cột bắt buộc hoặc file rỗng), `export_glossary_to_excel()`
  (header bold, format khớp import để roundtrip được).
- `tests/test_excel_utils.py` — 4 test: roundtrip export→import khớp dữ liệu, skip dòng
  rỗng + trim whitespace, thiếu cột bắt buộc raise lỗi, workbook rỗng raise lỗi.

**Glossary Manager** (`src/core/glossary_manager.py`, BR-GLOSS-01 → BR-GLOSS-06)
- `GlossaryManager` nhận `AsyncSession`, `get_entry()` case-insensitive (BR-GLOSS-02),
  project glossary override global khi có `project_id` (BR-GLOSS-06), `bulk_import()`
  ghi đè entry trùng term = last-updated-wins tự nhiên vì luôn là write gần nhất
  (BR-GLOSS-03), trả `ImportResult` (imported/updated/skipped), `build_prompt_snippet()`
  build Markdown table đúng format Architecture.md section 6.2, target rỗng/"(keep)" →
  note rõ "GIU NGUYEN tieng Anh".
- `tests/test_glossary_manager.py` — 8 test dùng `sqlite+aiosqlite:///:memory:`, không
  đụng DB thật: bulk import mới/update, case-insensitive match, project override global
  (và fallback global khi project khác không có entry), not-found, format prompt snippet,
  snippet rỗng khi glossary trống.

**API Endpoints** (`src/api/routes/glossary.py`, US-03)
- `POST /api/glossary/import` — parse Excel, trả preview KHÔNG lưu DB (AC-03.1).
- `POST /api/glossary/import/confirm` — nhận lại danh sách entries đã confirm từ client,
  lưu qua `GlossaryManager.bulk_import`.
- `GET /api/glossary` — list + pagination (`limit`, `offset`).
- `PUT /api/glossary/{entry_id}` — sửa entry (AC-03.3).
- `DELETE /api/glossary/{entry_id}` — xoá entry.
- `GET /api/glossary/export` — xuất Excel qua `FileResponse` (AC-03.4).
- Dùng Pydantic models riêng (`GlossaryEntryOut/In/Update`, request/response models) —
  không expose `GlossaryEntry` (SQLModel) trực tiếp qua API.
- `src/api/deps.py` (mới) — `SessionDep`, dependency injection cho DB session, cần cho
  cả API route lẫn test override.
- `tests/integration/test_glossary_api.py` — 4 test dùng `TestClient` +
  `app.dependency_overrides[get_db_session]` trỏ vào SQLite in-memory (`StaticPool` để
  giữ 1 connection dùng chung xuyên suốt lifecycle test): full flow import → confirm →
  list → edit → export → delete, reject file không phải Excel, edit/delete entry không
  tồn tại → 404.

### Quyết định kỹ thuật đáng chú ý / deviation

1. **`src/models/database.py`: đổi session factory sang `sqlmodel.ext.asyncio.session.AsyncSession`**
   thay vì `sqlalchemy.ext.asyncio.AsyncSession` mặc định từ Increment 1. Lý do: toàn bộ
   code nghiệp vụ (GlossaryManager, API routes) dùng `session.exec(select(...))` — API
   idiomatic của SQLModel — chỉ tồn tại trên subclass `sqlmodel.ext.asyncio.session.AsyncSession`,
   không có trên `AsyncSession` gốc của SQLAlchemy (chỉ có `.execute()` trả `Row` thô).
   Đây là subclass tương thích ngược 100% (chỉ thêm method `.exec()`), không đổi hành vi
   `init_db()`/WAL mode/index đã có, không cần Tech Lead duyệt lại vì Architecture.md
   section 1 đã chọn SQLModel làm ORM — đây là cách dùng đúng chuẩn của nó.
2. **Endpoint API khác path so với Architecture.md section 5.1**: PRD task Increment 2 chỉ
   định rõ path `/api/glossary/*` (số ít, không có `{glossary_id}` — vì hệ thống chỉ có
   scope `global`/`project:{id}`, không có khái niệm "nhiều glossary đặt tên tuỳ ý" như
   Architecture.md draft `/api/glossaries/{id}/entries`). Ưu tiên theo task spec (cụ thể
   hơn, đã duyệt cho increment này); flow import/confirm cũng đơn giản hoá: KHÔNG có
   staging `import_id` ở server — client giữ danh sách entries đã parse từ response
   `/import` và gửi thẳng lại `/import/confirm`, tránh phải thêm bảng staging tạm thời
   vào schema hiện có. Cần Tech Lead xác nhận lại nếu muốn khớp 100% với
   `/api/glossaries/{id}/import/{iid}/confirm` ở increment sau (ví dụ khi có UI thật cần
   giữ preview qua nhiều request).
3. **`MinerURunner` dùng `httpx.AsyncClient`, KHÔNG dùng `asyncio.create_subprocess_exec`**:
   đúng theo Architecture.md section 7.1 — MinerU chạy như container HTTP sidecar riêng
   (`docker-compose.yml` service `mineru`, port 8010), gọi qua network chứ không phải
   subprocess CLI local như pdf2zh.
4. **Thêm dependency `httpx` (main) và `pytest-mock` (dev)** vào `pyproject.toml`: `httpx`
   cần cho `MinerURunner` (không có trong danh sách Tech Stack gốc nhưng bắt buộc để gọi
   HTTP tới MinerU container theo thiết kế). `pytest-mock` dùng để mock subprocess/httpx
   trong test theo đúng chỉ đạo task. `uv sync` đã resolve thành công, không xung đột.
5. **Chưa implement**: `job_orchestrator.py`, `chunking.py`, `prompt_builder.py`,
   `cost_estimator.py`, provider dịch (Claude/OpenAI/DeepL/Ollama), post-processing
   (font shrink, bilingual merge), EPUB pipeline, upload/translate/history/settings API —
   để lại cho các increment sau, đúng phạm vi task này (File Router + Parsing wrapper +
   Glossary Management).
6. Máy dev chưa cài Docker/MinerU/pdf2zh thật — `pdf2zh_runner.py` và `mineru_runner.py`
   viết đúng interface/subprocess-HTTP call logic theo Architecture.md nhưng chỉ verify
   được bằng mock; cần integration test thật với container MinerU + `pdf2zh` CLI khi có
   Docker ở increment triển khai pipeline.

### Kết quả verify
- `ruff check src/`: All checks passed
- `pytest tests/ -v`: **27 passed** (5 file_router + 2 pdf2zh_runner + 3 mineru_runner +
  4 excel_utils + 8 glossary_manager + 4 integration API + 1 test_health cũ từ Increment 1)
- `python -c "from src.api.main import app"`: import chain thành công, không lỗi

## Increment 3 — Translation Engine

Dev: implement Translation Engine đa provider (Claude, OpenAI, DeepSeek, Gemini, DeepL,
Ollama), Prompt Builder (glossary + unit conversion + style rules), Cost Estimator, và xử
lý 2 gap non-blocking từ review Increment 2.

### File đã tạo

**Provider abstraction** (`src/services/translation.py`)
- `TranslationProvider` Protocol, `TranslationResult` dataclass (`text`, `input_tokens`,
  `output_tokens`, `estimated_cost_usd`, `provider_name`)
- Exceptions: `TranslationProviderError` (base), `RateLimitError` (transient, retry theo
  BR-BATCH-02), `AuthenticationError` (permanent, fail ngay theo BR-BATCH-02)

**6 concrete providers** (`src/services/`)
- `claude_provider.py` — `ClaudeProvider`, `anthropic.AsyncAnthropic`, model default
  `claude-sonnet-4-5-20250514`, prompt caching bật mặc định (`cache_control: ephemeral`
  trên system block chứa glossary) đúng Architecture.md 6.6. Giá: $2/$10 per MTok.
- `openai_provider.py` — `OpenAIProvider`, `openai.AsyncOpenAI`, chat completions. Giá
  **giả định** $2.5/$10 per MTok (gpt-4o) — Architecture.md không nêu rõ giá OpenAI, ghi
  chú "reference only" trong docstring.
- `deepseek_provider.py` — `DeepSeekProvider(OpenAIProvider)`, chỉ override `base_url` +
  pricing đúng code mẫu Architecture.md 6.6. Giá $0.27/$1.1 per MTok (đã nêu sẵn trong
  Architecture.md, "gia tham khao, co the doi").
- `gemini_provider.py` — `GeminiProvider`, `google-generativeai` SDK, đúng pattern mẫu
  Architecture.md 6.6 (`generate_content_async`, `system_instruction`). Giá **giả định**
  $1.25/$10 per MTok (Gemini 2.5 Pro) — không có trong Architecture.md, ghi chú rõ. SDK
  `google-generativeai` phát ra `FutureWarning` deprecated (khuyến nghị chuyển
  `google-genai`) — chưa migrate trong increment này vì Architecture.md 1 chỉ định rõ
  `google-generativeai`, để Tech Lead quyết định ở increment sau nếu cần.
- `deepl_provider.py` — `DeepLProvider`, `deepl` SDK (sync, wrap qua `asyncio.to_thread`).
  **Chưa hoàn thiện đầy đủ** phần glossary injection: theo Architecture.md 6.6, DeepL
  "khong co system prompt -> glossary inject qua DeepL Glossary API native". Provider này
  chỉ nhận `glossary_id` (resource DeepL đã tạo sẵn) qua constructor và truyền vào
  `translate_text(..., glossary=glossary_id)` — **KHÔNG** tự động tạo/đồng bộ DeepL
  glossary resource từ `glossary_entries` local (cần gọi `translator.create_glossary(...)`
  và giữ đồng bộ khi glossary sửa trên web). Để TODO rõ ràng cho increment Job
  Orchestrator, nơi glossary state của từng job được lắp ráp lần đầu. `estimate_cost` ở
  đây cũng chỉ là xấp xỉ vì DeepL tính phí theo ký tự (character) chứ không theo token —
  quy đổi heuristic ~4 ký tự/token, giá tham khảo $25/1M ký tự.
- `ollama_provider.py` — `OllamaProvider`, REST API qua `httpx.AsyncClient` tới
  `{OLLAMA_ENDPOINT}/api/generate`. Local, free → `estimate_cost()` luôn trả `0.0`.

**Provider Factory** (`src/services/provider_factory.py`)
- `ProviderFactory.create(provider_name, settings)` — map string → class, đọc config từ
  `Settings`. Raise `UnknownProviderError` nếu tên provider không tồn tại,
  `ProviderConfigError` nếu thiếu API key bắt buộc (Ollama không cần API key). Case-
  insensitive tên provider.

**Prompt Builder** (`src/core/prompt_builder.py`, `src/utils/unit_conversion_table.py`)
- `build_system_prompt(glossary_manager, project_id=None)` — ghép: glossary snippet (dùng
  lại `GlossaryManager.build_prompt_snippet()` từ Increment 2) + bảng chuyển đổi đơn vị
  (BR-UNIT-01/02/03, hard-code trong `unit_conversion_table.py` theo đúng bảng
  Architecture.md 6.2) + quy tắc dịch súc tích ≤130% (BR-FONT-03) + quy tắc giữ
  typography/structure (BR-TYPO-01 đến 04, PRD 4.6).

**Cost Estimator** (`src/core/cost_estimator.py`)
- `estimate_job_cost(total_pages, provider) -> CostEstimate` — heuristic 500 input
  tokens/trang (giả định, ghi rõ trong docstring vì Architecture.md không cho số cụ thể),
  output ước lượng = input × 1.3 (theo target BR-FONT-03), nhân giá qua
  `provider.estimate_cost()`. Dataclass `CostEstimate`: `estimated_input_tokens`,
  `estimated_output_tokens`, `estimated_cost_usd`, `provider_name`.

**Config** (`src/core/config.py`)
- Thêm các field còn thiếu cho từng provider: `claude_model/max_tokens/temperature/
  use_prompt_caching`, `openai_model/max_tokens/temperature`, `deepseek_base_url/model/
  max_tokens/temperature`, `gemini_model/max_tokens/temperature`, `deepl_formality`,
  `ollama_model/max_tokens/temperature` — đọc từ `.env`, default khớp Architecture.md
  section 6.6 config model mẫu.

### 2 gap fix từ review Increment 2

1. **`GET /api/glossary` thiếu field `scope`**: `src/api/routes/glossary.py` —
   `GlossaryEntryOut` thêm field `scope: str`. `list_entries` join `GlossaryEntry` với
   `Glossary` để lấy `scope`, hỗ trợ thêm filter `?scope=` (chưa có trong API cũ, tiện
   dùng cho increment sau). `update_entry` cũng trả `scope` (query lại `Glossary` theo
   `entry.glossary_id`). Test: `tests/integration/test_glossary_api.py` thêm assertion
   `scope == "global"` cho response list.
2. **`pdf2zh_runner.py` thiếu `mkdir` phòng thủ**: thêm
   `output_path.parent.mkdir(parents=True, exist_ok=True)` trước khi spawn subprocess,
   copy đúng pattern đã có ở `mineru_runner.py`. Test:
   `test_translate_pages_creates_output_parent_dir` trong `tests/test_pdf2zh_runner.py`.

### Quyết định kỹ thuật đáng chú ý / deviation

1. **`TranslationProvider.translate()` trả `TranslationResult` thay vì `str`**:
   Architecture.md section 6.6 code mẫu ghi `async def translate(...) -> str`, nhưng task
   spec increment này lại yêu cầu định nghĩa `TranslationResult` (`text`, `input_tokens`,
   `output_tokens`, `estimated_cost_usd`, `provider_name`) — hai chỗ mâu thuẫn nhau. Chọn
   trả `TranslationResult` vì Job Orchestrator (increment sau) cần token count/cost thực
   tế cho `jobs.actual_cost` (DB schema Architecture.md 4.2) và PRD R-01 ("hiển thị
   estimated cost trước dịch" ngụ ý cũng cần actual cost sau khi dịch để so sánh). Đây là
   thay đổi nhỏ ở interface, không đổi kiến trúc tổng thể (vẫn đúng
   `TranslationProvider` Protocol, vẫn đúng danh sách provider) — nhưng cần Tech Lead xác
   nhận lại nếu muốn khớp 100% chữ ký hàm trong Architecture.md.
2. **Giá cả cho OpenAI, Gemini, DeepL là giả định** (không có trong Architecture.md) — ghi
   rõ trong docstring từng provider + phần trên, cần cập nhật khi có giá chính thức hoặc
   khi đổi model.
3. **`GeminiProvider` dùng `genai.configure()` global** — hạn chế của SDK
   `google-generativeai`: API key được set ở scope process, không phải per-instance. Chấp
   nhận được với deployment 1-user hiện tại (Architecture.md 9.1), nhưng sẽ là vấn đề nếu
   sau này cần chạy song song nhiều provider Gemini với API key khác nhau — flag cho Tech
   Lead nếu multi-tenant sau này.
4. **DeepL glossary sync chưa hoàn thiện** — xem chi tiết ở mục provider phía trên, để
   TODO rõ ràng cho increment Job Orchestrator.
5. **Chưa implement**: Job Orchestrator, chunking thật, batch processing, API endpoint
   chọn provider/estimate cost qua HTTP — đúng phạm vi "KHÔNG làm trong increment này" của
   task spec, để lại cho increment sau.

### Kết quả verify
- `ruff check src/`: All checks passed
- `pytest tests/ -v`: **57 passed** (27 test cũ từ Increment 1+2 + 30 test mới: 21
  translation_providers + 9 provider_factory + 2 prompt_builder + 4 cost_estimator + 1
  pdf2zh mkdir + 1 glossary scope field — tổng khớp 30 vì một số file gộp nhiều test class)
- `python -c "from src.api.main import app"`: import chain thành công, không lỗi
- Không cần Docker/API key thật — toàn bộ provider test dùng `pytest-mock`, không gọi API
  thật (`anthropic.AsyncAnthropic`, `openai.AsyncOpenAI`, `genai.GenerativeModel`,
  `deepl.Translator`, `httpx.AsyncClient` đều được mock)

## Increment 4 — Job Orchestrator & Post-processing

Dev: lắp ráp toàn bộ building block từ Increment 1-3 thành pipeline chạy được 1 job
end-to-end (chunking → translate → render → post-process → merge → bilingual output),
cộng batch orchestration với concurrency/failure isolation/shortest-job-first, retry
logic, và progress tracking. Không chạy pdf2zh/MinerU thật (chưa có Docker) — toàn bộ
dependency ngoài được inject và test bằng mock, nhưng phần PDF I/O thật (PyMuPDF) chạy
thật trong mọi test, không mock `fitz`.

### File đã tạo

**Chunking Engine** (`src/core/chunking.py`, BR-CHUNK-01..05)
- `ChunkPlan` dataclass (`index`, `page_start`, `page_end`, `overlap_start`, `overlap_end`).
  Đặt tên `ChunkPlan` thay vì `Chunk` như brief gợi ý vì `Chunk` đã là tên bảng SQLModel
  trong `src/models/chunk.py` — dùng lại tên sẽ shadow model đó ở bất kỳ module nào import
  cả hai (Job Orchestrator có làm vậy).
- `calculate_chunks(total_pages, chunk_size=40, overlap=2)` — công thức suy ra từ VÍ DỤ
  minh hoạ trong Architecture.md 6.1 (120 trang → chunk `[1-40], [39-80], [79-120]`, overlap
  39-40/79-80 là context "Chi dich tu page {actual_start}"), KHÔNG theo đúng literal công
  thức `overlap_start = max(1, start - overlap)` trong code mẫu — công thức đó cho ra
  `overlap_start=37` ở chunk 1, không khớp chính ví dụ nằm ngay bên dưới nó trong cùng tài
  liệu. Đã ghi rõ deviation này trong docstring module.
- `plan_chunks(total_pages, file_size_bytes, chunk_size=40, overlap=2)` — áp dụng
  BR-CHUNK-01: ≤50 trang VÀ ≤20MB → 1 chunk duy nhất (toàn bộ file); ngược lại gọi
  `calculate_chunks()`.
- `tests/test_chunking.py` — 5 test: 30 trang không chunk, 120 trang chunk đúng overlap,
  45 trang/25MB vẫn chunk (size threshold), full-coverage không gap, 1 trang.

**Post-processing** (`src/postprocess/`)
- `font_shrink.py` — `evaluate_span()` (per-span, public để test được) +
  `font_shrink_page(page, overflow_entries) -> list[OverflowEntry]` đúng 3 bước BR-FONT-02:
  giảm font tối đa 20% → condensed scale 85% (dùng `insert_text(..., morph=(point,
  Matrix(scale, 1)))` để scale ngang thật qua PyMuPDF, không phải giả lập) → flag
  `OverflowEntry` nếu vẫn tràn (KHÔNG cắt text). Dùng `page.add_redact_annot()` +
  `insert_text()` để "vẽ lại" span ở size/scale mới — cách duy nhất PyMuPDF hỗ trợ sửa
  một span đã render. Giới hạn đã ghi rõ trong docstring: dùng font "helv" (base-14) khi
  vẽ lại thay vì đúng font gốc embedded (Noto) — không ảnh hưởng control-flow shrink/
  condense/flag nhưng cần thay bằng font Noto thật ở increment render production.
  `OverflowEntry` là dataclass riêng (không phải `OverflowReport` SQLModel) vì hàm này chạy
  per-page, chưa có `job_id` — Job Orchestrator map sang `OverflowReport` khi lưu DB.
  Module docstring giải thích rõ lý do `evaluate_span` được export: bbox từ
  `page.get_text("dict")` trên 1 trang MỚI render bởi chính PyMuPDF luôn tự khớp với chữ nó
  chứa (self-referential) — không thể tự "tràn" được trong 1 PDF test tạo từ đầu; overflow
  thật chỉ xảy ra khi bbox đến từ layout gốc (EN) trong khi text vẽ vào là bản dịch (VI)
  dài hơn. Vì vậy test gọi thẳng `evaluate_span()` với bbox nhỏ tự tạo, trên `fitz.Page`
  thật — vẫn chạy thật redact/insert qua PyMuPDF, không mock `fitz`.
- `bilingual_merge.py` — `create_bilingual_pdf(vi_pdf_path, en_pdf_path, output_path)` đúng
  code mẫu Architecture.md 6.4, interleave VI/EN.
- `chunk_merge.py` — `merge_chunk_pdfs(chunks: Sequence[Chunk], output_path)`. **Deviation
  có ghi rõ trong docstring**: brief gợi ý signature `(chunk_paths: list[Path],
  output_path)`, nhưng không thể đảm bảo "không trùng lặp overlap pages" (BR-CHUNK-04) chỉ
  từ list path trần — cần biết mỗi chunk có bao nhiêu trang overlap ở ĐẦU (từ
  `chunk.overlap_start`/`overlap_end`) để bỏ qua khi merge. Nhận `Chunk` (SQLModel, đã có
  sẵn `output_path` field) thay vì `Path` trần.
- `tests/test_font_shrink.py` (5 test), `tests/test_bilingual_merge.py` (2 test),
  `tests/test_chunk_merge.py` (3 test) — toàn bộ dùng `fitz.open()` tạo PDF thật, verify
  qua `fitz.open()` đọc lại kết quả, không mock PyMuPDF.

**Job Orchestrator** (`src/core/job_orchestrator.py`)
- `JobOrchestrator.run_job(job_id, db_session) -> JobResult`: đọc `Job` từ DB → reject
  EPUB (`EpubNotSupportedError`, ngoài phạm vi increment này — bilingual_book_maker chưa
  implement) → đếm `total_pages` nếu chưa có (PyMuPDF) → nếu `pdf_scan` và có
  `mineru_runner` thì chạy OCR lấy `ocr_confidence` → `plan_chunks()` → load hoặc tạo
  `Chunk` rows → build system prompt (`PromptBuilder` + `GlossaryManager`, dùng
  `job.batch_id` làm `project_id` cho glossary scope) → với mỗi chunk CHƯA `completed`
  (BR-CHUNK-05 resumable): gọi `provider.translate()` (qua `with_retry`) rồi
  `pdf2zh_runner.translate_pages()` (qua `with_retry`) → `font_shrink_page()` trên từng
  trang output chunk → lưu `OverflowReport` → cập nhật `Chunk` (status/tokens/cost) →
  `ProgressTracker.update()` sau mỗi chunk → sau khi hết chunk: `merge_chunk_pdfs()` →
  nếu `Batch.output_mode == "bilingual"` thì `create_bilingual_pdf()` → cập nhật `Job`
  (status=completed, actual_cost=tổng `chunk.api_cost`).
- Chunk lỗi (bất kỳ exception nào, kể cả sau khi `with_retry` đã hết lượt) → `Chunk.status
  = failed`, `Job.status = failed`, dừng job ngay (không tiếp tục các chunk sau) — trả kết
  quả để `BatchOrchestrator` cô lập lỗi ở cấp job.
- **Resumable thật (không chỉ lý thuyết)**: `_load_or_create_chunks()` query `Chunk` rows
  có sẵn theo `job_id` trước, chỉ tạo mới nếu chưa có — gọi lại `run_job()` sau khi 1 chunk
  fail sẽ skip mọi chunk `status == completed`, chỉ chạy lại chunk fail + chunk chưa chạy.
  Verify bằng integration test thật (không giả định): fail ở chunk 1/3, gọi lại `run_job`,
  assert provider chỉ được gọi thêm đúng 2 lần (chunk 1 retry + chunk 2), không gọi lại
  chunk 0.
- **Deviation quan trọng, cần Tech Lead/PM xác nhận**: Job Orchestrator gọi
  `provider.translate()` (ProviderFactory) VÀ `pdf2zh_runner.translate_pages()` cho MỖI
  chunk, đúng theo yêu cầu literal của task brief ("build prompt → goi provider dich → goi
  pdf2zh_runner"). Nhưng theo Architecture.md 3.1 bước [3b], pdf2zh TỰ gọi LLM API bên
  trong qua flag `-s {service} --prompt {...}` — nó không trả token/cost ra ngoài. Gọi
  `provider.translate()` riêng là cách DUY NHẤT hiện có để lấy `chunk.api_tokens_used`/
  `api_cost` (Architecture.md 4.2), nhưng nếu chạy thật với cả 2 lệnh gọi API thì sẽ tính
  phí THẬT hai lần cho cùng 1 đoạn text (1 lần từ `provider.translate()`, 1 lần ẩn bên
  trong `pdf2zh`). Đã ghi rõ trong docstring `JobOrchestrator`, cần quyết định ở increment
  sau: hoặc để pdf2zh tự báo cáo token usage, hoặc bỏ hẳn lệnh gọi `pdf2zh` và tự overlay
  text đã dịch từ `provider.translate()` lên PDF.
- `BatchOrchestrator.run_batch(batch_id, db_session) -> BatchResult`: load `Batch` + toàn
  bộ `Job` con → BR-BATCH-04 sort theo `total_pages` (fallback `file_size`) tăng dần
  (shortest-job-first) → `asyncio.Semaphore(max_concurrent_files)` (default đọc từ
  `settings.max_concurrent_files`, Increment 1 đã có = 3) → mỗi job chạy trong session DB
  RIÊNG (qua `session_factory`, không dùng chung `db_session` truyền vào `run_batch`) vì
  `AsyncSession` của SQLAlchemy KHÔNG an toàn khi nhiều coroutine dùng đồng thời — với
  `Semaphore(3)` vẫn có tối đa 3 job chạy song song thật sự. 1 job lỗi (exception bất kỳ,
  BR-BATCH-01) → catch trong `_run_one`, đánh dấu `Job.status = failed` trên session riêng
  của job đó, KHÔNG raise ra ngoài → các job khác không bị ảnh hưởng, `asyncio.gather()`
  luôn hoàn thành đủ. Verify bằng integration test thật: 5 job (1 job raise
  `RuntimeError`) → 4 job còn lại `completed`, job lỗi `failed` với `error_message` chứa lý
  do; test riêng verify thứ tự gọi đúng shortest-first với `max_concurrent_files=1`.
- `tests/integration/test_job_orchestrator.py` (2 test), `tests/integration/
  test_batch_orchestrator.py` (2 test) — dùng SQLite thật (`:memory:` cho job orchestrator,
  file tmp cho batch orchestrator vì cần nhiều connection/session độc lập cùng thấy 1 DB —
  `:memory:` sqlite mỗi connection là 1 DB riêng nếu không dùng `StaticPool`), mock
  `Pdf2zhRunner`/`TranslationProvider` nhưng cho mock TẠO FILE PDF THẬT bằng PyMuPDF ở
  `output_path` để `font_shrink_page`/`merge_chunk_pdfs` chạy logic PDF thật, không mock
  `fitz`.

**Retry Logic** (`src/utils/retry.py`, BR-BATCH-02, US-08)
- `with_retry(func, max_attempts=3, backoff_base=2)` — generic wrapper, backoff
  `backoff_base ** attempt` (2s→4s→8s). Transient (`RateLimitError`, `TimeoutError`,
  `ConnectionError`) → retry; permanent (`AuthenticationError`) hoặc bất kỳ exception nào
  KHÔNG nằm trong danh sách transient → raise ngay lập tức, không đốt hết lượt retry cho
  lỗi kiểu file hỏng/format không hỗ trợ.
- `tests/test_retry.py` — 4 test dùng `unittest.mock.patch("src.utils.retry.asyncio.sleep")`
  để test không cần chờ thật: fail 2 lần rồi thành công lần 3 (verify gọi đúng 3 lần +
  `sleep(2)`, `sleep(4)` đúng thứ tự), hết retry vẫn raise, permanent error không retry,
  exception lạ (`ValueError`) không retry.

**Progress Tracker** (`src/core/progress_tracker.py`, US-07)
- `ProgressTracker.update(job_id, current_chunk, total_chunks, db_session)` — ghi
  `Job.current_chunk`, `Job.total_chunks`, `Job.progress = current_chunk/total_chunks` vào
  DB. Chưa có WebSocket push (đúng phạm vi "KHONG lam" của brief — để increment Frontend).
- **Field DB mới**: `Job.current_chunk: int | None`, `Job.total_chunks: int | None` thêm
  vào `src/models/job.py`. Lý do: US-07 yêu cầu dashboard hiển thị "chunk hiện tại/tổng",
  nhưng `Job` (Architecture.md 4.2) chỉ có `progress: REAL` (tỷ lệ 0.0-1.0) — không đủ để
  hiển thị "chunk 5/10". Tái sử dụng `progress` có sẵn thay vì thêm `progress_percent`
  trùng lặp (brief gợi ý `progress_percent` nhưng field tương đương đã tồn tại).
- `tests/test_progress_tracker.py` — 2 test: update đúng field + progress ratio, job không
  tồn tại raise `JobNotFoundError`.

### Quyết định kỹ thuật đáng chú ý / deviation (tổng hợp)

1. Đặt tên `ChunkPlan` thay vì `Chunk` trong `chunking.py` — tránh đụng tên với SQLModel
   `Chunk` (`src/models/chunk.py`).
2. Công thức `calculate_chunks()` suy từ ví dụ minh hoạ trong Architecture.md 6.1, không
   theo literal code mẫu (mâu thuẫn nội bộ giữa công thức và ví dụ ngay bên dưới nó).
3. `merge_chunk_pdfs()` nhận `list[Chunk]` (SQLModel) thay vì `list[Path]` — cần
   `overlap_start`/`overlap_end` để không merge trùng trang.
4. Thêm `Job.current_chunk`, `Job.total_chunks` (SQLModel field mới) — cần cho US-07.
5. **Cần Tech Lead xác nhận**: `JobOrchestrator` gọi cả `provider.translate()` (accounting)
   VÀ `pdf2zh_runner.translate_pages()` (render) cho mỗi chunk — theo đúng brief nhưng có
   nguy cơ tính phí API thật 2 lần khi chạy production thật (hiện tại an toàn vì
   pdf2zh/provider đều chưa chạy thật, chỉ chạy qua Docker/API key thật ở increment sau).
6. `BatchOrchestrator` dùng session riêng (`session_factory`) cho mỗi job chạy song song
   thay vì tái sử dụng `db_session` truyền vào `run_batch` — bắt buộc vì SQLAlchemy
   `AsyncSession` không thread/task-safe cho truy cập đồng thời.
7. `font_shrink.py`: dùng font "helv" (base-14) khi vẽ lại span thay vì font gốc/Noto —
   giới hạn đã ghi rõ, không ảnh hưởng logic 3 bước shrink/condense/flag.
8. `EpubNotSupportedError`: `run_job()` reject EPUB ngay từ đầu — pipeline EPUB
   (bilingual_book_maker) chưa implement, đúng phạm vi "KHONG lam" của brief.
9. Với `pdf_scan`, `run_job()` gọi `MinerURunner.parse_document()` để lấy `ocr_confidence`
   nhưng CHƯA reconstruct PDF có text layer từ markdown OCR (Architecture.md 3.2 bước 3) —
   vẫn dùng `job.file_path` gốc cho `pdf2zh_runner` như flow `pdf_digital`. Đây là giới hạn
   đã biết, cần increment riêng cho bước "Reconstruct PDF voi text layer".
10. Chưa implement: API endpoint để trigger job/batch qua HTTP, WebSocket progress push,
    EPUB pipeline, DeepL glossary resource sync — đúng phạm vi "KHONG lam trong increment
    nay" của brief.

### Kết quả verify
- `ruff check src/`: All checks passed
- `pytest tests/ -v`: **82 passed** (57 test cũ từ Increment 1-3 + 25 test mới: 5
  chunking + 5 font_shrink + 2 bilingual_merge + 3 chunk_merge + 4 retry + 2
  progress_tracker + 2 job_orchestrator integration + 2 batch_orchestrator integration)
- `python -c "from src.api.main import app"`: import chain thành công, không lỗi
- Không cần Docker/pdf2zh/MinerU thật — mock qua dependency injection, nhưng mọi thao tác
  PDF (font shrink, bilingual merge, chunk merge, extract chunk text) chạy PyMuPDF thật
  trên file PDF thật tạo trong test, không mock `fitz`.

## Docker verification (PM, ngoài phạm vi increment) — 2026-09-04

Sau khi user cài Docker Desktop xong, PM tự build + chạy thử image để verify hạ tầng
(không phải business logic) trước khi Increment 4 hoàn thành. Phát hiện 2 vấn đề:

1. **[Đã sửa]** `docker/Dockerfile` — `RUN uv sync --frozen --no-dev` fail vì
   `pyproject.toml` khai báo `readme = "README.md"` (hatchling build backend) nhưng
   Dockerfile chỉ `COPY pyproject.toml uv.lock ./` trước khi sync, thiếu README.md.
   Sửa: `COPY pyproject.toml uv.lock README.md ./`. Build lại thành công.

2. **[Chưa sửa — để QA/Reviewer xử lý ở vòng kiểm tra Docker cuối]** `src/core/config.py`
   default `database_url` và `.env.example` dùng path tương đối
   (`sqlite+aiosqlite:///data/bb_translation.db`, 3 dấu `/`), trong khi
   `docker/docker-compose.yml` hardcode path tuyệt đối
   (`sqlite+aiosqlite:////data/bb_translation.db`, 4 dấu `/`) khớp với volume mount
   `../data:/data`. Chạy qua `docker compose up` (cách vận hành chính thức) hoạt động
   đúng vì compose override giá trị này. Nhưng chạy `docker run` trực tiếp không qua
   compose (hoặc quên set biến môi trường) sẽ crash vì SQLite cố mở `/app/data/...`
   (không tồn tại) thay vì `/data/...`. Đề xuất: đồng bộ lại 2 giá trị này, hoặc thêm
   `mkdir -p /app/data` phòng thủ trong Dockerfile, hoặc ghi rõ trong README là bắt buộc
   chạy qua `docker compose`, không hỗ trợ `docker run` trực tiếp.

Đã verify thực tế qua `docker compose -f docker/docker-compose.yml up -d app`:
`GET /health` → `200 {"status":"ok"}`, DB file + WAL tạo đúng trong `data/` (volume mount
từ host), `init_db()` chạy thành công trong container.

## Increment 4 — Fix Round 1 (Architecture correction: eliminate double-translation)

**Đây là fix cho lỗi kiến trúc phát hiện SAU KHI Increment 3+4 đã được Reviewer
APPROVE, không phải một review comment thường.** Tech Lead research trực tiếp source
code `pdf2zh` (`Byaidu/PDFMathTranslate@main`) và phát hiện `JobOrchestrator.run_job()`
gọi CẢ `provider.translate()` (Increment 3, cho mục đích accounting) LẪN
`pdf2zh_runner.translate_pages()` (render) cho cùng một nội dung — trong khi pdf2zh TỰ
gọi LLM API bên trong. Hậu quả nếu chạy thật: trả phí API 2 lần cho cùng 1 đoạn text,
và bản dịch dùng để tính cost khác bản dịch thực sự được render lên PDF (2 lệnh gọi LLM
độc lập → không deterministic). Kiến trúc mới đầy đủ: Architecture.md section 6.6 (viết
lại hoàn toàn), 2.2, 3.1, 4.2, 5.2, 5.3, 6.1, 6.2, 6.7, 8.

### Quyết định kiến trúc đã chốt (Tech Lead, Architecture.md 6.6.2 — Option A)

Một đoạn nội dung chỉ được gọi LLM **ĐÚNG MỘT LẦN**, nằm **BÊN TRONG** pdf2zh (PDF).
`JobOrchestrator` không còn gọi `provider.translate()` trong đường render. `provider`
(Increment 3, giữ nguyên không xoá) chuyển vai trò thành **out-of-band**: chỉ dùng cho
`estimate_cost()` — cost estimation trước job, và (increment sau) test connection/sample
preview. **Đây là lý do các quyết định implementation dưới đây tồn tại — không phải Dev
tự chọn kiến trúc khác.**

### File MỚI

- **`src/services/pdf2zh_service_map.py`** — `Pdf2zhService` (dataclass: `service_arg`,
  `envs`, `supports_custom_prompt`), `UnsupportedForPdfPipelineError`,
  `Pdf2zhServiceMapper.map(provider_name, settings) -> Pdf2zhService`. Map 6 provider nội
  bộ → `-s` flag đúng theo bảng Architecture.md 6.6.3: `claude` → `openailiked:{model}`
  qua Anthropic OpenAI-compat layer (`OPENAILIKED_BASE_URL=https://api.anthropic.com/v1/`
  — **KHÔNG PHẢI** `-s claude`, pdf2zh không có native Claude translator); `openai`,
  `gemini`, `deepseek`, `ollama` → native `-s` tương ứng; `deepl` → luôn raise
  `UnsupportedForPdfPipelineError` với message giải thích rõ lý do (DeepL
  `CustomPrompt = False` trong pdf2zh, không nhận glossary). API key luôn truyền qua
  `envs` (subprocess environment), không bao giờ qua argv (`ps` đọc được argv).
  `tests/test_pdf2zh_service_map.py` — 9 test, gồm 1 test riêng verify DeepL reject.

### File SỬA — breaking changes

- **`src/services/pdf2zh_runner.py`**
  - **BREAKING**: `Pdf2zhResult.output_path` → tách thành `mono_path` (bản VI, dùng cho
    merge) + `dual_path` (bản song ngữ pdf2zh tự sinh, `None` nếu không tồn tại).
  - **BREAKING**: `translate_pages()` đổi signature: `output_path: Path` (1 file) →
    `output_dir: Path` (1 thư mục riêng/chunk — pdf2zh đặt tên output theo tên file input,
    dùng chung dir giữa các chunk sẽ ghi đè); `service: str` → `service: Pdf2zhService`;
    `custom_prompt: str | None` → `prompt_file: Path | None` (pdf2zh's `--prompt` nhận
    ĐƯỜNG DẪN FILE qua `open()`, KHÔNG PHẢI chuỗi inline — code cũ truyền thẳng string sẽ
    crash khi chạy thật). Thêm `ignore_cache: bool = False` (map `--ignore-cache`),
    `timeout_seconds: int = 3600` (mới: `Pdf2zhTimeoutError`, kill process khi vượt
    timeout — pdf2zh có thể treo vô thời hạn, chưa có bảo vệ này trước đây).
  - `prompt_file` bị bỏ qua khi `service.supports_custom_prompt is False` (defense in
    depth — trong thực tế `Pdf2zhServiceMapper` đã chặn DeepL từ trước khi runner được
    gọi, nhưng runner tự vệ thêm 1 lớp phòng khi bị gọi trực tiếp bỏ qua mapper).
  - `tests/test_pdf2zh_runner.py` viết lại hoàn toàn theo signature mới, thêm test verify
    API key không lọt vào argv, test timeout kill process, test bỏ qua `--prompt` khi
    `supports_custom_prompt=False`.

- **`src/core/glossary_manager.py`** — `build_prompt_snippet()` thêm 2 tham số mới
  (không phá vỡ caller cũ, cả hai đều optional mặc định `None`):
  `only_terms_present_in: str | None` (text EN toàn tài liệu, dùng lọc glossary chỉ giữ
  term THỰC SỰ xuất hiện — case-insensitive, word-boundary regex) và
  `max_entries: int | None` (trần cứng, ưu tiên term có tần suất xuất hiện cao nhất khi
  vượt trần, ghi `logger.warning` khi bị cắt bớt). Lý do (Architecture.md 6.6.5): pdf2zh
  gửi prompt cho TỪNG SEGMENT riêng lẻ (không phải 1 lần/job) — glossary không lọc sẽ
  nhân input token lên hàng chục lần cho tài liệu dài. 7 test mới trong
  `tests/test_glossary_manager.py` (filter theo document, word-boundary không match
  substring, cap theo tần suất, cap không kèm filter).

- **`src/core/prompt_builder.py`** — hàm MỚI `write_prompt_file(glossary_manager, path,
  project_id=None, only_terms_present_in=None, max_glossary_entries=80) -> Path`. Ghi
  file `--prompt` cho pdf2zh đúng contract Architecture.md 6.6.4: dùng token literal
  `${lang_in}`/`${lang_out}`/`${text}` (KHÔNG tự substitute — pdf2zh tự làm qua
  `string.Template.safe_substitute` cho từng segment); mọi `$` khác trong glossary/nội
  dung được escape thành `$$` (`_escape_dollar()`); unit-conversion block chỉ chèn khi
  phát hiện dấu hiệu công thức (`cup`, `tbsp`, `tsp`, `oz`, `°F`, `inch`) trong
  `only_terms_present_in`; raise `ValueError` nếu `${text}` bị thiếu khỏi nội dung cuối
  cùng (guard, về lý thuyết không thể xảy ra vì nằm trong template tĩnh — phòng khi sửa
  sau này lỡ xoá mất). `build_system_prompt()` cũ GIỮ NGUYÊN không đổi — vẫn dùng cho vai
  trò out-of-band (`TranslationProvider.translate(system_prompt=...)`). 6 test mới trong
  `tests/test_prompt_builder.py`.

- **`src/core/cost_estimator.py`**
  - `CostEstimate` thêm field `cost_source: str = "estimated"` — v1.0 luôn là uớc lượng,
    field tồn tại để caller ghi thẳng vào `Job.cost_source` mà không cần tự biết fact đó.
  - Hàm MỚI `estimate_chunk_cost(source_text, segment_count, prompt_overhead_chars,
    provider, vi_expansion=1.3, vi_token_factor=1.5) -> tuple[int, int, float]` đúng công
    thức Architecture.md 6.6.6 — `prompt_overhead_chars` nhân với `segment_count` (không
    cộng 1 lần) vì pdf2zh gửi lại toàn bộ prompt file cho MỖI segment (F6). `provider`
    dùng DUY NHẤT qua `.estimate_cost()` (thuần tính toán), không gọi API — cùng vai trò
    out-of-band R3 như `estimate_job_cost()`.
  - **Quyết định implementation tự quyết (Architecture.md không đặc tả cách đo
    `segment_count`)**: `job_orchestrator._count_text_segments()` đếm số PyMuPDF text
    block không rỗng trong page range của chunk làm xấp xỉ cho segment count thật của
    pdf2zh (không quan sát được từ bên ngoài subprocess) — đã ghi rõ đây là xấp xỉ trong
    docstring, không phải số đo chính xác.
  - 5 test mới trong `tests/test_cost_estimator.py`.

- **`src/models/job.py`** — **BREAKING SCHEMA CHANGE**: thêm field
  `Job.cost_source: str = "estimated"` (`'estimated' | 'metered'`, Architecture.md 4.2).
  DB dev hiện tại xoá tạo lại được (chưa có data thật quan trọng) — không viết Alembic
  migration ở giai đoạn này, theo đúng yêu cầu task brief.

- **`src/core/config.py`** — thêm `default_provider: str = "deepseek"` (PRD US-14:
  "Provider mặc định: DeepSeek"), `openai_base_url` (cần cho `Pdf2zhServiceMapper`, thiếu
  trong Settings cũ), và nhóm `pdf_pipeline` settings mới:
  `max_glossary_entries_in_prompt: int = 80`, `pdf2zh_ignore_cache: bool = False`,
  `pdf2zh_timeout_seconds: int = 3600`, `vi_expansion_factor: float = 1.3`,
  `vi_token_factor: float = 1.5`, `metering_proxy_enabled: bool = False` (chưa dùng —
  dành cho v1.1 metering proxy, Architecture.md 6.6.6, KHÔNG implement ở increment này
  theo đúng phạm vi "HOAN lai" của Architecture.md).

- **`src/core/job_orchestrator.py`** — **BREAKING**: viết lại `run_job()` theo đúng 10
  bước Architecture.md 6.6.8.
  - **GỠ BỎ hoàn toàn**: tham số constructor `provider` KHÔNG còn được dùng để dịch —
    đổi vai trò thành pricing provider out-of-band. Mọi lời gọi `provider.translate()`
    trong `_process_chunk()` đã bị xoá. Constructor thêm `service_mapper:
    Pdf2zhServiceMapper | None = None`.
  - Thứ tự mới trong `run_job()`: (1) reject EPUB, (2) đếm `total_pages` + OCR nếu
    `pdf_scan`, (3) extract text EN toàn file (`_extract_full_text()`, PyMuPDF) để lọc
    glossary, (4) `service_mapper.map(job.model, settings)` — **DeepL (hoặc provider lạ)
    fail NGAY Ở ĐÂY**, set `Job.status = failed` với `error_message` rõ ràng, return
    trước khi chạm tới bất kỳ subprocess nào, (5) `write_prompt_file()` — 1 lần/job, tái
    sử dụng cho mọi chunk, (6) `plan_chunks()` + load/create `Chunk` rows (BR-CHUNK-05
    resumable, giữ nguyên logic cũ), (7) mỗi chunk: `pdf2zh_runner.translate_pages()` (LẦN
    GỌI LLM DUY NHẤT, qua `with_retry`) → `font_shrink_page()` → `estimate_chunk_cost()` →
    cập nhật `Chunk` + `ProgressTracker`, (8) `merge_chunk_pdfs()`, (9) bilingual output
    nếu batch yêu cầu, (10) `Job.actual_cost = Σ chunk.api_cost`,
    `Job.cost_source = "estimated"`, `status = completed`.
  - **Quyết định implementation tự quyết**: `GlossaryManager`, `cost_estimator` module,
    `prompt_builder` module KHÔNG được inject qua constructor (khác với pseudocode gợi ý
    trong Architecture.md 6.6.8) — giữ nguyên pattern đã có từ Increment 4 gốc:
    `GlossaryManager(db_session)` tạo mới per-session bên trong `run_job()` (session chỉ
    có tại thời điểm gọi, không thể inject qua `__init__`); `cost_estimator`/
    `prompt_builder` là module hàm thuần (pure functions), gọi trực tiếp như
    `font_shrink_page()`/`merge_chunk_pdfs()` đã có sẵn, không cần DI vì không có I/O
    ngoài cần mock độc lập với `pdf2zh_runner`/`mineru_runner`/`provider`.
  - Mỗi chunk render vào `data/processing/{job_id}/chunk_{index}/` (thư mục riêng biệt,
    đúng F9) thay vì `chunks/chunk_{index:03d}.pdf` dùng chung thư mục `chunks/` như cũ.
  - `tests/integration/test_job_orchestrator.py` viết lại hoàn toàn: fake
    `TranslationProvider` giờ chỉ implement `.estimate_cost()` (không còn `.translate()`
    side_effect); test resumable-after-failure giờ mô phỏng lỗi bằng cách cho
    `pdf2zh_runner` raise (không phải provider) vì đó là điểm lỗi duy nhất còn lại trên
    đường render; **test MỚI quan trọng nhất**: `test_run_job_with_deepl_fails_before_any_subprocess_call`
    — verify job PDF dùng DeepL fail ngay ở bước map service, `pdf2zh_runner.translate_pages`
    KHÔNG BAO GIỜ được gọi (`assert_not_awaited()`), `Job.status = failed` với
    `error_message` chứa "DeepL".

### Behavior đổi (không phải bug, là quyết định kiến trúc)

1. **Không còn double-translation**: 1 đoạn nội dung = 1 lần gọi LLM thật, nằm trong
   pdf2zh. Trước đây (Increment 3+4 gốc) là 2 lần gọi LLM độc lập cho cùng nội dung.
2. **Cost luôn là ước lượng ở v1.0** (`cost_source = "estimated"`), sai số kỳ vọng
   ±30–50% — không phải số đo chính xác, không dùng để đối soát hoá đơn nhà cung cấp.
   Trước đây `chunk.api_cost` đến từ `TranslationResult.estimated_cost_usd` của lần gọi
   `provider.translate()` thật (chính xác hơn nhưng lại là bản dịch KHÔNG được dùng để
   render — nên "chính xác" đó vô nghĩa).
3. **DeepL bị chặn cứng ở tầng logic cho PDF pipeline**, không chỉ ẩn ở UI — code gọi
   `Pdf2zhServiceMapper.map("deepl", ...)` luôn raise `UnsupportedForPdfPipelineError`,
   bất kể UI có ẩn được lựa chọn này hay không.
4. **Glossary bị lọc theo tài liệu + giới hạn trần 80 entry mặc định** trước khi vào
   prompt — trước đây gửi nguyên toàn bộ glossary global+project không giới hạn.
5. **Provider mặc định đổi sang DeepSeek** (`settings.default_provider`), theo PRD US-14
   cập nhật — trước đây các test/fixture dùng `claude` làm ví dụ mặc định.

### Kết quả verify
- `uv run ruff check src/`: All checks passed.
- `uv run ruff format --check` trên toàn bộ file sửa/tạo mới: pass sau khi format lại 5
  file (glossary_manager.py, prompt_builder.py, test_job_orchestrator.py,
  test_glossary_manager.py, test_prompt_builder.py).
- `uv run pytest tests/ -v`: **108 passed** (82 test cũ từ Increment 1-4 gốc + 26 test
  mới: 9 `pdf2zh_service_map` + 5 `pdf2zh_runner` sửa lại/thêm mới + 7 `glossary_manager`
  filter/cap + 6 `prompt_builder` write_prompt_file + 5 `cost_estimator` + 3
  `job_orchestrator` integration, trong đó có test DeepL-reject).
- `python -c "from src.api.main import app"`: import chain thành công, không lỗi.
- **Verify riêng theo yêu cầu**: `tests/integration/test_job_orchestrator.py::test_run_job_with_deepl_fails_before_any_subprocess_call`
  tạo job PDF với `model="deepl"`, chạy `run_job()`, assert `result.status == "failed"`,
  `"DeepL" in result.error_message`, và **`pdf2zh_runner.translate_pages.assert_not_awaited()`**
  — chứng minh job dừng lại ở bước map service (bước 4/10), không tiến tới bất kỳ
  subprocess call nào. Có thêm 1 unit test độc lập
  `test_pdf2zh_service_mapper_rejects_deepl_directly()` verify riêng tầng
  `Pdf2zhServiceMapper` không phụ thuộc vào orchestration xung quanh.

### Chưa làm (đúng phạm vi increment này)
- v1.1 LLM Metering Proxy (`src/services/metering_proxy.py`) — thiết kế sẵn trong
  Architecture.md 6.6.6 nhưng KHÔNG implement, đúng chỉ dẫn "HOAN lai, khong implement o
  vong nay".
- EPUB pipeline thật — chưa có code EPUB nào tồn tại để sửa theo nguyên tắc "no
  double-translation" (Architecture.md 6.7); khi increment EPUB được lên kế hoạch, áp
  dụng cùng nguyên tắc R1 cho `bilingual_book_maker`.
- Wiring `run_job()`/`run_batch()` vào HTTP endpoint thật — vẫn ngoài phạm vi (chưa có
  increment Frontend/API layer nào gọi tới `JobOrchestrator`).

## Increment 5 — API & Frontend

Dev: lắp API layer (upload, job/batch, download, WebSocket progress, settings) lên trên
`JobOrchestrator`/`BatchOrchestrator` (Increment 4, cho tới nay chưa có endpoint HTTP nào gọi
tới), cộng frontend HTML + Alpine.js + Tailwind (CDN, không build step) theo đúng Tech Stack
Architecture.md section 1.

### File MỚI

- **`src/api/routes/upload.py`** — `POST /api/upload`: nhận `UploadFile`, validate extension
  (BR-INPUT-04) + size (BR-INPUT-03, đọc `settings.max_upload_size_mb`) khi đang stream ghi
  file (không đọc hết vào RAM trước khi check), gọi `file_router.detect_file_type()`, đếm
  `page_count` qua PyMuPDF nếu không phải EPUB. Lưu file vào
  `data/uploads/{file_id}_{filename}` + 1 sidecar JSON `data/uploads/{file_id}.json`
  (`resolve_upload()`) chứa `file_path`/`file_hash`/`file_type`/`size_bytes`/`page_count` —
  không có bảng `uploads` nào trong Architecture.md 4.2, sidecar là cách nhỏ nhất để
  `POST /api/jobs` biến `file_id` thành đủ dữ liệu tạo `Job` mà không phải đọc/hash lại file
  (có thể tới 500MB) ở mỗi lần gọi.
- **`src/api/routes/jobs.py`** — SỬA file router rỗng từ Increment 1:
  - `POST /api/jobs` — tạo `Job` (202 Accepted). BR-PROVIDER-01: nếu `job_type=translate` +
    `provider=deepl` + file là PDF (`pdf_digital`/`pdf_scan`) → reject 400 NGAY, tái sử dụng
    `Pdf2zhServiceMapper.map()` đã có (Increment 4) để lấy đúng message giải thích, **không
    tạo `Job` row** (verify bằng test: `GET /api/jobs` trả `total: 0` sau khi bị reject).
  - `POST /api/batches` — tương tự cho nhiều `file_id`, dùng `BatchOrchestrator.run_batch()`.
  - `GET /api/jobs/{id}`, `GET /api/jobs` (pagination + filter `status`),
    `POST /api/jobs/{id}/retry` (chỉ cho job `status=failed`; resume tự động vì
    `run_job()` đã resumable từ Increment 4 — BR-CHUNK-05), `GET /api/jobs/{id}/cost-estimate`
    (gọi `cost_estimator.estimate_job_cost()`, ghi `Job.estimated_cost`).
- **`src/api/routes/download.py`** — `GET /api/jobs/{id}/download` (+ `?format=bilingual`),
  404 nếu job chưa `completed` hoặc thiếu file trên disk.
- **`src/api/routes/settings.py`** — `GET`/`PUT /api/settings`: `GET` trả `has_key: bool` cho
  từng provider (không bao giờ trả API key thật); `PUT` ghi vào bảng `settings` (key/value),
  KHÔNG ghi vào `.env`.
- **`src/api/websocket.py`** — `ConnectionManager` (`connect`/`disconnect`/
  `broadcast_progress`, đăng ký theo `job_id`), `WS /ws/jobs/{job_id}`. Singleton
  `connection_manager` module-level (app 1-user, 1 process — Architecture.md section 1: không
  cần message queue). `tests/test_websocket_connection_manager.py` — 6 test: connect gọi
  `accept()`, disconnect xoá đúng socket, broadcast chỉ tới đúng `job_id` (không lọt sang
  job khác), broadcast tới job không có connection nào không raise, socket chết bị tự động
  drop khi `send_json` raise.
- **`web/index.html` + `web/js/app.js`** — upload drag & drop đa file (US-02), sau upload
  hiện list file kèm loại đã detect, chọn provider (ẩn DeepL nếu PDF — BR-PROVIDER-01), chọn
  `output_mode`/`job_type`, nút "Xem chi phí ước tính" + "Dịch tất cả", dashboard progress qua
  WebSocket (fallback polling `GET /api/jobs/{id}` mỗi 3s nếu socket lỗi), nút download khi
  `completed`.
- **`web/glossary.html` + `web/js/glossary.js`** — CRUD glossary gọi thẳng API đã có sẵn từ
  Increment 2 (`src/api/routes/glossary.py`, không sửa backend), import Excel 2 bước
  preview → confirm, export, inline edit, filter theo scope.
- **`web/history.html` + `web/js/history.js`** — US-12, list `GET /api/jobs` + pagination +
  filter status + nút download cho job `completed`.
- **`web/css/style.css`** — vài rule tối thiểu (Tailwind CDN lo phần lớn UI).
- **`tests/integration/test_upload_and_job_flow.py`** — 7 test qua `TestClient` thật (không
  mock DB layer, chỉ isolate bằng `tmp_path`/`monkeypatch.chdir` + reset cache
  `get_settings`/`database_module._engine` — xem "Approach test" bên dưới): upload → tạo job
  `parse_only` → check status full flow, upload reject sai extension, upload reject quá size
  (monkeypatch `get_settings` trả limit rất nhỏ), **reject sớm DeepL+PDF: verify 400 VÀ
  `GET /api/jobs` total=0 sau đó** (đúng yêu cầu brief "không tạo Job record"), 404 cho job
  không tồn tại, 404 khi tạo job với `file_id` không tồn tại, 404 khi download job chưa xong.

### File SỬA

- **`src/core/progress_tracker.py`** — `ProgressTracker.__init__(broadcaster: BroadcastFn |
  None = None)`. `update()` giữ nguyên hành vi ghi DB (Increment 4 không đổi), sau khi commit
  thì `await self._broadcaster(job_id, {...})` nếu có — event shape đúng Architecture.md 5.2
  `{"type": "progress", ...}`. `broadcaster=None` mặc định → 100% tương thích ngược với 2 test
  cũ trong `tests/test_progress_tracker.py` (không sửa file đó).
- **`src/core/job_orchestrator.py`** — `JobOrchestrator.__init__` thêm
  `progress_broadcaster: BroadcastFn | None = None`, truyền vào
  `ProgressTracker(broadcaster=self._progress_broadcaster)` thay vì `ProgressTracker()`. Thêm
  broadcast `job_completed` (cuối `run_job()` khi thành công) và `job_failed`
  (`_broadcast_job_failed()`, gọi ở cả 2 điểm job có thể fail: DeepL/service-mapper reject sớm
  VÀ chunk fail giữa chừng) đúng shape Architecture.md 5.2. Không đổi logic pipeline nào khác
  của Increment 4 (chunking/render/merge/cost) — chỉ thêm hook quan sát.
- **`src/core/config.py`** — thêm `get_effective_settings(session) -> Settings` +
  `SETTINGS_DB_OVERRIDABLE_FIELDS` + `_cast_setting_value()`. **Quyết định thiết kế ngoài
  Architecture.md gốc** (yêu cầu ghi rõ trong brief): `get_settings()` (cached, đọc `.env`)
  giữ nguyên không đổi; `get_effective_settings()` là hàm MỚI, đọc thêm bảng `settings` (DB)
  và merge đè lên snapshot `.env` mỗi lần gọi — không cache, không mutate `Settings` singleton
  tại chỗ. Lý do tách riêng thay vì sửa `get_settings()` tại chỗ: `get_settings()` là hàm
  đồng bộ (`@lru_cache`) được gọi từ nhiều chỗ không có DB session (vd unit test
  `Pdf2zhServiceMapper`, `ProviderFactory` trong test hiện có) — đổi nó thành async hoặc thêm
  side-effect DB sẽ phá vỡ toàn bộ test suite cũ. Chỉ những field người dùng có thể muốn đổi
  qua UI (API key, model, `default_provider`, `max_concurrent_files`) được đưa vào
  `SETTINGS_DB_OVERRIDABLE_FIELDS` — field cấu hình chunking/cost heuristic vẫn chỉ đọc từ
  `.env`/code.
- **`src/api/main.py`** — mount `jobs.router` (`/api/jobs`), `jobs.batches_router`
  (`/api/batches`), `download.router` (`/api/jobs`, cùng prefix để route đọc là
  `GET /api/jobs/{id}/download`), `upload.router` (`/api/upload`), `settings.router`
  (`/api/settings`), `websocket.router` (không prefix, path đã có `/ws/jobs/{id}`). Mount
  `StaticFiles(directory="web", html=True)` tại `/` — đặt SAU mọi `include_router()` để không
  che các route `/api/*`/`/health`. Chỉ mount khi thư mục `web/` tồn tại (phòng
  môi trường test/CI không checkout thư mục này).

### Quyết định thiết kế đáng chú ý

1. **Background task = `asyncio.create_task()`, không dùng FastAPI `BackgroundTasks`.** Lý
   do: 1 job dịch có thể chạy nhiều phút (Architecture.md 9.1: "~5-10 phút/100 trang"), và
   `BackgroundTasks` gắn vòng đời task vào chính request/response đã tạo ra nó — không có chỗ
   nào khác trong app quan sát/theo dõi được nó sau khi response đã gửi. `asyncio.create_task()`
   cho 1 `Task` object độc lập, giữ tham chiếu trong `_background_tasks: set[asyncio.Task]`
   (tránh bug kinh điển: task không giữ ref có thể bị GC giữa chừng) — khớp đúng với việc job
   sống lâu hơn hẳn HTTP call đã khởi tạo nó. Trade-off đã chấp nhận: nếu process bị kill giữa
   chừng, task đang chạy mất (không có persistent queue) — chấp nhận được cho app 1-user chạy
   local (Architecture.md: "asyncio + in-process queue... du an 1 user").
2. **DB settings override `.env`** — xem phần "File SỬA — `src/core/config.py`" ở trên.
3. **`POST /api/jobs` (job đơn lẻ) vẫn tạo 1 `Batch` ẩn** — `JobOrchestrator._wants_bilingual()`
   (Increment 4) đọc `output_mode` từ `Batch`, không phải từ `Job`, và scope glossary project
   cũng luôn là `project:{job.batch_id}` (Architecture.md 3.4) — không có field nào khác trên
   `Job` mang 2 thông tin này. Thay vì sửa `JobOrchestrator`/schema (ngoài phạm vi — brief cấm
   "không tự ý thay đổi architecture"), 1 job đơn lẻ vẫn được gắn vào 1 `Batch` mới
   (`total_files=1`) mang đúng `output_mode` đã chọn; nếu request có `glossary_project_id`,
   nó phải trỏ tới 1 `Batch` đã tồn tại (dùng lại đúng khái niệm project glossary hiện có) thay
   vì tạo `Batch` mới — 404 nếu không tìm thấy.
4. **`job_type=parse_only` được API chấp nhận nhưng đánh dấu `failed` NGAY** với
   `error_message` giải thích rõ, thay vì để `status=created` treo vô thời hạn hoặc crash.
   Lý do: `JobOrchestrator.run_job()` (Increment 4) chưa có nhánh xử lý parse_only — brief
   increment này không yêu cầu implement nhánh MinerU-only đó (nằm trong US-15/Architecture.md
   6.8, là core pipeline logic, ngoài phạm vi "lắp API layer"). Đây cũng chính là lý do test
   integration chính (`test_upload_and_job_flow.py`) và bước verify thủ công dùng
   `job_type=parse_only` — không cần API key thật, và trả kết quả ngay trong 1
   request/response, không cần chờ/polling task nền.
5. **`Pdf2zhServiceMapper` được tái sử dụng ở tầng API** (`_reject_deepl_for_pdf()`) thay vì
   viết lại logic "DeepL không hỗ trợ PDF" lần 2 — chỉ 1 nơi định nghĩa lý do reject
   (`src/services/pdf2zh_service_map.py`), tầng API chỉ quyết định KHI NÀO gọi nó (dựa vào
   `job_type`/`file_type`) để fail sớm hơn, trước khi có bất kỳ `Job` row nào.
6. **`estimate_job_cost()` không chặn/block job đang chạy** — vì kiến trúc hiện tại (Increment
   4/5) khởi chạy job ngay khi tạo (`POST /api/jobs` trigger background task luôn), không có
   trạng thái "đã tạo nhưng chưa chạy" để user confirm cost trước. Cost estimate endpoint vẫn
   hoạt động đúng in dependently (chỉ cần `job.total_pages` + provider, không phụ thuộc
   job đã chạy xong hay chưa) — frontend gọi nó ngay sau khi tạo job và hiển thị song song với
   progress bar, ghi chú rõ đây là ước lượng "trong lúc job đang chạy" chứ không chặn được job
   trước khi bắt đầu như R-01 hình dung lý tưởng. Đã ghi chú trực tiếp trong
   `web/js/app.js` — cần Tech Lead xác nhận nếu muốn tách hẳn bước "tạo job" ra khỏi "chạy
   job" ở increment sau.
7. **Approach test cho `test_upload_and_job_flow.py`**: không dùng `StaticPool` +
   `dependency_overrides` như `test_glossary_api.py` (Increment 2), vì `_run_job_background()`/
   `_run_batch_background()` gọi `get_session_factory()` từ `src.models.database` TRỰC TIẾP
   (background task không đi qua FastAPI dependency injection nào cả — không có request nào
   đứng sau nó để override). Thay vào đó: `monkeypatch.chdir(tmp_path)` để mọi path tương đối
   mặc định (`data/bb_translation.db`, `data/uploads`, `data/processing`, `data/outputs`) tự
   trỏ vào `tmp_path`, cộng reset `get_settings.cache_clear()` +
   `database_module._engine = database_module._session_factory = None` (trong `try/finally`
   để không rò rỉ state sang test khác nếu `TestClient(app)` lỗi ngay lúc khởi động) — nhờ vậy
   CẢ request path (`get_db_session`) LẪN background task (`get_session_factory()`) đều nhìn
   thấy cùng 1 file SQLite trong `tmp_path`, không cần polling chờ task nền cho path
   `parse_only` (fail đồng bộ ngay trong request).

### Chưa làm (đúng phạm vi increment này)

- Markdown parse-only pipeline thật (MinerU-only branch trong `JobOrchestrator`) — US-15,
  Architecture.md 6.8. `job_type=parse_only` được API chấp nhận nhưng luôn trả `failed` với lý
  do rõ ràng (mục 4 ở trên).
- EPUB pipeline — vẫn chưa tồn tại từ Increment 4, API layer chấp nhận file EPUB ở
  `POST /api/upload` (detect đúng `FileType.EPUB`) nhưng `POST /api/jobs/{id}/cost-estimate`
  trả 400 rõ ràng cho EPUB, và job EPUB thật sẽ fail trong `JobOrchestrator.run_job()`
  (`EpubNotSupportedError`, Increment 4) khi chạy nền.
- Auth, DeepL glossary resource sync thật, real-time reconnect logic phức tạp cho WebSocket
  (frontend chỉ có fallback polling đơn giản) — đúng "KHONG lam" list của brief.

### Kết quả verify

- `uv run ruff check src/`: All checks passed (1 lỗi `PYI034` còn lại trong
  `tests/test_mineru_runner.py` — có từ trước Increment 5, không đụng tới file đó).
- `uv run pytest tests/ -v`: **121 passed** (108 test cũ Increment 1-4 + 13 test mới: 6
  `test_websocket_connection_manager.py` + 7 `test_upload_and_job_flow.py`).
- `python -c "from src.api.main import app"`: import chain thành công, không lỗi.
- **Verify thủ công qua `uv run uvicorn src.api.main:app --port 8123`** (xoá
  `data/bb_translation.db` cũ trước khi chạy — schema dev cũ từ trước Increment 4 thiếu cột
  `current_chunk`/`total_chunks`/`cost_source`, không phải lỗi của increment này, DB dev vẫn
  chưa có migration theo đúng quyết định đã ghi ở Increment 4):
  - `POST /api/upload` (file PDF 3 trang tự tạo bằng PyMuPDF) → 200, `file_type: pdf_digital`,
    `page_count: 3`.
  - `POST /api/jobs` với `job_type=parse_only` → 202, `status: failed` ngay lập tức.
    `GET /api/jobs/{id}` → xác nhận `error_message` giải thích rõ "parse_only chua duoc
    JobOrchestrator ho tro". `GET /api/jobs` → `total: 1`.
  - `POST /api/jobs` với `job_type=translate, provider=deepl` (file PDF) → **400** ngay,
    `detail` chứa "DeepL"; `GET /api/jobs` sau đó vẫn `total: 1` (không tăng — job DeepL
    không được tạo).
  - `GET /api/settings` → `has_key: false` cho mọi provider (chưa cấu hình .env thật trên máy
    dev); `PUT /api/settings` với `provider_api_keys: {"deepseek": "sk-test-123"}` → `GET`
    ngay sau đó trả `deepseek.has_key: true` — xác nhận DB override hoạt động.
  - `POST /api/jobs` với `job_type=translate, provider=deepseek` (đã có key giả lập từ DB) →
    202 `queued`, sau vài giây `GET /api/jobs/{id}` → `status: failed` với lý do
    `[Errno 2] No such file or directory` — **đúng như kỳ vọng**: máy dev không cài `pdf2zh`
    CLI thật (chưa có Docker/pdf2zh — nhất quán với ghi chú "chưa cài Docker" xuyên suốt
    Increment 2-4), xác nhận toàn bộ đường ống API → background task →
    `JobOrchestrator.run_job()` → `Pdf2zhServiceMapper` → `Pdf2zhRunner.translate_pages()`
    chạy đúng tới điểm cần binary ngoài thật, fail rõ ràng thay vì treo hoặc lỗi âm thầm.
  - `WS /ws/jobs/{job_id}` — connect thành công qua client `websockets` Python độc lập.
  - `GET /index.html`, `/glossary.html`, `/history.html` → 200 (static files served đúng).
  - Dọn dẹp: xoá `data/bb_translation.db*` và `data/uploads|processing|outputs` tạo ra trong
    lúc verify thủ công trước khi kết thúc, để không để lại state thử nghiệm trong repo.

## Increment 5 — Fix Round 1 (security + data bug, sau review REJECT)

PM tự test tay qua Browser + curl trước khi giao Reviewer, phát hiện 1 bug logic
(`excel_utils.py`); Reviewer review chính thức xác nhận bug đó VÀ tự tìm thêm 1 lỗ hổng bảo
mật nghiêm trọng PM bỏ sót → verdict REJECT, iteration 1/3. Dev fix cả hai. Agent fix bị dừng
giữa chừng (user interrupt) ngay trước bước verify cuối bằng curl; code + test đã hoàn chỉnh
tại thời điểm dừng, PM tự chạy verify sống (`ruff`, `pytest`, `curl` qua uvicorn thật) để xác
nhận và bổ sung mục CHANGELOG này thay Dev.

### Blocking issue #1 — Path Traversal (CWE-22) trong `POST /api/upload` [ĐÃ SỬA]

`src/api/routes/upload.py`: `dest_path` trước đây ghép thẳng `file.filename` (client-controlled,
không sanitize) vào path lưu file — client gửi filename dạng `../../../../tmp/evil.pdf` có thể
ghi file ra ngoài `data/uploads/`. Fix: `safe_name = Path(file.filename).name` (strip mọi phần
path, chỉ giữ basename) trước khi ghép `dest_path`, cộng thêm defense-in-depth verify
`dest_path.resolve().is_relative_to(_UPLOAD_DIR.resolve())`. Grep toàn `src/` xác nhận đây là
chỗ DUY NHẤT dùng filename client-controlled để ghép path ghi file.

Test: `tests/integration/test_upload_and_job_flow.py::test_upload_sanitizes_path_traversal_filename`.
PM verify sống thêm bằng `curl` với filename `../../../../../../tmp/pwned.pdf` — file lưu an
toàn trong `data/uploads/{file_id}_pwned.pdf`, `/tmp/pwned.pdf` không được tạo.

### Blocking issue #2 — `excel_utils.py` chỉ đọc `workbook.active`, không tìm sheet theo tên [ĐÃ SỬA]

`_select_data_sheet()` (mới) trong `src/utils/excel_utils.py`: ưu tiên tìm sheet tên
"Glossary" (case-insensitive, duyệt `workbook.sheetnames`), fallback `workbook.active` nếu
không tìm thấy. Áp dụng trong `import_glossary_from_excel()`. `export_glossary_to_excel()`
không cần sửa (luôn tạo `Workbook()` mới 1 sheet, `workbook.active` chính là sheet vừa tạo,
không có ambiguity).

Test: `tests/test_excel_utils.py::test_import_finds_glossary_sheet_when_not_active`.
PM verify sống thêm bằng file Excel tự tạo có active sheet CỐ TÌNH trỏ sai (active="Notes",
data thật nằm ở sheet "Glossary") — import vẫn đọc đúng 1 entry từ sheet "Glossary", không bị
lừa bởi active sheet sai.

### Kết quả verify (PM chạy thay Dev do agent bị interrupt)
- `uv run ruff check src/`: All checks passed
- `uv run pytest tests/ -q`: **123 passed** (121 cũ + 2 test mới cho 2 fix trên)
- `python -c "from src.api.main import app"`: OK
- Path traversal: verify sống qua `curl` — chặn đúng, không escape khỏi `data/uploads/`
- Excel multi-sheet: verify sống qua `curl` với file active-sheet cố tình sai — đọc đúng sheet
  "Glossary", không bị active sheet sai đánh lừa
- Dọn dẹp file test tạm (`/tmp/evil.pdf`, `/tmp/pwned.pdf`, `/tmp/wrong-active-sheet-test.xlsx`)
  sau khi verify xong

### Chưa xử lý (non-blocking từ review, để sau nếu cần)
- `web/js/app.js` polling song song với WebSocket thay vì chỉ dùng khi WebSocket lỗi
- `PUT /api/settings` chưa validate tên provider hợp lệ trước khi lưu

## QA Fix Round 1 (Dev, vòng 1/5 Circuit Breaker Dev↔QA)

Fix cả 3 bug blocking từ `docs/test-report.md` (QA Round 1, 2026-09-04). Bug #4 (Docker
`DATABASE_URL`) KHÔNG sửa trong vòng này — QA đã đánh giá rõ là non-blocking, chấp nhận
được cho release, và không nằm trong 3 bug được giao cho vòng fix này.

### Bug #1 — Upload file `.pdf` giả/hỏng → 500 Internal Server Error [ĐÃ SỬA]

`src/core/file_router.py`: `_detect_pdf_type()` gọi `fitz.open()` không có try/except.
Fix: bọc trong try/except bắt `RuntimeError` (base class của
`pymupdf.FileDataError` — verify bằng `pymupdf.FileDataError.__mro__` trước khi sửa, không
đoán), raise `InvalidFileError` (`ValueError` subclass mới, cùng pattern với
`UnsupportedFileTypeError` đã có) với message rõ ràng "File PDF bi hong hoac khong doc
duoc, vui long kiem tra lai file".

`src/api/routes/upload.py`: bắt thêm `InvalidFileError` (cùng nhánh với
`UnsupportedFileTypeError` đã có sẵn) → 400, xoá file tạm đã ghi (`dest_path.unlink()`) —
dọn luôn phần "file rác" QA nêu ở mục non-blocking. Bọc thêm try/except quanh lệnh
`fitz.open()` thứ hai (đếm `page_count`) cho nhất quán, dù về lý thuyết không thể fail nếu
`detect_file_type()` đã mở thành công cùng file đó trước đó.

Test mới: `tests/test_file_router.py::test_detect_pdf_type_rejects_fake_pdf`,
`tests/integration/test_upload_and_job_flow.py::test_upload_rejects_fake_pdf_with_400_not_500`
(verify cả response 400 lẫn không còn file rác trong `data/uploads/`).

Verify sống qua `uvicorn` thật: upload file `.pdf` chứa text thường → `400
{"detail":"File PDF bi hong hoac khong doc duoc..."}`, không có file rác trong
`data/uploads/`, `GET /health` sau đó vẫn `200` (server không bị ảnh hưởng).

### Bug #2 — OCR (MinerU) không bao giờ được kích hoạt qua API thật [ĐÃ SỬA]

**Root cause thật sự — trả lời rõ câu hỏi của QA**: đây CHỈ là thiếu truyền tham số, KHÔNG
phải thiếu nhánh logic. Nhánh "nếu `file_type == pdf_scan` thì chạy MinerU trước" đã tồn
tại đầy đủ và đúng trong `JobOrchestrator.run_job()`
(`src/core/job_orchestrator.py:192-199`) từ Increment 4:

```python
if (
    job.file_type == FileType.PDF_SCAN
    and self._mineru_runner is not None
    and job.ocr_confidence is None
):
    ocr_result = await self._mineru_runner.parse_document(file_path, ocr_dir)
    job.ocr_confidence = ocr_result.confidence_score
```

Vấn đề duy nhất: `self._mineru_runner` luôn là `None` khi chạy qua app thật, vì
`src/api/routes/jobs.py` (`_run_job_background()`, `_run_batch_background()`) khởi tạo
`JobOrchestrator(settings=..., progress_broadcaster=...)` mà không bao giờ truyền
`mineru_runner=`. Logic OCR đúng, chỉ chưa được "wire" vào tầng API.

Fix: thêm `mineru_endpoint` (default `http://localhost:8010`, khớp port MinerU sidecar
trong `docker/docker-compose.yml`) và `mineru_timeout_seconds` (default 300s, khớp default
sẵn có trong `MinerURunner.__init__`) vào `Settings` (`src/core/config.py`). Thêm helper
`_build_mineru_runner(settings)` trong `jobs.py`, gọi ở cả `_run_job_background()` và
`_run_batch_background()` khi khởi tạo `JobOrchestrator`. Cập nhật `.env.example` (thêm
`MINERU_ENDPOINT`) và `docker/docker-compose.yml` (service `app` nay có
`MINERU_ENDPOINT=${MINERU_ENDPOINT:-http://mineru:8010}` — trỏ đúng tên service Docker
Compose thay vì `localhost`, vì trong container `localhost:8010` sẽ không tới được sidecar
`mineru`).

`mineru_endpoint` KHÔNG thêm vào `SETTINGS_DB_OVERRIDABLE_FIELDS` — đây là hạ tầng
(endpoint của 1 sidecar Docker cố định), khác với API key/provider mà user chọn qua UI
(`PUT /api/settings`), theo đúng quy ước đã ghi trong docstring `config.py`
("Only fields a user would plausibly want to change from the UI are overridable").

Test mới (`tests/integration/test_job_orchestrator.py`, dùng `unittest.mock.AsyncMock` theo
đúng yêu cầu QA):
- `test_run_job_calls_mineru_before_pdf2zh_for_pdf_scan` — mock cả `mineru_runner` và
  `pdf2zh_runner`, ghi lại thứ tự gọi vào 1 list, assert `mineru` gọi trước `pdf2zh` và
  `job.ocr_confidence` được set đúng giá trị mock trả về.
- `test_run_job_does_not_call_mineru_for_pdf_digital` — job `pdf_digital` với
  `mineru_runner` được inject: assert `parse_document` KHÔNG BAO GIỜ được await,
  `job.ocr_confidence` vẫn `None`.

Verify sống qua `uvicorn` thật: dựng 1 HTTP server giả lập MinerU (`http.server`, trả
`{"markdown": ..., "confidence_score": 0.88}` cho `POST /ocr`) tại `localhost:8010` (khớp
default `mineru_endpoint`), upload 1 PDF scan-like (không text layer, detect đúng
`pdf_scan`), tạo job translate → job fail ở bước `pdf2zh` subprocess như dự kiến (máy dev
chưa cài `pdf2zh` binary, KHÔNG phải lỗi mới), nhưng `SELECT ocr_confidence FROM jobs`
trả về đúng `0.88` — xác nhận MinerU ĐÃ được gọi và chạy XONG trước khi job đi tới bước
pdf2zh, khác hẳn hành vi cũ (OCR bị bỏ qua hoàn toàn, im lặng).

### Bug #3 — AC-12.2 (duplicate file hash detection) [ĐÃ SỬA — backend đầy đủ, frontend UI cơ bản]

**Quyết định thiết kế — vị trí check**: đặt trong `POST /api/jobs` (không phải
`POST /api/upload`), vì hash một mình chưa đủ để coi là "trùng bản dịch cũ" — job phải
CHẠY XONG (`status == "completed"`) với hash đó thì mới có kết quả cũ đáng để hỏi user
dùng lại. Upload lại cùng 1 file trong lúc job trước đó cho hash đó vẫn đang
`translating`/đã `failed` không nên bị chặn — user vẫn cần tạo job mới bình thường.

**Quyết định thiết kế — response shape**: KHÔNG đổi shape hiện có của `JobCreateResponse`
(`job_id: str`, `status: str`) — chỉ THÊM field optional `duplicate_of:
DuplicateJobInfo | None = None` (`{job_id, completed_at}`). Khi phát hiện trùng: trả
`status="duplicate_found"`, `job_id` = id của job CŨ đã completed (không phải job mới —
vì không có job mới nào được tạo), HTTP status `200` (không phải `202` mặc định của route
— không có gì được "accepted" để xử lý nền, trả 202 sẽ gây hiểu lầm). Client cũ chỉ đọc
`job_id`/`status` mà bỏ qua `duplicate_of` vẫn nhận được 1 job_id dùng được (job cũ) thay vì
lỗi hoặc field thiếu.

Thêm `force: bool = False` vào `JobCreateRequest` — client set `true` để bỏ qua check và
luôn tạo job mới (dùng khi user chọn "dịch lại" ở dialog confirm).

`_find_completed_duplicate()` (mới, `src/api/routes/jobs.py`): query `Job` có cùng
`file_hash` và `status == "completed"`, lấy bản mới nhất theo `completed_at`. Gọi ngay đầu
`create_job()`, trước khi tạo `Batch`/`Job` row nào — nếu trùng, return sớm, không tạo gì
cả, không schedule background task nào.

**Phạm vi**: chỉ áp dụng cho `POST /api/jobs` (job đơn lẻ). CHƯA áp dụng cho
`POST /api/batches` (`create_batch()`) — batch có nhiều file cùng lúc, UX "hỏi từng file 1
trong 1 batch" phức tạp hơn nhiều so với 1 confirm() đơn giản, và không có trong 46 test
case QA đã liệt kê. **TODO cho fix round sau** (không tự ý mở rộng phạm vi round này): xem
xét cùng logic duplicate-check cho batch, hoặc để nguyên và document rõ trong PRD rằng
AC-12.2 chỉ áp dụng luồng single-file.

**Frontend** (`web/js/app.js`, `createJob()`): dùng `confirm()` built-in đúng như chỉ đạo
(không làm custom modal). Khi response có `status === "duplicate_found"`: hiện confirm
"File nay da duoc dich vao [ngày]. Nhan OK de dich lai, Cancel de dung ket qua cu." — OK
→ gọi lại `createJob(f, force=true)`; Cancel → gán `f.job` trỏ tới job cũ (`completed`,
100%) để UI hiện luôn nút download cho kết quả có sẵn.

Test mới:
`tests/integration/test_upload_and_job_flow.py::test_create_job_reports_duplicate_of_completed_job_with_same_hash`
— upload file A, tạo job, set `completed` thẳng trong DB (mô phỏng job đã hoàn thành thật),
upload lại CHÍNH file A (file_id mới, hash giống hệt), verify `POST /api/jobs` trả
`duplicate_of.job_id` đúng bằng job đầu tiên; verify thêm `force: true` bỏ qua check và tạo
job mới thật.

Verify sống qua `uvicorn` thật: upload file thật → tạo job `parse_only` → set `completed`
trực tiếp qua `sqlite3` (mô phỏng 1 job translate thật đã hoàn thành, vì máy dev không có
`pdf2zh`) → upload lại CHÍNH file đó → `POST /api/jobs` trả `200`,
`{"status":"duplicate_found","duplicate_of":{"job_id":"<job cu>","completed_at":"..."}}` —
đúng job cũ. Gọi lại với `"force":true` → `202`, tạo job MỚI (job_id khác).

### Thay đổi hạ tầng đi kèm

- `.env.example`: thêm `MINERU_ENDPOINT=http://localhost:8010`.
- `docker/docker-compose.yml`: service `app` thêm
  `MINERU_ENDPOINT=${MINERU_ENDPOINT:-http://mineru:8010}`.

### Kết quả verify

- `uv run ruff check src/`: All checks passed (2 warning ban đầu về import order tự động
  fix bằng `ruff check --fix`, không phải lỗi logic).
- `uv run pytest tests/ -v`: **128 passed** (123 cũ + 5 test mới: 1 cho Bug #1 unit-level,
  1 cho Bug #1 integration-level, 2 cho Bug #2, 1 cho Bug #3).
- `python -c "from src.api.main import app"`: OK.
- Verify sống qua `uvicorn` thật cho cả 3 bug (không chỉ tin unit test) — chi tiết ở từng
  mục bug phía trên. Dùng 1 fake HTTP server nhỏ (`http.server`) đóng vai MinerU cho Bug #2
  vì máy dev không có Docker MinerU container chạy sẵn — hợp lý vì mục tiêu verify là "API
  có gọi MinerU đúng thời điểm không", không phải "MinerU OCR thật có chính xác không"
  (nằm ngoài scope bug này).

### Chưa xử lý / TODO (ghi rõ, không tự ý mở rộng phạm vi)

- Bug #4 (Docker `DATABASE_URL` mismatch) — theo đúng khuyến nghị QA, để lại cho fix round
  sau, không chặn release.
- AC-12.2 duplicate-check cho `POST /api/batches` — xem mục "Phạm vi" ở Bug #3.
- Traceback `ERROR` level cho exception đã biết trước (EPUB, DeepL reject) — QA note
  non-blocking #2, chưa đụng tới trong round này (ngoài phạm vi 3 bug được giao).

## MinerU Rewrite (Protocol 5 fix)

Viết lại hoàn toàn `src/services/mineru_runner.py` theo Architecture.md section 6.9
(Tech Lead đã research trực tiếp source code MinerU thật và ghi lại contract đã VERIFIED —
xem CLAUDE.md Protocol 5 mục 2 để biết bối cảnh sự cố).

### Contract cũ (Increment 2) — SAI, không bao giờ chạy được với MinerU thật

- Endpoint `POST /ocr` — **không tồn tại**. MinerU thật là `POST /file_parse` (sync) hoặc
  `POST /tasks` + poll `GET /tasks/{id}` + `GET /tasks/{id}/result` (async).
- Field upload `file` (số ít) — thật ra là `files` (số nhiều, `list[UploadFile]`).
- Response top-level `markdown` + `confidence_score` bắt buộc — **không có field nào trong
  số đó**. Nội dung nằm ở `results[<file_name>]["md_content"]`; MinerU **không** trả bất kỳ
  điểm confidence nào ở bất kỳ cấp nào của response.
- `images` là list object có `data_hex`, decode bằng `bytes.fromhex()` — thật ra là
  **dict** `{filename: "data:<mime>;base64,<...>"}`, phải tách sau dấu phẩy rồi
  `base64.b64decode()`. `bytes.fromhex()` với data thật sẽ luôn `ValueError`.
- Timeout mặc định 300s (`mineru_timeout_seconds`) — không đủ cho 1 file scan thật
  (200-500 trang có thể mất 15-25 phút OCR).
- `confidence_score` thiếu → cũ `raise MinerUError` — sai cả kỹ thuật (field không tồn tại)
  lẫn nghiệp vụ (không có span nào qua OCR là trạng thái hợp lệ, không phải lỗi).

### Contract mới — đã verify trực tiếp trên source code MinerU (Architecture.md 6.9.1, S1-S9)

- **Async task flow bắt buộc**: `POST /tasks` (multipart, `files`, `backend=pipeline`,
  `lang_list=en`, `parse_method`, `return_md/return_images/return_middle_json=true`) → 202
  `{task_id}` → poll `GET /tasks/{task_id}` (2s → x1.5 → cap 15s, tổng ≤
  `mineru_task_timeout_seconds`, mặc định 3600s) đến `status=completed|failed`, `404` = task
  mất → `MinerUError` → `GET /tasks/{task_id}/result`.
- `results` keyed theo **tên file thật**, không phải key cố định —
  `MinerURunner._select_result_entry()` ưu tiên khớp đúng tên, fallback lấy phần tử duy nhất
  nếu dict có đúng 1 entry, ngược lại raise kèm danh sách key thật.
- `images` decode đúng dict base64 data-URI (tách sau dấu phẩy đầu tiên, `base64.b64decode`);
  entry dị dạng → log warning, bỏ qua, không làm hỏng job.
- `middle_json` là **JSON string**, phải `json.loads()` trước khi dùng.
- **`OcrQuality.confidence`**: trung bình có trọng số theo **số span** (không theo ký tự —
  span bị MinerU tự vứt có 0 ký tự nhưng vẫn phải tính vào mẫu số, nếu không sẽ che mất đúng
  tín hiệu cần đo) của mọi span có key `score` trong `middle_json` (đệ quy qua
  `pdf_info[*].preproc_blocks/discarded_blocks[*].lines[*].spans[*]`, kèm cả block lồng nhau
  dạng bảng). Không có span nào có `score` → `confidence = None` — **hợp lệ, không raise
  lỗi**, khác hẳn behavior cũ.
- `MinerUResult` đổi field: `confidence_score: float` (bắt buộc) → `quality: OcrQuality`
  (`confidence: float | None`), thêm `task_id`, `middle_json_path`.
- Thêm `health()` — `GET /health`, raise `MinerUUnavailableError` khi 503/không kết nối
  được — dùng cho startup check và live smoke test Protocol 5 R5-03.
- `config.py`: xoá field DEPRECATED `mineru_timeout_seconds`; dùng
  `mineru_task_timeout_seconds` (3600) + `mineru_request_timeout_seconds` (120), đã có sẵn.
- `src/api/routes/jobs.py::_build_mineru_runner()`: cập nhật theo signature mới của
  `MinerURunner.__init__` (2 timeout riêng thay vì 1).
- `src/core/job_orchestrator.py::run_job()`: `ocr_result.confidence_score` →
  `ocr_result.quality.confidence`, xử lý `None` đúng như thiết kế (không raise, không cảnh
  báo giả — `jobs.ocr_confidence` để NULL).

### Test

- Viết lại toàn bộ `tests/test_mineru_runner.py` (16 test) theo shape response thật
  (`build_result_dict()` — S1): submit trả 202 kèm `task_id`, poll qua nhiều trạng thái,
  `results` keyed theo tên file thật, `images` dict base64 data-URI, `middle_json` là JSON
  string chứa span có `score`. Riêng test cho: `confidence=None` khi không span nào có
  `score`, `confidence=None` khi thiếu hẳn `middle_json` (không raise), `status=failed` từ
  MinerU, task mất (404), timeout, submit lỗi field `files`/`backend=pipeline`, ảnh dị dạng
  bị bỏ qua không làm hỏng job, `results` key ambiguous, `/health` OK/503/connection error.
- `tests/integration/test_job_orchestrator.py::_fake_mineru_runner()` cập nhật theo
  `MinerUResult`/`OcrQuality` mới (trước đó dùng field `confidence_score`/`success` đã xoá).

### Live verification (Protocol 5 R5-02 + R5-03)

PM đã cài `mineru[core]` thật và có `mineru-api` chạy sẵn trên `127.0.0.1:8010` (model
pipeline đã tải xong — `completed_tasks: 1` khi Dev kiểm tra). Dev đã tận dụng để verify
**vượt mức tối thiểu ("chỉ `/health`") được giao**:

1. `GET http://127.0.0.1:8010/health` qua `curl` VÀ qua `MinerURunner.health()` thật (không
   mock) — `{"status":"healthy","version":"3.4.5",...}`. Xác nhận server chạy đúng và
   `/health` đúng shape Architecture.md 6.9.2.
2. **Full live OCR round-trip** qua `MinerURunner.parse_document()` thật với 1 PDF nhỏ tự
   tạo (`fitz`, 1 trang, `parse_method="ocr"`): submit `/tasks` → poll → `/tasks/{id}/result`
   → `task_id="3372d38a-..."`, `markdown` đúng nội dung trang, `quality=OcrQuality(
   confidence=0.986, ocr_span_count=1, dropped_span_count=0,
   source='middle_json_span_scores')`. Xác nhận toàn bộ pipeline thật — submit, poll, parse
   `results[<name>]`, decode `middle_json` string, tính confidence theo span score — hoạt
   động đúng với MinerU thật, không chỉ đúng với mock.

### Kết quả verify

- `uv run ruff check src/ tests/`: All checks passed.
- `uv run pytest tests/ -v`: **141 passed** (140 cũ + 16 test mới cho `mineru_runner.py`, trừ
  đi các test cũ đã bị thay thế hoàn toàn — net +1 so với trước; 1 fixture ở
  `test_job_orchestrator.py` cập nhật theo contract mới, không thêm/bớt test case ở file đó).
- `python -c "from src.api.main import app"`: OK.
- `GET /health` MinerU thật: OK (xem "Live verification" ở trên) — vượt mức yêu cầu tối
  thiểu, có luôn live OCR round-trip thật.

## Bug #5 Fix — OCR-to-Translate Bridge (Protocol 6)

Dev bị user interrupt giữa chừng (ngay trước bước live E2E cuối). Code + test đã hoàn chỉnh
tại thời điểm dừng; PM tự verify sống thay Dev và viết mục CHANGELOG này.

### Root cause
`JobOrchestrator.run_job()` (Increment 4): sau khi gọi MinerU OCR thành công, chỉ lấy
`ocr_result.quality.confidence` để lưu DB — nội dung OCR thật (`markdown_path`, `middle_json`)
bị vứt bỏ. Biến `file_path` (file scan gốc, không text layer) không bao giờ được cập nhật, nên
mọi bước sau (`_extract_full_text`, `_extract_chunk_text`, `pdf2zh_runner.translate_pages`) vẫn
đọc file gốc. pdf2zh không tìm thấy gì để dịch → xuất PDF gần nguyên trạng, báo "completed"
nhưng bản dịch trống rỗng (silent failure, phát hiện bởi QA Vòng 3).

### Giải pháp (Architecture.md 6.10, đã research + thực nghiệm bởi Tech Lead)
- Module mới `src/preprocess/searchable_pdf.py::build_searchable_pdf()` — dựng "searchable
  PDF" làm cầu nối: đọc bbox+text từng span trong `middle_json`, tô trắng (whiteout) đè lên
  bbox chữ gốc, ghi lại text OCR dưới dạng invisible layer (`render_mode=3`) đúng vị trí.
  Guard hệ toạ độ (`page_size` middle_json vs `page.rect` PyMuPDF lệch > 2pt → fail). BR-OCR-02:
  cầu nối tạo ra 0 ký tự → fail ngay tại bước này.
- `JobOrchestrator.run_job()`: gom toàn bộ luồng đọc nội dung sau OCR về **1 biến duy nhất**
  `translation_source_path` — `pdf_digital` giữ nguyên `file_path`, `pdf_scan` = path file cầu
  nối. MỌI lời gọi `_extract_full_text`/`_extract_chunk_text`/`pdf2zh_runner.translate_pages`
  dùng biến này, không dùng `job.file_path` gốc nữa (trừ 3 chỗ cố ý giữ file gốc: đếm trang,
  gọi MinerU OCR, và mặt tiếng Anh của bản song ngữ).
- **BR-OCR-01**: `pdf_scan` job mà `mineru_runner is None` → fail rõ ràng ngay, KHÔNG được
  âm thầm dịch tiếp bằng file gốc (chính là cách Bug #5 xảy ra ban đầu).
- **BR-OCR-03**: sau khi merge xong output cuối, đếm ký tự đọc được — nếu = 0 → job fail thay
  vì báo "completed". Áp dụng cho MỌI file_type, không chỉ scan — lưới an toàn cuối cùng chống
  mọi dạng silent-failure tương tự trong tương lai.
- Wire `ocr_confidence_threshold`: 3 nhánh (`None`/`>=0.80`/`<0.80`) phát `ocr_warning` qua
  WebSocket + field optional trong `JobDetail` response (backward-compatible).

### Breaking schema change
`Job` model thêm 2 cột nullable: `ocr_bridge_path`, `ocr_dropped_spans`. Project chưa có
Alembic — `SQLModel.metadata.create_all()` KHÔNG thêm cột vào bảng đã tồn tại. **Mọi DB dev cũ
(`data/*.db*`) phải xoá để `init_db()` tạo lại schema mới** — PM đã xoá trên máy dev hiện tại
trước khi chạy test cuối.

### Test (Protocol 6 R6-02 áp dụng nghiêm ngặt)
`tests/preprocess/test_searchable_pdf.py` — test bridge module bằng PyMuPDF THẬT (không mock),
verify qua `extract_text()`. `tests/integration/test_job_orchestrator.py` — bổ sung test assert
**giá trị cụ thể** `pdf2zh_runner.translate_pages.assert_called_with(input_path=<bridge_path>)`
(không chỉ `assert_awaited()`), test BR-OCR-01 (MinerU thiếu → `pdf2zh_runner` KHÔNG được gọi),
test BR-OCR-03 (output 0 ký tự → job fail, không phải completed).

### Kết quả verify (PM chạy thay Dev do bị interrupt)
- `uv run ruff check src/`: All checks passed
- Xoá `data/*.db*` cũ, chạy lại: `uv run pytest tests/ -q` → **159 passed** (141 cũ + 18 mới)
- `python -c "from src.api.main import app"`: OK
- **Live verification thật** (MinerU server thật port 8010 + `MinerURunner` + `build_searchable_pdf` thật, KHÔNG mock): tạo PDF scan-like MỚI (nội dung "Macaron shells...", khác mọi lần
  test trước) → OCR thật (`confidence=0.9875`) → dựng cầu nối thật → verify bằng
  `pdfminer.high_level.extract_text()` **chạy trong chính venv của pdf2zh** (công cụ đọc text
  thật pdf2zh dùng nội bộ, không phải giả lập) → trích xuất đúng 100% nội dung: *"Macaron
  shells: almond flour, egg white, sugar. Rest batter 30 minutes before baking at 150C."*
  (94 ký tự, trước đây bug cho ra chuỗi rỗng). Kiểm tra thêm qua `page.get_images()` +
  `page.get_drawings()`: ảnh gốc còn nguyên (1 image), chỉ 2 hình chữ nhật trắng nhỏ phủ đúng
  bbox 2 dòng chữ (không phủ trắng toàn ảnh) — đúng thiết kế whiteout có phạm vi, không phải
  xoá sạch nội dung trực quan.
- Chưa test được luồng dịch LLM thật đầu-cuối (máy dev chỉ có API key giả) — đây là giới hạn
  đã biết từ trước, không phải phạm vi bug này.

## Increment 6 — UX & Model Management

Dev: sửa 6 vấn đề UX/tính năng do user (Bích Bống) phát hiện khi dùng app thật để dịch 1 cuốn
sách 415 trang. Không đổi kiến trúc pipeline dịch (job_orchestrator, pdf2zh, MinerU) — toàn bộ
thay đổi nằm ở tầng API mới/mở rộng + frontend.

### Bug #6 (ưu tiên cao nhất) — Estimate cost / mất trạng thái / thiếu nút Download

**1a. `estimateCost()` âm thầm tạo job thật — ROOT CAUSE**

`web/js/app.js::estimateCost(f)` (dòng 109-120 cũ) gọi `this.createJob(f)` khi file chưa có
`job` gắn sẵn, để lấy `job_id` cho `GET /api/jobs/{id}/cost-estimate`. Nhưng `createJob()` gọi
`POST /api/jobs`, và `POST /api/jobs` — đúng theo thiết kế đã chốt từ Increment 5 — LUÔN
`_schedule_background(_run_job_background(job.id))` ngay khi tạo `Job` thành công, không có
trạng thái "đã tạo nhưng chưa chạy" nào để user confirm trước. Kết quả: bấm "Xem chi phí ước
tính" vô tình trigger dịch thật ngay lập tức — đúng như user quan sát (status nhảy thẳng sang
`translating`), và vi phạm PRD R-01 ("hiển thị estimated cost TRƯỚC KHI dịch").

Fix: thêm `POST /api/estimate` (`src/api/routes/jobs.py`, router mới `estimate_router`, mount
tại `/api/estimate` trong `src/api/main.py`) — nhận `{file_id, provider, output_mode}`, đọc
metadata upload qua `resolve_upload()` (đã có từ Increment 5, không đổi), gọi thẳng
`estimate_job_cost()` (`src/core/cost_estimator.py`, không đổi) qua `ProviderFactory.create()`
— **không đụng tới `JobOrchestrator`, không tạo `Job`/`Batch` row nào**. Verify bằng test
(`tests/integration/test_estimate_and_cancel_api.py::test_estimate_does_not_create_job_row`)
đếm trực tiếp số row bảng `jobs` trước/sau khi gọi (0 → 0), và verify sống qua `curl` thật
(xem "Kết quả verify" bên dưới). `web/js/app.js::estimateCost()` sửa lại gọi endpoint mới thay
vì `createJob()`.

**1b. Mất trạng thái khi chuyển tab**

`index.html`/`glossary.html`/`history.html` là static multi-page site (không SPA) — chuyển
trang là full page reload, Alpine `x-data` không persist gì. Fix:
- `src/api/routes/jobs.py::list_jobs()` — `status` query param nay chấp nhận DANH SÁCH cách
  nhau bởi dấu phẩy (`?status=queued,translating,completed`), dùng `Job.status.in_(...)` khi có
  nhiều giá trị, giữ nguyên hành vi cũ (`Job.status == status`) khi chỉ có 1 giá trị (không phá
  vỡ `history.js`/`glossary.js` đang gọi kiểu cũ).
- `web/js/app.js::init()` nay gọi `restoreRecentJobs()` — `GET
  /api/jobs?status=queued,chunking,translating,post_processing,merging,completed,cancelled&limit=20`
  ngay khi `index.html` load, dựng lại `this.files` từ response (mỗi `job` JSON đã đủ field
  `JobDetail` cần cho `trackJob()`/progress bar/download link) và gọi `trackJob()` cho từng cái
  để tiếp tục poll/WebSocket. File chỉ có trong session upload hiện tại (chưa tạo job) tất
  nhiên không khôi phục được — đúng giới hạn hợp lý (không có bảng `uploads` DB, chỉ sidecar
  JSON tạm theo `file_id`, xem Increment 5).

**1c. Thiếu nút Download trên trang chính**

Kiểm tra lại `web/index.html` hiện tại: nút "Tải bản VI"/"Tải bản song ngữ" (`/api/jobs/{id}/download`,
`?format=bilingual`) **đã tồn tại sẵn** khi Dev bắt đầu increment này (dòng 95-99 trước khi
sửa), đúng pattern `history.html`. Phân tích ban đầu trong task brief (dựa trên đọc code ở thời
điểm viết brief) không khớp với trạng thái code hiện tại — không rõ đã được thêm ở lần sửa nào
trước đó không ghi vào CHANGELOG, hoặc brief bị đọc nhầm phiên bản. Không có gì để sửa ở mục
này; đã verify link hoạt động đúng qua test hiện có (`test_download_before_completion_returns_404`)
và kiểm tra thủ công response HTML.

### Nhiệm vụ 2 — Chọn model + API key qua UI

- `src/core/config.py` — đổi `openai_model` default `"gpt-4o"` → `"gpt-4o-mini"` (rẻ hơn
  ~16 lần, đủ dùng cho hầu hết trường hợp dịch thuật) — đây chính là nguyên nhân user thấy ước
  tính $3.22 cho 1 cuốn sách. `claude_model`/`deepseek_model`/`gemini_model` giữ nguyên default
  đã có.
- `src/api/routes/settings.py` — `SettingsUpdateRequest` thêm `provider_models: dict[str, str] |
  None`; `SettingsResponse.providers[name]` (`ProviderStatus`) thêm field `model: str | None`
  (`None` cho `deepl` — không có model chọn được, API DeepL cố định). **Không cần sửa
  `src/core/config.py::get_effective_settings()`/`SETTINGS_DB_OVERRIDABLE_FIELDS`** —
  `claude_model`/`openai_model`/`deepseek_model`/`gemini_model` đã nằm trong
  `SETTINGS_DB_OVERRIDABLE_FIELDS` từ Increment 5 (viết cho tương lai, chưa từng có UI dùng
  tới); increment này chỉ thêm field request/response để UI chạm được vào cơ chế override đã
  có sẵn, tái sử dụng nguyên `_upsert_setting()` đã có cho `provider_api_keys`.
- `web/settings.html` + `web/js/settings.js` (MỚI) — trang Settings: chọn `default_provider`,
  `max_concurrent_files`, và với mỗi provider: ô nhập API key (`type=password`, không bao giờ
  hiện lại giá trị đã lưu — chỉ hiện badge "Đã có key"/"Chưa có key" theo đúng `has_key` API đã
  thiết kế từ Increment 5), dropdown chọn model (input text tự do cho riêng `ollama` vì model
  local rất đa dạng tuỳ máy user, không hardcode được danh sách hợp lý). Danh sách model gợi ý
  mỗi provider (`MODEL_OPTIONS` trong `settings.js`): OpenAI `gpt-4o-mini`/`gpt-4o`, DeepSeek
  `deepseek-chat`/`deepseek-reasoner`, Gemini `gemini-2.5-pro`/`gemini-2.5-flash`, Claude chỉ 1
  lựa chọn (model hiện đang hard-code làm default, `claude-sonnet-4-5-20250514`) — không tự bịa
  thêm model Claude khác chưa xác nhận version thật.
- Thêm link "Cài đặt" vào nav bar của cả 4 trang (`index.html`, `glossary.html`, `history.html`,
  `settings.html`).
- `web/index.html`/`web/js/app.js` — dropdown chọn provider cho từng file nay hiện
  `providerLabel(p)` (vd "openai (gpt-4o-mini)") thay vì chỉ tên provider trần, đọc từ
  `GET /api/settings` gọi 1 lần lúc `init()`.

### Nhiệm vụ 3 — Dừng job đang dịch (graceful cancel)

- `src/models/job.py` — thêm cột `Job.cancel_requested: bool = False`. **BREAKING SCHEMA
  CHANGE** — `SQLModel.metadata.create_all()` không thêm cột vào bảng đã tồn tại, mọi
  `data/*.db*` dev cũ phải xoá để `init_db()` tạo lại schema mới (cùng loại thay đổi đã xảy ra ở
  Increment 4 Fix Round 1 và Increment 4 Bug #5 fix — xem 2 mục đó phía trên).
- `src/api/routes/jobs.py::cancel_job()` — `POST /api/jobs/{id}/cancel`: chỉ đặt
  `job.cancel_requested = True` và commit, KHÔNG đổi `job.status` — job vẫn `translating` ngay
  sau khi gọi, cho tới khi chính `JobOrchestrator` tự phát hiện cờ. Reject 400 nếu job đã ở
  trạng thái cuối (`completed`/`failed`/`cancelled` — không có gì để dừng).
- `src/core/job_orchestrator.py::run_job()` — trong vòng lặp per-chunk (Step 7), SAU mỗi lần
  `progress_tracker.update()` (tức là sau khi 1 chunk vừa hoàn thành, kể cả chunk được skip vì
  đã `completed` từ lần chạy trước — BR-CHUNK-05), gọi `await db_session.refresh(job)` rồi kiểm
  tra `job.cancel_requested`. Bắt buộc phải `refresh()` tường minh: session dùng
  `expire_on_commit=False` (xem `src/models/database.py`, không đổi) nên object `job` trong bộ
  nhớ KHÔNG tự thấy write từ 1 session khác (request `POST /.../cancel` chạy trên session HTTP
  riêng) — thiếu `refresh()` sẽ không bao giờ phát hiện được cờ. Khi thấy cờ: đặt
  `job.status = "cancelled"`, commit, broadcast event WebSocket `job_cancelled` (shape mới, cùng
  dạng `job_completed`/`job_failed` — `type`/`job_id`/`completed_chunks`/`total_chunks`, không
  có `error`), **return `JobResult` KHÔNG set `error_message`** (đây là user chủ động dừng,
  không phải lỗi — khác hẳn nhánh chunk-fail ngay phía trên nó set `error_message` rõ ràng).
  Job dừng đúng SAU chunk hiện tại, không force-kill giữa chừng pdf2zh subprocess.
- `src/api/routes/jobs.py::retry_job()` — `_RETRYABLE_STATUSES = {"failed", "cancelled"}` thay
  vì chỉ `"failed"`; khi retry, đặt lại `job.cancel_requested = False` (nếu không, `run_job()`
  chạy lại sẽ đọc thấy cờ cũ còn `True` và dừng ngay sau chunk đầu tiên — bug tự mình tạo ra nếu
  quên bước này). Cơ chế resumable dùng lại NGUYÊN VẸN BR-CHUNK-05 đã có — không cần code mới
  nào để "biết tiếp tục từ đâu", `_load_or_create_chunks()` đã tự skip chunk `status ==
  "completed"`.
- `src/api/routes/jobs.py::JobDetail` — thêm field `cancel_requested: bool` (backward-compatible,
  default `False`) để frontend phân biệt "đang dừng" (`cancel_requested=True`, status vẫn hoạt
  động) với "đã dừng hẳn" (`status == "cancelled"`).
- `web/js/app.js`/`web/index.html` — nút "Dừng" hiện trên file card khi job đang ở trạng thái
  hoạt động (`queued`/`chunking`/`translating`/`post_processing`/`merging`) và chưa
  `cancel_requested`; bấm gọi `POST /.../cancel`, cập nhật `f.job.cancel_requested = true` ngay
  (không đợi backend xác nhận job đã dừng hẳn) — progress bar hiện "Đang dừng (sau khi xong
  chunk hiện tại)..." thay vì %/chunk cho tới khi poll/WebSocket báo `status === "cancelled"`.
  Nút "Thử lại" cũ đổi tên "Tiếp tục dịch", hiện cho cả `failed` VÀ `cancelled`.
  `TERMINAL_STATUSES` (dừng polling) thêm `"cancelled"`.

### Nhiệm vụ 4 — Dịch từng file riêng

`web/js/app.js::createJob(f)` đã tồn tại sẵn từ Increment 5 (dùng bên trong `translateAll()`
cho case 1 file) — không cần thêm logic backend/JS mới. Chỉ thêm 1 nút "Dịch" trên MỖI file
card trong `web/index.html` (cạnh nút "Xem chi phí ước tính"), gọi thẳng `createJob(f)` cho
đúng file đó, độc lập hoàn toàn với nút "Dịch tất cả" (giữ nguyên, vẫn dùng
`POST /api/batches` khi ≥2 file).

### Nhiệm vụ 5 — Glossary phân trang UI

`GET /api/glossary` backend đã hỗ trợ `limit`/`offset` từ Increment 2, không cần sửa backend.
`web/js/glossary.js` — thay hardcode `limit: 200, offset: 0` bằng state `limit`/`offset` thật
(`changePageSize()`, `prevPage()`, `nextPage()`), theo đúng pattern `history.js` đã có sẵn.
`web/glossary.html` — thêm dropdown chọn page size (25/50, mặc định 25 — brief yêu cầu), nút
"Trước"/"Sau" (disable đúng biên, giống `history.html`), hiển thị "X-Y / tổng Z entries" thay vì
chỉ "Z entries" trần.

### Nhiệm vụ 6 — Lưu provider/model + API key đã chọn lần trước

- API key: xác nhận `PUT /api/settings` (Increment 5, không đổi logic) ghi vào bảng `settings`
  DB thật, không phải localStorage — verify qua test hiện có + test mới
  (`test_put_provider_models_overrides_effective_settings`) đọc lại qua
  `get_effective_settings()` sau khi PUT, không chỉ tin response echo lại.
- Provider/output_mode đã chọn lần trước: `web/js/app.js::handleFiles()` đọc
  `localStorage.getItem('bb_last_provider')`/`'bb_last_output_mode'` để điền sẵn dropdown cho
  file MỚI upload (thay vì luôn về `availableProviders(fileType)[0]`/`"monolingual"`); hàm mới
  `rememberChoice(f)` (gọi từ `@change` của 2 dropdown trong `index.html`) ghi lại localStorage
  mỗi khi user đổi lựa chọn. Không thêm bảng DB mới — đúng quyết định đã chốt trong brief (app
  1-user local, không cần đồng bộ đa máy).

### File đã sửa/tạo

**Backend**
- `src/models/job.py` — cột mới `cancel_requested` (BREAKING SCHEMA CHANGE, xem trên).
- `src/core/config.py` — `openai_model` default đổi sang `gpt-4o-mini`.
- `src/api/routes/jobs.py` — router mới `estimate_router` (`POST /api/estimate`), `list_jobs()`
  hỗ trợ multi-status, `retry_job()` chấp nhận `cancelled`, endpoint mới `cancel_job()`,
  `JobDetail`/`CostEstimateResponse`/`EstimateRequest`/`CancelResponse` (model mới/mở rộng).
- `src/api/routes/settings.py` — `_PROVIDER_MODEL_FIELDS`, `ProviderStatus.model`,
  `SettingsUpdateRequest.provider_models`, xử lý trong `update_settings_endpoint()`.
- `src/core/job_orchestrator.py` — cancel check trong `run_job()` (Step 7), helper
  `_broadcast_job_cancelled()`.
- `src/api/main.py` — mount `jobs.estimate_router` tại `/api/estimate`.

**Frontend**
- `web/js/app.js` — `init()` async gọi `loadProviderSettings()` + `restoreRecentJobs()`,
  `estimateCost()` viết lại dùng `/api/estimate`, `cancelJob()` mới, `retryJob()` reset
  `cancel_requested`, `rememberChoice()` mới, `providerLabel()` mới, `isCancellable()` mới,
  `TERMINAL_STATUSES`/`statusBadgeClass` thêm `cancelled`, `trackJob()` xử lý thêm
  `job_cancelled` WebSocket event.
- `web/index.html` — nút "Dịch" riêng/file, nút "Dừng", hiển thị "Đang dừng...", link nav
  "Cài đặt", dropdown provider hiện kèm model.
- `web/settings.html`, `web/js/settings.js` — MỚI (Nhiệm vụ 2).
- `web/glossary.html`, `web/js/glossary.js` — phân trang thật (Nhiệm vụ 5), link nav "Cài đặt".
- `web/history.html`, `web/js/history.js` — link nav "Cài đặt", filter/badge `cancelled`.

**Test**
- `tests/integration/test_job_cancel.py` (MỚI, 3 test) — cancel giữa chừng (mock pdf2zh runner
  tự đặt `cancel_requested=True` qua session RIÊNG sau chunk đầu, mô phỏng đúng race điều kiện
  thật của 1 request HTTP khác), resumable sau cancel (giống hệt pattern test resumable-sau-fail
  đã có ở Increment 4), no-regression (cancel không set thì chạy y hệt trước).
- `tests/integration/test_estimate_and_cancel_api.py` (MỚI, 8 test) — `/api/estimate` không tạo
  Job row (đếm row trực tiếp trước/sau, không chỉ tin response), 404 file không tồn tại, 400
  EPUB; `/api/jobs/{id}/cancel` set cờ không đổi status ngay, reject job đã terminal, 404 job
  không tồn tại; `/api/jobs/{id}/retry` chấp nhận `cancelled` + reset cờ, vẫn reject job đang
  chạy.
- `tests/integration/test_settings_api.py` (MỚI, 4 test) — default `openai_model` đúng
  `gpt-4o-mini`, `GET /api/settings` trả đúng model hiện tại/provider, `PUT
  .../provider_models` override thực sự phản ánh qua `get_effective_settings()` (không chỉ
  response echo), tên provider lạ bị bỏ qua an toàn (không crash, không tạo `Setting` row rác).

### Kết quả verify
- `uv run ruff check src/ tests/`: All checks passed
- `uv run pytest tests/ -q`: **174 passed** (159 cũ + 15 mới: 3 cancel orchestrator + 8
  estimate/cancel API + 4 settings API)
- `python -c "from src.api.main import app"`: OK
- **Verify sống qua `uv run uvicorn src.api.main:app`** (DB `tmp` riêng, không đụng `data/` thật
  của máy dev):
  - Upload PDF 3 trang thật → `POST /api/estimate {file_id, provider:"ollama"}` → 200,
    `total_pages:3`, `estimated_cost_usd:0.0` (ollama free) → `GET /api/jobs` → `total:0` CẢ
    TRƯỚC LẪN SAU khi gọi estimate — xác nhận đúng root cause đã fix, không còn tạo Job ẩn.
  - `GET /api/settings` → `providers.openai.model == "gpt-4o-mini"` (default mới),
    `providers.deepl.model == null` (đúng thiết kế — DeepL không có model chọn được),
    `providers.ollama.has_key == true` (do `ollama_endpoint` có default non-empty sẵn trong
    `.env`/`Settings`).
  - `GET /index.html`, `/glossary.html`, `/history.html`, `/settings.html` → 200 (trang Settings
    mới serve đúng qua `StaticFiles`, không cần route riêng).
  - `POST /api/jobs/does-not-exist/cancel` → 404.
  - Dọn dẹp: xoá toàn bộ thư mục verify tạm sau khi xong, không để lại state trong repo.
- Chưa verify được cancel giữa 1 job dịch LLM thật đang chạy (cần API key thật + pdf2zh/MinerU
  Docker thật để có 1 job chạy đủ lâu nhiều chunk trên máy dev) — cơ chế đã verify đầy đủ ở
  cấp `JobOrchestrator` (test thật, không mock DB session) và cấp API (set cờ đúng, reject đúng
  trạng thái); phần còn lại là "job thật có tự dừng đúng lúc không" — nên coi đây là 1 hạng mục
  QA cần re-verify khi có Docker + API key thật trên máy khác, theo đúng tinh thần Protocol 5
  R5-03/CLAUDE.md.

## Bug #7+#8 Fix (Protocol 5 — golden-file verified)

Fix cho 2 bug QA Vòng 5 phát hiện (`docs/test-report.md` mục "QA Vòng 5"). Circuit breaker
Dev↔QA: vòng 5/5.

### Bug #7 [BLOCKING] — `chunk_merge.py` giả định sai shape output của pdf2zh

**Bước 1 — Golden-file thật (BẮT BUỘC trước khi sửa code, Protocol 5 R5-02)**:

- `pdf2zh` đã cài local (`v1.9.11`, `uv tool install`, binary tại
  `~/.local/share/uv/tools/pdf2zh/bin/pdf2zh`).
- Tạo file nguồn `6page.pdf` (6 trang, mỗi trang 1 câu ngắn khác nhau) bằng PyMuPDF.
- Chạy pdf2zh THẬT 2 lần, mô phỏng đúng overlap logic của `calculate_chunks()`:
  ```
  pdf2zh 6page.pdf -li en -lo vi -s google --pages 1-3 --output out_range1
  pdf2zh 6page.pdf -li en -lo vi -s google --pages 3-6 --output out_range2
  ```
  (dùng `-s google` — Google Translate miễn phí, không cần API key, tránh tốn tiền LLM thật
  chỉ để verify shape output).
- **Quan sát thật** (verify bằng PyMuPDF `get_text()` từng trang):
  - `out_range1/6page-mono.pdf` có **6 trang** (= toàn bộ tài liệu gốc, KHÔNG PHẢI chỉ 3
    trang của range `1-3`): trang 1-3 đã dịch sang tiếng Việt, trang 4-6 vẫn giữ nguyên
    tiếng Anh gốc.
  - `out_range2/6page-mono.pdf` cũng **6 trang**: trang 1-2 vẫn tiếng Anh gốc, trang 3-6 đã
    dịch.
  - Xác nhận đúng root cause QA Vòng 5 đã trace: `pdf2zh --pages A-B` luôn trả về **toàn bộ**
    tài liệu gốc, chỉ dịch đúng phạm vi `--pages` yêu cầu, các trang khác giữ nguyên ngôn ngữ
    nguồn.
- Golden-file lưu tại `tests/fixtures/pdf2zh/` (`6page_source.pdf`,
  `6page_range1-3_mono.pdf`, `6page_range3-6_mono.pdf`) kèm `README.md` ghi rõ lệnh đã chạy,
  version, ngày tạo, bảng quan sát từng trang — để verify lại được khi đổi version pdf2zh
  (Protocol 5 R5-05).

**Bước 2 — Sửa `merge_chunk_pdfs()`** (`src/postprocess/chunk_merge.py`):

- Logic cũ cắt theo **offset trong file chunk** (`skip_pages` tính từ trang 0 của
  `chunk_doc`, giả định `chunk_doc.page_count` == số trang riêng của chunk) — sai vì mono.pdf
  luôn chứa toàn bộ tài liệu gốc.
- Logic mới cắt theo **số trang tuyệt đối trong tài liệu gốc**: `actual_start = page_start`
  (chunk đầu) hoặc `overlap_end + 1` (chunk sau, bỏ phần overlap-context), `actual_end =
  page_end`. Vì mono.pdf's trang N (0-index N-1) luôn tương ứng đúng trang N của tài liệu
  gốc, `from_page = actual_start - 1`, `to_page = min(page_end, chunk_doc.page_count) - 1`.
- Kết quả: merge 3 chunk theo đúng kịch bản QA Vòng 5 (81 trang, chunks `[1-40]`, `[39-80]`,
  `[79-81]`) ra đúng **81 trang**, không phải 239.

**Bước 3 — Viết lại test** (`tests/test_chunk_merge.py`, KHÔNG dùng mock cũ):

- Mock mới (`_make_full_doc_mono_pdf`) mô phỏng đúng hành vi thật: mỗi "chunk mono.pdf" giả
  lập chứa **toàn bộ N trang** tài liệu gốc (tag "translated"/"original" theo đúng range đã
  yêu cầu), không chỉ riêng phạm vi chunk — đúng shape đã verify ở Bước 1.
- Thêm test case `test_merge_chunk_pdfs_golden_shape_three_chunks`: tái tạo chính xác kịch
  bản QA Vòng 5 (81 trang, 3 chunk `[1-40]`/`[39-80]`/`[79-81]`) → assert merge ra đúng 81
  trang, đúng thứ tự nội dung.
- Thêm test case `test_merge_chunk_pdfs_golden_fixture_real_pdf2zh_output` dùng TRỰC TIẾP 2
  file golden-file thật (`tests/fixtures/pdf2zh/6page_range*_mono.pdf`) làm input, không phải
  mock — assert nội dung merge đúng tiếng Việt ở đúng vị trí, không còn sót trang tiếng Anh
  chưa dịch nào.
- File test cũ đã bị xoá hoàn toàn (mock chunk-scoped sai giả định) và viết lại từ đầu.

**Bug liên quan phát hiện thêm khi fix**: `tests/integration/test_job_orchestrator.py::
_fake_pdf2zh_runner()` (fixture cho test `test_run_job_completes_with_three_chunks`) cũng
dùng đúng giả định sai này (`n_pages=end-start+1`, chunk-scoped). Đã sửa để mở
`input_path` bằng PyMuPDF, đọc `total_pages` thật, và tạo mono.pdf với đủ `total_pages` trang
— khớp đúng shape thật đã verify ở Bước 1. Test `test_run_job_completes_with_three_chunks`
(90 trang, 3 chunk) giờ pass đúng với `merged.page_count == 90`.

### Bug #8 [NON-BLOCKING, sửa cùng lần này] — Giá OpenAI tính sai theo model

- `src/services/openai_provider.py`: thêm bảng giá `_PRICING_PER_MTOK` (dict model →
  (input_per_mtok, output_per_mtok)), gồm `gpt-4o` ($2.5/$10) và `gpt-4o-mini` ($0.15/$0.60,
  nguồn: OpenAI pricing page, tham khảo lúc viết code — có thể đổi theo thời gian).
  `estimate_cost()` giờ đọc `self._model` qua `_cost_per_mtok()` để chọn đúng bậc giá, fallback
  về giá `gpt-4o` cho model chưa có trong bảng (thay vì hardcode 1 model duy nhất).
- `DeepSeekProvider` (subclass) không bị ảnh hưởng — đã tự override `estimate_cost()` với
  hằng số giá riêng của nó từ trước.
- Test mới `tests/test_openai_provider.py`: verify đúng giá cho cả `gpt-4o` và `gpt-4o-mini`,
  verify tỉ lệ chênh lệch đúng 2.5/0.15 (khớp con số 16.67x QA Vòng 5 đã đo thực tế), verify
  fallback cho model lạ, verify 0 token → $0. Không cần gọi API thật (thuần logic tính toán,
  theo đúng chỉ đạo).

### Verify

- `uv run ruff check src/`: **All checks passed**.
- `uv run pytest tests/ -q`: **180 passed**, 0 failed, không có test nào bị skip/xfail ẩn.
- `uv run python -c "from src.api.main import app"`: OK.
- Golden-file thật: `tests/fixtures/pdf2zh/` (`6page_source.pdf`, `6page_range1-3_mono.pdf`,
  `6page_range3-6_mono.pdf`, `README.md` — lệnh pdf2zh chính xác đã chạy, version, ngày tạo,
  bảng quan sát từng trang).

## Cost Safety — Lớp 0-3 (sau sự cố $6.50)

Fix theo Architecture.md section 6.11 ("Financial Safety — điều tra sự cố $6.50 và thiết kế
hard spending cap") — sự cố tiền thật ngày 2026-09-04 (job dịch sách "How Baking Works" 415
trang chạy nền bằng `gpt-4o`, tiêu hết $6.50 credit thật ở khoảng trang 270/415, không ai để ý
vì không có bất kỳ cơ chế chặn chi tiêu nào). Implement Lớp 0-3 theo đúng thứ tự Architecture.md
6.11.8. **Lớp 4 (`LLMMeteringProxy`, đo chi phí thật qua proxy) để lại cho increment riêng —
không nằm trong phạm vi lần này.**

### Lớp 1 — `estimate_job_cost_v2()` (`src/core/cost_estimator.py`)

- Thêm `CHARS_PER_TOKEN_VI = 2.0` và `VI_CHAR_EXPANSION = 1.16` — đo trực tiếp từ cache pdf2zh
  thật backing sự cố (Architecture.md 6.11.2, S1), không phải hằng số suy đoán.
- Thêm `estimate_job_cost_v2(source_text_chars, segment_count, prompt_overhead_chars, provider)`
  — thay thế `estimate_job_cost()` cho MỌI call site thật. `estimate_job_cost()` cũ (heuristic
  `AVG_INPUT_TOKENS_PER_PAGE=500` — gốc RC-2, sai thấp 8.4 lần) **giữ nguyên không xoá** để
  tương thích ngược, nhưng đã đánh dấu DEPRECATED trong docstring và không còn được gọi ở bất
  kỳ route API nào.
- Tách `_estimate_input_tokens()` làm hàm lõi dùng chung giữa `estimate_chunk_cost()` (không
  đổi logic, đúng như chỉ đạo — chỉ refactor phần input-token thành gọi hàm chung) và
  `estimate_job_cost_v2()`, đúng yêu cầu Architecture.md 6.11.4 điểm 3 ("2 công thức song song
  → Reviewer reject").
- `src/core/prompt_builder.py`: tách `build_prompt_text()` ra khỏi `write_prompt_file()` — cho
  phép đo `prompt_overhead_chars` từ prompt THẬT có glossary đã lọc cho tài liệu, không dùng
  hằng số cố định (Protocol 6 R6-01: data lineage tường minh, Architecture.md 6.11.5 bước 2→4).
- `src/core/cost_gate.py` (mới): `estimate_translation_cost()` — nối đúng chuỗi lineage
  upload → `_extract_full_text()` → `build_prompt_text()` (glossary đã lọc) →
  `_count_text_segments()` → `estimate_job_cost_v2()`, dùng chung cho `/api/estimate`,
  `/api/jobs/{id}/cost-estimate`, và pre-flight gate (Lớp 2).
- **Golden-file test bắt buộc** (`tests/test_cost_estimator.py::
  test_estimate_job_cost_v2_never_underestimates_golden_incident`), dùng
  `tests/fixtures/pdf2zh/cost_golden_howbakingworks.json`: `segment_count` dùng
  `requests_openai_billed` (2,989, số request OpenAI thực tế tính tiền, gồm cả retry) thay vì
  `requests_cached` (2,941) — vì đây mới là con số `_count_text_segments()` cần xấp xỉ trước
  job. Kết quả: tổng token ước tính = **1.009×** số token thật (1,548,096) — nằm đúng trong
  khoảng bắt buộc [1.0×, 1.6×], không bao giờ ước thấp.
- `GET /api/jobs/{id}/cost-estimate` và `POST /api/estimate` (`src/api/routes/jobs.py`): route
  sang `estimate_job_cost_v2()` qua `cost_gate.estimate_translation_cost()`. Response thêm
  `estimated_segment_count` và `estimated_cost_usd_high` (= 2× estimate, dùng cho Lớp 0).

### Lớp 2 — Pre-flight gate (`src/core/cost_gate.py`, `src/api/routes/jobs.py`)

- `src/core/config.py`: thêm `max_cost_per_job_usd` (default $2.00), `max_cost_per_batch_usd`
  (default $5.00), `cost_cap_enabled` (default `True`) — cả 3 thêm vào
  `SETTINGS_DB_OVERRIDABLE_FIELDS`, expose qua `PUT /api/settings` (`src/api/routes/settings.py`
  — thêm field vào `SettingsUpdateRequest`/`SettingsResponse`).
- `POST /api/jobs`, `POST /api/batches`: gọi `estimate_translation_cost()` + so với ngưỡng
  TRƯỚC KHI tạo `Job`/`Batch` row. Vượt ngưỡng và không có `confirm_cost=true` → **HTTP 402**,
  body `{"detail": {"detail": ..., "estimated_cost_usd": X, "cap_usd": Y,
  "requires_confirmation": true}}`, không tạo row nào, không trigger orchestrator. Batch cap áp
  lên **tổng** ước tính mọi file trong batch (đóng lỗ hổng Architecture.md 6.11.7 #1:
  `max_concurrent_files` chỉ giới hạn số file chạy song song, không giới hạn tiền).
- `confirm_cost: bool = False` trên `JobCreateRequest`/`BatchCreateRequest`/`RetryRequest` —
  opt-in tường minh cho từng request, không bao giờ là mặc định, không được nhớ lại cho lần
  sau. Khi bypass, log `logger.warning(...)` rõ ràng (không im lặng).
- **`POST /api/jobs/{id}/retry` cũng đi qua gate này** — Architecture.md 6.11.7 #2 gọi đích danh
  đây là lỗ hổng ("retry chạy lại không qua gate chi phí"), fix bằng cách gọi
  `estimate_translation_cost()` lại (dùng `job.file_path`, `job.batch_id`,
  `job.cost_cap_usd` nếu có override) trước khi đặt `status="queued"` và schedule background.
  Test riêng: `test_retry_blocked_with_402_when_estimate_exceeds_cap`.

### Lớp 3 — Running cost accumulator + status `cost_capped`

- `src/models/job.py`: thêm `Job.cost_cap_usd: float | None` (override riêng cho từng job,
  `effective_cap = job.cost_cap_usd if set else settings.max_cost_per_job_usd`). Status mới
  `"cost_capped"` — KHÔNG dùng lại `"failed"` (không có lỗi) hay `"cancelled"` (không phải user
  chủ động dừng). **BREAKING SCHEMA CHANGE** — DB dev cũ cần xoá/tạo lại, cùng pattern các
  increment trước.
- `JobOrchestrator.run_job()`: sau mỗi chunk hoàn thành, tại đúng điểm kiểm tra
  `cancel_requested` đã verify sống ở QA Vòng 5 (tái sử dụng, không thêm điểm dừng mới) — tính
  tổng `api_cost` các chunk đã xong, so với `effective_cap`. Vượt → `status="cost_capped"`,
  giữ nguyên các chunk đã dịch, dừng job (không raise lỗi).
- `BatchOrchestrator.run_batch()`: thêm bộ đếm `spent` dùng chung (khoá `asyncio.Lock`) — trước
  khi chạy mỗi file, nếu tổng `actual_cost` các file trước đã vượt `max_cost_per_batch_usd`, file
  đó được đánh dấu `cost_capped` NGAY, không chạy `JobOrchestrator` (file đang chạy dở khi chạm
  trần thì vẫn được chạy hết — không force-kill, cùng triết lý "graceful" với cancel).
- `_RETRYABLE_STATUSES` (`src/api/routes/jobs.py`) thêm `"cost_capped"` — resume đúng cơ chế
  BR-CHUNK-05 sẵn có (chunk `completed` được giữ, chạy tiếp từ chunk dở dang), nhưng **phải qua
  lại Lớp 2 gate** (xem trên).
- **Hạn chế đã ghi rõ (Architecture.md 6.11.4)**: granularity nhỏ nhất của lớp này là 1 chunk
  (40 trang) — 1 chunk đơn có thể tiêu vượt trần trước khi bị chặn. Chỉ Lớp 4 (chưa làm) mới
  chặn được ở granularity từng request.
- **Hạn chế khác chưa xử lý (ghi nhận, không che giấu)**: pre-flight gate (Lớp 2) đo chi phí
  bằng cách trích xuất text từ `file_path` gốc — với file `pdf_scan` (chưa OCR ở thời điểm
  ước tính), text trích ra gần như rỗng, nên gate không chặn được job scan trước khi chạy.
  Lớp 3 (running accumulator) vẫn bảo vệ các job này SAU chunk đầu tiên vì nó dùng chi phí
  thực tế đã tích luỹ, không phụ thuộc ước tính trước job. Mirror đúng lỗ hổng đã ghi nhận ở
  Architecture.md 6.11.7 #3 (OCR chưa được mô hình hoá chi phí, chấp nhận cho v1.0).

### Lớp 0 — UI cảnh báo (`web/index.html`, `web/history.html`, `web/js/app.js`, `web/js/history.js`)

- Ô ước tính chi phí đổi từ 1 số sang **khoảng** `$X – $Y` (`Y = X × 2.0`), kèm câu "đây là
  ước tính, chi phí thật có thể cao hơn".
- Cảnh báo riêng khi model đang chọn là `gpt-4o` (đắt hơn ~16.7× `gpt-4o-mini` — con số đo được
  từ chính sự cố $6.50, Architecture.md 6.11.2).
- Hiện rõ **số đoạn văn (segment) ước tính** sẽ gửi API, không chỉ số trang — kèm giải thích
  "mỗi đoạn văn là 1 request LLM riêng" (điều cả team lẫn user đều không hình dung được trước
  sự cố).
- Nút "Dừng tất cả job" (kill switch) — tái dùng `cancel_requested`/`cancelJob()` đã có, gọi
  loạt cho mọi job đang chạy, không cần endpoint mới.
- Badge + giải thích riêng cho status `cost_capped` (màu tím, phân biệt rõ với `failed`/
  `cancelled`) ở cả `index.html` (theo dõi job) và `history.html` (lịch sử).
- `web/settings.html`/`web/js/settings.js`: thêm mục "Trần chi phí" — bật/tắt
  `cost_cap_enabled`, chỉnh `max_cost_per_job_usd`/`max_cost_per_batch_usd` qua
  `PUT /api/settings`.

### Test mới

- `tests/test_cost_estimator.py` — golden-file test cho Lớp 1 (bắt buộc theo 6.11.6), test hàm
  lõi dùng chung, test formula output/negative-input.
- `tests/integration/test_cost_gate_api.py` — 8 test cho Lớp 2: 402 khi vượt trần (job/batch/
  retry) kèm assert **không có Job/Batch row nào được tạo**, bypass qua `confirm_cost=true`
  (background task bị monkeypatch thành no-op để không chạy pipeline thật).
- `tests/integration/test_cost_capped_orchestrator.py` — 4 test cho Lớp 3: dừng đúng lúc vượt
  trần, resume sau khi tăng trần, `cost_cap_enabled=False` không chặn, override `job.cost_cap_usd`
  có ưu tiên cao hơn setting toàn cục.
- `tests/integration/test_batch_orchestrator.py` — thêm test batch-level cap (file thứ 3 trong
  batch không chạy vì tổng chi phí 2 file trước đã vượt `max_cost_per_batch_usd`).
- `tests/integration/test_settings_api.py` — thêm test GET/PUT cho 3 field cost-cap mới.
- `tests/integration/test_estimate_and_cancel_api.py`: cập nhật fixture `_insert_job()` — dùng
  file PDF thật trên đĩa + provider `ollama` (không cần API key) thay vì đường dẫn giả, vì
  `retry` giờ chạy cost-gate thật (đọc file bằng PyMuPDF).

### Verify

- `uv run ruff check src/ tests/`: **All checks passed**.
- `uv run pytest tests/ -q`: **200 passed**, 0 failed.
- `uv run python -c "from src.api.main import app"`: OK.
- **Không có bất kỳ API call LLM thật nào được gọi trong lúc dev/test** — mọi provider dùng
  trong test đều là `ollama` (free, không cần key) hoặc `claude`/`openai` với API key GIẢ
  (`sk-ant-fake`), chỉ chạm `estimate_cost()` (thuần arithmetic, Architecture.md 6.6.2 R3.1),
  không bao giờ `.translate()`. Mọi test để `confirm_cost=true` lọt qua gate đều monkeypatch
  `_schedule_background` thành no-op để pipeline thật (pdf2zh/LLM) không bao giờ chạy.

## QA Vòng 7 (CUỐI) — Live Cost Cap Verification

Xác nhận sống Cost Safety Lớp 2+3 bằng key DeepSeek thật. Lớp 2: cap đặt dưới estimate đã đo
→ `POST /api/jobs` trả `402`, không tạo Job row, không có request LLM nào gửi đi. Lớp 3:
`confirm_cost=true` bypass Lớp 2, cap đặt dưới `actual_cost` đã biết → job chạy 1 chunk thật
qua DeepSeek rồi tự dừng đúng `status="cost_capped"` (không phải completed/failed/cancelled).
Chi phí thật toàn bộ vòng: **$0.00021437** (~0.02 cent), sâu trong ngân sách. `pytest` 200/200
pass trước và sau live test. Chi tiết đầy đủ: `docs/test-report.md` mục "QA Vòng 7".

---

# v1.0.0 — Release

**Ngày**: 2026-09-04

Pipeline dịch tài liệu ngành bánh (PDF born-digital, PDF scan qua OCR, EPUB) EN→VI, giữ nguyên
layout, hỗ trợ glossary chuyên ngành, đa provider (Claude/OpenAI/Gemini/DeepSeek/DeepL/Ollama),
batch processing, cost safety 4 lớp. Toàn bộ pipeline đã verify sống end-to-end với dữ liệu
thật (MinerU thật, pdf2zh thật, OpenAI/DeepSeek thật) qua 7 vòng QA.

**Known limitations (v1.0, hoãn sang v1.1)**:
- US-15 (Markdown parse-only mode) — API chấp nhận nhưng chưa có nhánh xử lý, fail rõ ràng
- Cost Safety Lớp 4 (đo chi phí thật qua metering proxy) — hiện dùng ước lượng (đã hiệu chỉnh
  chính xác theo dữ liệu thật, luôn ước cao không bao giờ ước thấp), chưa đo token thật 1:1
- Batch-level duplicate detection — chỉ có ở job đơn lẻ
- Tự động đổi tên file theo tên sách — đã đánh giá khả thi, chưa implement
- Dịch theo khoảng trang tuỳ chỉnh — chưa có UI, thiết kế đã hỗ trợ sẵn ở tầng API/chunking

**2 protocol mới bổ sung vào CLAUDE.md trong quá trình build, áp dụng cho mọi phát triển sau
này**: Protocol 5 (External Dependency Verification) và Protocol 6 (Cross-Step Data Lineage
Verification) — xem chi tiết trong `CLAUDE.md`.

---

## Fix: giữ tín hiệu rate-limit khi pdf2zh timeout (Architecture.md 6.12.2/6.12.3)

`Pdf2zhRunner.translate_pages()` trước đây khi timeout thì `kill()` rồi vứt bỏ toàn bộ
stdout/stderr đã sinh ra — không còn cách nào phân biệt "timeout vì bị rate-limit" (cần giảm
concurrency) với "timeout vì đơn thuần chậm" (giảm concurrency lúc này chỉ làm chậm thêm), điều
kiện bắt buộc để AIMD controller (task riêng, chưa implement) hoạt động đúng. Sửa bằng cách đọc
incremental 2 stream song song (`_drain` + `asyncio.wait_for(process.wait(), ...)` thay cho
`communicate()` đơn lẻ, tránh cả mất tín hiệu lẫn deadlock pipe khi log vượt 64KB) và vét buffer
5s sau kill. Đồng thời phát hiện: tín hiệu `RateLimitError` của pdf2zh đi ra **stdout** (không
phải stderr như giả định ban đầu) và bị `rich` wrap cắt đôi ở 80 cột khi không chạy trong TTY —
thêm `COLUMNS=200` vào env mọi provider trong `Pdf2zhServiceMapper` để dòng log không bị cắt, và
định nghĩa bộ đếm `RATE_LIMIT_LINE_RE` (`src/core/concurrency_controller.py`, mới) chỉ neo vào
token `RateLimitError` đơn lẻ thay vì cả cụm dễ bị wrap. `Pdf2zhTimeoutError` và `Pdf2zhResult`
nay mang theo `stdout`/`stderr`/`rate_limit_hits` để bước tiêu thụ (AIMD, task sau) không phải
đoán. Phạm vi lần này KHÔNG bao gồm thuật toán AIMD (6.12.4+).

---

## Feat: thuật toán AIMD cho adaptive concurrency — module logic thuần (Architecture.md 6.12.4/6.12.5)

Thêm `ChunkOutcome`, `classify_chunk_outcome()`, `next_thread_count()`, `ADAPTIVE_THREAD_FLOOR`,
`ADAPTIVE_THREAD_CEILING` vào `src/core/concurrency_controller.py`. Lý do tách riêng khỏi
`_drain`/`RATE_LIMIT_LINE_RE` đã có: đây là bước 4 trong 7 bước implement của 6.12.10, cố tình
viết dưới dạng logic thuần (input `exit_code`/`rate_limit_hits`/`duration_seconds` ->
`ChunkOutcome` -> delta thread, không đụng DB/subprocess) để unit test không cần mock nặng và
không cần golden file — golden file chỉ bắt buộc cho test tích hợp đọc `Pdf2zhResult.stdout`
thật (6.12.9), không áp dụng cho hàm logic thuần này.

`exit_code=None` được dùng làm tín hiệu "đã timeout" thay vì 1 giá trị exit code cụ thể, khớp
với cách `Pdf2zhTimeoutError` được raise trong `pdf2zh_runner.py` (process bị `kill()`, không
có return code thật). Giữ nguyên đúng công thức 6.12.4 (+2 additive/x0.5 multiplicative, không
đổi ngưỡng N>=3, mốc success ở đúng `<= 0.75 * timeout`) và đúng số floor/ceiling 6.12.5
(deepseek=8, openai=8, gemini=4, claude=4, ceiling chung=32) kèm comment ngắn giữ lại lý do từ
Architecture.md để tránh ai đó sau này đổi số mà không biết vì sao.

**CHƯA làm trong lần này** (để task riêng, đúng phạm vi được giao):
- Chưa chạy golden-file spike thật với DeepSeek API (bước 2, 6.12.10).
- Chưa tạo bảng `ConcurrencyState`, chưa nối `job_orchestrator.py` gọi controller thật (bước 3,
  6.12.8) — controller hiện là pure function chưa được wiring vào pipeline.
- Chưa động vào cold-start `chunk_size` (6.12.7) hay Claude/Ollama spike (6.12.6).

Test: `tests/test_concurrency_controller.py` (mới, dạng bảng parametrize đủ 6 outcome + biên
0.75*timeout + clamp floor/ceiling). `pytest tests/ -q` 227 passed, `ruff check` + `ruff format
--check` sạch.

## Bước 2 (6.12.10) — Golden file rate-limit DeepSeek: INCONCLUSIVE

Dev: chạy `pdf2zh` thật (không mock) với DeepSeek (`-s deepseek:deepseek-chat`, đúng service
arg app tự build ở `pdf2zh_service_map.py`), 3 lần thử trong trần chi phí $1 đã duyệt trước
(8-10 trang cắt từ "How baking works", `--thread` 64 → 128 → 256, có `--ignore-cache` từ lần 2).
Không lần nào bắt được dòng khớp `RATE_LIMIT_LINE_RE` — toàn bộ request đều 200 OK. Kết luận
INCONCLUSIVE (đúng nhánh xử lý 6.12.6 mục 6), không phải PASS/FAIL, vì số segment tối đa của
8-10 trang (~97-110) có thể thấp hơn ngưỡng rate-limit thật của DeepSeek bất kể `--thread` cao
tới đâu. Chi phí thực tế ước tính đã tiêu: ~$0.03 USD (tính bằng `estimate_chunk_cost()` +
`DeepSeekProvider.estimate_cost()`, pdf2zh không log token usage thật). Lưu tại
`tests/fixtures/pdf2zh/deepseek_ratelimit/` (`inconclusive_stdout.txt`, `inconclusive_stderr.txt`,
2 file thử trước, `README.md` ghi chi tiết) — KHÔNG dùng làm golden file cho mock 429 thật của
DeepSeek; cần escalate nếu muốn verify tiếp (mở rộng phạm vi trang/chi phí, ngoài phạm vi task
này). Không tự sửa/đoán thêm gì cho AIMD DeepSeek dựa trên kết quả này.

## Bước 2b — Spike gọi thẳng SDK `openai` tới DeepSeek: vẫn INCONCLUSIVE

Dev: đổi cách tiếp cận để né giới hạn "số đoạn văn trong 1 PDF nhỏ" — gọi thẳng
`openai.AsyncOpenAI(base_url="https://api.deepseek.com")` (đúng SDK `OpenAITranslator` của
pdf2zh dùng nội bộ), model `deepseek-chat`, prompt siêu ngắn + `max_tokens=5`, bắn đồng thời
thật bằng `asyncio.gather()` tăng dần 300 → 600 → 1000 → 1500 → 2000 → 2600, dừng đúng khi chạm
trần 8000 request (giới hạn cứng đã duyệt). Không hề gặp `openai.RateLimitError` (429) ở bất kỳ
mức nào; lỗi duy nhất là `openai.APITimeoutError` (client-side timeout, không phải HTTP status)
ở mức 2000 (692/2000) và 2600 (12/2600). Kết luận vẫn INCONCLUSIVE — không xác nhận được ngưỡng
429 thật lẫn hành vi `RateLimitError` cho `deepseek-chat`. Chi phí thực tế ước tính: ~$0.062 USD
(rất xa trần $1). Log đầy đủ lưu tại
`tests/fixtures/pdf2zh/deepseek_ratelimit/direct_sdk_spike.md`. KHÔNG sửa `[UNVERIFIED]` ở
Architecture.md 6.12.1 (S13) / 6.12.10 — floor `deepseek = 8` giữ nguyên, độc lập với con số
này. Script throwaway dùng để chạy spike đã xoá khỏi scratch, không nằm trong repo.

## Bước 3 (6.12.10) — Schema DB + nối AIMD vào `job_orchestrator.py`

Dev: bảng `ConcurrencyState` mới (`src/models/concurrency_state.py`, khoá ghép `(provider,
model)` đúng schema chốt 6.12.8), cột mới `Chunk.thread_used` / `Chunk.rate_limit_hits`
(`src/models/chunk.py`), cột mới `Job.chunk_size_used` (`src/models/job.py`, CHỈ thêm cột —
logic cold-start gán giá trị là task 6.12.7 riêng, ngoài phạm vi lần này). `init_db()`
(`src/models/database.py`) giờ chạy thêm `ALTER TABLE ... ADD COLUMN` (idempotent, dò qua
`PRAGMA table_info`) cho 3 cột mới trên `chunks`/`jobs` — khác quy ước "xoá DB dev cũ" của các
increment cột-mới trước, vì 6.12.8 yêu cầu tường minh ALTER TABLE. Setting mới
(`src/core/config.py`): `adaptive_concurrency_enabled: bool = True` (kill switch, `.env`-only,
KHÔNG vào `SETTINGS_DB_OVERRIDABLE_FIELDS`) và `ollama_thread: int = 2` (ngoại lệ CÓ vào
`SETTINGS_DB_OVERRIDABLE_FIELDS`, đúng 6.12.6 — giá trị đúng phụ thuộc phần cứng máy user, app
không tự suy ra được). `Pdf2zhRunner.translate_pages()` (`src/services/pdf2zh_runner.py`) nhận
thêm tham số `thread: int = 4` và thêm `--thread {thread}` vào argv — trước đây hàm này hoàn
toàn không truyền `--thread`, đây chính là gốc rễ khiến pdf2zh luôn chạy ở mặc định 4 dù
`ConcurrencyState` có học được gì đi nữa.

`JobOrchestrator._process_chunk()` nối AIMD theo đúng vòng đời 1 chunk ở 6.12.4: đọc/tạo
`ConcurrencyState` trước mỗi chunk, ghi `chunk.thread_used` TRƯỚC khi gọi `translate_pages()`
(R6-01), phân loại outcome bằng `classify_chunk_outcome()` có sẵn (kể cả nhánh
`Pdf2zhTimeoutError`/`Pdf2zhError` — bắt riêng để vẫn cập nhật state trước khi re-raise, giữ
nguyên hành vi fail-job hiện có), cập nhật `current_thread` bằng `next_thread_count()` có sẵn,
ghi `chunk.rate_limit_hits` từ đúng `Pdf2zhResult.rate_limit_hits`/`exc.rate_limit_hits` của
CHÍNH lần gọi đó (không tính lại từ `.stderr` — đúng bài học 6.12.2). Ba nhánh đặc biệt theo
6.12.6: `ollama` dùng thẳng `settings.ollama_thread`, không đọc/ghi `ConcurrencyState` nào;
`adaptive_concurrency_enabled=False` dùng `ADAPTIVE_THREAD_FLOOR[provider]` cố định, cũng không
đọc/ghi state (đường lui an toàn); `claude` vẫn đọc/tạo state (để có `current_thread` ổn định
phục vụ debug) nhưng khoá cứng ở floor — không áp dụng additive increase dù outcome là
`success`, vì `[UNVERIFIED]` S6 (6.12.6) chưa xanh.

**Escalation (R5-02), không tự đoán:** pseudocode 6.12.4 đọc `job.model_provider` — field này
KHÔNG tồn tại trong codebase. Field thật là `Job.model`, và nó vốn đã được toàn bộ phần còn lại
của module dùng làm provider identifier (`Pdf2zhServiceMapper.map(job.model, ...)`,
`ProviderFactory.create(job.model, ...)` ở `src/api/routes/jobs.py`) chứ không phải model cụ
thể. Quyết định dùng luôn `job.model` làm nửa `provider` của khoá ghép, và
`service.service_arg` (vd. `"deepseek:deepseek-chat"`) — đã có sẵn trong `_process_chunk()`,
định danh đúng 1 model backend cụ thể cho provider đó — làm nửa `model`, thay vì thêm cột `Job`
mới ngoài phạm vi PHẠM VI của task này. Cần Tech Lead xác nhận lại cách hiểu này khi review.

**CHƯA làm trong lần này** (để task riêng, đúng phạm vi được giao):
- Chưa chạy spike Claude/Gemini thật (6.12.6) — `claude` vẫn khoá floor, `gemini` vẫn AIMD ở
  floor 4 theo đúng trạng thái `[UNVERIFIED]`.
- Chưa implement logic cold-start `chunk_size` (6.12.7) — `Job.chunk_size_used` mới chỉ là cột,
  `run_job()` vẫn dùng `self._chunk_size` như cũ.

Test: `tests/integration/test_job_orchestrator_concurrency.py` (mới) — 6 test theo đúng yêu cầu
R6-02 6.12.9: thread truyền xuống pdf2zh bắt nguồn từ `state.current_thread` (không phải hằng
số); `rate_limit_hits` cập nhật state bắt nguồn từ `Pdf2zhResult.stdout` (2 test, gồm 1 test hồi
quy trực tiếp cho 6.12.2 — `stderr` rỗng, tín hiệu chỉ nằm ở `stdout`); nhánh Claude khoá floor
không tăng dù `success`; nhánh Ollama không tạo/đọc `ConcurrencyState` nào, dùng đúng
`settings.ollama_thread`; nhánh `adaptive_concurrency_enabled=False` dùng floor cố định, không
đọc/ghi state. Fixture rate-limit dùng `tests/fixtures/pdf2zh/richhandler_wrapped/stdout.txt` —
copy NGUYÊN VĂN từ output thật đã verify ở Architecture.md 6.12.2 (S9-S11, RichHandler chạy
thật), gắn nhãn rõ trong code + README.md cùng thư mục: đây KHÔNG phải golden file 429 thật của
DeepSeek (golden file đó vẫn đang INCONCLUSIVE, xem `tests/fixtures/pdf2zh/deepseek_ratelimit/`)
— không được dùng để tuyên bố đã verify hành vi 429 thật. `pytest tests/ -q` 233 passed, `ruff
check` + `ruff format --check` sạch trên toàn bộ file đã sửa/thêm.

## Bước 5 (6.12.10) — `chunk_size` cold-start

Implement 6.12.7: `Job.chunk_size_used` (cột đã có từ bước 3, luôn `None` trước đây) giờ được
chốt ĐÚNG 1 LẦN tại step 6 của `run_job()`, ngay trước `plan_chunks()` — cold (20) trừ khi
`(provider, model)` đã "warm" (`ConcurrencyState.observation_count >= 3` VÀ
`consecutive_successes >= 3`, khi đó 40). `service` đã được map ở step 4 (dòng ~228), nằm trong
scope trước lời gọi `plan_chunks()` ở step 6 (dòng ~264) nên không cần đảo thứ tự code — dùng
lại đúng `provider = job.model`, `model_key = service.service_arg` như bước 3 đã chốt.
`plan_chunks()` giờ nhận `job.chunk_size_used`, không phải `self._chunk_size` — tham số đó chỉ
còn là fallback cho test gọi thẳng helper nội bộ. Resumability: nếu `job.chunk_size_used` đã có
giá trị (job resume), dùng lại y nguyên, không tính lại — đổi giữa chừng sẽ làm
`page_start`/`page_end` đã persist lệch khỏi plan mới, đúng dạng lỗi lineage của Bug #5.

**Escalation (R5-02), không tự đoán:** pseudocode 6.12.7 gọi `controller.get_state(provider,
model, db_session)` VÔ ĐIỀU KIỆN trước `plan_chunks()`. Áp dụng y nguyên sẽ vỡ theo 2 cách đã
xác nhận bằng code thật: (1) `ADAPTIVE_THREAD_FLOOR` (`concurrency_controller.py:34`) KHÔNG có
khoá `"ollama"` — `_get_or_create_concurrency_state()` sẽ `KeyError` khi tạo state mới cho job
Ollama; (2) 6.12.6/6.12.8 đã chốt (và có test xác nhận ở
`test_job_orchestrator_concurrency.py`) rằng nhánh `ollama` và nhánh
`adaptive_concurrency_enabled=False` KHÔNG BAO GIỜ được đọc/ghi `ConcurrencyState`. Đã chọn
guard cùng hình dạng với guard có sẵn trong `_resolve_thread()`: hai nhánh đó nhận thẳng
`COLD_START_CHUNK_SIZE` (20) mà không đọc `ConcurrencyState`, chỉ nhánh AIMD thật (`deepseek`/
`openai`/`gemini`/`claude` khi `adaptive_concurrency_enabled=True`) mới đọc state để quyết định
cold/warm. Cần Tech Lead xác nhận lại cách hiểu này khi review — đây là 1 lựa chọn tránh crash/
vỡ invariant đã test, không phải suy đoán tuỳ tiện, nhưng khác pseudocode nguyên văn.

**Tác dụng phụ lên test cũ:** 4 test đã có từ trước (`test_run_job_completes_with_three_chunks`,
`test_run_job_is_resumable_after_a_chunk_fails` ở `test_job_orchestrator.py`, và 2 test
cancel-flow ở `test_job_cancel.py`) giả định ngầm `chunk_size=40` (qua `self._chunk_size` cũ) để
90 trang chia đúng 3 chunk. Cold-start mặc định giờ là 20 (chia 5 chunk) nên các test này được
sửa để pin `job.chunk_size_used = 40` trước khi chạy — giữ đúng mục đích gốc của chúng (test
resumability/cancellation, không phải test chunk sizing), không đổi assertion nào khác.

Test mới: `tests/integration/test_job_orchestrator_chunk_size_cold_start.py` — 4 test, mỗi test
assert giá trị cụ thể `plan_chunks()` được gọi với (`spy.assert_called_once_with(...)`, dùng
`patch.object` bọc `plan_chunks` thật chứ không mock giả — theo đúng kỷ luật R6-02): (1) chưa có
`ConcurrencyState` -> 20; (2) có state nhưng `observation_count < 3` -> vẫn 20; (3) state đã warm
(`observation_count=5, consecutive_successes=4`) -> job MỚI nhận 40; (4) job đã có
`chunk_size_used=20` từ trước (mô phỏng resume) -> giữ nguyên 20 dù state đã warm lên
`observation_count=10, consecutive_successes=10`, không tính lại.

`pytest tests/ -q` 237 passed (233 cũ + 4 mới), `ruff check` + `ruff format --check` sạch trên
`src/core/job_orchestrator.py`, `tests/integration/test_job_orchestrator_chunk_size_cold_start.py`,
`tests/integration/test_job_orchestrator.py`, `tests/integration/test_job_cancel.py` (23 file
khác trong repo có format lệch từ trước, không liên quan tới thay đổi lần này, không đụng vào).

## Fix: expose `ollama_thread` qua UI Settings + test khoá cho AIMD Gemini (Architecture.md 6.12.6)

Reviewer rà soát 6.12.6 phát hiện 2 điểm chưa xong:

1. `ollama_thread` đã nằm trong `SETTINGS_DB_OVERRIDABLE_FIELDS` từ trước nhưng **chưa được
   expose qua `PUT/GET /api/settings`** — `SettingsResponse`/`SettingsUpdateRequest`
   (`src/api/routes/settings.py`) không có field này, nên dù DB override cơ chế đã sẵn, UI
   không có cách nào gọi tới. Thêm `ollama_thread: int` vào `SettingsResponse`, `ollama_thread:
   int | None` vào `SettingsUpdateRequest`, và xử lý ghi trong `update_settings_endpoint()` —
   cùng pattern với `max_cost_per_job_usd`.
2. UI (`web/settings.html` + `web/js/settings.js`): thêm input số cho `ollamaThread`, chỉ hiện
   khi provider `ollama` có key (`x-show="name === 'ollama' && providers[name]?.has_key"`, bám
   theo pattern `hasModel`/`apiKeyDrafts` có sẵn trong file), kèm helper text đúng nguyên văn đã
   chốt 6.12.6: "Tăng nếu máy có nhiều VRAM; giảm về 1 nếu máy treo."

Test mới: `test_gemini_aimd_increases_on_success`
(`tests/integration/test_job_orchestrator_concurrency.py`) — đối xứng với
`test_claude_locked_at_floor_does_not_increase_on_success` đã có, nhưng khẳng định điều ngược
lại: `gemini` KHÔNG bị khoá AIMD như `claude` (chỉ floor thấp hơn, 4 thay vì 8), nên outcome
`success` phải cộng +2 thật (`state.current_thread == 6`), không chỉ `assert_called()` (R6-02).

`pytest tests/ -q` 240 passed (239 cũ + 1 mới), `ruff check` + `ruff format --check` sạch trên
`src/api/routes/settings.py` và `tests/integration/test_job_orchestrator_concurrency.py`.

## Spike (R5-02) — Claude rate-limit signal qua `openailiked`: FAIL, escalate — chưa unlock AIMD

Thực hiện spike bắt buộc tại Architecture.md 6.12.6 ("Spike test bắt buộc trước khi bật AIMD
cho Claude"): chạy `pdf2zh` thật (không mock) với `-s openailiked:claude-haiku-4-5-20251001`,
`--thread 64`, `COLUMNS=200`, trỏ `OPENAILIKED_BASE_URL=https://api.anthropic.com/v1/`, trên 1
file PDF 10 trang cắt từ "How baking works" (scratchpad, không đụng file gốc, đã xoá sau khi
xong). Dùng model Haiku (rẻ nhất) đúng giới hạn chi phí $1 của task.

**Kết quả: FAIL — không phải vì rate-limit signal sai, mà vì `CLAUDE_API_KEY` trong `.env` là
placeholder không hợp lệ (13 ký tự, không đúng định dạng key Anthropic thật).** Mọi request
tới `api.anthropic.com` bị từ chối ở bước xác thực (`HTTP 401 authentication_error`, 1081
dòng log) trước khi có cơ hội chạm rate limit thật — `grep -c "RateLimitError"` = 0/0 trên cả
stdout và stderr. Không crash tiến trình. Chi phí thực tế: **$0.00** (401 không phát sinh
billing token). Dừng ở 1/3 lần thử: tăng `--thread` lên 128/256 sẽ cho kết quả giống hệt vì
lỗi nằm ở tầng xác thực, xảy ra trước tầng concurrency.

Đã lưu `stdout.txt`, `stderr.txt`, `README.md` (ghi rõ root cause + escalation) vào
`tests/fixtures/pdf2zh/claude_ratelimit_spike/`. **Không** sửa `docs/Architecture.md` (S6,
6.12.1, 6.12.6, 6.12.10 giữ nguyên `[UNVERIFIED]`), **không** sửa
`ADAPTIVE_THREAD_FLOOR["claude"]` hay bỏ khoá AIMD trong `job_orchestrator.py` — Claude giữ
nguyên thread cố định = 4 đúng theo nhánh FAIL của spec. Escalate lên Tech Lead / người dùng:
cần 1 `CLAUDE_API_KEY` thật, hợp lệ để chạy lại spike này.

---

# v1.1.0 — Release

**Ngày**: 2026-09-05

Nội dung chính: **AIMD Adaptive Concurrency Controller** (Architecture.md 6.12) — pdf2zh giờ
nhận đúng flag `--thread` (trước đây không bao giờ được truyền, luôn chạy ở mặc định 4 của
chính pdf2zh dù cấu hình gì đi nữa). Concurrency tự tăng/giảm theo tín hiệu rate-limit thật đọc
từ stdout của pdf2zh (phát hiện tín hiệu nằm ở stdout chứ không phải stderr như giả định ban
đầu), riêng theo từng cặp (provider, model), với floor/ceiling và cơ chế khoá riêng cho
Claude/Ollama. Thêm cold-start `chunk_size` (20 trang cho job đầu, phục hồi 40 sau khi
(provider, model) đã "warm"). Verify sống qua QA Gate Release: job thật 65 trang qua
DeepSeek, `thread_used` tăng đúng luật AIMD qua các chunk, output PDF có nội dung tiếng Việt
mạch lạc thật.

`pyproject.toml` bump `0.1.0` → `1.1.0` (chưa từng được cập nhật khi v1.0.0 release — sai lệch
phát hiện khi làm release lần này, sửa cùng lúc).

**Known limitations mang sang từ v1.0** (chưa xử lý trong release này): US-15 (Markdown
parse-only), Cost Safety Lớp 4 (metering proxy đo token thật), batch-level duplicate
detection, tự động đổi tên file theo tên sách, dịch theo khoảng trang tuỳ chỉnh.

**Riêng của v1.1**: rate-limit detection cho Claude (`openailiked`) và Gemini vẫn
`[UNVERIFIED]` — chưa có `CLAUDE_API_KEY`/`GEMINI_API_KEY` thật để chạy spike xác nhận (xem
`blockers` trong `project_state.json`). Không chặn release vì đường dùng chính (DeepSeek/OpenAI)
đã verify sống; Claude/Ollama đã có nhánh khoá an toàn (không tự ramp) trong lúc chờ verify.

Kết quả verify trước release: `pytest tests/ -q` → 240/240 pass, `ruff check` + `ruff format
--check` sạch.

---

# v1.1.1 — Release

**Ngày**: 2026-09-05

2 bug fix phát hiện qua báo cáo dùng thật của user (job dịch thật `Figoni, Paula - How baking
works`) sau v1.1.0, cộng 1 known limitation mới ghi nhận (không sửa trong release này).

## Fix: MinerU `/tasks` trả 500 khi mở app qua shortcut Desktop

Root cause xác nhận qua `lsof` trực tiếp trên process MinerU thật đang chạy: double-click
`BB-Translation.app` (Automator/AppleScript) launch qua LaunchServices, KHÔNG qua shell profile
bình thường — CWD của process là `/` (ổ hệ thống, read-only trên macOS hiện đại). MinerU tự
`mkdir` thư mục output MẶC ĐỊNH tương đối (`./output`, xem `mineru/cli/fast_api.py:87,339`) —
`root.mkdir()` raise `OSError: Read-only file system` mỗi lần có request `/tasks` thật, dù
`/health` vẫn trả 200 bình thường (route khác, không đụng thư mục output) — đây là lý do bug
không lộ ra khi chỉ test health check. `scripts/pipeline_toggle.sh`: thêm `cd "$PROJECT_DIR"`
TRƯỚC khi khởi động `mineru-api` (trước đây `cd` chỉ chạy trước khi khởi động app, sau
`mineru-api`), và export `MINERU_API_OUTPUT_ROOT` tuyệt đối (`$PROJECT_DIR/data/mineru-output`)
làm phòng thủ thêm — không chỉ dựa vào CWD đúng. Verify sống: dừng process cũ (CWD sai xác nhận
qua `lsof -a -p <pid> -d cwd` = `/`), mở lại qua chính `open ~/Desktop/BB-Translation.app` (giả
lập double-click thật, không phải gọi script trực tiếp), `lsof` xác nhận CWD process mới đúng
project dir, `POST /tasks` (file scan-like tự tạo) trả `202` thay vì `500`.

## Fix: font tiếng Việt bị vỡ trong bước post-process `font_shrink_page`

Root cause xác nhận bằng test trực tiếp: `src/postprocess/font_shrink.py` (bước co/nén font khi
chữ dịch tràn khung, Architecture.md 6.3) đo VÀ vẽ lại span bằng font PDF base-14 `"helv"` — font
này không có glyph cho ký tự tiếng Việt ngoài Latin-1. Verify: `page.insert_text(..., text="bánh
mì thơm ngon", fontname="helv")` rồi đọc lại → `"thơm"` render thành `"th·m"` (ký tự ơ bị mất).
Đồng thời `helv` đo `"bánh"` ở 12pt = 20.0pt trong khi font Noto thật pdf2zh dùng để render đo
28.9pt (lệch ~45%) — sai cả 2 chiều: quyết định "có tràn khung không" sai, VÀ nếu có vẽ lại thì
vẽ lại bằng font vỡ chữ.

Sửa: `font_shrink_page()`/`evaluate_span()` nhận thêm `font_path` (optional, mặc định `None` giữ
nguyên hành vi `helv` cho test cũ không quan tâm) — dùng `fitz.Font(fontfile=...)` để đo,
`page.insert_text(..., fontfile=...)` để vẽ lại, đảm bảo ĐÚNG font pdf2zh đã render trang đó.
`Pdf2zhServiceMapper.map()` giờ set `NOTO_FONT_PATH` (tuyệt đối, chỉ khi file tồn tại) vào env
subprocess pdf2zh cho MỌI provider (trừ DeepL, đã bị chặn từ trước) — pin pdf2zh vào ĐÚNG 1 file
font thay vì để nó tự động tải riêng (không cách nào để `font_shrink_page` biết pdf2zh đã tải
file nào). `JobOrchestrator.__init__` resolve `settings.noto_font_path` một lần, truyền vào mọi
lời gọi `font_shrink_page()`.

Đổi font ghim từ GoNotoKurrent (fallback mặc định của pdf2zh) sang **Be Vietnam Pro** (OFL,
Google Fonts, theo yêu cầu user) — verify glyph coverage 100% cho dấu tiếng Việt + ký hiệu sách
nấu ăn thường gặp (°, phân số ¼ ½, bullet •, em-dash —, ngoặc kép cong) trước khi chốt. File thật
tại `fonts/BeVietnamPro-Regular.ttf`, `Settings.noto_font_path` default trỏ đúng đường dẫn này.
Phát hiện thêm: `.env`/`.env.example` từng có `NOTO_FONT_PATH=fonts/GoNotoKurrentRegular.ttf` trỏ
tới file KHÔNG TỒN TẠI (thiếu dấu `-`, và file chưa từng được cấp) — biến này override thẳng
field `noto_font_path` qua cơ chế mapping tên của `pydantic-settings`, khiến path mặc định mới
trong code bị vô hiệu cho tới khi phát hiện và sửa cả 2 file `.env`.

Test mới: `tests/test_font_shrink.py` (glyph tiếng Việt round-trip đúng qua `font_path`, chênh
lệch đo lường `helv` vs font thật >20%), `tests/test_pdf2zh_service_map.py` (set/omit
`NOTO_FONT_PATH` theo file tồn tại hay không). `pytest tests/ -q` → 244/244 pass (240 cũ + 4
mới), `ruff check` + `ruff format --check` sạch trên mọi file sửa/thêm.

## Known limitation (KHÔNG sửa trong release này) — danh sách/bullet bị gộp dòng, bullet vỡ ký tự

Verify sống bằng 1 job dịch thật tối thiểu (DeepSeek, chi phí ~\$0.00, PDF test tự tạo mô phỏng
đúng cấu trúc user báo cáo — danh sách đánh số + bullet). Output thật:

```
1. Cân bánh hoặc cân điện tử 2. Cốc đong và thìa đong, nhiều
kích cỡ khác nhau 3. Rây hoặc lưới lọc 4. Máy trộn có bát 5 q
uart, Hobart N50 ba tốc độ
```

Root cause đọc trực tiếp source `pdf2zh/converter.py` (KHÔNG suy đoán): (1) mỗi "đoạn văn" chỉ
lưu 1 cờ boolean `pstk[-1].brk` ("đoạn gốc CÓ ngắt dòng ở đâu đó"), KHÔNG lưu vị trí từng chỗ
ngắt — khi render lại, dòng ~447 chỉ xuống dòng khi `x + adv > x1` (chạm mép phải khung), y hệt
văn xuôi thường; nhiều dòng ngắn (không dòng nào chạm mép phải, ví dụ mỗi mục danh sách) bị gộp
thành 1 dòng liên tục. (2) Riêng ký tự `•`: dòng 237 có `if child.get_text() == "•": cls = 0`
("neo bullet vào vùng công thức/giữ chỗ" theo comment gốc) — bullet bị xử lý như công thức/ký
hiệu toán học, đi qua đường render font khác, output thật cho ra `"?"` thay vì `"•"`.

Đây là giới hạn thiết kế của chính pipeline dịch-theo-đoạn của pdf2zh (KHÔNG phải bug trong code
team viết) — sửa an toàn cần patch trực tiếp source `pdf2zh/converter.py` (fork/vendor riêng),
ngoài phạm vi release này. User đã đồng ý chấp nhận giới hạn này để release, và giao task riêng
điều tra 2 hướng: (a) patch/vendor pdf2zh để sửa tận gốc, hoặc (b) đánh giá thay thế bằng tool
dịch PDF khác phù hợp hơn cho nội dung có cấu trúc danh sách.

Kết quả verify trước release: `pytest tests/ -q` → 244/244 pass, `ruff check` sạch, `pipeline_
toggle.sh` verify sống qua double-click thật (không chỉ gọi script), MinerU `/tasks` 202,
font tiếng Việt round-trip đúng.

---

## Correction (2026-09-05) + Research babeldoc cho known limitation v1.1.1

### Correction: claim "bullet • vỡ thành ?" KHÔNG xác nhận được trên dữ liệu thật — rút lại

Verify sống trên đúng file gốc user upload (`Figoni, Paula - How baking works...-1-25.pdf`, trang
14, nội dung y hệt screenshot user gửi): file này **không chứa ký tự `•` nào** trong toàn bộ 25
trang (grep xác nhận), chỉ dùng số thứ tự. Claim "?" trong entry v1.1.1 ở trên đến từ 1 PDF test
tự tạo bằng `page.insert_textbox(..., fontname="helv")` — nhưng `"helv"` (base-14) không có glyph
cho `•`, nên bản thân bullet trong file test ĐÃ bị ghi thành `"?"` ngay khi tạo file, TRƯỚC KHI
đưa vào pdf2zh (xác nhận bằng `page.get_text("rawdict")` trên chính file test, trước khi dịch).
Dựng lại test với font có glyph `•` thật (Be Vietnam Pro) → pdf2zh render bullet ra đúng `"•"`,
không còn "?". **Kết luận: đây là lỗi trong phương pháp test của chính phiên làm việc trước, không
phải bug thật của pdf2zh** — rút lại phần "bullet vỡ ký tự" khỏi known limitation.

**Phần còn lại của known limitation (gộp dòng danh sách + cắt ngang từ giữa chừng) vẫn đứng vững
— tái hiện lại thành công trên đúng trang 14 file gốc thật** (không chỉ PDF test), qua pdf2zh
thật + DeepSeek thật, output: `"1. Cân của thợ làm bánh hoặc cân điện tử 2. Cốc đong và thìa
đong..."` (gộp) và `"điện t"` / `"ử"` (cắt ngang từ) — khớp 100% với báo cáo gốc của user.

### Research: `babeldoc` (kế nhiệm thực tế của pdf2zh) — cải thiện mạnh, chưa hoàn hảo

`pdf2zh` 1.9.11 (bản đang cài) xác nhận là bản mới nhất trên PyPI — dự án gần như ngừng phát
triển, và cờ `--babeldoc` có sẵn của nó pin `babeldoc==0.2.33` (rất cũ). `babeldoc` (dependency
được gọi) là dự án kế nhiệm đang phát triển tích cực, hiện tại 0.6.4 trên PyPI, kiến trúc hoàn
toàn khác (document Intermediate Language, `paragraph_finder.py` có logic tường minh xử lý bullet/
short-line — không phải hack thô như `converter.py` cũ của pdf2zh).

**2 vấn đề môi trường phát hiện khi thử** (không phải bug logic, thuần compatibility):
- `pdf2zh --babeldoc` (bridge có sẵn) crash ngay: `np.fromstring()` (binary mode) đã bị numpy gỡ
  bỏ, không tương thích numpy hiện tại trong venv của tool `pdf2zh`.
- Cài `babeldoc` CLI riêng (`uv tool install babeldoc`, mặc định kéo Python 3.14) cũng crash:
  dùng `concurrent.futures.thread._WorkItem` (API nội bộ private của CPython) với signature đã
  đổi ở Python 3.14. Ép `--python 3.12` khi cài thì chạy được bình thường.

**Verify sống trên ĐÚNG trang 14 file gốc thật** (không phải PDF test), qua `babeldoc` CLI riêng
(0.6.4, Python 3.12) + DeepSeek thật (`--openai --openai-base-url https://api.deepseek.com`,
`--split-short-lines`, `--watermark-output-mode no_watermark`):
```
1. Cân làm bánh hoặc cân điện tử
2. Cốc đong và thìa đong, nhiều
kích cỡ khác nhau
3. Rây hoặc lưới lọc
...
11. Lò nướng (thông thường, quay,
tầng, v.v.)12. Bếp ga
```
**31/35 mục xuống dòng đúng** (so với 0/35 của pdf2zh cũ), **không còn lỗi cắt ngang từ giữa
chừng nào quan sát được** trong toàn bộ output. Còn 4 cặp mục dính liền (11/12, 23/24, 31/32,
33/34) — khớp đúng caveat chính hãng ghi trong `--help`: `--split-short-lines`: "may cause poor
typesetting & bugs". Chưa thử chỉnh `--short-line-split-factor` (có thể giảm tiếp số cặp dính).

Contract CLI tương thích cao với `Pdf2zhServiceMapper` hiện tại: `-s`/service model giữ nguyên
khái niệm qua `--openai-base-url`/`--openai-api-key` (Claude/DeepSeek vẫn qua compat layer y hệt
đang dùng), `--pages`/`--output`/`--qps` tương ứng trực tiếp `-p`/`-o`/`--thread`. Khác biệt cần
xử lý nếu tích hợp: (1) tên file output khác pattern (`{stem}.no_watermark.{lang}.mono.pdf` thay
vì `{stem}-mono.pdf` — `Pdf2zhRunner` đang hardcode pattern cũ); (2) watermark bật mặc định, cần
luôn truyền `--watermark-output-mode no_watermark`; (3) cơ chế tín hiệu rate-limit cho AIMD
(hiện đang grep text log stdout/stderr theo `RATE_LIMIT_LINE_RE`) CHƯA điều tra cho babeldoc —
babeldoc dùng progress-event system khác hẳn (`async for event in yadt_translate(...)`), có thể
là kênh tín hiệu tốt hơn (structured) nhưng cần research riêng trước khi khẳng định.

### Tiếp tục research (b): tune factor + thử bridge `pdf2zh --babeldoc` sau khi pin numpy cũ

**Tune `--short-line-split-factor`**: thử 0.8 (default) → 1.0 (aggressive nhất còn hợp lý) trên
đúng trang 14 thật — **không đổi kết quả gì**, đúng 4 cặp mục dính liền cũ (11/12, 23/24, 31/32,
33/34) vẫn y nguyên. Kết luận: đây KHÔNG phải vấn đề ngưỡng độ rộng dòng — là 1 edge case khác
trong `paragraph_finder.py` (chưa xác định chính xác nguyên nhân, không đáng đào tiếp ở mức effort
hiện tại).

**Bridge `pdf2zh --babeldoc` sau khi pin numpy cũ**: xác nhận `babeldoc==0.2.33` (bản pdf2zh
1.9.11 bundle) **đã có sẵn CÙNG logic** `is_bullet_point`/`split_short_lines` như bản 0.6.4 (đọc
trực tiếp source, không phải feature mới). Downgrade `numpy<2.0` trong venv riêng của tool
`pdf2zh` (`uv pip install --python <venv>/bin/python3 "numpy<2.0"`) → hết crash `np.fromstring`.
NHƯNG gặp lỗi khác ngay khi test trên đúng file thật: `ScannedPDFError: Scanned PDF detected`
(babeldoc 0.2.33 tự phát hiện >80% trang trông giống scan trong file 25 trang, dù chỉ chọn dịch
1 trang qua `--pages 14`, và từ chối dịch thẳng — không có cách nào tắt qua CLI của `pdf2zh`).
Đọc trực tiếp source `pdf2zh/pdf2zh.py::yadt_main()` xác nhận nguyên nhân sâu hơn: hàm này chỉ
forward 11 tham số cố định vào `YadtConfig` (`input_file, font, pages, output_dir,
doc_layout_model, translator, debug, lang_in, lang_out, no_dual, no_mono, qps`) — **KHÔNG có
đường nào để truyền `split_short_lines`, `skip_scanned_detection`, hay bất kỳ flag nào khác** mà
bản CLI riêng `babeldoc` (0.6.4) có. Đã khôi phục lại `numpy==2.5.2` ban đầu cho venv `pdf2zh`
sau khi xác nhận xong (không giữ trạng thái pin, vì không dùng đường này).

**Kết luận rõ ràng cho quyết định tích hợp**: bridge `pdf2zh --babeldoc` là ngõ cụt — dù pin được
numpy, code CLI của chính `pdf2zh` không expose đủ điểm cấu hình cần thiết, và version babeldoc
nó bundle (0.2.33) có scan-detection gắt hơn/không tắt được. Nếu theo hướng babeldoc, phải tích
hợp **`babeldoc` CLI độc lập** (0.6.4, cần Python 3.12 riêng — không dùng chung venv với
`pdf2zh`/`mineru-api`), viết adapter mới song song `Pdf2zhRunner` (không dùng lại bridge cũ).

### Research: contract rate-limit cho AIMD — tín hiệu tồn tại nhưng KHÁC bản chất với pdf2zh

Đọc trực tiếp source `babeldoc/translator/translator.py`: `OpenAITranslator.do_translate()`/
`do_llm_translate()` bọc bằng `tenacity.retry(retry_if_exception_type(openai.RateLimitError),
stop_after_attempt(100), wait_exponential(...), before_sleep=before_sleep_log(logger,
logging.WARNING))` — khác hẳn cách pdf2zh log thô qua `rich` progress display, đây là log qua
Python `logging` chuẩn, logger name `babeldoc.translator.translator`, format do chính thư viện
`tenacity` sở hữu (ổn định, không phải babeldoc tự chế): `"Retrying {fn} in {N} seconds as it
raised RateLimitError: {msg}."`.

**Verify sống bằng local fake server trả HTTP 429** (không tốn API thật): dựng
`http.server.ThreadingHTTPServer` trả 429 N lần đầu rồi 200, gọi thẳng cùng pattern
`openai.OpenAI(...).chat.completions.create()` + tenacity decorator y hệt babeldoc — bắt được
đúng dòng log thật:
```
WARNING:...:Retrying __main__.do_translate in 1 seconds as it raised RateLimitError:
Error code: 429 - {'error': {'message': 'Rate limit reached', 'type': 'rate_limit_error'}}.
```
→ chuỗi ổn định để grep: `"as it raised RateLimitError:"`.

**NHƯNG phát hiện khác biệt kiến trúc quan trọng**: `translator.py` dòng ~230 khởi tạo
`openai.OpenAI(base_url=..., api_key=..., http_client=...)` — KHÔNG truyền `max_retries`, nên
dùng mặc định `openai.DEFAULT_MAX_RETRIES` (= 2) của chính SDK `openai`, và babeldoc/CLI **không
có flag nào để tắt/chỉnh số này**. Nghĩa là: SDK tự động retry ngầm (không log gì qua `logging`)
tối đa 2 lần cho MỖI request trước khi exception mới thoát ra tới tenacity — khác hẳn pdf2zh, nơi
MỌI lần 429 đều hiện ra trực tiếp (không có lớp retry ẩn nào ở dưới). Hệ quả: nếu tích hợp
babeldoc, bộ đếm `rate_limit_hits` hiện tại (dựa vào đếm dòng log) sẽ **undercount** — chỉ những
lần rate-limit đủ NẶNG để vượt quá 2 lần tự-retry ngầm của SDK mới lộ ra thành 1 dòng log đếm
được. Không thể tái dùng nguyên `ADAPTIVE_THREAD_FLOOR`/ngưỡng AIMD hiện tại mà không hiệu chỉnh
lại — ý nghĩa của "1 rate_limit_hit" đã đổi bản chất (không còn là "1 lần 429 thật" mà là "1 lần
429 dai dẳng qua >2 request ngầm").

Cũng xác nhận: babeldoc CLI (`main.py:920`) dùng
`logging.basicConfig(handlers=[RichHandler()])` — CÙNG cơ chế `rich` như pdf2zh cũ, nên rủi ro bị
cắt dòng ở COLUMNS thấp khi không chạy trong TTY (đã né bằng `COLUMNS=200`) áp dụng y hệt, mitigation
hiện có (`COLUMNS=200` trong env subprocess) nhiều khả năng chuyển thẳng sang được, nhưng chưa verify
sống dòng log rate-limit thật qua chính babeldoc CLI (chỉ verify qua script cô lập gọi thẳng SDK +
tenacity, KHÔNG qua toàn bộ pipeline PDF của babeldoc — thử qua fake-server + babeldoc CLI thật bị
vướng 1 lỗi khác không liên quan, JSON parse error ở tầng `il_translator_llm_only.py`, nghi do
response body giả không đúng format JSON mode babeldoc kỳ vọng — chưa gỡ tiếp, ngoài phạm vi câu
hỏi rate-limit).

### Tổng kết dữ kiện cho quyết định tích hợp (đã đủ để quyết định)

| Tiêu chí | pdf2zh (hiện tại) | babeldoc CLI riêng (0.6.4) |
|---|---|---|
| Gộp danh sách (trang 14 thật) | 0/35 mục đúng | 31/35 mục đúng |
| Cắt ngang từ giữa chừng | Có (xác nhận thật) | Không quan sát được |
| Cần venv riêng | Không (đã có) | Có (Python 3.12 riêng, tách biệt `pdf2zh`/`mineru-api`) |
| Bridge `pdf2zh --babeldoc` có sẵn | N/A | Ngõ cụt (thiếu flag forward + scan-detect cứng) |
| Tín hiệu rate-limit cho AIMD | Trực tiếp, mọi lần 429 | Có nhưng bị SDK tự nuốt tối đa 2 lần/request trước khi lộ ra — cần hiệu chỉnh lại floor/ceiling |
| Format output file | `{stem}-mono.pdf` | `{stem}.no_watermark.{lang}.mono.pdf` — cần sửa `Pdf2zhRunner` |
| Watermark mặc định | Không | Có, phải luôn truyền `--watermark-output-mode no_watermark` |
| Effort tích hợp | — | Viết adapter mới hoàn toàn (không tái dùng `Pdf2zhRunner` được, chỉ tái dùng `Pdf2zhServiceMapper`-style mapping khái niệm), hiệu chỉnh lại AIMD, cài đặt/quản lý thêm 1 tool venv |

**Kết luận**: babeldoc cải thiện thật (không phải ảo tưởng), đủ dữ kiện để quyết định, nhưng KHÔNG
phải "drop-in replacement" nhẹ nhàng — đổi cả cách đo rate-limit lẫn cách gọi subprocess. Quyết
định tích hợp chính thức (fork/patch pdf2zh cũ vs. viết adapter mới cho babeldoc vs. giữ nguyên
chấp nhận giới hạn) để người dùng/Tech Lead quyết, không tự chọn.

# v1.2.0 — Release

**Ngày**: 2026-09-05

Giải quyết known limitation ghi nhận từ v1.1.1 (danh sách/bullet bị gộp dòng của `pdf2zh`) bằng
1 engine dịch PDF thứ hai, `babeldoc`, chạy song song `pdf2zh` (không xoá/sửa code cũ) — xem
Architecture.md section 6.14 cho thiết kế đầy đủ.

## Increment 7 — `BabeldocRunner`: engine dịch PDF thứ hai (Architecture.md 6.14)

Implement đầy đủ theo Architecture.md 6.14 (đã qua checkpoint Protocol 2), sau khi PM brief chốt
sang đúng theo bản Tech Lead đã verify sống trên `babeldoc` 0.6.4 (spike B6/B10). Dev tự chạy lại
2 spike sống của Tech Lead (Protocol 5 mục 3) trước khi viết mock, thay vì tin lại kết quả spike
cũ không có golden file backing.

**File mới**: `src/services/babeldoc_runner.py` — `BabeldocRunner`, `BabeldocResult`,
`BabeldocError`, `BabeldocTimeoutError`. Cùng shape tham số/kiểu trả về với `Pdf2zhRunner`
(`src/services/pdf2zh_runner.py` — KHÔNG sửa 1 dòng nào của file này). Tái dùng nguyên kỹ thuật
subprocess đã có (`asyncio.create_subprocess_exec` + 2 task `_drain` + `wait_for` + kill timeout +
mop-up 5s) và `RATE_LIMIT_LINE_RE` hiện có (không viết regex mới).

Hardcode 7 flag bắt buộc theo bảng đối chiếu 6.14.2: `--openai --openai-base-url --openai-api-key
--openai-model` (dịch từ `service.envs`), `--pool-max-workers`, `--watermark-output-mode
no_watermark`, `--only-include-translated-page`, `--no-auto-extract-glossary`,
`--skip-scanned-detection`, `--split-short-lines`. `--custom-system-prompt` nhận NỘI DUNG file
prompt (đọc bằng `.read_text()`), không nhận đường dẫn — khác `pdf2zh --prompt`.

**Quyết định thiết kế phát sinh khi implement (chưa có trong Architecture.md 6.14.3, cần Tech
Lead/Reviewer soát lại)**: `service.envs` do `Pdf2zhServiceMapper` sinh ra chỉ mang đủ 3 giá trị
base_url/api_key/model cho `openai` và `claude` (qua `openailiked`) — `gemini`/`deepseek`/`ollama`
chỉ có api_key + model (pdf2zh tự biết base_url nội bộ, không cần biến môi trường riêng). Để dịch
đủ bộ 3 cho babeldoc mà KHÔNG tạo "bảng mapping thứ hai" theo đúng tinh thần Architecture.md
6.14.3 cảnh báo, `_resolve_openai_compat()` trong `babeldoc_runner.py` tra cứu thêm: Gemini dùng
endpoint OpenAI-compat đã verify sống (Architecture.md 6.14.1 B14), DeepSeek tái dùng đúng giá trị
đã có sẵn trong `Settings.deepseek_base_url` (`src/core/config.py`, không phải kiến thức mới),
Ollama suy ra `{OLLAMA_HOST}/v1`. Không provider nào map được -> raise
`UnsupportedForPdfPipelineError` trước khi spawn subprocess. Đây là 1 khoảng trống của spec gốc
(chữ ký `translate_pages()` không nhận `Settings`), Dev tự giải quyết theo nguyên tắc ít rủi ro
nhất thay vì escalate-block, nhưng PM cần đưa cho Reviewer soát kỹ chỗ này.

**Data lineage (Protocol 6 R6-01/R6-02)**: điểm chọn engine DUY NHẤT nằm ở property
`JobOrchestrator._translator_runner` (lazy, không cache trong `__init__` — giữ nguyên khả năng
test đổi `orchestrator._pdf2zh_runner`/`._babeldoc_runner` sau khi khởi tạo, đúng pattern
resumable-job đã có từ Increment 4). `_process_chunk()` gọi `self._translator_runner.translate_pages(
input_path=source_path, ...)` một lần duy nhất cho cả 2 engine — `source_path` vẫn là
`translation_source_path` đã tính ở Step 2 của `run_job()` (bridge OCR cho `pdf_scan`, file gốc
cho `pdf_digital`), không đọc lại `job.file_path`. Test mới
`test_pdf_scan_babeldoc_engine_translates_bridge_not_original`
(`tests/integration/test_job_orchestrator.py`) là bản sao chính xác của
`test_pdf_scan_translates_bridge_not_original` hiện có cho engine babeldoc, assert giá trị cụ thể
(`call.kwargs["input_path"] == expected_bridge`), không chỉ `assert_awaited()`.

**AIMD (Protocol 6, Architecture.md 6.14.5)**: thêm `BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR = 3` và
`BABELDOC_THREAD_FLOOR` (`src/core/concurrency_controller.py`) — floor riêng = ceil(floor_pdf2zh/2)
cho từng provider, `next_thread_count()` giữ nguyên. `ConcurrencyState` (`src/models/
concurrency_state.py`) đổi khóa chính từ `(provider, model)` sang `(engine, provider, model)`,
migration `_migrate_concurrency_state_engine_key()` (`src/models/database.py`) rebuild bảng SQLite
theo pattern chuẩn (ALTER TABLE không đổi được PRIMARY KEY), backfill `engine='pdf2zh'` cho mọi
bản ghi cũ — có test riêng xác nhận sau migrate, 1 `(provider, model)` có thể có 2 bản ghi khác
engine song song không đụng độ PK.

**Feature flag (Architecture.md 6.14.7)**: `Settings.pdf_translate_engine: Literal["pdf2zh",
"babeldoc"] = "pdf2zh"` + `babeldoc_executable: str = "babeldoc"` (`src/core/config.py`),
`.env`-only, KHÔNG vào `SETTINGS_DB_OVERRIDABLE_FIELDS`. Mặc định vẫn `pdf2zh` — toàn bộ 244 test
cũ chạy xanh y nguyên không cần sửa gì (ngoại trừ 6 chỗ `ConcurrencyState(provider=...)`/`.get(
ConcurrencyState, (provider, model))` trong `tests/integration/test_job_orchestrator_concurrency.py`
phải thêm `"pdf2zh"` vào khóa 3 phần do đổi PK ở trên).

**Golden files (Protocol 5 mục 3)**: 2 spike sống tự chạy lại trên `babeldoc` 0.6.4 (đã cài sẵn
trên máy Dev qua `uv tool install`) lưu tại `tests/fixtures/babeldoc/` — fake OpenAI-compat server
trả 200 (xác nhận đúng pattern tên file `{stem}.no_watermark.{lang}.mono.pdf`/`.dual.pdf`, đúng
Bearer header, đúng 1 trang mono khi có `--only-include-translated-page`, không có request
term-extraction khi có `--no-auto-extract-glossary`) và server ép HTTP 429 40 lần (xác nhận đúng
12 dòng `"RateLimitError"` trên stdout, 0 trên stderr — khớp Architecture.md 6.14.1 B10/B11).
`tests/test_babeldoc_runner.py` dựng mock rate-limit test TỪ chính golden stdout này
(`spike2_429_stdout.log`), không viết tay chuỗi log.

**Chưa verify (⚠️ ASSUMED, giữ nguyên theo Architecture.md — không tự ý coi là verified)**: Gemini
end-to-end thật qua babeldoc (thiếu `GEMINI_API_KEY` thật trong `.env`), Ollama (chưa cài trên máy
này, `which ollama` không tìm thấy). Không tự chạy live test cho 2 nhánh này — để nguyên trạng thái
ASSUMED cho QA/Tech Lead xử lý tiếp.

**Trạng thái**: code + unit test xanh (261/261, bao gồm 244 test cũ không đổi hành vi). CHƯA chạy
QA gate 6.14.6 (E2E 2 engine song song trên file thật) — đó là việc của QA, không phải Dev. Dừng
lại ở đây để PM chuyển Reviewer, đặc biệt lưu ý điểm "quyết định thiết kế phát sinh" ở trên
(`_resolve_openai_compat`) chưa có trong Architecture.md gốc.

## Đổi default engine sang babeldoc (2026-09-05)

Reviewer APPROVE (round 1) + QA gate 6.14.6 chạy sống PASS 8/8 trên file thật (Figoni...pdf trang
14, DeepSeek thật) — xem `docs/review-report.md` và `docs/test-report.md` mục mới. Số liệu đo
được: babeldoc sửa đúng lỗi gộp dòng danh sách (31/35 mục xuống dòng đúng vs ~0/35 ở pdf2zh) nhưng
chậm hơn **~108x** (2859s vs 26.4s cho 25 trang, do cold-start thread floor=4 + dịch theo dòng).
0 lần rate-limit thật xảy ra trong lần chạy này nên `BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR`/
`BABELDOC_THREAD_FLOOR` (Architecture.md 6.14.5) vẫn giữ nhãn `⚠️ ASSUMED` — N=1, chưa đủ dữ liệu
rate-limit thật để kiểm chứng.

Người dùng đã được PM trình bày rõ đánh đổi tốc độ và quyết định chấp nhận (Protocol 2 — đổi
default là quyết định người, không phải quyết định kỹ thuật của QA). Đổi
`Settings.pdf_translate_engine` default `"pdf2zh"` → `"babeldoc"` (`src/core/config.py`).
**Không xoá `pdf2zh_runner.py` hay bất kỳ code pdf2zh nào** — giữ nguyên làm đường rollback tức
thời (`PDF_TRANSLATE_ENGINE=pdf2zh` trong `.env` + restart), vì giữ code song song không tốn chi
phí runtime nào và increment này còn 2 điểm `⚠️ ASSUMED` (Gemini/Ollama end-to-end, hằng số AIMD)
chưa được kiểm chứng ở quy mô lớn hơn N=1.

## Fix: 15 test integration ngầm phụ thuộc default engine sau khi đổi sang babeldoc (2026-09-05)

Sau khi đổi `Settings.pdf_translate_engine` default sang `"babeldoc"` (mục trên), `pytest -q`
toàn bộ suite phát hiện 15 test FAIL, khiến suite chạy 988s (16.5 phút) thay vì ~10s — nguyên
nhân: các test này construct `JobOrchestrator`/`Settings` KHÔNG set tường minh
`pdf_translate_engine="pdf2zh"`, nên ngầm dựa vào default toàn cục. `JobOrchestrator._translator_runner`
(Architecture.md 6.14.7) khi thấy engine="babeldoc" bỏ qua HOÀN TOÀN `pdf2zh_runner` đã inject
(kể cả khi test truyền vào), tự dựng `BabeldocRunner` thật và gọi subprocess `babeldoc` CLI thật
(chậm, đúng tính chất đã biết) — mock pdf2zh không bao giờ được gọi, khiến assertion trên mock đó
FAIL, hoặc (với vài test có assertion dạng lặp qua `mock.await_args_list` rỗng) PASS giả — vacuously
true — dù mock chưa từng chạy.

Sửa: pin tường minh `pdf_translate_engine="pdf2zh"` vào MỌI `Settings(...)`/`JobOrchestrator(...)`
trong 5 file test dùng mock `pdf2zh_runner` (không chỉ 15 test FAIL ban đầu, mà toàn bộ call site
tương tự để chặn cùng lỗi tái phát ngầm — theo yêu cầu quét `grep -rn "JobOrchestrator("/"Settings("`):
- `tests/integration/test_cost_capped_orchestrator.py` (5 chỗ)
- `tests/integration/test_job_cancel.py` (3 chỗ, thêm import `Settings`)
- `tests/integration/test_job_orchestrator.py` (12 chỗ — trừ test babeldoc riêng đã pin sẵn
  `pdf_translate_engine="babeldoc"`)
- `tests/integration/test_job_orchestrator_concurrency.py` (7 chỗ)
- `tests/integration/test_job_orchestrator_chunk_size_cold_start.py` (6 chỗ)

`tests/integration/test_batch_orchestrator.py` không cần sửa — mock nguyên `JobOrchestrator`
bằng `AsyncMock(spec=JobOrchestrator)`, không bao giờ chạm `_translator_runner`.

Kết quả: `pytest -q` toàn bộ suite (261 test) xanh 100% trong ~10s (không còn gọi babeldoc CLI
thật lẫn vào test không liên quan đến babeldoc).

## Fix non-blocking suggestion của Reviewer: DeepSeek base_url hardcode (2026-09-05)

`review-report.md` (Iteration 1) ghi nhận `_resolve_openai_compat()` hardcode
`_DEEPSEEK_BASE_URL` trùng giá trị `Settings.deepseek_base_url`, nhưng field này nằm trong
`SETTINGS_DB_OVERRIDABLE_FIELDS` — nếu user đổi override qua UI, nhánh babeldoc sẽ không theo kịp.

Sửa: `_resolve_openai_compat()` nhận thêm keyword-only `deepseek_base_url` (mặc định
`_DEFAULT_DEEPSEEK_BASE_URL` cho chỗ gọi không có `Settings`, ví dụ test). `BabeldocRunner.__init__`
nhận `deepseek_base_url` và truyền xuống khi gọi `translate_pages()`. `JobOrchestrator._translator_runner`
(`src/core/job_orchestrator.py`) truyền `self._settings.deepseek_base_url` (đã áp dụng DB override
qua `get_effective_settings()`, xem `src/api/routes/jobs.py`) khi khởi tạo `BabeldocRunner`.

Thêm test `test_resolve_openai_compat_deepseek_honors_settings_override`
(`tests/test_babeldoc_runner.py`). `pytest -q`: 262 passed trong 10.24s, `ruff check` sạch.

`pyproject.toml` bump `1.1.1` → `1.2.0`.

**Known limitations mang sang (KHÔNG chặn release này, đúng kỷ luật đã áp dụng từ v1.1.0 cho
Claude/Gemini `[UNVERIFIED]`)**:

- Gemini và Ollama qua `babeldoc` chưa verify end-to-end thật (thiếu `GEMINI_API_KEY` thật trong
  `.env`, Ollama chưa cài trên máy dev) — chỉ verify được shape client (Architecture.md 6.14.1
  B2/B6/B14) khớp đúng contract 2 provider này cần, chưa chạy được 1 lần dịch thật. Đường dùng
  chính (DeepSeek qua babeldoc) đã verify sống qua QA gate 6.14.6. Gemini vẫn chạy AIMD tự động
  đầy đủ (không khoá an toàn, giống hệt cách pdf2zh đã ship Gemini AIMD `[UNVERIFIED]` ở v1.1.0);
  Claude vẫn khoá thread cố định ở floor, không tự ramp (6.14.5 mục 5).
- Hằng số AIMD cho tín hiệu babeldoc (`BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR=3`,
  `BABELDOC_THREAD_FLOOR`, Architecture.md 6.14.5) là lựa chọn bảo thủ có chủ đích dựa trên 1 lần
  đo (N=1, 0 lần rate-limit thật xảy ra trong QA gate) — chưa kiểm chứng ở quy mô lớn hơn. Người
  dùng đã quyết định chấp nhận rủi ro này, để AIMD tự học dần qua các job thật thay vì chặn release
  chờ đo thêm (`ConcurrencyState` tự điều chỉnh `current_thread` theo `next_thread_count()` qua
  từng chunk, không phải hằng số cố định vĩnh viễn).
- Tốc độ dịch qua `babeldoc` chậm hơn `pdf2zh` đo được **~108x** trên 1 file 25 trang (2859s vs
  26.4s) — đánh đổi đã được trình bày rõ và người dùng chấp nhận để đổi lấy chất lượng dịch tốt
  hơn (sửa đúng known limitation gộp dòng danh sách của v1.1.1). `pdf2zh` vẫn còn nguyên trong
  codebase, chọn lại bằng `PDF_TRANSLATE_ENGINE=pdf2zh` trong `.env` + restart nếu cần rollback.

Kết quả verify trước release: `pytest -q` → 262/262 pass (9.5s), `ruff check` sạch trên mọi file
sửa/thêm trong increment này. QA gate sống (Architecture.md 6.14.6, `docs/test-report.md`) PASS
8/8 trên file thật qua DeepSeek. Reviewer APPROVE (`docs/review-report.md`).

## Fix Bug thật (2026-09-05): sách born-digital bị phân loại nhầm thành pdf_scan, sinh 2 lớp text chồng nhau

User báo cáo bản dịch "How Baking Works" v1.2.0 lỗi hiển thị nặng: trang bìa mất chữ, font nhỏ
lộn xộn, đè chữ 2 lần, mục lục tràn số. PM tự tay mở TRỰC TIẾP các file output thật bằng PyMuPDF
(không qua mock) để điều tra — quy trình theo đúng tinh thần Protocol 5.

**Nghi ngờ ban đầu (đã bác bỏ)**: race condition khi job resume gọi lại `translate_pages()` vào
cùng `chunk_output_dir` cũ (`src/core/job_orchestrator.py`). Đã vá bằng `shutil.rmtree()` ở đầu
mỗi lần gọi `_call_translator()` — fix này ĐÚNG và VẪN GIỮ (chặn 1 race thật), nhưng Tech Lead
verify độc lập bằng thực nghiệm PyMuPDF cho thấy đây KHÔNG PHẢI nguyên nhân của lỗi user báo cáo
(race không giải thích được vì sao 25/25 trang đều hỏng theo cùng 1 pattern, cũng không giải
thích được 2 họ font Việt chồng nhau).

**Root cause thật (Tech Lead verify bằng dữ liệu thật, không suy đoán)**:

1. `src/core/file_router.py`: `_detect_pdf_type()` tính `pages_with_text / total_pages` — sách
   này là PDF chữ thật (font nhúng Palatino-Light/Futura-Bold, đọc được ngay bằng pdfminer), 21/25
   trang có text, nhưng 4 trang là ẢNH NGUYÊN TRANG hợp lệ (bìa, trang phân chương). Công thức cũ
   tính 4 trang đó là "thiếu text", kéo tỉ lệ xuống 0.84 < ngưỡng 0.9 → phân loại NHẦM cả file
   thành `pdf_scan`, đẩy vào nhánh OCR bridge.
2. `src/preprocess/searchable_pdf.py`: nhánh OCR bridge vẽ 1 hình chữ nhật trắng đè lên PIXEL của
   từng span (`draw_rect(fill=(1,1,1))`) rồi chèn thêm 1 lớp text OCR invisible — nhưng KHÔNG xoá
   text object gốc bên dưới (docstring cũ giả định "chạy trên bản copy của 1 scan thật", giả định
   này sai khi (1) đưa nhầm 1 file có text thật vào đây). Kết quả: trang có 2 lớp text object cùng
   tồn tại.
3. babeldoc/pdf2zh đọc PDF qua pdfminer.six (text object), không đọc pixel — nên đọc CẢ 2 lớp,
   dịch và vẽ cả hai → đúng là hiện tượng "đè chữ 2 lần, font lộn xộn" trong ảnh user gửi. Verify
   trực tiếp: 21/25 trang của file output có `n_contents=3` và 2 họ font Việt cùng lúc (`Noto
   Serif *` + `BeVietnamPro-Regular`), mỗi đoạn văn xuất hiện 2 lần ở 2 size khác nhau.

Đo lại trên 1 job chạy đúng nhánh `pdf_digital` (không qua OCR bridge): font size, line-fill-ratio
bình thường, không có tràn dòng dọc hệ thống — xác nhận giả thuyết ban đầu về "tiếng Việt dài hơn
gây tràn dòng có hệ thống" là SAI, chỉ là artifact của bug (1)+(2) ở trên.

**Sửa**:

- `src/core/file_router.py`: loại trang không-text-nhưng-có-ảnh khỏi mẫu số khi tính tỉ lệ
  (`countable_pages = total_pages - pages_image_only`). Nếu mọi trang đều là ảnh
  (`countable_pages == 0`), coi là `pdf_scan` (đúng ngữ nghĩa cũ). Test mới:
  `test_detect_pdf_digital_with_a_few_image_only_pages`.
- `src/preprocess/searchable_pdf.py`: thêm guard defense-in-depth — bỏ qua HOÀN TOÀN bước
  whiteout+chèn OCR cho bất kỳ trang nào ĐÃ CÓ text object thật (`page.get_text().strip()` không
  rỗng), không phụ thuộc `file_router.py` có phân loại đúng hay không. Test mới:
  `test_page_with_existing_text_layer_is_not_double_processed`.
- `src/core/job_orchestrator.py`: giữ nguyên fix `shutil.rmtree(chunk_output_dir)` ở đầu mỗi lần
  gọi `_call_translator()` (race condition thật, độc lập với bug chính, không nên revert).

**Việc KHÔNG làm**: 1 phiên bản trước đó đã thử viết `_fix_vertical_overlaps`/`_redraw_block`
trong `font_shrink.py` để xử lý giả thuyết "tràn dòng dọc do tiếng Việt dài hơn" — Tech Lead verify
bằng thực nghiệm cho thấy hướng này SAI và CÓ HẠI (tự kích hoạt 8-26 lần/trang ngay cả trên trang
tiếng Anh gốc hoàn hảo, do bbox dòng PyMuPDF luôn bao gồm ascender/descender nên overlap ~1pt là
nhiễu nền bình thường, không phải tín hiệu lỗi). Đã revert hoàn toàn trước khi commit, không đưa
vào code.

**Trang bìa**: lỗi mất chữ tiêu đề trên trang bìa (2/3 block tiêu đề lớn "BAKING"/"WORKS" biến mất)
là hệ quả của chính bug (1)+(2) trên — dự kiến tự hết sau khi sách được phân loại đúng `pdf_digital`
và chạy lại. User quyết định: nếu vẫn còn lỗi trang bìa sau khi chạy lại, sẽ chỉnh tay, không đầu
tư thêm code cho trường hợp riêng lẻ này.

Kết quả verify: `pytest -q` → 264/264 pass, `ruff check` sạch trên mọi file sửa/thêm.
`pyproject.toml` bump `1.2.0` → `1.2.1`.

**Việc cần làm tiếp (chưa làm trong lần sửa này)**: chạy lại chính file "How Baking Works" qua
pipeline đã sửa để xác nhận sống (chưa re-run thật sau khi vá — mới verify bằng cách đọc lại logic
+ dữ liệu cũ), rồi mới đóng hẳn báo cáo lỗi của user.

## Increment (2026-09-05) — Phân tích 7 lỗi hiển thị bản dịch v1.2.1 (Tech Lead + Dev)

User báo 7 lỗi hiển thị trên bản PDF dịch thật (mục lục, lời nói đầu, danh mục "Thiết bị và dụng
cụ nhỏ"): (1) không dàn lề 2 bên, (2) ngắt dòng giữa 1 từ, (3) mất chữ (mục 2-19 của 1 danh sách
biến mất), (4) không căn lề 2 bên như bản gốc, (5) font size lên xuống không đều trong cùng 1
đoạn, (6) co font chữ nhưng để lại nhiều khoảng trống, (7) giữ cột hẹp cứng nhắc dù trang không có
cột song song, trong khi tiếng Việt dài hơn tiếng Anh ~15-30%.

**Nguồn xác thực (R5-01)**: Tech Lead đọc trực tiếp source code `babeldoc` đã cài
(`~/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/typesetting.py`,
`.../utils/layout_helper.py`) và chạy `babeldoc --help` thật (executable tại
`~/.local/share/uv/tools/babeldoc/bin/babeldoc`), thay vì suy đoán từ kiến thức chung.

**Kết luận root cause**:

- (1), (4) — không justify: xác nhận `typesetting.py` không có bước justify, chỉ left-align sau
  khi ngắt dòng; `babeldoc --help` không có flag nào điều khiển alignment. Đây là giới hạn kiến
  trúc của engine bên thứ 3, không sửa được từ wrapper của ta.
- (2) — ngắt dòng giữa từ: `LINE_BREAK_REGEX` trong `typesetting.py` (định nghĩa "ký tự không được
  ngắt dòng ở đây") liệt kê Latin-1/Extended A/B/Additional/C nhưng **thiếu khối Combining
  Diacritical Marks U+0300–036F**. Verify bằng Python thật: chữ "chính" ở dạng Unicode NFD (base
  letter + dấu tổ hợp riêng, khác NFC là 1 codepoint đã ghép sẵn) → dấu sắc (U+0301) bị engine coi
  là điểm ngắt dòng hợp lệ, ngay giữa từ. `[CHƯA VERIFY TRÊN FILE LỖI THẬT]` — mới là giả thuyết
  đã chứng minh bằng code, cần đối chiếu Unicode form thật của text babeldoc nhận trước khi đầu tư
  sửa (xem mục "Việc cần làm tiếp" bên dưới).
- (3) — mất chữ: `_layout_typesetting_units` cố tình không drop nội dung khi tràn dọc (comment gốc
  của tác giả: "đừng break ở đây, tiếp tục layout phần còn lại"), nhưng vẫn đặt ký tự ra ngoài
  `box.y2` — có thể rơi ngoài vùng nhìn thấy hoặc bị đè bởi block khác. `[CHƯA VERIFY]` — chưa có
  file lỗi thật để xác nhận đây đúng là cơ chế gây mất chữ quan sát được.
- (7) — cột hẹp cứng nhắc: bounding box truyền cho layout engine lấy nguyên từ model doclayout
  phân tích trên PDF gốc tiếng Anh; không có cơ chế nới box theo ngôn ngữ đích, không có flag CLI
  nào điều khiển việc này. Xác nhận đây là giới hạn kiến trúc, không phải bug.

**Đã sửa (`src/postprocess/font_shrink.py`, thuộc phạm vi code của ta)**:

- (5) — bug thật: `evaluate_span` (bản cũ) quyết định tỉ lệ shrink **độc lập theo từng span**, nên
  2 span cùng 1 dòng thị giác có thể ra 2 cỡ chữ cuối khác nhau. Thêm `_shrink_line`: tính 1 tỉ lệ
  shrink chung cho cả dòng (tỉ lệ khắt khe nhất trong số các span), áp cho mọi span trên dòng đó.
  `evaluate_span` giữ nguyên chữ ký + hành vi cũ (dùng cho test/caller đơn-span độc lập), phần
  logic 3-bước tách ra hàm thuần `_compute_fit` dùng chung cho cả 2 đường.
- (6) — bug thật: `_redraw_span` (bản cũ) luôn neo lại text ở `span_bbox.x0` gốc, để phần rộng
  co được ra làm khoảng trống bên phải. Khi mọi span trên dòng đều redraw được (không có span nào
  vẫn tràn sau condense), `_shrink_line` xếp lại các span trái-sang-phải theo tỉ lệ đã chọn rồi
  canh giữa cả dòng trong `block_bbox`, thay vì để trống dồn 1 bên. Trường hợp dòng có span vẫn
  tràn ngay cả sau condense (US-05 bước 3, không được cắt chữ) thì giữ nguyên vị trí gốc từng span
  — không tự tin repack khi có span "để nguyên", rủi ro cao hơn giá trị.
- Test mới (`tests/test_font_shrink.py`):
  `test_shrink_line_forces_uniform_font_size_across_spans`,
  `test_shrink_line_centers_freed_up_space_instead_of_anchoring_left`. 9/9 test file này pass,
  266/266 toàn bộ suite pass, `ruff check`/`ruff format` sạch.
- `pyproject.toml` bump `1.2.1` → `1.2.2`.

**Việc cần làm tiếp (chưa làm trong lần sửa này, cần trước khi đầu tư thêm vào (2)/(3)/(7))**:
1. Chạy `babeldoc --debug --pages <N>` đúng trang "Thiết bị và dụng cụ nhỏ" bị mất chữ, đọc log
   thật để xác nhận/bác bỏ giả thuyết (3).
2. Mở file PDF dịch thật bằng PyMuPDF, kiểm tra `unicodedata.normalize("NFC", text) == text` cho
   text quanh chỗ ngắt dòng lỗi, để xác nhận/bác bỏ giả thuyết NFC/NFD ở (2) trước khi cân nhắc
   dựng 1 local HTTP shim đứng giữa babeldoc và LLM provider để chuẩn hoá NFC (babeldoc tự gọi LLM
   trong subprocess của nó, ta không có điểm chặn nào khác để sửa text trước khi vào layout
   engine).
3. Thử tắt thử `--split-short-lines` (flag đang hardcode bật ở `babeldoc_runner.py`, mà help text
   gốc của chính flag này cảnh báo "may cause poor typesetting & bugs") trên 1 file mẫu, xem có
   giảm lỗi ngắt dòng không.

## Increment (2026-09-05) — Spike xác nhận root cause + sửa (2) và (3) (Tech Lead + Dev)

Chạy spike đã đề ra ở increment trước, dùng luôn output thật đã có sẵn trong
`data/outputs/7e602723-2844-41f7-8c85-591137001601/translated_vi.pdf` (đúng trang "Thiết bị và
dụng cụ nhỏ" user gửi ảnh) và toàn bộ dữ liệu trung gian trong `data/processing/` của job đó —
không cần chạy lại babeldoc.

**(3) — mất chữ: ROOT CAUSE THẬT ĐÃ XÁC NHẬN, KHÔNG PHẢI LỖI babeldoc.**

Lần theo dữ liệu qua từng bước: `ocr_output/document.md` (OCR MinerU) có đủ 35/35 mục (thứ tự bị
xáo trộn nhẹ, không mất nội dung) → `ocr_bridge/searchable.pdf` (TRƯỚC babeldoc) có đủ 35/35, đúng
thứ tự → `translated_vi.pdf` (SAU babeldoc) chỉ còn 2/35. Input vào babeldoc hoàn chỉnh, output mất
gần hết → lỗi nằm ở bước dịch, không phải layout engine. Đọc `data/processing/.../prompt.txt`
(chính là nội dung `--custom-system-prompt` thật đã gửi cho babeldoc) thấy rule BR-FONT-03 viết
dưới dạng ràng buộc CỨNG: "Bản dịch KHÔNG được dài hơn 130% bản gốc" — không có câu nào nói đầy đủ
nội dung quan trọng hơn giới hạn độ dài. Với đoạn 35 mục liệt kê, LLM không thể vừa dịch hết vừa
giữ ≤130% (tiếng Việt của nhiều thuật ngữ thiết bị dài hơn), nên chọn bỏ mục để tuân đúng ràng buộc
đã ghi rõ — vi phạm chính nguyên tắc "never truncate/cut text" (US-05) mà `font_shrink.py` tuân thủ
ở bước sau.

**(2) — ngắt dòng giữa từ: giả thuyết NFC/NFD ở increment trước BỊ BÁC BỎ**, thay bằng root cause
khác đã verify. Trang mục lục thật của file có lỗi "TỔNG QUAN VỀ QUY TRÌN" / "H NƯỚNG BÁNH 27" —
đọc từng codepoint qua `unicodedata.name()` thì toàn bộ đã là NFC (`Ì` = U+00CC, ký tự ghép sẵn),
không phải base+dấu tổ hợp rời — bác bỏ giả thuyết NFD. Đọc lại `typesetting.py` của babeldoc kỹ
hơn: hàm `_get_width_before_next_break_point` nhận `typesetting_units[i:]` (bắt đầu từ CHÍNH ký tự
đang xét ở vị trí `i`), nên độ rộng ký tự hiện tại bị cộng 2 LẦN vào điều kiện quyết định ngắt dòng
(`current_x + unit_width + width_before_next_break_point`) — với 1 từ không ngắt được như "TRÌNH",
lúc xét đến ký tự cuối "H" điều kiện đòi hỏi khoảng trống dư gấp đôi mức cần thật, khiến engine
ngắt dòng sớm hơn cần thiết, đẩy đúng ký tự cuối "H" xuống dòng sau — khớp chính xác lỗi quan sát
được. Đây là bug thật trong source `babeldoc` (bên thứ 3), không sửa được từ code của ta trừ khi
vendor-patch hoặc báo lỗi lên upstream — **không đưa vào phạm vi sửa lần này**.

**Đã sửa (`src/core/prompt_builder.py`, thuộc phạm vi code của ta — chỉ áp dụng cho (3))**:

- Viết lại `_CONCISENESS_RULE` (dùng cho `build_system_prompt`, out-of-band) và
  `_FILE_CONCISENESS_RULE` (dùng cho `write_prompt_file`, đường render PDF thật — đây mới là bản
  babeldoc/pdf2zh thực sự đọc): giữ nguyên target "≤130%" (BR-FONT-03 không đổi ý nghĩa gốc theo
  PRD.md — vẫn là "target", chưa từng có ý cho phép bỏ nội dung), nhưng nói RÕ đây là mục tiêu chứ
  không phải giới hạn cứng, và khi đoạn có nhiều ý (danh sách nhiều mục) mà không thể vừa đủ ý vừa
  đạt target thì BẮT BUỘC ưu tiên dịch đầy đủ, không được bỏ sót mục nào chỉ để đạt độ dài.
- Test mới (`tests/test_prompt_builder.py`): assert cả 2 đường (`build_system_prompt` và
  `write_prompt_file`) đều chứa "MUC TIEU" + "KHONG duoc bo sot" — regression guard cho đúng bug
  vừa sửa.
- **Lưu ý vận hành phát hiện được khi sửa**: bản đầu tiên của rule mới (diễn giải đầy đủ hơn, dài
  hơn ~2.5x bản gốc) làm 4 test tích hợp (`test_job_orchestrator.py`,
  `test_job_cancel.py`) chuyển từ `status == "completed"` sang `status == "cost_capped"` — vì
  `prompt_overhead_chars` (Architecture.md, `cost_estimator.py`) nhân với `segment_count` mỗi job,
  nên prompt dài thêm dù chỉ vài trăm ký tự cũng cộng dồn đáng kể qua nhiều segment, đẩy cost
  estimate vượt `max_cost_per_job_usd` (default $2.00). Đã rút gọn lại rule (giữ đúng ý, bỏ phần
  diễn giải thừa) để không đổi hành vi cost gate của các job hiện có — nhưng đây là tín hiệu cho
  thấy cost estimate khá nhạy với độ dài prompt, cần cân nhắc mỗi lần sửa `prompt_builder.py` sau
  này, không chỉ lần này.
- Kết quả verify: `pytest -q` → 266/266 pass (bao gồm 23/23 test liên quan
  `test_prompt_builder.py`/`test_job_orchestrator.py`/`test_job_cancel.py` sau khi rút gọn rule),
  `ruff check`/`ruff format` sạch.

**Việc cần làm tiếp**: báo lỗi upstream lên GitHub project của `babeldoc` cho bug (2)
(`_get_width_before_next_break_point` double-count width của unit hiện tại), kèm ví dụ tái hiện
("TỔNG QUAN VỀ QUY TRÌNH NƯỚNG BÁNH" → "...QUY TRÌN" / "H NƯỚNG BÁNH..."). (1), (4), (7) vẫn là
giới hạn kiến trúc của babeldoc, chưa có hướng sửa nào được duyệt.

**Live E2E verify (R5-03/R6-03) cho fix (3), CHẠY XONG, GỌI THẬT khong mock**: unit test ở trên chỉ
assert prompt CHỨA đúng câu chữ mới — không chứng minh được LLM thật có nghe theo hay không. Đã
tách riêng trang "Equipment and smallwares" (page 13 của
`ocr_bridge/searchable.pdf`, job 7e602723-...) thành 1 file PDF 1 trang, dựng prompt bằng đúng
`build_prompt_text()` vừa sửa, gọi thẳng `BabeldocRunner.translate_pages()` thật với DeepSeek API
key thật từ `.env` (không mock, không stub) — cùng code path `JobOrchestrator` dùng trong
production. Kết quả: **đủ 35/35 mục** trong output (trước khi sửa: chỉ 2/35). Có 4 mục (12, 24, 32,
34) ban đầu bị regex kiểm tra bỏ sót vì nằm dính liền cuối dòng trước (không có `\n` phía trước số
thứ tự — hệ quả của lỗi ngắt dòng (2)/(7) vẫn còn, không phải mất nội dung) — đếm lại bằng regex
không neo đầu dòng thì xác nhận đủ cả 35. Kết luận: fix (3) hoạt động đúng trên gọi LLM thật, sẵn
sàng release phần này.

## Increment (2026-09-05) — Live verify fix (5)/(6) phát hiện bug MỚI (8) + đổi font

### Live verify fix (5)/(6) trên trang "Contents" thật: không tìm thấy cơ chế đã "sửa"

Dịch lại thật trang Mục lục (page 6, đúng trang trong ảnh gốc) qua babeldoc + DeepSeek, áp
`_shrink_line` mới lên bản dịch tươi (chưa qua xử lý lần nào): 0/0 dòng có nhiều span khác size
— kể cả nếu chạy lại thuật toán CŨ (per-span, có bug) trên đúng dữ liệu này cũng ra 0. Trường hợp
"khác size trong 1 block" duy nhất tìm được (`CHƯƠNG 1` 11.2pt vs tên chương `NHẬP MÔN LÀM BÁNH`
11.9pt) đối chiếu lại ảnh gốc tiếng Anh thì đây là 2 cấp typography khác nhau CÓ CHỦ ĐÍCH từ bản
gốc (số chương nhỏ, tên chương to+đậm), không phải bug. Kết luận: **chưa có bằng chứng thật nào
cho thấy fix (5)/(6) giải quyết đúng cái user thấy trong ảnh gốc** — cơ chế multi-span-per-line
mà code nhắm tới có thể hiếm/không xảy ra trên đúng cuốn sách này.

### Bug MỚI (8) phát hiện khi đào tiếp: babeldoc để sót glyph gốc tiếng Anh, không "clean"

Tìm đúng trang gây ấn tượng "font/size lộn xộn, nhiều khoảng trắng" (trang 20, "Density and
Thickness", nơi hiển thị `h / liter o f th / d / low. If` rời rạc trong ảnh user gửi). Dump
span-level: các mảnh `"so"`, `"h"`, `"l"`, `"f th"`, `"d"`, `"low. If"` đều mang
`font=Palatino-Light` size=10pt — **chính là font nhúng gốc của sách tiếng Anh** (không phải font
nào code mình từng gán). Input vào babeldoc (`searchable.pdf`) sạch, `n_contents=1`, đủ câu gốc —
corruption xảy ra HOÀN TOÀN bên trong babeldoc.

Test giả thuyết "babeldoc nhầm đoạn văn này thành nội dung bảng nên bỏ qua không dịch" (đoạn nằm
sát 1 bảng số liệu thật, không bật `--translate-table-text`): dịch lại thật trang này với cờ đó
bật — **bác bỏ**, 6 mảnh tiếng Anh vẫn còn nguyên **y hệt toạ độ bbox** dù bản dịch xung quanh đổi
hoàn toàn câu chữ (2 lần chạy LLM cho ra 2 bản dịch khác nhau). Toạ độ bbox giống hệt bất kể nội
dung dịch chứng minh: đây là glyph gốc bị babeldoc **quên xoá (bước "clean" nội bộ)** khi vẽ đè bản
dịch lên, hoàn toàn không phụ thuộc bản dịch — 1 bug babeldoc khác hẳn (2), đặt tên **bug (8):
"leftover original-language glyphs not cleaned"**. Third-party, không sửa được từ code wrapper,
cùng nhóm với (1)/(2)/(4)/(7) — cần báo upstream.

### Phát hiện phụ: `NOTO_FONT_PATH` là no-op với engine `babeldoc`

Đọc trực tiếp source `babeldoc.assets.embedding_assets_metadata.get_font_family()`: "vi" không
phải mã ngôn ngữ babeldoc nhận diện, rơi vào nhánh mặc định `EN_FONT_FAMILY`, mà font "normal"
của nhóm này là `NotoSerif-Regular.ttf`/`NotoSerif-Bold.ttf` — khớp đúng tên font thấy trong PDF
output thật (`font=Noto Serif Regular`). `FontMapper.__init__` lấy font hoàn toàn từ
`babeldoc.assets` (tự tải + verify SHA3-256), **không đọc `NOTO_FONT_PATH`** ở đâu cả — biến này
chỉ có tác dụng với `pdf2zh` (đúng như comment gốc trong `Pdf2zhServiceMapper` đã ghi, nhưng chưa
từng ai verify lại điều này áp dụng đúng cho babeldoc hay không kể từ khi đổi engine — giờ đã
verify: KHÔNG áp dụng). Không có flag CLI nào của babeldoc nhận 1 file font tuỳ ý (`--primary-
font-family` chỉ chọn NHÓM serif/sans-serif/script trong số font babeldoc có sẵn).

### Đã sửa (đổi font `noto_font_path`, KHÔNG sửa được bug (8))

User quyết định: bỏ BeVietnamPro-Regular.ttf, đổi sang font **đồng nhất với font babeldoc tự vẽ**
(vì không có cách nào an toàn ép babeldoc dùng font tuỳ ý — đã thử: tráo file cache bị chặn bởi
SHA3-256 checksum verify của babeldoc, vá source package thì rủi ro mất khi babeldoc update).
Copy thẳng `NotoSerif-Regular.ttf` từ cache asset của babeldoc
(`~/.cache/babeldoc/fonts/NotoSerif-Regular.ttf`) vào `fonts/` của project — verify đủ glyph cho
146/146 ký tự tiếng Việt test (đủ mọi tổ hợp dấu) trước khi dùng, round-trip render/extract khớp
100%.

- `src/core/config.py`: `noto_font_path` default đổi `fonts/BeVietnamPro-Regular.ttf` →
  `fonts/NotoSerif-Regular.ttf`, viết lại comment cho đúng thực tế (babeldoc không đọc biến này,
  file này chỉ để MATCH font babeldoc đã vẽ, không phải để ĐIỀU KHIỂN babeldoc).
- `.env` (không commit git, đã gitignore): `NOTO_FONT_PATH` cập nhật theo.
- `src/services/pdf2zh_service_map.py`, `src/postprocess/font_shrink.py`: cập nhật comment/docstring
  khớp phát hiện ở trên.
- `fonts/BeVietnamPro-Regular.ttf` xoá khỏi repo (không còn nơi nào tham chiếu).
- `tests/test_font_shrink.py`: `_NOTO_FONT_PATH` trỏ sang font mới, cập nhật docstring liên quan.
- Verify: 266/266 test pass, `ruff check`/`ruff format` sạch. Chạy lại `font_shrink_page` (font
  mới) trên đúng output babeldoc thật đã có (equipment list, không tốn thêm API call) — 0 lỗi, chữ
  tiếng Việt không vỡ.
- **Lưu ý rõ**: đây CHỈ sửa vấn đề font-family không đồng nhất giữa phần `font_shrink.py` tự vẽ và
  phần babeldoc tự vẽ (thẩm mỹ) — KHÔNG sửa bug (8) (nội dung tiếng Anh sót lại), bug đó vẫn mở,
  cần báo upstream.

### Trạng thái release

| # | Mô tả | Trạng thái |
|---|---|---|
| 3 | Mất chữ (LLM bỏ sót mục vì rule độ dài) | **Đã sửa, live-verify xong** — release được |
| 5/6 | Font size/khoảng trống (per-span) | Fix đã lên (không sai), nhưng chưa chứng minh được là root cause thật trên sách này |
| 8 (mới) | Sót glyph gốc tiếng Anh chưa clean | babeldoc third-party, chưa sửa được, cần báo upstream |
| font family | font_shrink.py dùng font khác babeldoc | **Đã sửa** — giờ cùng 1 file font |
| 1, 2, 4, 7 | Không justify / ngắt dòng / cột hẹp | babeldoc third-party, chưa sửa được, cần báo upstream |

Release phần đã sửa chắc chắn (3, font family). (5)/(6)/(8)/(1)/(2)/(4)/(7) coi là known issue,
theo dõi riêng, cần báo upstream lên GitHub project của babeldoc.

## Increment (2026-09-06) — File misclassification là root cause thật của bug ngắt dòng/mất chữ (Tech Lead)

User báo lại đúng loại lỗi đã thấy trước (heading 2 dòng ngắt giữa từ, mất 1 đoạn văn, mất ô giá
trị trong Bảng 1.1) trên "How Baking Works". Increment trước đã kết luận đây là giới hạn
third-party của babeldoc (TableParser bị deprecated, typesetting hard-break) — **kết luận đó sai**,
lật lại hoàn toàn bằng live A/B test thật (babeldoc + DeepSeek, cùng file, cùng trang):

- Dịch trực tiếp PDF gốc (`data/uploads/...-libgen.li.pdf`, không qua OCR bridge) qua babeldoc —
  cả với prompt cũ lỗi lẫn prompt mặc định — cho output **hoàn toàn đúng**: heading wrap sạch 2
  dòng, đủ cả 2 đoạn văn, đủ mọi ô Bảng 1.1. Verify bằng `translate_tracking.json` (debug mode) +
  render trực tiếp mono PDF ra ảnh.
- Đối chiếu 1 job thật đã chạy trong hệ thống (`8f07529a...`, `file_type=pdf_scan` trong DB) —
  render đúng y hệt bug user báo cáo (100% khớp: "SỰ C" / "HÍNH XÁC", thiếu đoạn "Most bakery
  items...", bảng thiếu "1 pound"/"1 quart = 0.95 liters").

**Root cause thật**: `_detect_pdf_type()` (`src/core/file_router.py`) tính tỷ lệ trang có text để
phân loại `pdf_digital`/`pdf_scan`. Fix trước (commit `abc5ff0`) đã loại trang **ảnh raster nguyên
trang** (bìa, ảnh minh hoạ) khỏi mẫu số, nhưng bỏ sót trang **chỉ có vector drawing** (trang phân
chương trang trí, không chữ không ảnh raster). File thật có 4/25 trang loại này → `pages_with_text
/ countable_pages = 21/25 = 0.84 < 0.9` → toàn bộ sách 415 trang bị phân loại nhầm `pdf_scan`, kéo
qua OCR bridge (MinerU) oan uổng. Verify trực tiếp bằng `detect_file_type()` trên file thật: trả về
`pdf_scan` dù mọi trang có text đều extract được ngay bằng PyMuPDF (không cần OCR). Bounding
box/layout MinerU tái tạo kém chính xác hơn PDF gốc → babeldoc typeset sai (hard-break giữa từ) và
bỏ sót nội dung khi render trên bản OCR-reconstruct — dù bản thân babeldoc dịch đúng hoàn toàn khi
chạy trên PDF gốc.

**Đã sửa**:
- `src/core/file_router.py`: mở rộng điều kiện loại trừ khỏi mẫu số — trang không text nhưng có
  ảnh **hoặc có vector drawing** (`page.get_drawings()`) đều bị loại (trước chỉ loại trang có ảnh).
  Đổi tên `pages_image_only` → `pages_without_translatable_content` cho đúng ý nghĩa mới.
- `tests/test_file_router.py`: thêm `test_detect_pdf_digital_with_vector_only_divider_pages` —
  tái hiện đúng kịch bản 4/25 trang chỉ có vector drawing, assert phân loại đúng `pdf_digital`.
- Verify: `detect_file_type()` trên file thật giờ trả về `pdf_digital` đúng.

**Đồng thời sửa 1 bug thật khác phát hiện trong lúc audit** (không phải root cause của bug user báo
lần này, nhưng đã verify là 1 bug thật riêng): `src/core/job_orchestrator.py` dùng chung
`write_prompt_file()` (contract `--prompt <file>` của pdf2zh, có `${lang_in}`/`${text}` template
+ footer `Source Text:/Translated Text:`) cho CẢ babeldoc, dù babeldoc's `--custom-system-prompt`
nhận CHUỖI không qua `string.Template` nào và tự thêm JSON-array output contract riêng ngay sau —
2 contract xung đột trong cùng 1 system prompt.
- `src/core/prompt_builder.py`: thêm `build_babeldoc_prompt_text()` + `write_babeldoc_prompt_file()`
  — nội dung riêng cho babeldoc, không có `${...}` template syntax, không có footer pdf2zh.
- `src/core/job_orchestrator.py`: Step 5 rẽ nhánh theo `pdf_translate_engine` khi build prompt file.
- `tests/test_prompt_builder.py`, `tests/integration/test_job_orchestrator.py`: thêm test assert
  nội dung file (không chỉ "được gọi") theo đúng data-lineage discipline của Protocol 6.

**Quyết định kèm theo**: bỏ kế hoạch dual-engine pdf2zh-fallback-cho-bảng (đã cân nhắc ở increment
trước dựa trên kết luận sai về babeldoc) — không cần nữa vì babeldoc dịch bảng đúng khi chạy trên
PDF gốc đúng cách; giữ babeldoc-only cho pipeline dịch.

`pyproject.toml` bump `1.2.3` → `1.2.4`.

**Trạng thái release**: 270/270 test pass, `ruff check`/`ruff format` sạch trên các file đã sửa.
Theo Protocol 5 R5-03/Protocol 6 R6-03 của CLAUDE.md: **CHƯA có live E2E chạy full
`JobOrchestrator` với cả 2 fix cùng lúc trên file thật** — 2 lần live test đã chạy (babeldoc trực
tiếp qua CLI, không qua `JobOrchestrator`/OCR bridge) đều KHÔNG dùng đúng `write_babeldoc_prompt_file()`
mới. User chấp nhận defer việc verify E2E này sang lần dịch thật tiếp theo thay vì chạy ngay —
ghi nhận rõ: `release blocked pending live verification: full JobOrchestrator pipeline (file
classifier fix + babeldoc prompt fix) trên "How Baking Works"`.
