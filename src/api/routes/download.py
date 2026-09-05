"""GET /api/jobs/{job_id}/download (US-09, AC-09.1/AC-09.2).

Mounted under the same `/api/jobs` prefix as `jobs.py` (see src/api/main.py)
so the route reads as `GET /api/jobs/{job_id}/download` per the increment
brief, while staying in its own module per Architecture.md section 8
(`src/api/routes/download.py`).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.deps import SessionDep
from src.models.job import Job

router = APIRouter()


@router.get("/{job_id}/download")
async def download_job_result(job_id: str, session: SessionDep, format: str | None = None) -> FileResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job khong ton tai")
    if job.status != "completed":
        raise HTTPException(
            status_code=404, detail=f"Job chua hoan thanh (status hien tai: '{job.status}')"
        )

    if format == "bilingual":
        if not job.bilingual_path:
            raise HTTPException(status_code=404, detail="Job nay khong co ban song ngu")
        result_path = Path(job.bilingual_path)
    else:
        if not job.output_path:
            raise HTTPException(status_code=404, detail="Job nay khong co file output")
        result_path = Path(job.output_path)

    if not result_path.exists():
        raise HTTPException(status_code=404, detail=f"File output khong ton tai tren disk: {result_path}")

    return FileResponse(
        result_path,
        filename=f"{Path(job.filename).stem}_{'bilingual' if format == 'bilingual' else 'vi'}{result_path.suffix}",
        media_type="application/pdf",
    )
