import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain.content import compact_blueprint, content_map, fingerprint, passport, prepare, recipe_coverage
from tobiz_mcp.domain.audit import compact
from tobiz_mcp.domain.draft import Draft, DraftBlock, DraftStore
from tobiz_mcp.errors import TobizError
from tobiz_mcp.tools import register
from tobiz_mcp.service import Service
from tobiz_mcp.domain.content import recipe_edits
from tobiz_mcp.domain.template import prepare_template, prepare_visual_fixes


def test_recipe_rebinds_ids_and_rejects_layout_mismatch():
    draft = sample()
    recipe = {'types': ['130'], 'slots': [{'block_index': 0, 'path': '/title', 'value': 'New'}]}
    assert recipe_edits(draft, recipe)[0]['block_id'] == '3'
    draft.blocks['3'].type_id = '101'
    with pytest.raises(TobizError):
        recipe_edits(draft, recipe)


def test_template_preparation_is_native_and_atomic():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '1154', {
            'anchor': 'cover', 'form1': [{'type': 'text'}],
            'btn1': {'link': '#old', 'use_form': '0'},
        }),
        '2': DraftBlock('2', '144', {
            'anchor': 'gallery', 'active_off': 0, 'fix_txt_img': 0,
            'arr1': [{'image_box': {'title': 'Step', 'descr': ''}}],
        }),
        '3': DraftBlock('3', '165', {
            'show_vk': 1, 'link_vk': '', 'show_tg': 1, 'link_tg': 'https://tobiz.net/demo',
            'text': 'Название товара',
        }),
        '4': DraftBlock('4', '306', {
            'back_dark': 1, 'show_form_title': 1,
            'form_title': '<strong>Contact us</strong>',
        }),
    }, order=['1', '2', '3', '4'])
    before = copy.deepcopy(draft)
    candidate, changes, warnings = prepare_template(draft, fingerprint(draft))
    assert draft == before
    assert candidate.blocks['1'].values['btn1'] == {'link': '', 'use_form': '1'}
    assert candidate.blocks['2'].values['fix_txt_img'] == 1
    assert candidate.blocks['2'].values['active_off'] == 1
    assert candidate.blocks['3'].values['show_vk'] == 0
    assert candidate.blocks['3'].values['show_tg'] == 0
    assert '#ffffff' in candidate.blocks['4'].values['form_title']
    assert len(changes) == 7
    assert warnings[0]['code'] == 'demo_content'


def test_template_preparation_puts_name_before_phone_without_rebuilding_form():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '306', {'form1': [
            {'type': 'phone', 'title': 'Телефон', 'required': 1},
            {'type': 'text', 'title': 'Ваше имя', 'required': 0},
            {'type': 'email', 'title': 'Email'},
            {'type': 'btn', 'title': 'Отправить'},
        ]}),
    }, order=['1'])
    candidate, changes, warnings = prepare_template(draft, fingerprint(draft))
    assert [item['type'] for item in candidate.blocks['1'].values['form1']] == [
        'text', 'phone', 'email', 'btn']
    assert changes[0]['reason'] == 'put_name_before_phone'
    assert warnings == []


def test_visual_preparation_uses_only_controls_present_on_affected_block():
    draft = Draft('1', '2', blocks={
        '10': DraftBlock('10', '130', {
            'flex_fix': 0, 'btn_up': 1, 'btn_move': 1, 'btn_align': 'left'}),
        '11': DraftBlock('11', '167', {'title': 'No matching controls'}),
    }, order=['10', '11'])
    audit = {'block_evidence': {
        '10': [
            {'code': 'card_heights_misaligned'},
            {'code': 'card_buttons_misaligned'},
            {'code': 'card_button_hidden_initially'},
            {'code': 'card_button_alignment_mismatch'},
        ],
        '11': [{'code': 'card_buttons_misaligned'}],
    }}
    candidate, changes, warnings = prepare_visual_fixes(draft, audit)
    assert candidate.blocks['10'].values == {
        'flex_fix': 1, 'btn_up': 0, 'btn_move': 0, 'btn_align': 'center'}
    assert draft.blocks['10'].values['flex_fix'] == 0
    assert {item['reason'] for item in changes} == {
        'align_native_cards_and_buttons', 'show_card_buttons_immediately',
        'disable_card_button_hover_animation', 'center_buttons_with_centered_card_text'}
    assert warnings == [{'block_id': '11', 'code': 'native_equal_height_control_missing'}]


