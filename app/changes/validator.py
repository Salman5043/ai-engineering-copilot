from __future__ import annotations

from pathlib import Path

from app.changes.diff_validator import (
    validate_proposal_changes,
    validate_proposal_paths,
)
from app.changes.models import (
    ChangeProposal,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from app.changes.python_validator import (
    validate_python_ast,
    validate_python_syntax,
)
from app.changes.test_discovery import (
    discover_tests,
)


class PatchValidator:
    """
    Validates generated code changes without
    modifying the repository.
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
    ) -> ValidationResult:
        issues: list[
            ValidationIssue
        ] = []

        checked_files: list[str] = []

        issues.extend(
            validate_proposal_paths(
                proposal,
                self.repository_root,
            )
        )

        issues.extend(
            validate_proposal_changes(
                proposal
            )
        )

        for change in proposal.changes:
            if not change.is_modified:
                continue

            checked_files.append(
                change.path
            )

            if change.path.lower().endswith(
                ".py"
            ):
                issues.extend(
                    self._validate_python_file(
                        change.path,
                        change.proposed_content,
                    )
                )

        discovered_tests = (
            discover_tests(
                self.repository_root
            )
        )

        if not discovered_tests:
            issues.append(
                ValidationIssue(
                    severity=(
                        ValidationSeverity.WARNING
                    ),
                    code="NO_TESTS_FOUND",
                    message=(
                        "No test files were "
                        "discovered."
                    ),
                )
            )

        valid = not any(
            issue.severity
            == ValidationSeverity.ERROR
            for issue in issues
        )

        return ValidationResult(
            valid=valid,
            issues=issues,
            checked_files=checked_files,
            discovered_tests=(
                discovered_tests
            ),
        )

    def _validate_python_file(
        self,
        path: str,
        content: str,
    ) -> list[ValidationIssue]:
        issues: list[
            ValidationIssue
        ] = []

        syntax_issues = (
            validate_python_syntax(
                content,
                path=path,
            )
        )

        for (
            code,
            message,
            line,
        ) in syntax_issues:
            issues.append(
                ValidationIssue(
                    severity=(
                        ValidationSeverity.ERROR
                    ),
                    code=code,
                    message=message,
                    path=path,
                    line=line,
                )
            )

        # AST validation is only meaningful
        # if syntax parsing succeeded.
        if not syntax_issues:
            ast_issues = (
                validate_python_ast(
                    content,
                    path=path,
                )
            )

            for (
                code,
                message,
                line,
            ) in ast_issues:
                issues.append(
                    ValidationIssue(
                        severity=(
                            ValidationSeverity.ERROR
                        ),
                        code=code,
                        message=message,
                        path=path,
                        line=line,
                    )
                )

        return issues