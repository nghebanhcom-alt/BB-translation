from itertools import pairwise

from src.core.chunking import calculate_chunks, plan_chunks


def test_plan_chunks_small_file_single_chunk() -> None:
    chunks = plan_chunks(total_pages=30, file_size_bytes=5 * 1024 * 1024)

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 30
    assert chunks[0].overlap_start is None
    assert chunks[0].overlap_end is None


def test_plan_chunks_large_file_chunks_with_overlap() -> None:
    chunks = plan_chunks(total_pages=120, file_size_bytes=5 * 1024 * 1024)

    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 40), (39, 80), (79, 120)]
    assert chunks[0].overlap_start is None
    assert chunks[0].overlap_end is None
    assert chunks[1].overlap_start == 39
    assert chunks[1].overlap_end == 40
    assert chunks[2].overlap_start == 79
    assert chunks[2].overlap_end == 80


def test_plan_chunks_small_page_count_but_large_size_still_chunks() -> None:
    chunks = plan_chunks(total_pages=45, file_size_bytes=25 * 1024 * 1024)

    assert len(chunks) > 1
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 45


def test_calculate_chunks_covers_every_page_without_gaps() -> None:
    chunks = calculate_chunks(total_pages=120, chunk_size=40, overlap=2)

    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 120
    for prev, nxt in pairwise(chunks):
        assert nxt.page_start <= prev.page_end + 1


def test_calculate_chunks_single_page() -> None:
    chunks = calculate_chunks(total_pages=1, chunk_size=40, overlap=2)
    assert chunks == [calculate_chunks(1)[0]]
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
