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

import re
from pathlib import Path
from unittest.mock import AsyncMock

import fitz  # PyMuPDF
import pytest

from src.services.babeldoc_runner import (
    BabeldocDroppedParagraph,
    BabeldocError,
    BabeldocResult,
    BabeldocRunner,
    BabeldocTimeoutError,
    _parse_drop_report_file,
    _parse_drop_report_lines,
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


# --- split_short_lines (F1/F2, Architecture.md "Root Cause Analysis:
# Line-break/List Regression", 2026-09-06) -----------------------------------
#
# `--split-short-lines` used to be hardcoded True (F1: removed, see
# `translate_pages()` docstring for the live-verified tradeoff). These tests
# assert the FLAG ITSELF is no longer force-passed, and that the new opt-in
# parameter actually controls it — the exact gap Architecture.md N4 calls
# out in the OLD test this replaces (`assert "--split-short-lines" in args`
# only proved the flag was passed, never that passing it produced a correct
# layout).
#
# NOTE on defaults: `BabeldocRunner.translate_pages()` ITSELF still defaults
# `split_short_lines` to `False` — a caller must opt in explicitly. The
# PRODUCTION default lives one layer up, on `Settings.babeldoc_split_short_lines`
# (`src/core/config.py`), which `JobOrchestrator` reads and passes through
# (see `tests/integration/test_job_orchestrator.py`
# `test_babeldoc_split_short_lines_defaults_to_enabled_with_babeldoc_factor`).
# That Settings default was flipped to `True`/`0.8` (2026-09-06, Architecture.md
# "Đo lại F1 trên nhiều trang") AFTER this file's tests were first written
# against the original `False`/`0.5` default — do not read "defaults to
# False" in the test names below as the current recommended production
# behavior; it only describes this raw method's own signature default when
# called with no `split_short_lines` argument at all.


@pytest.mark.asyncio
async def test_translate_pages_omits_split_short_lines_by_default(tmp_path: Path, mocker) -> None:
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
    )
    args = create_exec.call_args.args
    assert "--split-short-lines" not in args
    assert "--short-line-split-factor" not in args


@pytest.mark.asyncio
async def test_translate_pages_enables_split_short_lines_when_requested(
    tmp_path: Path, mocker
) -> None:
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
        split_short_lines=True,
        short_line_split_factor=0.5,
    )
    args = list(create_exec.call_args.args)
    assert "--split-short-lines" in args
    assert "--short-line-split-factor" in args
    assert args[args.index("--short-line-split-factor") + 1] == "0.5"


@pytest.mark.asyncio
async def test_translate_pages_omits_factor_flag_when_split_short_lines_disabled(
    tmp_path: Path, mocker
) -> None:
    """A caller passing a factor WITHOUT also enabling `split_short_lines` is
    a caller bug (the factor has no effect on its own per babeldoc's own
    `and` condition, VERIFIED `paragraph_finder.py:891`) — defense in depth:
    never emit an orphaned `--short-line-split-factor` with no
    `--split-short-lines` alongside it."""
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
        split_short_lines=False,
        short_line_split_factor=0.5,
    )
    args = create_exec.call_args.args
    assert "--split-short-lines" not in args
    assert "--short-line-split-factor" not in args


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
    # `--custom-system-prompt` nhan NOI DUNG file, khong phai duong dan.
    assert "--custom-system-prompt" in args
    assert "Dich chinh xac." in args
    assert str(prompt_file) not in args

    env = create_exec.call_args.kwargs["env"]
    assert env["DEEPSEEK_API_KEY"] == "sk-fake"
    assert env["COLUMNS"] == "200"


@pytest.mark.asyncio
async def test_translate_pages_deepseek_disables_thinking(tmp_path: Path, mocker) -> None:
    """DeepSeek phai duoc gui `--openai-thinking disabled` VA dung thu tu cap
    flag/value. Ly do: babeldoc hardcode `max_tokens=2048`; voi reasoning model
    (`deepseek-v4-flash`) toan bo ngan sach token bi reasoning an het,
    `message.content` rong -> `json.loads("")` raise -> ca batch roi xuong
    fallback -> mat noi dung hang loat. Live-verified 2026-09-06, xem docstring
    cua `_thinking_args`."""
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
    )
    args = list(create_exec.call_args.args)
    assert "--openai-thinking" in args
    assert args[args.index("--openai-thinking") + 1] == "disabled"


