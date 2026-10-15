"""Turn verbose browser inspection into a short, actionable summary."""


TECHNICAL = {
    "horizontal_overflow", "broken_images", "page_errors", "console_errors",
    "child_outside_container", "footer_columns_stacked_desktop", "block_geometry",
    "cards_not_stacked_mobile",
}
CONTENT = {
    "source_content_leftover", "missing_primary_heading", "multiple_primary_headings",
    "thin_page_content", "duplicate_headings", "missing_contact_signal", "missing_alt",
    "heading_level_skipped", "missing_primary_action", "editorial_copy",
}
USABILITY = {
    "form_contrast", "lead_form_structure", "missing_anchor", "no_action",
    "broken_interaction", "card_button_hidden_initially", "inactive_optional_link",
    "field_missing_accessible_label", "tap_target_too_small", "accordion_control_broken",
}

CRITICAL_VISUAL = {"text_over_image_without_scrim"}

FIXES = {
    "horizontal_overflow": "Исправить ширину или позиционирование элементов на мобильном экране.",
    "broken_images": "Заменить битые изображения штатными файлами TOBIZ.",
    "text_contrast": "Выбрать контрастный цвет текста относительно фактического фона.",
    "button_surface_contrast": "Отделить заливку кнопки от фона секции.",
    "lead_form_structure": "Поставить поле «Имя» перед полем «Телефон» штатной настройкой формы.",
    "form_contrast": "Исправить цвета подписей, полей и кнопки формы.",
    "source_content_leftover": "Заменить остатки текста исходного шаблона.",
    "missing_anchor": "Перевязать кнопку на существующий блок или штатную попап-форму.",
    "card_heights_misaligned": "Включить штатное выравнивание карточек по высоте.",
    "card_buttons_misaligned": "Включить штатную опцию «Выровнять по кнопке».",
    "card_button_hidden_initially": "Отключить появление кнопки только при наведении.",
    "card_button_alignment_mismatch": "Согласовать выравнивание текста и кнопки карточки.",
    "thin_page_content": "Раскрыть предложение, процесс, доказательства и следующий шаг.",
    "missing_contact_signal": "Добавить реальный телефон или email в контакты и подвал.",
    "duplicate_headings": "Убрать повтор заголовков и развести смысл секций.",
    "too_many_font_families": "Оставить не более трех согласованных семейств шрифтов.",
    "text_too_small": "Увеличить основной текст минимум до 12px.",
    "card_image_ratios_inconsistent": "Привести изображения одной группы карточек к общей пропорции.",
    "excessive_section_gap": "Убрать случайный двойной отступ между секциями.",
    "image_aspect_distorted": "Сохранить пропорции изображения через штатный режим кадрирования.",
    "image_low_resolution": "Заменить растянутое изображение файлом достаточного разрешения.",
    "image_crop_extreme": "Выбрать кадр подходящей ориентации или ослабить штатное кадрирование.",
    "image_reused_across_sections": "Заменить повторяющееся фото в одной из смысловых секций.",
    "text_over_image_without_scrim": "Включить штатное затемнение фонового фото для читаемости текста.",
    "image_semantic_mismatch": "Заменить фото на сюжет, соответствующий ближайшему тексту и роли секции.",
    "hero_background_too_dark": "Ослабить затемнение первого экрана, чтобы объект бизнеса читался.",
    "gallery_caption_too_long": "Сократить подпись галереи до одной короткой мысли.",
    "accordion_control_broken": "Привязать вопрос FAQ к существующему штатному ответу.",
    "adjacent_photo_backgrounds": "Разделить два фотофона спокойным штатным блоком с однотонным фоном.",
    "section_color_striping": "Сократить число случайно чередующихся фоновых цветов.",
    "editorial_copy": "Заменить служебный текст для дизайнера на клиентскую пользу и атмосферу.",
    "content_clipped": "Увеличить высоту или сократить содержимое штатными настройками блока.",
    "cards_not_stacked_mobile": "Включить штатное мобильное складывание карточек в одну колонку.",
    "container_widths_inconsistent": "Привести случайные ширины контейнеров к основной сетке страницы.",
    "button_palette_inconsistent": "Оставить один основной и один дополнительный цвет кнопок.",
    "button_radii_inconsistent": "Унифицировать радиусы кнопок в штатных настройках блоков.",
    "heading_alignment_inconsistent": "Согласовать выравнивание заголовков с композицией страницы.",
    "field_missing_accessible_label": "Добавить полю понятную подпись или placeholder.",
    "tap_target_too_small": "Увеличить мобильную кнопку минимум до 44x44px.",
    "heading_level_skipped": "Исправить последовательность уровней H1-H6.",
    "missing_primary_action": "Добавить понятное основное действие штатной кнопкой TOBIZ.",
}


