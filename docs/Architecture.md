# Architecture — BB-Translation

> Pipeline dich tai lieu nganh banh (EN → VI), giu nguyen layout goc
> Version: 1.0 | Ngay: 2026-09-03 | Phase: Planning
> Author: Tech Lead

---

## 1. Tech Stack

| Layer | Technology | Version | Ly do chon |
|-------|-----------|---------|------------|
| **Language** | Python | 3.12+ | Ecosystem PDF/NLP tot nhat, pdf2zh va MinerU deu Python-native |
| **Package Manager** | uv | latest | Nhanh hon pip 10-100x, lockfile deterministic, thay the ca virtualenv |
| **Web Framework** | FastAPI | 0.115+ | Async native, WebSocket support (progress streaming), auto OpenAPI docs |
| **Task Queue** | asyncio + in-process queue | stdlib | Du an 1 user, khong can Celery/Redis. Dung `asyncio.Queue` + `asyncio.Semaphore` de gioi han concurrency |
| **Database** | SQLite | 3.45+ (via aiosqlite) | Zero-config, single-file, du cho 1-user app. WAL mode cho concurrent read/write |
| **ORM** | SQLModel | 0.0.22+ | Ket hop SQLAlchemy + Pydantic, type-safe, FastAPI integration tot |
| **PDF Translation** | pdf2zh (PDFMathTranslate) | 1.9+ | Dich PDF giu layout 100% qua text overlay |
| **LLM SDKs** | anthropic, openai, google-generativeai | latest | Client cho Claude, OpenAI/DeepSeek (OpenAI-compatible), Gemini. DeepL dung `deepl` SDK rieng |
| **PDF Manipulation** | PyMuPDF (fitz) | 1.24+ | Font-shrink post-processing, merge bilingual PDF, detect text overflow |
| **OCR** | MinerU (HTTP service `mineru-api`, `backend=pipeline`) | 2.x/master | Parse PDF scan → Markdown + images. Chay nhu 1 service HTTP rieng, app goi qua REST. **Contract day du + nguon xac thuc: xem 6.9.** |
| **EPUB Translation** | bilingual_book_maker | latest | Dich EPUB tao sach song ngu, ho tro Claude + custom prompt |
| **EPUB → PDF** | Calibre CLI (ebook-convert) | 7.0+ | Convert EPUB → PDF de xuat output thong nhat |
| **Excel I/O** | openpyxl | 3.1+ | Doc/ghi Excel glossary (.xlsx) |
| **Frontend** | HTML + Alpine.js + Tailwind CSS | Alpine 3.x, Tailwind 3.x | Lightweight, khong can build step, du cho dashboard 1-user |
| **WebSocket** | FastAPI WebSocket | built-in | Real-time progress updates |
| **Containerization** | Docker + Docker Compose | 27+ | Reproducible environment, de deploy |
| **Font** | Go Noto Universal / Noto Sans | latest | Vietnamese Unicode coverage day du |

### Tai sao KHONG chon:

| Option | Ly do bo |
|--------|----------|
| Celery + Redis | Over-engineering cho 1 user. asyncio queue du |
| PostgreSQL | SQLite du cho single-user, zero maintenance |
| React/Vue SPA | Complexity khong can thiet. Alpine.js + HTMX-style du cho dashboard don gian |
| Streamlit | Gioi han customization, khong control duoc WebSocket/API |
| Tika/Textract | pdf2zh da giai quyet PDF translation, MinerU cho OCR — khong can tool extract rieng |

---

## 2. System Architecture

### 2.1. Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DOCKER COMPOSE ENVIRONMENT                        │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     FastAPI Web Server (:8000)                     │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────┐  │   │
│  │  │ Upload API │  │Glossary API│  │ Job API  │  │ History API │  │   │
│  │  └─────┬──────┘  └─────┬──────┘  └────┬─────┘  └──────┬──────┘  │   │
│  │        │               │               │               │          │   │
│  │  ┌─────▼───────────────▼───────────────▼───────────────▼──────┐  │   │
│  │  │                    Core Services Layer                      │  │   │
│  │  │                                                            │  │   │
│  │  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  │  │   │
│  │  │  │ File Router  │  │ Job Orchestr. │  │ Glossary Mgr   │  │  │   │
│  │  │  │ (detect type)│  │ (batch/chunk) │  │ (CRUD/import)  │  │  │   │
│  │  │  └──────┬───────┘  └───────┬───────┘  └───────┬────────┘  │  │   │
│  │  │         │                  │                   │           │  │   │
│  │  │  ┌──────▼──────────────────▼───────────────────▼────────┐  │  │   │
│  │  │  │              Translation Pipeline                     │  │  │   │
│  │  │  │                                                       │  │  │   │
│  │  │  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │  │  │   │
│  │  │  │  │ PDF Engine  │  │  OCR Engine  │  │ EPUB Engine│  │  │  │   │
│  │  │  │  │ (pdf2zh)    │  │  (MinerU)    │  │ (bbm)      │  │  │  │   │
│  │  │  │  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │  │  │   │
│  │  │  │         │                │                 │         │  │  │   │
│  │  │  │  ┌──────▼────────────────▼─────────────────▼──────┐  │  │  │   │
│  │  │  │  │           LLM Translation Service              │  │  │  │   │
│  │  │  │  │  ┌────────┐ ┌──────┐ ┌─────┐ ┌──────┐        │  │  │  │   │
│  │  │  │  │  │ Claude │ │OpenAI│ │DeepL│ │Ollama│        │  │  │  │   │
│  │  │  │  │  └────────┘ └──────┘ └─────┘ └──────┘        │  │  │  │   │
│  │  │  │  └───────────────────────────────────────────────┘  │  │  │   │
│  │  │  │                                                      │  │  │   │
│  │  │  │  ┌──────────────────────────────────────────────┐   │  │  │   │
│  │  │  │  │         Post-Processing                       │   │  │  │   │
│  │  │  │  │  • Font shrink (PyMuPDF)                      │   │  │  │   │
│  │  │  │  │  • Bilingual merge (PyMuPDF)                  │   │  │  │   │
│  │  │  │  │  • Chunk merge                                │   │  │  │   │
│  │  │  │  │  • EPUB → PDF (Calibre)                       │   │  │  │   │
│  │  │  │  └──────────────────────────────────────────────┘   │  │  │   │
│  │  │  └──────────────────────────────────────────────────────┘  │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │ SQLite DB    │  │ File Storage     │  │ Translation Cache        │   │
│  │ (glossary,   │  │ /data/uploads/   │  │ (pdf2zh built-in +      │   │
│  │  jobs, hist) │  │ /data/outputs/   │  │  custom SQLite cache)   │   │
│  └──────────────┘  └──────────────────┘  └──────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2. Component Responsibilities

#### Web Server (FastAPI)
- Serve static frontend (HTML/CSS/JS)
- REST API cho upload, glossary CRUD, job management, history
- WebSocket endpoint cho real-time progress streaming
- File upload handling voi size validation (max 500MB)

#### File Router
- Detect file type tu extension + content analysis
- PDF: kiem tra text layer — extractable text > 90% pages = born-digital, con lai = scan
- Dieu huong file den dung pipeline (PDF/OCR/EPUB)

#### Job Orchestrator
- Quan ly lifecycle cua translation jobs (created → queued → processing → completed/failed)
- **Moi doan noi dung chi duoc dich DUNG MOT LAN** — lan goi LLM nam ben trong pdf2zh.
  Orchestrator khong duoc goi `provider.translate()` trong duong render (xem 6.6.2 R1)
- Batch processing: `asyncio.Semaphore(3)` gioi han 3 file dong thoi
- Shortest-job-first scheduling: sort theo file size truoc khi queue
- Chunking logic: chia file > 50 trang thanh chunk 30-50 trang
- Retry logic: exponential backoff cho transient errors
- Progress tracking: emit events qua WebSocket

#### Glossary Manager
- CRUD operations cho glossary entries
- Excel import/export (openpyxl)
- 2-tier scope: global + project glossary
- Build glossary prompt text de inject vao LLM call

#### Translation Pipeline
- Orchestrate 3 sub-engines theo file type
- Inject glossary + unit conversion rules vao translation prompt
- Manage translation context giua cac chunk

#### LLM Translation Service (out-of-band — xem 6.6.2 R3)
- Abstract interface `TranslationProvider`
- Concrete implementations cho Claude, OpenAI, Gemini, DeepSeek, DeepL, Ollama
- **KHONG** nam trong duong render: lan goi LLM cua job dich nam ben trong pdf2zh /
  bilingual_book_maker. Service nay chi dung cho cost estimation, test connection,
  sample preview, va pipeline tuong lai khong qua pdf2zh.
- Cost estimation (`estimate_cost()` — thuan tinh toan, khong goi API)

#### pdf2zh Service Mapper
- Anh xa ten provider noi bo → gia tri `-s` cua pdf2zh + dict bien moi truong (API key)
- Tu choi provider khong ap duoc glossary cho PDF pipeline (DeepL) — xem 6.6.3, 6.6.7

#### Post-Processing
- Font shrink: detect text overflow, giam font size / condensed
- Bilingual merge: interleave trang VI va EN
- Chunk merge: noi cac chunk output thanh 1 PDF
- EPUB → PDF conversion qua Calibre

---

## 3. Data Flow

### 3.1. PDF Born-Digital Flow

```
User upload PDF
       │
       ▼
[1] File Router
    - Verify .pdf extension
    - Extract text layer (PyMuPDF)
    - Count pages with extractable text
    - Result: > 90% pages have text → BORN-DIGITAL
       │
       ▼
[2] Job Orchestrator
    - Create job record (SQLite)
    - Calculate chunks: 300 pages → chunks [1-40, 39-80, 79-120, ...]
    - Overlap: 2 pages between chunks
    - Queue chunks for processing
       │
       ▼
[3] Per-chunk Translation (loop)
    │
    ├─[3a] Build Translation Prompt File  (1 LAN cho ca job, khong phai moi chunk)
    │      - Load glossary (global + project, merged)
    │      - LOC glossary: chi giu term thuc su xuat hien trong file (xem 6.6.5)
    │      - Add unit conversion rules (chi khi phat hien noi dung cong thuc)
    │      - Add style instruction: "Dich suc tich, VI ≤ 130% do dai EN"
    │      - GHI RA FILE: data/processing/{job_id}/prompt.txt
    │        (--prompt cua pdf2zh nhan DUONG DAN FILE, khong phai chuoi inline — xem 6.6 F5)
    │        File phai chua ${text}, ${lang_in}, ${lang_out}
    │
    ├─[3b] Call pdf2zh  ← DAY LA LAN GOI LLM DUY NHAT cho doan noi dung nay
    │      Command: pdf2zh input.pdf -li en -lo vi -s {service_arg} \
    │               --pages {start}-{end} \
    │               --prompt data/processing/{job_id}/prompt.txt \
    │               --output data/processing/{job_id}/chunk_{i}/
    │      - {service_arg} do Pdf2zhServiceMapper sinh ra (vd "gemini:gemini-2.5-pro",
    │        "deepseek:deepseek-chat", "openailiked:claude-sonnet-4-5-20250514") — xem 6.6.3
    │      - API key truyen qua ENV cua subprocess, KHONG qua argv
    │      - pdf2zh tu goi LLM API voi prompt da inject
    │      - pdf2zh render text VI overlay len layout goc
    │      - Output: {input_stem}-mono.pdf (VI) va {input_stem}-dual.pdf trong chunk dir rieng
    │      LUU Y: Job Orchestrator KHONG duoc goi provider.translate() o day.
    │             Goi ca hai = tra phi 2 lan + 2 ban dich khac nhau (xem 6.6.2 R1)
    │
    ├─[3c] Post-process chunk
    │      - Open output voi PyMuPDF
    │      - Scan moi text block: kiem tra co tran bounding box khong
    │      - Buoc 1: giam font size toi da 20%
    │      - Buoc 2: horizontal scaling 85%
    │      - Buoc 3: flag blocks van tran → ghi vao overflow_report
    │      - Save chunk output
    │
    └─[3d] Update progress
           - Update job record: chunk X/Y completed
           - Emit WebSocket event: {job_id, chunk, progress%, eta}
       │
       ▼
[4] Merge Chunks
    - PyMuPDF merge all chunk PDFs (bo overlap pages)
    - Output: final_vi.pdf
       │
       ▼
[5] Bilingual Output (nếu user chon)
    - PyMuPDF interleave:
      Page 1 (VI) → Page 1 (EN) → Page 2 (VI) → Page 2 (EN) → ...
    - Output: final_bilingual.pdf
       │
       ▼
[6] Finalize
    - Move output to /data/outputs/{job_id}/
    - Update job status → completed
    - Generate overflow report (neu co)
    - Calculate API cost = UOC LUONG tu do dai text (jobs.cost_source = "estimated")
      pdf2zh khong xuat token usage ra ngoai — xem 6.6.6
    - Emit WebSocket: job completed
```

### 3.2. PDF Scan Flow

```
User upload PDF (scan)
       │
       ▼
[1] File Router
    - Extract text layer (PyMuPDF) → < 90% pages have text → SCAN   (BR-INPUT-02)
    - KHONG tinh confidence o buoc nay — confidence chi co sau khi MinerU chay xong
       │
       ▼
[2] MinerU OCR  (HTTP, async task flow — KHONG phai CLI subprocess)
    POST {MINERU_ENDPOINT}/tasks   (multipart)
        files=<file>, backend=pipeline, parse_method=ocr, lang_list=en,
        return_md=true, return_images=true, return_middle_json=true
      → 202 {task_id, status_url, result_url}
    Poll GET /tasks/{task_id} cho den status=completed|failed
    GET /tasks/{task_id}/result → results[<file_name>].md_content / .images / .middle_json
    - Output: Markdown + images (base64 data URI) ghi ra output_dir
    - Tinh ocr_confidence tu span-level `score` trong middle_json  (chi tiet: 6.9.5)
       │
       ├── ocr_confidence ≥ nguong (mac dinh 0.80) hoac None → tiep tuc
       └── ocr_confidence < nguong → emit WebSocket `ocr_warning`, cho user chon
                                     tiep tuc hoac huy

    > Chi tiet contract, nguon xac thuc, va spec `MinerURunner`: **section 6.9**.
       │
       ▼
[3] Dung "cau noi" searchable PDF   (src/preprocess/searchable_pdf.py)
    - Tren BAN SAO file goc, voi moi text span trong middle.json:
        (a) to hinh chu nhat trang len bbox span  -> xoa nen chu tieng Anh
        (b) insert_text(..., render_mode=3)       -> text layer VO HINH tai dung toa do
    - Anh / bang / hinh minh hoa giu nguyen pixel goc
    - Ket qua: data/processing/{job_id}/ocr_bridge/searchable.pdf — PDF co text layer
      extractable, pdf2zh xu ly y het mot file born-digital
    - Guard BR-OCR-02: cau noi khong co ky tu nao -> FAIL job, khong chay tiep

    > MinerU KHONG tu xuat duoc searchable PDF va pdf2zh KHONG tu OCR duoc — ca hai da
    > verify tren source ban cai that. Quyet dinh, bang chung, va spec day du: **section 6.10**.
       │
       ▼
[4] Chuyen sang PDF Born-Digital Flow (tu buoc [2] tro di)
    - Chunking → pdf2zh translation → post-processing → merge
    - **Input la searchable.pdf o buoc [3], KHONG phai job.file_path** (Protocol 6 R6-01;
      day chinh la soi day bi dut gay ra Bug #5 — xem lineage table 6.10.8)
    - Ban song ngu van dung file scan GOC lam mat EN (6.10.5)
```

### 3.3. EPUB Flow

```
User upload EPUB
       │
       ▼
[1] File Router
    - Verify .epub extension
    - Check DRM → neu co DRM → reject
       │
       ▼
[2] bilingual_book_maker Translation
    Command: bbook_maker --book_name input.epub \
             --model claude --claude_key $KEY \
             --prompt "{glossary + conversion rules}" \
             --use_context \
             --translation_style "custom CSS"
    - Dich tung chapter, giu structure
    - Output: EPUB da dich (bilingual EN-VI)
       │
       ▼
[3] Output Generation
    │
    ├── User chon EPUB → tra ve EPUB da dich
    │
    └── User chon PDF → Calibre convert
        Command: ebook-convert output.epub output.pdf \
                 --pdf-page-margin-top 72 \
                 --pdf-page-margin-bottom 72 \
                 --embed-all-fonts
        Output: PDF da dich
       │
       ▼
[4] Bilingual Output (nếu user chon)
    - Tuong tu PDF flow: interleave pages
```

### 3.4. Glossary Management Flow

```
[Import Excel]
User upload .xlsx
       │
       ▼
Parse voi openpyxl
    - Doc cot 1 (EN), cot 2 (VI), cot 3 (notes)
    - Validate: skip empty rows, trim whitespace
    - Detect duplicates (case-insensitive EN)
       │
       ▼
Preview cho user
    - Hien thi bang: EN | VI | Notes | Status (new/update/duplicate)
    - User confirm → bulk upsert vao SQLite
       │
       ▼
Luu vao glossary table
    - scope: 'global' hoac 'project:{project_id}'
    - updated_at: timestamp (cho last-updated-wins rule)

[Web CRUD]
    - GET /api/glossary?scope=global&search=ganache → list/search
    - POST /api/glossary → create entry
    - PUT /api/glossary/{id} → update entry
    - DELETE /api/glossary/{id} → delete entry

[Export Excel]
    - Query all entries by scope
    - Generate .xlsx voi openpyxl
    - Stream download

[Inject vao Translation]
    - Query glossary (global + project, project overrides global)
    - Build prompt text:
      "Bat buoc dich cac thuat ngu sau theo bang nay. Neu target la (keep), giu nguyen tieng Anh:
       | EN | VI |
       | fondant | fondant |
       | ganache | ganache |
       | buttercream | kem phu bo |
       | proof | u bot |
       | crumb coat | lop kem lot |
       ..."
    - Truyen prompt nay vao --prompt flag cua pdf2zh / bilingual_book_maker
```

### 3.5. Batch Processing Flow

```
User upload N files + chon config (model, glossary, output mode)
       │
       ▼
[1] Validate all files
    - Check format, size
    - Reject invalid files, keep valid ones
       │
       ▼
[2] Create batch job
    - batch_id, status: 'processing'
    - Sort files by size (shortest job first)
    - Create child job cho moi file
       │
       ▼
[3] Semaphore-controlled execution
    semaphore = asyncio.Semaphore(3)  # max 3 concurrent

    for file in sorted_files:
        async with semaphore:
            try:
                await process_file(file)  # route to PDF/OCR/EPUB flow
                file.status = 'completed'
            except TransientError:
                await retry_with_backoff(file, max_retries=3)
            except PermanentError:
                file.status = 'failed'
                file.error = str(error)
                # continue — failure isolation
       │
       ▼
[4] Batch completion
    - batch.status = 'completed' (even if some files failed)
    - Summary: X/N files translated, Y failed
    - WebSocket: batch completed event
```

---

## 4. Data Model / DB Schema

SQLite database tai `/data/bb_translation.db`, WAL mode enabled.

### 4.1. Entity Relationship

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   batches    │────<│      jobs        │────<│     chunks       │
└──────────────┘     └──────────────────┘     └──────────────────┘
                            │
                            │
                     ┌──────▼──────────────┐
                     │  overflow_reports   │
                     └─────────────────────┘

┌──────────────────┐     ┌──────────────────────┐
│   glossaries     │────<│  glossary_entries    │
└──────────────────┘     └──────────────────────┘

┌──────────────────────┐
│  translation_cache   │
└──────────────────────┘

┌──────────────────────┐
│      settings        │
└──────────────────────┘
```

### 4.2. Table Definitions

> ℹ️ **DDL dưới đây là ảnh chụp schema tại thời điểm v1.0** — cố ý giữ nguyên làm mốc lịch sử.
> Các increment sau bổ sung cột/bảng và mô tả schema **ngay trong section của chính increment đó**;
> nguồn sự thật vận hành luôn là `src/models/*.py`. Danh mục bổ sung cho tới 2026-09-08:
> `jobs.job_type` (§6.8) · `jobs.cost_cap_usd` + status `cost_capped` (§6.11.4) · `jobs.cancel_requested`
> (Increment 6) · `jobs.ocr_bridge_path` / `ocr_dropped_spans` (§6.10.7) · `jobs.chunk_size_used`,
> `chunks.thread_used` / `rate_limit_hits`, bảng `concurrency_state` (§6.12.8) · bảng
> `layout_qa_findings` (Bug #6) · **và đợt 2026-09-08**: `jobs.finished_at` (§6.17.2),
> `jobs.total_units` (§6.20.6), `chunks.unit_start` / `unit_end` + `page_start`/`page_end` đổi thành
> nullable (§6.20.7), bảng mới `suggested_terms` (§6.18.3).

```sql
-- Batch: nhom nhieu file dich cung luc
CREATE TABLE batches (
    id              TEXT PRIMARY KEY,  -- UUID
    status          TEXT NOT NULL DEFAULT 'created',
                    -- created | processing | completed | failed
    total_files     INTEGER NOT NULL DEFAULT 0,
    completed_files INTEGER NOT NULL DEFAULT 0,
    failed_files    INTEGER NOT NULL DEFAULT 0,
    model           TEXT NOT NULL DEFAULT 'claude',
    output_mode     TEXT NOT NULL DEFAULT 'vi_only',
                    -- vi_only | bilingual
    glossary_scope  TEXT NOT NULL DEFAULT 'global',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Job: 1 file dang duoc xu ly
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,  -- UUID
    batch_id        TEXT REFERENCES batches(id),
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,     -- duong dan file upload
    file_size       INTEGER NOT NULL,  -- bytes
    file_hash       TEXT NOT NULL,     -- SHA-256 de detect duplicate
    file_type       TEXT NOT NULL,     -- pdf_digital | pdf_scan | epub
    total_pages     INTEGER,
    status          TEXT NOT NULL DEFAULT 'created',
                    -- created | queued | chunking | translating |
                    -- post_processing | merging | completed | failed
    progress        REAL NOT NULL DEFAULT 0.0,  -- 0.0 → 1.0
    error_message   TEXT,
    output_path     TEXT,              -- duong dan file output
    bilingual_path  TEXT,              -- duong dan file song ngu (neu co)
    model           TEXT NOT NULL,
    estimated_cost  REAL,              -- USD
    actual_cost     REAL,
    cost_source     TEXT NOT NULL DEFAULT 'estimated',  -- 'estimated' | 'metered' (xem 6.6.6)
    ocr_confidence  REAL,              -- 0.0 → 1.0 (chi cho pdf_scan)
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_jobs_batch ON jobs(batch_id);
CREATE INDEX idx_jobs_file_hash ON jobs(file_hash);

-- Chunk: 1 phan cua file dang xu ly
CREATE TABLE chunks (
    id              TEXT PRIMARY KEY,  -- UUID
    job_id          TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,  -- thu tu chunk (0-based)
    page_start      INTEGER NOT NULL,  -- trang bat dau (inclusive)
    page_end        INTEGER NOT NULL,  -- trang ket thuc (inclusive)
    overlap_start   INTEGER,           -- trang overlap voi chunk truoc
    overlap_end     INTEGER,           -- trang overlap voi chunk sau
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending | translating | post_processing | completed | failed
    retry_count     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    output_path     TEXT,              -- chunk output file path
    api_tokens_used INTEGER,
    api_cost        REAL,
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_chunks_job ON chunks(job_id);

-- Overflow Report: text blocks bi tran sau post-processing
CREATE TABLE overflow_reports (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    page_number     INTEGER NOT NULL,
    block_index     INTEGER NOT NULL,
    original_text   TEXT,
    translated_text TEXT,
    bbox            TEXT,              -- JSON: {x0, y0, x1, y1}
    font_size_original  REAL,
    font_size_final     REAL,
    scaling_applied     REAL,          -- horizontal scaling factor
    still_overflow      INTEGER NOT NULL DEFAULT 0,  -- 1 = van tran
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_overflow_job ON overflow_reports(job_id);

-- Glossary: nhom thuat ngu
CREATE TABLE glossaries (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    scope           TEXT NOT NULL DEFAULT 'global',
                    -- 'global' hoac 'project:{batch_id}'
    description     TEXT,
    entry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Glossary Entry: 1 cap thuat ngu EN → VI
CREATE TABLE glossary_entries (
    id              TEXT PRIMARY KEY,
    glossary_id     TEXT NOT NULL REFERENCES glossaries(id) ON DELETE CASCADE,
    term_en         TEXT NOT NULL,
    term_vi         TEXT,              -- NULL hoac "(keep)" = giu nguyen EN
    context_hint    TEXT,              -- goi y ngu canh (vd: "ky thuat tron bot")
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_glossary_entries_glossary ON glossary_entries(glossary_id);
CREATE INDEX idx_glossary_entries_term ON glossary_entries(term_en COLLATE NOCASE);

-- Translation Cache: tranh goi API trung
CREATE TABLE translation_cache (
    id              TEXT PRIMARY KEY,
    source_hash     TEXT NOT NULL UNIQUE, -- SHA-256 cua (source_text + model + glossary_hash)
    source_text     TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    model           TEXT NOT NULL,
    glossary_hash   TEXT,              -- hash cua glossary version duoc dung
    tokens_used     INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_cache_hash ON translation_cache(source_hash);

-- Settings: cau hinh he thong
CREATE TABLE settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Default settings:
-- max_concurrent_files: 3
-- default_model: claude
-- default_chunk_size: 40
-- font_shrink_max_percent: 20
-- font_condensed_min: 85
-- api_keys: {claude: "", openai: "", deepl: ""}  (encrypted)
```

### 4.3. File Storage Layout

```
/data/
├── bb_translation.db          # SQLite database
├── uploads/                   # File nguyen goc
│   └── {job_id}/
│       └── original.pdf       # hoac .epub
├── processing/                # File dang xu ly (tam)
│   └── {job_id}/
│       ├── chunks/
│       │   ├── chunk_000.pdf
│       │   ├── chunk_001.pdf
│       │   └── ...
│       ├── ocr_output/        # Chi cho pdf_scan
│       │   └── *.md
│       └── temp/
├── outputs/                   # Ket qua cuoi
│   └── {job_id}/
│       ├── translated_vi.pdf
│       ├── bilingual_vi_en.pdf  # Neu co
│       └── overflow_report.json
├── glossary/                  # Glossary exports
│   └── *.xlsx
└── fonts/                     # Custom fonts
    └── NotoSans-Regular.ttf
```

---

## 5. API Design

### 5.1. REST API Endpoints

Base URL: `http://localhost:8000/api`

#### Upload & Jobs

| Method | Endpoint | Mo ta | Request | Response |
|--------|----------|-------|---------|----------|
| POST | `/upload` | Upload file(s) | `multipart/form-data`: files[] | `{job_ids: [...], batch_id}` |
| POST | `/translate` | Bat dau dich | `{batch_id, model, glossary_scope, output_mode}` | `{batch_id, status}` |
| GET | `/jobs` | List all jobs | `?status=&limit=&offset=` | `{jobs: [...], total}` |
| GET | `/jobs/{id}` | Chi tiet job | - | `{job detail + chunks}` |
| POST | `/jobs/{id}/retry` | Retry failed job | - | `{job_id, status}` |
| DELETE | `/jobs/{id}` | Xoa job + files | - | `{ok: true}` |

#### Batches

| Method | Endpoint | Mo ta | Request | Response |
|--------|----------|-------|---------|----------|
| GET | `/batches` | List batches | `?limit=&offset=` | `{batches: [...], total}` |
| GET | `/batches/{id}` | Chi tiet batch | - | `{batch detail + jobs}` |

#### Glossary

| Method | Endpoint | Mo ta | Request | Response |
|--------|----------|-------|---------|----------|
| GET | `/glossaries` | List glossaries | `?scope=` | `{glossaries: [...]}` |
| POST | `/glossaries` | Tao glossary | `{name, scope, description}` | `{glossary}` |
| GET | `/glossaries/{id}/entries` | List entries | `?search=&limit=&offset=` | `{entries: [...], total}` |
| POST | `/glossaries/{id}/entries` | Them entry | `{term_en, term_vi, context_hint, notes}` | `{entry}` |
| PUT | `/glossaries/{id}/entries/{eid}` | Sua entry | `{term_vi, context_hint, notes}` | `{entry}` |
| DELETE | `/glossaries/{id}/entries/{eid}` | Xoa entry | - | `{ok: true}` |
| POST | `/glossaries/{id}/import` | Import Excel | `multipart/form-data`: file | `{preview: [...], import_id}` |
| POST | `/glossaries/{id}/import/{iid}/confirm` | Xac nhan import | - | `{imported: N, updated: M}` |
| GET | `/glossaries/{id}/export` | Export Excel | - | `.xlsx` file stream |

#### History

| Method | Endpoint | Mo ta | Request | Response |
|--------|----------|-------|---------|----------|
| GET | `/history` | Lich su dich | `?limit=&offset=` | `{jobs: [...], total}` |
| GET | `/history/check-duplicate` | Check file trung | `{file_hash}` | `{exists, job_id, translated_at}` |

#### Downloads

| Method | Endpoint | Mo ta | Response |
|--------|----------|-------|----------|
| GET | `/download/{job_id}/vi` | Download ban VI | PDF file stream |
| GET | `/download/{job_id}/bilingual` | Download ban song ngu | PDF file stream |
| GET | `/download/{job_id}/report` | Download overflow report | JSON |

#### Settings

| Method | Endpoint | Mo ta | Request | Response |
|--------|----------|-------|---------|----------|
| GET | `/settings` | Doc cau hinh | - | `{settings}` |
| PUT | `/settings` | Cap nhat cau hinh | `{key: value, ...}` | `{settings}` |
| POST | `/settings/test-api` | Test API key | `{provider, api_key}` | `{ok, model_name, error}` |

#### Cost Estimation

| Method | Endpoint | Mo ta | Request | Response |
|--------|----------|-------|---------|----------|
| POST | `/estimate` | Uoc tinh chi phi | `{job_ids, model}` | `{total_pages, est_tokens, est_cost_usd}` |

### 5.2. WebSocket API

Endpoint: `ws://localhost:8000/ws`

Client connect va nhan events:

```json
// Progress update
{
    "type": "progress",
    "job_id": "abc-123",
    "chunk": 5,
    "total_chunks": 10,
    "progress": 0.45,
    "eta_seconds": 120,
    "status": "translating"
}

// Job completed
{
    "type": "job_completed",
    "job_id": "abc-123",
    "output_path": "/api/download/abc-123/vi",
    "overflow_count": 3,
    "actual_cost": 0.85,
    "cost_source": "estimated"
}

// Job failed
{
    "type": "job_failed",
    "job_id": "abc-123",
    "error": "Claude API rate limit exceeded after 3 retries",
    "completed_chunks": 4,
    "total_chunks": 10
}

// Batch completed
{
    "type": "batch_completed",
    "batch_id": "batch-456",
    "completed": 4,
    "failed": 1,
    "total": 5
}

// OCR warning — chi emit khi confidence != null VA < ocr_confidence_threshold (6.9.5/6.9.7).
// `confidence` la diem tong hop BB-Translation tu tinh tu span score cua MinerU,
// KHONG phai field co san trong response MinerU.
{
    "type": "ocr_warning",
    "job_id": "abc-123",
    "confidence": 0.72,
    "dropped_span_count": 18,
    "message": "Chat luong OCR thap (72%). MinerU da bo qua 18 vung chu khong doc duoc. Ket qua dich co the khong chinh xac."
}
```

### 5.3. Internal Service Interfaces

> **PHAM VI (cap nhat Increment 4)**: `TranslationProvider` la lop **out-of-band**, KHONG nam
> trong duong render cua PDF/EPUB pipeline. Trong luong dich that, LLM duoc goi ben trong pdf2zh
> (PDF) / bilingual_book_maker (EPUB). `TranslationProvider` chi phuc vu: cost estimation truoc job,
> test connection o Settings, sample preview 1-2 trang, va cac pipeline tuong lai khong qua pdf2zh.
> Xem section 6.6.2 (R1, R3).

```python
# === Translation Provider Interface ===

class TranslationProvider(Protocol):
    """Interface chung cho moi LLM translation backend (out-of-band, xem 6.6.2 R3)."""

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        system_prompt: str,
        temperature: float = 0.3,
    ) -> TranslationResult: ...

    async def estimate_cost(
        self,
        text: str,
    ) -> CostEstimate: ...

    def name(self) -> str: ...


@dataclass
class TranslationResult:
    translated_text: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    model: str
    cached: bool


@dataclass
class CostEstimate:
    estimated_tokens: int
    estimated_cost_usd: float
    model: str


# === Implementations ===

class ClaudeProvider(TranslationProvider):
    """Claude API via anthropic SDK. Dung Batch API khi > 10 chunks."""
    # model: claude-sonnet-4-5-20250514
    # Prompt caching: system prompt cached across chunks

class OpenAIProvider(TranslationProvider):
    """OpenAI API via openai SDK."""

class DeepLProvider(TranslationProvider):
    """DeepL API. Khong inject glossary qua prompt — dung DeepL glossary API."""

class OllamaProvider(TranslationProvider):
    """Ollama local. Model: gemma2 hoac llama3.1."""
```

---

## 6. Key Technical Decisions

### 6.1. Chunking Strategy

**Quyet dinh**: Dung pdf2zh `--pages` parameter truc tiep, khong build custom chunking engine.

**Chi tiet**:
- pdf2zh nhan `--pages 1-40` de dich tung page range
- Job Orchestrator chia file thanh chunks, goi pdf2zh nhieu lan
- Merge output chunks bang PyMuPDF

**Chunking algorithm**:
```python
def calculate_chunks(total_pages: int, chunk_size: int = 40, overlap: int = 2) -> list[Chunk]:
    """
    Chia file thanh chunks voi overlap.
    Vd: 120 pages, chunk_size=40, overlap=2
    → Chunk 0: pages 1-40   (translate 1-40)
    → Chunk 1: pages 39-80  (translate 41-80, pages 39-40 la context)
    → Chunk 2: pages 79-120 (translate 81-120, pages 79-80 la context)
    """
    chunks = []
    start = 1
    idx = 0
    while start <= total_pages:
        end = min(start + chunk_size - 1, total_pages)
        overlap_start = max(1, start - overlap) if idx > 0 else start
        chunks.append(Chunk(
            index=idx,
            page_start=start,
            page_end=end,
            overlap_start=overlap_start if idx > 0 else None,
            overlap_end=min(end + overlap, total_pages) if end < total_pages else None,
        ))
        start = end + 1 - overlap  # next chunk starts overlap pages before end
        idx += 1
    return chunks
```

**Context overlap handling**:

> **CAP NHAT (Increment 4 review) — vai tro cua overlap da thay doi.** pdf2zh dich **tung segment
> doc lap**, khong mang context xuyen trang, va prompt file la CHUNG cho ca job (khong the chen
> dong "pages X-Y la context" rieng cho tung chunk). Vi vay overlap **khong** con y nghia
> "cung cap context"; no chi con la **bien an toan khi merge** (chong mat dong o ranh gioi chunk).
> Overlap gan nhu **khong ton them chi phi API** vi pdf2zh cache theo `original_text` (6.6 F8) —
> segment cua trang overlap da duoc dich o chunk truoc se cache-hit. Giu `overlap = 2` nhu cu:
> khong can doi code, khong vi pham BR-CHUNK-03, chi doi cach dien giai.

- Overlap pages duoc pdf2zh xu ly lai nhung hau het cache-hit → chi phi ~0
- Khi merge: chi lay pages tu actual_start → actual_end cua moi chunk (BR-CHUNK-04)
- Moi chunk phai co **output dir rieng** `data/processing/{job_id}/chunk_{i}/` vi pdf2zh dat ten
  output theo ten file input (`{stem}-mono.pdf`) → dung chung dir se ghi de (6.6 F9)

### 6.2. Glossary Injection

**Quyet dinh**: Inject glossary vao **file prompt** truyen qua `--prompt <path>`. KHONG sua code pdf2zh hay bilingual_book_maker.

> **CAP NHAT (Increment 4 review)**: `--prompt` cua pdf2zh nhan **duong dan file**, khong phai chuoi
> inline; file dung `string.Template` voi 3 bien `${lang_in}` / `${lang_out}` / `${text}`; va pdf2zh
> gui prompt nay **cho tung segment** (doan van), duoi dang **1 message role `user`** — khong co
> system message. Hai he qua bat buoc: (a) template duoi day phai ket thuc bang `Source Text: ${text}`;
> (b) glossary phai duoc **loc theo tai lieu** truoc khi chen, neu khong token dau vao se tang hang
> chuc lan. Chi tiet + rang buoc day du: **section 6.6.4 va 6.6.5**.

**Ly do**:
- Giu nguyen upstream tools, de update version
- Prompt injection flexible, hoat dong voi moi LLM provider
- Glossary size nho (thuong < 500 entries) → fit trong prompt

**Prompt template**:
```
Ban la chuyen gia dich thuat tai lieu nganh banh. Dich tu tieng Anh sang tieng Viet.

QUY TAC BAT BUOC:
1. Dich cac thuat ngu theo bang duoi day. Neu cot VI la "(keep)" hoac trong, GIU NGUYEN tieng Anh:

| EN | VI |
|---|---|
{glossary_entries}

2. Dich suc tich. Ban dich tieng Viet KHONG duoc dai hon 130% ban goc tieng Anh.

3. Chuyen doi don vi do luong trong cong thuc:
   - cups → ml (1 cup = 240ml)
   - tablespoon (tbsp) → ml (1 tbsp = 15ml)
   - teaspoon (tsp) → ml (1 tsp = 5ml)
   - ounces (oz) → grams (theo bang nguyen lieu)
   - °F → °C (cong thuc: (°F - 32) × 5/9, lam tron)
   - inches → cm (1 inch = 2.54cm)
   CHI chuyen doi trong cong thuc/recipe. Trong van xuat, giu nguyen don vi goc.

4. Giu nguyen format: bold, italic, bullet list, numbered list, heading level.

5. Giu nguyen moi placeholder dang {{v0}}, {{v1}}... o dung vi tri cua chung.

Chi in ra ban dich, khong them loi dan hay giai thich.

Source Text: ${text}
Translated Text:
```

**Escape**: `safe_substitute` xu ly `$` la ky tu dac biet — moi `$` khac trong glossary/noi dung
phai duoc escape thanh `$$` khi ghi file prompt.

**Bang chuyen doi nguyen lieu (inject khi can)**:
```
| Nguyen lieu | 1 cup (US) |
|------------|-----------|
| Bot mi (flour) | 120g |
| Duong (sugar) | 200g |
| Bo (butter) | 225g |
| Sua (milk) | 240ml |
| Kem tuoi (heavy cream) | 240ml |
| Cacao (cocoa powder) | 85g |
| Bot ngu coc (oats) | 90g |
| Mat ong (honey) | 340g |
| Dau an (oil) | 215ml |
```

### 6.3. Font Shrink Strategy

**Quyet dinh**: Post-processing step sau khi pdf2zh render xong, dung PyMuPDF.

**Ly do**: pdf2zh khong co auto-shrink. Can xu ly o layer PDF sau khi text da duoc overlay.

**Algorithm**:
```python
async def font_shrink_page(page: fitz.Page, overflow_entries: list) -> list[OverflowReport]:
    """
    Scan moi text block tren page. Neu text tran bbox:
    1. Giam font size toi da 20%
    2. Neu van tran: horizontal scaling 85%
    3. Neu van tran: log vao report
    """
    reports = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:  # skip image blocks
            continue
        bbox = fitz.Rect(block["bbox"])
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"]
                font_size = span["size"]
                # Tinh text width voi font hien tai
                text_width = fitz.get_text_length(text, fontname=span["font"], fontsize=font_size)
                bbox_width = bbox.width

                if text_width <= bbox_width:
                    continue  # fit, khong can shrink

                # Buoc 1: giam font toi da 20%
                min_size = font_size * 0.80
                new_size = max(min_size, font_size * (bbox_width / text_width))

                if fitz.get_text_length(text, fontname=span["font"], fontsize=new_size) <= bbox_width:
                    # Apply new font size
                    apply_font_size(page, span, new_size)
                    continue

                # Buoc 2: horizontal scaling 85%
                scaled_width = text_width * 0.85
                if scaled_width <= bbox_width:
                    apply_horizontal_scale(page, span, 0.85)
                    continue

                # Buoc 3: flag cho user
                reports.append(OverflowReport(
                    page_number=page.number,
                    original_text=text,
                    bbox=bbox,
                    font_size_original=font_size,
                    font_size_final=new_size,
                    scaling_applied=0.85,
                    still_overflow=True,
                ))
    return reports
```

**Luu y implementation**:
- PyMuPDF `page.get_text("dict")` tra ve chi tiet font/size/bbox cua moi text span
- Viec thay doi font size trong PDF can: xoa text cu, ghi text moi voi size moi tai cung vi tri
- Dung `page.insert_text()` hoac `page.insert_textbox()` de ghi lai
- Horizontal scaling dung PDF content stream operator `Tz` (phan tram scaling)

### 6.4. Song Ngu Output

**Quyet dinh**: Interleave trang VI va EN bang PyMuPDF.

**Algorithm**:
```python
async def create_bilingual_pdf(vi_pdf_path: str, en_pdf_path: str, output_path: str) -> None:
    """
    Tao PDF song ngu: trang le = VI, trang chan = EN.
    Vd: Page 1 (VI) → Page 1 (EN) → Page 2 (VI) → Page 2 (EN) → ...
    """
    vi_doc = fitz.open(vi_pdf_path)
    en_doc = fitz.open(en_pdf_path)
    output_doc = fitz.open()

    for i in range(len(vi_doc)):
        output_doc.insert_pdf(vi_doc, from_page=i, to_page=i)
        if i < len(en_doc):
            output_doc.insert_pdf(en_doc, from_page=i, to_page=i)

    output_doc.save(output_path)
```

### 6.5. Unit Conversion

**Quyet dinh**: Xu ly hoan toan trong translation prompt. Khong can engine rieng.

**Ly do**:
- LLM du thong minh de detect context cong thuc vs prose
- Bang conversion inject vao prompt → LLM ap dung dung
- Khong can regex/parser phuc tap cho cac format don vi khac nhau

**Implementation**: Bang conversion duoc inject vao system prompt (xem section 6.2). LLM tu detect doan nao la recipe/formula va chi convert trong context do.

### 6.6. Multi-Model Support — Ranh gioi giua TranslationProvider va pdf2zh

> **REVISED (Increment 4 review, 2026-09-04)** — muc nay thay the hoan toan ban cu.
> Ly do: Increment 4 phat hien mau thuan kien truc — `JobOrchestrator.run_job()` goi CA
> `provider.translate()` (Increment 3) LAN `pdf2zh_runner.translate_pages()` cho moi chunk,
> trong khi pdf2zh TU goi LLM API ben trong. Hau qua: tra phi API 2 lan cho cung 1 noi dung,
> va ban dich dung de tinh cost (`provider.translate()`) KHAC ban dich thuc su duoc render len
> PDF (2 lan goi LLM doc lap → khong deterministic).

#### 6.6.1. Su that ky thuat da verify (source pdf2zh v1.9.x)

Cac ket luan duoi day doc truc tiep tu source `Byaidu/PDFMathTranslate@main`
(`pdf2zh/translator.py`, `pdf2zh/cache.py`, `pdf2zh/pdf2zh.py`), khong phai suy doan:

| # | Su that | He qua |
|---|---------|--------|
| F1 | pdf2zh **KHONG co** translator Anthropic/Claude. Grep `anthropic\|claude` tren `translator.py` → 0 ket qua. | Khong the dung `-s claude`. Lenh trong ban Architecture cu (`-s claude`) la **sai**. |
| F2 | pdf2zh **CO** `-s gemini` va `-s deepseek` native. `GeminiTranslator(OpenAITranslator)` base_url `https://generativelanguage.googleapis.com/v1beta/openai/`, env `GEMINI_API_KEY`/`GEMINI_MODEL`. `DeepseekTranslator(OpenAITranslator)` base_url `https://api.deepseek.com/v1`, env `DEEPSEEK_API_KEY`/`DEEPSEEK_MODEL`. | Gemini/DeepSeek **khong** la constraint. Gia dinh ban dau ("pdf2zh khong ho tro 2 provider nay") la sai. |
| F3 | pdf2zh co `-s openailiked` — OpenAI-compatible generic, env `OPENAILIKED_BASE_URL` / `OPENAILIKED_API_KEY` / `OPENAILIKED_MODEL` / `OPENAILIKED_STREAM` / `OPENAILIKED_MAX_TOKENS`. | Day la duong vao cho Claude (xem F4). |
| F4 | Anthropic cung cap OpenAI SDK compatibility layer tai `https://api.anthropic.com/v1/`, endpoint `chat/completions`, ho tro `stream`, `stream_options`, `temperature` (0–1), va tra ve day du `usage.prompt_tokens` / `usage.completion_tokens`. **Khong** ho tro prompt caching. Anthropic ghi ro day la lop test/compat, "not considered a long-term or production-ready solution". | Claude chay duoc qua `-s openailiked`, nhung day la **duong phu thuoc rui ro** — phai ghi vao risk register. |
| F5 | `--prompt` nhan **duong dan FILE**, khong phai chuoi inline. `pdf2zh.py` mo file bang `open(parsed_args.prompt)` roi boc `string.Template`; loi mo file → `ValueError("prompt error.")`. File dung 3 bien: `${lang_in}`, `${lang_out}`, `${text}`. | `Pdf2zhRunner.translate_pages(custom_prompt=<str>)` hien tai **se crash khi chay that**. Phai ghi prompt ra file va truyen path. |
| F6 | `BaseTranslator.prompt()` tra ve **1 message duy nhat role `user`** — khong co system message. Prompt duoc gui **cho tung segment** (doan van sau layout analysis), khong phai ca trang/ca chunk. | Glossary bi lap lai trong MOI request. 500 entry (~5k token) × ~400 segment/chunk 40 trang = ~2M input token cho 1 chunk. Day la rui ro chi phi lon nhat cua kien truc nay — bat buoc phai loc glossary (xem 6.6.5). |
| F7 | `translator.CustomPrompt` = `True` cho openai / azure-openai / gemini / deepseek / ollama / grok / groq / silicon / zhipu / modelscope / anythingllm / xinference / openailiked. **`DeepLTranslator.CustomPrompt` = False** va `DeepLTranslator.do_translate()` goi `translate_text()` khong co tham so `glossary`. | Voi PDF pipeline, DeepL **khong the** nhan glossary hay quy tac chuyen doi don vi duoi bat ky hinh thuc nao. |
| F8 | pdf2zh co translation cache rieng: peewee SQLite tai `~/.cache/pdf2zh/cache.v1.db`, bang `_TranslationCache`, UNIQUE(`translate_engine`, `translate_engine_params`, `original_text`). `translate_engine_params` = JSON da sort cua `{lang_in, lang_out, model, temperature, stop, max_tokens, prompt, think_filter_regex}`. `BaseTranslator.translate()` tra cache truoc khi goi API. `--ignore-cache` de bypass. | Cache la **mitigation truc tiep cho R-01**. Vi `prompt` nam trong cache key → doi glossary tu dong invalidate cache, khong can xoa thu cong. Vi `original_text` la key → overlap pages giua 2 chunk hau nhu luon cache-hit → overlap gan nhu mien phi. |
| F9 | pdf2zh ghi output ra `--output <dir>` voi ten `{input_stem}-mono.pdf` va `{input_stem}-dual.pdf`. | Goi pdf2zh nhieu lan tren CUNG file input (chunking) se **ghi de len nhau** neu dung chung output dir. Bat buoc moi chunk 1 thu muc rieng. |

#### 6.6.2. Quyet dinh: **Option A — Single Translation Pass**

**Mot doan noi dung chi duoc goi LLM DUNG MOT LAN, va lan goi do nam BEN TRONG pdf2zh
(PDF) hoac bilingual_book_maker (EPUB).**

Cu the:

- **R1** — `JobOrchestrator` **KHONG** goi `provider.translate()` trong luong dich thuc te.
  Tham so `translation_provider` bi go khoi duong render.
- **R2** — Toan bo quy tac dich (glossary, chuyen doi don vi, rang buoc ≤130%, giu typography)
  di vao **file prompt** truyen qua `--prompt`. Day la giao dien duy nhat de dieu khien chat luong dich.
- **R3** — `TranslationProvider` (Increment 3) **duoc giu lai** nhung doi vai tro: no la
  **out-of-band translation service**, khong nam trong render path. 4 muc dich duoc phep:
  1. `estimate_cost()` — uoc luong chi phi truoc khi chay job (R-01, `cost_estimator.py`).
  2. **Test connection** — nut "Kiem tra ket noi" o man hinh Settings: dich 1 cau ngan de
     verify API key/endpoint truoc khi user chay job that.
  3. **Sample preview** — dich thu 1–2 trang text da extract de user danh gia chat luong /
     glossary truoc khi cam ket ca cuon sach (mitigation truc tiep cho R-01).
  4. Cac pipeline tuong lai khong di qua pdf2zh (vd dich Markdown output cua MinerU).
  Nghia la **khong provider nao bi bo di** — Increment 3 khong phai code thua.
- **R4** — Option B (dich truoc, render sau) **bi tu choi**. Ly do da verify:
  pdf2zh khong co mode "chi render tu ban dich co san". Duong duy nhat la pre-seed
  `~/.cache/pdf2zh/cache.v1.db` — nhung `original_text` la segment SAU layout analysis cua
  pdf2zh (kem placeholder cong thuc `{{v0}}`), khong the biet truoc neu khong chay pdf2zh 1
  luot; va phai tai tao chuoi JSON `translate_engine_params` chinh xac tung byte tren mot
  schema noi bo, khong co cam ket tuong thich nguoc ("cache.v1", tac gia ghi ro khong ho tro
  migration). Chi phi: 2 luot pdf2zh + coupling vao internals. Loi ich: bang 0 so voi Option A
  sau khi F2 chung minh Gemini/DeepSeek chay native. **Khong dang.**
- **R5** — Tu viet overlay text bang PyMuPDF (bo hoan toan pdf2zh) **bi tu choi cho v1**.
  Do la viet lai layout engine (line-breaking, reflow, font fallback, formula placeholder,
  bilingual dual-layer) — nhieu tuan cong, va la chinh xac phan viec ma pdf2zh da lam tot.

#### 6.6.3. Bang anh xa provider → pdf2zh service

`Pdf2zhServiceMapper` chuyen ten provider noi bo thanh `(-s value, env dict)`. API key **truyen
qua env cua subprocess**, khong bao gio qua argv (argv doc duoc bang `ps`).

| Provider (noi bo) | `-s` | Env truyen vao subprocess | Custom prompt | Trang thai v1.0 |
|---|---|---|---|---|
| `openai` | `openai:{model}` | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_STREAM=false`, `OPENAI_MAX_TOKENS` | Co | Ho tro day du |
| `gemini` | `gemini:{model}` | `GEMINI_API_KEY`, `GEMINI_MODEL` | Co | Ho tro day du |
| `deepseek` | `deepseek:{model}` | `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | Co | Ho tro day du |
| `ollama` | `ollama:{model}` | `OLLAMA_HOST`, `OLLAMA_MODEL` | Co | Ho tro day du, cost = 0 |
| `claude` | `openailiked:{model}` | `OPENAILIKED_BASE_URL=https://api.anthropic.com/v1/`, `OPENAILIKED_API_KEY=<ANTHROPIC_API_KEY>`, `OPENAILIKED_MODEL`, `OPENAILIKED_STREAM=false`, `OPENAILIKED_MAX_TOKENS=8192` | Co | Ho tro qua compat layer (F4) — **khong co prompt caching**, xem 6.6.7 |
| `deepl` | `deepl` | `DEEPL_AUTH_KEY` | **KHONG** (F7) | **Khong ho tro cho PDF pipeline v1** — xem 6.6.7 |

Ghi chu implementation:
- `-s service:model` la cu phap hop le cua pdf2zh; van set them env `*_MODEL` de phong khi
  parser doi hanh vi.
- `OPENAI_STREAM=false` / `OPENAILIKED_STREAM=false`: tat streaming cho de doc loi va de
  metering (6.6.6). Gemini/DeepSeek khong doc bien nay (chung ke thua `OpenAITranslator`
  nhung `self.envs` la dict rieng) → van stream; chap nhan duoc o v1.0.
- `temperature` pdf2zh hardcode = 0 (`self.options`) — khong cau hinh duoc qua CLI. Chap nhan:
  dich tai lieu can determinism, 0 la lua chon dung. Field `temperature` trong config
  `settings` chi con ap dung cho `TranslationProvider` (sample preview / test connection).

#### 6.6.4. Prompt file contract

`PromptBuilder` sinh **1 file prompt cho moi job**, luu tai
`data/processing/{job_id}/prompt.txt`, truyen qua `--prompt <path>`.

Bat buoc:
1. File **phai** chua token `${text}` — thieu no thi noi dung goc khong bao gio den LLM.
2. Dung `${lang_in}` / `${lang_out}` thay vi hard-code "English"/"Vietnamese".
3. `string.Template.safe_substitute` → moi ky tu `$` khac trong glossary phai escape thanh `$$`.
4. Output phai la **chi ban dich**, khong loi dan — pdf2zh dan thang ket qua vao layout.
5. Phai giu nguyen placeholder cong thuc dang `{{v0}}`, `{{v1}}` — pdf2zh dung chung de
   khoi phuc cong thuc/rich-text sau khi dich.

Khung file (ket hop voi bang glossary + bang don vi o section 6.2):

```
Ban la chuyen gia dich thuat tai lieu nganh banh. Dich tu ${lang_in} sang ${lang_out}.
Chi in ra ban dich, khong them bat ky loi dan hay giai thich nao.
Giu nguyen moi placeholder dang {{v0}}, {{v1}}... o dung vi tri cua chung.

{glossary_block}      # da loc theo tai lieu — xem 6.6.5
{unit_conversion_block}  # chi chen khi phat hien noi dung cong thuc
{style_rules_block}   # suc tich <=130%, giu bold/italic/list/heading

Source Text: ${text}
Translated Text:
```

#### 6.6.5. BAT BUOC: loc glossary theo tai lieu (he qua cua F6)

pdf2zh gui prompt **cho tung segment**. Nhet nguyen glossary vao prompt se nhan token dau vao
len hang chuc lan. Vi vay:

- `GlossaryManager.build_prompt_snippet()` nhan them tham so
  `only_terms_present_in: str | None` — text tieng Anh da extract cua **ca file** (PyMuPDF).
  Chi giu entry co term EN thuc su xuat hien (so khop case-insensitive, ranh gioi tu).
- Ap tran cung: toi da `settings.max_glossary_entries_in_prompt` (default **80**) entry, uu tien
  entry co tan suat xuat hien cao nhat. Vuot tran → ghi canh bao vao job log va hien thi cho user.
- `unit_conversion_block` chi chen khi text co dau hieu cong thuc (`cup`, `tbsp`, `tsp`, `oz`,
  `°F`, `inch`) — sach ly thuyet thuan tuy khong can no.
- Prompt file duoc build **1 lan/job** va tai su dung cho moi chunk → dam bao ban dich nhat quan
  giua cac chunk, va giu cache key on dinh (F8).

#### 6.6.6. Cost accounting khi pdf2zh tu goi API

pdf2zh khong xuat token usage ra stdout/stderr. Chien luoc 2 giai doan:

**v1.0 — Uoc luong tu do dai text (BAT BUOC implement ngay)**

Sau khi chunk render xong, tinh:

```python
def estimate_chunk_cost(
    source_text: str,          # text EN extract tu page range bang PyMuPDF
    segment_count: int,        # so text block trong page range
    prompt_overhead_chars: int,# len(prompt file) - len("${text}")
    provider: TranslationProvider,
    vi_expansion: float = 1.3, # BR-FONT-03
    vi_token_factor: float = 1.5,  # token/ky tu cua tieng Viet co dau > tieng Anh
) -> tuple[int, int, float]:
    """Tra (input_tokens, output_tokens, cost_usd) — deu la UOC LUONG, khong phai so do dem."""
    chars_per_token_en = 4.0
    input_tokens = int(
        len(source_text) / chars_per_token_en
        + segment_count * prompt_overhead_chars / chars_per_token_en  # F6: prompt lap moi segment
    )
    output_tokens = int(len(source_text) * vi_expansion * vi_token_factor / chars_per_token_en)
    return input_tokens, output_tokens, provider.estimate_cost(input_tokens, output_tokens)
```

- `TranslationProvider` duoc dung o day **chi qua `estimate_cost()`** — thuan tinh toan, khong
  goi API. Dung R3.
- Ket qua ghi vao `chunks.api_tokens_used` / `chunks.api_cost`; `jobs.actual_cost` = tong.
- **Thay doi DB schema (section 4.2)**: them `jobs.cost_source TEXT NOT NULL DEFAULT 'estimated'`
  voi gia tri `'estimated' | 'metered'`. UI **phai** hien thi "~$X.XX (uoc tinh)" khi
  `cost_source = 'estimated'`, khong duoc trinh bay nhu so tien thuc.
- Sai so du kien ±30–50%. Chap nhan duoc voi muc tieu "canh bao chi phi", khong dung de doi soat.
- Cache hit (F8) khong ton API nhung uoc luong khong biet dieu do → cost bi **uoc cao hon thuc**
  khi chay lai/co overlap. Ghi ro trong tooltip UI.

**v1.1 — LLM Metering Proxy (thiet ke san, HOAN lai, khong implement o vong nay)**

- Component moi `src/services/metering_proxy.py`: HTTP server tren `127.0.0.1:<ephemeral>`,
  proxy `POST /v1/chat/completions` len upstream that, doc `usage` tu response
  (them `stream_options.include_usage=true` khi `stream=true`), cong don token.
- **1 instance per chunk**, khoi dong truoc khi spawn pdf2zh va tat sau → moi luu luong trong
  vong doi do chac chan thuoc ve chunk day, khong can pdf2zh gui header dinh danh.
- Ket noi bang cach tro `OPENAILIKED_BASE_URL` vao proxy. **Rang buoc**: `GeminiTranslator` va
  `DeepseekTranslator` **hard-code base_url trong `__init__`**, khong doc env → de metering duoc
  chung, phai chuyen sang `-s openailiked` voi `OPENAILIKED_BASE_URL` tro vao proxy va proxy
  forward len endpoint that. Viec doi `-s` lam doi `translate_engine` trong cache key (F8) →
  cache cu mat hieu luc 1 lan khi nang cap; chap nhan duoc, ghi vao CHANGELOG khi lam.
- Khi bat, `jobs.cost_source = 'metered'` va so lieu la token that.
- Ollama khong di qua `openai` client (dung client rieng) → khong metering duoc, nhung cost = 0.

#### 6.6.7. Known limitations (phai dua vao PRD)

1. **DeepL khong dung duoc cho PDF pipeline v1.0.** `DeepLTranslator.CustomPrompt = False` va
   pdf2zh khong truyen glossary cho DeepL (F7) → khong the ap glossary lan chuyen doi don vi.
   Dieu nay **vi pham truc tiep** acceptance criteria cua US-14 ("Glossary injection hoat dong
   dung voi moi model"). Quyet dinh: **UI an/disable DeepL khi job la PDF**, kem tooltip giai
   thich. Code `DeepLProvider` (Increment 3) van giu lai cho: cost estimate, test connection, va
   duong nang cap tuong lai (tu tao DeepL Glossary resource + goi DeepL API truc tiep ngoai
   pdf2zh). **Can PM cap nhat US-14: liet ke DeepL la "khong ho tro PDF o v1.0".**
2. **Claude di qua compat layer.** Anthropic ghi ro OpenAI-compat khong phai giai phap
   production dai han (F4), va **mat prompt caching** — dung nghia dong toi uu "prompt caching
   giam 90% cost" o ban Architecture cu **khong con dung** cho duong pdf2zh. Voi F6 (glossary
   lap moi segment), Claude se la provider **dat nhat** trong 6 provider. Khuyen nghi mac dinh
   cho PDF khoi luong lon: **DeepSeek** (re nhat, co context caching server-side tu dong) hoac
   **Gemini Flash**; Claude danh cho tai lieu ngan / can chat luong thuat ngu cao nhat.
3. **Cost o v1.0 la uoc luong, khong phai so do dem** (6.6.6).
4. `chunks.api_tokens_used` / `api_cost` la uoc luong per-chunk, khong the doi soat voi hoa don
   nha cung cap. Doi soat that chi kha thi tu v1.1.

#### 6.6.8. Thay doi interface (spec cho Dev)

```python
# src/services/pdf2zh_service_map.py  (MOI)

@dataclass(frozen=True)
class Pdf2zhService:
    service_arg: str              # gia tri cho -s, vd "gemini:gemini-2.5-pro"
    envs: dict[str, str]          # bien moi truong cho subprocess (chua API key)
    supports_custom_prompt: bool  # False → DeepL


class UnsupportedForPdfPipelineError(RuntimeError):
    """Provider khong dung duoc cho PDF pipeline (vd DeepL, xem 6.6.7)."""


class Pdf2zhServiceMapper:
    def map(self, provider_name: str, settings: Settings) -> Pdf2zhService:
        """Raise UnsupportedForPdfPipelineError neu provider khong ap duoc glossary."""


# src/services/pdf2zh_runner.py  (SUA)

@dataclass
class Pdf2zhResult:
    success: bool
    mono_path: Path          # {input_stem}-mono.pdf  — ban VI thuan
    dual_path: Path | None   # {input_stem}-dual.pdf  — pdf2zh tu sinh
    stderr: str
    duration_seconds: float

class Pdf2zhRunner:
    async def translate_pages(
        self,
        input_path: Path,
        output_dir: Path,          # DOI: dir rieng cho tung chunk (F9), khong phai file path
        page_range: str,
        service: Pdf2zhService,    # DOI: thay cho `service: str`
        prompt_file: Path | None = None,  # DOI: thay cho `custom_prompt: str` (F5)
        lang_in: str = "en",
        lang_out: str = "vi",
        ignore_cache: bool = False,       # MOI: map sang --ignore-cache (F8)
        timeout_seconds: int = 3600,      # MOI: pdf2zh co the treo
    ) -> Pdf2zhResult: ...
```

- Subprocess spawn voi `env={**os.environ, **service.envs}`; **khong** dua API key vao argv.
- `output_dir` = `data/processing/{job_id}/chunk_{index}/` — bat buoc rieng biet (F9).
- `prompt_file` bi bo qua khi `service.supports_custom_prompt is False`.

```python
# src/core/job_orchestrator.py  (SUA)

class JobOrchestrator:
    def __init__(
        self,
        pdf2zh_runner: Pdf2zhRunner,
        service_mapper: Pdf2zhServiceMapper,
        prompt_builder: PromptBuilder,
        glossary_manager: GlossaryManager,
        cost_estimator: CostEstimator,
        provider_factory: ProviderFactory,   # CHI dung cho estimate_cost(), khong translate()
        mineru_runner: MinerURunner | None = None,
        settings: Settings | None = None,
    ) -> None: ...

    async def run_job(self, job_id: str, db_session: AsyncSession) -> JobResult: ...
```

**GO BO**: tham so `translation_provider: TranslationProvider` va moi loi goi
`provider.translate()` trong `run_job()`.

Trinh tu `run_job()` sau khi sua:

```
1. Load Job; reject EPUB (chua implement)
2. Dem total_pages (PyMuPDF); pdf_scan → MinerU (6.9) lay
   `result.quality.confidence` → jobs.ocr_confidence (co the NULL)
3. Extract text EN toan file (PyMuPDF) → dung de LOC glossary (6.6.5)
4. service = service_mapper.map(job.provider, settings)
      → UnsupportedForPdfPipelineError ⇒ Job.status=failed, error_message ro rang
5. prompt_file = prompt_builder.write_prompt_file(
       glossary_manager, project_id=job.batch_id,
       only_terms_present_in=<text buoc 3>,
       path=data/processing/{job_id}/prompt.txt)
6. plan_chunks() → load/create Chunk rows (BR-CHUNK-05 resumable, giu nguyen)
7. Voi moi chunk chua completed:
     a. pdf2zh_runner.translate_pages(..., service=service, prompt_file=prompt_file,
                                      output_dir=.../chunk_{i}/)   [with_retry]
        → DUY NHAT mot lan goi LLM, nam ben trong pdf2zh
     b. font_shrink_page() tren tung trang mono output → OverflowReport
     c. estimate_chunk_cost() → chunk.api_tokens_used / chunk.api_cost   (6.6.6)
     d. chunk.status = completed; ProgressTracker.update()
8. merge_chunk_pdfs() → final_vi.pdf
9. output_mode == "bilingual" → create_bilingual_pdf()
10. Job.actual_cost = Σ chunk.api_cost; Job.cost_source = "estimated"; status = completed
```

**Config model** (`settings` table) — giu nguyen 6 provider nhu ban cu, bo sung:

```json
{
    "pdf_pipeline": {
        "max_glossary_entries_in_prompt": 80,
        "pdf2zh_ignore_cache": false,
        "pdf2zh_timeout_seconds": 3600,
        "vi_expansion_factor": 1.3,
        "vi_token_factor": 1.5,
        "metering_proxy_enabled": false
    },
    "providers": {
        "claude": {
            "api_key": "sk-ant-...",
            "model": "claude-sonnet-4-5-20250514",
            "max_tokens": 8192,
            "temperature": 0.3,
            "openai_compat_base_url": "https://api.anthropic.com/v1/",
            "use_batch_api": false,
            "use_prompt_caching": false
        },
        "openai":   { "api_key": "sk-...", "model": "gpt-4o", "max_tokens": 8192, "temperature": 0.3 },
        "gemini":   { "api_key": "AIza...", "model": "gemini-2.5-pro", "max_tokens": 8192, "temperature": 0.3 },
        "deepseek": { "api_key": "sk-...", "base_url": "https://api.deepseek.com", "model": "deepseek-chat", "max_tokens": 8192, "temperature": 0.3 },
        "deepl":    { "api_key": "...", "formality": "default", "pdf_pipeline_supported": false },
        "ollama":   { "endpoint": "http://localhost:11434", "model": "gemma2:27b", "max_tokens": 8192, "temperature": 0.3 }
    }
}
```

`use_batch_api` / `use_prompt_caching` cua Claude **doi mac dinh sang `false`**: ca hai deu khong
kha dung tren duong pdf2zh (F4). Chung chi con y nghia neu sau nay co pipeline dich truc tiep qua
`ClaudeProvider` (vd EPUB hoac Markdown).

**Dac thu tung provider (cap nhat)**:
- **Claude**: qua `-s openailiked` + Anthropic OpenAI-compat. Khong prompt caching, khong Batch API.
  Dat nhat trong 6 provider tren duong pdf2zh vi F6.
- **OpenAI**: `-s openai` native.
- **Gemini**: `-s gemini` native (qua OpenAI-compat endpoint cua Google). Context lon; co implicit
  context caching giup giam chi phi phan prompt lap lai.
- **DeepSeek**: `-s deepseek` native. Re nhat (~$0.27/$1.1 per MTok) + context caching tu dong →
  **khuyen nghi mac dinh cho file lon**. Van can benchmark chat luong thuat ngu nganh banh.
- **DeepL**: khong dung cho PDF v1.0 (6.6.7 muc 1).
- **Ollama**: `-s ollama` native, cost = 0, cham. Can RAM >= 16GB cho model 27B.

Provider registry (`ProviderFactory`) giu nguyen cho lop out-of-band; `Pdf2zhServiceMapper` la
registry song song cho lop render. Them provider moi = them entry o ca hai cho.

---

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

### 6.8. Markdown Parse-only Mode (PRD US-15)

> ⚠️ **Đã rà soát lại 2026-09-08 khi US-15 được kích hoạt lại — §6.8 vẫn ĐÚNG ở phần lõi nhưng
> KHÔNG còn đủ.** Phần nào còn dùng được, phần nào phải sửa (và tại sao) nằm ở **§6.15**. Đọc
> §6.15 TRƯỚC khi implement; §6.8 giữ nguyên làm bản thiết kế nền.

**Quyet dinh**: Them 1 job type moi `parse_only`, tai su dung Parsing Engine (MinerU) nhung SKIP hoan toan Translation Engine, Glossary Injection, va Unit Conversion.

**Ly do**:
- MinerU von da xuat Markdown chuan (giu heading level, table, image link) — day la output tu nhien cua no truoc khi dua vao Translation Engine
- Khong can them component moi, chi can Job Orchestrator dung lai o buoc sau parse thay vi di tiep sang translate

**Flow**:
```
Input (PDF born-digital / PDF scan / EPUB)
        │
        ▼
┌───────────────────┐
│  Parsing Engine    │   PDF born-digital/scan → MinerU (OCR neu can)
│  (MinerU / EPUB    │   EPUB → pandoc/ebooklib parse HTML chapters → Markdown
│   parser)           │
└─────────┬──────────┘
          │
          ▼  (KHONG di qua Translation Engine)
┌───────────────────┐
│  Output Packager    │  → file .md + thu muc images/
└───────────────────┘
```

**Job type trong DB** (`jobs` table them cot `job_type`):
```sql
ALTER TABLE jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT 'translate';
-- job_type IN ('translate', 'parse_only')
```

**API**:
```
POST /api/jobs
{
  "file_id": "...",
  "job_type": "parse_only",   -- thay vi "translate"
  "output_format": "markdown"
}
```

**Xu ly theo input**:
- **PDF born-digital**: MinerU form field `backend=pipeline` + `parse_method=txt` → Markdown + images/
  (khong chay OCR ⇒ `ocr_confidence` se la `None`, dung theo 6.9.5)
- **PDF scan**: MinerU `backend=pipeline` + `parse_method=ocr` → Markdown + images/ (giu nguyen buoc
  OCR, chi bo buoc dich)

> Ca hai deu goi qua HTTP async task flow cua 6.9.3, **khong** goi CLI `mineru` bang subprocess.
- **EPUB**: parse HTML chapters bang `ebooklib` + `BeautifulSoup`, giu heading/list/table qua `markdownify`, khong goi bilingual_book_maker (vi tool do luon di kem dich)

**Output structure**:
```
output/{job_id}/
├── document.md
└── images/
    ├── page_003_img_01.png
    └── page_015_img_02.png
```

**Khong ap dung**: BR-UNIT (unit conversion), BR-GLOSS (glossary), BR-FONT (font shrink — khong lien quan vi khong render PDF). Xem BR-PARSE-01 den BR-PARSE-05 trong PRD.

---

### 6.9. MinerU OCR Integration — contract da verify (spec cho Dev)

> **Trang thai R5-01**: toan bo section nay **VERIFIED** truc tiep tren source code MinerU
> branch `master` (fetch 2026-09-04). Moi cau khong co trich dan nguon la suy luan thiet ke
> CUA CHUNG TA tren nen su that da verify, khong phai giả dinh ve MinerU.
>
> **Ban Architecture truoc day SAI** (dan toi `src/services/mineru_runner.py` Increment 2 khong
> bao gio chay duoc voi MinerU that): endpoint `/ocr`, port 8010 noi trong container, field file
> `file`, response top-level `markdown` + `confidence_score` + `images[].data_hex`. **Khong cai
> nao trong so do ton tai.** Xem CLAUDE.md Protocol 5 muc 2.

#### 6.9.1. Nguon xac thuc

| # | Nguon | Dung de xac nhan dieu gi |
|---|-------|--------------------------|
| S1 | `mineru/cli/fast_api.py` (master) — https://raw.githubusercontent.com/opendatalab/MinerU/master/mineru/cli/fast_api.py | Danh sach endpoint, shape response, `build_result_dict()`, default host/port `127.0.0.1:8000` |
| S2 | `mineru/cli/api_request.py` (master) | Toan bo form field cua `parse_request_form` + default |
| S3 | `mineru/backend/pipeline/model_json_to_middle_json.py` (master), ham `_apply_post_ocr()` | Noi DUY NHAT gan `span['score']`, va gia tri do den tu OCR **recognition** score |
| S4 | `mineru/utils/ocr_utils.py` (master), class `OcrConfidence` | `min_confidence = 0.5`, `min_width = 3` |
| S5 | `mineru/backend/pipeline/pipeline_analyze.py` (master), ham `_get_ocr_enable()` | Ngu nghia `parse_method` = `auto` / `txt` / `ocr` |
| S6 | Docs — https://opendatalab.github.io/MinerU/reference/output_files/ | `score` co o `model.json` (layout detect) va span-level `middle.json`; **khong co** o `content_list.json` |
| S7 | `docker/compose.yaml` (master) + https://opendatalab.github.io/MinerU/quick_start/docker_deployment/ | Image build tu repo thanh tag `mineru:latest`, service api port 8000, healthcheck `/health`, **Docker chi ho tro Linux/WSL2 + NVIDIA — khong ho tro macOS/MPS** |
| S8 | https://opendatalab.github.io/MinerU/usage/cli_tools/ | Lenh `mineru-api --host TEXT --port INTEGER` (default `127.0.0.1:8000`) |
| S9 | Docker Hub API — `GET /v2/repositories/opendatalab/mineru` → `{"message":"object not found"}` | Image `opendatalab/mineru:latest` **KHONG ton tai** trên Docker Hub |

#### 6.9.2. HTTP contract that (S1, S2)

**Endpoints**

| Method | Path | Vai tro |
|--------|------|---------|
| `GET`  | `/health` | Health check. 200 `{status:"healthy", version, queued_tasks, processing_tasks, ...}` / 503 `{status:"unhealthy", error}` |
| `POST` | `/file_parse` | Parse **dong bo** — giu ket noi HTTP den khi xong |
| `POST` | `/tasks` | Submit **bat dong bo** → 202 `{task_id, status:"pending", status_url, result_url, queued_ahead, ...}` |
| `GET`  | `/tasks/{task_id}` | Trang thai: `pending` \| `processing` \| `completed` \| `failed`. 404 neu khong ton tai |
| `GET`  | `/tasks/{task_id}/result` | 200 = ket qua (cung shape `/file_parse`); 202 = chua xong; 409 = task failed |

**Form field cua `/file_parse` va `/tasks`** (giong het nhau — cung `parse_request_form`, S2):

| Field | Type | Default | BB-Translation dung |
|-------|------|---------|---------------------|
| `files` | `list[UploadFile]` | *(bat buoc)* | **so nhieu** — gui dung 1 file/lan |
| `lang_list` | `list[str]` | `["ch"]` | `["en"]` — default `ch` la **sai cho tai lieu EN**, phai override |
| `backend` | `str` | `DEFAULT_BACKEND` | `"pipeline"` — **bat buoc**, xem 6.9.5 |
| `parse_method` | `str` (`auto`/`txt`/`ocr`) | `"auto"` | `"ocr"` cho `pdf_scan`, `"txt"` cho `parse_only` born-digital |
| `formula_enable` | `bool` | `True` | giu `True` |
| `table_enable` | `bool` | `True` | giu `True` |
| `image_analysis` | `bool` | `True` | giu `True` |
| `effort` | `str` | `DEFAULT_HYBRID_EFFORT` | khong gui (chi cho backend hybrid) |
| `server_url` | `str \| None` | `None` | khong gui |
| `return_md` | `bool` | `True` | `True` |
| `return_middle_json` | `bool` | `False` | **`True`** — nguon duy nhat de tinh confidence |
| `return_model_output` | `bool` | `False` | `False` |
| `return_content_list` | `bool` | `False` | `False` |
| `return_images` | `bool` | `False` | **`True`** |
| `response_format_zip` | `bool` | `False` | `False` (can JSON) |
| `return_original_file` | `bool` | `False` | `False` |
| `client_side_output_generation` | `bool` | `False` | `False` |
| `start_page_id` | `int` | `0` | dung khi chunk theo trang |
| `end_page_id` | `int` | `99999` | dung khi chunk theo trang |

**Response body** (`/file_parse` va `/tasks/{id}/result`, S1 `build_result_dict()`):

```jsonc
{
  "task_id": "...", "status": "completed", "backend": "pipeline", "version": "...",
  "created_at": "...", "started_at": "...", "completed_at": "...", "error": null,
  "status_url": "...", "result_url": "...",
  "results": {
    "<pdf_name>": {                       // key = TEN FILE, khong phai key co dinh
      "md_content":    "…markdown…",      // null neu return_md=false
      "middle_json":   "…JSON string…",   // null neu return_middle_json=false
      "model_output":  null,
      "content_list":  null,
      "images": { "abc123.jpg": "data:image/jpeg;base64,/9j/4AAQ…" }   // base64 DATA URI
    }
  }
}
```

**Khac biet chet nguoi so voi code cu**: `images` la **dict** `{filename: data-URI base64}` (S1:
`f"data:{get_image_mime_type(path)};base64,{encode_image(path)}"`), **khong** phai list object co
`data_hex`. `bytes.fromhex()` trong code cu se luon nem `ValueError`.

**KHONG co field confidence / quality / score nao o cap response.** Da doc `build_result_dict()`
va toan bo response model trong S1 — xac nhan tuyet doi.

#### 6.9.3. Quyet dinh: **async task flow** (`/tasks` + polling), khong dung `/file_parse`

**Chon**: `POST /tasks` → poll `GET /tasks/{task_id}` → `GET /tasks/{task_id}/result`.

**Ly do**:
1. **Thoi luong**. PRD nham sach 200–500 trang; 9.1 uoc luong ~3–5 phut OCR cho 100 trang → mot
   file that co the 15–25 phut. `/file_parse` giu 1 ket noi HTTP mo suot thoi gian do; bat ky
   idle-timeout nao (httpx, reverse proxy, Docker userland-proxy) cung giet job **sau khi** MinerU
   da tieu ton toan bo compute — mat trang, khong resume duoc.
2. **Quan sat duoc**. `/tasks/{id}` tra `status` + `queued_ahead` (S1) → ProgressTracker phat
   duoc WebSocket "dang cho hang doi / dang OCR" thay vi treo im lang. Voi `/file_parse` ta khong
   biet gi cho toi byte cuoi.
3. **Resumable**. Luu `task_id` lai (`jobs.mineru_task_id`) → app restart giua chung van
   `GET /tasks/{id}/result` lay lai duoc. MinerU giu task 24h (S1 task retention).
4. **Khop kien truc san co**. Job cua ta von da chay background (`_run_job_background`), khong co
   ai dang cho dong bo → khong duoc loi gi tu sync flow.

**Danh doi da can nhac**: async them 1 vong poll + xu ly 3 status code (202/409/404) so voi sync.
Chap nhan — day la chi phi mot lan trong `MinerURunner`, doi lay 4 diem tren.

**KHONG lam dual-path** (sync cho file nho, async cho file lon): 2 duong code = 2 contract phai
test, va chinh su "mock tu nhat quan voi gia dinh" la nguyen nhan Protocol 5 ra doi. Mot duong duy nhat.

**Tham so polling** (thiet ke cua ta, khong phai cua MinerU):
- Interval: 2s cho 30s dau, sau do backoff x1.5 den toi da 15s.
- Tong thoi gian cho: `mineru_task_timeout_seconds`, mac dinh **3600** (khong phai 300 nhu cu —
  300s khong du cho 1 file scan that).
- `GET /tasks/{id}` tra 404 → coi la task bi mat (MinerU restart) → `MinerUError`, khong retry vo han.

#### 6.9.4. Quyet dinh: `backend=pipeline` la bat buoc

`backend` co nhieu gia tri (`pipeline`, `vlm-*`, `hybrid-*`). Ta ghim `pipeline` vi:
- Duong post-OCR gan `span['score']` nam trong `mineru/backend/pipeline/` (S3) → **chi backend
  `pipeline` moi cho ta tin hieu confidence** (6.9.5).
- `vlm-*` doi hoi GPU/VRAM hoac MLX; `pipeline` chay duoc CPU/MPS tren may dich (M1 Pro).
- Shape `middle_json` cua VLM backend khac (S6 mo ta rieng cho pipeline backend) → doi backend
  la doi contract, phai re-verify theo R5-01.

⚠️ Neu tuong lai doi sang `vlm-mlx-engine` (nhanh hon tren Apple Silicon), **phai re-verify lai
6.9.5** truoc khi doi — khong duoc mac dinh la span score van con.

#### 6.9.5. Gap "OCR confidence score" — quyet dinh **Option A (co dieu chinh)**

**Su that da xac minh** (KHONG phai "MinerU hoan toan khong co confidence" — da tra ky theo yeu cau):

| Vi tri | Co `score`? | Ngu nghia | Dung duoc? |
|--------|-------------|-----------|------------|
| Response top-level | Khong | — | — |
| `content_list` | Khong (S6) | — | — |
| `model_output` (model.json) | **Co** (S6) — `{cls_id, label, score, bbox, index}` | Confidence cua **layout detection** (day co phai "header"/"table" khong) | **Khong** — do sai dai luong: model nhan dung o day la nhan dang KHOI, khong phai doc dung CHU |
| `middle_json` span-level | **Co** (S3, S6) | Confidence **OCR text recognition** | **CO — day la nguon ta dung** |

Trich `_apply_post_ocr()` (S3) — noi duy nhat trong pipeline gan `score` cho span:

```python
for index, span in enumerate(need_ocr_list):
    ocr_text, ocr_score = ocr_res_list[index]
    if ocr_score > OcrConfidence.min_confidence:      # OcrConfidence.min_confidence = 0.5  (S4)
        span['content'] = ocr_text
        span['score'] = float(f"{ocr_score:.3f}")
        _clear_post_ocr_fallback(span)
    elif _restore_post_ocr_fallback(span):
        continue                                      # span GIU NGUYEN, khong co 'score' moi
    else:
        span['content'] = ''
        span['score'] = 0.0                           # span bi VUT — tin hieu xau manh nhat
```

Ba he qua rang buoc thiet ke cua ta:
1. **Chi span thuc su di qua OCR** (span co `np_img`) moi duoc gan `score`. Span lay tu text layer
   khong co `score` → loai chung ra khoi phep tinh la **dung**, vi ta dang do chat luong OCR.
2. **Span duoi 0.5 bi vut** (`content=''`, `score=0.0`). Chung PHAI duoc dem vao mau — day chinh
   la text bi mat. Neu weight theo so ky tu thi span vut co 0 ky tu → bi bo qua, che dau dung
   thu ta can do. **=> weight theo SO SPAN, khong theo so ky tu.**
3. Vi MinerU da loc bo <0.5, cac span song sot deu nam trong `(0.5, 1.0]`. Trung binh se **lech
   cao** neu khong co span 0.0. Day la ly do nguong 0.80 cua AC-11.2 **khong con duoc hieu theo
   nghia cu** — xem 6.9.7.

**Cong thuc chot** (`_compute_quality`, thuc thi trong BB-Translation, khong phai cua MinerU):

```
middle = json.loads(results[name]["middle_json"])          # la JSON STRING, phai loads
spans  = moi span trong middle["pdf_info"][*]["preproc_blocks"] (de quy qua lines/spans)
ocr_spans = [s for s in spans if "score" in s]

ocr_span_count     = len(ocr_spans)
dropped_span_count = so span co score == 0.0
confidence         = sum(s["score"] for s in ocr_spans) / ocr_span_count   neu count > 0
                     None                                                  neu count == 0
```

`confidence is None` nghia la **khong co span nao co key `score`**. Day la trang thai hop le,
**khong phai loi** — `jobs.ocr_confidence` de NULL, khong canh bao. Code cu `raise MinerUError`
khi thieu confidence la sai ca ky thuat lan nghiep vu.

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

**Vi sao khong chon Option C (heuristic ngoai MinerU, vd do dai text / dien tich trang)**: khong
co calibration, phu thuoc font size / mat do chu / ngon ngu; trong khi ta da co san tin hieu that
tu chinh recognizer. Heuristic ngoai chi la lua chon khi khong con gi khac — o day con.

#### 6.9.6. Trien khai — `MinerURunner` (spec cho Dev, `src/services/mineru_runner.py`)

```python
# src/services/mineru_runner.py  (VIET LAI HOAN TOAN)

class MinerUError(RuntimeError): ...
class MinerUTimeoutError(MinerUError): ...
class MinerUUnavailableError(MinerUError): ...     # /health 503 hoac connect refused

@dataclass(frozen=True)
class OcrQuality:
    confidence: float | None        # None = khong co span nao qua OCR (hop le)
    ocr_span_count: int
    dropped_span_count: int         # span bi MinerU vut (score == 0.0)
    source: str                     # "middle_json_span_scores" | "unavailable"

@dataclass(frozen=True)
class MinerUResult:
    markdown_path: Path             # {output_dir}/document.md
    images_dir: Path                # {output_dir}/images/
    quality: OcrQuality
    task_id: str
    middle_json_path: Path | None   # {output_dir}/middle.json — giu lai de debug/audit

class MinerURunner:
    def __init__(
        self,
        base_url: str,
        *,
        task_timeout_seconds: float = 3600.0,   # tong thoi gian cho task
        request_timeout_seconds: float = 120.0, # timeout tung request HTTP le
        poll_initial_seconds: float = 2.0,
        poll_max_seconds: float = 15.0,
        backend: str = "pipeline",
    ) -> None: ...

    async def health(self) -> dict[str, Any]:
        """GET /health. Raise MinerUUnavailableError neu 503 hoac khong ket noi duoc.
        Dung cho: startup check, va smoke test that theo Protocol 5 R5-03."""

    async def parse_document(
        self,
        file_path: Path,
        output_dir: Path,
        *,
        parse_method: str = "ocr",           # "ocr" cho pdf_scan, "txt" cho born-digital parse_only
        lang: str = "en",
        start_page_id: int | None = None,    # inclusive, 0-based
        end_page_id: int | None = None,      # inclusive
    ) -> MinerUResult: ...
```

**Trinh tu `parse_document()`**

```
1. output_dir.mkdir(parents=True, exist_ok=True)
2. POST {base_url}/tasks   (multipart/form-data)
     files            = [(file_path.name, <binary>, "application/pdf")]   # KEY LA "files"
     backend          = self._backend                                     # "pipeline"
     parse_method     = parse_method
     lang_list        = "en"          # gui lap lai field neu httpx can list
     formula_enable   = "true"
     table_enable     = "true"
     return_md            = "true"
     return_images        = "true"
     return_middle_json   = "true"
     return_content_list  = "false"
     return_model_output  = "false"
     response_format_zip  = "false"
     start_page_id / end_page_id  chi gui khi khac None
   → ky vong 202. Doc task_id. Status != 202 → MinerUError kem body.

3. Poll GET {base_url}/tasks/{task_id}, interval 2s → x1.5 → cap 15s,
   tong <= task_timeout_seconds:
     status pending|processing  → tiep tuc (emit progress: queued_ahead neu co)
     status completed           → sang buoc 4
     status failed              → MinerUError(payload["error"])
     HTTP 404                   → MinerUError("task lost")
   Het gio → MinerUTimeoutError

4. GET {base_url}/tasks/{task_id}/result
     200 → payload;  202 → coi nhu chua xong, quay lai buoc 3 (race hiem);  409 → MinerUError

5. entry = _select_result_entry(payload["results"], file_path.name)
     - Uu tien khop dung file_path.name
     - Neu khong khop VA dict co dung 1 phan tu → lay phan tu do (MinerU co the doi duoi file)
     - Nguoc lai → MinerUError liet ke cac key co that
     KHONG duoc hardcode key.

6. md = entry.get("md_content")
     None/rong → MinerUError  (day la field DUY NHAT that su bat buoc)
   Ghi {output_dir}/document.md (utf-8)

7. images: dict[str, str]. Voi moi (name, data_uri):
     - Chi nhan tien to "data:<mime>;base64,"  → tach sau dau phay dau tien, base64.b64decode
     - Ten file: dung Path(name).name  (chan path traversal — cung lop bug da fix o upload.py)
     - Ghi {output_dir}/images/{name}
     - Entry di dang (khong co tien to data:, decode loi) → log warning, BO QUA, khong lam hong job

8. middle_json: neu co → json.loads (LA STRING, khong phai dict; van phai
   phong ho truong hop server tra san dict) → ghi {output_dir}/middle.json
   → quality = _compute_quality(middle)
   Neu khong co / parse loi → OcrQuality(None, 0, 0, source="unavailable") + log warning.
   TUYET DOI KHONG raise vi thieu confidence.

9. return MinerUResult(...)
```

**`_compute_quality(middle: dict) -> OcrQuality`** — duyet de quy `middle["pdf_info"]`, voi moi
page gom ca `preproc_blocks` va `discarded_blocks` (S3 xu ly ca hai), di xuong `blocks` → `lines`
→ `spans`; gom moi span co key `"score"`. Ap cong thuc 6.9.5. Duyet phai chiu duoc shape thieu key
(dung `.get(..., [])` xuyen suot) — `middle_json` la debug output, khong co schema cam ket.

**Thay doi lan toa sang code khac (Dev phai sua kem)**:
- `job_orchestrator.py`: cho nao dang doc `result.confidence_score` → doi sang
  `result.quality.confidence`, va phai xu ly `None` (khong canh bao, `jobs.ocr_confidence = NULL`).
- Nguong canh bao lay tu setting moi `ocr_confidence_threshold: float = 0.80` (khong hardcode) —
  de recalibrate duoc sau khi co so lieu that ma khong phai sua code.
- `config.py`: `mineru_timeout_seconds` → tach thanh `mineru_task_timeout_seconds` (3600) va
  `mineru_request_timeout_seconds` (120).
- Test: **cam** mock bang dict tu che theo tri nho. Fixture phai la 1 file JSON copy dung shape
  6.9.2 (`results` -> `<name>` -> `md_content`/`images` data-URI/`middle_json` string). Them
  1 test khang dinh runner **khong** raise khi `middle_json` vang mat.
- Protocol 5 R5-03: truoc release phai co it nhat 1 lan `GET /health` + 1 lan parse that 1 file
  PDF scan 1–2 trang toi MinerU that. Mock-only khong du.

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

#### 6.9.8. Trien khai runtime — Docker khong dung duoc tren macOS

⚠️ **Hai sai sot ha tang trong ban Architecture cu**:
- `image: opendatalab/mineru:latest` — image nay **khong ton tai** tren Docker Hub (S9).
  Cach chinh thuc la `docker build -t mineru:latest -f docker/global/Dockerfile .` (S7).
- `environment: DEVICE=mps` trong container — vo nghia. Doc chinh thuc: Docker cua MinerU
  **chi ho tro Linux va Windows/WSL2 voi NVIDIA GPU**; Docker tren macOS khong truy cap duoc
  MPS/MLX (S7). Bien `DEVICE` cung khong phai bien MinerU doc.

**Quyet dinh**: MinerU chay theo 2 che do, app **luon** noi chuyen qua HTTP nen contract khong doi:

| Moi truong | Cach chay MinerU | `MINERU_ENDPOINT` |
|-----------|------------------|-------------------|
| **macOS M1/M2 (moi truong dich chinh v1.0)** | Cai native ngoai Docker (`uv pip install mineru[core]`), chay `mineru-api --host 127.0.0.1 --port 8010` (S8). MinerU tu dong dung MPS tren macOS. Giong het cach pdf2zh dang duoc cai. | `http://localhost:8010` |
| **Linux + NVIDIA (v2.0 / cloud)** | Sidecar Docker, build image `mineru:latest` tu repo MinerU, publish `8010:8000` | `http://mineru:8000` |

**Ve port**: MinerU mac dinh `8000` (S1, S8) — **trung voi FastAPI cua BB-Translation**. Nen:
- Trong container MinerU van la 8000 (giu default), map ra host `8010:8000`.
- Chay native tren macOS thi bat buoc `--port 8010` vi 8000 da bi app chiem.

=> `MINERU_ENDPOINT` mac dinh trong `config.py` / `.env.example` la `http://localhost:8010`
(**khong doi**), nhung compose cu sai o cho map `8010:8010` va tro app toi `http://mineru:8010`
— MinerU khong bao gio listen 8010 ben trong container. Da sua o 7.1.

---
### 6.10. Cau noi OCR → dich cho nhanh `pdf_scan` (fix Bug #5, spec cho Dev)

> **Trang thai R5-01**: toan bo section nay **VERIFIED**. Nguon la source code cua chinh 2 tool
> **da cai tren may dich** (khong phai GitHub master, khong phai tri nho) cong voi **4 thi nghiem
> chay that** Tech Lead tu thuc hien trong luc thiet ke (6.10.3). Moi cau khong co trich dan la
> suy luan thiet ke CUA CHUNG TA tren nen su that do.

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

#### 6.10.1. Nguon xac thuc

| # | Nguon | Xac nhan dieu gi |
|---|-------|------------------|
| S10 | `mineru/cli/common.py:290-344` (ban cai `~/.local/share/uv/tools/mineru/lib/python3.12/site-packages/mineru`) | Danh sach **day du** file MinerU ghi ra: `_layout.pdf`, `_span.pdf`, `_origin.pdf`, `.md`, `_content_list.json`, `_content_list_v2.json`, `_middle.json`, `_model.json`. **Khong co** searchable/OCR-text-layer PDF |
| S11 | `mineru/cli/api_request.py:233` — `effective_return_original_file = return_original_file and response_format_zip` | `return_original_file` chi copy `{pdf_name}_origin.*` (**ban goc nguyen si**) vao ZIP, va chi khi `response_format_zip=True`. Khong phai PDF da nhung text layer |
| S12 | `grep -ri "ocr" ~/.local/share/uv/tools/pdf2zh/.../pdf2zh/` → **0 ket qua** (pdf2zh 1.9.11) | pdf2zh **khong** co OCR duoi bat ky dang nao |
| S13 | `pdf2zh/high_level.py:21,119` — `from pdfminer.pdfpage import PDFPage` / `PDFPage.create_pages(doc)` | pdf2zh doc text **duy nhat** tu content stream qua pdfminer.six. Trang chi co anh → khong co text object → khong co gi de dich |
| S14 | `babeldoc/main.py:21,299` — `RapidOCRModel` chi duoc dung trong `table_detection` | OCR duy nhat trong cay phu thuoc cua pdf2zh la **table structure detection**, khong phai page text recognition. Va pdf2zh 1.9.11 mac dinh khong chay duong babeldoc (chi khi bat `use_babeldoc`, `pdf2zh/gui.py:332`) |
| S15 | `pdfminer/pdfinterp.py:80,1016-1025` — `self.render` duoc **luu** trong `PDFTextState` nhung khong co cho nao trong pdfminer/pdf2zh **loc** theo no; `pdf2zh/converter.py:80-99` tao `LTChar` vo dieu kien | Text render mode 3 (**invisible**) VAN duoc pdfminer/pdf2zh trich xuat binh thuong → nen tang ky thuat cua cau noi |
| S16 | `pdf2zh/high_level.py:132-157` — `vcls = ["abandon","figure","table","isolate_formula","formula_caption"]`, vung thuoc `vcls` bi gan `box = 0`; `pdf2zh/converter.py:230-245` — `cls == 0` → `cur_v = True` (coi la cong thuc) → **giu nguyen, khong dich** | Rui ro lon nhat cua huong nay: neu DocLayout-YOLO coi trang scan la 1 `figure` khong lo thi pdf2zh se bo qua toan bo. Da bac bo bang thi nghiem T2 (6.10.3) |
| S17 | `mineru/backend/pipeline/model_json_to_middle_json.py:31-32` — `page_w, page_h = map(int, page.get_size())`; `:256-262` — `make_page_info_dict()` tra `{'preproc_blocks', 'page_idx', 'page_size': [page_w, page_h], 'discarded_blocks'}` | bbox trong `middle.json` nam trong **he toa do diem PDF (pt) cua chinh trang goc**, goc trai-tren, y huong xuong — **cung he** voi PyMuPDF. Khong can quy doi DPI |
| S18 | PyMuPDF 1.28.2 (ban trong `.venv` cua project): `Page.insert_text(..., render_mode: int = 0)`, `TextWriter.write_text(..., render_mode=0)` | API dung de ghi text layer vo hinh (`render_mode=3`) da co san, khong can them thu vien |

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

#### 6.10.3. **QUYET DINH: Huong A' — cau noi "searchable PDF" do BB-Translation tu dung**

Giu nguyen tinh than cua Huong A (cau noi la 1 **file PDF that**, pdf2zh xu ly `pdf_scan` y het
`pdf_digital`), nhung **ta tu dung** file do thay vi cho MinerU xuat — vi MinerU khong xuat (S10).
Day cung la huong 2 QA goi y, nay da co bang chung thuc nghiem.

**Cau noi = anh trang goc (giu nguyen) + text OCR ghi de o dung toa do**, gom 2 thao tac tren
**ban sao** file goc, cho moi trang:
1. **Xoa nen chu goc**: to hinh chu nhat trang (`fill=(1,1,1)`) len dung bbox cua tung text span
   lay tu `middle.json`. Anh/bang/hinh minh hoa **khong** bi dung toi.
2. **Ghi text layer vo hinh**: `insert_text(..., render_mode=3)` noi dung OCR cua span do, font
   size scale de vua be ngang bbox.

Ket qua la 1 PDF hop le: mat nguoi nhin thay anh scan (da xoa vung chu), may doc thay text EN —
**dung dinh nghia PDF born-digital doi voi pdf2zh**. Tu day tro di nhanh `pdf_scan` di lai
**nguyen ven** duong 3.1: chunking → pdf2zh → font-shrink → merge → bilingual → cost. Khong co
duong code thu hai.

**Vi sao phai xoa nen chu (buoc 1) — khong duoc bo qua**: pdf2zh giu nguyen moi thu khong phai
text object cua trang goc (anh scan van con nguyen), roi **ve chu tieng Viet de len tren**. Neu
khong xoa nen, ban dich chong len chinh anh chu tieng Anh → khong doc noi (da chup lai o T3).

**Bon thi nghiem chay that** (Tech Lead tu chay luc thiet ke, dung `pdf2zh` 1.9.11 that trong
`~/.local/share/uv/tools/pdf2zh` va PyMuPDF 1.28.2 that trong `.venv` cua project):

| # | Thi nghiem | Ket qua |
|---|-----------|---------|
| T1 | Dung PDF scan-like (chu render thanh anh, khong text layer) → `pdfminer.high_level.extract_text()` **bang chinh python cua pdf2zh** | `''` — **tai hien dung Bug #5**. Cung file sau khi phu text layer `render_mode=3`: `'Blind bake the tart shell\n\nFold in the lemon curd gently'`. → **S15 duoc xac nhan bang thuc nghiem: pdf2zh doc duoc text vo hinh** |
| T2 | Chay **that** `OnnxModel.load_available().predict()` (DocLayout-YOLO cua pdf2zh, model da cache tai `~/.cache/babeldoc/models/doclayout_yolo_docstructbench_imgsz1024.onnx`) tren anh trang scan | `layout classes: ['plain text']` — **khong phai `figure`**. Rui ro S16 (pdf2zh bo qua ca trang vi coi la hinh) **khong xay ra**: DocLayout-YOLO nhin *hinh anh trang*, mot trang scan toan chu trong giong trang chu |
| T3 | Chay **toan bo** `pdf2zh.high_level.translate_stream()` that (translator thay bang ham gia offline) tren 2 file | File scan goc → output `text: ''`, `images: 1` — **dung hien tuong Bug #5**. File cau noi → output `text: 'BANHVI[Blind bake the tart shell Fold in the lemon curd gently]'`, `images: 1` — **noi dung da duoc dich, anh goc van con**. Render ra PNG: chu dich **de len** chu tieng Anh goc → khong doc duoc (ly do bat buoc co buoc xoa nen) |
| T4 | Lap lai T3 voi cau noi **co xoa nen chu** (`draw_rect(fill=(1,1,1))` + padding 1.5pt) | Output: `text: '[VI] Nuong mu vo tart; tron nhe\nlemon curd'`, `images: 1`. Render PNG: **sach, chi con chu tieng Viet**, khong chong hinh. **=> Huong A' hoat dong end-to-end voi pdf2zh that** |

**Danh doi da chap nhan** (phai ghi vao PRD known limitations, xem 6.10.7):
- Vung chu bi thay bang nen trang phang — mat mau nen/hoa tiet giay ben duoi chu (giu duoc anh,
  bang, hoa tiet o vung **khong** phai text span). Voi sach cong thuc lam banh (nen thuong sang,
  chu tren nen tron) day la danh doi chap nhan duoc; voi trang co chu de len anh nen dam, vung
  do se bi 1 mang trang.
- Text layer bam theo **span**, khong bam theo tung ky tu. Vi tri chu tieng Viet trong ban dich
  chinh xac o cap dong, khong cap ky tu.
- Cau noi khong tai tao **font/mau/in dam** cua ban goc — pdf2zh se render ban dich bang Noto,
  giong het cach no xu ly `pdf_digital`.

#### 6.10.4. Trien khai — `src/preprocess/searchable_pdf.py` (module MOI, spec cho Dev)

Dat trong package moi `src/preprocess/` (them `__init__.py`) — day la buoc **truoc** dich, khong
thuoc `postprocess`.

```python
# src/preprocess/searchable_pdf.py  (MOI)

class SearchablePdfError(RuntimeError):
    """Khong dung duoc cau noi — job PHAI fail, tuyet doi khong fallback ve file goc."""

@dataclass(frozen=True)
class SearchablePdfResult:
    path: Path              # {output_dir}/searchable.pdf
    span_count: int         # so span da ghi text layer
    page_count: int
    extracted_chars: int    # so ky tu doc lai duoc bang PyMuPDF — dung cho guard BR-OCR-02

def build_searchable_pdf(
    source_pdf: Path,        # job.file_path — file scan GOC
    middle_json_path: Path,  # MinerUResult.middle_json_path
    output_path: Path,       # data/processing/{job_id}/ocr_bridge/searchable.pdf
    *,
    whiteout_padding: float = 1.5,   # pt, no bbox ra de phu het nét chu
    font_name: str = "helv",
    min_font_size: float = 1.0,
) -> SearchablePdfResult: ...
```

**Trinh tu**

```
1. middle = json.loads(middle_json_path.read_text())
   pages   = middle.get("pdf_info", [])
   Neu rong -> SearchablePdfError("middle.json khong co pdf_info")

2. doc = fitz.open(source_pdf)
   Voi moi page_info trong pages:
     page_idx = page_info.get("page_idx")
     Bo qua neu page_idx None hoac >= doc.page_count (log warning)
     page = doc[page_idx]

     a. Thu thap TEXT SPAN cua trang:
        - Duyet CHI `preproc_blocks` (KHONG lay `discarded_blocks` — do la header/footer/
          watermark MinerU da co y loai; xoa nen chung se lam mat noi dung khong can dich).
          De quy: block -> block.get("blocks", []) (nested) -> lines -> spans.
        - Chi nhan span co `type` thuoc {"text", "inline_equation"} VA
          `content` la str non-empty sau strip. Bo span anh/bang (type image/table/...)
          — chung phai giu nguyen pixel goc.
        - bbox = span["bbox"] -> [x0, y0, x1, y1] float. Bo span co bbox thieu/khong hop le
          (x1 <= x0 hoac y1 <= y0).

     b. Kiem tra he toa do (S17): `page_size` cua middle.json phai xap xi
        (page.rect.width, page.rect.height) — sai lech > 2pt tren bat ky chieu nao ->
        SearchablePdfError kem ca 2 gia tri. KHONG tu doan he so scale: sai toa do se cho ra
        cau noi trong ma van "thanh cong", dung kieu loi im lang Protocol 5 sinh ra de chan.

     c. Xoa nen chu — LAM TRUOC TOAN BO buoc ghi text, cho ca trang:
        for span: page.draw_rect(Rect(x0-p, y0-p, x1+p, y1+p), color=None, fill=(1,1,1),
                                 overlay=True)
        (lam 2 vong rieng: neu xen ke, rect cua span sau se de len text cua span truoc)

     d. Ghi text layer vo hinh:
        for span:
            h  = y1 - y0
            fs = max(h * 0.85, min_font_size)
            tl = fitz.get_text_length(content, fontname=font_name, fontsize=fs)
            if tl > 0: fs = max(fs * min(1.0, (x1-x0)/tl), min_font_size)
            page.insert_text((x0, y1 - h*0.15), content,
                             fontname=font_name, fontsize=fs, render_mode=3)
        `render_mode=3` = invisible (S18). KHONG dung mau trang thay cho invisible — chu trang
        van la net ve that, se lam ban ban dich.
        Ky tu ngoai bang ma cua font base-14 -> insert_text nem loi: bat, log warning, BO QUA
        span do, KHONG lam hong job (OCR tieng Anh hiem khi cham nguong nay).

3. output_path.parent.mkdir(parents=True, exist_ok=True); doc.save(output_path)

4. GUARD (BR-OCR-02): mo lai output_path, cong len tong ky tu get_text() moi trang.
   extracted_chars == 0 -> SearchablePdfError(
       "Cau noi OCR khong tao ra text layer nao — khong the dich file scan nay")
   Day la cho **duy nhat** chan lai kich ban Bug #5.

5. return SearchablePdfResult(...)
```

#### 6.10.5. Sua `run_job()` — spec cho Dev (`src/core/job_orchestrator.py`)

Nguyen tac: sau buoc OCR, sinh ra **1 bien duy nhat** `translation_source_path` va **moi** buoc
doc noi dung sau do dung bien nay. Cach nay lam cho Bug #5 khong the tai dien duoi dang "quen 1
cho": chi con 1 cho de quen, va no co guard.

```python
# Step 2 (sua) — pdf_scan: OCR + dung cau noi
translation_source_path = file_path          # pdf_digital: khong doi

if job.file_type == FileType.PDF_SCAN:
    if self._mineru_runner is None:
        # BR-OCR-01: KHONG duoc chay tiep bang file goc — do chinh la Bug #5.
        raise MinerUUnavailableError(
            "File scan can OCR nhung MinerU chua duoc cau hinh (MINERU_ENDPOINT)"
        )

    bridge_path = self._processing_dir / job.id / "ocr_bridge" / "searchable.pdf"

    if job.ocr_bridge_path and Path(job.ocr_bridge_path).exists():
        # BR-CHUNK-05 resumable: da OCR + dung cau noi o lan chay truoc.
        translation_source_path = Path(job.ocr_bridge_path)
    else:
        ocr_dir = self._processing_dir / job.id / "ocr_output"
        ocr_result = await self._mineru_runner.parse_document(file_path, ocr_dir)
        job.ocr_confidence      = ocr_result.quality.confidence
        job.ocr_dropped_spans   = ocr_result.quality.dropped_span_count

        # US-11 / AC-11.2 — 3 nhanh, xem 6.10.6.
        await self._emit_ocr_warning_if_low(job)

        if ocr_result.middle_json_path is None:
            raise MinerUError(
                "MinerU khong tra middle.json — khong dung duoc text layer cho file scan"
            )
        bridge = build_searchable_pdf(file_path, ocr_result.middle_json_path, bridge_path)
        job.ocr_bridge_path = str(bridge.path)
        translation_source_path = bridge.path
        db_session.add(job)
        await db_session.commit()
```

**Moi cho sau day doi tu `file_path` sang `translation_source_path`** (Dev phai sua **het**,
Reviewer phai grep lai `job.file_path` trong module nay de xac nhan chi con dung 3 cho hop le
liet ke o duoi):

| Vi tri hien tai | Doi thanh |
|---|---|
| `run_job()` Step 3 — `_extract_full_text(file_path)` | `_extract_full_text(translation_source_path)` |
| `_process_chunk()` — `file_path = Path(job.file_path)` | nhan `source_path: Path` qua tham so tu `run_job()`, **bo** doc lai `job.file_path` |
| `_process_chunk()` — `translate_pages(input_path=file_path, ...)` | `input_path=source_path` |
| `_process_chunk()` — `_extract_chunk_text(file_path, chunk)` | `_extract_chunk_text(source_path, chunk)` |
| `_process_chunk()` — `_count_text_segments(file_path, ...)` | `_count_text_segments(source_path, ...)` |

**Ba cho VAN dung file goc — co chu dich, khong duoc doi**:
1. `_count_pdf_pages(file_path)` — so trang giong nhau, doc file goc re hon (cau noi chua ton tai
   o thoi diem do).
2. `MinerURunner.parse_document(file_path, ...)` — OCR phai doc **anh goc**.
3. `create_bilingual_pdf(merged_path, file_path, ...)` — mat EN cua ban song ngu phai la **ban
   scan goc** (nguoi doc can thay trang goc, khong phai ban da xoa nen chu).

**Guard cuoi (BR-OCR-03)** — them vao Step 8, ngay sau `merge_chunk_pdfs()`, ap dung cho **moi**
`file_type` (bug nay co the xay ra o duong `pdf_digital` neu pdf2zh doi hanh vi):

```python
with fitz.open(merged_path) as doc:
    if sum(len(page.get_text().strip()) for page in doc) == 0:
        raise Pdf2zhEmptyOutputError(
            f"Ban dich khong chua chu nao ({merged_path.name}) — pdf2zh khong tim thay "
            "text de dich. Job that bai thay vi tra ve file trong."
        )
```
Loi nay di theo duong `except` san co cua Step 7/8 → `job.status = "failed"` + `error_message`
+ WebSocket `job_failed`. **Day la yeu cau cua QA (Bug #5, "Cach sua de xuat" muc 3): tuyet doi
khong duoc bao `completed` voi ban dich trong.**

#### 6.10.6. Wire `ocr_confidence_threshold` (US-11 / AC-11.2) — gop cung lan fix nay

QA khuyen nghi gop vi cung khu vuc code (`docs/test-report.md` Vong 3 muc 2). Dong y — sau khi co
6.10.5, canh bao nay la **tuyen phong thu duy nhat** cho truong hop OCR *chay duoc nhung doc sai*
(cau noi van co text, guard BR-OCR-02/03 khong bat duoc, ban dich sai nhung khong trong).

`_emit_ocr_warning_if_low(job)` — 3 nhanh dung theo 6.9.7 muc 4:

| `job.ocr_confidence` | Hanh vi |
|---|---|
| `None` (khong span nao qua OCR) | **Khong** canh bao. `ocr_warning = None` |
| `>= settings.ocr_confidence_threshold` | **Khong** canh bao. `ocr_warning = None` |
| `< settings.ocr_confidence_threshold` | Emit WebSocket `ocr_warning` (shape da chot o 5.2, gom `confidence` + `dropped_span_count` + `message`), va set `ocr_warning` trong API response |

**Khong chan job de cho user xac nhan** (3.2 buoc [2] mo ta "cho user chon tiep tuc hoac huy"):
v1.0 job chay background, chua co co che pause/resume-by-user. Canh bao la **thong bao**, job van
chay tiep. Doi lai user co du thong tin de bo ban dich do. Ghi vao PRD known limitation.

**Thay doi API** (`src/api/routes/jobs.py`) — **backward-compatible**, moi field deu optional:

```python
class JobDetail(BaseModel):
    ...
    ocr_confidence: float | None = None      # None cho pdf_digital va cho scan khong co span OCR
    ocr_dropped_spans: int | None = None
    ocr_warning: str | None = None           # chi khac None khi roi vao nhanh 3 o bang tren
```
`_to_detail()` sinh `ocr_warning` bang **cung** ham dung cho WebSocket message (1 nguon su that,
khong viet 2 ban text) — dat trong `src/core/ocr_warning.py` hoac module tuong duong:
```python
def build_ocr_warning(confidence: float | None, dropped_spans: int | None,
                      threshold: float) -> str | None
```
Frontend hien `ocr_warning` nhu 1 banner canh bao tren dong job (mau vang, khong chan download).

#### 6.10.7. Thay doi DB schema + PRD

**Schema** (`src/models/job.py`) — them 2 cot, ca hai nullable, mac dinh `None`:
```python
ocr_bridge_path: str | None = Field(default=None)   # duong dan searchable.pdf (resumable)
ocr_dropped_spans: int | None = Field(default=None) # tu OcrQuality.dropped_span_count
```
⚠️ Project chua co Alembic — `SQLModel.metadata.create_all()` **khong** them cot vao bang da ton
tai. Giong tien le "BREAKING SCHEMA CHANGE" cua Increment 4 Fix Round 1: Dev phai ghi ro trong
`docs/CHANGELOG.md` rang DB dev cu phai xoa/tao lai (`data/bb_translation.db`), va QA phai bat dau
Vong 4 tren DB sach.

**PRD — can PM/user quyet dinh (Tech Lead KHONG tu sua):**
1. **AC-04.x / US-04 nhanh scan**: bo sung known limitation "vung chu tren trang scan duoc thay
   bang nen trang phang truoc khi ghi ban dich; anh/bang/hinh minh hoa giu nguyen" (danh doi
   6.10.3). Day la **thay doi ky vong chat luong dau ra**, khong phai thay doi scope.
2. **AC-11.2**: xac nhan canh bao OCR la **thong bao khong chan job** (khong co buoc user
   confirm/huy giua chung nhu 3.2 buoc [2] tung mo ta). Neu user muon chan that su → do la scope
   moi (pause/resume job), de nghi v1.1.
3. Muc 6.9.7 (cau chu AC-11.2 + nguong 0.80 provisional + nhanh `NULL`) **van dang cho PM xac
   nhan**, chua duoc tra loi — nay tro thanh chan hon vi da co code doc no.

3.2 buoc [3] ("Reconstruct PDF voi text layer") von da mo ta dung huong nay o muc y tuong; section
6.10 la spec thuc thi cua no. Da cap nhat 3.2 tro toi day.

#### 6.10.8. Data lineage tuong minh (CLAUDE.md Protocol 6 — R6-01)

Khai bao bat buoc theo R6-01 cho nhanh `pdf_scan`. Cot "Doc field/bien nao" la thu Reviewer phai
trace tay theo R6-04, va la thu test phai assert theo R6-02.

| Buoc | Artifact sinh ra (ten cu the) | Buoc tiep theo tieu thu | Doc field/bien nao |
|---|---|---|---|
| 1. Upload | `job.file_path` = `data/uploads/{...}.pdf` (scan goc) | 2 | `file_path` |
| 2. `MinerURunner.parse_document(file_path, ocr_dir)` | `MinerUResult.middle_json_path` = `data/processing/{job_id}/ocr_output/middle.json`; `.quality.confidence`; `.quality.dropped_span_count` | 3, 4 | `ocr_result.middle_json_path` |
| 3. `build_searchable_pdf(file_path, ocr_result.middle_json_path, bridge_path)` | `SearchablePdfResult.path` = `data/processing/{job_id}/ocr_bridge/searchable.pdf` | 5 | **`translation_source_path = bridge.path`** ← soi day tung bi dut o Bug #5 |
| 4. `_emit_ocr_warning_if_low(job)` | `job.ocr_confidence`, `job.ocr_dropped_spans`, WS `ocr_warning` | API/UI | `job.ocr_confidence` |
| 5. `_extract_full_text` / `plan_chunks` / `_process_chunk` → `pdf2zh_runner.translate_pages(input_path=...)` | `chunk.output_path` | 6 | **`translation_source_path`**, KHONG phai `job.file_path` |
| 6. `merge_chunk_pdfs` + guard BR-OCR-03 | `job.output_path` = `data/outputs/{job_id}/translated_vi.pdf` | 7 | `merged_path` |
| 7. `create_bilingual_pdf(merged_path, file_path, ...)` | `job.bilingual_path` | — | `merged_path` + **`file_path` goc** (co chu dich, xem 6.10.5) |

**Test bat buoc theo R6-02** (Dev viet, Reviewer verify):
1. `test_pdf_scan_translates_bridge_not_original`: mock `MinerURunner` + `Pdf2zhRunner`, chay
   `run_job()` cho 1 job `pdf_scan`, assert
   `pdf2zh_runner.translate_pages.call_args.kwargs["input_path"] == <bridge path>` **VA**
   `!= Path(job.file_path)`. Day la test se fail tren code hien tai — no chinh la Bug #5.
2. `test_pdf_digital_still_uses_original`: khong regression cho nhanh born-digital.
3. `test_bilingual_uses_original_scan_not_bridge`: assert tham so thu 2 cua
   `create_bilingual_pdf` van la file goc.
4. `test_empty_translation_fails_job`: pdf2zh tra ve PDF khong co text → `run_job()` phai tra
   `status="failed"`, KHONG phai `completed` (BR-OCR-03).
5. `test_build_searchable_pdf_raises_when_no_text_layer`: `middle.json` khong co span text nao →
   `SearchablePdfError` (BR-OCR-02).
6. Fixture `middle.json` **phai** copy shape that (6.9.2/S17), khong tu che theo tri nho —
   Protocol 5 R5-02 tinh than.

**Theo R6-03**: QA Vong 4 phai chay lai dung kich ban E2E Vong 3 (MinerU that + pdf2zh that +
PDF scan that) va mo `translated_vi.pdf` kiem tra **co chu tieng Viet that**, khong chi tin
`status == "completed"`.

---

### 6.11. Financial Safety — dieu tra su co $6.50 va thiet ke hard spending cap

> **Trang thai**: BLOCKING cho v1.0 release. Su co tai chinh THAT da xay ra
> (2026-09-04, $6.50 tien that cua user). Section nay ghi lai ket luan dieu tra
> (co bang chung truc tiep, khong suy doan — CLAUDE.md Protocol 5) va spec giai
> phap cho Dev.

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

#### 6.11.4. Quyet dinh thiet ke — phong thu 4 lop

Nguyen tac: **khong lop nao duoc tin tuong 1 minh**. Lop 1–3 dung uoc luong (co the sai),
lop 4 dung so do that (khong the sai). Thu tu uu tien theo muc do khan.

---

##### Lop 1 [P0] — Cong thuc uoc tinh moi: `estimate_job_cost_v2()`

Thay the `estimate_job_cost()`. **Xoa hang so `AVG_INPUT_TOKENS_PER_PAGE`** — no la goc
cua RC-2 va khong duoc phep ton tai duoi bat ky ten nao.

```python
# src/core/cost_estimator.py

#: Do truc tiep tu cache pdf2zh that (Architecture.md 6.11.2, S1): output tieng Viet
#: co dau tokenize ~2.0 chars/token voi cl100k_base, KHONG phai 4.0 nhu tieng Anh.
#: Thay the cap (vi_expansion=1.3, vi_token_factor=1.5) cu, vi cap do cho
#: chars*0.4875 tokens trong khi so do that la chars*0.579 (thieu 11%).
CHARS_PER_TOKEN_VI = 2.0
VI_CHAR_EXPANSION = 1.16  # do duoc: 809,717 out_chars / 699,103 src_chars

def estimate_job_cost_v2(
    source_text_chars: int,
    segment_count: int,
    prompt_overhead_chars: int,
    provider: TranslationProvider,
) -> CostEstimate:
    """Uoc tinh TRUOC JOB, cung cong thuc voi estimate_chunk_cost() — bat buoc,
    vi uoc tinh truoc va sau job lech nhau chinh la RC-2 cua su co 6.11.

    `segment_count` PHAI den tu _count_text_segments() tren toan bo pham vi trang,
    KHONG duoc suy ra tu so trang.
    """
    input_tokens = int(
        source_text_chars / CHARS_PER_TOKEN_EN
        + segment_count * prompt_overhead_chars / CHARS_PER_TOKEN_EN
    )
    output_tokens = int(source_text_chars * VI_CHAR_EXPANSION / CHARS_PER_TOKEN_VI)
    ...
```

**Rang buoc bat buoc cho Dev:**

1. `POST /api/estimate` va `GET /api/jobs/{id}/cost-estimate`
   (`src/api/routes/jobs.py:541`, `:586`) phai chuyen sang `estimate_job_cost_v2()`.
2. `prompt_overhead_chars` phai la **do dai prompt file THAT** sinh tu
   `write_prompt_file()` **voi glossary da loc cho chinh tai lieu do** — khong duoc
   dung hang so, vi cap 80 entry lam prompt phinh 3.4× (6.11.3 RC-1). Tuc luong
   `/api/estimate` phai goi `write_prompt_file()` (hoac mot ham `build_prompt_text()`
   tach ra) truoc khi uoc tinh.
3. `estimate_chunk_cost()` va `estimate_job_cost_v2()` phai **dung chung 1 ham loi**.
   Neu Dev viet 2 cong thuc song song → Reviewer reject.
4. Ca hai phai duoc kiem chung bang **golden file tu S1** (xem 6.11.6).

##### Lop 2 [P0] — Hard cap TRUOC KHI chay (pre-flight gate)

Config moi trong `src/core/config.py` (them ca 3 vao `SETTINGS_DB_OVERRIDABLE_FIELDS`):

| Field | Default | Y nghia |
|---|---|---|
| `max_cost_per_job_usd` | `2.00` | Tran cho 1 job |
| `max_cost_per_batch_usd` | `5.00` | Tran cho ca batch (bit lo hong RC-3 cap batch) |
| `cost_cap_enabled` | `True` | Tat duoc, nhung **phai tat tuong minh** |

Luong trong `POST /api/jobs` va `POST /api/batches`, **truoc khi tao background task**:

- `estimate > cap` → **HTTP 402 Payment Required**, body:
  `{"detail": ..., "estimated_cost_usd": X, "cap_usd": Y, "requires_confirmation": true}`.
  **KHONG tao Job row, KHONG chay.**
- User co the vuot rao bang `POST /api/jobs {"confirm_cost": true}` — nhung day la
  **opt-in tuong minh cho tung job**, khong bao gio la default, va khong duoc phep
  "nho" lua chon nay cho job sau.
- Voi batch: cap ap len **tong uoc tinh cua moi file trong batch**, tinh truoc khi
  file dau tien chay. Day la lo hong RC-3 nghiem trong nhat cho use-case "dich 5 cuon
  sach cung luc".

##### Lop 3 [P0] — Hard cap TRONG KHI chay (running accumulator)

Pre-flight gate khong du: neu uoc tinh sai thap (nhu RC-2 da tung sai 4.1×), job van
tran. Vi vay:

Trong `JobOrchestrator.run_job()`, tai **cung diem kiem tra `cancel_requested`
hien co** (sau khi `_process_chunk()` xong, truoc chunk ke tiep — vi tri nay da duoc
verify song o QA Vong 5, tai su dung thay vi them diem dung moi):

```
job.actual_cost = sum(chunk.api_cost or 0 for chunk in chunks)   # da co san, dong 376
if settings.cost_cap_enabled and job.actual_cost > effective_cap:
    job.status = "cost_capped"
    job.error_message = (
        f"Job dung o chunk {i}: chi phi uoc tinh tich luy ${job.actual_cost:.2f} "
        f"da vuot tran ${effective_cap:.2f}. Cac chunk da dich duoc giu nguyen — "
        f"tang tran trong Settings roi bam Retry de chay tiep."
    )
    break
```

**Yeu cau thiet ke:**
- Status moi `cost_capped` — **KHONG dung lai `failed`** (day khong phai loi) va
  **KHONG dung lai `cancelled`** (user khong bam gi). Phai phan biet duoc tren UI.
- Ke thua dung co che resume da co: chunk da xong giu `completed`, `retry` chay tiep
  tu chunk dang do (hanh vi nay da verify song o QA Vong 5).
- `effective_cap` = `job.cost_cap_usd` neu job co override, else
  `settings.max_cost_per_job_usd`.
- Voi `BatchOrchestrator`: kiem tra tuong tu **giua cac file**, dung ca batch khi tong
  `actual_cost` moi file vuot `max_cost_per_batch_usd`.

**Han che phai ghi ro trong PRD (khong duoc im lang)**: granularity nho nhat cua lop
nay la **1 chunk (40 trang)**. Mot chunk don doc van co the tieu vuot tran truoc khi bi
chan. Voi cuon 415 trang @gpt-4o, 1 chunk ≈ $1.3 → tran $2.00 co the bi vuot toi ~$3.3
truoc khi dung. **Chi Lop 4 moi chan duoc o granularity request.**

##### Lop 4 [P1, nhung DE XUAT day len lam ngay] — `LLMMeteringProxy`

6.6.6 da thiet ke san va hoan sang v1.1 voi ly do "chua co rui ro thuc te". **Ly do do
khong con dung nua** — rui ro da hien thuc hoa thanh $6.50.

**Phat hien lam giam manh effort**: `src/services/pdf2zh_service_map.py::_build_openai()`
**da truyen san `OPENAI_BASE_URL`** vao env cua subprocess pdf2zh. Tuc chi can doi 1
gia tri env de tro pdf2zh vao proxy cuc bo — **khong phai sua gi trong pdf2zh, khong
phai patch subprocess, khong phai doi kien truc**.

```
pdf2zh subprocess --(OPENAI_BASE_URL=http://127.0.0.1:PORT/v1)--> LLMMeteringProxy
                                                                       |
                                              doc response.usage THAT  |
                                              cong don, so voi tran    v
                                                                  api.openai.com
```

Spec:
- FastAPI app cuc bo, chi bind `127.0.0.1`, port ngau nhien, vong doi = vong doi job.
- Forward `POST /v1/chat/completions` toi `settings.openai_base_url` that.
- Doc `response.usage.prompt_tokens` / `completion_tokens` → **so do that**, cong don
  vao bo dem cua job.
- **Khi vuot tran: tra `429` cho moi request tiep theo** → pdf2zh dung lai. Day la
  hard stop **o granularity tung request**, khong phai tung chunk.
- Khi proxy hoat dong: `job.cost_source = "metered"` (thay vi `"estimated"`); UI hien
  so tien **khong** kem canh bao uoc luong.
- Ap dung duoc cho: `openai`, `deepseek`, `ollama` (deu OpenAI-compatible qua
  `*_BASE_URL`). `gemini`/`claude` v1.0 giu `cost_source="estimated"` + Lop 1–3.
- Bao mat: proxy khong bao gio log body/API key; token key giu trong env subprocess
  nhu hien tai.

**Effort/loi ich**: uoc ~1 increment cho Dev (proxy + wiring + test). Doi lai: xoa bo
hoan toan RC-2 (khong con phu thuoc do chinh xac uoc luong) VA RC-4 (`actual_cost` tro
thanh so that, dung nhu QA Vong 5 da tuong nham la minh dang co). **Danh gia: dang lam
ngay, khong hoan sang v1.1.**

##### Lop 0 [P0, effort ~0] — Sua canh bao va nhan tren UI

Nho nhat nhung chan dung kieu nham lan da gay ra su co:

1. **Model default**: xac nhan `openai_model = "gpt-4o-mini"` (da doi o Increment 6).
   Them canh bao tren UI Settings khi user chon model dat hon `gpt-4o-mini`:
   *"gpt-4o dat hon gpt-4o-mini ~16.7 lan"* — con so nay do duoc tu chinh su co nay.
2. **Nhan uoc luong**: `web/history.html:54-55` hien
   `~$X (estimated)`. Phai doi thanh **khoang**, khong phai 1 so:
   *"Uoc tinh $X – $Y (co the sai lech nhieu lan — pdf2zh khong bao cao token that)"*,
   voi `Y = X × 2.0`. Chi bo canh bao khi `cost_source == "metered"` (Lop 4).
3. **Man hinh xac nhan truoc khi dich**: hien ro **so segment uoc tinh** (khong chi so
   trang) va cau giai thich *"moi doan van la 1 request LLM rieng"* — vi day chinh la
   dieu ca team lan user deu khong hinh dung duoc truoc su co.
4. **Kill switch**: nut "Dung tat ca job" tren UI, dung `cancel_requested` co san cho
   moi job dang chay.

#### 6.11.5. Data lineage (Protocol 6 R6-01)

Chuoi bat buoc, ghi ro artifact va nguoi tieu thu:

| Buoc | Artifact tao ra | Buoc sau doc gi |
|---|---|---|
| 1. Upload | `upload.page_count`, `upload.stored_path` | (2) |
| 2. `build_prompt_text()` (glossary DA loc theo tai lieu) | `prompt_text: str` | (3) qua `prompt_overhead_chars = len(prompt_text) - len("${text}")` |
| 3. `_count_text_segments(stored_path, 1, page_count)` | `segment_count: int` | (4) |
| 4. `estimate_job_cost_v2(chars, segment_count, prompt_overhead_chars, provider)` | `CostEstimate` | (5) |
| 5. Pre-flight gate | pass / HTTP 402 | (6) |
| 6. `run_job()` moi chunk | `chunk.api_cost` | (7) |
| 7. Running accumulator | `job.actual_cost` | so voi `effective_cap` → `cost_capped` |

**Buoc 2 → 4 la soi day de dut nhat**: neu Dev truyen mot `prompt_overhead_chars` hang
so thay vi do tu prompt that co glossary, uoc tinh se thap hon 3.4× ma khong test nao
bat duoc. Test **bat buoc** phai assert gia tri cu the truyen giua buoc 2 va buoc 4
(R6-02), khong duoc chi `assert_called()`.

#### 6.11.6. Golden file bat buoc (Protocol 5 R5-03)

Trich xuat tu S1 truoc khi cache bi xoa, luu tai
`tests/fixtures/pdf2zh/cost_golden_howbakingworks.json`:

```json
{
  "source": "~/.cache/pdf2zh/cache.v1.db, doc 2026-09-04",
  "model": "gpt-4o",
  "requests_cached": 2941,
  "requests_openai_billed": 2989,
  "prompt_chars_total": 3864474,
  "prompt_chars_per_request": 1314,
  "source_text_chars": 699103,
  "translation_chars": 809717,
  "openai_reported_tokens": 1548096,
  "openai_reported_cost_usd": 6.50,
  "pages_translated_approx": 270
}
```

**Test bat buoc**: `estimate_job_cost_v2()` chay tren dung bo tham so nay phai ra
tong token nam trong khoang **[1.0×, 1.6×]** so voi `openai_reported_tokens` — tuc
duoc phep uoc cao (an toan), **khong duoc phep uoc thap**. Test nay la ly do ton tai
cua ca section: no bien su co $6.50 thanh mot rang buoc kiem chung tu dong, khong phai
mot bai hoc chi nam trong tai lieu.

#### 6.11.7. Ra soat cac diem rui ro tai chinh khac (khong con bo sot)

| # | Diem | Trang thai | Xu ly |
|---|---|---|---|
| 1 | `max_concurrent_files=3` gioi han file, **khong** gioi han tien | **HO** | Lop 2 `max_cost_per_batch_usd` |
| 2 | `POST /api/jobs/{id}/retry` chay lai khong qua gate chi phi | **HO** | Retry phai di qua cung pre-flight gate (Lop 2) |
| 3 | Job `pdf_scan` tra tien **2 lan** (MinerU OCR + pdf2zh dich searchable PDF) | Chua mo hinh hoa | `estimate_job_cost_v2()` chua tinh chi phi OCR; MinerU chay cuc bo (mien phi) nen v1.0 chap nhan, ghi vao PRD |
| 4 | `pdf2zh` timeout 3600s/chunk — job co the tieu tien gan 1 tieng truoc khi dung | Da xac nhan (QA Vong 6) | Lop 4 chan o granularity request; Lop 3 chan o granularity chunk |
| 5 | Cache `~/.cache/pdf2zh/cache.v1.db` la lop tiet kiem chi phi **khong duoc quan ly** | Rui ro 2 chieu | Khong xoa cache tu dong (mat tien dich lai). Nhung QA Vong 5 "Quan sat phu" cho thay cache co the tra ve ban dich cu sai ngu canh → them setting `pdf2zh_ignore_cache` (default `False`), ghi ro trade-off tien-vs-chinh-xac tren UI |
| 6 | Khong co tran chi tieu theo **ngay** | **HO** | v1.1: cong don `actual_cost` moi job trong 24h, canh bao khi vuot `daily_budget_usd` |

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


### 6.12. Adaptive Concurrency Controller (AIMD) cho `pdf2zh --thread`

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

#### 6.12.1. Nguon xac thuc (Protocol 5 R5-01)

Phien ban pdf2zh da cai va dung de verify: **v1.9.11**
(`pdf2zh --version` -> `pdf2zh v1.9.11`). Root:
`~/.local/share/uv/tools/pdf2zh/lib/python3.12/site-packages/pdf2zh/`.

| # | Contract | Nguon xac thuc | Ket luan |
|---|----------|----------------|----------|
| S1 | Flag `--thread` / `-t`, `type=int`, `default=4` | `pdf2zh/pdf2zh.py:102-107` (doc truc tiep) | VERIFIED |
| S2 | `--thread` -> `max_workers` cua `ThreadPoolExecutor` bao quanh `translator.translate(s)` cho tung doan van | `pdf2zh/converter.py:359-361` (`with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread) as executor: news = list(executor.map(worker, sstk))`) | VERIFIED |
| S3 | `OpenAITranslator.do_translate()` co `@retry(retry=retry_if_exception_type(openai.RateLimitError), stop=stop_after_attempt(100), wait=wait_exponential(multiplier=1, min=1, max=15))`, `before_sleep` log dong `"RateLimitError, retrying in {N} seconds... (Attempt {k}/100)"` | `pdf2zh/translator.py:436-456`; class `OpenAITranslator` tai `translator.py:399` | VERIFIED |
| S4 | `DeepseekTranslator(OpenAITranslator)` chi override `__init__` (set `base_url="https://api.deepseek.com/v1"`), KHONG override `do_translate` | `pdf2zh/translator.py:912-937`; `grep -n "^class \|do_translate"` xac nhan khong co `do_translate` giua dong 912 va 939 | VERIFIED — ke thua retry cua S3 |
| S5 | `GeminiTranslator(OpenAITranslator)` chi override `__init__` (set `base_url="https://generativelanguage.googleapis.com/v1beta/openai/"` — endpoint OpenAI-compat chinh thuc cua Google), KHONG override `do_translate` | `pdf2zh/translator.py:628-655` | VERIFIED ve mat ke thua code; **hanh vi 429 that chua verify** — xem 6.12.8 |
| S6 | `OpenAIlikedTranslator(OpenAITranslator)` (duong dan Claude qua Anthropic OpenAI-compat, xem 6.6.6) chi override `__init__`, KHONG override `do_translate` | `pdf2zh/translator.py:939-974` | VERIFIED ve mat ke thua code; **hanh vi 429 that chua verify** — xem 6.12.8 |
| S7 | `OllamaTranslator(BaseTranslator)` — class RIENG, KHONG ke thua `OpenAITranslator`, KHONG co decorator `@retry` nao, goi thang `self.client.chat(...)` khong catch exception | `pdf2zh/translator.py:296-336` | VERIFIED — co che rate-limit KHONG ap dung |
| S8 | pdf2zh CLI cau hinh logging bang `logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])` | `pdf2zh/pdf2zh.py:249` (trong `main()`) | VERIFIED |
| S9 | `RichHandler()` khong truyen `console=` -> dung `get_console()`, la global Console ghi ra **stdout** (`Console.file` = `sys.stderr if self.stderr else sys.stdout`, `stderr` default `False`) | `rich/logging.py:34-35` + `rich/logging.py:98` (`self.console = console or get_console()`) + `rich/console.py:757-759`, `console.py:630` | VERIFIED — **dao nguoc gia dinh ban dau**, xem 6.12.2 |
| S10 | Khi khong phai TTY, rich wrap dong log o 80 cot, **cat doi** chuoi `"RateLimitError, retrying"` | Chay that (xem 6.12.2, log capture) | VERIFIED |
| S11 | Dat `COLUMNS=200` trong env cua subprocess lam dong log khong bi wrap, grep duoc nguyen ven | Chay that (xem 6.12.2) | VERIFIED |
| S12 | DeepSeek gioi han **so request dong thoi** o muc tai khoan; vuot -> HTTP 429 ngay (khong queue). `deepseek-v4-pro` = 500, `deepseek-v4-flash` = 2500 | https://api-docs.deepseek.com/quick_start/rate_limit (WebFetch 2026-09-05) | VERIFIED — nhung xem canh bao S13 |
| S13 | Model DeepSeek app dang cau hinh mac dinh la `deepseek-chat` (`src/core/config.py:30`), **KHONG** nam trong bang gioi han cua S12 | `src/core/config.py:30` + bang o S12 | `[UNVERIFIED]` — khong duoc suy ra so 500/2500 cho `deepseek-chat` |

---

#### 6.12.2. Phat hien chan thiet ke: tin hieu rate-limit nam o STDOUT, khong phai STDERR

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

**Quyet dinh chot:**

- **D1** — `Pdf2zhRunner` **PHAI capture va giu ca stdout**, va bo dem rate-limit doc tu
  **stdout hop nhat voi stderr** (giu ca hai de an toan neu upstream doi handler ve stderr
  o version sau).
- **D2** — `Pdf2zhService.envs` **PHAI** them `COLUMNS=200`. Da verify (S11): voi
  `COLUMNS=200` dong log ra nguyen ven 1 dong, grep duoc, va doc duoc ca `(Attempt k/100)`.
  Chon 200 chu khong phai 80/400: du rong cho toan bo dong log dai nhat cua pdf2zh cong
  cot timestamp + level + source cua rich, van du hep de khong lam file log phinh vi padding.
- **D3** — Regex dem, dinh nghia 1 lan tai `src/core/concurrency_controller.py`:

```python
#: Doi voi rich, phan "RateLimitError" luon dung dau message va khong bao gio bi cat
#: (verified 6.12.1 S10/S11). Chi neo vao token nay, KHONG neo vao ca cum
#: "RateLimitError, retrying" — cum do da tung bi wrap lam doi khi COLUMNS < 120.
RATE_LIMIT_LINE_RE = re.compile(r"RateLimitError", re.MULTILINE)
```

  `rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))`.

**Thu tu bat buoc:** D1 + D2 la **blocker** cho toan bo phan con lai cua 6.12. Dev khong
duoc implement AIMD truoc khi 2 fix nay xanh, vi khong co chung thi bo dem luon bang 0.

---

#### 6.12.3. Fix bug mat stdout/stderr khi timeout (spec cho Dev)

Hien tai (`src/services/pdf2zh_runner.py:88-99`), khi timeout code `process.kill()` roi raise,
**vut bo toan bo output da sinh ra**. Vi vay khong phan biet duoc 2 gia thuyet doi lap nhau:
(A) bi rate-limit doi dap nen `wait_exponential` an het 1 gio, (B) don thuan thieu concurrency.
Hai gia thuyet nay doi hoi hanh dong **nguoc chieu** (A: giam thread; B: tang thread), nen
mat tin hieu = khong duoc phep doan.

**Spec sua** — thay `communicate()` don le bang thu gom incremental + vet buffer sau khi kill:

```python
# src/services/pdf2zh_runner.py  (SUA)

async def _drain(stream: asyncio.StreamReader, sink: bytearray) -> None:
    """Doc lien tuc vao `sink` cho toi EOF. Chay nhu task nen, khong bao gio raise."""
    while True:
        block = await stream.read(65536)
        if not block:
            return
        sink.extend(block)

# ...trong translate_pages(), thay cho asyncio.wait_for(process.communicate(), ...):
stdout_buf, stderr_buf = bytearray(), bytearray()
drains = [
    asyncio.create_task(_drain(process.stdout, stdout_buf)),
    asyncio.create_task(_drain(process.stderr, stderr_buf)),
]
timed_out = False
try:
    await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
except TimeoutError:
    timed_out = True
    process.kill()
    await process.wait()
finally:
    # Vet not phan pipe con dong lai sau khi process chet. 5s la du: pipe da
    # dong o dau ghi, `_drain` chi con doc phan buffer OS con lai.
    await asyncio.wait(drains, timeout=5.0)
    for d in drains:
        d.cancel()

stdout = bytes(stdout_buf).decode("utf-8", errors="replace")
stderr = bytes(stderr_buf).decode("utf-8", errors="replace")
```

Vi sao **khong** dung `communicate()` voi timeout ngan sau khi kill: `communicate()` doc
mot lan tu dau pipe; neu pdf2zh ghi qua 64KB (chac chan xay ra sau 1 gio log INFO) thi pipe
day va **process bi block ngay tu giua chung** truoc ca khi timeout — doc incremental
(`_drain` chay song song tu giay dau) vua giai quyet mat tin hieu vua giai quyet deadlock
pipe tiem an.

`Pdf2zhTimeoutError` phai mang theo tin hieu da vet duoc, khong con la exception tron:

```python
class Pdf2zhTimeoutError(RuntimeError):
    def __init__(self, message: str, *, stdout: str, stderr: str, rate_limit_hits: int) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.rate_limit_hits = rate_limit_hits
```

`Pdf2zhResult` them 2 field: `stdout: str` va `rate_limit_hits: int`.

---

##### 6.12.3.1. Quyet dinh: `stdout` / `rate_limit_hits` CO default (`""` / `0`)

**Boi canh:** spec tren khong noi ro 2 field moi co default hay khong. Dev escalate theo
R5-02: neu de no-default, 16 test integration co san (`tests/integration/test_job_orchestrator.py`
2 cho, `test_job_cancel.py` 1 cho, `test_cost_capped_orchestrator.py` dung lai fixture cua
file dau) fail ngay, du chung khong lien quan gi den rate-limit.

**Quyet dinh (Tech Lead, da chot — khong de mo): GIU default `stdout=""`, `rate_limit_hits=0`,
2 field dat o cuoi dataclass.** Ap dung cung quy tac cho `Pdf2zhError` (xem duoi).

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

**Rang buoc di kem (bat buoc, khong phai khuyen nghi):**

- **R-6.12.3.1-a:** Moi loi ra cua `translate_pages()` — return **va** ca 2 nhanh `raise` —
  phai truyen `stdout` va `rate_limit_hits` **tuong minh**. Cam dua vao default trong
  `src/`. Reviewer kiem dieu nay khi review `pdf2zh_runner.py`.
- **R-6.12.3.1-b:** `Pdf2zhError` cung phai mang `stdout` / `stderr` / `rate_limit_hits`.
  Truoc quyet dinh nay no la exception tron, trong khi 6.12.4 phan loai exit code != 0 thanh
  `rate_limited` (khi `rate_limit_hits >= 1`) hoac `error` (khi == 0) — thieu field thi
  orchestrator khong the phan biet, va se im lang roi ve `error`/HOLD dung luc dang bi
  rate-limit. Da sua trong cung lan nay.
- **R-6.12.3.1-c:** Khi controller AIMD duoc viet (6.12.4), no **khong** duoc nhan
  `rate_limit_hits` roi rac tu caller tu do; no nhan nguyen `Pdf2zhResult` / exception do
  runner sinh ra, de gia tri luon truy nguoc duoc ve `stdout` that.

**Chot cau hoi "1 lan TIMEOUT co phai tin hieu giam manh khong": KHONG.** Xu ly tach doi
theo tin hieu da vet duoc:

| Truong hop | Dieu kien | Hanh dong len `current_thread` | Ly do |
|---|---|---|---|
| Timeout **co** tin hieu | `rate_limit_hits >= 1` trong output da vet | Multiplicative decrease (giong overload thuong) | Gia thuyet A duoc xac nhan bang bang chung, khong phai doan |
| Timeout **khong** tin hieu | `rate_limit_hits == 0` | **HOLD** (giu nguyen `current_thread`) + giam `chunk_size` cho job sau (6.12.7) | Day la gia thuyet B: cham thuan tuy. Giam thread se lam **cham hon nua** -> timeout tiep -> vong xoay tu sat. Tang thread thi lai lieu linh khi chua biet nguyen nhan. HOLD la lua chon duy nhat khong the sai theo huong xau hon. Sau D1+D2 truong hop nay tro nen hiem: chi con xay ra khi provider that su cham chu khong throttle. |

---

#### 6.12.4. Thuat toan AIMD — chot cong thuc

Don vi dieu khien: gia tri truyen cho `pdf2zh --thread`. 1 quan sat = 1 chunk
(1 lan goi `translate_pages()` = 1 subprocess pdf2zh, `job_orchestrator.py:594-602`).

**Phan loai ket qua 1 chunk** (`ChunkOutcome`):

| Outcome | Dieu kien chinh xac | Delta thread |
|---|---|---|
| `success` | exit code 0 **VA** `rate_limit_hits == 0` **VA** `duration_seconds <= 0.75 * timeout_seconds` | `+2` (additive increase) |
| `slow_success` | exit code 0 **VA** `rate_limit_hits == 0` **VA** `duration_seconds > 0.75 * timeout_seconds` | `0` (HOLD) |
| `rate_limited` | exit code 0 hoac khac 0, **VA** `rate_limit_hits >= 1` | `max(floor, floor(current * 0.5))` |
| `timeout_signalled` | timeout **VA** `rate_limit_hits >= 1` | `max(floor, floor(current * 0.5))` |
| `timeout_silent` | timeout **VA** `rate_limit_hits == 0` | `0` (HOLD) — xem 6.12.3 |
| `error` | exit code != 0 va `rate_limit_hits == 0` (loi khac: font, PDF hong, thieu key) | `0` (HOLD) — khong phai tin hieu concurrency |

**Cac con so — deu la quyet dinh ky thuat noi bo, khong co "nguon xac thuc" ben ngoai
(R5-01 cho phep, nhung phai ghi ro ly do):**

- **Additive increase = +2 (khong phai +1, khong phai nhan 1.5).** 1 quan sat o day dat
  bat thuong: 1 chunk mat 10-40 phut. Voi `+1`, di tu floor 8 len tran 32 can 12 chunk —
  het ca cuon sach van chua hoc xong, controller vo dung. Voi multiplicative increase
  (x1.5+) buoc nhay gan tran qua lon (21 -> 32) va se dam thang vao tuong concurrency
  trong 1 buoc, dung nguyen nhan ma AIMD co dien chon **additive** increase de dat
  hoi tu on dinh. `+2` la thoa hiep: dat tran trong 12 quan sat ke tu floor 8, moi buoc
  du nho de khong nhay qua diem gay.
- **Multiplicative decrease = x0.5 (β = 0.5).** Gia tri co dien cua AIMD; cat doi bao dam
  thoat khoi vung qua tai trong `log2(32/8) = 2` buoc tu tran ve floor, tuc phan ung du
  nhanh de khong dot chay 100 lan retry.
- **`rate_limit_hits >= 1` la du de giam, KHONG doi nguong N >= 3.** Vi
  `stop_after_attempt(100)` + `wait_exponential(max=15)` (S3) nghia la pdf2zh **khong**
  crash khi bi 429 — no am tham ngu toi 15s/lan, toi da 100 lan cho **moi doan van**.
  Doi cho du "3 dong" moi phan ung nghia la da co the mat hang chuc phut dong ho. Chi phi
  cua viec giam nham (chi 1 dong log 429 le te) rat re: mat throughput cua dung 1 chunk,
  roi additive increase leo lai ngay chunk sau.
- **Nguong `success` = 0.75 * timeout.** Chunk chay het >75% ngan sach thoi gian la chunk
  **sat mep vuc**: tang thread luc do la dat cuoc rang lan sau se nhanh hon, nhung neu sai
  thi hau qua la timeout (mat 1-2 gio, phai chay lai chunk). Bien an toan 25% cho phep
  bien dong tu nhien giua cac chunk (mat do chu khac nhau tung phan sach) ma khong dua
  controller vao vung timeout.

**Vong doi 1 job** (`run_job()` step 6-7):

1. Doc `ConcurrencyState` cho `(provider, model)` = **`(job.model, service.service_arg)`**.
   Chua co -> tao moi voi `current_thread = ADAPTIVE_THREAD_FLOOR[provider]`,
   `observation_count = 0`. Xem 6.12.4.1 cho nguon chinh xac cua 2 nua khoa.
2. Truoc **moi** chunk: doc `state.current_thread`, truyen vao `translate_pages(thread=...)`.
   Ghi vao `chunk.thread_used` **truoc** khi goi (R6-01: lineage tuong minh).
3. Sau **moi** chunk: phan loai outcome tu `Pdf2zhResult` / `Pdf2zhTimeoutError`, cap nhat
   `state`, commit. Ghi `chunk.rate_limit_hits`.
4. State la **per (provider, model), khong phai per job** — hoc duoc tu job nay dung ngay
   cho job sau. Day la ly do no phai nam trong DB chu khong phai bien trong bo nho.

**Chot khong co giai doan "probe" rieng.** Khong tao them co che tham do; moi chunk that
da la 1 quan sat. Them probe chi lam ton tien API that (bai hoc 6.11).

##### 6.12.4.1. Nguon 2 nua khoa `(provider, model)` — chot (sua tham chieu sai field)

Ban dau muc 1 o tren viet `job.model_provider`. **Field do khong ton tai** — day la loi
tham chieu sai field trong tai lieu, khong phai 1 quyet dinh thiet ke khac. Chot lai theo
dung code that (Protocol 5 R5-01 — tai lieu phai khop nguon xac thuc):

| Nua khoa | Nguon | Vi du gia tri | Xac thuc |
|---|---|---|---|
| `provider` | **`job.model`** (`src/models/job.py:55`, kieu `str`) | `"deepseek"` | `Job.model` da duoc TOAN BO codebase dung lam **provider identifier**, khong phai ten model: `Pdf2zhServiceMapper.map(job.model, ...)` (`job_orchestrator.py:228`), `ProviderFactory.create(job.model, ...)` (`job_orchestrator.py:260`), `_resolve_provider_or_400(job.model, settings)` (`src/api/routes/jobs.py:590,653`). `ADAPTIVE_THREAD_FLOOR` cung dang key theo dung tap gia tri nay. |
| `model` | **`service.service_arg`** (`Pdf2zhService`, `src/services/pdf2zh_service_map.py:23`) | `"deepseek:deepseek-chat"` | Day la gia tri **that su** duoc truyen cho `pdf2zh -s`, tuc backend + model that su nhan tai — dung thu ma state can phan biet. |

**Khong them cot moi tren `Job`.** Mot cot `Job.model_provider` se trung lap y nghia voi
`Job.model` dang co va tao 2 nguon su that cho cung 1 khai niem — dung loai no lon ma
6.11 da phai tra gia. Neu ve sau muon doi ten cho ro (`Job.model` -> `Job.provider`), do la
1 migration rieng cho toan bo codebase, khong phai viec cua 6.12.

**Tai sao dung nguyen `service_arg` chu khong parse lay phan sau dau `:`.** Yeu cau o 6.12.8
la "doi model (`deepseek-chat` -> `deepseek-reasoner`) phai co state rieng". `service_arg`
thoa man dieu do **manh hon** phan model tran, vi anh xa `model -> service_arg` la don anh
(injective) trong pham vi 1 provider: 2 model khac nhau luon cho 2 `service_arg` khac nhau,
cung 1 model luon cho cung 1 chuoi. Parse `split(":", 1)` chi lam dep hien thi nhung them
1 diem gay: `ollama` dung dau `:` ngay trong ten model (`llama3:8b`), va tien to backend
khong phai luc nao cung bang ten provider (`claude` -> `openailiked:...`, 6.6.6) — nen
tien to la thong tin co ich de giu, khong phai nhieu. Hai provider con lai khong bao gio
toi day: `ollama` thoat som o `_resolve_thread()` (6.12.6), `deepl` raise
`UnsupportedForPdfPipelineError` truoc do (6.6.7).

---

#### 6.12.5. Floor va ceiling — chot con so

**Floor (gia tri khoi diem khi chua co lich su cho `(provider, model)`):**

| Provider | Floor | Ly do |
|---|---|---|
| `deepseek` | **8** | DeepSeek gioi han **so request dong thoi** o muc tai khoan va so do it nhat la hang tram (S12: 500 cho v4-pro, 2500 cho v4-flash). 8 luong nam duoi nguong do hang chuc lan — an toan tuyet doi, dong thoi gap doi mac dinh 4 cua pdf2zh von la nguyen nhan su co. **Luu y S13**: `deepseek-chat` (model app dang cau hinh) khong nam trong bang do; floor 8 duoc chon vi no an toan **du bang gioi han co ap dung hay khong**, chu khong phai suy ra tu so 500/2500. |
| `openai` | **8** | Cung ly do do lon: OpenAI gioi han theo RPM/TPM chu khong theo concurrency, va 8 request song song la muc thap so voi bat ky tier tra phi nao. Neu sai, S3 bao dam pdf2zh retry chu khong crash, va AIMD se cat con 4 ngay chunk sau. |
| `gemini` | **4** | Giu bang mac dinh pdf2zh. Gemini free/low tier co RPM rat thap va — quan trong hon — hanh vi 429 that qua lop OpenAI-compat **chua verify** (S5, 6.12.8). Khong duoc dat floor cao hon khi chua chac chan bo dem co hoat dong. |
| `claude` (qua `openailiked`) | **8** ⚠️ | **Cap nhat 2026-09-06 — quyet dinh chap nhan rui ro cua nguoi dung, KHONG phai ket qua spike PASS.** Ly do goc chon 4 van con nguyen: `openailiked` la lop workaround, hanh vi 429 that (S6) van `[UNVERIFIED]` — spike 6.12.6 cho Claude **da chay va KHONG PASS** (bi chan boi `CLAUDE_API_KEY` la placeholder gia trong `.env`, 0 tin hieu that quan sat duoc, xem `tests/fixtures/pdf2zh/claude_ratelimit_spike/README.md`). Nguoi dung yeu cau nang len 8 truoc khi co key that de spike lai. Chap nhan duoc **chi vi** 2 ly do: (1) AIMD van TAT cho claude — day la gia tri CO DINH, khong ramp them dua tren tin hieu co the sai; (2) `chunk_size` cold-start (6.12.7) van gioi han 3 chunk dau o 20 trang bat ke floor nay, chan ban kinh thiet hai. **Phai doi lai 4 (hoac verify that theo 6.12.6) ngay khi co `CLAUDE_API_KEY` that** — day la no ky thuat co chu dich, khong phai trang thai vinh vien. |
| `gemini` | **4 (khong doi)** | Giu bang mac dinh pdf2zh. Gemini free/low tier co RPM rat thap va — quan trong hon — hanh vi 429 that qua lop OpenAI-compat **chua verify** (S5, 6.12.8; spike 6.12.6 cung da thu nhung BLOCKED vi thieu `GEMINI_API_KEY`, chua co ket qua). Khac Claude, Gemini **van dang chay AIMD that** (khong bi khoa) — nang floor o day khong giong nang 1 hang so co dinh: no la diem xuat phat cua 1 tien trinh dang tu dieu chinh, sai lech o day khuech dai nhanh nhat dung luc do tin cay tin hieu thap nhat. Loi ich nang len 8 cung nho (chi tiet kiem ~2 chunk ramp-up truoc khi cham tran 32) — nguoi dung da dong y giu nguyen 4 cho Gemini (khac quyet dinh cho Claude). |
| `ollama` | **N/A** | Khong dung AIMD. Xem 6.12.6. |

**Ceiling (tran cung, dung chung cho moi provider) = 32.**

Tran nay **khong** suy ra tu quota cua provider (DeepSeek cho phep toi 500-2500, cao hon
rat nhieu). No suy ra tu **rang buoc phia BB-Translation**, la rang buoc chat hon:

1. **An toan chi phi (6.11).** Lop 3 cua 6.11.4 la running accumulator chan job khi vuot
   `max_cost_per_job_usd`. Do chinh xac cua no bi gioi han boi so request dang bay khi cham
   tran: N request in-flight = N request da tieu tien ma accumulator chua kip thay.
   `max_concurrent_files = 3` (`config.py:62`) nghia la toi da 3 job song song, tuc
   `3 * 32 = 96` request in-flight toan he. Day la muc "vuot tran" toi da chap nhan duoc.
   Nang tran len 64 se lam doi con so do — di nguoc bai hoc su co $6.50, noi ban than viec
   thieu chan tren la root cause.
2. **Bo nho.** Moi luong giu 1 HTTP connection + state cua 1 doan van trong tien trinh
   pdf2zh. 96 luong tren 3 tien trinh Python la muc M1 Pro 32GB (may target — 9.1) chiu
   duoc; cao hon thi rui ro swap lam **cham** di dung luc dang co gang nhanh len.

Vi tran bi rang buoc boi so tien va bo nho cua chinh app chu khong boi provider, no la
**hang so dung chung**, khong per-provider: `ADAPTIVE_THREAD_CEILING = 32`.

---

#### 6.12.6. Xu ly rieng: Claude va Ollama

**Ollama — KHONG dung AIMD. Chot: thread co dinh, user chinh tay.**

`OllamaTranslator` la class rieng ke thua `BaseTranslator`, khong co `@retry`, khong catch
exception (S7). Khong ton tai dong log nao de dem — co che tin hieu cua 6.12.2 khong ap dung
duoc, va khong the "vay muon" tin hieu khac: Ollama chay local, nghen la do CPU/GPU/RAM cua
may chu khong phai quota, bieu hien la **cham dan** hoac loi connection, khong phai 1 su kien
roi rac dem duoc. AIMD khong co tin hieu = AIMD leo mai toi tran roi lam treo may user.

Chot:
- Them `Settings.ollama_thread: int = 2` (`.env`-only, **khong** vao
  `SETTINGS_DB_OVERRIDABLE_FIELDS`... xem ngoai le duoi day).
- Ngoai le: `ollama_thread` **duoc** them vao `SETTINGS_DB_OVERRIDABLE_FIELDS`. Day la
  ngoai le co chu dich va la field duy nhat cua 6.12 nam trong do — dung tieu chi da ghi tai
  `config.py:96-104` ("chi field user thuc su muon doi tu UI"): gia tri dung phu thuoc phan
  cung cua chinh may user (VRAM, so core), thu ma app khong the tu suy ra va AIMD khong the
  tu hoc. Day la **user config**, dung nghia.
- Mac dinh 2, khong phai 4: `ollama_model` mac dinh la `gemma2:27b` (`config.py:44`) — model
  27B tren M1 Pro 32GB chi vua du RAM cho 1-2 request song song; 4 luong se day may vao swap.
- UI Settings phai co helper text: "Tang neu may co nhieu VRAM; giam ve 1 neu may treo."

**Claude (qua `openailiked`) — AIMD bi TAT cho toi khi spike xanh. `[UNVERIFIED]`**

Da verify (S6) rang `OpenAIlikedTranslator` khong override `do_translate`, tuc **ve mat
code** no ke thua nguyen decorator retry cua S3. Nhung decorator do bat dung
`openai.RateLimitError`. Chuoi phu thuoc chua verify duoc bang doc code:

Anthropic OpenAI-compat layer tra 429 -> SDK `openai` phai phan loai duoc response do
thanh dung `openai.RateLimitError`. Neu shape body/status cua Anthropic khien SDK nem
`openai.APIStatusError`/`APIError` chung chung thay vi `RateLimitError`, thi:
`retry_if_exception_type(openai.RateLimitError)` **khong khop** -> khong retry, khong log
dong nao -> `rate_limit_hits` = 0 vinh vien -> **AIMD tang thread mai cho toi khi crash
hoac timeout**, va im lang sai theo dung kieu su co MinerU (mock/gia dinh tu nhat quan voi
chinh no).

`[UNVERIFIED]` — chan Dev bat AIMD cho provider `claude`. Cho toi khi spike duoi day xanh,
`claude` dung thread co dinh = 4 (`current_thread` khoa o floor, khong tang).

**Spike test bat buoc truoc khi bat AIMD cho Claude (R5-02):**

1. Chuan bi 1 PDF nho that (5-10 trang, dac chu — dung 5 trang dau cua chinh file
   "How baking works" da gay su co).
2. Chay `pdf2zh` truc tiep bang tay (khong qua app) voi `-s openailiked`, env tro toi
   Anthropic compat endpoint theo dung 6.6.6, va **`--thread 64`** — co tinh dat cao gap
   doi tran de ep cham rate limit that. Them `COLUMNS=200` (D2).
3. Redirect **rieng** stdout va stderr ra 2 file. Ghi ca hai vao
   `tests/fixtures/pdf2zh/claude_ratelimit_spike/` lam golden file (Protocol 5 muc 3 —
   moi mock ve sau phai sinh tu day, khong duoc viet tay).
4. **Tieu chi PASS**: file stdout chua it nhat 1 dong khop `RATE_LIMIT_LINE_RE`.
   -> ket luan bo dem hoat dong cho Claude, go `[UNVERIFIED]`, dat floor claude = 8.
5. **Tieu chi FAIL**: khong co dong nao, ma process crash hoac tra loi bat thuong.
   -> ghi lai exception that (traceback day du) vao golden file, escalate ve Tech Lead.
   AIMD cho Claude o nguyen trang thai TAT; **khong** duoc "sua tam" bang cach doan them
   pattern regex khac.
6. Neu chay 3 lan lien tiep o `--thread 64` ma khong bao gio cham rate limit: ket qua la
   **INCONCLUSIVE**, khong phai PASS. Ghi ro trong test-report.md; AIMD cho Claude van TAT.

Spike y het nhu vay ap dung cho **Gemini** (S5) truoc khi nang floor gemini tu 4 len 8.
Cho toi khi do, gemini van chay AIMD (floor 4, tran 32) — chap nhan duoc vi neu bo dem
im lang sai thi tran 32 van la chan tren cung, va `slow_success`/`timeout_silent` van giu
duoc controller khoi leo vo han.

---

#### 6.12.7. Tuong tac voi `chunk_size` — chot

**Co, tam giam. 40 -> 20 khi `(provider, model)` chua hoc xong.**

`chunk_size` la **ban kinh sat thuong** cua 1 lan doan sai: o thread=4, 1 chunk 40 trang
sach dac chu da lam no ngan sach 3600s. Trong giai doan AIMD chua hoi tu, xac suat doan sai
cao nhat — nen phai la luc ban kinh sat thuong nho nhat. Chunk 20 trang cat doi wall-clock
xau nhat cua 1 lan sai (<=30 phut thay vi >=60 phut) va **doi luong quan sat cua AIMD**
tren cung 1 cuon sach (nhieu chunk hon = hoc nhanh hon) — hai loi cung 1 thay doi.

**Dieu kien tang lai 40:** `state.observation_count >= 3` **VA**
`state.consecutive_successes >= 3` (3 chunk `success` lien tiep, khong co lan giam nao xen
giua — bat ky outcome khac `success` deu reset `consecutive_successes` ve 0).
Chon 3: du de loai bo 1 chunk may man ngau nhien, du nho de khong ket o chunk 20 het ca cuon.

**Rang buoc bat buoc — `chunk_size` phai chot 1 lan cho ca job, KHONG doi giua chung:**
`plan_chunks()` (`job_orchestrator.py:256`) sinh ra cac `Chunk` row duoc persist va dung
lai khi resume (BR-CHUNK-05, `_load_or_create_chunks()`). Doi `chunk_size` giua job se lam
cac `page_start`/`page_end` da luu khong con khop ke hoach moi -> trang bi dich lai hoac bi
bo sot, tai dung kieu loi lineage cua Bug #5. Vi vay:

- Quyet dinh `chunk_size` **dung 1 lan** tai step 6 cua `run_job()`, truoc `plan_chunks()`.
- Ghi lai vao `Job.chunk_size_used: int` (cot moi) de resume dung so cu, khong doc lai
  `self._chunk_size` hay tinh lai tu `ConcurrencyState` (state co the da doi giua 2 lan chay).
- Ngua lai, `current_thread` **duoc phep** doi giua cac chunk trong cung 1 job — no chi la
  tham so runtime cua 1 subprocess, khong dinh vao ke hoach da persist.

**Nhanh `ollama` va nhanh `adaptive_concurrency_enabled=False`: LUON 20, KHONG doc
`ConcurrencyState`.** (Chot sau escalation cua Dev theo R5-02 o buoc 5 — ban dau pseudocode
duoi day goi `get_state()` vo dieu kien, sai.)

Ly do — 2 tang, deu bat buoc:

1. **Bat buoc ve invariant (khong the lam khac):** 6.12.6 chot `ollama` va 6.12.8 chot nhanh
   kill-switch **khong bao gio** doc/ghi `ConcurrencyState`. Goi `get_state()` o day se pha
   dung invariant do; rieng voi `ollama` no con `KeyError` ngay lap tuc vi
   `ADAPTIVE_THREAD_FLOOR` co tinh **khong co khoa `"ollama"`** (6.12.5: "N/A — khong dung
   AIMD"). Guard phai co **cung hinh dang** voi guard da co trong `_resolve_thread()`, doc
   cung 2 dieu kien theo cung thu tu — 2 guard lech nhau la mam mong cua 1 Bug #5 khac.
2. **Dung ve mat gia tri (20 la con so dung, khong phai chi la fallback an toan):** ly do goc
   chon 20 o tren la "ban kinh sat thuong cua 1 lan AIMD **doan sai**". O 2 nhanh nay khong
   ton tai lan doan nao — thread la hang so (`settings.ollama_thread`, hoac
   `ADAPTIVE_THREAD_FLOOR[provider]`) — nen thoat nhin co ve nen cho thang 40. **Khong.** Nua
   con lai cua ly do goc — wall-clock xau nhat cua 1 chunk va do min cua checkpoint resume —
   ap dung **manh hon**, khong yeu hon:
   - `ollama_thread` mac dinh la **2** (6.12.6), thap hon moi floor cloud (deepseek/openai 8).
     1 chunk 40 trang dac chu o thread 2 tren may user chinh la truong hop wall-clock xau nhat
     ton tai trong ca he thong. Che do nghen cua Ollama la **cham dan / swap / treo may**, va
     no khong co retry (S7) — nen chunk nho vua cat doi thiet hai 1 lan treo, vua cho resume
     nhieu diem tua hon. Con so 20 dung, chi la vi 1 ly do khac voi ly do goc.
   - Nhanh kill-switch la **duong rut lui an toan**: no duoc bat chinh xac vao luc AIMD bi
     nghi ngo. Chon gia tri bao thu o duong rut lui la dung dinh nghia cua duong rut lui.
   - Doi lai: 2 nhanh nay **khong bao gio** len 40. Chap nhan — chi phi la nhieu chunk hon
     (overhead khoi dong subprocess pdf2zh moi chunk), khong phai sai ket qua. Neu sau nay
     user Ollama phan anh cham, huong sua dung la 1 setting rieng (cung ho voi `ollama_thread`,
     do user dat theo phan cung cua ho), **khong** phai muon `ConcurrencyState` — vi van
     khong ton tai tin hieu nao de hoc (6.12.6).

```python
# src/core/job_orchestrator.py, step 6 (spec)
COLD_START_CHUNK_SIZE = 20
WARM_CHUNK_SIZE = 40

if job.chunk_size_used is None:                      # job chay lan dau
    # Cung 2 dieu kien, cung thu tu voi guard trong _resolve_thread() (6.12.6/6.12.8):
    # 2 nhanh nay khong duoc cham vao ConcurrencyState.
    if provider == "ollama" or not settings.adaptive_concurrency_enabled:
        job.chunk_size_used = COLD_START_CHUNK_SIZE
    else:
        state = await controller.get_state(provider, model, db_session)
        warm = state.observation_count >= 3 and state.consecutive_successes >= 3
        job.chunk_size_used = WARM_CHUNK_SIZE if warm else COLD_START_CHUNK_SIZE
    db_session.add(job)
    await db_session.commit()

chunk_plan = plan_chunks(
    job.total_pages, job.file_size, job.chunk_size_used, self._overlap
)
```

**Test bat buoc cho 2 nhanh nay** (`tests/integration/test_job_orchestrator_chunk_size_cold_start.py`):
job `ollama` va job voi `adaptive_concurrency_enabled=False` deu phai assert
`plan_chunks(..., 20, ...)` **va** — voi `ollama` — assert bang `concurrency_state` van rong
sau khi job xong. Assert thu hai moi la cai giu invariant; assert "= 20" mot minh van xanh
ke ca khi code lo doc state.

`self._chunk_size` (`__init__`, `job_orchestrator.py:165`) tro thanh gia tri **fallback cho
test injection**, khong con la nguon quyet dinh cho job that.

---

#### 6.12.8. Persistence — schema chot

`current_thread` la **learned runtime state**, khong phai user config. Chot: **bang rieng**,
KHONG dung `SETTINGS_DB_OVERRIDABLE_FIELDS`. Ly do:

- Bang `settings` hien tai (`src/models/settings.py`) la key/value `str -> str`, thiet ke cho
  overlay tren `Settings` cua pydantic (`config.py:88-104`). No ghi de **cau hinh do nguoi
  dat**. `current_thread` thi nguoc lai: app tu ghi, ghi lien tuc sau moi chunk, va nguoi
  dung khong nen sua tay (sua tay = xoa ket qua hoc duoc).
- No la state co **khoa ghep `(provider, model)`**, khong phai 1 gia tri toan cuc. Nhoi vao
  key/value string se phai encode khoa vao ten key va parse int tu string — dung kieu no ma
  6.11 da phai tra gia.
- Doi model (vd. `deepseek-chat` -> `deepseek-reasoner`) phai co state rieng, giong het
  pattern per-model da ap dung cho pricing trong `claude_provider.py`/`deepseek_provider.py`
  /`gemini_provider.py` (lookup theo `self._model`, khong hardcode 1 gia tri chung).

```python
# src/models/concurrency_state.py  (MOI)

from datetime import UTC, datetime
from sqlmodel import Field, SQLModel


class ConcurrencyState(SQLModel, table=True):
    """Muc `--thread` da hoc duoc cho 1 cap (provider, model). Architecture.md 6.12.

    Learned runtime state, KHONG phai user config: app tu ghi sau moi chunk.
    Khoa ghep (provider, model) — cung pattern per-model voi pricing lookup.
    """

    __tablename__ = "concurrency_state"

    #: `job.model` — provider identifier trong codebase nay, xem 6.12.4.1.
    provider: str = Field(primary_key=True)
    #: `service.service_arg`, vd. "deepseek:deepseek-chat" — xem 6.12.4.1.
    model: str = Field(primary_key=True)

    current_thread: int
    consecutive_successes: int = Field(default=0)
    observation_count: int = Field(default=0)

    #: Chan doan — doc tu chunk gan nhat, phuc vu UI/debug, khong tham gia thuat toan.
    last_outcome: str = Field(default="none")
    last_rate_limit_hits: int = Field(default=0)
    last_duration_seconds: float | None = Field(default=None)

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Cot moi tren bang `chunks`** (`src/models/chunk.py`) — bat buoc cho R6-02, vi khong co
chung thi test khong the assert lineage "thread nao da duoc dung cho chunk nao":

```python
thread_used: int | None = Field(default=None)
rate_limit_hits: int | None = Field(default=None)
```

**Cot moi tren bang `jobs`** (`src/models/job.py`): `chunk_size_used: int | None` (6.12.7).

**Settings moi** (`src/core/config.py`, `.env`-only tru ngoai le da neu):

```python
adaptive_concurrency_enabled: bool = True   # kill switch, KHONG vao DB overridable
ollama_thread: int = 2                      # NGOAI LE: CO vao SETTINGS_DB_OVERRIDABLE_FIELDS (6.12.6)
```

Khi `adaptive_concurrency_enabled = False`: dung `FLOOR[provider]` co dinh cho moi chunk,
khong doc, khong ghi `ConcurrencyState`. Day la duong lui an toan neu AIMD gay su co that.
Luu y no **van tot hon hien trang** vi floor deepseek/openai = 8 > mac dinh 4 cua pdf2zh.

Migration: `init_db()` (`src/models/database.py`) tao bang moi + 3 cot moi. DB hien tai la
SQLite dev, khong co du lieu production can bao ton -> `SQLModel.metadata.create_all` cho
bang moi, `ALTER TABLE ... ADD COLUMN` cho 3 cot (deu nullable, an toan).

---

#### 6.12.9. Data lineage tuong minh (Protocol 6 — R6-01)

Chuoi nay co 3 buoc noi tiep, moi buoc tieu thu artifact cua buoc truoc. Ghi ro artifact:

| Buoc | Sinh ra artifact | Buoc sau doc field/bien nao |
|---|---|---|
| 0. `_process_chunk()` xac dinh khoa | `provider = job.model`, `model_key = service.service_arg` (6.12.4.1) | Buoc 1 tra ca 2 gia tri nay vao `_resolve_thread(provider, model_key, ...)` |
| 1. `controller.get_state(provider, model)` | `ConcurrencyState.current_thread` (int, tu bang `concurrency_state`) | Buoc 2 doc **`state.current_thread`** — KHONG doc `Settings`, KHONG hardcode |
| 2. `_process_chunk()` -> `translate_pages(..., thread=state.current_thread)` | subprocess pdf2zh chay voi `--thread {state.current_thread}`; ghi `chunk.thread_used = state.current_thread` truoc khi goi | Buoc 3 doc **`Pdf2zhResult.stdout` + `.stderr`** (KHONG chi `.stderr` — xem 6.12.2 D1), hoac **`Pdf2zhTimeoutError.stdout/.stderr/.rate_limit_hits`** khi timeout |
| 3. `controller.observe(state, outcome, rate_limit_hits, duration)` | `ConcurrencyState.current_thread` (da cap nhat) da commit vao DB | Chunk **ke tiep** quay lai buoc 1 va doc chinh gia tri vua ghi |

**Diem de dut day nhat, Reviewer phai trace tay (R6-04):** `rate_limit_hits` o buoc 3 phai
duoc tinh tu **`result.stdout` hop nhat `result.stderr`** cua dung lan goi o buoc 2. Neu
Dev tinh no chi tu `result.stderr` (theo thoi quen tu code cu), gia tri se **luon bang 0** —
job van bao "completed", AIMD van chay, nhung no hoc tu tin hieu rong. Day dung la hinh thai
Bug #5: moi buoc rieng le deu dung, soi day noi giua chung thi dut.

**Test bat buoc (R6-02)** — phai assert **gia tri**, khong chi `assert_called()`:

```python
# 1. thread truyen xuong pdf2zh phai bat nguon tu state, khong phai hang so
state.current_thread = 12
await orchestrator._process_chunk(...)
pdf2zh_runner.translate_pages.assert_called_with(..., thread=12)

# 2. rate_limit_hits phai bat nguon tu STDOUT cua ket qua buoc truoc.
#    Fixture nay PHAI sinh tu golden file that (tests/fixtures/pdf2zh/...),
#    khong duoc viet tay 1 chuoi "RateLimitError" gia dinh (Protocol 5 muc 3).
runner.translate_pages.return_value = Pdf2zhResult(
    ..., stdout=GOLDEN_RATE_LIMITED_STDOUT, stderr="", rate_limit_hits=...,
)
await orchestrator._process_chunk(...)
assert state.current_thread == 6      # 12 -> x0.5, KHONG phai van la 12

# 3. Chong hoi quy truc tiep cho 6.12.2: tin hieu chi nam o stdout
runner.translate_pages.return_value = Pdf2zhResult(
    ..., stdout=GOLDEN_RATE_LIMITED_STDOUT, stderr="", ...
)
assert state.current_thread < 12      # FAIL neu Dev chi doc stderr
```

Test #3 la test quan trong nhat cua ca section: no la test duy nhat bat duoc dung loi
ma gia dinh ban dau cua thiet ke nay da mac phai.

---

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


### 6.14. `BabeldocRunner` — engine dich PDF thu hai, chay SONG SONG `Pdf2zhRunner`

> **Muc dich**: khac phuc known limitation v1.1.1 (gop dong danh sach + cat ngang tu giua chung
> cua `pdf2zh`, xem `docs/CHANGELOG.md` muc "Correction (2026-09-05) + Research babeldoc")
> **ma khong sua/xoa mot dong nao** cua `Pdf2zhRunner`. Engine duoc chon bang feature flag
> (6.14.7), mac dinh van la `pdf2zh` → rollback = doi 1 bien env.
>
> **Trang thai R5-01**: phan lon section nay **VERIFIED bang spike song Tech Lead tu chay
> trong luc thiet ke** tren `babeldoc` 0.6.4 **da cai that** tren may nay. Moi cau khong co
> trich dan la suy luan thiet ke CUA CHUNG TA tren nen su that do. Cac diem chua verify duoc
> deu mang nhan `⚠️ ASSUMED` tuong minh.

#### 6.14.1. Nguon xac thuc (Protocol 5 R5-01)

Duong dan package da cai:
`~/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/` (goi tat `$BD`),
entrypoint `~/.local/bin/babeldoc`.

| # | Nguon | Xac nhan dieu gi |
|---|-------|------------------|
| B1 | Chay `babeldoc --version` → `babeldoc 0.6.4`; `ls ~/.local/share/uv/tools/` → `babeldoc`, `mineru`, `pdf2zh` | babeldoc 0.6.4 **da cai san** tren may dich, venv **rieng** Python 3.12, tach hoan toan khoi venv `pdf2zh` va `.venv` cua project (dung ket luan CHANGELOG: khong dung chung venv) |
| B2 | `$BD/translator/translator.py:203-238` — `class OpenAITranslator(BaseTranslator)`, `__init__(..., base_url=None, api_key=None, ...)` → `self.client = openai.OpenAI(base_url=base_url, api_key=api_key, http_client=httpx.Client(limits=..., timeout=600))` | Moi provider OpenAI-compat (Gemini, Ollama, DeepSeek, Claude qua compat layer) di **cung mot duong**: chi la `base_url` + `api_key`. **KHONG truyen `max_retries`** |
| B3 | Chay `~/.local/share/uv/tools/babeldoc/bin/python -c "import openai; print(openai.__version__, openai.DEFAULT_MAX_RETRIES)"` → `3.8.0 2` | SDK `openai` trong chinh venv babeldoc dang dung `DEFAULT_MAX_RETRIES = 2` → **moi request tu retry ngam toi da 2 lan** truoc khi exception thoat ra toi tenacity. Day la goc cua van de undercount (6.14.5) |
| B4 | `$BD/translator/translator.py:265-269` va `:297-301` — `@retry(retry=retry_if_exception_type(openai.RateLimitError), stop=stop_after_attempt(100), wait=wait_exponential(multiplier=1, min=1, max=15), before_sleep=before_sleep_log(logger, logging.WARNING))` tren `do_translate()` va `do_llm_translate()` | Tin hieu rate-limit di qua `logging` chuan (logger `babeldoc.translator.translator`), format do chinh `tenacity` so huu — on dinh, khong phai babeldoc tu che |
| B5 | `$BD/main.py:404-411` (`--openai-base-url`, `--openai-api-key/-k`); `$BD/main.py:512-517` (`OpenAITranslator(lang_in=..., model=args.openai_model, base_url=args.openai_base_url, api_key=args.openai_api_key, ...)`) | Duong noi CLI → client la truc tiep, khong co lop bien doi/validate URL nao o giua |
| B6 | **Spike song 1** (Tech Lead chay 2026-09-05): dung `http.server.ThreadingHTTPServer` gia lam OpenAI-compat tren `127.0.0.1:18899`, chay `babeldoc --files <Figoni ...-1-25.pdf> --pages 14 --openai --openai-base-url http://127.0.0.1:18899/v1 --openai-api-key fake-key --openai-model fake-model -li en -lo vi ...` → exit 0, server nhan **52 request**, tat ca vao `POST /v1/chat/completions`, header `Authorization: Bearer fake-key` | **Verified song**: babeldoc goi dung endpoint OpenAI chuan tren base_url tuy y, key truyen qua Bearer header. Day chinh xac la shape ma Ollama (`/v1`) va Gemini (`/v1beta/openai/`) yeu cau |
| B7 | Cung spike B6, `ls` thu muc `--output` | Ten file output: `{stem}.no_watermark.vi.mono.pdf` va `{stem}.no_watermark.vi.dual.pdf` — **khac** pattern `{stem}-mono.pdf` ma `Pdf2zhRunner` hardcode |
| B8 | Cung spike B6: mono output co **25 trang** (ca tai lieu) du chi `--pages 14`. Chay lai them `--only-include-translated-page` → mono output con **1 trang** | Mac dinh babeldoc **giu ca tai lieu**; neu khong bat co nay, `merge_chunk_pdfs()` se noi N ban sao ca cuon sach. Day la bay lineage nghiem trong nhat khi thay engine |
| B9 | Cung spike B6, phan loai 52 request bat duoc: **4** request mang prompt `"You are an expert multilingual terminologist..."`, 48 request dich | babeldoc **tu dong goi LLM them** de trich thuat ngu (auto glossary) — chi phi nay khong nam trong `estimate_chunk_cost()` hien tai. Co tat: `--no-auto-extract-glossary` (help dong 173-175) |
| B10 | **Spike song 2** (rate-limit that, qua CLI babeldoc thuc): server gia tra HTTP 429 cho 40 request dau roi 200, chay lai voi `--ignore-cache` → **12 dong WARNING tenacity tren STDOUT, 0 tren STDERR**; exit 0 | (a) tin hieu rate-limit **co that va dem duoc** qua CLI that (khong chi qua script co lap nhu research truoc); (b) nam o **stdout**, giong het phat hien 6.12.2 D1 cho pdf2zh; (c) **40 lan 429 that → 12 dong log** = ty le undercount **≈ 3.3x**, khop dung ly thuyet `1 + DEFAULT_MAX_RETRIES = 3` (B3) |
| B11 | Cung spike B10, doc dong log that (da chay voi `COLUMNS=200`): `WARNING:babeldoc.translator.translator:Retrying babeldoc.translator.translator.OpenAITranslator.do_llm_translate in 1 seconds as it raised` **[xuong dong]** `RateLimitError: Error code: 429 - {...}`. `grep -c "as it raised RateLimitError:"` → **0**; `grep -c "RateLimitError"` → **12** (dung 1 lan/canh bao) | **CORRECTION doi voi research trong CHANGELOG**: chuoi `"as it raised RateLimitError:"` ma research truoc de xuat grep **KHONG khop** khi chay qua CLI that, vi `RichHandler` cua babeldoc (`main.py:920`) van wrap dong ngay ca o `COLUMNS=200` (con cot `before_sleep.py:64` ben phai). **`RATE_LIMIT_LINE_RE = re.compile(r"RateLimitError")` hien co dung nguyen xi la dung** — bai hoc y het 6.12.2 (chi neo vao token, khong neo vao cum tu) |
| B12 | `babeldoc --help` (ban 0.6.4 da cai), cac dong: `--pages/-p`, `--output/-o`, `--qps/-q`, `--ignore-cache`, `--no-dual`, `--no-mono`, `--lang-in/-li`, `--lang-out/-lo`, `--split-short-lines`, `--short-line-split-factor`, `--watermark-output-mode {watermarked,no_watermark,both}`, `--skip-scanned-detection`, `--custom-system-prompt`, `--only-include-translated-page`, `--no-auto-extract-glossary`, `--glossary-files`, `--pool-max-workers`, `--term-pool-max-workers` | Bang doi chieu flag 6.14.2. Dac biet `--pool-max-workers`: help ghi *"Maximum number of worker threads... If not specified, defaults to QPS value. This parameter directly sets the worker count, replacing previous QPS-based dynamic calculations"* → **day** moi la doi ung 1-1 cua `pdf2zh --thread`, **khong phai `--qps`** nhu bang so sanh trong CHANGELOG ghi |
| B13 | `$BD/main.py:718,723,727,740` — `custom_system_prompt=args.custom_system_prompt`, `pool_max_workers=args.pool_max_workers`, `only_include_translated_page=...`, `term_pool_max_workers=...` | Cac flag tren duoc forward that vao config, khong phai flag chet |
| B14 | Doc chinh thuc Gemini (WebFetch `https://ai.google.dev/gemini-api/docs/openai`, 2026-09-05) | base_url OpenAI-compat cua Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/`, key qua `Authorization: Bearer $GEMINI_API_KEY` — **khop dung** shape ma B6 da chung minh babeldoc phat ra |

**Nhung gi KHONG verify duoc (⚠️ ASSUMED — Dev/QA phai tu kiem tra truoc khi dua vao):**

- ⚠️ **ASSUMED**: goi Gemini that qua `--openai-base-url https://generativelanguage.googleapis.com/v1beta/openai/` chay duoc **end-to-end**. Da verify: shape client cua babeldoc (B2/B5/B6) khop shape Gemini yeu cau (B14). **Chua verify**: khong co `GEMINI_API_KEY` that trong `.env` (dong `GEMINI_API_KEY=` rong) → khong the goi that. Rui ro con lai giong het 6.12.6: neu Gemini tra 429 voi body/status ma SDK `openai` khong phan loai thanh `openai.RateLimitError`, tenacity khong bat, **`rate_limit_hits` = 0 vinh vien**.
- ⚠️ **ASSUMED**: Ollama qua `http://localhost:11434/v1`. **Khong verify duoc**: `which ollama` → khong tim thay, Ollama **chua cai** tren may nay. Ve mat thiet ke B6 da chung minh babeldoc goi duoc bat ky host OpenAI-compat nao, va Ollama co endpoint `/v1` — nhung **khong** duoc coi la verified. Ngoai ra 6.12.6 da chot Ollama **khong dung AIMD**; ket luan do giu nguyen cho babeldoc, va con manh hon: Ollama local khong sinh 429 nen `openai.RateLimitError` gan nhu khong bao gio xay ra.
- ⚠️ **ASSUMED**: `--no-auto-extract-glossary` thuc su **cat het** 4 request term-extraction. Da verify flag ton tai va duoc chap nhan (exit 0). **Chua do lai duoc so request** vi lan chay thu hai an **cache dich cua chinh babeldoc** (0 request moi toi server gia) — mot phat hien phu dang luu: babeldoc co cache ben ngoai giong pdf2zh, muon do lai phai them `--ignore-cache`.
- ⚠️ **ASSUMED**: chat luong dich that (31/35 muc xuong dong dung) tai hien duoc trong pipeline cua app. So do den tu research CHANGELOG chay babeldoc **bang tay**, chua chay qua `JobOrchestrator`. QA gate 6.14.6 ton tai chinh de dong khoang trong nay.

---

#### 6.14.2. Bang doi chieu flag `Pdf2zhRunner` → `BabeldocRunner`

| Khai niem trong `translate_pages()` | pdf2zh (hien tai) | babeldoc 0.6.4 (nguon B12/B13) |
|---|---|---|
| file dau vao | positional `<input>` | `--files <input>` |
| khoang trang | `--pages 1-40` | `--pages 1-40` (giong) |
| thu muc ra | `--output <dir>` | `--output <dir>` (giong) |
| ngon ngu | `-li en -lo vi` | `-li en -lo vi` (giong) |
| chon provider | `-s <service_arg>` + env | `--openai --openai-base-url <url> --openai-api-key <key> --openai-model <model>` |
| so luong (concurrency) | `--thread N` | `--pool-max-workers N` (**khong** phai `--qps`) |
| bo cache | `--ignore-cache` | `--ignore-cache` (giong) |
| prompt/glossary | `--prompt <file>` | `--custom-system-prompt "<chuoi>"` — **nhan chuoi, khong nhan duong dan file** |
| — | (khong co) | `--watermark-output-mode no_watermark` — **bat buoc luon truyen**, mac dinh cua babeldoc la `watermarked` |
| — | (khong co) | `--only-include-translated-page` — **bat buoc luon truyen** (B8) |
| — | (khong co) | `--no-auto-extract-glossary` — **bat buoc luon truyen** (B9, an toan chi phi 6.11) |
| — | (khong co) | `--skip-scanned-detection` — **bat buoc luon truyen**, tranh `ScannedPDFError` tren nhanh `pdf_scan` (cau noi searchable PDF 6.10 co the van "trong nhu scan") |
| — | (khong co) | `--split-short-lines` — **ly do ton tai cua ca section nay** (0/35 → 31/35 muc danh sach xuong dong dung) |
| ten file ra | `{stem}-mono.pdf` / `{stem}-dual.pdf` | `{stem}.no_watermark.{lang_out}.mono.pdf` / `...dual.pdf` (B7) |

**Chuyen doi `prompt_file` → `--custom-system-prompt`**: `BabeldocRunner` doc noi dung
`prompt_file` (file glossary/unit-rule sinh boi 6.2/6.5, khong doi gi o phia sinh) va truyen
**noi dung** vao `--custom-system-prompt`. Neu `prompt_file is None` thi bo qua flag. Khong tai
su dung `--glossary-files` cua babeldoc o v1.2: no la duong glossary **thu hai** voi format CSV
rieng, dung se tao 2 nguon su that cho glossary — ghi lai lam huong toi uu tuong lai, khong lam
bay gio.

---

#### 6.14.3. Interface `BabeldocRunner` (spec cho Dev)

File moi: `src/services/babeldoc_runner.py`. **Khong sua** `src/services/pdf2zh_runner.py`.

Nguyen tac: **cung shape voi `Pdf2zhRunner`** de `job_orchestrator._process_chunk()` doi engine
ma khong doi logic goi — cung ten tham so keyword, cung kieu tra ve, cung 2 kieu exception.

```python
@dataclass
class BabeldocResult:
    success: bool
    mono_path: Path
    dual_path: Path | None
    stderr: str
    duration_seconds: float
    stdout: str = ""
    rate_limit_hits: int = 0          # dem THO tu log (xem 6.14.5)


class BabeldocError(RuntimeError): ...      # cung shape Pdf2zhError
class BabeldocTimeoutError(RuntimeError): ...  # cung shape Pdf2zhTimeoutError


class BabeldocRunner:
    def __init__(self, executable: str = "babeldoc") -> None: ...

    async def translate_pages(
        self,
        input_path: Path,
        output_dir: Path,
        page_range: str,
        service: Pdf2zhService,     # tai dung nguyen, xem ghi chu duoi
        prompt_file: Path | None = None,
        lang_in: str = "en",
        lang_out: str = "vi",
        ignore_cache: bool = False,
        timeout_seconds: int = 3600,
        thread: int = 4,            # → --pool-max-workers
    ) -> BabeldocResult: ...
```

**Chu y `service: Pdf2zhService`**: v1.2 tai dung nguyen `Pdf2zhServiceMapper` (khong sua) —
`BabeldocRunner` chi doc `service.envs` de lay `OPENAI_BASE_URL` / api key / model roi dich sang
3 flag `--openai-*`. Ly do: mapper hien tai da chua toan bo tri thuc "provider nao dung
base_url/model nao" va da qua review; nhan them mot bang mapping thu hai la moi truong sinh loi
lech pha. Neu mot provider khong dien duoc thanh bo 3 `--openai-*` → raise
`UnsupportedForPdfPipelineError` **truoc khi** spawn subprocess (fail nhanh, giong DeepL o 6.6.1 F7).

Phan than ham **tai su dung nguyen ky thuat da chung minh cua `Pdf2zhRunner`**, khong sang tao lai:
`asyncio.create_subprocess_exec` + 2 task `_drain` + `asyncio.wait_for` + kill khi timeout +
mop-up 5s (6.12.3), va `env = {**os.environ, **service.envs, "COLUMNS": "200"}`.

**`rate_limit_hits` map the nao** (day la cau tra loi cho yeu cau 1 cua brief):

```python
rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))
```

— **dung lai `RATE_LIMIT_LINE_RE` hien co, khong viet regex moi**. Co so: B10 + B11 chung minh
song rang qua CLI babeldoc that, moi lan tenacity `before_sleep_log` bao rate-limit sinh **dung 1**
token `RateLimitError` tren **stdout** (12 canh bao → 12 khop), va cum tu day du bi `rich` cat
dong nen moi regex "chinh xac hon" deu se sai. Y nghia con so nay **da doi ban chat** so voi
pdf2zh — xem 6.14.5, day khong phai chi tiet phu.

**Doc output**: `mono_path = output_dir / f"{input_path.stem}.no_watermark.{lang_out}.mono.pdf"`
(B7). `dual_path` tuong tu voi `.dual.pdf`, tra `None` neu khong ton tai. Dev **phai** kem 1 test
khang dinh pattern nay tren golden listing capture tu spike that (Protocol 5 muc 3), khong viet tay.

---

#### 6.14.4. Data lineage (Protocol 6 — R6-01)

`BabeldocRunner` cam vao **dung mot cho** ma `Pdf2zhRunner` dang cam: ham noi bo
`_call_pdf2zh()` trong `_process_chunk()` (`src/core/job_orchestrator.py`, hien ~dong 663-673).
Khong them buoc moi, khong doi thu tu pipeline, khong dung toi 6.10.

**Artifact vao (bat buoc, chong tai dien Bug #5):** bien `source_path` — chinh la
`translation_source_path` do `run_job()` tinh o Step 2 (`job_orchestrator.py:235-238`):

| `job.file_type` | `translation_source_path` | Nguon |
|---|---|---|
| `pdf_digital` | `file_path` (file goc) | `job_orchestrator.py:235` |
| `pdf_scan` | `<processing>/<job.id>/ocr_bridge/searchable.pdf` do `build_searchable_pdf()` tao **tu `ocr_result.middle_json_path`** | 6.10.3 / `job_orchestrator.py:512-533` |

**Bat buoc**: `BabeldocRunner.translate_pages(input_path=source_path, ...)` — **tuyet doi khong**
doc lai `job.file_path` ben trong nhanh babeldoc. Day dung la sai lam cua Bug #5, va vi day la
duong code moi nen no co the tai sinh y nguyen neu Dev copy nham.

**Artifact ra:** `BabeldocResult.mono_path` → gan vao `chunk.output_path` → tieu thu boi
`font_shrink_page()` → `merge_chunk_pdfs(chunks, merged_path)` → guard BR-OCR-03 (6.10.5) →
`create_bilingual_pdf(merged_path, file_path_goc, ...)`. **Khong doi mot buoc nao** o day.

Guard BR-OCR-03 (`job_orchestrator.py:436-439` — "ban dich khong chua chu nao") **van la tuyen
phong thu cuoi cho ca hai engine**; Dev chi sua cau chu thong bao loi de neu ten engine dang dung,
khong duoc noi long dieu kien.

**Diem lineage rieng cua babeldoc, khong co o pdf2zh** (B8): neu thieu
`--only-include-translated-page`, `mono_path` chua **ca tai lieu** thay vi rieng khoang trang cua
chunk → `merge_chunk_pdfs()` van chay "thanh cong" va sinh file dai gap N lan, chua trang trung
lap chua dich. Day la **silent failure dung kieu Bug #5** (status `completed`, noi dung sai).
=> `--only-include-translated-page` la **flag bat buoc, hardcode trong runner, khong de tuy chon**,
va R6-02 test phai khang dinh so trang cua `mono_path` bang `page_end - page_start + 1`.

**Test bat buoc (R6-02)** — khong chap nhan `assert_awaited()` tran:

```python
babeldoc_runner.translate_pages.assert_called_with(
    input_path=translation_source_path,   # KHONG phai job.file_path
    ...
)
```
voi `translation_source_path` la file cau noi sinh tu `ocr_result` khi
`job.file_type == PDF_SCAN` — y het rang buoc da ap cho `pdf2zh_runner` (6.10.5).

---

#### 6.14.5. AIMD cho tin hieu babeldoc — floor/ceiling hieu chinh

**Van de**: `rate_limit_hits` cua babeldoc **khong cung don vi** voi cua pdf2zh.

- pdf2zh: 1 hit = 1 lan HTTP 429 that (khong co lop retry ngam nao ben duoi).
- babeldoc: SDK `openai` tu retry 2 lan truoc khi exception toi tenacity (B3), nen
  1 hit = **1 chuoi ~3 lan 429 lien tiep tren cung 1 request**.

**Do duoc that, khong phai suy dien** (B10): ep 40 lan 429 → dem duoc 12 hit. Ty le
40/12 = 3.33, khop `1 + DEFAULT_MAX_RETRIES = 3` cong them nhieu lan 429 rai rac chua du 3 lan
lien tiep tren cung request nen bi nuot han.

**Chot thiet ke — hieu chinh o tang *y nghia tin hieu*, khong o tang thuat toan.**
Khong sua `next_thread_count()` (AIMD +2 / x0.5 giu nguyen — no da dung, chi la dau vao doi don vi).
Chi sua **nguong coi la rate-limited** va **floor**, qua 2 hang so moi:

```python
#: So lan 429 that ma SDK openai nuot ngam truoc khi tenacity thay exception.
#: Do that: 40 lan 429 ep buoc -> 12 dong log (Architecture.md 6.14.1 B10).
BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR = 3

#: Floor rieng cho engine babeldoc = ceil(floor_pdf2zh / 2). Xem lap luan duoi.
BABELDOC_THREAD_FLOOR: dict[str, int] = {
    "deepseek": 4,
    "openai": 4,
    "gemini": 2,
    "claude": 4,
}
```

**1. Nguong "coi la rate-limited": giu `rate_limit_hits >= 1`, KHONG ha them.**
Day la diem de doan nguoc. Vi tin hieu bi undercount, 1 hit cua babeldoc da la bang chung
**manh hon** 1 hit cua pdf2zh (no dai dien ~3 lan 429 that), chu khong yeu hon. Ha nguong xuong
duoi 1 la vo nghia (khong co gia tri nao duoi 1). Cai bi mat la **do nhay**: cac dot rate-limit
nhe (1-2 lan 429 le te) bi SDK nuot sach, controller **khong bao gio thay**. Bu cho do nhay bi
mat khong lam bang cach ha nguong (khong the), ma lam bang cach **ha diem xuat phat** — muc 2.

**2. Floor: `ceil(floor_hien_tai / 2)` cho moi provider.**
Ly do chon so: floor hien tai (6.12.5) duoc bien minh bang lap luan "AIMD se cat xuong ngay chunk
sau neu doan sai". Voi babeldoc, **gia thiet do yeu di dung 1 buoc**: cac dot rate-limit nhe khong
tao tin hieu, nen viec cat xuong den muon hon. Chia doi floor dua he thong ve dung so lan cat
(x0.5) ma AIMD can de tu ve toi floor cu — tuc **danh doi dung 1 vong quan sat** de doi lay an
toan, dung logic beta=0.5 da chon o 6.12.4. Khong chon `floor / 3` (dung theo he so undercount)
vi he so 3 do luong **so 429 bi nuot**, khong phai **so luong an toan** — dung no de chia thread la
lan lon 2 dai luong khac nhau; va floor 2-3 cho deepseek se lam job cham dang ke ma khong co bang
chung nao noi rang can den muc do.

**3. Ceiling: giu nguyen `ADAPTIVE_THREAD_CEILING = 32`, dung chung.**
Lap luan 6.12.5 (tran do **chi phi + bo nho cua chinh app** quyet dinh, khong phai quota provider)
khong phu thuoc engine → khong co ly do doi.

**4. Ollama: khong AIMD, giu nguyen 6.12.6.** Dung `settings.ollama_thread` co dinh cho ca
`--pool-max-workers`. Ly do con manh hon voi babeldoc: Ollama local khong tra 429 nen
`openai.RateLimitError` gan nhu khong bao gio xuat hien → AIMD se leo mai toi tran roi treo may.

**5. Claude: AIMD van TAT** (6.12.6 chua co spike xanh). Thread co dinh = `BABELDOC_THREAD_FLOOR["claude"]` = 4.

> ⚠️ **ASSUMED — can tune them bang du lieu that o QA gate (6.14.6).**
> He so 3 (B10) do duoc tren **server gia 429 100%**, la truong hop cuc doan; ty le nuot voi
> rate-limit that cua provider that (rai rac, xen ke thanh cong) **chac chan khac** va nhieu kha
> nang **cao hon 3** (cang rai rac cang de bi nuot han). Con so floor `/2` la lua chon **bao thu
> co chu dich**, khong phai ket qua do dac. QA phai ghi lai `rate_limit_hits` that + tong thoi
> gian chunk cua ca 2 engine tren cung file (6.14.6) va bao cao ve Tech Lead truoc khi coi cac
> hang so nay la da chot.

**Persistence**: `ConcurrencyState` (6.12.8) key theo `(provider, model_key)`. Vi y nghia 1 hit
da doi, **state hoc duoc tu engine nay khong duoc dung cho engine kia**. Chot: them `engine` vao
key → `(engine, provider, model_key)`, gia tri `"pdf2zh"` cho moi ban ghi cu (migration mac dinh).
Neu khong lam, doi flag sang babeldoc se ke thua `current_thread` hoc bang tin hieu khac don vi —
dung kieu loi im lang ma Protocol 6 sinh ra de chan.

---

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
(nguong goc xoay `il_creater.py:968-974`, thu tu "gian truoc bop sau" cua `typesetting.py`) —
doi version ma khong biet la doi silent, co the lam sai lech moi ket luan da verify. Repo nay
chua co script/CI tu dong hoa viec cai `babeldoc` (khong tim thay trong README, script setup,
hay Dockerfile — xem `docker/Dockerfile` va `docs/Architecture.md` section 7 cho danh sach day
du cac buoc cai dat thu cong); day la lenh huong dan THU CONG duy nhat, nen viec pin o day la
đủ cho toan bo project (khong can them file cai dat rieng). Neu sau nay them script tu dong
hoa (CI, Dockerfile), phai pin cung dung `==0.6.4` o do, khong duoc de mac dinh "latest".

---

#### 6.14.7. Feature flag — chon engine, rollback tuc thoi

Them vao `src/core/config.py` (`class Settings`, canh cac field pipeline PDF):

```python
    # Engine dich PDF (Architecture.md 6.14). "pdf2zh" = duong da release v1.1.1,
    # KHONG doi. "babeldoc" = duong moi, sua loi gop dong danh sach (known
    # limitation v1.1.1). `.env`-only, KHONG vao SETTINGS_DB_OVERRIDABLE_FIELDS:
    # doi engine giua chung khong phai thao tac user thuong lam tu UI, va rollback
    # phai la 1 thao tac co chu dich (sua .env + restart), khong phai 1 cu click.
    pdf_translate_engine: Literal["pdf2zh", "babeldoc"] = "pdf2zh"
    babeldoc_executable: str = "babeldoc"
```

Env var tuong ung: `PDF_TRANSLATE_ENGINE=pdf2zh|babeldoc`, `BABELDOC_EXECUTABLE=...`
(theo dung convention pydantic-settings hien co: ten field viet hoa).

**Mac dinh `pdf2zh`** — cho toi khi QA gate 6.14.6 xanh. Doi mac dinh sang `babeldoc` la 1 quyet
dinh rieng, can nguoi duyet (Protocol 2), khong duoc gop vao increment implement.

**Diem chon engine** — dung **1 cho duy nhat**, trong `JobOrchestrator.__init__`:

```python
self._translator_runner = (
    BabeldocRunner(executable=settings.babeldoc_executable)
    if settings.pdf_translate_engine == "babeldoc"
    else self._pdf2zh_runner
)
```

`_process_chunk()` goi `self._translator_runner.translate_pages(...)` — **cung mot loi goi cho ca
2 engine**, khong co `if` nao rai rac trong than ham. Ly do: moi `if engine == ...` nam ben trong
pipeline la 1 co hoi de nhanh nay lech khoi nhanh kia (dung kieu Bug #5). `self._pdf2zh_runner`
giu nguyen ten va van ton tai — code cu khong bi dong toi.

**Rollback**: doi `PDF_TRANSLATE_ENGINE` ve `pdf2zh` + restart. Khong co migration DB nao can
undo (truong `engine` trong key `ConcurrencyState` 6.14.5 chi them ban ghi moi, khong sua ban ghi cu).

---

### 6.15. US-15 — Markdown parse-only: rà soát §6.8 so với code hiện tại (2026-09-08)

§6.8 được viết ở thời điểm trước AIMD (6.12), trước babeldoc (6.14), trước cầu nối OCR (6.10) và
trước Cost Safety (6.11). Mục này ghi rõ phần nào còn dùng được, phần nào phải sửa.

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

#### 6.15.3. Phần PHẢI SỬA (spec cho Dev)

**S15-1 — Thứ tự rẽ nhánh trong `run_job()`.** Hiện Step 1 reject EPUB trước tất cả. Một job
`parse_only` trên file EPUB sẽ chết ở Step 1 dù nhánh parse-only chẳng liên quan gì tới
`bilingual_book_maker`. **Rẽ theo `job.job_type` TRƯỚC, rồi mới rẽ theo `file_type`**:

```
run_job(job_id):
    if job.job_type == "parse_only":
        return await self.run_parse_only(job, db_session)   # nhánh MỚI, độc lập
    # ... Step 1..10 hiện tại giữ nguyên cho job_type == "translate"
```

`run_parse_only()` là **hàm riêng**, không nhồi `if job_type == ...` rải rác vào Step 1-10 —
cùng lý do §6.14.7 nêu cho việc chọn engine: mỗi chỗ rẽ nhánh nằm bên trong pipeline là 1 cơ hội
để 2 nhánh lệch nhau (đúng kiểu Bug #5).

**S15-2 — Bỏ `_mark_parse_only_unsupported()`** (`src/api/routes/jobs.py`) và cho `parse_only` đi
tiếp `status="queued"` + `_schedule_background()` như job translate. Cost gate vẫn skip (code hiện
tại đã đúng: `if request.job_type == "translate"`).

> **MỞ RỘNG sau phản biện Domain Expert (2026-09-08) — S15-2 bản gốc chỉ nêu `create_job`, THIẾU
> 2 call site khác.** Đã tự đối chiếu code, xác nhận Expert đúng ở cả hai:
> - `create_batch` (`src/api/routes/jobs.py:889-891` gọi `_mark_parse_only_unsupported(job)` cho
>   từng job; `:899-907` đánh cả batch `failed` + `failed_files = len(parse_only_jobs)`). Nếu Dev
>   chỉ sửa `create_job`, **batch parse_only vẫn chết**. Phải: bỏ cả 2 chỗ, và
>   `_schedule_background(_run_batch_background(batch.id))` chạy cho **cả hai** `job_type` (hiện
>   đang gate `if request.job_type == "translate"`).
> - `retry_job` (`:585-586`: `if job.job_type == "parse_only": raise HTTPException(400, …)`) —
>   xem S15-11.

**S15-3 (SỬA SAU PHẢN BIỆN DOMAIN EXPERT 2026-09-08) — Download phải là ZIP, và ZIP tạo EAGER
trong `run_parse_only()`, KHÔNG lazily trong `download.py`.** Bản gốc của S15-3 ghi "nén
`Path(job.output_path).parent` thành ZIP, tạo lazily lần tải đầu, cache lại". **Bác bỏ chính
mình** — 3 lý do của Expert đều đúng và tôi không có phản biện nào:
1. Tạo artifact trong request handler nằm **ngoài** bảng lineage §6.15.4 và **ngoài** guard S15-5:
   job đã `completed` rồi mà tải về vẫn có thể fail (thư mục `images/` bị xoá tay, đĩa đầy) — đúng
   shape "báo xong, output không dùng được" của Bug #5, chỉ dời từ bước dịch sang bước tải.
2. Cache zip nằm **trong chính thư mục bị nén** (`data/outputs/{job_id}/`) → lần dựng lại sẽ nén
   `parse_result.zip` vào chính nó.
3. Crash giữa lúc ghi để lại zip cụt, `exists()` vẫn `True` → serve file hỏng mãi mãi.

**Bản chốt:**
- `run_parse_only()` **tự đóng gói** sau guard S15-5:
  `data/outputs/{job_id}/parse_result.zip` (`zipfile.ZIP_DEFLATED`), ghi theo **danh sách file
  tường minh** (`document.md` + từng file trong `images/`), **không** `os.walk` thư mục — walk là
  đường duy nhất khiến zip tự nén chính nó.
- Ghi ra `parse_result.zip.tmp` rồi `os.replace()` → không bao giờ tồn tại zip dở mang tên thật.
- `download.py` **không biết gì về `parse_only`**: chỉ (a) suy `media_type` từ `result_path.suffix`
  (`{".pdf": "application/pdf", ".zip": "application/zip", ".epub": "application/epub+zip"}`, mặc
  định `application/octet-stream`) — thay cho hardcode `application/pdf` (P-05, xác nhận lại tại
  `src/api/routes/download.py:61`), và (b) đặt tên `{stem}_markdown_{timestamp}.zip` cho job
  `parse_only` (giữ nguyên pattern `_vi`/`_bilingual` + timestamp `:52-60`).
- UI: `web/index.html:134` ("Tải bản VI") và `web/history.html:59` ("Tải VI") rẽ theo `job_type`
  → "Tải Markdown (.zip)"; **ẩn** link bản song ngữ cho job parse_only.

**S15-4 (SỬA cùng S15-3) — `job.output_path` cho parse_only trỏ tới
`data/outputs/{job_id}/parse_result.zip`** (file `.zip`, KHÔNG phải `.md`, KHÔNG phải thư mục).
Lý do đổi so với bản gốc: `output_path` là thứ `download.py` trả thẳng cho user — nó phải trỏ tới
**artifact đã hoàn chỉnh và đã được guard**, không phải một mảnh của nó. Consumer nào cần chính
file `.md` (preview sau này, §6.18 US-20 — xem lineage đã sửa ở §6.18.5) derive bằng
`Path(job.output_path).parent / "document.md"`. `DELETE /api/jobs/{id}` vẫn dọn theo thư mục
`data/outputs/{job_id}` như cũ, không phải học khái niệm mới.

**S15-5 — Guard "không im lặng ra file rỗng"** (bản sao tinh thần BR-OCR-03): sau khi MinerU trả
về, nếu `document.md` có 0 ký tự (sau `.strip()`) → job `failed` với thông báo rõ, KHÔNG báo
`completed`. Đây chính xác là kịch bản Bug #5 áp cho nhánh parse.

**S15-6 (VIẾT LẠI — bản gốc SAI, sửa sau phản biện Domain Expert 2026-09-08) — `ocr_confidence`
cho parse_only rẽ theo `file_type`, KHÔNG theo giá trị runner trả về.**

Bản gốc viết: *"`parse_method="txt"` (born-digital) → MinerU không chạy OCR → `quality.confidence
is None` → ghi NULL"*. **Sai với dữ liệu thật.** Expert tự chạy `MinerURunner` thật ở `txt` mode
trên chính file Figoni 1-25 trang: `confidence = 0.9976`, `ocr_span_count = 1004`, 998/1004 span
có `score == 1.0` (chi tiết + nguồn: xem hộp "SỬA SAU PHẢN BIỆN" ở §6.9.5). Đây đúng lớp lỗi
Protocol 5 mà project đã dính 2 lần: contract được suy ra cho **một mode chưa từng có dữ liệu
thật** (§6.9 chỉ từng được verify ở `ocr` mode) rồi viết vào tài liệu như sự thật.

Bản chốt cho `run_parse_only()`:

| `job.file_type` | `parse_method` | `jobs.ocr_confidence` / `ocr_dropped_spans` | Cảnh báo US-11 |
|---|---|---|---|
| `pdf_digital` | `txt` | **ép `None` bất kể `quality.confidence` trả về gì** | **không** gọi `_emit_ocr_warning_if_low()` |
| `pdf_scan` | `ocr` | ghi giá trị thật từ `quality` | có, tái dùng `_emit_ocr_warning_if_low()` |

Lý do ép `None` thay vì ghi 0.9976: cột `jobs.ocr_confidence` có **một** ngữ nghĩa duy nhất trong
toàn app — "độ tin cậy của bước OCR" — và nó được hiển thị nguyên trạng lên `JobDetail`
(`src/api/routes/jobs.py:240`). Ghi vào đó một con số **không đến từ OCR** là đúng loại "cùng một
biến, hai ý nghĩa" đã sinh ra Bug #5 và nhầm lẫn `cost_source` ở RC-4.

**Test bắt buộc (Protocol 5 mục 3 — golden file, không mock viết tay)**: fixture sinh từ chính
run thật của Expert (`middle.json` 998 span `score=1.0`, lưu vào
`tests/fixtures/mineru/parse_only_txt_figoni25/`), assert `run_parse_only()` ghi `ocr_confidence
IS NULL` **dù runner trả 0.9976**. Test mà mock runner trả `None` sẽ pass một cách vô nghĩa —
đúng loại "mock tự nhất quán với giả định sai" mà Protocol 5 tồn tại để chặn.

**S15-7 — BR-PARSE-04 ("không tính vào translation history").** KHÔNG tạo bảng riêng. `GET /api/jobs`
thêm query param `job_type` (optional, cùng kiểu lọc như `status` đang có); tab Lịch sử mặc định
lọc `job_type=translate`, khu vực parse hiển thị `job_type=parse_only`. Lý do: tách bảng nghĩa là
nhân đôi mọi thứ đã có (progress, cancel, delete, WebSocket) cho một khác biệt thuần trình bày.

**S15-8 (VIẾT LẠI — sửa sau phản biện Domain Expert 2026-09-08) — Nhánh EPUB: MỘT loader dùng
chung, HAI projection riêng.**

Bản gốc viết: tái dùng **`EpubDocument.units`** rồi `units_to_markdown()`. **Expert bác bỏ cách
làm này và tôi chấp nhận hoàn toàn** — kèm số đo trên chính EPUB thật của user
(`ops/xhtml/chapter01.html`, 97,4% nội dung cuốn sách):

| Thành phần XHTML nguồn | Có trong file | Qua `units` → `units_to_markdown()` | Qua projection full-DOM |
|---|---|---|---|
| `<img>` | 10 | **0** (ảnh không phải đơn vị dịch nên không bao giờ là `EpubUnit`) | 10 |
| `<strong>` (tên + định lượng nguyên liệu in đậm) | 214 | **0** | 214 |
| `<em>` | 26 | **0** | 26 |
| `<sup>`/`<sub>` (6/6 là **tử số phân số**, 0/6 là footnote) | 6 | **bị `extract()` → phá định lượng** | giữ đúng nghĩa |
| `h2`/`h3` | 2 / 34 | 2 / 34 | 2 / 34 |

Lập luận Protocol 6 của bản gốc ("2 parser EPUB cho cùng 1 file = cấu hình sinh bug 2 nhánh lệch
nhau") **vẫn đúng và giữ nguyên** — nhưng nó phải áp ở **tầng loader**, không phải tầng
projection. `EpubUnit` được thiết kế có chủ đích là *danh sách đơn vị DỊCH* (chỉ node có chữ, bỏ
ảnh, bỏ unit toàn số). Mọi quy tắc đó **đúng cho dịch** và **phá** mục tiêu "giữ nguyên vị trí"
của parse-only: `units_to_markdown()` sẽ vi phạm trực tiếp 3/4 AC của US-15 (AC ảnh
`PRD.md:182` mất 100%; AC list `:181` — `EpubUnit.tag == "li"` không biết cha là `ol` hay `ul` nên
numbered steps thành bullet; AC bảng `:180` — `td`/`th` là unit phẳng, không còn ranh giới
`tr`/`table` để dựng lại cột; cộng thêm rule "bỏ unit toàn chữ số" xoá sạch ô số của bảng công
thức).

> **Câu trả lời (đã sửa) cho câu hỏi của PM "parser dùng chung được không?" — CÓ ở tầng LOADER,
> KHÔNG ở tầng projection.** Cái bắt buộc dùng chung là: mở zip, kiểm DRM, xác định `opf_dir`,
> thứ tự spine, parse XHTML → soup. Cái phải khác nhau là: chiếu soup đó ra *đơn vị dịch* (US-22)
> hay ra *Markdown giữ nguyên bố cục* (US-15). Hai projection đọc **cùng một** `spine_documents`
> → Protocol 6 vẫn được thoả ở đúng chỗ nó có ý nghĩa.

```
src/services/epub_document.py
  EpubDocument.load(path)                        # CHUNG: zip, DRM, opf_dir, spine order, soup
    .spine_documents -> list[tuple[str, BeautifulSoup]]   # MỚI, public, theo thứ tự spine
    .units           -> list[EpubUnit]           # projection DỊCH        (§6.20.5)
    .full_text()     -> str                      # text thuần (lọc glossary, US-20 §6.18.5)
    .write_translated(...)                       # §6.20.5
    .to_markdown(images_out_dir) -> str          # projection PARSE-ONLY (US-15)  — MỚI
```

`to_markdown()`: duyệt `spine_documents` **theo đúng thứ tự spine**; mỗi document →
`markdownify(soup, heading_style="ATX")` qua **converter riêng của app** (xem §6.21 — bắt buộc,
converter mặc định của `markdownify` làm hỏng số mũ/chỉ số dưới); nối các document bằng
`\n\n---\n\n`; rewrite mọi `src` ảnh từ đường dẫn tương đối trong zip (`../images/f0003-01.jpg`)
thành `images/f0003-01.jpg` và copy bytes từ zip ra `images_out_dir` — để cây output EPUB **giống
hệt** cây output PDF của MinerU (`document.md` + `images/`, BR-PARSE-03), download.py không phải
biết input là gì.

**Về dependency `markdownify`** (bản gốc muốn tránh): **đảo quyết định, CHẤP NHẬN thêm.** Expert
đã test hành vi thật (`ol` → `1. 2. 3.`, `ul` lồng → thụt đúng cấp, `<img>` → `![alt](src)`,
`<figure>/<figcaption>` → ảnh + dòng caption). Thư viện thuần Python, phụ thuộc duy nhất là `bs4`
— thứ US-22 đã phải cài. Tự viết walker ~100 dòng vẫn phải tự test lại đúng những case đó, không
rẻ hơn, và là code chúng ta phải nuôi. Ràng buộc kèm theo: **pin version trong `pyproject.toml`**
và `to_markdown()` phải có golden test trên chính `chapter01.html` (đổi version `markdownify`
→ golden test đỏ ngay, không âm thầm đổi output).

**Test R6-02 nối 2 projection**: `len(doc.units)` và số heading đếm được trong `to_markdown()`
phải cùng đến từ **một** lần `load()` — assert số `h2`/`h3` trong Markdown == số unit có
`tag in {"h2","h3"}`. Nếu 2 projection tách nhau ra dùng 2 lần `load()` khác nhau, đây là dấu
hiệu Reviewer phải flag.

**Hệ quả thứ tự làm việc**: nhánh EPUB của US-15 **phụ thuộc §6.20 (US-22)**. Nếu increment US-15
chạy trước US-22, `job_type=parse_only` + `file_type=epub` phải trả **HTTP 400 với thông báo rõ**
("Xuất Markdown cho EPUB sẽ có cùng đợt với tính năng dịch EPUB") — KHÔNG được tạo job rồi fail
im lặng. PDF born-digital và PDF scan không phụ thuộc gì, làm được ngay.

**S15-9 — Phụ thuộc hạ tầng phải nói trước (YA-7.3).** `parse_only` cho **PDF born-digital cũng
bắt buộc phải có MinerU đang chạy** (§6.9.8: chạy `mineru-api` bằng uv tool trên macOS, không phải
Docker). UI phải nói rõ điều này trước khi user chọn chế độ, và `run_parse_only()` phải gọi
`MinerURunner.health()` trước, fail sớm với thông báo tiếng Việt rõ ràng thay vì timeout 3600s.

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

#### 6.15.4. Data lineage (Protocol 6 — R6-01) — CẬP NHẬT 2026-09-08

| Bước | Artifact tạo ra | Bước sau đọc gì |
|---|---|---|
| 1. `run_parse_only()` → `_run_mineru_and_record_quality()` | `MinerUResult.markdown_path` + `images_dir` (PDF, trong `data/processing/`) **hoặc** `EpubDocument.to_markdown(images_out_dir)` (EPUB, §6.21) | (2) |
| 2. Đóng gói | `data/outputs/{job_id}/document.md` + `data/outputs/{job_id}/images/` | (3) |
| 3. Guard S15-5 (nội dung) | đọc lại **chính file `document.md` vừa ghi** ở (2), không phải biến trong bộ nhớ | (4) |
| 4. Đóng gói ZIP (S15-3, **eager**) | `data/outputs/{job_id}/parse_result.zip` — ghi từ **danh sách file tường minh** của (2), qua `.tmp` + `os.replace()` | (5) |
| 5. **Guard ZIP (MỚI)** | mở lại **chính file zip vừa ghi**: `testzip() is None`, `"document.md" in namelist()`, số entry `images/` **==** số file trong `images/` trên đĩa. Không đạt → job `failed`, KHÔNG `completed` | `job.output_path` = đường dẫn `.zip` này |
| 6. `download.py` | trả thẳng `job.output_path`, MIME suy từ `.suffix` | user |

Hai sợi dây dễ đứt nhất, **phải có assertion giá trị cụ thể** (R6-02, không được chỉ
`assert parse_document.assert_awaited()` — đúng dạng assertion đã để lọt Bug #5):
- **(1) → (2)**: `MinerUResult.markdown_path` nằm trong `data/processing/`, `job.output_path` nằm
  trong `data/outputs/`. Test assert **đúng đường dẫn cụ thể** được copy/move giữa 2 chỗ.
- **(2) → (4)**: zip phải được dựng từ **thư mục output vừa ghi**, không phải từ
  `MinerUResult.markdown_path` gốc. Test: mở zip ra, `document.md` bên trong phải **byte-identical**
  với `data/outputs/{job_id}/document.md`.

#### 6.15.5. Known limitations của US-15 (đo trên tài liệu bánh THẬT — bắt buộc vào PRD)

Toàn bộ mục này là số đo của Domain Expert trên Figoni *How Baking Works* 25 trang đầu, **cùng
một file** chạy qua **cả 2 mode** MinerU 3.4.5 (`ocr` đã có sẵn trên đĩa + `txt` chạy live) — nên
tách được "lỗi do OCR" khỏi "lỗi do layout/table model". Tech Lead **không đo lại** (lặp lần 3
không tạo thêm thông tin), ghi rõ ranh giới kế thừa này để Reviewer/QA biết.

| # | Giới hạn | Số đo | Hệ quả cho Dev/QA |
|---|---|---|---|
| L-1 | **Bảng KHÔNG phải Markdown table syntax** — MinerU xuất **HTML `<table>` một dòng** | 7/7 bảng ở **cả** `ocr` lẫn `txt`; `pipe_table_rows = 0`; có `rowspan=1 colspan=1` | **Giữ nguyên HTML table trong `document.md`** (GFM render được, và giữ được merged cell mà pipe-table không biểu diễn nổi). **KHÔNG viết converter ở v1.** PRD AC `:180` phải sửa (PM) |
| L-2 | **Cột hẹp bị gộp** — lỗi của table-structure model, KHÔNG phải lỗi OCR | Table 1.4: `POUNDS`+`OUNCES` gộp thành 1 cột; Table 1.5: 4 cột → **2 cột**. **Giống hệt nhau ở cả 2 mode** → born-digital không cứu được | Known limitation. AC-23.1 của BA ("đúng số cột") **sẽ FAIL trên Figoni Table 1.5** — QA không được coi là bug của app |
| L-3 | **List/bảng dàn 2 cột bị trộn thứ tự**, và lỗi **tàng hình khi render** | Trang "EQUIPMENT AND SMALLWARES": thứ tự ra `1,2,17,3,18,19,4,…`; CommonMark **đánh số lại 1-2-3-4** nên bản render trông "đẹp" | QA **bắt buộc kiểm Markdown thô**, không chỉ bản render (đúng tinh thần R6-03) |
| L-4 | **`txt` mode mất glyph ký hiệu toán** | Cùng dòng: `ocr` → `= scale readability × 10` (đúng); `txt` → `  scale readability - 10` — `=` mất, **`×` thành `-`** (nhân → trừ) | Xem §6.21 — đây là ca **nghiêm trọng nhất** của yêu cầu "giữ chuẩn công thức", và là lý do phải có `parse_method` override |
| L-5 | 7 file ảnh "mồ côi" trong `images/` | 23 ảnh ghi ra / 16 được tham chiếu; 7 file dư là **crop của 7 bảng** (MinerU lưu ảnh bảng dù đã xuất HTML) | Vô hại, ZIP vẫn chứa. **QA không được báo bug "ảnh thừa"** |
| L-6 | Ví dụ tên ảnh ở §6.8:1474-1481 (`page_003_img_01.png`) **SAI thực tế** | Tên thật = **SHA-256 + `.jpg`**, không có số trang; đường dẫn relative `images/` thì **đúng** | Test/AC **không được** assert theo mẫu tên cũ |
| L-7 | Heading: cấp đúng nhưng 3 lỗi nhỏ | `title` level chỉ có 1 và 2 trong 25 trang (6 + 43), 0 cấp 3; mất khoảng trắng khi nối dòng (`CHAPTER 4SENSORY PROPERTIES…`); sidebar bị nhận nhầm thành heading (`## HELPFUL HINT`) | QA cần trang có **3 cấp heading thật** mới kiểm được AC `:181` |
| L-8 | Header/footer/số trang **bị loại đúng như mong muốn** (không phải limitation, ghi để QA khỏi báo "mất nội dung") | `discarded_blocks`: header 30, footer 4, page_number 16; `table_footnote` **được giữ** ngay dưới bảng | — |

**Ảnh — ĐÚNG vị trí, xác nhận đồng ý với thiết kế gốc**: 16/16 tham chiếu `![](images/<sha256>.jpg)`
có file thật trên đĩa ở **cả 2 mode**; ảnh nằm **giữa** đoạn văn và heading kế tiếp đúng như trang
gốc, không bị dồn xuống cuối. Alt text luôn rỗng (MinerU đặt caption thành dòng text kế bên,
không nhét vào `alt`) — chấp nhận.

**Giữ MinerU là parser DUY NHẤT cho PDF** (đồng ý với S15-9, Expert xác nhận độc lập): phương án
thay thế duy nhất đáng cân nhắc là PyMuPDF (`pymupdf4llm`/`find_tables`), nhưng (i) heading level
ở PyMuPDF là heuristic cỡ font, không có layout model; (ii) nó là **parser thứ hai cho cùng một
loại input** — đúng thứ Protocol 6 tồn tại để chặn; (iii) MinerU đã chạy sẵn và đã verify sống.

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

---

### 6.16. US-17 + US-18 — Glossary: thêm từ mới có xác nhận ghi đè, và search server-side

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

#### 6.16.2. US-18 — `GET /api/glossary?q=`

**Quyết định**: filter **server-side**, dùng `col(...).contains(q, autoescape=True)` (KHÔNG dùng
`.ilike()`).

Lý do chọn `.contains(autoescape=True)` thay vì `.ilike()`:
1. G-01 vs G-02: cả hai cho cùng kết quả (ASCII fold), nhưng `.ilike()` bọc `lower()` quanh **cột**
   → vô hiệu hoá mọi index trên `term_en` một cách vĩnh viễn, đổi lại không được gì (G-03: vẫn
   không fold được tiếng Việt).
2. `autoescape=True` (G-05) là cách duy nhất trong 2 cách tự xử `%` và `_` — G-04 chứng minh bỏ
   qua việc này là bug thật.

Spec sửa `src/api/routes/glossary.py::list_entries`:

```python
async def list_entries(
    session: SessionDep,
    scope: str | None = None,
    q: str | None = None,        # MỚI
    limit: int = 50,
    offset: int = 0,
) -> GlossaryListResponse:
    ...
    # BR-GLOSS-08: tìm trong CẢ term_en lẫn term_vi
    if q is not None and q.strip():
        needle = q.strip()
        search_clause = col(GlossaryEntry.term_en).contains(needle, autoescape=True) | col(
            GlossaryEntry.term_vi
        ).contains(needle, autoescape=True)
        count_statement = count_statement.where(search_clause)   # BẮT BUỘC
        list_statement = list_statement.where(search_clause)     # BẮT BUỘC
```

**Ràng buộc bắt buộc cho Dev:**
1. `search_clause` phải là **một biến duy nhất** dùng cho cả 2 statement (YA-2.2). Viết 2 biểu
   thức song song → Reviewer reject, cùng lý do §6.11.4 Lop 1 điểm 3 cấm 2 công thức cost song song.
2. Test **bắt buộc** assert `total` khớp `len(entries)` khi kết quả nhỏ hơn `limit` (R6-02: assert
   giá trị cụ thể, không chỉ "gọi rồi").
3. Test bắt buộc có case `q="50%"` và `q="_"` (G-04/G-05) — nếu thiếu escape, `q="_"` trả cả bảng
   và test "search hoạt động" vẫn xanh.
4. `q` AND với `scope` (EC-18.3), không ghi đè nhau.
5. Frontend (`web/js/glossary.js`): thêm `searchQuery` vào state; mọi thay đổi `searchQuery` phải
   `this.offset = 0` trước khi `load()` (YA-2.3, AC-18 dòng 3), có debounce ~250ms.

**Known limitation ghi vào PRD (đã có sẵn ở US-18, đây là số đo xác nhận)**: G-03 — gõ `"đường"`
không ra `"Đường Nâu"`. Không phải chỉ là "không bỏ dấu" (accent-insensitive) như PRD viết, mà
**còn không fold được hoa/thường cho ký tự có dấu**. Cả hai đều xuất phát từ cùng một nguyên nhân
(SQLite build mặc định chỉ Unicode-fold ASCII). Nếu sau này thấy bất tiện thật, hướng nâng cấp rẻ
nhất là thêm cột dẫn xuất `term_vi_fold` (đã `casefold()` + strip dấu bằng `unicodedata`) và search
trên cột đó — KHÔNG cần đổi sang Postgres.

#### 6.16.3. US-17 — BR-GLOSS-07: xác nhận ghi đè khi trùng term

**Quyết định: backend trả `409 Conflict` kèm entry cũ; client hỏi user rồi gọi lại với `force=true`.**

Đúng phương án PM ưu tiên (nhất quán với `confirm_cost` của cost gate §6.11.4 Lop 2 và với `force`
của duplicate-hash AC-12.2 đã có trong `POST /api/jobs`).

Bác bỏ phương án "client tự `GET` rồi so sánh trước khi `POST`" vì 3 lý do:
1. **TOCTOU thật**: giữa lần GET và lần POST, một luồng khác (import Excel, hoặc promote từ US-20)
   có thể đã tạo entry đó. Kiểm tra ở client chỉ là gợi ý, không phải bảo đảm.
2. Nhân đôi luật BR-GLOSS-02 (case-insensitive match) sang JavaScript — luật này hiện chỉ tồn tại
   ở đúng 1 chỗ (`GlossaryManager._find_entry_in_scope` dùng `func.lower(...)`).
3. Không bảo vệ được các client khác (curl, script import) — mà BR-GLOSS-07 nói "hệ thống PHẢI
   hỏi xác nhận", là một luật nghiệp vụ, không phải một chi tiết UI.

Spec:

```python
class GlossaryEntryIn(BaseModel):
    term_en: str
    term_vi: str | None = None
    notes: str | None = None
    #: BR-GLOSS-07 — opt-in tường minh cho ĐÚNG request này, không bao giờ là
    #: default, không được "nhớ" cho lần sau (cùng kỷ luật `confirm_cost`).
    force: bool = False


class GlossaryConflictInfo(BaseModel):
    entry_id: str
    term_en: str          # nguyên văn hoa/thường của entry ĐANG CÓ
    term_vi: str | None
    notes: str | None
    updated_at: datetime
```

`POST /api/glossary`:
- `existing = await manager.get_entry(term_en)` (đã có sẵn, đúng BR-GLOSS-02).
- `existing is not None and not request.force` → **HTTP 409**, body
  `{"detail": "Tu '<term_en cu>' da co trong glossary voi ban dich '<term_vi cu>'. Ghi de?",
    "existing": GlossaryConflictInfo, "requires_confirmation": true}`. **KHÔNG ghi gì vào DB.**
- `force=true` → giữ nguyên `bulk_import()` 1 phần tử như hiện tại (BR-GLOSS-03 last-updated-wins),
  kèm `logger.info` ghi lại giá trị cũ đã bị ghi đè.

**Phạm vi KHÔNG đổi**: `bulk_import()` qua `POST /api/glossary/import/confirm` (Excel hàng loạt)
giữ nguyên hành vi ghi đè im lặng — BR-GLOSS-07 chỉ áp cho luồng thêm-1-entry-đơn-lẻ, đúng câu
chữ PRD.

**Ràng buộc test (R6-02)**: test phải assert **số dòng trong bảng KHÔNG đổi** và **`term_vi` cũ
KHÔNG đổi** sau một request 409 — không được chỉ assert `response.status_code == 409` (đúng kiểu
assertion mà test cost gate §6.11 đã làm đúng: đếm thật bằng `SELECT COUNT(*)`).

---

### 6.17. US-19 — Lịch sử: thời gian dịch + số trang

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

#### 6.17.2. Quyết định: thêm cột `Job.finished_at`

```python
# src/models/job.py
finished_at: datetime | None = Field(default=None)
# Mốc KẾT THÚC của job ở MỌI trạng thái cuối (completed | failed | cancelled |
# cost_capped), phục vụ BR-HIST-01/02. Cố ý KHÔNG dùng lại `completed_at`:
# `completed_at` hiện có đúng nghĩa "hoàn tất THÀNH CÔNG" và đang là dữ liệu
# nghiệp vụ của 2 chỗ khác (duplicate-detection AC-12.2 và hậu tố tên file
# tải về) — nới nghĩa của nó là đúng loại "trôi ngữ nghĩa im lặng" mà
# Protocol 6 tồn tại để chặn. BREAKING SCHEMA CHANGE, xoá/tạo lại DB dev.
```

**KHÔNG đổi `completed_at`, KHÔNG đổi `started_at`, KHÔNG đổi `total_pages`** — 3 cột này giữ
nguyên ý nghĩa và consumer hiện có.

Gán `job.finished_at = datetime.now(UTC)` tại **cả 5** điểm thoát cuối của `run_job()`:
Step 4 (`UnsupportedForPdfPipelineError` → failed), Step 7 (chunk failed), Lop 3 (`cost_capped`),
graceful cancel (`cancelled`), Step 8 (merge failed), Step 10 (`completed`). Và tại
`_run_job_background()`'s last-resort guard (`except Exception` → failed) — đây là điểm dễ quên
nhất vì nó nằm ở `jobs.py` chứ không ở orchestrator.

Với hàng cũ trong DB (`finished_at` NULL) → fallback `completed_at`; nếu cả hai NULL và status là
terminal → hiển thị `-`, **không** đoán bằng `updated_at`.

#### 6.17.3. Thay đổi tầng response (spec cho Dev)

```python
class JobDetail(BaseModel):
    ...  # giữ nguyên toàn bộ field hiện có
    total_pages: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None   # BR-HIST-01: finished_at - created_at
    total_units: int | None = None          # §6.20.6 — EPUB, NULL cho PDF
```

Tất cả optional với default → backward-compatible, không phá client cũ (cùng kỷ luật đã dùng cho
`ocr_confidence`/`cancel_requested`).

`_to_detail()` tính:

```
_TERMINAL = {"completed", "failed", "cancelled", "cost_capped"}

end = job.finished_at or job.completed_at
duration = (end - job.created_at).total_seconds() if (end and job.status in _TERMINAL) else None
```

- BR-HIST-01: mốc bắt đầu là `created_at`, **không** `started_at` — giữ đúng quyết định PM. Lý do
  kỹ thuật xác nhận quyết định đó đúng: `started_at` được gán ở Step 6, tức SAU toàn bộ OCR của
  nhánh `pdf_scan`, nên nó bỏ mất phần chờ dài nhất của job scan. `started_at` vẫn được expose
  để UI có thể hiện "trong đó OCR ≈ started_at − created_at" nếu muốn — **không bắt buộc** ở đợt này.
- BR-HIST-02: job đang chạy → `duration_seconds = None`, UI hiện `-` (không đếm tiến, tránh phải
  refresh định kỳ).
- EC-19.1: job cũ thiếu field → NULL → UI hiện `-`, không được vỡ.
- EC-19.2: định dạng "8 phút 12 giây" là việc của frontend; API luôn trả **số giây float**, một
  đơn vị duy nhất.
- **`total_pages` cho EPUB = NULL** → UI hiện `-` đúng theo AC US-19. `total_units` (§6.20.6) là
  thông tin bổ sung tuỳ chọn cho EPUB, không thay thế cột "số trang".

#### 6.17.4. BR-HIST-03 — bỏ "+ Glossary" khỏi tab Lịch sử

Thuần frontend: xoá nút ở `web/history.html` và hàm mở modal tương ứng ở `web/js/history.js`.
Nút **"Xoá job"** đã có từ 2026-09-06 **giữ nguyên** (BA đính chính Đ-02 — user không nói về nút này).

---

### 6.18. US-20 — "Các từ mới": gợi ý thuật ngữ từ tài liệu vừa dịch

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

#### 6.18.2. Thuật toán trích xuất (spec cho Dev — `src/core/term_extractor.py`, module MỚI)

Input: `source_text: str` (tiếng Anh, xem lineage §6.18.5), `existing_terms: set[str]` (đã
`.lower()`), `settings`.

```
1. Tách câu thô theo dấu câu; trong mỗi câu, tokenize theo [A-Za-z][A-Za-z'-]* (giữ dấu nháy đơn
   cho "baker's", giữ gạch nối cho "pre-ferment"), hạ về lowercase để đếm.
2. Sinh n-gram n = 1, 2, 3 KHÔNG vượt qua ranh giới câu và không bắt đầu/kết thúc bằng stopword.
3. Loại bỏ:
   - n-gram mà MỌI token đều nằm trong en_common.txt
   - n-gram chứa chữ số, hoặc dài < 3 ký tự
   - n-gram đã có trong glossary (BR-TERM-02, so khớp .lower(), kể cả khớp một phần: nếu
     "ganache" đã có thì "chocolate ganache" VẪN được gợi ý — nó là thuật ngữ khác)
   - n-gram xuất hiện < `min_occurrences` (mặc định 3; YA-4.6 của BA đề xuất bỏ từ chỉ xuất hiện
     1 lần vì phần lớn là tên riêng / lỗi OCR)
4. Khử trùng lặp lồng nhau: nếu "laminated dough" xuất hiện 12 lần và "laminated" xuất hiện 12
   lần (tức "laminated" gần như luôn đi kèm), giữ n-gram DÀI, bỏ n-gram ngắn. Ngưỡng: bỏ n-gram
   ngắn nếu >= 80% số lần xuất hiện của nó nằm bên trong 1 n-gram dài hơn đã giữ.
5. Xếp hạng: điểm = occurrence_count × (1 + 0.5 × (n − 1)) — ưu ái cụm nhiều từ vì đó là nhóm
   thuật ngữ giá trị nhất.
6. Cắt còn `max_suggested_terms_per_job` (mặc định 40; PRD đề xuất 30-50).
```

> **CẢNH BÁO — khối pseudo-code trên là BẢN CŨ, đã bị §6.18.8 thay thế ở bước 1, 3, 4, 5, 6.**
> Chỉ còn bước 2 (sinh n-gram 1–3, không vượt ranh giới câu) là còn nguyên hiệu lực. Dev
> **KHÔNG** được implement theo khối này; nó ở lại để đọc hiểu lịch sử quyết định.

Config mới (`src/core/config.py`, cả 3 vào `SETTINGS_DB_OVERRIDABLE_FIELDS`) — **bảng này đã được
§6.18.8 mục T5 cập nhật, đọc bảng ở đó**:

| Field | Default | Ý nghĩa |
|---|---|---|
| `term_extraction_enabled` | `True` | Tắt hẳn bước gợi ý (kill switch) |
| ~~`max_suggested_terms_per_job`~~ | ~~`40`~~ | ~~Trần chống spam (YA-4.6)~~ → đổi nghĩa thành **van chống tràn DB**, default `20_000`, xem T1 |
| `term_min_occurrences` | `3` | Bỏ từ xuất hiện quá ít — xem T5 (thêm biến thể cho tài liệu ngắn) |

**Đây là thuật toán heuristic thuần, KHÔNG phải external tool** → không thuộc phạm vi Protocol 5.
Nhưng bắt buộc phải có **golden file**: `tests/fixtures/term_extraction/` chứa text EN thật trích
từ 1 job đã dịch, kèm danh sách kỳ vọng — để lần chỉnh ngưỡng sau này đo được là tốt lên hay xấu đi.

#### 6.18.3. DB schema mới

```sql
CREATE TABLE suggested_terms (
    id                 TEXT PRIMARY KEY,     -- UUID
    job_id             TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    term_en            TEXT NOT NULL,        -- dạng bề mặt hiển thị cho user
    match_key          TEXT NOT NULL,        -- MỚI (T3): dạng chuẩn hoá dùng để so glossary
    ngram_size         INTEGER NOT NULL,     -- MỚI (T4): 1 | 2 | 3 — cho bộ lọc UI "chỉ cụm >= 2 từ"
    noise_flags        TEXT NOT NULL DEFAULT '',
                       -- MỚI (T4): CSV các nhãn nghi-nhiễu: proper_noun | stopword_middle
                       --           | fragment_suspect | plural_merged.
                       -- KHÔNG phải điều kiện loại bỏ — chỉ để UI ẩn mặc định + demote rank.
    occurrence_count   INTEGER NOT NULL,
    rank_score         REAL NOT NULL,        -- điểm xếp hạng (T5), để sắp xếp ổn định
    status             TEXT NOT NULL DEFAULT 'pending',
                       -- pending | added | dismissed
    suggested_term_vi  TEXT,                 -- CHỈ khác NULL sau khi user bấm "Gợi ý bản dịch"
    translation_cost_usd REAL,               -- chi phí THẬT của lượt LLM đó (metered)
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_suggested_terms_job ON suggested_terms(job_id);
CREATE UNIQUE INDEX idx_suggested_terms_job_term ON suggested_terms(job_id, term_en);
-- MỚI: khu vực "Chờ duyệt" gộp mọi job, mặc định lọc status + ẩn nhiễu, sắp theo rank_score.
CREATE INDEX idx_suggested_terms_status_rank ON suggested_terms(status, rank_score DESC);
```

**3 cột thêm sau phản biện Domain Expert (2026-09-08)** — lý do đầy đủ ở §6.18.8:
`match_key` (T3), `ngram_size` + `noise_flags` (T4). Cả 3 nằm trong **cùng đợt migration
`ALTER TABLE`** đã chốt ở §6.20.11 mục 1 — bảng này là bảng MỚI nên chỉ là `CREATE TABLE`, không
phải `ALTER`. Kích thước: pool đo thật trên sách 415 trang = **5.177 dòng/job** (§6.18.8 T1) —
không đáng kể với SQLite, nhưng là lý do phải có index `status, rank_score`.

Ghi chú thiết kế:
- `ON DELETE CASCADE` theo `job_id` — trả lời BA-Q13/EC-20.7: xoá job thì xoá luôn gợi ý chưa
  duyệt. Nhất quán với `chunks`/`overflow_reports` đang có. **Nhưng** `DELETE /api/jobs/{id}` hiện
  xoá thủ công từng bảng con (`chunks`, `overflow_reports`) chứ không dựa vào cascade của SQLite
  (SQLite mặc định **tắt** foreign key enforcement) → Dev phải thêm `suggested_terms` vào đúng
  danh sách xoá thủ công đó, không được tin vào `ON DELETE CASCADE`.
- **Không có** trạng thái `rejected` toàn cục. Đúng BR-TERM-04 (user đã chốt: "Bỏ qua" chỉ ẩn
  trong phạm vi job đó). Rủi ro BA nêu ở YA-4.2 (sau vài cuốn cùng chủ đề, danh sách lặp lại) là
  **có thật** nhưng được giảm nhẹ đáng kể bởi BR-TERM-02: mỗi từ user đã "Thêm vào glossary" biến
  mất vĩnh viễn khỏi mọi gợi ý tương lai. Chỉ những từ user chủ động **từ chối** mới lặp lại. Ghi
  vào §6.18.7 để PM theo dõi, không tự đổi luật.

#### 6.18.4. API

| Method | Path | Ghi chú |
|---|---|---|
| `GET` | `/api/glossary/suggested?job_id=&status=pending&limit=&offset=&sort=&min_ngram=&include_noise=` | `job_id` optional — bỏ trống = gộp mọi job (khu vực "Chờ duyệt" chung trong tab Glossary, đúng BA-Q4 phương án (B) user đã chọn). **4 tham số mới sau phản biện 2026-09-08** — xem T4: `sort` ∈ `rank` (mặc định) \| `count` \| `alpha`; `min_ngram` ∈ 1 (mặc định) \| 2; `include_noise` bool (mặc định `false`); response **bắt buộc** trả thêm `total` và `noise_hidden_count` để UI hiện đúng "Hiện thêm N mục nghi nhiễu" |
| `POST` | `/api/glossary/suggested/{id}/dismiss` | `status='dismissed'`, trả 204 |
| `POST` | `/api/glossary/suggested/{id}/promote` | body `{term_vi, notes, force}` → gọi **đúng logic `POST /api/glossary`** (§6.16.3), tức **có áp BR-GLOSS-07**: trùng + `force=false` → 409, entry Chờ duyệt **giữ nguyên `pending`**. Thành công → `status='added'` |
| `POST` | `/api/glossary/suggested/suggest-translation` | body `{ids: [...]}` — **hành động DUY NHẤT tốn tiền** trong US-20 |

**`suggest-translation` — ràng buộc bắt buộc:**
- Gộp **tối đa 40 term vào 1 request LLM duy nhất** (không 1 request/từ). Với 40 term ngắn, chi phí
  thực tế ở DeepSeek < $0.001 — nhưng vẫn phải hiển thị trước, không được giấu.
- Đi qua `provider.translate()` (§6.6.2 R3 mục 4 đã dành sẵn chỗ cho "cac pipeline tuong lai khong
  di qua pdf2zh") → **có `TranslationResult.input_tokens/output_tokens/estimated_cost_usd` thật**.
  Ghi vào `suggested_terms.translation_cost_usd`.
- **KHÔNG cộng vào `job.actual_cost`.** Lý do: `job.actual_cost` đi kèm `job.cost_source =
  'estimated'` (§6.6.6) — trộn một số **đo thật** vào một tổng **ước lượng** làm hỏng ngữ nghĩa của
  chính `cost_source`, đúng loại nhầm lẫn RC-4 của sự cố $6.50. Chi phí gợi ý bản dịch báo cáo
  riêng.
- UI: nút phải nói rõ *"Gợi ý bản dịch cho N từ — hành động này gọi LLM và phát sinh chi phí"*
  TRƯỚC khi bấm (BR-TERM-03, và Lop 0 §6.11.4 điểm 3).
- Prompt: yêu cầu trả JSON `{"<term_en>": "<term_vi>"}`; với thuật ngữ gốc Pháp/Ý (BA-Q15) hướng
  dẫn LLM trả `"(keep)"` — đúng BR-GLOSS-04. Không bắt buộc phải đúng, chỉ là gợi ý user duyệt.

#### 6.18.5. Data lineage (Protocol 6 — R6-01) — sợi dây quan trọng nhất của US-20

`source_text` phải là **văn bản tiếng Anh của tài liệu đó**, và với mỗi `file_type` nó nằm ở một
chỗ khác nhau. Đây đúng dạng lỗi Bug #5 (đọc nhầm `job.file_path` thay vì file cầu nối):

| `job.file_type` | Nguồn `source_text` BẮT BUỘC | Tuyệt đối KHÔNG đọc |
|---|---|---|
| `pdf_digital` | `_extract_full_text(Path(job.file_path))` | — |
| `pdf_scan` | `_extract_full_text(Path(job.ocr_bridge_path))` — file searchable PDF do §6.10 dựng | ❌ `job.file_path` (ảnh scan, 0 ký tự → danh sách gợi ý rỗng, im lặng) |
| `epub` | `EpubDocument.load(job.file_path).full_text()` (§6.20.5) — `full_text()` trả **text thuần đã strip tag**, KHÔNG phải inner-HTML của `EpubUnit.source_html` | ❌ `_extract_full_text()` (PyMuPDF không mở được EPUB); ❌ `"\n".join(u.source_html)` — sẽ sinh ứng viên `strong strong strong` |
| `parse_only` bất kỳ | `Path(job.output_path).parent / "document.md"` — **SỬA 2026-09-08**: `job.output_path` của parse_only nay trỏ tới `parse_result.zip` (S15-4 đã sửa), không phải `.md` | ❌ đọc thẳng `job.output_path` (sẽ đọc phải bytes của file ZIP) |

Chuỗi đầy đủ:

| Bước | Artifact tạo ra | Bước sau đọc gì |
|---|---|---|
| 1. `run_job()` kết thúc `status="completed"` | `job.file_path` / `job.ocr_bridge_path` / `job.output_path` | (2) |
| 2. `_extract_source_text_for_terms(job)` (hàm MỚI, bảng trên) | `source_text: str` | (3) |
| 3. `GlossaryManager` liệt kê mọi `term_en` hiện có, **scope global + project** (BR-GLOSS-06) | `existing_forms: set[str]` = hợp của `glossary_match_forms(term_en)` cho mọi entry — **KHÔNG** phải `{term_en.lower()}` (T3) | (4) |
| 4. `extract_terms(source_text, existing_forms, settings)` | `list[TermCandidate]` | (5) |
| 5. ghi `suggested_terms` rows | `status='pending'` | UI |

> **SỬA bước 3 sau phản biện Domain Expert (2026-09-08)**: bản gốc ghi `existing_terms` = tập
> `term_en.lower()`. Đo trên glossary **thật** của user (114 entry): **23/114 (20%)** entry có
> dạng `a / b` hoặc `x (ghi chú)` (`knead / kneading`, `bloom (chocolate)`, `pound (lb)`,
> `tempering (sugar)`…) → `.lower()` nguyên chuỗi **không bao giờ** bằng một n-gram, nên
> `pound` x112, `ounce` x92, `bloom` x56, `tempering` x32, `whipping` x40, `kneading` x15 … **vẫn
> lọt vào "Chờ duyệt"** dù đã có trong glossary. Đây là **vi phạm trực tiếp điều kiện lọc DUY
> NHẤT mà user vừa chốt** ("chỉ gợi ý từ không có trong glossary"). Chi tiết cơ chế thay thế:
> §6.18.8 T3. `build_prompt_snippet()` đã có sẵn logic gộp 2 scope
> (`src/core/glossary_manager.py:151-158`) → tái dùng, không viết lại.

**Test bắt buộc (R6-02)**: với 1 job `pdf_scan`, phải assert `_extract_source_text_for_terms` được
gọi/đọc **đúng `job.ocr_bridge_path`**, không chỉ `assert extract_terms.called`. Nếu 2 mock trong
cùng test không có assertion nào nối input của (4) với output của (2) → Reviewer flag (R6-02).

#### 6.18.6. Chạy ở đâu, và không được làm hỏng job dịch (BR-TERM-01, YA-4.5)

Trong `_run_job_background()` (`src/api/routes/jobs.py`), **SAU** khi `run_job()` trả về:

```
result = await orchestrator.run_job(job_id, session)
if result.status == "completed" and settings.term_extraction_enabled:
    try:
        await extract_and_store_terms(job_id, session)
    except Exception:
        logger.exception("Trich xuat tu moi that bai cho job %s — job VAN completed", job_id)
```

- Đặt ở đây (không đặt bên trong `run_job()`) để **không tồn tại đường nào** khiến lỗi trích xuất
  đổi được `job.status`. Job đã ra file đúng rồi.
- Chỉ chạy khi `status == "completed"` — trả lời EC-20.3: job `cost_capped`/`failed` **không** trích
  xuất (bản dịch dở dang, và văn bản nguồn thì vẫn nguyên vẹn nên chẳng mất gì khi user retry xong).
- Chạy **tuần tự sau job**, không `create_task` song song: nó đọc cùng `session`, và với 40 n-gram
  trên vài trăm nghìn ký tự thì đây là công việc mili-giây, không đáng để đánh đổi lấy một luồng
  đồng thời nữa.
- Có `POST /api/jobs/{id}/extract-terms` để chạy lại thủ công khi bước này lỗi (AC-20.3 của BA).

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

##### T1. Bỏ trần cứng 40 → liệt kê hết, phân trang ở UI

- `extract_terms()` trả **toàn bộ** ứng viên qua sàn tần suất, sau khi đã bỏ hết ứng viên khớp
  glossary (T3). **Không cắt ở bất kỳ con số nào.**
- `max_suggested_terms_per_job` **đổi nghĩa**: từ "trần chất lượng" thành **van chống tràn DB**,
  default **`20_000`** (≈ 4× worst case đo được là 5.177). Chạm trần → ghi `logger.warning` nêu rõ
  số bị cắt + `job_id`, cắt theo `rank_score` giảm dần. Đây là lưới an toàn chống tài liệu bệnh
  lý, **không phải** cơ chế chọn lọc chất lượng — Dev không được hạ con số này xuống "cho gọn".
- UI "Chờ duyệt": **phân trang 50 dòng/trang**, có `sort` + `min_ngram` + `include_noise`
  (§6.18.4 đã cập nhật). Mặc định: `sort=rank`, `min_ngram=1`, `include_noise=false`.

##### T2. Bỏ HẲN `en_common.txt` (~3.000 từ) — thay bằng chuẩn hoá token + stoplist hư từ

**Bằng chứng bác bỏ** (Expert, google-10000 làm list tiêu biểu): với ngưỡng 3.000 từ, `flour`
(hạng 9751), `sugar`, `egg`, `butter`, `oven` **KHÔNG bị lọc** và chiếm trọn top-40; còn `proof`
(2933), `score` (1154), `cream` (2966), `rest` (1539), `roll`, `turn`, `cup` — **đều là glossary
entry thật của user, đúng nhóm EC-06** — thì **BỊ lọc**. Tăng list lên 10.000 để lọc được `flour`
làm số term glossary bị giết tăng từ 4/60 lên **12/58**. Không có cỡ list nào đúng.

Expert đề xuất giữ list + thêm `baking_sense_allowlist.txt` (~80 từ ngoại lệ). **Tôi đi xa hơn và
bỏ hẳn list**, vì 2 lý do:
1. **Lý do tồn tại của list đã biến mất.** Nó sinh ra để giành chỗ trong 40 slot. Với T1 (không
   còn trần), một từ generic đứng trong danh sách chỉ tốn của user một lần lướt mắt — trong khi
   một từ bị list xoá thì **vĩnh viễn không bao giờ được gợi ý**, tức là đúng loại lỗi mà §6.18.1
   đã xác định là đắt hơn hẳn.
2. **Nó mâu thuẫn với luật mới của user.** User chốt điều kiện lọc **duy nhất** là "không có
   trong glossary". Một bộ lọc thứ hai theo "độ phổ thông" là luật thứ hai, và là luật đã được đo
   là chạy ngược hướng.

**Cái thay thế** (2 thứ, đều rẻ hơn và không xoá nhầm thuật ngữ):
- **Stoplist hư từ đóng (~200 từ)**: mạo từ, giới từ, liên từ, đại từ, trợ động từ. Dùng cho đúng
  2 việc: (i) n-gram **không được bắt đầu/kết thúc** bằng hư từ (rule cũ, giữ), (ii) 1-gram **là**
  hư từ thì bỏ. An toàn tuyệt đối với EC-06 vì `proof`/`score`/`cream`/`rest`/`turn`/`fold`
  **không phải hư từ** — khác hẳn "3.000 từ phổ thông". Ship tại `data/wordlists/en_function_words.txt`,
  **Architecture.md/CHANGELOG phải ghi rõ nguồn + ngày lấy** (tinh thần R5-01: kết quả phụ thuộc
  hoàn toàn vào nội dung file dữ liệu này).
- **Tần suất nền tiếng Anh dùng làm TÍN HIỆU XẾP HẠNG, tuyệt đối không dùng làm bộ lọc**: ship
  `data/wordlists/en_freq_top50k.tsv` (word + rank, nguồn công khai phải ghi rõ + ngày lấy). Từ
  càng phổ thông → `specificity` càng thấp → xếp sau, **nhưng vẫn có mặt trong danh sách**. Đây
  chính là biến "nhị phân sai" thành "liên tục đúng". Expert đo biến thể này cải thiện recall@500
  từ 18/60 → 24/60. Nếu file không tồn tại → `specificity = 1.0` cho mọi từ (degrade an toàn, chỉ
  mất chất lượng sắp xếp, không đổi tập hiển thị).

**Lời đề nghị soạn `baking_sense_allowlist.txt` của Expert: KHÔNG dùng làm escape hatch của bộ
lọc (vì không còn bộ lọc), nhưng NHẬN làm boost xếp hạng** — nếu Expert soạn, đưa vào
`data/wordlists/baking_sense_boost.txt`, token nằm trong đó nhân `rank_score × 1.5`. **Optional,
không chặn v1.**

##### T3. Trọng tâm mới — `glossary_match_forms()`: so khớp glossary phải MẠNH hơn `.lower()`

Đây là **hàm quan trọng nhất của US-20** sau quyết định (b), vì nó là **điều kiện lọc duy nhất**.

```python
# src/core/glossary_matching.py  (module MỚI, dùng CHUNG — xem cảnh báo Protocol 6 bên dưới)
def glossary_match_forms(term_en: str) -> set[str]:
    """Mọi dạng bề mặt mà một entry glossary có thể xuất hiện trong tài liệu."""
```

Thuật toán chốt (mọi bước đều có ví dụ từ glossary THẬT của user):

| # | Bước | Ví dụ thật |
|---|---|---|
| 1 | Tách theo `/` thành các phương án độc lập | `knead / kneading` → `knead`, `kneading`; `baking stone / pizza stone`; `phyllo / filo dough` |
| 2 | Bỏ phần trong `( … )`, **và** giữ thêm một phương án là chính nội dung trong ngoặc nếu nó ≥3 ký tự và không phải viết tắt thuần | `bloom (chocolate)` → `bloom`; `pound (lb)` → `pound`, `lb`; `Swiss meringue buttercream (SMBC)` → cả cụm dài lẫn `SMBC` |
| 3 | NFKC normalize; `’`/`‘` → `'`; lowercase; gộp khoảng trắng liên tiếp | `baker’s percentage` ↔ `baker's percentage` |
| 4 | **Sinh biến thể hình thái** cho mỗi phương án: từ mỗi *base ứng viên* (chính nó, và kết quả bỏ hậu tố `-s`/`-es`/`-ies`/`-ing`/`-ed` nếu còn ≥3 ký tự) sinh tập `{base, base+s, base+es, base+ies, base+ing, base+ed}` kèm xử lý `e` cuối (`bake`→`baking`) và nhân đôi phụ âm (`pit`→`pitting`) | `kneading` → sinh cả `knead`, `kneads`, `kneaded`, `kneading`; `meringue` → `meringues`; `bannetons` → `banneton` |

**Vì sao SINH biến thể (expansion) chứ không CẮT hậu tố (stemming) ứng viên**: cắt hậu tố một
token bất kỳ là thao tác **mất thông tin và dễ over-stem** trên từ ta không kiểm soát; sinh biến
thể từ một base **đã biết** thì dạng thừa (`meringueed`) chỉ đơn giản là không bao giờ khớp — vô
hại. Không cần `nltk`/`spacy` (dependency nặng, và đúng phạm vi Protocol 5 nếu là external model).

**Bất đối xứng rủi ro — cơ sở để chọn "thà gộp nhầm còn hơn bỏ sót"**: gộp nhầm 2 từ khác nghĩa
chỉ làm **ẩn một gợi ý**; bỏ sót làm **hiện lại một từ user đã có trong glossary**, đúng thứ user
vừa ra lệnh cấm. Trong ngành bánh, số nhiều **không bao giờ** là term khác
(`ganache`/`ganaches`, `éclair`/`éclairs`) nên rủi ro thực tế ≈ 0.

**So khớp**: ứng viên bị loại khi **`match_key` của cả cụm** ∈ `existing_forms`. **KHÔNG** so
substring: `ganache` đã có → `chocolate ganache` **vẫn được gợi ý** (nó là thuật ngữ khác — quy
tắc cũ của §6.18.2, Expert đồng ý, giữ nguyên).

> **⚠️ Protocol 6 — hàm này BẮT BUỘC dùng chung với đường dịch, không được có bản thứ hai.**
> Expert phát hiện `GlossaryManager._count_occurrences()` (`src/core/glossary_manager.py:22-26`,
> **code đang ship**) dùng `re.escape(term_en)` thô để lọc glossary theo tài liệu (§6.6.5, call
> site `prompt_builder.py:169-171`): trên Figoni chỉ **60/114** entry match, **23 entry dạng
> `/` `( )` match 0 lần** → 23 entry đó **chưa bao giờ được inject vào prompt dịch**. Đây là bug
> độc lập với US-20 (PM đã tách task riêng), nhưng **cùng một điểm mù**. Hai chỗ phải gọi **một**
> `glossary_match_forms()`; nếu Dev viết logic chuẩn hoá lần thứ hai bên trong `term_extractor.py`,
> Reviewer **reject** (R6-04) — 2 định nghĩa cho "thế nào là cùng một term" chính là cấu hình sinh
> ra 2 nhánh lệch nhau.

##### T4. Chuẩn hoá text + tokenizer: viết lại bước 1 (đây là tiền đề, sai ở đây thì mọi thứ sau vô nghĩa)

Bằng chứng bác bỏ tokenizer `[A-Za-z][A-Za-z'-]*` của bản gốc (Expert đo trên text thật, và tôi
xác nhận lại được ngay trong output MinerU thật: dòng 495 của `document.md` có `fl avorings`):

| Hiện tượng | Số đo thật | Hậu quả với spec cũ |
|---|---|---|
| Ligature `ﬂ`/`ﬁ` + **một khoảng trắng thật** trong PDF | `ﬂ our` **993 lần**, `ﬂ avor` 638, `ﬁ ne` 196 | `flour` mất 993/1183 lần đếm; **`avor` thành #1 top-40**; 98 ứng viên là mảnh vỡ |
| Nháy cong `’` vs ASCII `'` | Figoni **287 / 0**; Cauvain 258 / 0 | `baker's` — chính ví dụ của §6.18.1 — **không bao giờ** xuất hiện trên PDF. (Bản OCR MinerU lại ra nháy ASCII → 2 nhánh pipeline cho kết quả khác nhau cho cùng một từ) |
| Gạch nối ngắt dòng `xxx-\n` | 884 (Figoni) | 121 ứng viên dạng `choco- late`, `ingre- dients` |
| Chữ Latin có dấu | 135 token: `éclair` 27, `crème` 16, `pâte` 15… | `pâte à choux` → `p te choux`; `crème` → `cr`+`me` → bị rule "<3 ký tự" xoá sạch. **Đúng nhóm YA-4.7** ("rất nhiều thuật ngữ là tiếng Pháp/Ý") |
| HTML/Markdown (nhánh `parse_only`, EPUB) | bản OCR thật: 160 `<td>`, 53 `<tr>` | top-4 ứng viên là `td td td` (x110), `td tr tr`, `tr tr td`, `td td tr`; `jpg` x16 |

**Bước 1 mới = `normalize_source_text()` rồi mới tokenize**, 7 việc, theo đúng thứ tự:
1. Strip HTML tag + cú pháp Markdown (ảnh `![](…)`, heading `#`, bảng HTML) — **trước** khi tách
   câu. Áp cho nguồn `parse_only` (`document.md`) và EPUB.
2. `unicodedata.normalize("NFKC")` (ﬁ→fi, ﬂ→fl, ﬃ→ffi).
3. `’`/`‘` → `'`.
4. **Ghép mảnh ligature**: token lẻ ∈ `{fi, fl, ffi, ffl, ff}` + khoảng trắng + chữ thường → nối
   (`fl our` → `flour`); token kết thúc bằng `fi`/`fl` + khoảng trắng + mảnh chữ thường → nối
   (`emulsifi ers` → `emulsifiers`). Sau bước này `flour` = **1040 lần**, đúng thực tế.
5. Khử gạch nối ngắt dòng: `(?<=[a-z])-\n\s*(?=[a-z])` → `""`.
6. Tách câu trên **bộ dấu ghi tường minh**: `[.!?;:,()\[\]"“”—•|]` — spec cũ chỉ nói "theo dấu
   câu", nếu Dev chỉ tách theo `.!?` thì n-gram sẽ vượt dấu phẩy (`flour, water` → `flour water`).
7. Tokenizer chấp nhận Latin có dấu: `[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']*(?:-[A-Za-zÀ-ÿ']+)*`.

**Test đơn vị bắt buộc** (chuỗi lấy từ số đo thật, không bịa): `ﬂ our`→`flour`,
`emulsiﬁ ers`→`emulsifiers`, `baker’s`→`baker's`, `choco-\nlate`→`chocolate`, `pâte à choux`
nguyên vẹn, `<td>flour</td>`→`flour`.

**Nhiễu n-gram: DEMOTE + ẩn mặc định, KHÔNG xoá** (đây là chỗ tôi làm khác đề xuất của Expert).
Expert đề xuất **lọc bỏ** tên riêng/acronym và n-gram có hư từ ở giữa. Dưới luật mới của user,
xoá vĩnh viễn một ứng viên vì lý do khác "đã có trong glossary" là thêm một luật thứ hai — và rủi
ro thật: `Swiss meringue`, `Italian meringue`, `Silpat`, `Fahrenheit` **đều là glossary entry
thật** và đều là tên riêng viết hoa giữa câu. Vì vậy 4 tín hiệu sau ghi vào `noise_flags`, **demote
`rank_score` × 0.3**, và UI **ẩn mặc định** (có nút "Hiện thêm N mục nghi nhiễu") — user vẫn lấy
lại được, không mất vĩnh viễn:

| Flag | Điều kiện | Bắt được (đo thật) |
|---|---|---|
| `proper_noun` | tỷ lệ viết hoa **giữa câu** ≥80%, cần ≥3 lần quan sát; hoặc acronym toàn hoa | 221 ứng viên (Figoni) / 102 (Cauvain): `cauvain` x178, `baking problems solved` x129, `blackie academic professional`, `chipping campden` |
| `stopword_middle` | 3-gram có hư từ ở giữa, **trừ** `{of, à, de, en, au, aux}` | `exercises and experiments` x96, `batters and doughs` x71, `fats and oils` x56 |
| `fragment_suspect` | token ∈ danh sách mảnh vỡ đã biết, hoặc kết thúc bằng `-` | phòng tuyến hai lớp cho ligature nếu bước 4 sót |
| `plural_merged` | dòng này là kết quả gộp số ít/số nhiều | 10 cặp trong top-100 Figoni (`flour/flours`, `dough/doughs`…) — gộp thành 1 dòng, **cộng dồn count**, giữ dạng bề mặt xuất hiện nhiều hơn |

##### T5. Khử lồng nhau, xếp hạng, sàn tần suất

- **Bước 4 (khử lồng nhau) — chốt cách đọc: "MAX, không SUM".** Spec cũ mập mờ ("≥80% số lần xuất
  hiện nằm bên trong **1** n-gram dài hơn"); Dev có thể cài theo "tổng mọi n-gram dài chứa nó" mà
  không sai chữ. Đo thật: cách "sum" **giết** `gluten` x447, `crumb` x139, `meringue` x116,
  `crust` x91, `pound`, `ounce` — đúng 6 term glossary 1-gram giá trị nhất, vì mỗi từ đó tham gia
  hàng chục cụm cộng dồn vượt 80%. **Golden test bắt buộc: `gluten` (x447) phải còn trong pool.**
- **Term glossary tham gia làm "n-gram dài đã giữ"** dù không được xuất (sửa thứ tự bước 3/4 cũ).
  Đo thật: `puff pastry` x64 đã có trong glossary → bị xoá ở bước 3 → `puff` x70 không còn gì hấp
  thụ nó → nổi lên #35. Tương tự `powder` x216 sau khi `baking powder` bị xoá.
- **Xếp hạng**: `rank_score = log(1 + count) × ngram_weight × specificity × noise_penalty`, với
  `ngram_weight = 1 + 0.5×(n−1)` (giữ), `specificity` từ T2, `noise_penalty ∈ {1.0, 0.3}`.
  **Xếp hạng giờ chỉ quyết định THỨ TỰ, không quyết định ai bị loại** — nên không đầu tư thêm
  (PMI/t-score) trước khi có harness đo.
- **Sàn tần suất theo ĐỘ DÀI TÀI LIỆU, đếm theo token — KHÔNG theo số trang**:

| Field | Default | Ý nghĩa |
|---|---|---|
| `term_extraction_enabled` | `True` | kill switch (giữ nguyên) |
| `max_suggested_terms_per_job` | **`20_000`** | van chống tràn DB (T1), **không phải** trần chất lượng |
| `term_min_occurrences` | `3` | áp dụng khi tài liệu ≥ **50.000 token** |
| `term_min_occurrences_short_doc` | **`2`** | áp dụng khi tài liệu < 50.000 token |

  Expert đề xuất ngưỡng theo **số trang** (≥100 trang). **Tôi đổi sang số token**, vì `total_pages`
  **là NULL cho EPUB theo đúng thiết kế** (§6.20.6 — không bịa số trang cho định dạng reflow) và
  cũng NULL cho một số nhánh khác; một ngưỡng dựa vào cột thường xuyên NULL sẽ âm thầm rơi vào
  nhánh sai. Số token luôn có sẵn vì ta vừa tokenize xong. Cơ sở giữ nguyên: đo thật cho thấy bản
  OCR 25 trang chỉ có 7 term ≥3 lần nhưng **12 term xuất hiện đúng 1 lần**.

##### T6. Golden metric — điều kiện để lần sau chỉnh ngưỡng còn đo được

`tests/fixtures/term_extraction/` phải chứa **trích đoạn** (không nhúng nguyên sách vào repo)
Figoni + Cauvain + **1 fixture Markdown có bảng HTML thật** (nhánh `parse_only`, T4 mục 1). Metric
chốt = **recall so với chính glossary user đã curate**: coi glossary là rỗng, chạy trích xuất, đếm
xem bao nhiêu term user đã tự tay thêm (và xuất hiện ≥ sàn) có mặt trong pool và ở hạng nào. Mỗi
lần đổi công thức/ngưỡng phải in bảng recall@40/100/300/500 như T0. Đây là ground truth tốt nhất
có sẵn vì nó phản ánh gu của **chính user** (YA-4.7), không phải của Tech Lead hay Expert.

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

### 6.19. US-21 — Hiển thị phiên bản

Backend `GET /api/version` đã có sẵn và **đúng** (`src/api/main.py`, đọc thẳng `pyproject.toml`).
Không cần thiết kế lại. Chỉ 1 sửa nhỏ bắt buộc và 1 ghi chú UI:

**S21-1 (bắt buộc, YA-5.1 của BA)**: `FastAPI(title="BB-Translation", version="0.1.0", ...)`
hardcode `0.1.0` và đó chính là số hiển thị trên `/docs` (OpenAPI) — mâu thuẫn với `1.2.7` mà
`/api/version` trả về. Sửa thành `version=_read_app_version()`. Một nguồn sự thật duy nhất.

**S21-2 (UI)**: nav bar cạnh chữ "BB-Translation" (BA-Q11 phương án B, đúng đề xuất trong PRD).
4 trang HTML tĩnh lặp nav nguyên si → **1 đoạn JS dùng chung** gọi `/api/version` một lần và điền
vào `<span id="app-version">` (YA-5.2), không sửa tay từng file. Lỗi mạng hoặc `"unknown"`
(YA-5.4) → để trống lặng lẽ, **không** để exception JS chặn phần còn lại của trang.

Không có quyết định kiến trúc nào khác cần ghi lại cho US-21.

---

### 6.20. US-22 — Dịch EPUB (THAY THẾ HOÀN TOÀN §6.7)

> **Trạng thái R5-01**: mục này **VERIFIED** — `bilingual_book_maker` đã được cài thật
> (`bbook-maker==1.1.0` từ PyPI, vào 1 venv riêng ngoài project), đã đọc source đã cài, đã chạy
> `--help` thật và đã **chạy thật 3 lần** trên 1 file EPUB thật. `ebooklib` đã được cài thật và đã
> round-trip thật trên cùng file đó. Mọi câu không có trích dẫn nguồn là suy luận thiết kế CỦA
> CHÚNG TA trên nền sự thật đã verify, không phải giả định về tool.
>
> Bản §6.7 cũ **SAI về mặt kết luận thiết kế** dù các tên cờ tình cờ đúng — xem cảnh báo đầu §6.7.

#### 6.20.1. Nguồn xác thực

**Môi trường verify** (2026-09-08):
- `uv venv --python 3.12` riêng, `uv pip install bbook_maker` → `bbook-maker==1.1.0`, kéo theo
  `anthropic==1.4.0`, `openai==2.54.0`, `ebooklib==0.20`, `beautifulsoup4==4.15.0`.
  **Tên package trên PyPI là `bbook_maker`, KHÔNG phải `bilingual_book_maker`** — `uv pip install
  bilingual_book_maker` báo "not found in the package registry".
- File EPUB thật dùng để đo: `data/uploads/9d436d7b-…_Baking with Sourdough - Sara Pitzer.epub`
  (2.017.999 byte, sách dạy làm bánh thật của chính user, đã có sẵn trong repo).
- Source đọc trực tiếp: `<venv>/lib/python3.12/site-packages/book_maker/{cli.py, loader/epub_loader.py,
  loader/helper.py, translator/__init__.py, translator/claude_translator.py,
  translator/chatgptapi_translator.py}`.
- Đối chiếu thêm: source nhánh `main` trên GitHub (`yihong0618/bilingual_book_maker`,
  `book_maker/cli.py`, fetch 2026-09-08).

**⚠️ Phát hiện quan trọng về version — bắt buộc PIN**: nhánh `main` trên GitHub **đã đổi CLI hoàn
toàn** so với bản PyPI 1.1.0. Trên `main`: không còn `--claude_key`/`--openai_key` (gộp thành
`--key`), có `--api_format {openai,anthropic,gemini,…}`, có `--glossary`, `--parallel-workers`,
`--quiet`, `--plan-classify`… Bản 1.1.0 trên PyPI **không có** cái nào trong số đó. Bất kỳ tài
liệu/blog/ký ức nào về CLI của tool này đều có thể đang nói về một trong hai bản khác nhau. Nếu
sau này quay lại phương án A, **phải pin version và verify lại từ đầu** (Protocol 5 mục 5).

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

##### **QUYẾT ĐỊNH: Phương án B.**

Ba lý do — **THỨ TỰ ĐÃ SẮP XẾP LẠI 2026-09-08 sau phản biện Domain Expert**: bản cũ đặt trọng
lượng lớn nhất lên B-03 (97,2%), mà đó lại là lý do **yếu nhất về tính tổng quát** (N=1 trên một
bulletin 35 trang, xem §6.20.3). Lý do thật sự bất biến theo sách là cấu trúc của chính tool A:

1. **A không có cơ chế chunk nào TƯƠNG THÍCH VỚI RESUME — bất kể sách nào.** Cơ chế
   chọn-một-phần-sách duy nhất của A là document-granular (**E-05**: tài liệu ngoài
   `--only_filelist` **bị xoá khỏi output**, xác nhận độc lập bởi Expert tại
   `epub_loader.py:384-391`) → muốn chunk thì phải tự ghép EPUB lại từ N bản output, tức là công
   ngang với tự viết writer. Cộng thêm **E-13**: trạng thái resume là pickle theo **chỉ số tuyến
   tính toàn sách** (Expert xác nhận `epub_loader.py:117,565,616` + `_process_paragraph:147-148`)
   → đổi tập `--only_filelist` là mọi chỉ số lệch. Hai cái này **loại trừ nhau**: A không thể vừa
   chunk vừa resume, trên bất kỳ cuốn sách nào. Đây là lý do nặng nhất vì nó không phụ thuộc mẫu.
2. **A hỏng im lặng theo đúng 3 cách dự án này đã bị 3 lần.** exit 0 khi lỗi (E-06, đã chạy thật ở
   E-07, Expert xác nhận `epub_loader.py:553-560`), đoạn rỗng thay bản gốc (E-09), lỗi cấp đoạn
   nuốt thành `None` (E-08). Bug #5 và Bug #2 đều là biến thể của đúng một câu: "báo completed,
   nội dung rỗng".
3. **B-03 là MINH HOẠ trên chính cuốn sách của user, không phải bằng chứng tổng quát.** Trên file
   thật này, 97,2% nội dung nằm trong 1 document → Lớp 3 với granularity "gần bằng cả cuốn" chính
   là kịch bản đã làm mất $6.50, chỉ khác quy mô. Con số đúng (Expert đo lại được 97,4%), nhưng
   **N=1 trên bulletin 35 trang** — nó chứng minh A thất bại **ở đây**, không chứng minh A thất
   bại nói chung.

Và một lý do cộng thêm (không phải để bác A, mà để chọn B): **B trả lại nhiều thứ hơn nó lấy** —
chi phí đo thật (`cost_source='metered'`, lần đầu tiên trong dự án), tái dùng nguyên
chunk/resume/cancel/cost-gate/glossary, và tạo ra **cặp EN↔VI thật** mà app nhìn thấy được, mở
khoá EC-20.1 cho US-20 sau này (§6.18.7 mục 2).

Kèm 1 phát hiện làm B rẻ hơn dự kiến: **không cần dùng writer của `ebooklib`.** B-06 cho thấy
`write_epub()` dời toàn bộ đường dẫn (`ops/` → `EPUB/`) và ghi lại OPF — vẫn mở được nhưng không
đúng tinh thần "giữ nguyên cấu trúc gốc" của BR-EPUB-01. Cách ghi đè tại chỗ bằng `zipfile`
(B-07) giữ **27/27** entry còn lại nguyên byte, giữ nguyên thứ tự entry và `mimetype` STORED-đầu-file
theo đúng OCF spec. Dùng `ebooklib` **chỉ để đọc**, `zipfile` để ghi.

#### 6.20.5. `EpubDocument` — module MỚI `src/services/epub_document.py` (spec cho Dev)

> ### ⚠️ MỤC NÀY ĐÃ BỊ §6.20.12 THAY THẾ MỘT PHẦN (sửa sau phản biện Domain Expert, 2026-09-08)
>
> **Còn nguyên hiệu lực**: khung `EpubDocument` (1 loader, nhiều projection), danh sách tag lấy
> unit, nguyên tắc `unit_id` ổn định/tất định, ghi ngược bằng `zipfile` không dùng
> `epub.write_epub()`, kiểm DRM ở `POST /api/upload`.
>
> **ĐÃ BỊ THAY THẾ — Dev KHÔNG được implement theo bản dưới đây:**
> - `text: str` (text thuần) → **inner-HTML** (X2, §6.20.12)
> - rule `extract()` bỏ `sup` → **CẤM** (X1, §6.20.12 + §6.21)
> - `doc_href` lấy thẳng từ `ebooklib` → **phải join với `opf_dir`** (X6, §6.20.12)
> - `ordinal` đếm sau khi lọc → **đếm trước khi lọc** (Y3, §6.20.12)
> - `write_translated()` bước 2/3 → bổ sung parser `xml`, strip `id` bản copy, file tạm (Y1/Y2/Y5)

```python
@dataclass(frozen=True)
class EpubUnit:
    unit_id: str        # ĐỊNH DANH ỔN ĐỊNH, xem dưới
    doc_href: str       # tên entry trong zip, vd "ops/xhtml/chapter01.html"
                        # ⚠️ X6: KHÔNG phải item.file_name của ebooklib — xem §6.20.12
    tag: str            # "p" | "h2" | "li" | ...
    ordinal: int        # thứ tự trong CHÍNH tài liệu đó, 0-based
    text: str           # ⚠️ ĐÃ ĐỔI (X2): inner-HTML, KHÔNG phải văn bản thuần đã strip


class EpubDrmError(RuntimeError): ...
class EpubParseError(RuntimeError): ...


class EpubDocument:
    @classmethod
    def load(cls, path: Path) -> "EpubDocument": ...
    @property
    def units(self) -> list[EpubUnit]: ...
    def full_text(self) -> str: ...          # dùng cho lọc glossary (6.6.5) và US-20
    @property
    def total_chars(self) -> int: ...
    def write_translated(
        self,
        translations: dict[str, str],        # unit_id -> văn bản tiếng Việt
        output_path: Path,
        bilingual: bool = False,
    ) -> None: ...
```

**Quy tắc chọn unit** (dùng CHUNG với §6.15 S15-8, một định nghĩa duy nhất):
- Duyệt tài liệu theo **thứ tự spine** (không theo thứ tự entry trong zip).
- Tag lấy: `p, h1, h2, h3, h4, h5, h6, li, blockquote, td, th, dt, dd, figcaption`.
- ~~Trước khi lấy text, `extract()` bỏ các thẻ con `sup`, `code`, `pre` (giống `exclude_translate_tags`
  mặc định của bbook_maker, E-01 — ý tưởng đúng, mượn lại).~~ **RULE NÀY BỊ XOÁ HOÀN TOÀN (X1,
  2026-09-08)** — nó phá định lượng công thức (`<sup>1</sup>/<sub>3</sub> cup` → `/3 cup`, đo trên
  6/6 dòng nguyên liệu thật). "Ý tưởng đúng, mượn lại" là một đánh giá **sai** của bản gốc: trên
  sách dạy làm bánh nó là ý tưởng sai. Thay bằng: **giữ nguyên mọi thẻ inline** (X2 — unit là
  inner-HTML nên `sup`/`sub` đi qua LLM nguyên vẹn, không cần rule nào cả). Xem §6.21.
- Bỏ unit nếu: rỗng sau `.strip()`, toàn chữ số/khoảng trắng, là URL, hoặc khớp `ISBN`.
- Node lồng nhau: nếu 1 `li` chứa `p`, chỉ lấy **node ngoài cùng** trong danh sách tag (tránh dịch
  2 lần cùng nội dung — chính là bug đã có mặt sẵn trong bbook_maker's `filter_nest_list`).

**`unit_id` phải ỔN ĐỊNH và TẤT ĐỊNH** — đây là chốt của resume (BR-CHUNK-05):
`unit_id = f"{doc_href}#{ordinal}"`, với `ordinal` = chỉ số của node trong danh sách unit **của
chính tài liệu đó**, theo thứ tự tài liệu. **⚠️ SỬA (Y3, 2026-09-08): `ordinal` phải đếm trên MỌI
node thuộc danh sách tag — TRƯỚC khi áp các drop rule** (rỗng/toàn số/URL/ISBN), xem §6.20.12 Y3.
- **KHÔNG** dùng hash nội dung: sau khi dịch, nội dung đổi → resume tra không ra.
- **KHÔNG** dùng chỉ số tuyến tính toàn sách: chỉ cần đổi bộ lọc tag là mọi id lệch (đây đúng là
  cách bbook_maker làm, E-13, và đúng lý do resume của nó không chunk được).
- Bắt buộc có test: `load()` cùng 1 file 2 lần → danh sách `unit_id` **giống hệt** (R6-02).

**`write_translated()` — ghi đè tại chỗ bằng `zipfile`** (B-07):
1. Nhóm `translations` theo `doc_href`.
2. Mở zip gốc; với mỗi `doc_href` có bản dịch: parse lại bằng `BeautifulSoup` (**⚠️ Y1: bắt buộc
   `features="xml"`**, xem §6.20.12), đi đúng danh sách unit theo `ordinal`, và:
   - `bilingual=False` (BR-EPUB-01 mặc định): thay nội dung của node bằng **fragment HTML đã dịch**
     (X2), **giữ nguyên tag, class, style**. ~~và các thẻ con đã `extract()` được chèn lại đúng
     chỗ~~ — không còn `extract()` nào (X1), nên không có gì phải chèn lại.
   - `bilingual=True`: chèn 1 node **copy** ngay sau node gốc, node copy mang bản dịch (đúng cách
     `insert_trans` của bbook_maker làm, E-02 — ý tưởng đúng, tự cài). **⚠️ Y2: bản copy phải strip
     mọi `id`, phải mang `lang="vi"` + `class="bb-vi"`, và `td`/`th` chèn BÊN TRONG ô** — xem
     §6.20.12 Y2/X3.
3. Ghi zip mới: `mimetype` là entry **đầu tiên** và **`ZIP_STORED`** (OCF spec), mọi entry khác giữ
   nguyên `filename` + `date_time` + thứ tự, `ZIP_DEFLATED`. Entry không đổi thì copy nguyên bytes.
   **⚠️ Y5: ghi ra `<output>.epub.tmp` rồi `os.replace()`**, không ghi thẳng tên thật.
4. **KHÔNG** gọi `epub.write_epub()`.
5. **⚠️ Y1 (MỚI): trước khi ghi mỗi XHTML đã sửa, validate `ET.fromstring(output_bytes)`.** Không
   well-formed → chunk/job `failed` với thông báo rõ. **Tuyệt đối không ghi XHTML hỏng vào EPUB** —
   reader XHTML strict (Apple Books) hiện **trang trắng, không báo lỗi**: đúng dạng silent failure.

**DRM (EC-22.1 / YA-6.6)**: `load()` raise `EpubDrmError` nếu zip có `META-INF/encryption.xml`
**và** có ít nhất một `<EncryptedData>` trỏ tới tài nguyên **không phải font** (`.ttf/.otf/.woff*`)
— vì `encryption.xml` cũng được dùng hợp lệ cho font obfuscation, không chỉ DRM. Kiểm tra này chạy
ở **`POST /api/upload`** (không đợi tới lúc dịch): reject 400 với đúng câu AC-22.3
*"File EPUB có DRM, cần gỡ DRM trước khi dịch"*. File mẫu B-08 không có encryption.xml → là
negative-case fixture sẵn có.

#### 6.20.6. Đơn vị đo "kích thước" cho EPUB, và cost gate

Câu hỏi PM đặt: số chương? tổng ký tự? số từ? — **Cả ba đều cần, cho ba mục đích khác nhau:**

| Đại lượng | Dùng để làm gì | Lưu ở đâu |
|---|---|---|
| **Tổng ký tự** (`total_chars`) | Đầu vào công thức ước tính chi phí | không lưu cột riêng; tính lại từ `EpubDocument` |
| **Số unit** (`len(units)`) | Đơn vị chunk, đơn vị progress, hiển thị UI | **cột mới `Job.total_units`** |
| **Số request LLM** | `segment_count` của công thức chi phí | tính từ chunk plan |
| Số chương (`ITEM_DOCUMENT`) | **không dùng** làm đơn vị đo | — |

**`total_pages` giữ NULL cho EPUB.** Không bịa số trang cho một định dạng reflow — đó chính là
loại "trôi ngữ nghĩa" đã sinh ra Bug #5. `upload.py:127-134` giữ nguyên. UI hiện `-` ở cột số
trang (đúng AC US-19) và hiện `total_units` ở chỗ riêng nếu muốn.

```python
# src/models/job.py
total_units: int | None = Field(default=None)
# Số đơn vị dịch (đoạn văn/heading/mục list) của 1 job EPUB — thay cho
# total_pages, vốn vô nghĩa với định dạng reflow. NULL cho mọi job PDF.
# BREAKING SCHEMA CHANGE (cùng đợt với `finished_at` §6.17.2).
```

**Cost gate cho EPUB — tái dùng `estimate_job_cost_v2()`, KHÔNG viết công thức thứ hai.**
`src/core/cost_gate.py::estimate_translation_cost()` hiện hardcode đường PDF
(`_extract_full_text` → PyMuPDF, `_count_pdf_pages`, `_count_text_segments`). Rẽ nhánh theo
`file_type` **ở đúng 1 chỗ** — hàm này — rồi gọi **cùng một `estimate_job_cost_v2()`**:

```
if file_type == epub:
    doc = EpubDocument.load(file_path)
    full_text          = doc.full_text()
    source_text_chars  = doc.total_chars   # ⚠️ X5: ƯỚC THẤP 29% — xem hộp ngay dưới bảng
    plan               = plan_epub_chunks(doc.units)          # list[EpubChunkPlan]
    llm_request_count  = sum(len(c.requests) for c in plan)   # SỐ REQUEST, không phải số đoạn
    segment_count      = llm_request_count
    total_pages        = None
    total_units        = len(doc.units)
else:
    ... đường PDF hiện tại, không đổi ...
prompt_text = await build_prompt_text(..., only_terms_present_in=full_text, ...)
estimate    = estimate_job_cost_v2(source_text_chars, segment_count, prompt_overhead_chars, provider)
```

> ⚠️ **`segment_count` cho EPUB mang nghĩa KHÁC với PDF — Dev bắt buộc đọc kỹ.**
> Với pdf2zh/babeldoc, prompt được gửi lại cho **từng đoạn văn** (§6.6.1 F6), nên
> `segment_count` = số đoạn. Với phương án B, app **tự gộp nhiều unit vào 1 request**, nên overhead
> prompt trả **1 lần mỗi REQUEST**. Đo trên sách thật (B-04, 384 unit, 52.369 ký tự, prompt
> overhead 1.800 ký tự, `deepseek-v4-flash`):
> - nếu dùng nhầm `segment_count = 384` (số đoạn): **185.892 input token**
> - đúng `segment_count ≈ 18` (số request, gộp ~3.000 ký tự/request): **21.192 input token**
>
> Sai lệch **8,8×**. §6.11.6 cho phép ước cao hơn thật nhưng **không** cho phép ước sai bản chất:
> ước cao 8,8× sẽ khiến cost gate Lớp 2 **chặn nhầm** những cuốn sách hoàn toàn bình thường.
> `estimate_job_cost_v2()` **không đổi một dòng nào** — chỉ đầu vào `segment_count` khác nghĩa,
> và đó phải là một biến được đặt tên rõ (`llm_request_count`) chứ không phải một con số truyền thẳng.

> ### ⚠️ X5 — SỬA SAU PHẢN BIỆN DOMAIN EXPERT (2026-09-08): `source_text_chars = doc.total_chars` ƯỚC **THẤP**
>
> Đây là vi phạm trực tiếp §6.11.6 ("được ước cao, **cấm** ước thấp"), nằm đúng trên lớp bảo vệ tài
> chính đã từng để mất $6.50. Expert đo được envelope JSON; **Tech Lead đo lại độc lập và tìm thêm
> một số hạng thứ hai mà Expert bỏ sót** (Expert chỉ đo trên text thuần, không tính chi phí của
> chính X2 — chuyển sang inner-HTML).
>
> Số đo lại (384 unit thật của `Baking with Sourdough`, `json.dumps(ensure_ascii=False)`, script
> `envelope.py` trong scratchpad phiên này):
>
> | Cấu hình payload | Content chars | Payload chars | Overhead |
> |---|---|---|---|
> | `unit_id` dài (`ops/xhtml/chapter01.html#123`) + text thuần | 52.369 | 72.197 | **+37,9%** (khớp +38% Expert đo) |
> | id ngắn `0..N` + text thuần | 52.369 | 62.627 | **+19,6%** (khớp +20% Expert đo) |
> | id ngắn + **inner-HTML** (cấu hình THẬT sau X2) | 57.247 | **67.577** | **+29,0% so với `doc.total_chars`** |
>
> Riêng việc đổi sang inner-HTML (X2) đã cộng **+9,3%** ký tự nội dung (57.247 vs 52.369) — số hạng
> này **không có trong phản biện của Expert**, và nếu chỉ áp công thức của Expert thì vẫn còn ước
> thấp ~9%.
>
> **Chốt — 2 hằng số có tên, đặt cạnh `EPUB_CHUNK_CHAR_BUDGET` trong `src/core/chunking.py`:**
> ```python
> EPUB_INLINE_MARKUP_FACTOR        = 1.15   # inner-HTML vs text thuần; đo 1.093, làm tròn lên
> EPUB_JSON_ENVELOPE_CHARS_PER_UNIT = 30    # đo 26,7 ký tự/unit (id ngắn), làm tròn lên
>
> source_text_chars = int(doc.total_chars * EPUB_INLINE_MARKUP_FACTOR) \
>                   + len(doc.units) * EPUB_JSON_ENVELOPE_CHARS_PER_UNIT
> ```
> Kiểm chứng trên chính cuốn sách này: `52.369 × 1,15 + 384 × 30 = 71.744` vs payload thật
> `67.577` → **1,06× — cao hơn thật, đúng chiều §6.11.6 cho phép**. So với `doc.total_chars` trần
> trụi thì là 1,37×.
>
> **Bắt buộc dùng id ngắn `0..N` trong request**, map ngược sang `unit_id` ở phía app (giảm một nửa
> envelope, và giảm rủi ro model gõ sai một id dài 30 ký tự). Xem X4 (§6.20.12) cho contract.
>
> **Không sửa `estimate_job_cost_v2()`.** Nó suy `output_tokens` từ chính `source_text_chars`
> (`cost_estimator.py:167`), nên `source_text_chars` đã nở 1,37× kéo theo ước output nở 1,37× —
> trong khi overhead output thật chỉ ~+7% (Expert đo). Tức là ước output **cao hơn thật**, hợp lệ
> theo §6.11.6. **Reviewer không được "sửa" điểm này thành ước sát hơn** — ước sát ở lớp cost gate
> là đúng thứ RC-2 của sự cố $6.50.

Sửa kèm (bỏ chặn cứng EPUB đang có):
- `GET /api/jobs/{id}/cost-estimate` và `POST /api/estimate`: bỏ 2 nhánh `if file_type == "epub":
  raise 400` (`src/api/routes/jobs.py`), và bỏ điều kiện `if job.total_pages is None: raise 400`
  → đổi thành: EPUB hợp lệ khi có `total_units`, PDF hợp lệ khi có `total_pages`.
- `CostEstimateResponse.total_pages` đổi thành `int | None`, thêm `total_units: int | None = None`.

#### 6.20.7. Chunk theo chương — mô hình chốt

**BR-EPUB-02 nói "đơn vị chunk = chương". Thực hiện: chunk = một dãy unit liên tiếp theo thứ tự
spine, cắt ƯU TIÊN tại ranh giới tài liệu, nhưng KHÔNG bị ràng buộc bởi nó.** B-03 là lý do: một
"chương" thật có thể là 97% cuốn sách; nếu chunk cứng theo tài liệu thì cơ chế trần chi phí không
tồn tại trên chính cuốn sách của user.

`src/core/chunking.py` thêm (KHÔNG đụng `calculate_chunks`/`plan_chunks` của PDF):

```python
EPUB_CHUNK_CHAR_BUDGET = 8_000        # ~7 chunk cho cuốn 52k ký tự (B-04)
EPUB_REQUEST_CHAR_BUDGET = 3_000      # số ký tự tối đa gộp vào 1 request LLM
EPUB_UNIT_HARD_MAX_CHARS = 10_000     # MỚI (Y4): unit vượt ngưỡng này -> job failed, xem §6.20.12

@dataclass(frozen=True)
class EpubChunkPlan:
    index: int
    unit_start: int      # chỉ số unit toàn sách, 0-based, INCLUSIVE
    unit_end: int        # INCLUSIVE
    requests: list[tuple[int, int]]   # các lát (start, end) trong phạm vi chunk này

def plan_epub_chunks(units, char_budget=EPUB_CHUNK_CHAR_BUDGET,
                     request_budget=EPUB_REQUEST_CHAR_BUDGET) -> list[EpubChunkPlan]:
    """Cắt tại ranh giới tài liệu khi tài liệu tiếp theo còn vừa ngân sách;
    khi 1 tài liệu tự nó vượt ngân sách, cắt tiếp bên trong nó theo đúng ranh
    giới unit (không bao giờ cắt giữa 1 đoạn văn)."""
```

> **Z3 (bổ sung sau phản biện Domain Expert 2026-09-08) — gọi đúng tên hai ngân sách, vì chúng
> phục vụ 2 mục đích khác nhau và Dev rất dễ tưởng là một.**
> - `EPUB_CHUNK_CHAR_BUDGET = 8.000` là **granularity của checkpoint chi phí (Lớp 3)**, KHÔNG phải
>   giới hạn context. Ý nghĩa thật: mức "vượt trần" tối đa mà Lớp 3 có thể để lọt = đúng 1 chunk
>   ≈ $0,003 (DeepSeek) / ≈ $0,05 (Claude Sonnet).
> - `EPUB_REQUEST_CHAR_BUDGET = 3.000` là **giới hạn kích thước 1 lời gọi LLM**: ≈ 900 token nội
>   dung + envelope + ~450 token system prompt ≈ 1,4k in / ≈ 2k out — cách xa `max_tokens=8192`
>   (mặc định của **cả 4 provider**: `claude_provider.py:42`, `openai_provider.py:45`,
>   `deepseek_provider.py:37`, `gemini_provider.py:39` — tự đọc lại code xác nhận).
> - Trade-off Expert chỉ ra, ghi lại để đừng quên: 18 request × ~450 token system prompt ≈ 8k token
>   overhead ≈ **40% token nguồn**. Nếu spike R5-02 cho thấy JSON contract ổn định, **cân nhắc nâng
>   `EPUB_REQUEST_CHAR_BUDGET` lên 5.000–6.000** để giảm một nửa overhead này. **Không nâng trước
>   spike** — mỗi lần nâng là tăng lượng nội dung mất khi 1 request hỏng.
> - Cả 3 hằng số phải nằm ở `Settings` (`.env`), không chôn trong code.

**Không có overlap** (khác BR-CHUNK-03 của PDF). Lý do: overlap của PDF tồn tại vì pdf2zh cắt theo
**trang**, mà một câu có thể vắt qua 2 trang. Ở EPUB mỗi unit là một đoạn văn **hoàn chỉnh** —
không có gì bị cắt ngang để phải nối lại. Ghi vào known limitation: bản dịch không thấy ngữ cảnh
đoạn liền trước ở ranh giới chunk. Nếu về sau thấy cần, thêm `context_units` (gửi kèm làm ngữ
cảnh, **không** dịch lại) là mở rộng thuần cộng thêm.

**Tái dùng bảng `chunks`, thêm 2 cột thay vì mượn nghĩa `page_start`/`page_end`:**

```python
# src/models/chunk.py
page_start: int | None = Field(default=None)   # ĐỔI: nullable (NULL cho EPUB)
page_end:   int | None = Field(default=None)   # ĐỔI: nullable (NULL cho EPUB)
unit_start: int | None = Field(default=None)   # MỚI: NULL cho PDF
unit_end:   int | None = Field(default=None)   # MỚI: NULL cho PDF
```

Cố ý **không** nhồi chỉ số unit vào `page_start/page_end`. Một cột tên `page_start` mà thực ra
chứa chỉ số đoạn văn là đúng loại bẫy mà mọi lần đọc code sau này sẽ vấp — và dự án này đã trả giá
2 lần cho "cùng một biến, hai ý nghĩa" (Bug #5, và `cost_source` ở RC-4).

#### 6.20.8. `EpubTranslateRunner` + luồng `run_job()` cho EPUB (spec cho Dev)

Bỏ `EpubNotSupportedError` ở Step 1. Thay bằng rẽ nhánh **ở đúng 1 chỗ**, giống S15-1:

```
run_job(job_id):
    if job.job_type == "parse_only":  return await self.run_parse_only(...)     # §6.15
    if job.file_type == FileType.EPUB: return await self.run_epub_job(...)      # §6.20
    # ... Step 1..10 hiện tại, nguyên vẹn, chỉ dành cho PDF
```

`run_epub_job()` — cùng khung xương với `run_job()` để mọi cơ chế đã verify sống được tái dùng
nguyên trạng:

| Bước | Nội dung | Tái dùng gì |
|---|---|---|
| E1 | `doc = EpubDocument.load(job.file_path)`; `job.total_units = len(doc.units)` | §6.20.5 |
| E2 | `full_text = doc.full_text()` → lọc glossary theo tài liệu | `build_prompt_snippet(only_terms_present_in=…)` §6.6.5, nguyên vẹn |
| E3 | `system_prompt = await build_system_prompt(glossary_manager, project_id=job.batch_id)` | `prompt_builder.py` đã có. **KHÔNG** dùng `write_prompt_file()` (đó là contract `${text}` của pdf2zh) |
| E4 | `plan = plan_epub_chunks(doc.units)` → `_load_or_create_chunks()` | §6.20.7 + hàm resume đã có |
| E5 | Với mỗi chunk chưa `completed`: `_process_epub_chunk()` | ↓ |
| E6 | Sau MỖI chunk: `progress_tracker.update()` → **Lớp 3 cost accumulator** → **check `cancel_requested`** | **copy nguyên thứ tự 3 bước của `run_job()` Step 7**, không viết lại |
| E7 | Gộp mọi `chunk.output_path` (JSON) → `translations: dict[unit_id, str]` | ↓ |
| E8 | `doc.write_translated(translations, merged_path, bilingual=…)` | §6.20.5 |
| E9 | **Guard BR-EPUB-05** (mới, xem dưới) | tinh thần BR-OCR-03 |
| E10 | `job.output_path`, `actual_cost`, `cost_source='metered'`, `finished_at`, `completed` | §6.17.2 |

`_process_epub_chunk()`:
1. `chunk.status='translating'`.
2. Với mỗi lát request `(start, end)` trong `chunk.requests` — **tuần tự**:
   - Dựng payload: JSON array ~~`[{"id": "<unit_id>", "text": "<EN>"}, …]`~~ → **SỬA (X4+X5,
     2026-09-08): `[{"id": "<i cục bộ 0..N>", "html": "<inner-HTML EN>"}, …]`**, id ngắn cục bộ
     trong request, app tự map ngược sang `unit_id`. Xem §6.20.12 X4 cho contract đầy đủ.
   - ~~`result = await with_retry(lambda: provider.translate(payload_json, system_prompt, "en", "vi"))`~~
     → **SỬA (X4): `system_prompt` phải là `build_epub_batch_prompt(...)`**, KHÔNG phải
     `build_system_prompt()` trần — bản trần **không có bất kỳ chỉ thị JSON nào** (tự đọc
     `src/core/prompt_builder.py` xác nhận: 4 chỗ khớp "json" đều là **comment** mô tả contract của
     babeldoc, do babeldoc tự nối thêm, không phải nội dung app gửi). `with_retry`
     (`src/utils/retry.py`) và `RateLimitError` đã có từ Increment 3 — **nhưng xem Y6 (§6.20.12):
     `with_retry` hiện KHÔNG retry lỗi 5xx**, phải sửa trước khi nhánh EPUB dùng nó.
   - Parse JSON trả về `{"<id>": "<VI inner-HTML>", …}`. **Nếu thiếu id nào** → gọi lại **riêng lẻ**
     cho đúng các id thiếu (tối đa 1 vòng). **Nếu vẫn thiếu → chunk `failed`.**
     **TUYỆT ĐỐI KHÔNG ghi chuỗi rỗng cho unit thiếu bản dịch** — đó là đúng E-09, lỗi mà cả
     phương án A lẫn Bug #5 đều mắc.
   - Cộng dồn `result.input_tokens`/`output_tokens`/`estimated_cost_usd` **thật**.
3. Ghi `data/processing/{job_id}/chunk_{i}/units.json` = `{unit_id: vi_text}`; `chunk.output_path`
   trỏ vào đó (song song với `.pdf` của nhánh PDF → merge/resume/xoá job không cần biết gì mới).
4. `chunk.api_tokens_used`/`api_cost` = **số đo thật**, không phải `estimate_chunk_cost()`.
5. `chunk.status='completed'`.

**BR-EPUB-03 (không double-translation)**: phương án B chỉ có **đúng một** điểm gọi LLM
(`provider.translate()` ở bước 2) và **không dùng `bilingual_book_maker` ở bất kỳ đâu**. Nguyên tắc
§6.6.2 R1 được thoả một cách hiển nhiên. Reviewer kiểm bằng grep: trong luồng EPUB không được có
lời gọi subprocess nào.

**`cost_source = 'metered'` cho EPUB** — lần đầu tiên trong dự án. Hệ quả UI (§6.11.4 Lop 0 mục 2):
job EPUB **không** hiện cảnh báo "ước tính, có thể sai lệch nhiều lần"; job PDF vẫn hiện. Frontend
đã rẽ theo `cost_source` từ trước, không cần logic mới.

**BR-EPUB-05 (mới — guard chống im lặng ra file rỗng, đề xuất PM bổ sung vào PRD §4.12)**: sau E8,
mở lại file EPUB **vừa ghi** bằng `EpubDocument.load(merged_path)` và assert:
- tổng số ký tự > 0, **và**
- ~~số unit của file output **bằng** số unit của file input (không mất chương)~~, **và**
- ~~ít nhất 90% unit có nội dung **khác** bản gốc.~~

> ### ⚠️ X3 — SỬA SAU PHẢN BIỆN DOMAIN EXPERT (2026-09-08): guard trên MÂU THUẪN với `bilingual=True`
>
> §6.20.11 mục 2 đã chốt **`bilingual=True` là mặc định** cho EPUB. Nhưng `bilingual=True` **chèn
> thêm** 1 node sau mỗi unit → `load()` file output đếm được **~2×** số unit, và ~50% unit (các bản
> gốc EN) có nội dung **giống hệt** bản gốc. Guard như viết ở trên sẽ **fail 100% job bilingual**
> — và hậu quả thực tế còn tệ hơn thế: Dev sẽ "nới" guard cho qua, và ta **mất luôn** lớp bảo vệ
> duy nhất chặn được lớp lỗi Bug #5. Expert đúng hoàn toàn, tôi không có phản biện nào.
>
> **Bản chốt — điều kiện phụ thuộc `bilingual`, và dựa trên MỘT dấu hiệu tường minh:**
>
> Điều kiện tiên quyết (Y2): mọi node bản dịch chèn thêm **bắt buộc** mang `lang="vi"` **và**
> `class="bb-vi"`. Đây không phải để cho đẹp — nó là **thứ duy nhất** làm cho "unit gốc" và "unit
> dịch" phân biệt được ở lần `load()` sau, tức là thứ làm guard này tồn tại được.
> `EpubDocument.load()` **bỏ qua** node mang `class="bb-vi"` khi liệt kê `units` (mặc định).
> Hệ quả tốt kèm theo: upload lại chính file EPUB song ngữ đã dịch sẽ **không dịch đôi**.
>
> | Điều kiện | `bilingual=False` | `bilingual=True` |
> |---|---|---|
> | tổng ký tự > 0 | ✔ | ✔ |
> | `len(units_output)` == `len(units_input)` | ✔ (units_output đã bỏ qua `bb-vi`, nhưng ở đây không có) | ✔ (**vì `load()` bỏ qua `bb-vi`** — đây là chỗ dấu hiệu tường minh trả công) |
> | ≥90% unit khác bản gốc | ✔ | ✖ **thay bằng**: số node `bb-vi` ≥ 90% × `len(units_input)` **VÀ** ≥90% cặp (gốc, `bb-vi` liền sau) có nội dung text **khác nhau** |
> | XHTML well-formed (Y1) | ✔ | ✔ |
>
> Cặp (gốc, `bb-vi`) khác nhau là điều kiện **không thể bỏ**: thiếu nó, một job mà LLM trả nguyên
> văn tiếng Anh cho mọi unit vẫn qua guard (đủ số node, đủ ký tự) — đúng shape "báo completed, nội
> dung sai" của Bug #5, chỉ đổi từ "rỗng" sang "chưa dịch".

Không đạt → `job.status='failed'` với thông báo rõ. Đây là bản EPUB của BR-OCR-03, và là điều kiện
duy nhất chặn được đúng lớp lỗi đã làm ta mất 3 vòng QA ở nhánh PDF scan.

**Concurrency**: v1 **tuần tự** trong mỗi chunk, **không AIMD**. Lý do: AIMD (§6.12) được xây quanh
`--thread` của pdf2zh và quanh việc *đoán* tín hiệu rate-limit bằng cách grep stdout của subprocess.
Ở đây app gọi API trực tiếp nên nhận `RateLimitError` **thật** — cơ chế backoff của `with_retry` là
đủ và đúng hơn. Thêm setting `epub_translate_concurrency: int = 1` (`.env`-only, chưa dùng) làm
chỗ móc cho tương lai. Known limitation: sách rất lớn sẽ chậm hơn nếu chạy song song được — nhưng
so với 2.859 giây/25 trang của babeldoc (§6.14.6) thì đây không phải nút thắt của v1.

#### 6.20.9. Data lineage tường minh (Protocol 6 — R6-01)

| Bước | Artifact tạo ra (tên biến/file cụ thể) | Bước sau đọc CHÍNH XÁC cái gì |
|---|---|---|
| 1. `POST /api/upload` | `upload.file_path` (`data/uploads/{id}_{name}.epub`), kiểm DRM tại đây | (2) |
| 2. `EpubDocument.load(job.file_path)` | `doc.units: list[EpubUnit]` (mỗi cái có `unit_id` tất định) | (3), (4), (7) |
| 3. `doc.full_text()` | `full_text: str` | (4) lọc glossary, (5) ước chi phí |
| 4. `build_system_prompt(...)` với glossary đã lọc theo `full_text` | `system_prompt: str` | (6) — truyền **thẳng** vào `provider.translate()` |
| 5. `plan_epub_chunks(doc.units)` | `list[EpubChunkPlan]` với `unit_start`/`unit_end`/`requests` | (6) và `chunks` rows |
| 6. `_process_epub_chunk()` | `data/processing/{job_id}/chunk_{i}/units.json` = `{unit_id: vi}`; `chunk.api_cost` = **token thật** | (7), và Lớp 3 accumulator |
| 7. `doc.write_translated(translations, merged_path)` | `data/outputs/{job_id}/translated_vi.epub` | (8) |
| 8. Guard BR-EPUB-05 | đọc lại **chính `merged_path`**, không phải `translations` trong bộ nhớ | `job.output_path` |

**Hai sợi dây dễ đứt nhất, phải có assertion giá trị cụ thể (R6-02):**
- **(2) → (7)**: `write_translated()` phải nhận `translations` có key là **`unit_id` sinh từ CÙNG
  một lần `load()`** với lúc dịch. Nếu Dev `load()` lại lần thứ hai với bộ lọc tag khác, mọi
  `unit_id` lệch và bản dịch rơi vào hư không — job vẫn "completed", file vẫn mở được, nội dung vẫn
  tiếng Anh. Đây là **Bug #5 tái sinh dạng EPUB**. Test bắt buộc:
  `write_translated.assert_called_with(translations=<dict có key khớp đúng doc.units[i].unit_id>, ...)`.
- **(6) → (7)**: merge phải đọc `chunk.output_path` của **mọi** chunk `completed`, không chỉ chunk
  vừa chạy — test resume: chạy 2 chunk, giả lập crash, chạy lại, assert file output chứa bản dịch
  của **cả hai**.
- **(2) → (7) sợi dây thứ 3, BỔ SUNG sau phản biện (X6, 2026-09-08)**: `doc_href` mà `load()` sinh
  ra phải là **tên entry có thật trong zip**. Đây là một Bug #5 dạng EPUB đã đóng gói sẵn: nếu Dev
  dùng thẳng `item.file_name` của `ebooklib`, vòng ghi so `info.filename == doc_href` sẽ **không
  khớp entry nào**, mọi entry được copy nguyên → **output == input**, `status='completed'`, file mở
  được, nội dung nguyên tiếng Anh. **Test bắt buộc (R6-02), assert giá trị cụ thể**:
  `assert all(u.doc_href in zipfile.ZipFile(path).namelist() for u in doc.units)` trên file EPUB
  thật. Xem §6.20.12 X6 cho cách dựng `doc_href` đúng.
- **(4) → (6) sợi dây thứ 4, BỔ SUNG (X4)**: `system_prompt` truyền vào `provider.translate()`
  phải là kết quả của `build_epub_batch_prompt()` (có contract JSON), **không** phải
  `build_system_prompt()` trần. Test assert **nội dung**: chuỗi prompt thật gửi đi phải chứa marker
  contract JSON, không chỉ `assert translate.awaited`.

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

#### 6.20.12. Final Decision sau phản biện Domain Expert (2026-09-08)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement.
**Quan hệ tài liệu**: mục này **thay thế (supersede)** các phần của §6.20.5 / §6.20.6 / §6.20.7 /
§6.20.8 / §6.20.9 / §6.20.10 đã được đánh dấu ⚠️ tại chỗ. Mọi phần khác của §6.20 **giữ nguyên
hiệu lực**. Khi mâu thuẫn, **mục này thắng**.

**Hướng kiến trúc KHÔNG đổi**: Phương án B (`ebooklib` đọc + Translation Engine nội bộ + `zipfile`
ghi) đứng vững sau phản biện. Expert tự đối chiếu 7/14 claim `bbook_maker` vào source thật và toàn
bộ 8 số đo B-01..B-08 — tất cả đúng. Không mở lại phương án A.

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

##### X1 — `extract()` bỏ `<sup>` — GIẢI QUYẾT

**Chấp nhận hoàn toàn phát hiện của Expert, nhưng KHÔNG dùng cách sửa của Expert** (xem N-1).

- **Nhánh dịch EPUB (§6.20)**: rule `extract()` bị **xoá**, và không thay bằng rule nào cả — vì X2
  đã chuyển unit sang inner-HTML, `<sup>`/`<sub>` đi qua LLM **nguyên vẹn** rồi được ghi lại
  nguyên vẹn. Fidelity = 100%, không cần chuyển đổi biểu diễn. Đây là lý do X1 và X2 phải sửa
  **cùng một lúc**: sửa riêng X1 (bỏ `extract`) mà vẫn lấy text thuần thì `get_text()` vẫn cho ra
  `1/3` dính liền số nguyên → vẫn ra `11/3`.
- **Nhánh Markdown parse-only (§6.15 nhánh EPUB)**: ở đó **buộc** phải chiếu HTML → text, nên phải
  có quy tắc chuyển đổi tường minh. Toàn bộ quy tắc đó nằm ở **§6.21** (mục dùng chung, vì nó là
  yêu cầu xuyên suốt của user 2026-09-08 về công thức toán/lý/hoá, không riêng công thức bánh).
- **Prompt (X4) phải nói rõ**: không được đổi/xoá `<sup>`/`<sub>` và không được đổi con số. Rule
  "BẤT BIẾN NỘI DUNG" của `build_system_prompt()` chỉ có nghĩa khi LLM **nhìn thấy** thứ cần giữ.

##### X2 — Inner-HTML thay vì text thuần — GIẢI QUYẾT

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

**Chốt**: `EpubUnit.text` = inner-HTML (`"".join(str(c) for c in node.children)`). Ghi ngược: parse
fragment bản dịch bằng bs4 rồi `node.clear()` + append children của fragment.

**TỪ CHỐI phương án giảm scope của Expert** (`get_text("\n")` + tái tạo `<br/>`): nó cứu được dòng
nhưng vẫn mất 214 `<strong>` — tức là vẫn là một bản "nửa nạc nửa mỡ" của đúng lỗi vừa sửa xong ở
PDF, và sẽ phải làm lại lần thứ hai. Chi phí thật của bản đầy đủ là +9,3% token (N-2), đã tính vào
X5. Không có lý do kỹ thuật để làm nửa vời.

##### X3 — Guard BR-EPUB-05 vs `bilingual=True` — GIẢI QUYẾT tại §6.20.8 (bảng 4 điều kiện)

##### X4 — Contract JSON app↔LLM — GIẢI QUYẾT (thiết kế mới, chưa từng có)

Xác nhận độc lập: `build_system_prompt()` **không có chỉ thị JSON nào**; 4 chỗ khớp "json" trong
`src/core/prompt_builder.py` (dòng 27, 241, 244, 246) đều là **comment** mô tả contract mà
*babeldoc* tự nối thêm phía sau. `OpenAIProvider.translate()` gửi user message
`f"Translate from {source_lang} to {target_lang}:\n\n{text}"` (`openai_provider.py:66-72`). Tức là
"Parse JSON trả về" ở §6.20.8 bản gốc là một **mong muốn**, không phải contract.

**Ràng buộc kiến trúc phải tôn trọng**: `provider.translate(text, glossary_prompt, src, tgt)` là
interface chung của **cả 5 provider** (Increment 3, đã verify sống). **Không đổi signature** cho
riêng EPUB — đổi là phải sửa 5 file provider và phá lại thứ đã verify. Hệ quả: contract JSON phải
nằm **hoàn toàn trong system prompt**, và payload đi vào tham số `text` (sẽ bị prefix
`"Translate from en to vi:\n\n"` — vô hại, thậm chí có lợi vì nó nói đúng việc cần làm).

**`build_epub_batch_prompt(glossary_prompt: str) -> str`** — hàm MỚI trong `prompt_builder.py`,
3 phần nối nhau:

1. `glossary_prompt` hiện có (glossary + unit conversion + typography) — **không sửa một chữ**.
2. **Khối contract** (mới), nêu tường minh 6 điều:
   - Input là JSON array `[{"id": "0", "html": "…"}, …]`; `id` là chuỗi chứa số.
   - Output **phải** là JSON object `{"0": "…", "1": "…"}` — **đúng và đủ mọi `id`** đã nhận, không
     thêm id lạ, không bọc trong markdown code fence, không kèm lời dẫn.
   - Chỉ dịch **text node**; **giữ nguyên từng thẻ HTML inline** (`strong, em, b, i, sup, sub, br,
     a, span, small`) đúng số lượng và đúng vị trí tương đối.
   - **Không đổi, không làm tròn, không chuyển đổi bất kỳ CON SỐ nào**; `<sup>`/`<sub>` giữ nguyên
     là `<sup>`/`<sub>` (X1, §6.21).
   - Không dịch nội dung trong `<code>`/`<pre>`.
   - Nếu 1 mục không dịch được → trả **nguyên văn bản gốc** cho id đó; **tuyệt đối không trả chuỗi
     rỗng** (E-09 — đây đúng cách phương án A và Bug #5 hỏng).
3. **Đúng 1 cặp ví dụ** (one-shot) có đủ: 1 thẻ inline, 1 con số, 1 `<sup>`/`<sub>`.

**Parser trả về (`parse_epub_batch_response`)** — phải chịu được thực tế, không chỉ trường hợp đẹp:
strip markdown code fence (```` ```json ````), strip khoảng trắng/lời dẫn trước-sau, chấp nhận `id`
kiểu `str` lẫn `int`, và **validate**: đủ id, không id lạ, mỗi value non-empty. Thiếu id → gọi lại
riêng lẻ đúng các id thiếu (tối đa 1 vòng) → vẫn thiếu → **chunk `failed`**, không ghi rỗng.

**Golden fixture bắt buộc (Protocol 5 tinh thần)**: định dạng output của LLM là **external
contract** — không do team kiểm soát. `tests/fixtures/epub_llm/deepseek_batch_response_*.json` phải
được **capture từ request thật** ở spike R5-02 bước (e). **Mock viết tay theo thiết kế này = test
tự xác nhận giả định**, đúng thứ Protocol 5 tồn tại để chặn (bài học MinerU).

**DeepSeek JSON mode** (`response_format={"type": "json_object"}`): `⚠️ ASSUMED, chưa verify` — nếu
Dev verify được ở spike thì thêm tham số **optional** vào provider; **không bắt buộc**, và contract
trong prompt vẫn phải đủ mạnh để chạy đúng khi không có JSON mode (4 provider còn lại).

##### X5 — Ước tính chi phí — GIẢI QUYẾT tại §6.20.6 (2 hằng số + bảng đo lại)

##### X6 — `doc_href` (ebooklib ≠ zip) — GIẢI QUYẾT

Tự chạy `ebooklib==0.20` trên chính file EPUB thật, xác nhận Expert đúng và bổ sung cách sửa đã đo:

```
container.xml → rootfile/@full-path = 'ops/9781603424073.opf' → opf_dir = 'ops'
item.file_name (5 document) có trong zip.namelist() as-is : 0/5
posixpath.normpath(posixpath.join(opf_dir, item.file_name)) : 5/5
book.opf_dir                                               : KHÔNG TỒN TẠI (AttributeError)
```

**Chốt cho `EpubDocument.load()`**:
```python
full_path = re.search(r'full-path="([^"]+)"', zf.read("META-INF/container.xml").decode()).group(1)
opf_dir   = posixpath.dirname(full_path)                       # 'ops' — có thể là '' nếu OPF ở gốc
doc_href  = posixpath.normpath(posixpath.join(opf_dir, item.file_name))
```
`opf_dir` rỗng (OPF nằm ở gốc zip) là hợp lệ và `join`/`normpath` xử lý đúng — **không** hardcode
`"ops/"`. Test bắt buộc ở §6.20.9 (sợi dây thứ 3).

##### Y1..Y8 — chấp nhận toàn bộ, với 3 điều chỉnh

| # | Nội dung | Quyết định |
|---|---|---|
| **Y1** | Parser XHTML: dùng `features="xml"`; fallback `html.parser` chỉ khi XML parse fail; validate `ET.fromstring()` trên output trước khi ghi | **NHẬN** + **N-3**: phải thêm **`lxml`** vào `pyproject.toml` (bs4 "xml" không chạy nếu thiếu — tự verify bằng venv sạch). Lý do kỹ thuật: `html.parser` hạ `viewBox` → `viewbox`, hỏng SVG trong trang có cả SVG lẫn text |
| **Y2** | Quy tắc chèn bản dịch khi `bilingual=True`: (a) strip mọi `id` trong bản copy (file thật có **32 unit** chứa `<a id="page_N"/>` → duplicate id = epubcheck error + page-list trỏ sai); (b) `td`/`th`: chèn `<br/><span lang="vi" class="bb-vi">…</span>` **bên trong ô**, không `insert_after` (tạo ô mới, phá số cột); (c) `bilingual=False`: chỉ thay text node, **không đụng element con** (nếu không sẽ mất 10 `<img>` nằm trong `<p>`); (d) `li > ul` lồng: lấy **innermost** block có text trực tiếp | **NHẬN toàn bộ**. Thêm ràng buộc của X3: bản copy **bắt buộc** mang `lang="vi"` + `class="bb-vi"` — đây là dấu hiệu mà guard BR-EPUB-05 dựa vào, không phải trang trí |
| **Y3** | `ordinal` đếm trên **mọi** node thuộc tag list **trước** khi lọc (drop rule không làm lệch id); `units.json` lưu `{unit_id: {"src_sha1": …, "vi": …}}`, merge kiểm hash, lệch → chunk `failed` | **NHẬN**. Đây là ca nguy hiểm hơn cả rỗng: sửa 1 drop rule ở version sau làm resume **dán bản dịch vào sai đoạn**. Spec cũ bác "hash làm **key**" — vẫn đúng; "hash làm **check**" là chuyện khác và cần thiết |
| **Y4** | Unit quá khổ: > `EPUB_REQUEST_CHAR_BUDGET` → gửi **một mình**; > `EPUB_UNIT_HARD_MAX_CHARS = 10_000` → job `failed` nêu đúng `unit_id`, không cắt câu ở v1 | **NHẬN**. Cơ sở ngưỡng: `max_tokens=8192` ở **cả 4 provider** (tự đọc code xác nhận, §6.20.7 Z3); VI ≈ 1,16× ký tự EN, ~2 ký tự/token → unit > ~13.000 ký tự EN làm output **cụt** → JSON hỏng → retry lẻ vẫn cụt → chunk fail không lối thoát. 10.000 là ngưỡng có biên. **⚠️ chưa chạm dữ liệu thật** (max unit của file mẫu = 989 ký tự) — xem §6.20.11 mục 7 |
| **Y5** | Ghi qua `.epub.tmp` + `os.replace()` | **NHẬN** — 2 dòng, đóng hẳn ca "zip cụt bị resume ghi đè" |
| **Y6** | `with_retry` không retry 5xx: `_TRANSIENT_ERRORS = (RateLimitError, TimeoutError, ConnectionError)` (`retry.py:14-18`), còn `openai.APIError` (gồm `InternalServerError`, `APIConnectionError`, `APITimeoutError`) bị map thành `TranslationProviderError` (`openai_provider.py:80-81`) → **không retry** | **NHẬN, và nâng lên BẮT BUỘC trước khi nhánh EPUB dùng `with_retry`**. Nhánh PDF ít lộ vì pdf2zh/babeldoc tự retry bên trong; nhánh EPUB gọi API trực tiếp ~200 request tuần tự cho sách 600k ký tự → 1 lỗi 502 làm job `failed`. Resumable nên không mất tiền, nhưng đây là lỗi hạ tầng bình thường không được phép giết job. **Sửa ở tầng provider** (map 5xx/connection/timeout của SDK sang lớp transient), **không** nới `_TRANSIENT_ERRORS` thành `Exception` — nới rộng là đúng bẫy retry-vô-hạn E-10 của phương án A |
| **Y7** | Known limitations: NCX `navLabel` / EPUB3 `nav.xhtml` ngoài spine và `<title>` **không được dịch** → mục lục trong reader vẫn tiếng Anh; `<dc:language>` giữ `en`; tài liệu ngoài spine không dịch | **NHẬN** — ghi vào PRD known limitations. Không chặn v1, nhưng user **sẽ** hỏi ngay lần mở đầu tiên |
| **Y8** | Rule ISBN đang bỏ **cả đoạn** (`copyright.html` có `<p>Baking with sourdough / by Sara Pitzer<br/>…<br/>ISBN 978-…</p>`) | **NHẬN, sửa cho chặt**: rule là **"unit CHỈ chứa ISBN"** (sau khi strip tag, phần còn lại khớp ISBN + khoảng trắng), **không** phải "chứa ISBN". Đoạn trên có tên sách/tác giả → **phải được dịch** |

##### Z1..Z3

- **Z1** (N=1, xin thêm EPUB dày) → chuyển thành **§6.20.11 mục 7**, việc của PM/user.
- **Z2** (bổ sung 4 dòng vào bảng so sánh, bỏ ngầm định "prompt cộng đồng") → **đã làm** tại
  §6.20.4 bảng "4 tiêu chí BỔ SUNG" + §6.20.11 mục 6.
- **Z3** (gọi đúng tên 2 ngân sách) → **đã làm** tại §6.20.7.

##### Điểm của Expert tôi KHÔNG làm theo (kèm lý do)

| Đề xuất Expert | Quyết định | Lý do |
|---|---|---|
| §6 mục 3(c): kỳ vọng spike "6 dòng `<sup>` ra đúng `1/3`" | **Siết chặt hơn**: 5 dòng ra `1/3` **và** 1 dòng ra `1 1/3` | N-1: chính `markdownify` mà Expert đề xuất cho ra `11/3` ở dòng hỗn số. Kỳ vọng như Expert viết sẽ **pass** cho một implementation vẫn sai |
| X2 "phương án tối thiểu nếu PM muốn giảm scope": `get_text("\n")` + tái tạo `<br/>` | **Từ chối phương án giảm scope** | Cứu dòng nhưng mất 214 `<strong>` — nửa nạc nửa mỡ của đúng Bug #7 vừa đóng, sẽ phải làm lại lần 2. Chi phí bản đầy đủ đã đo được là +9,3% token |
| FD X5(b): `EPUB_JSON_ENVELOPE_CHARS_PER_UNIT = 26` | **Đổi thành 30, và thêm `EPUB_INLINE_MARKUP_FACTOR = 1.15`** | 26 là số đo trần trụi (26,7 làm tròn **xuống**) và thiếu hẳn số hạng inner-HTML (N-2). Công thức của Expert vẫn ước thấp ~9% — vi phạm §6.11.6 ở đúng lớp bảo vệ tài chính mà chính Expert đang bảo vệ |
| Y1: "fallback `html.parser` khi XML parse fail" | **Nhận, nhưng thêm điều kiện** | Fallback chỉ được dùng khi **output sau fallback vẫn qua `ET.fromstring()`**. Fallback im lặng sang parser hạ-chữ-hoa-attribute là cách hỏng SVG mà không ai biết |

##### Trạng thái §6.20 sau mục này

**Đủ điều kiện giao Dev**, với 2 điều kiện đi kèm: (a) spike R5-02 chạy đúng thứ tự 6 bước a→f của
§6.20.10 mục 1 **trước** khi viết implementation đầy đủ; (b) `lxml` + `ebooklib` + `bs4` +
`markdownify` được thêm vào `pyproject.toml` và **pin version** trong cùng commit đầu tiên.

#### 6.20.13. Fix Bug #EPUB-B2-1 (cost variance) + Bug #EPUB-4 (mất dấu tiếng Việt) — sau QA vòng 1/5 (2026-09-09)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement. **Quan hệ tài liệu**: mục này **bổ sung** vào
§6.20.6/§6.20.8/§6.20.12; không thay thế điều gì đã chốt ở đó, trừ 2 điểm được ghi rõ là "SỬA" tại
§6.20.13.4 (một-shot example của X4) và §6.20.13.6 (`prompt_overhead_chars` của nhánh EPUB). Khi
mâu thuẫn, mục này thắng.

**Nguồn bằng chứng đầu vào**: `docs/test-report.md`, 3 section US-22 Bước 2/3 ngày 2026-09-09 (QA
vòng 1/5 + 2 phiên độc lập). **Ranh giới bằng chứng phải nhớ suốt mục này**: cả 2 bug đều chỉ có
**1–2 điểm dữ liệu quan sát**, chưa lần nào tái lập có kiểm soát. Mọi hằng số ngưỡng đề xuất dưới
đây vì thế là **ước lượng thận trọng, `⚠️ ASSUMED — chưa đo trên corpus/nhiều lần chạy`** (R5-01),
KHÔNG phải số đã verify. Điều đã verify và điều mới suy ra được phân biệt tường minh ở từng mục.

##### 6.20.13.0. Ba điều Tech Lead tự verify khi thiết kế (đọc source thật, không suy đoán)

| # | Sự thật | Nguồn xác thực (đọc trực tiếp trong phiên này) |
|---|---|---|
| **V-1** | **One-shot example của contract X4 đang dạy model trả về tiếng Việt KHÔNG DẤU.** `_EPUB_BATCH_ONE_SHOT_EXAMPLE` (`src/core/prompt_builder.py:427-433`) có `'Dau ra: {"0": "<strong>2 cups</strong> bot mi, 1<sup>1</sup>/<sub>3</sub> tsp muoi, nuong o 350F."}'` — `bot mi`, `muoi`, `nuong o` là tiếng Việt không dấu. Quét toàn khối `_EPUB_BATCH_CONTRACT` + one-shot (dòng 409-433): **0 ký tự có dấu tiếng Việt**, ký tự non-ASCII duy nhất là dấu gạch ngang `—` | tự chạy script đếm ký tự trên `src/core/prompt_builder.py` dòng 409-433 |
| **V-2** | **`max_tokens=8192` là trần CHO MỖI REQUEST** (`deepseek_provider.py:37` → `OpenAIProvider`), nên **134.274 token của 1 chunk KHÔNG THỂ đến từ 1 request duy nhất**. Chunk 0 (31 unit, ~3 request theo `EPUB_CHUNK_CHAR_BUDGET=8.000`/`EPUB_REQUEST_CHAR_BUDGET=3.000`) chỉ có thể đạt con số đó qua **vòng gọi lại RIÊNG LẺ** ở `job_orchestrator.py:1758-1774` — vòng này hiện **không có trần số lần**: 1 response hỏng/cụt → `parse_epub_batch_response()` trả `{}` → **mọi** id thiếu → tối đa `len(slice_units)` ≈ 18 request phụ **cho mỗi request hỏng**, mỗi request phụ lại gánh nguyên system prompt | đọc `job_orchestrator.py:1742-1783`, `deepseek_provider.py:29-47`, `prompt_builder.py:455-493` |
| **V-3** | **`TranslationResult` KHÔNG có `finish_reason`** (`src/services/translation.py:27-32`), và §6.20.12 X4 cấm đổi signature `provider.translate()` (interface chung 5 provider). ⇒ Mọi cơ chế phát hiện runaway ở mục này **bắt buộc** chỉ được dùng `input_tokens`/`output_tokens` đã có, KHÔNG được dựa vào cờ truncation của SDK | đọc `src/services/translation.py:27-46` |

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

##### 6.20.13.2. Lớp 4 — kiểm trần chi phí sau MỖI REQUEST (không ngưỡng đoán, ưu tiên cao nhất)

Đây là cơ chế trả lời trực tiếp yêu cầu "phát hiện sớm hơn, không đợi hết chunk", và là cơ chế
**duy nhất trong mục này không phụ thuộc một hằng số ⚠️ ASSUMED nào** — vì thế nó là lưới an toàn
chính, còn §6.20.13.3 chỉ là lưới phụ.

Hiện tại Lớp 3 (`job_orchestrator.py:912-925`) chỉ chạy **sau khi 1 chunk hoàn tất**; mức "vượt
trần tối đa để lọt" = chi phí đúng 1 chunk (§6.20.7 Z3). Thêm **Lớp 4** ngay trong
`_process_epub_chunk()` để mức đó tụt xuống còn **chi phí đúng 1 request**:

- Đổi signature (`job_orchestrator.py:1713-1721`), thêm tham số **có tên**:
  ```python
  async def _process_epub_chunk(
      self, job, chunk, doc, chunk_plan, system_prompt, pricing_provider, db_session,
      *, cost_budget_remaining: float | None,   # MỚI — Lop 4
  ) -> None:
  ```
  Caller (`run_epub_job()`, ngay trước lời gọi `_process_epub_chunk`) tính:
  ```python
  cost_budget_remaining = (
      effective_cap - sum(c.api_cost or 0.0 for c in chunks[:position - 1])
      if self._settings.cost_cap_enabled else None
  )
  ```
  **Dùng LẠI đúng biểu thức `effective_cap` đã có ở dòng 917-921** (`job.cost_cap_usd` else
  `settings.max_cost_per_job_usd`) — không viết công thức trần thứ hai (cùng lý do
  `estimate_job_cost_v2()`/`estimate_chunk_cost()` phải dùng chung `_estimate_input_tokens()`).

- Trong vòng `for start, end in chunk_plan.requests:` — **ngay sau mỗi lần cộng
  `total_cost += result.estimated_cost_usd`** (dòng 1752, và cả dòng 1770 của nhánh gọi lại
  từng-id): nếu `cost_budget_remaining is not None and total_cost > cost_budget_remaining` →
  `raise EpubChunkCostCapExceeded(...)` (exception MỚI, đặt cạnh `EpubBatchTranslationError`).

- `run_epub_job()` bắt `EpubChunkCostCapExceeded` **riêng, trước** khối `except Exception` chung
  (dòng ~890), và đi vào **đúng nhánh `cost_capped` đã có** (dòng 926-945) — không tạo trạng thái
  mới, không đổi UI: `job.status='cost_capped'`, `cost_source='metered'`,
  `actual_cost = <chi phí các chunk completed> + <chi phí dở dang của chunk này>`.

- **Ghi nhận tiền đã tiêu dở dang (Protocol 6 — không để mất dấu vết tài chính)**: trước khi raise,
  ghi vào chính row chunk đang chạy: `chunk.api_tokens_used = total_input_tokens +
  total_output_tokens`, `chunk.api_cost = total_cost`, `chunk.status = "failed"`,
  **`chunk.output_path` để NGUYÊN `None`**. Không bao giờ đặt `status="completed"` cho chunk dở —
  bước merge (dòng 972-977) chỉ đọc chunk `completed` + có `output_path`, nên bản dịch dở không
  bao giờ lọt vào file output.
  - **Không double-count**: accumulator Lớp 3 là `sum(c.api_cost or 0.0 for c in chunks[:position])`
    — cộng theo row, mỗi row đúng 1 lần. Khi user bấm Retry, `retry_job()` reset chunk về `pending`
    và lần chạy mới **GÁN ĐÈ** (`=`, không phải `+=`) `chunk.api_cost` → vẫn không cộng đôi.
  - **Known limitation phải ghi vào `docs/CHANGELOG.md`** (đây là hệ quả có chủ đích, không phải
    bug): tiền đã tiêu cho phần dở dang của 1 chunk bị **quên** sau khi resume ghi đè row đó. Đây
    đúng hành vi hiện có của mọi chunk `failed` ở nhánh PDF — giữ nhất quán, không mở rộng schema
    (thêm cột = phải xoá/tạo lại DB, xem §6.20.11 mục 1).

- **Hiệu quả định lượng**: mức vượt trần tối đa giảm từ "1 chunk" (~8.000 ký tự nguồn) xuống
  "1 request" (~3.000 ký tự nguồn) = **giảm ~2,7×**. Với đúng sự cố QA gặp: cap $0,015, chunk 0 tốn
  $0,0663 → Lớp 4 sẽ dừng ở request đầu tiên vượt $0,015 thay vì để chạy hết chunk.

##### 6.20.13.3. Trần số request phụ (fix C-1) + phát hiện runaway per-request (fix C-3)

**(a) Trần số request phụ — không ngưỡng đoán, sửa trực tiếp V-2.** Thay vòng
`for local_id in sorted(missing_ids):` (dòng 1759) bằng logic 2 nhánh, **hằng số MỚI trong
`src/core/chunking.py` cạnh `EPUB_REQUEST_CHAR_BUDGET`**:

```python
EPUB_MAX_SINGLE_ID_RETRIES = 5      # ⚠️ ASSUMED (xem lý do chọn ngay dưới)
```

- `len(missing_ids) <= EPUB_MAX_SINGLE_ID_RETRIES` → giữ **nguyên** pattern hiện có (dòng
  1759-1774), không sửa một dòng nào.
- `len(missing_ids) > EPUB_MAX_SINGLE_ID_RETRIES` → **KHÔNG** gọi lại từng id. Thiếu quá nửa batch
  gần như luôn là "cả response hỏng/cụt", không phải "model bỏ sót vài mục" — gọi lại **NGUYÊN
  request đó đúng 1 lần** (payload y hệt, `expected_ids` y hệt), rồi merge kết quả vào `parsed`.
  Vẫn thiếu sau lần đó → giữ nguyên đường `still_missing` → `EpubBatchTranslationError` (E-09).
- **Trần cứng cho toàn bộ 1 slice**, đếm bằng biến cục bộ `extra_requests` trong vòng
  `for start, end`: `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE = 6` (= 1 lần gọi lại nguyên request + tối
  đa 5 lần gọi lại từng-id, hoặc 6 lần từng-id). Vượt trần → không gọi thêm, đi thẳng vào đường
  `still_missing`/chấp nhận (tuỳ mục 6.20.13.5). Trần này áp cho **cả** retry vì thiếu id **và**
  retry vì mất dấu (§6.20.13.5) — 2 cơ chế **dùng chung một quota**, không cộng dồn.
- **Hiệu quả định lượng**: worst case token của 1 slice giảm từ `1 + 18` request xuống `1 + 6`
  request = **giảm ~2,7×** phần khuếch đại C-1.
- **Cơ sở chọn số 5 — `⚠️ ASSUMED`**: 5 ≈ 28% của slice điển hình (18 unit). Không có dữ liệu đo
  phân bố "số id thiếu mỗi response" (QA không giữ log per-request). Dev/QA khi chạy live phải log
  giá trị `len(missing_ids)` mỗi lần > 0 để vòng sau có số thật mà chỉnh; ghi rõ trong
  `test-report.md`.

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

**Hành động khi phát hiện runaway — TRẢ LỜI CÂU HỎI 2 CỦA BRIEF: KHÔNG tự động retry.** Chia 2 ca,
theo tiêu chí "kết quả có dùng được không", vì trade-off khác hẳn nhau:

| Ca | Điều kiện | Hành động | Lý do |
|---|---|---|---|
| **R-a** | Runaway **nhưng** `parse_epub_batch_response()` trả đủ id, giá trị hợp lệ | **GIỮ kết quả**, chỉ ghi nhận anomaly (§6.20.13.7). Không retry | Tiền đã tiêu rồi và nội dung dùng được. Vứt đi + gọi lại = trả tiền lần 2 để đổi lấy đúng thứ đang có. Retry chỉ có nghĩa khi kết quả **không dùng được** |
| **R-b** | Runaway **và** thiếu id / parse hỏng | **Abort ngay**: `raise EpubRequestRunawayError` → chunk `failed` → user bấm Retry (BR-CHUNK-05, resumable, không mất chunk đã xong). **KHÔNG** chạy vòng gọi lại từng-id, **KHÔNG** gọi lại nguyên request | Đây đúng con đường C-1: 1 response runaway + hỏng mà đi vào vòng retry sẽ đẻ ra tối đa 6 request phụ **sau khi đã** tiêu bất thường. Brief hỏi "retry có thể tốn thêm tiền thật không?" — có, và đây là ca duy nhất chắc chắn tốn thêm mà xác suất thành công thấp nhất (model vừa chứng minh nó đang không ổn định trên đúng payload này) |

**Khuyến nghị chốt**: abort (R-b), không auto-retry. Cơ chế resumable của BR-CHUNK-05 đã đủ để user
tự quyết định có trả thêm tiền hay không — và đó là quyết định của **người trả tiền**, không phải
của heuristic có ngưỡng ⚠️ ASSUMED.

**Trả lời câu hỏi 3 của brief (cấu hình được hay hardcode)**: `EPUB_RUNAWAY_OUTPUT_FACTOR` và
`EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS` **hardcode** ở `cost_estimator.py` (tiền lệ BR-IMGCOMP-03), KHÔNG
đưa vào `.env`. Lý do: đây là **ngưỡng chẩn đoán nội bộ chưa có dữ liệu**, không phải chính sách
tài chính của user — chính sách tài chính là `max_cost_per_job_usd` (đã cấu hình được, và Lớp 4 ở
§6.20.13.2 đã làm nó có hiệu lực sớm hơn ~2,7×). Đưa 1 hằng số chưa đo vào `.env` là mời user chỉnh
một con số mà chính team chưa hiểu, rồi khó lần lại được nguyên nhân khi sự cố tái diễn. Khi có đủ
dữ liệu đo (yêu cầu log ở trên) → xem lại quyết định này, ghi vào §6.20.13 vòng sau.

##### 6.20.13.4. Bug #EPUB-4 — nguyên nhân gốc gần như chắc chắn: prompt tự dạy model bỏ dấu (V-1)

QA đặt giả thuyết "hành vi model với batch lớn". Đọc source thì có một nguyên nhân **cụ thể hơn,
verify được, và rẻ hơn nhiều để sửa** (V-1): **toàn bộ khối contract + one-shot example gửi cho
model không có một ký tự tiếng Việt có dấu nào**, và ví dụ one-shot — thứ model bắt chước mạnh nhất
— **demo output là `bot mi`, `muoi`, `nuong o 350F`**.

> **Ranh giới bằng chứng (R5-01)**: sự thật "prompt không có dấu, one-shot demo output không dấu"
> là **ĐÃ VERIFY** (đọc + quét ký tự trên `prompt_builder.py:409-433`). Còn "đó **là** nguyên nhân
> của 30-37% unit mất dấu" là **`⚠️ ASSUMED`** — chưa có A/B test. Nó **giải thích được** đặc điểm
> QA quan sát: batch lớn → tỉ lệ instruction/example (không dấu) so với ngữ cảnh sinh ra càng lớn,
> và mất dấu xuất hiện theo **cụm liên tiếp trong cùng 1 request** (QA đo được), tức là hiện tượng
> ở mức **response**, đúng chỗ one-shot example tác động.

**Sửa (bắt buộc, làm TRƯỚC mọi guard — rẻ nhất, tác động lớn nhất):**

1. **Viết lại `_EPUB_BATCH_ONE_SHOT_EXAMPLE`** (`prompt_builder.py:427-433`) sao cho phần "Dau ra"
   là **tiếng Việt có dấu đầy đủ, NFC**: `"<strong>2 cups</strong> bột mì, 1<sup>1</sup>/<sub>3</sub>
   tsp muối, nướng ở 350F."`. Phần "Dau vao" giữ nguyên tiếng Anh.
2. **Thêm rule 7 vào `_EPUB_BATCH_CONTRACT`** (sau rule 6, dòng 423-424), viết ASCII như 6 rule
   hiện có để không đội `prompt_overhead_chars`:
   `"7. Ban dich PHAI la tieng Viet CO DAU day du (Unicode NFC). TUYET DOI KHONG tra ve tieng Viet
   khong dau (vi du: phai la \"bột mì\", KHONG duoc la \"bot mi\")."` — cặp ví dụ trong rule này
   **bắt buộc** có bản có dấu, vì rule mô tả suông về dấu mà không cho model thấy dấu thì lại đúng
   cái bẫy V-1.
3. **KHÔNG** chuyển toàn bộ instruction sang tiếng Việt có dấu. Lý do định lượng: prompt được gửi
   lại **mỗi request** (~18 lần/sách); tiếng Việt có dấu tokenize ~2 ký tự/token vs ~4 của ASCII
   (`CHARS_PER_TOKEN_VI`/`CHARS_PER_TOKEN_EN`), nên bỏ dấu-hoá cả khối 1.149 ký tự sẽ **gấp đôi**
   token overhead của nó. Chỉ ~110 ký tự có dấu được thêm (ví dụ ở rule 7 + one-shot) → tăng
   ~55 token/request → ~1.000 token/sách → **< $0,001** với DeepSeek. Đây là đánh đổi có tính được,
   không phải cảm tính.
4. **Ảnh hưởng tới cost estimate**: `prompt_overhead_chars` được đo từ **chuỗi thật** lúc chạy, nên
   thay đổi độ dài tự phản ánh — nhưng chỉ khi §6.20.13.6 được làm. Đọc §6.20.13.6 trước khi sửa.

##### 6.20.13.5. Guard MỚI: `_check_epub_diacritics()` — 2 tầng, KHÔNG đụng BR-EPUB-05

Guard này là **lớp phòng thủ độc lập**, không sửa `_check_epub_output_guard()`
(`job_orchestrator.py:229`) — guard đó bắt lớp lỗi khác (Bug #5 dạng EPUB) và đang PASS đúng thiết
kế của nó.

**Helper MỚI — module MỚI `src/core/text_quality.py`** (không nhét vào `prompt_builder.py`: đây là
đo chất lượng output, không phải dựng prompt):

```python
_VN_DIACRITIC_CHARS = frozenset(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
    "ùúủũụưừứửữựỳýỷỹỵđ"
)

def strip_html_for_measure(html: str) -> str:
    """Bo THE va MOI thuoc tinh (href/class/alt tieng Anh khong duoc tinh
    vao mau do — do la nguon false-positive lon nhat)."""

def diacritic_ratio(html: str) -> tuple[float, int]:
    """Tra (ty le ky tu co dau / tong ky tu chu cai, so ky tu chu cai) tren
    text da strip tag, da NFC-normalize va lower()."""
```

**Ghi chú kỹ thuật bắt buộc cho Dev**: `unicodedata.normalize("NFC", s)` **trước** khi đếm — tiếng
Việt tổ hợp (NFD) sẽ cho ra chữ cái base ASCII + combining mark, đếm ra tỉ lệ 0 và tạo
false-positive hàng loạt. Đây là bẫy có thật của chính lớp lỗi đang đo.

**Tầng 1 — mức REQUEST (đặt ngay sau `parse_epub_batch_response`, dòng 1754, sau bước xử lý
missing id).** Bug là hiện tượng ở mức response (QA đo: mất dấu theo cụm liên tiếp trong cùng
request), nên đo gộp **toàn bộ giá trị `parsed` của request đó** cho mẫu lớn, ổn định:

```python
EPUB_DIACRITIC_MIN_LETTERS_REQUEST = 200   # ⚠️ ASSUMED
EPUB_DIACRITIC_RATIO_REQUEST       = 0.08  # ⚠️ ASSUMED
```
`letters >= 200` và `ratio < 0,08` → coi **cả request** là hỏng dấu → gọi lại **nguyên request đó
đúng 1 lần** (dùng chung quota `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE`, §6.20.13.3a). Nếu bản retry có
`ratio` **cao hơn** → dùng bản retry; nếu không → giữ bản đầu (đừng đổi lấy thứ tệ hơn).

**Tầng 2 — mức UNIT (đặt ngay trước vòng `for local_id, vi_html in parsed.items():`, dòng 1785).**
Bắt phần sót lại sau tầng 1:
```python
EPUB_DIACRITIC_MIN_LETTERS_UNIT = 40    # ⚠️ ASSUMED
EPUB_DIACRITIC_RATIO_UNIT       = 0.02  # ⚠️ ASSUMED — gần như là "0 dấu tuyệt đối"
```
Unit có `letters >= 40` và `ratio < 0,02` → gọi lại **riêng lẻ unit đó**, tối đa 1 lần, **tái dùng
ĐÚNG pattern code dòng 1759-1774**.

> **Hợp nhất hay tách 2 vòng retry? — CHỐT: TÁCH, nhưng dùng CHUNG 1 helper.** Rút phần thân của
> vòng hiện có (dòng 1760-1774) thành `async def _retry_single_unit(...) -> str | None` (trả bản
> dịch hoặc `None`), rồi cả 2 chỗ đều gọi nó. Không gộp thành 1 vòng vì 2 điều kiện kích hoạt xảy
> ra ở **2 thời điểm khác nhau** (thiếu id: biết ngay sau parse; mất dấu: chỉ biết sau khi đã có
> giá trị) và ngữ nghĩa lỗi khác nhau (thiếu = phải có gì đó; mất dấu = có rồi nhưng kém). Gộp
> cứng 2 ý nghĩa vào 1 vòng là đúng loại "một biến, hai ý nghĩa" mà §6.20.7 và Bug #5 đã trả giá.
> Chia sẻ code ở tầng helper, không ở tầng vòng lặp.

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

##### 6.20.13.6. SỬA `prompt_overhead_chars` của nhánh EPUB (fix C-2, Protocol 6 data lineage)

**Sai lệch tất định, đọc code là thấy** — không phải giả thuyết:
- `cost_gate.py:133-139` ước bằng `build_prompt_text(...)` = prompt **của pdf2zh** (có `${text}`
  placeholder, footer riêng).
- `job_orchestrator.py:840-846` gửi thật `build_epub_batch_prompt(build_system_prompt(...))` =
  `glossary_prompt` + `_EPUB_BATCH_CONTRACT` (**1.149 ký tự**, tự đếm) + one-shot (**~250 ký tự**).

⇒ **~1.400 ký tự/request không bao giờ được đếm vào ước tính**, và theo `_estimate_input_tokens()`
số hạng này được nhân với `segment_count` (~18 request) → **~+6.300 input token bị bỏ sót** so với
28.257 input token đã ước ⇒ ước thấp ~22% **chỉ riêng ở phần input**. Đây là vi phạm §6.11.6 nằm
đúng trên lớp bảo vệ tài chính, và là **cùng loại lỗi** với X5 (§6.20.6) — chỉ khác là X5 sót phần
nội dung, chỗ này sót phần prompt.

**Sửa (Protocol 6: bên ước tính phải tiêu thụ ĐÚNG artifact mà bên thực thi gửi đi)** — trong
`_estimate_epub_translation_cost()` (`cost_gate.py:115-155`), thay khối `build_prompt_text` bằng:

```python
base_system_prompt = await build_system_prompt(
    glossary_manager, project_id=batch_id,
    only_terms_present_in=full_text, max_glossary_entries=max_glossary_entries,
)
real_prompt = build_epub_batch_prompt(base_system_prompt)   # CHINH chuoi _process_epub_chunk() gui
prompt_overhead_chars = len(real_prompt)
```
Không còn trừ `len("${text}")` — chuỗi EPUB **không có** placeholder đó. Nhánh PDF (dòng 87-105)
**không đổi một dòng nào**.

**Test bắt buộc (R6-02, assert giá trị cụ thể, không chỉ `assert_called`)**: 1 test so **bằng nhau**
chuỗi prompt mà `_estimate_epub_translation_cost()` đo với chuỗi `system_prompt` mà
`_process_epub_chunk()` thực sự nhận, trên cùng 1 job/glossary — đây đúng loại "sợi dây nối 2 bước"
mà Protocol 6 sinh ra để bảo vệ.

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

##### 6.20.13.7. Ghi nhận anomaly (trả lời câu hỏi 4 của brief)

Cân nhắc mức độ: EPUB **chưa có** UI hiển thị report như `layout_qa_findings` của PDF, và Bước 3/3
mới làm UI. Vì vậy chọn mức **nhẹ nhất mà vẫn không mất dấu vết**, không thêm cột DB, không thêm
endpoint:

1. **File `chunk_dir/anomalies.json`** (cạnh `units.json`, cùng thư mục chunk theo pattern F9), ghi
   **sau vòng request, trước khi ghi `units.json`**, và **chỉ ghi khi có ≥1 anomaly**:
   ```json
   {"chunk_index": 0,
    "runaway_requests":   [{"slice": [0, 17], "payload_chars": 2980, "output_tokens": 6120, "ratio": 3.5, "action": "kept|aborted"}],
    "low_diacritic_requests": [{"slice": [0, 17], "ratio": 0.01, "retried": true, "ratio_after": 0.23}],
    "low_diacritic_units":    [{"unit_id": "ops/xhtml/chapter01.html#17", "ratio": 0.0, "retried": true, "resolved": false}]}
   ```
2. **`chunk_dir/requests.jsonl`** — 1 dòng `{"slice": [s,e], "payload_chars": …, "input_tokens": …,
   "output_tokens": …, "ratio": …, "diacritic_ratio": …}` cho **mọi** request (kể cả bình thường).
   Đây là **dữ liệu để chốt lại các ngưỡng ⚠️ ASSUMED ở vòng sau**, và là thứ QA vòng 1/5 không có
   nên phải suy đoán. Bắt buộc, không phải tuỳ chọn.
3. **Log WARN** 1 dòng/anomaly qua logger sẵn có, có `job.id` + `chunk_index` + loại anomaly.
4. **KHÔNG** đụng `job.error_message` khi job vẫn `completed` — trường đó là thông điệp lỗi hiển thị
   cho user, nhét cảnh báo chất lượng vào đó sẽ làm job thành công trông như job hỏng.
5. Bước 3/3 (UI) có thể đọc `anomalies.json` để hiện cảnh báo mềm — **ngoài phạm vi Bước 2/3**, ghi
   vào `docs/CHANGELOG.md` như một hook đã chuẩn bị sẵn.

##### 6.20.13.8. Danh sách hằng số MỚI (tổng hợp cho Dev)

| Hằng số | Giá trị | Ở đâu | Cấu hình `.env`? | Trạng thái bằng chứng |
|---|---|---|---|---|
| `EPUB_MAX_SINGLE_ID_RETRIES` | 5 | `core/chunking.py` | Không | ⚠️ ASSUMED |
| `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE` | 6 | `core/chunking.py` | Không | ⚠️ ASSUMED |
| `EPUB_RUNAWAY_OUTPUT_FACTOR` | 3.0 | `core/cost_estimator.py` | Không | ⚠️ ASSUMED (có phân tích trần `max_tokens=8192` — V-2 đã verify) |
| `EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS` | 1500 | `core/cost_estimator.py` | Không | ⚠️ ASSUMED |
| `EPUB_DIACRITIC_MIN_LETTERS_REQUEST` | 200 | `core/text_quality.py` | Không | ⚠️ ASSUMED |
| `EPUB_DIACRITIC_RATIO_REQUEST` | 0.08 | `core/text_quality.py` | Không | ⚠️ ASSUMED (corpus docs nội bộ, p5 = 0,122) |
| `EPUB_DIACRITIC_MIN_LETTERS_UNIT` | 40 | `core/text_quality.py` | Không | ⚠️ ASSUMED |
| `EPUB_DIACRITIC_RATIO_UNIT` | 0.02 | `core/text_quality.py` | Không | ⚠️ ASSUMED (khớp tiêu chí QA đã kiểm bằng mắt) |

Exception MỚI (đặt cạnh `EpubBatchTranslationError`): `EpubChunkCostCapExceeded`,
`EpubRequestRunawayError`.

##### 6.20.13.9. Thứ tự implement bắt buộc cho Dev

1. §6.20.13.4 (sửa one-shot + rule 7) — rẻ nhất, có thể tự nó xoá phần lớn Bug #EPUB-4.
2. §6.20.13.6 (`prompt_overhead_chars`) — phải làm **cùng lúc** với (1), vì (1) đổi độ dài prompt.
3. §6.20.13.2 (Lớp 4 trần chi phí per-request) — cost-safety, không phụ thuộc ngưỡng đoán.
4. §6.20.13.3a (trần số request phụ) → 3b (runaway detect).
5. §6.20.13.5 (guard dấu 2 tầng) → §6.20.13.7 (anomalies/requests log).
6. Task đo `chars/token` thật của DeepSeek (§6.20.13.6, dùng dữ liệu QA đã giữ, **không tốn API**).

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

### 6.20.14. Chiến lược MỚI cho lớp lỗi "DeepSeek trả JSON malformed" sau khi chạm giới hạn Protocol 3 (Tech Lead, 2026-09-10)

**Bối cảnh**: `docs/escalation-log.md` (2026-09-10) — US-22 Bước 2/3 đã dùng hết 5/5 vòng Dev↔QA
(Protocol 3) cho cùng một chuỗi lỗi. Ba biến thể JSON hỏng đã được vá đúng (B2-3 newline, B2-4 dấu
phẩy, B2-5 `}` thừa — biến thể thứ 3 CHƯA fix), nhưng mỗi vòng lại lộ ra biến thể mới. Section này
thay thế hướng "vá tiếp từng biến thể cú pháp" bằng 3 lớp phòng thủ độc lập, không lớp nào giả định
biết trước hình dạng lỗi tiếp theo.

**Chỉ đạo của user (ràng buộc thiết kế, không phải gợi ý)** — quyết định ngày 2026-09-10, PM chuyển
tiếp: *"Ưu tiên nhanh, tiết kiệm, độ chính xác của bản dịch có thể chấp nhận dung sai nhỏ."*
Hệ quả trực tiếp lên thiết kế này:
1. Không đổi kiến trúc lớn (không bỏ JSON, không tích hợp JSON-mode) ở vòng này — xem §6.20.14.8.
2. **E-09 không còn là chính sách mặc định tuyệt đối**: một unit không dịch được sau khi đã thử hết
   cơ chế tổng quát → được phép giữ nguyên tiếng Anh, có đánh dấu, thay vì làm hỏng cả chunk/job.
   E-09 chuyển vai trò: từ "luật mặc định" thành "chốt chặn khi vượt ngưỡng bất thường" (§6.20.14.4).

---

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

##### 6.20.14.2. Lớp A — Ép nhỏ request để GIẢM TẦN SUẤT sinh lỗi (rẻ nhất, làm trước)

**A-1. Hai trần thay vì một.** `plan_epub_chunks()` hiện chỉ cắt request theo `request_budget` đo bằng
**ký tự văn bản thuần** (`_plain_char_len()` strip hết tag). Đó là lý do một request có thể chứa **32
unit** mà vẫn "trong ngân sách 3.000": 32 dòng `<strong>1 cup starter</strong>` có rất ít ký tự thuần
nhưng sinh ra 32 khoá JSON — mà số KHOÁ mới là thứ model phải giữ đúng cú pháp. Vì vậy thêm trần thứ
hai theo SỐ UNIT.

Chốt giá trị (suy từ §6.20.14.0(a), không đoán): mục tiêu giữ `output_tokens` mỗi request về vùng đã
quan sát là sạch, **≤ ~600 token**. Từ dữ liệu thật, `output_tokens ≈ 0,42 × payload_chars`
(459/1.061 = 0,43; 1.279/3.209 = 0,40) và `payload_chars ≈ plain_chars × 1,15 +
30 × số_unit` (dùng đúng `EPUB_INLINE_MARKUP_FACTOR`/`EPUB_JSON_ENVELOPE_CHARS_PER_UNIT` đã có, không
viết công thức thứ hai):

```
plain 1.100 chars + 6 unit  →  payload ≈ 1.100×1,15 + 180 = 1.445 chars  →  output ≈ 607 token
```

- `EPUB_REQUEST_CHAR_BUDGET`: **3.000 → 1.100** (`src/core/chunking.py`, và
  `Settings.epub_request_char_budget` trong `src/core/config.py`).
- **MỚI** `EPUB_REQUEST_MAX_UNITS = 6` (`src/core/chunking.py`), kèm
  `Settings.epub_request_max_units: int = 6` để override qua `.env` — đúng pattern 2 hằng số hiện có.

**A-2. Sửa `plan_epub_chunks()`** (`src/core/chunking.py`, bước 2 "gom unit thành REQUEST"): thêm tham
số `request_max_units: int = EPUB_REQUEST_MAX_UNITS` và đổi đúng 1 điều kiện cắt:

```python
req_units = i - req_start          # số unit đã gom vào request đang mở
if req_units > 0 and (
    req_running + unit_len > request_budget or req_units >= request_max_units
):
    ...cắt request tại đây...
```
Không đụng bước 1 (ranh giới CHUNK) — `EPUB_CHUNK_CHAR_BUDGET = 8.000` **giữ nguyên**, vì nó là
granularity checkpoint chi phí (Z3), không phải giới hạn context. Hệ quả phụ đã kiểm: mỗi chunk giờ có
nhiều request hơn (~7 thay vì ~2-3), không ảnh hưởng resume (BR-CHUNK-05 vẫn checkpoint theo chunk).

**A-3. Hạ trần retry cho khớp batch nhỏ (bắt buộc, nếu quên sẽ ĂN NGƯỢC phần tiết kiệm).** Với slice
chỉ 6 unit, `EPUB_MAX_SINGLE_ID_RETRIES = 5` nghĩa là gần như luôn rơi vào nhánh "retry TỪNG id" — 5
request phụ để cứu 5/6 unit, đắt hơn hẳn 1 lần gọi lại nguyên request. Chốt:

- `EPUB_MAX_SINGLE_ID_RETRIES`: **5 → 2** (≥3 id thiếu trên tổng 6 ⇒ coi là cả response hỏng ⇒ gọi lại
  nguyên request 1 lần, rẻ hơn).
- `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE`: **6 → 3** (trần cứng dùng chung cho retry-thiếu-id VÀ
  retry-mất-dấu, không cộng dồn — giữ nguyên ngữ nghĩa §6.20.13.3a).

**A-4. Data lineage bắt buộc sửa cùng lúc (Protocol 6 R6-01) — nếu bỏ sót sẽ làm cost gate ước SAI.**
`cost_gate.py::_estimate_epub_translation_cost()` đang gọi `plan_epub_chunks(doc.units)` **với tham số
MẶC ĐỊNH**, trong khi `job_orchestrator.run_epub_job()` gọi với giá trị từ `Settings`. Hôm nay hai bên
tình cờ khớp nhau; sau A-1 (và với bất kỳ override `.env` nào) chúng sẽ lệch, mà `llm_request_count`
chính là `segment_count` của `estimate_job_cost_v2()` — lệch số request ⇒ ước THẤP chi phí ⇒ vi phạm
§6.11.6 ("được ước cao, CẤM ước thấp"). **Sửa**: `_estimate_epub_translation_cost()` nhận `settings` (đã
có sẵn ở call-site) và gọi
`plan_epub_chunks(doc.units, char_budget=settings.epub_chunk_char_budget, request_budget=settings.epub_request_char_budget, request_max_units=settings.epub_request_max_units)`.
Test bắt buộc kèm theo (R6-02): đổi `epub_request_max_units` trong `Settings` → assert
`DetailedCostEstimate.estimate.estimated_input_tokens` THAY ĐỔI theo, không phải chỉ `assert_called()`.

**A-5. Đánh đổi — tính bằng số học từ §6.20.14.0, không đoán.**

| | Hiện tại (3.000 chars, không trần unit) | Sau A-1 (1.100 chars + 6 unit) |
|---|---|---|
| Số request cho sách mẫu 384 unit | ≈ 31 (đo: 14 request cho 173 unit ⇒ 12,4 unit/request) | ≈ 64-68 (trần 6 unit gần như luôn chặn trước: 52.369 plain chars / 384 ≈ 136 chars/unit ⇒ 1.100 chars ≈ 8 unit) |
| Chi phí overhead system prompt | 31 × $0,000262 = $0,0081 | ≈ 68 × $0,000262 = $0,0178 |
| **Tổng chi phí/sách** | ≈ **$0,0387** (ngoại suy QA vòng 5/5) | ≈ **$0,0484** |
| **Chênh lệch** | — | **+$0,0097/sách ≈ +25%** |

Phần payload input và toàn bộ output token **không đổi** (cùng nội dung, cùng bản dịch) — chỉ phần
overhead nhân lên theo số request. Tuyệt đối: **thêm ~1 cent Mỹ cho mỗi cuốn sách**.

**Thời gian** (⚠️ ASSUMED — chưa đo trực tiếp, suy từ QA vòng 5/5: 16 request/99,2s): request EPUB chạy
TUẦN TỰ (không AIMD, §6.20.8). Tổng output token không đổi nên phần thời gian sinh chữ không đổi; chỉ
phần latency cố định mỗi request (~1,5s) nhân lên: `(68−31) × 1,5s ≈ +55s` trên một cuốn ~230s ⇒ **+20-30%
thời gian**, tức ~4 phút → ~5 phút cho sách 384 unit. Chấp nhận được so với hiện trạng "chạy 3 lần đều
fail, không bao giờ xong".

---

##### 6.20.14.3. Lớp B — Đổi chiến lược parse: trích cặp `"id": "chuỗi"`, KHÔNG dựa vào ngữ pháp JSON

**Đây là thay đổi chiến lược thật sự, không phải biến thể thứ 4 của cùng một hướng** — lý do ở
§6.20.14.1. Vị trí code: `src/core/prompt_builder.py`, ngay dưới `_decode_concatenated_json_objects()`
(hàm cũ **GIỮ NGUYÊN, không xoá, không sửa** — nó vẫn là đường đi đúng và chặt cho response lành).

**B-1. Hàm mới `_salvage_epub_id_pairs(text, expected_ids) -> dict[str, str]`**:

```python
#: Chi khop khoa la ID NGAN CUC BO app tu sinh ("0".."N", N < 1000) — khong
#: bao gio khop mot chuoi bat ky trong noi dung dich.
_EPUB_ID_PAIR_RE = re.compile(r'"(\d{1,3})"\s*:\s*"')

def _salvage_epub_id_pairs(text: str, expected_ids: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    pos = 0
    while (m := _EPUB_ID_PAIR_RE.search(text, pos)) is not None:
        try:
            # scanstring nhan vi tri NGAY SAU dau nhay mo, tra (chuoi, vi_tri_ket_thuc).
            value, end = json.decoder.scanstring(text, m.end())
        except (ValueError, json.JSONDecodeError):
            pos = m.end()      # cap nay hong -> bo qua, di tiep
            continue
        pos = end              # KHONG BAO GIO quet lai ben trong gia tri da an
        key = m.group(1)
        if key in expected_ids and value.strip():
            out[key] = value   # trung khoa: cai SAU thang, dong bo voi dict.update() cua ham cu
    return out
```

Bốn tính chất khiến hàm này an toàn (phải giữ đủ cả 4 khi implement, không được "đơn giản hoá"):
1. **Chỉ nhận khoá thuộc `expected_ids`** — id ngắn cục bộ `0..N` do chính app sinh mỗi request.
2. **Giá trị được decode bằng chính `json.decoder.scanstring`**, không phải regex — escape (`\"`,
   `\n`, `\uXXXX`) xử lý đúng như JSON thật; chuỗi cụt/escape hỏng thì `scanstring` raise và cặp đó bị
   bỏ, không bao giờ "đoán".
3. **`pos = end` sau mỗi lần ăn thành công** — con trỏ không bao giờ quét lại bên trong một giá trị đã
   lấy, nên một đoạn `"12": "` nằm TRONG nội dung bản dịch không thể tạo cặp giả.
4. **Không bao giờ tự chế nội dung**: mọi giá trị trả về là byte thật của response.

**B-2. Ghép vào `parse_epub_batch_response()` — CHỈ như lớp cứu hộ, không thay đường chính**:

```python
strict = _decode_concatenated_json_objects(text)      # nguyen si, khong doi
result = {...}                                        # loc expected_ids/str/non-empty nhu hien tai
if len(result) < len(expected_ids):                   # CHI khi con thieu
    for key, value in _salvage_epub_id_pairs(text, expected_ids).items():
        result.setdefault(key, value)                 # KHONG BAO GIO de len gia tri da parse chat
```
Response lành ⇒ nhánh salvage không bao giờ chạy ⇒ **zero regression risk** cho đường đi thường.

**B-3. Telemetry (bắt buộc — nếu không có, vòng QA sau lại không chốt được ngưỡng nào).** Giữ nguyên
chữ ký `parse_epub_batch_response()` (nhiều caller/test đang dùng) và thêm hàm chi tiết bên cạnh:

```python
@dataclass(frozen=True)
class EpubParseOutcome:
    translations: dict[str, str]
    strict_ids: frozenset[str]     # lay duoc qua duong JSON chuan
    salvaged_ids: frozenset[str]   # chi lay duoc nho _salvage_epub_id_pairs()

def parse_epub_batch_response_detailed(raw_text, expected_ids) -> EpubParseOutcome: ...
def parse_epub_batch_response(raw_text, expected_ids) -> dict[str, str]:
    return parse_epub_batch_response_detailed(raw_text, expected_ids).translations
```
`_process_epub_chunk()` dùng bản `_detailed`, ghi `salvaged_count` vào mỗi dòng `requests.jsonl`
(§6.20.13.7) và `logger.warning` khi `salvaged_ids` khác rỗng. `salvaged_count > 0` là **tín hiệu sức
khoẻ**: nó nói "model vẫn đang sinh JSON hỏng, chỉ là ta cứu được" — nếu tỉ lệ này cao, Lớp A cần siết
thêm.

**B-4. Test bắt buộc — chạy trên CẢ 5 golden fixture đã có, KHÔNG tốn 1 đồng API nào** (đây là điểm
"nhanh + tiết kiệm" mạnh nhất của Lớp B: bằng chứng đã nằm sẵn trong repo):

| Fixture | Kỳ vọng sau Lớp B |
|---|---|
| `..._ch1_5units.json` | 5/5 id, **`salvaged_ids` rỗng** (đường chuẩn, không đụng salvage) |
| `..._ch1_trailing_garbage.json` | 1/1 id, `salvaged_ids` rỗng |
| `..._ch1_multi_json_object.json` (B2-3) | 11/11 id, `salvaged_ids` rỗng |
| `..._comma_separated_json_objects.json` (B2-4) | 32/32 id, `salvaged_ids` rỗng |
| `..._single_object_spurious_closing_braces.json` (**B2-5, chưa từng có test**) | **32/32 id**, `salvaged_ids` = 31 id (`"1"`..`"31"`), nội dung id `"31"` = `<strong>¼ cup hạt cắt nhỏ</strong>` |

Cộng thêm 3 test tổng hợp (không phụ thuộc fixture) chứng minh hàm không nuốt rác thành dữ liệu:
(a) giá trị chứa chuỗi con `"7": "` bên trong bản dịch ⇒ **không** sinh cặp giả; (b) response cụt giữa
một giá trị ⇒ giữ các cặp hoàn chỉnh trước đó, bỏ cặp cụt; (c) id lạ ngoài `expected_ids` ⇒ bị loại.

**Giới hạn đã biết, ghi rõ để không ai kỳ vọng quá**: Lớp B cứu được mọi biến thể mà nội dung dịch vẫn
còn nguyên trong response. Nó **không** cứu được response bị cắt cụt vì `max_tokens`, hay response mà
model không hề trả bản dịch. Đó chính là phần việc của Lớp C.

---

##### 6.20.14.4. Lớp C — Chính sách dung sai có ngưỡng: E-09 từ "luật mặc định" thành "chốt chặn bất thường"

**Thay đổi chính sách so với §6.20.12 X4 / E-09 gốc.** Trước: thiếu bản dịch cho 1 unit sau vòng gọi
lại ⇒ `EpubBatchTranslationError` ⇒ chunk fail ⇒ job fail. Sau: unit đó **giữ nguyên tiếng Anh, có đánh
dấu**, job vẫn chạy tiếp — **nhưng chỉ trong hạn mức**. Vượt hạn mức thì E-09 vẫn nổ y như cũ.

Phần "TUYỆT ĐỐI không ghi chuỗi rỗng" của E-09 **KHÔNG hề nới lỏng** — bản gốc tiếng Anh không phải
chuỗi rỗng, và cấm ghi chuỗi rỗng vẫn là bất biến tuyệt đối.

**C-1. Điểm chèn** — `job_orchestrator.py::_process_epub_chunk()`, đúng chỗ đang `raise
EpubBatchTranslationError` (khối `if still_missing:`). Thay bằng:

```python
still_missing = expected_ids - parsed.keys()
fallback_ids: set[str] = set()          # KHONG cho vao `parsed`
if still_missing:
    for local_id in sorted(still_missing):
        unit = slice_units[int(local_id)]
        fallback_units.append({                    # gom cho ca chunk
            "unit_id": unit.unit_id,
            "reason": "missing_after_retry",
            "slice": [start, end],
        })
        fallback_ids.add(local_id)
    logger.warning("EPUB fallback EN (giu nguyen goc): job=%s chunk=%s n=%d ...", ...)
```

**Thứ tự thực thi là bắt buộc, không được đảo** (nếu đảo sẽ đốt tiền vô ích): unit fallback
**KHÔNG** được đưa vào `parsed` trước 2 guard mất dấu (§6.20.13.5). Văn bản EN có `diacritic_ratio`
≈ 0 ⇒ nếu lọt vào `parsed`, guard tầng 2 sẽ retry lẻ từng unit đúng những unit ta vừa quyết định bỏ
qua. Fallback chỉ được ghép vào ở **bước ghi cuối cùng** của vòng lặp request:

```python
for local_id, vi_html in parsed.items():
    translations[slice_units[int(local_id)].unit_id] = vi_html
# fallback KHONG ghi vao `translations` — xem C-4 ve cach danh dau trong output
```

**C-2. Hai ngưỡng, hai vai trò khác nhau** (hằng số mới trong `src/core/chunking.py`, cạnh các hằng
EPUB hiện có, và mirror sang `Settings`):

```python
#: ⚠️ ASSUMED — xem lap luan chon so o duoi, PHAI do lai bang du lieu live.
EPUB_FALLBACK_MAX_RATIO_CHUNK = 0.20
EPUB_FALLBACK_MAX_RATIO_JOB = 0.05
```

- **Ngưỡng CHUNK = 20%**, tính trên số unit của chính chunk đó, cho phép tối thiểu 1 unit:
  `allowed = max(1, ceil(0.20 × n_units_in_chunk))`. Vượt ⇒ `raise EpubBatchTranslationError` với
  đúng shape thông điệp E-09 cũ (thêm số liệu fallback). **Cơ sở chọn 20%**: sau Lớp A, một chunk có
  ~55 unit / ~7-9 request; một request mất TRỌN VẸN = 6 unit ≈ 11% chunk. 20% ⇒ chịu được 2 request
  hỏng hoàn toàn trong 1 chunk, nhưng "cả chunk hỏng" thì vẫn fail ngay — đúng điều PM yêu cầu chặn
  ("response hỏng hoàn toàn biến thành chấp nhận mọi thứ").
- **Ngưỡng JOB = 5%**, tính cộng dồn trên toàn sách. **Cơ sở chọn 5% không phải cảm tính** — nó bị
  BR-EPUB-05 ép: guard output (§6.20.12 X3) fail khi **dưới 90% unit khác bản gốc**. Unit fallback
  giữ nguyên EN ⇒ giống hệt bản gốc ⇒ **đếm vào đúng 10% khe hở đó**. Đặt trần job ở 5% để còn nguyên
  một nửa khe hở cho các nguyên nhân khác (unit vốn không có chữ để dịch, v.v.). Đặt ≥10% sẽ khiến
  Lớp C tự tay làm BR-EPUB-05 fail — biến "dung sai" thành lỗi khác, tệ hơn.

**C-3. Kiểm ngưỡng JOB phải sống sót qua resume (BR-CHUNK-05).** Không thêm cột DB (tránh migration —
"nhanh/rẻ"): mỗi chunk ghi `fallback_units.json` vào `chunk_dir` (cạnh `units.json`/`anomalies.json`
sẵn có) **chỉ khi danh sách khác rỗng**. `run_epub_job()`, sau mỗi chunk `completed`, cộng dồn bằng
cách đọc lại các file đó trên **mọi** chunk dir (kể cả chunk đã hoàn thành từ lần chạy trước — đây
chính là điểm khiến resume vẫn đếm đúng), so với `max(1, ceil(0.05 × len(doc.units)))`; vượt ⇒ job
`failed` với thông điệp nêu rõ số unit fallback và ngưỡng. Danh sách fallback cũng được nhân bản vào
`anomalies.json` dưới khoá mới `fallback_units` để dùng chung một chỗ chẩn đoán (§6.20.13.7).

**C-4. Đánh dấu trong file EPUB output** — người đọc phải nhận ra được đoạn nào chưa dịch, và đây phải
là cách RẺ NHẤT không đụng cấu trúc file:
`EpubDocument.write_translated()` nhận thêm `untranslated_ids: set[str] | None = None`; với mỗi
`unit_id` trong tập đó, **thêm class `bb-untranslated` vào chính node gốc** (không chèn node mới,
không bọc `<span>`) và đặt `lang="en"`. Đã kiểm 2 tác dụng phụ:
- `EpubDocument.load()` chỉ bỏ qua node theo class `bb-vi` ⇒ thêm `bb-untranslated` **không** đổi số
  unit đọc lại ⇒ BR-EPUB-05 điều kiện "số unit khớp" không bị ảnh hưởng.
- `count_bb_vi_pairs()` chỉ đếm node `bb-vi` ⇒ không bị ảnh hưởng.
Thêm 1 dòng CSS `.bb-untranslated { opacity: .75; }`? **KHÔNG** — v1 không đụng stylesheet của sách
(rủi ro epubcheck không tương xứng lợi ích). Class + `lang="en"` là đủ để truy vết.

**C-5. Báo cho người dùng.** Ghi `untranslated_units.json` ở cấp job
(`<output_dir>/<job_id>/untranslated_units.json`, cùng chỗ `translated_vi.epub`) gồm `unit_id`,
`reason`, `doc_href`, và trích 120 ký tự đầu của bản gốc. Đây là bản EPUB của "file findings" mà guard
mất dấu đã dùng. Nếu tổng số fallback > 0, `run_epub_job()` `logger.warning` một dòng tổng kết —
việc hiển thị lên UI để **Bước 3/3** làm, không mở rộng scope ở đây.

**C-6. Điều KHÔNG được làm**: không dùng fallback cho unit bị guard mất dấu (guard đó tự có 2 tầng
retry và đang hoạt động 0/107 — không đụng vào), không dùng fallback khi
`EpubRequestRunawayError`/`EpubChunkCostCapExceeded` (2 lỗi tài chính, phải abort ngay như cũ), và
không tự nới `EPUB_UNIT_HARD_MAX_CHARS`.

---

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

##### 6.20.14.6. Tổng hợp hằng số & artifact mới (cho Dev)

| Hằng số | Cũ | Mới | File | Trạng thái |
|---|---|---|---|---|
| `EPUB_REQUEST_CHAR_BUDGET` | 3.000 | **1.100** | `chunking.py` + `config.py` | Suy từ số đo thật (§6.20.14.0a), vẫn ⚠️ ASSUMED về hiệu quả |
| `EPUB_REQUEST_MAX_UNITS` | — | **6** | `chunking.py` + `config.py` | MỚI, ⚠️ ASSUMED |
| `EPUB_MAX_SINGLE_ID_RETRIES` | 5 | **2** | `chunking.py` | ⚠️ ASSUMED |
| `EPUB_MAX_EXTRA_REQUESTS_PER_SLICE` | 6 | **3** | `chunking.py` | ⚠️ ASSUMED |
| `EPUB_FALLBACK_MAX_RATIO_CHUNK` | — | **0,20** | `chunking.py` + `config.py` | MỚI, ⚠️ ASSUMED |
| `EPUB_FALLBACK_MAX_RATIO_JOB` | — | **0,05** | `chunking.py` + `config.py` | MỚI — trần trên bị BR-EPUB-05 ép (≤10%), giá trị cụ thể ⚠️ ASSUMED |

Artifact mới: `_salvage_epub_id_pairs()`, `EpubParseOutcome`,
`parse_epub_batch_response_detailed()` (`prompt_builder.py`); `fallback_units.json` (mỗi chunk dir);
`untranslated_units.json` (job output dir); khoá `fallback_units` trong `anomalies.json`; trường
`salvaged_count` trong `requests.jsonl`; tham số `untranslated_ids` của
`EpubDocument.write_translated()`; tham số `request_max_units` của `plan_epub_chunks()`.

---

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

### 6.21. Giữ chuẩn công thức toán/lý/hoá khi chiếu sang Markdown (yêu cầu xuyên suốt của user, 2026-09-08)

**Phạm vi**: mục này là **quy tắc dùng chung** cho mọi chỗ app chuyển nội dung có số mũ / chỉ số
dưới / phân số sang Markdown hoặc text thuần — cụ thể là §6.15 (US-15 Markdown parse-only, cả nhánh
PDF lẫn nhánh EPUB) và §6.20 (US-22 dịch EPUB). Nó tồn tại vì **cùng một lỗi đã xuất hiện độc lập ở
cả hai thiết kế**, ở cùng một tầng dùng chung (`EpubDocument` / trích xuất HTML) — sửa một chỗ mà
không sửa chỗ kia là đúng cấu hình sinh ra 2 nhánh lệch nhau mà Protocol 6 tồn tại để chặn.

**Yêu cầu gốc của user (2026-09-08)**: *"công thức toán/lý/hoá (không chỉ công thức bánh) phải giữ
chuẩn, không gây hiểu lầm — số mũ, chỉ số dưới, phân số phải giữ đúng ký hiệu"*.

#### 6.21.1. Nguyên tắc: 3 đích khác nhau, 3 cơ chế khác nhau

Điều quan trọng nhất phải hiểu trước khi đọc phần còn lại: **"giữ chuẩn" không có nghĩa là "cùng
một biểu diễn ở mọi nơi"** — nó có nghĩa là **không mất thông tin và không gây hiểu lầm** ở đích
đang xét.

| Đích | Có giữ được thẻ HTML không? | Cơ chế | Fidelity |
|---|---|---|---|
| **EPUB → EPUB** (US-22, §6.20) | **CÓ** — output cũng là XHTML | **Không chuyển đổi gì cả**: unit là inner-HTML, `<sup>`/`<sub>` đi qua LLM nguyên vẹn (X2), prompt cấm sửa (X4) | 100% |
| **EPUB → Markdown** (US-15 nhánh EPUB, §6.15 S15-8) | **KHÔNG** — Markdown không có `<sup>`/`<sub>` | Chuẩn hoá tường minh theo §6.21.2 **trước khi** gọi `markdownify` | Không mất thông tin, không nhập nhằng |
| **PDF → Markdown** (US-15 nhánh PDF, §6.15) | Không áp dụng — MinerU tự sinh Markdown, app không kiểm soát tầng này | Không thể sửa ở app → xử lý bằng **chọn `parse_method` đúng** (§6.21.3) | Có giới hạn đã đo, xem L-4 |

#### 6.21.2. Quy tắc chuẩn hoá `<sup>`/`<sub>` cho đích Markdown (spec cho Dev)

##### Vì sao KHÔNG được dùng hành vi mặc định của `markdownify`

`markdownify==1.2.3` (bản đã cài để spike, `mdspike` venv) định nghĩa:
`sub_symbol = ''` và `sup_symbol = ''` ở `markdownify/__init__.py:195-196`, dùng bởi
`convert_sub`/`convert_sup` (`:722`, `:724`). Nghĩa là **mặc định nó XOÁ dấu hiệu sup/sub và dán
nội dung dính vào text xung quanh**. Tự chạy thật:

| Input HTML | `markdownify` mặc định | Đánh giá |
|---|---|---|
| `<sup>1</sup>/<sub>3</sub> cup soy grits` | `1/3 cup soy grits` | ✅ đúng (may mắn) |
| `1<sup>1</sup>/<sub>3</sub> cups flour` | **`11/3 cups flour`** | ❌ **SAI 8,25×** — hỗn số thành phân số ảo |
| `x<sup>2</sup> + y<sup>3</sup> - 5x<sup>-1</sup>` | **`x2 + y3 - 5x-1`** | ❌ **SAI** — x² thành "x2", số mũ âm thành phép trừ |
| `H<sub>2</sub>O, CO<sub>2</sub>, Ca(OH)<sub>2</sub>` | `H2O, CO2, Ca(OH)2` | ⚠️ tạm chấp nhận cho hoá học, nhưng nhập nhằng |
| `network.<sup>12</sup>` (footnote) | `network.12` | ❌ chú thích dính vào câu thành số |

Đặt cạnh rule cũ của §6.20.5 (`extract()` bỏ `sup`) trên **6 dòng nguyên liệu thật** của
`ops/xhtml/chapter01.html`:

| Cách làm | Kết quả trên 6 dòng thật | Đúng |
|---|---|---|
| `extract()` (spec cũ) | `/ 3 cup soy grits` ×5, `1 / 3 cups unbleached white flour` ×1 | **0/6** |
| `markdownify` mặc định (đề xuất của Expert) | `1/3 cup …` ×5, **`11/3 cups …`** ×1 | **5/6** |
| **Chuẩn hoá §6.21.2 (chốt)** | `1/3 cup …` ×5, **`1 1/3 cups …`** ×1 | **6/6** |

Ngoài ra: đặt hành vi đúng của app phụ thuộc vào **giá trị mặc định của một option trong thư viện
bên thứ ba** là đúng loại rủi ro Protocol 5 nói tới — `sup_symbol` đổi mặc định ở version sau là
output của ta đổi im lặng. Cách chốt dưới đây **xử lý xong `sup`/`sub` TRƯỚC khi `markdownify`
nhìn thấy chúng**, nên độc lập hoàn toàn với option của thư viện.

##### `normalize_sup_sub(soup)` — chạy trên soup, TRƯỚC `markdownify`

Đặt tại `src/services/epub_document.py` (dùng bởi `to_markdown()`), hoặc module riêng nếu sau này
có consumer thứ hai. Sau khi chạy, **không còn thẻ `sup`/`sub` nào** trong soup.

**Bước 1 — Phân số (ưu tiên cao nhất, chạy trước)**
Mẫu: `<sup>N</sup>` + text node **chỉ chứa** `/` hoặc `⁄` (U+2044) + `<sub>M</sub>`, với `N`, `M`
đều là chuỗi chữ số. → thay cả 3 node bằng **một** text node `"N/M"`.
**Bắt buộc — guard hỗn số (đây là chỗ cách của Expert hỏng)**: nếu ký tự ngay trước `<sup>` là một
**chữ số**, chèn thêm **một dấu cách** trước phân số → `1<sup>1</sup>/<sub>3</sub>` ra
`1 1/3`, **không** phải `11/3`.

**Bước 2 — Mọi `<sup>`/`<sub>` còn lại**
Với nội dung `c` (đã strip):
- Nếu `c` khớp `[0-9+\-=()]+` (thuần số/dấu) **hoặc** là **đúng 1 chữ cái**, **và** mọi ký tự của
  `c` đều có ký tự Unicode super/subscript tương ứng → dùng **Unicode**.
- Ngược lại → dùng dạng ASCII tường minh `^(c)` cho sup, `_(c)` cho sub. Nếu `c` đã bắt đầu bằng
  `(` và kết thúc bằng `)` thì không bọc thêm ngoặc (`(n-1)` → `^(n-1)`, không phải `^((n-1))`).

Bảng ánh xạ Unicode (đủ cho toàn bộ hoá học phổ thông và số mũ số học):
```
sup: 0123456789+-=()ni  →  ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ
sub: 0123456789+-=()aeoxhklmnpst  →  ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ
```

**Kết quả đã chạy thật của quy tắc trên** (prototype `supsub_design.py`, scratchpad phiên này —
Dev không dùng lại code này, chỉ dùng làm bảng kỳ vọng cho test):

| Input | Output | Ghi chú |
|---|---|---|
| `<sup>1</sup>/<sub>3</sub> cup soy grits` | `1/3 cup soy grits` | phân số |
| `1<sup>1</sup>/<sub>3</sub> cups unbleached white flour` | `1 1/3 cups unbleached white flour` | **hỗn số — ca N-1** |
| `Area = x<sup>2</sup> + y<sup>3</sup> - 5x<sup>-1</sup>` | `Area = x² + y³ - 5x⁻¹` | số mũ, kể cả mũ âm |
| `H<sub>2</sub>O, CO<sub>2</sub>, Ca(OH)<sub>2</sub>, SO<sub>4</sub><sup>2-</sup>` | `H₂O, CO₂, Ca(OH)₂, SO₄²⁻` | hoá học, kể cả ion |
| `network.<sup>12</sup>` | `network.¹²` | chú thích **phân biệt được** với số thường |
| `x<sup>a+b</sup>`, `V<sub>total</sub>` | `x^(a+b)`, `V_(total)` | không map được → ASCII tường minh |
| `10<sup>-6</sup> mol` | `10⁻⁶ mol` | |

**Vì sao chọn Unicode làm mặc định** (user để Tech Lead tự quyết, nêu 2 phương án):
Markdown thuần **không có** cú pháp sup/sub (CommonMark không có; `^…^`/`~…~` là mở rộng riêng của
Pandoc, hiển thị nguyên văn ở mọi renderer khác). Vì vậy Unicode là biểu diễn **duy nhất** vừa đúng
về mặt thị giác ở mọi renderer, vừa không mất thông tin, vừa ngắn. Dạng `^`/`_` được giữ lại **đúng
cho những ca Unicode không biểu diễn nổi** — nơi mà "dài dòng nhưng rõ ràng" tốt hơn "ngắn nhưng
sai".

**Một setting duy nhất, `.env`-only** (không đưa vào `SETTINGS_DB_OVERRIDABLE_FIELDS` — đây là lựa
chọn biểu diễn, không phải tham số vận hành):

| Field | Default | Ý nghĩa |
|---|---|---|
| `markdown_supsub_style` | `"unicode"` | `"unicode"` = bảng trên. `"pandoc"` = `x^2^` / `H~2~O` (cho user nào render bằng Pandoc). **Quy tắc phân số ở Bước 1 GIỐNG NHAU ở cả 2 chế độ** — phân số không phải là sup/sub, nó là một con số |

##### Tác động chéo sang §6.18 (US-20) — đã kiểm, KHÔNG cần sửa §6.18

Chọn Unicode làm biểu diễn mặc định nghĩa là `document.md` của nhánh `parse_only` sẽ chứa `²`, `₂`
… — mà chính file đó là `source_text` của US-20 (§6.18.5 dòng `parse_only`). Đã kiểm: bước 2 của
`normalize_source_text()` (§6.18.8 T4) là `unicodedata.normalize("NFKC")`, và NFKC **tự** hạ các ký
tự này về chữ số thường (tự chạy: `'x²'→'x2'`, `'H₂O'→'H2O'`, `'network.¹²'→'network.12'`). Nên
tokenizer của US-20 không nhìn thấy ký tự lạ nào và **không cần rule mới**. Ghi lại ở đây để
Reviewer không phải tự suy ra, và để nếu sau này `markdown_supsub_style` đổi sang `"pandoc"` thì
biết ngay chỗ phải kiểm lại (`^`/`~` **không** bị NFKC xử lý).

#### 6.21.3. Nhánh PDF: app KHÔNG kiểm soát được tầng này — xử lý bằng `parse_method`

Ở nhánh PDF, Markdown do **MinerU** sinh ra; app không có chỗ nào để chèn `normalize_sup_sub()`.
Giới hạn đã đo (L-4, §6.15.5, số đo của Expert trên cùng một file qua cả 2 mode):

```
Cùng dòng công thức trong Figoni:
  parse_method="ocr" → "= scale readability × 10"     (ĐÚNG)
  parse_method="txt" → "  scale readability - 10"     (SAI: '=' mất, '×' thành '-')
```

Nguyên nhân: font ký hiệu trong text layer không map Unicode; OCR đọc từ pixel nên đúng. Đây
**không** phải bug của app và không sửa được ở app.

**Chốt — thêm tham số `parse_method` override cho `parse_only`** (mở rộng nhỏ, S15 bản gốc không
có): `POST /api/jobs` nhận thêm field optional `parse_method ∈ {auto, txt, ocr}`, mặc định `auto` =
mapping theo `file_type` như S15 đã chốt (`pdf_digital`→`txt`, `pdf_scan`→`ocr`). MinerU hỗ trợ cả
3 (§6.9.2). UI: 1 checkbox *"Tài liệu nhiều công thức toán/hoá — ưu tiên độ chính xác ký hiệu
(chậm hơn)"* → gửi `parse_method="ocr"`.
**Lưu ý bắt buộc đi kèm**: khi user ép `ocr` cho một file `pdf_digital`, rule S15-6 vẫn giữ nguyên
— `ocr_confidence` **ép `None` theo `file_type`**, không theo `parse_method`. Nếu Dev đổi rule
S15-6 sang rẽ theo `parse_method`, cột `jobs.ocr_confidence` lại mang 2 ý nghĩa, đúng thứ S15-6
tồn tại để chặn.

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

## 7. Docker Setup

### 7.1. docker-compose.yml

```yaml
version: "3.9"

services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"     # FastAPI
    volumes:
      - ./data:/data    # Persistent storage (DB, uploads, outputs)
      - ./fonts:/app/fonts
    environment:
      - DATABASE_URL=sqlite:///data/bb_translation.db
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - DEEPL_API_KEY=${DEEPL_API_KEY:-}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
      - OLLAMA_ENDPOINT=${OLLAMA_ENDPOINT:-http://host.docker.internal:11434}
      - NOTO_FONT_PATH=/app/fonts/GoNotoKurrentRegular.ttf
      - MAX_CONCURRENT_FILES=${MAX_CONCURRENT_FILES:-3}
      - MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-500}
      - LOG_LEVEL=${LOG_LEVEL:-info}
    deploy:
      resources:
        limits:
          memory: 16G     # M1 Pro 32GB — de lai 16GB cho host
          cpus: "6"       # 10 cores — de lai 4 cho host
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Sidecar MinerU — CHI dung duoc tren Linux/WSL2 + NVIDIA GPU (xem 6.9.8).
  # Tren macOS (moi truong dich chinh v1.0) KHONG bat profile nay; chay MinerU
  # native bang `mineru-api --host 127.0.0.1 --port 8010` va tro
  # MINERU_ENDPOINT=http://localhost:8010.
  mineru:
    # Image phai tu build tu repo MinerU — `opendatalab/mineru:latest` KHONG ton
    # tai tren Docker Hub (6.9.1 S9):
    #   wget https://raw.githubusercontent.com/opendatalab/MinerU/master/docker/global/Dockerfile
    #   docker build -t mineru:latest -f Dockerfile .
    image: mineru:latest
    profiles:
      - ocr
    entrypoint: mineru-api
    command: ["--host", "0.0.0.0", "--port", "8000"]   # 8000 la default that cua MinerU
    ports:
      - "8010:8000"    # host 8010 (8000 da bi app chiem) → container 8000
    environment:
      - MINERU_MODEL_SOURCE=local
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: "4"

volumes:
  data:
```

> `app` tro toi MinerU qua mang noi bo compose: `MINERU_ENDPOINT=http://mineru:8000`
> (**khong** phai `http://mineru:8010` — MinerU khong listen 8010 ben trong container).

### 7.2. Dockerfile

```dockerfile
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    calibre \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/
COPY web/ ./web/
COPY fonts/ ./fonts/

# Create data directories
RUN mkdir -p /data/uploads /data/processing /data/outputs /data/glossary

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.3. Environment Variables

```bash
# .env (KHONG commit vao git)
CLAUDE_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...          # Optional
DEEPL_API_KEY=...              # Optional
GEMINI_API_KEY=AIza...         # Optional
DEEPSEEK_API_KEY=sk-...        # Optional
OLLAMA_ENDPOINT=http://host.docker.internal:11434  # Ollama chay tren host

# MinerU OCR (xem 6.9.8)
#   - macOS native:  http://localhost:8010   (chay `mineru-api --port 8010`)
#   - Docker sidecar: http://mineru:8000
MINERU_ENDPOINT=http://localhost:8010
MINERU_TASK_TIMEOUT_SECONDS=3600      # tong thoi gian cho 1 task OCR
MINERU_REQUEST_TIMEOUT_SECONDS=120    # timeout tung request HTTP le
OCR_CONFIDENCE_THRESHOLD=0.80         # nguong canh bao AC-11.2 — provisional, xem 6.9.7

# Performance tuning
MAX_CONCURRENT_FILES=3
MAX_UPLOAD_SIZE_MB=500
LOG_LEVEL=info

# Font
NOTO_FONT_PATH=/app/fonts/GoNotoKurrentRegular.ttf
```

---

## 8. Project Directory Structure

```
BB-Translation/
├── CLAUDE.md                    # Project-specific conventions
├── project_state.json           # Shared context (Protocol 4)
├── pyproject.toml               # Python project config (uv)
├── uv.lock                      # Dependency lockfile
├── .env                         # API keys (gitignored)
├── .env.example                 # Template cho .env
├── .gitignore
│
├── .claude/
│   └── agents/                  # Claude Code agent definitions
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/
│   ├── PRD.md
│   ├── Architecture.md          # ← File nay
│   ├── CHANGELOG.md
│   ├── review-report.md
│   └── test-report.md
│
├── src/
│   ├── __init__.py
│   │
│   ├── api/                     # FastAPI web server
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── deps.py              # Dependency injection (DB session, etc.)
│   │   ├── websocket.py         # WebSocket manager cho progress
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── upload.py        # POST /api/upload
│   │       ├── translate.py     # POST /api/translate, GET /api/jobs/*
│   │       ├── glossary.py      # /api/glossaries/* CRUD
│   │       ├── history.py       # /api/history/*
│   │       ├── download.py      # /api/download/*
│   │       └── settings.py      # /api/settings/*
│   │
│   ├── core/                    # Business logic
│   │   ├── __init__.py
│   │   ├── file_router.py       # Detect file type (born-digital/scan/epub)
│   │   ├── job_orchestrator.py  # Batch scheduling, concurrency, retry
│   │   ├── chunking.py          # Page-range chunking algorithm
│   │   ├── glossary_manager.py  # Glossary CRUD, merge, prompt builder
│   │   ├── prompt_builder.py    # Build translation prompt (glossary + units + style)
│   │   ├── cost_estimator.py    # Estimate API cost truoc khi dich
│   │   └── progress_tracker.py  # Track & emit progress events
│   │
│   ├── pipelines/               # Translation pipelines theo file type
│   │   ├── __init__.py
│   │   ├── pdf_digital.py       # PDF born-digital pipeline (pdf2zh)
│   │   ├── pdf_scan.py          # PDF scan pipeline (MinerU → pdf2zh)
│   │   ├── epub.py              # EPUB pipeline (bilingual_book_maker)
│   │   └── base.py              # Abstract pipeline interface
│   │
│   ├── services/                # External service adapters
│   │   ├── __init__.py
│   │   ├── translation.py       # TranslationProvider protocol
│   │   ├── claude_provider.py   # Claude API (anthropic SDK)
│   │   ├── openai_provider.py   # OpenAI API
│   │   ├── deepl_provider.py    # DeepL API
│   │   ├── ollama_provider.py   # Ollama local
│   │   ├── pdf2zh_runner.py     # Wrapper goi pdf2zh CLI
│   │   ├── pdf2zh_service_map.py # Provider noi bo → -s + env cua pdf2zh (6.6.3)
│   │   ├── mineru_runner.py     # Wrapper goi MinerU CLI / HTTP API
│   │   └── calibre_runner.py    # Wrapper goi ebook-convert
│   │
│   ├── preprocess/              # Pre-processing TRUOC translation  (MOI, 6.10)
│   │   ├── __init__.py
│   │   └── searchable_pdf.py    # Cau noi OCR -> pdf2zh: whiteout + text layer vo hinh
│   │
│   ├── postprocess/             # Post-processing sau translation
│   │   ├── __init__.py
│   │   ├── font_shrink.py       # Detect overflow + shrink font (PyMuPDF)
│   │   ├── bilingual_merge.py   # Merge VI + EN pages (PyMuPDF)
│   │   └── chunk_merge.py       # Merge chunks thanh 1 PDF (PyMuPDF)
│   │
│   ├── models/                  # Data models (SQLModel + Pydantic)
│   │   ├── __init__.py
│   │   ├── database.py          # SQLite engine, session factory
│   │   ├── batch.py             # Batch model
│   │   ├── job.py               # Job model
│   │   ├── chunk.py             # Chunk model
│   │   ├── glossary.py          # Glossary + GlossaryEntry models
│   │   ├── overflow.py          # OverflowReport model
│   │   ├── cache.py             # TranslationCache model
│   │   └── settings.py          # Settings model
│   │
│   └── utils/                   # Helpers
│       ├── __init__.py
│       ├── file_utils.py        # Hash, size, temp file management
│       ├── pdf_utils.py         # PyMuPDF helpers
│       ├── excel_utils.py       # openpyxl helpers
│       ├── rate_limiter.py      # Token bucket rate limiter
│       └── logging.py           # Structured logging setup
│
├── web/                         # Frontend (static files served by FastAPI)
│   ├── index.html               # Main page — upload + dashboard
│   ├── glossary.html            # Glossary management page
│   ├── history.html             # Translation history page
│   ├── settings.html            # Settings page
│   ├── css/
│   │   └── styles.css           # Tailwind CSS (CDN) + custom styles
│   └── js/
│       ├── app.js               # Alpine.js app logic
│       ├── upload.js            # Upload + drag-drop handler
│       ├── websocket.js         # WebSocket client cho progress
│       └── glossary.js          # Glossary CRUD UI logic
│
├── fonts/
│   └── GoNotoKurrentRegular.ttf
│
├── tests/
│   ├── conftest.py              # Pytest fixtures
│   ├── test_file_router.py
│   ├── test_chunking.py
│   ├── test_glossary_manager.py
│   ├── test_prompt_builder.py
│   ├── test_font_shrink.py
│   ├── test_bilingual_merge.py
│   ├── test_cost_estimator.py
│   └── integration/
│       ├── test_pdf_pipeline.py
│       ├── test_epub_pipeline.py
│       └── test_batch_processing.py
│
└── data/                        # Runtime data (gitignored, Docker volume)
    ├── bb_translation.db
    ├── uploads/
    ├── processing/
    ├── outputs/
    └── glossary/
```

---

## 9. Deployment & Scaling

### 9.1. Local Docker (M1 Pro 32GB) — v1.0

**Resource allocation**:
- Docker app container: 16GB RAM, 6 CPU cores
- MinerU tren macOS: chay **native tren host** (khong Docker — 6.9.8), ~4-8GB RAM khi OCR
- Host (macOS + browser): 8-16GB RAM con lai
- Disk: ~10GB cho Docker images + models, ~5GB cho data (du cho hang tram file)

**Performance estimates** (M1 Pro):
- PDF born-digital 100 trang: ~5-10 phut (phụ thuoc API latency)
- PDF scan 100 trang: +3-5 phut cho OCR
- EPUB 300 trang: ~10-15 phut
- Batch 5 files x 200 trang: ~30-45 phut (3 concurrent)

**Khoi dong**:
```bash
# Lan dau
cp .env.example .env
# Sua .env: them API keys

docker compose up -d

# Voi OCR support — macOS (KHONG dung Docker cho MinerU, xem 6.9.8):
uv pip install "mineru[core]"
mineru-api --host 127.0.0.1 --port 8010 &     # kiem tra: curl http://localhost:8010/health
# .env: MINERU_ENDPOINT=http://localhost:8010

# Voi OCR support — Linux/WSL2 + NVIDIA:
#   docker build -t mineru:latest -f <MinerU>/docker/global/Dockerfile .
docker compose --profile ocr up -d
# .env: MINERU_ENDPOINT=http://mineru:8000

# Truy cap: http://localhost:8000
```

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

## 10. Security & Configuration

### 10.1. API Key Management
- API keys luu trong `.env` file, khong commit vao git
- Trong SQLite, API keys encrypted bang Fernet (symmetric encryption)
- Key encryption key lay tu environment variable `ENCRYPTION_KEY`

### 10.2. File Upload Security
- Validate file extension + magic bytes (khong chi dua vao extension)
- Max file size: 500MB (configurable)
- Upload files luu trong isolated directory, khong execute permission
- Filename sanitization: strip path traversal, unicode normalize

### 10.3. Rate Limiting
- Token bucket rate limiter cho API calls
- Default: Claude — 4000 requests/min (Tier 1), configurable
- Khi gan limit → giam concurrency tu dong
- Log moi API call cost cho audit

---

*Document version: 1.0*
*Author: Tech Lead*
*Status: Draft — Pending user review (Human Checkpoint 2)*

---

## Root Cause Analysis: Line-break/List Regression (2026-09-06)

**Tác giả**: Tech Lead — phân tích, KHÔNG implement. Dev implement ở bước sau.
**Triệu chứng user báo**: "Đôi chỗ bóc tách xuống dòng chưa chính xác" + "Xuống dòng ở
các chỗ bulleted/numbered".

### N1. Kết luận ngắn

Root cause **KHÔNG nằm trong code của team**. Nó nằm ở heuristic tách đoạn của babeldoc,
được kích hoạt bởi flag `--split-short-lines` mà `BabeldocRunner` hardcode bật:

- `src/services/babeldoc_runner.py:278` — `"--split-short-lines"` trong list `args`.

Commit `250709c` **không tạo ra** bug này. `git log -S "--split-short-lines" --
src/services/babeldoc_runner.py` chỉ trả về đúng 1 commit: `b29a54b` (Initial commit
v1.2.0, 2026-09-05) — flag đã có từ đầu. `250709c` chỉ đụng `_thinking_args` và
`_assert_gemini_model_safe`.

**Vì sao bug xuất hiện "sau" 250709c**: đây là bug latent bị **bóc trần** (unmask) chứ
không phải bug mới — cùng dạng với Bug #5 trong bối cảnh Protocol 6. Trước 250709c,
`deepseek-v4-flash` đốt hết `max_tokens=2048` vào thinking token → `json.loads("")` raise →
babeldoc rơi cả batch xuống nhánh fallback (giữ nguyên text gốc, không render lại layout
đã tách đoạn). Sau khi 250709c gửi `--openai-thinking disabled`, dịch **thành công** →
babeldoc lần đầu tiên thực sự **render theo cấu trúc đoạn mà `paragraph_finder` đã tách**.
Cấu trúc đó vốn đã sai từ đầu, chỉ là trước đây không ai nhìn thấy vì nội dung bị mất
trước khi tới bước render.

### N2. Nguồn xác thực (Protocol 5 / R5-01)

Toàn bộ claim dưới đây đọc trực tiếp từ **source thật của babeldoc 0.6.4 đã cài**
(`babeldoc --version` → `babeldoc 0.6.4`), tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`.
Không có claim nào từ trí nhớ.

| # | Claim | Nguồn (file:line) |
|---|-------|-------------------|
| L1 | `--split-short-lines` là `store_true`, help ghi rõ **"may cause poor typesetting & bugs"** | `babeldoc/main.py:179-182` |
| L2 | `--short-line-split-factor` default `0.8` | `babeldoc/main.py:184-189`; `format/pdf/translation_config.py:179` |
| L3 | Heuristic tách đoạn nằm ở `process_independent_paragraphs()` | `format/pdf/document_il/midend/paragraph_finder.py:841-925` |
| L4 | Điều kiện tách: `split_short_lines AND prev_width < median_width * factor` **OR** `is_bullet_point(chars[0])` của dòng hiện tại | `paragraph_finder.py:891-901` |
| L5 | `median_width` tính trên **TẤT CẢ dòng của cả trang**, gộp chung mọi paragraph (heading, caption, ô bảng, footnote, số trang) | `paragraph_finder.py:822-839`, gọi tại `:284` |
| L6 | `BULLET_POINT_PATTERN` chỉ khớp **glyph bullet**: `■•⚫⬤◆◇○●◦‣⁃▪▫∗†‡¹²³…·`. **KHÔNG có** `-` (hyphen-minus), `–`, `*`, và **KHÔNG có** hỗ trợ numbered list (`1.`, `a)`, `(1)`) | `format/pdf/document_il/utils/layout_helper.py:50-52` |
| L7 | `is_bullet_point()` chỉ xét **ký tự đầu tiên** của dòng (`chars[0]`) | `layout_helper.py:55-65`; call site `paragraph_finder.py:899-901` |
| L8 | babeldoc chỉ `.strip()` output LLM — newline **bên trong** chuỗi trả về KHÔNG bị loại bỏ | `format/pdf/document_il/midend/il_translator_llm_only.py:718, 987, 998` |

### N3. Root cause chi tiết — 3 cơ chế độc lập

#### RC-1 (chính) — `--split-short-lines` tách nhầm dòng ngắn giữa đoạn

`paragraph_finder.py:891-895`: với mỗi cặp dòng liền kề trong 1 paragraph, nếu **dòng
trước** (`prev_width`) hẹp hơn `median_width * 0.8` thì mọi dòng từ vị trí `j` trở đi bị
cắt ra thành paragraph mới.

Heuristic này giả định "dòng ngắn = dòng cuối đoạn". Giả định đó **sai** trong đúng loại
tài liệu của project (sách dạy làm bánh):

- Dòng ngay trước công thức/đơn vị đo, dòng kết câu trong cột căn đều.
- **Nghiêm trọng nhất (L5)**: `median_width` gộp mọi dòng của cả trang. Một trang vừa có
  body full-width vừa có bảng nguyên liệu / caption / cột hẹp → median bị kéo lệch → **mọi
  dòng của khối hẹp** đều `< 0.8 * median` → mỗi dòng thành 1 paragraph riêng → LLM dịch
  từng dòng rời rạc, mất ngữ cảnh câu → đúng triệu chứng "bóc tách xuống dòng chưa chính xác".

Đây cũng chính là rủi ro mà chính babeldoc cảnh báo trong help text (L1) — flag này được
bật hardcode mà không có nguồn xác thực nào trong Architecture.md chứng minh lợi ích của
nó lớn hơn tác hại.

#### RC-2 — bullet pattern không phủ `-` và numbered list

Nhánh `or` ở `paragraph_finder.py:896-901` chạy **độc lập với `split_short_lines`** (nó
nằm ngoài mệnh đề `and`). Nghĩa là: **babeldoc đã tự tách bullet item đúng cách mà KHÔNG
cần `--split-short-lines`** — flag kia không đóng góp gì cho việc nhận diện list.

Nhưng nhánh đó chỉ nhận diện được glyph bullet (L6) trên ký tự đầu dòng (L7). Hệ quả:

- `• Trộn bột` → `chars[0] = "•"` → khớp → tách đúng.
- `- Trộn bột` → `chars[0] = "-"` (U+002D) → **không khớp** → không tách.
- `1. Nướng ở 180°C` → `chars[0] = "1"` (ASCII digit) → **không khớp** → không tách.
  (Pattern có `¹²³` superscript, không có digit thường.)

→ Dash-bullet và numbered list **hoàn toàn phụ thuộc vào RC-1** để được tách. Mà RC-1 tách
theo hình học, không theo ngữ nghĩa → khi các item cùng dài (gần median) chúng bị **gộp**
thành một đoạn; khi một item xuống dòng thứ 2 ngắn thì bị **tách sai chỗ**. Đúng triệu
chứng thứ hai user báo: "Xuống dòng ở các chỗ bulleted/numbered".

Tác dụng phụ khác của L6: pattern chứa `¹²³` và `·` → **marker footnote** và **dấu chấm
giữa** bị hiểu nhầm là bullet → tách đoạn thừa.

#### RC-3 (phụ) — prompt yêu cầu giữ list ở cấp fragment

`src/core/prompt_builder.py:53-54, 111-112, 247-248` yêu cầu "Bullet list phải dịch thành
bullet list, numbered list phải dịch thành numbered list".

babeldoc gửi LLM **từng paragraph đã tách sẵn** (sản phẩm của RC-1/RC-2), không phải cả
khối list. Khi 1 item bị cắt thành fragment không còn ký tự bullet, chỉ thị này khiến LLM
có xu hướng **tự thêm lại** bullet/newline vào fragment. Vì babeldoc chỉ `.strip()` hai
đầu (L8), newline nội bộ do LLM sinh ra **sống sót** vào output.

⚠️ **CHƯA VERIFY**: chưa đo được tần suất LLM thực sự thêm newline, và chưa verify renderer
của babeldoc xử lý `\n` nội bộ ra sao (xuống dòng thật hay thành ô vuông tofu). Dev/QA cần
đo bằng live run trước khi coi RC-3 là nguyên nhân thật — hiện chỉ là giả thuyết có cơ sở
source (L8), không phải kết luận.

### N4. Vì sao lọt qua toàn bộ review/test

`tests/test_babeldoc_runner.py:201` chỉ assert `"--split-short-lines" in args` — tức là
test **xác nhận lại chính giả định đang sai**, không kiểm chứng flag đó có tạo layout đúng
hay không. Không có test nào trong toàn repo dựng PDF có bullet/numbered list rồi kiểm tra
cấu trúc đoạn của output (`grep -rn "bullet" tests/` chỉ hit `test_prompt_builder.py:62`,
mà file đó chỉ assert chuỗi "bullet" có mặt trong prompt).

Đây đúng dạng lỗ hổng Protocol 5 mô tả: mock/assert tự nhất quán với giả định, không nhất
quán với thực tế. Bổ sung đề xuất cho Protocol 5: **flag CLI bật hardcode cũng là một
"contract" cần nguồn xác thực** — hiện `--split-short-lines` được biện minh trong docstring
`babeldoc_runner.py:242-243` là "fix lỗi gộp dòng danh sách của pdf2zh" nhưng không có
nguồn xác thực nào, và theo L4 thì lý do đó **sai**: việc tách list do nhánh
`is_bullet_point` đảm nhiệm, độc lập hoàn toàn với flag này.

### N5. Phương án fix đề xuất

**F1 (bắt buộc, gốc rễ) — Bỏ `--split-short-lines` khỏi list hardcode.**
Sửa `src/services/babeldoc_runner.py:278`. Theo L4, nhánh `is_bullet_point` vẫn chạy khi
không có flag → glyph bullet vẫn được tách đúng, chỉ mất đi heuristic hình học đang gây
hại. Đây là fix triệt để cho RC-1, không phải patch tạm.

**F2 — Đưa flag thành tham số có kiểm soát, không hardcode.**
Thêm `split_short_lines: bool = False` vào signature `translate_pages()` và một field
tương ứng trong `Settings` (`src/core/config.py`), mặc định `False`. Lý do: một số tài liệu
scan qua cầu nối `searchable_pdf` có thể vẫn cần heuristic này; khoá cứng ở một trong hai
đầu đều sai. Nếu bật, đồng thời cho phép chỉnh `--short-line-split-factor` (mặc định
babeldoc `0.8` theo L2; hạ xuống ~`0.5` sẽ giảm mạnh false-positive vì chỉ còn dòng thật
sự ngắn mới bị tách).

**F3 — Bù cho RC-2 bằng tiền xử lý, KHÔNG fork babeldoc.**
babeldoc không có hook nào cho `BULLET_POINT_PATTERN`, và monkey-patch một
`frozenset`/`re.Pattern` module-level của tool bên thứ 3 chạy trong **subprocess riêng** là
bất khả thi (ta gọi qua CLI, không import). Hai hướng khả thi, theo thứ tự ưu tiên:

- **F3a**: chuẩn hoá ở bước tiền xử lý cho nhánh `pdf_scan` — trong
  `src/preprocess/searchable_pdf.py`, khi ghi lại text span OCR (`page.insert_text`,
  `:226`), map dash-bullet `-`/`–`/`*` đầu dòng sang `•` (U+2022, có trong L6) để nhánh
  `is_bullet_point` của babeldoc nhận ra. **Chỉ áp dụng được cho nhánh scan** — nhánh
  born-digital không đi qua file này.
- **F3b** (cho born-digital): chấp nhận giới hạn, ghi nhận là known limitation của babeldoc
  0.6.4, và mở issue upstream. **Không tự viết lại paragraph finder** — chi phí/rủi ro vượt
  xa lợi ích, và sẽ tạo đúng loại nợ mà Protocol 5 sinh ra để tránh.

⚠️ **ASSUMED — chưa verify**: F3a giả định việc đổi ký tự bullet trong lớp text vô hình
không làm lệch bbox hay hỏng layout render. Dev phải verify bằng 1 live run trước khi
implement đầy đủ (Protocol 5 R5-02 spike).

**F4 — Sửa prompt cho đúng cấp độ (giảm RC-3).**
`src/core/prompt_builder.py` (3 chỗ: `:53-54`, `:111-112`, `:247-248`). Riêng biến thể
babeldoc (`:247-248`) cần nói rõ: input là **một đoạn đơn lẻ**, phải dịch thành **đúng một
đoạn**, **không được thêm ký tự xuống dòng**, không tự thêm bullet nếu input không có. Giữ
nguyên chỉ thị list cho biến thể `_FILE_*` (dùng cho EPUB/bilingual_book_maker — nơi LLM
thực sự thấy cả khối list).

### N6. Yêu cầu test kèm fix (Protocol 5 + 6)

1. **Golden-file test, không mock tay** (R5-03 / Protocol 5 mục 3): tạo fixture PDF thật có
   3 khối — bullet `•`, bullet `-`, numbered `1./2./3.` — cạnh một bảng hẹp (để ép
   `median_width` lệch, tái hiện RC-1). Lưu tại `tests/fixtures/babeldoc/`.
2. **Assert cấu trúc, không assert flag**: thay assert kiểu
   `assert "--split-short-lines" in args` bằng test đọc output PDF bằng PyMuPDF và đếm số
   block/đoạn, so với số item mong đợi. Assert flag chỉ chứng minh ta gọi đúng cái ta định
   gọi, không chứng minh kết quả đúng.
3. **Live E2E (R6-03)**: chạy xuyên suốt 1 file thật, **mở PDF output và đọc nội dung**
   vùng list, xác nhận số item khớp bản gốc — không tin field `status`.
4. **Data lineage (R6-02)**: nếu implement F2, test phải assert giá trị
   `split_short_lines` từ `Settings` thực sự tới được `args` của subprocess, không chỉ
   `assert_awaited()`.

### N7. Việc KHÔNG phải nguyên nhân (đã loại trừ)

- `src/core/chunking.py` — chunking thuần **theo trang** (`ChunkPlan.page_start/page_end`),
  không hề đụng tới text. Không thể cắt giữa một list item. Loại trừ giả thuyết (d).
- `src/postprocess/chunk_merge.py`, `bilingual_merge.py` — ghép **ở cấp trang** bằng
  `fitz.insert_pdf()`, không đọc/ghi text. Không thể chèn xuống dòng. Loại trừ.
- `src/postprocess/font_shrink.py` — không nằm trong nhánh babeldoc (babeldoc tự vẽ lại
  text). Loại trừ giả thuyết (c).
- `250709c` — không đụng bất kỳ file nào trong `src/core/`, `src/postprocess/`,
  `src/preprocess/`. Chỉ `babeldoc_runner.py` (2 hàm mới), `config.py` (đổi default model),
  routes API + web UI. Loại trừ giả thuyết "commit gần nhất refactor làm hỏng regex".

### N8. Thứ tự implement đề xuất cho Dev

1. **F1** trước, một mình (một dòng), rồi live-run lại đúng file user báo lỗi → đo xem RC-1
   chiếm bao nhiêu phần triệu chứng. Đây là bước rẻ nhất và có khả năng giải quyết phần lớn.
2. Chỉ khi F1 chưa đủ mới làm **F4**, rồi đo lại.
3. **F2** làm cùng F1 (cùng file, cùng review).
4. **F3a** để sau cùng, và chỉ sau spike verify theo R5-02.

**Trạng thái**: Phân tích — chờ PM/user duyệt trước khi Dev implement.

---

## Đánh giá hướng Post-Processing cho lỗi gộp dòng Numbered List (2026-09-06)

**Tác giả**: Tech Lead — research/đánh giá, KHÔNG implement.
**Bối cảnh**: F1/F2/F4 đã ship, F3 (pre-processing injection ký tự bullet) đã THẤT BẠI qua
spike thật (xem CHANGELOG "F3 — Spike verify"). PM yêu cầu đánh giá hướng can thiệp SAU khi
babeldoc chạy, thay vì trước.

Toàn bộ claim dưới đây đọc trực tiếp từ **source thật babeldoc 0.6.4 đã cài** tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`
(`babeldoc/main.py:29` → `__version__ = "0.6.4"`), hoặc đo bằng script chạy thật trên
fixture có sẵn. Không có claim nào từ trí nhớ (Protocol 5 R5-01).

### P1. babeldoc trả về gì — nguồn xác thực

| # | Claim | Nguồn (file:line) |
|---|-------|-------------------|
| P1 | `BabeldocRunner.translate_pages()` trả `BabeldocResult` chỉ mang `mono_path`/`dual_path` (2 đường dẫn PDF) + stdout/stderr/duration/rate_limit_hits. **Không có bất kỳ cấu trúc text/layout nào** | `src/services/babeldoc_runner.py:191-199` (dataclass), `:374-388` (chỗ dựng return) |
| P2 | App gọi babeldoc qua **CLI trong subprocess riêng** (`asyncio.create_subprocess_exec`), không import in-process | `src/services/babeldoc_runner.py:325-331` |
| P3 | Console script `babeldoc` trỏ tới `babeldoc.main:cli` | `babeldoc-0.6.4.dist-info/entry_points.txt` |
| P4 | Nội bộ babeldoc CÓ 1 cấu trúc trung gian đầy đủ: IL (`il_version_1.Document` → `Page` → `PdfParagraph` → `PdfParagraphComposition` → `PdfLine` → `PdfCharacter`) | `format/pdf/document_il/il_version_1.py`; dùng xuyên suốt `high_level.py:836-1050` |
| P5 | Pipeline nội bộ (hàm `_do_translate_single`) chạy tuần tự **trong cùng 1 process**, các stage là lời gọi hardcode: `LayoutParser` → `ParagraphFinder` → `StylesAndFormulas` → `ILTranslatorLLMOnly` → `Typesetting` → `PDFCreater` | `high_level.py:953-1046`; `_do_translate_single` được gọi trực tiếp tại `:548,558,564,659` (không qua process pool) |
| P6 | `--debug` map thẳng vào `TranslationConfig.debug` | `main.py:53-56` (định nghĩa flag), `main.py:694` (`debug=args.debug`), `translation_config.py:171,233` |
| P7 | Khi `debug=True`, babeldoc **dump IL ra JSON tại 8 mốc**: `create_il.debug.json`, `detect_scanned_file.json`, `layout_generator.json`, `table_parser.json`, `paragraph_finder.json`, `styles_and_formulas.json`, `il_translated.json`, `add_debug_information.json`, `typsetting.json` | `high_level.py:916-919, 946-951, 957-961, 966-970, 973-977, 980-984, 1009-1013, 1015-1021, 1040-1044` |
| P8 | Các dump này ghi vào `working_dir` (mặc định `<CACHE_FOLDER>/working/<stem>`, đổi được bằng `--working-dir`) | `translation_config.py:428-429` (`get_working_file_path`), `:287-298`; `main.py:101` (flag), `:719` |
| P9 | **Dump là MỘT CHIỀU**: `XMLConverter` có `read_xml()`/`from_xml()` (`xml_converter.py:33,40`) nhưng **không có call site nào trong pipeline đọc IL ngược trở lại**. Không có flag kiểu `--resume-from-il`. `grep -rn "read_xml\|from_xml"` toàn source chỉ hit chính định nghĩa | `format/pdf/document_il/xml_converter.py:29-62`; `high_level.py` chỉ gọi `write_json` |

**Kết luận P1**: babeldoc CLI là hộp đen **PDF vào → PDF ra**. IL trung gian tồn tại và
**quan sát được** (`--debug`), nhưng **không tiêm ngược vào được** — nó là dump chẩn đoán,
không phải checkpoint có thể resume. Vì vậy câu hỏi 3 của PM ("hook vào cấu trúc trung gian
qua CLI") **không có đường đi trực tiếp**; muốn hook phải chạy babeldoc in-process (xem
Hướng B).

### P2. Phát hiện mới quan trọng — số liệu biện minh cho F1 đã bị đo sai

Trước khi bàn hướng đi mới, cần sửa lại một kết luận cũ. CHANGELOG F1 ghi:

> "F1 giảm mạnh over-fragmentation của đoạn văn thường (36→11 block — đúng triệu chứng RC-1
> 'xuống dòng chưa chính xác' mà user báo)"

**Số liệu này diễn giải SAI.** Đo lại trực tiếp trên chính 2 fixture đã capture
(`tests/fixtures/babeldoc/page14_split_short_lines_{true,false}_mono.pdf`, PyMuPDF
`get_text("blocks")`, chia vùng theo toạ độ y — danh sách ở `y < 505`, phần văn xuôi
"LỜI CẢM ƠN" ở `y >= 505`):

| Vùng | `--split-short-lines` BẬT (cũ) | TẮT (F1, hiện tại) |
|---|---|---|
| Văn xuôi (`y>=505`) — số block | 4 | 4 |
| Văn xuôi — text sau khi normalize whitespace | **giống hệt nhau, 1368 ký tự, `==` True** | như bên trái |
| Danh sách (`y<505`) — số block | 32 | 7 |
| Danh sách — số block bắt đầu bằng marker `N.` | 28 | 3 |
| Danh sách — các marker nhận ra được | 1,2,3,...,35 (31 marker) | chỉ 1, 2, 17, 27 |

Nghĩa là: **toàn bộ chênh lệch 36 vs 11 block nằm ở vùng danh sách, không phải ở văn xuôi.**
Trên trang này, `--split-short-lines` gây **0 (không) tổn hại** cho đoạn văn thường — văn bản
văn xuôi ra giống hệt từng ký tự ở cả 2 chế độ. 25 block "thêm" chính là 25 mục danh sách
được tách ĐÚNG.

Hệ quả với bản TẮT flag còn nặng hơn con số block gợi ý: các mục bị **dính liền không cả
dấu cách** trong cùng một chuỗi LLM trả về — ví dụ đọc được trong output thật:
`"...nhiều kích cỡ khác nhau3. Rây hoặc lưới lọc4. Máy trộn với tô 5 quart..."`. Đây là lỗi
nội dung nhìn thấy được, không chỉ lỗi thẩm mỹ layout.

⚠️ **Giới hạn của bằng chứng này**: chỉ đo trên **1 trang** (trang 14). RC-1 (heuristic
`median_width` toàn trang, `paragraph_finder.py:822-839,891-895`) vẫn là cơ chế **có thật đã
verify trong source** và vẫn có thể gây hại trên trang có bố cục khác (bảng hẹp cạnh body
full-width). Kết luận đúng là: **tác hại của RC-1 chưa từng được quan sát bằng dữ liệu thật
trên bất kỳ trang nào**, còn lợi ích của flag thì đã quan sát được rõ ràng. Trước đây ta đổi
một tác hại ĐÃ ĐO (gộp danh sách) lấy một tác hại mới CHỈ SUY LUẬN TỪ SOURCE.

### P3. Ba hướng khả thi

#### Hướng A — Hậu xử lý PDF output (câu hỏi 2 của PM)

Sửa `mono.pdf` sau khi babeldoc trả về: tìm block có nhiều marker `N.` dính liền, tách và vẽ
lại.

**Khả thi về mặt phát hiện**: marker vẫn còn trong text (`"...khác nhau3. Rây..."`), regex
tìm được. Project cũng đã có sẵn năng lực vẽ lại text lên PDF đã render
(`src/postprocess/font_shrink.py:311-345`, `_redraw_span()` dùng `page.insert_text()` với
`fontfile`).

**Nhưng không khả thi về mặt chất lượng**, vì việc cần làm không phải "merge dòng" như PM
mô tả ban đầu — mà là **tách một đoạn đã dính liền rồi TÁI TYPESET**: xoá text cũ, chèn
newline tại mỗi marker, tính lại ngắt dòng cho vừa bề rộng cột, tính lại chiều cao khối,
dịch chuyển mọi thứ bên dưới xuống, rồi vẽ lại toàn bộ bằng đúng font subset babeldoc đã
nhúng. Cụ thể:

- Đây là **viết lại module Typesetting của babeldoc** (`high_level.py:1039`) ở phía ngoài,
  không có thông tin layout (`Layout`, `layout_label`, bbox cột) mà babeldoc có sẵn trong IL
  — ta chỉ còn bbox của block sau khi đã render.
- `font_shrink.py:15-25` đã ghi rõ bài học: vẽ lại text bằng font SAI làm hỏng glyph tiếng
  Việt (`"thơm" -> "th·m"`); phải dùng **đúng file font đã nằm trên trang**. Font đó do
  babeldoc nhúng và subset, không phải file trong `fonts/` của project → phải extract font
  ra từ chính PDF output trước khi vẽ, thêm một lớp rủi ro nữa.
- Nội dung dài ra (thêm ngắt dòng) → khối cao lên → tràn sang phần dưới trang. Không có chỗ
  nào để "đẩy xuống" an toàn trong một PDF đã render.

**Đánh giá**: độ phức tạp **rất cao**; rủi ro hỏng nội dung/layout **cao** (đụng đúng 2 loại
lỗi đã có tiền sử trong project: glyph corruption và mất nội dung âm thầm); không phải fork
babeldoc nhưng **tệ hơn fork** ở chỗ phải tái hiện lại logic typeset mà không có dữ liệu
layout; effort **lớn**. → **Không khuyến nghị.**

#### Hướng B — Hook vào IL trước bước render, qua wrapper script (không fork)

babeldoc không có plugin/hook API (`ParagraphFinder(translation_config).process(docs)` là
lời gọi hardcode, `high_level.py:960`). Nhưng vì mọi stage chạy **trong cùng 1 process** (P5),
một **wrapper script** import babeldoc, thay thế hành vi tại runtime, rồi gọi
`babeldoc.main.cli()` là đủ — **không sửa 1 dòng source nào của babeldoc**, không phải fork,
và vẫn giữ nguyên mô hình subprocess hiện tại (`BabeldocRunner` chỉ đổi từ gọi `babeldoc`
sang gọi `<babeldoc-python> wrapper.py <args cũ>`).

Hai biến thể, **đã verify sống 2026-09-06** bằng cách chạy interpreter của chính tool
babeldoc (`/Users/hieutt/.local/share/uv/tools/babeldoc/bin/python`):

- **B-1 (nhỏ, thô)** — nới `BULLET_POINT_PATTERN`.
  Verify: `paragraph_finder.py:30` import `is_bullet_point` **theo tên** vào namespace riêng
  → patch `layout_helper.is_bullet_point` sẽ KHÔNG có tác dụng lên `paragraph_finder`.
  NHƯNG `is_bullet_point` đọc `BULLET_POINT_PATTERN` như **module global tại thời điểm gọi**
  (`layout_helper.py:65`) → patch chính cái pattern thì CÓ tác dụng. Đo thật:
  gán `lh.BULLET_POINT_PATTERN = re.compile(r"[■•⚫◆○●◦‣⁃▪▫0-9]")` rồi gọi
  `paragraph_finder.is_bullet_point(char("1"))` → trả `True` (trước khi patch: `False`);
  `char("a")` vẫn `False`.
  **Hạn chế cố hữu**: call site chỉ truyền `chars[0]` — MỘT ký tự
  (`paragraph_finder.py:899-902`). Không thể phân biệt `"1. Trộn bột"` với một dòng nối tiếp
  vô tình bắt đầu bằng `"180°C..."`. Thêm `0-9` = **mọi dòng bắt đầu bằng chữ số đều thành
  paragraph mới**. False-positive bị chặn ở mức "tách thừa 1 đoạn", cùng loại tác hại với
  RC-1 nhưng hẹp hơn nhiều (chỉ dòng bắt đầu bằng digit, thay vì mọi dòng ngắn).
  → Phức tạp: **thấp** (~20 dòng wrapper). Rủi ro: **thấp-trung bình**. Fork: **không**.
  Effort: **nhỏ**.

- **B-2 (đúng bài)** — bọc `ParagraphFinder.process`.
  Chạy `process()` gốc trước, rồi duyệt IL đã có (`document.page[*]` → paragraph →
  `pdf_paragraph_composition` → `pdf_line`) và tự tách paragraph tại các dòng mở đầu bằng
  marker. Ở tầng này ta thấy **toàn bộ text của dòng**, không chỉ `chars[0]` — nên áp được
  heuristic chống false-positive thật sự mà PM từng yêu cầu (marker tăng dần 1,2,3...; loại
  `"2 cups flour"`; loại dòng mục lục). Code tách có sẵn để tái dùng nguyên xi
  (`paragraph_finder.py:903-929`: dựng `PdfParagraph` mới, cắt composition, gọi
  `self.update_paragraph_data()` cho cả 2, `insert` vào list) — ta gọi lại chính các method
  đó qua `self`, không chép logic typeset.
  Quan trọng: can thiệp diễn ra **TRƯỚC** `ILTranslatorLLMOnly` (`high_level.py:1003`) và
  trước `Typesetting` (`:1039`) → babeldoc vẫn tự dịch và tự dàn trang bình thường, ta không
  đụng gì tới render. Đây chính là điều Hướng A không làm được.
  **Rủi ro thật sự**: phụ thuộc **internal API riêng của babeldoc 0.6.4** (tên method, shape
  `PdfParagraph`). Nâng version babeldoc = phải verify lại toàn bộ (Protocol 5 mục 5). Cần
  pin cứng version và có smoke test fail rõ ràng khi shape đổi.
  → Phức tạp: **trung bình** (~80-120 dòng wrapper + heuristic + test). Rủi ro: **trung
  bình** (không đụng render, không đụng nội dung; rủi ro chính là brittleness theo version).
  Fork: **không** (không sửa source babeldoc, không vendor code). Effort: **vừa**.

#### Hướng C — Chấp nhận known limitation, chỉnh lại default của F2

Không viết thêm code. Chỉ dựa vào `Settings.babeldoc_split_short_lines` (đã ship ở F2) và
chọn default cho đúng theo dữ liệu đo được.

Theo P2, trên trang duy nhất đã đo thật, `True` **tốt hơn nghiêm ngặt** so với `False`
(văn xuôi giống hệt nhau; danh sách đúng 28/32 block có marker thay vì 3/7 và không bị dính
chữ). Default hiện tại là `False`.

→ Phức tạp: **rất thấp** (1 dòng + đo thêm). Rủi ro: **thấp nhưng chưa đo đủ**. Effort:
**rất nhỏ**.

### P4. Khuyến nghị

**Bước 1 (làm ngay, rẻ nhất, chặn quyết định sai) — đo lại F1 trên nhiều trang.**
Chạy babeldoc thật ở cả 2 chế độ trên **3-5 trang có bố cục khác nhau** của chính cuốn "How
baking works" (bắt buộc có: 1 trang toàn văn xuôi, 1 trang có bảng nguyên liệu cạnh body
full-width — đúng kịch bản RC-1 dự đoán, 1 trang có công thức đánh số). Với mỗi trang, so
sánh theo **vùng** như bảng P2 (văn xuôi vs danh sách riêng), **không** so tổng số block —
tổng số block là proxy sai, chính nó đã dẫn tới kết luận nhầm ở F1. Đây là điều kiện tiên
quyết: nếu RC-1 không gây hại thật trên trang nào, thì Bước 2 giải quyết xong vấn đề mà
không cần viết code.

**Bước 2 (nhiều khả năng là đủ) — nếu Bước 1 xác nhận, đổi default
`Settings.babeldoc_split_short_lines` về `True`** (`src/core/config.py`), giữ nguyên
`babeldoc_short_line_split_factor` ở `0.5` (thấp hơn default `0.8` của babeldoc — chỉ dòng
thật sự ngắn mới bị tách, giảm mạnh false-positive của RC-1, xem L2/N5-F2). Nếu Bước 1 tìm
ra trang bị RC-1 làm hỏng thật, **không** đổi default; đi tiếp Bước 3.

**Bước 3 (chỉ khi Bước 2 không đủ) — làm Hướng B-2.** Khi đó bật lại
`--split-short-lines` **không còn cần thiết**: B-2 tách numbered list theo ngữ nghĩa, nên có
thể để `split_short_lines=False` (tránh hẳn RC-1) mà vẫn giữ danh sách đúng. Đây là phương
án duy nhất giải quyết triệt để cả RC-1 lẫn RC-2 cùng lúc.

**Không khuyến nghị Hướng A** trong mọi trường hợp: sửa PDF đã render đòi hỏi tái hiện lại
Typesetting của babeldoc mà không có dữ liệu layout, và đụng đúng 2 lớp rủi ro đã có tiền sử
gây sự cố trong project (glyph tiếng Việt hỏng khi vẽ lại bằng font sai; mất nội dung âm
thầm). Chi phí/rủi ro vượt xa lợi ích so với B-2.

### P5. Điều kiện kèm theo nếu chọn Hướng B (bắt buộc, Protocol 5/6)

1. **Pin version**: wrapper phải assert `babeldoc.__version__ == "0.6.4"` và **raise ngay**
   nếu lệch — không "chạy tiếp cho lành". Đổi version babeldoc = verify lại toàn bộ contract
   internal (Protocol 5 mục 5).
2. **Smoke test gọi thật** (R5-03): 1 test chạy wrapper thật trên fixture
   `page14_numbered_list_source.pdf`, assert số block có marker trong output ≥ 25.
3. **Assert nội dung, không assert flag** (bài học N4): không được viết test kiểu
   `assert "--wrapper" in args`. Phải đọc PDF output bằng PyMuPDF và đếm marker.
4. **Kiểm tra không dính chữ**: assert output KHÔNG chứa pattern `\S\d{1,2}\.\s` (chữ dính
   liền marker, dấu hiệu của lỗi gộp hiện tại).
5. Với B-2, cần assert cả **văn xuôi không bị đổi**: so text vùng văn xuôi trước/sau khi bật
   wrapper phải bằng nhau (đúng phương pháp đã dùng ở P2).

**Trạng thái**: Đánh giá — chờ PM/user quyết định. Không có code nào được viết trong task này.

---

## Đo lại F1 trên nhiều trang — kết quả live A/B/C (2026-09-06)

**Tác giả**: Tech Lead — đo lường, KHÔNG implement, KHÔNG sửa default. PM quyết định cuối cùng.
**Bối cảnh**: thực hiện đúng "Bước 1" của section trước (P4). Mục tiêu: xác định tác hại RC-1
có THẬT trên dữ liệu thật hay không, trước khi giữ/đổi `Settings.babeldoc_split_short_lines`.

### Q1. Phương pháp (live, không mock — Protocol 5 R5-03 / Protocol 6 R6-03)

- **Engine**: `babeldoc` 0.6.4 CLI thật, gọi qua chính production code path của app
  (`BabeldocRunner.translate_pages()` + `Pdf2zhServiceMapper().map("deepseek", settings)`),
  không tự dựng lại lệnh CLI bằng tay.
- **LLM**: DeepSeek API thật, model `deepseek-v4-flash` — lấy đúng giá trị đang chạy production
  trong bảng `settings` của `data/bb_translation.db` (KHÔNG phải `deepseek-chat` mặc định trong
  `.env`; `get_settings()` chỉ đọc `.env` nên harness override tường minh).
- **Prompt**: prompt babeldoc thật do `build_babeldoc_prompt_text()` sinh (đã bao gồm bản sửa
  F4), dùng chung 1 file cho toàn bộ 21 lần chạy để loại prompt khỏi biến số.
- **File nguồn**: `data/uploads/898a567a-..._Figoni, Paula - How baking works...-1-25.pdf`.
- **3 nhánh (arm)** cho MỖI trang:
  - `false` — `split_short_lines=False` (F1, default đang ship).
  - `true` — `split_short_lines=True`, `factor=0.5` (F2, giá trị
    `Settings.babeldoc_short_line_split_factor` đang ship).
  - `true08` — `split_short_lines=True`, `factor=0.8` (**default của chính babeldoc**,
    `main.py:184-189` / `translation_config.py:179` — chính là hành vi TRƯỚC F1).
- **Tổng**: 7 trang × 3 nhánh = **21 lần chạy babeldoc + DeepSeek thật**, 0 rate-limit hit,
  0 lần fail.
- **Artifact đã lưu lại** (golden file, không phải mock viết tay):
  `tests/fixtures/babeldoc/ab_split_short_lines/page{N}_{arm}_mono.pdf` (21 PDF) +
  `run_measure.py` (harness đã chạy) + `analyze.py` (script đo). Tái chạy được nguyên trạng.

⚠️ Nhánh `true08` **không có trong đề bài PM giao** (PM chỉ yêu cầu A/B True-vs-False). Bổ sung
vì phát hiện giữa chừng: fixture cũ của F1 dùng factor **0.8**, còn `Settings` sau F2 mặc định
**0.5** — nên "bật lại flag" theo cấu hình hiện tại KHÔNG tái hiện hành vi trước F1. Nếu chỉ đo
A/B như đề bài, kết luận sẽ sai lệch (xem Q3).

### Q2. Chọn trang — 7 trang, 5 loại bố cục

Chọn bằng cách quét thống kê toàn bộ 25 trang (số block, số marker `N.`, số bullet glyph,
median width, số block hẹp < 0.6 × median) rồi lấy đại diện mỗi loại:

| Trang | Loại bố cục | Lý do chọn |
|---|---|---|
| 13 | **Văn xuôi thuần**, 1 cột full-width, không list/bảng | Yêu cầu (a) của PM. Baseline sạch nhất |
| 21 | Có **bảng** (TABLE 1.2) + văn xuôi | Yêu cầu (c) |
| 20 | Văn xuôi + **bảng hẹp + caption** ở cột trái (8 block hẹp — cao nhất tài liệu, median_width bị lệch mạnh nhất) | Yêu cầu (c), đúng kịch bản RC-1 mô tả |
| 22 | **Mix nhiều loại**: văn xuôi 2 cột + bảng + caption ảnh + heading giãn chữ | Yêu cầu (d) |
| 8 | **Mục lục** (72 block nguồn, toàn dòng ngắn) | Yêu cầu (d) |
| 17 | **Mix**: numbered list ngắn (5 mục "CHAPTER OBJECTIVES") + văn xuôi | Yêu cầu (b) + (d) |
| 14 | **Numbered list dài** (35 mục) trong 2 cột hẹp | Yêu cầu (b), trang user báo lỗi |

### Q3. Số liệu thô

Chỉ số dùng (đo bằng PyMuPDF `get_text("blocks")` trên PDF output thật):

- `blk` — số text block; `chars` — tổng ký tự (kiểm tra mất nội dung).
- `glue:N+UP` — số lần **một chữ số dính liền ngay một chữ HOA** trong CÙNG 1 block
  (vd `"CHƯƠNG 6CÁC LOẠI NGŨ CỐC"`). Lỗi nội dung nhìn thấy được.
- `glue:x+N.` — số lần **một chữ cái dính liền ngay marker `N.`** (vd `"khác nhau3. Rây"`).
  Đây chính là triệu chứng gộp danh sách user báo.
- `mkBlk` — số block **bắt đầu bằng** marker `N.` (mục còn đứng đúng dòng riêng).

Cả 2 chỉ số `glue` đếm **trong từng block**, không nối các block lại — nối block sẽ tự tạo ra
đúng cái ranh giới mà chỉ số này dùng để kiểm tra sự VẮNG MẶT (lỗi của lần đo đầu tiên).

| Trang | arm | blk | chars | glue:N+UP | glue:x+N. | mkBlk |
|---|---|---:|---:|---:|---:|---:|
| **13** (văn xuôi thuần) | false | 10 | 4243 | 0 | 0 | 0 |
| | true (0.5) | 10 | 4243 | 0 | 0 | 0 |
| | true08 | 10 | 4243 | 0 | 0 | 0 |
| **21** (bảng) | false | 30 | 2402 | 0 | 0 | 0 |
| | true (0.5) | 30 | 2402 | 0 | 0 | 0 |
| | true08 | 30 | 2402 | 0 | 0 | 0 |
| **20** (bảng hẹp + caption) | false | 19 | 3320 | 0 | 0 | 0 |
| | true (0.5) | 22 | 3310 | 0 | 0 | 0 |
| | true08 | 22 | 3310 | 0 | 0 | 0 |
| **22** (mix) | false | 31 | 3264 | 0 | 0 | 0 |
| | true (0.5) | 32 | 3280 | 0 | 0 | 0 |
| | true08 | 35 | 3255 | 0 | 0 | 0 |
| **8** (mục lục) | false | 15 | 1952 | **7** | 0 | 0 |
| | true (0.5) | 17 | 1937 | **7** | 0 | 0 |
| | true08 | 34 | 1930 | **0** | 0 | 0 |
| **17** (list ngắn + văn xuôi) | false | 8 | 2044 | 0 | 0 | 1/5 |
| | true (0.5) | 9 | 2096 | 0 | 0 | 2/5 |
| | true08 | 11 | 2077 | 0 | 0 | **4/5** |
| **14** (list 35 mục) | false | 11 | 2764 | 0 | **28** | 3/35 |
| | true (0.5) | 20 | 2804 | 0 | **21** | 12/35 |
| | true08 | 34 | 2801 | 0 | **3** | **26/35** |

**Kiểm tra mất nội dung**: `chars` của mọi arm nằm trong ±1.5% so với nhau và so với trang
nguồn. **Không arm nào làm mất nội dung** — khác hẳn lớp lỗi Bug #2/#5 trước đây.

**Kiểm tra "output có giống hệt nhau không"** (so text toàn bộ block sau khi normalize
whitespace):

| Trang | `false` == `true(0.5)` | `false` == `true08` |
|---|---|---|
| 13 | **True** | **True** |
| 21 | **True** | **True** |
| 20 | False | False |
| 22 | False | False |
| 8 | False | False |
| 17 | False | False |
| 14 | False | False |

### Q4. Phân tích từng trang (đọc nội dung thật, không chỉ đếm block)

**Trang 13 — văn xuôi thuần: KHÔNG KHÁC BIỆT.**
(a) văn xuôi: không arm nào tách vụn. (b) không có list/bảng. (c) **Kết luận: không khác biệt** —
output giống hệt nhau từng ký tự ở cả 3 arm. **RC-1 không hề kích hoạt trên trang văn xuôi thuần.**

**Trang 21 — có bảng: KHÔNG KHÁC BIỆT.**
(a) văn xuôi nguyên vẹn ở cả 3 arm. (b) bảng không dính chữ ở arm nào. (c) **Kết luận: không
khác biệt** — giống hệt nhau từng ký tự. Đáng chú ý vì đây là trang có bảng mà RC-1 lẽ ra phải
gây hại.

**Trang 20 — bảng hẹp + caption (kịch bản RC-1 nặng nhất): `false` tốt hơn chút ít.**
(a) văn xuôi: **giống hệt nhau ở cả 3 arm** (5 đoạn body, từng chữ như nhau). (b) khác biệt DUY
NHẤT: caption bảng. `false` giữ nguyên 1 khối
`"BẢNG 1.1 ■ SỰ TƯƠNG ĐƯƠNG GIỮA ĐƠN VỊ THÔNG DỤNG CỦA MỸ (IMPERIAL) VÀ ĐƠN VỊ MÉT"`;
`true`/`true08` cắt thành 4 fragment (`"BẢNG 1.1 ■"` / `"SỰ TƯƠNG ĐƯƠNG GIỮA"` /
`"ĐƠN VỊ THÔNG DỤNG CỦA MỸ (IMPERIAL)"` / `"VÀ ĐƠN VỊ HỆ MÉT"`). Ghép lại vẫn đọc đúng nghĩa,
không dính chữ, không mất nội dung. (c) **Kết luận: `false` tốt hơn, mức độ nhẹ** — đây là bằng
chứng THẬT ĐẦU TIÊN của RC-1, nhưng tác hại giới hạn ở 1 caption và không làm sai nội dung.
`0.5` và `0.8` cho kết quả y hệt nhau ở trang này.

**Trang 22 — mix: KẾT QUẢ TRÁI CHIỀU (cả 2 arm đều có lỗi riêng).**
(a) văn xuôi: không arm nào tách vụn. (b) **`true08` gây hại**: cắt vụn 2 caption, và một trong
số đó mất mạch nghĩa thật sự — caption gốc `"TABLE 1.3 ■ VOLUME CONVERSIONS FOR COMMON U.S.
UNITS"` ra thành 3 fragment dịch rời rạc, lặp ý:
`"BẢNG 1.3 ■ QUY ĐỔI THỂ TÍCH"` / `"CHO CÁC ĐƠN VỊ"` / `"CÁC ĐƠN VỊ THÔNG DỤNG"`. Đây là **tác
hại RC-1 rõ ràng nhất tìm được trong toàn bộ mẫu**. NHƯNG (b') **`false` cũng gây hại riêng**:
heading giãn chữ ra thành `"MẸ O H A Y"` (hỏng, `true08` ra đúng `"MẸO HỮU ÍCH"`), và credit ảnh
bị dính vào caption: `"...siro cây phong, nước và bột mì.Ảnh: Aaron Seyfarth"` (`true08` tách
đúng thành 2). (c) **Kết luận: trái chiều, không arm nào thắng** — mỗi arm hỏng một chỗ khác nhau.

**Trang 8 — mục lục: `true08` tốt hơn RÕ RỆT.**
(a) không có văn xuôi. (b) `false` VÀ `true(0.5)` đều dính chữ **7 lần**, kiểu
`"CHƯƠNG 6CÁC LOẠI NGŨ CỐC"`, `"CHƯƠNG 7GLUTEN 117"`, `"CHƯƠNG 10CHẤT BÉO"` — số chương dính
liền tên chương, lỗi nội dung nhìn thấy ngay. Các mục con cũng bị gộp thành chuỗi dài
(`"Giới thiệu 101 Ngũ cốc 102 Các loại ngũ cốc và bột không chứa gluten 106..."`). `true08`:
**0 lần dính**, mỗi mục mục lục một block (`"Giới thiệu 101"`, `"Ngũ cốc có gluten 102"`), và
`"CHƯƠNG 6"` xuống dòng đúng trước tên chương. (c) **Kết luận: `true08` tốt hơn rõ rệt**; `0.5`
gần như không cải thiện gì so với `false`.

**Trang 17 — numbered list ngắn + văn xuôi: `true08` tốt hơn.**
(a) văn xuôi: cả 3 arm đều giữ nguyên 3 đoạn body, không tách vụn. (b) `false` gộp cả 5 mục
"CHAPTER OBJECTIVES" vào 1 block dính chữ
(`"...cách đạt được điều đó.2. Phân biệt giữa..."`), chỉ 1/5 mục đứng riêng. `true08` tách được
**4/5**, các mục 3/4/5 mỗi mục 1 block sạch. `true(0.5)` chỉ được 2/5. (c) **Kết luận: `true08`
tốt hơn**, không kèm tác hại nào quan sát được trên trang này.

**Trang 14 — numbered list 35 mục: `true08` tốt hơn RẤT RÕ.**
(a) văn xuôi ("LỜI CẢM ƠN", 3 đoạn): **giống hệt nhau ở cả 3 arm** — xác nhận lại kết luận P2 của
section trước bằng một lần chạy độc lập, prompt mới. (b) dính chữ: `false` **28 lần**,
`true(0.5)` **21 lần**, `true08` chỉ **3 lần**. Số mục đứng đúng dòng riêng: 3/35 → 12/35 →
**26/35**. `false` dồn 33 mục vào đúng 2 khối khổng lồ. (c) **Kết luận: `true08` tốt hơn rất rõ.**

### Q5. Tổng hợp

| Trang | Loại | Kết luận |
|---|---|---|
| 13 | văn xuôi thuần | không khác biệt (identical) |
| 21 | bảng | không khác biệt (identical) |
| 20 | bảng hẹp + caption | `false` tốt hơn (nhẹ — 1 caption bị cắt 4) |
| 22 | mix | trái chiều (mỗi arm hỏng 1 chỗ khác nhau) |
| 8 | mục lục | **`true08` tốt hơn rõ rệt** (7 lỗi dính chữ → 0) |
| 17 | list ngắn + văn xuôi | **`true08` tốt hơn** (1/5 → 4/5 mục đúng) |
| 14 | list 35 mục | **`true08` tốt hơn rất rõ** (28 → 3 dính chữ; 3/35 → 26/35) |

**Tổng kết: `true08` thắng rõ 3 trang, trái chiều 1 trang, thua nhẹ 1 trang, hoà 2 trang.**

Ba kết luận quan trọng:

1. **RC-1 CÓ THẬT nhưng hẹp hơn nhiều so với dự đoán từ source.** Phân tích N3/RC-1 dự đoán
   `median_width` toàn trang sẽ làm "mọi dòng của khối hẹp" bị tách, gây hại cho **đoạn văn
   thường**. Đo thật: **không có một đoạn văn xuôi nào trong toàn bộ 7 trang bị tách vụn ở bất kỳ
   arm nào.** Tác hại thật của RC-1 chỉ xuất hiện ở **caption của bảng/ảnh** (trang 20, 22) —
   một loại nội dung ngắn, ít quan trọng hơn nhiều so với body text và list.

2. **`factor` quan trọng hơn cả bản thân flag.** Đây là phát hiện làm thay đổi kết luận:
   `true(0.5)` — chính là cấu hình `Settings` đang ship sau F2 — là **tệ nhất trong ba**: nó giữ
   gần như trọn vẹn lỗi gộp danh sách của `false` (trang 8: vẫn 7 lỗi dính chữ, y hệt `false`;
   trang 14: 21/28 lỗi còn lại) mà **vẫn phải trả đủ giá RC-1** (trang 20 cắt caption y hệt
   `true08`). Nghĩa là nếu PM bật `babeldoc_split_short_lines=True` với default `factor` hiện tại,
   sẽ nhận về **gần như toàn bộ tác hại và rất ít lợi ích**. Hạ factor từ 0.8 xuống 0.5 ở F2 được
   suy luận là "giảm false-positive" nhưng chưa từng đo — đo thật cho thấy nó chủ yếu giảm
   TRUE-positive.

3. **Kết quả KHÔNG mâu thuẫn theo loại trang** theo cách cần setting per-document. Trang văn xuôi
   thuần và trang bảng **hoàn toàn không bị ảnh hưởng** (identical) — tức là bật flag không có
   rủi ro gì với chúng. Chỉ trang có caption ngắn mới chịu thiệt. Vì vậy **không cần** heuristic
   "phát hiện tài liệu nhiều list" hay setting per-file-type: một default duy nhất là đủ, vì chi
   phí của việc bật flag bằng 0 trên đúng những trang mà nó không giúp gì.

### Q6. Khuyến nghị

**Khuyến nghị chính: đổi CẢ HAI default trong `src/core/config.py`:**

- `babeldoc_split_short_lines: bool = False` → **`True`**
- `babeldoc_short_line_split_factor: float = 0.5` → **`0.8`** (bằng đúng default của babeldoc)

Tức là **hoàn nguyên hành vi runtime về trước F1**, nhưng **GIỮ NGUYÊN toàn bộ phần plumbing của
F1/F2** (tham số hoá, `Settings`, data-lineage test) — đó mới là giá trị thật của F1/F2: biến một
flag hardcode không nguồn xác thực thành một tham số đo được, đổi được. Không đề xuất revert code.

Lý do, theo đúng thứ tự sức nặng bằng chứng:

1. Lợi ích **đã đo được** trên 3/7 trang, gồm cả trang user trực tiếp báo lỗi (trang 14), và gồm
   loại lỗi **nhìn thấy được trong bản dịch giao cho user** (dính chữ `"CHƯƠNG 6CÁC LOẠI"`,
   `"khác nhau3. Rây"`).
2. Tác hại **đã đo được** giới hạn ở caption bảng/ảnh trên 2/7 trang, và trên 1 trong 2 trang đó
   (trang 22) arm `false` cũng có lỗi riêng tương đương — nên tác hại ròng thực tế chỉ là **1
   caption trên 7 trang**.
3. Trang văn xuôi thuần và trang bảng: **bật flag không gây bất kỳ thay đổi nào** — rủi ro bằng 0
   trên phần lớn nội dung của một cuốn sách.
4. Giữ `factor=0.5` là lựa chọn tệ nhất trong cả ba (điểm 2 mục Q5) — nếu PM chọn giữ
   `split_short_lines=False`, cũng nên sửa `0.5` về `0.8`, vì giá trị 0.5 hiện tại chỉ có hại khi
   ai đó bật flag lên qua `.env`.

**Không khuyến nghị**: setting per-`file_type` hoặc heuristic tự phát hiện "tài liệu nhiều list".
Dữ liệu không ủng hộ (điểm 3 mục Q5): chi phí bật flag trên trang không có list bằng 0, nên phân
nhánh chỉ thêm phức tạp mà không mua được gì.

**Việc kèm theo nếu PM duyệt** (Dev thực hiện, Protocol 5/6):

1. Sửa 2 default nói trên trong `src/core/config.py`. Cập nhật docstring
   `BabeldocRunner.translate_pages()` — hiện đang viết `--split-short-lines` là "tác hại hình học
   lan rộng hơn toàn bộ trang", câu này **đã bị dữ liệu ở đây bác bỏ** và cần sửa lại theo phạm vi
   thật (chỉ caption).
2. Cập nhật 2 test đang khoá default cũ trong `tests/integration/test_job_orchestrator.py`
   (`test_babeldoc_split_short_lines_defaults_to_disabled`) — đổi tên và đảo assert theo default
   mới. Giữ nguyên test data-lineage (R6-02).
3. Thêm golden-file test đọc **cấu trúc** từ fixture đã lưu
   (`tests/fixtures/babeldoc/ab_split_short_lines/`), tối thiểu 3 assert:
   `page8_true08` có `glue:N+UP == 0` (arm `false` là 7); `page14_true08` có ≥ 24 block bắt đầu
   bằng marker (arm `false` là 3); `page13` giống hệt nhau ở cả 3 arm. **Không** assert sự có mặt
   của flag trong `args` — đó đúng là lỗi N4 đã mắc một lần.
4. Ghi **known limitation** vào CHANGELOG: caption bảng/ảnh có thể bị cắt thành nhiều fragment
   (trang 20, 22). Đây là giá đã biết và đã chấp nhận có ý thức, không phải bug chưa phát hiện.

**Hướng B-2 (section trước) vẫn là fix triệt để duy nhất** và bây giờ có thêm lý do: nó tách
numbered list theo **ngữ nghĩa**, nên cho phép đặt `split_short_lines=False` mà vẫn giữ list
đúng — tức là loại bỏ hoàn toàn cái giá "caption bị cắt" mà khuyến nghị trên đang phải trả. Nhưng
khuyến nghị trên rẻ hơn nhiều (2 dòng config) và đã đủ để xử lý triệu chứng user báo, nên nên làm
trước; B-2 chỉ cần khi caption bị cắt trở thành phàn nàn thật từ user.

**Trạng thái**: Đo lường xong — chờ PM/user quyết định. Không sửa code, không đổi default.

---

## US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — thiết kế (2026-09-06)

Thiết kế cho US-16 / BR-IMGCOMP-01..04 (`docs/PRD.md` §3, §4.9). Trạng thái: **đã spike đo
thật trên dữ liệu production, không có phần nào `[UNVERIFIED]`** — mọi contract PyMuPDF dưới
đây đều đã chạy thật trong `.venv` của project và có output kèm theo.

### S1. Nguồn xác thực (Protocol 5 R5-01 — áp dụng tự nguyện)

PyMuPDF là thư viện Python import trực tiếp (không phải subprocess/HTTP service) nên **không
thuộc phạm vi bắt buộc** của Protocol 5 (xem "Phạm vi áp dụng" trong `CLAUDE.md` project).
Tuy nhiên toàn bộ contract dưới đây vẫn được verify bằng cách chạy thật, không viết từ trí nhớ.

**Version đã cài** (lệnh: `.venv/bin/python -c "import fitz; print(fitz.VersionBind, fitz.version)"`):

```
PyMuPDF 1.28.2: Python bindings for the MuPDF 1.28.2 library.
Python 3.14 running on darwin (64-bit).
VersionBind 1.28.2
version ('1.28.2', '1.28.2', None)
```

⚠️ **Deprecation warning đã quan sát thấy**: `import fitz` in ra
`"The fitz API is deprecated and will be removed in future. Use import pymupdf instead."`
`src/postprocess/chunk_merge.py:54` hiện đang dùng `import fitz`. **Không đổi trong scope
US-16** (ngoài phạm vi, sẽ gây diff nhiễu); hàm mới bám theo import sẵn có của file.

**Signature đã verify bằng `inspect.signature`** (không có cái nào là suy đoán):

| API | Signature thật (1.28.2) | Ghi chú |
|---|---|---|
| `Document.get_page_images` | `(self, pno: int, full: bool = False) -> list` | `full=True` mới có trường filter |
| `Document.xref_get_key` | `(self, xref, key)` | trả tuple `(type, value)`, ví dụ `('null','null')` / `('name','/DCTDecode')` |
| `Document.xref_stream_raw` | `(self, xref)` | bytes stream **chưa** giải nén — dùng để đo size thật |
| `Document.update_stream` | `(self, xref=0, stream=None, new=1, compress=1)` | **phải truyền `compress=0`** khi ghi JPEG |
| `Document.xref_set_key` | `(self, xref, key, value)` | sửa `/Filter`, `/ColorSpace`... |
| `Pixmap.tobytes` | `(self, output='png', jpg_quality=95)` | **`jpg_quality` là tên tham số đúng**, không phải `quality` |
| `Page.replace_image` | `(page, xref, *, filename=None, pixmap=None, stream=None)` | tồn tại, nhưng **KHÔNG dùng** — xem S4 |
| `Document.extract_image` | `(self, xref)` | tồn tại, **KHÔNG dùng** — xem S4 |

**Tuple của `get_page_images(pno, full=True)`** — đã verify thứ tự thật trên dữ liệu production:

```
(12, 0, 859, 1582, 8, 'ICCBased', '', 'Im1', '', 0)
 ^   ^   ^    ^     ^   ^          ^    ^     ^   ^
 |   |   w    h    bpc  colorspace alt  name  |   referencer
 |   smask xref (0 = khong co)                filter (chuoi rong = raw)
 xref
```

⚠️ **Cạm bẫy đã thực sự mắc phải trong lúc spike**: index `1` là `smask`, index `8` là
`filter` — dễ nhầm lẫn nhau. Lần đo đầu tiên của spike này dùng nhầm `info[8]` làm smask và
báo "0 ảnh có smask" từ một trường hoàn toàn khác. Đã đo lại bằng index đúng (`info[1]`) và
kết quả tình cờ vẫn là 0, nhưng **Dev không được tin vào sự trùng hợp đó** — dùng đúng index.

**Đã verify `info[8]` và `xref_get_key(xref,"Filter")` cho kết quả nhất quán 100%** trên cả
538 image xref của file thật (`agree: 538, disagree: 0`). Dev dùng cách nào cũng được;
thiết kế dưới đây dùng `xref_get_key` cho khớp cách diễn đạt của BR-IMGCOMP-02 (`Filter: null`).

### S2. Vấn đề đo được trên dữ liệu thật

Đo trên chính file đã sinh ra US-16 — `data/outputs/3594a7a3-8b72-4390-9d9b-159769a2a215/translated_vi.pdf`
(job thật 415 trang, engine `babeldoc`, `status=completed`):

| Chỉ số | Giá trị đo |
|---|---|
| Kích thước file | **846.79 MB** |
| Số trang | 415 |
| Unique image xref | 538 |
| `Filter: null` (raw) | **357 xref — 690.96 MB** stream bytes |
| `DCTDecode` (JPEG sẵn) | 156 xref — 1.60 MB |
| `CCITTFaxDecode` | 25 xref — 0.04 MB |
| Phần còn lại (font, content stream, metadata) | ~155.82 MB |

=> **81.6% dung lượng file** nằm ở 357 ảnh raw không nén. Đúng như PRD mô tả.

Đặc điểm của 357 ảnh raw (đã đo, quan trọng cho S4): **tất cả** đều `ColorSpace: ICCBased`,
`BitsPerComponent: 8`, **0 ảnh có `/SMask`**, **0 ảnh là `/ImageMask`**. Tức là trên dữ liệu
thật hiện có, các edge case nguy hiểm nhất **không xuất hiện** — nhưng thiết kế vẫn phải guard
chúng (S4/S6), vì file khác có thể có.

### S3. Kết quả spike dedupe — **KHÔNG đạt ngưỡng, LOẠI khỏi scope** (BR-IMGCOMP-04)

Phương pháp: SHA-256 trên nội dung stream thật của từng xref, gom nhóm theo hash, tính phần
dung lượng thừa (`size × (số bản sao − 1)`). Đo trên chính file production 846.79 MB ở trên —
**không phải fixture, không phải ước lượng**.

**Đo 1 — dedupe trong nhóm ảnh raw (nhóm mà US-16 thực sự nén):**

```
raw-content dup groups: 0    redundant xrefs: 0    wasted bytes: 0.0 MB / 690.96 MB
```

**0 nhóm trùng.** Đáng chú ý: có những cặp xref *trông như* trùng (ví dụ xref 12 và 58: cùng
`859×1582`, cùng đúng 5,435,752 bytes) nhưng hash khác nhau (`64fddbc4…` vs `80593ef4…`) —
tức là babeldoc render lại ảnh cho từng trang, gần giống nhau về thị giác nhưng **không
byte-identical**. Đây chính là lý do không được suy đoán: nhìn bảng size/dims sẽ kết luận
ngược hoàn toàn với kết quả hash.

**Đo 2 — dedupe trên TOÀN BỘ 538 ảnh (kể cả DCTDecode/CCITT, rộng hơn cách diễn đạt của BR):**

```
ALL images: 538   unique: 460   dup groups: 19   redundant xrefs: 78
total img bytes 692.60 MB, exact-dup waste 0.349 MB (0.05%)
```

Có trùng lặp thật (78 xref thừa), nhưng **chỉ nằm ở nhóm ảnh vốn đã nhỏ** (icon/logo lặp lại
qua các chương), tổng cộng 0.349 MB.

**So với ngưỡng 20% của BR-IMGCOMP-04** — "giảm THÊM ≥20% so với chỉ nén JPEG", nên mẫu số
phải là dung lượng ảnh **sau khi** đã nén JPEG (6.64 MB raw-đã-nén + 1.64 MB DCT/CCITT giữ
nguyên = 8.28 MB):

| Phép so | Kết quả |
|---|---|
| Dedupe / tổng ảnh gốc | 0.349 / 692.60 = **0.05%** |
| Dedupe / ảnh sau nén JPEG (mẫu số đúng theo BR) | 0.349 / 8.28 = **4.2%** |
| Ngưỡng yêu cầu | ≥ 20% |
| Trên tổng file sau nén (19.34 MB) | 0.349 / 19.34 = **1.8%** |

=> **4.2% < 20% → KHÔNG đạt ngưỡng.**

**QUYẾT ĐỊNH: dedupe KHÔNG vào scope implement lần này.** Defer về backlog kèm số liệu trên.
Dev **không** implement dedupe. Acceptance criterion điều kiện cuối cùng của US-16 ("Nếu spike
dedupe đạt ngưỡng ≥ 20%…") **không kích hoạt**.

Giới hạn của kết luận (nêu rõ, không giấu): đo trên **1 job thật duy nhất** (415 trang, sách
`How Baking Works`). Đây là job lớn nhất và chính là case đã gây ra US-16, nên đại diện tốt
cho vấn đề cần giải; nhưng nếu sau này gặp tài liệu dạng catalogue lặp ảnh nhiều, con số có
thể khác — lúc đó **đo lại**, không kế thừa kết luận này. Các fixture nhỏ trong
`tests/fixtures/babeldoc/` đã được khảo sát và **không đủ đại diện** (chunk0 chỉ có 5 ảnh,
chunk1 và `page14_*` chỉ có 1 ảnh) — đó là lý do spike dùng thẳng file production.

### S4. Vì sao KHÔNG dùng `extract_image()` / `replace_image()`

Cả hai API đều tồn tại thật trong 1.28.2 (S1), nhưng thiết kế **cố ý không dùng**:

- `Page.replace_image()` cần đối tượng `Page`, buộc phải theo dõi xref ↔ page và sẽ xử lý lặp
  với ảnh dùng ở nhiều trang. Đi thẳng qua xref ở cấp `Document` đơn giản và ít trạng thái hơn.
- `Document.extract_image()` trả về dict đã **giải mã sang một format ảnh** (`image` bytes +
  `ext`). Muốn re-encode sang JPEG từ đó thì cần một thư viện ảnh (Pillow) để decode lại.
  **Pillow KHÔNG có trong `.venv`** (đã kiểm tra: `ModuleNotFoundError: No module named 'PIL'`).

=> **Dùng `pymupdf.Pixmap(doc, xref)` + `Pixmap.tobytes("jpeg", jpg_quality=85)`** — PyMuPDF
tự encode JPEG, **không cần thêm dependency nào**. Đã verify chạy thật (S6).

### S5. Vị trí gắn code, signature, data lineage (Protocol 6 — R6-01)

**File**: `src/postprocess/image_compress.py` (module mới, cạnh `chunk_merge.py`).
Không nhét vào `chunk_merge.py`: `merge_chunk_pdfs()` là code đã 2 lần dính bug trang
(Bug #7, Bug #8) và đang có test golden bám sát; nén ảnh là mối quan tâm tách biệt, gộp vào sẽ
làm bề mặt hồi quy của hàm ghép rộng ra vô cớ.

**Signature** (async cho đồng nhất với `merge_chunk_pdfs`, dù thân hàm là CPU-bound thuần):

```python
async def compress_pdf_images(pdf_path: str | Path, *, jpeg_quality: int = 85) -> ImageCompressStats
```

`jpeg_quality` là **keyword-only, mặc định 85, KHÔNG đọc từ `Settings`/`.env`/UI**
(BR-IMGCOMP-03). Tham số tồn tại chỉ để test tham số hoá được, không phải điểm cấu hình.

`ImageCompressStats` — dataclass thuần để log/test, không ghi DB, không lên UI:
`images_scanned: int`, `images_recompressed: int`, `images_skipped_already_compressed: int`,
`images_skipped_larger: int`, `images_skipped_unsupported: int`,
`size_before: int`, `size_after: int`.

**Data lineage — tường minh (R6-01), đây là phần bắt buộc đọc kỹ:**

| | |
|---|---|
| **Artifact vào** | `merged_path` — chính biến `merged_path` mà `run_job()` tạo ở Step 8 (`src/core/job_orchestrator.py:477`) và truyền cho `merge_chunk_pdfs(chunks, merged_path)` (`:479`). **KHÔNG** phải `job.file_path`, **KHÔNG** phải `chunk.output_path`. |
| **Artifact ra** | **Ghi đè in-place chính `merged_path`** — không tạo file mới, không đổi tên. Lý do: `job.output_path = str(merged_path)` ở `:508`, và `create_bilingual_pdf(merged_path, …)` ở Step 9 đều đang trỏ vào đúng path này. Sinh file mới sẽ tạo ra đúng loại lỗ hổng Bug #5 (bước sau vẫn dùng file cũ chưa nén, "thành công" nhưng sai artifact). |
| **Ai gọi** | `JobOrchestrator.run_job()`, **trong cùng khối `try` của Step 8**, **sau** `merge_chunk_pdfs(...)` và **sau** guard rỗng-chữ BR-OCR-03, **trước** `job.output_path = str(merged_path)` (`:508`). |
| **Điều kiện gọi** | `if self._settings.pdf_translate_engine == "babeldoc":` (BR-IMGCOMP-01, `src/core/config.py:135`). Nhánh `pdf2zh` **không gọi**, không đổi một dòng hành vi nào. |

**Thứ tự bắt buộc — đặt SAU guard BR-OCR-03, không phải trước.** Guard đó (`job_orchestrator.py:481-491`)
đọc `page.get_text()` để bắt job dịch ra file rỗng chữ. Nếu nén chạy trước guard, một lỗi trong
bước nén sẽ làm job `failed` với thông báo "bản dịch không chứa chữ nào" — chẩn đoán sai hoàn
toàn nguyên nhân. Nén sau guard thì lỗi nén báo đúng là lỗi nén.

**Ghi đè in-place: PyMuPDF KHÔNG cho save đè file đang mở.** Đã verify bằng cách chạy thật:

```
ValueError: save to original must be incremental
```

=> Dev **phải** ghi ra file tạm cùng thư mục rồi `os.replace()`:
`doc.save(tmp, garbage=4, deflate=True)` → `doc.close()` → `os.replace(tmp, pdf_path)`.
`os.replace` là atomic trong cùng filesystem — nếu tiến trình chết giữa chừng, `merged_path`
vẫn là bản chưa nén hợp lệ, không bao giờ là file cụt.

### S6. Thuật toán (spec cho Dev — KHÔNG phải code để copy)

1. Mở `pdf_path`. Ghi lại `size_before`.
2. Duyệt `for pno in range(doc.page_count)` → `doc.get_page_images(pno, full=True)`.
   Gom **xref duy nhất** vào một `set` trước — ảnh dùng ở nhiều trang chỉ được xử lý **một lần**
   (trong file thật có xref xuất hiện tới 10 lần; nén lại nhiều lần vừa lãng phí vừa gây
   generation loss chồng nhau).
3. Với mỗi xref, **bỏ qua** nếu `doc.xref_get_key(xref, "Filter")[0] != "null"` — tức mọi ảnh đã
   có filter (`DCTDecode`, `CCITTFaxDecode`, `JPXDecode`, `FlateDecode`, `JBIG2Decode`…) đều giữ
   nguyên. Đây chính là BR-IMGCOMP-02 "không nén chồng JPEG".
4. **Guard các trường hợp không được đụng vào** (chưa xuất hiện trong dữ liệu hiện có, nhưng
   bắt buộc phải có — đếm vào `images_skipped_unsupported`):
   - `doc.xref_get_key(xref, "ImageMask")[1] == "true"` → **bỏ qua**. Stencil mask là ảnh 1-bit
     dùng làm khuôn tô màu; biến thành JPEG 8-bit sẽ hỏng cách vẽ.
   - `info[1] != 0` (có `/SMask`, tức có kênh alpha) → **bỏ qua**. JPEG không mang được alpha.
     Có thể xử lý bằng cách tách alpha ra giữ riêng, nhưng đó là độ phức tạp không có dữ liệu
     nào hiện tại biện minh (đo được: 0/357 ảnh có SMask).
5. Tạo `pix = pymupdf.Pixmap(doc, xref)`. Nếu `pix.alpha` → `pix = pymupdf.Pixmap(pix, 0)`
   (bỏ kênh alpha) — lưới an toàn thứ hai cho bước 4.
6. `jb = pix.tobytes("jpeg", jpg_quality=jpeg_quality)`.
7. **Guard nở file**: nếu `len(jb) >= len(doc.xref_stream_raw(xref))` → **bỏ qua**, đếm vào
   `images_skipped_larger`. Ảnh rất nhỏ hoặc nhiễu cao có thể to ra sau khi encode JPEG.
8. Ghi đè:
   - `doc.update_stream(xref, jb, new=1, compress=0)` — **`compress=0` là bắt buộc**: JPEG đã nén
     rồi, để `compress=1` (mặc định!) sẽ bọc thêm một lớp Flate vô ích lên trên.
   - `doc.xref_set_key(xref, "Filter", "/DCTDecode")`
   - `doc.xref_set_key(xref, "BitsPerComponent", "8")`
   - `doc.xref_set_key(xref, "ColorSpace", …)` theo `pix.n`: `4 → /DeviceCMYK`,
     `3 → /DeviceRGB`, còn lại `→ /DeviceGray`.
   - `doc.xref_set_key(xref, "Width", str(pix.width))`, `"Height", str(pix.height)`.

   ⚠️ Ghi `/ColorSpace` là **bắt buộc, không được bỏ**: 357/357 ảnh thật đang là `ICCBased`.
   Stream mới là JPEG thường, ICC profile cũ không còn khớp — để nguyên key cũ thì màu sai.
9. `doc.save(tmp, garbage=4, deflate=True)` → `close()` → `os.replace(tmp, pdf_path)` (S5).

**Về `/DeviceCMYK` và hiện tượng đảo màu**: `Pixmap.tobytes("jpeg")` trên ảnh CMYK sinh JPEG có
marker Adobe APP14 (đã quan sát: byte đầu `ff d8 ff ee`), thường đi kèm quy ước CMYK **đảo**.
Đây là rủi ro thật và đã được **kiểm chứng bằng pixel**, không chỉ bằng "file mở được" — xem S7.

**Xử lý lỗi**: bọc phần xử lý **từng xref** trong `try/except` — một ảnh dị dạng chỉ nên bị bỏ
qua (log `warning`, tăng `images_skipped_unsupported`), **không được làm hỏng cả job** ở bước
gần cuối pipeline khi tiền dịch đã tiêu. Ngược lại, lỗi ở bước `save`/`os.replace` **phải** raise
lên — lúc đó file đích không còn tin được nữa.

### S7. Kết quả verify chạy thật — end-to-end trên file production 846.79 MB

Không phải mock, không phải ước lượng: chạy đúng thuật toán S6 trên bản copy của file thật.

| Chỉ số | Trước | Sau |
|---|---|---|
| Kích thước | 846.79 MB | **19.34 MB (−97.7%)** |
| Số trang | 415 | **415** |
| Tổng ký tự text | 1,160,121 | **1,160,121 — giống hệt từng trang** |
| Ảnh re-encode | — | 357/357 raw, 0 lỗi, 0 bị guard nở file |
| Render toàn bộ trang | — | **all pages render OK** |
| Thời gian chạy | — | **~30 giây** (415 trang) |

**Kiểm chứng thị giác bằng pixel** (chống đúng cái bẫy "tin vào status" của Bug #5 / R6-03):
render trước-sau ở 25 trang mẫu và so sánh từng pixel.

```
worst pages by mean abs pixel diff: [(0.08, 0), (0.02, 68), (0.02, 102), (0.02, 51), ...]
mean over sampled pages: 0.009  / 255
```

Sai khác trung bình **0.009/255** — mất mát thị giác không đáng kể. Trang bìa (trang 0, chứa
ảnh CMYK 5.4 MB) đã được render ra PNG và **xem tận mắt**: màu đúng, **không bị đảo màu CMYK**.

Chạy thêm trên fixture nhỏ `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf`:
7.42 MB → 0.61 MB (−91.8%), 5/5 trang, text giống hệt, 1 ảnh raw 5,435,752 → 52,245 bytes.

### S8. Phát hiện phụ — `merge_chunk_pdfs()` đang save KHÔNG nén (cần PM quyết định)

Đo tách riêng hai tác nhân, phát hiện ngoài dự kiến ban đầu:

| Xử lý | Kích thước |
|---|---|
| Hiện tại | 846.79 MB |
| **Chỉ** `save(garbage=4, deflate=True)`, không đụng gì tới ảnh | **44.93 MB (−94.7%)** |
| Thêm re-encode JPEG q85 (thiết kế S6 đầy đủ) | **19.34 MB (−97.7%)** |

Nguyên nhân: `chunk_merge.py:131` đang gọi `output_doc.save(output_path)` **trần** — mặc định
của PyMuPDF là `deflate=False`, `garbage=0`, nên mọi stream (kể cả bitmap thô 691 MB) được ghi
ra **hoàn toàn không nén**. Phần lớn con số 846 MB đến từ đây chứ không riêng từ việc ảnh chưa
phải JPEG.

Nghĩa là: **phần lớn thắng lợi (−94.7%) đến từ một sửa đổi một dòng**, và JPEG re-encode đóng
góp thêm 57% trên phần còn lại (44.93 → 19.34 MB). Cả hai đều đáng làm; thiết kế S6 đã bao gồm
`garbage=4, deflate=True` trong bước save của nó, nên **job `babeldoc` hưởng cả hai mà không
cần đụng vào `chunk_merge.py`**.

**Điểm cần PM/user quyết định** — job dùng engine `pdf2zh` hiện cũng đang chịu đúng vấn đề save
không nén này, nhưng BR-IMGCOMP-01 nói rõ "job dùng `pdf2zh` không đổi hành vi". Hai lựa chọn:

- **(A) Giữ nguyên scope PRD** (khuyến nghị mặc định): chỉ nhánh `babeldoc` được nén; không đụng
  `chunk_merge.py`. Rủi ro hồi quy bằng 0 với đường `pdf2zh` và với các test golden Bug #7/#8.
- **(B) Mở rộng nhẹ**: đổi `chunk_merge.py:131` thành `save(output_path, garbage=4, deflate=True)`
  cho **cả hai** engine. Job `pdf2zh` cũng nhỏ đi rõ rệt, nhưng đây là thay đổi hành vi nằm
  ngoài US-16, chạm vào file đã 2 lần dính bug — cần user duyệt như một thay đổi có chủ đích,
  và cần chạy lại toàn bộ test golden của `chunk_merge`.

Tech Lead **không tự quyết** cái này vì nó mâu thuẫn trực tiếp với một business rule đã chốt.
Mặc định giao Dev là **(A)**, trừ khi PM/user chọn (B).

### S9. Yêu cầu test kèm implementation (Protocol 6 R6-02 + R6-03)

1. **Test data lineage (R6-02) — không chấp nhận `assert_awaited()` trần.** Phải khẳng định
   được giá trị cụ thể đi giữa hai bước:

   ```
   compress_pdf_images.assert_called_with(merged_path, ...)   # đúng cái merge vừa ghi ra
   ```

   với `merged_path` là chính path đã truyền cho `merge_chunk_pdfs` trong cùng test — đây đúng
   là dạng ràng buộc mà Bug #5 đã thiếu. Test riêng cho nhánh `pdf2zh`: khẳng định
   `compress_pdf_images` **không** được gọi (BR-IMGCOMP-01).
2. **Test thứ tự**: khẳng định nén chạy **sau** guard BR-OCR-03 — một job có output rỗng chữ
   phải `failed` với thông báo của guard, không phải thông báo lỗi nén.
3. **Test nội dung, không chỉ status (R6-03)**: chạy `compress_pdf_images` thật trên fixture
   `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf` (đã có sẵn, 5 trang, 1 ảnh raw
   5.4 MB) và khẳng định: `page_count` không đổi (5), **text từng trang giống hệt trước/sau**,
   file sau nhỏ hơn, và **mọi image xref đều có `Filter != null`** sau khi chạy. Đây là test
   bắt được đúng lớp lỗi mà "job status = completed" không bao giờ bắt được.
4. **Test guard**: ảnh `DCTDecode` sẵn có phải giữ **nguyên byte** stream sau khi chạy (chống
   nén chồng — dùng luôn 3 ảnh DCTDecode có sẵn trong chính fixture đó).
5. **Không cần golden file mới**: các fixture cần thiết đã tồn tại và đã có xuất xứ ghi trong
   `tests/fixtures/babeldoc/README.md`.

### S10. Trạng thái verify

| Hạng mục | Trạng thái |
|---|---|
| Version + signature PyMuPDF | ✅ Verified — chạy thật, output ở S1 |
| Thứ tự tuple `get_page_images(full=True)` | ✅ Verified trên 538 xref thật |
| Đọc `Filter`, phát hiện ảnh raw | ✅ Verified — khớp 538/538 qua 2 cách độc lập |
| Encode JPEG q85 không cần Pillow | ✅ Verified |
| Ghi đè stream + đổi `/Filter`,`/ColorSpace` | ✅ Verified end-to-end, 357 ảnh |
| Bảo toàn text/số trang | ✅ Verified — 1,160,121 ký tự giống hệt, 415/415 trang |
| Bảo toàn màu (CMYK không đảo) | ✅ Verified bằng pixel-diff + xem ảnh render thật |
| Không save đè được file đang mở | ✅ Verified — `ValueError` thật ở S5 |
| Số liệu dedupe | ✅ Verified trên job production, **không đạt 20% → loại khỏi scope** |
| Hành vi với ảnh có `/SMask` hoặc `/ImageMask` | ⚠️ **`[UNVERIFIED]`** — không có mẫu nào trong dữ liệu hiện có (0/357). Thiết kế **bỏ qua** các ảnh này (S6 bước 4), tức nhánh code an toàn theo mặc định; nhưng chính đường `skip` đó chưa từng chạy trên dữ liệu thật. Không chặn Dev implement (hành vi mong đợi là "không làm gì"). |
| Lựa chọn (A)/(B) ở S8 | ⏸ **Chờ PM/user quyết định** — không chặn phần còn lại của US-16 |


---

## Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order trên trang layout phức tạp (2026-09-07)

**Tác giả**: Tech Lead — phân tích/research, KHÔNG implement.
**Đầu vào**: `docs/ux-review-report.md` (UX-A…UX-E, 21 ảnh trang PDF đã dịch).
**Trạng thái**: ⏸ **Chưa phải kết luận cuối** — PM sẽ mời Domain Expert phản biện trước khi chốt.

### T1. Kết luận ngắn

Năm nhóm hiện tượng UX báo cáo **KHÔNG có chung một nguyên nhân**. Có ít nhất **3 lỗi độc
lập**:

| Nhóm UX | Root cause | Nằm ở đâu | Mức verify |
|---------|-----------|-----------|-----------|
| UX-A (overlap 2 block), UX-B (vỡ box), UX-E (font không đều) | **Cùng 1 nguyên nhân**: babeldoc typeset mỗi paragraph ĐỘC LẬP, neo tuyệt đối vào bbox GỐC của chính nó, không reflow theo chiều cao thực tế của paragraph trước; khi text dịch tràn đáy box thì **vẫn vẽ tiếp ra ngoài box** thay vì dừng | babeldoc `typesetting.py` | ✅ Verified (source + đo trên output thật) |
| UX-C (mất nội dung → ô trắng) | **Lỗi KHÁC HẲN**: mọi glyph có góc xoay ≠ 0°/90° (±0.1°) bị **loại bỏ khỏi IL ngay bước parse** → không dịch, không vẽ lại, mà text gốc thì đã bị xoá | babeldoc `il_creater.py:968-978` | ✅ Verified (source + tái hiện live 1 trang) |
| UX-D (sai thứ tự đọc) | **Chưa xác định** — chạy lại đúng trang mục lục đó ở chế độ 1-trang-độc-lập thì render ĐÚNG, không tái hiện được | phụ thuộc ngữ cảnh nhiều trang / chunk | ⚠️ `[UNVERIFIED]` |

Giả thuyết chính của UX ("tiếng Việt dài hơn, khung không giãn, sai lệch cộng dồn") **đúng
cho UX-A/B/E** và **sai cho UX-C** — UX-C không liên quan gì tới độ dài text.
Giả thuyết phụ của UX ("xoá text gốc xong nhưng vẽ text mới thất bại") **đúng về hiện tượng,
sai về cơ chế**: không có bước "vẽ thất bại", mà là **chưa bao giờ có gì để vẽ** vì ký tự đã
bị vứt từ bước đọc PDF.

### T2. Nguồn xác thực (Protocol 5 / R5-01)

babeldoc **0.6.4** đã cài (`babeldoc --version` → `babeldoc 0.6.4`), source tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`.
Prefix `format/pdf/document_il/` viết tắt là `IL/`.

| # | Claim | Nguồn (file:line) |
|---|-------|-------------------|
| T-01 | `on_lt_char()` **return sớm** (bỏ hẳn ký tự) nếu góc xoay của text matrix không nằm trong `-0.1..0.1` hoặc `89.9..90.1` độ | `IL/frontend/il_creater.py:968-974` |
| T-02 | Góc xoay tính bằng `atan2(b, a)` từ matrix ký tự | `il_creater.py:390-397` |
| T-03 | Mỗi paragraph được typeset bắt đầu từ **đỉnh bbox của CHÍNH NÓ** (`current_y = box.y2 - avg_height`, `current_x = box.x`) — không có tham số nào mang chiều cao thực tế của paragraph trước vào | `IL/midend/typesetting.py:1349-1350` |
| T-04 | Khi xuống dòng vượt đáy box: chỉ set cờ `all_units_fit = False`, **comment ghi rõ "这里不要 break，继续排版剩余内容"** (đừng break, tiếp tục xếp phần còn lại) → text tràn được **vẽ ra ngoài box**, đè lên block dưới | `typesetting.py:1440-1444` |
| T-05 | Vòng thu nhỏ font: `scale` giảm 0.05 (khi >0.6) rồi 0.1, tới `min_scale = 0.1` | `typesetting.py:967-1015` |
| T-06 | **Giãn khung chỉ được thử khi `scale < 0.7`**, và chỉ 2 lần: giãn xuống (`get_max_bottom_space`) rồi giãn phải (`get_max_right_space`); giãn thất bại (không còn chỗ trống) → reset `scale = 1.0` và tiếp tục thu nhỏ | `typesetting.py:1017-1062` |
| T-07 | `preprocess_document()` gom `optimal_scale` của **mọi paragraph trong CẢ tài liệu**, lấy **mode**, rồi ép mọi paragraph có scale > mode **xuống bằng mode** | `typesetting.py:919-935` |
| T-08 | Trước khi render, có bước chống chồng lấn nhưng nó chỉ **cắt ngắn box trên từ phía dưới** (`p_upper.box.y = new_y`), **không đẩy block dưới xuống** — tức làm box trên NHỎ đi (dễ tràn hơn), không tạo thêm chỗ | `typesetting.py:1172-1211` |
| T-09 | `render_paragraph()` gán `pdf_paragraph_composition = []` TRƯỚC khi gọi retypeset; nếu retypeset không apply được thì composition ở lại rỗng | `typesetting.py:1277-1280` |
| T-10 | Paragraph có composition rỗng → `render_paragraph_to_char()` trả list rỗng, log `ERROR "Unable to export paragraphs that have not yet been formatted"` | `IL/backend/pdf_creater.py:831-836` |
| T-11 | `debug_id` được sinh **luôn luôn** (`generate_base58_id()`), không phụ thuộc `--debug` → guard `typesetting.py:1008` thực tế không chặn vòng thu nhỏ | `IL/midend/paragraph_finder.py:500, 874, 911` |
| T-12 | `--translate-table-text` mặc định **False**; bật lên mới nạp `RapidOCRModel` cho table detection | `main.py:238-242, 586-591` |
| T-13 | `--max-pages-per-part` **không set thì không split** → 1 lần gọi babeldoc = 1 "document" cho T-07 | `main.py:222-225`; `format/pdf/split_manager.py:27-40` |
| T-14 | `--ocr-workaround` (vẽ nền trắng dưới text) mặc định False; `BabeldocRunner` **không** truyền flag này → ô trắng quan sát được **không phải** do rectangle nền trắng | `main.py:256`; `pdf_creater.py:882-887`; `src/services/babeldoc_runner.py:280-311` |

### T3. Bằng chứng sống (Protocol 6 / R6-03) — đo trên output production thật

**Dữ liệu**: job `136645f9-ffe8-4927-afb2-b725236ede44` (Le Cordon Bleu Pâtisserie and Baking
Foundations, 418 trang, `pdf_digital`, status `completed`).
Nguồn: `data/uploads/f88282bb-…_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf`;
output: `data/outputs/136645f9-…/translated_vi.pdf`. Đo bằng PyMuPDF `get_text("blocks")` /
`get_text("dict")`.

**(a) Chồng lấn text tăng vọt sau khi dịch** — đếm cặp block có diện tích giao > 5% diện tích
block nhỏ hơn (đúng ngưỡng DoD-UX-01):

| Trang | Cặp chồng lấn ở BẢN GỐC | Cặp chồng lấn ở BẢN DỊCH | Tỉ lệ giao lớn nhất |
|-------|------------------------|--------------------------|---------------------|
| 6 (mục lục) | 3 | 8 | 0.95 |
| 12 | 7 | 18 | 1.00 |
| 13 | 28 | 62 | 1.00 |
| 26 | 3 | 9 | 1.00 |
| 21, 27, 39 | 0 | 5 mỗi trang | 0.90 |

→ DoD-UX-01 **FAIL** rõ rệt; trang văn xuôi thường (21, 27, 39) vốn 0 cặp chồng ở bản gốc
cũng thành 5 cặp. Khớp nhận định UX-A "xảy ra trên văn xuôi bình thường".

**(b) Tổng ký tự bản dịch THẤP HƠN bản gốc**: 520.855 / 573.211 = **0,909**. Tiếng Việt lẽ ra
phải **dài hơn** ~20–40% → thiếu hụt thực tế lớn hơn con số 9% này nhiều.

**(c) Ký tự bị xoay trong bản gốc** (`line["dir"]` ≠ 0°/90°, đúng ngưỡng T-01): **7.832 ký tự
trên 19/418 trang** (1,17% toàn sách). Danh sách trang: 11, 12, 13, 14, 25, 26, 66, 69, 73,
75, 80, 83, 86, 158, 159, 160, 171, 229, 268.

**(d) Tái hiện live UX-C** — trích trang 67 (0-index 66) ra file 1 trang, chạy babeldoc THẬT
(deepseek-chat, đúng bộ flag production + `--debug`): khối chú giải nghiêng "Disaccharide — The
word disaccharide is composed of…" (16 dòng, `dir = (0.982, -0.191)` ≈ **-11°**) **biến mất
hoàn toàn** khỏi output ở CẢ bản chạy độc lập LẪN bản production. Không có dòng log `ERROR`
nào — đúng như T-01 dự đoán: ký tự bị bỏ ở bước parse nên không có gì để báo lỗi ở bước render.
Cùng cơ chế với bảng quy đổi trang 15 (bảng nghiêng, mất 39/58 block).

**(e) Đối chứng loại trừ T-09/T-10 làm nguyên nhân chính**: 3 trang chạy lại độc lập
(trang 7 mục lục, 63 Fiche de Technique, 67) — **không** trang nào sinh log
`"Unable to export paragraphs that have not yet been formatted"`. Cơ chế T-09/T-10 **tồn tại
trong source nhưng chưa quan sát thấy kích hoạt** trên dữ liệu này → giữ lại như rủi ro đã
biết, KHÔNG kết luận là nguyên nhân của UX-C.

**(f) Kết quả bất ngờ, quan trọng cho UX-D**: trang mục lục (trang 7, 0-index 6) và trang
"Fiche de Technique" (trang 63) khi chạy LẠI ở chế độ **1 trang độc lập** thì render **ĐÚNG** —
dòng nối tiếp đều đặn `y = 289.5 → 305.1 → 320.7 → 336.3`, cùng `x = 119.9`, không lệch cột,
không đè heading. Trong bản production **cùng trang đó** các dòng nối tiếp lại nhảy ngược lên
trên và lệch trái (`y=289.6 x=119.9` → dòng tiếp theo `y=271.1 x=101.0`), và dòng
"Hai chữ T: Nhiệt độ" (`y=329.7 x=328.2`, cỡ 10.0) đè lên heading cha "4. Kỹ Thuật và Kỹ Năng
Làm Bánh 172" (`y=330.2 x=330.0`, cỡ 12.0) — **đúng hiện tượng UX-D**.

⚠️ **`[UNVERIFIED]`** — chưa xác định được biến nào tạo ra khác biệt production vs 1-trang.
Hai ứng viên, cả hai đều **chưa** kiểm chứng:
1. **T-07 (nghi ngờ mạnh nhất)**: mode-scale tính trên TOÀN BỘ document của 1 lần gọi babeldoc.
   Production gọi babeldoc theo **chunk ~38 trang** (11 chunk cho 418 trang) → mode lấy trên 38
   trang; chạy 1 trang → mode lấy trên 1 trang → `optimal_scale` khác → font khác → số dòng
   khác → vị trí khác. Số đo ủng hộ: các dòng lệch trong production đều có cỡ chữ **nhỏ hơn**
   (8.3/9.2/9.9/10.0) so với các dòng đặt đúng (10.2/12.8).
2. Độ dài text LLM trả về khác nhau giữa 2 lần chạy (không deterministic).

Không được viết fix cho UX-D trước khi phân biệt được 2 khả năng này (xem T6-1).

### T4. Root cause chi tiết

#### RC-T1 — UX-A / UX-B / UX-E: không có reflow giữa các paragraph, tràn box vẫn vẽ

Chuỗi nhân quả, mỗi mắt xích có nguồn:

1. Text dịch VI dài hơn EN → cần nhiều dòng hơn trong đúng bbox gốc.
2. Vòng `_find_optimal_scale_and_layout` thu nhỏ font để cứu (T-05). Mỗi paragraph tự chọn
   scale riêng → **UX-E (font-size không đều)**. UX đoán đúng: UX-E là **hệ quả**, không phải
   lỗi độc lập.
3. Giãn khung chỉ được thử **sau khi đã thu nhỏ xuống dưới 0.7** và chỉ khi cạnh dưới/phải còn
   khoảng trống (T-06). Trong box trang trí cỡ cố định hoặc ô bảng chật, không có chỗ trống →
   giãn thất bại → chỉ còn cách bóp chữ → **UX-B**. Box text ngắn (caption "Antonin Carême")
   vừa ngay ở scale 1.0 → không hỏng. Đúng đối chứng UX nêu: biến quyết định là **tỉ lệ độ dài
   text / sức chứa khung**, không phải loại box.
4. Nếu tới `min_scale = 0.1` vẫn không vừa: **không có nhánh nào cắt bớt hay dừng vẽ** — T-04
   nói thẳng là cố ý vẽ tiếp ra ngoài box.
5. Paragraph kế tiếp vẫn neo vào `box.y2` gốc của chính nó (T-03), không hề biết paragraph
   trước đã tràn tới đâu → chữ tràn nằm chồng lên chữ của block dưới → **UX-A**.
6. Bước chống chồng lấn duy nhất (T-08) đi **sai hướng**: nó **cắt ngắn** box trên chứ không
   đẩy block dưới xuống → giảm chỗ chứa, làm bước 4 dễ xảy ra hơn.

Điểm này giải thích luôn quan sát baseline "đầu trang sạch, cuối trang nát" của UX: không phải
sai số cộng dồn theo toạ độ, mà là **xác suất cộng dồn** — trang càng xuống dưới càng nhiều
paragraph đã tràn đè lên nhau, và block dưới không có cách nào tự tránh.

#### RC-T2 — UX-C: ký tự xoay bị vứt ở bước parse (lỗi ĐỘC LẬP, không liên quan độ dài text)

`il_creater.py:968-974` (T-01): bất kỳ glyph nào có góc xoay ngoài `0°±0.1` và `90°±0.1` bị
`return` — không vào IL, không được dịch, không được vẽ lại. Vì babeldoc **dựng lại content
stream** thay vì sửa tại chỗ, text gốc cũng không còn → đúng hiện tượng "ô trắng trống, không
ai biết mình đang thiếu gì".

Sách Le Cordon Bleu dùng rất nhiều khối nghiêng nhẹ (~11°) làm chú giải/pull-quote và bảng
quy đổi đặt nghiêng → 7.832 ký tự / 19 trang mất trắng (T3-c). Đây là **Blocker** đúng như UX
xếp hạng.

Lưu ý phân biệt: hiện tượng "vài ô trong bảng Fiche de Technique trống" mà UX quan sát **không**
tái hiện được khi chạy lại trang đó độc lập (T3-e/f: 42 block / 1.352 ký tự, gần bằng bản gốc
41 block / 1.320 ký tự). Nhiều khả năng phần lớn "ô trống" trong ảnh chụp trang đó thực ra là
**chữ bị dời chỗ (RC-T1)** chứ không phải mất hẳn — người đọc nhìn ảnh không phân biệt được 2
loại. Chỉ nội dung xoay là mất thật, đã chứng minh.

#### RC-T3 — UX-D: chưa xác định, phụ thuộc ngữ cảnh chunk

Xem T3-f. `[UNVERIFIED]`. Không gộp vào RC-T1 vì RC-T1 chỉ giải thích được dịch chuyển **xuống
dưới**, còn quan sát production là dòng nối tiếp nhảy **lên trên và sang trái**.

### T5. Phần thuộc về code của team (không phải "toàn bộ nằm ở babeldoc")

Khác kết luận RC-1 (2026-09-06, "root cause không nằm trong code của team"), lần này team có
đóng góp thật vào triệu chứng:

| # | Vấn đề phía team | Nguồn |
|---|------------------|-------|
| P-1 | Chunk theo trang (~38 trang/chunk) = **ranh giới document của T-07**. Mode-scale — tức cỡ chữ cuối cùng — phụ thuộc vào việc trang nào rơi vào chunk nào. Cùng 1 trang, chunk khác nhau ⇒ cỡ chữ khác nhau ⇒ **UX-E xuyên chương** và (nghi) **UX-D**. | T-07 + `src/core/chunking.py` (chunk theo `page_start/page_end`) |
| P-2 | `BabeldocRunner` **không** truyền `--translate-table-text` (T-12). Chưa đo được flag này ảnh hưởng gì tới trang bảng — có thể tốt hơn, có thể tệ hơn. | `babeldoc_runner.py:280-311` |
| P-3 | `BabeldocRunner` **không** truyền `--max-pages-per-part` (T-13) → không kiểm soát được đơn vị tính mode-scale độc lập với kích thước chunk. | như trên |
| P-4 | Không có kiểm tra hậu kỳ nào phát hiện chồng lấn hay mất nội dung. Job báo `completed` với 19 trang mất chữ và hàng trăm cặp block chồng nhau. Đây đúng dạng lỗ hổng Protocol 6 R6-03 đã mô tả, ở cấp **chất lượng render** thay vì cấp **liên kết bước**. | `src/core/job_orchestrator.py` |

### T6. Phương án đề xuất — theo TỪNG nhóm lỗi

Không có 1 giải pháp chung. Effort tính theo ngày-người của 1 Dev.

#### G1 (UX-C, Blocker) — patch runtime cho ngưỡng góc xoay của babeldoc

Nới điều kiện `il_creater.py:973` từ `±0.1°` lên ngưỡng cấu hình được (đề xuất `±15°`), để text
nghiêng nhẹ vẫn vào IL. Có 3 cách thực thi:

| Cách | Mô tả | Effort | Risk |
|------|-------|--------|------|
| G1a | **Fork/patch có kiểm soát**: `uv tool` cài babeldoc từ fork nội bộ đã sửa 1 dòng đó | 1–2 ngày (gồm dựng pipeline build fork) | **Cao** — nợ bảo trì vĩnh viễn, mỗi lần babeldoc lên version phải rebase; đúng loại nợ Protocol 5 sinh ra để tránh |
| G1b | **`sitecustomize`/wrapper monkey-patch**: vì gọi qua **subprocess**, có thể chèn 1 module patch qua `PYTHONPATH` + `PYTHONSTARTUP` không đụng file cài | 1 ngày | **Cao** — sửa hành vi tool bên thứ 3 từ bên ngoài, khó debug, dễ vỡ âm thầm khi đổi version |
| G1c | **Tiền xử lý: "duỗi thẳng" text nghiêng** — dùng PyMuPDF phát hiện line có `dir` ngoài 0°/90°, redact text gốc và vẽ lại cùng nội dung ở góc 0° trong cùng bbox, TRƯỚC khi đưa vào babeldoc | 2–3 ngày | **Trung bình** — không đụng babeldoc; đánh đổi: mất hiệu ứng nghiêng thẩm mỹ (chấp nhận được: thà chữ thẳng còn hơn mất chữ). Rủi ro thật: bbox của text nghiêng rộng hơn text thẳng nên thường đủ chỗ, nhưng **chưa verify** trên mẫu thật |
| G1d | **Chấp nhận + cảnh báo**: không sửa render, nhưng **phát hiện và báo cáo** — quét trước, ghi vào job "19 trang chứa 7.832 ký tự xoay sẽ bị mất", xuất phụ lục text các khối đó | 0,5 ngày | **Thấp** |

**Khuyến nghị**: **G1d ngay** (rẻ, biến lỗi im lặng thành lỗi nhìn thấy được — đúng tinh thần
UX xếp UX-C là Blocker *vì người đọc không biết mình mất gì*), rồi **G1c** làm fix thật.
**Không** chọn G1a/G1b nếu chưa thử G1c.

⚠️ **`[UNVERIFIED]`**: G1c chưa được spike. Bắt buộc R5-02 spike trên trang 67 và trang 15
trước khi implement đầy đủ.

#### G2 (UX-A/B/E, Critical) — giảm áp lực tràn thay vì sửa engine typeset

Viết lại thuật toán typeset của babeldoc là ngoài tầm (≈ toàn bộ `typesetting.py`, 1.682 dòng).
Bốn hướng khả thi:

| Hướng | Mô tả | Effort | Risk | Ghi chú |
|-------|-------|--------|------|---------|
| G2a | **Prompt "dịch cô đọng"**: bắt buộc bản dịch ≤ ~110% độ dài nguồn (đo bằng ký tự), thêm chỉ thị vào `src/core/prompt_builder.py` biến thể babeldoc | 0,5 ngày | Thấp | Chỉ giảm áp lực, không xoá lỗi. PRD đã có chiến lược "concise prompt" — hiện chưa áp cho nhánh babeldoc. **Đo được**: so tỉ lệ ký tự VI/EN trước–sau |
| G2b | **Chuẩn hoá đơn vị tính mode-scale**: truyền `--max-pages-per-part` cố định (vd 4) độc lập với chunk size → cỡ chữ không còn phụ thuộc chunk nào chứa trang nào (P-1/P-3) | 0,5 ngày | Thấp–TB | Sửa **UX-E xuyên chương** và có thể cả UX-D. **Phải A/B đo trước** — chưa verify part nhỏ hơn có tốt hơn không |
| G2c | **Gate chất lượng tự động (DoD-UX-01/02)**: hậu kiểm output — đếm cặp block chồng > 5% và block gốc không có text dịch tương ứng; vượt ngưỡng → đánh dấu trang cần review, không báo `completed` trắng trơn | 1,5–2 ngày | Thấp | Script đo đã có sẵn ở T3 (chạy thật rồi). Đây là món **giá trị nhất trên đơn vị công**: không sửa được lỗi nhưng chặn được việc giao hàng lỗi mà không ai biết |
| G2d | **Fallback engine cho trang phức tạp**: phát hiện trang nhiều cột/bảng → dịch bằng `pdf2zh` thay vì babeldoc | 3–5 ngày | **Cao** | ⚠️ **`[UNVERIFIED]` — CHƯA ĐƯỢC ĐỀ XUẤT**: chưa đo pdf2zh trên đúng các trang này. pdf2zh cũng neo bbox gốc và cũng có tràn chữ (chính lý do project thêm babeldoc). **Không implement trước khi có 1 lần đo A/B thật trên trang 6, 13, 63, 67** |

**Khuyến nghị**: **G2c + G2a** trước (rẻ, rủi ro thấp, kết quả đo được ngay), **G2b** sau khi
A/B; **G2d chỉ khi đã verify pdf2zh thực sự tốt hơn trên đúng bộ trang này**.

#### G3 (UX-D, Major) — điều tra trước, sửa sau

Chưa đủ dữ liệu để đề xuất fix. Việc cần làm (0,5 ngày, không cần code sản phẩm):
chạy babeldoc trên **cùng trang mục lục** với 3 cấu hình — (i) 1 trang, (ii) 38 trang giống
chunk production, (iii) 38 trang + `--max-pages-per-part 4` — rồi so vị trí/cỡ chữ. Nếu (ii)
tái hiện lỗi còn (iii) thì không → xác nhận T-07 là nguyên nhân, và **G2b chính là fix cho cả
UX-D**. Nếu cả (ii) và (iii) đều tái hiện → nguyên nhân khác, điều tra tiếp.

#### G4 — Report upstream

Cả RC-T1 (T-04, cố ý vẽ tràn) và RC-T2 (T-01, vứt ký tự xoay) đều là hành vi của babeldoc, ảnh
hưởng mọi người dùng dịch sang ngôn ngữ dài hơn ngôn ngữ nguồn. Nên mở issue upstream kèm 2
file tái hiện tối thiểu đã có sẵn (`p67.pdf`, `p15.pdf`). Effort 0,5 ngày, risk 0, nhưng
**không tính là fix** — không được chờ upstream để đóng task.

**✅ Đã thực hiện (2026-09-07)**: đã mở issue tại
[funstory-ai/BabelDOC#615](https://github.com/funstory-ai/BabelDOC/issues/615) — tổng hợp
3 lỗi kèm nguồn xác thực (file:line): Bug A = RC-T2 (T-01, vứt glyph xoay), Bug B = RC-T1
(T-04 vẽ tràn + T-08 chống chồng lấn sai hướng), Bug C = root cause `max_tokens=2048` hardcode
mất nội dung với reasoning model (CHANGELOG 2026-09-06). Repro file (`p67.pdf`, `p15.pdf`)
chưa đính kèm trực tiếp trong issue, sẽ gửi khi maintainer yêu cầu. **Không chờ phản hồi
upstream để đóng bất kỳ task nào** — giữ nguyên tinh thần G4/P2.2.

#### G5 — Known limitation trong PRD

Dù chọn hướng nào, ghi vào PRD: bản dịch giữ layout PDF **không** đảm bảo 100% không chồng
chữ trên trang bố cục phức tạp với engine hiện tại; kèm số đo thật ở T3 để người dùng biết quy
mô. Effort 0,5 ngày.

### T7. Yêu cầu test kèm bất kỳ fix nào (Protocol 5 + 6)

1. **Golden fixture từ output thật, không viết tay** (Protocol 5 mục 3): lưu
   `tests/fixtures/babeldoc/rotated_text_p67.pdf` (đã trích, có khối -11°) và
   `toc_2col_p7.pdf`. Assert: sau khi dịch, **số ký tự của khối nghiêng > 0**.
2. **Test theo DoD-UX-01/02 của UX**, không phải theo flag: đo cặp bbox giao > 5% và block gốc
   không có text dịch — chính script ở T3.
3. **Live E2E (R6-03)**: mở PDF output và **đọc nội dung** vùng khối nghiêng; không tin field
   `status`.
4. **Data lineage (R6-02)**: nếu làm G2b, assert giá trị `max_pages_per_part` từ `Settings` đi
   thật tới `args` của subprocess, không chỉ `assert_awaited()`.

### T8. Trạng thái verify (tổng hợp)

| Claim | Trạng thái |
|-------|-----------|
| Ngưỡng góc xoay ±0.1° làm mất ký tự | ✅ Verified — source `il_creater.py:968-974` + tái hiện live trang 67 |
| Quy mô mất chữ do xoay (7.832 ký tự / 19 trang) | ✅ Verified — đo trên PDF gốc thật |
| Overflow được cố ý vẽ ra ngoài box | ✅ Verified — `typesetting.py:1440-1444` + comment gốc |
| Không reflow giữa các paragraph | ✅ Verified — `typesetting.py:1349-1350` |
| Giãn khung chỉ chạy khi scale < 0.7 | ✅ Verified — `typesetting.py:1017-1062` |
| Mode-scale tính trên cả document | ✅ Verified — `typesetting.py:919-935` |
| Chồng lấn tăng sau dịch (số liệu bảng T3-a) | ✅ Verified — đo trên output production |
| T-09/T-10 (composition rỗng) là nguyên nhân UX-C | ❌ **Đã loại trừ trên dữ liệu này** — 3 lần chạy live không sinh log tương ứng; giữ lại như rủi ro đã biết |
| Nguyên nhân UX-D | ⚠️ **`[UNVERIFIED]`** — không tái hiện được ở chế độ 1 trang; xem G3 |
| Mode-scale/chunk là nguyên nhân UX-D và UX-E xuyên chương | ⚠️ **`[UNVERIFIED]`** — mới là suy luận từ source + 1 quan sát cỡ chữ; cần A/B ở G3 |
| pdf2zh có bị lỗi tương tự hay không | ⚠️ **`[UNVERIFIED]`** — chưa đo. **Chặn** đề xuất G2d |
| `--translate-table-text` ảnh hưởng trang bảng | ⚠️ **`[UNVERIFIED]`** — chưa đo |
| G1c (duỗi thẳng text nghiêng) khả thi | ⚠️ **`[UNVERIFIED]`** — chưa spike (bắt buộc R5-02) |

---

## Final Decision: Babeldoc Layout Bug Fix Roadmap (sau phản biện Domain Expert, 2026-09-07)

**Tác giả**: Tech Lead. **Đầu vào**: section "Root Cause Analysis: Text Overlap, Content-Loss
& Reading-Order…" (T1–T8, 2026-09-07) + phản biện độc lập của Domain Expert (PDF typesetting).
**Trạng thái**: ✅ **Đây là quyết định kỹ thuật cuối cùng** cho nhóm lỗi UX-A…UX-E. Ba mục
thuộc thẩm quyền PM/user được tách riêng ở U7 (escalation).

Mọi claim mới trong section này đã được Tech Lead **tự verify lại**, không kế thừa từ phản
biện. Nguồn xác thực ghi ở U1.

### U1. Kết quả tự verify các phát hiện mới của Domain Expert (Protocol 5 / R5-01)

Môi trường: babeldoc **0.6.4** (`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`),
pdf2zh **1.9.11** (`/Users/hieutt/.local/share/uv/tools/pdf2zh/lib/python3.12/site-packages/pdf2zh/`),
PyMuPDF **1.28.2 / MuPDF 1.28.2**. Prefix `IL/` = `format/pdf/document_il/`.

| ID | Claim của Expert | Phán quyết | Nguồn xác thực Tech Lead tự chạy/đọc |
|----|------------------|-----------|--------------------------------------|
| V-1 | Backend babeldoc **không** render được chữ xoay góc tuỳ ý → nới ngưỡng góc KHÔNG phải fix tận gốc | ✅ **ĐÚNG — xác nhận** | `IL/backend/pdf_creater.py:111-120` chỉ phát 2 dạng `Tm`: `0 1 -1 0` (khi `char.vertical`) và `1 0 0 1` (mọi trường hợp khác). `IL/il_version_1.py:627-663`: `PdfCharacter` có `vertical: bool`, `scale: float` — **không có field góc xoay nào**. Kể cả nới ngưỡng ở `il_creater.py:973`, char nghiêng vẫn bị vẽ lại NGANG. |
| V-2 | pdf2zh 1.9.11 **không** vứt chữ nghiêng nhẹ; chỉ lọc font dọc | ✅ **ĐÚNG — xác nhận** | `pdf2zh/converter.py:244`: điều kiện duy nhất liên quan matrix là `child.matrix[0] == 0 and child.matrix[3] == 0` (font dọc thuần). Char nghiêng ~11° có `matrix[0]≈matrix[3]≈0.98` → không khớp → đi tiếp như text thường; render tại `converter.py:384` với `1 0 0 1 x y Tm` (ngang). Kết luận: pdf2zh **không mất chữ**, nhưng **cũng duỗi thẳng** — thẩm mỹ ≈ G1c. |
| V-3 | Text trong vùng nhãn `table` **không được dịch**, giữ nguyên tiếng Anh (loại content-loss thứ 4) | ❌ **BÁC BỎ** — xem U2 | Cơ chế Expert mô tả có thật nhưng **bị vô hiệu hoá bởi `fallback_line`**; và đo trên output production cho kết quả ngược lại. Chi tiết + số liệu ở U2. |
| V-4 | `babeldoc` latest trên PyPI = 0.6.4 = bản đang cài; nên pin | ✅ **ĐÚNG — xác nhận** | PyPI JSON API `https://pypi.org/pypi/babeldoc/json` (fetch 2026-09-07): `info.version = 0.6.4`; releases gần nhất `0.5.9 → 0.6.0 → 0.6.1 → 0.6.2 → 0.6.3 → 0.6.4`. |
| E-1 | `get_max_bottom_space()` đo chỗ trống thật, không đè paragraph khác → "giãn trước, bóp sau" là patch nhỏ không dây chuyền | ✅ **ĐÚNG — xác nhận** | `IL/midend/typesetting.py:1628-1660`: hàm loại trừ mọi `page.pdf_paragraph`, `page.pdf_character`, `page.pdf_figure` nằm dưới và có giao ngang, chặn dưới bằng `page.cropbox.box.y * 1.1`. **Phát hiện bổ sung của Tech Lead**: khi giãn xuống THÀNH CÔNG (`typesetting.py:1036-1037`) vòng lặp `continue` với `scale` ĐANG ở mức < 0.7 — **không bao giờ thử lại scale 1.0 trong box đã giãn**. Tức chữ bị bóp nhỏ vĩnh viễn dù sau đó đã có đủ chỗ. Đây là 1 lỗi logic thật, đúng như Expert dự đoán, và mạnh hơn Expert mô tả. |
| E-2 | babeldoc vứt char xoay **im lặng**, không cả `logger.debug` | ✅ **ĐÚNG — xác nhận** | `IL/frontend/il_creater.py:968-974`: nhánh `return` ở dòng 974 không có log; chỉ nhánh `except` (dòng 975-979) mới `logger.warning`. |
| E-3 | `insert_text(..., morph=(pivot, Matrix(angle)))` của PyMuPDF vẽ được text xoay góc tuỳ ý (khác `insert_textbox` chỉ 0/90/180/270) | ✅ **ĐÚNG — đã spike chạy thật** | Xem U3. |

### U2. BÁC BỎ V-3 — bảng KHÔNG bị bỏ dịch (bằng cả source lẫn dữ liệu sống)

Đây là điểm PM yêu cầu ưu tiên verify vì nếu đúng sẽ là loại content-loss thứ 4. **Kết luận:
không phải.** Bốn tầng bằng chứng:

**(1) Expert đọc `is_text_layout()` bị cắt cụt.** Expert trích `layout_helper.py:801-813` và
kết luận danh sách "chỉ chứa `table_text`". Danh sách thật kéo dài tới **dòng 849**, gồm
`table_caption`, `table_footnote`, `table_title`, `table_cell`, `wired_table_cell`,
`wireless_table_cell`, `table_cell_hybrid`… (`layout_helper.py:803-849`). Đúng là **không có
nhãn trần `table`** — phần này Expert nói đúng.

**(2) Model layout mặc định thật sự sinh nhãn `table`** — nên nguy cơ là có thật, không phải
tưởng tượng. Tech Lead nạp trực tiếp metadata của model ONNX đang dùng
(`~/.cache/babeldoc/models/doclayout_yolo_docstructbench_imgsz1024.onnx`, đọc bằng
`onnx.load` + `metadata_props`, đúng cách `docvision/doclayout.py:47-49` làm):

```
{0:'title', 1:'plain text', 2:'abandon', 3:'figure', 4:'figure_caption',
 5:'table', 6:'table_caption', 7:'table_footnote', 8:'isolate_formula', 9:'formula_caption'}
```

Chạy chính model này trên file gốc, trang 63 (Fiche de Technique) cho:
`{'table': 1, 'table_caption': 1, 'abandon': 2}` với box `table` = `[88.8, 78.1, 612.8, 462.5]`
— tức **gần trọn trang**. Nếu chỉ có cơ chế Expert mô tả thì cả trang 63 phải là tiếng Anh.

**(3) Nhưng `fallback_line` chặn đường đó lại.** `IL/midend/layout_parser.py:171-208`: sau khi
chạy model, babeldoc **luôn** gọi `generate_fallback_line_layout_for_page()` cho MỌI trang,
sinh thêm 1 `PageLayout(class_name="fallback_line", conf=1)` bao quanh **từng cụm dòng chữ**.
`fallback_line` **có** trong `is_text_layout` (`layout_helper.py:844`) và đứng **trên**
`table`/`figure`/`image` trong `layout_priority` (`layout_helper.py:725-728`) —
`get_character_layout()` trả về layout ưu tiên cao nhất khớp char, nên char trong ô bảng nhận
`fallback_line`, **không** nhận `table` → không rơi vào `skip_chars` ở
`paragraph_finder.py:454-455` → **được dịch bình thường**.

**(4) Đo trên output production thật (R6-03)** — job `136645f9-…`, `translated_vi.pdf`, đếm ký
tự trong block ≥ 25 ký tự không mang dấu tiếng Việt (chuẩn hoá NFD, bắt cả `ăâđêôơư`):

| Chỉ số | Giá trị |
|--------|---------|
| Tổng ký tự (block ≥ 25 ký tự) | 631.947 |
| Ký tự trong block **không có dấu tiếng Việt** | 17.180 (**2,7%**) |
| Số trang có > 200 ký tự không dấu | **11 / 418** |
| Trang 63 (Fiche de Technique, vùng `table` gần trọn trang) | 39 block, chỉ **3** block không dấu, đều là tên riêng: `"Fondant au chocolat, coulis de framboise"`, `"© Le Cordon Bleu International"`, `"Gluxit Protein 100 200"` (`Gluxit` LÀ tiếng Việt) |

11 trang còn lại là **index/mục lục cuối sách (409–418)**, **credit ảnh** (`"Credits: …
© iStockphoto.com"`, trang 18, 188) và **danh sách tên riêng** (trang 16: tên các cơ sở
Le Cordon Bleu, tên người). Không có trang nào là bảng bị bỏ dịch.

**Kết luận U2**: V-3 **sai về hệ quả**. Không tồn tại loại content-loss thứ 4. Cơ chế
`is_text_layout` → `skip_chars` là **rủi ro đã biết** (nếu upstream đổi/bỏ `fallback_line`, hoặc
nếu bật `--translate-table-text` làm đổi tập nhãn), nên ghi vào bảng rủi ro U6, **không** đưa
vào roadmap fix.

**Hệ quả cho đề xuất `--translate-table-text`**: Expert nâng flag này thành "quyết định sản
phẩm hạng nhất" **dựa trên tiền đề vừa bị bác bỏ**. Vì bảng đã được dịch sẵn, flag này mất lý
do chính. Nó vẫn có thể cải thiện **cách gom dòng** trong bảng (thay `fallback_line` theo dòng
bằng `wired/wireless_table_cell` theo ô), nhưng đó là câu hỏi chất lượng dàn trang, kèm chi
phí nạp thêm RapidOCR và rủi ro "experimental". → **Giữ nguyên mức P2 tuỳ chọn**, đo kèm trong
thí nghiệm A/B duy nhất (P0.2), **không** nâng ưu tiên.

### U3. G1e (overlay PyMuPDF `morph`) — ĐÃ SPIKE THẬT, KHẢ THI

Tech Lead đã chạy spike (không mock), PyMuPDF 1.28.2:

```python
page.insert_text(pivot, text, fontsize=11,
                 morph=(pivot, pymupdf.Matrix(11)),      # xoay 11°
                 fontname="vi", fontfile="fonts/NotoSerif-Regular.ttf")
```

Kết quả đọc lại bằng `get_text("dict")` trên chính file vừa ghi:

```
dir: (0.9816271066665649, -0.19080941379070282)
text: 'Đường nghiêng: nhiệt độ 180°C, 250g bột mì'
```

Hai điều được chứng minh cùng lúc:
1. `morph` cho ra góc xoay tuỳ ý thật — và `dir` thu được **trùng khít** với `dir` của khối
   nghiêng trang 67 trong sách gốc đã đo ở T3-d (`(0.982, -0.191)`). Tức đây đúng là công cụ
   tái tạo lại được hiệu ứng thiết kế đã mất.
2. Dấu tiếng Việt đầy đủ (`Đ ườ ệ độ ộ ì`) + ký hiệu `°C` render và trích xuất lại đúng, với
   **font project đã có sẵn** — `fonts/NotoSerif-Regular.ttf` là file font duy nhất trong repo,
   không cần thêm dependency.

**Rủi ro còn lại của G1e (chưa spike, phải làm ở P1.1)**: `insert_text` **không tự xuống dòng**
— phải tự tách dòng + tự bóp font cho vừa bbox nghiêng. Đây chính là "tam nan" ở U5 nhưng trong
phạm vi **ta kiểm soát được**: bóp tới 70% (đúng DoD-UX-03) rồi FLAG, không bao giờ bóp tới 0.1
như `min_scale` của babeldoc.

**Quyết định**: **CHỌN G1e làm hướng chính cho UX-C**, thay thế G1c trong đề xuất T6. Lý do
quyết định là **V-1**, không phải "nợ bảo trì": vì backend babeldoc không có khả năng render
góc xoay (không có field góc trong `PdfCharacter`), **mọi** hướng đi xuyên qua babeldoc —
G1a fork, G1b monkey-patch, G1c duỗi thẳng — đều **bắt buộc** mất góc nghiêng. G1e là hướng
duy nhất giữ được thẩm mỹ, effort ngang G1c (2–3 ngày). **G1a/G1b bị LOẠI vĩnh viễn**: chúng
không những mang nợ bảo trì mà còn **không đạt được mục tiêu** (V-1) — nới ngưỡng chỉ đổi "mất
chữ" thành "chữ bị duỗi thẳng + gom dòng sai", vì `paragraph_finder` gom dòng bằng hình học
ngang sẽ băm 1 dòng nghiêng 11° thành nhiều mảnh. Đồng ý với Expert ở điểm này.
**G1c giữ lại làm phương án dự phòng** nếu spike fit-text của G1e thất bại.

### U4. Roadmap đã chốt

Nguyên tắc: **đo trước, mọi fix phải A/B được, KHÔNG fork engine reflow.**

#### P0 — Thiết bị đo + khoá nền (≈ 3,5 ngày, làm trước mọi fix)

**P0.1 — Gate chất lượng G2c MỞ RỘNG (2 ngày).** Hậu kiểm output PDF, 5 kiểm tra:

| Kiểm tra | Nguồn / lý do | Ứng với |
|----------|---------------|---------|
| a. cặp block text giao > 5% diện tích block nhỏ hơn | script đã chạy thật ở T3-a | DoD-UX-01 / UX-A |
| b. text vượt qua **đường viền vẽ** (`page.get_drawings()`) | ✅ đồng ý với Expert (5c) — gate chỉ đo text∩text sẽ cho PASS sai 1 trang có đúng 1 box tràn viền mà không đè text nào | DoD-UX-03 / UX-B |
| c. text đè lên **ảnh** (`page.get_image_rects()`) | như trên | UX-B |
| d. **pre-scan chữ xoay** trên file GỐC (`line["dir"]` ngoài 0°/90°) → cảnh báo trước + xuất phụ lục text (chính là G1d) | T3-c (7.832 ký tự / 19 trang) | UX-C |
| e. **bảo toàn thực thể**: regex trích `số + đơn vị` (`180°C`, `250g`, `10 min`, `1/2`) từ block GỐC, assert xuất hiện đủ trong block dịch tương ứng | ✅ đồng ý với Expert (mục 2) — **đây là lỗ hổng nghiêm trọng nhất của đề xuất T6 cũ: toàn bộ test đang đo hình học, không có dòng nào đo nội dung** | DoD-UX-02 |

Output **bắt buộc** là **hàng đợi review theo trang, xếp hạng mức nghiêm trọng + ảnh overlay**,
không phải 1 kết quả pass/fail toàn tài liệu — với 418 trang, mục tiêu là QA soi 30–50 trang bị
flag. ✅ Đồng ý hoàn toàn với Expert. Bổ sung của Tech Lead: gate phải **ghi số đo vào DB theo
job** để so được giữa các lần chạy — nếu không thì không A/B được, và đó chính là lý do gate
phải đứng TRƯỚC mọi fix.

**P0.2 — MỘT thí nghiệm A/B duy nhất (1 ngày).** ✅ Đồng ý gộp G3 + G2b-A/B + P-2 + G2d thành
1 lần chạy — chúng vốn là cùng 1 thí nghiệm; chạy tách là lãng phí 1 vòng round-trip.
- Trang: **7, 13, 15, 63, 67** (đã trích sẵn từ T3; phủ mục lục / văn xuôi 2 cột / bảng nghiêng
  / bảng lớn / khối chú giải nghiêng).
- Cấu hình: (i) 1 trang; (ii) chunk 38 trang giống production; (iii) chunk 38 +
  `--max-pages-per-part 4`; (iv) (ii) + `--translate-table-text`; (v) pdf2zh cùng bộ trang.
- **Khoá biến "LLM không deterministic"** ✅ (đồng ý — Expert đúng, và đây là điều T6/G3 bỏ
  sót): chạy (i) trước để làm ấm cache babeldoc, các lần sau **KHÔNG** truyền `--ignore-cache`
  (`src/services/babeldoc_runner.py:323-324` chỉ thêm flag khi `ignore_cache=True` → chỉ cần
  đặt False). Không khoá cache thì mọi kết luận đều bị nghi ngờ.
- **Dump debug paragraph boxes; so SỐ PARAGRAPH + BOX, không chỉ so vị trí dòng cuối** ✅
  (đồng ý). Tech Lead xác nhận tiền đề suy luận của Expert là đúng: RC-T3 ghi nguyên văn hiện
  tượng production là dòng nhảy **"lên trên và sang trái"**, không phải xuống dưới — nên "gom
  nhầm paragraph" là ứng viên hợp lệ ngang hàng T-07 mode-scale, và `--split-short-lines` (app
  đang bật, `babeldoc_runner.py:308-309`) là biến nghi ngờ chính.
- Trả lời **cùng lúc 4 câu**: UX-D do đâu; G2b (`--max-pages-per-part`) có đáng không;
  `--translate-table-text` đổi gì trên trang bảng; pdf2zh có đáng làm fallback cho 19 trang chữ
  xoay không.

**P0.3 — Pin `babeldoc==0.6.4` (0,1 ngày).** ✅ Đồng ý. Mọi số đo ở T3/U1/U2 và toàn bộ thiết
kế G1e đều gắn với hành vi bản này; upstream đang release dày (6 bản gần đây).

#### P1 — Fix thật (≈ 3 ngày, chỉ bắt đầu sau khi P0 xanh)

**P1.1 — UX-C: spike fit-text cho G1e (0,5 ngày) → implement (2 ngày).**
Spike phải trả lời: với khối 16 dòng nghiêng −11° ở trang 67, bản dịch VI có vừa bbox gốc ở
scale ≥ 0,7 không. Đạt → implement. Không đạt → **G1c** (duỗi thẳng, mất góc nghiêng) hoặc
**pdf2zh cho riêng 19 trang xoay**, chọn theo số đo P0.2-(v).
**Data lineage (R6-01)**: `rotated_blocks ← source.pdf` (quét bằng PyMuPDF, `line["dir"]`) →
`translated_blocks ← LLM provider của app` (KHÔNG qua babeldoc) → overlay lên
`babeldoc_output.pdf` bằng `insert_text(..., morph=…)`. Bước overlay đọc `translated_blocks`,
**không** đọc lại `source.pdf`.
G1d (phụ lục text cho QA) đã nằm trong P0.1-d và giao **luôn** kèm mọi phương án — nhưng ✅ đồng
ý với Expert: đó là **phụ lục cho QA**, không phải sản phẩm giao người đọc.

**P1.2 — Viết lại G2a theo hướng bất biến nội dung (0,5 ngày).** ✅ **Đồng ý với Expert, và đây
là chỗ Tech Lead tự nhận đề xuất T6/G2a cũ SAI.** Bản cũ ghi "bắt buộc bản dịch ≤ ~110% độ dài
nguồn" — hard cap độ dài trong prompt ép LLM lược bỏ định lượng/gộp bước. Với sách công thức,
mất "180°C" hay "10 phút" nguy hiểm hơn UX-C nhiều: bản dịch **trông hoàn hảo**, gate hình học
không bao giờ bắt được. G2a bản chốt:
- (a) prompt nêu **bất biến nội dung tường minh**: mọi con số, đơn vị, nhiệt độ, thời gian, tên
  nguyên liệu, số bước phải có đủ trong bản dịch;
- (b) khuyến khích **văn phong cô đọng** (bỏ hư từ, câu ngắn) — KHÔNG đưa con số 110% vào
  prompt; tỉ lệ ký tự chỉ là **metric đo SAU**, không phải chỉ thị cho LLM;
- (c) chốt chặn là **gate P0.1-e** (bảo toàn số + đơn vị), không phải lời hứa của prompt.
Ghi rõ: G2a chỉ tác dụng ở văn xuôi, **không cứu được UX-B** (box cố định vốn text đã ngắn).

**P1.3 — G2b (`--max-pages-per-part`) chỉ implement nếu P0.2 chứng minh.** Kèm assert data
lineage R6-02: giá trị từ `Settings` phải đi thật tới `args` của subprocess, không chỉ
`assert_awaited()`.

#### P2 — Nền dài hạn

- **P2.1 — Chính sách "tam nan" theo loại phần tử** → **escalate PM/user**, xem U7.
- **P2.2 — Upstream babeldoc**: 2 PR nhỏ + 1 issue.
  - PR (a): **đảo thứ tự "giãn xuống TRƯỚC, bóp SAU"**. ✅ Đồng ý với Expert, và Tech Lead
    verify ra lý do mạnh hơn (E-1): hiện tại khi giãn xuống thành công, vòng lặp `continue` với
    `scale` đang < 0.7 và **không bao giờ thử lại 1.0** trong box mới — chữ bị bóp nhỏ vĩnh viễn
    dù đã có đủ chỗ. Đây là **bug logic**, không chỉ "thứ tự chưa tối ưu" → khả năng merge cao.
  - PR (b): biến ngưỡng góc `il_creater.py:973` thành tham số CLI + **thêm log khi vứt char**
    (hiện `return` im lặng, E-2). Không đổi default → rủi ro merge thấp.
  - Issue: kèm `p67.pdf` / `p15.pdf` (đã có sẵn từ T3). **✅ Đã mở
    [funstory-ai/BabelDOC#615](https://github.com/funstory-ai/BabelDOC/issues/615)
    (2026-09-07)** — xem chi tiết ở G4. PR (a)/(b) ở trên **chưa** mở, mới dừng ở đề xuất trong
    thân issue #615 (đợi phản hồi maintainer trước khi bỏ công viết PR thật).
  Ghi rõ: **không được chờ upstream để đóng task** (giữ nguyên tinh thần G4).
- **P2.3 — `--translate-table-text`**: chỉ xét lại nếu P0.2-(iv) cho số đo tốt hơn rõ rệt.
  Không còn là ưu tiên sản phẩm sau khi V-3 bị bác bỏ (U2).
- **P2.4 — G5 known limitation trong PRD**, kèm số đo thật ở T3 + U2.
- **P2.5 — KHÔNG fork engine reflow.** ✅ Đồng ý tuyệt đối với Expert. Reflow đúng nghĩa = đẩy
  paragraph N+1 xuống theo chiều cao thật của N → dây chuyền toàn trang → đụng hình/box cố
  định/footer → phải tràn sang trang sau → **lệch số trang so với mục lục/index**. Đó là viết
  lại 1 engine dàn trang, không phải patch. Nếu sau P0–P1 văn xuôi vẫn vượt ngưỡng chấp nhận,
  thứ tự xét là: PR upstream (P2.2a) → monkey-patch có pin version (phương án cuối cùng, chỉ
  khi PR bị từ chối).

### U5. Khung "tam nan" — điểm Expert đúng mà T6 cũ nói chưa đủ rõ

✅ Đồng ý, và ghi nhận đây là đóng góp có giá trị nhất của phản biện. Khi text đích dài hơn
nguồn 20–40% mà khung giữ nguyên, phần dôi ra chỉ có 3 chỗ để đi: **(1) bóp font** (→ UX-E),
**(2) giãn khung** (→ phá layout, đẩy khối dưới, tràn trang), **(3) cắt/rút text** (→ rủi ro
nội dung). babeldoc chọn (1), và khi hết cách thì **cố ý vẽ tràn** (T-04) — đây là **quyết định
POLICY của một tool dùng chung**, không phải bug ngẫu nhiên.

Hệ quả với cách trình bày của T6 cũ: T6-G2c tuy có tự ghi "không sửa được lỗi, chỉ chặn giao
hàng lỗi", nhưng đặt nó ở vị trí "khuyến nghị hàng đầu" dễ khiến người đọc hiểu thành "làm gate
là xong". **Nói lại cho rõ**: gate là **thiết bị đo**, không phải fix. Nó đứng đầu P0 vì
**không có nó thì không A/B được bất kỳ patch nào** — chứ không phải vì nó giải quyết được
UX-A/B/E.

### U6. Rủi ro đã biết (theo dõi, không fix ngay)

| # | Rủi ro | Vì sao không fix ngay |
|---|--------|----------------------|
| RK-1 | `is_text_layout()` không chứa nhãn trần `table`; text vùng `table` chỉ thoát được nhờ `fallback_line` (U2-3). Nếu upstream bỏ/đổi `generate_fallback_line_layout_for_page`, **toàn bộ bảng sẽ ngừng được dịch trong im lặng** | Đã đo: hiện KHÔNG xảy ra (U2-4). Đã pin version (P0.3). Gate P0.1-e (bảo toàn số/đơn vị) sẽ bắt được nếu nó xảy ra về sau |
| RK-2 | T-09/T-10 (paragraph composition rỗng → log `"Unable to export paragraphs…"`) | Đã loại trừ trên dữ liệu này (T3-e); giữ nguyên trạng thái theo dõi |
| RK-3 | G1e overlay đặt text lên PDF đã qua `compress_pdf_images` (US-16) — thứ tự 2 bước phải cố định | Ghi vào spec P1.1: overlay chạy **sau** merge chunk, **trước** nén ảnh, để bước nén không đụng text mới thêm |

### U7. Escalate cho PM/user (không thuộc thẩm quyền Tech Lead)

✅ Đồng ý với Expert: đây là **quyết định sản phẩm**, phải do PM/user chốt rồi ghi vào PRD.
Tech Lead chỉ trình bày lựa chọn và hệ quả.

**E-1. Chính sách tam nan theo TỪNG loại phần tử.** Đề xuất của Tech Lead để PM duyệt:

| Loại phần tử | Chính sách đề xuất | Hệ quả người dùng nhìn thấy |
|--------------|-------------------|----------------------------|
| Văn xuôi 1 cột có khoảng trắng dưới | Cho phép **giãn khung xuống** trước, giữ font 100% | Khoảng cách giữa các khối thay đổi nhẹ |
| Box trang trí / ô bảng cỡ cố định | Bóp font tối đa tới **70%** (DoD-UX-03) rồi **FLAG**, KHÔNG bóp tới 0.1 | Một số box bị flag để QA sửa tay |
| Mục lục / index | KHÔNG bóp, KHÔNG giãn — ưu tiên **rút gọn tiêu đề mục** | Tên mục có thể ngắn hơn bản gốc |
| Khối chữ xoay | Overlay G1e giữ góc; không vừa thì bóp tới 70% rồi FLAG | Giữ được thiết kế nghiêng |

**E-2. Ngưỡng chấp nhận release.** DoD-UX-01/02/03 hiện là "chặn release" tuyệt đối. Với số đo
T3-a (trang văn xuôi thường cũng có 5 cặp chồng lấn), **giữ nguyên = không bao giờ release
được**. PM cần chốt ngưỡng định lượng, ví dụ "≤ 5% số trang bị flag ở mức nghiêm trọng".

**E-3. Review thủ công bắt buộc.** ✅ Đồng ý với Expert (5d): 3 lớp trang phải QA soi tay 100%
**bất kể gate nói gì** — 19 trang chữ xoay (danh sách ở T3-c), mọi trang có vùng nhãn `table`,
và mục lục/index. Ước tính ~40–60 trang — khả thi; 418 trang thì không. PM cần xác nhận QA có
ngân sách thời gian cho việc này.

### U8. Trạng thái verify (tổng hợp section này)

| Claim | Trạng thái |
|-------|-----------|
| V-1 backend babeldoc không render được góc xoay tuỳ ý | ✅ Verified — `pdf_creater.py:111-120`, `il_version_1.py:627-663` |
| V-2 pdf2zh không vứt chữ nghiêng nhẹ, nhưng cũng duỗi thẳng | ✅ Verified — `converter.py:244, 384` |
| V-3 bảng chưa từng được dịch | ❌ **BÁC BỎ** — `layout_parser.py:171-208` + `layout_helper.py:725-728, 844` + đo output production (2,7% ký tự không dấu; trang 63 đã dịch) |
| V-4 babeldoc latest = 0.6.4 | ✅ Verified — PyPI JSON, fetch 2026-09-07 |
| E-1 "giãn trước, bóp sau" khả thi + scale không bao giờ về 1.0 sau khi giãn | ✅ Verified — `typesetting.py:1017-1062, 1628-1660` |
| G1e `insert_text(morph=…)` xoay góc tuỳ ý + dấu tiếng Việt | ✅ Verified — spike chạy thật, PyMuPDF 1.28.2, `dir=(0.9816,−0.1908)` trùng khít khối gốc trang 67 |
| G1e fit text dài trong bbox nghiêng | ⚠️ `[UNVERIFIED]` — spike bắt buộc ở P1.1 (R5-02) |
| Nguyên nhân UX-D | ⚠️ `[UNVERIFIED]` — thí nghiệm P0.2 phải phân biệt mode-scale (T-07) vs gom nhầm paragraph (`--split-short-lines`) |
| pdf2zh có tốt hơn babeldoc trên 19 trang xoay không | ⚠️ `[UNVERIFIED]` — đo ở P0.2-(v) |
| `--translate-table-text` ảnh hưởng trang bảng | ⚠️ `[UNVERIFIED]` — đo ở P0.2-(iv); đã hạ ưu tiên sau U2 |

---

### Kết quả thí nghiệm A/B — P0.2 (2026-09-07, Dev)

**Cách chạy** (đúng spec U4/P0.2, không mock — Protocol 5 R5-03): gọi thẳng
`babeldoc`/`pdf2zh` CLI thật qua `asyncio.create_subprocess_exec`, dùng chung file gốc
`data/uploads/f88282bb-…_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf` (418 trang,
xác nhận lại bằng PyMuPDF), cùng flag production (`--split-short-lines --short-line-split-factor
0.8`, `--openai-thinking disabled` cho DeepSeek, model `deepseek-v4-flash` — đúng giá trị đang
override trong bảng `settings` của DB, không phải default `deepseek-chat` trong code). Script
spike lưu tại
`/private/tmp/.../scratchpad/p02_experiment/run_experiment.py` (không phải code sản phẩm).

**Khoá cache**: chạy (i) 1-trang riêng lẻ cho cả 5 trang TRƯỚC để làm ấm cache, các lần sau
không truyền `--ignore-cache`. Ghi chú quan trọng phát hiện thêm: dù đã làm ấm cache, một vài
đoạn dịch vẫn đổi nhẹ giữa các lần gọi khác batch-context (ví dụ tiêu đề trang 7 dịch ra
"Mục lục" ở chế độ 1 trang nhưng "Nội dung" ở chế độ chunk, "Hai Chữ T: Nhiệt Độ" viết hoa khác
"Hai chữ T: Nhiệt độ") — tức cache của babeldoc không khoá được 100% biến LLM non-deterministic
khi ngữ cảnh batch xung quanh đoạn đó thay đổi (batch cùng 1 request gồm nhiều đoạn). Các so
sánh dưới đây vì vậy ưu tiên tín hiệu HÌNH HỌC (bbox, số block, overlap) hơn là tín hiệu câu chữ
chính xác.

**Cách bật debug JSON**: `--debug` CLI flag chỉ set `TranslationConfig.debug=True` (help text
"Use debug logging level" gây hiểu lầm — đã đọc source `main.py:694`/`high_level.py:916-1030`
để verify). Khi `debug=True`, JSON được ghi vào `working_dir` (không phải `--output`!),
`working_dir` mặc định là `~/.cache/babeldoc/working/<stem file input>/` nếu không truyền
`--working-dir` — **và bị GHI ĐÈ giữa các lần chạy cùng 1 file input** nếu không tách riêng.
Đã tự truyền `--working-dir <thư mục riêng theo config>` cho mỗi lần gọi để tránh mất dữ liệu.
Với `--max-pages-per-part`, `working_dir` của từng part bị `cleanup_part_working_dir()` xoá
NGAY sau khi part đó xong (`high_level.py:671`) — nên KHÔNG lấy được JSON debug per-part cho
cấu hình (iii); phải đối chiếu bằng cách đọc trực tiếp PDF output cuối (mono) thay vì JSON.

**Câu hỏi 1 — UX-D do mode-scale-theo-chunk (T-07) hay gom nhầm paragraph do
`--split-short-lines`?**

Đối chiếu đúng cặp đoạn PM từng thấy lỗi trong production ("4. Kỹ Thuật và Kỹ Năng Làm Bánh
Ngọt 172" / "Hai chữ T: Nhiệt độ", trang 7) qua `typsetting.json` (IL, toạ độ PDF-native
y-up) VÀ qua PDF output cuối (PyMuPDF, toạ độ top-left) ở cả 3 cấu hình — (i) 1 trang, (ii)
chunk 1-40 y hệt production, (iii) chunk 1-40 + `--max-pages-per-part 4`:

| Cấu hình | bbox heading | bbox sub-entry | Thứ tự |
|---|---|---|---|
| (i) 1 trang | (330.0,330.3)-(546.6,344.6) | (361.2,361.5)-(467.5,377.0) | heading TRÊN, sub-entry DƯỚI — ĐÚNG |
| (ii) chunk 1-40 | (330.0,330.3)-(546.6,344.6) | (361.2,361.4)-(469.6,377.8) | heading TRÊN, sub-entry DƯỚI — ĐÚNG |
| (iii) chunk + mpp4 | (330.0,330.3)-(546.6,344.6) | (361.2,361.4)-(469.6,377.8) | heading TRÊN, sub-entry DƯỚI — ĐÚNG |

**Kết quả bất ngờ**: KHÔNG tái hiện được hiện tượng UX-D cho đúng cặp đoạn này ở BẤT KỲ cấu
hình nào trong lần chạy này — bbox gần như giống hệt nhau giữa cả 3 cấu hình (heading giống
tuyệt đối, sub-entry lệch < 2pt do word-wrap khác 1 chữ). Điều này **không xác nhận** T-07 hay
`--split-short-lines` là biến quyết định cho CHÍNH cặp đoạn này ở lần chạy hiện tại — nhiều khả
năng lỗi PM thấy trong production (T3-f, "391 384" và cặp "Hai chữ T" nói trên) là sản phẩm của
1 lần gọi LLM cụ thể khác (tổ hợp câu chữ/độ dài dịch khác đủ để đẩy paragraph qua ngưỡng
overflow) — **không loại trừ T-07** (chỉ là không tái hiện được lần này), nhưng cũng không xác
nhận được. Giữ nguyên trạng thái `[UNVERIFIED]` cho câu hỏi "nguyên nhân UX-D", không nâng
thành kết luận.

Tuy vậy, khi quét TOÀN BỘ trang 7 bằng gate P0.1 (không chỉ 1 cặp), chồng lấn là RẤT LỚN và
đồng nhất giữa (ii)/(iii): **149 cặp overlap ở cả (ii) và (iii)** (so với **157** ở (i) — chênh
lệch do khác câu chữ dịch, không phải do vị trí). Trên TOÀN BỘ 40 trang của chunk 1-40, tổng số
cặp overlap là **410.898 (ii)** so với **411.832 (iii)** — cùng bậc độ lớn, 25/40 trang có
chênh lệch nhưng không theo chiều hướng nhất quán (một số trang giảm: trang 30 giảm 1074→723,
trang 18 giảm 1240→881; một số trang tăng: trang 27 tăng 184→345, trang 6 tăng 175→208). Số
liệu áp đảo này (hàng trăm nghìn cặp overlap/40 trang) đến từ rất nhiều block cực nhỏ/trùng lặp
gần như tuyệt đối (`fallback_line` trùng khít `plain text` ở tỉ lệ giao 1.0) — đây là hạn chế
đã biết của gate P0.1-a khi áp lên trang dày đặc block nhỏ (bảng/mục lục nhiều dòng ngắn): số
đếm thô bị "ngợp" bởi nhiễu hình học chứ không phản ánh đúng mức độ nghiêm trọng thực tế — ghi
nhận đây là điểm cần tinh chỉnh gate (lọc block quá nhỏ hoặc dedupe trùng khít) ở vòng sau,
KHÔNG sửa trong task này (ngoài scope P0.1 đã chốt).

**Câu hỏi 2 — `--max-pages-per-part 4` có cải thiện đáng kể không?**

**KHÔNG.** Trên cả 3 trang đo trực tiếp (7, 63, 67):

| Trang | Overlap (ii, mặc định) | Overlap (iii, mpp4) | Char count (ii) | Char count (iii) |
|---|---|---|---|---|
| 7 | 149 | 149 | — | — |
| 63 | 55 | 57 | 3.286 | 3.318 |
| 67 | 4.243 | 4.243 | 5.978 | 5.962 |

Trang 7 và 67: SỐ OVERLAP GIỐNG HỆT NHAU giữa (ii) và (iii) — `--max-pages-per-part 4` không
đổi gì đo được ở 2 trang này trong lần chạy này. Trang 63 chỉ lệch ±2 (nhiễu). Tổng thể 40
trang của chunk 1-40 cũng cùng bậc độ lớn (410.898 vs 411.832, xem Câu hỏi 1). **Kết luận**:
không có bằng chứng `--max-pages-per-part 4` cải thiện đáng kể trên bộ trang này — **P1.3
(G2b) KHÔNG nên implement** dựa trên số đo P0.2 này (đúng điều kiện đã chốt ở U4: "P1.3 chỉ
implement nếu P0.2 chứng minh" — P0.2 KHÔNG chứng minh).

**Câu hỏi 3 — `--translate-table-text` đổi gì trên trang bảng (63)?**

Gần như KHÔNG đổi gì: 117 block text (mặc định) so với 118 block (`--translate-table-text`),
3.286 ký tự so với 3.319 ký tự, 55 overlap so với 57 overlap — sample nội dung dịch giống hệt
nhau theo thứ tự block. Khớp với kết luận U2 (V-3 "bảng chưa từng được dịch" đã bị BÁC BỎ —
bảng ĐÃ được dịch qua cơ chế `fallback_line` mặc định, xem `layout_helper.py:725-728, 844`) —
`--translate-table-text` không mang lại giá trị đo được thêm trên đúng trang bảng này.
**Kết luận**: giữ nguyên quyết định U2/T6 — **không nâng ưu tiên P2.3**.

**Câu hỏi 4 — pdf2zh có đáng làm fallback cho 19 trang chữ xoay không?**

So sánh trực tiếp bằng chính gate P0.1 vừa xây, chạy trên CẢ HAI output (babeldoc chunk 39-80
và pdf2zh 5-trang) cho 3 trang xoay (15, 63, 67):

| Trang | Char count pdf2zh | Char count babeldoc | Overlap pdf2zh | Overlap babeldoc | Nội dung nghiêng còn không? |
|---|---|---|---|---|---|
| 15 (bảng quy đổi, xoay 20°) | 1.651 | 860 | 74 | 47 | pdf2zh: nhiều chữ hơn hẳn (babeldoc mất phần lớn, khớp T3-c "39/58 block mất"); chưa xác nhận có đúng nội dung "CONVERSION CHART" bằng regex đơn giản |
| 63 (Fiche de Technique, không xoay) | 1.374 | 3.286 | **0** | 55 | N/A (không xoay) — pdf2zh **0 overlap** trên trang bảng này, tốt hơn hẳn babeldoc |
| 67 (chú giải xoay -11°, "Disaccharide") | 3.631 | 5.978 | 65 | 4.243 | **pdf2zh GIỮ ĐƯỢC nội dung** (`"...một loại disaccharide..."`, `"Disaccharide"`, `"The word disaccharide is composed..."`) — babeldoc **MẤT TRẮNG** hoàn toàn (khớp T3-d) |

Kiểm tra trực tiếp góc xoay (`line["dir"]`) trên output pdf2zh trang 67: **`dir=(1.0, 0.0)`**
— tức pdf2zh **duỗi thẳng** khối chữ nghiêng (khớp đúng V-2 đã verify trước đó qua source
`converter.py:244,384`: "pdf2zh không vứt chữ nghiêng nhẹ nhưng cũng duỗi thẳng"). Đồng thời
phát hiện MỚI: nội dung bên trong khối đó ở pdf2zh bị **dịch DỞ DANG** — dòng đầu đã dịch sang
tiếng Việt, 3 dòng còn lại (bao gồm chính tiêu đề "Disaccharide") **vẫn nguyên văn tiếng Anh**
— tức pdf2zh không mất chữ hoàn toàn nhưng chất lượng dịch không đồng nhất trên khối này.

**Kết luận, có điều kiện**: pdf2zh **đáng cân nhắc làm fallback cho vấn đề MẤT NỘI DUNG** (UX-C)
trên trang chữ xoay — nó KHÔNG BAO GIỜ tạo ra "ô trắng" như babeldoc quan sát được trên cả 3
trang test (15/63/67), và trên trang 63 (bảng, không xoay) overlap = 0 tuyệt đối tốt hơn hẳn.
NHƯNG: (a) nó đánh đổi mất góc nghiêng thẩm mỹ (duỗi thẳng, đã biết trước ở V-2 — đây chính là
lý do project chọn babeldoc lúc đầu), (b) chất lượng dịch không đồng nhất trong 1 khối (phát
hiện mới, `[UNVERIFIED]` cần đo thêm mẫu lớn hơn trước khi kết luận đây là hiện tượng hệ thống
hay ngẫu nhiên 1 lần), và (c) trên trang 15, pdf2zh có overlap CAO HƠN babeldoc (74 so với 47)
— tức không phải lúc nào pdf2zh cũng thắng tuyệt đối. **Giữ nguyên roadmap U4/P1.1**: hướng
chính cho UX-C vẫn là G1e (overlay giữ góc nghiêng, đã spike khả thi ở U3); pdf2zh cho 19 trang
xoay **chỉ nên là phương án dự phòng cuối** nếu spike fit-text G1e ở P1.1 thất bại — đúng thứ tự
đã chốt ở P1.1, số đo P0.2-(v) này KHÔNG đủ mạnh để đảo ngược quyết định đó (mới đo 3/19 trang,
1 lần chạy, chưa loại trừ non-determinism của LLM).

**Thời gian chạy thật** (tham khảo cho ước tính chi phí, KHÔNG phải benchmark hiệu năng
nghiêm ngặt — máy Dev, không kiểm soát tải hệ thống): 1 trang babeldoc ~42-51s; chunk 40 trang
babeldoc ~176-255s (~4-6s/trang); pdf2zh 5 trang riêng lẻ (không liền mạch, `--pages
"7,13,15,63,67"`) ~427s tổng — dùng cùng `--thread 8`/`--pool-max-workers 8` cho công bằng.

**File/artifact của thí nghiệm** (không commit vào repo, chỉ tham chiếu): script + toàn bộ
output/debug JSON của 11 lần chạy lưu tại
`/private/tmp/claude-501/.../scratchpad/p02_experiment/` (`run_experiment.py`,
`results_summary.json`, `config_i/` .. `config_v/`) — PM/QA cần xem lại số đo thô có thể yêu
cầu Dev export lại vào `tests/fixtures/babeldoc/` theo đúng Protocol 5 mục 3 (golden file) nếu
muốn dùng làm fixture test lâu dài; hiện tại đây là dữ liệu spike một lần, không phải fixture
đã chốt.

---

### Bug #6 — Root Cause & Phương án fix: chữ xoay bị mất góc trong OCR bridge (2026-09-07)

**Người viết**: Tech Lead (Opus). **Trạng thái**: Đánh giá/đề xuất SƠ BỘ — chờ Domain Expert
phản biện + PM/user quyết định. **Không có code nào được viết trong task này.**

**Đầu vào**: `docs/test-report.md` mục "QA Vòng 6" — Bug #6: overlay chữ xoay (P1.1/G1e) không
bao giờ kích hoạt cho job `pdf_scan` + `babeldoc`; `layout_qa_findings` = 0 hàng (im lặng hoàn
toàn). QA đã đánh dấu `[CHƯA VERIFY]`: "MinerU 3.4.5 có API/field nào khác chứa góc không?".
Task này trả lời DỨT ĐIỂM câu hỏi đó theo Protocol 5 R5-01/R5-02.

#### 6.13.1 — Nguồn xác thực (Protocol 5 R5-01)

Bản đã cài: `mineru --version` → **3.4.5**, đường dẫn
`/Users/hieutt/.local/share/uv/tools/mineru/lib/python3.12/site-packages/mineru/`.
Toàn bộ trích dẫn dưới đây là **đọc trực tiếp source code của bản đã cài này** (không phải trí
nhớ, không phải suy đoán), cộng thêm 1 nguồn doc chính thức đã fetch thật để đối chiếu chéo.

| # | Nguồn | Nội dung xác thực |
|---|---|---|
| S-M1 | `mineru/model/ocr/pytorch_paddle.py:203-225, 242-291` | Detector (DBNet, `self.text_detector`) trả `dt_boxes` dạng **poly 4 điểm** — có mang thông tin góc. `ocr(det=True, rec=False)` trả thẳng poly (`tmp_res = [box.tolist() for box in dt_boxes]`). |
| S-M2 | `mineru/utils/ocr_utils.py:276-297` (`merge_det_boxes`), `211-236` (`update_det_boxes`) | Poly nghiêng (`calculate_is_angle()` = True) được **cố ý tách riêng** vào `angle_boxes_list` và bỏ qua bước gộp/làm phẳng — góc **vẫn sống** ở tầng này. Comment gốc của tác giả (pytorch_paddle.py:218): "merge_det_boxes 和 update_det_boxes 都会把poly转成bbox再转回poly，因此需要过滤所有倾斜程度较大的文本框". |
| S-M3 | **`mineru/utils/ocr_utils.py:399-410`** | **Điểm mất góc — chốt.** `if calculate_is_angle(poly):` → poly nghiêng bị **thay bằng 1 hình chữ nhật thẳng trục** dựng quanh **trọng tâm** poly: `x_center/y_center` = trung bình 4 đỉnh, `new_height` = trung bình 2 cạnh dọc, `new_width = p3[0] - p1[0]`. Góc bị **vứt bỏ có chủ đích**, không lưu ở đâu. |
| S-M4 | `mineru/utils/ocr_utils.py:391-392` | Dòng comment chết `# average_angle_degrees = calculate_angle_degrees(box_ocr_res[0])` — hàm `calculate_angle_degrees` **không còn tồn tại** trong bản 3.4.5 (`grep -rn "calculate_angle_degrees"` chỉ khớp đúng dòng comment này). Tức là tác giả từng tính góc rồi **bỏ hẳn**. |
| S-M5 | `mineru/utils/ocr_utils.py:418-432` | `ocr_item` cuối cùng chỉ có `{"label","bbox","score","text"}` — `bbox` qua `normalize_to_int_bbox` (`mineru/utils/bbox_utils.py:7-32`: lấy min/max, luôn ra 4 số thẳng trục). **Không có field góc nào.** |
| S-M6 | `mineru/backend/pipeline/batch_analyze.py:788, 832` và `mineru/backend/hybrid/hybrid_analyze.py:212, 285` | **MỌI** nhánh OCR (batch và single, pipeline và hybrid) đều đi qua đúng `get_ocr_result_list()` ở S-M3. Không có đường vòng nào giữ được poly. |
| S-M7 | `mineru/backend/vlm/vlm_magic_model.py:54, 225`; `mineru/backend/hybrid/hybrid_analyze.py:357-366` (`_normalize_medium_vlm_angle`), `437` | Backend **VLM/hybrid** CÓ field `angle` trong block — nhưng bị chuẩn hoá cứng: `if normalized_angle in {0, 90, 180, 270}: return normalized_angle; return 0`. Nguồn của nó là **table orientation classifier** (`AtomicModel.TableOrientationCls`, dòng 437) — tức "bảng bị xoay ngang/ngược", KHÔNG phải góc nghiêng tuỳ ý. |
| S-M8 | Doc chính thức, fetch thật 2026-09-07: https://opendatalab.github.io/MinerU/reference/output_files/ | Xác nhận chéo S-M7: chỉ backend VLM sinh field `angle`, giá trị giới hạn trong `{0, 90, 180, 270}`; `middle.json`/`model.json` của backend **pipeline** (backend app đang dùng, `MinerURunner(backend="pipeline")`) **không có** field angle. |
| S-M9 | `mineru/utils/ocr_utils.py:453-513` (`get_rotate_crop_image` → `get_rotate_crop_image_for_text_rec`), gọi tại `pytorch_paddle.py:276` | Crop để nhận dạng chữ được **warp phối cảnh về ngang** (rectify) trước khi đưa vào `text_recognizer`. Đây là lý do MinerU **đọc đúng nội dung** chữ nghiêng nhưng trả toạ độ ngang. |

#### 6.13.2 — Trả lời dứt điểm câu `[CHƯA VERIFY]` của QA

**VERIFIED — MinerU 3.4.5 KHÔNG cung cấp góc xoay tuỳ ý qua bất kỳ API/config/output nào.**
Cụ thể, 3 mệnh đề con, mỗi cái có nguồn:

1. **Không phải "MinerU không tính được góc"** — detector DBNet của nó trả poly 4 điểm có góc
   thật, và MinerU còn có hàm `calculate_is_angle()` nhận biết poly nghiêng (S-M1, S-M2).
2. **Giả thuyết "góc bị tiêu thụ ở bước rectify" của PM là ĐÚNG MỘT PHẦN, nhưng không phải cơ
   chế chính** (đây là khả năng PM yêu cầu loại trừ): góc quả thật bị tiêu thụ ở
   `get_rotate_crop_image` để nhận dạng chữ (S-M9) — nhưng ngay cả nếu bỏ qua bước rectify,
   góc vẫn sẽ mất, vì có **một bước làm phẳng riêng, tường minh, có chủ đích** ở
   `get_ocr_result_list` (S-M3) áp lên chính poly gốc (không phải lên bản đã rectify). Ma trận
   rectify KHÔNG được lưu lại ở đâu (S-M9 tạo `img_crop` rồi bỏ ma trận). ⇒ **Không có "ma trận
   rectify nội bộ để đọc lại"** — hướng fix "moi lại rectify matrix" bị **LOẠI**.
3. **Không có cờ/env/backend nào bật lại góc**: đã liệt kê toàn bộ `MINERU_*` env của bản 3.4.5
   (`grep -rhoE "MINERU_[A-Z_]+"`, 40 biến) — không biến nào liên quan góc/skew/deskew.
   Backend `vlm`/`hybrid` có `angle` nhưng lượng tử hoá về `{0,90,180,270}` và nguồn là bộ phân
   loại hướng BẢNG (S-M7, S-M8) ⇒ **không dùng được cho góc -11°**. Chuyển sang backend VLM
   **KHÔNG** giải quyết Bug #6.

**Hệ quả kiến trúc**: `middle.json` là **API công khai duy nhất** app đang tiêu thụ, và nó
**vĩnh viễn** không mang góc cho backend pipeline. Muốn có góc, app **bắt buộc phải tự tính**
(hoặc gọi tầng dưới `middle.json`). Đây không phải thiếu sót cấu hình — là thiết kế của MinerU.

**Điểm phụ nhưng quan trọng cho mọi phương án fix** (VERIFIED, S-M3): với dòng chữ nghiêng,
bbox MinerU trả về **KHÔNG phải bounding box của poly**, mà là 1 **dải ngang mỏng đi qua trọng
tâm** dòng chữ (cao = chiều cao chữ thật, rộng = bề rộng ngang của poly). Nghĩa là:
- (a) `_insert_invisible_text` hiện tại chèn chữ vô hình vào đúng dải mỏng đó — lệch khỏi vệt
  mực thật, nhưng vẫn nằm ở giữa nó (chấp nhận được cho mục đích "cầu nối để dịch").
- (b) **Chỉ cần biết thêm 1 số vô hướng θ** là tái dựng được hình bình hành thật:
  tâm = tâm bbox, chiều cao = `y1-y0`, chiều dài = `(x1-x0)/cos θ`, xoay quanh tâm góc θ.
  Đây là điều làm phương án (A) rẻ hơn nhiều so với cảm giác ban đầu.

#### 6.13.3 — Các phương án

| Mã | Phương án | Cách làm | Effort | Rủi ro | Tự tin |
|---|---|---|---|---|---|
| **A** | App tự đo góc trên ảnh raster, bổ sung vào bridge | Module mới `src/preprocess/skew_probe.py`: render trang bằng PyMuPDF `get_pixmap()`, với MỖI span bbox của `middle.json` cắt vùng (nới rộng theo 6.13.2-a), nhị phân hoá, đo θ bằng **projection-profile** (quét θ ∈ [-20°, +20°], chọn θ tối đa hoá phương sai tổng theo hàng). Truyền θ vào `_insert_invisible_text` → `insert_text(..., morph=(pivot, Matrix(-θ)))` + tái dựng hình học theo 6.13.2-b. Overlay P1.1 sau đó chạy **không cần sửa dòng nào**. | **Cao** (~2-3 ngày: 1 spike đo độ chính xác + 1 increment Dev + QA live E2E) | **Trung bình-cao** | Cơ chế đo: `assumed` (chưa spike). Hình học tái dựng: `verified` (S-M3). |
| **A′** | Như A nhưng **chỉ để FLAG**, không đổi hình học | Cùng module `skew_probe.py`, cùng θ — nhưng θ **không** đi vào `insert_text`; chỉ dùng để ghi `layout_qa_findings` ("trang N có K dòng nghiêng ~θ°, overlay không khả dụng cho `pdf_scan`, cần soát tay"). | **Thấp-trung bình** (~0.5-1 ngày) | **Thấp** (không đụng hình học output, chỉ thêm hàng DB) | Như A cho phần đo; phần ghi flag `verified` (đã có sẵn `LayoutQaFindingData`) |
| **B** | Chấp nhận known-limitation, FLAG mức job | Ghi known-limitation vào PRD; `JobOrchestrator` ghi **1 finding cho mỗi job** `pdf_scan` + `babeldoc`: "nhánh scan không phát hiện được chữ xoay — soát tay 100% trang". Không đo góc. | **Rất thấp** (~2 giờ) | **Thấp**, nhưng **nhiễu cao** (mọi job scan đều bị flag, kể cả job không có chữ xoay → nguy cơ "flag fatigue" làm mất tác dụng chính U7-E3) | `verified` |
| **C** | Tự xoay ảnh trước khi gửi MinerU | Bị **LOẠI**. Bài toán con gà-quả trứng (phải biết θ trước mới xoay được → nếu đã biết θ thì đã là phương án A), và MinerU vẫn rectify từng dòng ở tầng crop (S-M9) nên xoay cả trang không giữ được gì. | — | — | `verified` (S-M9, S-M3) |
| **D** | Đổi engine `pdf_scan` sang pdf2zh | Bị **LOẠI cho mục tiêu giữ góc**: đã đo ở P0.2 câu 4 — pdf2zh cũng **duỗi thẳng** (`dir=(1.0,0.0)`), chỉ hơn ở chỗ không mất nội dung. Nhưng nhánh `pdf_scan` **đã không mất nội dung** (QA Vòng 6 mục 4: 3.310 ký tự tiếng Việt đúng nghĩa) ⇒ đổi engine không mua được gì, lại mất các ưu điểm khác của babeldoc. | — | — | `verified` (P0.2 câu 4, đo thật) |
| **E** | Gọi thẳng detector của MinerU ngoài luồng | Chạy subprocess bằng chính interpreter của MinerU (`~/.local/share/uv/tools/mineru/bin/python`) gọi `PytorchPaddleOCR.ocr(img, det=True, rec=False)` → nhận poly 4 điểm **còn nguyên góc** (S-M1), match với bbox `middle.json` theo trọng tâm, suy ra θ. Chính xác hơn A (dùng đúng model đã tải sẵn, không cần dep mới nặng). | **Cao** (~3-4 ngày) | **Cao** — phụ thuộc **API nội bộ** của MinerU (không phải API công khai), Protocol 5 mục 5 bắt verify lại toàn bộ mỗi lần nâng version; chạy model lần 2 → tăng thời gian job đáng kể; ghép venv lạ vào runtime app | Poly có góc: `verified` (S-M1). Chi phí/độ ổn định: `assumed` |

**Ghi chú dependency cho A/A′**: app **chưa có** `numpy` lẫn `cv2` (`pyproject.toml` dòng 7-23;
`uv run python -c "import numpy"` → `ModuleNotFoundError`). Projection-profile trên vùng crop đã
hạ mẫu (≤200px bề rộng, ~13-27 góc thử) chạy được bằng **Python thuần + PyMuPDF `Pixmap`**, không
cần dep mới — `assumed`, phải đo trong spike; nếu quá chậm thì thêm `numpy` (nhẹ), **không** thêm
`opencv`.

#### 6.13.4 — Một rủi ro ẩn của phương án A mà Domain Expert cần soi kỹ

Nếu A thành công (bridge mang chữ vô hình ĐÃ xoay), hành vi babeldoc trên nhánh `pdf_scan` sẽ
**đổi**: hiện tại babeldoc dàn khối chữ đó thành hộp ngang (QA Vòng 6 mục 4); khi input đã
nghiêng, nhiều khả năng babeldoc sẽ **vứt bỏ** khối đó như nó vẫn làm với `pdf_digital` (T3-d,
P0.2) → chừa chỗ trống cho overlay P1.1 điền vào — tức nhánh `pdf_scan` **hội tụ về đúng nhánh
`pdf_digital` đã PASS**. Đây là kịch bản mong muốn, nhưng là **`[UNVERIFIED]` — assumed**, phải
là câu hỏi ĐẦU TIÊN của spike A. Nếu babeldoc **vẫn** vẽ hộp ngang, A sẽ tạo ra **chữ đè chữ**
(overlay nghiêng chồng lên hộp ngang của babeldoc) — tệ hơn hiện trạng — và khi đó A cần thêm
1 bước xoá/che vùng babeldoc đã vẽ (`page.add_redact_annot`), làm effort/rủi ro tăng thêm một
bậc. `overlay_rotated_text()` hiện **chỉ vẽ, không xoá** (`_draw_block`,
`rotated_text_overlay.py:367-389`) — `verified`.

#### 6.13.5 — Đề xuất SƠ BỘ của Tech Lead

**Trả lời câu hỏi cốt lõi của PM ("đào sâu sửa tiếp hay chấp nhận known-limitation"):
CHẤP NHẬN known-limitation cho hình học, NHƯNG BẮT BUỘC sửa phần FLAG — cụ thể là phương án
A′, không phải B.**

Lý do (theo thứ tự sức nặng):

1. **Ưu tiên sai đối tượng nếu làm A ngay**: ví dụ động lực của toàn bộ roadmap P1.1 (trang 67,
   khối "Disaccharide" nghiêng -11°) nằm trên nhánh **`pdf_digital`** — nhánh này **đã PASS,
   verify sống, góc khớp < 0.01°** (QA Vòng 6 mục 3). Nhánh `pdf_scan` có chữ xoay hiện là
   trường hợp **giả định**, chưa có tài liệu thật nào trong corpus chứng minh nó xảy ra. Đầu tư
   2-4 ngày + rủi ro trung bình-cao cho 1 nhánh chưa có bằng chứng nhu cầu là sai thứ tự — đúng
   tinh thần kỷ luật đã áp dụng khi **bác bỏ P1.3** ở P0.2 ("chỉ implement nếu số đo chứng minh").
2. **Thiệt hại thực tế là thẩm mỹ, không phải nội dung**: QA Vòng 6 xác nhận nội dung dịch
   **không mất** trên nhánh scan (3.310 ký tự tiếng Việt đúng nghĩa). Đây là mức nghiêm trọng
   khác hẳn Bug #5 (mất trắng nội dung).
3. **Nhưng phần "im lặng" thì KHÔNG được chấp nhận** — đây là chỗ tôi **không** đồng ý với việc
   chỉ ghi known-limitation rồi thôi. Hệ thống đang **báo sai** rằng không có trang nào cần soi,
   trong khi chính sách U7-E3 tự đặt ra là "soát tay bắt buộc 100% cho mọi trang có chữ xoay".
   Im lặng có hệ thống nguy hiểm hơn lỗi thẩm mỹ.
4. **Chọn A′ chứ không B**, vì B (flag mức job) sẽ flag **mọi** job scan kể cả job không có chữ
   xoay → flag fatigue làm hỏng chính cơ chế U7-E1/U7-E3 mà nó định cứu. A′ flag **đúng trang
   có chữ nghiêng thật**.
5. **A′ là bước 1 của A, không phải ngõ cụt**: cùng module `skew_probe.py`, cùng θ. Nếu sau này
   corpus thật xuất hiện tài liệu scan có chữ xoay (bằng chứng nhu cầu), nâng A′ → A chỉ còn là
   nối θ vào `insert_text(morph=...)` + trả lời câu hỏi `[UNVERIFIED]` ở 6.13.4 — phần đo góc,
   phần khó và rủi ro nhất, đã xong và đã chạy thật trong production suốt thời gian đó (tức là
   **đã tự tích luỹ dữ liệu độ chính xác thật** thay vì phải spike mù).

**Giải pháp cụ thể đề xuất (A′)** — để Dev không phải đoán:

- **Module mới** `src/preprocess/skew_probe.py`, hàm
  `estimate_span_skew_deg(page: fitz.Page, bbox, *, max_abs_deg=20.0, step_deg=1.0) -> float | None`.
  Render **một lần mỗi trang** (`page.get_pixmap(dpi=150, colorspace=fitz.csGRAY)`), cắt vùng
  bbox **nới rộng dọc theo `(x1-x0) * sin(max_abs_deg)`** (bắt buộc, vì bbox MinerU là dải mỏng
  qua trọng tâm — 6.13.2-a), nhị phân hoá theo ngưỡng Otsu đơn giản, quét θ và chọn θ tối đa hoá
  phương sai của projection profile. Trả `None` khi tín hiệu yếu (tránh dương tính giả).
- **Ngưỡng**: coi là "nghiêng" khi `|θ| >= 3.0°` (dưới ngưỡng này là skew scan bình thường, không
  phải chữ xoay có chủ đích) — con số này **`[UNVERIFIED]`, phải hiệu chỉnh bằng fixture thật**
  (`tests/fixtures/babeldoc/rotated_text_p67_source.pdf` raster hoá 200 DPI, ground truth
  -10.9999°, đã có sẵn từ QA Vòng 6) trước khi chốt.
- **Điểm nối (R6-01, khai báo lineage tường minh)**: gọi trong `searchable_pdf.py` ngay tại vòng
  lặp đã có sẵn qua các span của `middle.json` (nơi `_collect_text_spans()` trả về), **cùng lúc**
  với việc dựng bridge — không thêm lần render trang thứ 2. Kết quả θ **không** đi vào
  `_insert_invisible_text` ở giai đoạn A′; nó đi vào `MinerUResult`/kết quả bridge dưới dạng
  danh sách `(page_number, bbox, angle_deg)`, rồi `JobOrchestrator` chuyển thành
  `LayoutQaFindingData` với lý do `"rotated_text_scan_unsupported"`.
- **Test bắt buộc (R6-02)**: assert **giá trị θ cụ thể** đo được từ fixture raster hoá (sai số
  cho phép ±1.5°) và assert **số hàng `layout_qa_findings` > 0** cho đúng job `pdf_scan` fixture
  đó — không chấp nhận `assert_called()`.
- **Không đụng** `rotated_text_overlay.py` (module đó ĐÚNG, QA đã verify sống ở nhánh digital).
- **PRD**: ghi known-limitation tường minh — "overlay giữ góc chữ xoay chỉ hỗ trợ `pdf_digital`;
  với `pdf_scan`, hệ thống **phát hiện và FLAG** trang có chữ xoay để soát tay, nhưng **không**
  tái tạo góc — nguyên nhân gốc nằm ở MinerU (6.13.1 S-M3), không sửa được từ phía app mà không
  tự đo góc lại."

**Việc cần làm ngay, độc lập với mọi phương án** (đã được QA nêu ở test-report mục 8, tôi tán
thành và nâng lên thành hạng mục kiến trúc): `src/api/main.py` **chưa cấu hình logging handler**
nào cho logger `src.*` ⇒ mọi `logger.warning(..., exc_info=True)` trong các nhánh best-effort
(bao gồm nhánh nuốt exception của `overlay_rotated_text()` tại `job_orchestrator.py:533-539`)
**im lặng hoàn toàn** trong production. Đây là **điều kiện khiến Bug #6 khó phát hiện** và sẽ
khiến bug tiếp theo cũng khó phát hiện y hệt. Đề xuất tách 1 task riêng, ưu tiên cao hơn cả A′.

**Trạng thái**: Đề xuất sơ bộ — chờ Domain Expert (Fable) phản biện độc lập, sau đó PM/user
quyết định. Không tự chuyển sang implement.

---

### Bug #6 — Final Decision sau phản biện Domain Expert (2026-09-07)

**Người viết**: Tech Lead (Opus). **Trạng thái**: QUYẾT ĐỊNH CUỐI của Tech Lead — thay thế mục
6.13.5 (đề xuất sơ bộ) ở phần trên. Vẫn **không có code nào được viết trong task này**. Có 2 câu
hỏi escalate lên PM/user ở V7.

**Đầu vào**: phản biện độc lập của Domain Expert (Fable), kèm spike thật Expert tự chạy. Toàn bộ
mục này chỉ ghi những gì **tôi (Tech Lead) tự chạy lại / tự đọc lại source được**, không nhận
kết quả của Expert như dữ kiện.

#### V1. Kết quả TỰ VERIFY lại các claim của Expert (Protocol 5 R5-01)

Phiên bản đã cài dùng cho mọi phép đo dưới đây: MinerU **3.4.5**
(`/Users/hieutt/.local/share/uv/tools/mineru/`), babeldoc **0.6.4**
(`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`,
`babeldoc.__version__` in ra `0.6.4`), PyMuPDF của venv app.

| # | Claim của Expert | Kết quả tự verify | Nguồn |
|---|---|---|---|
| V-1 | `PytorchPaddleOCR.ocr(img, det=True, rec=False)` trả poly **còn góc** | **XÁC NHẬN — tự chạy lại, tái hiện được.** Render `tests/fixtures/babeldoc/rotated_text_p67_source.pdf` ở 200 DPI (1800×2175 px) rồi gọi detector bằng chính interpreter MinerU: **88 poly**, trong đó **19 poly có \|θ\| ≥ 3°**. Loại 1 poly nhiễu (`score=0.51`, text `"0"`) bằng ngưỡng `score ≥ 0.8` → còn **18 dòng, θ ∈ [-11.40°, -10.29°]**. | Spike tự chạy, script `det_spike.py`, output `det_probe_p67.json` |
| V-2 | Độ chính xác góc | **XÁC NHẬN, thậm chí tốt hơn Expert báo.** Ground truth đo bằng PyMuPDF trên chính fixture: 17 dòng có `dir` = **-11.0°** (và 75 dòng 0°). Sai số **median ≈ 0.1°**, **max 0.40°** trên 18 dòng (Expert báo ≤0.7°). | So sánh trực tiếp GT PyMuPDF vs poly detector |
| V-3 | `ocr(det=True, rec=True)` **vẫn** giữ poly còn góc (kèm text) ⇒ điểm làm phẳng nằm ở tầng backend, không nằm trong class detector | **XÁC NHẬN bằng cả 2 cách.** (a) Chạy thật: 88 item, 19 item nghiêng, text đọc đúng (`"Disaccharide"`, `"The word disaccharide is composed of the prefix di"`, ...), score 0.99-1.00. (b) Đọc source: `pytorch_paddle.py:196-201` (`tmp_res = [[box.tolist(), res] ...]`) trả thẳng `dt_boxes` chưa qua `get_ocr_result_list`. | Spike + `pytorch_paddle.py:190-291` |
| V-4 | Chi phí thời gian của (E) | **XÁC NHẬN và RẺ HƠN cả số Expert đo.** Trên máy này: init model **0.73s**; `det` only **0.36s/trang**; `det+rec` **2.00s/trang**. ⇒ 400 trang scan ≈ **2,4 phút** (det-only) hoặc **~13 phút** (det+rec). *Lưu ý*: đây là 1 lần chạy, không kiểm soát tải máy — dùng để so sánh bậc độ lớn, không phải benchmark. | Spike tự chạy |
| V-5 | babeldoc `il_creater` vứt glyph **deterministic theo ma trận ký tự**, không phân biệt `render_mode` | **XÁC NHẬN.** `il_creater.py:968-974` (`on_lt_char`, bản 0.6.4): `rotation_angle = get_rotation_angle(char.matrix)`; `if not (-0.1 <= rotation_angle <= 0.1 or 89.9 <= rotation_angle <= 90.1): return`. `get_rotation_angle` = `atan2(b, a)` của ma trận (`il_creater.py:390-398`). `grep -n "render_mode"` trên toàn file → **0 kết quả** ⇒ chữ vô hình (`render_mode=3`) bị xử lý y hệt chữ thường. | Đọc source bản đã cài |
| V-6 | "Không có paragraph thì không có ô nền trắng" | **XÁC NHẬN, và mạnh hơn Expert nói.** `paragraph_finder.py:89-121` (`add_text_fill_background`) lặp `for paragraph in page.pdf_paragraph` → không paragraph thì không sinh `PdfRectangle` nào. Thêm nữa: `grep -rn "fill_background=True"` trên **toàn bộ package babeldoc** chỉ khớp **đúng 1 dòng** (`paragraph_finder.py:117`) ⇒ đây là **nơi DUY NHẤT** ô nền trắng được sinh ra, không có đường vòng nào khác. | Đọc source + grep toàn package |

#### V2. Rủi ro 6.13.4 ("2 lớp chữ đè nhau") — GỠ `[UNVERIFIED]`, nhưng KHÔNG gỡ hết

**Đồng ý với Expert**: với dải góc của bài toán thật (\|θ\| khoảng 3°-30°), rủi ro "2 lớp chữ đè
nhau" **KHÔNG xảy ra** — `verified` bằng V-5 + V-6. Chuỗi nhân quả: glyph xoay bị `on_lt_char`
`return` sớm → không vào IL → không có `pdf_paragraph` → `add_text_fill_background` không sinh
`PdfRectangle` nào → **không có hộp ngang nào để đè lên**. Đây đúng là cơ chế đã làm nhánh
`pdf_digital` "chừa chỗ trống" mà overlay P1.1 đang tận dụng (đã PASS QA Vòng 6).

**Bổ sung một điểm cả tôi lẫn Expert đều chưa nêu** (`verified`, V-5): điều kiện vứt glyph có
**hai** khoảng an toàn, không phải một — `-0.1..0.1` **và `89.9..90.1`**. Nghĩa là với chữ xoay
**≈ ±90°** (nhãn trục dọc trong biểu đồ, chữ chạy dọc mép bảng — rất phổ biến trong sách kỹ
thuật), babeldoc **GIỮ** glyph, **dựng** paragraph, và **vẽ** ô nền trắng ⇒ trong dải góc đó
rủi ro "2 lớp chữ đè nhau" là **CÓ THẬT**. Ghi lại đây để bất kỳ ai làm Phase 2 sau này không
đọc kết luận "KHÔNG xảy ra" ở trên một cách quá rộng.

⇒ **Sửa 6.13.4**: `[UNVERIFIED]` → **`verified: KHÔNG xảy ra với \|θ\| nằm ngoài lân cận 0° và
90°; CÓ xảy ra với θ ≈ ±90°`** (nguồn: `il_creater.py:968-974`, `paragraph_finder.py:89-121`,
grep `fill_background=True` toàn package babeldoc 0.6.4).

#### V3. Rủi ro MỚI Expert nêu ("raster tiếng Anh còn nguyên dưới overlay") — ĐÚNG HƯỚNG, SAI MỨC ĐỘ

Expert cảnh báo: nếu Phase 2 chỉ nối θ vào `insert_text` mà không thêm bước che nền, chữ tiếng
Việt sẽ **in đè trực tiếp lên pixel tiếng Anh gốc → "không đọc được gì cả, tệ hơn hiện trạng"**,
và đề xuất thêm một bước vẽ tứ giác xoay che nền (~0.5 ngày), lấy mẫu màu nền từ pixmap.

**Tôi BÁC BỎ MỘT PHẦN — đo được, không phải suy đoán:**

1. **Bước che nền KHÔNG phải là bước còn thiếu — nó ĐÃ TỒN TẠI trong code.**
   `src/preprocess/searchable_pdf.py:113-125` đã có sẵn vòng lặp whiteout 2 pha: với **mọi**
   span, vẽ `page.draw_rect(..., fill=(1,1,1), overlay=True)` với `whiteout_padding=1.5pt`
   **trước** khi chèn chữ vô hình (comment trong code nói rõ vì sao phải tách 2 pha). Nhánh này
   vốn **chỉ chạy cho `pdf_scan`** (`build_searchable_pdf` chỉ được gọi ở cầu nối OCR), nên điều
   kiện "chỉ bật cho `pdf_scan`" Expert đề xuất cũng đã tự thoả mãn.
2. **Mức độ hở thực tế: 5,5%, không phải 100%.** Tôi mô phỏng đúng công thức làm phẳng của MinerU
   (`ocr_utils.py:399-410`) lên chính 18 poly nghiêng detector trả về ở V-1, dựng lại dải whiteout
   ngang + padding 1.5pt, rồi đo tỷ lệ diện tích vệt mực nghiêng **không** được che (lấy mẫu lưới
   1px): **5,5% tổng diện tích**. Phân bố **rất lệch**: 15/18 dòng ở giữa khối hở **≤ 2,2%** (các
   dải ngang của những dòng kề nhau chồng lấn và che hộ nhau), toàn bộ phần hở dồn vào **các dòng
   rìa khối**: 17,8% (dòng tiêu đề `"What's in a word?"`), 11,2% và **28,5%** (dòng cuối
   `"blocks of the sucrose molecule."`).
   ⇒ Kết quả thật sẽ là **vệt chữ tiếng Anh sót lại ở mép trên/mép dưới khối**, không phải "không
   đọc được gì cả". Nói cách khác **rủi ro là THẬT và phải fix, nhưng nó không đảo ngược so sánh
   với hiện trạng** — luận điểm "tệ hơn hiện trạng" của Expert là **quá mạnh so với số đo**.
3. **Hệ quả về thiết kế Phase 2** (rẻ hơn Expert ước tính): việc cần làm **không phải** thêm một
   module che nền mới, mà là **đổi hình dạng whiteout đã có**: trong đúng vòng lặp pha 1 của
   `searchable_pdf.py:113-125`, khi span có θ, thay `draw_rect` bằng tứ giác xoay
   (`Shape.draw_polygon` + `finish(fill=(1,1,1))`) dựng từ poly gốc + padding. **Không cần lấy
   mẫu màu nền** như Expert đề xuất: production hiện đã tô **trắng thuần** cho 100% span của mọi
   trang scan và QA Vòng 6 đã PASS ⇒ đổi màu tô là thay đổi hành vi ngoài phạm vi Bug #6, nếu
   muốn thì tách task riêng.
4. **`[CHƯA VERIFY]` mới, phải là câu hỏi ĐẦU TIÊN của Phase 2**: các hình chữ nhật whiteout do
   cầu nối vẽ có **sống sót** qua bước babeldoc dựng lại trang hay không (babeldoc chỉ vứt glyph,
   nhưng tôi **chưa** đo trực tiếp việc nó giữ nguyên vector rect của trang gốc). Bằng chứng gián
   tiếp ủng hộ: QA Vòng 6 không báo hiện tượng chữ tiếng Anh lộ ra trên toàn trang scan — nếu
   whiteout bị mất thì **mọi** span (kể cả 75 dòng ngang) đều sẽ lộ chữ gốc, khó bỏ sót. Nhưng
   suy luận gián tiếp không thay thế phép đo.

#### V4. Đánh giá lại phương án (E) — TÔI RÚT LẠI đánh giá cũ ở 6.13.3

Ở 6.13.3 tôi chấm (E) là "effort cao (~3-4 ngày), rủi ro cao, chạy model lần 2 → tăng thời gian
job đáng kể". **Đánh giá đó dựa trên phỏng đoán chưa đo, và số đo của tôi ở V1 bác bỏ nó**:

| Tiêu chí | (A) projection-profile tự viết (đánh giá cũ) | (E) gọi detector MinerU (số đo thật hôm nay) |
|---|---|---|
| Độ chính xác | `assumed`, chưa spike, yếu với dòng ngắn | **max 0.40°, median 0.1°** trên 18 dòng thật (V-2) |
| Ghép span với `middle.json` | theo trọng tâm bbox đã bị làm phẳng — mơ hồ | theo **TEXT** (`det+rec` trả text, score 0.99-1.00) — gần như không nhầm (V-3) |
| Dependency mới | có thể cần `numpy` | **không** — dùng lại venv MinerU đã cài |
| Chi phí | chưa đo | **0.36s/trang** (det) / **2.0s/trang** (det+rec) + 0.73s init (V-4) |

**Kết luận**: (E) **thắng (A) trên mọi tiêu chí đã đo**. Lý do duy nhất còn lại để dè chừng (E) là
**bề mặt API nội bộ** — và điều đó được xử lý bằng golden fixture (Protocol 5 mục 3), không phải
bằng cách né phương án. ⇒ **Phương án nền tảng chuyển từ (A) sang (E).** Đánh giá cũ ở bảng 6.13.3
dòng (A)/(E) coi như **bị thay thế bởi mục V4 này**.

#### V5. Điểm KHÔNG đồng ý với Expert: bỏ "bộ lọc bậc thang" khỏi Phase 1

Expert đề xuất dùng heuristic "bậc thang" (đo độ trôi trọng tâm bbox giữa các dòng trong 1 khối,
suy ra góc gần đúng, sai số ~1°) làm **pre-filter rẻ tiền** để chỉ chạy detector trên trang nghi
ngờ. **Tôi loại hạng mục này khỏi Phase 1**, lý do dựa trên chính số đo của tôi:

- Chi phí mà pre-filter định tiết kiệm là **2,4 phút cho 1 sách 400 trang** (det-only, V-4) — so
  với 1 job scan vốn mất **hàng giờ** (OCR toàn bộ + dịch LLM từng chunk). Tiết kiệm **dưới 1%**
  thời gian job.
- Đổi lại, nó thêm **một code path thứ hai, kém chính xác hơn**, với chế độ hỏng riêng mà chính
  Expert đã thừa nhận: **bỏ sót caption 1 dòng** — tức bỏ sót đúng loại khối mà cơ chế FLAG sinh
  ra để bắt (nhãn xoay, pull-quote ngắn). Một bộ lọc âm tính giả nằm **trước** cơ chế chống im
  lặng thì phá hỏng chính mục tiêu của cơ chế đó (đúng bài học Bug #6).
- Nguyên tắc đã áp dụng khi bác bỏ P1.3 ở P0.2: **chỉ tối ưu khi số đo chứng minh cần tối ưu**.
  Ở đây số đo chứng minh điều ngược lại.

Nếu sau này đo được thời gian probe thật sự đáng kể trên corpus lớn (ví dụ > 5% thời gian job),
mở lại hạng mục này — ghi vào backlog, không làm bây giờ.

#### V6. QUYẾT ĐỊNH CUỐI — 2 pha, xây trên (E)

**Tôi chấp nhận cấu trúc 2 pha của Expert thay cho A′ thuần tuý của tôi.** Lý do tôi đổi ý (chứ
không phải chỉ nhượng bộ): trong đề xuất cũ, lập luận số 5 của tôi ("A′ là bước 1 của A, không
phải ngõ cụt") là **suy đoán** — với (A) tự viết, phần đo góc là phần khó nhất và chưa ai biết nó
có đủ chính xác để dùng cho hình học hay không. Sau spike hôm nay, với (E), lập luận đó trở thành
**sự thật đo được**: góc đã có sẵn với sai số 0.4°, nên khoảng cách từ "chỉ flag" tới "dựng đúng
hình học" thu lại còn **2 chỉnh sửa cục bộ trong đúng 1 file** (`searchable_pdf.py`: nối θ vào
`insert_text(morph=...)`, và xoay tứ giác whiteout ở V3-3). Khi delta nhỏ và đã biết rõ như vậy,
việc **viết sẵn Phase 2 thành thiết kế có điều kiện kích hoạt** rẻ hơn hẳn việc để nó là "known
limitation vĩnh viễn" rồi phải research lại từ đầu. Đây là ưu điểm thật của đề xuất Expert so với
A′ của tôi.

**PHASE 1 — làm ngay, ~1 ngày** (mục tiêu: **hết im lặng**, không đụng hình học output)

1. **Task P0 (làm TRƯỚC mọi thứ, ~1-2 giờ)**: cấu hình logging handler cho logger `src.*` trong
   `src/api/main.py`. Cả tôi và Expert đều xếp đây trên cùng: mọi `logger.warning(exc_info=True)`
   ở các nhánh best-effort (gồm nhánh nuốt exception của `overlay_rotated_text()`,
   `job_orchestrator.py:533-539`) hiện **im lặng hoàn toàn** trong production. Bug #6 chỉ lộ ra vì
   QA mở file thủ công.
2. **Module mới `src/services/mineru_det_probe.py`** (đặt ở `services/` chứ không `preprocess/`
   vì đây là wrapper gọi tool ngoài qua subprocess — cùng loại với `*_runner.py`, chịu Protocol 5).
   - Chạy subprocess bằng interpreter MinerU (`~/.local/share/uv/tools/mineru/bin/python`), input
     là PNG từng trang render **200 DPI** bằng PyMuPDF, gọi
     `PytorchPaddleOCR(lang="en").ocr(img, det=True, rec=True)`.
   - Output JSON `[{page, poly_px, text, score}]`; lọc `score >= 0.8` và `|θ| >= 3.0°`.
   - Quy đổi toạ độ: poly ở px@200DPI → point nhân `72/200`. Góc trong hệ ảnh (y hướng xuống) có
     **dấu ngược** với `dir` của PyMuPDF — spike đo θ_ảnh ≈ -11° trùng dấu với `dir` = -11.0° ở
     fixture này, nhưng đây là chi tiết dễ sai dấu, **bắt buộc assert bằng fixture trong test**.
3. **Ghép với `middle.json`**: khớp theo **TEXT** (fuzzy, chuẩn hoá khoảng trắng/hoa thường) +
   ràng buộc khoảng cách trọng tâm < 0.5 chiều cao dòng. Góc của cả khối = **median** góc các dòng
   thành phần (median chứ không mean — spike cho thấy có poly nhiễu `-23.43°`, median miễn nhiễm).
4. **Ghi flag**: kết quả `(page_number, bbox, angle_deg)` → `LayoutQaFindingData` với lý do
   `"rotated_text_scan_unsupported"`, đúng trang/khối/góc. **θ KHÔNG đi vào `insert_text`** ở
   Phase 1.
5. **Golden fixture (Protocol 5 mục 3)**: lưu output spike hôm nay tại
   `tests/fixtures/mineru/det_probe_p67.json` — file này đã được sinh ra trong task này, Dev
   **copy vào repo, không viết tay lại**.
6. **Test bắt buộc (R6-02)**: assert **giá trị θ cụ thể** (median ≈ -11.0°, dung sai ±1.5°) và
   assert `layout_qa_findings` có **≥ 1 hàng** cho job `pdf_scan` fixture — không chấp nhận
   `assert_called()`. Thêm 1 smoke test gọi detector thật, được phép `skip` khi thiếu venv MinerU
   (R5-03).
7. **PRD**: ghi known-limitation — `pdf_scan` **phát hiện và FLAG** trang có chữ xoay để soát tay,
   nhưng **chưa** tái tạo góc; nguyên nhân gốc ở MinerU (6.13.1 S-M3).

**PHASE 2 — thiết kế đã chốt, KHÔNG implement bây giờ**

*Điều kiện kích hoạt*: job `pdf_scan` **thật trong production** đầu tiên sinh ra ≥ 1 finding
`"rotated_text_scan_unsupported"`. Khi điều kiện xảy ra, Tech Lead **re-scope rồi mới giao Dev**
(không tự động chuyển sang implement) — vì còn phải phân loại finding đó là khối nội dung thật
hay chỉ nhãn trang trí.

*Nội dung (ước ~1-1.5 ngày, đã tính cả 2 câu hỏi verify)*:
- **B2.1 (verify trước tiên)**: đo xem hình chữ nhật whiteout của cầu nối có sống sót qua babeldoc
  không (`[CHƯA VERIFY]` ở V3-4). Nếu **không** sống sót thì toàn bộ Phase 2 phải thiết kế lại —
  đây là gate, không phải chi tiết.
- **B2.2**: `searchable_pdf.py:113-125` — khi span có θ, thay `draw_rect` ngang bằng **tứ giác
  xoay** (`Shape.draw_polygon` + `finish(fill=(1,1,1))`) dựng từ poly gốc + padding 1.5pt. Vá
  đúng phần 5,5% hở đã đo ở V3-2.
- **B2.3**: `_insert_invisible_text()` nhận thêm `angle_deg`/`poly`; đặt baseline theo cạnh poly
  gốc; `insert_text(..., morph=(pivot, Matrix(-θ)))`; hình học tái dựng theo 6.13.2-b.
- **B2.4**: **KHÔNG** đụng `rotated_text_overlay.py` (module đó đã verify sống ở nhánh digital;
  chỉ cần input đúng) — điểm này tôi và Expert đồng ý hoàn toàn.
- **B2.5 (live E2E, R6-03)**: dựng lại fixture scan từ `tests/fixtures/babeldoc/rotated_text_p67_source.pdf`
  (raster hoá 200 DPI — cách QA đã mô tả trong `docs/test-report.md`; fixture scratchpad cũ của QA
  có thể đã bị dọn, tái tạo chứ đừng phụ thuộc vào nó), chạy **xuyên suốt** OCR → dịch → overlay,
  rồi **mở file output đọc nội dung thật**: assert ≥ 15 dòng có `dir` ≈ -11° và **không còn** dòng
  ngang nào chứa `"disaccharide"`.
- **B2.6**: nếu gặp khối chữ xoay ≈ ±90° thì áp dụng cảnh báo ở V2 (babeldoc **giữ** glyph và
  **vẽ** ô nền trắng ở dải góc đó) — cần bước xoá/che vùng babeldoc đã vẽ, effort tăng thêm.

**Vẫn giữ LOẠI**: phương án (B) flag mức job (flag fatigue), (C) tự xoay ảnh, (D) đổi engine sang
pdf2zh — lý do không đổi so với 6.13.3, Expert cũng đồng ý loại.

#### V7. Escalate lên PM/user (ngoài thẩm quyền Tech Lead)

1. **Câu hỏi sản phẩm (Expert nêu, tôi tán thành là đúng chỗ)**: **PM/user có kế hoạch nhận tài
   liệu PDF scan trong thời gian tới không?** Điều này quyết định Phase 2 là "thiết kế treo chờ
   điều kiện" (nếu chưa có kế hoạch — mặc định tôi chọn) hay nên đẩy lên làm ngay sau Phase 1
   (nếu sắp có sách scan thật). Dữ kiện để PM cân nhắc: cả **6 file đã upload đều là
   `pdf_digital`**, chưa có sách scan nào đi qua app; nhưng trong corpus digital cùng thể loại,
   ~4-5% số trang có khối chữ xoay có chủ đích (Expert quét: Le Cordon Bleu 19/418 trang, Figoni
   4 trang) ⇒ nếu một ấn bản **scan** cùng thể loại xuất hiện, kỳ vọng hợp lý là hiện tượng lặp
   lại. *Tôi đã sửa lại cách nói của mình ở 6.13.5-1*: gọi đây là "trường hợp giả định" là **quá
   nhẹ**; chính xác hơn là "chưa có bằng chứng trên nhánh scan, nhưng có bằng chứng gián tiếp
   mạnh từ bản digital song sinh".
2. **Ưu tiên task P0 logging**: xác nhận cho phép chen task này lên **trước** Phase 1 (~1-2 giờ,
   chạm `src/api/main.py`). Nó không sửa Bug #6 nhưng là điều kiện để bug kế tiếp không im lặng
   y hệt.

#### V8. Trạng thái verify (tổng hợp mục này)

| Nội dung | Trạng thái |
|---|---|
| Detector MinerU trả poly còn góc, sai số ≤ 0.40° trên 18 dòng | `verified` — spike Tech Lead tự chạy 2026-09-07 |
| Chi phí probe 0.36s/trang (det) — 2.0s/trang (det+rec), init 0.73s | `verified` (1 lần chạy, máy Dev, không kiểm soát tải) |
| babeldoc vứt glyph xoay deterministic, không phân biệt `render_mode` | `verified` — `il_creater.py:968-974, 390-398` (0.6.4) |
| Ô nền trắng chỉ sinh từ paragraph, đúng 1 nơi trong toàn package | `verified` — `paragraph_finder.py:117` + grep toàn package |
| Rủi ro "2 lớp chữ" với \|θ\| ngoài lân cận 0°/90° | `verified: KHÔNG xảy ra` (thay thế `[UNVERIFIED]` ở 6.13.4) |
| Rủi ro "2 lớp chữ" với θ ≈ ±90° | `verified: CÓ xảy ra` — phát hiện mới, chưa ai nêu trước đó |
| Cầu nối đã có sẵn whiteout ngang cho mọi span | `verified` — `searchable_pdf.py:113-125` |
| Vệt raster tiếng Anh hở 5,5% diện tích (dồn vào dòng rìa khối, tối đa 28,5%) | `verified` — mô phỏng công thức `ocr_utils.py:399-410` trên poly thật |
| Whiteout của cầu nối có sống sót qua babeldoc hay không | `[CHƯA VERIFY]` — **gate đầu tiên của Phase 2 (B2.1)** |
| Chữ ký `PytorchPaddleOCR` ở branch `dev`/version tương lai của MinerU | `[CHƯA VERIFY]` — khoá bằng golden fixture, verify lại khi nâng version (Protocol 5 mục 5) |

**Artifact của spike** (không commit vào repo trong task này): `render.py`, `det_spike.py`,
`coverage.py`, `p67_200dpi.png`, `det_probe_p67.json` tại scratchpad của session này. File
`det_probe_p67.json` là **golden fixture bắt buộc** của Phase 1 — Dev copy vào
`tests/fixtures/mineru/`, không viết tay lại (Protocol 5 mục 3).

---

### Bug #7 — List line-break regression tái phát + Bug #8 — Font quá nhỏ trong bảng (2026-09-07)

**Tác giả**: Tech Lead — phân tích/research, KHÔNG implement code.
**Triệu chứng user báo (v1.2.6, đã verify bằng mắt trên 4 ảnh so sánh song song)**:
- **Bug #7**: mục lục, danh sách "Questions for Review" đánh số 1–17, và bullet list lồng nhau
  trong box "Products Prepared"/"Materials and Equipment" bị dồn thành đoạn văn liền mạch; số thứ
  tự (`2.`, `3.`) và bullet (`■`/`▪`) nằm giữa dòng thay vì đầu dòng.
- **Bug #8**: cỡ chữ trong bảng "TABLE 4.2 — Texture Terms" không đồng đều và nhỏ bất thường so
  với bản gốc, ngay trong cùng 1 cột của cùng 1 bảng.

#### W0. Tóm tắt điều hướng

| | Bug #7 | Bug #8 |
|---|---|---|
| Có phải regression của fix cũ không? | **Không** — F1/F2/Q6 (`split_short_lines=True`, `factor=0.8`) vẫn đang chạy đúng; nó chỉ **không phủ được** 2 cơ chế mới tìm ra ở đây | Không — là biểu hiện cụ thể đầu tiên **đo được bằng số** của "tam nan" U5/U7-E1 |
| Nguyên nhân nằm ở đâu | 100% trong babeldoc 0.6.4 (`paragraph_finder.py`) | 100% trong babeldoc 0.6.4 (`typesetting.py`) |
| Code của team có sai gì không | Không | Không |
| Có flag CLI nào chữa được không | Không (đã hết tác dụng, xem W3) | **Không có flag nào tồn tại** (W5-3) |

#### W1. Nguồn xác thực (Protocol 5 / R5-01)

Toàn bộ claim dưới đây có nguồn trực tiếp. **Không có claim nào từ trí nhớ.**

**(a) Source thật babeldoc 0.6.4 đã cài** tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`
(`main.py:29` → `__version__ = "0.6.4"`).

**(b) Bằng chứng sống (Protocol 6 / R6-03) — chạy thật, $0 chi phí LLM**: chạy `babeldoc` 0.6.4
CLI thật với `--debug` trên 4 trang thật (`src` page 74–77) trích từ chính file production
`data/uploads/937b1d1c-…_Figoni, Paula - How baking works….pdf`, cùng flag production
(`--split-short-lines --short-line-split-factor 0.8`). Cố ý trỏ `--openai-base-url` tới
`http://127.0.0.1:1/v1` (không có server) → **0 token, 0 USD**, nhưng dump IL
`paragraph_finder.json` **vẫn được ghi vì nó nằm TRƯỚC bước dịch** (`high_level.py:973-977`).
Đây là cách quan sát trực tiếp cấu trúc đoạn mà babeldoc tạo ra, tách bạch hoàn toàn khỏi biến số
LLM. Artifact: `/tmp/bdprobe/wd/p74_77/paragraph_finder.json`.

**(c) Đo output production thật**: so `data/uploads/937b1d1c-…Figoni….pdf` (nguồn) với
`data/outputs/40cb4746-16ba-4c24-ab75-5b2cd9f83d0d/translated_vi.pdf` (job `40cb4746`, chạy
2026-09-06 14:00, **đúng bản v1.2.6 user đang báo lỗi**), bằng PyMuPDF 1.28.2.

| # | Claim | Nguồn |
|---|-------|-------|
| W-1 | `min_scale = 0.1` là **hằng số cứng trong thân hàm**, không phải tham số | `format/pdf/document_il/midend/typesetting.py:969` |
| W-2 | Vòng tìm scale: `while scale >= min_scale`, giảm `-0.05` khi `scale > 0.6`, `-0.1` khi thấp hơn | `typesetting.py:973, 1012-1015` |
| W-3 | **Không có CLI flag nào** và **không có field nào trong `TranslationConfig`** liên quan tới scale/min font size | `grep -n "scale" main.py` → 0 kết quả; `grep -n "scale" translation_config.py` → 0 kết quả |
| W-4 | Mỗi `PdfParagraph` (⇒ mỗi Ô BẢNG) có `optimal_scale` **riêng**, tìm độc lập từ 1.0 | `typesetting.py:895-914` (`preprocess_document`), `:1078-1094` (`_get_optimal_scale`) |
| W-5 | Chuẩn hoá theo mode **chỉ kéo XUỐNG**: `if paragraph.optimal_scale > mode_scale: = mode_scale`. **Không có nhánh nào nâng scale nhỏ lên** | `typesetting.py:919-936` |
| W-6 | `render_paragraph` dùng `optimal_scale` đã tính làm `initial_scale`, rồi lại chạy tiếp vòng giảm scale tới `min_scale` | `typesetting.py:1271-1281`, `:1096-1116` |
| W-7 | Gap giữa các dòng chỉ được ghi nhận khi collision count **`< 1`** (tức đúng bằng 0), **mâu thuẫn với chính docstring của hàm** ("less than 2") | `paragraph_finder.py:725` vs docstring `:657-661` |
| W-8 | Nếu `gaps` rỗng → **toàn bộ paragraph gộp thành MỘT `PdfLine` duy nhất** | `paragraph_finder.py:735-743` |
| W-9 | `process_independent_paragraphs` **bỏ qua hoàn toàn** paragraph có `len(pdf_paragraph_composition) <= 1` | `paragraph_finder.py:848-851` |
| W-10 | `is_bullet_point` chỉ xét `chars[0]` — ký tự ĐẦU TIÊN của dòng | `layout_helper.py:55-65`; call site `paragraph_finder.py:896-901` |
| W-11 | `BULLET_POINT_PATTERN` **CÓ** `■` (U+25A0) và `▪` (U+25AA); **KHÔNG CÓ** chữ số ASCII `0-9`, `-`, `–`, `*` | `layout_helper.py:48-50`; verify chạy thật bằng interpreter của chính babeldoc: `▪`→True, `■`→True, `1`→False, `2`→False, `-`→False |
| W-12 | Nhánh nhận diện mục lục chỉ kích hoạt khi có **≥ 20 dấu chấm liên tiếp** (dot leader) | `paragraph_finder.py:864-866` (`re.search(r"\.{20,}", prev_text)`) |
| W-13 | Cả 2 default hiện hành đúng như Q6 đã chốt: `babeldoc_split_short_lines = True`, `babeldoc_short_line_split_factor = 0.8` | `src/core/config.py:181, 188` |

#### W2. Bug #7 — bằng chứng sống: chuyện gì thực sự xảy ra

Đọc trực tiếp `paragraph_finder.json` (IL **trước khi dịch**, W1-b). Đây là bằng chứng mạnh nhất:
nó chứng minh cấu trúc đã sai **trước** khi LLM chạm vào, nên **loại trừ hoàn toàn** giả thuyết
"LLM gộp dòng" / "prompt sai" (RC-3 cũ) cho 2 ca này.

**Ca A — `QUESTIONS FOR REVIEW` (src page 74), numbered list 17 mục.**
IL page 0 sau `ParagraphFinder`, các paragraph `plain text`:

```
"1. Why is it that humans often "eat with their eyes"?"                      <- ĐÚNG (1 mục)
"2. What three things can happen…?  3. What makes limes green in color?"     <- GỘP 2 mục
"4. List the three main factors…  5. Explain why the appearance…"            <- GỘP 2 mục
"6. Explain and provide an example…  7. …"                                    <- GỘP
"8. Why is saliva necessary…  9. …  10. …  11. …  12. …  13. …  14. …  15. …" <- GỘP 8 mục (9 dòng)
"16. How does the perception of saltiness change…"                            <- ĐÚNG
"17. What is meant by mouthfeel?"                                             <- ĐÚNG
```

Paragraph "8.…15." có **9 `pdf_line` riêng biệt, tách dòng ĐÚNG** (đo được: `w=273.8 / 361.1 /
277.3 / 311.8 / 225.3 / 325.0 / 208.4 / 356.2 / 26.5`). Nghĩa là bước tách dòng chạy tốt; bước
**tách ĐOẠN** mới là chỗ hỏng. Với mỗi cặp dòng liền kề, điều kiện tách (`paragraph_finder.py:891-901`):
- nhánh bullet: `chars[0]` là `'8'`, `'9'`, `'1'` — chữ số ASCII → `is_bullet_point` **luôn False**
  (W-11). Nhánh này chết hoàn toàn với numbered list.
- nhánh hình học: `prev_width < median_width × 0.8`. Các dòng câu hỏi rộng **208–361pt**, tức là
  **chính chúng tạo ra median của trang** → điều kiện gần như không bao giờ đúng. Nó chỉ kích hoạt
  ở đúng chỗ dòng trước bị ngắn thật (dòng cuối bị wrap, `w=26.5` của `"usual?"`) — và đó chính
  là lý do mục 16 và 17 tách ra đúng còn 8–15 thì không.

Đo trên output production (W1-c), page 74:

| | Nguồn EN | Bản dịch VI (v1.2.6) |
|---|---:|---:|
| Số dòng **bắt đầu** bằng `N.` | **17** | **3** |
| Số lần `N.` nằm **giữa dòng** | 0 | **10** |

→ Khớp chính xác triệu chứng user mô tả.

**Ca B — box `PRODUCTS PREPARED` / `MATERIALS AND EQUIPMENT` (src page 77), bullet `■` (U+25A0).**
Đây là ca **QUAN TRỌNG NHẤT và HOÀN TOÀN MỚI**, vì `■` **NẰM TRONG** `BULLET_POINT_PATTERN`
(W-11) — tức là RC-2 cũ ("pattern thiếu marker") **KHÔNG giải thích được** ca này. Cơ chế thật:

IL cho thấy paragraph `"■ Sugar and acid  ■ Other (…)  ■ Your choice of additions"` có
**đúng 1 composition** — tức babeldoc coi cả 3 mục là **MỘT dòng duy nhất**. Đo toạ độ các ký tự
`■` trong "dòng" đó: `x=410.8 y=205.7`, `x=410.8 y=193.7`, `x=410.8 y=157.7` — **cùng x, khác y**,
tức là 3 mục **xếp chồng theo chiều dọc thật sự**, không phải nhiều cột.

Vì sao 3 dòng vật lý bị gộp thành 1 `PdfLine`? `_split_paragraph_into_lines`
(`paragraph_finder.py:652-776`) dùng phương pháp "line-threading": quét ngang theo y, chỗ nào có
ít ký tự cắt qua thì coi là khe giữa 2 dòng. **Docstring viết ngưỡng là "less than 2"
(`:657-661`) nhưng code implement là `count < 1` (`:725`) — tức đòi khe phải HOÀN TOÀN TRỐNG.**

Tự tính lại histogram từ chính dữ liệu IL đó (pure Python, cùng `step=0.25`, cùng `visual_bbox`
mà `_get_effective_y_bounds` dùng — `:600-609`):

```
y=204.24  count=21   [' ', ' ', ' ', ' ', 'S', 'u', …]   <- dòng "■ Sugar and acid"
y=203.99  count=1    ['g']        <- KHE giữa 2 dòng, nhưng bị 1 ký tự bắc cầu
…
y=202.24  count=1    ['g']
y=201.99  count=11   ['g', ' ', ' ', …]                  <- dòng kế tiếp
```

Khe giữa 2 dòng **có tồn tại**, nhưng bị bắc cầu bởi **đúng MỘT ký tự**: đuôi descender của chữ
`g` trong `"Sugar"`. Vì `1 < 1` là False → không ghi nhận gap nào → `gaps` rỗng → W-8 kích hoạt →
**cả box bullet gộp thành 1 `PdfLine`**. Hệ quả dây chuyền:

1. Paragraph còn đúng 1 composition → W-9: `process_independent_paragraphs` **bỏ qua không xét**.
2. Kể cả có xét, `is_bullet_point` chỉ nhìn `chars[0]` (W-10) → chỉ thấy `■` đầu tiên; `■` thứ 2,
   thứ 3 nằm giữa dòng, vô hình với thuật toán.
3. Cả 3 mục đi vào LLM như **một chuỗi**, quay về như một chuỗi, được typeset thành một đoạn chảy.

Đo trên output production, page 77: dòng bắt đầu bằng bullet **16 → 7**; bullet nằm giữa dòng
**1 → 10**. Ví dụ thật trong file giao cho user:
`"■ Không bổ sung (sản phẩm đối chứng) ■ Đường ■ Axit"` — **khớp chính xác** ảnh user gửi.

**Đây là một bug thật của babeldoc** (code lệch docstring của chính nó), không phải giới hạn thiết
kế. Một ký tự có đuôi (`g`, `y`, `p`, `q`, `j`) hoặc dấu tiếng Việt lấn vào dải giữa 2 dòng là đủ
phá vỡ việc tách dòng của **cả khối**. Điều này giải thích tính **thất thường** của lỗi: cùng một
kiểu box, chỗ hỏng chỗ không, phụ thuộc thuần vào việc dòng đó có chữ nào thò đuôi hay không.

**Ca C — trang mục lục (Contents).** Hai lớp bảo vệ đều không hoạt động:
- Nhánh mục lục chuyên dụng đòi **≥ 20 dấu chấm liên tiếp** (W-12). Mục lục của Figoni
  **không dùng dot leader** (chỉ `"Stage II: Baking 32"`) → nhánh này không bao giờ chạy.
- Nhánh hình học: mọi dòng mục lục đều ngắn như nhau ⇒ **chính chúng là median** ⇒
  `prev_width < 0.8 × median` hiếm khi đúng. Đây đúng là cơ chế "median bị kéo lệch" mà RC-1 đã
  cảnh báo, nhưng theo chiều **ngược lại** với dự đoán ban đầu: trang toàn dòng ngắn thì heuristic
  **mất tác dụng**, chứ không phải tách quá tay.
- Đo: page 7 (Contents), block **72 → 49**, dòng **88 → 81**.

#### W3. Vì sao fix F1/F2/Q6 đã ship KHÔNG chặn được (và không phải do đo sai)

Kết luận Q6 (đổi default sang `True`/`0.8`) **vẫn đúng với dữ liệu Q1–Q6** và **không nên revert**.
Vấn đề là **phạm vi**:

| | Trang 14 (đo ở Q1–Q6) | Trang 74 (bug này) |
|---|---|---|
| Bố cục list | 2 cột **hẹp**, mỗi mục 1 dòng ngắn | 1 cột **rộng**, mỗi mục 1–3 dòng gần full-width |
| Quan hệ với `median_width` | Dòng list **hẹp hơn** median toàn trang → heuristic kích hoạt | Dòng list **CHÍNH LÀ** median → heuristic im lặng |
| Kết quả `true08` | 26/35 mục đúng (tốt rõ rệt) | 3/17 mục đúng (gần như không tác dụng) |

`--split-short-lines` là **proxy hình học**, chỉ đúng khi list item tình cờ ngắn hơn văn xuôi xung
quanh. Nó **không phải** cơ chế nhận diện list. Q1–Q6 đo trên đúng chế độ mà proxy này hoạt động;
sách mới rơi vào chế độ ngược lại. **Không có giá trị `factor` nào chữa được ca này** — hạ factor
làm heuristic im lặng hơn; nâng factor > 1.0 sẽ tách vụn cả văn xuôi. Đây là **giới hạn cấu trúc**
của F2, không phải tham số chưa tune.

Tương tự, **Ca B nằm ngoài phạm vi của MỌI phân tích trước đó**: RC-1 (hình học) và RC-2 (pattern
thiếu marker) đều không đúng cho nó — bug nằm ở **tầng tách DÒNG**, một tầng thấp hơn cả hai.

#### W4. Bug #7 — quan hệ với F3 (spike đã thất bại) — KHÔNG lặp lại cách cũ

F3 (CHANGELOG "F3 — Spike verify … KHÔNG thành công", 2026-09-06) đã thử **chèn ký tự `•` vô hình
vào PDF NGUỒN** trước khi đưa cho babeldoc. Thất bại vì 2 lý do độc lập đã verify:
(1) thứ tự ký tự trong dòng **không sort theo x** (3 dòng `sort` bị comment out trong source thật)
→ ký tự chèn thêm không rơi vào vị trí `chars[0]`; (2) babeldoc **re-render toàn bộ**, không tôn
trọng `render_mode=3` → ký tự "vô hình" hiện ra thành rác trong output.

**Mọi đề xuất ở W6 dưới đây KHÔNG dùng lại cơ chế injection đó.** Chúng can thiệp **bên trong
process của babeldoc** (Hướng B, Architecture.md P3), nơi cả 2 lý do thất bại trên đều không tồn
tại: không chèn gì vào PDF nguồn, không phụ thuộc thứ tự extraction, không đụng bước render.

#### W5. Bug #8 — root cause (verified)

**Đo trên dữ liệu thật** (W1-c), trang `TABLE 4.2 — Texture Terms` (src page 75), phân bố cỡ chữ
(số span mỗi cỡ, đọc bằng PyMuPDF `get_text("dict")`):

| | Nguồn EN | Bản dịch VI (v1.2.6) |
|---|---|---|
| Phân bố cỡ chữ | `9.0pt × 101` span, `10.0 × 8`, `8.0 × 7` — **gần như đồng nhất** | `8.1 × 24`, `5.85 × 15`, `6.3 × 14`, `9.0 × 10`, `6.75 × 7`, `7.65 × 7`, `6.0 × 6`, `4.5 × 6`, `7.2 × 3`, `6.5 × 2`, `4.05 × 2`, `5.4 × 2` — **12 cỡ khác nhau** |
| Tỷ lệ so với 9.0pt gốc | 1.00 | **0.45 → 1.00** (`4.05/9.0 = 0.45`) |

Chuỗi nguyên nhân, mọi mắt xích đều có source:

1. **Mỗi ô bảng là một `PdfParagraph` riêng** → có `optimal_scale` riêng, tìm **độc lập** bằng
   `_find_optimal_scale_and_layout` khởi tạo từ `1.0` (W-4).
2. Vòng lặp giảm scale cho tới `min_scale = **0.1**` — **hằng số cứng trong thân hàm**, không phải
   tham số, không có flag CLI, không có field config (W-1, W-2, W-3).
3. Bước chuẩn hoá theo mode (`preprocess_document`) **chỉ kéo XUỐNG những paragraph cao hơn mode,
   không bao giờ nâng những paragraph thấp hơn mode lên** (W-5). Nghĩa là nó **áp một trần chung**
   nhưng **bảo toàn nguyên vẹn mọi sự chênh lệch phía dưới trần**. Đây chính là lý do bảng trông
   "vỡ": mode ở đây là `0.9` (⇒ `8.1pt`), các ô ngắn ("Mềm", "Dai") nằm ở trần; các ô dài
   ("Có thịt quả, ẩm…") tụt tự do xuống tới `0.45`.
4. Tiếng Việt dài hơn tiếng Anh ~20–40% ⇒ ô nào text dài hơn thì tụt sâu hơn. Chênh lệch độ dài
   giữa các ô trong cùng một cột **được khuếch đại thành chênh lệch cỡ chữ nhìn thấy được**.

**Đây chính là "tam nan" U5 đã mô tả** (bóp font / giãn khung / cắt text), lần đầu **đo được bằng
số** thay vì mô tả định tính. Với ô bảng, babeldoc gần như luôn chọn "bóp font": nhánh giãn khung
(`typesetting.py:1017-1062`) chỉ chạy khi `scale < 0.7`, và trong bảng thì
`get_max_bottom_space`/`get_max_right_space` gần như không có chỗ trống để giãn (ô bảng bị bao
quanh bởi ô khác) → rơi thẳng về nhánh bóp font tới đáy `0.1`.

**Chính sách U7-E1 ("bóp tối đa 70% rồi FLAG") CHƯA từng được implement ở đâu** — xác nhận bằng
`grep -rn "min_scale\|0\.7" src/` → không có chỗ nào áp sàn scale. U7-E1 tới nay vẫn ở trạng thái
"escalate cho PM/user, chưa chốt". **Bug #8 là bằng chứng thực nghiệm đầu tiên cho thấy nó cần
được chốt.**

#### W6. Đề xuất SƠ BỘ (Tech Lead — chưa chốt, chờ Domain Expert phản biện + PM duyệt)

##### Bug #7

**Đường đi khả thi duy nhất còn lại là Hướng B-2 (wrapper in-process)** đã đánh giá ở P3 và đã
verify sống cơ chế patch (P3/B-1: patch `BULLET_POINT_PATTERN` ở module global CÓ tác dụng lên
`paragraph_finder`). Hai patch, theo thứ tự lợi ích/rủi ro:

- **B-2a (ưu tiên cao nhất — rẻ, rủi ro thấp, sửa đúng một bug thật của babeldoc)**: nới ngưỡng
  gap của line-threading từ `count < 1` về `count < 2` — **đúng bằng con số docstring của chính
  babeldoc tuyên bố** (W-7). Đây không phải "chế thêm heuristic", mà là làm cho code khớp với đặc
  tả của chính nó. Sửa được **Ca B** (bullet `■` bị gộp) ở tận gốc, và có khả năng cải thiện cả
  **Ca C** (mục lục). Rủi ro cần đo: ngưỡng 2 có thể tách nhầm ở khối chữ dày đặc/nhiều dấu — phải
  A/B trên nhiều trang trước khi chốt.
  ⚠️ **`[UNVERIFIED]`**: chưa đo tác động của `count < 2` trên toàn tài liệu. Bắt buộc spike theo
  R5-02 trước khi implement đầy đủ.
- **B-2b — bọc `ParagraphFinder.process`**: chạy `process()` gốc trước, rồi duyệt IL và tách
  paragraph tại các **dòng** mở đầu bằng marker numbered (`1.`, `2.`, `a)`). Ở tầng này ta thấy
  **toàn bộ text của dòng**, không chỉ `chars[0]` (W-10) — nên áp được heuristic chống
  false-positive thật (marker phải tăng dần; loại `"2 cups flour"`; loại dòng mục lục). Sửa được
  **Ca A**. Code tách có sẵn để tái dùng nguyên xi (`paragraph_finder.py:868-925`), không phải
  chép lại logic typeset.
- **KHÔNG đề xuất**: (a) tiếp tục tune `short_line_split_factor` — đã chứng minh là ngõ cụt cấu
  trúc (W3); (b) nới `BULLET_POINT_PATTERN` thêm `0-9` (B-1 cũ) — vô dụng cho Ca A vì `chars[0]`
  chỉ 1 ký tự, không phân biệt được `"1. Trộn bột"` với `"180°C…"`, mà B-2b làm được đúng việc đó
  với cùng chi phí wrapper; (c) mọi biến thể của F3 (injection vào PDF nguồn) — đã thất bại, xem W4.

**Điều kiện bắt buộc kèm theo** (giữ nguyên P5): pin cứng `babeldoc.__version__ == "0.6.4"`, raise
ngay nếu lệch; smoke test gọi thật; assert **cấu trúc output** (đếm dòng bắt đầu bằng marker), tuyệt
đối không assert sự có mặt của flag trong `args` (bài học N4).

##### Bug #8

**Đề xuất: ĐÃ ĐỦ CƠ SỞ để chốt U7-E1, nhưng KHÔNG nên implement như "sàn 0.7 cứng".** Lý do: `0.7`
trong U7-E1 là con số **đề xuất chưa từng đo**. Số đo thật ở W5 cho thấy mode của trang bảng này là
`0.9` và đuôi kéo tới `0.45`. Một sàn cứng `0.7` sẽ biến mọi ô hiện ở `0.45–0.65` thành **tràn chữ**
(babeldoc cố ý vẽ tràn khi hết cách — T-04) — tức là **đổi một lỗi thẩm mỹ lấy một lỗi chồng chữ**,
đúng nhánh (2)/(3) của tam nan U5. Đề xuất 3 bước, theo thứ tự:

1. **Đo trước, chốt số sau** (P0, rẻ nhất): dùng chính phương pháp W1-c chạy trên ≥ 5 trang bảng
   thật, dựng **histogram scale thực tế**. Sàn phải chọn từ dữ liệu, không từ con số tròn.
2. **Ưu tiên "thu hẹp khoảng cách" hơn "áp sàn tuyệt đối"**: cái user thực sự phàn nàn là
   **KHÔNG ĐỒNG ĐỀU trong cùng 1 bảng**, không phải "chữ nhỏ" nói chung. Vì vậy đề xuất **đảo ngược
   chiều chuẩn hoá của W-5**: thay vì chỉ kéo xuống mode, **kéo mọi paragraph trong cùng một vùng
   layout `table` về CÙNG một scale** (= min scale của vùng đó). Bảng sẽ nhỏ đều thay vì vỡ — đây
   là thay đổi rẻ hơn, rủi ro thấp hơn nhiều so với áp sàn, vì **không tạo thêm tràn chữ nào**
   (mọi ô chỉ nhỏ đi hoặc giữ nguyên, không ô nào to lên). Cùng cơ chế wrapper B-2 (patch
   `preprocess_document`), không phát sinh hạ tầng mới.
3. **Sàn + FLAG (U7-E1 đúng nghĩa)** chỉ làm sau, và phải đi kèm cơ chế **flag vào
   `layout_qa_findings`** — sàn mà không flag thì chỉ là đổi lỗi im lặng này lấy lỗi im lặng khác
   (đúng bài học Bug #6: `scan_rotated_lines()` trả 0 block và **không flag gì cả**).

⚠️ **`[UNVERIFIED]`**: cả bước 2 lẫn bước 3 đều chưa spike. Phải verify theo R5-02 trước khi
implement.

#### W7. Trạng thái verify (tổng hợp mục này)

| Claim | Trạng thái |
|-------|-----------|
| Bug #7 Ca A — numbered list gộp do `chars[0]` là chữ số + median không lệch | ✅ **Verified** — IL dump thật (W1-b) + `paragraph_finder.py:891-901` + đo output production 17→3 |
| Bug #7 Ca B — `■` bị gộp do `count < 1` bắc cầu bởi descender `g` | ✅ **Verified** — IL dump thật, tự tính lại histogram, `paragraph_finder.py:725, 735-743, 848-851` |
| Bug #7 Ca C — mục lục không có dot leader nên nhánh TOC không chạy | ✅ **Verified** — `paragraph_finder.py:864-866` + đo page 7 (72→49 block) |
| Bug #7 KHÔNG do LLM/prompt gộp dòng | ✅ **Verified** — cấu trúc đã sai trong IL **trước** bước dịch, 0 token LLM |
| Bug #7 KHÔNG do code của team | ✅ **Verified** — default `True`/`0.8` đúng như Q6 chốt (`config.py:181,188`), flag truyền đúng (`babeldoc_runner.py:308-318`) |
| Bug #8 — `min_scale = 0.1` hardcode, không có flag/config nào | ✅ **Verified** — `typesetting.py:969` + grep 0 kết quả trên `main.py`/`translation_config.py` |
| Bug #8 — chuẩn hoá mode chỉ kéo xuống, không nâng lên | ✅ **Verified** — `typesetting.py:919-936` |
| Bug #8 — biểu hiện thật: 12 cỡ chữ, scale 0.45–1.0 trong 1 bảng | ✅ **Verified** — đo output production page 75 |
| U7-E1 (sàn 0.7) chưa từng được implement | ✅ **Verified** — `grep -rn "min_scale" src/` → 0 kết quả |
| B-2a (`count < 2`) không gây tách nhầm trên tài liệu thật | ⚠️ **`[UNVERIFIED]`** — spike bắt buộc (R5-02) |
| B-2b heuristic marker tăng dần không false-positive | ⚠️ **`[UNVERIFIED]`** tại thời điểm viết mục này — bảng này (W7) đã bị section "Bug #7/#8 — Final Decision…" phía dưới thay thế; xem bảng X10 (đã ✅ Verified sau bước 7.2, 2026-09-07) cho trạng thái mới nhất |
| Đồng bộ scale theo vùng `table` không gây tràn chữ | ⚠️ **`[UNVERIFIED]`** — spike bắt buộc (R5-02) |
| Con số sàn tối ưu (0.7 hay khác) | ⚠️ **`[UNVERIFIED]`** — phải đo histogram trước khi chốt |

**Artifact spike** (không commit trong task này, tái tạo được bằng lệnh ghi ở W1-b):
`/tmp/bdprobe/wd/p74_77/paragraph_finder.json` — dump IL thật, **golden file bắt buộc** nếu PM
duyệt đi tiếp: Dev copy vào `tests/fixtures/babeldoc/`, KHÔNG viết tay lại (Protocol 5 mục 3).

**Trạng thái**: Phân tích/research xong — **không có code nào được viết**. Chờ Domain Expert phản
biện rồi PM/user quyết định.

---

### Bug #7/#8 — Final Decision sau phản biện Domain Expert (2026-09-07)

Section này **thay thế phần đề xuất** ở mục W6/W7 của section trước (W0–W7 giữ nguyên làm hồ sơ
điều tra). Nơi nào mâu thuẫn, **section này thắng**.

#### X0. Phán quyết một dòng

Domain Expert **đúng ở cả 4 điểm phản biện chính**. Tôi đã tự verify độc lập bằng cách viết lại
thuật toán từ source (không dùng script của Expert) và tái tạo **chính xác** con số Expert báo cáo.
Hai đề xuất của tôi ở W6/W7 bị **rút lại**: B-2a (`count < 2`) và "đồng bộ scale toàn bảng về MIN".

#### X1. Bảo toàn bằng chứng (làm trước tiên)

Golden IL dump đã được đưa vào repo, nén gzip để giảm 17MB → 613KB:

`tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz`

Nguồn: `/tmp/bdprobe/wd/p74_77/paragraph_finder.json`, sinh bởi babeldoc 0.6.4 `--debug` trên
Figoni p74–77 (cách tái tạo: W1-b của section trước). Mọi số liệu dưới đây tái tạo được **từ chính
file này** (Protocol 5 mục 3 — golden file, không phải mock viết tay). Đọc bằng
`gzip.open(path, "rt")`.

#### X2. Tự verify độc lập — kết quả

**Phương pháp**: tôi viết lại `_split_paragraph_into_lines` bằng numpy từ source đã cài
(`step=0.25`, cùng công thức difference-array của `_compute_collision_counts_histogram`), chạy trên
golden dump. Ground truth = cluster baseline `char.box.y` (dung sai 3pt) trên ký tự **có mực**
(loại space). Loại "space dummy" (`pdf_character_id is None`, do `add_space_dummy_chars` chèn SAU
bước thread) khỏi tập ký tự.

**Fidelity của reimplementation**: tái tạo đúng số `pdf_line` có thật trong dump ở mức
**162/163 paragraph** — đủ để tin rằng tôi đang đo đúng thuật toán thật, không phải đo mô hình của
chính mình.

| Biến thể | Đúng / 163 | Under-split còn lại | Hồi quy |
|---|---|---|---|
| Hiện tại (`count<1`, tính cả space) | **147** | 16 | — |
| B-2a của tôi (`count<2`) | **149** | 14 | 0 (trên mẫu này) |
| Expert (`count<1`, **loại ký tự trắng khỏi phép đếm**) | **161** | 2 | 0 |

→ **Cả ba con số 147 / 149 / 161 trên 163 khớp tuyệt đối với báo cáo của Expert.** Đây là replication
độc lập (tôi viết script riêng từ source + mô tả phương pháp), không phải chạy lại script của Expert.

**Chi tiết 16 paragraph hiện đang sai** (in ra từ script):

| Trang | GT | Hiện tại | `count<2` | Loại-space | Nội dung |
|---|---|---|---|---|---|
| p0 | 2 | 1 | 1 | 1 | `)60` — nhãn `abandon` (số trang) |
| p0 | 3 | 1 | **1** | **3** | `1. Explain what is meant by…` |
| p0 | 3 | 1 | **1** | **3** | `2. Explain what is meant by…` |
| p1 | 7 | 2 | 2 | **7** | `Using regular (water-soluble) blue food coloring…` |
| p1 | 5 | 1 | 2 | **5** | `Compare the texture of properly stored…` |
| p1 | 7 | 1 | 1 | **7** | `Compare the texture of two products…` |
| p2 | 2 | 1 | 1 | 1 | `)62` — nhãn `abandon` |
| p2 | 5 | 1 | 1 | **5** | `Apple juice is a relatively mild-tasting juice…` |
| p2 | 3 | 1 | 1 | **3** | `Work slowly through this exercise…` |
| p2 | 3 | 1 | 1 | **3** | `While diluted apple juice is used…` |
| p2 | 2 | 1 | 2 | 2 | `■ To identify and describe differences…` |
| p2 | 6 | 1 | **1** | **6** | `■ To demonstrate how sugar affects…` |
| p2 | 5 | 1 | **3** | **5** | `■ Sugar and acid ■ Other…` |
| p2 | 3 | 1 | **2** | **3** | `■ No additions (control product) ■ Sugar ■ Acid` |
| p2 | 2 | 1 | 2 | 2 | `■ Tannin powder ■ Caffeine` |
| p2 | 2 | 1 | **1** | **2** | `■ Apple juice, 6 quarts (liters) or more…` |

Ba kết luận rút ra, **tất cả đều xác nhận Expert**:

1. **Trên 6 paragraph bullet `■` — bằng chứng chính của tôi cho Ca B — `count<2` chỉ sửa đúng 2/6**
   (2 ca cải thiện một phần nhưng vẫn sai, 1 ca không đổi gì). Cách loại ký tự trắng sửa **6/6**.
2. **Ca A KHÔNG chỉ là lỗi tầng ghép đoạn.** Hai mục numbered-list `1. Explain…` / `2. Explain…`
   bị nén từ 3 dòng thật xuống **1 `PdfLine` duy nhất ngay ở tầng tách dòng**. `count<2` **không
   sửa được** (vẫn =1); loại ký tự trắng sửa đúng =3. Đây là điểm mô tả sai của tôi ở W2, và nó
   tạo ra một **dependency** mà tôi chưa nêu: **B-2b bắt buộc phải chạy SAU khi tầng dòng được sửa**,
   nếu không nó chỉ nhìn thấy một dòng gộp `"1. Explain… 2. Explain…"` và không có gì để tách.
3. **Phạm vi lỗi rộng hơn hẳn "bullet lồng nhau"**: 6 paragraph văn xuôi bình thường (không list,
   không bullet) cũng đang bị nén sai — nặng nhất là 7 dòng → 1 dòng. Mô tả của tôi ở W2 giới hạn
   lỗi vào list là **hẹp hơn thực tế**.

2 ca còn sai sau fix Expert đều là `)60` / `)62` nhãn `abandon` (page furniture, không đi vào nội
dung dịch) — **không đáng xử lý**.

##### X2-b. Rủi ro hồi quy của `count<2` — tôi tự dựng ca tổng hợp và XÁC NHẬN có thật

Expert cảnh báo `count<2` sẽ gộp sai mọi dòng chỉ có **đúng 1 ký tự** (ô bảng số hẹp, chữ cái đơn,
số trang 1 chữ số) vì dòng đó không bao giờ đạt count ≥ 2. Mẫu 4 trang không tình cờ có ca này nên
tôi chưa đo được. Tôi dựng ca tổng hợp bằng chính reimplementation:

| Ca | GT | `count<1` | `count<2` | Loại-space |
|---|---|---|---|---|
| 1 chữ số đứng riêng 1 dòng + 1 dòng văn xuôi bên dưới | 2 | 2 | **1 ✗** | 2 |
| 2 dòng, mỗi dòng đúng 1 chữ số (cột số hẹp) | 2 | 2 | **1 ✗** | 2 |

→ **Hồi quy có thật, và rơi đúng vào bảng số** — chính là loại nội dung Bug #8 đang xử lý. Đủ để
loại bỏ B-2a hoàn toàn, độc lập với việc nó kém hiệu quả hơn.

##### X2-c. Verify các claim về source (Protocol 5 R5-01)

Nguồn: babeldoc **0.6.4** đã cài tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/`
— cộng thêm fetch upstream `main` qua raw.githubusercontent.com để đối chiếu.

| Claim của Expert | Kết quả tự verify |
|---|---|
| `_get_effective_y_bounds` có dead code sau `return` | ✅ **Đúng** — `paragraph_finder.py:608-613`: `return visual_box.y, visual_box.y2` rồi mới tới nhánh IoU/`pdf_box`, **không bao giờ chạy**; docstring `:601-606` mô tả đúng cái nhánh chết đó. Upstream `main` **y hệt**. |
| Lời gọi `_sort_characters_in_lines` bị comment out | ✅ **Đúng** — hàm tồn tại `:1032`, lời gọi `:305` là `# self._sort_characters_in_lines(page)`. Upstream `main` **y hệt**. **Tôi phát hiện thêm**: 3 chỗ sort theo x **ngay trong** `_split_paragraph_into_lines` cũng bị comment (`:696`, `:738`, `:772`) — tức thứ tự ký tự trong dòng **hoàn toàn không được đảm bảo**, mạnh hơn cả cảnh báo của Expert. |
| Docstring "less than 2" vs code `count < 1` | ✅ **Đúng** — docstring `:660-662`, code `:727`. Upstream `main` **y hệt** (chưa ai sửa). |
| Ký tự space giữ `visual_bbox` cao bằng font_size | ✅ **Đúng** — `il_creater.py:1048-1054` gán `visual_bbox` mặc định = `char.bbox` dịch theo descent; `:1092-1108` chỉ **thay** bằng bbox glyph khi `volume > 1`. Space không có glyph → `volume` = 0 → **giữ nguyên box cao bằng cả font_size**. |
| `scale < 0.7` mới kích hoạt giãn khung | ✅ **Đúng** — `typesetting.py:1017`. |
| Sau khi giãn khung thành công vẫn giữ scale thấp | ✅ **Đúng, và tệ hơn Expert mô tả** — `:1036-1037` và `:1055-1056` `continue` giữ scale hiện tại; nhưng `:1060-1062` lại **reset `scale = 1.0` đúng khi giãn khung THẤT BẠI**. Logic **bị đảo ngược**: thành công (khung to hơn, đáng thử lại từ 1.0) thì giữ scale thấp; thất bại (khung không đổi) thì reset về 1.0. |
| mode-scale tính theo `unit_count` toàn tài liệu | ✅ **Đúng, và mạnh hơn "side effect"** — `:892-935`: `all_paragraphs`/`all_scales` tích luỹ **qua mọi trang**, mỗi paragraph đóng góp `unit_count` phiếu; sau đó **mọi** paragraph có `optimal_scale > mode` bị **kẹp xuống bằng mode**. Một bảng nhiều ô nhỏ **kéo tụt văn xuôi toàn tài liệu**, không chỉ cùng trang. |

**Về "docstring nói 2 nên chủ đích ban đầu là 2"**: tôi **rút lại** kết luận này ở W2. Expert đúng —
với `_get_effective_y_bounds` có dead code và 4 lời gọi sort bị comment, đây rõ ràng là code thử
nghiệm dở dang; không thể suy ra chủ đích từ docstring, và không có git blame để chốt. Nó là **dấu
hiệu** đáng nghi, **không phải bằng chứng**.

##### X2-d. Verify claim Bug #8

Đo trên `page_number == 1` của golden dump (trang chứa TABLE 4.2):

| Claim | Kết quả |
|---|---|
| 77 ô bảng mang nhãn `fallback_line`, **không** ô nào nhãn `table` | ✅ **Đúng chính xác** — lọc paragraph có tâm nằm trong box layout `table`: được **đúng 77** paragraph, tập nhãn = `{'fallback_line'}`. **Spec W6 của tôi ("gom các ô theo vùng layout `table`" hiểu là gom theo nhãn paragraph) sẽ gom được 0 ô.** |
| Vẫn có căn cứ hình học để gom nhóm | ✅ **Có** — `page.page_layout` **có** entry `class_name == "table"`, `id=1`, box `(87.0, 252.0)-(583.0, 741.0)`. Phải gom theo **chứa trong box này**, không theo `paragraph.layout_label`. |
| 3 cụm cột x ≈ 96-97 / 241-242 / 432-433 | ✅ **Đúng** — cluster: x~96.2–97.3 (n=14), x~241.1–242.3 (n=31), x~431.8–433.3 (n=32). |
| Cột 2/3 còn thừa ~70–75pt ngang | ✅ **Đúng về hướng, số còn LỚN HƠN** — slack tới ô kế bên cùng hàng (hoặc mép bảng): median **cột 2 = 109.7pt**, **cột 3 = 98.1pt**. |
| Cột 1 "gần như dùng hết chỗ ngang" | ⚠️ **Chỉ đúng một phần** — median slack cột 1 = **51.8pt**, min toàn bảng = 12.2pt (nằm ở cột 1). Cột 1 chật **hơn** cột 2/3 nhưng **không hết chỗ**. Kỳ vọng cải thiện của (8a) nên bao gồm cả cột 1, chỉ là biên độ nhỏ hơn. |

**Phát hiện riêng của tôi — chặn một sai lầm trong roadmap đo đạc**: `paragraph.scale` và
`optimal_scale` là `None` ở **mọi** IL dump (`paragraph_finder`, `layout_generator`,
`styles_and_formulas`, `il_translated`, `add_debug_information` — kiểm tra cả 1230 paragraph).
Typesetting tính scale **trong bộ nhớ** rồi ghi thẳng ra PDF, **không persist vào IL**. Con số
`0.45` ở W6 đến từ **đo cỡ chữ trong PDF output production**, không phải từ dump. ⇒ **Bước đo
histogram của Bug #8 KHÔNG thể làm từ IL dump**; phải hoặc (i) đo font size trong PDF output bằng
pymupdf, hoặc (ii) instrument `typesetting.py` để log `optimal_scale`. Nếu không ghi rõ, Dev sẽ mất
thời gian tìm một field không tồn tại.

#### X3. Cơ chế thật của Bug #7 (thay thế mô tả ở W2)

Mô tả cũ ở W2 — "ký tự đuôi `g` trong *Sugar* bắc cầu qua khe giữa 2 dòng" — **đúng hiện tượng
quan sát được nhưng sai nguyên nhân gốc**. Cơ chế thật:

1. Ký tự **khoảng trắng** không có glyph ⇒ `il_creater.py` giữ `visual_bbox` mặc định **cao đúng
   bằng `font_size`** (`:1092-1108`, chỉ thay khi `volume > 1`).
2. Với font 10.0pt và pitch dòng 12pt, mỗi space **lấp 10/12pt** chiều cao ⇒ khe hở thật giữa 2
   dòng chỉ còn **~2pt**.
3. Bất kỳ ký tự nào có descender (`g`, `y`, `p`, `q`, `j` — và **dấu tiếng Việt**) chọc vào 2pt còn
   lại là đủ để `count` không bao giờ về 0 ⇒ `gaps` rỗng ⇒ **cả paragraph gộp thành 1 `PdfLine`**.

Chữ `g` trong "Sugar" chỉ là **giọt nước tràn ly**. Đây là lý do đổi ngưỡng sang `<2` chỉ sửa được
những dòng có **đúng một** ký tự descender — phần lớn câu tiếng Anh có nhiều hơn một, và tiếng Việt
thì gần như luôn có dấu.

**Hệ quả cho fix**: loại ký tự trắng khỏi **phép đếm va chạm** trả lại khe hở thật ~10pt giữa các
dòng. Ký tự trắng **vẫn được gán vào đúng dòng của nó** theo tâm y như thường (không mất space),
chỉ là không được bỏ phiếu vào việc "có khe hở hay không". Vì thế nó **không** mang rủi ro dòng-1-ký-tự
như `count<2`.

#### X4. Điểm tôi bổ sung thêm ngoài phản biện của Expert

**X4-1. Vector kỹ thuật để áp patch — chưa ai nêu, và nó quyết định effort.**
App gọi babeldoc **qua subprocess CLI** (`BabeldocRunner(executable="babeldoc")`,
`asyncio.create_subprocess_exec`), **không** import babeldoc trong process của app; babeldoc cài
bằng `uv tool` ở venv **riêng**, không phải dependency trong `pyproject.toml`. ⇒ **Monkey-patch
thuần Python trong code app sẽ KHÔNG có tác dụng.** Ba vector khả thi, theo thứ tự ưu tiên:

- **(V1) `sitecustomize.py` shim qua `PYTHONPATH`** (khuyến nghị): đặt một thư mục shim trong repo,
  truyền `PYTHONPATH=<shim_dir>` vào `env` của subprocess. CPython tự import `sitecustomize` lúc
  khởi động; shim cài một `meta_path` hook, đợi module `…midend.paragraph_finder` được import xong
  rồi thay `_split_paragraph_into_lines`. Không đụng file trong venv của tool, gỡ ra chỉ cần bỏ
  biến môi trường, và **tự vô hiệu hoá an toàn** nếu đường dẫn module đổi ở version sau.
- **(V2) Thêm `babeldoc` thành dependency của app** rồi chạy `python -m <wrapper>` thay vì binary
  `babeldoc`. Sạch hơn về mặt kiểm soát version, nhưng kéo toàn bộ cây phụ thuộc nặng của babeldoc
  vào app venv — cần cân nhắc riêng, **không làm trong scope này**.
- **(V3) Vendor/patch file trong venv của tool** — **loại bỏ**: mất khi `uv tool upgrade`, không tái
  lập được trên máy khác, vi phạm tinh thần Protocol 5 (bind cứng vào một bản cài cục bộ).

⇒ Chốt **V1**. Shim phải **fail-safe**: nếu không patch được (đổi tên hàm/module ở version khác),
**log cảnh báo và chạy tiếp với hành vi gốc**, tuyệt đối không crash job. Và phải có một
**assertion version**: shim chỉ áp dụng khi `babeldoc.__version__ == "0.6.4"`; version khác → log
cảnh báo, không patch (Protocol 5 mục 5: đổi version ⇒ verify lại contract).

**X4-2. Không đồng ý hoàn toàn về "cột 1 hết chỗ"** — xem X2-d, median slack cột 1 vẫn 51.8pt.

**X4-3. Bổ sung ràng buộc đo cho Bug #8** — scale không có trong IL dump (X2-d). Bước 1 của roadmap
Bug #8 phải nêu rõ công cụ đo, nếu không sẽ tắc.

**X4-4. Về yêu cầu tự sort theo x của Expert cho B-2b**: đồng ý, và **mạnh hơn** — không chỉ
`_sort_characters_in_lines` ở `:305` bị tắt, mà cả 3 lời gọi sort **bên trong** chính
`_split_paragraph_into_lines` (`:696`, `:738`, `:772`) cũng bị comment. Wrapper B-2b **bắt buộc**
tự sort theo `visual_bbox.box.x` trước khi ghép chuỗi tìm marker. Ghi vào spec trước khi giao Dev.

#### X5. QUYẾT ĐỊNH CUỐI — Bug #7

**D7-1. CHẤP NHẬN fix của Expert; RÚT LẠI B-2a.**
Sửa: **loại ký tự trắng khỏi phép đếm va chạm**, **giữ nguyên ngưỡng `count < 1`**. Ký tự trắng vẫn
được phân vào dòng theo tâm y như cũ. Không đổi ngưỡng — `count<2` đã được chứng minh (X2-b) là hồi
quy thật với dòng 1 ký tự trong bảng số.

**D7-2. Vector: V1 (sitecustomize shim qua `PYTHONPATH`)**, fail-safe + gate version `0.6.4` (X4-1).

**D7-3. Thứ tự bắt buộc — có dependency, không được đảo:**

| Bước | Nội dung | Gate trước khi qua bước sau |
|---|---|---|
| **7.0** | Spike: shim V1 patch được thật, `--debug` trên p74–77 sinh IL mới | Số `pdf_line` trong IL mới khớp ground truth **≥ 161/163**; job chạy xanh; shim tắt được bằng env |
| **7.1** | Ship fix tầng dòng (D7-1) | Chạy lại **cả 4 trang lần này VÀ 7 trang của nghiên cứu Q2**; đọc **nội dung** PDF output (R6-03), không tin `status` |
| **7.2** | Ca A — tách numbered-list theo marker tăng dần (B-2b) | **Chỉ bắt đầu sau khi 7.1 xanh.** Wrapper tự sort theo x (X4-4). Phải loại được false-positive kiểu `"2 cups"` trong công thức |
| **7.3** | Ca C — mục lục: **chưa code gì**, chỉ **đo lại** sau 7.1 | Đọc nội dung thật trang Contents; đo **cả 2 chiều**: cấu trúc tốt lên **và** tỷ lệ cắt nhầm caption (RC-1) — ✅ **Đã đo (2026-09-07)**, xem CHANGELOG.md "bước 7.3 (Ca C, mục lục)". Kết quả: (1) cấu trúc **KHÔNG cải thiện** — Ca C vẫn còn nguyên (7.1/7.2 không chạm tới, marker của B-2b ở đầu dòng, TOC có số trang ở cuối dòng); verify sống qua dịch thật cho thấy tác hại rõ (nhiều mục TOC bị trộn lẫn thành 1 câu chạy dài). (2) RC-1: **không hồi quy**, có 1 phát hiện MỚI ngoài Ca A/B/C — 7.1 vô tình sửa luôn lỗi heading 2 dòng bị đảo lộn ký tự chéo nhau (cùng root cause X3). **Ca C cần thiết kế fix riêng (heuristic theo marker cuối dòng, không phải B-2b) — chưa làm, chờ PM/user quyết định.** |

**D7-4. Effort ước lượng**: 7.0 + 7.1 ≈ **0.5–1 ngày** (logic lõi ~15 dòng; phần lớn công là shim
+ test lineage + đo 11 trang). 7.2 ≈ **1–1.5 ngày** (heuristic marker + chống false-positive).
7.3 ≈ **2–3 giờ** (thuần đo).

**D7-5. Test bắt buộc (Protocol 6 R6-02)**: test không được chỉ assert "đã gọi". Phải có test chạy
hàm tách dòng đã patch **trên golden fixture** `paragraph_finder_p74_77_dump.json.gz` và assert
**số dòng cụ thể** của các paragraph đã liệt kê ở bảng X2 (ví dụ `1. Explain…` phải ra **3** dòng,
`■ To demonstrate…` phải ra **6**). Bảng X2 chính là **oracle** cho test này.

#### X6. QUYẾT ĐỊNH CUỐI — Bug #8

**D8-1. RÚT LẠI hoàn toàn đề xuất "đồng bộ scale toàn vùng bảng về MIN".**
Lập luận của tôi ở W6 ("không tạo tràn chữ mới vì không ô nào bị phóng to") đúng hình học nhưng sai
mục tiêu: MIN của TABLE 4.2 là **0.45** ⇒ **cả 77 ô xuống 4.05pt**, không đọc được. Nó biến một vấn
đề cục bộ (vài ô xấu) thành hỏng **toàn bảng** — tệ hơn cả sàn cứng 0.7 mà chính tôi lo ngại.
Expert đúng.

**D8-2. Chấp nhận hướng của Expert: sửa nguyên nhân gốc (babeldoc bỏ phí chỗ trống ngang) trước,
chính sách sàn sau.**

| Bước | Nội dung | Gate |
|---|---|---|
| **8.1** | **Đo trước khi code.** Histogram scale trên **≥ 5 trang có bảng**, tách số liệu **theo từng cột**, kèm slack ngang mỗi ô. **Công cụ: đo font size trong PDF output bằng pymupdf, HOẶC instrument `typesetting.py` — KHÔNG có trong IL dump (X2-d).** | Có histogram thật; ước lượng được (8a) cứu được bao nhiêu % ô |
| **8.2** | **(8a) Nới khung ô TRƯỚC khi babeldoc tìm scale.** Với mỗi paragraph có tâm nằm trong box layout `class_name == "table"` (**gom theo hình học, KHÔNG theo `layout_label`** — X2-d), đặt lại `box.x2` = mép trái ô kế bên cùng hàng (hoặc `get_max_right_space`) trừ đệm; rồi để babeldoc tìm scale **từ 1.0 trên khung mới** | Cột 2/3 đạt scale ~1.0; **không** ô nào tràn sang ô bên cạnh — kiểm tra bằng mắt trên PDF output |
| **8.3** | **(8b) Đồng đều scale theo TỪNG CỘT + sàn**, sàn chọn **từ histogram 8.1** (tham chiếu khởi đầu ~0.67 ≈ 6pt với font gốc 9pt, **không phải kết luận**). Ô cần thấp hơn sàn → **giữ bằng sàn** và **ghi flag `layout_qa_findings` NGAY TRONG CÙNG lần implement này** | Không ô nào < sàn mà không có flag |

Đơn vị đồng đều hoá là **cột**, không phải bảng — mắt người so cỡ chữ dọc theo cột, và nó chặn được
đúng rủi ro "1 ô xấu kéo cả bảng".

**D8-3. Sàn và flag KHÔNG được tách làm 2 giai đoạn.** Sàn không kèm flag = đổi một lỗi im lặng lấy
một lỗi im lặng khác — đúng bài học Bug #6.

**D8-4. Effort**: 8.1 ≈ **0.5 ngày** (viết harness đo, không có sẵn field ⇒ tốn hơn dự kiến ban đầu).
8.2 ≈ **1 ngày**. 8.3 ≈ **0.5–1 ngày**.

**D8-5. Không đổi engine.** pdf2zh không giảm `size` mà chỉ giảm `line_height` rồi để chữ tràn ⇒
không mắc Bug #8 nhưng mắc nhóm lỗi T (chồng/tràn chữ) đã biết. Đây không phải lý do đổi default.
*(Nguồn: Expert đọc `converter.py`; **tôi chưa tự verify**, và nó không ảnh hưởng quyết định.)*

#### X7. Tương tác Bug #7 ↔ Bug #8 — ràng buộc thứ tự

Fix tầng dòng đổi số dòng/paragraph ⇒ đổi `unit_count` ⇒ đổi mode-scale toàn tài liệu
(`typesetting.py:892-935`, kẹp **xuyên trang**) ⇒ **mọi số đo của Bug #8 trước fix #7 đều hết hạn**.

⇒ **Bước 8.1 (đo histogram) BẮT BUỘC chạy SAU bước 7.1.** Đo trước sẽ phải đo lại. Và lần đo sau
7.1 phải bao cả **11 trang** (4 trang lần này + 7 trang Q2), đo đồng thời **3 chiều**: cấu trúc list,
tỷ lệ cắt nhầm caption (RC-1), và histogram scale.

#### X8. Báo cáo upstream babeldoc

Nên report (tinh thần P2.2), nhưng **theo đúng cơ chế thật**, không theo hướng "docstring nói 2":

1. Ký tự khoảng trắng không có glyph được gán `visual_bbox` cao bằng cả `font_size`
   (`il_creater.py:1092-1108`) ⇒ lấp khe giữa các dòng ⇒ `_split_paragraph_into_lines` gộp nhầm.
   Số đo: **147 → 161 / 163** paragraph đúng, 0 hồi quy.
2. `_get_effective_y_bounds` (`paragraph_finder.py:608-613`) có dead code sau `return`.
3. Logic **đảo ngược** ở `typesetting.py:1036-1062`: giãn khung **thành công** thì giữ scale thấp,
   **thất bại** thì reset `scale = 1.0`.

Đính kèm script tái tạo (X9) + golden fixture. **Không chờ phản hồi upstream để đóng task nào.**

#### X9. Script tái tạo số liệu

Không commit thành file `.py` trong repo (Protocol 7: mọi file code phải qua Reviewer; commit này
là docs + fixture). Dev tái tạo bằng cách chép khối dưới đây ra file tạm rồi chạy bằng python có
numpy. Nó **chính là** oracle cho test ở D7-5.

- Đọc fixture: `gzip.open("tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz", "rt")`.
- Lọc paragraph: bỏ paragraph có composition `pdf_same_style_unicode_characters.debug_info` (chú
  thích debug của babeldoc); gom ký tự từ `pdf_line` / `pdf_formula` / `pdf_character` /
  `pdf_same_style_characters`; **bỏ ký tự có `pdf_character_id is None`** (space dummy chèn SAU bước
  thread); giữ paragraph có ≥ 2 ký tự ⇒ **163 paragraph**.
- Thuật toán: sao đúng `_compute_collision_counts_histogram` (difference array, `step=0.25`), dùng
  `visual_bbox.box.y/.y2`; `(ymax-ymin) < 5` ⇒ 1 dòng; gap khi `count < 1`; separator = `y` tại
  index bắt đầu mỗi gap; gán ký tự theo tâm y.
- 3 biến thể: (a) nguyên trạng; (b) `count < 2`; (c) loại ký tự trắng khỏi mảng `y1/y2` đưa vào
  histogram, giữ `count < 1`.
- Ground truth: cluster `char.box.y` của ký tự **có mực**, dung sai **3pt**.
- Kỳ vọng: fidelity **162/163**; đúng **147 / 149 / 161**; hồi quy **0 / 0**.

#### X10. Bảng trạng thái verify (Protocol 5 R5-01) — cập nhật

| Claim | Trạng thái |
|---|---|
| Con số 147 / 149 / 161 trên 163 của Expert | ✅ **Verified** — replication độc lập trên golden fixture (X2) |
| Cơ chế thật = space không glyph, `visual_bbox` cao bằng font_size | ✅ **Verified** — `il_creater.py:1048-1054, 1092-1108` |
| `count<2` gây hồi quy với dòng 1 ký tự | ✅ **Verified** — ca tổng hợp X2-b, 2/2 sai |
| Ca A cũng hỏng từ tầng dòng (⇒ B-2b phụ thuộc 7.1) | ✅ **Verified** — 2 paragraph numbered-list, gt=3 → cur=1 |
| Phạm vi lỗi gồm cả văn xuôi, không chỉ list | ✅ **Verified** — 6 paragraph văn xuôi, nặng nhất 7 dòng → 1 |
| Dead code trong `_get_effective_y_bounds` | ✅ **Verified** — `:608-613` + upstream `main` |
| Lời gọi sort bị comment (`:305`, `:696`, `:738`, `:772`) | ✅ **Verified** — + upstream `main` |
| 77 ô bảng nhãn `fallback_line`, 0 ô nhãn `table` | ✅ **Verified** — golden fixture, page_number 1 |
| Có box layout `class_name == "table"` để gom theo hình học | ✅ **Verified** — id=1, `(87,252)-(583,741)` |
| Slack ngang cột 2 = 109.7pt, cột 3 = 98.1pt (median) | ✅ **Verified** — golden fixture |
| "Cột 1 gần như hết chỗ" | ⚠️ **Sai một phần** — median slack 51.8pt (X2-d) |
| `scale`/`optimal_scale` KHÔNG có trong mọi IL dump | ✅ **Verified** — 1230 paragraph, 5 dump, 0 giá trị |
| mode-scale kẹp xuyên trang theo `unit_count` | ✅ **Verified** — `typesetting.py:892-935` |
| Logic reset scale bị đảo khi giãn khung | ✅ **Verified** — `typesetting.py:1036-1062` |
| Shim V1 (`PYTHONPATH` + `sitecustomize`) patch được babeldoc subprocess | ✅ **Verified** — spike 7.0 + ship 7.1 (xem "Bug #7 fix — bước 7.0+7.1" trong CHANGELOG.md), job chạy xanh sống nhiều lần |
| B-2b heuristic marker tăng dần không false-positive | ✅ **Verified** (7.2, 2026-09-07) — spike sống (R5-02): quét TOÀN BỘ text thật trên 2 fixture ("QUESTIONS FOR REVIEW" 1-17, "EQUIPMENT AND SMALLWARES" 35-mục, gồm cả các dòng có số lượng như `"1½ quart"`, `"2- and 4-quart sizes"`) — 0 false-positive. Live E2E qua đúng `BabeldocRunner.translate_pages()` với DeepSeek thật (R6-03): 35/35 và 17/17 mục xuống dòng đúng, 0 ca dính chữ, 0 mất nội dung. Xem CHANGELOG.md "Bug #7 fix — bước 7.2 (Ca A)". |
| (8a) nới khung không gây tràn sang ô bên cạnh | ⚠️ **`[UNVERIFIED]`** — spike 8.2 |
| Giá trị sàn cụ thể (~0.67 chỉ là tham chiếu) | ⚠️ **`[UNVERIFIED]`** — phải chốt từ histogram 8.1 |
| pdf2zh không giảm `size`, chỉ giảm `line_height` | ⚠️ **`[UNVERIFIED]`** — Expert đọc source, tôi chưa tự verify; không ảnh hưởng quyết định |

**Trạng thái**: quyết định đã chốt, **vẫn chưa có dòng code nào được viết**. Việc tiếp theo là
**spike 7.0** (shim V1) — cần PM/user duyệt trước khi giao Dev (Protocol 2).

---

### Bug #7 Ca C — Đề xuất thiết kế fix mục lục (Tech Lead, 2026-09-07)

> **TRẠNG THÁI: ĐỀ XUẤT, CHƯA CHỐT — chờ Domain Expert phản biện + PM/user duyệt.**
> Viết theo đúng văn phong/quy trình mục W6 cũ và section "Final Decision" (X0–X10) phía trên:
> Tech Lead đề xuất → Domain Expert phản biện → chốt. **Không được implement bất kỳ dòng nào
> của section này trước khi có bước phản biện + duyệt.** Mọi chỗ tôi chưa tự verify được đều
> gắn nhãn tường minh ở bảng Y12 để Expert biết chỗ cần đánh.
>
> Đây là bước **"7.4"** đã được D7-3 (dòng 7.3) nêu là *"Ca C cần thiết kế fix riêng (heuristic
> theo marker cuối dòng, không phải B-2b) — chưa làm, chờ PM/user quyết định."*

#### Y0. Phán quyết một dòng

Đề xuất **TOC-1**: tách paragraph tại các **dòng kết thúc bằng số trang** — nhận diện bằng
**khoảng hở hình học** giữa phần chữ và cụm chữ số cuối dòng (chuẩn hoá theo `font_size`), cộng
với một **cổng cố kết ở mức paragraph** (phải có ≥ 2 dòng cùng dạng và chiếm ≥ 60% số dòng của
paragraph). Dùng lại **đúng cơ chế shim V1** đã ship ở 7.1/7.2, nhưng **hook ở điểm khác** (bọc
`process_independent_paragraphs` thay vì bọc `process`) — lý do ở Y6.

Tôi đã **mô phỏng luật này trên IL dump thật** (không suy đoán): trên 2 trang Contents của Figoni
nó tách đúng **20/20** paragraph mục lục (66 điểm tách mới), **0 ca tách nhầm**; trên 4 bộ dump
trang KHÔNG phải mục lục (55 paragraph nhiều dòng) nó **không kích hoạt lần nào**; quét thô toàn
bộ 6 đầu sách trong `data/uploads/` (~4657 block nhiều dòng chỉ riêng Figoni) nó cho **0 điểm
tách sai** — lần kích hoạt duy nhất ngoài Figoni là **trang mục lục của Le Cordon Bleu** (đúng ca
cần fix). Số liệu chi tiết ở Y2/Y7/Y8.

#### Y1. Nguồn xác thực (Protocol 5 R5-01) — mọi claim về babeldoc trong section này

Nguồn: babeldoc **0.6.4** đã cài thật tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/`
(cùng bản đang chạy production, cùng bản mà 7.1/7.2 gate version `"0.6.4"`). **Tôi đã tự đọc từng
dòng dưới đây trong task này**, không kế thừa từ section trước:

| Claim | Nguồn (file:line, đã đọc thật) |
|---|---|
| Thứ tự các bước trong `process_page` | `midend/paragraph_finder.py:235-310` — `:245` gán `page.pdf_paragraph = paragraphs`; `:275` gọi `_split_paragraph_into_lines` (7.1 vá ở đây); `:278-281` `add_space_dummy_chars` + `process_paragraph_spacing`; `:284` `calculate_median_line_width`; `:287` `process_independent_paragraphs`; `:290-291` `merge_alternating_line_number_paragraphs`; `:302` `fix_overlapping_paragraphs`; `:305` lời gọi sort theo x **bị comment**; `:307` `add_debug_info`; `:310` `_set_paragraph_render_order` |
| Nhánh mục lục dot-leader đòi ≥ 20 dấu chấm liên tiếp | `paragraph_finder.py:864-866` — `if re.search(r"\.{20,}", prev_text):` |
| Nhánh hình học + nhánh bullet chỉ nhìn `chars[0]` | `paragraph_finder.py:891-903` — `prev_width < median_width * short_line_split_factor` HOẶC `is_bullet_point(chars[0])` |
| Nguyên mẫu tách paragraph (tái dùng được nguyên xi) | `paragraph_finder.py:868-888` (nhánh dot-leader) và `:904-926` (nhánh hình học) — tạo `PdfParagraph(box=Box(0,0,0,0), pdf_paragraph_composition=comp[j:], unicode="", debug_id=generate_base58_id(), layout_label=…, layout_id=…)`, gọi `update_paragraph_data` cho **cả hai**, rồi `paragraphs.insert(i+1, new_paragraph)` + `break`; vòng ngoài `i += 1` sẽ **xét lại chính paragraph mới** ⇒ tách dây chuyền (cascade) là hành vi **có sẵn**, không cần tự viết vòng lặp |
| `is_bullet_point` chỉ khớp ký tự bullet, **không** nhận chữ số | `utils/layout_helper.py:50-52` (`BULLET_POINT_PATTERN`, tập ký tự không chứa `0-9`) + `:55-65` |
| `font_size` có thật trên từng ký tự | `il_version_1.py:627-638` (`PdfCharacter.pdf_style`) + `:584-610` (`PdfStyle`, `font_id` `:596`, `font_size: float` `:603`) |
| `visual_bbox.box.x/.x2` có thật trên từng ký tự | `il_version_1.py:646-651` (`PdfCharacter.visual_bbox`) + `:613-623` (`VisualBbox.box`) |
| `merge_alternating_line_number_paragraphs` **KHÔNG** gộp lại được các paragraph mục lục vừa tách | `paragraph_finder.py:393-418` chỉ gộp `a` với `c` khi **mọi** paragraph nằm giữa là "thuần chữ số/khoảng trắng" theo `_is_ascii_digit_or_space_paragraph` (`:368-380` — gặp 1 ký tự không phải digit/space là `return False`). Paragraph mục lục luôn có chữ ⇒ `saw_l` không bao giờ True ⇒ không gộp. Thêm một lớp nữa: `_same_layout_and_xobj` (`:382-391`) đòi **cả hai** `xobj_id is not None` |
| Paragraph tạo sau khi `process()` kết thúc sẽ có `render_order = None`, và điều đó **không crash** | `paragraph_finder.py:310` gọi `_set_paragraph_render_order` (định nghĩa `:312-347`) **bên trong** `process_page`; `typesetting.py:1664-1670` `_update_paragraph_render_order` `return` ngay khi `paragraph.render_order is None` |

**Không có claim nào trong section này được viết từ trí nhớ.** Chỗ nào tôi chưa verify được đều
nằm ở bảng Y12 với nhãn `[UNVERIFIED]`.

#### Y2. Dữ liệu thật đã đo trong chính task này (cơ sở của mọi con số)

**Nguồn dữ liệu** (tái sử dụng đúng artifact của bước 7.3, không dựng mới):

- IL dump trang Contents (đã có shim 7.1+7.2 bật): `/tmp/bdprobe/wd_toc/figoni_p7_toc/paragraph_finder.json`,
  `/tmp/bdprobe/wd_toc2/figoni_p8_toc/paragraph_finder.json`.
- IL dump 4 bộ trang **KHÔNG** phải mục lục (đối chứng): `/tmp/bdprobe/wd74c/p74_77/`,
  `/tmp/bdprobe/wd72c/page14_numbered_list_source/`, `/tmp/bdprobe/wd_p20/figoni_p20/`,
  `/tmp/bdprobe/wd_p22/figoni_p22/`.
- PDF gốc 6 đầu sách khác nhau trong `data/uploads/` (Figoni bản đầy đủ ~400 trang, Figoni 1-25,
  Bo Friberg, Woodhead, Le Cordon Bleu, `qa_aimd_65pages`).

⚠️ Các dump `/tmp/bdprobe/**` là **artifact tạm của phiên trước, không commit**. Nếu PM duyệt đi
tiếp, **Dev bắt buộc phải sinh lại + commit golden fixture** cho 2 trang Contents theo đúng
Protocol 5 mục 3 (xem Y11 bước 7.4-a) — **tuyệt đối không viết tay mock theo bảng số dưới đây**.

**Cấu trúc thật của mục lục Figoni** (đọc từ IL, ký tự đã sort theo x):

```
para#105  label='plain text'  8 dòng — MỘT paragraph gộp 8 mục TOC:
  [x=354.5 x2=508.9] 'Commercial Grades of White Flours   77'
  [x=354.1 x2=484.1] 'Types of Patent Wheat Flours    79'
  … (6 dòng nữa) …
  [x=354.8 x2=473.6] 'Exercises and Experiments    89'
```

Bốn quan sát **quyết định thiết kế**, tất cả đều đo được:

1. **Số trang KHÔNG căn phải.** `x2` chạy từ 416.8 tới 513.0 trong cùng một cột ⇒ **không dùng
   được tín hiệu "cột số căn phải"**. Đây là lý do tôi loại hướng thiết kế "phát hiện cột số bên
   phải" ngay từ đầu (Y5-c).
2. **Khoảng trắng giữa tên mục và số trang là DUMMY, không có trong PDF gốc.** Mọi ký tự trắng
   trong khe đó có `pdf_character_id is None` ⇒ do `add_space_dummy_chars` (`:279`) chèn vào, **số
   lượng space là sản phẩm phụ của heuristic babeldoc**, không phải dữ liệu gốc. ⇒ **Không được
   xây luật trên "đếm ≥ N khoảng trắng"**; phải đo **khoảng hở hình học**.
3. **Khoảng hở hình học rất ổn định và rất lớn**: gap = 9.0pt trên font 9.0pt ⇒ **tỷ lệ đúng
   1.00** (median trên 57 dòng của trang 6 và 78 dòng của trang 7, đo bằng PyMuPDF `rawdict`).
   Dòng tiêu đề chương (`'OF FOOD   49'`, font 14pt) có tỷ lệ **2.0**. Trong khi đó khoảng cách
   từ chuẩn giữa 2 từ ≈ 0.25–0.35 em, và ca văn xuôi tệ nhất tìm được trong cả cuốn sách là
   **0.64**. ⇒ Có một **khe an toàn rộng** giữa hai phân bố.
4. **Mục TOC có thể xuống dòng**, và **tiêu đề chương chiếm 2 dòng với số ở dòng cuối**:
   - `['Flour and Dough Additives and', 'Treatments    72']` — 1 mục, 2 dòng.
   - `['SENSORY PROPERTIES', 'OF FOOD   49']` — 1 tiêu đề chương, 2 dòng.
   ⇒ Luật **bắt buộc** phải tách **SAU** dòng có số trang (không phải "tách trước mọi dòng"),
   nếu không sẽ xé đôi chính 2 ca này. Đây là ràng buộc thiết kế cứng, không phải tinh chỉnh.

#### Y3. Vì sao cả 3 lớp của babeldoc đều chết trên trang này (xác nhận lại, có nguồn)

| Lớp | Điều kiện | Vì sao chết |
|---|---|---|
| Dot leader (`:864-866`) | `re.search(r"\.{20,}", prev_text)` | TOC Figoni **không dùng dot leader** — 0 dấu chấm |
| Hình học (`:891-895`) | `prev_width < median_width × 0.8` | Trang toàn dòng TOC ⇒ **chính chúng là median** ⇒ điều kiện gần như không bao giờ đúng (đã ghi ở W3) |
| Bullet (`:896-903`) | `is_bullet_point(chars[0])` | Marker của TOC là **số trang ở CUỐI dòng**; `chars[0]` là chữ cái đầu tên mục. `BULLET_POINT_PATTERN` (`layout_helper.py:50-52`) **không chứa `0-9`** nên kể cả đảo ngược cũng vô nghĩa |
| 7.1 (đã ship) | Sửa tầng **tách dòng** | Các dòng TOC vốn đã tách đúng — 7.1 đo được **byte-for-byte không đổi** trên 2 trang này (CHANGELOG 7.3) |
| 7.2 / B-2b (đã ship) | Marker số ở **ĐẦU** dòng | TOC không có marker đầu dòng ⇒ `extract_leading_marker` trả `None` ngay ở dòng neo ⇒ **không bao giờ kích hoạt** |

⇒ Ca C là một **lỗ hổng độc lập**, không phải phần dư của 7.1/7.2.

#### Y4. Đề xuất chính — **TOC-1**: tách theo marker số trang ở CUỐI dòng

Toàn bộ quyết định "có tách không / tách ở đâu" nằm trong **một module thuần Python**
(`src/babeldoc_shim/toc_split.py`, không import babeldoc) — **dùng chung** bởi `sitecustomize.py`
và test, đúng khuôn mẫu `numbered_list_split.py` của 7.2 (Protocol 6 R6-02: test phải gọi đúng
logic production, không chép tay thuật toán).

**Bước 1 — trích đặc trưng từng dòng** (input: danh sách `(x, x2, char_unicode, font_size)` của
các ký tự trong `pdf_line`, **đã tự sort theo x** — bắt buộc, vì cả 4 lời gọi sort của babeldoc
đều bị comment, `paragraph_finder.py:305,696,738,772`, xem X4-4):

1. Bỏ mọi ký tự `.isspace()` (gồm cả dummy space — xem Y2 điểm 2).
2. Lấy **dãy chữ số liền cuối** (`str.isdigit()`), độ dài `k`. Loại nếu `k == 0`, `k > 4`, hoặc
   `k == len(chars)` (cả dòng chỉ là số ⇒ đây là số trang chân trang / ô bảng số, **không phải**
   mục TOC).
3. `gap = x(chữ số đầu tiên của dãy) − x2(ký tự có mực cuối cùng của phần thân)`.
4. `size = font_size` của ký tự ngay trước khe (`PdfStyle.font_size`, `il_version_1.py:603-610`).
5. Đánh dấu dòng là **"đuôi mục TOC"** khi **tất cả** đúng:
   - `gap ≥ TOC_GAP_RATIO × size` (đề xuất `TOC_GAP_RATIO = 0.8`);
   - phần thân chứa **≥ `TOC_MIN_BODY_WORDS` cụm chữ cái dài ≥ 2** (đề xuất `= 1`) ⇒ loại ô bảng
     thuần số, loại `"4.0"`, `"120"`;
   - `1 ≤ số ≤ 9999`.

**Bước 2 — cổng cố kết ở mức paragraph** (đây mới là lớp chống false-positive chính, **không phải**
regex):

- `m` = số dòng được đánh dấu, `L` = số composition của paragraph.
- Chỉ tách khi `m ≥ TOC_MIN_TAIL_LINES` (đề xuất `= 2`) **VÀ** `m / L ≥ TOC_MIN_TAIL_FRACTION`
  (đề xuất `= 0.6`).
- **Bổ sung, đề xuất bật**: dãy số trang của các dòng được đánh dấu phải **không giảm**
  (`n[i] ≤ n[i+1]`). Đo thật: **20/20** paragraph mục lục thoả (`[38,39,40,40]`,
  `[77,79,82,84,86,87,88,89]`, `[4,5,6,7,8,9,10,10,11]`, `[219,224,225,226,226]`…). Phải cho
  phép **bằng nhau** — mục lục thật có `[2,2,3]` và `[194,194,195,196]`. Nếu luật này sai trên
  sách khác, hậu quả là **không tách** (giữ nguyên hiện trạng), **không phải** tách sai — đây là
  hướng thất bại an toàn.

**Bước 3 — điểm tách**: mọi dòng được đánh dấu **mà không phải dòng cuối** ⇒ ranh giới nằm **NGAY
SAU** dòng đó. Đây chính là điều làm cho `['Flour and Dough Additives and', 'Treatments 72']` và
`['SENSORY PROPERTIES', 'OF FOOD 49']` **không bị xé** (dòng có số là dòng cuối ⇒ 0 điểm tách).

**Bước 4 — thực thi**: cắt `pdf_paragraph_composition` theo các nhóm, nhóm đầu giữ nguyên
paragraph gốc, mỗi nhóm sau tạo `PdfParagraph` mới **đúng theo nguyên mẫu `:868-888`** (copy
`layout_label`, `layout_id`, gọi `update_paragraph_data` cho cả hai). Composition **không phải**
`pdf_line` (`pdf_formula`, `pdf_character`) ⇒ không bao giờ được đánh dấu, dính vào nhóm liền
trước — giống hệt cách 7.2 xử lý.

#### Y5. Ba hướng thay thế — và vì sao tôi loại

- **(a) Nới nhánh dot-leader** (`\.{20,}` → `\.{3,}`): **không giải quyết được Ca C** (TOC Figoni
  có **0** dấu chấm), đồng thời tăng rủi ro với dấu ba chấm/ellipsis trong văn xuôi. **Loại làm
  giải pháp chính.** Nhưng đề xuất **giữ lại như một tín hiệu PHỤ** (TOC-1b): nếu phần thân kết
  thúc bằng ≥ 3 dấu chấm liên tiếp (hoặc ≥ 3 cặp `. `), coi như thoả điều kiện `gap` — để cùng
  một luật phục vụ được cả TOC có dot leader thưa (< 20 chấm) mà babeldoc đang bỏ lọt. **Đề xuất
  để TẮT mặc định ở v1**, chỉ bật sau khi đo được trên một cuốn có dot leader thật (Y12).
- **(b) Hạ `short_line_split_factor`**: đã chứng minh là **ngõ cụt cấu trúc** ở W3 — trên trang
  toàn dòng ngắn, chính chúng là median. Không giá trị nào chữa được. **Loại.**
- **(c) Nhận diện "cột số căn phải"** (gom các số cùng `x2`): **sai ngay trên dữ liệu thật** —
  `x2` của Figoni chạy 416.8 → 513.0 (Y2 điểm 1). **Loại.**
- **(d) Nhận diện "trang này là trang mục lục" rồi mới áp luật** (ví dụ tìm chữ "Contents" trên
  trang): **loại** — phụ thuộc ngôn ngữ/nhan đề, và mục lục thường tràn nhiều trang mà chỉ trang
  đầu có tiêu đề. Cổng cố kết ở Y4 bước 2 đã đóng vai trò "đây có phải khối mục lục không" ngay
  ở mức paragraph, **không cần biết trang nào là trang gì** — quan trọng, vì babeldoc xử lý toàn
  bộ IL và **không có khái niệm "trang mục lục"**.

#### Y6. Điểm hook — đề xuất **KHÁC** 7.2, và đây là điểm tôi muốn Expert soi kỹ nhất

7.2 bọc `ParagraphFinder.process` và chạy **sau khi `process()` kết thúc hoàn toàn**. Với TOC-1
tôi đề xuất hook **sớm hơn**: bọc `ParagraphFinder.process_independent_paragraphs(paragraphs,
median_width)` (`:841`) — chạy hàm gốc trước, rồi chạy TOC-1 trên **cùng list `paragraphs`** (hàm
gốc cũng mutate in-place bằng `paragraphs.insert`, và `page.pdf_paragraph` trỏ tới **cùng object
list**, gán ở `:245`).

Lý do (3 cái, đều có nguồn ở Y1):

1. **Paragraph mới sẽ được gán `render_order`**: `_set_paragraph_render_order` chạy ở `:310`,
   **sau** `:287`. Paragraph do 7.2 tạo (sau `process()`) hiện có `render_order = None` ⇒
   `typesetting._update_paragraph_render_order` (`:1664-1670`) `return` ngay, **bỏ qua việc chuẩn
   hoá render order cho mọi ký tự của paragraph đó**. Không crash, nhưng là một **sai khác âm
   thầm mà 7.2 đang mang sẵn** — tôi phát hiện trong task này, xem Y10-b.
2. **Paragraph mới sẽ có debug rectangle**: `add_debug_info` (`:307`, chỉ chạy khi `--debug`) —
   giúp chính việc đo/QA của chúng ta nhìn thấy ranh giới mới.
3. **Đúng tầng ngữ nghĩa**: `process_independent_paragraphs` **chính là** hàm babeldoc dành cho
   "tách paragraph theo marker", và nhánh mục lục (dot leader) của nó cũng ở đó. TOC-1 là **anh
   em cùng tầng** với nhánh `:864-866`, không phải một pass ngoại lai.

Rủi ro của hook sớm hơn (đã tự kiểm và **loại được bằng đọc source**, không phải phỏng đoán):
`merge_alternating_line_number_paragraphs` chạy ngay sau ở `:290-291` — nhưng nó **không thể gộp
lại** các paragraph mục lục vừa tách, vì `_is_ascii_digit_or_space_paragraph` (`:368-380`) trả
`False` ngay khi paragraph có chữ cái, và `_same_layout_and_xobj` (`:382-391`) còn đòi cả hai
`xobj_id is not None`. ⇒ Không có nguy cơ "tách xong bị gộp lại".

**Không đề xuất di dời 7.2 sang hook này trong cùng task** — 7.2 đã qua live E2E, đổi hook là mở
lại một thứ đã verify. Ghi lại thành **tech debt** (Y10-b).

#### Y7. Rủi ro false-positive — tôi tự liệt kê, và số đo cho từng loại

Đây là phần tôi muốn bị phản biện mạnh nhất. Các loại nội dung **không phải TOC** mà vẫn có thể
kết thúc bằng số:

| # | Loại nội dung | Luật nào chặn | Đo thật |
|---|---|---|---|
| FP-1 | Văn xuôi kết thúc bằng số liệu (`"…contains about 15"`, `"…amount—about 75"`) | `gap ≥ 0.8×size` (khoảng trắng từ thường ≈ 0.25–0.35 em) **và** `m ≥ 2` trong cùng paragraph | Quét **toàn bộ** Figoni (~400 trang, 4657 block nhiều dòng): ở ngưỡng tuyệt đối `gap ≥ 4pt` có **3** ca (p83, p92, p340, gap 4.1–6.4pt); ở `ratio ≥ 0.5` còn **1**; ở **`ratio ≥ 0.8` còn 0**. Trên IL thật của 4 bộ trang đối chứng: **0** dòng khớp |
| FP-2 | Số trang chân trang / đầu trang (folio) đứng một mình | Loại bởi `k == len(chars)` (cả dòng là số) **và** `TOC_MIN_BODY_WORDS ≥ 1` | Quét thô ban đầu cho thấy folio là nguồn nhiễu lớn nhất (hàng trăm dòng); sau khi thêm 2 điều kiện này ⇒ **0** |
| FP-3 | Ô bảng số (`"4.0"`, `"120"`, `"3000"`) | Như FP-2, cộng `k ≤ 4` chữ số và phải là **dãy digit liền cuối** (`"4.0"` kết thúc bằng `0` nhưng thân là `"4."` ⇒ 0 cụm chữ cái ⇒ loại) | IL thật `p20`/`p22` (đúng 2 trang bảng đã dùng làm bằng chứng RC-1): **0 kích hoạt** |
| FP-4 | Bảng công thức bánh (`"Bread flour   100"`, `"Water   62"`) — **rủi ro thật, chưa loại được** | Không có luật nào chặn: mọi dòng đều có chữ + số cuối + khe rộng | ⚠️ **Chưa đo được** — chưa có trang công thức nào trong 11 trang đã dump IL. Xem Y12 và Y11 bước 7.4-a. **Lưu ý giảm nhẹ**: nếu bị tách, mỗi dòng công thức thành 1 paragraph riêng — với chất lượng dịch đây **có thể là cải thiện chứ không phải hỏng** (LLM hết trộn các dòng nguyên liệu vào nhau, đúng bản chất Ca C). Nhưng nó **đổi `unit_count`** ⇒ đụng mode-scale của Bug #8 (X7) ⇒ **phải đo, không được đoán** |
| FP-5 | Chú thích hình/bảng kết thúc bằng số (`"…xem Bảng 4.2"`) | Thân kết thúc bằng `"4."` + dãy `2` ⇒ khe giữa `.` và `2` = 0 ⇒ `gap` gần 0 ⇒ loại | IL `p20`/`p22`: **0** |
| FP-6 | Danh mục tài liệu tham khảo (`"J. Food Sci. 45"`) | `gap` là khoảng trắng từ thường ⇒ tỷ lệ ~0.25 ⇒ loại | Không có trang references trong mẫu ⇒ ⚠️ chưa đo, nhưng cơ chế chặn giống FP-1 |
| FP-7 | Index (`"Sugar, 45"`) | `gap` nhỏ (sau dấu phẩy) ⇒ loại. **Kể cả nếu khớp**, tách index thành từng mục là **đúng**, không phải hỏng | ⚠️ chưa đo |
| FP-8 | Danh sách bảng/hình ("List of Tables") | **Cố ý khớp** — đây là TOC biến thể, tách là **đúng mong muốn** | — |

**Ba tín hiệu tôi coi là đáng tin nhất, xếp theo độ mạnh** (trả lời trực tiếp yêu cầu của brief):

1. **Cổng cố kết `m ≥ 2` trong CÙNG một paragraph** — mạnh nhất. Một câu văn xuôi kết thúc ngẫu
   nhiên bằng số là chuyện có thật (3 ca / 400 trang); **hai dòng trong cùng một paragraph cùng
   kết thúc bằng số với khe rộng** thì trong toàn bộ dữ liệu đã đo là **0 ca ngoài mục lục**.
2. **Khe hình học chuẩn hoá theo font** — TOC = 1.0–2.0, văn xuôi tệ nhất = 0.64. Khe an toàn
   rộng. Chuẩn hoá theo `font_size` (không dùng pt tuyệt đối) là điều bắt buộc để luật còn đúng
   với sách cỡ chữ khác.
3. **Số trang không giảm** — 20/20 đúng trên dữ liệu thật; và khi sai thì thất bại theo hướng an
   toàn (không tách).

Tín hiệu tôi **cố ý KHÔNG dùng** và lý do: đếm số khoảng trắng (dummy, Y2-2); căn phải `x2` (sai
trên dữ liệu thật, Y2-1); "số trang tăng đều/liên tục" (mục lục thật nhảy cóc: `[15,21,22,22]`,
`[245,250,253,256]`); "số trang phải khớp số trang vật lý của PDF" (mục lục dùng số trang **in
trong sách**, lệch offset với index PDF — chính CHANGELOG 7.3 đã ghi mapping "trang sách N ↔
PyMuPDF index N−1").

#### Y8. Rủi ro hồi quy trên trang KHÔNG phải mục lục

Trả lời thẳng câu hỏi của brief: **đúng, luật này chạy trên MỌI paragraph của MỌI trang** —
babeldoc không có khái niệm "trang mục lục", và tôi **cố ý không** thêm khái niệm đó (Y5-d). Vì
vậy phần chống hồi quy phải nằm hoàn toàn trong bản thân heuristic. Bằng chứng hiện có:

| Phạm vi đo | Đơn vị | Kích hoạt sai |
|---|---|---|
| IL thật, 4 bộ trang không phải TOC (p74–77, page14 35-mục, p20 bảng+caption, p22 mix) | 55 paragraph nhiều dòng | **0** |
| Figoni bản đầy đủ, quét toàn sách bằng PyMuPDF (`ratio ≥ 0.8`, thân ≥ 2 từ) | 4657 block nhiều dòng | **0** |
| 6 đầu sách khác nhau trong `data/uploads/` cùng ngưỡng | toàn bộ | **1 block** — và đó là **trang mục lục của Le Cordon Bleu** (`'Crème d'amandes—Almond Cream  352'`, gap 11.6pt / font 12pt = 0.97) ⇒ **true positive**, không phải FP |

⚠️ **Giới hạn của bằng chứng, phải nói rõ**: phép quét toàn sách dùng **block của PyMuPDF**, còn
babeldoc gom paragraph theo **layout model** — hai cách gom **khác nhau**, và babeldoc thường gom
**to hơn**. Vì vậy con số "0 trên 4657 block" là **ước lượng bề mặt rủi ro, KHÔNG phải bằng chứng
tương đương**. Chỉ 4 bộ dump IL (11 trang) là so sánh đúng-đối-đúng. **Đây là lý do bước spike
7.4-a ở Y11 là bắt buộc, không được bỏ.**

**Rủi ro gián tiếp (không phải tách sai, nhưng phải nêu)**: TOC-1 làm **tăng số paragraph** ⇒ đổi
`unit_count` ⇒ đổi **mode-scale toàn tài liệu** (`typesetting.py:892-935`, kẹp **xuyên trang** —
đã verified ở X2-c). Đúng ràng buộc X7. ⇒ Nếu Bug #8 (bước 8.1) đã đo histogram trước khi TOC-1
lên, **số đo đó hết hạn**. Phải ghi vào D-ordering.

#### Y9. Có tổng quát cho sách khác không?

**Tổng quát ở mức cơ chế, KHÔNG phải chỉ đúng cho Figoni** — nhưng có biên rõ ràng:

| Dạng mục lục | TOC-1 xử lý được? |
|---|---|
| Số trang cuối dòng, cách bằng khe rộng (Figoni, Le Cordon Bleu) | ✅ Đây là ca thiết kế chính. Đã thấy khớp trên **2 đầu sách khác nhau** |
| Dot leader ≥ 20 chấm | ✅ Đã được **babeldoc gốc** xử lý (`:864-866`), TOC-1 không cần đụng |
| Dot leader < 20 chấm hoặc chấm cách thưa (`. . . .`) | ⚠️ Hiện **lọt cả hai lưới**. TOC-1b (Y5-a) đóng được, đề xuất tắt mặc định ở v1 |
| Số trang là **chữ số La Mã** (phần đầu sách: `"Preface  vii"`) | ❌ **Không xử lý** — cố ý. Thêm La Mã sẽ khớp cả `"I"`, `"V"`, `"X"`, `"C"`, `"D"`, `"M"` đứng cuối dòng (chữ cái đầu tên riêng, ký hiệu đơn vị) ⇒ rủi ro FP tăng vọt so với lợi ích. **Đề xuất KHÔNG làm** |
| Mục lục 2 cột mà babeldoc gom **chéo cột** vào 1 paragraph | ⚠️ Chưa gặp. Nếu xảy ra, dãy số sẽ **giảm** ở chỗ nhảy cột ⇒ cổng "không giảm" sẽ **chặn toàn bộ paragraph** ⇒ mất fix (an toàn nhưng mất tác dụng). Nếu Expert cho rằng đây là ca phổ biến, cân nhắc **hạ cổng monotonic xuống mức "cảnh báo" thay vì "chặn"** |
| Mục lục có số trang dạng `"12–15"` hoặc `"3-1"` | ⚠️ Dãy digit liền cuối sẽ là `15` / `1`; vẫn tách đúng chỗ. Vô hại |

#### Y10. Chi tiết triển khai đề xuất (để Expert soi, **chưa phải lệnh cho Dev**)

**(a) File và cờ điều khiển** — theo đúng khuôn 7.2, kill-switch **RIÊNG**:

| Thành phần | Nội dung |
|---|---|
| `src/babeldoc_shim/toc_split.py` (mới) | Thuần Python, không import babeldoc. API đề xuất: `mark_toc_tail(chars) -> TocTail \| None` và `split_paragraph_by_toc_tails(lines) -> list[list[int]]`. **Hàm duy nhất** quyết định ranh giới; `sitecustomize.py` chỉ thực thi |
| `src/babeldoc_shim/sitecustomize.py` | Thêm patch thứ 3: bọc `ParagraphFinder.process_independent_paragraphs` (Y6). **Cùng `try/except` + cùng gate version `0.6.4`** với 7.1/7.2 — cả 3 rollback chung nếu cấu trúc babeldoc đổi |
| `src/core/config.py` | `Settings.babeldoc_toc_split_enabled: bool` — **đề xuất mặc định `False` ở lần ship đầu**, bật sau khi QA live xanh. Lý do: 7.1 đã qua 11 trang, 7.2 qua 2 fixture; TOC-1 mới nhất ⇒ rủi ro cao nhất ⇒ phải tắt được độc lập |
| `src/services/babeldoc_runner.py` | Nối `BABELDOC_SHIM_TOC_SPLIT=1/0` vào `env` của subprocess (đúng cách 7.2 làm với `BABELDOC_SHIM_NUMBERED_LIST_SPLIT`) |
| `src/core/job_orchestrator.py` | Truyền cờ vào `BabeldocRunner` |

Tham số (đề xuất, **phải chốt lại từ số đo của spike**, không phải hằng số thiêng):
`TOC_GAP_RATIO = 0.8`, `TOC_MIN_TAIL_LINES = 2`, `TOC_MIN_TAIL_FRACTION = 0.6`,
`TOC_MIN_BODY_WORDS = 1`, `TOC_MAX_DIGITS = 4`, `TOC_REQUIRE_NON_DECREASING = True`,
`TOC_DOT_LEADER_FALLBACK = False`.

**(b) Tech debt phát hiện trong task này (KHÔNG thuộc phạm vi Ca C, ghi để không mất dấu)**:
paragraph do **7.2** tạo ra có `render_order = None` (vì hook chạy sau `:310`), khiến
`typesetting._update_paragraph_render_order` (`:1664-1670`) bỏ qua paragraph đó. Không crash,
không thấy triệu chứng trong live E2E của 7.2, nhưng là sai khác âm thầm so với paragraph do
babeldoc tự tách. **Fix rẻ nhất**: copy `paragraph.render_order` sang paragraph mới trong
`_split_numbered_list_paragraphs_on_page` (`sitecustomize.py:219-226`). ⚠️ **`[UNVERIFIED]`** —
tôi **chưa đo** được nó có gây khác biệt nhìn thấy trong PDF output hay không. Đề xuất: **task
riêng**, không nhét vào 7.4.

#### Y11. Kế hoạch bước "7.4" và effort

| Bước | Nội dung | Gate bắt buộc trước khi qua bước sau |
|---|---|---|
| **7.4-a** — Spike (R5-02) | Sinh IL dump thật (`--debug`, LLM port chết, 0 token) cho: 2 trang Contents Figoni + **ít nhất 1 trang bảng công thức bánh** (FP-4) + 1 trang index/references nếu có + trang Contents của **Le Cordon Bleu** (sách thứ 2). Chạy TOC-1 offline trên các dump, báo cáo **recall** và **FP** riêng từng loại. **Commit golden fixture** (`.json.gz`) vào `tests/fixtures/babeldoc/` | FP trên trang không phải TOC = **0**; recall trên 2 trang Contents Figoni = **20/20 paragraph**; **có số liệu cho FP-4**. Nếu FP-4 kích hoạt ⇒ **dừng, escalate Tech Lead**, không tự chỉnh tham số |
| **7.4-b** — Implement | `toc_split.py` + patch thứ 3 + 3 file wiring (Y10-a) | `ruff check` + `ruff format` sạch |
| **7.4-c** — Test (R6-02) | Unit test cho từng luật (gồm ca âm tường minh: `"…about 15"`, `"4.0"`, folio thuần số, tiêu đề 2 dòng, mục TOC xuống dòng). Golden-fixture test assert **số nhóm VÀ nội dung từng nhóm** — bảng số ở Y2 là **oracle** | Test gọi **đúng** hàm production, không chép tay thuật toán |
| **7.4-d** — Live E2E (R6-03) | Dịch thật 2 trang Contents qua đúng `BabeldocRunner.translate_pages()` với DeepSeek, **mở PDF output đọc nội dung**, đếm số block và kiểm tra ranh giới mục. So với baseline 7.3 (**26 block**, các mục bị trộn) | Không còn ca "nhiều mục TOC trộn thành 1 câu"; multiset ký tự trước/sau **không đổi** (không mất chữ) |
| **7.4-e** — Đo hồi quy | Chạy lại **11 trang** của 7.1 (4 trang p74-77 + 7 trang Q2) + p20/p22, so IL trước/sau | **0** thay đổi trên các trang không phải TOC |
| **7.4-f** — Reviewer (Protocol 7 R7-01) | Spawn agent `Reviewer` thật, ghi **APPEND** vào `docs/review-report.md` | Bắt buộc, không tự review |

**Effort ước lượng**: 7.4-a ≈ **3–4 giờ** (phần lớn là sinh dump cho trang công thức/sách thứ 2);
7.4-b ≈ **3 giờ** (logic lõi ~60 dòng, phần lớn là wiring 4 file); 7.4-c ≈ **3 giờ**;
7.4-d + 7.4-e ≈ **3 giờ**. **Tổng ≈ 1.5 ngày**, tương đương 7.2.

**Ràng buộc thứ tự** (bổ sung vào D7-3/X7): 7.4 **phải xong trước** bước **8.1** (đo histogram
scale của Bug #8), vì TOC-1 đổi số paragraph ⇒ đổi `unit_count` ⇒ đổi mode-scale xuyên trang
(Y8). Nếu 8.1 đã chạy trước, **phải đo lại**.

#### Y12. Bảng trạng thái verify (Protocol 5 R5-01) — chỗ Domain Expert nên đánh

| Claim | Trạng thái |
|---|---|
| Mọi contract babeldoc trích ở Y1 (file:line) | ✅ **Verified** — đọc trực tiếp source 0.6.4 đã cài trong task này |
| TOC Figoni không dot leader, số trang **không** căn phải, khe = dummy space | ✅ **Verified** — IL dump thật + PyMuPDF `rawdict` |
| Tỷ lệ `gap/font_size` của mục TOC = 1.0 (tiêu đề 2.0), văn xuôi tệ nhất = 0.64 | ✅ **Verified** — 135 dòng trên 2 trang Contents + quét toàn sách |
| TOC-1 tách đúng **20/20** paragraph mục lục (66 điểm tách), **0** tách nhầm tiêu đề/dòng nối | ✅ **Verified** — mô phỏng trên IL dump thật của p7 (8/12 fire, 28 splits) và p8 (12/18 fire, 38 splits); 10 paragraph bị bỏ qua đều **đúng** là tiêu đề chương / mục xuống dòng |
| Dãy số trang không giảm trên **20/20** paragraph mục lục | ✅ **Verified** — cùng dump |
| TOC-1 **0** kích hoạt trên 55 paragraph nhiều dòng của 4 bộ trang không phải TOC | ✅ **Verified** — IL dump thật |
| `merge_alternating_line_number_paragraphs` không gộp lại paragraph mục lục vừa tách | ✅ **Verified** — `:368-380`, `:382-391`, `:393-418` |
| Hook `process_independent_paragraphs` mutate in-place và propagate qua `page.pdf_paragraph` | ⚠️ **`[UNVERIFIED]`** — suy ra từ việc `:247` gán cùng object list và hàm gốc dùng `paragraphs.insert`; **chưa chạy thật**. Spike 7.4-a phải chứng minh bằng dump |
| **FP-4 — bảng công thức bánh** (`"Bread flour  100"`) có kích hoạt TOC-1 không | ⚠️ **`[UNVERIFIED]` — RỦI RO LỚN NHẤT.** Chưa có trang nào loại này trong 11 trang đã dump. **Gate cứng của 7.4-a** |
| FP-6 (references), FP-7 (index) | ⚠️ **`[UNVERIFIED]`** — chưa có mẫu; cơ chế chặn giống FP-1 |
| Bộ tham số (0.8 / 2 / 0.6 / 1) là tối ưu | ⚠️ **`[UNVERIFIED]`** — tune trên **1 cuốn**. Phải chốt lại từ 7.4-a với ≥ 2 cuốn |
| Quét toàn sách bằng PyMuPDF ⇒ 0 FP có tương đương với babeldoc paragraph không | ❌ **KHÔNG tương đương** — cách gom khác nhau (Y8). Chỉ dùng làm ước lượng bề mặt rủi ro |
| TOC-1b (dot leader thưa) không gây FP với ellipsis văn xuôi | ⚠️ **`[UNVERIFIED]`** — đề xuất **tắt mặc định** ở v1 |
| Chữ số La Mã | ❌ **Cố ý không hỗ trợ** (Y9) — quyết định thiết kế, không phải thiếu sót |
| `render_order = None` của paragraph do 7.2 tạo có gây khác biệt nhìn thấy được không | ⚠️ **`[UNVERIFIED]`** — task riêng (Y10-b) |
| TOC-1 đổi `unit_count` ⇒ hết hạn số đo Bug #8 | ✅ **Verified về cơ chế** (`typesetting.py:892-935`, X2-c) — **chưa đo biên độ** |

#### Y13. Ba câu hỏi tôi muốn Domain Expert phản biện tập trung

1. **FP-4 (bảng công thức bánh)** — đây là chỗ tôi tự thấy yếu nhất. Với domain bánh, dòng
   `"Bread flour   100"` / `"Water   62%"` xuất hiện dày đặc, thoả **mọi** điều kiện của TOC-1
   (có chữ, số cuối, khe rộng, `m` lớn, thậm chí có thể không giảm). Câu hỏi: (a) khi babeldoc
   gom một cột công thức thành 1 paragraph rồi TOC-1 tách thành từng dòng — đó là **hỏng** hay
   thực ra là **cải thiện** cho chất lượng dịch? (b) nếu là hỏng, tín hiệu nào phân biệt được
   "bảng công thức" với "mục lục" mà **không** cần biết trang nào là trang gì?
2. **Cổng monotonic** — tôi đề xuất bật (20/20 đúng trên dữ liệu Figoni). Nhưng nếu mục lục 2 cột
   bị babeldoc gom chéo cột thì cổng này giết luôn cả fix. Expert có ca thật nào cho thấy nên hạ
   nó xuống mức "tín hiệu mềm" thay vì "điều kiện cứng" không?
3. **Điểm hook `process_independent_paragraphs` (Y6)** — tôi cố tình chọn **khác** 7.2 để paragraph
   mới nhận được `render_order` và debug rect. Đổi lại, nó chạy **trong lòng** `process_page` chứ
   không phải sau, nên bề mặt tương tác với các bước `:290-310` rộng hơn. Tôi đã đọc source và
   loại được nguy cơ bị `merge_alternating_line_number_paragraphs` gộp lại — Expert có thấy bước
   nào khác trong `:288-310` (`fix_overlapping_paragraphs` ở `:302`?) có thể phá hoặc gộp lại
   các paragraph vừa tách mà tôi bỏ sót không?

**Trạng thái**: thiết kế xong ở mức đề xuất, **chưa có dòng code nào được viết**. Việc tiếp theo:
Domain Expert phản biện → Tech Lead chốt → PM/user duyệt (Protocol 2) → mới giao Dev spike 7.4-a.

---

### Bug #7 Ca C — Phản biện của Domain Expert (2026-09-07)

> Phản biện độc lập cho đề xuất TOC-1 (Y0–Y13). Mọi số liệu dưới đây do tôi **tự đo lại** bằng script
> viết riêng (không chạy lại script của Tech Lead) và bằng **6 lần chạy `babeldoc --debug` mới** trên
> trang chưa từng được dump trước đây. Mọi trích dẫn source đều đã tự mở file đúng dòng.

#### Z0. Phán quyết một dòng

**ĐỒNG Ý cho TOC-1 đi tiếp sang spike 7.4-a**, với 3 sửa đổi thiết kế bắt buộc (Z8), và với **1 điều
kiện tiên quyết không thuộc Ca C**: phải hotfix một **bug production thật của 7.2** mà tôi phát hiện
trong lúc kiểm tra điểm hook (Z6) — mọi paragraph do 7.2 tách ra hiện **không được dịch** (giữ nguyên
tiếng Anh), và CHANGELOG 7.2 đã ghi nhận triệu chứng này nhưng **quy nhầm nguyên nhân** cho LLM fallback.

#### Z1. Dữ liệu tự sinh trong task này (tái tạo được, Protocol 5 mục 3)

Lệnh chạy (đúng flag production của `BabeldocRunner`, shim 7.1+7.2 bật qua `PYTHONPATH`, cổng LLM
chết, 0 token), mỗi file trích bằng `pymupdf.insert_pdf` từ `data/uploads/`:

```
PYTHONPATH=src/babeldoc_shim BABELDOC_SHIM_NUMBERED_LIST_SPLIT=1 babeldoc --files <f>.pdf --debug \
  --working-dir <wd> --output <out> -li en -lo vi --openai --openai-base-url http://127.0.0.1:1/v1 \
  --openai-api-key x --openai-model x --pool-max-workers 1 --watermark-output-mode no_watermark \
  --only-include-translated-page --no-auto-extract-glossary --skip-scanned-detection \
  --split-short-lines --short-line-split-factor 0.8 --ignore-cache
```

| Tên | Nguồn (PyMuPDF index) | Mục đích | Kết quả TOC-1 (mô phỏng độc lập) |
|---|---|---|---|
| `figoni_p25_recipe` | Figoni bản đầy đủ idx 40 (trang sách 25, "Drop Sugar Cookie Dough", cột BAKER'S PERCENTAGE **không có `%`**: 82/113/1.6/1.6/37/100/335.2) | **FP-4** | 9 paragraph nhiều dòng, **0 kích hoạt** |
| `figoni_p45_recipe` | Figoni idx 60 (trang công thức thứ 2) | FP-4 | 14 paragraph nhiều dòng, **0** |
| `figoni_p7_tables` | Figoni idx 22 (TABLE 1.4/1.5/1.6, có `%`) | FP-3/FP-4 | 6 paragraph nhiều dòng, **0** |
| `lcb_toc` | Le Cordon Bleu idx 6–7 (Contents, **2 cột**, nhiều mục xuống dòng) | Q2 + tổng quát hoá | 15 paragraph nhiều dòng, **11 kích hoạt, 64 điểm tách**, monotonic 11/11 |
| `friberg_toc` | Bo Friberg idx 6 (Contents, số trang căn phải xa, font 8pt) | Quy ước xuống dòng khác | 3 paragraph nhiều dòng, **0** (xem Z7-a) |
| `lcb_index` | Le Cordon Bleu idx 408 (Subject Index) | **FP-7** | 16 paragraph nhiều dòng, **0** |

Dump nằm tại scratchpad phiên này
(`/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad/wd/<tên>/<tên>/paragraph_finder.json`,
script mô phỏng `toc1_sim.py`, `struct.py` cùng thư mục) — artifact tạm, **Dev phải sinh lại và commit
golden fixture ở 7.4-a** như Y2 đã yêu cầu.

Ngoài ra tôi tái mô phỏng TOC-1 trên 2 dump Contents Figoni của 7.3 (`/tmp/bdprobe/wd_toc*`): kết quả
**khớp tuyệt đối** với Y12 — 8/12 và 12/18 paragraph kích hoạt, 28 + 38 = **66 điểm tách**, 10
paragraph bị bỏ qua đúng là 7 tiêu đề chương 2 dòng + 3 mục xuống dòng. Con số của Tech Lead **đúng**.

#### Z2. Kiểm tra từng trích dẫn source ở Y1 (tự mở file 0.6.4 đã cài)

| Claim Y1 | Kết quả |
|---|---|
| `process_page` `:235-310`, thứ tự `:245/:275/:278-281/:284/:287/:290-291/:302/:305/:307/:310` | ✅ Đúng từng dòng. **Lỗi nhỏ**: Y12 ghi "`:247` gán cùng object list" — dòng đúng là **`:245`** (`page.pdf_paragraph = paragraphs`); `:247` là `page_level_formula_font_ids…`. Chỉ là lỗi đánh máy, kết luận không đổi |
| Dot-leader `\.{20,}` `:864-866`; hình học/bullet `:891-903`; nguyên mẫu tách `:868-888` và `:904-926`; cascade qua `paragraphs.insert(i+1)` + `break` + vòng ngoài `i += 1` | ✅ Đúng |
| `is_bullet_point` không nhận chữ số, `layout_helper.py:50-52`, `:55-65` | ✅ Đúng |
| `il_version_1.py` `PdfStyle.font_size`, `PdfCharacter.visual_bbox` | ✅ Đúng (font_size `:603`, VisualBbox `:613-623`, PdfCharacter `:627+`) |
| `merge_alternating_line_number_paragraphs` `:393-418`, `_is_ascii_digit_or_space_paragraph` `:368-380`, `_same_layout_and_xobj` `:382-391` | ✅ Dòng đúng — **nhưng lập luận "còn đòi cả hai `xobj_id is not None`" là SAI trên dữ liệu thật**: trong **mọi** dump tôi mở (Figoni p7/p8/p25/p45/p7-tables, LCB, Friberg, p74-77, page14) paragraph nội dung chính có **`xobj_id = 0`**, không phải `None` — `0 is not None` là `True`, guard này **không chặn gì cả**. Lớp bảo vệ thật là `_is_ascii_digit_or_space_paragraph` (TOC-1 không bao giờ tạo paragraph thuần số) **và** `a.layout_id == c.layout_id`. Kết luận "không bị gộp lại" **vẫn đúng**, nhưng vì lý do khác (Z5-a) |
| `_set_paragraph_render_order` `:312-347` chạy trong `process_page`; `typesetting.py:1664-1670` `return` khi `render_order is None` | ✅ Đúng. **Bổ sung TL chưa xem hạ nguồn**: `backend/pdf_creater.py:52-55` ép `render_order None → 9999999999999999`, `:66-68` sort key, `:934 sorted(render_units, key=get_sort_key)` ⇒ ký tự của paragraph không có `render_order` bị **vẽ sau cùng** trong content stream. Không crash, chỉ đổi z-order; không thấy hậu quả nhìn được — Y10-b xếp **ưu tiên thấp** là hợp lý (nhưng xem Z6: cùng dòng code đó còn thiếu thứ nghiêm trọng hơn) |
| `_update_paragraph_render_order` chỉ được gọi ở nhánh re-typeset (`typesetting.py:1283`), không gọi ở nhánh passthrough (`:1265-1269`) | ✅ Tôi tự kiểm, TL không nêu — nhánh passthrough giữ ký tự gốc (đã có `render_order`), nên khác biệt chỉ xuất hiện với paragraph **được dịch** |

#### Z3. Câu hỏi 1 — FP-4 (bảng công thức bánh): **KHÔNG kích hoạt trên dữ liệu thật của project — nhưng vì một lý do khác với những gì Y7 giả định**

**Bằng chứng (3 trang công thức thật, dump IL mới)**: trên cả 3 trang, layout model của babeldoc gán vùng
bảng nhãn `table` và `_group_characters_into_paragraphs` (`:447-507`, tạo paragraph mới mỗi khi
`layout_id` đổi trong thứ tự content stream) đưa **mỗi ô thành 1 paragraph `fallback_line` 1 dòng**
(`figoni_p25_recipe`: `'Shortening, all-purpose'` lid=34, `'410'` lid=30, `'Sugar, regular granulated'`
lid=39… — 82 ô `fallback_line` trên `figoni_p7_tables`). Dòng kiểu `"Bread flour   100"` mà Y7 lo ngại
**không tồn tại ở tầng IL**: tên nguyên liệu và con số nằm ở 2 paragraph khác nhau, TOC-1 (đòi ≥ 2 dòng
trong **cùng** paragraph) không có gì để xét. Đây đúng là hiện tượng X2-d đã ghi (77 ô `fallback_line`)
— Tech Lead đã có bằng chứng này trong tay từ Bug #8 nhưng không nối vào FP-4.

**Ba đầu sách còn lại** (đọc text thật): Bo Friberg viết định lượng **trước** tên nguyên liệu
(`'1 pound 6 ounces (625 g) cake flour'`, idx 118) ⇒ không có chữ số cuối dòng; Le Cordon Bleu ghi số
**kèm đơn vị** (`'20 g'`, `'350 ml'`) ⇒ `k = 0`; Woodhead: 0 dòng dạng `chữ  <2+ space>  số$` trong 298
trang. Bảng "Ingredient Ratios" của Friberg (idx 79) dùng `100%` ⇒ `k = 0`.

**Trả lời (a)**: đồng ý với TL — *nếu* một cột công thức bị gom thành 1 paragraph rồi bị tách từng dòng,
đó là **cải thiện** (LLM hết trộn dòng nguyên liệu), không phải hỏng; rủi ro duy nhất là đổi `unit_count`
(X7) — nhưng ca này **không xảy ra** trên dữ liệu đã có. **Trả lời (b)**: tín hiệu phân biệt đã có sẵn
và đã verify (X2-d): `page.page_layout` có entry `class_name == "table"` với box hình học. Đề xuất thêm
**guard rẻ**: bỏ qua paragraph có tâm nằm trong box `table` (cùng cách gom của bước 8.2). Không cần
biết "trang nào là trang gì".

**Rủi ro còn lại, phải ghi rõ**: kết luận trên phụ thuộc layout model nhận ra bảng. Bảng công thức
**không kẻ khung, không bị nhận là `table`** (nhãn `plain text`) sẽ đi vào đường bình thường — chưa có
mẫu nào như vậy trong 6 đầu sách, nên đánh dấu `[CHƯA VERIFY]` cho sách ngoài bộ này. Guard `table`
ở trên **không** che được ca đó; khi đó chỉ còn cổng `m/L ≥ 0.6` + monotonic (cột công thức thật hiếm
khi không giảm vì dòng `Total` luôn lớn nhất và ở cuối, còn `Flour 100` thường ở đầu — trên
`figoni_p25` dãy là `[82,113,37,100]`, không đơn điệu).

**KHÔNG ĐỒNG Ý với cách Y7/Y12 mô tả "khe an toàn rộng" (TOC ≥ 1.0 vs văn xuôi tệ nhất 0.64)**:
- Đo trên IL (`visual_bbox`, đúng đặc trưng Y4 dùng): mục TOC Figoni cho tỷ lệ **1.05–1.21** (không phải
  1.00 — số 1.00 của Y2 đo bằng bbox advance của PyMuPDF, hai hệ đo khác nhau, Dev phải chọn 1 và chốt
  ngưỡng theo hệ đó).
- Trên **LCB**, tên mục dài đẩy sát số trang: `'Pâte à croissants—Croissant Dough 332'` = **0.43**,
  `'Crème Chantilly—Chantilly Cream 348'` = **0.66**, `'Crème Chibouste—Chiboust Cream 350'` = **0.81**,
  `'Crème d'amandes—Almond Cream 352'` = 1.00. Phân bố TOC **tràn xuống dưới 0.8**.
- Ngược lại, dòng slug in ấn nhãn `abandon` (`'c04.indd 62'`, có trên **mọi** trang Figoni, ký tự bị nhân
  đôi thành `cc0044..iinndddd6622`) qua được **toàn bộ** luật mức dòng với tỷ lệ **0.92–0.93** — chỉ bị
  chặn vì là paragraph 1 dòng.
⇒ Ngưỡng 0.8 là **thoả hiệp**, không phải "khe an toàn"; lớp chống FP thật sự là cổng paragraph
(`m ≥ 2`, `m/L ≥ 0.6`, monotonic) — điểm này TL cũng đã xếp là tín hiệu mạnh nhất, nhưng phần mô tả
"khe rộng" cần sửa lại để Dev không hạ ngưỡng xuống 0.5–0.6 "cho chắc" (sẽ dính slug 0.92 nếu có
trang nào gom 2 slug vào 1 paragraph). **Giữ 0.8**, và chấp nhận 2/84 mục LCB bị bỏ sót (hướng an toàn).

**Về phép quét toàn sách bằng PyMuPDF (Y8, "0 FP trên 4657 block")**: tôi đo độ nhạy của cách quét này
trên chính 2 trang Contents Figoni — 123/152 dòng thoả luật mức dòng nhưng **0 block** có ≥ 2 dòng như
vậy (PyMuPDF tách mỗi mục TOC thành block riêng); trên LCB Contents chỉ **2/184** dòng thoả luật (số
trang nằm ở span/line riêng). Một phép quét **không phát hiện nổi chính mục lục** thì "0 FP" của nó
gần như **không có trọng lượng bằng chứng** — TL đã tự cảnh báo (Y8 "không tương đương") nhưng vẫn
đưa vào Y0 như một điểm mạnh. Bằng chứng FP thật chỉ là các dump IL (11 trang cũ + 6 trang mới ở Z1).

#### Z4. Câu hỏi 2 — Cổng monotonic: **giữ làm điều kiện cứng; rủi ro "gom chéo cột" là lý thuyết**

- **Bằng chứng thật**: cả 2 mục lục 2 cột trong project (Figoni p7/p8: cột trái x≈102, cột phải x≈354;
  LCB p6/p7: x≈123–153 và x≈363–393) đều được layout model chia **vùng riêng cho từng khối/cột**
  (Figoni: `layout_id` 1–6 khác nhau cho từng khối; LCB: lid 2/3/12 trái, 4/5/1 phải). **31/31**
  paragraph kích hoạt đều có dãy số không giảm; **không có** paragraph nào bị cổng này chặn.
- **Lập luận cấu trúc** (đọc `:747-776`): dòng trong paragraph được tạo bằng **phân cụm theo y** rồi sắp
  từ trên xuống. Nếu một vùng layout ôm cả 2 cột, ký tự cột trái và cột phải **cùng y sẽ dính vào cùng
  một `PdfLine`** (`'Mục trái 12   Mục phải 210'`) — dãy số cuối dòng khi đó chỉ là số của cột phải,
  **vẫn không giảm**. Ca "dãy số giảm ở chỗ nhảy cột" chỉ xảy ra khi vùng layout ôm 2 cột **và** 2 cột
  không giao nhau theo y (cột 2 bắt đầu ở đầu trang sau khi cột 1 kết thúc giữa trang) — chưa gặp, và
  khi đó vấn đề thật là dòng bị trộn chéo cột (TOC-1 không sửa được, cổng nào cũng vô nghĩa).
- Vì cổng này chưa từng "bắt" được gì trên dữ liệu, giá trị chống FP của nó **chưa được chứng minh**
  (nhưng cũng không tốn gì). Giữ, log khi nó chặn để 7.4-e có số liệu.

#### Z5. Câu hỏi 3 — Điểm hook `process_independent_paragraphs`: **ĐỒNG Ý, và lý do mạnh hơn TL nêu**

Tôi trace từng bước sau `:287`:

- **(a) `merge_alternating_line_number_paragraphs` `:290-291`** (config `merge_alternating_line_numbers`
  mặc định `True`, `translation_config.py:207`): guard `xobj_id is not None` **không có tác dụng** (Z2).
  Bảo vệ thật: (1) TOC-1 chỉ tạo paragraph chứa chữ ⇒ không bao giờ là "l"; (2) để "a l+ c" gộp cần 1
  paragraph thuần số **chen giữa** 2 paragraph TOC-1 vừa tách **cùng `layout_id`** — TOC-1 chèn liền kề
  (`insert(i+1)`), nên không có gì chen giữa. Trường hợp gần nhất trong dữ liệu là **Bo Friberg**: số
  trang là paragraph thuần số riêng (`'207'` lid=27, `'259'` lid=32…) xen kẽ tiêu đề — nhưng mỗi mục có
  `layout_id` riêng ⇒ `_same_layout_and_xobj` False ⇒ không gộp. Kết luận an toàn của TL **đứng vững**,
  nhưng Dev **không được** viết test/comment dựa vào guard `xobj_id`.
- **(b) `fix_overlapping_paragraphs` `:302`** (`:939-1030`): chỉ sửa **`paragraph.box`** (y/y2 về
  `mid ± 1`), không đụng composition, và chỉ khi 2 box giao nhau 2D. Đo thật: sau khi tách từng dòng
  trên Figoni p7/p8, khe dọc giữa 2 group liên tiếp = **2.85–2.95 pt** (âm = không giao) trên **toàn bộ
  66 điểm tách** ⇒ no-op. Với sách có leading chặt (font 10/pitch 11) box có thể giao < 1pt ⇒ mỗi box bị
  cắt ~1pt+ ⇒ khung typeset nhỏ đi một chút. Đây là **khác biệt hành vi có thật so với hook 7.2** (chạy
  sau `:302`), nhưng cùng cách babeldoc đối xử paragraph do chính nó tách — chấp nhận được, ghi vào
  7.4-e để đo.
- **(c) `:293-294` `update_paragraph_data(paragraph, update_unicode=True)`** — TL **không liệt kê**, và
  đây là lý do quan trọng nhất để hook sớm: chỉ lời gọi này mới ghi `paragraph.unicode` (`:147-148`).
  Paragraph tạo **sau** `process()` (cách 7.2 đang làm) không bao giờ đi qua đây ⇒ xem Z6.
- **(d) `add_debug_info` `:307`** chỉ khi `--debug`; **(e) `_set_paragraph_render_order` `:310`** gán
  đúng cho paragraph mới. ✅ như TL nói.
- **(f) Tương tác với patch 7.2** (bọc `process`, chạy sau toàn bộ `process_page`): 7.2 duyệt lại
  `page.pdf_paragraph` gồm cả paragraph TOC-1 mới; mục TOC không có marker đầu dòng dạng `\d{1,3}[.)]\s`
  (LCB `'1. History of Pâtisserie in France 2'` là paragraph 1 dòng ⇒ 7.2 bỏ qua) ⇒ không xung đột.

**Không có bước nào trong `:288-310` phá hoặc gộp lại paragraph TOC-1 tạo ra** — xác nhận Y6, thêm (b)
là điểm cần đo, (c) là điểm cần tận dụng.

#### Z6. PHÁT HIỆN QUAN TRỌNG NHẤT — 7.2 đang ship với bug thật: paragraph tách ra **không được dịch**

**Cơ chế** (đọc source, không suy đoán):
1. `sitecustomize.py:219-227` tạo `PdfParagraph(unicode="")` rồi gọi `self.update_paragraph_data(new_paragraph)`
   với `update_unicode` mặc định `False` ⇒ `unicode` **vẫn là `""`**; paragraph gốc (`:216`) giữ
   `unicode` **cũ** chứa cả các dòng đã bị cắt đi (stale).
2. Không stage nào giữa ParagraphFinder và ILTranslator tính lại `unicode`
   (`high_level.py:274-281`: StylesAndFormulas, AutomaticTermExtractor không ghi field này — grep toàn
   `midend/` chỉ có `il_translator.py:1004/1232` và `il_translator_llm_only.py:835/861`, đều là ghi **sau**
   khi dịch).
3. Translator đang dùng là `ILTranslatorLLMOnly` (CHANGELOG 7.2 trích log `il_translator_llm_only.py:828`).
   Cổng vào `:556-568`: `if paragraph.unicode is None: continue` … `if len(paragraph.unicode) <
   min_text_length: continue` với `min_text_length = 5` (`translation_config.py:187`, app không truyền
   `--min-text-length`). `len("") < 5` ⇒ paragraph **bị bỏ qua hoàn toàn, không gửi LLM, không log**.
   Paragraph gốc không bị ảnh hưởng vì text gửi LLM dựng từ composition
   (`pre_translate_paragraph`, `il_translator.py:954+`, `text = translate_input.unicode`), `unicode` stale
   chỉ dùng cho đếm token.

**Bằng chứng sống (artifact 7.2 còn nguyên trong `/tmp/bdprobe`)**:
- Dump `wd72c/page14_numbered_list_source/paragraph_finder.json`: đúng **4 paragraph** có
  `unicode=''`, `render_order=None` — `'12. Stovetop burners'`, `'24. Stainless steel saucepans…'`,
  `'32. Cutting boards'`, `'34. Cups for water'` — chính là 4 paragraph 7.2 tạo ra (cặp 11+12, 23+24,
  31+32, 33+34 ghi ở CHANGELOG 7.2).
- PDF output live `live72/page14_numbered_list_source.no_watermark.vi.mono.pdf` (đọc text bằng PyMuPDF):
  `11. Lò nướng…` (Việt) → **`12. Stovetop burners` (Anh)** → `13. Khay nướng…` (Việt); tương tự
  **`24. Stainless steel saucepans, heavy`**, **`32. Cutting boards`**, **`34. Cups for water`** giữ nguyên
  tiếng Anh, mọi mục lân cận đều Việt.
- Dump `wd74c/p74_77/paragraph_finder.json`: **10 paragraph** `unicode=''` = câu hỏi **#3, #5, #7,
  #9–15** — **trùng khớp từng số** với danh sách CHANGELOG 7.2 "bị babeldoc fallback về giữ nguyên
  tiếng Anh (#3, #5, #7, #9-15)".

⇒ CHANGELOG 7.2 mục "Quan sát thêm" **chẩn đoán sai**: không phải LLM trả kết quả xấu (`:828` fallback),
mà là shim **tự làm paragraph vô hình** với translator. Gate R6-03 của 7.2 ("35/35 mục xuống dòng
đúng") đo **cấu trúc dòng**, không đo **"mục đã được dịch chưa"** — đúng loại lỗ hổng Protocol 6 R6-03
cảnh báo (tin cấu trúc, không đọc nội dung cuối). Trên production hiện nay, **mọi mục numbered-list từ
mục thứ 2 của mỗi cụm bị dính** đang ra tiếng Anh.

**Fix** (1 dòng + 1 dòng, ngoài phạm vi Ca C, **hotfix riêng qua Reviewer trước 7.4**):
`self.update_paragraph_data(new_paragraph, update_unicode=True)` và
`self.update_paragraph_data(paragraph, update_unicode=True)` ở `sitecustomize.py:216/227`, cộng
`new_paragraph.render_order = paragraph.render_order` (Y10-b). Hoặc triệt để hơn: dời 7.2 sang cùng
hook `process_independent_paragraphs` như TOC-1 để `:293-294`/`:310` tự lo — nhưng TL đã lý luận đúng
rằng không mở lại 7.2 trong cùng task; tôi đồng ý, **hotfix tối thiểu trước, dời hook sau**.
Golden-fixture test của 7.2 **phải thêm assertion** `unicode != ""` và `render_order is not None` cho
paragraph mới — đúng tinh thần R6-02 (assert giá trị truyền sang bước sau, không chỉ số nhóm). Cùng
assertion đó là **bắt buộc** cho test 7.4-c.

#### Z7. Phát hiện khác ngoài 3 câu hỏi

- **(a) Quy ước "số trang ở dòng ĐẦU của mục xuống dòng" — Bo Friberg, ngược với giả định Y2-4.**
  PyMuPDF rawdict idx 6: `'Chapter 8   Tea Cakes, Pound Cakes, Muffins, and Other '` y=385–395,
  `'383'` y=386.5–394.5 (**cùng dòng**), `'Quick Breads'` y=397–407 (dòng sau); IL cũng vậy
  (`'Chapter 10 Basic Chocolate Work and Decorating 451 | Techniques'`, `'…Bavarian 755 | Creams'`).
  Bước 3 của Y4 ("tách NGAY SAU dòng có số") sẽ **xé dòng nối `Techniques`/`Creams` sang mục kế tiếp**
  nếu 2 mục như vậy nằm chung 1 paragraph 3 dòng (`m/L = 2/3` ⇒ kích hoạt). Trên trang này chưa xảy
  ra chỉ vì layout model tách từng mục thành paragraph riêng — nhưng đây là sách thứ 2 trong chính
  `data/uploads/` dùng quy ước ngược, không thể coi là ngoại lệ. **Đề xuất luật nối dòng**: dòng không
  đánh dấu đứng **ngay sau** dòng đánh dấu, có `x` đầu dòng **thụt vào** hơn dòng đánh dấu (Friberg:
  284 vs 230) ⇒ thuộc group **trước**; ngược lại (Figoni `'Flour and Dough Additives and'` cùng x với
  `'Treatments 72'`; LCB `'Pâte sucrée—Sweet Shorcrust'` cùng x với các mục) ⇒ thuộc group **sau** như
  hiện tại. Đã kiểm luật này bằng tay trên 3 sách — `[CHƯA VERIFY]` với sách khác; 7.4-a phải có 1
  fixture Friberg.
- **(b) Recall trên LCB không phải 100%**: 84 dòng mục có số trang trên 2 trang Contents; sau TOC-1 còn
  **2 cặp dính** (332+336, 348+350 — 2 dòng tỷ lệ 0.43/0.66 ở Z3). Ngoài ra babeldoc gốc (nhánh
  short-line `:891-895`, flag production `--split-short-lines 0.8`) đã cắt sẵn nhiều mục xuống dòng
  thành nửa-mục nằm ở 2 paragraph khác nhau (`'…Sweet Shorcrust'` cuối para 82, `'Pastry 326'` đầu para
  83; para 84 = `'Dough 340 | Les Crèmes et Meringues—'`, `m = 1` ⇒ TOC-1 không chạm) — không phải lỗi
  TOC-1, nhưng Y9 nên ghi "đã thấy khớp trên 2 đầu sách" thành **"Figoni 20/20, LCB ~82/84"**.
- **(c) `str.isdigit()` nhận cả chữ số trên (`'²'.isdigit() == True`)** — chú thích cuối dòng
  (`'…flour²'`) có khe 0 nên không kích hoạt, nhưng nên dùng **ASCII `0-9`** cho `k` để khỏi phụ thuộc
  khe. Nhỏ, sửa khi implement.
- **(d) Không có gì ở tầng IL để TOC-1 dựa vào cho Friberg**: số trang là paragraph riêng (font 8pt,
  x=526) ⇒ Ca C trên sách kiểu này nằm ở tầng **layout/paragraph grouping**, ngoài tầm TOC-1. Ghi vào
  Y9 như một biên rõ ràng ("số trang tách thành paragraph riêng ⇒ không xử lý").
- **(e) FP-7 (index) verify thật**: LCB Subject Index, 16 paragraph nhiều dòng, **0** kích hoạt (khe sau
  dấu phẩy ≈ khoảng trắng từ). Y12 có thể chuyển FP-7 sang ✅ Verified với fixture `lcb_index`.

#### Z8. Khuyến nghị

**Tiếp tục sang spike 7.4-a — CÓ**, với thứ tự và sửa đổi sau:

0. **Trước 7.4 (P0, task riêng, qua Reviewer)**: hotfix 7.2 theo Z6 (`update_unicode=True` cho cả 2
   paragraph + copy `render_order`), re-run live E2E 7.2 với gate mới **"0 mục còn tiếng Anh"** (đếm
   residue bằng regex chữ Anh/không dấu trên text output), sửa lại đoạn "Quan sát thêm" của CHANGELOG
   7.2 cho đúng nguyên nhân. Nếu bỏ qua bước này, TOC-1 sẽ kế thừa cùng lỗi nếu Dev copy nguyên
   `_split_numbered_list_paragraphs_on_page`.
1. **Giữ**: hook `process_independent_paragraphs` (Y6), ngưỡng 0.8 theo `visual_bbox`, `m ≥ 2`,
   `m/L ≥ 0.6`, monotonic **cứng**, không hỗ trợ La Mã, TOC-1b tắt.
2. **Thêm**: (i) guard bỏ qua paragraph có tâm trong box layout `table` (Z3); (ii) luật dòng nối theo
   thụt đầu dòng (Z7-a); (iii) `k` chỉ đếm ASCII digit (Z7-c); (iv) log 1 dòng mỗi khi cổng monotonic
   hoặc cổng `m/L` chặn một paragraph có `m ≥ 2` — để 7.4-e có số liệu thay vì tin lý thuyết.
3. **Fixture 7.4-a phải gồm** (tất cả đã có lệnh tái tạo ở Z1): Figoni Contents p7+p8, **LCB Contents
   p6+p7** (2 cột, recall ≠ 100%, oracle: 82/84), **Friberg Contents** (quy ước ngược, oracle: 0 tách
   sai + `Techniques`/`Creams` không bị xé nếu dựng ca tổng hợp), Figoni p25 công thức (FP-4 oracle: 0),
   LCB index p408 (FP-7 oracle: 0). Không cần trang references riêng — cơ chế giống index.
4. **Gate 7.4-d (R6-03) phải đo 2 thứ, không chỉ 1**: số block/ranh giới mục (như Y11) **và** số mục
   còn tiếng Anh trong output (Z6 chứng minh gate thứ 2 mới bắt được lỗi thật).
5. **Sửa văn bản Y7/Y12**: bỏ mô tả "khe an toàn rộng 0.64 vs 1.0", thay bằng phân bố thật (Z3); hạ
   trọng số bằng chứng "0 FP/4657 block PyMuPDF" xuống mức "không dùng làm bằng chứng"; sửa `:247`
   thành `:245`; sửa lập luận `xobj_id is not None` (Z2).

**Bảng trạng thái verify của riêng section này (R5-01)**

| Claim | Trạng thái |
|---|---|
| FP-4 không kích hoạt trên 3 trang công thức Figoni (ô bảng = paragraph 1 dòng) | ✅ Verified — dump IL mới, Z1 |
| FP-7 không kích hoạt trên LCB index | ✅ Verified — dump IL mới |
| TOC-1 tái mô phỏng khớp 20/20, 66 điểm tách | ✅ Verified — script riêng trên dump 7.3 |
| LCB Contents: 11 paragraph kích hoạt, 64 điểm tách, 2/84 mục sót, monotonic 11/11 | ✅ Verified — dump IL mới |
| Friberg: số trang ở dòng đầu mục xuống dòng | ✅ Verified — rawdict y + dump IL |
| 7.2 tạo paragraph `unicode=''` ⇒ translator bỏ qua ⇒ giữ tiếng Anh | ✅ Verified — source (`sitecustomize.py:227`, `il_translator_llm_only.py:556-568`, `translation_config.py:187`) + dump `wd72c`/`wd74c` + PDF `live72` |
| `xobj_id = 0` (không phải `None`) cho nội dung chính | ✅ Verified — 9 dump |
| `fix_overlapping_paragraphs` no-op trên TOC Figoni (khe 2.85–2.95pt) | ✅ Verified — đo box theo `visual_bbox` kể cả dummy space |
| Luật dòng nối theo thụt đầu dòng đúng cho sách ngoài 3 cuốn đã xem | ⚠️ `[CHƯA VERIFY]` |
| Bảng công thức không bị layout model nhận là `table` (nhãn `plain text`) có kích hoạt TOC-1 không | ⚠️ `[CHƯA VERIFY]` — chưa có mẫu |
| Giá trị chống FP thực tế của cổng monotonic | ⚠️ Chưa chứng minh — chưa từng chặn gì trên dữ liệu |

---

### Bug #7 Ca C — Quyết định cuối sau phản biện Domain Expert + kế hoạch spike 7.4-a (Tech Lead, 2026-09-08)

> **ĐÂY LÀ QUYẾT ĐỊNH CUỐI ĐỂ GIAO DEV.** Section này **thay thế** phần thiết kế Y4/Y7/Y10/Y11 của
> mục "Bug #7 Ca C — Đề xuất thiết kế fix mục lục" (Y0–Y13 giữ nguyên làm hồ sơ điều tra). Nơi nào
> mâu thuẫn, **section này thắng**. Không còn bước "chờ duyệt thêm" — Protocol 2 đã qua ở vòng
> trước; việc tiếp theo là Dev chạy spike 7.4-a theo AA8.
>
> Viết theo đúng khuôn mẫu "Bug #7/#8 — Final Decision sau phản biện Domain Expert" (X0–X10): trả
> lời **từng** điểm phản biện, rồi chốt.

#### AA0. Phán quyết một dòng

Domain Expert **đúng ở 9/10 điểm**, gồm cả điểm quan trọng nhất (Z6 — bug `unicode=""` của 7.2, đã
hotfix ở `a31ac42`). Tôi **KHÔNG ĐỒNG Ý đúng 1 điểm**: đề xuất Z8-2(i) *"guard bỏ qua paragraph có
tâm nằm trong box layout `table`"*. Tôi đã tự đo và guard đó **giết 5/11 paragraph mục lục + 24/64
điểm tách của Le Cordon Bleu** (trang Contents thứ 2 của LCB **bị chính layout model gán nhãn
`table`**), trong khi **không cứu được gì** trên cả 3 trang công thức bánh (ở đó TOC-1 vốn đã kích
hoạt 0 lần, và **không paragraph nhiều dòng nào** có tâm trong box `table`). Thay bằng một guard
khác **rẻ hơn, mạnh hơn, không mất recall**: **deny-list theo `paragraph.layout_label`** — bằng
chứng ở AA3.

Thiết kế chốt là **TOC-1 v2** (AA4/AA5/AA6). Oracle cuối cùng, tự đo lại trong task này trên **12 bộ
dump IL thật**: **31 paragraph kích hoạt / 130 điểm tách** trên 4 trang mục lục, **0 kích hoạt** trên
**8 trang không phải mục lục** (3 trang công thức/bảng, 1 trang index, 4 trang văn xuôi/list).

#### AA1. Tôi đã tự verify lại những gì trong task này (Protocol 5 R5-01)

**Không kế thừa số liệu của ai.** Tôi viết script riêng (`toc1_v2.py`, không dùng `toc1_sim.py` của
Expert, không dùng script của vòng Y) và chạy trên dump IL thật:

| Việc | Kết quả |
|---|---|
| Tái tạo số liệu của Expert trên LCB | ✅ **Khớp tuyệt đối**: 11 paragraph kích hoạt, 64 điểm tách (6 fire/40 cut ở p0 + 5 fire/24 cut ở p1), monotonic 11/11 |
| Tái tạo số liệu của vòng Y trên Figoni | ✅ **Khớp tuyệt đối**: p7 = 8 fire/28 cut, p8 = 12 fire/38 cut ⇒ **20 paragraph / 66 điểm tách** |
| `paragraph_finder.py:245` là `page.pdf_paragraph = paragraphs` | ✅ Đọc trực tiếp — **Expert đúng**, Y12 ghi nhầm `:247` |
| `_same_layout_and_xobj` (`:382-391`) có đòi `xobj_id is not None` | ✅ Source đúng như Y1 ghi, **nhưng suy luận của Y1 sai**: đo trên dump thật, `xobj_id` chỉ nhận **`-1`** (101 paragraph rỗng) và **`0`** (56 paragraph nội dung) trên `figoni_p25_recipe` — **không bao giờ `None`** ⇒ guard đó **không chặn gì**. Expert đúng; Expert ghi "`= 0`", chính xác hơn là **`0` hoặc `-1`, không bao giờ `None`** |
| `page.page_layout` có `class_name` + `box` + `id` để làm guard bảng | ✅ Verified — `figoni_p25_recipe` có 101 entry: `fallback_line`×82, `abandon`×9, `title`×4, `plain text`×3, **`table`×3** |
| Guard `table` theo hình học có mất recall không | ✅ **Verified — CÓ, mất nặng** (AA3) |
| Nhãn của **mọi** paragraph kích hoạt TOC-1 | ✅ **31/31 đều là `'plain text'`** — không có `title`, `abandon`, `table`, `fallback_line` nào |
| Slug in ấn `abandon` lọt luật mức dòng | ✅ Verified — LCB `'57131_fm_i_xv.indd 5'` ratio **0.82**, Figoni `'c04.indd 62'` ~0.92 (Expert). Chỉ thoát vì là paragraph **1 dòng** |
| Độ nhạy ngưỡng `TOC_GAP_RATIO` | ✅ Quét 0.5 → 1.0 trên **12 dump**: FP **luôn = 0**, recall chỉ đổi 131 → 128 điểm tách. **Ngưỡng KHÔNG phải bộ lọc chính** (AA2/Z3) |
| Luật dòng nối theo thụt đầu (Z7-a) có phải no-op trên dữ liệu hiện có | ✅ Verified — **6 ranh giới "dòng đánh dấu → dòng không đánh dấu"** trong toàn bộ paragraph kích hoạt, delta thụt đầu dòng = **−13.0, −1.1, +0.0, +0.0, +0.0, +0.1 pt** ⇒ với ngưỡng 1.0 em, **no-op tuyệt đối** |
| Hotfix Z6 đã ship chưa | ✅ Commit `a31ac42` — `update_unicode=True` cho **cả 2** lời gọi. ⚠️ **`render_order` KHÔNG được copy** (grep `render_order` trong `src/babeldoc_shim/sitecustomize.py` = 0 hit) ⇒ nợ Y10-b **vẫn còn nguyên** |

**Nguồn dữ liệu (còn sống, đã kiểm tra hôm nay 2026-09-08)** — 6 dump mới của Expert **và** PDF nguồn
đã trích sẵn, nằm tại
`/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad/`
(`pdfs/*.pdf`, `wd/<tên>/<tên>/paragraph_finder.json`, `run_all.sh` để tái tạo). Cộng 6 dump cũ ở
`/tmp/bdprobe/wd_toc*`, `/tmp/bdprobe/wd74c`, `/tmp/bdprobe/wd72c`, `/tmp/bdprobe/wd_p20`,
`/tmp/bdprobe/wd_p22`. **Đây vẫn là artifact tạm** — nhiệm vụ số 1 của 7.4-a là commit golden fixture
(AA8 bước 1).

#### AA2. Trả lời từng điểm phản biện của Domain Expert

| # | Điểm Expert nêu | Phán quyết | Lý do |
|---|---|---|---|
| Z2-a | Y12 ghi `:247`, đúng là `:245` | ✅ **ĐỒNG Ý** | Tự đọc lại source. Đính chính ở AA11 |
| Z2-b / Z5-a | Lập luận "guard `xobj_id is not None` chặn `merge_alternating_line_number_paragraphs`" là **SAI** | ✅ **ĐỒNG Ý** | Tự đo: `xobj_id ∈ {0, −1}`, không bao giờ `None`. **Kết luận "không bị gộp lại" vẫn đứng**, nhưng nhờ `_is_ascii_digit_or_space_paragraph` (paragraph TOC-1 luôn có chữ) + `layout_id` phải trùng + TOC-1 chèn liền kề nên không có paragraph thuần số chen giữa. **Dev bị CẤM** viết test/comment dựa vào guard `xobj_id` |
| Z3-a | FP-4 (bảng công thức) **không kích hoạt** vì layout model đã tách mỗi ô thành paragraph `fallback_line` 1 dòng | ✅ **ĐỒNG Ý** — tự đo lại 3 trang, xác nhận 0 kích hoạt. Đây là rủi ro `[UNVERIFIED]` lớn nhất của Y12, **nay đóng lại** ở mức "3 trang công thức thật của cuốn chính" | Bổ sung của tôi: trên cả 3 trang, **số paragraph nhiều dòng có tâm trong box `table` = 0** — tức FP-4 không những không xảy ra, mà còn **không thể** được cứu bởi guard `table` |
| Z3-b | Nếu cột công thức có bị tách từng dòng thì đó là **cải thiện**, không phải hỏng | ✅ **ĐỒNG Ý** | Đúng bản chất Ca C. Rủi ro duy nhất còn lại là `unit_count`/mode-scale (X7) — giữ ràng buộc thứ tự 7.4 trước 8.1 |
| Z3-c | **Đề xuất guard `table` theo hình học** | ❌ **KHÔNG ĐỒNG Ý — BÁC BỎ** | Chi tiết bằng chứng ở **AA3**. Thay bằng deny-list `layout_label` |
| Z3-d | Mô tả "khe an toàn rộng (TOC 1.0 vs văn xuôi 0.64)" là **sai/gây hiểu nhầm** | ✅ **ĐỒNG Ý** | Tự đo thêm: quét ngưỡng 0.5→1.0 trên 12 dump cho FP = 0 ở **mọi** ngưỡng, recall chỉ đổi 131→128. Ngưỡng **không** là bộ lọc; **cổng cố kết paragraph mới là**. Giữ 0.8 vì đó là ngưỡng đã có nhiều dữ liệu nhất, **không** vì "khe an toàn". Đính chính ở AA11 |
| Z3-e | "0 FP / 4657 block PyMuPDF" **gần như không có trọng lượng bằng chứng** (phép quét đó không phát hiện nổi chính mục lục) | ✅ **ĐỒNG Ý HOÀN TOÀN** | Rút khỏi mọi lập luận. Bằng chứng FP hợp lệ **chỉ còn** 12 bộ dump IL. Đính chính ở AA11 |
| Z4 | Giữ cổng monotonic làm **điều kiện cứng**; rủi ro "gom chéo cột" là lý thuyết | ✅ **ĐỒNG Ý** | Tự xác nhận 31/31 paragraph kích hoạt đều monotonic, **0** paragraph bị cổng này chặn. Chấp nhận Z8-2(iv): **log 1 dòng mỗi lần cổng chặn** để 7.4-e có số liệu thật thay vì lý thuyết |
| Z5-c | Hook sớm còn được `update_paragraph_data(..., update_unicode=True)` ở `:293-294` — **TL bỏ sót, và đây là lý do mạnh nhất** | ✅ **ĐỒNG Ý, và nâng lên lý do #1** | Chính là cơ chế gây Bug Z6 cho 7.2. Hook `process_independent_paragraphs` khiến TOC-1 **miễn nhiễm** với lớp lỗi đó **theo thiết kế**, không phải nhờ nhớ gọi đúng cờ. Cập nhật thứ tự lý do ở AA6 |
| Z5-b | `fix_overlapping_paragraphs` (`:302`) chỉ sửa `box`, no-op trên Figoni (khe 2.85–2.95pt), nhưng là **khác biệt hành vi thật** so với hook 7.2 | ✅ **ĐỒNG Ý** | Đưa vào gate đo của 7.4-e (AA8 bước 6) |
| Z6 | 7.2 ship với bug `unicode=""` ⇒ paragraph tách ra **không được dịch** | ✅ **ĐỒNG Ý — phát hiện đúng và quan trọng nhất của cả vòng phản biện** | Đã hotfix `a31ac42`, Reviewer APPROVE, live 0/35 + 0/40 mục còn tiếng Anh. **Điều kiện tiên quyết Z8-0 coi như ĐÃ THOẢ.** ⚠️ Phần `render_order` của Z8-0 **chưa làm** — xem AA10-b |
| Z7-a | Bo Friberg đặt số trang ở **dòng ĐẦU** của mục xuống dòng ⇒ cần luật dòng nối theo thụt đầu dòng | ✅ **ĐỒNG Ý CÓ ĐIỀU KIỆN — nhận vào thiết kế** | Tự đo: trên **toàn bộ** 6 ranh giới "đánh dấu → không đánh dấu" của 31 paragraph kích hoạt, thụt đầu dòng = −13.0 … +0.1 pt ⇒ với ngưỡng **1.0 × font_size** luật này là **no-op tuyệt đối** trên dữ liệu hiện có (Friberg: 284 vs 230 = **6.75 em**, cách ngưỡng rất xa). Nhận vì rẻ + hướng thất bại an toàn; **điều kiện**: spike phải chứng minh nó là no-op (gate AA9-4) |
| Z7-b | Recall LCB là ~82/84, không phải 100% | ✅ **ĐỒNG Ý** | Sửa Y9 (AA11). Ghi thành chỉ tiêu gate riêng cho LCB |
| Z7-c | Dùng ASCII `0-9` thay `str.isdigit()` (`'²'.isdigit()` là True) | ✅ **ĐỒNG Ý** | Vào spec AA4 bước 2 |
| Z7-d | Friberg: số trang là paragraph **riêng** ⇒ Ca C của sách kiểu này nằm ngoài tầm TOC-1 | ✅ **ĐỒNG Ý** | Ghi thành **biên thiết kế tường minh** (AA4, bảng biên). Tự xác nhận: TOC-1 v2 kích hoạt **0** trên `friberg_toc` — đúng như dự đoán, và đây là **kết quả mong đợi**, không phải FN cần sửa |
| Z7-e | FP-7 (index) đã verify thật trên LCB index | ✅ **ĐỒNG Ý** | Chuyển FP-7 sang ✅ Verified (AA12) |
| Z8-4 | Gate 7.4-d phải đo **2** thứ: ranh giới mục **và** số mục còn tiếng Anh | ✅ **ĐỒNG Ý — bắt buộc** | Vào gate AA9-6. Chính là bài học R6-03 từ Z6 |

#### AA3. Điểm KHÔNG ĐỒNG Ý — bác bỏ guard `table` theo hình học (Z8-2 mục i)

Expert đề xuất: *"bỏ qua paragraph có tâm nằm trong box layout `table`"*. Tôi đã cài đúng luật đó vào
mô phỏng và đo trên **cùng** bộ dump Expert dùng:

| Dump | Không guard | **Có guard `table` hình học** |
|---|---|---|
| `lcb_toc` trang 0 | 6 fire / 40 cut | 6 fire / 40 cut |
| **`lcb_toc` trang 1** | **5 fire / 24 cut** | **0 fire / 0 cut** ❌ |
| `figoni_p7_toc` | 8 fire / 28 cut | 8 fire / 28 cut |
| `figoni_p8_toc` | 12 fire / 38 cut | 12 fire / 38 cut |
| `figoni_p25_recipe`, `figoni_p45_recipe`, `figoni_p7_tables` (3 trang công thức/bảng) | 0 / 0 | 0 / 0 (**không cứu được gì**) |
| `lcb_index`, `friberg_toc` | 0 / 0 | 0 / 0 |

**Nguyên nhân**: layout model của babeldoc gán **1 box `class_name="table"`** phủ gần trọn trang
Contents thứ 2 của Le Cordon Bleu (mục lục 2 cột **trông giống bảng**) — **8/8** paragraph nhiều dòng
của trang đó có tâm nằm trong box ấy. Guard sẽ **xoá 37.5% tác dụng của fix trên chính cuốn sách thứ 2
dùng để chứng minh tính tổng quát**.

**Và guard đó không thể cứu FP-4 ngay cả về nguyên tắc**: trên cả 3 trang công thức/bảng, số paragraph
**nhiều dòng** có tâm trong box `table` = **0** (đo thật). Lý do chính là điều Expert đã chỉ ra ở Z3:
trong vùng bảng, mỗi ô thành **paragraph 1 dòng** `fallback_line` ⇒ `L < 2` ⇒ TOC-1 không xét. Còn ca
FP-4 thật sự đáng sợ — **bảng công thức không kẻ khung, bị gán nhãn `plain text`** (Expert tự đánh dấu
`[CHƯA VERIFY]`) — thì **theo định nghĩa không có box `table`** nên guard cũng vô hiệu. ⇒ Guard này là
**toàn chi phí, không lợi ích**.

**Thay bằng: deny-list theo `paragraph.layout_label`** (rẻ hơn, không phụ thuộc hình học, đo được):

- Bằng chứng recall: **31/31** paragraph kích hoạt trên 4 trang mục lục đều có `layout_label ==
  'plain text'` ⇒ deny-list **không mất một điểm tách nào** (đã chạy: 20/66 Figoni + 11/64 LCB giữ
  nguyên sau khi bật deny-list).
- Bằng chứng phòng thủ: lớp nội dung **có tỷ lệ khe cao nhất** trong toàn bộ dữ liệu mà **không phải**
  mục lục là **slug nhà in nhãn `abandon`** (`'57131_fm_i_xv.indd 5'` = 0.82; Figoni `'c04.indd 62'` ≈
  0.92). Hôm nay chúng chỉ thoát nhờ là paragraph 1 dòng — **một sự may mắn, không phải một luật**.
  Deny-list biến may mắn đó thành luật.

Nếu sau này có bằng chứng thật về FP trong vùng bảng, mở lại — **nhưng lúc đó phải là luật khác**, vì
guard hình học đã chứng minh là chọn nhầm trục.

Để không mất dấu: TOC-1 v2 **vẫn tính** cờ "tâm paragraph nằm trong box `table`" và **chỉ ghi log**
(`toc_split: fired_inside_table_box=N`), không dùng để chặn. 7.4-a/7.4-e báo cáo con số này.

#### AA4. TOC-1 v2 — thiết kế CHỐT (thay thế Y4)

Toàn bộ quyết định nằm trong module thuần Python `src/babeldoc_shim/toc_split.py` (không import
babeldoc), dùng chung bởi `sitecustomize.py` và test — đúng khuôn `numbered_list_split.py` của 7.2
(R6-02: test phải gọi **đúng** logic production).

**Bước 0 — cổng paragraph (MỚI, thay guard `table` của Expert)**
Bỏ qua ngay nếu `paragraph.layout_label` (chuẩn hoá lower/strip) thuộc **deny-list**:
`abandon`, `header`, `footer`, `page_header`, `page_footer`, `table`, `table_cell`, `wired_table_cell`,
`wireless_table_cell`, `table_cell_hybrid`, `table_text`, `table_caption`, `table_footnote`, `figure`,
`figure_caption`, `figure_text`, `formula`, `isolate_formula`, `formula_caption`.
Bỏ qua nếu số composition `L < 2`.
(Tên nhãn lấy từ tập hợp lệ trong `utils/layout_helper.py:655-690` và `:789-845` của babeldoc 0.6.4 —
đã đọc thật.)

**Bước 1 — chuẩn bị ký tự của một dòng**
Lấy `composition.pdf_line.pdf_character`, **bỏ mọi ký tự `.isspace()`** (gồm dummy space do
`add_space_dummy_chars` chèn, `paragraph_finder.py:279`), rồi **tự sort theo `visual_bbox.box.x`** —
bắt buộc, vì cả 4 lời gọi sort của babeldoc đều bị comment (`:305,696,738,772`, X4-4). Bỏ qua dòng có
< 2 ký tự.

**Bước 2 — đánh dấu "đuôi mục TOC"** (tất cả điều kiện phải đúng)
1. `k` = độ dài dãy **ASCII `0-9`** liền cuối (**không** dùng `str.isdigit()` — Z7-c). Loại nếu
   `k == 0`, `k > TOC_MAX_DIGITS`, hoặc `k == len(chars)` (cả dòng là số ⇒ folio/ô bảng).
2. Phần thân (`chars[:-k]`) phải chứa **≥ 1 cụm ≥ 2 chữ cái ASCII** (`[A-Za-z]{2,}`).
3. `1 ≤ n ≤ 9999` với `n` = giá trị dãy số.
4. `size = chars[-k-1].pdf_style.font_size`; bỏ qua nếu `size <= 0`.
5. `gap = chars[-k].visual_bbox.box.x − chars[-k-1].visual_bbox.box.x2`
   (**hệ đo bắt buộc: `visual_bbox`** — chốt theo Z3, KHÔNG dùng advance-width của PyMuPDF).
6. `ratio = gap / size ≥ TOC_GAP_RATIO`.

**Bước 3 — cổng cố kết ở mức paragraph** (lớp chống FP **chính**, không phải ngưỡng ở bước 2)
`m` = số dòng đánh dấu, `L` = số composition. Chỉ tách khi **cả ba**:
`m ≥ TOC_MIN_TAIL_LINES` **và** `m / L ≥ TOC_MIN_TAIL_FRACTION` **và** dãy `n` **không giảm**
(cho phép bằng nhau). Khi cổng `m/L` hoặc monotonic chặn một paragraph có `m ≥ 2`, **ghi log 1 dòng**
(Z8-2 iv).

**Bước 4 — điểm tách + luật dòng nối (MỚI, Z7-a)**
Với mỗi dòng đánh dấu ở chỉ số `i`: đặt `j = i`; **trong khi** composition `j+1` tồn tại, là `pdf_line`
**không** được đánh dấu, và `min_x(dòng j+1) ≥ min_x(dòng i) + TOC_CONT_INDENT_EM × size(dòng i)`
⇒ `j += 1` (dòng nối kiểu Bo Friberg thuộc **group trước**). Ranh giới nằm **ngay sau** composition `j`;
bỏ nếu `j == L-1`.
Composition không phải `pdf_line` (`pdf_formula`, `pdf_character`) không bao giờ được đánh dấu và dính
vào group liền trước — giống hệt 7.2.

**Bước 5 — thực thi**
Cắt `pdf_paragraph_composition` theo group. Group đầu **giữ nguyên object paragraph gốc**; mỗi group sau
tạo `PdfParagraph` theo **đúng nguyên mẫu babeldoc `paragraph_finder.py:868-888`**: `box=Box(0,0,0,0)`,
`unicode=""`, `debug_id=generate_base58_id()`, copy `layout_label` + `layout_id`, rồi
`paragraphs.insert(...)`. **KHÔNG cần** tự gọi `update_paragraph_data(update_unicode=True)` và **KHÔNG
cần** tự gán `render_order` — hook ở AA6 nằm **trước** `:293-294` và `:310` nên babeldoc tự làm cả hai.
Đây chính là điểm khiến TOC-1 miễn nhiễm với bug Z6 **theo thiết kế**.

**Biên thiết kế tường minh (cố ý KHÔNG xử lý)**

| Dạng | Xử lý |
|---|---|
| Số trang cuối dòng, khe rộng, cùng paragraph (Figoni, LCB) | ✅ Ca chính |
| Dot leader ≥ 20 chấm | ✅ babeldoc gốc đã lo (`:864-866`) |
| Dot leader < 20 chấm | ❌ TOC-1b **TẮT** ở v1 (`TOC_DOT_LEADER_FALLBACK = False`) |
| Số trang La Mã (`"Preface vii"`) | ❌ Cố ý không hỗ trợ (Y9) |
| **Số trang nằm ở paragraph RIÊNG (Bo Friberg)** | ❌ **Ngoài tầm TOC-1** — lỗi ở tầng layout/grouping. `friberg_toc` kích hoạt 0 là **đúng**, không phải FN (Z7-d) |
| Mục bị `--split-short-lines` cắt sẵn sang 2 paragraph (LCB) | ❌ Ngoài tầm — nguồn của 2/84 mục sót (Z7-b) |

#### AA5. Tham số cuối

| Tham số | Giá trị chốt | Căn cứ |
|---|---|---|
| `TOC_GAP_RATIO` | **0.8** (theo `visual_bbox`) | Quét 0.5→1.0 trên 12 dump: FP = 0 ở mọi mức, recall 131→128. Giữ 0.8 vì có nhiều dữ liệu nhất và chặn slug `abandon` 0.82 ở mức dòng. **Không phải "khe an toàn"** |
| `TOC_MIN_TAIL_LINES` | **2** | Tín hiệu chống FP mạnh nhất (Y7 + Z3 đều đồng ý) |
| `TOC_MIN_TAIL_FRACTION` | **0.6** | 31/31 paragraph mục lục thoả |
| `TOC_MIN_BODY_ALPHA_RUNS` | **1** (cụm ≥ 2 chữ cái ASCII) | Loại ô bảng thuần số, `"4.0"`, folio |
| `TOC_MAX_DIGITS` | **4** | Số trang sách ≤ 9999 |
| `TOC_REQUIRE_NON_DECREASING` | **True** (cứng) | Z4. Log mỗi lần chặn |
| `TOC_CONT_INDENT_EM` | **1.0** | Đo thật: ranh giới thật ≤ 0.1pt; Friberg 6.75 em. Biên rất rộng |
| `TOC_DOT_LEADER_FALLBACK` | **False** | Chưa có dữ liệu |
| `TOC_LAYOUT_LABEL_DENY` | danh sách ở AA4 bước 0 | AA3 |
| Cờ runtime | `BABELDOC_SHIM_TOC_SPLIT`, `Settings.babeldoc_toc_split_enabled` — **mặc định `False` ở lần ship đầu**, bật sau khi QA live xanh | Giữ nguyên Y10-a: kill-switch RIÊNG, độc lập với 7.1/7.2 |

#### AA6. Điểm hook cuối

**Giữ nguyên đề xuất Y6**: bọc `ParagraphFinder.process_independent_paragraphs(paragraphs,
median_width)` (`paragraph_finder.py:287`) — chạy hàm gốc trước, rồi chạy TOC-1 v2 trên **cùng list
`paragraphs`** (mutate in-place; `page.pdf_paragraph` trỏ cùng object list, gán ở **`:245`**).

Lý do, **đã xếp lại theo phản biện Z5-c**:

1. **(Mới, mạnh nhất)** `:293-294` gọi `update_paragraph_data(paragraph, update_unicode=True)` cho
   **mọi** paragraph ⇒ paragraph TOC-1 tạo ra **luôn có `unicode` đúng** ⇒ **miễn nhiễm với đúng lớp
   bug đã làm hỏng 7.2** (Z6: `unicode=""` ⇒ `il_translator_llm_only.py:556-568` bỏ qua ⇒ không dịch).
   Đây là **an toàn theo cấu trúc**, không phải theo trí nhớ của người viết code.
2. `_set_paragraph_render_order` (`:310`) chạy sau ⇒ paragraph mới có `render_order` thật (tránh nợ
   Y10-b của 7.2).
3. `add_debug_info` (`:307`) vẽ debug rect cho paragraph mới — phục vụ chính việc đo của 7.4.
4. Đúng tầng ngữ nghĩa: nhánh mục lục dot-leader của babeldoc cũng nằm trong hàm này.

**Bề mặt tương tác đã trace hết (Y6 + Z5, không còn ẩn số)**: `merge_alternating_line_number_paragraphs`
(`:290-291`) không gộp lại được (lý do đúng: `_is_ascii_digit_or_space_paragraph` + `layout_id`, **không
phải** `xobj_id`); `fix_overlapping_paragraphs` (`:302`) chỉ sửa `box`, đo được là no-op trên Figoni
(khe dọc 2.85–2.95pt) nhưng **có thể cắt ~1pt** với sách leading chặt ⇒ đưa vào 7.4-e; patch 7.2 (bọc
`process`, chạy sau) không xung đột vì mục TOC không có marker đầu dòng.

**Không di dời 7.2 sang hook này trong 7.4** — giữ nguyên quyết định Y6. Ghi tech debt (AA10-b).

#### AA7. Oracle cuối cùng — con số Dev phải tái tạo ĐÚNG ở 7.4-a

Đo bằng TOC-1 v2 đầy đủ (deny-list + luật dòng nối bật):

| Fixture | Loại | fire | cut points | Ghi chú oracle |
|---|---|---|---|---|
| `figoni_p7_toc` | TOC | **8** | **28** | 12 paragraph nhiều dòng; 4 không fire = tiêu đề chương 2 dòng |
| `figoni_p8_toc` | TOC | **12** | **38** | 18 paragraph nhiều dòng |
| `lcb_toc` (2 trang) | TOC 2 cột | **11** | **64** | p0: 6/40, p1: 5/24. `fired_inside_table_box = 5` (chỉ log) |
| `friberg_toc` | TOC quy ước ngược | **0** | **0** | **Đúng theo thiết kế** (AA4 biên) — không phải FN |
| `lcb_index` | FP-7 | **0** | **0** | |
| `figoni_p25_recipe` | **FP-4** | **0** | **0** | |
| `figoni_p45_recipe` | **FP-4** | **0** | **0** | |
| `figoni_p7_tables` | FP-3/FP-4 | **0** | **0** | |
| `p74_77` (4 trang) | hồi quy 7.1 | **0** | **0** | |
| `page14_numbered_list_source` | hồi quy 7.2 | **0** | **0** | |
| `figoni_p20`, `figoni_p22` | bảng + caption | **0** | **0** | |
| **Tổng** | | **31 / 130** | | **0 kích hoạt trên 8 trang không phải mục lục** |

#### AA8. Kế hoạch spike 7.4-a — giao Dev ngay

**Nguyên tắc**: đây là **spike theo R5-02**. Sản phẩm là **bằng chứng + fixture**, KHÔNG phải feature.

**Bước 1 — Bảo toàn bằng chứng (làm ĐẦU TIÊN, trước mọi thứ khác)**
Artifact đang nằm ở `/tmp` và scratchpad phiên khác, **sẽ mất**. Đã kiểm tra còn sống hôm nay
2026-09-08. Gzip và commit **8 file** vào `tests/fixtures/babeldoc/` (đọc bằng `gzip.open(path,"rt")`,
đúng khuôn `paragraph_finder_p74_77_dump.json.gz` đã có):

| File nguồn | Tên fixture đề xuất | gz |
|---|---|---|
| `<SP>/wd/lcb_toc/lcb_toc/paragraph_finder.json` | `toc_lcb_contents_p6_p7_dump.json.gz` | 222KB |
| `<SP>/wd/friberg_toc/friberg_toc/paragraph_finder.json` | `toc_friberg_contents_dump.json.gz` | 53KB |
| `<SP>/wd/lcb_index/lcb_index/paragraph_finder.json` | `toc_lcb_index_dump.json.gz` | 192KB |
| `<SP>/wd/figoni_p25_recipe/.../paragraph_finder.json` | `toc_figoni_p25_recipe_dump.json.gz` | 127KB |
| `<SP>/wd/figoni_p45_recipe/.../paragraph_finder.json` | `toc_figoni_p45_recipe_dump.json.gz` | 165KB |
| `<SP>/wd/figoni_p7_tables/.../paragraph_finder.json` | `toc_figoni_tables_dump.json.gz` | 185KB |
| `/tmp/bdprobe/wd_toc/figoni_p7_toc/paragraph_finder.json` | `toc_figoni_contents_p7_dump.json.gz` | 104KB |
| `/tmp/bdprobe/wd_toc2/figoni_p8_toc/paragraph_finder.json` | `toc_figoni_contents_p8_dump.json.gz` | 133KB |

`<SP>` = `/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad`.
Tổng ≈ **1.2 MB** — chấp nhận được. Cũng copy **6 PDF nguồn** ở `<SP>/pdfs/` vào
`tests/fixtures/babeldoc/toc_sources/` (tổng ~1.1MB) và cập nhật `tests/fixtures/babeldoc/README.md`
với lệnh tái tạo (`<SP>/run_all.sh`, đã có sẵn, dùng đúng flag production của `BabeldocRunner` + LLM
port chết ⇒ **0 token**).

**Nếu file nguồn đã bị xoá**: tái tạo bằng `run_all.sh` — trang cần trích bằng `pymupdf.insert_pdf` từ
`data/uploads/`: Figoni bản đầy đủ idx **40** (`figoni_p25_recipe`), idx **60** (`figoni_p45_recipe`),
idx **22** (`figoni_p7_tables`); Le Cordon Bleu idx **6–7** (`lcb_toc`), idx **408** (`lcb_index`);
Bo Friberg idx **6** (`friberg_toc`). **KHÔNG được tự viết tay mock** (Protocol 5 mục 3).

**Bước 2 — Viết `toc_split.py` ở mức spike**
Đúng spec AA4 + tham số AA5. Thuần Python, không import babeldoc, nhận **dict đã parse từ dump JSON**
(hoặc object IL — cùng tên field) để chạy được offline. **Chưa** wiring vào `sitecustomize.py`.

**Bước 3 — Chạy trên 8 fixture, báo cáo bảng AA7**
Báo cáo **từng fixture**: `fire`, `cut points`, và 3 counter mới: `blocked_by_monotonic`,
`blocked_by_fraction`, `fired_inside_table_box`.

**Bước 4 — Đo riêng luật dòng nối (Z7-a)**
In **mọi** ranh giới "dòng đánh dấu → dòng không đánh dấu" trong các paragraph kích hoạt, kèm delta
thụt đầu dòng. **Kỳ vọng: 6 ranh giới, delta ∈ [−13.0, +0.1] pt ⇒ luật là no-op** (kết quả đo của Tech
Lead). Nếu Dev đo ra khác ⇒ dừng, escalate.

**Bước 5 — Chứng minh hook mutate in-place (mục `[UNVERIFIED]` cuối cùng của Y12)**
Chạy **1** lần babeldoc thật với `sitecustomize.py` đã bọc `process_independent_paragraphs` bằng một
patch **rỗng nhưng có instrument** (chỉ đếm + chèn 1 paragraph đánh dấu tổng hợp), trên
`figoni_p7_toc.pdf`, LLM port chết, `--debug`. Đọc dump ra và xác nhận: (a) paragraph chèn thêm **có mặt**
trong `page.pdf_paragraph`, (b) nó có `unicode != ""`, (c) nó có `render_order is not None`.
**Đây là bằng chứng sống cho AA6 lý do 1 và 2** — bắt buộc, vì đó chính là cơ chế bảo vệ khỏi bug Z6.

**Bước 6 — Báo cáo**
Ghi kết quả vào `docs/CHANGELOG.md` (**đọc file hiện có, APPEND section mới vào cuối, KHÔNG xoá/ghi đè
nội dung cũ** — Protocol 7 R7-03). Kèm bảng đối chiếu với AA7.

**Ngoài phạm vi 7.4-a (làm ở 7.4-b trở đi, chỉ khi spike PASS)**: `sitecustomize.py` patch thứ 3, wiring
`config.py` / `babeldoc_runner.py` / `job_orchestrator.py`, unit test đầy đủ, live E2E, đo hồi quy 11
trang, Reviewer.

#### AA9. Gate PASS/FAIL của 7.4-a

**PASS khi ĐỦ 6 điều**:

1. **Recall Figoni**: `figoni_p7_toc` = **8 fire / 28 cut** và `figoni_p8_toc` = **12 fire / 38 cut**
   (tổng **20 / 66**) — **khớp chính xác**, không xê dịch.
2. **Recall LCB**: **11 fire / 64 cut**, monotonic 11/11. Chấp nhận **≥ 80/84** mục được tách đúng
   (oracle Expert: 82/84; 2 mục sót do `--split-short-lines` cắt sẵn, **không** tính là fail).
3. **FP = 0 tuyệt đối** trên **8** fixture không phải mục lục (`friberg_toc`, `lcb_index`,
   `figoni_p25_recipe`, `figoni_p45_recipe`, `figoni_p7_tables`, `p74_77`, `page14_...`,
   `figoni_p20`+`p22`). **Bất kỳ kích hoạt nào ở đây = FAIL, không có ngưỡng "chấp nhận được"**.
4. **Luật dòng nối là no-op**: 0 điểm tách bị dịch chuyển so với khi tắt luật đó (bước 4).
5. **Bước 5 xanh**: paragraph chèn qua hook có `unicode != ""` **và** `render_order is not None`.
6. **8 fixture + 6 PDF nguồn đã commit** vào `tests/fixtures/babeldoc/`, README cập nhật.

**FAIL ⇒ DỪNG, escalate cho Tech Lead** (không tự chỉnh tham số, không tự đổi thiết kế):

| Triệu chứng | Hành động |
|---|---|
| **Bất kỳ FP nào**, đặc biệt trên `figoni_p25_recipe`/`p45`/`p7_tables` (**FP-4**) | Dừng ngay. Báo cáo **paragraph nào, dòng nào, ratio bao nhiêu, `layout_label` gì**. Tech Lead quyết định — **có thể** mở lại hướng guard bảng theo trục khác |
| Recall lệch oracle AA7 | Dừng. Nhiều khả năng khác hệ đo (`visual_bbox` vs `box`) hoặc quên sort theo x hoặc quên bỏ dummy space |
| Luật dòng nối làm dịch điểm tách | Dừng — nghĩa là ngưỡng 1.0 em sai với dữ liệu thật |
| Bước 5 cho `unicode == ""` hoặc `render_order is None` | **Dừng — nghiêm trọng**: giả định nền của AA6 sai, TOC-1 sẽ tái diễn bug Z6. Tech Lead phải thiết kế lại điểm hook |
| Fixture nguồn đã mất và tái tạo ra số khác | Dừng, báo cáo cả 2 bộ số |

Escalate bằng cách báo cho **PM**, PM chuyển **Tech Lead**. Không escalate thẳng sang tự sửa
Architecture.md.

#### AA10. Nhắc lại ràng buộc quy trình

**(a) ĐÂY VẪN LÀ SPIKE (Protocol 5 R5-02).** Dev **CHƯA ĐƯỢC** viết code production đầy đủ cho tới khi
spike PASS gate AA9: **không** tạo patch thứ 3 trong `src/babeldoc_shim/sitecustomize.py` (trừ patch
instrument tạm của bước 5, **không commit**), **không** wiring
`src/core/config.py` / `src/services/babeldoc_runner.py` / `src/core/job_orchestrator.py`, **không**
viết bộ test đầy đủ 7.4-c. Sản phẩm commit của 7.4-a chỉ gồm: **fixture + `toc_split.py` mức spike +
script đo + entry CHANGELOG**.

**(b) Nợ kỹ thuật vẫn mở, KHÔNG thuộc 7.4** — hotfix `a31ac42` đã sửa `unicode=""` nhưng **chưa** copy
`render_order` (`grep render_order src/babeldoc_shim/sitecustomize.py` = 0 hit). Paragraph do **7.2**
tạo vẫn có `render_order = None` ⇒ `pdf_creater.py:52-55` ép về `9999999999999999` ⇒ ký tự bị vẽ **sau
cùng** trong content stream (Z2, Expert đã trace hạ nguồn). Không crash, chưa thấy triệu chứng.
**Task riêng, ưu tiên thấp.** TOC-1 **không** thừa hưởng lỗi này (AA6 lý do 2).

**(c) Ràng buộc thứ tự (giữ nguyên Y8/X7)**: 7.4 **phải xong trước** bước **8.1**. TOC-1 tăng số
paragraph ⇒ đổi `unit_count` ⇒ đổi mode-scale **xuyên trang** (`typesetting.py:892-935`). Nếu 8.1 đã
đo histogram trước, **số đo đó hết hạn**.

**(d) Gate 7.4-d (làm sau, ghi sẵn để không quên)**: phải đo **2** thứ — ranh giới mục **và** **số mục
còn tiếng Anh** trong PDF output (Z8-4). Bài học Z6: gate chỉ đo cấu trúc đã bỏ lọt một bug production
suốt 1 vòng release.

#### AA11. Đính chính các phát biểu cũ (Y-section)

| Chỗ | Sai | Đúng |
|---|---|---|
| Y12 | "`:247` gán cùng object list" | **`:245`** — `page.pdf_paragraph = paragraphs` |
| Y1, Y6 | "`_same_layout_and_xobj` còn đòi cả hai `xobj_id is not None` ⇒ không gộp" | Source đúng nhưng **suy luận sai**: `xobj_id ∈ {0, −1}`, không bao giờ `None`. Lý do thật: `_is_ascii_digit_or_space_paragraph` + `layout_id` phải trùng + TOC-1 chèn liền kề |
| Y7, Y12 | "khe an toàn rộng: TOC 1.0 vs văn xuôi tệ nhất 0.64" | **Bỏ.** Đo trên `visual_bbox`: TOC Figoni 1.05–1.21, TOC LCB **tràn xuống 0.43**; slug `abandon` **0.82–0.93**. Ngưỡng 0.5→1.0 cho FP = 0 như nhau ⇒ **ngưỡng không phải bộ lọc; cổng cố kết paragraph mới là** |
| Y0, Y8 | "quét toàn sách PyMuPDF: 0 FP / 4657 block" là điểm mạnh | **Rút hoàn toàn.** Phép quét đó không phát hiện nổi chính mục lục (Figoni 0/152 block; LCB 2/184 dòng) ⇒ **không dùng làm bằng chứng** |
| Y9 | "đã thấy khớp trên 2 đầu sách" | **Figoni 20/20 paragraph; LCB ~82/84 mục** (2 mục sót do `--split-short-lines` cắt sẵn) |
| Y4 bước 2 | `str.isdigit()` | **ASCII `0-9`** (`'²'.isdigit()` là `True`) |
| Y4 bước 3 | "tách NGAY SAU mọi dòng đánh dấu" | Thêm **luật dòng nối theo thụt đầu dòng** (AA4 bước 4) cho quy ước kiểu Bo Friberg |
| Y7 FP-4 | "⚠️ chưa đo được — rủi ro thật" | ✅ **Đã đo: 0 kích hoạt** trên 3 trang công thức/bảng thật. Cơ chế bảo vệ là **layout model tách ô thành paragraph 1 dòng**, không phải luật của TOC-1 |
| Y11 bước 7.4-a | Bảng mô tả chung | **Thay bằng AA8 + AA9** |
| Z8-2 (i) | Guard `table` theo hình học | **BÁC BỎ** — thay bằng deny-list `layout_label` (AA3) |

#### AA12. Bảng trạng thái verify của section này (Protocol 5 R5-01)

| Claim | Trạng thái |
|---|---|
| Oracle AA7 (31 fire / 130 cut; 0 FP trên 8 fixture không phải TOC) | ✅ **Verified** — script riêng của Tech Lead trên 12 dump IL thật, trong task này |
| Tái tạo được số của Expert (LCB 11/64) và của vòng Y (Figoni 20/66) | ✅ **Verified** — replication độc lập, khớp tuyệt đối |
| Guard `table` hình học làm mất 5 fire / 24 cut trên `lcb_toc` p1 | ✅ **Verified** — đo trực tiếp, có/không guard |
| Guard `table` hình học **không** cứu được FP-4 (0 paragraph nhiều dòng có tâm trong box `table` trên 3 trang công thức) | ✅ **Verified** |
| 31/31 paragraph kích hoạt có `layout_label == 'plain text'` ⇒ deny-list mất 0 recall | ✅ **Verified** |
| Slug nhà in nhãn `abandon` lọt luật mức dòng (0.82–0.93), chỉ thoát vì là paragraph 1 dòng | ✅ **Verified** — LCB `'57131_fm_i_xv.indd 5'` = 0.82 |
| `TOC_GAP_RATIO` 0.5→1.0 đều cho FP = 0 | ✅ **Verified** — quét 6 mức trên 12 dump |
| Luật dòng nối (1.0 em) là no-op trên dữ liệu hiện có | ✅ **Verified** — 6/6 ranh giới, delta ≤ +0.1pt |
| `page.page_layout[].class_name/box/id` tồn tại, có `"table"` | ✅ **Verified** — dump `figoni_p25_recipe` |
| `xobj_id ∈ {0, −1}`, không bao giờ `None` | ✅ **Verified** — dump thật |
| `paragraph_finder.py:245/:287/:293-294/:302/:307/:310` đúng như mô tả | ✅ **Verified** — đọc source 0.6.4 đã cài, trong task này |
| Danh sách nhãn layout hợp lệ (`layout_helper.py:655-690`, `:789-845`) | ✅ **Verified** — đọc source |
| Hotfix `a31ac42` có `update_unicode=True`, **không** có copy `render_order` | ✅ **Verified** — `git show` + grep |
| Hook `process_independent_paragraphs` mutate in-place, paragraph mới nhận `unicode` + `render_order` | ⚠️ **`[UNVERIFIED]`** — **gate cứng của 7.4-a bước 5**. Đây là mục `[UNVERIFIED]` duy nhất còn lại chặn implement |
| Bảng công thức **không kẻ khung** (nhãn `plain text`) có kích hoạt TOC-1 không | ⚠️ **`[CHƯA VERIFY]`** — chưa có mẫu trong 6 đầu sách. Rủi ro tồn đọng, theo dõi ở 7.4-d/7.4-e; **không chặn** 7.4-a |
| `fix_overlapping_paragraphs` cắt box với sách leading chặt | ⚠️ **`[CHƯA VERIFY]`** — no-op trên Figoni (khe 2.85–2.95pt); đo ở 7.4-e |
| Biên độ TOC-1 làm đổi mode-scale của Bug #8 | ⚠️ **Verified về cơ chế, chưa đo biên độ** — ràng buộc thứ tự AA10-c |

---

### Bug #7 Ca C — Đóng vòng: implement + QA + bật default (2026-09-08)

Cập nhật ngắn (không sửa bảng AA12 ở trên, chỉ đính chính trạng thái mới nhất tại đây theo đúng
tinh thần "section sau thắng khi mâu thuẫn"):

- **Gate 7.4-a bước 5 (hook mutate in-place, dòng `[UNVERIFIED]` duy nhất chặn implement ở AA12)**:
  ✅ **Đã verify sống** trong spike — paragraph probe chèn qua hook có `unicode != ""` và
  `render_order is not None`. Xem `docs/CHANGELOG.md` "Spike 7.4-a".
- **7.4-b→e (implement, test, live E2E, hồi quy)**: hoàn tất, Reviewer APPROVE (`docs/review-report.md`,
  2 lần review: spike + implement đầy đủ). Commit `0aea37b` (spike) → `2c47a03` (implement).
- **QA Vòng 8** (`docs/test-report.md`): PASS — tự chạy lại độc lập qua cả `BabeldocRunner` trực
  tiếp lẫn `JobOrchestrator.run_job()` đầy đủ (DB thật, DeepSeek thật), xác nhận điều kiện AA5
  "bật sau khi QA live xanh" đã thoả.
- **Quyết định**: `Settings.babeldoc_toc_split_enabled` đổi default `False` → **`True`** (PM chốt
  dựa trên khuyến nghị QA — đây là quyết định cơ học đã được AA5 định sẵn tiêu chí từ trước, không
  phát sinh câu hỏi thiết kế mới cần Tech Lead/Domain Expert trao đổi thêm).
- **Nợ kỹ thuật còn mở, KHÔNG chặn release này** (giữ nguyên như AA10-b/AA12, chỉ nhắc lại):
  `render_order` của paragraph do **7.2** tạo vẫn chưa được copy (khác TOC-1 v2 — miễn nhiễm theo
  thiết kế); `fix_overlapping_paragraphs` trên sách leading chặt và bảng công thức không kẻ khung
  vẫn ở mức `[CHƯA VERIFY]` — theo dõi tiếp khi có dữ liệu production thật, không phải điều kiện
  chặn bật default.
- **Ràng buộc AA10-c vẫn còn hiệu lực**: chưa bắt đầu Bug #8 (đo histogram mode-scale, bước 8.1)
  cho tới khi Ca C ổn định trên production thật với default mới — TOC-1 đổi `unit_count` sẽ làm
  hết hạn mọi số đo mode-scale đo trước thời điểm này.

---

## US-16 v2 — Mở rộng phạm vi sang ảnh `/FlateDecode` (2026-09-08)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement.
**Trạng thái**: ⏸ **Chờ user duyệt (Protocol 2)** — đây là thay đổi phạm vi của business rule đã
chốt (BR-IMGCOMP-02), cùng loại tình huống với S8 của US-16 v1. Không giao Dev trước khi duyệt.
**Quan hệ với US-16 v1 (S1–S10)**: v1 **vẫn còn hiệu lực toàn bộ**, v2 chỉ **mở rộng bước 3 của
S6** (điều kiện lọc filter) và **sửa 1 lỗi tiềm ẩn của S6 bước 8** (`/Decode`, xem V4.4). Mọi
guard, data lineage, vị trí gắn code, cách save của v1 **giữ nguyên không đổi**.

### V1. Kết luận ngắn

Job thật `78674af9-ce15-4d39-bba5-7f8d1e2804fe` (30 trang, 46.87 MB, `status=completed`) chạy
`compress_pdf_images()` **thành công nhưng re-encode 0 ảnh**. Nguyên nhân: file này có **0 xref
`Filter: null`** — 85% dung lượng nằm ở **57 ảnh `/FlateDecode`**, và
`src/postprocess/image_compress.py:81-84` coi *mọi* filter khác `null` là "đã nén rồi, bỏ qua".

`/FlateDecode` là zlib **lossless** — với ảnh chụp nó gần như không nén được gì (đo được: có ảnh
Flate còn **to hơn** kích thước bitmap thô, xref 1144: 10,074,126 bytes cho 1681×1800×4 =
12,103,200 pixel bytes). Coi nó "tương đương đã nén như JPEG" là một suy diễn sai, và là suy diễn
**do code tự mở rộng ra**, không có trong câu chữ của BR-IMGCOMP-02.

Sửa: cho phép re-encode cả `/FlateDecode`, giữ nguyên mọi guard cũ + thêm 3 guard mới.
**Đo thật trên chính file đó: 46.87 MB → 25.19 MB (−46.3%), 1.5 giây, text giống hệt từng trang,
sai khác pixel trung bình 0.0613/255.**

### V2. Nguồn xác thực (Protocol 5 R5-01 / Protocol 1 mở rộng)

Toàn bộ số liệu trong section này do Tech Lead **tự chạy lại từ đầu**, không kế thừa từ brief của
PM — kể cả những con số PM đã báo là đã verify (đúng theo kỷ luật "không nhận claim về hành vi tool
bên ngoài mà không tự chạy"). Kết quả trùng khớp với PM ở mọi chỉ số PM đã đo, và **phát hiện thêm
4 contract mà brief chưa có** (V2.2) — trong đó 2 cái sẽ làm implementation sai nếu không biết.

**Môi trường**: `.venv/bin/python` (Python 3.14, darwin), PyMuPDF **1.28.2**
(`1.28.2 ('1.28.2', '1.28.2', None)`) — cùng version với US-16 v1, nên bảng signature ở S1 vẫn
còn hiệu lực, không verify lại.

**Dữ liệu đo**: `data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf`
(49,146,122 bytes = 46.87 MB, 30 trang) + 5 job output thật khác (V3.3) + fixture hiện có
`tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf`. Không dùng file dựng tay.

#### V2.1. Xác nhận lại hiện trạng (không chỉ đọc code)

Chạy **đúng logic đang ship** (`Filter != "null"` → skip) trên bản copy của file thật:

```
variant=cur counts={'scanned': 99, 'recompressed': 0, 'skip_filter': 99, ...}
size: 46.87 MB -> 46.87 MB
```

`recompressed=0` — xác nhận bằng chạy thật, không phải suy luận từ đọc code.

#### V2.2. Contract PyMuPDF mới verify được (4 cái, đều ảnh hưởng trực tiếp tới code)

| # | Contract | Bằng chứng chạy thật | Hệ quả thiết kế |
|---|---|---|---|
| C1 | `Pixmap.colorspace.name` **KHÔNG** trả `"DeviceCMYK"` cho ảnh ICCBased — trả chuỗi mô tả: `'ICCBased(CMYK,Artifex CMYK SWOP Profile)'`, `'ICCBased(Gray,Artifex Software sGray ICC Profile)'`, `'Separation(DeviceCMYK,Black)'` | in trực tiếp `pix.colorspace` của xref 1144/1062/889 | Guard dạng `name in {DeviceGray,DeviceRGB,DeviceCMYK}` **loại nhầm 19/19 ảnh cần nén**. Đây **là lỗi đã thực sự mắc phải** trong lúc spike: lần chạy đầu ra `recompressed=0, skip_cs=19`. Phải chấp nhận thêm tiền tố `ICCBased(` |
| C2 | `Pixmap.tobytes("jpeg")` **raise** `FzErrorArgument: code=4: pixmap must be Grayscale, RGB, or CMYK to save as JPEG` với colorspace `Separation` (dù `pix.n == 1`) | 29 xref 1×1 trong chính file thật đều raise | Không có guard colorspace thì 29 xref này rơi vào `except Exception` chung → **29 stack trace `logger.warning(exc_info=True)` cho 1 job 30 trang**, trông như lỗi thật. Cần guard tường minh + đếm riêng |
| C3 | `update_stream(xref, jb, new=1, compress=0)` **tự xoá `/Filter` VÀ `/DecodeParms`** khỏi object dict | in `xref_object()` trước/sau: trước có `/Filter /FlateDecode`, sau **không còn**; inject `/DecodeParms <</Predictor 15…>>` rồi gọi update_stream → `xref_get_key` trả `('null','null')` | **Không cần** thêm bước xoá `/DecodeParms` — PyMuPDF đã lo. Ghi lại để Dev/Reviewer khỏi "sửa cho chắc" |
| C4 | `update_stream` **KHÔNG** xoá `/Decode`; và `Pixmap(doc, xref)` **CÓ áp dụng** `/Decode` | inject `/Decode [1 0]` → samples đổi từ `ffff…` sang `0000…` (`Pixmap APPLIES /Decode: True`); sau `update_stream` key `/Decode [1 0]` vẫn còn nguyên | **Bắt buộc xoá `/Decode`** khi ghi đè: pixel đã được áp dụng Decode 1 lần rồi, để lại key sẽ áp dụng **lần thứ hai** → ảnh âm bản. Xem V4.4 — đây là **lỗi tiềm ẩn có sẵn trong code đang ship**, không phải lỗi do v2 tạo ra |

Contract phụ (verify kèm, dùng để viết guard):

- `xref_set_key(xref, key, "null")` = **xoá key theo ngữ nghĩa PDF**: object dict vẫn hiển thị
  `/DecodeParms null` nhưng `xref_get_key` trả `('null','null')`, và null object ≡ vắng mặt theo
  spec PDF. Đây là cách xoá key duy nhất verify được ở 1.28.2.
- Trên 99 xref ảnh của file thật: `/Decode` xuất hiện ở **62 xref** nhưng **đều là identity**
  (`[0 1]` ×46, `[0 1 0 1 0 1 0 1]` ×16); `/DecodeParms <</ColorTransform 0>>` ở 41 xref DCT.
  Nghĩa là bug C4 **hiện chưa phát tác trên dữ liệu đã có** — nhưng chỉ vì may, không vì code đúng.

### V3. Số liệu đo trên dữ liệu thật

#### V3.1. Phân bố filter của file sự cố (30 trang, 46.87 MB)

| Filter | Số xref | Stream bytes |
|---|---|---|
| `/FlateDecode` | **57** | **28.72 MB** |
| `/DCTDecode` | 42 | 11.12 MB |
| `null` (raw) | **0** | 0 |
| **Tổng ảnh** | 99 | 39.84 MB (**85%** của 46.87 MB) |

#### V3.2. Bên trong 57 ảnh `/FlateDecode`

| Nhóm | Số xref | Bytes | Đặc điểm (đã đo) |
|---|---|---|---|
| ≥ 1 MB | 5 | 23.53 MB | ảnh chụp CMYK, `ICCBased`, bpc=8 |
| 100 KB – 1 MB | 12 | 5.05 MB | ảnh chụp CMYK + 3 ảnh xám `ICCBased(Gray)` |
| 4 KB – 100 KB | 2 | 0.14 MB | — |
| 100 B – 4 KB | **0** | 0 | **không có ảnh nào rơi vào vùng này** |
| < 100 B | 38 | ~0.0004 MB | 1×1 px: 29 `Separation(DeviceCMYK,Black)` (9–11 B) + 9 `DeviceCMYK` (14–55 B) |

Toàn bộ 57 ảnh: `BitsPerComponent = 8`, `/SMask` = 0 (không có), `/ImageMask` vắng mặt.
**Khoảng trống 100 B – 4 KB rỗng hoàn toàn** — đây là căn cứ chọn ngưỡng ở V5 (ngưỡng đặt ở đâu
trong khoảng 100 B–40 KB cũng cho **cùng một kết quả** trên file này, tức kết quả không nhạy cảm
với việc chọn con số).

#### V3.3. Khảo sát rộng — 6 job output thật (chống kết luận từ 1 mẫu, đúng bài học S3)

| Job | Trang | Size | `null` | `/FlateDecode` | `/DCTDecode` | `/CCITTFax` |
|---|---|---|---|---|---|---|
| `78674af9` (sự cố) | 30 | 46.87 MB | 0 | **57 — 28.72 MB** | 42 — 11.12 MB | 0 |
| `136645f9` | 418 | **520.14 MB** | 0 | 393 — 0.08 MB | **1110 — 437.69 MB** | 0 |
| `40cb4746` (đã qua US-16 v1) | 415 | 18.44 MB | 0 | 0 | 454 — 7.56 MB | 6 |
| `4c9834bf` | 298 | 6.19 MB | 0 | 13 — 1.32 MB | 0 | 1 |
| `803fce52` | 25 | 28.06 MB | **9 — 20.93 MB** | 0 | 13 — 0.11 MB | 1 |
| `f18f796c` | 1040 | 35.97 MB | 0 | 3 — 0.28 MB | 288 — 6.00 MB | 357 |

Ba kết luận rút ra, đều quan trọng cho phạm vi thiết kế:

1. **Cả `null` lẫn `/FlateDecode` đều xuất hiện thật** (`803fce52` có `null`, `78674af9` có Flate)
   → v2 phải xử lý **cả hai**, không được thay `null` bằng `Flate`.
2. **`/FlateDecode` không phải hiện tượng cá biệt của 1 file**: 4/6 job có, nhưng chỉ 1 job có ở
   mức gây hại (28.72 MB) — nên lợi ích của v2 **phụ thuộc tài liệu nguồn**, không phải cải thiện
   đều cho mọi job. Không được hứa với user rằng mọi file sẽ nhỏ đi ~46%.
3. **v2 KHÔNG cứu được job lớn nhất trong kho** (`136645f9`, 520 MB): 437 MB ở đó **đã là JPEG
   sẵn**, đúng nhóm mà BR-IMGCOMP-02 cố ý không đụng để tránh nén chồng. Xem V9.2 — việc đó là
   một bài toán khác (downsample), **không** thiết kế trong v2.

### V4. Vì sao phải sửa business rule, không chỉ sửa code

#### V4.1. Câu chữ gốc vs. code

BR-IMGCOMP-02 (`docs/PRD.md:242`) viết: *"Chỉ re-encode ảnh đang ở dạng raw/uncompressed
(`Filter: null`); ảnh đã là JPEG (`DCTDecode`) giữ nguyên, không nén chồng lần 2."*

Business rule **chỉ nói về 2 trạng thái**: raw và JPEG. Code (và S6 bước 3 của v1) diễn giải thành
**"mọi filter ≠ null đều bỏ qua"** — một tập rộng hơn hẳn, bao gồm `/FlateDecode`, thứ **không
phải JPEG và không được bảo vệ bởi lý do "không nén chồng"** (Flate là lossless, re-encode sang
JPEG lần đầu không phải nén chồng).

#### V4.2. Vì sao lỗ hổng này không bị phát hiện ở v1

Spike v1 (S2) đo trên `3594a7a3` — file đó có **đúng 3 loại**: `null` (357), `DCTDecode` (156),
`CCITTFaxDecode` (25) — tổng 538, khớp 100% số xref. **Không có một xref `/FlateDecode` nào.**
Nên nhánh `Flate → skip` chưa từng được kiểm chứng trên dữ liệu thật; nó đúng theo câu chữ code
nhưng chưa bao giờ được đối chiếu với thực tế. Đây là biến thể của cùng một bài học: *test/spike
chỉ chứng minh code khớp với dữ liệu đã có, không chứng minh giả định đúng cho dữ liệu chưa gặp*.

#### V4.3. Bằng chứng "Flate ≠ đã nén hiệu quả"

Re-encode thật 19 ảnh Flate ≥ 4 KB sang JPEG q85:

| xref | Flate bytes | JPEG q85 | Còn lại | Kích thước |
|---|---|---|---|---|
| 1144 | 10,074,126 | 2,212,526 | 22% | 1681×1800 CMYK |
| 983 | 10,067,072 | 2,206,540 | 22% | 1681×1800 CMYK |
| 882 | 2,456,262 | 1,184,711 | 48% | 1039×1245 CMYK |
| 986 | 1,075,212 | 158,001 | **15%** | 233×1711 CMYK |
| 155 | 606,195 | 266,739 | 44% | 455×545 CMYK |
| 1062 | 122,668 | 47,682 | 39% | 702×403 **Gray** |
| … (19 ảnh) | **28.72 MB** | **7.04 MB** | **24.5%** | — |

Không ảnh nào bị guard nở file (`len(jpeg) >= raw`) chặn — tức **không ảnh nào trong nhóm này là
đồ hoạ phẳng mà JPEG sẽ làm to ra**.

#### V4.4. Lỗi tiềm ẩn `/Decode` — có sẵn trong code đang ship

Theo C4 (V2.2): `Pixmap(doc, xref)` áp dụng `/Decode`, còn `update_stream` không xoá nó. Với ảnh
`Filter: null` **có `/Decode` không phải identity** (ví dụ `[1 0]`), code **hiện tại** sẽ ghi JPEG
đã-áp-Decode rồi để nguyên key `/Decode [1 0]` → viewer áp lần hai → **ảnh âm bản**. Chưa phát tác
vì cả 2 file production đã đo đều chỉ có `/Decode` identity. v2 sửa luôn (V5 bước 9) — sửa này
**độc lập với việc user có duyệt mở rộng phạm vi Flate hay không**, và nên làm kể cả khi user chọn
giữ nguyên scope cũ.

### V5. Thuật toán v2 (spec cho Dev — KHÔNG phải code để copy)

Thay đổi so với S6 nằm ở **bước 3** (điều kiện lọc), **bước 4b/4c/4d** (3 guard mới) và **bước 9**
(xoá `/Decode`). Các bước còn lại giữ nguyên y hệt v1.

Thứ tự guard được sắp **rẻ → đắt** có chủ đích: mọi phép loại trừ đọc key đều chạy **trước** khi
dựng `Pixmap` (thao tác tốn RAM/CPU nhất — với ảnh 1681×1800 CMYK là ~12 MB bộ nhớ mỗi ảnh).

1. Mở `pdf_path`, ghi `size_before`. (như v1)
2. Gom xref duy nhất qua `get_page_images(pno, full=True)`; `info[0]`=xref, `info[1]`=smask. (như v1)
3. **[ĐỔI] Điều kiện được phép re-encode**: `Filter` là `null` **HOẶC** chứa `FlateDecode`.
   - Đọc `doc.xref_get_key(xref, "Filter")` → `(type, value)`.
   - `type == "null"` → eligible (ảnh raw, đúng như v1).
   - `type == "name"` và `value == "/FlateDecode"` → eligible.
   - `type == "array"` (ví dụ `[ /ASCII85Decode /FlateDecode ]`) → eligible **nếu** `"FlateDecode"`
     xuất hiện trong chuỗi value **và** không xuất hiện filter nén ảnh nào khác
     (`DCTDecode`, `JPXDecode`, `JBIG2Decode`, `CCITTFaxDecode`). Ghi chú: dạng array **chưa có mẫu
     thật** trong 6 job đã khảo sát (Reviewer US-16 v1 cũng đã nêu điểm này) → nhánh này là
     ⚠️ **`[UNVERIFIED]` — không chặn Dev** vì hành vi mặc định khi không match là *bỏ qua* (an toàn).
   - Mọi thứ khác (`/DCTDecode`, `/CCITTFaxDecode`, `/JPXDecode`, `/JBIG2Decode`, `/RunLengthDecode`…)
     → `images_skipped_already_compressed += 1`, bỏ qua. **BR-IMGCOMP-02 phần "không nén chồng JPEG"
     giữ nguyên 100%.**
4. **Guard** (thứ tự bắt buộc):
   - **4a (như v1)** `/ImageMask == true` → skip `unsupported`; `info[1] != 0` (có `/SMask`) →
     skip `unsupported`. *Lưu ý: bản thân object smask không nằm trong `get_page_images()` nên
     không bao giờ bị hàm này chạm tới — đã kiểm chứng ở v1, nhắc lại để Reviewer khỏi nghi.*
   - **4b [MỚI] Ngưỡng kích thước**: `len(doc.xref_stream_raw(xref)) < min_recompress_bytes`
     (mặc định **4096**) → skip, đếm vào **`images_skipped_small`** (field mới).
     *Lý do*: JPEG có sàn ~700 byte (đo thật: ảnh 1×1 → 698–763 byte), nên dưới vài KB không thể
     có lợi ích thật; guard này **không phải guard đúng-sai** (guard nở file ở bước 8 mới là guard
     đúng-sai) mà là guard **chi phí + nhiễu log**: nó loại 38/57 xref trước khi dựng Pixmap và
     nhờ đó tránh luôn 29 exception của C2. Đo: khoảng 100 B–4 KB rỗng hoàn toàn (V3.2) nên ngưỡng
     này không cắt nhầm ảnh thật nào.
   - **4c [MỚI] Bit depth**: `BitsPerComponent != 8` → skip `unsupported`.
     *Lý do*: ảnh 1-bit (bilevel — bản scan đen trắng, line art) là nhóm mà JPEG **vừa hỏng chất
     lượng vừa thường làm file to ra**; Flate/CCITT/JBIG2 mới là codec đúng cho chúng. Đây là guard
     bảo vệ chính cho đường `pdf_scan` (V8.2).
   - **4d [MỚI] Colorspace**: dựng `pix = Pixmap(doc, xref)` (và `Pixmap(pix, 0)` nếu `pix.alpha`),
     rồi chấp nhận **chỉ khi** `pix.n ∈ {1, 3, 4}` **và** `pix.colorspace.name` thuộc
     `{"DeviceGray", "DeviceRGB", "DeviceCMYK"}` **hoặc** bắt đầu bằng `"ICCBased("`.
     Ngược lại (`Separation(...)`, `Indexed(...)`, `DeviceN(...)`, `Lab`, `None`) → skip, đếm vào
     **`images_skipped_colorspace`** (field mới), log mức **`debug`** chứ không `warning` — đây là
     đường đi bình thường, không phải sự cố.
     ⚠️ **Không được viết guard là `name in {DeviceGray, DeviceRGB, DeviceCMYK}` cho gọn** — xem C1:
     làm vậy loại nhầm 19/19 ảnh cần nén và hàm lại im lặng không làm gì, đúng bằng bug đang sửa.
5. `jb = pix.tobytes("jpeg", jpg_quality=jpeg_quality)`. (như v1)
6. **Guard nở file (như v1)**: `len(jb) >= raw_size` → skip, `images_skipped_larger += 1`.
   Đây vẫn là **guard đúng-sai duy nhất cần thiết** cho câu hỏi "ảnh này có phải ảnh chụp không" —
   PM nói đúng ở điểm này: không cần heuristic "photographic hay không", vì icon/đồ hoạ phẳng mà
   JPEG làm to ra sẽ tự bị loại ở đây. Đo thật: 0/19 ảnh bị guard này chặn trên file sự cố.
7. Ghi đè stream + key (như v1): `update_stream(xref, jb, new=1, compress=0)`;
   `Filter → /DCTDecode`; `BitsPerComponent → 8`;
   `ColorSpace →` `/DeviceCMYK` | `/DeviceRGB` | `/DeviceGray` theo `pix.n`; `Width`/`Height`.
8. **[MỚI] Dọn `/Decode`**: nếu `doc.xref_get_key(xref, "Decode")[0] != "null"` →
   `doc.xref_set_key(xref, "Decode", "null")`. **Chỉ set khi key tồn tại** — set vô điều kiện sẽ
   thêm `/Decode null` vào mọi object và làm fixture hiện có lệch 12 byte không cần thiết (đã đo:
   606,629 → 606,641 byte trên `job3594a7a3_chunk0_sample_mono.pdf`).
   Không cần đụng `/DecodeParms` (C3 — `update_stream` đã xoá).
9. `doc.save(tmp, garbage=4, deflate=True)` → `close()` → `os.replace(tmp, pdf_path)`. (như v1)

**Chữ ký hàm** (mở rộng tối thiểu, giữ nguyên tinh thần S5 — tham số chỉ để test tham số hoá được,
**không** phải điểm cấu hình `.env`/UI, BR-IMGCOMP-03 giữ nguyên):

```python
async def compress_pdf_images(
    pdf_path: str | Path, *, jpeg_quality: int = 85, min_recompress_bytes: int = 4096
) -> ImageCompressStats
```

`ImageCompressStats` thêm 2 field: `images_skipped_small`, `images_skipped_colorspace`
(giữ nguyên toàn bộ field cũ — đây là dataclass chỉ dùng cho log/test, không ghi DB, không lên UI).

### V6. Data lineage (Protocol 6 R6-01) — **không đổi so với S5**

Nhắc lại tường minh để Reviewer trace tay được mà không phải mở lại v1:

| | |
|---|---|
| **Artifact vào** | `merged_path` = `self._output_dir / job.id / "translated_vi.pdf"` (`src/core/job_orchestrator.py:488`), chính biến vừa truyền cho `merge_chunk_pdfs(chunks, merged_path)` (`:490`) và có thể đã được `overlay_rotated_text(output_pdf_path=merged_path)` sửa tại chỗ (`:528-537`). **KHÔNG** phải `job.file_path`, **KHÔNG** phải `chunk.output_path`. |
| **Artifact ra** | Ghi đè in-place chính `merged_path` (tmp + `os.replace`). |
| **Ai gọi / thứ tự** | `run_job()` `:573-574`, trong cùng khối `try`, **sau** guard BR-OCR-03 (`:495-499`), **sau** overlay chữ xoay (RK-3), **trước** `job.output_path = str(merged_path)` (`:592`) và **trước** `create_bilingual_pdf(merged_path, file_path, bilingual_path)` (`:597`). |
| **Điều kiện gọi** | `if self._settings.pdf_translate_engine == "babeldoc":` — BR-IMGCOMP-01 **giữ nguyên**, nhánh `pdf2zh` không đổi một dòng hành vi nào. |

### V7. Kết quả verify chạy thật (đúng khuôn S7 — R6-03: kiểm tra nội dung, không tin status)

Chạy thuật toán V5 đầy đủ trên **bản copy** của file production 46.87 MB (file gốc không bị đụng):

| Chỉ số | Trước | Sau |
|---|---|---|
| Kích thước | 46.87 MB | **25.19 MB (−46.3%)** |
| Stream bytes của 19 ảnh Flate | 28.72 MB | **7.04 MB** |
| Số trang | 30 | **30** |
| Tổng ký tự text | 59,193 | **59,193 — giống hệt từng trang (30/30)** |
| Ảnh xử lý | — | 19 re-encode, 42 skip (đã nén), 38 skip (nhỏ), **0 lỗi**, 0 bị guard nở file |
| Thời gian chạy | — | **1.5 giây** |

**Kiểm chứng thị giác bằng pixel** (render trước/sau toàn bộ 30 trang, so từng pixel):

```
worst pages by mean abs pixel diff: (0.720, p17), (0.579, p29), (0.214, p22), (0.101, p26)
mean over all 30 pages: 0.0613 / 255      max single-pixel diff: 46 (p22)
```

**Không có hiện tượng đảo màu CMYK** (nếu có, mean diff sẽ ở mức ~130–250/255 — đây chính là mức
tôi đo được khi decode JPEG CMYK *đứng riêng ngoài PDF*, một cái bẫy đo lường: phải so **trang đã
render**, không so pixmap giải mã trực tiếp).

**Xem tận mắt** (R6-03): trang 22 chứa ảnh khắc nét (engraving) **xám, nhiều nét gạch mảnh** —
đúng nhóm nhạy cảm nhất với ringing của JPEG. Render 200 dpi trước/sau và nhìn trực tiếp:
**không phân biệt được bằng mắt**; sai khác tập trung ở rìa nét gạch, đỉnh 46/255.

**Hồi quy trên fixture đang có** (`job3594a7a3_chunk0_sample_mono.pdf`, 5 ảnh: 1 `null` + 3 DCT +
1 CCITT): thuật toán v2 cho **kết quả y hệt v1** — `recompressed=1, skip_filter=4`, 7.08 MB →
0.58 MB. Tức **v2 không làm đổi hành vi trên dữ liệu mà v1 đã xử lý đúng**; test hiện có phải vẫn
xanh không sửa gì (trừ khi test assert kích thước file theo byte tuyệt đối).

### V8. Các quyết định thiết kế đã cân nhắc (và phương án bị loại)

#### V8.1. Có cần heuristic "ảnh chụp hay đồ hoạ phẳng" không? → **KHÔNG**

Đã thử đo thống kê số màu duy nhất / tỉ lệ màu áp đảo cho từng ảnh để phân loại. Kết luận: **không
cần** — guard nở file (bước 6) đã xử lý đúng lớp rủi ro đó bằng *kết quả thật* thay vì bằng *dự
đoán*, và đo được 0/19 ảnh bị nó chặn. Thêm heuristic = thêm ngưỡng phải tune, thêm đường code
không test được bằng dữ liệu thật. PM đề xuất hướng này và tôi xác nhận: giữ nguyên guard cũ.

#### V8.2. Có nên loại trừ ảnh xám (grayscale) để bảo vệ bản scan văn bản? → **KHÔNG, nhưng có phương án lùi**

Đã đo cả 2 biến thể trên cùng file thật:

| Biến thể | Kết quả | Sai khác pixel |
|---|---|---|
| **(A)** re-encode cả Gray/RGB/CMYK (khuyến nghị) | 46.87 → **25.19 MB** | mean 0.0613/255 |
| **(B)** bỏ qua ảnh 1 kênh (grayscale) | 46.87 → 25.34 MB | mean 0.0486/255 |

Chênh lệch chỉ **0.15 MB (0.3%)** — nghĩa là cả hai đều chấp nhận được về dung lượng. Chọn (A) vì:

- Rủi ro thật của grayscale không nằm ở "ảnh xám" mà ở **ảnh 1-bit bilevel** (scan đen trắng) —
  nhóm đó đã bị guard 4c (`BitsPerComponent != 8`) chặn tuyệt đối, không phụ thuộc quyết định này.
- Với ảnh xám 8-bit thật (engraving nhiều nét mảnh — trường hợp xấu nhất có trong dữ liệu), đã
  **nhìn tận mắt ở 200 dpi**: không phân biệt được (V7).
- Đường `pdf_scan` **hưởng lợi nhiều hơn chứ không thiệt**: OCR bridge (`src/preprocess/searchable_pdf.py`)
  **không chèn ảnh mới** — nó vẽ whiteout + text vô hình lên chính trang scan gốc, nên ảnh trang
  giữ nguyên codec của file nguồn. Scan 8-bit lưu Flate là đúng nhóm phình to nhất mà v2 cứu được.
- Nếu sau này gặp job scan bị giảm chất lượng thật: lùi về (B) chỉ là **thêm 1 điều kiện `pix.n == 1`
  vào guard 4d** — không phải viết lại thiết kế. Ghi sẵn ở đây để khỏi phải điều tra lại.

#### V8.3. Vì sao không nâng `jpeg_quality` cho ảnh xám? → giữ **q85 cố định**

BR-IMGCOMP-03 chốt q85 cố định. Chất lượng đo được ở q85 đã đạt (V7), nên thêm một hằng số thứ hai
theo kênh màu là độ phức tạp **không có số liệu nào biện minh**. Không làm.

### V9. Phát hiện phụ (ngoài phạm vi v2 — cần PM/user quyết định riêng)

#### V9.1. `create_bilingual_pdf()` đang save KHÔNG nén — **đúng lỗi S8, ở một file khác**

`src/postprocess/bilingual_merge.py:22` gọi `output_doc.save(output_path)` **trần** —
`deflate=False, garbage=0` mặc định. Bước này chạy **sau** `compress_pdf_images()` nên nó **thổi
phồng lại** chính file vừa được nén.

Đo thật trên output song ngữ có sẵn (`4c9834bf`, 596 trang):

| Xử lý | Kích thước |
|---|---|
| Hiện tại (`save()` trần) | **86.97 MB** |
| Chỉ đổi thành `save(garbage=4, deflate=True)` | **7.40 MB (−91.5%)**, mất 1.0 giây |

Đáng chú ý: file này chỉ có 2.65 MB là ảnh — tức ~84 MB là **content stream/font không nén**, không
phải vấn đề ảnh. Bản dịch đơn ngữ của cùng job chỉ 6.19 MB, nghĩa là bước song ngữ **một mình** làm
file to gấp 14 lần. Job `f18f796c` còn cực đoan hơn: đơn ngữ 35.97 MB → song ngữ **433.86 MB**.

**Điểm cần PM/user quyết định** (Tech Lead **không tự quyết**, đúng tiền lệ S8 — đây là sửa hành vi
nằm ngoài US-16, chạm code path dùng chung cho **cả `pdf2zh` lẫn `babeldoc`**):

- **(A) Ngoài scope lần này**: giữ nguyên, ghi backlog. File song ngữ tiếp tục lớn bất thường.
- **(B) Sửa kèm v2** (khuyến nghị của tôi nếu user quan tâm dung lượng — mà theo bối cảnh thì đúng
  là đang quan tâm): đổi 1 dòng `bilingual_merge.py:22` → `save(output_path, garbage=4, deflate=True)`.
  Rủi ro thấp hơn hẳn trường hợp `chunk_merge.py` ở S8 (file này **không** dính Bug #7/#8, không có
  golden test bám sát), nhưng vẫn là thay đổi ảnh hưởng **cả 2 engine** nên vẫn cần user duyệt.

#### V9.2. Job 520 MB toàn ảnh JPEG — **v2 không cứu được**, backlog riêng

`136645f9`: 520.14 MB, trong đó **437.69 MB là 1110 ảnh `/DCTDecode`** (đã là JPEG, trung bình
394 KB/ảnh). BR-IMGCOMP-02 cố ý không đụng nhóm này. Muốn giảm phải **downsample theo kích thước
hiển thị thật trên trang** (ảnh 300+ dpi đặt vào khung nhỏ) hoặc re-encode JPEG→JPEG chấp nhận nén
chồng — cả hai đều là bài toán mới, cần spike đo riêng. **Chưa thiết kế, chỉ ghi nhận.** Cần nói rõ
với user: sau v2, những job dạng này **vẫn sẽ lớn**.

### V10. Yêu cầu test + fixture (Protocol 5 R5-03 / Protocol 6 R6-02, R6-03)

#### V10.1. Fixture vàng mới — **CÓ, cần thiết**

Fixture hiện có (`job3594a7a3_chunk0_sample_mono.pdf`) **không có ảnh `/FlateDecode` nào** (1 null
+ 3 DCT + 1 CCITT) → không thể test đường mới. Nếu Dev/QA viết fixture tay theo mô tả này, đó đúng
là loại "mock tự nhất quán với giả định" mà Protocol 5 cấm.

**Cách tạo (đã tự chạy thử để chắc chắn khả thi — Dev chỉ việc lặp lại):**

```
Nguồn: data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf
Trích trang 22 và 25 (0-based) bằng insert_pdf, save(garbage=4, deflate=True)
Đích:  tests/fixtures/babeldoc/job78674af9_flate_sample.pdf
```

Đã kiểm chứng kết quả của cách trích này:

| Chỉ số | Giá trị đo |
|---|---|
| Kích thước fixture | **1.66 MB** |
| Thành phần | 1 ảnh `FlateDecode` **Gray** ICC (122 KB, engraving), 1 ảnh `FlateDecode` **CMYK** ICC (835 KB, ảnh chụp), 1 ảnh `DCTDecode` Gray (phải giữ nguyên byte) |
| Chạy thuật toán v2 | 1.66 MB → **0.85 MB**, `recompressed=2, skip_filter=1`, 0 lỗi |
| Chạy thuật toán v1 (hiện tại) | **0 ảnh re-encode** — tức fixture này *thất bại* với code cũ và *pass* với code mới, đúng yêu cầu của một regression fixture |
| Ảnh trong fixture có byte y hệt file gốc? | **có** — `save(deflate=True)` không đụng stream ảnh đã có filter (đã hash SHA-256 đối chiếu 60/60 xref) |

Bắt buộc ghi xuất xứ vào `tests/fixtures/babeldoc/README.md` (job id, số trang gốc, ngày trích,
lệnh trích) theo đúng nếp các fixture hiện có.

**Tuỳ chọn (PM quyết theo khẩu vị dung lượng repo)**: thêm **trang 13** vào fixture sẽ phủ thêm 29
ảnh `Separation(DeviceCMYK,Black)` 1×1 + 17 DCT Separation — tức dữ liệu thật cho **guard 4d** và
**guard 4b**. Giá phải trả: fixture tăng **1.66 MB → 8.70 MB** (font subsetting chỉ giảm được
0.24 MB, đã thử). **Khuyến nghị: KHÔNG thêm** — thay vào đó test guard 4d/4b bằng cách gọi hàm với
`min_recompress_bytes=0` trên fixture nhỏ (xem V10.2 mục 5), và ghi nhận rằng nhánh
`images_skipped_colorspace` với ảnh **lớn** không có mẫu thật (`[UNVERIFIED]`, hành vi mong đợi là
"không làm gì" nên an toàn theo mặc định).

#### V10.2. Danh sách test bắt buộc

1. **Đường mới, nội dung không chỉ status (R6-03)**: chạy `compress_pdf_images` thật trên fixture
   mới → `page_count` không đổi (2), **text từng trang giống hệt trước/sau**, file nhỏ đi, và
   `stats.images_recompressed == 2`. Assert **giá trị cụ thể**, không chỉ "chạy không lỗi".
2. **Guard không nén chồng (giữ từ v1)**: ảnh `DCTDecode` trong fixture mới phải có stream
   **byte-identical** trước/sau (SHA-256).
3. **Hồi quy v1**: giữ nguyên toàn bộ test hiện có trên
   `job3594a7a3_chunk0_sample_mono.pdf` — phải xanh **không sửa assertion** (đã đo: kết quả v2
   trùng v1 trên fixture đó, xem V7).
4. **`/Decode` (V4.4)**: lấy fixture mới, inject `/Decode [1 0]` vào 1 xref Flate rồi chạy hàm →
   sau khi chạy `xref_get_key(xref, "Decode")` phải trả `('null','null')`. Đây là test cho một lỗi
   **chưa từng phát tác**, nên bắt buộc phải có test mới giữ được nó đã sửa.
5. **Guard ngưỡng nhỏ + colorspace**: gọi `compress_pdf_images(..., min_recompress_bytes=0)` trên
   fixture mới → không được raise, và số ảnh re-encode không tăng thêm ngoài dự kiến. (Nếu PM chọn
   thêm trang 13 vào fixture thì test này assert luôn `images_skipped_colorspace == 29`.)
6. **Data lineage (R6-02, giữ từ S9)**: `compress_pdf_images.assert_called_with(merged_path, ...)`
   đúng path mà `merge_chunk_pdfs` vừa ghi; và nhánh `pdf2zh` khẳng định **không** được gọi.
7. **Thứ tự (giữ từ S9)**: job có output rỗng chữ phải `failed` bằng thông báo của guard BR-OCR-03,
   không phải lỗi nén.
8. **R5-03 / R6-03 gate**: QA phải chạy **1 job thật xuyên suốt** (babeldoc, file có ảnh Flate) và
   **mở file output kiểm tra nội dung** — không chấp nhận chỉ đọc `status=completed`. Có thể tái sử
   dụng chính file 46.87 MB làm đối chứng "trước".

### V11. Trạng thái verify

| Hạng mục | Trạng thái |
|---|---|
| Hiện trạng "re-encode 0 ảnh" trên job sự cố | ✅ Verified — chạy lại logic đang ship, `recompressed=0` |
| Phân bố filter 6 job output thật | ✅ Verified — đo trực tiếp từng file |
| Flate ảnh chụp nén được 12–48% | ✅ Verified — re-encode thật 19/19 ảnh |
| Kết quả cuối 46.87 → 25.19 MB | ✅ Verified end-to-end trên bản copy file thật |
| Bảo toàn text / số trang | ✅ Verified — 59,193 ký tự giống hệt, 30/30 trang |
| Bảo toàn màu (không đảo CMYK) | ✅ Verified — pixel-diff 0.0613/255 + xem ảnh render thật |
| C1 `colorspace.name` của ICCBased | ✅ Verified — và đã thực sự mắc bẫy này 1 lần khi spike |
| C2 `tobytes("jpeg")` raise với Separation | ✅ Verified — 29 xref thật |
| C3 `update_stream` xoá `/Filter` + `/DecodeParms` | ✅ Verified — in object dict trước/sau |
| C4 `Pixmap` áp dụng `/Decode`, `update_stream` không xoá | ✅ Verified — samples `ffff…` vs `0000…` |
| Hồi quy trên fixture v1 | ✅ Verified — kết quả trùng v1 |
| Fixture mới khả thi ở 1.66 MB | ✅ Verified — đã trích thử và chạy cả v1 lẫn v2 lên nó |
| `Filter` dạng **array** (`[/ASCII85Decode /FlateDecode]`) | ⚠️ **`[UNVERIFIED]`** — 0 mẫu thật trong 6 job. Không chặn Dev (không match ⇒ bỏ qua ⇒ an toàn) |
| Guard 4d với ảnh **lớn** colorspace lạ (Indexed/DeviceN/Lab) | ⚠️ **`[UNVERIFIED]`** — chỉ có mẫu 1×1. Hành vi mong đợi: bỏ qua |
| Ảnh có `/SMask` hoặc `/ImageMask` | ⚠️ **`[UNVERIFIED]`** (kế thừa S10) — vẫn 0 mẫu thật sau khi khảo sát thêm 5 job |
| **Sửa BR-IMGCOMP-02 (mở rộng phạm vi)** | ⏸ **Chờ user duyệt — Protocol 2** |
| **V9.1 `bilingual_merge.py` save không nén** | ⏸ **Chờ PM/user quyết định (A)/(B)** — không chặn phần còn lại của v2 |
| V9.2 job 520 MB toàn DCT | ⏸ Backlog, chưa thiết kế |

## US-16 v2 — Phản biện của Domain Expert (2026-09-08)

**Người viết**: Domain Expert (Fable) — chuyên PDF internals / image compression / color management.
**Vai trò**: CHỈ phản biện độc lập thiết kế "US-16 v2" của Tech Lead ở trên. **Không sửa code trong
`src/`, không quyết định thay PM/user** ở các điểm Protocol 2.
**Kỷ luật**: mọi số liệu của Tech Lead đều được **tự chạy lại từ đầu** trên bản copy của dữ liệu
thật (không đụng file production), bằng script tạm viết riêng (không kế thừa script của Tech Lead).
Không có claim nào dưới đây là "tôi nghĩ" — mỗi kết luận đi kèm số đo tự chạy hoặc nguồn tự đọc.

**Môi trường**: `.venv/bin/python` (Python 3.14), PyMuPDF **1.28.2** (cùng bản Tech Lead dùng).
Renderer độc lập: **macOS Quartz** qua `/usr/bin/sips` (150 dpi) — đây là engine của Preview.app,
hoàn toàn không dùng MuPDF. Chrome/pdfium: **không thử được** (Browser pane từ chối mở PDF local),
đánh dấu `[UNVERIFIED]` ở X8. `numpy` không có trong venv → pixel-diff tính bằng pure Python trên
`Pixmap.samples` (chậm hơn nhưng cùng kết quả). Dữ liệu: đúng 6 job output Tech Lead đã khảo sát
(V3.3) + file sự cố `78674af9` + fixture `job3594a7a3_chunk0_sample_mono.pdf`.

### X0. Kết luận ngắn

**Số liệu của Tech Lead đúng toàn bộ** (X1 — 100% tái hiện được, kể cả thứ tự 4 trang lệch pixel
nhiều nhất). **Nhưng thiết kế V5 chưa đủ chín để trình user** vì 3 lỗi mà cách đo của Tech Lead
**không thể nhìn thấy** — hai trong số đó là lỗi có sẵn trong code v1 đang ship, cùng loại với
lỗi `/Decode` (C4) mà chính Tech Lead đã tìm ra:

1. **Guard 4d không bắt được `Indexed`** (X2): `Pixmap(doc, xref)` **tự expand** Indexed sang base
   colorspace, nên `pix.colorspace.name` trả `'DeviceCMYK'`, không bao giờ trả `'Indexed(...)'`.
   Chạy thật: 2 ảnh Indexed lọt qua guard và bị JPEG hoá. BR-IMGCOMP-02c hứa "Indexed giữ nguyên"
   nhưng V5 không thực hiện được lời hứa đó.
2. **Ghi đè `/ColorSpace` làm mất ICC profile → lệch màu thật trên macOS Preview** (X3): đo bằng
   Quartz, trang 17 lệch **6.98/255**, trang 29 lệch **5.55/255**; giữ nguyên `/ColorSpace` → còn
   **0.97 / 0.76**. MuPDF cho **0.00** với cùng thay đổi — tức phép đo "0.0613/255" ở V7 mù hoàn
   toàn với lỗi này. Lỗi có sẵn trong v1 (`image_compress.py:120-122`).
3. **`/Mask` color-key không có guard** (X4): `Pixmap` trả `alpha=1`, code drop alpha, `update_stream`
   **giữ nguyên** key `/Mask` → mask áp lên sample JPEG đã đổi. Guard 4a (`info[1]`) không thấy
   `/Mask`. Lỗi có sẵn trong v1; 0 mẫu thật trong kho — `[UNVERIFIED]` trên production, nhưng cơ chế
   đã chứng minh bằng inject.

Ngoài ra 2 chỗ **kết luận đúng nhưng lý do sai**, cần sửa câu chữ trước khi Dev đọc: ngưỡng 4 KB
(X5) và cơ chế phình file song ngữ V9.1 (X6 — là **font bị nhân bản 65 lần**, không phải "không
nén"; `deflate=True` đơn thuần cho **0 byte** lợi ích, `garbage=4` mới là tham số quyết định).

**Khuyến nghị cuối (X9)**: Tech Lead sửa V5 ở 3 điểm blocking (4d, bước 7, thêm guard `/Mask`) + sửa
câu chữ 4b và V9.1, rồi mới trình user. Không cần đo lại từ đầu — mọi số đo còn lại đứng vững.

### X1. Đối chiếu số liệu Tech Lead — tất cả tái hiện được

| Claim Tech Lead | Tự chạy lại | Trạng thái |
|---|---|---|
| V2.1 logic đang ship → `recompressed=0` trên file sự cố | Đọc code `image_compress.py:81-84` + khảo sát: file có **0** xref `Filter: null` → đúng 0 | ✅ |
| V3.1 57 Flate / 42 DCT / 0 null; 28.72 MB / 11.12 MB | 57 / 42 / 0; 30.12 MB (= 28.72 **MiB**) / 11.66 MB (= 11.12 MiB). *Tech Lead ghi "MB" nhưng là MiB — nhất quán trong toàn section, không ảnh hưởng kết luận* | ✅ |
| V3.2 phân bố kích thước 57 ảnh Flate; 100 B–4 KB rỗng **trên file này** | 4 ≥1M + 13 100K–1M + 1 50–100K + 1 4–50K + 38 <100 B; đúng, khoảng 100 B–4 KB rỗng *trên file này* (nhưng xem X5) | ✅ (file này) |
| V3.3 bảng 6 job | Đo lại từng file: khớp **toàn bộ** số xref và bytes (sau quy đổi MiB) | ✅ |
| V4.3 JPEG q85 của 19 ảnh: 28.72 → 7.04 MiB, từng dòng 1144/983/882/986/155/1062 | Khớp **từng byte** (vd 1144: 10,074,126 → 2,212,526) | ✅ |
| C1 `colorspace.name` = `'ICCBased(CMYK,Artifex CMYK SWOP Profile)'` | Tái hiện đúng chuỗi; xref 889 = `'Separation(DeviceCMYK,Black)'` | ✅ |
| C2 `tobytes("jpeg")` raise `FzErrorArgument code=4` với Separation | Tái hiện | ✅ |
| C3 `update_stream` xoá `/Filter` + `/DecodeParms` | Inject `/DecodeParms` → sau update_stream: `('null','null')`, object dict không còn key | ✅ |
| C4 `Pixmap` áp `/Decode`; `update_stream` giữ `/Decode` | Inject `[1 0 1 0 1 0 1 0]` → 64 sample đầu đảo đúng (`a+b==255`); sau update_stream key vẫn còn | ✅ |
| `xref_set_key(x, "Decode", "null")` = xoá theo ngữ nghĩa PDF | `xref_get_key` → `('null','null')`; sau `save(garbage=4)` + reload object vẫn ghi `/Decode null` nhưng vẫn `('null','null')`; Quartz render đúng (X7.1) | ✅ |
| V7 46.87 → 25.19 MiB, 1.5 s, 19/42/38/0, 59,193 ký tự, 30/30 trang | 46.87 → 25.19 MiB, **1.4 s**, 19 re-encode / 42 skip filter / 38 skip nhỏ / 0 lỗi / 0 nở file; 59,193 = 59,193, 30/30 trang text giống hệt | ✅ |
| V7 pixel-diff MuPDF, 4 trang xấu nhất p17 > p29 > p22 > p26 | 100 dpi: mean 0.0409 (Tech Lead 0.0613 — khác dpi), thứ tự **đúng y hệt** p17 (0.53) > p29 (0.45) > p22 (0.07) > p26 (0.04) | ✅ |
| V7 DCT giữ nguyên byte | SHA-256 theo **nội dung** (xref bị `garbage=4` đánh số lại — không so theo xref được): 42 hash gốc ⊆ 61 hash sau | ✅ |
| V8.2 biến thể (B) bỏ ảnh xám → 25.34 MiB | 25.34 MiB, 16 re-encode, 3 skip | ✅ |
| V9.1 song ngữ 86.97 → 7.40 MiB, 1.0 s | 86.97 → 7.40 MiB, 1.0 s; f18f796c 413.76 → **42.31 MiB**; text 596/596 giống; pixel-diff 6 trang ngẫu nhiên = **0.0** | ✅ số — ❌ **cơ chế** (X6) |
| V10.1 fixture trang 22+25 = 1.66 MiB, 3 ảnh, v2 → 0.85 MiB `recompressed=2, skip_filter=1` | 1.66 MiB; Flate ICC CMYK 656×659 (835 KB) + Flate ICC Gray 702×403 (122 KB) + DCT Gray 316×82; v2 → 0.85 MiB, 2/1/0 lỗi | ✅ |
| V10.1 thêm trang 13 → ~8.7 MB | 9.91 MiB (không subset font) — cùng kết luận: quá to | ✅ |
| Filter dạng array `[UNVERIFIED]` | Inject thử: `xref_get_key` trả `('array', '[/FlateDecode]')` và `('array', '[/ASCIIHexDecode/FlateDecode]')` — **không có khoảng trắng giữa các name**. Substring check như V5 bước 3 hoạt động; `value.split()` sẽ sai. `Pixmap(doc, xref)` decode được `[/FlateDecode]` | ✅ hành vi API (vẫn 0 mẫu thật) |

### X2. KHÔNG ĐỒNG Ý #1 — Guard 4d (colorspace) không bắt được `Indexed`

**Claim V5 bước 4d**: skip khi `pix.colorspace.name` là `Separation(...)`, `Indexed(...)`,
`DeviceN(...)`, `Lab`, `None`.

**Phản chứng (chạy thật)**: job `136645f9` (Tech Lead có khảo sát ở V3.3 nhưng chỉ đếm filter, không
đếm colorspace) có **277 ảnh `/FlateDecode` colorspace `[/Indexed /DeviceCMYK hival …]`** — mẫu
thật cho đúng cái Tech Lead ghi `[UNVERIFIED] chỉ có mẫu 1×1`. Với 3 xref Indexed điển hình
(3691 209×188, 3071 80×112, 3132 46×56):

```
Pixmap(doc, 3691): n=4 alpha=0 colorspace.name='DeviceCMYK'   ← KHÔNG phải 'Indexed(...)'
tobytes("jpeg") → OK, 4267 byte
```

MuPDF **expand Indexed sang base colorspace ngay khi dựng Pixmap** (`fz_get_pixmap_from_image` →
`fz_convert_indexed_pixmap_to_base`), khác với Separation (giữ nguyên, n=1). Hệ quả: nhánh
`Indexed(...)` trong guard 4d là **dead code** — không bao giờ match.

Chạy thuật toán V5 với `min_recompress_bytes=0` trên `136645f9` để bóc riêng guard 4d:

```
scanned=1503 recompressed=2 skip_filter=1110 skip_larger=347 skip_cs=44 errors=0
→ 2 ảnh được re-encode: CẢ HAI đều là Indexed (1079 B và 1291 B), lọt guard với tên 'DeviceCMYK'
→ skip_cs=44: toàn bộ là Separation — guard chỉ bắt được đúng cái Tech Lead đã thấy trong file sự cố
```

Trên dữ liệu hiện có hậu quả = 0 (cả 277 ảnh đều < 4 KB nên guard 4b chặn trước). Nhưng **BR-IMGCOMP-02c
hứa với user "ảnh `Indexed` giữ nguyên"** và V5 không giữ được lời hứa đó với ảnh Indexed ≥ 4 KB —
đúng nhóm biểu đồ/bảng dạng palette ≤ 256 màu mà JPEG làm hỏng (viền màu bết, chữ nhỏ nhoè), và
guard nở file **không** bảo vệ được vì JPEG của ảnh palette thường vẫn nhỏ hơn Flate.

**Cách sửa (đã verify công cụ)**: `get_page_images(pno, full=True)` trả **`info[4]` = bpc (int, đã
resolve indirect ref)** và **`info[5]` = tên họ colorspace lấy từ PDF dict**, đo trên 2 file thật:

| `info[5]` quan sát được | Ở file | Ghi chú |
|---|---|---|
| `'DeviceGray'`, `'DeviceRGB'`, `'DeviceCMYK'` | cả 2 | |
| `'ICCBased'` | cả 2 | không kèm N — vẫn cần `pix.n ∈ {1,3,4}` sau khi dựng Pixmap |
| `'Indexed'` | `136645f9` (277 Flate) | **đây là cái cần bắt** |
| `'Separation'` (alt `'DeviceCMYK'` ở `info[6]`) | cả 2 | |
| `'DeviceN'` (alt `'DeviceCMYK'`) | cả 2 (chỉ trên DCT) | |

⇒ Guard 4d nên là **allowlist trên `info[5]` ∈ {DeviceGray, DeviceRGB, DeviceCMYK, ICCBased}, chạy
TRƯỚC khi dựng Pixmap** (rẻ hơn, đúng tinh thần "rẻ → đắt" của V5), rồi giữ kiểm tra
`pix.n ∈ {1,3,4}` + `pix.colorspace.name` như lớp thứ hai. Cách này cũng loại luôn 29+44 ảnh
Separation **trước** Pixmap thay vì sau. `CalRGB`/`CalGray`/`Lab`/`Pattern`: `[UNVERIFIED]` (0 mẫu),
allowlist mặc định bỏ qua = an toàn. Tương tự nên đọc bpc từ `info[4]` thay vì
`xref_get_key(xref, "BitsPerComponent")[1] != "8"` — cái sau trả `('xref', 'N 0 R')` nếu key là
indirect ref và sẽ skip nhầm trong im lặng (hiếm, nhưng miễn phí để tránh).

### X3. PHÁT HIỆN MỚI #1 — Ghi đè `/ColorSpace` làm mất ICC profile → lệch màu trên macOS Preview

**Vấn đề**: V5 bước 7 (kế thừa v1 `image_compress.py:120-122`) ghi
`ColorSpace → /DeviceCMYK | /DeviceRGB | /DeviceGray theo pix.n`. Với ảnh gốc `[/ICCBased …]`
(19/19 ảnh cần nén của file sự cố, 3/3 của `f18f796c`), thao tác này **vứt ICC profile**. Với MuPDF
điều đó vô hại vì DeviceCMYK mặc định của MuPDF *chính là* profile "Artifex CMYK SWOP" đang nhúng
trong file (đã đọc tag `desc` của ICC stream 157: `Artifex CMYK SWOP Profile`, 1064: `Artifex
Software sGray ICC Profile`). Nhưng viewer khác map `DeviceCMYK` sang profile mặc định của **họ**
(Quartz: "Generic CMYK Profile") → màu đổi.

**Đo bằng Quartz (`sips`, 150 dpi, cùng trang render 2 lần, so từng pixel)**:

| So sánh (Quartz) | Trang 17 (2 ảnh CMYK lớn) | Trang 29 (ảnh táo/gỗ) | Cùng phép so bằng MuPDF |
|---|---|---|---|
| Gốc vs v2 như V5 (ghi `/DeviceCMYK`) | **6.98/255**, max 102 | **5.55/255**, max 56 | 0.53 / 0.45 |
| Gốc vs v2 **giữ nguyên `/ColorSpace`** (ICCBased) | **0.97/255**, max 88 | **0.76/255**, max 45 | 0.53 / 0.45 (**y hệt**) |
| **Control**: chỉ đổi ICC→`/DeviceCMYK`, giữ Flate, **không JPEG** | — | **4.38/255**, max 25 | **0.00 / 0** |

Hàng control là bằng chứng quyết định: **JPEG không phải nguyên nhân**, riêng việc đổi
`/ColorSpace` đã gây 4.38/255 trên Quartz và **0.00 trên MuPDF**. Tức mọi số "pixel-diff" ở V7 và
V8.2, dù đúng, **không có năng lực phát hiện** loại lỗi này — cùng bản chất với bài học C4: đo bằng
chính thư viện tạo ra kết quả thì chỉ chứng minh nhất quán với chính nó.

Về mức độ: 5–7/255 là lệch tông/độ bão hoà **thấy được khi đặt cạnh nhau nhưng không "sai màu" rõ
rệt** (đã crop vùng táo xanh/gỗ nâu render Quartz 3 biến thể và nhìn: khác biệt tinh tế). Không phải
lỗi đảo màu. Nhưng sửa **hoàn toàn miễn phí**: với allowlist ở X2, `Pixmap(doc, xref)` luôn ở đúng
colorspace gốc với cùng số kênh, nên **không cần ghi `/ColorSpace` nữa** — chỉ bỏ dòng đó. Biến thể
giữ ICC: 25.19 MiB (**bằng hệt**), 19 re-encode, 0 lỗi. `[/ICCBased N]` + `/DCTDecode` là tổ hợp
chuẩn (Adobe vẫn xuất như vậy).

Lưu ý thêm: (i) `f18f796c` nhúng **`sRGB IEC61966-2.1` thật** (không phải profile Artifex mặc định)
— nên vấn đề không chỉ giới hạn ở "profile mặc định của MuPDF"; (ii) đây là lỗi **có sẵn trong v1**
với mọi ảnh `Filter: null` gốc ICCBased, độc lập với việc duyệt mở rộng Flate — cùng trạng thái với
`/Decode` ở V4.4; (iii) v1 trước đây cũng chỉ kiểm CMYK bằng MuPDF (Architecture.md dòng 241, 272 —
"render ra PNG và xem tận mắt" bằng PyMuPDF), tức **đây là lần đầu output CMYK JPEG của
`compress_pdf_images` được render bằng viewer không phải MuPDF**. Kết quả tốt: Quartz **không đảo
màu** (nếu đảo, mean đã ở mức 100+), APP14 `transform=0` được hiểu đúng.

### X4. PHÁT HIỆN MỚI #2 — Ảnh có `/Mask` (color-key) không có guard, v1 lẫn v2

Guard 4a chỉ nhìn `/SMask` (qua `info[1]`) và `/ImageMask`. Key **`/Mask`** có 2 dạng: array
color-key (`/Mask [min max …]` — sample trong dải này trong suốt) và ref tới stencil mask. Inject
`/Mask [200 255]` vào xref 1062 (Gray 702×403) trên bản copy:

```
Pixmap(doc, 1062): n=2 alpha=1                 ← MuPDF áp color-key thành alpha
get_page_images(...)[1] (smask) = 0            ← guard 4a KHÔNG thấy
sau Pixmap(pix, 0) + update_stream(...):  dict còn nguyên  /Mask[200 255]  (và /Interpolate true)
```

Hệ quả nếu xảy ra thật: alpha bị vứt, JPEG ghi đè, nhưng `/Mask [200 255]` vẫn áp lên **sample JPEG
đã đổi giá trị** → vùng trong suốt bị lốm đốm/mất, hoặc vùng không trong suốt bị trong suốt. Khảo
sát 6 job: **0 xref có `/Mask`** → `[UNVERIFIED]` trên production, cùng hạng với `/SMask` ở S10.
Sửa rẻ: thêm vào 4a `if doc.xref_get_key(xref, "Mask")[0] != "null" → skip unsupported` (bắt cả
array lẫn ref), và đổi `if pix.alpha: pix = Pixmap(pix, 0)` thành **skip** — trong luồng này alpha
chỉ có thể đến từ SMask/color-key, drop alpha luôn là mất thông tin.

### X5. KHÔNG ĐỒNG Ý #2 — Lý do của ngưỡng 4 KB sai, con số vẫn đúng

V5 4b: *"Đo: khoảng 100 B–4 KB rỗng hoàn toàn (V3.2) nên ngưỡng này không cắt nhầm ảnh thật nào."*
Đó là tính chất của **1 file**. Khảo sát lại 6 job theo bucket:

| Job | Flate < 100 B | **100 B–4 KB** | 4–50 KB | 50–100 KB | 100 KB–1 MB | ≥ 1 MB |
|---|---|---|---|---|---|---|
| `78674af9` | 38 | **0** | 1 | 1 | 13 | 4 |
| `136645f9` | 207 | **186** | 0 | 0 | 0 | 0 |
| `4c9834bf` | 0 | 0 | 1 (4,678 B RGB 274×24) | 5 | 7 | 0 |
| `f18f796c` | 0 | 0 | 1 | 1 | 1 | 0 |

Khoảng 100 B–4 KB **không rỗng** trong kho (186 icon Indexed 46×56 … 209×188). Lý do đúng để giữ
4096 là số đo khác: tổng bytes Flate < 4 KB toàn kho = **0.08 MiB** (431 ảnh); chạy `136645f9` với
ngưỡng 0 → 347 ảnh bị guard nở file chặn, 44 skip colorspace, **chỉ 2 ảnh qua được, tiết kiệm 194
byte** — đổi lấy 393 lần dựng Pixmap. Ngưỡng 4096 đúng chỗ, nhưng câu lý giải trong V5 cần thay bằng
số này để Dev/Reviewer sau không tin nhầm rằng "không có ảnh nào ở đó".

### X6. KHÔNG ĐỒNG Ý #3 — V9.1 chẩn đoán sai cơ chế; cách sửa vẫn đúng nhưng phải ghi đúng lý do

V9.1 viết: *"~84 MB là content stream/font không nén"* và đề xuất `save(garbage=4, deflate=True)`.
Kiểm kê stream của `bilingual_vi_en.pdf` (`4c9834bf`, 596 trang, 86.97 MiB):

| Loại stream | Filter | Số stream | Bytes |
|---|---|---|---|
| font (`/Length1`) | **`/FlateDecode`** (đã nén) | **592** | **71.08 MiB** |
| content/khác | `/FlateDecode` | 2,598 | 7.96 MiB |
| image | `/FlateDecode` | 26 | 2.65 MiB |

Toàn bộ đã Flate. Đếm hash nội dung 592 font stream → **chỉ 9 nội dung duy nhất** (0.31 MiB); bản
đơn ngữ `translated_vi.pdf` của cùng job có đúng **9** font stream. Tức `create_bilingual_pdf()` gọi
`insert_pdf` **từng trang một** (`bilingual_merge.py:18-20`) và mỗi lần gọi chép lại 9 font của
bản VI → 9 × ~65 = 592 bản sao. (File EN nguồn 2.64 MiB không có font nhúng `/Length1` nào — toàn bộ
nhân bản đến từ phía VI.)

Bằng chứng tách 2 tham số:

| Cách save | Kết quả |
|---|---|
| `save(output, deflate=True)` — **chỉ deflate** | **86.97 MiB — 0 byte lợi ích** |
| `save(output, garbage=4, deflate=True)` | 7.40 MiB (font stream còn lại: 9) |

⇒ **`garbage=4` (dedupe stream trùng) là tham số làm việc; `deflate=True` vô nghĩa ở đây.** Đề xuất
(B) của Tech Lead vẫn cho đúng kết quả, nhưng nếu Architecture.md ghi lý do "không nén" thì một
Dev/Reviewer "tối giản" thành `deflate=True` sẽ mất **toàn bộ** lợi ích mà test kích thước tương đối
vẫn có thể pass (file không to *hơn*). Cần sửa câu chữ V9.1 trước khi giao.

Về rủi ro của (B): cùng pattern đã verify ở S8; tự đo thêm: text 596/596 trang giống hệt, pixel-diff
72 dpi trên 6 trang ngẫu nhiên = **0.0/255 tuyệt đối** (dedupe stream byte-identical không thể đổi
glyph); `f18f796c` 413.76 → 42.31 MiB. Tôi **không quyết định (A)/(B)** — chỉ xác nhận (B) an toàn
về mặt kỹ thuật và nêu rõ tham số nào mới là thứ cần giữ. Vẫn là Protocol 2 vì chạm cả 2 engine.

### X7. ĐỒNG Ý — có bổ sung cách verify

**X7.1 Sửa `/Decode` (V4.4, V5 bước 8) — ĐỒNG Ý, đã chứng minh bằng số.** Inject `/Decode
[1 0 1 0 1 0 1 0]` vào xref 1144 (trang 29) trên bản copy, tạo 3 file: *inj* (gốc đã inject — đây là
"sự thật" viewer phải hiển thị), *v2-fixed* (V5 đầy đủ), *v1-nofix* (re-encode nhưng giữ `/Decode`
như code đang ship):

| So với *inj* | MuPDF (72 dpi) | Quartz (100 dpi) | Nhìn tận mắt (Quartz) |
|---|---|---|---|
| *v2-fixed* | **0.46/255**, max 18 | 10.23/255 (gồm phần lệch ICC ở X3) | ảnh tối/đảo **giống inj** |
| *v1-nofix* | **42.28/255**, max 193 | 25.10/255, max 140 | ảnh **sáng bình thường** = đảo 2 lần |

Cả 2 renderer cùng kết luận. Quartz hiểu `/Decode null` là "không có" (nếu không, ảnh đã mất hoặc
lệch ~40). Đề nghị test V10.2 #4 assert thêm **mức pixel** (render trang sau khi sửa ≈ render gốc
đã inject, trong ngưỡng nhiễu JPEG) chứ không chỉ `xref_get_key == ('null','null')` — vì lỗi này
chưa từng phát tác, assertion ở tầng key không đủ chứng minh viewer hiển thị đúng.

**X7.2 Mở rộng phạm vi sang `/FlateDecode` — ĐỒNG Ý.** Lập luận V4.1 đúng: Flate là lossless, không
thuộc lý do "không nén chồng". Số liệu X1. Lợi ích phụ thuộc tài liệu (V3.3 kết luận 2) — tự đo thêm
2 job Tech Lead chưa chạy V5 lên: `4c9834bf` 6.19 → **5.16 MiB** (13 ảnh DeviceGray/RGB), `f18f796c`
35.97 → **35.73 MiB** (3 ảnh sRGB); text 298/298 và 1040/1040 trang giống hệt.

**X7.3 V8.1 không cần heuristic "ảnh chụp hay đồ hoạ" — ĐỒNG Ý, kèm cảnh báo phạm vi.** Tôi tìm
phản ví dụ bằng tỉ lệ nén Flate (`bytes_flate / (w×h×n)` — đồ hoạ phẳng thường < 0.1): xref 985
(**0.063**), 1146 (0.107), 172/197/206 (~0.3), 3 ảnh `f18f796c` (0.17–0.22). Render 400 dpi
trước/sau và nhìn từng cái: **đều là ảnh chụp** có nền trắng/giấy lớn (collage mở chương, phác thảo
bút chì trên giấy, ảnh phới lồng) — không phân biệt được. Guard nở file đủ **cho 35 ảnh đã gặp**.
Không có mẫu đồ hoạ phẳng > 4 KB nào trong kho → khả năng "biểu đồ/bảng dinh dưỡng dạng ảnh bị
JPEG hoá nhưng vẫn nhỏ hơn Flate" vẫn là `[UNVERIFIED]`, không phải đã loại trừ. Đề nghị **rẻ**: log
`debug` tỉ lệ này cho mỗi ảnh re-encode để QA/Reviewer soi được outlier ở job thật, không thêm
ngưỡng.

**X7.4 V8.2 giữ ảnh xám 8-bit — ĐỒNG Ý.** 12 ảnh DeviceGray của `4c9834bf` (ảnh SEM/ruột bánh, tỉ lệ
Flate 0.3–0.63) nhìn 400 dpi không phân biệt; (B) tái hiện 25.34 MiB.

**X7.5 Guard 4c bpc ≠ 8 — ĐỒNG Ý về logic**; kho không có ảnh Flate nào bpc ≠ 8 (cả 6 job đều 8) →
`[UNVERIFIED]` trên dữ liệu thật, an toàn theo mặc định. Đọc từ `info[4]` (X2).

**X7.6 Fixture 22+25 — ĐỒNG Ý là cần và đúng cỡ**, nhưng nó **chỉ phủ 1 job, 1 producer, 1 ICC
profile**, không phủ DeviceGray thuần, không phủ Indexed. Đo 2 ứng viên bổ sung: trang 99 của
`4c9834bf` = **0.48 MiB**, 1 ảnh Flate `DeviceGray` 800×523 (job khác, colorspace dạng name, v2 →
0.31 MiB) — đáng thêm; trang 168 của `136645f9` = 1.15 MiB, 5 ảnh Indexed + Separation (mẫu thật
cho guard 4d với `min_recompress_bytes=0`) — tuỳ PM cân dung lượng. Không thêm trang 13/17 (9.9 /
14 MiB).

### X8. Điểm nhỏ và `[UNVERIFIED]` còn lại

- **`/LZWDecode`, `/RunLengthDecode`**: cũng lossless như Flate; V5 bước 3 gộp vào "đã nén, bỏ
  qua" và đếm vào `images_skipped_already_compressed` — sai về ngữ nghĩa (không phải "nén chồng")
  nhưng an toàn. 0 mẫu trong kho. Đề nghị ít nhất ghi rõ trong V5 là **cố ý loại, `[UNVERIFIED]`**,
  thay vì im lặng; đưa vào eligibility là việc 1 dòng nếu sau này gặp.
- **pdfium (Chrome) / Acrobat**: `[UNVERIFIED]` — không có công cụ trên máy này. Đề nghị QA (V10.2
  #8) mở file output bằng **Chrome và Preview** ít nhất 1 lần, nhìn trang có ảnh CMYK lớn (p17/p29
  của file sự cố) để loại trừ đảo màu — Quartz đã pass, pdfium chưa.
- **Bẫy đo lường (đồng ý với V7)**: JPEG CMYK MuPDF ghi có APP14 `transform=0`, dữ liệu **thẳng**
  (không theo quy ước Adobe đảo); `Pixmap(jpeg_bytes)` standalone của chính MuPDF đọc lại ra
  `ffff…` từ `0000…` (tự đảo). Ai dùng `extract_image`/`pdfimages` rồi mở file JPEG rời sẽ thấy âm
  bản và báo bug giả. Ghi vào docstring để khỏi điều tra lại.
- Kết quả 4 trang lệch nhiều nhất giống hệt Tech Lead → phép đo pixel-diff của Tech Lead làm đúng,
  chỉ thiếu renderer thứ hai.

### X9. Khuyến nghị cuối — CHƯA sẵn sàng trình user; cần Tech Lead sửa 5 điểm (không cần đo lại)

**Blocking (sửa V5 rồi mới trình — mỗi điểm ≤ 5 dòng code, đều đã verify công cụ ở trên):**

1. **4d**: allowlist `info[5] ∈ {DeviceGray, DeviceRGB, DeviceCMYK, ICCBased}` chạy **trước**
   Pixmap; giữ `pix.n ∈ {1,3,4}` làm lớp hai. Bỏ nhánh `Indexed(...)` chết. (X2)
2. **Bước 7**: **không ghi `/ColorSpace`** (bỏ `_COLORSPACE_BY_CHANNELS`), giữ ICC profile gốc. Ghi rõ
   đây là sửa lỗi có sẵn của v1, độc lập với duyệt scope — cùng hạng với `/Decode`. (X3)
3. **4a**: thêm guard `/Mask` (array hoặc ref) và đổi drop-alpha thành skip. (X4)
4. **V9.1**: viết lại cơ chế = font nhân bản do `insert_pdf` từng trang; `garbage=4` là tham số quyết
   định, `deflate=True` đơn thuần = 0 lợi ích. (X6) — vẫn để PM/user chọn (A)/(B).
5. **4b**: thay câu lý giải "khoảng 100 B–4 KB rỗng" bằng số đo toàn kho (0.08 MiB, 194 byte). (X5)

**Non-blocking (đề nghị, PM quyết):** đọc bpc từ `info[4]`; test `/Decode` assert mức pixel; test
mới cho ICC (`info[5]` của ảnh re-encode vẫn `'ICCBased'`), `/Mask` (inject → ảnh vẫn Flate,
đếm `unsupported`), Indexed (`min_recompress_bytes=0` → `images_skipped_colorspace` tăng đúng số);
fixture bổ sung `4c9834bf` p99 (0.48 MiB); QA mở Chrome + Preview; log tỉ lệ Flate; ghi chú LZW.

**Sau 5 sửa trên**, tôi đánh giá thiết kế **đủ chín** để trình user theo Protocol 2 — số liệu lợi
ích (−46.3% trên file sự cố, lợi ích phụ thuộc tài liệu) và các guard còn lại đều đứng vững qua
verify độc lập, và cả 3 lỗi mới đều là lỗi có sẵn của v1 mà v2 là dịp sửa rẻ nhất.

### X10. Cách tái lập (script tạm ở scratchpad phiên làm việc, không lưu vào repo)

Mọi phép đo dùng bản **copy** trong scratchpad; file production không bị mở ở chế độ ghi. Các bước
tái lập chính (đủ để Tech Lead/QA lặp lại, không cần script của tôi):

1. *Khảo sát*: với mỗi `data/outputs/*/translated_vi.pdf`, gom xref qua `get_page_images(full=True)`,
   đọc `Filter`/`BitsPerComponent`/`ColorSpace`/`Mask`/`Decode` bằng `xref_get_key`, bucket theo
   `len(xref_stream_raw)`; `info[5]` cho họ colorspace.
2. *Thuật toán V5* viết lại độc lập theo đúng text (có cờ `keep_icc`, `min_bytes`, biến thể B);
   so DCT bằng **set SHA-256 nội dung** (không theo xref).
3. *Render độc lập*: `insert_pdf` 1 trang → PDF riêng → `sips -s format png -s dpiWidth 150 -s
   dpiHeight 150 in.pdf --out out.png`; so `Pixmap(png).samples` từng byte (mean/max |Δ|).
4. *Control ICC*: chỉ `xref_set_key(x, "ColorSpace", "/DeviceCMYK")` trên 3 xref trang 29, không đổi
   stream → render Quartz và MuPDF.
5. *Inject*: `xref_set_key(x, "Decode", "[1 0 1 0 1 0 1 0]")` / `"Mask", "[200 255]"` /
   `"Filter", "[/ASCIIHexDecode/FlateDecode]"` trên bản copy rồi quan sát `Pixmap`, `update_stream`.
6. *Song ngữ*: kiểm kê stream theo `/Length1`, hash nội dung; `save(deflate=True)` và
   `save(garbage=4, deflate=True)` riêng rẽ.

## US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement.
**Trạng thái**: ⏸ **Chờ user duyệt (Protocol 2)** — xem W10 để biết chính xác 2 điều user cần quyết.
**Quan hệ tài liệu (đọc kỹ trước khi implement)**: mục này **thay thế (supersede)** các phần sau của
mục "US-16 v2" ở trên: **bước 4a, 4b, 4d, bước 7** của V5, và toàn bộ mục **V9.1**. Mọi phần khác
của US-16 v1 (S1–S10) và US-16 v2 (V1–V4, V6, V7, V8, V10, V11) **giữ nguyên hiệu lực**. Khi 2 mục
mâu thuẫn, **mục này thắng** — Dev đọc W6 (thuật toán hợp nhất) là đủ, không phải ghép tay V5 + sửa.

**Phán quyết tổng**: **chấp nhận cả 5 điểm** Domain Expert nêu ở X9. Không có điểm nào tôi bác bỏ.
Có **2 chỗ tôi làm khác cách Expert đề xuất** (W1 lớp hai, W8 mức độ bắt buộc của fixture Indexed) và
**1 phát hiện bổ sung** (W2.2 — điểm 1 và điểm 2 **ràng buộc nhau**, tách ra implement riêng sẽ tạo
lỗi nặng hơn hiện trạng). Cả 3 đều là "làm chặt hơn", không phải bất đồng về kết luận.

### W0. Nguồn xác thực của riêng mục này (R5-01)

Tôi **không đo lại** các số liệu lớn: Domain Expert đã tái hiện độc lập 100% bảng số của tôi (X1)
bằng script riêng **và** renderer khác hẳn (macOS Quartz qua `sips`, không dùng MuPDF) — lặp lại
lần thứ ba không tạo thêm thông tin, chỉ tốn thời gian. Cái tôi tự chạy hôm nay là **đúng phần
contract PyMuPDF mà 3 điểm blocking dựa vào**, trên file nhỏ (46.87 MB):

```
PyMuPDF 1.28.2 / Python 3.14 — data/outputs/78674af9-.../translated_vi.pdf, quét cả 30 trang
get_page_images(pno, full=True) -> tuple 10 phần tử
info[4] = 8            (int, KHÔNG phải str — dùng trực tiếp, không cần xref_get_key)
info[5] = 'DeviceRGB' | 'DeviceCMYK' | 'ICCBased' | 'Separation' | 'DeviceN' | 'DeviceGray'
info[6] = ''  với DeviceX/ICCBased;  'DeviceCMYK'  với Separation/DeviceN (alternate space)
Phân bố 99 xref: DeviceCMYK 24, ICCBased 22, Separation 46, DeviceN 3, DeviceGray 3, DeviceRGB 1
xref_get_key(xref, "Mask") -> ('null','null') khi key vắng mặt   (5/5 xref thử)
Pixmap(doc, 172).colorspace.name -> 'ICCBased(CMYK,Artifex CMYK SWOP Profile)'   (xác nhận lại C1)
```

Hai điều đáng ghi: (i) tổng **99 xref** khớp chính xác V3.1 → dữ liệu tôi đang đọc đúng là file
Expert và tôi đã dùng; (ii) `info[5]` trả **tên trần** (`'ICCBased'`), **không** kèm dấu ngoặc như
`Pixmap.colorspace.name` — nên guard mới **không dính bẫy C1** (không cần xử lý tiền tố `ICCBased(`).

Ba claim tôi **không tự chạy lại**, kế thừa nguyên trạng từ phản biện đã verify của Expert, ghi rõ
để Reviewer biết ranh giới: đo màu bằng Quartz (X3), 277 ảnh Indexed của `136645f9` (X2), kiểm kê
592 font stream của file song ngữ (X6).

### W1. Điểm 1 — Guard colorspace: allowlist trên `info[5]`, chạy TRƯỚC khi dựng Pixmap

**Đồng ý với X2.** Nhánh `Indexed(...)` trong V5 bước 4d là **dead code** đúng như Expert chứng minh:
MuPDF expand Indexed sang base colorspace ngay khi dựng Pixmap, nên `pix.colorspace.name` trả
`'DeviceCMYK'` — không bao giờ trả `'Indexed(...)'`. Guard viết theo tên Pixmap **không thể** thực
hiện lời hứa "Indexed giữ nguyên" của BR-IMGCOMP-02c.

**Spec chốt**:

- Vòng gom xref (V5 bước 2) không chỉ lưu smask nữa, mà lưu **bộ ba** lấy từ cùng một `info`:
  `meta_by_xref[info[0]] = (smask=info[1], bpc=info[4], cs_family=info[5])`, **first sighting wins**
  (cùng lý do đã ghi ở v1: `info` mô tả chính object xref, không phải chỗ đặt trên trang).
- Hằng số mới: `_ELIGIBLE_CS_FAMILIES = {"DeviceGray", "DeviceRGB", "DeviceCMYK", "ICCBased"}`.
- **Guard 4d (mới)**: `cs_family not in _ELIGIBLE_CS_FAMILIES` → `images_skipped_colorspace += 1`,
  log `debug`, `continue` — **trước** mọi lời gọi `Pixmap`. Loại được `Indexed`, `Separation`,
  `DeviceN`, `Lab`, `Pattern`, `CalRGB`, `CalGray`, và cả `''` (không có `/ColorSpace`).
- **Guard 4c (mới, đổi nguồn dữ liệu)**: đọc bpc từ `meta.bpc` (int) thay vì
  `xref_get_key(xref, "BitsPerComponent")`. Lý do Expert nêu (indirect ref trả `('xref','N 0 R')` →
  skip nhầm trong im lặng) là đúng, và `info[4]` đã resolve sẵn — miễn phí, dùng luôn.

**Chỗ tôi làm khác Expert (lớp hai)**: Expert đề xuất giữ `pix.n ∈ {1,3,4}` **và**
`pix.colorspace.name` làm lớp hai. Tôi **bỏ hẳn `pix.colorspace.name` khỏi vai trò guard** và thay
lớp hai bằng **kiểm tra nhất quán số kênh**:

| `cs_family` | `pix.n` bắt buộc |
|---|---|
| `DeviceGray` | 1 |
| `DeviceRGB` | 3 |
| `DeviceCMYK` | 4 |
| `ICCBased` | ∈ {1, 3, 4} (dict không ghi `N` trong `info[5]`) |

Sai → `images_skipped_colorspace += 1`, log `debug`, không ghi gì. Lý do bỏ `colorspace.name`:
(a) sau allowlist nó **không loại thêm được gì** — chính nó là thứ mù với Indexed (X2) nên không
phải lớp phòng thủ thật; (b) giữ nó lại buộc phải viết đúng cái special-case tiền tố `"ICCBased("`
đã **thực sự gây bug một lần** lúc spike (C1) — giữ một biểu thức đã từng sai làm "lớp hai" cho một
guard đã đúng là thêm rủi ro chứ không thêm an toàn. Kiểm tra `pix.n` vs `cs_family` thì **chính
xác** và là đúng bất biến mà bước ghi kết quả (W2) phụ thuộc vào.

### W2. Điểm 2 — Không ghi đè `/ColorSpace` nữa

**Đồng ý với X3.** Bằng chứng quyết định là hàng "control" của Expert: chỉ đổi `[/ICCBased …]` →
`/DeviceCMYK`, **giữ nguyên Flate, không đụng JPEG** → Quartz lệch **4.38/255**, MuPDF lệch
**0.00**. Nghĩa là toàn bộ phép đo pixel-diff của tôi ở V7/V8.2 — dù đúng — **không có năng lực
nhìn thấy lỗi này**, đúng bản chất bài học C4 (đo bằng chính thư viện tạo ra kết quả).

**W2.1. Spec chốt**: xoá hằng `_COLORSPACE_BY_CHANNELS` và xoá dòng
`doc.xref_set_key(xref, "ColorSpace", ...)` (`image_compress.py:120-122`). **Không thay bằng gì cả.**
`Pixmap(doc, xref)` luôn giải mã ở đúng colorspace gốc với đúng số kênh, JPEG ghi ra cũng đúng số
kênh đó (đã ràng buộc bằng lớp hai ở W1) → `/ColorSpace` cũ tiếp tục mô tả đúng stream mới, và ICC
profile gốc được giữ. `[/ICCBased N]` + `/DCTDecode` là tổ hợp chuẩn. Đo của Expert: biến thể giữ ICC
cho **25.19 MiB — bằng hệt** biến thể ghi đè, tức sửa này **miễn phí về dung lượng**.

Các key còn lại ở bước 7 **giữ nguyên**: `Filter → /DCTDecode`, `BitsPerComponent → 8`,
`Width`/`Height` theo `pix`.

**W2.2. [BỔ SUNG CỦA TECH LEAD — không có trong X9] Điểm 1 và điểm 2 ràng buộc nhau, phải vào cùng
một commit.** Đây là điều tôi cho là rủi ro implement lớn nhất của cả đợt này:

- **Hôm nay** (v1 đang ship): ảnh `Indexed` lọt guard → JPEG hoá → nhưng code **ghi đè**
  `/ColorSpace = /DeviceCMYK` theo `pix.n=4`, nên object vẫn **tự nhất quán**. Hậu quả chỉ là "ảnh
  palette bị JPEG hoá" — xấu, mất chất lượng, nhưng **hiển thị được**.
- **Nếu Dev làm điểm 2 mà quên điểm 1**: stream thành JPEG CMYK 4 kênh trong khi `/ColorSpace` vẫn
  là `[/Indexed /DeviceCMYK hival lookup]` — mỗi sample được viewer hiểu là **1 chỉ số bảng màu**.
  Đây là **PDF hỏng**, nặng hơn hẳn hiện trạng.
- Chiều ngược lại (điểm 1 mà không có điểm 2) thì vô hại, chỉ là chưa sửa lệch màu.

⇒ **Ràng buộc bắt buộc cho Dev**: dòng ghi `/ColorSpace` **chỉ được xoá sau khi** allowlist `info[5]`
đã có mặt trong cùng thay đổi, **và** test W8-#9 (mẫu Indexed thật) xanh. Reviewer kiểm tra đúng thứ
tự này (R6-04 áp cho chuỗi guard→ghi trong cùng một hàm).
⚠️ Cơ chế hỏng ở gạch đầu dòng thứ hai là **suy ra** từ số đo đã verify của Expert (X2:
`Pixmap(doc, 3691)` → `n=4`, `colorspace.name='DeviceCMYK'` trên ảnh `[/Indexed /DeviceCMYK …]`) —
**tôi không tự dựng file hỏng để chạy thử**. Không cần dựng: thiết kế cấm nhánh đó xảy ra, và test
W8-#9 khẳng định điều cấm đó có hiệu lực.

**W2.3. Phạm vi**: sửa này là **sửa lỗi có sẵn của v1**, **độc lập** với quyết định mở rộng scope
sang Flate (W10-a) — v1 hôm nay đã vứt ICC profile với mọi ảnh `Filter: null` gốc ICCBased. Cùng
hạng với sửa `/Decode` (V4.4): nên làm kể cả khi user từ chối mở rộng scope. Lưu ý W2.2 vẫn áp dụng
nguyên vẹn trong kịch bản đó.

### W3. Điểm 3 — Guard `/Mask`, và alpha thì skip chứ không drop

**Đồng ý với X4.** Guard 4a hiện chỉ nhìn `/SMask` (qua `info[1]`) và `/ImageMask`; key **`/Mask`**
(cả dạng array color-key lẫn ref tới stencil) không ai thấy, và `update_stream` giữ nguyên key đó →
mask áp lên sample JPEG **đã đổi giá trị**. Cùng loại lỗi im lặng với `/Decode`.

**Spec chốt — bổ sung vào nhóm guard 4a**:

- `mask_type, _ = doc.xref_get_key(xref, "Mask")`; `mask_type != "null"` → `images_skipped_unsupported
  += 1`, log `warning` (hiếm, đáng nhìn thấy), `continue`. Bắt cả `('array', '[200 255]')` lẫn
  `('xref', 'N 0 R')` chỉ bằng việc so với `"null"` — cú pháp này tôi đã tự xác nhận hôm nay (W0).
- Đổi `if pix.alpha: pix = fitz.Pixmap(pix, 0)` (`image_compress.py:108-109`) thành
  **`if pix.alpha: → images_skipped_unsupported += 1, log warning, continue`**. Lý do: trong luồng
  này alpha chỉ có thể đến từ `/SMask` (đã guard) hoặc `/Mask` color-key (vừa guard) — nếu vẫn còn
  alpha thì nghĩa là có một nguồn ta **chưa hiểu**, và drop nó vừa mất thông tin vừa để lại key sinh
  ra nó trong dict. Skip là lựa chọn duy nhất an toàn.
- 3 guard mask này **không phụ thuộc** quyết định W10-a: chúng là sửa lỗi của v1.

`[UNVERIFIED]` giữ nguyên: 0 mẫu `/Mask` và 0 mẫu `/SMask` thật trong cả 6 job. Hành vi mặc định khi
không có mẫu là **bỏ qua** ⇒ an toàn.

### W4. Điểm 4 — Viết lại cơ chế phình file song ngữ (thay thế V9.1)

**Đồng ý với X6 — chẩn đoán cũ của tôi sai, kết luận cũ đúng vì lý do khác.** V9.1 viết "~84 MB là
content stream/font **không nén**" là sai. Kiểm kê của Expert:

| Loại stream trong `bilingual_vi_en.pdf` (`4c9834bf`, 596 trang, 86.97 MiB) | Filter | Số stream | Bytes |
|---|---|---|---|
| font (`/Length1`) | **`/FlateDecode` — đã nén sẵn** | **592** | **71.08 MiB** |
| content/khác | `/FlateDecode` | 2,598 | 7.96 MiB |
| image | `/FlateDecode` | 26 | 2.65 MiB |

**Cơ chế đúng**: `create_bilingual_pdf()` gọi `insert_pdf` **từng trang một**
(`src/postprocess/bilingual_merge.py:18-21`, vì phải xen kẽ VI/EN). Mỗi lời gọi chép lại bộ font của
bản VI → 592 font stream nhưng chỉ **9 nội dung duy nhất** (0.31 MiB); bản đơn ngữ cùng job có đúng
9. Không có gì "chưa nén" cả — có **9 font bị nhân bản ~65 lần**.

**Hệ quả bắt buộc phải ghi rõ trước khi giao Dev**:

| Cách save | Kết quả đo |
|---|---|
| `save(output_path, deflate=True)` — chỉ deflate | **86.97 MiB — 0 byte lợi ích** |
| `save(output_path, garbage=4, deflate=True)` | **7.40 MiB** (font stream còn 9) |

⇒ **`garbage=4` (garbage-collect object trùng) là tham số làm việc; `deflate=True` một mình vô
nghĩa ở đây.** Nếu Architecture ghi lý do là "không nén", một Dev/Reviewer "tối giản hoá" thành
`deflate=True` sẽ mất **toàn bộ** lợi ích mà một test kiểu "file không to hơn" vẫn pass. Vì vậy nếu
user chọn (B), **test bắt buộc phải assert số font stream (`/Length1`) sau khi save ≤ 10**, không
chỉ assert kích thước — assertion ở tầng kích thước không phân biệt được 2 tham số này.

Rủi ro của (B): Expert đo độc lập — text 596/596 trang giống hệt, **pixel-diff 6 trang ngẫu nhiên =
0.0/255 tuyệt đối** (dedupe stream byte-identical không thể đổi glyph), `f18f796c` 413.76 → 42.31
MiB. Cùng pattern đã verify ở S8.

Một phương án (C) — bỏ `insert_pdf` từng trang, chèn nguyên 2 tài liệu rồi `move_page()` để xen kẽ —
sẽ chặn nhân bản **từ gốc** thay vì dọn sau. Tôi **không đề xuất**: nhiều code hơn, đụng đúng vòng
lặp đang chạy đúng, và không có số đo nào cho thấy nó hơn (B) về kết quả cuối. Ghi lại để khỏi phải
nghĩ lại. Quyết định (A)/(B) vẫn thuộc user (W10-b) vì chạm code path dùng chung cho **cả 2 engine**.

### W5. Điểm 5 — Sửa câu lý giải ngưỡng 4 KB (con số 4096 giữ nguyên)

**Đồng ý với X5.** Câu cũ ở V5 bước 4b — *"khoảng 100 B–4 KB rỗng hoàn toàn nên ngưỡng này không cắt
nhầm ảnh thật nào"* — là tính chất của **đúng 1 file**, và **sai trên kho**: `136645f9` có **186 ảnh
Flate** nằm trong khoảng đó (icon Indexed 46×56 … 209×188).

**Câu thay thế (Dev/Reviewer đọc cái này, không đọc câu cũ)**: ngưỡng 4096 giữ nguyên vì
**tổng dung lượng toàn bộ ảnh Flate < 4 KB trên cả 6 job chỉ ~0.08 MiB (431 ảnh)** — hạ ngưỡng
không đáng công. Đo cụ thể: chạy `136645f9` với `min_recompress_bytes=0` → 347 ảnh bị guard nở file
chặn, 44 skip colorspace, **chỉ 2 ảnh qua được và tiết kiệm tổng cộng 194 byte**, đổi lấy 393 lần
dựng Pixmap. Đây là guard **chi phí + nhiễu log**, không phải guard đúng-sai (guard đúng-sai là guard
nở file ở bước 8). Nó cũng là thứ tránh cho ta 29 exception của C2 trên file sự cố.

### W6. Thuật toán V5-final (hợp nhất — Dev implement theo mục này, không ghép tay)

Thứ tự vẫn là **rẻ → đắt**: mọi phép loại trừ đọc key/metadata chạy **trước** khi dựng `Pixmap`.
Sau W1, **toàn bộ** guard trừ guard nở file đều nằm trước Pixmap.

1. Mở `pdf_path`, ghi `size_before`. *(như v1)*
2. Gom metadata theo xref qua `get_page_images(pno, full=True)`, first sighting wins:
   `meta_by_xref[info[0]] = (smask=info[1], bpc=info[4], cs_family=info[5])`. **[ĐỔI — W1]**
   `images_scanned = len(meta_by_xref)`.
3. **Eligibility filter** *(như V5 bước 3, không đổi)*: `xref_get_key(xref, "Filter")` →
   `type == "null"` **hoặc** `('name', '/FlateDecode')` → eligible; `type == "array"` chứa
   `"FlateDecode"` và không chứa `DCTDecode`/`JPXDecode`/`JBIG2Decode`/`CCITTFaxDecode` → eligible
   (⚠️ `[UNVERIFIED]`, 0 mẫu thật; Expert xác nhận value trả về **không có khoảng trắng giữa các
   name** → phải dùng **substring check**, `value.split()` sẽ sai). Còn lại →
   `images_skipped_already_compressed += 1`, `continue`.
   *Ghi chú cố ý (X8)*: `/LZWDecode`, `/RunLengthDecode` cũng lossless như Flate nhưng **cố ý không
   đưa vào eligibility** (0 mẫu trong kho, `[UNVERIFIED]`) — ghi comment trong code để lần sau khỏi
   tưởng là bỏ sót; thêm vào là việc 1 dòng nếu gặp mẫu thật.
4. **Guard mask/alpha** **[ĐỔI — W3]**: `/ImageMask == true` → skip `unsupported`;
   `meta.smask != 0` → skip `unsupported`; **`xref_get_key(xref,"Mask")[0] != "null"` → skip
   `unsupported`**. Cả 3 log `warning`.
5. **Guard kích thước** *(giữ nguyên hành vi, sửa lý do — W5)*:
   `len(doc.xref_stream_raw(xref)) < min_recompress_bytes` (mặc định 4096) →
   `images_skipped_small += 1`, log `debug`.
6. **Guard bit depth** **[ĐỔI nguồn — W1]**: `meta.bpc != 8` → skip `unsupported`.
7. **Guard colorspace** **[ĐỔI — W1]**: `meta.cs_family not in _ELIGIBLE_CS_FAMILIES` →
   `images_skipped_colorspace += 1`, log `debug`, `continue`. **Trước Pixmap.**
8. Dựng `pix = fitz.Pixmap(doc, xref)`. **`if pix.alpha:` → skip `unsupported`** (không drop — W3).
   **Lớp hai**: `pix.n` không khớp bảng W1 → `images_skipped_colorspace += 1`, log `debug`, `continue`.
9. `jb = pix.tobytes("jpeg", jpg_quality=jpeg_quality)`. Log `debug` kèm **tỉ lệ nén Flate gốc**
   `raw_size / (pix.width * pix.height * pix.n)` (đề nghị X7.3 — để QA soi outlier đồ hoạ phẳng ở
   job thật mà không phải thêm ngưỡng nào).
10. **Guard nở file** *(như v1 — guard đúng-sai duy nhất)*: `len(jb) >= raw_size` →
    `images_skipped_larger += 1`, `continue`.
11. Ghi kết quả **[ĐỔI — W2]**: `update_stream(xref, jb, new=1, compress=0)`;
    `Filter → /DCTDecode`; `BitsPerComponent → 8`; `Width`/`Height` theo `pix`.
    **KHÔNG ghi `/ColorSpace`** — giữ nguyên key gốc (ICC profile). Không cần đụng `/DecodeParms`
    (C3: `update_stream` đã xoá).
12. **Dọn `/Decode`** *(như V5 bước 8)*: **chỉ khi** `xref_get_key(xref,"Decode")[0] != "null"` →
    `xref_set_key(xref, "Decode", "null")`. Set vô điều kiện làm fixture cũ lệch 12 byte vô ích.
13. `doc.save(tmp, garbage=4, deflate=True)` → `close()` → `os.replace(tmp, pdf_path)`. *(như v1)*

### W7. Chữ ký hàm và stats

```python
async def compress_pdf_images(
    pdf_path: str | Path, *, jpeg_quality: int = 85, min_recompress_bytes: int = 4096
) -> ImageCompressStats
```

Không đổi so với V5. `ImageCompressStats` thêm đúng **2 field**: `images_skipped_small`,
`images_skipped_colorspace` (giữ toàn bộ field cũ). Dataclass này chỉ dùng cho log/test — **không**
ghi DB, **không** lên UI. `min_recompress_bytes` là tham số để test tham số hoá được, **không** phải
điểm cấu hình `.env`/UI (BR-IMGCOMP-03 giữ nguyên).

### W8. Test bắt buộc — cập nhật so với V10.2

Giữ nguyên **V10.2 #1–#8**. Bổ sung/nâng cấp:

| # | Test | Mức |
|---|---|---|
| 9 | **Indexed thật bị skip**: fixture mới từ `136645f9` **trang 168** (1.15 MiB, 5 ảnh Indexed + Separation). Gọi với `min_recompress_bytes=0` → `images_skipped_colorspace` tăng đúng số ảnh Indexed+Separation, `images_recompressed == 0`, và `xref_get_key(xref,"ColorSpace")` của các ảnh đó **không đổi**. | **BẮT BUỘC — blocking** |
| 10 | **ICC được giữ**: sau khi chạy trên fixture `78674af9` p22+p25, ảnh đã re-encode phải có `info[5] == 'ICCBased'` và `xref_get_key(xref,"ColorSpace")` **giống hệt trước khi chạy**; `xref_get_key(xref,"Filter") == ('name','/DCTDecode')`. | **BẮT BUỘC** |
| 11 | **`/Mask` inject**: inject `/Mask [200 255]` vào 1 xref Flate → sau khi chạy, `Filter` vẫn `/FlateDecode` (không đụng), stream byte-identical, `images_skipped_unsupported` tăng 1. | **BẮT BUỘC** |
| 12 | **`/Decode` mức pixel** (nâng cấp V10.2 #4 theo X7.1): ngoài assert `xref_get_key == ('null','null')`, render trang sau khi sửa và so với file gốc-đã-inject, sai khác trong ngưỡng nhiễu JPEG (Expert đo: 0.46/255 khi đúng vs **42.28/255** khi sai) — vì lỗi này chưa từng phát tác, assertion ở tầng key không chứng minh viewer hiển thị đúng. | **BẮT BUỘC** |
| 13 | Fixture bổ sung `4c9834bf` **trang 99** (0.48 MiB, 1 ảnh Flate `DeviceGray` **name-form**, job khác, producer khác, ICC khác) — phủ nhánh `cs_family == 'DeviceGray'` mà fixture chính không có. | Nên có |

**Chỗ tôi làm khác Expert**: Expert xếp fixture Indexed (trang 168) là *non-blocking, tuỳ PM cân
dung lượng*. Tôi **nâng lên blocking**, vì sau W2.2 nó không còn là "test cho một guard phụ" — nó là
**bằng chứng duy nhất bằng dữ liệu thật** rằng điều kiện tiên quyết của việc bỏ ghi `/ColorSpace` có
hiệu lực. Nếu PM không chấp nhận thêm 1.15 MiB vào repo, thì phương án lùi **không phải** bỏ test mà
là **giữ nguyên dòng ghi `/ColorSpace`** (tức bỏ luôn điểm 2) — hai thứ đi cùng nhau, không tách.

Ràng buộc Protocol 5/6 giữ nguyên: fixture **phải trích từ file production thật** (không dựng tay),
ghi xuất xứ vào `tests/fixtures/babeldoc/README.md` (job id, số trang gốc, ngày trích, lệnh trích).

### W9. Trạng thái verify sau phản biện

| Hạng mục | Trạng thái |
|---|---|
| Toàn bộ số liệu V1–V8 của Tech Lead | ✅ Verified **2 lần độc lập** (Tech Lead + Domain Expert, script riêng, dữ liệu thật) |
| `info[4]`=bpc int, `info[5]`=họ colorspace trần, `xref_get_key("Mask")` khi vắng | ✅ Verified — Tech Lead tự chạy hôm nay trên file 46.87 MB (W0) |
| Indexed lọt guard cũ (`Pixmap` expand sang base) | ✅ Verified — Expert, 277 ảnh thật ở `136645f9` |
| Ghi đè `/ColorSpace` gây lệch màu trên viewer khác MuPDF | ✅ Verified — Quartz 4.38–6.98/255, control tách riêng khỏi JPEG |
| `/Mask` không có guard, `Pixmap` trả alpha=1 | ✅ Verified cơ chế bằng inject — ⚠️ `[UNVERIFIED]` trên production (0 mẫu/6 job) |
| `garbage=4` mới là tham số quyết định của V9.1, `deflate=True` = 0 byte | ✅ Verified — Expert đo tách 2 tham số |
| Ngưỡng 4096: lý do đúng = 0.08 MiB toàn kho | ✅ Verified — bucket 6 job |
| PDF hỏng nếu bỏ ghi `/ColorSpace` mà thiếu allowlist (W2.2) | ⚠️ **Suy ra** từ X2 đã verify — chặn bằng thiết kế + test W8-#9, không dựng file hỏng để chạy |
| `Filter` dạng array; bpc ≠ 8; colorspace lạ cỡ lớn; `/SMask` | ⚠️ `[UNVERIFIED]` (kế thừa) — mặc định "bỏ qua" ⇒ an toàn |
| pdfium (Chrome) / Acrobat render output CMYK | ⚠️ `[UNVERIFIED]` — QA mở bằng **Chrome + Preview** ít nhất 1 lần ở gate V10.2 #8 |
| **Mở rộng BR-IMGCOMP-02 sang Flate** | ⏸ **Chờ user duyệt — Protocol 2 (W10-a)** |
| **`bilingual_merge.py` (A)/(B)** | ⏸ **Chờ user quyết — Protocol 2 (W10-b)** |
| Thiết kế đã đủ chín để trình user | ✅ Theo đánh giá X9 của Domain Expert, sau 5 sửa ở W1–W5 |

### W10. Hai điều user cần quyết (Protocol 2) — và những gì KHÔNG phụ thuộc vào chúng

**(a) Có duyệt mở rộng BR-IMGCOMP-02 sang ảnh `/FlateDecode` không?**
Được gì: file sự cố 46.87 → 25.19 MB (−46.3%), text/số trang giữ nguyên 100%. Mất gì: ảnh Flate ≥ 4 KB
trở thành JPEG q85 (lossy, **không đảo ngược được** trên file output). Lợi ích **phụ thuộc tài liệu
nguồn**, không đều: `4c9834bf` 6.19 → 5.16 MB, `f18f796c` 35.97 → 35.73 MB (gần như không đổi).
Job 520 MB (`136645f9`) **v2 không cứu được** — 437 MB ở đó đã là JPEG sẵn (V9.2, bài toán khác).

**(b) `bilingual_merge.py`: (A) để backlog hay (B) sửa kèm lần này?**
(B) = đổi `bilingual_merge.py:22` thành `save(output_path, garbage=4, deflate=True)`. Đo: 86.97 →
7.40 MB (−91.5%), 1.0 s; `f18f796c` 413.76 → 42.31 MB. Expert xác nhận **an toàn**: text 596/596
trang giống hệt, **pixel-diff 0.0/255 tuyệt đối**. Vẫn cần user duyệt vì chạm code path dùng chung
cho **cả `pdf2zh` lẫn `babeldoc`** (đúng tiền lệ S8, nơi user đã cố ý từ chối mở rộng sang pdf2zh).

**KHÔNG phụ thuộc (a) hay (b) — là sửa lỗi tiềm ẩn của code đang ship, nên làm trong mọi kịch bản**:
xoá `/Decode` (V4.4), không ghi đè `/ColorSpace` + allowlist `info[5]` đi kèm (W2, **cặp không tách
rời** — W2.2), guard `/Mask` và skip-khi-có-alpha (W3). Nếu user từ chối (a), 4 sửa này vẫn áp dụng
cho nhánh `Filter: null` hiện hành, và W6 rút gọn về đúng bước 3 cũ (`type == "null"`).

---

## Bug #9 — `font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc` (2026-09-08)

**Trạng thái**: hướng khắc phục P0 **ĐÃ QUA Protocol 2** — user duyệt trực tiếp qua PM
(2026-09-08) đúng đề xuất của Domain Expert (chạy model Fable): *tắt hẳn `font_shrink_page()` cho
output của engine `babeldoc`, giữ nguyên cho `pdf2zh`*. Mục này KHÔNG điều tra lại root cause (đã
xong), chỉ chốt **thiết kế cụ thể** để giao Dev.

### B9.1. Nguồn xác thực (Protocol 5 R5-01 / Protocol 1 mở rộng)

Bảng dưới phân biệt rạch ròi 3 mức: (i) Tech Lead **tự đọc source trong repo này** lúc viết mục
này; (ii) **Domain Expert đo/đọc thật** và báo cáo lại cho PM (Tech Lead **chưa** tự chạy lại);
(iii) đã nằm sẵn trong tài liệu handoff đã qua review.

| # | Claim | Mức | Nguồn |
|---|---|---|---|
| B9-01 | Chỉ có **đúng 1** call site của `font_shrink_page()` trong toàn bộ `src/` — `job_orchestrator.py:1292`, bên trong `_process_chunk()`, chạy cho **mọi** trang của **mọi** chunk, **không** phân biệt engine | (i) tự verify | `grep -rn "font_shrink" src/` → chỉ 1 lời gọi; đọc `src/core/job_orchestrator.py:1289-1308` |
| B9-02 | `_process_chunk()` gọi engine qua `self._translator_runner.translate_pages(...)`, engine được chọn ở **1 chỗ duy nhất** là property `_translator_runner` (§6.14.7) | (i) tự verify | `src/core/job_orchestrator.py:264-282` |
| B9-03 | `_redraw_span()` gọi `page.add_redact_annot(span_bbox, fill=(1,1,1))` rồi `page.apply_redactions()` **ngay lập tức, cho từng span một** — nên khi xử lý dòng N+1, vùng redact của nó xoá luôn glyph mà dòng N vừa được `insert_text()` vẽ vào, nếu 2 bbox giao nhau dù chỉ vài phần mười pt | (i) tự verify (cơ chế đọc được thẳng từ code) | `src/postprocess/font_shrink.py:332-333` |
| B9-04 | `font_shrink_page()` được thiết kế **cho pdf2zh**: pdf2zh vẽ bản dịch vào đúng vị trí/cỡ chữ của bản gốc EN, không tự fit lại theo bề ngang box | (i) tự verify | docstring `src/postprocess/font_shrink.py:36-51` ("Real overflow happens when pdf2zh draws the (longer) Vietnamese translation at a page position sized for the (shorter) original English text") |
| B9-05 | babeldoc (`IL/midend/typesetting.py`, bản 0.6.4) **tự bóp cỡ chữ tới tối thiểu 10%** để vừa khung, và **bỏ hẳn đoạn** nếu vẫn không vừa — **không bao giờ** vẽ tràn ra ngoài box | (ii) Domain Expert đọc source thật 2026-09-08 — **Tech Lead CHƯA tự đọc lại** | báo cáo Domain Expert (Fable) gửi PM, 2026-09-08 |
| B9-06 | Trên output babeldoc, `font_shrink_page` bị kích hoạt bởi **sai số đo float vặt vãnh** (median excess đo được = **0.00%**), tức nó redraw mà không hề sửa được gì | (ii) Domain Expert đo thật | như trên |
| B9-07 | **Mất chữ thật**: trang 26 của chính cuốn Le Cordon Bleu, **4 dòng nội dung biến mất** sau bước redraw dòng kế tiếp (đúng cơ chế B9-03; pitch dòng babeldoc = `font_size × 1.3` nhưng bbox glyph Noto Serif cao hơn → 2 bbox dòng kề nhau giao ~0.5pt) | (ii) Domain Expert verify sống | như trên |
| B9-08 | Đo trên chunk 0 thật (40 trang, babeldoc + DeepSeek thật): **126** cặp overlap trước fix Bug #8 → **66** sau fix Bug #8 (mới chỉ sửa toạ độ, CHƯA tắt `font_shrink`) | (iii) đã có trong doc | `docs/test-report.md` mục "Bug #8 — R5-03/R6-03 live E2E trên chunk 0 thật", bảng dòng 2146-2149 |
| B9-09 | Phần lớn 66 cặp còn lại là **nhiễu đo** (dải giao < 2pt giữa 2 dòng kề nhau, sinh ra do chính `font_shrink` tách dòng thành block riêng); overlap **thật** chỉ còn **11**, toàn bộ nằm ở ảnh minh hoạ/bìa, **không** phải văn xuôi | (ii) Domain Expert đo lại 2026-09-08 | báo cáo Domain Expert — đây là **hiệu chỉnh** cách đọc số 66 ở B9-08, không mâu thuẫn với nó |

> **Lưu ý cho Dev (R5-02)**: B9-05/B9-06/B9-07/B9-09 là claim **chưa được Tech Lead tự verify lại**.
> Dev **không cần** spike lại để implement thiết kế này — vì thiết kế chỉ *bỏ đi* một bước xử lý,
> không *thêm* phụ thuộc mới nào vào contract của babeldoc. Nhưng nếu sau này có ai muốn **bật lại**
> `font_shrink` cho babeldoc, hoặc muốn implement khoảng trống ở B9.7 (đọc `paragraph.scale`),
> **bắt buộc** phải tự verify B9-05 từ source babeldoc thật trước.

### B9.2. Root cause (tóm tắt — không điều tra lại)

Ba tầng độc lập cộng lại:

1. **babeldoc không cần bước co-font của app** (B9-05). Nó tự typeset lại toàn bộ và tự đảm bảo
   không vẽ tràn ra ngoài box. Đây là khác biệt bản chất so với pdf2zh (B9-04) — pdf2zh giữ nguyên
   layout gốc nên tràn khung là chuyện *phải* xử lý ở tầng app.
2. **`font_shrink_page()` vẫn chạy cho babeldoc** chỉ vì `_process_chunk()` dùng **chung 1 đường
   ống** cho cả 2 engine (§6.14.7 — nguyên tắc "không rẽ nhánh `if engine ==` rải rác trong thân
   hàm", đặt ra để tránh tái diễn Bug #5). Nguyên tắc đó **đúng và giữ nguyên**; cái sai là ở chỗ
   §6.14.7 chỉ nói về *lời gọi engine*, còn bước post-processing phía sau thì mặc nhiên được coi là
   trung lập với engine — **nó không trung lập**.
3. **Chạy `font_shrink` trên output babeldoc là thao tác thuần rủi ro, lợi ích bằng 0**: nó không
   sửa được gì (B9-06: median excess 0.00% — nó chỉ đang phản ứng với sai số float), nhưng vẫn
   `redact` + `insert_text` lại thật → gây ra Bug #8 (lệch toạ độ MediaBox/CropBox — **đã fix**) VÀ
   **mất chữ thật** (B9-07 + cơ chế B9-03 — **chưa fix, chính là Bug #9**), đồng thời tạo ra phần
   lớn "overlap" giả trong số đo (B9-09).

### B9.3. Thiết kế — thuộc tính năng lực trên runner, KHÔNG rẽ nhánh theo tên engine

**Nguyên tắc**: `_process_chunk()` hỏi **năng lực của runner**, không hỏi **tên engine**. Đây là
mở rộng đúng tinh thần §6.14.7 chứ không phải ngoại lệ của nó: vẫn chỉ có **một** chỗ trong pipeline
biết engine nào đang chạy (property `_translator_runner`), phần thân hàm chỉ đọc một thuộc tính
boolean từ runner đã được chọn.

**Tên thuộc tính đã chốt: `needs_font_shrink`.** Lý do chọn tên này (đã cân nhắc `applies_own_fit`
/ `draws_at_source_layout`):
- Nó trả lời **đúng câu hỏi mà call site đang hỏi**, không bắt người đọc suy luận thêm một bước.
- Khớp precedent naming đã có sẵn trong chính pipeline này: `Pdf2zhService.supports_custom_prompt`
  (dùng ở `src/services/pdf2zh_runner.py:136`) — capability boolean, đặt tên theo *cái mà caller
  cần biết*, không theo *cơ chế nội bộ của tool*.
- Kiểu khai báo: **`ClassVar[bool]`** (class attribute, không phải instance attribute / không phải
  `@property`). Đây là sự thật cố định của engine, không phụ thuộc tham số khởi tạo; khai báo ở cấp
  class để đọc được mà không cần instance và để `ruff`/type-checker soi được.

```python
# src/services/pdf2zh_runner.py — trong `class Pdf2zhRunner`, ngay sau docstring
    #: Bug #9 (Architecture.md "Bug #9"). pdf2zh vẽ bản dịch VÀO ĐÚNG vị trí và
    #: cỡ chữ của bản gốc EN, không tự fit lại theo bề ngang box — nên bước
    #: `font_shrink_page()` của app (BR-FONT-02/US-05) là bắt buộc ở đây.
    needs_font_shrink: ClassVar[bool] = True
```

```python
# src/services/babeldoc_runner.py — trong `class BabeldocRunner`, ngay sau docstring
    #: Bug #9 (Architecture.md "Bug #9"). babeldoc tự typeset lại và tự bóp cỡ
    #: chữ (tới tối thiểu 10%) để vừa box, bỏ hẳn đoạn nếu vẫn không vừa —
    #: KHÔNG BAO GIỜ vẽ tràn ra ngoài box. Chạy thêm `font_shrink_page()` trên
    #: output của nó không sửa được gì (median excess đo được = 0.00%, nó chỉ
    #: phản ứng với sai số float) nhưng vẫn redact + insert_text lại thật —
    #: gây Bug #8 (lệch toạ độ, đã fix) và XOÁ MẤT CHỮ THẬT (Bug #9).
    needs_font_shrink: ClassVar[bool] = False
```

Cả 2 file cần thêm `from typing import ClassVar` (hiện chưa import `typing`).

### B9.4. Vị trí sửa chính xác trong `job_orchestrator.py`

**(a) Thêm property đọc năng lực — đặt NGAY SAU `_translator_runner` (hiện kết thúc ở dòng 282):**

```python
    @property
    def _needs_font_shrink(self) -> bool:
        """Bug #9 — hỏi NĂNG LỰC của engine đã chọn, không hỏi TÊN engine.
        Cùng kỷ luật §6.14.7: chỉ `_translator_runner` biết engine nào đang
        chạy; thân `_process_chunk()` chỉ đọc 1 boolean.

        `isinstance` guard là CÓ CHỦ ĐÍCH, không phải phòng thủ thừa: production
        luôn trả về `bool` thật (ClassVar trên cả 2 runner), nên nhánh raise chỉ
        với tới được từ test dùng `AsyncMock(spec=...Runner)` — mock KHÔNG copy
        GIÁ TRỊ của class attribute, chỉ copy TÊN, nên `mock.needs_font_shrink`
        là 1 child Mock TRUTHY. Không có guard này, một test babeldoc quên set
        thuộc tính sẽ âm thầm chạy nhánh pdf2zh và vẫn PASS — đúng loại
        "mock tự nhất quán với chính nó" mà Protocol 5/6 sinh ra để chặn.
        """
        value = self._translator_runner.needs_font_shrink
        if not isinstance(value, bool):
            raise TypeError(
                f"{type(self._translator_runner).__name__}.needs_font_shrink phải là bool, "
                f"nhận được {value!r}. Nếu đây là test dùng AsyncMock(spec=...), phải set "
                "tường minh `runner.needs_font_shrink = True/False` cho đúng nhánh đang test "
                "(Architecture.md Bug #9 B9.4)."
            )
        return value
```

**(b) Bọc đúng khối `font_shrink` hiện tại (`job_orchestrator.py:1289-1293`):**

```python
        overflow_entries: list[OverflowEntry] = []
        # Bug #9 (Architecture.md "Bug #9", Protocol 2 2026-09-08): CHỈ engine
        # nào tự nó không fit text vào box mới cần bước này. Với babeldoc, mở
        # file ra redact + insert_text lại là thao tác thuần rủi ro: không sửa
        # được gì mà xoá mất chữ thật.
        if self._needs_font_shrink:
            with fitz.open(chunk.output_path) as doc:
                for page in doc:
                    await font_shrink_page(page, overflow_entries, font_path=self._noto_font_path)
                doc.saveIncr()

        for entry in overflow_entries:
            ...  # GIỮ NGUYÊN, không sửa 1 ký tự nào (dòng 1295-1308 hiện tại)
```

**Tổng phạm vi sửa `src/`**: 3 file, không file nào khác.

| File | Vị trí (theo bản hiện tại) | Việc |
|---|---|---|
| `src/services/pdf2zh_runner.py` | dòng 82 (giữa docstring class `Pdf2zhRunner` kết thúc ở 81 và `def __init__` ở 83) | thêm `needs_font_shrink: ClassVar[bool] = True` + import `ClassVar` |
| `src/services/babeldoc_runner.py` | dòng 220 (giữa docstring class `BabeldocRunner` kết thúc ở 219 và `def __init__` ở 221) | thêm `needs_font_shrink: ClassVar[bool] = False` + import `ClassVar` |
| `src/core/job_orchestrator.py` | sau dòng 282 | thêm property `_needs_font_shrink` |
| `src/core/job_orchestrator.py` | dòng 1289-1293 | bọc khối `with fitz.open(...)` trong `if self._needs_font_shrink:` |

**KHÔNG sửa**: `src/postprocess/font_shrink.py` (module giữ nguyên 100% — nó vẫn là đường đúng cho
pdf2zh), `src/models/overflow.py`, schema DB, `src/core/config.py`.

### B9.5. `overflow_entries` khi `needs_font_shrink=False` — giữ list rỗng, KHÔNG bỏ code

**Quyết định: giữ nguyên khai báo `overflow_entries: list[OverflowEntry] = []` ở ngoài `if`, và
giữ nguyên vòng lặp ghi `OverflowReport` phía sau — không đụng vào.** Khi tắt, list rỗng, vòng lặp
chạy 0 lần, 0 row được ghi.

Lý do (đây là phương án **ít xáo trộn nhất**, đúng yêu cầu):
1. **Diff nhỏ nhất có thể**: đúng 1 dòng `if` + thụt lề 4 dòng. Phương án gộp cả khối ghi DB vào
   trong `if` phải di chuyển 14 dòng code — nhiều cơ hội sai hơn, và toàn bộ 14 dòng đó là đường
   **đang chạy đúng** cho pdf2zh.
2. **Không đụng vào đường persistence của pdf2zh**: đây chính là cách hỏng kiểu Bug #5 (sửa nhánh
   này làm gãy nhánh kia mà không ai thấy vì test mỗi nhánh tự nhất quán).
3. **Chừa sẵn chỗ cho khoảng trống B9.7**: nếu sau này lấy được tín hiệu overflow từ chính babeldoc
   (`paragraph.scale`), chỗ nạp vào `overflow_entries` đã có sẵn, không phải dựng lại đường ghi DB.
4. Chi phí runtime của việc giữ lại: cấp phát 1 list rỗng + 1 vòng lặp 0 vòng — bằng 0 trên thực tế.

### B9.6. Yêu cầu test cho Dev (R6-02 — assert giá trị, không chỉ assert "đã gọi")

Bắt buộc, vì bug này thuộc đúng loại "hai mock tự nhất quán với nhau":

1. **T9-1 (nhánh babeldoc — không đụng file)**: chạy `_process_chunk()`/`run_job()` với
   `pdf_translate_engine="babeldoc"` trên 1 PDF thật do PyMuPDF sinh; assert **file
   `chunk.output_path` byte-identical trước/sau bước post-processing** (so `hashlib.sha256` hoặc
   `st_mtime` + size), VÀ `SELECT COUNT(*) FROM overflow_reports WHERE job_id=...` **== 0**.
   Assert nội dung/giá trị, không dùng `assert_called()`.
2. **T9-2 (nhánh pdf2zh — hồi quy, không được đổi hành vi)**: cùng input, `pdf_translate_engine=
   "pdf2zh"`; assert bước font_shrink **vẫn chạy** (file bị sửa / `OverflowReport` vẫn được ghi khi
   có span tràn thật). Đây là test chống việc fix này vô tình tắt cả 2 engine.
3. **T9-3 (guard)**: `AsyncMock(spec=BabeldocRunner)` không set `needs_font_shrink` → `pytest.raises(TypeError)`.
   Test này bảo vệ chính cơ chế bảo vệ.
4. **Sửa 7 chỗ tạo mock runner hiện có** (đây là toàn bộ, đã grep — không có chỗ nào khác):
   `tests/integration/test_job_cancel.py:76`, `tests/integration/test_job_orchestrator_concurrency.py:66`,
   `tests/integration/test_job_orchestrator.py:86`, `:379`, `:441` (`spec=Pdf2zhRunner` → set
   `= True`), `tests/integration/test_job_orchestrator.py:504`, `:1001`
   (`spec=BabeldocRunner` → set `= False`). Mỗi chỗ thêm đúng 1 dòng
   `runner.needs_font_shrink = True/False`.

**Live E2E (R6-03)**: chạy lại đúng chunk 0 (40 trang đầu Le Cordon Bleu, babeldoc + DeepSeek thật)
mà QA đã dùng cho Bug #8, rồi **mở file output ra kiểm tra nội dung** (không tin `status`):
(a) trang 26 phải có **đủ 4 dòng** mà B9-07 báo là biến mất; (b) đếm lại overlap bằng đúng script
`ov3.py` (area giao > 200pt², `block[6]==0`) — kỳ vọng tụt mạnh khỏi mốc 66 về gần 11 (B9-09).
Không đặt ngưỡng cứng "phải bằng 11": 11 cặp còn lại thuộc root cause khác (babeldoc typesetting
không reflow, xem mục "Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order", 2026-09-07)
và **không** nằm trong phạm vi Bug #9.

### B9.7. Khoảng trống đã biết trước — CHẤP NHẬN, để dành cho tương lai

Tắt `font_shrink_page()` cho babeldoc đồng nghĩa **nhánh babeldoc không còn ghi `OverflowReport`
nào nữa** — kể cả khi bản thân babeldoc âm thầm **bỏ hẳn 1 đoạn** vì không vừa box dù đã bóp còn
10% (B9-05). BA/QA sẽ mất cờ cảnh báo "trang này cần soi tay" cho nhánh babeldoc.

Đây là khoảng trống **đã biết trước và được chấp nhận có ý thức**, KHÔNG vá trong task này:

- Cờ đó vốn đã **gần như vô giá trị** trên babeldoc: nó được sinh ra từ phép đo của
  `font_shrink_page` trên một trang mà chính babeldoc đã fit xong, tức đo trên sai số float
  (B9-06) — dữ liệu đúng nhưng vô nghĩa, tệ hơn là kèm theo tác hại xoá chữ.
- Hướng vá đúng trong tương lai (đề xuất của Domain Expert, **chưa thiết kế**): đọc
  `paragraph.scale` từ debug output riêng của babeldoc → nếu `scale` chạm sàn (hoặc đoạn bị drop
  hẳn) thì ghi 1 `OverflowReport`/`layout_qa_finding`. Việc này cần Protocol 5 R5-01 đầy đủ cho
  format debug output của babeldoc (**chưa ai verify**) nên **không** gộp vào P0 này.
- Nơi đặt tự nhiên cho tín hiệu đó khi làm: cùng đường `persist_findings()` mà overlay chữ xoay
  đang dùng (`job_orchestrator.py:593-609`), chứ không nhất thiết là bảng `overflow_reports`.

**Hệ quả cần PM/BA biết**: acceptance criteria US-05/BR-FONT-02 (co font chống tràn khung) từ nay
**chỉ còn hiệu lực trên đường `pdf2zh`**. Trên đường `babeldoc` (đang là **default** từ 2026-09-05),
chống tràn khung là trách nhiệm của chính babeldoc, app không can thiệp và không đo. Cần cập nhật
PRD ở lượt review PRD gần nhất — **không** phải việc của Dev trong task này.

### B9.8. Rollback

**Không thêm feature flag mới** cho bước này (cân nhắc rồi, cố ý bỏ). Lý do: một flag chỉ có ý
nghĩa khi cả 2 trạng thái đều là lựa chọn hợp lệ; ở đây trạng thái "bật" đã được chứng minh là
**phá dữ liệu** (xoá chữ thật, B9-07) chứ không phải "đánh đổi". Thêm flag = thêm một đường cấu
hình dẫn thẳng tới bug đã biết, cộng thêm surface cho `SETTINGS_DB_OVERRIDABLE_FIELDS`.

Đường rollback thực tế nếu cần: (a) `PDF_TRANSLATE_ENGINE=pdf2zh` + restart — flag **đã có sẵn**
từ §6.14.7, đưa toàn bộ pipeline về đường v1.1.1; hoặc (b) revert đúng 1 hằng số
`BabeldocRunner.needs_font_shrink` về `True` (1 dòng, 1 commit).

---

## Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (`_get_width_before_next_break_point` đếm đôi bề rộng ký tự hiện tại) — thiết kế bản vá (Tech Lead, 2026-09-09)

**Trạng thái**: THIẾT KẾ — chưa implement. Đây là **lỗi thật của chính babeldoc 0.6.4 upstream**,
không phải lỗi code của project. Vá bằng shim monkeypatch qua `src/babeldoc_shim/sitecustomize.py`,
đúng khuôn mẫu đã dùng cho Bug #7 (7.1/7.2/7.4-b).

**Nguồn phát hiện**: Domain Expert (Fable) trong lúc điều tra Bug #8/#9. Toàn bộ root cause dưới đây
đã được Tech Lead **tự đọc lại source thật để verify** (Protocol 5 R5-01) — brief của Expert được coi
là giả thuyết cần kiểm chứng, không phải sự thật. Kết quả: root cause khớp; có **4 điểm cần đính
chính/bổ sung** so với brief, ghi ở BA10.4.

---

### BA10.1. Nguồn xác thực (Protocol 5 R5-01)

| Mục | Nguồn |
|---|---|
| Tool | `babeldoc` **0.6.4**, cài qua `uv tool` |
| Đường dẫn source đã đọc | `~/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/typesetting.py` (1682 dòng) |
| Xác nhận version | thư mục `babeldoc-0.6.4.dist-info` cạnh package |
| Cách verify | Đọc trực tiếp file bằng `Read`/`sed` (không qua trí nhớ, không qua WebFetch bản upstream) |
| Ngày verify | 2026-09-09 |

**CẢNH BÁO có thật, Dev phải biết**: trên máy này tồn tại **hai** bản babeldoc khác nhau:
- `~/.local/share/uv/tools/babeldoc/.../babeldoc/format/pdf/document_il/midend/typesetting.py` — bản
  0.6.4 **app đang thực sự dùng** (`BabeldocRunner._executable = "babeldoc"`). ĐÂY là bản cần vá.
- `~/.local/share/uv/tools/pdf2zh/.../babeldoc/document_il/midend/typesetting.py` — bản babeldoc **cũ
  hơn, bundle bên trong tool `pdf2zh`** (đường module KHÁC: không có `format/pdf/`). Bản này chỉ chạy
  khi `PDF_TRANSLATE_ENGINE=pdf2zh`. **KHÔNG thuộc phạm vi Bug #10** — shim gate theo
  `babeldoc.__version__ == "0.6.4"` và theo tên module đầy đủ `babeldoc.format.pdf...`, nên tự động
  không đụng tới bản trong pdf2zh. Không mở rộng phạm vi sang đó trong task này.

---

### BA10.2. Root cause — đã tự verify bằng đọc code thật

#### BA10.2-a. Hàm lookahead ĐÃ CỘNG bề rộng của chính unit hiện tại

`typesetting.py:1285-1298` (trích nguyên văn bản đã cài):

```python
    def _get_width_before_next_break_point(
        self, typesetting_units: list[TypesettingUnit], scale: float
    ) -> float:
        if not typesetting_units:
            return 0
        if typesetting_units[0].can_break_line:
            return 0

        total_width = 0
        for unit in typesetting_units:          # <-- BẮT ĐẦU TỪ units[0] = unit HIỆN TẠI
            if unit.can_break_line:
                return total_width * scale
            total_width += unit.width           # <-- cộng cả w(unit hiện tại)
        return total_width * scale
```

Vòng lặp bắt đầu từ `typesetting_units[0]`. Ngay trước đó đã có guard `if typesetting_units[0].
can_break_line: return 0`, nên khi vào được vòng lặp thì `units[0]` chắc chắn KHÔNG phải break point
⇒ lần lặp đầu tiên luôn chạy `total_width += units[0].width`. Kết luận:

> giá trị trả về = `w(unit_hiện_tại) + w(unit kế) + ... ` cho tới (không kể) break point kế tiếp.

#### BA10.2-b. Chỗ gọi CỘNG THÊM `unit_width` một lần nữa

`typesetting.py:1366` và `:1399-1417` (trong `_layout_typesetting_units`):

```python
            unit_width = unit.width * scale                       # :1366
            ...
            if use_english_line_break:                            # :1399
                width_before_next_break_point = self._get_width_before_next_break_point(
                    typesetting_units[i:], scale                  # :1400-1402  <-- lát cắt BẮT ĐẦU tại i
                )
            else:
                width_before_next_break_point = 0

            # 如果当前行放不下这个元素，换行
            if not unit.is_hung_punctuation and (                 # :1407
                (current_x + unit_width > box.x2)                 # :1408  (A) chốt chặn cứng
                or (
                    use_english_line_break
                    and current_x + unit_width + width_before_next_break_point > box.x2   # :1411 (B) LỖI
                )
                or (
                    unit.is_cannot_appear_in_line_end_punctuation
                    and current_x + unit_width * 2 > box.x2       # :1415  (C) không liên quan
                )
            ):
```

Lát cắt truyền vào là `typesetting_units[i:]` — tức **bao gồm chính unit thứ `i`**. Vì vậy biểu thức
(B) ở `:1411` khai triển ra là:

```
current_x + w(uᵢ) + [ w(uᵢ) + w(uᵢ₊₁) + ... + w(u_{k-1}) ]      với u_k là break point kế tiếp
= current_x + 2·w(uᵢ) + w(phần còn lại của từ)
```

Đúng ra phải là `current_x + w(uᵢ) + w(phần còn lại của từ)` — tức chính xác bằng
`current_x + width_before_next_break_point` (vì hàm đã bao gồm `w(uᵢ)` rồi). **Xác nhận toàn bộ mô tả
root cause của Expert, kể cả số dòng (1285-1298 và 1407-1417) đều đúng nguyên văn.**

#### BA10.2-c. Hệ quả: wrap xảy ra SAI CHỖ, cắt giữa từ

Phần dư `+w(uᵢ)` **phụ thuộc vào bề rộng của chính ký tự đang xét**, nên ngưỡng không nhất quán giữa
các ký tự trong cùng một từ:
- ký tự hẹp (`t`, w≈3.17pt) → phần dư nhỏ → vượt qua được (B) → được đặt ở cuối dòng;
- ký tự rộng ngay sau (`r`, w≈4.24pt) → phần dư lớn hơn → (B) kích hoạt → **xuống dòng giữa từ**.

Kết quả quan sát được: `"trung thành"` → `"t"` cuối dòng + `"rung thành"` đầu dòng sau; các case khác
Expert đo được: `"khâu c|huẩn bị"`, `"liên tục c|ho"`. Quy mô Expert đo: 31 ca / 1.664 dòng trên 40
trang raw babeldoc (phía tiếng Anh gốc: 7/1.801 — nhiễu nền).

#### BA10.2-d. Tại sao upstream không phát hiện: `LINE_BREAK_REGEX` KHÔNG chứa dải CJK

`typesetting.py:31-88` định nghĩa `LINE_BREAK_REGEX`; `calc_can_break_line` (`:213-219`) trả về
`False` khi regex match. Các dải có trong regex gồm `a-zA-Z0-9`, Latin-1 Supplement, Latin Extended
A/B/**Additional (`Ḁ-ỿ`)**, **Combining Diacritical Marks (`̀-ͯ`)**, Cyrillic,
Greek, Thai, Khmer, Myanmar... — **KHÔNG có dải Hán/Kana nào**.

⇒ Với tiếng Trung/Nhật (thị trường chính của babeldoc), MỌI ký tự đều `can_break_line == True` ⇒
guard `:1290-1291` trả `0` ⇒ số hạng lỗi ở (B) **triệt tiêu hoàn toàn**, bug **vô hình**.
⇒ Với tiếng Việt, chữ có dấu nằm đúng trong `Ḁ-ỿ` + `̀-ͯ` ⇒ cả từ là một chuỗi
`can_break_line == False` dài ⇒ bug lộ ra dày đặc.

Đây là cơ chế **cấu trúc**, mạnh hơn cách diễn đạt của Expert ("lộ rõ hơn ở tiếng Việt vì nhiều từ có
dấu/âm tiết dài") — xem đính chính BA10.4-3.

---

### BA10.3. Bản vá — thiết kế chốt

#### BA10.3-a. Điểm vá: vá HÀM lookahead, KHÔNG vá chỗ gọi

Hai cách sửa tương đương về số học:
1. Bỏ `w(uᵢ)` khỏi giá trị trả về của `_get_width_before_next_break_point` (hàm 14 dòng), hoặc
2. Bỏ `unit_width` khỏi biểu thức `:1411` — nhưng phải thay thế **cả hàm
   `_layout_typesetting_units` dài 167 dòng** (`:1300-1466`) vì không có điểm hook nhỏ hơn.

**Chốt cách (1)** — patch tối thiểu, đúng nguyên tắc "ưu tiên patch nhỏ, dễ review":
- Đã grep toàn bộ package babeldoc đã cài: `_get_width_before_next_break_point` có **đúng 1 chỗ gọi**
  (`typesetting.py:1400`) và **1 chỗ định nghĩa** (`:1285`) — không có consumer nào khác, nên đổi ngữ
  nghĩa của nó là an toàn tuyệt đối trong phạm vi package.
- Cách (2) phải copy 167 dòng logic layout (line-skip, mixed CJK/Latin spacing, box expansion...) vào
  shim — rủi ro sai sót và chi phí re-verify khi upgrade cao hơn hẳn, **loại**.

#### BA10.3-b. Hàm thay thế

Đặt thuật toán thuần (không phụ thuộc babeldoc) tại **module mới `src/babeldoc_shim/word_wrap.py`**
để test gọi đúng logic production (Protocol 6 R6-02 — không được chép tay thuật toán sang test):

```python
# src/babeldoc_shim/word_wrap.py  (module MỚI, thuật toán thuần)
def width_before_next_break_point(
    units: Sequence[tuple[float, bool]],   # [(width, can_break_line), ...] bắt đầu TẠI unit hiện tại
    scale: float,
) -> float:
    """Bề rộng phần CÒN LẠI của từ, KHÔNG kể unit hiện tại (Bug #10)."""
    if not units:
        return 0.0
    if units[0][1]:              # unit hiện tại tự nó là break point -> giữ nguyên hành vi gốc
        return 0.0
    total = 0.0
    for width, can_break in units[1:]:     # <-- KHÁC BẢN GỐC: bỏ qua units[0]
        if can_break:
            break
        total += width
    return total * scale
```

Wrapper trong `sitecustomize.py` chỉ làm nhiệm vụ bóc field từ object babeldoc thật rồi ủy thác:

```python
def _build_patched_get_width_before_next_break_point(typesetting_module):
    from word_wrap import width_before_next_break_point       # import tên trần: PYTHONPATH trỏ
                                                              # THẲNG vào src/babeldoc_shim/
    def patched(self, typesetting_units, scale):
        return width_before_next_break_point(
            [(u.width, u.can_break_line) for u in typesetting_units], scale
        )
    return patched
```

**Lưu ý hiệu năng (bắt buộc cân nhắc khi implement)**: hàm gốc **thoát sớm** tại break point đầu
tiên, còn list-comprehension ở trên **duyệt toàn bộ lát cắt `typesetting_units[i:]`** (O(n) cho mọi
`i` ⇒ O(n²) trên paragraph dài). Hàm này nằm trong vòng lặp layout chạy lại cho **mọi giá trị scale**
thử nghiệm ⇒ nguy cơ chậm thật, không phải lo xa. **Yêu cầu Dev**: hoặc (a) truyền generator/iterator
lười thay vì list đã materialize, hoặc (b) để wrapper tự duyệt và thoát sớm rồi chỉ ủy thác phép cộng
— miễn là thuật toán vẫn nằm ở `word_wrap.py` và test gọi đúng nó. Dev đo thời gian dịch 1 trang
trước/sau patch trong spike (BA10.5-G4) để chứng minh không hồi quy hiệu năng.

#### BA10.3-c. Vì sao bản vá KHÔNG thể gây tràn dòng (tự verify bằng đọc code)

Ba tính chất, đọc thẳng từ source:

1. **Chốt chặn cứng bên phải KHÔNG bị đụng tới.** Nhánh (A) `:1408` `current_x + unit_width > box.x2`
   là một mệnh đề `or` **độc lập**, không dùng `width_before_next_break_point`, và patch không sửa
   `_layout_typesetting_units`. Vì vậy sau vá, mọi unit được đặt vẫn thoả `current_x + unit_width <=
   box.x2` y hệt trước vá ⇒ **không unit nào có thể bị đặt vượt quá `box.x2`**. Đây là tính chất
   quan trọng nhất, và nó là tính chất **cấu trúc** (nhánh (A) còn nguyên), không phải suy luận số học.
2. **Số dòng không thể TĂNG.** Patch làm vế trái của (B) **nhỏ đi đúng `unit_width >= 0`** ⇒ (B) là
   một vị từ **yếu hơn theo từng điểm**: "sau vá wrap" ⟹ "trước vá cũng wrap". Với thuật toán greedy
   đơn điệu theo `current_x` này, vị từ yếu hơn không bao giờ sinh thêm dòng. Đã kiểm chứng thêm bằng
   mô phỏng thuần: 20.000 trường hợp ngẫu nhiên (độ dài từ/bề rộng ký tự ngẫu nhiên) — **0 trường hợp
   nào bản vá cho ra nhiều dòng hơn bản gốc**.
3. **`all_units_fit` chỉ tuỳ thuộc số dòng.** `:1440-1444` đặt `all_units_fit = False` khi và chỉ khi
   `current_y < box.y` sau một lần xuống dòng ⇒ ít dòng hơn (hoặc bằng) ⇒ `all_units_fit` chỉ có thể
   giữ nguyên hoặc chuyển `False → True`, không bao giờ ngược lại.

Từ (2)+(3): trong `_find_optimal_scale_and_layout` (`:973-1002`) vòng `while scale >= min_scale` sẽ
**dừng sớm hơn hoặc bằng** ⇒ scale được chọn **lớn hơn hoặc bằng** trước vá. Xem hệ quả ở BA10.4-4.

---

### BA10.4. Khác biệt so với báo cáo của Expert (bắt buộc ghi theo Protocol 5 R5-01)

| # | Expert nói | Tech Lead verify | Kết luận |
|---|---|---|---|
| 1 | Số dòng `~1285-1298` (hàm) và `~1407-1417` (điều kiện wrap), công thức sai `cx + 2·w(uᵢ) + w(phần còn lại)` | Đúng **nguyên văn**, cả số dòng lẫn công thức | ✅ XÁC NHẬN |
| 2 | "dòng có thể chứa thêm **tối đa 1 ký tự** khi từ vừa khít" | **KHÔNG chính xác** — xem dưới | ⚠️ ĐÍNH CHÍNH |
| 3 | Bug "lộ rõ hơn ở tiếng Việt vì nhiều từ có dấu/âm tiết dài" | Cơ chế thật mạnh hơn: `LINE_BREAK_REGEX` (`:31-88`) không chứa dải CJK ⇒ với zh/ja số hạng lỗi **triệt tiêu bằng 0**, bug **vô hình hoàn toàn**, không phải "ít lộ hơn" | ⚠️ BỔ SUNG |
| 4 | (không đề cập) | Bản vá có **tác dụng phụ nhìn thấy được**: một số paragraph sẽ render **font TO HƠN** trước | ⚠️ BỔ SUNG QUAN TRỌNG |

**Đính chính #2 chi tiết** — vì `can_break_line` là `False` cho toàn bộ chữ cái nhưng `True` cho dấu
cách, "phần còn lại tới break point kế tiếp" chính là **phần đuôi còn lại của TỪ hiện tại**, không
phải một ký tự. Trong ca `"trung thành"`: tại `t`, biểu thức đúng là `cx + w("t") + w("rung") =
cx + w("trung") = 587.06 <= 590.91` ⇒ đặt `t`; tại `r`, `cx' + w("r") + w("ung") = cx + w("trung")`
= vẫn 587.06 ⇒ đặt tiếp; và cứ thế **cả từ `"trung"` ở lại trên dòng**. Chỗ xuống dòng thật sẽ rơi
vào **dấu cách** ngay sau đó (`can_break_line == True` ⇒ lookahead = 0 ⇒ chỉ còn nhánh (A)).

⇒ Phát biểu đúng: **một dòng có thể nhận thêm phần đuôi còn lại của MỘT từ (có thể vài ký tự), không
phải đúng 1 ký tự.** Điều này KHÔNG làm yếu tính chất an toàn, vì tính chất an toàn đến từ nhánh (A)
còn nguyên (BA10.3-c điểm 1), không đến từ "chỉ thêm 1 ký tự".

**Bổ sung #4 chi tiết** — theo BA10.3-c điểm (2)+(3), `all_units_fit` có thể chuyển `False → True` ở
một `scale` **lớn hơn**, nên `_get_optimal_scale` sẽ trả về scale lớn hơn cho một số paragraph.
**Hệ quả nhìn thấy được: chữ ở các paragraph đó TO HƠN sau khi vá.** Đây là **cải thiện**, không phải
hồi quy (mọi scale được chấp nhận đều đã qua `all_units_fit`, vẫn nằm trong box). QA **phải biết
trước** điều này để không mở bug mới khi thấy diff cỡ chữ giữa 2 lần chạy A/B.

---

### BA10.5. Yêu cầu spike TRƯỚC KHI implement đầy đủ (Protocol 5 R5-02) — BẮT BUỘC

Đây là lần đầu project vá vào `typesetting.py` (3 patch Bug #7 đều nằm ở `paragraph_finder.py`), tức
hành vi **chưa từng được project verify sống**. Dev **KHÔNG** được viết implementation + test đầy đủ
trước khi spike xanh.

**Phương pháp A/B bắt buộc — tận dụng translation cache của babeldoc**: babeldoc cache kết quả dịch
(`--ignore-cache` để tắt). Chạy lần 1 **KHÔNG patch** (nạp cache), rồi lần 2 **CÓ patch** trên đúng
input đó **KHÔNG** truyền `--ignore-cache` ⇒ văn bản tiếng Việt **giống hệt nhau** giữa 2 lần, mọi
khác biệt còn lại **thuần tuý là layout**. Không làm thế này thì LLM trả về text khác nhau và mọi
phép so sánh trước/sau đều vô nghĩa.

| Gate | Nội dung | Tiêu chí PASS |
|---|---|---|
| **G1** (đích) | Chạy trên fixture 1 trang (BA10.6), so sánh raw babeldoc trước/sau patch | Trước: có ít nhất 1 ca cắt giữa từ (kỳ vọng `"trung thành"` bị tách). Sau: ca đó **không còn bị tách** |
| **G2** (tràn ngang) | Trích bbox mọi text block bằng `pymupdf` trên toàn bộ trang test + trang đối chứng | `max(block.x1)` sau vá **KHÔNG lớn hơn** trước vá quá 0.5pt trên bất kỳ trang nào |
| **G3** (số dòng) | Đếm số dòng text mỗi trang, trước vs sau | Sau vá `<=` trước vá trên **MỌI** trang. Nếu có trang nào TĂNG ⇒ giả thuyết đơn điệu ở BA10.3-c sai ⇒ **escalate Tech Lead ngay**, không tự sửa |
| **G4** (hiệu năng) | Đo wall-clock 1 trang, trước vs sau (cache đã nóng cho cả 2) | Không chậm hơn quá 20%. Nếu chậm hơn ⇒ áp dụng tối ưu thoát-sớm ở BA10.3-b |
| **G5** (không mất chữ) | So tổng độ dài text trích được | Sau vá `>=` trước vá (không được mất ký tự nào) |

**Trang đối chứng cho G2/G3/G5** (trang KHÔNG có bug này từ trước, để bắt hồi quy ngược) — tái dùng
fixture đã có, **không tạo mới**: `tests/fixtures/babeldoc/page14_numbered_list_source.pdf`,
`tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf`, `tests/fixtures/babeldoc/toc_sources/figoni_p25_recipe.pdf`.

---

### BA10.6. Golden fixture (Protocol 5 mục 3)

**Fixture nguồn — TẠO MỚI (bắt buộc, không tái dùng được cái nào đang có)**:

```
tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf
```

Trích **đúng 1 trang, page index 39 (0-based)** từ
`data/uploads/7ff56932-0c9e-403e-9555-4b4059c60b59_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf`
(418 trang, 277MB — **KHÔNG commit file gốc**):

```python
import pymupdf
src = pymupdf.open("data/uploads/7ff56932-...-Foundations (1).pdf")
out = pymupdf.open(); out.insert_pdf(src, from_page=39, to_page=39)
out.save("tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf")
```

**Tech Lead đã tự xác nhận trang này đúng là trang có case của Expert**: text trang 39 (0-based) chứa
`"...recognizes motivated and loyal employees by sending them to do a "stage"..."` — `"loyal
employees"` chính là nguồn của `"nhân viên trung thành"` mà Expert quan sát thấy bị cắt thành
`"t|rung thành"`. Trang này cũng là "Chapter 2 / trang in số 24" — dùng để đối chiếu bằng mắt.

**Fixture unit-level — TẠO MỚI trong lúc spike**:

```
tests/fixtures/babeldoc/bug10_wrap/lcb_p39_trung_thanh_units.json
```

Trong spike, dump từ **lần chạy babeldoc THẬT** chuỗi `[(unit.width, unit.can_break_line), ...]` của
paragraph chứa `"trung thành"`, kèm `current_x` tại điểm bắt đầu từ đó, `box.x2` và `scale`. Test đơn
vị cho `word_wrap.width_before_next_break_point` **phải nạp từ file này**, KHÔNG được gõ tay số liệu
tự nghĩ ra (Protocol 5 mục 3: mock viết tay theo giả định = test tự xác nhận giả định).

Assertion bắt buộc của test đó (R6-02 — assert **giá trị cụ thể**, không phải "đã gọi"):
- với dữ liệu golden, biểu thức `current_x + unit_width + width_before_next_break_point(...)` tại ký
  tự `'r'` phải `<= box.x2` (sau vá), trong khi công thức gốc (đếm đôi) cho `> box.x2` — tức test
  **chứng minh được chính xác điểm khác biệt hành vi**, không chỉ "hàm chạy không lỗi".

---

### BA10.7. Vị trí sửa trong `src/babeldoc_shim/sitecustomize.py` — cơ chế gate GIỮ NGUYÊN

**KHÔNG tạo cơ chế gate mới.** Tái dùng nguyên `_EXPECTED_BABELDOC_VERSION = "0.6.4"` +
`_install_hook_if_version_matches()` đang có. Danh sách thay đổi tối thiểu (số dòng theo bản hiện tại,
603 dòng):

| Vị trí hiện tại | Thay đổi |
|---|---|
| `:137` `_TARGET_MODULE_NAME` | Đổi tên thành `_PARAGRAPH_FINDER_MODULE_NAME`; **thêm** `_TYPESETTING_MODULE_NAME = "babeldoc.format.pdf.document_il.midend.typesetting"` |
| `:144-147` (cạnh `_toc_split_enabled`) | Thêm `_word_wrap_fix_enabled()` đọc `BABELDOC_SHIM_WORD_WRAP_FIX`, **mặc định `"1"` (BẬT)** |
| mới, cạnh `:427` | Thêm `_build_patched_get_width_before_next_break_point(typesetting_module)` (code ở BA10.3-b) |
| `:462` `_apply_patch` | Đổi tên → `_apply_paragraph_finder_patch`; **thêm** `_apply_typesetting_patch(module)` riêng: check `hasattr(Typesetting, "_get_width_before_next_break_point")` rồi mới gán, log `logger.warning` riêng |
| `:508` `_PatchingLoader` | Tham số hoá: `__init__(self, wrapped_loader, apply_patch, label)`; `exec_module` gọi `self._apply_patch(module)` trong try/except như cũ, log kèm `label` |
| `:533` `_ParagraphFinderPatchFinder` | Đổi tên → `_ModulePatchFinder(target_fullname, apply_patch, label)` (logic `find_spec` giữ **nguyên xi**, kể cả cờ `_resolving` và thủ thuật gỡ/chèn lại `sys.meta_path`) |
| `:597` | Cài **hai** finder: một cho `paragraph_finder`, một cho `typesetting`. Nhánh fallback `if ... in sys.modules` (`:583-595`) áp dụng riêng cho từng module |

**Ràng buộc thiết kế bắt buộc**:

1. **Rollback ĐỘC LẬP.** Patch typesetting phải nằm trong `try/except` **riêng** với 3 patch
   `paragraph_finder`. Nếu babeldoc đổi cấu trúc `typesetting.py`, 3 patch Bug #7 vẫn phải chạy bình
   thường, và ngược lại. (Khác với 3 patch Bug #7 — chúng cố ý rollback CHUNG vì cùng một class.)
   Vì là 2 module / 2 loader riêng nên tính chất này có sẵn — **không được gộp lại cho "gọn"**.
2. **KHÔNG có phụ thuộc thứ tự** giữa Bug #10 và 7.1/7.2/7.4-b. `paragraph_finder` chạy ở giai đoạn
   tách đoạn/dòng, `typesetting` chạy sau ở giai đoạn dàn trang; bản vá Bug #10 không quan tâm đoạn
   được tách thế nào. (Khác 7.1→7.2 vốn **bắt buộc** đúng thứ tự.)
3. **Tên module `word_wrap.py` phải không đụng hàng.** `PYTHONPATH` trỏ thẳng vào
   `src/babeldoc_shim/` nên mọi file `.py` ở đó thành **module top-level** trong subprocess babeldoc,
   có thể che khuất module cùng tên của stdlib/thư viện. Dev phải xác nhận `word_wrap` không tồn tại
   trong venv babeldoc. **Tech Lead đã tự kiểm tra 2026-09-09**: `ls ~/.local/share/uv/tools/babeldoc/
   lib/python3.12/site-packages/ | grep -i word_wrap` → **0 kết quả**, và `python3 -c "import
   word_wrap"` → `ModuleNotFoundError` ⇒ tên `word_wrap` **an toàn, không đụng hàng**. Rủi ro này có
   sẵn từ Bug #7 (`line_split`, `toc_split`) — nếu Dev đổi sang tên khác thì phải tự kiểm tra lại.

---

### BA10.8. Feature flag & wiring

Theo đúng mẫu 3 flag đang có (`babeldoc_line_split_shim_enabled` / `..._numbered_list_split_enabled` /
`..._toc_split_enabled`):

| Tầng | Thêm |
|---|---|
| `src/core/config.py` (cạnh `:240`) | `babeldoc_word_wrap_fix_enabled: bool = True` + comment nêu rõ đây là **fix số học đúng/sai**, không phải heuristic |
| `src/services/babeldoc_runner.py` `__init__` | tham số `word_wrap_fix_enabled: bool = False` (giữ default `False` cho khởi tạo trực tiếp trong test, **giống hệt** `toc_split_enabled`) → `self._word_wrap_fix_enabled` |
| `src/services/babeldoc_runner.py` `:378` | trong block `if self._line_split_shim_enabled:` thêm `env["BABELDOC_SHIM_WORD_WRAP_FIX"] = "1" if self._word_wrap_fix_enabled else "0"` |
| `src/core/job_orchestrator.py` `:275-281` | truyền `word_wrap_fix_enabled=self._settings.babeldoc_word_wrap_fix_enabled` |

**Mặc định BẬT (`Settings` = `True`)** — khác TOC-1 v2 (từng mặc định TẮT). Lý do: đây không phải
heuristic đoán ý đồ layout mà là **sửa một phép cộng thừa**, có tính chất an toàn cấu trúc chứng minh
được (BA10.3-c) và không có "false positive" theo nghĩa của heuristic. **Nhưng**: Dev **không được**
đặt default `True` trong cùng commit với spike chưa xanh — thứ tự bắt buộc là spike (BA10.5) xanh →
Reviewer → mới bật.

**Đường rollback**: `BABELDOC_SHIM_WORD_WRAP_FIX=0` / `babeldoc_word_wrap_fix_enabled=False` — tắt
riêng Bug #10, **không** đụng 7.1/7.2/7.4-b.

---

### BA10.9. Phạm vi test yêu cầu cho Dev

1. **Unit test thuần** `tests/test_babeldoc_word_wrap.py` — gọi `word_wrap.width_before_next_break_point`
   trên golden fixture BA10.6, assert đúng điểm khác biệt hành vi (đã nêu chi tiết ở BA10.6). Kèm case
   biên: list rỗng; `units[0].can_break_line == True` (phải trả `0.0`, **giữ nguyên hành vi gốc**); từ
   dài không có break point nào tới hết list; `scale != 1.0`.
2. **Test wiring** trong `tests/test_babeldoc_runner.py` — assert `env["BABELDOC_SHIM_WORD_WRAP_FIX"]`
   nhận đúng `"1"`/`"0"` theo cờ, và **không** xuất hiện khi `line_split_shim_enabled=False`.
3. **Test shim** trong `tests/test_babeldoc_shim_unicode_regression.py` (hoặc file mới cùng phong
   cách) — dựng class giả có `_get_width_before_next_break_point`, chạy `_apply_typesetting_patch`,
   assert đã bị thay; và assert khi class **thiếu** method đó thì raise `AttributeError` (đường
   fail-safe) mà **không** ảnh hưởng tới các patch `paragraph_finder`.
4. **Live E2E (Protocol 6 R6-03, QA gate)** — 1 lần chạy xuyên suốt trên fixture BA10.6 qua
   `JobOrchestrator` đầy đủ (không chỉ `BabeldocRunner`), **mở file PDF output ra kiểm tra nội dung
   thật**: `"trung thành"` (hoặc case tương đương thực tế quan sát được trong lần chạy đó) xuất hiện
   **liền mạch trên cùng một dòng**. Không được chỉ tin `status == "completed"`.

---

### BA10.10. Việc KHÔNG làm trong task này

- **Không** report bug lên upstream babeldoc trong phạm vi task này (Expert đã xác nhận nhánh `main`
  còn nguyên lỗi, chưa có issue nào mô tả đúng bản chất — issue #615 là chuyện khác). Nếu muốn làm,
  đó là task riêng do người quyết định, không phải Dev.
- **Không** đụng bản babeldoc bundle trong tool `pdf2zh` (BA10.1).
- **Không** gộp chung với 11 cặp overlap còn tồn của Bug #9 / mục "Root Cause Analysis: Text Overlap"
  (2026-09-07) — đó là root cause khác (babeldoc không reflow), không liên quan.
