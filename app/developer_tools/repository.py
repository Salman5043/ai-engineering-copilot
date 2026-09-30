from __future__ import annotations

from app.developer_tools.filesystem import RepositoryFileSystem
from app.developer_tools.models import (
    RepositoryStructureResult,
)


class RepositoryTools:
    """
    Repository-level developer tools.
    """

    def __init__(self, repository_id: str):
        self.filesystem = RepositoryFileSystem(repository_id)

    def get_structure(
        self,
        max_files: int = 1000,
    ) -> RepositoryStructureResult:
        if max_files < 1:
            raise ValueError(
                "max_files must be greater than zero."
            )

        files: list[str] = []
        directories: list[str] = []

        for path in self.filesystem.root.rglob("*"):
            if path.is_dir():
                relative = path.relative_to(
                    self.filesystem.root
                ).as_posix()

                if relative:
                    directories.append(relative)

            elif path.is_file():
                relative = path.relative_to(
                    self.filesystem.root
                ).as_posix()

                files.append(relative)

                if len(files) >= max_files:
                    break

        return RepositoryStructureResult(
            repository_id=self.filesystem.repository_id,
            root=str(self.filesystem.root),
            files=sorted(files),
            directories=sorted(directories),
        )