from __future__ import annotations

from typing import Any, Callable

from app.developer_tools.filesystem import RepositoryFileSystem
from app.developer_tools.repository import RepositoryTools
from app.developer_tools.search import RepositorySearch


DeveloperTool = Callable[..., Any]


def read_file(
    repository_id: str,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
):
    filesystem = RepositoryFileSystem(repository_id)

    return filesystem.read_file(
        relative_path=path,
        start_line=start_line,
        end_line=end_line,
    )


def list_files(
    repository_id: str,
    path: str = ".",
):
    filesystem = RepositoryFileSystem(repository_id)

    return filesystem.list_directory(
        relative_path=path,
    )


def search_text(
    repository_id: str,
    query: str,
    max_results: int = 50,
    case_sensitive: bool = False,
):
    filesystem = RepositoryFileSystem(repository_id)
    searcher = RepositorySearch(filesystem)

    return searcher.search(
        query=query,
        max_results=max_results,
        case_sensitive=case_sensitive,
    )


def repository_structure(
    repository_id: str,
    max_files: int = 1000,
):
    repository = RepositoryTools(repository_id)

    return repository.get_structure(
        max_files=max_files,
    )


DEVELOPER_TOOL_REGISTRY: dict[str, DeveloperTool] = {
    "read_file": read_file,
    "list_files": list_files,
    "search_text": search_text,
    "repository_structure": repository_structure,
}