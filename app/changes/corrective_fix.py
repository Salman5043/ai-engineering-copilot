from __future__ import annotations

from pathlib import Path
from typing import Any

from app.changes.failure_analysis import (
    FailureAnalysis,
)
from app.changes.investigation_context import (
    InvestigationContext,
)
from app.changes.llm_patch import (
    LLMPatchGenerator,
)


class CorrectiveFixError(RuntimeError):
    """Raised when a corrective fix cannot be generated."""


def _build_investigation_context(
    context: InvestigationContext,
) -> str:
    """
    Convert repository investigation results into a
    structured text block for the LLM.

    The LLM receives:
    - observations
    - hypotheses
    - tools used
    - repository evidence
    """

    parts: list[str] = []

    if context.observations:
        parts.append("Observations:")

        parts.extend(
            f"- {item}"
            for item in context.observations
        )

    if context.hypotheses:
        parts.append("")
        parts.append("Hypotheses:")

        parts.extend(
            f"- {item}"
            for item in context.hypotheses
        )

    if context.tools_used:
        parts.append("")
        parts.append(
            "Investigation tools used:"
        )

        parts.extend(
            f"- {tool}"
            for tool in context.tools_used
        )

    if context.errors:
        parts.append("")
        parts.append(
            "Investigation errors:"
        )

        parts.extend(
            f"- {error}"
            for error in context.errors
        )

    if context.evidence:
        parts.append("")
        parts.append(
            "Repository investigation evidence:"
        )

        for index, item in enumerate(
            context.evidence,
            start=1,
        ):
            parts.extend(
                [
                    "",
                    f"[Evidence {index}]",
                    (
                        "File: "
                        f"{item.get('file', '')}"
                    ),
                    (
                        "Lines: "
                        f"{item.get('start_line', '')}"
                        "-"
                        f"{item.get('end_line', '')}"
                    ),
                    (
                        "Symbol: "
                        f"{item.get('symbol', '')}"
                    ),
                    (
                        "Symbol type: "
                        f"{item.get('symbol_type', '')}"
                    ),
                    (
                        "Language: "
                        f"{item.get('language', '')}"
                    ),
                    (
                        "Tool: "
                        f"{item.get('source_tool', '')}"
                    ),
                    (
                        "Score: "
                        f"{item.get('score', '')}"
                    ),
                    "Content:",
                    str(
                        item.get(
                            "content",
                            "",
                        )
                    ),
                ]
            )

    if not parts:
        return (
            "No additional repository investigation "
            "evidence was collected."
        )

    return "\n".join(parts)


def _build_corrective_query(
    *,
    original_query: str,
    failure: FailureAnalysis,
    investigation_context: (
        InvestigationContext | None
    ) = None,
) -> str:
    """
    Build the corrective-fix request sent to the
    existing LLMPatchGenerator.

    The request contains:
    - original task
    - verification failure
    - failed test output
    - likely affected files
    - investigation evidence
    - strict corrective-fix requirements
    """

    parts: list[str] = [
        "Correct the previous code change.",
        "",
        "Original task:",
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

    if investigation_context is not None:
        parts.extend(
            [
                "",
                "Autonomous repository investigation:",
                _build_investigation_context(
                    investigation_context
                ),
            ]
        )

    parts.extend(
        [
            "",
            "Requirements:",
            (
                "- Analyze the verification failure "
                "before changing code."
            ),
            (
                "- Use repository investigation evidence "
                "when determining the root cause."
            ),
            (
                "- Fix the underlying cause rather than "
                "hiding or weakening the failing test."
            ),
            (
                "- Make the smallest reasonable correction."
            ),
            (
                "- Only modify files explicitly supplied "
                "to the patch generator."
            ),
            (
                "- Preserve existing project behavior "
                "outside the requested fix."
            ),
            (
                "- Do not modify secrets or sensitive "
                "configuration."
            ),
            (
                "- Do not invent files, symbols, APIs, "
                "or repository behavior."
            ),
            (
                "- Do not claim that tests pass unless "
                "the verification result proves it."
            ),
            (
                "- Return complete file contents for "
                "every proposed file change."
            ),
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
    investigation_context: (
        InvestigationContext | None
    ) = None,
    llm: Any | None = None,
):
    """
    Generate a corrective ChangeProposal from a failed
    verification attempt.

    This function does NOT modify repository files.

    The corrective proposal is generated from:

    1. Original developer request
    2. Verification failure
    3. Failed test output
    4. Likely affected files
    5. Repository investigation evidence

    Parameters
    ----------
    repository_id:
        Repository identifier.

    repository_root:
        Absolute repository root.

    original_query:
        Original developer request.

    failure:
        Structured failure analysis from verification.

    files:
        Repository files explicitly supplied to the
        patch generator.

    evidence:
        Existing repository evidence.

    investigation_context:
        Optional autonomous investigation results from
        Phase 4.8.

    llm:
        Optional LLM instance, primarily useful for tests.

    Returns
    -------
    ChangeProposal
        A proposed corrective code change.

    Raises
    ------
    CorrectiveFixError
        If the verification did not fail or no files
        were supplied.
    """

    if not failure.has_failure:
        raise CorrectiveFixError(
            "Corrective fix generation requires "
            "a failed verification."
        )

    if not files:
        raise CorrectiveFixError(
            "No repository files were supplied "
            "for corrective fix generation."
        )

    query = _build_corrective_query(
        original_query=original_query,
        failure=failure,
        investigation_context=(
            investigation_context
        ),
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

