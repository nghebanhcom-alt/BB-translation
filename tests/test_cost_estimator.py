import json
from pathlib import Path

import pytest

from src.core.cost_estimator import (
    AVG_INPUT_TOKENS_PER_PAGE,
    OUTPUT_TO_INPUT_TOKEN_RATIO,
    estimate_chunk_cost,
    estimate_job_cost,
    estimate_job_cost_v2,
)
from src.services.claude_provider import ClaudeProvider
from src.services.ollama_provider import OllamaProvider

_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "pdf2zh" / "cost_golden_howbakingworks.json"


def test_estimate_job_cost_formula() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    estimate = estimate_job_cost(total_pages=100, provider=provider)

    expected_input = 100 * AVG_INPUT_TOKENS_PER_PAGE
    expected_output = int(expected_input * OUTPUT_TO_INPUT_TOKEN_RATIO)

    assert estimate.estimated_input_tokens == expected_input
    assert estimate.estimated_output_tokens == expected_output
    assert estimate.provider_name == "claude"
    assert estimate.estimated_cost_usd == pytest.approx(
        provider.estimate_cost(expected_input, expected_output)
    )


def test_estimate_job_cost_zero_pages() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    estimate = estimate_job_cost(total_pages=0, provider=provider)
    assert estimate.estimated_input_tokens == 0
    assert estimate.estimated_output_tokens == 0
    assert estimate.estimated_cost_usd == 0.0


def test_estimate_job_cost_ollama_is_free() -> None:
    provider = OllamaProvider(endpoint="http://localhost:11434")
    estimate = estimate_job_cost(total_pages=200, provider=provider)
    assert estimate.estimated_cost_usd == 0.0
    assert estimate.provider_name == "ollama"


def test_estimate_job_cost_negative_pages_raises() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(ValueError, match="total_pages"):
        estimate_job_cost(total_pages=-1, provider=provider)


def test_estimate_job_cost_marks_cost_source_estimated() -> None:
    """Architecture.md 6.6.6: v1.0 never has metered numbers — every CostEstimate
    must be labelled 'estimated', matching `Job.cost_source`."""
    provider = ClaudeProvider(api_key="sk-ant-fake")
    estimate = estimate_job_cost(total_pages=10, provider=provider)
    assert estimate.cost_source == "estimated"


def test_estimate_chunk_cost_scales_with_prompt_overhead_per_segment() -> None:
    """Architecture.md 6.6.6: pdf2zh resends the whole prompt file for every
    segment (F6), so `prompt_overhead_chars` must be multiplied by
    `segment_count`, not added once."""
    provider = ClaudeProvider(api_key="sk-ant-fake")
    source_text = "a" * 400  # 100 tokens at 4 chars/token

    few_segments_tokens, _, _ = estimate_chunk_cost(
        source_text=source_text,
        segment_count=1,
        prompt_overhead_chars=400,  # 100 tokens
        provider=provider,
    )
    many_segments_tokens, _, _ = estimate_chunk_cost(
        source_text=source_text,
        segment_count=10,
        prompt_overhead_chars=400,
        provider=provider,
    )

    assert many_segments_tokens > few_segments_tokens
    # base 100 (source) + overhead 100*segment_count.
    assert few_segments_tokens == 100 + 100
    assert many_segments_tokens == 100 + 1000


def test_estimate_chunk_cost_output_uses_vi_expansion_and_token_factor() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    source_text = "a" * 400  # 100 tokens

    _, output_tokens, _ = estimate_chunk_cost(
        source_text=source_text,
        segment_count=1,
        prompt_overhead_chars=0,
        provider=provider,
        vi_expansion=1.3,
        vi_token_factor=1.5,
    )

    assert output_tokens == int(100 * 1.3 * 1.5)


def test_estimate_chunk_cost_prices_via_provider_estimate_cost_only() -> None:
    """`provider` is used ONLY for arithmetic (`.estimate_cost()`), never a
    real API call (Architecture.md 6.6.2 R3.1) — Ollama (cost=0) proves this
    doesn't require any credentials or network access."""
    provider = OllamaProvider(endpoint="http://localhost:11434")

    _, _, cost_usd = estimate_chunk_cost(
        source_text="some text", segment_count=5, prompt_overhead_chars=50, provider=provider
    )

    assert cost_usd == 0.0


