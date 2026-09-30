from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools import (
    mcp_list_files,
    mcp_read_file,
    mcp_repository_structure,
    mcp_search_text,
)


mcp = FastMCP(
    "AI Engineering Copilot",
)


@mcp.tool()
def read_file(
    repository_id: str,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict:
    """
    Read a file from a repository.

    The path is always resolved relative to the selected
    repository and cannot escape the repository boundary.
    """

    return mcp_read_file(
        repository_id=repository_id,
        path=path,
        start_line=start_line,
        end_line=end_line,
    )


@mcp.tool()
def list_files(
    repository_id: str,
    path: str = ".",
) -> list[dict]:
    """
    List files and directories in a repository path.
    """

    return mcp_list_files(
        repository_id=repository_id,
        path=path,
    )


@mcp.tool()
def search_text(
    repository_id: str,
    query: str,
    max_results: int = 50,
    case_sensitive: bool = False,
) -> dict:
    """
    Search for text throughout a repository.
    """

    return mcp_search_text(
        repository_id=repository_id,
        query=query,
        max_results=max_results,
        case_sensitive=case_sensitive,
    )


@mcp.tool()
def repository_structure(
    repository_id: str,
    max_files: int = 1000,
) -> dict:
    """
    Inspect repository files and directories.
    """

    return mcp_repository_structure(
        repository_id=repository_id,
        max_files=max_files,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")