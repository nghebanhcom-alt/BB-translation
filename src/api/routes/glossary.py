import json
import logging
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import col, func, select

from src.api.deps import SessionDep
from src.core.config import get_effective_settings
from src.core.glossary_manager import GlossaryManager
from src.models.glossary import Glossary, GlossaryEntry
from src.models.suggested_term import SuggestedTerm
from src.services.provider_factory import ProviderConfigError, ProviderFactory, UnknownProviderError
from src.services.translation import TranslationProviderError
from src.utils.excel_utils import (
    GlossaryEntryData,
    export_glossary_to_excel,
    import_glossary_from_excel,
)

logger = logging.getLogger(__name__)

router = APIRouter()

#: Architecture.md §6.18.4 "suggest-translation — ràng buộc bắt buộc": gộp
#: tối đa 40 term / 1 request LLM (không 1 request/từ).
_MAX_TERMS_PER_SUGGEST_TRANSLATION_REQUEST = 40


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
    #: BR-GLOSS-07 (Architecture.md 6.16.3) — opt-in tuong minh cho DUNG
    #: request nay, khong bao gio la default, khong duoc "nho" cho lan sau
    #: (cung ky luat voi `confirm_cost` cua cost gate 6.11.4 Lop 2).
    force: bool = False


class GlossaryConflictInfo(BaseModel):
    entry_id: str
    term_en: str
    term_vi: str | None
    notes: str | None
    updated_at: datetime


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

    entries = [GlossaryEntryIn(term_en=e.term_en, term_vi=e.term_vi, notes=e.notes) for e in parsed]
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


@router.post("", response_model=GlossaryEntryOut, status_code=201)
async def create_entry(request: GlossaryEntryIn, session: SessionDep) -> GlossaryEntryOut:
    """US moi (2026-09-06): them 1 cap thuat ngu don le tu UI (khac `/import`
    danh cho ca file Excel qua `import_glossary_from_excel()`). Dung lai
    `GlossaryManager.bulk_import()` (BR-GLOSS-03 "last-updated-wins" tren
    trung `term_en`, case-insensitive theo BR-GLOSS-02) voi list 1 phan tu de
    khong nhan doi logic tao-hoac-cap-nhat entry. Scope co dinh "global" —
    UI hien tai (`web/history.html`) chua co lua chon project glossary.

    BR-GLOSS-07 (Architecture.md 6.16.3, US-17): neu `term_en` da trung (case-
    insensitive, BR-GLOSS-02) voi 1 entry co san va `request.force` la False,
    KHONG ghi gi vao DB — tra ve 409 kem thong tin entry cu de client hoi xac
    nhan roi goi lai voi `force=true`. Pham vi CHI ap dung cho luong them-1-
    entry-don-le nay; `bulk_import()` qua `/import/confirm` (Excel hang loat)
    giu nguyen hanh vi ghi de am tham (BR-GLOSS-03 last-updated-wins).
    """
    term_en = request.term_en.strip()
    if not term_en:
        raise HTTPException(status_code=400, detail="term_en khong duoc de trong")

    manager = GlossaryManager(session)
    existing = await manager.get_entry(term_en)
    if existing is not None and not request.force:
        conflict = GlossaryConflictInfo(
            entry_id=existing.id,
            term_en=existing.term_en,
            term_vi=existing.term_vi,
            notes=existing.notes,
            updated_at=existing.updated_at,
        )
        raise HTTPException(
            status_code=409,
            # Cung 1 idiom voi `gate_error_detail()` (src/core/cost_gate.py) —
            # `detail=` la 1 dict, FastAPI/Starlette KHONG chay jsonable_encoder
            # tren no (dung json.dumps thang), nen phai tu convert datetime
            # sang string bang `.model_dump(mode="json")" thay vi truyen thang
            # pydantic model.
            detail={
                "detail": (
                    f"Tu '{existing.term_en}' da co trong glossary voi ban dich "
                    f"'{existing.term_vi or '(chua co)'}'. Ghi de?"
                ),
                "existing": conflict.model_dump(mode="json"),
                "requires_confirmation": True,
            },
        )

    if existing is not None and request.force:
        logger.info(
            "Glossary entry '%s' bi ghi de (force=true): term_vi cu=%r, notes cu=%r "
            "-> term_vi moi=%r, notes moi=%r",
            existing.term_en,
            existing.term_vi,
            existing.notes,
            request.term_vi,
            request.notes,
        )

    await manager.bulk_import(
        [GlossaryEntryData(term_en=term_en, term_vi=request.term_vi, notes=request.notes)],
        scope="global",
        project_id=None,
    )
    entry = await manager.get_entry(term_en)
    if entry is None:  # pragma: no cover - bulk_import vua ghi xong o tren
        raise HTTPException(status_code=500, detail="Loi noi bo: khong tim thay entry vua tao")
    return _to_out(entry, "global")


