"""MinerU OCR HTTP client — async `/tasks` submit+poll flow.

Contract verified directly against MinerU source (Architecture.md section 6.9,
Protocol 5 R5-01). The previous version of this module (`/ocr`, sync,
`confidence_score` top-level field, hex-encoded images) matched NONE of the
real MinerU API and would have failed on first real call — see
CLAUDE.md Protocol 5 and Architecture.md 6.9 for the incident writeup.
"""

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MinerUError(RuntimeError):
    """Raised when the MinerU HTTP OCR service returns an error or unusable response."""


class MinerUTimeoutError(MinerUError):
    """Raised when a submitted task does not reach `completed`/`failed` within the budget."""


class MinerUUnavailableError(MinerUError):
    """Raised when `/health` reports 503, or the service cannot be reached at all."""


class MinerUCancelledError(MinerUError):
    """Raised by `_poll_until_done()` when the caller's `should_cancel`
    callback reports the user asked to stop mid-poll (US-15 §6.15.3 S15-13).
    MinerU has no verified server-side cancel endpoint (Architecture.md 6.9.2
    lists none) — `⚠️ ASSUMED` the submitted task keeps running remotely;
    accepted because it's local compute at $0 cost and the caller only stops
    WAITING on it, it doesn't try to kill it.
    """


@dataclass(frozen=True)
class OcrQuality:
    """Post-OCR recognition confidence, computed by BB-Translation from
    `middle_json` span scores — MinerU itself exposes no confidence field
    (Architecture.md 6.9.5). `confidence is None` is a valid, non-error state:
    it means no span in the document actually went through OCR.
    """

    confidence: float | None
    ocr_span_count: int
    dropped_span_count: int
    source: str  # "middle_json_span_scores" | "unavailable"


@dataclass(frozen=True)
class MinerUResult:
    markdown_path: Path
    images_dir: Path
    quality: OcrQuality
    task_id: str
    middle_json_path: Path | None


