import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REPOSITORY = "https://github.com/Tobiz21/tobiz-mcp"


def test_public_links_do_not_point_to_old_repository() -> None:
    checked = [ROOT / "README.md", ROOT / "skills" / "tobiz-mcp" / "SKILL.md"]
    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert "raydev-ru/tobiz-mcp" not in text
        assert PUBLIC_REPOSITORY in text


def test_package_metadata_has_public_project_urls() -> None:
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'readme = "README.md"' in metadata
    assert f'Homepage = "{PUBLIC_REPOSITORY}"' in metadata
    assert f'Repository = "{PUBLIC_REPOSITORY}"' in metadata


def test_readme_marks_docker_as_supported_distribution() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Поддерживаемый способ установки публичной бета-версии - Docker" in readme
    assert "wheel сам по себе не" in readme


def test_server_manifest_matches_public_container() -> None:
    manifest = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "io.github.Tobiz21/tobiz-mcp"
    assert manifest["version"] == "0.9.0-beta.2"
    assert manifest["repository"]["url"] == PUBLIC_REPOSITORY
    package = manifest["packages"][0]
    assert package["registryType"] == "oci"
    assert package["identifier"] == "ghcr.io/tobiz21/tobiz-mcp:0.9.0-beta.2"
    variables = {item["name"]: item for item in package["environmentVariables"]}
    assert variables["TOBIZ_PASSWORD"]["isSecret"] is True
    assert variables["TOBIZ_ALLOWED_PROJECT_IDS"]["isRequired"] is True


def test_container_declares_registry_ownership() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'io.modelcontextprotocol.server.name="io.github.Tobiz21/tobiz-mcp"' in dockerfile
