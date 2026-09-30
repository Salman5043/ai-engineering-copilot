from __future__ import annotations

from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp_client.models import (
    MCPServerConfig,
    MCPToolDefinition,
)


class MCPClient:
    """
    Lightweight MCP client for connecting to an MCP server
    over stdio and discovering its tools.
    """

    def __init__(
        self,
        config: MCPServerConfig,
    ) -> None:
        self.config = config

    def _server_parameters(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env,
        )

    async def discover_tools(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Connect to the MCP server and discover all available tools.
        """

        server_parameters = self._server_parameters()

        async with stdio_client(
            server_parameters
        ) as (read, write):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                response = await session.list_tools()

                return [
                    MCPToolDefinition.from_mcp_tool(
                        tool,
                        server_name=self.config.name,
                    )
                    for tool in response.tools
                ]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Call a discovered MCP tool.
        """

        server_parameters = self._server_parameters()

        async with stdio_client(
            server_parameters
        ) as (read, write):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                return await session.call_tool(
                    tool_name,
                    arguments or {},
                )