"""Script do spike 7.4-a (Bug #7 Ca C, TOC-1 v2) — Architecture.md AA8 buoc
3+4. KHONG dep, mien chay dung (AA8: "khong can dep").

Chay tren 11 fixture (8 da commit vao tests/fixtures/babeldoc/toc_*.json.gz +
3 fixture hoi quy dung lai tu fixture da co / tu artifact tam /tmp/bdprobe
chua commit trong spike nay — xem PATHS ben duoi) va in bang doi chieu voi
oracle AA7 + cac counter AA8 buoc 3 (blocked_by_monotonic, blocked_by_fraction,
fired_inside_table_box) + do rieng luat noi dong AA8 buoc 4.

Goi DUNG logic production `src.babeldoc_shim.toc_split.evaluate_paragraph`
(Protocol 6 R6-02) — script nay CHI lam viec doc field tu dump JSON
(`paragraph_finder.json` cua babeldoc 0.6.4) roi chuyen thanh cac kieu du
lieu thuan (`TocChar`, tuple toa do) ma module do nhan vao; KHONG tu viet
lai bat ky phan nao cua thuat toan quyet dinh tach.

Chay: `uv run python scripts/toc_split_spike_measure.py`
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.babeldoc_shim.toc_split import (
    REASON_LOW_FRACTION,
    REASON_NOT_MONOTONIC,
    ParagraphSplitResult,
    TocChar,
    evaluate_paragraph,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "babeldoc"

# 8 fixture moi cua spike nay (da gzip + commit, AA8 buoc 1).
_TOC_SPIKE_FIXTURES: dict[str, Path] = {
    "figoni_p7_toc": _FIXTURES_DIR / "toc_figoni_contents_p7_dump.json.gz",
    "figoni_p8_toc": _FIXTURES_DIR / "toc_figoni_contents_p8_dump.json.gz",
    "lcb_toc": _FIXTURES_DIR / "toc_lcb_contents_p6_p7_dump.json.gz",
    "friberg_toc": _FIXTURES_DIR / "toc_friberg_contents_dump.json.gz",
    "lcb_index": _FIXTURES_DIR / "toc_lcb_index_dump.json.gz",
    "figoni_p25_recipe": _FIXTURES_DIR / "toc_figoni_p25_recipe_dump.json.gz",
    "figoni_p45_recipe": _FIXTURES_DIR / "toc_figoni_p45_recipe_dump.json.gz",
    "figoni_p7_tables": _FIXTURES_DIR / "toc_figoni_tables_dump.json.gz",
}

# 3 fixture hoi quy con lai cua oracle AA7. p74_77/page14 da co san duoi dang
# fixture da commit TU TRUOC (buoc 7.1/7.2, khong phai cua spike nay). figoni
# p20/p22 CHUA duoc commit (AA8 buoc 1 chi liet ke dung 8 file o tren) — doc
# tam tu artifact /tmp/bdprobe con song (kiem tra 2026-09-08) CHI de do hoi
# quy trong spike nay, KHONG phu thuoc lau dai vao duong dan nay.
_REGRESSION_FIXTURES: dict[str, Path] = {
    "p74_77": _FIXTURES_DIR / "paragraph_finder_p74_77_post71_dump.json.gz",
    "page14_numbered_list_source": _FIXTURES_DIR
    / "paragraph_finder_numbered_list_post71_dump.json.gz",
}
_REGRESSION_FIXTURES_PLAIN: dict[str, Path] = {
    "figoni_p20": Path("/tmp/bdprobe/wd_p20/figoni_p20/paragraph_finder.json"),
    "figoni_p22": Path("/tmp/bdprobe/wd_p22/figoni_p22/paragraph_finder.json"),
}

_NON_TOC_FIXTURE_NAMES = {
    "friberg_toc",
    "lcb_index",
    "figoni_p25_recipe",
    "figoni_p45_recipe",
    "figoni_p7_tables",
    "p74_77",
    "page14_numbered_list_source",
    "figoni_p20",
    "figoni_p22",
}


def _load_gzip_json(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _load_plain_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _char_to_tocchar(char: dict) -> TocChar:
    box = char["visual_bbox"]["box"]
    return TocChar(
        x=box["x"],
        x2=box["x2"],
        unicode=char["char_unicode"] or "",
        font_size=(char.get("pdf_style") or {}).get("font_size") or 0.0,
    )


def _paragraph_line_chars(paragraph: dict) -> list[list[TocChar] | None]:
    out: list[list[TocChar] | None] = []
    for comp in paragraph["pdf_paragraph_composition"]:
        line = comp.get("pdf_line")
        if line is None:
            out.append(None)
            continue
        out.append([_char_to_tocchar(c) for c in line["pdf_character"]])
    return out


def _paragraph_box(paragraph: dict) -> tuple[float, float, float, float] | None:
    box = paragraph.get("box")
    if not box:
        return None
    return (box["x"], box["y"], box["x2"], box["y2"])


def _table_boxes(page: dict) -> list[tuple[float, float, float, float]]:
    boxes = []
    for entry in page.get("page_layout") or []:
        if (entry.get("class_name") or "").strip().lower() != "table":
            continue
        b = entry["box"]
        boxes.append((b["x"], b["y"], b["x2"], b["y2"]))
    return boxes


def evaluate_dump(dump: dict) -> tuple[list[ParagraphSplitResult], list[dict]]:
    """Tra ve (results, debug_rows) — debug_rows chi de in ranh gioi buoc 4."""
    results: list[ParagraphSplitResult] = []
    debug_rows: list[dict] = []
    for page in dump["page"]:
        table_boxes = _table_boxes(page)
        for paragraph in page["pdf_paragraph"]:
            line_chars = _paragraph_line_chars(paragraph)
            result = evaluate_paragraph(
                paragraph.get("layout_label"),
                line_chars,
                paragraph_box=_paragraph_box(paragraph),
                table_boxes=table_boxes,
            )
            results.append(result)
            if result.fired:
                debug_rows.append(
                    {
                        "page_number": page.get("page_number"),
                        "tail_marks": result.tail_marks,
                        "composition_count": result.composition_count,
                        "cut_after": result.cut_after,
                        "inside_table_box": result.inside_table_box,
                        "continuation_boundaries": result.continuation_boundaries,
                    }
                )
    return results, debug_rows


def summarize(name: str, results: list[ParagraphSplitResult]) -> dict:
    fired = [r for r in results if r.fired]
    fire = len(fired)
    cuts = sum(len(r.cut_after) for r in fired)
    blocked_by_monotonic = sum(1 for r in results if r.reason == REASON_NOT_MONOTONIC)
    blocked_by_fraction = sum(1 for r in results if r.reason == REASON_LOW_FRACTION)
    fired_inside_table_box = sum(1 for r in fired if r.inside_table_box)
    return {
        "name": name,
        "fire": fire,
        "cuts": cuts,
        "blocked_by_monotonic": blocked_by_monotonic,
        "blocked_by_fraction": blocked_by_fraction,
        "fired_inside_table_box": fired_inside_table_box,
    }


def main() -> int:
    print("=== AA8 buoc 3 — bang doi chieu voi oracle AA7 ===")
    header = (
        f"{'fixture':28s} {'fire':>5s} {'cuts':>5s} {'blk_mono':>9s} "
        f"{'blk_frac':>9s} {'fired_in_table':>15s}"
    )
    print(header)
    print("-" * len(header))

    all_summaries: list[dict] = []
    all_boundaries: list[tuple[str, dict]] = []

    for name, path in _TOC_SPIKE_FIXTURES.items():
        dump = _load_gzip_json(path)
        results, debug_rows = evaluate_dump(dump)
        summary = summarize(name, results)
        all_summaries.append(summary)
        for row in debug_rows:
            for boundary in row["continuation_boundaries"]:
                all_boundaries.append((name, boundary))

    for name, path in _REGRESSION_FIXTURES.items():
        dump = _load_gzip_json(path)
        results, _debug_rows = evaluate_dump(dump)
        all_summaries.append(summarize(name, results))

    for name, path in _REGRESSION_FIXTURES_PLAIN.items():
        if not path.exists():
            print(f"[CANH BAO] khong tim thay {path} — bo qua fixture hoi quy {name}")
            continue
        dump = _load_plain_json(path)
        results, _debug_rows = evaluate_dump(dump)
        all_summaries.append(summarize(name, results))

    for s in all_summaries:
        print(
            f"{s['name']:28s} {s['fire']:5d} {s['cuts']:5d} "
            f"{s['blocked_by_monotonic']:9d} {s['blocked_by_fraction']:9d} "
            f"{s['fired_inside_table_box']:15d}"
        )

    total_fire = sum(s["fire"] for s in all_summaries)
    total_cuts = sum(s["cuts"] for s in all_summaries)
    total_fp = sum(s["fire"] for s in all_summaries if s["name"] in _NON_TOC_FIXTURE_NAMES)
    print("-" * len(header))
    print(f"TONG fire={total_fire} cuts={total_cuts}  (oracle AA7: 31 / 130)")
    print(f"TONG false-positive tren fixture KHONG phai muc luc: {total_fp}  (oracle: 0)")

    print()
    print("=== AA8 buoc 4 — ranh gioi 'danh dau -> khong danh dau' + delta thut dau dong ===")
    print(f"So ranh gioi tim thay: {len(all_boundaries)}  (ky vong theo AA1/AA8: 6)")
    for fixture_name, boundary in all_boundaries:
        print(
            f"  [{fixture_name}] marked_idx={boundary.marked_index} "
            f"next_idx={boundary.next_index} indent_delta={boundary.indent_delta:+.2f}pt "
            f"extended={boundary.extended}"
        )
    deltas = [b.indent_delta for _n, b in all_boundaries]
    any_extended = any(b.extended for _n, b in all_boundaries)
    if deltas:
        print(f"  min={min(deltas):+.2f}pt max={max(deltas):+.2f}pt")
    print(f"  co bat ky ranh gioi nao duoc 'extended' (gop group) khong? {any_extended}")
    print("  (ky vong theo AA9 dieu kien 4: KHONG co ranh gioi nao duoc gop -> luat la no-op)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
