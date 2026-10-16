"""Deterministic native-first site plan derived from an installed TOBIZ template."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from . import claim_audit, composition, content, design_feedback


PHOTO_RULES = {
    "background": {"orientation": "wide", "ratio": "16:9 or wider", "safe_zone": "preserve the template text area"},
    "catalog_image": {"orientation": "consistent cards", "ratio": "1:1 or native slot ratio", "safe_zone": "center the object with equal scale"},
    "gallery_image": {"orientation": "consistent series", "ratio": "native gallery ratio", "safe_zone": "keep the main subject away from crop edges"},
    "logo": {"orientation": "horizontal or native logo slot", "ratio": "preserve artwork", "safe_zone": "transparent padding around the mark"},
    "content_image": {"orientation": "match native slot", "ratio": "preserve source proportions", "safe_zone": "keep the subject inside the visible crop"},
}

SHOT_ROLE_BY_SECTION = {
    "hero": "hero", "process": "process_or_game", "contact": "location",
    "proof": "people_or_event", "expert": "people", "benefits": "details",
    "offer": "interior", "catalog": "details", "programs": "process_or_game",
}

CRITICAL_ARCHITECTURE = {
    "lead_generation": ("hero", "offer", "cta", "contact"),
    "education": ("hero", "programs", "expert", "cta", "contact"),
    "ecommerce": ("hero", "catalog", "delivery", "cta", "contact"),
}

TRUST_ARCHITECTURE = {
    "lead_generation": (("process", "expert", "proof", "contact"), 3),
    "education": (("process", "expert", "proof", "contact"), 3),
    "ecommerce": (("delivery", "proof", "contact"), 2),
}


def safe_system_title(value: str, fallback: str = "Новая страница") -> str:
    """Return a TOBIZ panel-safe title without changing visible or SEO copy."""
    title = str(value or "").replace("«", "").replace("»", "").replace('"', "")
    title = re.sub(r"[^0-9A-Za-zА-Яа-яЁё _.,()\-]", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .,-")
    return title[:120] or fallback


def _visible_media_paths(group: dict[str, Any]) -> list[str]:
    paths = list(group.get("paths") or [])
    if group.get("role") != "catalog_image" or not paths:
        return paths
    primary_field = str(group.get("path_pattern") or paths[0]).rsplit("/", 1)[-1]
    visible = [path for path in paths if str(path).rsplit("/", 1)[-1] == primary_field]
    return visible or paths[:1]

EVIDENCE_REQUIREMENTS = {
    "lead_generation": (
        ("offer", ("offer", "service", "services"), "Что именно получает клиент"),
        ("geography", ("geography", "city", "region"), "Где оказывается услуга"),
        ("process", ("process", "steps"), "Как проходит работа"),
        ("expertise", ("experience", "expertise", "company"), "Кто выполняет работу и на чем основана компетенция"),
        ("contact", ("phone", "email", "address", "contacts"), "Как связаться"),
    ),
    "education": (
        ("program", ("program", "programs", "curriculum"), "Что входит в обучение"),
        ("format", ("format", "formats", "schedule"), "Формат и организация занятий"),
        ("expert", ("teacher", "expert", "experience"), "Кто преподает и его подтвержденный опыт"),
        ("result", ("result", "outcomes", "method"), "Какой проверяемый результат ожидается"),
        ("contact", ("phone", "email", "contacts"), "Как записаться"),
    ),
    "ecommerce": (
        ("catalog", ("products", "catalog", "assortment"), "Какие товары продаются"),
        ("price", ("price", "prices", "pricing"), "Реальные цены или правило их расчета"),
        ("delivery", ("delivery", "pickup", "shipping"), "Условия доставки и получения"),
        ("payment", ("payment", "payments"), "Способы оплаты"),
        ("contact", ("phone", "email", "contacts"), "Как задать вопрос"),
    ),
}

EVIDENCE_QUESTIONS = {
    "offer": "Что именно получает клиент: услуга, состав результата и ключевые ограничения?",
    "geography": "В каком городе или регионе оказывается услуга?",
    "process": "Как проходит работа по шагам от заявки до результата?",
    "expertise": "Кто выполняет работу и какими подтвержденными фактами доказана компетенция?",
    "contact": "Какие телефон, email или другой способ связи можно публиковать?",
    "program": "Что конкретно входит в программу обучения?",
    "format": "В каком формате проходят занятия, по какому графику и для кого?",
    "expert": "Кто преподает и какой подтвержденный опыт можно указать?",
    "result": "Какой конкретный и проверяемый результат получает ученик?",
    "catalog": "Какие категории и товары должны быть представлены в каталоге?",
    "price": "Какие реальные цены или правила расчета стоимости можно указать?",
    "delivery": "Каковы условия доставки, самовывоза и сроки получения?",
    "payment": "Какие способы и условия оплаты доступны покупателю?",
}

PLACEHOLDER_FACT_TERMS = (
    "уточнить", "неизвестно", "нет данных", "пока нет", "придумай", "примерно",
    "клиент исправит", "клиент заменит", "заполнить позже", "будет позже", "tbd",
    "todo", "placeholder", "lorem ipsum", "example.com", "+7 800 333 22 33",
)

SLOT_INSTRUCTIONS = {
    "section_title": "Коротко назвать смысл секции, без рекламной абстракции.",
    "card_title": "Одна конкретная мысль; соседние карточки должны иметь сопоставимую длину.",
    "subtitle": "Раскрыть заголовок одним проверяемым обещанием или пояснением.",
    "body": "Использовать только факты из брифа; добавить детали процесса, состава или условий.",
    "button": "Назвать следующее действие пользователя, а не использовать нейтральное «Подробнее» без причины.",
    "link": "Использовать штатный якорь, форму, карточку товара или подтвержденный внешний адрес.",
    "text": "Сохранить функцию исходного поля и не превышать длину соседних элементов.",
}


def _fact_leaves(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _fact_leaves(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _fact_leaves(child)
    elif value is not None:
        text = str(value).strip()
        if text:
            yield text


def _usable_fact(value: Any) -> bool:
    for text in _fact_leaves(value):
        normalized = re.sub(r"\s+", " ", text.lower().replace("ё", "е"))
        if not any(term in normalized for term in PLACEHOLDER_FACT_TERMS):
            return True
    return False


def _fact_status(brief: dict[str, Any], aliases: tuple[str, ...]) -> tuple[bool, list[str]]:
    facts = brief.get("facts") if isinstance(brief.get("facts"), dict) else {}
    unresolved = []
    for key in aliases:
        value = brief.get(key, facts.get(key))
        if _usable_fact(value):
            return True, unresolved
        if list(_fact_leaves(value)):
            unresolved.append(key)
    return False, unresolved


def _has_fact(brief: dict[str, Any], aliases: tuple[str, ...]) -> bool:
    return _fact_status(brief, aliases)[0]


def brief_readiness(brief: dict[str, Any], goal: str | None = None) -> dict[str, Any]:
    """Return the smallest factual question set required for a trustworthy quality build."""
    if not isinstance(brief, dict):
        raise ValueError("brief must be an object")
    resolved_goal = goal or infer_goal(brief)
    if resolved_goal not in EVIDENCE_REQUIREMENTS:
        raise ValueError(f"Unknown site goal: {resolved_goal}")
    missing = []
    confirmed = []
    for code, aliases, label in EVIDENCE_REQUIREMENTS[resolved_goal]:
        available, unresolved = _fact_status(brief, aliases)
        if available:
            confirmed.append(code)
            continue
        missing.append({
            "code": code,
            "label": label,
            "accepted_fields": list(aliases),
            "question": EVIDENCE_QUESTIONS[code],
            **({"unresolved_fields": unresolved} if unresolved else {}),
        })
    prototype = brief.get("allow_placeholders") is True
    optional = []
    if not _has_fact(brief, ("audience", "target_audience", "clients")):
        optional.append({
            "code": "audience",
            "question": "Кто основной клиент и в какой ситуации он ищет это предложение?",
        })
    if not _has_fact(brief, ("primary_cta", "cta", "action")):
        optional.append({
            "code": "primary_cta",
            "question": "Какое одно основное действие должен совершить посетитель сайта?",
        })
    return {
        "goal": resolved_goal,
        "mode": "prototype" if prototype else "quality",
        "ready_for_quality_build": not missing,
        "confirmed_fields": confirmed,
        "missing_required": missing,
        "questions": [item["question"] for item in missing],
        "optional_questions": optional,
        "can_continue_with_placeholders": prototype,
        "rule": ("Не придумывать отсутствующие факты. Для чернового прототипа явно передать "
                 "allow_placeholders=true; такой прототип не готов к публикации."),
    }


def compile_content_brief(brief: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Turn a site plan into evidence-bound instructions for every native text slot."""
    goal = str(plan.get("goal") or infer_goal(brief))
    readiness = brief_readiness(brief, goal)
    missing = readiness["missing_required"]
    slots = []
    for section in plan.get("sections") or []:
        for slot in section.get("text_slots") or []:
            role = str(slot.get("role") or "text")
            slots.append({
                "block_index": section.get("position"),
                "section_role": section.get("role"),
                "path": slot.get("path"),
                "field_role": role,
                "max_chars": slot.get("max_chars"),
                "instruction": SLOT_INSTRUCTIONS.get(role, SLOT_INSTRUCTIONS["text"]),
                "evidence_policy": "Use only supplied facts; mark unknown data as required instead of inventing it.",
            })
    return {
        "plan_id": plan.get("plan_id"), "goal": goal,
        "ready_for_copywriting": not missing, "missing_evidence": missing, "slots": slots,
        "questions": readiness["questions"],
        "prohibited_inventions": [
            "prices and discounts", "statistics and quantities", "experience and credentials",
            "customer names and testimonials", "guarantees and deadlines", "addresses and contacts",
        ],
        "rules": [
            "Preserve the native slot and section structure.",
            "Keep neighboring card titles and descriptions visually balanced.",
            "Use a concrete contextual CTA and the native TOBIZ action.",
            "Leave an explicit content gap when evidence is missing; never fill it with a fabricated claim.",
        ],
    }


