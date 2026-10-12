from tobiz_mcp.domain.design_reference import compare, extract
from tobiz_mcp.domain.draft import Draft, DraftBlock


def draft(types=("101", "130", "306"), *, color="#111111"):
    texts = (
        "Главная услуга для вашего бизнеса",
        "Наши услуги и решения",
        "Свяжитесь с нами: телефон +7 (999) 123-45-67",
    )
    blocks = {
        str(index): DraftBlock(str(index), block_type, {
            "title": texts[index - 1], "bg_color": "#ffffff",
            "btn1": {"color": color, "radius": "0.35", "align": "center"},
        })
        for index, block_type in enumerate(types, 1)
    }
    return Draft("1", "2", blocks=blocks, order=list(blocks))


def audit(button="#111111"):
    return {"viewports": {
        "desktop": {"design_profile": {
            "containerWidths": [1170], "buttonColors": [button],
            "buttonRadii": ["7px"], "headingAlignments": ["left"],
            "fontFamilies": ["Arial"],
        }},
        "mobile": {"design_profile": {
            "containerWidths": [360], "buttonColors": [button],
            "buttonRadii": ["7px"], "headingAlignments": ["left"],
            "fontFamilies": ["Arial"],
        }},
    }}


def test_identical_native_recipe_keeps_full_fidelity():
    reference = extract(draft(), audit())
    target = extract(draft(), audit())

    result = compare(reference, target)

    assert result["score"] == 10.0
    assert result["meets_7_of_10"] is True
    assert result["issues"] == []
    assert result["block_differences"] == []


def test_structure_and_rendered_style_drift_are_explained():
    reference = extract(draft(), audit())
    target = extract(draft(("101", "777"), color="#ff0000"), audit("#ff0000"))

    result = compare(reference, target)

    assert result["meets_7_of_10"] is False
    codes = {item["code"] for item in result["issues"]}
    assert "reference_structure_drift" in codes
    assert "reference_native_style_drift" in codes
    assert "reference_rendered_style_drift" in codes
    assert any(item["code"] == "block_type_changed" for item in result["block_differences"])
    assert any(item["property"] == "buttonColors" for item in result["visual_differences"])


def test_excess_flex_is_reported_against_native_reference():
    reference = extract(draft(), audit())
    target = extract(draft(("1600", "1600", "306")), audit())

    result = compare(reference, target)

    assert any(item["code"] == "excess_flex_vs_reference" for item in result["issues"])
