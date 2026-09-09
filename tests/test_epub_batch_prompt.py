"""Tests for `build_epub_batch_prompt()`/`parse_epub_batch_response()`
(Architecture.md 6.20.12 X4, US-22 buoc 2/3).

`parse_epub_batch_response()` against a REAL LLM reply (not hand-written) is
covered separately in `tests/test_epub_batch_golden_fixture.py` (Protocol 5
muc 3, `tests/fixtures/epub_llm/`) — this file only tests the parser's
tolerance rules in isolation (fence stripping, missing/extra/empty id
handling) and the prompt builder's composition contract.
"""

import json

from src.core.prompt_builder import (
    EPUB_BATCH_CONTRACT_MARKER,
    build_epub_batch_prompt,
    parse_epub_batch_response,
)

# --- build_epub_batch_prompt() ------------------------------------------


def test_build_epub_batch_prompt_preserves_glossary_prompt_verbatim() -> None:
    glossary_prompt = "GLOSSARY-PROMPT-CANARY-XYZ line 1\nline 2"

    result = build_epub_batch_prompt(glossary_prompt)

    # X4: "glossary_prompt hien co — khong sua 1 chu". Substring match proves
    # it was concatenated, not paraphrased/rebuilt.
    assert glossary_prompt in result


def test_build_epub_batch_prompt_contains_marker_and_inline_tag_list() -> None:
    result = build_epub_batch_prompt("(glossary)")

    assert EPUB_BATCH_CONTRACT_MARKER in result
    for tag in ("strong", "em", "b", "i", "sup", "sub", "br", "a", "span", "small"):
        assert tag in result
    assert "<code>" in result or "code" in result
    assert "json" in result.lower()


def test_build_epub_batch_prompt_includes_one_shot_example_with_fraction() -> None:
    result = build_epub_batch_prompt("(glossary)")

    # X1/X4: vi du one-shot phai co the inline, con so, VA <sup>/<sub>.
    assert "<sup>" in result
    assert "<sub>" in result
    assert '"id"' in result
    assert '"html"' in result


# --- parse_epub_batch_response() ------------------------------------------


def test_parse_clean_json_object() -> None:
    raw = json.dumps({"0": "Xin chao", "1": "Tam biet"})

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {"0": "Xin chao", "1": "Tam biet"}


def test_parse_strips_markdown_code_fence() -> None:
    raw = '```json\n{"0": "Xin chao"}\n```'

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    assert result == {"0": "Xin chao"}


def test_parse_strips_plain_code_fence_without_json_hint() -> None:
    raw = '```\n{"0": "Xin chao"}\n```'

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    assert result == {"0": "Xin chao"}


def test_parse_strips_leading_prose() -> None:
    raw = 'Here is the translation:\n{"0": "Xin chao"}'

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    # Leading prose before the JSON is NOT stripped by design (only fences +
    # surrounding whitespace) — json.loads() then fails on the whole string,
    # so this must come back empty (id "missing"), not raise or crash.
    assert result == {}


def test_parse_missing_id_is_excluded_not_defaulted() -> None:
    raw = json.dumps({"0": "Xin chao"})

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {"0": "Xin chao"}
    assert "1" not in result


def test_parse_empty_string_value_treated_as_missing() -> None:
    """X4 point 6: "tuyet doi khong tra chuoi rong" — an empty value reaching
    the parser must be dropped exactly like a missing id, never written into
    translations (E-09's exact shape from bilingual_book_maker/Bug #5)."""
    raw = json.dumps({"0": "Xin chao", "1": "", "2": "   "})

    result = parse_epub_batch_response(raw, expected_ids={"0", "1", "2"})

    assert result == {"0": "Xin chao"}
    assert "1" not in result
    assert "2" not in result


def test_parse_unexpected_extra_id_is_dropped_silently() -> None:
    raw = json.dumps({"0": "Xin chao", "99": "hallucinated"})

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    assert result == {"0": "Xin chao"}
    assert "99" not in result


def test_parse_int_like_keys_from_json_still_match_string_expected_ids() -> None:
    """JSON object keys are always strings once decoded, but a model that
    emits e.g. `{"0": ...}` where "0" round-trips as the Python str "0" must
    still match `expected_ids={"0"}`, not `{0}` (int) — this asserts the
    `str(key)` normalization is actually exercised, not accidentally a no-op
    because `json.loads` already gives back str keys."""
    raw = json.dumps({0: "invalid json actually"}) if False else '{"0": "Xin chao"}'

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    assert result == {"0": "Xin chao"}


def test_parse_non_string_value_treated_as_missing() -> None:
    raw = json.dumps({"0": "Xin chao", "1": 123})

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {"0": "Xin chao"}
    assert "1" not in result


def test_parse_totally_invalid_json_returns_empty_dict() -> None:
    result = parse_epub_batch_response("not json at all {{{", expected_ids={"0", "1"})

    assert result == {}


def test_parse_json_array_top_level_returns_empty_dict() -> None:
    """Contract requires a JSON OBJECT, not an array — a model that replies
    with `["Xin chao", "Tam biet"]` must count as every id missing, not
    crash or silently zip by position (id order is not guaranteed)."""
    raw = json.dumps(["Xin chao", "Tam biet"])

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {}


def test_parse_preserves_inline_html_tags_in_value() -> None:
    raw = json.dumps({"0": "<strong>2 cups</strong> bot mi, 1<sup>1</sup>/<sub>3</sub> tsp muoi"})

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    assert result["0"] == "<strong>2 cups</strong> bot mi, 1<sup>1</sup>/<sub>3</sub> tsp muoi"


# ---------------------------------------------------------------------------
# Trailing garbage sau JSON hop le -- Dev tu bat gap khi chay live E2E
# full-book cho US-22 Buoc 2/3 (tests/test_epub_batch_golden_fixture.py co
# ban ghi lai CHINH phan hoi that gay ra bug nay, capture tu DeepSeek —
# 2 test duoi day dung chuoi tong hop, chi de kiem tra logic bien gioi ma
# fixture that khong tien loi kiem (vd nhieu id, hoac loi KHONG phai
# "Extra data").
# ---------------------------------------------------------------------------


def test_parse_recovers_single_trailing_character_after_valid_json() -> None:
    raw = '{"0": "Xin chao"}"'  # dung 1 dau " thua sau `}` -- dang bug that

    result = parse_epub_batch_response(raw, expected_ids={"0"})

    assert result == {"0": "Xin chao"}


def test_parse_recovers_trailing_prose_after_valid_json_with_multiple_ids() -> None:
    raw = '{"0": "Xin chao", "1": "Tam biet"}\n\nHy vong ban hai long voi ban dich.'

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {"0": "Xin chao", "1": "Tam biet"}


def test_parse_genuinely_truncated_json_still_returns_empty_dict() -> None:
    """Phan biet voi ca "Extra data": JSON bi CAT CUT GIUA CHUNG (vd het
    max_tokens) khong phai loi "Extra data" -- van phai ve `{}` nhu cu, KHONG
    duoc am tham "phuc hoi" 1 phan noi dung dang do dang/co the sai."""
    raw = '{"0": "Xin chao", "1": "Tam bi'  # cat cut, thieu dau " va } dong

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {}
