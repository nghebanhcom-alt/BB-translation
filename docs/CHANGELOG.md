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

## Increment (2026-09-06) — Reasoning model + `max_tokens=2048` của babeldoc là root cause thật của mất nội dung hàng loạt (Tech Lead)

User gửi ảnh bản dịch mới (trang Mục lục + Bảng 1.3 "How Baking Works") báo 2 vấn đề: (1) chữ to
nhỏ bất thường trong cùng 1 trang, (2) mất nội dung trầm trọng hơn trước. Đây chính là lần chạy
E2E đầu tiên sau v1.2.4 mà increment trước đã defer
(`release blocked pending live verification: full JobOrchestrator pipeline`).

### Dữ liệu gốc điều tra (job thật, không dựng lại)

Job `425567c9-b959-46bd-9d1e-4e7601155939` (bảng `jobs`, `data/bb_translation.db`):
`file_type=pdf_digital`, `ocr_bridge_path=NULL`, `model=deepseek`, 25 trang, `status=completed`,
35 giây, $0.0623. → **fix file classifier của v1.2.4 hoạt động đúng**: sách KHÔNG còn bị kéo qua
OCR bridge nữa. `data/processing/425567c9-.../prompt.txt` đúng là bản
`build_babeldoc_prompt_text()` mới (không có `${text}`, không có footer `Source Text:`) → **fix
prompt babeldoc cũng đang chạy đúng**. Cả 2 fix v1.2.4 đều KHÔNG phải nguyên nhân lần này.

### Tách bạch babeldoc vs `font_shrink.py` mà không tốn thêm API call

`JobOrchestrator` chạy `font_shrink_page()` trên chính file mono rồi `doc.saveIncr()`
(`src/core/job_orchestrator.py`, Step post_processing) — incremental save nên **revision trước
font_shrink vẫn nằm nguyên trong file**. Cắt file tại `%%EOF` đầu tiên (offset 856835 / tổng
39522799 byte) khôi phục được bản RAW babeldoc. So text từng trang, RAW vs MONO chênh nhau ≤1 ký
tự mỗi trang → **`font_shrink.py` KHÔNG làm mất nội dung**. Mất nội dung đã có sẵn trong output
babeldoc:

| trang | SRC (EN) | RAW babeldoc | mất |
|---|---|---|---|
| 6 (Mục lục) | 1494 | 850 | 43% |
| 7 (Mục lục) | 2074 | 1167 | 44% |
| 13 (Equipment list) | 2798 | 1693 | 39% (chỉ còn mục 1 và 20 trong 35 mục) |
| 20 | 2593 | 1207 | 53% |
| 21 (Bảng 1.3) | 3347 | 1038 | **69%** |

Trang 21 RAW khớp chính xác ảnh user gửi: Bảng 1.3 chỉ còn `" 48 thìa cà phê"` + `"1 pint"`,
mất hẳn các đoạn "Refer to Table 1.3…", "Consider feathers and bullets…".

### (A) ROOT CAUSE — mất nội dung: reasoning model ăn hết `max_tokens=2048` hardcode của babeldoc

Chuỗi bằng chứng (tất cả đều verify trực tiếp, không suy đoán):

1. **Model thật đang dùng là `deepseek-v4-flash`, không phải `deepseek-chat`.** `Settings.deepseek_model`
   default là `deepseek-chat` nhưng bảng `settings` trong DB override thành `deepseek-v4-flash`
   (`deepseek_model` nằm trong `SETTINGS_DB_OVERRIDABLE_FIELDS`). `GET https://api.deepseek.com/models`
   (gọi thật) trả về đúng 3 model: `deepseek-v4-flash`, `deepseek-v4-pro`,
   `deepseek-v4-flash-vision-exp` — đều là dòng reasoning.
2. **babeldoc hardcode `max_tokens=2048`** cho đường dịch chính:
   `babeldoc/translator/translator.py:324` (`OpenAITranslator.do_llm_translate`) và
   `babeldoc/tools/executor/translator.py:74`. Không có flag CLI nào đổi được (grep toàn package
   babeldoc 0.6.4 đã cài: chỉ 2 chỗ này).
3. **Gọi API thật** `deepseek-v4-flash`, `max_tokens=2048`, prompt đúng shape babeldoc
   (`PROMPT_TEMPLATE` + JSON array input):
   `finish_reason="length"`, `usage.completion_tokens_details.reasoning_tokens=2048`,
   `message.content == ""`, `reasoning_content` dài 7839 ký tự. **Toàn bộ ngân sách token bị
   reasoning ăn hết, không còn token nào cho câu trả lời.**
4. **Hệ quả trong babeldoc**: `json.loads("")` →
   `Expecting value: line 1 column 1 (char 0)` → rơi vào `except Exception` ở
   `babeldoc/format/pdf/document_il/midend/il_translator_llm_only.py:852` → cả batch paragraph
   rớt xuống nhánh fallback → nội dung biến mất trên PDF (babeldoc đã xoá glyph gốc rồi).
5. **Tái hiện A/B thật, cùng file, cùng trang 22, cùng prompt.txt, cùng bộ flag của
   `BabeldocRunner`, `--ignore-cache`**:
   - `--openai-model deepseek-chat` → output **3316 ký tự**, đủ Bảng 1.3 (1 tablespoon / 1 cup /
     1 pint / 1 quart / 1 gallon + mọi dòng quy đổi), 0 fallback.
   - `--openai-model deepseek-v4-flash` (đúng production) → output **647 ký tự**, 8 lần
     `try fallback`, Bảng 1.3 chỉ còn `" 2 pints"` — **tái hiện đúng bug user báo**.
   - `--openai-model deepseek-v4-flash --openai-thinking disabled` → output **3292 ký tự**,
     **0 fallback**, đủ Bảng 1.3. Gọi API thật với `thinking={"type":"disabled"}`:
     `finish_reason="stop"`, không còn `reasoning_tokens`, JSON hợp lệ, 147 completion token.

**Lật lại kết luận cũ**: increment 2026-09-05 kết luận bug (3) "LLM bỏ sót mục vì rule độ dài
BR-FONT-03" đã sửa xong và live-verify 35/35 mục trang Equipment. Live-verify đó chạy với
`deepseek-chat`; production chạy `deepseek-v4-flash` — nên trang Equipment trong job thật lại chỉ
còn 2/35 mục (mục 1 và 20). Fix prompt vẫn đúng và vẫn giữ, nhưng **nó chưa bao giờ là ràng buộc
duy nhất**; ràng buộc thật sự khống chế là `max_tokens` + reasoning.

**Đã sửa** (`src/services/babeldoc_runner.py`): thêm `_is_deepseek()` + `_thinking_args()`, chèn
`--openai-thinking disabled` vào `args` của `translate_pages()` **chỉ khi provider là DeepSeek**
(`thinking` là trường riêng của DeepSeek API; gửi cho OpenAI/Gemini/Ollama có thể bị 400).
`--openai-thinking` nằm trong `add_cache_impact_parameters("thinking", ...)`
(`babeldoc/translator/translator.py:255`) nên bật nó tự động invalidate cache babeldoc cũ, không
cần `--ignore-cache`. `_resolve_openai_compat()` giữ nguyên chữ ký (không ảnh hưởng test cũ).

Test mới (`tests/test_babeldoc_runner.py`, assert giá trị cụ thể chứ không chỉ "đã gọi", theo
R6-02): `test_translate_pages_deepseek_disables_thinking` (assert flag CÓ mặt và giá trị ngay sau
nó đúng bằng `"disabled"`), `test_translate_pages_non_deepseek_omits_thinking_flag` (assert flag
KHÔNG có với `_OPENAI_SERVICE`).

**Rủi ro còn lại đã nhận diện, CHƯA sửa**: `max_tokens=2048` là trần cứng của babeldoc cho MỌI
provider. Bất kỳ model reasoning nào khác (`gemini-2.5-flash` đang là default `gemini_model`,
model o-series của OpenAI) đều dính đúng cơ chế này và **không có flag `--openai-thinking` tương
đương** — cần verify riêng trước khi cho phép chọn các model đó cho pipeline PDF.
`[CHƯA VERIFY]` cho gemini/openai.

### (B) ROOT CAUSE — chữ to nhỏ bất thường: babeldoc scale từng paragraph độc lập

Đếm số cỡ chữ khác nhau trên đúng trang Mục lục (page index 6), `get_text("dict")` span-level:

| bản | số cỡ chữ khác nhau | phân bố |
|---|---|---|
| SRC (EN gốc) | 4 | `{9.0: 48, 10.0: 1, 14.0: 14, 30.0: 1}` |
| RAW babeldoc (trước font_shrink) | **9** | `{5.4:1, 6.3:1, 7.65:4, 8.1:24, 10.0:1, 11.2:1, 11.9:5, 12.6:8, 27.0:1}` |
| MONO (sau font_shrink) | **10** | thêm `7.47: 1` (dòng "Hạt lúa mì 68" 8.1 → 7.47) |

Bản gốc: **toàn bộ 48 span mục lục cùng 9.0pt**, heading chương cùng 14.0pt. Sau babeldoc: cùng
loại mục lục đó bị vỡ thành 5.4 / 6.3 / 7.65 / 8.1pt, heading chương vỡ thành 11.2 / 11.9 / 12.6pt.
→ **Nguồn chính của triệu chứng (1) là babeldoc**, không phải code của ta: babeldoc co từng
paragraph độc lập cho vừa bbox riêng của nó (tiếng Việt dài hơn tiếng Anh, mỗi paragraph cần tỉ lệ
co khác nhau), không có cơ chế nào đồng bộ cỡ chữ giữa các paragraph anh em cùng 1 danh sách/bảng.
Không có flag CLI nào của babeldoc 0.6.4 điều khiển việc này.

**Nguồn phụ, thuộc code của ta**: `font_shrink_page()` (`src/postprocess/font_shrink.py`) lặp
`for line in block["lines"]` và gọi `_shrink_line()` **cho từng dòng độc lập** — fix (5)/(6) ở
increment trước chỉ đồng bộ cỡ chữ GIỮA CÁC SPAN TRONG 1 DÒNG, không đồng bộ giữa các DÒNG trong
1 block, càng không giữa các block anh em. Bằng chứng: trên MONO page 6 đúng 1 dòng
("Hạt lúa mì 68") bị co 8.1 → 7.47 trong khi 23 dòng mục lục anh em giữ nguyên 8.1 — lệch 7.8%,
nhìn thấy được. Đây đúng là cơ chế bug (5)/(6) nhưng ở cấp DÒNG thay vì cấp SPAN, và lần này CÓ
bằng chứng thật trên sách này (khác với increment trước, khi không tìm được ca multi-span nào).
Bảng `overflow_reports` cho job này rỗng — vì `OverflowEntry` chỉ được ghi khi `still_overflow`,
mọi lần co thành công đều không để lại dấu vết nào để audit. **CHƯA SỬA** cả 2 điểm này — cần
thiết kế riêng (đồng bộ tỉ lệ co ở cấp block, và log mọi lần co chứ không chỉ lần thất bại).

### Live E2E qua ĐÚNG code path production (R5-03 / R6-03)

3 lần A/B ở trên gọi `babeldoc` CLI trực tiếp. Chạy thêm 1 lần nữa qua đúng chuỗi production
`Settings` → `Pdf2zhServiceMapper().map("deepseek", settings)` → `BabeldocRunner.translate_pages()`
(cùng `prompt.txt` thật của job 425567c9, `deepseek_model="deepseek-v4-flash"` như bảng `settings`,
DeepSeek API key thật, không mock): `service_arg=deepseek:deepseek-v4-flash`, output trang 22 =
**3265 ký tự** (trước fix: 647), có đủ `"16 tablespoon"`, `"gallon"`, `"quart"`, `"Bảng 1.3"`,
và đoạn `"lông vũ"` (Consider feathers and bullets) trước đó biến mất hoàn toàn.

### Trạng thái

| # | Mô tả | Trạng thái |
|---|---|---|
| A | Mất nội dung hàng loạt (reasoning ăn hết `max_tokens=2048`) | **Đã sửa + live-verify A/B/C trên file thật** |
| B1 | Chữ to nhỏ — babeldoc scale từng paragraph độc lập | Third-party, không có flag; chưa sửa được |
| B2 | Chữ to nhỏ — `font_shrink_page` co từng DÒNG độc lập | Đã xác định root cause, **chưa sửa**, cần thiết kế riêng |
| — | `max_tokens=2048` với gemini/openai reasoning model | `[CHƯA VERIFY]` — chặn việc chọn các model đó cho PDF |
| 8 | Sót glyph gốc tiếng Anh chưa clean | babeldoc third-party, vẫn mở |
| 1,2,4,7 | Không justify / ngắt dòng / cột hẹp | babeldoc third-party, vẫn mở |

`pyproject.toml` bump `1.2.4` → `1.2.5`. 272/272 test pass, `ruff check`/`ruff format` sạch.

## Increment (2026-09-06, tiếp) — Giá/chất lượng DeepSeek + Gemini dính đúng bẫy `max_tokens=2048`, đã chặn fail-fast (Tech Lead)

### (1) `deepseek-chat` vs `deepseek-v4-flash`: CÙNG MỘT MODEL, cùng giá

Gọi thật `POST https://api.deepseek.com/chat/completions` và đọc field `model` trong response:
**`deepseek-chat` chỉ là ALIAS, server resolve về đúng `deepseek-v4-flash`.** Khác biệt duy nhất
là mặc định thinking:

| model gửi lên | `model` server trả về | thinking mặc định | `reasoning_tokens` (batch 2 đoạn, `max_tokens=2048`) | `content` |
|---|---|---|---|---|
| `deepseek-chat` | `deepseek-v4-flash` | TẮT | không có | 176 ký tự, JSON hợp lệ |
| `deepseek-v4-flash` | `deepseek-v4-flash` | BẬT | 446 | 303 ký tự (batch nhỏ nên vẫn lọt) |
| `deepseek-v4-flash` + `thinking:{"type":"disabled"}` | `deepseek-v4-flash` | TẮT | không có | 189 ký tự, JSON hợp lệ |

→ A/B ở increment trước ("`deepseek-chat` 3316 ký tự tốt vs `deepseek-v4-flash` 647 ký tự hỏng")
**không phải khác biệt model, mà là khác biệt cờ thinking**. Fix `_thinking_args()` đưa
`deepseek-v4-flash` về đúng hành vi của alias `deepseek-chat`.

**Giá** — nguồn: WebFetch https://api-docs.deepseek.com/quick_start/pricing (fetch thật
2026-09-06). Bảng giá **không còn liệt kê `deepseek-chat`** (đúng với việc nó chỉ là alias);
chỉ còn 3 model, `deepseek-v4-flash` (USD/1M token):

| | cache hit | cache miss | output |
|---|---|---|---|
| off-peak | $0.007 | $0.22 | $0.66 |
| peak | $0.014 | $0.44 | $1.32 |

Peak = 01:00–04:00 và 06:00–10:00 UTC, T2–T6; giờ còn lại off-peak (= 1/2 giá peak).
→ **Giá 2 tên model giống hệt nhau vì là cùng 1 model.** Không có lựa chọn giá nào phải cân nhắc.

**Chất lượng dịch**: cùng model + cùng thinking-off ⇒ tương đương về mặt cấu trúc. Đối chiếu 1
đoạn văn xuôi (không phải bảng số) trên 3 lần chạy thật cùng trang 22 — chỉ khác ở mức chọn từ
đồng nghĩa, **không có đổi nghĩa hay lệch văn phong**: "mật mía" vs "mật đường" (molasses),
"ounce khối lượng" vs "ounce trọng lượng" (weight ounce), "Hãy chú ý rằng" vs "Lưu ý rằng".
Kết luận: **không cần đổi model DeepSeek; giữ `deepseek-v4-flash` + `--openai-thinking disabled`.**

### (2) Gemini: key hoạt động, nhưng dính ĐÚNG bẫy `max_tokens=2048` và babeldoc KHÔNG tắt được

Key user cấp (`AQ.Ab8...`, 53 ký tự — khác định dạng `AIzaSy...` cũ) **hoạt động bình thường** với
endpoint OpenAI-compat `_GEMINI_OPENAI_COMPAT_BASE_URL` mà `babeldoc_runner.py` đang dùng:
`GET .../openai/models` trả về danh sách model đầy đủ. Key hợp lệ, đúng scope.

**Phát hiện 1 — default của project đã chết**: `gemini-2.5-flash` (giá trị trong bảng `settings`)
và `gemini-2.5-pro` (default trong `Settings`) đều trả HTTP 404:
`"no longer available to new users"`. Mọi job Gemini hiện tại sẽ fail ngay từ request đầu tiên.

**Phát hiện 2 — bẫy reasoning tồn tại, giống hệt DeepSeek**. Test thật với batch 30 đoạn (kích
thước thật của 1 trang mục lục/bảng), `max_tokens=2048`. Gemini không trả `reasoning_tokens`
riêng, nhưng tính được: `thinking = total_tokens - prompt_tokens - completion_tokens`:

| model | `finish_reason` | thinking token | `json.loads(content)` |
|---|---|---|---|
| `gemini-flash-latest` | **length** | **2104** | **HỎNG** |
| `gemini-3-flash-preview` | **length** | **1963** | **HỎNG** |
| `gemini-3.1-flash-lite` | stop | 0 | OK |

→ Đúng cơ chế đã gây mất nội dung ở DeepSeek: thinking đốt hết `max_tokens`, nội dung bị cắt,
`json.loads` raise, babeldoc bỏ cả batch, PDF mất nội dung nhưng job vẫn báo `completed`.

**Phát hiện 3 — babeldoc 0.6.4 KHÔNG có knob nào tắt được thinking của Gemini**. Test thật từng
tham số:

| tham số | nguồn | kết quả trên Gemini |
|---|---|---|
| `thinking:{"type":"disabled"}` | flag `--openai-thinking` của babeldoc | **HTTP 400** `Unknown name "thinking": Cannot find field` |
| `reasoning:{"effort":"none"}` | flag `--openai-reasoning` của babeldoc | **HTTP 400** `Unknown name "reasoning": Cannot find field` |
| `reasoning_effort:"none"` | tham số top-level riêng của Gemini | **thinking=0, JSON OK** |
| `extra_body.google.thinking_config.thinking_budget=0` | tham số riêng của Gemini | thinking=0, JSON OK |

Knob DUY NHẤT có tác dụng (`reasoning_effort`) **không có đường nào để babeldoc gửi** — cả 2 flag
babeldoc đều làm Gemini trả 400 (tức là bật lên còn hỏng nặng hơn: fail toàn bộ job).

**Đã sửa (quyết định của Tech Lead — chặn fail-fast thay vì để mất nội dung âm thầm)**:

- `src/services/babeldoc_runner.py`: thêm `_GEMINI_VERIFIED_SAFE_MODELS`
  (`frozenset({"gemini-3.1-flash-lite"})`) + `_assert_gemini_model_safe()`, gọi ở đầu
  `translate_pages()` **trước khi spawn subprocess**. Model Gemini chưa verify → raise
  `UnsupportedForPdfPipelineError` với thông điệp nêu rõ lý do và cách verify để thêm model mới.
  Cùng kỷ luật fail-fast với DeepL (Architecture.md 6.6.1 F7): **một lỗi rõ ràng tốt hơn một file
  PDF mất nội dung mà job báo `completed`** — đây chính xác là kiểu silent failure của Bug #5.
- `src/core/config.py`: `gemini_model` default `gemini-2.5-pro` (đã 404) → `gemini-3.1-flash-lite`.
- Bảng `settings` trong `data/bb_translation.db`: `gemini_model` `gemini-2.5-flash` (đã 404) →
  `gemini-3.1-flash-lite`. Giá trị DB override default nên phải sửa cả 2 chỗ.
- Test mới (assert giá trị cụ thể + assert KHÔNG spawn subprocess, theo R6-02):
  `test_translate_pages_rejects_unverified_gemini_model_before_spawning` (assert
  `create_exec.assert_not_awaited()`), `test_translate_pages_allows_verified_gemini_model` (assert
  có spawn VÀ `--openai-thinking` không lọt sang nhánh Gemini).
- `tests/integration/test_settings_api.py`: cập nhật assert default `gemini_model` theo giá trị mới.

**Cần user quyết (không phải quyết định kỹ thuật)**: `gemini-3.1-flash-lite` là model Gemini DUY
NHẤT hiện an toàn cho pipeline PDF, nhưng là dòng "lite" — chất lượng dịch nhiều khả năng thấp hơn
`deepseek-v4-flash`. Đề xuất: **giữ DeepSeek làm provider mặc định cho PDF**, coi Gemini là dự
phòng. Muốn dùng model Gemini mạnh hơn thì cần vá `max_tokens` của babeldoc hoặc chờ babeldoc
thêm hỗ trợ `reasoning_effort` — cả hai đều là việc upstream.

**Trạng thái**: 281/281 test pass, `ruff check` sạch trên toàn repo, `ruff format` sạch trên các
file đã sửa (drift sẵn có ở `tests/integration/test_settings_api.py` dòng 60/111 KHÔNG do increment
này, đã xác nhận bằng `git stash`).

## Tính năng mới (2026-09-06, theo yêu cầu trực tiếp của user, không thuộc PRD gốc)

PM tự implement (chưa qua Dev riêng ở lượt đầu — xem Protocol 7 mới thêm vào CLAUDE.md, sự cố
này chính là lý do protocol đó ra đời), Reviewer duyệt sau đó (`docs/review-report.md`, APPROVE).

**1. Nút xoá nội dung đã upload/đã dịch**:
- `DELETE /api/upload/{file_id}` (`src/api/routes/upload.py`): xoá file thô + sidecar JSON trên
  đĩa cho file mới upload, CHƯA có Job nào tạo ra từ nó. Không đụng tới Job nào (upload chưa có
  Job cho tới khi `POST /api/jobs` được gọi).
- `DELETE /api/jobs/{job_id}` (`src/api/routes/jobs.py`): xoá 1 Job đã dịch — Job row + `Chunk`/
  `OverflowReport` liên quan (xoá tay, SQLite không cấu hình `ON DELETE CASCADE`) + thư mục
  `data/processing/{job_id}`/`data/outputs/{job_id}`. Từ chối (400) nếu job đang ở trạng thái
  active (`created/queued/chunking/translating/post_processing/merging`) — phải dừng job trước.
  KHÔNG đụng file gốc trong `data/uploads/` (có thể được job khác tham chiếu).
- Frontend: nút "Xoá" trong `web/index.html`/`web/js/app.js` (file card — gọi cả 2 endpoint nếu
  đã có job) và `web/history.html`/`web/js/history.js` (job row — chỉ gọi endpoint job).

**2. Timestamp trong tên file tải về** (`src/api/routes/download.py`): 2 lần dịch cùng 1 file gốc
(vd retry với provider khác) trước đây luôn tải về TRÙNG TÊN (`{stem}_vi.pdf`), không phân biệt
được trong thư mục Downloads. Giờ thêm hậu tố `_{completed_at hoặc fallback updated_at}` định
dạng `%Y%m%d-%H%M%S` vào tên file trả về (Content-Disposition) — không đổi tên file lưu trên đĩa
(`data/outputs/{job_id}/translated_vi.pdf` giữ nguyên), chỉ đổi tên hiển thị khi tải.

Test mới: `tests/integration/test_delete_and_download_naming.py` (7 test ban đầu + 3 test bổ
sung ở "Fix Round" bên dưới cho phần đồng bộ `Batch` counter).

**Trạng thái**: 281/281 test pass tại thời điểm viết tính năng này (trước khi Reviewer nêu 3 issue
non-blocking, xem "Fix Round" ngay dưới đây).

## Fix Round — Reviewer non-blocking findings (2026-09-06)

Dev sửa 3 issue non-blocking nêu trong `docs/review-report.md` (approve tổng thể, không tính vào
Circuit Breaker Dev↔Reviewer vì đây là non-blocking, không phải reject).

1. **`uv.lock` lệch version**: chạy `uv lock` (không `--upgrade`) để đồng bộ `bb-translation`
   1.2.4 → 1.2.5 theo `pyproject.toml`, không đổi version dependency nào khác.
2. **`tests/integration/test_settings_api.py` chưa qua `ruff format`**: chạy `ruff format`, chỉ
   đổi whitespace, không đổi hành vi test (đã re-run, vẫn pass).
3. **`DELETE /api/jobs/{job_id}` không đồng bộ `Batch.completed_files`/`failed_files`** khi xoá
   job thuộc 1 batch (Protocol 6 R6-04 — lỗi data-lineage: `BatchOrchestrator.run_batch()`
   (`src/core/job_orchestrator.py` cuối hàm) chỉ đếm đúng `status == "completed"` vào
   `completed_files` và đúng `status == "failed"` vào `failed_files` — `cancelled`/`cost_capped`
   không được đếm vào bên nào). Sửa `delete_job()` (`src/api/routes/jobs.py`): trước khi xoá Job
   row, nếu `job.batch_id` khác None, load `Batch` tương ứng (bỏ qua an toàn nếu không tìm thấy)
   và giảm đúng 1 trong 2 counter tương ứng theo `job.status` lúc xoá, clamp tối thiểu 0.
   Test mới trong `tests/integration/test_delete_and_download_naming.py`:
   `test_delete_completed_job_decrements_batch_completed_files`,
   `test_delete_failed_job_decrements_batch_failed_files` (assert giá trị counter cụ thể sau khi
   xoá, đúng tinh thần R6-02, không chỉ assert status code 204),
   `test_delete_job_without_batch_does_not_error` (job không thuộc batch nào vẫn xoá bình thường).

**Trạng thái**: 284/284 test pass (`.venv/bin/python -m pytest tests/ -q`), `ruff check` và
`ruff format --check` sạch trên mọi file đã sửa trong round này.

## 5 tính năng bổ sung (2026-09-06, PM phân công Dev — không thuộc PRD gốc, không liên quan bug
line-break đang Tech Lead phân tích riêng)

**a. Thêm vào glossary từ lịch sử dịch**:
- `POST /api/glossary` (`src/api/routes/glossary.py`): thêm 1 cặp thuật ngữ đơn lẻ, khác `/import`
  (dành cho cả file Excel). Dùng lại `GlossaryManager.bulk_import()` (BR-GLOSS-03 "last-updated-wins"
  trên trùng `term_en`, case-insensitive theo BR-GLOSS-02) với list 1 phần tử, scope cố định
  "global" (UI hiện tại chưa hỗ trợ chọn project glossary). 400 nếu `term_en` rỗng sau khi strip.
- Frontend: nút "+ Glossary" trên mỗi hàng job ở `web/history.html` mở modal nhỏ (EN/VI) —
  `web/js/history.js` (`openAddGlossary()`, `saveGlossaryTerm()`) gọi endpoint trên.

