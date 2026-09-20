from dataclasses import dataclass
from pathlib import Path

from .filters import (
    is_supported_file,
    should_ignore_directory,
)


@dataclass
class RepositoryFile:
    path: Path
    relative_path: str
    extension: str
    size_bytes: int


def scan_repository(
    repository_path: str,
    max_file_size_mb: int = 2,
) -> list[RepositoryFile]:

    root = Path(repository_path).resolve()

    if not root.exists():
        raise FileNotFoundError(
            f"Repository does not exist: {root}"
        )

    if not root.is_dir():
        raise ValueError(
            f"Repository path is not a directory: {root}"
        )

    max_size = max_file_size_mb * 1024 * 1024

    files: list[RepositoryFile] = []

    for path in root.rglob("*"):

        if should_ignore_directory(path.parent):
            continue

        if not is_supported_file(path):
            continue

        try:
            size = path.stat().st_size
        except OSError:
            continue

        if size > max_size:
            continue

        relative_path = path.relative_to(root).as_posix()

        files.append(
            RepositoryFile(
                path=path,
                relative_path=relative_path,
                extension=path.suffix.lower(),
                size_bytes=size,
            )
        )

    return sorted(
        files,
        key=lambda item: item.relative_path,
    )