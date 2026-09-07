"""MinerU rotated-text DETECTOR probe for `pdf_scan` jobs (Architecture.md
"Final Decision: Babeldoc Layout Bug Fix Roadmap", Bug #6, V6 -- PHASE 1
ONLY: flag rotated text on scan pages, do NOT reconstruct the angle in the
translated output).

Root cause this exists for (Architecture.md V1/V4, verified against the
installed MinerU 3.4.5 source, NOT guessed): the MinerU HTTP service
(`src/services/mineru_runner.py`, `mineru_endpoint`) only ever returns
AXIS-ALIGNED bboxes in `middle.json` -- the angle a line was actually
detected at is computed internally and then discarded before the HTTP
response is built (`ocr_utils.py:399-410`, "flattening"). So a scan page with
a rotated caption/pull-quote/label produces a `middle.json` bbox that looks
perfectly ordinary, and `build_searchable_pdf()` (`src/preprocess/
searchable_pdf.py`) writes the recognized text back at 0 degrees -- readable
text, in the wrong orientation relative to the page, with NOTHING in the
pipeline able to tell this happened. This module calls MinerU's underlying
DETECTOR class directly (`PytorchPaddleOCR`, same package, different entry
point than the HTTP service) in a SEPARATE subprocess using MinerU's own venv
interpreter (`Settings.mineru_python_path`) -- that class's raw output DOES
still carry the poly's rotation (Architecture.md V-1/V-3, spike-verified,
golden fixture `tests/fixtures/mineru/det_probe_p67.json`), because the
flattening step lives in a layer above it, in the HTTP-service code path this
module does not go through.

Data lineage (Protocol 6 R6-01, must hold exactly): this module reads
`file_path` -- the SAME raw scan image pages `JobOrchestrator._build_ocr_bridge()`
already fed to `MinerURunner.parse_document()` for THIS job -- and
`middle_json_path`, THIS job's own OCR result (not a fixture, not another
job's). It does not read the searchable-PDF bridge `build_searchable_pdf()`
produces: that bridge already has the original scan pixels whited out under
every recognized span (Architecture.md V3), so running a detector against it
would find nothing to detect.

Angle sign convention (Architecture.md V6 step 3, flagged explicitly as
error-prone -- do NOT re-derive from first principles without the fixture
test backing it): the subprocess script below computes
`angle = atan2(y1 - y0, x1 - x0)` on the poly's TOP edge (points 0 and 1, in
image space, y axis pointing DOWN because that is how OpenCV/the detector
produce coordinates). On the Tech Lead's spike fixture
(`rotated_text_p67_source.pdf`), this produced angles matching (SAME sign,
not flipped) the `dir` PyMuPDF reads back from the real PDF's rotated text
objects. This is convenient but NOT something to assume holds in general --
`tests/test_mineru_det_probe.py::test_angle_sign_matches_pymupdf_dir` locks
this down against both artifacts (the golden fixture AND the source PDF)
rather than letting a silent sign flip corrupt every finding's `angle_deg`.

Grouping ("Ghép với middle.json", V6 step 4) -- Giả định tự chọn (no formal
spec covers exactly how to turn N matched detector LINES into 1 finding
BLOCK): this module groups matched lines by the middle.json BLOCK
(`preproc_blocks[i]`, i.e. MinerU's own paragraph/title grouping) they
matched into, rather than inventing a new distance-based clustering
heuristic (as `rotated_text_overlay.py`'s `group_rotated_lines()` does for a
different problem -- grouping PyMuPDF `line["dir"]` results with no
pre-existing block structure to lean on). Reusing MinerU's own block
boundaries is cheaper and, for the "16 dòng nghiêng -11° ở trang 67" case
Architecture.md V1 spiked, correct: MinerU already put all 16 lines in one
`title`/`text` block.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import statistics
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from src.services.layout_qa import ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK, LayoutQaFindingData

logger = logging.getLogger(__name__)

#: Architecture.md V6 step 1 -- spike-verified render resolution; the golden
#: fixture (`tests/fixtures/mineru/det_probe_p67.json`) was captured at this
#: same DPI, so changing this constant would invalidate that fixture's
#: pixel-space polys.
DET_PROBE_DPI = 200

#: V6 step 2 -- score/angle thresholds applied to the raw detector output.
DET_PROBE_MIN_SCORE = 0.8
DET_PROBE_MIN_ANGLE_DEG = 3.0

#: V6 step 3 -- poly coordinates come out of the detector in pixels at
#: `DET_PROBE_DPI`; PDF/`middle.json` coordinates are in points (72/inch).
PX_TO_PT_SCALE = 72.0 / DET_PROBE_DPI

#: V6 step 4 -- fuzzy text-match acceptance threshold (`SequenceMatcher.ratio()`)
#: between a detector line's recognized text and a middle.json span's content.
#: Not 1.0: the detector's own `rec` pass and MinerU's OCR pass are two
#: independent recognition runs over the SAME pixels and can disagree on
#: individual characters (accents, punctuation) while clearly being the same
#: line -- exact-match would silently drop real matches.
TEXT_MATCH_MIN_RATIO = 0.6


class MineruDetProbeError(RuntimeError):
    """The detector subprocess ran but its output could not be used."""


class MineruDetProbeUnavailableError(MineruDetProbeError):
    """`Settings.mineru_python_path` does not exist on this machine.

    Callers (`JobOrchestrator`) MUST treat this as best-effort (Architecture.md
    V6 step 6): log it and continue without rotated-text flagging, never fail
    the job over it -- this is a supplementary QA signal, not a pipeline
    dependency the way `MinerURunner` itself is (BR-OCR-01).
    """


@dataclass(frozen=True)
class DetProbeLine:
    """1 dòng chữ (score/góc đã qua ngưỡng lọc V6 step 2) từ detector MinerU."""

    page_number: int  # 1-indexed, matches src/services/layout_qa.py convention
    poly_px: tuple[tuple[float, float], ...]  # pixel space @ DET_PROBE_DPI
    text: str
    score: float
    angle_deg: float  # image-frame (y-down) -- see module docstring


@dataclass(frozen=True)
class RotatedScanBlock:
    """1 khối chữ xoay đã ghép với middle.json (nhiều dòng gộp theo cùng 1
    block middle.json, V6 step 4) -- input trực tiếp cho `build_findings()`."""

    page_number: int
    bbox: tuple[float, float, float, float]  # points, from the middle.json block
    angle_deg: float  # median of the matched lines' angle_deg
    matched_texts: tuple[str, ...]


# Subprocess script run with MinerU's OWN interpreter (Settings.mineru_python_path)
# -- calls the exact class/method Architecture.md V6 step 1 specifies:
# `PytorchPaddleOCR(lang="en").ocr(img, det=True, rec=True)`. Output shape
# matches `tests/fixtures/mineru/det_probe_p67.json` exactly (`{"timings":
# {...}, "items": [{"angle", "text", "score", "poly"}, ...]}`) so the same
# parser (`parse_det_probe_output()` below) reads both a real subprocess run
# and the golden fixture.
_DET_PROBE_SCRIPT = """
import json
import math
import sys
import time


