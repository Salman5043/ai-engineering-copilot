from __future__ import annotations

from dataclasses import dataclass

from app.changes.approval import (
    ApprovalDecision,
)


@dataclass(frozen=True)
class PendingApproval:
    proposal_id: str
    repository_id: str

    description: str

    changed_files: list[str]

    diff: str

    decision: ApprovalDecision | None = None

    comment: str = ""