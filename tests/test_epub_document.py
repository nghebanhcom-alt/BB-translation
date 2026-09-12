"""Tests for `EpubDocument` (US-22 buoc 1/3, Architecture.md 6.20.5/6.20.12).

Protocol 5 muc 3: KHONG viet mock tay theo gia dinh — 2 file EPUB THAT trong
`data/uploads/` (BAT BUOC dung theo brief cua PM) lam bang chung chinh cho
cau truc/chunk/sup-sub/bold; cac test con lai dung 1 EPUB toi thieu tu dung
xay bang `zipfile` (KHONG phai mock cho ham dang test — day la fixture EPUB
that, hop le ve mat OCF, chi nho hon) de kiem cac nhanh logic ma 2 file that
khong cham toi (DRM, drop rule ranh gioi, nesting).
"""

from __future__ import annotations

import tempfile
import zipfile
from itertools import pairwise
from pathlib import Path

import markdownify
import pytest

from src.services.epub_document import (
    EpubDocument,
    EpubDrmError,
    EpubParseError,
    _parse_xhtml,
    _rewrite_image_srcs,
    count_bb_vi_pairs,
    normalize_sup_sub,
)

# ---------------------------------------------------------------------------
# File EPUB that (Protocol 5 muc 3 — bat buoc dung, khong viet mock tay).
# ---------------------------------------------------------------------------

SOURDOUGH_PATH = Path(
    "data/uploads/9d436d7b-e91e-4198-a12b-a2150f7dd362_Baking with Sourdough - Sara Pitzer.epub"
)
BREAD_PATH = Path("data/uploads/sample2_Bread-A-Global-History.epub")

pytestmark = pytest.mark.skipif(
    not SOURDOUGH_PATH.exists() or not BREAD_PATH.exists(),
    reason="Can file EPUB that trong data/uploads/ (Protocol 5 muc 3)",
)


# ---------------------------------------------------------------------------
# Helper: dung 1 EPUB toi thieu, hop le OCF, de test cac nhanh logic ma 2
# file that o tren khong tinh co cham toi (DRM, nesting, drop rule ranh gioi).
# ---------------------------------------------------------------------------

_CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="bookid">urn:uuid:test-book</dc:identifier>
  </metadata>
  <manifest>
    <item id="chap1" href="{href}" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chap1"/>
  </spine>
</package>
"""

_NCX = """<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:test-book"/></head>
  <docTitle><text>Test Book</text></docTitle>
  <navMap>
    <navPoint id="np1" playOrder="1">
      <navLabel><text>Chapter 1</text></navLabel>
      <content src="{href}"/>
    </navPoint>
  </navMap>
</ncx>
"""

_ENC_XML = """<?xml version="1.0"?>
<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container"
            xmlns:enc="http://www.w3.org/2001/04/xmlenc#">
  <enc:EncryptedData>
    <enc:CipherData><enc:CipherReference URI="{uri}"/></enc:CipherData>
  </enc:EncryptedData>
</encryption>
"""


def _build_minimal_epub(
    path: Path,
    body: str,
    *,
    opf_dir: str = "OEBPS",
    href: str = "xhtml/chap1.xhtml",
    encryption_xml: str | None = None,
) -> Path:
    opf_path = f"{opf_dir}/content.opf" if opf_dir else "content.opf"
    doc_entry = f"{opf_dir}/{href}" if opf_dir else href
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        f"<head><title>Chapter 1</title></head><body>{body}</body></html>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        mimetype_info = zipfile.ZipInfo("mimetype")
        mimetype_info.compress_type = zipfile.ZIP_STORED
        zf.writestr(mimetype_info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", _CONTAINER_XML.format(opf_path=opf_path))
        if encryption_xml is not None:
            zf.writestr("META-INF/encryption.xml", encryption_xml)
        opf_href = f"{opf_dir}/toc.ncx" if opf_dir else "toc.ncx"
        ncx_rel = href  # href is relative to opf_dir, same as manifest item href
        zf.writestr(opf_path, _OPF.format(href=href))
        zf.writestr(opf_href, _NCX.format(href=ncx_rel))
        zf.writestr(doc_entry, xhtml)
    return path


# ---------------------------------------------------------------------------
# (a) Parse dung so spine document / unit cua ca 2 file that.
# ---------------------------------------------------------------------------


def test_load_sourdough_matches_verified_structure() -> None:
    doc = EpubDocument.load(SOURDOUGH_PATH)

    # B-01 (Architecture.md 6.20.3, tu verify lai): 5 ITEM_DOCUMENT trong spine.
    assert {u.doc_href for u in doc.units}.issubset(
        {
            "ops/xhtml/cover.html",
            "ops/xhtml/title.html",
            "ops/xhtml/copyright.html",
            "ops/xhtml/chapter01.html",
            "ops/xhtml/backmatter01.html",
        }
    )
    # Tu do lai (khop B-04 384/383 trong khoang sai so nho da ghi trong
    # Architecture.md 6.20.3, khac parser cho ra lech <1 unit).
    assert len(doc.units) == 384
    chapter_units = [u for u in doc.units if u.doc_href == "ops/xhtml/chapter01.html"]
    assert len(chapter_units) == 373


def test_load_bread_matches_verified_spine_count() -> None:
    doc = EpubDocument.load(BREAD_PATH)

    # PM brief: 19 tai lieu spine cho file nay — tu verify lai bang ebooklib
    # truc tiep (khong qua EpubDocument) truoc khi tin brief.
    from ebooklib import epub

    book = epub.read_epub(str(BREAD_PATH))
    assert len(book.spine) == 19

    doc_hrefs = {u.doc_href for u in doc.units}
    assert len(doc_hrefs) <= 19
    assert len(doc.units) > 0


def test_unit_ids_deterministic_across_loads() -> None:
    """R6-02: load() 2 lan tren cung 1 file -> unit_id list phai giong het."""
    doc_a = EpubDocument.load(SOURDOUGH_PATH)
    doc_b = EpubDocument.load(SOURDOUGH_PATH)

    assert [u.unit_id for u in doc_a.units] == [u.unit_id for u in doc_b.units]


def test_doc_href_matches_real_zip_entries() -> None:
    """X6 lineage trap regression: `doc_href` PHAI la entry that trong zip —
    dung `item.file_name` cua ebooklib truc tiep (khong join opf_dir) se cho
    0/5 khop (tu do lai trong spike). Day la sam Bug #5 tai sinh dang EPUB."""
    doc = EpubDocument.load(SOURDOUGH_PATH)
    names = set(zipfile.ZipFile(SOURDOUGH_PATH).namelist())

    assert all(u.doc_href in names for u in doc.units)
    # doc_href phai la duong da join opf_dir, KHONG phai item.file_name tran.
    assert all(u.doc_href.startswith("ops/") for u in doc.units)


# ---------------------------------------------------------------------------
# (b) Chunk theo budget.
# ---------------------------------------------------------------------------


def test_plan_epub_chunks_sourdough_matches_measured_value() -> None:
    from src.core.chunking import plan_epub_chunks

    doc = EpubDocument.load(SOURDOUGH_PATH)
    plans = plan_epub_chunks(doc.units)

    # Khop con so Architecture.md 6.20.3/6.20.7 (7 chunk @ budget 8000 cho
    # cuon Sourdough that).
    assert len(plans) == 7
    # Moi chunk phai lien tuc, khong chong lan, phu het toan bo unit.
    assert plans[0].unit_start == 0
    assert plans[-1].unit_end == len(doc.units) - 1
    for prev, cur in pairwise(plans):
        assert cur.unit_start == prev.unit_end + 1


def test_plan_epub_chunks_bread_book_is_continuous_and_covers_all_units() -> None:
    from src.core.chunking import plan_epub_chunks

    doc = EpubDocument.load(BREAD_PATH)
    plans = plan_epub_chunks(doc.units)

    assert len(plans) > 1  # sach day, chac chan phai chunk
    assert plans[0].unit_start == 0
    assert plans[-1].unit_end == len(doc.units) - 1
    for prev, cur in pairwise(plans):
        assert cur.unit_start == prev.unit_end + 1
    # Moi request trong moi chunk cung phai lien tuc va nam trong pham vi chunk.
    for plan in plans:
        assert plan.requests[0][0] == plan.unit_start
        assert plan.requests[-1][1] == plan.unit_end
        for r_prev, r_cur in zip(plan.requests, plan.requests[1:]):
            assert r_cur[0] == r_prev[1] + 1


