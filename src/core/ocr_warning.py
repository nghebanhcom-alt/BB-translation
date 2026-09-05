"""Single source of truth for the OCR-quality warning message (US-11 /
AC-11.2, Architecture.md 6.10.6). Used by both the WebSocket `ocr_warning`
event (src/core/job_orchestrator.py) and the `GET /api/jobs/{id}` response
field (src/api/routes/jobs.py) so the two never drift apart.
"""


def build_ocr_warning(
    confidence: float | None,
    dropped_spans: int | None,
    threshold: float,
) -> str | None:
    """3 branches (Architecture.md 6.10.6):

    - `confidence is None` (no span went through OCR at all) -> no warning.
    - `confidence >= threshold` -> no warning.
    - `confidence < threshold` -> a warning message, non-blocking (the job
      keeps running; v1.0 has no pause/resume-by-user, PRD known limitation).
    """
    if confidence is None or confidence >= threshold:
        return None

    dropped = dropped_spans or 0
    return (
        f"Chat luong OCR thap ({confidence * 100:.0f}%). MinerU da bo qua {dropped} "
        "vung chu khong doc duoc. Ket qua dich co the khong chinh xac."
    )
