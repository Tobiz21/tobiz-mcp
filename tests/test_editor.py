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


def test_flex_and_incomplete_form_require_review():
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
    codes = {item["code"] for item in result["warnings"]}
    assert result["verdict"] == "review"
    assert {"high_flex_share", "form_without_button"} <= codes
