"""Run the deterministic four-workflow TOBIZ release contract."""

import json

from tobiz_mcp.domain.control_scenarios import run


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
