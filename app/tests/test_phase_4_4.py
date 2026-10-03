from pathlib import Path

import pytest

from app.changes.approval import (
    ApprovalDecision,
    ApprovalError,
    apply_approval,
    build_approval_request,
)
from app.changes.approval_manager import (
    ApprovalManager,
)
from app.changes.manager import (
    ChangeManager,
)
from app.changes.models import (
    ChangeStatus,
)
from app.changes.proposal import (
    create_change_proposal,
    create_file_change,
)


def make_proposal(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "def hello():\n"
            "    return 'world'\n"
        ),
        reason="Update greeting.",
    )

    return create_change_proposal(
        repository_id="test-repo",
        description="Update greeting.",
        changes=[change],
    )


def test_prepare_approval(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    manager = ApprovalManager(
        ChangeManager(tmp_path)
    )

    request = manager.prepare(
        proposal
    )

    assert (
        request.proposal_id
        == proposal.proposal_id
    )

    assert (
        request.repository_id
        == "test-repo"
    )

    assert (
        "app.py"
        in request.changed_files
    )

    assert (
        "--- a/app.py"
        in request.diff
    )

    assert request.validation.valid


def test_approval_requires_validated_proposal(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    with pytest.raises(
        ApprovalError
    ):
        build_approval_request(
            proposal,
            diff="test",
            validation=type(
                "Validation",
                (),
                {"valid": False},
            )(),
        )


def test_approve_proposal(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    manager = ApprovalManager(
        ChangeManager(tmp_path)
    )

    manager.prepare(
        proposal
    )

    manager.approve(
        proposal,
        comment="Looks correct.",
    )

    assert (
        proposal.status
        == ChangeStatus.APPROVED
    )

    assert (
        proposal.metadata[
            "approval_decision"
        ]
        == "approve"
    )

    assert (
        proposal.metadata[
            "approval_comment"
        ]
        == "Looks correct."
    )


def test_reject_proposal(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    manager = ApprovalManager(
        ChangeManager(tmp_path)
    )

    manager.prepare(
        proposal
    )

    manager.reject(
        proposal,
        comment="Needs another approach.",
    )

    assert (
        proposal.status
        == ChangeStatus.REJECTED
    )

    assert (
        proposal.metadata[
            "approval_decision"
        ]
        == "reject"
    )


def test_approval_response_must_match_proposal(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    manager = ApprovalManager(
        ChangeManager(tmp_path)
    )

    manager.prepare(
        proposal
    )

    from app.changes.approval import (
        ApprovalResponse,
    )

    with pytest.raises(
        ApprovalError
    ):
        apply_approval(
            proposal,
            ApprovalResponse(
                proposal_id="wrong-id",
                decision=(
                    ApprovalDecision.APPROVE
                ),
            ),
        )


def test_approval_does_not_modify_file(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    file_path = (
        tmp_path / "app.py"
    )

    original = file_path.read_text(
        encoding="utf-8"
    )

    manager = ApprovalManager(
        ChangeManager(tmp_path)
    )

    manager.prepare(
        proposal
    )

    manager.approve(
        proposal
    )

    assert (
        file_path.read_text(
            encoding="utf-8"
        )
        == original
    )


def test_cannot_approve_failed_proposal(
    tmp_path: Path,
):
    proposal = make_proposal(
        tmp_path
    )

    # Deliberately create invalid Python.
    proposal.changes[0] = (
        type(proposal.changes[0])(
            path="app.py",
            original_content=(
                proposal.changes[0]
                .original_content
            ),
            proposed_content=(
                "def broken(\n"
            ),
            reason="Invalid change.",
        )
    )

    manager = ApprovalManager(
        ChangeManager(tmp_path)
    )

    with pytest.raises(
        ApprovalError
    ):
        manager.prepare(
            proposal
        )