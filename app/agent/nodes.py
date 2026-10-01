from __future__ import annotations

from typing import Any

from app.agent import tools
from app.agent.tools import TOOL_REGISTRY
from app.agent.evidence import add_evidence
from app.agent.reasoner import generate_reasoned_answer
from app.agent.planner import build_investigation_plan
from app.retrieval.query_parser import extract_identifiers
from app.retrieval.query_intent import detect_intent
from app.agent.tool_arguments import (
    build_tool_arguments,
)
from app.agent.mcp_integration import (
    execute_mcp_tool_sync,
)


# ============================================================
# Tool registry compatibility
# ============================================================

# Keep a reference to the original registry.
#
# This allows the test suite to monkeypatch either:
#
#   app.agent.nodes.TOOL_REGISTRY
#
# or:
#
#   app.agent.tools.TOOL_REGISTRY
#
# without breaking tool execution.
_ORIGINAL_TOOL_REGISTRY = TOOL_REGISTRY


# ============================================================
# Initialization
# ============================================================


def initialize_investigation(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Initialize a new repository investigation.
    """

    state.setdefault("intent", "")
    state.setdefault("intent_confidence", 0.0)

    state.setdefault("identifiers", [])
    state.setdefault("keywords", [])

    state.setdefault("investigation_plan", [])
    state.setdefault("current_step", 0)
    state.setdefault("max_steps", 0)
    state.setdefault("plan_reasons", {})

    state.setdefault("search_results", [])
    state.setdefault("evidence", [])
    state.setdefault("evidence_count", 0)

    state.setdefault("observations", [])
    state.setdefault("hypotheses", [])

    state.setdefault("reasoning", "")
    state.setdefault("reasoning_error", "")
    state.setdefault("answer", "")

    state.setdefault(
        "needs_more_investigation",
        True,
    )

    state.setdefault(
        "investigation_complete",
        False,
    )

    state.setdefault(
        "investigation_decision",
        "",
    )

    state.setdefault(
        "investigation_reason",
        "",
    )

    state.setdefault(
        "executed_tools",
        [],
    )

    state.setdefault(
        "tool_errors",
        [],
    )

    state.setdefault(
        "errors",
        [],
    )

    # --------------------------------------------------------
    # Phase 2.8 — Human-in-the-Loop
    # --------------------------------------------------------

    state.setdefault(
        "approval_required",
        False,
    )

    state.setdefault(
        "approval_status",
        "",
    )

    state.setdefault(
        "approval_message",
        "",
    )

    return state


# ============================================================
# Query analysis
# ============================================================


def analyze_query(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Analyze the developer query and determine its intent
    and important identifiers.
    """

    query = state["query"]

    try:
        intent_result = detect_intent(query)

        # ----------------------------------------------------
        # Tuple-based result
        # ----------------------------------------------------

        if isinstance(intent_result, tuple):

            intent = intent_result[0]

            confidence = (
                float(intent_result[1])
                if len(intent_result) > 1
                else 0.0
            )

        # ----------------------------------------------------
        # Dictionary-based result
        # ----------------------------------------------------

        elif isinstance(intent_result, dict):

            intent = intent_result.get(
                "intent",
                "general_search",
            )

            confidence = float(
                intent_result.get(
                    "confidence",
                    0.0,
                )
            )

        # ----------------------------------------------------
        # QueryIntent object
        #
        # Current detect_intent() returns a QueryIntent
        # instance with:
        #
        #   .name
        #   .confidence
        #   .matched_terms
        #
        # The graph state should store only the intent name
        # because the planner/evaluator expect a string.
        # ----------------------------------------------------

        elif hasattr(intent_result, "name"):

            intent = intent_result.name

            confidence = float(
                getattr(
                    intent_result,
                    "confidence",
                    0.0,
                )
            )

        # ----------------------------------------------------
        # Plain string / fallback
        # ----------------------------------------------------

        else:

            intent = str(intent_result)

            confidence = 0.0

        # ----------------------------------------------------
        # Normalize intent
        # ----------------------------------------------------

        if not isinstance(intent, str):
            intent = str(intent)

        intent = intent.strip()

        if not intent:
            intent = "general_search"

        state["intent"] = intent
        state["intent_confidence"] = confidence

    except Exception as exc:

        error = (
            f"Query intent detection failed: {exc}"
        )

        state["errors"] = (
            state.get("errors", [])
            + [error]
        )

        state["intent"] = "general_search"
        state["intent_confidence"] = 0.0

    # --------------------------------------------------------
    # Extract identifiers
    # --------------------------------------------------------

    try:

        identifiers_result = extract_identifiers(
            query
        )

        if isinstance(
            identifiers_result,
            dict,
        ):

            state["identifiers"] = identifiers_result.get(
                "identifiers",
                [],
            )

            state["keywords"] = identifiers_result.get(
                "keywords",
                [],
            )

        elif isinstance(
            identifiers_result,
            list,
        ):

            state["identifiers"] = identifiers_result
            state["keywords"] = []

        else:

            state["identifiers"] = []
            state["keywords"] = []

    except Exception as exc:

        error = (
            f"Query identifier extraction failed: {exc}"
        )

        state["errors"] = (
            state.get("errors", [])
            + [error]
        )

        state["identifiers"] = []
        state["keywords"] = []

    return state


# ============================================================
# Investigation planner
# ============================================================


def create_plan(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a deterministic investigation plan.
    """

    try:

        plan = build_investigation_plan(
            intent=state.get(
                "intent",
                "general_search",
            ),
            identifiers=state.get(
                "identifiers",
                [],
            ),
            keywords=state.get(
                "keywords",
                [],
            ),
        )

        state["investigation_plan"] = [
            step.tool_name
            for step in plan.steps
        ]

        state["plan_reasons"] = {
            step.tool_name: step.reason
            for step in plan.steps
        }

        state["max_steps"] = plan.max_steps

        state["current_step"] = 0

        state["needs_more_investigation"] = bool(
            plan.steps
        )

    except Exception as exc:

        error = (
            f"Investigation planning failed: {exc}"
        )

        state["errors"] = (
            state.get("errors", [])
            + [error]
        )

        state["investigation_plan"] = [
            "repository_search"
        ]

        state["plan_reasons"] = {
            "repository_search": (
                "Fallback repository search."
            )
        }

        state["max_steps"] = 1
        state["current_step"] = 0

        state["needs_more_investigation"] = True

    return state


# ============================================================
# Tool registry helper
# ============================================================


def _get_tool_registry() -> dict[str, Any]:
    """
    Return the active tool registry.

    The project historically exposed TOOL_REGISTRY through
    app.agent.nodes, while the canonical registry lives in
    app.agent.tools.

    Tests may monkeypatch either location, so support both.
    """

    # If nodes.TOOL_REGISTRY has been monkeypatched,
    # prefer that registry.
    if TOOL_REGISTRY is not _ORIGINAL_TOOL_REGISTRY:
        return TOOL_REGISTRY

    # Otherwise use the canonical registry from tools.py.
    return tools.TOOL_REGISTRY


# ============================================================
# Tool execution
# ============================================================


def execute_current_tool(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the current investigation tool.
    """

    plan = state.get(
        "investigation_plan",
        [],
    )

    current_step = state.get(
        "current_step",
        0,
    )

    # --------------------------------------------------------
    # No more tools
    # --------------------------------------------------------

    if current_step >= len(plan):

        state["needs_more_investigation"] = False
        state["investigation_complete"] = True

        return state

    tool_name = plan[current_step]

    # --------------------------------------------------------
    # Tool lookup
    # --------------------------------------------------------

    registry = _get_tool_registry()

    tool = registry.get(
        tool_name
    )

    if tool is None:

        error = (
            f"Unknown investigation tool: "
            f"{tool_name}"
        )

        state["tool_errors"] = (
            state.get("tool_errors", [])
            + [error]
        )

        state["errors"] = (
            state.get("errors", [])
            + [error]
        )

        state["executed_tools"] = (
            state.get("executed_tools", [])
            + [tool_name]
        )

        state["current_step"] = (
            current_step + 1
        )

        return state

    # --------------------------------------------------------
    # Execute tool
    # --------------------------------------------------------

    try:

        repository_id = state[
            "repository_id"
        ]

        query = state["query"]

        identifiers = state.get(
            "identifiers",
            [],
        )

        # ----------------------------------------------------
        # Symbol search
        # ----------------------------------------------------

        if tool_name == "symbol_search":

            symbol = (
                identifiers[0]
                if identifiers
                else query
            )

            results = tool(
                repository_id=repository_id,
                symbol=symbol,
            )

        # ----------------------------------------------------
        # Reference search
        # ----------------------------------------------------

        elif tool_name == "reference_search":

            symbol = (
                identifiers[0]
                if identifiers
                else query
            )

            results = tool(
                repository_id=repository_id,
                symbol=symbol,
            )

        # ----------------------------------------------------
        # Test search
        # ----------------------------------------------------

        elif tool_name == "test_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # ----------------------------------------------------
        # Configuration search
        # ----------------------------------------------------

        elif tool_name == "configuration_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # ----------------------------------------------------
        # Entrypoint search
        # ----------------------------------------------------

        elif tool_name == "entrypoint_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # ----------------------------------------------------
        # General repository search
        # ----------------------------------------------------

        else:

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # ----------------------------------------------------
        # Normalize None results
        # ----------------------------------------------------

        if results is None:
            results = []

        # ----------------------------------------------------
        # Store raw results
        # ----------------------------------------------------

        state["search_results"] = (
            state.get(
                "search_results",
                [],
            )
            + results
        )

        # ----------------------------------------------------
        # Convert raw results into structured evidence
        #
        # IMPORTANT:
        #
        # add_evidence() expects:
        #
        #   evidence_store
        #   results
        #   repository_id
        #   source_tool
        #
        # It performs normalize_evidence() internally.
        # ----------------------------------------------------

        state["evidence"] = add_evidence(
            state.get(
                "evidence",
                [],
            ),
            results,
            repository_id=repository_id,
            source_tool=tool_name,
        )

        # ----------------------------------------------------
        # Track execution
        # ----------------------------------------------------

        state["executed_tools"] = (
            state.get(
                "executed_tools",
                [],
            )
            + [tool_name]
        )

        state["current_step"] = (
            current_step + 1
        )

        state["evidence_count"] = len(
            state.get(
                "evidence",
                [],
            )
        )

    except Exception as exc:

        error = (
            f"Tool '{tool_name}' failed: "
            f"{exc}"
        )

        state["tool_errors"] = (
            state.get(
                "tool_errors",
                [],
            )
            + [error]
        )

        state["errors"] = (
            state.get(
                "errors",
                [],
            )
            + [error]
        )

        state["executed_tools"] = (
            state.get(
                "executed_tools",
                [],
            )
            + [tool_name]
        )

        state["current_step"] = (
            current_step + 1
        )

    return state


# ============================================================
# Investigation evaluator
# ============================================================


def evaluate_current_investigation(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate whether the investigation should continue.
    """

    from app.agent.evaluator import (
        COMPLETE,
        evaluate_investigation,
    )

    evaluation = evaluate_investigation(
        intent=state.get(
            "intent",
            "general_search",
        ),
        evidence=state.get(
            "evidence",
            [],
        ),
        executed_tools=state.get(
            "executed_tools",
            [],
        ),
        current_step=state.get(
            "current_step",
            0,
        ),
        max_steps=state.get(
            "max_steps",
            0,
        ),
    )

    state["investigation_decision"] = (
        evaluation.decision
    )

    state["investigation_reason"] = (
        evaluation.reason
    )

    if evaluation.decision == COMPLETE:

        state["needs_more_investigation"] = False
        state["investigation_complete"] = True

    else:

        state["needs_more_investigation"] = True
        state["investigation_complete"] = False

    return state


# ============================================================
# Phase 2.8 — Human-in-the-Loop
# ============================================================


def human_approval(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Pause the investigation workflow and mark it as waiting
    for human approval.

    This node deliberately does not approve or reject anything.
    The decision is supplied when the workflow is resumed.
    """

    state["approval_required"] = True

    state["approval_status"] = (
        state.get(
            "approval_status",
            "pending",
        )
        or "pending"
    )

    state["approval_message"] = (
        "The repository investigation has completed "
        "its evidence collection stage. "
        "Human approval is required before generating "
        "the final answer."
    )

    return state


# ============================================================
# Final LLM answer
# ============================================================


def generate_answer(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate the final evidence-grounded answer.
    """

    try:

        answer = generate_reasoned_answer(
            query=state["query"],
            intent=state.get(
                "intent",
                "general_search",
            ),
            evidence=state.get(
                "evidence",
                [],
            ),
        )

        state["reasoning"] = answer
        state["answer"] = answer
        state["reasoning_error"] = ""

    except Exception as exc:

        error = (
            f"LLM reasoning failed: {exc}"
        )

        state["reasoning_error"] = error

        state["errors"] = (
            state.get(
                "errors",
                []
            )
            + [error]
        )

        state["answer"] = (
            "The repository investigation completed, "
            "but the reasoning model could not generate "
            "the final answer."
        )

    return state
