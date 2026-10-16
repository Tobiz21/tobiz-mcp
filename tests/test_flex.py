from tobiz_mcp.domain import flex


def element(element_id, element_type, *, desktop=None, mobile=None):
    result = {"id": element_id, "type": element_type}
    if desktop is not None:
        result["l"] = desktop
    if mobile is not None:
        result["xs"] = mobile
    return result


def test_valid_native_flex_model():
    values = {"flexblocks": [
        element("title", "text", desktop={"x": 0, "y": 0, "w": 420, "h": 80},
                mobile={"x": 0, "y": 0, "w": 300, "h": 80}),
        element("cta", "btn", desktop={"x": 0, "y": 100, "w": 180, "h": 48},
                mobile={"x": 0, "y": 100, "w": 160, "h": 44}),
    ]}
    result = flex.validate(values)
    assert result["valid"] is True
    assert result["element_count"] == 2
    assert result["blockers"] == []
    assert result["schema_profile"]["element_keys_by_type"]["btn"] == ["id", "l", "type", "xs"]
    assert result["schema_profile"]["style_keys_by_mode"]["xs"] == ["h", "w", "x", "y"]


def test_positioned_element_requires_mobile_layout():
    values = {"flexblocks": [
        element("title", "text", desktop={"x": 0, "y": 0, "w": 420, "h": 80}),
    ]}
    result = flex.validate(values)
    assert result["valid"] is False
    assert "flex_mobile_layout_missing" in {item["code"] for item in result["blockers"]}


def test_duplicate_id_and_unsupported_type_are_blocked():
    values = {"flexblocks": [
        {"id": "same", "type": "text"},
        {"id": "same", "type": "made-up-widget"},
    ]}
    result = flex.validate(values)
    codes = {item["code"] for item in result["blockers"]}
    assert {"flex_duplicate_element_id", "flex_element_type_unsupported"} <= codes


def test_mobile_overlap_blocks_but_desktop_overlap_only_warns():
    first = element("one", "text", desktop={"x": 0, "y": 0, "w": 100, "h": 100},
                    mobile={"x": 0, "y": 0, "w": 100, "h": 100})
    second = element("two", "image", desktop={"x": 50, "y": 50, "w": 100, "h": 100},
                     mobile={"x": 50, "y": 50, "w": 100, "h": 100})
    result = flex.validate({"flexblocks": [first, second]})
    overlaps = [item for item in result["issues"] if item["code"] == "flex_elements_overlap"]
    assert {item["mode"] for item in overlaps} == {"l", "xs"}
    assert next(item for item in overlaps if item["mode"] == "l")["priority"] == "improve"
    assert next(item for item in overlaps if item["mode"] == "xs")["priority"] == "must_fix"


def test_small_mobile_cta_and_invalid_size_are_blocked():
    values = {"flexblocks": [
        element("cta", "btn", desktop={"x": 0, "y": 0, "w": 180, "h": 48},
                mobile={"x": 0, "y": 0, "w": 40, "h": 0}),
    ]}
    result = flex.validate(values)
    codes = {item["code"] for item in result["blockers"]}
    assert {"flex_cta_too_small", "flex_element_size_invalid"} <= codes


def test_mapping_form_of_flexblocks_is_supported():
    values = {"flexblocks": {
        "title": element("title", "text", mobile={"x": 0, "y": 0, "w": 300, "h": 80}),
    }}
    assert flex.validate(values)["element_count"] == 1
