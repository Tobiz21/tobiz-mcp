from __future__ import annotations

import pytest
from types import SimpleNamespace

from tobiz_mcp import errors
from tobiz_mcp.config import Config
from tobiz_mcp.service import Service


def make_service(*, allowed: frozenset[str], strict: bool) -> Service:
    service = Service.__new__(Service)
    service.config = Config(
        email=None,
        password=None,
        allowed_project_ids=allowed,
        require_project_allowlist=strict,
    )
    return service


def test_strict_mode_rejects_empty_allowlist() -> None:
    service = make_service(allowed=frozenset(), strict=True)

    with pytest.raises(errors.TobizError) as caught:
        service.check_allowed("123")

    assert caught.value.code == errors.PROJECT_NOT_ALLOWED


def test_allowlist_rejects_another_project() -> None:
    service = make_service(allowed=frozenset({"123"}), strict=True)

    with pytest.raises(errors.TobizError) as caught:
        service.check_allowed("456")

    assert caught.value.code == errors.PROJECT_NOT_ALLOWED


def test_allowlist_accepts_configured_project() -> None:
    service = make_service(allowed=frozenset({"123"}), strict=True)

    service.check_allowed("123")


def test_health_reports_project_access_mode() -> None:
    service = Service.__new__(Service)
    service.config = SimpleNamespace(
        transport="stdio",
        read_only=False,
        dry_run=False,
        assets_dir="/tmp/assets",
        require_project_allowlist=True,
        allowed_project_ids=frozenset({"123", "456"}),
    )
    service.client = SimpleNamespace(describe_session=lambda: {"present": False})
    service.bridge = SimpleNamespace(available=False)
    service._counters = {}

    with pytest.raises(StopIteration) as completed:
        service.health().send(None)
    result = completed.value.value

    assert result["project_access"] == {
        "strict": True,
        "allowlist_configured": True,
        "allowed_project_count": 2,
    }
