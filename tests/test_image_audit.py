from tobiz_mcp.domain.image_audit import summarize


def report(issues=None, broken=None, missing=0):
    return {"viewports": {"desktop": {
        "screenshot": "desktop.png",
        "media": {"imageItems": [{
            "block": "b_10", "src": "photo.jpg", "alt": "Работа",
            "naturalWidth": 1200, "naturalHeight": 800,
            "renderedWidth": 600, "renderedHeight": 400, "objectFit": "cover",
            "nearbyText": "Как проходит работа",
        }], "brokenImages": broken or [], "missingAlt": missing},
        "layout": {"visualIssues": issues or []},
    }}}


def test_clean_image_inventory_is_ready_and_keeps_semantic_context():
    result = summarize(report())
    assert result["verdict"] == "ready"
    assert result["images"][0]["block_id"] == "10"
    assert result["semantic_review"][0]["nearby_text"] == "Как проходит работа"


def test_background_text_and_broken_image_block_release():
    result = summarize(report(
        [{"code": "text_over_image_without_scrim", "items": [{"block": "b_10"}]}],
        broken=[{"src": "missing.jpg", "block": "b_10"}]))
    assert result["verdict"] == "save_blocked"
    assert result["score"] == 4.9
    assert set(result["issue_codes"]) == {"broken_images", "text_over_image_without_scrim"}


def test_mechanical_image_warning_requires_review():
    result = summarize(report([{"code": "image_crop_extreme", "count": 1}]))
    assert result["verdict"] == "review"
    assert result["score"] == 9.2
