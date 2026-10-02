from __future__ import annotations

import difflib
import hashlib
from pathlib import Path

from app.changes.models import (
    ChangeProposal,
    FileChange,
)
from app.changes.safety import (
    validate_change_path,
)


def _proposal_id(
    repository_id: str,
    description: str,
) -> str:
    payload = (
        f"{repository_id}:{description}"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:16]


def create_file_change(
    *,
    repository_root: Path,
    path: str,
    proposed_content: str,
    reason: str = "",
) -> FileChange:
    """
    Create a safe file-level change proposal.
    """

    file_path = validate_change_path(
        repository_root,
        path,
    )

    if file_path.exists():
        if not file_path.is_file():
            raise ValueError(
                f"Path is not a file: {path}"
            )

        original_content = (
            file_path.read_text(
                encoding="utf-8"
            )
        )
    else:
        original_content = ""

    return FileChange(
        path=path,
        original_content=original_content,
        proposed_content=proposed_content,
        reason=reason,
    )


def create_change_proposal(
    *,
    repository_id: str,
    description: str,
    changes: list[FileChange],
) -> ChangeProposal:
    """
    Build a repository-level change proposal.
    """

    return ChangeProposal(
        proposal_id=_proposal_id(
            repository_id,
            description,
        ),
        repository_id=repository_id,
        description=description,
        changes=changes,
    )


def generate_file_diff(
    change: FileChange,
) -> str:
    """
    Generate a unified diff for one file.
    """

    original = (
        change.original_content
        .splitlines(
            keepends=True
        )
    )

    proposed = (
        change.proposed_content
        .splitlines(
            keepends=True
        )
    )

    diff = difflib.unified_diff(
        original,
        proposed,
        fromfile=f"a/{change.path}",
        tofile=f"b/{change.path}",
    )

    return "".join(diff)


def generate_proposal_diff(
    proposal: ChangeProposal,
) -> str:
    """
    Generate the complete unified diff.
    """

    parts: list[str] = []

    for change in proposal.changes:
        if not change.is_modified:
            continue

        diff = generate_file_diff(
            change
        )

        if diff:
            parts.append(diff)

    return "\n".join(parts)