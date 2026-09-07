"""Tests for `src/services/mineru_det_probe.py` (Architecture.md "Final
Decision: Babeldoc Layout Bug Fix Roadmap", Bug #6, V6 Phase 1).

Protocol 5 R5-03 (real dependency): the golden fixture
`tests/fixtures/mineru/det_probe_p67.json` is REAL output the Tech Lead
captured from an actual MinerU detector run against
`tests/fixtures/babeldoc/rotated_text_p67_source.pdf` (Protocol 5 mục 3 —
copied into the repo, not hand-typed). `test_run_det_probe_real_subprocess`
below additionally re-runs the REAL subprocess against the same fixture PDF
(skipped, not failed, if this machine has no MinerU venv installed).

Protocol 6 R6-02 (assert specific values, not `assert_called()`):
- `test_angle_sign_matches_pymupdf_dir` locks the angle SIGN convention
  against ground truth read directly from the source PDF via PyMuPDF
  (Architecture.md V6 step 3's explicit warning: this is easy to get backwards
  and must be pinned by a real assertion, not left to "should be fine").
- `test_match_lines_to_middle_json_...` asserts the MEDIAN angle value, not
  just that matching "ran".
- `test_probe_persists_findings_for_pdf_scan_job` asserts an actual row lands
  in `layout_qa_findings` via a REAL (in-memory sqlite) `AsyncSession`, not a
  mock session.
"""

import json
import math
import statistics
from collections.abc import AsyncIterator
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.layout_qa import LayoutQaFinding
from src.services.layout_qa import ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK, persist_findings
from src.services.mineru_det_probe import (
    DET_PROBE_MIN_ANGLE_DEG,
    DET_PROBE_MIN_SCORE,
    DetProbeLine,
    build_findings,
    default_mineru_python_path,
    is_mineru_interpreter_available,
    match_lines_to_middle_json,
    parse_det_probe_output,
    probe_and_flag_rotated_text,
    run_det_probe,
)

FIXTURES_BABELDOC = Path(__file__).parent / "fixtures" / "babeldoc"
FIXTURES_MINERU = Path(__file__).parent / "fixtures" / "mineru"
P67_SOURCE = FIXTURES_BABELDOC / "rotated_text_p67_source.pdf"
GOLDEN_DET_PROBE = FIXTURES_MINERU / "det_probe_p67.json"

#: Architecture.md V1/V6: 18 lines survive the score>=0.8/|angle|>=3.0 filter
#: on the golden fixture, median angle ~ -11.0 deg (tolerance per V6 step 8).
_EXPECTED_ROTATED_LINE_COUNT = 18
_EXPECTED_MEDIAN_ANGLE_DEG = -11.0
_MEDIAN_ANGLE_TOLERANCE_DEG = 1.5


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


def _load_golden_fixture() -> dict:
    return json.loads(GOLDEN_DET_PROBE.read_text(encoding="utf-8"))


def _real_pymupdf_dir_angle_deg() -> float:
    """Ground truth read DIRECTLY from the source PDF (not the golden
    fixture) — used to lock the angle sign convention (Architecture.md V6
    step 3) against an INDEPENDENT source, same discipline
    `test_layout_qa.py`/`test_rotated_text_overlay.py` already use."""
    with fitz.open(P67_SOURCE) as doc:
        page = doc[0]
        text_dict = page.get_text("dict")
        angles: list[float] = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                dx, dy = line["dir"]
                angle = math.degrees(math.atan2(dy, dx))
                if abs(angle) >= DET_PROBE_MIN_ANGLE_DEG:
                    angles.append(angle)
    assert angles, "fixture p67 phai co it nhat 1 dong xoay theo PyMuPDF dir"
    return statistics.median(angles)


# --- parse_det_probe_output — golden fixture, real detector output --------


def test_parse_det_probe_output_filters_score_and_angle():
    raw = _load_golden_fixture()

    lines = parse_det_probe_output(raw, page_number=67)

    assert len(lines) == _EXPECTED_ROTATED_LINE_COUNT
    for line in lines:
        assert line.page_number == 67
        assert line.score >= DET_PROBE_MIN_SCORE
        assert abs(line.angle_deg) >= DET_PROBE_MIN_ANGLE_DEG


