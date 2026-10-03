from __future__ import annotations

import shutil
from pathlib import Path


class BackupError(RuntimeError):
    """Raised when a backup operation fails."""


class BackupManager:
    """
    Creates and restores pre-change file snapshots.
    """

    def __init__(
        self,
        repository_root: Path,
        backup_root: Path | None = None,
    ) -> None:
        self.repository_root = (
            repository_root.resolve()
        )

        self.backup_root = (
            backup_root
            if backup_root is not None
            else (
                self.repository_root
                / ".copilot"
                / "backups"
            )
        ).resolve()

    def create_backup(
        self,
        *,
        proposal_id: str,
        paths: list[str],
    ) -> Path:
        """
        Create a backup snapshot for the supplied files.
        """

        backup_directory = (
            self.backup_root
            / proposal_id
        )

        backup_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            for relative_path in paths:
                source = (
                    self.repository_root
                    / relative_path
                ).resolve()

                try:
                    source.relative_to(
                        self.repository_root
                    )
                except ValueError as exc:
                    raise BackupError(
                        f"Backup path escapes repository: "
                        f"{relative_path}"
                    ) from exc

                if not source.exists():
                    continue

                if not source.is_file():
                    raise BackupError(
                        f"Backup source is not a file: "
                        f"{relative_path}"
                    )

                destination = (
                    backup_directory
                    / relative_path
                )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    source,
                    destination,
                )

        except Exception as exc:
            if isinstance(
                exc,
                BackupError,
            ):
                raise

            raise BackupError(
                "Failed to create change backup."
            ) from exc

        return backup_directory

    def restore_backup(
        self,
        *,
        backup_directory: Path,
        paths: list[str],
    ) -> None:
        """
        Restore backed-up files to the repository.
        """

        backup_directory = (
            backup_directory.resolve()
        )

        for relative_path in paths:
            backup_file = (
                backup_directory
                / relative_path
            ).resolve()

            target_file = (
                self.repository_root
                / relative_path
            ).resolve()

            try:
                backup_file.relative_to(
                    backup_directory
                )

                target_file.relative_to(
                    self.repository_root
                )

            except ValueError as exc:
                raise BackupError(
                    "Backup restore path escaped "
                    "its allowed directory."
                ) from exc

            if not backup_file.exists():
                continue

            target_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                backup_file,
                target_file,
            )