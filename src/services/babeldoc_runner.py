import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

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

#: Thu muc chua `sitecustomize.py` shim (Bug #7 fix, Architecture.md X4-1/X5
#: D7-2). Truyen qua `PYTHONPATH` cua subprocess babeldoc — CPython tu dong
#: `import sitecustomize` luc khoi dong interpreter con, TRUOC ca entry point
#: `babeldoc`. Khong import babeldoc trong process app duoc (chay qua
#: subprocess CLI o venv rieng qua `uv tool`) nen day la vector DUY NHAT co
#: tac dung — xem docstring day du trong `src/babeldoc_shim/sitecustomize.py`.
_BABELDOC_SHIM_DIR = str(Path(__file__).resolve().parent.parent / "babeldoc_shim")


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


def _is_deepseek(service: Pdf2zhService) -> bool:
    """True khi `service` tro toi DeepSeek — dung de quyet dinh co gui
    `--openai-thinking disabled` hay khong (xem `_thinking_args`)."""
    return {"DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"} <= service.envs.keys()


def _thinking_args(service: Pdf2zhService) -> list[str]:
    """`--openai-thinking disabled` cho DeepSeek, rong cho provider khac.

    VERIFIED 2026-09-06 (goi that api.deepseek.com + chay that babeldoc 0.6.4
    tren trang 22 cua "How baking works", xem CHANGELOG increment cung ngay):

    - `babeldoc/translator/translator.py:324` hardcode `max_tokens=2048` cho
      `do_llm_translate()` — duong dich chinh (il_translator_llm_only), khong
      co flag CLI nao doi duoc.
    - `deepseek-v4-flash` (model that dang dung, ghi trong bang `settings`) la
      reasoning model, MAC DINH bat thinking. Goi that voi `max_tokens=2048`:
      `finish_reason="length"`, `completion_tokens_details.reasoning_tokens=2048`,
      `message.content == ""` — toan bo ngan sach token bi reasoning an het,
      khong con token nao cho cau tra loi.
    - `json.loads("")` raise -> babeldoc bat exception o
      `il_translator_llm_only.py:852` -> ca batch roi xuong nhanh fallback ->
      mat noi dung hang loat tren PDF ket qua (trang 22: 647 ky tu thay vi
      3292).
    - Gui `thinking={"type":"disabled"}` (dung flag `--openai-thinking
      disabled` cua babeldoc, `translator.py:253-255`) -> `finish_reason="stop"`,
      khong con reasoning token, JSON hop le, 0 fallback, 3292 ky tu.

    CHI gui cho DeepSeek: `thinking` la truong rieng cua DeepSeek API.
    VERIFIED 2026-09-06 rang gui cho Gemini bi tu choi ngay:
    `{"thinking": {"type": "disabled"}}` -> HTTP 400 `Unknown name "thinking":
    Cannot find field` (xem `_assert_gemini_model_safe`). `--openai-thinking`
    cung nam trong `add_cache_impact_parameters("thinking", ...)`
    (`translator.py:255`), nen bat no tu dong lam invalidate cache cu — khong
    can `--ignore-cache`.
    """
    return ["--openai-thinking", "disabled"] if _is_deepseek(service) else []


#: Cac model Gemini DA VERIFY SONG (2026-09-06) la an toan cho duong babeldoc:
#: khong sinh thinking token, nen khong dung cham tran `max_tokens=2048`
#: hardcode cua babeldoc (`babeldoc/translator/translator.py:324`).
#:
#: Cach verify (lap lai y het khi muon them model vao day): goi that endpoint
#: OpenAI-compat cua Gemini voi `max_tokens=2048` va 1 batch ~30 doan (kich
#: thuoc that cua 1 trang muc luc/bang), roi kiem tra
#: `total_tokens - prompt_tokens - completion_tokens == 0` (khong co thinking
#: token) VA `json.loads(content)` chay duoc.
#:
#: Ket qua do that tren cung 1 batch 30 doan:
#: - `gemini-3.1-flash-lite` -> thinking=0, `finish_reason="stop"`, JSON parse OK.
#: - `gemini-flash-latest`   -> thinking=2104, `finish_reason="length"`, JSON HONG.
#: - `gemini-3-flash-preview`-> thinking=1963, `finish_reason="length"`, JSON HONG.
#: - `gemini-2.5-flash` (default CU cua project) -> HTTP 404 "no longer
#:   available to new users" — model nay da chet, khong con goi duoc.
#:
#: babeldoc 0.6.4 KHONG co flag nao tat duoc thinking cua Gemini: ca
#: `--openai-thinking` (gui `thinking`) lan `--openai-reasoning` (gui
#: `reasoning`) deu bi Gemini tra ve HTTP 400 `Unknown name ... Cannot find
#: field`. Knob DUY NHAT co tac dung la `reasoning_effort: "none"` (tham so
#: top-level rieng cua Gemini) — babeldoc khong co duong nao gui no. Vi vay
#: cach an toan duy nhat hien tai la chan tu dau, thay vi de job chay xong roi
#: tra ve PDF mat noi dung am tham.
_GEMINI_VERIFIED_SAFE_MODELS = frozenset({"gemini-3.1-flash-lite"})


