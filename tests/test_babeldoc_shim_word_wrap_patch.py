"""Test Bug #10 (Architecture.md BA10.7/BA10.9 muc 3) — generic hoa
`_ModulePatchFinder`/`_PatchingLoader` va patch moi `_apply_typesetting_patch`
trong `src/babeldoc_shim/sitecustomize.py`.

Khac cac test pin-cung-bang-regex hien co cho ParagraphFinder (3 patch Bug #7
can `PdfParagraph`/`Box`/`generate_base58_id` that phuc tap de fake day du),
patch Bug #10 chi can DUNG 1 method tren 1 class don gian
(`Typesetting._get_width_before_next_break_point`), nen test o day THUC THI
THAT ham production (`_apply_typesetting_patch`,
`_build_patched_get_width_before_next_break_point`) tren mot class GIA, dung
Protocol 6 R6-02 (khong chi assert "khong loi", ma assert HANH VI cu the
truoc/sau patch).

CAN sys.path tro thang vao `src/babeldoc_shim/` (giong PYTHONPATH that trong
subprocess babeldoc, BA10.7 rang buoc #3) vi cac ham build-patch trong
`sitecustomize.py` dung BARE import (`from word_wrap import ...`) chu khong
qua goi `src.babeldoc_shim.*`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

_BABELDOC_SHIM_DIR = Path(__file__).parent.parent / "src" / "babeldoc_shim"
_SIBLING_MODULE_NAMES = (
    "sitecustomize",
    "word_wrap",
    "line_split",
    "numbered_list_split",
    "toc_split",
)


@pytest.fixture
def sitecustomize_module():
    """Import `sitecustomize.py` bang BARE import (them thu muc
    `src/babeldoc_shim/` vao dau `sys.path`) — y het co che PYTHONPATH that
    ma `BabeldocRunner` truyen cho subprocess babeldoc (khong phai qua goi
    `src.babeldoc_shim.sitecustomize`, vi ban than file do dung bare import
    cho cac module anh em)."""
    sys.path.insert(0, str(_BABELDOC_SHIM_DIR))
    for name in _SIBLING_MODULE_NAMES:
        sys.modules.pop(name, None)
    try:
        module = importlib.import_module("sitecustomize")
        yield module
    finally:
        for name in _SIBLING_MODULE_NAMES:
            sys.modules.pop(name, None)
        if str(_BABELDOC_SHIM_DIR) in sys.path:
            sys.path.remove(str(_BABELDOC_SHIM_DIR))


class _FakeUnit:
    def __init__(self, width: float, can_break_line: bool) -> None:
        self.width = width
        self.can_break_line = can_break_line


def _original_buggy_get_width_before_next_break_point(self, typesetting_units, scale):
    """Sao y HANH VI GOC (dem doi) cua babeldoc 0.6.4 that
    (`typesetting.py:1285-1298`, BA10.2-a) — dung lam fake method TRUOC patch."""
    total = 0.0
    for unit in typesetting_units:
        if unit.can_break_line:
            return total * scale
        total += unit.width
    return total * scale


def _make_fake_typesetting_module() -> ModuleType:
    fake_module = ModuleType("fake_typesetting_module")
    fake_class = type(
        "Typesetting",
        (),
        {"_get_width_before_next_break_point": _original_buggy_get_width_before_next_break_point},
    )
    fake_module.Typesetting = fake_class
    return fake_module


class TestApplyTypesettingPatch:
    def test_patches_method_and_fixes_double_counting_when_enabled(
        self, sitecustomize_module, monkeypatch
    ) -> None:
        monkeypatch.setenv("BABELDOC_SHIM_WORD_WRAP_FIX", "1")
        fake_module = _make_fake_typesetting_module()
        original_method = fake_module.Typesetting._get_width_before_next_break_point

        sitecustomize_module._apply_typesetting_patch(fake_module)

        assert fake_module.Typesetting._get_width_before_next_break_point is not original_method

        units = [_FakeUnit(3.0, False), _FakeUnit(4.0, False), _FakeUnit(1.0, True)]
        result = fake_module.Typesetting._get_width_before_next_break_point(None, units, 1.0)
        # Fixed: bo qua unit dau tien (3.0), chi cong 4.0 truoc break point.
        assert result == pytest.approx(4.0)

    def test_falls_back_to_original_behavior_when_disabled(
        self, sitecustomize_module, monkeypatch
    ) -> None:
        monkeypatch.setenv("BABELDOC_SHIM_WORD_WRAP_FIX", "0")
        fake_module = _make_fake_typesetting_module()

        sitecustomize_module._apply_typesetting_patch(fake_module)

        units = [_FakeUnit(3.0, False), _FakeUnit(4.0, False), _FakeUnit(1.0, True)]
        result = fake_module.Typesetting._get_width_before_next_break_point(None, units, 1.0)
        # TAT: giu nguyen hanh vi GOC (dem doi) — cong ca unit dau tien.
        assert result == pytest.approx(7.0)

    def test_raises_attribute_error_when_method_missing(self, sitecustomize_module) -> None:
        """Fail-safe (BA10.7): cau truc babeldoc doi (method bi doi ten/xoa)
        phai raise AttributeError ro rang, KHONG duoc patch nham vao thu
        khac hoac im lang bo qua."""
        fake_module = ModuleType("fake_typesetting_module_no_method")
        fake_module.Typesetting = type("Typesetting", (), {})

        with pytest.raises(AttributeError):
            sitecustomize_module._apply_typesetting_patch(fake_module)

    def test_rollback_independent_from_paragraph_finder_patch(self, sitecustomize_module) -> None:
        """BA10.7 rang buoc #1: loi o patch Typesetting KHONG duoc lam anh
        huong patch ParagraphFinder (va nguoc lai) — kiem tra qua
        `_PatchingLoader`/`_ModulePatchFinder` GENERIC (doi ten tu
        `_ParagraphFinderPatchFinder`), moi instance boc DUNG 1 apply_patch
        rieng."""
        calls: list[str] = []

        def failing_apply_patch(module: ModuleType) -> None:
            calls.append("typesetting_attempted")
            raise RuntimeError("gia lap babeldoc doi cau truc typesetting.py")

        def succeeding_apply_patch(module: ModuleType) -> None:
            calls.append("paragraph_finder_applied")

        class _StubLoader:
            def __init__(self, module: ModuleType) -> None:
                self._module = module

            def create_module(self, spec):
                return None

            def exec_module(self, module: ModuleType) -> None:
                pass

        typesetting_loader = sitecustomize_module._PatchingLoader(
            _StubLoader(ModuleType("typesetting")), failing_apply_patch, "Typesetting (Bug #10)"
        )
        paragraph_finder_loader = sitecustomize_module._PatchingLoader(
            _StubLoader(ModuleType("paragraph_finder")),
            succeeding_apply_patch,
            "ParagraphFinder (Bug #7)",
        )

        # Loader Typesetting that bai (exception bi nuot, log warning) —
        # KHONG duoc raise ra ngoai (fail-safe, BA10.7).
        typesetting_loader.exec_module(ModuleType("typesetting"))
        # Loader ParagraphFinder van chay BINH THUONG, hoan toan doc lap.
        paragraph_finder_loader.exec_module(ModuleType("paragraph_finder"))

        assert calls == ["typesetting_attempted", "paragraph_finder_applied"]

    def test_module_patch_finder_only_intercepts_its_own_target(self, sitecustomize_module) -> None:
        """Generic hoa (`_ModulePatchFinder`, doi ten tu
        `_ParagraphFinderPatchFinder`) van giu dung logic `find_spec`: chi
        can thiep DUNG 1 fullname duoc gan luc khoi tao, tra ve None cho moi
        import khac."""
        finder = sitecustomize_module._ModulePatchFinder(
            "babeldoc.format.pdf.document_il.midend.typesetting",
            lambda module: None,
            "Typesetting (Bug #10)",
        )
        assert finder.find_spec("some.other.module", None) is None
        assert (
            finder.find_spec("babeldoc.format.pdf.document_il.midend.paragraph_finder", None)
            is None
        )


class TestFlagIndependence:
    """BA10.9 muc 3 — TOC-1 v2 (Bug #7 Ca C) va word-wrap (Bug #10) phai bat/
    tat DOC LAP qua bien moi truong rieng, ca 4 to hop."""

    @pytest.mark.parametrize(
        ("toc_split_env", "word_wrap_env", "expected_toc", "expected_word_wrap"),
        [
            ("0", "0", False, False),
            ("1", "0", True, False),
            ("0", "1", False, True),
            ("1", "1", True, True),
        ],
    )
    def test_toc_split_and_word_wrap_fix_toggle_independently(
        self,
        sitecustomize_module,
        monkeypatch,
        toc_split_env,
        word_wrap_env,
        expected_toc,
        expected_word_wrap,
    ) -> None:
        monkeypatch.setenv("BABELDOC_SHIM_TOC_SPLIT", toc_split_env)
        monkeypatch.setenv("BABELDOC_SHIM_WORD_WRAP_FIX", word_wrap_env)
        assert sitecustomize_module._toc_split_enabled() is expected_toc
        assert sitecustomize_module._word_wrap_fix_enabled() is expected_word_wrap

    def test_word_wrap_fix_defaults_to_enabled_when_env_absent(
        self, sitecustomize_module, monkeypatch
    ) -> None:
        monkeypatch.delenv("BABELDOC_SHIM_WORD_WRAP_FIX", raising=False)
        assert sitecustomize_module._word_wrap_fix_enabled() is True

    def test_toc_split_defaults_to_disabled_when_env_absent(
        self, sitecustomize_module, monkeypatch
    ) -> None:
        monkeypatch.delenv("BABELDOC_SHIM_TOC_SPLIT", raising=False)
        assert sitecustomize_module._toc_split_enabled() is False
