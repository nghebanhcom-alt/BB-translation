import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class LayoutQaFinding(SQLModel, table=True):
    """1 dong = 1 flag cua gate P0.1 (Architecture.md "Final Decision" U4/P0.1).

    `job_id` la nullable co chu dich: P0.2 chay babeldoc/pdf2zh THAT ngoai
    `JobOrchestrator` (khong tao Job row that), nen can `run_label` de phan
    biet cac lan chay A/B ma khong co job that dung sau. Khi gate chay trong
    pipeline that (tuong lai, ngoai pham vi P0.1 nay), caller truyen `job_id`
    that va `run_label` co the de trong.
    """

    __tablename__ = "layout_qa_findings"

    id: str = Field(default_factory=_uuid, primary_key=True)
    job_id: str | None = Field(default=None, foreign_key="jobs.id", index=True)
    run_label: str | None = Field(default=None, index=True)
    # Dinh danh tu do cho 1 lan chay A/B (vd "chunk38_maxpages4") — dung de so
    # sanh giua cac lan chay khi chua co job that (P0.2).
    source_file: str | None = Field(default=None)
    page_number: int = Field(index=True)
    check_type: str
    # overlap | text_over_drawing | text_over_image | rotated_text_prescan | entity_loss
    severity: str
    # blocker | critical | major | minor
    detail: str
    # JSON string — noi dung tuy check_type, xem docstring cua tung ham _check_* trong
    # src/services/layout_qa.py.
    created_at: datetime = Field(default_factory=datetime.utcnow)
