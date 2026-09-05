"""Tests for MinerURunner against the REAL MinerU HTTP contract (Architecture.md
6.9, verified against `mineru/cli/fast_api.py` + `api_request.py` source, S1/S2).

Fixtures below mirror the exact response shape from `build_result_dict()`
(6.9.2) — `results` keyed by real file name, `images` as a dict of base64
data URIs, `middle_json` as a JSON *string* — never a hand-rolled dict built
from memory of what MinerU "probably" returns. That mismatch (mock
self-consistent with a wrong assumption, not with reality) is exactly what
let the old `/ocr` contract slip past Reviewer and QA (CLAUDE.md Protocol 5).
"""

import base64
import json
from pathlib import Path
from typing import Any, Self
from unittest.mock import AsyncMock

import httpx
import pytest

from src.services.mineru_runner import (
    MinerUError,
    MinerURunner,
    MinerUTimeoutError,
    MinerUUnavailableError,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


class _ScriptedAsyncClient:
    """Replays a queue of (method, path) -> response mappings, matched by
    substring on the requested URL. `get`/`post` calls are logged for
    assertions on request shape.
    """

    def __init__(self, script: list[tuple[str, _FakeResponse]]) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def _next(self, method: str, url: str, **kwargs) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._script:
            raise AssertionError(f"no more scripted responses, got unexpected {method} {url}")
        expected_method, response = self._script.pop(0)
        assert expected_method == method, f"expected {expected_method}, got {method} for {url}"
        return response

    async def post(self, url: str, **kwargs) -> _FakeResponse:
        return await self._next("POST", url, **kwargs)

    async def get(self, url: str, **kwargs) -> _FakeResponse:
        return await self._next("GET", url, **kwargs)


def _mineru_result_payload(
    file_name: str,
    *,
    md_content: str = "# Recipe\n\nFlour: 480ml",
    images: dict[str, str] | None = None,
    middle_json: str | dict | None = "unset",
) -> dict:
    if middle_json == "unset":
        middle_json = json.dumps(_middle_json_with_scores([0.95, 0.88, 0.0]))
    return {
        "task_id": "task-123",
        "status": "completed",
        "results": {
            file_name: {
                "md_content": md_content,
                "middle_json": middle_json,
                "model_output": None,
                "content_list": None,
                "images": images if images is not None else {},
            }
        },
    }


def _middle_json_with_scores(scores: list[float]) -> dict:
    return {
        "pdf_info": [
            {
                "preproc_blocks": [
                    {
                        "lines": [
                            {
                                "spans": [{"score": s, "content": "x"} for s in scores],
                            }
                        ]
                    }
                ],
                "discarded_blocks": [],
            }
        ]
    }


def _data_uri(raw: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")
    return pdf_path


@pytest.mark.asyncio
async def test_parse_document_success(tmp_path: Path, sample_pdf: Path, mocker) -> None:
    submit_response = _FakeResponse(202, {"task_id": "task-123", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(
        200,
        _mineru_result_payload(
            sample_pdf.name,
            images={"img_01.png": _data_uri(b"hello")},
        ),
    )
    client = _ScriptedAsyncClient(
        [
            ("POST", submit_response),
            ("GET", status_response),
            ("GET", result_response),
        ]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")
    output_dir = tmp_path / "output"

    result = await runner.parse_document(sample_pdf, output_dir)

    assert result.task_id == "task-123"
    assert result.markdown_path.read_text(encoding="utf-8") == "# Recipe\n\nFlour: 480ml"
    assert (result.images_dir / "img_01.png").read_bytes() == b"hello"
    assert result.middle_json_path is not None
    assert result.middle_json_path.exists()

    # scores [0.95, 0.88, 0.0] -> weighted by span COUNT (3), not chars.
    assert result.quality.ocr_span_count == 3
    assert result.quality.dropped_span_count == 1
    assert result.quality.confidence == pytest.approx((0.95 + 0.88 + 0.0) / 3)
    assert result.quality.source == "middle_json_span_scores"


@pytest.mark.asyncio
async def test_submit_uses_files_field_and_pipeline_backend(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    """Regression guard for the old bug: field must be `files` (plural), not
    `file`, and `backend=pipeline` must always be sent — it's the only
    backend whose middle_json carries span scores (6.9.4).
    """
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, _mineru_result_payload(sample_pdf.name))
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")
    await runner.parse_document(sample_pdf, tmp_path / "output")

    submit_call = client.calls[0]
    assert "files" in submit_call["files"]
    assert submit_call["data"]["backend"] == "pipeline"
    assert submit_call["data"]["lang_list"] == "en"
    assert submit_call["data"]["return_middle_json"] == "true"
    assert submit_call["data"]["return_images"] == "true"


@pytest.mark.asyncio
async def test_confidence_none_when_no_span_has_score(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    """`middle_json` present but no span went through OCR (e.g. text-layer-only
    page) -> confidence None, NOT an error (Architecture.md 6.9.5).
    """
    payload = _mineru_result_payload(
        sample_pdf.name,
        middle_json=json.dumps({"pdf_info": [{"preproc_blocks": [], "discarded_blocks": []}]}),
    )
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, payload)
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")
    result = await runner.parse_document(sample_pdf, tmp_path / "output")

    assert result.quality.confidence is None
    assert result.quality.ocr_span_count == 0
    assert result.quality.source == "unavailable"


@pytest.mark.asyncio
async def test_confidence_none_when_middle_json_absent(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    """Runner must NOT raise when middle_json is missing entirely — only
    md_content is truly required (6.9.6 step 6/8).
    """
    payload = _mineru_result_payload(sample_pdf.name, middle_json=None)
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, payload)
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")
    result = await runner.parse_document(sample_pdf, tmp_path / "output")

    assert result.quality.confidence is None
    assert result.middle_json_path is None


@pytest.mark.asyncio
async def test_task_status_failed_raises_mineru_error(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "failed", "error": "OCR model crashed"})
    client = _ScriptedAsyncClient([("POST", submit_response), ("GET", status_response)])
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUError, match="OCR model crashed"):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_task_lost_404_raises_mineru_error(tmp_path: Path, sample_pdf: Path, mocker) -> None:
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(404, text="not found")
    client = _ScriptedAsyncClient([("POST", submit_response), ("GET", status_response)])
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUError, match="lost"):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_task_timeout_raises_mineru_timeout_error(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    # Always "processing" -> never completes within the timeout budget.
    status_response = _FakeResponse(200, {"status": "processing", "queued_ahead": 0})
    client = _ScriptedAsyncClient([("POST", submit_response)] + [("GET", status_response)] * 50)
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(
        base_url="http://localhost:8010",
        task_timeout_seconds=5.0,
        poll_initial_seconds=2.0,
        poll_max_seconds=2.0,
    )

    with pytest.raises(MinerUTimeoutError):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_submit_non_202_raises_mineru_error(tmp_path: Path, sample_pdf: Path, mocker) -> None:
    submit_response = _FakeResponse(500, text="internal error")
    client = _ScriptedAsyncClient([("POST", submit_response)])
    mocker.patch("httpx.AsyncClient", return_value=client)

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUError, match="500"):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_connection_error_raises_mineru_error(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    class _RaisingClient:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc_info) -> None:
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    mocker.patch("httpx.AsyncClient", return_value=_RaisingClient())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUError, match="connection refused"):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_result_entry_selected_by_real_file_name(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    """`results` is keyed by the real file name, not a fixed key — must not
    be hardcoded (6.9.6 step 5).
    """
    payload = _mineru_result_payload("scan.pdf")
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, payload)
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")
    result = await runner.parse_document(sample_pdf, tmp_path / "output")

    assert result.markdown_path.exists()


@pytest.mark.asyncio
async def test_result_entry_ambiguous_key_mismatch_raises(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    payload = {
        "task_id": "task-1",
        "status": "completed",
        "results": {
            "other_name.pdf": {"md_content": "x", "middle_json": None, "images": {}},
            "yet_another.pdf": {"md_content": "y", "middle_json": None, "images": {}},
        },
    }
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, payload)
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUError, match="ambiguous"):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_missing_md_content_raises(tmp_path: Path, sample_pdf: Path, mocker) -> None:
    payload = _mineru_result_payload(sample_pdf.name, md_content="")
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, payload)
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUError, match="md_content"):
        await runner.parse_document(sample_pdf, tmp_path / "output")


