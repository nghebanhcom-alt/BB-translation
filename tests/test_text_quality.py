"""`src/core/text_quality.py` (Architecture.md 6.20.13.5, guard Bug #EPUB-4
— mat dau tieng Viet). Module MOI, do doc lap voi
`_check_epub_output_guard()` (job_orchestrator.py) — guard lop loi khac."""

import unicodedata

from src.core.text_quality import (
    EPUB_DIACRITIC_MIN_LETTERS_REQUEST,
    EPUB_DIACRITIC_MIN_LETTERS_UNIT,
    EPUB_DIACRITIC_RATIO_REQUEST,
    EPUB_DIACRITIC_RATIO_UNIT,
    diacritic_ratio,
    strip_html_for_measure,
)


def test_strip_html_for_measure_removes_tags_and_attributes() -> None:
    html = '<a href="https://example.com/vi-du" class="foo">bột mì</a>'

    result = strip_html_for_measure(html)

    assert "href" not in result
    assert "class" not in result
    assert "bột mì" in result
    assert "<a" not in result
    assert "</a>" not in result


def test_diacritic_ratio_full_diacritics_is_high() -> None:
    ratio, letters = diacritic_ratio("<p>bột mì, muối, nướng ở 350F</p>")

    assert letters > 0
    assert ratio > 0.3


def test_diacritic_ratio_no_diacritics_is_zero() -> None:
    ratio, letters = diacritic_ratio("<p>bot mi, muoi, nuong o 350F</p>")

    assert letters > 0
    assert ratio == 0.0


def test_diacritic_ratio_empty_after_strip_returns_zero_letters() -> None:
    ratio, letters = diacritic_ratio('<img src="x.png" alt="photo"/>')

    assert letters == 0
    assert ratio == 0.0


def test_diacritic_ratio_nfd_input_still_measured_correctly() -> None:
    """Bay ky thuat Architecture.md 6.20.13.5 canh bao ro rang: chuoi to hop
    (NFD — chu cai base ASCII + combining mark) phai duoc NFC-normalize
    truoc khi dem, neu khong moi ky tu co dau se bi dem la KHONG dau (ratio
    sai ve 0), tao false-positive hang loat."""
    nfc_text = "bột mì nướng"
    nfd_text = unicodedata.normalize("NFD", nfc_text)
    assert nfc_text != nfd_text  # xac nhan input THAT SU la dang to hop

    nfc_ratio, nfc_letters = diacritic_ratio(nfc_text)
    nfd_ratio, nfd_letters = diacritic_ratio(nfd_text)

    assert nfd_ratio == nfc_ratio
    assert nfd_letters == nfc_letters


def test_diacritic_ratio_english_heavy_unit_stays_above_thresholds() -> None:
    """Chong false-positive: cac unit hop le giau thuat ngu Anh
    ("sourdough starter", "450F") van phai vuot qua nguong — bang chung
    Architecture.md 6.20.13.5's "p5 corpus = 0,122" dat nguong request rat
    thap (0,08)."""
    text = (
        "Cho <strong>sourdough starter</strong> vào âu lớn, để nghỉ ở nhiệt độ phòng "
        "trong khoảng 450F rồi mới đem đi nướng trong lò thật nóng."
    )

    ratio, letters = diacritic_ratio(text)

    assert letters >= EPUB_DIACRITIC_MIN_LETTERS_UNIT
    assert ratio >= EPUB_DIACRITIC_RATIO_UNIT
    assert ratio >= EPUB_DIACRITIC_RATIO_REQUEST


def test_diacritic_ratio_below_request_threshold_when_no_dau_and_enough_letters() -> None:
    text = "Tron bot mi voi men no va nuong o nhiet do 350F trong 30 phut, sau do de nguoi. " * 5

    ratio, letters = diacritic_ratio(text)

    assert letters >= EPUB_DIACRITIC_MIN_LETTERS_REQUEST
    assert ratio < EPUB_DIACRITIC_RATIO_REQUEST
