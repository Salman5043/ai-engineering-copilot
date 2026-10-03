from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.changes.backup import (
    BackupManager,
)
from app.changes.models import (
    ChangeManifest,
    ChangeProposal,
    ChangeStatus,
)
from app.changes.safety import (
    ChangeSafetyError,
    validate_change_path,
)
from app.changes.writer import (
    atomic_write,
)


class PatchApplicationError(RuntimeError):
    """Raised when a patch cannot be safely applied."""


class SafePatchApplier:
    """
    Applies only human-approved change proposals.

    Safety guarantees:

    - proposal must be APPROVED
    - paths must remain inside repository
    - protected files cannot be modified
    - backups are created before modification
    - writes are atomic
    - failed application attempts are rolled back
    """

    def __init__(
        self,
        repository_root: Path,
        backup_manager: BackupManager | None = None,
    ) -> None:
        self.repository_root = (
            repository_root.resolve()
        )

        self.backup_manager = (
            backup_manager
            if backup_manager is not None
            else BackupManager(
                self.repository_root
            )
        )

    def _validate_proposal(
        self,
        proposal: ChangeProposal,
    ) -> list[Path]:
        if proposal.status != (
            ChangeStatus.APPROVED
        ):
            raise PatchApplicationError(
                "Only APPROVED proposals can be applied."
            )

        if proposal.is_empty:
            raise PatchApplicationError(
                "Cannot apply an empty proposal."
            )

        validated_paths: list[Path] = []

        for change in proposal.changes:
            try:
                path = validate_change_path(
                    self.repository_root,
                    change.path,
                )
            except ChangeSafetyError as exc:
                raise PatchApplicationError(
                    str(exc)
                ) from exc

            validated_paths.append(path)

        return validated_paths

    def apply(
        self,
        proposal: ChangeProposal,
    ) -> ChangeProposal:
        """
        Apply an approved proposal safely.

        Any failure during application triggers
        restoration from the pre-change backup.
        """

        self._validate_proposal(
            proposal
        )

        changed_files = [
            change.path
            for change in proposal.changes
            if change.is_modified
        ]

        if not changed_files:
            raise PatchApplicationError(
                "Proposal contains no actual file changes."
            )

        backup_directory = (
            self.backup_manager.create_backup(
                proposal_id=proposal.proposal_id,
                paths=changed_files,
            )
        )

        applied_files: list[str] = []

        try:
            for change in proposal.changes:
                if not change.is_modified:
                    continue

                target = validate_change_path(
                    self.repository_root,
                    change.path,
                )

                atomic_write(
                    target,
                    change.proposed_content,
                )

                applied_files.append(
                    change.path
                )

            applied_at = datetime.now(
                timezone.utc
            ).isoformat()

            proposal.applied_files = (
                applied_files
            )

            proposal.backup_directory = (
                str(backup_directory)
            )

            proposal.applied_at = (
                applied_at
            )

            proposal.manifest = (
                ChangeManifest(
                    proposal_id=(
                        proposal.proposal_id
                    ),
                    repository_id=(
                        proposal.repository_id
                    ),
                    changed_files=(
                        list(applied_files)
                    ),
                    backup_directory=(
                        str(backup_directory)
                    ),
                    applied_at=(
                        applied_at
                    ),
                    rollback_available=True,
                )
            )

            proposal.status = (
                ChangeStatus.APPLIED
            )

            return proposal

        except Exception as exc:
            proposal.status = (
                ChangeStatus.FAILED
            )

            try:
                self.backup_manager.restore_backup(
                    backup_directory=(
                        backup_directory
                    ),
                    paths=changed_files,
                )

                proposal.status = (
                    ChangeStatus.ROLLED_BACK
                )

            except Exception as rollback_exc:
                raise PatchApplicationError(
                    "Patch application failed and "
                    "automatic rollback also failed."
                ) from rollback_exc

            raise PatchApplicationError(
                "Patch application failed. "
                "Repository was restored from backup."
            ) from exc

    def rollback(
        self,
        proposal: ChangeProposal,
    ) -> ChangeProposal:
        """
        Explicitly restore an applied proposal.
        """

        if proposal.status != (
            ChangeStatus.APPLIED
        ):
            raise PatchApplicationError(
                "Only APPLIED proposals can be rolled back."
            )

        if not proposal.backup_directory:
            raise PatchApplicationError(
                "No backup is available for rollback."
            )

        backup_directory = Path(
            proposal.backup_directory
        )

        self.backup_manager.restore_backup(
            backup_directory=backup_directory,
            paths=proposal.applied_files,
        )

        proposal.status = (
            ChangeStatus.ROLLED_BACK
        )

        if proposal.manifest is not None:
            proposal.manifest = (
                ChangeManifest(
                    proposal_id=(
                        proposal.manifest.proposal_id
                    ),
                    repository_id=(
                        proposal.manifest.repository_id
                    ),
                    changed_files=(
                        proposal.manifest.changed_files
                    ),
                    backup_directory=(
                        proposal.manifest.backup_directory
                    ),
                    applied_at=(
                        proposal.manifest.applied_at
                    ),
                    rollback_available=False,
                )
            )

        return proposal