from pathlib import Path

import pytest

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
from app.changes.safety import (
    ChangeSafetyError,
)


def test_create_file_change(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "print('hello world')\n"
        ),
    )

    assert change.path == "app.py"
    assert (
        change.original_content
        == "print('hello')\n"
    )
    assert (
        change.proposed_content
        == "print('hello world')\n"
    )
    assert change.is_modified


def test_create_new_file(
    tmp_path: Path,
):
    change = create_file_change(
        repository_root=tmp_path,
        path="new_file.py",
        proposed_content=(
            "print('new')\n"
        ),
    )

    assert change.original_content == ""
    assert change.is_modified


def test_path_escape_is_blocked(
    tmp_path: Path,
):
    with pytest.raises(
        ChangeSafetyError
    ):
        create_file_change(
            repository_root=tmp_path,
            path="../outside.py",
            proposed_content="bad",
        )


def test_absolute_path_is_blocked(
    tmp_path: Path,
):
    with pytest.raises(
        ChangeSafetyError
    ):
        create_file_change(
            repository_root=tmp_path,
            path=str(
                tmp_path.parent
                / "outside.py"
            ),
            proposed_content="bad",
        )


def test_git_path_is_protected(
    tmp_path: Path,
):
    with pytest.raises(
        ChangeSafetyError
    ):
        create_file_change(
            repository_root=tmp_path,
            path=".git/config",
            proposed_content="bad",
        )


def test_proposal_validation(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "print('hello world')\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Update greeting",
        changes=[change],
    )

    manager = ChangeManager(
        tmp_path
    )

    manager.validate(proposal)

    assert (
        proposal.status
        == ChangeStatus.VALIDATED
    )

    assert proposal.is_valid


def test_generate_diff(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "print('hello world')\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Update greeting",
        changes=[change],
    )

    manager = ChangeManager(
        tmp_path
    )

    diff = manager.diff(
        proposal
    )

    assert "--- a/app.py" in diff
    assert "+++ b/app.py" in diff
    assert "-print('hello')" in diff
    assert "+print('hello world')" in diff


def test_approval_requires_validation(
    tmp_path: Path,
):
    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Test",
        changes=[],
    )

    manager = ChangeManager(
        tmp_path
    )

    with pytest.raises(
        ValueError
    ):
        manager.approve(
            proposal
        )


def test_approved_proposal(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "print('hello world')\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Update greeting",
        changes=[change],
    )

    manager = ChangeManager(
        tmp_path
    )

    manager.validate(proposal)
    manager.approve(proposal)

    assert (
        proposal.status
        == ChangeStatus.APPROVED
    )


def test_apply_is_available_after_phase_4_5(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "print('hello world')\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Update greeting",
        changes=[change],
    )

    manager = ChangeManager(
        tmp_path
    )

    manager.validate(proposal)
    manager.approve(proposal)

    result = manager.apply(
        proposal
    )

    assert result.status.value == "applied"

    assert file_path.read_text(
        encoding="utf-8"
    ) == "print('hello world')\n"