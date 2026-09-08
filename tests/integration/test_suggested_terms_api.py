"""US-20 "Các từ mới" — `/api/glossary/suggested*` (Architecture.md §6.18.4)."""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.deps import get_db_session
from src.api.main import app
from src.api.routes import glossary as glossary_route
from src.models.job import Job
from src.models.suggested_term import SuggestedTerm
from src.services.translation import TranslationResult


@pytest.fixture
async def db() -> AsyncIterator[tuple[TestClient, async_sessionmaker[AsyncSession]]]:
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    with TestClient(app) as test_client:
        yield test_client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_job_and_terms(
    session_factory: async_sessionmaker[AsyncSession], rows: list[SuggestedTerm]
) -> None:
    async with session_factory() as session:
        session.add(
            Job(
                id="job1",
                filename="book.pdf",
                file_path="unused.pdf",
                file_size=1,
                file_hash="h",
                file_type="pdf_digital",
                model="deepseek",
                status="completed",
            )
        )
        for row in rows:
            session.add(row)
        await session.commit()


def _term(**overrides: object) -> SuggestedTerm:
    defaults: dict[str, object] = {
        "job_id": "job1",
        "term_en": "laminated dough",
        "match_key": "laminated dough",
        "ngram_size": 2,
        "noise_flags": "",
        "occurrence_count": 5,
        "rank_score": 3.0,
        "status": "pending",
    }
    defaults.update(overrides)
    return SuggestedTerm(**defaults)


