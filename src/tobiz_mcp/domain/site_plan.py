"""Deterministic native-first site plan derived from an installed TOBIZ template."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from . import claim_audit, composition, content


PHOTO_RULES = {
    "background": {"orientation": "wide", "ratio": "16:9 or wider", "safe_zone": "preserve the template text area"},
    "catalog_image": {"orientation": "consistent cards", "ratio": "1:1 or native slot ratio", "safe_zone": "center the object with equal scale"},
    "gallery_image": {"orientation": "consistent series", "ratio": "native gallery ratio", "safe_zone": "keep the main subject away from crop edges"},
    "logo": {"orientation": "horizontal or native logo slot", "ratio": "preserve artwork", "safe_zone": "transparent padding around the mark"},
    "content_image": {"orientation": "match native slot", "ratio": "preserve source proportions", "safe_zone": "keep the subject inside the visible crop"},
}

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

SLOT_INSTRUCTIONS = {
    "section_title": "Коротко назвать смысл секции, без рекламной абстракции.",
    "card_title": "Одна конкретная мысль; соседние карточки должны иметь сопоставимую длину.",
    "subtitle": "Раскрыть заголовок одним проверяемым обещанием или пояснением.",
    "body": "Использовать только факты из брифа; добавить детали процесса, состава или условий.",
    "button": "Назвать следующее действие пользователя, а не использовать нейтральное «Подробнее» без причины.",
    "link": "Использовать штатный якорь, форму, карточку товара или подтвержденный внешний адрес.",
    "text": "Сохранить функцию исходного поля и не превышать длину соседних элементов.",
}


def _has_fact(brief: dict[str, Any], aliases: tuple[str, ...]) -> bool:
    facts = brief.get("facts") if isinstance(brief.get("facts"), dict) else {}
    for key in aliases:
        value = brief.get(key, facts.get(key))
        if isinstance(value, (list, tuple, set, dict)) and value:
            return True
        if value is not None and str(value).strip():
            return True
    return False


def compile_content_brief(brief: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Turn a site plan into evidence-bound instructions for every native text slot."""
    goal = str(plan.get("goal") or infer_goal(brief))
    missing = [
        {"code": code, "label": label, "accepted_fields": list(aliases)}
        for code, aliases, label in EVIDENCE_REQUIREMENTS[goal]
        if not _has_fact(brief, aliases)
    ]
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
        photos.append({**item, **PHOTO_RULES.get(role, PHOTO_RULES["content_image"]),
                       "brief": "Use a realistic, topic-specific photo; do not use generic stock-like imagery."})
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
        "acceptance": [
            "all meaningful recipe slots replaced", "no source-theme terms remain",
            "all photo requirements reviewed on desktop and mobile",
            "native reference structure preserved", "editor roundtrip is safe",
            "tobiz_release_design_gate returns ready",
        ],
        "rule": "Copy the installed native structure; replace content and media; add no custom code.",
    }
    plan["content_brief"] = compile_content_brief(brief, plan)
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
    blockers = [item for item in issues if item.get("priority") == "must_fix"]
    return {
        "plan_id": plan.get("plan_id"), "ready_for_build": not blockers,
        "coverage": coverage, "claims": claims,
        "evidence_ready": bool(evidence.get("ready_for_copywriting")),
        "missing_evidence": evidence.get("missing_evidence") or [],
        "issues": issues, "blockers": blockers,
    }


def validate_media_recipe(plan: dict[str, Any], blueprint: dict[str, Any],
                          media_recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate image assignments before a native template is copied."""
    expected = {
        (item.get("block_index"), item.get("path_pattern")): item
        for item in blueprint.get("photo_slots") or []
    }
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
            if not str(asset.get("subject") or "").strip():
                issues.append({"priority": "improve", "code": "media_subject_missing",
                               "block_index": key[0], "path": paths[index],
                               "action": "Кратко описать главный объект кадра для смысловой проверки."})
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
            issues.append({"priority": "improve", "code": "media_reused_across_sections",
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
        "seo": {"provided": bool(seo_values)}, "issues": issues, "blockers": blockers,
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
        assets = []
        for path in group.get("paths") or []:
            asset = {"path": path, "filename": "", "width": 0, "height": 0,
                     "subject": ""}
            if group.get("role") == "background":
                asset["safe_text_area"] = False
            assets.append(asset)
        media_groups.append({
            "block_index": group.get("block_index"), "path_pattern": group.get("path_pattern"),
            "role": group.get("role"), "required_assets": len(assets),
            "orientation": requirement.get("orientation"), "ratio": requirement.get("ratio"),
            "safe_zone": requirement.get("safe_zone"), "brief": requirement.get("brief"),
            "assets": assets,
        })
    facts = brief.get("facts") if isinstance(brief.get("facts"), dict) else {}
    topic = str(brief.get("industry") or brief.get("offer") or facts.get("offer") or "").strip()
    return {
        "schema_version": 1, "package_id": f"{plan.get('plan_id')}:v1",
        "plan_id": plan.get("plan_id"), "brief": brief,
        "template": plan.get("template"), "mode": "prototype" if brief.get("allow_placeholders") is True else "quality",
        "recipe": {"types": list((blueprint.get("recipe") or {}).get("types") or []),
                   "slots": recipe_slots},
        "media_recipe": {"groups": media_groups},
        "seo": {"title": topic, "dir": "", "seo_title": topic,
                "seo_description": "", "og_image": ""},
        "missing_evidence": (plan.get("content_brief") or {}).get("missing_evidence") or [],
        "workflow": [
            "Fill only confirmed values from the brief into recipe slots.",
            "Upload or prepare every media asset and fill its actual filename and dimensions.",
            "Complete SEO fields without unsupported claims.",
            "Run tobiz_preflight_site_build and fix blockers.",
            "Run tobiz_build_quality_page once with the validated package and plan_id.",
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
