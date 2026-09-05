import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.concurrency_controller import RATE_LIMIT_LINE_RE
from src.services.pdf2zh_runner import _drain
from src.services.pdf2zh_service_map import Pdf2zhService, UnsupportedForPdfPipelineError

#: Endpoint OpenAI-compat chinh thuc cua Gemini — VERIFIED (Architecture.md
#: 6.14.1 B14, WebFetch https://ai.google.dev/gemini-api/docs/openai,
#: 2026-09-05). Shape client babeldoc phat ra (B2/B5/B6, live-verified o day)
#: khop dung shape nay.
_GEMINI_OPENAI_COMPAT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

#: Fallback khi khong co `Settings` truyen vao (vd goi truc tiep trong test).
#: Khong phai kien thuc moi: gia tri nay TRUNG voi mac dinh cua
#: `Settings.deepseek_base_url` (src/core/config.py) da co san va da qua
#: review. `pdf2zh` khong can bien `DEEPSEEK_BASE_URL` (no tu biet URL noi bo),
#: nen `service.envs` khong mang field nay. `deepseek_base_url` NAM TRONG
#: `SETTINGS_DB_OVERRIDABLE_FIELDS` — neu user doi qua UI, gia tri hardcode se
#: LECH khoi gia tri that dang dung. Vi vay `BabeldocRunner` phai nhan gia tri
#: nay tu `Settings` (xem __init__), khong doc lai hang so o day tru khi
#: khong co Settings nao duoc truyen (review-report.md, non-blocking suggestion).
_DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _resolve_openai_compat(
    service: Pdf2zhService, *, deepseek_base_url: str = _DEFAULT_DEEPSEEK_BASE_URL
) -> tuple[str, str, str]:
    """Dich `service.envs` (san pham cua `Pdf2zhServiceMapper`, khong doi) sang
    bo 3 (base_url, api_key, model) can cho `--openai-*` cua babeldoc.

    `openai` va `claude` (qua lop compat `openailiked`) da mang du ca 3 gia tri
    thang trong envs. `gemini`/`deepseek`/`ollama` chi mang api_key + model
    (pdf2zh tu biet base_url noi bo, khong can bien moi truong rieng) nen can
    them 1 buoc tra cuu nho — xem ghi chu tren hang so. Neu khong nhan dien
    duoc provider nao, raise TRUOC KHI spawn subprocess (Architecture.md
    6.14.3, fail-fast giong DeepL o 6.6.1 F7).
    """
    envs = service.envs
    if {"OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"} <= envs.keys():
        return envs["OPENAI_BASE_URL"], envs["OPENAI_API_KEY"], envs["OPENAI_MODEL"]

    if {"OPENAILIKED_BASE_URL", "OPENAILIKED_API_KEY", "OPENAILIKED_MODEL"} <= envs.keys():
        return envs["OPENAILIKED_BASE_URL"], envs["OPENAILIKED_API_KEY"], envs["OPENAILIKED_MODEL"]

    if {"GEMINI_API_KEY", "GEMINI_MODEL"} <= envs.keys():
        return _GEMINI_OPENAI_COMPAT_BASE_URL, envs["GEMINI_API_KEY"], envs["GEMINI_MODEL"]

    if {"DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"} <= envs.keys():
        return deepseek_base_url, envs["DEEPSEEK_API_KEY"], envs["DEEPSEEK_MODEL"]

    if {"OLLAMA_HOST", "OLLAMA_MODEL"} <= envs.keys():
        base = envs["OLLAMA_HOST"].rstrip("/")
        # Ollama khong kiem tra api key that — mot chuoi bat ky la du de client
        # openai gui header Authorization ma khong bi tu choi o phia client.
        return f"{base}/v1", "ollama", envs["OLLAMA_MODEL"]

    raise UnsupportedForPdfPipelineError(
        "Khong the dich service.envs sang bo 3 flag --openai-* can cho babeldoc: "
        f"khong nhan dien duoc provider tu cac key hien co {sorted(envs.keys())}. "
        "Xem Architecture.md 6.14.3."
    )


