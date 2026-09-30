from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.developer_tools.filesystem import RepositoryFileSystem
from app.developer_tools.models import (
    SearchMatch,
    SearchResult,
)


DEFAULT_IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


class RepositorySearch:
    """
    Deterministic text search inside a repository.
    """

    def __init__(self, filesystem: RepositoryFileSystem):
        self.filesystem = filesystem

    def search(
        self,
        query: str,
        max_results: int = 50,
        case_sensitive: bool = False,
    ) -> SearchResult:
        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        if max_results < 1:
            raise ValueError(
                "max_results must be greater than zero."
            )

        matches: list[SearchMatch] = []

        for path in self._iter_files():
            if len(matches) >= max_results:
                break

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            for line_number, line in enumerate(
                content.splitlines(),
                start=1,
            ):
                haystack = line if case_sensitive else line.lower()
                needle = query if case_sensitive else query.lower()

                if needle in haystack:
                    matches.append(
                        SearchMatch(
                            path=path.relative_to(
                                self.filesystem.root
                            ).as_posix(),
                            line=line_number,
                            content=line.strip(),
                        )
                    )

                    if len(matches) >= max_results:
                        break

        return SearchResult(
            query=query,
            matches=matches,
        )

    def _iter_files(self):
        for path in self.filesystem.root.rglob("*"):
            if not path.is_file():
                continue

            if self._is_ignored(path):
                continue

            try:
                if (
                    path.stat().st_size
                    > settings.max_file_size_mb * 1024 * 1024
                ):
                    continue
            except OSError:
                continue

            yield path

    def _is_ignored(self, path: Path) -> bool:
        relative_parts = path.relative_to(
            self.filesystem.root
        ).parts

        return any(
            part in DEFAULT_IGNORED_DIRECTORIES
            for part in relative_parts
        )