# Architecture — BB-Translation

> Pipeline dich tai lieu nganh banh (EN → VI), giu nguyen layout goc
> Version goc: 1.0 | Ngay goc: 2026-09-03 | Phase goc: Planning
> Author: Tech Lead
>
> **Baseline duyet lai (Hieu, 2026-09-11)**: checkpoint C2 (Protocol C / mo rong Protocol 2) da
> `stale` tu truoc (tai lieu tang tu ban duyet goc len 12.818 dong, khong truy vet duoc moc duyet
> nao). Hieu duyet lai toan bo noi dung hien tai cua file nay lam **Version 2.0**. Xem
> `project_state.json` → `checkpoints[]` cho `approved_commit`, va `docs/design-log.md` muc "Final
> Decision: Hieu tra loi 3 open_questions... (2026-09-11)" cho boi canh day du.

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
    cost_source     TEXT NOT NULL DEFAULT 'estimated',
                    -- 'estimated' | 'metered' — nguon cua CHINH 2 cot ngay tren,
                    -- ghi per-chunk (xem 6.23). `jobs.cost_source` la ket qua
                    -- GOP tu cot nay, khong phai hang so dat cung.
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
- **Cap nhat (6.23, BL-10)**: duong uoc luong nay van la hop dong cho **pdf2zh**, nhung da tro
  thanh **fallback** cho engine `babeldoc` — babeldoc tu dem token that va in ra stdout, nen chunk
  dich bang babeldoc ghi `chunks.cost_source = 'metered'`. `jobs.cost_source` gio **suy ra tu
  chunk** (§6.23.5), khong con dat cung `'estimated'` cho moi job PDF.
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
3. **Cost o v1.0 la uoc luong, khong phai so do dem** (6.6.6) — **chi con dung cho engine
   `pdf2zh`**; nhanh `babeldoc` da co token that tu 6.23.
