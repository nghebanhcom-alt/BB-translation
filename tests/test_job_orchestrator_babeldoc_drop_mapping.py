"""BL-04 (Architecture.md 6.22.6, gate 6.22.9) — test THUAN cho
`_map_babeldoc_drop_report_to_findings()` (`src/core/job_orchestrator.py`),
KHONG can DB/session (Chunk duoc dung nhu 1 dataclass thuan, khong luu).

Protocol 6 R6-02: moi test assert GIA TRI CU THE (page_number, check_type,
detail, suppressed_overlap_count, checksum_mismatch_pages...), khong chi
"khong loi"/"co finding".
"""

from src.core.job_orchestrator import (
    _SEVERITY_BY_CHECK,
    BABELDOC_DROP_REPORT_INCOMPLETE_CHECK,
    BABELDOC_DROP_REPORT_MISMATCH_CHECK,
    BABELDOC_DROP_REPORT_UNAVAILABLE_CHECK,
    BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK,
    _map_babeldoc_drop_report_to_findings,
)
from src.models.chunk import Chunk
from src.services.babeldoc_runner import BabeldocDroppedParagraph, BabeldocDropReport


def _make_chunk(**overrides) -> Chunk:
    defaults: dict = {
        "job_id": "job-1",
        "chunk_index": 0,
        "page_start": 1,
        "page_end": 40,
        "overlap_start": None,
        "overlap_end": None,
    }
    defaults.update(overrides)
    return Chunk(**defaults)


def _dropped(page_number: int, debug_id: str = "abc12") -> BabeldocDroppedParagraph:
    return BabeldocDroppedParagraph(
        page_number=page_number,
        debug_id=debug_id,
        layout_label="plain text",
        box=(10.0, 20.0, 100.0, 200.0),
        optimal_scale=0.1,
        scale=None,
        text_excerpt="doan van bi mat vi khong vua khung",
        text_len=35,
    )


# --- Gate test #2 — test_drop_report_unavailable ----------------------------


def test_drop_report_unavailable_writes_single_finding_and_zero_drops() -> None:
    chunk = _make_chunk()
    drop_report = BabeldocDropReport(
        available=False,
        dropped=[],
        observed_pages=frozenset(),
        page_dropped_counts={},
        header_count=0,
        malformed_line_count=0,
        stdout_sentinel_count=0,
    )

    mapping = _map_babeldoc_drop_report_to_findings(drop_report, chunk)

    assert len(mapping.findings) == 1
    finding = mapping.findings[0]
    assert finding.check_type == BABELDOC_DROP_REPORT_UNAVAILABLE_CHECK
    assert finding.severity == _SEVERITY_BY_CHECK[BABELDOC_DROP_REPORT_UNAVAILABLE_CHECK]
    assert finding.severity == "major"
    assert finding.page_number == chunk.page_start
    assert mapping.unfit_drop_count == 0
    assert mapping.available is False


# --- Gate test #3 — test_drop_report_incomplete -----------------------------


def test_drop_report_incomplete_missing_pages_keeps_observed_drops() -> None:
    """Golden shape: 2 trang (17, 18) thieu dong `type=page` — trang thai 3
    (do duoc NHUNG khong tron ven), nhung finding drop DA quan sat duoc (trang
    5) van phai duoc ghi (khong bi bo qua vi 'chua tron ven')."""
    chunk = _make_chunk(page_start=1, page_end=40)
    expected = set(range(1, 41))
    observed = expected - {17, 18}
    drop_report = BabeldocDropReport(
        available=True,
        dropped=[_dropped(5)],
        observed_pages=frozenset(observed),
        page_dropped_counts={p: (1 if p == 5 else 0) for p in observed},
        header_count=1,
        malformed_line_count=0,
        stdout_sentinel_count=0,
    )

    mapping = _map_babeldoc_drop_report_to_findings(drop_report, chunk)

    check_types = [f.check_type for f in mapping.findings]
    assert check_types.count(BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK) == 1
    assert check_types.count(BABELDOC_DROP_REPORT_INCOMPLETE_CHECK) == 1

    unfit = next(f for f in mapping.findings if f.check_type == BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK)
    assert unfit.page_number == 5

    incomplete = next(
        f for f in mapping.findings if f.check_type == BABELDOC_DROP_REPORT_INCOMPLETE_CHECK
    )
    assert incomplete.page_number == chunk.page_start
    assert incomplete.detail["missing"] == [17, 18]
    assert incomplete.detail["unexpected"] == []
    assert incomplete.detail["checksum_mismatch_pages"] == []
    assert mapping.is_incomplete is True


# --- Gate test #4 — test_overlap_pages_filtered -----------------------------


