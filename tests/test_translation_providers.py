"""Unit tests for TranslationProvider implementations. All external SDK calls
are mocked — no real API keys or network calls involved.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anthropic
import deepl
import google.api_core.exceptions as google_exceptions
import httpx
import openai
import pytest

from src.services.claude_provider import ClaudeProvider
from src.services.deepl_provider import DeepLProvider
from src.services.deepseek_provider import DeepSeekProvider
from src.services.gemini_provider import GeminiProvider
from src.services.ollama_provider import OllamaProvider
from src.services.openai_provider import OpenAIProvider
from src.services.translation import (
    AuthenticationError,
    RateLimitError,
    TranslationProviderError,
)
from src.utils.retry import _TRANSIENT_ERRORS

#: Y6 (Architecture.md 6.20.12): every "5xx / connection / timeout" mapping
#: added below must land on one of these — the SAME tuple `with_retry()`
#: (src/utils/retry.py) actually checks. Asserting membership here (not just
#: `pytest.raises(ConnectionError)`) is what makes these tests catch a future
#: regression back to `TranslationProviderError` (permanent, never retried).
assert _TRANSIENT_ERRORS == (RateLimitError, TimeoutError, ConnectionError)

# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claude_translate_success(mocker) -> None:
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Ban dich")],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=fake_response)
    mocker.patch("src.services.claude_provider.anthropic.AsyncAnthropic", return_value=mock_client)

    provider = ClaudeProvider(api_key="sk-ant-fake")
    result = await provider.translate("hello", "glossary", "en", "vi")

    assert result.text == "Ban dich"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.provider_name == "claude"
    assert result.estimated_cost_usd == pytest.approx(100 / 1_000_000 * 2.0 + 50 / 1_000_000 * 10.0)

    # Prompt caching enabled by default.
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_claude_translate_auth_error(mocker) -> None:
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.AuthenticationError(
            message="bad key", response=MagicMock(status_code=401), body=None
        )
    )
    mocker.patch("src.services.claude_provider.anthropic.AsyncAnthropic", return_value=mock_client)

    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(AuthenticationError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_claude_translate_rate_limit_error(mocker) -> None:
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.RateLimitError(
            message="slow down", response=MagicMock(status_code=429), body=None
        )
    )
    mocker.patch("src.services.claude_provider.anthropic.AsyncAnthropic", return_value=mock_client)

    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(RateLimitError):
        await provider.translate("hello", "glossary", "en", "vi")


def test_claude_estimate_cost() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    cost = provider.estimate_cost(1_000_000, 1_000_000)
    assert cost == pytest.approx(2.0 + 10.0)


# --- Y6 (Architecture.md 6.20.12): 5xx/connection/timeout must map onto a
# _TRANSIENT_ERRORS member (retried by with_retry()), NOT the permanent
# TranslationProviderError the old code used to raise for every one of these.


@pytest.mark.asyncio
async def test_claude_translate_timeout_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=MagicMock())
    )
    mocker.patch("src.services.claude_provider.anthropic.AsyncAnthropic", return_value=mock_client)

    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(TimeoutError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_claude_translate_connection_error_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.APIConnectionError(request=MagicMock())
    )
    mocker.patch("src.services.claude_provider.anthropic.AsyncAnthropic", return_value=mock_client)

    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_claude_translate_5xx_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.InternalServerError(
            message="upstream overloaded", response=MagicMock(status_code=503), body=None
        )
    )
    mocker.patch("src.services.claude_provider.anthropic.AsyncAnthropic", return_value=mock_client)

    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_translate_success(mocker) -> None:
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Ban dich"))],
        usage=SimpleNamespace(prompt_tokens=80, completion_tokens=40),
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)
    mocker.patch("src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client)

    provider = OpenAIProvider(api_key="sk-fake")
    result = await provider.translate("hello", "glossary", "en", "vi")

    assert result.text == "Ban dich"
    assert result.input_tokens == 80
    assert result.output_tokens == 40
    assert result.provider_name == "openai"


@pytest.mark.asyncio
async def test_openai_translate_rate_limit_error(mocker) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.RateLimitError(
            message="slow down", response=MagicMock(status_code=429), body=None
        )
    )
    mocker.patch("src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client)

    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(RateLimitError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_openai_translate_timeout_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock())
    )
    mocker.patch("src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client)

    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(TimeoutError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_openai_translate_connection_error_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.APIConnectionError(request=MagicMock())
    )
    mocker.patch("src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client)

    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_openai_translate_5xx_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.InternalServerError(
            message="upstream overloaded", response=MagicMock(status_code=502), body=None
        )
    )
    mocker.patch("src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client)

    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_openai_translate_bad_request_stays_permanent(mocker) -> None:
    """Y6 only widens the TRANSIENT set — a genuine 4xx (not 429) must stay
    permanent (`TranslationProviderError`), never silently start retrying."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.BadRequestError(
            message="invalid request", response=MagicMock(status_code=400), body=None
        )
    )
    mocker.patch("src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client)

    provider = OpenAIProvider(api_key="sk-fake")
    with pytest.raises(TranslationProviderError):
        await provider.translate("hello", "glossary", "en", "vi")


# ---------------------------------------------------------------------------
# DeepSeek (reuses OpenAIProvider)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepseek_translate_uses_openai_compatible_client(mocker) -> None:
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Ban dich re"))],
        usage=SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=1_000_000),
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_response)
    mock_ctor = mocker.patch(
        "src.services.openai_provider.openai.AsyncOpenAI", return_value=mock_client
    )

    provider = DeepSeekProvider(api_key="sk-fake")
    result = await provider.translate("hello", "glossary", "en", "vi")

    assert result.provider_name == "deepseek"
    assert result.estimated_cost_usd == pytest.approx(0.22 + 0.66)
    mock_ctor.assert_called_once_with(api_key="sk-fake", base_url="https://api.deepseek.com")


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_translate_success(mocker) -> None:
    fake_response = SimpleNamespace(
        text="Ban dich",
        usage_metadata=SimpleNamespace(prompt_token_count=60, candidates_token_count=30),
    )
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=fake_response)
    mocker.patch("src.services.gemini_provider.genai.configure")
    mocker.patch(
        "src.services.gemini_provider.genai.GenerativeModel", return_value=mock_model
    )

    provider = GeminiProvider(api_key="AIza-fake")
    result = await provider.translate("hello", "glossary", "en", "vi")

    assert result.text == "Ban dich"
    assert result.input_tokens == 60
    assert result.output_tokens == 30
    assert result.provider_name == "gemini"