4. `chunks.api_tokens_used` / `api_cost` la uoc luong per-chunk, khong the doi soat voi hoa don
   nha cung cap. Doi soat that chi kha thi tu v1.1 — **tru nhanh `babeldoc`** (6.23: token that,
   nhung gia tien van phu thuoc bang gia co the loi thoi, xem 6.23.8 muc 1).

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
> **⚠️ SỬA 2026-09-11 (§6.20.15 K-1)**: `EPUB_INLINE_MARKUP_FACTOR = 1.15` **chỉ đúng cho EPUB có
> markup inline thưa**. Đo thật trên 3 cuốn: 1,14× · 1,21× · **2,29×** — cuốn thứ ba (`Sourdough
> Culture`, export từ Kobo) làm công thức trên ước **THẤP ~2×**, vi phạm §6.11.6 ("được ước cao, CẤM
> ước thấp"). Hằng số **không đổi**; thay vào đó §6.20.15 K-1 thêm bước chuẩn hoá ở tầng parse để
> đưa tỉ lệ thật của mọi EPUB về vùng 1,13–1,21×, và K-4 thêm assertion đo-thật chặn im lặng tái
> diễn. Xem §6.20.15.
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

#### 6.20.14. Chiến lược MỚI cho lớp lỗi "DeepSeek trả JSON malformed" sau khi chạm giới hạn Protocol 3 (Tech Lead, 2026-09-10)

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

#### 6.20.15. Bug #EPUB-5 — chuẩn hoá markup rác (K-1) + sửa phép đo runaway đang abort nhầm (K-2..K-5)

**Trạng thái**: hợp đồng. RCA, số liệu đầy đủ, giả thuyết đã bị bác bỏ → `docs/design-log.md`,
mục *"Bug #EPUB-5 — koboSpan KHÔNG phải nguyên nhân runaway (2026-09-11)"*.

**Tóm tắt 1 dòng**: hai lỗi ĐỘC LẬP bị gộp làm một. K-1 sửa lỗi **chi phí/độ ồn payload** (markup
Kobo), K-2..K-5 sửa lỗi **abort nhầm** (phép đo runaway) — **chỉ K-2..K-5 mới làm job chạy được**.
Làm riêng K-1 KHÔNG sửa được job nào.

**Trạng thái quyết định (2026-09-11, Hiếu duyệt qua AskUserQuestion — HOI-04/HOI-05)**:

| Mục | Hướng xử lý | Trạng thái quyết định | Trạng thái verify |
|---|---|---|---|
| K-1 (bóc `koboSpan`, chấp nhận mất `id="kobo.*"`) | **ĐÃ CHỐT LÀM** (HOI-05) | Hiếu đồng ý, không cần hỏi lại | ✅ có nguồn xác thực (S1–S4, S8); **✅ ĐÃ IMPLEMENT + test** (2026-09-11, Dev) |
| K-2 (tách `reasoning_tokens` khỏi phép đo) | Chưa chốt riêng — hệ quả kỹ thuật của K-3 | — | ✅ **VERIFIED qua spike R5-02** (2026-09-11, golden file `tests/fixtures/epub_llm/deepseek_v4flash_usage.json`) — `reasoning_tokens` tồn tại, khác 0 (833/933). **✅ ĐÃ IMPLEMENT + live confirm** (0/784 request có reasoning_tokens khác 0 sau khi tắt thinking, job `bfc0ac24-...`) |
| K-3 (tắt thinking cho nhánh EPUB, `epub_disable_thinking=True`) | **ĐÃ CHỐT LÀM** (HOI-04) | Hiếu đồng ý, chấp nhận đánh đổi chất lượng dịch câu khó | ✅ **VERIFIED qua spike R5-02** — endpoint chấp nhận `extra_body={"thinking":{"type":"disabled"}}` (không 400). **✅ ĐÃ IMPLEMENT + live confirm** trên 784 request thật |
| K-5 | Quyết định kỹ thuật thuần, không cần Hiếu duyệt | — | ✅ **ĐÃ IMPLEMENT + test** (2026-09-11, Dev) — không chặn spike |
| K-4 | Quyết định kỹ thuật thuần, không cần Hiếu duyệt | — | ✅ **Đã đo live sau K-2/K-3/K-5** (2026-09-11) — xem mục K-4 bên dưới cho số đo + quyết định KHÔNG đổi hằng số kèm lý do |

> ⚠️ **Đọc kỹ ranh giới**: quyết định của Hiếu ở HOI-04/HOI-05 là **"làm cái gì"** (chấp nhận đánh
> đổi nghiệp vụ), **KHÔNG PHẢI** "đã verify cơ chế hoạt động đúng như mô tả". Các nhãn
> ⚠️ ASSUMED ở K-2 và K-3 **giữ nguyên hiệu lực** và vẫn chặn Dev implement đúng 2 mục đó cho tới
> khi spike R5-02 xong (đo `response.usage.model_dump()` thật của `deepseek-v4-flash`). Không được
> gỡ nhãn chỉ vì hướng xử lý đã được duyệt.
>
> Nhật ký quyết định: `docs/design-log.md` — *"Final Decision: Hiếu trả lời HOI-04/HOI-05
> (Bug #EPUB-5) — 2026-09-11"*.

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

##### K-1 — Chuẩn hoá markup rác ở TẦNG PARSE (`epub_document.py`) — ✅ ĐÃ CHỐT (HOI-05, 2026-09-11)

**Hiếu đã duyệt** phương án này, gồm cả hệ quả "mất `id="kobo.*"` trong file output" (mục *Mất mát
chấp nhận được* bên dưới). K-1 **không** mang nhãn ASSUMED — mọi claim của nó có nguồn xác thực
(S1–S4, S8) ⇒ Dev được implement ngay, không chờ spike.

**Vấn đề (đo thật)**: `Sourdough Culture.epub` (export Kobo) có **1.963/1.963 unit** chứa
`koboSpan`, tổng **7.616** thẻ. inner-HTML = **1.245.072** ký tự vs text thuần **543.924** →
**2,29×**; sau khi unwrap koboSpan còn **616.745** (**1,13×**). Tức **50,5% payload là rác** —
phải trả tiền input, **và** buộc model sinh lại y hệt ở output (S2, S3) nên trả tiền cả chiều ra.

**Quyết định**: unwrap tại **`_parse_xhtml()`** (`src/services/epub_document.py`), NGAY sau khi
parse xong soup, TRƯỚC mọi thứ khác.

*Vì sao ở `_parse_xhtml()` chứ không ở chỗ build payload* (đây là điểm dễ sai nhất, đã đo):
`write_translated()` → `_apply_translation_untrusted_structure()` đếm "slot" bằng
`_text_runs_under()` trên **node GỐC đọc lại từ zip**. Nếu chỉ bóc markup ở payload, node gốc vẫn
còn 4 koboSpan ⇒ **4 slot**, còn bản dịch trả về chỉ **1 run** ⇒ lệch số lượng ⇒ rơi vào nhánh
*"Known limitation"* (dồn hết bản dịch vào slot dài nhất, **các slot khác GIỮ NGUYÊN tiếng Anh**).
Đo trên chính file này: **85/1.963 unit** đi qua nhánh untrusted, **64** trong số đó multi-slot ⇒
64 unit sẽ dịch sót. Unwrap ở `_parse_xhtml()` làm `load()`, `write_translated()`,
`count_bb_vi_pairs()`, `to_markdown()` **cùng nhìn một cây** — số slot/unit tụt từ median 4,0
(max 16) xuống **median 1,0** (max 12), tức nhánh rủi ro này còn **an toàn hơn** hiện trạng.

**Phạm vi bóc — deny-by-default, hẹp nhất có thể**: CHỈ `<span>` có `class` chứa token `koboSpan`,
và **`unwrap()`** (giữ nguyên con), KHÔNG `decompose()`. Cụ thể **KHÔNG** đụng tới:
- `<span epub:type="pagebreak" id="page_i"/>` — không có class `koboSpan`; `id` của nó ĐƯỢC
  `page-list` tham chiếu, xoá là epubcheck fail.
- mọi `<span>` khác (có thể mang hook CSS thật).
- Không tổng quát hoá thành "bóc mọi span rỗng nghĩa" — chưa đo, R8-02.

**Mất mát chấp nhận được**: `id="kobo.*"` biến mất khỏi file output ⇒ máy đọc Kobo sẽ tự phân trang
lại. Không có tham chiếu nào tới các id này (S8), `nav`/`ncx`/CSS không dùng ⇒ không phá cấu trúc
EPUB, không vi phạm BR-EPUB-01.

**Đọc/ghi (R6-01, data lineage)**:

| Bước | Đọc | Tạo ra | Bước sau đọc gì |
|---|---|---|---|
| `_parse_xhtml(raw_bytes)` | bytes entry zip | `soup` **đã unwrap koboSpan** | `_collect_candidate_nodes(soup)` |
| `load()` | `soup` trên | `EpubUnit.text` = `_inner_html(_strip_nested_lists(node))` — **đã sạch koboSpan** | `plan_epub_chunks(units)`; `payload = [{"id", "html": u.text}]` (job_orchestrator.py:2372) — **không sửa dòng này** |
| `write_translated()` | mở LẠI zip gốc, `_parse_xhtml()` → **cùng phép unwrap** | `output_path` | `_check_epub_output_guard(source_doc, merged_path)` |

##### K-1b — Tác động lên BR-EPUB-05 (bắt buộc đọc trước khi code)

Guard giữ **nguyên văn**, không nới một điều kiện nào. Kiểm từng điều kiện:

| Điều kiện (`job_orchestrator.py:478-524`) | Ảnh hưởng của K-1 | Vì sao |
|---|---|---|
| `guard_doc.total_chars > 0` | không | unwrap không xoá text |
| `len(guard_doc.units) == len(source_doc.units)` | **không** | `span` **không** thuộc `UNIT_TAG_NAMES`; unwrap không đổi tập `_collect_candidate_nodes()`. Và cả 2 phía đều qua `_parse_xhtml()` đã unwrap ⇒ đối xứng |
| `bilingual=False`: ≥90% unit có `orig.text != new.text` | **không** (nới lỏng nhẹ về phía an toàn) | `source_doc` cũng đã unwrap ⇒ so sánh vẫn là "EN sạch vs VI sạch" |
| `bilingual=True` (mặc định): `count_bb_vi_pairs()` ≥90% node `bb-vi` **và** ≥90% cặp khác nội dung | **không** | hàm này so bằng `get_text(" ", strip=True)` — **text thuần**, tag vô can |

⚠️ **Bẫy đối xứng**: K-1 **bắt buộc** nằm trong `_parse_xhtml()` — nếu Dev đặt ở `load()` mà quên
`write_translated()`/`count_bb_vi_pairs()`, `source_doc` sạch còn output còn koboSpan ⇒ điều kiện 3
vẫn qua nhưng lineage đã lệch. Test bắt buộc theo R6-02 phải assert **cùng một hàm** được dùng cho
cả 3 đường đọc.

##### K-2 — Tách token thinking khỏi phép đo runaway (đây mới là bản vá làm job chạy được)

`TranslationResult` (`src/services/translation.py`) thêm **1 field mới, mặc định `0`**:

```python
reasoning_tokens: int = 0   # phần token KHÔNG phải nội dung trả về (thinking/CoT)
```

`OpenAIProvider.translate()` (DeepSeek kế thừa) đọc:
`getattr(getattr(response.usage, "completion_tokens_details", None), "reasoning_tokens", 0) or 0`.

- `output_tokens` **giữ nguyên** = `completion_tokens` → **tính tiền không đổi** (nhà cung cấp tính
  tiền trên completion_tokens; hạ số này xuống là tự ước thấp chi phí, vi phạm §6.11.6).
- `answer_tokens = max(0, output_tokens - reasoning_tokens)` → **chỉ dùng cho phép đo runaway**.

`job_orchestrator.py:2389-2391` đổi đối số (KHÔNG đổi công thức trong `cost_estimator.py`):
```python
runaway = is_runaway_output(len(payload_json), result.answer_tokens)
runaway_ratio = result.answer_tokens / max(expected_output_tokens, 1)
```
`requests.jsonl` ghi thêm `reasoning_tokens` và `answer_tokens` (giữ nguyên các field cũ).

> ✅ **VERIFIED (2026-09-11, Dev, spike R5-02)** — không còn ASSUMED. Gọi thật 1 request EPUB tới
> `deepseek-v4-flash` (thinking mặc định): `response.usage.completion_tokens_details.reasoning_tokens
> = 833` (trên `completion_tokens = 933` tổng) — field TỒN TẠI và KHÁC 0, đúng S7. Golden file:
> `tests/fixtures/epub_llm/deepseek_v4flash_usage.json`. Đã implement (`TranslationResult.
> reasoning_tokens`/`answer_tokens`, `src/services/translation.py` +
> `src/services/openai_provider.py`) và xác nhận lại trên live E2E 784 request thật
> (job `bfc0ac24-0664-4932-96da-1ac99c1abc10`, `Sourdough Culture...epub`) — 0/784 request có
> `reasoning_tokens` khác 0 (nhất quán, vì K-3 đã tắt thinking cho toàn bộ nhánh EPUB, xem K-3 bên
> dưới và K-4 cho số đo `answer_tokens` đầy đủ).

##### K-3 — Tắt thinking cho nhánh dịch EPUB — ✅ ĐÃ CHỐT HƯỚNG (HOI-04, 2026-09-11), ✅ cơ chế ĐÃ VERIFIED + IMPLEMENT

**Hiếu đã duyệt** hướng "tắt thinking cho nhánh EPUB", chấp nhận đánh đổi: chi phí output giảm
mạnh, chất lượng dịch câu khó **có thể** giảm nhẹ. ⇒ `Settings.epub_disable_thinking` mặc định
`True` là hợp đồng chính thức, không còn là đề xuất.

**Cơ chế đã verify (2026-09-11, Dev, spike R5-02)**: `extra_body` truyền đúng key `thinking`, endpoint
DeepSeek CHẤP NHẬN (không 400) — xem hộp verify cuối mục.

**Lệch nhỏ so với pseudocode nháp bên dưới (có chủ đích, KHÔNG phải phỏng đoán)**: pseudocode gốc
viết `translate()` truyền `extra_body=self._extra_body() khi khác rỗng` — nếu hiểu là BẤT CỨ khi
nào `_extra_body()` khác rỗng thì áp dụng, sẽ tắt thinking cho MỌI lần gọi `DeepSeekProvider.
translate()`, kể cả `glossary.py` (dịch glossary term) và `rotated_text_overlay.py` (PDF babeldoc) —
2 nơi này CŨNG gọi `.translate()` (không chỉ nhánh EPUB) nhưng K-3 chỉ được Hiếu duyệt cho **riêng
nhánh EPUB**. Implement thật thêm 1 thuộc tính INSTANCE `disable_thinking: bool = False` (mặc định
`False`, hành vi không đổi) — `translate()` chỉ áp `_extra_body()` khi
`supports_thinking_toggle and self.disable_thinking` đều đúng; `run_epub_job()`
(`src/core/job_orchestrator.py`) tự bật `pricing_provider.disable_thinking = True` NGAY sau khi
tạo provider, CHỈ trong nhánh EPUB, theo `Settings.epub_disable_thinking` — vẫn giữ đúng tinh thần
R8-03 (hỏi capability `supports_thinking_toggle` trên object, không rẽ nhánh theo tên provider),
chỉ thêm 1 lớp "ai được phép bật cờ" để không rò rỉ sang PDF/glossary ngoài ý Hiếu đã duyệt.

Dịch câu là tác vụ **không cần CoT**; effort `high` mặc định (S6) là phần lớn chi phí output đang
trả. Thêm **thuộc tính năng lực trên class provider** (R8-03 — KHÔNG rẽ nhánh `if provider ==` trong
`job_orchestrator`):

```python
class OpenAIProvider:
    supports_thinking_toggle: bool = False
    def _extra_body(self) -> dict: return {}

class DeepSeekProvider(OpenAIProvider):
    supports_thinking_toggle = True
    def _extra_body(self) -> dict:
        return {"thinking": {"type": "disabled"}}   # doc: api-docs.deepseek.com/guides/thinking_mode/
```
`translate()` truyền `extra_body=self._extra_body()` khi khác rỗng. 4 provider còn lại trả `{}` ⇒
hành vi **không đổi một byte**.

Bật/tắt qua `Settings.epub_disable_thinking: bool = True` (`.env`, Protocol E → phải có commit trong
24h khi đổi). Mặc định **True**: đây là quyết định kỹ thuật có nguồn xác thực, không phải chính sách
tài chính của user.

> ✅ **VERIFIED (2026-09-11, Dev, spike R5-02)** — không còn ASSUMED. `extra_body={"thinking":
> {"type": "disabled"}}` gửi qua `openai` SDK tới endpoint DeepSeek: **KHÔNG** trả HTTP 400, và
> `completion_tokens_details` biến mất khỏi response (`None`, không phải object với
> `reasoning_tokens=0`) — `getattr(None, "reasoning_tokens", 0) or 0` trong `OpenAIProvider.
> translate()` xử lý đúng trường hợp này. Golden file:
> `tests/fixtures/epub_llm/deepseek_v4flash_usage.json`. Xác nhận lại trên live E2E 784 request thật
> (0/784 request rò rỉ `reasoning_tokens`).

K-2 và K-3 **độc lập, làm được cả hai**: K-3 làm giảm mạnh `output_tokens` (⇒ giảm tiền), K-2 làm
phép đo đúng **kể cả khi** một provider khác bật thinking mà ta không tắt được.

##### K-4 — Hiệu chỉnh lại hằng số, chỉ SAU khi có số đo hậu-K-2/K-3

`CHARS_PER_TOKEN_VI = 2.0` hiện **sai nặng**: đo thật trên 55 chunk cho **0,23–0,66 ký tự/token**
(median ~0,32) — và đây còn là **cận trên** (mẫu số bỏ qua token của retry). Nhưng **CẤM sửa hằng số
này trong cùng lượt với K-2/K-3**: số đo hiện tại đã bị ô nhiễm bởi token thinking, hiệu chỉnh theo
nó là khoá cứng cái sai vào hằng số. Thứ tự bắt buộc:

1. Làm K-2 (+K-3), chạy live **1 cuốn**, thu `requests.jsonl` có `answer_tokens`.
2. Tính `chars_per_answer_token` thật; cập nhật `CHARS_PER_TOKEN_VI` **và** `VI_CHAR_EXPANSION`,
   ghi số đo + ngày vào §6.20.15 này (không để ⚠️ ASSUMED trần).
3. Chỉ khi đó mới xét lại `EPUB_RUNAWAY_OUTPUT_FACTOR = 3.0`. Tiêu chí giữ nguyên §6.20.13.3b:
   **max ratio của lần chạy lành mạnh phải ≤ 1,5×**; nếu không, ngưỡng vẫn sai.

Assertion chống tái diễn im lặng (K-1 phần đo): `run_epub_job()` log WARNING khi
`sum(len(u.text)) / doc.total_chars > EPUB_INLINE_MARKUP_FACTOR` — tức khi công thức cost gate
đang ước **thấp**. Chỉ log, **không chặn** job (§6.11.6 chỉ cấm ước thấp im lặng).

**K-4 — số đo thật sau K-2/K-3/K-5 (2026-09-11, Dev, live E2E job `bfc0ac24-0664-4932-96da-1ac99c1abc10`,
`Sourdough Culture...epub`, KHÔNG kèm K-1)**: 66/66 chunk `completed`, **784 request**, **0/784
request có `reasoning_tokens` khác 0** (K-3 tắt thinking hoạt động đúng trên toàn bộ sách thật, không
chỉ 1 request spike). `chars_per_answer_token` (`payload_chars / answer_tokens`, CÙNG định nghĩa
`payload_chars` với `is_runaway_output()`) đo trên cả 784 request: min 1,89 · median **2,386** · max
7,66. Suy ra `runaway_ratio = answer_tokens / epub_expected_output_tokens(payload_chars)`: mean
**0,7048** · median **0,7234** · **max 0,9119** — xa dưới ngưỡng `EPUB_RUNAWAY_OUTPUT_FACTOR = 3,0`
VÀ dưới tiêu chí ≤ 1,5× của bước 3 (K-4) với biên an toàn thoải mái. Tổng chi phí thật đo được:
$0,588 / 2.043.387 token (input + output cộng dồn), well trong `max_cost_per_job_usd=2.00`.

**Quyết định KHÔNG đổi `CHARS_PER_TOKEN_VI`/`VI_CHAR_EXPANSION`/`EPUB_RUNAWAY_OUTPUT_FACTOR` ở lượt
này** (khác kỳ vọng ban đầu của mục K-4 khi viết — quyết định này CÓ SỐ ĐO, không phải bỏ qua bước):
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

##### K-5 — R-b không được là "abort khi thiếu bất kỳ id nào"

Ngay cả sau K-2, giữ **deny-by-default** cho chính cơ chế abort: R-b chỉ được raise khi **cả hai**
đúng — `runaway` (đo bằng `answer_tokens`) **và** `len(missing_ids) > EPUB_MAX_SINGLE_ID_RETRIES`.
Với ≤ 2 id thiếu, thang cứu hộ C-1 (retry từng-id) rẻ và có tỉ lệ thành công cao; abort cả chunk ở
đó là đánh đổi sai chiều — và đó đúng là cái bẫy đã làm 3 job chết ở §6.20.13.3b.

##### Thứ tự implement bắt buộc

1. **Spike R5-02** (K-2/K-3): 1 request thật, capture `usage` → golden file. **Chặn** K-2, K-3.
2. K-5 (thuần logic, không phụ thuộc spike) → K-2 → K-3.
3. Chạy live 1 cuốn, thu số đo.
4. K-1 (độc lập hoàn toàn, có thể song song, nhưng **không** được báo là "fix Bug #EPUB-5").
5. K-4 cuối cùng, dựa trên số đo bước 3.

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

### 6.22. BL-04 — Phát hiện babeldoc bỏ đoạn VÌ KHÔNG VỪA KHUNG (paragraph drop, kênh 1/3) và báo cáo như một QA finding

> **Phạm vi — đọc trước khi dùng bất kỳ con số nào của mục này**: §6.22 đo **đúng một** trong ít
> nhất **ba** kênh làm mất nội dung của babeldoc (kênh "không vừa khung"). Hai kênh còn lại (lọc góc
> xoay và thiếu font id, cả hai xảy ra ở `ActiveILCreater.project_native_char` **trước** khi ký tự
> thành IL) **KHÔNG** được đo bởi thiết kế này. Chi tiết + bằng chứng đo thật: **§6.22.6.1**. Không được đọc "0 drop" là
> "không mất nội dung".

**Vấn đề đang vá**: từ khi Bug #9 tắt `font_shrink_page()` cho engine `babeldoc`
(`BabeldocRunner.needs_font_shrink = False`, xem `design-log.md` B9.3–B9.5), khối
`for entry in overflow_entries:` trong `job_orchestrator.py:1907-1920` **không bao giờ chạy** cho
nhánh babeldoc — `overflow_entries` luôn rỗng. Nhánh babeldoc do đó **không có bất kỳ cờ cảnh báo
nào** cho trường hợp mất nội dung do không vừa khung (`design-log.md` B9.7, backlog `BL-04`).

Mục này thiết kế phần bù: lấy tín hiệu **từ chính babeldoc**, không tự can thiệp hậu kỳ vào PDF.

> **Quy ước ký hiệu trong §6.22**: `F1`–`F9` = phát hiện của Domain Expert **lượt 1**; `X1`–`X8` =
> phát hiện của Domain Expert **lượt 2 (2026-09-11)** —
> `docs/expert-notes/domain-expert-20260911-bl04-babeldoc-overflow.md`, section "Xác nhận lần 2".
> ⚠️ **KHÔNG liên quan** tới loạt `X1`–`X6` của §6.20.12 (phản biện EPUB, 2026-09-08) — trùng chữ
> cái, khác hạng mục, khác ngày. Nhật ký đầy đủ của lượt này: `design-log.md` **BL4.15**.

#### 6.22.1. Nguồn xác thực (Protocol 5 R5-01 + R5-05 — verify lại, KHÔNG kế thừa Bug #9)

**Version thật sự đang chạy khi `pdf_translate_engine=babeldoc`: `babeldoc 0.6.4`.**

Chuỗi truy vết (tự chạy 2026-09-11, không suy đoán):

| # | Bước | Lệnh/file đã đọc | Kết quả |
|---|---|---|---|
| V-1 | Runner gọi executable nào | `src/services/babeldoc_runner.py:232` (`executable: str = "babeldoc"`), `src/core/config.py:151` (`babeldoc_executable: str = "babeldoc"`) | `babeldoc`, **không phải** `pdf2zh` |
| V-2 | `babeldoc` resolve về đâu | `which babeldoc` → `/Users/hieutt/.local/bin/babeldoc`; shebang dòng 1 = `#!/Users/hieutt/.local/share/uv/tools/babeldoc/bin/python` | uv tool env **riêng**, độc lập với env của `pdf2zh` |
| V-3 | Version trong env đó | `ls .../uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc-*.dist-info` → `babeldoc-0.6.4.dist-info`; `babeldoc --version` → `babeldoc 0.6.4` | **0.6.4** |
| V-4 | `babeldoc 0.2.33` PM tìm thấy là gì | `.../uv/tools/pdf2zh/lib/python3.12/site-packages/babeldoc-0.2.33.dist-info`; `pdf2zh --version` → `pdf2zh v1.9.11` | dependency **bắc cầu** của pdf2zh, nằm trong tool env của pdf2zh |
| V-5 | 0.2.33 có bao giờ chạy trong pipeline này không | `pdf2zh/pdf2zh.py:174-177` khai báo flag `--babeldoc` ("Use experimental backend babeldoc"), `pdf2zh.py:320` `if parsed_args.babeldoc:`; `grep -n '"--' src/services/pdf2zh_runner.py` → chỉ `--pages`, `--output`, `--thread`, `--prompt`, `--ignore-cache` | **KHÔNG**. `Pdf2zhRunner` không bao giờ truyền `--babeldoc` → nhánh dùng 0.2.33 là code chết với app này |

**Kết luận cho câu hỏi `[CHƯA VERIFY]` của PM**: không phải (a) gõ nhầm, không phải (b) hạ version,
không phải (c) 2 version khác hành vi. Đáp án là **(d)**: trên máy này có **hai bản babeldoc cài
độc lập** — 0.6.4 (uv tool riêng, là bản engine `babeldoc` thực sự chạy) và 0.2.33 (dep bắc cầu bên
trong tool env của pdf2zh, không được kích hoạt). Con số 0.6.4 trong `design-log.md` B9-05 là
**đúng**. Không có sai lệch version nào cần xử lý.

**Đính chính đường dẫn module**: `design-log.md` B9-05 ghi nguồn là `IL/midend/typesetting.py`.
Đường dẫn thật trong 0.6.4 là
`babeldoc/format/pdf/document_il/midend/typesetting.py`. (Layout `babeldoc/document_il/midend/...`
— không có tầng `format/pdf/` — là của **0.2.33**, xác nhận bằng `find` trong tool env pdf2zh. Đây
đúng là loại lệch cấu trúc mà R5-05 sinh ra để bắt, dù ở đây nó vô hại vì bản 0.2.33 không chạy.)

Toàn bộ trích dẫn dưới đây trỏ vào cây source của **0.6.4 đã cài**, gốc:
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`
(viết tắt `<BD>/` trong các mục sau).

⚠️ **Self-correction R5-05 (2026-09-11, Domain Expert X1 — bản trước của §6.22 trích dẫn NHẦM
class frontend)**: trong luồng **DỊCH** của 0.6.4, `_do_translate_single()` parse bằng
`new_parser/native_parse.py` (`<BD>/format/pdf/high_level.py:902-910`), và `native_parse.py:53, 57`
dựng sink là **`ActiveILCreater`** (`<BD>/format/pdf/document_il/frontend/il_creater_active.py`).
Class **`ILCreater`** (`.../frontend/il_creater.py:402`) + `legacy_parse.start_parse_il` **KHÔNG**
nằm trên đường dịch — người dùng duy nhất của chúng trong cả package là entry point tách biệt
`<BD>/format/pdf/parse_only.py:5-6, 29` (tự verify bằng `grep -rn "ILCreater\|legacy_parse" <BD>`
ngày 2026-09-11: ngoài `parse_only.py` chỉ còn khai báo `Protocol` ở `pdfminer`-side
`format/pdf/pdfinterp.py:50` và `format/pdf/converter.py` — bản thân `converter.py` cũng chỉ được
`legacy_parse` dùng).

⇒ **Mọi trích dẫn frontend trong §6.22 PHẢI trỏ vào bản `_active`.** Kết luận kỹ thuật của §6.22
**không đổi** vì `ActiveILCreater.project_native_char` (`il_creater_active.py:1292-1300`) có predicate
lọc **y hệt** bản legacy (đọc trực tiếp, xem §6.22.6.1). Nhưng địa chỉ sai là nguy hiểm theo đúng
khuôn Bug #9: ai patch `ILCreater` trong luồng dịch sẽ được một **no-op im lặng** — không lỗi, không
log, và kết luận nhầm là "đã đo, không có gì". Đây cùng loại lệch mà R5-05 sinh ra để bắt như ca
"0.2.33 có `document_il/` không có `format/pdf/`" ở trên, chỉ khác là lần này lệch **bên trong cùng
một version**.

**Midend KHÔNG bị ảnh hưởng** (ghi ra để không ai phải đi audit lại): `high_level.py:971`
`ParagraphFinder(...).process(docs)` và `:1038` `Typesetting(...).typsetting_document(docs)` vẫn nằm
nguyên trên đường chạy ⇒ patch Bug #7 (`paragraph_finder`) và Bug #10 (`typesetting`) của shim vẫn
đúng chỗ. Chỉ tầng **frontend** đổi.

#### 6.22.2. Hành vi thật khi text không vừa khung — verify lại B9-05

Đã tự đọc `<BD>/format/pdf/document_il/midend/typesetting.py` (1.682 dòng) và
`<BD>/format/pdf/document_il/backend/pdf_creater.py`. Đối chiếu từng vế của B9-05:

| Vế của B9-05 | Kết quả verify lại (2026-09-11, bản 0.6.4 đã cài) | Nguồn |
|---|---|---|
| "tự bóp cỡ chữ tới tối thiểu 10%" | **ĐÚNG** — `min_scale = 0.1`, vòng `while scale >= min_scale`. Bước giảm: `-0.05` khi `scale > 0.6`, `-0.1` khi thấp hơn | `typesetting.py:967-973`, `:1011-1015` |
| "bỏ hẳn đoạn nếu vẫn không vừa" | **ĐÚNG, nhưng cơ chế khác với hình dung trong B9-05** — không có lệnh "drop" tường minh nào. `render_paragraph()` **xoá trắng** `paragraph.pdf_paragraph_composition = []` TRƯỚC khi typeset lại; layout chỉ được ghi đè trở lại khi `all_units_fit` là `True`. Không lần scale nào fit → composition **ở nguyên trạng thái rỗng** → đoạn biến mất khỏi PDF | `typesetting.py:1277-1280` (xoá trắng), `:986-1002` (chỉ apply khi fit), `:1064-1076` (hết vòng, trả `final_typeset_units = None`) |
| "KHÔNG BAO GIỜ vẽ tràn ra ngoài box" | **ĐÚNG với sắc thái quan trọng**: khi text vượt đáy box, `_layout_typesetting_units` đặt `all_units_fit = False` và **cố ý không `break`** (comment gốc: `这里不要 break，继续排版剩余内容`) — tức nó VẪN tính toạ độ cho phần tràn. Nhưng kết quả đó chỉ nằm trong biến tạm và **bị vứt bỏ** vì `apply_layout` không chạy khi `all_units_fit=False`. Thêm nữa, trước khi bỏ cuộc babeldoc còn **nới rộng chính box** xuống dưới rồi sang phải nếu có chỗ trống (`get_max_bottom_space` / `get_max_right_space`), và cập nhật `paragraph.box` theo — nên chữ có thể nằm ngoài box **ban đầu**, nhưng luôn trong box **đã nới** và luôn trong vùng đã kiểm tra là trống | `typesetting.py:1440-1444`, `:986-1002`, `:1020-1056` |
| (không có trong B9-05) | Trước khi bỏ cuộc còn **một lần thử lại nữa**: chạy lại toàn bộ vòng với `use_english_line_break=False` (bỏ luật ngắt dòng kiểu tiếng Anh) | `typesetting.py:1064-1073` |
| (không có trong B9-05) | Vòng giảm scale **chỉ chạy quá 1 vòng khi `paragraph.debug_id` khác rỗng** — nếu không có `debug_id`, hàm return ngay sau lần thử đầu. Đã kiểm: `ParagraphFinder` gán `debug_id=generate_base58_id()` cho **mọi** paragraph, không phụ thuộc `--debug` → trong luồng chạy thật vòng lặp **có** chạy đủ | `typesetting.py:1008-1009`; `paragraph_finder.py:497-502`, `:874`, `:911` |

**Kết luận R5-05**: verify lại xác nhận B9-05 **khớp** với bản 0.6.4 đang chạy. Quyết định
`BabeldocRunner.needs_font_shrink = False` của Bug #9 **giữ nguyên, không đổi**. Điểm bổ sung so
với B9-05 là *cơ chế* drop (composition rỗng), và chính cơ chế đó là thứ cho ta điểm quan sát ở
6.22.3.

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

#### 6.22.4. Thiết kế — patch quan sát (observer) trong shim + file sidecar JSONL

**Nguyên tắc**: patch này **chỉ đọc, không sửa** hành vi typeset của babeldoc. Khác hẳn 4 patch có
sẵn (Bug #7 / Bug #10) vốn thay đổi kết quả. Đây là ràng buộc thiết kế, không phải mô tả: nếu
implementation nào cần sửa dữ liệu để lấy được tín hiệu thì thiết kế này sai, dừng và escalate.

**Điểm hook**: `PDFCreater.create_render_units_for_page(self, page, translation_config)` —
`<BD>/format/pdf/document_il/backend/pdf_creater.py:839-843`.

Lý do chọn đúng hàm này (đã verify, không suy đoán):

| Yêu cầu | Xác nhận | Nguồn |
|---|---|---|
| Có object `page` → lấy được số trang | Tham số thứ nhất là `page`; thân hàm duyệt `page.pdf_paragraph` | `pdf_creater.py:839-852` |
| Chạy **sau** typesetting, tức composition đã ở trạng thái cuối | Được gọi từ `update_page_content_stream` trong giai đoạn ghi PDF, sau midend | `pdf_creater.py:1698` |
| Chỉ chạy **đúng 1 lần / trang** (không nhân đôi record vì bản dual) | `write()` gọi `update_page_content_stream` trong đúng 1 vòng `for page in self.docs.page` (`:1465-1466`); PDF dual dựng lại **từ trang mono đã render**, không render lại | `pdf_creater.py:1465-1466`, `:1559-1574` |
| …**VÀ** `--watermark-output-mode` **khác** `both` (X4 — ràng buộc có tên, không phải phụ thuộc tình cờ) | Khi `watermark_output_mode == WatermarkOutputMode.Both`, `high_level.py:1023-1029` gọi `generate_first_page_with_watermark()`, hàm này dựng **một `PDFCreater` THỨ HAI** trên bản copy trang đầu và gọi `write()` **lần nữa** (`:1097-1103`) ⇒ **trang đầu của mỗi chunk sẽ có 2 record `page` và có thể 2 record `drop`**. Hôm nay an toàn vì `BabeldocRunner` hardcode `--watermark-output-mode no_watermark` (`babeldoc_runner.py:350-351`) — nhưng đó là một phụ thuộc vào code khác nên **phải nằm trong hợp đồng**: ai đổi cờ này phải quay lại đọc 6.22.4 và 6.22.6 (checksum + trạng thái 3 sẽ kêu, nhưng kêu **sai nguyên nhân**) | `<BD>/format/pdf/high_level.py:1023-1029`, `:1097-1103`; `src/services/babeldoc_runner.py:350-351` (tự verify 2026-09-11) |
| Không đụng nhánh debug | Nhánh `write_debug_info` (`:1129-1165`) gọi thẳng `render_paragraph_to_char`, **không** đi qua hàm này | `pdf_creater.py:1129-1165` |

**Predicate phát hiện drop** — sao chép đúng định nghĩa của chính babeldoc
(`pdf_creater.py:814-831`), không tự phát minh ngưỡng:

```python
def _has_rendered_chars(paragraph) -> bool:
    for comp in paragraph.pdf_paragraph_composition or []:
        if comp.pdf_character is not None:
            return True
        if comp.pdf_formula is not None and comp.pdf_formula.pdf_character:
            return True
    return False

# dropped  <=>  (not _has_rendered_chars(p)) and p.unicode and p.debug_id
```

**Số trang (R6-01 — nói rõ đơn vị, không để mập mờ)**: `page.page_number` là chỉ số **0-based trong
tài liệu GỐC**, không phải chỉ số trong chunk và không phải chỉ số trong file output. Đã verify 2
đường:
- `pdf_creater.py:1708` dùng `pdf[page.page_number].xref` để index vào pymupdf document **gốc**;
- việc xoá trang không được dịch (`only_include_translated_page`) xảy ra ở `:1489-1502`, tức **SAU**
  vòng render `:1465-1466` — nên tại thời điểm hook chạy, đánh số vẫn là đánh số của file gốc.

`BabeldocRunner` luôn truyền **cả file** kèm `--pages <page_range>` (`babeldoc_runner.py:329-332`),
nên `page.page_number + 1` = **số trang 1-based của tài liệu nguồn**. Shim ghi ra field
`page_number_1based = page.page_number + 1`; app dùng thẳng, **không** cộng thêm offset chunk.

**Kênh truyền ra ngoài**: file **JSONL sidecar**, đường dẫn do app quyết định và truyền qua biến môi
trường `BABELDOC_SHIM_DROP_REPORT_PATH` (cùng kiểu với 3 biến `BABELDOC_SHIM_*` đã có ở
`babeldoc_runner.py:386-389`). Không dùng stdout cho payload — lý do đã đo ở 6.22.3(a).

**Vị trí file — RÀNG BUỘC, không phải tuỳ chọn**: sidecar **PHẢI** nằm trong `chunk_output_dir`
(thư mục `output_dir` mà `_call_translator()` truyền cho `translate_pages()`). Lý do có nguồn xác
thực: `job_orchestrator.py:1801-1802` chạy `if chunk_output_dir.exists(): shutil.rmtree(chunk_output_dir)`
ở **đầu MỖI attempt** — kể cả attempt retry ngầm bên trong `with_retry`, và cả lần resume sau
crash (comment tại `:1786-1800` giải thích vì sao). Nhờ đó bản ghi của attempt hỏng bị xoá sạch
trước attempt kế tiếp. Đặt sidecar ở **bất kỳ đâu ngoài** thư mục này → record của attempt hỏng
sống sót và bị cộng chung với attempt thành công (đếm thừa, không ai biết). Đây là phụ thuộc vào
hành vi của code khác nên phải ghi vào hợp đồng, không để Dev suy ra.

Quy tắc ghi (bắt buộc, để an toàn với multiprocessing của babeldoc — `main.py` đặt
`mp.set_start_method("spawn")`, và process con re-import `sitecustomize`):
- mở file ở chế độ **append** (`"a"`), ghi **1 dòng JSON rồi đóng ngay**, không giữ handle mở;
- `ensure_ascii=False`;
- **cắt `text_excerpt` tối đa 400 ký tự** — lý do là *"đủ để QA nhận ra đoạn nào bị mất, và giữ file
  sidecar nhỏ"*, **KHÔNG** phải để "nằm dưới ngưỡng ghi nguyên tử của `O_APPEND`".
  ⚠️ **Đính chính (2026-09-11, Domain Expert F7 — lý do cũ SAI về kỹ thuật, đã đo lại)**: ngưỡng
  ghi nguyên tử liên quan là `PIPE_BUF`, đo thật trên chính máy này bằng
  `os.pathconf(".", "PC_PIPE_BUF")` → **512 byte** (Darwin; Linux thường 4096). 400 ký tự tiếng
  Việt với `ensure_ascii=False` có thể tới ~1.200 byte UTF-8, cộng `box`/`debug_id`/`layout_label`
  ⇒ **vượt xa 512** — con số 400 chưa bao giờ đảm bảo tính nguyên tử. Thêm nữa `open(..., "a")` của
  Python là text I/O **có buffer**, có thể tự tách thành nhiều `write()` syscall. Và trên thực tế
  **chỉ có 1 process ghi dòng `drop`/`page`** (xem "Ai ghi file này" ngay dưới), nên nguy cơ đan xen
  gần như không tồn tại. Giữ 400 vì lý do thật ở trên; **không** được coi 400 là một bất biến kỹ
  thuật có thể suy ra ngưỡng khác.

**Ai ghi file này** (xác định rõ để không ai phải suy đoán về tranh chấp ghi): vòng render
`for page in self.docs.page` của `PDFCreater.write()` (`pdf_creater.py:1465-1466`) chạy trong
**process chính** ⇒ **chỉ process chính** ghi dòng `page` và `drop`. babeldoc chỉ tạo process con ở
`subset_fonts_in_subprocess` (`pdf_creater.py:1220`, gọi tại `:1216` nhánh debug và `:1479`) — bước
đó **không** render paragraph nên không sinh record nào. Ngược lại, dòng `header` thì **có thể**
xuất hiện nhiều lần: `main.py:951` đặt `mp.set_start_method("spawn")` trên macOS, mọi process con
re-import `sitecustomize` qua `PYTHONPATH` và áp patch lại (đó là lý do header mang `pid`).

**Schema mỗi dòng** (`schema` = `babeldoc_drop_report/v2`):

| Field | Kiểu | Nguồn | Ghi chú |
|---|---|---|---|
| `type` | `"header"` \| `"page"` \| `"drop"` | shim | **KHÔNG** giả định thứ tự/vị trí dòng — xem "Quy tắc parse" dưới |
| `page_number_1based` | int | `page.page_number + 1` | có ở `type="page"` **và** `type="drop"` |
| `paragraph_count` | int | `len(page.pdf_paragraph)` | chỉ ở `type="page"` |
| `dropped_count` | int | số paragraph của trang đó thoả predicate drop | chỉ ở `type="page"`; dùng làm checksum chéo với số dòng `drop` |
| `debug_id` | str | `paragraph.debug_id` | id base58 babeldoc tự sinh. ⚠️ **KHÔNG dùng để dedupe** — xem ghi chú dưới bảng |
| `layout_label` | str \| null | `paragraph.layout_label` | vd `"plain text"`, `"title"` |
| `box` | `{x, y, x2, y2}` \| null | `paragraph.box` | toạ độ PDF của khung đã (có thể) được nới |
| `optimal_scale` | float \| null | `paragraph.optimal_scale` | **marker chẩn đoán**: `== 0.1` nghĩa là đoạn này đã được biết là không fit ngay từ `preprocess_document` — `_find_optimal_scale_and_layout(apply_layout=False)` trả về `min_scale = 0.1` khi không scale nào fit (`typesetting.py:1076`), và `preprocess_document` chỉ **hạ** các giá trị **lớn hơn** mode (`typesetting.py:929-935`, đã đọc trực tiếp) nên 0.1 sống sót. Giá trị khác 0.1 = đoạn từng fit ở preprocess nhưng drop ở lần typeset thật |
| `scale` | float \| null | `paragraph.scale` | **thường là `null`** ở ca drop, vì `paragraph.scale` chỉ được gán khi apply thành công (`typesetting.py:989`) — đây là *thông tin đúng*, không phải thiếu dữ liệu |
| `text_excerpt` | str | `paragraph.unicode[:400]` | bản **dịch** bị mất — thứ QA cần để soi tay |
| `text_len` | int | `len(paragraph.unicode)` | độ dài đầy đủ trước khi cắt |

⚠️ **`debug_id` KHÔNG phải khoá dedupe** (Domain Expert F9, 2026-09-11): `generate_base58_id()`
(`paragraph_finder.py:46`, `:500`) sinh **ngẫu nhiên mỗi lần chạy**, nên id của cùng một đoạn khác
nhau giữa 2 lần chạy → không khử được trùng giữa 2 chunk chồng lấn (6.22.5 F1). Ngược lại, độ dài
id chỉ 5 ký tự nên 2 đoạn **khác nhau** trên cùng 1 trang về lý thuyết có thể trùng id và bị **gộp
nhầm**. Trong **một** lần chạy thì không có gì để dedupe: hook chạy đúng 1 lần/trang và mỗi
paragraph xuất hiện đúng 1 lần trong `page.pdf_paragraph`. ⇒ **Thiết kế này KHÔNG có bước dedupe**;
thứ thật sự cần khử là vùng chồng lấn giữa các chunk, xử lý bằng bộ lọc dải trang ở 6.22.5.
`debug_id` chỉ để QA đối chiếu tay trong phạm vi **một** lần chạy.

**Record `type="page"` — vì sao tồn tại (F2)**: shim ghi **1 dòng `page` cho MỖI trang đi qua hook**,
ngay sau khi duyệt xong `page.pdf_paragraph` của trang đó (nên `dropped_count` đã biết). Không có
record này thì hệ thống chỉ chứng minh được *"patch đã cài"*, chứ không chứng minh được *"hook đã
chạy trên đủ các trang của chunk"* — xem 6.22.6 trạng thái 3/4.

**Dòng `header`** (ghi lúc patch được áp thành công, tức lúc **import module** trong
`_PatchingLoader.exec_module`): `{"type":"header","schema":"babeldoc_drop_report/v2",
"babeldoc_version":"0.6.4","pid":<os.getpid()>}`.

**Quy tắc parse (bắt buộc — F2)**:
- **KHÔNG** giả định dòng đầu tiên là `header`, và **KHÔNG** giả định chỉ có 1 dòng `header`. macOS
  dùng `mp.set_start_method("spawn")` (`<BD>/main.py:951`) → mọi process con re-import
  `sitecustomize` qua `PYTHONPATH` ⇒ **có thể có N dòng `header`**, thứ tự append giữa các process
  không được đảm bảo. Parser chỉ cần **≥1** dòng `header` hợp lệ.
- Dòng JSON hỏng (parse lỗi) → bỏ qua dòng đó + đếm vào `malformed_line_count`, **không** làm hỏng
  cả report (một dòng bị xé do ghi xen kẽ không được phép làm mù toàn bộ cơ chế).
- Header tồn tại để phân biệt **"cơ chế đo đã cài"** với **"không đo"**; record `page` tồn tại để
  phân biệt **"đã thật sự quan sát đủ trang"** với **"cài rồi nhưng không chạy"**. Hai câu hỏi
  khác nhau, hai bằng chứng khác nhau — xem 6.22.6.

**Version gate & fail-safe**: patch mới đăng ký bằng `_install_patch_hook(...)` **riêng**, module
đích `babeldoc.format.pdf.document_il.backend.pdf_creater`, hằng số module name mới
`_PDF_CREATER_MODULE_NAME`. Rollback **độc lập hoàn toàn** với patch `paragraph_finder` (Bug #7) và
patch `typesetting` (Bug #10) — đúng ràng buộc BA10.7 #1. Toàn bộ thân patched wrapper bọc
`try/except Exception` và **luôn** gọi hàm gốc: một lỗi trong observer không bao giờ được làm hỏng
việc render PDF.

**Cờ bật/tắt**: biến môi trường riêng `BABELDOC_SHIM_DROP_REPORT` (`"1"` = bật, mặc định **bật**),
tương ứng `Settings.babeldoc_drop_report_enabled: bool = True` và tham số
`BabeldocRunner.__init__(drop_report_enabled: bool = True)` — cùng pattern với
`word_wrap_fix_enabled` (`babeldoc_runner.py:260-268`). Patch chỉ có tác dụng khi shim tổng
(`line_split_shim_enabled`) cũng bật, vì `PYTHONPATH` do nó set.

#### 6.22.5. Data lineage (R6-01) — artifact nào, ai đọc field nào

| Bước | Tạo ra artifact | Bước sau đọc gì |
|---|---|---|
| 1. `BabeldocRunner.translate_pages()` trước khi spawn | tạo đường dẫn `drop_report_path = output_dir / f"{input_path.stem}.{page_range}.drops.jsonl"` — `output_dir` ở đây **chính là** `chunk_output_dir` của `_call_translator()` (ràng buộc bắt buộc, lý do ở 6.22.4 "Vị trí file"); tên file gắn `page_range` để 2 chunk chạy song song không ghi đè nhau. Set `env["BABELDOC_SHIM_DROP_REPORT_PATH"] = str(drop_report_path)` | subprocess babeldoc đọc biến môi trường này |
| 2. shim trong subprocess | **ghi thêm (append)** từng dòng JSON (`header` / `page` / `drop`) vào **đúng file đó** | bước 3 đọc **đúng file đó**, không phải stdout |
| 3. `BabeldocRunner` sau khi `process.wait()` | parse file → `BabeldocResult.drop_report: BabeldocDropReport` (**chưa lọc chồng lấn** — runner không biết gì về chunk plan) | bước 4 đọc `result.drop_report`, **không** tự mở lại file, **không** tự đọc `stdout` |
| 4. `JobOrchestrator._process_chunk()` | (4a) lọc `drop_report.dropped` xuống **dải trang sống sót** của chunk bằng `surviving_page_range(chunk, is_first_in_merge=chunk.chunk_index == 0)`; (4b) đối chiếu `drop_report.observed_pages` với dải trang mong đợi; (4c) map phần còn lại sang `list[LayoutQaFindingData]` | bước 5 nhận list này |
| 5. `persist_findings(db_session, findings, job_id=job.id, source_file=file_path.name)` | rows trong `layout_qa_findings` | **chưa có UI/API nào đọc bảng này** — xem 6.22.6 "Đường đọc (F4)" để biết BL-04 giao gì và KHÔNG giao gì |

`BabeldocDropReport` (dataclass, trong `src/services/babeldoc_runner.py`):

```python
@dataclass(frozen=True)
class BabeldocDroppedParagraph:
    page_number: int          # 1-based, tài liệu nguồn
    debug_id: str
    layout_label: str | None
    box: tuple[float, float, float, float] | None
    optimal_scale: float | None
    scale: float | None
    text_excerpt: str
    text_len: int

@dataclass(frozen=True)
class BabeldocDropReport:
    available: bool                              # False = KHÔNG đo được (không có dòng `header` hợp lệ nào)
    dropped: list[BabeldocDroppedParagraph]      # TOÀN BỘ record của lần chạy, CHƯA lọc chồng lấn
    observed_pages: frozenset[int]               # 1-based; từ record type="page" (F2)
    page_dropped_counts: dict[int, int]          # page_number_1based -> dropped_count đã khai báo
    header_count: int                            # >=1 là bình thường (spawn nhiều process)
    malformed_line_count: int
    stdout_sentinel_count: int                   # đối chiếu 1 chiều, xem 6.22.6
```

**KHÔNG có bước dedupe** (F9) — lý do ở 6.22.4 ("`debug_id` KHÔNG phải khoá dedupe").

##### 6.22.5.1. Lọc dải trang sống sót (F1) — bắt buộc, chống false positive + đếm 2 lần

**Vấn đề (có nguồn xác thực, đã tự đọc lại source 2026-09-11)**: `calculate_chunks(chunk_size=40,
overlap=2)` (`src/core/chunking.py:28-78`) sinh các chunk **chồng nhau 2 trang** — `1-40`, `39-80`,
`79-120`, … (`start = end - overlap + 1` tại `chunking.py:75`; chunk `idx > 0` có
`overlap_start = start`, `overlap_end = start + overlap - 1` tại `:60-61`). Nhưng
`merge_chunk_pdfs()` **vứt bỏ** phần đầu chồng lấn của mọi chunk sau chunk đầu:
`actual_start = chunk.overlap_end + 1` (`src/postprocess/chunk_merge.py:85-91`). Nghĩa là bản render
trang 39-40 **của chunk 1 không bao giờ có mặt trong file giao cho người dùng** — bản của chunk 0
mới là bản người dùng thấy.

Hệ quả nếu map **toàn bộ** `drop_report.dropped` sang finding:

1. **False positive**: drop ở trang 39 trong lần chạy của chunk 1 → finding "mất nội dung trang 39",
   trong khi trang 39 của file cuối là bản của chunk 0 và hoàn toàn bình thường. QA mở PDF soi tay
   thấy chữ vẫn còn ⇒ mất niềm tin vào chính cơ chế cảnh báo.
2. **Đếm 2 lần** khi cùng một đoạn drop ở cả 2 lần chạy.
3. Và hai lần chạy **không** nhất thiết cho cùng kết quả: `preprocess_document` ép `optimal_scale`
   của mọi đoạn xuống **mode của TẬP TRANG trong chính lần gọi đó** (`typesetting.py:919-935`, đã
   đọc trực tiếp: `statistics.multimode(all_scales)` trên `all_paragraphs` gom từ **mọi trang của
   `document`**, rồi hạ mọi giá trị lớn hơn mode). Chunk 0 (1-40) và chunk 1 (39-80) có tập trang
   khác nhau ⇒ mode khác nhau ⇒ cùng một đoạn ở trang 39 có thể fit ở chunk này và drop ở chunk kia.
   Đây **không** phải "trùng lặp vô hại" mà là **hai phép đo trên hai vật thể khác nhau**, chỉ một
   cái được giao cho người dùng.

Quy mô: 10/11 chunk × 2 trang = **20 trang/cuốn** nằm trong vùng rủi ro (đo trên job `1ee1fdee`,
418 trang, 11 chunk).

**Quy tắc chốt: chỉ tin kết quả của chunk mà bản render của nó SỐNG SÓT vào file cuối** — tức chunk
*đứng trước*. Với chunk `N > 0`, mọi record có `page_number < overlap_end + 1` bị **loại**, không
tạo finding.

**Vì sao loại mà KHÔNG để lại lỗ hổng quan sát** (điểm này phải nói rõ, nếu không sẽ có người tưởng
BL-04 tự bịt mắt mình): các dải sống sót **phủ kín và rời nhau** trên toàn tài liệu —
chunk 0 → `[1, 40]`, chunk 1 → `[41, 80]`, chunk 2 → `[81, 120]`, … hợp lại đúng `[1, total_pages]`.
Và mỗi chunk **quan sát** cả dải `[page_start, page_end]` ⊇ dải sống sót của chính nó. Nên mọi trang
vật lý của file cuối đều được đo **đúng một lần**, bởi đúng lần chạy đã tạo ra trang đó.

**Hàm dùng chung (bắt buộc — chống Bug #5 "hai bản sao lệch nhau")**:

```python
# src/core/chunking.py — cùng module định nghĩa luật chồng lấn (calculate_chunks)
class _ChunkLike(Protocol):          # structural typing: hợp cả ChunkPlan lẫn models.Chunk
    page_start: int | None           # None = chunk EPUB (xem ghi chú X2 dưới)
    page_end: int | None
    overlap_start: int | None
    overlap_end: int | None

def surviving_page_range(chunk: _ChunkLike, *, is_first_in_merge: bool) -> tuple[int, int]:
    """Dải trang 1-based (INCLUSIVE) của `chunk` thực sự có mặt trong file đã merge.
    `start > end` nghĩa là chunk không đóng góp trang nào.
    Raise ValueError nếu `page_start`/`page_end` là None (chunk EPUB không có dải trang)."""
```

⚠️ **Kiểu phải là `int | None`, không phải `int` (X2, 2026-09-11)**: `src/models/chunk.py:23-24`
khai `page_start: int | None` / `page_end: int | None` — **nullable từ 6.20.7** vì chunk EPUB dùng
`unit_start`/`unit_end` thay cho dải trang (comment lý do ngay tại `chunk.py:18-22`). Mà
`merge_chunk_pdfs(chunks: Sequence[Chunk])` truyền **chính model đó** vào hàm chung ⇒ khai `int`
trong Protocol là **khai sai sự thật**. Hôm nay chưa có bug runtime: đường EPUB rẽ sang
`run_epub_job()` ngay tại `job_orchestrator.py:457`, **không** đi qua `_process_chunk()` hay
`merge_chunk_pdfs()`. Nhưng hàm chung **phải `raise ValueError` tường minh** khi gặp `None` ("chunk
EPUB không có dải trang, không dùng được `surviving_page_range`") thay vì để `None + 1` nổ
`TypeError` ở một chỗ khác, mất dấu vết nguyên nhân.

Hai call site **bắt buộc** dùng chung hàm này:
- `merge_chunk_pdfs()` — thay khối `chunk_merge.py:85-91`, truyền `is_first_in_merge=(position == 0)`
  (giữ **nguyên** ngữ nghĩa hiện tại, không đổi hành vi);
- `_process_chunk()` (bước 4a ở trên) — truyền `is_first_in_merge=(chunk.chunk_index == 0)`.

⚠️ **Hàm chung sở hữu ĐÚNG quy tắc `start`, KHÔNG sở hữu quy tắc `end` (X3, 2026-09-11)** — nói rõ
để Dev không refactor quá tay. `merge_chunk_pdfs` hiện có **hai** quy tắc, không phải một:

| Quy tắc | Code hiện tại | Chuyển vào hàm chung? |
|---|---|---|
| **start**: `actual_start = chunk.overlap_end + 1` khi `position > 0` **và** `overlap_start is not None` **và** `overlap_end is not None` | `chunk_merge.py:85-91` | ✅ **CÓ** — đây là toàn bộ phạm vi của `surviving_page_range()` |
| **end**: kẹp theo `chunk_doc.page_count` của **file PDF thật** (2 nhánh full-document / chunk-scoped, Bug #7 vs Bug #8) | `chunk_merge.py:95-107` | ❌ **KHÔNG** — phụ thuộc file trên đĩa, một hàm thuần không thể biết. **Ở LẠI** `chunk_merge.py` |

Hệ quả bắt buộc cho Dev: **giữ nguyên** guard `overlap_start is not None and overlap_end is not None`
bên trong hàm chung. Bỏ guard ⇒ `merge_chunk_pdfs` đổi hành vi ở ca chunk có `overlap_* = None`,
trái cam kết "giữ nguyên hành vi" ngay trên.

⚠️ **Bất biến giữa 2 call site, phải được kiểm chứ không được giả định**: hai tham số trên chỉ trùng
nhau khi `position == chunk.chunk_index`, tức khi merge được gọi với **đủ** chunk, không thiếu chunk
nào. Hiện tại điều đó **đúng** — `job_orchestrator.py:693` gọi `await merge_chunk_pdfs(chunks, merged_path)`
với nguyên danh sách `chunks` của job (đã verify bằng đọc call site; job fail trước khi merge nếu có
chunk chưa `completed`). Vì đây là phụ thuộc vào code khác, `merge_chunk_pdfs()` **phải**
`logger.warning` khi `position != chunk.chunk_index` thay vì im lặng — cùng tinh thần với cảnh báo
"contributed 0 pages" đã có tại `chunk_merge.py:116-127`.

**Quan sát được chính bộ lọc**: `_process_chunk()` ghi `suppressed_overlap_count` (số record bị
loại) vào dòng log của 6.22.6 — để một bộ lọc quá tay không bao giờ im lặng.

⚠️ **Lỗi CÙNG LOẠI ở nhánh pdf2zh — KHÔNG sửa trong BL-04**: vòng `for page_num in range(chunk.page_start - 1, …)`
(`job_orchestrator.py:1901`) cũng không loại trang chồng lấn, nên `overflow_reports` của nhánh
pdf2zh cũng đang đếm 2 lần trên ~20 trang/cuốn. Đây là lỗi có sẵn từ BL-01, **không** thuộc phạm vi
BL-04, và §6.22.7 đã chốt "không đụng một dòng nào vào nhánh pdf2zh". Ghi nhận thành backlog
**BL-07** (khi nào sửa thì gần như miễn phí vì `surviving_page_range()` đã có sẵn).

#### 6.22.6. Ánh xạ sang record — dùng `LayoutQaFinding`, KHÔNG dùng `OverflowReport`

**Quyết định: KHÔNG tái dùng bảng `overflow_reports`.** Lý do (đúng yêu cầu "đừng bịa giá trị giả
cho field không đo được"):

| Field `OverflowReport` (`src/models/overflow.py`) | Babeldoc có cho biết không? |
|---|---|
| `font_size_original` | **KHÔNG** — không có khái niệm "cỡ chữ gốc của span" ở tầng này |
| `font_size_final` | **KHÔNG** — ca drop không có cỡ chữ cuối, vì không có lần vẽ nào |
| `scaling_applied` | **KHÔNG** — `paragraph.scale` là `None` chính xác ở ca drop (`typesetting.py:989`) |
| `still_overflow` | Sai ngữ nghĩa — babeldoc không tràn, nó **bỏ** |
| `block_index` | Không có khái niệm tương đương (`debug_id` là base58, không phải số thứ tự) |

Điền `0`/`None` vào 5 field trên chỉ để "dùng lại bảng cũ" sẽ tạo ra dữ liệu trông như đã đo mà thực
ra không đo — đúng loại mập mờ Protocol 5 sinh ra để chặn. Ngoài ra `overflow_reports` có nghĩa hợp
đồng rõ ràng "app đã co font ở đây" (US-05/BR-FONT-02), nghĩa đó **không còn hiệu lực trên nhánh
babeldoc** (design-log B9.7).

**Chọn `layout_qa_findings`** — đúng "nơi đặt tự nhiên" mà B9.7 đã đề xuất, đã có sẵn đường ghi
(`persist_findings`, `src/services/layout_qa.py:451-479`).

⚠️ **Đính chính (2026-09-11, Domain Expert F4)**: bản trước của mục này ghi thêm *"và đã có UI/QA
đọc"* — **SAI**. Đã tự chạy lại `grep -rln "LayoutQaFinding\|layout_qa_finding" src/ web/ scripts/ tests/`:
chỉ có **3 writer** (`src/postprocess/rotated_text_overlay.py`, `src/services/layout_qa.py`,
`src/services/mineru_det_probe.py`), phần còn lại là định nghĩa model/export + test. **0 route trong
`src/api/`, 0 file trong `web/`.** Xem "Đường đọc (F4)" cuối mục này để biết BL-04 giao gì.

| Field `LayoutQaFindingData` | Giá trị |
|---|---|
| `page_number` | `dropped.page_number` (**1-based** — khớp convention của `layout_qa.py:403` `page_number = index + 1`) |
| `check_type` | `BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK = "babeldoc_paragraph_drop_unfit"` — hằng số **khai báo trong `src/services/layout_qa.py`**, cùng chỗ với `ROTATED_OVERLAY_FLAG_CHECK`/`ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK`. Hậu tố `_unfit` là **bắt buộc**: cơ chế này chỉ đo kênh "không vừa khung", xem "Phạm vi đo được" dưới |
| `severity` | `"critical"` — **KHÔNG hardcode ở `job_orchestrator`**, phải tra `_SEVERITY_BY_CHECK[BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK]` (xem "Đăng ký severity" dưới). `critical` chứ không `blocker` vì không chặn release tự động; trọng số `_SEVERITY_WEIGHT` = 2 (`layout_qa.py:86`), đủ để trang đó nổi lên đầu `page_queue` |
| `detail` | dict giữ **nguyên vẹn** phần còn lại: `{"cause": "typeset_unfit", "debug_id", "layout_label", "box", "optimal_scale", "scale", "text_excerpt", "text_len", "source": "babeldoc_shim/v2"}`. `"cause"` là **bắt buộc** — nó khoá ngữ nghĩa lại đúng phạm vi ngay cả khi ai đó sau này đổi tên `check_type` |

**Đăng ký severity ở một nguồn sự thật duy nhất (F6)**: `src/services/layout_qa.py:76-84`
(`_SEVERITY_BY_CHECK`) là ánh xạ `check_type → severity` duy nhất đang có, và **mọi** `check_type`
hiện hữu đều nằm trong đó. BL-04 **thêm 3 khoá mới vào chính dict đó** — `babeldoc_paragraph_drop_unfit`
→ `"critical"`, `babeldoc_drop_report_unavailable` → `"major"`, `babeldoc_drop_report_incomplete` →
`"major"` — và `job_orchestrator` **tra dict**, không tự điền chuỗi severity. Hai nguồn sự thật cho
cùng một ánh xạ là cách chắc chắn để chúng lệch nhau.

⚠️ **Đính chính danh sách `check_type` (F6)**: bản trước liệt kê 5 giá trị (`overlap`,
`text_over_drawing`, `text_over_image`, `rotated_text_prescan`, `entity_loss`) — **thiếu 2**. Danh
sách đúng, đọc trực tiếp `layout_qa.py:76-84` ngày 2026-09-11, là **7** giá trị: 5 giá trị trên,
cộng `rotated_text_overlay_flag` (`layout_qa.py:66`, `"blocker"`) và `rotated_text_scan_unsupported`
(`layout_qa.py:74`, `"blocker"`). Điều này quan trọng vì `rotated_text_overlay_flag` chính là giá
trị **duy nhất** thực sự có trong DB hiện tại (221 row) — lập luận "`check_type` khác nhau nên
không lẫn nhau" ở 6.22.7 phải đứng trên danh sách đầy đủ, không phải danh sách nhớ nhầm.

⚠️ **Lệch convention đã biết, KHÔNG sửa trong hạng mục này**: `OverflowReport.page_number` hiện là
**0-based** (`font_shrink.py:194`, `:272` dùng `page.number` của PyMuPDF) trong khi
`LayoutQaFinding.page_number` là **1-based**. Thiết kế này theo 1-based cho khớp bảng nó ghi vào.
Việc thống nhất 2 bảng là một backlog riêng, đụng vào dữ liệu lịch sử của nhánh pdf2zh — ghi nhận,
không gộp vào đây.

**BỐN trạng thái, không phải ba** (đây là điểm dễ sai nhất của cả thiết kế; bản trước chỉ có 3 —
trạng thái "cài rồi nhưng không chạy đủ trang" bị gộp nhầm vào trạng thái 1, xem F2):

Ký hiệu: `expected_pages = set(range(chunk.page_start, chunk.page_end + 1))`;
`observed_pages` = tập `page_number_1based` của các record `type="page"`;
`surviving = surviving_page_range(chunk, …)` (6.22.5.1).

| # | Trạng thái | Điều kiện | Hành vi |
|---|---|---|---|
| 1 | **Đo được, trọn vẹn, không có drop** | ≥1 `header` hợp lệ **VÀ** `observed_pages == expected_pages` **VÀ** `checksum_mismatch_pages` rỗng **VÀ** 0 record `drop` trong dải `surviving` | ghi 0 finding. Đây là tin tốt **thật** — nhưng chỉ trong phạm vi ở "Phạm vi đo được" dưới |
| 2 | **Đo được, trọn vẹn, có drop** | ≥1 `header` **VÀ** `observed_pages == expected_pages` **VÀ** `checksum_mismatch_pages` rỗng **VÀ** N record `drop` trong dải `surviving` | ghi N finding `babeldoc_paragraph_drop_unfit` |
| 3 | **Đo được nhưng KHÔNG TRỌN VẸN** (thiếu trang **hoặc** lệch checksum) | ≥1 `header` **VÀ** (`observed_pages != expected_pages` **HOẶC** `checksum_mismatch_pages` khác rỗng — X5, xem ghi chú "Checksum chéo" dưới) | vẫn ghi các finding drop **đã** quan sát được (trạng thái 2 áp dụng cho phần đã đo), **CỘNG** đúng **1** finding `check_type="babeldoc_drop_report_incomplete"`, `severity="major"` (tra `_SEVERITY_BY_CHECK`), `page_number = chunk.page_start`, `detail={"expected": sorted(expected_pages), "observed": sorted(observed_pages), "missing": sorted(expected - observed), "unexpected": sorted(observed - expected), "checksum_mismatch_pages": [...]}` |
| 4 | **KHÔNG đo được** | file không tồn tại, rỗng, hoặc **không có dòng `header` hợp lệ nào** (shim tắt / version babeldoc ≠ 0.6.4 / patch fail) | `available=False`. Ghi **1** finding `check_type="babeldoc_drop_report_unavailable"`, `severity="major"`, `page_number = chunk.page_start`, `detail={"reason": ...}`. **KHÔNG** ghi finding drop nào |

Trạng thái 3 và 4 **không được** im lặng quy về "0 drop" — đó chính là kiểu silent failure của
Bug #5.

**Vì sao trạng thái 3 phải tách riêng (F2)**: dòng `header` được ghi lúc **import module**
(`_PatchingLoader.exec_module`, `sitecustomize.py:626-637`), tức **trước khi render bất cứ trang
nào**. Nên `available=True` chỉ chứng minh *"module `pdf_creater` đã được import và patch không ném
lỗi"* — nó **không** chứng minh `create_render_units_for_page` đã thật sự chạy trên trang nào. Không
có trạng thái 3, hệ thống sẽ báo *"đo được, 0 drop"* trong tình huống patch cài xong nhưng hook
không chạy đủ trang (babeldoc đổi đường gọi ở bản sau; một exception trong `write()` cắt ngang vòng
`for page in self.docs.page`) — **tin tốt giả**, đúng hình dạng Bug #5.

Ta **biết trước** tập trang phải quan sát, không phải suy đoán: `ActiveILCreater.create_il()` lọc
`self.docs.page` xuống đúng các trang thoả `should_translate_page(page.page_number + 1)`
(`<BD>/format/pdf/document_il/frontend/il_creater_active.py:239-245`, đã đọc trực tiếp
2026-09-11 — **không** phải `il_creater.py`, xem self-correction R5-05 ở 6.22.1), và
`BabeldocRunner` luôn truyền `page_range=f"{chunk.page_start}-{chunk.page_end}"`
(`job_orchestrator.py:1806`). ⇒ `expected_pages` là một con số xác định, kiểm được.

**Checksum chéo trong chính file sidecar**: với mỗi trang, `page.dropped_count` phải bằng số record
`drop` của trang đó. Lệch → tên trang vào `detail["checksum_mismatch_pages"]` của finding trạng thái
3 (một dòng bị xé/mất khi ghi sẽ lộ ra ở đây thay vì âm thầm làm giảm số finding).

⚠️ **Checksum PHẢI luôn có chỗ đi — kể cả khi đủ trang (X5, 2026-09-11)**: bản trước gắn
`checksum_mismatch_pages` **chỉ** vào finding trạng thái 3, mà trạng thái 3 lại **chỉ** kích hoạt
khi `observed_pages != expected_pages`. Ca đáng lo nhất của checksum là ca **ngược lại**: đủ trang
(`observed == expected`) nhưng một dòng `drop` bị xé/mất ⇒ `page.dropped_count = 3` mà chỉ parse
được 2 dòng `drop`. Khi đó không có finding nào để gắn vào, hệ thống rơi về **trạng thái 2 với số
finding ÍT HƠN sự thật** — đúng loại "giảm âm thầm" mà chính checksum sinh ra để chặn.

⇒ **Điều kiện trạng thái 3 được mở rộng thành**:
`observed_pages != expected_pages` **HOẶC** `checksum_mismatch_pages` khác rỗng
(bảng bốn trạng thái ở trên đọc theo điều kiện này). Khi kích hoạt vì vế thứ hai, `detail` vẫn
đúng shape cũ — `missing`/`unexpected` sẽ là list rỗng, và `checksum_mismatch_pages` là thứ mang
thông tin. Ngoài ra `checksum_mismatch=K` là trường **bắt buộc** trong định dạng log R-1 (6.22.6.1),
để con số này không bao giờ biến mất khỏi mọi mặt hiển thị.

**Đối chiếu chéo (`stdout_sentinel_count`) — CHỈ MỘT CHIỀU (F5)**: `BabeldocRunner` đếm số lần xuất
hiện cụm `Unable to export paragraphs that have not yet been formatted` trong `stdout + "\n" + stderr`
— dùng được vì runner đã ép `COLUMNS=200` (`babeldoc_runner.py:374`, đo thật ở 6.22.3(a)). Ghi thêm
1 finding `check_type="babeldoc_drop_report_mismatch"`, `severity="minor"`, `detail={"sentinel": n,
"structured": m}` **chỉ khi `stdout_sentinel_count > len(dropped_before_overlap_filter)`** — tức chỉ
theo chiều hàm ý *shim bỏ sót*.

⚠️ **Không được dùng `!=`**: `main.py:944` gọi `speed_up_logs()`, thay handler gốc bằng `QueueHandler`
trên một `EvictQueue(1000)` **tự vứt bớt** bản ghi khi đầy (`main.py:895-903`, biến đếm
`self.discarded`). Sentinel **≤** structured là hành vi thiết kế của chính babeldoc, không phải lỗi;
dùng `!=` sẽ sinh finding rác một cách hệ thống mỗi khi log dồn — đúng loại báo động giả mà một cờ
QA không được phép mắc.

⚠️ **Giới hạn của phép đối chiếu này — phải nói rõ, đừng để ai tưởng đây là phép đo độc lập**:
`logger.error` tại `pdf_creater.py:831` nằm **bên trong** `render_paragraph_to_char`, mà hàm đó được
gọi **từ chính** `create_render_units_for_page` (`pdf_creater.py:852`) — cùng call site, cùng dữ
liệu, cùng thời điểm. Nó chỉ bắt được **sai lệch predicate** (`_has_rendered_chars` lệch khỏi định
nghĩa của babeldoc), **không** bắt được "hook không chạy" — đó là việc của trạng thái 3. Thêm nữa,
đo thật trên job `1ee1fdee` (418 trang) chỉ có **1** ca drop trong toàn tài liệu ⇒ trong thực tế
phép đối chiếu này gần như luôn là `0 == 0` và kiểm được rất ít. **Không đầu tư thêm vào nó.**

##### 6.22.6.1. Phạm vi đo được — "0 drop" KHÔNG có nghĩa "không mất nội dung" (F3)

Đây là mục **quan trọng nhất** của cả §6.22 về mặt trung thực dữ liệu. Tên cũ
`babeldoc_paragraph_drop` (và tiêu đề §6.22 "babeldoc TỰ bỏ đoạn") hứa nhiều hơn thứ cơ chế này đo
được.

babeldoc có **ít nhất 3 kênh** làm mất nội dung. Thiết kế này quan sát **đúng 1 kênh**:

| Kênh | Cơ chế | Nguồn xác thực | §6.22 có đo? |
|---|---|---|---|
| **(1)** Không vừa khung sau khi đã bóp tới `min_scale = 0.1` | composition bị xoá trắng trước typeset, chỉ ghi lại khi `all_units_fit` ⇒ đoạn biến mất | `typesetting.py:1277-1280`, `:986-1002`, `:1064-1076` | ✅ **CÓ** — đây chính là cái §6.22 thiết kế |
| **(2)** **Lọc theo góc xoay lúc parse** | `ActiveILCreater.project_native_char`: `rotation_angle = get_rotation_angle(char.matrix)`; nếu **không** thuộc `[-0.1, 0.1] ∪ [89.9, 90.1]` thì `return` ⇒ ký tự **không bao giờ** trở thành `PdfCharacter`, không thuộc paragraph nào | `<BD>/format/pdf/document_il/frontend/il_creater_active.py:1295-1297` (trong `project_native_char`, `:1292`; đã đọc trực tiếp 2026-09-11) | ❌ **KHÔNG** — không có paragraph nào để mà "rỗng"; sentinel ở `pdf_creater.py:831` cũng không kêu |
| **(3)** Ký tự không có font id | `ActiveILCreater.project_native_char`: `if char.aw_font_id is None: return` | `il_creater_active.py:1293-1294` | ❌ **KHÔNG** — cùng lý do |

⚠️ **Địa chỉ trong bảng trên đã được sửa 2026-09-11 (R5-05, Domain Expert X1)**: bản trước trỏ vào
`ILCreater.on_lt_char` (`il_creater.py:969-974`) — **class đó không chạy trong luồng dịch**, xem
6.22.1. Predicate là **y hệt** nên kết luận "kênh (2)/(3) không được §6.22 đo" **không đổi**; chỉ
địa chỉ đổi. Ở `ActiveILCreater`, `on_lt_char` (`:1423-1427`) chỉ là **vỏ** gọi
`project_native_char` — ai định patch phải patch `project_native_char`, không phải `on_lt_char`.

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

**Hệ quả phải ghi thẳng vào hợp đồng — không được mập mờ**:

> `babeldoc_paragraph_drop_unfit` = 0 chỉ có nghĩa **"không có đoạn nào bị bỏ vì không vừa khung
> trong dải trang đã quan sát"**. Nó **KHÔNG** có nghĩa "chunk này không mất nội dung". Ký tự bị lọc
> ở `ActiveILCreater.project_native_char` (góc xoay ngoài ≈0°/≈+90°, hoặc thiếu `aw_font_id`) **không bao giờ đi
> qua điểm quan sát của §6.22** — kênh đó thuộc trách nhiệm của `overlay_rotated_text` (§U3–U7), và
> đã đo được rằng nó không phủ hết. Chunk 0 của Le Cordon Bleu là ví dụ sống: **0 drop theo kênh
> (1)**, nhưng **mất 2 tiêu đề chương thật** theo kênh (2).

**Ràng buộc hình thức chống mập mờ (bắt buộc, không phải khuyến nghị)**: mọi nơi hệ thống phát ra
con số này — dòng log 6.22.6.2, `detail` của finding, báo cáo QA — **không được phép** phát ra chuỗi
"0 drop" trần. Định dạng bắt buộc là dạng có mẫu số **và** có phạm vi, ví dụ:

```
babeldoc drop report: job=<id> chunk=<i> pages=199-240 observed=42/42
  unfit_drops=0 (surviving 201-240, suppressed_overlap=0, checksum_mismatch=0)
  — PHAM VI: chi do kenh "khong vua khung"; chu bi loc o
    ActiveILCreater.project_native_char (xoay/thieu font id) KHONG duoc do boi
    co che nay (Architecture.md 6.22.6.1)
```

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

##### 6.22.6.2. Đường đọc: ai thật sự nhìn thấy finding này (F4)

**Sự thật hiện tại, đã grep lại 2026-09-11**: `layout_qa_findings` có 3 writer, **0 reader**. Ghi
một finding `critical` "mất nội dung thật" vào một bảng SQLite mà không lộ trình nào của con người
chạm tới ≈ vẫn **không** có cờ cảnh báo — chỉ khác là từ nay tồn tại một *niềm tin* rằng nó đã tồn
tại. Với tần suất đo được (**1 row/cuốn 418 trang**), không ai soi tay ra được row đó. Bằng chứng:
job `1ee1fdee` mất trọn một đoạn sidebar **614 ký tự** ở trang 230, `layout_qa_findings` = 0 row,
`overflow_reports` = 0 row, `status = completed`.

**BL-04 giao — và CHỈ giao — đường đọc tối thiểu sau** (đủ để không ai phải tự query DB mới biết):

| # | Nơi | Nội dung |
|---|---|---|
| R-1 | `_process_chunk()`, ngay sau `persist_findings(...)` | `logger.warning` **1 dòng/chunk** theo đúng định dạng bắt buộc ở 6.22.6.1 (có `observed=x/y`, `unfit_drops=N`, `suppressed_overlap=K`, `checksum_mismatch=M` (X5), và câu PHAM VI). Mức `WARNING` khi `N > 0` hoặc trạng thái 3/4; `INFO` khi trạng thái 1 |
| R-2 | `run_job()` Bước 10, **trước** khi gán `job.status = "completed"` (`job_orchestrator.py:807`) | `logger.warning` **1 dòng/job** tổng hợp: tổng số finding `babeldoc_*` của job này, lấy bằng **đúng 1 câu `SELECT COUNT(...)` chạy trực tiếp trên DB** (chi tiết + lý do bắt buộc ngay dưới bảng), kèm câu PHAM VI. `N == 0` → `INFO` |
| R-3 | `docs/test-report.md` (QA ghi mỗi đợt) | câu SQL dán được: `SELECT page_number, check_type, severity, detail FROM layout_qa_findings WHERE job_id = '<id>' AND check_type LIKE 'babeldoc_%' ORDER BY page_number;` |

**R-2 PHẢI đếm từ DB, KHÔNG được đếm từ list in-memory tích luỹ qua `_process_chunk()`** (ràng buộc
bắt buộc — Domain Expert X7, 2026-09-11; bản trước của mục này ghi ngược lại là *"đếm từ list đã
map, không query lại DB"* và đó là **sai hướng an toàn**):

```python
# run_job() Bước 10, ngay TRƯỚC `job.status = "completed"` (job_orchestrator.py:807)
babeldoc_finding_count = (
    await db_session.exec(
        select(func.count())
        .select_from(LayoutQaFinding)
        .where(LayoutQaFinding.job_id == job.id)
        .where(col(LayoutQaFinding.check_type).like("babeldoc_%"))
    )
).one()
```

(`job_orchestrator.py:31` hiện chỉ `from sqlmodel import select` ⇒ Dev cần thêm `func`/`col` và
import `LayoutQaFinding` từ `src/models/layout_qa.py:11`. Shape câu query trên là **spec**, không
phải code đã chạy — Dev khớp với style query sẵn có trong file nếu khác.)

Lý do có nguồn xác thực (đã tự đọc lại source 2026-09-11):
- `_process_chunk()` trả về `None` (`job_orchestrator.py:1733-1743`) ⇒ muốn đếm in-memory thì phải
  thêm accumulator mới, tức thêm một sợi lineage mới chỉ để phục vụ một dòng log.
- Vòng Bước 7 (`job_orchestrator.py:576-577`) **bỏ qua** chunk đã xong: `if chunk.status != "completed":`.
  ⇒ Job **resume sau crash**: các chunk hoàn tất ở lần chạy trước **đã ghi finding vào DB** nhưng
  **không** đi qua `_process_chunk()` lần này ⇒ accumulator in-memory rỗng cho chúng ⇒ R-2 in ra con
  số **NHỎ HƠN sự thật**, đúng ở kịch bản rủi ro cao nhất (job từng crash).
- R-2 là **mặt hiển thị DUY NHẤT** của BL-04 (không có UI/API — xem "BL-04 KHÔNG giao" dưới). Một
  mặt hiển thị duy nhất mà **báo ít hơn sự thật** là hướng sai tệ nhất có thể chọn: nó tạo **an toàn
  giả**, cùng hình dạng với Bug #5 ("status = completed" nhưng output rỗng).
- Chi phí bằng không: chạy **đúng 1 lần/job**, tại bước hoàn tất. Và nó dùng **cùng một nguồn sự
  thật** với câu SQL R-3 đã giao cho QA — một nguồn, không hai.

**Hệ quả về ngữ nghĩa con số**: vì đếm từ DB, `N` của R-2 là **tổng của cả job qua mọi lần chạy**,
đúng như tên gọi hứa. Nếu Dev vì lý do nào đó **không** thực hiện được câu query này, **không được**
giữ nguyên nhãn "tổng của job" cho một con số của riêng lần chạy — khi đó bắt buộc đổi tên trường
thành `unfit_drops_this_run=` và thêm `skipped_completed_chunks=K`, rồi escalate cho Tech Lead.

**BL-04 KHÔNG giao** (ghi rõ để không ai ngụ ý ngược lại): không có route API, không có badge UI,
không có cột mới trong `JobDetail`. Đó là backlog **BL-09** — thêm `layout_qa_finding_counts` vào
response `GET /api/jobs/{job_id}` (`src/api/routes/jobs.py:702-717`, hiện `_to_detail()` là hàm
thuần từ 1 row `Job` nên phải thêm 1 query) + badge ở `web/`. **Giới hạn đã biết của BL-04: cảnh báo
chỉ tới được người đọc log server, chưa tới được người dùng qua UI.**

#### 6.22.7. Audit Protocol 8 (R8-01/02/03) — từng bước hậu kỳ hiện có

Thêm một bước hậu kỳ mới vào `_process_chunk()`, nên phải trả lời cho **từng** bước đang có, kể cả
bước cũ:

| Bước hậu kỳ hiện có | Tồn tại để giải quyết vấn đề gì | Bước mới (đọc drop report) có liên quan không |
|---|---|---|
| `font_shrink_page()` (`job_orchestrator.py:1893-1905`) | pdf2zh vẽ bản dịch ở đúng cỡ/vị trí bản gốc EN → tràn khung | **Không đụng vào.** Gate `self._needs_font_shrink` giữ nguyên 100%. Bước mới **không** bật lại nó |
| Vòng ghi `OverflowReport` (`:1907-1920`) | persist kết quả đo của `font_shrink_page` | **Không đụng vào.** B9.5 cố ý giữ list rỗng + vòng lặp 0 vòng; bước mới ghi vào bảng **khác** (`layout_qa_findings`), đường đi song song, không chia sẻ code |
| `overlay_rotated_text` + `persist_findings` (`:725-770`) | babeldoc bỏ chữ **xoay** — nguyên nhân gốc là bộ lọc góc xoay ở `il_creater_active.py:1295-1297` (`ActiveILCreater.project_native_char`; địa chỉ đã sửa 2026-09-11 theo R5-05, xem 6.22.1), tức **kênh (2)** ở 6.22.6.1 | **Cùng họ vấn đề nhưng KHÁC KÊNH**, và chạy ở **cấp job trên `merged_path`**, còn bước mới chạy ở **cấp chunk**. Dùng chung `persist_findings()` — đúng ý B9.7 — và `check_type` khác nhau (danh sách đầy đủ 7 giá trị hiện có đã đính chính ở 6.22.6) nên không lẫn row. ⚠️ **Hai bước KHÔNG cộng lại thành phủ kín**: đo thật trên job `1ee1fdee` cho thấy trang 19/31 mất chữ xoay mà overlay không khôi phục **và** không để lại finding nào (6.22.6.1) — đó là backlog BL-08, không phải phạm vi BL-04 |
| `compress_pdf_images` (`:776-777`) | giảm dung lượng ảnh raw của output babeldoc | Không liên quan. Chạy sau merge; drop report chỉ đọc file JSONL, không đọc PDF |
| `merge_chunk_pdfs` | ghép chunk **và vứt bỏ phần đầu chồng lấn** của mọi chunk sau chunk đầu (`chunk_merge.py:85-91`) — vì `calculate_chunks` cố ý cho 2 chunk liền kề chồng nhau 2 trang làm context | ⚠️ **CÓ LIÊN QUAN — bản audit trước đánh giá SAI**. Bản trước ghi "không liên quan vì số trang đã là số trang tài liệu nguồn": đúng về **đơn vị đo**, nhưng bỏ sót rằng **bản render của 2 trang chồng lấn bị vứt đi**, nên drop báo trên chúng là false positive + đếm 2 lần. Thiết kế đã sửa: bộ lọc `surviving_page_range()` dùng **chung hàm** với `merge_chunk_pdfs` (6.22.5.1) |
| `_call_translator()` `shutil.rmtree(chunk_output_dir)` đầu mỗi attempt (`:1801-1802`) | pdf2zh/babeldoc ghi đè lên file cũ của attempt trước → trang dịch lặp 2 lần (bug 2026-09-05) | **Có liên quan, và là điều kiện đúng đắn cho BL-04**: nhờ bước này, sidecar đặt **trong** `chunk_output_dir` được xoá sạch trước mỗi attempt ⇒ record của attempt hỏng không bị cộng vào attempt thành công. Ràng buộc đã ghi vào hợp đồng ở 6.22.4 ("Vị trí file"), không để Dev tự suy ra |

**R8-03 — capability, không rẽ nhánh theo tên engine**: khai báo trên chính runner, đối xứng với
`needs_font_shrink`:

```python
# src/services/babeldoc_runner.py, class BabeldocRunner
    #: BL-04 (Architecture.md 6.22). babeldoc tự bỏ hẳn đoạn không vừa khung
    #: (6.22.2) — app không đo được bằng hậu kỳ, phải lấy tín hiệu từ chính nó.
    reports_own_paragraph_drops: ClassVar[bool] = True

# src/services/pdf2zh_runner.py, class Pdf2zhRunner
    #: BL-04. pdf2zh không bỏ đoạn (nó vẽ tràn — đó là lý do `needs_font_shrink`
    #: tồn tại), và không có kênh báo cáo tương đương. Không có gì để đọc.
    reports_own_paragraph_drops: ClassVar[bool] = False
```

`_process_chunk()` đọc capability qua property `_reports_own_paragraph_drops`, **cùng khuôn** với
`_needs_font_shrink` (`job_orchestrator.py:412-431`) — **bao gồm cả guard
`isinstance(value, bool)`** với thông điệp lỗi tương tự. Guard này là bắt buộc, không phải phòng thủ
thừa: `AsyncMock(spec=...)` chỉ copy TÊN thuộc tính chứ không copy GIÁ TRỊ, nên thiếu guard thì một
test babeldoc quên set thuộc tính sẽ chạy nhầm nhánh và vẫn PASS (xem B9.4).

**R8-02 (deny-by-default)**: nếu sau này có engine thứ ba, mặc định của
`reports_own_paragraph_drops` khi chưa verify là `False` — không đọc, không ghi finding, thay vì
"cứ đọc thử xem có gì không".

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

### 6.23. BL-10 — Chi phí ĐO THẬT cho nhánh PDF/babeldoc (`cost_source = 'metered'`)

> **Mục đích**: `chunks.api_tokens_used` / `chunks.api_cost` của job PDF hiện là **ước lượng**
> (`estimate_chunk_cost()`, §6.6.6) với sai số công bố ±30–50%, và `jobs.cost_source` **luôn**
> `'estimated'` — chưa từng có job PDF nào `'metered'`. babeldoc 0.6.4 **tự đếm token thật từ
> `response.usage`** và in ra stdout cuối mỗi lần chạy CLI; app **đã capture sẵn** stdout đó và đã
> có tiền lệ parse nó (`RATE_LIMIT_LINE_RE`, `drop_sentinel_count`). Section này biến số thật đó
> thành `cost_source='metered'` cho **đúng chunk dịch bằng babeldoc**, giữ nguyên `'estimated'`
> cho pdf2zh.
>
> **Phạm vi**: KHÔNG sửa bảng giá `deepseek_provider.py` (xem "Giới hạn đã biết" 6.23.8 — quyết
> định của Hiếu: bảng giá xử lý ở task riêng). KHÔNG động tới `estimate_chunk_cost()`,
> `estimate_job_cost_v2()`, pre-flight gate (Lớp 2), hay nhánh EPUB (đã `'metered'` từ §6.20).

#### 6.23.1. Nguồn xác thực (Protocol 5 R5-01 + R5-05)

Package đã cài: `~/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`
(gọi tắt `$BD`), **`babeldoc --version` → `babeldoc 0.6.4`** (chạy thật 2026-09-11, cùng version
đã verify ở §6.14.1/§6.22.1 — không kế thừa mù, đã chạy lại lệnh `--version`).

| # | Nguồn | Xác nhận điều gì |
|---|---|---|
| T1 | `$BD/translator/translator.py:260-263` — `self.token_count = AtomicInteger()`, `prompt_token_count`, `completion_token_count`, `cache_hit_prompt_token_count` | babeldoc có 4 bộ đếm token **cấp translator**, cộng dồn toàn tiến trình |
| T2 | `$BD/translator/translator.py:345-364` — `def update_token_count(self, response)`: `self.token_count.inc(response.usage.total_tokens)`, `.prompt_tokens`, `.completion_tokens`, và `hit_count` lấy từ `response.usage.prompt_cache_hit_tokens` (DeepSeek) **hoặc** `response.prompt_tokens_details.cached_tokens` | Số đếm là **token THẬT do API trả về**, không phải ước lượng theo độ dài. Toàn khối bọc `try/except` → lỗi đếm không làm hỏng dịch |
| T3 | `$BD/translator/translator.py:275-282` — trong `do_translate()`: `response = self.client.chat.completions.create(...)` rồi `self.update_token_count(response)` (tương tự trong `do_llm_translate()`) | Mọi lời gọi LLM dịch đều đi qua bộ đếm, không có đường vòng |
| T4 | `$BD/main.py:772-784` — sau vòng `for file in pending_files:` (`main.py:683`): `logger.info(f"Total tokens: {translator.token_count.value}")`, `Prompt tokens:`, `Completion tokens:`, `Cache hit prompt tokens:`, và `"Term extraction tokens: total=%s prompt=%s completion=%s cache_hit_prompt=%s"` | 5 dòng tổng kết in **một lần cho mỗi tiến trình** (ngoài vòng lặp file), **không** in mỗi file |
| T5 | `$BD/main.py:524` — `term_extraction_translator = translator`, chỉ tách thành object riêng khi có `--openai-term-extraction-model/-base-url/-api-key` (`main.py:525-545`); `main.py:785` — dòng log thứ 6 chỉ in `if term_extraction_translator is not translator` | App **không** truyền 3 flag đó ⇒ term-extraction dùng CHÍNH translator ⇒ token term-extraction (nếu có) **đã nằm trong** `Total tokens`. **Không được cộng thêm** dòng `Term extraction tokens:` vào tổng — sẽ đếm 2 lần |
| T6 | `$BD/main.py:918-920` — `from rich.logging import RichHandler` + `logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])`, **không truyền `format=`** ⇒ dùng `logging.BASIC_FORMAT` = `"%(levelname)s:%(name)s:%(message)s"` | Giải thích vì sao message thật có tiền tố `INFO:babeldoc.main:` **bên trong** cột message của rich (level hiển thị 2 lần) |
| T7 | **Chạy thật, non-tty** (Tech Lead, 2026-09-11): `COLUMNS=200 ~/.local/share/uv/tools/babeldoc/bin/python -c "<dựng lại đúng 2 dòng main.py:918-920, logger 'babeldoc.main'>" > f 2>/dev/null`, in `repr()` của file → `'[09/11/26 16:01:42] INFO     INFO:babeldoc.main:Total tokens: 123456' + <padding khoảng trắng> + '<string>:6\n'` | **Định dạng dòng thật khi redirect non-tty đã verify sống**: có timestamp + `INFO` + `INFO:babeldoc.main:` + message + cột nguồn bên phải; số nguyên **không có dấu phân cách nghìn** (f-string trên `int`) |
| T8 | `src/services/babeldoc_runner.py:523` — `env = {**os.environ, **service.envs, "COLUMNS": "200"}`; `:568-570` — `stdout = bytes(stdout_buf).decode(...)`; `:574` `rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))`; `:577` `drop_sentinel_count = (stdout + "\n" + stderr).count(_DROP_SENTINEL_TEXT)` | stdout **đã được capture nguyên vẹn** và **đã có 2 tiền lệ parse** trên chính chuỗi đó; `COLUMNS=200` đã được set sẵn (tiền đề chống rich wrap — xem 6.23.2) |
| T9 | `src/core/job_orchestrator.py:2055-2077` — `await self._translator_runner.translate_pages(...)` nằm trong `_call_translator()` của `_process_chunk()`, gọi **1 lần cho mỗi chunk**; mỗi lần là **1 subprocess babeldoc riêng** | Tổng token in ra cuối mỗi tiến trình ứng **1-1 với đúng chunk đó**. Đây là điều khiến cách này đúng mà không cần metering proxy (§6.6.6 v1.1) |
| T10 | `$BD/main.py:620,683` — `for file in args.files:` (lọc) rồi `for file in pending_files:` (chạy); app truyền **đúng 1** `--files` (`babeldoc_runner.py`, §6.14.2) | Trong pipeline của app, `Total tokens` = token của riêng 1 file = riêng 1 chunk. Vẫn lấy **match CUỐI CÙNG** để phòng thủ (6.23.2) |
| T11 | §6.6.6 (hợp đồng hiện hành, từ Increment 1): *"pdf2zh khong xuat token usage ra stdout/stderr"*; `Pdf2zhResult` không có field token nào | pdf2zh **không** có gì để parse ⇒ `reports_token_usage = False`, giữ nguyên `'estimated'` — đây cũng là mặc định deny-by-default của R8-02, không cần verify thêm để được phép SKIP |

**⚠️ ASSUMED — chưa verify với nguồn thật** (chặn Dev ở đúng phần này, xem R5-02 ở 6.23.7):
- ⚠️ **ASSUMED**: dòng `Total tokens:` **thật sự xuất hiện** trong stdout của một lần chạy babeldoc
  **qua pipeline của app** (subprocess, có `--no-auto-extract-glossary`, có `--pages`). Đã verify:
  code in ra nó vô điều kiện (T4) và định dạng dòng khi non-tty (T7, dựng lại đúng cấu hình
  logging của babeldoc). **Chưa verify**: một lần chạy babeldoc end-to-end thật với API key thật
  rồi grep stdout — Tech Lead không chạy để tránh tốn tiền/thời gian ngoài phạm vi thiết kế.
  R5-02 giao đúng việc này cho Dev **trước khi** viết regex chính thức.
- ⚠️ **ASSUMED**: với DeepSeek, `total_tokens == prompt_tokens + completion_tokens`. T2 chỉ chứng
  minh 3 con số đến từ 3 field khác nhau của `response.usage`, **không** chứng minh quan hệ cộng.
  Thiết kế **không phụ thuộc** vào đẳng thức này (6.23.4 chỉ log WARNING khi lệch, không đổi hành
  vi) — ghi ở đây để không ai âm thầm dựa vào nó sau này.

#### 6.23.2. Hợp đồng parse — `parse_babeldoc_token_usage(stdout)` (spec cho Dev)

Module: **`src/services/babeldoc_runner.py`** (cùng chỗ với 2 tiền lệ parse hiện có, không tạo
module mới).

```python
#: 6.23.1 T4/T6/T7 — VERIFIED. Tiền tố `INFO:babeldoc.main:` là phần message
#: THẬT (logging.BASIC_FORMAT của basicConfig, main.py:918-920), không phải
#: cột hiển thị của rich → neo vào nó là neo vào thứ ổn định nhất có được.
_TOKEN_LINE_RES: dict[str, re.Pattern[str]] = {
    "total_tokens": re.compile(r"INFO:babeldoc\.main:Total tokens:\s*(\d+)"),
    "prompt_tokens": re.compile(r"INFO:babeldoc\.main:Prompt tokens:\s*(\d+)"),
    "completion_tokens": re.compile(r"INFO:babeldoc\.main:Completion tokens:\s*(\d+)"),
    "cache_hit_prompt_tokens": re.compile(
        r"INFO:babeldoc\.main:Cache hit prompt tokens:\s*(\d+)"
    ),
}


