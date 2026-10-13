import pytest

from tobiz_mcp.domain import design, site_plan
from tobiz_mcp.domain.content import compact_blueprint, content_map, passport
from tobiz_mcp.domain.draft import Draft, DraftBlock


def draft():
    return Draft('1', '2', blocks={
        '10': DraftBlock('10', '1154', {'title': 'Курс математики', 'bg_image': 'hero.jpg'}),
        '11': DraftBlock('11', '306', {'title': 'Записаться', 'form1': [{'type': 'phone'}]}),
    }, order=['10', '11'])


def test_plan_is_deterministic_and_uses_native_slots():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'goal': 'Запись на курс'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    first = site_plan.build(brief, selection, selected, blueprint, source)
    second = site_plan.build(brief, selection, selected, blueprint, source)
    assert first['plan_id'] == second['plan_id']
    assert first['goal'] == 'education'
    assert first['structure_locked'] is True
    assert first['photo_requirements'][0]['orientation'] == 'wide'
    assert first['content_brief']['plan_id'] == first['plan_id']
    assert first['content_brief']['ready_for_copywriting'] is False
    assert first['content_brief']['slots'][0]['field_role'] == 'section_title'


def test_content_compiler_requires_evidence_and_accepts_nested_facts():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'facts': {
        'program': ['Задачи и арифметика'], 'format': 'Онлайн', 'teacher': 'Ирина, преподаватель',
        'result': 'Самостоятельно решает задачи', 'phone': '+7 900 000-00-00'}}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    manifest = site_plan.compile_content_brief(brief, plan)
    assert manifest['ready_for_copywriting'] is True
    assert manifest['missing_evidence'] == []
    assert 'prices and discounts' in manifest['prohibited_inventions']


def test_plan_comparison_detects_structure_and_role_drift():
    source = draft()
    plan = {'plan_id': 'x', 'sections': [
        {'type_id': '1154', 'role': 'hero'}, {'type_id': '306', 'role': 'cta'}]}
    matching = {'sections': [{'role': 'hero'}, {'role': 'cta'}]}
    assert site_plan.compare(plan, source, matching)['matches'] is True
    source.order.reverse()
    result = site_plan.compare(plan, source, {'sections': [{'role': 'cta'}, {'role': 'hero'}]})
    assert {item['code'] for item in result['issues']} == {'plan_structure_drift', 'plan_role_drift'}


def test_recipe_preflight_blocks_unsupported_claim_before_copy():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'goal': 'Запись на курс'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Курс за 6 400 руб.'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    result = site_plan.validate_recipe(brief, plan, blueprint, recipe)
    assert result['ready_for_build'] is False
    assert 'unsupported_price_claim' in {item['code'] for item in result['blockers']}


def test_recipe_preflight_accepts_supported_claim_and_complete_structure():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'price': '6 400 руб.'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Курс за 6 400 руб.'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    result = site_plan.validate_recipe(brief, plan, blueprint, recipe)
    assert result['ready_for_build'] is True
    assert result['claims']['unsupported'] == 0


def test_media_preflight_accepts_complete_high_resolution_assignment():
    plan = {'plan_id': 'media-plan'}
    blueprint = {'photo_slots': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'role': 'background',
        'paths': ['/bg_image'], 'slots': 1,
    }, {
        'block_index': 1, 'path_pattern': '/items/0/image', 'role': 'catalog_image',
        'paths': ['/items/0/image', '/items/1/image'], 'slots': 2,
    }]}
    media_recipe = {'groups': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'assets': [{
            'filename': 'hero.webp', 'width': 1920, 'height': 1080,
            'subject': 'Учитель у доски', 'safe_text_area': True,
        }],
    }, {
        'block_index': 1, 'path_pattern': '/items/0/image', 'assets': [{
            'filename': 'course-1.webp', 'width': 1000, 'height': 1000,
            'subject': 'Тетрадь ученика',
        }, {
            'filename': 'course-2.webp', 'width': 1000, 'height': 1000,
            'subject': 'Онлайн-занятие',
        }],
    }]}
    result = site_plan.validate_media_recipe(plan, blueprint, media_recipe)
    assert result['ready_for_build'] is True
    assert result['assigned_slots'] == 3
    merged = site_plan.merge_media_recipe({'types': ['1'], 'slots': []}, result)
    assert merged['slots'][0] == {
        'block_index': 0, 'path': '/bg_image', 'value': 'hero.webp'}


