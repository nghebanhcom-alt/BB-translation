"""Unit tests for `BabeldocRunner` (Architecture.md section 6.14).

Golden files under `tests/fixtures/babeldoc/` were captured from 2 LIVE spikes
run against the real `babeldoc` 0.6.4 CLI already installed on the dev
machine (Protocol 5 muc 3 — no hand-written mocks):

- spike1_ok_*: a fake OpenAI-compat `ThreadingHTTPServer` (127.0.0.1) answering
  200 to every request, run through the actual `babeldoc` CLI with the exact
  hardcoded flags this runner uses. Confirms output filename pattern (B7) and
  page-count effect of `--only-include-translated-page` (B8).
- spike2_429_*: same setup but the fake server returns HTTP 429 for the first
  40 requests. Confirms the real `RateLimitError` log shape (B10/B11): 40
  forced 429s -> 12 "RateLimitError" tokens on stdout, 0 on stderr — the same
  ~3x undercount Architecture.md 6.14.1/6.14.5 documents.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.services.babeldoc_runner import (
    BabeldocError,
    BabeldocRunner,
    BabeldocTimeoutError,
    _resolve_openai_compat,
)
from src.services.pdf2zh_service_map import Pdf2zhService, UnsupportedForPdfPipelineError

_FIXTURES = Path(__file__).parent / "fixtures" / "babeldoc"

_DEEPSEEK_SERVICE = Pdf2zhService(
    service_arg="deepseek:deepseek-chat",
    envs={"DEEPSEEK_API_KEY": "sk-fake", "DEEPSEEK_MODEL": "deepseek-chat"},
    supports_custom_prompt=True,
)
_OPENAI_SERVICE = Pdf2zhService(
    service_arg="openai:gpt-4o-mini",
    envs={
        "OPENAI_API_KEY": "sk-fake",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_MODEL": "gpt-4o-mini",
    },
    supports_custom_prompt=True,
)


class _FakeStreamReader:
    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = list(chunks or [])

    async def read(self, _n: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = _FakeStreamReader([stdout] if stdout else [])
        self.stderr = _FakeStreamReader([stderr] if stderr else [])
        self.killed = False

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> None:
        return None


def _read_fixture(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


# --- _resolve_openai_compat -------------------------------------------------


def test_resolve_openai_compat_openai_reads_all_three_from_envs() -> None:
    base_url, api_key, model = _resolve_openai_compat(_OPENAI_SERVICE)
    assert base_url == "https://api.openai.com/v1"
    assert api_key == "sk-fake"
    assert model == "gpt-4o-mini"


def test_resolve_openai_compat_claude_reads_openailiked_envs() -> None:
    service = Pdf2zhService(
        service_arg="openailiked:claude-sonnet-4-5",
        envs={
            "OPENAILIKED_BASE_URL": "https://api.anthropic.com/v1/",
            "OPENAILIKED_API_KEY": "sk-ant-fake",
            "OPENAILIKED_MODEL": "claude-sonnet-4-5",
        },
        supports_custom_prompt=True,
    )
    base_url, api_key, model = _resolve_openai_compat(service)
    assert base_url == "https://api.anthropic.com/v1/"
    assert api_key == "sk-ant-fake"
    assert model == "claude-sonnet-4-5"


def test_resolve_openai_compat_gemini_uses_verified_compat_base_url() -> None:
    # Architecture.md 6.14.1 B14 — WebFetch chinh thuc Gemini docs.
    service = Pdf2zhService(
        service_arg="gemini:gemini-2.5-pro",
        envs={"GEMINI_API_KEY": "g-fake", "GEMINI_MODEL": "gemini-2.5-pro"},
        supports_custom_prompt=True,
    )
    base_url, api_key, model = _resolve_openai_compat(service)
    assert base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert api_key == "g-fake"
    assert model == "gemini-2.5-pro"


def test_resolve_openai_compat_deepseek_uses_known_base_url() -> None:
    base_url, api_key, model = _resolve_openai_compat(_DEEPSEEK_SERVICE)
    assert base_url == "https://api.deepseek.com"
    assert api_key == "sk-fake"
    assert model == "deepseek-chat"


def test_resolve_openai_compat_deepseek_honors_settings_override() -> None:
    """Review-report.md non-blocking suggestion: `deepseek_base_url` is in
    `SETTINGS_DB_OVERRIDABLE_FIELDS`, so a user-configured override must reach
    babeldoc too, not just the hardcoded default."""
    base_url, _api_key, _model = _resolve_openai_compat(
        _DEEPSEEK_SERVICE, deepseek_base_url="https://custom.deepseek.internal"
    )
    assert base_url == "https://custom.deepseek.internal"


def test_resolve_openai_compat_ollama_derives_v1_base_url() -> None:
    service = Pdf2zhService(
        service_arg="ollama:gemma2:27b",
        envs={"OLLAMA_HOST": "http://localhost:11434", "OLLAMA_MODEL": "gemma2:27b"},
        supports_custom_prompt=True,
    )
    base_url, _api_key, model = _resolve_openai_compat(service)
    assert base_url == "http://localhost:11434/v1"
    assert model == "gemma2:27b"


def test_resolve_openai_compat_unknown_provider_raises() -> None:
    service = Pdf2zhService(
        service_arg="deepl", envs={"DEEPL_AUTH_KEY": "x"}, supports_custom_prompt=False
    )
    with pytest.raises(UnsupportedForPdfPipelineError):
        _resolve_openai_compat(service)


# --- translate_pages ---------------------------------------------------------


@pytest.mark.asyncio
async def test_translate_pages_success_hardcodes_all_required_flags(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )

    runner = BabeldocRunner()
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "output"
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Dich chinh xac.")

    result = await runner.translate_pages(
        input_path=input_path,
        output_dir=output_dir,
        page_range="1-40",
        service=_DEEPSEEK_SERVICE,
        prompt_file=prompt_file,
        lang_out="vi",
        thread=6,
    )

    # Output path pattern — captured from live golden listing (Protocol 5),
    # NOT hand-typed per Architecture.md 6.14.1 B7.
    assert result.mono_path == output_dir / "input.no_watermark.vi.mono.pdf"
    assert result.dual_path is None  # not actually written by this mock

    create_exec.assert_awaited_once()
    args = create_exec.call_args.args
    assert args[0] == "babeldoc"
    assert "--files" in args
    assert str(input_path) in args
    assert "--openai" in args
    assert "--openai-base-url" in args
    assert "https://api.deepseek.com" in args
    assert "--openai-api-key" in args
    assert "sk-fake" in args
    assert "--openai-model" in args
    assert "deepseek-chat" in args
    assert "--pool-max-workers" in args
    assert "6" in args
    assert "--watermark-output-mode" in args
    assert "no_watermark" in args
    assert "--only-include-translated-page" in args
    assert "--no-auto-extract-glossary" in args
    assert "--skip-scanned-detection" in args
    assert "--split-short-lines" in args
    # `--custom-system-prompt` nhan NOI DUNG file, khong phai duong dan.
    assert "--custom-system-prompt" in args
    assert "Dich chinh xac." in args
    assert str(prompt_file) not in args

    env = create_exec.call_args.kwargs["env"]
    assert env["DEEPSEEK_API_KEY"] == "sk-fake"
    assert env["COLUMNS"] == "200"


@pytest.mark.asyncio
async def test_translate_pages_without_prompt_file_omits_flag(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner()
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
        prompt_file=None,
    )
    args = create_exec.call_args.args
    assert "--custom-system-prompt" not in args


@pytest.mark.asyncio
async def test_translate_pages_creates_output_dir(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = BabeldocRunner()
    output_dir = tmp_path / "nested" / "does" / "not" / "exist"
    assert not output_dir.exists()

    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=output_dir,
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    assert output_dir.exists()


@pytest.mark.asyncio
async def test_translate_pages_failure_raises_babeldoc_error(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=1, stderr=b"babeldoc: invalid api key")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = BabeldocRunner()
    with pytest.raises(BabeldocError, match="invalid api key"):
        await runner.translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_DEEPSEEK_SERVICE,
        )


@pytest.mark.asyncio
async def test_translate_pages_timeout_kills_process_and_preserves_output(
    tmp_path: Path, mocker
) -> None:
    async def _timeout(*args, **kwargs):
        raise TimeoutError

    mocker.patch("asyncio.wait_for", side_effect=_timeout)
    fake_process = _FakeProcess(returncode=0, stdout=b"some progress\n", stderr=b"some warning\n")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = BabeldocRunner()
    with pytest.raises(BabeldocTimeoutError) as exc_info:
        await runner.translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_DEEPSEEK_SERVICE,
            timeout_seconds=1,
        )

    assert fake_process.killed is True
    assert exc_info.value.stdout == "some progress\n"
    assert exc_info.value.stderr == "some warning\n"


@pytest.mark.asyncio
async def test_translate_pages_counts_rate_limit_hits_from_golden_stdout(
    tmp_path: Path, mocker
) -> None:
    """R5 golden-file requirement: `rate_limit_hits` must be derived from the
    REAL stdout captured off the live babeldoc CLI (spike2_429), not a
    hand-typed string — 40 forced HTTP 429s produced exactly 12
    "RateLimitError" tokens, 0 on stderr (Architecture.md 6.14.1 B10/B11).
    """
    stdout_payload = _read_fixture("spike2_429_stdout.log")
    stderr_payload = _read_fixture("spike2_429_stderr.log")
    assert stdout_payload.count(b"RateLimitError") == 12
    assert stderr_payload.count(b"RateLimitError") == 0

    fake_process = _FakeProcess(returncode=0, stdout=stdout_payload, stderr=stderr_payload)
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = BabeldocRunner()
    result = await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="14-14",
        service=_DEEPSEEK_SERVICE,
    )

    assert result.rate_limit_hits == 12


def test_golden_mono_output_filename_matches_live_spike_listing() -> None:
    """Protocol 5 muc 3: khang dinh pattern ten file output tren golden
    listing capture tu spike that (khong viet tay). File goc dung trong ca 2
    spike: "...-1-25.pdf", chay `--pages 14`, `-lo vi`.
    """
    listing = (_FIXTURES / "spike_output_listing.txt").read_text()
    assert "libgen.li-1-25.no_watermark.vi.mono.pdf" in listing
    assert "libgen.li-1-25.no_watermark.vi.dual.pdf" in listing

    stem = "898a567a-5034-41ed-8a95-7fc7dc1b4ca9_Figoni, Paula - How baking works_ exploring the fundamentals of baking science (2007_2008, Wiley) - libgen.li-1-25"
    lang_out = "vi"
    expected_mono = f"{stem}.no_watermark.{lang_out}.mono.pdf"
    expected_dual = f"{stem}.no_watermark.{lang_out}.dual.pdf"
    assert expected_mono in listing
    assert expected_dual in listing
