from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain import project_quality
from tobiz_mcp.domain.draft import Draft, DraftBlock
from tobiz_mcp.tobiz.pages import Page, PageForm
from tobiz_mcp.tools import register


def page(page_id, slug, seo_title, header="105", footer="165"):
    return {
        "page_id": page_id, "title": f"Страница {page_id}", "slug": slug, "visible": True,
        "page": {
            "page_dir": slug,
            "page_seo_title": seo_title,
            "page_seo_description": (
                "Подробное описание страницы для поисковой выдачи, которое объясняет содержание "
                "и пользу посетителю без шаблонных формулировок."),
        },
        "composition": {
            "score": 8, "meets_7_of_10": True,
            "sections": [
                {"role": "header", "type_id": header},
                {"role": "hero", "type_id": "101"},
                {"role": "cta", "type_id": footer},
            ],
        },
    }


def test_complete_multipage_project_is_ready():
    result = project_quality.audit([
        page("1", "glavnaya", "Создание сайтов для бизнеса в Чебоксарах"),
        page("2", "uslugi", "Услуги разработки сайтов для компаний"),
    ])
    assert result["ready"] is True
    assert result["score"] >= 7
    assert result["metrics"]["header_types"] == {"105": 2}


def test_project_audit_blocks_duplicate_routes_and_missing_conversion():
    first = page("1", "uslugi", "Одинаковый SEO заголовок для двух страниц")
    second = page("2", "uslugi", "Одинаковый SEO заголовок для двух страниц", header="777")
    second["composition"]["sections"] = [
        {"role": "header", "type_id": "777"},
        {"role": "hero", "type_id": "101"},
    ]
    result = project_quality.audit([first, second])
    codes = {item["code"] for item in result["issues"]}
    assert result["ready"] is False
    assert {"page_slug_duplicate", "page_seo_title_duplicate",
            "page_conversion_exit_missing", "project_header_type_inconsistent",
            "project_footer_type_inconsistent"} <= codes


def test_single_page_project_is_not_accepted_as_multipage():
    result = project_quality.audit([page("1", "glavnaya", "Создание сайтов для бизнеса")])
    assert "multipage_has_fewer_than_two_visible_pages" in {
        item["code"] for item in result["blockers"]}


@pytest.mark.asyncio
async def test_project_audit_tool_reads_every_native_page():
    pages = [
        Page("1", title="Главная", slug="glavnaya"),
        Page("2", title="Услуги", slug="uslugi"),
    ]
    project = SimpleNamespace(project_id="7")
    forms = [
        PageForm(text={"page_title": item.title, "page_dir": item.slug,
                       "page_seo_title": f"Разработка сайтов - {item.title} для бизнеса",
                       "page_seo_description": (
                           "Подробное описание страницы для поисковой выдачи, которое объясняет "
                           "содержание и пользу посетителю без шаблонных формулировок.")})
        for item in pages
    ]
    drafts = []
    for item in pages:
        drafts.append(Draft("7", item.page_id, blocks={
            "1": DraftBlock("1", "105", {"menu1": [], "phone": "+7 900 000-00-00"}),
            "2": DraftBlock("2", "101", {"title": "Создаем сайты для бизнеса"}),
            "3": DraftBlock("3", "306", {"title": "Оставьте заявку", "form1": []}),
        }, order=["1", "2", "3"]))
    service = SimpleNamespace(
        config=SimpleNamespace(read_only=False),
        pages=AsyncMock(return_value=(project, pages)),
        page_form=AsyncMock(side_effect=forms),
        draft=AsyncMock(side_effect=drafts),
    )
    functions = {}

    class MCP:
        def tool(self, name, description):
            def capture(fn):
                functions[name] = fn
                return fn
            return capture

    register(MCP(), service)
    response = await functions["tobiz_audit_project"](project_id="7")
    assert response["ok"] is True
    assert response["data"]["project_id"] == "7"
    assert response["data"]["visible_pages"] == 2
    assert service.page_form.await_count == 2
    assert service.draft.await_count == 2
