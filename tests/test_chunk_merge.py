"""Tests for `merge_chunk_pdfs` (Bug #7 fix).

Fixtures model the REAL `pdf2zh` output shape, verified against real
`pdf2zh` runs (see `tests/fixtures/pdf2zh/README.md`): every chunk's
`{stem}-mono.pdf` contains the FULL original document, not just that
chunk's own page range — only the pages inside the `--pages` range passed
to that invocation are translated, the rest stay in the source language.
`_make_full_doc_mono_pdf` below reproduces that shape (each simulated
"chunk mono.pdf" carries every page of the source document) instead of the
previous test's chunk-scoped mock, which is exactly the un-verified
assumption that caused Bug #7 (real `chunk_doc.page_count` never matched a
chunk's own range once a job had >=2 chunks).
"""

from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.models.chunk import Chunk
from src.postprocess.chunk_merge import ChunkMergeError, merge_chunk_pdfs


def _make_full_doc_mono_pdf(path: Path, total_pages: int, translated_range: tuple[int, int]) -> None:
    """Build a fake `{stem}-mono.pdf` the way real pdf2zh does: ALL
    `total_pages` of the source document, with pages inside
    `translated_range` (1-indexed, inclusive) marked "translated" and every
    other page marked "original" — mirroring the golden fixtures at
    `tests/fixtures/pdf2zh/6page_range1-3_mono.pdf` /
    `6page_range3-6_mono.pdf`.
    """
    start, end = translated_range
    doc = fitz.open()
    for page_num in range(1, total_pages + 1):
        page = doc.new_page()
        tag = "translated" if start <= page_num <= end else "original"
        page.insert_text((50, 100), f"P{page_num}-{tag}", fontsize=14)
    doc.save(path)
    doc.close()


def _page_texts(path: Path) -> list[str]:
    with fitz.open(path) as doc:
        return [page.get_text().strip() for page in doc]


@pytest.mark.asyncio
async def test_merge_chunk_pdfs_golden_shape_three_chunks(tmp_path: Path) -> None:
    """Reproduces the QA Vong 5 Bug #7 scenario: 81-page doc, chunk_size=40,
    overlap=2 -> chunks [1-40], [39-80], [79-81] (`calculate_chunks()` in
    `src/core/chunking.py`). Each chunk's mono.pdf carries all 81 pages
    (golden-verified shape); merge must produce exactly 81 pages, each one
    the "translated" tag from the chunk actually responsible for it.
    """
    total_pages = 81
    chunk0_path = tmp_path / "chunk_000-mono.pdf"
    chunk1_path = tmp_path / "chunk_001-mono.pdf"
    chunk2_path = tmp_path / "chunk_002-mono.pdf"

    _make_full_doc_mono_pdf(chunk0_path, total_pages, (1, 40))
    _make_full_doc_mono_pdf(chunk1_path, total_pages, (39, 80))
    _make_full_doc_mono_pdf(chunk2_path, total_pages, (79, 81))

    chunks = [
        Chunk(
            job_id="job-1",
            chunk_index=0,
            page_start=1,
            page_end=40,
            overlap_start=None,
            overlap_end=None,
            output_path=str(chunk0_path),
        ),
        Chunk(
            job_id="job-1",
            chunk_index=1,
            page_start=39,
            page_end=80,
            overlap_start=39,
            overlap_end=40,
            output_path=str(chunk1_path),
        ),
        Chunk(
            job_id="job-1",
            chunk_index=2,
            page_start=79,
            page_end=81,
            overlap_start=79,
            overlap_end=80,
            output_path=str(chunk2_path),
        ),
    ]

    output_path = tmp_path / "merged.pdf"
    await merge_chunk_pdfs(chunks, output_path)

    with fitz.open(output_path) as merged:
        assert merged.page_count == total_pages

    texts = _page_texts(output_path)
    assert texts == [f"P{n}-translated" for n in range(1, total_pages + 1)]


@pytest.mark.asyncio
async def test_merge_chunk_pdfs_golden_fixture_real_pdf2zh_output(tmp_path: Path) -> None:
    """Uses the actual `pdf2zh` output files captured in
    tests/fixtures/pdf2zh/ (6-page source, ranges 1-3 and 3-6, real
    `-s google` run) as a 2-chunk job with a 1-page overlap on page 3.
    """
    fixtures_dir = Path(__file__).parent / "fixtures" / "pdf2zh"
    range1_mono = fixtures_dir / "6page_range1-3_mono.pdf"
    range2_mono = fixtures_dir / "6page_range3-6_mono.pdf"
    assert range1_mono.exists(), "golden fixture missing - see tests/fixtures/pdf2zh/README.md"
    assert range2_mono.exists(), "golden fixture missing - see tests/fixtures/pdf2zh/README.md"

    chunks = [
        Chunk(
            job_id="job-2",
            chunk_index=0,
            page_start=1,
            page_end=3,
            overlap_start=None,
            overlap_end=None,
            output_path=str(range1_mono),
        ),
        Chunk(
            job_id="job-2",
            chunk_index=1,
            page_start=3,
            page_end=6,
            overlap_start=3,
            overlap_end=3,
            output_path=str(range2_mono),
        ),
    ]

    output_path = tmp_path / "merged.pdf"
    await merge_chunk_pdfs(chunks, output_path)

    with fitz.open(output_path) as merged:
        assert merged.page_count == 6

    texts = _page_texts(output_path)
    # Pages 1-3 come from chunk 0's translated range; pages 4-6 from chunk 1's.
    assert "Trang 1" in texts[0] and "abc1xyz" in texts[0]
    assert "Trang 2" in texts[1] and "abc2xyz" in texts[1]
    assert "Trang 3" in texts[2] and "abc3xyz" in texts[2]
    assert "Trang 4" in texts[3] and "abc4xyz" in texts[3]
    assert "Trang 5" in texts[4] and "abc5xyz" in texts[4]
    assert "Trang 6" in texts[5] and "abc6xyz" in texts[5]
    # None of the merged pages should be untranslated English leftovers.
    assert not any("Page " in t and "unique marker" in t for t in texts)


@pytest.mark.asyncio
async def test_merge_chunk_pdfs_single_chunk_no_overlap(tmp_path: Path) -> None:
    total_pages = 30
    chunk0_path = tmp_path / "chunk_000-mono.pdf"
    _make_full_doc_mono_pdf(chunk0_path, total_pages, (1, total_pages))

    chunks = [
        Chunk(
            job_id="job-1",
            chunk_index=0,
            page_start=1,
            page_end=total_pages,
            output_path=str(chunk0_path),
        )
    ]

    output_path = tmp_path / "merged.pdf"
    await merge_chunk_pdfs(chunks, output_path)

    with fitz.open(output_path) as merged:
        assert merged.page_count == total_pages
    texts = _page_texts(output_path)
    assert texts == [f"P{n}-translated" for n in range(1, total_pages + 1)]


@pytest.mark.asyncio
async def test_merge_chunk_pdfs_raises_when_output_path_missing(tmp_path: Path) -> None:
    chunks = [Chunk(job_id="job-1", chunk_index=0, page_start=1, page_end=10, output_path=None)]

    with pytest.raises(ChunkMergeError):
        await merge_chunk_pdfs(chunks, tmp_path / "merged.pdf")
