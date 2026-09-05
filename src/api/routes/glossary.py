import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import func, select

from src.api.deps import SessionDep
from src.core.glossary_manager import GlossaryManager
from src.models.glossary import Glossary, GlossaryEntry
from src.utils.excel_utils import (
    GlossaryEntryData,
    export_glossary_to_excel,
    import_glossary_from_excel,
)

router = APIRouter()


class GlossaryEntryOut(BaseModel):
    id: str
    term_en: str
    term_vi: str | None
    notes: str | None
    scope: str
    created_at: datetime
    updated_at: datetime


class GlossaryEntryIn(BaseModel):
    term_en: str
    term_vi: str | None = None
    notes: str | None = None


class GlossaryEntryUpdate(BaseModel):
    term_en: str | None = None
    term_vi: str | None = None
    notes: str | None = None


class GlossaryListResponse(BaseModel):
    entries: list[GlossaryEntryOut]
    total: int
    limit: int
    offset: int


class GlossaryImportPreviewResponse(BaseModel):
    entries: list[GlossaryEntryIn]
    count: int


class GlossaryImportConfirmRequest(BaseModel):
    entries: list[GlossaryEntryIn]
    scope: str = "global"
    project_id: str | None = None


class GlossaryImportConfirmResponse(BaseModel):
    imported: int
    updated: int
    skipped: int


def _to_out(entry: GlossaryEntry, scope: str) -> GlossaryEntryOut:
    return GlossaryEntryOut(
        id=entry.id,
        term_en=entry.term_en,
        term_vi=entry.term_vi,
        notes=entry.notes,
        scope=scope,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.post("/import", response_model=GlossaryImportPreviewResponse)
async def preview_import(file: UploadFile) -> GlossaryImportPreviewResponse:
    """AC-03.1: parse the uploaded Excel and return a preview WITHOUT saving to DB yet."""
    if file.filename is None or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Chi ho tro file Excel (.xlsx)")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        parsed = import_glossary_from_excel(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    entries = [
        GlossaryEntryIn(term_en=e.term_en, term_vi=e.term_vi, notes=e.notes) for e in parsed
    ]
    return GlossaryImportPreviewResponse(entries=entries, count=len(entries))


@router.post("/import/confirm", response_model=GlossaryImportConfirmResponse)
async def confirm_import(
    request: GlossaryImportConfirmRequest, session: SessionDep
) -> GlossaryImportConfirmResponse:
    manager = GlossaryManager(session)
    entries = [
        GlossaryEntryData(term_en=e.term_en, term_vi=e.term_vi, notes=e.notes)
        for e in request.entries
    ]
    result = await manager.bulk_import(entries, scope=request.scope, project_id=request.project_id)
    return GlossaryImportConfirmResponse(
        imported=result.imported, updated=result.updated, skipped=result.skipped
    )


@router.get("", response_model=GlossaryListResponse)
async def list_entries(
    session: SessionDep, scope: str | None = None, limit: int = 50, offset: int = 0
) -> GlossaryListResponse:
    count_statement = select(func.count()).select_from(GlossaryEntry)
    list_statement = (
        select(GlossaryEntry, Glossary.scope)
        .join(Glossary, Glossary.id == GlossaryEntry.glossary_id)
        .order_by(GlossaryEntry.term_en)
    )
    if scope is not None:
        count_statement = count_statement.join(
            Glossary, Glossary.id == GlossaryEntry.glossary_id
        ).where(Glossary.scope == scope)
        list_statement = list_statement.where(Glossary.scope == scope)

    total_result = await session.exec(count_statement)
    total = total_result.one()

    result = await session.exec(list_statement.limit(limit).offset(offset))
    entries = [_to_out(entry, entry_scope) for entry, entry_scope in result.all()]
    return GlossaryListResponse(entries=entries, total=total, limit=limit, offset=offset)


@router.put("/{entry_id}", response_model=GlossaryEntryOut)
async def update_entry(
    entry_id: str, request: GlossaryEntryUpdate, session: SessionDep
) -> GlossaryEntryOut:
    entry = await session.get(GlossaryEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Khong tim thay glossary entry")

    if request.term_en is not None:
        entry.term_en = request.term_en
    if request.term_vi is not None:
        entry.term_vi = request.term_vi
    if request.notes is not None:
        entry.notes = request.notes
    entry.updated_at = datetime.now(UTC)

    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    glossary = await session.get(Glossary, entry.glossary_id)
    scope = glossary.scope if glossary is not None else "global"
    return _to_out(entry, scope)


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, session: SessionDep) -> dict[str, bool]:
    entry = await session.get(GlossaryEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Khong tim thay glossary entry")

    await session.delete(entry)
    await session.commit()
    return {"ok": True}


@router.get("/export")
async def export_entries(session: SessionDep) -> FileResponse:
    result = await session.exec(select(GlossaryEntry).order_by(GlossaryEntry.term_en))
    entries = [
        GlossaryEntryData(term_en=e.term_en, term_vi=e.term_vi, notes=e.notes)
        for e in result.all()
    ]

    tmp_path = Path(tempfile.mkstemp(suffix=".xlsx")[1])
    export_glossary_to_excel(entries, tmp_path)

    return FileResponse(
        tmp_path,
        filename="glossary_export.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
