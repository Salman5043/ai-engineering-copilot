from __future__ import annotations

import pytest

from app.mcp_client.client import MCPClient
from app.mcp_client.discovery import discover_tools
from app.mcp_client.models import (
    MCPServerConfig,
    MCPToolDefinition,
    local_copilot_server_config,
)


def test_mcp_server_config():
    config = local_copilot_server_config()

    assert config.name == "ai-engineering-copilot"
    assert config.command == "uv"
    assert "app.mcp_server.server" in config.args


def test_mcp_tool_definition():
    tool = type(
        "FakeTool",
        (),
        {
            "name": "read_file",
            "description": "Read a repository file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repository_id": {
                        "type": "string",
                    },
                },
            },
            "title": "Read File",
        },
    )()

    definition = MCPToolDefinition.from_mcp_tool(
        tool,
        server_name="test-server",
    )

    assert definition.name == "read_file"
    assert definition.description == "Read a repository file."
    assert definition.server_name == "test-server"
    assert definition.title == "Read File"
    assert definition.input_schema["type"] == "object"


def test_mcp_tool_definition_handles_missing_description():
    tool = type(
        "FakeTool",
        (),
        {
            "name": "list_files",
            "description": None,
            "inputSchema": {
                "type": "object",
            },
        },
    )()

    definition = MCPToolDefinition.from_mcp_tool(
        tool,
        server_name="test-server",
    )

    assert definition.name == "list_files"
    assert definition.description == ""
    assert definition.title is None


def test_mcp_client_initializes():
    config = MCPServerConfig(
        name="test-server",
        command="uv",
        args=["run", "python", "-m", "example.server"],
    )

    client = MCPClient(config)

    assert client.config == config


def test_mcp_server_parameters():
    config = MCPServerConfig(
        name="test-server",
        command="python",
        args=["server.py"],
        env={"TEST_MODE": "1"},
    )

    client = MCPClient(config)

    params = client._server_parameters()

    assert params.command == "python"
    assert params.args == ["server.py"]
    assert params.env == {"TEST_MODE": "1"}


@pytest.mark.anyio
async def test_discover_local_mcp_tools():
    config = local_copilot_server_config()

    tools = await discover_tools(config)

    tool_names = {
        tool.name
        for tool in tools
    }

    assert "read_file" in tool_names
    assert "list_files" in tool_names
    assert "search_text" in tool_names
    assert "repository_structure" in tool_names


@pytest.mark.anyio
async def test_discovered_tools_have_schemas():
    config = local_copilot_server_config()

    tools = await discover_tools(config)

    assert tools

    for tool in tools:
        assert tool.name
        assert tool.server_name == "ai-engineering-copilot"
        assert isinstance(tool.input_schema, dict)