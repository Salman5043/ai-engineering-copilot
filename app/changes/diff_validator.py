from __future__ import annotations

from app.changes.models import (
    ChangeProposal,
    ValidationIssue,
    ValidationSeverity,
)
from app.changes.safety import (
    ChangeSafetyError,
    validate_change_path,
)


def validate_proposal_paths(
    proposal: ChangeProposal,
    repository_root,
) -> list[ValidationIssue]:
    """
    Validate all paths in a proposal.
    """

    issues: list[ValidationIssue] = []

    for change in proposal.changes:
        try:
            validate_change_path(
                repository_root,
                change.path,
            )

        except ChangeSafetyError as exc:
            issues.append(
                ValidationIssue(
                    severity=(
                        ValidationSeverity.ERROR
                    ),
                    code="UNSAFE_PATH",
                    message=str(exc),
                    path=change.path,
                )
            )

    return issues


def validate_proposal_changes(
    proposal: ChangeProposal,
) -> list[ValidationIssue]:
    """
    Validate the logical structure of a proposal.
    """

    issues: list[ValidationIssue] = []

    if proposal.is_empty:
        issues.append(
            ValidationIssue(
                severity=(
                    ValidationSeverity.ERROR
                ),
                code="EMPTY_PROPOSAL",
                message=(
                    "Proposal contains no "
                    "actual file changes."
                ),
            )
        )

        return issues

    seen_paths: set[str] = set()

    for change in proposal.changes:
        normalized = change.path.replace(
            "\\",
            "/",
        )

        if normalized in seen_paths:
            issues.append(
                ValidationIssue(
                    severity=(
                        ValidationSeverity.ERROR
                    ),
                    code="DUPLICATE_PATH",
                    message=(
                        "The same file appears "
                        "more than once."
                    ),
                    path=change.path,
                )
            )

        seen_paths.add(normalized)

        if not change.proposed_content.strip():
            issues.append(
                ValidationIssue(
                    severity=(
                        ValidationSeverity.WARNING
                    ),
                    code="EMPTY_FILE",
                    message=(
                        "Proposed file content "
                        "is empty."
                    ),
                    path=change.path,
                )
            )

    return issues