"""Test Bug #10 fix (Architecture.md muc "Bug #10 — babeldoc cat ngang tu
tieng Viet giua chung ... thiet ke ban vá (Tech Lead, 2026-09-09)", BA10.3-b/
BA10.6/BA10.9) — bo be rong cua chinh unit hien tai khoi tong tra ve cua
`width_before_next_break_point`, fix loi "dem doi" khien babeldoc
`_get_width_before_next_break_point` + `_layout_typesetting_units:1411`
(typesetting.py 0.6.4) cong be rong unit hien tai 2 lan, gay wrap SAI CHO,
cat ngang giua tu tieng Viet (vd `"trung thanh"` -> `"t"` cuoi dong +
`"rung thanh"` dau dong sau).

Protocol 6 R6-02: test KHONG duoc chi assert "ham chay khong loi". Test nay
goi DUNG logic production `src.babeldoc_shim.word_wrap.width_before_next_break_point`
tren golden fixture `tests/fixtures/babeldoc/bug10_wrap/lcb_p39_trung_thanh_units.json`
va assert GIA TRI CU THE (BA10.6): tai ky tu 'r', bieu thuc
`current_x + unit_width + width_before_next_break_point(...)` PHAI <= box.x2
SAU vá, trong khi cong thuc goc (dem doi) cho > box.x2 — chung minh dung diem
khac biet hanh vi, khong chi "ham chay khong loi".

Golden fixture nguon (Protocol 5 muc 3 — KHONG go tay so lieu tu nghi ra):
dump TRUC TIEP tu 1 lan chay babeldoc 0.6.4 THAT (spike BA10.5, R5-02) tren
`tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf` (trang 39, 0-based,
trich tu Le Cordon Bleu Patisserie and Baking Foundations) qua debug hook tam
thoi bam vao `Typesetting._get_width_before_next_break_point` (frame
introspection lay `current_x`/`box` cua ham goi `_layout_typesetting_units`),
CHAY VOI patch TAT (`BABELDOC_SHIM_WORD_WRAP_FIX=0`) de bat dung khoanh khac
gay bug that (scale=0.85, ngay truoc khi babeldoc quyet dinh xuong dong giua
tu). So khop CHINH XAC voi vi du minh hoa cua Tech Lead trong Architecture.md
BA10.4 dinh chinh #2 (587.06 <= 590.91) — khong phai trung hop, day chinh la
ban ghi that ma vi du do dua tren.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.babeldoc_shim.word_wrap import width_before_next_break_point

_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "babeldoc"
    / "bug10_wrap"
    / "lcb_p39_trung_thanh_units.json"
)


def _load_golden() -> dict:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _original_lookahead(pairs: list[tuple[float, bool]], scale: float) -> float:
    """Cong thuc GOC (buggy) cua babeldoc — CONG CA be rong unit dau tien.
    Dung lam oracle doi chieu (khong phai code production), sao y nguyen van
    tu `typesetting.py:1285-1298` da trich trong Architecture.md BA10.2-a."""
    total = 0.0
    for width, can_break in pairs:
        if can_break:
            return total * scale
        total += width
    return total * scale


class TestGoldenFixtureLcbP39TrungThanh:
    """BA10.6: golden fixture dump tu 1 lan chay babeldoc THAT (khong go tay).

    Chuoi `units` bat dau TAI ky tu 't' cua "trung" (unit hien tai la 't'),
    voi `current_x` la vi tri TRUOC KHI dat 't'. `char` thu 3 trong moi bo ba
    CHI de doc hieu (debug), khong dung trong assertion (production
    `width_before_next_break_point` chi nhan (width, can_break_line))."""

    def test_char_at_index_0_is_t_and_index_1_is_r(self) -> None:
        golden = _load_golden()
        chars = [ch for _w, _cb, ch in golden["units"]]
        assert chars[0] == "t"
        assert chars[1] == "r"
        # Ca 2 deu KHONG phai break point (dung giua tu, dau vao hop le cho
        # nhanh "khong phai break point" cua ham production).
        assert golden["units"][0][1] is False
        assert golden["units"][1][1] is False

    def test_fixed_formula_at_r_fits_within_box_but_original_overflows(self) -> None:
        """Diem mau chot cua Bug #10 (BA10.6): tai ky tu 'r' (unit thu 2, sau
        khi da dat xong 't'), cong thuc SAU vá phai <= box.x2, cong thuc GOC
        (dem doi) phai > box.x2 — day la day du bang chung wrap SAI CHO chi
        xay ra voi cong thuc chua vá."""
        golden = _load_golden()
        units = golden["units"]
        current_x_at_t = golden["current_x"]
        box_x2 = golden["box_x2"]
        scale = golden["scale"]

        width_t, can_break_t, _ = units[0]
        width_r, can_break_r, _ = units[1]
        assert not can_break_t
        assert not can_break_r

        # Ca 2 cong thuc (goc/sua) DEU dong y 't' vua (khong wrap tai 't') —
        # xac nhan bang cach doc thang gia tri da tinh san trong fixture,
        # KHONG suy doan.
        pairs_from_t = [(w, cb) for w, cb, _ in units]
        original_lookahead_t = _original_lookahead(pairs_from_t, scale)
        fixed_lookahead_t = width_before_next_break_point(iter(pairs_from_t), scale)
        cond_original_t = current_x_at_t + width_t * scale + original_lookahead_t
        cond_fixed_t = current_x_at_t + width_t * scale + fixed_lookahead_t
        assert cond_original_t <= box_x2, "golden fixture invalid: 't' da vuot box truoc ca patch"
        assert cond_fixed_t <= box_x2

        # Dat 't' (ca 2 nhanh deu dat, current_x tien them width_t*scale).
        current_x_at_r = current_x_at_t + width_t * scale

        # Tai 'r' — DAY LA DIEM KHAC BIET HANH VI (BA10.6 assertion bat buoc).
        pairs_from_r = [(w, cb) for w, cb, _ in units[1:]]
        original_lookahead_r = _original_lookahead(pairs_from_r, scale)
        fixed_lookahead_r = width_before_next_break_point(iter(pairs_from_r), scale)
        cond_original_r = current_x_at_r + width_r * scale + original_lookahead_r
        cond_fixed_r = current_x_at_r + width_r * scale + fixed_lookahead_r

        assert cond_original_r > box_x2, (
            f"oracle sai: cong thuc GOC (dem doi) phai VUOT box.x2 tai 'r' "
            f"({cond_original_r:.4f} > {box_x2:.4f}) — day chinh la nguyen "
            f"nhan wrap sai cho, cat ngang giua tu 'trung'"
        )
        assert cond_fixed_r <= box_x2, (
            f"FIX SAI: cong thuc SAU VA phai <= box.x2 tai 'r' "
            f"({cond_fixed_r:.4f} <= {box_x2:.4f}) — neu assertion nay fail, "
            f"'r' van bi day xuong dong moi, bug Bug #10 CHUA duoc sua"
        )

        # Khop CHINH XAC voi vi du minh hoa cua Tech Lead (Architecture.md
        # BA10.4 dinh chinh #2): "cx' + w('r') + w('ung') = cx + w('trung') =
        # van 587.06 <= 590.91" — khong phai trung hop, day la ban ghi that
        # ma vi du do dua tren (BA10.5 spike).
        assert cond_fixed_r == pytest.approx(587.06, abs=0.01)
        assert box_x2 == pytest.approx(590.91, abs=0.01)


class TestWidthBeforeNextBreakPointEdgeCases:
    """BA10.9 muc 1 — cac case bien bat buoc, doc lap voi golden fixture."""

    def test_empty_iterable_returns_zero(self) -> None:
        assert width_before_next_break_point(iter([]), scale=1.0) == 0.0

    def test_current_unit_itself_is_break_point_returns_zero_unchanged_from_original(
        self,
    ) -> None:
        """`units[0].can_break_line == True` -> giu NGUYEN hanh vi goc (guard
        `typesetting_units[0].can_break_line: return 0` cua ham babeldoc,
        BA10.3-b docstring)."""
        units = [(5.0, True), (3.0, False), (4.0, False)]
        assert width_before_next_break_point(iter(units), scale=1.0) == 0.0

    def test_word_with_no_break_point_until_end_of_list(self) -> None:
        """Tu dai khong co break point nao toi het list — tong CA phan con
        lai (tru unit hien tai), khong sinh loi/khong cat cut."""
        units = [(3.0, False), (4.0, False), (5.0, False), (6.0, False)]
        result = width_before_next_break_point(iter(units), scale=1.0)
        assert result == pytest.approx(4.0 + 5.0 + 6.0)

    def test_scale_factor_applied_to_final_sum_only(self) -> None:
        units = [(3.0, False), (4.0, False), (2.0, True)]
        result = width_before_next_break_point(iter(units), scale=0.5)
        # Bo qua unit dau (3.0), cong 4.0 (unit ke), dung tai break point (2.0
        # khong duoc cong vi no LA break point) -> 4.0 * 0.5 = 2.0.
        assert result == pytest.approx(2.0)

    def test_excludes_current_unit_from_total_unlike_original_babeldoc(self) -> None:
        """Diem khac biet CHINH voi ham goc (BA10.3-b): unit dau tien (unit
        hien tai) KHONG duoc cong vao tong, chi cac unit KE TIEP moi duoc
        cong cho toi break point."""
        units = [(10.0, False), (1.0, False), (1.0, True)]
        fixed = width_before_next_break_point(iter(units), scale=1.0)
        original = _original_lookahead(units, scale=1.0)
        assert fixed == pytest.approx(1.0)  # chi unit thu 2 (1.0), bo qua 10.0
        assert original == pytest.approx(11.0)  # ham goc cong ca 10.0 + 1.0
        assert fixed < original

    def test_accepts_lazy_generator_not_just_list(self) -> None:
        """BA10.3-b + hieu nang (G4): ham phai nhan duoc iterable LUOI (khong
        bat buoc phai la list/Sequence da materialize) — day la co so cho
        thiet ke early-exit tranh O(n^2) trong sitecustomize.py."""

        def gen():
            yield (3.0, False)
            yield (4.0, False)
            yield (2.0, True)
            raise AssertionError("khong duoc doc qua break point (early exit)")

        result = width_before_next_break_point(gen(), scale=1.0)
        assert result == pytest.approx(4.0)
