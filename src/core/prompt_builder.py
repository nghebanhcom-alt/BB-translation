"""Build translation prompts (Architecture.md sections 6.2, 6.6.4/6.6.5).

Three distinct outputs live here, matching the "out-of-band vs render path"
split from Architecture.md 6.6.2 R1/R3:

- `build_system_prompt()` — a single string, passed as `system_prompt=` to
  `TranslationProvider.translate()`. Originally written for the OUT-OF-BAND
  uses only (cost estimation, Settings "test connection", sample preview) —
  but as of P1.1 (G1e), `job_orchestrator.py` also calls this SAME function
  to build `glossary_prompt` for `overlay_rotated_text()`'s per-block LLM
  calls, and THAT result is drawn straight into `translated_vi.pdf`, the
  file handed to the user. So "never the real PDF render path" is no longer
  literally true for every caller of this function — read it as "the shape
  this function returns matches a single `translate()` system_prompt call,
  not pdf2zh/babeldoc's own file-template contract", not as "safe to change
  without affecting what the user sees".
- `write_prompt_file()` — writes the `--prompt <path>` FILE pdf2zh reads and
  re-substitutes (`${lang_in}`/`${lang_out}`/`${text}` via `string.Template`)
  for every segment of the real render. This is the ONLY place glossary/unit
  rules reach the actual translated output when engine == pdf2zh
  (Architecture.md 6.6.2 R2).
- `write_babeldoc_prompt_file()` — writes the CONTENT passed verbatim (no
  template substitution) as babeldoc's `--custom-system-prompt <string>`.
  MUST NOT reuse `write_prompt_file()`'s content: babeldoc has no
  `string.Template` mechanism for this value (verified against installed
  babeldoc 0.6.4 source, `il_translator_llm_only.py`) and appends its OWN
  Structure Rules + mandatory per-paragraph JSON output contract right after
  this string. Feeding it pdf2zh's `${text}`/"only print the translation"
  content produces a system prompt with two contradicting protocols, which
  was the confirmed root cause of babeldoc silently dropping paragraphs
  (root-cause investigation, 2026-09-05).
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.core.glossary_manager import GlossaryManager
from src.utils.unit_conversion_table import build_unit_conversion_section

#: Architecture.md §6.26.6 (S7 — dich FR->VI) — bang du lieu, KHONG re nhanh
#: `if lang == ...` rai rac trong than ham. `source_lang` khong khop key nao
#: (khong nen xay ra — moi noi doc `job.source_lang or "en"`) roi ve "en".
_SOURCE_LANG_NAME_VI: dict[str, str] = {"en": "tieng Anh", "fr": "tieng Phap"}


def _source_lang_name(source_lang: str) -> str:
    return _SOURCE_LANG_NAME_VI.get(source_lang, _SOURCE_LANG_NAME_VI["en"])


def _intro(source_lang: str) -> str:
    return (
        "Ban la chuyen gia dich thuat tai lieu nganh banh. "
        f"Dich tu {_source_lang_name(source_lang)} sang tieng Viet.\n\n"
        "QUY TAC BAT BUOC:"
    )


_GLOSSARY_INSTRUCTION = (
    '1. Dich cac thuat ngu theo bang duoi day. Neu cot VI la "(keep)" hoac trong, '
    "GIU NGUYEN tieng Anh:"
)

#: BR-FONT-03 (Architecture.md U4/P1.2, chot lai sau khi Tech Lead tu nhan ban cu SAI):
#: ban cu ghi "<=130% do dai ban goc" — dau da ghi ro "khong phai gioi han cung", con so
#: phan tram trong prompt van du de LLM tu suy dien thanh gioi han cung va LUOC BO dinh
#: luong (bug thuc te da xay ra, xem CHANGELOG "Increment 2026-09-05"). Ban chot KHONG
#: dua BAT KY con so phan tram/ky tu gioi han do dai nao vao prompt nua — ty le do dai chi
#: la METRIC DO SAU (cost_estimator.py), khong phai chi thi cho LLM. Chot chan chat luong
#: thuc su la gate P0.1-e (`src/services/layout_qa.py`), khong phai loi hua cua prompt nay.
#: Ngan gon co chu dich (xem ghi chu ben tren + CHANGELOG "Increment 2026-09-05"
#: ve rui ro `prompt_overhead_chars` nhan voi segment_count trong cost_estimator.py
#: day cost estimate vuot cost cap — moi lan sua rule nay PHAI kiem tra lai do dai).
_CONCISENESS_RULE = (
    "2. BAT BIEN NOI DUNG: giu du so, don vi, nhiet do, thoi gian, ten nguyen lieu, so buoc — "
    "TUYET DOI KHONG bo/gop/lam tron dinh luong. Con lai uu tien van phong CO DONG. Danh sach "
    "nhieu muc: dich DAY DU, KHONG duoc bo sot muc nao."
)

_TYPOGRAPHY_RULES = (
    "4. Giu nguyen typography va cau truc tai lieu (BR-TYPO-01 den BR-TYPO-04):\n"
    "   - Font size / cap heading (H1, H2, H3...) phai giu dung ty le tuong duong ban goc, "
    "khong tu y doi cap.\n"
    "   - Bullet list phai dich thanh bullet list, numbered list phai dich thanh numbered "
    "list. Khong flatten list thanh doan van hay nguoc lai.\n"
    "   - Bold, italic, underline va cac text decoration khac phai giu nguyen vi tri "
    "tuong ung trong ban dich.\n"
    "   - Indentation level cua nested list/sub-items phai giu nguyen cap bac so voi ban goc."
)


async def build_system_prompt(
    glossary_manager: GlossaryManager,
    project_id: str | None = None,
    only_terms_present_in: str | None = None,
    max_glossary_entries: int = 80,
    source_lang: str = "en",
) -> str:
    """Trả về full system prompt string ghép glossary + unit conversion + style rules.

    `only_terms_present_in`/`max_glossary_entries` mirror `build_prompt_text()`'s
    glossary filter (Architecture.md 6.6.5/6.20.9 sợi dây thứ 4): khi được truyền
    (full EN text của tài liệu), glossary chỉ giữ lại entry thực sự xuất hiện
    trong `only_terms_present_in`, cap ở `max_glossary_entries`. Mặc định
    `None` giữ nguyên hành vi CŨ (glossary KHÔNG lọc) cho các caller hiện có
    (`overlay_rotated_text`'s `glossary_prompt`) — chỉ EPUB (`run_epub_job()`)
    truyền `only_terms_present_in` để khớp đúng cách `cost_gate.py` đã lọc khi
    ước chi phí Lớp 2 (§6.11.6: prompt thật và prompt dùng để ước chi phí phải
    cùng một tập glossary, nếu không Lớp 2 có thể ước THẤP hơn thật).

    `source_lang` (S7, Architecture.md §6.26.6): mặc định "en" giữ NGUYÊN
    chuỗi CŨ byte-for-byte (test regression bắt buộc) — đổi độ dài chuỗi này
    đổi `prompt_overhead_chars` × `segment_count` = đổi cost estimate của MỌI
    job EN đang chạy. `"fr"` nội suy tên ngôn ngữ qua `_intro()`.
    """
    glossary_snippet = await glossary_manager.build_prompt_snippet(
        project_id=project_id,
        only_terms_present_in=only_terms_present_in,
        max_entries=max_glossary_entries,
    )
    if not glossary_snippet:
        glossary_snippet = "(Khong co glossary entry nao duoc cau hinh.)"

    sections = [
        _intro(source_lang),
        _GLOSSARY_INSTRUCTION,
        "",
        glossary_snippet,
        "",
        _CONCISENESS_RULE,
        "",
        build_unit_conversion_section(),
        "",
        _TYPOGRAPHY_RULES,
    ]
    return "\n".join(sections)


# === pdf2zh `--prompt <file>` contract (Architecture.md 6.6.4) ===
#
# `string.Template.safe_substitute` is what pdf2zh applies to this file per
# segment — every `$` that is NOT one of `${lang_in}`/`${lang_out}`/`${text}`
# must be escaped to `$$`, or a stray `$` in glossary/doc content could be
# misread as a template reference (6.6.4 point 3).

_FILE_INTRO = (
    "Ban la chuyen gia dich thuat tai lieu nganh banh. Dich tu ${lang_in} sang ${lang_out}.\n"
    "Chi in ra ban dich, khong them bat ky loi dan hay giai thich nao.\n"
    "Giu nguyen moi placeholder dang {{v0}}, {{v1}}... o dung vi tri cua chung."
)

_FILE_GLOSSARY_INSTRUCTION = (
    'Dich cac thuat ngu theo bang duoi day. Neu cot VI la "(keep)" hoac trong, '
    "GIU NGUYEN tieng Anh:"
)

_FILE_NO_GLOSSARY = "(Khong co glossary entry nao ap dung cho tai lieu nay.)"

#: Cung quyet dinh U4/P1.2 nhu `_CONCISENESS_RULE` o tren — KHONG con con so phan tram
#: nao trong noi dung file nay (day la file pdf2zh THUC SU doc + gui lai MOI segment,
#: nen cang phai ngan gon — `prompt_overhead_chars` trong cost_estimator.py nhan voi
#: segment_count, xem CHANGELOG "Increment 2026-09-05").
_FILE_CONCISENESS_RULE = (
    "BAT BIEN NOI DUNG: giu du so, don vi, nhiet do, thoi gian, ten nguyen lieu, so buoc — "
    "TUYET DOI KHONG bo/gop/lam tron dinh luong. Con lai uu tien van phong CO DONG. Danh sach "
    "nhieu muc: dich DAY DU, KHONG duoc bo sot muc nao."
)

_FILE_TYPOGRAPHY_RULES = (
    "Giu nguyen typography va cau truc tai lieu: font size/cap heading, bullet/numbered "
    "list, bold/italic/underline, va indentation level cua nested list phai giu dung vi tri "
    "va cap bac tuong ung ban goc."
)

_FILE_FOOTER = "Source Text: ${text}\nTranslated Text:"

#: Content hints that trigger inclusion of the unit-conversion block (6.6.5:
#: "chi chen khi phat hien noi dung cong thuc" — a pure-theory document doesn't
#: need it, and it costs input tokens on every segment like everything else here).
_UNIT_HINTS = ("cup", "tbsp", "tsp", "oz", "°f", "inch")


def _escape_dollar(text: str) -> str:
    return text.replace("$", "$$")


def _has_unit_conversion_hint(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _UNIT_HINTS)


async def build_prompt_text(
    glossary_manager: GlossaryManager,
    project_id: str | None = None,
    only_terms_present_in: str | None = None,
    max_glossary_entries: int = 80,
) -> str:
    """Build the pdf2zh `--prompt` file CONTENT (Architecture.md 6.6.4/6.6.5)
    without writing it to disk. Extracted out of `write_prompt_file()`
    (Architecture.md 6.11.4 Lop 1, point 2) so the Lop 2 pre-flight cost gate
    (`src/core/cost_gate.py`) can measure the REAL prompt length — including
    this document's filtered glossary — before a Job exists, instead of
    assuming a constant. A constant here is exactly RC-1 of the $6.50
    incident (Architecture.md 6.11.3): a full glossary swells the prompt
    ~3.4x, and a fixed estimate would silently miss that.
    """
    glossary_snippet = await glossary_manager.build_prompt_snippet(
        project_id=project_id,
        only_terms_present_in=only_terms_present_in,
        max_entries=max_glossary_entries,
    )
    if not glossary_snippet:
        glossary_block = _FILE_NO_GLOSSARY
    else:
        glossary_block = f"{_FILE_GLOSSARY_INSTRUCTION}\n\n{_escape_dollar(glossary_snippet)}"

    include_units = (
        _has_unit_conversion_hint(only_terms_present_in)
        if only_terms_present_in is not None
        else True
    )
    unit_block = _escape_dollar(build_unit_conversion_section()) if include_units else ""

    sections = [_FILE_INTRO, "", glossary_block]
    if unit_block:
        sections += ["", unit_block]
    sections += ["", _FILE_CONCISENESS_RULE, "", _FILE_TYPOGRAPHY_RULES, "", _FILE_FOOTER]

    content = "\n".join(sections)

    if "${text}" not in content:
        # Should be unreachable (${text} is in the static footer) — guards
        # against a future edit silently dropping it (6.6.4 point 1: pdf2zh
        # would then never receive the source text to translate).
        raise ValueError(
            "Prompt file thieu ${text} placeholder — pdf2zh se khong nhan noi dung goc."
        )

    return content


async def write_prompt_file(
    glossary_manager: GlossaryManager,
    path: Path,
    project_id: str | None = None,
    only_terms_present_in: str | None = None,
    max_glossary_entries: int = 80,
) -> Path:
    """Write the pdf2zh `--prompt` file for one job (Architecture.md 6.6.4/6.6.5).

    Built ONCE per job and reused for every chunk (Job Orchestrator step 5) so
    the translation stays consistent across chunk boundaries and the pdf2zh
    cache key (`translate_engine_params` includes `prompt`, 6.6.1 F8) stays
    stable. `only_terms_present_in` should be the full EN text extracted from
    the document (PyMuPDF) — passing it filters the glossary down to terms
    that actually occur, capped at `max_glossary_entries` (6.6.5).

    pdf2zh ONLY — do not reuse this file's content for babeldoc, see
    `write_babeldoc_prompt_file()`.
    """
    content = await build_prompt_text(
        glossary_manager,
        project_id=project_id,
        only_terms_present_in=only_terms_present_in,
        max_glossary_entries=max_glossary_entries,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# === babeldoc `--custom-system-prompt <string>` contract ===
#
# Passed through by BabeldocRunner VERBATIM as the LLM system prompt's
# `role_block` — no `string.Template` substitution happens on this value
# (verified against installed babeldoc 0.6.4 source,
# `il_translator_llm_only.py`). babeldoc appends its own Structure Rules and
# mandatory per-paragraph JSON array output contract right after this string,
# so this content must NOT contain `${...}` template syntax (never
# substituted — would reach the LLM as a literal, confusing token) nor any
# instruction that contradicts babeldoc's JSON contract (e.g. "print only the
# translation, no other output" — directly conflicts with "respond with a
# JSON array"). babeldoc also documents its own placeholder syntax (`{v1}`,
# single-brace) to the LLM already, so this content omits pdf2zh's
# double-brace `{{v0}}` placeholder hint, which uses a different convention.


def _babeldoc_intro(source_lang: str) -> str:
    #: §6.26.6: noi dung babeldoc KHONG duoc chua `${...}` (khong co co che
    #: template) — nen noi tinh ten ngon ngu tai thoi diem build bang Python
    #: f-string, KHAC voi `_FILE_INTRO` (pdf2zh, giu `${lang_in}` de pdf2zh
    #: tu thay the).
    return (
        "Ban la chuyen gia dich thuat tai lieu nganh banh. "
        f"Dich tu {_source_lang_name(source_lang)} sang tieng Viet."
    )


_BABELDOC_GLOSSARY_INSTRUCTION = (
    'Dich cac thuat ngu theo bang duoi day. Neu cot VI la "(keep)" hoac trong, '
    "GIU NGUYEN tieng Anh:"
)

_BABELDOC_NO_GLOSSARY = "(Khong co glossary entry nao ap dung cho tai lieu nay.)"

#: Cung quyet dinh U4/P1.2 — KHONG con con so phan tram nao (day la noi dung babeldoc
#: gui thang cho LLM lam system prompt, khong qua string.Template). Ngan gon co chu dich
#: nhu 2 bien the tren — `prompt_overhead_chars` (cost_estimator.py) dung DUNG do dai
#: chuoi nay cho engine babeldoc, nhan voi segment_count.
_BABELDOC_CONCISENESS_RULE = (
    "BAT BIEN NOI DUNG: giu du so, don vi, nhiet do, thoi gian, ten nguyen lieu, so buoc — "
    "TUYET DOI KHONG bo/gop/lam tron dinh luong. Con lai uu tien van phong CO DONG. Danh sach "
    "nhieu muc: dich DAY DU, KHONG duoc bo sot muc nao."
)

#: F4 (Architecture.md "Root Cause Analysis: Line-break/List Regression",
#: RC-3, 2026-09-06): KHAC voi `_TYPOGRAPHY_RULES`/`_FILE_TYPOGRAPHY_RULES`
#: o tren (noi LLM thay CA mot khoi list), babeldoc goi LLM dich TUNG
#: PARAGRAPH DA TACH SAN boi `paragraph_finder.py` (VERIFIED nguon babeldoc
#: 0.6.4 da cai, `il_translator_llm_only.py`) — 1 fragment co the chi la 1
#: cau hoac 1 phan cua 1 muc list, khong phai ca khoi. Chi thi "bullet list
#: phai dich thanh bullet list" o cac bien the khac, ap dung vao 1 fragment
#: da bi cat roi, khien LLM co xu huong TU THEM lai bullet/newline vao
#: fragment khong con ky tu bullet nao — va vi babeldoc chi `.strip()` 2 dau
#: (KHONG loai newline noi bo, `il_translator_llm_only.py:718,987,998`),
#: newline do LLM tu them song sot vao output. Bien the nay noi ro nguoc
#: lai: dich DUNG MOT doan, KHONG tu chen newline, KHONG tu them
#: bullet/so thu tu neu ban goc khong co san.
_BABELDOC_TYPOGRAPHY_RULES = (
    "Giu nguyen typography (font size/cap heading, bold/italic/underline). LUU Y RIENG: "
    "doan van ban nhan duoc la MOT fragment DON LE ma he thong da tu tach san — co the la "
    "ca 1 cau, 1 muc trong danh sach, hoac chi MOT PHAN cua 1 muc (khong phai ca khoi danh "
    "sach). Dich thanh DUNG MOT doan van lien tuc; TUYET DOI KHONG tu chen ky tu xuong dong "
    "vao giua ban dich. Neu dau fragment goc DA CO SAN ky tu bullet/so thu tu (vd '•', '-', "
    "'1.'), giu nguyen dung ky tu do o dau ban dich; neu KHONG co, TUYET DOI KHONG tu them "
    "bullet/so thu tu moi — cau truc danh sach do he thong tu quan ly o buoc khac, khong "
    "phai o day."
)


async def build_babeldoc_prompt_text(
    glossary_manager: GlossaryManager,
    project_id: str | None = None,
    only_terms_present_in: str | None = None,
    max_glossary_entries: int = 80,
    source_lang: str = "en",
) -> str:
    """Build babeldoc's `--custom-system-prompt` CONTENT (no template syntax,
    no `${text}`/footer — see module docstring and the contract note above).
    Mirrors `build_prompt_text()`'s glossary-filtering/unit-hint logic so both
    engines get the same glossary/unit coverage, just packaged for babeldoc's
    different substitution contract.

    `source_lang` (S7, Architecture.md §6.26.6): mặc định "en" giữ NGUYÊN
    chuỗi CŨ byte-for-byte — xem `build_system_prompt()` cho lý do (cost
    estimate của mọi job EN đang chạy).
    """
    glossary_snippet = await glossary_manager.build_prompt_snippet(
        project_id=project_id,
        only_terms_present_in=only_terms_present_in,
        max_entries=max_glossary_entries,
    )
    glossary_block = (
        f"{_BABELDOC_GLOSSARY_INSTRUCTION}\n\n{glossary_snippet}"
        if glossary_snippet
        else _BABELDOC_NO_GLOSSARY
    )

    include_units = (
        _has_unit_conversion_hint(only_terms_present_in)
        if only_terms_present_in is not None
        else True
    )
    unit_block = build_unit_conversion_section() if include_units else ""

    sections = [_babeldoc_intro(source_lang), "", glossary_block]
    if unit_block:
        sections += ["", unit_block]
    sections += ["", _BABELDOC_CONCISENESS_RULE, "", _BABELDOC_TYPOGRAPHY_RULES]

    return "\n".join(sections)


async def write_babeldoc_prompt_file(
    glossary_manager: GlossaryManager,
    path: Path,
    project_id: str | None = None,
    only_terms_present_in: str | None = None,
    max_glossary_entries: int = 80,
    source_lang: str = "en",
) -> Path:
    """Write babeldoc's `--custom-system-prompt` CONTENT to disk for one job.

    `BabeldocRunner.translate_pages()` reads this file's TEXT and passes it as
    the flag's STRING value (unlike pdf2zh's `--prompt <path>`) — writing to
    disk here only lets Job Orchestrator reuse the same "build once per job,
    reuse per chunk" pattern as `write_prompt_file()`. babeldoc ONLY — do not
    use for pdf2zh, see `write_prompt_file()`.
    """
    content = await build_babeldoc_prompt_text(
        glossary_manager,
        project_id=project_id,
        only_terms_present_in=only_terms_present_in,
        max_glossary_entries=max_glossary_entries,
        source_lang=source_lang,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# === EPUB batch JSON contract app<->LLM (Architecture.md 6.20.12 X4) ===
#
# Neither pdf2zh's `${text}` template NOR babeldoc's own per-paragraph JSON
# contract applies here — US-22 (buoc 2/3) calls `provider.translate()`
# DIRECTLY (Architecture.md 6.20.4: "khong dung bilingual_book_maker o bat ky
# dau"), and `provider.translate(text, glossary_prompt, src, tgt)`'s
# signature is a FIXED cross-provider interface (Increment 3, 5 providers) —
# it CANNOT be changed just for EPUB. So the JSON contract below lives
# ENTIRELY inside the `glossary_prompt`/`system_prompt` argument; the actual
# payload (the JSON array of units to translate) goes into `text`, which every
# provider prefixes with "Translate from {src} to {tgt}:\n\n" — harmless, and
# arguably helpful since it states the task plainly.
#
# `build_epub_batch_prompt()` does NOT call `build_system_prompt()` itself —
# the caller (Job Orchestrator) already has ITS OWN `glossary_prompt` (from
# `build_system_prompt()`, filtered to this EPUB's `full_text()`) and passes
# it straight through UNCHANGED, per Architecture.md 6.20.12 X4: "glossary_prompt
# hien co — khong sua mot chu".

#: Literal marker a test can `in`-check for in the exact string handed to
#: `provider.translate()` (R6-02, Architecture.md 6.20.9 sợi dây thứ 4) —
#: proof the REAL system_prompt sent for an EPUB chunk came from THIS
#: function, not the bare `build_system_prompt()` (which has no JSON
#: instruction at all — verified: none of prompt_builder.py's other "json"
#: hits are app-authored content, they're comments describing babeldoc's OWN
#: contract).
EPUB_BATCH_CONTRACT_MARKER = "BB-EPUB-JSON-CONTRACT-X4"

_EPUB_BATCH_CONTRACT = f"""
{EPUB_BATCH_CONTRACT_MARKER}
Ban se nhan 1 JSON array cac doi tuong dang {{"id": "<so>", "html": "<doan HTML can dich>"}}.
Tra ve DUY NHAT 1 JSON object dang {{"<id>": "<ban dich tieng Viet>", ...}}:
1. Object tra ve phai co DAY DU va DUNG moi "id" da nhan duoc trong array dau vao — khong duoc \
thieu id nao, khong duoc them id la khong co trong dau vao.
2. TUYET DOI KHONG boc JSON trong markdown code fence (vi du ```json), va KHONG kem theo bat ky \
loi dan/giai thich nao khac ngoai chinh JSON object do.
3. Chi dich phan TEXT; GIU NGUYEN tung the HTML inline sau day dung nguyen ten, dung so luong va \
dung vi tri tuong doi so voi ban goc: strong, em, b, i, sup, sub, br, a, span, small.
4. TUYET DOI KHONG doi, khong lam tron, khong chuyen doi bat ky CON SO nao trong "html". The \
<sup>/<sub> (dung cho phan so, vi du <sup>1</sup>/<sub>3</sub>) phai giu nguyen la <sup>/<sub>, \
khong duoc rut gon/gop lai.
5. KHONG dich noi dung nam trong the <code> hoac <pre> — giu nguyen nhu ban goc.
6. Neu 1 muc khong the dich duoc, tra ve NGUYEN VAN "html" cua chinh muc do cho dung "id" ay — \
TUYET DOI KHONG tra ve chuoi rong cho bat ky "id" nao.
7. Ban dich PHAI la tieng Viet CO DAU day du (Unicode NFC). TUYET DOI KHONG tra ve tieng Viet \
khong dau (vi du: phai la "bột mì", KHONG duoc la "bot mi").
""".strip()

# Architecture.md 6.20.13.4 (fix Bug #EPUB-4, V-1): ban truoc cua vi du one-shot
# nay co phan "Dau ra" la tieng Viet KHONG DAU ("bot mi", "muoi", "nuong o") —
# vi day la thu model bat chuoc MANH NHAT, no tu day model bo dau. Sua thanh
# co dau day du (NFC) — GIU NGUYEN phan "Dau vao" (tieng Anh).
_EPUB_BATCH_ONE_SHOT_EXAMPLE = (
    "Vi du (co the inline, con so, va phan so <sup>/<sub>):\n"
    'Dau vao: [{"id": "0", "html": "<strong>2 cups</strong> flour, '
    '1<sup>1</sup>/<sub>3</sub> tsp salt, bake at 350F."}]\n'
    'Dau ra: {"0": "<strong>2 cups</strong> bột mì, '
    '1<sup>1</sup>/<sub>3</sub> tsp muối, nướng ở 350F."}'
)


def build_epub_batch_prompt(glossary_prompt: str) -> str:
    """Architecture.md 6.20.12 X4 — noi `glossary_prompt` HIEN CO (khong sua
    1 chu) voi khoi contract JSON + 1 vi du one-shot. Dung cho MOI request
    LLM cua US-22 buoc 2/3 (`_process_epub_chunk()`), thay `build_system_prompt()`
    tran (khong co chi thi JSON nao — xac nhan lai o docstring section nay).
    """
    sections = [glossary_prompt, _EPUB_BATCH_CONTRACT, _EPUB_BATCH_ONE_SHOT_EXAMPLE]
    return "\n\n".join(sections)


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class EpubBatchResponseError(ValueError):
    """Raised only when the caller cannot proceed at all (currently unused —
    `parse_epub_batch_response()` is deliberately tolerant, see its
    docstring — kept as a named exception for a future stricter mode)."""


@dataclass(frozen=True)
class EpubParseOutcome:
    """Architecture.md §6.20.14.3 B-3 — telemetry cho parse 1 response EPUB.

    `strict_ids`: id lay duoc qua duong JSON chuan (`_decode_concatenated_json_objects()`).
    `salvaged_ids`: id CHI lay duoc nho lop cuu ho `_salvage_epub_id_pairs()` (B-1/B-2)
    — id nam trong `strict_ids` KHONG bao gio trung voi id trong `salvaged_ids` (mot id
    da co ket qua tu duong chuan thi khong bao gio bi salvage ghi de, xem B-2).
    `salvaged_count > 0` la tin hieu suc khoe: model van dang sinh JSON hong, chi la
    da cuu duoc — dung de `_process_epub_chunk()` ghi vao `requests.jsonl` va canh bao.
    """

    translations: dict[str, str]
    strict_ids: frozenset[str]
    salvaged_ids: frozenset[str]


#: Architecture.md §6.20.14.3 B-1 — lop cuu ho SAU parser chat hien co, KHONG
#: thay the no. Bat bien nen tang (khac han 3 fix B2-3/B2-4/B2-5 truoc, tat ca
#: deu gia dinh "response la N gia tri JSON HOP LE noi voi nhau"): moi ban dich
#: LUON xuat hien duoi dang 1 cap `"<id>": "<chuoi JSON hop le>"`, id nam trong
#: tap id ngan cuc bo da gui di — KHONG gia dinh gi ve dau ngoac/dau phay/cau
#: truc long nhau xung quanh cap do.
#: Chi khop khoa la ID NGAN CUC BO app tu sinh ("0".."999", da du du cho batch
#: <= EPUB_REQUEST_MAX_UNITS) — khong bao gio khop mot chuoi bat ky trong noi
#: dung dich (id that su cua unit_id EPUB co dang "doc_href#ordinal", khong
#: bao gio la thuan so nam trong dau nhay ngay truoc dau ":").
_EPUB_ID_PAIR_RE = re.compile(r'"(\d{1,3})"\s*:\s*"')


def _salvage_epub_id_pairs(text: str, expected_ids: set[str]) -> dict[str, str]:
    """Quet `text` tim moi cap `"<id>": "<chuoi>"` voi id thuoc `expected_ids`,
    decode gia tri BANG CHINH `json.decoder.scanstring` (khong phai regex) —
    escape (`\\"`, `\\n`, `\\uXXXX`) duoc xu ly dung y het JSON that; chuoi
    cut/escape hong thi `scanstring` raise va cap do bi bo qua, khong bao gio
    "doan". Con tro LUON tien toi `end` sau moi lan an thanh cong (khong bao
    gio quet lai BEN TRONG mot gia tri da lay) — mot doan `"12": "` nam TRONG
    noi dung ban dich (vi du unit chua chinh cau truc JSON lam vi du) khong
    the tao ra 1 cap gia vi con tro da di qua no. Trung khoa: cai SAU trong
    text thang (dong bo voi ngu nghia `dict.update()` cua parser chat).
    """
    out: dict[str, str] = {}
    pos = 0
    while (match := _EPUB_ID_PAIR_RE.search(text, pos)) is not None:
        try:
            value, end = json.decoder.scanstring(text, match.end())
        except (ValueError, json.JSONDecodeError):
            pos = match.end()
            continue
        pos = end
        key = match.group(1)
        if key in expected_ids and value.strip():
            out[key] = value
    return out


def parse_epub_batch_response_detailed(raw_text: str, expected_ids: set[str]) -> EpubParseOutcome:
    """Nhu `parse_epub_batch_response()` nhung tra ve them telemetry
    (Architecture.md §6.20.14.3 B-3) phan biet id lay duoc qua duong JSON
    chuan (`strict_ids`) voi id CHI cuu duoc nho lop salvage (`salvaged_ids`,
    §6.20.14.3 Lop B). Response lanh (moi id deu qua duoc parser chat) khong
    bao gio kich hoat nhanh salvage — `len(result) < len(expected_ids)` la
    False ngay tu dau, nen zero regression risk cho duong di thuong.
    """
    text = _CODE_FENCE_RE.sub("", raw_text.strip()).strip()
    data = _decode_concatenated_json_objects(text)

    result: dict[str, str] = {}
    strict_ids: set[str] = set()
    for key, value in data.items():
        str_key = str(key)
        if str_key not in expected_ids:
            continue
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if not stripped:
            continue
        result[str_key] = value
        strict_ids.add(str_key)

    salvaged_ids: set[str] = set()
    if len(result) < len(expected_ids):
        for key, value in _salvage_epub_id_pairs(text, expected_ids).items():
            if key in result:
                # KHONG BAO GIO de len gia tri da parse chat (B-2) — duong
                # chuan luon thang neu ca 2 deu tim thay cung 1 id.
                continue
            result[key] = value
            salvaged_ids.add(key)

    return EpubParseOutcome(
        translations=result,
        strict_ids=frozenset(strict_ids),
        salvaged_ids=frozenset(salvaged_ids),
    )


def parse_epub_batch_response(raw_text: str, expected_ids: set[str]) -> dict[str, str]:
    """Architecture.md 6.20.12 X4 — parse the LLM's reply to an
    `build_epub_batch_prompt()`-shaped request. MUST tolerate a real-world
    imperfect reply, not just the happy path (this exact tolerance is why
    Protocol 5 requires a GOLDEN FIXTURE captured from a real call —
    `tests/fixtures/epub_llm/` — rather than a hand-written mock of what we
    assume the model does):
    - strips a ```` ```json ... ``` ```` fence and surrounding whitespace/prose
      if present;
    - a value that is missing, not a string, or empty after `.strip()` is
      treated exactly like a MISSING id (never returned) — Architecture.md
      6.20.12 X4 point 6: "tuyet doi khong tra chuoi rong", so an empty
      string reaching this far must be re-requested exactly like an absent
      key, not written into `translations`;
    - an id NOT in `expected_ids` is silently dropped (a model hallucinating
      an extra id is not, by itself, a reason to fail the whole batch — the
      caller only cares whether every EXPECTED id got a usable value);
    - a response that isn't valid JSON at all (or whose top level isn't a
      JSON object) returns `{}` — every id counts as missing, so the caller's
      existing "missing id -> retry individually, still missing -> chunk
      failed" path (Architecture.md 6.20.8) handles it uniformly instead of
      needing a separate "totally malformed" branch;
    - a reply that is one or more genuinely well-formed top-level JSON
      OBJECTS concatenated back-to-back (`json.loads()` on the whole string
      fails with "Extra data") is MERGED, not truncated to the first object.
      Two real-world shapes confirmed so far, both handled by the SAME
      general loop (`json.JSONDecoder().raw_decode()` repeated over the
      remainder of the string, skipping only whitespace between objects):
        1. Bug fixed 2026-09-09 (`deepseek_batch_response_sourdough_ch1_trailing_garbage.json`):
           1 well-formed object + 1 stray `"` after the closing `}` — the
           "second object" never parses, so the loop naturally degrades to
           "keep the first object, drop the trailing garbage" (this is now
           just the N=1 case of the general loop, not a separate branch).
        2. Bug #EPUB-B2-3 (QA vong 2/5, 2026-09-10): DeepSeek splits a single
           batch reply into SEVERAL separate top-level JSON objects (one or
           more ids each), e.g. `{"0": "..."}\n{"1": "..."}\n...\n{"10": "..."}`
           instead of 1 object with 11 keys. The OLD code kept only the
           FIRST object and silently discarded every id in the rest — real,
           already-translated, already-PAID-FOR content — which then made
           the id-level retry (C-1) fail identically (DeepSeek reproduces
           the same split on retry), permanently failing the whole chunk
           (E-09) despite every id actually being translated correctly.
      When two merged objects share the same key, the LATER one in the text
      wins (plain `dict.update()` semantics, in text order) — no evidence
      seen of DeepSeek repeating a key with a WORSE answer the second time,
      and this keeps the merge trivially simple; revisit only if a real case
      ever shows the opposite.
      A chunk of the tail that is genuine garbage (not parseable JSON at
      all) stops the loop there and is dropped — everything parsed BEFORE
      it is still kept (this is the "dung sai" tolerance philosophy above,
      not a relaxation that accepts junk as data: junk after the last valid
      object is ignored, junk is never invented or guessed at).
    - Architecture.md §6.20.14.3 (Lop B, sau khi cham gioi han Protocol 3 voi
      Bug #EPUB-B2-5 — response chi co 1 dau `{` nhung nhieu dau `}` thua, gay
      "khong con `{`/`[` nao de tim tiep" cho thuat toan tren): NEU sau khi
      parse chat con thieu id, thu them lop cuu ho `_salvage_epub_id_pairs()`
      truoc khi coi la thieu that su — xem `parse_epub_batch_response_detailed()`.

    Returns only `{id: text}` pairs that passed validation — the caller
    computes `expected_ids - returned.keys()` to find what still needs a
    single-id retry.
    """
    return parse_epub_batch_response_detailed(raw_text, expected_ids).translations


#: Bug #EPUB-B2-4 (test-report.md, QA vong 3/5, 2026-09-10): fix B2-3 chi skip
#: whitespace giua 2 object — DeepSeek cung duoc quan sat noi 2 object bang dau
#: phay (`}, {`), khien fix cu dung lai ngay tai dau phay (khong phai whitespace)
#: va chi giu duoc object dau tien. Day la 1 HO LOI TONG QUAT hon ("model tra ve
#: nhieu JSON value roi rac, noi voi nhau bang BAT KY ky tu phan cach nao — chua
#: chac chi 2 bien the newline/phay da quan sat duoc la duy nhat"), khong phai 1
#: ky tu phan cach cu the — nen fix nay khong con giu danh sach ky tu phan cach
#: hop le, ma tim thang vi tri bat dau 1 JSON value tiep theo (`{` hoac `[`, 2 ky
#: tu duy nhat co the mo dau object/array hop le) bo qua TOAN BO moi thu nam giua
#: 2 object (whitespace, dau phay, hay bat ky rac gi khac).
_NEXT_JSON_VALUE_START_RE = re.compile(r"[{\[]")


def _decode_concatenated_json_objects(text: str) -> dict:
    """Decode `text` as 1+ top-level JSON values concatenated back-to-back,
    merging every dict found via `dict.update()` in text order (later key
    wins). Non-dict top-level values are skipped (kept out of the merge,
    same as the old "not a dict" check).

    Giua 2 object khong bat buoc CHI co whitespace nua (xem Bug #EPUB-B2-4):
    sau khi decode xong 1 object tai vi tri `end`, ta tim vi tri `{`/`[` gan
    nhat trong phan con lai (`_NEXT_JSON_VALUE_START_RE`) — bo qua whitespace,
    dau phay, hay bat ky ky tu phan cach nao khac model chen vao — roi thu
    `raw_decode()` tiep tu do. Neu khong tim thay `{`/`[` nao nua, hoac decode
    tai vi tri tim duoc THAT BAI, dung lai NGAY (khong tim tiep 1 vi tri `{`
    khac xa hon) va giu nguyen nhung gi da parse duoc — day la "dung sai co
    chu dich" (chap nhan ky tu phan cach la), khong phai noi long de doan/dung
    rac thanh du lieu that. Truong hop pho bien nhat (response chi co dung 1
    object) khong doi hanh vi: `raw_decode()` tieu thu het chuoi, vong lap
    dung o dieu kien `pos >= length` nhu cu.
    """
    decoder = json.JSONDecoder()
    merged: dict = {}
    pos = 0
    length = len(text)
    found_any = False
    # Chi lan dau tien, cho phep whitespace dan dau truoc gia tri JSON dau
    # tien (khop hanh vi cu — KHONG strip prose/rac dan dau, chi whitespace).
    while pos < length and text[pos].isspace():
        pos += 1
    while pos < length:
        try:
            obj, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            break
        found_any = True
        if isinstance(obj, dict):
            merged.update(obj)
        pos = end
        if pos >= length:
            break
        match = _NEXT_JSON_VALUE_START_RE.search(text, pos)
        if match is None:
            break
        pos = match.start()
    if not found_any:
        return {}
    return merged
