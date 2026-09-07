"""Thuat toan tach dong thuan (khong phu thuoc babeldoc), dung chung boi
`sitecustomize.py` (patch that su, chay trong subprocess babeldoc) VA test
(`tests/test_babeldoc_line_split_shim.py`, chay trong process app, KHONG can
babeldoc cai san — Protocol 6 R6-02: test phai goi dung logic production,
khong duoc chep tay lai thuat toan roi test ban chep).

Sao y logic goc cua `ParagraphFinder._split_paragraph_into_lines` (babeldoc
0.6.4, `paragraph_finder.py:652-776`) + fix Bug #7 (Architecture.md X5 D7-1):
loai ky tu khoang trang khoi PHEP DEM va cham dung de tim khe giua 2 dong,
GIU NGUYEN nguong goc `count < 1`. Ky tu khoang trang van duoc gan vao dung
dong cua no theo tam y nhu binh thuong o buoc gan dong cuoi cung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CharBound:
    """Bien gioi doc hieu qua (effective y-bounds) cua 1 ky tu, cung co la no
    co phai khoang trang hay khong (dung de loai khoi phep dem va cham)."""

    y1: float
    y2: float
    is_space: bool


def _compute_collision_counts_histogram(
    y1_list: list[float],
    y2_list: list[float],
    para_y_min: float,
    para_y_max: float,
    step: float,
) -> list[int]:
    """Cung mot phep toan voi `ParagraphFinder._compute_collision_counts_histogram`
    goc cua babeldoc (difference-array histogram: moi ky tu cong 1 phieu tai
    diem bat dau, tru 1 phieu tai diem ket thuc, roi cumsum) — viet lai bang
    Python thuan (khong numpy) de module nay khong keo them dependency nang
    vao app (`line_split.py` duoc import ca trong test cua app LAN trong
    subprocess babeldoc — subprocess da co san numpy qua chinh babeldoc, con
    app thi khong can). Cung phep toan tren tap du lieu nho (vai tram ky tu
    moi paragraph) nen ket qua giong het, chi khac cach thuc thi.
    """
    m = math.ceil((para_y_max - para_y_min) / step)
    if m <= 0:
        return []

    hist = [0] * (m + 1)
    for y1, y2 in zip(y1_list, y2_list):
        start = math.floor((para_y_max - y2) / step)
        end = math.floor((para_y_max - y1) / step) + 1
        end = max(0, min(end, m))
        start = max(0, min(start, m))
        hist[start] += 1
        hist[end] -= 1

    counts: list[int] = []
    running = 0
    for delta in hist[:-1]:
        running += delta
        counts.append(running)
    return counts


def split_into_line_groups(bounds: list[CharBound], step: float = 0.25) -> list[list[int]]:
    """Tra ve danh sach cac nhom chi so (index vao `bounds`), moi nhom la 1
    dong, theo THU TU TU TREN XUONG DUOI — dung logic threading-scan goc cua
    babeldoc, CHI khac o cho: phep dem va cham (buoc 3) loai bo ky tu khoang
    trang (Bug #7 fix, X5 D7-1). Buoc gan ky tu vao dong (buoc 5) van dung
    DAY DU danh sach `bounds` (bao gom ca khoang trang) — khong mat noi dung.

    Ham nay khong biet gi ve `PdfCharacter`/babeldoc — chi lam viec tren cac
    con so y1/y2/is_space thuan tuy, de co the test doc lap khong can cai
    babeldoc (Protocol 6 R6-02).
    """
    if not bounds:
        return []

    para_y_min = min(b.y1 for b in bounds)
    para_y_max = max(b.y2 for b in bounds)

    # If the paragraph is vertically flat, treat it as a single line.
    if (para_y_max - para_y_min) < 5:
        return [list(range(len(bounds)))]

    scan_y_min = para_y_min
    scan_y_max = para_y_max
    # Tuong duong `np.arange(scan_y_max, scan_y_min, -step)` cua ban goc:
    # do dai = ceil((scan_y_max - scan_y_min) / step), gia tri giam dan tu
    # scan_y_max theo buoc `step`.
    m = math.ceil((scan_y_max - scan_y_min) / step)
    y_coordinates = [scan_y_max - i * step for i in range(m)]

    collision_bounds = [b for b in bounds if not b.is_space]
    if not collision_bounds:
        collision_bounds = bounds

    collision_counts = _compute_collision_counts_histogram(
        [b.y1 for b in collision_bounds],
        [b.y2 for b in collision_bounds],
        scan_y_min,
        scan_y_max,
        step,
    )

    gaps: list[tuple[int, int]] = []
    in_gap = False
    gap_start_index = 0
    for i, count in enumerate(collision_counts):
        if count < 1 and not in_gap:
            in_gap = True
            gap_start_index = i
        elif count >= 1 and in_gap:
            in_gap = False
            gaps.append((gap_start_index, i - 1))
    if in_gap:
        gaps.append((gap_start_index, len(collision_counts) - 1))

    if not gaps:
        return [list(range(len(bounds)))]

    separator_y_coords = sorted(
        (y_coordinates[start_idx] for start_idx, _end_idx in gaps),
        reverse=True,
    )

    line_groups: list[list[int]] = [[] for _ in range(len(separator_y_coords) + 1)]
    for idx, b in enumerate(bounds):
        char_y_center = (b.y1 + b.y2) / 2
        line_idx = 0
        for sep_y in separator_y_coords:
            if char_y_center > sep_y:
                break
            line_idx += 1
        line_groups[line_idx].append(idx)

    return [group for group in line_groups if group]