@dataclass(frozen=True)
class BabeldocTokenUsage:
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cache_hit_prompt_tokens: int


def parse_babeldoc_token_usage(stdout: str) -> BabeldocTokenUsage | None:
    """Trả `None` khi KHÔNG parse đủ — không raise, không đoán (6.23.3)."""
```

Ràng buộc bắt buộc, mỗi cái có lý do cụ thể — Dev **không được** đơn giản hoá:

1. **Case-sensitive tuyệt đối, CẤM `re.IGNORECASE`.** babeldoc in cả `Prompt tokens:` và
   `Cache hit prompt tokens:` (T4). Với `IGNORECASE`, pattern `Prompt tokens:` khớp **bên trong**
   dòng cache-hit ⇒ `prompt_tokens` nhận nhầm giá trị cache-hit. Đây là bẫy duy nhất của tập 4
   dòng này.
2. **Chỉ đọc `stdout`, KHÔNG nối `stderr`.** Khác `rate_limit_hits`/`drop_sentinel_count` (cố ý
   quét cả hai vì chỉ đếm sự kiện, thừa còn hơn thiếu). Ở đây con số đi thẳng vào tiền: gộp 2 kênh
   là mở đường cho cùng một dòng bị đếm 2 lần nếu babeldoc đổi handler sang stderr ở bản sau.
   Nguồn: T4 + §6.12.2 D1 (log babeldoc/pdf2zh ra **stdout**) + T8.
3. **Lấy match CUỐI CÙNG** (`matches = RE.findall(stdout)`; dùng `matches[-1]`), không phải match
   đầu. T4/T10 chứng minh chỉ in 1 lần/tiến trình, nhưng nếu bản sau in thêm dòng tổng kết giữa
   chừng thì con số **cuối** mới là tổng — phòng thủ này miễn phí.
4. **Thiếu bất kỳ dòng nào trong 3 dòng `total`/`prompt`/`completion` ⇒ trả `None`** (không dựng
   usage một phần). `cache_hit_prompt_tokens` thiếu ⇒ điền `0` (chỉ dùng để quan sát, không dùng
   để tính tiền ở vòng này). Lý do deny-by-default: một usage thiếu prompt/completion không tính
   được giá (2 rate khác nhau), mà đoán split là quay lại đúng bản chất "ước lượng" nhưng **đội
   lốt** `'metered'` — chính là loại nhầm lẫn RC-4 (§6.11.3).
5. **`\d+` thuần, không chấp nhận dấu phẩy/dấu chấm phân cách.** T7: f-string trên `int` không
   sinh dấu phân cách. Nếu bản sau đổi sang `{value:,}` thì regex **không khớp** → rơi về
   `estimated` (an toàn), thay vì khớp nửa vời `123` từ `123,456` (sai 1000 lần, im lặng).
6. **Tiền đề `COLUMNS=200`** (T8, đã có sẵn trong runner) là **một phần của hợp đồng này**: rich
   wrap theo chiều rộng terminal, và toàn bộ chuỗi `INFO:babeldoc.main:Total tokens: <số>` chỉ
   ~45 ký tự nên không bị cắt ở 200 cột. Ai bỏ `COLUMNS=200` là phá đồng thời parse này **và**
   `RATE_LIMIT_LINE_RE` (§6.14.3 B11).
7. **Không parse dòng `Term extraction tokens:`** (T5) — nó đã nằm trong `Total tokens` vì app
   dùng chung translator. Parse rồi cộng = đếm 2 lần.

#### 6.23.3. Mở rộng `BabeldocResult` + capability (R8-03)

```python
@dataclass
class BabeldocResult:
    ...                                   # giữ nguyên toàn bộ field hiện có
    rate_limit_hits: int = 0
    drop_report: BabeldocDropReport = field(default_factory=_empty_drop_report)
    #: 6.23 — token THẬT babeldoc tự đếm từ `response.usage` (6.23.1 T2/T4),
    #: parse từ `stdout` của CHÍNH lần chạy này. `None` = không parse được
    #: (bản babeldoc khác / log level khác / call site cũ, mock) ⇒ orchestrator
    #: rơi về `estimate_chunk_cost()`, KHÔNG crash.
    real_token_usage: BabeldocTokenUsage | None = None
