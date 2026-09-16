"""EPUB structure parser + in-place writer for US-22 (Architecture.md 6.20).

Bước 1/3 của US-22: chỉ parse cấu trúc EPUB thành các `EpubUnit` dịch được,
chunk theo chương (`src/core/chunking.py::plan_epub_chunks`), và ghi ngược bản
dịch bằng `zipfile` tại chỗ. KHÔNG gọi `provider.translate()`, KHÔNG đụng
cost_estimator/cost_gate, KHÔNG wire vào job_orchestrator — đó là bước 2/3.

Nguồn thiết kế chốt: Architecture.md 6.20.12 "Final Decision sau phản biện
Domain Expert" — mục này SUPERSEDE các đoạn tương ứng của 6.20.5 đã đánh dấu
⚠️ tại chỗ. Ba quyết định cốt lõi module này tuân theo:
  - X1+X2: unit là INNER-HTML (không phải text thuần), `<sup>`/`<sub>` đi qua
    nguyên vẹn — vì đích là EPUB→EPUB (XHTML→XHTML), không có bước chiếu sang
    Markdown nào ở đây (đó là §6.21, nhánh US-15 riêng, không thuộc module này).
  - X6: `doc_href` PHẢI join `opf_dir` (từ META-INF/container.xml) với
    `item.file_name` của ebooklib — `item.file_name` một mình KHÔNG khớp entry
    thật trong zip (tự verify lại: 0/5 khớp thẳng, 5/5 khớp sau khi join).
  - Y3: `ordinal` đếm trên MỌI node thuộc danh sách tag (sau khi lọc node lồng
    nhau + node "bb-vi" của lần dịch trước), TRƯỚC khi áp drop rule nội dung
    (rỗng/toàn số/URL/ISBN) — để tweak drop rule sau này không làm resume lệch.

`write_translated()` bilingual=False — Y2(c) (Architecture.md 6.20.12, dòng
5591, cột "Quyết định" = "NHẬN toàn bộ", THẮNG so với mô tả nháp ở §6.20.5
bước 2 "thay nội dung node bằng fragment HTML đã dịch"): CHỈ thay text node,
KHÔNG đụng element con — nếu không sẽ mất `<img>` nằm trong node unit (10
`<img>` đo được trên file mẫu, luôn nằm trong `<p>` không có text nào khác
nên hiện bị `_is_droppable_content` loại khỏi `units` — an toàn với dữ liệu
mẫu hiện có — nhưng rule này PHẢI đúng tổng quát cho mọi EPUB khác nơi ảnh
và chữ chú thích nằm chung 1 `<p>`, không riêng file mẫu). Cách làm
(`_apply_translation` nhánh `not bilingual`):
  - Nếu subtree của unit KHÔNG có tag nào ngoài `_INLINE_PRESERVE_TAGS` (danh
    sách "giữ nguyên thẻ inline" của contract X4, §6.20.12 dòng 5541-5542):
    an toàn dùng `node.clear()` + append fragment dịch nguyên khối như cũ —
    LLM cam kết giữ đúng số lượng/vị trí các thẻ này.
  - Nếu CÓ tag ngoài danh sách đó (vd `<img>`): KHÔNG tin cấu trúc LLM trả về
    cho tag đó. Gom danh sách text node gốc (`_text_runs_under`, đệ quy, bỏ
    qua `<code>`/`<pre>` theo X4 — dùng CHUNG hàm này cho cả subtree gốc lẫn
    fragment đã dịch, để 2 phía cùng 1 định nghĩa "slot"). Nếu chỉ có 1
    "slot" — thay đúng node đó bằng fragment dịch (`NavigableString.
    replace_with`), mọi tag khác (kể cả `<img>`) không bị đụng vì không có
    lệnh nào xoá/thay chúng. Nếu có NHIỀU slot: cố khớp 1-1 với các đoạn text
    trong bản dịch theo đúng thứ tự; khớp số lượng thì gán 1-1, KHÔNG khớp
    thì áp dụng fallback đã biết giới hạn (xem khối comment "Known
    limitation" ngay dưới docstring này) — **gap này KHÔNG có thuật toán
    tường minh trong Architecture.md, đã báo cáo lại PM kèm phương án đã
    chọn (2026-09-09), chưa có phản hồi ngược lại yêu cầu đổi hướng.**

Y2(d) (Architecture.md 6.20.12, dòng 5591, "NHẬN toàn bộ" — bắt buộc, không
phải tuỳ chọn): `li` chứa `ul`/`ol` con (list lồng list) KHÔNG được gộp thành
1 unit khổng lồ chứa markup `<ul>/<li>` thô — markup đó nằm ngoài contract X4
(`_INLINE_PRESERVE_TAGS`), hành vi LLM với nó là không xác định. Thay vào đó
tách thành nhiều unit độc lập, đệ quy tới tận "innermost" (lá có text trực
tiếp): `_has_unit_tag_ancestor`/`_crosses_list_container` cho phép `li` con
bên trong `ul`/`ol` lồng trở thành candidate riêng (khác quy tắc lồng đơn
giản `li > p` vẫn giữ outermost theo §6.20.5); `_strip_nested_lists` loại bỏ
`<ul>/<ol>` con khỏi text/HTML của unit cha trước khi trích (tránh dịch đôi +
tránh markup thô lọt vào prompt); `_collect_runs_recursive` chặn text bên
trong `<ul>/<ol>` lồng khỏi bị tính là "slot" của unit cha ở
`write_translated()` (tránh ghi đè nhầm sang nội dung của unit con).
"""

# Known limitation (đã báo cáo PM 2026-09-09, xem tin nhắn Dev cùng ngày):
# khi 1 unit có NHIỀU text node xen kẽ với tag ngoài _INLINE_PRESERVE_TAGS
# (vd `<img>` chen giữa 2 câu) VÀ bản dịch LLM trả về không giữ đúng số
# lượng đoạn text tương ứng (vd LLM gộp 2 câu thành 1), app KHÔNG có cách
# tường minh nào (chưa có trong Architecture.md) để chia lại bản dịch cho
# đúng từng text node gốc. Fallback: gán TOÀN BỘ bản dịch vào text node dài
# nhất (khả năng cao là nội dung chính), các text node còn lại GIỮ NGUYÊN
# tiếng Anh gốc (không xoá, không đoán) — ưu tiên "không mất/không hỏng cấu
# trúc" hơn "dịch đủ 100% mọi từ" ở đúng ca hiếm này. Không xảy ra trên 2 file
# mẫu hiện có (10 `<img>` đo được đều nằm trong `<p>` KHÔNG có text nào khác,
# nên bị drop khỏi `units` từ trước, chưa từng đi tới nhánh `write_translated`
# này) — nhưng rule Y2(c) áp dụng tổng quát cho MỌI EPUB, không riêng 2 file
# mẫu, nên vẫn phải xử lý được ca tổng quát.

from __future__ import annotations

import copy
import logging
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import markdownify
from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
from ebooklib import epub

from src.core.config import get_settings

logger = logging.getLogger(__name__)

#: Quy tắc chọn unit dùng CHUNG với §6.15 S15-8 (Architecture.md 6.20.5).
UNIT_TAG_NAMES: tuple[str, ...] = (
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "blockquote",
    "td",
    "th",
    "dt",
    "dd",
    "figcaption",
)

_BB_VI_CLASS = "bb-vi"
_BB_VI_LANG = "vi"

