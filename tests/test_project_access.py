from __future__ import annotations

import pytest
from types import SimpleNamespace

from tobiz_mcp import errors
from tobiz_mcp.config import Config
from tobiz_mcp.service import Service
from tobiz_mcp.tobiz.pages import Project


def finish(coroutine):
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    return completed.value.value


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

    result = finish(service.health())

    assert result["project_access"] == {
        "strict": True,
        "allowlist_configured": True,
        "allowed_project_count": 2,
    }


def test_projects_filters_entries_outside_allowlist(monkeypatch) -> None:
    service = make_service(allowed=frozenset({"123"}), strict=True)
    service._projects = None

    async def ensure_session() -> None:
        return None

    async def panel_ajax(_action: str):
        return SimpleNamespace(ok=True, payload={"html": "fixture"})

    service.client = SimpleNamespace(
        ensure_session=ensure_session,
        panel_ajax=panel_ajax,
    )
    monkeypatch.setattr(
        "tobiz_mcp.service.parse_projects",
        lambda _html, _template: [Project("123"), Project("456")],
    )

    projects = finish(service.projects(refresh=True))

    assert [project.project_id for project in projects] == ["123"]


def test_projects_strict_empty_allowlist_stops_before_network() -> None:
    service = make_service(allowed=frozenset(), strict=True)
    service._projects = None
    service.client = SimpleNamespace()

    with pytest.raises(errors.TobizError) as caught:
        finish(service.projects(refresh=True))

    assert caught.value.code == errors.PROJECT_NOT_ALLOWED


def test_onboarding_warns_for_personal_unrestricted_install() -> None:
    service = make_service(allowed=frozenset(), strict=False)
    service.client = SimpleNamespace(describe_session=lambda: {"present": True})
    service.bridge = SimpleNamespace(available=True)

    async def projects(refresh: bool = False):
        return [Project("123")]

    service.projects = projects

    result = finish(service.onboarding_check())

    assert result["ready"] is True
    assert result["distribution_ready"] is False
    assert result["next_action"] == "Включите строгую изоляцию для распространения"
