"""Read-only checks for a safe TOBIZ visual-editor save round trip."""

from __future__ import annotations

from typing import Any

from .draft import Draft


def report(draft: Draft, block_types: dict[str, Any], rendered: dict[str, str],
           payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact native payload without sending it to TOBIZ."""
    critical: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    anchors: dict[str, list[str]] = {}
    visible_blocks: list[str] = []
    flex_count = 0

    for block_id in draft.order:
        block = draft.blocks.get(block_id)
        if block is None or block.deleted:
            continue
        visible_blocks.append(block_id)
        block_type = block_types.get(block.type_id)
        if block_type is None:
            critical.append({"code": "unknown_block_type", "block_id": block_id,
                             "type_id": block.type_id})
        elif not getattr(block_type, "has_template", True):
            critical.append({"code": "template_unavailable", "block_id": block_id,
                             "type_id": block.type_id})

        if block.type_id == "163":
            critical.append({"code": "custom_code_block", "block_id": block_id,
                             "message": "Блок содержит пользовательский код"})
        if block.type_id == "1600":
            flex_count += 1

        anchor = str(block.values.get("anchor") or "").strip().lstrip("#")
        if anchor:
            anchors.setdefault(anchor, []).append(block_id)

        hidden_mobile = str(block.values.get("hide_in_mobile") or "0") == "1"
        hidden_desktop = str(block.values.get("hide_in_desktop") or "0") == "1"
        if hidden_mobile and hidden_desktop:
            critical.append({"code": "hidden_everywhere", "block_id": block_id})

        html = rendered.get(block_id, "")
        if len(html.strip()) < 40:
            critical.append({"code": "empty_render", "block_id": block_id,
                             "type_id": block.type_id})

        form = block.values.get("form1")
        if isinstance(form, list):
            has_field = any(isinstance(item, dict) and item.get("type") not in {"btn", "button"}
                            for item in form)
            has_button = any(isinstance(item, dict) and item.get("type") in {"btn", "button"}
                             for item in form)
            if has_field and not has_button:
                warnings.append({"code": "form_without_button", "block_id": block_id})

    for anchor, block_ids in anchors.items():
        if len(block_ids) > 1:
            critical.append({"code": "duplicate_anchor", "anchor": anchor,
                             "block_ids": block_ids})

    flex_share = round(flex_count / max(len(visible_blocks), 1), 3)
    if flex_share > 0.3:
        warnings.append({"code": "high_flex_share", "share": flex_share,
                         "recommended_max": 0.3})

    payload_blocks = [item for item in payload.get("userBlocks", [])
                      if str(item.get("deleted") or "0") != "1"]
    payload_ids = [str(item.get("id")) for item in payload_blocks]
    if payload_ids != visible_blocks:
        critical.append({"code": "payload_order_mismatch", "expected": visible_blocks,
                         "actual": payload_ids})
    for item in payload_blocks:
        block_id = str(item.get("id"))
        if not isinstance(item.get("data"), dict):
            critical.append({"code": "invalid_block_data", "block_id": block_id})
        if not str(item.get("cache") or "").strip():
            critical.append({"code": "empty_block_cache", "block_id": block_id})

    verdict = "save_blocked" if critical else "review" if warnings else "editor_safe"
    return {
        "verdict": verdict,
        "editor_safe": not critical,
        "would_save": False,
        "blocks": len(visible_blocks),
        "flex_blocks": flex_count,
        "flex_share": flex_share,
        "critical": critical,
        "warnings": warnings,
    }