#: Architecture.md §6.20.14.4 C-4 (Lop C, 2026-09-10) — danh dau unit fallback
#: (giu nguyen tieng Anh vi khong cuu duoc ke ca sau Lop B, §6.20.14.3).
_BB_UNTRANSLATED_CLASS = "bb-untranslated"
_BB_UNTRANSLATED_LANG = "en"

_ALL_DIGITS_WS_RE = re.compile(r"^[\d\s]*$")
_URL_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)
# Y8 (Architecture.md 6.20.12): rule la unit CHI chua ISBN, khong phai "chua
# ISBN" — mot doan co ten sach/tac gia truoc ISBN van phai duoc dich.
_ISBN_ONLY_RE = re.compile(r"^ISBN(?:-1[03])?[\s:-]*[\dXx][\dXx\s-]*$", re.IGNORECASE)

_ENC_XML_NS = {"enc": "http://www.w3.org/2001/04/xmlenc#"}
_FONT_EXTENSIONS = (".ttf", ".otf", ".woff", ".woff2")

#: X4 contract (Architecture.md 6.20.12, dòng 5541-5542): thẻ inline LLM
#: CAM KẾT giữ nguyên đúng số lượng + vị trí tương đối khi dịch. Bất kỳ tag
#: NGOÀI danh sách này (vd `<img>`) không có cam kết đó — Y2(c) cấm tin cấu
#: trúc LLM trả về cho các tag này.
_INLINE_PRESERVE_TAGS = frozenset(
    {"strong", "em", "b", "i", "sup", "sub", "br", "a", "span", "small"}
)
#: X4: "Không dịch nội dung trong `<code>`/`<pre>`" — không đi vào subtree
#: này khi gom text node cần thay/so khớp.
_NO_TRANSLATE_TAGS = frozenset({"code", "pre"})
#: Y2(d) (Architecture.md 6.20.12 dong 5591): `li > ul`/`li > ol` long PHAI
#: tach unit theo "innermost" -- khac han quy tac long don gian S6.20.5 (`li
#: > p` giu outermost). Dung o ca `_has_unit_tag_ancestor` (cho phep `li` con
#: trong `ul`/`ol` long tro thanh unit rieng thay vi bi dedup) lan
#: `_collect_runs_recursive` (chan "slot" text cua unit cha lan vao subtree
#: da tach rieng cho unit con, tranh ghi de sai unit o `write_translated`).
_LIST_CONTAINER_TAGS = frozenset({"ul", "ol"})

#: Bug #EPUB-1 (QA vong 1 US-22 buoc 1/3, 2026-09-09): `vi_html` la PLAIN TEXT
#: LLM tra ve (co the xen it the nam trong _INLINE_PRESERVE_TAGS neu LLM giu
#: dung X4), KHONG phai HTML da escape san. Neu dua thang vao
#: `_fragment_children()` de re-parse nhu XML (`features="xml"` qua lxml),
#: bat ky `&` khong phai 1 phan cua entity hop le hay `<` tran nao cung lam
#: XML khong well-formed -- lxml "chua chay" bang cach am tham CAT BO phan
#: noi dung sau do, KHONG raise loi (`_validate_wellformed` khong bat duoc vi
#: ket qua sau khi cat van la XML hop le). Da tu verify truc tiep:
#: `BeautifulSoup("<bb-fragment-root>Do am < 65%</bb-fragment-root>", "xml")`
#: chi con lai text truoc dau `<`, mat toan bo phan sau dau lang. Fix: escape
#: moi `&`/`<` tran thanh entity TRUOC khi re-parse, tru cac the nam trong
#: _INLINE_PRESERVE_TAGS (van phai parse thanh Tag that de X4 hoat dong).
_INLINE_TAG_ALTERNATION = "|".join(sorted(_INLINE_PRESERVE_TAGS, key=len, reverse=True))
_TRUSTED_TAG_OR_BARE_LT_RE = re.compile(
    rf"</?(?:{_INLINE_TAG_ALTERNATION})(?:\s[^<>]*)?/?>|<", re.IGNORECASE
)
#: Ten entity coi la "da escape san" — moi `&` khac (vd trong "A&W", "dough &
#: set") la ky tu & tran trong van ban thuong, khong phai LLM tu escape.
_BARE_AMP_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")


def _escape_untrusted_markup(vi_html: str) -> str:
    """Escape `&`/`<` tran trong `vi_html` (ban dich LLM, plain text) truoc
    khi dua vao `_fragment_children()` de re-parse nhu XML/HTML — giu nguyen
    cac the nam trong `_INLINE_PRESERVE_TAGS` (X4) de chung van duoc parse
    thanh Tag that thay vi bi escape nham thanh text. Khong dong den `>` tran
    — XML khong yeu cau escape `>` don le trong text content (chi chuoi
    `]]>` moi can, ca hiem gap ngoai pham vi bug nay)."""
    escaped = _BARE_AMP_RE.sub("&amp;", vi_html)
    return _TRUSTED_TAG_OR_BARE_LT_RE.sub(
        lambda m: "&lt;" if m.group(0) == "<" else m.group(0), escaped
    )


#: §6.21.2 Buoc 1 — text node phan cach phan so PHAI chi chua DUNG 1 trong 2
#: ky tu nay (khong strip whitespace them: "chi chua" trong Architecture.md
#: la nghia den).
_FRACTION_SEP_CHARS = frozenset({"/", "⁄"})
#: §6.21.2 Buoc 2 — dieu kien "thuan so/dau" de xet mapping Unicode.
_NUMERIC_PUNCT_RE = re.compile(r"^[0-9+\-=()]+$")
_SINGLE_ALPHA_RE = re.compile(r"^[A-Za-z]$")

