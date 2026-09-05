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
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("src.services.ollama_provider.httpx.AsyncClient", return_value=mock_client)

    provider = OllamaProvider(endpoint="http://localhost:11434")
    with pytest.raises(TranslationProviderError):
        await provider.translate("hello", "glossary", "en", "vi")
