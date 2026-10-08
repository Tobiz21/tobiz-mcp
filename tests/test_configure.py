from __future__ import annotations

import pytest

from tobiz_mcp.configure import env_text, project_ids, write_config


def test_project_ids_normalizes_and_deduplicates() -> None:
    assert project_ids("123, 456,123") == ["123", "456"]


@pytest.mark.parametrize("value", ["", "abc", "123,wrong"])
def test_project_ids_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(Exception):
        project_ids(value)


def test_env_enables_strict_allowlist() -> None:
    content = env_text(projects=["123", "456"], email="owner@example.test",
                       password="secret")

    assert "TOBIZ_ALLOWED_PROJECT_IDS=123,456" in content
    assert "TOBIZ_REQUIRE_PROJECT_ALLOWLIST=true" in content
    assert "MCP_TRANSPORT=stdio" in content


def test_http_env_generates_token() -> None:
    content = env_text(projects=["123"], transport="http")

    token = next(line for line in content.splitlines() if line.startswith("MCP_HTTP_TOKEN="))
    assert len(token.split("=", 1)[1]) >= 32


def test_env_rejects_multiline_secret() -> None:
    with pytest.raises(ValueError, match="переносы строк"):
        env_text(projects=["123"], password="first\nTOBIZ_READ_ONLY=0")


def test_write_config_backs_up_existing_file(tmp_path) -> None:
    target = tmp_path / ".env"
    target.write_text("OLD=1\n", encoding="utf-8")

    backup = write_config(target, "NEW=1\n")

    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "OLD=1\n"
    assert target.read_text(encoding="utf-8") == "NEW=1\n"
