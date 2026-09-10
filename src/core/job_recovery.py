"""Bug #EPUB-3 (Architecture.md Bug #EPUB-3, section E3): server startup
recovery for jobs "mo coi" (orphaned) — a job whose background `asyncio.Task`
died with the previous process (crash, deploy, `--reload`) and will never be
picked up by anything, so its `Job.status` row would otherwise stay stuck in
an "active" state forever (E3.1).

Kept in its own module rather than inlined into `src/api/main.py::lifespan()`
so tests can call `fail_orphaned_jobs()` directly against an in-memory
session (E3.7) without spinning up a `TestClient` + overriding the global
DB engine.
"""

import logging
from datetime import UTC, datetime

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.job import Job

logger = logging.getLogger(__name__)

# E3.3: deliberately NOT importing `_ACTIVE_JOB_STATUSES`
# (src/api/routes/jobs.py:821-833) even though the values are identical
# today — the two sets happen to match because they both mean "job not
# finished yet", not because they encode the same business rule. Coupling
# them would create an implicit dependency between "block deleting a running
# job" and "orphan sweep on startup" that isn't actually there.
_ORPHAN_JOB_STATUSES = {
    "created",
    "queued",
    "chunking",
    "parsing",
    "translating",
    "post_processing",
    "merging",
}

# E3.4: exact wording matches the "what happened — old data kept — what to do
# next" structure already used by src/core/job_orchestrator.py:634-638 and
# :1006-1010, and stays unaccented Vietnamese to match every other
# `error_message` in the codebase.
_ORPHAN_ERROR_MESSAGE = (
    "Job bi gian doan do server khoi dong lai (restart/crash) trong luc dang chay. "
    "Cac chunk da dich xong duoc giu nguyen — bam Retry de chay tiep tu cho dang do."
)


async def fail_orphaned_jobs(session: AsyncSession) -> int:
    """Mark every `Job` stuck in a non-terminal status as `failed` so the UI
    stops showing it as running forever and the user can Retry it (E3.6
    confirms retry already resumes from the first non-completed chunk,
    BR-CHUNK-05 — no code change needed there).

    Returns the number of jobs marked. Idempotent: a second call after the
    first finds nothing left in `_ORPHAN_JOB_STATUSES` and returns 0.
    """
    result = await session.exec(select(Job).where(col(Job.status).in_(_ORPHAN_JOB_STATUSES)))
    jobs = result.all()

    now = datetime.now(UTC)
    for job in jobs:
        job.status = "failed"
        job.error_message = _ORPHAN_ERROR_MESSAGE
        # E3.4: `or` so a value set for some other reason is never clobbered
        # — should never happen for a non-terminal job, but keeps the
        # contract of "never regress finished_at" from BR-HIST-01/02.
        job.finished_at = job.finished_at or now
        job.updated_at = now
        # E3.4 / E3.5: deliberately NOT touching progress, current_chunk,
        # total_chunks, actual_cost (let the user see how far it got) and
        # NOT touching Chunk.status (resume already skips `completed` chunks
        # on its own — resetting them here would be no-op code that doesn't
        # change behavior).
        session.add(job)

    if jobs:
        await session.commit()

    logger.warning("Startup: da danh dau %d job mo coi thanh failed (server restart)", len(jobs))
    return len(jobs)
