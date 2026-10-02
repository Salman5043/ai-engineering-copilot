from __future__ import annotations

from typing import Any

from app.mcp_client.models import (
    MCPToolDefinition,
    local_copilot_server_config,
)
from app.mcp_client.registry import MCPToolRegistry
from app.mcp_client.results import normalize_mcp_result
from app.mcp_client.tracing import MCPTrace


class MCPAgentTools:
    """
    Adapter between the LangGraph agent and MCP tools.
    """

    def __init__(
        self,
        registry: MCPToolRegistry | None = None,
    ) -> None:
        self.registry = (
            registry
            if registry is not None
            else MCPToolRegistry(
                local_copilot_server_config()
            )
        )

    async def discover_tools(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Discover MCP tools available to the agent.
        """

        return await self.registry.discover()

    def list_tools(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Return currently discovered tools.
        """

        return self.registry.list_tools()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an MCP tool and normalize its result.
        """

        result = await self.registry.execute(
            tool_name,
            arguments,
        )

        return normalize_mcp_result(
            result
        )

    def list_traces(
        self,
    ) -> list[MCPTrace]:
        """
        Return MCP execution traces.
        """

        return self.registry.client.tracer.list_traces()

    def trace_snapshot(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return serializable MCP traces.
        """

        return self.registry.client.tracer.snapshot()

    def clear_traces(self) -> None:
        """
        Clear retained MCP traces.
        """

        self.registry.client.tracer.clear()