from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.mcp_client.models import MCPToolDefinition
from app.mcp_client.registry import MCPToolRegistry


def make_tool(
    name: str,
) -> MCPToolDefinition:
    return MCPToolDefinition(
        name=name,
        description=f"Test tool: {name}",
        input_schema={
            "type": "object",
            "properties": {
                "repository_id": {
                    "type": "string",
                }
            },
        },
        server_name="test-server",
    )


@pytest.mark.anyio
async def test_mcp_registry_caches_discovery():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(
        config
    )

    registry.client.discover_tools = AsyncMock(
        return_value=[
            make_tool("search_text"),
        ]
    )

    first = await registry.discover()
    second = await registry.discover()

    assert first == second

    registry.client.discover_tools.assert_awaited_once()


@pytest.mark.anyio
async def test_mcp_registry_force_refresh():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(
        config
    )

    registry.client.discover_tools = AsyncMock(
        side_effect=[
            [
                make_tool("search_text"),
            ],
            [
                make_tool("search_text"),
                make_tool("repository_structure"),
            ],
        ]
    )

    first = await registry.discover()

    second = await registry.discover(
        force_refresh=True
    )

    assert len(first) == 1
    assert len(second) == 2

    assert (
        registry.client.discover_tools.await_count
        == 2
    )


@pytest.mark.anyio
async def test_mcp_registry_cache_clear():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(
        config
    )

    registry.client.discover_tools = AsyncMock(
        return_value=[
            make_tool("search_text"),
        ]
    )

    await registry.discover()

    assert registry.is_discovered is True
    assert registry.has_tool("search_text")

    registry.clear_cache()

    assert registry.is_discovered is False
    assert not registry.has_tool(
        "search_text"
    )
    assert registry.list_tools() == []


@pytest.mark.anyio
async def test_mcp_registry_get_cached_tool():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(
        config
    )

    tool = make_tool(
        "search_text"
    )

    registry.client.discover_tools = AsyncMock(
        return_value=[tool]
    )

    await registry.discover()

    result = registry.get(
        "search_text"
    )

    assert result is tool


@pytest.mark.anyio
async def test_mcp_registry_unknown_tool_rejected():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(
        config
    )

    with pytest.raises(
        ValueError,
        match="has not been discovered",
    ):
        await registry.execute(
            "unknown_tool",
            {},
        )