#: Bang anh xa Unicode §6.21.2 (du cho hoa hoc pho thong + so mu so hoc).
_SUP_UNICODE_MAP: dict[str, str] = dict(zip("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ", strict=True))
_SUB_UNICODE_MAP: dict[str, str] = dict(
    zip("0123456789+-=()aeoxhklmnpst", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ", strict=True)
)


def _all_digits(text: str) -> bool:
    return bool(text) and text.isdigit()


def _extract_mixed_number_fractions(soup: BeautifulSoup) -> None:
    """§6.21.2 Buoc 1 (uu tien cao nhat, chay TRUOC Buoc 2): pattern
    `<sup>N</sup>` + text node CHI chua "/" hoac "⁄" (U+2044) + `<sub>M</sub>`
    (N, M la chuoi chu so) -> gop ca 3 node thanh MOT text node "N/M".

    Guard hon so (day la CHINH cho cach lam cua Expert hong, §6.21.2 F-2):
    neu ky tu NGAY TRUOC `<sup>` la 1 chu so, chen them 1 dau cach truoc phan
    so -> `1<sup>1</sup>/<sub>3</sub>` ra "1 1/3", KHONG phai "11/3".
    """
    for sup in list(soup.find_all("sup")):
        numerator = sup.get_text().strip()
        if not _all_digits(numerator):
            continue
        separator = sup.next_sibling
        if not isinstance(separator, NavigableString) or str(separator) not in _FRACTION_SEP_CHARS:
            continue
        denominator_node = separator.next_sibling
        if not (isinstance(denominator_node, Tag) and denominator_node.name == "sub"):
            continue
        denominator = denominator_node.get_text().strip()
        if not _all_digits(denominator):
            continue

        prev = sup.previous_sibling
        needs_space = isinstance(prev, NavigableString) and str(prev)[-1:].isdigit()
        prefix = " " if needs_space else ""
        sup.replace_with(NavigableString(f"{prefix}{numerator}/{denominator}"))
        separator.extract()
        denominator_node.decompose()


def _unicode_supsub(content: str, table: dict[str, str]) -> str | None:
    """§6.21.2 Buoc 2: tra ve dang Unicode neu `content` khop dieu kien
    (thuan `[0-9+\\-=()]+` HOAC dung 1 chu cai) VA MOI ky tu cua no co mapping
    trong `table` — nguoc lai tra None (bao hieu Dev goi `_ascii_supsub()`)."""
    if not content:
        return None
    if not (_NUMERIC_PUNCT_RE.fullmatch(content) or _SINGLE_ALPHA_RE.fullmatch(content)):
        return None
    if not all(ch in table for ch in content):
        return None
    return "".join(table[ch] for ch in content)


def _ascii_supsub(content: str, marker: str) -> str:
    """§6.21.2 Buoc 2, fallback ASCII: `^(c)` cho sup, `_(c)` cho sub — neu
    `c` da bat dau bang "(" va ket thuc bang ")" thi KHONG boc them ngoac
    (`(n-1)` -> `^(n-1)`, khong phai `^((n-1))`)."""
    if content.startswith("(") and content.endswith(")"):
        return f"{marker}{content}"
    return f"{marker}({content})"


def normalize_sup_sub(soup: BeautifulSoup, *, style: str = "unicode") -> None:
    """Architecture.md §6.21.2 — chuan hoa MOI `<sup>`/`<sub>` con lai trong
    `soup` sang bieu dien Markdown-an-toan (Unicode hoac Pandoc `^..^`/`~..~`
    tuy `style`, xem `Settings.markdown_supsub_style`). CHAY TRUOC khi goi
    `markdownify` — doc lap hoan toan voi `sup_symbol`/`sub_symbol` mac dinh
    cua thu vien do (Protocol 5: khong phu thuoc hanh vi ngam dinh ben thu
    ba). Sau khi chay xong, khong con the `sup`/`sub` nao trong `soup`.

    CHI dung boi `EpubDocument.to_markdown()` (dich EPUB->Markdown, US-15).
    KHONG duoc dung cho luong `units`/`write_translated()` cua US-22 — X2
    (Architecture.md 6.20.12) giu `<sup>`/`<sub>` nguyen ven khi dich
    EPUB->EPUB, vi dich XHTML->XHTML khong can chieu sang Markdown.
    """
    _extract_mixed_number_fractions(soup)

    for node in list(soup.find_all(("sup", "sub"))):
        content = node.get_text().strip()
        is_sup = node.name == "sup"
        if style == "pandoc":
            marker = "^" if is_sup else "~"
            replacement = f"{marker}{content}{marker}"
        else:
            table = _SUP_UNICODE_MAP if is_sup else _SUB_UNICODE_MAP
            unicode_form = _unicode_supsub(content, table)
            replacement = (
                unicode_form
                if unicode_form is not None
                else _ascii_supsub(content, "^" if is_sup else "_")
            )
        node.replace_with(NavigableString(replacement))


_EXTERNAL_OR_DATA_URI_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:)", re.IGNORECASE)


def _is_external_or_data_uri(src: str) -> bool:
    """§6.15.7 muc B: `src` la URL tuyet doi (`http://...`) hoac `data:` URI
    -> giu nguyen, KHONG copy (khong phai anh nhung trong zip). Bat theo
    scheme URI tong quat (`scheme:`), khong chi `http(s)`/`data`, de khong bo
    sot cac scheme khac (vd `mailto:`) — an toan hon la chi liet ke 2 ten."""
    return bool(_EXTERNAL_OR_DATA_URI_RE.match(src))


def _rewrite_image_srcs(
    soup: BeautifulSoup,
    doc_href: str,
    zf: zipfile.ZipFile,
    zip_names: set[str],
    images_out_dir: Path,
    entry_to_target: dict[str, str],
    bytes_by_target: dict[str, bytes],
) -> None:
    """§6.15.7 muc B: copy bytes cua moi `<img>` nhung trong `soup` (tai
    lieu `doc_href`) ra `images_out_dir`, roi rewrite `img["src"]` tro dung
    file da copy — de `markdownify` sau do tu sinh `![alt](images/x.jpg)`.

    Diem de sai nhat (Architecture.md nhan manh): `src` tuong doi so voi
    CHINH `doc_href`, KHONG phai `opf_dir` (`doc_href` da la duong dan
    tuyet doi trong zip, vi `load()` da join `opf_dir` theo X6).

    `entry_to_target`/`bytes_by_target` la trang thai DUNG CHUNG cho CA
    cuon sach (nhieu loi goi ham nay, moi lan 1 doc_href) — de:
    - cung 1 zip_entry duoc tham chieu > 1 lan (nhieu trang cung dung 1
      anh) chi copy MOT LAN, dung lai dung target_name.
    - basename trung nhau giua 2 thu muc KHAC nhau trong zip: neu bytes
      GIONG nhau, gop chung 1 file dich; neu bytes KHAC nhau, them hau to
      tang dan (`f01_2.jpg`) — khong ghi de im lang (mat anh), khong de 2
      link Markdown tro nham vao nhau.
    """
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        if _is_external_or_data_uri(src):
            continue
        zip_entry = posixpath.normpath(posixpath.join(posixpath.dirname(doc_href), src))

        target_name = entry_to_target.get(zip_entry)
        if target_name is None:
            if zip_entry not in zip_names:
                # Khong raise (khac guard X6 cua load()): 1 anh hong khong
                # duoc lam hong ca job parse-only. Giu src nguyen trang.
                logger.warning(
                    "EPUB to_markdown(): anh '%s' (src='%s' trong '%s') khong "
                    "ton tai trong zip — bo qua, giu src nguyen trang",
                    zip_entry,
                    src,
                    doc_href,
                )
                continue
            data = zf.read(zip_entry)
            basename = posixpath.basename(zip_entry)
            target_name = basename
            stem, dot, ext = basename.rpartition(".")
            suffix = 2
            while target_name in bytes_by_target and bytes_by_target[target_name] != data:
                target_name = f"{stem}_{suffix}{dot}{ext}" if dot else f"{basename}_{suffix}"
                suffix += 1
            bytes_by_target[target_name] = data
            entry_to_target[zip_entry] = target_name
            (images_out_dir / target_name).write_bytes(data)

        img["src"] = f"images/{target_name}"


class EpubDrmError(RuntimeError):
    """Raised by `load()` when the EPUB carries real DRM (not just font
    obfuscation) — Architecture.md 6.20.5 DRM section (EC-22.1 / YA-6.6)."""


class EpubParseError(RuntimeError):
    """Raised for any structural problem: not a valid zip/EPUB, missing
    container.xml/OPF, a spine document whose entry does not exist in the
    zip (X6 lineage trap), or a translated fragment that fails to reparse
    into well-formed XHTML (Y1) when writing back."""


@dataclass(frozen=True)
class EpubUnit:
    """Một đơn vị dịch được. `text` là INNER-HTML (X2), KHÔNG phải text
    thuần — giữ nguyên `<strong>`, `<sup>`/`<sub>`, `<br/>`, v.v."""

    unit_id: str
    doc_href: str
    tag: str
    ordinal: int
    text: str


