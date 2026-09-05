"""Gemini provider via `google-generativeai` SDK (Architecture.md section 6.6).

Pricing: looked up per model (<=200k-token prompt tier). gemini-2.5-pro and
gemini-2.5-flash confirmed against ai.google.dev/gemini-api/docs/pricing and
cross-checked via a second independent source (fetched 2026-09-04). Newer
3.x-series model names surfaced during that research but could not be
corroborated against a stable primary source in this pass — do not add them
here without a fresh, directly-cited verification (Protocol 5 R5-01).
"""

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from src.services.translation import (
    AuthenticationError,
    RateLimitError,
    TranslationProviderError,
    TranslationResult,
)

#: (input_per_mtok, output_per_mtok) in USD, <=200k-token prompt tier.
#: Nguon xac thuc: https://ai.google.dev/gemini-api/docs/pricing (2026-09-04).
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),
}
_DEFAULT_PRICING = _PRICING_PER_MTOK["gemini-2.5-pro"]


class GeminiProvider:
    """Dung google-generativeai SDK, khac cau truc request/response so voi OpenAI-style."""

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-pro",
        max_tokens: int = 8192,
        temperature: float = 0.3,
    ) -> None:
        # genai.configure is process-global; scoping per-instance API keys is a
        # known limitation of this SDK, acceptable for the current 1-user deployment.
        genai.configure(api_key=api_key)
        self._model_name = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def translate(
        self,
        text: str,
        glossary_prompt: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        model = genai.GenerativeModel(self._model_name, system_instruction=glossary_prompt)
        prompt = f"Translate from {source_lang} to {target_lang}:\n\n{text}"

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config={
                    "temperature": self._temperature,
                    "max_output_tokens": self._max_tokens,
                },
            )
        except google_exceptions.Unauthenticated as exc:
            raise AuthenticationError(f"Gemini authentication failed: {exc}") from exc
        except google_exceptions.PermissionDenied as exc:
            raise AuthenticationError(f"Gemini permission denied: {exc}") from exc
        except (google_exceptions.ResourceExhausted, google_exceptions.TooManyRequests) as exc:
            raise RateLimitError(f"Gemini rate limit exceeded: {exc}") from exc
        except google_exceptions.GoogleAPICallError as exc:
            raise TranslationProviderError(f"Gemini API error: {exc}") from exc

        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        return TranslationResult(
            text=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens),
            provider_name="gemini",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = _PRICING_PER_MTOK.get(self._model_name, _DEFAULT_PRICING)
        return input_tokens / 1_000_000 * input_rate + output_tokens / 1_000_000 * output_rate
