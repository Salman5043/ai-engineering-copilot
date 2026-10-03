from __future__ import annotations

from app.changes.approval import (
    ApprovalDecision,
    ApprovalError,
    ApprovalRequest,
    ApprovalResponse,
    apply_approval,
    build_approval_request,
)
from app.changes.manager import (
    ChangeManager,
)
from app.changes.models import (
    ChangeProposal,
)


class ApprovalManager:
    """
    Coordinates validation and human approval.

    This class does not modify repository files.
    """

    def __init__(
        self,
        change_manager: ChangeManager,
    ) -> None:
        self.change_manager = change_manager

    def prepare(
        self,
        proposal: ChangeProposal,
    ) -> ApprovalRequest:
        """
        Validate a proposal and prepare the
        information required for human review.

        No repository files are modified.
        """

        validation = (
            self.change_manager.validate_patch(
                proposal
            )
        )

        if not validation.valid:
            raise ApprovalError(
                "Patch failed validation and "
                "cannot be submitted for approval."
            )

        diff = self.change_manager.diff(
            proposal
        )

        return build_approval_request(
            proposal,
            diff=diff,
            validation=validation,
        )

    def approve(
        self,
        proposal: ChangeProposal,
        *,
        comment: str = "",
    ) -> ChangeProposal:
        """
        Approve a validated proposal.

        Approval only changes the proposal state.
        It does not modify repository files.
        """

        response = ApprovalResponse(
            proposal_id=proposal.proposal_id,
            decision=ApprovalDecision.APPROVE,
            comment=comment,
        )

        return apply_approval(
            proposal,
            response,
        )

    def reject(
        self,
        proposal: ChangeProposal,
        *,
        comment: str = "",
    ) -> ChangeProposal:
        """
        Reject a validated proposal.

        Rejection does not modify repository files.
        """

        response = ApprovalResponse(
            proposal_id=proposal.proposal_id,
            decision=ApprovalDecision.REJECT,
            comment=comment,
        )

        return apply_approval(
            proposal,
            response,
        )