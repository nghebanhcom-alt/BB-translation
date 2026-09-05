"""Provider-agnostic translation abstraction (Architecture.md section 5.3 / 6.6).

`TranslationProvider.translate()` intentionally returns a `TranslationResult`
(not the bare `str` shown in the Architecture.md 6.6 code sample) so token
counts and per-call cost are available to the Job Orchestrator (increment
after this one) for `jobs.actual_cost` tracking and BR-BATCH-02 error
handling. See docs/CHANGELOG.md "Increment 3" for the rationale.
"""

from dataclasses import dataclass
from typing import Protocol


class TranslationProviderError(RuntimeError):
    """Base exception for any translation provider failure."""


class RateLimitError(TranslationProviderError):
    """Transient error (HTTP 429 / provider rate limit). Retry with backoff (BR-BATCH-02)."""


class AuthenticationError(TranslationProviderError):
    """Permanent error: invalid/missing API key or auth failure. Do not retry (BR-BATCH-02)."""


@dataclass
class TranslationResult:
    text: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    provider_name: str


class TranslationProvider(Protocol):
    """Interface chung cho moi LLM translation backend (Architecture.md section 5.3)."""

    async def translate(
        self,
        text: str,
        glossary_prompt: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult: ...

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float: ...
