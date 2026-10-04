from __future__ import annotations

from pathlib import Path

import pytest

from app.changes.approval_manager import (
    ApprovalManager,
)
from app.changes.autonomous_fix import (
    ApprovalRequiredError,
    AutonomousFixVerifier,
)
from app.changes.llm_models import (
    GeneratedFileChange,
    PatchGenerationResponse,
)
from app.changes.manager import (
    ChangeManager,
)
from app.changes.models import (
    ChangeProposal,
    ChangeStatus,
    TestResult,
    VerificationResult,
    VerificationStatus,
)


class FakeStructuredLLM:
    def __init__(
        self,
        response: PatchGenerationResponse,
    ) -> None:
        self.response = response

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):
        self.prompt = prompt
        return self.response


def build_failure() -> VerificationResult:
    test_result = TestResult(
        command=[
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_example.py",
        ],
        status=VerificationStatus.FAILED,
        return_code=1,
        stdout=(
            "FAILED tests/test_example.py::test_example\n"
            "app/example.py:42: AssertionError\n"
        ),
        stderr="",
        duration_seconds=0.5,
    )

    return VerificationResult(
        status=VerificationStatus.FAILED,
        tests=[test_result],
        selected_tests=[
            "tests/test_example.py",
        ],
    )


def test_max_iterations_must_be_positive(
    tmp_path: Path,
):
    manager = ChangeManager(
        repository_root=tmp_path
    )

    approval_manager = ApprovalManager(
        manager
    )

    with pytest.raises(ValueError):
        AutonomousFixVerifier(
            repository_root=tmp_path,
            approval_manager=approval_manager,
            max_iterations=0,
        )


def test_unapproved_proposal_cannot_execute(
    tmp_path: Path,
):
    manager = ChangeManager(
        repository_root=tmp_path
    )

    approval_manager = ApprovalManager(
        manager
    )

    orchestrator = AutonomousFixVerifier(
        repository_root=tmp_path,
        approval_manager=approval_manager,
    )

    proposal = ChangeProposal(
        proposal_id="proposal-1",
        repository_id="demo",
        description="Test proposal",
        changes=[],
    )

    with pytest.raises(
        ApprovalRequiredError
    ):
        orchestrator.execute_approved_attempt(
            proposal
        )


def test_failed_verification_prepares_next_fix(
    tmp_path: Path,
):
    example_file = (
        tmp_path
        / "app"
        / "example.py"
    )

    example_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    original = (
        "def example():\n"
        "    return 1\n"
    )

    example_file.write_text(
        original,
        encoding="utf-8",
    )

    manager = ChangeManager(
        repository_root=tmp_path
    )

    approval_manager = ApprovalManager(
        manager
    )

    orchestrator = AutonomousFixVerifier(
        repository_root=tmp_path,
        approval_manager=approval_manager,
        max_iterations=3,
    )

    fake_llm = FakeStructuredLLM(
        PatchGenerationResponse(
            description="Fix failing example.",
            changes=[
                GeneratedFileChange(
                    path="app/example.py",
                    proposed_content=(
                        "def example():\n"
                        "    return 2\n"
                    ),
                    reason="Fix failing assertion.",
                )
            ],
        )
    )

    proposal, approval_request, failure = (
        orchestrator.prepare_next_fix(
            repository_id="demo",
            original_query=(
                "Fix the example function."
            ),
            verification=build_failure(),
            files=[
                {
                    "path": "app/example.py",
                    "content": original,
                }
            ],
            evidence=[
                {
                    "source_tool": "test_search",
                    "file": "tests/test_example.py",
                    "start_line": 1,
                    "end_line": 20,
                    "symbol": "test_example",
                    "content": (
                        "def test_example():\n"
                        "    assert example() == 2\n"
                    ),
                }
            ],
            llm=fake_llm,
        )
    )

    assert failure.has_failure is True

    assert proposal.status == (
        ChangeStatus.VALIDATED
    )

    assert approval_request.proposal_id == (
        proposal.proposal_id
    )

    assert approval_request.changed_files == [
        "app/example.py"
    ]

    # Preparing a corrective fix must never modify files.
    assert example_file.read_text(
        encoding="utf-8"
    ) == original


def test_approved_attempt_can_be_executed(
    tmp_path: Path,
):
    manager = ChangeManager(
        repository_root=tmp_path
    )

    approval_manager = ApprovalManager(
        manager
    )

    orchestrator = AutonomousFixVerifier(
        repository_root=tmp_path,
        approval_manager=approval_manager,
        max_iterations=3,
    )

    proposal = ChangeProposal(
        proposal_id="proposal-1",
        repository_id="demo",
        description="Test proposal",
        changes=[],
        status=ChangeStatus.PROPOSED,
    )

    with pytest.raises(
        ApprovalRequiredError
    ):
        orchestrator.execute_approved_attempt(
            proposal
        )