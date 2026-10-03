from __future__ import annotations

from pathlib import Path

from app.changes.models import (
    ChangeProposal,
    ChangeStatus,
)
from app.changes.proposal import (
    generate_proposal_diff,
)
from app.changes.safety import (
    ChangeSafetyError,
    validate_change_path,
)
from app.changes.validator import (
    PatchValidator,
)
from app.changes.applier import (
    SafePatchApplier,
)
class ChangeManager:
    """
    Controls the lifecycle of repository changes.

    Phase 4.1 intentionally does NOT apply changes.
    """

    def __init__(
        self,
        repository_root: Path,
    ) -> None:
        self.repository_root = (
            repository_root.resolve()
        )

    def validate(
        self,
        proposal: ChangeProposal,
    ) -> ChangeProposal:
        """
        Validate a change proposal without modifying files.
        """

        proposal.validation_errors.clear()
        proposal.validation_warnings.clear()

        if proposal.is_empty:
            proposal.validation_errors.append(
                "Proposal contains no modified files."
            )

        for change in proposal.changes:
            try:
                validate_change_path(
                    self.repository_root,
                    change.path,
                )
            except ChangeSafetyError as exc:
                proposal.validation_errors.append(
                    str(exc)
                )
                continue

            if not change.is_modified:
                proposal.validation_warnings.append(
                    f"No content change: {change.path}"
                )

        if proposal.validation_errors:
            proposal.status = (
                ChangeStatus.FAILED
            )
        else:
            proposal.status = (
                ChangeStatus.VALIDATED
            )

        return proposal

    def diff(
        self,
        proposal: ChangeProposal,
    ) -> str:
        return generate_proposal_diff(
            proposal
        )

    def approve(
        self,
        proposal: ChangeProposal,
    ) -> ChangeProposal:
        """
        Mark a validated proposal as approved.

        Approval does not modify files.
        """

        if proposal.status != (
            ChangeStatus.VALIDATED
        ):
            raise ValueError(
                "Only validated proposals "
                "can be approved."
            )

        proposal.status = (
            ChangeStatus.APPROVED
        )

        return proposal

    def reject(
        self,
        proposal: ChangeProposal,
    ) -> ChangeProposal:
        proposal.status = (
            ChangeStatus.REJECTED
        )

        return proposal

    def apply(
    self,
    proposal: ChangeProposal,
) -> ChangeProposal:
        """
        Apply an approved proposal safely.
        """

        applier = SafePatchApplier(
            self.repository_root
        )

        return applier.apply(
            proposal
        )


    def rollback(
        self,
        proposal: ChangeProposal,
    ) -> ChangeProposal:
        """
        Roll back an applied proposal.
        """

        applier = SafePatchApplier(
            self.repository_root
        )

        return applier.rollback(
            proposal
        )

    def validate_patch(
    self,
    proposal: ChangeProposal,
):
        """
        Run the complete Phase 4.3 validation pipeline.
        """

        validator = PatchValidator(
            self.repository_root
        )

        result = validator.validate(
            proposal
        )

        proposal.validation_errors.clear()
        proposal.validation_warnings.clear()

        for issue in result.issues:
            if (
                issue.severity.value
                == "error"
            ):
                proposal.validation_errors.append(
                    issue.message
                )

            elif (
                issue.severity.value
                == "warning"
            ):
                proposal.validation_warnings.append(
                    issue.message
                )

        if result.valid:
            proposal.status = (
                ChangeStatus.VALIDATED
            )
        else:
            proposal.status = (
                ChangeStatus.FAILED
            )

        return result