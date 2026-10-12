"""Deterministic native-first site plan derived from an installed TOBIZ template."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import composition


PHOTO_RULES = {
    "background": {"orientation": "wide", "ratio": "16:9 or wider", "safe_zone": "preserve the template text area"},
    "catalog_image": {"orientation": "consistent cards", "ratio": "1:1 or native slot ratio", "safe_zone": "center the object with equal scale"},
    "gallery_image": {"orientation": "consistent series", "ratio": "native gallery ratio", "safe_zone": "keep the main subject away from crop edges"},
    "logo": {"orientation": "horizontal or native logo slot", "ratio": "preserve artwork", "safe_zone": "transparent padding around the mark"},
    "content_image": {"orientation": "match native slot", "ratio": "preserve source proportions", "safe_zone": "keep the subject inside the visible crop"},
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
    return {
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
