"""BL-04 live E2E fallback (b) (Architecture.md 6.22.9 "Nếu không tái hiện được").

Chunk 5 (`--pages 199-240`) did NOT reproduce the channel-(1) drop this run
(see `scripts/bl04_live_e2e_chunk5.py` output, 2026-09-11: `unfit_drops=0`,
even though the real feuilletage sidebar IS confirmed missing from the real
translated output — that's channel (2)/BL-08, out of BL-04's scope, not this
mechanism). Per Architecture.md's explicit fallback (b): "dựng tài liệu ép
drop sao chép đúng hình học đã đo" — NOT a fabricated test case, a geometric
copy of the real trang 230 box (61.5, 223.6, 332.3, 466.6 -> 271x243pt) and
the real 614-char EN sidebar text, standalone on 1 page (no averaging against
41 other pages' `optimal_scale` mode, so this is a distinct, weaker claim
than "reproduces job 1ee1fdee exactly" -- it only tests "can the shim/sidecar
mechanism capture a REAL babeldoc drop when one genuinely happens", closing
the one part of R5-03/R6-03 chunk 5 didn't verify live).
"""

import asyncio
import json
import logging
from pathlib import Path

import fitz

from src.core.config import Settings
from src.services.babeldoc_runner import BabeldocRunner
from src.services.pdf2zh_service_map import Pdf2zhServiceMapper

logging.basicConfig(level=logging.INFO)

WORK_DIR = Path("data/bl04_live_e2e_synth")
SIDEBAR_TEXT = (
    "The term feuilletage appeared in the 15th century and some attribute its "
    "invention to Feuillet, the pâtissier to the Marshall of Conde. Others "
    "believe it was the painter Claude Le Lorrain, while some give Catherine de "
    "Médicis the credit. There are many stories that attribute the invention "
    "of pâte feuilletée either by accident or design, but its roots can be "
    "traced back to the ancient Greeks who made a flaky pastry using oil. The "
    "individuals cited above perhaps didn't invent it, but they certainly "
    "popularized it during the 17th and 18th centuries, including Carême who "
    "innovated the fifth turn of the dough!"
)
BOX = fitz.Rect(61.5, 223.6, 332.3, 466.6)  # 271 x 243 pt, measured from page 230


def _make_source() -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    source = WORK_DIR / "source.pdf"
    doc = fitz.open()
    page = doc.new_page(width=648, height=783)  # same as real page 230 mediabox
    page.insert_textbox(BOX, SIDEBAR_TEXT, fontsize=12, fontname="Times-Roman")
    doc.save(source)
    doc.close()
    return source


async def main() -> None:
    source = _make_source()
    settings = Settings(pdf_translate_engine="babeldoc")
    assert settings.deepseek_api_key, "DEEPSEEK_API_KEY not configured"
    service = Pdf2zhServiceMapper().map("deepseek", settings)
    runner = BabeldocRunner()

    print(f"source={source}, starting translate_pages(page_range='1-1') ...")
    result = await runner.translate_pages(
        input_path=source,
        output_dir=WORK_DIR / "output",
        page_range="1-1",
        service=service,
        lang_out="vi",
    )
    print(f"success={result.success} mono_path={result.mono_path}")
    dr = result.drop_report
    print(
        f"drop_report.available={dr.available} observed_pages={sorted(dr.observed_pages)} "
        f"page_dropped_counts={dr.page_dropped_counts} header_count={dr.header_count} "
        f"malformed_line_count={dr.malformed_line_count}"
    )
    for d in dr.dropped:
        print(
            f"DROPPED: page={d.page_number} debug_id={d.debug_id} text_excerpt={d.text_excerpt!r}"
        )

    with fitz.open(result.mono_path) as out_doc:
        text = out_doc[0].get_text()
        print(f"\n=== translated output page text ({len(text)} chars) ===\n{text}")

    (WORK_DIR / "drop_report_result.json").write_text(
        json.dumps(
            {
                "available": dr.available,
                "observed_pages": sorted(dr.observed_pages),
                "page_dropped_counts": dr.page_dropped_counts,
                "dropped": [
                    {
                        "page_number": d.page_number,
                        "debug_id": d.debug_id,
                        "text_excerpt": d.text_excerpt,
                        "text_len": d.text_len,
                    }
                    for d in dr.dropped
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
