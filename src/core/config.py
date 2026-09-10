from functools import lru_cache
from typing import TYPE_CHECKING, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5-20250514"
    claude_max_tokens: int = 8192
    claude_temperature: float = 0.3
    claude_use_prompt_caching: bool = True

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    # Increment 6: doi tu "gpt-4o" -> "gpt-4o-mini" (re hon ~16 lan, du dung
    # cho hau het truong hop dich thuat) — day la nguyen nhan chinh khien user
    # thay uoc tinh $3.22 cho 1 cuon sach, dat hon can thiet.
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 8192
    openai_temperature: float = 0.3

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_max_tokens: int = 8192
    deepseek_temperature: float = 0.3

    gemini_api_key: str = ""
    # VERIFIED 2026-09-06 (goi that endpoint OpenAI-compat cua Gemini):
    # `gemini-2.5-pro`/`gemini-2.5-flash` tra HTTP 404 "no longer available to
    # new users" — default cu da chet. `gemini-3.1-flash-lite` la model Gemini
    # DUY NHAT da verify khong sinh thinking token, nen la model duy nhat an
    # toan voi tran `max_tokens=2048` hardcode cua babeldoc — xem
    # `_GEMINI_VERIFIED_SAFE_MODELS` (src/services/babeldoc_runner.py).
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_max_tokens: int = 8192
    gemini_temperature: float = 0.3

    deepl_api_key: str = ""
    deepl_formality: str = "default"

    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "gemma2:27b"
    ollama_max_tokens: int = 8192
    ollama_temperature: float = 0.3

    # MinerU OCR service — real contract verified in Architecture.md section 6.9.
    # MinerU's own default port is 8000, which this app already binds, so both the
    # native macOS process and the Docker port mapping expose it on host 8010.
    mineru_endpoint: str = "http://localhost:8010"
    # A real 200-500 page scan takes far longer than the previous 300s ceiling; the
    # async /tasks flow means only the per-request timeout needs to stay small.
    mineru_task_timeout_seconds: float = 3600.0
    mineru_request_timeout_seconds: float = 120.0
    # AC-11.2 threshold. Provisional — the metric it applies to is now computed by
    # BB-Translation from MinerU span scores, not supplied by MinerU (6.9.5/6.9.7),
    # so it must stay tunable until calibrated against real scans.
    ocr_confidence_threshold: float = 0.80

    # Bug #6 Phase 1 (Architecture.md "Final Decision" V6): rotated-text detection for
    # `pdf_scan` jobs runs MinerU's OWN detector (`PytorchPaddleOCR`) via a SEPARATE
    # subprocess using MinerU's dedicated venv interpreter — NOT the `mineru_endpoint`
    # HTTP service above, which never exposes raw poly angles through its API (V-1).
    # Default path matches the Tech Lead spike's verified installation
    # (`~/.local/share/uv/tools/mineru/bin/python`, `uv tool install mineru`); expanded
    # with `Path(...).expanduser()` at call time, not here (pydantic-settings does not
    # expand `~` for plain `str` fields).
    mineru_python_path: str = "~/.local/share/uv/tools/mineru/bin/python"
    # Feature flag matching `babeldoc_rotated_text_overlay`'s rollback pattern — this
    # probe is best-effort (Architecture.md V6 step 6: never fails the job), but a flag
    # lets it be disabled instantly if the subprocess proves too slow/flaky in production
    # without needing a code change.
    mineru_det_probe_enabled: bool = True

    database_url: str = "sqlite+aiosqlite:///data/bb_translation.db"

    max_concurrent_files: int = 3
    max_upload_size_mb: int = 500

    # `NOTO_FONT_PATH` only affects the legacy `pdf2zh` engine (it reads this
    # env var itself, see `Pdf2zhServiceMapper`) — `babeldoc` ignores it
    # entirely and always draws translated text with its OWN bundled font
    # asset, chosen by `babeldoc.assets.embedding_assets_metadata.get_font_family`
    # (verified 2026-09-05 by reading that source directly: "vi" isn't a
    # recognized language code there, so it falls through to `EN_FONT_FAMILY`,
    # whose "normal" entry is `NotoSerif-Regular.ttf`/`NotoSerif-Bold.ttf` —
    # confirmed live in a real translated PDF's font names too). This path
    # therefore points at the SAME font FILE (copied from babeldoc's own
    # asset cache into `fonts/`), not because we can make babeldoc use it,
    # but so `font_shrink_page`'s own redraws match babeldoc's rendering
    # instead of introducing a second, different font family on the page.
    # Verified full glyph coverage for the Vietnamese alphabet (146/146 test
    # chars incl. all tone-mark combinations) before switching to it.
    #
    # Previously "fonts/BeVietnamPro-Regular.ttf" (also OFL, also full
    # Vietnamese coverage) — switched away from it 2026-09-05: it was a
    # DIFFERENT font family than whatever babeldoc itself draws the rest of
    # the page with, which is exactly the kind of "measuring/redrawing
    # against a font different from what's already on the page" mismatch
    # this setting exists to prevent (see `font_shrink.py` module docstring).
    noto_font_path: str = "fonts/NotoSerif-Regular.ttf"

    log_level: str = "info"

    # PDF pipeline (Architecture.md 6.6.8) — provider mac dinh la DeepSeek: re nhat, ho
    # tro native qua pdf2zh -s deepseek, co context caching phia server (PRD US-14).
    default_provider: str = "deepseek"
    max_glossary_entries_in_prompt: int = 80
    pdf2zh_ignore_cache: bool = False
    pdf2zh_timeout_seconds: int = 3600
    # BR-FONT-03 (VI <= 130% EN) + he so token/ky tu tieng Viet co dau, dung trong
    # estimate_chunk_cost() (Architecture.md 6.6.6) — cost la UOC LUONG, khong phai so do dem.
    vi_expansion_factor: float = 1.3
    vi_token_factor: float = 1.5
    metering_proxy_enabled: bool = False

    # Financial Safety Lop 2 (Architecture.md 6.11.4) — su co $6.50 that
    # (2026-09-04, RC-3: "KHONG CO hard cap o bat ky lop nao"). Nguong nay
    # chan job/batch TRUOC KHI tao, dua tren estimate_job_cost_v2().
    max_cost_per_job_usd: float = 2.00
    max_cost_per_batch_usd: float = 5.00
    cost_cap_enabled: bool = True

    # AIMD concurrency controller (Architecture.md 6.12.6/6.12.8).
    adaptive_concurrency_enabled: bool = True
    # Kill switch — `.env`-only, NOT in SETTINGS_DB_OVERRIDABLE_FIELDS below:
    # a safe rollback if AIMD misbehaves in production, falls back to
    # ADAPTIVE_THREAD_FLOOR[provider] fixed for every chunk.
    ollama_thread: int = 2
    # Ollama has no AIMD (6.12.6 — no countable rate-limit signal exists for
    # a local model; throttling shows up as generic slowness/CPU-GPU-RAM
    # pressure, not a discrete event). Deliberate exception: IS in
    # SETTINGS_DB_OVERRIDABLE_FIELDS, because the right value depends on the
    # user's own hardware (VRAM/cores) — the app cannot infer or learn it.

    # Engine dich PDF (Architecture.md 6.14). Default doi sang "babeldoc"
    # 2026-09-05 sau QA gate 6.14.6 (PASS 8/8, xem docs/test-report.md): sua duoc
    # loi gop dong danh sach cua pdf2zh (31/35 vs 0/35) doi lay ~108x thoi gian
    # dich (do tren 1 file 25 trang, N=1 - AIMD constants babeldoc van con
    # ⚠️ ASSUMED). Nguoi dung chap nhan danh doi nay (quyet dinh Protocol 2).
    # "pdf2zh" van giu nguyen lam duong rollback - `.env`-only, KHONG vao
    # SETTINGS_DB_OVERRIDABLE_FIELDS: doi engine khong phai thao tac user thuong
    # lam tu UI, va rollback phai la 1 thao tac co chu dich (sua .env + restart).
    pdf_translate_engine: Literal["pdf2zh", "babeldoc"] = "babeldoc"
    babeldoc_executable: str = "babeldoc"

    # US-15 nhanh EPUB->Markdown, Architecture.md §6.15.7 muc C / §6.21.2:
    # bieu dien sup/sub trong `EpubDocument.to_markdown()` — "unicode" (mac
    # dinh, x2 -> "x²") hay "pandoc" (x^2^, cho user render bang Pandoc). Day
    # la lua chon bieu dien, KHONG phai tham so van hanh -> `.env`-only,
    # KHONG vao SETTINGS_DB_OVERRIDABLE_FIELDS.
    markdown_supsub_style: Literal["unicode", "pandoc"] = "unicode"
    # Architecture.md "Root Cause Analysis: Line-break/List Regression" (F1/F2,
    # 2026-09-06) + "Đo lại F1 trên nhiều trang — kết quả live A/B/C"
    # (2026-09-06, Tech Lech, 21 lan chay babeldoc+DeepSeek that qua dung
    # production code path, 7 trang x 3 cau hinh). `--split-short-lines`
    # KHONG con hardcode trong `BabeldocRunner.translate_pages()` — gio la 1
    # cap setting co the bat/tat + chinh factor.
    #
    # LICH SU QUYET DINH (2 lan doi, DUNG ca 2 lan deu dua tren do luong that,
    # khong doan — doc de hieu TAI SAO, dung xoa):
    # 1. F1/F2 lan dau (1 trang, 1 lan chay): tuong RC-1 (heuristic hinh hoc
    #    cua flag nay) gay hai LAN RONG cho doan van thuong tren ca trang ->
    #    chon mac dinh TAT (`False`/`0.5`) de an toan.
    # 2. Do lai tren 7 trang x 3 cau hinh (21 lan chay that, xem Architecture.md
    #    section "Đo lại F1 trên nhiều trang"): ket luan (1) SAI — KHONG mot
    #    doan van xuoi nao trong toan bo 7 trang bi tach vun o bat ky cau hinh
    #    nao; tac hai RC-1 that chi gioi han o caption bang/anh (2/7 trang, muc
    #    do nhe). Nguoc lai, BAT flag voi factor DUNG BANG default goc cua
    #    babeldoc (`0.8`) xu ly list/muc luc tot hon RO RET (vd trang list 35
    #    muc: 28 cho dinh chu -> con 3; trang muc luc: 7 loi dinh chu -> 0).
    #    factor `0.5` (cau hinh da ship o lan 1) la CAU HINH TE NHAT trong 3 —
    #    no giu gan het tac hai cua `False` (van dinh chu) MA van phai tra gan
    #    du gia RC-1 (van cat caption y het `0.8`) — ha factor de "giam
    #    false-positive" ho ra chu yeu giam TRUE-positive, chua tung do truoc
    #    khi chon o lan 1.
    #
    # -> Doi mac dinh production sang BAT + factor bang chinh default cua
    # babeldoc. `.env`-only nhu `pdf_translate_engine` o tren: day van la
    # gia tri co the rollback/tuy chinh co chu dich cho tung loai tai lieu,
    # khong phai thao tac UI thuong ngay.
    babeldoc_split_short_lines: bool = True
    # Chi co tac dung khi `babeldoc_split_short_lines=True`
    # (`paragraph_finder.py:891` dung ca 2 gia tri trong cung 1 dieu kien
    # `and`). Mac dinh BANG DUNG default goc cua babeldoc (VERIFIED
    # `babeldoc/main.py:184-189`) — do that (xem comment tren) cho thay day la
    # cau hinh TOT NHAT trong 3 da do, khong phai `0.5` (da ship truoc, do
    # SAI vi chua do truoc khi chon).
    babeldoc_short_line_split_factor: float = 0.8

    # Architecture.md "Final Decision: Babeldoc Layout Bug Fix Roadmap", U3/U4
    # P1.1 (G1e): babeldoc 0.6.4 silently drops any character whose line angle
    # falls outside 0/90 deg +-0.1 deg (`il_creater.py:968-974`, V-1 verified —
    # backend has no rotation field at all, so this is UX-C content-loss, not
    # a cosmetic issue). This flag gates the PyMuPDF `insert_text(morph=...)`
    # overlay step that re-draws that lost rotated text back onto the merged
    # babeldoc output (only ever runs when `pdf_translate_engine == "babeldoc"`
    # — pdf2zh does not drop rotated text, V-2 verified). `.env`-only like
    # `pdf_translate_engine` above, same rationale: an immediate rollback path
    # if the overlay step itself misbehaves on some future document, without
    # needing a UI round-trip.
    babeldoc_rotated_text_overlay: bool = True

    # Bug #7 fix (Architecture.md "Bug #7/#8 — Final Decision sau phản biện
    # Domain Expert", X5 D7-2): `sitecustomize.py` shim (`src/babeldoc_shim/`)
    # vá `ParagraphFinder._split_paragraph_into_lines` cua babeldoc 0.6.4 qua
    # PYTHONPATH cua subprocess — loai ky tu khoang trang khoi phep dem va
    # cham dung de tim khe giua 2 dong (giu nguyen nguong goc `count < 1`).
    # Khong bat buoc theo spec (khong yeu cau feature flag rieng), nhung giu
    # cung mau rollback tuc thi voi `babeldoc_rotated_text_overlay` o tren —
    # shim tu fail-safe (khong patch/khong crash) neu version babeldoc doi,
    # nhung co the tat het qua bien nay ma khong can deploy lai code.
    babeldoc_line_split_shim_enabled: bool = True

    # Bug #7 fix buoc 7.2 — Ca A (Architecture.md X5 D7-3, "7.2"): cung
    # `sitecustomize.py` shim tren, vá THEM `ParagraphFinder.process` de tach
    # paragraph tai cac dong mo dau bang marker numbered-list tang dan dung 1
    # don vi (vd "8." roi "9."), CHI chay SAU khi tang dong (7.1, o tren) da
    # xong — phu thuoc thu tu bat buoc, khong duoc dao (X5 D7-3). Doc lap voi
    # `babeldoc_line_split_shim_enabled`: co bien rollback rieng vi day la
    # heuristic moi hon, chua co lich su production (khac 7.1 da qua R6-03
    # live tren 11 trang) — tat rieng bien nay khi 7.1 van chay binh thuong.
    babeldoc_numbered_list_split_enabled: bool = True

    # Bug #7 fix buoc 7.4-b — Ca C (Architecture.md "Bug #7 Ca C — Quyet
    # dinh cuoi sau phan bien Domain Expert + ke hoach spike 7.4-a", AA5):
    # cung `sitecustomize.py` shim tren, vá THEM `ParagraphFinder.
    # process_independent_paragraphs` de tach paragraph gom nhieu muc muc
    # luc KHONG co dot-leader "du day" (< 20 cham) — TOC-1 v2. Doc lap voi
    # `babeldoc_numbered_list_split_enabled`: co bien rollback rieng vi day
    # la heuristic MOI NHAT/rui ro cao nhat trong ca 3.
    #
    # BAT mac dinh (`True`) tu ban release nay — dieu kien AA5 "chi bat sau
    # khi QA live xanh" da thoa (QA Vong 8, docs/test-report.md: PASS qua ca
    # BabeldocRunner truc tiep lan JobOrchestrator day du, live E2E that qua
    # DeepSeek tren 2 trang Contents that, 0 false-positive tren 8 trang doi
    # chung + 4 fixture hoi quy cua 7.1/7.2). Van giu bien
    # `BABELDOC_SHIM_TOC_SPLIT`/bien Settings nay nhu kill-switch doc lap —
    # tat duoc rieng TOC-1 v2 ma khong dong 7.1/7.2 neu phat sinh
    # false-positive that tren layout/sach chua tung gap trong 12 dump da do.
    babeldoc_toc_split_enabled: bool = True

    # Bug #10 (Architecture.md muc "Bug #10 — babeldoc cat ngang tu tieng
    # Viet giua chung"): cung `sitecustomize.py` shim tren nhung VA MODULE
    # KHAC (`typesetting`, giai doan dan trang) — fix
    # `Typesetting._get_width_before_next_break_point` dem doi be rong cua
    # chinh unit hien tai trong lookahead wrap. Doc lap hoan toan voi 3 co
    # tren (rollback rieng, khong phu thuoc thu tu — BA10.7).
    #
    # BAT mac dinh (`True`) — KHAC TOC-1 v2 (tung mac dinh TAT luc moi ra).
    # Ly do (BA10.8): day la fix SO HOC dung/sai (bo 1 phep cong thua), co
    # tinh chat an toan CAU TRUC chung minh duoc bang doc source
    # (`current_x + unit_width <= box.x2` nguyen ven sau vá — BA10.3-c), KHONG
    # phai heuristic doan y do layout can "chi bat sau khi QA live xanh" nhu
    # TOC-1 v2. Da qua spike A/B song (BA10.5, R5-02) truoc khi bat mac dinh
    # nay — xem docs/CHANGELOG.md muc Bug #10 cho ket qua 5 gate.
    babeldoc_word_wrap_fix_enabled: bool = True

    # US-20 "Cac tu moi" (Architecture.md 6.18.2, bang cau hinh CAP NHAT boi
    # 6.18.8 T5 — 4 field, khong con 3 nhu ban goc). Rule-based, $0, chay SAU
    # khi job completed (BR-TERM-01) — khong lien quan translation pipeline.
    term_extraction_enabled: bool = True
    # DA DOI Y NGHIA boi 6.18.8 T1: KHONG con la "tran chat luong" (spec goc
    # tung la 40) — gio la van chong tran DB thuan tuy. User da chot "chi
    # dieu kien loc la khong co trong glossary", khong tran so luong tuy y.
    # Default 20_000 (~4x worst-case do duoc tren sach 415 trang that,
    # Architecture.md 6.18.8 T0/T1). KHONG duoc ha xuong "cho gon".
    max_suggested_terms_per_job: int = 20_000
    # Ap dung cho tai lieu >= 50_000 token (dem theo token, KHONG theo trang
    # — total_pages la NULL cho EPUB theo dung thiet ke, 6.18.8 T5).
    term_min_occurrences: int = 3
    term_min_occurrences_short_doc: int = 2

    # US-22 EPUB chunking (Architecture.md 6.20.7 Z3): "ca 3 hang so phai nam
    # o Settings (.env), khong chon trong code". Gia tri mac dinh KHOP voi
    # module constant cung ten trong src/core/chunking.py (EPUB_CHUNK_CHAR_BUDGET
    # v.v.) — 2 noi ton tai co chu dich: hang so trong chunking.py la default
    # param cua plan_epub_chunks() (chay doc lap duoc trong test khong can
    # Settings), field o day la duong override qua .env cho luc wire that vao
    # Job Orchestrator (buoc 2/3 cua US-22, NGOAI PHAM VI increment nay).
    epub_chunk_char_budget: int = 8_000
    # Architecture.md §6.20.14.2 A-1 (2026-09-10) — ha tu 3.000 xuong 1.100 +
    # them tran unit moi, sau khi Protocol 3 cham gioi han (5/5 vong Dev<->QA)
    # vi DeepSeek lien tuc sinh JSON hong voi batch lon (docs/escalation-log.md).
    epub_request_char_budget: int = 1_100
    epub_request_max_units: int = 6
    epub_unit_hard_max_chars: int = 10_000
    # Architecture.md §6.20.14.4 C-2 (Lop C) — mirror EPUB_FALLBACK_MAX_RATIO_*
    # trong src/core/chunking.py, override qua .env giong pattern cac hang so
    # EPUB khac o tren.
    epub_fallback_max_ratio_chunk: float = 0.20
    epub_fallback_max_ratio_job: float = 0.05
    # Architecture.md 6.20.8: "chi la cho moc cho tuong lai" — buoc 2/3 nay
    # (`_process_epub_chunk()`) chay TUAN TU trong 1 chunk du bao nhieu, gia
    # tri nay CHUA duoc doc o dau ca. Ly do khong AIMD cho EPUB: app goi API
    # truc tiep (nhan RateLimitError THAT qua with_retry()), khac PDF/pdf2zh
    # phai *doan* tin hieu rate-limit tu stdout subprocess.
    epub_translate_concurrency: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()