@pytest.mark.asyncio
async def test_gemini_translate_rate_limit_error(mocker) -> None:
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(
        side_effect=google_exceptions.ResourceExhausted("quota exceeded")
    )
    mocker.patch("src.services.gemini_provider.genai.configure")
    mocker.patch(
        "src.services.gemini_provider.genai.GenerativeModel", return_value=mock_model
    )

    provider = GeminiProvider(api_key="AIza-fake")
    with pytest.raises(RateLimitError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_gemini_translate_auth_error(mocker) -> None:
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(
        side_effect=google_exceptions.Unauthenticated("bad key")
    )
    mocker.patch("src.services.gemini_provider.genai.configure")
    mocker.patch(
        "src.services.gemini_provider.genai.GenerativeModel", return_value=mock_model
    )

    provider = GeminiProvider(api_key="AIza-fake")
    with pytest.raises(AuthenticationError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_gemini_translate_deadline_exceeded_is_transient(mocker) -> None:
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(
        side_effect=google_exceptions.DeadlineExceeded("timed out")
    )
    mocker.patch("src.services.gemini_provider.genai.configure")
    mocker.patch(
        "src.services.gemini_provider.genai.GenerativeModel", return_value=mock_model
    )

    provider = GeminiProvider(api_key="AIza-fake")
    with pytest.raises(TimeoutError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_gemini_translate_5xx_is_transient(mocker) -> None:
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(
        side_effect=google_exceptions.ServiceUnavailable("upstream overloaded")
    )
    mocker.patch("src.services.gemini_provider.genai.configure")
    mocker.patch(
        "src.services.gemini_provider.genai.GenerativeModel", return_value=mock_model
    )

    provider = GeminiProvider(api_key="AIza-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


# ---------------------------------------------------------------------------
# DeepL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepl_translate_success(mocker) -> None:
    fake_result = SimpleNamespace(text="Ban dich")
    mock_translator = MagicMock()
    mock_translator.translate_text = MagicMock(return_value=fake_result)
    mocker.patch("src.services.deepl_provider.deepl.Translator", return_value=mock_translator)

    provider = DeepLProvider(api_key="deepl-fake")
    result = await provider.translate("hello world", "glossary", "en", "vi")

    assert result.text == "Ban dich"
    assert result.provider_name == "deepl"
    assert result.input_tokens > 0
    assert result.output_tokens > 0


@pytest.mark.asyncio
async def test_deepl_translate_auth_error(mocker) -> None:
    mock_translator = MagicMock()
    mock_translator.translate_text = MagicMock(
        side_effect=deepl.AuthorizationException("bad key")
    )
    mocker.patch("src.services.deepl_provider.deepl.Translator", return_value=mock_translator)

    provider = DeepLProvider(api_key="deepl-fake")
    with pytest.raises(AuthenticationError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_deepl_translate_connection_error_is_transient(mocker) -> None:
    mock_translator = MagicMock()
    mock_translator.translate_text = MagicMock(
        side_effect=deepl.ConnectionException("upstream unreachable", should_retry=True)
    )
    mocker.patch("src.services.deepl_provider.deepl.Translator", return_value=mock_translator)

    provider = DeepLProvider(api_key="deepl-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_deepl_translate_5xx_is_transient(mocker) -> None:
    """Y6 fix (US-22 Buoc 2/3, vong 1/3 review — issue #2, Reviewer tu doc
    source `deepl==1.32.0` xac nhan): 1 response 5xx THAT tu server DeepL
    (vd 502) khong di qua `deepl.ConnectionException` (chi bao phu transport
    — khong nhan duoc response nao ca) ma raise `deepl.DeepLException` thuong
    voi `http_status_code=502` — phai duoc map thanh `ConnectionError`
    (transient), khong phai `TranslationProviderError` (permanent)."""
    mock_translator = MagicMock()
    mock_translator.translate_text = MagicMock(
        side_effect=deepl.DeepLException(
            "Internal server error", should_retry=True, http_status_code=502
        )
    )
    mocker.patch("src.services.deepl_provider.deepl.Translator", return_value=mock_translator)

    provider = DeepLProvider(api_key="deepl-fake")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_deepl_translate_4xx_stays_permanent(mocker) -> None:
    """Y6 chi mo rong tap TRANSIENT cho 5xx — 1 loi client that (khong phai
    429, da co except rieng) phai giu nguyen permanent, khong duoc am tham
    bat dau retry vo ich."""
    mock_translator = MagicMock()
    mock_translator.translate_text = MagicMock(
        side_effect=deepl.DeepLException("Bad request", should_retry=False, http_status_code=400)
    )
    mocker.patch("src.services.deepl_provider.deepl.Translator", return_value=mock_translator)

    provider = DeepLProvider(api_key="deepl-fake")
    with pytest.raises(TranslationProviderError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_deepl_translate_exception_without_status_code_stays_permanent(mocker) -> None:
    """`http_status_code` co the la `None` (loi khong gan voi 1 response HTTP
    cu the nao — vd loi parse noi bo cua SDK) — phai fallback ve permanent,
    khong duoc coi `None >= 500` (se raise TypeError) hay am tham thanh transient."""
    mock_translator = MagicMock()
    mock_translator.translate_text = MagicMock(
        side_effect=deepl.DeepLException("Unexpected SDK error", should_retry=False)
    )
    mocker.patch("src.services.deepl_provider.deepl.Translator", return_value=mock_translator)

    provider = DeepLProvider(api_key="deepl-fake")
    with pytest.raises(TranslationProviderError):
        await provider.translate("hello", "glossary", "en", "vi")


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_translate_success(mocker) -> None:
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "response": "Ban dich",
        "prompt_eval_count": 20,
        "eval_count": 10,
    }
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.services.ollama_provider.httpx.AsyncClient", return_value=mock_client)

    provider = OllamaProvider(endpoint="http://localhost:11434")
    result = await provider.translate("hello", "glossary", "en", "vi")

    assert result.text == "Ban dich"
    assert result.input_tokens == 20
    assert result.output_tokens == 10
    assert result.estimated_cost_usd == 0.0
    assert result.provider_name == "ollama"


@pytest.mark.asyncio
async def test_ollama_translate_connection_error(mocker) -> None:
    """Y6 (Architecture.md 6.20.12): connection failures are transient — this
    used to assert TranslationProviderError (permanent), which was exactly
    the bug Y6 exists to fix (with_retry() never retried it)."""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.services.ollama_provider.httpx.AsyncClient", return_value=mock_client)

    provider = OllamaProvider(endpoint="http://localhost:11434")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_ollama_translate_timeout_is_transient(mocker) -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.services.ollama_provider.httpx.AsyncClient", return_value=mock_client)

    provider = OllamaProvider(endpoint="http://localhost:11434")
    with pytest.raises(TimeoutError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_ollama_translate_5xx_is_transient(mocker) -> None:
    fake_response = MagicMock()
    fake_response.status_code = 503
    fake_response.text = "service unavailable"
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.services.ollama_provider.httpx.AsyncClient", return_value=mock_client)

    provider = OllamaProvider(endpoint="http://localhost:11434")
    with pytest.raises(ConnectionError):
        await provider.translate("hello", "glossary", "en", "vi")


@pytest.mark.asyncio
async def test_ollama_translate_4xx_stays_permanent(mocker) -> None:
    fake_response = MagicMock()
    fake_response.status_code = 404
    fake_response.text = "model not found"
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.services.ollama_provider.httpx.AsyncClient", return_value=mock_client)

    provider = OllamaProvider(endpoint="http://localhost:11434")
    with pytest.raises(TranslationProviderError):
        await provider.translate("hello", "glossary", "en", "vi")
