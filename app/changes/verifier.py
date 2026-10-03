from __future__ import annotations

from pathlib import Path

from app.changes.models import (
    ChangeProposal,
    VerificationResult,
    VerificationStatus,
)
from app.changes.test_discovery import (
    discover_related_tests,
)
from app.changes.test_runner import (
    TestExecutionError,
    TestRunner,
)


class ChangeVerifier:
    """
    Performs post-change verification.

    This class does not apply or modify patches.
    """

    def __init__(
        self,
        repository_root: Path,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.repository_root = (
            repository_root.resolve()
        )

        self.test_runner = TestRunner(
            repository_root=self.repository_root,
            timeout_seconds=timeout_seconds,
        )

    def select_tests(
        self,
        proposal: ChangeProposal,
    ) -> list[str]:
        """
        Select tests related to the changed files.
        """

        return discover_related_tests(
            self.repository_root,
            proposal.changed_files,
        )

    def verify(
        self,
        proposal: ChangeProposal,
    ) -> VerificationResult:
        """
        Run post-change verification.
        """

        if proposal.status.value != "applied":
            return VerificationResult(
                status=(
                    VerificationStatus.ERROR
                ),
                errors=[
                    "Only APPLIED proposals "
                    "can be verified."
                ],
            )

        tests = self.select_tests(
            proposal
        )

        if not tests:
            return VerificationResult(
                status=(
                    VerificationStatus.ERROR
                ),
                selected_tests=[],
                errors=[
                    "No tests were discovered "
                    "for verification."
                ],
            )

        try:
            result = (
                self.test_runner.run(
                    tests
                )
            )

        except TestExecutionError as exc:
            return VerificationResult(
                status=(
                    VerificationStatus.ERROR
                ),
                selected_tests=tests,
                errors=[
                    str(exc)
                ],
            )

        return VerificationResult(
            status=result.status,
            tests=[result],
            selected_tests=tests,
            errors=(
                []
                if result.status
                == VerificationStatus.PASSED
                else [
                    result.stderr
                    or result.stdout
                    or "Tests failed."
                ]
            ),
        )