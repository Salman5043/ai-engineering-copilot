from __future__ import annotations

from pathlib import Path


class ChangeSafetyError(ValueError):
    """Raised when a proposed change violates repository safety rules."""


PROTECTED_PATHS = {
    ".git",
    ".gitignore",
}


def normalize_repository_path(
    repository_root: Path,
    relative_path: str,
) -> Path:
    """
    Resolve a repository-relative path safely.

    Raises:
        ChangeSafetyError:
            If the path escapes the repository.
    """

    if not relative_path:
        raise ChangeSafetyError(
            "Change path cannot be empty."
        )

    candidate = Path(relative_path)

    if candidate.is_absolute():
        raise ChangeSafetyError(
            "Absolute paths are not allowed."
        )

    resolved_root = (
        repository_root.resolve()
    )

    resolved_path = (
        repository_root / candidate
    ).resolve()

    try:
        resolved_path.relative_to(
            resolved_root
        )
    except ValueError as exc:
        raise ChangeSafetyError(
            f"Path escapes repository: {relative_path}"
        ) from exc

    return resolved_path


def is_protected_path(
    relative_path: str,
) -> bool:
    """
    Determine whether a path is protected from
    autonomous modification.
    """

    normalized = (
        Path(relative_path)
        .as_posix()
        .strip("/")
    )

    parts = set(
        Path(normalized).parts
    )

    if ".git" in parts:
        return True

    first = (
        Path(normalized).parts[0]
        if Path(normalized).parts
        else ""
    )

    return first in PROTECTED_PATHS


def validate_change_path(
    repository_root: Path,
    relative_path: str,
) -> Path:
    """
    Validate both path safety and protected paths.
    """

    if is_protected_path(
        relative_path
    ):
        raise ChangeSafetyError(
            f"Protected path cannot be modified: "
            f"{relative_path}"
        )

    return normalize_repository_path(
        repository_root,
        relative_path,
    )