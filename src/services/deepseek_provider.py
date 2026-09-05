"""DeepSeek provider — OpenAI-compatible API, reuses OpenAIProvider logic
(Architecture.md section 6.6: "API tuong thich OpenAI SDK, chi doi base_url").

Pricing: looked up per model, off-peak cache-miss rate (worst case — the app
has no way to know per-request cache-hit status ahead of time, and
Architecture.md 6.11.6 requires estimates to stay on the over- not
under-estimate side). `deepseek-chat`/`deepseek-reasoner` are the legacy
aliases, retired 2026-07-24 and repointed at deepseek-v4-flash — new configs
should use the explicit `deepseek-v4-*` names. Nguon xac thuc:
https://api-docs.deepseek.com/quick_start/pricing/ (fetched 2026-09-04).
"""

from src.services.openai_provider import OpenAIProvider

#: (input_per_mtok, output_per_mtok) in USD, off-peak cache-miss rate.
#: Nguon xac thuc: https://api-docs.deepseek.com/quick_start/pricing/ (2026-09-04).
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "deepseek-v4-flash": (0.22, 0.66),
    "deepseek-v4-pro": (0.66, 1.98),
    # Legacy aliases, retired 2026-07-24 — kept so existing configs don't
    # silently mis-price; both now repoint at deepseek-v4-flash server-side.
    "deepseek-chat": (0.22, 0.66),
    "deepseek-reasoner": (0.22, 0.66),
}
_DEFAULT_PRICING = _PRICING_PER_MTOK["deepseek-v4-flash"]


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek dung chung logic voi OpenAIProvider, chi doi base_url + model."""

    provider_name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-flash",
        max_tokens: int = 8192,
        temperature: float = 0.3,
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            base_url=base_url,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = _PRICING_PER_MTOK.get(self._model, _DEFAULT_PRICING)
        return input_tokens / 1_000_000 * input_rate + output_tokens / 1_000_000 * output_rate
