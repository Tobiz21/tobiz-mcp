from __future__ import annotations

import pytest

from tobiz_mcp import errors
from tobiz_mcp.selftest import cmd_release


def finish(coroutine):
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    return completed.value.value


class FakeService:
    def __init__(self, distribution_ready: bool = True, missing_feature: bool = False):
        self.distribution_ready = distribution_ready
        self.missing_feature = missing_feature

    async def onboarding_check(self, project_id: str, page_id: str):
        return {
            "ready": True,
            "distribution_ready": self.distribution_ready,
            "checks": [],
            "editor_roundtrip": {"editor_safe": True, "would_save": False},
        }

    def list_page_backups(self, project_id: str, page_id: str):
        return {"backups": []}

    async def health(self):
        features = [
            "editor_roundtrip_check",
            "safe_page_backups",
            "onboarding_readiness_check",
            "strict_project_isolation",
            "local_privacy_safe_diagnostics",
            "block_level_visual_evidence",
            "native_card_layout_autofix",
            "native_layout_control_registry",
            "safe_layout_repair",
            "page_wide_design_system_analysis",
            "safe_design_refinement",
            "semantic_page_composition_audit",
            "native_design_reference_comparison",
            "unified_design_release_gate",
            "rendered_image_composition_audit",
            "deterministic_native_site_planning",
            "evidence_bound_content_compiler",
            "brief_bound_claim_integrity_audit",
            "pre_copy_recipe_validation",
            "pre_copy_media_validation",
            "unified_pre_copy_build_gate",
            "one_call_site_package_scaffold",
            "direct_validated_site_package_build",
            "batch_site_package_media_upload",
            "safe_site_package_content_fill",
            "resumable_site_package_status",
            "persistent_site_package_checkpoints",
            "automatic_site_package_checkpoints",
            "versioned_site_package_checkpoints",
            "optimistic_site_package_concurrency",
            "verified_image_upload_metadata",
            "post_build_plan_conformance",
            "safe_native_block_reuse",
            "native_flex_inspection_and_editing",
            "design_library_drift_detection",
            "structured_design_feedback",
            "feedback_informed_template_selection",
            "design_feedback_regression_gate",
            "enforced_design_passport_freshness",
            "local_design_passport_refresh",
            "account_local_design_template_registry",
            "quality_gated_design_template_registration",
            "available_template_fallback_selection",
            "bounded_parallel_template_preflight",
            "design_template_candidate_discovery",
            "evidence_first_brief_gate",
            "goal_specific_architecture_gate",
            "native_conversion_contract_gate",
            "native_anchor_recipe_validation",
            "brief_aligned_primary_cta_gate",
            "brief_aligned_seo_gate",
            "semantic_media_assignment_gate",
            "within_group_media_deduplication",
            "content_hash_media_deduplication",
            "brief_to_copy_evidence_traceability",
            "grounded_evidence_mapping",
            "section_aware_evidence_mapping",
            "evidence_aware_recipe_verdict",
            "cross_section_copy_deduplication",
            "placeholder_copy_quality_gate",
            "balanced_native_card_copy_gate",
            "mobile_critical_copy_length_gate",
            "native_form_field_role_profiling",
            "complete_native_form_submission_gate",
            "required_primary_cta_recipe_slot",
            "required_contact_field_gate",
            "labeled_native_form_field_gate",
            "brief_aligned_required_form_fields",
            "nested_native_form_discovery",
            "nested_form_editor_roundtrip",
            "broken_form_editor_blocker",
            "article_publication_quality_audit",
            "product_publication_quality_audit",
            "article_product_preflight",
            "multipage_project_quality_audit",
            "one_call_site_workflow_start",
        ]
        if self.missing_feature:
            features.remove("safe_page_backups")
        return {"version": "0.9.0b3", "features": features}


def test_release_passes_complete_strict_install(capsys) -> None:
    code = finish(cmd_release(FakeService(), "123", "456"))

    assert code == 0
    assert '"release_ready": true' in capsys.readouterr().out


@pytest.mark.parametrize(
    ("service", "expected"),
    [(FakeService(distribution_ready=False), 1), (FakeService(missing_feature=True), 1)],
)
def test_release_rejects_incomplete_install(service, expected, capsys) -> None:
    assert finish(cmd_release(service, "123", "456")) == expected
    assert '"release_ready": false' in capsys.readouterr().out


def test_release_requires_project() -> None:
    with pytest.raises(errors.TobizError) as caught:
        finish(cmd_release(FakeService(), None, "456"))

    assert caught.value.code == errors.BAD_ARGUMENT
