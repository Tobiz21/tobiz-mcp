from __future__ import annotations

import pytest

from tobiz_mcp import errors
from tobiz_mcp.selftest import cmd_release


def finish(coroutine):
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    return completed.value.value


class FakeService:
    def __init__(self, distribution_ready: bool = True, missing_feature: bool = False):
        self.distribution_ready = distribution_ready
        self.missing_feature = missing_feature

    async def onboarding_check(self, project_id: str, page_id: str):
        return {
            "ready": True,
            "distribution_ready": self.distribution_ready,
            "checks": [],
            "editor_roundtrip": {"editor_safe": True, "would_save": False},
        }

    def list_page_backups(self, project_id: str, page_id: str):
        return {"backups": []}

    async def health(self):
        features = [
            "editor_roundtrip_check",
            "safe_page_backups",
            "onboarding_readiness_check",
            "strict_project_isolation",
            "local_privacy_safe_diagnostics",
        ]
        if self.missing_feature:
            features.remove("safe_page_backups")
        return {"version": "0.9.0b2", "features": features}


def test_release_passes_complete_strict_install(capsys) -> None:
    code = finish(cmd_release(FakeService(), "123", "456"))

    assert code == 0
    assert '"release_ready": true' in capsys.readouterr().out


@pytest.mark.parametrize(
    ("service", "expected"),
    [(FakeService(distribution_ready=False), 1), (FakeService(missing_feature=True), 1)],
)
def test_release_rejects_incomplete_install(service, expected, capsys) -> None:
    assert finish(cmd_release(service, "123", "456")) == expected
    assert '"release_ready": false' in capsys.readouterr().out


def test_release_requires_project() -> None:
    with pytest.raises(errors.TobizError) as caught:
        finish(cmd_release(FakeService(), None, "456"))

    assert caught.value.code == errors.BAD_ARGUMENT
