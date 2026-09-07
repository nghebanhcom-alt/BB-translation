"""Shim vá lỗi tách dòng của babeldoc 0.6.4 (Bug #7 — Architecture.md mục
"Bug #7/#8 — Final Decision sau phản biện Domain Expert (2026-09-07)", X3/X4-1/X5).

BỐI CẢNH KỸ THUẬT (đọc trước khi sửa file này)
------------------------------------------------
App gọi `babeldoc` qua subprocess CLI (`src/services/babeldoc_runner.py`,
`asyncio.create_subprocess_exec`) — KHÔNG import babeldoc trong process của
app. babeldoc cài ở venv riêng qua `uv tool`. Vì vậy monkey-patch Python
thông thường viết trong code app sẽ KHÔNG có tác dụng gì lên babeldoc chạy
trong subprocess con.

Vector kỹ thuật dùng ở đây (V1, đã chốt ở Architecture.md X4-1):
`BabeldocRunner` truyền `PYTHONPATH=<thư mục chứa file này>` vào `env` của
subprocess babeldoc. CPython tự động `import sitecustomize` (nếu tìm thấy
trên `sys.path`) ngay khi khởi động interpreter, TRƯỚC khi chạy entry point
`babeldoc`. File này lợi dụng đúng cơ chế chuẩn đó — không đụng file nào bên
trong venv của tool (V3 đã bị loại vì mất khi `uv tool upgrade`).

CƠ CHẾ BUG THẬT (X3, thay thế mô tả sai ở W2 của Architecture.md)
------------------------------------------------------------------
1. Ký tự khoảng trắng không có glyph ⇒ babeldoc gán `visual_bbox` mặc định
   cao ĐÚNG BẰNG `font_size` (`il_creater.py:1092-1108`, chỉ thay bằng bbox
   glyph thật khi `volume > 1`).
2. Với font ~10pt, pitch dòng ~12pt, một space có thể lấp gần hết pitch ⇒ khe
   hở thật giữa 2 dòng chỉ còn ~2pt.
3. Bất kỳ ký tự nào có descender (g, y, p, q, j — và dấu tiếng Việt) chọc vào
   phần khe còn lại là đủ khiến `count` (số ký tự cắt qua 1 lát cắt ngang)
   không bao giờ về 0 ⇒ `_split_paragraph_into_lines` không tìm thấy gap nào
   ⇒ CẢ paragraph gộp thành một `PdfLine` duy nhất.

FIX (D7-1, X5): loại ký tự khoảng trắng khỏi PHÉP ĐẾM va chạm dùng để tìm
gap. GIỮ NGUYÊN ngưỡng gốc `count < 1` — KHÔNG đổi thành `count < 2` (đã bị
chứng minh là hồi quy thật với dòng chỉ có đúng 1 ký tự, ví dụ ô số hẹp trong
bảng — xem X2-b). Ký tự khoảng trắng vẫn được gán vào đúng dòng của nó theo
tâm y (bước gán dòng KHÔNG đổi) — chỉ đơn giản không được tính phiếu vào việc
"khe có trống hay không".

FAIL-SAFE BẮT BUỘC
-------------------
1. Chỉ áp dụng patch khi `babeldoc.__version__ == "0.6.4"` — version khác
   (`uv tool upgrade`) có thể đổi tên hàm/module/cấu trúc code, patch mù theo
   giả định cũ sẽ sai lặng lẽ (Protocol 5 mục 5). Version khác ⇒ log cảnh báo,
   KHÔNG patch gì cả.
2. Nếu quá trình patch thất bại vì BẤT KỲ lý do gì (đổi tên hàm, đổi cấu trúc
   module, lỗi import...) ⇒ log cảnh báo rõ ràng, để babeldoc chạy tiếp với
   hành vi GỐC. TUYỆT ĐỐI không được để lỗi ở đây làm crash job dịch.
3. Tắt shim: bỏ biến môi trường `PYTHONPATH` trỏ tới thư mục này (hoặc không
   truyền nó) — babeldoc quay lại hành vi gốc hoàn toàn, không cần chỉnh gì
   trong venv của tool.

BUOC 7.2 — CA A: TACH NUMBERED-LIST (Architecture.md X5 D7-3, "7.2")
---------------------------------------------------------------------
Sau khi tang dong duoc sua (7.1 o tren), mot so paragraph van con GOM CHUNG
nhieu muc numbered-list (vd 8 muc "8./9./.../15." dinh lien trong 1
paragraph — xac nhan bang spike song, khong suy doan) vi `is_bullet_point`
goc cua babeldoc CHI xet ky tu dau tien cua dong VA khong nhan chu so la
bullet. Vá THEM `ParagraphFinder.process` (bao boc: chay ham goc truoc, roi
duyet IL VUA duoc tao va tach tiep) — CHUA duoc phep chay TRUOC 7.1 (phu
thuoc thu tu, X5 D7-3: patch tang dong phai ap dung xong het thi cac dong
numbered-list moi tach dung, moi co gi de B-2b tach tiep o tang paragraph).

Heuristic: dong DAU TIEN cua 1 paragraph la "marker neo" (vd "8."); tim dong
DAU TIEN xuat hien sau do co marker dung bang marker neo + 1 (vd "9.") de
tach. Thuat toan thuan (khong phu thuoc babeldoc) nam o
`numbered_list_split.py`, dung chung voi test golden fixture. Tu sort ky tu
theo x (`visual_bbox.box.x`) truoc khi ghep chuoi di tim marker — cac loi
goi sort theo x cua chinh babeldoc deu bi comment (`paragraph_finder.py:305,
696,738,772`), nen thu tu ky tu KHONG duoc dam bao.

Doc lap voi bien BABELDOC_SHIM_NUMBERED_LIST_SPLIT (mac dinh "1" — bat):
`BabeldocRunner` truyen bien nay rieng, tat duoc heuristic 7.2 ma khong dong
ca shim 7.1 (Settings.babeldoc_numbered_list_split_enabled).
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import logging
import os
import sys
from types import ModuleType

logger = logging.getLogger("babeldoc_shim")

_EXPECTED_BABELDOC_VERSION = "0.6.4"
_TARGET_MODULE_NAME = "babeldoc.format.pdf.document_il.midend.paragraph_finder"


def _numbered_list_split_enabled() -> bool:
    return os.environ.get("BABELDOC_SHIM_NUMBERED_LIST_SPLIT", "1") != "0"


def _is_whitespace_char(char: object) -> bool:
    """True khi `char` (PdfCharacter) la ky tu khoang trang.

    `char_unicode` la field String bat buoc cua PdfCharacter (verified doc
    truc tiep tu `il_version_1.py`). Dung `.isspace()` de bat ca space thuong
    lan cac loai whitespace khac (tab, non-breaking space...) ma babeldoc co
    the sinh ra.
    """
    unicode_ = getattr(char, "char_unicode", None)
    return bool(unicode_) and unicode_.isspace()


def _build_patched_split_paragraph_into_lines(paragraph_finder_module: ModuleType):
    """Tra ve ham thay the cho `ParagraphFinder._split_paragraph_into_lines`.

    Sao y cau truc I/O cua ham goc (`paragraph_finder.py:652-776` cua
    babeldoc 0.6.4 da cai) nhung UY THAC toan bo thuat toan tach dong cho
    `line_split.split_into_line_groups()` — mot ham thuan (khong phu thuoc
    babeldoc) dung CHUNG voi test golden fixture
    (`tests/test_babeldoc_line_split_shim.py`, Protocol 6 R6-02: test phai
    goi dung logic production, khong duoc chep tay lai thuat toan roi test
    ban chep).
    """
    # `PYTHONPATH` (truyen tu `BabeldocRunner`) tro THANG vao thu muc nay
    # (`src/babeldoc_shim/`, khong phai project root) — vi vay import module
    # anh em cung thu muc bang ten tran, KHONG qua goi `src.babeldoc_shim.*`
    # (goi do khong ton tai tren `sys.path` cua subprocess babeldoc).
    from line_split import CharBound, split_into_line_groups

    def patched(self, paragraph, formula_font_ids):
        if not paragraph.pdf_paragraph_composition:
            return

        # 1. Extract all characters and other compositions from the paragraph.
        all_chars = []
        other_compositions = []
        for comp in paragraph.pdf_paragraph_composition:
            if comp.pdf_character:
                all_chars.append(comp.pdf_character)
            else:
                other_compositions.append(comp)

        if not all_chars:
            return

        # 2. Determine effective y-bounds for each character.
        bounds = [
            CharBound(y1=y1, y2=y2, is_space=_is_whitespace_char(char))
            for char in all_chars
            for y1, y2 in [self._get_effective_y_bounds(char)]
        ]

        if not bounds:
            paragraph.pdf_paragraph_composition = other_compositions
            self.update_paragraph_data(paragraph)
            return

        # 3-5. Thuat toan tach dong that su (Bug #7 fix, X5 D7-1) nam trong
        # `line_split.split_into_line_groups` — xem docstring cua no.
        line_groups = split_into_line_groups(bounds)

        if not line_groups:
            # Khong the xay ra voi bounds khong rong, nhung fail-safe: giu
            # nguyen thanh 1 dong duy nhat thay vi mat noi dung.
            line_groups = [list(range(len(all_chars)))]

        # 6. Rebuild the paragraph's composition list from the new lines.
        new_line_compositions = [
            self.create_line([all_chars[i] for i in group]) for group in line_groups if group
        ]

        paragraph.pdf_paragraph_composition = new_line_compositions + other_compositions
        self.update_paragraph_data(paragraph)

    return patched


def _split_numbered_list_paragraphs_on_page(self, page, paragraph_finder_module) -> None:
    """Buoc 7.2 (Ca A, X5 D7-3): duyet `page.pdf_paragraph` SAU KHI
    `process()` goc (da vá 7.1) chay xong, tach tiep cac paragraph con gom
    chung nhieu muc numbered-list. Moi quyet dinh CO tach hay khong VA tach
    O DAU deu do `numbered_list_split.split_paragraph_lines` (thuan Python,
    testable — Protocol 6 R6-02) tra ve; ham nay chi thuc thi ket qua do
    tren cac object babeldoc thuc: cat `pdf_paragraph_composition` theo do
    dai moi nhom, tao `PdfParagraph` moi cho tu nhom thu 2 tro di (tai su
    dung nguyen mau cua babeldoc `process_independent_paragraphs`,
    `paragraph_finder.py:868-925` — khong chep lai logic typeset/box).
    """
    from numbered_list_split import build_sorted_line_text, split_paragraph_lines

    PdfParagraph = paragraph_finder_module.PdfParagraph
    Box = paragraph_finder_module.Box
    generate_base58_id = paragraph_finder_module.generate_base58_id

    new_paragraphs = []
    for paragraph in page.pdf_paragraph:
        compositions = paragraph.pdf_paragraph_composition
        if len(compositions) <= 1:
            new_paragraphs.append(paragraph)
            continue

        line_texts: list[str | None] = []
        for comp in compositions:
            if not comp.pdf_line:
                line_texts.append(None)
                continue
            chars = [
                (char.visual_bbox.box.x, char.char_unicode) for char in comp.pdf_line.pdf_character
            ]
            line_texts.append(build_sorted_line_text(chars))

        groups = split_paragraph_lines(line_texts)
        if len(groups) == 1:
            new_paragraphs.append(paragraph)
            continue

        offset = 0
        for group_idx, group in enumerate(groups):
            comp_slice = compositions[offset : offset + len(group)]
            offset += len(group)
            if group_idx == 0:
                paragraph.pdf_paragraph_composition = comp_slice
                self.update_paragraph_data(paragraph)
                new_paragraphs.append(paragraph)
                continue
            new_paragraph = PdfParagraph(
                box=Box(0, 0, 0, 0),
                pdf_paragraph_composition=comp_slice,
                unicode="",
                debug_id=generate_base58_id(),
                layout_label=paragraph.layout_label,
                layout_id=paragraph.layout_id,
            )
            self.update_paragraph_data(new_paragraph)
            new_paragraphs.append(new_paragraph)

    page.pdf_paragraph = new_paragraphs


def _build_patched_process(paragraph_finder_module: ModuleType):
    """Boc `ParagraphFinder.process` (buoc 7.2): chay ham goc (da vá 7.1)
    truoc, roi tach tiep numbered-list tren tung trang cua `document.page`
    da duoc `process()` dien day du (Architecture.md X5 D7-3, phu thuoc
    thu tu bat buoc voi 7.1).
    """
    original_process = paragraph_finder_module.ParagraphFinder.process

    def patched(self, document):
        original_process(self, document)
        if not _numbered_list_split_enabled():
            return
        for page in document.page:
            _split_numbered_list_paragraphs_on_page(self, page, paragraph_finder_module)

    return patched


def _apply_patch(paragraph_finder_module: ModuleType) -> None:
    """Ap patch len `ParagraphFinder._split_paragraph_into_lines` (7.1) va
    `ParagraphFinder.process` (7.2).

    Goi tu `exec_module` wrapper cua import hook, SAU KHI module da import
    xong hoan toan. Boc trong try/except o noi goi (`_PatchingLoader`), noi
    day gia dinh moi thu ton tai dung nhu verify — neu sai (doi ten
    class/method o version khac), exception se bi bat va log canh bao o tang
    tren, KHONG patch GI CA (ca 2 patch deu rollback cung nhau — neu cau truc
    doi du de 1 patch sai thi patch kia cung dang nghi).
    """
    ParagraphFinder = paragraph_finder_module.ParagraphFinder
    if not hasattr(ParagraphFinder, "_split_paragraph_into_lines"):
        raise AttributeError(
            "ParagraphFinder khong co method _split_paragraph_into_lines — "
            "cau truc babeldoc co the da doi, khong ap patch."
        )
    if not hasattr(ParagraphFinder, "process"):
        raise AttributeError(
            "ParagraphFinder khong co method process — cau truc babeldoc co "
            "the da doi, khong ap patch."
        )
    ParagraphFinder._split_paragraph_into_lines = _build_patched_split_paragraph_into_lines(
        paragraph_finder_module
    )
    ParagraphFinder.process = _build_patched_process(paragraph_finder_module)
    logger.warning(
        "babeldoc_shim: da vá ParagraphFinder._split_paragraph_into_lines "
        "(Bug #7 fix — loai ky tu khoang trang khoi phep dem va cham, giu "
        "nguyen nguong count<1) va ParagraphFinder.process (buoc 7.2 — tach "
        "numbered-list, %s). PYTHONPATH shim dang hoat dong.",
        "bat" if _numbered_list_split_enabled() else "TAT qua BABELDOC_SHIM_NUMBERED_LIST_SPLIT=0",
    )


class _PatchingLoader(importlib.abc.Loader):
    """Boc loader that cua module muc tieu de chay patch NGAY SAU khi module
    duoc exec xong (khong dung truoc do — cac class/ham chua ton tai)."""

    def __init__(self, wrapped_loader: importlib.abc.Loader) -> None:
        self._wrapped = wrapped_loader

    def create_module(self, spec):
        create = getattr(self._wrapped, "create_module", None)
        return create(spec) if create is not None else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        try:
            _apply_patch(module)
        except Exception:
            logger.warning(
                "babeldoc_shim: KHONG the ap patch Bug #7 len %s — babeldoc "
                "se chay tiep voi hanh vi GOC (khong patch). Co the do "
                "version babeldoc da doi cau truc code so voi 0.6.4.",
                _TARGET_MODULE_NAME,
                exc_info=True,
            )


class _ParagraphFinderPatchFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder: chi can thiep dung 1 lan cho dung 1 module muc tieu
    (`…midend.paragraph_finder`), de nguyen moi import khac cho co che chuan
    cua Python xu ly.
    """

    def __init__(self, target_fullname: str) -> None:
        self._target_fullname = target_fullname
        self._resolving = False

    def find_spec(self, fullname, path, target=None):
        if fullname != self._target_fullname or self._resolving:
            return None

        # Tam thoi go chinh minh khoi meta_path de goi lai
        # importlib.util.find_spec ma khong de quy vo han vao day.
        self._resolving = True
        try:
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(fullname)
            finally:
                sys.meta_path.insert(0, self)
        finally:
            self._resolving = False

        if spec is None or spec.loader is None:
            return None

        spec.loader = _PatchingLoader(spec.loader)
        return spec


