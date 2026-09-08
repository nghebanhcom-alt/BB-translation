"""Shared "what forms can a glossary term appear as" logic.

Architecture.md §6.18.8 T3 — this is the SINGLE most important function of
US-20 after the user's 2026-09-08 decision ("chỉ gợi ý từ không có trong
glossary"), because it is now the ONLY filter condition. It also fixes a
real bug (independent of US-20, cùng điểm mù) in
`GlossaryManager._count_occurrences()` (§6.6.5) which uses a raw
`re.escape(term_en)` word-boundary match — on the user's real 114-entry
glossary, 23 entries written as `"a / b"` or `"x (note)"`
(`knead / kneading`, `bloom (chocolate)`, `pound (lb)`, `tempering (sugar)`
…) never match a single-word document occurrence at all.

Protocol 6 (Architecture.md §6.18.8 T3 warning box): this module is meant to
be the ONE place both call sites (the document-scoped glossary filter in
`glossary_manager.py` and US-20's term extractor) eventually converge on.
This increment only wires it into US-20 — `glossary_manager.py` itself is
being edited in a separate, parallel session/task for an unrelated
word-boundary bug fix (`_count_occurrences()`), so it is intentionally left
untouched here to avoid a merge collision; wiring it into
`_count_occurrences()` is tracked as a separate follow-up bug (see
Architecture.md §6.18.8 T3 note and docs/CHANGELOG.md for this increment).

`glossary_match_forms()` never CUTS a document token to guess its base form
(that is "stemming" — lossy and prone to over-stemming on words we don't
control). Instead it EXPANDS a *known* glossary base into the small set of
surface forms it could plausibly take (plural/-ing/-ed) — an unknown form
just never matches, which is safe. See Architecture.md §6.18.8 T3 for the
full rationale ("SINH biến thể chứ không CẮT hậu tố").
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_PAREN_RE = re.compile(r"\(([^)]*)\)")


def _normalize_basic(text: str) -> str:
    """NFKC + curly-quote-to-straight + lowercase + whitespace collapse.

    Same normalization family used by `term_extractor.normalize_source_text()`
    so a candidate's `match_key` and a glossary entry's generated forms live
    in the same space and a plain set-membership check is enough (Architecture.md
    §6.18.8 T3: "so khớp ... KHÔNG so substring").
    """
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized.lower()


def _morphological_variants(base: str) -> set[str]:
    """Basic plural/-ing/-ed surface forms for a single normalized word.

    Deliberately simple (no NLP dependency — Architecture.md §6.18.8 T3
    explicitly rules out nltk/spacy here). Over-generation (a variant that
    never actually occurs) is harmless — it just never matches anything.
    Under-generation is the failure mode BR-TERM-02 cares about, so this
    errs toward generating more forms, not fewer.
    """
    base = base.strip()
    if len(base) < 3:
        return {base} if base else set()

    roots = {base}
    if base.endswith("ing") and len(base) > 5:
        stem = base[:-3]
        roots.add(stem)
        roots.add(stem + "e")  # baking -> bake
        if len(stem) >= 4 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            roots.add(stem[:-1])  # kidding -> kid (doubled consonant)
    if base.endswith("ed") and len(base) > 4:
        stem = base[:-2]
        roots.add(stem)
        roots.add(stem + "e")
        if len(stem) >= 4 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            roots.add(stem[:-1])
    if base.endswith("ies") and len(base) > 4:
        roots.add(base[:-3] + "y")
    if base.endswith("es") and len(base) > 4:
        roots.add(base[:-2])
    if base.endswith("s") and not base.endswith("ss") and len(base) > 3:
        roots.add(base[:-1])

    variants: set[str] = set()
    for root in roots:
        if len(root) < 3:
            continue
        variants.add(root)
        variants.add(root + "s")
        variants.add(root + "es")
        if root.endswith("y") and len(root) > 3 and root[-2] not in "aeiouy":
            variants.add(root[:-1] + "ies")
        if root.endswith("e"):
            variants.add(root[:-1] + "ing")
            variants.add(root[:-1] + "ed")
        else:
            variants.add(root + "ing")
            variants.add(root + "ed")
            if len(root) >= 3 and root[-1] not in "aeiouwxy" and root[-2] in "aeiou":
                # single closed syllable -> doubled consonant (pit -> pitting/pitted)
                variants.add(root + root[-1] + "ing")
                variants.add(root + root[-1] + "ed")
    return variants


def glossary_match_forms(term_en: str) -> set[str]:
    """Every normalized surface form a glossary entry's `term_en` could
    plausibly appear as in a translated document.

    Handles 3 real shapes found in the user's actual glossary (Architecture.md
    §6.18.8 T3, `docs/expert-review-us20-suggested-terms.md` §6.1):

    1. `"a / b"` (alternatives) — e.g. `"knead / kneading"`,
       `"baking stone / pizza stone"` — split on `/`, each side handled
       independently.
    2. `"x (note)"` (parenthetical) — e.g. `"bloom (chocolate)"`,
       `"pound (lb)"`, `"Swiss meringue buttercream (SMBC)"` — the outer
       phrase (with the parenthetical stripped) AND the parenthetical's own
       content are BOTH kept as alternatives. Note: Architecture.md's prose
       says the parenthetical is only kept "nếu ≥3 ký tự và không phải viết
       tắt thuần", but its own worked examples keep `"lb"` (2 chars) and
       `"SMBC"` (a pure abbreviation) — the examples are followed here
       (always keep the parenthetical content) since the risk asymmetry
       Architecture.md itself states ("thà gộp nhầm còn hơn bỏ sót") favors
       over-inclusion for a filter whose only job is "already in glossary,
       don't show again".
    3. Plain multi-word phrases — the phrase's own plural/-ing/-ed
       morphology is generated off its LAST token only (`rolling pin` ->
       `rolling pins`, not `rollings pin`).
    """
    if not term_en:
        return set()

    alternatives: list[str] = []
    for part in term_en.split("/"):
        part = part.strip()
        if not part:
            continue
        paren_match = _PAREN_RE.search(part)
        outer = _PAREN_RE.sub("", part).strip()
        outer = _WHITESPACE_RE.sub(" ", outer)
        if outer:
            alternatives.append(outer)
        if paren_match:
            inner = paren_match.group(1).strip()
            if inner:
                alternatives.append(inner)

    forms: set[str] = set()
    for alt in alternatives:
        normalized = _normalize_basic(alt)
        if not normalized:
            continue
        if " " in normalized:
            forms.add(normalized)
            tokens = normalized.split(" ")
            head, last = tokens[:-1], tokens[-1]
            for variant in _morphological_variants(last):
                forms.add(" ".join([*head, variant]))
        else:
            forms |= _morphological_variants(normalized)

    return forms


def normalize_candidate_key(surface: str) -> str:
    """Normalize a term-extraction candidate's surface text into the same
    space `glossary_match_forms()` produces, for a direct set-membership
    check (no substring matching — Architecture.md §6.18.8 T3).
    """
    return _normalize_basic(surface)
