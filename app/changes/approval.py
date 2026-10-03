from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.changes.models import (
    ChangeProposal,
    ChangeStatus,
    ValidationResult,
)


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ApprovalRequest:
    """
    Information presented to the human reviewer.
    """

    proposal_id: str
    repository_id: str
    description: str

    changed_files: list[str]

    diff: str

    validation: ValidationResult


@dataclass(frozen=True)
class ApprovalResponse:
    """
    Human decision regarding a change proposal.
    """

    proposal_id: str
    decision: ApprovalDecision
    comment: str = ""


class ApprovalError(RuntimeError):
    """Raised when approval rules are violated."""


def build_approval_request(
    proposal: ChangeProposal,
    *,
    diff: str,
    validation: ValidationResult,
) -> ApprovalRequest:
    """
    Build the information that will be shown
    to the human reviewer.
    """

    if not validation.valid:
        raise ApprovalError(
            "Only validated proposals can be "
            "submitted for approval."
        )

    if proposal.status != ChangeStatus.VALIDATED:
        raise ApprovalError(
            "Proposal must have VALIDATED status "
            "before approval."
        )

    return ApprovalRequest(
        proposal_id=proposal.proposal_id,
        repository_id=proposal.repository_id,
        description=proposal.description,
        changed_files=proposal.changed_files,
        diff=diff,
        validation=validation,
    )


def apply_approval(
    proposal: ChangeProposal,
    response: ApprovalResponse,
) -> ChangeProposal:
    """
    Apply a human approval decision to the proposal.

    This does NOT modify repository files.
    """

    if (
        response.proposal_id
        != proposal.proposal_id
    ):
        raise ApprovalError(
            "Approval response does not match "
            "the proposal."
        )

    if proposal.status != ChangeStatus.VALIDATED:
        raise ApprovalError(
            "Only validated proposals can "
            "receive approval."
        )

    if response.decision == (
        ApprovalDecision.APPROVE
    ):
        proposal.status = (
            ChangeStatus.APPROVED
        )

    elif response.decision == (
        ApprovalDecision.REJECT
    ):
        proposal.status = (
            ChangeStatus.REJECTED
        )

    else:
        raise ApprovalError(
            f"Unsupported approval decision: "
            f"{response.decision}"
        )

    if response.comment:
        proposal.metadata[
            "approval_comment"
        ] = response.comment

    proposal.metadata[
        "approval_decision"
    ] = response.decision.value

    return proposal