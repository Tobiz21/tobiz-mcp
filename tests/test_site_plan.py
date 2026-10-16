import pytest

from tobiz_mcp.domain import design, site_plan
from tobiz_mcp.domain.content import compact_blueprint, content_map, passport
from tobiz_mcp.domain.draft import Draft, DraftBlock


def draft():
    return Draft('1', '2', blocks={
        '10': DraftBlock('10', '1154', {'title': 'Курс математики', 'bg_image': 'hero.jpg'}),
        '11': DraftBlock('11', '306', {'title': 'Записаться', 'form1': [
            {'type': 'name'}, {'type': 'phone'}, {'type': 'btn'},
        ]}),
    }, order=['10', '11'])


def complete_education_brief():
    return {
        'industry': 'Онлайн-школа математики',
        'audience': 'Родители учеников 2-4 классов',
        'primary_cta': 'Записаться на консультацию',
        'facts': {
            'program': 'Арифметика', 'format': 'Онлайн',
            'teacher': 'Ирина', 'result': 'Самостоятельно решает задачи',
            'phone': '+7 900 000-00-00',
        },
    }


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
    assert first['photo_requirements'][0]['shot_role'] == 'hero'
    assert first['content_brief']['plan_id'] == first['plan_id']
    assert first['content_brief']['ready_for_copywriting'] is False
    assert first['content_brief']['slots'][0]['field_role'] == 'section_title'
    assert first['anchors'] == []


def test_recipe_links_require_existing_native_anchor():
    result = site_plan.validate_recipe_links({'anchors': ['contacts', '#programs']}, {'slots': [
        {'block_index': 0, 'path': '/btn1/link', 'value': '#contacts'},
        {'block_index': 1, 'path': '/btn1/link', 'value': '#missing'},
        {'block_index': 2, 'path': '/btn1/link', 'value': '#'},
        {'block_index': 3, 'path': '/btn1/link', 'value': 'javascript:alert(1)'},
    ]})
    assert result['valid'] is False
    assert result['anchors'] == ['contacts', 'programs']
    assert {item['code'] for item in result['issues']} == {
        'missing_recipe_anchor', 'empty_recipe_anchor', 'unsafe_recipe_link'}
    missing = next(item for item in result['issues']
                   if item['code'] == 'missing_recipe_anchor')
    assert missing['available_anchors'] == ['contacts', 'programs']


def test_seo_alignment_requires_confirmed_topic_and_region():
    result = site_plan.validate_seo_alignment({
        'industry': 'Бурение скважин', 'region': 'Чувашия',
    }, {
        'title': 'Профессиональная помощь',
        'seo_title': 'Надежная компания с большим опытом',
        'seo_description': 'Выполняем работы качественно и в согласованные сроки.',
    })
    assert result['ready'] is False
    assert {item['code'] for item in result['issues']} == {
        'seo_topic_not_grounded', 'seo_region_missing'}


def test_seo_alignment_accepts_inflected_local_topic():
    result = site_plan.validate_seo_alignment({
        'industry': 'Бурение скважин', 'region': 'Чувашия',
    }, {
        'title': 'Бурение скважин в Чувашии',
        'seo_title': 'Бурение скважин под ключ в Чувашии',
        'seo_description': 'Пробурим скважину и подготовим систему водоснабжения.',
    })
    assert result['ready'] is True
    assert result['issues'] == []


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


def test_brief_readiness_returns_only_missing_required_questions():
    result = site_plan.brief_readiness({
        'industry': 'Онлайн-школа математики',
        'facts': {'program': 'Арифметика', 'format': 'Онлайн'},
    })
    assert result['goal'] == 'education'
    assert result['ready_for_quality_build'] is False
    assert [item['code'] for item in result['missing_required']] == [
        'expert', 'result', 'contact']
    assert len(result['questions']) == 3
    assert {item['code'] for item in result['optional_questions']} == {
        'audience', 'primary_cta'}


def test_brief_readiness_accepts_complete_nested_facts():
    result = site_plan.brief_readiness({
        'industry': 'Онлайн-школа математики',
        'audience': 'Родители учеников 2-4 классов',
        'primary_cta': 'Записаться на консультацию',
        'facts': {
            'program': 'Арифметика', 'format': 'Онлайн в группе',
            'teacher': 'Ирина, преподаватель', 'result': 'Решает задачи самостоятельно',
            'phone': '+7 900 000-00-00',
        },
    })
    assert result['ready_for_quality_build'] is True
    assert result['questions'] == []
    assert result['optional_questions'] == []


