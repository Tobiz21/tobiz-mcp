"""Conservative dependency checks before reusing a native TOBIZ block."""

from __future__ import annotations

import re
from typing import Any


ANCHOR_KEYS = {"anchor", "block_anchor", "section_anchor"}
PROJECT_BOUND = re.compile(r"(?:product|item|article|category|popup|quiz|calc).*id", re.I)
MEDIA_KEYS = re.compile(r"(?:image|img|background|video|poster|logo|icon)", re.I)


def _walk(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            yield child_path, str(key), child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}/{index}")


def block_dependencies(values: dict[str, Any]) -> dict[str, Any]:
    anchors, references, media, bound = set(), set(), [], []
    for path, key, value in _walk(values):
        lowered = key.lower()
        text = str(value or "").strip()
        if lowered in ANCHOR_KEYS and text:
            anchors.add(text.lstrip("#"))
        if text.startswith("#") and len(text) > 1:
            references.add(text[1:])
        if text and MEDIA_KEYS.search(lowered):
            media.append({"path": path, "value": text})
        if text and PROJECT_BOUND.search(lowered):
            bound.append({"path": path, "key": key, "value": text})
    return {"anchors": sorted(anchors), "internal_references": sorted(references),
            "media": media, "project_bound": bound}


def page_anchors(draft: Any) -> set[str]:
    result = set()
    for block_id in draft.order:
        block = draft.blocks.get(block_id)
        if block is not None and not block.deleted:
            result.update(block_dependencies(block.values)["anchors"])
    return result


def copy_preflight(values: dict[str, Any], target_draft: Any) -> dict[str, Any]:
    dependencies = block_dependencies(values)
    target = page_anchors(target_draft)
    issues = []
    duplicates = sorted(set(dependencies["anchors"]) & target)
    if duplicates:
        issues.append({"priority": "must_fix", "code": "duplicate_anchor_on_target",
                       "anchors": duplicates,
                       "action": "Изменить anchor копируемого блока или целевой страницы."})
    missing = sorted(set(dependencies["internal_references"])
                     - set(dependencies["anchors"]) - target)
    if missing:
        issues.append({"priority": "must_fix", "code": "missing_internal_target",
                       "anchors": missing,
                       "action": "Сначала перенести целевые секции или заменить ссылки."})
    if dependencies["project_bound"]:
        issues.append({"priority": "review", "code": "project_bound_references",
                       "items": dependencies["project_bound"],
                       "action": "Проверить сущности в целевом проекте после копирования."})
    blockers = [item for item in issues if item["priority"] == "must_fix"]
    return {"valid": not blockers, "dependencies": dependencies,
            "target_anchors": sorted(target), "issues": issues, "blockers": blockers}
