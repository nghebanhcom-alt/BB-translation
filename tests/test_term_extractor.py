"""Architecture.md §6.18.8 (Final Decision) — `src/core/term_extractor.py`.

Test strings for `normalize_source_text()` are the EXACT strings
Architecture.md §6.18.8 T4 lists as "bắt buộc" ("chuỗi lấy từ số đo thật,
không bịa") — most were measured directly off the user's real PDFs (see
`docs/expert-review-us20-suggested-terms.md` §2), and the app's own
Architecture.md quotes the same short fragments as its evidence, so
reproducing them here (a handful of words each, not prose) is the same
scope of quotation Architecture.md itself already carries.
"""

import json
from pathlib import Path

from src.core.config import Settings
from src.core.glossary_matching import glossary_match_forms
from src.core.term_extractor import extract_terms, normalize_source_text

_REAL_GLOSSARY_PATH = Path(__file__).parent / "fixtures/term_extraction/real_glossary_114.json"
_MINERU_DOCUMENT_MD = Path(__file__).parent / "fixtures/mineru/parse_only_txt_figoni25/document.md"


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)


# --- normalize_source_text() — T4 bước 1-6 -----------------------------------


def test_ligature_lone_token_merges_fl_our() -> None:
    assert "flour" in normalize_source_text("was added to reﬂ our the mixture")


def test_ligature_suffix_merges_reflect() -> None:
    # Real string from the user's PDF (Architecture.md §6.18.8 T4 table).
    assert "reflect" in normalize_source_text("was added to reﬂ ect the increasing")


def test_ligature_suffix_merges_emulsifiers() -> None:
    assert "Emulsifiers" in normalize_source_text("Oils, and Emulsiﬁ ers  205")


def test_lone_ff_ligature_merges_but_real_word_staff_is_untouched() -> None:
    """ff/ffi/ffl only merge as a LONE token, never as a suffix of a real
    word (Architecture.md §6.18.8 T4 bước 4, first clause vs second clause).
    Regression guard for the false-positive this distinction exists to
    avoid: "staff members" must never become "staffmembers".
    """
    assert "staff members" in normalize_source_text("the staff members arrived")


def test_curly_apostrophe_normalizes_to_straight() -> None:
    assert "baker's" in normalize_source_text("baker’s percentage")


def test_dehyphenation_across_linebreak() -> None:
    assert normalize_source_text("choco-\nlate") == "chocolate"


def test_pate_a_choux_survives_intact() -> None:
    normalized = normalize_source_text("such as cookies and pâte à choux (puff pastry)")
    assert "pâte à choux" in normalized


def test_html_table_and_markdown_image_stripped() -> None:
    normalized = normalize_source_text("<table><tr><td>flour</td></tr></table> ![](img.jpg)")
    assert "flour" in normalized
    assert "<td>" not in normalized
    assert "![" not in normalized


def test_markdown_heading_marker_stripped_but_text_kept() -> None:
    normalized = normalize_source_text("## Chapter One\nSome text")
    assert "Chapter One" in normalized
    assert "##" not in normalized


# --- extract_terms() end to end ----------------------------------------------


def test_min_occurrences_floor_short_doc_is_2() -> None:
    settings = _settings()
    text = "Turbinado sugar. Turbinado sugar again."
    candidates = extract_terms(text, set(), settings)
    keys = {c.match_key for c in candidates}
    assert "turbinado sugar" in keys

    text_once = "Turbinado sugar is used once here."
    candidates_once = extract_terms(text_once, set(), settings)
    assert "turbinado sugar" not in {c.match_key for c in candidates_once}


def test_nesting_collapse_is_max_not_sum() -> None:
    """Architecture.md §6.18.8 T5 golden test: `gluten` must survive even
    though its occurrences are collectively (summed across DIFFERENT
    bigrams) 100% "contained" in some longer n-gram — no SINGLE bigram
    individually reaches the 80% absorption threshold.
    """
    parts = (
        ["Gluten strands trap gas."] * 3
        + ["Gluten proteins form structure."] * 3
        + ["Gluten networks matter here."] * 2
        + ["Gluten tests confirm results."] * 2
    )
    text = " ".join(parts)
    candidates = extract_terms(text, set(), _settings())
    gluten = next((c for c in candidates if c.match_key == "gluten"), None)
    assert gluten is not None, "gluten (n=1) must survive nesting collapse under MAX-not-SUM"
    assert gluten.occurrence_count == 10


def test_nesting_collapse_does_absorb_when_one_long_ngram_dominates() -> None:
    """Sanity check for the other side of the same rule: when ONE specific
    long n-gram really does account for >=80% of the short one's
    occurrences, the short one IS absorbed. Vary the word AFTER "laminated
    dough" so the 2-gram itself (not a longer 3-gram) is the dominant
    survivor, isolating 1-gram-into-2-gram absorption from the 2-into-3
    cascade already covered by `test_nesting_collapse_is_max_not_sum`.
    """
    text = (
        "Laminated dough rests overnight in the fridge. "
        "Laminated dough needs careful folding technique. "
        "Laminated dough is used for croissants here."
    )
    candidates = extract_terms(text, set(), _settings())
    keys = {c.match_key for c in candidates}
    assert "laminated dough" in keys
    assert "laminated" not in keys


