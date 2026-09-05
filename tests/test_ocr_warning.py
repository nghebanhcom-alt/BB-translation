from src.core.ocr_warning import build_ocr_warning


def test_no_warning_when_confidence_none() -> None:
    assert build_ocr_warning(None, None, 0.80) is None


def test_no_warning_when_confidence_at_or_above_threshold() -> None:
    assert build_ocr_warning(0.80, 0, 0.80) is None
    assert build_ocr_warning(0.95, 0, 0.80) is None


def test_warning_when_confidence_below_threshold() -> None:
    warning = build_ocr_warning(0.72, 18, 0.80)
    assert warning is not None
    assert "72" in warning
    assert "18" in warning


def test_warning_handles_missing_dropped_span_count() -> None:
    warning = build_ocr_warning(0.5, None, 0.80)
    assert warning is not None
    assert "0" in warning
