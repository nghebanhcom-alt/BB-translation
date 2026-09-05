from pathlib import Path

import pytest

from src.core.config import Settings
from src.services.pdf2zh_service_map import (
    Pdf2zhServiceMapper,
    UnsupportedForPdfPipelineError,
)


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def test_map_deepseek_native_service_arg() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings(deepseek_api_key="sk-fake", deepseek_model="deepseek-chat")

    service = mapper.map("deepseek", settings)

    assert service.service_arg == "deepseek:deepseek-chat"
    assert service.envs["DEEPSEEK_API_KEY"] == "sk-fake"
    assert service.envs["DEEPSEEK_MODEL"] == "deepseek-chat"
    assert service.envs["COLUMNS"] == "200"
    assert service.supports_custom_prompt is True


def test_map_gemini_native_service_arg() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings(gemini_api_key="AIza-fake", gemini_model="gemini-2.5-pro")

    service = mapper.map("gemini", settings)

    assert service.service_arg == "gemini:gemini-2.5-pro"
    assert service.envs["GEMINI_API_KEY"] == "AIza-fake"
    assert service.envs["COLUMNS"] == "200"


def test_map_claude_goes_through_openailiked_compat_layer() -> None:
    """Architecture.md 6.6.1 F1/F3/F4: pdf2zh has no native Claude translator,
    so Claude must be reached via `-s openailiked` pointed at Anthropic's
    OpenAI-compat endpoint — NOT `-s claude` (that crashes, pdf2zh doesn't
    have it)."""
    mapper = Pdf2zhServiceMapper()
    settings = _settings(claude_api_key="sk-ant-fake", claude_model="claude-sonnet-4-5-20250514")

    service = mapper.map("claude", settings)

    assert service.service_arg == "openailiked:claude-sonnet-4-5-20250514"
    assert service.envs["OPENAILIKED_BASE_URL"] == "https://api.anthropic.com/v1/"
    assert service.envs["OPENAILIKED_API_KEY"] == "sk-ant-fake"
    assert service.envs["OPENAILIKED_STREAM"] == "false"
    assert service.envs["COLUMNS"] == "200"
    assert service.supports_custom_prompt is True


def test_map_openai_service_arg() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings(openai_api_key="sk-fake", openai_model="gpt-4o")

    service = mapper.map("openai", settings)

    assert service.service_arg == "openai:gpt-4o"
    assert service.envs["OPENAI_STREAM"] == "false"
    assert service.envs["COLUMNS"] == "200"


def test_map_ollama_service_arg() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings(ollama_endpoint="http://localhost:11434", ollama_model="gemma2:27b")

    service = mapper.map("ollama", settings)

    assert service.service_arg == "ollama:gemma2:27b"
    assert service.envs["OLLAMA_HOST"] == "http://localhost:11434"
    assert service.envs["COLUMNS"] == "200"


def test_all_supported_providers_set_columns_200_for_rich_log_unwrapping() -> None:
    """Architecture.md 6.12.2 D2/S11: without COLUMNS=200, rich wraps pdf2zh's
    log lines at 80 columns in non-TTY subprocess output and cuts the
    RateLimitError signal in half. Every provider that actually spawns pdf2zh
    (i.e. not DeepL, which is rejected before spawning) must carry it."""
    mapper = Pdf2zhServiceMapper()
    settings = _settings(
        openai_api_key="sk-fake",
        gemini_api_key="AIza-fake",
        deepseek_api_key="sk-fake",
        ollama_endpoint="http://localhost:11434",
        claude_api_key="sk-ant-fake",
    )

    for provider in ("openai", "gemini", "deepseek", "ollama", "claude"):
        service = mapper.map(provider, settings)
        assert service.envs["COLUMNS"] == "200", f"{provider} missing COLUMNS=200"


def test_map_deepl_raises_unsupported_for_pdf_pipeline() -> None:
    """Architecture.md 6.6.7 #1 / PRD BR-PROVIDER-01: DeepL's `CustomPrompt =
    False` in pdf2zh means glossary + unit-conversion rules (delivered only
    through --prompt) can never reach it on the PDF pipeline. Must fail fast,
    with a clear reason, before any subprocess is spawned."""
    mapper = Pdf2zhServiceMapper()
    settings = _settings(deepl_api_key="fake-key")

    with pytest.raises(UnsupportedForPdfPipelineError, match="DeepL"):
        mapper.map("deepl", settings)


def test_map_deepl_case_insensitive_still_raises() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings(deepl_api_key="fake-key")

    with pytest.raises(UnsupportedForPdfPipelineError):
        mapper.map("DeepL", settings)


def test_map_unknown_provider_raises_unsupported() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings()

    with pytest.raises(UnsupportedForPdfPipelineError, match="unknown-provider"):
        mapper.map("unknown-provider", settings)


def test_map_sets_noto_font_path_when_font_file_exists() -> None:
    """`font_shrink_page` and pdf2zh must render/measure against the SAME
    font file (see src/postprocess/font_shrink.py module docstring: "helv"
    silently corrupts Vietnamese chars outside Latin-1). The project ships
    the real font at `settings.noto_font_path` (default), so this should
    resolve to an absolute, existing path in a real checkout."""
    mapper = Pdf2zhServiceMapper()
    settings = _settings(deepseek_api_key="sk-fake")

    service = mapper.map("deepseek", settings)

    assert "NOTO_FONT_PATH" in service.envs
    font_path = Path(service.envs["NOTO_FONT_PATH"])
    assert font_path.is_absolute()
    assert font_path.exists()


def test_map_omits_noto_font_path_when_font_file_missing() -> None:
    mapper = Pdf2zhServiceMapper()
    settings = _settings(deepseek_api_key="sk-fake", noto_font_path="does/not/exist.ttf")

    service = mapper.map("deepseek", settings)

    assert "NOTO_FONT_PATH" not in service.envs
