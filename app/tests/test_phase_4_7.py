from __future__ import annotations

from app.changes.failure_analysis import (
    analyze_verification_failure,
)
from app.changes.models import (
    TestResult,
    VerificationResult,
    VerificationStatus,
)


def test_analyze_failed_verification():
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

    verification = VerificationResult(
        status=VerificationStatus.FAILED,
        tests=[test_result],
        selected_tests=[
            "tests/test_example.py",
        ],
    )

    analysis = analyze_verification_failure(
        verification
    )

    assert analysis.has_failure is True
    assert len(analysis.failed_tests) == 1
    assert "One test execution failed." in analysis.failure_summary
    assert "app/example.py" in analysis.likely_files
    assert "tests/test_example.py" in analysis.stdout


def test_analyze_timeout():
    test_result = TestResult(
        command=[
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_slow.py",
        ],
        status=VerificationStatus.TIMED_OUT,
        return_code=None,
        stdout="",
        stderr="timeout",
        duration_seconds=300.0,
        timed_out=True,
    )

    verification = VerificationResult(
        status=VerificationStatus.TIMED_OUT,
        tests=[test_result],
        selected_tests=[
            "tests/test_slow.py",
        ],
    )

    analysis = analyze_verification_failure(
        verification
    )

    assert analysis.has_failure is True
    assert (
        "timeout"
        in analysis.failure_summary.lower()
    )
    assert (
        "timeout"
        in analysis.suggested_investigation.lower()
    )


def test_success_has_no_failure():
    verification = VerificationResult(
        status=VerificationStatus.PASSED,
        tests=[],
    )

    analysis = analyze_verification_failure(
        verification
    )

    assert analysis.has_failure is False
    assert analysis.failed_tests == []