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

BUOC 7.4-b — CA C: TACH MUC LUC KHONG DOT-LEADER "DU DAY" (TOC-1 v2)
---------------------------------------------------------------------
Architecture.md muc "Bug #7 Ca C — Quyet dinh cuoi sau phan bien Domain
Expert + ke hoach spike 7.4-a (Tech Lead, 2026-09-08)" (AA0-AA12). Spike
7.4-a (module `toc_split.py`, thuat toan thuan) da PASS toan bo gate AA9 va
qua Reviewer APPROVE (`docs/review-report.md`, "Review spike 7.4-a") — patch
NAY (7.4-b) wiring thuat toan do vao babeldoc that.

Diem hook (AA6, KHAC 2 patch tren): boc `ParagraphFinder.
process_independent_paragraphs(paragraphs, median_width)` — KHONG boc
`process()` nhu 7.2. Ham nay chay o `process_page` (`paragraph_finder.py:287`)
NGAY SAU khi `page.pdf_paragraph = paragraphs` (`:245`, cung 1 list object)
va TRUOC 3 buoc quan trong chay SAU no trong `process_page`:
  1. `merge_alternating_line_number_paragraphs` (`:291`) — khong gop lai duoc
     paragraph TOC-1 tao ra (ly do that: `_is_ascii_digit_or_space_paragraph`
     + `layout_id` phai trung, KHONG phai `xobj_id` nhu suy doan sai cua vong
     Y — da tu doc source xac nhan, AA1/AA2 Z2-b).
  2. `for paragraph in paragraphs: update_paragraph_data(paragraph,
     update_unicode=True)` (`:293-294`) — chay cho MOI paragraph trong cung
     list `paragraphs` ma patch nay mutate in-place, nen paragraph TOC-1 tao
     moi LUON co `.unicode` dung — MIEN NHIEM voi dung lop bug da lam hong
     7.2 (Z6: `unicode=""` khien `il_translator_llm_only.py` bo qua, khong
     dich). Day la ly do CHINH chon hook nay (AA6 ly do 1) — an toan theo
     CAU TRUC, khong phai theo tri nho nguoi viet code phai tu goi
     `update_paragraph_data(update_unicode=True)`.
  3. `_set_paragraph_render_order` (`:310`) — chay SAU, nen paragraph TOC-1
     co `render_order` THAT, khong ke thua no cua 7.2 (Y10-b, `render_order`
     khong duoc copy khi tach — AA10-b, van con o 7.2, KHONG thuoc pham vi
     7.4).
Vi 2 dieu nay, patch nay KHONG tu goi `update_paragraph_data(...,
update_unicode=True)` va KHONG tu gan `render_order` — khac han patch 7.2 o
tren (`_split_numbered_list_paragraphs_on_page` phai tu lam ca hai vi no hook
SAU cung 1 loi goi nay trong `process()`).

Thuat toan tach thuan (AA4 6 buoc + AA5 tham so) nam trong `toc_split.py`,
dung chung voi test golden fixture (`tests/test_babeldoc_toc_split.py`,
Protocol 6 R6-02). Ham o day (`_split_toc_paragraphs_in_list`) chi thuc thi
ket qua `evaluate_paragraph(...)` tra ve tren object babeldoc that: cat
`pdf_paragraph_composition` theo `cut_after`, tao `PdfParagraph` moi cho tung
nhom tu nhom thu 2 tro di — dung nguyen mau chinh nhanh dot-leader (>= 20
cham) da co san CUA CHINH `process_independent_paragraphs` goc
(`paragraph_finder.py:868-885`, da doc source that AA4 buoc 5).

Doc lap voi bien BABELDOC_SHIM_TOC_SPLIT (mac dinh "0" — TAT, KHAC 2 patch
tren mac dinh BAT): day la heuristic MOI NHAT/rui ro cao nhat theo AA5, chi
bat sau khi QA live xanh (Settings.babeldoc_toc_split_enabled). Cung gate
version `0.6.4` va cung co che rollback-chung (try/except o
`_apply_paragraph_finder_patch`) voi 2 patch kia — babeldoc doi cau truc code
se lam CA 3 patch rollback cung nhau, khong rieng patch nay.