def _assert_gemini_model_safe(service: Pdf2zhService) -> None:
    """Fail-fast TRUOC khi spawn subprocess neu model Gemini chua duoc verify
    la khong sinh thinking token — cung ky luat voi DeepL o
    `Pdf2zhServiceMapper` (Architecture.md 6.6.1 F7): tha bao loi ro rang con
    hon de pipeline chay het roi giao 1 file PDF mat noi dung ma khong ai biet.
    Xem `_GEMINI_VERIFIED_SAFE_MODELS` cho cach verify va so lieu do that.
    """
    model = service.envs.get("GEMINI_MODEL")
    if model is None or model in _GEMINI_VERIFIED_SAFE_MODELS:
        return
    raise UnsupportedForPdfPipelineError(
        f"Model Gemini '{model}' chua duoc verify an toan cho pipeline PDF (babeldoc). "
        "babeldoc hardcode max_tokens=2048; cac model Gemini co thinking dot het ngan "
        "sach token nay vao suy luan, tra ve noi dung bi cat -> babeldoc bo ca batch -> "
        "PDF ket qua mat noi dung ma job van bao 'completed'. babeldoc 0.6.4 khong co "
        "flag nao tat thinking cua Gemini (ca --openai-thinking lan --openai-reasoning "
        "deu bi Gemini tra HTTP 400). "
        f"Model da verify an toan: {sorted(_GEMINI_VERIFIED_SAFE_MODELS)}. "
        "Hoac dung DeepSeek (da co --openai-thinking disabled). "
        "Xem `_GEMINI_VERIFIED_SAFE_MODELS` de biet cach verify them model moi."
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

    #: Bug #9 (Architecture.md "Bug #9"). babeldoc tự typeset lại và tự bóp cỡ
    #: chữ (tới tối thiểu 10%) để vừa box, bỏ hẳn đoạn nếu vẫn không vừa —
    #: KHÔNG BAO GIỜ vẽ tràn ra ngoài box. Chạy thêm `font_shrink_page()` trên
    #: output của nó không sửa được gì (median excess đo được = 0.00%, nó chỉ
    #: phản ứng với sai số float) nhưng vẫn redact + insert_text lại thật —
    #: gây Bug #8 (lệch toạ độ, đã fix) và XOÁ MẤT CHỮ THẬT (Bug #9).
    needs_font_shrink: ClassVar[bool] = False

    def __init__(
        self,
        executable: str = "babeldoc",
        deepseek_base_url: str = _DEFAULT_DEEPSEEK_BASE_URL,
        line_split_shim_enabled: bool = True,
        numbered_list_split_enabled: bool = True,
        toc_split_enabled: bool = False,
        word_wrap_fix_enabled: bool = False,
    ) -> None:
        self._executable = executable
        self._deepseek_base_url = deepseek_base_url
        #: Bug #7 fix (Architecture.md X5 D7-2). Mac dinh True — khong yeu
        #: cau feature flag rieng theo spec, nhung giu co che tat khan cap
        #: giong cac feature flag khac cua project (vd
        #: `babeldoc_rotated_text_overlay`, `mineru_det_probe_enabled`) de
        #: rollback tuc thi khong can deploy lai code neu shim gay van de o
        #: version babeldoc khac ngoai du kien.
        self._line_split_shim_enabled = line_split_shim_enabled
        #: Bug #7 fix buoc 7.2 — Ca A (Architecture.md X5 D7-3). Doc lap voi
        #: `line_split_shim_enabled`: chi co tac dung khi shim tren CUNG bat
        #: (PYTHONPATH phai duoc set), truyen qua bien moi truong rieng de
        #: `sitecustomize.py` doc va co the tat rieng heuristic numbered-list
        #: (moi hon, rui ro cao hon 7.1) ma khong dong ca shim.
        self._numbered_list_split_enabled = numbered_list_split_enabled
        #: Bug #7 fix buoc 7.4-b — Ca C (Architecture.md AA5). Doc lap voi 2
        #: co tren, cung ly do: chi co tac dung khi shim tong CUNG bat, truyen
        #: qua bien moi truong RIENG de tat duoc mot minh TOC-1 v2 (heuristic
        #: moi nhat/rui ro cao nhat, mac dinh TAT) ma khong dong 7.1/7.2.
        self._toc_split_enabled = toc_split_enabled
        #: Bug #10 (Architecture.md BA10.8). Doc lap HOAN TOAN voi 3 co tren
        #: (module/loader/rollback rieng — BA10.7 rang buoc #1): chi co tac
        #: dung khi shim tong CUNG bat (PYTHONPATH phai duoc set), truyen qua
        #: bien moi truong RIENG de tat duoc mot minh fix nay ma khong dong
        #: 7.1/7.2/7.4-b. Default `False` o day (khoi tao truc tiep trong
        #: test) — gia tri production THAT nam o
        #: `Settings.babeldoc_word_wrap_fix_enabled` (mac dinh `True`, xem
        #: src/core/config.py), giong het pattern cua `toc_split_enabled`.
        self._word_wrap_fix_enabled = word_wrap_fix_enabled

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
    ) -> BabeldocResult:
        """Run babeldoc for one chunk's page range and return the rendered PDFs.

        Cac flag sau la BAT BUOC, hardcode, khong tuy chon (bang doi chieu
        Architecture.md 6.14.2, moi flag co ly do rieng da verify song B6-B9):
        `--watermark-output-mode no_watermark`, `--only-include-translated-page`
        (thieu flag nay: mono output chua CA tai lieu thay vi rieng chunk, B8),
        `--no-auto-extract-glossary` (chan 4 request LLM phu ngoai chi phi da
        uoc tinh, B9), `--skip-scanned-detection` (tranh ScannedPDFError tren
        cau noi searchable PDF cua nhanh pdf_scan).

        `--split-short-lines` KHONG con hardcode (Architecture.md "Root Cause
        Analysis: Line-break/List Regression", F1/F2, 2026-09-06). Docstring
        cu (truoc F1) bien minh flag nay la "fix loi gop dong danh sach cua
        pdf2zh" — SAI theo nguon xac thuc that (source babeldoc 0.6.4 da cai,
        `paragraph_finder.py:891-901`): nhanh tach bullet (`is_bullet_point`)
        chay DOC LAP voi flag nay; flag chi them 1 heuristic hinh hoc
        ("dong truoc hep hon median_width toan trang * factor thi tach") ma
        chinh babeldoc canh bao trong help text la "may cause poor
        typesetting & bugs" (`main.py:179-182`).

        Tham so nay (`split_short_lines`/`short_line_split_factor`) CHI la co
        che ky thuat de bat/tat + chinh factor — GIA TRI MAC DINH production
        thuc te nam o `Settings.babeldoc_split_short_lines`/
        `babeldoc_short_line_split_factor` (`src/core/config.py`), va gia tri
        do DA DOI 2 LAN dua tren 2 lan do that khac nhau — xem
        `src/core/config.py` va Architecture.md section "Đo lại F1 trên
        nhiều trang — kết quả live A/B/C" (2026-09-06) cho ly do đầy đủ va so
        lieu 21 lan chay that/7 trang: ket luan cuoi cung la BAT flag nay VOI
        factor bang dung default goc cua babeldoc (`0.8`) xu ly numbered
        list/muc luc tot hon RO RET (vd trang 35-muc: 28 loi dinh chu -> 3),
        va tac hai RC-1 that te ra CHI gioi han o vai caption bang/anh ngan
        (khong phai doan van thuong lan rong nhu suy doan tu doc source ban
        dau — xem `tests/fixtures/babeldoc/page14_*` cho 1 lan do don le cu
        va Architecture.md cho bang do day du hon). Doc them chi tiet o
        `src/core/config.py` truoc khi doi lai gia tri nay — dung suy doan
        lai tu dau, 2 lan doi truoc do deu tung "suy doan hop ly" nhung sai vi
        chua do du du lieu.
        """
        _assert_gemini_model_safe(service)
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
            *_thinking_args(service),
            "--pool-max-workers",
            str(thread),
            "--watermark-output-mode",
            "no_watermark",
            "--only-include-translated-page",
            "--no-auto-extract-glossary",
            "--skip-scanned-detection",
        ]
        if split_short_lines:
            args.append("--split-short-lines")
            if short_line_split_factor is not None:
                # VERIFIED 2026-09-06 doc truc tiep tu babeldoc 0.6.4 da cai
                # (`main.py:184-189`): `--short-line-split-factor` la
                # `type=float, default=0.8`, chi co tac dung khi
                # `--split-short-lines` cung duoc bat (`paragraph_finder.py:891`
                # dung ca 2 gia tri trong cung 1 dieu kien `and`) — vi vay chi
                # gui flag nay khi `split_short_lines` cung True, tranh gui 1
                # flag mo côi khong anh huong gi.
                args.extend(["--short-line-split-factor", str(short_line_split_factor)])
        if prompt_file is not None:
            # babeldoc `--custom-system-prompt` nhan CHUOI, khong nhan duong
            # dan file (Architecture.md 6.14.2) — khac han `pdf2zh --prompt`.
            args.extend(["--custom-system-prompt", prompt_file.read_text(encoding="utf-8")])
        if ignore_cache:
            args.append("--ignore-cache")

        env = {**os.environ, **service.envs, "COLUMNS": "200"}
        if self._line_split_shim_enabled:
            # Noi vao PYTHONPATH hien co (neu co), khong ghi de — dung
            # os.pathsep de dung tren ca macOS/Linux (":") lan Windows (";")
            # neu can sau nay (Architecture.md X4-1 D7-2).
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                f"{_BABELDOC_SHIM_DIR}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else _BABELDOC_SHIM_DIR
            )
            env["BABELDOC_SHIM_NUMBERED_LIST_SPLIT"] = (
                "1" if self._numbered_list_split_enabled else "0"
            )
            env["BABELDOC_SHIM_TOC_SPLIT"] = "1" if self._toc_split_enabled else "0"
            env["BABELDOC_SHIM_WORD_WRAP_FIX"] = "1" if self._word_wrap_fix_enabled else "0"

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
