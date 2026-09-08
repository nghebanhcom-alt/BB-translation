"""Re-encode raw and lossless-Flate images inside a merged PDF as JPEG (US-16
v1+v2, BR-IMGCOMP-01..04).

Design source: `docs/Architecture.md` "US-16 v2 — Final Decision sau phản
biện Domain Expert (2026-09-08)", section W6 (algorithm, 13 steps) + W7
(signature/stats) — that section SUPERSEDES steps 4a/4b/4d/7 of the earlier
"US-16 v2" draft (section V5) and the whole V9.1 section; W6 is what this
file implements, not a hand-merge of V5 + the Final Decision diffs. v1
(Architecture.md "US-16 — Nen anh sau khi ghep", S1-S10) is still the base
algorithm for everything W6 doesn't change, verified against a real 415-page
production job (846.79 MB -> 19.34 MB).

Deliberately NOT using `Document.extract_image()` / `Page.replace_image()`
(Architecture.md S4): `extract_image()` decodes into an image format, which
would need Pillow to re-encode — Pillow is not installed in this project's
`.venv`. Going through `Document`-level xref APIs plus
`pymupdf.Pixmap(doc, xref).tobytes("jpeg", ...)` needs no extra dependency.

Dedupe (BR-IMGCOMP-04's conditional acceptance criterion) is explicitly OUT
of scope: a real spike on the production file measured redundant-byte savings
at 4.2% of post-JPEG image bytes, below the 20% threshold (Architecture.md
S3). Do not add it back without a fresh measurement.

v2 changes vs. v1 (BR-IMGCOMP-02b/02c), all verified live on real production
jobs (Architecture.md V1-V11, X1-X10, W0-W10):

- Eligibility (step 3) widened: `Filter: null` (raw) OR `/FlateDecode`
  (lossless zlib) are both re-encode candidates now — Flate is lossless, so
  with photographic content it barely shrinks anything (measured: one real
  image was LARGER Flate-compressed than its raw bitmap). `/DCTDecode`,
  `/CCITTFaxDecode`, `/JPXDecode`, `/JBIG2Decode` (and, deliberately left
  out — 0 real sample, `[UNVERIFIED]` — `/LZWDecode`, `/RunLengthDecode`)
  are untouched, same as v1's "no double compression" guarantee.
- Colorspace guard (step 7) reads `info[5]` (the PDF dict's own colorspace
  *family* name, from `Document.get_page_images(pno, full=True)`) instead of
  `Pixmap.colorspace.name`. `Pixmap.colorspace.name` is USELESS as a guard
  here: PyMuPDF expands `Indexed` images to their base colorspace the moment
  a `Pixmap` is built, so it never reports `'Indexed(...)'` — a guard
  written against it is dead code for the exact case BR-IMGCOMP-02c promises
  to protect (verified live: 2 real `Indexed` images from a real job
  silently slipped through and got JPEG-encoded before this fix). `info[5]`
  is read straight from the object dict and is unaffected by that
  expansion. It also does NOT carry PyMuPDF's `"ICCBased(...)"` decoration
  (that was a trap during the v2 spike — a naive `name in {...}` allowlist
  against `Pixmap.colorspace.name` rejected 19/19 images that needed
  compressing).
- No longer overwrites `/ColorSpace` after re-encoding (used to hard-code
  `/DeviceGray|/DeviceRGB|/DeviceCMYK` by channel count) — that discarded
  the original ICC profile. Invisible to MuPDF's own renderer (it
  substitutes its own default profile for the same family, so a MuPDF-vs-
  MuPDF pixel diff reads 0.00) but IS visible on other viewers: measured
  4.4-7.0/255 mean pixel diff on macOS Preview/Quartz for a `/ColorSpace`
  overwrite alone, with Flate untouched and no JPEG involved. The two fixes
  are coupled BY DESIGN: the colorspace ALLOWLIST (step 7) and NOT
  overwriting `/ColorSpace` (step 11) must ship together. Dropping the
  overwrite without the allowlist would let an `Indexed` image slip through,
  get JPEG-encoded, while `/ColorSpace` still says `[/Indexed ...]` — each
  output byte would then be read as a palette index into JPEG CMYK/RGB
  samples, a broken PDF, worse than the current merely-lossy bug.
- `/Decode` is explicitly cleared after re-encoding (step 12) if present and
  non-identity. `Pixmap(doc, xref)` APPLIES `/Decode` when decoding, but
  `update_stream()` does NOT remove the key afterwards — leaving it in place
  would apply the same transform a SECOND time on every future render
  (negative image). This bug is latent in v1 for any `Filter: null` image
  with a non-identity `/Decode`; fixing it is independent of the v2
  Flate-scope decision.
- New guard: `/Mask` (color-key array or a ref to a stencil mask) is treated
  the same as `/SMask`/`/ImageMask` — skipped, not recompressed. v1 left
  `/Mask` unguarded, so `update_stream()` would keep it applied on top of
  sample values that had just changed underneath it.
- New guard: a `Pixmap` that still reports `pix.alpha` after the
  SMask/ImageMask/Mask checks above is SKIPPED, not alpha-dropped (v1 used
  to strip it with `fitz.Pixmap(pix, 0)`) — in this pipeline alpha can only
  legitimately come from `/SMask` or `/Mask`, both already guarded above, so
  surviving alpha means an unrecognized source; dropping it silently would
  both lose information and leave whatever PDF key produced it untouched.
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import fitz  # PyMuPDF — matches src/postprocess/chunk_merge.py's existing import

logger = logging.getLogger(__name__)

# Architecture.md W1: allowlist on the PDF dict's OWN colorspace family name
# (`info[5]` from `get_page_images(..., full=True)`), read BEFORE building a
# Pixmap — NOT `Pixmap.colorspace.name`, which MuPDF rewrites for `Indexed`
# images (expanded to their base colorspace) and decorates for `ICCBased`
# (e.g. `'ICCBased(CMYK,Artifex CMYK SWOP Profile)'`), making it useless as
# an allowlist key for either case. See module docstring / Architecture.md
# C1, W1, X2.
_ELIGIBLE_CS_FAMILIES = frozenset({"DeviceGray", "DeviceRGB", "DeviceCMYK", "ICCBased"})

# Layer-two consistency check (Architecture.md W1): the decoded Pixmap's
# channel count must match what `cs_family` implies. `ICCBased` doesn't
# encode N in `info[5]`, so any of 1/3/4 is accepted for it.
_EXPECTED_CHANNELS_BY_CS_FAMILY: dict[str, frozenset[int]] = {
    "DeviceGray": frozenset({1}),
    "DeviceRGB": frozenset({3}),
    "DeviceCMYK": frozenset({4}),
    "ICCBased": frozenset({1, 3, 4}),
}

# Filter names of dedicated image codecs — never eligible for re-encoding,
# whether `/Filter` is a plain name or (rare, [UNVERIFIED]) part of an array
# alongside `/FlateDecode` (Architecture.md W6 step 3).
_ALREADY_COMPRESSED_IMAGE_FILTERS = (
    "DCTDecode",
    "JPXDecode",
    "JBIG2Decode",
    "CCITTFaxDecode",
)


class _ImageMeta(NamedTuple):
    """Per-xref metadata gathered once from `get_page_images(..., full=True)`
    (Architecture.md W1) — `smask`=info[1], `bpc`=info[4], `cs_family`=info[5].
    """

    smask: int
    bpc: int
    cs_family: str


@dataclass
class ImageCompressStats:
    """Stats for logging/tests only — never persisted to DB or shown in UI."""

    images_scanned: int = 0
    images_recompressed: int = 0
    images_skipped_already_compressed: int = 0
    images_skipped_larger: int = 0
    images_skipped_unsupported: int = 0
    images_skipped_small: int = 0
    images_skipped_colorspace: int = 0
    size_before: int = 0
    size_after: int = 0


async def compress_pdf_images(
    pdf_path: str | Path, *, jpeg_quality: int = 85, min_recompress_bytes: int = 4096
) -> ImageCompressStats:
    """Re-encode every raw (`Filter: null`) or lossless-Flate (`/FlateDecode`)
    image xref in `pdf_path` as JPEG, overwriting the file in place.

    `jpeg_quality` and `min_recompress_bytes` are keyword-only and exist so
    tests can parametrize them, not as user/Settings-facing knobs
    (BR-IMGCOMP-03 fixes quality=85; `min_recompress_bytes` has no `.env`/UI
    equivalent — Architecture.md W7).

    Images that already carry a dedicated image codec (`DCTDecode`,
    `CCITTFaxDecode`, `JPXDecode`, `JBIG2Decode`) are left untouched
    (BR-IMGCOMP-02/02b: no double-compression). Images with `/SMask` (alpha),
    `/ImageMask` (stencil mask), or `/Mask` (color-key array or stencil ref)
    are skipped rather than recompressed — JPEG cannot represent any of them
    losslessly (Architecture.md W3). Images below `min_recompress_bytes`,
    with `BitsPerComponent != 8`, or outside the Gray/RGB/CMYK/ICCBased
    colorspace allowlist are skipped too (BR-IMGCOMP-02c, Architecture.md
    W1/W6).
    """
    pdf_path = Path(pdf_path)
    stats = ImageCompressStats(size_before=pdf_path.stat().st_size)

    doc = fitz.open(pdf_path)
    try:
        # W6 step 2: gather (smask, bpc, cs_family) per xref in one pass —
        # info[0]=xref, info[1]=smask xref, info[4]=bpc (int, pre-resolved),
        # info[5]=colorspace family name (bare, e.g. 'ICCBased', NOT
        # Pixmap.colorspace.name's decorated 'ICCBased(...)' form — verified
        # live, Architecture.md W0). An xref can repeat across pages (same
        # image reused) — first sighting wins, since info describes the xref
        # object itself, not where it's placed on a page (unchanged from v1).
        meta_by_xref: dict[int, _ImageMeta] = {}
        for pno in range(doc.page_count):
            for info in doc.get_page_images(pno, full=True):
                meta_by_xref.setdefault(
                    info[0], _ImageMeta(smask=info[1], bpc=info[4], cs_family=info[5])
                )

        stats.images_scanned = len(meta_by_xref)

        for xref, meta in meta_by_xref.items():
            try:
                # W6 step 3: eligibility — raw or lossless-Flate only.
                filter_type, filter_value = doc.xref_get_key(xref, "Filter")
                if filter_type == "null":
                    eligible = True
                elif filter_type == "name":
                    eligible = filter_value == "/FlateDecode"
                elif filter_type == "array":
                    # [UNVERIFIED] (Architecture.md W6 step 3) — 0 real
                    # sample of an array Filter containing FlateDecode in
                    # any job surveyed. Safe by construction: a non-match
                    # falls through to "already compressed, skip" below.
                    # PyMuPDF's array value has NO spaces between names
                    # (e.g. "[/ASCIIHexDecode/FlateDecode]") — substring
                    # check, not value.split().
                    eligible = "FlateDecode" in filter_value and not any(
                        codec in filter_value for codec in _ALREADY_COMPRESSED_IMAGE_FILTERS
                    )
                else:
                    eligible = False

                if not eligible:
                    stats.images_skipped_already_compressed += 1
                    continue

                # W6 step 4: mask/alpha guards. All 3 logged at warning —
                # rare on real data (0 samples across every job surveyed so
                # far, Architecture.md W9), so a hit is worth surfacing.
                mask_type, mask_value = doc.xref_get_key(xref, "ImageMask")
                if mask_type != "null" and mask_value == "true":
                    logger.warning(
                        "compress_pdf_images: skipping xref %s — /ImageMask "
                        "stencil mask cannot be safely re-encoded as JPEG",
                        xref,
                    )
                    stats.images_skipped_unsupported += 1
                    continue

                if meta.smask:
                    logger.warning(
                        "compress_pdf_images: skipping xref %s — has /SMask "
                        "(alpha channel), JPEG cannot represent it",
                        xref,
                    )
                    stats.images_skipped_unsupported += 1
                    continue

                mask_key_type, _mask_key_value = doc.xref_get_key(xref, "Mask")
                if mask_key_type != "null":
                    logger.warning(
                        "compress_pdf_images: skipping xref %s — has /Mask "
                        "(color-key or stencil mask reference), JPEG cannot "
                        "represent it",
                        xref,
                    )
                    stats.images_skipped_unsupported += 1
                    continue

                # W6 step 5: cheap size guard BEFORE building a Pixmap — also
                # sidesteps PyMuPDF raising on tiny 1x1 /Separation swatches
                # (Architecture.md C2), since real sub-4KB images in the
                # surveyed jobs are all tiny (<100 bytes). Cost+noise guard,
                # not a correctness guard (that's step 10) — threshold stays
                # 4096 because the total bytes it could ever reclaim across
                # 6 real jobs was ~0.08 MiB (Architecture.md W5), not because
                # "nothing real" lives below it.
                raw_size = len(doc.xref_stream_raw(xref))
                if raw_size < min_recompress_bytes:
                    stats.images_skipped_small += 1
                    logger.debug(
                        "compress_pdf_images: skipping xref %s — %d raw bytes "
                        "< min_recompress_bytes=%d",
                        xref,
                        raw_size,
                        min_recompress_bytes,
                    )
                    continue

                # W6 step 6: bit depth, read from pre-resolved info[4] (int),
                # not xref_get_key (which returns ('xref', 'N 0 R') for an
                # indirect BitsPerComponent and would silently skip nothing
                # instead of skipping the image — Architecture.md W1).
                if meta.bpc != 8:
                    stats.images_skipped_unsupported += 1
                    logger.debug(
                        "compress_pdf_images: skipping xref %s — "
                        "BitsPerComponent=%s != 8 (bilevel/scan line art — "
                        "JPEG both loses quality and often grows the file)",
                        xref,
                        meta.bpc,
                    )
                    continue

                # W6 step 7: colorspace allowlist on the PDF dict's OWN
                # family name, BEFORE building a Pixmap — see module
                # docstring for why `Pixmap.colorspace.name` cannot do this.
                if meta.cs_family not in _ELIGIBLE_CS_FAMILIES:
                    stats.images_skipped_colorspace += 1
                    logger.debug(
                        "compress_pdf_images: skipping xref %s — colorspace "
                        "family %r not in allowlist",
                        xref,
                        meta.cs_family,
                    )
                    continue

                # W6 step 8: build Pixmap. Any surviving alpha means an
                # unrecognized source (SMask/ImageMask/Mask are already
                # guarded above) — skip rather than drop it (v1 used to
                # strip it with `Pixmap(pix, 0)`, leaving whatever PDF key
                # produced it untouched in the dict).
                pix = fitz.Pixmap(doc, xref)
                if pix.alpha:
                    logger.warning(
                        "compress_pdf_images: skipping xref %s — Pixmap "
                        "reports alpha with no /SMask, /ImageMask or /Mask "
                        "guard hit; unrecognized source, refusing to drop "
                        "it silently",
                        xref,
                    )
                    stats.images_skipped_unsupported += 1
                    continue

                # Layer two (Architecture.md W1): channel count must match
                # what cs_family implies, or the allowlist match for this
                # xref isn't trusted.
                if pix.n not in _EXPECTED_CHANNELS_BY_CS_FAMILY[meta.cs_family]:
                    stats.images_skipped_colorspace += 1
                    logger.debug(
                        "compress_pdf_images: skipping xref %s — pix.n=%d "
                        "doesn't match colorspace family %r",
                        xref,
                        pix.n,
                        meta.cs_family,
                    )
                    continue

                # W6 step 9.
                jpeg_bytes = pix.tobytes("jpeg", jpg_quality=jpeg_quality)
                logger.debug(
                    "compress_pdf_images: xref %s — raw Flate compression "
                    "ratio %.3f (raw_size / (w*h*n)) — a low ratio here "
                    "flags a candidate flat-graphic outlier for QA/Reviewer "
                    "to eyeball (Architecture.md X7.3)",
                    xref,
                    raw_size / (pix.width * pix.height * pix.n),
                )

                # W6 step 10: the one correctness-relevant guard — if JPEG
                # comes out bigger, this wasn't a photo, leave it alone.
                if len(jpeg_bytes) >= raw_size:
                    stats.images_skipped_larger += 1
                    continue

                # W6 step 11: write results. Deliberately NOT setting
                # /ColorSpace anymore — see module docstring (W2/W2.2): this
                # is safe ONLY because steps 7 and this line ship together.
                doc.update_stream(xref, jpeg_bytes, new=1, compress=0)
                doc.xref_set_key(xref, "Filter", "/DCTDecode")
                doc.xref_set_key(xref, "BitsPerComponent", "8")
                doc.xref_set_key(xref, "Width", str(pix.width))
                doc.xref_set_key(xref, "Height", str(pix.height))

                # W6 step 12: clear /Decode if present and non-identity —
                # Pixmap already applied it once when decoding above;
                # leaving the key would apply it a SECOND time on every
                # future render (Architecture.md V4.4/C4 — negative image).
                # Only set when the key already exists — setting it
                # unconditionally would add `/Decode null` to every
                # re-encoded image and shift existing fixtures by a few
                # bytes for no reason.
                decode_type, _decode_value = doc.xref_get_key(xref, "Decode")
                if decode_type != "null":
                    doc.xref_set_key(xref, "Decode", "null")

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
