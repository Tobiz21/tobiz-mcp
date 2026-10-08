from __future__ import annotations

import base64
from pathlib import Path

import pytest

from tobiz_mcp.config import Config
from tobiz_mcp.service import Service


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "h6Y3vQAAAABJRU5ErkJggg=="
)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def module_upload(self, *args: object) -> dict[str, object]:
        self.calls.append(args)
        return {}


def service(tmp_path: Path) -> Service:
    instance = object.__new__(Service)
    instance.config = Config(email=None, password=None, inbox_dir=tmp_path)
    instance.client = FakeClient()

    async def module_get(project_id: str, kind: str, entity_id: str) -> dict[str, object]:
        return {"id": entity_id, "images": [{"id": "1"}]}

    instance.module_get = module_get  # type: ignore[method-assign]
    return instance


def finish(coroutine):
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    return completed.value.value


@pytest.mark.parametrize(
    ("kind", "action", "entity", "id_name"),
    [
        ("article", "upload_article_image", "article", "article_id"),
        ("item", "upload_image", "image", "item_id"),
    ],
)
def test_module_upload_uses_vendor_entity(
    tmp_path: Path, kind: str, action: str, entity: str, id_name: str
) -> None:
    instance = service(tmp_path)
    result = finish(instance.module_upload_image(
        "432776", kind, "99", content_base64=base64.b64encode(PNG).decode(),
        file_name="test.png",
    ))

    call = instance.client.calls[0]
    assert call[2:6] == (action, entity, id_name, "99")
    assert result == {"id": "99", "images": [{"id": "1"}]}
