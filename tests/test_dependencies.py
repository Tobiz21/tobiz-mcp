from tobiz_mcp.domain import dependencies
from tobiz_mcp.domain.draft import Draft, DraftBlock


def target(values=None):
    return Draft("1", "2", blocks={
        "10": DraftBlock("10", "100", values or {"anchor": "contacts"}),
    }, order=["10"])


def test_dependency_inventory_finds_native_links_media_and_bound_entities():
    result = dependencies.block_dependencies({
        "anchor": "offer", "btn": {"link": "#contacts"},
        "image1": "photo.jpg", "product_id": "42",
    })
    assert result["anchors"] == ["offer"]
    assert result["internal_references"] == ["contacts"]
    assert result["media"][0]["path"] == "/image1"
    assert result["project_bound"][0]["path"] == "/product_id"


def test_copy_preflight_blocks_duplicate_and_missing_anchors():
    result = dependencies.copy_preflight({
        "anchor": "contacts", "btn": {"link": "#missing"},
    }, target())
    assert result["valid"] is False
    assert {item["code"] for item in result["blockers"]} == {
        "duplicate_anchor_on_target", "missing_internal_target"}


def test_copy_preflight_allows_reference_to_existing_target():
    result = dependencies.copy_preflight({"btn": {"link": "#contacts"}}, target())
    assert result["valid"] is True
    assert result["blockers"] == []