class MinerURunner:
    """Wraps the MinerU OCR HTTP service's async task flow.

    `/file_parse` (sync) is deliberately not used: a real 200-500 page scan
    can take 15-25 minutes, and holding one HTTP connection open that long is
    fragile against idle timeouts (httpx, reverse proxies, Docker's userland
    proxy) that would kill the job after MinerU already spent the compute
    (Architecture.md 6.9.3).
    """

    def __init__(
        self,
        base_url: str,
        *,
        task_timeout_seconds: float = 3600.0,
        request_timeout_seconds: float = 120.0,
        poll_initial_seconds: float = 2.0,
        poll_max_seconds: float = 15.0,
        backend: str = "pipeline",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._task_timeout_seconds = task_timeout_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._poll_initial_seconds = poll_initial_seconds
        self._poll_max_seconds = poll_max_seconds
        self._backend = backend

    async def health(self) -> dict[str, Any]:
        """GET /health. Used for startup checks and the Protocol 5 R5-03 live smoke test."""
        try:
            async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                response = await client.get(f"{self._base_url}/health")
        except httpx.HTTPError as exc:
            raise MinerUUnavailableError(f"MinerU unreachable at {self._base_url}: {exc}") from exc

        if response.status_code == 503:
            raise MinerUUnavailableError(f"MinerU unhealthy: {response.text}")
        if response.status_code != 200:
            raise MinerUError(f"MinerU /health returned {response.status_code}: {response.text}")
        return response.json()

    async def parse_document(
        self,
        file_path: Path,
        output_dir: Path,
        *,
        parse_method: str = "ocr",
        lang: str = "en",
        start_page_id: int | None = None,
        end_page_id: int | None = None,
        task_timeout_seconds: float | None = None,
        should_cancel: Callable[[], Awaitable[bool]] | None = None,
    ) -> MinerUResult:
        """`task_timeout_seconds` overrides `self._task_timeout_seconds` for
        THIS call only (US-15 S15-14: `parse_only` scales the budget with
        page count instead of the fixed 3600s constant `_build_ocr_bridge()`
        uses). `should_cancel`, if given, is polled once per poll iteration
        (S15-13) — returning `True` raises `MinerUCancelledError` instead of
        continuing to wait.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        task_id = await self._submit_task(
            file_path,
            parse_method=parse_method,
            lang=lang,
            start_page_id=start_page_id,
            end_page_id=end_page_id,
        )
        await self._poll_until_done(task_id, task_timeout_seconds, should_cancel)
        payload = await self._fetch_result(task_id)

        entry = self._select_result_entry(payload.get("results") or {}, file_path.name)

        markdown_path = self._write_markdown(entry, output_dir)
        images_dir = self._write_images(entry, output_dir)
        quality, middle_json_path = self._write_middle_json(entry, output_dir)

        return MinerUResult(
            markdown_path=markdown_path,
            images_dir=images_dir,
            quality=quality,
            task_id=task_id,
            middle_json_path=middle_json_path,
        )

    async def _submit_task(
        self,
        file_path: Path,
        *,
        parse_method: str,
        lang: str,
        start_page_id: int | None,
        end_page_id: int | None,
    ) -> str:
        data: dict[str, str] = {
            "backend": self._backend,
            "parse_method": parse_method,
            "lang_list": lang,
            "formula_enable": "true",
            "table_enable": "true",
            "return_md": "true",
            "return_images": "true",
            "return_middle_json": "true",
            "return_content_list": "false",
            "return_model_output": "false",
            "response_format_zip": "false",
        }
        if start_page_id is not None:
            data["start_page_id"] = str(start_page_id)
        if end_page_id is not None:
            data["end_page_id"] = str(end_page_id)

        try:
            async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                with file_path.open("rb") as fh:
                    files = {"files": (file_path.name, fh, "application/pdf")}
                    response = await client.post(f"{self._base_url}/tasks", data=data, files=files)
        except httpx.HTTPError as exc:
            raise MinerUError(f"MinerU task submit failed for {file_path}: {exc}") from exc

        if response.status_code != 202:
            raise MinerUError(
                f"MinerU /tasks returned {response.status_code} for {file_path}: {response.text}"
            )

        payload = response.json()
        task_id = payload.get("task_id")
        if not task_id:
            raise MinerUError(f"MinerU /tasks response missing task_id: {payload}")
        return task_id

    async def _poll_until_done(
        self,
        task_id: str,
        task_timeout_seconds: float | None = None,
        should_cancel: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        interval = self._poll_initial_seconds
        elapsed = 0.0
        timeout = (
            task_timeout_seconds if task_timeout_seconds is not None else self._task_timeout_seconds
        )

        async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
            while True:
                if should_cancel is not None and await should_cancel():
                    raise MinerUCancelledError(
                        f"MinerU task {task_id} bi huy theo yeu cau nguoi dung (task co the van "
                        "dang chay o server MinerU — chua verify co API huy task hay khong)"
                    )

                try:
                    response = await client.get(f"{self._base_url}/tasks/{task_id}")
                except httpx.HTTPError as exc:
                    raise MinerUError(f"MinerU task status request failed: {exc}") from exc

                if response.status_code == 404:
                    raise MinerUError(
                        f"MinerU task {task_id} lost (404) — server may have restarted"
                    )
                if response.status_code != 200:
                    raise MinerUError(
                        f"MinerU /tasks/{task_id} returned {response.status_code}: {response.text}"
                    )

                payload = response.json()
                status = payload.get("status")

                if status == "completed":
                    return
                if status == "failed":
                    raise MinerUError(f"MinerU task {task_id} failed: {payload.get('error')}")

                if elapsed >= timeout:
                    raise MinerUTimeoutError(
                        f"MinerU task {task_id} did not complete within "
                        f"{timeout}s (last status: {status})"
                    )

                queued_ahead = payload.get("queued_ahead")
                logger.debug(
                    "MinerU task %s status=%s queued_ahead=%s elapsed=%.0fs",
                    task_id,
                    status,
                    queued_ahead,
                    elapsed,
                )

                await asyncio.sleep(interval)
                elapsed += interval
                interval = min(interval * 1.5, self._poll_max_seconds)

    async def _fetch_result(self, task_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
            try:
                response = await client.get(f"{self._base_url}/tasks/{task_id}/result")
            except httpx.HTTPError as exc:
                raise MinerUError(f"MinerU result request failed: {exc}") from exc

        if response.status_code == 409:
            raise MinerUError(f"MinerU task {task_id} failed: {response.text}")
        if response.status_code == 202:
            # Rare race between the polling "completed" observation and the
            # result endpoint catching up — one more poll pass covers it.
            await self._poll_until_done(task_id)
            return await self._fetch_result(task_id)
        if response.status_code != 200:
            raise MinerUError(
                f"MinerU /tasks/{task_id}/result returned {response.status_code}: {response.text}"
            )
        return response.json()

    @staticmethod
    def _select_result_entry(results: dict[str, Any], file_name: str) -> dict[str, Any]:
        if file_name in results:
            return results[file_name]
        if len(results) == 1:
            return next(iter(results.values()))
        raise MinerUError(
            f"MinerU result has no entry for '{file_name}' and is ambiguous "
            f"(available keys: {sorted(results.keys())})"
        )

    @staticmethod
    def _write_markdown(entry: dict[str, Any], output_dir: Path) -> Path:
        markdown_content = entry.get("md_content")
        if not markdown_content:
            raise MinerUError("MinerU result missing md_content")
        markdown_path = output_dir / "document.md"
        markdown_path.write_text(markdown_content, encoding="utf-8")
        return markdown_path

    @staticmethod
    def _write_images(entry: dict[str, Any], output_dir: Path) -> Path:
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        for name, data_uri in (entry.get("images") or {}).items():
            if (
                not isinstance(data_uri, str)
                or "," not in data_uri
                or not data_uri.startswith("data:")
            ):
                logger.warning("MinerU image '%s' has unexpected format, skipping", name)
                continue
            _, _, b64_data = data_uri.partition(",")
            try:
                image_bytes = base64.b64decode(b64_data)
            except (ValueError, base64.binascii.Error):
                logger.warning("MinerU image '%s' failed base64 decode, skipping", name)
                continue
            safe_name = Path(name).name
            (images_dir / safe_name).write_bytes(image_bytes)
        return images_dir

    @classmethod
    def _write_middle_json(
        cls, entry: dict[str, Any], output_dir: Path
    ) -> tuple[OcrQuality, Path | None]:
        raw_middle_json = entry.get("middle_json")
        if not raw_middle_json:
            return OcrQuality(None, 0, 0, source="unavailable"), None

        try:
            middle = (
                json.loads(raw_middle_json) if isinstance(raw_middle_json, str) else raw_middle_json
            )
        except (json.JSONDecodeError, TypeError):
            logger.warning("MinerU middle_json failed to parse, confidence unavailable")
            return OcrQuality(None, 0, 0, source="unavailable"), None

        middle_json_path = output_dir / "middle.json"
        middle_json_path.write_text(json.dumps(middle), encoding="utf-8")

        quality = cls._compute_quality(middle)
        return quality, middle_json_path

    @staticmethod
    def _compute_quality(middle: dict[str, Any]) -> OcrQuality:
        """Weighted average of span-level OCR recognition scores.

        Weighted by SPAN COUNT, not character count: spans MinerU discards
        (score == 0.0) end up with zero characters, so a character-weighted
        average would hide exactly the signal this metric exists to surface
        (Architecture.md 6.9.5).
        """
        scores: list[float] = []

        def _walk_block(block: dict[str, Any]) -> None:
            for line in block.get("lines", []) or []:
                for span in line.get("spans", []) or []:
                    if "score" in span:
                        scores.append(span["score"])
            # Some block types (e.g. tables) nest sub-blocks rather than lines directly.
            for nested in block.get("blocks", []) or []:
                _walk_block(nested)

        for page in middle.get("pdf_info", []) or []:
            for block_group_key in ("preproc_blocks", "discarded_blocks"):
                for block in page.get(block_group_key, []) or []:
                    _walk_block(block)

        if not scores:
            return OcrQuality(None, 0, 0, source="unavailable")

        ocr_span_count = len(scores)
        dropped_span_count = sum(1 for s in scores if s == 0.0)
        confidence = sum(scores) / ocr_span_count
        return OcrQuality(
            confidence=confidence,
            ocr_span_count=ocr_span_count,
            dropped_span_count=dropped_span_count,
            source="middle_json_span_scores",
        )
