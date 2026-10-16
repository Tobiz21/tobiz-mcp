"""Validation and conservative editing contracts for native TOBIZ Flex blocks."""

from __future__ import annotations

import re
from typing import Any

SUPPORTED_TYPES = {"text", "html", "mdicon", "figure", "hint", "image", "video", "form", "btn"}
MODES = ("l", "m", "s", "xs", "xxs")
MOBILE_MODES = ("xs", "xxs")


def elements(values: dict[str, Any]) -> list[dict[str, Any]]:
    raw = values.get("flexblocks") or []
    if isinstance(raw, dict):
        raw = list(raw.values())
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _mode_style(element: dict[str, Any], mode: str) -> dict[str, Any]:
    direct = element.get(mode)
    if isinstance(direct, dict):
        return direct
    styles = element.get("styles")
    if isinstance(styles, dict) and isinstance(styles.get(mode), dict):
        return styles[mode]
    for key in (f"style_{mode}", f"style{mode.upper()}", f"{mode}_style"):
        if isinstance(element.get(key), dict):
            return element[key]
    return {}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.fullmatch(r"\s*(-?(?:\d+(?:\.\d+)?|\.\d+))\s*(?:px|%)?\s*", str(value or ""))
    return float(match.group(1)) if match else None


def _box(element: dict[str, Any], mode: str) -> tuple[float, float, float, float] | None:
    style = _mode_style(element, mode)
    aliases = {
        "x": ("x", "left"), "y": ("y", "top"),
        "w": ("w", "width"), "h": ("h", "height"),
    }
    values = {}
    for name, keys in aliases.items():
        value = None
        for key in keys:
            candidate = _number(style.get(key))
            if candidate is not None:
                value = candidate
                break
        if value is None:
            return None
        values[name] = value
    return values["x"], values["y"], values["w"], values["h"]


def _overlap(left: tuple[float, float, float, float],
             right: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = left
    bx, by, bw, bh = right
    return min(ax + aw, bx + bw) - max(ax, bx) > 4 and min(ay + ah, by + bh) - max(ay, by) > 4


def validate(values: dict[str, Any]) -> dict[str, Any]:
    """Validate an existing native Flex model without guessing vendor-specific missing fields."""
    items = elements(values)
    issues: list[dict[str, Any]] = []
    identities: dict[str, int] = {}
    inventory = []
    for index, element in enumerate(items):
        element_type = str(element.get("type") or element.get("type_id") or "").lower()
        identity = str(element.get("id") or element.get("uuid") or element.get("guid") or "")
        if not element_type:
            issues.append({"priority": "must_fix", "code": "flex_element_type_missing", "index": index})
        elif element_type not in SUPPORTED_TYPES:
            issues.append({"priority": "must_fix", "code": "flex_element_type_unsupported",
                           "index": index, "type": element_type})
        if identity:
            identities[identity] = identities.get(identity, 0) + 1
        modes = [mode for mode in MODES if _mode_style(element, mode)]
        inventory.append({"index": index, "id": identity or None, "type": element_type,
                          "responsive_modes": modes})
        positioned = any(_box(element, mode) is not None for mode in MODES)
        if positioned and not any(_mode_style(element, mode) for mode in MOBILE_MODES):
            issues.append({"priority": "must_fix", "code": "flex_mobile_layout_missing",
                           "index": index, "type": element_type,
                           "action": "Задать штатную геометрию элемента для xs или xxs."})
        for mode in MODES:
            box = _box(element, mode)
            if box and (box[2] <= 0 or box[3] <= 0):
                issues.append({"priority": "must_fix", "code": "flex_element_size_invalid",
                               "index": index, "mode": mode,
                               "width": box[2], "height": box[3]})
        if element_type == "btn":
            for mode in MOBILE_MODES:
                box = _box(element, mode)
                if box and (box[2] < 44 or box[3] < 44):
                    issues.append({"priority": "must_fix", "code": "flex_cta_too_small",
                                   "index": index, "mode": mode, "width": box[2], "height": box[3]})
    for identity, count in identities.items():
        if count > 1:
            issues.append({"priority": "must_fix", "code": "flex_duplicate_element_id",
                           "id": identity, "count": count})
    for mode in MODES:
        boxes = [(index, _box(element, mode)) for index, element in enumerate(items)]
        boxes = [(index, box) for index, box in boxes if box is not None]
        for offset, (left_index, left) in enumerate(boxes):
            for right_index, right in boxes[offset + 1:]:
                if _overlap(left, right):
                    issues.append({"priority": "must_fix" if mode in MOBILE_MODES else "improve",
                                   "code": "flex_elements_overlap", "mode": mode,
                                   "element_indexes": [left_index, right_index]})
    blockers = [item for item in issues if item["priority"] == "must_fix"]
    schema_profile = {
        "root_keys": sorted(str(key) for key in values),
        "element_keys_by_type": {},
        "style_keys_by_mode": {},
    }
    for element in items:
        element_type = str(element.get("type") or element.get("type_id") or "unknown").lower()
        current = schema_profile["element_keys_by_type"].setdefault(element_type, set())
        current.update(str(key) for key in element)
        for mode in MODES:
            style = _mode_style(element, mode)
            if style:
                mode_keys = schema_profile["style_keys_by_mode"].setdefault(mode, set())
                mode_keys.update(str(key) for key in style)
    schema_profile["element_keys_by_type"] = {
        key: sorted(value) for key, value in schema_profile["element_keys_by_type"].items()}
    schema_profile["style_keys_by_mode"] = {
        key: sorted(value) for key, value in schema_profile["style_keys_by_mode"].items()}
    return {
        "valid": not blockers, "element_count": len(items), "elements": inventory,
        "supported_types": sorted(SUPPORTED_TYPES), "responsive_modes": list(MODES),
        "schema_profile": schema_profile, "issues": issues, "blockers": blockers,
    }
