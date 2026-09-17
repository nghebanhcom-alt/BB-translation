"""S8 — bo cham diem loai bo trang claim ban quyen (Architecture.md 6.28.2).

Mot bo cham diem DUY NHAT dung chung cho ca PDF va EPUB (cung tinh than
6.14.7): khac biet PDF/EPUB chi nam o *ai cung cap danh sach text* va *cua so
quet* (goi tu src/core/job_orchestrator.py), khong nam o luat cham diem.

Cac hang so duoi day duoc chot tu do that tren 13 PDF + 7 EPUB thuc trong
data/uploads/ (Architecture.md 6.28.2/6.28.9) — KHONG duoc doi tu truc giac,
xem `docs/design-log.md` muc "S8" cho ly do tung con so.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

#: Architecture.md 6.28.2 bang "Luat cham diem".
STRONG_KEYWORDS: tuple[str, ...] = (
    "all rights reserved",
    "no part of this",
    "library of congress",
    "cataloging-in-publication",
    "isbn",
    "tous droits réservés",
    "tous droits reserves",
    "aucune partie de",
    "dépôt légal",
    "depot legal",
    "droits d'auteur",
    "reproduction interdite",
    "achevé d'imprimer",
)

#: "copyright ©" / "© <nam>" / "copyright <nam>" / "© <ten>...<nam>" — bat
#: "All contents copyright © Penny Williams … 2015", loai footer "©" tro troi.
STRONG_PATTERN = re.compile(
    r"copyright\s*©|©\s*\d{4}|copyright\s+\d{4}|©\s*\w+.{0,40}\d{4}",
)

WEAK_KEYWORDS: tuple[str, ...] = (
    "copyright",
    "©",
    "published by",
    "first published",
    "printed in",
    "publisher",
    "publié par",
    "imprimé en",
    "éditions",
    "éditeur",
    "editeur",
)

#: Architecture.md 6.28.2 bang hang so — bien bang 0 o chieu duong (S8-A1),
#: xem backlog[] trong project_state.json.
MIN_SCORE = 5
MAX_WORDS = 600
MIN_WORDS = 5
MAX_REMOVED = 3

#: Cua so quet (Architecture.md 6.28.2 bang "Cua so quet").
PDF_HEAD = 10
PDF_TAIL = 5
EPUB_HEAD = 6
EPUB_TAIL = 3


@dataclass(frozen=True)
class PageVerdict:
    ref: str  # so trang 1-based (PDF) hoac doc_href (EPUB)
    score: int
    word_count: int
    matched: tuple[str, ...]
    is_copyright: bool


@dataclass(frozen=True)
class CopyrightScanResult:
    removed: tuple[str, ...]  # rong = khong xoa gi
    verdicts: tuple[PageVerdict, ...]  # MOI ung vien trong cua so da cham diem
    aborted_reason: str | None  # "too_many_candidates" | None


def _normalize(text: str) -> str:
    """Gop xuong dong — trang ban quyen PDF hay bi PyMuPDF tra ve nhieu
    dong ngan (Architecture.md 6.28.2)."""
    return " ".join(text.lower().split())


def _score(text: str) -> tuple[int, int, tuple[str, ...]]:
    normalized = _normalize(text)
    word_count = len(normalized.split())
    score = 0
    matched: list[str] = []

    for keyword in STRONG_KEYWORDS:
        if keyword in normalized:
            score += 2
            matched.append(keyword)

    if STRONG_PATTERN.search(normalized):
        score += 2
        matched.append("copyright©/©<year>")

    for keyword in WEAK_KEYWORDS:
        if keyword in normalized:
            score += 1
            matched.append(keyword)

    return score, word_count, tuple(matched)


def scan_units(
    refs: Sequence[str],
    texts: Sequence[str],
    *,
    head: int,
    tail: int,
    max_removed: int = MAX_REMOVED,
) -> CopyrightScanResult:
    """Cham diem cac ung vien trong cua so dau (`head`) + cuoi (`tail`) cua
    `refs`/`texts` (cung do dai, cung thu tu — PDF: so trang 1-based tang
    dan; EPUB: `doc.spine_hrefs`). Tra ve MOI ung vien da cham (de audit),
    va danh sach `removed` (chi cac ung vien dat ca 3 dieu kien —
    Architecture.md 6.28.2 "Ket luan is_copyright").

    `max_removed`: vuot nguong nay -> HUY toan bo viec xoa cho tai lieu nay
    (`aborted_reason="too_many_candidates"`), KHONG lay top-N diem cao nhat
    (R8-02 deny-by-default — xoa nham noi dung that khong the hoan tac).
    """
    if len(refs) != len(texts):
        raise ValueError(f"refs ({len(refs)}) va texts ({len(texts)}) phai cung do dai")

    n = len(refs)
    candidate_indices = sorted(set(range(min(head, n))) | set(range(max(0, n - tail), n)))

    verdicts: list[PageVerdict] = []
    removed: list[str] = []
    for idx in candidate_indices:
        score, word_count, matched = _score(texts[idx])
        is_copyright = score >= MIN_SCORE and MIN_WORDS <= word_count <= MAX_WORDS
        verdicts.append(
            PageVerdict(
                ref=refs[idx],
                score=score,
                word_count=word_count,
                matched=matched,
                is_copyright=is_copyright,
            )
        )
        if is_copyright:
            removed.append(refs[idx])

    if len(removed) > max_removed:
        return CopyrightScanResult(
            removed=(), verdicts=tuple(verdicts), aborted_reason="too_many_candidates"
        )

    return CopyrightScanResult(
        removed=tuple(removed), verdicts=tuple(verdicts), aborted_reason=None
    )
