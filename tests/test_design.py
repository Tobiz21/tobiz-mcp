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
            'tobiz_editor_roundtrip_check', 'tobiz_build_quality_page'} <= set(names)
