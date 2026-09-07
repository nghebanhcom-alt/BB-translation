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

`confidence is None` nghia la **khong co span nao qua OCR** (file thuc ra co text layer). Day la
trang thai hop le, **khong phai loi** — `jobs.ocr_confidence` de NULL, khong canh bao. Code cu
`raise MinerUError` khi thieu confidence la sai ca ky thuat lan nghiep vu.

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
| B-2b heuristic marker tăng dần không false-positive | ⚠️ **`[UNVERIFIED]`** — spike bắt buộc (R5-02) |
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
| **7.3** | Ca C — mục lục: **chưa code gì**, chỉ **đo lại** sau 7.1 | Đọc nội dung thật trang Contents; đo **cả 2 chiều**: cấu trúc tốt lên **và** tỷ lệ cắt nhầm caption (RC-1) |

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
| Shim V1 (`PYTHONPATH` + `sitecustomize`) patch được babeldoc subprocess | ⚠️ **`[UNVERIFIED]`** — **spike 7.0 bắt buộc** (R5-02) trước khi giao Dev |
| B-2b heuristic marker tăng dần không false-positive | ⚠️ **`[UNVERIFIED]`** — spike, và chỉ sau 7.1 |
| (8a) nới khung không gây tràn sang ô bên cạnh | ⚠️ **`[UNVERIFIED]`** — spike 8.2 |
| Giá trị sàn cụ thể (~0.67 chỉ là tham chiếu) | ⚠️ **`[UNVERIFIED]`** — phải chốt từ histogram 8.1 |
| pdf2zh không giảm `size`, chỉ giảm `line_height` | ⚠️ **`[UNVERIFIED]`** — Expert đọc source, tôi chưa tự verify; không ảnh hưởng quyết định |

**Trạng thái**: quyết định đã chốt, **vẫn chưa có dòng code nào được viết**. Việc tiếp theo là
**spike 7.0** (shim V1) — cần PM/user duyệt trước khi giao Dev (Protocol 2).
