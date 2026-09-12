"""K-2/K-3 (Architecture.md §6.20.15) — `reasoning_tokens`/`answer_tokens`
extraction and the `disable_thinking`/`supports_thinking_toggle` mechanism.

R5-02/R5-03: mocks below are built FROM the real captured
`response.usage.model_dump()` golden file
(`tests/fixtures/epub_llm/deepseek_v4flash_usage.json`, spike run
2026-09-11 against `deepseek-v4-flash`), NOT hand-typed per Architecture.md's
description — see the golden file for provenance.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.services.deepseek_provider import DeepSeekProvider
from src.services.openai_provider import OpenAIProvider

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "epub_llm" / "deepseek_v4flash_usage.json"


def _load_golden() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _to_namespace(value: Any) -> Any:
    """Recursively converts a plain dict (as produced by
    `BaseModel.model_dump()`) back into an object exposing the SAME
    attribute access shape as the real `openai` SDK response object, so the
    provider code (`getattr(response.usage, "completion_tokens_details",
    None)`, etc.) exercises the exact same code path it would against a
    real SDK response."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in value.items()})
    return value


@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    usage: Any
    choices: list = field(default_factory=list)


def _fake_response_from_golden_case(case: dict) -> _FakeResponse:
    usage_ns = _to_namespace(case["usage"])
    return _FakeResponse(
        usage=usage_ns,
        choices=[_FakeChoice(message=_FakeMessage(content=case["text_preview"]))],
    )


class _StubCompletions:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.received_kwargs: dict | None = None

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.received_kwargs = kwargs
        return self._response


class _StubChat:
    def __init__(self, completions: _StubCompletions) -> None:
        self.completions = completions


class _StubClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.completions = _StubCompletions(response)
        self.chat = _StubChat(self.completions)


pytestmark = pytest.mark.asyncio


async def test_reasoning_tokens_extracted_when_thinking_enabled() -> None:
    """S7/K-2 verified live (spike R5-02, 2026-09-11):
    `completion_tokens_details.reasoning_tokens` exists and is non-zero
    (833) on a real deepseek-v4-flash response with thinking mode at its
    default (`high`). `output_tokens` must stay the RAW `completion_tokens`
    (833 reasoning + 100 actual translation = 933) — billing must never be
    understated (§6.11.6)."""
    golden = _load_golden()["baseline_thinking_default"]
    response = _fake_response_from_golden_case(golden)
    provider = DeepSeekProvider(api_key="sk-test")
    provider._client = _StubClient(response)

    result = await provider.translate("hello", "system", "en", "vi")

    assert result.output_tokens == 933
    assert result.reasoning_tokens == 833
    assert result.answer_tokens == 100


async def test_reasoning_tokens_zero_when_completion_tokens_details_absent() -> None:
    """Verified live: when `extra_body={"thinking": {"type": "disabled"}}` is
    accepted, DeepSeek's response drops `completion_tokens_details`
    entirely (`None`, not an object with `reasoning_tokens=0`) — the
    `getattr(None, "reasoning_tokens", 0) or 0` chain in
    `OpenAIProvider.translate()` must handle this without raising, ending
    up with `answer_tokens == output_tokens`."""
    golden = _load_golden()["thinking_disabled"]
    assert golden["usage"]["completion_tokens_details"] is None
    response = _fake_response_from_golden_case(golden)
    provider = DeepSeekProvider(api_key="sk-test")
    provider._client = _StubClient(response)

    result = await provider.translate("hello", "system", "en", "vi")

    assert result.output_tokens == 97
    assert result.reasoning_tokens == 0
    assert result.answer_tokens == 97


async def test_plain_openai_provider_defaults_reasoning_tokens_to_zero() -> None:
    """A provider whose SDK response has no `completion_tokens_details` at
    all (e.g. plain OpenAI models, or any provider not offering the field)
    must default to `reasoning_tokens=0`/`answer_tokens==output_tokens`,
    not raise `AttributeError`."""
    usage_ns = SimpleNamespace(prompt_tokens=10, completion_tokens=42)
    response = _FakeResponse(
        usage=usage_ns, choices=[_FakeChoice(message=_FakeMessage(content="hi"))]
    )
    provider = OpenAIProvider(api_key="sk-test")
    provider._client = _StubClient(response)

    result = await provider.translate("hello", "system", "en", "vi")

    assert result.output_tokens == 42
    assert result.reasoning_tokens == 0
    assert result.answer_tokens == 42


async def test_extra_body_not_sent_when_disable_thinking_false() -> None:
    """K-3 default: `disable_thinking=False` on a fresh provider instance ->
    hanh vi KHONG doi mot byte, `extra_body` khong duoc truyen."""
    golden = _load_golden()["baseline_thinking_default"]
    response = _fake_response_from_golden_case(golden)
    provider = DeepSeekProvider(api_key="sk-test")
    stub_client = _StubClient(response)
    provider._client = stub_client

    await provider.translate("hello", "system", "en", "vi")

    assert "extra_body" not in stub_client.completions.received_kwargs


async def test_extra_body_sent_when_disable_thinking_true() -> None:
    """K-3 verified live (spike R5-02, 2026-09-11): endpoint DeepSeek chap
    nhan `extra_body={"thinking": {"type": "disabled"}}` (khong HTTP 400).
    Khi `disable_thinking=True` tren instance, `translate()` phai truyen
    DUNG key/format nay."""
    golden = _load_golden()["thinking_disabled"]
    response = _fake_response_from_golden_case(golden)
    provider = DeepSeekProvider(api_key="sk-test")
    provider.disable_thinking = True
    stub_client = _StubClient(response)
    provider._client = stub_client

    await provider.translate("hello", "system", "en", "vi")

    assert stub_client.completions.received_kwargs["extra_body"] == {
        "thinking": {"type": "disabled"}
    }


async def test_extra_body_not_sent_for_provider_without_thinking_toggle() -> None:
    """R8-03 — plain `OpenAIProvider` (`supports_thinking_toggle=False`)
    must never send `extra_body` even if some caller mistakenly sets
    `disable_thinking=True` on it (defensive: capability gate, not the
    per-instance flag alone, decides)."""
    usage_ns = SimpleNamespace(prompt_tokens=10, completion_tokens=42)
    response = _FakeResponse(
        usage=usage_ns, choices=[_FakeChoice(message=_FakeMessage(content="hi"))]
    )
    provider = OpenAIProvider(api_key="sk-test")
    provider.disable_thinking = True
    stub_client = _StubClient(response)
    provider._client = stub_client

    await provider.translate("hello", "system", "en", "vi")

    assert "extra_body" not in stub_client.completions.received_kwargs
