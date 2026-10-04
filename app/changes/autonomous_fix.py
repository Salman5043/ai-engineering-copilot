from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.changes.approval_manager import (
    ApprovalManager,
)
from app.changes.apply_and_verify import (
    ApplyAndVerify,
)
from app.changes.corrective_fix import (
    generate_corrective_fix,
)
from app.changes.failure_analysis import (
    FailureAnalysis,
    analyze_verification_failure,
)
from app.changes.models import (
    ChangeProposal,
    ChangeStatus,
    VerificationResult,
    VerificationStatus,
)
from app.changes.validator import (
    PatchValidator,
)
from app.changes.failure_investigator import (
    FailureInvestigator,
)


class AutonomousFixError(RuntimeError):
    """Raised when the autonomous fix workflow cannot continue."""


class ApprovalRequiredError(AutonomousFixError):
    """
    Raised when the workflow reaches a proposal that requires
    explicit human approval.
    """


@dataclass(frozen=True)
class FixAttempt:
    iteration: int
    proposal_id: str
    status: ChangeStatus
    verification: VerificationResult | None = None
    failure_analysis: FailureAnalysis | None = None


@dataclass
class AutonomousFixResult:
    success: bool
    iterations: int
    final_proposal: ChangeProposal | None = None
    final_verification: VerificationResult | None = None
    attempts: list[FixAttempt] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )

    @property
    def rolled_back(self) -> bool:
        return any(
            attempt.status == ChangeStatus.ROLLED_BACK
            for attempt in self.attempts
        )


class AutonomousFixVerifier:
    """
    Coordinates repeated apply -> verify -> rollback -> fix cycles.

    Important:
    - It never approves a proposal automatically.
    - Every corrective proposal must pass validation.
    - Every corrective proposal must receive human approval.
    - Failed attempts are rolled back.
    - max_iterations prevents infinite repair loops.
    """

    def __init__(
        self,
        *,
        repository_root: Path,
        approval_manager: ApprovalManager,
        max_iterations: int = 3,
        test_timeout_seconds: float = 300.0,
    ) -> None:
        if max_iterations < 1:
            raise ValueError(
                "max_iterations must be at least 1."
            )

        self.repository_root = (
            repository_root.resolve()
        )

        self.approval_manager = approval_manager

        self.max_iterations = max_iterations

        self.test_timeout_seconds = (
            test_timeout_seconds
        )

    def _verify(
        self,
        proposal: ChangeProposal,
    ) -> VerificationResult:
        workflow = ApplyAndVerify(
            repository_root=self.repository_root,
            test_timeout_seconds=(
                self.test_timeout_seconds
            ),
        )

        return workflow.execute(
            proposal
        )

    def _build_corrective_proposal(
        self,
        *,
        repository_id: str,
        original_query: str,
        failure: FailureAnalysis,
        files: list[dict[str, str]],
        evidence: list[dict[str, Any]],
        llm: Any | None,
    ) -> ChangeProposal:
        proposal = generate_corrective_fix(
            repository_id=repository_id,
            repository_root=self.repository_root,
            original_query=original_query,
            failure=failure,
            files=files,
            evidence=evidence,
            llm=llm,
        )

        validation = (
            self.approval_manager.change_manager
            .validate_patch(proposal)
        )

        if not validation.valid:
            raise AutonomousFixError(
                "Corrective proposal failed validation."
            )

        return proposal

    def prepare_next_fix(
        self,
        *,
        repository_id: str,
        original_query: str,
        verification: VerificationResult,
        files: list[dict[str, str]],
        evidence: list[dict[str, Any]],
        llm: Any | None = None,
    ) -> tuple[
        ChangeProposal,
        Any,
        FailureAnalysis,
    ]:
        """
        Analyze a failed verification and prepare the next
        corrective proposal for human approval.

        No files are modified.
        """

        failure = analyze_verification_failure(
            verification
        )

        if not failure.has_failure:
            raise AutonomousFixError(
                "Cannot prepare a corrective fix "
                "from a successful verification."
            )

        proposal = self._build_corrective_proposal(
            repository_id=repository_id,
            original_query=original_query,
            failure=failure,
            files=files,
            evidence=evidence,
            llm=llm,
        )

        approval_request = (
            self.approval_manager.prepare(
                proposal
            )
        )

        return (
            proposal,
            approval_request,
            failure,
        )

    def execute_approved_attempt(
        self,
        proposal: ChangeProposal,
    ) -> VerificationResult:
        """
        Apply an already-approved proposal and verify it.

        The proposal must already have APPROVED status.
        """

        if proposal.status != ChangeStatus.APPROVED:
            raise ApprovalRequiredError(
                "Proposal requires explicit human approval "
                "before it can be applied."
            )

        return self._verify(proposal)

    def run_first_attempt(
        self,
        proposal: ChangeProposal,
    ) -> VerificationResult:
        """
        Execute the initial approved proposal.
        """

        return self.execute_approved_attempt(
            proposal
        )

    def investigate_failure(
    self,
    *,
    repository_id: str,
    original_query: str,
    verification: VerificationResult,
) -> tuple[
    FailureAnalysis,
    Any,
]:
        """
        Analyze a failed verification and investigate the
        repository before generating a corrective proposal.
        """

        failure = analyze_verification_failure(
            verification
        )

        if not failure.has_failure:
            raise AutonomousFixError(
                "Cannot investigate a successful verification."
            )

        investigator = FailureInvestigator(
            repository_id=repository_id,
            repository_root=self.repository_root,
        )

        context = investigator.investigate(
            original_query=original_query,
            failure=failure,
        )

        return failure, context