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

    Responsibilities:
    - maintain MCP server configuration
    - discover tools
    - cache discovered tools
    - look up tools
    - execute discovered tools
    """

    def __init__(
        self,
        config: MCPServerConfig,
    ) -> None:
        self.config = config
        self.client = MCPClient(config)

        self._tools: dict[str, MCPToolDefinition] = {}
        self._discovered = False

    async def discover(
        self,
        *,
        force_refresh: bool = False,
    ) -> list[MCPToolDefinition]:
        """
        Discover MCP tools.

        Discovery is cached after the first successful call.

        Set force_refresh=True when the MCP server's tool catalog
        may have changed.
        """

        if self._discovered and not force_refresh:
            return self.list_tools()

        tools = await self.client.discover_tools()

        self._tools = {
            tool.name: tool
            for tool in tools
        }

        self._discovered = True

        return tools

    def get(
        self,
        tool_name: str,
    ) -> MCPToolDefinition | None:
        """
        Return a discovered tool by name.
        """

        return self._tools.get(tool_name)

    def list_tools(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Return all currently cached tools.
        """

        return list(self._tools.values())

    def has_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool exists in the cached catalog.
        """

        return tool_name in self._tools

    @property
    def is_discovered(self) -> bool:
        """
        Return True when the MCP tool catalog has been discovered.
        """

        return self._discovered

    def clear_cache(self) -> None:
        """
        Clear the cached MCP tool catalog.
        """

        self._tools.clear()
        self._discovered = False

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute a discovered MCP tool.

        The tool must exist in the discovered catalog before
        execution is allowed.
        """

        if not self.has_tool(tool_name):
            raise ValueError(
                f"MCP tool '{tool_name}' has not been discovered."
            )

        return await self.client.call_tool(
            tool_name,
            arguments or {},
        )
    
    def list_traces(self):
        """
        Return traces recorded by the MCP client.
        """

        return self.client.tracer.list_traces()


    def trace_snapshot(self):
        """
        Return serializable MCP trace records.
        """

        return self.client.tracer.snapshot()


    def clear_traces(self) -> None:
        """
        Clear MCP execution traces.
        """

        self.client.tracer.clear()