@pytest.mark.asyncio
async def test_translate_pages_non_deepseek_omits_thinking_flag(tmp_path: Path, mocker) -> None:
    """`thinking` la truong rieng cua DeepSeek API — gui cho OpenAI-compat khac
    co the bi tu choi 400, nen flag nay KHONG duoc xuat hien voi provider khac."""
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner()
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_OPENAI_SERVICE,
    )
    assert "--openai-thinking" not in create_exec.call_args.args


def _gemini_service(model: str) -> Pdf2zhService:
    return Pdf2zhService(
        service_arg=f"gemini:{model}",
        envs={"GEMINI_API_KEY": "fake", "GEMINI_MODEL": model},
        supports_custom_prompt=True,
    )


@pytest.mark.asyncio
async def test_translate_pages_rejects_unverified_gemini_model_before_spawning(
    tmp_path: Path, mocker
) -> None:
    """Model Gemini co thinking dot het `max_tokens=2048` cua babeldoc -> JSON
    hong -> babeldoc bo ca batch -> PDF mat noi dung nhung job van 'completed'.
    Phai chan TRUOC khi spawn subprocess, khong duoc chay roi giao file hong.
    Live-verified 2026-09-06 (`gemini-3-flash-preview`: thinking=1963,
    finish_reason='length', JSON khong parse duoc)."""
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=_FakeProcess(returncode=0))
    )
    with pytest.raises(UnsupportedForPdfPipelineError, match="gemini-3-flash-preview"):
        await BabeldocRunner().translate_pages(
            input_path=tmp_path / "input.pdf",
            output_dir=tmp_path / "out",
            page_range="1-10",
            service=_gemini_service("gemini-3-flash-preview"),
        )
    create_exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_translate_pages_allows_verified_gemini_model(tmp_path: Path, mocker) -> None:
    """`gemini-3.1-flash-lite` da verify song 2026-09-06: thinking=0,
    finish_reason='stop', JSON parse duoc -> khong bi chan."""
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=_FakeProcess(returncode=0))
    )
    await BabeldocRunner().translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_gemini_service("gemini-3.1-flash-lite"),
    )
    create_exec.assert_awaited_once()
    # `thinking` bi Gemini tra HTTP 400 (`Unknown name "thinking"`) — flag nay
    # KHONG duoc lot sang nhanh Gemini.
    assert "--openai-thinking" not in create_exec.call_args.args


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


# --- Bug #10 word_wrap_fix wiring (Architecture.md BA10.8/BA10.9 muc 2)
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_translate_pages_word_wrap_fix_enabled_sets_env_flag_1(
    tmp_path: Path, mocker
) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner(word_wrap_fix_enabled=True)
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    env = create_exec.call_args.kwargs["env"]
    assert env["BABELDOC_SHIM_WORD_WRAP_FIX"] == "1"


@pytest.mark.asyncio
async def test_translate_pages_word_wrap_fix_disabled_sets_env_flag_0(
    tmp_path: Path, mocker
) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner(word_wrap_fix_enabled=False)
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    env = create_exec.call_args.kwargs["env"]
    assert env["BABELDOC_SHIM_WORD_WRAP_FIX"] == "0"


@pytest.mark.asyncio
async def test_translate_pages_word_wrap_fix_env_absent_when_shim_disabled(
    tmp_path: Path, mocker
) -> None:
    """Doc lap voi 3 co Bug #7 (BA10.8): bien BABELDOC_SHIM_WORD_WRAP_FIX chi
    co y nghia khi shim tong (PYTHONPATH) CUNG duoc bat — giong het cach
    BABELDOC_SHIM_TOC_SPLIT/BABELDOC_SHIM_NUMBERED_LIST_SPLIT khong duoc gui
    khi `line_split_shim_enabled=False`."""
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner(line_split_shim_enabled=False, word_wrap_fix_enabled=True)
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    env = create_exec.call_args.kwargs["env"]
    assert "BABELDOC_SHIM_WORD_WRAP_FIX" not in env
    assert "PYTHONPATH" not in env or "babeldoc_shim" not in env.get("PYTHONPATH", "")