def test_media_preflight_blocks_placeholders_bad_ratio_and_missing_safe_area():
    blueprint = {'photo_slots': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'role': 'background',
        'paths': ['/bg_image'], 'slots': 1,
    }]}
    result = site_plan.validate_media_recipe({'plan_id': 'x'}, blueprint, {'groups': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'assets': [{
            'filename': 'gray-placeholder.png', 'width': 800, 'height': 1200,
            'subject': '',
        }],
    }]})
    codes = {item['code'] for item in result['blockers']}
    assert {'media_placeholder_used', 'media_resolution_too_low', 'background_not_wide',
            'background_safe_area_unconfirmed'} <= codes
    assert result['ready_for_build'] is False


def test_unified_preflight_accepts_complete_quality_package():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'price': '6 400 руб.'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Курс за 6 400 руб.'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    media = {'groups': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'assets': [{
            'filename': 'hero.webp', 'width': 1920, 'height': 1080,
            'subject': 'Урок математики', 'safe_text_area': True,
        }],
    }]}
    seo = {
        'title': 'Онлайн-курс математики для школьников',
        'dir': 'kurs-matematiki',
        'seo_title': 'Онлайн-курс математики для школьников',
        'seo_description': ('Курс математики для школьников с понятной программой, практическими '
                            'занятиями и последовательной подготовкой к самостоятельному решению задач.'),
    }
    result = site_plan.validate_build_package(brief, plan, blueprint, recipe, media, seo)
    assert result['ready_for_build'] is True
    assert result['mode'] == 'quality'
    assert result['next_action'] == 'build'


def test_unified_preflight_blocks_missing_seo_and_unsafe_link():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Курс математики'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться'},
        {'block_index': 1, 'path': '/link', 'value': 'javascript:alert(1)'},
    ]}
    result = site_plan.validate_build_package(brief, plan, blueprint, recipe, None, None)
    codes = {item['code'] for item in result['blockers']}
    assert {'media_recipe_missing', 'seo_package_missing', 'unsafe_recipe_link'} <= codes
    assert result['ready_for_build'] is False


def test_prepare_package_returns_clean_exact_fill_in_contract():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    package = site_plan.prepare_build_package(brief, plan, blueprint)
    assert package['schema_version'] == 1
    assert package['brief'] == brief
    assert package['package_id'] == f"{plan['plan_id']}:v1"
    assert package['recipe']['types'] == ['1154', '306']
    assert all(slot['value'] == '' for slot in package['recipe']['slots'])
    assert package['recipe']['slots'][0]['instruction']
    assert package['media_recipe']['groups'][0]['assets'][0] == {
        'path': '/bg_image', 'filename': '', 'width': 0, 'height': 0,
        'subject': '', 'safe_text_area': False,
    }
    assert package['seo']['title'] == 'Онлайн-школа математики'
    assert 'Курс математики' not in str(package['recipe'])


def test_package_envelope_rejects_stale_plan_and_template():
    plan = {'plan_id': 'fresh', 'template': {'project_id': '1', 'page_id': '2'}}
    valid = {'schema_version': 1, 'package_id': 'fresh:v1', 'plan_id': 'fresh',
             'template': {'project_id': '1', 'page_id': '2'}}
    assert site_plan.validate_package_envelope(valid, plan)['valid'] is True
    stale = {**valid, 'package_id': 'old:v1', 'plan_id': 'old',
             'template': {'project_id': '1', 'page_id': '9'}}
    result = site_plan.validate_package_envelope(stale, plan)
    assert result['valid'] is False
    assert {item['code'] for item in result['blockers']} == {
        'package_plan_mismatch', 'package_identity_mismatch', 'package_template_mismatch'}


