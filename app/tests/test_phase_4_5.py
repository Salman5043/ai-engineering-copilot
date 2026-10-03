from __future__ import annotations

from pathlib import Path

import pytest

from app.changes.applier import (
    PatchApplicationError,
    SafePatchApplier,
)
from app.changes.manager import (
    ChangeManager,
)
from app.changes.models import (
    ChangeStatus,
    FileChange,
)
from app.changes.proposal import (
    create_change_proposal,
)


def make_proposal(
    repository_root: Path,
    *,
    status: ChangeStatus = ChangeStatus.APPROVED,
):
    target = (
        repository_root
        / "app.py"
    )

    target.write_text(
        "print('old')\n",
        encoding="utf-8",
    )

    change = FileChange(
        path="app.py",
        original_content="print('old')\n",
        proposed_content="print('new')\n",
        reason="Update output.",
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Update app.",
        changes=[change],
    )

    proposal.status = status

    return proposal


def test_apply_requires_approval(
    tmp_path,
):
    proposal = make_proposal(
        tmp_path,
        status=ChangeStatus.VALIDATED,
    )

    applier = SafePatchApplier(
        tmp_path
    )

    with pytest.raises(
        PatchApplicationError,
        match="APPROVED",
    ):
        applier.apply(
            proposal
        )


def test_apply_modifies_file(
    tmp_path,
):
    proposal = make_proposal(
        tmp_path
    )

    applier = SafePatchApplier(
        tmp_path
    )

    result = applier.apply(
        proposal
    )

    assert result.status == (
        ChangeStatus.APPLIED
    )

    assert (
        tmp_path
        / "app.py"
    ).read_text(
        encoding="utf-8"
    ) == "print('new')\n"


def test_apply_creates_backup(
    tmp_path,
):
    proposal = make_proposal(
        tmp_path
    )

    applier = SafePatchApplier(
        tmp_path
    )

    result = applier.apply(
        proposal
    )

    assert result.backup_directory
    assert Path(
        result.backup_directory
    ).exists()

    backup_file = (
        Path(
            result.backup_directory
        )
        / "app.py"
    )

    assert backup_file.read_text(
        encoding="utf-8"
    ) == "print('old')\n"


def test_rollback_restores_original(
    tmp_path,
):
    proposal = make_proposal(
        tmp_path
    )

    applier = SafePatchApplier(
        tmp_path
    )

    result = applier.apply(
        proposal
    )

    assert result.status == (
        ChangeStatus.APPLIED
    )

    result = applier.rollback(
        result
    )

    assert result.status == (
        ChangeStatus.ROLLED_BACK
    )

    assert (
        tmp_path
        / "app.py"
    ).read_text(
        encoding="utf-8"
    ) == "print('old')\n"


def test_absolute_path_is_rejected(
    tmp_path,
):
    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Unsafe change.",
        changes=[
            FileChange(
                path=str(
                    tmp_path
                    / "outside.py"
                ),
                original_content="",
                proposed_content="print('x')\n",
            )
        ],
    )

    proposal.status = (
        ChangeStatus.APPROVED
    )

    applier = SafePatchApplier(
        tmp_path
    )

    with pytest.raises(
        PatchApplicationError
    ):
        applier.apply(
            proposal
        )


def test_parent_escape_is_rejected(
    tmp_path,
):
    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Unsafe change.",
        changes=[
            FileChange(
                path="../../outside.py",
                original_content="",
                proposed_content="print('x')\n",
            )
        ],
    )

    proposal.status = (
        ChangeStatus.APPROVED
    )

    applier = SafePatchApplier(
        tmp_path
    )

    with pytest.raises(
        PatchApplicationError
    ):
        applier.apply(
            proposal
        )


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        ".git/config",
        "credentials.json",
        "secrets.json",
        "private.key",
        "certificate.pem",
    ],
)
def test_sensitive_paths_are_rejected(
    tmp_path,
    path,
):
    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Unsafe change.",
        changes=[
            FileChange(
                path=path,
                original_content="",
                proposed_content="secret\n",
            )
        ],
    )

    proposal.status = (
        ChangeStatus.APPROVED
    )

    applier = SafePatchApplier(
        tmp_path
    )

    with pytest.raises(
        PatchApplicationError
    ):
        applier.apply(
            proposal
        )


def test_manifest_is_created(
    tmp_path,
):
    proposal = make_proposal(
        tmp_path
    )

    applier = SafePatchApplier(
        tmp_path
    )

    result = applier.apply(
        proposal
    )

    assert result.manifest is not None

    assert result.manifest.proposal_id == (
        result.proposal_id
    )

    assert result.manifest.changed_files == [
        "app.py"
    ]

    assert (
        result.manifest.rollback_available
        is True
    )


def test_change_manager_can_apply(
    tmp_path,
):
    proposal = make_proposal(
        tmp_path
    )

    manager = ChangeManager(
        tmp_path
    )

    result = manager.apply(
        proposal
    )

    assert result.status == (
        ChangeStatus.APPLIED
    )

    assert (
        tmp_path
        / "app.py"
    ).read_text(
        encoding="utf-8"
    ) == "print('new')\n"