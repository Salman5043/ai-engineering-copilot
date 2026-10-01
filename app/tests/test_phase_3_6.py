from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.mcp_catalog import (
    index_mcp_tools,
    is_mcp_tool,
)
from app.agent.mcp_integration import (
    DynamicMCPTools,
    build_mcp_arguments,
    mcp_result_to_evidence,
)
from app.mcp_client.models import MCPToolDefinition
from app.mcp_client.registry import MCPToolRegistry


def make_tool(
    name: str,
    properties: dict,
) -> MCPToolDefinition:
    return MCPToolDefinition(
        name=name,
        description=f"Test MCP tool: {name}",
        input_schema={
            "type": "object",
            "properties": properties,
        },
        server_name="test-server",
    )


def test_mcp_catalog_indexes_discovered_tools():
    tools = [
        make_tool(
            "search_text",
            {
                "repository_id": {"type": "string"},
                "query": {"type": "string"},
            },
        ),
        make_tool(
            "repository_structure",
            {
                "repository_id": {"type": "string"},
            },
        ),
    ]

    catalog = index_mcp_tools(tools)

    assert "search_text" in catalog
    assert "repository_structure" in catalog


def test_mcp_catalog_only_accepts_discovered_tools():
    tools = [
        make_tool(
            "search_text",
            {
                "repository_id": {"type": "string"},
            },
        )
    ]

    catalog = index_mcp_tools(tools)

    assert is_mcp_tool(
        "search_text",
        catalog,
    )

    assert not is_mcp_tool(
        "unknown_tool",
        catalog,
    )


def test_build_search_text_arguments():
    tool = make_tool(
        "search_text",
        {
            "repository_id": {
                "type": "string",
            },
            "query": {
                "type": "string",
            },
            "max_results": {
                "type": "integer",
            },
            "case_sensitive": {
                "type": "boolean",
            },
        },
    )

    arguments = build_mcp_arguments(
        tool,
        repository_id="demo",
        query="Where is LangGraph created?",
        identifiers=["build_graph"],
        keywords=["LangGraph"],
    )

    assert arguments == {
        "repository_id": "demo",
        "query": "build_graph",
        "max_results": 50,
        "case_sensitive": False,
    }


def test_build_repository_structure_arguments():
    tool = make_tool(
        "repository_structure",
        {
            "repository_id": {
                "type": "string",
            },
            "max_files": {
                "type": "integer",
            },
        },
    )

    arguments = build_mcp_arguments(
        tool,
        repository_id="demo",
        query="architecture",
        identifiers=[],
        keywords=[],
    )

    assert arguments == {
        "repository_id": "demo",
        "max_files": 1000,
    }


def test_build_list_files_arguments():
    tool = make_tool(
        "list_files",
        {
            "repository_id": {
                "type": "string",
            },
            "path": {
                "type": "string",
            },
        },
    )

    arguments = build_mcp_arguments(
        tool,
        repository_id="demo",
        query="files",
        identifiers=[],
        keywords=[],
    )

    assert arguments == {
        "repository_id": "demo",
        "path": ".",
    }


def test_read_file_requires_explicit_path():
    tool = make_tool(
        "read_file",
        {
            "repository_id": {
                "type": "string",
            },
            "path": {
                "type": "string",
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="explicit repository-relative path",
    ):
        build_mcp_arguments(
            tool,
            repository_id="demo",
            query="read file",
            identifiers=[],
            keywords=[],
        )


def test_mcp_result_to_evidence():
    result = {
        "is_error": False,
        "content": [
            {
                "type": "text",
                "text": "app/graph.py contains build_graph",
            }
        ],
        "structured_content": None,
    }

    evidence = mcp_result_to_evidence(
        result=result,
        tool_name="search_text",
        repository_id="demo",
    )

    assert len(evidence) == 1
    assert evidence[0]["content"] == (
        "app/graph.py contains build_graph"
    )
    assert evidence[0]["source_tool"] == "search_text"
    assert evidence[0]["repository_id"] == "demo"


def test_mcp_error_result_produces_no_evidence():
    result = {
        "is_error": True,
        "content": [],
        "structured_content": None,
    }

    evidence = mcp_result_to_evidence(
        result=result,
        tool_name="search_text",
        repository_id="demo",
    )

    assert evidence == []


@pytest.mark.anyio
async def test_dynamic_mcp_tools_discover():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(config)

    expected = [
        make_tool(
            "search_text",
            {
                "repository_id": {
                    "type": "string",
                }
            },
        )
    ]

    registry.discover = AsyncMock(
        return_value=expected
    )

    adapter = DynamicMCPTools(
        registry=registry
    )

    tools = await adapter.discover()

    assert len(tools) == 1
    assert tools[0].name == "search_text"


@pytest.mark.anyio
async def test_dynamic_mcp_tools_execute():
    config = type(
        "FakeConfig",
        (),
        {},
    )()

    registry = MCPToolRegistry(config)

    registry.execute = AsyncMock(
        return_value={
            "is_error": False,
            "content": [],
            "structured_content": {
                "matches": 2,
            },
        }
    )

    adapter = DynamicMCPTools(
        registry=registry
    )

    result = await adapter.execute(
        "search_text",
        {
            "repository_id": "demo",
            "query": "LangGraph",
        },
    )

    assert result["is_error"] is False
    assert result["structured_content"] == {
        "matches": 2,
    }

    registry.execute.assert_awaited_once_with(
        "search_text",
        {
            "repository_id": "demo",
            "query": "LangGraph",
        },
    )