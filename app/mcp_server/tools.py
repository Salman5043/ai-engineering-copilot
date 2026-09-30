from __future__ import annotations

from typing import Any

from app.developer_tools.registry import (
    DEVELOPER_TOOL_REGISTRY,
)


def _serialize_result(result: Any) -> Any:
    """
    Convert Pydantic models into plain dictionaries so the
    MCP layer exposes predictable structured data.
    """

    if hasattr(result, "model_dump"):
        return result.model_dump()

    if isinstance(result, list):
        return [
            _serialize_result(item)
            for item in result
        ]

    if isinstance(result, dict):
        return {
            key: _serialize_result(value)
            for key, value in result.items()
        }

    return result


def mcp_read_file(
    repository_id: str,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict[str, Any]:
    """
    Read source code or text from a repository file.
    """

    tool = DEVELOPER_TOOL_REGISTRY["read_file"]

    result = tool(
        repository_id=repository_id,
        path=path,
        start_line=start_line,
        end_line=end_line,
    )

    return _serialize_result(result)


def mcp_list_files(
    repository_id: str,
    path: str = ".",
) -> list[dict[str, Any]]:
    """
    List files and directories inside a repository path.
    """

    tool = DEVELOPER_TOOL_REGISTRY["list_files"]

    result = tool(
        repository_id=repository_id,
        path=path,
    )

    return _serialize_result(result)


def mcp_search_text(
    repository_id: str,
    query: str,
    max_results: int = 50,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """
    Search repository text and return matching files and lines.
    """

    tool = DEVELOPER_TOOL_REGISTRY["search_text"]

    result = tool(
        repository_id=repository_id,
        query=query,
        max_results=max_results,
        case_sensitive=case_sensitive,
    )

    return _serialize_result(result)


def mcp_repository_structure(
    repository_id: str,
    max_files: int = 1000,
) -> dict[str, Any]:
    """
    Inspect the structure of a repository.
    """

    tool = DEVELOPER_TOOL_REGISTRY[
        "repository_structure"
    ]

    result = tool(
        repository_id=repository_id,
        max_files=max_files,
    )

    return _serialize_result(result)