from __future__ import annotations

from typing import Any

from app.developer_tools.registry import (
    DEVELOPER_TOOL_REGISTRY,
)


def execute_developer_tool(
    tool_name: str,
    *,
    repository_id: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    """
    Execute one developer tool through the shared registry.

    This function is intentionally independent of MCP and LangGraph.
    """

    if tool_name not in DEVELOPER_TOOL_REGISTRY:
        raise ValueError(
            f"Unknown developer tool: {tool_name}"
        )

    arguments = arguments or {}

    tool = DEVELOPER_TOOL_REGISTRY[tool_name]

    return tool(
        repository_id=repository_id,
        **arguments,
    )


DEVELOPER_TOOL_NAMES = frozenset(
    DEVELOPER_TOOL_REGISTRY.keys()
)