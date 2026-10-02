from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class FileChange:
    """
    Represents a proposed modification to one repository file.
    """

    path: str
    original_content: str
    proposed_content: str

    reason: str = ""

    @property
    def is_modified(self) -> bool:
        return (
            self.original_content
            != self.proposed_content
        )


@dataclass
class ChangeProposal:
    """
    A complete, reviewable repository change proposal.
    """

    proposal_id: str

    repository_id: str

    description: str

    changes: list[FileChange] = field(
        default_factory=list
    )

    status: ChangeStatus = (
        ChangeStatus.PROPOSED
    )

    validation_errors: list[str] = field(
        default_factory=list
    )

    validation_warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def changed_files(self) -> list[str]:
        return [
            change.path
            for change in self.changes
            if change.is_modified
        ]

    @property
    def is_empty(self) -> bool:
        return not any(
            change.is_modified
            for change in self.changes
        )

    @property
    def is_valid(self) -> bool:
        return (
            not self.validation_errors
        )