def test_plan_epub_chunks_respects_request_budget() -> None:
    """Dung DUNG thuoc do ma plan_epub_chunks tu dung (plain-text, tag da
    duoc strip) de kiem ngan sach — do dai inner-HTML tho (co the vuot xa
    request_budget o cac unit nhieu the inline nhu <td>/<a>) khong phai bat
    bien ma ham nay dam bao."""
    import re

    from src.core.chunking import EPUB_REQUEST_CHAR_BUDGET, plan_epub_chunks

    tag_re = re.compile(r"<[^>]+>")
    doc = EpubDocument.load(BREAD_PATH)
    plans = plan_epub_chunks(doc.units)

    units_by_index = doc.units
    for plan in plans:
        for r_start, r_end in plan.requests:
            plain_len = sum(
                len(tag_re.sub("", units_by_index[i].text)) for i in range(r_start, r_end + 1)
            )
            # Cho phep 1 unit don le vuot request_budget (Y4 — unit qua kho gui
            # 1 minh); voi request nhieu unit, tong plain-text KHONG duoc vuot
            # ngan sach (do la chinh bat bien plan_epub_chunks dam bao).
            if r_end > r_start:
                assert plain_len <= EPUB_REQUEST_CHAR_BUDGET


def test_plan_epub_chunks_empty_units_returns_empty_list() -> None:
    from src.core.chunking import plan_epub_chunks

    assert plan_epub_chunks([]) == []


def test_plan_epub_chunks_raises_on_oversized_unit() -> None:
    from src.core.chunking import EpubUnitTooLargeError, plan_epub_chunks
    from src.services.epub_document import EpubUnit

    huge = EpubUnit(unit_id="x#0", doc_href="x", tag="p", ordinal=0, text="A" * 10_001)
    with pytest.raises(EpubUnitTooLargeError) as exc_info:
        plan_epub_chunks([huge])
    assert exc_info.value.unit_id == "x#0"


# ---------------------------------------------------------------------------
# (c) <sup>/<sub> giu dung ky hieu (X1) — 6 dong nguyen lieu that.
# ---------------------------------------------------------------------------


def test_sup_sub_preserved_verbatim_on_real_fraction_lines() -> None:
    """X1/X2: KHONG duoc extract()/rut gon sup-sub — unit la inner-HTML nen
    phan so di qua nguyen ven. Kiem dung 6 dong da do trong Architecture.md
    6.20.3/6.20.12 (N-1): 5 dong phan so thuan + 1 dong hon so."""
    doc = EpubDocument.load(SOURDOUGH_PATH)
    sup_units = [u for u in doc.units if "<sup>" in u.text]

    assert len(sup_units) == 6
    fraction_units = [u for u in sup_units if "cups unbleached white flour" not in u.text]
    assert len(fraction_units) == 5
    for unit in fraction_units:
        assert "<sup>1</sup>/<sub>3</sub>" in unit.text

    mixed_number = next(u for u in sup_units if "cups unbleached white flour" in u.text)
    # Ca hon so: KHONG duoc de sup/sub dinh lien vao "1" phia truoc (do la
    # loi 11/3 cua markdownify mac dinh, N-1) — nhung o day KHONG chuyen doi
    # gi ca (EPUB->EPUB), nen chuoi phai giu y het HTML goc, "1" va sup/sub
    # phai dung canh nhau (khong co gi chen giua).
    assert "1<sup>1</sup>/<sub>3</sub>" in mixed_number.text


# ---------------------------------------------------------------------------
# (d) Bold/inline markup giu nguyen qua parse (khong flatten ve text thuan).
# ---------------------------------------------------------------------------


def test_inline_markup_preserved_not_flattened() -> None:
    """X2: doan nguyen lieu 4 <strong>...</strong><br/> phai giu nguyen —
    day chinh la Bug #7 tai sinh o EPUB neu dung get_text() thay vi inner-HTML.
    Trong file that, doan nay la <p class="blockquote"> (khong phai the
    <blockquote>) — kiem theo noi dung, khong theo ten the."""
    doc = EpubDocument.load(SOURDOUGH_PATH)
    ingredient_units = [
        u
        for u in doc.units
        if u.text.count("<strong>") >= 4
        and "<br/>" in u.text
        and "unbleached white flour" in u.text
    ]

    assert len(ingredient_units) >= 1
    sample = ingredient_units[0].text
    assert sample.count("<strong>") == 4
    assert sample.count("<br/>") == 3
    assert "4 cups unbleached white flour" in sample
    assert "2 teaspoons salt" in sample


def test_nesting_dedup_keeps_outermost_node_only() -> None:
    """§6.20.5: node long nhau (li chua p) chi lay node NGOAI CUNG, tranh
    dich 2 lan cung noi dung."""
    with_tmp = Path("/tmp/bb_test_nesting.epub")
    _build_minimal_epub(with_tmp, "<li>outer <p>inner</p> text</li>")
    doc = EpubDocument.load(with_tmp)

    assert len(doc.units) == 1
    assert doc.units[0].tag == "li"
    assert "<p>inner</p>" in doc.units[0].text


def test_nested_list_splits_into_innermost_units(tmp_path: Path) -> None:
    """Y2(d) (Architecture.md 6.20.12 dong 5591, "NHAN toan bo"): `li` chua
    `ul` con (list long list) KHONG duoc gom thanh 1 unit khong lo chua
    markup `<ul>/<li>` tho (ngoai contract X4 `_INLINE_PRESERVE_TAGS`, hanh
    vi LLM voi no khong xac dinh) — phai tach thanh unit RIENG cho phan text
    truc tiep cua `li` cha + moi `li` con trong `ul` long."""
    path = _build_minimal_epub(
        tmp_path / "nested_list.epub",
        "<li>Preheat the oven to 220C, then:"
        "<ul><li>Add flour and water</li><li>Knead for ten minutes</li></ul>"
        "</li>",
    )
    doc = EpubDocument.load(path)

    assert len(doc.units) == 3
    assert [u.tag for u in doc.units] == ["li", "li", "li"]
    assert doc.units[0].text == "Preheat the oven to 220C, then:"
    assert doc.units[1].text == "Add flour and water"
    assert doc.units[2].text == "Knead for ten minutes"
    # Unit cha KHONG duoc chua markup <ul>/<li> tho cua danh sach con.
    assert "<ul>" not in doc.units[0].text
    assert "<li>" not in doc.units[0].text


def test_nested_list_multi_level_splits_to_every_leaf(tmp_path: Path) -> None:
    """Y2(d) "innermost": long nhieu cap (`li > ul > li > ul > li`) phai
    tach het toi tan cung, moi block la co text truc tiep la 1 unit doc lap
    — khong chi xu ly dung 1 cap long."""
    path = _build_minimal_epub(
        tmp_path / "nested_list_multi.epub",
        "<li>Level A text<ul><li>Level B text<ul><li>Level C text</li></ul></li></ul></li>",
    )
    doc = EpubDocument.load(path)

    assert len(doc.units) == 3
    assert [u.text for u in doc.units] == [
        "Level A text",
        "Level B text",
        "Level C text",
    ]
    for unit in doc.units:
        assert "<ul>" not in unit.text
        assert "<li>" not in unit.text