def test_parse_det_probe_output_median_angle_matches_expected():
    raw = _load_golden_fixture()

    lines = parse_det_probe_output(raw, page_number=67)
    median_angle = statistics.median(line.angle_deg for line in lines)

    assert median_angle == pytest.approx(
        _EXPECTED_MEDIAN_ANGLE_DEG, abs=_MEDIAN_ANGLE_TOLERANCE_DEG
    )


def test_angle_sign_matches_pymupdf_dir():
    """Architecture.md V6 step 3 — explicit warning this is error-prone: the
    detector's image-frame angle (y axis down) and PyMuPDF's `dir` (PDF-space,
    y axis... whichever way babeldoc/PyMuPDF define it) happened to agree in
    SIGN on this fixture. This test is the one thing standing between that
    observation and a silently-flipped `angle_deg` shipped to every finding.
    """
    raw = _load_golden_fixture()
    lines = parse_det_probe_output(raw, page_number=67)
    detector_median = statistics.median(line.angle_deg for line in lines)

    pymupdf_median = _real_pymupdf_dir_angle_deg()

    assert pymupdf_median == pytest.approx(-11.0, abs=0.5)
    # Same sign, same order of magnitude — NOT flipped.
    assert detector_median * pymupdf_median > 0
    assert detector_median == pytest.approx(pymupdf_median, abs=_MEDIAN_ANGLE_TOLERANCE_DEG)


# --- match_lines_to_middle_json — grouping + median (V6 step 4) -----------


def _middle_json_from_golden_lines(lines: list[DetProbeLine], page_idx: int = 66) -> dict:
    """Builds a synthetic (but realistic-shaped, Protocol 5 mục 3 -- derived
    FROM the golden fixture's own detected polys, not invented independently
    of it) `middle.json` with every matched line's text as ONE span inside a
    SINGLE `preproc_blocks` entry -- mirrors how the real MinerU OCR run
    would group one rotated paragraph into one block (Architecture.md V1:
    "16 dòng nghiêng -11° ở trang 67" is one title/text block)."""
    px_to_pt = 72.0 / 200.0
    spans = []
    all_x: list[float] = []
    all_y: list[float] = []
    for line in lines:
        xs = [p[0] * px_to_pt for p in line.poly_px]
        ys = [p[1] * px_to_pt for p in line.poly_px]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        all_x.extend(xs)
        all_y.extend(ys)
        spans.append(
            {"spans": [{"type": "text", "content": line.text, "bbox": bbox, "score": line.score}]}
        )
    block_bbox = [min(all_x), min(all_y), max(all_x), max(all_y)]
    return {
        "pdf_info": [
            {
                "page_idx": page_idx,
                "page_size": [648.0, 783.0],
                "preproc_blocks": [{"bbox": block_bbox, "type": "text", "lines": spans}],
                "discarded_blocks": [],
            }
        ]
    }


def _golden_rotated_lines() -> list[DetProbeLine]:
    raw = _load_golden_fixture()
    return parse_det_probe_output(raw, page_number=67)


def test_match_lines_to_middle_json_groups_into_one_block_with_median_angle():
    lines = _golden_rotated_lines()
    middle_json = _middle_json_from_golden_lines(lines, page_idx=66)  # 0-indexed -> page 67

    blocks = match_lines_to_middle_json(lines, middle_json)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.page_number == 67
    assert block.angle_deg == pytest.approx(
        _EXPECTED_MEDIAN_ANGLE_DEG, abs=_MEDIAN_ANGLE_TOLERANCE_DEG
    )
    assert len(block.matched_texts) == _EXPECTED_ROTATED_LINE_COUNT


def test_match_lines_to_middle_json_ignores_unrelated_text():
    """Fuzzy match must not glue a rotated line onto a middle.json span with
    completely unrelated content, even if it's on the same page."""
    lines = _golden_rotated_lines()[:1]
    middle_json = {
        "pdf_info": [
            {
                "page_idx": 66,
                "page_size": [648.0, 783.0],
                "preproc_blocks": [
                    {
                        "bbox": [0, 0, 100, 100],
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "type": "text",
                                        "content": "Completely unrelated caption text",
                                        "bbox": [0, 0, 100, 20],
                                        "score": 0.99,
                                    }
                                ]
                            }
                        ],
                    }
                ],
                "discarded_blocks": [],
            }
        ]
    }

    blocks = match_lines_to_middle_json(lines, middle_json)

    assert blocks == []


# --- build_findings / persist_findings (Bug #6 V6 step 5) -----------------


