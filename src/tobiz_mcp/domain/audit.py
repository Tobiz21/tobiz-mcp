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
            if form.get("issues"):
                target = critical if form.get("visible") else warnings
                target.append({"viewport": name, "code": "form_contrast",
                               "visible": bool(form.get("visible")), "issues": form["issues"]})
                form_issues.extend(form["issues"])
        if document.get("overflowX") or overflow:
            critical.append({"viewport": name, "code": "horizontal_overflow", "items": overflow})
        if media.get("brokenImages"):
            critical.append({"viewport": name, "code": "broken_images",
                             "items": media["brokenImages"]})
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
    return {"status": "pass" if not critical else "needs_fix", "url": report.get("url"),
            "critical": critical, "warnings": warnings, "viewports": viewports}