def test_brief_readiness_rejects_placeholder_and_demo_values():
    result = site_plan.brief_readiness({
        'industry': 'Услуги бурения скважин',
        'facts': {
            'offer': 'Бурение под ключ',
            'region': 'Чувашия',
            'steps': ['Выезд', 'Бурение'],
            'experience': 'клиент исправит позже',
            'contacts': {'phone': '+7 800 333 22 33', 'email': ''},
        },
    })
    missing = {item['code']: item for item in result['missing_required']}
    assert set(missing) == {'expertise', 'contact'}
    assert missing['expertise']['unresolved_fields'] == ['experience']
    assert missing['contact']['unresolved_fields'] == ['contacts']


def test_brief_readiness_accepts_one_real_value_in_nested_contact():
    result = site_plan.brief_readiness({
        'industry': 'Услуги бурения скважин',
        'facts': {
            'offer': 'Бурение под ключ', 'region': 'Чувашия',
            'steps': ['Выезд', 'Бурение'], 'experience': 'Работаем с 2018 года',
            'contacts': {'phone': 'уточнить', 'email': 'hello@company.ru'},
        },
    })
    assert result['ready_for_quality_build'] is True


def test_architecture_readiness_requires_goal_sections_and_trust_layers():
    result = site_plan.architecture_readiness({
        'score': 5.5,
        'present_roles': ['hero', 'programs', 'cta', 'contact'],
    }, 'education')
    assert result['ready'] is False
    assert result['missing_critical_roles'] == ['expert']
    assert result['trust']['sufficient'] is False
    assert {item['code'] for item in result['blockers']} == {
        'critical_sections_missing', 'trust_layers_missing',
        'composition_below_quality_target'}


def test_architecture_readiness_accepts_complete_education_story():
    result = site_plan.architecture_readiness({
        'score': 8.2,
        'present_roles': [
            'hero', 'programs', 'benefits', 'process', 'expert', 'proof', 'cta', 'contact'],
    }, 'education')
    assert result['ready'] is True
    assert result['blockers'] == []


def test_conversion_readiness_accepts_requested_native_form_fields():
    source = Draft('1', '2', blocks={
        '1': DraftBlock('1', '306', {'form1': [
            {'type': 'text', 'title': 'Ваше имя'},
            {'type': 'phone', 'title': 'Телефон'},
            {'type': 'date', 'title': 'Дата мероприятия'},
            {'type': 'number', 'title': 'Количество гостей'},
            {'type': 'btn', 'title': 'Узнать свободное время'},
        ]}),
    }, order=['1'])
    result = site_plan.conversion_readiness(source, {
        'form_fields': ['имя', 'телефон', 'дата', 'количество гостей']})
    assert result['ready'] is True
    assert result['required_fields'] == ['name', 'phone', 'date', 'guests']
    assert result['matching_forms'] == 1


def test_conversion_readiness_rejects_missing_name_button_and_wrong_order():
    source = Draft('1', '2', blocks={
        '1': DraftBlock('1', '306', {'form1': [
            {'type': 'phone', 'title': 'Телефон'},
            {'type': 'text', 'title': 'Ваше имя'},
        ]}),
    }, order=['1'])
    result = site_plan.conversion_readiness(source, {})
    assert result['ready'] is False
    assert {item['code'] for item in result['blockers']} == {
        'form_contract_not_covered', 'lead_form_name_order_invalid'}
    assert result['forms'][0]['has_button'] is False