def _node_classes(node: Tag) -> list[str]:
    """Chuẩn hoá `node.get("class")` về `list[str]`, bất kể bs4 trả `list`
    (builder HTML coi `class` là multi-valued attribute) hay `str` (builder
    XML — `features="xml"`, dùng CHÍNH cho `EpubDocument` theo Y1 — KHÔNG coi
    `class` multi-valued, trả nguyên chuỗi vd `"noindent"`). Bug đã tái hiện
    trên file EPUB thật (Reviewer, vòng 1/3 US-22 Bước 2/3): unpack `*existing`
    trên 1 chuỗi tách thành TỪNG KÝ TỰ (`"noindent"` -> `['n','o','i',...]`),
    hỏng attribute `class` trên MỌI node gốc có sẵn class thật (rất phổ biến
    trong EPUB dàn trang thật, vd `class="noindent"`), khiến guard BR-EPUB-05
    fail 0/384 dù đã dịch đầy đủ. Dùng helper này ở MỌI chỗ đọc/ghi `class`
    trong module để không tái diễn lệch giả định."""
    classes = node.get("class") or []
    if isinstance(classes, str):
        return classes.split()
    return list(classes)


def _has_bb_vi_class(node: Tag) -> bool:
    return _BB_VI_CLASS in _node_classes(node)


def _in_bb_vi_subtree(node: Tag) -> bool:
    for ancestor in (node, *node.parents):
        if isinstance(ancestor, Tag) and _has_bb_vi_class(ancestor):
            return True
    return False


def _nearest_unit_ancestor(node: Tag) -> Tag | None:
    for ancestor in node.parents:
        if isinstance(ancestor, Tag) and ancestor.name in UNIT_TAG_NAMES:
            return ancestor
    return None


def _crosses_list_container(node: Tag, ancestor: Tag) -> bool:
    """True neu co it nhat 1 the `<ul>`/`<ol>` nam GIUA `node` va `ancestor`
    (khong tinh chinh `ancestor`) -- day la dau hieu Y2(d): `node` la 1 `li`
    long trong 1 danh sach con CUA `ancestor`, phai tro thanh unit RIENG,
    khac voi luong long don gian (vd `li > p`, khong co `ul`/`ol` xen giua)
    van chi giu outermost theo S6.20.5."""
    current = node.parent
    while current is not None and current is not ancestor:
        if isinstance(current, Tag) and current.name in _LIST_CONTAINER_TAGS:
            return True
        current = current.parent
    return False


def _has_unit_tag_ancestor(node: Tag) -> bool:
    """S6.20.5: node long nhau (vd `li > p`) chi giu node NGOAI CUNG -- TRU
    ca Y2(d) (`li > ul > li`): `node` van la 1 unit RIENG neu duong di toi
    ancestor gan nhat bang qua >= 1 the danh sach (`<ul>`/`<ol>`), de quy
    duoc voi long nhieu cap (`li > ul > li > ul > li`, moi `li` la ke la co
    text truc tiep deu thanh 1 unit doc lap)."""
    ancestor = _nearest_unit_ancestor(node)
    if ancestor is None or _has_bb_vi_class(ancestor):
        return False
    return not _crosses_list_container(node, ancestor)


def _collect_candidate_nodes(soup: BeautifulSoup) -> list[Tag]:
    """Danh sách node theo đúng thứ tự tài liệu, sau khi:
    - bỏ node nằm trong 1 subtree mang class `bb-vi` (X3 — bản dịch song ngữ
      của lần chạy trước, tránh dịch đôi khi upload lại chính output).
    - với node lồng nhau (vd `li` chứa `p`), chỉ giữ node NGOÀI CÙNG.

    Đây CHÍNH LÀ tập "MỌI node thuộc danh sách tag" mà Y3 dùng để đếm
    `ordinal` — PHẢI dùng lại nguyên hàm này ở cả `load()` lẫn
    `write_translated()` để ordinal ổn định giữa 2 lần chạy (R6-02).
    """
    raw = soup.find_all(UNIT_TAG_NAMES)
    candidates: list[Tag] = []
    for node in raw:
        if _in_bb_vi_subtree(node):
            continue
        if _has_unit_tag_ancestor(node):
            continue
        candidates.append(node)
    return candidates


def _is_droppable_content(node: Tag) -> bool:
    """Bỏ unit nếu: rỗng sau strip, toàn chữ số/khoảng trắng, là URL, hoặc
    CHỈ chứa ISBN (Y8) — áp dụng SAU khi ordinal đã được gán (Y3)."""
    plain = node.get_text(" ", strip=True)
    if not plain:
        return True
    if _ALL_DIGITS_WS_RE.fullmatch(plain):
        return True
    if _URL_RE.fullmatch(plain):
        return True
    return bool(_ISBN_ONLY_RE.fullmatch(plain))


def _inner_html(node: Tag) -> str:
    """Bug #EPUB-1 (QA vong 1 US-22 buoc 1/3): `Tag.decode_contents()` la API
    dung cua bs4 cho inner-HTML — TU escape dung `&`/`<`/`>` cho ca `Tag` lan
    `NavigableString` con khi serialize. Cach cu (`"".join(str(child) for
    child in node.children)`) sai vi `str()` cua 1 `NavigableString` DA BI
    TACH KHOI cay tra ve text da decode, KHONG re-escape (tu verify:
    `str(NavigableString)` cho `<p>a &amp; b</p>` ra `'a & b'`, khong phai
    `'a &amp; b'`) — chuoi chua escape nay sau do lam hong X2 (`unit.text`
    duoc ghi la "INNER-HTML" nhung thuc te khong phai HTML hop le khi co
    `&`/`<`)."""
    return node.decode_contents()


def _strip_nested_lists(node: Tag) -> Tag:
    """Y2(d): ban COPY doc lap cua `node`, da bo toan bo `<ul>`/`<ol>` con
    (moi cap sau, khong chi truc tiep) -- moi `<li>` ben trong cac the do da
    tro thanh unit RIENG (xem `_has_unit_tag_ancestor`), nen text/HTML cua
    CHINH `node` khong duoc gom lai markup danh sach con do (tranh dich 2
    lan cung noi dung + tranh unit cha chua markup `<ul>/<li>` tho ngoai
    contract X4 khi gui cho LLM). Dung `copy.deepcopy` (khong sua truc tiep
    tren soup that dang dich) roi `decompose()` -- da tu kiem chung khong
    lam sai lech serialize (`str()`) so voi node goc cho phan con lai."""
    clone = copy.deepcopy(node)
    for list_tag in clone.find_all(_LIST_CONTAINER_TAGS):
        list_tag.decompose()
    return clone


#: K-1 (Architecture.md §6.20.15) — CHI token class nay, KHONG tong quat hoa
#: (Protocol 8 R8-02, deny-by-default).
_KOBO_SPAN_CLASS = "koboSpan"


