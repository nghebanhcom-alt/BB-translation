import time
from pathlib import Path

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert isinstance(body["pid"], int)
    assert isinstance(body["started_at"], str)
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0
    assert isinstance(body["git_commit"], str)
    assert isinstance(body["git_commit_full"], str)
    assert body["git_dirty_at_start"] is None or isinstance(body["git_dirty_at_start"], bool)
    assert isinstance(body["code_stale"], bool)
    assert isinstance(body["code_changed_count"], int)
    assert isinstance(body["code_changed_files"], list)
    assert len(body["code_changed_files"]) <= 10
    assert isinstance(body["code_fingerprint_at_start"], str)
    assert isinstance(body["code_fingerprint_now"], str)

    # Fresh process, nothing touched since import -> must report fresh.
    assert body["code_stale"] is False
    assert body["code_changed_count"] == 0
    assert body["code_changed_files"] == []
    assert body["code_fingerprint_now"] == body["code_fingerprint_at_start"]


def test_health_reports_code_stale_after_file_touched(tmp_path: Path) -> None:
    """Architecture.md Section 5.4.6: simulate a file changing on disk after
    the module's startup snapshot was taken, without touching real files
    under `src/` (would pollute the actual fingerprint for other tests /
    for a real running server).
    """
    fake_file = tmp_path / "fake_module.py"
    fake_file.write_text("x = 1\n")
    fake_relpath = "src/fake_module.py"

    original_snapshot = dict(main_module._CODE_SNAPSHOT_AT_START)
    original_fingerprint = main_module._CODE_FINGERPRINT_AT_START

    stat = fake_file.stat()
    main_module._CODE_SNAPSHOT_AT_START = {
        **original_snapshot,
        fake_relpath: f"{stat.st_mtime_ns}:{stat.st_size}",
    }
    main_module._CODE_FINGERPRINT_AT_START = main_module._fingerprint(
        main_module._CODE_SNAPSHOT_AT_START
    )

    try:
        # Simulate the tracked file being edited after startup.
        time.sleep(0.01)
        fake_file.write_text("x = 2\n")

        real_snapshot = main_module._code_snapshot
        try:
            main_module._code_snapshot = lambda: {  # type: ignore[assignment]
                **real_snapshot(),
                fake_relpath: f"{fake_file.stat().st_mtime_ns}:{fake_file.stat().st_size}",
            }
            with TestClient(app) as client:
                response = client.get("/health")
        finally:
            main_module._code_snapshot = real_snapshot

        body = response.json()
        assert body["code_stale"] is True
        assert fake_relpath in body["code_changed_files"]
        assert body["code_changed_count"] >= 1
    finally:
        main_module._CODE_SNAPSHOT_AT_START = original_snapshot
        main_module._CODE_FINGERPRINT_AT_START = original_fingerprint
