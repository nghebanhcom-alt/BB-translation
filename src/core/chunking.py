"""Page-range chunking algorithm (Architecture.md section 6.1, BR-CHUNK-01..05).

Naming note: the plan-level chunk here is called `ChunkPlan`, not `Chunk` —
`Chunk` is already the SQLModel DB table in `src/models/chunk.py`. Reusing
that name for a plain dataclass would shadow the DB model in any module that
imports both (the Job Orchestrator does).
"""

from dataclasses import dataclass

#: BR-CHUNK-01: chunk only when the file exceeds either threshold.
CHUNK_THRESHOLD_PAGES = 50
CHUNK_THRESHOLD_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class ChunkPlan:
    index: int
    page_start: int
    page_end: int
    overlap_start: int | None
    overlap_end: int | None


def calculate_chunks(total_pages: int, chunk_size: int = 40, overlap: int = 2) -> list[ChunkPlan]:
    """Split `total_pages` into overlapping page-range chunks.

    Matches the worked example in Architecture.md section 6.1: 120 pages,
    chunk_size=40, overlap=2 -> chunks [1-40], [39-80], [79-120], where the
    leading `overlap` pages of every chunk after the first (39-40, 79-80) are
    context-only carried over from the previous chunk, not re-translated.

    The literal formula in the Architecture.md code sample (`overlap_start =
    max(1, start - overlap)`) does not reproduce that worked example — e.g. it
    yields overlap_start=37 for chunk 1, not 39. This implementation instead
    derives the formula from the worked example and from the prose right
    below it ("Pages {overlap_start}-{overlap_end} la context ... Chi dich tu
    page {actual_start}"), which requires overlap_start == page_start.
    """
    if total_pages < 1:
        raise ValueError("total_pages must be >= 1")
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    chunks: list[ChunkPlan] = []
    start = 1
    idx = 0
    while start <= total_pages:
        if idx == 0:
            end = min(start + chunk_size - 1, total_pages)
            overlap_start: int | None = None
            overlap_end: int | None = None
        else:
            end = min(start + overlap + chunk_size - 1, total_pages)
            overlap_start = start
            overlap_end = min(start + overlap - 1, end)

        chunks.append(
            ChunkPlan(
                index=idx,
                page_start=start,
                page_end=end,
                overlap_start=overlap_start,
                overlap_end=overlap_end,
            )
        )

        if end >= total_pages:
            break
        start = end - overlap + 1
        idx += 1

    return chunks


def plan_chunks(
    total_pages: int,
    file_size_bytes: int,
    chunk_size: int = 40,
    overlap: int = 2,
) -> list[ChunkPlan]:
    """BR-CHUNK-01: only chunk when the file exceeds 50 pages or 20MB.

    Otherwise the whole file is processed as a single chunk covering every
    page, so downstream code (Job Orchestrator, chunk merge) never needs a
    separate "no-chunking" code path.
    """
    if total_pages <= CHUNK_THRESHOLD_PAGES and file_size_bytes <= CHUNK_THRESHOLD_BYTES:
        return [
            ChunkPlan(
                index=0,
                page_start=1,
                page_end=total_pages,
                overlap_start=None,
                overlap_end=None,
            )
        ]
    return calculate_chunks(total_pages, chunk_size=chunk_size, overlap=overlap)
