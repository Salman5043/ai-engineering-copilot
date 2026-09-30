from __future__ import annotations

from app.mcp_client.client import MCPClient
from app.mcp_client.models import (
    MCPServerConfig,
    MCPToolDefinition,
)


async def discover_tools(
    config: MCPServerConfig,
) -> list[MCPToolDefinition]:
    """
    Discover all tools exposed by an MCP server.
    """

    client = MCPClient(config)

    return await client.discover_tools()