BUG #10 — DEM DOI BE RONG TRONG LOOKAHEAD WRAP (Architecture.md muc "Bug #10
— babeldoc cat ngang tu tieng Viet giua chung", 2026-09-09)
---------------------------------------------------------------------------
Vá THEM, o MODULE KHAC (`babeldoc.format.pdf.document_il.midend.typesetting`,
giai doan DAN TRANG — chay SAU giai doan tach doan/dong cua 3 patch tren) —
KHONG co phu thuoc thu tu voi 7.1/7.2/7.4-b. `Typesetting.
_get_width_before_next_break_point` cong CA be rong cua chinh unit hien tai
vao tong tra ve, roi noi goi (`_layout_typesetting_units:1411`) CONG THEM
`unit_width` cua chinh unit do 1 lan nua — dem doi. Voi tieng Trung/Nhat moi
ky tu deu duoc coi la break point nen loi nay vo hinh; voi tieng Viet (dau/am
tiet dai) loi lo ra thanh cat ngang giua tu (vd `"trung thanh"` ->
`"t"`/`"rung thanh"`). Fix: bo be rong unit hien tai khoi tong — thuat toan
thuan nam o `word_wrap.py`, dung chung voi test golden fixture (Protocol 6
R6-02).

Patch nay dung LOADER/FINDER RIENG voi 3 patch ParagraphFinder o tren
(`_ModulePatchFinder`, generic hoa tu `_ParagraphFinderPatchFinder` cu) —
rollback DOC LAP hoan toan (BA10.7 rang buoc #1): babeldoc doi cau truc
`typesetting.py` khong lam hong 3 patch Bug #7, va nguoc lai. Doc lap voi
bien BABELDOC_SHIM_WORD_WRAP_FIX (mac dinh "1" — BAT, KHAC TOC-1 v2: day la
fix so hoc dung/sai, khong phai heuristic can tune truoc khi bat mac dinh).
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import logging
import os
import sys
from collections.abc import Callable
from types import ModuleType

logger = logging.getLogger("babeldoc_shim")

_EXPECTED_BABELDOC_VERSION = "0.6.4"
_PARAGRAPH_FINDER_MODULE_NAME = "babeldoc.format.pdf.document_il.midend.paragraph_finder"
#: Bug #10 (Architecture.md muc "Bug #10 — babeldoc cat ngang tu tieng Viet
#: giua chung"). Module RIENG voi `_PARAGRAPH_FINDER_MODULE_NAME` — patch nay
#: vá `Typesetting._get_width_before_next_break_point` (giai doan dan trang,
#: chay SAU giai doan tach doan/dong) va rollback DOC LAP hoan toan voi 3
#: patch ParagraphFinder (BA10.7 rang buoc #1): neu babeldoc doi cau truc
#: `typesetting.py`, 3 patch Bug #7 van phai chay binh thuong, va nguoc lai.
_TYPESETTING_MODULE_NAME = "babeldoc.format.pdf.document_il.midend.typesetting"


def _numbered_list_split_enabled() -> bool:
    return os.environ.get("BABELDOC_SHIM_NUMBERED_LIST_SPLIT", "1") != "0"


def _toc_split_enabled() -> bool:
    # Mac dinh "0" (TAT) — KHAC 2 patch tren mac dinh BAT (AA5: heuristic moi
    # nhat/rui ro cao nhat, chi bat sau khi QA live xanh).
    return os.environ.get("BABELDOC_SHIM_TOC_SPLIT", "0") == "1"


def _word_wrap_fix_enabled() -> bool:
    # Bug #10: mac dinh "1" (BAT) — KHAC TOC-1 v2 (tung mac dinh TAT). Day la
    # fix so hoc dung/sai (bo 1 phep cong thua), khong phai heuristic doan y
    # do layout can tune truoc khi bat mac dinh (Architecture.md BA10.8).
    return os.environ.get("BABELDOC_SHIM_WORD_WRAP_FIX", "1") != "0"


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
                # update_unicode=True bat buoc: paragraph nay da di qua vong lap
                # `update_paragraph_data(paragraph, update_unicode=True)` cua
                # process_page (paragraph_finder.py:294) TRUOC KHI bi truncate o
                # day, nen .unicode dang giu NGUYEN VAN BAN GOP (dai hon noi dung
                # thuc te con lai). Khong cap nhat lai se de .unicode "an" chua
                # noi dung da bi tach di cho paragraph khac.
                self.update_paragraph_data(paragraph, update_unicode=True)
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
            # update_unicode=True bat buoc (Bug tim thay boi Domain Expert,
            # 2026-09-07): paragraph MOI nay khong bao gio di qua vong lap
            # `update_paragraph_data(..., update_unicode=True)` cua process_page
            # (paragraph_finder.py:294) vi no duoc tao SAU KHI process() da
            # chay xong hoan toan. Neu khong tu goi voi update_unicode=True,
            # `.unicode` giu nguyen "" (default) -> il_translator_llm_only.py
            # bo qua hoan toan paragraph nay (`len(paragraph.unicode) <
            # min_text_length`) -> muc numbered-list bi giu nguyen tieng Anh,
            # KHONG duoc dich. Verify song: 4/4 muc bi anh huong o 1 lan chay
            # thuc te (item #12/#24/#32/#34 tren page14_numbered_list_source.pdf)
            # deu la nhom thu 2 tro di cua 1 cap da tach — khop chinh xac gia
            # thuyet nay, khong phai "LLM tu fallback" nhu CHANGELOG buoc 7.2
            # ghi nham luc dau.
            self.update_paragraph_data(new_paragraph, update_unicode=True)
            new_paragraphs.append(new_paragraph)

    page.pdf_paragraph = new_paragraphs


def _split_toc_paragraphs_in_list(
    self, paragraphs: list, paragraph_finder_module: ModuleType
) -> None:
    """Buoc 7.4-b (TOC-1 v2, "Bug #7 Ca C"): sau khi `process_independent_
    paragraphs` GOC (nhanh dot-leader >= 20 cham) da chay xong tren CHINH
    list `paragraphs` nay, tach tiep cac paragraph con gom nhieu muc muc luc
    KHONG co dot-leader du day (< 20 cham). Moi quyet dinh CO tach hay khong
    VA tach O DAU deu do `toc_split.evaluate_paragraph` (thuan Python,
    testable — Protocol 6 R6-02) tra ve; ham nay chi thuc thi ket qua do tren
    cac object babeldoc that: cat `pdf_paragraph_composition` theo
    `cut_after`, tao `PdfParagraph` moi cho tung nhom tu nhom thu 2 tro di —
    dung nguyen mau chinh nhanh dot-leader cua ham goc
    (`paragraph_finder.py:868-885`, da doc source that AA4 buoc 5).

    Mutate `paragraphs` IN-PLACE qua slice assignment (`paragraphs[:] = ...`)
    — AA6 dua vao viec `page.pdf_paragraph` va tham so `paragraphs` cua ham
    `process_independent_paragraphs` TRO CUNG 1 list object
    (`paragraph_finder.py:245`), nen sua list nay tai cho se tu dong phan
    anh sang `page.pdf_paragraph` MA KHONG can duoc truyen `page`.

    KHONG tu goi `update_paragraph_data(..., update_unicode=True)` va KHONG
    tu gan `render_order` cho paragraph moi (AA4 buoc 5) — hook nay chay
    TRUOC `paragraph_finder.py:293-294` va `:310` nen babeldoc GOC se tu lam
    ca hai cho MOI paragraph con lai trong `paragraphs` (bao gom paragraph
    moi ham nay vua chen), giong het cach nhanh dot-leader cua chinh
    `process_independent_paragraphs` khong tu goi `update_unicode=True`.
    """
    from toc_split import (
        REASON_LOW_FRACTION,
        REASON_NOT_MONOTONIC,
        TocChar,
        evaluate_paragraph,
    )

    PdfParagraph = paragraph_finder_module.PdfParagraph
    Box = paragraph_finder_module.Box
    generate_base58_id = paragraph_finder_module.generate_base58_id

    new_paragraphs = []
    for paragraph in paragraphs:
        compositions = paragraph.pdf_paragraph_composition
        if len(compositions) <= 1:
            new_paragraphs.append(paragraph)
            continue

        line_chars: list[list[TocChar] | None] = []
        for comp in compositions:
            if not comp.pdf_line:
                line_chars.append(None)
                continue
            line_chars.append(
                [
                    TocChar(
                        x=char.visual_bbox.box.x,
                        x2=char.visual_bbox.box.x2,
                        unicode=char.char_unicode,
                        font_size=char.pdf_style.font_size or 0.0,
                    )
                    for char in comp.pdf_line.pdf_character
                ]
            )

        result = evaluate_paragraph(paragraph.layout_label, line_chars)
        if not result.fired:
            # AA4 buoc 3 / Z8-2(iv): khi cong m/L hoac monotonic CHAN mot
            # paragraph da co >= 2 dong duoc danh dau la duoi muc luc, ghi
            # log 1 dong de 7.4-e/7.4-d co so lieu THAT thay vi ly thuyet
            # (Tech Lead AA2 dong Z4 chap nhan yeu cau nay cua Domain Expert).
            # KHONG log cho REASON_DENY_LAYOUT/REASON_TOO_SHORT/
            # REASON_FEW_TAIL_LINES (tail_marks < 2 - khong phai ca dang lo
            # ngai) de tranh spam log tren moi trang van xuoi binh thuong.
            if (
                result.reason in (REASON_LOW_FRACTION, REASON_NOT_MONOTONIC)
                and result.tail_marks >= 2
            ):
                logger.warning(
                    "babeldoc_shim toc_split: paragraph co %d dong duoi muc "
                    "luc nhung BI CHAN boi %s (composition_count=%d) — khong "
                    "tach. Neu day la mot muc luc that bi bo lot, xem lai "
                    "tham so TOC_MIN_TAIL_FRACTION/TOC_REQUIRE_NON_DECREASING.",
                    result.tail_marks,
                    result.reason,
                    result.composition_count,
                )
            new_paragraphs.append(paragraph)
            continue

        # `cut_after` (tuple khong rong vi `fired=True`) la cac chi so
        # composition ma ranh gioi tach nam NGAY SAU no — chia thanh
        # `len(cut_after) + 1` nhom lien tiep (nhom cuoi la phan con lai sau
        # diem tach cuoi cung, AA4 buoc 5 bao dam luon con it nhat 1
        # composition o nhom nay vi buoc 4 da bo diem tach `j == L-1`).
        groups: list[list] = []
        offset = 0
        for cut_after in result.cut_after:
            groups.append(compositions[offset : cut_after + 1])
            offset = cut_after + 1
        groups.append(compositions[offset:])

        for group_idx, comp_slice in enumerate(groups):
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

    paragraphs[:] = new_paragraphs


def _build_patched_process_independent_paragraphs(paragraph_finder_module: ModuleType):
    """Boc `ParagraphFinder.process_independent_paragraphs` (buoc 7.4-b, AA6):
    chay ham goc (nhanh dot-leader >= 20 cham) truoc, roi chay TOC-1 v2 tren
    CUNG list `paragraphs` (mutate in-place)."""
    original_process_independent_paragraphs = (
        paragraph_finder_module.ParagraphFinder.process_independent_paragraphs
    )

    def patched(self, paragraphs, median_width):
        original_process_independent_paragraphs(self, paragraphs, median_width)
        if not _toc_split_enabled():
            return
        _split_toc_paragraphs_in_list(self, paragraphs, paragraph_finder_module)

    return patched


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


def _build_patched_get_width_before_next_break_point(typesetting_module: ModuleType):
    """Boc `Typesetting._get_width_before_next_break_point` (Bug #10):
    khi bat (`_word_wrap_fix_enabled()`), uy thac tinh toan cho thuat toan
    thuan `word_wrap.width_before_next_break_point` (bo unit hien tai khoi
    tong — fix dem doi be rong); khi tat, goi lai HAM GOC da chup lai truoc
    khi patch (rollback tuc thi qua bien moi truong, khong can deploy lai).

    Truyen GENERATOR (khong phai list) vao `width_before_next_break_point` —
    xem docstring ham do va BA10.3-b: giu dung do phuc tap O(k) early-exit
    cua ham goc, tranh O(n^2) khi ham nay bi goi lai cho moi chi so `i` trong
    `_layout_typesetting_units`.
    """
    # `PYTHONPATH` (truyen tu `BabeldocRunner`) tro THANG vao thu muc nay,
    # nen import module anh em bang ten tran — xem giai thich chi tiet o
    # `_build_patched_split_paragraph_into_lines` phia tren.
    from word_wrap import width_before_next_break_point

    original = typesetting_module.Typesetting._get_width_before_next_break_point

    def patched(self, typesetting_units, scale):
        if not _word_wrap_fix_enabled():
            return original(self, typesetting_units, scale)
        unit_pairs = ((unit.width, unit.can_break_line) for unit in typesetting_units)
        return width_before_next_break_point(unit_pairs, scale)

    return patched


def _apply_paragraph_finder_patch(paragraph_finder_module: ModuleType) -> None:
    """Ap patch len `ParagraphFinder._split_paragraph_into_lines` (7.1),
    `ParagraphFinder.process` (7.2) va `ParagraphFinder.
    process_independent_paragraphs` (7.4-b, TOC-1 v2 — Bug #7 Ca C).

    Goi tu `exec_module` wrapper cua import hook, SAU KHI module da import
    xong hoan toan. Boc trong try/except o noi goi (`_PatchingLoader`), noi
    day gia dinh moi thu ton tai dung nhu verify — neu sai (doi ten
    class/method o version khac), exception se bi bat va log canh bao o tang
    tren, KHONG patch GI CA (ca 3 patch deu rollback cung nhau — neu cau truc
    doi du de 1 patch sai thi 2 patch kia cung dang nghi). Rollback nay HOAN
    TOAN DOC LAP voi patch Bug #10 o `_apply_typesetting_patch` (module rieng,
    loader rieng — BA10.7 rang buoc #1).
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
    if not hasattr(ParagraphFinder, "process_independent_paragraphs"):
        raise AttributeError(
            "ParagraphFinder khong co method process_independent_paragraphs "
            "— cau truc babeldoc co the da doi, khong ap patch."
        )
    ParagraphFinder._split_paragraph_into_lines = _build_patched_split_paragraph_into_lines(
        paragraph_finder_module
    )
    ParagraphFinder.process = _build_patched_process(paragraph_finder_module)
    ParagraphFinder.process_independent_paragraphs = _build_patched_process_independent_paragraphs(
        paragraph_finder_module
    )
    logger.warning(
        "babeldoc_shim: da vá ParagraphFinder._split_paragraph_into_lines "
        "(Bug #7 fix — loai ky tu khoang trang khoi phep dem va cham, giu "
        "nguyen nguong count<1), ParagraphFinder.process (buoc 7.2 — tach "
        "numbered-list, %s) va ParagraphFinder.process_independent_paragraphs "
        "(buoc 7.4-b — tach muc luc Ca C, %s). PYTHONPATH shim dang hoat dong.",
        "bat" if _numbered_list_split_enabled() else "TAT qua BABELDOC_SHIM_NUMBERED_LIST_SPLIT=0",
        "bat" if _toc_split_enabled() else "TAT qua BABELDOC_SHIM_TOC_SPLIT=0 (mac dinh)",
    )


def _apply_typesetting_patch(typesetting_module: ModuleType) -> None:
    """Ap patch Bug #10 len `Typesetting._get_width_before_next_break_point`.

    Goi tu `exec_module` wrapper cua import hook RIENG cho module
    `typesetting` (loader/finder rieng voi `_apply_paragraph_finder_patch` —
    BA10.7 rang buoc #1: rollback DOC LAP, babeldoc doi cau truc
    `typesetting.py` khong duoc lam hong 3 patch ParagraphFinder cua Bug #7,
    va nguoc lai). Boc trong try/except o noi goi (`_PatchingLoader`), giong
    het co che fail-safe cua `_apply_paragraph_finder_patch`.
    """
    Typesetting = typesetting_module.Typesetting
    if not hasattr(Typesetting, "_get_width_before_next_break_point"):
        raise AttributeError(
            "Typesetting khong co method _get_width_before_next_break_point "
            "— cau truc babeldoc co the da doi, khong ap patch Bug #10."
        )
    Typesetting._get_width_before_next_break_point = (
        _build_patched_get_width_before_next_break_point(typesetting_module)
    )
    logger.warning(
        "babeldoc_shim: da vá Typesetting._get_width_before_next_break_point "
        "(Bug #10 — bo unit hien tai khoi lookahead wrap, tranh dem doi be "
        "rong khi kiem tra xuong dong, %s). PYTHONPATH shim dang hoat dong.",
        "bat" if _word_wrap_fix_enabled() else "TAT qua BABELDOC_SHIM_WORD_WRAP_FIX=0",
    )


class _PatchingLoader(importlib.abc.Loader):
    """Boc loader that cua module muc tieu de chay patch NGAY SAU khi module
    duoc exec xong (khong dung truoc do — cac class/ham chua ton tai).

    Tham so hoa boi `apply_patch`/`label` (Bug #10, generic hoa de dung chung
    cho ca patch ParagraphFinder (Bug #7) lan patch Typesetting (Bug #10)) —
    moi instance boc DUNG 1 module muc tieu voi DUNG 1 ham patch, nen loi cua
    module nay khong lam anh huong module kia (BA10.7 rang buoc #1: rollback
    doc lap)."""

    def __init__(
        self,
        wrapped_loader: importlib.abc.Loader,
        apply_patch: Callable[[ModuleType], None],
        label: str,
    ) -> None:
        self._wrapped = wrapped_loader
        self._apply_patch = apply_patch
        self._label = label

    def create_module(self, spec):
        create = getattr(self._wrapped, "create_module", None)
        return create(spec) if create is not None else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        try:
            self._apply_patch(module)
        except Exception:
            logger.warning(
                "babeldoc_shim: KHONG the ap patch %s — babeldoc se chay tiep "
                "voi hanh vi GOC (khong patch). Co the do version babeldoc da "
                "doi cau truc code so voi 0.6.4.",
                self._label,
                exc_info=True,
            )


class _ModulePatchFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder: chi can thiep dung 1 lan cho dung 1 module muc tieu,
    de nguyen moi import khac cho co che chuan cua Python xu ly.

    Generic hoa (Bug #10, doi ten tu `_ParagraphFinderPatchFinder`) de dung
    chung cho ca 2 module muc tieu (`paragraph_finder` va `typesetting`) — 2
    instance RIENG BIET, khong chia se trang thai `_resolving`, nen 1 loader
    that bai khong anh huong loader con lai.
    """

    def __init__(
        self,
        target_fullname: str,
        apply_patch: Callable[[ModuleType], None],
        label: str,
    ) -> None:
        self._target_fullname = target_fullname
        self._apply_patch = apply_patch
        self._label = label
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

        spec.loader = _PatchingLoader(spec.loader, self._apply_patch, self._label)
        return spec


def _install_patch_hook(
    target_fullname: str,
    apply_patch: Callable[[ModuleType], None],
    label: str,
) -> None:
    """Cai hook cho DUNG 1 module muc tieu (Bug #10: tach ra tu than
    `_install_hook_if_version_matches` de goi 2 lan doc lap — mot cho
    `paragraph_finder`, mot cho `typesetting`, moi loi that bai chi anh huong
    dung module do, BA10.7 bang "Vi tri sua", dong `:597`)."""
    if target_fullname in sys.modules:
        # Da import roi (khong nen xay ra trong luong CLI binh thuong vi
        # sitecustomize chay truoc entry point, nhung fail-safe: thu patch
        # truc tiep thay vi cai hook cho mot import se khong bao gio toi).
        try:
            apply_patch(sys.modules[target_fullname])
        except Exception:
            logger.warning(
                "babeldoc_shim: module %s da duoc import truoc do va patch "
                "truc tiep that bai — babeldoc chay voi hanh vi goc.",
                label,
                exc_info=True,
            )
        return

    sys.meta_path.insert(0, _ModulePatchFinder(target_fullname, apply_patch, label))


def _install_hook_if_version_matches() -> None:
    try:
        import babeldoc
    except Exception:  # noqa: BLE001 - khong co babeldoc thi khong lam gi ca
        return

    version = getattr(babeldoc, "__version__", None)
    if version != _EXPECTED_BABELDOC_VERSION:
        logger.warning(
            "babeldoc_shim: babeldoc version '%s' khac voi version da verify "
            "('%s') — KHONG ap patch Bug #7/#10 (Protocol 5 muc 5: doi "
            "version phai verify lai contract truoc). babeldoc chay voi hanh "
            "vi goc.",
            version,
            _EXPECTED_BABELDOC_VERSION,
        )
        return

    _install_patch_hook(
        _PARAGRAPH_FINDER_MODULE_NAME,
        _apply_paragraph_finder_patch,
        f"ParagraphFinder (Bug #7, {_PARAGRAPH_FINDER_MODULE_NAME})",
    )
    _install_patch_hook(
        _TYPESETTING_MODULE_NAME,
        _apply_typesetting_patch,
        f"Typesetting (Bug #10, {_TYPESETTING_MODULE_NAME})",
    )


try:
    _install_hook_if_version_matches()
except Exception:
    logger.warning("babeldoc_shim: loi khong luong truoc khi cai hook.", exc_info=True)