@pytest.mark.asyncio
async def test_list_suggested_defaults_to_pending_and_hides_noise(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(
        session_factory,
        [
            _term(term_en="laminated dough", match_key="laminated dough", rank_score=3.0),
            _term(
                term_en="cauvain", match_key="cauvain", rank_score=1.0, noise_flags="proper_noun"
            ),
            _term(term_en="already added", match_key="already added", status="added"),
        ],
    )

    response = client.get("/api/glossary/suggested")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2  # both pending rows count toward total (noise included)
    assert body["noise_hidden_count"] == 1
    terms = [e["term_en"] for e in body["entries"]]
    assert terms == ["laminated dough"]  # noisy one hidden by default


@pytest.mark.asyncio
async def test_list_suggested_include_noise_shows_everything(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(
        session_factory,
        [
            _term(term_en="laminated dough", match_key="laminated dough", rank_score=3.0),
            _term(
                term_en="cauvain", match_key="cauvain", rank_score=1.0, noise_flags="proper_noun"
            ),
        ],
    )

    response = client.get("/api/glossary/suggested", params={"include_noise": "true"})
    assert response.status_code == 200
    body = response.json()
    assert {e["term_en"] for e in body["entries"]} == {"laminated dough", "cauvain"}


@pytest.mark.asyncio
async def test_list_suggested_min_ngram_filters_1grams(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(
        session_factory,
        [
            _term(term_en="flour", match_key="flour", ngram_size=1, rank_score=5.0),
            _term(
                term_en="laminated dough", match_key="laminated dough", ngram_size=2, rank_score=3.0
            ),
        ],
    )

    response = client.get("/api/glossary/suggested", params={"min_ngram": 2})
    assert response.status_code == 200
    body = response.json()
    assert [e["term_en"] for e in body["entries"]] == ["laminated dough"]


@pytest.mark.asyncio
async def test_list_suggested_sort_alpha_and_count(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(
        session_factory,
        [
            _term(term_en="zabaglione", match_key="zabaglione", rank_score=1.0, occurrence_count=2),
            _term(
                term_en="apricot glaze",
                match_key="apricot glaze",
                rank_score=2.0,
                occurrence_count=9,
            ),
        ],
    )

    alpha = client.get("/api/glossary/suggested", params={"sort": "alpha"}).json()
    assert [e["term_en"] for e in alpha["entries"]] == ["apricot glaze", "zabaglione"]

    by_count = client.get("/api/glossary/suggested", params={"sort": "count"}).json()
    assert [e["term_en"] for e in by_count["entries"]] == ["apricot glaze", "zabaglione"]


@pytest.mark.asyncio
async def test_list_suggested_job_id_scoping(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(
        session_factory,
        [_term(job_id="job1", term_en="laminated dough")],
    )
    async with session_factory() as session:
        session.add(
            Job(
                id="job2",
                filename="book2.pdf",
                file_path="unused2.pdf",
                file_size=1,
                file_hash="h2",
                file_type="pdf_digital",
                model="deepseek",
                status="completed",
            )
        )
        session.add(_term(job_id="job2", term_en="apricot glaze", match_key="apricot glaze"))
        await session.commit()

    scoped = client.get("/api/glossary/suggested", params={"job_id": "job1"}).json()
    assert [e["term_en"] for e in scoped["entries"]] == ["laminated dough"]

    all_jobs = client.get("/api/glossary/suggested").json()
    assert {e["term_en"] for e in all_jobs["entries"]} == {"laminated dough", "apricot glaze"}


@pytest.mark.asyncio
async def test_dismiss_hides_from_pending_listing(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(session_factory, [_term()])
    listing = client.get("/api/glossary/suggested").json()
    suggested_id = listing["entries"][0]["id"]

    dismiss_response = client.post(f"/api/glossary/suggested/{suggested_id}/dismiss")
    assert dismiss_response.status_code == 204

    after = client.get("/api/glossary/suggested").json()
    assert after["entries"] == []
    dismissed = client.get("/api/glossary/suggested", params={"status": "dismissed"}).json()
    assert len(dismissed["entries"]) == 1


@pytest.mark.asyncio
async def test_promote_creates_glossary_entry_and_marks_added(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(session_factory, [_term(term_en="laminated dough")])
    listing = client.get("/api/glossary/suggested").json()
    suggested_id = listing["entries"][0]["id"]

    response = client.post(
        f"/api/glossary/suggested/{suggested_id}/promote",
        json={"term_vi": "bot cuon lop", "notes": "tu goi y"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["term_en"] == "laminated dough"
    assert body["term_vi"] == "bot cuon lop"

    glossary_list = client.get("/api/glossary").json()
    assert any(e["term_en"] == "laminated dough" for e in glossary_list["entries"])

    after = client.get("/api/glossary/suggested").json()
    assert after["entries"] == []
    added = client.get("/api/glossary/suggested", params={"status": "added"}).json()
    assert len(added["entries"]) == 1


@pytest.mark.asyncio
async def test_promote_rejects_non_pending_row(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(session_factory, [_term(status="dismissed")])
    async with session_factory() as session:
        from sqlmodel import select

        row = (await session.exec(select(SuggestedTerm))).first()
        assert row is not None
        suggested_id = row.id

    response = client.post(f"/api/glossary/suggested/{suggested_id}/promote", json={"term_vi": "x"})
    assert response.status_code == 400


class _FakeProvider:
    def __init__(self, response_text: str, cost: float = 0.0004) -> None:
        self._response_text = response_text
        self._cost = cost
        self.calls: list[str] = []

    async def translate(
        self, text: str, glossary_prompt: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        self.calls.append(text)
        return TranslationResult(
            text=self._response_text,
            input_tokens=20,
            output_tokens=10,
            estimated_cost_usd=self._cost,
            provider_name="fake",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0


@pytest.mark.asyncio
async def test_suggest_translation_writes_vi_and_cost_never_touches_job(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session_factory = db
    await _seed_job_and_terms(
        session_factory,
        [
            _term(term_en="laminated dough", match_key="laminated dough"),
            _term(term_en="apricot glaze", match_key="apricot glaze"),
        ],
    )
    listing = client.get("/api/glossary/suggested").json()
    ids = [e["id"] for e in listing["entries"]]
    assert len(ids) == 2

    fake_provider = _FakeProvider(
        response_text='{"laminated dough": "bot cuon lop", "apricot glaze": "(keep)"}'
    )
    monkeypatch.setattr(
        glossary_route.ProviderFactory,
        "create",
        classmethod(lambda cls, name, settings: fake_provider),
    )

    response = client.post("/api/glossary/suggested/suggest-translation", json={"ids": ids})
    assert response.status_code == 200
    body = response.json()
    assert body["updated"] == 2
    assert body["total_cost_usd"] == pytest.approx(0.0004)
    assert len(fake_provider.calls) == 1  # both terms batched into ONE LLM request

    after = client.get("/api/glossary/suggested").json()
    by_term = {e["term_en"]: e for e in after["entries"]}
    assert by_term["laminated dough"]["suggested_term_vi"] == "bot cuon lop"
    assert by_term["apricot glaze"]["suggested_term_vi"] == "(keep)"
    assert by_term["laminated dough"]["translation_cost_usd"] == pytest.approx(0.0002)

    # Architecture.md §6.18.4: KHONG cong vao job.actual_cost.
    job_detail = client.get("/api/jobs/job1").json()
    assert job_detail["actual_cost"] is None


@pytest.mark.asyncio
async def test_suggest_translation_batches_at_most_40_terms_per_llm_request(
    db: tuple[TestClient, async_sessionmaker[AsyncSession]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session_factory = db
    rows = [
        _term(term_en=f"term {i}", match_key=f"term {i}", occurrence_count=i + 1) for i in range(45)
    ]
    await _seed_job_and_terms(session_factory, rows)
    listing = client.get("/api/glossary/suggested", params={"limit": 100, "min_ngram": 2}).json()
    ids = [e["id"] for e in listing["entries"]]
    assert len(ids) == 45

    fake_provider = _FakeProvider(response_text="{}", cost=0.001)
    monkeypatch.setattr(
        glossary_route.ProviderFactory,
        "create",
        classmethod(lambda cls, name, settings: fake_provider),
    )

    response = client.post("/api/glossary/suggested/suggest-translation", json={"ids": ids})
    assert response.status_code == 200
    assert len(fake_provider.calls) == 2  # 40 + 5, never more than 40 per call
