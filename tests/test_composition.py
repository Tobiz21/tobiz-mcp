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


def test_native_header_before_hero_is_not_a_weak_first_screen():
    draft = Draft("1", "2", blocks={
        "header": DraftBlock("header", "105", {
            "logo": "logo.png", "menu1": [{"title": "Программы"}], "fixed": 1,
        }),
        "hero": DraftBlock("hero", "1154", {
            "title": "Праздник под ключ для вашей компании",
            "subtitle": "Квест, музыка и ведущий в одном сценарии",
        }),
    }, order=["header", "hero"])

    result = analyze(draft)

    assert result["sections"][0]["role"] == "header"
    assert result["sections"][0]["fixed"] is True
    assert result["sections"][1]["role"] == "hero"
    assert "weak_first_screen" not in {item["code"] for item in result["issues"]}


def test_composition_detects_editorial_copy_and_adjacent_photo_backgrounds():
    draft = Draft("1", "2", blocks={
        "hero": DraftBlock("hero", "1154", {
            "title": "Праздник под ключ", "bg_image": "hero.jpg",
        }),
        "gallery": DraftBlock("gallery", "100", {
            "title": "10 новых кадров в единой стилистике",
            "background_image": "gallery.jpg",
        }),
    }, order=["hero", "gallery"])

    result = analyze(draft)
    codes = {item["code"] for item in result["issues"]}

    assert "editorial_copy" in codes
    assert "adjacent_photo_backgrounds" in codes


def test_faq_is_a_valid_neutral_separator_between_photo_backgrounds():
    draft = Draft("1", "2", blocks={
        "hero": DraftBlock("hero", "1154", {"title": "Главная услуга", "bg_image": "a.jpg"}),
        "faq": DraftBlock("faq", "100", {"title": "Часто задаваемые вопросы и ответы"}),
        "place": DraftBlock("place", "100", {"title": "Как нас найти", "bg_image": "b.jpg"}),
    }, order=["hero", "faq", "place"])

    result = analyze(draft)

    assert "adjacent_photo_backgrounds" not in {item["code"] for item in result["issues"]}


def test_landing_story_accepts_header_hero_offer_gallery_process_cta_faq_location_footer():
    draft = Draft("1", "2", blocks={
        "h": DraftBlock("h", "105", {"logo": "logo.png", "menu1": []}),
        "hero": DraftBlock("hero", "1", {"title": "Праздник под ключ", "bg_image": "hero.jpg"}),
        "offer": DraftBlock("offer", "2", {"title": "Что вы получите: квест и ведущего"}),
        "gallery": DraftBlock("gallery", "3", {"title": "Атмосфера праздника", "gallery": ["1.jpg"]}),
        "process": DraftBlock("process", "4", {"title": "Как проходит мероприятие: четыре этапа"}),
        "cta": DraftBlock("cta", "5", {"title": "Оставьте заявку", "form1": [{"type": "phone"}]}),
        "faq": DraftBlock("faq", "6", {"title": "Часто задаваемые вопросы и ответы"}),
        "location": DraftBlock("location", "7", {"title": "Как нас найти: адрес и карта", "bg_image": "place.jpg"}),
        "footer": DraftBlock("footer", "8", {"title": "Контакты", "phone": "+7 (900) 000-00-00"}),
    }, order=["h", "hero", "offer", "gallery", "process", "cta", "faq", "location", "footer"])

    result = analyze(draft)
    codes = {item["code"] for item in result["issues"]}

    assert result["sections"][0]["role"] == "header"
    assert "weak_first_screen" not in codes
    assert "adjacent_photo_backgrounds" not in codes
