"""Thuat toan wrap thuan (khong phu thuoc babeldoc), dung chung boi
`sitecustomize.py` (patch that su, chay trong subprocess babeldoc) VA test
(`tests/test_babeldoc_word_wrap.py`, chay trong process app, KHONG can
babeldoc cai san — Protocol 6 R6-02: test phai goi dung logic production,
khong duoc chep tay lai thuat toan roi test ban chep).

Bug #10 (Architecture.md muc "Bug #10 — babeldoc cat ngang tu tieng Viet giua
chung"): ham goc `Typesetting._get_width_before_next_break_point`
(`typesetting.py:1285-1298` cua babeldoc 0.6.4 da cai) CONG CA be rong cua
chinh unit hien tai (`typesetting_units[0]`) vao tong tra ve, roi cho goi
(`typesetting.py:1411`) LAI CONG THEM `unit_width` cua chinh unit do mot lan
nua — dem doi. Voi tieng Trung/Nhat, moi ky tu deu `can_break_line == True`
nen guard dau ham luon tra `0` va loi nay vo hinh; voi tieng Viet (dau/am tiet
dai lam `can_break_line == False` keo dai), loi lo ra thanh cat ngang giua tu
(vd `"trung thanh"` -> `"t"` cuoi dong + `"rung thanh"` dau dong sau).

Fix: bo `w(unit hien tai)` khoi tong tra ve — chi cong tu unit KE TIEP tro di
cho toi break point.
"""

from __future__ import annotations

from collections.abc import Iterable


def width_before_next_break_point(
    units: Iterable[tuple[float, bool]],
    scale: float,
) -> float:
    """Be rong phan CON LAI cua tu, KHONG ke unit hien tai (Bug #10).

    `units` la mot iterable LUOI (vd generator), BAT DAU TAI unit hien tai —
    y het dau vao cua ham goc babeldoc (`typesetting_units[i:]`), CHI khac o
    cho phan tu dau tien (unit hien tai) bi BO QUA khoi tong (day chinh la
    fix). Nhan iterable thay vi list/Sequence la co y: ham goc thoat som
    (early exit) ngay tai break point dau tien; neu wrapper trong
    `sitecustomize.py` truyen mot LIST da materialize toan bo lat cat con lai
    cua paragraph (`typesetting_units[i:]`) thi early-exit nay se bi vo hieu
    hoa hoan toan (duyet het ca lat cat moi lan goi thay vi dung o break point
    dau tien), gay O(n) moi lan goi thay vi O(k) — vi ham nay nam trong vong
    lap ngoai chay lai cho MOI chi so `i` (va cho MOI gia tri `scale` thu),
    chenh lech nay thanh O(n^2)/O(scale_count * n^2) tren paragraph dai. Dung
    generator (`iter()` + vong lap `for` thoat som ngay ben duoi) giu dung do
    phuc tap O(k) cua ham goc.
    """
    iterator = iter(units)
    try:
        _first_width, first_can_break = next(iterator)
    except StopIteration:
        return 0.0
    if first_can_break:
        # Unit hien tai tu no da la break point -> giu nguyen hanh vi goc
        # (guard `typesetting_units[0].can_break_line` cua ham babeldoc goc).
        return 0.0

    total = 0.0
    for width, can_break in iterator:  # KHAC ban goc: bo qua unit dau tien
        if can_break:
            break
        total += width
    return total * scale
