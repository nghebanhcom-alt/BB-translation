"""Auto-detect ngôn ngữ nguồn EN/FR — Architecture.md §6.26.3 (S7).

Thuần Python, không thêm dependency ngoài (không `langdetect`/`lingua`/
`fasttext` — mỗi dependency mới là 1 contract phải verify theo Protocol 5, mà
bài toán chỉ là phân biệt 2 lớp trên văn bản cỡ vài nghìn token, xem
docs/design-log.md "S7 — Dịch FR→VI" mục 2).

Phương pháp: tỷ lệ hư từ (function word) phân biệt được — đếm token khớp
`en_function_words.txt` (đã dùng cho `term_extractor.py`) và
`fr_function_words.txt` (mới, xem file đó để biết các từ mơ hồ bị loại
tường minh).
"""

import re
from dataclasses import dataclass
from pathlib import Path

_WORDLIST_DIR = Path(__file__).parent / "wordlists"

#: Architecture.md §6.26.3 — 3 điều kiện kết luận, xem bảng ngưỡng ở đó.
_MIN_TOKEN_COUNT = 500
_MIN_WINNER_SHARE = 0.05
_MIN_WINNER_LOSER_RATIO = 3.0

#: Bao gồm ký tự có dấu tiếng Pháp (à â ä é è ê ë ï î ô ö ù û ü ç œ æ) — text
#: đã được lowercase trước khi áp regex này, xem `detect_source_lang()`.
_TOKEN_RE = re.compile(r"[a-zàâäéèêëïîôöùûüçœæ]+")


def _load_wordlist(filename: str) -> frozenset[str]:
    path = _WORDLIST_DIR / filename
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lower()
        if not stripped or stripped.startswith("#"):
            continue
        words.add(stripped)
    return frozenset(words)


_EN_FUNCTION_WORDS = _load_wordlist("en_function_words.txt")
_FR_FUNCTION_WORDS = _load_wordlist("fr_function_words.txt")


@dataclass(frozen=True)
class LanguageDetection:
    lang: str | None  # "en" | "fr" | None (không kết luận được)
    en_share: float
    fr_share: float
    token_count: int


def detect_source_lang(text: str) -> LanguageDetection:
    """Trả về `LanguageDetection`. `lang is None` khi bất kỳ 1 trong 3 điều
    kiện (Architecture.md §6.26.3 bảng ngưỡng) không thoả — caller PHẢI coi
    `None` như "chưa detect được", ghi `source_lang = "en"` (fallback an
    toàn, KHÔNG đoán bừa) chứ hàm này không tự fallback.
    """
    tokens = _TOKEN_RE.findall(text.lower())
    token_count = len(tokens)
    if token_count == 0:
        return LanguageDetection(lang=None, en_share=0.0, fr_share=0.0, token_count=0)

    en_count = sum(1 for t in tokens if t in _EN_FUNCTION_WORDS)
    fr_count = sum(1 for t in tokens if t in _FR_FUNCTION_WORDS)
    en_share = en_count / token_count
    fr_share = fr_count / token_count

    if token_count < _MIN_TOKEN_COUNT:
        return LanguageDetection(
            lang=None, en_share=en_share, fr_share=fr_share, token_count=token_count
        )

    winner_share = max(en_share, fr_share)
    if winner_share < _MIN_WINNER_SHARE:
        return LanguageDetection(
            lang=None, en_share=en_share, fr_share=fr_share, token_count=token_count
        )

    loser_share = min(en_share, fr_share)
    ratio = winner_share / loser_share if loser_share > 0 else float("inf")
    if ratio < _MIN_WINNER_LOSER_RATIO:
        return LanguageDetection(
            lang=None, en_share=en_share, fr_share=fr_share, token_count=token_count
        )

    lang = "en" if en_share >= fr_share else "fr"
    return LanguageDetection(
        lang=lang, en_share=en_share, fr_share=fr_share, token_count=token_count
    )