def infer_goal(brief: dict[str, Any]) -> str:
    text = " ".join(str(value) for value in brief.values()).lower().replace("ё", "е")
    if any(term in text for term in ("курс", "обуч", "школ", "репетитор", "образован")):
        return "education"
    if any(term in text for term in ("магазин", "товар", "каталог", "продаж", "доставк")):
        return "ecommerce"
    return "lead_generation"


def architecture_readiness(story: dict[str, Any], goal: str) -> dict[str, Any]:
    """Judge whether a locked native structure can support a complete, trustworthy page."""
    if goal not in CRITICAL_ARCHITECTURE:
        raise ValueError(f"Unknown site goal: {goal}")
    present = set(story.get("present_roles") or [])
    critical = list(CRITICAL_ARCHITECTURE[goal])
    trust_roles, trust_minimum = TRUST_ARCHITECTURE[goal]
    missing_critical = [role for role in critical if role not in present]
    trust_present = [role for role in trust_roles if role in present]
    missing_trust = [role for role in trust_roles if role not in present]
    score = float(story.get("score") or 0)
    blockers = []
    if missing_critical:
        blockers.append({
            "code": "critical_sections_missing",
            "roles": missing_critical,
            "action": "Выбрать другой проверенный шаблон с нужными штатными секциями.",
        })
    if len(trust_present) < trust_minimum:
        blockers.append({
            "code": "trust_layers_missing",
            "present": trust_present,
            "missing": missing_trust,
            "required_count": trust_minimum,
            "action": "Выбрать шаблон, где доверие раскрывается процессом, экспертом и доказательствами.",
        })
    if score < 7:
        blockers.append({
            "code": "composition_below_quality_target",
            "score": score,
            "target": 7.0,
            "action": "Использовать структурно более полный шаблон без добавления самописных секций.",
        })
    return {
        "goal": goal,
        "ready": not blockers,
        "score": score,
        "target": 7.0,
        "present_roles": sorted(present),
        "missing_critical_roles": missing_critical,
        "trust": {
            "present": trust_present,
            "missing": missing_trust,
            "required_count": trust_minimum,
            "sufficient": len(trust_present) >= trust_minimum,
        },
        "blockers": blockers,
        "rule": "Если структура не готова, выбрать другой штатный шаблон, а не достраивать ее кодом.",
    }


