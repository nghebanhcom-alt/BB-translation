"""`is_runaway_output()`/`epub_expected_output_tokens()` (Architecture.md
6.20.13.3b, fix C-3, Bug #EPUB-B2-1) — heuristic phat hien 1 request LLM
sinh output "runaway" so voi CHINH payload cua request do.

⚠️ ASSUMED (Architecture.md 6.20.13.3b): `EPUB_RUNAWAY_OUTPUT_FACTOR=3.0` va
`EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS=1500` chua duoc do tren phan bo that — cac
test o day chi xac nhan CODE dung DUNG 2 con so Tech Lead da cho, khong tu
doan lai nguong.
"""

from src.core.cost_estimator import (
    CHARS_PER_TOKEN_VI,
    EPUB_RUNAWAY_OUTPUT_FACTOR,
    EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS,
    VI_CHAR_EXPANSION,
    epub_expected_output_tokens,
    is_runaway_output,
)


def test_epub_expected_output_tokens_matches_shared_estimator_constants() -> None:
    payload_chars = 3_000

    expected = epub_expected_output_tokens(payload_chars)

    assert expected == int(payload_chars * VI_CHAR_EXPANSION / CHARS_PER_TOKEN_VI)


def test_is_runaway_output_false_for_healthy_response() -> None:
    payload_chars = 3_000
    expected = epub_expected_output_tokens(payload_chars)

    assert not is_runaway_output(payload_chars, expected)
    assert not is_runaway_output(payload_chars, int(expected * 1.5))


def test_is_runaway_output_true_when_factor_exceeded() -> None:
    payload_chars = 3_000
    expected = epub_expected_output_tokens(payload_chars)

    just_over = int(expected * EPUB_RUNAWAY_OUTPUT_FACTOR) + 1

    assert is_runaway_output(payload_chars, just_over)


def test_is_runaway_output_uses_floor_for_small_payloads() -> None:
    """Payload rat nho (vd 1 request retry rieng le 1 unit ngan) -> muc ky
    vong theo cong thuc co the < floor — phai dung floor de tranh
    false-positive tren dao dong nho."""
    payload_chars = 10  # expected ~= 5 token, nho hon xa floor
    expected = epub_expected_output_tokens(payload_chars)
    assert expected * EPUB_RUNAWAY_OUTPUT_FACTOR < EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS

    assert not is_runaway_output(payload_chars, EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS)
    assert is_runaway_output(payload_chars, EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS + 1)


def test_is_runaway_output_boundary_exact_threshold_is_not_runaway() -> None:
    payload_chars = 3_000
    expected = epub_expected_output_tokens(payload_chars)
    threshold = max(EPUB_RUNAWAY_OUTPUT_FACTOR * expected, EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS)

    assert not is_runaway_output(payload_chars, int(threshold))