def test_write_translated_nested_list_updates_each_leaf_independently(
    tmp_path: Path,
) -> None:
    """R6-02: khong chi assert so luong unit — assert CAU TRUC XHTML sau khi
    ghi ban dich nguoc: `<ul>/<li>` phai con nguyen (khong bi flatten thanh
    markup tho), va moi `<li>` phai mang DUNG ban dich cua chinh no (khong bi
    lech/tron sang unit khac) — day chinh la ca Reviewer da dung de phat hien
    bug o vong 1."""
    path = _build_minimal_epub(
        tmp_path / "nested_list_write.epub",
        "<li>Preheat the oven to 220C, then:"
        "<ul><li>Add flour and water</li><li>Knead for ten minutes</li></ul>"
        "</li>",
    )
    doc = EpubDocument.load(path)
    assert len(doc.units) == 3

    translations = {
        doc.units[0].unit_id: "Lam nong lo den 220C, sau do:",
        doc.units[1].unit_id: "Cho bot mi va nuoc",
        doc.units[2].unit_id: "Nhao trong muoi phut",
    }
    out = tmp_path / "nested_list_write_out.epub"
    doc.write_translated(translations, out, bilingual=False)

    raw = zipfile.ZipFile(out).read("OEBPS/xhtml/chap1.xhtml").decode("utf-8")
    # Cau truc <ul>/<li> phai con nguyen — khong bi flatten.
    assert raw.count("<li>") == 3
    assert "<ul>" in raw
    # Moi unit mang DUNG ban dich cua chinh no, dung vi tri long nhau.
    assert (
        "<li>Lam nong lo den 220C, sau do:"
        "<ul><li>Cho bot mi va nuoc</li><li>Nhao trong muoi phut</li></ul>"
        "</li>" in raw
    )
    # Khong con tieng Anh goc nao sot lai.
    assert "Preheat" not in raw
    assert "Add flour" not in raw
    assert "Knead" not in raw

    from xml.etree import ElementTree as ET

    ET.fromstring(raw.encode("utf-8"))  # van well-formed


# ---------------------------------------------------------------------------
# Drop rules (rong / toan so / URL / ISBN-only, Y8).
# ---------------------------------------------------------------------------


def test_drop_rules_and_ordinal_counted_before_content_filter(tmp_path: Path) -> None:
    path = _build_minimal_epub(
        tmp_path / "drop.epub",
        "<p>A</p><p>123</p><p>https://example.com/x</p>"
        "<p>ISBN 978-0-88266-225-1</p>"
        "<p>Book Title ISBN 978-0-88266-225-1</p><p>B</p>",
    )
    doc = EpubDocument.load(path)

    texts = [u.text for u in doc.units]
    assert texts == ["A", "Book Title ISBN 978-0-88266-225-1", "B"]
    # Y3: ordinal dem tren MOI node truoc drop rule -> "B" phai co ordinal 5,
    # khong phai 2 (khong bi don lai sau khi loc).
    ordinals = [u.ordinal for u in doc.units]
    assert ordinals == [0, 4, 5]


def test_isbn_line_with_title_is_kept_not_dropped() -> None:
    """Y8: rule la unit CHI chua ISBN, khong phai "chua ISBN" — doan co
    ten sach/tac gia truoc ISBN (file that, copyright.html#8) phai duoc giu.
    Ca "chi ISBN" bi drop duoc kiem rieng o test_drop_rules_and_ordinal_...
    (khong co dong ISBN-thuan-tuy nao trong 2 file that de lam ca am tinh)."""
    doc = EpubDocument.load(SOURDOUGH_PATH)
    copyright_units = [u for u in doc.units if u.doc_href == "ops/xhtml/copyright.html"]

    assert any("ISBN 978-0-88266-225-1" in u.text for u in copyright_units)


# ---------------------------------------------------------------------------
# DRM (EC-22.1 / YA-6.6).
# ---------------------------------------------------------------------------


def test_load_raises_drm_error_for_non_font_encryption(tmp_path: Path) -> None:
    path = _build_minimal_epub(
        tmp_path / "drm.epub",
        "<p>hi</p>",
        encryption_xml=_ENC_XML.format(uri="OEBPS/xhtml/chap1.xhtml"),
    )
    with pytest.raises(EpubDrmError):
        EpubDocument.load(path)


def test_load_does_not_raise_drm_error_for_font_only_encryption(tmp_path: Path) -> None:
    path = _build_minimal_epub(
        tmp_path / "font_obfuscation.epub",
        "<p>hi</p>",
        encryption_xml=_ENC_XML.format(uri="OEBPS/fonts/embedded.ttf"),
    )
    doc = EpubDocument.load(path)  # khong duoc raise
    assert len(doc.units) == 1


def test_real_sourdough_file_has_no_drm() -> None:
    """B-08 (tu verify lai): file mau khong co META-INF/encryption.xml."""
    names = set(zipfile.ZipFile(SOURDOUGH_PATH).namelist())
    assert "META-INF/encryption.xml" not in names
    EpubDocument.load(SOURDOUGH_PATH)  # khong duoc raise EpubDrmError


# ---------------------------------------------------------------------------
# Loi parse (EpubParseError) cho input hong.
# ---------------------------------------------------------------------------