def test_conversion_readiness_rejects_template_without_native_form():
    source = Draft('1', '2', blocks={
        '1': DraftBlock('1', '1154', {'title': 'Первый экран'}),
    }, order=['1'])
    result = site_plan.conversion_readiness(source, {})
    assert result['ready'] is False
    assert result['blockers'][0]['code'] == 'native_form_missing'


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
            'section_fit_confirmed': True,
        }],
    }, {
        'block_index': 1, 'path_pattern': '/items/0/image', 'assets': [{
            'filename': 'course-1.webp', 'width': 1000, 'height': 1000,
            'subject': 'Тетрадь ученика', 'section_fit_confirmed': True,
        }, {
            'filename': 'course-2.webp', 'width': 1000, 'height': 1000,
            'subject': 'Онлайн-занятие', 'section_fit_confirmed': True,
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
            'background_safe_area_unconfirmed', 'media_subject_missing',
            'media_section_fit_unconfirmed'} <= codes
    assert result['ready_for_build'] is False


def test_media_preflight_blocks_reused_image_inside_card_group():
    blueprint = {'photo_slots': [{
        'block_index': 2, 'path_pattern': '/items/0/image', 'role': 'catalog_image',
        'paths': ['/items/0/image', '/items/1/image'], 'slots': 2,
    }]}
    repeated = {
        'filename': 'same-card.webp', 'width': 1000, 'height': 1000,
        'subject': 'Комплект оборудования на белом фоне',
        'section_fit_confirmed': True,
    }
    result = site_plan.validate_media_recipe({'plan_id': 'media'}, blueprint, {'groups': [{
        'block_index': 2, 'path_pattern': '/items/0/image',
        'assets': [dict(repeated), dict(repeated)],
    }]})
    assert result['ready_for_build'] is False
    issue = next(item for item in result['blockers']
                 if item['code'] == 'media_reused_within_group')
    assert issue['paths'] == ['/items/0/image', '/items/1/image']


def test_media_preflight_detects_same_bytes_under_different_names():
    blueprint = {'photo_slots': [{
        'block_index': 2, 'path_pattern': '/items/0/image', 'role': 'catalog_image',
        'paths': ['/items/0/image', '/items/1/image'], 'slots': 2,
    }]}
    digest = 'a' * 64
    assets = [{
        'filename': filename, 'width': 1000, 'height': 1000, 'sha256': digest,
        'subject': subject, 'section_fit_confirmed': True,
    } for filename, subject in [
        ('card-one.webp', 'Первый комплект оборудования'),
        ('card-two.webp', 'Второй комплект оборудования'),
    ]]
    result = site_plan.validate_media_recipe({'plan_id': 'media'}, blueprint, {'groups': [{
        'block_index': 2, 'path_pattern': '/items/0/image', 'assets': assets,
    }]})
    issue = next(item for item in result['blockers']
                 if item['code'] == 'media_content_reused_under_new_name')
    assert result['ready_for_build'] is False
    assert {item['filename'] for item in issue['uses']} == {
        'card-one.webp', 'card-two.webp'}


def test_unified_preflight_accepts_complete_quality_package():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'price': '6 400 руб.', 'facts': {
        'program': 'Арифметика', 'format': 'Онлайн', 'teacher': 'Ирина, преподаватель',
        'result': 'Самостоятельно решает задачи', 'phone': '+7 900 000-00-00'}}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    plan['architecture_readiness'] = site_plan.architecture_readiness({
        'score': 8.2,
        'present_roles': [
            'hero', 'programs', 'benefits', 'process', 'expert', 'proof', 'cta', 'contact'],
    }, 'education')
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title',
         'value': 'Арифметика онлайн с Ириной: решать задачи самостоятельно',
         'evidence_codes': ['program', 'format', 'expert', 'result']},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    media = {'groups': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'assets': [{
            'filename': 'hero.webp', 'width': 1920, 'height': 1080,
            'subject': 'Урок математики', 'safe_text_area': True,
            'section_fit_confirmed': True,
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
    assert result['evidence_coverage']['missing'] == []


def test_evidence_coverage_reports_confirmed_facts_omitted_from_copy():
    plan = {
        'goal': 'education',
        'brief': {'facts': {
            'program': 'Арифметика', 'format': 'Онлайн', 'teacher': 'Ирина',
            'result': 'Самостоятельно решает задачи', 'phone': '+7 900 000-00-00'}},
        'brief_readiness': {
            'goal': 'education',
            'confirmed_fields': ['program', 'format', 'expert', 'result', 'contact']},
        'conversion_readiness': {'ready': True},
    }
    recipe = {'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Арифметика онлайн',
         'evidence_codes': ['program', 'format']},
    ]}
    result = site_plan.validate_evidence_coverage(plan, recipe)
    assert result['ready'] is False
    assert result['missing'] == ['expert', 'result']
    assert result['issues'][0]['code'] == 'confirmed_evidence_not_used'


def test_evidence_coverage_rejects_unknown_mapping_code():
    result = site_plan.validate_evidence_coverage(
        {'goal': 'lead_generation', 'brief': {'offer': 'Услуга'},
         'brief_readiness': {'goal': 'lead_generation', 'confirmed_fields': ['offer']}},
        {'slots': [{'block_index': 0, 'path': '/title', 'value': 'Услуга',
                    'evidence_codes': ['offer', 'invented_award']}]})
    assert result['ready'] is False
    assert result['covered'] == ['offer']
    assert result['issues'][0]['code'] == 'unknown_evidence_mapping'


def test_evidence_coverage_rejects_label_without_fact_in_copy():
    result = site_plan.validate_evidence_coverage({
        'goal': 'education',
        'brief': {'teacher': 'Ирина Мезенцева'},
        'brief_readiness': {'goal': 'education', 'confirmed_fields': ['expert']},
    }, {'slots': [{
        'block_index': 2, 'path': '/text', 'value': 'Опытный преподаватель',
        'evidence_codes': ['expert'],
    }]})
    assert result['ready'] is False
    assert result['missing'] == ['expert']
    assert result['issues'][-1]['code'] == 'evidence_mapping_not_grounded'


def test_recipe_preflight_includes_evidence_coverage_in_build_verdict():
    source = draft()
    brief = complete_education_brief()
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Арифметика онлайн'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    result = site_plan.validate_recipe(brief, plan, blueprint, recipe)
    assert result['ready_for_build'] is False
    assert 'confirmed_evidence_not_used' in {item['code'] for item in result['blockers']}


def test_recipe_preflight_downgrades_evidence_gap_for_explicit_prototype():
    source = draft()
    brief = {**complete_education_brief(), 'allow_placeholders': True}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Арифметика онлайн'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    result = site_plan.validate_recipe(brief, plan, blueprint, recipe)
    assert result['ready_for_build'] is True
    issue = next(item for item in result['issues']
                 if item['code'] == 'confirmed_evidence_not_used')
    assert issue['priority'] == 'improve'


def test_recipe_preflight_blocks_duplicate_copy_across_sections():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'price': '6 400 руб.'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    repeated = 'Новая программа занятий'
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': repeated},
        {'block_index': 1, 'path': '/title', 'value': repeated},
    ]}
    result = site_plan.validate_recipe(brief, plan, blueprint, recipe)
    issue = next(item for item in result['issues'] if item['code'] == 'duplicate_recipe_copy')
    assert result['ready_for_build'] is False
    assert issue['priority'] == 'must_fix'
    assert len(issue['uses']) == 2