def _dimension(code):
    if code in TECHNICAL:
        return "technical"
    if code in CONTENT:
        return "content"
    if code in USABILITY:
        return "usability"
    return "visual"


def _score(critical, warnings, advisory_codes):
    dimensions = {name: 10.0 for name in ("technical", "visual", "content", "usability")}
    seen = set()
    for severity, items in (("critical", critical), ("warning", warnings)):
        for item in items:
            code = item.get("code", "unknown")
            dimension = _dimension(code)
            key = (severity, dimension, code)
            if key in seen:
                continue
            seen.add(key)
            penalty = 3.0 if severity == "critical" else .25 if code in advisory_codes else 1.25
            dimensions[dimension] = max(0.0, dimensions[dimension] - penalty)
    overall = round(sum(dimensions.values()) / len(dimensions), 1)
    if critical:
        overall = min(overall, 4.9)
    return {
        "overall": overall,
        "dimensions": {name: round(value, 1) for name, value in dimensions.items()},
        "target": 7.0,
        "meets_7_of_10": overall >= 7.0 and not critical,
        "method": "Unique issue codes are deducted once across viewports; critical issues cap overall at 4.9.",
    }


def _fix_plan(critical, warnings, limit=8):
    result, seen = [], set()
    for severity, items in (("critical", critical), ("warning", warnings)):
        for item in items:
            code = item.get("code", "unknown")
            if code in seen:
                continue
            seen.add(code)
            blocks = []
            raw = item.get("item") or item
            block = raw.get("block")
            if block:
                blocks.append(str(block).removeprefix("b_"))
            for nested in item.get("items") or []:
                nested_block = nested.get("block") if isinstance(nested, dict) else None
                if nested_block:
                    blocks.append(str(nested_block).removeprefix("b_"))
            for nested in raw.get("blocks") or []:
                nested_block = nested.get("block") if isinstance(nested, dict) else None
                if nested_block:
                    blocks.append(str(nested_block).removeprefix("b_"))
            result.append({
                "priority": "must_fix" if severity == "critical" else "improve",
                "dimension": _dimension(code),
                "code": code,
                "action": FIXES.get(code, "Проверить элемент на desktop и mobile и исправить штатными настройками TOBIZ."),
                "block_ids": sorted(set(blocks)),
            })
            if len(result) >= limit:
                return result
    return result


