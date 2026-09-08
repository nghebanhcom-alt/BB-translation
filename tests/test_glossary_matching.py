"""Architecture.md §6.18.8 T3 — `glossary_match_forms()` is the SOLE filter
condition for US-20 after the user's 2026-09-08 decision. Every case here
comes straight from `docs/expert-review-us20-suggested-terms.md` §6.1 (real
114-entry glossary) — these are documented bugs the OLD `.lower()`-only
matching produced, not invented edge cases.
"""

import json
from pathlib import Path

from src.core.glossary_matching import glossary_match_forms, normalize_candidate_key

_REAL_GLOSSARY_PATH = Path(__file__).parent / "fixtures/term_extraction/real_glossary_114.json"


def test_slash_alternatives_both_sides_present() -> None:
    forms = glossary_match_forms("knead / kneading")
    assert "knead" in forms
    assert "kneading" in forms


def test_parenthetical_kept_as_extra_alternative_even_when_short() -> None:
    # Architecture.md's own worked example keeps "lb" (2 chars) despite the
    # prose nearby saying ">=3 ky tu" — the examples win (see
    # src/core/glossary_matching.py module docstring for the full reasoning).
    forms = glossary_match_forms("pound (lb)")
    assert "pound" in forms
    assert "lb" in forms


def test_parenthetical_pure_abbreviation_kept_too() -> None:
    forms = glossary_match_forms("Swiss meringue buttercream (SMBC)")
    assert "swiss meringue buttercream" in forms
    assert "smbc" in forms


def test_bloom_chocolate_matches_bare_bloom() -> None:
    forms = glossary_match_forms("bloom (chocolate)")
    assert "bloom" in forms


def test_plural_and_gerund_variants_generated() -> None:
    forms = glossary_match_forms("meringue")
    assert "meringues" in forms
    forms = glossary_match_forms("banneton")
    assert "bannetons" in forms
    forms = glossary_match_forms("crust")
    assert "crusts" in forms
    forms = glossary_match_forms("mousse")
    assert "mousses" in forms


def test_no_substring_matching_chocolate_ganache_survives_ganache() -> None:
    """T3: "ganache đã có -> chocolate ganache VẪN được gợi ý (nó là thuật
    ngữ khác)" — glossary_match_forms() must never make a bigram match just
    because it CONTAINS a known unigram.
    """
    forms = glossary_match_forms("ganache")
    assert "chocolate ganache" not in forms
    assert normalize_candidate_key("chocolate ganache") not in forms


def test_curly_apostrophe_normalizes_same_as_straight() -> None:
    forms = glossary_match_forms("baker's percentage")
    assert normalize_candidate_key("baker’s percentage") in forms


def test_empty_term_returns_empty_set() -> None:
    assert glossary_match_forms("") == set()
    assert glossary_match_forms("   ") == set()


def test_real_glossary_114_entries_cover_documented_leak_cases() -> None:
    """docs/expert-review-us20-suggested-terms.md §6.1: with the OLD
    `.lower()`-only matching, 13 n-grams equivalent to an existing entry
    still leaked into "Chờ duyệt" on the real 114-entry glossary. Every one
    of them must now be covered by `glossary_match_forms()`.
    """
    real_terms = json.loads(_REAL_GLOSSARY_PATH.read_text(encoding="utf-8"))
    existing_forms: set[str] = set()
    for term_en in real_terms:
        existing_forms |= glossary_match_forms(term_en)

    leaked_in_old_code = [
        "pound",
        "ounce",
        "bloom",
        "tempering",
        "whipping",
        "kneading",
        "teaspoon",
        "glaze",
        "silpat",
        "fahrenheit",
        "knead",
        "whisking",
        "tablespoon",
    ]
    for term in leaked_in_old_code:
        assert term in existing_forms, f"{term!r} should now be covered by glossary_match_forms()"

    plural_cases = ["crusts", "meringues", "mousses"]
    for term in plural_cases:
        assert term in existing_forms, f"{term!r} (plural) should now be covered"