def test_recipe_preflight_allows_repeated_copy_only_in_explicit_prototype():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики', 'price': '6 400 руб.',
             'allow_placeholders': True}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    repeated = 'Новая программа занятий'
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': repeated},
        {'block_index': 1, 'path': '/title', 'value': repeated},
    ]}
    result = site_plan.validate_recipe(brief, plan, blueprint, recipe)
    issue = next(item for item in result['issues'] if item['code'] == 'duplicate_recipe_copy')
    assert issue['priority'] == 'improve'
    assert 'duplicate_recipe_copy' not in {item['code'] for item in result['blockers']}


def test_recipe_preflight_blocks_severely_unbalanced_card_copy():
    blueprint = {'recipe': {'types': ['130'], 'slots': [
        {'block_index': 0, 'path': '/title1', 'kind': 'text',
         'role': 'card_title', 'current': 'Старая карточка 1'},
        {'block_index': 0, 'path': '/title2', 'kind': 'text',
         'role': 'card_title', 'current': 'Старая карточка 2'},
    ]}}
    plan = {'plan_id': 'cards', 'content_brief': {'ready_for_copywriting': True},
            'brief_readiness': {'confirmed_fields': []}}
    recipe = {'types': ['130'], 'slots': [
        {'block_index': 0, 'path': '/title1', 'value': 'Аудит'},
        {'block_index': 0, 'path': '/title2',
         'value': 'Полный технический аудит проекта с подробными рекомендациями'},
    ]}
    result = site_plan.validate_recipe({}, plan, blueprint, recipe)
    issue = next(item for item in result['issues'] if item['code'] == 'unbalanced_card_copy')
    assert result['ready_for_build'] is False
    assert issue['priority'] == 'must_fix'


