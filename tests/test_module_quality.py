from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain import module_quality
from tobiz_mcp.tools import register


def article():
    return {
        "id": "1", "title": "Как выбрать программу обучения для ребенка",
        "dir": "programma-obucheniya-rebenka",
        "short_description": ("Разбираем критерии выбора программы, формат занятий и вопросы, "
                              "которые стоит задать преподавателю до начала обучения."),
        "description": "<h2>Цели обучения</h2><p>" + "Полезный текст " * 105 +
                       "</p><h2>Формат занятий</h2><p>Практические рекомендации.</p>",
        "seo_title": "Как выбрать программу обучения для ребенка",
        "seo_description": ("Практическое руководство для родителей: как оценить программу, формат "
                            "занятий, преподавателя и ожидаемый результат обучения ребенка."),
        "images": [{"id": "10"}], "categories": ["2"],
    }


def product():
    return {
        "id": "2", "title": "Комплект тестера дымовых извещателей",
        "dir": "komplekt-testera-dymovyh-izveshchateley", "price": 24900,
        "short_description": ("Готовый комплект для функциональной проверки дымовых пожарных "
                              "извещателей на объектах."),
        "description": "Комплектация, совместимость и порядок применения. " * 12,
        "seo_title": "Комплект тестера дымовых пожарных извещателей",
        "seo_description": ("Комплект оборудования для функциональной проверки дымовых пожарных "
                            "извещателей. Характеристики, состав, цена и условия поставки."),
        "images": [{"id": "20"}], "categories": ["4"],
    }


def test_complete_article_is_ready_for_publication():
    result = module_quality.audit_article(article())
    assert result["ready_for_publication"] is True
    assert result["score"] >= 7
    assert result["metrics"]["headings"] == 2


def test_article_audit_blocks_thin_unstructured_placeholder():
    result = module_quality.audit_article({
        "id": "1", "title": "Заголовок", "description": "Текст",
        "short_description": "Описание", "dir": "", "images": [],
    })
    codes = {item["code"] for item in result["blockers"]}
    assert {"article_title_weak", "article_excerpt_weak", "article_body_too_short",
            "article_image_missing", "module_slug_invalid", "module_seo_title_length",
            "module_seo_description_length"} <= codes


def test_complete_product_and_unique_offers_are_ready():
    offers = [
        {"title": "Высота 6 м", "vendor_code": "T-6", "price": 24900},
        {"title": "Высота 9 м", "vendor_code": "T-9", "price": 32900},
    ]
    result = module_quality.audit_product(product(), offers)
    assert result["ready_for_publication"] is True
    assert result["metrics"]["offers"] == 2


def test_product_audit_blocks_missing_commerce_and_duplicate_offers():
    value = product()
    value.update({"price": 0, "images": [], "categories": [], "video1": "youtube/id"})
    offers = [
        {"title": "Размер M", "vendor_code": "SKU"},
        {"title": "Размер M", "vendor_code": "SKU"},
    ]
    result = module_quality.audit_product(value, offers)
    codes = {item["code"] for item in result["blockers"]}
    assert {"product_image_missing", "product_category_missing", "product_video_url_invalid",
            "product_offer_title_duplicate", "product_offer_vendor_code_duplicate",
            "product_offer_price_missing"} <= codes


def test_product_price_on_request_can_be_explicitly_allowed():
    value = product()
    value["price"] = 0
    result = module_quality.audit_product(value, allow_price_on_request=True)
    assert "product_price_missing" not in {item["code"] for item in result["issues"]}


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


@pytest.mark.asyncio
async def test_article_audit_tool_reads_native_entity():
    service = SimpleNamespace(
        config=SimpleNamespace(read_only=False),
        project=AsyncMock(return_value=SimpleNamespace(project_id="7")),
        module_get=AsyncMock(return_value=article()),
    )
    response = await registered_functions(service)["tobiz_audit_article"](
        project_id="7", article_id="1")
    assert response["ok"] is True
    assert response["data"]["ready_for_publication"] is True
    service.module_get.assert_awaited_once_with("7", "article", "1")


@pytest.mark.asyncio
async def test_product_audit_tool_reads_offers():
    offers = [{"title": "Высота 6 м", "vendor_code": "T-6", "price": 24900}]
    service = SimpleNamespace(
        config=SimpleNamespace(read_only=False),
        project=AsyncMock(return_value=SimpleNamespace(project_id="7")),
        module_get=AsyncMock(return_value=product()),
        product_offers=AsyncMock(return_value=offers),
    )
    response = await registered_functions(service)["tobiz_audit_product"](
        project_id="7", product_id="2")
    assert response["ok"] is True
    assert response["data"]["ready_for_publication"] is True
    service.product_offers.assert_awaited_once_with("7", "2")
