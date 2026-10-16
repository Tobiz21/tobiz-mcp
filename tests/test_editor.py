from types import SimpleNamespace

from tobiz_mcp.domain import editor
from tobiz_mcp.domain.draft import Draft, DraftBlock


def make_draft(blocks):
    draft = Draft(project_id="1", page_id="2")
    for index, block in enumerate(blocks):
        block.sort_id = index
        draft.blocks[block.block_id] = block
        draft.order.append(block.block_id)
    return draft


def payload_for(draft, rendered):
    return {"userBlocks": [
        {"id": block_id, "deleted": "0", "data": draft.blocks[block_id].values,
         "cache": rendered.get(block_id, "")}
        for block_id in draft.order
    ]}


def test_native_roundtrip_is_safe():
    draft = make_draft([DraftBlock("10", "130", {"anchor": "catalog"})])
    types = {"130": SimpleNamespace(has_template=True)}
    rendered = {"10": "<section><h2>Каталог оборудования для проверки</h2></section>"}
    result = editor.report(draft, types, rendered, payload_for(draft, rendered))
    assert result["verdict"] == "editor_safe"
    assert result["editor_safe"] is True
    assert result["would_save"] is False


def test_unsafe_structure_blocks_editor_save():
    draft = make_draft([
        DraftBlock("10", "163", {"anchor": "same", "hide_in_mobile": "1",
                                  "hide_in_desktop": "1"}),
        DraftBlock("11", "9999", {"anchor": "same"}),
    ])
    types = {"163": SimpleNamespace(has_template=True)}
    rendered = {"10": "", "11": ""}
    payload = payload_for(draft, rendered)
    payload["userBlocks"].reverse()
    result = editor.report(draft, types, rendered, payload)
    codes = {item["code"] for item in result["critical"]}
    assert result["verdict"] == "save_blocked"
    assert {"custom_code_block", "unknown_block_type", "hidden_everywhere",
            "duplicate_anchor", "empty_render", "empty_block_cache",
            "payload_order_mismatch"} <= codes


def test_flex_warning_does_not_mask_incomplete_form_blocker():
    blocks = [DraftBlock(str(index), "1600", {}) for index in range(1, 3)]
    blocks.append(DraftBlock("3", "120", {"form1": [{"type": "text"}]}))
    draft = make_draft(blocks)
    types = {
        "1600": SimpleNamespace(has_template=True),
        "120": SimpleNamespace(has_template=True),
    }
    rendered = {block_id: "<section>Полностью отрендерированный штатный блок TOBIZ</section>"
                for block_id in draft.order}
    result = editor.report(draft, types, rendered, payload_for(draft, rendered))
    assert result["verdict"] == "save_blocked"
    assert result["editor_safe"] is False
    assert "form_without_button" in {item["code"] for item in result["critical"]}
    assert "high_flex_share" in {item["code"] for item in result["warnings"]}


def test_invalid_flex_mobile_layout_blocks_editor_roundtrip():
    flex_values = {"flexblocks": [{
        "id": "title", "type": "text",
        "l": {"x": 0, "y": 0, "w": 400, "h": 80},
    }]}
    draft = make_draft([DraftBlock("10", "1600", flex_values)])
    types = {"1600": SimpleNamespace(has_template=True)}
    rendered = {"10": "<section>Полностью отрендерированный штатный Flex TOBIZ</section>"}
    result = editor.report(draft, types, rendered, payload_for(draft, rendered))
    assert result["verdict"] == "save_blocked"
    assert "flex_mobile_layout_missing" in {item["code"] for item in result["critical"]}


def test_nested_flex_form_without_button_requires_editor_review():
    values = {"flexblocks": [{
        "id": "lead", "type": "form", "content": {
            "form1": [{"type": "phone", "title": "Телефон"}],
        },
    }]}
    draft = make_draft([DraftBlock("10", "1600", values)])
    types = {"1600": SimpleNamespace(has_template=True)}
    rendered = {"10": "<section>Полностью отрендерированный штатный Flex TOBIZ</section>"}
    result = editor.report(draft, types, rendered, payload_for(draft, rendered))
    issue = next(item for item in result["critical"]
                 if item["code"] == "form_without_button")
    assert result["verdict"] == "save_blocked"
    assert result["editor_safe"] is False
    assert issue["form_path"] == "/flexblocks/0/content/form1"


def test_nested_submit_control_is_accepted_by_editor_roundtrip():
    values = {"flexblocks": [{
        "id": "lead", "type": "form", "content": {"form1": [
            {"type": "phone", "title": "Телефон"},
            {"type": "submit", "title": "Отправить"},
        ]},
    }]}
    draft = make_draft([DraftBlock("10", "1600", values)])
    types = {"1600": SimpleNamespace(has_template=True)}
    rendered = {"10": "<section>Полностью отрендерированный штатный Flex TOBIZ</section>"}
    result = editor.report(draft, types, rendered, payload_for(draft, rendered))
    assert "form_without_button" not in {item["code"] for item in result["warnings"]}
