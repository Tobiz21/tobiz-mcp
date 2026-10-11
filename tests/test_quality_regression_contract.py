from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_quality_regression_fixture_is_wired_into_ci():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    inspector = (ROOT / "renderer/page-inspector.js").read_text(encoding="utf-8")
    assert "quality-failures.html" in workflow
    assert "assert-quality-regression.py" in workflow
    assert "missing_lead_name" in inspector
    assert "lead_name_not_first" in inspector
    assert "card_button_alignment_mismatch" in inspector
