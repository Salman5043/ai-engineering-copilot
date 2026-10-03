from __future__ import annotations

from pathlib import Path

import pytest

from app.changes.apply_and_verify import (
    ApplyAndVerify,
)
from app.changes.models import (
    ChangeStatus,
    FileChange,
    VerificationStatus,
)
from app.changes.proposal import (
    create_change_proposal,
)
from app.changes.test_runner import (
    TestRunner,
)


def create_proposal(
    repository_root: Path,
    *,
    content: str,
    status: ChangeStatus = ChangeStatus.APPROVED,
):
    file_path = (
        repository_root
        / "app.py"
    )

    original = (
        file_path.read_text(
            encoding="utf-8"
        )
        if file_path.exists()
        else ""
    )

    change = FileChange(
        path="app.py",
        original_content=original,
        proposed_content=content,
        reason="Test change.",
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Test change.",
        changes=[change],
    )

    proposal.status = status

    return proposal


def create_passing_test(
    repository_root: Path,
):
    tests = (
        repository_root
        / "tests"
    )

    tests.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        tests / "test_app.py"
    ).write_text(
        """
def test_pass():
    assert True
""".strip(),
        encoding="utf-8",
    )


def create_failing_test(
    repository_root: Path,
):
    tests = (
        repository_root
        / "tests"
    )

    tests.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        tests / "test_app.py"
    ).write_text(
        """
def test_fail():
    assert False
""".strip(),
        encoding="utf-8",
    )


def test_test_runner_passes(
    tmp_path,
):
    create_passing_test(
        tmp_path
    )

    runner = TestRunner(
        tmp_path,
        timeout_seconds=30,
    )

    result = runner.run(
        ["tests/test_app.py"]
    )

    assert result.status == (
        VerificationStatus.PASSED
    )

    assert result.return_code == 0


def test_test_runner_detects_failure(
    tmp_path,
):
    create_failing_test(
        tmp_path
    )

    runner = TestRunner(
        tmp_path,
        timeout_seconds=30,
    )

    result = runner.run(
        ["tests/test_app.py"]
    )

    assert result.status == (
        VerificationStatus.FAILED
    )

    assert result.return_code != 0


def test_apply_and_verify_keeps_successful_change(
    tmp_path,
):
    create_passing_test(
        tmp_path
    )

    file_path = (
        tmp_path
        / "app.py"
    )

    file_path.write_text(
        "print('old')\n",
        encoding="utf-8",
    )

    proposal = create_proposal(
        tmp_path,
        content="print('new')\n",
    )

    workflow = ApplyAndVerify(
        tmp_path,
        test_timeout_seconds=30,
    )

    result = workflow.execute(
        proposal
    )

    assert result.status == (
        VerificationStatus.PASSED
    )

    assert (
        proposal.status
        == ChangeStatus.APPLIED
    )

    assert file_path.read_text(
        encoding="utf-8"
    ) == "print('new')\n"

    assert (
        result.rollback_performed
        is False
    )


def test_apply_and_verify_rolls_back_failed_change(
    tmp_path,
):
    create_failing_test(
        tmp_path
    )

    file_path = (
        tmp_path
        / "app.py"
    )

    file_path.write_text(
        "print('old')\n",
        encoding="utf-8",
    )

    proposal = create_proposal(
        tmp_path,
        content="print('new')\n",
    )

    workflow = ApplyAndVerify(
        tmp_path,
        test_timeout_seconds=30,
    )

    result = workflow.execute(
        proposal
    )

    assert result.status == (
        VerificationStatus.FAILED
    )

    assert (
        result.rollback_performed
        is True
    )

    assert (
        proposal.status
        == ChangeStatus.ROLLED_BACK
    )

    assert file_path.read_text(
        encoding="utf-8"
    ) == "print('old')\n"


def test_unapproved_proposal_is_not_applied(
    tmp_path,
):
    create_passing_test(
        tmp_path
    )

    file_path = (
        tmp_path
        / "app.py"
    )

    file_path.write_text(
        "print('old')\n",
        encoding="utf-8",
    )

    proposal = create_proposal(
        tmp_path,
        content="print('new')\n",
        status=ChangeStatus.VALIDATED,
    )

    workflow = ApplyAndVerify(
        tmp_path
    )

    with pytest.raises(Exception):
        workflow.execute(
            proposal
        )

    assert file_path.read_text(
        encoding="utf-8"
    ) == "print('old')\n"