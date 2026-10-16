"""Deterministic contracts for planning a native TOBIZ multi-page site."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Awaitable, Callable


GOALS = {"lead_generation", "education", "ecommerce"}


def _issue(items: list[dict[str, Any]], code: str, action: str, **details: Any) -> None:
    items.append({"priority": "must_fix", "code": code, "action": action, **details})


def validate(site_brief: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    if not isinstance(site_brief, dict) or not site_brief:
        _issue(blockers, "multipage_site_brief_missing",
               "Передать общий бриф, единый для всех страниц сайта.")
    if not isinstance(pages, list) or not 2 <= len(pages) <= 20:
        _issue(blockers, "multipage_page_count_invalid",
               "Передать от 2 до 20 страниц многостраничного сайта.", count=len(pages or []))

    for index, raw in enumerate(pages or []):
        if not isinstance(raw, dict):
            _issue(blockers, "multipage_page_invalid", "Каждая страница должна быть объектом.",
                   page_index=index)
            continue
        key = str(raw.get("key") or "").strip().lower()
        title = str(raw.get("title") or "").strip()
        slug = str(raw.get("slug") or "").strip().strip("/").lower()
        purpose = str(raw.get("purpose") or "").strip()
        goal = str(raw.get("goal") or site_brief.get("goal") or "lead_generation").strip()
        is_home = raw.get("is_home") is True or slug == ""
        menu_title = str(raw.get("menu_title") or title).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", key):
            _issue(blockers, "multipage_key_invalid",
                   "Задать стабильный key латиницей для каждой страницы.", page_index=index, value=key)
        if len(title) < 3:
            _issue(blockers, "multipage_title_missing",
                   "Задать понятное название каждой страницы.", page_index=index)
        if not purpose:
            _issue(blockers, "multipage_purpose_missing",
                   "Объяснить роль страницы в пути пользователя.", page_index=index)
        if not is_home and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            _issue(blockers, "multipage_slug_invalid",
                   "Использовать URL латиницей через дефисы.", page_index=index, value=slug)
        if goal not in GOALS:
            _issue(blockers, "multipage_goal_invalid",
                   "Использовать lead_generation, education или ecommerce.",
                   page_index=index, value=goal)
        if not menu_title or len(menu_title) > 24:
            _issue(blockers, "multipage_menu_title_invalid",
                   "Задать короткий пункт меню длиной до 24 символов.",
                   page_index=index, value=menu_title)
        page_brief = dict(site_brief)
        page_brief.update(raw.get("brief") if isinstance(raw.get("brief"), dict) else {})
        page_brief["page_purpose"] = purpose
        page_brief["page_title"] = title
        normalized.append({
            "index": index, "key": key, "title": title, "slug": slug,
            "is_home": is_home, "menu_title": menu_title, "purpose": purpose,
            "goal": goal, "brief": page_brief,
            "href": "/" if is_home else f"/{slug}/",
        })

    for field in ("key", "slug", "title"):
        values: dict[str, list[int]] = {}
        for item in normalized:
            value = str(item[field]).casefold()
            values.setdefault(value, []).append(item["index"])
        for value, indexes in values.items():
            if len(indexes) > 1:
                _issue(blockers, f"multipage_{field}_duplicate",
                       f"Сделать {field} каждой страницы уникальным.", value=value, indexes=indexes)
    homes = [item["index"] for item in normalized if item["is_home"]]
    if len(homes) != 1:
        _issue(blockers, "multipage_home_count_invalid",
               "Отметить ровно одну главную страницу с пустым slug.", indexes=homes)

    menu = [{"title": item["menu_title"], "href": item["href"], "page_key": item["key"]}
            for item in normalized]
    identity_source = {"site_brief": site_brief, "pages": [
        {key: item[key] for key in ("key", "title", "slug", "purpose", "goal")}
        for item in normalized]}
    identity = hashlib.sha256(json.dumps(
        identity_source, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": 1, "multipage_id": f"multipage:{identity}",
        "ready_for_planning": not blockers, "site_brief": dict(site_brief or {}),
        "pages": normalized, "menu": menu, "blockers": blockers,
        "rules": {"native_only": True, "shared_visual_system": True,
                  "unique_routes": True, "one_home_page": True},
    }


def combine(manifest: dict[str, Any], page_plans: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = list(manifest.get("blockers") or [])
    by_key = {str(item.get("key")): item for item in page_plans}
    systems: dict[str, list[str]] = {}
    for page in manifest.get("pages") or []:
        key = page["key"]
        plan = by_key.get(key)
        if not plan:
            _issue(blockers, "multipage_page_plan_missing",
                   "Подготовить план каждой страницы до сборки.", page_key=key)
            continue
        visual = str((plan.get("template") or {}).get("visual_system") or "")
        if visual:
            systems.setdefault(visual, []).append(key)
        readiness = plan.get("brief_readiness") or {}
        architecture = plan.get("architecture_readiness") or {}
        conversion = plan.get("conversion_readiness") or {}
        if not (readiness.get("ready_for_quality_build")
                and architecture.get("ready") and conversion.get("ready")):
            _issue(blockers, "multipage_page_plan_not_ready",
                   "Исправить бриф, архитектуру или конверсионный путь страницы.",
                   page_key=key,
                   failed={"brief": not readiness.get("ready_for_quality_build"),
                           "architecture": not architecture.get("ready"),
                           "conversion": not conversion.get("ready")})
    if len(systems) > 1:
        _issue(blockers, "multipage_visual_system_inconsistent",
               "Выбрать единый визуальный язык для всех страниц.", systems=systems)
    return {**manifest, "page_plans": page_plans, "visual_systems": systems,
            "ready_for_packages": not blockers, "blockers": blockers,
            "next_action": "tobiz_prepare_multipage_package" if not blockers
                           else "fix_multipage_plan_blockers"}


def package(plan: dict[str, Any], page_packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap independently editable native page packages in one immutable site envelope."""
    expected = [str(item.get("key")) for item in plan.get("pages") or []]
    actual = [str(item.get("key")) for item in page_packages]
    blockers: list[dict[str, Any]] = []
    if actual != expected:
        _issue(blockers, "multipage_package_order_mismatch",
               "Подготовить по одному пакету в порядке карты страниц.",
               expected=expected, actual=actual)
    for item in page_packages:
        nested = item.get("package") if isinstance(item.get("package"), dict) else {}
        if not nested.get("package_id") or not nested.get("plan_id"):
            _issue(blockers, "multipage_nested_package_invalid",
                   "Повторно подготовить штатный пакет страницы.", page_key=item.get("key"))
    return {
        "schema_version": 1, "multipage_package_id": f"{plan.get('multipage_id')}:v1",
        "multipage_id": plan.get("multipage_id"), "site_brief": plan.get("site_brief"),
        "menu": plan.get("menu"), "pages": page_packages,
        "ready_to_fill": not blockers, "blockers": blockers,
        "workflow": [
            "Fill each nested package with tobiz_fill_package_content and tobiz_fill_package_media.",
            "Check the complete envelope with tobiz_multipage_package_status.",
            "Build only after every nested page reports ready_for_build.",
            "After building, run tobiz_audit_project for the complete project.",
        ],
    }


