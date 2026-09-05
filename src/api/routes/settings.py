"""GET/PUT /api/settings (Architecture.md section 5.1).

`PUT` writes to the `settings` DB table (src/models/settings.py), never to
`.env` — see `src.core.config.get_effective_settings()` for how those DB
rows are layered back on top of the `.env`-sourced `Settings` singleton at
read time. This is the "DB settings override .env" design decision recorded
in docs/CHANGELOG.md "Increment 5".
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.deps import SessionDep
from src.core.config import get_effective_settings
from src.models.settings import Setting

router = APIRouter()

#: provider name (as used by ProviderFactory/Pdf2zhServiceMapper) -> the
#: Settings field holding its API key / connection string.
_PROVIDER_KEY_FIELDS = {
    "claude": "claude_api_key",
    "openai": "openai_api_key",
    "deepseek": "deepseek_api_key",
    "gemini": "gemini_api_key",
    "deepl": "deepl_api_key",
    "ollama": "ollama_endpoint",
}

#: Increment 6 (Nhiem vu 2): provider name -> the `Settings` field holding
#: its model string. `deepl` has no selectable model (1 fixed API), so it is
#: deliberately absent here — same reasoning `_PROVIDER_KEY_FIELDS` already
#: applies to fields that don't exist for every provider.
_PROVIDER_MODEL_FIELDS = {
    "claude": "claude_model",
    "openai": "openai_model",
    "deepseek": "deepseek_model",
    "gemini": "gemini_model",
    "ollama": "ollama_model",
}


class ProviderStatus(BaseModel):
    has_key: bool
    #: `None` for providers with no selectable model (deepl).
    model: str | None = None


class SettingsResponse(BaseModel):
    default_provider: str
    max_concurrent_files: int
    max_upload_size_mb: int
    providers: dict[str, ProviderStatus]
    # Architecture.md 6.11.4 Lop 2 — user-tunable via this same PUT endpoint
    # (spec: "expose qua PUT /api/settings de user tu chinh duoc").
    max_cost_per_job_usd: float
    max_cost_per_batch_usd: float
    cost_cap_enabled: bool
    # Architecture.md 6.12.6 — user-tunable exception inside AIMD's block:
    # the right value depends on the user's own hardware (VRAM/cores), so it
    # is exposed here even though every other concurrency knob stays
    # code-only.
    ollama_thread: int


class SettingsUpdateRequest(BaseModel):
    default_provider: str | None = None
    max_concurrent_files: int | None = None
    #: provider name -> api_key (or, for "ollama", the endpoint URL).
    provider_api_keys: dict[str, str] | None = None
    #: provider name -> model string (Increment 6, Nhiem vu 2). Reuses the
    #: same `SETTINGS_DB_OVERRIDABLE_FIELDS`/`get_effective_settings()`
    #: mechanism as `provider_api_keys` — `claude_model`/`openai_model`/
    #: `deepseek_model`/`gemini_model` were already DB-overridable fields
    #: since Increment 5, just never exposed through this request model.
    provider_models: dict[str, str] | None = None
    #: Architecture.md 6.11.4 Lop 2 — the pre-flight cost gate's thresholds,
    #: user-tunable from the Settings page (RC-3 fix: no cap existed at any
    #: layer before the $6.50 incident).
    max_cost_per_job_usd: float | None = None
    max_cost_per_batch_usd: float | None = None
    cost_cap_enabled: bool | None = None
    #: Architecture.md 6.12.6 — Ollama's fixed thread count (no AIMD signal
    #: exists for a local model), the one concurrency knob depending on the
    #: user's own hardware rather than something the app can learn.
    ollama_thread: int | None = None


async def _build_response(session: SessionDep) -> SettingsResponse:
    settings = await get_effective_settings(session)
    providers = {
        name: ProviderStatus(
            has_key=bool(getattr(settings, field)),
            model=getattr(settings, _PROVIDER_MODEL_FIELDS[name], None)
            if name in _PROVIDER_MODEL_FIELDS
            else None,
        )
        for name, field in _PROVIDER_KEY_FIELDS.items()
    }
    return SettingsResponse(
        default_provider=settings.default_provider,
        max_concurrent_files=settings.max_concurrent_files,
        max_upload_size_mb=settings.max_upload_size_mb,
        providers=providers,
        max_cost_per_job_usd=settings.max_cost_per_job_usd,
        max_cost_per_batch_usd=settings.max_cost_per_batch_usd,
        cost_cap_enabled=settings.cost_cap_enabled,
        ollama_thread=settings.ollama_thread,
    )


async def _upsert_setting(session: SessionDep, key: str, value: str) -> None:
    row = await session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
    else:
        row.value = value
        row.updated_at = datetime.now(UTC)
    session.add(row)


@router.get("", response_model=SettingsResponse)
async def get_settings_endpoint(session: SessionDep) -> SettingsResponse:
    return await _build_response(session)


@router.put("", response_model=SettingsResponse)
async def update_settings_endpoint(
    request: SettingsUpdateRequest, session: SessionDep
) -> SettingsResponse:
    if request.default_provider is not None:
        await _upsert_setting(session, "default_provider", request.default_provider)

    if request.max_concurrent_files is not None:
        await _upsert_setting(session, "max_concurrent_files", str(request.max_concurrent_files))

    if request.provider_api_keys:
        for provider_name, api_key in request.provider_api_keys.items():
            field = _PROVIDER_KEY_FIELDS.get(provider_name)
            if field is None:
                continue
            await _upsert_setting(session, field, api_key)

    if request.provider_models:
        for provider_name, model in request.provider_models.items():
            field = _PROVIDER_MODEL_FIELDS.get(provider_name)
            if field is None:
                continue
            await _upsert_setting(session, field, model)

    if request.max_cost_per_job_usd is not None:
        await _upsert_setting(session, "max_cost_per_job_usd", str(request.max_cost_per_job_usd))

    if request.max_cost_per_batch_usd is not None:
        await _upsert_setting(
            session, "max_cost_per_batch_usd", str(request.max_cost_per_batch_usd)
        )

    if request.cost_cap_enabled is not None:
        await _upsert_setting(session, "cost_cap_enabled", str(request.cost_cap_enabled))

    if request.ollama_thread is not None:
        await _upsert_setting(session, "ollama_thread", str(request.ollama_thread))

    await session.commit()
    return await _build_response(session)