def test_visual_preparation_uses_none_for_select_button_animation():
    draft = Draft('1', '2', blocks={
        '10': DraftBlock('10', '130', {'btn_up': 1, 'btn_move': 'pulse'}),
    }, order=['10'])
    candidate, changes, warnings = prepare_visual_fixes(draft, {'block_evidence': {
        '10': [{'code': 'card_button_hidden_initially'}]}})
    assert candidate.blocks['10'].values == {'btn_up': 0, 'btn_move': 'none'}
    assert len(changes) == 2
    assert warnings == []


def sample():
    return Draft('1', '2', blocks={'3': DraftBlock('3', '130', {
        'title': 'Old', 'image': 'old.jpg', 'items': [{'title': 'Item', 'image': 'null.png'}],
        'columns': 4, 'html': '<p>untouched</p>', 'styles': {'title': 'skip'},
    })}, order=['3'])


def test_map_and_structure():
    draft = sample()
    assert len(content_map(draft)['blocks'][0]['fields']) == 4
    candidate, changes = prepare(draft, [{'block_id': '3', 'path': '/items/0/title', 'value': 'New'}], 'gray.png')
    assert len(changes) == 2
    assert draft.blocks['3'].values['image'] == 'old.jpg'
    assert candidate.blocks['3'].values['items'][0]['image'] == 'null.png'
    assert candidate.blocks['3'].values['columns'] == 4
    assert candidate.order == draft.order


def test_compact_blueprint_groups_image_variants_and_omits_empty_text():
    draft = Draft('1', '2', blocks={'3': DraftBlock('3', '130', {
        'title': 'Каталог', 'sub_title': '',
        'arr1': [{'image1': 'a.jpg', 'image1_1': 'b.jpg', 'image1_2': 'c.jpg'}],
    })}, order=['3'])
    result = compact_blueprint(passport(draft), content_map(draft))
    assert result['recipe']['types'] == ['130']
    assert [slot['path'] for slot in result['recipe']['slots']] == ['/title']
    assert result['image_slots'] == 3
    assert result['image_groups'] == 1
    assert result['photo_slots'][0]['path_pattern'] == '/arr1/0/image1'
    assert result['photo_slots'][0]['slots'] == 3


def test_recipe_coverage_requires_meaningful_copy_but_skips_generic_controls():
    draft = Draft('1', '2', blocks={'3': DraftBlock('3', '1154', {
        'title': 'Старый заголовок', 'phone1': '+7 900 000-00-00',
        'btn1': {'title': 'Отправить заявку', 'link': '#form'},
    })}, order=['3'])
    blueprint = compact_blueprint(passport(draft), content_map(draft))
    recipe = {'types': ['1154'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Новый заголовок'},
        {'block_index': 0, 'path': '/phone1', 'value': '+7 900 000-00-00'},
    ]}
    result = recipe_coverage(blueprint, recipe)
    assert result['required'] == 2
    assert result['replaced'] == 1
    assert result['unchanged'][0]['path'] == '/phone1'
    assert result['complete'] is False
    recipe['slots'][1]['value'] = '+7 8352 00-00-00'
    assert recipe_coverage(blueprint, recipe)['complete'] is True


def test_map_includes_native_nested_subtitles_and_form_copy():
    draft = sample()
    draft.blocks['3'].values.update({
        'arr1': [{'subtitle1': '<p>Body</p>', 'subtitle2': '<p>Second</p>'}],
        'form_title': '<strong>Contact</strong>',
        'form_text': 'Consent copy',
    })
    paths = {field['path'] for field in content_map(draft)['blocks'][0]['fields']}
    assert {'/arr1/0/subtitle1', '/arr1/0/subtitle2', '/form_title', '/form_text'} <= paths


