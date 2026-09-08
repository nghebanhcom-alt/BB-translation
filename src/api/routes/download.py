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

#: US-15 S15-3 (Architecture.md 6.15.3, sua sau phan bien Domain Expert):
#: MIME suy tu duoi file thay vi hardcode "application/pdf" (P-05) — endpoint
#: nay khong can biet gi ve job_type, chi can biet duoi file thuc te tren
#: dia (`.zip` cho parse_only, `.pdf` cho translate).
_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".epub": "application/epub+zip",
}


@router.get("/{job_id}/download")
async def download_job_result(
    job_id: str, session: SessionDep, format: str | None = None
) -> FileResponse:
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
        raise HTTPException(
            status_code=404, detail=f"File output khong ton tai tren disk: {result_path}"
        )

    # US moi (2026-09-06): 2 lan dich cung 1 file goc (vd retry voi provider
    # khac) truoc day deu tra ve CUNG 1 ten file tai ve ("{stem}_vi.pdf") —
    # khong the phan biet duoc 2 ban da tai ve nam chung trong thu muc
    # Downloads cua user. Dung `completed_at` (thoi diem dich XONG, on dinh
    # hon `updated_at` vi khong doi khi metadata khac cua job doi sau do) lam
    # hau to, fallback `updated_at` cho job cu truoc khi field nay ton tai.
    timestamp_source = job.completed_at or job.updated_at
    timestamp_suffix = f"_{timestamp_source.strftime('%Y%m%d-%H%M%S')}" if timestamp_source else ""

    # US-15 S15-3: job parse_only tai ve la "{stem}_markdown_{timestamp}.zip"
    # — nhat quan voi pattern "_vi"/"_bilingual" + timestamp da co san.
    if job.job_type == "parse_only":
        label = "markdown"
    else:
        label = "bilingual" if format == "bilingual" else "vi"

    media_type = _MEDIA_TYPES.get(result_path.suffix.lower(), "application/octet-stream")

    return FileResponse(
        result_path,
        filename=f"{Path(job.filename).stem}_{label}{timestamp_suffix}{result_path.suffix}",
        media_type=media_type,
    )
