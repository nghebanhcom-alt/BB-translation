"""BL-04 live E2E harness (Architecture.md 6.22.9, X8 — R5-03 + R6-03).

Calls `JobOrchestrator._process_chunk()` DIRECTLY (not `run_job()`, not the
babeldoc CLI by hand) against the REAL 418-page Le Cordon Bleu source file,
for exactly chunk 5 (`--pages 199-240`, 42 pages) with a real `BabeldocRunner`
(real subprocess, real DeepSeek API calls) and a real (in-memory) DB session.

Why this exact shape, not `run_job()` / not a hand-run CLI — see
Architecture.md 6.22.9 "Harness bắt buộc (X8)": assertions 1-3 need a real
`BabeldocRunner` run; assertion 5 needs the overlap-page filter that lives
INSIDE `_process_chunk()`; assertion 6 needs the R-1 log line that also lives
inside `_process_chunk()`; and running the full 418 pages via `run_job()`
would cost real money for 376 pages this gate doesn't need.

Usage: `uv run python scripts/bl04_live_e2e_chunk5.py`
Requires: `DEEPSEEK_API_KEY` in `.env` (already present), `babeldoc` CLI on
PATH (verified installed: 0.6.4), the real upload file below present on disk.
"""

import asyncio
import json
import logging
from pathlib import Path

import fitz
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.core.glossary_manager import GlossaryManager
from src.core.job_orchestrator import JobOrchestrator, _extract_full_text
from src.core.prompt_builder import write_babeldoc_prompt_file
from src.models.chunk import Chunk
from src.models.job import Job
from src.models.layout_qa import LayoutQaFinding
from src.services.babeldoc_runner import BabeldocRunner
from src.services.pdf2zh_service_map import Pdf2zhServiceMapper
from src.services.provider_factory import ProviderFactory

logging.basicConfig(level=logging.INFO)

SOURCE_PDF = Path(
    "data/uploads/f07b3194-b98e-4227-9516-198c6c91ff75_"
    "Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf"
)
CHUNK_INDEX = 5
PAGE_START = 199
PAGE_END = 240
OVERLAP_START = 199
OVERLAP_END = 200
EXPECTED_DROP_PAGE = 230

WORK_DIR = Path("data/bl04_live_e2e")


async def main() -> None:
    assert SOURCE_PDF.exists(), f"source file not found: {SOURCE_PDF}"

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db_session:
        job = Job(
            filename=SOURCE_PDF.name,
            file_path=str(SOURCE_PDF),
            file_size=SOURCE_PDF.stat().st_size,
            file_hash="bl04-live-e2e",
            file_type="pdf_digital",
            model="deepseek",
            total_pages=418,
            chunk_size_used=40,  # assertion 0 (6.22.9) — must be 40 (warm), not 20
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        chunk = Chunk(
            job_id=job.id,
            chunk_index=CHUNK_INDEX,
            page_start=PAGE_START,
            page_end=PAGE_END,
            overlap_start=OVERLAP_START,
            overlap_end=OVERLAP_END,
        )
        db_session.add(chunk)
        await db_session.commit()
        await db_session.refresh(chunk)

        settings = Settings(pdf_translate_engine="babeldoc")
        assert settings.deepseek_api_key, "DEEPSEEK_API_KEY not configured in .env"
        pricing_provider = ProviderFactory.create("deepseek", settings)

        orchestrator = JobOrchestrator(
            settings=settings,
            babeldoc_runner=BabeldocRunner(),
            provider=pricing_provider,
            output_dir=WORK_DIR / "outputs",
            processing_dir=WORK_DIR / "processing",
        )

        service = Pdf2zhServiceMapper().map(job.model, settings)

        full_text = _extract_full_text(SOURCE_PDF)
        glossary_manager = GlossaryManager(db_session)
        prompt_path = WORK_DIR / "processing" / job.id / "prompt.txt"
        await write_babeldoc_prompt_file(
            glossary_manager,
            path=prompt_path,
            project_id=job.batch_id,
            only_terms_present_in=full_text,
            max_glossary_entries=settings.max_glossary_entries_in_prompt,
        )
        prompt_overhead_chars = len(prompt_path.read_text(encoding="utf-8"))

        print(f"job={job.id} chunk={chunk.id} starting _process_chunk() ...")
        await orchestrator._process_chunk(
            job,
            chunk,
            SOURCE_PDF,
            service,
            prompt_path,
            prompt_overhead_chars,
            pricing_provider,
            db_session,
        )
        await db_session.refresh(chunk)
        print(f"chunk.status={chunk.status} chunk.output_path={chunk.output_path}")

        # --- Assertion 0 (precondition) ---
        assert job.chunk_size_used == 40
        assert chunk.page_start == 199 and chunk.page_end == 240

        # --- Findings persisted for this job ---
        findings_result = await db_session.exec(
            select(LayoutQaFinding).where(LayoutQaFinding.job_id == job.id)
        )
        findings = findings_result.all()
        print(f"\n{len(findings)} LayoutQaFinding row(s) persisted for job {job.id}:")
        drop_findings = []
        for f in findings:
            detail = json.loads(f.detail) if f.detail else {}
            print(f"  check_type={f.check_type} page_number={f.page_number} detail={detail}")
            if f.check_type == "babeldoc_paragraph_drop_unfit":
                drop_findings.append((f, detail))

        # --- Assertion 5: no finding at overlap pages 199-200 ---
        overlap_findings = [f for f, _ in drop_findings if f.page_number in (199, 200)]
        assert not overlap_findings, f"F1 filter failed, found: {overlap_findings}"

        # --- Assertion 2/3: a finding at page 230 with the feuilletage text ---
        page_230 = [(f, d) for f, d in drop_findings if f.page_number == EXPECTED_DROP_PAGE]
        if page_230:
            f, d = page_230[0]
            print(f"\n>>> FOUND finding at page {EXPECTED_DROP_PAGE}: {d.get('text_excerpt')!r}")
        else:
            print(
                f"\n>>> NO finding at page {EXPECTED_DROP_PAGE} this run (see script docstring "
                "'Neu khong tai hien duoc' fallback in Architecture.md 6.22.9)."
            )

        # --- Assertion 4: open translated PDF page 230 (index 31 within the
        # 42-page --only-include-translated-page mono output) and print full
        # text for manual/visual confirmation the feuilletage sidebar is gone.
        if chunk.output_path:
            mono = Path(chunk.output_path)
            page_index_in_mono = EXPECTED_DROP_PAGE - PAGE_START  # 230 - 199 = 31
            with fitz.open(mono) as doc:
                print(f"\nmono page_count={doc.page_count} (expected 42)")
                if 0 <= page_index_in_mono < doc.page_count:
                    text = doc[page_index_in_mono].get_text()
                    print(
                        f"\n=== translated page {EXPECTED_DROP_PAGE} "
                        f"(mono index {page_index_in_mono}) text ({len(text)} chars) ===\n{text}"
                    )

        print(
            "\nDone. Inspect output above for R-1 log line (search stderr/stdout for "
            "'BL-04' / 'observed=')."
        )


if __name__ == "__main__":
    asyncio.run(main())
