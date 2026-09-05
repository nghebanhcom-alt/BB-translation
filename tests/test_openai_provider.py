"""Tests for OpenAIProvider.estimate_cost (Bug #8 fix).

Pure arithmetic — no real API calls needed (per project instructions), just
verifying the per-model pricing table is actually consulted via `self._model`
instead of a hardcoded gpt-4o rate.
"""

from src.services.openai_provider import OpenAIProvider


def test_estimate_cost_gpt4o() -> None:
    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")

    cost = provider.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000)

    assert cost == 2.5 + 10.0


def test_estimate_cost_gpt4o_mini() -> None:
    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")

    cost = provider.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000)

    assert cost == 0.15 + 0.60


def test_estimate_cost_gpt4o_mini_is_cheaper_than_gpt4o_for_same_tokens() -> None:
    mini = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
    full = OpenAIProvider(api_key="sk-test", model="gpt-4o")

    mini_cost = mini.estimate_cost(input_tokens=30_925, output_tokens=5_000)
    full_cost = full.estimate_cost(input_tokens=30_925, output_tokens=5_000)

    # Regression guard for the observed 16.67x QA Vong 5 discrepancy.
    assert full_cost / mini_cost == 2.5 / 0.15


def test_estimate_cost_unknown_model_falls_back_to_gpt4o_pricing() -> None:
    provider = OpenAIProvider(api_key="sk-test", model="gpt-4-turbo-not-in-table")

    cost = provider.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000)

    assert cost == 2.5 + 10.0


def test_estimate_cost_zero_tokens() -> None:
    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")

    assert provider.estimate_cost(input_tokens=0, output_tokens=0) == 0.0
