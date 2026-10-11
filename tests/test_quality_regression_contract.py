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
    assert "thin_page_content" in inspector
    assert "duplicate_headings" in inspector
    assert "missing_contact_signal" in inspector
    assert "visual-consistency-failures.html" in workflow
    assert "assert-visual-consistency-regression.py" in workflow
    assert "card_image_ratios_inconsistent" in inspector
    assert "too_many_font_families" in inspector
    assert "text_too_small" in inspector
    assert "excessive_section_gap" in inspector
    assert "image_aspect_distorted" in inspector
    assert "field_missing_accessible_label" in inspector
    assert "tap_target_too_small" in inspector
    assert "heading_level_skipped" in inspector
    assert "missing_primary_action" in inspector
    assert "quality-pass.html" in workflow
    assert "assert-quality-pass.py" in workflow
