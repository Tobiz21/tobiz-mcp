"""Assert page-wide design-system inconsistency detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path


report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
layout = report["viewports"]["desktop"]["layout"]
codes = {item["code"] for item in layout["visualIssues"]}
expected = {"container_widths_inconsistent", "button_palette_inconsistent",
            "button_radii_inconsistent", "heading_alignment_inconsistent"}
assert expected <= codes, f"Missing {sorted(expected - codes)}; got {sorted(codes)}"
profile = layout["designProfile"]
assert len(profile["containerWidths"]) >= 4
assert len(profile["buttonColors"]) == 4
assert len(profile["buttonRadii"]) == 4
print("Design-system regression detection: ready")