def _install_hook_if_version_matches() -> None:
    try:
        import babeldoc
    except Exception:  # noqa: BLE001 - khong co babeldoc thi khong lam gi ca
        return

    version = getattr(babeldoc, "__version__", None)
    if version != _EXPECTED_BABELDOC_VERSION:
        logger.warning(
            "babeldoc_shim: babeldoc version '%s' khac voi version da verify "
            "('%s') — KHONG ap patch Bug #7 (Protocol 5 muc 5: doi version "
            "phai verify lai contract truoc). babeldoc chay voi hanh vi goc.",
            version,
            _EXPECTED_BABELDOC_VERSION,
        )
        return

    if _TARGET_MODULE_NAME in sys.modules:
        # Da import roi (khong nen xay ra trong luong CLI binh thuong vi
        # sitecustomize chay truoc entry point, nhung fail-safe: thu patch
        # truc tiep thay vi cai hook cho mot import se khong bao gio toi).
        try:
            _apply_patch(sys.modules[_TARGET_MODULE_NAME])
        except Exception:
            logger.warning(
                "babeldoc_shim: module muc tieu da duoc import truoc do va "
                "patch truc tiep that bai — babeldoc chay voi hanh vi goc.",
                exc_info=True,
            )
        return

    sys.meta_path.insert(0, _ParagraphFinderPatchFinder(_TARGET_MODULE_NAME))


try:
    _install_hook_if_version_matches()
except Exception:
    logger.warning("babeldoc_shim: loi khong luong truoc khi cai hook.", exc_info=True)