def test_build_findings_shape():
    lines = _golden_rotated_lines()
    middle_json = _middle_json_from_golden_lines(lines, page_idx=66)
    blocks = match_lines_to_middle_json(lines, middle_json)

    findings = build_findings(blocks)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_type == ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK
    assert finding.severity == "blocker"
    assert finding.page_number == 67
    assert finding.detail["angle_deg"] == pytest.approx(
        _EXPECTED_MEDIAN_ANGLE_DEG, abs=_MEDIAN_ANGLE_TOLERANCE_DEG
    )
    assert finding.detail["matched_line_count"] == _EXPECTED_ROTATED_LINE_COUNT
    assert len(finding.detail["bbox"]) == 4


@pytest.mark.asyncio
async def test_probe_persists_findings_for_pdf_scan_job(session: AsyncSession):
    """R6-02: assert an ACTUAL row lands in `layout_qa_findings` (queried
    back from a real in-memory AsyncSession/sqlite DB), not `assert_called()`
    on a mock — this is the exact discipline Bug #5 was missed by NOT
    having."""
    lines = _golden_rotated_lines()
    middle_json = _middle_json_from_golden_lines(lines, page_idx=66)
    blocks = match_lines_to_middle_json(lines, middle_json)
    findings = build_findings(blocks)
    assert findings  # sanity: the fixture must actually produce >=1 finding

    await persist_findings(
        session, findings, job_id="job-bug6-p1", source_file="rotated_text_p67_source.pdf"
    )

    result = await session.exec(
        select(LayoutQaFinding).where(
            LayoutQaFinding.job_id == "job-bug6-p1",
            LayoutQaFinding.check_type == ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK,
        )
    )
    rows = result.all()

    assert len(rows) >= 1
    row = rows[0]
    assert row.page_number == 67
    assert row.severity == "blocker"
    detail = json.loads(row.detail)
    assert detail["angle_deg"] == pytest.approx(
        _EXPECTED_MEDIAN_ANGLE_DEG, abs=_MEDIAN_ANGLE_TOLERANCE_DEG
    )


# --- probe_and_flag_rotated_text — full pipeline on synthetic middle.json --


@pytest.mark.asyncio
async def test_probe_and_flag_rotated_text_returns_empty_when_no_lines(tmp_path, mocker):
    mocker.patch(
        "src.services.mineru_det_probe.run_det_probe",
        return_value=[],
    )
    middle_json_path = tmp_path / "middle.json"
    middle_json_path.write_text(json.dumps({"pdf_info": []}), encoding="utf-8")

    findings = await probe_and_flag_rotated_text(P67_SOURCE, middle_json_path)

    assert findings == []


@pytest.mark.asyncio
async def test_probe_and_flag_rotated_text_full_flow(tmp_path, mocker):
    lines = _golden_rotated_lines()
    middle_json = _middle_json_from_golden_lines(lines, page_idx=66)
    middle_json_path = tmp_path / "middle.json"
    middle_json_path.write_text(json.dumps(middle_json), encoding="utf-8")

    mocker.patch("src.services.mineru_det_probe.run_det_probe", return_value=lines)

    findings = await probe_and_flag_rotated_text(P67_SOURCE, middle_json_path)

    assert len(findings) == 1
    assert findings[0].check_type == ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK
    assert findings[0].page_number == 67


# --- Protocol 5 R5-03 — real dependency smoke test -------------------------


@pytest.mark.skipif(
    not is_mineru_interpreter_available(),
    reason=(
        f"MinerU interpreter khong co san tai {default_mineru_python_path()} tren may nay "
        "(cai bang 'uv tool install mineru' de chay smoke test nay)"
    ),
)
@pytest.mark.asyncio
async def test_run_det_probe_real_subprocess():
    """Protocol 5 R5-03 — calls the REAL MinerU detector subprocess (no
    mocked geometry) against the same source PDF the golden fixture was
    captured from, and re-verifies the same median angle Architecture.md V1
    reported. Skipped (not failed) when this machine has no MinerU venv."""
    lines = await run_det_probe(P67_SOURCE)

    assert len(lines) >= 10  # some slack vs. the pinned 18 for model/version drift
    median_angle = statistics.median(line.angle_deg for line in lines)
    assert median_angle == pytest.approx(_EXPECTED_MEDIAN_ANGLE_DEG, abs=2.0)
