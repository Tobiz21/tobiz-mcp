from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_smoke_covers_protocol_and_core_tools() -> None:
    script = (ROOT / "scripts" / "mcp-smoke.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "clean-install.yml").read_text(encoding="utf-8")

    assert "session.initialize()" in script
    assert "session.list_tools()" in script
    assert "tobiz_save_page" in script
    assert "tobiz_audit_page" in script
    assert "mcp-smoke.py:/tmp/mcp-smoke.py:ro" in workflow
