import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.glossary import Glossary, GlossaryEntry
from src.utils.excel_utils import GlossaryEntryData

logger = logging.getLogger(__name__)

_KEEP_MARKERS = {"", "(keep)"}


def _project_scope(project_id: str) -> str:
    return f"project:{project_id}"


def _count_occurrences(term: str, haystack: str) -> int:
    """Case-insensitive, word-boundary occurrence count used by the document
    glossary filter (Architecture.md 6.6.5)."""
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    return len(pattern.findall(haystack))


@dataclass
class ImportResult:
    imported: int
    updated: int
    skipped: int


class GlossaryManager:
    """CRUD + import/export + prompt building for glossary entries.

    Implements PRD business rules BR-GLOSS-01 to BR-GLOSS-06.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_or_create_glossary(self, scope: str) -> Glossary:
        result = await self._session.exec(select(Glossary).where(Glossary.scope == scope))
        glossary = result.first()
        if glossary is not None:
            return glossary

        glossary = Glossary(name=scope, scope=scope)
        self._session.add(glossary)
        await self._session.flush()
        return glossary

    async def get_entry(self, term: str, project_id: str | None = None) -> GlossaryEntry | None:
        """BR-GLOSS-02: case-insensitive EN match.
        BR-GLOSS-06: project glossary overrides global when project_id is given.
        """
        normalized = term.strip()

        if project_id is not None:
            project_entry = await self._find_entry_in_scope(normalized, _project_scope(project_id))
            if project_entry is not None:
                return project_entry

        return await self._find_entry_in_scope(normalized, "global")

    async def _find_entry_in_scope(self, term: str, scope: str) -> GlossaryEntry | None:
        statement = (
            select(GlossaryEntry)
            .join(Glossary, Glossary.id == GlossaryEntry.glossary_id)
            .where(Glossary.scope == scope)
            .where(func.lower(GlossaryEntry.term_en) == term.lower())
        )
        result = await self._session.exec(statement)
        return result.first()

    async def bulk_import(
        self, entries: list[GlossaryEntryData], scope: str, project_id: str | None
    ) -> ImportResult:
        """BR-GLOSS-03: on duplicate term, last-updated-wins (we simply overwrite on import,
        which is always the most recent write).
        """
        target_scope = _project_scope(project_id) if project_id else scope
        glossary = await self._get_or_create_glossary(target_scope)

        imported = 0
        updated = 0
        skipped = 0

        for entry_data in entries:
            term_en = entry_data.term_en.strip()
            if not term_en:
                skipped += 1
                continue

            existing = await self._find_entry_in_scope(term_en, target_scope)
            if existing is not None:
                existing.term_vi = entry_data.term_vi
                existing.notes = entry_data.notes
                existing.updated_at = datetime.now(UTC)
                self._session.add(existing)
                updated += 1
            else:
                new_entry = GlossaryEntry(
                    glossary_id=glossary.id,
                    term_en=term_en,
                    term_vi=entry_data.term_vi,
                    notes=entry_data.notes,
                )
                self._session.add(new_entry)
                imported += 1

        glossary.entry_count = await self._count_entries(glossary.id)
        glossary.updated_at = datetime.now(UTC)
        self._session.add(glossary)

        await self._session.commit()
        return ImportResult(imported=imported, updated=updated, skipped=skipped)

    async def _count_entries(self, glossary_id: str) -> int:
        statement = (
            select(func.count())
            .select_from(GlossaryEntry)
            .where(GlossaryEntry.glossary_id == glossary_id)
        )
        result = await self._session.exec(statement)
        return result.one()

    async def build_prompt_snippet(
        self,
        project_id: str | None = None,
        only_terms_present_in: str | None = None,
        max_entries: int | None = None,
    ) -> str:
        """Build the Markdown glossary table injected into the translation prompt,
        matching the format designed in Architecture.md section 6.2.

        `only_terms_present_in`/`max_entries` implement Architecture.md 6.6.5:
        pdf2zh sends the prompt file to every segment individually (not once per
        job), so an unfiltered glossary multiplies input tokens by the segment
        count. When `only_terms_present_in` is given (the full extracted EN text
        of the document), only entries whose `term_en` actually occurs in it
        (case-insensitive, word-boundary match) are kept; when the result still
        exceeds `max_entries`, the highest-frequency entries win and the rest are
        dropped with a warning log (caller surfaces this to the job/user).
        """
        entries_by_term: dict[str, GlossaryEntry] = {}

        global_entries = await self._list_entries_in_scope("global")
        for entry in global_entries:
            entries_by_term[entry.term_en.lower()] = entry

        if project_id is not None:
            project_entries = await self._list_entries_in_scope(_project_scope(project_id))
            for entry in project_entries:
                entries_by_term[entry.term_en.lower()] = entry

        if not entries_by_term:
            return ""

        ordered = sorted(entries_by_term.values(), key=lambda e: e.term_en.lower())

        if only_terms_present_in is not None:
            frequencies = {
                entry.id: _count_occurrences(entry.term_en, only_terms_present_in)
                for entry in ordered
            }
            ordered = [entry for entry in ordered if frequencies[entry.id] > 0]

            if max_entries is not None and len(ordered) > max_entries:
                dropped = len(ordered) - max_entries
                logger.warning(
                    "Glossary vuot tran: %d entry xuat hien trong tai lieu, gioi han %d -> "
                    "chi giu %d entry co tan suat cao nhat, bo %d entry.",
                    len(ordered),
                    max_entries,
                    max_entries,
                    dropped,
                )
                ordered = sorted(ordered, key=lambda e: frequencies[e.id], reverse=True)[
                    :max_entries
                ]
                ordered.sort(key=lambda e: e.term_en.lower())
        elif max_entries is not None and len(ordered) > max_entries:
            logger.warning(
                "Glossary vuot tran: %d entry, gioi han %d -> chi giu %d entry dau tien.",
                len(ordered),
                max_entries,
                max_entries,
            )
            ordered = ordered[:max_entries]

        if not ordered:
            return ""

        lines = ["| EN | VI |", "|---|---|"]
        for entry in ordered:
            term_vi = entry.term_vi
            if term_vi is None or term_vi.strip().lower() in _KEEP_MARKERS:
                lines.append(f"| {entry.term_en} | (keep) - GIU NGUYEN tieng Anh |")
            else:
                lines.append(f"| {entry.term_en} | {term_vi} |")

        return "\n".join(lines)

    async def _list_entries_in_scope(self, scope: str) -> list[GlossaryEntry]:
        statement = (
            select(GlossaryEntry)
            .join(Glossary, Glossary.id == GlossaryEntry.glossary_id)
            .where(Glossary.scope == scope)
        )
        result = await self._session.exec(statement)
        return list(result.all())
