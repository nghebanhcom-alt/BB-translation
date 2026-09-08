"""Tests for `src/postprocess/rotated_text_overlay.py` (Architecture.md
"Final Decision: Babeldoc Layout Bug Fix Roadmap", U3/U4 P1.1 -- G1e).

Protocol 5 R5-03 (real dependency, not mocked geometry): every scan/group/fit
assertion below runs PyMuPDF for real against
`tests/fixtures/babeldoc/rotated_text_p67_source.pdf` /
`rotated_chart_p15_source.pdf` -- golden fixtures cut directly from the real
production file (see `tests/fixtures/babeldoc/README.md`), not hand-typed.

Protocol 6 R6-02 (assert data lineage, not just "was it called"): the only
thing mocked anywhere in this file is the LLM call itself
(`TranslationProvider.translate()`), at the LOWEST level -- a real
`FakeTranslationProvider.translate()` implementation, not
`unittest.mock.AsyncMock` wrapped around `assert_called()`. Every overlay
test below asserts the ACTUAL VALUE drawn onto the output PDF equals what
the fake provider returned (not the source English text) -- this is exactly
the lineage check Bug #5 (Architecture.md) was missed by NOT having.
"""

from pathlib import Path

import fitz
import pytest

from src.postprocess.rotated_text_overlay import (
    MIN_FONT_SCALE,
    FitResult,
    RotatedBlock,
    RotatedLine,
    _draw_block,
    fit_translated_block,
    group_rotated_lines,
    line_angle_deg,
    overlay_rotated_text,
    scan_rotated_lines,
    translate_rotated_blocks,
)
from src.services.layout_qa import ROTATED_OVERLAY_FLAG_CHECK
from src.services.translation import TranslationProvider, TranslationResult

FIXTURES = Path(__file__).parent / "fixtures" / "babeldoc"
P67_SOURCE = FIXTURES / "rotated_text_p67_source.pdf"
P15_SOURCE = FIXTURES / "rotated_chart_p15_source.pdf"
NO_ROTATION_SOURCE = FIXTURES / "page14_numbered_list_source.pdf"
#: Bug #8 round-2 regression fixture (docs/review-report.md, issue Blocking
#: #1) -- the SAME real Le Cordon Bleu excerpt that exposed the
#: `page.insert_text()` MediaBox/CropBox coordinate bug in
#: `font_shrink.py::_redraw_span` (mediabox=(33,33,681,816),
#: cropbox=(0,-33,714,816)) also reproduces it here, live-verified by the
#: reviewer directly against `_draw_block`'s exact call shape.
LCB_TOC_FIXTURE = FIXTURES / "toc_sources" / "lcb_toc.pdf"
NOTO_FONT_PATH = Path(__file__).parent.parent / "fonts" / "NotoSerif-Regular.ttf"

#: Realistic Vietnamese translation, similar length to the real EN source
#: paragraph on p67 (~600 chars) -- long enough to require real word-wrap
#: across multiple lines, short enough to fit at scale 1.0.
_VI_TRANSLATION_FITS = (
    "Disaccharide. Tu disaccharide duoc cau tao tu tien to di, nghia la hai, va goc tu "
    "saccharide, nghia la duong. Dieu nay kha ro rang khi xem xet cac disaccharide nhu "
    "sucrose (duong cat), lactose (co trong sua), va maltose (co trong ngu coc nay mam) "
    "deu duoc tao thanh tu hai monosaccharide. Trong truong hop sucrose, hai monosaccharide "
    "lien ket la fructose va glucose, ban than chung co the duoc tach ra de tao thanh hai san "
    "pham duong khac nhau. So do di kem cho thay phan tu fructose, phan tu glucose, va lien "
    "ket tao nen mot phan tu sucrose."
)


