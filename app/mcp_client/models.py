from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPServerConfig:
    """
    Configuration required to launch/connect to an MCP server.
    """

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


@dataclass(frozen=True)
class MCPToolDefinition:
    """
    Normalized representation of an MCP tool.

    This keeps raw MCP SDK objects isolated from the
    rest of the application.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

    title: str | None = None

    @classmethod
    def from_mcp_tool(
        cls,
        tool: Any,
        *,
        server_name: str,
    ) -> "MCPToolDefinition":
        return cls(
            name=tool.name,
            description=tool.description or "",
            input_schema=dict(tool.inputSchema),
            server_name=server_name,
            title=getattr(tool, "title", None),
        )


def local_copilot_server_config() -> MCPServerConfig:
    """
    Return the configuration for the local
    AI Engineering Copilot MCP server.
    """

    return MCPServerConfig(
        name="ai-engineering-copilot",
        command="uv",
        args=[
            "run",
            "python",
            "-m",
            "app.mcp_server.server",
        ],
    )