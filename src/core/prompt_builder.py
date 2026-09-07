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

from pathlib import Path

from src.core.glossary_manager import GlossaryManager
from src.utils.unit_conversion_table import build_unit_conversion_section

_INTRO = (
    "Ban la chuyen gia dich thuat tai lieu nganh banh. "
    "Dich tu tieng Anh sang tieng Viet.\n\n"
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
    glossary_manager: GlossaryManager, project_id: str | None = None
) -> str:
    """Trả về full system prompt string ghép glossary + unit conversion + style rules."""
    glossary_snippet = await glossary_manager.build_prompt_snippet(project_id=project_id)
    if not glossary_snippet:
        glossary_snippet = "(Khong co glossary entry nao duoc cau hinh.)"

    sections = [
        _INTRO,
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

_BABELDOC_INTRO = (
    "Ban la chuyen gia dich thuat tai lieu nganh banh. Dich tu tieng Anh sang tieng Viet."
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
) -> str:
    """Build babeldoc's `--custom-system-prompt` CONTENT (no template syntax,
    no `${text}`/footer — see module docstring and the contract note above).
    Mirrors `build_prompt_text()`'s glossary-filtering/unit-hint logic so both
    engines get the same glossary/unit coverage, just packaged for babeldoc's
    different substitution contract.
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

    sections = [_BABELDOC_INTRO, "", glossary_block]
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
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
