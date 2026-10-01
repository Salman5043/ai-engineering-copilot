from __future__ import annotations

from typing import Any

from app.mcp_client.client import MCPClient
from app.mcp_client.models import (
    MCPServerConfig,
    MCPToolDefinition,
)


class MCPToolRegistry:
    """
    Runtime registry for tools exposed by MCP servers.

    The registry separates:
    - MCP server connection
    - tool discovery
    - tool lookup
    - tool execution
    """

    def __init__(
        self,
        config: MCPServerConfig,
    ) -> None:
        self.config = config
        self.client = MCPClient(config)
        self._tools: dict[str, MCPToolDefinition] = {}

    async def discover(self) -> list[MCPToolDefinition]:
        """
        Discover tools from the configured MCP server.
        """

        tools = await self.client.discover_tools()

        self._tools = {
            tool.name: tool
            for tool in tools
        }

        return tools

    def get(
        self,
        tool_name: str,
    ) -> MCPToolDefinition | None:
        """
        Return a discovered tool by name.
        """

        return self._tools.get(tool_name)

    def list_tools(self) -> list[MCPToolDefinition]:
        """
        Return all currently discovered tools.
        """

        return list(self._tools.values())

    def has_tool(
        self,
        tool_name: str,
    ) -> bool:
        return tool_name in self._tools

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute a discovered MCP tool.
        """

        if not self.has_tool(tool_name):
            raise ValueError(
                f"MCP tool '{tool_name}' has not been discovered."
            )

        return await self.client.call_tool(
            tool_name,
            arguments or {},
        )