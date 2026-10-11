"""Assert that the browser audit catches recurring TOBIZ quality failures."""

from __future__ import annotations

import json
import sys
from pathlib import Path


report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["ok"] is True
mobile = report["viewports"]["mobile"]
assert mobile["document"]["overflowX"] is True
assert mobile["layout"]["textContrast"], "Text contrast regression was missed"
assert mobile["layout"]["buttonSurfaceContrast"], "Button/surface contrast regression was missed"
assert mobile["media"]["brokenImages"], "Broken image regression was missed"
form_codes = {code for form in mobile["interactions"]["forms"] for code in form.get("formIssues", [])}
assert {"missing_lead_name", "lead_name_not_first"} <= form_codes, form_codes
integrity_codes = {item["code"] for item in mobile["content"]["integrity"]["issues"]}
assert {"missing_primary_heading", "thin_page_content", "duplicate_headings", "missing_contact_signal"} <= integrity_codes, integrity_codes
print("Quality regression detection: ready")