**b. Hiển thị chi phí thực tế trong lịch sử**: `Job.actual_cost`/`estimated_cost` đã có sẵn trong
`JobDetail` (`src/api/routes/jobs.py`, không cần đổi backend). Chỉnh `web/history.html`/
`web/js/history.js` (`formatCost()`): hiện `$X.XX (nguồn)` khi có `actual_cost`, hiện
`ước tính: $X.XX` khi job chưa xong nhưng có `estimated_cost`, hiện `-` khi không có dữ liệu nào —
trước đây ô này để trống thay vì "-" khi cả hai đều null.

**c. Nút "Xóa tất cả" cho file đã upload**: `web/js/app.js` — `removeAllFiles()` (1 xác nhận duy
nhất cho cả danh sách, khác `removeFile()` hỏi từng file) tái dùng logic xóa hiện có
(`_deleteFileRecord()`, factor ra từ `removeFile()` cũ) gọi tuần tự `DELETE /api/jobs/{id}` +
`DELETE /api/upload/{file_id}` cho từng file — KHÔNG thêm endpoint bulk-delete mới ở backend (danh
sách này thường chỉ vài file/session, xóa tuần tự đủ nhanh và tránh nhân đôi logic lỗi). Nút ở
`web/index.html`.

**d. Sắp xếp mới nhất lên đầu + hiển thị timestamp file đã upload**:
- `UploadMetadata`/`UploadResponse` (`src/api/routes/upload.py`) thêm field `uploaded_at` (ISO 8601
  string, ghi lúc `POST /api/upload` xử lý xong). Field có default `""` để sidecar JSON cũ (tạo
  TRƯỚC feature này, thiếu key `uploaded_at`) vẫn đọc được qua `UploadMetadata(**data)` mà không
  raise `TypeError` — xem test `test_resolve_upload_tolerates_sidecar_without_uploaded_at`.
- `web/js/app.js`: `sortFilesDesc()` sắp xếp `files` giảm dần theo `uploaded_at` (file mới
  upload) hoặc `job.created_at` (job phục hồi từ `restoreRecentJobs()`, không có `uploaded_at`
  riêng) — gọi sau `handleFiles()` và `restoreRecentJobs()`. `formatUploadDate()` hiện
  "dd/MM/yyyy HH:mm" (`toLocaleString("vi-VN")`) cạnh thông tin file trong `web/index.html`.

**e. Hiển thị version app**: `GET /api/version` (`src/api/main.py`, `_read_app_version()`) đọc
trực tiếp `pyproject.toml` bằng `tomllib` (stdlib, project yêu cầu Python >=3.12) ở runtime — không
dùng `importlib.metadata.version()` vì app chạy từ source, không `pip install`, nên metadata package
không đảm bảo tồn tại. Trả `{"version": "unknown"}` nếu đọc lỗi thay vì 500. Frontend:
`web/js/app.js` (`loadVersion()`) fetch lúc `init()`, hiện ở footer `web/index.html`.

Test mới: `tests/integration/test_glossary_api.py` (3 test cho `POST /api/glossary`),
`tests/integration/test_version_and_upload_timestamp.py` (5 test: `GET /api/version` khớp
`pyproject.toml`, `uploaded_at` có trong response + sidecar, tương thích ngược sidecar cũ).

**Trạng thái**: 291/291 test pass (`.venv/bin/python -m pytest tests/ -q`), `ruff check` và
`ruff format --check` sạch trên toàn repo. Chưa qua Reviewer/QA — chờ bước tiếp theo trong pipeline
(Protocol 7: không tự báo "xong" khi chưa có Reviewer thật).

## Fix bug line-break/bullet-list — F1/F2/F4 (2026-09-06, theo Root Cause Analysis của Tech Lead
trong Architecture.md, section "Root Cause Analysis: Line-break/List Regression")

Dev implement đúng theo đề xuất Tech Lead (không tự suy đoán lại root cause). Chi tiết root cause
đầy đủ (RC-1/RC-2/RC-3, nguồn xác thực L1-L8) xem Architecture.md, không lặp lại ở đây.

**F1 — Bỏ `--split-short-lines` khỏi list hardcode** (`src/services/babeldoc_runner.py:278` cũ):
đây là root cause chính (RC-1) — babeldoc tự cảnh báo flag này "may cause poor typesetting & bugs"
(VERIFIED `babeldoc/main.py:179-182`, babeldoc 0.6.4 đã cài); nó tách đoạn dựa trên `median_width`
tính trên TOÀN TRANG (`paragraph_finder.py:822-839`), gây tách sai cả đoạn văn thường trên trang có
bảng/layout hẹp cạnh body full-width.

**F2 — Đưa flag thành tham số có kiểm soát**: `BabeldocRunner.translate_pages()` thêm
`split_short_lines: bool = False` + `short_line_split_factor: float | None = None` — chỉ gửi
`--short-line-split-factor` khi `split_short_lines=True` (VERIFIED `paragraph_finder.py:891` dùng cả
2 giá trị trong cùng 1 điều kiện `and`, factor một mình không có tác dụng). `Pdf2zhRunner.translate_pages()`
nhận cùng 2 tham số nhưng bỏ qua (docstring giải thích lý do — giữ đồng bộ signature 2 engine, tránh
`if engine == ...` ở `JobOrchestrator`, Architecture.md 6.14.7). `Settings` (`src/core/config.py`)
thêm `babeldoc_split_short_lines: bool = False` + `babeldoc_short_line_split_factor: float = 0.5`
(`.env`-only, cùng nhóm với `pdf_translate_engine`/`babeldoc_executable` — không phải thao tác UI
thường ngày). `JobOrchestrator._process_chunk()` (`src/core/job_orchestrator.py`) truyền 2 giá trị
này vào lời gọi `translate_pages()` thật — test data-lineage (R6-02) mới trong
`tests/integration/test_job_orchestrator.py`:
`test_babeldoc_split_short_lines_defaults_to_disabled`,
`test_babeldoc_split_short_lines_setting_reaches_translate_pages_call` (assert giá trị kwargs cụ
thể, không chỉ `assert_awaited()`).

**F4 — Sửa prompt babeldoc cho đúng cấp độ fragment** (RC-3, `src/core/prompt_builder.py`,
`_BABELDOC_TYPOGRAPHY_RULES`): babeldoc gọi LLM dịch TỪNG paragraph đã tách sẵn (không phải cả khối
list) — chỉ thị cũ "bullet list phải dịch thành bullet list" áp lên 1 fragment đã mất ký tự bullet
khiến LLM có xu hướng tự thêm lại bullet/newline; babeldoc chỉ `.strip()` 2 đầu (VERIFIED
`il_translator_llm_only.py:718,987,998`) nên newline nội bộ đó sống sót vào output. Prompt mới nói
rõ: input là MỘT fragment đơn lẻ, dịch thành ĐÚNG MỘT đoạn, KHÔNG tự chèn newline, KHÔNG tự thêm
bullet/số thứ tự nếu bản gốc không có sẵn. Biến thể `_FILE_*`/`_TYPOGRAPHY_RULES` (pdf2zh, EPUB) giữ
nguyên — không đổi, vì các đường đó LLM thấy cả khối list thật.

**Live verify thật (không chỉ mock)**: chạy `babeldoc` 0.6.4 CLI thật + DeepSeek API thật, dịch
trang 14 của file thật `data/uploads/898a567a-..._How baking works..._libgen.li-1-25.pdf` (trang có
numbered list 35 mục "1." đến "35." trong layout 2 cột hẹp — đúng điều kiện gây lệch `median_width`
RC-1 mô tả). Kết quả đo được (PyMuPDF, đếm text block + số mục còn đứng dòng riêng):

| | có `--split-short-lines` (CŨ) | không có flag (F1, MỚI) |
|---|---|---|
| Số text block/trang | 36 | 11 |
| Số mục numbered giữ đúng dòng riêng | 31/35 | 4/35 |

**Phát hiện quan trọng cần báo lại PM/Tech Lead**: F1 giảm mạnh over-fragmentation của đoạn văn
thường (36→11 block — đúng triệu chứng RC-1 "xuống dòng chưa chính xác" mà user báo), NHƯNG làm
NẶNG HƠN việc gộp dòng cho numbered list cụ thể này (31/35 → 4/35 mục còn dòng riêng) — vì digit
marker ("1.", "2."...) KHÔNG nằm trong `BULLET_POINT_PATTERN` của babeldoc (VERIFIED
`layout_helper.py:50-52`, đúng RC-2 Tech Lead đã chỉ ra), nên numbered list loại này phụ thuộc HOÀN
TOÀN vào chính heuristic vừa bị tắt để được tách. Đây là tradeoff ĐÃ ĐƯỢC Tech Lead dự đoán trước
trong RC-2 ("Dash-bullet và numbered list hoàn toàn phụ thuộc vào RC-1 để được tách"), không phải
regression mới do Dev gây ra — nhưng nghĩa là F1 một mình KHÔNG giải quyết dứt điểm triệu chứng
"numbered list" cho loại tài liệu này. `Settings.babeldoc_split_short_lines=True` (F2) cho phép bật
lại heuristic cho tài liệu cần nó, đánh đổi lại rủi ro RC-1 trên phần còn lại của trang. F3 (chuẩn
hoá bullet/numbered marker ở bước tiền xử lý, mở rộng nhận diện cho digit) vẫn NGOÀI PHẠM VI lần
này theo đúng chỉ đạo — cần Tech Lead/PM quyết định có làm tiếp hay chấp nhận giới hạn.

**Test mới**:
- `tests/test_babeldoc_runner.py`: xoá assertion cũ `assert "--split-short-lines" in args` (N4 chỉ
  ra đây là "test tự xác nhận giả định sai"); thêm `test_translate_pages_omits_split_short_lines_by_default`,
  `test_translate_pages_enables_split_short_lines_when_requested`,
  `test_translate_pages_omits_factor_flag_when_split_short_lines_disabled`; thêm 3 golden-file test
  đọc CẤU TRÚC PDF thật bằng PyMuPDF (`test_golden_source_page_has_35_numbered_items`,
  `test_split_short_lines_true_golden_output_over_fragments_numbered_list`,
  `test_split_short_lines_false_golden_output_reduces_page_wide_fragmentation`) dựa trên fixture
  thật `tests/fixtures/babeldoc/page14_*.pdf` (capture từ chính live verify ở trên, không phải mock
  viết tay — Protocol 5 mục 3).
- `tests/test_prompt_builder.py`: `test_babeldoc_prompt_tells_llm_input_is_single_fragment_no_newlines`.
- `tests/integration/test_job_orchestrator.py`: 2 test data-lineage nêu ở phần F2.

**Trạng thái**: 300/300 test pass (`.venv/bin/python -m pytest tests/ -q`, tăng từ 291 do 9 test
mới), `ruff check`/`ruff format --check` sạch trên đúng các file đã sửa (không chạy tràn lan trên
toàn `src/`/`tests/` — bài học từ lần trước). Chưa commit git, chưa tự sửa `docs/review-report.md`.
Chờ Reviewer + QA thật (Protocol 7) trước khi coi là xong.

## F3 — Spike verify (Protocol 5 R5-02) KHÔNG thành công, KHÔNG implement (2026-09-06)

PM yêu cầu làm F3 (Architecture.md "Root Cause Analysis: Line-break/List Regression" N5): làm
babeldoc nhận diện numbered/lettered list marker ("1.", "2.", "a)") như bullet point, để tận dụng
nhánh `is_bullet_point` (chạy độc lập với `--split-short-lines`, không bị ảnh hưởng bởi F1). Theo
đúng Protocol 5 R5-02, Dev spike verify TRƯỚC khi implement đầy đủ — spike THẤT BẠI ở bước cơ chế
nền tảng, KHÔNG code gì được ship trong task này.

**Đọc source xác nhận (Protocol 5 R5-01, babeldoc 0.6.4 đã cài)**:
- `is_bullet_point(char)` (`layout_helper.py:55-65`) chỉ nhận 1 `PdfCharacter` — regex
  `BULLET_POINT_PATTERN` trên `char.char_unicode` của ký tự đầu dòng (`chars[0]`). babeldoc KHÔNG
  expose field/flag nào để app tự đánh dấu 1 đoạn/dòng là bullet (loại trừ phương án 3 PM đề xuất
  ban đầu) — chỉ có đường tiền xử lý TEXT (phương án 2).
- **Phát hiện quan trọng, chưa từng biết trước đây**: việc xây dựng thứ tự ký tự trong 1 dòng
  (`paragraph_finder.py:696,738,772`) KHÔNG sort theo x-coordinate — 3 dòng `all_chars.sort(...)`/
  `line_chars.sort(...)` đều bị COMMENT OUT trong source thật. Nghĩa là thứ tự `chars[0]` phụ thuộc
  thứ tự EXTRACTION gốc từ file PDF, không phải vị trí trái-phải trên trang.

**Spike thực hiện** (live, không mock — cùng file mẫu trang 14 "How baking works" đã dùng verify F1):
dùng PyMuPDF `page.insert_text(..., render_mode=3)` chèn 1 ký tự "•" VÔ HÌNH ngay trước mỗi marker
"1.", "2." (giữ nguyên số thật hiển thị — đúng yêu cầu PM "đừng làm mất số thứ tự"), rồi chạy
`babeldoc` 0.6.4 CLI thật + DeepSeek API thật trên file đã chèn.

**Kết quả spike — THẤT BẠI theo 2 lý do độc lập, cả 2 đều đã verify bằng dữ liệu thật**:
1. **Không cải thiện gì**: số mục numbered list giữ dòng riêng vẫn y hệt baseline (4/35, không đổi)
   — đúng như phát hiện source ở trên dự đoán: ký tự chèn thêm KHÔNG được xếp vào vị trí `chars[0]`
   của dòng dự định, mà bị gom vào 1 nhóm tách biệt ở cuối luồng xử lý.
2. **Làm hỏng nội dung output** (đúng rủi ro PM cảnh báo trước, giờ đã CONFIRM bằng thực nghiệm):
   babeldoc tự vẽ lại (re-render) TỪ ĐẦU mọi ký tự nó trích xuất được, KHÔNG tôn trọng render mode
   vô hình (`Tr 3`) gốc của PDF nguồn. Verify bằng ảnh render trực tiếp: ký tự "•" hoàn toàn vô hình
   trong file NGUỒN (trước khi qua babeldoc), nhưng xuất hiện thành 1 khối 35 dấu "·" HIỂN THỊ THẬT
   ở cuối trang trong file OUTPUT — nội dung rác mới, không có trong bản gốc.

**Kết luận**: đây KHÔNG phải vấn đề heuristic nhận diện marker chưa đủ chặt (chuỗi tăng dần, phân
biệt "2 cups flour" với "2. Trộn bột", loại trừ mục lục — các yêu cầu chống false-positive PM gửi
sau đó) — mọi tinh chỉnh heuristic phía DETECTION đều vô nghĩa vì cơ chế INJECTION (chèn ký tự đánh
dấu cho babeldoc nhận diện) đã thất bại ở tầng nền tảng của babeldoc, không phải do input chưa đủ
chính xác. Sửa triệt để đòi hỏi hiểu/patch hành vi re-render + thứ tự extraction nội bộ của
babeldoc — đúng loại "fork babeldoc" mà Architecture.md N5/F3 đã chủ động loại trừ ngay từ đầu vì
chi phí/rủi ro vượt xa lợi ích.

**Quyết định**: KHÔNG implement F3 trong task này. Escalate lại cho PM/Tech Lead để quyết định
phương án khác — các lựa chọn còn lại: (a) chấp nhận F3b (known limitation của babeldoc 0.6.4 cho
numbered/lettered list, đúng như Architecture.md N5 đã dự phòng), mở issue upstream; (b) dùng F2
(`Settings.babeldoc_split_short_lines=True`, đã ship) làm giải pháp tạm cho riêng tài liệu nhiều
numbered list, chấp nhận đánh đổi rủi ro RC-1 trên phần còn lại của trang; (c) hướng khác ngoài
phạm vi hiểu biết hiện tại (vd tự thay thế module render của babeldoc — rủi ro/chi phí cao, chưa
đánh giá). Không có code nào được thêm vào `src/`; không cần cập nhật test/fixture nào (fixture
trang 14 hiện có từ F1 vẫn giữ nguyên, không đổi).

## Đảo ngược default `babeldoc_split_short_lines`/`babeldoc_short_line_split_factor` (2026-09-06,
theo đo lường mở rộng 21 lần chạy thật của Tech Lech)

**Bối cảnh**: sau khi F1/F2 ship (default `babeldoc_split_short_lines=False`,
`babeldoc_short_line_split_factor=0.5`, dựa trên 1 lần đo trên 1 trang), Tech Lead đo lại trên quy
mô lớn hơn nhiều: **21 lần chạy babeldoc + DeepSeek thật** (7 trang đại diện 5 loại bố cục — văn
xuôi thuần, bảng, bảng hẹp+caption, mix, mục lục, list ngắn, list 35 mục — × 3 cấu hình: `False`,
`True/factor=0.5`, `True/factor=0.8`), qua đúng production code path
(`BabeldocRunner.translate_pages()` + `Pdf2zhServiceMapper`). Chi tiết đầy đủ + bảng số liệu thô:
Architecture.md section "Đo lại F1 trên nhiều trang — kết quả live A/B/C".

**Kết quả đảo ngược cả 2 kết luận ban đầu**:
1. **RC-1 (tách nhầm đoạn văn thường) hẹp hơn nhiều so với suy luận từ đọc source.** Trong toàn bộ
   7 trang × 3 cấu hình, **không một đoạn văn xuôi nào bị tách vụn** ở bất kỳ cấu hình nào. Tác hại
   thật của RC-1 chỉ giới hạn ở vài caption bảng/ảnh ngắn (2/7 trang, mức độ nhẹ) — không phải mối
   lo lan rộng toàn trang như phân tích ban đầu (dựa trên đọc source, chưa đo) đã suy luận.
2. **`factor=0.5` (cấu hình đã ship) là TỆ NHẤT trong 3 phương án đo được**, không phải lựa chọn
   "trung dung, giảm false-positive" như suy luận lúc chọn. Nó giữ gần như trọn vẹn lỗi gộp danh
   sách của `False` (trang mục lục: vẫn 7 lỗi dính chữ y hệt; trang list 35 mục: 21/28 lỗi còn
   nguyên) trong khi VẪN phải trả gần đủ giá RC-1 (cắt caption y hệt `factor=0.8`) — tức nhận gần
   như toàn bộ tác hại và rất ít lợi ích. Ngược lại, `factor=0.8` (đúng bằng default gốc của
   babeldoc, không phải phát minh riêng) xử lý numbered list/mục lục tốt RÕ RỆT: trang mục lục 7
   lỗi dính chữ → 0; trang list 35 mục 28 lỗi dính chữ → 3, số mục đứng dòng riêng 3/35 → 26/35.

**Quyết định (User)**: đổi default trong `src/core/config.py`:
- `babeldoc_split_short_lines`: `False` → **`True`**
- `babeldoc_short_line_split_factor`: `0.5` → **`0.8`**

**File đã sửa**:
- `src/core/config.py` — đổi 2 default trên; viết lại toàn bộ comment giải thích, ghi rõ LỊCH SỬ 2
  lần đổi default (không xoá lý do cũ, chỉ rõ tại sao lý do đó sai — cả 2 lần đều dựa trên đo thật,
  không phải đoán, chỉ là lần đầu đo trên mẫu quá nhỏ/hẹp).
- `src/services/babeldoc_runner.py` — sửa lại docstring `translate_pages()`: bỏ đoạn giải thích cũ
  "Mac dinh False vi tac hai lan rong hon toan bo trang" (SAI theo số liệu mới), thay bằng con trỏ
  tới `src/core/config.py`/Architecture.md thay vì lặp lại số liệu (tránh 2 nguồn dễ lệch nhau khi
  đổi default lần sau).
- `tests/integration/test_job_orchestrator.py` — viết lại hoàn toàn 2 test data-lineage (Protocol 6
  R6-02): `test_babeldoc_split_short_lines_defaults_to_enabled_with_babeldoc_factor` (đổi tên +
  logic từ `..._defaults_to_disabled`, giờ assert default `True`/`0.8` là hành vi ĐÚNG, kèm giải
  thích đầy đủ lịch sử 2 lần đổi trong docstring) và
  `test_babeldoc_split_short_lines_can_be_opted_out_via_settings` (đổi hướng từ test "opt back in"
  cũ sang test "opt-out" — vì giờ đây bật là mặc định, tắt mới là override).
- `tests/test_babeldoc_runner.py` — thêm ghi chú CORRECTION vào 2 khối comment (trước danh sách
  test opt-in flag, và trước 2 golden-file test dùng fixture trang 14 cũ) làm rõ: số liệu trong file
  này là snapshot lịch sử của 1 lần đo đơn lẻ, không phải khuyến nghị hiện tại — không sửa số liệu
  gốc (fixture PDF không đổi, vẫn đúng sự thật của chính nó), chỉ sửa phần DIỄN GIẢI để không còn
  gây hiểu nhầm "default nên là False".

**Trạng thái**: 300/300 test pass (`.venv/bin/python -m pytest tests/ -q`, không đổi so với trước —
đây là sửa giá trị default + docstring, không thêm/bớt test), `ruff check`/`ruff format --check`
sạch trên đúng các file đã sửa. Đây là đảo ngược 1 quyết định đã qua Reviewer approve trước đó
(F1/F2) — chưa tự sửa `docs/review-report.md`, cần Reviewer duyệt lại lần cuối trước khi coi bug
line-break/bullet-list là closed.

## US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) (2026-09-06, Dev, theo thiết kế
Tech Lead đã spike/verify thật — Architecture.md "US-16 — Nen anh sau khi ghep")

**Bối cảnh**: job `babeldoc` render ảnh raw (không nén) vào từng chunk, khiến file merge
cuối cùng phình rất to (đo thật trên 1 job production 415 trang: 846.79 MB, 81.6% dung
lượng nằm ở 357 ảnh `Filter: null`). Tech Lead đã spike + verify sống toàn bộ contract
PyMuPDF liên quan (version 1.28.2, signature, tuple `get_page_images(full=True)`, hành vi
`update_stream`/`xref_set_key`) trước khi giao Dev — không có phần nào `[UNVERIFIED]` trừ
nhánh `/SMask`/`/ImageMask` (0 mẫu thật, nhưng thiết kế bỏ qua an toàn theo mặc định).

**File mới**:
- `src/postprocess/image_compress.py` — `compress_pdf_images(pdf_path, *, jpeg_quality=85)`
  (async) + dataclass `ImageCompressStats`. Duyệt xref ảnh duy nhất mỗi trang, bỏ qua ảnh đã
  có filter (`DCTDecode`/`CCITTFaxDecode`/...), bỏ qua `/ImageMask` và ảnh có `/SMask`
  (log warning), encode lại bằng `pymupdf.Pixmap(doc, xref).tobytes("jpeg", jpg_quality=85)`
  (KHÔNG dùng `extract_image`/`replace_image` — Pillow không có trong `.venv`, xem
  Architecture.md S4), guard ảnh nở file sau encode, ghi `/ColorSpace` theo `pix.n` (bắt
  buộc — ảnh cũ là `ICCBased`, để nguyên key cũ sẽ ra màu sai). Ghi ra file tạm cùng thư
  mục rồi `os.replace()` (PyMuPDF không cho save đè file đang mở). Dedupe **không**
  implement — spike đo thật trên file production trên chỉ đạt 4.2% giảm thêm, dưới ngưỡng
  20% của BR-IMGCOMP-04 (Architecture.md S3) — defer về backlog, không phải "quên".

**File đã sửa**:
- `src/core/job_orchestrator.py` — gọi `compress_pdf_images(merged_path)` trong khối `try`
  của Step 8, **sau** `merge_chunk_pdfs(...)` và **sau** guard rỗng-chữ BR-OCR-03, **trước**
  `job.output_path = str(merged_path)`; chỉ khi
  `self._settings.pdf_translate_engine == "babeldoc"` (BR-IMGCOMP-01). Nhánh `pdf2zh` không
  đổi một dòng hành vi nào. Thứ tự sau guard BR-OCR-03 là cố ý (Architecture.md S5): nếu nén
  chạy trước, một lỗi nén sẽ bị chẩn đoán sai thành "bản dịch không chứa chữ nào".

**Test**:
- `tests/test_image_compress.py` (mới) — chạy `compress_pdf_images` thật (không mock) trên
  golden fixture có sẵn `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf` (1 ảnh
  raw + 3 DCTDecode + 1 CCITTFaxDecode, verified live). Assert: file nhỏ hơn, số trang/text
  không đổi, mọi filter khác `null` sau khi chạy, và các ảnh đã nén sẵn giữ nguyên byte
  stream (so sánh theo nội dung byte, không theo số xref — phát hiện thêm trong lúc viết
  test: `doc.save(..., garbage=4, ...)` renumber/loại bỏ xref không dùng, nên xref của cùng
  1 ảnh KHÔNG ổn định qua lần save này, phải so bằng nội dung).
- `tests/integration/test_job_orchestrator.py` — 3 test mới theo Protocol 6 R6-02 (không
  chấp nhận `assert_awaited()` trần): `test_babeldoc_engine_compresses_merged_output_with_correct_lineage`
  (assert `compress_pdf_images` được gọi đúng `merged_path`, không phải `job.file_path`),
  `test_pdf2zh_engine_does_not_compress_images` (assert KHÔNG được gọi khi engine pdf2zh),
  `test_empty_translation_fails_before_compress_runs` (assert nén không chạy khi guard
  BR-OCR-03 đã fail job trước đó).

**Trạng thái**: `.venv/bin/python -m pytest tests/ -q` → 307/307 pass (thêm 7 test mới:
3 ở `test_image_compress.py`, 3 ở `test_job_orchestrator.py`, không tính 1 test cũ đã có).
`ruff check`/`ruff format --check` sạch trên toàn bộ file đã sửa/tạo. Điểm S8 của
Architecture.md (`merge_chunk_pdfs()` cũng đang save không nén, ảnh hưởng cả nhánh pdf2zh)
**chưa xử lý** — Tech Lead ghi rõ đây là quyết định (A)/(B) chờ PM/user, mặc định giao Dev
là (A) = không đụng `chunk_merge.py`/nhánh `pdf2zh`, nên Dev giữ nguyên, không tự chọn (B).
Đây là code implement chưa qua Reviewer thật (Protocol 7 R7-01) — PM sẽ tự giao Reviewer
riêng trước khi coi US-16 là "xong".

