from tobiz_mcp.domain import multipage
import pytest


SITE_BRIEF = {
    "industry": "Создание сайтов", "offer": "Сайты для малого бизнеса",
    "audience": "Предприниматели", "contacts": "+7 900 000-00-00",
    "process": "Бриф, прототип, сборка, приемка", "proof": "Портфолио проектов",
    "primary_cta": "Обсудить проект",
}


def specs():
    return [
        {"key": "home", "title": "Главная", "slug": "", "is_home": True,
         "menu_title": "Главная", "purpose": "Объяснить предложение и привести к заявке"},
        {"key": "services", "title": "Услуги", "slug": "uslugi",
         "menu_title": "Услуги", "purpose": "Раскрыть состав и формат услуг"},
    ]


def plan(key, visual="clean_service", ready=True):
    return {
        "key": key, "template": {"visual_system": visual},
        "brief_readiness": {"ready_for_quality_build": ready},
        "architecture_readiness": {"ready": ready},
        "conversion_readiness": {"ready": ready},
    }


def test_valid_multipage_manifest_has_stable_routes_and_menu():
    result = multipage.validate(SITE_BRIEF, specs())
    assert result["ready_for_planning"] is True
    assert result["multipage_id"].startswith("multipage:")
    assert result["menu"] == [
        {"title": "Главная", "href": "/", "page_key": "home"},
        {"title": "Услуги", "href": "/uslugi/", "page_key": "services"},
    ]


def test_manifest_blocks_duplicate_routes_and_multiple_home_pages():
    pages = specs()
    pages[1]["slug"] = ""
    pages[1]["is_home"] = True
    result = multipage.validate(SITE_BRIEF, pages)
    codes = {item["code"] for item in result["blockers"]}
    assert result["ready_for_planning"] is False
    assert {"multipage_slug_duplicate", "multipage_home_count_invalid"} <= codes


def test_combined_plans_require_one_visual_system_and_ready_pages():
    manifest = multipage.validate(SITE_BRIEF, specs())
    ready = multipage.combine(manifest, [plan("home"), plan("services")])
    assert ready["ready_for_packages"] is True
    inconsistent = multipage.combine(
        manifest, [plan("home"), plan("services", visual="dark_tech", ready=False)])
    codes = {item["code"] for item in inconsistent["blockers"]}
    assert inconsistent["ready_for_packages"] is False
    assert {"multipage_visual_system_inconsistent",
            "multipage_page_plan_not_ready"} <= codes


def test_multipage_package_preserves_page_order_and_shared_menu():
    manifest = multipage.validate(SITE_BRIEF, specs())
    combined = multipage.combine(manifest, [plan("home"), plan("services")])
    nested = [
        {"key": "home", "title": "Главная", "package": {
            "package_id": "home:v1", "plan_id": "home"}},
        {"key": "services", "title": "Услуги", "package": {
            "package_id": "services:v1", "plan_id": "services"}},
    ]
    result = multipage.package(combined, nested)
    assert result["ready_to_fill"] is True
    assert result["menu"] == manifest["menu"]
    assert result["multipage_package_id"].endswith(":v1")


def test_multipage_progress_waits_for_every_page():
    menu_slots = {"recipe": {"slots": [
        {"kind": "link", "path": "/menu1/0/link", "value": "/"},
        {"kind": "link", "path": "/menu1/1/link", "value": "/uslugi/"},
    ]}}
    package_value = {"menu": [{"href": "/"}, {"href": "/uslugi/"}], "pages": [
        {"key": "home", "title": "Главная", "package": menu_slots},
        {"key": "services", "title": "Услуги", "package": menu_slots},
    ]}
    result = multipage.progress(package_value, [
        {"key": "home", "progress": {"completion_percent": 100,
                                       "ready_for_build": True,
                                       "next_action": "tobiz_build_site_package"}},
        {"key": "services", "progress": {"completion_percent": 40,
                                           "ready_for_build": False,
                                           "next_action": "tobiz_fill_package_content"}},
    ])
    assert result["ready_for_build"] is False
    assert result["pages_ready"] == 1
    assert result["completion_percent"] == 70
    assert result["next_action"] == "fill_incomplete_page_packages"


def test_navigation_requires_every_route_on_every_page():
    value = {"menu": [{"href": "/"}, {"href": "/uslugi/"}], "pages": [{
        "key": "home", "package": {"recipe": {"slots": [
            {"kind": "link", "path": "/menu1/0/link", "value": "/"},
        ]}},
    }]}
    result = multipage.validate_navigation(value)
    assert result["ready"] is False
    assert result["issues"][0]["code"] == "multipage_navigation_incomplete"
    assert result["issues"][0]["missing"] == ["/uslugi/"]


@pytest.mark.asyncio
async def test_transactional_build_rolls_back_created_pages_on_failure():
    rolled_back = []

    async def build(page):
        if page["key"] == "services":
            raise RuntimeError("upstream failed")
        return {"page": {"page_id": "101"}}

    async def rollback(page_id):
        rolled_back.append(page_id)

    with pytest.raises(RuntimeError, match="upstream failed"):
        await multipage.transactional_build(
            [{"key": "home"}, {"key": "services"}], build, rollback)
    assert rolled_back == ["101"]
