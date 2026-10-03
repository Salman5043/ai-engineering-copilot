from __future__ import annotations

from pathlib import Path

from app.changes.applier import (
    PatchApplicationError,
    SafePatchApplier,
)
from app.changes.models import (
    ChangeProposal,
    ChangeStatus,
    VerificationResult,
    VerificationStatus,
)
from app.changes.verifier import (
    ChangeVerifier,
)


class PostChangeVerificationError(RuntimeError):
    """
    Raised when verification or rollback fails.
    """


class ApplyAndVerify:
    """
    Coordinates:

        approved proposal
            ↓
        safe application
            ↓
        automated verification
            ↓
        rollback on failure
    """

    def __init__(
        self,
        repository_root: Path,
        test_timeout_seconds: float = 300.0,
    ) -> None:
        self.repository_root = (
            repository_root.resolve()
        )

        self.applier = SafePatchApplier(
            self.repository_root
        )

        self.verifier = ChangeVerifier(
            self.repository_root,
            timeout_seconds=(
                test_timeout_seconds
            ),
        )

    def execute(
        self,
        proposal: ChangeProposal,
    ) -> VerificationResult:
        """
        Apply and verify an approved proposal.

        If verification fails, automatically roll
        the repository back to its pre-change state.
        """

        try:
            self.applier.apply(
                proposal
            )

        except PatchApplicationError:
            raise

        verification = (
            self.verifier.verify(
                proposal
            )
        )

        if verification.passed:
            return verification

        rollback_error: str | None = None

        try:
            self.applier.rollback(
                proposal
            )

            verification.rollback_performed = (
                True
            )

        except Exception as exc:
            rollback_error = str(exc)

            verification.rollback_error = (
                rollback_error
            )

            raise PostChangeVerificationError(
                "Post-change verification failed "
                "and repository rollback failed."
            ) from exc

        return verification