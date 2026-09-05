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
(`uv tool install --python 3.12 babeldoc`) — Python 3.14 crash vi dung API private
`concurrent.futures.thread._WorkItem` (CHANGELOG). Neu tren may QA khong cai duoc, QA ghi dung
cau: `"release blocked pending live verification: babeldoc"`.

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
