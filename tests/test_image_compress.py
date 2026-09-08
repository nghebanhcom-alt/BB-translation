"""Tests for `compress_pdf_images` (US-16 v1+v2, BR-IMGCOMP-01..04).

Runs the real PyMuPDF re-encode path against golden fixtures extracted from
real production job output (Protocol 5 R5-03/Protocol 6 R6-02 — no
hand-built mocks), see `tests/fixtures/babeldoc/README.md`:

- `job3594a7a3_chunk0_sample_mono.pdf` (v1 fixture): 1 raw (`Filter: null`)
  image + 3 `DCTDecode` + 1 `CCITTFaxDecode` already-compressed images. Has
  ZERO `/FlateDecode` images, so it cannot exercise the v2-widened
  eligibility filter — kept as-is for the v1 regression tests below
  (Architecture.md "US-16 v2" V7: v2 must give byte-for-byte-identical
  guard behavior on this fixture, so none of its assertions may change).
- `job78674af9_flate_sample.pdf` (v2 fixture): 2 `/FlateDecode` ICCBased
  images (1 Gray, 1 CMYK) + 1 `/DCTDecode` image, extracted from the exact
  job that motivated US-16 v2 (Architecture.md V10.1).
- `job136645f9_indexed_sample.pdf` (v2 fixture): 5 `/FlateDecode` `Indexed`
  images + 6 `/DCTDecode` images, the only real-data proof that the
  colorspace allowlist (Architecture.md W1) actually catches `Indexed`
  before a Pixmap gets built (W8 test #9, promoted to BLOCKING per W8).
"""

import shutil
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.image_compress import ImageCompressStats, compress_pdf_images

FIXTURE = Path(__file__).parent / "fixtures" / "babeldoc" / "job3594a7a3_chunk0_sample_mono.pdf"
FLATE_FIXTURE = Path(__file__).parent / "fixtures" / "babeldoc" / "job78674af9_flate_sample.pdf"
INDEXED_FIXTURE = Path(__file__).parent / "fixtures" / "babeldoc" / "job136645f9_indexed_sample.pdf"


def _page_texts(path: Path) -> list[str]:
    with fitz.open(path) as doc:
        return [page.get_text().strip() for page in doc]


def _image_xref_streams(path: Path) -> dict[int, bytes]:
    with fitz.open(path) as doc:
        xrefs: set[int] = set()
        for pno in range(doc.page_count):
            for info in doc.get_page_images(pno, full=True):
                xrefs.add(info[0])
        return {xref: doc.xref_stream_raw(xref) for xref in xrefs}


def _filters(path: Path) -> dict[int, str]:
    with fitz.open(path) as doc:
        xrefs: set[int] = set()
        for pno in range(doc.page_count):
            for info in doc.get_page_images(pno, full=True):
                xrefs.add(info[0])
        return {xref: doc.xref_get_key(xref, "Filter")[1] for xref in xrefs}


@pytest.mark.asyncio
async def test_compress_pdf_images_shrinks_file_and_preserves_content(tmp_path: Path) -> None:
    assert FIXTURE.exists(), "golden fixture missing - see tests/fixtures/babeldoc/README.md"

    work_path = tmp_path / "sample.pdf"
    shutil.copy(FIXTURE, work_path)

    size_before = work_path.stat().st_size
    texts_before = _page_texts(work_path)
    page_count_before = len(texts_before)

    stats = await compress_pdf_images(work_path)

    assert isinstance(stats, ImageCompressStats)
    size_after = work_path.stat().st_size

    # R6-03: verify actual content, not just "it ran without raising".
    assert size_after < size_before
    with fitz.open(work_path) as doc:
        assert doc.page_count == page_count_before
    assert _page_texts(work_path) == texts_before

    # The one raw image (xref 12, see README/spike data) must have been
    # recompressed; every image xref must now carry a real filter.
    assert stats.images_recompressed == 1
    filters_after = _filters(work_path)
    assert all(f != "null" for f in filters_after.values())


