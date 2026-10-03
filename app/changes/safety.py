from __future__ import annotations

from pathlib import Path


class ChangeSafetyError(ValueError):
    """Raised when a proposed change violates repository safety rules."""


PROTECTED_PATHS = {
    ".git",
    ".gitignore",
}

SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    "credentials.json",
    "secrets.json",
}


def is_sensitive_path(
    relative_path: str,
) -> bool:
    """
    Determine whether a file may contain secrets
    or credentials.
    """

    normalized = (
        Path(relative_path)
        .as_posix()
        .strip("/")
    )

    path = Path(normalized)

    if not path.parts:
        return False

    filename = path.name.lower()

    if filename in SENSITIVE_FILENAMES:
        return True

    if filename.endswith(
        ".pem"
    ):
        return True

    if filename.endswith(
        ".key"
    ):
        return True

    return False


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
    Validate path safety before any repository
    modification is allowed.
    """

    if is_protected_path(
        relative_path
    ):
        raise ChangeSafetyError(
            f"Protected path cannot be modified: "
            f"{relative_path}"
        )

    if is_sensitive_path(
        relative_path
    ):
        raise ChangeSafetyError(
            f"Sensitive file cannot be modified "
            f"automatically: {relative_path}"
        )

    return normalize_repository_path(
        repository_root,
        relative_path,
    )
