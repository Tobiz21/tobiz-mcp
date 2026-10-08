from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tobiz_mcp import errors
from tobiz_mcp.service import Service
from tobiz_mcp.tools import wrap


def finish(coroutine):
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    return completed.value.value


def test_tool_wrapper_records_success_and_error_codes() -> None:
    recorded = []

    async def success():
        return {"value": 1}

    async def failure():
        raise errors.TobizError(errors.NOT_FOUND, "missing")

    ok = finish(wrap(success, tool_name="success", metric_recorder=lambda *args: recorded.append(args))())
    failed = finish(wrap(failure, tool_name="failure", metric_recorder=lambda *args: recorded.append(args))())

    assert ok["ok"] is True
    assert failed["ok"] is False
    assert recorded[0][0:2] == ("success", True)
    assert recorded[1][0:2] == ("failure", False)
    assert recorded[1][3] == errors.NOT_FOUND


def test_diagnostics_contains_only_aggregates(tmp_path) -> None:
    service = Service.__new__(Service)
    service.config = SimpleNamespace(
        audit_dir=tmp_path,
        read_only=False,
        dry_run=False,
        require_project_allowlist=True,
        allowed_project_ids=frozenset({"123"}),
    )
    service.bridge = SimpleNamespace(available=True)
    service.client = SimpleNamespace(describe_session=lambda: {
        "present": True,
        "cookies": {"session": "super-secret"},
    })
    service._counters = {"render_failed": 0}
    service._tool_metrics = {}
    service.record_tool_metric("tobiz_page_summary", True, 20)
    service.record_tool_metric("tobiz_save_page", False, 40, errors.CONFLICT)

    (tmp_path / "audit.jsonl").write_text(
        json.dumps({"tool": "tobiz_save_page", "project_id": "123",
                    "page_text": "private content"}) + "\n",
        encoding="utf-8",
    )
    backup = tmp_path / "backups" / "123" / "456"
    backup.mkdir(parents=True)
    (backup / "one.json").write_text("{}", encoding="utf-8")

    result = service.diagnostics()
    serialized = json.dumps(result)

    assert result["privacy"]["remote_telemetry"] is False
    assert result["tool_metrics"]["tobiz_save_page"]["error_codes"] == {errors.CONFLICT: 1}
    assert result["audit"] == {"records_scanned": 1, "operations": {"tobiz_save_page": 1}}
    assert result["backups"]["files"] == 1
    assert "super-secret" not in serialized
    assert "private content" not in serialized
    assert '"123"' not in serialized