def _unwrap_kobo_spans(soup: BeautifulSoup) -> None:
    """K-1 (Architecture.md §6.20.15) — unwrap (KHONG decompose, giu nguyen
    con ben trong) MOI `<span>` co `class` chua dung token `koboSpan`. Goi
    NGAY sau khi parse xong soup, TRUOC moi buoc khac (`_parse_xhtml()`), la
    diem vao DUY NHAT ma `load()`, `write_translated()`, `count_bb_vi_pairs()`,
    `to_markdown()` deu dung chung -- BAT BUOC o day, KHONG o cho build
    payload (`job_orchestrator.py`), vi `write_translated()` doc lai node GOC
    tu zip qua CHINH `_parse_xhtml()` nay de dem "slot"
    (`_text_runs_under()`); unwrap muon (chi o payload) se lam node goc con
    nhieu koboSpan = nhieu slot trong khi ban dich tra ve gop thanh 1 run ->
    lech slot -> roi vao nhanh "Known limitation" (dich sot cac slot con
    lai). Xem Architecture.md §6.20.15 K-1/K-1b cho so do that + bang tac
    dong len BR-EPUB-05.

    `class` la string (khong phai list) duoi builder "xml" nhung LA list duoi
    "html.parser" -- xu ly ca 2 dang bang `.split()` thay vi dua vao hanh vi
    multi-valued-attribute cua bs4 (chi ap dung cho HTML, khong ap dung cho
    XML). TUYET DOI khong dung `class_="koboSpan"` cua `find_all()` (phu
    thuoc hanh vi parser-specific do).

    KHONG dung toi `<span epub:type="pagebreak" id="page_i"/>` (khong co
    class `koboSpan`) -- `id` cua no DUOC `page-list` tham chieu, xoa se lam
    epubcheck fail.
    """
    for span in soup.find_all("span"):
        class_attr = span.get("class")
        if class_attr is None:
            continue
        classes = class_attr if isinstance(class_attr, list) else class_attr.split()
        if _KOBO_SPAN_CLASS in classes:
            span.unwrap()


def _parse_xhtml(raw_bytes: bytes) -> tuple[BeautifulSoup, str]:
    """§6.20.12 Y1: dùng `features="xml"`; fallback `html.parser` CHỈ khi XML
    parse fail, và chỉ chấp nhận fallback nếu kết quả serialize lại vẫn qua
    được `ET.fromstring()` (điều kiện Tech Lead thêm, không chấp nhận fallback
    mù — `html.parser` hạ `viewBox` thành `viewbox`, hỏng SVG)."""
    try:
        soup = BeautifulSoup(raw_bytes, "xml")
        _unwrap_kobo_spans(soup)
        return soup, "xml"
    except Exception:  # noqa: BLE001, S110 — lxml raises assorted types on malformed XML; any of them means "fall back to html.parser"
        pass
    soup = BeautifulSoup(raw_bytes, "html.parser")
    try:
        ET.fromstring(str(soup).encode("utf-8"))
    except ET.ParseError as exc:
        raise EpubParseError(
            "XHTML khong well-formed va fallback html.parser cung khong cuu duoc"
        ) from exc
    _unwrap_kobo_spans(soup)
    return soup, "html.parser"


def _validate_wellformed(data: bytes, doc_href: str) -> None:
    try:
        ET.fromstring(data)
    except ET.ParseError as exc:
        raise EpubParseError(
            f"'{doc_href}' sau khi ghi ban dich khong con la XHTML well-formed: {exc}"
        ) from exc


def _strip_ids(node: Tag) -> None:
    """Y2(a): bản copy chèn cho `bilingual=True` phải strip mọi `id` — kể cả
    id nằm trên descendant (`<a id="page_N"/>` lồng bên trong đoạn văn) — nếu
    không sẽ tạo `duplicate id`, epubcheck sẽ bắt lỗi này."""
    if "id" in node.attrs:
        del node.attrs["id"]
    for descendant in node.find_all(True):
        if "id" in descendant.attrs:
            del descendant.attrs["id"]


def _mark_bb_vi(node: Tag) -> None:
    node["lang"] = _BB_VI_LANG
    existing = _node_classes(node)
    if _BB_VI_CLASS not in existing:
        node["class"] = [*existing, _BB_VI_CLASS]


def _mark_bb_untranslated(node: Tag) -> None:
    """Architecture.md §6.20.14.4 C-4 (Lop C) — danh dau 1 unit KHONG dich
    duoc (fallback, giu nguyen tieng Anh) NGAY TREN chinh node goc: them
    class `bb-untranslated` + `lang="en"`. KHONG chen node moi, KHONG boc
    `<span>` — day la cach RE NHAT khong dung cau truc file (khac han
    `_mark_bb_vi()`, vi khong co noi dung MOI nao de chen, node da la ban
    goc). Da kiem 2 tac dung phu (Architecture.md C-4): `EpubDocument.load()`
    chi bo qua node theo class `bb-vi` -> them `bb-untranslated` KHONG doi so
    unit doc lai; `count_bb_vi_pairs()` chi dem node `bb-vi` -> khong bi anh
    huong.
    """
    node["lang"] = _BB_UNTRANSLATED_LANG
    existing = _node_classes(node)
    if _BB_UNTRANSLATED_CLASS not in existing:
        node["class"] = [*existing, _BB_UNTRANSLATED_CLASS]


def _fragment_children(soup: BeautifulSoup, html: str, parser_name: str) -> list:
    fragment = BeautifulSoup(f"<bb-fragment-root>{html}</bb-fragment-root>", parser_name)
    root = fragment.find("bb-fragment-root")
    if root is None:
        return []
    return list(root.children)


def _has_untrusted_descendant(node: Tag) -> bool:
    """True neu subtree cua `node` co Tag NGOAI `_INLINE_PRESERVE_TAGS` (vd
    `<img>`) — Y2(c): truong hop nay cam dung `node.clear()+append` vi co the
    mat han tag do neu LLM khong phan chieu dung (10 `<img>` do duoc trong
    data mau, Architecture.md 6.20.12 dong 5591)."""
    return any(descendant.name not in _INLINE_PRESERVE_TAGS for descendant in node.find_all(True))


def _collect_runs_recursive(node: object, runs: list[NavigableString]) -> None:
    if isinstance(node, Comment):
        return
    if isinstance(node, NavigableString):
        if node.strip():
            runs.append(node)
        return
    if isinstance(node, Tag):
        if node.name in _NO_TRANSLATE_TAGS or node.name in _LIST_CONTAINER_TAGS:
            # Y2(d): <ul>/<ol> long da tro thanh (cac) unit RIENG (xem
            # _has_unit_tag_ancestor) -- text ben trong KHONG duoc tinh la
            # "slot" cua unit CHA, neu khong write_translated() se ghi de
            # nham noi dung cua unit con khi khop 1-1/fallback o day.
            return
        for child in node.children:
            _collect_runs_recursive(child, runs)


def _text_runs_under(nodes: list) -> list[NavigableString]:
    """Danh sach NavigableString non-whitespace, de quy, DUNG THU TU tai
    lieu, bo qua Comment, noi dung trong `<code>`/`<pre>` (X4), va noi dung
    trong `<ul>`/`<ol>` long (Y2(d) -- da tro thanh unit rieng). Dung cho
    ca subtree GOC (`node.children`) lan fragment DA DICH da parse — cung
    1 dinh nghia "slot" cho 2 phia de con zip 1-1 duoc (Y2(c))."""
    runs: list[NavigableString] = []
    for child in nodes:
        _collect_runs_recursive(child, runs)
    return runs


