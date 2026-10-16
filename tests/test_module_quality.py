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


def test_article_preflight_validates_planned_native_media_before_write():
    value = article()
    value.pop("images")
    value.pop("categories")
    result = module_quality.preflight_article(value, ["2"], image_count=1)
    assert result["ready_for_publication"] is True
    assert result["preview"] is True
    assert result["id"] == "preview"


def test_product_preflight_blocks_incomplete_offer_before_write():
    value = product()
    value.pop("images")
    value.pop("categories")
    result = module_quality.preflight_product(
        value, ["4"], [{"title": "Высота 6 м", "vendor_code": "T-6"}], image_count=1)
    assert result["ready_for_publication"] is False
    assert "product_offer_price_missing" in {item["code"] for item in result["blockers"]}


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


@pytest.mark.asyncio
async def test_module_preflight_tools_do_not_access_tobiz():
    service = SimpleNamespace(config=SimpleNamespace(read_only=False))
    functions = registered_functions(service)
    article_value = article()
    article_value.pop("images")
    article_value.pop("categories")
    article_response = await functions["tobiz_preflight_article"](
        fields=article_value, category_ids=["2"], image_count=1)
    product_value = product()
    product_value.pop("images")
    product_value.pop("categories")
    product_response = await functions["tobiz_preflight_product"](
        fields=product_value, category_ids=["4"], image_count=1)
    assert article_response["data"]["ready_for_publication"] is True
    assert product_response["data"]["ready_for_publication"] is True


@pytest.mark.asyncio
async def test_publish_article_package_previews_without_writing():
    service = SimpleNamespace(config=SimpleNamespace(read_only=False))
    value = article()
    value.pop("images")
    value.pop("categories")
    response = await registered_functions(service)["tobiz_publish_article_package"](
        fields=value, category_ids=["2"], images=[{"path": "cover.jpg"}], apply=False)
    assert response["ok"] is True
    assert response["data"]["ready_for_apply"] is True
    assert response["data"]["dry_run"] is True


@pytest.mark.asyncio
async def test_publish_article_package_builds_and_audits_complete_entity():
    value = article()
    fields = {key: item for key, item in value.items()
              if key not in {"id", "images", "categories"}}
    service = SimpleNamespace(
        config=SimpleNamespace(read_only=False),
        project=AsyncMock(return_value=SimpleNamespace(project_id="7")),
        module_create=AsyncMock(return_value={"id": "11"}),
        module_update=AsyncMock(),
        module_upload_image=AsyncMock(),
        module_get=AsyncMock(return_value={**value, "id": "11"}),
        module_delete=AsyncMock(),
    )
    response = await registered_functions(service)["tobiz_publish_article_package"](
        project_id="7", fields=fields, category_ids=["2"],
        images=[{"path": "cover.jpg"}], apply=True)
    assert response["ok"] is True
    assert response["data"]["published"] is True
    service.module_delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_product_package_rolls_back_on_offer_failure():
    value = product()
    fields = {key: item for key, item in value.items()
              if key not in {"id", "images", "categories"}}
    offers = [{"title": "Высота 6 м", "vendor_code": "T-6", "price": 24900}]
    service = SimpleNamespace(
        config=SimpleNamespace(read_only=False),
        project=AsyncMock(return_value=SimpleNamespace(project_id="7")),
        module_create=AsyncMock(return_value={"id": "12"}),
        module_update=AsyncMock(),
        module_upload_image=AsyncMock(),
        product_offer_create=AsyncMock(side_effect=RuntimeError("offer failed")),
        module_delete=AsyncMock(return_value={"deleted": True}),
    )
    response = await registered_functions(service)["tobiz_publish_product_package"](
        project_id="7", fields=fields, category_ids=["4"],
        images=[{"path": "product.jpg"}], offers=offers, apply=True)
    assert response["ok"] is False
    await_args = service.module_delete.await_args.args
    assert await_args == ("7", "item", "12")