#: Increment 5 design decision (docs/CHANGELOG.md "Increment 5"): the `PUT
#: /api/settings` endpoint lets the user set API keys through the web UI
#: instead of editing `.env` by hand. `Settings` itself stays a cached
#: `pydantic-settings` singleton read once from `.env` (`get_settings()`
#: above, unchanged) — DB-stored values are layered on top of it at read
#: time via this function, never mutated in place, so `get_settings()`
#: remains a pure `.env` snapshot for anything that doesn't need DB access
#: (e.g. `Pdf2zhServiceMapper` unit tests). Only fields a user would
#: plausibly want to change from the UI are overridable; everything else
#: (chunking, cost heuristics, etc.) stays `.env`/code-only.
SETTINGS_DB_OVERRIDABLE_FIELDS: frozenset[str] = frozenset(
    {
        "claude_api_key",
        "claude_model",
        "openai_api_key",
        "openai_base_url",
        "openai_model",
        "deepseek_api_key",
        "deepseek_base_url",
        "deepseek_model",
        "gemini_api_key",
        "gemini_model",
        "deepl_api_key",
        "ollama_endpoint",
        "ollama_model",
        "ollama_thread",
        "default_provider",
        "max_concurrent_files",
        "max_cost_per_job_usd",
        "max_cost_per_batch_usd",
        "cost_cap_enabled",
        "term_extraction_enabled",
        "max_suggested_terms_per_job",
        "term_min_occurrences",
        "term_min_occurrences_short_doc",
    }
)


def _cast_setting_value(raw: str, current: object) -> object:
    """Cast a DB-stored string back to the type `Settings` declares for that
    field. `bool` must be checked before `int` — `bool` is an `int` subclass
    in Python, so `isinstance(current, int)` alone would wrongly stringify a
    bool field back into `int(raw)`.
    """
    if isinstance(current, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


async def get_effective_settings(session: "AsyncSession") -> Settings:
    """`get_settings()` (.env) with any DB-stored overrides from the
    `settings` table layered on top. Call this instead of `get_settings()`
    anywhere a DB session is already available and the caller cares about
    user-configured API keys/provider choice (job execution, cost estimate,
    the settings endpoints themselves) — see docs/CHANGELOG.md "Increment 5"
    for why this exists instead of writing directly into the cached
    `Settings` singleton.
    """
    from sqlmodel import select

    from src.models.settings import Setting

    base = get_settings()
    result = await session.exec(select(Setting))
    rows = {row.key: row.value for row in result.all() if row.key in SETTINGS_DB_OVERRIDABLE_FIELDS}
    if not rows:
        return base

    data = base.model_dump()
    for key, raw_value in rows.items():
        data[key] = _cast_setting_value(raw_value, data[key])
    return Settings(**data)
