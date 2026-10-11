"""Native TOBIZ layout-control registry and deterministic repair planning."""

from __future__ import annotations

import copy
import re
from typing import Any


RULES = {
    "flex_fix": {"role": "equal_card_button_height", "value": 1, "safe": True},
    "btn_up": {"role": "button_initial_visibility", "value": 0, "safe": True},
    "btn_align": {"role": "button_alignment", "value": "center", "safe": True},
    "btn_move": {"role": "button_hover_animation", "value": 0, "safe": True},
}

MOBILE_TITLE = re.compile(r"мобил|телефон|адаптив", re.I)
LAYOUT_TITLE = re.compile(r"колон|карточ|сетк|ширин|выровн|кноп|изображ|отступ|скруг", re.I)


def _public_control(setting: dict[str, Any]) -> dict[str, Any]:
    name = str(setting.get("name") or "")
    rule = RULES.get(name)
    recommended = _recommended_value(setting, None) if rule else None
    return {
        "name": name,
        "title": str(setting.get("title") or ""),
        "control_type": str(setting.get("type") or ""),
        "role": (rule or {}).get("role", "mobile_layout" if MOBILE_TITLE.search(
            str(setting.get("title") or "")) else "layout_option"),
        "safe_automatic": bool((rule or {}).get("safe")) and recommended is not None,
        "recommended_value": recommended,
        "require": setting.get("require"),
        "options": [
            {"value": option.get("val", option.get("value")), "title": option.get("title", "")}
            for option in setting.get("vars") or [] if isinstance(option, dict)
        ],
    }


def registry(types: dict[str, Any], type_ids: list[str] | None = None) -> dict[str, Any]:
    selected = {str(value) for value in type_ids or []}
    blocks = []
    for type_id, block_type in sorted(types.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 0):
        if selected and str(type_id) not in selected:
            continue
        controls = []
        for setting in block_type.settings or []:
            if not setting.get("name"):
                continue
            title = str(setting.get("title") or "")
            if setting["name"] in RULES or MOBILE_TITLE.search(title) or LAYOUT_TITLE.search(title):
                controls.append(_public_control(setting))
        if controls:
            blocks.append({
                "type_id": str(type_id), "title": block_type.title,
                "controls": controls,
                "safe_automatic_controls": sum(item["safe_automatic"] for item in controls),
            })
    return {
        "types": blocks, "type_count": len(blocks),
        "control_count": sum(len(item["controls"]) for item in blocks),
        "automatic_control_count": sum(item["safe_automatic_controls"] for item in blocks),
    }


def _set(block, name: str, value: Any, changes: list[dict[str, Any]], reason: str) -> None:
    if block.values.get(name) == value:
        return
    block.values[name] = value
    path = f"/{name}"
    if path not in block.changed_paths:
        block.changed_paths.append(path)
    changes.append({"block_id": block.block_id, "type_id": block.type_id,
                    "path": path, "value": value, "reason": reason})


def _off_value(setting: dict[str, Any], current: Any) -> Any:
    if setting.get("type") != "select":
        return 0
    options = setting.get("vars") or []
    for option in options:
        if str(option.get("title") or "").strip().lower() in {"нет", "выкл", "отключено"}:
            return option.get("val", option.get("value"))
    values = [option.get("val", option.get("value")) for option in options]
    return "none" if "none" in values or isinstance(current, str) else 0


def _recommended_value(setting: dict[str, Any], current: Any) -> Any:
    name = str(setting.get("name") or "")
    if name == "btn_move":
        return _off_value(setting, current)
    if name == "btn_align":
        options = [option.get("val", option.get("value"))
                   for option in setting.get("vars") or []]
        return "center" if not options or "center" in options else None
    return (RULES.get(name) or {}).get("value")


def prepare(draft, audit: dict[str, Any], types: dict[str, Any]):
    candidate = copy.deepcopy(draft)
    changes, warnings = [], []
    for block_id, issues in (audit.get("block_evidence") or {}).items():
        block = candidate.blocks.get(str(block_id))
        block_type = types.get(block.type_id) if block else None
        if not block or block.deleted or not block_type:
            continue
        settings = {str(item.get("name")): item for item in block_type.settings or [] if item.get("name")}
        codes = {item.get("code") for item in issues}
        if codes & {"card_heights_misaligned", "card_buttons_misaligned"}:
            if "flex_fix" in settings:
                _set(block, "flex_fix", 1, changes, "align_native_cards_and_buttons")
            else:
                warnings.append({"block_id": block_id, "type_id": block.type_id,
                                 "code": "native_equal_height_control_missing"})
        if "card_button_hidden_initially" in codes:
            if "btn_up" in settings:
                _set(block, "btn_up", 0, changes, "show_card_buttons_immediately")
            if "btn_move" in settings:
                _set(block, "btn_move", _off_value(settings["btn_move"], block.values.get("btn_move")),
                     changes, "disable_card_button_hover_animation")
        if "card_button_alignment_mismatch" in codes:
            if "btn_align" in settings:
                center = _recommended_value(settings["btn_align"], block.values.get("btn_align"))
                if center is not None:
                    _set(block, "btn_align", center, changes,
                         "center_buttons_with_centered_card_text")
                else:
                    warnings.append({"block_id": block_id, "type_id": block.type_id,
                                     "code": "native_center_alignment_option_missing"})
            else:
                warnings.append({"block_id": block_id, "type_id": block.type_id,
                                 "code": "native_button_alignment_control_missing"})
        if "cards_not_stacked_mobile" in codes:
            mobile = [_public_control(item) for item in settings.values()
                      if MOBILE_TITLE.search(str(item.get("title") or ""))]
            warnings.append({"block_id": block_id, "type_id": block.type_id,
                             "code": "mobile_layout_requires_review", "candidates": mobile})
    return candidate, changes, warnings


def issue_count(audit: dict[str, Any]) -> int:
    return len(audit.get("critical") or []) + len(audit.get("warnings") or [])