@pytest.mark.asyncio
async def test_compress_pdf_images_does_not_recompress_already_compressed_images(
    tmp_path: Path,
) -> None:
    """BR-IMGCOMP-02: DCTDecode/CCITTFaxDecode images already in the fixture
    must survive byte-identical — no double compression.

    Xref numbers are NOT stable across the `doc.save(..., garbage=4, ...)`
    call `compress_pdf_images` does (garbage collection renumbers/drops
    unused objects) — verified directly by this test failing on a
    xref-keyed comparison before this fix. Compare by stream byte content
    instead of by xref number.
    """
    work_path = tmp_path / "sample.pdf"
    shutil.copy(FIXTURE, work_path)

    streams_before = _image_xref_streams(work_path)
    filters_before = _filters(work_path)
    already_compressed_streams_before = sorted(
        stream for xref, stream in streams_before.items() if filters_before[xref] != "null"
    )
    assert len(already_compressed_streams_before) == 4  # 3 DCTDecode + 1 CCITTFaxDecode (live)

    stats = await compress_pdf_images(work_path)

    assert stats.images_skipped_already_compressed == 4

    streams_after = _image_xref_streams(work_path)
    filters_after = _filters(work_path)
    already_compressed_streams_after = sorted(
        stream for xref, stream in streams_after.items() if filters_after[xref] != "null"
    )
    # 1 raw image got recompressed and now also has a non-null filter, so
    # "already compressed after" has 5 entries, not 4 — restrict the
    # comparison to bytes that existed pre-run, not raw equality of the sets.
    assert set(already_compressed_streams_before) <= set(already_compressed_streams_after), (
        "one or more already-compressed images' stream bytes changed"
    )


@pytest.mark.asyncio
async def test_compress_pdf_images_stats_report_size_before_and_after(tmp_path: Path) -> None:
    work_path = tmp_path / "sample.pdf"
    shutil.copy(FIXTURE, work_path)
    size_before = work_path.stat().st_size

    stats = await compress_pdf_images(work_path)

    assert stats.size_before == size_before
    assert stats.size_after == work_path.stat().st_size
    assert stats.size_after < stats.size_before
    assert stats.images_scanned == 5


# --- US-16 v2 (Architecture.md "US-16 v2 — Final Decision", W6/W8) ---------


def _inject_key(path: Path, xref: int, key: str, value: str) -> None:
    """Test-only helper: overwrite `key` = `value` in `xref`'s object dict
    and save. NEVER used by the code under test — this exists purely to
    reach guard branches that have 0 real sample in any job surveyed so far
    (`/Decode` non-identity, `/Mask`) deterministically. Per Protocol 5 this
    is NOT a substitute for a golden fixture for the parts that DO have real
    samples (eligibility, colorspace allowlist) — those use FLATE_FIXTURE /
    INDEXED_FIXTURE above, extracted from real production output.
    """
    doc = fitz.open(path)
    try:
        doc.xref_set_key(xref, key, value)
        tmp = path.with_suffix(".injected.pdf")
        doc.save(tmp)
    finally:
        doc.close()
    tmp.replace(path)


def _mean_abs_pixel_diff(path_a: Path, path_b: Path, *, page_no: int = 0, dpi: int = 72) -> float:
    """Mean absolute per-byte diff between the same page rendered from 2
    files. No numpy in this project's `.venv` (Architecture.md X0) — pure
    Python is slow but fine for a single fixture page."""
    with fitz.open(path_a) as doc_a, fitz.open(path_b) as doc_b:
        pix_a = doc_a[page_no].get_pixmap(dpi=dpi)
        pix_b = doc_b[page_no].get_pixmap(dpi=dpi)
        assert (pix_a.width, pix_a.height) == (pix_b.width, pix_b.height)
        samples_a, samples_b = pix_a.samples, pix_b.samples
        assert len(samples_a) == len(samples_b)
        return sum(abs(a - b) for a, b in zip(samples_a, samples_b)) / len(samples_a)


