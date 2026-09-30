from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.developer_tools import (
    DEVELOPER_TOOL_NAMES,
    execute_developer_tool,
)
from app.agent.tool_arguments import (
    build_tool_arguments,
)
from app.agent.tool_categories import (
    ALL_AGENT_TOOLS,
    DEVELOPER_TOOLS,
    INVESTIGATION_TOOLS,
)
from app.mcp_server.schemas import (
    ListFilesInput,
    ReadFileInput,
    RepositoryStructureInput,
    SearchTextInput,
)


def test_read_file_schema():
    data = ReadFileInput(
        repository_id="repo",
        path="app/main.py",
        start_line=10,
        end_line=20,
    )

    assert data.repository_id == "repo"
    assert data.path == "app/main.py"
    assert data.start_line == 10
    assert data.end_line == 20


def test_read_file_schema_rejects_empty_path():
    with pytest.raises(ValidationError):
        ReadFileInput(
            repository_id="repo",
            path="",
        )


def test_search_schema_defaults():
    data = SearchTextInput(
        repository_id="repo",
        query="LangGraph",
    )

    assert data.max_results == 50
    assert data.case_sensitive is False


def test_search_schema_limits_results():
    with pytest.raises(ValidationError):
        SearchTextInput(
            repository_id="repo",
            query="test",
            max_results=501,
        )


def test_list_files_schema():
    data = ListFilesInput(
        repository_id="repo",
    )

    assert data.path == "."


def test_repository_structure_schema():
    data = RepositoryStructureInput(
        repository_id="repo",
    )

    assert data.max_files == 1000


def test_developer_tools_are_registered():
    expected = {
        "read_file",
        "list_files",
        "search_text",
        "repository_structure",
    }

    assert expected.issubset(
        DEVELOPER_TOOL_NAMES
    )


def test_tool_categories_are_disjoint():
    assert (
        INVESTIGATION_TOOLS
        & DEVELOPER_TOOLS
    ) == frozenset()


def test_all_agent_tools_are_combined():
    assert (
        ALL_AGENT_TOOLS
        == INVESTIGATION_TOOLS | DEVELOPER_TOOLS
    )


def test_search_text_argument_builder():
    arguments = build_tool_arguments(
        "search_text",
        query="Where is LangGraph used?",
        identifiers=["LangGraph"],
        keywords=["used"],
    )

    assert arguments["query"] == "LangGraph"
    assert arguments["max_results"] == 50


def test_repository_structure_argument_builder():
    arguments = build_tool_arguments(
        "repository_structure",
        query="Show the architecture",
        identifiers=[],
        keywords=[],
    )

    assert arguments == {
        "max_files": 1000,
    }


def test_read_file_requires_explicit_path():
    with pytest.raises(
        ValueError,
        match="explicit repository-relative path",
    ):
        build_tool_arguments(
            "read_file",
            query="read main.py",
            identifiers=[],
            keywords=[],
        )


def test_unknown_tool_argument_builder():
    with pytest.raises(
        ValueError,
        match="No argument builder",
    ):
        build_tool_arguments(
            "unknown_tool",
            query="test",
            identifiers=[],
            keywords=[],
        )


def test_developer_tool_execution_entrypoint_exists():
    assert callable(execute_developer_tool)