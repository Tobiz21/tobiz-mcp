"""Extract and compare native TOBIZ design recipes."""

from __future__ import annotations

import re
from typing import Any

from . import composition


STYLE_KEY = re.compile(
    r"(?:^|_)(?:bg|background|color|font|align|width|height|padd|padding|margin|radius|"
    r"shadow|border|size|column|columns|cols|grid|dark|light|position|crop|flex_fix|"
    r"fix_txt_img|active_off|btn_align)(?:_|$)", re.I)


def _style_fields(value: Any, path: str = "") -> dict[str, Any]:
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if isinstance(child, (str, int, float, bool)) and STYLE_KEY.search(key):
                result[child_path] = child
            elif isinstance(child, (dict, list)):
                result.update(_style_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                result.update(_style_fields(child, f"{path}/{index}"))
    return result


def extract(draft, audit: dict[str, Any] | None = None, goal: str = "lead_generation") -> dict[str, Any]:
    story = composition.analyze(draft, goal)
    sections = []
    active = [draft.blocks[block_id] for block_id in draft.order if not draft.blocks[block_id].deleted]
    for index, block in enumerate(active):
        story_section = story["sections"][index]
        sections.append({
            "position": index, "block_id": str(block.block_id), "type_id": str(block.type_id),
            "role": story_section["role"], "style": _style_fields(block.values),
        })
    profiles = {name: data.get("design_profile") or {}
                for name, data in ((audit or {}).get("viewports") or {}).items()}
    flex = sum(section["type_id"] == "1600" for section in sections)
    return {
        "goal": goal, "sections": sections,
        "type_sequence": [section["type_id"] for section in sections],
        "role_sequence": [section["role"] for section in sections],
        "block_count": len(sections),
        "flex_share": round(flex / len(sections), 3) if sections else 0.0,
        "visual_profiles": profiles,
        "composition_score": story["score"],
    }


def _lcs(left: list[str], right: list[str]) -> int:
    row = [0] * (len(right) + 1)
    for a in left:
        previous = 0
        for index, b in enumerate(right, 1):
            current = row[index]
            row[index] = previous + 1 if a == b else max(row[index], row[index - 1])
            previous = current
    return row[-1]


def _sequence_score(left: list[str], right: list[str]) -> float:
    denominator = max(len(left), len(right), 1)
    return _lcs(left, right) / denominator


def _jaccard(left: list[Any], right: list[Any]) -> float:
    a, b = {str(item) for item in left}, {str(item) for item in right}
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _visual_score(reference: dict[str, Any], target: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    metrics, differences = [], []
    keys = ("containerWidths", "buttonColors", "buttonRadii", "headingAlignments", "fontFamilies")
    for viewport in sorted(set(reference) | set(target)):
        ref_profile, target_profile = reference.get(viewport, {}), target.get(viewport, {})
        for key in keys:
            score = _jaccard(ref_profile.get(key) or [], target_profile.get(key) or [])
            metrics.append(score)
            if score < .5:
                differences.append({
                    "viewport": viewport, "property": key,
                    "reference": ref_profile.get(key) or [], "target": target_profile.get(key) or [],
                })
    return (sum(metrics) / len(metrics) if metrics else 1.0), differences


def compare(reference: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    structure = _sequence_score(reference["type_sequence"], target["type_sequence"])
    roles = _sequence_score(reference["role_sequence"], target["role_sequence"])
    style_scores, block_differences = [], []
    for ref_section, target_section in zip(reference["sections"], target["sections"]):
        if ref_section["type_id"] != target_section["type_id"]:
            block_differences.append({
                "position": ref_section["position"], "code": "block_type_changed",
                "reference_block_id": ref_section["block_id"], "target_block_id": target_section["block_id"],
                "reference_type_id": ref_section["type_id"], "target_type_id": target_section["type_id"],
            })
            continue
        ref_style, target_style = ref_section["style"], target_section["style"]
        keys = set(ref_style) | set(target_style)
        equal = sum(ref_style.get(key) == target_style.get(key) for key in keys)
        score = equal / len(keys) if keys else 1.0
        style_scores.append(score)
        changed = [key for key in sorted(keys) if ref_style.get(key) != target_style.get(key)]
        if changed:
            block_differences.append({
                "position": ref_section["position"], "code": "native_style_changed",
                "reference_block_id": ref_section["block_id"], "target_block_id": target_section["block_id"],
                "type_id": ref_section["type_id"], "fields": changed[:20],
            })
    native_style = sum(style_scores) / len(style_scores) if style_scores else 0.0
    visual, visual_differences = _visual_score(
        reference.get("visual_profiles") or {}, target.get("visual_profiles") or {})
    overall = round((structure * .35 + roles * .2 + native_style * .25 + visual * .2) * 10, 1)
    issues = []
    if structure < .9:
        issues.append({"priority": "must_fix", "code": "reference_structure_drift",
                       "action": "Восстановить последовательность штатных типов блоков эталона."})
    if roles < .8:
        issues.append({"priority": "must_fix", "code": "reference_story_drift",
                       "action": "Вернуть смысловые роли секций к структуре эталона."})
    if native_style < .8:
        issues.append({"priority": "improve", "code": "reference_native_style_drift",
                       "action": "Вернуть измененные штатные настройки блоков по указанным полям."})
    if visual < .9:
        issues.append({"priority": "improve", "code": "reference_rendered_style_drift",
                       "action": "Сверить сетку, кнопки и типографику по desktop/mobile-профилю эталона."})
    if target["flex_share"] > .3 and reference["flex_share"] <= .3:
        issues.append({"priority": "improve", "code": "excess_flex_vs_reference",
                       "action": "Заменить лишние Flex-секции обычными штатными блоками эталона."})
    return {
        "score": overall, "target": 7.0,
        "meets_7_of_10": overall >= 7 and not any(item["priority"] == "must_fix" for item in issues),
        "fidelity": {"structure": round(structure, 3), "roles": round(roles, 3),
                     "native_style": round(native_style, 3), "rendered_visual": round(visual, 3)},
        "issues": issues, "block_differences": block_differences,
        "visual_differences": visual_differences,
        "reference": {"blocks": reference["block_count"], "flex_share": reference["flex_share"]},
        "target_page": {"blocks": target["block_count"], "flex_share": target["flex_share"]},
        "rule": "Preserve the native reference recipe; change content and media, not composition without evidence.",
    }
