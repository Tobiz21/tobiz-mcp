from tobiz_mcp.domain.composition import analyze
from tobiz_mcp.domain.draft import Draft, DraftBlock


def page(*texts):
    blocks = {str(index): DraftBlock(str(index), "100", {"title": text})
              for index, text in enumerate(texts, 1)}
    return Draft("1", "2", blocks=blocks, order=list(blocks))


def test_complete_education_story_reaches_target_and_maps_blocks():
    draft = page(
        "Онлайн-школа математики для учеников 2-4 класса",
        "Курсы и программы обучения под разные задачи",
        "Что меняется: ребенок понимает условие и увереннее решает задачи",
        "Как проходит обучение: диагностика, уроки, практика и обратная связь",
        "Об авторе курса: преподаватель с опытом работы более 15 лет",
        "Отзывы родителей, результаты учеников и сертификаты",
        "Часто задаваемые вопросы и ответы",
        "Запишитесь на консультацию и оставьте заявку",
        "Контакты: телефон +7 (999) 123-45-67",
    )
    result = analyze(draft, "education")

    assert result["score"] == 10.0
    assert result["meets_7_of_10"] is True
    assert result["missing_roles"] == []
    assert result["sections"][0]["block_id"] == "1"
    assert result["sections"][0]["role"] == "hero"
    assert result["trust"]["score"] == 10.0


def test_sparse_page_explains_missing_conversion_and_trust_layers():
    result = analyze(page("Мы оказываем качественные услуги"), "lead_generation")

    assert result["meets_7_of_10"] is False
    assert {"proof", "process", "expert", "cta", "contact"} <= set(result["missing_roles"])
    assert result["trust"]["score"] == 0.0
    codes = {item["code"] for item in result["issues"]}
    assert "missing_contact_section" in codes
    assert "missing_cta_section" in codes


def test_composition_ignores_deleted_blocks_and_custom_code_payloads():
    draft = Draft("1", "2", blocks={
        "1": DraftBlock("1", "163", {"title": "Главная услуга", "code": "Отзывы контакты +79991234567"}),
        "2": DraftBlock("2", "100", {"title": "Отзывы клиентов"}, deleted=True),
    }, order=["1", "2"])

    result = analyze(draft)

    assert len(result["sections"]) == 1
    assert "proof" in result["missing_roles"]
    assert "contact" in result["missing_roles"]
