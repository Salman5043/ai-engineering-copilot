from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.changes.failure_analysis import FailureAnalysis


@dataclass
class InvestigationContext:
    """
    Structured context collected while investigating
    a failed code change.

    This object deliberately contains no mutation state.
    It is evidence used to generate a corrective patch.
    """

    query: str

    failure_summary: str

    likely_files: list[str] = field(
        default_factory=list
    )

    failed_tests: list[str] = field(
        default_factory=list
    )

    evidence: list[dict[str, Any]] = field(
        default_factory=list
    )

    observations: list[str] = field(
        default_factory=list
    )

    hypotheses: list[str] = field(
        default_factory=list
    )

    tools_used: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )


def build_investigation_context(
    *,
    original_query: str,
    failure: FailureAnalysis,
) -> InvestigationContext:
    """
    Create an investigation context from the
    structured verification failure.
    """

    failed_tests = [
        " ".join(test.command)
        for test in failure.failed_tests
    ]

    return InvestigationContext(
        query=original_query,
        failure_summary=failure.failure_summary,
        likely_files=list(
            failure.likely_files
        ),
        failed_tests=failed_tests,
    )


def add_evidence(
    context: InvestigationContext,
    evidence: list[dict[str, Any]],
    *,
    source_tool: str,
) -> None:
    """
    Add repository evidence while recording its source.
    """

    for item in evidence:
        normalized = dict(item)

        normalized.setdefault(
            "source_tool",
            source_tool,
        )

        context.evidence.append(
            normalized
        )

    if source_tool not in context.tools_used:
        context.tools_used.append(
            source_tool
        )


def add_observation(
    context: InvestigationContext,
    observation: str,
) -> None:
    """
    Add a unique investigation observation.
    """

    if (
        observation
        and observation not in context.observations
    ):
        context.observations.append(
            observation
        )


def add_hypothesis(
    context: InvestigationContext,
    hypothesis: str,
) -> None:
    """
    Add a unique investigation hypothesis.
    """

    if (
        hypothesis
        and hypothesis not in context.hypotheses
    ):
        context.hypotheses.append(
            hypothesis
        )


def add_error(
    context: InvestigationContext,
    error: str,
) -> None:
    """
    Record an investigation error without
    stopping the entire investigation.
    """

    if error:
        context.errors.append(error)