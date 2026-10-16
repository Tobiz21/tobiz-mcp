"""Deterministic design passports and brief-to-template matching."""

from __future__ import annotations

import re
from typing import Any


INSTALLED = (
    {"id": "modular-homes", "title": "Модульные и каркасные дома", "project_id": "433135",
     "page_id": "1221163", "visual_system": "industrial_b2b", "site_kind": "service_catalog",
     "concepts": ["construction", "industrial", "service", "catalog"],
     "strengths": ["catalog", "process", "reviews", "gallery", "contacts"],
     "photo_dependency": "high", "content_density": "medium", "blocks": 14, "flex_share": 0.0},
    {"id": "jeans-store", "title": "Интернет-магазин джинсов", "project_id": "433136",
     "page_id": "1221168", "visual_system": "ecommerce", "site_kind": "online_store",
     "concepts": ["ecommerce", "fashion", "catalog"],
     "strengths": ["catalog", "products", "promotions", "delivery"],
     "photo_dependency": "high", "content_density": "medium", "blocks": 12, "flex_share": 0.0},
    {"id": "dog-trainer", "title": "Услуги кинолога", "project_id": "433137",
     "page_id": "1221173", "visual_system": "friendly_service", "site_kind": "expert_service",
     "concepts": ["expert", "service", "pet", "education"],
     "strengths": ["expert", "programs", "catalog", "consultation"],
     "photo_dependency": "medium", "content_density": "medium", "blocks": 10, "flex_share": 0.7},
    {"id": "pajamas-store", "title": "Интернет-магазин пижам", "project_id": "433138",
     "page_id": "1221174", "visual_system": "ecommerce", "site_kind": "online_store",
     "concepts": ["ecommerce", "fashion", "catalog", "consumer"],
     "strengths": ["catalog", "products", "gallery", "reviews", "contacts"],
     "photo_dependency": "high", "content_density": "medium", "blocks": 13, "flex_share": 0.0},
    {"id": "medical-booking", "title": "Запись к врачу", "project_id": "433139",
     "page_id": "1221179", "visual_system": "light_expert", "site_kind": "booking_service",
     "concepts": ["medical", "expert", "service", "booking"],
     "strengths": ["booking", "experts", "services", "contacts"],
     "photo_dependency": "medium", "content_density": "medium", "blocks": 10, "flex_share": 0.4},
    {"id": "cabinets", "title": "Тумбы и мебель", "project_id": "433140",
     "page_id": "1221191", "visual_system": "product_premium", "site_kind": "product_catalog",
     "concepts": ["furniture", "premium", "catalog", "craft"],
     "strengths": ["catalog", "process", "gallery", "conditions", "reviews", "contacts"],
     "photo_dependency": "high", "content_density": "long", "blocks": 20, "flex_share": 0.0},
    {"id": "foam-blocks", "title": "Пеноблоки и строительные материалы", "project_id": "433141",
     "page_id": "1221196", "visual_system": "industrial_b2b", "site_kind": "long_service",
     "concepts": ["construction", "industrial", "service", "catalog", "regional"],
     "strengths": ["catalog", "process", "gallery", "conditions", "reviews", "contacts", "seo"],
     "photo_dependency": "medium", "content_density": "long", "blocks": 19, "flex_share": 0.0},
    {"id": "land-plots", "title": "Земельные участки", "project_id": "433143",
     "page_id": "1221202", "visual_system": "emotional_place", "site_kind": "real_estate",
     "concepts": ["real_estate", "place", "catalog", "regional"],
     "strengths": ["catalog", "location", "gallery", "conditions", "reviews"],
     "photo_dependency": "high", "content_density": "medium", "blocks": 13, "flex_share": 0.0},
    {"id": "culinary", "title": "Кулинария и готовая еда", "project_id": "433144",
     "page_id": "1221206", "visual_system": "ecommerce", "site_kind": "local_catalog",
     "concepts": ["food", "ecommerce", "catalog", "local", "event"],
     "strengths": ["catalog", "gallery", "products", "reviews", "contacts"],
     "photo_dependency": "high", "content_density": "medium", "blocks": 12, "flex_share": 0.0},
)

