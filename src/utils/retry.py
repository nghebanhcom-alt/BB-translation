"""Generic retry wrapper with exponential backoff (BR-BATCH-02, US-08)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from src.services.translation import AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)

#: Transient errors are retried with backoff: provider rate limits, timeouts,
#: and network-level failures. `TranslationProviderError` subclasses not
#: listed here (e.g. `AuthenticationError`) are treated as permanent.
_TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    RateLimitError,
    TimeoutError,
    ConnectionError,
)
#: Permanent errors fail immediately, no retry (BR-BATCH-02: "permanent
#: error -> fail + log"). Listed explicitly so a bug in a new exception
#: hierarchy can't accidentally make something permanent retry forever.
_PERMANENT_ERRORS: tuple[type[BaseException], ...] = (AuthenticationError,)


async def with_retry[T](
    func: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
    backoff_base: int = 2,
) -> T:
    """Call `func()`, retrying on transient errors with exponential backoff.

    Backoff for `backoff_base=2`: 2s, 4s, 8s, ... (`backoff_base ** attempt`).
    Permanent errors (`AuthenticationError`) and any error not recognized as
    transient re-raise immediately — a corrupt file or unsupported format
    should fail fast rather than burn through retry attempts.
    """
    attempt = 1
    while True:
        try:
            return await func()
        except _PERMANENT_ERRORS:
            raise
        except _TRANSIENT_ERRORS:
            if attempt >= max_attempts:
                raise
            delay = backoff_base**attempt
            logger.warning(
                "Transient error on attempt %d/%d, retrying in %ds", attempt, max_attempts, delay
            )
            await asyncio.sleep(delay)
            attempt += 1
