from __future__ import annotations

INVESTIGATION_TOOLS = frozenset(
    {
        "repository_search",
        "symbol_search",
        "reference_search",
        "test_search",
        "configuration_search",
        "entrypoint_search",
    }
)


DEVELOPER_TOOLS = frozenset(
    {
        "read_file",
        "list_files",
        "search_text",
        "repository_structure",
    }
)


ALL_AGENT_TOOLS = (
    INVESTIGATION_TOOLS
    | DEVELOPER_TOOLS
)