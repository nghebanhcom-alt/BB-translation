from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.services.pdf2zh_runner import Pdf2zhError, Pdf2zhRunner, Pdf2zhTimeoutError
from src.services.pdf2zh_service_map import Pdf2zhService

_DEEPSEEK_SERVICE = Pdf2zhService(
    service_arg="deepseek:deepseek-chat",
    envs={"DEEPSEEK_API_KEY": "sk-fake", "DEEPSEEK_MODEL": "deepseek-chat"},
    supports_custom_prompt=True,
)


class _FakeStreamReader:
    """Minimal stand-in for asyncio.StreamReader: yields `chunks` then EOF."""

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


@pytest.mark.asyncio
async def test_translate_pages_success(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )

    runner = Pdf2zhRunner()
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "output"
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Source Text: ${text}")

    result = await runner.translate_pages(
        input_path=input_path,
        output_dir=output_dir,
        page_range="1-40",
        service=_DEEPSEEK_SERVICE,
        prompt_file=prompt_file,
    )

    assert result.success is True
    assert result.mono_path == output_dir / "input-mono.pdf"
    assert result.dual_path is None  # pdf2zh didn't actually write it in this mock
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.rate_limit_hits == 0
    assert result.duration_seconds >= 0

    create_exec.assert_awaited_once()
    args = create_exec.call_args.args
    assert args[0] == "pdf2zh"
    assert str(input_path) in args
    assert "--pages" in args
    assert "1-40" in args
    assert "-s" in args
    assert "deepseek:deepseek-chat" in args
    assert "--prompt" in args
    assert str(prompt_file) in args
    # API key must never appear in argv (ps-visible) — only in env.
    assert "sk-fake" not in args

    env = create_exec.call_args.kwargs["env"]
    assert env["DEEPSEEK_API_KEY"] == "sk-fake"


@pytest.mark.asyncio
async def test_translate_pages_creates_output_dir(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = Pdf2zhRunner()
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
async def test_translate_pages_failure_raises_with_stderr(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=1, stderr=b"pdf2zh: invalid API key")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = Pdf2zhRunner()

    with pytest.raises(Pdf2zhError, match="invalid API key"):
        await runner.translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_DEEPSEEK_SERVICE,
        )


@pytest.mark.asyncio
async def test_translate_pages_without_custom_prompt_support_drops_prompt_flag(
    tmp_path: Path, mocker
) -> None:
    """DeepL-shaped service: `supports_custom_prompt=False` -> `--prompt` never
    reaches argv, even if a prompt_file is passed (defense in depth — in
    practice Pdf2zhServiceMapper already rejects DeepL before this is reached).
    """
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    no_prompt_service = Pdf2zhService(
        service_arg="deepl", envs={"DEEPL_AUTH_KEY": "x"}, supports_custom_prompt=False
    )

    runner = Pdf2zhRunner()
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=no_prompt_service,
        prompt_file=tmp_path / "prompt.txt",
    )

    args = create_exec.call_args.args
    assert "--prompt" not in args


@pytest.mark.asyncio
async def test_translate_pages_timeout_kills_process_and_raises(tmp_path: Path, mocker) -> None:
    async def _timeout(*args, **kwargs):
        raise TimeoutError

    mocker.patch("asyncio.wait_for", side_effect=_timeout)
    fake_process = _FakeProcess(returncode=0)
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = Pdf2zhRunner()

    with pytest.raises(Pdf2zhTimeoutError):
        await runner.translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_DEEPSEEK_SERVICE,
            timeout_seconds=1,
        )

    assert fake_process.killed is True


@pytest.mark.asyncio
async def test_translate_pages_timeout_preserves_drained_stdout_and_stderr(
    tmp_path: Path, mocker
) -> None:
    """Architecture.md 6.12.3 (D1): a timeout must NOT discard output already
    produced before the kill — it's the only way to tell rate-limiting apart
    from plain slowness."""

    async def _timeout(*args, **kwargs):
        raise TimeoutError

    mocker.patch("asyncio.wait_for", side_effect=_timeout)
    fake_process = _FakeProcess(
        returncode=0,
        stdout=b"some progress output\n",
        stderr=b"some warning\n",
    )
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = Pdf2zhRunner()

    with pytest.raises(Pdf2zhTimeoutError) as exc_info:
        await runner.translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_DEEPSEEK_SERVICE,
            timeout_seconds=1,
        )

    err = exc_info.value
    assert err.stdout == "some progress output\n"
    assert err.stderr == "some warning\n"
    assert err.rate_limit_hits == 0


@pytest.mark.asyncio
async def test_translate_pages_timeout_counts_rate_limit_hits_from_stdout(
    tmp_path: Path, mocker
) -> None:
    """S9: pdf2zh's rich logging writes RateLimitError lines to STDOUT, not
    stderr — the count must be read from stdout (Architecture.md 6.12.2 D1)."""

    async def _timeout(*args, **kwargs):
        raise TimeoutError

    mocker.patch("asyncio.wait_for", side_effect=_timeout)
    stdout_payload = (
        b"WARNING RateLimitError <string>:6\n"
        b", retrying in 3.5 seconds... (Attempt 7/100)\n"
        b"WARNING RateLimitError <string>:6\n"
        b", retrying in 5.0 seconds... (Attempt 8/100)\n"
    )
    fake_process = _FakeProcess(returncode=0, stdout=stdout_payload, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = Pdf2zhRunner()

    with pytest.raises(Pdf2zhTimeoutError) as exc_info:
        await runner.translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_DEEPSEEK_SERVICE,
            timeout_seconds=1,
        )

    assert exc_info.value.rate_limit_hits == 2


@pytest.mark.asyncio
async def test_translate_pages_success_counts_rate_limit_hits_from_stdout(
    tmp_path: Path, mocker
) -> None:
    stdout_payload = b"WARNING RateLimitError, retrying in 1 seconds... (Attempt 1/100)\n"
    fake_process = _FakeProcess(returncode=0, stdout=stdout_payload, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = Pdf2zhRunner()
    result = await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )

    assert result.stdout == stdout_payload.decode()
    assert result.rate_limit_hits == 1