class BabeldocError(RuntimeError):
    """Raised when the babeldoc subprocess exits with a non-zero code.

    Cung shape voi `Pdf2zhError` — xem docstring cua no cho ly do giu
    `rate_limit_hits` ngay ca tren nhanh loi (Architecture.md 6.12.4).
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


class BabeldocTimeoutError(RuntimeError):
    """Raised when the babeldoc subprocess exceeds `timeout_seconds`.

    Cung shape voi `Pdf2zhTimeoutError` — xem docstring cua no.
    """

    def __init__(self, message: str, *, stdout: str, stderr: str, rate_limit_hits: int) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.rate_limit_hits = rate_limit_hits


@dataclass
class BabeldocResult:
    success: bool
    mono_path: Path
    dual_path: Path | None
    stderr: str
    duration_seconds: float
    stdout: str = ""
    rate_limit_hits: int = 0


class BabeldocRunner:
    """Wraps the `babeldoc` CLI via asyncio subprocess — engine dich PDF thu
    hai, chay song song `Pdf2zhRunner` (Architecture.md section 6.14).

    Cung shape (tham so, kieu tra ve, 2 kieu exception) voi `Pdf2zhRunner` de
    `JobOrchestrator` doi engine ma khong doi logic goi (6.14.7). Tai su dung
    nguyen ky thuat subprocess da chung minh cua `Pdf2zhRunner` (6.14.3):
    `asyncio.create_subprocess_exec` + 2 task `_drain` + `wait_for` + kill khi
    timeout + mop-up 5s.
    """

    def __init__(
        self,
        executable: str = "babeldoc",
        deepseek_base_url: str = _DEFAULT_DEEPSEEK_BASE_URL,
    ) -> None:
        self._executable = executable
        self._deepseek_base_url = deepseek_base_url

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
    ) -> BabeldocResult:
        """Run babeldoc for one chunk's page range and return the rendered PDFs.

        Cac flag sau la BAT BUOC, hardcode, khong tuy chon (bang doi chieu
        Architecture.md 6.14.2, moi flag co ly do rieng da verify song B6-B9):
        `--watermark-output-mode no_watermark`, `--only-include-translated-page`
        (thieu flag nay: mono output chua CA tai lieu thay vi rieng chunk, B8),
        `--no-auto-extract-glossary` (chan 4 request LLM phu ngoai chi phi da
        uoc tinh, B9), `--skip-scanned-detection` (tranh ScannedPDFError tren
        cau noi searchable PDF cua nhanh pdf_scan), `--split-short-lines` (ly
        do ton tai cua ca engine nay — fix loi gop dong danh sach cua pdf2zh).
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        base_url, api_key, model = _resolve_openai_compat(
            service, deepseek_base_url=self._deepseek_base_url
        )

        args = [
            "--files",
            str(input_path),
            "--pages",
            page_range,
            "--output",
            str(output_dir),
            "-li",
            lang_in,
            "-lo",
            lang_out,
            "--openai",
            "--openai-base-url",
            base_url,
            "--openai-api-key",
            api_key,
            "--openai-model",
            model,
            "--pool-max-workers",
            str(thread),
            "--watermark-output-mode",
            "no_watermark",
            "--only-include-translated-page",
            "--no-auto-extract-glossary",
            "--skip-scanned-detection",
            "--split-short-lines",
        ]
        if prompt_file is not None:
            # babeldoc `--custom-system-prompt` nhan CHUOI, khong nhan duong
            # dan file (Architecture.md 6.14.2) — khac han `pdf2zh --prompt`.
            args.extend(["--custom-system-prompt", prompt_file.read_text(encoding="utf-8")])
        if ignore_cache:
            args.append("--ignore-cache")

        env = {**os.environ, **service.envs, "COLUMNS": "200"}

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
            await asyncio.wait(drains, timeout=5.0)
            for d in drains:
                d.cancel()

        duration = time.monotonic() - start
        stdout = bytes(stdout_buf).decode("utf-8", errors="replace")
        stderr = bytes(stderr_buf).decode("utf-8", errors="replace")
        # Dung lai RATE_LIMIT_LINE_RE hien co, KHONG viet regex moi
        # (Architecture.md 6.14.3) — verified song qua CLI babeldoc that
        # (B10/B11): moi canh bao tenacity sinh dung 1 token "RateLimitError"
        # tren stdout, dong bi rich wrap nen chi neo token la dung.
        rate_limit_hits = len(RATE_LIMIT_LINE_RE.findall(stdout + "\n" + stderr))

        if timed_out:
            raise BabeldocTimeoutError(
                f"babeldoc vuot qua timeout {timeout_seconds}s cho {input_path} (trang {page_range})",
                stdout=stdout,
                stderr=stderr,
                rate_limit_hits=rate_limit_hits,
            )

        if process.returncode != 0:
            raise BabeldocError(
                f"babeldoc exited with code {process.returncode} for {input_path}: {stderr.strip()}",
                stdout=stdout,
                stderr=stderr,
                rate_limit_hits=rate_limit_hits,
            )

        # Ten file output cua babeldoc KHAC pdf2zh (B7, verified song):
        # "{stem}.no_watermark.{lang_out}.mono.pdf" / "...dual.pdf".
        stem = input_path.stem
        mono_path = output_dir / f"{stem}.no_watermark.{lang_out}.mono.pdf"
        dual_path = output_dir / f"{stem}.no_watermark.{lang_out}.dual.pdf"

        return BabeldocResult(
            success=True,
            mono_path=mono_path,
            dual_path=dual_path if dual_path.exists() else None,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            rate_limit_hits=rate_limit_hits,
        )