def test_passport_classifies_images_and_long_text():
    draft = sample()
    draft.blocks['3'].values['title'] = 'x' * 71
    result = passport(draft)
    title = next(x for x in result['blocks'][0]['fields'] if x['path'] == '/title')
    image = next(x for x in result['blocks'][0]['fields'] if x['path'] == '/image')
    assert title['role'] == 'section_title'
    assert result['warnings'][0]['code'] == 'text_over_recommended'
    assert image['role'] == 'catalog_image'


def test_compact_audit_filters_map_canvas_and_surfaces_real_errors():
    report = {'url': 'https://example.test', 'viewports': {'mobile': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [{'tag': 'canvas'}]},
        'media': {'brokenImages': [], 'missingAlt': 2},
        'interactions': {'broken': [
            {'issue': 'no_action', 'classes': ['ymaps-2-1-79-copyright__logo']},
            {'issue': 'missing_anchor', 'classes': ['btn1'], 'text': 'Go'},
        ], 'forms': []},
        'screenshot': 'mobile.png',
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['status'] == 'needs_fix'
    assert result['critical'][0]['code'] == 'missing_anchor'
    assert {x['code'] for x in result['warnings']} == {'inactive_optional_link', 'missing_alt'}


def test_compact_audit_keeps_native_only_advisories_ready():
    report = {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [], 'textContrast': []},
        'media': {'brokenImages': [], 'missingAlt': 6},
        'content': {'termMatches': []},
        'interactions': {'broken': [
            {'issue': 'no_action', 'classes': ['ymaps-2-1-79-copyright__logo']},
        ], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['status'] == 'pass'
    assert result['verdict'] == 'ready'
    assert {item['code'] for item in result['warnings']} == {
        'inactive_optional_link', 'missing_alt'}


def test_compact_audit_ignores_hidden_fields_and_closed_mobile_menu():
    report = {'url': 'https://example.test', 'viewports': {'mobile': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [{'tag': 'ul', 'classes': ['menu']} ]},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'interactions': {'broken': [], 'forms': [{
            'visible': True,
            'issues': [{'tag': 'input', 'issues': ['not_visible']}],
        }]},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['status'] == 'pass'
    assert result['critical'] == []
    assert result['viewports']['mobile']['form_issues'] == 0


def test_compact_audit_blocks_source_terms_and_text_contrast():
    report = {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [],
                   'textContrast': [{'tag': 'div', 'text': 'Hidden', 'ratio': 1.2}]},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': [{'term': 'пеноблок', 'count': 2}]},
        'interactions': {'broken': [], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['verdict'] == 'save_blocked'
    assert {item['code'] for item in result['critical']} == {
        'source_content_leftover', 'text_contrast'}


def test_compact_audit_blocks_button_matching_section_surface():
    report = {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [], 'textContrast': [],
                   'buttonSurfaceContrast': [
                       {'tag': 'button', 'text': 'Send', 'ratio': 1.08}]},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': []},
        'interactions': {'broken': [], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['verdict'] == 'save_blocked'
    assert result['critical'][0]['code'] == 'button_surface_contrast'


def test_compact_audit_blocks_invalid_lead_form_structure():
    report = {'url': 'https://example.test', 'viewports': {'mobile': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [], 'textContrast': []},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': []},
        'interactions': {'broken': [], 'forms': [{
            'visible': True, 'issues': [],
            'formIssues': ['missing_lead_name'],
        }]},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['verdict'] == 'save_blocked'
    assert result['critical'][0]['code'] == 'lead_form_structure'
    assert result['viewports']['mobile']['form_issues'] == 1


def test_compact_audit_marks_content_integrity_for_review():
    report = {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [], 'textContrast': []},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': [], 'integrity': {'issues': [
            {'code': 'thin_page_content', 'characters': 240},
            {'code': 'missing_contact_signal'},
        ]}},
        'interactions': {'broken': [], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['status'] == 'pass'
    assert result['verdict'] == 'review'
    assert {item['code'] for item in result['warnings']} == {
        'thin_page_content', 'missing_contact_signal'}


def test_compact_audit_marks_visual_inconsistency_for_review():
    report = {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [], 'textContrast': [],
                   'visualIssues': [
                       {'code': 'too_many_font_families', 'items': ['arial', 'georgia', 'impact', 'verdana']},
                       {'code': 'text_too_small', 'count': 2},
                   ]},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': []},
        'interactions': {'broken': [], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['status'] == 'pass'
    assert result['verdict'] == 'review'
    assert {item['code'] for item in result['warnings']} == {
        'too_many_font_families', 'text_too_small'}
    assert result['quality_score']['overall'] == 9.4
    assert result['quality_score']['dimensions']['visual'] == 7.5
    assert result['quality_score']['meets_7_of_10'] is True


def test_compact_audit_critical_error_caps_quality_below_five():
    report = {'url': 'https://example.test', 'viewports': {'mobile': {
        'document': {'overflowX': True},
        'layout': {'horizontalOverflow': [{'tag': 'div'}], 'blockIssues': [], 'textContrast': []},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': []},
        'interactions': {'broken': [], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['quality_score']['overall'] == 4.9
    assert result['quality_score']['dimensions']['technical'] == 7.0
    assert result['quality_score']['meets_7_of_10'] is False
    assert result['fix_plan'][0] == {
        'priority': 'must_fix',
        'dimension': 'technical',
        'code': 'horizontal_overflow',
        'action': 'Исправить ширину или позиционирование элементов на мобильном экране.',
        'block_ids': [],
    }


def test_compact_audit_groups_visual_evidence_by_native_block():
    report = {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'textContrast': [],
                   'blockIssues': [
                       {'block': 'b_42', 'code': 'card_buttons_misaligned', 'difference': 30}],
                   'visualIssues': []},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': []},
        'interactions': {'broken': [], 'forms': []},
    }}, 'consoleErrors': [], 'pageErrors': []}
    result = compact(report)
    assert result['block_evidence']['42'][0]['code'] == 'card_buttons_misaligned'
    assert result['fix_plan'][0]['block_ids'] == ['42']


def test_health_identifies_loaded_quality_features(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(
        transport='stdio', read_only=False, dry_run=False, assets_dir=tmp_path,
        require_project_allowlist=False, allowed_project_ids=frozenset())
    service.client = SimpleNamespace(describe_session=lambda: {'present': True})
    service.bridge = SimpleNamespace(available=True)
    service._counters = {}
    with pytest.raises(StopIteration) as completed:
        service.health().send(None)
    result = completed.value.value
    assert result['version'] == '0.9.0b2'
    assert 'button_surface_contrast_detection' in result['features']
    assert 'design_passport_selection' in result['features']
    assert 'editor_roundtrip_check' in result['features']
    assert 'quality_page_pipeline' in result['features']
    assert 'compact_quality_blueprint' in result['features']
    assert 'quality_recipe_coverage' in result['features']
    assert 'content_integrity_detection' in result['features']
    assert 'visual_consistency_detection' in result['features']
    assert 'explainable_quality_score' in result['features']
    assert 'safe_autonomous_page_improvement' in result['features']
    assert 'block_level_visual_evidence' in result['features']
    assert 'native_card_layout_autofix' in result['features']
    assert 'mobile_card_layout_detection' in result['features']
    assert 'clipped_content_detection' in result['features']
    assert 'native_layout_control_registry' in result['features']
    assert 'safe_layout_repair' in result['features']
    assert 'page_wide_design_system_analysis' in result['features']
    assert 'safe_design_refinement' in result['features']
    assert 'semantic_page_composition_audit' in result['features']
    assert 'native_design_reference_comparison' in result['features']
    assert 'unified_design_release_gate' in result['features']


@pytest.mark.parametrize('path', ['/columns', '/missing', '/styles/title', '/html'])
def test_invalid_batch_is_atomic(path):
    draft = sample()
    before = copy.deepcopy(draft)
    with pytest.raises(TobizError):
        prepare(draft, [{'block_id': '3', 'path': '/title', 'value': 'New'},
                        {'block_id': '3', 'path': path, 'value': 'bad'}])
    assert draft == before


def test_hash_and_duplicates():
    draft = sample()
    edit = {'block_id': '3', 'path': '/title', 'value': 'New'}
    with pytest.raises(TobizError):
        prepare(draft, [edit], expected_hash='stale')
    with pytest.raises(TobizError):
        prepare(draft, [edit, edit])
    assert prepare(draft, [], expected_hash=fingerprint(draft))[1] == []


def finish(coroutine):
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    return completed.value.value


def test_preview_then_one_save():
    draft = sample()
    store = DraftStore()
    store.put(draft)
    service = SimpleNamespace(config=SimpleNamespace(read_only=False, dry_run=False),
                              drafts=store, resolve_page=AsyncMock(return_value=('1', None)),
                              draft=AsyncMock(return_value=draft), save_page=AsyncMock(return_value={'status': 'saved'}))
    functions = {}
    class MCP:
        def tool(self, name, description):
            def capture(fn):
                functions[name] = fn
                return fn
            return capture
    register(MCP(), service)
    arguments = dict(project_id='1', page_id='2', expected_hash=fingerprint(draft),
                     edits=[{'block_id': '3', 'path': '/title', 'value': 'New'}])
    result = finish(functions['tobiz_apply_content'](**arguments))
    assert result['ok'] and result['data']['preview']
    assert store.get('1', '2') == draft
    service.save_page.assert_not_called()
    result = finish(functions['tobiz_apply_content'](**arguments, apply=True, save=True))
    assert result['ok'] and result['data']['saved']
    assert store.get('1', '2').blocks['3'].values['title'] == 'New'
    service.save_page.assert_awaited_once()


def test_build_from_template_previews_then_runs_one_save_and_audit():
    source = sample()
    target = copy.deepcopy(source)
    target.project_id, target.page_id = '9', '10'
    store = DraftStore()
    service = SimpleNamespace(
        config=SimpleNamespace(read_only=False, dry_run=False), drafts=store,
        resolve_page=AsyncMock(side_effect=lambda project, page: (
            (str(project), SimpleNamespace(title='Template')))),
        draft=AsyncMock(side_effect=lambda project, page, refresh=False: source if str(page) == '2' else target),
        copy_page=AsyncMock(return_value={'new_project': '9', 'created': [{'page_id': '10', 'url': 'https://x'}]}),
        save_page=AsyncMock(return_value={'saved': True}),
        update_page=AsyncMock(return_value={'applied': {}}),
        inspect_page=AsyncMock(return_value={'url': 'https://x', 'viewports': {}, 'consoleErrors': [], 'pageErrors': []}),
    )
    functions = {}
    class MCP:
        def tool(self, name, description):
            def capture(fn):
                functions[name] = fn
                return fn
            return capture
    register(MCP(), service)
    recipe = {'types': ['130'], 'slots': [{'block_index': 0, 'path': '/title', 'value': 'Built'}]}
    preview = finish(functions['tobiz_build_from_template'](
        source_project_id='1', source_page_id='2', target_project_id='9',
        title='New site', recipe=recipe, replacement_image='gray.png'))
    assert preview['ok'] and preview['data']['preview']
    service.copy_page.assert_not_awaited()
    result = finish(functions['tobiz_build_from_template'](
        source_project_id='1', source_page_id='2', target_project_id='9',
        title='New site', recipe=recipe, replacement_image='gray.png',
        source_terms=['old topic'], seo={'dir': 'new-site'}, apply=True))
    assert result['ok'] and result['data']['audit']['verdict'] == 'ready'
    assert result['data']['quality_score']['overall'] == 10.0
    assert result['data']['quality_score']['meets_7_of_10'] is True
    service.copy_page.assert_awaited_once()
    service.save_page.assert_awaited_once()
    service.inspect_page.assert_awaited_once()


def audit_report(*, overflow=False):
    return {'url': 'https://example.test', 'viewports': {'mobile': {
        'document': {'overflowX': overflow},
        'layout': {'horizontalOverflow': [{'tag': 'div'}] if overflow else [],
                   'blockIssues': [], 'visualIssues': [], 'textContrast': []},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': [], 'integrity': {'issues': []}},
        'interactions': {'broken': [], 'forms': [], 'usabilityIssues': []},
    }}, 'consoleErrors': [], 'pageErrors': []}


def improve_service(draft, reports):
    store = DraftStore()
    store.put(draft)
    return SimpleNamespace(
        config=SimpleNamespace(read_only=False, dry_run=False), drafts=store,
        resolve_page=AsyncMock(return_value=('1', SimpleNamespace(title='Page'))),
        draft=AsyncMock(return_value=draft),
        inspect_page=AsyncMock(side_effect=reports),
        editor_roundtrip=AsyncMock(return_value={'editor_safe': True, 'warnings': []}),
        save_page=AsyncMock(return_value={
            'saved': True, 'backup': {'backup_id': 'before-improve'}}),
        restore_page_backup=AsyncMock(return_value={'restored': True}),
    )


def registered_functions(service):
    functions = {}
    class MCP:
        def tool(self, name, description):
            def capture(fn):
                functions[name] = fn
                return fn
            return capture
    register(MCP(), service)
    return functions


def test_improve_page_previews_safe_native_changes_without_saving():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '165', {'show_vk': 1, 'link_vk': ''}),
    }, order=['1'])
    service = improve_service(draft, [audit_report()])
    functions = registered_functions(service)
    result = finish(functions['tobiz_improve_page'](project_id='1', page_id='2'))
    assert result['ok'] and result['data']['preview']
    assert result['data']['can_apply'] is True
    assert result['data']['safe_changes'][0]['reason'] == 'hide_empty_social'
    service.save_page.assert_not_awaited()


def test_improve_page_applies_one_safe_cycle_and_keeps_editor_safe():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '165', {'show_vk': 1, 'link_vk': ''}),
    }, order=['1'])
    service = improve_service(draft, [audit_report(), audit_report()])
    functions = registered_functions(service)
    result = finish(functions['tobiz_improve_page'](
        project_id='1', page_id='2', apply=True, max_cycles=1))
    data = result['data']
    assert result['ok'] and data['applied'] is True
    assert data['stopped_reason'] == 'target_reached'
    assert data['cycles'][0]['backup']['backup_id'] == 'before-improve'
    assert data['editor_roundtrip']['editor_safe'] is True
    service.save_page.assert_awaited_once()


def test_improve_page_rolls_back_when_score_decreases():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '165', {'show_vk': 1, 'link_vk': ''}),
    }, order=['1'])
    service = improve_service(draft, [audit_report(), audit_report(overflow=True)])
    functions = registered_functions(service)
    result = finish(functions['tobiz_improve_page'](
        project_id='1', page_id='2', apply=True, max_cycles=1))
    data = result['data']
    assert data['rolled_back'] is True
    assert data['applied'] is False
    assert data['stopped_reason'] == 'score_decreased_rolled_back'
    service.restore_page_backup.assert_awaited_once_with(
        '1', '2', 'before-improve', confirm=True)


