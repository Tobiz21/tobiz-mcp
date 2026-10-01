import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain.content import content_map, fingerprint, passport, prepare
from tobiz_mcp.domain.audit import compact
from tobiz_mcp.domain.draft import Draft, DraftBlock, DraftStore
from tobiz_mcp.errors import TobizError
from tobiz_mcp.tools import register
from tobiz_mcp.domain.content import recipe_edits
from tobiz_mcp.domain.template import prepare_template


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


@pytest.mark.asyncio
async def test_preview_then_one_save():
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
    result = await functions['tobiz_apply_content'](**arguments)
    assert result['ok'] and result['data']['preview']
    assert store.get('1', '2') == draft
    service.save_page.assert_not_called()
    result = await functions['tobiz_apply_content'](**arguments, apply=True, save=True)
    assert result['ok'] and result['data']['saved']
    assert store.get('1', '2').blocks['3'].values['title'] == 'New'
    service.save_page.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_from_template_previews_then_runs_one_save_and_audit():
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
    preview = await functions['tobiz_build_from_template'](
        source_project_id='1', source_page_id='2', target_project_id='9',
        title='New site', recipe=recipe, replacement_image='gray.png')
    assert preview['ok'] and preview['data']['preview']
    service.copy_page.assert_not_awaited()
    result = await functions['tobiz_build_from_template'](
        source_project_id='1', source_page_id='2', target_project_id='9',
        title='New site', recipe=recipe, replacement_image='gray.png',
        source_terms=['old topic'], seo={'dir': 'new-site'}, apply=True)
    assert result['ok'] and result['data']['audit']['verdict'] == 'ready'
    service.copy_page.assert_awaited_once()
    service.save_page.assert_awaited_once()
    service.inspect_page.assert_awaited_once()
