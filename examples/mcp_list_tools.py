"""Smoke test the MCP stdio server by listing exposed tools."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"


async def main() -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_pubmed_evidence.server"],
        env={"PYTHONPATH": str(SRC_DIR)},
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()

    for tool in tools.tools:
        print(tool.name)


if __name__ == "__main__":
    asyncio.run(main())
