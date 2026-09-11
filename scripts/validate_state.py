#!/usr/bin/env python3
"""Validate project_state.json — Protocol 4 (mở rộng) trong CLAUDE.md.

PM chạy trước mỗi lần dispatch. Chỉ dùng stdlib, không thêm dependency mới.

Validator này làm 2 việc tách bạch, không trộn lẫn:
1. Áp ràng buộc cấu trúc sinh TRỰC TIẾP từ `project_state.schema.json` (type, required,
   additionalProperties, properties, items, enum, pattern, maxLength, minimum, maximum, format)
   bằng 1 checker generic đệ quy thuần stdlib (`check_against_schema`) — không duy trì tay 2 bản
   luật tách rời khỏi schema (đây chính là lỗi đã bị Reviewer chặn ở vòng 1/3: hai file duy trì
   tay tách rời lệch nhau theo thời gian).
2. Áp các luật nghiệp vụ Protocol B/E/3/4 mà bản thân schema (JSON Schema draft-07) không diễn
   đạt được — quan hệ CHÉO giữa nhiều field trong cùng 1 object (ví dụ status=done kéo theo phải
   có output; count>limit kéo theo phải có escalated_at). Các hàm `check_*` (trừ
   `check_against_schema`) thuộc nhóm này.

Usage: python3 scripts/validate_state.py
Exit code: 0 = hợp lệ, 1 = không hợp lệ (in danh sách lỗi).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "project_state.json"
SCHEMA_PATH = ROOT / "project_state.schema.json"

REQUIRED_TOP = [
    "project_name",
    "phase",
    "version",
    "updated_at",
    "team",
    "documents",
    "checkpoints",
    "open_questions",
    "backlog",
    "steps",
    "loops",
    "infra_pending",
    "blockers",
]
PHASES = ["planning", "design", "build", "verify", "released"]
CHECKPOINT_STATUS = ["pending", "approved", "stale"]
QUESTION_STATUS = ["open", "answered", "deferred"]
BACKLOG_STATUS = ["open", "done", "wontfix"]
STEP_STATUS = ["todo", "in_progress", "blocked", "review", "done"]

# Protocol C — ngân sách kích thước tài liệu (dòng). Vượt ngưỡng = cảnh báo, không chặn.
DOC_LINE_BUDGET = {
    "docs/Architecture.md": 8000,
    "docs/PRD.md": 2000,
    "docs/design-log.md": 8000,
    "docs/review-report.md": 4000,
    "docs/test-report.md": 4000,
    "docs/CHANGELOG.md": 8000,
}

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def parse_day(value: str) -> date | None:
    """Lấy phần ngày của applied_at — chấp nhận cả "YYYY-MM-DD" lẫn ISO datetime đầy đủ."""
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"KHÔNG ĐỌC ĐƯỢC {STATE_PATH.name}: {exc}", file=sys.stderr)
        sys.exit(1)


def load_schema() -> dict:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"KHÔNG ĐỌC ĐƯỢC {SCHEMA_PATH.name}: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 1. Generic JSON-Schema (draft-07 subset) checker — đọc project_state.schema.json trực tiếp.
# ---------------------------------------------------------------------------


def _matches_type(value: object, type_name: str) -> bool:
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "null":
        return value is None
    return False


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _short(value: object) -> str:
    text = repr(value)
    return text if len(text) <= 60 else text[:60] + "...'"


def _path_join(parent: str, key: str) -> str:
    return key if not parent else f"{parent}.{key}"


def _path_index(parent: str, idx: int) -> str:
    return f"{parent}[{idx}]"


def check_against_schema(instance: object, schema: dict, path: str) -> list[str]:
    """Áp đệ quy các keyword schema draft-07 thực sự dùng trong project_state.schema.json:
    type (kể cả list ["string","null"]), required, additionalProperties (bool hoặc schema),
    properties, items, enum, pattern, maxLength, minimum, maximum, format=date.
    """
    node_errors: list[str] = []
    label = path or "(root)"

    schema_type = schema.get("type")
    if schema_type is not None:
        allowed = schema_type if isinstance(schema_type, list) else [schema_type]
        if not any(_matches_type(instance, t) for t in allowed):
            node_errors.append(
                f"{label}: type phải thuộc {allowed}, thực tế {_type_name(instance)} "
                f"({_short(instance)})"
            )
            return node_errors

    if instance is None:
        return node_errors

    if "enum" in schema and instance not in schema["enum"]:
        node_errors.append(f"{label}: giá trị {_short(instance)} không thuộc enum {schema['enum']}")

    if isinstance(instance, str):
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            node_errors.append(
                f"{label}: vượt maxLength {schema['maxLength']} (thực tế {len(instance)} ký tự)"
            )
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            node_errors.append(f"{label}: không khớp pattern {schema['pattern']}")
        if schema.get("format") == "date" and parse_day(instance) is None:
            node_errors.append(
                f'{label}: format=date nhưng "{instance}" không phải ngày ISO hợp lệ'
            )

    if isinstance(instance, int | float) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            node_errors.append(f"{label}: nhỏ hơn minimum {schema['minimum']} (thực tế {instance})")
        if "maximum" in schema and instance > schema["maximum"]:
            node_errors.append(f"{label}: lớn hơn maximum {schema['maximum']} (thực tế {instance})")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                node_errors.append(f'{label}: thiếu trường bắt buộc "{key}"')

        properties: dict = schema.get("properties", {})
        for key, sub_schema in properties.items():
            if key in instance:
                node_errors.extend(
                    check_against_schema(instance[key], sub_schema, _path_join(path, key))
                )

        additional = schema.get("additionalProperties")
        if additional is False:
            for key in instance:
                if key not in properties:
                    node_errors.append(
                        f"{_path_join(path, key)}: field lạ, không khai báo trong schema "
                        "(additionalProperties: false)"
                    )
        elif isinstance(additional, dict):
            for key, value in instance.items():
                if key not in properties:
                    node_errors.extend(
                        check_against_schema(value, additional, _path_join(path, key))
                    )

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(instance):
                node_errors.extend(check_against_schema(item, item_schema, _path_index(path, i)))

    return node_errors


# ---------------------------------------------------------------------------
# 2. Luật nghiệp vụ Protocol B/E/3/4 — quan hệ chéo giữa nhiều field, schema không diễn đạt được.
# ---------------------------------------------------------------------------


def check_checkpoints(state: dict) -> set[str]:
    ids: set[str] = set()
    for cp in state.get("checkpoints", []):
        if not all(k in cp for k in ("id", "document", "status")):
            fail(f"checkpoint thiếu id/document/status: {json.dumps(cp, ensure_ascii=False)[:80]}")
            continue
        ids.add(cp["id"])
        if cp["status"] not in CHECKPOINT_STATUS:
            fail(f'checkpoint {cp["id"]}: status "{cp["status"]}" không hợp lệ')
        if cp["status"] == "stale" and not cp.get("status_reason"):
            fail(
                f"checkpoint {cp['id']}: status=stale nhưng thiếu status_reason (Protocol 2 mở rộng)"
            )
    return ids


def check_questions(state: dict) -> set[str]:
    ids: set[str] = set()
    for q in state.get("open_questions", []):
        if not all(k in q for k in ("id", "text", "asked_by", "status", "blocks")):
            fail(f"open_question thiếu trường bắt buộc: {json.dumps(q, ensure_ascii=False)[:80]}")
            continue
        ids.add(q["id"])
        if len(q["text"]) > 220:
            fail(
                f"open_question {q['id']}: text vượt 220 ký tự ({len(q['text'])}) — mô tả dài thuộc docs/, không thuộc state"
            )
        if q["status"] not in QUESTION_STATUS:
            fail(f'open_question {q["id"]}: status "{q["status"]}" không hợp lệ')
        if q["status"] == "answered" and not q.get("answered_in"):
            fail(f"open_question {q['id']}: status=answered nhưng thiếu answered_in")
        if q.get("clarify_rounds", 0) > 2:
            fail(
                f"open_question {q['id']}: clarify_rounds > 2 (Protocol B — tối đa 2 đợt CLARIFY, cần escalate)"
            )
    return ids


def check_backlog(state: dict) -> None:
    for b in state.get("backlog", []):
        if not all(k in b for k in ("id", "text", "source", "status")):
            fail(f"backlog thiếu trường bắt buộc: {json.dumps(b, ensure_ascii=False)[:80]}")
            continue
        if b["status"] not in BACKLOG_STATUS:
            fail(f'backlog {b["id"]}: status "{b["status"]}" không hợp lệ')
        if len(b["text"]) > 220:
            fail(f"backlog {b['id']}: text vượt 220 ký tự ({len(b['text'])})")


def check_steps(state: dict) -> set[str]:
    ids: set[str] = set()
    for s in state.get("steps", []):
        if not all(k in s for k in ("id", "title", "owner_role", "status", "blocked_by")):
            fail(f"step thiếu trường bắt buộc: {json.dumps(s, ensure_ascii=False)[:80]}")
            continue
        ids.add(s["id"])
        if s["status"] not in STEP_STATUS:
            fail(f'step {s["id"]}: status "{s["status"]}" không hợp lệ')
        if s["status"] == "done" and not s.get("output"):
            fail(f"step {s['id']}: status=done nhưng thiếu output (Protocol 4 mở rộng)")
    return ids


def check_loops(state: dict) -> None:
    for loop in state.get("loops", []):
        if not all(k in loop for k in ("pair", "item", "count", "limit")):
            fail(f"loop thiếu trường bắt buộc: {json.dumps(loop, ensure_ascii=False)[:80]}")
            continue
        if loop["count"] > loop["limit"] and not loop.get("escalated_at"):
            fail(
                f"loop {loop['pair']}/{loop['item']}: count {loop['count']} > limit {loop['limit']} "
                "nhưng chưa escalate (Protocol 3 mở rộng — ghi docs/escalation-log.md)"
            )


def check_infra(state: dict) -> set[str]:
    ids: set[str] = set()
    today = datetime.now(tz=UTC).date()
    for item in state.get("infra_pending", []):
        if not all(k in item for k in ("id", "applied_at", "target", "description")):
            fail(
                f"infra_pending thiếu trường bắt buộc: {json.dumps(item, ensure_ascii=False)[:80]}"
            )
            continue
        ids.add(item["id"])
        applied = parse_day(item["applied_at"])
        if applied is None:
            fail(
                f'infra_pending {item["id"]}: applied_at="{item["applied_at"]}" không parse được '
                "thành ngày hợp lệ — Protocol E dựa vào đúng field này để chặn dispatch quá 24h"
            )
            continue
        if item.get("commit"):
            continue
        if (today - applied).days > 1:
            fail(
                f"infra_pending {item['id']}: quá 24h chưa có commit (Protocol E) — "
                f"applied_at={item['applied_at']}, target={item['target']}"
            )
    return ids


def check_blockers(state: dict, known_ids: set[str]) -> None:
    for b in state.get("blockers", []):
        if not isinstance(b, str):
            fail(
                f"blockers chứa phần tử không phải string: {json.dumps(b, ensure_ascii=False)[:60]}"
            )
            continue
        if " " in b or len(b) > 20:
            fail(
                f'blockers chứa "{b[:40]}..." trông như câu văn, không phải id '
                "(Protocol 4 mở rộng: blockers chỉ chứa id)"
            )
        elif b not in known_ids:
            fail(f'blockers chứa id "{b}" không khớp open_questions/infra_pending/checkpoints nào')


def check_duplicate_ids(items: list, id_key: str, label: str) -> None:
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        value = it.get(id_key)
        if value is None:
            continue
        if value in seen:
            fail(f'{label}: id "{value}" bị trùng lặp trong cùng 1 mảng')
        seen.add(value)


def check_duplicate_loop_pairs(loops: list) -> None:
    seen: set[tuple[str, str]] = set()
    for loop in loops:
        if not isinstance(loop, dict):
            continue
        pair, item = loop.get("pair"), loop.get("item")
        if pair is None or item is None:
            continue
        key = (pair, item)
        if key in seen:
            fail(f'loops: cặp pair/item "{pair}/{item}" bị trùng lặp')
        seen.add(key)


def check_doc_budget() -> None:
    for rel, budget in DOC_LINE_BUDGET.items():
        path = ROOT / rel
        if not path.exists():
            continue
        lines = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
        if lines > budget:
            warn(
                f"{rel}: {lines} dòng > ngân sách {budget} (Protocol C) — "
                "tách lịch sử ra file riêng hoặc archive theo tháng"
            )


def main() -> int:
    state = load_state()
    schema = load_schema()

    for schema_error in check_against_schema(state, schema, ""):
        fail(schema_error)

    for key in REQUIRED_TOP:
        if key not in state:
            fail(f'thiếu trường bắt buộc cấp cao nhất: "{key}"')

    if state.get("phase") and state["phase"] not in PHASES:
        fail(f'phase "{state["phase"]}" không hợp lệ, phải thuộc {"/".join(PHASES)}')

    checkpoint_ids = check_checkpoints(state)
    question_ids = check_questions(state)
    check_backlog(state)
    step_ids = check_steps(state)
    check_loops(state)
    infra_ids = check_infra(state)
    check_blockers(state, checkpoint_ids | question_ids | infra_ids)
    check_duplicate_ids(state.get("steps", []), "id", "steps[]")
    check_duplicate_ids(state.get("checkpoints", []), "id", "checkpoints[]")
    check_duplicate_ids(state.get("open_questions", []), "id", "open_questions[]")
    check_duplicate_ids(state.get("backlog", []), "id", "backlog[]")
    check_duplicate_loop_pairs(state.get("loops", []))
    check_doc_budget()

    for s in state.get("steps", []):
        for dep in s.get("blocked_by", []):
            if dep not in step_ids | question_ids | checkpoint_ids:
                warn(
                    f'step {s["id"]}: blocked_by "{dep}" không khớp step/question/checkpoint nào đã biết'
                )

    if errors:
        print(f"❌ project_state.json KHÔNG hợp lệ — {len(errors)} lỗi:\n", file=sys.stderr)
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}", file=sys.stderr)
    else:
        print(
            f"✅ project_state.json hợp lệ — {len(state.get('steps', []))} bước, "
            f"{len(state.get('open_questions', []))} câu hỏi mở, "
            f"{len(state.get('backlog', []))} backlog, "
            f"{len(state.get('checkpoints', []))} checkpoint."
        )

    if warnings:
        stream = sys.stderr if errors else sys.stdout
        print(f"\n⚠ {len(warnings)} cảnh báo (không chặn):", file=stream)
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}", file=stream)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
