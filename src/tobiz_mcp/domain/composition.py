"""Deterministic page-story and conversion-architecture analysis."""

from __future__ import annotations

import re
from html import unescape
from typing import Any


ROLE_TERMS = {
    "hero": ("главн", "первый экран", "получите", "поможем", "для вашего", "закажите"),
    "offer": ("услуг", "решени", "предлагаем", "что вы получите", "подберем", "программ"),
    "catalog": ("каталог", "товар", "продукц", "модел", "комплект"),
    "programs": ("курс", "тариф", "формат обучения", "программ", "абонемент"),
    "problem": ("проблем", "сложност", "не получается", "ошибк", "боит", "не умеет"),
    "benefits": ("преимуществ", "почему", "выгод", "результат", "что меняется", "получите"),
    "process": ("как проходит", "этап", "шаг", "процесс", "как мы работаем", "схема работ"),
    "expert": ("обо мне", "о компании", "команда", "специалист", "эксперт", "опыт", "лет работы"),
    "proof": ("отзыв", "кейс", "результат", "сертификат", "лиценз", "нам доверяют", "работ"),
    "faq": ("вопрос", "ответ", "часто спрашивают", "faq"),
    "delivery": ("доставк", "оплат", "самовывоз", "гаранти"),
    "cta": ("оставьте заявку", "записаться", "заказать", "получить консультац", "свяжитесь", "рассчитать"),
    "contact": ("контакт", "адрес", "телефон", "как нас найти", "свяжитесь"),
}

GOALS = {
    "lead_generation": ["hero", "offer", "benefits", "process", "expert", "proof", "faq", "cta", "contact"],
    "education": ["hero", "programs", "benefits", "process", "expert", "proof", "faq", "cta", "contact"],
    "ecommerce": ["hero", "catalog", "benefits", "delivery", "proof", "faq", "cta", "contact"],
}

LABELS = {
    "hero": "первый экран", "offer": "предложение", "catalog": "каталог",
    "programs": "программы или тарифы", "problem": "проблема клиента",
    "benefits": "выгоды и результат", "process": "процесс", "expert": "экспертность",
    "proof": "доказательства и доверие", "faq": "ответы на вопросы",
    "delivery": "доставка и оплата", "cta": "призыв к действию", "contact": "контакты",
    "content": "содержательный блок",
}


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _text_values(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in {"cache", "styles", "css", "code", "html", "form_html"}:
                continue
            yield from _text_values(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from _text_values(child, key)
    elif isinstance(value, str) and not re.search(
            r"(?:image|img|icon|video|link|url|color|font|anchor|class|style)", key, re.I):
        plain = _plain(value)
        if plain:
            yield plain


def _has_form(values: dict[str, Any]) -> bool:
    return any(isinstance(value, list) and key.startswith("form")
               for key, value in values.items())


def _has_phone(text: str) -> bool:
    return bool(re.search(r"(?:\+7|8)[\s(\-]*\d{3}", text))


def _classify(text: str, *, position: int, has_form: bool, has_phone: bool) -> tuple[str, list[str]]:
    normalized = text.lower().replace("ё", "е")
    scores = {role: sum(1 for term in terms if term in normalized)
              for role, terms in ROLE_TERMS.items()}
    if position == 0:
        scores["hero"] += 2
    if has_form:
        scores["cta"] += 2
    if has_phone:
        scores["contact"] += 2
    matched = sorted((role for role, score in scores.items() if score),
                     key=lambda role: (-scores[role], role))
    return (matched[0] if matched else "content"), matched


def analyze(draft, goal: str = "lead_generation") -> dict[str, Any]:
    if goal not in GOALS:
        raise ValueError(f"Unsupported composition goal: {goal}")
    sections = []
    for position, block_id in enumerate(draft.order):
        block = draft.blocks[block_id]
        if block.deleted:
            continue
        parts = list(_text_values(block.values))
        text = " ".join(parts)
        form = _has_form(block.values)
        phone = _has_phone(text)
        role, signals = _classify(text, position=len(sections), has_form=form, has_phone=phone)
        sections.append({
            "position": len(sections), "block_id": str(block_id), "type_id": str(block.type_id),
            "role": role, "label": LABELS[role], "signals": signals[:4],
            "text_chars": len(text), "has_form": form, "has_phone": phone,
        })

    required = GOALS[goal]
    present = {signal for section in sections for signal in section["signals"]}
    missing = [role for role in required if role not in present]
    observed = [section["role"] for section in sections if section["role"] in required]
    observed_unique = list(dict.fromkeys(observed))
    desired_index = {role: index for index, role in enumerate(required)}
    inversions = sum(
        desired_index[left] > desired_index[right]
        for index, left in enumerate(observed_unique)
        for right in observed_unique[index + 1:]
    )
    possible = len(observed_unique) * (len(observed_unique) - 1) // 2
    order_score = 1.0 if not possible else max(0.0, 1 - inversions / possible)
    coverage = (len(required) - len(missing)) / len(required)
    score = round((coverage * .75 + order_score * .25) * 10, 1)

    issues = []
    if not sections:
        issues.append({"code": "empty_page", "priority": "must_fix",
                       "action": "Добавить штатные блоки TOBIZ по выбранной структуре."})
    if sections and sections[0]["role"] != "hero":
        issues.append({"code": "weak_first_screen", "priority": "must_fix",
                       "block_id": sections[0]["block_id"],
                       "action": "На первом экране ясно назвать предложение, аудиторию и следующее действие."})
    for role in missing:
        priority = "must_fix" if role in {"hero", "offer", "programs", "catalog", "cta", "contact"} else "improve"
        issues.append({"code": f"missing_{role}_section", "priority": priority,
                       "role": role, "label": LABELS[role],
                       "action": f"Раскрыть «{LABELS[role]}» штатным блоком существующей структуры."})
    if inversions:
        issues.append({"code": "story_order_inconsistent", "priority": "improve",
                       "action": "Переставить существующие блоки по рекомендуемой смысловой последовательности."})
    short_blocks = [section["block_id"] for section in sections
                    if section["role"] not in {"hero", "cta", "contact"}
                    and section["text_chars"] < 80]
    if short_blocks:
        issues.append({"code": "thin_sections", "priority": "improve",
                       "block_ids": short_blocks,
                       "action": "Добавить конкретику в короткие секции без изменения их штатной структуры."})

    trust_roles = {"expert", "proof", "process", "contact"}
    trust_present = sorted(trust_roles & present)
    return {
        "goal": goal, "score": score, "target": 7.0, "meets_7_of_10": score >= 7 and not any(
            issue["priority"] == "must_fix" for issue in issues),
        "coverage": round(coverage, 3), "order_score": round(order_score, 3),
        "sections": sections, "present_roles": sorted(present),
        "missing_roles": missing, "issues": issues,
        "recommended_order": [{"role": role, "label": LABELS[role]} for role in required],
        "trust": {"present": trust_present, "missing": sorted(trust_roles - present),
                  "score": round(len(trust_present) / len(trust_roles) * 10, 1)},
        "rule": "Анализ не добавляет код и не меняет страницу; рекомендации реализуются штатными блоками TOBIZ.",
    }