def progress(package_value: dict[str, Any], statuses: list[dict[str, Any]]) -> dict[str, Any]:
    pages = package_value.get("pages") if isinstance(package_value.get("pages"), list) else []
    by_key = {str(item.get("key")): item for item in statuses}
    items = []
    for page in pages:
        key = str(page.get("key") or "")
        status = by_key.get(key) or {}
        page_progress = status.get("progress") if isinstance(status.get("progress"), dict) else {}
        items.append({"key": key, "title": page.get("title"),
                      "completion_percent": int(page_progress.get("completion_percent") or 0),
                      "ready_for_build": page_progress.get("ready_for_build") is True,
                      "next_action": page_progress.get("next_action") or "check_page_package"})
    navigation = validate_navigation(package_value)
    ready = (bool(items) and all(item["ready_for_build"] for item in items)
             and navigation["ready"])
    average = round(sum(item["completion_percent"] for item in items) / len(items)) if items else 0
    return {"ready_for_build": ready, "completion_percent": average,
            "pages_ready": sum(item["ready_for_build"] for item in items),
            "pages_total": len(items), "pages": items, "navigation": navigation,
            "next_action": "tobiz_build_multipage_package" if ready
                           else ("fix_shared_navigation" if not navigation["ready"]
                                 else "fill_incomplete_page_packages")}


def validate_navigation(package_value: dict[str, Any]) -> dict[str, Any]:
    """Require every page package to contain the exact shared native menu routes."""
    expected = [str(item.get("href") or "") for item in package_value.get("menu") or []]
    issues: list[dict[str, Any]] = []
    pages = package_value.get("pages") if isinstance(package_value.get("pages"), list) else []
    for page in pages:
        nested = page.get("package") if isinstance(page.get("package"), dict) else {}
        slots = (nested.get("recipe") or {}).get("slots") or []
        menu_links = [str(slot.get("value") or "").strip() for slot in slots
                      if isinstance(slot, dict) and slot.get("kind") == "link"
                      and "menu" in str(slot.get("path") or "").lower()]
        if not menu_links:
            _issue(issues, "multipage_native_menu_missing",
                   "Использовать штатную шапку с редактируемым меню на каждой странице.",
                   page_key=page.get("key"))
            continue
        missing = [href for href in expected if href not in menu_links]
        if missing:
            _issue(issues, "multipage_navigation_incomplete",
                   "Заполнить общее штатное меню всеми маршрутами проекта.",
                   page_key=page.get("key"), missing=missing, actual=menu_links)
    return {"ready": not issues, "expected": expected, "issues": issues}


async def transactional_build(
        pages: list[dict[str, Any]],
        build: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        rollback: Callable[[str], Awaitable[Any]]) -> list[dict[str, Any]]:
    """Build pages in order and roll back every page created by this call on failure."""
    created: list[dict[str, Any]] = []
    try:
        for page in pages:
            result = await build(page)
            page_id = str((result.get("page") or {}).get("page_id") or "")
            if not page_id:
                raise ValueError("Builder did not return page.page_id")
            created.append({"key": page.get("key"), "page_id": page_id, "result": result})
    except Exception:
        for item in reversed(created):
            try:
                await rollback(item["page_id"])
            except Exception:
                pass
        raise
    return created
