"""Golden tests cho `src/core/copyright_detector.py` (Architecture.md 6.28.9).

Protocol 5 muc 3: KHONG mock/fixture viet tay theo Architecture.md — chay
`scan_units()` THAT tren tai lieu THAT trong `data/uploads/` va assert DUNG
bang §6.28.2 (do that 2026-09-17). Skip co ly do neu file khong co tren may
CI, nhung PHAI chay xanh o may Dev truoc khi dong task.
"""

from __future__ import annotations

import glob
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.core.copyright_detector import EPUB_HEAD, EPUB_TAIL, PDF_HEAD, PDF_TAIL, scan_units
from src.services.epub_document import EpubDocument

_UPLOADS = Path("data/uploads")


def _first_match(pattern: str) -> Path | None:
    matches = sorted(glob.glob(str(_UPLOADS / pattern)))
    return Path(matches[0]) if matches else None


def _pdf_scan_result(path: Path):
    with fitz.open(path) as doc:
        texts = [page.get_text() for page in doc]
    refs = [str(i + 1) for i in range(len(texts))]
    return scan_units(refs, texts, head=PDF_HEAD, tail=PDF_TAIL)


def _epub_scan_result(path: Path):
    doc = EpubDocument.load(path)
    doc_texts = doc.doc_plain_texts()
    refs = list(doc.spine_hrefs)
    texts = [doc_texts.get(href, "") for href in refs]
    return scan_units(refs, texts, head=EPUB_HEAD, tail=EPUB_TAIL)


#: Bang golden PDF (Architecture.md §6.28.2 "Ket qua do day du") —
#: (glob pattern, expected `removed` tuple).
_PDF_GOLDEN: list[tuple[str, tuple[str, ...]]] = [
    ("*Figoni*libgen.li.pdf", ("6",)),
    ("*Le-Cordon-Bleu*.pdf", ("6",)),
    ("*Bo_Friberg*.pdf", ("6",)),
    ("*Ken Forkish*.pdf", ("4",)),
    ("*Buehler*.pdf", ("3",)),
    ("*Sourdough Discard Recipes*.pdf", ("3",)),
    ("*Faster Artisan Breads II*.pdf", ("5",)),
    ("*Cauvain*.pdf", ("2",)),
    # Ca AM bat buoc 1: an trang © moi trang -> KHONG duoc xoa gi.
    ("*Better_For_You_Packaged_Food*.pdf", ()),
    # Ca AM bat buoc 2: score 8 NHUNG 884 tu (> MAX_WORDS=600) -> KHONG xoa.
    ("*Baking Heaven*.pdf", ()),
    # PDF quet, text nhieu -> am tinh that (khong co gi de cham).
    ("*Sourdough Panettone*.pdf", ()),
]

_EPUB_GOLDEN: list[tuple[str, tuple[str, ...]]] = [
    ("9d436d7b*.epub", ("ops/xhtml/copyright.html",)),
    ("*Sourdough Culture*.epub", ("OEBPS/xhtml/04_Copyright01.xhtml",)),
    ("*Sourdough Discard Recipes*.epub", ("index_split_001.html",)),
    # Trang ban quyen o CUOI spine (index 40/41, 79/80) — kiem tra cua so tail.
    ("*Sourdough by Science*.epub", ("OEBPS/xhtml/Copyright.xhtml",)),
    ("9343f01a*.epub", ("OEBPS/cop.xhtml",)),
    ("sample2_Bread-A-Global-History.epub", ("OEBPS/04_copy.xhtml",)),
]


@pytest.mark.parametrize("pattern,expected_removed", _PDF_GOLDEN)
def test_pdf_golden_scan_matches_architecture_table(
    pattern: str, expected_removed: tuple[str, ...]
) -> None:
    path = _first_match(pattern)
    if path is None:
        pytest.skip(f"file that '{pattern}' khong co trong data/uploads/ tren may nay")
    result = _pdf_scan_result(path)
    assert result.removed == expected_removed, (
        f"{path.name}: removed={result.removed}, verdicts>=3diem="
        f"{[(v.ref, v.score, v.word_count) for v in result.verdicts if v.score >= 3]}"
    )


@pytest.mark.parametrize("pattern,expected_removed", _EPUB_GOLDEN)
def test_epub_golden_scan_matches_architecture_table(
    pattern: str, expected_removed: tuple[str, ...]
) -> None:
    path = _first_match(pattern)
    if path is None:
        pytest.skip(f"file that '{pattern}' khong co trong data/uploads/ tren may nay")
    result = _epub_scan_result(path)
    assert result.removed == expected_removed, (
        f"{path.name}: removed={result.removed}, verdicts>=3diem="
        f"{[(v.ref, v.score, v.word_count) for v in result.verdicts if v.score >= 3]}"
    )


def test_sample2_photo_acknowledgements_scores_below_threshold() -> None:
    """Ca am o bien: score 4 (< MIN_SCORE=5) — bien bang 0 o chieu am, day
    la ly do S8-A1 duoc ghi ⚠️ ASSUMED trong backlog[] (R5-06)."""
    path = _first_match("sample2_Bread-A-Global-History.epub")
    if path is None:
        pytest.skip("file that khong co trong data/uploads/ tren may nay")
    result = _epub_scan_result(path)
    verdict = next(v for v in result.verdicts if v.ref == "OEBPS/17_Photo_Acknowledgements.xhtml")
    assert verdict.score == 4
    assert verdict.word_count == 140
    assert verdict.is_copyright is False


def test_scan_units_aborts_when_more_than_max_removed_candidates() -> None:
    """R8-02 deny-by-default: > MAX_REMOVED ung vien -> huy TOAN BO, khong
    lay top-N diem cao nhat."""
    copyright_text = "All rights reserved. No part of this. ISBN 111-222. Copyright © 2020."
    refs = [str(i + 1) for i in range(4)]
    texts = [copyright_text] * 4
    result = scan_units(refs, texts, head=10, tail=5, max_removed=3)
    assert result.removed == ()
    assert result.aborted_reason == "too_many_candidates"
    assert len(result.verdicts) == 4


def test_scan_units_window_covers_head_and_tail_only() -> None:
    refs = [str(i + 1) for i in range(30)]
    copyright_text = "All rights reserved. No part of this. ISBN 111-222. Copyright © 2020."
    texts = ["ordinary content page here, nothing special at all"] * 30
    texts[14] = copyright_text  # giua sach, NGOAI ca 2 cua so (head=10, tail=5 -> index 25-29)
    result = scan_units(refs, texts, head=10, tail=5)
    assert result.removed == ()  # bo sot vi ngoai cua so — gioi han da biet (§6.28.7 muc 3)
    assert not any(v.ref == "15" for v in result.verdicts)
