from tobiz_mcp.domain.refinement import regression, summarize


def audit(*codes):
    return {
        "critical": [], "warnings": [{"code": code} for code in codes],
        "viewports": {"desktop": {"design_profile": {
            "containerWidths": [940, 1170], "buttonColors": ["rgb(1, 2, 3)"]}}},
    }


def test_refinement_summary_keeps_only_page_design_system_issues():
    result = summarize(audit("container_widths_inconsistent", "missing_alt"))
    assert result["system_issue_codes"] == ["container_widths_inconsistent"]
    assert result["profiles"]["desktop"]["containerWidths"] == [940, 1170]
    assert result["coherent"] is False


def test_refinement_regression_reports_resolved_and_introduced_codes():
    result = regression(
        audit("container_widths_inconsistent", "button_radii_inconsistent"),
        audit("button_radii_inconsistent", "button_palette_inconsistent"))
    assert result == {
        "introduced": ["button_palette_inconsistent"],
        "resolved": ["container_widths_inconsistent"],
        "regressed": True,
    }