@pytest.mark.asyncio
async def test_compress_pdf_images_flate_fixture_recompresses_and_preserves_content(
    tmp_path: Path,
) -> None:
    """W8 #1 (V10.2 #1): the Flate golden fixture is what actually
    exercises the v2-widened eligibility filter (FIXTURE above has 0
    `/FlateDecode` images). Assert the exact recompress count, not just
    "shrunk and didn't crash" (R6-03)."""
    assert FLATE_FIXTURE.exists(), "golden fixture missing - see tests/fixtures/babeldoc/README.md"

    work_path = tmp_path / "flate_sample.pdf"
    shutil.copy(FLATE_FIXTURE, work_path)

    size_before = work_path.stat().st_size
    texts_before = _page_texts(work_path)
    filters_before = _filters(work_path)
    streams_before = _image_xref_streams(work_path)
    dct_streams_before = {
        xref: stream
        for xref, stream in streams_before.items()
        if filters_before[xref] == "/DCTDecode"
    }
    assert len(dct_streams_before) == 1

    stats = await compress_pdf_images(work_path)

    assert stats.images_scanned == 3
    assert stats.images_recompressed == 2
    assert stats.images_skipped_already_compressed == 1  # the pre-existing DCTDecode image

    size_after = work_path.stat().st_size
    assert size_after < size_before

    with fitz.open(work_path) as doc:
        assert doc.page_count == len(texts_before)
    assert _page_texts(work_path) == texts_before

    # BR-IMGCOMP-02 (V10.2 #2): the image that was already DCTDecode must
    # survive byte-identical — no double compression, same guard as v1.
    streams_after = _image_xref_streams(work_path)
    filters_after = _filters(work_path)
    for xref, stream in dct_streams_before.items():
        assert filters_after.get(xref) == "/DCTDecode"
        assert streams_after.get(xref) == stream


@pytest.mark.asyncio
async def test_compress_pdf_images_skips_indexed_images_even_at_zero_threshold(
    tmp_path: Path,
) -> None:
    """W8 #9 — BLOCKING (Architecture.md W2.2, W8): the only real-data proof
    that the colorspace allowlist (Architecture.md W1) actually catches
    `Indexed` images BEFORE a Pixmap gets built. `Pixmap.colorspace.name`
    cannot do this — PyMuPDF expands `Indexed` to its base colorspace on
    decode, so a guard written against the decoded Pixmap's own colorspace
    name is dead code for exactly this case; verified live, 2 real Indexed
    images slipped through and got JPEG-encoded before this fix
    (Architecture.md X2). `min_recompress_bytes=0` removes the size guard so
    only the colorspace guard is under test — this fixture's real Indexed
    images are all well under 4096 bytes."""
    assert INDEXED_FIXTURE.exists(), (
        "golden fixture missing - see tests/fixtures/babeldoc/README.md"
    )

    work_path = tmp_path / "indexed_sample.pdf"
    shutil.copy(INDEXED_FIXTURE, work_path)

    with fitz.open(work_path) as doc:
        indexed_xrefs = {
            info[0]
            for pno in range(doc.page_count)
            for info in doc.get_page_images(pno, full=True)
            if info[5] in ("Indexed", "Separation")
        }
        colorspace_before = {xref: doc.xref_get_key(xref, "ColorSpace") for xref in indexed_xrefs}
    assert len(indexed_xrefs) > 0, "fixture must contain real Indexed/Separation images"

    stats = await compress_pdf_images(work_path, min_recompress_bytes=0)

    assert stats.images_recompressed == 0
    assert stats.images_skipped_colorspace == len(indexed_xrefs)

    with fitz.open(work_path) as doc:
        for xref in indexed_xrefs:
            assert doc.xref_get_key(xref, "ColorSpace") == colorspace_before[xref]


@pytest.mark.asyncio
async def test_compress_pdf_images_keeps_original_colorspace_key(tmp_path: Path) -> None:
    """W8 #10: re-encoding must NOT touch `/ColorSpace` (Architecture.md
    W2) — this is what keeps the original ICC profile. Xref numbers stay
    stable across this specific run (verified empirically: nothing is
    deleted, only 2 streams get rewritten in place, so `garbage=4` has
    nothing to renumber) — unlike the mixed v1 fixture, where the existing
    byte-content-based comparison test above deliberately avoids relying on
    xref stability."""
    work_path = tmp_path / "flate_sample.pdf"
    shutil.copy(FLATE_FIXTURE, work_path)

    with fitz.open(work_path) as doc:
        iccbased_xrefs = {
            info[0]
            for pno in range(doc.page_count)
            for info in doc.get_page_images(pno, full=True)
            if info[5] == "ICCBased"
        }
        colorspace_before = {xref: doc.xref_get_key(xref, "ColorSpace") for xref in iccbased_xrefs}
    assert len(iccbased_xrefs) == 2

    stats = await compress_pdf_images(work_path)
    assert stats.images_recompressed == 2

    with fitz.open(work_path) as doc:
        xrefs_after = {
            info[0] for pno in range(doc.page_count) for info in doc.get_page_images(pno, full=True)
        }
        assert iccbased_xrefs <= xrefs_after, "xref numbers shifted — cannot compare by xref"

        info5_after = {
            info[0]: info[5]
            for pno in range(doc.page_count)
            for info in doc.get_page_images(pno, full=True)
        }
        for xref in iccbased_xrefs:
            assert doc.xref_get_key(xref, "ColorSpace") == colorspace_before[xref]
            assert doc.xref_get_key(xref, "Filter") == ("name", "/DCTDecode")
            assert info5_after[xref] == "ICCBased"


