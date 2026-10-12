"""Page-wide design-system analysis for native TOBIZ pages."""

from __future__ import annotations

from typing import Any


SYSTEM_CODES = {
    "container_widths_inconsistent", "button_palette_inconsistent",
    "button_radii_inconsistent", "heading_alignment_inconsistent",
    "too_many_font_families", "excessive_section_gap", "text_too_small",
    "card_image_ratios_inconsistent", "image_aspect_distorted", "content_clipped",
}


def summarize(audit: dict[str, Any]) -> dict[str, Any]:
    issues = []
    for item in (audit.get("critical") or []) + (audit.get("warnings") or []):
        if item.get("code") in SYSTEM_CODES:
            issues.append(item)
    profiles = {name: data.get("design_profile") or {}
                for name, data in (audit.get("viewports") or {}).items()}
    return {
        "profiles": profiles,
        "system_issues": issues,
        "system_issue_codes": sorted({item.get("code") for item in issues}),
        "coherent": not issues,
        "principles": [
            "one dominant container grid", "one primary and one secondary button style",
            "consistent card image proportions", "predictable section rhythm",
            "no more than three font families",
        ],
    }


def regression(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_codes = set(summarize(before)["system_issue_codes"])
    after_codes = set(summarize(after)["system_issue_codes"])
    return {"introduced": sorted(after_codes - before_codes),
            "resolved": sorted(before_codes - after_codes),
            "regressed": bool(after_codes - before_codes)}
