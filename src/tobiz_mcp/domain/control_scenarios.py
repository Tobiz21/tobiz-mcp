"""Deterministic release scenarios spanning the four supported TOBIZ workflows."""

from __future__ import annotations

from typing import Any

from . import composition, design_gate, module_quality, project_quality
from .draft import Draft, DraftBlock


def _landing() -> dict[str, Any]:
    texts = (
        "Создание сайтов для малого бизнеса в Чебоксарах",
        "Услуги и решения для запуска продаж в интернете: лендинги, многостраничные сайты и каталоги под задачи бизнеса",
        "Преимущества: понятная структура, убедительный контент, удобная мобильная версия и штатное редактирование в TOBIZ",
        "Этапы и процесс создания сайта: изучение задачи, подробный бриф, прототипирование, сборка штатных блоков и приемка",
        "О компании: команда специалистов с подтвержденным опытом проектирования, текстов, дизайна и запуска коммерческих сайтов",
        "Отзывы клиентов, выполненные проекты и измеримые результаты показывают качество работы и помогают принять решение",
        "Часто задаваемые вопросы и ответы объясняют сроки, состав работ, порядок согласования, оплату и дальнейшую поддержку",
        "Оставьте заявку на консультацию",
        "Контакты: телефон +7 (900) 000-00-00",
    )
    blocks = {str(index): DraftBlock(str(index), "100", {"title": text})
              for index, text in enumerate(texts, 1)}
    story = composition.analyze(Draft("control", "landing", blocks=blocks,
                                      order=list(blocks)), "lead_generation")
    rendered = {"quality_score": {"overall": 9, "dimensions": {
        "technical": 9, "visual": 9, "content": 9, "usability": 9}},
        "critical": [], "warnings": []}
    gate = design_gate.evaluate(
        rendered, story, {"score": 9, "meets_7_of_10": True, "issues": []},
        {"editor_safe": True}, claims={"ready": True, "issues": []},
        require_complete=True, visual_review={"approved": True, "notes": "control"})
    return {"passed": gate["release_ready"], "gate": gate, "composition": story}


def _multipage() -> dict[str, Any]:
    reports = []
    for page_id, slug, title in (
            ("1", "glavnaya", "Создание сайтов для бизнеса в Чебоксарах"),
            ("2", "uslugi", "Услуги разработки сайтов для компаний")):
        reports.append({
            "page_id": page_id, "title": title, "slug": slug, "visible": True,
            "page": {"page_dir": slug, "page_seo_title": title,
                     "page_seo_description": (
                         "Подробное описание страницы для поисковой выдачи, раскрывающее услугу, "
                         "ее пользу, формат работы и следующий шаг для потенциального клиента.")},
            "composition": {"score": 8, "meets_7_of_10": True, "sections": [
                {"role": "header", "type_id": "105"},
                {"role": "hero", "type_id": "101"},
                {"role": "contact", "type_id": "165"},
            ]},
        })
    result = project_quality.audit(reports)
    return {"passed": result["ready"], "audit": result}


def _article() -> dict[str, Any]:
    fields = {
        "title": "Как выбрать структуру сайта для услуг",
        "dir": "kak-vybrat-strukturu-sayta",
        "short_description": (
            "Разбираем, какие разделы помогают раскрыть услугу, сформировать доверие и привести "
            "посетителя к понятному целевому действию."),
        "description": "<h2>Задача страницы</h2><p>" + "Содержательный текст. " * 90 +
                       "</p><h2>Доверие и действие</h2><p>Практические рекомендации.</p>",
        "seo_title": "Как выбрать структуру сайта для услуг",
        "seo_description": (
            "Практическое руководство по структуре сайта услуг: первый экран, доказательства, "
            "описание процесса, ответы на вопросы и форма обращения."),
    }
    result = module_quality.preflight_article(fields, ["1"], image_count=1)
    return {"passed": result["ready_for_publication"], "audit": result}


def _catalog() -> dict[str, Any]:
    fields = {
        "title": "Комплект оборудования для проверки извещателей",
        "dir": "komplekt-proverki-izveshchateley", "price": 24900,
        "short_description": (
            "Готовый комплект оборудования для функциональной проверки пожарных извещателей "
            "на объектах разной высоты."),
        "description": "Комплектация, совместимость, применение и условия поставки. " * 8,
        "seo_title": "Комплект для проверки пожарных извещателей",
        "seo_description": (
            "Комплект оборудования для функциональной проверки пожарных извещателей: состав, "
            "характеристики, совместимость, цена и условия поставки."),
    }
    offers = [{"title": "Высота 6 м", "vendor_code": "KIT-6", "price": 24900},
              {"title": "Высота 9 м", "vendor_code": "KIT-9", "price": 32900}]
    result = module_quality.preflight_product(fields, ["1"], offers, image_count=2)
    return {"passed": result["ready_for_publication"], "audit": result}


def run() -> dict[str, Any]:
    scenarios = {"landing": _landing(), "multipage": _multipage(),
                 "seo_article_with_media": _article(), "product_catalog": _catalog()}
    failed = [name for name, result in scenarios.items() if not result["passed"]]
    return {"passed": not failed, "scenario_count": len(scenarios),
            "failed": failed, "scenarios": scenarios}
