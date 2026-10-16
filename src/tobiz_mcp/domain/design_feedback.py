"""Structured, privacy-safe design feedback for continuous quality improvement."""

from __future__ import annotations

from typing import Any
from collections import Counter


DIMENSIONS = {"layout", "visual", "trust", "content", "mobile", "conversion"}
ISSUE_CODES = {
    "uneven_cards": {"card_heights_misaligned", "card_buttons_misaligned"},
    "hidden_buttons": {"card_button_hidden_initially"},
    "low_contrast": {"text_contrast", "button_surface_contrast", "form_contrast"},
    "mobile_overflow": {"horizontal_overflow"},
    "clipped_content": {"content_clipped"},
    "alignment_inconsistent": {"card_button_alignment_mismatch", "heading_alignment_inconsistent"},
    "weak_first_screen": {"weak_first_screen"},
    "missing_proof": {"missing_proof_section"},
    "broken_forms": {"lead_form_structure", "form_contrast"},
    "inconsistent_buttons": {"button_palette_inconsistent", "button_radii_inconsistent"},
    "thin_content": {"thin_sections"},
}


def normalize(*, project_id: str, page_id: str, score_overall: float,
              dimensions: dict[str, Any] | None = None,
              issues: list[str] | None = None,
              issue_codes: list[str] | None = None,
              corrections: list[str] | None = None,
              notes: str = "", template_id: str = "") -> dict[str, Any]:
    score = float(score_overall)
    if not 0 <= score <= 10:
        raise ValueError("score_overall must be between 0 and 10")
    clean_dimensions: dict[str, float] = {}
    for name, value in (dimensions or {}).items():
        if name not in DIMENSIONS:
            raise ValueError(f"unsupported design dimension: {name}")
        numeric = float(value)
        if not 0 <= numeric <= 10:
            raise ValueError(f"dimension {name} must be between 0 and 10")
        clean_dimensions[name] = numeric

    def clean_list(values: list[str] | None, field: str) -> list[str]:
        if values is not None and not isinstance(values, list):
            raise ValueError(f"{field} must be a list")
        return [str(value).strip() for value in values or [] if str(value).strip()]

    if not str(project_id).strip() or not str(page_id).strip():
        raise ValueError("project_id and page_id are required")
    clean_codes = clean_list(issue_codes, "issue_codes")
    unknown_codes = sorted(set(clean_codes) - set(ISSUE_CODES))
    if unknown_codes:
        raise ValueError("unsupported issue_codes: " + ", ".join(unknown_codes))
    return {
        "project_id": str(project_id),
        "page_id": str(page_id),
        "template_id": str(template_id).strip() or None,
        "score_overall": score,
        "dimensions": clean_dimensions,
        "issues": clean_list(issues, "issues"),
        "issue_codes": clean_codes,
        "corrections": clean_list(corrections, "corrections"),
        "notes": str(notes).strip(),
    }


def summarize(records: list[dict[str, Any]], templates: list[dict[str, Any]] | tuple) -> dict[str, Any]:
    """Aggregate explicit feedback into reusable, explainable design lessons."""
    identities = {(str(item["project_id"]), str(item["page_id"])): item["id"]
                  for item in templates}
    scores: dict[str, list[float]] = {}
    issues: Counter[str] = Counter()
    corrections: Counter[str] = Counter()
    issue_codes: dict[str, Counter[str]] = {}
    for record in records:
        template_id = record.get("template_id") or identities.get(
            (str(record.get("project_id")), str(record.get("page_id"))))
        if template_id:
            scores.setdefault(str(template_id), []).append(float(record.get("score_overall", 0)))
            issue_codes.setdefault(str(template_id), Counter()).update(record.get("issue_codes") or [])
        issues.update(str(value).strip() for value in record.get("issues") or [] if str(value).strip())
        corrections.update(str(value).strip() for value in record.get("corrections") or []
                           if str(value).strip())
    template_scores = {
        key: {"count": len(values), "average": round(sum(values) / len(values), 2)}
        for key, values in scores.items()
    }
    return {
        "records": len(records),
        "template_scores": template_scores,
        "template_issue_codes": {
            key: [{"code": code, "count": count} for code, count in counter.most_common()]
            for key, counter in issue_codes.items()
        },
        "common_issues": [{"text": text, "count": count} for text, count in issues.most_common(10)],
        "proven_corrections": [{"text": text, "count": count}
                               for text, count in corrections.most_common(10)],
    }


def apply_to_selection(selection: dict[str, Any], lessons: dict[str, Any],
                       top_k: int = 3) -> dict[str, Any]:
    """Re-rank templates with a bounded feedback adjustment, preserving base evidence."""
    ranked = [dict(selection["recommended"]),
              *(dict(item) for item in selection.get("alternatives") or [])]
    template_scores = lessons.get("template_scores") or {}
    for item in ranked:
        feedback = template_scores.get(item["id"])
        if not feedback:
            item["feedback"] = {"count": 0, "average": None, "adjustment": 0.0}
            continue
        confidence = min(int(feedback["count"]), 3) / 3
        adjustment = round(max(-6.0, min(4.5, (float(feedback["average"]) - 7) * 1.5))
                           * confidence, 2)
        item["score"] = round(float(item["score"]) + adjustment, 2)
        item["feedback"] = {**feedback, "adjustment": adjustment}
        note = f"Средняя пользовательская оценка: {feedback['average']}/10 ({feedback['count']})"
        (item["reasons"] if adjustment >= 0 else item["risks"]).append(note)
    ranked.sort(key=lambda item: (-item["score"], item["flex_share"], -item["blocks"], item["id"]))
    bounded = max(1, min(int(top_k), len(ranked)))
    return {**selection, "recommended": ranked[0], "alternatives": ranked[1:bounded],
            "feedback_lessons": lessons}


def regression_profile(template_id: str, lessons: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"code": item["code"], "previous_count": item["count"],
         "detects": sorted(ISSUE_CODES[item["code"]])}
        for item in (lessons.get("template_issue_codes") or {}).get(template_id, [])
        if item.get("code") in ISSUE_CODES
    ]


def check_regressions(profile: list[dict[str, Any]], audit: dict[str, Any],
                      composition: dict[str, Any]) -> dict[str, Any]:
    observed = {str(item.get("code")) for item in [
        *(audit.get("critical") or []), *(audit.get("warnings") or []),
        *(composition.get("issues") or []),
    ]}
    recurring = [item for item in profile if observed & set(item.get("detects") or [])]
    return {"passed": not recurring, "profile": profile, "recurring": recurring,
            "observed_codes": sorted(observed)}
