from __future__ import annotations

from app.mcp_client.models import MCPToolDefinition


def index_mcp_tools(
    tools: list[MCPToolDefinition],
) -> dict[str, MCPToolDefinition]:
    """
    Build a runtime catalog from discovered MCP tools.
    """

    return {
        tool.name: tool
        for tool in tools
    }


def is_mcp_tool(
    tool_name: str,
    catalog: dict[str, MCPToolDefinition],
) -> bool:
    """
    Determine whether a tool was actually discovered
    from an MCP server.
    """

    return tool_name in catalog