# --- Golden-file structural regression (N6 point 2, "assert cau truc, khong
# assert flag") -----------------------------------------------------------
#
# `tests/fixtures/babeldoc/page14_*.pdf` are REAL output from 2 live spikes
# (2026-09-06) run against the REAL installed `babeldoc` 0.6.4 CLI + real
# DeepSeek API, translating page 14 of the actual "How baking works" upload
# already in `data/uploads/` — chosen because it is a real numbered list
# (items "1." to "35.") laid out in a narrow 2-column format, exactly the
# median_width-skew condition Architecture.md RC-1 describes. NOT hand-typed
# mocks (Protocol 5 muc 3): `page14_numbered_list_source.pdf` is the source
# page extracted verbatim with PyMuPDF; the two `_mono.pdf` outputs are
# babeldoc's actual rendered result with `--split-short-lines`
# included/omitted, nothing else changed.
#
# These assertions document the MEASURED tradeoff from Architecture.md N5/N8
# honestly — they do NOT claim the "false" (F1-fixed) output is fully
# correct for this specific numbered-list page. Per Architecture.md RC-2,
# digit markers ("1.", "2.") are outside babeldoc's `BULLET_POINT_PATTERN`
# (VERIFIED `layout_helper.py:50-52`) and entirely depended on the removed
# heuristic to be split at all — so removing it measurably INCREASES
# same-line merging for numbered items on THIS page, while measurably
# DECREASING total block count page-wide on THIS ONE page.
#
# CORRECTION (2026-09-06, Architecture.md "Đo lại F1 trên nhiều trang — kết
# quả live A/B/C"): a later 21-run/7-page study found the drop in block count
# above is NOT evidence that RC-1 was fragmenting ORDINARY BODY TEXT — across
# all 7 pages tested (including this one's own body paragraphs), no prose
# paragraph was ever split by RC-1 in any configuration; the only real RC-1
# damage found was to a couple of short table/image captions on 2 of the 7
# pages. `Settings.babeldoc_split_short_lines` default was flipped back to
# `True` (with `factor=0.8`, not the `0.5` this file's numbers do NOT use —
# see below) BECAUSE of that broader finding — do not use the single-page
# numbers below to argue for keeping the flag off; they undercount the flag's
# benefit for numbered lists (this fixture used babeldoc's own default
# `factor=0.8` for the "true" arm, same as the now-current `Settings`
# default) and say nothing about the caption-only cost measured elsewhere.
# Both facts are still asserted below so this exact fixture pair cannot
# silently drift without a test failure — they are a historical snapshot,
# not a recommendation.


def _load_golden_text(filename: str) -> str:
    path = _FIXTURES / filename
    with fitz.open(path) as doc:
        return doc[0].get_text()


def test_golden_source_page_has_35_numbered_items() -> None:
    """Sanity check on the fixture's provenance: the real source page really
    does contain a 35-item numbered list (not a synthetic stand-in) — the
    2 golden outputs below are babeldoc's actual translation of it."""
    with fitz.open(_FIXTURES / "page14_numbered_list_source.pdf") as doc:
        source_text = doc[0].get_text()
    assert source_text.count("35.") == 1
    assert "EQUIPMENT AND SMALLWARES" in source_text


