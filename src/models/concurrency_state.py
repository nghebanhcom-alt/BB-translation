from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ConcurrencyState(SQLModel, table=True):
    """Muc `--thread` da hoc duoc cho 1 bo (engine, provider, model). Architecture.md 6.12/6.14.5.

    Learned runtime state, KHONG phai user config: app tu ghi sau moi chunk.
    Khoa ghep (engine, provider, model) — Architecture.md 6.14.5: `rate_limit_hits`
    cua babeldoc KHONG cung don vi voi cua pdf2zh (SDK openai ben trong babeldoc
    tu nuot ~3 lan 429 truoc khi tenacity thay duoc, xem
    `BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR`), nen state hoc duoc tu engine nay
    KHONG duoc dung cho engine kia — doi flag sang babeldoc ma van dung chung
    key se ke thua `current_thread` hoc bang tin hieu khac don vi, dung kieu
    loi im lang Protocol 6 sinh ra de chan. Ban ghi cu (truoc khi co cot nay)
    duoc migrate voi `engine="pdf2zh"` — xem `_migrate_concurrency_state_engine_key`
    trong `src/models/database.py`.
    """

    __tablename__ = "concurrency_state"

    engine: str = Field(primary_key=True, default="pdf2zh")
    provider: str = Field(primary_key=True)
    model: str = Field(primary_key=True)

    current_thread: int
    consecutive_successes: int = Field(default=0)
    observation_count: int = Field(default=0)

    #: Chan doan — doc tu chunk gan nhat, phuc vu UI/debug, khong tham gia thuat toan.
    last_outcome: str = Field(default="none")
    last_rate_limit_hits: int = Field(default=0)
    last_duration_seconds: float | None = Field(default=None)

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
