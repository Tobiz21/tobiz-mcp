"""Compact rendered image evidence for visual and semantic review."""

from __future__ import annotations

from typing import Any


IMAGE_CODES = {
    "broken_images", "missing_alt", "card_image_ratios_inconsistent",
    "image_aspect_distorted", "image_low_resolution", "image_crop_extreme",
    "image_reused_across_sections", "text_over_image_without_scrim",
}


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    inventory: dict[tuple[str, str], dict[str, Any]] = {}
    issues = []
    screenshots = {}
    for viewport, data in (report.get("viewports") or {}).items():
        screenshots[viewport] = data.get("screenshot")
        media = data.get("media") or {}
        for item in media.get("imageItems") or []:
            key = (str(item.get("block") or ""), str(item.get("src") or ""))
            record = inventory.setdefault(key, {
                "block_id": str(item.get("block") or "").removeprefix("b_"),
                "src": item.get("src"), "alt": item.get("alt"),
                "natural": {"width": item.get("naturalWidth"), "height": item.get("naturalHeight")},
                "nearby_text": item.get("nearbyText"), "viewports": {},
            })
            record["viewports"][viewport] = {
                "width": item.get("renderedWidth"), "height": item.get("renderedHeight"),
                "object_fit": item.get("objectFit"),
            }
        for item in (data.get("layout") or {}).get("visualIssues") or []:
            if item.get("code") in IMAGE_CODES:
                issues.append({"viewport": viewport, **item})
        if media.get("brokenImages"):
            issues.append({"viewport": viewport, "code": "broken_images",
                           "items": media["brokenImages"]})
        if media.get("missingAlt"):
            issues.append({"viewport": viewport, "code": "missing_alt",
                           "count": media["missingAlt"]})
    unique_codes = sorted({item["code"] for item in issues})
    critical_codes = {"broken_images", "text_over_image_without_scrim"}
    score = max(0.0, 10 - sum(2.5 if code in critical_codes else .8 for code in unique_codes))
    critical = [item for item in issues if item["code"] in critical_codes]
    return {
        "score": round(min(score, 4.9) if critical else score, 1), "target": 7.0,
        "verdict": "save_blocked" if critical else "review" if issues else "ready",
        "issues": issues, "issue_codes": unique_codes,
        "images": list(inventory.values()), "image_count": len(inventory),
        "screenshots": screenshots,
        "semantic_review": [
            {"block_id": item["block_id"], "src": item["src"], "nearby_text": item["nearby_text"],
             "question": "Соответствует ли фотография смыслу секции и оставляет ли безопасную зону под текст?"}
            for item in inventory.values()
        ],
        "rule": "Автоматические измерения дополняются визуальной проверкой снимков; смысл фото не угадывается по имени файла.",
    }
