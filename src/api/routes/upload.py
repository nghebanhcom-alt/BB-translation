"""POST /api/upload (US-01, BR-INPUT-01..04).

Stores the raw file under `data/uploads/{file_id}_{filename}` and a small
JSON sidecar `data/uploads/{file_id}.json` with the metadata `POST /api/jobs`
needs later (`resolve_upload()` below). There is no `uploads` DB table in
Architecture.md section 4.2 — a sidecar file is the smallest thing that lets
`jobs.py` turn a `file_id` back into a path/file_type/hash without
re-reading and re-hashing the (possibly 500MB) file on every job-create call.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.file_router import (
    FileType,
    InvalidFileError,
    UnsupportedFileTypeError,
    detect_file_type,
)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".pdf", ".epub"}
_UPLOAD_DIR = Path("data/uploads")
_CHUNK_SIZE = 1024 * 1024


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    page_count: int | None = None
    uploaded_at: str | None = None


@dataclass
class UploadMetadata:
    file_id: str
    filename: str
    file_path: str
    file_type: str
    size_bytes: int
    file_hash: str
    page_count: int | None
    # US moi (2026-09-06): sap xep "file da upload" moi nhat len dau + hien
    # thi gio upload o UI. ISO 8601 string (khong phai datetime) de tuong
    # thich JSON sidecar hien co. Default "" (khong phai None/thieu field)
    # de doc duoc sidecar CU tao TRUOC khi truong nay ton tai — UploadMetadata(**data)
    # se loi TypeError neu field bat buoc khong co default va sidecar cu thieu key nay.
    uploaded_at: str = ""


class UploadNotFoundError(ValueError):
    pass


def _metadata_path(file_id: str) -> Path:
    return _UPLOAD_DIR / f"{file_id}.json"


def resolve_upload(file_id: str) -> UploadMetadata:
    """Look up a previously uploaded file's metadata by `file_id` — used by
    `POST /api/jobs`/`POST /api/batches` to turn an upload into a `Job` row.
    """
    path = _metadata_path(file_id)
    if not path.exists():
        raise UploadNotFoundError(f"file_id '{file_id}' khong ton tai hoac chua duoc upload")
    data = json.loads(path.read_text(encoding="utf-8"))
    return UploadMetadata(**data)


@router.post("", response_model=UploadResponse)
async def upload_file(file: UploadFile) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Thieu ten file")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Chi ho tro PDF va EPUB")

    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    # CWE-22: file.filename is client-controlled and unsanitized by
    # Starlette — ".name" strips any "../" / directory components so the
    # write can never land outside _UPLOAD_DIR.
    safe_name = Path(file.filename).name
    dest_path = _UPLOAD_DIR / f"{file_id}_{safe_name}"
    if not dest_path.resolve().is_relative_to(_UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Ten file khong hop le")

    size_bytes = 0
    hasher = hashlib.sha256()
    try:
        with dest_path.open("wb") as out:
            while chunk := await file.read(_CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File vuot qua {settings.max_upload_size_mb}MB",
                    )
                hasher.update(chunk)
                out.write(chunk)
    except HTTPException:
        dest_path.unlink(missing_ok=True)
        raise

    try:
        file_type = detect_file_type(dest_path)
    except (UnsupportedFileTypeError, InvalidFileError) as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    page_count: int | None = None
    if file_type != FileType.EPUB:
        # detect_file_type() already opened this exact file successfully
        # above, so a failure here would mean something changed the file out
        # from under us — treat it the same way rather than let it 500.
        try:
            with fitz.open(dest_path) as doc:
                page_count = doc.page_count
        except RuntimeError as exc:
            dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="File PDF bi hong hoac khong doc duoc, vui long kiem tra lai file",
            ) from exc

    uploaded_at = datetime.now(UTC).isoformat()
    metadata = UploadMetadata(
        file_id=file_id,
        filename=file.filename,
        file_path=str(dest_path),
        file_type=file_type.value,
        size_bytes=size_bytes,
        file_hash=hasher.hexdigest(),
        page_count=page_count,
        uploaded_at=uploaded_at,
    )
    _metadata_path(file_id).write_text(
        json.dumps(metadata.__dict__, ensure_ascii=False), encoding="utf-8"
    )

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        file_type=file_type.value,
        size_bytes=size_bytes,
        page_count=page_count,
        uploaded_at=uploaded_at,
    )


@router.delete("/{file_id}", status_code=204)
async def delete_upload(file_id: str) -> Response:
    """Xoa 1 file vua upload (US moi, theo yeu cau user 2026-09-06) — chi xoa
    file thuc + sidecar json tren dia, KHONG dong toi Job/DB nao (upload
    chua co Job cho toi khi `POST /api/jobs` duoc goi, xem docstring dau
    module). Neu `file_id` da duoc dung de tao Job roi, xoa upload nay KHONG
    xoa Job do — Job da tu doc xong `file_path` tu luc tao va van chay/xem
    duoc binh thuong; dung `DELETE /api/jobs/{job_id}` de xoa Job.
    """
    try:
        metadata = resolve_upload(file_id)
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    Path(metadata.file_path).unlink(missing_ok=True)
    _metadata_path(file_id).unlink(missing_ok=True)

    return Response(status_code=204)
