import pytest

from src.core.config import Settings
from src.services.claude_provider import ClaudeProvider
from src.services.deepl_provider import DeepLProvider
from src.services.deepseek_provider import DeepSeekProvider
from src.services.gemini_provider import GeminiProvider
from src.services.ollama_provider import OllamaProvider
from src.services.openai_provider import OpenAIProvider
from src.services.provider_factory import ProviderConfigError, ProviderFactory, UnknownProviderError


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_create_claude_provider() -> None:
    settings = _settings(claude_api_key="sk-ant-fake")
    provider = ProviderFactory.create("claude", settings)
    assert isinstance(provider, ClaudeProvider)


def test_create_openai_provider() -> None:
    settings = _settings(openai_api_key="sk-fake")
    provider = ProviderFactory.create("openai", settings)
    assert isinstance(provider, OpenAIProvider)


def test_create_deepseek_provider() -> None:
    settings = _settings(deepseek_api_key="sk-fake")
    provider = ProviderFactory.create("deepseek", settings)
    assert isinstance(provider, DeepSeekProvider)


def test_create_gemini_provider() -> None:
    settings = _settings(gemini_api_key="AIza-fake")
    provider = ProviderFactory.create("gemini", settings)
    assert isinstance(provider, GeminiProvider)


def test_create_deepl_provider() -> None:
    settings = _settings(deepl_api_key="deepl-fake")
    provider = ProviderFactory.create("deepl", settings)
    assert isinstance(provider, DeepLProvider)


def test_create_ollama_provider_no_api_key_needed() -> None:
    settings = _settings()
    provider = ProviderFactory.create("ollama", settings)
    assert isinstance(provider, OllamaProvider)


def test_create_unknown_provider_raises() -> None:
    settings = _settings()
    with pytest.raises(UnknownProviderError):
        ProviderFactory.create("grok", settings)


def test_create_provider_missing_api_key_raises() -> None:
    settings = _settings(claude_api_key="")
    with pytest.raises(ProviderConfigError):
        ProviderFactory.create("claude", settings)


def test_provider_name_is_case_insensitive() -> None:
    settings = _settings(claude_api_key="sk-ant-fake")
    provider = ProviderFactory.create("CLAUDE", settings)
    assert isinstance(provider, ClaudeProvider)
