from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class FileChange:
    """
    Represents a proposed modification to one repository file.
    """

    path: str
    original_content: str
    proposed_content: str

    reason: str = ""

    @property
    def is_modified(self) -> bool:
        return (
            self.original_content
            != self.proposed_content
        )


@dataclass
class ChangeProposal:
    """
    A complete, reviewable repository change proposal.
    """

    proposal_id: str

    repository_id: str

    description: str

    changes: list[FileChange] = field(
        default_factory=list
    )

    status: ChangeStatus = (
        ChangeStatus.PROPOSED
    )

    validation_errors: list[str] = field(
        default_factory=list
    )

    validation_warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def changed_files(self) -> list[str]:
        return [
            change.path
            for change in self.changes
            if change.is_modified
        ]

    @property
    def is_empty(self) -> bool:
        return not any(
            change.is_modified
            for change in self.changes
        )

    @property
    def is_valid(self) -> bool:
        return (
            not self.validation_errors
        )
    
    applied_files: list[str] = field(
    default_factory=list
    )

    backup_directory: str | None = None

    applied_at: str | None = None

    manifest: ChangeManifest | None = None




class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str
    path: str | None = None
    line: int | None = None


@dataclass
class ValidationResult:
    valid: bool

    issues: list[ValidationIssue] = field(
        default_factory=list
    )

    checked_files: list[str] = field(
        default_factory=list
    )

    discovered_tests: list[str] = field(
        default_factory=list
    )

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity
            == ValidationSeverity.ERROR
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity
            == ValidationSeverity.WARNING
        ]

@dataclass(frozen=True)
class ChangeManifest:
    """
    Records exactly what was modified by an applied proposal.
    """

    proposal_id: str
    repository_id: str

    changed_files: list[str]

    backup_directory: str | None = None

    applied_at: str | None = None

    rollback_available: bool = False

class VerificationStatus(str, Enum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    ERROR = "error"


@dataclass(frozen=True)
class TestResult:
    """
    Result of one test execution.
    """
    __test__ = False
    command: list[str]

    status: VerificationStatus

    return_code: int | None

    stdout: str

    stderr: str

    duration_seconds: float

    timed_out: bool = False


@dataclass
class VerificationResult:
    """
    Complete post-change verification result.
    """

    status: VerificationStatus

    tests: list[TestResult] = field(
        default_factory=list
    )

    selected_tests: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    rollback_performed: bool = False

    rollback_error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def passed(self) -> bool:
        return (
            self.status
            == VerificationStatus.PASSED
        )

    @property
    def failed(self) -> bool:
        return (
            self.status
            in {
                VerificationStatus.FAILED,
                VerificationStatus.TIMED_OUT,
                VerificationStatus.ERROR,
            }
        )