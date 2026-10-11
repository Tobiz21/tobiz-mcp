"""Assert detection of mobile card stacking and clipped content failures."""

from __future__ import annotations

import json
import sys
from pathlib import Path


report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
layout = report["viewports"]["mobile"]["layout"]
block_codes = {item["code"] for item in layout["blockIssues"]}
visual_codes = {item["code"] for item in layout["visualIssues"]}
assert "cards_not_stacked_mobile" in block_codes, block_codes
assert "content_clipped" in visual_codes, visual_codes
issue = next(item for item in layout["blockIssues"] if item["code"] == "cards_not_stacked_mobile")
assert issue["block"] == "b_77"
print("Mobile layout regression detection: ready")