def _form_field_role(item: dict[str, Any]) -> str:
    field_type = str(item.get("type") or "").lower()
    text = " ".join(str(item.get(key) or "") for key in (
        "type", "title", "placeholder", "name")).lower().replace("ё", "е")
    if field_type in {"btn", "button", "submit"}:
        return "button"
    if field_type in {"phone", "tel"} or re.search(r"телефон|phone|\btel\b", text):
        return "phone"
    if field_type == "email" or re.search(r"e-?mail|почт", text):
        return "email"
    if field_type == "date" or re.search(r"дата|date", text):
        return "date"
    if re.search(r"гост|участник|человек", text):
        return "guests"
    if field_type in {"text", "name"} and re.search(r"имя|фио|name", text):
        return "name"
    return field_type or "unknown"


def _requested_form_fields(brief: dict[str, Any]) -> list[str]:
    supplied = brief.get("form_fields")
    if not isinstance(supplied, (list, tuple)) or not supplied:
        return ["name", "phone"]
    aliases = {
        "имя": "name", "фио": "name", "name": "name",
        "телефон": "phone", "phone": "phone", "tel": "phone",
        "почта": "email", "email": "email", "e-mail": "email",
        "дата": "date", "date": "date",
        "гости": "guests", "количество гостей": "guests", "guests": "guests",
    }
    normalized = []
    for value in supplied:
        key = re.sub(r"\s+", " ", str(value).strip().lower().replace("ё", "е"))
        role = aliases.get(key, key)
        if role and role not in normalized:
            normalized.append(role)
    return normalized


def conversion_readiness(draft, brief: dict[str, Any]) -> dict[str, Any]:
    """Validate native lead forms against the requested conversion contract."""
    required = _requested_form_fields(brief)
    forms = []
    for position, block_id in enumerate(draft.order):
        block = draft.blocks[block_id]
        if block.deleted:
            continue
        for key, value in block.values.items():
            if not re.fullmatch(r"form\d+", str(key)) or not isinstance(value, list) or not value:
                continue
            roles = [_form_field_role(item) for item in value if isinstance(item, dict)]
            missing = [role for role in required if role not in roles]
            name_index = roles.index("name") if "name" in roles else -1
            phone_index = roles.index("phone") if "phone" in roles else -1
            forms.append({
                "block_index": position,
                "block_id": str(block_id),
                "form_key": str(key),
                "fields": roles,
                "missing_required_fields": missing,
                "has_button": "button" in roles,
                "name_before_phone": (name_index >= 0 and phone_index >= 0
                                      and name_index < phone_index),
                "matches_contract": (not missing and "button" in roles
                                     and ("phone" not in required or name_index < phone_index)),
            })
    matching = [item for item in forms if item["matches_contract"]]
    blockers = []
    if not forms:
        blockers.append({
            "code": "native_form_missing",
            "action": "Выбрать шаблон со штатной формой TOBIZ.",
        })
    elif not matching:
        blockers.append({
            "code": "form_contract_not_covered",
            "required_fields": required,
            "forms": forms,
            "action": "Выбрать штатную форму со всеми нужными полями и кнопкой отправки.",
        })
    invalid_lead_forms = [item for item in forms
                          if "phone" in item["fields"] and not item["name_before_phone"]]
    if invalid_lead_forms:
        blockers.append({
            "code": "lead_form_name_order_invalid",
            "forms": [{"block_id": item["block_id"], "form_key": item["form_key"]}
                      for item in invalid_lead_forms],
            "action": "Поставить поле «Имя» перед «Телефоном» штатной настройкой формы.",
        })
    return {
        "ready": not blockers,
        "required_fields": required,
        "forms": forms,
        "matching_forms": len(matching),
        "blockers": blockers,
        "rule": "Использовать штатную форму; поле «Имя» идет перед «Телефоном».",
    }