def test_overlap_pages_filtered_suppresses_overlap_and_counts_them() -> None:
    chunk = _make_chunk(chunk_index=1, page_start=39, page_end=80, overlap_start=39, overlap_end=40)
    expected_pages = set(range(39, 81))
    drop_report = BabeldocDropReport(
        available=True,
        dropped=[_dropped(39), _dropped(40), _dropped(55)],
        observed_pages=frozenset(expected_pages),
        page_dropped_counts={p: (1 if p in (39, 40, 55) else 0) for p in expected_pages},
        header_count=1,
        malformed_line_count=0,
        stdout_sentinel_count=0,
    )

    mapping = _map_babeldoc_drop_report_to_findings(drop_report, chunk)

    assert [f.page_number for f in mapping.findings] == [55]
    assert mapping.findings[0].check_type == BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK
    assert mapping.suppressed_overlap_count == 2
    assert mapping.unfit_drop_count == 1
    assert mapping.is_incomplete is False
    assert mapping.surviving_range == (41, 80)


# --- Gate test #9 — test_sentinel_mismatch_one_way --------------------------


def test_sentinel_mismatch_only_fires_when_sentinel_exceeds_structured() -> None:
    chunk = _make_chunk()

    # sentinel (0) <= structured (len(dropped)=1) -> KHONG finding mismatch
    # (EvictQueue tu vut bot log khi day la binh thuong, KHONG phai loi).
    report_under = BabeldocDropReport(
        available=True,
        dropped=[_dropped(5)],
        observed_pages=frozenset(range(1, 41)),
        page_dropped_counts={p: (1 if p == 5 else 0) for p in range(1, 41)},
        header_count=1,
        malformed_line_count=0,
        stdout_sentinel_count=0,
    )
    mapping_under = _map_babeldoc_drop_report_to_findings(report_under, chunk)
    assert BABELDOC_DROP_REPORT_MISMATCH_CHECK not in [f.check_type for f in mapping_under.findings]

    # sentinel (1) > structured (0) -> CO dung 1 finding mismatch.
    report_over = BabeldocDropReport(
        available=True,
        dropped=[],
        observed_pages=frozenset(range(1, 41)),
        page_dropped_counts=dict.fromkeys(range(1, 41), 0),
        header_count=1,
        malformed_line_count=0,
        stdout_sentinel_count=1,
    )
    mapping_over = _map_babeldoc_drop_report_to_findings(report_over, chunk)
    mismatch_findings = [
        f for f in mapping_over.findings if f.check_type == BABELDOC_DROP_REPORT_MISMATCH_CHECK
    ]
    assert len(mismatch_findings) == 1
    assert mismatch_findings[0].detail == {"sentinel": 1, "structured": 0}
    assert mismatch_findings[0].severity == _SEVERITY_BY_CHECK[BABELDOC_DROP_REPORT_MISMATCH_CHECK]


# --- Gate test #10 — test_severity_from_registry ----------------------------


def test_severity_from_registry_is_not_hardcoded(monkeypatch) -> None:
    """F6 — `_map_babeldoc_drop_report_to_findings` PHAI tra `_SEVERITY_BY_CHECK`,
    khong tu dien chuoi severity. Monkeypatch dict (cung 1 object duoc
    `src.services.layout_qa` va `src.core.job_orchestrator` cung tham chieu)
    va kiem tra severity cua finding thay doi theo."""
    chunk = _make_chunk()
    drop_report = BabeldocDropReport(
        available=True,
        dropped=[_dropped(5)],
        observed_pages=frozenset(range(1, 41)),
        page_dropped_counts={p: (1 if p == 5 else 0) for p in range(1, 41)},
        header_count=1,
        malformed_line_count=0,
        stdout_sentinel_count=0,
    )

    monkeypatch.setitem(_SEVERITY_BY_CHECK, BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK, "minor")

    mapping = _map_babeldoc_drop_report_to_findings(drop_report, chunk)

    assert mapping.findings[0].check_type == BABELDOC_PARAGRAPH_DROP_UNFIT_CHECK
    assert mapping.findings[0].severity == "minor"


# --- Gate test #12 — test_checksum_mismatch_triggers_incomplete ------------


def test_checksum_mismatch_triggers_incomplete_even_when_pages_complete() -> None:
    """X5 — checksum PHAI luon co cho di, KE CA khi du trang (khong chi khi
    thieu trang). `page.dropped_count=2` nhung chi 1 dong `drop` thuc te cho
    trang do, VA `observed_pages == expected_pages`."""
    chunk = _make_chunk()
    expected = set(range(1, 41))
    drop_report = BabeldocDropReport(
        available=True,
        dropped=[_dropped(10)],
        observed_pages=frozenset(expected),
        page_dropped_counts={p: (2 if p == 10 else 0) for p in expected},
        header_count=1,
        malformed_line_count=0,
        stdout_sentinel_count=0,
    )

    mapping = _map_babeldoc_drop_report_to_findings(drop_report, chunk)

    incomplete_findings = [
        f for f in mapping.findings if f.check_type == BABELDOC_DROP_REPORT_INCOMPLETE_CHECK
    ]
    assert len(incomplete_findings) == 1
    incomplete = incomplete_findings[0]
    assert incomplete.detail["checksum_mismatch_pages"] == [10]
    assert incomplete.detail["missing"] == []
    assert incomplete.detail["unexpected"] == []
    assert mapping.is_incomplete is True
    assert mapping.checksum_mismatch_pages == [10]