def test_glossary_match_key_filters_whole_ngram_only_no_substring() -> None:
    existing_forms = glossary_match_forms("ganache")
    text = (
        "Fold in the chocolate ganache gently. "
        "The chocolate ganache sets in the fridge. "
        "Cut the chocolate ganache carefully now."
    )
    candidates = extract_terms(text, existing_forms, _settings())
    keys = {c.match_key for c in candidates}
    assert "ganache" not in keys
    assert "chocolate ganache" in keys


def test_stopword_middle_flag_on_3gram_and_exemption_for_a_choux() -> None:
    text = " ".join(["We use flour and sugar together in this mix."] * 3)
    candidates = extract_terms(text, set(), _settings())
    flagged = next((c for c in candidates if c.match_key == "flour and sugar"), None)
    assert flagged is not None
    assert "stopword_middle" in flagged.noise_flags.split(",")

    text_pate = " ".join(["The pâte à choux recipe is classic."] * 3)
    candidates_pate = extract_terms(text_pate, set(), _settings())
    pate = next((c for c in candidates_pate if c.match_key == "pâte à choux"), None)
    assert pate is not None
    assert "stopword_middle" not in pate.noise_flags.split(",")


def test_proper_noun_flag_mid_clause_capitalized_repeated_name() -> None:
    text = " ".join(["The author is Cauvain and this book is by Cauvain."] * 3)
    candidates = extract_terms(text, set(), _settings())
    cauvain = next((c for c in candidates if c.match_key == "cauvain"), None)
    assert cauvain is not None
    assert "proper_noun" in cauvain.noise_flags.split(",")


def test_proper_noun_flag_on_allcaps_acronym() -> None:
    text = (
        "CCFRA released a report this year. "
        "According to CCFRA, standards improved. "
        "Bakers rely on CCFRA for guidance."
    )
    candidates = extract_terms(text, set(), _settings())
    acronym = next((c for c in candidates if c.match_key == "ccfra"), None)
    assert acronym is not None
    assert "proper_noun" in acronym.noise_flags.split(",")


def test_plural_merged_flag_and_count_accumulation() -> None:
    text = (
        "Weigh the flour. More flour is needed. Sift the flours well. These flours vary by brand."
    )
    candidates = extract_terms(text, set(), _settings())
    flour = next((c for c in candidates if c.match_key == "flour"), None)
    assert flour is not None
    assert flour.occurrence_count == 4  # 2x "flour" + 2x "flours" merged
    assert "plural_merged" in flour.noise_flags.split(",")


def test_max_suggested_terms_per_job_is_a_safety_valve_not_a_quality_cutoff() -> None:
    settings = _settings(max_suggested_terms_per_job=2)
    text = "Alpha beta. Gamma delta. Epsilon zeta. Alpha beta again here now."
    # Below floor by itself but repeat everything so several distinct
    # bigrams clear min_occurrences=2 and exceed the artificially tiny cap.
    text = " ".join([text] * 2)
    candidates = extract_terms(text, set(), settings)
    assert len(candidates) <= 2


def test_real_glossary_114_filters_documented_leak_terms_end_to_end() -> None:
    """Architecture.md §6.18.8 T8 gate #3, run against the algorithm (not
    just `glossary_match_forms()` in isolation): with the real 114-entry
    glossary applied, none of the documented leak terms should appear in
    the suggestion list even when they occur in the source document.
    """
    real_terms = json.loads(_REAL_GLOSSARY_PATH.read_text(encoding="utf-8"))
    existing_forms: set[str] = set()
    for term_en in real_terms:
        existing_forms |= glossary_match_forms(term_en)

    text = " ".join(
        [
            "Weigh one pound of butter and one ounce of chocolate for the bloom test.",
            "Tempering the chocolate takes patience; kneading the dough builds gluten.",
            "Use a teaspoon of vanilla. Whipping cream is folded in gently.",
            "The crusts and meringues and mousses should be crisp and light.",
        ]
        * 3
    )
    candidates = extract_terms(text, existing_forms, _settings())
    surfaces_lower = {c.term_en.lower() for c in candidates}
    for leaked_term in (
        "pound",
        "ounce",
        "bloom",
        "tempering",
        "whipping",
        "kneading",
        "teaspoon",
        "crusts",
        "meringues",
        "mousses",
    ):
        assert leaked_term not in surfaces_lower, f"{leaked_term!r} should be filtered by glossary"


def test_real_mineru_document_markdown_html_table_noise_does_not_dominate() -> None:
    """Architecture.md §6.18.8 T4 mục "Bổ sung 1 — nhánh Markdown": on real
    MinerU OCR output, HTML table tags (`<td>`, `<tr>`) must not survive as
    candidates once `normalize_source_text()`'s HTML-stripping step runs —
    this fixture is the same real file US-15 already ships
    (`tests/fixtures/mineru/parse_only_txt_figoni25/document.md`).
    """
    raw_text = _MINERU_DOCUMENT_MD.read_text(encoding="utf-8")
    candidates = extract_terms(raw_text, set(), _settings())
    surfaces_lower = {c.term_en.lower() for c in candidates}
    for html_noise in ("td", "tr", "td td td", "tr tr td"):
        assert html_noise not in surfaces_lower