REFERENCES = (
    ("yuhim", "https://yuhim.ru/", "industrial_b2b", ["industrial", "service", "b2b"]),
    ("421040", "https://421040.lp.tobiz.net/", "light_digital", ["digital", "expert"]),
    ("beloussov", "https://start.beloussov.ru/", "light_expert", ["expert", "education"]),
    ("toplivopro", "https://toplivopro.ru/", "dark_tech", ["technical", "product"]),
    ("405788", "https://405788.lp.tobiz.net/", "ecommerce", ["ecommerce", "catalog"]),
    ("381594", "https://381594.lp.tobiz.net/", "friendly_service", ["industrial", "service"]),
    ("380853", "https://380853.lp.tobiz.net/", "product_premium", ["furniture", "premium"]),
    ("380539", "https://380539.lp.tobiz.net/", "dark_premium", ["expert", "premium"]),
    ("377038", "https://377038.lp.tobiz.net/", "eco_minimal", ["agro", "food", "eco"]),
    ("greenwood-villa", "https://greenwood-villa.ru/", "emotional_place", ["tourism", "place"]),
    ("373389", "https://373389.lp.tobiz.net/", "industrial_b2b", ["logistics", "industrial"]),
    ("cherevatkin", "https://cherevatkin.ru/", "product_premium", ["food", "premium", "product"]),
    ("367091", "https://367091.lp.tobiz.net/", "industrial_b2b", ["industrial", "b2b"]),
    ("auto-up", "https://auto-up.ru/", "friendly_service", ["automotive", "local", "service"]),
    ("aktive-montage", "https://anapa.aktive-montage.ru/", "long_service", ["construction", "regional", "service"]),
    ("zona-auto", "https://zona-auto.ru/", "dark_tech", ["automotive", "premium"]),
    ("woodenbull", "https://woodenbull-vrn.ru/", "product_premium", ["furniture", "craft", "premium"]),
)

CONCEPT_TERMS = {
    "construction": ["строитель", "дом", "бурен", "скваж", "монтаж", "ремонт", "материал"],
    "industrial": ["производ", "оборудован", "завод", "инженер", "b2b", "подряд"],
    "service": ["услуг", "сервис", "работ", "консультац", "заказ"],
    "catalog": ["каталог", "ассортимент", "товар", "модел", "вариант"],
    "ecommerce": ["магазин", "купить", "доставк", "корзин", "товар"],
    "fashion": ["одежд", "джинс", "пижам", "мода"],
    "expert": ["эксперт", "специалист", "консульт", "обучен", "врач"],
    "medical": ["медицин", "клиник", "врач", "здоров"],
    "booking": ["запис", "брон", "расписан", "прием"],
    "pet": ["собак", "кинолог", "питом"],
    "furniture": ["мебел", "тумб", "интерьер", "дерев"],
    "premium": ["преми", "индивидуал", "авторск", "люкс"],
    "real_estate": ["недвиж", "участ", "квартир", "поселок", "земл"],
    "place": ["место", "локац", "отдых", "отель", "глэмп"],
    "regional": ["регион", "чуваш", "чебоксар", "город", "район"],
    "food": ["еда", "кулинар", "продукт", "ресторан", "ферм"],
    "local": ["локаль", "рядом", "город", "адрес"],
    "education": ["курс", "обучен", "школ", "программ"],
    "event": ["праздник", "квест", "мероприят", "вечерин", "день рожд"],
    "tourism": ["туризм", "отдых", "аренд", "глэмп", "отель"],
    "automotive": ["авто", "машин", "автомоб"],
    "technical": ["техничес", "оборудован", "систем", "инженер"],
    "product": ["продукт", "издел", "товар", "модель"],
    "b2b": ["b2b", "опт", "компани", "предприят"],
}

VISUAL_SYSTEMS = {item["visual_system"] for item in INSTALLED} | {item[2] for item in REFERENCES}


