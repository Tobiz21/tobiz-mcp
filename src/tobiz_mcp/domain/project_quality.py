"""Project-level quality checks for native TOBIZ multi-page sites."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


def _issue(issues: list[dict[str, Any]], priority: str, code: str, action: str,
           **details: Any) -> None:
    issues.append({"priority": priority, "code": code, "action": action, **details})


def audit(pages: list[dict[str, Any]]) -> dict[str, Any]:
    visible = [page for page in pages if page.get("visible", True)]
    issues: list[dict[str, Any]] = []
    slugs: dict[str, list[str]] = {}
    seo_titles: dict[str, list[str]] = {}
    header_types: list[str] = []
    footer_types: list[str] = []

    if len(visible) < 2:
        _issue(issues, "must_fix", "multipage_has_fewer_than_two_visible_pages",
               "Добавить минимум две содержательные видимые страницы или собирать проект как лендинг.")

    for page in visible:
        page_id = str(page.get("page_id") or "")
        title = str(page.get("title") or "").strip()
        form = page.get("page") if isinstance(page.get("page"), dict) else {}
        slug = str(form.get("page_dir") if "page_dir" in form else page.get("slug") or "")
        slug = slug.strip().strip("/")
        seo_title = str(form.get("page_seo_title") or "").strip()
        seo_description = str(form.get("page_seo_description") or "").strip()
        composition = page.get("composition") if isinstance(page.get("composition"), dict) else {}
        sections = composition.get("sections") if isinstance(composition.get("sections"), list) else []

        if len(title) < 3:
            _issue(issues, "must_fix", "page_title_missing",
                   "Задать понятное название страницы в панели TOBIZ.", page_id=page_id)
        if slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            _issue(issues, "must_fix", "page_slug_invalid",
                   "Использовать URL латиницей через дефисы.", page_id=page_id, value=slug)
        slugs.setdefault(slug, []).append(page_id)
        if not 20 <= len(seo_title) <= 75:
            _issue(issues, "must_fix", "page_seo_title_length",
                   "Задать уникальный SEO title длиной 20-75 символов.",
                   page_id=page_id, chars=len(seo_title))
        else:
            seo_titles.setdefault(seo_title.casefold(), []).append(page_id)
        if not 80 <= len(seo_description) <= 200:
            _issue(issues, "must_fix", "page_seo_description_length",
                   "Задать SEO description длиной 80-200 символов.",
                   page_id=page_id, chars=len(seo_description))
        if not sections:
            _issue(issues, "must_fix", "page_structure_unavailable",
                   "Прочитать штатные блоки страницы и повторить аудит.", page_id=page_id)
            continue
        if sections[0].get("role") != "header":
            _issue(issues, "must_fix", "page_header_missing",
                   "Добавить штатную шапку с навигацией.", page_id=page_id)
        else:
            header_types.append(str(sections[0].get("type_id") or ""))
        footer_types.append(str(sections[-1].get("type_id") or ""))
        roles = {str(section.get("role") or "") for section in sections}
        if not roles.intersection({"cta", "contact"}):
            _issue(issues, "must_fix", "page_conversion_exit_missing",
                   "Завершить страницу штатным CTA или контактным блоком.", page_id=page_id)
        if not composition.get("meets_7_of_10"):
            _issue(issues, "improve", "page_composition_below_7",
                   "Довести смысловую композицию страницы минимум до 7/10.",
                   page_id=page_id, score=composition.get("score"))

    for slug, page_ids in slugs.items():
        if len(page_ids) > 1:
            _issue(issues, "must_fix", "page_slug_duplicate",
                   "Назначить каждой видимой странице уникальный URL.",
                   value=slug or "/", page_ids=page_ids)
    for value, page_ids in seo_titles.items():
        if len(page_ids) > 1:
            _issue(issues, "must_fix", "page_seo_title_duplicate",
                   "Сделать SEO title страниц уникальными.", value=value, page_ids=page_ids)
    if len(set(header_types)) > 1:
        _issue(issues, "improve", "project_header_type_inconsistent",
               "Использовать один штатный тип шапки на всех страницах.",
               values=dict(Counter(header_types)))
    if len(set(footer_types)) > 1:
        _issue(issues, "improve", "project_footer_type_inconsistent",
               "Использовать один штатный тип подвала на всех страницах.",
               values=dict(Counter(footer_types)))

    blockers = [item for item in issues if item["priority"] == "must_fix"]
    improvements = [item for item in issues if item["priority"] == "improve"]
    score = max(0.0, round(10 - 1.0 * len(blockers) - .25 * len(improvements), 1))
    return {
        "kind": "multipage_project", "pages": len(pages), "visible_pages": len(visible),
        "ready": not blockers and score >= 7, "score": score, "target": 7.0,
        "issues": issues, "blockers": blockers, "improvements": improvements,
        "metrics": {"unique_slugs": len(slugs), "unique_seo_titles": len(seo_titles),
                    "header_types": dict(Counter(header_types)),
                    "footer_types": dict(Counter(footer_types))},
    }


def audit_module_uniqueness(articles: list[dict[str, Any]], products: list[dict[str, Any]],
                            offers_by_product: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    def duplicates(entities: list[dict[str, Any]], field: str) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        for entity in entities:
            value = str(entity.get(field) or "").strip().strip("/").casefold()
            if value:
                values.setdefault(value, []).append(str(entity.get("id") or ""))
        return {value: ids for value, ids in values.items() if len(ids) > 1}

    checks = [
        (articles, "dir", "article_slug_duplicate"),
        (articles, "seo_title", "article_seo_title_duplicate"),
        (products, "dir", "product_slug_duplicate"),
        (products, "seo_title", "product_seo_title_duplicate"),
        (products, "vendor_code", "product_vendor_code_duplicate"),
    ]
    for entities, field, code in checks:
        for value, entity_ids in duplicates(entities, field).items():
            _issue(issues, "must_fix", code,
                   f"Сделать поле {field} уникальным во всем проекте.",
                   field=field, value=value, entity_ids=entity_ids)

    offer_codes: dict[str, list[dict[str, str]]] = {}
    for product_id, offers in offers_by_product.items():
        for offer in offers:
            code = str(offer.get("vendor_code") or "").strip().casefold()
            if code:
                offer_codes.setdefault(code, []).append({
                    "product_id": str(product_id), "offer_id": str(offer.get("id") or "")})
    for value, locations in offer_codes.items():
        if len(locations) > 1:
            _issue(issues, "must_fix", "product_offer_vendor_code_duplicate_global",
                   "Использовать уникальный артикул варианта во всем каталоге.",
                   value=value, locations=locations)

    blockers = [item for item in issues if item["priority"] == "must_fix"]
    return {"ready": not blockers, "issues": issues, "blockers": blockers,
            "metrics": {"articles": len(articles), "products": len(products),
                        "offers": sum(len(value) for value in offers_by_product.values())}}