# === estimate_job_cost_v2() — Architecture.md 6.11, golden-file mandated by
# Protocol 5 R5-03 / Architecture.md 6.11.6. This is the test the $6.50
# real-money incident exists to justify: it turns the incident into an
# automated regression instead of a lesson that only lives in a document. ===


def _load_golden() -> dict:
    return json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))


def test_estimate_job_cost_v2_never_underestimates_golden_incident() -> None:
    """`tests/fixtures/pdf2zh/cost_golden_howbakingworks.json` is captured
    directly from the real pdf2zh cache backing the $6.50 incident
    (Architecture.md 6.11.2, S1) — NOT hand-written from assumptions
    (CLAUDE.md Protocol 5 R5-03). `segment_count` uses
    `requests_openai_billed` (2,989), not `requests_cached` (2,941): the
    billed count is what OpenAI actually charged for (retries included), and
    is the number `_count_text_segments()` is meant to approximate pre-job —
    using the cached (dedup'd) count would model a smaller, unrealistically
    cheap run.

    Architecture.md 6.11.6: the formula's own total token estimate must land
    in [1.0x, 1.6x] of the real reported token count — allowed to
    over-estimate (safe), never to under-estimate (this is exactly the
    failure mode, RC-2, that caused the incident).
    """
    golden = _load_golden()
    provider = ClaudeProvider(api_key="sk-ant-fake")

    estimate = estimate_job_cost_v2(
        source_text_chars=golden["source_text_chars"],
        segment_count=golden["requests_openai_billed"],
        prompt_overhead_chars=golden["prompt_chars_per_request"],
        provider=provider,
    )

    total_tokens = estimate.estimated_input_tokens + estimate.estimated_output_tokens
    real_tokens = golden["openai_reported_tokens"]
    ratio = total_tokens / real_tokens

    assert ratio >= 1.0, (
        f"estimate_job_cost_v2() UNDER-estimated the real $6.50 incident by "
        f"{(1 - ratio) * 100:.2f}% ({total_tokens} vs real {real_tokens}) — this is "
        "the exact failure mode (RC-2) that caused it. Never acceptable."
    )
    assert ratio <= 1.6, (
        f"estimate_job_cost_v2() over-estimated the golden incident by more than the "
        f"1.6x safety bound ({ratio:.2f}x) — Architecture.md 6.11.6."
    )


def test_estimate_job_cost_v2_shares_input_formula_with_estimate_chunk_cost() -> None:
    """Architecture.md 6.11.4 Lop 1 point 3: 'estimate_chunk_cost() va
    estimate_job_cost_v2() phai dung chung 1 ham loi. Neu Dev viet 2 cong
    thuc song song -> Reviewer reject.' — pins the input-token side of both
    formulas to the same numbers for the same inputs.
    """
    provider = ClaudeProvider(api_key="sk-ant-fake")
    source_text = "a" * 4000  # 1000 tokens at 4 chars/token

    chunk_input_tokens, _, _ = estimate_chunk_cost(
        source_text=source_text,
        segment_count=7,
        prompt_overhead_chars=300,
        provider=provider,
    )
    v2_estimate = estimate_job_cost_v2(
        source_text_chars=len(source_text),
        segment_count=7,
        prompt_overhead_chars=300,
        provider=provider,
    )

    assert v2_estimate.estimated_input_tokens == chunk_input_tokens


def test_estimate_job_cost_v2_uses_vi_char_expansion_for_output() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")

    estimate = estimate_job_cost_v2(
        source_text_chars=2000,
        segment_count=1,
        prompt_overhead_chars=0,
        provider=provider,
    )

    from src.core.cost_estimator import CHARS_PER_TOKEN_VI, VI_CHAR_EXPANSION

    assert estimate.estimated_output_tokens == int(2000 * VI_CHAR_EXPANSION / CHARS_PER_TOKEN_VI)


