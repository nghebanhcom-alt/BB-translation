"""Tests cho gate P0.1 (Architecture.md U4/P0.1, "layout_qa").

Protocol 5 R5-03 / Protocol 6 R6-02: cac test tren fixture "_source.pdf" o
`tests/fixtures/babeldoc/` dung PDF THAT da trich tu output production (khong
phai mock viet tay) va assert GIA TRI CU THE (goc xoay, so cap chong lan, noi
dung text) chu khong chi "gate chay khong loi". So lieu ky vong duoc do TRUC
TIEP tren fixture (xem docstring tung test) — trung voi so da bao cao trong
Architecture.md T3(c)/(d) cho fixture p67 (dir=(0.982,-0.191), goc -11 deg).

`_build_pdf` chi dung cho 2 test entity-preservation cuoi file: day KHONG
phai mock hanh vi babeldoc/pdf2zh (Protocol 5 khong ap dung — module nay
khong goi tool ben thu 3 nao), ma la PDF that duoc fitz tu ve de kiem tra
logic regex+bbox-matching CUA CHINH module nay o 1 truong hop bien co kiem
soat duoc (mat 1 thuc thc cu the) — thu tuong duong voi cach `font_shrink.py`
tu dung `fitz.Page` that trong test cua no.
"""

from pathlib import Path

import fitz
import pytest

from src.services.layout_qa import (
    LayoutQaFindingData,
    _check_entity_preservation,
    _check_rotated_text_prescan,
    _find_entities,
    _is_rotated,
    persist_findings,
    run_layout_qa_gate,
)

FIXTURES = Path(__file__).parent / "fixtures" / "babeldoc"
P67_ROTATED_CAPTION = FIXTURES / "rotated_text_p67_source.pdf"
P15_ROTATED_CHART = FIXTURES / "rotated_chart_p15_source.pdf"
P7_TOC_2COL = FIXTURES / "toc_2col_p7_source.pdf"


# --- (d) rotated-text prescan — real fixtures (T3-c/T3-d) -----------------


def test_rotated_text_prescan_matches_t3d_measurement_on_p67():
    """Architecture.md T3(d): khoi chu giai nghieng trang 67 co `dir =
    (0.982, -0.191)` ~ -11 deg, 16-17 dong (dem ca dong tieu de "Disaccharide"
    thi la 17). Assert dung gia tri do that tren fixture, khong doan."""
    doc = fitz.open(P67_ROTATED_CAPTION)
    findings = _check_rotated_text_prescan(doc[0], page_number=67)
    doc.close()

    assert len(findings) == 17
    assert all(f.page_number == 67 for f in findings)
    assert all(f.check_type == "rotated_text_prescan" for f in findings)
    assert all(f.severity == "blocker" for f in findings)

    angles = {round(f.detail["angle_deg"]) for f in findings}
    assert angles == {-11}

    first = findings[0]
    assert first.detail["text"] == "Disaccharide"
    dx, dy = first.detail["dir"]
    assert dx == pytest.approx(0.9816276431083679, abs=1e-6)
    assert dy == pytest.approx(-0.19080695509910583, abs=1e-6)

    full_text = " ".join(f.detail["text"] for f in findings)
    assert "disaccharide is composed of" in full_text


def test_rotated_text_prescan_matches_conversion_chart_p15():
    """Trang 15 (bang quy doi) — goc xoay khac (20 deg, khong phai -11 deg)
    de dam bao check khong hardcode 1 goc duy nhat."""
    doc = fitz.open(P15_ROTATED_CHART)
    findings = _check_rotated_text_prescan(doc[0], page_number=15)
    doc.close()

    assert len(findings) == 100
    angles = {round(f.detail["angle_deg"]) for f in findings}
    assert angles == {20}
    texts = {f.detail["text"] for f in findings}
    assert "CONVERSION CHART" in texts


def test_rotated_text_prescan_empty_on_horizontal_toc_page():
    """Trang muc luc 2 cot la van xuoi ngang (0 deg) — khong duoc flag nham
    thanh "chu xoay"."""
    doc = fitz.open(P7_TOC_2COL)
    findings = _check_rotated_text_prescan(doc[0], page_number=7)
    doc.close()

    assert findings == []


@pytest.mark.parametrize(
    ("angle_deg", "expected"),
    [
        (0.0, False),
        (0.05, False),
        (0.15, True),
        (90.0, False),
        (89.95, False),
        (89.8, True),
        (180.0, False),
        (-11.0, True),
        (20.0, True),
    ],
)
def test_is_rotated_tolerance_matches_babeldoc_threshold(angle_deg, expected):
    """+-0.1 deg quanh 0/90 deg, dung nguong `il_creater.py:968-974` cua
    babeldoc (Architecture.md T-01) ma gate nay dung de du doan truoc chu se
    bi babeldoc vut mat."""
    assert _is_rotated(angle_deg) is expected


# --- (a)/(b)/(c) real-fixture geometry checks ------------------------------


def test_run_layout_qa_gate_output_only_finds_real_overlaps_on_toc_page():
    """Khong truyen source -> chi chay (a)/(b)/(c), `source_checked` False.
    Trang muc luc 2 cot that co 3 cap block giao > 5% (do that tren fixture,
    khong phai gia dinh)."""
    report = run_layout_qa_gate(P7_TOC_2COL)

    assert report.source_checked is False
    assert all(f.check_type != "rotated_text_prescan" for f in report.findings)
    assert all(f.check_type != "entity_loss" for f in report.findings)

    overlaps = [f for f in report.findings if f.check_type == "overlap"]
    assert len(overlaps) == 3
    assert all(f.severity == "critical" for f in overlaps)