def _apply_translation_untrusted_structure(node: Tag, translated_children: list) -> None:
    """Y2(c): subtree co tag ngoai `_INLINE_PRESERVE_TAGS` (vd `<img>`) —
    KHONG duoc goi `node.clear()`, chi duoc thay NOI DUNG cac text node goc,
    moi Tag (ke ca tag khong tin duoc) giu nguyen vi tri vi khong bao gio bi
    xoa/thay the."""
    slots = _text_runs_under(list(node.children))
    if not slots:
        # Khong co gi de dich ngoai chinh tag khong tin duoc (vd <p><img/></p>
        # thuan tuy, get_text() rong nen thuc te khong bao gio thanh unit —
        # nhung van giu nhanh nay cho an toan/tuong minh) — khong dong gi.
        return

    if len(slots) == 1:
        # Ca don gian, khong nhap nhang: toan bo noi dung dich (giu nguyen
        # cau truc the inline neu LLM tra dung, vd <b>) thay dung 1 slot nay.
        slots[0].replace_with(*translated_children)
        return

    # Nhieu slot xen ke tag khong tin duoc — co gang khop 1-1 theo dung thu
    # tu tai lieu voi cac doan text trong ban dich.
    translated_runs = _text_runs_under(translated_children)
    if len(translated_runs) == len(slots):
        for original_slot, translated_run in zip(slots, translated_runs):
            original_slot.replace_with(str(translated_run))
        return

    # Fallback da biet gioi han (xem docstring dau file, "Known limitation"):
    # khong co thuat toan tuong minh trong Architecture.md cho ca lech so
    # luong "slot". Gan toan bo ban dich vao slot dai nhat (nhieu ky tu goc
    # nhat — heuristic "noi dung chinh"), cac slot con lai GIU NGUYEN tieng
    # Anh goc — uu tien khong mat/khong hong cau truc hon dich du 100% o ca
    # hiem nay.
    if translated_runs:
        translated_text = "".join(str(run) for run in translated_runs)
    else:
        translated_text = "".join(str(child) for child in translated_children)
        translated_text = BeautifulSoup(translated_text, "html.parser").get_text()
    main_slot = max(slots, key=len)
    main_slot.replace_with(translated_text)


def _apply_translation(
    soup: BeautifulSoup,
    node: Tag,
    vi_html: str,
    *,
    bilingual: bool,
    parser_name: str,
) -> None:
    # Bug #EPUB-1: `vi_html` la plain text tu LLM, chua chac da escape dung
    # `&`/`<` — sanitize truoc khi bat ky nhanh nao ben duoi goi
    # `_fragment_children()` de re-parse nhu XML/HTML.
    vi_html = _escape_untrusted_markup(vi_html)
    if not bilingual:
        translated_children = _fragment_children(soup, vi_html, parser_name)
        if _has_untrusted_descendant(node):
            # Y2(c) (Architecture.md 6.20.12 dong 5591, THANG so voi mo ta
            # nhap o §6.20.5 buoc 2): CHI thay text node, KHONG dung element
            # con — neu khong se mat cac tag ngoai contract giu-nguyen (vd
            # <img>, 10 cai do duoc tren file mau).
            _apply_translation_untrusted_structure(node, translated_children)
        else:
            # An toan dung ca node.clear()+append: moi tag con deu thuoc
            # _INLINE_PRESERVE_TAGS, LLM cam ket giu dung so luong/vi tri
            # (X4), giu nguyen tag/class/style cua chinh node.
            node.clear()
            for child in translated_children:
                node.append(child)
        return

    # bilingual=True (Y2 + X3): chen THEM, khong thay the ban goc.
    if node.name in ("td", "th"):
        # Y2(b): chen BEN TRONG o, khong insert_after (se tao them cot moi).
        br = soup.new_tag("br")
        node.append(br)
        span = soup.new_tag("span")
        for child in _fragment_children(soup, vi_html, parser_name):
            span.append(child)
        _mark_bb_vi(span)
        node.append(span)
        return

    copy_node = copy.deepcopy(node)
    copy_node.clear()
    for child in _fragment_children(soup, vi_html, parser_name):
        copy_node.append(child)
    _strip_ids(copy_node)
    _mark_bb_vi(copy_node)
    node.insert_after(copy_node)


