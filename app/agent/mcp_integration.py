from __future__ import annotations

import asyncio
from typing import Any

from app.mcp_client.models import (
    MCPToolDefinition,
    local_copilot_server_config,
)
from app.mcp_client.registry import MCPToolRegistry
from app.mcp_client.results import normalize_mcp_result


class DynamicMCPTools:
    """
    Bridge between LangGraph and dynamically discovered MCP tools.

    The registry owns tool discovery and caching.
    The adapter provides the interface used by the agent.
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

    async def discover(
        self,
        *,
        force_refresh: bool = False,
    ) -> list[MCPToolDefinition]:
        """
        Discover MCP tools.

        Results are cached by the registry unless
        force_refresh=True.
        """

        return await self.registry.discover(
            force_refresh=force_refresh,
        )

    async def execute(
    self,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
        """
        Execute an MCP tool and normalize the result.

        Preserve structured_content returned by the MCP registry.
        """

        result = await self.registry.execute(
            tool_name,
            arguments,
        )

        normalized = normalize_mcp_result(result)

        if (
            normalized.get("structured_content") is None
            and isinstance(result, dict)
            and "structured_content" in result
        ):
            normalized["structured_content"] = result.get(
                "structured_content"
            )

        return normalized

    def has_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool is currently available
        in the cached catalog.
        """

        return self.registry.has_tool(
            tool_name
        )

    def get_tool(
        self,
        tool_name: str,
    ) -> MCPToolDefinition | None:
        """
        Return a cached tool definition.
        """

        return self.registry.get(
            tool_name
        )

    def list_tools(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Return all currently cached MCP tools.
        """

        return self.registry.list_tools()


def _run_async(
    coroutine: Any,
) -> Any:
    """
    Run an async MCP operation from the synchronous
    LangGraph execution path.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    raise RuntimeError(
        "MCP execution cannot use the synchronous adapter while "
        "an event loop is already running."
    )


def discover_mcp_tools_sync(
    adapter: DynamicMCPTools | None = None,
    *,
    force_refresh: bool = False,
) -> list[MCPToolDefinition]:
    """
    Synchronous entrypoint used by the current LangGraph graph.
    """

    adapter = adapter or DynamicMCPTools()

    return _run_async(
        adapter.discover(
            force_refresh=force_refresh,
        )
    )


def build_mcp_arguments(
    tool: MCPToolDefinition,
    *,
    repository_id: str,
    query: str,
    identifiers: list[str],
    keywords: list[str],
) -> dict[str, Any]:
    """
    Build arguments for a dynamically discovered MCP tool.

    Only arguments supported by the discovered schema are added.
    """

    schema = tool.input_schema or {}

    properties = schema.get(
        "properties",
        {},
    )

    arguments: dict[str, Any] = {}

    identifier = (
        identifiers[0]
        if identifiers
        else query
    )

    if "repository_id" in properties:
        arguments["repository_id"] = repository_id

    if tool.name == "search_text":
        if "query" in properties:
            arguments["query"] = identifier

        if "max_results" in properties:
            arguments["max_results"] = 50

        if "case_sensitive" in properties:
            arguments["case_sensitive"] = False

    elif tool.name == "repository_structure":
        if "max_files" in properties:
            arguments["max_files"] = 1000

    elif tool.name == "list_files":
        if "path" in properties:
            arguments["path"] = "."

    elif tool.name == "read_file":
        raise ValueError(
            "read_file requires an explicit repository-relative path."
        )

    else:
        if "query" in properties:
            arguments["query"] = query

        if "symbol" in properties:
            arguments["symbol"] = identifier

        if "keywords" in properties:
            arguments["keywords"] = keywords

    return arguments


def execute_mcp_tool_sync(
    tool_name: str,
    *,
    repository_id: str,
    query: str,
    identifiers: list[str],
    keywords: list[str],
    adapter: DynamicMCPTools | None = None,
) -> dict[str, Any]:
    """
    Discover and execute one MCP tool from the synchronous
    LangGraph execution path.

    Discovery is cached inside the adapter's registry.
    """

    adapter = adapter or DynamicMCPTools()

    if not adapter.has_tool(tool_name):
        _run_async(
            adapter.discover()
        )

    tool = adapter.get_tool(
        tool_name
    )

    if tool is None:
        raise ValueError(
            f"MCP tool '{tool_name}' was not discovered."
        )

    arguments = build_mcp_arguments(
        tool,
        repository_id=repository_id,
        query=query,
        identifiers=identifiers,
        keywords=keywords,
    )

    return _run_async(
        adapter.execute(
            tool_name,
            arguments,
        )
    )


def mcp_result_to_evidence(
    *,
    result: dict[str, Any],
    tool_name: str,
    repository_id: str,
) -> list[dict[str, Any]]:
    """
    Convert normalized MCP output into evidence-compatible
    dictionaries.
    """

    if result.get("is_error"):
        return []

    evidence: list[dict[str, Any]] = []

    structured_content = result.get(
        "structured_content"
    )

    if isinstance(
        structured_content,
        dict,
    ):
        content = structured_content.get(
            "content",
            structured_content,
        )

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    evidence.append(
                        {
                            **item,
                            "source_tool": tool_name,
                            "repository_id": repository_id,
                        }
                    )

        elif isinstance(content, str):
            evidence.append(
                {
                    "content": content,
                    "source_tool": tool_name,
                    "repository_id": repository_id,
                }
            )

        elif content:
            evidence.append(
                {
                    "content": str(content),
                    "source_tool": tool_name,
                    "repository_id": repository_id,
                }
            )

    for item in result.get(
        "content",
        [],
    ):
        if not isinstance(item, dict):
            continue

        if item.get("type") != "text":
            continue

        text = item.get(
            "text",
            "",
        )

        if not text:
            continue

        evidence.append(
            {
                "content": text,
                "source_tool": tool_name,
                "repository_id": repository_id,
            }
        )

    return evidence