"""Regression test cho bug tìm thấy bởi Domain Expert (2026-09-07, xem
`docs/Architecture.md` section "Bug #7 Ca C — Phản biện của Domain Expert") trong
code bước 7.2 (Ca A, numbered-list split) đã commit trước đó.

BỐI CẢNH BUG (đã tự verify độc lập bằng cách đọc source thật + đối chiếu lại
1 lần chạy live thật đã lưu — không chỉ tin lại Expert; xem CHANGELOG.md mục
"hotfix 7.2 — unicode rỗng khiến mục numbered-list bị bỏ dịch"):

babeldoc 0.6.4 chỉ cập nhật `PdfParagraph.unicode` khi gọi
`ParagraphFinder.update_paragraph_data(paragraph, update_unicode=True)`
(`paragraph_finder.py:124-158`) — mặc định `update_unicode=False`, không làm gì
với `.unicode`. `process_page` tự gọi đúng 1 lần với `update_unicode=True` cho
MỌI paragraph (`paragraph_finder.py:294`), NHƯNG lời gọi đó chạy TRƯỚC KHI patch
7.2 (`_split_numbered_list_paragraphs_on_page`, chạy SAU khi `process()` đã trả
về hoàn toàn) có cơ hội tạo paragraph mới. Paragraph mới tạo bởi 7.2 nếu KHÔNG
tự gọi `update_paragraph_data(..., update_unicode=True)` sẽ giữ nguyên
`unicode=""` (giá trị khởi tạo lúc construct `PdfParagraph`) —
`il_translator_llm_only.py:563-566` (`len(paragraph.unicode) < min_text_length`)
sẽ BỎ QUA HOÀN TOÀN paragraph đó, không gửi đi dịch — mục numbered-list bị giữ
nguyên tiếng Anh, KHÔNG phải do LLM tự "fallback" như CHANGELOG bước 7.2 đã ghi
nhầm lúc đầu.

Verify sống đã xác nhận đúng giả thuyết: 4/4 mục còn tiếng Anh trong 1 lần chạy
thật (`page14_numbered_list_source.pdf`, mục #12/#24/#32/#34) đều chính xác là
"nhóm thứ 2" của 4 cặp mà `numbered_list_split.split_paragraph_lines` tách ra —
đúng những paragraph MỚI được tạo bởi patch 7.2. Sau hotfix (thêm
`update_unicode=True`), verify sống lại: 0/35 mục còn tiếng Anh.

KHÔNG import `babeldoc` trong test này — package đó cố ý KHÔNG phải dependency
của app (`Architecture.md` X4-1: cài ở venv riêng qua `uv tool`), nên
`import babeldoc` sẽ luôn thất bại trong venv của app ở BẤT KỲ máy nào (không
phải vấn đề CI-only — đây là kiến trúc cố ý, không phải thiếu sót môi trường).
Vì vậy test này pin cứng bằng cách ĐỌC SOURCE THẬT của `sitecustomize.py` —
đủ để chặn hồi quy (ai đó lỡ bỏ mất `update_unicode=True` khi sửa hàm), không
cần chạy babeldoc thật. Cơ chế fix (rằng `update_unicode=True` thật sự khiến
`.unicode` được điền) đã verify trực tiếp bằng cách đọc
`paragraph_finder.py:124-158` (trích trong Architecture.md) — không suy đoán.
"""

from __future__ import annotations

import re
from pathlib import Path

_SITECUSTOMIZE_PATH = Path(__file__).parent.parent / "src" / "babeldoc_shim" / "sitecustomize.py"


def _extract_function_body(source: str, func_name: str) -> str:
    match = re.search(rf"def {func_name}\(.*?\n(?=\ndef |\Z)", source, re.DOTALL)
    assert match, f"khong tim thay ham {func_name} trong sitecustomize.py"
    return match.group(0)


