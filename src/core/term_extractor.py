"""US-20 "Các từ mới" — rule-based term extraction (Architecture.md §6.18,
FINAL algorithm per §6.18.8 "Final Decision sau phản biện Domain Expert +
quyết định mới của user"). $0 cost, no LLM — BR-TERM-01/02/03.

§6.18.2's original pseudo-code (bước 1, 3, 4, 5, 6) is SUPERSEDED by §6.18.8
T1-T5; this module implements ONLY the superseding version. Do not reintroduce
the old `en_common.txt` "common word" blacklist (T2) or the hard cutoff of 40
(T1) — both were measured on real data to actively delete real glossary
terms (`proof`, `score`, `cream`, `rest`, `turn`) while keeping the most
generic words (`flour`, `sugar`, `egg`). See §6.18.8 for the full evidence.

Pipeline, in order:
    normalize_source_text() -> segment on punctuation -> tokenize each
    segment -> generate 1..3-grams (T4) -> count + track nested-containment
    + mid-clause-capitalization per n-gram key -> apply the frequency floor
    (T5) -> apply nested-absorption ("MAX not SUM", T5) -> apply the
    glossary filter (T3, via `src.core.glossary_matching`) -> merge
    singular/plural pairs within the surviving pool (T4 `plural_merged`) ->
    compute noise flags + rank_score (T4/T5) -> sort, apply the DB
    safety-valve cap (T1, NOT a quality cutoff) -> return.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.glossary_matching import normalize_candidate_key

if TYPE_CHECKING:
    from src.core.config import Settings

logger = logging.getLogger(__name__)

_WORDLIST_DIR = Path(__file__).parent / "wordlists"

# --- normalize_source_text() building blocks (§6.18.8 T4) ------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_HEADING_MARKER_RE = re.compile(r"(?m)^#{1,6}[ \t]*")
_CURLY_SQUOTE_RE = re.compile(r"[‘’]")
# Rule A (T4 bước 4, first clause): a LONE token that IS exactly fi/fl/ffi/ffl/ff,
# followed by whitespace and a lowercase fragment -> merge (`fl our` -> `flour`).
# Kept separate from Rule B below so `ff`/`ffi`/`ffl` are NEVER merged as a
# *suffix* of a longer real word (e.g. "staff members" must NOT become
# "staffmembers" — "ff" only triggers when the WHOLE token is just "ff").
_LONE_FF_LIGATURE_RE = re.compile(r"\b(ffi|ffl|ff)[ \t]+([a-z]{1,20})\b")
# Rule B (T4 bước 4, second clause): a token ENDING in fi/fl (only — not
# ff/ffi/ffl) followed by whitespace and a lowercase fragment -> merge
# (`emulsifi ers` -> `emulsifiers`, `refl ect` -> `reflect`). Safe to apply
# broadly: no common English word both ends in bare "fi"/"fl" AND is
# genuinely followed by a separate lowercase word at that exact boundary.
_SUFFIX_FI_FL_LIGATURE_RE = re.compile(r"\b([A-Za-z]*(?:fi|fl))[ \t]+([a-z]{1,20})\b")
_DEHYPHEN_RE = re.compile(r"(?<=[a-z])-[ \t]*\n[ \t]*(?=[a-z])")
# Explicit punctuation set to segment on (T4 bước 6) — deliberately wider
# than ".!?" alone: a 3-gram must not cross a comma either
# ("flour, water" must never become the candidate "flour water").
_SEGMENT_SPLIT_RE = re.compile(r"[.!?;:,()\[\]\"“”—•|]+")
# T4 bước 7 — accepts Latin-1 Supplement letters (À-ÿ) so `pâte`, `crème`,
# `à` survive as real tokens instead of being butchered into `p`/`te`.
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']*(?:-[A-Za-zÀ-ÿ']+)*")
_DIGIT_RE = re.compile(r"\d")

_STOPWORD_MIDDLE_EXEMPT = frozenset({"of", "à", "de", "en", "au", "aux"})
_NESTING_ABSORPTION_RATIO = 0.8
_NOISE_RANK_PENALTY = 0.3


@lru_cache(maxsize=1)
def _load_function_words() -> frozenset[str]:
    path = _WORDLIST_DIR / "en_function_words.txt"
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        words.add(stripped.lower())
    return frozenset(words)


@lru_cache(maxsize=1)
def _load_freq_ranks() -> dict[str, int] | None:
    """Background English word-frequency ranks (T2 "specificity" ranking
    signal) — OPTIONAL. Ship `data/wordlists/en_freq_top50k.tsv`
    (word<TAB>rank, most-frequent = rank 1) to enable it. Absent by design
    in this increment (no such list was available to bundle — see
    docs/CHANGELOG.md for this increment) — `specificity()` degrades to a
    flat `1.0` for every term when this returns `None`, which
    Architecture.md §6.18.8 T2 explicitly calls a safe degrade: "chỉ mất
    chất lượng sắp xếp, không đổi tập hiển thị".
    """
    path = _WORDLIST_DIR / "en_freq_top50k.tsv"
    if not path.exists():
        return None
    ranks: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        word, rank_text = parts
        try:
            ranks[word.strip().lower()] = int(rank_text.strip())
        except ValueError:
            continue
    return ranks or None


def normalize_source_text(text: str) -> str:
    """T4 bước 1-6 (bước 7 — tokenizer — is applied separately per segment).

    Order matters (each step's evidence is a real string measured on the
    user's own PDFs/OCR output — Architecture.md §6.18.8 T4 table):
    1. Strip HTML tags + Markdown image/heading syntax (parse_only/EPUB source).
    2. Unicode NFKC (ﬁ -> fi, ﬂ -> fl, ﬃ -> ffi).
    3. Curly single quotes -> straight (baker's survives on real PDF text).
    4. Re-join ligature-broken word fragments a PDF's text extraction split
       across a stray space (`fl our` -> `flour`).
    5. Remove line-break hyphenation (`choco-\\nlate` -> `chocolate`).
    Segmenting on punctuation (bước 6) and tokenizing (bước 7) happen in
    `extract_terms()` since they need to stay separate per-segment lists,
    not one big string.
    """
    text = _MD_IMAGE_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _MD_HEADING_MARKER_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = _CURLY_SQUOTE_RE.sub("'", text)
    text = _LONE_FF_LIGATURE_RE.sub(lambda m: m.group(1) + m.group(2), text)
    text = _SUFFIX_FI_FL_LIGATURE_RE.sub(lambda m: m.group(1) + m.group(2), text)
    text = _DEHYPHEN_RE.sub("", text)
    return text


def _tokenize_segment(segment: str) -> list[tuple[str, str]]:
    """Returns `(surface, lower)` pairs, in order, for one punctuation-bounded segment."""
    return [(m.group(0), m.group(0).lower()) for m in _TOKEN_RE.finditer(segment)]


def _singularize_last_token(token: str) -> str:
    """Light, deliberately-conservative normalization used ONLY to merge
    singular/plural pairs *within the surviving candidate pool* (T4
    `plural_merged`) — NOT the same thing as `glossary_match_forms()`'s
    variant *expansion* (T3), which is what actually enforces BR-TERM-02.
    Under-merging here (e.g. `starches`/`starch` not merging) just means two
    rows instead of one, not a correctness bug — so this stays simple
    instead of chasing English's many `-es` irregularities.
    """
    if token.endswith("ies") and len(token) > 5:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _specificity(surface_lower: str) -> float:
    ranks = _load_freq_ranks()
    if not ranks:
        return 1.0
    tokens = surface_lower.split(" ")
    known_ranks = [ranks[t] for t in tokens if t in ranks]
    if not known_ranks:
        return 1.0
    # The MOST frequent (lowest rank number) constituent token dominates —
    # a phrase is only as "common" as its most generic word.
    best_rank = min(known_ranks)
    return min(1.0, best_rank / 50_000)


@dataclass(frozen=True)
class TermCandidate:
    term_en: str
    match_key: str
    ngram_size: int
    noise_flags: str
    occurrence_count: int
    rank_score: float


@dataclass
class _RawCandidate:
    key: str
    n: int
    surface: str
    match_key: str
    count: int
    noise_flags: set[str]


def extract_terms(
    source_text: str,
    existing_forms: set[str],
    settings: Settings,
) -> list[TermCandidate]:
    """Architecture.md §6.18.8 — see module docstring for pipeline order.

    `existing_forms` MUST already be the union of `glossary_match_forms()`
    over every glossary entry in scope (global + project, BR-GLOSS-06) — NOT
    a plain `{term_en.lower()}` set (that was the bug §6.18.8 T3 fixes).
    """
    normalized = normalize_source_text(source_text)
    segments = [s for s in _SEGMENT_SPLIT_RE.split(normalized) if s.strip()]
    function_words = _load_function_words()

    counts: dict[int, dict[str, int]] = {1: {}, 2: {}, 3: {}}
    surfaces: dict[str, Counter[str]] = defaultdict(Counter)
    cap_mid_hits: dict[str, int] = defaultdict(int)
    # short_key -> Counter(long_key -> how many of short_key's occurrences
    # that specific long_key's span contains). Kept per-key-pair (not summed
    # across every containing long n-gram) so the "MAX, not SUM" rule
    # (§6.18.8 T5) can be applied correctly.
    absorption: dict[str, Counter[str]] = defaultdict(Counter)
    total_tokens = 0

    for segment in segments:
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        total_tokens += len(tokens)

        windows: dict[int, list[tuple[int, str, list[tuple[str, str]]]]] = {1: [], 2: [], 3: []}
        for n in (1, 2, 3):
            for i in range(len(tokens) - n + 1):
                window = tokens[i : i + n]
                first_lower, last_lower = window[0][1], window[-1][1]
                if first_lower in function_words or last_lower in function_words:
                    continue
                key = " ".join(lower for _surface, lower in window)
                if _DIGIT_RE.search(key):
                    continue
                if len(key.replace(" ", "")) < 3:
                    continue
                windows[n].append((i, key, window))

        for n in (1, 2, 3):
            for i, key, window in windows[n]:
                counts[n][key] = counts[n].get(key, 0) + 1
                surface = " ".join(s for s, _lower in window)
                surfaces[key][surface] += 1
                is_capitalized_mid_clause = i > 0 and all(
                    s[:1].isupper() for s, _lower in window if s
                )
                if is_capitalized_mid_clause:
                    cap_mid_hits[key] += 1

        for i1, key1, _w1 in windows[1]:
            for n2 in (2, 3):
                for i2, key2, _w2 in windows[n2]:
                    if i2 <= i1 <= i2 + n2 - 1:
                        absorption[key1][key2] += 1
        for i1, key1, _w1 in windows[2]:
            for i2, key2, _w2 in windows[3]:
                if i2 <= i1 and (i1 + 1) <= (i2 + 2):
                    absorption[key1][key2] += 1

    threshold = (
        settings.term_min_occurrences
        if total_tokens >= 50_000
        else settings.term_min_occurrences_short_doc
    )

    def _is_kept_long_ngram(n_long: int, long_key: str) -> bool:
        long_count = counts[n_long].get(long_key, 0)
        if long_count == 0:
            return False
        if long_count >= threshold:
            return True
        # A glossary-matched long n-gram still counts as "kept" for
        # absorption purposes even below the frequency floor — it will be
        # excluded from the OUTPUT by the glossary filter below, but it must
        # still be allowed to absorb its shorter sub-phrases (T5: fixes
        # `puff` #35 orphaned once `puff pastry` was removed pre-absorption
        # in the old, superseded step order).
        representative = surfaces[long_key].most_common(1)[0][0]
        return normalize_candidate_key(representative) in existing_forms

    absorbed: set[tuple[int, str]] = set()
    for n in (1, 2):
        for key, total in counts[n].items():
            if total == 0:
                continue
            best = 0
            for long_key, hits in absorption.get(key, {}).items():
                n_long = long_key.count(" ") + 1
                if _is_kept_long_ngram(n_long, long_key):
                    best = max(best, hits)
            if best / total >= _NESTING_ABSORPTION_RATIO:
                absorbed.add((n, key))

    raw_candidates: list[_RawCandidate] = []
    for n in (1, 2, 3):
        for key, count in counts[n].items():
            if count < threshold:
                continue
            if (n, key) in absorbed:
                continue
            representative = surfaces[key].most_common(1)[0][0]
            match_key = normalize_candidate_key(representative)
            if match_key in existing_forms:
                continue

            noise: set[str] = set()
            is_all_caps_acronym = n == 1 and representative.isupper() and len(representative) >= 2
            cap_ratio = cap_mid_hits.get(key, 0) / count
            if is_all_caps_acronym or (count >= 3 and cap_ratio >= 0.8):
                noise.add("proper_noun")
            if n == 3:
                middle = key.split(" ")[1]
                if middle in function_words and middle not in _STOPWORD_MIDDLE_EXEMPT:
                    noise.add("stopword_middle")
            if any(part.endswith("-") for part in representative.split(" ")):
                noise.add("fragment_suspect")

            raw_candidates.append(
                _RawCandidate(
                    key=key,
                    n=n,
                    surface=representative,
                    match_key=match_key,
                    count=count,
                    noise_flags=noise,
                )
            )

    merged: dict[tuple[int, tuple[str, ...]], _RawCandidate] = {}
    for cand in raw_candidates:
        tokens_lower = cand.key.split(" ")
        merge_key = (cand.n, (*tokens_lower[:-1], _singularize_last_token(tokens_lower[-1])))
        existing = merged.get(merge_key)
        if existing is None:
            merged[merge_key] = cand
            continue
        winner, loser = (existing, cand) if existing.count >= cand.count else (cand, existing)
        merged[merge_key] = _RawCandidate(
            key=winner.key,
            n=winner.n,
            surface=winner.surface,
            match_key=winner.match_key,
            count=existing.count + cand.count,
            noise_flags=winner.noise_flags | loser.noise_flags | {"plural_merged"},
        )

    results: list[TermCandidate] = []
    for cand in merged.values():
        ngram_weight = 1 + 0.5 * (cand.n - 1)
        specificity = _specificity(cand.key)
        noise_penalty = _NOISE_RANK_PENALTY if cand.noise_flags else 1.0
        rank_score = math.log(1 + cand.count) * ngram_weight * specificity * noise_penalty
        results.append(
            TermCandidate(
                term_en=cand.surface,
                match_key=cand.match_key,
                ngram_size=cand.n,
                noise_flags=",".join(sorted(cand.noise_flags)),
                occurrence_count=cand.count,
                rank_score=rank_score,
            )
        )

    results.sort(key=lambda c: (-c.rank_score, c.match_key))

    cap = settings.max_suggested_terms_per_job
    if len(results) > cap:
        logger.warning(
            "Term extraction vuot van chong tran DB: %d ung vien, gioi han %d -> "
            "cat theo rank_score, bo %d ung vien.",
            len(results),
            cap,
            len(results) - cap,
        )
        results = results[:cap]

    return results
