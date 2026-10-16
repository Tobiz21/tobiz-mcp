import pytest
from types import SimpleNamespace

from tobiz_mcp.domain import design
from tobiz_mcp.tools import register


def test_library_contains_verified_installed_sources_and_references():
    result = design.library()
    assert len(result['installed']) == 9
    assert len(result['references']) == 17
    assert all(item['project_id'] and item['page_id'] for item in result['installed'])
    assert result['rules']['max_flex_share'] == .3


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
            'tobiz_copy_native_block'} <= set(names)
