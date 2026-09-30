from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.developer_tools.models import (
    FileEntry,
    ReadFileResult,
)


class RepositoryFileSystem:
    """
    Safe filesystem access scoped to one repository.

    All file operations are restricted to the configured
    repository root.
    """

    def __init__(self, repository_id: str):
        if not repository_id:
            raise ValueError("repository_id is required.")

        self.repository_id = repository_id

        base_root = Path(settings.repository_root).resolve()
        repository_root = (base_root / repository_id).resolve()

        if not repository_root.exists():
            raise FileNotFoundError(
                f"Repository not found: {repository_id}"
            )

        if not repository_root.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {repository_id}"
            )

        self.base_root = base_root
        self.root = repository_root

    def resolve_path(self, relative_path: str = ".") -> Path:
        """
        Resolve a repository-relative path safely.

        Raises:
            ValueError: if the path escapes the repository.
        """

        if not relative_path:
            relative_path = "."

        candidate = (self.root / relative_path).resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(
                "Path escapes repository boundary."
            ) from exc

        return candidate

    def list_directory(
        self,
        relative_path: str = ".",
    ) -> list[FileEntry]:
        directory = self.resolve_path(relative_path)

        if not directory.exists():
            raise FileNotFoundError(
                f"Path not found: {relative_path}"
            )

        if not directory.is_dir():
            raise NotADirectoryError(
                f"Path is not a directory: {relative_path}"
            )

        entries: list[FileEntry] = []

        for item in sorted(
            directory.iterdir(),
            key=lambda path: (not path.is_dir(), path.name.lower()),
        ):
            relative = item.relative_to(self.root).as_posix()

            entries.append(
                FileEntry(
                    path=relative,
                    is_directory=item.is_dir(),
                    size=item.stat().st_size if item.is_file() else None,
                )
            )

        return entries

    def read_file(
        self,
        relative_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> ReadFileResult:
        path = self.resolve_path(relative_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        if not path.is_file():
            raise IsADirectoryError(
                f"Path is not a file: {relative_path}"
            )

        max_size = settings.max_file_size_mb * 1024 * 1024

        if path.stat().st_size > max_size:
            raise ValueError(
                f"File exceeds the configured size limit of "
                f"{settings.max_file_size_mb} MB."
            )

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = content.splitlines()

        total_lines = len(lines)

        if start_line is None:
            start_line = 1

        if end_line is None:
            end_line = total_lines

        if start_line < 1:
            raise ValueError("start_line must be >= 1.")

        if end_line < start_line:
            raise ValueError(
                "end_line must be >= start_line."
            )

        selected_lines = lines[start_line - 1 : end_line]

        return ReadFileResult(
            path=path.relative_to(self.root).as_posix(),
            content="\n".join(selected_lines),
            start_line=start_line,
            end_line=min(end_line, total_lines),
        )