```

`real_tokens_used` (1 field int) mà brief đề xuất **được thay bằng dataclass 4 số** vì giá input và
giá output khác nhau (`DeepSeekProvider.estimate_cost(input_tokens, output_tokens)`,
`deepseek_provider.py:49-51`): chỉ có `total` thì buộc phải **đoán tỷ lệ split** — xem lý do ở
6.23.2 mục 4. `.total_tokens` chính là con số ghi vào `chunk.api_tokens_used`, nên không mất gì.

Gán trong `translate_pages()`, **ngay cạnh 2 tiền lệ hiện có** (`babeldoc_runner.py:574-577`):

```python
rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))
drop_sentinel_count = (stdout + "\n" + stderr).count(_DROP_SENTINEL_TEXT)
real_token_usage = parse_babeldoc_token_usage(stdout)   # 6.23 — CHỈ stdout
```

**Không** đưa `real_token_usage` vào `BabeldocError`/`BabeldocTimeoutError`: chunk fail thì không
có `api_cost` để ghi, và chi phí đã tiêu của lần fail đó không đo được đầy đủ (bị kill giữa chừng)
— ghi nửa vời vào cột tiền là tệ hơn không ghi. Ghi nhận vào backlog nếu sau này cần.

**Capability (R8-03 — hỏi năng lực của object, không hỏi TÊN engine):**

```python
# src/services/babeldoc_runner.py, class BabeldocRunner
    #: 6.23 (BL-10). babeldoc tự đếm token thật từ `response.usage` và in ra
    #: stdout cuối mỗi lần chạy (6.23.1 T2/T4) → chunk dịch bằng engine này
    #: có thể đạt `cost_source='metered'`.
    reports_token_usage: ClassVar[bool] = True