def test_estimate_job_cost_v2_marks_cost_source_estimated() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    estimate = estimate_job_cost_v2(
        source_text_chars=1000, segment_count=1, prompt_overhead_chars=100, provider=provider
    )
    assert estimate.cost_source == "estimated"


def test_estimate_job_cost_v2_negative_inputs_raise() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    with pytest.raises(ValueError, match="source_text_chars"):
        estimate_job_cost_v2(
            source_text_chars=-1, segment_count=1, prompt_overhead_chars=0, provider=provider
        )
    with pytest.raises(ValueError, match="segment_count"):
        estimate_job_cost_v2(
            source_text_chars=1, segment_count=-1, prompt_overhead_chars=0, provider=provider
        )


# === S7 — dich FR->VI (Architecture.md §6.26.5 audit buoc #6) ==============


def test_estimate_job_cost_v2_source_lang_en_is_default_and_matches_no_arg() -> None:
    """Byte/so-for-so regression: `source_lang="en"` (hoac bo qua) phai cho
    KET QUA GIONG HET truoc khi co S7 — golden file EN khong bi anh huong."""
    provider = ClaudeProvider(api_key="sk-ant-fake")
    no_arg = estimate_job_cost_v2(
        source_text_chars=12345, segment_count=9, prompt_overhead_chars=456, provider=provider
    )
    explicit_en = estimate_job_cost_v2(
        source_text_chars=12345,
        segment_count=9,
        prompt_overhead_chars=456,
        provider=provider,
        source_lang="en",
    )
    assert explicit_en.estimated_input_tokens == no_arg.estimated_input_tokens
    assert explicit_en.estimated_output_tokens == no_arg.estimated_output_tokens
    assert explicit_en.estimated_cost_usd == no_arg.estimated_cost_usd


def test_estimate_job_cost_v2_source_lang_fr_estimates_more_input_tokens_than_en() -> None:
    """Architecture.md §6.26.5 buoc #6: CHARS_PER_TOKEN_FR (3.0) < CHARS_PER_TOKEN_EN
    (4.0) co chu dich — chars/token THAP hon => token CAO hon => uoc DU, dung
    chieu an toan §6.11.6 ('duoc phep uoc du, cam uoc thieu')."""
    provider = ClaudeProvider(api_key="sk-ant-fake")
    en_estimate = estimate_job_cost_v2(
        source_text_chars=10000,
        segment_count=5,
        prompt_overhead_chars=200,
        provider=provider,
        source_lang="en",
    )
    fr_estimate = estimate_job_cost_v2(
        source_text_chars=10000,
        segment_count=5,
        prompt_overhead_chars=200,
        provider=provider,
        source_lang="fr",
    )
    assert fr_estimate.estimated_input_tokens > en_estimate.estimated_input_tokens
    # Output (VI) khong lien quan source_lang — khong doi.
    assert fr_estimate.estimated_output_tokens == en_estimate.estimated_output_tokens


def test_estimate_chunk_cost_source_lang_en_default_matches_no_arg() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    source_text = "a" * 4000
    no_arg = estimate_chunk_cost(
        source_text=source_text, segment_count=7, prompt_overhead_chars=300, provider=provider
    )
    explicit_en = estimate_chunk_cost(
        source_text=source_text,
        segment_count=7,
        prompt_overhead_chars=300,
        provider=provider,
        source_lang="en",
    )
    assert explicit_en == no_arg


def test_estimate_chunk_cost_source_lang_fr_estimates_more_input_tokens() -> None:
    provider = ClaudeProvider(api_key="sk-ant-fake")
    source_text = "a" * 4000
    en_input, _, _ = estimate_chunk_cost(
        source_text=source_text,
        segment_count=7,
        prompt_overhead_chars=300,
        provider=provider,
        source_lang="en",
    )
    fr_input, _, _ = estimate_chunk_cost(
        source_text=source_text,
        segment_count=7,
        prompt_overhead_chars=300,
        provider=provider,
        source_lang="fr",
    )
    assert fr_input > en_input