@router.get("", response_model=GlossaryListResponse)
async def list_entries(
    session: SessionDep,
    scope: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
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

    # US-18 / BR-GLOSS-08 (Architecture.md 6.16.2): tim trong CA term_en lan
    # term_vi. `.contains(needle, autoescape=True)` (KHONG `.ilike()` — xem
    # 6.16.1 G-01/G-02/G-05/G-04) tu dong escape `%`/`_` trong needle.
    # `search_clause` la 1 bien DUY NHAT dung cho ca count_statement va
    # list_statement (YA-2.2) de tranh lech `total` voi so dong tra ve.
    if q is not None and q.strip():
        needle = q.strip()
        search_clause = col(GlossaryEntry.term_en).contains(needle, autoescape=True) | col(
            GlossaryEntry.term_vi
        ).contains(needle, autoescape=True)
        count_statement = count_statement.where(search_clause)
        list_statement = list_statement.where(search_clause)

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
        GlossaryEntryData(term_en=e.term_en, term_vi=e.term_vi, notes=e.notes) for e in result.all()
    ]

    tmp_path = Path(tempfile.mkstemp(suffix=".xlsx")[1])
    export_glossary_to_excel(entries, tmp_path)

    return FileResponse(
        tmp_path,
        filename="glossary_export.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# --- US-20 "Cac tu moi" (Architecture.md 6.18.4) ----------------------------


class SuggestedTermOut(BaseModel):
    id: str
    job_id: str
    term_en: str
    ngram_size: int
    noise_flags: str
    occurrence_count: int
    rank_score: float
    status: str
    suggested_term_vi: str | None
    translation_cost_usd: float | None
    created_at: datetime
    updated_at: datetime


class SuggestedTermListResponse(BaseModel):
    entries: list[SuggestedTermOut]
    total: int
    noise_hidden_count: int
    limit: int
    offset: int


class SuggestedTermPromoteRequest(BaseModel):
    term_vi: str | None = None
    notes: str | None = None
    # US-17 da implement BR-GLOSS-07 tren `create_entry()` (409 xac nhan ghi
    # de khi trung term_en, case-insensitive). Field nay duoc truyen thang
    # (`force=request.force`) vao `GlossaryEntryIn` o `promote_suggested_term()`
    # ben duoi de client co the ghi de co-y-thuc khi promote 1 suggested term
    # trung voi entry da co (vd. do 1 job khac them truoc — PRD US-20 dong 241).
    force: bool = False


def _to_suggested_out(row: SuggestedTerm) -> SuggestedTermOut:
    return SuggestedTermOut(
        id=row.id,
        job_id=row.job_id,
        term_en=row.term_en,
        ngram_size=row.ngram_size,
        noise_flags=row.noise_flags,
        occurrence_count=row.occurrence_count,
        rank_score=row.rank_score,
        status=row.status,
        suggested_term_vi=row.suggested_term_vi,
        translation_cost_usd=row.translation_cost_usd,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/suggested", response_model=SuggestedTermListResponse)
async def list_suggested_terms(
    session: SessionDep,
    job_id: str | None = None,
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
    sort: str = "rank",
    min_ngram: int = 1,
    include_noise: bool = False,
) -> SuggestedTermListResponse:
    """Architecture.md 6.18.4: `job_id` bo trong = gop moi job (khu vuc "Cho
    duyet" chung trong tab Glossary). `total`/`noise_hidden_count` la so dem
    THEO filter status/job_id/min_ngram (truoc khi ap `include_noise`) — UI
    dung 2 so nay de hien nut "Hien them N muc nghi nhiem" dung so.
    """
    if sort not in {"rank", "count", "alpha"}:
        raise HTTPException(status_code=400, detail="sort phai la 'rank' | 'count' | 'alpha'")

    base_conditions = [SuggestedTerm.status == status, SuggestedTerm.ngram_size >= min_ngram]
    if job_id is not None:
        base_conditions.append(SuggestedTerm.job_id == job_id)

    total_result = await session.exec(
        select(func.count()).select_from(SuggestedTerm).where(*base_conditions)
    )
    total = total_result.one()

    noise_result = await session.exec(
        select(func.count())
        .select_from(SuggestedTerm)
        .where(*base_conditions, SuggestedTerm.noise_flags != "")
    )
    noise_hidden_count = noise_result.one()

    list_conditions = list(base_conditions)
    if not include_noise:
        list_conditions.append(SuggestedTerm.noise_flags == "")

    list_statement = select(SuggestedTerm).where(*list_conditions)
    if sort == "count":
        list_statement = list_statement.order_by(SuggestedTerm.occurrence_count.desc())
    elif sort == "alpha":
        list_statement = list_statement.order_by(SuggestedTerm.term_en)
    else:
        list_statement = list_statement.order_by(SuggestedTerm.rank_score.desc())
    list_statement = list_statement.limit(limit).offset(offset)

    rows = (await session.exec(list_statement)).all()
    return SuggestedTermListResponse(
        entries=[_to_suggested_out(row) for row in rows],
        total=total,
        noise_hidden_count=noise_hidden_count,
        limit=limit,
        offset=offset,
    )


@router.post("/suggested/{suggested_id}/dismiss", status_code=204)
async def dismiss_suggested_term(suggested_id: str, session: SessionDep) -> Response:
    """BR-TERM-04: chi an trong pham vi job do (KHONG blacklist toan cuc —
    khong co status 'rejected', chi 'dismissed' per-row cua chinh job nay).
    """
    row = await session.get(SuggestedTerm, suggested_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Khong tim thay suggested term")

    row.status = "dismissed"
    row.updated_at = datetime.now(UTC)
    session.add(row)
    await session.commit()
    return Response(status_code=204)


@router.post("/suggested/{suggested_id}/promote", response_model=GlossaryEntryOut)
async def promote_suggested_term(
    suggested_id: str, request: SuggestedTermPromoteRequest, session: SessionDep
) -> GlossaryEntryOut:
    """Architecture.md 6.18.4: phai di qua DUNG logic `POST /api/glossary`
    (goi thang `create_entry()` cung module, khong viet lai). Tu khi US-17
    implement BR-GLOSS-07 (409 khi trung `term_en` + `force=false`),
    `create_entry()` co the raise `HTTPException(409, ...)` — vi day la loi
    goi ham Python binh thuong (khong qua router), exception nay tu propagate
    len thanh response 409 CUA CHINH endpoint promote nay (FastAPI bat
    `HTTPException` o bat ky do sau trong call stack cua 1 route handler),
    dung y PRD US-20 dong 241 "ap dung BR-GLOSS-07 neu lo trung do co job
    khac them truoc". `request.force` duoc truyen thang xuong de client co
    the ghi de co-y-thuc.
    """
    row = await session.get(SuggestedTerm, suggested_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Khong tim thay suggested term")
    if row.status != "pending":
        raise HTTPException(
            status_code=400, detail=f"Suggested term dang status={row.status!r}, khong the promote"
        )

    entry_out = await create_entry(
        GlossaryEntryIn(
            term_en=row.term_en,
            term_vi=request.term_vi,
            notes=request.notes,
            force=request.force,
        ),
        session,
    )

    row.status = "added"
    row.updated_at = datetime.now(UTC)
    session.add(row)
    await session.commit()
    return entry_out


class SuggestTranslationRequest(BaseModel):
    ids: list[str]


class SuggestTranslationResponse(BaseModel):
    updated: int
    total_cost_usd: float


_SUGGEST_TRANSLATION_PROMPT = """Ban la chuyen gia dich thuat nganh banh (English -> Vietnamese).
Voi moi thuat ngu tieng Anh duoi day, dua ra 1 ban dich tieng Viet ngan gon, \
dung thuat ngu chuyen nganh banh dang dung trong sach day. Neu thuat ngu goc \
tieng Phap/Y ma nguoi Viet trong nganh thuong giu nguyen, tra ve chuoi \
"(keep)" cho thuat ngu do thay vi dich.

CHI tra ve 1 doi tuong JSON hop le, KHONG giai thich gi them, dung dang:
{{"thuat ngu goc 1": "ban dich 1", "thuat ngu goc 2": "ban dich 2"}}

Danh sach thuat ngu can dich:
{terms_block}
"""

_JSON_PAIR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _build_suggest_translation_prompt(terms: list[str]) -> str:
    terms_block = "\n".join(f"- {term}" for term in terms)
    return _SUGGEST_TRANSLATION_PROMPT.format(terms_block=terms_block)


def _parse_translation_json(raw_text: str) -> dict[str, str]:
    """Best-effort JSON parse of the LLM response. `[CHUA VERIFY]`: khong co
    API key that trong moi truong dev nay de xac nhan cac provider (DeepSeek
    mac dinh, Claude/OpenAI/Gemini/Ollama) THAT SU tuan thu dung dinh dang
    JSON duoc yeu cau trong prompt — day la 1 diem Dev khong tu verify duoc,
    ghi ro de PM/QA biet can smoke-test that truoc khi coi tinh nang nay la
    xong (tinh than Protocol 5 R5-03, du day la hanh vi prompt-engineering
    noi bo chu khong phai contract API cua provider). Fallback regex duoi day
    (`_JSON_PAIR_RE`) chi la luoi an toan cho truong hop LLM tra ve JSON kem
    van ban giai thich thua quanh no, KHONG thay the cho viec verify that.
    """
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError):
        pass

    return dict(_JSON_PAIR_RE.findall(raw_text))


def _find_translation(translations: dict[str, str], term_en: str) -> str | None:
    if term_en in translations:
        return translations[term_en]
    lowered = term_en.lower()
    for key, value in translations.items():
        if key.lower() == lowered:
            return value
    return None


@router.post("/suggested/suggest-translation", response_model=SuggestTranslationResponse)
async def suggest_translation_for_terms(
    request: SuggestTranslationRequest, session: SessionDep
) -> SuggestTranslationResponse:
    """Architecture.md 6.18.4 "suggest-translation — rang buoc bat buoc":
    hanh dong DUY NHAT ton tien trong US-20 (BR-TERM-03). Goi
    `provider.translate()` (KHONG phai tu goi httpx/SDK truc tiep) de co
    `TranslationResult.estimated_cost_usd` that, chia deu cho tung term
    trong CUNG 1 batch (moi batch <=40 term = 1 request LLM). KHONG cong vao
    `job.actual_cost` — chi phi nay bao cao rieng qua chinh
    `suggested_terms.translation_cost_usd` (Job khong bi dung toi o day).
    """
    if not request.ids:
        raise HTTPException(status_code=400, detail="ids khong duoc de trong")

    rows: list[SuggestedTerm] = []
    for suggested_id in request.ids:
        row = await session.get(SuggestedTerm, suggested_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Khong tim thay suggested term {suggested_id}"
            )
        if row.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Suggested term {suggested_id} dang status={row.status!r}",
            )
        rows.append(row)

    settings = await get_effective_settings(session)
    try:
        provider = ProviderFactory.create(settings.default_provider, settings)
    except (UnknownProviderError, ProviderConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated = 0
    total_cost = 0.0
    for start in range(0, len(rows), _MAX_TERMS_PER_SUGGEST_TRANSLATION_REQUEST):
        batch = rows[start : start + _MAX_TERMS_PER_SUGGEST_TRANSLATION_REQUEST]
        prompt = _build_suggest_translation_prompt([row.term_en for row in batch])
        try:
            result = await provider.translate(
                text=prompt, glossary_prompt="", source_lang="en", target_lang="vi"
            )
        except TranslationProviderError as exc:
            raise HTTPException(status_code=502, detail=f"Loi goi LLM: {exc}") from exc

        translations = _parse_translation_json(result.text)
        per_term_cost = result.estimated_cost_usd / len(batch) if batch else 0.0
        for row in batch:
            row.suggested_term_vi = _find_translation(translations, row.term_en)
            row.translation_cost_usd = per_term_cost
            row.updated_at = datetime.now(UTC)
            session.add(row)
            updated += 1
        total_cost += result.estimated_cost_usd

    await session.commit()
    return SuggestTranslationResponse(updated=updated, total_cost_usd=total_cost)
