from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.mcp_client.models import (
    MCPServerConfig,
    MCPToolDefinition,
)
from app.mcp_client.registry import MCPToolRegistry
from app.mcp_client.results import normalize_mcp_result


def make_tool(
    name: str,
) -> MCPToolDefinition:
    return MCPToolDefinition(
        name=name,
        description=f"Test tool: {name}",
        input_schema={
            "type": "object",
        },
        server_name="test-server",
    )


@pytest.mark.anyio
async def test_registry_discovers_tools():
    config = MCPServerConfig(
        name="test-server",
        command="python",
        args=["server.py"],
    )

    registry = MCPToolRegistry(config)

    registry.client.discover_tools = AsyncMock(
        return_value=[
            make_tool("read_file"),
            make_tool("search_text"),
        ]
    )

    tools = await registry.discover()

    assert len(tools) == 2
    assert registry.has_tool("read_file")
    assert registry.has_tool("search_text")


def test_registry_get_tool():
    config = MCPServerConfig(
        name="test-server",
        command="python",
    )

    registry = MCPToolRegistry(config)

    tool = make_tool("read_file")

    registry._tools = {
        tool.name: tool,
    }

    result = registry.get("read_file")

    assert result is tool


def test_registry_unknown_tool():
    config = MCPServerConfig(
        name="test-server",
        command="python",
    )

    registry = MCPToolRegistry(config)

    assert registry.get("unknown") is None
    assert not registry.has_tool("unknown")


@pytest.mark.anyio
async def test_registry_execute_tool():
    config = MCPServerConfig(
        name="test-server",
        command="python",
    )

    registry = MCPToolRegistry(config)

    tool = make_tool("search_text")

    registry._tools = {
        tool.name: tool,
    }

    registry.client.call_tool = AsyncMock(
        return_value="mock-result"
    )

    result = await registry.execute(
        "search_text",
        {
            "query": "LangGraph",
        },
    )

    assert result == "mock-result"

    registry.client.call_tool.assert_awaited_once_with(
        "search_text",
        {
            "query": "LangGraph",
        },
    )


@pytest.mark.anyio
async def test_registry_rejects_unknown_tool():
    config = MCPServerConfig(
        name="test-server",
        command="python",
    )

    registry = MCPToolRegistry(config)

    with pytest.raises(
        ValueError,
        match="has not been discovered",
    ):
        await registry.execute(
            "unknown",
            {},
        )


def test_normalize_mcp_error_result():
    result = type(
        "FakeResult",
        (),
        {
            "is_error": True,
            "content": [],
            "structured_content": None,
        },
    )()

    normalized = normalize_mcp_result(result)

    assert normalized["is_error"] is True
    assert normalized["content"] == []
    assert normalized["structured_content"] is None


def test_normalize_structured_result():
    result = type(
        "FakeResult",
        (),
        {
            "is_error": False,
            "content": [],
            "structured_content": {
                "matches": 3,
            },
        },
    )()

    normalized = normalize_mcp_result(result)

    assert normalized["is_error"] is False
    assert normalized["structured_content"] == {
        "matches": 3,
    }