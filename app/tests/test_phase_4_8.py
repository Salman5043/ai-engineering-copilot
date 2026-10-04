from __future__ import annotations

from pathlib import Path

from app.changes.failure_investigator import (
    FailureInvestigator,
)
from app.changes.investigation_context import (
    build_investigation_context,
)
from app.changes.failure_analysis import (
    analyze_verification_failure,
)
from app.changes.models import (
    TestResult,
    VerificationResult,
    VerificationStatus,
)


def build_failure():
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

    return VerificationResult(
        status=VerificationStatus.FAILED,
        tests=[test_result],
        selected_tests=[
            "tests/test_example.py",
        ],
    )


def test_investigation_context_contains_failure():
    verification = build_failure()

    failure = analyze_verification_failure(
        verification
    )

    context = build_investigation_context(
        original_query="Fix example function.",
        failure=failure,
    )

    assert context.failure_summary
    assert (
        "tests/test_example.py"
        in context.failed_tests[0]
    )


def test_failure_investigator_collects_evidence(
    tmp_path: Path,
    monkeypatch,
):
    verification = build_failure()

    failure = analyze_verification_failure(
        verification
    )

    investigator = FailureInvestigator(
        repository_id="demo",
        repository_root=tmp_path,
    )

    def fake_search(
        query: str,
        *,
        top_k: int = 5,
    ):
        return [
            {
                "file": "app/example.py",
                "start_line": 1,
                "end_line": 10,
                "symbol": "example",
                "content": (
                    "def example():\n"
                    "    return 1\n"
                ),
            }
        ]

    monkeypatch.setattr(
        investigator,
        "_search",
        fake_search,
    )

    context = investigator.investigate(
        original_query="Fix example function.",
        failure=failure,
    )

    assert len(context.evidence) > 0

    assert (
        "implementation_search"
        in context.tools_used
    )

    assert (
        "failure_context_search"
        in context.tools_used
    )