from __future__ import annotations

from typing import Any


def build_tool_arguments(
    tool_name: str,
    *,
    query: str,
    identifiers: list[str],
    keywords: list[str],
) -> dict[str, Any]:
    """
    Build arguments for an agent tool from investigation state.
    """

    identifier = identifiers[0] if identifiers else query

    if tool_name == "repository_search":
        return {
            "query": query,
            "top_k": 5,
        }

    if tool_name == "symbol_search":
        return {
            "symbol": identifier,
            "top_k": 5,
        }

    if tool_name == "reference_search":
        return {
            "symbol": identifier,
            "top_k": 10,
        }

    if tool_name == "test_search":
        return {
            "query": identifier,
            "top_k": 10,
        }

    if tool_name == "configuration_search":
        return {
            "query": query,
            "top_k": 10,
        }

    if tool_name == "entrypoint_search":
        return {
            "query": query,
            "top_k": 10,
        }

    if tool_name == "search_text":
        return {
            "query": identifier,
            "max_results": 50,
            "case_sensitive": False,
        }

    if tool_name == "repository_structure":
        return {
            "max_files": 1000,
        }

    # These require a concrete file path that cannot safely
    # be inferred from the natural-language query alone.
    if tool_name == "read_file":
        raise ValueError(
            "read_file requires an explicit repository-relative path."
        )

    if tool_name == "list_files":
        return {
            "path": ".",
        }

    raise ValueError(
        f"No argument builder exists for tool: {tool_name}"
    )