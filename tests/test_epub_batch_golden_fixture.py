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

from src.core.prompt_builder import parse_epub_batch_response

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_ch1_5units.json"
)

TRAILING_GARBAGE_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "epub_llm"
    / "deepseek_batch_response_sourdough_ch1_trailing_garbage.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_trailing_garbage_fixture() -> dict:
    return json.loads(TRAILING_GARBAGE_FIXTURE_PATH.read_text(encoding="utf-8"))


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
