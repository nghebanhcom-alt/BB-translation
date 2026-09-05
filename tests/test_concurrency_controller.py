import pytest

from src.core.concurrency_controller import (
    ADAPTIVE_THREAD_CEILING,
    ADAPTIVE_THREAD_FLOOR,
    RATE_LIMIT_LINE_RE,
    ChunkOutcome,
    classify_chunk_outcome,
    next_thread_count,
)


def test_rate_limit_line_re_matches_token() -> None:
    assert RATE_LIMIT_LINE_RE.search("RateLimitError, retrying in 4s...")
    assert not RATE_LIMIT_LINE_RE.search("no signal here")


@pytest.mark.parametrize(
    ("exit_code", "rate_limit_hits", "duration_seconds", "timeout_seconds", "expected"),
    [
        # success: exit 0, no rate limit, duration <= 0.75 * timeout
        (0, 0, 100.0, 200.0, ChunkOutcome.SUCCESS),
        # slow_success: exit 0, no rate limit, duration > 0.75 * timeout
        (0, 0, 151.0, 200.0, ChunkOutcome.SLOW_SUCCESS),
        # rate_limited: exit 0 or nonzero, rate_limit_hits >= 1
        (0, 1, 50.0, 200.0, ChunkOutcome.RATE_LIMITED),
        (1, 2, 50.0, 200.0, ChunkOutcome.RATE_LIMITED),
        # timeout_signalled: exit_code is None (timed out) + rate_limit_hits >= 1
        (None, 1, 200.0, 200.0, ChunkOutcome.TIMEOUT_SIGNALLED),
        # timeout_silent: exit_code is None + rate_limit_hits == 0
        (None, 0, 200.0, 200.0, ChunkOutcome.TIMEOUT_SILENT),
        # error: nonzero exit, no rate limit signal
        (1, 0, 50.0, 200.0, ChunkOutcome.ERROR),
    ],
)
def test_classify_chunk_outcome_table(
    exit_code: int | None,
    rate_limit_hits: int,
    duration_seconds: float,
    timeout_seconds: float,
    expected: ChunkOutcome,
) -> None:
    assert (
        classify_chunk_outcome(
            exit_code=exit_code,
            rate_limit_hits=rate_limit_hits,
            duration_seconds=duration_seconds,
            timeout_seconds=timeout_seconds,
        )
        == expected
    )


def test_classify_chunk_outcome_boundary_exactly_75_percent_is_success() -> None:
    # duration == 0.75 * timeout must fall on the "<=" success side, not slow_success.
    outcome = classify_chunk_outcome(
        exit_code=0, rate_limit_hits=0, duration_seconds=150.0, timeout_seconds=200.0
    )
    assert outcome is ChunkOutcome.SUCCESS


def test_classify_chunk_outcome_rate_limited_regardless_of_exit_code_zero() -> None:
    outcome = classify_chunk_outcome(
        exit_code=0, rate_limit_hits=1, duration_seconds=10.0, timeout_seconds=200.0
    )
    assert outcome is ChunkOutcome.RATE_LIMITED


def test_classify_chunk_outcome_rate_limited_regardless_of_exit_code_nonzero() -> None:
    outcome = classify_chunk_outcome(
        exit_code=1, rate_limit_hits=3, duration_seconds=10.0, timeout_seconds=200.0
    )
    assert outcome is ChunkOutcome.RATE_LIMITED


@pytest.mark.parametrize(
    ("outcome", "expected_delta_or_halve"),
    [
        (ChunkOutcome.SUCCESS, 2),
        (ChunkOutcome.SLOW_SUCCESS, 0),
        (ChunkOutcome.TIMEOUT_SILENT, 0),
        (ChunkOutcome.ERROR, 0),
    ],
)
def test_next_thread_count_hold_and_additive(
    outcome: ChunkOutcome, expected_delta_or_halve: int
) -> None:
    floor = ADAPTIVE_THREAD_FLOOR["deepseek"]
    current = 10
    assert next_thread_count(outcome, current, floor) == current + expected_delta_or_halve


@pytest.mark.parametrize("outcome", [ChunkOutcome.RATE_LIMITED, ChunkOutcome.TIMEOUT_SIGNALLED])
def test_next_thread_count_multiplicative_decrease(outcome: ChunkOutcome) -> None:
    floor = ADAPTIVE_THREAD_FLOOR["deepseek"]
    assert next_thread_count(outcome, 20, floor) == 10
    assert next_thread_count(outcome, 16, floor) == 8


def test_next_thread_count_success_clamps_at_ceiling() -> None:
    floor = ADAPTIVE_THREAD_FLOOR["deepseek"]
    current = ADAPTIVE_THREAD_CEILING
    for _ in range(5):
        current = next_thread_count(ChunkOutcome.SUCCESS, current, floor)
    assert current == ADAPTIVE_THREAD_CEILING

    current = ADAPTIVE_THREAD_CEILING - 1
    assert next_thread_count(ChunkOutcome.SUCCESS, current, floor) == ADAPTIVE_THREAD_CEILING


@pytest.mark.parametrize("provider", ["deepseek", "openai", "gemini", "claude"])
def test_next_thread_count_decrease_clamps_at_provider_floor(provider: str) -> None:
    floor = ADAPTIVE_THREAD_FLOOR[provider]
    current = floor
    for _ in range(5):
        current = next_thread_count(ChunkOutcome.RATE_LIMITED, current, floor)
    assert current == floor

    current = floor + 1
    assert next_thread_count(ChunkOutcome.TIMEOUT_SIGNALLED, current, floor) == floor


def test_adaptive_thread_floor_values() -> None:
    assert ADAPTIVE_THREAD_FLOOR == {
        "deepseek": 8,
        "openai": 8,
        "gemini": 4,
        "claude": 8,  # 2026-09-06: user risk-acceptance override, see concurrency_controller.py
    }
    assert ADAPTIVE_THREAD_CEILING == 32
