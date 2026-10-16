from tobiz_mcp.domain.design_gate import evaluate


def audit(score=9, critical=None, warnings=None):
    return {"quality_score": {"overall": score, "dimensions": {
        "technical": score, "visual": score, "content": score, "usability": score}},
        "critical": critical or [], "warnings": warnings or []}


def composition(score=9, issues=None):
    return {"score": score, "meets_7_of_10": score >= 7 and not issues,
            "issues": issues or []}


def test_ready_requires_all_quality_layers_to_pass():
    result = evaluate(audit(), composition(), {"score": 9, "meets_7_of_10": True,
                                               "issues": []}, {"editor_safe": True})
    assert result["verdict"] == "ready"
    assert result["release_ready"] is True
    assert result["checks"] == {"public_desktop_mobile": True, "composition": True,
                                "reference": True, "editor_roundtrip": True,
                                "draft_saved": True, "claim_integrity": None,
                                "visual_review": None}


def test_unsupported_claim_blocks_release():
    claims = {"ready": False, "issues": [
        {"priority": "must_fix", "code": "unsupported_price_claim"}]}
    result = evaluate(audit(), composition(), roundtrip={"editor_safe": True}, claims=claims)
    assert result["verdict"] == "save_blocked"
    assert result["checks"]["claim_integrity"] is False
    assert result["blockers"][0]["source"] == "claim_integrity"


def test_critical_or_unsaved_draft_blocks_release_and_caps_score():
    result = evaluate(audit(9, critical=[{"code": "broken_images"}]), composition(),
                      {"score": 9, "meets_7_of_10": True, "issues": []},
                      {"editor_safe": True}, has_unsaved_changes=True)
    assert result["verdict"] == "save_blocked"
    assert result["score"] == 4.9
    assert {item["code"] for item in result["blockers"]} == {
        "broken_images", "unsaved_draft_not_audited"}


def test_improvements_require_review_without_blocking_save():
    result = evaluate(audit(warnings=[{"code": "button_palette_inconsistent"}]),
                      composition(), roundtrip={"editor_safe": True})
    assert result["verdict"] == "review"
    assert result["release_ready"] is False
    assert result["improvements"][0]["source"] == "rendered_audit"


def test_unsafe_editor_and_reference_structure_are_blockers():
    reference = {"score": 8, "meets_7_of_10": False, "issues": [
        {"priority": "must_fix", "code": "reference_structure_drift"}]}
    result = evaluate(audit(), composition(), reference, {"editor_safe": False})
    assert result["verdict"] == "save_blocked"
    assert {item["source"] for item in result["blockers"]} == {
        "design_reference", "editor_roundtrip"}


def test_strict_release_requires_reference_claims_editor_and_visual_review():
    result = evaluate(audit(), composition(), require_complete=True)
    assert result["release_ready"] is False
    assert {item["code"] for item in result["blockers"]} == {
        "required_design_reference_missing", "required_editor_roundtrip_missing",
        "required_claim_integrity_missing", "required_visual_review_missing"}


def test_strict_release_accepts_complete_evidence():
    result = evaluate(
        audit(), composition(), {"score": 9, "meets_7_of_10": True, "issues": []},
        {"editor_safe": True}, claims={"ready": True, "issues": []},
        require_complete=True, visual_review={"approved": True, "notes": "Скриншоты проверены"})
    assert result["verdict"] == "ready"
    assert result["checks"]["visual_review"] is True
