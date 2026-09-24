"""Прикладной слой: операции над сайтами, страницами и блоками.

Здесь нет ни MCP, ни HTTP-деталей: инструменты вызывают эти методы, а те работают с
нормализованными структурами (см. domain/ и tobiz/).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import errors, log
from .config import Config
from .domain import blocks as block_domain
from .domain.draft import Draft, DraftStore
from .render.bridge import RenderBridge
from .session import SessionStore
from .tobiz import endpoints as ep
from .tobiz import pages as page_forms
from .tobiz import payload as payload_builder
from .tobiz import upload as upload_module
from .tobiz.catalog import BlockType, Catalog
from .tobiz.client import TobizClient
from .tobiz.envelope import blocks_from, json_field
from .tobiz.pages import Page, Project, parse_projects

logger = log.get("service")


class Service:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.store = SessionStore(config)
        self.store.load()
        self.client = TobizClient(config, self.store)
        self.bridge = RenderBridge(config)
        self.catalog = Catalog(config, self.client, self.bridge)
        self.drafts = DraftStore()
        self._projects: list[Project] | None = None
        self._counters = {"auth_relogin": 0, "upstream_error": 0, "render_failed": 0}

    async def aclose(self) -> None:
        await self.client.aclose()

    # --- сессия ---

    async def login(self, force: bool = True) -> dict[str, Any]:
        return await self.client.login(force=force)

    async def session_status(self) -> dict[str, Any]:
        return self.client.describe_session()

    # --- проекты и страницы ---

    async def projects(self, refresh: bool = False) -> list[Project]:
        await self.client.ensure_session()
        if self._projects is not None and not refresh:
            return self._projects
        envelope = await self.client.panel_ajax(ep.PANEL_AJAX_ACTION_PROJECTS)
        if not envelope.ok:
            raise errors.TobizError(errors.ACCESS_DENIED, "Не удалось получить список проектов",
                                    "Проверьте сессию: tobiz_login")
        html = envelope.payload.get("html") or ""
        projects = parse_projects(str(html), self.config.lp_template)
        self._projects = projects
        return projects

    async def project(self, project_id: str | None = None, refresh: bool = False) -> Project:
        projects = await self.projects(refresh=refresh)
        if project_id:
            self.check_allowed(project_id)
            for project in projects:
                if project.project_id == str(project_id):
                    return project
            raise errors.TobizError(
                errors.NOT_FOUND, f"Проект {project_id} не найден среди проектов аккаунта",
                "Вызовите tobiz_list_projects",
            )
        if len(projects) == 1:
            self.check_allowed(projects[0].project_id)
            return projects[0]
        raise errors.TobizError(
            errors.AMBIGUOUS_PROJECT,
            "В аккаунте несколько проектов — укажите project_id",
            "Список проектов: tobiz_list_projects",
        )

    def check_allowed(self, project_id: str) -> None:
        allowed = self.config.allowed_project_ids
        if allowed and str(project_id) not in allowed:
            raise errors.TobizError(
                errors.PROJECT_NOT_ALLOWED,
                f"Проект {project_id} не входит в TOBIZ_ALLOWED_PROJECT_IDS",
                "Измените белый список или работайте с разрешённым проектом",
            )

    async def pages(self, project_id: str | None = None, refresh: bool = False) -> tuple[Project, list[Page]]:
        project = await self.project(project_id, refresh=refresh)
        return project, project.pages

    async def resolve_page(self, project_id: str | None, page_id: str) -> tuple[str, Page]:
        project, pages = await self.pages(project_id)
        for page in pages:
            if page.page_id == str(page_id):
                return project.project_id, page
        raise errors.TobizError(
            errors.NOT_FOUND, f"Страница {page_id} не найдена в проекте {project.project_id}",
            "Вызовите tobiz_list_pages",
        )

    # --- блоки ---

    async def _editor_page_meta(self, project_id: str, page_id: str) -> dict[str, Any]:
        html = await self.client.fetch_text(self.config.editor_url(project_id, page_id))
        marker = "window.tobiz = "
        start = html.find(marker)
        if start < 0:
            return {}
        start += len(marker)
        end = html.find("</script>", start)
        raw = html[start:end].strip().rstrip(";")
        try:
            meta = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("window.tobiz не разобран", extra={"page_id": page_id})
            return {}
        return meta if isinstance(meta, dict) else {}

    async def draft(self, project_id: str, page_id: str, refresh: bool = False) -> Draft:
        existing = self.drafts.get(project_id, page_id)
        if existing is not None and not refresh:
            return existing
        meta = await self._editor_page_meta(project_id, page_id)
        draft = existing or self.drafts.create(project_id, page_id, meta)
        draft.page_meta.update(meta)
        envelope = await self.client.editor_ajax(
            ep.ACT_GET_BLOCKS, self.config.lp_base(project_id), page_id, rep_id=page_id)
        if not envelope.ok:
            raise errors.TobizError(
                errors.ACCESS_DENIED,
                f"Конструктор не отдал блоки страницы: {envelope.message or envelope.status}",
                "Проверьте сессию и доступ к странице",
            )
        raw_blocks = blocks_from(envelope)
        if refresh:
            draft.blocks.clear()
            draft.order.clear()
            draft.changed_meta.clear()
        self.drafts.load_blocks(draft, raw_blocks)
        return draft

    async def block_types(self, project_id: str) -> dict[str, BlockType]:
        return await self.catalog.types(project_id)

    # --- статьи и товары ---

    async def module_list(self, project_id: str, kind: str, *, limit: int = 30,
                          page: int = 1, category: str = "all", search: str = "",
                          order_by: str = "sort_id") -> dict[str, Any]:
        await self.project(project_id)
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        action = "get_articles" if kind == "article" else "get_items"
        return await self.client.module_ajax(path, action, project_id, limit=limit, page=page,
                                             category=category, search=search, order_by=order_by)

    async def module_categories(self, project_id: str, kind: str) -> list[dict[str, Any]]:
        await self.project(project_id)
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        data = await self.client.module_ajax(path, "get_categories", project_id)
        return data if isinstance(data, list) else []

    async def module_get(self, project_id: str, kind: str, entity_id: str) -> dict[str, Any]:
        await self.project(project_id)
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        action = "get_article" if kind == "article" else "get_item"
        data = await self.client.module_ajax(path, action, project_id, id=entity_id)
        if not isinstance(data, dict) or not data.get("id"):
            raise errors.TobizError(errors.NOT_FOUND, f"Объект {entity_id} не найден")
        return data

    async def module_create(self, project_id: str, kind: str) -> dict[str, Any]:
        before = await self.module_list(project_id, kind, limit=100)
        key = "articles" if kind == "article" else "items"
        before_ids = {str(item.get("id")) for item in before.get(key, [])}
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        action = "add_article" if kind == "article" else "add_item"
        created = await self.client.module_ajax(path, action, project_id)
        if isinstance(created, dict) and created.get("id"):
            return await self.module_get(project_id, kind, str(created["id"]))
        after = await self.module_list(project_id, kind, limit=100)
        new_ids = [str(item.get("id")) for item in after.get(key, [])
                   if str(item.get("id")) not in before_ids]
        if len(new_ids) != 1:
            raise errors.TobizError(errors.SAVE_FAILED,
                                    "TOBIZ создал объект, но не удалось однозначно определить id")
        return await self.module_get(project_id, kind, new_ids[0])

    async def module_update(self, project_id: str, kind: str, entity_id: str,
                            fields: dict[str, Any], category_ids: list[str] | None = None) -> dict[str, Any]:
        current = await self.module_get(project_id, kind, entity_id)
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        if kind == "article":
            groups = {
                "update_article_str_data": {"title", "seo_title", "seo_keywords", "seo_description", "publication_date"},
                "update_article_description": {"description", "short_description"},
                "update_article_dir": {"dir"},
                "update_article_str_int": {"sort_id"},
            }
        else:
            groups = {
                "update_item_str_data": {"title", "vendor_code", "vendor", "brand", "material",
                                         "seo_title", "seo_keywords", "seo_description",
                                         "video1", "video2", "video3"},
                "update_item_description": {"description", "short_description"},
                "update_item_dir": {"dir"},
                "update_item_str_float": {"price", "quantity", "discount", "step", "min_in_order",
                                          "max_in_order", "width", "depth", "height", "weight"},
                "update_item_str_int": {"sort_id", "discount_type", "novelty", "sale", "bestseller",
                                        "not_available"},
            }
        allowed = set().union(*groups.values()) | {"visible"}
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    f"Неизвестные поля {kind}: {', '.join(unknown)}")
        for action, names in groups.items():
            for name in names & fields.keys():
                await self.client.module_ajax(path, action, project_id, id=entity_id,
                                              name=name, val=fields[name])
        if "visible" in fields:
            await self.client.module_ajax(path, "set_visible", project_id, id=entity_id,
                                          entity=kind, val=1 if fields["visible"] else 0)
        if category_ids is not None:
            relation_action = "update_article_relations" if kind == "article" else "update_item_relations"
            id_name = "article_id" if kind == "article" else "item_id"
            old_categories = {str(value) for value in current.get("categories", [])}
            new_categories = {str(value) for value in category_ids}
            for category_id in old_categories | new_categories:
                await self.client.module_ajax(path, relation_action, project_id,
                                              **{id_name: entity_id, "category_id": category_id,
                                                 "val": 1 if category_id in new_categories else 0})
        return await self.module_get(project_id, kind, entity_id)

    async def module_delete(self, project_id: str, kind: str, entity_id: str) -> dict[str, Any]:
        await self.module_get(project_id, kind, entity_id)
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        result = await self.client.module_ajax(path, "delete", project_id,
                                               id=entity_id, entity=kind)
        return {"id": entity_id, "deleted": bool(result)}

    async def module_upload_image(self, project_id: str, kind: str, entity_id: str,
                                  path: str | None = None, content_base64: str | None = None,
                                  file_name: str | None = None) -> dict[str, Any]:
        await self.module_get(project_id, kind, entity_id)
        prepared = upload_module.prepare(self.config, path, content_base64, file_name)
        endpoint = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        action = "upload_article_image" if kind == "article" else "upload_image"
        id_name = "article_id" if kind == "article" else "item_id"
        upload_entity = "article" if kind == "article" else "image"
        await self.client.module_upload(endpoint, project_id, action, upload_entity, id_name, entity_id,
                                        prepared.file_name, prepared.content, prepared.content_type)
        entity = await self.module_get(project_id, kind, entity_id)
        return {"id": entity_id, "images": entity.get("images", [])}

    async def module_sort_images(self, project_id: str, kind: str, entity_id: str,
                                 image_ids: list[str]) -> dict[str, Any]:
        entity = await self.module_get(project_id, kind, entity_id)
        current = [str(image.get("id")) for image in entity.get("images", []) if image.get("id")]
        requested = [str(value) for value in image_ids]
        if len(requested) != len(set(requested)) or set(requested) != set(current):
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    "image_ids должен содержать все текущие изображения ровно по одному разу",
                                    f"Текущий порядок: {current}")
        path = ep.ARTICLES_AJAX if kind == "article" else ep.PRODUCTS_AJAX
        action = "sort_article_images" if kind == "article" else "sort_images"
        params = {f"sort[{index}][0]": image_id for index, image_id in enumerate(requested)}
        params.update({f"sort[{index}][1]": index for index in range(len(requested))})
        await self.client.module_ajax(path, action, project_id, **params)
        updated = await self.module_get(project_id, kind, entity_id)
        return {"id": entity_id, "images": updated.get("images", [])}

    async def product_offer_get(self, project_id: str, offer_id: str) -> dict[str, Any]:
        await self.project(project_id)
        data = await self.client.module_ajax(ep.PRODUCTS_AJAX, "get_offer", project_id, id=offer_id)
        if not isinstance(data, dict) or not data.get("id"):
            raise errors.TobizError(errors.NOT_FOUND, f"Вариант товара {offer_id} не найден")
        return data

    async def product_offers(self, project_id: str, product_id: str) -> list[dict[str, Any]]:
        current = await self.module_get(project_id, "item", product_id)
        if isinstance(current.get("offers"), list):
            return list(current["offers"])
        data = await self.module_list(project_id, "item", limit=100,
                                      search=str(current.get("title") or ""))
        item = next((value for value in data.get("items", [])
                     if str(value.get("id")) == str(product_id)), None)
        return list((item or {}).get("offers") or [])

    async def product_offer_create(self, project_id: str, product_id: str,
                                   fields: dict[str, Any] | None = None) -> dict[str, Any]:
        before = {str(value.get("id")) for value in await self.product_offers(project_id, product_id)}
        created = await self.client.module_ajax(ep.PRODUCTS_AJAX, "add_offer", project_id, id=product_id)
        offer_id = str(created.get("id")) if isinstance(created, dict) and created.get("id") else ""
        if not offer_id:
            after = await self.product_offers(project_id, product_id)
            new_ids = [str(value.get("id")) for value in after if str(value.get("id")) not in before]
            if len(new_ids) != 1:
                raise errors.TobizError(errors.SAVE_FAILED,
                                        "Вариант создан, но TOBIZ не позволил однозначно определить id")
            offer_id = new_ids[0]
        return await self.product_offer_update(project_id, offer_id, fields or {})

    async def product_offer_update(self, project_id: str, offer_id: str,
                                   fields: dict[str, Any]) -> dict[str, Any]:
        await self.product_offer_get(project_id, offer_id)
        groups = {"update_offer_str_data": {"title", "vendor_code"},
                  "update_offer_str_float": {"price", "quantity"}}
        allowed = set().union(*groups.values()) | {"image_id"}
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise errors.TobizError(errors.BAD_ARGUMENT,
                                    f"Неизвестные поля варианта: {', '.join(unknown)}")
        for action, names in groups.items():
            for name in names & fields.keys():
                await self.client.module_ajax(ep.PRODUCTS_AJAX, action, project_id,
                                              id=offer_id, name=name, val=fields[name])
        if "image_id" in fields:
            await self.client.module_ajax(ep.PRODUCTS_AJAX, "set_offer_iamge", project_id,
                                          id=offer_id, image_id=fields["image_id"])
        return await self.product_offer_get(project_id, offer_id)

    async def product_offer_delete(self, project_id: str, offer_id: str) -> dict[str, Any]:
        await self.product_offer_get(project_id, offer_id)
        result = await self.client.module_ajax(ep.PRODUCTS_AJAX, "delete", project_id,
                                               id=offer_id, entity="offer")
        return {"id": offer_id, "deleted": bool(result)}

    async def site_styles(self, project_id: str, page_id: str, refresh: bool = False) -> dict[str, Any]:
        draft = await self.draft(project_id, page_id, refresh=refresh)
        config = draft.page_meta.get("page_config") or {}
        return dict(config) if isinstance(config, dict) else {}

    async def update_site_styles(self, project_id: str, page_id: str, styles: dict[str, Any],
                                 apply_to_all_pages: bool = False) -> dict[str, Any]:
        known = {"text_font", "text_fontsize", "text_fweight", "title_font", "title_fontsize",
                 "title_fweight", "menu_font", "menu_fontsize", "menu_fweight", "btn_bg",
                 "btn_bg_hover"}
        targets = [page_id]
        if apply_to_all_pages:
            _, pages = await self.pages(project_id, refresh=True)
            targets = [page.page_id for page in pages]
        changed_pages = []
        for target in targets:
            draft = await self.draft(project_id, target)
            current = draft.page_meta.get("page_config") or {}
            current = dict(current) if isinstance(current, dict) else {}
            unknown = sorted(set(styles) - known - set(current))
            if unknown:
                raise errors.TobizError(errors.BAD_ARGUMENT,
                                        f"Неизвестные поля оформления: {', '.join(unknown)}")
            changed = [key for key, value in styles.items() if current.get(key) != value]
            current.update(styles)
            draft.page_meta["page_config"] = current
            for key in changed:
                marker = f"page_config.{key}"
                if marker not in draft.changed_meta:
                    draft.changed_meta.append(marker)
            if changed:
                changed_pages.append({"page_id": target, "changed_fields": changed})
        return {"pages": changed_pages, "pending_save": bool(changed_pages)}

    async def inspect_page(self, project_id: str, page_id: str, *, screenshot: bool = True,
                           viewports: list[str] | None = None) -> dict[str, Any]:
        await self.resolve_page(project_id, page_id)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        output = Path(self.config.audit_dir) / "screenshots" / str(project_id) / str(page_id) / stamp
        return await self.bridge.inspect_page(self.config.public_url(project_id, page_id), output,
                                              viewports=viewports, screenshot=screenshot)

    async def audit_catalog(self, project_id: str,
                            type_ids: list[str] | None = None) -> dict[str, Any]:
        await self.catalog.ensure_assets(project_id)
        vendor_dir = self.catalog.project_dir(project_id) / "bundles"
        selected = list(type_ids or (await self.block_types(project_id)).keys())
        samples_by_type: dict[str, list[dict[str, Any]]] = {}
        _, pages = await self.pages(project_id, refresh=True)
        for page in pages:
            draft = await self.draft(project_id, page.page_id, refresh=True)
            for block_id in draft.order:
                block = draft.blocks[block_id]
                if block.deleted or block.type_id not in selected:
                    continue
                samples = samples_by_type.setdefault(block.type_id, [])
                sample_limit = 100 if block.type_id == "1600" else 5
                if len(samples) < sample_limit:
                    samples.append(block.values)
        block_types = await self.block_types(project_id)
        for type_id in selected:
            if type_id in samples_by_type:
                continue
            block_type = block_types.get(type_id)
            if block_type is None:
                continue
            defaults = await self.catalog.default_values(project_id, block_type)
            if defaults:
                samples_by_type[type_id] = [defaults]
        combined: dict[str, Any] = {
            "ok": True, "types_checked": 0, "cases_checked": 0,
            "passed": 0, "failed": 0, "failures": [], "by_type": {},
        }
        # jsdom is intentionally process-scoped; batches keep a full-catalog audit below the
        # Node heap limit even for thousands of checkbox/select combinations.
        for offset in range(0, len(selected), 12):
            batch = selected[offset:offset + 12]
            result = await self.bridge.audit(
                vendor_dir, batch,
                {type_id: samples_by_type[type_id] for type_id in batch
                 if type_id in samples_by_type},
            )
            combined["types_checked"] += int(result.get("types_checked") or 0)
            combined["cases_checked"] += int(result.get("cases_checked") or 0)
            combined["passed"] += int(result.get("passed") or 0)
            combined["failed"] += int(result.get("failed") or 0)
            combined["failures"].extend(result.get("failures") or [])
            combined["by_type"].update(result.get("by_type") or {})
        combined["ok"] = combined["failed"] == 0
        combined["types_with_server_samples"] = len(samples_by_type)
        flex_samples = list(samples_by_type.get("1600", []))
        flex_type = block_types.get("1600")
        if flex_type and flex_type.values:
            flex_samples.insert(0, flex_type.values)
        flex_element_types: dict[str, int] = {}
        flex_style_keys: dict[str, int] = {}
        flex_elements = 0
        for sample in flex_samples:
            flexblocks = sample.get("flexblocks") or []
            if isinstance(flexblocks, dict):
                flexblocks = list(flexblocks.values())
            if not isinstance(flexblocks, list):
                continue
            for element in flexblocks:
                if not isinstance(element, dict):
                    continue
                flex_elements += 1
                element_type = str(element.get("type") or element.get("type_id") or "unknown")
                flex_element_types[element_type] = flex_element_types.get(element_type, 0) + 1
                for key in element:
                    if key.startswith(("style", "desktop", "tablet", "mobile")):
                        flex_style_keys[key] = flex_style_keys.get(key, 0) + 1
        combined["flex"] = {
            "samples": len(flex_samples),
            "elements": flex_elements,
            "element_types": flex_element_types,
            "supported_element_types": [
                "text", "html", "mdicon", "figure", "hint",
                "image", "video", "form", "btn",
            ],
            "responsive_style_keys": flex_style_keys,
        }
        return combined

    async def block_controls(self, project_id: str, *, type_id: str = "",
                             category_id: str = "", query: str = "",
                             control_type: str = "interactive", limit: int = 50,
                             offset: int = 0) -> dict[str, Any]:
        """Return editor switches/selects for block types and all palette variants."""
        block_types = await self.block_types(project_id)
        variants = await self.catalog.variants_by_type(project_id)
        needle = query.strip().lower()
        items: list[dict[str, Any]] = []
        controls_total = 0
        for block_type in block_types.values():
            if type_id and block_type.type_id != str(type_id):
                continue
            type_variants = variants.get(block_type.type_id, [])
            categories = {str(item.get("category_id") or "") for item in type_variants}
            if category_id and str(category_id) not in categories:
                continue
            searchable = " ".join([
                block_type.type_id, block_type.title, block_type.description,
                *[str(item.get("title") or "") for item in type_variants],
            ]).lower()
            if needle and needle not in searchable:
                continue
            controls = block_domain.control_schema(block_type, control_type)
            if not controls:
                continue
            controls_total += len(controls)
            items.append({
                "type_id": block_type.type_id,
                "title": block_type.title,
                "category_id": block_type.category_id,
                "has_template": block_type.has_template,
                "controls": controls,
                "controls_count": len(controls),
                "variant_count": len(type_variants),
                "variants": type_variants,
            })
        items.sort(key=lambda item: (int(item["type_id"])
                                     if str(item["type_id"]).isdigit() else 10**9,
                                     str(item["type_id"])))
        total = len(items)
        start = max(0, int(offset or 0))
        size = max(1, min(int(limit or 50), 100))
        return {
            "project_id": project_id,
            "control_type": control_type,
            "total": total,
            "controls_total": controls_total,
            "limit": size,
            "offset": start,
            "items": items[start:start + size],
            "verification": "Use tobiz_audit_catalog(type_ids=[...]) to render both checkbox "
                            "states and every select option without changing the site.",
        }

    async def type_or_raise(self, project_id: str, type_id: str) -> BlockType:
        types = await self.block_types(project_id)
        block_type = types.get(str(type_id))
        if block_type is None:
            raise errors.TobizError(
                errors.UNKNOWN_TYPE, f"Тип блока {type_id} отсутствует в сборке проекта",
                "Поиск по каталогу: tobiz_search_blocks",
            )
        if not block_type.has_template:
            raise errors.TobizError(
                errors.TEMPLATE_UNAVAILABLE,
                f"У типа {type_id} нет шаблона в этой сборке — рендер невозможен",
                "Выберите другой тип: tobiz_search_blocks",
            )
        return block_type

    def merged_values(self, block_type: BlockType, data: dict[str, Any],
                      server_defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        """Порядок важен: дефолты вендора -> серверные дефолты -> фактические значения."""
        merged: dict[str, Any] = dict(block_type.values)
        if server_defaults:
            merged.update(server_defaults)
        merged.update(data or {})
        return merged

    # --- изображения ---

    async def upload_image(self, project_id: str, page_id: str, block_id: str,
                           path: str | None = None, content_base64: str | None = None,
                           file_name: str | None = None) -> dict[str, Any]:
        # upload.php требует block_id: без него конструктор отвечает «Изображение не загружено! #2»,
        # и это легко принять за запрет загрузки тарифом (проверено живой загрузкой логотипа).
        if not str(block_id or "").strip():
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Не указан block_id: конструктор требует его при загрузке файла",
                "Возьмите block_id из tobiz_list_blocks или из ответа tobiz_add_block",
            )
        prepared = upload_module.prepare(self.config, path, content_base64, file_name)
        result = await self.client.upload_image(
            prepared.file_name, prepared.content, prepared.content_type, block_id,
            self.config.lp_base(project_id), page_id, project_id,
        )
        await self.audit("tobiz_upload_image", project_id, page_id=page_id, block_id=block_id,
                         extra={"filename": prepared.file_name, "bytes": prepared.size})
        return {
            "filename": result.get("image"),
            "bytes": prepared.size,
            "url_original": f"/img/original/{result.get('image')}",
            "url_325": f"/img/325x0/{result.get('image')}",
            "raw": result if result.get("msg") else None,
        }

    # --- параметры страницы: название, slug, SEO, доступ, og:image ---

    #: имя параметра инструмента -> (имя поля формы edit_page, тип)
    PAGE_EDIT_FIELDS = {
        "title": ("page_title", "text"),
        "dir": ("page_dir", "text"),
        "seo_title": ("page_seo_title", "text"),
        "seo_keywords": ("page_seo_keywords", "text"),
        "seo_description": ("page_seo_description", "text"),
        "og_image": ("page_image", "radio"),
        "valid_login": ("page_valid_login", "text"),
        "valid_password": ("page_valid_password", "text"),
        "personal_seo_configs": ("page_user_personal_seo_configs", "checkbox"),
        "access_control": ("page_access_control", "checkbox"),
    }

    async def page_form(self, project_id: str, page_id: str) -> page_forms.PageForm:
        """Текущие параметры страницы: форма action=edit_page_form."""
        await self.resolve_page(project_id, page_id)
        envelope = await self.client.panel_ajax(
            ep.PANEL_AJAX_ACTION_EDIT_PAGE_FORM, page_id=page_id)
        if not envelope.ok:
            raise errors.TobizError(
                errors.UPSTREAM_UNAVAILABLE,
                f"Конструктор не отдал форму страницы: {envelope.message or envelope.status}",
                "Проверьте page_id и сессию (tobiz_session_status)",
            )
        return page_forms.parse_edit_form(str(envelope.payload.get("html") or ""))

    async def update_page(self, project_id: str, page_id: str, **fields: Any) -> dict[str, Any]:
        """Правка параметров страницы через action=edit_page.

        Панель принимает полный набор полей формы (как это делает редактор), поэтому сначала
        читаем форму и отправляем её целиком с замененными значениями: иначе не переданные
        поля могут обнулиться. В отличие от блоков, изменения уходят на сервер сразу.
        """
        if self.config.read_only:
            raise errors.read_only()
        project_id, _ = await self.resolve_page(project_id, page_id)

        unknown = [name for name, value in fields.items()
                   if value is not None and name not in self.PAGE_EDIT_FIELDS]
        if unknown:
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                f"Неизвестные параметры страницы: {', '.join(sorted(unknown))}",
                f"Разрешены: {', '.join(sorted(self.PAGE_EDIT_FIELDS))}",
            )

        form = await self.page_form(project_id, page_id)
        params = dict(form.fields)
        applied: dict[str, Any] = {}
        for name, value in fields.items():
            if value is None:
                continue
            payload_key, kind = self.PAGE_EDIT_FIELDS[name]
            if kind == "checkbox":
                if value:
                    params[payload_key] = "1"
                else:
                    params.pop(payload_key, None)
                applied[payload_key] = bool(value)
                continue
            params[payload_key] = "" if value == "" else str(value)
            applied[payload_key] = params[payload_key]
        if not applied:
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                "Не передано ни одного параметра страницы",
                "Например: seo_title, seo_description, seo_keywords, og_image",
            )
        params["page_id"] = str(page_id)
        params.pop("action", None)

        envelope = await self.client.panel_ajax(
            ep.PANEL_AJAX_ACTION_EDIT_PAGE, **params)
        if not envelope.ok:
            raise errors.TobizError(
                errors.SAVE_FAILED,
                f"Конструктор не изменил параметры страницы: {envelope.message or envelope.status}",
                "Проверьте значения: slug может быть занят, картинка — не из списка",
                raw={"status": envelope.status, "body": envelope.raw_text[:500]},
            )

        # читаем форму заново: подтверждаем, что применилось именно то, что просили
        after = await self.page_form(project_id, page_id)
        # SaveBlocks тоже несёт SEO из page_meta: обновляем кеш черновика значениями из формы,
        # иначе следующее сохранение блоков вернёт старые SEO (window.tobiz может отставать)
        draft = self.drafts.get(project_id, page_id)
        if draft is not None:
            applied_form = after.to_dict()
            draft.page_meta.update({
                "page_title": applied_form.get("page_title", ""),
                "page_dir": applied_form.get("page_dir", ""),
                "seo_title": applied_form.get("page_seo_title", ""),
                "seo_keywords": applied_form.get("page_seo_keywords", ""),
                "seo_description": applied_form.get("page_seo_description", ""),
                "OG_image": applied_form.get("page_image", ""),
                "personal_seo_configs": "1" if applied_form.get("page_user_personal_seo_configs")
                else "0",
            })
        self._projects = None  # кеш списка страниц устарел: могли поменяться название и адрес

        result = after.to_dict()
        mismatched = {
            key: value for key, value in applied.items()
            if str(result.get(key, "")) != str(value)
            and not (isinstance(value, bool) and bool(result.get(key)) is value)
        }
        await self.audit("tobiz_update_page", project_id, page_id=page_id,
                         extra={"fields": sorted(applied), "mismatched": sorted(mismatched)})
        return {
            "page_id": page_id,
            "applied": applied,
            "page": result,
            "mismatched": mismatched,
            "note": "Изменения уже на сайте: edit_page пишет сразу, без tobiz_save_page",
        }

    def page_info(self, draft: Draft) -> dict[str, Any]:
        """Параметры страницы из кеша редактора (window.tobiz) — может отставать."""
        meta = draft.page_meta
        return {
            "page_title": meta.get("page_title") or "",
            "page_dir": meta.get("page_dir") or "",
            "seo_title": meta.get("seo_title") or "",
            "seo_keywords": meta.get("seo_keywords") or "",
            "seo_description": meta.get("seo_description") or "",
            "personal_seo_configs": str(meta.get("personal_seo_configs") or "0"),
            "hint": "точные текущие значения — tobiz_page_info",
        }

    # --- копирование и удаление страницы ---

    async def copy_page_form(self, project_id: str, page_id: str) -> page_forms.PageForm:
        """Форма копирования: название копии и список доступных проектов."""
        await self.resolve_page(project_id, page_id)
        envelope = await self.client.panel_ajax(
            ep.PANEL_AJAX_ACTION_COPY_PAGE_FORM, page_id=page_id)
        if not envelope.ok:
            raise errors.TobizError(
                errors.UPSTREAM_UNAVAILABLE,
                f"Конструктор не отдал форму копирования: {envelope.message or envelope.status}",
                "Проверьте page_id и сессию (tobiz_session_status)",
            )
        return page_forms.parse_edit_form(str(envelope.payload.get("html") or ""))

    async def copy_page(self, project_id: str, page_id: str, title: str | None = None,
                        target_project: str | None = None, apply: bool = True) -> dict[str, Any]:
        """Копирует страницу в проект (по умолчанию — в текущий).

        apply=False — только показать, что будет отправлено, ничего не создавая.
        """
        if self.config.read_only:
            raise errors.read_only()
        project_id, page = await self.resolve_page(project_id, page_id)
        form = await self.copy_page_form(project_id, page_id)
        targets = form.selects.get("new_project") or []
        new_title = title or form.text.get("page_title") or f"Копия {page.title}"
        target = str(target_project or "").strip()
        if not target:
            selected = [v for v in targets if v.get("selected") == "1"]
            target = (selected[0]["value"] if selected else (targets[0]["value"] if targets else project_id))
        if targets and target not in [v["value"] for v in targets]:
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                f"Проект {target} недоступен для копирования",
                "Доступные проекты: " + ", ".join(f"{v['value']} «{v['title']}»" for v in targets),
            )
        plan = {"page_id": page_id, "page_title": new_title, "new_project": target}
        if not apply:
            return {"dry_run": True, "will_send": plan, "targets": targets}

        projects_before = await self.projects(refresh=True)
        before = {p.page_id for project in projects_before
                  if project.project_id == str(target) for p in project.pages}
        envelope = await self.client.panel_ajax(ep.PANEL_AJAX_ACTION_COPY_PAGE, **plan)
        if not envelope.ok:
            raise errors.TobizError(
                errors.SAVE_FAILED,
                f"Конструктор не скопировал страницу: {envelope.message or envelope.status}",
                "Проверьте название и целевой проект",
                raw={"status": envelope.status, "body": envelope.raw_text[:500]},
            )
        self._projects = None
        projects = await self.projects(refresh=True)
        created: list[dict[str, Any]] = []
        for project in projects:
            if project.project_id != str(target):
                continue
            for page_item in project.pages:
                if page_item.page_id not in before:
                    created.append(page_item.to_dict(self.config.lp_template, project.project_id))
        await self.audit("tobiz_copy_page", project_id, page_id=page_id,
                         extra={"title": new_title, "new_project": target})
        return {"copied_from": page_id, "title": new_title, "new_project": target,
                "created": created, "response": envelope.status,
                "note": "Новая страница пустая по контенту? Нет — копия содержит блоки источника; "
                        "проверьте её в tobiz_list_pages"}

    async def delete_page(self, project_id: str, page_id: str, confirm: bool = False) -> dict[str, Any]:
        """Удаляет страницу. Требует confirm=True — операция необратимая."""
        if self.config.read_only:
            raise errors.read_only()
        project_id, page = await self.resolve_page(project_id, page_id)
        if not confirm:
            raise errors.TobizError(
                errors.BAD_ARGUMENT,
                f"Удаление страницы {page_id} «{page.title}» не подтверждено",
                "Повторите вызов с confirm=true, если страницу действительно надо удалить",
            )
        envelope = await self.client.panel_ajax(
            ep.PANEL_AJAX_ACTION_DELETE_PAGE, page_id=page_id)
        if not envelope.ok:
            raise errors.TobizError(
                errors.SAVE_FAILED,
                f"Конструктор не удалил страницу: {envelope.message or envelope.status}",
                "Возможно, страница уже удалена — проверьте tobiz_list_pages",
                raw={"status": envelope.status, "body": envelope.raw_text[:500]},
            )
        self.drafts.drop(project_id, page_id)
        self._projects = None
        remaining = [p.page_id for project in await self.projects(refresh=True)
                     if project.project_id == project_id for p in project.pages]
        await self.audit("tobiz_delete_page", project_id, page_id=page_id,
                         extra={"title": page.title})
        return {"deleted": page_id, "title": page.title, "remaining_pages": remaining,
                "response": envelope.status}

    # --- сохранение ---

    async def save_page(self, project_id: str, page_id: str, verify: bool = True,
                        only_if_changed: bool = True,
                        expected_block_hashes: dict[str, str] | None = None,
                        include_payload: bool = False) -> dict[str, Any]:
        if self.config.read_only:
            raise errors.read_only()
        draft = await self.draft(project_id, page_id)
        if only_if_changed:
            draft.ensure_changes()
        if expected_block_hashes:
            for block_id, expected in expected_block_hashes.items():
                block = draft.blocks.get(str(block_id))
                if block is None:
                    raise errors.TobizError(errors.NOT_FOUND, f"Блок {block_id} исчез из черновика")
                current = json.dumps(block.values, ensure_ascii=False, sort_keys=True)
                import hashlib
                current_hash = hashlib.sha256(current.encode()).hexdigest()[:16]
                if current_hash != expected:
                    raise errors.TobizError(
                        errors.CONFLICT,
                        f"Блок {block_id} изменился после чтения (ожидался {expected})",
                        "Перечитайте блок и повторите правку",
                    )

        types = await self.block_types(project_id)
        items: list[dict[str, Any]] = []
        for block_id in draft.order:
            block = draft.blocks.get(block_id)
            if block is None:
                continue
            block_type = types.get(block.type_id)
            server_defaults: dict[str, Any] = {}
            if block_type is not None:
                try:
                    server_defaults = await self.catalog.default_values(project_id, block_type)
                except errors.TobizError:
                    server_defaults = {}
            base_values = block_type.values if block_type else {}
            values = {**base_values, **server_defaults, **block.values}
            items.append({"block_id": block_id, "type_id": block.type_id, "values": values})

        project_dir = self.catalog.project_dir(project_id) / "bundles"
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            rendered = await self.bridge.render(project_dir, items)
        except errors.TobizError:
            self._counters["render_failed"] += 1
            raise

        for block_id, html in rendered.items():
            block = draft.blocks.get(block_id)
            if block is not None:
                # старый cache сохраняем на случай повторного сохранения без рендера
                block.cache = html

        payload = payload_builder.build(draft, rendered)
        if self.config.dry_run or include_payload:
            preview = {
                "blocks": len(payload["userBlocks"]),
                "changed": draft.changed_blocks,
                "change_hash": draft.change_hash(),
                "payload": payload if include_payload else None,
            }
            if self.config.dry_run:
                preview["dry_run"] = True
                return preview

        envelope = await self.client.editor_ajax(
            ep.ACT_SAVE_BLOCKS, self.config.lp_base(project_id), page_id,
            data=json.dumps(payload, ensure_ascii=False))
        if not envelope.ok:
            raise errors.TobizError(
                errors.SAVE_FAILED,
                f"Конструктор не сохранил страницу: {envelope.message or envelope.status}",
                "Черновик сохранён в памяти: повторите tobiz_save_page",
                raw={"status": envelope.status, "body": envelope.raw_text[:500]},
            )

        change_hash = draft.change_hash()
        # счётчики считаем ДО сброса правок: иначе ответ сообщает «изменено 0 блоков»
        changed_blocks = list(draft.changed_blocks)
        for block_id in changed_blocks:
            draft.blocks[block_id].changed_paths = []
        changed_meta = list(draft.changed_meta)
        draft.changed_meta.clear()
        await self.audit("tobiz_save_page", project_id, page_id=page_id,
                         extra={"blocks_total": len(items), "blocks_changed": len(changed_blocks),
                                "change_hash": change_hash, "result": "ok"})

        result: dict[str, Any] = {
            "saved": True,
            "blocks_total": len(items),
            "blocks_changed": len(changed_blocks),
            "meta_changed": changed_meta,
            "change_hash": change_hash,
            "response": envelope.message or envelope.status,
        }
        if verify:
            result["verify"] = await self.verify_page(project_id, page_id)
        if include_payload:
            result["payload"] = payload
        return result

    # --- верификация ---

    async def verify_page(self, project_id: str, page_id: str,
                          expect: list[str] | None = None,
                          block_ids: list[str] | None = None) -> dict[str, Any]:
        try:
            html = await self.client.fetch_text(self.config.public_url(project_id, page_id))
        except errors.TobizError as exc:
            return {"status": "unavailable", "reason": exc.message}
        found: list[str] = []
        missing: list[str] = []
        for needle in expect or []:
            (found if needle in html else missing).append(needle)
        blocks_report: dict[str, bool] = {}
        for block_id in block_ids or []:
            blocks_report[str(block_id)] = f'id="b_{block_id}"' in html
        status = "ok"
        if missing or not all(blocks_report.values()):
            status = "mismatch"
        return {"status": status, "bytes": len(html), "found": found, "missing": missing,
                "blocks": blocks_report or None}

    # --- журнал ---

    async def audit(self, tool: str, project_id: str, page_id: str | None = None,
                    block_id: str | None = None, extra: dict[str, Any] | None = None) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool": tool,
            "project_id": str(project_id),
            "page_id": str(page_id) if page_id else None,
            "block_id": str(block_id) if block_id else None,
        }
        record.update(extra or {})
        try:
            self.config.audit_dir.mkdir(parents=True, exist_ok=True)
            with (self.config.audit_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:  # журнал не должен ломать операцию
            logger.warning("журнал недоступен: %s", exc)

    async def health(self) -> dict[str, Any]:
        from . import __version__

        return {
            "version": __version__,
            "transport": self.config.transport,
            "read_only": self.config.read_only,
            "dry_run": self.config.dry_run,
            "session": self.client.describe_session(),
            "assets_dir": str(self.config.assets_dir),
            "renderer_available": self.bridge.available,
            "counters": dict(self._counters),
        }
