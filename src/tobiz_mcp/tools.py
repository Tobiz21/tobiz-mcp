"""MCP-инструменты: тонкий слой над Service (схемы, валидация, формат ответов).

Имена инструментов нейтральны по возможности (tobiz_*), не по потребителю.
"""

from __future__ import annotations

import functools
import time
from typing import Annotated, Any, Callable

from . import errors, log
from .domain import blocks as block_domain
from .domain import claim_audit as claim_audit_domain
from .domain import content as content_domain
from .domain import composition as composition_domain
from .domain import design_gate as design_gate_domain
from .domain import image_audit as image_audit_domain
from .domain import site_plan as site_plan_domain
from .domain import template as template_domain
from .domain import audit as audit_domain
from .domain import design as design_domain
from .domain import design_reference as design_reference_domain
from .domain import layout as layout_domain
from .domain import refinement as refinement_domain
from .service import Service

logger = log.get("tools")

from pydantic import BeforeValidator, WithJsonSchema

SCHEMA_VERSION = 1

# Идентификаторы конструктора — строки, но LLM-клиенты естественно передают числа, и клиентская
# валидация по JSON-схеме отсекает int у поля с типом string. Поэтому схема объявляет оба типа
# (WithJsonSchema), а BeforeValidator приводит значение к строке до бизнес-логики.
Id = Annotated[
    str,
    BeforeValidator(lambda value: "" if value is None else str(value)),
    WithJsonSchema({"type": ["string", "integer"]}),
]
READ_TOOLS = {
    "tobiz_page_content", "tobiz_template_passport", "tobiz_prepare_template",
    "tobiz_login", "tobiz_session_status", "tobiz_health", "tobiz_diagnostics",
    "tobiz_onboarding_check",
    "tobiz_list_projects",
    "tobiz_list_pages", "tobiz_page_summary", "tobiz_list_blocks", "tobiz_get_block",
    "tobiz_search_blocks", "tobiz_describe_block", "tobiz_verify_page", "tobiz_refresh_assets",
    "tobiz_page_info", "tobiz_audit_catalog", "tobiz_block_controls",
    "tobiz_list_articles", "tobiz_get_article",
    "tobiz_list_article_categories", "tobiz_list_products", "tobiz_get_product",
    "tobiz_list_product_categories",
    "tobiz_get_site_styles", "tobiz_get_computed_styles", "tobiz_screenshot_page",
    "tobiz_diagnose_interactions", "tobiz_audit_page", "tobiz_audit_summary", "tobiz_list_product_offers",
    "tobiz_get_product_offer",
    "tobiz_list_page_backups",
    "tobiz_design_library", "tobiz_select_design",
    "tobiz_editor_roundtrip_check",
    "tobiz_improve_page",
    "tobiz_layout_registry", "tobiz_repair_layout",
    "tobiz_refine_design",
    "tobiz_audit_composition",
    "tobiz_compare_design_reference", "tobiz_release_design_gate", "tobiz_audit_images",
    "tobiz_plan_site", "tobiz_compile_site_content", "tobiz_validate_site_recipe",
    "tobiz_validate_media_recipe", "tobiz_prepare_site_package", "tobiz_preflight_site_build",
    "tobiz_build_site_package",
    "tobiz_audit_claims", "tobiz_check_site_plan",
}


def _envelope(data: Any, started: float, **extra: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "duration_ms": int((time.time() - started) * 1000),
    }
    meta.update(extra)
    return {"ok": True, "data": data, "meta": meta}


def _error(exc: Exception, started: float) -> dict[str, Any]:
    if isinstance(exc, errors.TobizError):
        payload = exc.to_dict()
    else:  # неожиданное — не показываем трассу агенту, но логируем
        logger.exception("необработанная ошибка")
        payload = {"code": errors.INTERNAL, "message": str(exc)}
    return {"ok": False, "error": payload,
            "meta": {"schema_version": SCHEMA_VERSION,
                     "duration_ms": int((time.time() - started) * 1000)}}


