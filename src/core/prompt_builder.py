"""Build translation prompts (Architecture.md sections 6.2, 6.6.4/6.6.5).

Two distinct outputs live here, matching the "out-of-band vs render path"
split from Architecture.md 6.6.2 R1/R3:

- `build_system_prompt()` — a single string, passed as `system_prompt=` to
  `TranslationProvider.translate()` for the OUT-OF-BAND uses that remain
  after Increment 4's fix (cost estimation, Settings "test connection",
  sample preview — never the real PDF render path).
- `write_prompt_file()` — writes the `--prompt <path>` FILE pdf2zh reads and
  re-substitutes (`${lang_in}`/`${lang_out}`/`${text}` via `string.Template`)
  for every segment of the real render. This is the ONLY place glossary/unit
  rules reach the actual translated output (Architecture.md 6.6.2 R2).
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

_CONCISENESS_RULE = (
    "2. Dich suc tich, MUC TIEU la <=130% do dai ban goc tieng Anh (khong phai gioi han "
    "cung). Doan nhieu y (vd danh sach nhieu muc): uu tien dich DAY DU, KHONG duoc bo sot "
    "muc nao chi de dat muc tieu do dai."
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

_FILE_CONCISENESS_RULE = (
    "Dich suc tich, MUC TIEU la <=130% do dai ban goc ${lang_in} (khong phai gioi han "
    "cung). Doan nhieu y (vd danh sach nhieu muc): uu tien dich DAY DU, KHONG duoc bo sot "
    "muc nao chi de dat muc tieu do dai."
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