@dataclass
class EpubDocument:
    path: Path
    opf_dir: str
    _units: list[EpubUnit] = field(default_factory=list)
    #: §6.15.7 muc A — `doc_href` theo DUNG thu tu spine, tinh ĐÚNG MỘT LẦN
    #: trong `load()` (khong giu lai soup nao — `to_markdown()` mo lai zip
    #: va parse lai tung doc theo danh sach nay, expose qua `spine_hrefs`).
    _spine_hrefs: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> EpubDocument:
        path = Path(path)
        try:
            zf = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, FileNotFoundError, OSError) as exc:
            raise EpubParseError(f"Khong mo duoc EPUB '{path}': {exc}") from exc

        with zf:
            names = set(zf.namelist())
            _check_drm(zf, names)
            _check_mimetype_entry(zf, names, path)

            try:
                container = zf.read("META-INF/container.xml").decode("utf-8")
            except KeyError as exc:
                raise EpubParseError(f"EPUB '{path}' thieu META-INF/container.xml") from exc
            match = re.search(r'full-path="([^"]+)"', container)
            if not match:
                raise EpubParseError(
                    f"EPUB '{path}' co container.xml nhung khong tim thay rootfile full-path"
                )
            opf_full_path = match.group(1)
            opf_dir = posixpath.dirname(opf_full_path)

            try:
                book = epub.read_epub(str(path))
            except Exception as exc:  # ebooklib raises assorted exceptions
                raise EpubParseError(f"ebooklib khong doc duoc EPUB '{path}': {exc}") from exc

            doc = cls(path=path, opf_dir=opf_dir)
            units: list[EpubUnit] = []
            spine_hrefs: list[str] = []
            for idref, _linear in book.spine:
                item = book.get_item_with_id(idref)
                if item is None:
                    continue
                doc_href = posixpath.normpath(posixpath.join(opf_dir, item.file_name))
                if doc_href not in names:
                    # X6 — dung "MOI phai la entry that trong zip", khong duoc
                    # im lang bo qua: neu lech, day chinh la Bug #5 tai sinh
                    # (output == input, khong ai bao loi).
                    raise EpubParseError(
                        f"doc_href '{doc_href}' (tu spine idref='{idref}') "
                        f"khong khop entry nao trong zip cua '{path}'"
                    )
                # §6.15.7 muc A: tinh thu tu spine DUNG MOT LAN o day, dung
                # chung boi to_markdown() sau nay — khong giu lai soup nao
                # (chi phi bo nho vo ich cho sach vai tram trang).
                spine_hrefs.append(doc_href)
                raw_bytes = zf.read(doc_href)
                soup, _parser_used = _parse_xhtml(raw_bytes)
                candidates = _collect_candidate_nodes(soup)
                for ordinal, node in enumerate(candidates):
                    # Y2(d): loai <ul>/<ol> con (da tro thanh unit rieng)
                    # truoc khi xet drop-rule/trich text -- neu khong,
                    # get_text() se "an" noi dung cua unit con vao unit cha
                    # (ca "rong sau strip" se sai) va text se chua markup
                    # <ul>/<li> tho ngoai contract X4 khi gui cho LLM.
                    own = _strip_nested_lists(node)
                    if _is_droppable_content(own):
                        continue
                    units.append(
                        EpubUnit(
                            unit_id=f"{doc_href}#{ordinal}",
                            doc_href=doc_href,
                            tag=node.name,
                            ordinal=ordinal,
                            text=_inner_html(own),
                        )
                    )
            doc._units = units
            doc._spine_hrefs = spine_hrefs
            return doc

    @property
    def units(self) -> list[EpubUnit]:
        return self._units

    @property
    def spine_hrefs(self) -> list[str]:
        return self._spine_hrefs

    def to_markdown(self, images_out_dir: Path) -> str:
        """US-15 nhanh EPUB->Markdown (Architecture.md §6.15.7 muc A/B/C):
        chieu TOAN BO cuon sach sang MOT chuoi Markdown, theo dung thu tu
        `self._spine_hrefs` cua CHINH lan `load()` nay — CAM goi `load()`
        lan thu hai o day (R6-02: soi day lineage Reviewer phai trace).

        Voi tung tai lieu trong spine: mo lai `self.path` (KHONG dung soup
        da vut di sau `load()`), parse lai bang `_parse_xhtml()` (dung lai
        helper co san, khong viet parser thu hai), rewrite `<img src>` +
        copy bytes anh ra `images_out_dir` (`_rewrite_image_srcs()`), chuan
        hoa `<sup>`/`<sub>` (`normalize_sup_sub()`) — THU TU BAT BUOC: chuan
        hoa sup/sub TRUOC khi goi `markdownify`, khong duoc dao nguoc (phu
        thuoc `sup_symbol` mac dinh cua thu vien neu lam sai thu tu).
        """
        images_out_dir = Path(images_out_dir)
        images_out_dir.mkdir(parents=True, exist_ok=True)
        style = get_settings().markdown_supsub_style
        converter = markdownify.MarkdownConverter(heading_style="ATX")

        entry_to_target: dict[str, str] = {}
        bytes_by_target: dict[str, bytes] = {}
        parts: list[str] = []

        with zipfile.ZipFile(self.path) as zf:
            zip_names = set(zf.namelist())
            for doc_href in self._spine_hrefs:
                raw_bytes = zf.read(doc_href)
                soup, _parser_used = _parse_xhtml(raw_bytes)
                _rewrite_image_srcs(
                    soup, doc_href, zf, zip_names, images_out_dir, entry_to_target, bytes_by_target
                )
                normalize_sup_sub(soup, style=style)
                # Convert only <body> (via convert_soup(), no re-serialize +
                # re-parse round trip through markdownify.markdownify()) —
                # feeding the WHOLE soup back through markdownify() would
                # also re-parse the XML declaration + <head>/<title> as
                # ordinary body content (verified: leaks "xml version=..."
                # and the page <title> text into the Markdown output).
                body = soup.find("body") or soup
                fragment_md = converter.convert_soup(body).strip("\n")
                if fragment_md:
                    parts.append(fragment_md)

        return ("\n\n".join(parts) + "\n") if parts else ""

    def full_text(self) -> str:
        """Text thuần nối từ mọi unit — dùng cho lọc glossary (6.6.5) và
        US-20, KHÔNG dùng cho việc dịch (đó là `unit.text`, inner-HTML)."""
        parts = []
        for unit in self._units:
            fragment = BeautifulSoup(unit.text, "html.parser")
            plain = fragment.get_text(" ", strip=True)
            if plain:
                parts.append(plain)
        return "\n\n".join(parts)

    @property
    def total_chars(self) -> int:
        return len(self.full_text())

    def write_translated(
        self,
        translations: dict[str, str],
        output_path: Path,
        bilingual: bool = False,
        untranslated_ids: set[str] | None = None,
    ) -> None:
        """Ghi đè tại chỗ bằng `zipfile` (B-07) — KHÔNG dùng
        `epub.write_epub()` (§6.20.5/6.20.12: nó dời đường dẫn + ghi lại mọi
        entry, phá tinh thần "giữ nguyên cấu trúc gốc" của BR-EPUB-01).

        `untranslated_ids` (Architecture.md §6.20.14.4 C-4, MỚI — Lớp C):
        tập `unit_id` KHÔNG có trong `translations` mà vẫn cần đánh dấu
        trong file output vì bị giữ nguyên tiếng Anh (fallback, sau khi đã
        thử hết cơ chế cứu vãn tổng quát — Lớp B). Với mỗi id trong tập này,
        thêm class `bb-untranslated` + `lang="en"` NGAY TRÊN chính node gốc
        (không chèn node mới, không bọc `<span>`) — KHÔNG được lẫn với
        `translations` (2 tập này rời nhau theo thiết kế: 1 unit hoặc có bản
        dịch, hoặc bị đánh dấu fallback, không bao giờ cả hai).
        """
        output_path = Path(output_path)
        units_by_id = {unit.unit_id: unit for unit in self._units}
        untranslated_ids = untranslated_ids or set()

        unknown_ids = [uid for uid in translations if uid not in units_by_id]
        if unknown_ids:
            # R6-02: day la sam Bug #5 dang EPUB — ban dich roi vao "hu khong"
            # neu key khong khop unit_id sinh tu CHINH lan load() nay.
            raise EpubParseError(
                f"translations co {len(unknown_ids)} unit_id khong thuoc lan "
                f"load() nay (vd '{unknown_ids[0]}') — co the do load() lai "
                "voi bo loc tag khac, hoac dung sai EpubDocument instance"
            )
        unknown_untranslated_ids = [uid for uid in untranslated_ids if uid not in units_by_id]
        if unknown_untranslated_ids:
            raise EpubParseError(
                f"untranslated_ids co {len(unknown_untranslated_ids)} unit_id khong thuoc "
                f"lan load() nay (vd '{unknown_untranslated_ids[0]}')"
            )

        by_doc: dict[str, list[tuple[int, str]]] = {}
        for uid, vi_html in translations.items():
            unit = units_by_id[uid]
            by_doc.setdefault(unit.doc_href, []).append((unit.ordinal, vi_html))

        by_doc_untranslated: dict[str, list[int]] = {}
        for uid in untranslated_ids:
            unit = units_by_id[uid]
            by_doc_untranslated.setdefault(unit.doc_href, []).append(unit.ordinal)

        with zipfile.ZipFile(self.path) as src_zf:
            names = set(src_zf.namelist())
            all_doc_hrefs = set(by_doc) | set(by_doc_untranslated)
            for doc_href in all_doc_hrefs:
                if doc_href not in names:
                    raise EpubParseError(f"doc_href '{doc_href}' khong con ton tai trong zip goc")

            modified_entries: dict[str, bytes] = {}
            for doc_href in all_doc_hrefs:
                raw_bytes = src_zf.read(doc_href)
                soup, parser_used = _parse_xhtml(raw_bytes)
                candidates = _collect_candidate_nodes(soup)
                for ordinal, vi_html in by_doc.get(doc_href, []):
                    if ordinal >= len(candidates):
                        raise EpubParseError(
                            f"'{doc_href}': ordinal {ordinal} vuot qua so unit "
                            f"do lai duoc ({len(candidates)}) — cau truc tai lieu "
                            "co the da doi so voi luc load()"
                        )
                    node = candidates[ordinal]
                    _apply_translation(
                        soup, node, vi_html, bilingual=bilingual, parser_name=parser_used
                    )
                for ordinal in by_doc_untranslated.get(doc_href, []):
                    if ordinal >= len(candidates):
                        raise EpubParseError(
                            f"'{doc_href}': ordinal {ordinal} (untranslated) vuot qua so unit "
                            f"do lai duoc ({len(candidates)}) — cau truc tai lieu "
                            "co the da doi so voi luc load()"
                        )
                    _mark_bb_untranslated(candidates[ordinal])
                output_bytes = str(soup).encode("utf-8")
                _validate_wellformed(output_bytes, doc_href)
                modified_entries[doc_href] = output_bytes

            infolist = src_zf.infolist()
            mimetype_infos = [info for info in infolist if info.filename == "mimetype"]
            if not mimetype_infos:
                # load() da kiem entry nay ton tai (L1) — chi con la defensive
                # guard neu ai goi write_translated() ma khong qua load().
                raise EpubParseError(f"'{self.path}': khong tim thay entry 'mimetype' de chuan hoa")
            mimetype_info = mimetype_infos[0]
            rest_infos = [info for info in infolist if info.filename != "mimetype"]
            # §6.25.2 L2: 'mimetype' luon la entry DAU TIEN cua output, du vi
            # tri/compress_type cua no o input the nao — chuan hoa khi GHI,
            # khong tu choi vi input vi pham (sua duoc, khac voi L1 o load()).
            ordered_infos = [mimetype_info, *rest_infos]

            tmp_path = output_path.with_name(output_path.name + ".tmp")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(tmp_path, "w", allowZip64=True) as out_zf:
                for info in ordered_infos:
                    data = modified_entries.get(info.filename)
                    if data is None:
                        data = src_zf.read(info.filename)
                    new_info = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
                    new_info.external_attr = info.external_attr
                    new_info.create_system = info.create_system
                    new_info.internal_attr = info.internal_attr
                    if info.filename == "mimetype":
                        # §6.25.1 (EPUB 3.3 §4.3): STORED + khong extra field,
                        # bat ke input nen kieu gi — writestr() von khong bao
                        # gio sinh extra field (R5-01 §6.25.4), nen chi can ep
                        # compress_type.
                        new_info.compress_type = zipfile.ZIP_STORED
                    else:
                        new_info.compress_type = info.compress_type
                    out_zf.writestr(new_info, data)

        tmp_path.replace(output_path)