def test_load_raises_parse_error_for_corrupt_zip(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_zip.epub"
    bad.write_bytes(b"this is not a zip file at all")
    with pytest.raises(EpubParseError):
        EpubDocument.load(bad)


def test_load_raises_parse_error_when_container_xml_missing(tmp_path: Path) -> None:
    path = tmp_path / "no_container.epub"
    with zipfile.ZipFile(path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, "application/epub+zip")
    with pytest.raises(EpubParseError):
        EpubDocument.load(path)


# ---------------------------------------------------------------------------
# (e) write_translated() — round-trip: entry khong lien quan byte-identical.
# ---------------------------------------------------------------------------


def test_write_translated_monolingual_preserves_untouched_entries(tmp_path: Path) -> None:
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    translations = {u.unit_id: f"[VI] {u.text}" for u in doc.units}
    doc.write_translated(translations, out, bilingual=False)

    zin = zipfile.ZipFile(src)
    zout = zipfile.ZipFile(out)
    assert zin.namelist() == zout.namelist()  # thu tu entry giu nguyen (B-07)

    touched = {u.doc_href for u in doc.units}
    untouched = [n for n in zin.namelist() if n not in touched]
    assert len(untouched) >= 20  # da so entry (anh, font, css, mimetype...) khong dung toi
    for name in untouched:
        assert zin.read(name) == zout.read(name), f"entry '{name}' bi doi noi dung ngoai y muon"


def test_write_translated_monolingual_output_reparses_with_translated_content(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    translations = {u.unit_id: f"BAN DICH: {u.text}" for u in doc.units}
    doc.write_translated(translations, out, bilingual=False)

    doc_out = EpubDocument.load(out)
    assert len(doc_out.units) == len(doc.units)
    assert all(u.text.startswith("BAN DICH:") for u in doc_out.units)
    # sup/sub phai con nguyen sau khi ghi lai (khong bi ET/bs4 lam hong).
    assert any("<sup>" in u.text for u in doc_out.units)


def test_write_translated_bilingual_preserves_original_units_on_reload(
    tmp_path: Path,
) -> None:
    """X3: `load()` bo qua node mang class bb-vi -> upload lai chinh file
    song ngu da dich se KHONG dich doi. So unit doc lai phai BANG so unit goc."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out_bilingual.epub"

    doc = EpubDocument.load(src)
    translations = {u.unit_id: f"<em>VI-{u.ordinal}</em>" for u in doc.units}
    doc.write_translated(translations, out, bilingual=True)

    doc_reloaded = EpubDocument.load(out)
    assert len(doc_reloaded.units) == len(doc.units)

    chapter_raw = zipfile.ZipFile(out).read("ops/xhtml/chapter01.html").decode("utf-8")
    assert chapter_raw.count("bb-vi") == 373  # so unit cua chapter01.html


def test_mark_bb_vi_preserves_preexisting_class_string_under_xml_parser(
    tmp_path: Path,
) -> None:
    """Regression cho bug BLOCKING tim boi Reviewer (US-22 Buoc 2/3, vong 1/3)
    + 1 lop sau hon Dev tu phat hien khi viet lai fix (chua tung duoc noi
    trong review-report.md, xem ghi chu (2b) o duoi):

    (a) `_mark_bb_vi()` (bug goc Reviewer tim): voi builder XML
    (`features="xml"`, dung CHINH cho EpubDocument theo Y1), bs4 tra
    `node.get("class")` la 1 CHUOI (khong phai list) khi node goc DA CO SAN
    attribute class -- rat pho bien trong EPUB dan trang that (vd
    `chapter01.html` cua chinh file mau Sourdough co san `class="noindent"`
    tren hau het `<p>`). Code cu lam `[*existing, "bb-vi"]` tren 1 chuoi se
    unpack thanh TUNG KY TU (`"noindent"` -> `['n','o','i',...]`), hong
    attribute class thanh vd `class="n o i n d e n t bb-vi"`.

    (b) `count_bb_vi_pairs()` (lop bug THU HAI, KHONG nam trong review-report
    goc -- Dev tu phat hien khi verify lai fix (a) tren file that, xem
    CHANGELOG): ngay ca SAU KHI (a) da sua dung (class ghi ra dung
    `class="noindent bb-vi"`), `soup.find_all(class_="bb-vi")` cua bs4 4.15
    VAN KHONG khop duoc node nay khi doc lai qua builder XML -- tu verify
    truc tiep: `BeautifulSoup('<p class="noindent bb-vi">x</p>',
    "xml").find_all(class_="bb-vi")` tra ve RONG. Ly do: bs4 chi thu ghep lai
    "ca chuoi" khi gia tri GOC la 1 LIST nhieu phan tu; voi builder XML, gia
    tri doc lai LUON la 1 chuoi don (`isinstance(..., list)` False), nen
    nhanh ghep-lai-roi-so-sanh khong bao gio kich hoat -- so khop that bai
    cho MOI node co >1 class (da so unit cua sach that). Fix: thay
    `find_all(class_=...)` bang `_find_bb_vi_nodes()` (predicate callable
    dung `_node_classes()` da chuan hoa), khong dua vao hanh vi noi bo nay
    cua bs4.

    Test nay dung CHINH file EPUB that (khong phai fixture tu dung, dung
    `_build_minimal_epub` khong co class tren node goc nen KHONG bat duoc ca
    2 lop bug tren -- day chinh xac la ly do 12 test cu lot qua no)."""
    from src.core.job_orchestrator import _check_epub_output_guard
    from src.services.epub_document import _find_bb_vi_nodes, count_bb_vi_pairs

    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out_bilingual.epub"

    source_doc = EpubDocument.load(src)
    # Dich "that" toan bo 384 unit -- noi dung khac han ban goc, giong dung
    # kich ban live-verify cua Reviewer.
    translations = {u.unit_id: f"VI:{u.text}" for u in source_doc.units}
    source_doc.write_translated(translations, out, bilingual=True)

    # (1) Node goc chapter01.html PHAI co san class that (vd "noindent") --
    # xac nhan kich ban that su cham vao nhanh bug, khong phai gia dinh suong.
    original_raw = zipfile.ZipFile(src).read("ops/xhtml/chapter01.html").decode("utf-8")
    assert 'class="noindent"' in original_raw

    # (2) class attribute sau khi chen bb-vi phai la list dung chuan
    # ("noindent bb-vi"), KHONG bi tach ky tu ("n o i n d e n t bb-vi").
    out_raw = zipfile.ZipFile(out).read("ops/xhtml/chapter01.html").decode("utf-8")
    assert 'class="noindent bb-vi"' in out_raw
    assert "n o i n d e n t" not in out_raw

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(out_raw, "xml")
    # (2b) tai hien CHINH lop bug thu hai: filter mac dinh cua bs4 phai FAIL
    # tren dung node nay (khang dinh chu dong bug (b) van con that neu ai do
    # lo hoan doi _find_bb_vi_nodes() lai thanh find_all(class_=...) don gian).
    assert soup.find_all(class_="bb-vi") == []
    marked_noindent_nodes = [
        node for node in _find_bb_vi_nodes(soup) if "noindent" in node.get("class", [])
    ]
    assert marked_noindent_nodes, "khong tim thay node bb-vi nao ke thua class=noindent tu ban goc"
    classes = marked_noindent_nodes[0].get("class")
    assert isinstance(classes, str)  # xml builder van tra chuoi khi doc lai
    assert classes == "noindent bb-vi"

    # (3) count_bb_vi_pairs() -- doc CHINH BANG _find_bb_vi_nodes() ma guard
    # dung -- phai dem DUNG 384/384, khong phai 0/384.
    total, differing = count_bb_vi_pairs(out)
    assert total == len(source_doc.units) == 384
    assert differing == len(source_doc.units)

    # (4) Guard BR-EPUB-05 (X3, nhanh bilingual=True) phai PASS, khong raise.
    _check_epub_output_guard(source_doc, out, bilingual=True)


def test_check_epub_output_guard_threshold_uses_ceil_not_truncate(tmp_path: Path) -> None:
    """Regression cho issue #3 (US-22 Buoc 2/3, vong 1/3 review): code cu
    dung `int(len(units) * 0.9)` -- TRUNCATE ve phia 0 -- cho file Sourdough
    that (384 unit): `int(384*0.9)=345`, tuc guard PASS khi chi 345/384 =
    89.84% unit khac ban goc, THAP HON 90% yeu cau thuc su (Architecture.md
    6.20.12 X3 "ngưỡng ≥90%"). Dich CHINH XAC 345/384 unit that (giu nguyen
    39 unit con lai, khac nguyen van tieng Anh) -- day la ca bien ranh gioi
    THAT su ma code cu se cho pass sai. `math.ceil(384*0.9)=346` moi la
    nguong dung -- 345 < 346 nen guard PHAI raise."""
    from src.core.job_orchestrator import EpubEmptyOutputError, _check_epub_output_guard

    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    source_doc = EpubDocument.load(src)
    assert len(source_doc.units) == 384  # gia dinh nen cua ca bien ranh gioi nay

    translated_units = source_doc.units[:345]
    translations = {u.unit_id: f"VI:{u.text}" for u in translated_units}
    source_doc.write_translated(translations, out, bilingual=False)

    with pytest.raises(EpubEmptyOutputError, match=r"345/384"):
        _check_epub_output_guard(source_doc, out, bilingual=False)


def test_write_translated_bilingual_strips_ids_no_duplicates(tmp_path: Path) -> None:
    """Y2(a): file that co 32 unit chua <a id="page_N"/> — ban copy chen
    them KHONG duoc mang id nao, neu khong se tao duplicate id (epubcheck)."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out_bilingual.epub"

    doc = EpubDocument.load(src)
    translations = {u.unit_id: f"VI {u.ordinal}" for u in doc.units}
    doc.write_translated(translations, out, bilingual=True)

    import re
    from collections import Counter
    from xml.etree import ElementTree as ET

    chapter_raw = zipfile.ZipFile(out).read("ops/xhtml/chapter01.html")
    ids = re.findall(rb'id="([^"]+)"', chapter_raw)
    counts = Counter(ids)
    duplicates = {k: v for k, v in counts.items() if v > 1}
    assert duplicates == {}
    ET.fromstring(chapter_raw)  # van well-formed


def test_write_translated_bilingual_table_cell_keeps_column_count(tmp_path: Path) -> None:
    """Y2(b): bilingual chen BEN TRONG o <td>/<th>, khong insert_after — neu
    khong se tao them cot moi, phai dung file Bread (co <table> that)."""
    from bs4 import BeautifulSoup

    src = tmp_path / "bread_src.epub"
    src.write_bytes(BREAD_PATH.read_bytes())
    out = tmp_path / "bread_out.epub"

    doc = EpubDocument.load(src)
    td_units = [u for u in doc.units if u.tag == "td"]
    assert len(td_units) > 0  # xac nhan file that co td unit truoc khi test tiep

    translations = {u.unit_id: f"VI-{u.ordinal}" for u in td_units[:5]}
    doc.write_translated(translations, out, bilingual=True)

    doc_href = td_units[0].doc_href
    raw = zipfile.ZipFile(out).read(doc_href).decode("utf-8")
    soup = BeautifulSoup(raw, "xml")
    table = soup.find("table")
    assert table is not None
    first_row = table.find("tr")
    original_soup = BeautifulSoup(zipfile.ZipFile(src).read(doc_href), "xml")
    original_row = original_soup.find("table").find("tr")
    assert len(first_row.find_all("td", recursive=False)) == len(
        original_row.find_all("td", recursive=False)
    )
    bb_vi_cells = [td for td in table.find_all("td") if "bb-vi" in str(td)]
    assert len(bb_vi_cells) == 5


def test_write_translated_rejects_unit_id_not_from_this_load(tmp_path: Path) -> None:
    """R6-02 lineage guard: translations voi unit_id khong thuoc lan load()
    nay phai bi tu choi ro rang, khong duoc im lang bo qua (Bug #5 dang EPUB)."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    with pytest.raises(EpubParseError):
        doc.write_translated({"nonexistent-doc.html#0": "VI"}, out, bilingual=False)


# ---------------------------------------------------------------------------
# Architecture.md §6.20.14.4 C-4 (Lop C, 2026-09-10) — `untranslated_ids`.
# ---------------------------------------------------------------------------


def test_write_translated_marks_untranslated_ids_with_class_and_lang(tmp_path: Path) -> None:
    """C-4: unit trong `untranslated_ids` (KHONG co trong `translations`)
    phai duoc danh dau NGAY TREN chinh node goc bang class `bb-untranslated`
    + `lang="en"` — khong chen node moi, khong boc `<span>`."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    all_units = doc.units
    fallback_unit = all_units[0]
    translated_units = all_units[1:]
    translations = {u.unit_id: f"VI {u.ordinal}" for u in translated_units}

    doc.write_translated(
        translations,
        out,
        bilingual=True,
        untranslated_ids={fallback_unit.unit_id},
    )

    raw = zipfile.ZipFile(out).read(fallback_unit.doc_href).decode("utf-8")
    assert "bb-untranslated" in raw
    assert 'lang="en"' in raw


def test_write_translated_untranslated_ids_does_not_change_reloaded_unit_count(
    tmp_path: Path,
) -> None:
    """C-4 tac dung phu (1): `EpubDocument.load()` chi bo qua node theo class
    `bb-vi` — them `bb-untranslated` KHONG duoc doi so unit doc lai duoc
    (BR-EPUB-05 dieu kien "so unit khop" khong bi anh huong)."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    fallback_unit = doc.units[0]
    translations = {u.unit_id: f"VI {u.ordinal}" for u in doc.units[1:]}

    doc.write_translated(
        translations,
        out,
        bilingual=True,
        untranslated_ids={fallback_unit.unit_id},
    )

    doc_reloaded = EpubDocument.load(out)
    assert len(doc_reloaded.units) == len(doc.units)


def test_write_translated_untranslated_ids_does_not_affect_bb_vi_count(tmp_path: Path) -> None:
    """C-4 tac dung phu (2): `count_bb_vi_pairs()` chi dem node `bb-vi` —
    them `bb-untranslated` khong duoc lam so cap bb-vi thay doi."""
    from src.services.epub_document import count_bb_vi_pairs

    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    fallback_unit = doc.units[0]
    translated_units = doc.units[1:]
    translations = {u.unit_id: f"VI {u.ordinal}" for u in translated_units}

    doc.write_translated(
        translations,
        out,
        bilingual=True,
        untranslated_ids={fallback_unit.unit_id},
    )

    total, _differing = count_bb_vi_pairs(out)
    assert total == len(translated_units)


def test_write_translated_untranslated_ids_rejects_unknown_unit_id(tmp_path: Path) -> None:
    """`untranslated_ids` phai chiu cung ky luat lineage (R6-02) voi
    `translations` — unit_id khong thuoc lan load() nay bi tu choi ro rang."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    with pytest.raises(EpubParseError):
        doc.write_translated({}, out, bilingual=True, untranslated_ids={"nonexistent-doc.html#0"})


def test_write_translated_untranslated_ids_default_none_behaves_like_before(
    tmp_path: Path,
) -> None:
    """Khong truyen `untranslated_ids` (mac dinh `None`) phai giu nguyen
    hanh vi cu — khong co node nao bi danh dau `bb-untranslated`."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    translations = {u.unit_id: f"VI {u.ordinal}" for u in doc.units}
    doc.write_translated(translations, out, bilingual=True)

    chapter_raw = zipfile.ZipFile(out).read("ops/xhtml/chapter01.html").decode("utf-8")
    assert "bb-untranslated" not in chapter_raw


def test_write_translated_monolingual_preserves_img_child_single_text_run(
    tmp_path: Path,
) -> None:
    """Y2(c) (Architecture.md 6.20.12 dong 5591, THANG so voi mo ta nhap o
    §6.20.5 buoc 2 "thay noi dung node bang fragment HTML da dich"): bilingual
    =False chi thay text node, KHONG dung element con — vi neu khong se mat
    <img> (10 cai do duoc tren file mau, luon nam trong <p>). Ca don gian:
    1 <img> + DUNG 1 doan text ngay sau no."""
    path = _build_minimal_epub(
        tmp_path / "img_single.epub",
        '<p><img src="a.jpg" alt="Anh minh hoa"/> Very tasty bread.</p>',
    )
    doc = EpubDocument.load(path)
    assert len(doc.units) == 1
    out = tmp_path / "img_single_out.epub"

    translations = {doc.units[0].unit_id: "Banh rat ngon."}
    doc.write_translated(translations, out, bilingual=False)

    raw = zipfile.ZipFile(out).read("OEBPS/xhtml/chap1.xhtml").decode("utf-8")
    # Thu tu attribute do serializer quyet dinh, khong phai contract can giu —
    # kiem su ton tai cua <img> + 2 attribute, khong kiem nguyen van chuoi.
    assert "<img " in raw
    assert 'src="a.jpg"' in raw
    assert 'alt="Anh minh hoa"' in raw
    assert "Banh rat ngon." in raw
    assert "Very tasty bread." not in raw


def test_write_translated_monolingual_preserves_img_child_matched_multi_run(
    tmp_path: Path,
) -> None:
    """Y2(c), ca nhieu text node xen ke <img>: neu ban dich giu DUNG so
    luong doan text tuong ung (dem bang _text_runs_under), app khop 1-1 theo
    dung thu tu tai lieu — <img> khong bao gio bi dung toi vi khong co lenh
    xoa/thay the nao nham vao no."""
    path = _build_minimal_epub(
        tmp_path / "img_matched.epub",
        '<p>Mix <b>flour</b> with <img src="b.jpg" alt="step"/> water.</p>',
    )
    doc = EpubDocument.load(path)
    assert len(doc.units) == 1

    from src.services.epub_document import _text_runs_under

    unit = doc.units[0]
    original_runs = _text_runs_under(_fragment_children_of_unit_text(unit.text))
    assert len(original_runs) == 4  # "Mix ", "flour", " with ", " water."

    # "." nam TRONG <i> de tranh tao them 1 doan text rieng sau </i> (se
    # thanh 5 doan, khong con khop 4-4 nua) — dung dung 4 doan nhu ban goc.
    vi_html = "Tron <b>bot mi</b> voi <i>nuoc.</i>"
    translated_runs = _text_runs_under(_fragment_children_of_unit_text(vi_html))
    assert len(translated_runs) == 4  # "Tron ", "bot mi", " voi ", "nuoc."

    out = tmp_path / "img_matched_out.epub"
    doc.write_translated({unit.unit_id: vi_html}, out, bilingual=False)

    raw = zipfile.ZipFile(out).read("OEBPS/xhtml/chap1.xhtml").decode("utf-8")
    assert "<img " in raw
    assert 'src="b.jpg"' in raw
    assert 'alt="step"' in raw
    # Khop 1-1 dung thu tu: <b> goc GIU NGUYEN (chi doi text ben trong no),
    # khong bi thay bang cau truc cua ban dich.
    assert "<b>bot mi</b>" in raw
    assert "flour" not in raw
    assert "Tron " in raw
    assert " voi " in raw
    assert "nuoc." in raw


def test_write_translated_monolingual_img_mismatch_uses_documented_fallback(
    tmp_path: Path,
) -> None:
    """Y2(c) fallback (gap CHUA co thuat toan tuong minh trong Architecture.md
    — da bao cao PM 2026-09-09): khi ban dich KHONG giu dung so luong doan
    text goc (LLM gop nhieu cau lam mot), app KHONG duoc lam mat/hong <img>.
    Toan bo ban dich duoc gan vao text node GOC DAI NHAT (heuristic "noi dung
    chinh"), cac text node con lai GIU NGUYEN tieng Anh goc — biet gioi han,
    nhung khong danh doi cau truc/mat <img>."""
    path = _build_minimal_epub(
        tmp_path / "img_mismatch.epub",
        '<p>Mix <b>flour</b> with <img src="c.jpg" alt="step"/> water.</p>',
    )
    doc = EpubDocument.load(path)
    unit = doc.units[0]

    # 4 slot goc: "Mix "(4 ky tu), "flour"(5), " with "(6), " water."(7 —
    # DAI NHAT). Ban dich gop het thanh 1 cau lien tuc (1 doan) — LECH so
    # luong doan text so voi goc (4) -> roi vao nhanh fallback.
    vi_html = "Tron bot mi voi nuoc, tat ca cung mot luc."
    out = tmp_path / "img_mismatch_out.epub"
    doc.write_translated({unit.unit_id: vi_html}, out, bilingual=False)

    raw = zipfile.ZipFile(out).read("OEBPS/xhtml/chap1.xhtml").decode("utf-8")
    assert "<img " in raw  # <img> khong bao gio duoc mat
    assert 'src="c.jpg"' in raw
    assert 'alt="step"' in raw
    assert vi_html in raw  # gan vao slot dai nhat (" water." -> ban dich day du)
    # Cac slot ngan hon GIU NGUYEN tieng Anh goc (known limitation, khong bi
    # xoa/de trong).
    assert "Mix " in raw
    assert "flour" in raw
    assert " with " in raw
    from xml.etree import ElementTree as ET

    ET.fromstring(raw.encode("utf-8"))  # van well-formed sau fallback


# ---------------------------------------------------------------------------
# (f) Bug #EPUB-1 (QA vong 1 US-22 buoc 1/3, 2026-09-09): `&`/`<` tran trong
# ban dich bi mat du lieu AM THAM khi `write_translated()` ghi nguoc, vi
# `_fragment_children()` dua thang chuoi chua escape vao parser XML strict
# (lxml qua `features="xml"`) -- parser "chua chay" bang cach am tham CAT BO
# phan noi dung khong hop le, KHONG raise loi (`_validate_wellformed` khong
# bat duoc vi ket qua sau khi cat van la XML hop le). Golden case dung DUNG 2
# cau QA da do duoc that (khong tu bia): mat "hon nua cau sau dau '<'" tren
# fixture rieng, va mat "&C" trong "C&C Offset Printing" tren file Bread that.
# ---------------------------------------------------------------------------


def test_write_translated_bare_lt_in_translation_no_longer_silently_truncated(
    tmp_path: Path,
) -> None:
    """Bug #EPUB-1 golden case 1 (QA do that): vi_html co '<' tran (khong mo
    dau 1 the hop le trong _INLINE_PRESERVE_TAGS) khong duoc lam mat noi dung
    phia sau dau '<' -- truoc fix, chi con lai text TRUOC dau '<', mat hon
    nua cau, khong raise loi nao."""
    from bs4 import BeautifulSoup

    path = _build_minimal_epub(tmp_path / "lt.epub", "<p>Placeholder.</p>")
    doc = EpubDocument.load(path)
    unit = doc.units[0]

    vi_html = "Do am can duy tri o muc < 65% de tranh nhao qua uot."
    out = tmp_path / "lt_out.epub"
    doc.write_translated({unit.unit_id: vi_html}, out, bilingual=False)

    reloaded = EpubDocument.load(out)
    plain = BeautifulSoup(reloaded.units[0].text, "html.parser").get_text()
    assert plain == vi_html  # khong mat noi dung sau dau '<'

    from xml.etree import ElementTree as ET

    raw = zipfile.ZipFile(out).read("OEBPS/xhtml/chap1.xhtml")
    ET.fromstring(raw)  # van well-formed


def test_write_translated_bare_ampersand_in_translation_no_longer_silently_truncated(
    tmp_path: Path,
) -> None:
    """Bug #EPUB-1 golden case 2 (QA do that tren file Bread that,
    unit OEBPS/04_copy.xhtml#6): '&' tran trong ten rieng "C&C Offset
    Printing" bi mat thanh "C Offset Printing" (mat '&C') truoc fix."""
    from bs4 import BeautifulSoup

    path = _build_minimal_epub(tmp_path / "amp.epub", "<p>Placeholder.</p>")
    doc = EpubDocument.load(path)
    unit = doc.units[0]

    vi_html = "In an boi C&C Offset Printing Co. Ltd."
    out = tmp_path / "amp_out.epub"
    doc.write_translated({unit.unit_id: vi_html}, out, bilingual=False)

    reloaded = EpubDocument.load(out)
    plain = BeautifulSoup(reloaded.units[0].text, "html.parser").get_text()
    assert plain == vi_html
    assert "C&C" in plain  # khong mat '&C'


def test_write_translated_still_parses_trusted_inline_tags_alongside_bare_special_chars(
    tmp_path: Path,
) -> None:
    """Regression guard cho fix Bug #EPUB-1: escape '&'/'<' tran KHONG duoc
    lam hong cac the inline trong _INLINE_PRESERVE_TAGS (X4) -- chung van
    phai duoc parse thanh Tag that, khong bi escape nham thanh text."""
    from bs4 import BeautifulSoup

    path = _build_minimal_epub(tmp_path / "mixed.epub", "<p>Placeholder.</p>")
    doc = EpubDocument.load(path)
    unit = doc.units[0]

    vi_html = "Tron <b>bot mi</b> voi <i>nuoc & muoi</i> o nhiet do < 200 do C."
    out = tmp_path / "mixed_out.epub"
    doc.write_translated({unit.unit_id: vi_html}, out, bilingual=False)

    raw = zipfile.ZipFile(out).read("OEBPS/xhtml/chap1.xhtml").decode("utf-8")
    assert "<b>bot mi</b>" in raw  # the inline van la Tag that, khong bi escape
    assert "<i>nuoc &amp; muoi</i>" in raw  # & ben trong tag van duoc escape dung

    reloaded = EpubDocument.load(out)
    plain = BeautifulSoup(reloaded.units[0].text, "html.parser").get_text()
    assert plain == "Tron bot mi voi nuoc & muoi o nhiet do < 200 do C."


def test_inner_html_escapes_special_chars_in_source_text_node(tmp_path: Path) -> None:
    """`_inner_html()` (dung boi `EpubDocument.load()` de tao `EpubUnit.text`,
    X2) phai tra ve inner-HTML DUNG NGHIA -- escape `&`/`<` cua NavigableString
    con, khong chi cua Tag con. Cach cu (`str(NavigableString)`) tra ve text
    DA DECODE, khong re-escape (`BeautifulSoup('<p>a &amp; b</p>','xml')` ->
    `str(NavigableString)` = 'a & b', khong phai 'a &amp; b') -- day la 1
    trong 2 nguyen nhan goc Bug #EPUB-1 (QA da trace toi tan bs4)."""
    from bs4 import BeautifulSoup

    path = _build_minimal_epub(
        tmp_path / "src_escape.epub",
        "<p>C&amp;C Offset Printing &lt; 100 units</p>",
    )
    doc = EpubDocument.load(path)
    unit = doc.units[0]

    assert unit.text == "C&amp;C Offset Printing &lt; 100 units"
    plain = BeautifulSoup(unit.text, "html.parser").get_text()
    assert plain == "C&C Offset Printing < 100 units"


def _fragment_children_of_unit_text(inner_html: str) -> list:
    from bs4 import BeautifulSoup

    fragment = BeautifulSoup(f"<bb-fragment-root>{inner_html}</bb-fragment-root>", "html.parser")
    root = fragment.find("bb-fragment-root")
    return list(root.children) if root is not None else []


def test_write_translated_writes_via_tmp_then_replaces(tmp_path: Path) -> None:
    """Y5: ghi ra `<output>.tmp` roi thay the — khong duoc de lai file .tmp
    mo cong sau khi ghi xong."""
    src = tmp_path / "src.epub"
    src.write_bytes(SOURDOUGH_PATH.read_bytes())
    out = tmp_path / "out.epub"

    doc = EpubDocument.load(src)
    translations = {u.unit_id: u.text for u in doc.units[:1]}
    doc.write_translated(translations, out, bilingual=False)

    assert out.exists()
    assert not out.with_name(out.name + ".tmp").exists()


# ---------------------------------------------------------------------------
# full_text() / total_chars — dung cho loc glossary (6.6.5) va cost gate
# (buoc 2/3, NGOAI PHAM VI increment nay — chi kiem contract co ban).
# ---------------------------------------------------------------------------


def test_full_text_and_total_chars_are_plain_text_not_html() -> None:
    doc = EpubDocument.load(SOURDOUGH_PATH)
    full_text = doc.full_text()

    assert "<strong>" not in full_text
    assert "<sup>" not in full_text
    assert "1/3 cup soy grits" in full_text or "13 cup soy grits" not in full_text
    assert doc.total_chars == len(full_text)
    assert doc.total_chars > 0


# ---------------------------------------------------------------------------
# normalize_sup_sub() — US-15 nhanh EPUB->Markdown (Architecture.md §6.15.7
# muc C / §6.21.2). Bang 7 dong "Kết quả đã chạy thật" o §6.21.2 la bang KY
# VONG TEST BAT BUOC, khong phai vi du minh hoa.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # F-1: 5 dong phan so thuan cua chapter01.html.
        ("<sup>1</sup>/<sub>3</sub> cup soy grits", "1/3 cup soy grits"),
        # F-2 — case QUAN TRONG NHAT (§6.21.2): hon so, KHONG duoc ra
        # "11/3" (loi cua markdownify mac dinh / de xuat cua Expert).
        (
            "1<sup>1</sup>/<sub>3</sub> cups unbleached white flour",
            "1 1/3 cups unbleached white flour",
        ),
        # F-3: so mu, ke ca so mu am (khong duoc doc thanh phep tru).
        (
            "Area = x<sup>2</sup> + y<sup>3</sup> - 5x<sup>-1</sup>",
            "Area = x² + y³ - 5x⁻¹",
        ),
        # F-4: chi so duoi hoa hoc, ke ca ion (sup sau sub).
        (
            "H<sub>2</sub>O, CO<sub>2</sub>, Ca(OH)<sub>2</sub>, SO<sub>4</sub><sup>2-</sup>",
            "H₂O, CO₂, Ca(OH)₂, SO₄²⁻",
        ),
        # Chu thich dinh vao cau van van phai PHAN BIET duoc voi so thuong.
        ("network.<sup>12</sup>", "network.¹²"),
        # Khong map duoc sang Unicode (nhieu ky tu/chu cai) -> ASCII tuong
        # minh `^(...)`/`_(...)`.
        ("x<sup>a+b</sup>, V<sub>total</sub>", "x^(a+b), V_(total)"),
        ("10<sup>-6</sup> mol", "10⁻⁶ mol"),
    ],
)
def test_normalize_sup_sub_golden_table(html: str, expected: str) -> None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(f"<p>{html}</p>", "html.parser")
    normalize_sup_sub(soup)

    assert soup.p.get_text() == expected
    assert soup.find(("sup", "sub")) is None  # khong con the sup/sub nao


