from __future__ import annotations

from pathlib import Path

from app.agent.approval import (
    prepare_corrective_fix_approval,
)
from app.changes.approval_manager import (
    ApprovalManager,
)
from app.changes.llm_models import (
    GeneratedFileChange,
    PatchGenerationResponse,
)
from app.changes.manager import (
    ChangeManager,
)
from app.changes.models import (
    ChangeStatus,
    TestResult,
    VerificationResult,
    VerificationStatus,
)
from app.changes.failure_analysis import (
    analyze_verification_failure,
)


class FakeStructuredLLM:
    def __init__(
        self,
        response: PatchGenerationResponse,
    ) -> None:
        self.response = response
        self.prompt = None

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


def test_corrective_fix_requires_human_approval(
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

    failure = analyze_verification_failure(
        build_failure()
    )

    fake_llm = FakeStructuredLLM(
        PatchGenerationResponse(
            description="Correct failing example.",
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

    change_manager = ChangeManager(
        repository_root=tmp_path
    )

    approval_manager = ApprovalManager(
        change_manager
    )

    proposal, approval_request = (
        prepare_corrective_fix_approval(
            approval_manager=approval_manager,
            repository_id="demo",
            repository_root=tmp_path,
            original_query="Fix the example function.",
            failure=failure,
            files=[
                {
                    "path": "app/example.py",
                    "content": original,
                }
            ],
            evidence=[],
            llm=fake_llm,
        )
    )

    assert proposal.status == ChangeStatus.VALIDATED

    assert approval_request.proposal_id == (
        proposal.proposal_id
    )

    assert approval_request.changed_files == [
        "app/example.py"
    ]

    # Most importantly, repository was NOT modified.
    assert example_file.read_text(
        encoding="utf-8"
    ) == original


def test_corrective_fix_can_be_explicitly_approved(
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

    failure = analyze_verification_failure(
        build_failure()
    )

    fake_llm = FakeStructuredLLM(
        PatchGenerationResponse(
            description="Correct failing example.",
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

    change_manager = ChangeManager(
        repository_root=tmp_path
    )

    approval_manager = ApprovalManager(
        change_manager
    )

    proposal, _ = (
        prepare_corrective_fix_approval(
            approval_manager=approval_manager,
            repository_id="demo",
            repository_root=tmp_path,
            original_query="Fix the example function.",
            failure=failure,
            files=[
                {
                    "path": "app/example.py",
                    "content": original,
                }
            ],
            evidence=[],
            llm=fake_llm,
        )
    )

    approved = approval_manager.approve(
        proposal,
        comment="Approved corrective fix.",
    )

    assert approved.status == (
        ChangeStatus.APPROVED
    )

    assert approved.metadata[
        "approval_comment"
    ] == "Approved corrective fix."

    # Approval alone still must not modify files.
    assert example_file.read_text(
        encoding="utf-8"
    ) == original