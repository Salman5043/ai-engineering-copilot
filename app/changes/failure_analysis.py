from __future__ import annotations

from dataclasses import dataclass, field

from app.changes.models import (
    TestResult,
    VerificationResult,
    VerificationStatus,
)


@dataclass(frozen=True)
class FailedTest:
    command: list[str]
    return_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float


@dataclass
class FailureAnalysis:
    status: VerificationStatus

    failed_tests: list[FailedTest] = field(
        default_factory=list
    )

    failure_summary: str = ""

    stdout: str = ""
    stderr: str = ""

    likely_files: list[str] = field(
        default_factory=list
    )

    suggested_investigation: str = ""

    @property
    def has_failure(self) -> bool:
        return self.status in {
            VerificationStatus.FAILED,
            VerificationStatus.TIMED_OUT,
            VerificationStatus.ERROR,
        }


def _extract_likely_files(
    result: VerificationResult,
) -> list[str]:
    """
    Extract likely Python repository files from pytest output.

    Handles common pytest/traceback formats such as:

        app/example.py:42: AssertionError
        tests/test_example.py:15
        E   app/example.py:42
    """

    candidates: list[str] = []

    text_parts: list[str] = []

    for test in result.tests:
        text_parts.append(test.stdout)
        text_parts.append(test.stderr)

    combined = "\n".join(text_parts)

    for line in combined.splitlines():
        line = line.strip()

        if not line:
            continue

        # Look for a Python file followed by a line number.
        #
        # Example:
        #   app/example.py:42: AssertionError
        #
        # We find the ".py:" boundary and preserve ".py".
        marker = ".py:"

        if marker not in line:
            continue

        prefix = line.split(marker, 1)[0]

        # Keep only the final whitespace-delimited token.
        path = prefix.split()[-1]

        # Remove common pytest traceback prefixes.
        path = path.lstrip("./\\")

        if not path.endswith(".py"):
            path = f"{path}.py"

        if path not in candidates:
            candidates.append(path)

    return candidates


def _build_failure_summary(
    result: VerificationResult,
) -> str:
    if result.status == VerificationStatus.TIMED_OUT:
        return (
            "The selected tests exceeded the configured "
            "execution timeout."
        )

    if result.status == VerificationStatus.ERROR:
        return (
            "The test runner encountered an execution error "
            "while verifying the change."
        )

    failed_count = sum(
        1
        for test in result.tests
        if test.status != VerificationStatus.PASSED
    )

    if failed_count == 1:
        return "One test execution failed."

    return f"{failed_count} test executions failed."


def _build_investigation(
    result: VerificationResult,
    likely_files: list[str],
) -> str:
    if result.status == VerificationStatus.TIMED_OUT:
        return (
            "Investigate the test execution timeout and determine "
            "whether the change introduced an execution or performance issue."
        )

    if result.status == VerificationStatus.ERROR:
        return (
            "Investigate the test runner error before generating "
            "another code change."
        )

    if likely_files:
        files = ", ".join(likely_files[:10])

        return (
            "Investigate the failing test output and the affected "
            f"repository files: {files}."
        )

    return (
        "Investigate the failing test output and identify the "
        "repository code responsible for the failure."
    )


def analyze_verification_failure(
    result: VerificationResult,
) -> FailureAnalysis:
    """
    Convert a failed verification result into structured
    evidence for the next investigation/fix cycle.
    """

    failed_tests: list[FailedTest] = []

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for test in result.tests:
        if test.status == VerificationStatus.PASSED:
            continue

        failed_tests.append(
            FailedTest(
                command=list(test.command),
                return_code=test.return_code,
                stdout=test.stdout,
                stderr=test.stderr,
                duration_seconds=test.duration_seconds,
            )
        )

        if test.stdout:
            stdout_parts.append(test.stdout)

        if test.stderr:
            stderr_parts.append(test.stderr)

    stdout = "\n".join(stdout_parts)
    stderr = "\n".join(stderr_parts)

    likely_files = _extract_likely_files(result)

    return FailureAnalysis(
        status=result.status,
        failed_tests=failed_tests,
        failure_summary=_build_failure_summary(result),
        stdout=stdout,
        stderr=stderr,
        likely_files=likely_files,
        suggested_investigation=_build_investigation(
            result,
            likely_files,
        ),
    )