def test_fill_package_media_returns_new_package_with_verified_metadata():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    package = site_plan.prepare_build_package(brief, plan, blueprint)
    result = site_plan.fill_package_media(package, [{
        'block_index': 0, 'path_pattern': '/bg_image', 'asset_index': 0,
        'media_asset': {'filename': 'hero.webp', 'width': 1920, 'height': 1080,
                        'aspect_ratio': 1.7778, 'content_type': 'image/webp'},
        'subject': 'Учитель объясняет задачу', 'safe_text_area': True,
    }])
    asset = result['package']['media_recipe']['groups'][0]['assets'][0]
    assert result['filled_count'] == 1
    assert asset['filename'] == 'hero.webp'
    assert asset['width'] == 1920
    assert asset['subject'] == 'Учитель объясняет задачу'
    assert asset['safe_text_area'] is True
    assert package['media_recipe']['groups'][0]['assets'][0]['filename'] == ''


def test_fill_package_media_rejects_unknown_slot():
    with pytest.raises(ValueError, match='Unknown media group'):
        site_plan.fill_package_media({'media_recipe': {'groups': []}}, [{
            'block_index': 9, 'path_pattern': '/image', 'asset_index': 0,
            'media_asset': {'filename': 'photo.jpg'},
        }])


def test_fill_package_content_preserves_contract_and_warns_on_long_copy():
    package = {'recipe': {'slots': [{
        'block_index': 0, 'path': '/title', 'value': '', 'recommended_max_chars': 8,
        'instruction': 'Короткий заголовок',
    }]}, 'seo': {'title': '', 'dir': '', 'seo_title': '', 'seo_description': ''}}
    result = site_plan.fill_package_content(package, [{
        'block_index': 0, 'path': '/title', 'value': 'Длинный заголовок',
    }], {'dir': 'kurs-matematiki'})
    slot = result['package']['recipe']['slots'][0]
    assert slot['value'] == 'Длинный заголовок'
    assert slot['instruction'] == 'Короткий заголовок'
    assert result['package']['seo']['dir'] == 'kurs-matematiki'
    assert result['warnings'][0]['code'] == 'copy_exceeds_mobile_limit'
    assert package['recipe']['slots'][0]['value'] == ''


def test_fill_package_content_rejects_duplicate_and_unknown_fields():
    package = {'recipe': {'slots': [{'block_index': 0, 'path': '/title', 'value': ''}]}}
    duplicate = [
        {'block_index': 0, 'path': '/title', 'value': 'Один'},
        {'block_index': 0, 'path': '/title', 'value': 'Два'},
    ]
    with pytest.raises(ValueError, match='Duplicate content slot'):
        site_plan.fill_package_content(package, duplicate)
    with pytest.raises(ValueError, match='Unknown SEO fields'):
        site_plan.fill_package_content(package, [], {'keywords': 'математика'})


def test_package_progress_returns_exact_resume_action_and_missing_targets():
    package = {
        'recipe': {'slots': [
            {'block_index': 0, 'path': '/title', 'role': 'title', 'value': 'Курс'},
            {'block_index': 1, 'path': '/text', 'role': 'body', 'value': ''},
        ]},
        'media_recipe': {'groups': [{
            'block_index': 0, 'path_pattern': '/image', 'role': 'image',
            'assets': [{'path': '/image', 'filename': ''}],
        }]},
        'seo': {'title': 'Курс математики', 'dir': '', 'seo_title': '', 'seo_description': ''},
    }
    result = site_plan.package_progress(package, {'ready_for_build': False, 'blockers': [
        {'code': 'recipe_slot_missing'}, {'code': 'recipe_slot_missing'},
    ]})
    assert result['completion_percent'] == 29
    assert result['content']['missing'][0]['path'] == '/text'
    assert result['media']['missing'][0]['asset_index'] == 0
    assert result['seo']['missing'] == ['dir', 'seo_title', 'seo_description']
    assert result['blocker_codes'] == {'recipe_slot_missing': 2}
    assert result['next_action'] == 'tobiz_fill_package_content'


def test_package_progress_moves_to_build_when_complete():
    package = {'recipe': {'slots': [{'block_index': 0, 'path': '/title', 'value': 'Курс'}]},
               'media_recipe': {'groups': []},
               'seo': {'title': 'Заголовок', 'dir': 'kurs', 'seo_title': 'SEO',
                       'seo_description': 'Описание'}}
    result = site_plan.package_progress(package, {'ready_for_build': True, 'blockers': []})
    assert result['completion_percent'] == 100
    assert result['next_action'] == 'tobiz_build_site_package'