def layout_audit_report(*, extra_critical=False):
    block_issues = [{"block": "b_1", "code": "card_buttons_misaligned", "difference": 30}]
    if extra_critical:
        block_issues.append({"block": "b_1", "code": "child_outside_container"})
    return {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': block_issues,
                   'visualIssues': [], 'textContrast': [], 'buttonSurfaceContrast': []},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': [], 'integrity': {'issues': []}},
        'interactions': {'broken': [], 'forms': [], 'usabilityIssues': []},
    }}, 'consoleErrors': [], 'pageErrors': []}


def repair_service(draft, reports):
    store = DraftStore()
    store.put(draft)
    block_type = SimpleNamespace(type_id='130', title='Cards', settings=[
        {'name': 'flex_fix', 'type': 'checkbox', 'title': 'Выровнять по кнопке'},
    ])
    return SimpleNamespace(
        config=SimpleNamespace(read_only=False, dry_run=False), drafts=store,
        resolve_page=AsyncMock(return_value=('1', SimpleNamespace(title='Page'))),
        draft=AsyncMock(return_value=draft), block_types=AsyncMock(return_value={'130': block_type}),
        inspect_page=AsyncMock(side_effect=reports),
        editor_roundtrip=AsyncMock(return_value={'editor_safe': True, 'warnings': []}),
        save_page=AsyncMock(return_value={
            'saved': True, 'backup': {'backup_id': 'before-layout-repair'}}),
        restore_page_backup=AsyncMock(return_value={'restored': True}),
    )