# src/services/pdf2zh_runner.py, class Pdf2zhRunner
    #: 6.23 (BL-10). pdf2zh vứt bỏ `response.usage`, không in token ra đâu cả
    #: (§6.6.6, T11) — không có gì để parse. Giữ `estimated`.
    reports_token_usage: ClassVar[bool] = False
```

`JobOrchestrator` đọc qua property `_reports_token_usage`, **đúng khuôn** `_needs_font_shrink`
(`job_orchestrator.py:608-631`) và `_reports_own_paragraph_drops` (`:633-650`), **bao gồm cả guard
`isinstance(value, bool)`** kèm thông điệp lỗi cùng dạng. Guard là bắt buộc: `AsyncMock(spec=...)`
chỉ copy TÊN thuộc tính chứ không copy GIÁ TRỊ, nên thiếu guard thì test pdf2zh quên set thuộc
tính sẽ chạy nhầm nhánh metered và vẫn PASS (B9.4).

**R8-02 (deny-by-default)**: engine thứ ba trong tương lai mặc định `reports_token_usage = False`.

#### 6.23.4. Sửa `_process_chunk()` — data lineage (R6-01), thay `job_orchestrator.py:2202-2214`

Khối hiện tại (nguyên văn hành vi: luôn ước lượng) đổi thành **2 nhánh, chọn theo capability +
kết quả parse**:

```python
# 6.23 — capability của engine ĐÃ CHỌN (R8-03), không hỏi tên engine.
usage = pdf2zh_result.real_token_usage if self._reports_token_usage else None
if self._reports_token_usage and usage is None:
    logger.warning(
        "6.23: engine bao co token usage nhung KHONG parse duoc dong "
        "'Total tokens:' tren stdout cho chunk %s cua job %s — roi ve "
        "estimate_chunk_cost() (cost_source='estimated'). Kiem tra version "
        "babeldoc/log level, xem Architecture.md 6.23.2.",
        chunk.chunk_index, job.id,
    )

