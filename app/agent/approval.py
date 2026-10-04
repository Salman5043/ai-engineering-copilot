from __future__ import annotations

from pathlib import Path
from typing import Any

from app.changes.approval import (
    ApprovalRequest,
)
from app.changes.approval_manager import (
    ApprovalManager,
)
from app.changes.corrective_fix import (
    generate_corrective_fix,
)
from app.changes.failure_analysis import (
    FailureAnalysis,
)
from app.changes.models import (
    ChangeProposal,
)


def prepare_change_approval(
    approval_manager: ApprovalManager,
    proposal: ChangeProposal,
) -> ApprovalRequest:
    """
    Validate a proposal and prepare it for human approval.
    """

    return approval_manager.prepare(proposal)


def approve_change(
    approval_manager: ApprovalManager,
    proposal: ChangeProposal,
    *,
    comment: str = "",
) -> ChangeProposal:
    """
    Apply an explicit human approval decision.

    This does not write repository files.
    """

    return approval_manager.approve(
        proposal,
        comment=comment,
    )


def reject_change(
    approval_manager: ApprovalManager,
    proposal: ChangeProposal,
    *,
    comment: str = "",
) -> ChangeProposal:
    """
    Apply an explicit human rejection decision.
    """

    return approval_manager.reject(
        proposal,
        comment=comment,
    )


def prepare_corrective_fix_approval(
    *,
    approval_manager: ApprovalManager,
    repository_id: str,
    repository_root: Path,
    original_query: str,
    failure: FailureAnalysis,
    files: list[dict[str, str]],
    evidence: list[dict[str, Any]],
    llm: Any | None = None,
) -> tuple[ChangeProposal, ApprovalRequest]:
    """
    Generate, validate, and prepare a corrective proposal
    for human approval.

    This function NEVER modifies repository files.
    """

    proposal = generate_corrective_fix(
        repository_id=repository_id,
        repository_root=repository_root,
        original_query=original_query,
        failure=failure,
        files=files,
        evidence=evidence,
        llm=llm,
    )

    approval_request = approval_manager.prepare(
        proposal
    )

    return proposal, approval_request