def test_recipe_preflight_warns_about_unbalanced_cards_in_prototype():
    blueprint = {'recipe': {'types': ['130'], 'slots': [
        {'block_index': 0, 'path': '/title1', 'kind': 'text',
         'role': 'card_title', 'current': 'Старая карточка 1'},
        {'block_index': 0, 'path': '/title2', 'kind': 'text',
         'role': 'card_title', 'current': 'Старая карточка 2'},
    ]}}
    plan = {'plan_id': 'cards', 'content_brief': {'ready_for_copywriting': True},
            'brief_readiness': {'confirmed_fields': []}}
    recipe = {'types': ['130'], 'slots': [
        {'block_index': 0, 'path': '/title1', 'value': 'Аудит'},
        {'block_index': 0, 'path': '/title2',
         'value': 'Полный технический аудит проекта с подробными рекомендациями'},
    ]}
    result = site_plan.validate_recipe({'allow_placeholders': True}, plan, blueprint, recipe)
    issue = next(item for item in result['issues'] if item['code'] == 'unbalanced_card_copy')
    assert issue['priority'] == 'improve'
    assert result['ready_for_build'] is True


def test_recipe_preflight_requires_brief_primary_cta_in_native_button():
    blueprint = {'recipe': {'types': ['306'], 'slots': [{
        'block_index': 0, 'path': '/btn1/title', 'kind': 'text',
        'role': 'button', 'current': 'Отправить',
    }]}}
    plan = {'plan_id': 'cta', 'content_brief': {'ready_for_copywriting': True},
            'brief_readiness': {'confirmed_fields': []}}
    recipe = {'types': ['306'], 'slots': [{
        'block_index': 0, 'path': '/btn1/title', 'value': 'Подробнее',
    }]}
    result = site_plan.validate_recipe(
        {'primary_cta': 'Узнать свободное время'}, plan, blueprint, recipe)
    assert result['ready_for_build'] is False
    assert 'primary_cta_not_used' in {item['code'] for item in result['blockers']}


def test_recipe_preflight_accepts_inflected_primary_cta_wording():
    blueprint = {'recipe': {'types': ['306'], 'slots': [{
        'block_index': 0, 'path': '/btn1/title', 'kind': 'text',
        'role': 'button', 'current': 'Отправить',
    }]}}
    plan = {'plan_id': 'cta', 'content_brief': {'ready_for_copywriting': True},
            'brief_readiness': {'confirmed_fields': []}}
    recipe = {'types': ['306'], 'slots': [{
        'block_index': 0, 'path': '/btn1/title', 'value': 'Записаться на консультацию',
    }]}
    result = site_plan.validate_recipe(
        {'primary_cta': 'Запись на консультацию'}, plan, blueprint, recipe)
    assert result['ready_for_build'] is True
    assert 'primary_cta_not_used' not in {item['code'] for item in result['issues']}


def test_unified_preflight_blocks_incomplete_quality_brief_but_allows_prototype():
    source = draft()
    brief = {'industry': 'Онлайн-школа математики'}
    selection, selected = design.select_native(brief)
    blueprint = compact_blueprint(passport(source), content_map(source))
    plan = site_plan.build(brief, selection, selected, blueprint, source)
    recipe = {'types': ['1154', '306'], 'slots': [
        {'block_index': 0, 'path': '/title', 'value': 'Курс математики'},
        {'block_index': 1, 'path': '/title', 'value': 'Записаться на курс'},
    ]}
    result = site_plan.validate_build_package(brief, plan, blueprint, recipe, None, None)
    assert 'brief_evidence_missing' in {item['code'] for item in result['blockers']}
    assert result['brief_readiness']['ready_for_quality_build'] is False

    prototype_brief = {**brief, 'allow_placeholders': True}
    prototype_plan = site_plan.build(
        prototype_brief, selection, selected, blueprint, source)
    prototype = site_plan.validate_build_package(
        prototype_brief, prototype_plan, blueprint, recipe, None, None)
    assert 'brief_evidence_missing' not in {item['code'] for item in prototype['blockers']}
    assert any(item['code'] == 'brief_evidence_missing' for item in prototype['issues'])
    assert prototype['mode'] == 'prototype'


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
    assert package['gates']['brief'] == plan['brief_readiness']
    assert package['gates']['architecture'] == plan['architecture_readiness']
    assert package['gates']['conversion'] == plan['conversion_readiness']
    assert package['recipe']['types'] == ['1154', '306']
    assert all(slot['value'] == '' for slot in package['recipe']['slots'])
    assert all(slot['evidence_codes'] == [] for slot in package['recipe']['slots'])
    assert package['recipe']['slots'][0]['instruction']
    assert package['media_recipe']['groups'][0]['assets'][0] == {
        'path': '/bg_image', 'filename': '', 'width': 0, 'height': 0,
        'subject': '', 'section_fit_confirmed': False, 'safe_text_area': False,
    }
    assert package['media_recipe']['groups'][0]['section_role'] == 'hero'
    assert package['media_recipe']['groups'][0]['shot_role'] == 'hero'
    assert package['seo']['title'] == 'Онлайн-школа математики'
    assert 'Курс математики' not in str(package['recipe'])


