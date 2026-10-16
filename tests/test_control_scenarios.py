from tobiz_mcp.domain.control_scenarios import run


def test_all_four_supported_workflows_pass_release_contract():
    result = run()
    assert result["passed"] is True
    assert result["scenario_count"] == 4
    assert result["failed"] == []
    assert set(result["scenarios"]) == {
        "landing", "multipage", "seo_article_with_media", "product_catalog"}
