from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.glossary_manager import GlossaryManager
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
async def test_bulk_import_creates_entries(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    entries = [
        GlossaryEntryData(term_en="ganache", term_vi="(keep)"),
        GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo"),
    ]

    result = await manager.bulk_import(entries, scope="global", project_id=None)

    assert result.imported == 2
    assert result.updated == 0
    assert result.skipped == 0


@pytest.mark.asyncio
async def test_bulk_import_updates_existing_term_last_write_wins(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="buttercream", term_vi="kem bo")],
        scope="global",
        project_id=None,
    )

    result = await manager.bulk_import(
        [GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo")],
        scope="global",
        project_id=None,
    )

    assert result.imported == 0
    assert result.updated == 1

    entry = await manager.get_entry("buttercream")
    assert entry is not None
    assert entry.term_vi == "kem phu bo"


@pytest.mark.asyncio
async def test_get_entry_case_insensitive(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="Fondant", term_vi="(keep)")],
        scope="global",
        project_id=None,
    )

    entry = await manager.get_entry("fONDANT")

    assert entry is not None
    assert entry.term_en == "Fondant"


@pytest.mark.asyncio
async def test_get_entry_project_overrides_global(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="fold", term_vi="tron deu")],
        scope="global",
        project_id=None,
    )
    await manager.bulk_import(
        [GlossaryEntryData(term_en="fold", term_vi="gap banh")],
        scope="global",
        project_id="batch-123",
    )

    project_entry = await manager.get_entry("fold", project_id="batch-123")
    assert project_entry is not None
    assert project_entry.term_vi == "gap banh"

    global_entry = await manager.get_entry("fold", project_id=None)
    assert global_entry is not None
    assert global_entry.term_vi == "tron deu"

    other_project_entry = await manager.get_entry("fold", project_id="batch-999")
    assert other_project_entry is not None
    assert other_project_entry.term_vi == "tron deu"


@pytest.mark.asyncio
async def test_get_entry_not_found_returns_none(session: AsyncSession) -> None:
    manager = GlossaryManager(session)

    entry = await manager.get_entry("nonexistent")

    assert entry is None


@pytest.mark.asyncio
async def test_build_prompt_snippet_format(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [
            GlossaryEntryData(term_en="ganache", term_vi="(keep)"),
            GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo"),
            GlossaryEntryData(term_en="fondant", term_vi=None),
        ],
        scope="global",
        project_id=None,
    )

    snippet = await manager.build_prompt_snippet()

    lines = snippet.splitlines()
    assert lines[0] == "| EN | VI |"
    assert lines[1] == "|---|---|"
    assert "| buttercream | kem phu bo |" in snippet
    assert "| ganache | (keep) - GIU NGUYEN tieng Anh |" in snippet
    assert "| fondant | (keep) - GIU NGUYEN tieng Anh |" in snippet


@pytest.mark.asyncio
async def test_build_prompt_snippet_project_overrides_global_entry(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="fold", term_vi="tron deu")],
        scope="global",
        project_id=None,
    )
    await manager.bulk_import(
        [GlossaryEntryData(term_en="fold", term_vi="gap banh")],
        scope="global",
        project_id="batch-123",
    )

    snippet = await manager.build_prompt_snippet(project_id="batch-123")

    assert "| fold | gap banh |" in snippet
    assert "tron deu" not in snippet


@pytest.mark.asyncio
async def test_build_prompt_snippet_empty_glossary(session: AsyncSession) -> None:
    manager = GlossaryManager(session)

    snippet = await manager.build_prompt_snippet()

    assert snippet == ""


@pytest.mark.asyncio
async def test_build_prompt_snippet_filters_to_terms_present_in_document(
    session: AsyncSession,
) -> None:
    """Architecture.md 6.6.5: pdf2zh resends the prompt file per segment, so an
    unfiltered glossary multiplies input tokens — only terms that actually
    occur in the document's extracted text should be kept."""
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [
            GlossaryEntryData(term_en="ganache", term_vi="(keep)"),
            GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo"),
            GlossaryEntryData(term_en="fondant", term_vi=None),
        ],
        scope="global",
        project_id=None,
    )

    document_text = "This recipe uses ganache and buttercream frosting throughout."
    snippet = await manager.build_prompt_snippet(only_terms_present_in=document_text)

    assert "| ganache |" in snippet
    assert "| buttercream | kem phu bo |" in snippet
    assert "fondant" not in snippet


@pytest.mark.asyncio
async def test_build_prompt_snippet_word_boundary_not_substring(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="oat", term_vi="yen mach")],
        scope="global",
        project_id=None,
    )

    # "oat" is a substring of "coating" but should NOT match as the whole word "oat".
    snippet = await manager.build_prompt_snippet(only_terms_present_in="apply a thin coating")

    assert snippet == ""


@pytest.mark.asyncio
async def test_build_prompt_snippet_no_terms_present_returns_empty(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [GlossaryEntryData(term_en="ganache", term_vi="(keep)")],
        scope="global",
        project_id=None,
    )

    snippet = await manager.build_prompt_snippet(only_terms_present_in="a document about cars")

    assert snippet == ""


@pytest.mark.asyncio
async def test_build_prompt_snippet_caps_at_max_entries_by_frequency(
    session: AsyncSession,
) -> None:
    """Hard cap (default 80 in Settings) — when more terms occur than the cap
    allows, the highest-frequency terms win."""
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [
            GlossaryEntryData(term_en="ganache", term_vi="(keep)"),
            GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo"),
            GlossaryEntryData(term_en="fondant", term_vi="(keep)"),
        ],
        scope="global",
        project_id=None,
    )

    document_text = "ganache ganache ganache buttercream fondant"
    snippet = await manager.build_prompt_snippet(only_terms_present_in=document_text, max_entries=2)

    entry_lines = snippet.splitlines()[2:]  # skip "| EN | VI |" header + "|---|---|" separator
    assert len(entry_lines) == 2
    assert any("ganache" in line for line in entry_lines)


@pytest.mark.asyncio
async def test_build_prompt_snippet_max_entries_without_filter(session: AsyncSession) -> None:
    manager = GlossaryManager(session)
    await manager.bulk_import(
        [
            GlossaryEntryData(term_en="ganache", term_vi="(keep)"),
            GlossaryEntryData(term_en="buttercream", term_vi="kem phu bo"),
        ],
        scope="global",
        project_id=None,
    )

    snippet = await manager.build_prompt_snippet(max_entries=1)

    entry_lines = snippet.splitlines()[2:]  # skip "| EN | VI |" header + "|---|---|" separator
    assert len(entry_lines) == 1