def test_split_short_lines_true_golden_output_over_fragments_numbered_list() -> None:
    """With `--split-short-lines` (the OLD hardcoded behavior): 31/35
    numbered items land on their own line (babeldoc's own text-block count:
    36) — most items ARE separated, but RC-1 also mis-splits ordinary body
    text elsewhere on the page (see the "false" golden counterpart below for
    the page-wide block-count contrast)."""
    text = _load_golden_text("page14_split_short_lines_true_mono.pdf")
    own_line_items = len(re.findall(r"(?:^|\n)\s*\d{1,2}\.\s", text))
    assert own_line_items == 31

    with fitz.open(_FIXTURES / "page14_split_short_lines_true_mono.pdf") as doc:
        blocks = doc[0].get_text("blocks")
    assert len(blocks) == 36


def test_split_short_lines_false_golden_output_reduces_page_wide_fragmentation() -> None:
    """F1 fix (`--split-short-lines` no longer sent): page-wide text-block
    count drops from 36 to 11 (less over-fragmentation of ordinary
    paragraphs — the RC-1 symptom user reported as "xuong dong chua chinh
    xac"). Documented tradeoff: only 4/35 numbered items keep their own
    line — see module-level comment above and Architecture.md RC-2. This is
    the honest empirical baseline this fix produces on a real numbered-list
    page, not an aspirational target."""
    text = _load_golden_text("page14_split_short_lines_false_mono.pdf")
    own_line_items = len(re.findall(r"(?:^|\n)\s*\d{1,2}\.\s", text))
    assert own_line_items == 4

    with fitz.open(_FIXTURES / "page14_split_short_lines_false_mono.pdf") as doc:
        blocks = doc[0].get_text("blocks")
    assert len(blocks) == 11


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


# --- BL-04 (Architecture.md 6.22.4/6.22.5) — sidecar drop report ------------


@pytest.mark.asyncio
async def test_translate_pages_sets_drop_report_env_vars_inside_output_dir(
    tmp_path: Path, mocker
) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner(drop_report_enabled=True)
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    await runner.translate_pages(
        input_path=input_path,
        output_dir=output_dir,
        page_range="199-240",
        service=_DEEPSEEK_SERVICE,
    )
    env = create_exec.call_args.kwargs["env"]
    assert env["BABELDOC_SHIM_DROP_REPORT"] == "1"
    # Architecture.md 6.22.4 "Vi tri file" — BAT BUOC nam TRONG output_dir
    # (== chunk_output_dir cua _call_translator()), voi page_range trong ten
    # file de 2 chunk chay song song khong ghi de nhau.
    expected_path = output_dir / "input.199-240.drops.jsonl"
    assert env["BABELDOC_SHIM_DROP_REPORT_PATH"] == str(expected_path)


@pytest.mark.asyncio
async def test_translate_pages_drop_report_env_flag_0_when_disabled(tmp_path: Path, mocker) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner(drop_report_enabled=False)
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    env = create_exec.call_args.kwargs["env"]
    assert env["BABELDOC_SHIM_DROP_REPORT"] == "0"
    # Path VAN duoc truyen (shim doc _drop_report_enabled() rieng) — chi co
    # gia tri BAT/TAT thay doi, khong phai su co mat cua bien path.
    assert "BABELDOC_SHIM_DROP_REPORT_PATH" in env


@pytest.mark.asyncio
async def test_translate_pages_drop_report_env_absent_when_shim_disabled(
    tmp_path: Path, mocker
) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    create_exec = mocker.patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process)
    )
    runner = BabeldocRunner(line_split_shim_enabled=False, drop_report_enabled=True)
    await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    env = create_exec.call_args.kwargs["env"]
    assert "BABELDOC_SHIM_DROP_REPORT" not in env
    assert "BABELDOC_SHIM_DROP_REPORT_PATH" not in env


