"""Combine TOBIZ quality signals into one deterministic release gate."""

from __future__ import annotations

from typing import Any


def _issues(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [{"source": source, **item} for item in items]


def evaluate(audit: dict[str, Any], composition: dict[str, Any],
             reference: dict[str, Any] | None = None,
             roundtrip: dict[str, Any] | None = None,
             *, has_unsaved_changes: bool = False,
             claims: dict[str, Any] | None = None) -> dict[str, Any]:
    reference = reference or {}
    audit_score = float((audit.get("quality_score") or {}).get("overall", 0))
    composition_score = float(composition.get("score", 0))
    dimensions = dict((audit.get("quality_score") or {}).get("dimensions") or {})
    dimensions["architecture"] = composition_score

    weighted = [(audit_score, .55), (composition_score, .3)]
    if reference:
        reference_score = float(reference.get("score", 0))
        dimensions["reference_fidelity"] = reference_score
        weighted.append((reference_score, .1))
    if roundtrip is not None:
        editor_score = 10.0 if roundtrip.get("editor_safe") else 0.0
        dimensions["editor_safety"] = editor_score
        weighted.append((editor_score, .05))
    total_weight = sum(weight for _, weight in weighted)
    overall = round(sum(score * weight for score, weight in weighted) / total_weight, 1)

    blockers = []
    improvements = []
    blockers.extend(_issues(audit.get("critical") or [], "rendered_audit"))
    improvements.extend(_issues(audit.get("warnings") or [], "rendered_audit"))
    for item in composition.get("issues") or []:
        target = blockers if item.get("priority") == "must_fix" else improvements
        target.extend(_issues([item], "composition"))
    for item in reference.get("issues") or []:
        target = blockers if item.get("priority") == "must_fix" else improvements
        target.extend(_issues([item], "design_reference"))
    if claims is not None:
        blockers.extend(_issues(claims.get("issues") or [], "claim_integrity"))
    if roundtrip is not None and not roundtrip.get("editor_safe"):
        blockers.append({
            "source": "editor_roundtrip", "code": "editor_roundtrip_unsafe",
            "action": "Исправить штатный payload и cache блоков до передачи страницы пользователю.",
        })
    if has_unsaved_changes:
        blockers.append({
            "source": "draft", "code": "unsaved_draft_not_audited",
            "action": "Сохранить или сбросить черновик и повторить приемку публичной страницы.",
        })

    if blockers:
        verdict = "save_blocked"
    elif overall < 7 or improvements:
        verdict = "review"
    else:
        verdict = "ready"
    return {
        "verdict": verdict, "score": min(overall, 4.9) if blockers else overall,
        "target": 7.0, "dimensions": {key: round(float(value), 1)
                                        for key, value in dimensions.items()},
        "blockers": blockers, "improvements": improvements,
        "release_ready": verdict == "ready",
        "checks": {
            "public_desktop_mobile": not bool(audit.get("critical")),
            "composition": composition.get("meets_7_of_10", False),
            "reference": None if not reference else reference.get("meets_7_of_10", False),
            "editor_roundtrip": None if roundtrip is None else bool(roundtrip.get("editor_safe")),
            "draft_saved": not has_unsaved_changes,
            "claim_integrity": None if claims is None else bool(claims.get("ready")),
        },
        "rule": "Выдавать сайт можно только при verdict=ready; исправления выполняются штатными блоками TOBIZ.",
    }
