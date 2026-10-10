"""Assert that the browser audit catches recurring TOBIZ card-layout failures."""

from __future__ import annotations

import json
import sys
from pathlib import Path


report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["ok"] is True
issues = report["viewports"]["desktop"]["layout"]["blockIssues"]
codes = {item["code"] for item in issues}
expected = {
    "card_heights_misaligned",
    "card_buttons_misaligned",
    "card_button_hidden_initially",
}
missing = expected - codes
assert not missing, f"Layout audit missed regressions: {sorted(missing)}; got {sorted(codes)}"
print(f"Layout regression detection: ready; codes: {sorted(expected)}")