def wrap(func: Callable[..., Any], *, tool_name: str = "",
         metric_recorder: Callable[[str, bool, int, str | None], None] | None = None
         ) -> Callable[..., Any]:
    """Оборачивает метод сервиса в конверт {ok, data|error, meta}.

    Важно: functools.wraps сохраняет сигнатуру исходной функции (`__wrapped__`), иначе MCP
    построит схему инструмента из `*args/**kwargs` и клиент не сможет передать параметры.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        started = time.time()
        try:
            result = await func(*args, **kwargs)
            duration_ms = int((time.time() - started) * 1000)
            ok = not (isinstance(result, dict) and result.get("ok") is False)
            if metric_recorder:
                metric_recorder(tool_name, ok, duration_ms, None if ok else errors.INTERNAL)
            if isinstance(result, dict) and "ok" in result:
                return result
            return _envelope(result, started)
        except Exception as exc:  # noqa: BLE001 — конверт нужен всегда
            if metric_recorder:
                code = exc.code if isinstance(exc, errors.TobizError) else errors.INTERNAL
                metric_recorder(tool_name, False, int((time.time() - started) * 1000), code)
            return _error(exc, started)

    return wrapper


def register(mcp: Any, service: Service) -> list[str]:
    """Регистрирует инструменты и возвращает список их имён."""
    read_only = service.config.read_only
    registered: list[str] = []

    def tool(name: str, description: str):
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            if read_only and name not in READ_TOOLS:
                return func
            recorder = getattr(service, "record_tool_metric", None)
            mcp.tool(name=name, description=description)(
                wrap(func, tool_name=name, metric_recorder=recorder))
            registered.append(name)
            return func
        return decorator

    # --- служебные ---

    @tool("tobiz_login",
          "Войти в конструктор (или принудительно обновить сессию). Возвращает состояние сессии "
          "без значений cookie.")
    async def tobiz_login(force: bool = True) -> dict[str, Any]:
        return await service.login(force=force)

    @tool("tobiz_session_status",
          "Состояние сессии конструктора: есть ли cookie, когда проверялись, какой user_id.")
    async def tobiz_session_status() -> dict[str, Any]:
        return await service.session_status()

    @tool("tobiz_health",
          "Версия сервиса, режимы, состояние сессии, доступность рендерера, счётчики ошибок.")
    async def tobiz_health() -> dict[str, Any]:
        return await service.health()

    @tool("tobiz_diagnostics",
          "Локальный обезличенный технический отчет: агрегаты вызовов и ошибок, длительность, "
          "состояние сессии/рендерера, число резервных копий и операций аудита. Не содержит "
          "пароли, cookie или содержимое страниц и ничего не отправляет наружу.")
    async def tobiz_diagnostics() -> dict[str, Any]:
        return service.diagnostics()

    @tool("tobiz_onboarding_check",
          "Безопасная проверка подключения перед началом работы: сессия, рендерер, изоляция "
          "проектов и доступ. Если передать project_id и page_id, дополнительно выполняет "
          "read-only проверку пересохранения страницы. Ничего не изменяет.")
    async def tobiz_onboarding_check(project_id: Id | None = None,
                                     page_id: Id | None = None) -> dict[str, Any]:
        return await service.onboarding_check(project_id, page_id)

    @tool("tobiz_design_library",
          "Machine-readable library of installed native TOBIZ template passports and visual references. "
          "Returns source project/page IDs, structure density, Flex share, strengths and image dependency.")
    async def tobiz_design_library() -> dict[str, Any]:
        return design_domain.library()

    @tool("tobiz_select_design",
          "Rank installed native templates for a website brief. brief may include industry, offer, audience, "
          "goal, needs/features, visual_system, page_length and photo_quality. Returns an explainable choice, "
          "alternatives, risks and visual references; does not copy or change a site.")
    async def tobiz_select_design(brief: dict[str, Any], top_k: int = 3) -> dict[str, Any]:
        try:
            return design_domain.select(brief, top_k)
        except (TypeError, ValueError) as exc:
            raise errors.TobizError(errors.BAD_ARGUMENT, str(exc)) from exc

    @tool("tobiz_editor_roundtrip_check",
          "Read-only simulation of a TOBIZ visual-editor save. Renders every native block and validates "
          "payload order/cache, block availability, anchors, visibility, forms and Flex share. Never saves.")
    async def tobiz_editor_roundtrip_check(project_id: Id | None = None,
                                           page_id: Id = "") -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.editor_roundtrip(project_id, page_id)

    @tool("tobiz_layout_registry",
          "Build a project-specific registry of native TOBIZ layout controls from vendor block metadata. "
          "Returns controls, options, dependencies and whether each control is safe for automatic repair. "
          "Optionally filter by type_ids. Read-only.")
    async def tobiz_layout_registry(project_id: Id | None = None,
                                    type_ids: list[Id] | None = None) -> dict[str, Any]:
        project, _ = await service.pages(project_id)
        types = await service.block_types(project.project_id)
        return layout_domain.registry(types, [str(value) for value in type_ids or []])

    # --- чтение структуры ---

    @tool("tobiz_list_projects",
          "Список проектов (сайтов) аккаунта: project_id, название, адрес сайта, число страниц. "
          "project_id нужен всем остальным инструментам.")
    async def tobiz_list_projects(include_pages: bool = False,
                                  refresh: bool = False) -> dict[str, Any]:
        projects = await service.projects(refresh=refresh)
        return {
            "projects": [p.to_dict(service.config.lp_template, include_pages) for p in projects],
            "count": len(projects),
        }

    @tool("tobiz_install_template",
          "Установить бесплатный штатный шаблон TOBIZ как отдельный проект. "
          "По умолчанию только проверяет план; apply=true создает проект. "
          "Платные шаблоны никогда не покупает автоматически.")
    async def tobiz_install_template(template_id: Id, template_page_id: Id,
                                     multipage: bool = False,
                                     apply: bool = False) -> dict[str, Any]:
        return await service.install_template(template_id, template_page_id,
                                              multipage=multipage, apply=apply)

    @tool("tobiz_list_pages",
          "Страницы проекта: page_id (он же v в адресе редактора), название, slug, видимость, "
          "ссылка редактора.")
    async def tobiz_list_pages(project_id: Id | None = None,
                               refresh: bool = False) -> dict[str, Any]:
        project, pages = await service.pages(project_id, refresh=refresh)
        return {
            "project_id": project.project_id,
            "pages": [p.to_dict(service.config.lp_template, project.project_id) for p in pages],
            "count": len(pages),
        }

    @tool("tobiz_list_blocks",
          "Блоки страницы в порядке отображения: block_id, type_id, название типа, позиция, "
          "признак правки в черновике. values=true добавляет значения полей.")
    async def tobiz_list_blocks(project_id: Id | None = None, page_id: Id = "",
                                values: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        types = await service.block_types(project_id)
        items = []
        for block_id in draft.order:
            block = draft.blocks[block_id]
            block_type = types.get(block.type_id)
            item = {
                "block_id": block.block_id,
                "type_id": block.type_id,
                "type_title": block_type.title if block_type else "",
                "position": block.position,
                "sort_id": block.sort_id,
                "deleted": block.deleted,
                "changed": bool(block.changed_paths) or block.origin == "created",
            }
            if values:
                item["values"] = block.values
            items.append(item)
        return {"page_id": page_id, "blocks": items, "count": len(items),
                "pending_changes": draft.changed_blocks}

    @tool("tobiz_get_block",
          "Значения полей блока. with_schema=true добавляет подписи и типы полей.")
    async def tobiz_get_block(project_id: Id | None = None, page_id: Id = "",
                              block_id: Id = "", with_schema: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        block = draft.blocks.get(str(block_id))
        if block is None:
            raise errors.TobizError(errors.NOT_FOUND, f"Блок {block_id} не найден на странице",
                                    "Состав страницы: tobiz_list_blocks")
        data: dict[str, Any] = {
            "block_id": block.block_id,
            "type_id": block.type_id,
            "values": block.values,
            "changed": bool(block.changed_paths) or block.origin == "created",
        }
        if with_schema:
            block_type = await service.type_or_raise(project_id, block.type_id)
            data["schema"] = block_domain.field_schema(block_type, block.values)
        return data

    @tool("tobiz_page_summary",
          "Компактная карта страницы: порядок блоков и короткий текст каждого — экономит контекст.")
    async def tobiz_page_summary(project_id: Id | None = None, page_id: Id = "",
                                 max_chars_per_block: int = 160) -> dict[str, Any]:
        project_id, page = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        types = await service.block_types(project_id)
        summary = []
        for block_id in draft.order:
            block = draft.blocks[block_id]
            block_type = types.get(block.type_id)
            summary.append({
                "block_id": block.block_id,
                "type_id": block.type_id,
                "type_title": block_type.title if block_type else "",
                "snippet": _snippet(block.values, max_chars_per_block),
                "changed": bool(block.changed_paths) or block.origin == "created",
            })
        return {"project_id": project_id, "page_id": page_id, "title": page.title,
                "url": page.url, "seo": service.page_info(draft), "blocks": summary}

    @tool("tobiz_search_blocks",
          "Поиск по библиотеке блоков: русский текст ищется в названии и описании типа, "
          "можно отфильтровать по категории или точному type_id.")
    async def tobiz_search_blocks(project_id: Id | None = None, query: str = "",
                                  category_id: Id = "", type_id: Id = "",
                                  limit: int = 20, offset: int = 0) -> dict[str, Any]:
        project = await service.project(project_id)
        types = await service.block_types(project.project_id)
        limit = max(1, min(int(limit or 20), 100))
        total, items = service.catalog.search(types, query, category_id, type_id, limit, offset)
        return {"total": total, "limit": limit, "offset": offset,
                "items": [t.to_public() for t in items]}

    @tool("tobiz_describe_block",
          "Схема полей типа блока: имена, русские подписи, типы, значения по умолчанию и текущие. "
          "only=changed — только поля, отличающиеся от дефолта. Достаточно указать type_id "
          "либо пару page_id + block_id (тип возьмётся из блока).")
    async def tobiz_describe_block(project_id: Id | None = None, type_id: Id = "",
                                   page_id: Id = "", block_id: Id = "",
                                   only: str = "all") -> dict[str, Any]:
        project = await service.project(project_id)
        current: dict[str, Any] = {}
        if not type_id:
            if not (page_id and block_id):
                raise errors.TobizError(
                    errors.BAD_ARGUMENT,
                    "Укажите type_id либо пару page_id + block_id",
                    "Список типов: tobiz_search_blocks; состав страницы: tobiz_list_blocks",
                )
            await service.resolve_page(project.project_id, page_id)
            draft = await service.draft(project.project_id, page_id)
            block = draft.blocks.get(str(block_id))
            if block is None:
                raise errors.TobizError(errors.NOT_FOUND, f"Блок {block_id} не найден на странице")
            type_id = block.type_id
        block_type = await service.type_or_raise(project.project_id, type_id)
        if page_id and block_id:
            await service.resolve_page(project.project_id, page_id)
            draft = await service.draft(project.project_id, page_id)
            block = draft.blocks.get(str(block_id))
            if block is None:
                raise errors.TobizError(errors.NOT_FOUND, f"Блок {block_id} не найден на странице")
            current = block.values
        schema = block_domain.field_schema(block_type, current, only=only)
        if not current:
            schema["defaults_from_server"] = bool(
                await service.catalog.default_values(project.project_id, block_type))
        return schema

    @tool("tobiz_refresh_assets",
          "Принудительно перекачать библиотеку блоков и каталог проекта (если вендор обновил сборку).")
    async def tobiz_refresh_assets(project_id: Id | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        index = await service.catalog.ensure_assets(project.project_id, force=True)
        types = await service.block_types(project.project_id)
        return {"project_id": project.project_id, "files": index.get("files", {}),
                "types": len(types)}

    @tool("tobiz_audit_catalog",
          "Без записи на сайт прогнать рендер всех типов блоков либо выбранных type_ids: "
          "дефолт, оба состояния checkbox и все варианты select. Возвращает несовместимые "
          "шаблоны и функции рантайма.")
    async def tobiz_audit_catalog(project_id: Id | None = None,
                                  type_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        result = await service.audit_catalog(project.project_id, list(type_ids or []))
        failures = result.get("failures") or []
        result["failures"] = failures[:200]
        result["failures_truncated"] = max(0, len(failures) - 200)
        return result

    @tool("tobiz_block_controls",
          "Реестр штатных галочек и списков выбора для каждого типа блока. Возвращает русскую "
          "подпись, имя поля, значение по умолчанию, зависимости, варианты select и все "
          "визуальные варианты блока из палитры. control_type: checkbox, select, interactive "
          "или all. Для проверки обоих состояний используйте tobiz_audit_catalog.")
    async def tobiz_block_controls(project_id: Id | None = None, type_id: Id = "",
                                   category_id: Id = "", query: str = "",
                                   control_type: str = "interactive", limit: int = 50,
                                   offset: int = 0) -> dict[str, Any]:
        project = await service.project(project_id)
        allowed = {"checkbox", "select", "interactive", "all"}
        normalized = (control_type or "interactive").strip().lower()
        if normalized not in allowed:
            raise errors.TobizError(
                errors.BAD_ARGUMENT, f"Неизвестный control_type: {control_type}",
                "Допустимо: checkbox, select, interactive, all",
            )
        return await service.block_controls(
            project.project_id, type_id=str(type_id or ""),
            category_id=str(category_id or ""), query=query,
            control_type=normalized, limit=limit, offset=offset,
        )

    # --- статьи ---

    @tool("tobiz_list_articles",
          "Список статей проекта с фильтром категории, поиском и пагинацией.")
    async def tobiz_list_articles(project_id: Id | None = None, limit: int = 30,
                                  page: int = 1, category: Id = "all",
                                  search: str = "", order_by: str = "sort_id") -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_list(project.project_id, "article", limit=limit, page=page,
                                         category=category, search=search, order_by=order_by)

    @tool("tobiz_get_article",
          "Полная статья: текст CKEditor, краткое описание, SEO, категории и изображения.")
    async def tobiz_get_article(project_id: Id | None = None,
                                article_id: Id = "") -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_get(project.project_id, "article", article_id)

    @tool("tobiz_list_article_categories", "Категории статей проекта.")
    async def tobiz_list_article_categories(project_id: Id | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        categories = await service.module_categories(project.project_id, "article")
        return {"categories": categories, "count": len(categories)}

    @tool("tobiz_create_article",
          "Создать статью штатным редактором TOBIZ и сразу заполнить поля. description и "
          "short_description принимают HTML CKEditor, включая штатные iframe видео.")
    async def tobiz_create_article(project_id: Id | None = None,
                                   fields: dict[str, Any] | None = None,
                                   category_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        article = await service.module_create(project.project_id, "article")
        if fields or category_ids is not None:
            article = await service.module_update(project.project_id, "article", str(article["id"]),
                                                  fields or {}, list(category_ids or []))
        return article

    @tool("tobiz_update_article",
          "Изменить статью. Поддерживаются title, dir, description, short_description, SEO, "
          "publication_date, sort_id, visible и полный список category_ids.")
    async def tobiz_update_article(project_id: Id | None = None, article_id: Id = "",
                                   fields: dict[str, Any] | None = None,
                                   category_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_update(project.project_id, "article", article_id,
                                           fields or {}, None if category_ids is None
                                           else list(category_ids))

    @tool("tobiz_upload_article_image",
          "Загрузить изображение в галерею статьи из path или content_base64.")
    async def tobiz_upload_article_image(project_id: Id | None = None,
                                         article_id: Id = "", path: str | None = None,
                                         content_base64: str | None = None,
                                         file_name: str | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_upload_image(project.project_id, "article", article_id,
                                                 path, content_base64, file_name)

    @tool("tobiz_sort_article_images",
          "Изменить порядок изображений статьи штатной сортировкой TOBIZ. Передайте все image_ids.")
    async def tobiz_sort_article_images(project_id: Id | None = None, article_id: Id = "",
                                        image_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_sort_images(project.project_id, "article", article_id,
                                                list(image_ids or []))

    @tool("tobiz_delete_article",
          "Удалить статью сразу. Требует confirm=true.")
    async def tobiz_delete_article(project_id: Id | None = None, article_id: Id = "",
                                   confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    "Удаление статьи требует confirm=true")
        project = await service.project(project_id)
        return await service.module_delete(project.project_id, "article", article_id)

    # --- товары ---

    @tool("tobiz_list_products",
          "Список товаров проекта с фильтром категории, поиском, сортировкой и пагинацией.")
    async def tobiz_list_products(project_id: Id | None = None, limit: int = 30,
                                  page: int = 1, category: Id = "all",
                                  search: str = "", order_by: str = "sort_id") -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_list(project.project_id, "item", limit=limit, page=page,
                                         category=category, search=search, order_by=order_by)

    @tool("tobiz_get_product",
          "Полная карточка товара: цены, остаток, текст, SEO, видео, категории, фото и свойства.")
    async def tobiz_get_product(project_id: Id | None = None,
                                product_id: Id = "") -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_get(project.project_id, "item", product_id)

    @tool("tobiz_list_product_categories", "Категории интернет-магазина проекта.")
    async def tobiz_list_product_categories(project_id: Id | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        categories = await service.module_categories(project.project_id, "item")
        return {"categories": categories, "count": len(categories)}

    @tool("tobiz_create_product",
          "Создать товар штатным редактором TOBIZ и сразу заполнить карточку.")
    async def tobiz_create_product(project_id: Id | None = None,
                                   fields: dict[str, Any] | None = None,
                                   category_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        product = await service.module_create(project.project_id, "item")
        if fields or category_ids is not None:
            product = await service.module_update(project.project_id, "item", str(product["id"]),
                                                  fields or {}, list(category_ids or []))
        return product

    @tool("tobiz_update_product",
          "Изменить карточку товара: тексты, URL, SEO, цену, скидку, остаток, размеры, метки, "
          "video1-video3, видимость и категории.")
    async def tobiz_update_product(project_id: Id | None = None, product_id: Id = "",
                                   fields: dict[str, Any] | None = None,
                                   category_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_update(project.project_id, "item", product_id,
                                           fields or {}, None if category_ids is None
                                           else list(category_ids))

    @tool("tobiz_upload_product_image",
          "Загрузить изображение в галерею товара из path или content_base64.")
    async def tobiz_upload_product_image(project_id: Id | None = None,
                                         product_id: Id = "", path: str | None = None,
                                         content_base64: str | None = None,
                                         file_name: str | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_upload_image(project.project_id, "item", product_id,
                                                 path, content_base64, file_name)

    @tool("tobiz_sort_product_images",
          "Изменить порядок изображений товара штатной сортировкой TOBIZ. Передайте все image_ids.")
    async def tobiz_sort_product_images(project_id: Id | None = None, product_id: Id = "",
                                        image_ids: list[Id] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.module_sort_images(project.project_id, "item", product_id,
                                                list(image_ids or []))

    @tool("tobiz_list_product_offers", "Список вариантов (offers) товара.")
    async def tobiz_list_product_offers(project_id: Id | None = None,
                                        product_id: Id = "") -> dict[str, Any]:
        project = await service.project(project_id)
        offers = await service.product_offers(project.project_id, product_id)
        return {"offers": offers, "count": len(offers)}

    @tool("tobiz_get_product_offer", "Получить вариант товара: название, артикул, цену, остаток и фото.")
    async def tobiz_get_product_offer(project_id: Id | None = None,
                                      offer_id: Id = "") -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.product_offer_get(project.project_id, offer_id)

    @tool("tobiz_create_product_offer",
          "Создать штатный вариант товара. fields: title, vendor_code, price, quantity, image_id.")
    async def tobiz_create_product_offer(project_id: Id | None = None, product_id: Id = "",
                                         fields: dict[str, Any] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.product_offer_create(project.project_id, product_id, fields)

    @tool("tobiz_update_product_offer",
          "Изменить штатный вариант товара. fields: title, vendor_code, price, quantity, image_id.")
    async def tobiz_update_product_offer(project_id: Id | None = None, offer_id: Id = "",
                                         fields: dict[str, Any] | None = None) -> dict[str, Any]:
        project = await service.project(project_id)
        return await service.product_offer_update(project.project_id, offer_id, fields or {})

    @tool("tobiz_delete_product_offer", "Удалить вариант товара. Требует confirm=true.")
    async def tobiz_delete_product_offer(project_id: Id | None = None, offer_id: Id = "",
                                         confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise errors.TobizError(errors.BAD_ARGUMENT, "Удаление варианта требует confirm=true")
        project = await service.project(project_id)
        return await service.product_offer_delete(project.project_id, offer_id)

    @tool("tobiz_delete_product", "Удалить товар сразу. Требует confirm=true.")
    async def tobiz_delete_product(project_id: Id | None = None, product_id: Id = "",
                                   confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    "Удаление товара требует confirm=true")
        project = await service.project(project_id)
        return await service.module_delete(project.project_id, "item", product_id)

    # --- запись ---

    @tool("tobiz_add_block",
          "Добавить блок из библиотеки на страницу (в конец или после указанного блока). "
          "Блок попадает в черновик: на сайте появится после tobiz_save_page.")
    async def tobiz_add_block(project_id: Id | None = None, page_id: Id = "",
                              type_id: Id = "", after_block_id: Id = "",
                              values: dict[str, Any] | None = None) -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        project_id, _ = await service.resolve_page(project_id, page_id)
        block_type = await service.type_or_raise(project_id, type_id)
        draft = await service.draft(project_id, page_id)
        server_defaults = await service.catalog.default_values(project_id, block_type)
        base = service.merged_values(block_type, {}, server_defaults)
        if values:
            block_domain.validate_values(block_type, values)
            merged, changed = block_domain.apply_edits(base, values)
        else:
            merged, changed = base, []
        envelope = await service.client.editor_ajax(
            "CreateNewBlock", service.config.lp_base(project_id), page_id,
            rep_id=page_id, type_id=block_type.type_id)
        if not envelope.ok:
            raise errors.TobizError(
                errors.SAVE_FAILED,
                f"Конструктор не создал блок: {envelope.message or envelope.status}",
                "Повторите попытку; при устойчивой ошибке проверьте тариф/лимиты аккаунта",
            )
        created = envelope.payload.get("respons")
        block_id = ""
        if isinstance(created, str):
            try:
                import json
                block_id = str(json.loads(created).get("block_id") or "")
            except Exception:  # noqa: BLE001
                block_id = ""
        if not block_id:
            raise errors.TobizError(errors.SAVE_FAILED,
                                    "Конструктор не вернул block_id нового блока",
                                    raw=envelope.raw_text[:300])
        block = draft.add_created(block_id, block_type.type_id, merged,
                                  after_block_id or None)
        block.changed_paths = changed
        return {"block_id": block.block_id, "type_id": block.type_id, "sort_id": block.sort_id,
                "changed_fields": changed, "pending_save": True}

    @tool("tobiz_update_block",
          "Изменить поля блока: values — слияние по именам полей, set — точечные правки путями "
          "(например /arr1/0/title). Непереданные поля не теряются.")
    async def tobiz_update_block(project_id: Id | None = None, page_id: Id = "",
                                 block_id: Id = "", values: dict[str, Any] | None = None,
                                 set: list[dict[str, Any]] | None = None,
                                 replace: bool = False) -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        if not values and not set:
            raise errors.TobizError(errors.BAD_ARGUMENT, "Передайте values или set")
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        block = draft.blocks.get(str(block_id))
        if block is None:
            raise errors.TobizError(errors.NOT_FOUND, f"Блок {block_id} не найден на странице",
                                    "Состав страницы: tobiz_list_blocks")
        block_type = await service.type_or_raise(project_id, block.type_id)
        if values:
            block_domain.validate_values(block_type, values)
        merged, changed = block_domain.apply_edits(block.values, values, set, replace)
        block.values = merged
        for path in changed:
            if path not in block.changed_paths:
                block.changed_paths.append(path)
        return {"block_id": block.block_id, "changed_fields": changed,
                "change_hash": draft.change_hash()}

    @tool("tobiz_page_content", "Read all editable content in one call with a draft hash. Does not change layout.")
    async def tobiz_page_content(project_id: Id | None = None, page_id: Id = "") -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return content_domain.content_map(await service.draft(project_id, page_id))

    @tool("tobiz_template_passport", "Read content roles, image requirements and conservative "
          "mobile text-length guidance before filling a native template.")
    async def tobiz_template_passport(project_id: Id | None = None,
                                      page_id: Id = "") -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return content_domain.passport(await service.draft(project_id, page_id))

    @tool("tobiz_prepare_template", "Preview deterministic native fixes for a copied template. "
          "With apply=true, stage them in the draft without saving. Fixes broken button anchors "
          "when a native form is available, keeps gallery labels visible, and hides empty social links.")
    async def tobiz_prepare_template(project_id: Id | None = None, page_id: Id = "",
                                     expected_hash: str = "", apply: bool = False) -> dict[str, Any]:
        if apply and service.config.read_only:
            raise errors.read_only()
        if not expected_hash:
            raise errors.TobizError(errors.BAD_ARGUMENT, "Hash required")
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        candidate, changes, warnings = template_domain.prepare_template(draft, expected_hash)
        if apply and changes:
            service.drafts.put(candidate)
        return {"preview": not apply, "changes": changes, "warnings": warnings,
                "hash": content_domain.fingerprint(candidate)}

    @tool("tobiz_apply_content", "Validate a whole content batch before changing the draft. Preview by default. "
          "Use apply=true to stage; save=true additionally saves once. Requires hash from tobiz_page_content. "
          "replacement_image replaces populated image fields with a previously uploaded native filename. "
          "Layout and block order are preserved. Hash guards this MCP draft, not concurrent browser edits.")
    async def tobiz_apply_content(project_id: Id | None = None, page_id: Id = "",
                                  expected_hash: str = "", edits: list[dict[str, Any]] | None = None,
                                  replacement_image: str | None = None, apply: bool = False,
                                  save: bool = False, recipe: dict[str, Any] | None = None,
                                  prepare_template: bool = False) -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        if not expected_hash or (save and not apply):
            raise errors.TobizError(errors.BAD_ARGUMENT, "Hash required; save requires apply=true")
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        if save and draft.has_changes:
            raise errors.TobizError(errors.CONFLICT, "Save or discard existing draft edits before batch save")
        if recipe is not None and edits:
            raise errors.TobizError(errors.BAD_ARGUMENT, "Use either recipe or edits")
        prepared, template_changes, warnings = (
            template_domain.prepare_template(draft, expected_hash)
            if prepare_template else (draft, [], [])
        )
        batch = content_domain.recipe_edits(prepared, recipe) if recipe is not None else edits or []
        candidate, changes = content_domain.prepare(
            prepared, batch, replacement_image, None if prepare_template else expected_hash)
        if prepare_template:
            candidate, post_changes, post_warnings = template_domain.prepare_template(candidate)
            template_changes += post_changes
            warnings += post_warnings
        result = {"preview": not apply, "changes": changes, "changed_fields": len(changes),
                  "template_changes": template_changes, "warnings": warnings,
                  "hash": content_domain.fingerprint(candidate), "saved": False}
        if apply and (changes or template_changes):
            service.drafts.put(candidate)
            if save:
                result["save_result"] = await service.save_page(project_id, page_id)
                result["saved"] = not service.config.dry_run
        return result

    @tool("tobiz_delete_block",
          "Удалить блок со страницы (в черновике; на сайте — после tobiz_save_page).")
    async def tobiz_delete_block(project_id: Id | None = None, page_id: Id = "",
                                 block_id: Id = "") -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        draft.remove_block(str(block_id))
        return {"block_id": str(block_id), "deleted": True,
                "change_hash": draft.change_hash()}

    @tool("tobiz_move_block",
          "Изменить порядок блоков: position (индекс с нуля) или after_block_id.")
    async def tobiz_move_block(project_id: Id | None = None, page_id: Id = "",
                               block_id: Id = "", position: int | None = None,
                               after_block_id: Id = "") -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        order = draft.move_block(str(block_id), position, after_block_id or None)
        return {"order": order, "change_hash": draft.change_hash()}

    @tool("tobiz_page_info",
          "Параметры страницы как в панели: название, URL (slug), SEO-заголовок, описание, "
          "ключевые слова, картинка для соцсетей, доступ по паролю. Читается из формы панели.")
    async def tobiz_page_info(project_id: Id | None = None, page_id: Id = "") -> dict[str, Any]:
        project_id, page = await service.resolve_page(project_id, page_id)
        form = await service.page_form(project_id, page_id)
        return {"project_id": project_id, "page_id": page_id, "title": page.title,
                "url": page.url, "visible": page.visible, "page": form.to_dict()}

    @tool("tobiz_get_site_styles",
          "Глобальные стили страницы из штатного page_config: шрифты текста/заголовков/меню и цвета кнопок.")
    async def tobiz_get_site_styles(project_id: Id | None = None,
                                    page_id: Id = "", refresh: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return {"page_id": page_id, "styles": await service.site_styles(project_id, page_id, refresh)}

    @tool("tobiz_update_site_styles",
          "Изменить штатный page_config. Поддерживает text/title/menu font, fontsize, fweight и "
          "btn_bg/btn_bg_hover. apply_to_all_pages=true применяет конфигурацию ко всем страницам; "
          "затем каждую измененную страницу нужно сохранить через tobiz_save_page.")
    async def tobiz_update_site_styles(project_id: Id | None = None, page_id: Id = "",
                                       styles: dict[str, Any] | None = None,
                                       apply_to_all_pages: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.update_site_styles(project_id, page_id, styles or {}, apply_to_all_pages)

    @tool("tobiz_update_page",
          "Изменить параметры страницы: title (название), dir (URL/slug), seo_title, "
          "seo_description, seo_keywords, og_image (имя загруженного файла), valid_login, "
          "valid_password, personal_seo_configs, access_control. Пишет СРАЗУ на сайт, "
          "без tobiz_save_page. Остальные поля формы сохраняются как были.")
    async def tobiz_update_page(project_id: Id | None = None, page_id: Id = "",
                                title: str | None = None, dir: str | None = None,
                                seo_title: str | None = None, seo_description: str | None = None,
                                seo_keywords: str | None = None, og_image: str | None = None,
                                valid_login: str | None = None,
                                valid_password: str | None = None,
                                personal_seo_configs: bool | None = None,
                                access_control: bool | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.update_page(
            project_id, page_id, title=title, dir=dir, seo_title=seo_title,
            seo_description=seo_description, seo_keywords=seo_keywords, og_image=og_image,
            valid_login=valid_login, valid_password=valid_password,
            personal_seo_configs=personal_seo_configs, access_control=access_control)

    @tool("tobiz_copy_page",
          "Скопировать страницу (вместе с блоками) в проект: title — название копии, "
          "target_project — project_id получателя (по умолчанию текущий). "
          "apply=false — только показать план и список доступных проектов.")
    async def tobiz_copy_page(project_id: Id | None = None, page_id: Id = "",
                              title: str = "", target_project: Id = "",
                              apply: bool = True) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.copy_page(project_id, page_id, title or None,
                                       target_project or None, apply=apply)

    @tool("tobiz_build_from_template", "One-command native template pipeline: preview or copy a page, "
          "rebind a positional content recipe, prepare native settings, replace populated images, "
          "save once, apply SEO and run desktop/mobile quality audit. No custom HTML/CSS/JS is added.")
    async def tobiz_build_from_template(source_project_id: Id = "", source_page_id: Id = "",
                                        target_project_id: Id = "", title: str = "",
                                        recipe: dict[str, Any] | None = None,
                                        replacement_image: str | None = None,
                                        source_terms: list[str] | None = None,
                                        seo: dict[str, Any] | None = None,
                                        apply: bool = False,
                                        viewports: list[str] | None = None) -> dict[str, Any]:
        if apply and service.config.read_only:
            raise errors.read_only()
        allowed_seo = {"title", "dir", "seo_title", "seo_description", "seo_keywords",
                       "og_image", "personal_seo_configs", "access_control"}
        seo_values = seo or {}
        unknown_seo = sorted(set(seo_values) - allowed_seo)
        if unknown_seo:
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    "Неизвестные SEO-поля: " + ", ".join(unknown_seo))
        source_project_id, source_page = await service.resolve_page(source_project_id, source_page_id)
        source_draft = await service.draft(source_project_id, source_page_id)
        prepared_source, template_changes, template_warnings = template_domain.prepare_template(
            source_draft, content_domain.fingerprint(source_draft))
        batch = content_domain.recipe_edits(prepared_source, recipe or {
            "types": [prepared_source.blocks[bid].type_id for bid in prepared_source.order
                      if not prepared_source.blocks[bid].deleted], "slots": []})
        candidate, content_changes = content_domain.prepare(
            prepared_source, batch, replacement_image)
        candidate, final_template_changes, final_warnings = template_domain.prepare_template(candidate)
        plan = {
            "source_page_id": source_page_id,
            "source_title": source_page.title,
            "target_project_id": target_project_id or source_project_id,
            "title": title or f"Копия {source_page.title}",
            "block_types": [candidate.blocks[bid].type_id for bid in candidate.order
                            if not candidate.blocks[bid].deleted],
            "content_changes": len(content_changes),
            "template_changes": len(template_changes) + len(final_template_changes),
            "warnings": template_warnings + final_warnings,
        }
        if not apply:
            return {"preview": True, "plan": plan, "passport": content_domain.passport(candidate)}

        copied = await service.copy_page(source_project_id, source_page_id, plan["title"],
                                         target_project_id or source_project_id, apply=True)
        created = copied.get("created") or []
        if len(created) != 1 or not created[0].get("page_id"):
            raise errors.TobizError(errors.SAVE_FAILED,
                                    "Не удалось однозначно определить созданную страницу")
        target_page_id = str(created[0]["page_id"])
        target_project = str(copied["new_project"])
        target_draft = await service.draft(target_project, target_page_id, refresh=True)
        prepared, first_changes, first_warnings = template_domain.prepare_template(
            target_draft, content_domain.fingerprint(target_draft))
        target_batch = content_domain.recipe_edits(prepared, recipe or {
            "types": [prepared.blocks[bid].type_id for bid in prepared.order
                      if not prepared.blocks[bid].deleted], "slots": []})
        built, changed = content_domain.prepare(prepared, target_batch, replacement_image)
        built, last_changes, last_warnings = template_domain.prepare_template(built)
        service.drafts.put(built)
        save_result = await service.save_page(target_project, target_page_id)

        seo_result = await service.update_page(target_project, target_page_id, **seo_values) if seo_values else None
        report = await service.inspect_page(target_project, target_page_id, screenshot=True,
                                            viewports=viewports,
                                            forbidden_terms=source_terms)
        summary = audit_domain.compact(report)
        return {"preview": False, "page": created[0], "plan": plan,
                "changed_fields": len(changed),
                "template_changes": first_changes + last_changes,
                "warnings": first_warnings + last_warnings,
                "save": save_result, "seo": seo_result, "audit": summary,
                "quality_score": summary.get("quality_score"),
                "fix_plan": summary.get("fix_plan", [])}

    @tool("tobiz_plan_site", "Create a deterministic native-first site plan before building. Selects "
          "an installed TOBIZ template, locks its block structure, assigns a purpose to each section, "
          "sets text-slot limits, photo briefs, CTA rules and acceptance criteria. Returns a stable "
          "plan_id that can be validated after restart. Read-only; no page is created.")
    async def tobiz_plan_site(brief: dict[str, Any], goal: str = "") -> dict[str, Any]:
        if not isinstance(brief, dict):
            raise errors.TobizError(errors.BAD_ARGUMENT, "brief must be an object")
        if goal and goal not in composition_domain.GOALS:
            raise errors.TobizError(errors.BAD_ARGUMENT, f"Неизвестная цель композиции: {goal}")
        try:
            selection, selected = design_domain.select_native(brief, max_flex_share=0.3)
        except (TypeError, ValueError) as exc:
            raise errors.TobizError(errors.BAD_ARGUMENT, str(exc)) from exc
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        blueprint = content_domain.compact_blueprint(
            content_domain.passport(source_draft), content_domain.content_map(source_draft))
        return site_plan_domain.build(
            brief, selection, selected, blueprint, source_draft, goal or None)

    @tool("tobiz_compile_site_content", "Compile an evidence-bound copywriting manifest for a native "
          "TOBIZ site before writing text. Selects and locks the same installed template as tobiz_plan_site, "
          "maps every native text slot to its purpose and mobile length limit, lists missing client evidence, "
          "and forbids fabricated prices, reviews, credentials, guarantees and contacts. Read-only.")
    async def tobiz_compile_site_content(brief: dict[str, Any], goal: str = "") -> dict[str, Any]:
        plan = await tobiz_plan_site(brief, goal)
        return {
            "plan_id": plan["plan_id"], "template": plan["template"],
            "content_brief": plan["content_brief"],
            "photo_requirements": plan["photo_requirements"],
        }

    @tool("tobiz_validate_site_recipe", "Validate proposed native-template copy before creating a page. "
          "Checks the locked block sequence, meaningful-slot coverage, mobile text limits, card-copy balance, "
          "CTA specificity and unsupported factual claims. Read-only; returns exact slots and never rewrites text.")
    async def tobiz_validate_site_recipe(brief: dict[str, Any], recipe: dict[str, Any],
                                         goal: str = "") -> dict[str, Any]:
        if not isinstance(recipe, dict):
            raise errors.TobizError(errors.BAD_ARGUMENT, "recipe must be an object")
        plan = await tobiz_plan_site(brief, goal)
        selected = plan["template"]
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        blueprint = content_domain.compact_blueprint(
            content_domain.passport(source_draft), content_domain.content_map(source_draft))
        return site_plan_domain.validate_recipe(brief, plan, blueprint, recipe)

    @tool("tobiz_validate_media_recipe", "Validate image assignments before creating a page. Checks exact "
          "native-slot coverage, uploaded filenames, pixel dimensions, background orientation and text-safe "
          "area, consistent card ratios, placeholders and cross-section reuse. Read-only.")
    async def tobiz_validate_media_recipe(brief: dict[str, Any], media_recipe: dict[str, Any],
                                          goal: str = "") -> dict[str, Any]:
        if not isinstance(media_recipe, dict):
            raise errors.TobizError(errors.BAD_ARGUMENT, "media_recipe must be an object")
        plan = await tobiz_plan_site(brief, goal)
        selected = plan["template"]
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        blueprint = content_domain.compact_blueprint(
            content_domain.passport(source_draft), content_domain.content_map(source_draft))
        return site_plan_domain.validate_media_recipe(plan, blueprint, media_recipe)

    @tool("tobiz_prepare_site_package", "Prepare the complete clean fill-in package for a new native "
          "TOBIZ page in one call. Returns stable plan_id, locked template, every text/link slot with role "
          "and mobile limit, every exact image path with visual requirements, SEO fields and missing client "
          "evidence. Source-template copy is deliberately omitted. Read-only.")
    async def tobiz_prepare_site_package(brief: dict[str, Any], goal: str = "") -> dict[str, Any]:
        plan = await tobiz_plan_site(brief, goal)
        selected = plan["template"]
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        blueprint = content_domain.compact_blueprint(
            content_domain.passport(source_draft), content_domain.content_map(source_draft))
        return site_plan_domain.prepare_build_package(brief, plan, blueprint)

    @tool("tobiz_build_site_package", "Preview or build directly from the complete object returned by "
          "tobiz_prepare_site_package. Recomputes the plan, rejects stale or mixed package/template IDs, "
          "runs the unified preflight and delegates to the native one-save quality pipeline. Fill the "
          "package in place; do not manually unpack its fields. No custom HTML/CSS/JS is added.")
    async def tobiz_build_site_package(package: dict[str, Any], target_project_id: Id = "",
                                       source_terms: list[str] | None = None,
                                       apply: bool = False,
                                       viewports: list[str] | None = None,
                                       details: bool = False) -> dict[str, Any]:
        if not isinstance(package, dict) or not isinstance(package.get("brief"), dict):
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    "Передайте полный пакет из tobiz_prepare_site_package")
        brief = package["brief"]
        plan = await tobiz_plan_site(brief)
        envelope = site_plan_domain.validate_package_envelope(package, plan)
        if envelope["blockers"]:
            raise errors.TobizError(
                errors.CONFLICT, "Пакет устарел или относится к другому плану",
                "Повторно вызовите tobiz_prepare_site_package и перенесите подтвержденные значения",
                raw=envelope,
            )
        recipe = package.get("recipe")
        media_recipe = package.get("media_recipe")
        seo = package.get("seo")
        preflight = await tobiz_preflight_site_build(
            brief=brief, recipe=recipe, media_recipe=media_recipe, seo=seo,
            plan_id=plan["plan_id"])
        if apply and not preflight.get("ready_for_build"):
            raise errors.TobizError(
                errors.BAD_ARGUMENT, "Пакет сайта не готов к сборке",
                "Исправьте blockers из preflight; страница еще не создана", raw=preflight)
        title = str((seo or {}).get("title") or "").strip()
        result = await tobiz_build_quality_page(
            brief=brief, target_project_id=target_project_id, title=title,
            recipe=recipe, media_recipe=media_recipe, source_terms=source_terms,
            seo=seo, apply=apply, viewports=viewports, details=details,
            plan_id=plan["plan_id"])
        result["package_id"] = package.get("package_id")
        result["package_validation"] = envelope
        result["preflight"] = preflight
        return result

    @tool("tobiz_preflight_site_build", "One-call read-only gate for the complete site package before "
          "creating a TOBIZ page. Validates plan_id, copy, factual claims, media assignments, SEO lengths, "
          "page slug and unsafe or empty links. Returns one ready_for_build verdict and exact blockers.")
    async def tobiz_preflight_site_build(brief: dict[str, Any], recipe: dict[str, Any],
                                         media_recipe: dict[str, Any] | None = None,
                                         seo: dict[str, Any] | None = None,
                                         plan_id: str = "", goal: str = "") -> dict[str, Any]:
        if not isinstance(recipe, dict):
            raise errors.TobizError(errors.BAD_ARGUMENT, "recipe must be an object")
        plan = await tobiz_plan_site(brief, goal)
        if plan_id and plan_id != plan["plan_id"]:
            raise errors.TobizError(errors.CONFLICT, "plan_id не соответствует текущему брифу",
                                    "Повторно вызовите tobiz_plan_site")
        selected = plan["template"]
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        blueprint = content_domain.compact_blueprint(
            content_domain.passport(source_draft), content_domain.content_map(source_draft))
        return site_plan_domain.validate_build_package(
            brief, plan, blueprint, recipe, media_recipe, seo)

    @tool("tobiz_audit_claims", "Read-only factual integrity audit for a TOBIZ page. Finds phones, emails, "
          "prices, discounts, experience, durations and numeric results that are not present in the approved "
          "brief. Returns the exact block and native field; never edits copy or invents replacements.")
    async def tobiz_audit_claims(brief: dict[str, Any], project_id: Id | None = None,
                                 page_id: Id = "") -> dict[str, Any]:
        if not isinstance(brief, dict):
            raise errors.TobizError(errors.BAD_ARGUMENT, "brief must be an object")
        project_id, _ = await service.resolve_page(project_id, page_id)
        return claim_audit_domain.analyze(await service.draft(project_id, page_id), brief)

    @tool("tobiz_check_site_plan", "Compare an existing TOBIZ page with a deterministic plan_id "
          "reconstructed from the same brief. Checks native structure and section roles, then runs "
          "image composition, reference fidelity, editor safety and the unified release gate. Read-only.")
    async def tobiz_check_site_plan(
            brief: dict[str, Any], plan_id: str, project_id: Id | None = None,
            page_id: Id = "", source_terms: list[str] | None = None,
            screenshots: bool = True) -> dict[str, Any]:
        selection, selected = design_domain.select_native(brief, max_flex_share=0.3)
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        blueprint = content_domain.compact_blueprint(
            content_domain.passport(source_draft), content_domain.content_map(source_draft))
        plan = site_plan_domain.build(brief, selection, selected, blueprint, source_draft)
        if plan_id != plan["plan_id"]:
            raise errors.TobizError(
                errors.CONFLICT, "plan_id не соответствует текущему брифу и шаблону",
                "Повторно вызовите tobiz_plan_site и используйте полученный plan_id")
        project_id, _ = await service.resolve_page(project_id, page_id)
        target_draft = await service.draft(project_id, page_id)
        target_composition = composition_domain.analyze(target_draft, plan["goal"])
        plan_check = site_plan_domain.compare(plan, target_draft, target_composition)
        target_report = await service.inspect_page(
            project_id, page_id, screenshot=screenshots, viewports=["desktop", "mobile"],
            forbidden_terms=source_terms)
        target_audit = audit_domain.compact(target_report)
        reference_report = await service.inspect_page(
            selected["project_id"], selected["page_id"], screenshot=False,
            viewports=["desktop", "mobile"])
        reference = design_reference_domain.compare(
            design_reference_domain.extract(
                source_draft, audit_domain.compact(reference_report), plan["goal"]),
            design_reference_domain.extract(target_draft, target_audit, plan["goal"]))
        roundtrip = await service.editor_roundtrip(project_id, page_id)
        claims = claim_audit_domain.analyze(target_draft, brief)
        gate = design_gate_domain.evaluate(
            target_audit, target_composition, reference, roundtrip,
            has_unsaved_changes=target_draft.has_changes, claims=claims)
        if not plan_check["matches"]:
            gate["blockers"] = plan_check["issues"] + gate["blockers"]
            gate["verdict"] = "save_blocked"
            gate["release_ready"] = False
            gate["score"] = min(float(gate["score"]), 4.9)
        return {"plan": plan, "plan_check": plan_check,
                "images": image_audit_domain.summarize(target_report),
                "claims": claims, "reference_comparison": reference, "gate": gate}

    @tool("tobiz_build_quality_page", "Brief-driven native TOBIZ quality pipeline. Selects a verified "
          "installed template, enforces the 30% Flex limit, returns a photo-slot manifest in preview, "
          "then copies, fills and saves once. Apply mode also runs desktop/mobile audit and an editor "
          "round-trip safety check. No custom HTML/CSS/JS or new blocks are added.")
    async def tobiz_build_quality_page(brief: dict[str, Any], target_project_id: Id = "",
                                       title: str = "", recipe: dict[str, Any] | None = None,
                                       media_recipe: dict[str, Any] | None = None,
                                       replacement_image: str | None = None,
                                       source_terms: list[str] | None = None,
                                       seo: dict[str, Any] | None = None,
                                       apply: bool = False,
                                       viewports: list[str] | None = None,
                                       details: bool = False,
                                       plan_id: str = "") -> dict[str, Any]:
        if not isinstance(brief, dict):
            raise errors.TobizError(errors.BAD_ARGUMENT, "brief must be an object")
        try:
            selection, selected = design_domain.select_native(brief, max_flex_share=0.3)
        except (TypeError, ValueError) as exc:
            raise errors.TobizError(errors.BAD_ARGUMENT, str(exc)) from exc
        source_draft = await service.draft(selected["project_id"], selected["page_id"])
        source_passport = content_domain.passport(source_draft)
        blueprint = content_domain.compact_blueprint(
            source_passport, content_domain.content_map(source_draft))
        site_plan = site_plan_domain.build(brief, selection, selected, blueprint, source_draft)
        if plan_id and plan_id != site_plan["plan_id"]:
            raise errors.TobizError(
                errors.CONFLICT, "plan_id не соответствует выбранному шаблону",
                "Повторно вызовите tobiz_plan_site для этого брифа")
        coverage_recipe = recipe or {
            "types": blueprint.get("recipe", {}).get("types", []), "slots": []}
        coverage = content_domain.recipe_coverage(blueprint, coverage_recipe)
        recipe_validation = (site_plan_domain.validate_recipe(
            brief, site_plan, blueprint, recipe) if recipe else None)
        media_validation = (site_plan_domain.validate_media_recipe(
            site_plan, blueprint, media_recipe) if media_recipe else None)
        preflight = site_plan_domain.validate_build_package(
            brief, site_plan, blueprint, recipe, media_recipe, seo)
        if apply and not recipe:
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Для сборки требуется recipe из предпросмотра",
                "Сначала вызовите apply=false, заполните штатные текстовые слоты и повторите",
            )
        if apply and not coverage.get("complete"):
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                f"Рецепт заполнен не полностью: {coverage['replaced']} из {coverage['required']}",
                "Замените поля из missing и unchanged; страница еще не создана",
                raw=coverage,
            )
        if apply and recipe_validation and recipe_validation.get("blockers"):
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Контентный рецепт не прошел предварительную проверку",
                "Исправьте blockers из tobiz_validate_site_recipe; страница еще не создана",
                raw=recipe_validation,
            )
        if apply and preflight.get("blockers"):
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Пакет сайта не прошел единую предсборочную проверку",
                "Исправьте blockers из tobiz_preflight_site_build; страница еще не создана",
                raw=preflight,
            )
        has_photo_slots = bool(blueprint.get("photo_slots"))
        allow_placeholders = brief.get("allow_placeholders") is True
        if apply and has_photo_slots and not media_recipe and not allow_placeholders:
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Для качественной сборки требуется media_recipe",
                "Заполните photo_requirements, вызовите tobiz_validate_media_recipe и повторите",
            )
        if apply and media_validation and media_validation.get("blockers"):
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Медиарецепт не прошел предварительную проверку",
                "Исправьте blockers из tobiz_validate_media_recipe; страница еще не создана",
                raw=media_validation,
            )
        if recipe and media_validation and not media_validation.get("blockers"):
            recipe = site_plan_domain.merge_media_recipe(recipe, media_validation)
        if apply and not replacement_image:
            slots = recipe.get("slots", []) if isinstance(recipe, dict) else []
            has_images = any("image" in str(slot.get("path") or "").lower()
                             for slot in slots if isinstance(slot, dict))
            if not has_images:
                raise errors.TobizError(
                    errors.BAD_ARGUMENT,
                    "Укажите replacement_image или изображения в recipe",
                    "Исходные фотографии шаблона нельзя оставлять на новом сайте",
                )

        result = await tobiz_build_from_template(
            source_project_id=selected["project_id"],
            source_page_id=selected["page_id"],
            target_project_id=target_project_id,
            title=title,
            recipe=recipe,
            replacement_image=replacement_image,
            source_terms=source_terms,
            seo=seo,
            apply=apply,
            viewports=viewports or ["desktop", "mobile"],
        )
        if not details:
            result.pop("passport", None)
        result["blueprint"] = blueprint
        result["site_plan"] = site_plan
        result["recipe_validation"] = recipe_validation
        result["media_validation"] = media_validation
        result["preflight"] = preflight
        result["recipe_coverage"] = coverage if recipe else {
            key: value for key, value in coverage.items()
            if key not in {"missing", "unchanged"}
        }
        result["design"] = {
            "template": selected,
            "visual_references": selection["visual_references"],
            "flex_limit": 0.3,
            "native_blocks_only": True,
        }
        result["photo_slots"] = blueprint.get("photo_slots", [])
        result["quality_gates"] = [
            "native_blocks_only", "flex_share_lte_30_percent", "single_save",
            "complete_recipe_before_copy", "desktop_mobile_audit", "editor_roundtrip_safe",
            "content_integrity_review", "brief_bound_claim_integrity",
            "pre_copy_media_validation", "unified_pre_copy_build_gate",
            "visual_consistency_review",
        ]
        if apply:
            page = result.get("page") or {}
            target_page_id = str(page.get("page_id") or "")
            target_project = str(target_project_id or selected["project_id"])
            roundtrip = await service.editor_roundtrip(target_project, target_page_id)
            result["editor_roundtrip"] = roundtrip
            audit_verdict = (result.get("audit") or {}).get("verdict", "review")
            result["quality_score"] = (result.get("audit") or {}).get("quality_score")
            target_draft = await service.draft(target_project, target_page_id, refresh=True)
            target_composition = composition_domain.analyze(target_draft, site_plan["goal"])
            plan_check = site_plan_domain.compare(site_plan, target_draft, target_composition)
            target_report = await service.inspect_page(
                target_project, target_page_id, screenshot=True,
                viewports=viewports or ["desktop", "mobile"], forbidden_terms=source_terms)
            target_audit = audit_domain.compact(target_report)
            reference_report = await service.inspect_page(
                selected["project_id"], selected["page_id"], screenshot=False,
                viewports=["desktop", "mobile"])
            reference = design_reference_domain.compare(
                design_reference_domain.extract(
                    source_draft, audit_domain.compact(reference_report), site_plan["goal"]),
                design_reference_domain.extract(
                    target_draft, target_audit, site_plan["goal"]))
            claims = claim_audit_domain.analyze(target_draft, brief)
            gate = design_gate_domain.evaluate(
                target_audit, target_composition, reference, roundtrip,
                has_unsaved_changes=target_draft.has_changes,
                claims=claims)
            if not plan_check["matches"]:
                gate["blockers"] = plan_check["issues"] + gate["blockers"]
                gate["verdict"] = "save_blocked"
                gate["release_ready"] = False
                gate["score"] = min(float(gate["score"]), 4.9)
            result["plan_check"] = plan_check
            result["image_audit"] = image_audit_domain.summarize(target_report)
            result["reference_comparison"] = reference
            result["claim_audit"] = claims
            result["design_gate"] = gate
            result["quality_verdict"] = gate["verdict"]
        else:
            result["quality_verdict"] = "preview"
            result["quality_score"] = None
        return result

    @tool("tobiz_improve_page", "Audit a TOBIZ page and iteratively apply only deterministic native "
          "fixes: broken anchors with an existing native form, empty/demo social links, gallery hover-only "
          "labels, dark-form heading contrast, Name-before-Phone form order, equal card/button height, "
          "always-visible card buttons and centered buttons when the affected block exposes these controls. "
          "Every visual defect is tied to its native block id. Preview by default. "
          "Apply mode requires an editor-safe clean draft, creates a backup on every save, re-audits after "
          "each cycle and automatically restores the backup if the quality score decreases.")
    async def tobiz_improve_page(project_id: Id | None = None, page_id: Id = "",
                                 target_score: float = 7.0, max_cycles: int = 2,
                                 source_terms: list[str] | None = None,
                                 apply: bool = False,
                                 viewports: list[str] | None = None) -> dict[str, Any]:
        if apply and service.config.read_only:
            raise errors.read_only()
        if not 0 <= target_score <= 10:
            raise errors.TobizError(errors.BAD_ARGUMENT, "target_score must be between 0 and 10")
        if not 1 <= max_cycles <= 3:
            raise errors.TobizError(errors.BAD_ARGUMENT, "max_cycles must be between 1 and 3")
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        if draft.has_changes:
            raise errors.TobizError(
                errors.CONFLICT,
                "В MCP-черновике есть несохраненные изменения",
                "Сохраните или отмените их перед автоматическим улучшением",
            )
        initial_report = await service.inspect_page(
            project_id, page_id, screenshot=True, viewports=viewports or ["desktop", "mobile"],
            forbidden_terms=source_terms)
        initial = audit_domain.compact(initial_report)
        candidate, planned, preparation_warnings = template_domain.prepare_template(
            draft, content_domain.fingerprint(draft))
        candidate, visual_planned, visual_warnings = template_domain.prepare_visual_fixes(
            candidate, initial)
        planned.extend(visual_planned)
        preparation_warnings.extend(visual_warnings)
        preview = {
            "preview": not apply,
            "target_score": target_score,
            "max_cycles": max_cycles,
            "initial": initial,
            "safe_changes": planned,
            "preparation_warnings": preparation_warnings,
            "human_fix_plan": initial.get("fix_plan", []),
        }
        if not apply:
            preview["can_apply"] = bool(planned)
            preview["stopped_reason"] = "preview"
            return preview

        roundtrip_before = await service.editor_roundtrip(project_id, page_id)
        if not roundtrip_before.get("editor_safe"):
            return {**preview, "preview": False, "applied": False,
                    "stopped_reason": "editor_not_safe", "editor_roundtrip": roundtrip_before}
        if not planned:
            return {**preview, "preview": False, "applied": False, "cycles": [],
                    "final": initial, "achieved_target": initial["quality_score"]["overall"] >= target_score,
                    "stopped_reason": "no_safe_automatic_fixes"}

        cycles = []
        current = initial
        rolled_back = False
        stopped_reason = "cycle_limit"
        for cycle_number in range(1, max_cycles + 1):
            current_draft = draft if cycle_number == 1 else await service.draft(
                project_id, page_id, refresh=True)
            improved, changes, warnings = template_domain.prepare_template(
                current_draft, content_domain.fingerprint(current_draft))
            improved, visual_changes, visual_warnings = template_domain.prepare_visual_fixes(
                improved, current)
            changes.extend(visual_changes)
            warnings.extend(visual_warnings)
            if not changes:
                stopped_reason = "no_more_safe_fixes"
                break
            service.drafts.put(improved)
            save = await service.save_page(project_id, page_id)
            report = await service.inspect_page(
                project_id, page_id, screenshot=True, viewports=viewports or ["desktop", "mobile"],
                forbidden_terms=source_terms)
            after = audit_domain.compact(report)
            before_score = current["quality_score"]["overall"]
            after_score = after["quality_score"]["overall"]
            cycle = {"cycle": cycle_number, "changes": changes, "warnings": warnings,
                     "backup": save.get("backup"), "score_before": before_score,
                     "score_after": after_score, "audit": after}
            if after_score < before_score:
                backup_id = (save.get("backup") or {}).get("backup_id")
                if backup_id:
                    cycle["rollback"] = await service.restore_page_backup(
                        project_id, page_id, backup_id, confirm=True)
                    rolled_back = True
                    stopped_reason = "score_decreased_rolled_back"
                    cycles.append(cycle)
                    current = initial if cycle_number == 1 else current
                    break
            cycles.append(cycle)
            current = after
            if after_score >= target_score and after.get("verdict") != "save_blocked":
                stopped_reason = "target_reached"
                break

        roundtrip_after = await service.editor_roundtrip(project_id, page_id)
        return {**preview, "preview": False, "applied": bool(cycles) and not rolled_back,
                "cycles": cycles, "rolled_back": rolled_back, "final": current,
                "achieved_target": current["quality_score"]["overall"] >= target_score
                and current.get("verdict") != "save_blocked",
                "stopped_reason": stopped_reason, "editor_roundtrip": roundtrip_after,
                "remaining_fix_plan": current.get("fix_plan", [])}

    @tool("tobiz_repair_layout", "Repair block-level visual layout defects using only controls exposed "
          "by the affected native TOBIZ block type. Handles equal card/button height, initially visible "
          "buttons, hover animation and button alignment. Mobile controls are reported for review unless "
          "their semantics are deterministic. Preview by default. Apply mode requires a clean editor-safe "
          "draft, creates a backup, re-audits desktop/mobile and rolls back on a lower score or new critical issue.")
    async def tobiz_repair_layout(project_id: Id | None = None, page_id: Id = "",
                                  source_terms: list[str] | None = None,
                                  apply: bool = False,
                                  viewports: list[str] | None = None) -> dict[str, Any]:
        if apply and service.config.read_only:
            raise errors.read_only()
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        if draft.has_changes:
            raise errors.TobizError(
                errors.CONFLICT, "В MCP-черновике есть несохраненные изменения",
                "Сохраните или отмените их перед ремонтом верстки")
        modes = viewports or ["desktop", "mobile"]
        before_report = await service.inspect_page(
            project_id, page_id, screenshot=True, viewports=modes,
            forbidden_terms=source_terms)
        before = audit_domain.compact(before_report)
        types = await service.block_types(project_id)
        candidate, changes, warnings = layout_domain.prepare(draft, before, types)
        affected_types = sorted({item["type_id"] for item in changes})
        result = {
            "preview": not apply, "before": before, "safe_changes": changes,
            "warnings": warnings, "affected_type_registry": layout_domain.registry(
                types, affected_types)["types"] if affected_types else [],
            "can_apply": bool(changes),
        }
        if not apply:
            return result
        if not changes:
            return {**result, "preview": False, "applied": False,
                    "stopped_reason": "no_safe_layout_fixes"}

        service.drafts.put(candidate)
        roundtrip = await service.editor_roundtrip(project_id, page_id)
        if not roundtrip.get("editor_safe"):
            service.drafts.put(draft)
            return {**result, "preview": False, "applied": False,
                    "stopped_reason": "editor_not_safe", "editor_roundtrip": roundtrip}
        save = await service.save_page(project_id, page_id)
        after_report = await service.inspect_page(
            project_id, page_id, screenshot=True, viewports=modes,
            forbidden_terms=source_terms)
        after = audit_domain.compact(after_report)
        before_score = before["quality_score"]["overall"]
        after_score = after["quality_score"]["overall"]
        before_critical = {(item.get("viewport"), item.get("code"))
                           for item in before.get("critical") or []}
        after_critical = {(item.get("viewport"), item.get("code"))
                          for item in after.get("critical") or []}
        new_critical = [
            {"viewport": viewport, "code": code}
            for viewport, code in sorted(after_critical - before_critical,
                                         key=lambda item: (str(item[0]), str(item[1])))
        ]
        regressed = after_score < before_score or bool(new_critical)
        rollback = None
        if regressed:
            backup_id = (save.get("backup") or {}).get("backup_id")
            if backup_id:
                rollback = await service.restore_page_backup(
                    project_id, page_id, backup_id, confirm=True)
        final_roundtrip = await service.editor_roundtrip(project_id, page_id)
        return {**result, "preview": False, "applied": not regressed,
                "stopped_reason": "regression_rolled_back" if regressed else "layout_repaired",
                "backup": save.get("backup"), "before_score": before_score,
                "after_score": after_score, "issue_delta": layout_domain.issue_count(after)
                - layout_domain.issue_count(before), "new_critical": new_critical,
                "after": after, "rollback": rollback, "editor_roundtrip": final_roundtrip}

    @tool("tobiz_refine_design", "Analyze the whole rendered page as a design system across desktop "
          "and mobile: container grid, section alignment and rhythm, button palette/radii, typography, "
          "image proportions and clipped content. Preview by default. Apply mode combines only deterministic "
          "native template and layout fixes, validates editor roundtrip, saves once and restores the backup "
          "if quality decreases, a critical error appears or design-system consistency regresses.")
    async def tobiz_refine_design(project_id: Id | None = None, page_id: Id = "",
                                  source_terms: list[str] | None = None,
                                  apply: bool = False) -> dict[str, Any]:
        if apply and service.config.read_only:
            raise errors.read_only()
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        if draft.has_changes:
            raise errors.TobizError(
                errors.CONFLICT, "В MCP-черновике есть несохраненные изменения",
                "Сохраните или отмените их перед комплексным улучшением дизайна")
        before_report = await service.inspect_page(
            project_id, page_id, screenshot=True, viewports=["desktop", "mobile"],
            forbidden_terms=source_terms)
        before = audit_domain.compact(before_report)
        types = await service.block_types(project_id)
        candidate, template_changes, template_warnings = template_domain.prepare_template(
            draft, content_domain.fingerprint(draft))
        candidate, layout_changes, layout_warnings = layout_domain.prepare(
            candidate, before, types)
        changes = template_changes + layout_changes
        warnings = template_warnings + layout_warnings
        result = {
            "preview": not apply, "before": before,
            "design_system": refinement_domain.summarize(before),
            "safe_changes": changes, "warnings": warnings, "can_apply": bool(changes),
            "manual_design_plan": [item for item in before.get("fix_plan", [])
                                   if item.get("dimension") == "visual"],
        }
        if not apply:
            return result
        if not changes:
            return {**result, "preview": False, "applied": False,
                    "stopped_reason": "no_safe_design_fixes"}
        service.drafts.put(candidate)
        roundtrip = await service.editor_roundtrip(project_id, page_id)
        if not roundtrip.get("editor_safe"):
            service.drafts.put(draft)
            return {**result, "preview": False, "applied": False,
                    "stopped_reason": "editor_not_safe", "editor_roundtrip": roundtrip}
        save = await service.save_page(project_id, page_id)
        after_report = await service.inspect_page(
            project_id, page_id, screenshot=True, viewports=["desktop", "mobile"],
            forbidden_terms=source_terms)
        after = audit_domain.compact(after_report)
        design_delta = refinement_domain.regression(before, after)
        before_critical = {(item.get("viewport"), item.get("code"))
                           for item in before.get("critical") or []}
        after_critical = {(item.get("viewport"), item.get("code"))
                          for item in after.get("critical") or []}
        new_critical = after_critical - before_critical
        regressed = (after["quality_score"]["overall"] < before["quality_score"]["overall"]
                     or bool(new_critical) or design_delta["regressed"])
        rollback = None
        if regressed:
            backup_id = (save.get("backup") or {}).get("backup_id")
            if backup_id:
                rollback = await service.restore_page_backup(
                    project_id, page_id, backup_id, confirm=True)
        final_roundtrip = await service.editor_roundtrip(project_id, page_id)
        return {**result, "preview": False, "applied": not regressed,
                "stopped_reason": "design_regression_rolled_back" if regressed else "design_refined",
                "backup": save.get("backup"), "after": after,
                "after_design_system": refinement_domain.summarize(after),
                "design_delta": design_delta,
                "score_delta": round(after["quality_score"]["overall"]
                                     - before["quality_score"]["overall"], 1),
                "rollback": rollback, "editor_roundtrip": final_roundtrip}

    @tool("tobiz_audit_composition", "Analyze the semantic architecture of a native TOBIZ page "
          "without changing it. Classifies every block by role, checks topic coverage, trust signals, "
          "section order and thin sections, then returns block-specific issues and a recommended native "
          "story sequence. Goals: lead_generation, education or ecommerce. No custom code is generated.")
    async def tobiz_audit_composition(project_id: Id | None = None, page_id: Id = "",
                                      goal: str = "lead_generation") -> dict[str, Any]:
        if goal not in composition_domain.GOALS:
            raise errors.TobizError(
                errors.BAD_ARGUMENT, f"Неизвестная цель композиции: {goal}",
                "Используйте lead_generation, education или ecommerce")
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        return composition_domain.analyze(draft, goal)

    @tool("tobiz_compare_design_reference", "Compare a target TOBIZ page with a native reference "
          "page across block sequence, semantic section roles, native style fields and rendered "
          "desktop/mobile design profiles. Returns per-block and visual deviations without changing "
          "either page. Use before delivery when a site must preserve an installed template design.")
    async def tobiz_compare_design_reference(
            reference_project_id: Id, reference_page_id: Id,
            target_project_id: Id, target_page_id: Id,
            goal: str = "lead_generation", screenshots: bool = False) -> dict[str, Any]:
        if goal not in composition_domain.GOALS:
            raise errors.TobizError(
                errors.BAD_ARGUMENT, f"Неизвестная цель композиции: {goal}",
                "Используйте lead_generation, education или ecommerce")
        reference_project_id, _ = await service.resolve_page(
            reference_project_id, reference_page_id)
        target_project_id, _ = await service.resolve_page(target_project_id, target_page_id)
        reference_draft = await service.draft(reference_project_id, reference_page_id)
        target_draft = await service.draft(target_project_id, target_page_id)
        reference_report = await service.inspect_page(
            reference_project_id, reference_page_id, screenshot=screenshots,
            viewports=["desktop", "mobile"])
        target_report = await service.inspect_page(
            target_project_id, target_page_id, screenshot=screenshots,
            viewports=["desktop", "mobile"])
        reference_audit = audit_domain.compact(reference_report)
        target_audit = audit_domain.compact(target_report)
        reference_recipe = design_reference_domain.extract(reference_draft, reference_audit, goal)
        target_recipe = design_reference_domain.extract(target_draft, target_audit, goal)
        return {
            "comparison": design_reference_domain.compare(reference_recipe, target_recipe),
            "reference_recipe": reference_recipe,
            "target_recipe": target_recipe,
            "draft_warnings": {
                "reference_has_unsaved_changes": reference_draft.has_changes,
                "target_has_unsaved_changes": target_draft.has_changes,
            },
        }

    @tool("tobiz_release_design_gate", "Run the mandatory final acceptance gate for a native TOBIZ "
          "page. Combines rendered desktop/mobile quality, semantic composition, optional reference "
          "fidelity and editor roundtrip safety into one ready/review/save_blocked verdict. Does not "
          "change the site or submit forms.")
    async def tobiz_release_design_gate(
            project_id: Id | None = None, page_id: Id = "",
            goal: str = "lead_generation", source_terms: list[str] | None = None,
            reference_project_id: Id | None = None, reference_page_id: Id = "",
            screenshots: bool = True, check_editor: bool = True) -> dict[str, Any]:
        if goal not in composition_domain.GOALS:
            raise errors.TobizError(
                errors.BAD_ARGUMENT, f"Неизвестная цель композиции: {goal}",
                "Используйте lead_generation, education или ecommerce")
        project_id, _ = await service.resolve_page(project_id, page_id)
        draft = await service.draft(project_id, page_id)
        report = await service.inspect_page(
            project_id, page_id, screenshot=screenshots,
            viewports=["desktop", "mobile"], forbidden_terms=source_terms)
        audit = audit_domain.compact(report)
        composition = composition_domain.analyze(draft, goal)
        reference_comparison = None
        if reference_project_id is not None or reference_page_id:
            if reference_project_id is None or not reference_page_id:
                raise errors.TobizError(
                    errors.BAD_ARGUMENT, "Для эталона нужны reference_project_id и reference_page_id")
            reference_project_id, _ = await service.resolve_page(
                reference_project_id, reference_page_id)
            reference_draft = await service.draft(reference_project_id, reference_page_id)
            reference_report = await service.inspect_page(
                reference_project_id, reference_page_id, screenshot=False,
                viewports=["desktop", "mobile"])
            reference_recipe = design_reference_domain.extract(
                reference_draft, audit_domain.compact(reference_report), goal)
            target_recipe = design_reference_domain.extract(draft, audit, goal)
            reference_comparison = design_reference_domain.compare(
                reference_recipe, target_recipe)
        roundtrip = await service.editor_roundtrip(project_id, page_id) if check_editor else None
        gate = design_gate_domain.evaluate(
            audit, composition, reference_comparison, roundtrip,
            has_unsaved_changes=draft.has_changes)
        return {"gate": gate, "audit": audit, "composition": composition,
                "reference_comparison": reference_comparison,
                "editor_roundtrip": roundtrip}

    @tool("tobiz_audit_images", "Audit every rendered image on desktop and mobile. Detects broken "
          "or stretched files, insufficient source resolution, extreme cropping, repeated photos, "
          "inconsistent card ratios and text over background images without a scrim. Returns image "
          "geometry, nearby section text and screenshots for semantic visual review. Read-only.")
    async def tobiz_audit_images(project_id: Id | None = None, page_id: Id = "",
                                 screenshots: bool = True) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        report = await service.inspect_page(
            project_id, page_id, screenshot=screenshots, viewports=["desktop", "mobile"])
        return image_audit_domain.summarize(report)

    @tool("tobiz_delete_page",
          "Удалить страницу проекта. Необратимо: требует confirm=true, иначе вернёт отказ "
          "с названием страницы — сначала проверьте, ту ли удаляете (tobiz_list_pages).")
    async def tobiz_delete_page(project_id: Id | None = None, page_id: Id = "",
                                confirm: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.delete_page(project_id, page_id, confirm=confirm)

    @tool("tobiz_save_page",
          "Единственный инструмент, который пишет на сервер: рендерит HTML блоков шаблонами "
          "вендора и отправляет SaveBlocks. verify=true проверяет результат по публичной вёрстке.")
    async def tobiz_save_page(project_id: Id | None = None, page_id: Id = "",
                              verify: bool = True, only_if_changed: bool = True,
                              include_payload: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.save_page(project_id, page_id, verify=verify,
                                       only_if_changed=only_if_changed,
                                       include_payload=include_payload)

    @tool("tobiz_discard_changes",
          "Забыть несохранённые правки страницы и перечитать её с сервера.")
    async def tobiz_discard_changes(project_id: Id | None = None,
                                    page_id: Id = "") -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        service.drafts.drop(project_id, page_id)
        draft = await service.draft(project_id, page_id, refresh=True)
        return {"page_id": page_id, "blocks": len(draft.blocks), "discarded": True}

    @tool("tobiz_list_page_backups",
          "Список автоматических резервных копий блоков страницы, созданных перед сохранением.")
    async def tobiz_list_page_backups(project_id: Id | None = None,
                                      page_id: Id = "") -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return service.list_page_backups(project_id, page_id)

    @tool("tobiz_restore_page_backup",
          "Восстановить блоки страницы из автоматической резервной копии. Перезаписывает страницу "
          "и требует confirm=true.")
    async def tobiz_restore_page_backup(project_id: Id | None = None, page_id: Id = "",
                                        backup_id: str = "", confirm: bool = False) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.restore_page_backup(project_id, page_id, backup_id, confirm=confirm)

    # --- проверка и изображения ---

    @tool("tobiz_verify_page",
          "Проверить публичную вёрстку страницы: наличие блоков и ожидаемых текстов.")
    async def tobiz_verify_page(project_id: Id | None = None, page_id: Id = "",
                                expect: list[str] | None = None,
                                block_ids: list[str] | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        if not block_ids:
            draft = await service.draft(project_id, page_id)
            block_ids = [b for b in draft.order]
        return await service.verify_page(project_id, page_id, expect, block_ids)

    @tool("tobiz_get_computed_styles",
          "Прочитать реальные вычисленные стили публичной страницы на desktop/mobile: body, заголовки, текст, ссылки, кнопки и поля.")
    async def tobiz_get_computed_styles(project_id: Id | None = None, page_id: Id = "",
                                        viewports: list[str] | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        report = await service.inspect_page(project_id, page_id, screenshot=False, viewports=viewports)
        return {name: data.get("computedStyles") for name, data in report.get("viewports", {}).items()}

    @tool("tobiz_screenshot_page",
          "Сделать полностраничные PNG-снимки публичной страницы в desktop и mobile и вернуть пути к файлам.")
    async def tobiz_screenshot_page(project_id: Id | None = None, page_id: Id = "",
                                    viewports: list[str] | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        report = await service.inspect_page(project_id, page_id, screenshot=True, viewports=viewports)
        return {name: data.get("screenshot") for name, data in report.get("viewports", {}).items()}

    @tool("tobiz_diagnose_interactions",
          "Проверить формы, поля, кнопки, ссылки, якоря и попапы на desktop/mobile без отправки заявок.")
    async def tobiz_diagnose_interactions(project_id: Id | None = None, page_id: Id = "",
                                          viewports: list[str] | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        report = await service.inspect_page(project_id, page_id, screenshot=False, viewports=viewports)
        return {"viewports": {name: data.get("interactions") for name, data in report.get("viewports", {}).items()},
                "consoleErrors": report.get("consoleErrors"), "pageErrors": report.get("pageErrors")}

    @tool("tobiz_audit_page",
          "Полный аудит публичной страницы одной командой: desktop/mobile-снимки, computed styles, переполнение, "
          "битые изображения, пустые заголовки, формы, кнопки, ссылки, попапы и ошибки JavaScript.")
    async def tobiz_audit_page(project_id: Id | None = None, page_id: Id = "",
                               viewports: list[str] | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        return await service.inspect_page(project_id, page_id, screenshot=True, viewports=viewports)

    @tool("tobiz_audit_summary", "Compact desktop/mobile audit with critical errors, warnings, "
          "screenshots, an explainable 0-10 score across four dimensions and a prioritized fix plan. "
          "Does not submit forms or change the site.")
    async def tobiz_audit_summary(project_id: Id | None = None, page_id: Id = "",
                                  viewports: list[str] | None = None,
                                  source_terms: list[str] | None = None) -> dict[str, Any]:
        project_id, _ = await service.resolve_page(project_id, page_id)
        report = await service.inspect_page(project_id, page_id, screenshot=True, viewports=viewports,
                                            forbidden_terms=source_terms)
        return audit_domain.compact(report)

    @tool("tobiz_upload_image",
          "Загрузить изображение в конструктор. path — файл внутри /data/inbox, либо "
          "content_base64. Возвращает имя файла для полей image/image_gallery.")
    async def tobiz_upload_image(project_id: Id | None = None, page_id: Id = "",
                                 block_id: Id = "", path: str = "",
                                 content_base64: str = "", file_name: str = "") -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        project = await service.project(project_id)
        if page_id:
            await service.resolve_page(project.project_id, page_id)
        return await service.upload_image(
            project.project_id, page_id or "", block_id, path or None,
            content_base64 or None, file_name or None)

    @tool("tobiz_set_block_image",
          "Загрузить изображение и подставить его имя в указанное поле блока одним вызовом.")
    async def tobiz_set_block_image(project_id: Id | None = None, page_id: Id = "",
                                    block_id: Id = "", field: str = "",
                                    path: str = "", content_base64: str = "",
                                    file_name: str = "") -> dict[str, Any]:
        if service.config.read_only:
            raise errors.read_only()
        project_id, _ = await service.resolve_page(project_id, page_id)
        uploaded = await service.upload_image(
            project_id, page_id, block_id, path or None, content_base64 or None,
            file_name or None)
        draft = await service.draft(project_id, page_id)
        block = draft.blocks.get(str(block_id))
        if block is None:
            raise errors.TobizError(errors.NOT_FOUND, f"Блок {block_id} не найден на странице")
        block_type = await service.type_or_raise(project_id, block.type_id)
        block_domain.validate_values(block_type, {field: uploaded["filename"]})
        merged, changed = block_domain.apply_edits(block.values, {field: uploaded["filename"]})
        block.values = merged
        for path_name in changed:
            if path_name not in block.changed_paths:
                block.changed_paths.append(path_name)
        return {"filename": uploaded["filename"], "url_325": uploaded["url_325"],
                "field": field, "changed_fields": changed,
                "change_hash": draft.change_hash()}

    return registered


def _snippet(values: dict[str, Any], limit: int) -> str:
    """Короткий человекочитаемый текст блока: собираем строковые значения верхнего уровня."""
    parts: list[str] = []
    for key in ("title", "h1", "h2", "header", "text", "text1", "text2", "subtitle",
                "description", "logo_text", "btn_text", "phone1", "email"):
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for key, value in values.items():
        if len(parts) >= 6:
            break
        if isinstance(value, list) and value and isinstance(value[0], dict):
            for item in value[:3]:
                title = item.get("title") or item.get("name")
                if isinstance(title, str) and title.strip():
                    parts.append(title.strip())
    text = " | ".join(parts) or (values.get("anchor") or "")
    text = " ".join(str(text).split())
    return text[:limit]
