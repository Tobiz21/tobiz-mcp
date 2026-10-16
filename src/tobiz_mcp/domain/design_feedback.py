"""Structured, privacy-safe design feedback for continuous quality improvement."""

from __future__ import annotations

from typing import Any


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
