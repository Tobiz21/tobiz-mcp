from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp import errors
from tobiz_mcp.service import Service
from tobiz_mcp.tobiz.pages import Page, PageForm, Project


def service_for(project, pages, form):
    service = object.__new__(Service)
    service.config = SimpleNamespace(
        lp_base=lambda project_id: f"https://{project_id}.lp.tobiz.net",
        audit_dir="C:/tmp/tobiz-audit",
    )
    service.pages = AsyncMock(return_value=(project, pages))
    service.page_form = AsyncMock(return_value=form)
    return service


@pytest.mark.asyncio
async def test_public_page_url_uses_custom_domain_and_native_slug():
    project = Project("7", site_url="https://example.ru/?panel=1")
    page = Page("2", title="Услуги", slug="old")
    service = service_for(project, [Page("1"), page], PageForm(text={"page_dir": "uslugi"}))
    assert await service.public_page_url("7", "2") == "https://example.ru/uslugi/"


@pytest.mark.asyncio
async def test_public_page_url_uses_root_only_for_first_visible_page():
    project = Project("7", site_url="")
    first = Page("1", visible=True)
    second = Page("2", visible=True)
    service = service_for(project, [first, second], PageForm(text={"page_dir": ""}))
    assert await service.public_page_url("7", "1") == "https://7.lp.tobiz.net/"
    with pytest.raises(errors.TobizError) as captured:
        await service.public_page_url("7", "2")
    assert captured.value.code == errors.BAD_ARGUMENT


@pytest.mark.asyncio
async def test_verify_page_fetches_resolved_slug_instead_of_v_query():
    project = Project("7", site_url="https://example.ru")
    page = Page("2", title="Услуги")
    service = service_for(project, [Page("1"), page], PageForm(text={"page_dir": "uslugi"}))
    service.client = SimpleNamespace(fetch_text=AsyncMock(
        return_value='<div id="b_20">Проверочный текст</div>'))
    result = await service.verify_page("7", "2", expect=["Проверочный текст"], block_ids=["20"])
    assert result["status"] == "ok"
    assert result["url"] == "https://example.ru/uslugi/"
    service.client.fetch_text.assert_awaited_once_with("https://example.ru/uslugi/")
