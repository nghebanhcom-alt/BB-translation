from unittest.mock import AsyncMock, call, patch

import pytest

from src.services.translation import AuthenticationError, RateLimitError
from src.utils.retry import with_retry


@pytest.mark.asyncio
async def test_with_retry_succeeds_after_transient_errors() -> None:
    func = AsyncMock(side_effect=[RateLimitError("rate limited"), RateLimitError("rate limited"), "ok"])

    with patch("src.utils.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await with_retry(func, max_attempts=3, backoff_base=2)

    assert result == "ok"
    assert func.await_count == 3
    mock_sleep.assert_has_awaits([call(2), call(4)])


@pytest.mark.asyncio
async def test_with_retry_raises_after_exhausting_attempts() -> None:
    func = AsyncMock(side_effect=RateLimitError("rate limited"))

    with (
        patch("src.utils.retry.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(RateLimitError),
    ):
        await with_retry(func, max_attempts=3, backoff_base=2)

    assert func.await_count == 3


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_permanent_errors() -> None:
    func = AsyncMock(side_effect=AuthenticationError("bad key"))

    with (
        patch("src.utils.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        pytest.raises(AuthenticationError),
    ):
        await with_retry(func, max_attempts=3, backoff_base=2)

    assert func.await_count == 1
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_unrecognized_errors() -> None:
    func = AsyncMock(side_effect=ValueError("corrupt file"))

    with pytest.raises(ValueError, match="corrupt file"):
        await with_retry(func, max_attempts=3, backoff_base=2)

    assert func.await_count == 1
