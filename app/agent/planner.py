from __future__ import annotations

from dataclasses import dataclass

from app.agent.tools import TOOL_REGISTRY


@dataclass(frozen=True)
class PlanStep:
    tool_name: str
    reason: str


@dataclass(frozen=True)
class InvestigationPlan:
    steps: list[PlanStep]
    max_steps: int


def _add_step(
    steps: list[PlanStep],
    tool_name: str,
    reason: str,
) -> None:
    """
    Add a tool to the plan only if the tool is registered
    and has not already been added.
    """
    if tool_name not in TOOL_REGISTRY:
        return

    if any(step.tool_name == tool_name for step in steps):
        return

    steps.append(
        PlanStep(
            tool_name=tool_name,
            reason=reason,
        )
    )


def build_investigation_plan(
    intent: str,
    identifiers: list[str] | None = None,
    keywords: list[str] | None = None,
) -> InvestigationPlan:
    """
    Build a deterministic investigation plan from the
    detected query intent and extracted query information.

    The planner is repository-agnostic and only uses
    tools registered in TOOL_REGISTRY.
    """

    identifiers = identifiers or []
    keywords = keywords or []

    steps: list[PlanStep] = []

    has_identifier = bool(identifiers)

    # ---------------------------------------------------------
    # Symbol lookup
    # ---------------------------------------------------------
    if intent == "symbol_lookup":
        if has_identifier:
            _add_step(
                steps,
                "symbol_search",
                "Locate the requested symbol definition.",
            )

        _add_step(
            steps,
            "repository_search",
            "Collect surrounding repository context.",
        )

    # ---------------------------------------------------------
    # Function explanation
    # ---------------------------------------------------------
    elif intent == "function_explanation":
        if has_identifier:
            _add_step(
                steps,
                "symbol_search",
                "Locate the function implementation.",
            )

        _add_step(
            steps,
            "repository_search",
            "Collect related implementation context.",
        )

    # ---------------------------------------------------------
    # Reference search
    # ---------------------------------------------------------
    elif intent == "reference_search":
        if has_identifier:
            _add_step(
                steps,
                "symbol_search",
                "First locate the referenced symbol.",
            )

            _add_step(
                steps,
                "reference_search",
                "Find calls and references to the symbol.",
            )

        _add_step(
            steps,
            "repository_search",
            "Collect additional repository context.",
        )

    # ---------------------------------------------------------
    # Test discovery
    # ---------------------------------------------------------
    elif intent == "test_discovery":
        if has_identifier:
            _add_step(
                steps,
                "symbol_search",
                "Locate the implementation being tested.",
            )

        _add_step(
            steps,
            "test_search",
            "Locate relevant tests.",
        )

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------
    elif intent == "configuration":
        _add_step(
            steps,
            "configuration_search",
            "Locate configuration sources.",
        )

        _add_step(
            steps,
            "repository_search",
            "Collect surrounding configuration context.",
        )

    # ---------------------------------------------------------
    # Entrypoint discovery
    # ---------------------------------------------------------
    elif intent == "entrypoint_discovery":
        _add_step(
            steps,
            "entrypoint_search",
            "Locate application startup and entrypoint code.",
        )

        _add_step(
            steps,
            "repository_search",
            "Collect surrounding startup context.",
        )

    # ---------------------------------------------------------
    # Dependency search
    # ---------------------------------------------------------
    elif intent == "dependency_search":
        _add_step(
            steps,
            "repository_search",
            "Search dependency manifests and dependency-related code.",
        )

    # ---------------------------------------------------------
    # Architecture
    # ---------------------------------------------------------
    elif intent == "architecture":
        _add_step(
            steps,
            "repository_structure",
            "Inspect the repository structure and identify major components.",
        )
        _add_step(
            steps,
            "repository_search",
            "Search the repository for architectural components and entrypoints.",
        )

    # ---------------------------------------------------------
    # General search
    # ---------------------------------------------------------
    elif intent == "general_search":
        _add_step(
            steps,
            "search_text",
            "Search the repository directly for relevant code and text.",
        )
        _add_step(
            steps,
            "repository_search",
            "Collect semantic repository context around the search results.",
        )

    # Safety fallback.
    if not steps:
        _add_step(
            steps,
            "repository_search",
            "Fallback repository search.",
        )

    return InvestigationPlan(
        steps=steps,
        max_steps=len(steps),
    )