@pytest.mark.asyncio
async def test_translate_pages_reads_drop_report_from_exact_sidecar_path(
    tmp_path: Path, mocker
) -> None:
    """`BabeldocRunner` phai doc DUNG file sidecar ma no vua truyen duong dan
    qua env cho subprocess — khong tu doan duong dan khac, khong doc stdout."""
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))

    runner = BabeldocRunner()
    input_path = tmp_path / "input.pdf"
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True)
    sidecar_path = output_dir / "input.1-10.drops.jsonl"
    sidecar_path.write_text(
        '{"type":"header","schema":"babeldoc_drop_report/v2","babeldoc_version":"0.6.4","pid":1}\n'
        '{"type":"page","page_number_1based":1,"paragraph_count":2,"dropped_count":1}\n'
        '{"type":"drop","page_number_1based":1,"debug_id":"abc12","layout_label":"plain text",'
        '"box":[1.0,2.0,3.0,4.0],"optimal_scale":0.1,"scale":null,'
        '"text_excerpt":"mat het roi","text_len":11}\n',
        encoding="utf-8",
    )

    result = await runner.translate_pages(
        input_path=input_path,
        output_dir=output_dir,
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )

    assert result.drop_report.available is True
    assert result.drop_report.observed_pages == frozenset({1})
    assert len(result.drop_report.dropped) == 1
    assert result.drop_report.dropped[0].debug_id == "abc12"
    assert result.drop_report.dropped[0].page_number == 1
    assert result.drop_report.dropped[0].box == (1.0, 2.0, 3.0, 4.0)


@pytest.mark.asyncio
async def test_translate_pages_missing_sidecar_file_yields_unavailable_report(
    tmp_path: Path, mocker
) -> None:
    fake_process = _FakeProcess(returncode=0, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))
    runner = BabeldocRunner()
    result = await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    assert result.drop_report.available is False
    assert result.drop_report.dropped == []
    assert result.drop_report.header_count == 0


@pytest.mark.asyncio
async def test_translate_pages_counts_drop_sentinel_from_stdout_and_stderr(
    tmp_path: Path, mocker
) -> None:
    sentinel = "Unable to export paragraphs that have not yet been formatted"
    stdout_payload = f"{sentinel}: foo\n{sentinel}: bar\n".encode()
    fake_process = _FakeProcess(returncode=0, stdout=stdout_payload, stderr=b"")
    mocker.patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_process))
    runner = BabeldocRunner()
    result = await runner.translate_pages(
        input_path=tmp_path / "input.pdf",
        output_dir=tmp_path / "out",
        page_range="1-10",
        service=_DEEPSEEK_SERVICE,
    )
    assert result.drop_report.stdout_sentinel_count == 2


# --- _parse_drop_report_lines / _parse_drop_report_file (thuan) ------------


def test_parse_drop_report_lines_multiple_headers_are_normal() -> None:
    """macOS `mp.set_start_method("spawn")` -> moi process con re-import
    sitecustomize -> co the co N dong header. Parser CHI can >=1 dong hop
    le, KHONG gia dinh dung 1 dong (Architecture.md 6.22.4 "Quy tac parse")."""
    lines = [
        '{"type":"header","schema":"babeldoc_drop_report/v2","babeldoc_version":"0.6.4","pid":1}',
        '{"type":"header","schema":"babeldoc_drop_report/v2","babeldoc_version":"0.6.4","pid":2}',
        '{"type":"page","page_number_1based":1,"paragraph_count":1,"dropped_count":0}',
    ]
    report = _parse_drop_report_lines(lines)
    assert report.available is True
    assert report.header_count == 2
    assert report.observed_pages == frozenset({1})
    assert report.dropped == []


def test_parse_drop_report_lines_malformed_line_counted_not_fatal() -> None:
    lines = [
        '{"type":"header","schema":"babeldoc_drop_report/v2","babeldoc_version":"0.6.4","pid":1}',
        "not valid json {{{",
        '{"type":"page","page_number_1based":1,"paragraph_count":1,"dropped_count":0}',
    ]
    report = _parse_drop_report_lines(lines)
    assert report.available is True
    assert report.malformed_line_count == 1
    assert report.observed_pages == frozenset({1})


def test_parse_drop_report_lines_no_header_is_unavailable() -> None:
    lines = ['{"type":"page","page_number_1based":1,"paragraph_count":1,"dropped_count":0}']
    report = _parse_drop_report_lines(lines)
    assert report.available is False


