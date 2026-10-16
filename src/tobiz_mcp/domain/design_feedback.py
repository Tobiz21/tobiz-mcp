"""Structured, privacy-safe design feedback for continuous quality improvement."""

from __future__ import annotations

from typing import Any
from collections import Counter


DIMENSIONS = {"layout", "visual", "trust", "content", "mobile", "conversion"}


def normalize(*, project_id: str, page_id: str, score_overall: float,
              dimensions: dict[str, Any] | None = None,
              issues: list[str] | None = None,
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
    return {
        "project_id": str(project_id),
        "page_id": str(page_id),
        "template_id": str(template_id).strip() or None,
        "score_overall": score,
        "dimensions": clean_dimensions,
        "issues": clean_list(issues, "issues"),
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
    for record in records:
        template_id = record.get("template_id") or identities.get(
            (str(record.get("project_id")), str(record.get("page_id"))))
        if template_id:
            scores.setdefault(str(template_id), []).append(float(record.get("score_overall", 0)))
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
