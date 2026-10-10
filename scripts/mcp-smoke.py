"""Offline MCP protocol smoke test used by public-image CI."""

from __future__ import annotations

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REQUIRED_TOOLS = {
    "tobiz_onboarding_check",
    "tobiz_list_projects",
    "tobiz_list_pages",
    "tobiz_page_summary",
    "tobiz_update_block",
    "tobiz_save_page",
    "tobiz_audit_page",
    "tobiz_editor_roundtrip_check",
}


async def smoke() -> None:
    server = StdioServerParameters(
        command="python",
        args=["-m", "tobiz_mcp"],
        env={
            "TOBIZ_READ_ONLY": "0",
            "TOBIZ_REQUIRE_PROJECT_ALLOWLIST": "true",
            "TOBIZ_ALLOWED_PROJECT_IDS": "999999999",
            "TOBIZ_LOG_LEVEL": "WARNING",
        },
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()

    names = {tool.name for tool in tools.tools}
    missing = REQUIRED_TOOLS - names
    assert not missing, f"Missing required MCP tools: {sorted(missing)}"
    assert initialized.server_info.name == "tobiz-mcp"
    assert len(names) >= 40, f"Unexpectedly small tool set: {len(names)}"
    print(f"MCP handshake: ready; tools: {len(names)}")


if __name__ == "__main__":
    asyncio.run(smoke())
