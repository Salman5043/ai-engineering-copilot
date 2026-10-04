from __future__ import annotations

from pathlib import Path
from typing import Any

from app.changes.failure_analysis import FailureAnalysis
from app.changes.llm_patch import (
    LLMPatchGenerator,
)


class CorrectiveFixError(RuntimeError):
    """Raised when a corrective fix cannot be generated."""


def _build_corrective_query(
    *,
    original_query: str,
    failure: FailureAnalysis,
) -> str:
    """
    Build a corrective-fix request for the existing
    LLM patch generator.

    The LLM receives the original task together with
    concrete verification failure information.
    """

    parts = [
        "Correct the previous code change.",
        "",
        f"Original task:",
        original_query,
        "",
        "Verification result:",
        failure.failure_summary,
    ]

    if failure.suggested_investigation:
        parts.extend(
            [
                "",
                "Investigation guidance:",
                failure.suggested_investigation,
            ]
        )

    if failure.likely_files:
        parts.extend(
            [
                "",
                "Likely affected files:",
                *(
                    f"- {path}"
                    for path in failure.likely_files
                ),
            ]
        )

    if failure.stdout:
        parts.extend(
            [
                "",
                "Test stdout:",
                failure.stdout,
            ]
        )

    if failure.stderr:
        parts.extend(
            [
                "",
                "Test stderr:",
                failure.stderr,
            ]
        )

    parts.extend(
        [
            "",
            "Requirements:",
            "- Analyze the verification failure before changing code.",
            "- Fix the underlying cause rather than hiding the test failure.",
            "- Make the smallest reasonable correction.",
            "- Only modify files explicitly supplied to the patch generator.",
            "- Preserve existing project behavior outside the requested fix.",
            "- Do not modify secrets or sensitive configuration.",
            "- Do not claim that tests pass unless the verification result proves it.",
        ]
    )

    return "\n".join(parts)


def generate_corrective_fix(
    *,
    repository_id: str,
    repository_root: Path,
    original_query: str,
    failure: FailureAnalysis,
    files: list[dict[str, str]],
    evidence: list[dict[str, Any]],
    llm: Any | None = None,
):
    """
    Generate a corrective ChangeProposal from a failed
    verification attempt.

    This function does not modify repository files.
    """

    if not failure.has_failure:
        raise CorrectiveFixError(
            "Corrective fix generation requires a failed verification."
        )

    if not files:
        raise CorrectiveFixError(
            "No repository files were supplied for corrective fix generation."
        )

    query = _build_corrective_query(
        original_query=original_query,
        failure=failure,
    )

    generator = LLMPatchGenerator(
        llm=llm,
    )

    return generator.generate(
        repository_id=repository_id,
        repository_root=repository_root,
        query=query,
        files=files,
        evidence=evidence,
    )