def custom_passport(*, template_id: str, title: str, project_id: str, page_id: str,
                    visual_system: str, site_kind: str, concepts_list: list[str],
                    strengths: list[str], photo_dependency: str,
                    content_density: str, draft: Any) -> dict[str, Any]:
    template_id = str(template_id).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", template_id):
        raise ValueError("template_id must contain 3-64 lowercase Latin letters, digits, _ or -")
    if visual_system not in VISUAL_SYSTEMS:
        raise ValueError("unsupported visual_system")
    if photo_dependency not in {"low", "medium", "high"}:
        raise ValueError("photo_dependency must be low, medium or high")
    if content_density not in {"short", "medium", "long"}:
        raise ValueError("content_density must be short, medium or long")
    clean_concepts = sorted({str(value).strip() for value in concepts_list if str(value).strip()})
    clean_strengths = sorted({str(value).strip() for value in strengths if str(value).strip()})
    if not clean_concepts or not clean_strengths:
        raise ValueError("concepts and strengths must not be empty")
    visible = [block for block in draft.blocks.values() if not block.deleted]
    flex = sum(str(block.type_id) == "1600" for block in visible)
    return {
        "id": template_id, "title": str(title).strip() or template_id,
        "project_id": str(project_id), "page_id": str(page_id),
        "visual_system": visual_system, "site_kind": str(site_kind).strip() or "custom",
        "concepts": clean_concepts, "strengths": clean_strengths,
        "photo_dependency": photo_dependency, "content_density": content_density,
        "blocks": len(visible), "flex_share": round(flex / max(len(visible), 1), 3),
        "source": "local_verified_page",
    }


def template_registration_gate(audit: dict[str, Any], composition: dict[str, Any],
                               roundtrip: dict[str, Any], *, visual_review_approved: bool,
                               visual_review_notes: str) -> dict[str, Any]:
    blockers = []
    if audit.get("critical"):
        blockers.append({"code": "template_render_failures", "items": audit["critical"]})
    if not roundtrip.get("editor_safe"):
        blockers.append({"code": "template_editor_unsafe"})
    if float(composition.get("score") or 0) < 7:
        blockers.append({"code": "template_composition_below_7",
                         "score": float(composition.get("score") or 0)})
    if not visual_review_approved or not str(visual_review_notes).strip():
        blockers.append({"code": "template_visual_review_missing",
                         "action": "Просмотрите desktop/tablet/mobile снимки и опишите результат."})
    return {
        "ready": not blockers,
        "blockers": blockers,
        "quality_score": (audit.get("quality_score") or {}).get("overall"),
        "composition_score": composition.get("score"),
        "editor_safe": bool(roundtrip.get("editor_safe")),
        "visual_review": {"approved": bool(visual_review_approved),
                          "notes": str(visual_review_notes).strip()},
    }


def _tokens(value: Any) -> set[str]:
    if isinstance(value, dict):
        value = " ".join(str(item) for item in value.values())
    elif isinstance(value, (list, tuple, set)):
        value = " ".join(str(item) for item in value)
    return set(re.findall(r"[a-zа-я0-9]+", str(value or "").lower().replace("ё", "е")))


def concepts(brief: dict[str, Any]) -> set[str]:
    raw = " ".join(str(value) for value in brief.values()).lower().replace("ё", "е")
    found = set()
    for concept, terms in CONCEPT_TERMS.items():
        if any(term in raw for term in terms):
            found.add(concept)
    return found


def library(installed: list[dict[str, Any]] | tuple | None = None) -> dict[str, Any]:
    return {
        "installed": [dict(item) for item in (installed or INSTALLED)],
        "references": [{"id": item[0], "url": item[1], "visual_system": item[2],
                        "concepts": item[3]} for item in REFERENCES],
        "rules": {"max_flex_share": 0.3, "one_primary_visual_system": True,
                  "native_blocks_first": True},
    }


