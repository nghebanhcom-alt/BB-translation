"""Provider registry (Architecture.md section 6.6: "Provider registry
(ProviderFactory) map ten provider -> class, cho phep them provider moi sau
nay ma khong sua code goi chung.").
"""

from src.core.config import Settings
from src.services.claude_provider import ClaudeProvider
from src.services.deepl_provider import DeepLProvider
from src.services.deepseek_provider import DeepSeekProvider
from src.services.gemini_provider import GeminiProvider
from src.services.ollama_provider import OllamaProvider
from src.services.openai_provider import OpenAIProvider
from src.services.translation import TranslationProvider


class UnknownProviderError(ValueError):
    """Raised when `provider_name` does not match any registered provider."""


class ProviderConfigError(ValueError):
    """Raised when a provider is selected but its required config (e.g. API key) is missing."""


class ProviderFactory:
    """Maps a provider name string to a configured `TranslationProvider` instance."""

    _REGISTRY = frozenset({"claude", "openai", "deepseek", "gemini", "deepl", "ollama"})

    @classmethod
    def create(cls, provider_name: str, settings: Settings) -> TranslationProvider:
        name = provider_name.strip().lower()
        if name not in cls._REGISTRY:
            raise UnknownProviderError(
                f"Unknown translation provider '{provider_name}'. "
                f"Valid options: {sorted(cls._REGISTRY)}"
            )

        builder = getattr(cls, f"_build_{name}")
        return builder(settings)

    @staticmethod
    def _build_claude(settings: Settings) -> ClaudeProvider:
        if not settings.claude_api_key:
            raise ProviderConfigError("CLAUDE_API_KEY is not configured")
        return ClaudeProvider(
            api_key=settings.claude_api_key,
            model=settings.claude_model,
            max_tokens=settings.claude_max_tokens,
            temperature=settings.claude_temperature,
            use_prompt_caching=settings.claude_use_prompt_caching,
        )

    @staticmethod
    def _build_openai(settings: Settings) -> OpenAIProvider:
        if not settings.openai_api_key:
            raise ProviderConfigError("OPENAI_API_KEY is not configured")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature,
        )

    @staticmethod
    def _build_deepseek(settings: Settings) -> DeepSeekProvider:
        if not settings.deepseek_api_key:
            raise ProviderConfigError("DEEPSEEK_API_KEY is not configured")
        return DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            max_tokens=settings.deepseek_max_tokens,
            temperature=settings.deepseek_temperature,
            base_url=settings.deepseek_base_url,
        )

    @staticmethod
    def _build_gemini(settings: Settings) -> GeminiProvider:
        if not settings.gemini_api_key:
            raise ProviderConfigError("GEMINI_API_KEY is not configured")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            max_tokens=settings.gemini_max_tokens,
            temperature=settings.gemini_temperature,
        )

    @staticmethod
    def _build_deepl(settings: Settings) -> DeepLProvider:
        if not settings.deepl_api_key:
            raise ProviderConfigError("DEEPL_API_KEY is not configured")
        return DeepLProvider(
            api_key=settings.deepl_api_key,
            formality=settings.deepl_formality,
        )

    @staticmethod
    def _build_ollama(settings: Settings) -> OllamaProvider:
        if not settings.ollama_endpoint:
            raise ProviderConfigError("OLLAMA_ENDPOINT is not configured")
        return OllamaProvider(
            endpoint=settings.ollama_endpoint,
            model=settings.ollama_model,
            max_tokens=settings.ollama_max_tokens,
            temperature=settings.ollama_temperature,
        )
