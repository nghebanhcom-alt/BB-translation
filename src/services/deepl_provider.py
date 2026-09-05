"""DeepL provider via the `deepl` SDK.

Architecture.md section 6.6: "Khong co system prompt -> glossary inject qua
DeepL Glossary API native. Khong ho tro unit conversion prompt -> fallback
post-process."

Scope of this increment (TODO for a later increment, documented in
docs/CHANGELOG.md "Increment 3"):
- This provider accepts `glossary_prompt` for `TranslationProvider` interface
  compatibility but does NOT parse it into DeepL glossary entries. Instead it
  takes an already-created DeepL glossary resource id (`glossary_id`) at
  construction time.
- Creating/updating that DeepL glossary resource from the local
  `glossary_entries` table (via DeepL's glossary management API,
  `translator.create_glossary(...)`) so it stays in sync with
  `GlossaryManager` is NOT implemented yet — left as a TODO for the Job
  Orchestrator increment, which is where per-job glossary state is first
  assembled.
- Unit conversion prompt instructions are also not applicable to DeepL for
  the same reason (no free-text system prompt) — Architecture.md already
  flags this as "fallback post-process", not implemented in this increment.

Pricing: DeepL bills per character, not per token, so `estimate_cost` here is
an approximation only (assumes ~4 characters/token). Reference rate: DeepL
API Pro pay-as-you-go, ~$25 per 1M characters (~$0.0001/token at 4 chars/tok)
— confirm against the real DeepL account plan before relying on this number.
"""

import asyncio

import deepl

from src.services.translation import (
    AuthenticationError,
    RateLimitError,
    TranslationProviderError,
    TranslationResult,
)

_COST_PER_MILLION_CHARACTERS = 25.0
_CHARS_PER_TOKEN_ESTIMATE = 4


class DeepLProvider:
    """DeepL API. Glossary injected via DeepL's native Glossary API (id-based),
    not via free-text prompt — see module docstring for the TODO scope.
    """

    provider_name = "deepl"

    def __init__(
        self,
        api_key: str,
        formality: str = "default",
        glossary_id: str | None = None,
    ) -> None:
        self._translator = deepl.Translator(api_key)
        self._formality = formality
        self._glossary_id = glossary_id

    async def translate(
        self,
        text: str,
        glossary_prompt: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        try:
            result = await asyncio.to_thread(
                self._translator.translate_text,
                text,
                source_lang=source_lang,
                target_lang=target_lang,
                formality=self._formality,
                glossary=self._glossary_id,
            )
        except deepl.AuthorizationException as exc:
            raise AuthenticationError(f"DeepL authentication failed: {exc}") from exc
        except deepl.TooManyRequestsException as exc:
            raise RateLimitError(f"DeepL rate limit exceeded: {exc}") from exc
        except deepl.DeepLException as exc:
            raise TranslationProviderError(f"DeepL API error: {exc}") from exc

        input_tokens = max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)
        output_tokens = max(1, len(result.text) // _CHARS_PER_TOKEN_ESTIMATE)

        return TranslationResult(
            text=result.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens),
            provider_name="deepl",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        total_chars = (input_tokens + output_tokens) * _CHARS_PER_TOKEN_ESTIMATE
        return total_chars / 1_000_000 * _COST_PER_MILLION_CHARACTERS
