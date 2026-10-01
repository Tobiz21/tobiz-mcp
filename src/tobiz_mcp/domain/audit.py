"""Turn verbose browser inspection into a short, actionable summary."""


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
        if document.get("overflowX"):
            critical.append({"viewport": name, "code": "horizontal_overflow", "items": overflow})
        if media.get("brokenImages"):
            critical.append({"viewport": name, "code": "broken_images",
                             "items": media["brokenImages"]})
        if content.get("termMatches"):
            critical.append({"viewport": name, "code": "source_content_leftover",
                             "items": content["termMatches"]})
        if (data.get("layout") or {}).get("textContrast"):
            critical.append({"viewport": name, "code": "text_contrast",
                             "items": (data.get("layout") or {})["textContrast"]})
        for issue in (data.get("layout") or {}).get("blockIssues") or []:
            critical.append({"viewport": name, "code": issue.get("code", "block_geometry"),
                             "item": issue})
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
        }
    if report.get("consoleErrors"):
        warnings.append({"code": "console_errors", "count": len(report["consoleErrors"])})
    if report.get("pageErrors"):
        critical.append({"code": "page_errors", "items": report["pageErrors"]})
    verdict = "save_blocked" if critical else "review" if warnings else "ready"
    return {"status": "pass" if not critical else "needs_fix", "verdict": verdict,
            "url": report.get("url"),
            "critical": critical, "warnings": warnings, "viewports": viewports}
