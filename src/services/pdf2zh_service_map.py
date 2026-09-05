"""Provider name -> pdf2zh `-s` service argument (Architecture.md section 6.6.3/6.6.8).

pdf2zh calls the LLM itself once it receives `-s {service}` — this module never
makes an API call, it only shapes the subprocess invocation: the `-s` flag value
plus the env vars pdf2zh reads for that backend. API keys always go through
`envs` (subprocess environment), never through argv, which any local user could
read via `ps`.

Kept as a registry parallel to `ProviderFactory` (src/services/provider_factory.py):
`ProviderFactory` builds out-of-band `TranslationProvider` instances for cost
estimation / test-connection / sample-preview (Architecture.md 6.6.2 R3).
`Pdf2zhServiceMapper` builds what the render path needs. Adding a new provider
means updating both registries — see Architecture.md 6.6.3 closing note.
"""

from dataclasses import dataclass, replace
from pathlib import Path

from src.core.config import Settings


@dataclass(frozen=True)
class Pdf2zhService:
    service_arg: str
    envs: dict[str, str]
    supports_custom_prompt: bool


class UnsupportedForPdfPipelineError(RuntimeError):
    """Provider cannot be used to render a PDF via pdf2zh.

    The only v1.0 case is DeepL: `DeepLTranslator.CustomPrompt = False` and
    `DeepLTranslator.do_translate()` never passes a `glossary` argument to
    `translate_text()` (Architecture.md 6.6.1 F7) — so glossary injection and
    unit-conversion rules, both delivered exclusively through `--prompt`, can
    never reach DeepL on the PDF pipeline. See Architecture.md 6.6.7 #1 and
    PRD BR-PROVIDER-01.
    """


class Pdf2zhServiceMapper:
    """Maps an internal provider name to the `(-s value, env dict)` pdf2zh needs."""

    _KNOWN_PROVIDERS = frozenset({"openai", "gemini", "deepseek", "ollama", "claude", "deepl"})

    def map(self, provider_name: str, settings: Settings) -> Pdf2zhService:
        name = provider_name.strip().lower()
        if name not in self._KNOWN_PROVIDERS:
            raise UnsupportedForPdfPipelineError(
                f"Provider '{provider_name}' khong duoc ho tro cho PDF pipeline "
                f"(khong co entry trong Pdf2zhServiceMapper). Cac provider hop le: "
                f"{sorted(self._KNOWN_PROVIDERS)}"
            )
        builder = getattr(self, f"_build_{name}")
        service = builder(settings)
        font_path = Path(settings.noto_font_path)
        if font_path.exists():
            # Pin pdf2zh to the SAME font file `font_shrink_page` measures/
            # redraws with (Architecture.md 6.3) — without this, pdf2zh falls
            # back to auto-downloading its own copy, which our post-process
            # step has no way to locate or match. NOTE: `babeldoc` does NOT
            # read this env var at all (verified 2026-09-05 by reading
            # `babeldoc.assets.embedding_assets_metadata` — it always uses its
            # own bundled font asset for the target language, ignoring any
            # env var). For babeldoc, `noto_font_path` matters only because it
            # points at a local copy of that SAME bundled font file, so
            # `font_shrink_page` matches babeldoc's rendering rather than
            # actually redirecting babeldoc to use it — see font_shrink.py's
            # module docstring.
            service = replace(
                service, envs={**service.envs, "NOTO_FONT_PATH": str(font_path.resolve())}
            )
        return service

    @staticmethod
    def _build_openai(settings: Settings) -> Pdf2zhService:
        return Pdf2zhService(
            service_arg=f"openai:{settings.openai_model}",
            envs={
                "OPENAI_API_KEY": settings.openai_api_key,
                "OPENAI_BASE_URL": settings.openai_base_url,
                "OPENAI_MODEL": settings.openai_model,
                "OPENAI_STREAM": "false",
                "OPENAI_MAX_TOKENS": str(settings.openai_max_tokens),
                "COLUMNS": "200",
            },
            supports_custom_prompt=True,
        )

    @staticmethod
    def _build_gemini(settings: Settings) -> Pdf2zhService:
        return Pdf2zhService(
            service_arg=f"gemini:{settings.gemini_model}",
            envs={
                "GEMINI_API_KEY": settings.gemini_api_key,
                "GEMINI_MODEL": settings.gemini_model,
                "COLUMNS": "200",
            },
            supports_custom_prompt=True,
        )

    @staticmethod
    def _build_deepseek(settings: Settings) -> Pdf2zhService:
        return Pdf2zhService(
            service_arg=f"deepseek:{settings.deepseek_model}",
            envs={
                "DEEPSEEK_API_KEY": settings.deepseek_api_key,
                "DEEPSEEK_MODEL": settings.deepseek_model,
                "COLUMNS": "200",
            },
            supports_custom_prompt=True,
        )

    @staticmethod
    def _build_ollama(settings: Settings) -> Pdf2zhService:
        return Pdf2zhService(
            service_arg=f"ollama:{settings.ollama_model}",
            envs={
                "OLLAMA_HOST": settings.ollama_endpoint,
                "OLLAMA_MODEL": settings.ollama_model,
                "COLUMNS": "200",
            },
            supports_custom_prompt=True,
        )

    @staticmethod
    def _build_claude(settings: Settings) -> Pdf2zhService:
        # Anthropic's OpenAI-compat layer (Architecture.md 6.6.1 F4) — no native
        # pdf2zh Claude translator exists (F1). No prompt caching / Batch API on
        # this path (6.6.7 #2); `claude_use_batch_api`/`claude_use_prompt_caching`
        # only apply to the out-of-band `ClaudeProvider`.
        return Pdf2zhService(
            service_arg=f"openailiked:{settings.claude_model}",
            envs={
                "OPENAILIKED_BASE_URL": "https://api.anthropic.com/v1/",
                "OPENAILIKED_API_KEY": settings.claude_api_key,
                "OPENAILIKED_MODEL": settings.claude_model,
                "OPENAILIKED_STREAM": "false",
                "OPENAILIKED_MAX_TOKENS": str(settings.claude_max_tokens),
                "COLUMNS": "200",
            },
            supports_custom_prompt=True,
        )

    @staticmethod
    def _build_deepl(settings: Settings) -> Pdf2zhService:
        raise UnsupportedForPdfPipelineError(
            "DeepL khong the dung cho PDF pipeline: DeepLTranslator.CustomPrompt = False "
            "trong pdf2zh, nen glossary va quy tac chuyen doi don vi (chi truyen duoc qua "
            "--prompt) se khong bao gio den duoc DeepL. Chon provider khac (khuyen nghi: "
            "deepseek) cho job PDF nay, hoac dung DeepL cho pipeline EPUB / test connection / "
            "cost estimate. Xem Architecture.md 6.6.7 muc 1, PRD BR-PROVIDER-01."
        )
