"""Assert detection of recurring TOBIZ visual-system regressions."""

from __future__ import annotations

import json
import sys
from pathlib import Path


report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["ok"] is True
issues = report["viewports"]["desktop"]["layout"]["visualIssues"]
codes = {item["code"] for item in issues}
expected = {
    "card_image_ratios_inconsistent",
    "too_many_font_families",
    "text_too_small",
    "excessive_section_gap",
}
assert expected <= codes, f"Visual audit missed: {sorted(expected - codes)}; got {sorted(codes)}"
print(f"Visual consistency regression detection: ready; codes: {sorted(expected)}")
