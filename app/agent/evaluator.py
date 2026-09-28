from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InvestigationEvaluation:
    """
    Result of evaluating the current investigation state.
    """

    decision: str
    reason: str


CONTINUE = "continue"
COMPLETE = "complete"


def _has_evidence_from_tool(
    evidence: list[dict[str, Any]],
    tool_name: str,
) -> bool:
    """
    Check whether at least one evidence item came from
    the specified investigation tool.
    """

    return any(
        item.get("source_tool") == tool_name
        for item in evidence
    )


def evaluate_investigation(
    *,
    intent: str,
    evidence: list[dict[str, Any]],
    executed_tools: list[str],
    current_step: int,
    max_steps: int,
) -> InvestigationEvaluation:
    """
    Deterministically decide whether the investigation
    should continue or finish.

    The evaluator does not use an LLM.

    It uses:
    - query intent
    - collected evidence
    - executed tools
    - remaining investigation steps
    """

    # ---------------------------------------------------------
    # No more planned tools
    # ---------------------------------------------------------
    if current_step >= max_steps:
        return InvestigationEvaluation(
            decision=COMPLETE,
            reason="All planned investigation steps have been executed.",
        )

    # ---------------------------------------------------------
    # Reference search
    # ---------------------------------------------------------
    if intent == "reference_search":
        if _has_evidence_from_tool(
            evidence,
            "reference_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Reference evidence was found; "
                    "the requested symbol references have been investigated."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "Reference evidence has not been collected yet; "
                "continue the investigation."
            ),
        )

    # ---------------------------------------------------------
    # Test discovery
    # ---------------------------------------------------------
    if intent == "test_discovery":
        if _has_evidence_from_tool(
            evidence,
            "test_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Relevant test evidence was collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "Test evidence has not been collected yet."
            ),
        )

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------
    if intent == "configuration":
        if _has_evidence_from_tool(
            evidence,
            "configuration_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Configuration evidence was collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "Configuration evidence has not been collected yet."
            ),
        )

    # ---------------------------------------------------------
    # Entrypoint discovery
    # ---------------------------------------------------------
    if intent == "entrypoint_discovery":
        if _has_evidence_from_tool(
            evidence,
            "entrypoint_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Entrypoint evidence was collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "Entrypoint evidence has not been collected yet."
            ),
        )

    # ---------------------------------------------------------
    # Symbol lookup
    # ---------------------------------------------------------
    if intent == "symbol_lookup":
        if _has_evidence_from_tool(
            evidence,
            "symbol_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "The requested symbol was located."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "The requested symbol has not been located yet."
            ),
        )

    # ---------------------------------------------------------
    # Function explanation
    # ---------------------------------------------------------
    if intent == "function_explanation":
        if _has_evidence_from_tool(
            evidence,
            "symbol_search",
        ) and _has_evidence_from_tool(
            evidence,
            "repository_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Function implementation and repository context "
                    "have been collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "More implementation or repository context "
                "is required."
            ),
        )

    # ---------------------------------------------------------
    # Architecture
    # ---------------------------------------------------------
    if intent == "architecture":
        if _has_evidence_from_tool(
            evidence,
            "repository_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Repository architecture evidence was collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "Architecture evidence has not been collected yet."
            ),
        )

    # ---------------------------------------------------------
    # Dependency search
    # ---------------------------------------------------------
    if intent == "dependency_search":
        if _has_evidence_from_tool(
            evidence,
            "repository_search",
        ):
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Dependency-related repository evidence was collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "Dependency evidence has not been collected yet."
            ),
        )

    # ---------------------------------------------------------
    # General search
    # ---------------------------------------------------------
    if intent == "general_search":
        if evidence:
            return InvestigationEvaluation(
                decision=COMPLETE,
                reason=(
                    "Relevant repository evidence was collected."
                ),
            )

        return InvestigationEvaluation(
            decision=CONTINUE,
            reason=(
                "No evidence has been collected yet."
            ),
        )

    # ---------------------------------------------------------
    # Generic fallback
    # ---------------------------------------------------------
    if evidence:
        return InvestigationEvaluation(
            decision=COMPLETE,
            reason=(
                "Evidence was collected for the investigation."
            ),
        )

    return InvestigationEvaluation(
        decision=CONTINUE,
        reason=(
            "No evidence has been collected; "
            "continue investigating."
        ),
    )