@pytest.mark.asyncio
async def test_compress_pdf_images_clears_decode_and_preserves_pixel_render(
    tmp_path: Path,
) -> None:
    """W8 #12 — BLOCKING, upgrades V10.2 #4 per X7.1: `Pixmap(doc, xref)`
    APPLIES `/Decode` when decoding (verified live, Architecture.md C4), but
    `update_stream()` does NOT remove the key — left in place, a future
    render would apply the SAME transform a SECOND time (negative image).
    This bug has never fired on real data (every `/Decode` array surveyed
    so far is identity), so a key-level assertion alone can't prove a
    viewer renders correctly — check the pixel level too (Expert measured
    0.46/255 mean diff for the correct fix vs 42.28/255 for the known-wrong
    "leave /Decode in place" behavior, Architecture.md X7.1)."""
    reference_path = tmp_path / "reference_injected.pdf"  # /Decode injected, NEVER compressed
    work_path = tmp_path / "work_injected.pdf"  # /Decode injected, then compressed
    shutil.copy(FLATE_FIXTURE, reference_path)
    shutil.copy(FLATE_FIXTURE, work_path)

    with fitz.open(reference_path) as doc:
        page_no, flate_xref = next(
            (pno, info[0])
            for pno in range(doc.page_count)
            for info in doc.get_page_images(pno, full=True)
            if doc.xref_get_key(info[0], "Filter") == ("name", "/FlateDecode")
            and fitz.Pixmap(doc, info[0]).n == 1
        )

    _inject_key(reference_path, flate_xref, "Decode", "[1 0]")
    _inject_key(work_path, flate_xref, "Decode", "[1 0]")

    with fitz.open(work_path) as doc:
        assert doc.xref_get_key(flate_xref, "Decode")[0] != "null"

    stats = await compress_pdf_images(work_path)
    assert stats.images_recompressed >= 1

    with fitz.open(work_path) as doc:
        assert doc.xref_get_key(flate_xref, "Decode") == ("null", "null")

    mean_diff = _mean_abs_pixel_diff(reference_path, work_path, page_no=page_no)
    # Real threshold from Expert's measurement is 0.46 (correct) vs 42.28
    # (wrong) — pick a value with real margin from the wrong case rather
    # than tuned to the exact number (renderer/dpi choice shifts it a bit).
    assert mean_diff < 5.0, (
        f"mean pixel diff {mean_diff:.2f}/255 too high — /Decode may be applied twice"
    )


@pytest.mark.asyncio
async def test_compress_pdf_images_skips_images_with_mask_key(tmp_path: Path) -> None:
    """W8 #11 — BLOCKING: `/Mask` (color-key array or a stencil-mask xref
    reference) has 0 real samples across every job surveyed so far
    (Architecture.md W9), so this guard is only reachable by injection —
    still required per Protocol 5 (the mechanism must be proven live, not
    "trust me"), see Architecture.md W3/X4."""
    work_path = tmp_path / "flate_sample.pdf"
    shutil.copy(FLATE_FIXTURE, work_path)

    with fitz.open(work_path) as doc:
        flate_xref = next(
            info[0]
            for pno in range(doc.page_count)
            for info in doc.get_page_images(pno, full=True)
            if doc.xref_get_key(info[0], "Filter") == ("name", "/FlateDecode")
        )
        stream_before = doc.xref_stream_raw(flate_xref)

    _inject_key(work_path, flate_xref, "Mask", "[200 255]")

    stats = await compress_pdf_images(work_path)

    assert stats.images_skipped_unsupported == 1
    assert stats.images_recompressed == 1  # the other Flate image, untouched by the injection

    with fitz.open(work_path) as doc:
        assert doc.xref_get_key(flate_xref, "Filter") == ("name", "/FlateDecode")
        assert doc.xref_stream_raw(flate_xref) == stream_before