if usage is not None:
    tokens_used = usage.total_tokens
    cost_usd = pricing_provider.estimate_cost(usage.prompt_tokens, usage.completion_tokens)
    cost_source = "metered"
    if usage.prompt_tokens + usage.completion_tokens != usage.total_tokens:
        logger.warning(...)          # 6.23.1 ASSUMED #2 — CHỈ log, không đổi hành vi
else:
    source_text = _extract_chunk_text(source_path, chunk)
    segment_count = _count_text_segments(source_path, chunk.page_start, chunk.page_end)
    input_tokens, output_tokens, cost_usd = estimate_chunk_cost(...)   # nguyên xi như hiện tại
    tokens_used = input_tokens + output_tokens
    cost_source = "estimated"

chunk.api_tokens_used = tokens_used
chunk.api_cost = cost_usd
chunk.cost_source = cost_source
```

**Lineage tường minh (R6-01) — artifact nào, ai đọc field nào:**

| Bước | Artifact tạo ra | Bước sau đọc gì |
|---|---|---|
| 1. subprocess babeldoc (`babeldoc_runner.translate_pages`) | chuỗi `stdout` của **chính lần chạy này** (biến cục bộ `stdout`, `babeldoc_runner.py:568`) | `parse_babeldoc_token_usage(stdout)` — **không** đọc file log, **không** đọc `stderr`, **không** đọc stdout của lần chạy khác |
| 2. parse | `BabeldocResult.real_token_usage` (`BabeldocTokenUsage \| None`) | `_process_chunk()` đọc `pdf2zh_result.real_token_usage` — **cùng object** trả về từ `_call_translator()` cho **chunk đang xử lý**, không lấy lại từ biến nào khác |
| 3. tính tiền | `tokens_used`, `cost_usd`, `cost_source` | ghi vào **3 cột của chính row `chunk` đó**: `api_tokens_used`, `api_cost`, `cost_source` |
| 4. gộp job | `chunks[*].cost_source` trong DB | `run_job()` Bước 10 (`:1022`) + nhánh cost-cap (`:848`) tính `job.cost_source` — **suy ra từ chunk**, không đặt cứng (xem 6.23.5) |

**Điểm Bug #5 tương ứng của section này**: `usage` phải đến từ `pdf2zh_result` (return value của
lời gọi translate của **chunk này**), tuyệt đối không từ `self`, không từ biến tích luỹ cấp job,
không parse lại `stdout` ở tầng orchestrator. Hai chunk chạy song song sẽ có 2 tiến trình babeldoc
riêng, mỗi tiến trình có tổng token riêng — trộn là sai tiền cho cả hai.

**Ghi chú cho Dev**: nhánh metered **cố ý bỏ qua** `_extract_chunk_text()` /
`_count_text_segments()` (2 lần mở file PyMuPDF không còn dùng để làm gì). Dev **phải grep xác
nhận** `source_text`/`segment_count`/`input_tokens`/`output_tokens` không được dùng ở đoạn sau
trong cùng hàm trước khi chuyển chúng vào nhánh `else` — nếu có, giữ nguyên vị trí tính toán.

#### 6.23.5. `jobs.cost_source` — suy ra từ chunk, không đặt cứng

Luật gộp (áp dụng cho **nhánh PDF**):

```python
def rollup_cost_source(chunks: Sequence[Chunk]) -> str:
    """'metered' CHỈ khi mọi chunk có đóng góp chi phí đều là số đo thật."""
    sources = {c.cost_source for c in chunks if c.api_cost is not None}
    return "metered" if sources == {"metered"} else "estimated"
