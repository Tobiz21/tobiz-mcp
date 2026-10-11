"""Ensure the browser audit leaves a known-good landing page at 10/10."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tobiz_mcp.domain.audit import compact


report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["ok"] is True
summary = compact(report)
assert summary["verdict"] == "ready", summary
assert summary["quality_score"]["overall"] == 10.0, summary["quality_score"]
assert summary["quality_score"]["meets_7_of_10"] is True
assert summary["critical"] == []
assert summary["warnings"] == []
assert summary["fix_plan"] == []
print("Known-good landing page: ready; score: 10.0")
