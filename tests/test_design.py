import pytest
from types import SimpleNamespace

from tobiz_mcp.domain import design, design_feedback
from tobiz_mcp.domain.draft import Draft, DraftBlock
from tobiz_mcp.service import Service
from tobiz_mcp.tools import register


def test_library_contains_verified_installed_sources_and_references():
    result = design.library()
    assert len(result['installed']) == 9
    assert len(result['references']) == 17
    assert all(item['project_id'] and item['page_id'] for item in result['installed'])
    assert result['rules']['max_flex_share'] == .3


def test_design_passport_detects_native_structure_drift():
    draft = Draft(project_id="1", page_id="2")
    draft.blocks = {
        "1": DraftBlock("1", "101", {}),
        "2": DraftBlock("2", "1600", {}),
        "3": DraftBlock("3", "226", {}, deleted=True),
    }
    valid = design.validate_passport(
        {"id": "sample", "blocks": 2, "flex_share": .5}, draft)
    assert valid["valid"] is True
    drift = design.validate_passport(
        {"id": "sample", "blocks": 3, "flex_share": 0}, draft)
    assert drift["valid"] is False
    assert {item["field"] for item in drift["mismatches"]} == {"blocks", "flex_share"}


def test_custom_design_passport_uses_live_native_structure():
    draft = Draft(project_id="7", page_id="8")
    draft.blocks = {
        "1": DraftBlock("1", "101", {}),
        "2": DraftBlock("2", "1600", {}),
    }
    passport = design.custom_passport(
        template_id="local-service", title="Локальные услуги", project_id="7", page_id="8",
        visual_system="friendly_service", site_kind="expert_service",
        concepts_list=["service", "regional"], strengths=["process", "contacts"],
        photo_dependency="medium", content_density="medium", draft=draft)
    assert passport["blocks"] == 2
    assert passport["flex_share"] == .5
    assert passport["source"] == "local_verified_page"


def test_template_registration_requires_visual_and_technical_quality():
    blocked = design.template_registration_gate(
        {"critical": [{"code": "horizontal_overflow"}],
         "quality_score": {"overall": 5}},
        {"score": 6}, {"editor_safe": False},
        visual_review_approved=False, visual_review_notes="")
    assert blocked["ready"] is False
    assert {item["code"] for item in blocked["blockers"]} == {
        "template_render_failures", "template_editor_unsafe",
        "template_composition_below_7", "template_visual_review_missing",
    }
    ready = design.template_registration_gate(
        {"critical": [], "quality_score": {"overall": 8}},
        {"score": 8}, {"editor_safe": True},
        visual_review_approved=True,
        visual_review_notes="Desktop, tablet and mobile reviewed; no overlaps.")
    assert ready["ready"] is True


def test_regional_drilling_prefers_long_native_construction_template():
    result = design.select({
        'industry': 'Бурение скважин в Чувашии',
        'offer': 'Услуги для частных домов и участков',
        'needs': ['catalog', 'process', 'contacts', 'seo'],
        'page_length': 'long',
        'photo_quality': 'low',
    })
    assert result['recommended']['id'] == 'foam-blocks'
    assert result['recommended']['flex_share'] == 0
    assert result['visual_references'][0]['id'] == 'aktive-montage'


def test_event_brief_is_not_classified_as_construction():
    selection, selected = design.select_native({
        'industry': 'Квест Темно и весело',
        'offer': 'Праздник под ключ для компании друзей',
        'goal': 'Узнать свободное время',
    })
    assert 'event' in selection['brief_concepts']
    assert 'construction' not in selection['brief_concepts']
    assert selected['id'] == 'culinary'


def test_medical_booking_prefers_booking_template_even_with_flex_risk():
    result = design.select({
        'industry': 'Медицинская клиника',
        'goal': 'Запись к врачу',
        'needs': ['booking', 'experts', 'contacts'],
    })
    assert result['recommended']['id'] == 'medical-booking'
    assert any('Flex' in risk for risk in result['recommended']['risks'])


def test_native_preference_penalizes_flex_heavy_generic_expert_template():
    result = design.select({
        'industry': 'Экспертные консультации и обучение',
        'needs': ['catalog', 'consultation'],
        'prefer_native': True,
    }, top_k=9)
    dog = next(item for item in [result['recommended'], *result['alternatives']]
               if item['id'] == 'dog-trainer')
    assert dog['score'] < 20
    assert any('Flex' in risk for risk in dog['risks'])


def test_quality_selection_enforces_native_flex_limit():
    selection, selected = design.select_native({
        'industry': 'Медицинская клиника',
        'goal': 'Запись к врачу',
        'needs': ['booking', 'experts', 'contacts'],
    })
    assert selection['recommended']['id'] == 'medical-booking'
    assert selection['recommended']['flex_share'] > .3
    assert selected['flex_share'] <= .3