@pytest.mark.asyncio
async def test_malformed_image_entry_skipped_not_fatal(
    tmp_path: Path, sample_pdf: Path, mocker
) -> None:
    payload = _mineru_result_payload(
        sample_pdf.name,
        images={
            "good.png": _data_uri(b"ok"),
            "bad.png": "not-a-data-uri",
        },
    )
    submit_response = _FakeResponse(202, {"task_id": "task-1", "status": "pending"})
    status_response = _FakeResponse(200, {"status": "completed"})
    result_response = _FakeResponse(200, payload)
    client = _ScriptedAsyncClient(
        [("POST", submit_response), ("GET", status_response), ("GET", result_response)]
    )
    mocker.patch("httpx.AsyncClient", return_value=client)
    mocker.patch("asyncio.sleep", new=AsyncMock())

    runner = MinerURunner(base_url="http://localhost:8010")
    result = await runner.parse_document(sample_pdf, tmp_path / "output")

    assert (result.images_dir / "good.png").read_bytes() == b"ok"
    assert not (result.images_dir / "bad.png").exists()


@pytest.mark.asyncio
async def test_health_ok(mocker) -> None:
    response = _FakeResponse(200, {"status": "healthy", "version": "2.x"})

    class _HealthClient:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc_info) -> None:
            return None

        async def get(self, url: str, **kwargs) -> _FakeResponse:
            return response

    mocker.patch("httpx.AsyncClient", return_value=_HealthClient())

    runner = MinerURunner(base_url="http://localhost:8010")
    result = await runner.health()

    assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_503_raises_unavailable(mocker) -> None:
    response = _FakeResponse(503, {"status": "unhealthy", "error": "models not loaded"})

    class _HealthClient:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc_info) -> None:
            return None

        async def get(self, url: str, **kwargs) -> _FakeResponse:
            return response

    mocker.patch("httpx.AsyncClient", return_value=_HealthClient())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUUnavailableError):
        await runner.health()


@pytest.mark.asyncio
async def test_health_connection_error_raises_unavailable(mocker) -> None:
    class _RaisingClient:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc_info) -> None:
            return None

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    mocker.patch("httpx.AsyncClient", return_value=_RaisingClient())

    runner = MinerURunner(base_url="http://localhost:8010")

    with pytest.raises(MinerUUnavailableError):
        await runner.health()