```

- Trộn lẫn (vài chunk metered, vài chunk fallback estimated) ⇒ **`'estimated'`**. Không tạo giá
  trị thứ ba `'partial'`: cột đang là 2 giá trị trong hợp đồng §4.2 và UI đã rẽ theo đúng 2 giá
  trị đó; thêm giá trị mới là đổi hợp đồng ở 3 tầng để mô tả một trạng thái hiếm. Nguyên tắc:
  **một tổng chứa số ước lượng thì bản thân nó là số ước lượng.**
- Không chunk nào có `api_cost` (job fail sớm) ⇒ `'estimated'` (mặc định an toàn).
- 2 điểm gán **phải sửa**: `job_orchestrator.py:1022` (Bước 10, dùng toàn bộ `chunks`) và `:848`
  (nhánh `cost_capped`, dùng **`chunks[:position]`** — đúng tập đã cộng vào `completed_cost` ngay
  trên đó). Câu `error_message` ở nhánh cost-cap nói "chi phí **ước tính** tích luỹ" — khi
  rollup trả `'metered'` thì đổi thành "chi phí **thật** tích luỹ", đúng khuôn nhánh EPUB đã làm
  (`:1256-1259`).
- **Nhánh EPUB không đổi luật**: `job.cost_source = "metered"` vẫn đặt trực tiếp tại `:1197`,
  `:1256`, `:1293`, `:1417`, `:1679` (số thật từ `TranslationResult`, §6.20.8). Nhưng
  `_process_epub_chunk()` **phải ghi thêm `chunk.cost_source = "metered"`** tại đúng chỗ nó ghi
  `api_tokens_used`/`api_cost` — nếu không, cột mới sẽ nói dối (`'estimated'`) cho những chunk
  duy nhất trong dự án đã đo thật từ trước. Đây là yêu cầu lineage (R6-01), không phải tuỳ chọn.
- **Job PDF bằng pdf2zh**: `reports_token_usage = False` ⇒ mọi chunk `'estimated'` ⇒ job
  `'estimated'` — **hành vi hiện tại giữ nguyên 100%**.

**Tương tác với cost gate (§6.11.4 Lớp 3)**: `completed_cost = sum(c.api_cost)` không đổi công
thức; chỉ có chất lượng con số tốt lên (số thật thay vì ước lượng ±30–50%). Hệ quả cần biết
trước: với babeldoc, chi phí tích luỹ **có thể thấp hơn hẳn** ước lượng cũ ⇒ job từng bị
`cost_capped` oan nay chạy tiếp. Đó là cải thiện, không phải hồi quy — nhưng QA phải biết để
không báo là bug.

#### 6.23.6. Audit Protocol 8 (R8-01) — từng bước hiện có trong `_process_chunk()`

Thêm một nhánh xử lý mới vào đường ống dùng chung 2 engine ⇒ phải trả lời cho **từng** bước đang
có, kể cả bước cũ (bài học Bug #9: bước CŨ mới là chỗ dễ sót).

| Bước hiện có | Tồn tại để giải quyết vấn đề gì | Nhánh metered mới có liên quan không |
|---|---|---|
| `shutil.rmtree(chunk_output_dir)` đầu mỗi attempt (`:2053-2054`) | pdf2zh/babeldoc ghi đè file cũ của attempt trước → trang dịch lặp 2 lần | **Có liên quan, theo hướng tốt**: mỗi attempt là **1 subprocess mới** ⇒ `stdout` (và do đó token) thuộc **đúng attempt cuối cùng thành công**. Token của attempt fail trước đó **không** bị cộng vào — vì `with_retry` trả về `BabeldocResult` của attempt thành công. ⚠️ **Giới hạn đã biết**: tiền đã tiêu cho attempt fail **không được tính** vào `api_cost` ⇒ metered là **under-count** khi có retry. Ghi rõ ở 6.23.8 |
| `chunk.rate_limit_hits = pdf2zh_result.rate_limit_hits` (`:2117`) | lineage AIMD (§6.12.2 D1) | Không liên quan; cùng nguồn `stdout` nhưng khác regex, khác cột. **Không gộp 2 regex**, không đổi `RATE_LIMIT_LINE_RE` |
| `classify_chunk_outcome` + `_observe_chunk_outcome` (`:2119-2140`) | AIMD | Không liên quan. Token không phải tín hiệu concurrency |
| `font_shrink_page()` + vòng `OverflowReport` (`:2145-2172`) | pdf2zh vẽ tràn khung (Bug #9) | **Không đụng vào.** Gate `self._needs_font_shrink` giữ nguyên. Nhánh mới không đọc/ghi gì ở đây |
| Khối BL-04 drop report (`:2181-2199`) | babeldoc tự bỏ đoạn không vừa khung | Không liên quan về dữ liệu, nhưng **cùng họ thiết kế**: cũng là "đọc tín hiệu do chính babeldoc phát ra". Đặt nhánh mới **sau** khối này, giữ nguyên thứ tự hiện có |
| `estimate_chunk_cost()` + `_extract_chunk_text` + `_count_text_segments` (`:2202-2214`) | pdf2zh không xuất token ⇒ buộc phải ước lượng (§6.6.6) | **Đây chính là bước bị audit.** Câu hỏi R8-01: *"lý do bước này tồn tại có còn đúng với babeldoc không?"* → **KHÔNG**: babeldoc có token thật (T2/T4). Bước này trở thành **fallback**, không phải đường chính, cho engine có `reports_token_usage = True` |
| `merge_chunk_pdfs` / guard BR-OCR-03 / `create_bilingual_pdf` (cấp job, §6.14.4) | nối chunk, chống bản dịch rỗng | Không liên quan — nhánh mới không tạo/sửa file PDF nào |

**Kết luận R8-02**: không có bước nào rơi vào trạng thái "chưa rõ" ⇒ không bước nào bị SKIP thêm.
Bước duy nhất đổi trạng thái là `estimate_chunk_cost()` (đường chính → fallback), và nó **vẫn
chạy nguyên xi** khi parse trượt.

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

#### 6.23.8. Giới hạn đã biết (phải đưa vào PRD / tooltip UI)

1. **Bảng giá DeepSeek có thể đã lỗi thời** — `deepseek_provider.py:17-24` (tên model + giá
   output). Theo quyết định của Hiếu, **task này KHÔNG sửa bảng giá**: chỉ đổi *nguồn số token*
   từ ước lượng sang đo thật; phép nhân token × giá vẫn dùng nguyên `provider.estimate_cost()`
   hiện có. Hệ quả trung thực: `cost_source='metered'` ở vòng này có nghĩa **"token là số đo
   thật"**, **không** có nghĩa "số tiền chắc chắn đúng". Sẽ xử lý ở task riêng (cập nhật bảng
   giá) — cho tới lúc đó **tooltip UI không được hứa độ chính xác của số tiền**.
2. **Không chiết khấu cache-hit.** DeepSeek tính giá input cache-hit rẻ hơn nhiều;
   `cache_hit_prompt_tokens` đã parse nhưng **chưa dùng** để tính tiền ⇒ chi phí bị tính **cao
   hơn thực tế**. Đây là chiều sai an toàn theo đúng nguyên tắc §6.11.6 (thà ước cao còn hơn ước
   thấp), và là lý do field vẫn được lưu trong `BabeldocTokenUsage` để dùng sau.
3. **Under-count khi có retry**: token của attempt thất bại (timeout/lỗi, bị `with_retry` chạy
   lại) không được cộng (6.23.6, hàng `shutil.rmtree`). Số metered là chi phí của **attempt thành
   công**, không phải toàn bộ tiền đã tiêu cho chunk đó.
4. **Cache của chính babeldoc**: khi `pdf2zh_ignore_cache = False` và nội dung đã dịch trước đó,
   babeldoc không gọi API ⇒ `Total tokens: 0` ⇒ `api_cost = 0.0` với `cost_source='metered'`.
   **`0` là số đo thật**, không phải lỗi parse — cùng tiền lệ đã chốt ở §6.20 (`actual_cost=0.0`
   + `metered`). Phân biệt với "không parse được" chính là lý do `real_token_usage` dùng
   `None` chứ không dùng `0` làm sentinel.
5. **Chỉ áp dụng cho engine babeldoc.** Job PDF bằng pdf2zh vĩnh viễn `'estimated'` cho tới khi
   có metering proxy (§6.6.6 v1.1, vẫn hoãn).

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

### 6.24. S5 — UI hint "chọn thư mục tải về" (không code logic, dựa hoàn toàn vào browser)

Quyết định: KHÔNG dùng File System Access API (`showSaveFilePicker`, chỉ Chromium desktop). Chỉ thêm
1 hint tĩnh cạnh link download ở `web/index.html` và `web/history.html` — browser tự lo chọn + nhớ thư mục.

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

Kết luận wording: ĐƯỢC phép claim "browser sẽ mở lại thư mục bạn chọn lần trước", nhưng phải nói rõ điều kiện
(phải bật setting) và không hứa cho mọi browser/mọi chế độ — private/incognito không lưu lại (Firefox
`DownloadLastDir.sys.mjs:54-61` xoá pref; Chrome dùng prefs của profile thường). Không claim app tự nhớ.

---

### 6.25. BL-12 — EPUB nguồn không tuân thủ OCF (`mimetype` bị nén): SỬA ở bước ghi, KHÔNG từ chối ở bước cuối

**Trạng thái**: thiết kế đã chốt về mặt kỹ thuật, **chưa implement** (chờ Hiếu duyệt CLARIFY
BL-12-Q1/Q2, xem `docs/design-log.md` mục BL-12). RCA đầy đủ nằm ở design-log — mục này chỉ ghi
hợp đồng phải đạt sau khi implement (Protocol C.1).

#### 6.25.1. Chuẩn OCF về entry `mimetype` (nguồn xác thực — R5-01)

EPUB 3.3 §4.3 *OCF ZIP container* (W3C, fetch thật qua WebFetch 2026-09-16,
<https://www.w3.org/TR/epub-33/#sec-container-zip>), nguyên văn:

> "The `mimetype` file _MUST_ be the first file in the OCF ZIP container, _MUST_ be stored
> uncompressed, and _MUST NOT_ have an extra field."

3 ràng buộc — **thứ tự đầu tiên**, **STORED**, **không extra field** — đều là ràng buộc lên *bên
tạo file*, KHÔNG phải ràng buộc "reading system phải từ chối file vi phạm" (spec không có câu MUST
nào bắt reading system reject — đã kiểm cùng lần fetch).

#### 6.25.2. Hợp đồng MỚI (thay thế 2 nhánh reject tại `epub_document.py:985-991`)

| Lớp | Nơi | Kiểm gì | Hành vi |
|---|---|---|---|
| **L1 — pre-flight** | `EpubDocument.load()` (`src/services/epub_document.py:758`) | Có entry tên `mimetype` **và** nội dung byte đúng `b"application/epub+zip"` | Sai → `EpubParseError` ngay ở bước ước tính chi phí. `src/api/routes/jobs.py:376-380` đã map sẵn `EpubParseError` → **HTTP 400**, nên user biết TRƯỚC khi tốn tiền dịch |
| **L2 — normalize khi ghi** | `EpubDocument.write_translated()` (`:899`) | Không kiểm nữa — **sửa** | Luôn ghi `mimetype` là entry **ĐẦU TIÊN**, `compress_type = ZIP_STORED`, `extra = b""`; các entry còn lại giữ nguyên **thứ tự tương đối** và `compress_type` gốc |

Nguyên tắc: **tính tuân thủ OCF là thuộc tính của file app GHI RA, không phải điều kiện nhập học
của file app ĐỌC VÀO.** App tự kiểm soát được cả 3 ràng buộc ở §6.25.1 tại bước ghi, nên vi phạm ở
input là *sửa được*, không phải *lý do từ chối*. Chỉ thứ không sửa được mới được phép reject — và
phải reject ở L1 (trước cost gate), không phải ở bước merge cuối (sau khi đã trả tiền LLM).

**Deny-by-default (Protocol 8 R8-02) vẫn giữ**: trường hợp `mimetype` **thiếu hẳn** hoặc nội dung
KHÁC `application/epub+zip` → app **KHÔNG tự chế ra** entry mimetype (đó là đoán media-type thay
user, có thể file không phải EPUB thật) → reject ở L1.

#### 6.25.3. Data lineage (R6-01) — không đổi so với §6.20

- `run_epub_job()` (`job_orchestrator.py:1143`): `doc = EpubDocument.load(file_path)` với
  `file_path = job.file_path` (**file gốc user upload**, `data/uploads/<uuid>_<tên>.epub`).
- Bước merge cuối (`job_orchestrator.py:1412-1424`): `doc.write_translated(translations, merged_path, ...)`
  — đọc lại zip tại `self.path` (**chính file gốc đó**, không phải bản trung gian nào) làm khuôn,
  ghi ra `merged_path = <output_dir>/<job.id>/translated_vi.epub`. Chuẩn hoá `mimetype` xảy ra
  **trong lúc ghi ra `merged_path`** — **KHÔNG sửa tại chỗ file gốc trong `data/uploads/`**.
- `_check_epub_output_guard(doc, merged_path, ...)` (`:1424` → `:470`) sau đó `EpubDocument.load(merged_path)`
  lại từ đầu; sau khi có L2, `merged_path` luôn hợp lệ OCF kể cả khi input vi phạm.

#### 6.25.4. Hành vi thư viện đã verify (R5-01)

Đo trực tiếp trên CPython **3.14.7** của `.venv` (`zipfile/__init__.py`, đường dẫn
`~/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/lib/python3.14/zipfile/__init__.py`):

1. **`writestr(ZipInfo, data)` không bao giờ sinh extra field.** `ZipInfo` tạo mới có `extra = b""`
   và không chỗ nào gán thêm. Đo thật trên file đã ghi: local header `extra len = 0`, `infolist()[0].extra == b""`.
2. **`flag_bits` copy từ input là DEAD CODE.** `zipfile.py:1824` trong `_open_to_write()` gán đè
   `zinfo.flag_bits = _MASK_UTF_FILENAME` **vô điều kiện**, và `writestr()` (`:2037-2038`) luôn đi
   qua `self.open(zinfo, mode='w')`. ⇒ dòng `new_info.flag_bits = info.flag_bits`
   (`epub_document.py:1005`) không có tác dụng gì. **Được phép xoá** khi implement BL-12 — đồng thời
   loại luôn rủi ro tiềm ẩn copy nhầm bit 3 (data descriptor) từ 1 input lạ.
3. **`ebooklib` KHÔNG hề từ chối `mimetype` bị nén.** `ebooklib 0.20.0`, `epub.read_epub()` đọc
   thành công CHÍNH file vi phạm của Hiếu (`spine = 22`). Nghĩa là guard cũ nghiêm khắc hơn cả
   thư viện đọc mà app đang dùng.
4. **Chuẩn hoá hoạt động thật** (spike đã chạy, không phải suy đoán): re-zip file vi phạm với
   `mimetype` ép `ZIP_STORED`, giữ nguyên thứ tự + `compress_type` 62 entry còn lại →
   `zipfile.testzip() == None`, `unzip -lv` báo `mimetype … Stored … 0%`, `ebooklib` đọc lại đúng
   `spine = 22`.

⚠️ **[UNVERIFIED]** — hành vi của **reading system thực tế** (Apple Books, Calibre viewer, Kobo,
KindlePreviewer) trước 1 EPUB có `mimetype` bị nén: CHƯA đo. Không cần đo để chốt thiết kế này, vì
hợp đồng §6.25.2 làm cho **output luôn tuân thủ** — không phụ thuộc mức độ khoan dung của reader.
Cũng chưa chạy `epubcheck` (chưa cài trong repo; `which epubcheck` → không có).

#### 6.25.5. Phạm vi — lỗi CHUNG, không phải cá biệt 1 job

Đo thật toàn bộ EPUB trong `data/uploads/` (8 file, 2026-09-16), cột `compress_type` của
`infolist()[0]`:

| File | entry đầu | `compress_type` | Kết luận |
|---|---|---|---|
| `4a752f64-…_Sourdough Culture … (z-library.sk …).epub` | `mimetype` | **8 (DEFLATED)** | **VI PHẠM** — đúng file của job `bfc0ac24` |
| 7 file còn lại (kể cả `sample2_Bread-A-Global-History.epub`, `fake_drm.epub`) | `mimetype` | 0 (STORED) | hợp lệ |

⇒ **1/8 = 12,5%** file thật đã vi phạm. File vi phạm còn chứa `META-INF/com.kobobooks.display-options.xml`
và markup `koboSpan` (cùng file đã gây phần lãng phí payload ở §6.20 K-1) — dấu vết đã bị công cụ
Kobo/z-library **re-zip lại toàn bộ** (cả 63/63 entry đều DEFLATED, kể cả `mimetype`). Đây là một
lớp nguồn file phổ biến, **chắc chắn tái diễn**, không phải sự cố một lần.

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


## 11. Nhật ký thiết kế — đã tách sang `docs/design-log.md`

> Theo **Protocol C** (2026-09-10): toàn bộ khối RCA / phản biện Domain Expert / Final Decision
> trước đây nằm ở cuối file này đã được chuyển **nguyên văn** sang [`docs/design-log.md`](design-log.md).
> Bảng dưới giữ lại tiêu đề gốc để mọi tham chiếu cũ kiểu *"xem Architecture.md mục Bug #9"* vẫn
> tra ra được bằng `grep` trên chính file này.

| # | Tiêu đề gốc | Vị trí mới |
|---|---|---|
| 1 | Root Cause Analysis: Line-break/List Regression (2026-09-06) | [`docs/design-log.md`](design-log.md#root-cause-analysis-line-breaklist-regression-2026-09-06) |
| 2 | Đánh giá hướng Post-Processing cho lỗi gộp dòng Numbered List (2026-09-06) | [`docs/design-log.md`](design-log.md#đánh-giá-hướng-post-processing-cho-lỗi-gộp-dòng-numbered-list-2026-09-06) |
| 3 | Đo lại F1 trên nhiều trang — kết quả live A/B/C (2026-09-06) | [`docs/design-log.md`](design-log.md#đo-lại-f1-trên-nhiều-trang-kết-quả-live-abc-2026-09-06) |
| 4 | US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — thiết kế (2026-09-06) | [`docs/design-log.md`](design-log.md#us-16-nén-ảnh-sau-khi-ghép-compress_pdf_images-thiết-kế-2026-09-06) |
| 5 | Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order trên trang layout phức tạp (2026-09-07) | [`docs/design-log.md`](design-log.md#root-cause-analysis-text-overlap-content-loss-reading-order-trên-trang-layout-phức-tạp-2026-09-07) |
| 6 | Final Decision: Babeldoc Layout Bug Fix Roadmap (sau phản biện Domain Expert, 2026-09-07) | [`docs/design-log.md`](design-log.md#final-decision-babeldoc-layout-bug-fix-roadmap-sau-phản-biện-domain-expert-2026-09-07) |
| 7 | US-16 v2 — Mở rộng phạm vi sang ảnh `/FlateDecode` (2026-09-08) | [`docs/design-log.md`](design-log.md#us-16-v2-mở-rộng-phạm-vi-sang-ảnh-flatedecode-2026-09-08) |
| 8 | US-16 v2 — Phản biện của Domain Expert (2026-09-08) | [`docs/design-log.md`](design-log.md#us-16-v2-phản-biện-của-domain-expert-2026-09-08) |
| 9 | US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08) | [`docs/design-log.md`](design-log.md#us-16-v2-final-decision-sau-phản-biện-domain-expert-2026-09-08) |
| 10 | Bug #9 — `font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc` (2026-09-08) | [`docs/design-log.md`](design-log.md#bug-9-font_shrink_page-phá-output-của-babeldoc-tắt-hẳn-cho-engine-babeldoc-2026-09-08) |
| 11 | Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (`_get_width_before_next_break_point` đếm đôi bề rộng ký tự hiện tại) — thiết kế bản vá (Tech Lead, 2026-09-09) | [`docs/design-log.md`](design-log.md#bug-10-babeldoc-cắt-ngang-từ-tiếng-việt-giữa-chừng-_get_width_before_next_break_point-đếm-đôi-bề-rộng-ký-tự-hiện-tại-thiết-kế-bản-vá-tech-lead-2026-09-09) |
| 12 | Bug #EPUB-3 — Quét job mồ côi (orphan) lúc server startup (Tech Lead, 2026-09-10) | [`docs/design-log.md`](design-log.md#bug-epub-3-quét-job-mồ-côi-orphan-lúc-server-startup-tech-lead-2026-09-10) |

**Quy tắc từ 2026-09-10**:
- Nội dung mô tả **hợp đồng hiện hành** (schema, API, flow, hằng số đang chạy) → viết vào §1–10 của
  file này.
- Nội dung **nhật ký** (vì sao đổi, đo đạc, phản biện, quyết định) → append vào `docs/design-log.md`.
- Một quyết định trong design-log làm đổi hợp đồng → **bắt buộc** cập nhật §1–10 tương ứng, không để
  hợp đồng chỉ tồn tại dưới dạng nhật ký.