def test_normalize_sup_sub_pandoc_style_wraps_with_carets_and_tildes() -> None:
    """§6.21.2: `markdown_supsub_style="pandoc"` -> `x^2^` / `H~2~O`, KHAC
    voi mac dinh "unicode". Quy tac phan so o Buoc 1 GIONG NHAU o ca 2 che
    do (phan so khong phai sup/sub)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        "<p>x<sup>2</sup>, H<sub>2</sub>O, 1<sup>1</sup>/<sub>3</sub> cups flour</p>",
        "html.parser",
    )
    normalize_sup_sub(soup, style="pandoc")

    assert soup.p.get_text() == "x^2^, H~2~O, 1 1/3 cups flour"


# ---------------------------------------------------------------------------
# EpubDocument.to_markdown() — US-15 nhanh EPUB->Markdown (Architecture.md
# §6.15.7). Golden test tren CHINH ops/xhtml/chapter01.html cua sourdough
# (S15-8): 10 <img>, 214 <strong>, 26 <em>, 2 <h2>, 34 <h3>.
# ---------------------------------------------------------------------------


def test_to_markdown_golden_chapter01_html_counts(tmp_path: Path) -> None:
    """Dung dung CAC HAM NOI BO ma `to_markdown()` goi (`_parse_xhtml`,
    `_rewrite_image_srcs`, `normalize_sup_sub`, `markdownify.MarkdownConverter`)
    tren MOT tai lieu spine (`ops/xhtml/chapter01.html`) de doi chieu voi
    bang so do that cua S15-8 — tach rieng khoi tong ca cuon sach (co them
    anh tu cover/title, xem test_to_markdown_whole_book_* ben duoi)."""
    doc_href = "ops/xhtml/chapter01.html"
    images_out = tmp_path / "images"
    images_out.mkdir()

    with zipfile.ZipFile(SOURDOUGH_PATH) as zf:
        zip_names = set(zf.namelist())
        raw_bytes = zf.read(doc_href)
        soup, _parser_used = _parse_xhtml(raw_bytes)
        # So dem TRUOC normalize (so mu/chi so van la <sup>/<sub> luc nay,
        # dung dung ham that de kiem chinh contract Y1/X6 §6.15.7 muc B).
        assert len(soup.find_all("img")) == 10
        assert len(soup.find_all("strong")) == 214
        assert len(soup.find_all("em")) == 26
        assert len(soup.find_all("h2")) == 2
        assert len(soup.find_all("h3")) == 34

        _rewrite_image_srcs(soup, doc_href, zf, zip_names, images_out, {}, {})

    normalize_sup_sub(soup)
    assert soup.find(("sup", "sub")) is None

    body = soup.find("body") or soup
    markdown_text = markdownify.MarkdownConverter(heading_style="ATX").convert_soup(body)

    assert markdown_text.count("![") == 10
    assert len(list(images_out.iterdir())) == 10
    assert markdown_text.count("\n## ") + markdown_text.startswith("## ") == 2
    assert markdown_text.count("\n### ") + markdown_text.startswith("### ") == 34


def test_to_markdown_whole_book_produces_real_content_and_images(tmp_path: Path) -> None:
    """R6-03 tinh than (Architecture.md §6.15.7 muc G-5): mo file that ra
    xem co chu that + anh that, khong chi tin 1 string non-empty. Dung
    `EpubDocument.to_markdown()` public API (khong dung helper noi bo nhu
    test golden o tren) tren CA cuon sach that."""
    doc = EpubDocument.load(SOURDOUGH_PATH)
    images_out = tmp_path / "images"

    markdown_text = doc.to_markdown(images_out_dir=images_out)

    assert "Baking with Sourdough" in markdown_text
    assert "1/3 cup soy grits" in markdown_text  # normalize_sup_sub() chay dung
    assert "<sup>" not in markdown_text
    assert "<sub>" not in markdown_text
    written_images = list(images_out.iterdir())
    assert len(written_images) > 0
    for name in written_images:
        assert f"images/{name.name}" in markdown_text


def test_to_markdown_r6_02_heading_counts_match_units() -> None:
    """R6-02 (S15-8, giu nguyen theo §6.15.7 muc G-1): tu MOT `load()`, so
    h2/h3 trong `to_markdown()` phai == so unit co `tag in {"h2","h3"}` —
    day la soi day noi 2 projection (units DE DICH / to_markdown DE XUAT)
    cung mot lan parse. Sourdough KHONG co ca heading-toan-chu-so bi
    `_is_droppable_content()` drop khoi `units` (da tu kiem: h2=2/h2=2,
    h3=34/h3=34 khop tuyet doi) — neu file mau khac co ca do, assert nay
    phai duoc sua de TRU dung so bi drop, KHONG duoc noi long thanh `>=`."""
    doc = EpubDocument.load(SOURDOUGH_PATH)

    with tempfile.TemporaryDirectory() as td:
        markdown_text = doc.to_markdown(images_out_dir=Path(td) / "images")

    md_h2 = markdown_text.count("\n## ") + markdown_text.startswith("## ")
    md_h3 = markdown_text.count("\n### ") + markdown_text.startswith("### ")
    units_h2 = sum(1 for u in doc.units if u.tag == "h2")
    units_h3 = sum(1 for u in doc.units if u.tag == "h3")

    assert md_h2 == units_h2
    assert md_h3 == units_h3


def test_to_markdown_rejects_second_load_lineage_break(tmp_path: Path) -> None:
    """R6-02 lineage guard: `to_markdown()` PHAI dung `self._spine_hrefs` cua
    CHINH instance vua `load()` — kiem gian tiep bang cach xac nhan 2 lan
    `load()` doc lap tren CUNG 1 file cho ra `spine_hrefs` GIONG HET NHAU (vi
    load() luon tinh lai dung 1 cach) — tuc goi `load()` lai (neu Dev lam
    sai) se KHONG the bi phat hien boi so sanh gia tri, day la ly do
    Architecture.md yeu cau Reviewer trace bang doc code, khong chi bang
    test. Test nay it nhat khoa contract "spine_hrefs on dinh giua 2 lan
    load() doc lap"."""
    doc_a = EpubDocument.load(SOURDOUGH_PATH)
    doc_b = EpubDocument.load(SOURDOUGH_PATH)

    assert doc_a.spine_hrefs == doc_b.spine_hrefs
    assert doc_a.spine_hrefs == [
        "ops/xhtml/cover.html",
        "ops/xhtml/title.html",
        "ops/xhtml/copyright.html",
        "ops/xhtml/chapter01.html",
        "ops/xhtml/backmatter01.html",
    ]


