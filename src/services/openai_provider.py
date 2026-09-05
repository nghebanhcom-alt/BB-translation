"""OpenAI API provider via the `openai` async SDK (chat completions).

Pricing: gpt-4o pricing is not specified in Architecture.md (only Claude and
DeepSeek pricing are given in section 6.6). Reference values below are public
OpenAI pricing at time of writing — may change; update `_PRICING_PER_MTOK`
when a real value is confirmed.

Bug #8 fix: pricing MUST be looked up per `self._model`, not hardcoded to a
single model's rate — Increment 6 changed the app default to `gpt-4o-mini`
(~16.67x cheaper than `gpt-4o`) but `estimate_cost()` kept using the `gpt-4o`
constants regardless of which model was actually configured, inflating every
displayed cost (`/api/estimate` and `Job.actual_cost`) by that same factor
(observed live in QA Vong 5: $0.62775 estimated vs ~$0.005-0.04 real cost).
"""

import openai

from src.services.translation import (
    AuthenticationError,
    RateLimitError,
    TranslationProviderError,
    TranslationResult,
)

#: OpenAI pricing page, tham khao luc viet code - co the doi theo thoi gian.
#: (input_per_mtok, output_per_mtok) in USD. Falls back to gpt-4o's rate for
#: any model not listed here (see `_cost_per_mtok`).
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
}
_DEFAULT_PRICING = _PRICING_PER_MTOK["gpt-4o"]


class OpenAIProvider:
    """OpenAI API via openai SDK, standard chat completions."""

    #: Overridden by DeepSeekProvider to swap the base_url/pricing.
    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 8192,
        temperature: float = 0.3,
        base_url: str | None = None,
    ) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def translate(
        self,
        text: str,
        glossary_prompt: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[
                    {"role": "system", "content": glossary_prompt},
                    {
                        "role": "user",
                        "content": f"Translate from {source_lang} to {target_lang}:\n\n{text}",
                    },
                ],
            )
        except openai.AuthenticationError as exc:
            raise AuthenticationError(
                f"{self.provider_name} authentication failed: {exc}"
            ) from exc
        except openai.RateLimitError as exc:
            raise RateLimitError(f"{self.provider_name} rate limit exceeded: {exc}") from exc
        except openai.APIError as exc:
            raise TranslationProviderError(f"{self.provider_name} API error: {exc}") from exc

        translated_text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return TranslationResult(
            text=translated_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens),
            provider_name=self.provider_name,
        )

    def _cost_per_mtok(self) -> tuple[float, float]:
        """(input, output) USD/MTok for `self._model`, falling back to the
        `gpt-4o` rate for an unlisted model rather than silently using $0.
        """
        return _PRICING_PER_MTOK.get(self._model, _DEFAULT_PRICING)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost_per_mtok, output_cost_per_mtok = self._cost_per_mtok()
        return (
            input_tokens / 1_000_000 * input_cost_per_mtok
            + output_tokens / 1_000_000 * output_cost_per_mtok
        )
