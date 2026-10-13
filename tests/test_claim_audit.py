from tobiz_mcp.domain.claim_audit import analyze
from tobiz_mcp.domain.draft import Draft, DraftBlock


def page():
    return Draft('1', '2', blocks={
        '10': DraftBlock('10', '1154', {
            'title': 'Скидка 30% до конца месяца',
            'text1': 'Стоимость 6 400 руб. Опыт работы 12 лет.',
            'phone1': '+7 (900) 123-45-67',
        }),
    }, order=['10'])


def test_claim_audit_blocks_values_absent_from_brief():
    result = analyze(page(), {'offer': 'Курс математики'})
    assert result['ready'] is False
    assert {item['code'] for item in result['issues']} == {
        'unsupported_discount_claim', 'unsupported_price_claim',
        'unsupported_experience_claim', 'unsupported_phone_claim'}


def test_claim_audit_accepts_exact_facts_from_nested_brief():
    brief = {'facts': {'discount': '30%', 'price': '6 400 руб.',
                       'experience': '12 лет опыта работы',
                       'phone': '+7 900 123-45-67'}}
    result = analyze(page(), brief)
    assert result['ready'] is True
    assert result['unsupported'] == 0
    assert result['supported'] == 4