# ---------------------------------------------------------------------------
# to_markdown() — anh: URL tuyet doi/data URI giu nguyen, entry thieu trong
# zip khong crash (Architecture.md §6.15.7 muc B).
# ---------------------------------------------------------------------------


def test_to_markdown_skips_external_and_data_uri_images(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    body = (
        '<p><img src="http://example.com/x.jpg" alt="ext"/></p>'
        '<p><img src="data:image/png;base64,AAAA" alt="data"/></p>'
    )
    _build_minimal_epub(epub_path, body)
    doc = EpubDocument.load(epub_path)

    images_out = tmp_path / "images"
    markdown_text = doc.to_markdown(images_out_dir=images_out)

    assert "http://example.com/x.jpg" in markdown_text
    assert "data:image/png;base64,AAAA" in markdown_text
    assert list(images_out.iterdir()) == []


def test_to_markdown_missing_image_entry_does_not_crash(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    body = '<p><img src="missing.jpg" alt="gone"/></p>'
    _build_minimal_epub(epub_path, body)
    doc = EpubDocument.load(epub_path)

    images_out = tmp_path / "images"
    markdown_text = doc.to_markdown(images_out_dir=images_out)

    # Khong raise — src giu nguyen trang (khong rewrite thanh images/...).
    assert "images/missing.jpg" not in markdown_text
    assert list(images_out.iterdir()) == []


# ---------------------------------------------------------------------------
# K-1 (Architecture.md §6.20.15) — unwrap koboSpan tai `_parse_xhtml()`, diem
# vao DUY NHAT ma load()/write_translated()/count_bb_vi_pairs()/to_markdown()
# deu dung chung. R6-02: test o day BAT BUOC assert CA 3 duong doc dung CHUNG
# 1 phep unwrap — khong chi assert rieng le tung ham.
# ---------------------------------------------------------------------------

_KOBO_SPAN_BODY = (
    "<p>Preheat the oven "
    '<span class="koboSpan" id="kobo.1.1">to 220C</span>'
    ", then "
    '<span class="koboSpan" id="kobo.1.2">add the flour</span>'
    " and knead.</p>"
    # Mo phong span pagebreak that (khong co class koboSpan) — id DUOC
    # page-list tham chieu trong EPUB that, KHONG duoc dung toi boi K-1.
    # Bo prefix `epub:` (khong khai bao namespace o helper `_build_minimal_epub`)
    # de tranh loi parse XML khong lien quan toi noi dung dang test o day.
    '<span class="pagebreak" id="page_1" title="1"/>'
)


def test_unwrap_kobo_spans_removes_only_kobospan_class_token(tmp_path: Path) -> None:
    """Don vi truc tiep tren `_unwrap_kobo_spans()`: chi `<span>` co class
    CHUA DUNG token `koboSpan` bi unwrap (giu nguyen con ben trong, mat the
    `<span>` bao ngoai) — span pagebreak (khong co class koboSpan, mo phong
    span `id="page_i"` DUOC page-list tham chieu trong EPUB that) PHAI con
    nguyen ca the lan id."""
    path = _build_minimal_epub(tmp_path / "kobo.epub", _KOBO_SPAN_BODY)
    with zipfile.ZipFile(path) as zf:
        raw = zf.read("OEBPS/xhtml/chap1.xhtml")

    soup, _parser_used = _parse_xhtml(raw)

    assert "koboSpan" not in str(soup)
    assert "kobo.1.1" not in str(soup)
    assert "kobo.1.2" not in str(soup)
    # Text ben trong cac span da unwrap phai con nguyen, lien mach (dung
    # `str(soup)` thay vi `get_text(" ")` — ham nay chen space GIUA MOI node
    # con, se lam sai lech gia dinh "lien mach" o day khong lien quan toi
    # unwrap).
    assert "<p>Preheat the oven to 220C, then add the flour and knead.</p>" in str(soup)
    # pagebreak span KHONG bi dung toi.
    assert 'id="page_1"' in str(soup)
    assert soup.find("span", attrs={"id": "page_1"}) is not None


def test_load_write_translated_and_to_markdown_share_same_kobo_unwrap(
    tmp_path: Path,
) -> None:
    """R6-02 — kiem CA 3 duong doc dung CHUNG 1 phep unwrap, tren CUNG 1 file
    co koboSpan multi-slot (mo phong dung kich ban da do that o Architecture.md
    §6.20.15: nhieu koboSpan/paragraph). Truoc K-1, `write_translated()` se
    dem 2 "slot" (2 koboSpan) trong khi ban dich unit tra ve 1 chuoi -> lech
    slot -> roi vao nhanh "Known limitation" (dich sot). Sau K-1: node goc
    doc lai qua `_parse_xhtml()` (trong `write_translated()`) DA unwrap CUNG
    kieu voi luc `load()` -> chi con 1 candidate node (`<p>`), khop 1-1 voi 1
    unit -> khong bao gio roi vao nhanh slot-mismatch do."""
    path = _build_minimal_epub(tmp_path / "kobo_lineage.epub", _KOBO_SPAN_BODY)

    # (1) load() — unit text KHONG con koboSpan, va CHI 1 unit (khong bi
    # koboSpan lam phinh so unit/slot).
    doc = EpubDocument.load(path)
    assert len(doc.units) == 1
    assert "koboSpan" not in doc.units[0].text
    assert "kobo." not in doc.units[0].text

    # (2) write_translated() — ban dich 1-cau THAY THE TOAN BO noi dung unit
    # duy nhat nay; PHAI ap dung DAY DU (khong bi cat/dich sot do lech slot),
    # va output KHONG con koboSpan/id "kobo.*" nao.
    vi_translation = "Làm nóng lò đến 220C, sau đó cho bột vào và nhào."
    out = tmp_path / "kobo_lineage_out.epub"
    doc.write_translated({doc.units[0].unit_id: vi_translation}, out, bilingual=False)

    with zipfile.ZipFile(out) as zf:
        raw_out = zf.read("OEBPS/xhtml/chap1.xhtml").decode("utf-8")
    assert "koboSpan" not in raw_out
    assert "kobo.1.1" not in raw_out
    assert "kobo.1.2" not in raw_out
    assert vi_translation in raw_out
    # Mat mat chap nhan duoc (K-1, Hieu da duyet HOI-05): id kobo.* bien mat.
    # pagebreak van con nguyen — KHONG bi dung toi boi K-1.
    assert 'id="page_1"' in raw_out

    from xml.etree import ElementTree as ET

    ET.fromstring(raw_out.encode("utf-8"))  # van well-formed

    # (3) to_markdown() — cung 1 phep unwrap, khong con koboSpan/id lo ra
    # trong markdown, text lien mach (khong bi tach doi boi 2 the <span>
    # rieng biet o giua).
    doc2 = EpubDocument.load(path)
    markdown_text = doc2.to_markdown(images_out_dir=tmp_path / "images")
    assert "koboSpan" not in markdown_text
    assert "kobo." not in markdown_text
    assert "Preheat the oven to 220C, then add the flour and knead." in markdown_text

    # (4) count_bb_vi_pairs() — mo LAI file output tu dia (khong tin bo nho),
    # cung dung `_parse_xhtml()` -> van dem dung 1 cap bb-vi (bilingual=False
    # o day khong tao node bb-vi nao, nhung ham phai chay khong loi tren file
    # da qua unwrap).
    out_bilingual = tmp_path / "kobo_lineage_out_bilingual.epub"
    doc3 = EpubDocument.load(path)
    doc3.write_translated({doc3.units[0].unit_id: vi_translation}, out_bilingual, bilingual=True)
    total, differing = count_bb_vi_pairs(out_bilingual)
    assert total == 1
    assert differing == 1
