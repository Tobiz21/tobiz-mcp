"""Deterministic publication-readiness audits for TOBIZ articles and products."""

from __future__ import annotations

import re
from html import unescape
from typing import Any


PLACEHOLDERS = {
    "заголовок", "название", "описание", "текст", "товар", "новый товар",
    "новая статья", "lorem ipsum", "todo", "tbd", "placeholder",
}


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _placeholder(value: Any) -> bool:
    normalized = _plain(value).lower().replace("ё", "е")
    return normalized in PLACEHOLDERS or any(token in normalized for token in (
        "пример текста", "заполнить позже", "ваш текст", "example.com"))


def _issue(issues: list[dict[str, Any]], priority: str, code: str, action: str,
           **details: Any) -> None:
    issues.append({"priority": priority, "code": code, "action": action, **details})


def _seo(entity: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    seo_title = _plain(entity.get("seo_title"))
    seo_description = _plain(entity.get("seo_description"))
    slug = str(entity.get("dir") or "").strip().strip("/")
    if not slug or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        _issue(issues, "must_fix", "module_slug_invalid",
               "Задать короткий человекочитаемый URL латиницей через дефисы.", value=slug)
    if not 20 <= len(seo_title) <= 75:
        _issue(issues, "must_fix", "module_seo_title_length",
               "Подготовить содержательный SEO title длиной 20-75 символов.", chars=len(seo_title))
    if not 80 <= len(seo_description) <= 200:
        _issue(issues, "must_fix", "module_seo_description_length",
               "Подготовить SEO description длиной 80-200 символов.",
               chars=len(seo_description))


def _result(kind: str, entity: dict[str, Any], issues: list[dict[str, Any]],
            metrics: dict[str, Any]) -> dict[str, Any]:
    blockers = [item for item in issues if item["priority"] == "must_fix"]
    improvements = [item for item in issues if item["priority"] == "improve"]
    score = max(0.0, round(10 - 1.25 * len(blockers) - .35 * len(improvements), 1))
    return {
        "kind": kind, "id": str(entity.get("id") or ""),
        "ready_for_publication": not blockers and score >= 7,
        "score": score, "target": 7.0, "metrics": metrics,
        "issues": issues, "blockers": blockers, "improvements": improvements,
    }


def audit_article(article: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    title = _plain(article.get("title"))
    short = _plain(article.get("short_description"))
    html = str(article.get("description") or "")
    body = _plain(html)
    headings = len(re.findall(r"<h[2-3]\b", html, re.I))
    images = _list(article.get("images"))
    if len(title) < 12 or _placeholder(title):
        _issue(issues, "must_fix", "article_title_weak",
               "Написать конкретный заголовок статьи без служебной заглушки.", chars=len(title))
    if not 80 <= len(short) <= 400 or _placeholder(short):
        _issue(issues, "must_fix", "article_excerpt_weak",
               "Подготовить самостоятельный анонс статьи длиной 80-400 символов.", chars=len(short))
    if len(body) < 1500 or _placeholder(body):
        _issue(issues, "must_fix", "article_body_too_short",
               "Раскрыть тему статьи содержательным текстом не короче 1500 символов.", chars=len(body))
    if headings < 2:
        _issue(issues, "improve", "article_structure_flat",
               "Разделить материал минимум двумя смысловыми подзаголовками H2/H3.", headings=headings)
    if not images:
        _issue(issues, "must_fix", "article_image_missing",
               "Добавить хотя бы одно релевантное изображение в штатную галерею статьи.")
    if not _list(article.get("categories")):
        _issue(issues, "improve", "article_category_missing",
               "Назначить статье подходящую штатную категорию.")
    _seo(article, issues)
    return _result("article", article, issues, {
        "title_chars": len(title), "excerpt_chars": len(short), "body_chars": len(body),
        "headings": headings, "images": len(images),
        "categories": len(_list(article.get("categories"))),
        "iframes": len(re.findall(r"<iframe\b", html, re.I)),
    })


def audit_product(product: dict[str, Any], offers: list[dict[str, Any]] | None = None,
                  allow_price_on_request: bool = False) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    title = _plain(product.get("title"))
    short = _plain(product.get("short_description"))
    body = _plain(product.get("description"))
    images = _list(product.get("images"))
    categories = _list(product.get("categories"))
    variants = list(offers if offers is not None else _list(product.get("offers")))
    if len(title) < 5 or _placeholder(title):
        _issue(issues, "must_fix", "product_title_weak",
               "Указать конкретное название товара без служебной заглушки.", chars=len(title))
    if len(short) < 60 or _placeholder(short):
        _issue(issues, "must_fix", "product_excerpt_weak",
               "Кратко объяснить назначение и ключевое отличие товара.", chars=len(short))
    if len(body) < 300 or _placeholder(body):
        _issue(issues, "must_fix", "product_description_too_short",
               "Раскрыть характеристики, применение, комплектацию и условия покупки.", chars=len(body))
    try:
        price = float(product.get("price") or 0)
    except (TypeError, ValueError):
        price = 0.0
    if price <= 0 and not allow_price_on_request and not variants:
        _issue(issues, "must_fix", "product_price_missing",
               "Указать цену либо явно разрешить сценарий «по запросу».")
    if not images:
        _issue(issues, "must_fix", "product_image_missing",
               "Добавить хотя бы одно четкое изображение товара.")
    if not categories:
        _issue(issues, "must_fix", "product_category_missing",
               "Назначить товару штатную категорию каталога.")
    videos = [str(product.get(f"video{index}") or "").strip() for index in range(1, 4)]
    invalid_videos = [value for value in videos if value and not re.match(r"https?://", value, re.I)]
    if invalid_videos:
        _issue(issues, "must_fix", "product_video_url_invalid",
               "Использовать полные http(s)-ссылки в штатных полях video1-video3.",
               values=invalid_videos)
    seen_titles: set[str] = set()
    seen_codes: set[str] = set()
    for index, offer in enumerate(variants):
        offer_title = _plain(offer.get("title")).lower()
        vendor_code = _plain(offer.get("vendor_code")).lower()
        try:
            offer_price = float(offer.get("price") or 0)
        except (TypeError, ValueError):
            offer_price = 0.0
        if not offer_title:
            _issue(issues, "must_fix", "product_offer_title_missing",
                   "Назвать каждый вариант товара.", offer_index=index)
        elif offer_title in seen_titles:
            _issue(issues, "must_fix", "product_offer_title_duplicate",
                   "Сделать названия вариантов различимыми.", offer_index=index, value=offer_title)
        seen_titles.add(offer_title)
        if vendor_code and vendor_code in seen_codes:
            _issue(issues, "must_fix", "product_offer_vendor_code_duplicate",
                   "Использовать уникальный артикул для каждого варианта.",
                   offer_index=index, value=vendor_code)
        if vendor_code:
            seen_codes.add(vendor_code)
        if offer_price <= 0 and not allow_price_on_request:
            _issue(issues, "must_fix", "product_offer_price_missing",
                   "Указать цену каждого варианта либо явно разрешить сценарий «по запросу».",
                   offer_index=index)
    _seo(product, issues)
    return _result("product", product, issues, {
        "title_chars": len(title), "excerpt_chars": len(short), "description_chars": len(body),
        "images": len(images), "categories": len(categories), "offers": len(variants),
        "videos": len([value for value in videos if value]), "price": price,
    })