def compact(report):
    critical, warnings, viewports = [], [], {}
    for name, data in (report.get("viewports") or {}).items():
        document = data.get("document") or {}
        overflow = [
            item for item in (data.get("layout") or {}).get("horizontalOverflow", [])
            if item.get("tag") != "canvas"
        ]
        media = data.get("media") or {}
        content = data.get("content") or {}
        interactions = data.get("interactions") or {}
        broken = []
        for item in interactions.get("broken") or []:
            classes = set(item.get("classes") or [])
            if item.get("issue") == "no_action" and (
                    "ymaps-2-1-79-copyright__logo" in classes or any(c.startswith("sn-") for c in classes)):
                warnings.append({"viewport": name, "code": "inactive_optional_link",
                                 "text": item.get("text", ""), "classes": sorted(classes)})
            else:
                broken.append(item)
        form_issues = []
        for form in interactions.get("forms") or []:
            issues = [
                issue for issue in (form.get("issues") or [])
                if not (issue.get("tag") == "input"
                        and set(issue.get("issues") or []) == {"not_visible"})
            ]
            if issues:
                target = critical if form.get("visible") else warnings
                target.append({"viewport": name, "code": "form_contrast",
                               "visible": bool(form.get("visible")), "issues": issues})
                form_issues.extend(issues)
            semantic_issues = form.get("formIssues") or []
            if semantic_issues:
                target = critical if form.get("visible") else warnings
                target.append({"viewport": name, "code": "lead_form_structure",
                               "visible": bool(form.get("visible")), "issues": semantic_issues})
                form_issues.extend(semantic_issues)
            for issue in form.get("accessibilityIssues") or []:
                warnings.append({"viewport": name, **issue})
        for issue in interactions.get("usabilityIssues") or []:
            warnings.append({"viewport": name, **issue})
        if document.get("overflowX"):
            critical.append({"viewport": name, "code": "horizontal_overflow", "items": overflow})
        if media.get("brokenImages"):
            critical.append({"viewport": name, "code": "broken_images",
                             "items": media["brokenImages"]})
        if content.get("termMatches"):
            critical.append({"viewport": name, "code": "source_content_leftover",
                             "items": content["termMatches"]})
        for issue in (content.get("integrity") or {}).get("issues") or []:
            warnings.append({"viewport": name, **issue})
        if (data.get("layout") or {}).get("textContrast"):
            critical.append({"viewport": name, "code": "text_contrast",
                             "items": (data.get("layout") or {})["textContrast"]})
        if (data.get("layout") or {}).get("buttonSurfaceContrast"):
            critical.append({"viewport": name, "code": "button_surface_contrast",
                             "items": (data.get("layout") or {})["buttonSurfaceContrast"]})
        for issue in (data.get("layout") or {}).get("blockIssues") or []:
            critical.append({"viewport": name, "code": issue.get("code", "block_geometry"),
                             "item": issue})
        for issue in (data.get("layout") or {}).get("visualIssues") or []:
            target = critical if issue.get("code") in CRITICAL_VISUAL else warnings
            target.append({"viewport": name, **issue})
        for item in broken:
            critical.append({"viewport": name, "code": item.get("issue", "broken_interaction"),
                             "item": item})
        missing_alt = int(media.get("missingAlt") or 0)
        if missing_alt:
            warnings.append({"viewport": name, "code": "missing_alt", "count": missing_alt})
        viewports[name] = {
            "overflow_x": bool(document.get("overflowX")),
            "broken_images": len(media.get("brokenImages") or []),
            "broken_interactions": len(broken),
            "form_issues": len(form_issues),
            "screenshot": data.get("screenshot"),
            "design_profile": (data.get("layout") or {}).get("designProfile") or {},
        }
    if report.get("consoleErrors"):
        warnings.append({"code": "console_errors", "count": len(report["consoleErrors"])})
    if report.get("pageErrors"):
        critical.append({"code": "page_errors", "items": report["pageErrors"]})
    advisory_codes = {"missing_alt", "inactive_optional_link"}
    actionable_warnings = [item for item in warnings if item.get("code") not in advisory_codes]
    verdict = "save_blocked" if critical else "review" if actionable_warnings else "ready"
    quality_score = _score(critical, warnings, advisory_codes)
    evidence = {}
    for severity, items in (("critical", critical), ("warning", warnings)):
        for item in items:
            raw = item.get("item") or item
            targets = ([raw] + [nested for nested in item.get("items") or []
                                if isinstance(nested, dict)]
                       + [nested for nested in raw.get("blocks") or []
                          if isinstance(nested, dict)])
            for target in targets:
                block = target.get("block")
                if not block:
                    continue
                block_id = str(block).removeprefix("b_")
                record = {"severity": severity, "viewport": item.get("viewport"),
                          "code": item.get("code"), "details": target}
                if record not in evidence.setdefault(block_id, []):
                    evidence[block_id].append(record)
    return {"status": "pass" if not critical else "needs_fix", "verdict": verdict,
            "url": report.get("url"),
            "quality_score": quality_score,
            "fix_plan": _fix_plan(critical, warnings),
            "block_evidence": evidence,
            "critical": critical, "warnings": warnings, "viewports": viewports}