def build(brief: dict[str, Any], selection: dict[str, Any], selected: dict[str, Any],
          blueprint: dict[str, Any], draft, goal: str | None = None) -> dict[str, Any]:
    goal = goal or infer_goal(brief)
    story = composition.analyze(draft, goal)
    slots_by_block: dict[int, list[dict[str, Any]]] = {}
    for slot in (blueprint.get("recipe") or {}).get("slots") or []:
        slots_by_block.setdefault(int(slot["block_index"]), []).append({
            "path": slot["path"], "role": slot.get("role"),
            **({"max_chars": slot["recommended_max_chars"]}
               if slot.get("recommended_max_chars") else {}),
        })
    photos = []
    for item in blueprint.get("photo_slots") or []:
        role = item.get("role") or "content_image"
        block_index = int(item.get("block_index") or 0)
        section_role = next((section["role"] for section in story["sections"]
                             if int(section["position"]) == block_index), "content")
        shot_role = SHOT_ROLE_BY_SECTION.get(
            section_role, "details" if role == "gallery_image" else "interior")
        photos.append({**item, **PHOTO_RULES.get(role, PHOTO_RULES["content_image"]),
                       "section_role": section_role, "shot_role": shot_role,
                       "brief": (f"Prepare a realistic {shot_role} photo for the {section_role} section; "
                                 "do not use generic stock-like imagery.")})
    sections = []
    for section in story["sections"]:
        index = int(section["position"])
        sections.append({
            "position": index, "type_id": section["type_id"], "role": section["role"],
            "objective": section["label"], "text_slots": slots_by_block.get(index, []),
            "cta_required": section["role"] in {"hero", "offer", "catalog", "programs", "cta"},
        })
    identity = {
        "brief": brief, "template_id": selected.get("id"),
        "source_project_id": str(selected["project_id"]),
        "source_page_id": str(selected["page_id"]),
        "types": (blueprint.get("recipe") or {}).get("types") or [], "goal": goal,
    }
    plan_id = hashlib.sha256(json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    plan = {
        "plan_id": plan_id, "goal": goal, "brief": brief,
        "template": selected, "alternatives": selection.get("alternatives", [])[:2],
        "visual_references": selection.get("visual_references", []),
        "structure_locked": True, "sections": sections,
        "recipe": blueprint.get("recipe"), "photo_requirements": photos,
        "design_system": {
            "visual_system": selected.get("visual_system"),
            "palette": "preserve template palette unless the brief explicitly requires brand colors",
            "typography": "preserve template font scale and alignment",
            "cta": "one primary style; align buttons with the surrounding content",
            "flex_limit": .3,
        },
        "anti_regression": design_feedback.regression_profile(
            str(selected.get("id") or ""), selection.get("feedback_lessons") or {}),
        "acceptance": [
            "all meaningful recipe slots replaced", "no source-theme terms remain",
            "all photo requirements reviewed on desktop, tablet and mobile",
            "native reference structure preserved", "editor roundtrip is safe",
            "tobiz_release_design_gate returns ready",
        ],
        "rule": "Copy the installed native structure; replace content and media; add no custom code.",
    }
    plan["content_brief"] = compile_content_brief(brief, plan)
    plan["brief_readiness"] = brief_readiness(brief, goal)
    plan["architecture_readiness"] = architecture_readiness(story, goal)
    plan["conversion_readiness"] = conversion_readiness(draft, brief)
    return plan


def compare(plan: dict[str, Any], target_draft, target_composition: dict[str, Any]) -> dict[str, Any]:
    expected_types = [str(item["type_id"]) for item in plan.get("sections") or []]
    target_types = [str(target_draft.blocks[bid].type_id) for bid in target_draft.order
                    if not target_draft.blocks[bid].deleted]
    expected_roles = [item["role"] for item in plan.get("sections") or []]
    target_roles = [item["role"] for item in target_composition.get("sections") or []]
    issues = []
    if target_types != expected_types:
        issues.append({"priority": "must_fix", "code": "plan_structure_drift",
                       "action": "Восстановить исходную последовательность штатных блоков плана."})
    if target_roles != expected_roles:
        issues.append({"priority": "must_fix", "code": "plan_role_drift",
                       "action": "Вернуть назначение секций к утвержденному плану."})
    return {
        "plan_id": plan.get("plan_id"), "matches": not issues,
        "issues": issues, "expected_types": expected_types, "target_types": target_types,
        "expected_roles": expected_roles, "target_roles": target_roles,
    }


def validate_recipe(brief: dict[str, Any], plan: dict[str, Any], blueprint: dict[str, Any],
                    recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate proposed copy against native slots before creating a TOBIZ page."""
    coverage = content.recipe_coverage(blueprint, recipe)
    expected = {
        (slot.get("block_index"), slot.get("path")): slot
        for slot in (blueprint.get("recipe") or {}).get("slots") or []
    }
    issues = []
    lengths: dict[tuple[int, str], list[int]] = {}
    for slot in recipe.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        key = (slot.get("block_index"), slot.get("path"))
        spec = expected.get(key)
        if spec is None:
            issues.append({"priority": "must_fix", "code": "unknown_recipe_slot",
                           "block_index": key[0], "path": key[1],
                           "action": "Использовать только слот из blueprint выбранного шаблона."})
            continue
        value = str(slot.get("value") or "").strip()
        role = str(spec.get("role") or "text")
        limit = spec.get("recommended_max_chars")
        if limit and len(value) > int(limit):
            ratio = len(value) / int(limit)
            issues.append({
                "priority": "must_fix" if ratio > 1.5 else "improve",
                "code": "recipe_text_over_mobile_limit", "block_index": key[0], "path": key[1],
                "chars": len(value), "recommended_max_chars": int(limit),
                "action": "Сократить текст по смыслу и повторно проверить мобильную верстку.",
            })
        if role == "button" and value.lower().replace("ё", "е") in {
                "подробнее", "узнать больше", "нажмите", "перейти"}:
            issues.append({"priority": "improve", "code": "generic_recipe_cta",
                           "block_index": key[0], "path": key[1],
                           "action": "Назвать конкретное действие пользователя в контексте секции."})
        if role in {"card_title", "body"}:
            lengths.setdefault((int(key[0]), role), []).append(len(value))
    for (block_index, role), values in lengths.items():
        threshold = 35 if role == "card_title" else 110
        if len(values) > 1 and max(values) - min(values) > threshold:
            issues.append({"priority": "improve", "code": "unbalanced_card_copy",
                           "block_index": block_index, "field_role": role,
                           "min_chars": min(values), "max_chars": max(values),
                           "action": "Сбалансировать объем соседних карточек без добавления пустых фраз."})
    claims = claim_audit.analyze_recipe(recipe, brief)
    issues.extend(claims["issues"])
    if not coverage.get("valid_structure"):
        issues.append({"priority": "must_fix", "code": "recipe_structure_mismatch",
                       "action": "Вернуть последовательность типов выбранного шаблона."})
    if not coverage.get("complete"):
        issues.append({"priority": "must_fix", "code": "recipe_incomplete",
                       "action": "Заменить все meaningful-поля, отмеченные в missing и unchanged."})
    evidence = plan.get("content_brief") or {}
    evidence_coverage = validate_evidence_coverage(plan, recipe)
    draft_mode = brief.get("allow_placeholders") is True
    issues.extend({
        **item,
        "priority": "improve" if draft_mode else "must_fix",
    } for item in evidence_coverage["issues"])
    blockers = [item for item in issues if item.get("priority") == "must_fix"]
    return {
        "plan_id": plan.get("plan_id"), "ready_for_build": not blockers,
        "coverage": coverage, "claims": claims,
        "evidence_ready": bool(evidence.get("ready_for_copywriting")),
        "missing_evidence": evidence.get("missing_evidence") or [],
        "evidence_coverage": evidence_coverage,
        "issues": issues, "blockers": blockers,
    }


def validate_evidence_coverage(plan: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    """Ensure every confirmed brief fact is intentionally represented in native copy slots."""
    readiness = plan.get("brief_readiness") or {}
    required = list(readiness.get("confirmed_fields") or [])
    allowed = set(required)
    mapped: dict[str, list[dict[str, Any]]] = {code: [] for code in required}
    unknown = []
    weak = []
    brief = plan.get("brief") if isinstance(plan.get("brief"), dict) else {}
    facts = brief.get("facts") if isinstance(brief.get("facts"), dict) else {}
    goal = str(readiness.get("goal") or plan.get("goal") or infer_goal(brief))
    aliases_by_code = {
        code: aliases for code, aliases, _label in EVIDENCE_REQUIREMENTS.get(goal, ())}

    def tokens(value: Any) -> set[str]:
        ignored = {"для", "или", "это", "как", "при", "под", "над", "без", "все", "что"}
        return {
            token for text in _fact_leaves(value)
            for token in re.findall(r"[0-9A-Za-zА-Яа-яЁё]{3,}", text.lower().replace("ё", "е"))
            if token not in ignored
        }

    evidence_tokens = {}
    for code in required:
        values = [brief.get(alias, facts.get(alias)) for alias in aliases_by_code.get(code, ())]
        evidence_tokens[code] = tokens(values)

    def grounded(code: str, value: str) -> bool:
        expected = evidence_tokens.get(code, set())
        actual = tokens(value)
        if expected & actual:
            return True
        expected_stems = {token[:4] for token in expected if len(token) >= 5}
        actual_stems = {token[:4] for token in actual if len(token) >= 5}
        return bool(expected_stems & actual_stems)

    if ("contact" in mapped
            and (plan.get("conversion_readiness") or {}).get("ready") is True):
        mapped["contact"].append({"source": "native_conversion_form"})
    for slot in recipe.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        codes = slot.get("evidence_codes")
        if codes is None:
            continue
        if not isinstance(codes, list):
            unknown.append({
                "block_index": slot.get("block_index"), "path": slot.get("path"),
                "code": "invalid_evidence_codes",
            })
            continue
        for code in codes:
            normalized = str(code).strip()
            if normalized not in allowed:
                unknown.append({
                    "block_index": slot.get("block_index"), "path": slot.get("path"),
                    "code": normalized,
                })
                continue
            value = str(slot.get("value") or "").strip()
            if value and grounded(normalized, value):
                mapped[normalized].append({
                    "block_index": slot.get("block_index"), "path": slot.get("path")})
            elif value and normalized != "contact":
                weak.append({
                    "block_index": slot.get("block_index"), "path": slot.get("path"),
                    "evidence_code": normalized,
                })
    missing = [code for code in required if not mapped[code]]
    issues = []
    if missing:
        issues.append({
            "priority": "must_fix", "code": "confirmed_evidence_not_used",
            "evidence_codes": missing,
            "action": "Связать каждый подтвержденный факт с конкретным текстовым слотом.",
        })
    if unknown:
        issues.append({
            "priority": "must_fix", "code": "unknown_evidence_mapping",
            "items": unknown,
            "action": "Использовать только коды из brief_readiness.confirmed_fields.",
        })
    if weak:
        issues.append({
            "priority": "must_fix", "code": "evidence_mapping_not_grounded",
            "items": weak,
            "action": "Добавить в текст конкретный подтвержденный факт или убрать неверную связь.",
        })
    return {
        "ready": not issues,
        "required": required,
        "covered": [code for code in required if mapped[code]],
        "missing": missing,
        "mappings": mapped,
        "ungrounded_mappings": weak,
        "issues": issues,
    }


def validate_media_recipe(plan: dict[str, Any], blueprint: dict[str, Any],
                          media_recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate image assignments before a native template is copied."""
    requirements = {
        (item.get("block_index"), item.get("path_pattern")): item
        for item in plan.get("photo_requirements") or []
    }
    expected = {}
    for item in blueprint.get("photo_slots") or []:
        key = (item.get("block_index"), item.get("path_pattern"))
        spec = {**dict(item), **requirements.get(key, {})}
        paths = _visible_media_paths(spec)
        if paths != list(spec.get("paths") or []):
            spec["paths"] = paths
            spec["slots"] = len(paths)
        expected[(spec.get("block_index"), spec.get("path_pattern"))] = spec
    supplied = {
        (item.get("block_index"), item.get("path_pattern")): item
        for item in media_recipe.get("groups") or [] if isinstance(item, dict)
    } if isinstance(media_recipe, dict) else {}
    issues: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    filenames: dict[str, list[tuple[Any, Any]]] = {}
    for key, spec in expected.items():
        group = supplied.get(key)
        if group is None:
            issues.append({"priority": "must_fix", "code": "media_group_missing",
                           "block_index": key[0], "path_pattern": key[1],
                           "action": "Назначить изображения всем слотам этой группы."})
            continue
        assets = group.get("assets") if isinstance(group.get("assets"), list) else []
        paths = list(spec.get("paths") or [])
        if len(assets) != len(paths):
            issues.append({"priority": "must_fix", "code": "media_asset_count_mismatch",
                           "block_index": key[0], "path_pattern": key[1],
                           "required": len(paths), "supplied": len(assets),
                           "action": "Передать по одному изображению для каждого штатного фотослота."})
        ratios = []
        for index, asset in enumerate(assets[:len(paths)]):
            if not isinstance(asset, dict):
                issues.append({"priority": "must_fix", "code": "invalid_media_asset",
                               "block_index": key[0], "path": paths[index]})
                continue
            filename = str(asset.get("filename") or "").strip()
            width = asset.get("width")
            height = asset.get("height")
            if not re.fullmatch(r"[A-Za-z0-9_. -]+\.(?:png|jpg|jpeg|webp)", filename, re.I):
                issues.append({"priority": "must_fix", "code": "invalid_media_filename",
                               "block_index": key[0], "path": paths[index],
                               "action": "Использовать имя файла, возвращенное tobiz_upload_image."})
                continue
            if re.search(r"(?:null|placeholder|grey|gray|заглуш)", filename, re.I):
                issues.append({"priority": "must_fix", "code": "media_placeholder_used",
                               "block_index": key[0], "path": paths[index],
                               "action": "Заменить заглушку содержательным изображением перед публикацией."})
            if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
                issues.append({"priority": "must_fix", "code": "media_dimensions_missing",
                               "block_index": key[0], "path": paths[index],
                               "action": "Передать фактические width и height загруженного файла."})
            else:
                ratio = width / height
                ratios.append(ratio)
                role = spec.get("role") or "content_image"
                min_width = 1600 if role == "background" else 200 if role == "logo" else 800
                if width < min_width:
                    issues.append({"priority": "must_fix", "code": "media_resolution_too_low",
                                   "block_index": key[0], "path": paths[index],
                                   "width": width, "required_width": min_width,
                                   "action": "Загрузить изображение достаточного разрешения для штатного слота."})
                if role == "background" and ratio < 1.5:
                    issues.append({"priority": "must_fix", "code": "background_not_wide",
                                   "block_index": key[0], "path": paths[index],
                                   "ratio": round(ratio, 3),
                                   "action": "Использовать широкий кадр для фонового изображения."})
                if role == "background" and asset.get("safe_text_area") is not True:
                    issues.append({"priority": "must_fix", "code": "background_safe_area_unconfirmed",
                                   "block_index": key[0], "path": paths[index],
                                   "action": "Подтвердить свободную область под текст после проверки кадра."})
            subject = str(asset.get("subject") or "").strip()
            normalized_subject = subject.lower().replace("ё", "е")
            if (len(subject) < 8 or normalized_subject in {
                    "фото", "картинка", "изображение", "женщина", "мужчина", "человек"}):
                issues.append({"priority": "must_fix", "code": "media_subject_missing",
                               "block_index": key[0], "path": paths[index],
                               "action": "Описать конкретный сюжет кадра, а не общий тип изображения."})
            if asset.get("section_fit_confirmed") is not True:
                issues.append({"priority": "must_fix", "code": "media_section_fit_unconfirmed",
                               "block_index": key[0], "path": paths[index],
                               "section_role": spec.get("section_role"),
                               "shot_role": spec.get("shot_role"),
                               "action": "Визуально проверить кадр и подтвердить соответствие смыслу секции."})
            filenames.setdefault(filename.lower(), []).append(key)
            assignments.append({"block_index": key[0], "path": paths[index], "value": filename})
        if len(ratios) > 1 and max(ratios) - min(ratios) > .08:
            issues.append({"priority": "must_fix", "code": "media_group_ratios_inconsistent",
                           "block_index": key[0], "path_pattern": key[1],
                           "ratios": [round(value, 3) for value in ratios],
                           "action": "Подготовить изображения карточек в единой пропорции."})
    for key in sorted(set(supplied) - set(expected), key=str):
        issues.append({"priority": "must_fix", "code": "unknown_media_group",
                       "block_index": key[0], "path_pattern": key[1],
                       "action": "Использовать только фотогруппу из photo_requirements плана."})
    for filename, groups in filenames.items():
        if filename and len(set(groups)) > 1:
            issues.append({"priority": "must_fix", "code": "media_reused_across_sections",
                           "filename": filename, "uses": len(groups),
                           "action": "Не повторять один кадр в разных смысловых секциях без причины."})
    blockers = [item for item in issues if item.get("priority") == "must_fix"]
    return {"plan_id": plan.get("plan_id"), "ready_for_build": not blockers,
            "required_groups": len(expected), "assigned_slots": len(assignments),
            "assignments": assignments, "issues": issues, "blockers": blockers}


def merge_media_recipe(recipe: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    """Append validated image assignments to the positional native recipe."""
    merged = {**recipe, "slots": list(recipe.get("slots") or [])}
    merged["slots"].extend(validation.get("assignments") or [])
    return merged


def validate_build_package(brief: dict[str, Any], plan: dict[str, Any],
                           blueprint: dict[str, Any], recipe: dict[str, Any] | None,
                           media_recipe: dict[str, Any] | None,
                           seo: dict[str, Any] | None) -> dict[str, Any]:
    """Run every deterministic pre-copy gate in one call."""
    draft_mode = brief.get("allow_placeholders") is True
    content_result = validate_recipe(brief, plan, blueprint, recipe or {})
    media_result = (validate_media_recipe(plan, blueprint, media_recipe)
                    if media_recipe else None)
    issues = list(content_result.get("issues") or [])
    readiness = brief_readiness(brief, str(plan.get("goal") or "") or None)
    for item in readiness["missing_required"]:
        issues.append({
            "priority": "improve" if draft_mode else "must_fix",
            "code": "brief_evidence_missing",
            "evidence_code": item["code"],
            "question": item["question"],
            "action": "Получить подтвержденный факт от клиента или включить режим прототипа.",
        })
    evidence_coverage = content_result["evidence_coverage"]
    architecture = plan.get("architecture_readiness") or {}
    if architecture and not architecture.get("ready"):
        issues.append({
            "priority": "improve" if draft_mode else "must_fix",
            "code": "template_architecture_incomplete",
            "details": architecture.get("blockers") or [],
            "action": "Выбрать другой проверенный шаблон; не добавлять случайные или самописные блоки.",
        })
    conversion = plan.get("conversion_readiness") or {}
    if conversion and not conversion.get("ready"):
        issues.append({
            "priority": "improve" if draft_mode else "must_fix",
            "code": "conversion_path_incomplete",
            "details": conversion.get("blockers") or [],
            "action": "Выбрать шаблон с подходящей штатной формой до создания страницы.",
        })
    if blueprint.get("photo_slots") and media_result is None:
        issues.append({
            "priority": "improve" if draft_mode else "must_fix",
            "code": "media_recipe_missing",
            "action": "Заполнить и проверить media_recipe по photo_requirements.",
        })
    elif media_result:
        issues.extend(media_result.get("issues") or [])

    seo_values = seo if isinstance(seo, dict) else {}
    seo_checks = {
        "title": (30, 70), "seo_title": (30, 70), "seo_description": (100, 180),
    }
    if not seo_values:
        issues.append({
            "priority": "improve" if draft_mode else "must_fix", "code": "seo_package_missing",
            "action": "Передать title, dir, seo_title и seo_description до сборки.",
        })
    else:
        for field in ("title", "dir", "seo_title", "seo_description"):
            if not str(seo_values.get(field) or "").strip():
                issues.append({"priority": "must_fix", "code": "seo_required_field_missing",
                               "field": field, "action": f"Заполнить SEO-поле {field}."})
        slug = str(seo_values.get("dir") or "")
        if slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            issues.append({"priority": "must_fix", "code": "invalid_page_slug", "value": slug,
                           "action": "Использовать короткий URL из латиницы, цифр и дефисов без слешей."})
        for field, (minimum, maximum) in seo_checks.items():
            value = str(seo_values.get(field) or "").strip()
            if value and not minimum <= len(value) <= maximum:
                issues.append({"priority": "improve", "code": "seo_length_outside_guidance",
                               "field": field, "chars": len(value), "recommended": [minimum, maximum],
                               "action": "Скорректировать длину без повторов и переспама."})
        seo_claims = claim_audit.analyze_recipe({"slots": [
            {"block_index": "seo", "path": f"/{key}", "value": value}
            for key, value in seo_values.items() if isinstance(value, str)
        ]}, brief)
        issues.extend(seo_claims.get("issues") or [])

    for slot in (recipe or {}).get("slots") or []:
        if not isinstance(slot, dict) or not isinstance(slot.get("value"), str):
            continue
        value = slot["value"].strip()
        if re.match(r"(?i)^javascript:", value):
            issues.append({"priority": "must_fix", "code": "unsafe_recipe_link",
                           "block_index": slot.get("block_index"), "path": slot.get("path"),
                           "action": "Использовать штатный якорь, форму или безопасный URL."})
        if value == "#":
            issues.append({"priority": "must_fix", "code": "empty_recipe_anchor",
                           "block_index": slot.get("block_index"), "path": slot.get("path"),
                           "action": "Привязать ссылку к существующей секции или форме."})

    blockers = [item for item in issues if item.get("priority") == "must_fix"]
    return {
        "plan_id": plan.get("plan_id"), "mode": "prototype" if draft_mode else "quality",
        "ready_for_build": not blockers, "content": content_result, "media": media_result,
        "brief_readiness": readiness, "architecture_readiness": architecture,
        "conversion_readiness": conversion,
        "evidence_coverage": evidence_coverage,
        "seo": {"provided": bool(seo_values)},
        "issues": issues, "blockers": blockers,
        "next_action": ("build" if not blockers else "fix_blockers_before_creating_page"),
    }


def prepare_build_package(brief: dict[str, Any], plan: dict[str, Any],
                          blueprint: dict[str, Any]) -> dict[str, Any]:
    """Create a clean fill-in package without carrying source-template copy forward."""
    instructions = {
        (slot.get("block_index"), slot.get("path")): slot
        for slot in (plan.get("content_brief") or {}).get("slots") or []
    }
    recipe_slots = []
    for slot in (blueprint.get("recipe") or {}).get("slots") or []:
        key = (slot.get("block_index"), slot.get("path"))
        guidance = instructions.get(key, {})
        recipe_slots.append({
            "block_index": slot.get("block_index"), "path": slot.get("path"),
            "kind": slot.get("kind"), "role": slot.get("role"), "value": "",
            "evidence_codes": [],
            "instruction": guidance.get("instruction"),
            **({"recommended_max_chars": slot["recommended_max_chars"]}
               if slot.get("recommended_max_chars") else {}),
        })
    media_groups = []
    requirements = {
        (item.get("block_index"), item.get("path_pattern")): item
        for item in plan.get("photo_requirements") or []
    }
    for group in blueprint.get("photo_slots") or []:
        requirement = requirements.get((group.get("block_index"), group.get("path_pattern")), {})
        # Catalog blocks expose hidden image2/image3 fields even when cards show one image.
        paths = _visible_media_paths(group)
        assets = []
        for path in paths:
            asset = {"path": path, "filename": "", "width": 0, "height": 0,
                     "subject": "", "section_fit_confirmed": False}
            if group.get("role") == "background":
                asset["safe_text_area"] = False
            assets.append(asset)
        media_groups.append({
            "block_index": group.get("block_index"), "path_pattern": group.get("path_pattern"),
            "role": group.get("role"), "required_assets": len(assets),
            "orientation": requirement.get("orientation"), "ratio": requirement.get("ratio"),
            "safe_zone": requirement.get("safe_zone"), "brief": requirement.get("brief"),
            "section_role": requirement.get("section_role"),
            "shot_role": requirement.get("shot_role"),
            "assets": assets,
        })
    facts = brief.get("facts") if isinstance(brief.get("facts"), dict) else {}
    topic = str(brief.get("industry") or brief.get("offer") or facts.get("offer") or "").strip()
    return {
        "schema_version": 1, "package_id": f"{plan.get('plan_id')}:v1",
        "plan_id": plan.get("plan_id"), "brief": brief,
        "template": plan.get("template"), "mode": "prototype" if brief.get("allow_placeholders") is True else "quality",
        "gates": {
            "brief": plan.get("brief_readiness") or {},
            "architecture": plan.get("architecture_readiness") or {},
            "conversion": plan.get("conversion_readiness") or {},
        },
        "recipe": {"types": list((blueprint.get("recipe") or {}).get("types") or []),
                   "slots": recipe_slots},
        "media_recipe": {"groups": media_groups},
        "seo": {"title": topic, "dir": "", "seo_title": topic,
                "seo_description": "", "og_image": ""},
        "missing_evidence": (plan.get("content_brief") or {}).get("missing_evidence") or [],
        "workflow": [
            "Fill confirmed copy and SEO with tobiz_fill_package_content.",
            "Upload exact media slots with tobiz_fill_package_media.",
            "Use tobiz_site_package_status whenever work resumes or a blocker remains.",
            "Build once with tobiz_build_site_package only when ready_for_build is true.",
        ],
    }


def validate_package_envelope(package: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Reject stale or mixed packages before their editable payload is used."""
    issues = []
    expected_plan_id = str(plan.get("plan_id") or "")
    expected_package_id = f"{expected_plan_id}:v1"
    if package.get("schema_version") != 1:
        issues.append({"priority": "must_fix", "code": "unsupported_package_schema",
                       "expected": 1, "actual": package.get("schema_version"),
                       "action": "Повторно вызовите tobiz_prepare_site_package."})
    if str(package.get("plan_id") or "") != expected_plan_id:
        issues.append({"priority": "must_fix", "code": "package_plan_mismatch",
                       "expected": expected_plan_id, "actual": package.get("plan_id"),
                       "action": "Не смешивать пакет с другим брифом или шаблоном."})
    if str(package.get("package_id") or "") != expected_package_id:
        issues.append({"priority": "must_fix", "code": "package_identity_mismatch",
                       "expected": expected_package_id, "actual": package.get("package_id"),
                       "action": "Использовать неизмененный идентификатор подготовленного пакета."})
    expected_template = plan.get("template") or {}
    actual_template = package.get("template") if isinstance(package.get("template"), dict) else {}
    for field in ("project_id", "page_id"):
        if str(actual_template.get(field) or "") != str(expected_template.get(field) or ""):
            issues.append({"priority": "must_fix", "code": "package_template_mismatch",
                           "field": field, "expected": expected_template.get(field),
                           "actual": actual_template.get(field),
                           "action": "Повторно подготовить пакет для текущей библиотеки шаблонов."})
    blockers = [item for item in issues if item.get("priority") == "must_fix"]
    return {"valid": not blockers, "expected_package_id": expected_package_id,
            "issues": issues, "blockers": blockers}


def fill_package_media(package: dict[str, Any], uploaded: list[dict[str, Any]]) -> dict[str, Any]:
    """Place verified upload metadata into exact package media slots."""
    updated = json.loads(json.dumps(package, ensure_ascii=False))
    groups = {
        (item.get("block_index"), item.get("path_pattern")): item
        for item in (updated.get("media_recipe") or {}).get("groups") or []
        if isinstance(item, dict)
    }
    filled = []
    for item in uploaded:
        key = (item.get("block_index"), item.get("path_pattern"))
        group = groups.get(key)
        index = item.get("asset_index")
        if group is None:
            raise ValueError(f"Unknown media group: {key}")
        assets = group.get("assets") if isinstance(group.get("assets"), list) else []
        if not isinstance(index, int) or index < 0 or index >= len(assets):
            raise ValueError(f"Invalid asset_index for media group {key}: {index}")
        metadata = item.get("media_asset") if isinstance(item.get("media_asset"), dict) else {}
        if not metadata.get("filename"):
            raise ValueError(f"Missing uploaded filename for media group {key}")
        asset = {**assets[index], **metadata}
        if str(item.get("subject") or "").strip():
            asset["subject"] = str(item["subject"]).strip()
        if "safe_text_area" in item:
            asset["safe_text_area"] = item.get("safe_text_area") is True
        if "section_fit_confirmed" in item:
            asset["section_fit_confirmed"] = item.get("section_fit_confirmed") is True
        if str(item.get("visual_review_notes") or "").strip():
            asset["visual_review_notes"] = str(item["visual_review_notes"]).strip()
        assets[index] = asset
        filled.append({"block_index": key[0], "path_pattern": key[1],
                       "asset_index": index, "filename": metadata["filename"]})
    return {"package": updated, "filled": filled, "filled_count": len(filled)}


def fill_package_content(package: dict[str, Any], updates: list[dict[str, Any]],
                         seo: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fill exact copy and SEO slots without allowing package-structure drift."""
    updated = json.loads(json.dumps(package, ensure_ascii=False))
    slots = {
        (item.get("block_index"), item.get("path")): item
        for item in (updated.get("recipe") or {}).get("slots") or []
        if isinstance(item, dict)
    }
    filled = []
    warnings = []
    targets = set()
    for position, item in enumerate(updates):
        if not isinstance(item, dict):
            raise ValueError(f"Content update {position} must be an object")
        key = (item.get("block_index"), item.get("path"))
        if key in targets:
            raise ValueError(f"Duplicate content slot: {key}")
        targets.add(key)
        slot = slots.get(key)
        if slot is None:
            raise ValueError(f"Unknown content slot: {key}")
        value = item.get("value")
        if not isinstance(value, str):
            raise ValueError(f"Content value must be a string: {key}")
        slot["value"] = value.strip()
        if "evidence_codes" in item:
            codes = item.get("evidence_codes")
            if not isinstance(codes, list) or any(not str(code).strip() for code in codes):
                raise ValueError(f"evidence_codes must be a list of non-empty codes: {key}")
            slot["evidence_codes"] = list(dict.fromkeys(str(code).strip() for code in codes))
        maximum = slot.get("recommended_max_chars")
        if isinstance(maximum, int) and maximum > 0 and len(slot["value"]) > maximum:
            warnings.append({"code": "copy_exceeds_mobile_limit", "block_index": key[0],
                             "path": key[1], "chars": len(slot["value"]),
                             "recommended_max_chars": maximum})
        filled.append({"block_index": key[0], "path": key[1], "chars": len(slot["value"])})
    if seo is not None:
        if not isinstance(seo, dict):
            raise ValueError("SEO update must be an object")
        allowed = {"title", "dir", "seo_title", "seo_description", "og_image"}
        unknown = sorted(set(seo) - allowed)
        if unknown:
            raise ValueError(f"Unknown SEO fields: {', '.join(unknown)}")
        for key, value in seo.items():
            if not isinstance(value, str):
                raise ValueError(f"SEO value must be a string: {key}")
            updated.setdefault("seo", {})[key] = value.strip()
    return {"package": updated, "filled": filled, "filled_count": len(filled),
            "warnings": warnings, "seo_updated": sorted(seo or {})}


def package_progress(package: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic completion and the one next package action."""
    content_slots = [item for item in (package.get("recipe") or {}).get("slots") or []
                     if isinstance(item, dict)]
    missing_content = [{key: item.get(key) for key in
                        ("block_index", "path", "role", "instruction", "recommended_max_chars")
                        if key in item}
                       for item in content_slots if not str(item.get("value") or "").strip()]
    media_assets = []
    for group in (package.get("media_recipe") or {}).get("groups") or []:
        if not isinstance(group, dict):
            continue
        for index, asset in enumerate(group.get("assets") or []):
            if isinstance(asset, dict):
                media_assets.append((group, index, asset))
    missing_media = [{
        "block_index": group.get("block_index"),
        "path_pattern": group.get("path_pattern"),
        "asset_index": index,
        "path": asset.get("path"),
        "role": group.get("role"),
        "brief": group.get("brief"),
    } for group, index, asset in media_assets
        if not str(asset.get("filename") or "").strip()]
    seo = package.get("seo") if isinstance(package.get("seo"), dict) else {}
    required_seo = ("title", "dir", "seo_title", "seo_description")
    missing_seo = [field for field in required_seo if not str(seo.get(field) or "").strip()]
    total = len(content_slots) + len(media_assets) + len(required_seo)
    missing = len(missing_content) + len(missing_media) + len(missing_seo)
    completed = max(0, total - missing)
    blockers = list(preflight.get("blockers") or [])
    if missing_content or missing_seo:
        next_action = "tobiz_fill_package_content"
    elif missing_media:
        next_action = "tobiz_fill_package_media"
    elif blockers:
        next_action = "fix_preflight_blockers"
    else:
        next_action = "tobiz_build_site_package"
    blocker_codes = {}
    for item in blockers:
        code = str(item.get("code") or "unknown")
        blocker_codes[code] = blocker_codes.get(code, 0) + 1
    return {
        "ready_for_build": bool(preflight.get("ready_for_build")),
        "completion_percent": round(completed * 100 / total) if total else 100,
        "completed_units": completed, "total_units": total,
        "content": {"filled": len(content_slots) - len(missing_content),
                    "total": len(content_slots), "missing": missing_content},
        "media": {"filled": len(media_assets) - len(missing_media),
                  "total": len(media_assets), "missing": missing_media},
        "seo": {"filled": len(required_seo) - len(missing_seo),
                "total": len(required_seo), "missing": missing_seo},
        "blocker_count": len(blockers), "blocker_codes": blocker_codes,
        "next_action": next_action,
    }
