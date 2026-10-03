from __future__ import annotations

from typing import Any

from app.changes.approval import (
    ApprovalError,
)
from app.changes.models import (
    ChangeProposal,
)
from app.changes.approval_manager import (
    ApprovalManager,
)


def prepare_change_approval(
    state: dict[str, Any],
    *,
    proposal: ChangeProposal,
    approval_manager: ApprovalManager,
) -> dict[str, Any]:
    """
    Prepare a validated change for human approval.

    This node does not modify repository files.
    """

    try:
        request = (
            approval_manager.prepare(
                proposal
            )
        )

    except ApprovalError as exc:
        return {
            "approval_required": False,
            "approval_granted": False,
            "approval_error": str(exc),
            "change_status": proposal.status.value,
        }

    return {
        "change_proposal_id": (
            proposal.proposal_id
        ),
        "change_status": (
            proposal.status.value
        ),
        "approval_required": True,
        "approval_granted": False,
        "approval_comment": "",
        "approval_diff": request.diff,
        "approval_error": "",
    }


def approve_change(
    state: dict[str, Any],
    *,
    proposal: ChangeProposal,
    approval_manager: ApprovalManager,
    comment: str = "",
) -> dict[str, Any]:
    """
    Apply a human approval decision.

    Still does not modify repository files.
    """

    try:
        approval_manager.approve(
            proposal,
            comment=comment,
        )

    except ApprovalError as exc:
        return {
            "approval_granted": False,
            "approval_error": str(exc),
            "change_status": proposal.status.value,
        }

    return {
        "approval_required": False,
        "approval_granted": True,
        "approval_comment": comment,
        "change_status": proposal.status.value,
        "approval_error": "",
    }


def reject_change(
    state: dict[str, Any],
    *,
    proposal: ChangeProposal,
    approval_manager: ApprovalManager,
    comment: str = "",
) -> dict[str, Any]:
    """
    Reject a change proposal.
    """

    try:
        approval_manager.reject(
            proposal,
            comment=comment,
        )

    except ApprovalError as exc:
        return {
            "approval_granted": False,
            "approval_error": str(exc),
            "change_status": proposal.status.value,
        }

    return {
        "approval_required": False,
        "approval_granted": False,
        "approval_comment": comment,
        "change_status": proposal.status.value,
        "approval_error": "",
    }