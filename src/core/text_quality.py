"""Do chat luong output dich EPUB (Architecture.md 6.20.13.5, guard Bug
#EPUB-4 — mat dau tieng Viet). MODULE MOI, khong nhet vao `prompt_builder.py`:
day la do chat luong OUTPUT, khong phai dung PROMPT.

Day la LOP PHONG THU DOC LAP voi `_check_epub_output_guard()`
(`job_orchestrator.py`) — guard do bat lop loi khac (Bug #5 dang EPUB: noi
dung chua dich/rong) va van dang PASS dung thiet ke cua no.
"""

import re
import unicodedata

#: Toan bo nguyen am/phu am co dau tieng Viet (khong bao gom nguyen am
#: thuong/hoa khong dau — chinh ta co dau la dieu dang do).
_VN_DIACRITIC_CHARS = frozenset(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
)

_TAG_RE = re.compile(r"<[^>]+>")

#: Tang 1 (muc REQUEST) — Architecture.md 6.20.13.5. ⚠️ ASSUMED, chua do
#: tren corpus tieng Viet that cua nganh banh (corpus dung de chot la
#: docs/PRD.md + docs/Architecture.md cua chinh du an, p5 = 0,122).
EPUB_DIACRITIC_MIN_LETTERS_REQUEST = 200
EPUB_DIACRITIC_RATIO_REQUEST = 0.08

#: Tang 2 (muc UNIT) — bat phan sot lai sau tang 1. ⚠️ ASSUMED, khop tieu
#: chi QA da kiem bang mat ("0 ky tu co dau", nang san tu 3 len 40 chu cai
#: de loai false-positive dang "2 tsp"/"350F"/ten rieng).
EPUB_DIACRITIC_MIN_LETTERS_UNIT = 40
EPUB_DIACRITIC_RATIO_UNIT = 0.02


def strip_html_for_measure(html: str) -> str:
    """Bo THE va MOI thuoc tinh (href/class/alt tieng Anh khong duoc tinh
    vao mau do — do la nguon false-positive lon nhat)."""
    return _TAG_RE.sub(" ", html)


def diacritic_ratio(html: str) -> tuple[float, int]:
    """Tra (ty le ky tu co dau / tong ky tu chu cai, so ky tu chu cai) tren
    text da strip tag, da NFC-normalize va lower().

    `unicodedata.normalize("NFC", ...)` la buoc BAT BUOC truoc khi dem —
    tieng Viet to hop (NFD) se cho ra chu cai base ASCII + combining mark,
    dem ra ty le 0 va tao false-positive hang loat (Architecture.md
    6.20.13.5's "bay co that cua chinh lop loi dang do").
    """
    text = unicodedata.normalize("NFC", strip_html_for_measure(html)).lower()
    letters = [ch for ch in text if ch.isalpha()]
    total_letters = len(letters)
    if total_letters == 0:
        return 0.0, 0
    diacritic_count = sum(1 for ch in letters if ch in _VN_DIACRITIC_CHARS)
    return diacritic_count / total_letters, total_letters