def main() -> None:
    image_path = sys.argv[1]

    t0 = time.time()
    import cv2
    from mineru.model.ocr.pytorch_paddle import PytorchPaddleOCR

    ocr = PytorchPaddleOCR(lang="en")
    init_s = time.time() - t0

    img = cv2.imread(image_path)
    if img is None:
        print(json.dumps({"timings": {"init": init_s}, "items": []}))
        return

    t1 = time.time()
    result = ocr.ocr(img, det=True, rec=True)
    det_rec_s = time.time() - t1

    items = []
    page_result = result[0] if result else None
    if page_result:
        for poly, rec in page_result:
            text, score = rec
            poly_pts = [[float(x), float(y)] for x, y in poly]
            (x0, y0), (x1, y1) = poly_pts[0], poly_pts[1]
            angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
            items.append(
                {
                    "angle": round(angle, 3),
                    "text": text,
                    "score": float(score),
                    "poly": poly_pts,
                }
            )

    print(json.dumps({"timings": {"init": init_s, "det_rec": det_rec_s}, "items": items}))


if __name__ == "__main__":
    main()
"""


def default_mineru_python_path() -> Path:
    return Path("~/.local/share/uv/tools/mineru/bin/python").expanduser()


def is_mineru_interpreter_available(python_path: Path | str | None = None) -> bool:
    """Used both by `run_det_probe()` itself and by the Protocol 5 R5-03 smoke
    test to skip (not fail) when this machine has no MinerU venv installed."""
    resolved = Path(python_path).expanduser() if python_path else default_mineru_python_path()
    return resolved.exists()


def _render_page_png(pdf_path: Path, page_index: int, out_path: Path) -> None:
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        pixmap = page.get_pixmap(dpi=DET_PROBE_DPI)
        pixmap.save(out_path)


async def _run_ocr_subprocess(python_path: Path, image_path: Path) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as script_file:
        script_file.write(_DET_PROBE_SCRIPT)
        script_path = Path(script_file.name)

    try:
        proc = await asyncio.create_subprocess_exec(
            str(python_path),
            str(script_path),
            str(image_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise MineruDetProbeError(
                f"MinerU det probe subprocess that bai (exit {proc.returncode}): "
                f"{stderr.decode('utf-8', errors='replace')[-2000:]}"
            )
        try:
            return json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MineruDetProbeError(
                f"MinerU det probe subprocess tra ve JSON khong hop le: {exc}. "
                f"stderr: {stderr.decode('utf-8', errors='replace')[-500:]}"
            ) from exc
    finally:
        script_path.unlink(missing_ok=True)


def parse_det_probe_output(
    raw: dict[str, Any],
    page_number: int,
    *,
    min_score: float = DET_PROBE_MIN_SCORE,
    min_angle_deg: float = DET_PROBE_MIN_ANGLE_DEG,
) -> list[DetProbeLine]:
    """Parse subprocess (or golden-fixture) JSON, applying V6 step 2's
    filter. Shared by `run_det_probe()` and the golden-fixture test."""
    lines: list[DetProbeLine] = []
    for item in raw.get("items") or []:
        score = float(item.get("score", 0.0))
        angle = float(item.get("angle", 0.0))
        if score < min_score or abs(angle) < min_angle_deg:
            continue
        raw_poly = item.get("poly") or []
        if len(raw_poly) < 2:
            continue
        poly = tuple((float(x), float(y)) for x, y in raw_poly)
        lines.append(
            DetProbeLine(
                page_number=page_number,
                poly_px=poly,
                text=str(item.get("text") or ""),
                score=score,
                angle_deg=angle,
            )
        )
    return lines


async def run_det_probe(
    pdf_path: Path,
    python_path: Path | str | None = None,
    *,
    min_score: float = DET_PROBE_MIN_SCORE,
    min_angle_deg: float = DET_PROBE_MIN_ANGLE_DEG,
) -> list[DetProbeLine]:
    """Runs the REAL MinerU detector (Protocol 5 -- no mock geometry) over
    every page of `pdf_path`, page by page (one subprocess call per page,
    matching how the Tech Lead's spike captured the golden fixture -- a
    single-page image per call keeps each subprocess's memory/model-init
    cost bounded and independent of document length).

    Raises `MineruDetProbeUnavailableError` if the configured interpreter
    isn't installed -- callers MUST treat this as best-effort (see that
    exception's docstring), never as a job-failing error.
    """
    resolved_python = (
        Path(python_path).expanduser() if python_path else default_mineru_python_path()
    )
    if not resolved_python.exists():
        raise MineruDetProbeUnavailableError(
            f"MinerU interpreter khong ton tai tai {resolved_python} — bo qua det probe "
            "(cai dat bang 'uv tool install mineru' neu can bat tinh nang nay)"
        )

    lines: list[DetProbeLine] = []
    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for page_index in range(page_count):
            image_path = tmp_path / f"page_{page_index}.png"
            _render_page_png(pdf_path, page_index, image_path)
            raw = await _run_ocr_subprocess(resolved_python, image_path)
            lines.extend(
                parse_det_probe_output(
                    raw, page_index + 1, min_score=min_score, min_angle_deg=min_angle_deg
                )
            )
    return lines


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _poly_centroid_pt(poly_px: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    xs = [p[0] * PX_TO_PT_SCALE for p in poly_px]
    ys = [p[1] * PX_TO_PT_SCALE for p in poly_px]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _poly_line_height_pt(poly_px: tuple[tuple[float, float], ...]) -> float:
    ys = [p[1] * PX_TO_PT_SCALE for p in poly_px]
    height = max(ys) - min(ys)
    return height if height > 0 else 1.0


@dataclass(frozen=True)
class _MiddleJsonSpan:
    block_index: int
    block_bbox: tuple[float, float, float, float]
    content: str
    bbox: tuple[float, float, float, float]


def _iter_middle_json_spans(page_info: dict[str, Any]) -> list[_MiddleJsonSpan]:
    """Same `preproc_blocks` walk as `src/preprocess/searchable_pdf.py::_collect_text_spans()`
    but ALSO keeps each span's owning top-level block index/bbox -- needed for
    V6 step 4's block-level grouping, which `_collect_text_spans()` doesn't
    track (it only needs flat spans for the whiteout+insert pass)."""
    spans: list[_MiddleJsonSpan] = []

    def _walk(block: dict[str, Any], block_index: int, block_bbox: tuple[float, ...]) -> None:
        for line in block.get("lines", []) or []:
            for span in line.get("spans", []) or []:
                content = span.get("content")
                bbox = span.get("bbox")
                if not isinstance(content, str) or not content.strip():
                    continue
                if not bbox or len(bbox) != 4:
                    continue
                try:
                    span_bbox = tuple(float(v) for v in bbox)
                except (TypeError, ValueError):
                    continue
                spans.append(_MiddleJsonSpan(block_index, block_bbox, content, span_bbox))
        for nested in block.get("blocks", []) or []:
            _walk(nested, block_index, block_bbox)

    for index, block in enumerate(page_info.get("preproc_blocks", []) or []):
        raw_bbox = block.get("bbox")
        if raw_bbox and len(raw_bbox) == 4:
            try:
                block_bbox = tuple(float(v) for v in raw_bbox)
            except (TypeError, ValueError):
                block_bbox = (0.0, 0.0, 0.0, 0.0)
        else:
            block_bbox = (0.0, 0.0, 0.0, 0.0)
        _walk(block, index, block_bbox)

    return spans


def match_lines_to_middle_json(
    lines: list[DetProbeLine], middle_json: dict[str, Any]
) -> list[RotatedScanBlock]:
    """V6 step 4: matches each detector line to the closest-by-text,
    closest-by-position middle.json span, then groups all matched lines that
    landed in the SAME middle.json block into one `RotatedScanBlock` whose
    angle is the MEDIAN of its lines (not mean -- Architecture.md V6 step 4:
    the spike had a noisy outlier poly at -23.43° that a mean would have let
    skew the whole block's reported angle)."""
    lines_by_page: dict[int, list[DetProbeLine]] = {}
    for line in lines:
        lines_by_page.setdefault(line.page_number, []).append(line)

    blocks: list[RotatedScanBlock] = []
    for page_info in middle_json.get("pdf_info") or []:
        page_number = int(page_info.get("page_idx", 0)) + 1  # 0-indexed -> 1-indexed
        page_lines = lines_by_page.get(page_number)
        if not page_lines:
            continue

        spans = _iter_middle_json_spans(page_info)
        if not spans:
            continue

        matched_lines_by_block: dict[int, list[DetProbeLine]] = {}
        block_bbox_by_index: dict[int, tuple[float, float, float, float]] = {}

        for line in page_lines:
            centroid = _poly_centroid_pt(line.poly_px)
            line_height = _poly_line_height_pt(line.poly_px)
            distance_limit = 0.5 * line_height

            best_span: _MiddleJsonSpan | None = None
            best_ratio = 0.0
            for span in spans:
                ratio = _text_similarity(line.text, span.content)
                if ratio < TEXT_MATCH_MIN_RATIO or ratio <= best_ratio:
                    continue
                span_centroid = (
                    (span.bbox[0] + span.bbox[2]) / 2,
                    (span.bbox[1] + span.bbox[3]) / 2,
                )
                distance = math.hypot(
                    centroid[0] - span_centroid[0], centroid[1] - span_centroid[1]
                )
                if distance >= distance_limit:
                    continue
                best_ratio = ratio
                best_span = span

            if best_span is not None:
                matched_lines_by_block.setdefault(best_span.block_index, []).append(line)
                block_bbox_by_index[best_span.block_index] = best_span.block_bbox

        for block_index, matched_lines in matched_lines_by_block.items():
            angle_deg = round(statistics.median(m.angle_deg for m in matched_lines), 3)
            blocks.append(
                RotatedScanBlock(
                    page_number=page_number,
                    bbox=block_bbox_by_index[block_index],
                    angle_deg=angle_deg,
                    matched_texts=tuple(m.text for m in matched_lines),
                )
            )

    return blocks


def build_findings(blocks: list[RotatedScanBlock]) -> list[LayoutQaFindingData]:
    """V6 step 5: wraps each matched block into the SAME `LayoutQaFindingData`
    shape P0/P1's checks already use (`persist_findings()` reused as-is, no
    new table -- Architecture.md V6 explicit instruction). `angle_deg` has no
    dedicated column on `LayoutQaFinding` (the SQLModel table); it goes
    inside `detail` (a free-form JSON string column), the SAME place
    `_check_rotated_text_prescan()` in `src/services/layout_qa.py` already
    stores its own `angle_deg` for a DIFFERENT check_type -- reusing an
    existing, already-JSON column is backward compatible by construction
    (older/other check_types' `detail` shapes are untouched), so no schema
    migration is needed here (Architecture.md V6 step 5's "extend if the
    current schema has nowhere to put it" does not apply: it already does)."""
    findings: list[LayoutQaFindingData] = []
    for block in blocks:
        findings.append(
            LayoutQaFindingData(
                page_number=block.page_number,
                check_type=ROTATED_TEXT_SCAN_UNSUPPORTED_CHECK,
                severity="blocker",
                detail={
                    "bbox": list(block.bbox),
                    "angle_deg": block.angle_deg,
                    "matched_texts": list(block.matched_texts)[:10],
                    "matched_line_count": len(block.matched_texts),
                },
            )
        )
    return findings


async def probe_and_flag_rotated_text(
    file_path: Path,
    middle_json_path: Path,
    python_path: Path | str | None = None,
) -> list[LayoutQaFindingData]:
    """Single entry point `JobOrchestrator` calls (V6 step 6): runs the
    detector over `file_path` (the job's RAW scan pages -- see module
    docstring's data-lineage note), matches against THIS job's own
    `middle_json_path`, and returns findings ready for `persist_findings()`.

    Raises on any failure -- the caller (`JobOrchestrator`) is responsible
    for the best-effort try/except + logging, matching the
    `overlay_rotated_text()` call site's pattern in `job_orchestrator.py`, so
    both best-effort steps fail the same visible way instead of each
    inventing its own swallowing convention.
    """
    lines = await run_det_probe(file_path, python_path)
    if not lines:
        return []
    middle_json: dict[str, Any] = json.loads(Path(middle_json_path).read_text(encoding="utf-8"))
    blocks = match_lines_to_middle_json(lines, middle_json)
    return build_findings(blocks)