def test_empty_brief_is_rejected_and_top_k_is_bounded():
    with pytest.raises(ValueError):
        design.select({})
    result = design.select({'industry': 'магазин одежды'}, top_k=100)
    assert len(result['alternatives']) == 8


def test_design_tools_are_registered_as_read_only_operations():
    class MCP:
        def tool(self, name, description):
            return lambda fn: fn

    names = register(MCP(), SimpleNamespace(config=SimpleNamespace(read_only=False)))
    assert {'tobiz_design_library', 'tobiz_select_design',
            'tobiz_editor_roundtrip_check', 'tobiz_build_quality_page',
            'tobiz_improve_page', 'tobiz_layout_registry', 'tobiz_repair_layout',
            'tobiz_refine_design', 'tobiz_audit_composition',
            'tobiz_compare_design_reference', 'tobiz_release_design_gate',
            'tobiz_audit_images'} <= set(names)
    assert {'tobiz_plan_site', 'tobiz_compile_site_content', 'tobiz_validate_site_recipe',
            'tobiz_validate_media_recipe',
            'tobiz_prepare_site_package',
            'tobiz_fill_package_content',
            'tobiz_site_package_status',
            'tobiz_save_site_package', 'tobiz_list_site_packages', 'tobiz_load_site_package',
            'tobiz_delete_site_package',
            'tobiz_list_site_package_revisions', 'tobiz_restore_site_package_revision',
            'tobiz_fill_package_media',
            'tobiz_preflight_site_build',
            'tobiz_build_site_package',
            'tobiz_audit_claims',
            'tobiz_check_site_plan',
            'tobiz_inspect_flex_block', 'tobiz_audit_flex_page', 'tobiz_update_flex_block',
            'tobiz_copy_native_block', 'tobiz_validate_design_library',
            'tobiz_record_design_feedback', 'tobiz_list_design_feedback',
            'tobiz_design_lessons', 'tobiz_refresh_design_passport',
            'tobiz_register_design_template'} <= set(names)


def test_design_feedback_normalizes_scores_and_rejects_unknown_dimensions():
    record = design_feedback.normalize(
        project_id="1", page_id="2", score_overall=7.5,
        dimensions={"layout": 8, "mobile": 6},
        issues=["  Карточки разной высоты  ", ""],
        corrections=["Выровнять штатной настройкой"],
    )
    assert record["issues"] == ["Карточки разной высоты"]
    assert record["dimensions"] == {"layout": 8.0, "mobile": 6.0}
    with pytest.raises(ValueError):
        design_feedback.normalize(project_id="1", page_id="2", score_overall=11)
    with pytest.raises(ValueError):
        design_feedback.normalize(
            project_id="1", page_id="2", score_overall=5, dimensions={"magic": 5})


