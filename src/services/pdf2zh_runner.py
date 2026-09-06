import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.concurrency_controller import RATE_LIMIT_LINE_RE
from src.services.pdf2zh_service_map import Pdf2zhService


async def _drain(stream: asyncio.StreamReader, sink: bytearray) -> None:
    """Read continuously into `sink` until EOF. Runs as a background task, never raises."""
    while True:
        block = await stream.read(65536)
        if not block:
            return
        sink.extend(block)


class Pdf2zhError(RuntimeError):
    """Raised when the pdf2zh subprocess exits with a non-zero code.

    Carries the same drained signal as `Pdf2zhTimeoutError`: Architecture.md
    6.12.4 classifies a non-zero exit as `rate_limited` when
    `rate_limit_hits >= 1` and only as `error` (HOLD) when it is 0, so this
    branch must not discard the count either. Defaults exist for the same
    reason as on `Pdf2zhResult` — see Architecture.md 6.12.3.1.
    """

    def __init__(
        self,
        message: str,
        *,
        stdout: str = "",
        stderr: str = "",
        rate_limit_hits: int = 0,
    ) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.rate_limit_hits = rate_limit_hits


class Pdf2zhTimeoutError(RuntimeError):
    """Raised when the pdf2zh subprocess exceeds `timeout_seconds` (Architecture.md 6.6.8).

    Carries the stdout/stderr drained before the kill plus the rate-limit hit
    count so the caller can tell "timed out because of rate limiting"
    (`rate_limit_hits >= 1`) apart from "timed out because it's just slow"
    (`rate_limit_hits == 0`) — see Architecture.md 6.12.3. Without this, a
    timeout used to discard all diagnostic signal.
    """

    def __init__(self, message: str, *, stdout: str, stderr: str, rate_limit_hits: int) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.rate_limit_hits = rate_limit_hits


@dataclass
class Pdf2zhResult:
    success: bool
    mono_path: Path
    dual_path: Path | None
    stderr: str
    duration_seconds: float
    # New fields (Architecture.md 6.12.3): default to "" / 0 so existing
    # keyword-only construction sites that predate this change (and don't
    # care about rate-limit diagnostics) keep working unchanged.
    stdout: str = ""
    rate_limit_hits: int = 0


class Pdf2zhRunner:
    """Wraps the `pdf2zh` CLI (PDFMathTranslate) via asyncio subprocess.

    See Architecture.md section 3.1 step [3b] and section 6.6 (6.6.1 F5/F8/F9,
    6.6.8) for the `--pages`/`--prompt`/`--output`/`--ignore-cache` contract
    this wrapper builds on.
    """

    def __init__(self, executable: str = "pdf2zh") -> None:
        self._executable = executable

    async def translate_pages(
        self,
        input_path: Path,
        output_dir: Path,
        page_range: str,
        service: Pdf2zhService,
        prompt_file: Path | None = None,
        lang_in: str = "en",
        lang_out: str = "vi",
        ignore_cache: bool = False,
        timeout_seconds: int = 3600,
        thread: int = 4,
        split_short_lines: bool = False,
        short_line_split_factor: float | None = None,
    ) -> Pdf2zhResult:
        """Run pdf2zh for one chunk's page range and return the rendered PDFs.

        `split_short_lines`/`short_line_split_factor` accepted-but-unused here:
        they are a babeldoc-only CLI concept (Architecture.md "Root Cause
        Analysis: Line-break/List Regression" F2, `BabeldocRunner.translate_pages()`).
        Kept on this signature purely so `JobOrchestrator._translator_runner`
        (Architecture.md 6.14.7 "DIEM CHON ENGINE DUY NHAT") can call either
        engine with the exact same kwargs and never branch on `if engine ==
        ...` at the call site — pdf2zh has no equivalent flag.

        `output_dir` MUST be unique per chunk (Architecture.md 6.6.1 F9): pdf2zh
        names its output after the input file's stem (`{stem}-mono.pdf` /
        `{stem}-dual.pdf`), so two chunks sharing a directory would overwrite
        each other. `prompt_file` is silently dropped when
        `service.supports_custom_prompt` is False (only reachable today via a
        caller bypassing `Pdf2zhServiceMapper`, since the mapper already
        rejects DeepL before construction — kept as defense in depth).
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        args = [
            str(input_path),
            "-li",
            lang_in,
            "-lo",
            lang_out,
            "-s",
            service.service_arg,
            "--pages",
            page_range,
            "--output",
            str(output_dir),
            "--thread",
            str(thread),
        ]
        if prompt_file is not None and service.supports_custom_prompt:
            args.extend(["--prompt", str(prompt_file)])
        if ignore_cache:
            args.append("--ignore-cache")

        env = {**os.environ, **service.envs}

        start = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            self._executable,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_buf, stderr_buf = bytearray(), bytearray()
        drains = [
            asyncio.create_task(_drain(process.stdout, stdout_buf)),
            asyncio.create_task(_drain(process.stderr, stderr_buf)),
        ]
        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
        except TimeoutError:
            timed_out = True
            process.kill()
            await process.wait()
        finally:
            # Mop up whatever pipe buffer is left after the process dies. 5s is
            # enough: the write end is already closed, `_drain` only has to
            # read the remaining OS buffer.
            await asyncio.wait(drains, timeout=5.0)
            for d in drains:
                d.cancel()

        duration = time.monotonic() - start
        stdout = bytes(stdout_buf).decode("utf-8", errors="replace")
        stderr = bytes(stderr_buf).decode("utf-8", errors="replace")
        rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))

        if timed_out:
            raise Pdf2zhTimeoutError(
                f"pdf2zh vuot qua timeout {timeout_seconds}s cho {input_path} (trang {page_range})",
                stdout=stdout,
                stderr=stderr,
                rate_limit_hits=rate_limit_hits,
            )

        if process.returncode != 0:
            raise Pdf2zhError(
                f"pdf2zh exited with code {process.returncode} for {input_path}: {stderr.strip()}",
                stdout=stdout,
                stderr=stderr,
                rate_limit_hits=rate_limit_hits,
            )

        stem = input_path.stem
        mono_path = output_dir / f"{stem}-mono.pdf"
        dual_path = output_dir / f"{stem}-dual.pdf"

        return Pdf2zhResult(
            success=True,
            mono_path=mono_path,
            dual_path=dual_path if dual_path.exists() else None,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            rate_limit_hits=rate_limit_hits,
        )
