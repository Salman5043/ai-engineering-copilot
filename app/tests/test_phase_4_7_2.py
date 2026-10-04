from __future__ import annotations

from pathlib import Path

import pytest

from app.changes.corrective_fix import (
    CorrectiveFixError,
    generate_corrective_fix,
)
from app.changes.failure_analysis import (
    analyze_verification_failure,
)
from app.changes.llm_models import (
    PatchGenerationResponse,
    GeneratedFileChange,
)
from app.changes.models import (
    TestResult,
    VerificationResult,
    VerificationStatus,
)


class FakeStructuredLLM:
    def __init__(
        self,
        response: PatchGenerationResponse,
    ) -> None:
        self.response = response

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt: str):
        self.prompt = prompt
        return self.response


def build_failed_verification() -> VerificationResult:
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


def test_corrective_fix_requires_failure(
    tmp_path: Path,
):
    verification = VerificationResult(
        status=VerificationStatus.PASSED,
        tests=[],
    )

    failure = analyze_verification_failure(
        verification
    )

    with pytest.raises(CorrectiveFixError):
        generate_corrective_fix(
            repository_id="demo",
            repository_root=tmp_path,
            original_query="Fix the example function.",
            failure=failure,
            files=[
                {
                    "path": "app/example.py",
                    "content": "def example():\n    return 1\n",
                }
            ],
            evidence=[],
        )


def test_corrective_fix_requires_files(
    tmp_path: Path,
):
    verification = build_failed_verification()

    failure = analyze_verification_failure(
        verification
    )

    with pytest.raises(CorrectiveFixError):
        generate_corrective_fix(
            repository_id="demo",
            repository_root=tmp_path,
            original_query="Fix the example function.",
            failure=failure,
            files=[],
            evidence=[],
        )


def test_corrective_fix_generates_proposal(
    tmp_path: Path,
):
    example_file = tmp_path / "app" / "example.py"
    example_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    example_file.write_text(
        "def example():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    verification = build_failed_verification()

    failure = analyze_verification_failure(
        verification
    )

    fake_llm = FakeStructuredLLM(
        PatchGenerationResponse(
            description="Correct the failing example implementation.",
            changes=[
                GeneratedFileChange(
                    path="app/example.py",
                    proposed_content=(
                        "def example():\n"
                        "    return 2\n"
                    ),
                    reason=(
                        "The implementation returns the value "
                        "that caused the failing assertion."
                    ),
                )
            ],
        )
    )

    proposal = generate_corrective_fix(
        repository_id="demo",
        repository_root=tmp_path,
        original_query="Fix the example function.",
        failure=failure,
        files=[
            {
                "path": "app/example.py",
                "content": (
                    "def example():\n"
                    "    return 1\n"
                ),
            }
        ],
        evidence=[
            {
                "source_tool": "test_search",
                "file": "tests/test_example.py",
                "start_line": 1,
                "end_line": 20,
                "symbol": "test_example",
                "content": (
                    "def test_example():\n"
                    "    assert example() == 2\n"
                ),
            }
        ],
        llm=fake_llm,
    )

    assert proposal.repository_id == "demo"

    assert proposal.description == (
        "Correct the failing example implementation."
    )

    assert proposal.changed_files == [
        "app/example.py"
    ]

    assert proposal.changes[0].proposed_content == (
        "def example():\n"
        "    return 2\n"
    )

    prompt_text = str(fake_llm.prompt)

    assert "failed" in prompt_text.lower()
    assert "AssertionError" in prompt_text
    assert "app/example.py" in prompt_text


def test_corrective_fix_does_not_modify_files(
    tmp_path: Path,
):
    example_file = tmp_path / "app" / "example.py"
    example_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    original = (
        "def example():\n"
        "    return 1\n"
    )

    example_file.write_text(
        original,
        encoding="utf-8",
    )

    failure = analyze_verification_failure(
        build_failed_verification()
    )

    fake_llm = FakeStructuredLLM(
        PatchGenerationResponse(
            description="Fix example.",
            changes=[
                GeneratedFileChange(
                    path="app/example.py",
                    proposed_content=(
                        "def example():\n"
                        "    return 2\n"
                    ),
                    reason="Fix assertion failure.",
                )
            ],
        )
    )

    generate_corrective_fix(
        repository_id="demo",
        repository_root=tmp_path,
        original_query="Fix example.",
        failure=failure,
        files=[
            {
                "path": "app/example.py",
                "content": original,
            }
        ],
        evidence=[],
        llm=fake_llm,
    )

    assert example_file.read_text(
        encoding="utf-8"
    ) == original