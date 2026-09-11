"""BL-04 (Architecture.md 6.22.4) — test THUAN cho `src/babeldoc_shim/
drop_report.py` (predicate + dung record, khong can babeldoc cai san) VA
wiring cua patch observer trong `sitecustomize.py` (`_apply_pdf_creater_patch`/
`_build_patched_create_render_units_for_page`) tren 1 class GIA, cung pattern
voi `tests/test_babeldoc_shim_word_wrap_patch.py` (Protocol 6 R6-02: THUC
THI THAT ham production, khong chi assert "khong loi").
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from src.babeldoc_shim.drop_report import (
    build_drop_record,
    build_header_record,
    build_page_record,
    collect_page_records,
    has_rendered_chars,
    is_dropped,
)

_BABELDOC_SHIM_DIR = Path(__file__).parent.parent / "src" / "babeldoc_shim"
_SIBLING_MODULE_NAMES = (
    "sitecustomize",
    "word_wrap",
    "line_split",
    "numbered_list_split",
    "toc_split",
    "drop_report",
)


@pytest.fixture
def sitecustomize_module():
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


# --- drop_report.py (thuan, khong can babeldoc) -----------------------------


def _fake_paragraph(*, unicode_: str | None, debug_id: str | None, has_char: bool, **kwargs):
    comp = SimpleNamespace(
        pdf_character=SimpleNamespace() if has_char else None,
        pdf_formula=None,
    )
    return SimpleNamespace(
        pdf_paragraph_composition=[comp],
        unicode=unicode_,
        debug_id=debug_id,
        layout_label=kwargs.get("layout_label", "plain text"),
        box=kwargs.get("box"),
        optimal_scale=kwargs.get("optimal_scale"),
        scale=kwargs.get("scale"),
    )


def test_has_rendered_chars_true_when_composition_has_char() -> None:
    p = _fake_paragraph(unicode_="xin chao", debug_id="abc12", has_char=True)
    assert has_rendered_chars(p) is True


def test_has_rendered_chars_false_when_composition_empty_of_chars() -> None:
    p = _fake_paragraph(unicode_="xin chao", debug_id="abc12", has_char=False)
    assert has_rendered_chars(p) is False


def test_is_dropped_true_exactly_when_no_chars_but_unicode_and_debug_id_present() -> None:
    dropped = _fake_paragraph(unicode_="mat noi dung", debug_id="abc12", has_char=False)
    assert is_dropped(dropped) is True

    not_dropped_has_char = _fake_paragraph(unicode_="con noi dung", debug_id="abc12", has_char=True)
    assert is_dropped(not_dropped_has_char) is False

    not_dropped_no_unicode = _fake_paragraph(unicode_="", debug_id="abc12", has_char=False)
    assert is_dropped(not_dropped_no_unicode) is False

    not_dropped_no_debug_id = _fake_paragraph(
        unicode_="mat noi dung", debug_id=None, has_char=False
    )
    assert is_dropped(not_dropped_no_debug_id) is False


def test_build_header_record_shape() -> None:
    record = build_header_record("0.6.4", 12345)
    assert record == {
        "type": "header",
        "schema": "babeldoc_drop_report/v2",
        "babeldoc_version": "0.6.4",
        "pid": 12345,
    }


def test_build_page_record_shape() -> None:
    record = build_page_record(page_number_1based=230, paragraph_count=12, dropped_count=1)
    assert record == {
        "type": "page",
        "page_number_1based": 230,
        "paragraph_count": 12,
        "dropped_count": 1,
    }


def test_build_drop_record_truncates_text_excerpt_and_reports_full_len() -> None:
    box = SimpleNamespace(x=61.5, y=223.6, x2=332.3, y2=466.6)
    long_text = "a" * 500
    p = _fake_paragraph(
        unicode_=long_text,
        debug_id="dbg01",
        has_char=False,
        layout_label="plain text",
        box=box,
        optimal_scale=0.1,
        scale=None,
    )
    record = build_drop_record(p, page_number_1based=230)
    assert record["type"] == "drop"
    assert record["page_number_1based"] == 230
    assert record["debug_id"] == "dbg01"
    assert record["layout_label"] == "plain text"
    assert record["box"] == (61.5, 223.6, 332.3, 466.6)
    assert record["optimal_scale"] == 0.1
    assert record["scale"] is None
    assert len(record["text_excerpt"]) == 400
    assert record["text_len"] == 500


def test_collect_page_records_checksum_matches_drop_count() -> None:
    paragraphs = [
        _fake_paragraph(unicode_="con chu", debug_id="a1", has_char=True),
        _fake_paragraph(unicode_="mat het roi", debug_id="a2", has_char=False),
        _fake_paragraph(unicode_="cung mat", debug_id="a3", has_char=False),
    ]
    page = SimpleNamespace(pdf_paragraph=paragraphs)

    page_record, drop_records = collect_page_records(page, page_number_1based=5)

    assert page_record == {
        "type": "page",
        "page_number_1based": 5,
        "paragraph_count": 3,
        "dropped_count": 2,
    }
    assert len(drop_records) == 2
    assert {r["debug_id"] for r in drop_records} == {"a2", "a3"}


# --- sitecustomize.py wiring (patch quan sat, CHI DOC) ----------------------


class _FakePage:
    def __init__(self, page_number: int, pdf_paragraph: list) -> None:
        self.page_number = page_number
        self.pdf_paragraph = pdf_paragraph


def _make_fake_pdf_creater_module(original_return=("render_units",)):
    fake_module = ModuleType("fake_pdf_creater_module")

    def original_method(self, page, translation_config):
        return list(original_return)

    fake_class = type("PDFCreater", (), {"create_render_units_for_page": original_method})
    fake_module.PDFCreater = fake_class
    return fake_module


def test_apply_pdf_creater_patch_writes_header_and_page_and_drop_lines(
    sitecustomize_module, monkeypatch, tmp_path: Path
) -> None:
    # BabeldocRunner luon `output_dir.mkdir(parents=True, exist_ok=True)`
    # TRUOC khi set bien moi truong nay (Architecture.md 6.22.4 "Vi tri
    # file") — mo phong dung thu tu do o day.
    chunk_output_dir = tmp_path / "chunk_5"
    chunk_output_dir.mkdir(parents=True)
    report_path = chunk_output_dir / "out.199-240.drops.jsonl"
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT", "1")
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT_PATH", str(report_path))

    fake_module = _make_fake_pdf_creater_module()
    sitecustomize_module._apply_pdf_creater_patch(fake_module)

    # Header phai duoc ghi NGAY luc ap patch (truoc khi render trang nao).
    header_lines_before = report_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(header_lines_before) == 1
    header = json.loads(header_lines_before[0])
    assert header["type"] == "header"
    assert header["schema"] == "babeldoc_drop_report/v2"

    dropped_paragraph = _fake_paragraph(unicode_="mat het roi", debug_id="x1", has_char=False)
    kept_paragraph = _fake_paragraph(unicode_="con chu", debug_id="x2", has_char=True)
    page = _FakePage(page_number=229, pdf_paragraph=[dropped_paragraph, kept_paragraph])

    result = fake_module.PDFCreater.create_render_units_for_page(None, page, None)

    # Ham goc LUON duoc goi va ket qua LUON duoc tra ve dung (patch CHI DOC).
    assert result == ["render_units"]

    lines = report_path.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    assert records[0]["type"] == "header"

    page_records = [r for r in records if r["type"] == "page"]
    assert len(page_records) == 1
    assert page_records[0]["page_number_1based"] == 230  # 229 + 1 (0-based -> 1-based)
    assert page_records[0]["paragraph_count"] == 2
    assert page_records[0]["dropped_count"] == 1

    drop_records = [r for r in records if r["type"] == "drop"]
    assert len(drop_records) == 1
    assert drop_records[0]["page_number_1based"] == 230
    assert drop_records[0]["debug_id"] == "x1"


def test_apply_pdf_creater_patch_no_writes_when_disabled(
    sitecustomize_module, monkeypatch, tmp_path: Path
) -> None:
    report_path = tmp_path / "out.jsonl"
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT", "0")
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT_PATH", str(report_path))

    fake_module = _make_fake_pdf_creater_module()
    sitecustomize_module._apply_pdf_creater_patch(fake_module)

    assert not report_path.exists()

    page = _FakePage(page_number=0, pdf_paragraph=[])
    result = fake_module.PDFCreater.create_render_units_for_page(None, page, None)
    assert result == ["render_units"]
    assert not report_path.exists()


def test_apply_pdf_creater_patch_no_writes_when_path_env_absent(
    sitecustomize_module, monkeypatch
) -> None:
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT", "1")
    monkeypatch.delenv("BABELDOC_SHIM_DROP_REPORT_PATH", raising=False)

    fake_module = _make_fake_pdf_creater_module()
    # KHONG duoc raise du khong co duong dan — patch van ap thanh cong, chi
    # khong ghi gi ca.
    sitecustomize_module._apply_pdf_creater_patch(fake_module)

    page = _FakePage(page_number=0, pdf_paragraph=[])
    result = fake_module.PDFCreater.create_render_units_for_page(None, page, None)
    assert result == ["render_units"]


def test_apply_pdf_creater_patch_observer_failure_never_breaks_render(
    sitecustomize_module, monkeypatch, tmp_path: Path
) -> None:
    """Patch nay CHI DOC — 1 loi trong buoc ghi sidecar (o day: duong dan la
    1 thu muc, khong mo file duoc) khong bao gio duoc lam hong ket qua render
    that su tra ve."""
    bad_path = tmp_path  # la thu muc, khong phai file -> mo() se raise
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT", "1")
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT_PATH", str(bad_path))

    fake_module = _make_fake_pdf_creater_module(original_return=("unit_a", "unit_b"))
    # Ap patch: ghi header that bai (bad_path la thu muc) nhung KHONG duoc
    # raise ra ngoai _apply_pdf_creater_patch (header write co try/except
    # rieng).
    sitecustomize_module._apply_pdf_creater_patch(fake_module)

    page = _FakePage(page_number=0, pdf_paragraph=[])
    result = fake_module.PDFCreater.create_render_units_for_page(None, page, None)
    assert result == ["unit_a", "unit_b"]


def test_apply_pdf_creater_patch_raises_when_method_missing(sitecustomize_module) -> None:
    fake_module = ModuleType("fake_pdf_creater_module_no_method")
    fake_module.PDFCreater = type("PDFCreater", (), {})

    with pytest.raises(AttributeError):
        sitecustomize_module._apply_pdf_creater_patch(fake_module)


def test_drop_report_enabled_defaults_to_true(sitecustomize_module, monkeypatch) -> None:
    monkeypatch.delenv("BABELDOC_SHIM_DROP_REPORT", raising=False)
    assert sitecustomize_module._drop_report_enabled() is True


def test_drop_report_enabled_env_0_disables(sitecustomize_module, monkeypatch) -> None:
    monkeypatch.setenv("BABELDOC_SHIM_DROP_REPORT", "0")
    assert sitecustomize_module._drop_report_enabled() is False
