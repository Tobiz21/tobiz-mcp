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
