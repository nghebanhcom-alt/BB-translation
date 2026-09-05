import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.glossary_manager import GlossaryManager
from src.core.prompt_builder import build_system_prompt, write_prompt_file
from src.utils.excel_utils import GlossaryEntryData


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_system_prompt_contains_all_required_sections(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="ganache", term_vi="(keep)")],
        scope="global",
        project_id=None,
    )

    prompt = await build_system_prompt(manager)

    # Glossary table.
    assert "ganache" in prompt
    assert "| EN | VI |" in prompt

    # Unit conversion table (BR-UNIT-01/02/03).
    assert "cups" in prompt
    assert "°F" in prompt
    assert "Bot mi (flour)" in prompt

    # Conciseness rule (BR-FONT-03): a target, not a hard cap that licenses
    # dropping content — regression for the v1.2.2 bug where a dense
    # numbered list got silently truncated by the model to satisfy a
    # conciseness rule phrased as an absolute constraint.
    assert "130%" in prompt
    assert "MUC TIEU" in prompt
    assert "KHONG duoc bo sot" in prompt

    # Typography/structure preservation (BR-TYPO-01..04).
    assert "heading" in prompt
    assert "bullet" in prompt or "numbered list" in prompt
    assert "Bold, italic" in prompt
    assert "Indentation" in prompt


@pytest.mark.asyncio
async def test_system_prompt_handles_empty_glossary(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    prompt = await build_system_prompt(manager)
    assert "Khong co glossary entry" in prompt
    assert "130%" in prompt


@pytest.mark.asyncio
async def test_write_prompt_file_contains_template_tokens(
    session: AsyncSession, tmp_path: Path
) -> None:
    """Architecture.md 6.6.4: pdf2zh's `--prompt` reads a FILE and applies
    `string.Template` itself with `${lang_in}`/`${lang_out}`/`${text}` — the
    file must literally contain these tokens, not pre-substituted values."""
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="ganache", term_vi="(keep)")],
        scope="global",
        project_id=None,
    )

    path = tmp_path / "job-1" / "prompt.txt"
    result_path = await write_prompt_file(
        manager, path=path, only_terms_present_in="a ganache cake"
    )

    assert result_path == path
    content = path.read_text(encoding="utf-8")
    assert "${lang_in}" in content
    assert "${lang_out}" in content
    assert content.endswith("Source Text: ${text}\nTranslated Text:")
    assert "ganache" in content
    # Same v1.2.2 regression guard as the out-of-band system prompt above,
    # but for the FILE contract pdf2zh/babeldoc actually read per segment.
    assert "MUC TIEU" in content
    assert "KHONG duoc bo sot" in content


@pytest.mark.asyncio
async def test_write_prompt_file_escapes_stray_dollar_signs(
    session: AsyncSession, tmp_path: Path
) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="butter", term_vi="bo (gia $5/kg)")],
        scope="global",
        project_id=None,
    )

    path = tmp_path / "prompt.txt"
    await write_prompt_file(manager, path=path, only_terms_present_in="butter")

    content = path.read_text(encoding="utf-8")
    # Every literal "$" from glossary content must be doubled to "$$" (safe_substitute
    # rule, Architecture.md 6.6.4 point 3) — check no LONE "$" survives (a template
    # var like ${lang_in} is fine, a bare "$5" is not).
    assert "$$5" in content
    assert not re.search(r"(?<!\$)\$(?!\$)(?!\{)", content)


@pytest.mark.asyncio
async def test_write_prompt_file_skips_unit_conversion_when_no_hints(
    session: AsyncSession, tmp_path: Path
) -> None:
    manager = GlossaryManager(session)
    path = tmp_path / "prompt.txt"

    await write_prompt_file(manager, path=path, only_terms_present_in="a pure theory chapter")

    content = path.read_text(encoding="utf-8")
    assert "cups" not in content


@pytest.mark.asyncio
async def test_write_prompt_file_includes_unit_conversion_when_hints_present(
    session: AsyncSession, tmp_path: Path
) -> None:
    manager = GlossaryManager(session)
    path = tmp_path / "prompt.txt"

    await write_prompt_file(manager, path=path, only_terms_present_in="2 cups flour")

    content = path.read_text(encoding="utf-8")
    assert "cups" in content


@pytest.mark.asyncio
async def test_write_prompt_file_caps_glossary_entries(
    session: AsyncSession, tmp_path: Path
) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [
            GlossaryEntryData(term_en="ganache", term_vi="(keep)"),
            GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo"),
        ],
        scope="global",
        project_id=None,
    )

    path = tmp_path / "prompt.txt"
    await write_prompt_file(
        manager,
        path=path,
        only_terms_present_in="ganache buttercream",
        max_glossary_entries=1,
    )

    content = path.read_text(encoding="utf-8")
    table_lines = [line for line in content.splitlines() if line.startswith("| ")]
    entry_lines = [line for line in table_lines if line not in ("| EN | VI |", "|---|---|")]
    assert len(entry_lines) == 1