def test_prepare_package_requires_only_primary_catalog_images() -> None:
    package = site_plan.prepare_build_package(
        {'industry': 'Праздники'},
        {'plan_id': 'x', 'template': {}, 'content_brief': {}, 'photo_requirements': []},
        {'recipe': {'types': [], 'slots': []}, 'photo_slots': [{
            'block_index': 3, 'path_pattern': '/arr1/0/image', 'role': 'catalog_image',
            'paths': ['/arr1/0/image', '/arr1/0/image2', '/arr1/0/image3'],
        }]},
    )

    group = package['media_recipe']['groups'][0]
    assert group['required_assets'] == 1
    assert [asset['path'] for asset in group['assets']] == ['/arr1/0/image']


def test_media_validation_ignores_hidden_catalog_alternates() -> None:
    blueprint = {'photo_slots': [{
        'block_index': 3, 'path_pattern': '/arr1/0/image', 'role': 'catalog_image',
        'paths': ['/arr1/0/image', '/arr1/0/image2', '/arr1/0/image3'],
    }]}
    result = site_plan.validate_media_recipe({'plan_id': 'x'}, blueprint, {'groups': [{
        'block_index': 3, 'path_pattern': '/arr1/0/image', 'assets': [{
            'filename': 'event.webp', 'width': 1200, 'height': 1200,
            'subject': 'Гости на празднике', 'section_fit_confirmed': True,
        }],
    }]})

    assert result['ready_for_build'] is True
    assert result['assigned_slots'] == 1


def test_media_validation_blocks_one_photo_reused_across_sections() -> None:
    blueprint = {'photo_slots': [{
        'block_index': 0, 'path_pattern': '/bg_image', 'role': 'background',
        'paths': ['/bg_image'], 'slots': 1,
    }, {
        'block_index': 1, 'path_pattern': '/image', 'role': 'content_image',
        'paths': ['/image'], 'slots': 1,
    }]}
    groups = []
    for index, pattern in ((0, '/bg_image'), (1, '/image')):
        groups.append({
            'block_index': index, 'path_pattern': pattern, 'assets': [{
                'filename': 'same.webp', 'width': 1920, 'height': 1080,
                'subject': 'Преподаватель объясняет материал ученику',
                'safe_text_area': True, 'section_fit_confirmed': True,
            }],
        })
    result = site_plan.validate_media_recipe(
        {'plan_id': 'x'}, blueprint, {'groups': groups})
    assert 'media_reused_across_sections' in {
        item['code'] for item in result['blockers']}


def test_safe_system_title_removes_panel_forbidden_symbols() -> None:
    assert site_plan.safe_system_title('Квест «Темно и весело»!') == 'Квест Темно и весело'


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
        'section_fit_confirmed': True, 'visual_review_notes': 'Кадр подходит первому экрану.',
    }])
    asset = result['package']['media_recipe']['groups'][0]['assets'][0]
    assert result['filled_count'] == 1
    assert asset['filename'] == 'hero.webp'
    assert asset['width'] == 1920
    assert asset['subject'] == 'Учитель объясняет задачу'
    assert asset['safe_text_area'] is True
    assert asset['section_fit_confirmed'] is True
    assert asset['visual_review_notes'] == 'Кадр подходит первому экрану.'
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
        'evidence_codes': ['offer'],
    }], {'dir': 'kurs-matematiki'})
    slot = result['package']['recipe']['slots'][0]
    assert slot['value'] == 'Длинный заголовок'
    assert slot['instruction'] == 'Короткий заголовок'
    assert slot['evidence_codes'] == ['offer']
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
