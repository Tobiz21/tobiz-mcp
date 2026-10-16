"""Opt-in authenticated read-only contract test against a dedicated TOBIZ page."""

from __future__ import annotations

import asyncio
import json
import os

from tobiz_mcp.config import Config
from tobiz_mcp.service import Service


async def main() -> None:
    project_id = os.environ["TOBIZ_LIVE_TEST_PROJECT_ID"]
    page_id = os.environ["TOBIZ_LIVE_TEST_PAGE_ID"]
    service = Service(Config.from_env())
    try:
        await service.login(force=True)
        resolved, page = await service.resolve_page(project_id, page_id)
        draft = await service.draft(resolved, page_id, refresh=True)
        types = await service.block_types(resolved)
        roundtrip = await service.editor_roundtrip(resolved, page_id)
        report = await service.inspect_page(
            resolved, page_id, screenshot=False,
            viewports=["desktop", "tablet", "mobile"])
        missing_types = sorted({block.type_id for block in draft.blocks.values()} - set(types))
        result = {
            "project_id": resolved, "page_id": page.page_id,
            "blocks": len(draft.order), "catalog_types": len(types),
            "missing_types": missing_types,
            "editor_safe": bool(roundtrip.get("editor_safe")),
            "viewports": sorted((report.get("viewports") or {}).keys()),
            "page_errors": len(report.get("pageErrors") or []),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        assert not missing_types
        assert result["editor_safe"]
        assert result["viewports"] == ["desktop", "mobile", "tablet"]
        assert result["page_errors"] == 0
    finally:
        await service.aclose()


if __name__ == "__main__":
    asyncio.run(main())