def validate_passport(expected: dict[str, Any], draft: Any) -> dict[str, Any]:
    """Compare a live native page with the immutable facts stored in its passport."""
    visible = [block for block in draft.blocks.values() if not block.deleted]
    flex_count = sum(str(block.type_id) == "1600" for block in visible)
    actual = {
        "blocks": len(visible),
        "flex_share": round(flex_count / max(len(visible), 1), 3),
    }
    mismatches = []
    if actual["blocks"] != int(expected["blocks"]):
        mismatches.append({"field": "blocks", "expected": int(expected["blocks"]),
                           "actual": actual["blocks"]})
    if actual["flex_share"] != float(expected["flex_share"]):
        mismatches.append({"field": "flex_share", "expected": float(expected["flex_share"]),
                           "actual": actual["flex_share"]})
    return {"valid": not mismatches, "template_id": expected.get("id"),
            "expected": {"blocks": int(expected["blocks"]),
                         "flex_share": float(expected["flex_share"])},
            "actual": actual, "mismatches": mismatches}


def _rank(item: dict[str, Any], brief: dict[str, Any], brief_concepts: set[str]) -> dict[str, Any]:
    score, reasons, risks = 0, [], []
    overlap = sorted(brief_concepts & set(item["concepts"]))
    if overlap:
        score += len(overlap) * 5
        reasons.append("Совпадают задачи: " + ", ".join(overlap))
    wanted_system = str(brief.get("visual_system") or "").strip()
    if wanted_system and wanted_system == item["visual_system"]:
        score += 7
        reasons.append("Совпадает визуальная система")
    needs = _tokens(brief.get("needs") or brief.get("features"))
    strengths = set(item["strengths"])
    feature_overlap = sorted(needs & strengths)
    if feature_overlap:
        score += len(feature_overlap) * 3
        reasons.append("Есть нужные секции: " + ", ".join(feature_overlap))
    length = str(brief.get("page_length") or "")
    if length and length == item["content_density"]:
        score += 3
        reasons.append("Подходит плотность страницы")
    photo_quality = str(brief.get("photo_quality") or "unknown")
    if photo_quality in {"low", "poor", "none"} and item["photo_dependency"] == "high":
        score -= 4
        risks.append("Шаблон требует сильных предметных фотографий")
    prefer_native = brief.get("prefer_native", True)
    if prefer_native and item["flex_share"] > .3:
        score -= 8
        risks.append(f"Flex занимает {round(item['flex_share'] * 100)}% блоков")
    if not reasons:
        reasons.append("Резервная структурная основа")
    return {**item, "score": score, "reasons": reasons, "risks": risks}


def select(brief: dict[str, Any], top_k: int = 3,
           installed: list[dict[str, Any]] | tuple | None = None) -> dict[str, Any]:
    if not isinstance(brief, dict) or not any(str(value).strip() for value in brief.values()):
        raise ValueError("brief must contain at least one non-empty field")
    candidates = installed or INSTALLED
    top_k = max(1, min(int(top_k), len(candidates)))
    brief_concepts = concepts(brief)
    ranked = sorted((_rank(dict(item), brief, brief_concepts) for item in candidates),
                    key=lambda item: (-item["score"], item["flex_share"], -item["blocks"], item["id"]))
    reference_ranked = []
    for ref_id, url, system, ref_concepts in REFERENCES:
        score = len(brief_concepts & set(ref_concepts)) * 5
        if brief.get("visual_system") == system:
            score += 7
        reference_ranked.append({"id": ref_id, "url": url, "visual_system": system,
                                 "score": score, "concepts": ref_concepts})
    reference_ranked.sort(key=lambda item: (-item["score"], item["id"]))
    return {"brief_concepts": sorted(brief_concepts), "recommended": ranked[0],
            "alternatives": ranked[1:top_k], "visual_references": reference_ranked[:2],
            "rule": "Copy the installed structure; replace content and media; keep native blocks."}


def select_native(brief: dict[str, Any], max_flex_share: float = 0.3,
                  installed: list[dict[str, Any]] | tuple | None = None
                  ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the full ranking and its best native-first candidate."""
    candidates = installed or INSTALLED
    selection = select(brief, top_k=len(candidates), installed=candidates)
    ranked = [selection["recommended"], *selection["alternatives"]]
    eligible = [item for item in ranked
                if float(item.get("flex_share") or 0) <= max_flex_share]
    if not eligible:
        raise ValueError(f"no verified template with Flex share <= {max_flex_share}")
    return selection, eligible[0]