def test_run_layout_qa_gate_with_source_builds_ranked_page_queue():
    """Voi source truyen vao (chinh no lam ca 2 vai, vi fixture chi co 1
    trang va khong co ban dich rieng), gate phai tra ve HANG DOI theo trang
    xep hang giam dan theo severity_score — khong phai 1 pass/fail duy
    nhat."""
    report = run_layout_qa_gate(P67_ROTATED_CAPTION, source_pdf_path=P67_ROTATED_CAPTION)

    assert report.source_checked is True
    assert len(report.page_queue) == 1
    entry = report.page_queue[0]
    assert entry.page_number == 1
    # severity_score = 3 (blocker) * 17 (rotated) + 2 (critical) * so overlap/
    # drawing/image that do duoc — it nhat phai > 0 va bang tong trong so that.
    expected_score = sum(
        {"blocker": 3, "critical": 2, "major": 1, "minor": 0}[f.severity] for f in entry.findings
    )
    assert entry.severity_score == expected_score
    assert entry.severity_score > 0
    # Sap xep giam dan theo trong so trong tung trang: finding dau tien phai
    # co trong so >= finding cuoi cung.
    weights = [
        {"blocker": 3, "critical": 2, "major": 1, "minor": 0}[f.severity] for f in entry.findings
    ]
    assert weights == sorted(weights, reverse=True)


def test_entity_preservation_no_false_positive_when_translation_is_identical():
    """Khi ban 'dich' giong het ban goc (chinh no), moi thuc the deu con
    nguyen -> KHONG duoc flag entity_loss du block nao co chua thuc the
    (dung de bat false positive trong logic match bbox/IoU)."""
    report = run_layout_qa_gate(P67_ROTATED_CAPTION, source_pdf_path=P67_ROTATED_CAPTION)
    entity_findings = [f for f in report.findings if f.check_type == "entity_loss"]
    assert entity_findings == []


# --- (e) entity preservation — controlled real fitz-rendered PDFs ---------


def _build_pdf(blocks: list[tuple[str, tuple[float, float, float, float]]]) -> "fitz.Document":
    """Tao 1 PDF 1 trang that (khong phai mock du lieu) co cac block text tai
    dung toa do cho truoc, dung de kiem tra logic match-bbox+regex cua CHINH
    module nay (khong lien quan contract babeldoc/pdf2zh)."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    for text, (x0, y0, x1, y1) in blocks:
        page.insert_textbox(fitz.Rect(x0, y0, x1, y1), text, fontsize=10)
    return doc


def test_find_entities_extracts_all_four_categories():
    text = "Nướng ở 180°C trong 10 phút, dùng 250g bột mì và 1/2 thìa muối."
    entities = _find_entities(text)
    assert "180°C" in entities
    assert "250g" in entities
    assert "10 phút" in entities
    assert "1/2" in entities


def test_check_entity_preservation_flags_missing_temperature():
    """Block goc co '180°C'; block dich (o cung vi tri bbox) da lam mat con
    so nhiet do — phai bi flag entity_loss voi entity thieu dung la '180°C'."""
    source_doc = _build_pdf([("Bake at 180°C for 10 minutes.", (50, 50, 350, 90))])
    translated_doc = _build_pdf([("Nướng trong 10 phút.", (50, 50, 350, 90))])

    findings = _check_entity_preservation(source_doc[0], translated_doc[0], page_number=42)
    source_doc.close()
    translated_doc.close()

    assert len(findings) == 1
    finding = findings[0]
    assert finding.page_number == 42
    assert finding.check_type == "entity_loss"
    assert finding.severity == "blocker"
    assert "180°C" in finding.detail["missing_entities"]
    assert finding.detail["match_iou"] > 0.05


def test_check_entity_preservation_passes_when_all_entities_kept():
    source_doc = _build_pdf([("Bake at 180°C for 10 minutes.", (50, 50, 350, 90))])
    translated_doc = _build_pdf([("Nướng ở 180°C trong 10 phút.", (50, 50, 350, 90))])

    findings = _check_entity_preservation(source_doc[0], translated_doc[0], page_number=1)
    source_doc.close()
    translated_doc.close()

    assert findings == []


# --- persist_findings — asserts actual rows written, not just "was called" -


class _FakeSession:
    """Session gia toi thieu de assert DUNG DU LIEU duoc ghi (Protocol 6
    R6-02) — khong dung `unittest.mock.AsyncMock` de tranh assert chi
    `assert_called()` ma khong kiem tra gia tri thuc su duoc `add()`."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_persist_findings_writes_rows_with_correct_fields():
    findings = [
        LayoutQaFindingData(
            page_number=67,
            check_type="rotated_text_prescan",
            severity="blocker",
            detail={"text": "Disaccharide", "angle_deg": -11.0},
        )
    ]
    session = _FakeSession()

    await persist_findings(
        session,
        findings,
        job_id="job-123",
        run_label="spike_1page",
        source_file="p67.pdf",
    )

    assert session.committed is True
    assert len(session.added) == 1
    row = session.added[0]
    assert row.job_id == "job-123"
    assert row.run_label == "spike_1page"
    assert row.source_file == "p67.pdf"
    assert row.page_number == 67
    assert row.check_type == "rotated_text_prescan"
    assert row.severity == "blocker"
    assert '"text": "Disaccharide"' in row.detail
