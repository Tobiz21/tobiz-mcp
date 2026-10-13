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