**Reviewer** (`docs/review-report.md`, mục cuối): **APPROVE**. R6-04 trace tay xác nhận
`compress_pdf_images(merged_path)` nhận đúng biến bắt nguồn từ `merge_chunk_pdfs()`, không
phải `job.file_path`. R5-04: "External contract verified against real source: YES" (đối
chiếu `jpg_quality`, `compress=0`, thứ tự tuple `get_page_images` với Architecture.md S1-S4).
2 issue non-blocking: rò file tạm `.tmp.pdf` nếu `doc.save()` lỗi giữa chừng; filter dạng
array chưa có dữ liệu thật để kiểm chứng.

**QA** (`docs/test-report.md`, mục cuối): verify độc lập trên **bản copy** file production
thật `data/outputs/3594a7a3-.../translated_vi.pdf` (846.79MB, 415 trang) — không đụng file
gốc (MD5 khớp trước/sau). Kết quả: 846.79MB → 19.34MB (−97.7%), 415/415 trang,
1.160.121/1.160.121 ký tự khớp từng trang, ảnh CMYK không đảo màu (pixel-diff trung bình
0.009/255). Tất cả acceptance criteria US-16 PASS, mục dedupe ghi N/A (loại khỏi scope theo
BR-IMGCOMP-04). **ready_for_release: YES**.

## Release v1.2.6 (2026-09-06)

`pyproject.toml` bump `1.2.5` → `1.2.6`. Nội dung: US-16 (nén ảnh sau ghép, chỉ engine
babeldoc) — xem chi tiết ở trên. 307/307 test pass, `ruff check`/`ruff format --check` sạch.
Không có blocker mới phát sinh từ US-16; các blocker non-blocking tồn đọng từ trước (AIMD
Claude/Gemini spike, thứ tự duplicate-check/cost-gate, v.v. — xem `project_state.json`
`blockers`) không liên quan tới US-16, giữ nguyên trạng thái không chặn release.

## P0 — Babeldoc Layout Bug Fix Roadmap: gate đo lường + pin version (2026-09-07)

Implement **P0.1** và **P0.3** của roadmap đã chốt tại `docs/Architecture.md`
"Final Decision: Babeldoc Layout Bug Fix Roadmap" (U4). **P0.2** (thí nghiệm A/B) đang chạy
live song song — kết quả (4 câu hỏi) được append riêng vào `docs/Architecture.md` khi xong,
không ghi ở đây để tránh trùng lặp 2 nguồn.

**P0.1 — Gate chất lượng hậu kiểm (`src/services/layout_qa.py`, module mới)**: hàm
`run_layout_qa_gate(translated_pdf_path, source_pdf_path=None)` chạy 5 kiểm tra bằng
PyMuPDF, đúng bảng đặc tả U4/P0.1:
- (a) cặp block text giao nhau > 5% diện tích block nhỏ hơn (`get_text("blocks")`) — tái sử
  dụng đúng ngưỡng/logic script T3-a đã chạy thật.
- (b) text vượt qua đường viền vẽ (`page.get_drawings()`, chỉ xét drawing có nét stroke).
- (c) text đè lên ảnh (`page.get_image_rects()`).
- (d) pre-scan chữ xoay trên file GỐC (`line["dir"]` ngoài 0/90° ± 0.1°, đúng ngưỡng babeldoc
  `il_creater.py:968-974`) — chính là G1d, xuất phụ lục text cho QA, không phải sản phẩm giao
  người đọc cuối.
- (e) bảo toàn thực thể số+đơn vị (nhiệt độ/khối lượng-thể tích/thời gian/phân số) — match
  block gốc↔dịch theo IoU bbox (không so toàn trang), heuristic có ghi rõ giới hạn trong
  docstring (không phải NLP entity-matching chính xác 100%).

Output là **hàng đợi review theo trang, xếp hạng mức nghiêm trọng** (`LayoutQaReport.page_queue`,
sắp giảm dần theo `severity_score`) — không phải 1 kết quả pass/fail toàn tài liệu, đúng yêu
cầu tường minh của Tech Lead. Kết quả ghi vào bảng mới `layout_qa_findings`
(`src/models/layout_qa.py`, đăng ký trong `src/models/__init__.py`/`database.py`) qua
`persist_findings()` — điều kiện bắt buộc để P0.2 so sánh được giữa các lần chạy A/B.

**Test** (`tests/test_layout_qa.py`, 19 test): theo Protocol 5 R5-03 + Protocol 6 R6-02 — dùng
PDF thật đã trích ở `tests/fixtures/babeldoc/` (`rotated_text_p67_source.pdf`,
`rotated_chart_p15_source.pdf`, `toc_2col_p7_source.pdf`), assert GIÁ TRỊ CỤ THỂ đo được (góc
xoay `-11°`/`20°`, `dir=(0.9816…, -0.1908…)` khớp đúng số đã ghi ở Architecture.md T3(d), số
cặp overlap thật đo trên fixture) — không phải chỉ "gate chạy không lỗi". 2 test cho check (e)
dùng PDF do chính `fitz` vẽ ra (không phải mock hành vi babeldoc/pdf2zh — chỉ kiểm logic
regex+bbox-matching của module này) để kiểm soát được trường hợp mất 1 thực thể cụ thể.
`persist_findings()` test bằng 1 fake session tối thiểu, assert đúng field ghi vào row (không
dùng `AsyncMock` + `assert_called()` trần).

**P0.3 — Pin `babeldoc==0.6.4`**: repo chưa có script/CI tự động hoá việc cài `babeldoc`
(chỉ có hướng dẫn thủ công tại `docs/Architecture.md` 6.14.6) — sửa dòng lệnh đó thành
`uv tool install --python 3.12 "babeldoc==0.6.4"`, kèm ghi chú lý do (U1/U4/V-4: mọi số đo
T3/U1/U2 và toàn bộ thiết kế G1e đều gắn với đúng hành vi bản 0.6.4).

**Giả định tự chọn (không tự đoán, ghi rõ ở đây theo yêu cầu PM)**:
1. `page_number` trong `LayoutQaFinding`/`LayoutQaFindingData` là **1-indexed** (khác
   `fitz.Page.number` 0-indexed) để khớp cách Architecture.md/UX report gọi trang ("trang 67").
2. Severity map cố định: `overlap`/`text_over_drawing`/`text_over_image` = `critical` (khớp
   UX-A/UX-B trong `ux-review-report.md`), `rotated_text_prescan`/`entity_loss` = `blocker`
   (khớp UX-C, Blocker theo UX report) — Architecture.md không tự chỉ định nhãn severity cụ
   thể cho từng check, chỉ nói "xếp hạng mức nghiêm trọng".
3. `job_id` trên bảng `layout_qa_findings` là **nullable** + thêm `run_label`/`source_file` —
   vì P0.2 chạy babeldoc/pdf2zh ngoài `JobOrchestrator` (không tạo `Job` row thật), cần cách
   phân biệt các lần chạy A/B mà Architecture.md chưa đặc tả tên cột.
4. Ngưỡng match IoU tối thiểu cho check (e) chọn `0.05` (lỏng, vì block dịch có thể lệch toạ
   độ khỏi bản gốc — chính RC-T1) — chưa có con số nào trong Architecture.md, sẽ cần tinh
   chỉnh khi có dữ liệu QA thật soi qua gate.

**Trạng thái**: `uv run pytest -q` → 326/326 pass (19 test mới, không có test nào bị vỡ).
`ruff check`/`ruff format --check` sạch trên mọi file đã sửa/tạo. Đây là code thay đổi hành vi
runtime (P0.1) — **CHƯA qua Reviewer thật** (Protocol 7 R7-01) — PM sẽ tự spawn Reviewer riêng
trước khi coi P0 là "xong".