def _find_bb_vi_nodes(root: Tag | BeautifulSoup) -> list[Tag]:
    """`soup.find_all(class_=_BB_VI_CLASS)` KHONG dang tin cay khi node co
    NHIEU class (vd `class="noindent bb-vi"`) duoi builder XML: bs4 (4.15)
    chi coi `class` la multi-valued attribute cho builder HTML — voi builder
    XML, gia tri tra ve la 1 CHUOI DUY NHAT, va `_attribute_match()` cua bs4
    chi thu khop lai "ca chuoi noi lien" khi gia tri GOC la list nhieu phan
    tu (`len(attr_values) != 1`) — 1 chuoi don (du chua nhieu tu cach nhau
    boi khoang trang) khong bao gio kich hoat nhanh do, nen so khop THAT BAI
    du node co dung class "bb-vi" nam trong đó. Tu verify truc tiep:
    `BeautifulSoup('<p class="noindent bb-vi">x</p>', "xml").find_all(class_="bb-vi")`
    tra ve RONG. Dung `_node_classes()` (da chuan hoa str/list) qua callable
    predicate de tranh phu thuoc hanh vi noi bo nay cua bs4."""
    return [node for node in root.find_all(True) if _BB_VI_CLASS in _node_classes(node)]


def count_bb_vi_pairs(path: Path) -> tuple[int, int]:
    """BR-EPUB-05 guard, nhanh `bilingual=True` (X3, Architecture.md
    6.20.12) — dung boi `job_orchestrator._check_epub_output_guard()`. Mo
    LAI file EPUB `path` (khong tin trang thai trong bo nho — R6-02) va dem:
    (a) tong so node mang `class="bb-vi"` — day la DAU HIEU TUONG MINH duy
    nhat phan biet "unit goc" / "unit dich" o lan `load()` sau (X3); (b)
    trong so do, bao nhieu node co noi dung KHAC voi phan "goc" tuong ung.

    2 hinh dang bb-vi ma `_apply_translation()` sinh ra (phai xu ly rieng):
    - `td`/`th` (Y2(b)): ban dich la 1 `<span class="bb-vi">` CHEN BEN TRONG
      CHINH o do (sau 1 `<br/>`) — khong phai node anh em. "Ban goc" de so
      sanh la phan con lai cua o SAU KHI bo `<br/>` + span do.
    - Moi tag khac (Y2): ban dich la 1 `copy_node` CUNG TEN TAG, duoc
      `node.insert_after(copy_node)` — "ban goc" la node ANH EM (Tag) ngay
      TRUOC no trong cay (bo qua NavigableString/Comment xen giua).
    """
    total = 0
    differing = 0
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            soup, _parser_used = _parse_xhtml(zf.read(name))
            for node in _find_bb_vi_nodes(soup):
                total += 1
                if (
                    node.name == "span"
                    and node.parent is not None
                    and node.parent.name
                    in (
                        "td",
                        "th",
                    )
                ):
                    parent_clone = copy.deepcopy(node.parent)
                    for marked in _find_bb_vi_nodes(parent_clone):
                        prev_sibling = marked.previous_sibling
                        marked.decompose()
                        if isinstance(prev_sibling, Tag) and prev_sibling.name == "br":
                            prev_sibling.decompose()
                    original_text = parent_clone.get_text(" ", strip=True)
                else:
                    sibling = node.previous_sibling
                    while sibling is not None and not isinstance(sibling, Tag):
                        sibling = sibling.previous_sibling
                    original_text = sibling.get_text(" ", strip=True) if sibling is not None else ""
                translated_text = node.get_text(" ", strip=True)
                if original_text.strip() != translated_text.strip():
                    differing += 1
    return total, differing


#: §6.25.1 (EPUB 3.3 §4.3, W3C) — noi dung bat buoc cua entry `mimetype`.
_EPUB_MIMETYPE = b"application/epub+zip"


def _check_mimetype_entry(zf: zipfile.ZipFile, names: set[str], path: Path) -> None:
    """§6.25.2 L1 (BL-12) — reject SOM (truoc cost gate) khi EPUB thieu han
    entry `mimetype` hoac noi dung sai. KHONG kiem thu tu/compress_type o
    day (do la vi pham SUA DUOC, chuan hoa o `write_translated()` L2) —
    deny-by-default (R8-02) CHI ap dung cho thu KHONG sua duoc: thieu han
    entry, hoac noi dung khac `application/epub+zip` (app khong tu che entry
    thay user)."""
    if "mimetype" not in names:
        raise EpubParseError(f"EPUB '{path}' thieu entry 'mimetype' — vi pham OCF, tu choi som")
    content = zf.read("mimetype")
    if content != _EPUB_MIMETYPE:
        raise EpubParseError(
            f"EPUB '{path}': entry 'mimetype' co noi dung '{content!r}', "
            f"khac '{_EPUB_MIMETYPE!r}' — tu choi som"
        )


def _check_drm(zf: zipfile.ZipFile, names: set[str]) -> None:
    """EC-22.1 / YA-6.6: `encryption.xml` cũng hợp lệ cho font obfuscation,
    không chỉ DRM — chỉ raise khi có `<EncryptedData>` trỏ tới tài nguyên
    KHÔNG phải font."""
    if "META-INF/encryption.xml" not in names:
        return
    try:
        root = ET.fromstring(zf.read("META-INF/encryption.xml"))
    except ET.ParseError:
        return
    for enc_data in root.findall(".//enc:EncryptedData", _ENC_XML_NS):
        cipher_ref = enc_data.find(".//enc:CipherReference", _ENC_XML_NS)
        uri = cipher_ref.get("URI") if cipher_ref is not None else None
        if uri and not uri.lower().endswith(_FONT_EXTENSIONS):
            raise EpubDrmError("File EPUB co DRM, can go DRM truoc khi dich")
