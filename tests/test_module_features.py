from __future__ import annotations

from pathlib import Path

import pytest

from tobiz_mcp.config import Config
from tobiz_mcp.domain.draft import Draft
from tobiz_mcp.service import Service


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, dict[str, object]]] = []

    async def module_ajax(self, path: str, action: str, project_id: str, **params: object):
        self.calls.append((path, action, project_id, params))
        if action == "get_offer":
            return {"id": params["id"], "title": "Size M"}
        return True


def bare_service(tmp_path: Path) -> Service:
    instance = object.__new__(Service)
    instance.config = Config(email=None, password=None, inbox_dir=tmp_path)
    instance.client = FakeClient()
    return instance


@pytest.mark.asyncio
async def test_sort_product_images_uses_php_array_keys(tmp_path: Path) -> None:
    instance = bare_service(tmp_path)

    async def module_get(project_id: str, kind: str, entity_id: str):
        return {"id": entity_id, "images": [{"id": "11"}, {"id": "22"}]}

    instance.module_get = module_get  # type: ignore[method-assign]
    await instance.module_sort_images("432812", "item", "7", ["22", "11"])
    _, action, _, params = instance.client.calls[0]
    assert action == "sort_images"
    assert params == {"sort[0][0]": "22", "sort[1][0]": "11",
                      "sort[0][1]": 0, "sort[1][1]": 1}


@pytest.mark.asyncio
async def test_offer_update_uses_native_actions(tmp_path: Path) -> None:
    instance = bare_service(tmp_path)

    async def project(project_id: str):
        return object()

    instance.project = project  # type: ignore[method-assign]
    result = await instance.product_offer_update(
        "432812", "9", {"title": "Large", "price": 1200, "image_id": "4"})
    actions = [call[1] for call in instance.client.calls]
    assert actions == ["get_offer", "update_offer_str_data", "update_offer_str_float",
                       "set_offer_iamge", "get_offer"]
    assert result["id"] == "9"


@pytest.mark.asyncio
async def test_site_style_change_marks_metadata_pending(tmp_path: Path) -> None:
    instance = bare_service(tmp_path)
    draft = Draft(project_id="432812", page_id="1", page_meta={"page_config": {"text_font": "Arial"}})

    async def get_draft(project_id: str, page_id: str):
        return draft

    instance.draft = get_draft  # type: ignore[method-assign]
    result = await instance.update_site_styles("432812", "1", {"text_font": "Inter, sans-serif"})
    assert result["pending_save"] is True
    assert draft.has_changes is True
    assert draft.changed_meta == ["page_config.text_font"]
