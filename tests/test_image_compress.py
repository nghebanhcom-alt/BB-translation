"""Tests for `compress_pdf_images` (US-16, BR-IMGCOMP-01..04).

Runs the real PyMuPDF re-encode path against the golden fixture
`tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf` (already used by
`tests/test_chunk_merge.py`, see `tests/fixtures/babeldoc/README.md`) rather
than a hand-built fixture, per Protocol 5 R5-03/Protocol 6 R6-02: the sample
has 1 raw (`Filter: null`) image and 3 `DCTDecode` + 1 `CCITTFaxDecode`
already-compressed images (verified live, see Architecture.md US-16 S9), so
it exercises both the recompress path and the "leave already-compressed
images alone" guard on real data.
"""

import shutil
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.postprocess.image_compress import ImageCompressStats, compress_pdf_images

FIXTURE = Path(__file__).parent / "fixtures" / "babeldoc" / "job3594a7a3_chunk0_sample_mono.pdf"


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
