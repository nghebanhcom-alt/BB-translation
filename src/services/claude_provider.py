"""Claude API provider via the `anthropic` async SDK.

Pricing: looked up per `self._model` (same fix as Bug #8 in
`openai_provider.py` — a single hardcoded price regardless of the
configured model silently mis-prices every other tier). Nguon xac thuc:
https://claude.com/pricing (fetched 2026-09-04).
"""

import anthropic

from src.services.translation import (
    AuthenticationError,
    RateLimitError,
    TranslationProviderError,
    TranslationResult,
)

#: (input_per_mtok, output_per_mtok) in USD, keyed by API model ID.
#: Nguon xac thuc: https://claude.com/pricing (fetched 2026-09-04).
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-5-20250514": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-fable-5-1": (10.0, 50.0),
}
_DEFAULT_PRICING = _PRICING_PER_MTOK["claude-sonnet-5"]


class ClaudeProvider:
    """Claude API via anthropic SDK. Supports prompt caching for the glossary
    system prompt (Architecture.md section 6.6: "Prompt caching: system prompt
    cached across chunks" -> ~90% cost reduction on cached input reads).
    """

    provider_name = "claude"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250514",
        max_tokens: int = 8192,
        temperature: float = 0.3,
        use_prompt_caching: bool = True,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._use_prompt_caching = use_prompt_caching

    async def translate(
        self,
        text: str,
        glossary_prompt: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        system_block: list[dict] = [{"type": "text", "text": glossary_prompt}]
        if self._use_prompt_caching:
            system_block[0]["cache_control"] = {"type": "ephemeral"}

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system_block,
                messages=[
                    {
                        "role": "user",
                        "content": f"Translate from {source_lang} to {target_lang}:\n\n{text}",
                    }
                ],
            )
        except anthropic.AuthenticationError as exc:
            raise AuthenticationError(f"Claude authentication failed: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise RateLimitError(f"Claude rate limit exceeded: {exc}") from exc
        except anthropic.APIError as exc:
            raise TranslationProviderError(f"Claude API error: {exc}") from exc

        translated_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return TranslationResult(
            text=translated_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens),
            provider_name="claude",
        )

    def _cost_per_mtok(self) -> tuple[float, float]:
        """(input, output) USD/MTok for `self._model`, falling back to the
        Sonnet 5 rate for an unlisted model rather than silently using $0.
        """
        return _PRICING_PER_MTOK.get(self._model, _DEFAULT_PRICING)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = self._cost_per_mtok()
        return input_tokens / 1_000_000 * input_rate + output_tokens / 1_000_000 * output_rate