def test_repair_layout_previews_native_changes_without_saving():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '130', {'flex_fix': 0}),
    }, order=['1'])
    service = repair_service(draft, [layout_audit_report()])
    functions = registered_functions(service)
    result = finish(functions['tobiz_repair_layout'](project_id='1', page_id='2'))
    data = result['data']
    assert data['preview'] is True and data['can_apply'] is True
    assert data['safe_changes'][0]['path'] == '/flex_fix'
    assert data['affected_type_registry'][0]['type_id'] == '130'
    service.save_page.assert_not_awaited()


def test_repair_layout_applies_and_rolls_back_new_critical_regression():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '130', {'flex_fix': 0}),
    }, order=['1'])
    service = repair_service(draft, [layout_audit_report(), layout_audit_report(extra_critical=True)])
    functions = registered_functions(service)
    result = finish(functions['tobiz_repair_layout'](
        project_id='1', page_id='2', apply=True))
    data = result['data']
    assert data['applied'] is False
    assert data['stopped_reason'] == 'regression_rolled_back'
    assert data['new_critical'][0]['code'] == 'child_outside_container'
    service.restore_page_backup.assert_awaited_once_with(
        '1', '2', 'before-layout-repair', confirm=True)


def design_audit_report(*, system_issue=None):
    visual = [] if not system_issue else [{"code": system_issue}]
    return {'url': 'https://example.test', 'viewports': {'desktop': {
        'document': {'overflowX': False},
        'layout': {'horizontalOverflow': [], 'blockIssues': [], 'visualIssues': visual,
                   'textContrast': [], 'buttonSurfaceContrast': [],
                   'designProfile': {'containerWidths': [1170], 'buttonColors': ['rgb(1,2,3)']}},
        'media': {'brokenImages': [], 'missingAlt': 0},
        'content': {'termMatches': [], 'integrity': {'issues': []}},
        'interactions': {'broken': [], 'forms': [], 'usabilityIssues': []},
    }}, 'consoleErrors': [], 'pageErrors': []}