**Phát hiện phụ (ngoài scope, đã tách task riêng)**: trong lúc chạy P0.2, soi `ps aux` phát
hiện `BabeldocRunner.translate_pages()` truyền API key thật qua CLI argument
`--openai-api-key` (không chỉ qua `env=`) — vi phạm chính nguyên tắc bảo mật ghi trong
docstring đầu file `src/services/pdf2zh_service_map.py` ("API keys always go through envs...
never through argv, which any local user could read via ps"). `Pdf2zhRunner` không mắc lỗi
này. Chưa sửa trong task này (ngoài phạm vi P0.1/P0.2/P0.3) — đã tách thành task riêng cho
PM/Dev sau.

**P0.2 — Thí nghiệm A/B (spike, không phải code sản phẩm)**: chạy babeldoc/pdf2zh THẬT (không
mock) trên trang 7/13/15/63/67 của file production `f88282bb-…-Foundations (1).pdf`, 5 cấu
hình đúng spec U4/P0.2 (1 trang / chunk 1-40 & 39-80 giống production / chunk + `--max-pages-
per-part 4` / chunk + `--translate-table-text` / pdf2zh cùng bộ trang), khoá cache đúng thứ tự
(chạy 1-trang trước để làm ấm, không truyền `--ignore-cache` sau đó). Kết quả đầy đủ (bảng số
liệu, 4 câu trả lời) đã append vào `docs/Architecture.md` mục "Kết quả thí nghiệm A/B — P0.2
(2026-09-07, Dev)" ở cuối file — không lặp lại ở đây để tránh 2 nguồn lệch nhau. Tóm tắt cực
ngắn: (1) không tái hiện được đúng cặp đoạn UX-D đã biết ở bất kỳ cấu hình nào lần này — giữ
`[UNVERIFIED]`; (2) `--max-pages-per-part 4` không cải thiện đo được → **không implement P1.3**;
(3) `--translate-table-text` gần như không đổi gì trên trang 63 → giữ nguyên P2.3; (4) pdf2zh
không mất nội dung trên trang chữ xoay (khác babeldoc mất trắng) nhưng duỗi thẳng góc nghiêng +
dịch dở dang 1 phần khối — chỉ nên là phương án dự phòng cuối cho P1.1, không đảo ngược thứ tự
ưu tiên G1e đã chốt. Phát hiện phụ: gate P0.1-a (overlap) bị "ngợp" bởi hàng trăm nghìn cặp
block cực nhỏ/trùng lặp trên trang dày đặc (mục lục/bảng) — cần lọc/dedupe ở vòng tinh chỉnh
sau, ghi nhận nhưng không sửa trong task này.

Artifact thô của thí nghiệm (script + JSON debug + PDF output của 11 lần chạy) lưu ngoài repo
tại thư mục scratchpad của session Dev — chưa export vào `tests/fixtures/babeldoc/` (Protocol
5 mục 3), vì đây là dữ liệu spike 1 lần chưa chốt làm golden fixture lâu dài.

## Increment (2026-09-07) — P1.1 (G1e overlay chữ xoay) + P1.2 (prompt bất biến nội dung), Dev

Theo đúng `docs/Architecture.md` "Final Decision: Babeldoc Layout Bug Fix Roadmap" U3/U4 (P1.1,
P1.2) — **KHÔNG làm P1.3** (đã loại bỏ ở P0.2, `--max-pages-per-part` không cải thiện đo được).

**P1.2 — viết lại rule "súc tích" trong `src/core/prompt_builder.py` (cả 3 biến thể:
`_CONCISENESS_RULE`/`_FILE_CONCISENESS_RULE`/`_BABELDOC_CONCISENESS_RULE`)**:
- Bỏ HOÀN TOÀN con số phần trăm/giới hạn độ dài khỏi cả 3 prompt (kể cả dạng "≤130%... không
  phải giới hạn cứng" — bản thân con số đó đã đủ để lần trước LLM tự suy diễn thành hard cap và
  lược bỏ định lượng, xem increment "2026-09-05" ở trên).
- Thêm yêu cầu bất biến nội dung tường minh: số, đơn vị, nhiệt độ, thời gian, tên nguyên liệu,
  số bước phải đủ trong bản dịch, tuyệt đối không bỏ/gộp/làm tròn.
- Khuyến khích văn phong cô đọng ở phần KHÔNG ảnh hưởng định lượng — không kèm con số nào.
- Chốt chặn chất lượng vẫn là gate P0.1-e (`src/services/layout_qa.py`, đã có sẵn từ P0.1) —
  không sửa gate này ở increment này.
- **Bẫy đã gặp lại và tự sửa trong lúc làm**: bản đầu tiên của rule mới dài hơn ~2.4x bản cũ,
  làm 4 test tích hợp (`test_job_orchestrator.py`, `test_job_cancel.py`) chuyển từ
  `status=="completed"` sang `status=="cost_capped"` — CHÍNH XÁC cái bẫy đã ghi trong increment
  "2026-09-05" (`prompt_overhead_chars` nhân với `segment_count` trong `cost_estimator.py`).
  Đã rút gọn lại cả 3 rule (giữ đúng ý, bỏ diễn giải dư) để độ dài chỉ dài hơn bản cũ ~24 ký tự
  thay vì ~285 — 4 test trên xanh trở lại.
- Test: viết lại `tests/test_prompt_builder.py` — assert KHÔNG có `\d+%` nào trong prompt (cả
  3 đường `build_system_prompt`/`write_prompt_file`/`write_babeldoc_prompt_file`) + assert có
  đủ các từ khoá bất biến nội dung (`BAT BIEN NOI DUNG`, `nhiet do`, `don vi`, `so buoc`,
  `KHONG duoc bo sot`).

**P1.1 — overlay chữ xoay bằng PyMuPDF `insert_text(morph=...)` (G1e), module mới
`src/postprocess/rotated_text_overlay.py`**:
- Data lineage đúng U4/P1.1 (R6-01): `rotated_blocks` quét từ `source.pdf` (TÁI SỬ DỤNG logic
  detect ở check (d) của `src/services/layout_qa.py` — refactor `_line_angle_deg`/`_is_rotated`
  thành `line_angle_deg`/`is_rotated` PUBLIC, giữ alias tên cũ để không đổi lời gọi nội bộ module
  đó) → `translated_blocks` từ LLM provider THẬT của app (`TranslationProvider.translate()`,
  tham số hoá qua `pricing_provider` mà `JobOrchestrator` đã tạo sẵn cho job đó — KHÔNG bao giờ
  gọi lại babeldoc/pdf2zh CLI cho bước này) → overlay lên `merged_path` (file babeldoc đã merge).
- Chính sách fit (U5/U7-E1): bóp font tối đa tới 70% (`MIN_FONT_SCALE`), KHÔNG bao giờ thấp hơn.
  Không vừa dù đã bóp 70% → KHÔNG overlay đè (giữ nguyên chỗ trống babeldoc để lại) + FLAG bằng
  CHÍNH cơ chế `layout_qa_findings` đã có từ P0.1 (`check_type="rotated_text_overlay_flag"`,
  hằng số `ROTATED_OVERLAY_FLAG_CHECK` mới thêm vào `src/services/layout_qa.py`, severity
  `blocker`) — không tạo bảng mới, dùng lại `persist_findings()`.
- Nối vào pipeline: `src/core/job_orchestrator.py` gọi `overlay_rotated_text()` ngay SAU
  `merge_chunk_pdfs()` và TRƯỚC `compress_pdf_images()` (đúng U6/RK-3), chỉ khi
  `pdf_translate_engine=="babeldoc"` VÀ feature flag mới `Settings.babeldoc_rotated_text_overlay`
  (mặc định `True`, `.env`-only giống `pdf_translate_engine`, dùng để rollback tức thời).
- Feature flag mới: `babeldoc_rotated_text_overlay: bool = True` trong `src/core/config.py` —
  KHÔNG thêm vào `SETTINGS_DB_OVERRIDABLE_FIELDS` (cùng lý do `pdf_translate_engine`: đổi engine
  behaviour không phải thao tác UI thường ngày).
- Best-effort: lỗi trong `overlay_rotated_text()` được log + nuốt (không làm fail job) — job vẫn
  hoàn thành với bản dịch chính đã đúng, chỉ thiếu phần overlay chữ xoay.

**Giả định tự chọn (chưa có spec chính thức, ghi rõ theo yêu cầu brief thay vì âm thầm đoán)**:
1. **Gộp nhóm dòng xoay thành đoạn văn**: babeldoc/PyMuPDF tách 1 đoạn văn xoay nhiều dòng (vd
   "16 dòng nghiêng -11° ở trang 67") thành nhiều block PyMuPDF riêng (mỗi block ~1 dòng). Không
   có spec nào định nghĩa cách gộp lại — đã tự chọn heuristic `group_rotated_lines()`: cluster
   theo góc (bucket 1°), sort theo trục vuông góc với hướng chữ, gộp các dòng liên tiếp nếu
   khoảng cách chiếu ≤ `1.8×` cỡ chữ lớn hơn (`_PARAGRAPH_GAP_FONT_MULTIPLE`). Verify thật trên
   2 fixture: trang 67 (đoạn văn liền mạch) gộp đúng thành 1 khối 17 dòng; trang 15 (bảng quy
   đổi xoay, nhãn rời rạc) tách đúng thành 6 khối riêng thay vì gộp cả trang thành 1 đoạn vô
   nghĩa. Chưa test trên tập lớn hơn — cần theo dõi khi có dữ liệu QA thật.
2. **Kích thước khung gốc để fit chữ**: không có field "bbox khung gốc" tường minh cho 1 đoạn
   văn xoay nhiều dòng — đã tự tính bằng cách chiếu 4 góc bbox mỗi dòng lên trục dọc theo hướng
   chữ (độ rộng 1 dòng) và trục vuông góc (tổng chiều cao cả khối), verify bằng spike thật cho
   ra width/height hợp lý so với hình dạng trực quan của khối (xem `_block_extents()`).
3. **Lỗi overlay là best-effort, không fail job**: không có spec nào nói rõ hành vi khi bước
   overlay lỗi — chọn nuốt lỗi + log, vì đây là tính năng UX bổ sung lên trên 1 pipeline dịch đã
   hoạt động đúng, và khớp tinh thần "feature flag để rollback tức thời" mà brief đề xuất.

**Test mới**: `tests/test_rotated_text_overlay.py` (10 test, PyMuPDF thật, không mock hình học —
Protocol 5 R5-03) dùng 2 fixture có sẵn `tests/fixtures/babeldoc/rotated_text_p67_source.pdf` /
`rotated_chart_p15_source.pdf`. Điểm đáng chú ý:
- `FakeTranslationProvider` là 1 implementation THẬT của `TranslationProvider` (không phải
  `AsyncMock` bọc `assert_called()`) — mọi test overlay assert GIÁ TRỊ CỤ THỂ được vẽ lên PDF
  output khớp ĐÚNG những gì fake provider trả về (không phải text tiếng Anh gốc) — đúng kỷ luật
  R6-02.
- Nhánh FLAG (không vừa dù đã bóp tới 70%) có test riêng: assert `overlaid_block_count==0`,
  `flagged_block_count==1`, finding đúng `check_type`/`severity`, và text KHÔNG xuất hiện trong
  PDF output (không đè chữ vỡ lên trang).
- "babeldoc output đã mất chữ xoay" được mô phỏng bằng redaction PyMuPDF THẬT (`add_redact_annot`
  + `apply_redactions`) trên bản copy của file gốc — một thao tác PyMuPDF hợp lệ, không phải nội
  dung babeldoc tự bịa ra (Protocol 5 mục 3: không viết mock tay theo giả định).

**Trạng thái**: `uv run pytest -q` → 336/336 pass (14 test mới: 10 ở
`test_rotated_text_overlay.py`, 4 test cũ trong `test_prompt_builder.py` được viết lại — không
tăng net count vì thay thế assertion cũ). `ruff check`/`ruff format --check` sạch trên mọi file
đã sửa/tạo. Đây là code thay đổi hành vi runtime quan trọng (đụng `JobOrchestrator`, engine
babeldoc) — **CHƯA qua Reviewer thật** (Protocol 7 R7-01) — PM sẽ tự spawn Reviewer riêng trước
khi coi P1.1/P1.2 là "xong".

**File đã thay đổi/tạo mới**:
- Mới: `src/postprocess/rotated_text_overlay.py`, `tests/test_rotated_text_overlay.py`
- Sửa: `src/core/prompt_builder.py`, `tests/test_prompt_builder.py`, `src/core/job_orchestrator.py`,
  `src/core/config.py`, `src/services/layout_qa.py`

## Fix Reviewer REJECT vòng 1/3 (Dev↔Reviewer, P1.1 overlay chữ xoay) — R6-04

Reviewer vòng 1 REJECT 1 blocking issue: `job_orchestrator.py:520` gọi
`overlay_rotated_text(source_pdf_path=file_path, ...)` — dùng `file_path` (file scan gốc, KHÔNG
có text layer) thay vì `translation_source_path` (biến cầu nối OCR mà Step 7 đã dùng đúng cho
babeldoc/pdf2zh). Vì `pdf_translate_engine=babeldoc` độc lập với `job.file_type`, tổ hợp
`PDF_SCAN + babeldoc` là hợp lệ trong production — khi đó `scan_rotated_lines()` chạy trên ảnh
scan không chữ, luôn trả `[]`, khiến toàn bộ overlay P1.1 âm thầm không bao giờ chạy cho sách
scan, đúng hình dạng Bug #5 (silent failure, không log lỗi nào).

**Đã sửa**:
1. `job_orchestrator.py:524` — đổi `source_pdf_path=file_path` → `source_pdf_path=
   translation_source_path`. Cập nhật lại comment phía trên (dòng ~499-508) để nêu rõ đây là
   CÙNG biến Step 7 dùng, tránh tái phạm.
2. Tách `try/except` quanh `overlay_rotated_text()` và `persist_findings()` thành 2 khối riêng
   (non-blocking #1 của Reviewer) — trước đây gộp chung 1 `except Exception`, nếu
   `persist_findings()` lỗi (vd DB constraint) SAU KHI overlay đã chạy đúng và trả về finding
   FLAG hợp lệ, finding đó biến mất im lặng, QA không bao giờ biết trang nào cần soi tay
   (U7-E3). Giờ log message phân biệt rõ lỗi overlay vs lỗi persist, kèm số finding bị mất nếu
   persist lỗi.
3. Cập nhật docstring module `prompt_builder.py:1-14` (non-blocking #2) — câu "never the real
   PDF render path" không còn đúng 100% vì `overlay_rotated_text()` giờ dùng `build_system_prompt()`
   làm `glossary_prompt`, và kết quả dịch từ đó được vẽ thẳng vào `translated_vi.pdf` giao cho
   user.
4. Ghi chú rủi ro bucket góc 1° (non-blocking #3) trực tiếp tại định nghĩa
   `_ANGLE_GROUP_TOLERANCE_DEG` trong `rotated_text_overlay.py` — không sửa logic (Reviewer không
   yêu cầu), chỉ ghi rõ để người sau biết đây là rủi ro đã cân nhắc, chưa gặp trên fixture hiện có.

**Test mới** (R6-02 — assert giá trị lineage cụ thể, không chỉ `assert_called()`):
`tests/integration/test_job_orchestrator.py::test_pdf_scan_babeldoc_overlay_uses_bridge_not_original`
— dựng job `file_type=pdf_scan` + `pdf_translate_engine=babeldoc`, mock `overlay_rotated_text`
tại `src.core.job_orchestrator.overlay_rotated_text`, assert
`overlay_spy.await_args.kwargs["source_pdf_path"] == expected_bridge` (đường dẫn OCR bridge thật,
`processing/<job_id>/ocr_bridge/searchable.pdf`) VÀ `!= Path(job.file_path)` — đúng loại lineage
guarantee mà `test_pdf_scan_babeldoc_engine_translates_bridge_not_original` đã verify cho bước
dịch chính, giờ verify thêm cho bước overlay.

**Kết quả cuối**:
```
uv run pytest -q            → 337 passed (336 + 1 test mới), 420 warnings
uv run ruff check           → All checks passed! (job_orchestrator.py, prompt_builder.py,
                               rotated_text_overlay.py, tests/integration/test_job_orchestrator.py)
uv run ruff format --check  → 4 files already formatted
```

**Trạng thái**: Vòng 1/3 (Dev↔Reviewer) đã dùng. Gửi lại Reviewer vòng 2 — KHÔNG tự báo cáo "xong",
PM sẽ tự spawn Reviewer.

## Bug #6 Phase 1 + task P0 (logging) — 2026-09-07

Theo `docs/Architecture.md` mục "Bug #6 — Final Decision sau phản biện Domain Expert" (V6, QUYẾT
ĐỊNH CUỐI). Chỉ làm task P0 + Phase 1 (FLAG, không sửa hình học) — **Phase 2 (tái tạo góc xoay
thật trong bản dịch) KHÔNG được implement**, chỉ là thiết kế đã chốt, chờ điều kiện kích hoạt
(job `pdf_scan` thật trong production sinh ra ≥ 1 finding).

### Task P0 — logging handler

`Settings.log_level` đã tồn tại từ trước trong `src/core/config.py` nhưng KHÔNG có handler nào
đọc nó — `logger.warning(exc_info=True)` ở mọi nhánh best-effort (`overlay_rotated_text()`,
`job_orchestrator.py`) im lặng hoàn toàn trong production (QA Vòng 6 mục 8 đã xác nhận bằng thực
nghiệm). Thêm `_configure_logging()` trong `src/api/main.py`, gọi ngay ở module-level (trước khi
`FastAPI(...)` khởi tạo): gắn 1 `StreamHandler` (stdout) vào logger `"src"` (cha chung của mọi
`logging.getLogger(__name__)` trong `src/`, vì mọi module ở đây đều bắt đầu bằng `src.`) ở mức
`Settings.log_level`, `propagate=False` để tránh log kép nếu sau này root logger cũng có handler.
Cố ý KHÔNG đụng root logger / logger `uvicorn`/`uvicorn.access` — giữ nguyên logging riêng của
uvicorn.

### Phase 1 — phát hiện chữ xoay trong ảnh scan (chỉ FLAG)

**Module mới `src/services/mineru_det_probe.py`** (đặt ở `services/`, chịu Protocol 5, cùng loại
với `babeldoc_runner.py`/`pdf2zh_runner.py` — wrapper gọi tool ngoài qua subprocess):

1. Render mỗi trang PDF scan thành PNG 200 DPI bằng PyMuPDF, gọi subprocess bằng interpreter
   MinerU (`Settings.mineru_python_path`, mặc định `~/.local/share/uv/tools/mineru/bin/python`)
   chạy `PytorchPaddleOCR(lang="en").ocr(img, det=True, rec=True)` — **verify trực tiếp trên máy
   Dev** (không phải chạy lại theo trí nhớ): script subprocess tái tạo **CHÍNH XÁC** golden
   fixture của Tech Lead (18/18 dòng nghiêng, cùng góc chính xác tới 3 chữ số thập phân, median
   -10.8565°) khi chạy thật trên `tests/fixtures/babeldoc/rotated_text_p67_source.pdf`.
2. Lọc `score >= 0.8` và `|angle| >= 3.0°` (`parse_det_probe_output()`).
3. Quy đổi toạ độ poly px@200DPI → point (`72/200`).
4. Ghép với `middle.json` của CHÍNH job đó (`match_lines_to_middle_json()`): fuzzy text match
   (`difflib.SequenceMatcher`, chuẩn hoá khoảng trắng + casefold, ngưỡng 0.6) + ràng buộc khoảng
   cách trọng tâm < 0.5 × chiều cao dòng. Góc của khối = **median** (không phải mean — khoá bởi
   test, tránh outlier kiểu -23.43° trong golden fixture làm lệch kết quả).
5. Ghi finding qua `persist_findings()`/`LayoutQaFindingData` đã có sẵn từ P0/P1 — **không tạo
   bảng mới**. `angle_deg`/bbox nằm trong `detail` (cột JSON tự do đã có sẵn, cùng cách
   `_check_rotated_text_prescan()` đã lưu `angle_deg` cho 1 check_type khác) — **không cần** mở
   rộng schema `LayoutQaFindingData`/`LayoutQaFinding` vì cột `detail` vốn đã là JSON tự do.
   check_type mới `rotated_text_scan_unsupported` (severity `blocker`) được thêm vào
   `src/services/layout_qa.py` cùng chỗ với `ROTATED_OVERLAY_FLAG_CHECK`.
6. Nối vào `JobOrchestrator._build_ocr_bridge()` (method mới `_run_rotated_text_probe()`) — chạy
   CHỈ khi `file_type == PDF_SCAN` (độc lập engine dịch), SAU khi có `middle.json` của job, dùng
   ĐÚNG `file_path` (ảnh scan gốc CHƯA whiteout — không phải bridge đã whiteout, detector sẽ
   không tìm thấy gì trên bridge) + `middle_json_path` CỦA CHÍNH job đó (Protocol 6 R6-01 lineage).
   Best-effort giống hệt `overlay_rotated_text()`: 2 khối try/except riêng (lỗi detect vs lỗi
   persist), không bao giờ làm fail job. Cũng chạy cho nhánh resumable (`job.ocr_bridge_path` đã
   tồn tại) bằng cách suy ra `middle.json` từ đường dẫn `ocr_output/` cố định.
7. Feature flag `Settings.mineru_det_probe_enabled` (mặc định `True`) — cùng kiểu rollback tức
   thời với `babeldoc_rotated_text_overlay`.
8. Golden fixture `tests/fixtures/mineru/det_probe_p67.json` (đã có sẵn trong repo từ Tech Lead)
   dùng làm dữ liệu test, không viết tay.

**Test mới**: `tests/test_mineru_det_probe.py` (10 test) + 3 test tích hợp trong
`tests/integration/test_job_orchestrator.py`. Điểm đáng chú ý (Protocol 6 R6-02 — assert giá trị
cụ thể, không chỉ `assert_called()`):
- `test_angle_sign_matches_pymupdf_dir`: khoá dấu góc bằng cách đọc `dir` THẬT từ
  `rotated_text_p67_source.pdf` qua PyMuPDF (median -11.0°) và so với median góc detector
  (-10.8565°) — cùng dấu, sai lệch < 1.5°. Không suy luận suông theo cảnh báo của Architecture.md.
- `test_match_lines_to_middle_json_groups_into_one_block_with_median_angle`: assert đúng 1 khối,
  đúng 18 dòng, `angle_deg` khớp median mong đợi trong dung sai ±1.5°.
- `test_probe_persists_findings_for_pdf_scan_job`: assert **có hàng thật** trong bảng
  `layout_qa_findings` (AsyncSession sqlite in-memory thật, không mock session).
- `test_run_det_probe_real_subprocess` (Protocol 5 R5-03): gọi detector MinerU THẬT, skip (không
  fail) nếu máy không có venv MinerU (`is_mineru_interpreter_available()`). **Đã chạy PASS thật
  trên máy Dev** (venv MinerU có sẵn từ trước).
- 3 test tích hợp trong `test_job_orchestrator.py`: lineage (probe nhận đúng `file_path` gốc +
  đúng `middle.json` của job), best-effort không fail job khi probe lỗi
  (`MineruDetProbeUnavailableError`), và tắt hoàn toàn qua flag.

**Giả định tự chọn** (không có spec chính thức, ghi rõ theo yêu cầu — không dừng lại hỏi):
1. Nhóm "nhiều dòng liền kề" thành 1 khối dựa theo RANH GIỚI BLOCK của `middle.json`
   (`preproc_blocks[i]`) thay vì tự viết heuristic khoảng cách mới — tái sử dụng cấu trúc
   MinerU đã tự nhóm (paragraph/title), đúng với trường hợp "16 dòng nghiêng -11° ở trang 67"
   (MinerU đã gộp cả 16 dòng vào 1 block).
2. Probe chạy trên nhánh resumable (`_build_ocr_bridge()` early-return) bằng cách suy ra đường
   dẫn `middle.json` cố định (`ocr_output/middle.json`) thay vì bỏ qua hoàn toàn — giữ tính chất
   "độc lập với trạng thái resumable" của tính năng best-effort này.
3. `angle_deg` lưu trong `detail` JSON thay vì thêm cột mới trên `LayoutQaFinding` — vì cột
   `detail` vốn đã tự do, thêm cột mới sẽ là thay đổi schema không cần thiết.

**Kết quả cuối**:
```
uv run pytest -q            → 350 passed (337 + 13 test mới), 437 warnings
uv run ruff check           → All checks passed!
uv run ruff format --check  → 7 files already formatted
```

**File đã thay đổi/tạo mới**:
- Mới: `src/services/mineru_det_probe.py`, `tests/test_mineru_det_probe.py`
- Sửa: `src/api/main.py` (P0 logging), `src/core/config.py` (`mineru_python_path`,
  `mineru_det_probe_enabled`), `src/core/job_orchestrator.py` (wiring + `_run_rotated_text_probe()`),
  `src/services/layout_qa.py` (check_type mới), `tests/integration/test_job_orchestrator.py`,
  `docs/PRD.md` (known limitation mới)

**Trạng thái**: Đây là code thay đổi hành vi runtime (P0 logging + Phase 1 nối vào
`JobOrchestrator`) — theo Protocol 7 (R7-01/R7-02), **CHƯA qua Reviewer thật**. PM sẽ tự spawn
Reviewer riêng trước khi coi task này là "xong" — Dev KHÔNG tự báo cáo "xong"/"đã review"/"sẵn
sàng".

## Bug #7 fix — bước 7.0 (spike) + 7.1 (ship) — sitecustomize shim loại ký tự trắng khỏi
## phép đếm va chạm tách dòng (2026-09-07)

Theo `docs/Architecture.md` mục "Bug #7/#8 — Final Decision sau phản biện Domain Expert
(2026-09-07)" (X3/X4-1/X5, bảng thứ tự D7-3). Chỉ làm **7.0 + 7.1** — **KHÔNG** làm 7.2
(numbered-list, Ca A) và 7.3 (đo lại mục lục, Ca C) theo đúng phạm vi PM giao.

### 7.0 — Spike: xác nhận vector kỹ thuật (sitecustomize shim qua PYTHONPATH) hoạt động thật

App gọi `babeldoc` qua subprocess CLI (`asyncio.create_subprocess_exec`), không import babeldoc
trong process app (cài ở venv riêng qua `uv tool`) — monkey-patch Python thường **không có tác
dụng**. Dùng đúng Vector V1 đã chốt (Architecture.md X4-1): `sitecustomize.py` trong thư mục mới
`src/babeldoc_shim/`, truyền `PYTHONPATH=<thư mục đó>` vào `env` của subprocess babeldoc —
CPython tự `import sitecustomize` lúc khởi động interpreter con, trước cả entry point `babeldoc`.

**Verify sống (Protocol 5 R5-02, không suy đoán)**: chạy `babeldoc` 0.6.4 CLI thật (đã cài tại
`~/.local/share/uv/tools/babeldoc/`) với `--debug` trên p74–77 (Figoni, file trích sẵn
`/private/tmp/bdprobe/p74_77.pdf` từ spike trước), `--openai-base-url http://127.0.0.1:1/v1`
(cổng chết, 0 token/0 USD, dump `paragraph_finder.json` vẫn ghi vì nằm TRƯỚC bước dịch) + đúng
flag production (`--split-short-lines --short-line-split-factor 0.8`):

| Cấu hình | pdf_line đúng / tổng paragraph (>=2 ký tự có mực) | Ghi chú |
|---|---|---|
| Shim TẮT (không `PYTHONPATH`) | **147 / 163** | Khớp CHÍNH XÁC baseline đã ghi ở Architecture.md X2 — xác nhận môi trường đo đúng, không phải trùng hợp |
| Shim BẬT (`PYTHONPATH` trỏ `src/babeldoc_shim/`) | **170 / 172** | 2 ca còn sai là `)60`/`)62` (nhãn `abandon`, số trang — đúng như X2 dự đoán là "không đáng xử lý", KHÔNG liên quan Bug #7) |

Gate 7.0 (Architecture.md D7-3): pdf_line khớp ground truth ≥161/163 ✅ (170/172), job chạy xanh
(exit 0) cả 2 lần ✅, tắt được bằng cách bỏ `PYTHONPATH` (quay lại đúng 147/163 gốc) ✅. **Spike đạt
gate — tiếp tục 7.1.**

### 7.1 — Ship fix

1. **`src/babeldoc_shim/line_split.py`** (mới): thuật toán tách dòng thuần Python (không
   dependency numpy — `_compute_collision_counts_histogram` viết lại bằng difference-array thuần
   Python, cùng phép toán với bản numpy gốc của babeldoc, đã verify lại kết quả không đổi trước/
   sau khi bỏ numpy bằng cách chạy lại spike 7.0 — vẫn 170/172). Sao y logic gốc
   `_split_paragraph_into_lines` (`paragraph_finder.py:652-776`), CHỈ khác ở bước tính histogram
   va chạm: loại ký tự khoảng trắng (`is_space=True`) khỏi mảng đưa vào đếm, **giữ nguyên ngưỡng
   gốc `count < 1`** (KHÔNG đổi thành `count < 2` — X2-b đã chứng minh đó là hồi quy thật với dòng
   chỉ có đúng 1 ký tự, ví dụ ô số hẹp trong bảng). Ký tự khoảng trắng vẫn được gán vào đúng dòng
   theo tâm y ở bước cuối như cũ — không mất nội dung.
2. **`src/babeldoc_shim/sitecustomize.py`** (mới): meta-path import hook đợi module
   `babeldoc.format.pdf.document_il.midend.paragraph_finder` import xong rồi patch
   `ParagraphFinder._split_paragraph_into_lines` (adapter mỏng gọi `line_split.split_into_line_groups`).
   Assertion version bắt buộc: chỉ patch khi `babeldoc.__version__ == "0.6.4"` — version khác thì
   log cảnh báo, KHÔNG patch (verify sống bằng cách giả lập `babeldoc.__version__` khác trước khi
   import — xác nhận hook không được cài). Fail-safe: mọi lỗi trong lúc patch (đổi tên hàm/module ở
   version khác) đều bị bắt, log cảnh báo, babeldoc chạy tiếp với hành vi GỐC — verify bằng cách
   patch thất bại giả lập, không crash job.
3. **`src/services/babeldoc_runner.py`**: `BabeldocRunner.__init__` thêm tham số
   `line_split_shim_enabled: bool = True`; `translate_pages()` nối `PYTHONPATH` (trỏ
   `src/babeldoc_shim/`) vào `env` của subprocess khi bật — nối thêm bằng `os.pathsep` vào
   `PYTHONPATH` hiện có nếu đã tồn tại, không ghi đè.
4. **`src/core/config.py`**: `Settings.babeldoc_line_split_shim_enabled: bool = True` — không bắt
   buộc theo spec (spec không yêu cầu feature flag riêng) nhưng thêm để giữ cùng mẫu rollback tức
   thời với `babeldoc_rotated_text_overlay` đã có, theo gợi ý của PM.
5. **`src/core/job_orchestrator.py`**: truyền `line_split_shim_enabled=self._settings.babeldoc_line_split_shim_enabled`
   khi khởi tạo `BabeldocRunner` trong `_translator_runner` (điểm chọn engine duy nhất, 6.14.7).

**Test mới (Protocol 6 R6-02, `tests/test_babeldoc_line_split_shim.py`, 19 test)**: gọi ĐÚNG
`src.babeldoc_shim.line_split.split_into_line_groups` (hàm production, cùng hàm mà
`sitecustomize.py` monkey-patch vào babeldoc thật) trên chính golden fixture
`tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz` — assert **số dòng cụ thể** theo
đúng bảng oracle X2 (copy nguyên số liệu, không suy diễn): 14 case tham số hoá (ví dụ
`"1. Explain…"` → 3 dòng, `"■ To demonstrate…"` → 6 dòng) + 2 case "known unfixed" ghi lại tường
minh 2 ca `)60`/`)62` vẫn còn sai sau fix (X2: không phải hồi quy, không đáng xử lý, chỉ để không
ai nhầm là hồi quy) + 3 test hình học tổng hợp (không hồi quy dòng-1-ký-tự theo X2-b, ký tự trắng
bị loại khỏi đếm nhưng vẫn được gán đúng dòng theo X3, và tái hiện đúng hành vi lỗi GỐC khi không
loại ký tự trắng — chứng minh bug có thật trước khi có fix, không phải hiện tượng tự dựng của
fixture).

**Verify sống R6-03 (đọc nội dung PDF output thật, không tin `status`)** — chạy qua ĐÚNG
`BabeldocRunner.translate_pages()` (production class, không hàm rời rạc) với provider DeepSeek
thật (`.env`), shim mặc định BẬT (production default sau 7.1), trên **11 trang**:

**(a) 4 trang p74–77 (Figoni, chính nơi bug được báo cáo)**:

| Vị trí | Trước fix (Architecture.md W2, v1.2.6) | Sau fix 7.1 (live, lần này) |
|---|---|---|
| Bullet `■` trang 77: bắt đầu dòng / giữa dòng | 7 / 16 bắt đầu, 10 giữa dòng | **16 / 17 bắt đầu, 1 giữa dòng** — khớp gần đúng phân bố nguồn EN (16 đầu dòng, 1 giữa dòng) |
| `"1. Explain…" / "2. Explain…"` (trang 75, EXPERIMENT prompts) | Gộp 1 dòng (bug X2 point 2) | Mỗi mục tách đúng dòng riêng — khớp oracle test |
| `"QUESTIONS FOR REVIEW"` 1–17 (trang 74): bắt đầu dòng `N.` / giữa dòng | 3 / 17 bắt đầu, 10 giữa dòng | 7 bắt đầu, 6 giữa dòng — **cải thiện nhưng CHƯA hết** (đúng dự đoán: đây là Ca A/lỗi tầng GHÉP ĐOẠN `is_bullet_point`/`process_independent_paragraphs`, một hàm khác hoàn toàn với `_split_paragraph_into_lines` — cần B-2b ở bước 7.2, KHÔNG nằm trong scope 7.1) |

**(b) 7 trang nghiên cứu Q2** (trang sách 8, 13, 14, 17, 20, 21, 22 — trích lại từ
`data/uploads/937b1d1c-…Figoni….pdf`, mapping trang sách N ↔ PyMuPDF index N-1 đã verify khớp nội
dung mô tả ở Q2): so với số liệu `true08` (cấu hình production hiện tại) đã đo trong Architecture.md
Q3 — **không hồi quy** trên bất kỳ trang nào trong 7 trang (số block/ký tự cùng thang, không mất
nội dung; trang 13 văn xuôi thuần và trang 8 mục lục giữ nguyên 0 lỗi dính chữ; trang 17/14 vẫn
giữ mức chất lượng tương đương baseline đã tốt, dao động trong biên độ ngẫu nhiên bình thường của
1 lần dịch LLM khác — không có mẫu hình xấu đi hệ thống nào).

**Giả định tự chọn** (không dừng lại hỏi, ghi rõ lý do theo yêu cầu):
1. `line_split.py` viết bằng Python thuần thay vì numpy như bản gốc babeldoc — vì module này bị
   import cả trong app (test golden fixture) lẫn trong subprocess babeldoc (qua `PYTHONPATH`);
   subprocess babeldoc vốn có sẵn numpy nhưng app thì không, và không muốn thêm numpy vào
   `pyproject.toml` chỉ để phục vụ 1 module test nội bộ. Đã verify lại spike 7.0 sau khi viết lại
   (170/172, không đổi) để đảm bảo tương đương toán học.
2. `Settings.babeldoc_line_split_shim_enabled` là feature flag KHÔNG bắt buộc theo spec — thêm
   theo gợi ý tuỳ chọn của PM, cùng mẫu với `babeldoc_rotated_text_overlay`.
3. Mapping "trang sách N" ↔ PyMuPDF index N-1 cho 7 trang Q2: tự verify bằng cách đọc nội dung
   trích ra và so khớp với mô tả bố cục ở bảng Q2 (Architecture.md) — không có tài liệu nào ghi rõ
   quy ước 1-indexed/0-indexed trước đó.

**Kết quả cuối**:
```
uv run pytest -q            → 369 passed (350 + 19 test moi), 419 warnings
uv run ruff check           → All checks passed!
uv run ruff format --check  → 7 files (touched) already formatted
```

**File đã tạo mới**: `src/babeldoc_shim/__init__.py`, `src/babeldoc_shim/line_split.py`,
`src/babeldoc_shim/sitecustomize.py`, `tests/test_babeldoc_line_split_shim.py`.
**File đã sửa**: `src/services/babeldoc_runner.py` (PYTHONPATH wiring), `src/core/config.py`
(`babeldoc_line_split_shim_enabled`), `src/core/job_orchestrator.py` (truyền flag vào
`BabeldocRunner`).

**Trạng thái**: Đây là thay đổi hành vi runtime quan trọng — đụng cách gọi babeldoc cho MỌI job
dùng engine `babeldoc` (mặc định production). Theo Protocol 7 (R7-01/R7-02), **CHƯA qua Reviewer
thật** — Dev KHÔNG tự báo cáo "xong"/"đã review"/"sẵn sàng". **KHÔNG làm 7.2 (numbered-list, Ca A)
và 7.3 (đo lại mục lục, Ca C)** — PM quyết định hướng tiếp theo sau khi xem kết quả 7.1 này.

## Bug #7 fix — bước 7.2 (Ca A) — tách paragraph numbered-list theo marker
## tăng dần (B-2b) (2026-09-07)

Theo `docs/Architecture.md` mục "Bug #7/#8 — Final Decision sau phản biện Domain Expert
(2026-09-07)" (X5 D7-3, bảng "7.2"). Chỉ làm **7.2** — **KHÔNG** làm 7.3 (đo lại mục lục, Ca C),
đúng phạm vi PM giao ("tiếp tục với bước 7.2 (numbered-list)").

### Root cause / giải pháp do ai đưa ra (trả lời câu hỏi PM hỏi giữa task)

Root cause tầng dòng (X3 — ký tự trắng giữ `visual_bbox` cao bằng `font_size`) do **Domain
Expert** phát hiện, phản biện lại phân tích ban đầu sai của Tech Lead (W2: "ký tự đuôi `g` bắc
cầu"); Tech Lead tự verify độc lập và xác nhận Expert đúng. Riêng insight "Ca A cũng hỏng từ
tầng tách dòng ⇒ B-2b phải chạy SAU 7.1" (X2 điểm 2) cũng do Domain Expert chỉ ra. **Giải pháp
B-2b** (bọc `process()`, tách paragraph theo marker số tăng dần, tự sort theo x) là đề xuất gốc
của **Tech Lead** (W6, "chưa chốt, chờ Domain Expert phản biện") — Expert không bác bỏ B-2b
(chỉ bác B-2a), Tech Lead giữ nguyên và chốt thứ tự trong D7-3.

### Spike (R5-02, bắt buộc trước khi implement đầy đủ — B-2b còn `[UNVERIFIED]` ở X10)

Chạy `babeldoc` 0.6.4 thật (shim 7.1 đang bật qua `PYTHONPATH`, `--debug`, `--openai-base-url`
cổng chết 0 token) trên 2 fixture, dump `paragraph_finder.json` SAU KHI 7.1 đã chạy (input thật
cho 7.2):

1. `tests/fixtures/babeldoc/page14_numbered_list_source.pdf` (danh sách 35 mục "EQUIPMENT AND
   SMALLWARES", có sẵn từ increment cũ) — quét toàn bộ text thật: SAU 7.1 vẫn còn đúng **4 cặp
   mục dính chung 1 paragraph** (11+12, 23+24+dòng tiếp nối `"1½ quart"`, 31+32, 33+34) —
   `is_bullet_point` gốc của babeldoc không nhận chữ số là bullet nên không tách được.
2. Trích đoạn p74-77 (Figoni) dùng lại ở spike 7.0/7.1 — trang "QUESTIONS FOR REVIEW": SAU 7.1
   còn đúng 1 paragraph gồm **8 mục liên tiếp dính chung** (8..15).
3. Quét TOÀN BỘ marker số+dấu `.`/`)` xuất hiện trên cả 2 fixture (không chỉ tại các paragraph
   đã biết lỗi) để tìm false-positive: **0 ca sai** — mọi marker tìm được đều là mục danh sách
   thật, kể cả các dòng có số lượng dễ gây nhầm như `"1½ quart"`, `"2- and 4-quart sizes"`,
   `"2" or 2½\" or equivalent"` (không khớp regex vì thiếu dấu `.`/`)` ngay sau chữ số, hoặc ký tự
   sau chữ số không phải khoảng trắng).

**Gate 7.2 (từ D7-3: "loại được false-positive kiểu '2 cups' trong công thức") ✅ đạt** — spike
xác nhận trên dữ liệu thật, không suy đoán. Tiếp tục implement đầy đủ.

### Implementation

1. **`src/babeldoc_shim/numbered_list_split.py`** (mới, thuần Python, không phụ thuộc babeldoc):
   - `extract_leading_marker(text)`: regex `^\s*(\d{1,3})[.)]\s+\S` — bắt buộc `.`/`)` NGAY SAU
     chữ số rồi khoảng trắng rồi có nội dung — đây là cơ chế chặn false-positive chính (loại
     `"2 cups"` vì thiếu `.`/`)`; loại `"2.5 cups"` vì không có khoảng trắng ngay sau `.`).
   - `find_numbered_list_split_index(line_texts)`: marker của dòng ĐẦU TIÊN của paragraph là
     "marker neo"; tìm dòng ĐẦU TIÊN xuất hiện sau đó có marker = neo + 1 → trả về index đó để
     tách. KHÔNG cập nhật lại marker neo theo các marker không khớp giữa đường (an toàn hơn: một
     con số không liên quan xuất hiện giữa đường sẽ bị bỏ qua, không làm hỏng chuỗi tìm kiếm).
   - `split_paragraph_lines(line_texts)`: gọi lặp `find_numbered_list_split_index` để tách hết
     TẤT CẢ điểm tách trong 1 paragraph (cascade, tương đương vòng lặp ngoài của
     `process_independent_paragraphs` gốc) — đây là hàm DUY NHẤT quyết định ranh giới tách, dùng
     chung bởi `sitecustomize.py` (patch thật) và test golden fixture (Protocol 6 R6-02).
   - `build_sorted_line_text(chars)`: ghép ký tự theo x tăng dần (X4-4 — 4 lời gọi sort theo x
     của chính babeldoc đều bị comment, thứ tự ký tự thô KHÔNG được đảm bảo).
2. **`src/babeldoc_shim/sitecustomize.py`**: vá THÊM `ParagraphFinder.process` (bọc: chạy hàm gốc
   đã vá 7.1 trước, rồi duyệt `document.page` vừa được tạo, tách numbered-list trên từng trang).
   Thực thi hoàn toàn dựa trên kết quả của `split_paragraph_lines` — cắt `pdf_paragraph_composition`
   theo độ dài mỗi nhóm, tạo `PdfParagraph` mới cho từ nhóm thứ 2 trở đi (tái dùng nguyên mẫu tách
   của babeldoc `process_independent_paragraphs`, `paragraph_finder.py:868-925` — không chép lại
   logic typeset/box, gọi `self.update_paragraph_data`). Cả 2 patch (7.1 + 7.2) rollback CÙNG NHAU
   nếu cấu trúc babeldoc đổi (cùng 1 `try/except` ở `_PatchingLoader`, cùng gate version `0.6.4`).
3. **`src/core/config.py`**: `Settings.babeldoc_numbered_list_split_enabled: bool = True` — bộ
   rollback RIÊNG với `babeldoc_line_split_shim_enabled` (7.1), vì B-2b mới hơn/rủi ro cao hơn
   7.1 (7.1 đã qua R6-03 sống trên 11 trang, 7.2 chỉ mới qua 2 fixture) — tắt được 7.2 mà không
   tắt luôn 7.1.
4. **`src/services/babeldoc_runner.py`**: `BabeldocRunner.__init__` thêm
   `numbered_list_split_enabled: bool = True`; khi shim 7.1 đang bật, nối thêm biến môi trường
   `BABELDOC_SHIM_NUMBERED_LIST_SPLIT=1/0` vào `env` của subprocess — `sitecustomize.py` đọc biến
   này để quyết định có áp patch `process()` hay không (độc lập với patch `_split_paragraph_into_lines`).
5. **`src/core/job_orchestrator.py`**: truyền `numbered_list_split_enabled=self._settings.babeldoc_numbered_list_split_enabled`
   khi khởi tạo `BabeldocRunner`.

**Test mới (Protocol 6 R6-02, `tests/test_babeldoc_numbered_list_split.py`, 30 test)**:
- Unit test `extract_leading_marker`/`find_numbered_list_split_index` cho các ca chống
  false-positive named tường minh trong Architecture.md (`"2 cups flour"`, `"2.5 cups flour"`,
  `"1½ quart"`, marker không liên tiếp giữa đường).
- Golden-fixture test (2 fixture MỚI, ghi từ babeldoc thật — Protocol 5 mục 3, không mock tay):
  `tests/fixtures/babeldoc/paragraph_finder_numbered_list_post71_dump.json.gz` và
  `paragraph_finder_p74_77_post71_dump.json.gz` (dump `paragraph_finder.json` SAU 7.1, TRƯỚC khi
  có code 7.2 — đúng input thật mà B-2b phải xử lý). Assert số paragraph kết quả và NỘI DUNG cụ
  thể từng nhóm sau tách (ví dụ mục 24 phải giữ đúng dòng tiếp nối `"1½ quart"`; mục 8-15 phải
  cascade ra đúng 8 nhóm riêng theo đúng thứ tự) — copy nguyên text đọc ra từ fixture, không suy
  diễn.

**Verify sống R6-03 (đọc nội dung PDF output thật qua ĐÚNG `BabeldocRunner.translate_pages()`,
provider DeepSeek thật, KHÔNG tin `status`)**:

| Fixture | Trước 7.2 (sau 7.1) | Sau 7.2 (live, lần này) |
|---|---|---|
| `page14_numbered_list_source.pdf` (35 mục) | 4 cặp mục vẫn dính chung 1 paragraph | **35/35 mục xuống dòng đúng, 0 ca dính chữ** (`grep [^\d\s]\d{1,2}[.)]\s` → rỗng), mục 24 giữ đúng dòng tiếp nối `"1½ quart"` |
| p74-77, trang "QUESTIONS FOR REVIEW" (17 mục) | 7 bắt đầu dòng / 6 giữa dòng (ghi ở entry 7.1) | **17/17 bắt đầu dòng, 0 giữa dòng, 0 dính chữ** |

Nội dung không đổi (so tổng ký tự multiset trước/sau — bằng nhau, không mất chữ).

**Quan sát thêm (KHÔNG phải bug của 7.2, ghi lại minh bạch để theo dõi)**: ở cả 2 lần chạy live,
một số mục (3 mục trong list 35-mục: #12, #32, #34; và nhiều mục trong "QUESTIONS FOR REVIEW":
#3, #5, #7, #9-15) bị babeldoc fallback về giữ nguyên text gốc tiếng Anh (log
`il_translator_llm_only.py:828 "Fallback to simple translation"` — do DeepSeek trả kết quả
"too long/too short" hoặc giống input). Có khả năng liên quan tới việc mỗi mục giờ là 1 paragraph
NGẮN riêng biệt (trước 7.2 các mục bị dính chung thành block dài hơn, tỷ lệ fallback có thể khác).
Đây là hành vi fallback CÓ SẴN của babeldoc (`il_translator_llm_only.py`), không phải lỗi do code
7.2 gây ra — nhưng đáng theo dõi vì có thể ảnh hưởng tỷ lệ dịch hoàn chỉnh của numbered-list sau
khi 7.2 lên production. Chưa điều tra sâu (ngoài phạm vi 7.2) — PM/user quyết định có cần task
riêng không.

**Kết quả cuối**:
```
uv run pytest -q            → 399 passed (369 + 30 test moi), 419 warnings
uv run ruff check           → All checks passed!
uv run ruff format --check  → tat ca file da sua deu da dung format
```

**File đã tạo mới**: `src/babeldoc_shim/numbered_list_split.py`,
`tests/test_babeldoc_numbered_list_split.py`,
`tests/fixtures/babeldoc/paragraph_finder_numbered_list_post71_dump.json.gz`,
`tests/fixtures/babeldoc/paragraph_finder_p74_77_post71_dump.json.gz`.
**File đã sửa**: `src/babeldoc_shim/sitecustomize.py` (vá thêm `ParagraphFinder.process`),
`src/core/config.py` (`babeldoc_numbered_list_split_enabled`), `src/services/babeldoc_runner.py`
(env `BABELDOC_SHIM_NUMBERED_LIST_SPLIT`), `src/core/job_orchestrator.py` (truyền flag vào
`BabeldocRunner`), `docs/Architecture.md` (X10: đánh dấu B-2b ✅ Verified).

**Trạng thái**: Đây là thay đổi hành vi runtime — đụng cách gọi babeldoc cho MỌI job dùng engine
`babeldoc` có numbered-list (mặc định production). Theo Protocol 7 (R7-01/R7-02), **CHƯA qua
Reviewer thật** — PM sẽ tự spawn Reviewer riêng trước khi coi task này là "xong". **KHÔNG làm 7.3
(đo lại mục lục, Ca C)** — đúng phạm vi PM giao lần này.

## Bug #7 fix — bước 7.3 (Ca C, mục lục) — CHỈ ĐO LẠI, KHÔNG code gì (2026-09-07)

Theo `docs/Architecture.md` X5 D7-3 (bảng "7.3"): "chưa code gì, chỉ đo lại" sau khi 7.1+7.2 đã
ship, đo cả 2 chiều bắt buộc — (1) cấu trúc mục lục có tốt lên không, (2) tỷ lệ cắt nhầm caption
(RC-1) có xấu đi không. **Không viết code fix nào trong task này** — đúng phạm vi PM giao
("tiếp tục với bước 7.3 (mục lục)").

### (1) Cấu trúc mục lục — KẾT LUẬN: 7.1+7.2 KHÔNG cải thiện gì, Ca C vẫn còn nguyên

Trích 2 trang Contents thật của chính file production `data/uploads/937b1d1c-…Figoni….pdf`
(trang sách 7 và trang sách 8, đúng trang đã dùng ở phân tích Ca C gốc — mapping "trang sách N
↔ PyMuPDF index N-1"). Chạy `babeldoc` 0.6.4 thật, `--debug`, cổng LLM chết (0 token), 2 lần —
1 lần KHÔNG có `PYTHONPATH` shim (baseline, hành vi gốc), 1 lần CÓ shim 7.1+7.2 đang bật — rồi so
sánh `paragraph_finder.json` (IL cấu trúc thật, không phải suy đoán):

- **Trang sách 7**: 34 paragraph nội dung thật / 66 dòng ở CẢ 2 lần chạy — **byte-for-byte giống
  hệt nhau**, không đổi 1 ký tự. 12 paragraph vẫn còn gộp chung nhiều mục TOC (vd 1 paragraph gộp
  8 dòng: `"Commercial Grades of White Flours 77"` → `"Exercises and Experiments 89"`).
- **Trang sách 8**: 44 paragraph / 89 dòng ở CẢ 2 lần — cũng byte-for-byte giống hệt. Ca nặng
  nhất: 1 paragraph gộp **8 mục TOC liên tiếp** (`"The Importance of Gluten 117"` →
  `"Exercises and Experiments 133"`).

**Nguyên nhân đúng như Architecture.md đã dự đoán trước khi làm 7.1/7.2**: 7.1 sửa lỗi ở TẦNG
TÁCH DÒNG (ký tự trắng lấp khe giữa 2 dòng) — không liên quan gì tới việc TOC gộp nhiều DÒNG đã
tách đúng vào 1 PARAGRAPH. 7.2 (B-2b) chỉ tách khi dòng có marker số ở ĐẦU dòng (`"1. "`, `"2. "`)
— mục TOC có số trang ở CUỐI dòng (`"...Exercises and Experiments 61"`), không khớp anchor nào
của B-2b, nên không bao giờ kích hoạt trên trang này (giải thích vì sao kết quả giống hệt 100%).

**Verify sống (R6-03, đọc nội dung PDF output thật, không tin cấu trúc IL không)** — dịch thật
qua đúng `BabeldocRunner.translate_pages()` với DeepSeek, trang sách 7: dry-run (0 token, giữ
nguyên văn gốc) ra 55 block sạch (không lộ bug vì text gốc không đổi khi fallback), nhưng **dịch
thật lộ rõ tác hại**: chỉ còn **26 block**, nhiều mục TOC bị **trộn lẫn thành 1 câu chạy dài**
khi LLM dịch chung 1 đoạn — ví dụ 4 mục thật bị dịch dính thành:
`"Giai đoạn III: Làm nguội 38 Câu hỏi Ôn tập 39 Câu hỏi Thảo luận 40 Bài tập và Thí nghiệm 40"`
(4 tên mục + 4 số trang lẫn vào nhau, không còn ranh giới rõ giữa các mục — người dùng không thể
phân biệt mục nào ứng với trang nào).

**Kết luận (1)**: **Ca C (mục lục) là bug THẬT, còn nguyên, KHÔNG được 7.1/7.2 chạm tới.** Cần
thiết kế fix riêng (heuristic khác B-2b — phải tách theo marker SỐ TRANG Ở CUỐI dòng, không phải
marker ở đầu dòng) — **ngoài phạm vi 7.1/7.2/7.3**, cần Tech Lead thiết kế lại nếu PM/user muốn
làm tiếp (tạm gọi "7.4" nếu có).

### (2) Tỷ lệ cắt nhầm caption (RC-1) — KẾT LUẬN: KHÔNG hồi quy, có 1 phát hiện MỚI ngoài dự kiến

Đo lại đúng 2 trang đã dùng làm bằng chứng RC-1 gốc trong "Đo lại F1 trên nhiều trang" (Q3/Q4) —
trang sách 20 (bảng hẹp + caption) và trang sách 22 (mix). So `paragraph_finder.json` baseline
vs shim 7.1+7.2, dùng diff theo tập hợp (không phụ thuộc thứ tự) để không bị nhiễu bởi việc số
paragraph tăng/giảm do chỗ khác:

- **Trang 20**: chỉ có ĐÚNG 1 khác biệt — heading gốc `"WEIGHT AND VOLUME MEASUREMENTS"` (2
  dòng) ở baseline bị GÁN KÝ TỰ SAI HOÀN TOÀN giữa 2 dòng thành 1 chuỗi vô nghĩa
  `"WVOELIGUHMTE  AMNEDA SUREMENTS"` (không phải chỉ "dính chữ" — mà đảo lộn thứ tự ký tự giữa
  2 dòng, do cùng root cause X3 + việc 3 lời gọi sort theo x bị comment trong babeldoc gốc). Sau
  shim: tách đúng thành 2 paragraph riêng `"WEIGHT AND"` / `"VOLUME MEASUREMENTS"` — same set ký
  tự (đã verify bằng `sorted()`), không mất/thêm chữ nào.
- **Trang 22**: tương tự — `"THE DIFFERENCE BETWEEN WEIGHT OUNCES AND FLUID OUNCES"` bị đảo lộn
  thành `"TOHUEN DCIEFSF EARNEDN CFLEU BIDE TOWUENECNE SWEIGHT"` ở baseline; sau shim tách đúng
  thành 2 dòng đọc được.
- **Không tìm thấy caption nào bị CẮT XẤU ĐI** (mất nghĩa, mất chữ) do 7.1/7.2 trên 2 trang này —
  văn xuôi xung quanh giữ nguyên, không có regression.

**Phát hiện MỚI, chưa từng ghi trong Architecture.md trước đây** (không thuộc Ca A/B/C đã biết):
heading 2 dòng ngắn nằm cạnh nhau có thể bị babeldoc gán SAI ký tự chéo giữa 2 dòng (không chỉ
gộp — mà XÁO TRỘN), cùng root cause X3 (space bít khe + sort theo x bị comment). 7.1 vô tình sửa
luôn ca này vì cùng cơ chế gốc. Đáng ghi nhận nhưng **không mở rộng thêm code** trong task này —
đúng phạm vi "chỉ đo".

**Verify sống trên trang 20 qua dịch thật (DeepSeek)**: cả 2 arm (có/không shim) đều ra heading
tiếng Việt ĐỌC ĐƯỢC (khác câu chữ, cùng nghĩa: `"KHỐI LƯỢNG VÀ ĐO THỂ TÍCH"` vs
`"ĐO LƯỜNG TRỌNG LƯỢNG VÀ THỂ TÍCH"`) — **LLM tự "đoán đúng" nghĩa dù input tiếng Anh bị xáo trộn**
trong đúng lần chạy này, nên KHÔNG dùng được live-run này để chứng minh lợi ích cho end-user một
cách chắc chắn (phụ thuộc khả năng đoán ngẫu nhiên của 1 LLM cụ thể, không đáng tin cậy). Cấu
trúc IL đúng vẫn là cải thiện thật về độ ổn định (không phụ thuộc LLM có "đoán" ra hay không) —
ghi rõ giới hạn của bằng chứng này, không phóng đại thành "user sẽ luôn thấy tốt hơn".

**File dùng để đo** (không commit, script/PDF trích tạm tại scratchpad phiên này — tái tạo được
bằng đúng lệnh `babeldoc --debug` + `fitz.insert_pdf` ghi ở trên, theo tinh thần Protocol 5 mục 3
áp dụng cho việc ĐO, không phải cho code production):
`/tmp/bdprobe/figoni_p7_toc.pdf`, `figoni_p8_toc.pdf`, `figoni_p20.pdf`, `figoni_p22.pdf` (trích
từ `data/uploads/937b1d1c-…Figoni….pdf`).

**Trạng thái**: Đo xong theo đúng gate D7-3 cho 7.3. **Không có code nào được viết/sửa trong task
này** — chỉ 1 entry docs này. Ca C (mục lục) cần PM/user quyết định có làm tiếp không (thiết kế
mới, không phải mở rộng B-2b) — chưa tự ý code thêm.

## Hotfix bước 7.2 — `unicode=""` khiến mục numbered-list bị BỎ DỊCH, không phải "LLM fallback"
## như đã ghi nhầm (phát hiện bởi Domain Expert, 2026-09-07)

### Bối cảnh phát hiện

Trong lúc phản biện thiết kế Ca C (xem section "Bug #7 Ca C — Phản biện của Domain Expert" trong
`docs/Architecture.md`), Domain Expert phát hiện **bug thật trong code 7.2 đã ship** (commit
`e324b29`) — không liên quan trực tiếp tới Ca C nhưng nghiêm trọng hơn cả việc đang bàn, nên xử lý
ngay thay vì để dồn qua bước sau.

**Root cause** (đã tự verify độc lập, đọc source thật, không chỉ tin lại Domain Expert):

1. `ParagraphFinder.update_paragraph_data(paragraph, update_unicode=False)` — mặc định **không**
   đụng tới `paragraph.unicode` (`paragraph_finder.py:124-158`, tham số `update_unicode` mặc định
   `False`).
2. `process_page` của babeldoc gốc gọi ĐÚNG 1 LẦN `update_paragraph_data(paragraph,
   update_unicode=True)` cho MỌI paragraph, nhưng dòng gọi đó (`paragraph_finder.py:294`) nằm
   **BÊN TRONG** `process_page` — chạy xong TRƯỚC KHI patch 7.2 (`_split_numbered_list_paragraphs_on_page`,
   bọc `ParagraphFinder.process` và chỉ chạy SAU KHI `process()` đã trả về hoàn toàn cho MỌI trang)
   có cơ hội tạo paragraph mới.
3. Paragraph mới do 7.2 tạo (`PdfParagraph(..., unicode="", ...)`) gọi
   `self.update_paragraph_data(new_paragraph)` — **thiếu** `update_unicode=True` — nên `.unicode`
   giữ nguyên `""` vĩnh viễn.
4. `il_translator_llm_only.py:563-566`: `if len(paragraph.unicode) < self.translation_config.min_text_length: continue`
   — paragraph có `unicode=""` (độ dài 0) bị **bỏ qua hoàn toàn**, không bao giờ được gửi đi dịch.

**Hệ quả**: mọi mục numbered-list bị 7.2 tách ra ở vị trí "nhóm thứ 2 trở đi" (tức paragraph MỚI
tạo, không phải paragraph gốc bị cắt) đều bị giữ nguyên tiếng Anh trong PDF output — **không phải**
do LLM tự "fallback" như CHANGELOG bước 7.2 (2026-09-07, mục "Quan sát thêm") đã ghi. Đính chính:
mục đó ghi "một số mục... bị babeldoc fallback về giữ nguyên tiếng Anh... CHƯA điều tra sâu" — kết
luận đó **sai một phần quan trọng** (không phải hành vi ngẫu nhiên của babeldoc/LLM, mà là bug xác
định 100% trong code app) — giữ nguyên đoạn cũ (không sửa/xoá lịch sử), đính chính tại đây.

**Verify chéo bằng chính dữ liệu live-run đã lưu trước đó** (không cần chạy lại mới đã đủ bằng
chứng): 4 mục còn tiếng Anh trong lần chạy `page14_numbered_list_source.pdf` ở bước 7.2
(`#12`, `#24`, `#32`, `#34`) khớp **chính xác 100%** với "nhóm thứ 2" của **đúng 4 cặp** mà
`numbered_list_split.split_paragraph_lines` đã tách (11+12, 23+24+"1½ quart", 31+32, 33+34) —
không lệch 1 mục nào. Tương tự 10 mục còn tiếng Anh ở trang "QUESTIONS FOR REVIEW" (#3, #5, #7,
#9-15) khớp chính xác các nhóm mới tạo trong chuỗi cascade 8→15 và các cặp (2,3)/(4,5)/(6,7).

### Fix

`src/babeldoc_shim/sitecustomize.py`, hàm `_split_numbered_list_paragraphs_on_page`: thêm
`update_unicode=True` vào **CẢ HAI** lời gọi `update_paragraph_data`:
- Paragraph gốc bị cắt (nhóm đầu, `group_idx == 0`) — trước đó `.unicode` giữ nguyên **văn bản
  gộp CŨ** (dài hơn nội dung thực còn lại sau khi cắt).
- Paragraph mới tạo (nhóm thứ 2 trở đi) — đây là chỗ gây bug thấy được (bỏ dịch hoàn toàn).

**Đính chính sau review** (Reviewer đào sâu hơn phạm vi được giao, đọc thêm
`il_translator.py:607-623` — `get_translate_input`): trường hợp paragraph gốc bị cắt chỉ còn ĐÚNG
1 composition (khớp 3/4 cặp ví dụ chính ở trên: 11+12, 31+32, 33+34), text gửi cho LLM dịch lấy
**THẲNG** từ `paragraph.unicode`, không dựng lại từ ký tự thật. Vậy fix cho nhóm đầu KHÔNG chỉ là
"dọn dữ liệu lỗi thời vô hại" như nhận định ban đầu ở trên — mà là chặn đúng 1 rủi ro thật: **dịch
sai nội dung** (gửi văn bản gộp CŨ, dài hơn, cho LLM dịch thay vì đúng nội dung ngắn còn lại sau
khi cắt). May mắn là bản fix đã áp dụng từ đầu (thêm `update_unicode=True` cho CẢ HAI) đã chặn kín
rủi ro này dù lý do ban đầu ghi ở trên chưa đủ mạnh — không cần sửa thêm code, chỉ đính chính lại
lý do tại đây.

### Verify sống lại sau fix (R6-03, đọc nội dung PDF output thật)

| Fixture | Trước hotfix | Sau hotfix |
|---|---|---|
| `page14_numbered_list_source.pdf` (35 mục) | **4/35** mục còn tiếng Anh (#12,#24,#32,#34) | **0/35** — dịch đủ hết, cấu trúc vẫn giữ nguyên 35/35 xuống dòng đúng, 0 dính chữ |
| p74-77, "QUESTIONS FOR REVIEW" + 3 trang khác | **10** mục còn tiếng Anh (đếm trên page0) | **0** mục còn tiếng Anh trên cả 4 trang; cấu trúc vẫn 17/17, 3/3, 3/3, 1/1 đúng như trước |

**Test mới** (`tests/test_babeldoc_shim_unicode_regression.py`, 2 test): pin cứng bằng cách đọc
SOURCE THẬT của `sitecustomize.py` (không import `babeldoc` — package này cố ý KHÔNG phải
dependency của app, `import babeldoc` sẽ luôn thất bại trong venv của app ở bất kỳ máy nào, đây là
kiến trúc cố ý theo Architecture.md X4-1, không phải giới hạn CI) — assert cả 2 lời gọi
`update_paragraph_data` trong hàm này đều có `update_unicode=True`. Chặn hồi quy nếu ai đó sau này
lỡ sửa hàm và bỏ mất flag.

**Kết quả cuối**:
```
uv run pytest -q            → 401 passed (399 + 2 test moi), 419 warnings
uv run ruff check           → All checks passed!
uv run ruff format --check  → 2 file da sua deu dung format
```

**File đã sửa**: `src/babeldoc_shim/sitecustomize.py`.
**File đã tạo mới**: `tests/test_babeldoc_shim_unicode_regression.py`.

**Trạng thái**: Đây là fix hành vi runtime cho code ĐÃ SHIP (7.2). **Đã qua Reviewer thật (Protocol
7 R7-01) — APPROVE, không blocking issue**, xem `docs/review-report.md`. **Ghi nhận công phát
hiện: Domain Expert** (đang trong lúc phản biện thiết kế Ca C, không phải nhiệm vụ được giao) —
đây là lý do giữ nguyên quy trình 2 vai trò (Tech Lead đề xuất, Domain Expert phản biện độc lập
bằng cách tự đọc source/tự đo) cho các thay đổi runtime quan trọng, kể cả khi việc đang bàn là một
task khác.

## Bug #7 Ca C — Spike 7.4-a (Dev, 2026-09-08)

### Kết quả: **PASS** cả 6/6 điều kiện gate AA9 của `docs/Architecture.md` mục "Bug #7 Ca C —
### Quyết định cuối sau phản biện Domain Expert + kế hoạch spike 7.4-a (Tech Lead, 2026-09-08)"

Thực hiện đúng 6 bước AA8 theo thứ tự. Đây là **spike theo Protocol 5 R5-02** — sản phẩm là
bằng chứng + fixture, KHÔNG phải feature. Không có patch thứ 3 nào được commit vào
`src/babeldoc_shim/sitecustomize.py`, không wiring `config.py`/`babeldoc_runner.py`/
`job_orchestrator.py`, không viết bộ test đầy đủ — đúng ràng buộc AA10(a).

### Bước 1 — Bảo toàn bằng chứng

Đã kiểm tra: cả 8 nguồn `paragraph_finder.json` (6 ở scratchpad phiên trước, 2 ở
`/tmp/bdprobe/wd_toc*`) và 6 PDF nguồn ở `<SP>/pdfs/` **còn sống nguyên vẹn** — không cần tái
tạo lại bằng `run_all.sh`. Đã gzip + commit đúng 8 file vào `tests/fixtures/babeldoc/` với tên
theo đúng bảng AA8 bước 1, và copy 6 PDF nguồn vào `tests/fixtures/babeldoc/toc_sources/`.
Cập nhật `tests/fixtures/babeldoc/README.md` với bảng nguồn + lệnh tái tạo.

File mới:
- `tests/fixtures/babeldoc/toc_lcb_contents_p6_p7_dump.json.gz` (222KB)
- `tests/fixtures/babeldoc/toc_friberg_contents_dump.json.gz` (53KB)
- `tests/fixtures/babeldoc/toc_lcb_index_dump.json.gz` (188KB)
- `tests/fixtures/babeldoc/toc_figoni_p25_recipe_dump.json.gz` (127KB)
- `tests/fixtures/babeldoc/toc_figoni_p45_recipe_dump.json.gz` (165KB)
- `tests/fixtures/babeldoc/toc_figoni_tables_dump.json.gz` (185KB)
- `tests/fixtures/babeldoc/toc_figoni_contents_p7_dump.json.gz` (104KB)
- `tests/fixtures/babeldoc/toc_figoni_contents_p8_dump.json.gz` (133KB)
- `tests/fixtures/babeldoc/toc_sources/{figoni_p25_recipe,figoni_p45_recipe,figoni_p7_tables,
  friberg_toc,lcb_index,lcb_toc}.pdf`

### Bước 2 — `src/babeldoc_shim/toc_split.py`

Module thuần Python mới, **không import babeldoc**, implement đúng AA4 (thuật toán 6 bước) +
AA5 (tham số chốt: `TOC_GAP_RATIO=0.8`, `TOC_MIN_TAIL_LINES=2`, `TOC_MIN_TAIL_FRACTION=0.6`,
`TOC_MIN_BODY_ALPHA_RUNS=1`, `TOC_MAX_DIGITS=4`, `TOC_REQUIRE_NON_DECREASING=True`,
`TOC_CONT_INDENT_EM=1.0`, `TOC_DOT_LEADER_FALLBACK=False`, deny-list `TOC_LAYOUT_LABEL_DENY`).

Thiết kế theo đúng khuôn `numbered_list_split.py` của 7.2: hàm quyết định (`evaluate_paragraph`)
nhận kiểu dữ liệu thuần (`TocChar`, tuple toạ độ `(x, y, x2, y2)`) thay vì object IL thật của
babeldoc hay dict JSON thô — việc trích field thật (từ dump JSON ở spike này, hoặc từ object IL
thật khi wiring vào `sitecustomize.py` ở 7.4-c) là việc của caller, không phải của module này.
Điều này giữ module test được độc lập với cấu trúc object cụ thể.

API chính: `TocChar`, `LineMark`, `ContinuationBoundary`, `ParagraphSplitResult`,
`sort_line_chars`, `mark_toc_tail`, `evaluate_paragraph`.

### Bước 3 — Đo trên 8+3 fixture, đối chiếu oracle AA7

Script đo: `scripts/toc_split_spike_measure.py` (`uv run python scripts/toc_split_spike_measure.py`).
Gọi đúng `evaluate_paragraph` (Protocol 6 R6-02), không chép lại logic quyết định.

| Fixture | fire | cut points | blocked_by_monotonic | blocked_by_fraction | fired_inside_table_box | Oracle AA7 |
|---|---|---|---|---|---|---|
| `figoni_p7_toc` | **8** | **28** | 0 | 0 | 0 | 8/28 ✅ khớp |
| `figoni_p8_toc` | **12** | **38** | 0 | 0 | 0 | 12/38 ✅ khớp |
| `lcb_toc` | **11** | **64** | 0 | 0 | **5** | 11/64, `fired_inside_table_box=5` ✅ khớp |
| `friberg_toc` | 0 | 0 | 0 | 0 | 0 | 0/0 ✅ khớp (đúng thiết kế, ngoài tầm TOC-1) |
| `lcb_index` | 0 | 0 | 0 | 0 | 0 | 0/0 ✅ khớp (FP-7) |
| `figoni_p25_recipe` | **0** | **0** | 0 | 0 | 0 | 0/0 ✅ khớp (FP-4, KHÔNG có false-positive) |
| `figoni_p45_recipe` | **0** | **0** | 0 | 0 | 0 | 0/0 ✅ khớp (FP-4, KHÔNG có false-positive) |
| `figoni_p7_tables` | **0** | **0** | 0 | 0 | 0 | 0/0 ✅ khớp (FP-3/FP-4, KHÔNG có false-positive) |
| `p74_77` (4 trang, dùng fixture `paragraph_finder_p74_77_post71_dump.json.gz` đã có sẵn từ 7.1) | 0 | 0 | 0 | 0 | 0 | 0/0 ✅ khớp |
| `page14_numbered_list_source` (dùng fixture `paragraph_finder_numbered_list_post71_dump.json.gz` đã có sẵn từ 7.2) | 0 | 0 | 0 | 0 | 0 | 0/0 ✅ khớp |
| `figoni_p20` (đọc trực tiếp từ `/tmp/bdprobe/wd_p20/`, KHÔNG commit — không nằm trong 8 file bắt buộc của AA8 bước 1) | 0 | 0 | 0 | 0 | 0 | 0/0 ✅ khớp |
| `figoni_p22` (đọc trực tiếp từ `/tmp/bdprobe/wd_p22/`, KHÔNG commit) | 0 | 0 | 0 | 0 | 0 | 0/0 ✅ khớp |
| **TỔNG** | **31** | **130** | 0 | 0 | 5 | **31/130, 0 FP trên 8 fixture không phải mục lục** ✅ khớp tuyệt đối |

**Không có bất kỳ false-positive nào** trên 8 fixture không phải mục lục, kể cả 3 fixture công
thức bánh (`figoni_p25_recipe`, `figoni_p45_recipe`, `figoni_p7_tables`) — điều kiện FAIL nghiêm
trọng nhất theo brief KHÔNG xảy ra.

### Bước 4 — Đo riêng luật dòng nối (Z7-a, `TOC_CONT_INDENT_EM=1.0`)

Tìm được đúng **6** ranh giới "dòng đánh dấu → dòng không đánh dấu" trong 31 paragraph kích
hoạt (tất cả đều nằm trong `lcb_toc`):

| marked_idx | next_idx | indent_delta (pt) | extended |
|---|---|---|---|
| 3 | 4 | −1.08 | False |
| 3 | 4 | +0.00 | False |
| 2 | 3 | +0.00 | False |
| 5 | 6 | +0.07 | False |
| 2 | 3 | +0.00 | False |
| 4 | 5 | −13.03 | False |

`min=-13.03pt, max=+0.07pt` — khớp gần như tuyệt đối với số đo của Tech Lead ở AA1/AA8
(`−13.0 … +0.1 pt`, sai khác chỉ do làm tròn). **0/6 ranh giới được `extended`** ⇒ luật dòng nối
là **no-op tuyệt đối** trên dữ liệu hiện có — 0 điểm tách bị dịch chuyển so với khi tắt luật này
(vì luật không bao giờ kích hoạt). Đúng kỳ vọng AA8 bước 4 / điều kiện AA9-4.

### Bước 5 — Chứng minh hook mutate in-place (mục `[UNVERIFIED]` cuối cùng của AA12)

Thêm 1 patch TẠM THỜI (instrument) vào `src/babeldoc_shim/sitecustomize.py`, bọc
`ParagraphFinder.process_independent_paragraphs`: chạy hàm gốc trước, rồi chèn 1 lần duy nhất 1
`PdfParagraph` tổng hợp (mượn lại 1 composition `pdf_line` thật từ paragraph đầu tiên có dòng,
`unicode=""`, `debug_id="TOC_SPIKE_STEP5_PROBE"`) vào **cùng list** `paragraphs` bằng
`paragraphs.append(...)` — kích hoạt qua biến môi trường riêng `TOC_SPIKE_STEP5_INSTRUMENT=1`
để không bao giờ vô tình chạy trong production.

Chạy `babeldoc --debug` thật trên `figoni_p7_toc.pdf`, LLM port chết (`127.0.0.1:1`),
`--ignore-cache`, working-dir tạm. Đọc `paragraph_finder.json` kết quả, tìm paragraph có
`debug_id == "TOC_SPIKE_STEP5_PROBE"`:

```
so luong tim thay: 1
page_number = 0
unicode = 'CONTENTS'
render_order = 5
layout_label = fallback_line   layout_id = 24
```

**Cả 3 điều kiện đều xanh**: (a) paragraph chèn thêm **có mặt** trong `page.pdf_paragraph`,
(b) `unicode = 'CONTENTS'` (**khác `""`**), (c) `render_order = 5` (**không phải `None`**) — dù
code TOC-1 hoàn toàn không tự gán 2 field này. Xác nhận sống cơ chế AA6 lý do 1+2: hook đặt
TRƯỚC `update_paragraph_data(..., update_unicode=True)` (`:293-294`) và `_set_paragraph_render_order`
(`:310`) khiến paragraph mới **tự động** nhận đủ `unicode`/`render_order` từ chính babeldoc, không
phụ thuộc code TOC-1 nhớ gọi đúng — TOC-1 miễn nhiễm với lớp bug Z6 (đã hại 7.2) **theo thiết kế**.

**Đã revert patch tạm ngay sau khi đo xong** — `git diff --stat src/babeldoc_shim/sitecustomize.py`
= rỗng, `grep -n TOC_SPIKE_STEP5 src/babeldoc_shim/sitecustomize.py` = 0 hit. File này **không**
nằm trong commit của spike 7.4-a, đúng AA10(a).

### Đối chiếu Gate AA9 — PASS 6/6

| # | Điều kiện AA9 | Kết quả |
|---|---|---|
| 1 | Recall Figoni khớp chính xác 8/28 + 12/38 | ✅ **PASS** — khớp tuyệt đối |
| 2 | Recall LCB 11/64, monotonic 11/11 | ✅ **PASS** — 11 fire, 64 cut, `blocked_by_monotonic=0` (không paragraph nào bị chặn bởi cổng monotonic ⇒ monotonic 11/11) |
| 3 | FP = 0 tuyệt đối trên 8 fixture không phải mục lục | ✅ **PASS** — 0 kích hoạt trên cả 8 |
| 4 | Luật dòng nối là no-op | ✅ **PASS** — 6/6 ranh giới không được `extended`, 0 điểm tách bị dịch chuyển |
| 5 | Bước 5 xanh (`unicode != ""` và `render_order is not None`) | ✅ **PASS** — `unicode='CONTENTS'`, `render_order=5` |
| 6 | 8 fixture + 6 PDF nguồn đã commit, README cập nhật | ✅ **PASS** |

### Kết quả kiểm tra chất lượng

```
uv run pytest -q                                                            → 401 passed, 420 warnings
uv run ruff check src/babeldoc_shim/toc_split.py scripts/toc_split_spike_measure.py       → All checks passed!
uv run ruff format --check src/babeldoc_shim/toc_split.py scripts/toc_split_spike_measure.py → 2 files formatted
```

Số lượng test pass **không đổi** (401, giống baseline trước spike) — đúng chủ đích AA10(a): spike
này không viết bộ test đầy đủ (`tests/test_babeldoc_toc_split.py` thuộc phạm vi 7.4-c).

**File đã tạo mới**: `src/babeldoc_shim/toc_split.py`, `scripts/toc_split_spike_measure.py`,
8 fixture `.json.gz` + 6 PDF trong `tests/fixtures/babeldoc/` (+ `toc_sources/`).
**File đã cập nhật**: `tests/fixtures/babeldoc/README.md`.
**File KHÔNG có thay đổi nào được commit**: `src/babeldoc_shim/sitecustomize.py` (patch tạm đã
revert), `src/core/config.py`, `src/services/babeldoc_runner.py`, `src/core/job_orchestrator.py`.

**Trạng thái**: **Spike PASS toàn bộ gate AA9.** Theo AA9, bước tiếp theo là báo cáo cho
PM/Tech Lead để quyết định mở 7.4-b (wiring `toc_split.py` vào `sitecustomize.py` như patch thứ
3 thật, cờ runtime `BABELDOC_SHIM_TOC_SPLIT`/`Settings.babeldoc_toc_split_enabled` mặc định
`False`) — **chưa tự ý làm tiếp** trong task này (đúng AA10(a): "ĐÂY VẪN LÀ SPIKE"). Chưa qua
Reviewer (không bắt buộc cho spike theo brief, nhưng 7.4-b trở đi PHẢI qua Reviewer thật theo
Protocol 7 R7-01 trước khi coi là "xong").

## Bug #7 Ca C — 7.4-b/c/d/e: Implement production + test + live E2E + hồi quy (Dev, 2026-09-08)

Tiếp nối spike 7.4-a (PASS gate AA9, đã qua Reviewer APPROVE — mục ngay trên). Nhiệm vụ: implement
đầy đủ production cho TOC-1 v2 (AA4-AA9), viết test, chạy live E2E, đo hồi quy — theo brief PM.
**Chưa spawn Reviewer** (Protocol 7 R7-01 — PM sẽ tự làm việc đó sau task này).

### 7.4-b — Sửa bug continuation-line (issue non-blocking #1 của Reviewer) TRƯỚC khi implement

Review spike 7.4-a (`docs/review-report.md`, "Review spike 7.4-a", issue non-blocking #1) chỉ ra:
luật dòng nối (AA4 bước 4) trong `evaluate_paragraph` (`src/babeldoc_shim/toc_split.py`) gán SAI
nhóm cho 1 composition **không phải** `pdf_line` (vd `pdf_formula`) đứng NGAY SAU dòng đã đánh dấu
— code cũ `break` ngay với `j` giữ nguyên `= i` rồi `cut_after.append(j)`, đẩy composition đó vào
group **SAU** điểm cắt, trong khi đặc tả AA4 bước 4 nói rõ nó phải **dính vào group LIỀN TRƯỚC**
— giống hệt 7.2 (`numbered_list_split.find_numbered_list_split_index` trả `None` cho composition
không phải dòng, nên nó tự nhiên nằm trong group trước khi slicing).

**Sửa**: khi `next_chars is None` (composition không phải `pdf_line`), thay vì `break` ngay, gán
`j = next_idx` rồi `continue` — kéo composition đó (và mọi composition non-line liên tiếp sau nó)
vào group của dòng đánh dấu, không log `ContinuationBoundary` cho nó (không có `font_size`/`x` để
đo "thụt đầu dòng" cho 1 composition không phải dòng — boundary chỉ dành cho cặp dòng-đánh-dấu →
dòng-không-đánh-dấu thật sự). Đã tự đo lại `scripts/toc_split_spike_measure.py` sau khi sửa: **kết
quả AA7/AA8 KHÔNG đổi** (31 fire/130 cut, 6/6 ranh giới không `extended`, min=−13.03pt
max=+0.07pt) — đúng dự đoán của Reviewer ("rủi ro thấp/lý thuyết", không fixture nào trong 12 dump
thật có `pdf_formula` xen giữa mục lục).

### 7.4-b — Wiring patch thứ 3 vào `sitecustomize.py`

Theo đúng khuôn `_split_numbered_list_paragraphs_on_page` (bước 7.2), nhưng điểm hook KHÁC hẳn
(AA6): bọc `ParagraphFinder.process_independent_paragraphs(paragraphs, median_width)`
(`paragraph_finder.py:287`, **không** bọc `process()` như 7.2) — chạy hàm gốc trước (xử lý nhánh
dot-leader ≥ 20 chấm có sẵn), rồi chạy `toc_split.evaluate_paragraph` trên **cùng list**
`paragraphs`, mutate in-place qua `paragraphs[:] = new_paragraphs` (`page.pdf_paragraph` và tham
số `paragraphs` trỏ cùng 1 list object từ `paragraph_finder.py:245`, đã verify source thật ở
AA1/spike 7.4-a).

**Đã đọc lại trực tiếp source `paragraph_finder.py` (0.6.4 đã cài) trong task này** để xác nhận
điểm hook đúng như AA6 mô tả (không suy đoán lại): `process_independent_paragraphs` gọi ở dòng 287
— NGAY SAU `page.pdf_paragraph = paragraphs` (dòng 245) và TRƯỚC `merge_alternating_line_number_
paragraphs` (dòng 291), `update_paragraph_data(paragraph, update_unicode=True)` (dòng 293-294),
`fix_overlapping_paragraphs` (dòng 302), `add_debug_info` (dòng 307), `_set_paragraph_render_order`
(dòng 310). Cũng đọc `process_independent_paragraphs` (dòng 841-889): nhánh dot-leader tạo
`PdfParagraph` mới với `box=Box(0,0,0,0)`, `unicode=""`, `debug_id=generate_base58_id()`, rồi chỉ
gọi `update_paragraph_data(paragraph)`/`update_paragraph_data(new_paragraph)` (KHÔNG
`update_unicode=True`) — patch mới (`_split_toc_paragraphs_in_list`) tái dùng ĐÚNG nguyên mẫu này,
không tự gọi `update_unicode=True` và không tự gán `render_order` (khác hẳn patch 7.2 phải tự làm
cả hai vì nó hook SAU cùng điểm này trong `process()`).

Cờ runtime: `BABELDOC_SHIM_TOC_SPLIT` — mặc định `"0"` (TẮT, khác 2 patch trước mặc định `"1"`) —
đọc qua `_toc_split_enabled()`. `_apply_patch` cập nhật để patch cả 3 (rollback chung nếu babeldoc
đổi cấu trúc — patch mới thêm `hasattr(ParagraphFinder, "process_independent_paragraphs")` check
riêng, cùng cơ chế fail-safe try/except ở tầng trên).

### 7.4-b — Wiring config/runner/orchestrator

- `src/core/config.py`: `Settings.babeldoc_toc_split_enabled: bool = False` (mặc định TẮT theo
  AA5 — "bật sau khi QA live xanh"), comment theo đúng khuôn 2 flag trước.
- `src/services/babeldoc_runner.py`: `BabeldocRunner.__init__` thêm param `toc_split_enabled: bool
  = False`; `translate_pages()` nối `env["BABELDOC_SHIM_TOC_SPLIT"] = "1"/"0"` — chỉ khi shim tổng
  đang bật qua `PYTHONPATH` (cùng khối `if self._line_split_shim_enabled:` như 2 biến kia).
- `src/core/job_orchestrator.py`: `_translator_runner` truyền thêm
  `toc_split_enabled=self._settings.babeldoc_toc_split_enabled` khi dựng `BabeldocRunner`.

### 7.4-c — Test (`tests/test_babeldoc_toc_split.py`, Protocol 6 R6-02)

33 test, tất cả gọi **đúng** hàm production (`evaluate_paragraph`, `mark_toc_tail`,
`sort_line_chars` từ `src.babeldoc_shim.toc_split`) — không chép lại thuật toán:

**Unit test (22 test)** — từng điều kiện AA4 bước 0-4 + các ca chống false-positive named ở
AA4/AA7: folio đứng riêng (`k == len`), ô bảng số kiểu `"4.0"` (thiếu cụm ≥2 chữ cái), văn xuôi
kết thúc bằng số liệu (gap quá nhỏ, ratio ~0.3 < 0.8), số trang ngoài phạm vi (0, >4 chữ số), font
size ≤ 0, ASCII digit vs `str.isdigit()` (Z7-c, `'²'`), deny-list layout (chuẩn hoá lower/strip),
cổng `TOC_MIN_TAIL_LINES`/`TOC_MIN_TAIL_FRACTION`, monotonic (Z4, cho phép bằng nhau), luật dòng
nối cả 2 nhánh `extended=True/False`, và **4 test riêng cho bug continuation-line vừa sửa**
(composition non-line ngay sau dòng đánh dấu dính đúng group trước; nhiều composition non-line
liên tiếp; composition non-line ở cuối paragraph không tạo cut thừa).

Phát hiện phụ trong lúc viết test: `REASON_NO_CUT_POINTS` (nhánh "đánh dấu đủ điều kiện nhưng
không có điểm tách nào") **không thể xảy ra được** với `TOC_MIN_TAIL_LINES=2` hiện tại — chứng
minh bằng tay: bất kỳ dòng đánh dấu nào không phải dòng đánh dấu CUỐI CÙNG luôn tạo ra đúng 1
`cut_after` (vòng lặp mở rộng luôn dừng ngay khi gặp dòng đánh dấu tiếp theo, không bao giờ "nuốt"
được nó), nên có ≥2 dòng đánh dấu thì `cut_after` luôn khác rỗng. Đây là code phòng thủ hợp lệ cho
trường hợp tham số đổi trong tương lai (vd `TOC_MIN_TAIL_LINES=1`), không phải bug — không escalate,
chỉ ghi lại ở đây để không ai mất công viết lại test cho nhánh này lần nữa.

**Golden-fixture test (11 test)** — trên **8 fixture đã commit**
(`tests/fixtures/babeldoc/toc_*_dump.json.gz`), parametrize + test tổng: khớp **chính xác từng
dòng** bảng oracle AA7 (`figoni_p7_toc`=8/28, `figoni_p8_toc`=12/38, `lcb_toc`=11/64, 5 fixture còn
lại=0/0) và **tổng 31 fire/130 cut** — tự chạy lại, không tin lại số cũ. Riêng `test_golden_
fixtures_zero_false_positive_on_non_toc_pages` assert FP=0 tuyệt đối (AA9 điều kiện 3) và
`test_golden_fixture_lcb_toc_all_fires_are_plain_text_layout` xác nhận lại phát hiện AA1 (31/31
paragraph kích hoạt có `layout_label == 'plain text'`) trên chính `lcb_toc` (fixture có
`fired_inside_table_box=5`, ca dễ vô tình mất recall nếu deny-list sai).

**Kết quả**: `uv run pytest -q` → **434 passed** (401 cũ + 33 mới), `uv run ruff check .` → All
checks passed, `uv run ruff format --check` trên toàn bộ file đã sửa/tạo → sạch.

### 7.4-d — Live E2E (R6-03, đo CẢ 2 thứ theo AA9(d)/Z8-4)

Dịch thật qua **đúng** `BabeldocRunner.translate_pages()` với DeepSeek (`.env` có key), so sánh
`toc_split_enabled=False` (baseline) vs `toc_split_enabled=True` (bật tường minh), trên PDF ghép 2
trang Contents Figoni (p7+p8) — **chính là 2 trang nguồn** đã dùng để sinh 2 fixture đã commit
`toc_figoni_contents_p7/p8_dump.json.gz`, lấy lại từ `/tmp/bdprobe/figoni_p7_toc.pdf` +
`figoni_p8_toc.pdf` (còn sống, kiểm tra hôm nay), ghép bằng `pymupdf.insert_pdf`. Dùng đúng flag
production khác (`split_short_lines=True`, `short_line_split_factor=0.8` từ `Settings`).

Đọc PDF output thật bằng PyMuPDF, đếm 2 chỉ số theo AA9(d)/Z8-4:

| Trang | Số dòng "ranh giới mục" (regex trùng AA4 bước 2) baseline → TOC-1 v2 | Số từ còn tiếng Anh (regex `[A-Za-z]{3,}` không kèm dấu tiếng Việt) baseline → TOC-1 v2 |
|---|---|---|
| p7 (Contents, trang 0) | 27 → **57** | 18 → 17 |
| p8 (Contents, trang 1) | 40 → **78** | 17 → 18 |

**(a) Ranh giới mục**: tăng rõ rệt và đúng — đọc trực tiếp text PDF, baseline gộp nhiều mục liền
nhau thành 1 dòng dài (đúng bài học 7.3, ví dụ:
`"Tầm Quan Trọng của Độ Chính Xác trong Lò Bánh 2 Cân và Thước Cân 2 Đơn Vị Đo Lường 3"` — 3 mục
dính 1 dòng), còn bản TOC-1 v2 tách đúng từng dòng riêng:
`"Tầm Quan Trọng của Độ Chính Xác trong Lò Bánh 2"`, `"Cân và Cân Điện Tử 2"`,
`"Đơn Vị Đo Lường 3"` — xác nhận bằng mắt trên toàn bộ text 2 trang, không chỉ tin đếm số dòng.

**(b) Số mục còn tiếng Anh (Z6 check)**: KHÔNG tăng có ý nghĩa (18→17, 17→18 — dao động ±1 do
LLM chọn từ khác nhau giữa 2 lần gọi thật, không phải hồi quy). Đã tự kiểm tra TỪNG từ bị regex bắt
— toàn bộ đều là **false-positive của chính regex đơn giản** (từ tiếng Việt không dấu như "Giai",
"Quan", "trong", "Cho", "nhu", "quy", "tinh", "cao"; số La Mã "III:"; thuật ngữ/danh từ riêng giữ
nguyên hợp lý "Gluten", "Gelatin", "Ounce", "Patent", "GEL") — **không có cụm từ tiếng Anh nguyên
câu nào còn sót**, khác hẳn dấu hiệu Z6 thật (paragraph nguyên vẹn không dịch). **Kết luận: Z6
KHÔNG tái diễn.**

### 7.4-e — Đo hồi quy (0 thay đổi trên 7.1/7.2, kể cả `fix_overlapping_paragraphs`)

Chạy `babeldoc --debug` thật (dump IL, LLM port chết `127.0.0.1:1`, `--ignore-cache`,
`--split-short-lines --short-line-split-factor 0.8`) trên 4 fixture của 7.1/7.2, MỖI fixture 2 lần
(`BABELDOC_SHIM_TOC_SPLIT=0` rồi `=1`), so sánh `paragraph_finder.json` — mỗi paragraph so theo
`unicode` + số composition + `layout_label` + `box` (bỏ qua `debug_id`/`render_order`, có thể đổi
giữa 2 lần chạy vì lý do không liên quan TOC-1):

| Fixture | Số trang | Kết quả so sánh TẮT vs BẬT `TOC_SPLIT` |
|---|---|---|
| `p74_77` (4 trang, nguồn `/tmp/bdprobe/p74_77.pdf`) | 4 | **IDENTICAL — 0 thay đổi** trên cả 4 trang |
| `page14_numbered_list_source` (nguồn: `tests/fixtures/babeldoc/page14_numbered_list_source.pdf`, đã commit) | 1 | **IDENTICAL — 0 thay đổi** |
| `figoni_p20` (nguồn `/tmp/bdprobe/figoni_p20.pdf`) | 1 | **IDENTICAL — 0 thay đổi** |
| `figoni_p22` (nguồn `/tmp/bdprobe/figoni_p22.pdf`) | 1 | **IDENTICAL — 0 thay đổi** |

**0/4 fixture có bất kỳ khác biệt nào** — đúng yêu cầu AA10-c/7.4-e ("không phải mục lục, TOC-1
không được kích hoạt gì cả"). Log `sitecustomize.py` xác nhận patch áp dụng đúng cả 2 chiều
(`... process_independent_paragraphs (buoc 7.4-b — tach muc luc Ca C, TAT qua
BABELDOC_SHIM_TOC_SPLIT=0 (mac dinh))` / `..., bat)`).

**`fix_overlapping_paragraphs` (AA6, nợ `[CHƯA VERIFY]` ở AA12)**: vì phép so sánh trên bao gồm cả
field `box` của mọi paragraph và 4/4 fixture đều IDENTICAL tuyệt đối, đây là bằng chứng gián tiếp
nhưng trực tiếp trên dữ liệu thật rằng hàm này **không cắt box khác đi** khi TOC-1 v2 bật trên các
trang KHÔNG PHẢI mục lục — khớp đúng dự đoán no-op của Tech Lead (AA6 mục cuối). Vẫn giữ nguyên
trạng thái `[CHƯA VERIFY]` cho ca sách leading chặt trên trang MỤC LỤC thật (ngoài phạm vi 4
fixture hồi quy này, vốn không phải mục lục) — không tự ý đóng nợ kỹ thuật này.

### Kết quả kiểm tra chất lượng cuối task

```
uv run pytest -q                     → 434 passed, 420 warnings (~94s)
uv run ruff check .                  → All checks passed!
uv run ruff format --check <files đã sửa/tạo> → sạch
```

**File đã sửa**: `src/babeldoc_shim/toc_split.py` (bug fix continuation-line),
`src/babeldoc_shim/sitecustomize.py` (patch thứ 3 + docstring), `src/core/config.py`
(`babeldoc_toc_split_enabled`), `src/services/babeldoc_runner.py` (param + env),
`src/core/job_orchestrator.py` (wiring).
**File mới**: `tests/test_babeldoc_toc_split.py`.
**KHÔNG đổi default** `babeldoc_toc_split_enabled` — vẫn `False` theo đúng chỉ đạo brief (quyết
định bật để sau QA, không phải việc của Dev).

### Vấn đề cần Tech Lead/Expert quyết định

**Không có.** Mọi kết quả đo (7.4-c oracle AA7, 7.4-d live E2E, 7.4-e hồi quy) đều khớp hoặc tốt
hơn kỳ vọng của AA7/AA9 — không phát sinh sai lệch nào cần escalate. 2 quan sát phụ (không phải
vấn đề, chỉ ghi lại để không mất dấu):
1. `REASON_NO_CUT_POINTS` hiện không thể xảy ra với tham số hiện tại (xem mục 7.4-c) — code phòng
   thủ hợp lệ, không phải bug.
2. `fix_overlapping_paragraphs` xác nhận thêm no-op trên dữ liệu hồi quy (không phải mục lục) —
   nợ `[CHƯA VERIFY]` ở AA12 cho ca sách leading chặt trên trang mục lục thật **vẫn còn mở**, chưa
   có dữ liệu để đóng.

**Chưa spawn Reviewer** (Protocol 7 R7-01) — PM sẽ tổ chức Reviewer thật trước khi coi 7.4-b/c/d/e
là "xong".

## Bug #7 Ca C — Xử lý issue non-blocking từ Reviewer 7.4-b→e (2026-09-08)

Reviewer (`docs/review-report.md`, review 7.4-b→e) APPROVE kèm 3 issue non-blocking. Xử lý 2/3
trong commit này (`2c47a03`):

1. **Thiếu logging Z8-2(iv) trong code production**: yêu cầu "log 1 dòng khi cổng `m/L` hoặc
   monotonic chặn 1 paragraph có ≥2 dòng nghi ngờ mục lục" (Tech Lead chấp nhận ở AA2 dòng Z4)
   trước đó chỉ tồn tại trong script đo của spike (`scripts/toc_split_spike_measure.py`), chưa vào
   `sitecustomize.py` thật. Thêm `logger.warning(...)` trong `_split_toc_paragraphs_in_list` khi
   `result.reason` là `REASON_LOW_FRACTION`/`REASON_NOT_MONOTONIC` và `result.tail_marks >= 2`.
   Thêm 1 test pin cứng (`tests/test_babeldoc_shim_unicode_regression.py`) xác nhận hàm có tham
   chiếu đúng 2 hằng reason + gọi `logger.warning`.
2. **2 entry CHANGELOG trùng nội dung** (do PM lỡ chạy trùng việc với 1 phiên Dev khác đang chạy
   nền — xem chi tiết ở message commit `2c47a03`): đã xoá entry ngắn/trùng của PM, giữ lại entry
   chi tiết của Dev (mục "7.4-b/c/d/e" ngay trên). Số liệu 2 lần đo live E2E khác nhau (đếm block
   PyMuPDF vs đếm dòng theo regex) đã đối chiếu lại bằng cách đọc trực tiếp toàn bộ nội dung trang
   dịch thật — xác nhận không có mục nào bị bỏ sót thật sự, chỉ là 2 phương pháp đếm khác nhau.
3. **`uv.lock` version drift** (issue thứ 3): không liên quan tới Ca C, có từ trước, không xử lý
   trong commit này.

**Kết quả**: `uv run pytest -q` → 435 passed (434 + 1 test pin mới), `ruff check .`/`ruff format
--check .` sạch. Đã qua Reviewer cho toàn bộ commit `2c47a03` (bao gồm cả 2 thay đổi này).

## Bug #7 Ca C — Bật default sau QA Vòng 8 (2026-09-08)

`Settings.babeldoc_toc_split_enabled` đổi default `False` → `True`, đúng điều kiện AA5 ("bật sau
khi QA live xanh") — xem `docs/test-report.md` "QA Vòng 8" (PASS, tự chạy lại độc lập qua cả
`BabeldocRunner` trực tiếp lẫn `JobOrchestrator.run_job()` đầy đủ với DB/DeepSeek thật). Biến môi
trường `BABELDOC_SHIM_TOC_SPLIT`/chính field `Settings` này vẫn là kill-switch độc lập nếu cần
rollback tức thời. `docs/Architecture.md` đã thêm section đóng vòng "Bug #7 Ca C — Đóng vòng:
implement + QA + bật default" xác nhận không phát sinh câu hỏi thiết kế mới cần Tech Lead/Domain
Expert quyết định — đây là quyết định cơ học đã được AA5 định tiêu chí từ trước.

`uv run pytest -q` → 435 passed (không đổi số test, chỉ đổi giá trị default), `ruff check .`/`ruff
format --check .` sạch.

## Release v1.2.7 (2026-09-08)

`pyproject.toml` bump `1.2.6` → `1.2.7`. Nội dung release: toàn bộ chuỗi fix Bug #7 (List
line-break/numbered-list/mục lục regression) —

- **7.0+7.1**: sitecustomize shim sửa lỗi tách dòng gốc (ký tự trắng lấp khe giữa 2 dòng).
- **7.2 (Ca A)**: tách paragraph numbered-list dính chung qua marker tăng dần (B-2b).
- **Hotfix 7.2**: sửa bug `unicode=""` khiến mục numbered-list bị bỏ dịch (phát hiện bởi Domain
  Expert trong lúc phản biện thiết kế Ca C).
- **7.3**: đo lại mục lục sau 7.1+7.2 — xác nhận Ca C còn nguyên, phát hiện thêm 1 lỗi heading
  2 dòng bị đảo ký tự chéo nhau (7.1 vô tình sửa được).
- **7.4 (Ca C)**: thiết kế TOC-1 v2 (Tech Lead, phản biện bởi Domain Expert) — tách mục lục theo
  khoảng hở hình học trước số trang cuối dòng + cổng cố kết chống false-positive. Spike PASS 6/6
  gate, implement đầy đủ, Reviewer APPROVE, QA Vòng 8 PASS — **bật default** trong bản release
  này.

Toàn bộ chuỗi đã qua đủ 6 vai trò theo CLAUDE.md (PM điều phối, Tech Lead thiết kế + phản biện
Domain Expert, Dev implement, Reviewer — 6 lần review độc lập xuyên suốt chuỗi, QA — Vòng 8 verify
release). `uv run pytest -q` → 435 passed, `ruff check`/`ruff format --check` sạch.

**Known limitation mang sang, không chặn release** (đã ghi trong `project_state.json`, không phải
phát sinh mới): Bug #6 (nhánh `pdf_scan` của tính năng overlay chữ xoay P1.1) vẫn đang BLOCKED ở
circuit breaker Dev↔QA 5/5, cần PM/Tech Lead quyết định hướng thiết kế lại riêng — không liên quan
và không bị ảnh hưởng bởi release Bug #7 này (2 tính năng độc lập).

## US-16 v2 — Mở rộng nén ảnh sang `/FlateDecode` + sửa `bilingual_merge.py` (2026-09-08)

Implement theo thiết kế đã chốt và được user duyệt (Protocol 2) tại `docs/Architecture.md` mục
"US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08)" (section W6 — thuật toán hợp
nhất 13 bước, W7 — chữ ký hàm, W8 — bảng test bắt buộc). Đây là bản implement sau 2 vòng phản biện
(Tech Lead → Domain Expert (Fable) → Tech Lead chốt lại), không phải mục "US-16 v2" gốc (V1-V11) —
W6 SUPERSEDE 4 bước (4a/4b/4d/7) của V5 và toàn bộ V9.1.

### 2 quyết định user đã duyệt — implement cả hai (W10)

- **(a)** Mở rộng `BR-IMGCOMP-02` → `BR-IMGCOMP-02b`: cho phép re-encode cả ảnh `/FlateDecode`
  (zlib lossless), không chỉ `Filter: null` như v1. Lý do: Flate là lossless nên với ảnh chụp gần
  như không giảm dung lượng gì — coi nó "tương đương đã nén" là suy diễn sai của code v1.
- **(b)** Sửa `src/postprocess/bilingual_merge.py:22`: `output_doc.save(output_path)` trần →
  `output_doc.save(output_path, garbage=4, deflate=True)`. Cơ chế đúng (đã sửa lại từ chẩn đoán sai
  ban đầu của Tech Lead ở V9.1, xem X6/W4): `create_bilingual_pdf()` gọi `insert_pdf` **từng trang
  một** nên nhân bản font nhúng của bản VI — đo thật 9 font gốc → 592 bản sao trên job 596 trang.
  `garbage=4` (dedupe object trùng) mới là tham số làm việc; `deflate=True` một mình cho **0 byte**
  lợi ích ở đây (mọi stream đã Flate sẵn) — vì vậy test mới assert trực tiếp SỐ LƯỢNG font stream
  (`/Length1`) chứ không chỉ kích thước file, đúng yêu cầu W4 (một test chỉ theo kích thước sẽ
  không bắt được nếu sau này ai đó "tối giản" nhầm thành chỉ `deflate=True`).

### 3 sửa lỗi có sẵn của v1 — độc lập với (a)/(b), áp dụng trong mọi kịch bản (W1-W3)

1. **Guard colorspace đọc `info[5]`** (từ `get_page_images(pno, full=True)`), KHÔNG dùng
   `Pixmap.colorspace.name` — field đó bị PyMuPDF "expand" Indexed sang base colorspace ngay khi
   dựng `Pixmap` nên không bao giờ thấy `Indexed(...)`; đây chính là bug Domain Expert bắt được
   (đo thật: 2 ảnh Indexed lọt guard cũ). Allowlist mới:
   `{DeviceGray, DeviceRGB, DeviceCMYK, ICCBased}`, chạy TRƯỚC khi dựng Pixmap (rẻ hơn). Lớp hai:
   kiểm tra `pix.n` khớp bảng kỳ vọng theo `cs_family` (không dùng `pix.colorspace.name` — chính
   field từng gây bug lúc spike, giữ lại làm "lớp hai" là thêm rủi ro chứ không thêm an toàn).
2. **KHÔNG ghi đè `/ColorSpace` nữa** — xoá `_COLORSPACE_BY_CHANNELS` và dòng `xref_set_key(xref,
   "ColorSpace", ...)`. Ghi đè `ICCBased` → `/DeviceCMYK` vứt ICC profile gốc: vô hại trên MuPDF
   (nó tự thay bằng profile mặc định của chính nó, nên MuPDF-vs-MuPDF pixel-diff đọc 0.00) nhưng
   lệch màu thật 4.4–7.0/255 trên macOS Preview/Quartz — Tech Lead **không tự đo** loại lỗi này
   (đo bằng MuPDF chỉ chứng minh nhất quán với chính nó), Domain Expert phát hiện bằng renderer
   độc lập (Quartz qua `sips`). **Ràng buộc bắt buộc (W2.2)**: sửa #1 và #2 PHẢI đi cùng 1 commit —
   nếu chỉ làm #2 mà thiếu #1, ảnh Indexed lọt guard sẽ bị JPEG hoá trong khi `/ColorSpace` vẫn ghi
   `[/Indexed ...]` → PDF hỏng nặng hơn hiện trạng (mỗi byte JPEG bị đọc nhầm thành index bảng màu).
3. **Guard `/Mask`** (color-key array hoặc ref stencil mask) — cùng nhóm với `/SMask`/`/ImageMask`
   đã có, skip thay vì recompress. Đổi luôn `if pix.alpha: pix = Pixmap(pix, 0)` (drop alpha) thành
   **skip** — nếu vẫn còn alpha sau khi đã guard SMask/Mask thì nghĩa là nguồn chưa biết, drop âm
   thầm vừa mất thông tin vừa để lại key gây ra nó trong PDF dict.
4. **Dọn `/Decode`** sau khi re-encode (chỉ khi key tồn tại và khác `null`): `Pixmap(doc, xref)` ÁP
   DỤNG `/Decode` lúc decode, nhưng `update_stream()` KHÔNG xoá key này — để nguyên sẽ áp transform
   lần thứ 2 ở mọi lần render sau → ảnh âm bản. Lỗi có sẵn trong v1 cho mọi ảnh `Filter: null` có
   `/Decode` không phải identity, chưa từng phát tác (mọi `/Decode` khảo sát được đều identity).

### File đã sửa

- `src/postprocess/image_compress.py`: implement lại toàn bộ theo W6 (13 bước) — eligibility filter
  mở rộng Flate, guard mask/alpha/`Mask`/kích thước/bpc/colorspace theo đúng thứ tự rẻ→đắt, không
  ghi `/ColorSpace`, dọn `/Decode`. `ImageCompressStats` thêm 2 field: `images_skipped_small`,
  `images_skipped_colorspace`. Chữ ký hàm thêm `min_recompress_bytes: int = 4096` (keyword-only,
  chỉ để test tham số hoá được — không phải điểm cấu hình `.env`/UI, BR-IMGCOMP-03 giữ nguyên).
- `src/postprocess/bilingual_merge.py`: 1 dòng, `save(output_path)` → `save(output_path, garbage=4,
  deflate=True)`.
- `tests/fixtures/babeldoc/job78674af9_flate_sample.pdf` (fixture vàng mới, 1.75 MB, trích trang
  22+25 0-based từ `data/outputs/78674af9-.../translated_vi.pdf` bằng `insert_pdf` +
  `save(garbage=4, deflate=True)`): 2 ảnh `/FlateDecode` `ICCBased` (1 Gray, 1 CMYK) + 1 ảnh
  `/DCTDecode` đã nén sẵn.
- `tests/fixtures/babeldoc/job136645f9_indexed_sample.pdf` (fixture vàng mới, 1.15 MB, trích trang
  168 0-based từ `data/outputs/136645f9-.../translated_vi.pdf`): 5 ảnh `/FlateDecode` `Indexed` + 6
  ảnh `/DCTDecode` — bằng chứng dữ liệu thật DUY NHẤT cho điều kiện tiên quyết của W2.2 (Tech Lead
  nâng lên **blocking** so với đề xuất non-blocking ban đầu của Domain Expert).
- `tests/fixtures/babeldoc/README.md`: append xuất xứ 2 fixture trên (job id, trang gốc, ngày
  trích, lệnh trích, nội dung xác nhận).
- `tests/test_image_compress.py`: thêm 5 test mới theo bảng W8 (giữ nguyên 3 test cũ, không sửa
  assertion — đúng yêu cầu hồi quy V7 "v2 phải cho kết quả y hệt v1 trên fixture cũ"):
  1. Fixture Flate mới: `images_recompressed == 2`, text/số trang giữ nguyên, ảnh DCT giữ byte
     nguyên vẹn.
  2. Guard Indexed (**blocking**, W8 #9): chạy `min_recompress_bytes=0` trên fixture Indexed →
     `images_skipped_colorspace == 5` (đúng số ảnh Indexed thật), `images_recompressed == 0`,
     `/ColorSpace` không đổi.
  3. `/ColorSpace` giữ nguyên (W8 #10): ảnh ICCBased sau re-encode vẫn `info[5] == 'ICCBased'`,
     `ColorSpace` key y hệt trước.
  4. `/Decode` mức pixel (**blocking**, nâng cấp W8 #12 theo X7.1): không chỉ assert
     `xref_get_key == ('null','null')` mà còn render trang trước/sau và so pixel — đo được
     0.21/255 (Domain Expert đo case đúng: 0.46/255; case sai/double-apply: 42.28/255).
  5. Guard `/Mask` (**blocking**, W8 #11): inject `/Mask [200 255]`, assert ảnh bị skip
     (`images_skipped_unsupported += 1`), stream giữ byte nguyên vẹn.
- `tests/test_bilingual_merge.py`: thêm 1 test dùng font TTF nhúng thật (`fonts/NotoSerif-
  Regular.ttf`, base14 không nhúng nên không tái hiện được bug) — xác nhận số `/Length1` font
  stream sau merge KHÔNG tăng so với 1 bản gốc (đo thủ công lúc implement: không có `garbage=4` →
  40 stream trên 20 trang x 2 tài liệu; có `garbage=4` → 1 stream).
- `docs/CHANGELOG.md`: mục này.

### Kết quả chạy test

`.venv/bin/python -m pytest tests/test_image_compress.py tests/test_bilingual_merge.py
tests/integration/test_job_orchestrator.py -q` → **34 passed**. `uv run pytest -q` (toàn bộ repo)
→ **441 passed** (435 trước đó + 6 test mới), không có test nào fail/skip. `ruff check`/`ruff
format --check` sạch trên toàn bộ file đã sửa.

### R5-03/R6-03 — chạy thật trên chính file lỗi (không mock)

Copy `data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf` ra thư mục tạm ngoài
`data/outputs/` (file gốc không bị đụng — xác nhận lại bằng MD5 + timestamp sau khi chạy), chạy
`compress_pdf_images()` thật:

| Chỉ số | Kết quả đo | Số Tech Lead đo (Architecture.md V7/W9) |
|---|---|---|
| Kích thước | 46.87 MB → **25.19 MB (−46.3%)** | 46.87 MB → 25.19 MB (−46.3%) — khớp |
| Số trang | 30 → **30** | 30 → 30 — khớp |
| Text từng trang | **giống hệt** (so trực tiếp `get_text()` từng trang) | giống hệt — khớp |
| Thời gian | **1.41 giây** | 1.4–1.5 giây — khớp |
| Ảnh xử lý | `images_recompressed=19, images_skipped_already_compressed=42, images_skipped_small=38, images_skipped_colorspace=0, images_skipped_larger=0, images_skipped_unsupported=0` | 19 re-encode / 42 skip đã nén / 38 skip nhỏ / 0 lỗi / 0 nở file — khớp |

Kết quả implement khớp chính xác số liệu thiết kế đã verify 2 lần độc lập (Tech Lead + Domain
Expert). Không phát sinh sai lệch nào cần escalate Tech Lead.

### Khác biệt so với thiết kế

Không có khác biệt về logic. 1 điểm khác biệt số liệu KHÔNG đáng kể: fixture
`job78674af9_flate_sample.pdf` khi Dev tự trích lại (đúng quy trình `insert_pdf` +
`save(garbage=4, deflate=True)` như Architecture.md chỉ định) cho 1.75 MB / nén còn ~1.03 MB, khác
với số đo tham khảo trong Architecture.md (1.66 MB / 0.85 MB — kết quả trích thử của Tech Lead lúc
viết thiết kế). Số lượng ảnh re-encode và guard đều khớp tuyệt đối (`recompressed=2,
skip_filter=1`); chênh byte tuyệt đối chỉ là do 2 lần trích độc lập không tất định 100% ở tầng nén
Flate nội bộ của PyMuPDF, không ảnh hưởng bất kỳ assertion hay guard nào.

**Chưa spawn Reviewer** (Protocol 7 R7-01) — PM sẽ tổ chức Reviewer thật trước khi coi US-16 v2 là
"xong" và trước khi commit (pre-commit hook cũng sẽ chặn commit nếu thiếu `docs/review-report.md`
trong cùng commit).

## Bug #8 — "Chữ nhảy lung tung" tái phát ở v1.2.8: MediaBox/CropBox offset trong font_shrink (2026-09-08)

### Bối cảnh

User báo bản dịch full-book *Le Cordon Bleu Patisserie and Baking Foundations* (job
`f3c22ddc-374a-4408-9dd3-99c49da802e8`, chạy dưới app version 1.2.8) bị chữ chồng đè lên nhau,
nghi là Bug #7 (TOC-1 v2, release v1.2.7) tái phát. User cũng hỏi liệu có phải do 2 session Claude
Code chạy song song trên cùng repo (có thật — nhiều session khác đang hoạt động trên project này)
gây ra.

### Chẩn đoán (Tech Lead, live reproduction — không mock, không đoán)

**KHÔNG phải TOC-1 v2 regression, và KHÔNG phải do chạy song song session.** TOC-1 v2 vẫn được
kích hoạt đúng trong pipeline thật (xác nhận qua `job_orchestrator.py:248` +
`Settings.babeldoc_toc_split_enabled=True`). Đã loại trừ giả thuyết concurrency 32-thread của
babeldoc (adaptive, bảng `concurrency_state`) bằng live reproduction đơn lẻ, tất định.

**Root cause thật**: `src/postprocess/font_shrink.py::_redraw_span` gọi `page.insert_text()` để vẽ
lại span sau khi co font — nhưng PyMuPDF's `Shape.insert_text` (đọc trực tiếp source cài trong
venv, `pymupdf` 1.28.2, class `Shape`) offset toạ độ theo **CropBox** (`page.cropbox_position`),
trong khi `page.get_text("dict")`/`add_redact_annot` dùng hệ toạ độ theo `page.rect` (giao của
CropBox và MediaBox, chuẩn hoá về gốc (0,0)). Khi CropBox không nằm gọn trong MediaBox (case thật:
Le Cordon Bleu có `mediabox=(33,33,681,816)`, `cropbox=(0,-33,714,816)` — CropBox lớn hơn MediaBox
mọi phía, không chuẩn PDF spec nhưng là trạng thái thật của output pdf2zh/babeldoc cho cuốn này),
2 hệ toạ độ lệch nhau → chữ co-font bị vẽ sai vị trí, đè lên nội dung khác.

Đo trực tiếp 1 lời gọi đơn lẻ: span `"Giới thiệu 4"` bbox gốc `[120.1, 289.5]` → sau redraw (code
cũ) bị vẽ tại `[87.1, 258.4]`, lệch đúng `(-33, -31)` = origin của MediaBox. Đếm bbox-overlap
(diện tích giao > 200pt²) trên trang mục lục (page index 6, `translated_vi.pdf` output thật):
**12 cặp block chồng đè** trước fix.

**Vì sao QA v1.2.7 không bắt được**: live E2E QA lúc đó chỉ chạy trên sách Figoni, có
`mediabox=(0,0,684,855)` (origin đã là 0) → độ lệch = 0, bug không lộ. TOC-1 v2 không gây bug này
nhưng khuếch đại triệu chứng (tách nhiều dòng ngắn hơn → nhiều dòng đi qua nhánh co-font/redraw
hơn). Bug có từ trước v1.2.7, không nằm trong diff v1.2.7→v1.2.8.

**Phạm vi ảnh hưởng**: mọi trang có dòng bị co font trên PDF có CropBox không nằm gọn trong
MediaBox — đo được overlap thêm ở trang 5, 9, 12, 25, 35 của cùng cuốn Le Cordon Bleu.

### Fix (Dev)

Hàm mới `_insert_text_origin_fix(page, origin)` trong `src/postprocess/font_shrink.py`, gọi từ
`_redraw_span()` trước khi `insert_text()`. Công thức (per-axis, `max(..., 0)` để không phá case
CropBox hợp lệ nhỏ hơn MediaBox — ví dụ margin box hợp pháp):

```
dx = max(mediabox.x0 - cropbox_position.x, 0.0)
dy = max(-cropbox_position.y, 0.0)
```

Nguồn xác thực: đọc trực tiếp `pymupdf/__init__.py` (venv, `Shape.__init__` và
`Shape.insert_text`) cài đặt tại `.venv/lib/python3.14/site-packages/pymupdf/__init__.py`.

### Test

`tests/test_font_shrink.py::test_redraw_span_lands_on_its_own_bbox_despite_mediabox_cropbox_offset`
— parametrize trên 2 fixture: `tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf` (CropBox lệch thật,
case bug) và `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf` (CropBox nhỏ hơn
MediaBox hợp lệ — margin box, phải KHÔNG bị "sửa" nhầm). Assert giá trị origin cụ thể sau redraw
khớp bbox gốc từ `get_text("dict")` (không chỉ `assert_called()` — theo R6-02).

**PM tự verify độc lập** (không chỉ tin báo cáo của Dev agent, vì agent lần đầu bị treo giữa
chừng khi tự sửa công thức): `git stash push -- src/postprocess/font_shrink.py` (giữ nguyên file
test) rồi `uv run pytest tests/test_font_shrink.py` → lỗi import (thiếu
`_insert_text_origin_fix` — đúng kỳ vọng khi chưa có fix); `git stash pop` khôi phục → **12
passed**. Xác nhận test mới thực sự phụ thuộc vào fix, không pass giả (vacuous).

### Trạng thái — CHƯA xong, còn thiếu trước khi release

- **Chưa có live E2E cấp pipeline đầy đủ** (chạy `font_shrink_page()` qua đúng đường
  `job_orchestrator.py`, không chỉ gọi thẳng `_redraw_span` trong unit test) đo lại số overlap
  thật trên trang mục lục/trang 5,9,12,25,35 — Dev agent thứ 2 được giao việc này bị fail do rate
  limit session (`resets 7:30pm Asia/Saigon`), chưa chạy được. Đây là việc còn nợ, PM sẽ giao lại
  hoặc để QA đảm nhiệm phần R5-03/R6-03 live E2E trước khi duyệt release.
- **Chưa spawn Reviewer** (Protocol 7 R7-01) — chưa được coi là "xong".
- Checklist R5-04 (external contract verified against real source): **YES** — nguồn:
  `pymupdf/__init__.py` cài trong venv, đọc trực tiếp source `Shape.insert_text`/`Shape.__init__`,
  version 1.28.2.

### Vòng 2 (Dev, sau REJECT của Reviewer — xem section "Bug #8 ... review `font_shrink.py`
MediaBox/CropBox fix" trong `docs/review-report.md`)

Reviewer round 1 REJECT: đúng tại điểm sửa (`font_shrink.py`) nhưng phạm vi hẹp hơn phạm vi
thật của bug — 2 call site khác của `page.insert_text()` mắc CHÍNH XÁC cùng 1 bug, chưa được
sửa. Vòng 2 xử lý đầy đủ 5 yêu cầu của Reviewer:

1. **Tách hàm dùng chung**: `_insert_text_origin_fix` chuyển từ `font_shrink.py` thành
   `insert_text_origin_fix()` (public) tại module mới `src/utils/pdf_coords.py` — cạnh
   `src/utils/retry.py`/`excel_utils.py` đã có sẵn, đúng quy ước "shared helper" của project
   (không đặt trong `src/postprocess/` vì 1 trong 3 nơi dùng — `searchable_pdf.py` — nằm ở
   `src/preprocess/`, tránh preprocess phải phụ thuộc ngược vào postprocess). `font_shrink.py`
   giờ chỉ `import` hàm này, không còn định nghĩa riêng.
2. **Áp dụng cho `rotated_text_overlay.py::_draw_block`** (issue Blocking #1): mỗi `pivot`
   tính theo dòng (kể cả pivot dùng làm neo `morph`) được đưa qua `insert_text_origin_fix()`
   trước khi gọi `page.insert_text()` — cùng pattern `_redraw_span` đã dùng (fix áp cho `origin`
   1 lần trước khi nó chảy vào tuple `morph`).
3. **Áp dụng cho `searchable_pdf.py::_insert_invisible_text`** (issue non-blocking #2, làm luôn
   theo yêu cầu "làm luôn cho gọn"): điểm `(x0, y1 - h*0.15)` được đưa qua
   `insert_text_origin_fix()` trước khi `page.insert_text(..., render_mode=3)`.
4. **Test regression mới** `tests/test_rotated_text_overlay.py::
   test_draw_block_lands_on_pivot_despite_mediabox_cropbox_offset` — dùng lại chính
   `tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf` và đúng giá trị pivot thực nghiệm Reviewer
   đã đo (`(261.53, 154.71)` → lệch `(228.53, 121.71)` trước fix). **Phát hiện khi viết test**:
   pivot đó trùng gần như tuyệt đối với 1 span thật đã có sẵn trên trang ("Contents" heading) —
   assert theo *origin* sẽ pass giả (vacuous) bất kể `_draw_block` có vẽ đúng hay không, vì luôn
   tìm thấy span "Contents" có sẵn. Sửa bằng cách match theo **text marker riêng** (không có
   trên trang) trước, rồi mới kiểm tra origin của CHÍNH span đó — tự verify lại bằng `git stash`
   trên `src/postprocess/rotated_text_overlay.py`: FAIL đúng ở vị trí lệch `(228.53, 121.71)`
   trước fix, PASS sau fix.
5. **2 lỗi docstring/comment Reviewer chỉ ra**: (a) xoá câu "see the false-start note at the
   bottom" (tham chiếu treo, không có section đó) khi viết lại docstring cho
   `insert_text_origin_fix()` ở vị trí mới; (b) sửa header comment ở
   `tests/test_font_shrink.py` (dòng ~241) từ "MediaBox origin != (0,0)" (lý thuyết SAI mà chính
   docstring minh thị bác bỏ) thành đúng bản chất bug (CropBox không nằm gọn trong MediaBox).

**Test đã chạy (số thật)**:

```
uv run pytest tests/test_font_shrink.py -q                    → 12 passed
uv run pytest tests/test_rotated_text_overlay.py -q           → 10 passed, 1 FAILED (xem dưới)
uv run pytest tests/preprocess/test_searchable_pdf.py -q      → 9 passed
uv run ruff check <5 file sửa>                                 → All checks passed!
uv run ruff format --check <5 file sửa>                        → đã format
```

**PHÁT HIỆN MỚI, NGOÀI PHẠM VI 5 MỤC TRÊN — không tự sửa, đã flag riêng** (spawn_task
`task_062a9bd5`, "Fix rotated_text_overlay pivot overflow at page edge"): áp đúng fix
MediaBox/CropBox cho `_draw_block` làm 1 test ĐANG PASS trước đó
(`test_overlay_rotated_text_draws_translated_text_at_correct_angle`) bắt đầu FAIL. Root cause
(đã chẩn đoán, CHƯA sửa — khác cơ chế với Bug #8): `_draw_block` tính pivot của mỗi dòng bằng
cách ngoại suy TUYẾN TÍNH chỉ từ origin của DÒNG ĐẦU TIÊN (`block.pivot`) cộng bước cố định
theo hướng chữ, KHÔNG dùng origin thật của từng dòng, KHÔNG kiểm tra biên trang. Trên fixture
`rotated_text_p67_source.pdf`, dòng đầu ("Disaccharide.") nằm ở x≈409, nhưng các dòng thân đoạn
văn thật lại ở x≈337-377 — ngoại suy lệch baseline ~35-70pt. Cộng với bề rộng mỗi dòng dịch
(~200pt), 1-2 dòng cuối trước fix Bug #8 chỉ còn margin ~5.6pt trong biên phải trang (648pt) —
CỰC KỲ MỎNG MANH nhưng vẫn pass. Fix Bug #8 dịch điểm chèn thêm +33 sang phải, đẩy 1-2 dòng cuối
đó lố ra ngoài biên trang, và PyMuPDF's `get_text()`/rendering CẮT thật các ký tự cuối dòng
(verify thực nghiệm độc lập: `page.insert_text((600,100), "Hello World Testing Clip",
fontsize=11)` trên trang rộng 648pt → extract ra chỉ `"Hello Wor"`). Đây là 1 lỗi khác cơ chế,
có từ trước, bị Bug #8's CropBox bug VÔ TÌNH che giấu (dịch trái đủ để lọt vào biên) — giờ mới lộ
ra khi Bug #8 được sửa đúng. KHÔNG sửa trong lần này (ngoài phạm vi 5 mục PM giao, cần thiết kế
lại cách tính pivot — không phải patch nhỏ), đã tạo task riêng theo dõi.

**Trạng thái**: 5/5 mục Reviewer yêu cầu đã làm xong, `docs/CHANGELOG.md` chỉ append (không ghi
đè). PM sẽ giao Reviewer lại vòng 2 — KHÔNG tự báo "đã approve"/"sẵn sàng release". 1 test hiện
có (`test_overlay_rotated_text_draws_translated_text_at_correct_angle`) đang FAIL vì lý do NGOÀI
phạm vi bug này (xem trên) — Reviewer/PM cần quyết định có chặn round này hay tách riêng.

## US-15 — Markdown parse-only, nhánh PDF (born-digital + scan) — implement theo Architecture.md
## §6.15 (2026-09-08)

Implement `job_type=parse_only` cho `pdf_digital`/`pdf_scan` đúng theo thiết kế đã chốt ở
`docs/Architecture.md` §6.15 (qua Tech Lead + phản biện Domain Expert + sửa lại, Human Checkpoint
2 đã qua). **KHÔNG làm nhánh EPUB** (phụ thuộc US-22 `EpubDocument`, chưa implement — theo đúng
thứ tự ưu tiên user chọn 7-4-5-1-2-3-6).

### `src/core/job_orchestrator.py`

- **S15-1**: `run_job()` giờ rẽ theo `job.job_type` TRƯỚC mọi rẽ nhánh khác — `if job.job_type ==
  "parse_only": return await self.run_parse_only(job, db_session)` chèn ngay đầu hàm, trước Step 1
  (reject EPUB của luồng translate). Sửa đúng lỗi kiến trúc gốc của §6.8/§6.15 bản đầu (EPUB bị
  reject ở Step 1 trước mọi rẽ nhánh khiến `parse_only` chết oan).
- **`run_parse_only()`** (hàm riêng, không nhồi `if job_type` rải rác vào 10 Step của luồng
  translate — cùng lý do 6.14.7 chọn engine 1 lần duy nhất):
  - EPUB → raise `EpubNotSupportedError` (lưới an toàn thứ 2; chặn chính nằm ở API layer, xem
    dưới).
  - Đếm `total_pages` nếu chưa có (PyMuPDF).
  - **S15-9**: `mineru_runner is None` hoặc `MinerURunner.health()` fail → raise loạt (không bắt),
    KHÔNG để job chờ tới timeout — cùng shape với guard `mineru_runner is None` hiện có của
    `_build_ocr_bridge()` (BR-OCR-01).
  - `job.status = "parsing"` (status MỚI, xem bên dưới) + `started_at`.
  - `parse_method`: `"txt"` cho `pdf_digital`, `"ocr"` cho `pdf_scan`.
  - **S15-14**: `timeout_seconds = max(600, total_pages * 6)` — thay hằng số 3600s cố định (đo
    thật 89s/25 trang ≈ 3.6s/trang, hệ số 6 = 3.6 × ~1.65 biên an toàn).
  - **S15-13**: callback `_should_cancel()` (đọc lại `job.cancel_requested` từ DB mỗi vòng poll)
    truyền xuống `MinerURunner.parse_document(..., should_cancel=...)` — `MinerUCancelledError` →
    `job.status = "cancelled"` (không phải "failed").
  - **S15-6 (viết lại đúng theo bản chốt sau phản biện)**: `ocr_confidence`/`ocr_dropped_spans` ép
    `None` tường minh cho `pdf_digital` bất kể `quality.confidence` runner trả về gì (MinerU 3.4.5
    gán `score=1.0` cho span text-layer ở mode `txt` — không phải tín hiệu OCR thật); ghi giá trị
    thật + gọi `_emit_ocr_warning_if_low()` cho `pdf_scan`.
  - **S15-5**: guard Markdown rỗng (0 ký tự sau `.strip()`) → `ParseOnlyEmptyOutputError`, job
    `failed` — kiểm tra 2 lần: ngay sau khi MinerU trả về, VÀ đọc lại chính file `document.md` vừa
    ghi vào `data/outputs/` (R6-02, không tin biến trong bộ nhớ).
  - **S15-3/S15-4 (bản chốt sau phản biện, KHÔNG phải bản gốc)**: đóng gói ZIP **eager** ngay
    trong `run_parse_only()` (không lazy trong `download.py`) — danh sách file tường minh
    (`document.md` + từng file `images/`), KHÔNG `os.walk()` (walk là đường duy nhất khiến zip tự
    nén chính nó); ghi ra `.tmp` rồi `os.replace()`. `job.output_path` trỏ thẳng file `.zip`.
  - **Guard ZIP mới** (§6.15.4 bước 5, thêm sau phản biện Expert): mở lại CHÍNH file zip vừa ghi —
    `testzip() is None`, `"document.md" in namelist()`, số entry `images/` == số file trên đĩa —
    không đạt → `ParseOnlyZipGuardError`, job `failed`.
  - Finalize: `actual_cost = 0.0`, `cost_source = "metered"` (0 là số đo thật, không phải ước
    tính), `completed_at` được set, broadcast `job_completed` cùng shape với luồng translate.
- **`_run_mineru_and_record_quality()`** (helper mới, S15-13): 1 định nghĩa DUY NHẤT cho "gọi
  MinerU + ghi `ocr_confidence`/`ocr_dropped_spans` + emit US-11 warning", dùng chung bởi
  `_build_ocr_bridge()` (translate/`pdf_scan`, hành vi giữ nguyên 100%) và
  `run_parse_only()`. Tham số `record_confidence=False` cho phép `run_parse_only()`'s
  `pdf_digital` branch lấy `MinerUResult` thật (cần cho guard) mà KHÔNG để giá trị confidence rò
  vào `job.ocr_confidence`.
- 2 exception mới: `ParseOnlyEmptyOutputError`, `ParseOnlyZipGuardError`. Cập nhật docstring
  `EpubNotSupportedError` để không còn nói riêng về `bilingual_book_maker` (giờ dùng chung cho cả
  2 lý do EPUB chưa hỗ trợ: translate lẫn parse-only).

### `src/services/mineru_runner.py`

- `MinerUCancelledError(MinerUError)` — raise bởi `_poll_until_done()` khi `should_cancel()` trả
  `True`. Known limitation ghi rõ trong docstring: MinerU không có endpoint huỷ task đã verify
  (§6.9.2 không liệt kê) — `⚠️ ASSUMED` task vẫn chạy tiếp server-side, chấp nhận được (compute
  local, $0).
- `parse_document()`/`_poll_until_done()` nhận thêm `task_timeout_seconds: float | None` (override
  timeout của constructor CHO 1 LẦN GỌI, không đổi hành vi mặc định khi không truyền) và
  `should_cancel: Callable[[], Awaitable[bool]] | None`, kiểm tra mỗi vòng poll TRƯỚC khi gọi
  `GET /tasks/{id}`. Cả 2 tham số optional, backward-compatible — mọi call site cũ (kể cả
  `_build_ocr_bridge()`) không đổi hành vi.

### `src/api/routes/jobs.py`

- **S15-2 (mở rộng sau phản biện)**: bỏ `_mark_parse_only_unsupported()` hoàn toàn (cả
  `create_job` LẪN `create_batch` — bản S15-2 gốc chỉ nói `create_job`, batch vẫn chết nếu chỉ sửa
  1 chỗ). `parse_only` giờ đi CÙNG đường với `translate`: `status="queued"` +
  `_schedule_background(...)`.
- **S15-8 (chặn ở API layer, đúng thiết kế)**: `_reject_epub_parse_only()` — `job_type=parse_only`
  + `file_type=epub` → HTTP 400 rõ ràng TRƯỚC KHI tạo `Job` row, gọi từ cả `create_job` và
  `create_batch` (per-upload).
- **S15-10 [BLOCKING, phát hiện bởi Domain Expert]**: `_find_completed_duplicate()` thêm điều
  kiện `Job.job_type == "translate"` — job `parse_only` đã `completed` KHÔNG còn bị coi là "đã
  dịch rồi" khi user sau đó tạo job `translate` trên cùng file hash.
- **S15-11 [BLOCKING, phát hiện bởi Domain Expert]**: `retry_job()` bỏ hẳn block chặn `parse_only`
  (400 cũ) — mâu thuẫn trực tiếp với S15-9 (fail sớm khi MinerU chưa chạy thì phải retry được sau
  khi user bật MinerU lên). `_resolve_provider_or_400`/`_enforce_cost_gate` giờ chỉ chạy khi
  `job.job_type == "translate"`.
- **S15-12 [BLOCKING, phát hiện bởi Domain Expert]**: status mới `"parsing"` — thêm vào
  `_ACTIVE_JOB_STATUSES` (chặn `DELETE /api/jobs/{id}` trong lúc MinerU đang ghi
  `data/processing/{job_id}/parse_output/`, tránh rmtree giữa chừng).
- `GET /api/jobs` thêm query param `job_type` (optional, cùng kiểu lọc với `status` đã có) —
  S15-7/BR-PARSE-04.

### `src/api/routes/download.py`

- **S15-3**: `media_type` suy từ `result_path.suffix` (`.pdf`/`.zip`/`.epub` → MIME tương ứng,
  mặc định `application/octet-stream`) thay vì hardcode `"application/pdf"`. Tên file
  `{stem}_markdown_{timestamp}.zip` cho job `parse_only`, giữ nguyên pattern `_vi`/`_bilingual` +
  timestamp cho `translate`.

### Frontend (`web/`)

- `web/js/app.js`: `RESTORABLE_STATUSES`, `CANCELLABLE_STATUSES`, `statusBadgeClass()` thêm
  `"parsing"`.
- `web/index.html`: progress bar hiện cho status `"parsing"` (thông báo riêng "Đang parse
  (MinerU)..." thay vì %/chunk vô nghĩa); nút Tải/Chạy lại đổi nhãn theo `job_type`.
- `web/history.html` + `web/js/history.js`: filter `job_type` mới (mặc định `"translate"`,
  BR-PARSE-04 — không trộn job parse vào "translation history"), option `"parsing"` trong filter
  status, badge màu, nhãn link tải đổi theo `job_type`.

### Test (Protocol 6 R6-02 — assert giá trị cụ thể, không chỉ `assert_called()`)

- **Golden fixture mới** (Protocol 5 mục 3): `tests/fixtures/mineru/parse_only_txt_figoni25/`
  (`document.md`, `middle.json`, `summary.json`) — capture từ 1 lần chạy live thật
  `MinerURunner.parse_document(parse_method="txt")` qua MinerU 3.4.5 (task
  `cdbd0988-1182-456d-bf23-791e03490bc6`, Figoni *How Baking Works* 25 trang đầu). Dùng bởi
  `tests/integration/test_job_orchestrator.py::test_run_parse_only_pdf_digital_forces_none_using_golden_mineru_fixture`
  — chạy `middle.json` THẬT qua `MinerURunner._compute_quality()` THẬT (không hardcode số), xác
  nhận `confidence=0.9976` (998/1004 span `score=1.0`) rồi assert `run_parse_only()` vẫn ghi
  `ocr_confidence IS NULL` cho `pdf_digital` — đúng bằng chứng S15-6 cần.
- `tests/integration/test_job_orchestrator.py`: 10 test mới (pdf_digital completes + ép
  `ocr_confidence=None`, pdf_scan ghi confidence thật, golden fixture ở trên, data lineage
  processing→outputs→zip byte-identical, empty-markdown fails, zip-guard fails trên zip hỏng
  (mock `testzip()`), cancel giữa chừng qua `should_cancel`, MinerU unavailable raise trước khi
  đụng `job.status`, EPUB raise không gọi MinerU, timeout scale theo số trang).
- `tests/test_mineru_runner.py`: 2 test mới cho `task_timeout_seconds` override + `should_cancel`
  callback ở tầng `MinerURunner` (không qua `JobOrchestrator`).
- `tests/integration/test_upload_and_job_flow.py`: viết lại
  `test_upload_then_create_parse_only_job_and_check_status` (parse_only giờ async, không còn
  fail đồng bộ — theo đúng quy ước có sẵn của `test_estimate_and_cancel_api.py`, không mock/chờ
  background task) và `test_create_job_reports_duplicate_of_completed_job_with_same_hash` (viết
  lại theo S15-10 — assert CẢ 2 chiều: job `parse_only` completed KHÔNG bị coi trùng, job
  `translate` completed VẪN bị coi trùng như cũ); thêm test EPUB+parse_only 400 (S15-8) và test
  `create_batch` schedule đúng cho `parse_only` (S15-2 mở rộng).
- `tests/integration/test_estimate_and_cancel_api.py`: 2 test mới cho `retry_job()` (S15-11) —
  `parse_only` failed → retry OK dù `model` là provider bịa (chứng minh cost gate THẬT SỰ bị bỏ
  qua, không chỉ bỏ check 400), `translate` failed vẫn qua cost gate như cũ (negative test).
- `tests/integration/test_delete_and_download_naming.py`: test `DELETE` chặn status `"parsing"`
  (S15-12), test download ZIP đúng MIME/tên file cho `parse_only` (S15-3).

### Kết quả chạy thật

```
uv run ruff check src/ tests/ web/                    → All checks passed!
uv run ruff format --check <file đã sửa>              → đã format
uv run pytest -q                                       → 462 passed, 1 failed, ... (xem dưới)
```

1 test FAIL (`tests/test_rotated_text_overlay.py::
test_overlay_rotated_text_draws_translated_text_at_correct_angle`) — **KHÔNG liên quan tới US-15,
không phải do session này gây ra**. Đây là lỗi ĐÃ ĐƯỢC GHI NHẬN sẵn ở entry "Bug #8 — 'Chữ nhảy
lung tung' tái phát..." phía trên (task theo dõi riêng `task_062a9bd5`, do 1 session/worktree khác
đang sửa `src/postprocess/rotated_text_overlay.py`/`font_shrink.py`/`src/preprocess/
searchable_pdf.py` song song — 3 file này có thay đổi CHƯA COMMIT tại thời điểm Dev session này
chạy, không đụng tới bởi source nào của US-15). Toàn bộ 10 test mới của US-15 + mọi test hiện có
liên quan (`test_job_orchestrator.py` 49/49, `test_mineru_runner.py` 18/18,
`test_upload_and_job_flow.py` 12/12, `test_estimate_and_cancel_api.py` 10/10,
`test_delete_and_download_naming.py` 12/12) đều PASS.

### Quyết định phạm vi tự đưa ra (cần PM xác nhận)

**KHÔNG implement `parse_method` override** (§6.21.3 — checkbox UI "ưu tiên độ chính xác ký hiệu"
cho phép user ép `ocr` mode ngay cả với `pdf_digital`). Lý do: (a) mục "Việc cụ thể" trong brief
PM giao không liệt kê tính năng này tường minh (khác các mục khác đều rất chi tiết); (b) implement
đúng cần thêm cột `Job.parse_method` mới để retry dùng lại đúng lựa chọn user — 1 quyết định đổi
DB schema mà brief không xin phép rõ. `run_parse_only()` vẫn dùng đúng mapping mặc định đã chốt
(`pdf_digital→txt`, `pdf_scan→ocr`), không có cách nào user ép `ocr` cho file `pdf_digital` ở round
này. Known limitation L-4 (§6.15.5, `txt` mode mất glyph `=`/`×`) vẫn còn nguyên — nếu PM muốn có
override này ngay, cần round riêng.

### Trạng thái

Implement xong theo đúng §6.15 (nhánh PDF). `docs/CHANGELOG.md` chỉ append. **CHƯA spawn
Reviewer** (Protocol 7 R7-01) — KHÔNG được coi là "xong"/"sẵn sàng" cho tới khi Reviewer thật
review xong và ghi vào `docs/review-report.md`.

## US-15 §6.21.3 — `parse_method` override (auto/txt/ocr) cho `job_type=parse_only`

Bổ sung phần Dev trước đã cố ý bỏ qua ("Quyết định phạm vi tự đưa ra" ở entry ngay trên) — implement
đúng §6.21.3: cho phép user ép `parse_method="ocr"` cho 1 file `pdf_digital` khi tài liệu nhiều công
thức toán/hoá, để đọc đúng ký hiệu (L-4, `txt` mode làm mất `=`/`×` do font text-layer không map
Unicode). KHÔNG đụng `src/core/glossary_manager.py`.

### `src/api/routes/jobs.py`

- `JobCreateRequest` thêm field `parse_method: Literal["auto", "txt", "ocr"] = "auto"` — CHỈ có ý
  nghĩa khi `job_type=parse_only`.
- Helper mới `_resolve_parse_method(requested, file_type) -> str`: `"auto"` → mapping theo
  `file_type` như S15 gốc đã chốt (`pdf_digital`→`"txt"`, `pdf_scan`→`"ocr"`); `"txt"`/`"ocr"` pass
  through nguyên văn (override tường minh của user).
- `create_job()`: gọi `_resolve_parse_method()` **1 LẦN** ngay lúc tạo `Job` row (khi
  `job_type == "parse_only"`) rồi ghi thẳng vào `job.parse_method` — cùng pattern với
  `Job.chunk_size_used` (chốt 1 lần, ghi lại, KHÔNG suy đoán lại mỗi lần chạy). Nhờ vậy 1 lần
  `retry_job()` sau đó tự động dùng lại ĐÚNG lựa chọn cũ (BR-CHUNK-05-style resumable) mà không cần
  sửa gì thêm ở `retry_job()`. `job_type=translate` → `job.parse_method=None` (field không có ý
  nghĩa ở nhánh này, không validate/reject nếu client lỡ gửi).
- **Không đổi `create_batch()`/`BatchCreateRequest`** — §6.21.3 chỉ mô tả tường minh
  `POST /api/jobs`, không nhắc `/api/batches`. Quyết định phạm vi: batch `parse_only` vẫn dùng
  `"auto"` mặc định như cũ (không regress), chỉ chưa có override qua batch endpoint. Cần PM xác nhận
  nếu muốn mở rộng.

### `src/core/job_orchestrator.py`

- `run_parse_only()`: dòng hardcode cũ `parse_method = "txt" if job.file_type == FileType.PDF_DIGITAL
  else "ocr"` đổi thành fallback — `job.parse_method = job.parse_method or (...)`, rồi
  `parse_method = job.parse_method`. Trong luồng bình thường (đi qua `POST /api/jobs`) giá trị đã
  được `_resolve_parse_method()` ghi sẵn từ lúc tạo job nên nhánh `or` không kích hoạt; fallback chỉ
  chạy cho Job row cũ (tạo trước khi có cột này) hoặc Job tạo trực tiếp trong test. Ghi
  `job.parse_method` cùng 1 `commit()` với `job.status = "parsing"` — không thêm round-trip DB.
- **KHÔNG đổi rule S15-6** (`_run_parse_only_pipeline()`): `record_confidence=(job.file_type ==
  FileType.PDF_SCAN)` và `if job.file_type == FileType.PDF_DIGITAL: job.ocr_confidence = None` giữ
  nguyên 100% — vẫn rẽ theo `file_type`, KHÔNG rẽ theo `parse_method`. Đây chính là bug tiềm ẩn brief
  cảnh báo trước (`jobs.ocr_confidence` mang 2 ý nghĩa nếu đổi sang rẽ theo `parse_method`) — đã kiểm
  tra kỹ, không cần sửa gì ở 2 dòng này, chỉ cần đảm bảo không vô tình đụng vào.

### `src/models/job.py`

- Cột mới `parse_method: str | None` — lưu giá trị **đã resolve thật** (`"txt"`/`"ocr"`), KHÔNG bao
  giờ lưu `"auto"` (cùng pattern `chunk_size_used`).

### `src/models/database.py`

- Thêm `("jobs", "parse_method", "TEXT")` vào `_NEW_NULLABLE_COLUMNS` — dùng ĐÚNG migration mechanism
  idempotent (`_add_missing_columns()` + `ALTER TABLE ... ADD COLUMN`) đã có sẵn trong codebase cho
  `chunk_size_used`/`thread_used`/`rate_limit_hits`, không tạo file/script migration riêng.
- **Quyết định phạm vi (cần PM xác nhận — lệch với 1 câu trong brief)**: brief yêu cầu gộp cột này
  vào "1 migration script duy nhất" cùng với `Job.finished_at` (§6.17.2), `Job.total_units`
  (§6.20.6), `Chunk.unit_start`/`unit_end` (§6.20.7), bảng `suggested_terms` (§6.18.3). Đã kiểm tra
  kỹ: **KHÔNG có script migration nào đang tồn tại cho 4 thay đổi đó** — `src/models/job.py`,
  `src/models/chunk.py`, `src/models/database.py` hiện tại chưa có field/bảng nào trong 4 thứ này,
  và cũng chưa có `src/models/suggested_term.py`. 4 thay đổi đó thuộc các user story khác hẳn
  (US-19 unit tracking cho EPUB, US-20 suggested terms) — không nằm trong phạm vi việc được giao
  (chỉ §6.21.3). Tự ý implement cả 4 thứ đó sẽ là mở rộng phạm vi ngoài brief + rủi ro đụng session
  khác đang làm song song (repo hiện có nhiều file chưa commit từ 1 session khác, xem "Trạng thái"
  entry US-15 phía trên về Bug #8). Theo đúng quy tắc "Không tự ý thay đổi architecture — escalate
  lên Tech Lead nếu cần" của vai trò Dev: chỉ thêm ĐÚNG 1 dòng `("jobs", "parse_method", "TEXT")` vào
  `_NEW_NULLABLE_COLUMNS` hiện có (cơ chế migration idempotent duy nhất mà project đang dùng — không
  có "file migration script" riêng biệt nào khác để gộp vào). Migration cho 4 thay đổi kia (nếu vẫn
  cần) nên là 1 task riêng, có brief riêng.

### Frontend (`web/`)

- `web/index.html`: checkbox mới trong khối config file (hiện khi `f.job_type === 'parse_only'`),
  nhãn đúng theo brief: *"Tài liệu nhiều công thức toán/hoá — ưu tiên độ chính xác ký hiệu (chậm
  hơn)"*.
- `web/js/app.js`: `handleFiles()` khởi tạo `f.parse_force_ocr = false`; `createJob()` gửi
  `parse_method: "ocr"` khi `job_type === "parse_only"` VÀ checkbox được tick, ngược lại bỏ field
  (JSON.stringify tự drop `undefined` → backend dùng mặc định `"auto"`). Không đổi `translateAll()`
  (nhánh batch) — cùng lý do phạm vi ở trên (§6.21.3 không nhắc `/api/batches`); khi chỉ 1 file
  pending, `translateAll()` gọi thẳng `createJob()` nên override vẫn hoạt động cho use case phổ biến
  nhất (dịch/parse từng file).

### Test (Protocol 6 R6-02 — assert giá trị cụ thể, không chỉ `assert_called()`)

- `tests/integration/test_job_orchestrator.py`:
  - `_create_parse_only_job()` thêm param `parse_method: str | None = None` để mô phỏng Job row đã
    được `_resolve_parse_method()` ghi sẵn (hoặc chưa, cho nhánh fallback).
  - Test mới **`test_run_parse_only_pdf_digital_ocr_override_still_forces_confidence_none`** — chính
    xác test case chống bug đã cảnh báo ở mục 4 của brief: tạo job `pdf_digital` với
    `parse_method="ocr"` đã resolve sẵn, fake MinerU trả `confidence=0.81`; assert CẢ 2 chiều:
    (a) `calls[0]["parse_method"] == "ocr"` — override thật sự có hiệu lực, KHÔNG bị âm thầm ép lại
    thành `"txt"`; (b) `job.ocr_confidence is None` và `job.ocr_dropped_spans is None` — rule S15-6
    vẫn giữ nguyên theo `file_type`, không rò giá trị 0.81 của fake runner vào DB.
- `tests/integration/test_upload_and_job_flow.py`: test mới
  `test_create_job_resolves_parse_method_auto_default_and_explicit_ocr_override` — gọi thật
  `POST /api/jobs` qua `TestClient`, đọc lại `Job.parse_method` trực tiếp từ DB (cùng pattern
  `database_module.get_session_factory()` với `test_create_job_reports_duplicate_of_completed_job_with_same_hash`
  đã có) cho 3 case: (1) field bỏ trống → `"txt"` cho `pdf_digital` (hành vi mặc định không đổi);
  (2) `parse_method="ocr"` tường minh trên `pdf_digital` → lưu đúng `"ocr"`; (3) `job_type="translate"`
  kèm `parse_method="ocr"` → `job.parse_method` vẫn `None` (field vô nghĩa ở nhánh translate).

### Kết quả chạy thật

```
uv run ruff check src/ tests/ web/                                          → All checks passed!
uv run ruff format --check <file đã sửa trong session này>                  → đã format
uv run pytest -q                                                             → 464 passed, 1 failed
uv run pytest -q tests/integration/test_job_orchestrator.py \
  tests/integration/test_upload_and_job_flow.py -k "parse_method or parse_only" → 15 passed
```

1 test FAIL — **CÙNG 1 test đã biết từ trước, KHÔNG liên quan session này**:
`tests/test_rotated_text_overlay.py::test_overlay_rotated_text_draws_translated_text_at_correct_angle`
(Bug #8, đang được 1 session/worktree khác sửa `rotated_text_overlay.py`/`font_shrink.py`/
`searchable_pdf.py` song song — session này không đụng 3 file đó). 462 test cũ + 2 test mới của
session này (1 ở `test_job_orchestrator.py`, 1 ở `test_upload_and_job_flow.py`) = 464 passed, khớp
đúng số liệu.

### Trạng thái

Implement xong đúng §6.21.3 (không tự thêm/bớt so với spec, trừ 2 quyết định phạm vi đã ghi rõ ở
trên — cần PM xác nhận: (1) không gộp migration cho `finished_at`/`total_units`/`unit_start`-`end`/
`suggested_terms` vì các thay đổi đó chưa hề tồn tại trong code, thuộc task khác hẳn; (2) không mở
rộng override qua `/api/batches`). **CHƯA spawn Reviewer** (Protocol 7 R7-01) — KHÔNG được coi là
"xong"/"sẵn sàng" cho tới khi Reviewer thật review xong và ghi vào `docs/review-report.md`.

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
