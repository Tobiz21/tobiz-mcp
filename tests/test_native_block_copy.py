import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain.draft import Draft, DraftBlock
from tobiz_mcp.tools import register


def registered_functions(service):
    functions = {}

    class MCP:
        def tool(self, name, description):
            def capture(fn):
                functions[name] = fn
                return fn
            return capture

    register(MCP(), service)
    return functions


def copy_service(source, target, *, created_id="900"):
    async def resolve(project_id, page_id):
        return str(project_id), SimpleNamespace(page_id=str(page_id), title="Page")

    async def draft(project_id, page_id):
        return source if str(project_id) == source.project_id else target

    envelope = SimpleNamespace(
        ok=True, payload={"respons": json.dumps({"block_id": created_id})},
        raw_text="", message="", status=200)
    return SimpleNamespace(
        config=SimpleNamespace(read_only=False, lp_base=lambda project_id: "https://example.test"),
        resolve_page=AsyncMock(side_effect=resolve),
        draft=AsyncMock(side_effect=draft),
        type_or_raise=AsyncMock(return_value=SimpleNamespace(has_template=True)),
        client=SimpleNamespace(editor_ajax=AsyncMock(return_value=envelope)),
    )


@pytest.mark.asyncio
async def test_native_block_copy_previews_without_creating_block():
    source = Draft("1", "10", blocks={
        "100": DraftBlock("100", "130", {"title": "Каталог", "vendor_flag": "kept"}),
    }, order=["100"])
    target = Draft("2", "20")
    service = copy_service(source, target)
    function = registered_functions(service)["tobiz_copy_native_block"]

    result = await function(source_project_id="1", source_page_id="10",
                            source_block_id="100", target_project_id="2",
                            target_page_id="20")

    assert result["ok"] is True
    assert result["data"]["preview"] is True
    assert result["data"]["plan"]["target"]["change_hash"] == target.change_hash()
    service.client.editor_ajax.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_block_copy_preserves_values_and_stages_for_one_save():
    source_values = {"title": "Проверенный блок", "unknown_vendor_data": {"keep": [1, 2]}}
    source = Draft("1", "10", blocks={
        "100": DraftBlock("100", "3010", source_values),
    }, order=["100"])
    target = Draft("2", "20", blocks={
        "200": DraftBlock("200", "165", {"title": "Шапка"}),
    }, order=["200"])
    service = copy_service(source, target)
    function = registered_functions(service)["tobiz_copy_native_block"]
    expected_hash = target.change_hash()

    result = await function(source_project_id="1", source_page_id="10",
                            source_block_id="100", target_project_id="2",
                            target_page_id="20", after_block_id="200",
                            expected_target_hash=expected_hash, apply=True)

    assert result["ok"] is True
    assert result["data"]["pending_save"] is True
    assert target.order == ["200", "900"]
    assert target.blocks["900"].values == source_values
    assert target.blocks["900"].values is not source_values
    assert target.blocks["900"].changed_paths == ["native_block_copy"]


@pytest.mark.asyncio
async def test_native_block_copy_rejects_stale_target_hash():
    source = Draft("1", "10", blocks={
        "100": DraftBlock("100", "130", {"title": "Каталог"}),
    }, order=["100"])
    target = Draft("2", "20")
    service = copy_service(source, target)
    function = registered_functions(service)["tobiz_copy_native_block"]

    result = await function(source_project_id="1", source_page_id="10",
                            source_block_id="100", target_project_id="2",
                            target_page_id="20", expected_target_hash="stale", apply=True)

    assert result["ok"] is False
    assert result["error"]["code"] == "CONFLICT"
    service.client.editor_ajax.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_block_copy_rejects_invalid_flex():
    source = Draft("1", "10", blocks={
        "100": DraftBlock("100", "1600", {"flexblocks": [{
            "id": "title", "type": "text",
            "l": {"x": 0, "y": 0, "w": 400, "h": 80},
        }]}),
    }, order=["100"])
    target = Draft("2", "20")
    service = copy_service(source, target)
    function = registered_functions(service)["tobiz_copy_native_block"]

    result = await function(source_project_id="1", source_page_id="10",
                            source_block_id="100", target_project_id="2",
                            target_page_id="20")

    assert result["ok"] is False
    assert result["error"]["code"] == "BAD_ARGUMENT"
    assert result["error"]["raw"]["blockers"][0]["code"] == "flex_mobile_layout_missing"