def test_parse_drop_report_lines_blank_lines_ignored() -> None:
    lines = [
        "",
        '{"type":"header","schema":"babeldoc_drop_report/v2","babeldoc_version":"0.6.4","pid":1}',
        "   ",
    ]
    report = _parse_drop_report_lines(lines)
    assert report.available is True
    assert report.malformed_line_count == 0


def test_parse_drop_report_file_missing_file_is_unavailable(tmp_path: Path) -> None:
    report = _parse_drop_report_file(tmp_path / "does-not-exist.jsonl")
    assert report.available is False
    assert report.dropped == []
    assert report.header_count == 0
    assert report.malformed_line_count == 0


def test_parse_drop_report_file_reads_real_written_file(tmp_path: Path) -> None:
    path = tmp_path / "real.jsonl"
    path.write_text(
        '{"type":"header","schema":"babeldoc_drop_report/v2","babeldoc_version":"0.6.4","pid":1}\n'
        '{"type":"page","page_number_1based":230,"paragraph_count":9,"dropped_count":1}\n'
        '{"type":"drop","page_number_1based":230,"debug_id":"z9","layout_label":"plain text",'
        '"box":[61.5,223.6,332.3,466.6],"optimal_scale":0.1,"scale":null,'
        '"text_excerpt":"The term feuilletage...","text_len":614}\n',
        encoding="utf-8",
    )
    report = _parse_drop_report_file(path)
    assert report.available is True
    assert report.observed_pages == frozenset({230})
    assert report.page_dropped_counts == {230: 1}
    assert len(report.dropped) == 1
    dropped = report.dropped[0]
    assert dropped == BabeldocDroppedParagraph(
        page_number=230,
        debug_id="z9",
        layout_label="plain text",
        box=(61.5, 223.6, 332.3, 466.6),
        optimal_scale=0.1,
        scale=None,
        text_excerpt="The term feuilletage...",
        text_len=614,
    )


def test_parse_drop_report_file_reads_real_live_e2e_golden_fixture() -> None:
    """Gate test 1 (`test_drop_report_parse`, Architecture.md 6.22.9) — parses
    `tests/fixtures/babeldoc/drop_report_v2.jsonl`, the REAL sidecar written
    by a real `babeldoc` 0.6.4 subprocess during the live E2E harness
    (`scripts/bl04_live_e2e_chunk5.py`, 2026-09-11, chunk 5/`--pages
    199-240`/job `1ee1fdee`'s source file) — not hand-typed (R5-03/R6-03).

    That live run did NOT reproduce a `type=drop` line this time (dịch máy
    không tất định — see `tests/fixtures/babeldoc/README.md` "drop_report_v2.jsonl"
    for the full investigation, including live confirmation via PyMuPDF that
    the real feuilletage sidebar IS missing from that run's translated page
    230 output anyway, just via a different, out-of-scope-for-BL-04 channel).
    So this test only covers the `header`/`page`/`observed_pages` branches
    against real bytes; the `type=drop` field-shape branch stays covered by
    `test_parse_drop_report_file_reads_real_written_file` above (schema
    verified against source per R5-01, not live-captured).
    """
    report = _parse_drop_report_file(_FIXTURES / "drop_report_v2.jsonl")

    assert report.available is True
    assert report.header_count == 4  # 4 multiprocessing workers re-imported sitecustomize
    assert report.malformed_line_count == 0
    assert report.observed_pages == frozenset(range(199, 241))  # 42/42
    assert report.dropped == []
    assert all(count == 0 for count in report.page_dropped_counts.values())
    assert report.page_dropped_counts[230] == 0  # the page Domain Expert found the real drop on


def test_babeldoc_drop_report_dataclass_default_is_unavailable_not_zero_drops() -> None:
    """`BabeldocResult.drop_report` default (call sites khong truyen field
    nay) PHAI la trang thai 4 'KHONG do duoc', KHONG duoc coi la '0 drop
    that su' — chinh la phan biet chinh cua Architecture.md 6.22.6."""
    result = BabeldocResult(
        success=True,
        mono_path=Path("/tmp/x.pdf"),
        dual_path=None,
        stderr="",
        duration_seconds=0.1,
    )
    assert result.drop_report.available is False