def test_sitecustomize_calls_update_paragraph_data_with_update_unicode_true() -> None:
    """Pin cứng: patch 7.2 (`_split_numbered_list_paragraphs_on_page`) PHẢI gọi
    `update_paragraph_data(..., update_unicode=True)` cho CẢ paragraph gốc bị cắt
    (nhóm đầu) LẪN paragraph mới tạo (nhóm sau) — thiếu 1 trong 2 đều tái hiện
    lại bug Domain Expert tìm thấy (2026-09-07)."""
    source = _SITECUSTOMIZE_PATH.read_text(encoding="utf-8")
    func_body = _extract_function_body(source, "_split_numbered_list_paragraphs_on_page")

    calls = re.findall(r"self\.update_paragraph_data\(([^)]*)\)", func_body)
    assert len(calls) == 2, (
        f"ky vong dung 2 loi goi update_paragraph_data trong ham nay, thay {len(calls)}: {calls}"
    )
    for call_args in calls:
        assert "update_unicode=True" in call_args, (
            f"loi goi update_paragraph_data thieu update_unicode=True: {call_args!r} — "
            "day chinh la bug Domain Expert tim thay (2026-09-07): thieu flag nay "
            "khien paragraph moi/paragraph bi cat giu unicode sai (rong hoac stale) "
            "va bi translator bo qua hoan toan hoac dich nham noi dung."
        )


def test_numbered_list_split_touches_only_the_documented_two_call_sites() -> None:
    """Bảo vệ giả định của test trên: nếu sau này ai thêm 1 lời gọi
    `update_paragraph_data` thứ 3 vào hàm này mà quên soát lại test trên, ít
    nhất test này báo động số lượng lời gọi đã đổi (thay vì âm thầm bỏ qua)."""
    source = _SITECUSTOMIZE_PATH.read_text(encoding="utf-8")
    func_body = _extract_function_body(source, "_split_numbered_list_paragraphs_on_page")
    assert func_body.count("PdfParagraph(") == 1, (
        "ham nay duoc thiet ke chi tao paragraph moi o DUNG 1 cho (nhom thu 2 tro "
        "di trong vong lap groups) — neu so cho tao PdfParagraph doi, test pin cung "
        "o tren co the khong con bao ve dung cho"
    )


def test_toc_split_logs_when_monotonic_or_fraction_gate_blocks_a_candidate() -> None:
    """Pin cứng yêu cầu Z8-2(iv)/AA2 dòng Z4 (Domain Expert, chấp nhận bởi Tech
    Lead trong "Quyết định cuối..." AA2): khi cổng `m/L` (`REASON_LOW_FRACTION`)
    hoặc cổng số trang không giảm (`REASON_NOT_MONOTONIC`) CHẶN một paragraph đã
    có >= 2 dòng được đánh dấu là đuôi mục lục, `_split_toc_paragraphs_in_list`
    PHẢI log 1 dòng cảnh báo — để 7.4-e/7.4-d có số liệu thật về tần suất các
    cổng này chặn nhầm thay vì chỉ có lý luận trên giấy. Ban đầu yêu cầu này chỉ
    được implement trong script đo của spike 7.4-a, KHÔNG có trong code production
    — Reviewer phát hiện thiếu (non-blocking, review 7.4-b→e) và đã được bổ sung."""
    source = _SITECUSTOMIZE_PATH.read_text(encoding="utf-8")
    func_body = _extract_function_body(source, "_split_toc_paragraphs_in_list")

    assert "REASON_LOW_FRACTION" in func_body and "REASON_NOT_MONOTONIC" in func_body, (
        "ham nay phai tham chieu ca 2 hang REASON_LOW_FRACTION va "
        "REASON_NOT_MONOTONIC de biet khi nao can log canh bao (AA2 dong Z4)"
    )
    assert "logger.warning" in func_body and "tail_marks" in func_body, (
        "ham nay phai log 1 dong canh bao (dung result.tail_marks) khi cong "
        "m/L hoac monotonic chan mot paragraph co >= 2 dong danh dau — thieu "
        "logging nay la issue non-blocking Reviewer da flag o review 7.4-b→e"
    )
