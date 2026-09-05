"""Increment 6, Nhiem vu 2: `provider_models` on `PUT /api/settings` and its
effect through `get_effective_settings()`.

`claude_model`/`openai_model`/`deepseek_model`/`gemini_model` were already
`SETTINGS_DB_OVERRIDABLE_FIELDS` since Increment 5 (src/core/config.py) —
this increment only adds the request/response fields on top
(`src/api/routes/settings.py`) that let the UI reach that existing
mechanism. These tests verify the field actually reaches
`get_effective_settings()`, not just that the HTTP round-trip echoes it back.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import src.models.database as database_module
from src.api.main import app
from src.core.config import get_effective_settings, get_settings


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    database_module._engine = None
    database_module._session_factory = None

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()
        database_module._engine = None
        database_module._session_factory = None


def test_openai_model_defaults_to_gpt_4o_mini() -> None:
    """Nhiem vu 2, bug context: the $3.22-for-one-book estimate the user saw
    came from the old `gpt-4o` default — this is the actual default-change
    fix, not just the settings-override plumbing around it."""
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.openai_model == "gpt-4o-mini"


def test_get_settings_reports_current_model_per_provider(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["openai"]["model"] == "gpt-4o-mini"
    assert body["providers"]["deepseek"]["model"] == "deepseek-chat"
    # deepl has no selectable model.
    assert body["providers"]["deepl"]["model"] is None


def test_put_provider_models_overrides_effective_settings(client: TestClient) -> None:
    response = client.put(
        "/api/settings", json={"provider_models": {"openai": "gpt-4o", "deepseek": "deepseek-reasoner"}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["openai"]["model"] == "gpt-4o"
    assert body["providers"]["deepseek"]["model"] == "deepseek-reasoner"

    # GET reflects the same DB-backed override, not just the PUT echo.
    get_response = client.get("/api/settings")
    assert get_response.json()["providers"]["openai"]["model"] == "gpt-4o"

    # And it must actually be what ProviderFactory.create()/JobOrchestrator
    # would see — this is the real bug this endpoint fixes, not just an API
    # round-trip.
    async def _check_effective():
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            return await get_effective_settings(session)

    import asyncio

    effective = asyncio.run(_check_effective())
    assert effective.openai_model == "gpt-4o"
    assert effective.deepseek_model == "deepseek-reasoner"
    # Untouched providers keep their untouched default.
    assert effective.gemini_model == "gemini-2.5-pro"


def test_put_provider_models_ignores_unknown_provider_name(client: TestClient) -> None:
    response = client.put("/api/settings", json={"provider_models": {"not-a-provider": "x"}})
    assert response.status_code == 200
    # Must not crash / must not silently create a bogus Setting row that
    # later confuses get_effective_settings() casting.
    assert "not-a-provider" not in response.json()["providers"]


# === Architecture.md 6.11.4 Lop 2 — cost cap settings ===


def test_get_settings_reports_cost_cap_defaults(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["max_cost_per_job_usd"] == 2.00
    assert body["max_cost_per_batch_usd"] == 5.00
    assert body["cost_cap_enabled"] is True


def test_put_cost_cap_settings_overrides_effective_settings(client: TestClient) -> None:
    response = client.put(
        "/api/settings",
        json={"max_cost_per_job_usd": 0.5, "max_cost_per_batch_usd": 1.5, "cost_cap_enabled": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["max_cost_per_job_usd"] == 0.5
    assert body["max_cost_per_batch_usd"] == 1.5
    assert body["cost_cap_enabled"] is False

    get_response = client.get("/api/settings")
    assert get_response.json()["max_cost_per_job_usd"] == 0.5

    async def _check_effective():
        session_factory = database_module.get_session_factory()
        async with session_factory() as session:
            return await get_effective_settings(session)

    import asyncio

    effective = asyncio.run(_check_effective())
    assert effective.max_cost_per_job_usd == 0.5
    assert effective.max_cost_per_batch_usd == 1.5
    assert effective.cost_cap_enabled is False
