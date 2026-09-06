"""Re-encode raw (unfiltered) images inside a merged PDF as JPEG (US-16,
BR-IMGCOMP-01..04).

Design source: `docs/Architecture.md` "US-16 — Nen anh sau khi ghep
(`compress_pdf_images`)" (S1-S10), verified against real PyMuPDF 1.28.2
behaviour and a real 415-page production job (846.79 MB -> 19.34 MB), not
written from memory.

Deliberately NOT using `Document.extract_image()` / `Page.replace_image()`
(Architecture.md S4): `extract_image()` decodes into an image format, which
would need Pillow to re-encode — Pillow is not installed in this project's
`.venv`. Going through `Document`-level xref APIs plus
`pymupdf.Pixmap(doc, xref).tobytes("jpeg", ...)` needs no extra dependency.

Dedupe (BR-IMGCOMP-04's conditional acceptance criterion) is explicitly OUT
of scope: a real spike on the production file measured redundant-byte savings
at 4.2% of post-JPEG image bytes, below the 20% threshold (Architecture.md
S3). Do not add it back without a fresh measurement.
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF — matches src/postprocess/chunk_merge.py's existing import

logger = logging.getLogger(__name__)

_COLORSPACE_BY_CHANNELS = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}


@dataclass
class ImageCompressStats:
    """Stats for logging/tests only — never persisted to DB or shown in UI."""

    images_scanned: int = 0
    images_recompressed: int = 0
    images_skipped_already_compressed: int = 0
    images_skipped_larger: int = 0
    images_skipped_unsupported: int = 0
    size_before: int = 0
    size_after: int = 0


async def compress_pdf_images(
    pdf_path: str | Path, *, jpeg_quality: int = 85
) -> ImageCompressStats:
    """Re-encode every raw (`Filter: null`) image xref in `pdf_path` as JPEG,
    overwriting the file in place.

    `jpeg_quality` is keyword-only and defaults to 85 (BR-IMGCOMP-03) — it
    exists so tests can parametrize it, not as a user/Settings-facing knob.

    Images that already carry a filter (`DCTDecode`, `CCITTFaxDecode`, ...)
    are left untouched (BR-IMGCOMP-02: no double-compression). Images with
    `/SMask` (alpha) or `/ImageMask` (stencil mask) are skipped rather than
    recompressed — JPEG cannot represent either losslessly and no real sample
    of either has been observed yet (Architecture.md S6/S10, `[UNVERIFIED]`
    but safe-by-default).
    """
    pdf_path = Path(pdf_path)
    stats = ImageCompressStats(size_before=pdf_path.stat().st_size)

    doc = fitz.open(pdf_path)
    try:
        # info[0]=xref, info[1]=smask xref (Architecture.md S1: NOT info[8],
        # which is the filter name and easy to confuse with the smask slot).
        # An xref can repeat across pages (same image reused) — first sighting
        # of its smask value wins, since it describes the xref object itself.
        smask_by_xref: dict[int, int] = {}
        for pno in range(doc.page_count):
            for info in doc.get_page_images(pno, full=True):
                smask_by_xref.setdefault(info[0], info[1])

        stats.images_scanned = len(smask_by_xref)

        for xref, smask_xref in smask_by_xref.items():
            try:
                filter_type, _filter_value = doc.xref_get_key(xref, "Filter")
                if filter_type != "null":
                    stats.images_skipped_already_compressed += 1
                    continue

                mask_type, mask_value = doc.xref_get_key(xref, "ImageMask")
                if mask_type != "null" and mask_value == "true":
                    logger.warning(
                        "compress_pdf_images: skipping xref %s — /ImageMask "
                        "stencil mask cannot be safely re-encoded as JPEG",
                        xref,
                    )
                    stats.images_skipped_unsupported += 1
                    continue

                if smask_xref:
                    logger.warning(
                        "compress_pdf_images: skipping xref %s — has /SMask "
                        "(alpha channel), JPEG cannot represent it",
                        xref,
                    )
                    stats.images_skipped_unsupported += 1
                    continue

                raw_size = len(doc.xref_stream_raw(xref))

                pix = fitz.Pixmap(doc, xref)
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)

                jpeg_bytes = pix.tobytes("jpeg", jpg_quality=jpeg_quality)

                if len(jpeg_bytes) >= raw_size:
                    stats.images_skipped_larger += 1
                    continue

                doc.update_stream(xref, jpeg_bytes, new=1, compress=0)
                doc.xref_set_key(xref, "Filter", "/DCTDecode")
                doc.xref_set_key(xref, "BitsPerComponent", "8")
                doc.xref_set_key(
                    xref, "ColorSpace", _COLORSPACE_BY_CHANNELS.get(pix.n, "/DeviceGray")
                )
                doc.xref_set_key(xref, "Width", str(pix.width))
                doc.xref_set_key(xref, "Height", str(pix.height))

                stats.images_recompressed += 1
            except Exception:
                logger.warning(
                    "compress_pdf_images: skipping xref %s after error", xref, exc_info=True
                )
                stats.images_skipped_unsupported += 1

        fd, tmp_name = tempfile.mkstemp(
            dir=str(pdf_path.parent), prefix=f".{pdf_path.stem}-", suffix=".tmp.pdf"
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            doc.save(tmp_path, garbage=4, deflate=True)
        finally:
            doc.close()
        os.replace(tmp_path, pdf_path)
    except Exception:
        if not doc.is_closed:
            doc.close()
        raise

    stats.size_after = pdf_path.stat().st_size
    return stats