def test_refine_design_previews_combined_safe_native_changes():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '165', {'show_vk': 1, 'link_vk': ''}),
    }, order=['1'])
    service = repair_service(draft, [design_audit_report()])
    functions = registered_functions(service)
    result = finish(functions['tobiz_refine_design'](project_id='1', page_id='2'))
    data = result['data']
    assert data['preview'] is True and data['can_apply'] is True
    assert data['safe_changes'][0]['reason'] == 'hide_empty_social'
    assert data['design_system']['profiles']['desktop']['containerWidths'] == [1170]
    service.save_page.assert_not_awaited()


def test_refine_design_rolls_back_new_design_system_regression():
    draft = Draft('1', '2', blocks={
        '1': DraftBlock('1', '165', {'show_vk': 1, 'link_vk': ''}),
    }, order=['1'])
    service = repair_service(draft, [
        design_audit_report(), design_audit_report(system_issue='button_palette_inconsistent')])
    functions = registered_functions(service)
    result = finish(functions['tobiz_refine_design'](
        project_id='1', page_id='2', apply=True))
    data = result['data']
    assert data['applied'] is False
    assert data['stopped_reason'] == 'design_regression_rolled_back'
    assert data['design_delta']['introduced'] == ['button_palette_inconsistent']
    service.restore_page_backup.assert_awaited_once_with(
        '1', '2', 'before-layout-repair', confirm=True)
