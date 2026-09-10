"""`parse_epub_batch_response()` against a REAL DeepSeek reply (Protocol 5 mục
3, Architecture.md 6.20.12 X4) — `tests/fixtures/epub_llm/` was captured from
1 real API call (see the fixture's `README.md` for cost/date/model), NOT
hand-written. `tests/test_epub_batch_prompt.py` covers the parser's tolerance
rules in isolation with synthetic strings; this file is the counterpart that
proves the parser actually works on what the real model sends back.
"""

import json
from pathlib import Path

import pytest

from src.core.prompt_builder import parse_epub_batch_response, parse_epub_batch_response_detailed

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_ch1_5units.json"
)

COMMA_SEPARATED_JSON_OBJECTS_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_comma_separated_json_objects.json"
)

TRAILING_GARBAGE_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_ch1_trailing_garbage.json"
)

MULTI_JSON_OBJECT_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_ch1_multi_json_object.json"
)

SPURIOUS_CLOSING_BRACES_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_single_object_spurious_closing_braces.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_trailing_garbage_fixture() -> dict:
    return json.loads(TRAILING_GARBAGE_FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_multi_json_object_fixture() -> dict:
    return json.loads(MULTI_JSON_OBJECT_FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_comma_separated_json_objects_fixture() -> dict:
    return json.loads(
        COMMA_SEPARATED_JSON_OBJECTS_FIXTURE_PATH.read_text(encoding="utf-8")
    )


def _load_spurious_closing_braces_fixture() -> dict:
    return json.loads(SPURIOUS_CLOSING_BRACES_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_file_exists_and_was_a_real_call() -> None:
    fixture = _load_fixture()
    assert fixture["provider"] == "deepseek"
    # Protocol 5 muc 3: chi phi that > 0 la bang chung day la 1 request that,
    # khong phai mock — 1 mock khong the co estimated_cost_usd > 0.
    assert fixture["estimated_cost_usd"] > 0
    assert fixture["input_tokens"] > 0
    assert fixture["output_tokens"] > 0
    # R6-02 (§6.20.9 soi day thu 4): system_prompt THAT gui di phai chua
    # marker contract JSON, khong chi "da goi provider.translate()".
    assert fixture["system_prompt_marker_check"] is True


def test_parse_real_deepseek_response_returns_all_expected_ids() -> None:
    fixture = _load_fixture()
    expected_ids = {str(item["id"]) for item in fixture["request_payload"]}

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    assert set(result.keys()) == expected_ids
    for value in result.values():
        assert value.strip() != ""


def test_parse_real_deepseek_response_preserves_inline_markup_and_numbers() -> None:
    """X1/X2/X4 tren du lieu THAT: giu strong/br/sup/sub dung so luong, va
    dong HON SO (N-1, Architecture.md 6.20.12) khong bi gop sai thanh "11/3"."""
    fixture = _load_fixture()
    expected_ids = {str(item["id"]) for item in fixture["request_payload"]}

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    ingredients_list = result["1"]  # <strong>...</strong><br/> x4
    assert ingredients_list.count("<strong>") == 4
    assert ingredients_list.count("<br/>") == 3

    plain_fraction = result["3"]  # <sup>1</sup>/<sub>3</sub> cup ...
    assert "<sup>1</sup>" in plain_fraction
    assert "<sub>3</sub>" in plain_fraction

    mixed_number = result["4"]  # 1<sup>1</sup>/<sub>3</sub> cups ...
    assert "<sup>1</sup>" in mixed_number
    assert "<sub>3</sub>" in mixed_number
    # N-1: markdownify mac dinh (Expert de xuat) cho ra "11/3" o day — dung
    # cach nay (giu nguyen <sup>/<sub> qua LLM, X1+X2) phai KHONG co "11/3"
    # dinh lien nhau trong ket qua.
    assert "11/3" not in mixed_number.replace(" ", "")


def test_parse_real_deepseek_response_does_not_translate_page_anchor_away() -> None:
    """Unit 0 la 1 h3 heading co <a id="page_4"/> di kem — giu the <a> (nam
    trong _INLINE_PRESERVE_TAGS/X4) la dung hop dong, du contract khong bat
    buoc giu attribute `id` cu the (Y2(a) chi bat buoc STRIP id cho nhanh
    bilingual=True, khong lien quan o day)."""
    fixture = _load_fixture()
    expected_ids = {str(item["id"]) for item in fixture["request_payload"]}

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    heading = result["0"]
    assert "<a " in heading


# ---------------------------------------------------------------------------
# Trailing-garbage-after-valid-JSON — bug Dev tu bat gap khi chay live E2E
# full-book cho US-22 Buoc 2/3 (khong nam trong review-report goc cua vong
# nay). Golden fixture RIENG (Protocol 5 muc 3) vi day la 1 hinh dang phan
# hoi LLM KHAC han: JSON hop le nhung co 1 ky tu thua sau dau `}` dong.
# ---------------------------------------------------------------------------


def test_trailing_garbage_fixture_file_exists_and_was_a_real_call() -> None:
    fixture = _load_trailing_garbage_fixture()
    assert fixture["provider"] == "deepseek"
    assert fixture["estimated_cost_usd"] > 0
    assert fixture["input_tokens"] > 0
    assert fixture["output_tokens"] > 0
    assert fixture["system_prompt_marker_check"] is True
    # Xac nhan chinh xac day la ca that: raw_response_text PHAI that su lam
    # json.loads() ban dau that bai voi "Extra data" (khong phai fixture da
    # bi "sua sach" tay truoc khi luu).
    assert fixture["json_decode_error_before_fix"] is not None
    assert "Extra data" in fixture["json_decode_error_before_fix"]


def test_raw_response_text_is_genuinely_malformed_before_parser_fix() -> None:
    """Xac nhan tien de cua bug: `json.loads()` THO (chua qua
    `parse_epub_batch_response()`) phai FAIL that tren chinh
    `raw_response_text` da capture — neu khong, fixture khong con dai dien
    cho ca that nua (vd bi format lai vo tinh khi luu)."""
    fixture = _load_trailing_garbage_fixture()
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        json.loads(fixture["raw_response_text"])


def test_parse_epub_batch_response_recovers_from_trailing_garbage() -> None:
    """`parse_epub_batch_response()` (sau fix) phai trich xuat dung noi dung
    JSON hop le nam TRUOC ky tu thua, thay vi coi ca phan hoi la hong hoan
    toan (`{}`) -- truoc fix, ca nay khien unit duy nhat trong chunk bi coi
    la "thieu ban dich" NGAY CA SAU 1 vong goi lai rieng le (vi goi lai van
    tra ve cung 1 dang loi deterministic), lam chunk that bai that su (E-09)
    du LLM da dich dung noi dung -- tai hien 2 lan lien tiep qua
    `run_job()` day du tren file Sourdough that."""
    fixture = _load_trailing_garbage_fixture()
    expected_ids = {str(item["id"]) for item in fixture["request_payload"]}

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    assert set(result.keys()) == expected_ids
    assert result["0"] == fixture["parsed_after_trailing_garbage_fix"]["0"]
    # Noi dung DA duoc dich that (co dau tieng Viet), khong phai ban goc
    # tieng Anh vong lai nguyen van.
    assert "đơn giản" in result["0"]
    assert "Two simpler ways" not in result["0"]


# ---------------------------------------------------------------------------
# Multiple separate top-level JSON objects in 1 reply — Bug #EPUB-B2-3 (QA
# vong 2/5, test-report.md 2026-09-10). Golden fixture DAY DU (Protocol 5 muc
# 3) — capture qua 1 lan goi API DeepSeek THAT (PM da duyet, 2026-09-10,
# input_tokens=1994/output_tokens=1279/estimated_cost_usd=0.00128282), dung
# CHINH XAC slice unit index 45-55 (11 unit, chapter01.html#36..#46) da lam
# job that fail trong QA vong 2/5, tai hien duoc ngay lan goi dau tien. Khac
# fixture "_partial_capture" cu (da xoa) — fixture nay la byte-for-byte THAT
# 100% cho toan bo 11 id, khong con placeholder/reconstructed nao.
# ---------------------------------------------------------------------------


def test_multi_json_object_fixture_file_exists_and_was_a_real_call() -> None:
    fixture = _load_multi_json_object_fixture()
    assert fixture["provider"] == "deepseek"
    assert fixture["estimated_cost_usd"] > 0
    assert fixture["input_tokens"] > 0
    assert fixture["output_tokens"] > 0
    assert fixture["system_prompt_marker_check"] is True
    # Sanity: fixture text really does make raw json.loads() fail exactly like
    # the real bug (Extra data), not some already-fixed/cleaned-up string.
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        json.loads(fixture["raw_response_text"])


def test_parse_recovers_all_ids_from_multiple_concatenated_json_objects() -> None:
    """Trung tam cua fix Bug #EPUB-B2-3: truoc fix, `parse_epub_batch_response()`
    chi giu object DAU TIEN (chi co id "0") va mat toan bo id "1".."10" - fix
    phai gop TAT CA object top-level tim duoc, khong chi object dau."""
    fixture = _load_multi_json_object_fixture()
    expected_ids = set(fixture["expected_ids"])

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    assert set(result.keys()) == expected_ids
    for value in result.values():
        assert value.strip() != ""


def test_parse_multi_json_object_keeps_genuinely_real_content() -> None:
    """Toan bo 11 id trong fixture nay la THAT 100% (khong con placeholder
    nhu ban "_partial_capture" cu) - xac nhan noi dung cu the tai id "0"
    (dau), "2" (co the <em>/<a id=...>), "9" va "10" (cuoi, khop dung cau QA
    da trich trong docs/test-report.md khi phat hien bug)."""
    fixture = _load_multi_json_object_fixture()
    expected_ids = set(fixture["expected_ids"])

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    assert result["0"].startswith(
        'Để hồi sinh một men cái đã quá già, bạn cần phải "làm ngọt nồi".'
    )
    assert result["2"] == '<em><a id="page_7"/>Bổ sung lại cho nồi men</em>'
    assert (
        result["9"]
        == "Hãy ghi nhớ vài quy tắc này về sourdough khi bạn làm theo các quy "
        "trình cơ bản vốn là điển hình khi làm việc với sourdough và hơi khác "
        "so với các kiểu nướng bánh khác."
    )
    assert result["10"] == '<a id="page_8"/>Các quy trình cơ bản'


def test_parse_multi_json_object_unit_ids_match_reported_bug_location() -> None:
    """Fixture phai dung dung slice da lam job that fail trong QA vong 2/5
    (docs/test-report.md: chunk 1, vd id 'ops/xhtml/chapter01.html#37')."""
    fixture = _load_multi_json_object_fixture()
    assert fixture["unit_ids_in_order"][1] == "ops/xhtml/chapter01.html#37"
    assert len(fixture["unit_ids_in_order"]) == 11


# ---------------------------------------------------------------------------
# Bug #EPUB-B2-4 (test-report.md, QA vong 3/5, 2026-09-10): CUNG ho loi voi
# Bug #EPUB-B2-3 o tren (DeepSeek tra nhieu JSON value roi rac thay vi 1 object
# gom du id) nhung noi nhau bang DAU PHAY (`}, {`) thay vi xuong dong — fix cu
# (chi skip whitespace) dung lai ngay tai dau phay, chi giu duoc object dau
# tien trong 32 object. Fixture nay THAT 100% (lay tu log chan doan cua chinh
# QA vong 3/5, xem note trong file fixture), khong viet tay theo Protocol 5
# R5-01. Fix lan nay TONG QUAT HOA thuat toan (tim `{`/`[` tiep theo thay vi
# chi skip whitespace) thay vi vi them 1 truong hop dac biet cho dau phay.
# ---------------------------------------------------------------------------


def test_comma_separated_json_objects_fixture_file_exists_and_was_a_real_call() -> None:
    fixture = _load_comma_separated_json_objects_fixture()
    assert fixture["provider"] == "deepseek"
    assert fixture["estimated_cost_usd"] > 0
    assert fixture["input_tokens"] > 0
    assert fixture["output_tokens"] > 0
    assert fixture["system_prompt_marker_check"] is True
    # Sanity: raw json.loads() tho phai that su fail voi "Extra data" ngay tu
    # cho dau phay noi object dau va object thu 2 — chung minh day la ca that,
    # khong phai fixture da "sua sach" tay truoc khi luu.
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        json.loads(fixture["raw_response_text"])


def test_parse_recovers_all_32_ids_from_comma_separated_json_objects() -> None:
    """Truoc fix B2-4: parser chi giu object DAU TIEN (id "0"), mat toan bo id
    "1".."31" — vi fix B2-3 chi skip whitespace, dung lai ngay tai dau phay
    (khong phai whitespace) giua 2 object. Sau fix TONG QUAT: phai gop du ca
    32 object, bat ke ky tu phan cach giua chung la gi."""
    fixture = _load_comma_separated_json_objects_fixture()
    expected_ids = set(fixture["expected_ids"])
    assert len(expected_ids) == 32

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    assert set(result.keys()) == expected_ids
    for value in result.values():
        assert value.strip() != ""


def test_parse_comma_separated_json_objects_keeps_genuinely_real_content() -> None:
    fixture = _load_comma_separated_json_objects_fixture()
    expected_ids = set(fixture["expected_ids"])

    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)

    assert result["0"].startswith("Trộn 4 nguyên liệu đầu tiên")
    assert result["31"] == "<strong>¼ cup hạt cắt nhỏ</strong>"


def test_parse_comma_separated_json_objects_also_has_trailing_garbage() -> None:
    """raw_response_text ket thuc bang 1 dau `}` thua sau object cuoi cung (id
    "31") — vua la bang chung that ve "trailing garbage sau JSON hop le" (nhu
    fixture rieng o tren), vua xac nhan thuat toan moi khong co gang decode
    dau `}` do thanh du lieu (khong tim thay `{`/`[` nao sau no nen dung lai
    dung luc, khong raise, khong mat id nao da parse duoc truoc do)."""
    fixture = _load_comma_separated_json_objects_fixture()
    assert fixture["raw_response_text"].rstrip().endswith('"}}')


# ---------------------------------------------------------------------------
# Bang chung quan trong nhat rang fix nay la TONG QUAT (khong phai va rieng
# dau phay): 1 ky tu phan cach HOAN TOAN CHUA TUNG GAP (dau cham phay `;`) phai
# TU DONG duoc xu ly dung MA KHONG CAN SUA THEM CODE, vi thuat toan khong con
# quan tam ky tu phan cach cu the la gi nua, chi tim vi tri `{`/`[` tiep theo.
# ---------------------------------------------------------------------------


def test_parse_handles_never_before_seen_separator_without_further_code_changes() -> None:
    raw = '{"0": "Xin chao"};{"1": "Tam biet"}'

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {"0": "Xin chao", "1": "Tam biet"}


def test_parse_handles_mixed_whitespace_separator_without_further_code_changes() -> None:
    raw = '{"0": "Xin chao"}   \t\n{"1": "Tam biet"}'

    result = parse_epub_batch_response(raw, expected_ids={"0", "1"})

    assert result == {"0": "Xin chao", "1": "Tam biet"}


# ---------------------------------------------------------------------------
# Architecture.md §6.20.14.3 — Lop B (`_salvage_epub_id_pairs()` /
# `parse_epub_batch_response_detailed()`), them SAU khi cham gioi han
# Protocol 3 voi Bug #EPUB-B2-5 (response chi co 1 dau `{` nhung 32 dau `}`
# thua — thuat toan "tim `{`/`[` tiep theo" cua fix B2-4 khong con `{` nao
# de tim, chi cuu duoc 1/32 id). B-4: chay tren CA 5 golden fixture da co,
# KHONG goi API moi.
# ---------------------------------------------------------------------------


def test_layer_b_5units_fixture_no_salvage_needed() -> None:
    fixture = _load_fixture()
    expected_ids = {str(item["id"]) for item in fixture["request_payload"]}

    outcome = parse_epub_batch_response_detailed(fixture["raw_response_text"], expected_ids)

    assert set(outcome.translations.keys()) == expected_ids
    assert outcome.salvaged_ids == frozenset()


def test_layer_b_trailing_garbage_fixture_no_salvage_needed() -> None:
    fixture = _load_trailing_garbage_fixture()
    expected_ids = {str(item["id"]) for item in fixture["request_payload"]}

    outcome = parse_epub_batch_response_detailed(fixture["raw_response_text"], expected_ids)

    assert set(outcome.translations.keys()) == expected_ids
    assert outcome.salvaged_ids == frozenset()


def test_layer_b_multi_json_object_fixture_no_salvage_needed() -> None:
    """Bug #EPUB-B2-3 — parser chat da tu cuu duoc du 11/11, Lop B khong can
    kich hoat."""
    fixture = _load_multi_json_object_fixture()
    expected_ids = set(fixture["expected_ids"])

    outcome = parse_epub_batch_response_detailed(fixture["raw_response_text"], expected_ids)

    assert set(outcome.translations.keys()) == expected_ids
    assert outcome.salvaged_ids == frozenset()


def test_layer_b_comma_separated_json_objects_fixture_no_salvage_needed() -> None:
    """Bug #EPUB-B2-4 — parser chat da tu cuu duoc du 32/32, Lop B khong can
    kich hoat."""
    fixture = _load_comma_separated_json_objects_fixture()
    expected_ids = set(fixture["expected_ids"])

    outcome = parse_epub_batch_response_detailed(fixture["raw_response_text"], expected_ids)

    assert set(outcome.translations.keys()) == expected_ids
    assert outcome.salvaged_ids == frozenset()


def test_spurious_closing_braces_fixture_file_exists_and_was_a_real_call() -> None:
    fixture = _load_spurious_closing_braces_fixture()
    assert fixture["provider"] == "deepseek"
    assert fixture["estimated_cost_usd"] > 0
    assert fixture["input_tokens"] > 0
    assert fixture["output_tokens"] > 0
    assert len(fixture["expected_ids"]) == 32
    # Xac nhan dung ca that: 1 dau `{` mo duy nhat nhung 32 dau `}` — day
    # chinh la Bug #EPUB-B2-5, khac han B2-3/B2-4 (N object rieng, moi object
    # co `{` rieng).
    raw = fixture["raw_response_text"]
    assert raw.count("{") == 1
    assert raw.count("}") == 32


def test_layer_a_parser_alone_only_recovers_1_of_32_ids_for_b2_5() -> None:
    """Truoc Lop B: parser chat (`parse_epub_batch_response()`, KHONG qua
    salvage) chi cuu duoc dung 1/32 id cho fixture nay — day la BANG CHUNG
    Bug #EPUB-B2-5 la GIOI HAN CAU TRUC that su cua huong "tim `{`/`[` tiep
    theo", khong phai loi trien khai sai fix B2-4 (dung y Architecture.md
    §6.20.14.1: "moi fix truoc deu phai doan truoc hinh dang hong")."""
    fixture = _load_spurious_closing_braces_fixture()

    strict_only = _decode_concatenated_json_objects_result(fixture["raw_response_text"])

    assert len(strict_only) == 1
    assert "0" in strict_only


def _decode_concatenated_json_objects_result(raw_text: str) -> dict:
    """Helper local — goi truc tiep `_decode_concatenated_json_objects()`
    (parser CHAT, khong qua Lop B) de chung minh no mot minh khong du cho
    fixture B2-5, khong phai vi ham nay bi go bo/sua doi boi Lop B."""
    from src.core.prompt_builder import _decode_concatenated_json_objects

    text = raw_text.strip()
    return _decode_concatenated_json_objects(text)


def test_layer_b_recovers_all_32_of_32_ids_for_bug_epub_b2_5() -> None:
    """Trung tam cua Lop B (§6.20.14.3 B-4) — day la fixture DUY NHAT ma
    parser chat khong the cuu duoc (chi 1/32), va la ly do vi sao Protocol 3
    da cham gioi han (5/5 vong Dev<->QA). Sau Lop B: 32/32, voi 31 id den tu
    salvage (id "0" den tu duong chuan, khong bi salvage ghi de — dung ngu
    nghia B-2 "KHONG BAO GIO de len gia tri da parse chat")."""
    fixture = _load_spurious_closing_braces_fixture()
    expected_ids = set(fixture["expected_ids"])

    outcome = parse_epub_batch_response_detailed(fixture["raw_response_text"], expected_ids)

    assert set(outcome.translations.keys()) == expected_ids
    assert outcome.strict_ids == frozenset({"0"})
    assert outcome.salvaged_ids == expected_ids - {"0"}
    assert len(outcome.salvaged_ids) == 31

    # parse_epub_batch_response() (API cong khai, khong doi chu ky) phai
    # phan anh dung ket qua nay — moi caller hien co (job_orchestrator.py)
    # deu goi ham nay, khong goi truc tiep _detailed.
    result = parse_epub_batch_response(fixture["raw_response_text"], expected_ids)
    assert set(result.keys()) == expected_ids


def test_layer_b_recovers_correct_content_for_id_31_bug_epub_b2_5() -> None:
    """Yeu cau cu the cua §6.20.14.3 B-4: noi dung id '31' phai dung
    '<strong>¼ cup hạt cắt nhỏ</strong>' — khong bi cat/hong ky tu dac biet
    (dau tieng Viet, the HTML)."""
    fixture = _load_spurious_closing_braces_fixture()
    expected_ids = set(fixture["expected_ids"])

    outcome = parse_epub_batch_response_detailed(fixture["raw_response_text"], expected_ids)

    assert outcome.translations["31"] == "<strong>¼ cup hạt cắt nhỏ</strong>"
    assert outcome.translations["0"].startswith(
        "Trộn 4 nguyên liệu đầu tiên"
    )


# ---------------------------------------------------------------------------
# Architecture.md §6.20.14.3 B-4 — 3 test tong hop (khong phu thuoc fixture)
# chung minh Lop B khong "nuot rac thanh du lieu".
# ---------------------------------------------------------------------------


def test_layer_b_does_not_create_fake_pair_from_substring_inside_translated_value() -> None:
    """Neu ban dich CHINH NO chua chuoi con `"7": "` (vi du unit la 1 doan
    van ban mau ve JSON), salvage KHONG duoc tao ra 1 cap gia cho id "7" tu
    ben trong gia tri cua 1 id khac — con tro `pos = end` sau moi lan an
    thanh cong phai ngan chan dung dieu nay."""
    raw = '{"3": "Vi du JSON: {\\"7\\": \\"gia tri gia\\"} khong phai id that"}'

    outcome = parse_epub_batch_response_detailed(raw, expected_ids={"3", "7"})

    assert outcome.translations.get("7") is None
    assert "7" not in outcome.salvaged_ids


def test_layer_b_keeps_complete_pairs_before_a_truncated_tail() -> None:
    """Response cut giua chung 1 gia tri (vd het max_tokens) — giu lai cac
    cap DA HOAN CHINH truoc do, bo cap cut (scanstring raise -> bo qua, KHONG
    doan phan con thieu)."""
    raw = '{"0": "hoan chinh"}{"1": "bi cat giua chu'

    outcome = parse_epub_batch_response_detailed(raw, expected_ids={"0", "1"})

    assert outcome.translations == {"0": "hoan chinh"}
    assert "1" not in outcome.translations


def test_layer_b_ignores_id_outside_expected_ids() -> None:
    """Id la thuan so nhung KHONG nam trong `expected_ids` (vd model tu
    them 1 id khong duoc yeu cau) phai bi loai, dung nhu duong chuan."""
    raw = '{"0": "that"}{"99": "khong duoc yeu cau"}'

    outcome = parse_epub_batch_response_detailed(raw, expected_ids={"0"})

    assert outcome.translations == {"0": "that"}
    assert "99" not in outcome.translations
    assert "99" not in outcome.salvaged_ids