class FakeTranslationProvider:
    """Minimal real implementation of `TranslationProvider` (not a mock of
    the whole overlay call) -- lets tests control EXACTLY what text comes
    back from `translate()` and assert the overlay drew THAT, not the
    source text, per R6-02."""

    def __init__(self, translated_text: str) -> None:
        self.translated_text = translated_text
        self.calls: list[tuple[str, str, str, str]] = []

    async def translate(
        self, text: str, glossary_prompt: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        self.calls.append((text, glossary_prompt, source_lang, target_lang))
        return TranslationResult(
            text=self.translated_text,
            input_tokens=len(text.split()),
            output_tokens=len(self.translated_text.split()),
            estimated_cost_usd=0.0,
            provider_name="fake",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0


def _as_translation_provider(provider: FakeTranslationProvider) -> TranslationProvider:
    # `TranslationProvider` is a structural `Protocol` (not `@runtime_checkable`
    # -- `isinstance()` against it would raise `TypeError`), so this is a
    # type-checker-only cast: `FakeTranslationProvider` satisfies the
    # Protocol's shape (`translate()` + `estimate_cost()`) by construction.
    return provider


def test_scan_rotated_lines_matches_source_dir_from_architecture_spike() -> None:
    """Architecture.md U3: the real p67 rotated block has `dir=(0.982,-0.191)`
    (angle -11 deg) -- regression guard that `scan_rotated_lines` (which
    reuses `layout_qa.line_angle_deg`/`is_rotated`, R6-01) still detects it."""
    doc = fitz.open(P67_SOURCE)
    try:
        lines = scan_rotated_lines(doc[0])
    finally:
        doc.close()

    assert len(lines) >= 16
    for line in lines:
        assert line.angle_deg == pytest.approx(-11.0, abs=0.5)
        assert line.dir[0] == pytest.approx(0.9816, abs=0.01)
        assert line.dir[1] == pytest.approx(-0.1908, abs=0.01)
    assert any("Disaccharide" in line.text for line in lines)


def test_scan_rotated_lines_noop_on_non_rotated_page() -> None:
    doc = fitz.open(NO_ROTATION_SOURCE)
    try:
        lines = scan_rotated_lines(doc[0])
    finally:
        doc.close()
    assert lines == []


def test_group_rotated_lines_merges_p67_paragraph_into_one_block() -> None:
    """Architecture.md U3: "16 dòng nghiêng -11° ở trang 67" is ONE logical
    paragraph, not 16 unrelated blocks -- `group_rotated_lines` must merge
    them so translation gets full sentence context (data lineage: a
    fragmented paragraph fed word-by-word to the LLM would produce
    incoherent, ungrammatical translations)."""
    doc = fitz.open(P67_SOURCE)
    try:
        lines = scan_rotated_lines(doc[0])
    finally:
        doc.close()

    blocks = group_rotated_lines(lines, page_number=67)
    assert len(blocks) == 1
    block = blocks[0]
    assert block.page_number == 67
    assert "Disaccharide" in block.source_text
    assert "building" in block.source_text or "sucrose molecule" in block.source_text


def test_group_rotated_lines_keeps_p15_chart_labels_separate() -> None:
    """`rotated_chart_p15_source.pdf` is a rotated CHART with scattered
    same-angle labels (title / note / column headers / data grid), not one
    continuous paragraph. Regression guard for the grouping heuristic: it
    must NOT concatenate the whole page into a single nonsense block."""
    doc = fitz.open(P15_SOURCE)
    try:
        lines = scan_rotated_lines(doc[0])
    finally:
        doc.close()

    blocks = group_rotated_lines(lines, page_number=15)
    assert len(blocks) > 1
    joined_titles = " ".join(b.source_text for b in blocks)
    assert "CONVERSION CHART" in joined_titles


@pytest.mark.asyncio
async def test_translate_rotated_blocks_returns_provider_result_not_source_text() -> None:
    """R6-02: the dict `translate_rotated_blocks` returns must contain what
    the LLM PROVIDER returned, not a re-read of the source text -- the exact
    lineage distinction Bug #5 (Architecture.md Protocol 6) was missed by
    NOT asserting."""
    block = RotatedBlock(
        page_number=67,
        lines=scan_rotated_lines(fitz.open(P67_SOURCE)[0]),
    )
    marker_translation = "BAN DICH GIA LAP KHONG PHAI TEXT GOC"
    provider = _as_translation_provider(FakeTranslationProvider(marker_translation))

    result = await translate_rotated_blocks([block], provider, glossary_prompt="glossary-x")

    assert result[id(block)] == marker_translation
    assert result[id(block)] != block.source_text
    # Provider was called with the SOURCE text (that's what it's supposed to
    # translate) and the glossary prompt passed through untouched.
    called_text, called_glossary, called_src, called_tgt = provider.calls[0]
    assert called_text == block.source_text
    assert called_glossary == "glossary-x"
    assert called_src == "en"
    assert called_tgt == "vi"


def test_fit_translated_block_fits_realistic_translation_at_full_scale() -> None:
    doc = fitz.open(P67_SOURCE)
    try:
        blocks = group_rotated_lines(scan_rotated_lines(doc[0]), page_number=67)
    finally:
        doc.close()
    font = fitz.Font(fontfile=str(NOTO_FONT_PATH))

    fit = fit_translated_block(blocks[0], _VI_TRANSLATION_FITS, font)

    assert fit.fits is True
    assert fit.scale == pytest.approx(1.0)
    assert len(fit.wrapped_lines) > 1


def test_fit_translated_block_flags_when_too_long_even_at_min_scale() -> None:
    """U5/U7-E1 policy: shrink at most to MIN_FONT_SCALE (70%), never lower
    -- a translation far too long to fit even then must report `fits=False`
    at exactly `MIN_FONT_SCALE`, not keep shrinking further."""
    doc = fitz.open(P67_SOURCE)
    try:
        blocks = group_rotated_lines(scan_rotated_lines(doc[0]), page_number=67)
    finally:
        doc.close()
    font = fitz.Font(fontfile=str(NOTO_FONT_PATH))

    huge_translation = _VI_TRANSLATION_FITS * 8

    fit = fit_translated_block(blocks[0], huge_translation, font)

    assert fit.fits is False
    assert fit.scale == pytest.approx(MIN_FONT_SCALE)


def _build_babeldoc_output_stub(source_path: Path, dest_path: Path) -> None:
    """Build a stand-in for "what babeldoc's real output looks like after it
    silently dropped the rotated text" (V-1/E-2, Architecture.md U1): copy
    the real source page, then REDACT (white-fill, a real PyMuPDF operation,
    not hand-typed content) the bbox region covering the rotated lines --
    this is the legitimate way to get a "rotated text is gone" page for
    testing OUR overlay step without needing a full babeldoc CLI run inside
    this test (Protocol 5 golden-file discipline: the SOURCE is real and
    unmodified; only the "already lost" simulation uses a real, documented
    PyMuPDF op, not a fabricated assumption about babeldoc's byte output)."""
    doc = fitz.open(source_path)
    try:
        page = doc[0]
        lines = scan_rotated_lines(page)
        blocks = group_rotated_lines(lines, page_number=1)
        for block in blocks:
            page.add_redact_annot(fitz.Rect(block.bbox), fill=(1, 1, 1))
        page.apply_redactions()
        doc.save(dest_path)
    finally:
        doc.close()


@pytest.mark.asyncio
async def test_overlay_rotated_text_draws_translated_text_at_correct_angle(
    tmp_path: Path,
) -> None:
    """End-to-end (real PyMuPDF read+write, real font, fake LLM at the
    lowest level -- R5-03/R6-02/R6-03): after overlay, the output PDF must
    contain the PROVIDER'S translated text (not the English source) drawn at
    the SAME angle as the original source block, and the finding queue must
    be empty (it fit)."""
    output_path = tmp_path / "translated_vi.pdf"
    _build_babeldoc_output_stub(P67_SOURCE, output_path)

    # Confirm the stub really did lose the rotated text (sanity on our own
    # test fixture construction, not on babeldoc).
    stub_doc = fitz.open(output_path)
    try:
        assert scan_rotated_lines(stub_doc[0]) == []
        assert "Disaccharide" not in stub_doc[0].get_text()
    finally:
        stub_doc.close()

    marker_translation = _VI_TRANSLATION_FITS
    provider = _as_translation_provider(FakeTranslationProvider(marker_translation))

    result = await overlay_rotated_text(
        source_pdf_path=P67_SOURCE,
        output_pdf_path=output_path,
        provider=provider,
        glossary_prompt="(khong co glossary)",
        font_path=NOTO_FONT_PATH,
    )

    assert result.findings == []
    assert result.overlaid_block_count == 1
    assert result.flagged_block_count == 0
    assert len(provider.calls) == 1

    out_doc = fitz.open(output_path)
    try:
        page = out_doc[0]
        page_text = page.get_text()
        assert "Disaccharide" in page_text  # first word of marker_translation
        assert "phan tu sucrose" in page_text  # last words of marker_translation

        drawn_lines = [
            line
            for block in page.get_text("dict")["blocks"]
            if block.get("type") == 0
            for line in block.get("lines", [])
            if line_angle_deg(line["dir"]) == pytest.approx(-11.0, abs=1.0)
        ]
        assert drawn_lines, "khong tim thay dong nao duoc ve dung goc xoay -11 deg"
    finally:
        out_doc.close()


@pytest.mark.asyncio
async def test_overlay_rotated_text_flags_and_skips_drawing_when_too_long(
    tmp_path: Path,
) -> None:
    """The nhánh FLAG bắt buộc theo brief: a translation too long to fit even
    at MIN_FONT_SCALE must NOT be drawn (keep babeldoc's blank space, per
    U5/U7-E1 policy) and must produce a `ROTATED_OVERLAY_FLAG_CHECK` finding
    for QA to review by hand."""
    output_path = tmp_path / "translated_vi.pdf"
    _build_babeldoc_output_stub(P67_SOURCE, output_path)

    huge_marker = "KHOI DICH QUA DAI KHONG THE VUA BBOX GOC DU DA BOP TOI TOI THIEU. " * 40
    provider = _as_translation_provider(FakeTranslationProvider(huge_marker))

    result = await overlay_rotated_text(
        source_pdf_path=P67_SOURCE,
        output_pdf_path=output_path,
        provider=provider,
        glossary_prompt="(khong co glossary)",
        font_path=NOTO_FONT_PATH,
    )

    assert result.overlaid_block_count == 0
    assert result.flagged_block_count == 1
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.check_type == ROTATED_OVERLAY_FLAG_CHECK
    assert finding.severity == "blocker"
    assert finding.page_number == 1
    assert finding.detail["attempted_scale"] == pytest.approx(MIN_FONT_SCALE)
    assert "KHOI DICH QUA DAI" in finding.detail["translated_text"]

    # Not drawn: the huge marker text must NOT appear in the output page at
    # all (neither at the rotated angle nor anywhere else) -- "giu nguyen
    # cho trong babeldoc de lai, khong overlay de chu vo len" policy.
    out_doc = fitz.open(output_path)
    try:
        assert "KHOI DICH QUA DAI" not in out_doc[0].get_text()
    finally:
        out_doc.close()


@pytest.mark.asyncio
async def test_overlay_rotated_text_noop_when_no_rotated_lines(tmp_path: Path) -> None:
    """A normal (non-rotated) page must produce zero LLM calls and the
    output file must be left untouched -- no wasted resave on every babeldoc
    job just because this feature exists."""
    output_path = tmp_path / "translated_vi.pdf"
    doc = fitz.open(NO_ROTATION_SOURCE)
    try:
        doc.save(output_path)
    finally:
        doc.close()
    original_bytes = output_path.read_bytes()

    provider = _as_translation_provider(FakeTranslationProvider("should never be used"))

    result = await overlay_rotated_text(
        source_pdf_path=NO_ROTATION_SOURCE,
        output_pdf_path=output_path,
        provider=provider,
        glossary_prompt="(khong co glossary)",
        font_path=NOTO_FONT_PATH,
    )

    assert result.findings == []
    assert result.overlaid_block_count == 0
    assert result.flagged_block_count == 0
    assert provider.calls == []
    assert output_path.read_bytes() == original_bytes


def _span_with_text(page: "fitz.Page", text_marker: str) -> dict | None:
    """Finds the span whose text matches `text_marker` exactly -- used
    instead of matching by origin alone because `lcb_toc.pdf` already has
    real page content (a genuine "Contents" heading) whose origin happens to
    coincide with the reviewer's reproduction pivot; matching by origin only
    would find that PRE-EXISTING span and pass vacuously regardless of
    whether `_draw_block` drew anything at all, let alone at the right
    place."""
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["text"] == text_marker:
                    return span
    return None


def test_draw_block_lands_on_pivot_despite_mediabox_cropbox_offset() -> None:
    """Regression for Bug #8 round-2 (`docs/review-report.md`, "Bug #8 ...
    review `font_shrink.py` MediaBox/CropBox fix", issue Blocking #1): the
    reviewer live-reproduced the exact same `page.insert_text()`
    MediaBox/CropBox coordinate bug fixed in `font_shrink.py::_redraw_span`
    inside `_draw_block`, on this SAME real fixture --

        mediabox: Rect(33.0, 33.0, 681.0, 816.0)  cropbox_position: Point(0.0, -33.0)
        intended pivot (page-space, from get_text dict): (261.53, 154.71)
        actual landing origin (pre-fix): (228.53, 121.71)
        OFFSET ERROR: dx=-33.0, dy=-33.0

    -- because `_draw_block` calls `page.insert_text(pivot, ...,
    morph=(pivot, ...))` with a page-space `pivot` (sourced from
    `block.pivot`, which is `RotatedLine.origin`, itself read from
    `page.get_text("dict")` in `scan_rotated_lines`) without ever correcting
    it, the same class of bug as `font_shrink.py`'s uncorrected `origin`.
    This test uses the reviewer's own reproduction values directly. It FAILS
    on the pre-fix code (verified via `git stash` on
    `src/postprocess/rotated_text_overlay.py`) and PASSES once `_draw_block`
    applies `insert_text_origin_fix` to `pivot` before drawing."""
    doc = fitz.open(LCB_TOC_FIXTURE)
    try:
        page = doc[0]
        mediabox_origin = (page.mediabox.x0, 0.0)
        cropbox_position = (page.cropbox_position.x, page.cropbox_position.y)
        assert cropbox_position != mediabox_origin, (
            "fixture sanity check failed: this test only proves anything when "
            "the page's CropBox origin actually diverges from its MediaBox "
            f"origin (got cropbox_position={cropbox_position}, "
            f"mediabox origin={mediabox_origin})"
        )

        # A single-line, non-rotated (angle_deg=0.0) block is enough to
        # exercise `_draw_block`'s `page.insert_text()` call and its
        # `insert_text_origin_fix` correction in isolation -- the rotation
        # angle itself is orthogonal to the MediaBox/CropBox offset bug (see
        # `insert_text_origin_fix`'s docstring: PyMuPDF's CTM-based rotation
        # handling is independent of the CropBox-position offset bug).
        #
        # `pivot_page_space` intentionally reuses the reviewer's own
        # reproduction value verbatim -- which turns out to coincide almost
        # exactly with this fixture's real "Contents" heading span already
        # on the page (origin (261.5346, 154.7097)). That is exactly why
        # `_span_with_text` below matches on the DRAWN TEXT, not on origin
        # proximity: an origin-only check would find that pre-existing
        # "Contents" span and pass vacuously no matter what `_draw_block`
        # actually did.
        pivot_page_space = (261.53, 154.71)
        marker_text = "Khoi chu xoay gia lap cho test hoi quy Bug8 R2"
        line = RotatedLine(
            bbox=(
                pivot_page_space[0],
                pivot_page_space[1] - 11.0,
                pivot_page_space[0] + 180.0,
                pivot_page_space[1] + 3.0,
            ),
            dir=(1.0, 0.0),
            angle_deg=0.0,
            text=marker_text,
            font_size=11.0,
            origin=pivot_page_space,
        )
        block = RotatedBlock(page_number=1, lines=[line])
        fit = FitResult(fits=True, scale=1.0, font_size=11.0, wrapped_lines=[marker_text])

        assert _span_with_text(page, marker_text) is None  # sanity: not there yet

        _draw_block(page, block, fit, str(NOTO_FONT_PATH))

        redrawn = _span_with_text(page, marker_text)
        assert redrawn is not None, (
            "the block _draw_block was told to draw never landed on the page"
        )
        assert redrawn["origin"][0] == pytest.approx(pivot_page_space[0], abs=0.05), (
            f"marker text landed at x={redrawn['origin'][0]!r}, expected "
            f"{pivot_page_space[0]!r} -- the exact 'chữ nhảy lung tung' "
            "symptom Bug #8 describes: text drawn at the wrong position "
            "instead of at its own bbox"
        )
        assert redrawn["origin"][1] == pytest.approx(pivot_page_space[1], abs=0.05), (
            f"marker text landed at y={redrawn['origin'][1]!r}, expected "
            f"{pivot_page_space[1]!r} -- the exact 'chữ nhảy lung tung' "
            "symptom Bug #8 describes: text drawn at the wrong position "
            "instead of at its own bbox"
        )
    finally:
        doc.close()