def test_design_feedback_local_roundtrip(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(audit_dir=tmp_path)
    first = service.record_design_feedback(design_feedback.normalize(
        project_id="1", page_id="2", score_overall=4, issues=["Слабое доверие"]))
    service.record_design_feedback(design_feedback.normalize(
        project_id="1", page_id="3", score_overall=8))
    result = service.list_design_feedback(project_id="1", page_id="2")
    assert result["count"] == 1
    assert result["average_score"] == 4
    assert result["records"][0]["feedback_id"] == first["feedback_id"]


def test_local_design_passport_override_roundtrip(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(audit_dir=tmp_path)
    stored = service.save_design_passport_override(
        "sample", {"actual": {"blocks": 17, "flex_share": .118}})
    assert stored["blocks"] == 17
    loaded = service.design_passport_overrides()
    assert loaded["sample"]["flex_share"] == .118
    assert loaded["sample"]["verified_at"]


def test_custom_design_template_registry_roundtrip(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(audit_dir=tmp_path)
    passport = {"id": "local-one", "project_id": "1", "page_id": "2"}
    stored = service.save_custom_design_template(passport)
    assert stored["verified_at"]
    assert service.custom_design_templates()[0]["id"] == "local-one"
    with pytest.raises(Exception):
        service.save_custom_design_template(passport)


def test_template_override_cannot_replace_source_identity(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(audit_dir=tmp_path, read_only=False)
    service._tool_metrics = {}
    (tmp_path / "design-passports.json").write_text(
        '{"modular-homes":{"project_id":"attacker","page_id":"evil","blocks":14,'
        '"flex_share":0.0}}', encoding="utf-8")
    functions = {}

    class MCP:
        def tool(self, name, description):
            def decorator(fn):
                functions[name] = fn
                return fn
            return decorator

    register(MCP(), service)
    result = __import__("asyncio").run(functions["tobiz_design_library"]())
    item = next(value for value in result["data"]["installed"]
                if value["id"] == "modular-homes")
    assert item["project_id"] == "433135"
    assert item["page_id"] == "1221163"


def test_design_feedback_reorders_templates_with_bounded_evidence():
    base = design.select({"industry": "магазин одежды"}, top_k=9)
    lessons = design_feedback.summarize([
        {"project_id": "433136", "page_id": "1221168", "score_overall": 2,
         "issues": ["Слабая мобильная верстка"], "corrections": ["Сократить заголовки"]},
        {"project_id": "433136", "page_id": "1221168", "score_overall": 2,
         "issues": ["Слабая мобильная верстка"], "corrections": []},
        {"project_id": "433136", "page_id": "1221168", "score_overall": 2,
         "issues": [], "corrections": []},
    ], design.INSTALLED)
    adjusted = design_feedback.apply_to_selection(base, lessons, top_k=9)
    jeans = next(item for item in [adjusted["recommended"], *adjusted["alternatives"]]
                 if item["id"] == "jeans-store")
    assert jeans["feedback"]["adjustment"] == -6
    assert lessons["common_issues"][0] == {"text": "Слабая мобильная верстка", "count": 2}
    assert any("пользовательская оценка" in risk for risk in jeans["risks"])


def test_known_design_issue_becomes_regression_check():
    records = [{"project_id": "433136", "page_id": "1221168", "score_overall": 5,
                "issue_codes": ["uneven_cards"], "issues": [], "corrections": []}]
    lessons = design_feedback.summarize(records, design.INSTALLED)
    profile = design_feedback.regression_profile("jeans-store", lessons)
    assert profile[0]["detects"] == ["card_buttons_misaligned", "card_heights_misaligned"]
    result = design_feedback.check_regressions(
        profile, {"critical": [], "warnings": [{"code": "card_heights_misaligned"}]},
        {"issues": []})
    assert result["passed"] is False
    assert result["recurring"][0]["code"] == "uneven_cards"


def test_unknown_design_issue_code_is_rejected():
    with pytest.raises(ValueError):
        design_feedback.normalize(
            project_id="1", page_id="2", score_overall=5,
            issue_codes=["make_it_pretty"])


@pytest.mark.asyncio
async def test_design_library_validator_reports_drift(monkeypatch):
    functions = {}

    class MCP:
        def tool(self, name, description):
            def decorator(fn):
                functions[name] = fn
                return fn
            return decorator

    draft = Draft(project_id="x", page_id="y")
    draft.blocks = {
        "1": DraftBlock("1", "101", {}),
        "2": DraftBlock("2", "1600", {}),
    }

    class FakeService:
        config = SimpleNamespace(read_only=False)

        def design_passport_overrides(self):
            return {}

        def custom_design_templates(self):
            return []

        async def resolve_page(self, project_id, page_id):
            return project_id, SimpleNamespace()

        async def draft(self, project_id, page_id):
            return draft

    monkeypatch.setattr(design, "INSTALLED", ({
        "id": "sample", "project_id": "x", "page_id": "y",
        "blocks": 2, "flex_share": 0.0,
    },))
    register(MCP(), FakeService())
    response = await functions["tobiz_validate_design_library"]()
    assert response["ok"] is True
    assert response["data"]["valid"] is False
    assert response["data"]["templates"][0]["actual_flex_share"] == .5


@pytest.mark.asyncio
async def test_design_selection_skips_unavailable_source(monkeypatch):
    functions = {}

    class MCP:
        def tool(self, name, description):
            def decorator(fn):
                functions[name] = fn
                return fn
            return decorator

    common = {
        "title": "Услуги", "visual_system": "friendly_service",
        "site_kind": "expert_service", "concepts": ["service"],
        "strengths": ["contacts"], "photo_dependency": "medium",
        "content_density": "medium", "blocks": 1, "flex_share": 0.0,
    }
    monkeypatch.setattr(design, "INSTALLED", (
        {**common, "id": "a-bad", "project_id": "bad", "page_id": "1"},
        {**common, "id": "z-good", "project_id": "good", "page_id": "2"},
    ))
    draft = Draft(project_id="good", page_id="2")
    draft.blocks = {"1": DraftBlock("1", "101", {})}

    class FakeService:
        config = SimpleNamespace(read_only=False)

        def design_passport_overrides(self):
            return {}

        def custom_design_templates(self):
            return []

        def list_design_feedback(self, **kwargs):
            return {"records": []}

        async def resolve_page(self, project_id, page_id):
            if project_id == "bad":
                raise RuntimeError("not available")
            return project_id, SimpleNamespace()

        async def draft(self, project_id, page_id):
            return draft

    register(MCP(), FakeService())
    response = await functions["tobiz_select_design"]({"industry": "услуги"}, top_k=2)
    assert response["ok"] is True
    assert response["data"]["recommended"]["id"] == "z-good"
    assert response["data"]["unavailable_sources"][0]["id"] == "a-bad"
    assert response["data"]["availability_checked"] is True
