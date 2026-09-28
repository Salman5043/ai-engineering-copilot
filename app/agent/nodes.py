from __future__ import annotations

from app.agent.evidence import add_evidence
from app.agent.planner import build_investigation_plan
from app.agent.state import InvestigationState
from app.agent.tools import TOOL_REGISTRY
from app.retrieval.query_intent import detect_intent
from app.retrieval.query_parser import parse_query


def initialize_investigation(
    state: InvestigationState,
) -> InvestigationState:
    """
    Initialize the investigation state.
    """

    state.setdefault("search_results", [])
    state.setdefault("evidence", [])
    state.setdefault("observations", [])
    state.setdefault("hypotheses", [])
    state.setdefault("errors", [])
    state.setdefault("executed_tools", [])
    state.setdefault("tool_errors", [])

    state["evidence_count"] = len(
        state.get("evidence", [])
    )

    state["investigation_complete"] = False
    state["needs_more_investigation"] = True

    return state


def analyze_query(
    state: InvestigationState,
) -> InvestigationState:
    """
    Analyze the developer query.
    """

    query = state["query"]

    intent = detect_intent(query)
    parsed = parse_query(query)

    state["intent"] = intent.name
    state["intent_confidence"] = intent.confidence
    state["identifiers"] = parsed.identifiers
    state["keywords"] = parsed.keywords

    return state


def create_plan(
    state: InvestigationState,
) -> InvestigationState:
    """
    Create the investigation plan.
    """

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

    return state


def execute_current_tool(
    state: InvestigationState,
) -> InvestigationState:
    """
    Execute the current investigation tool.

    Raw results are stored in search_results.

    Structured, deduplicated evidence is stored in evidence.
    """

    plan = state.get(
        "investigation_plan",
        [],
    )

    current_step = state.get(
        "current_step",
        0,
    )

    # ---------------------------------------------------------
    # Investigation already finished
    # ---------------------------------------------------------
    if current_step >= len(plan):
        state["needs_more_investigation"] = False
        state["investigation_complete"] = True

        return state

    tool_name = plan[current_step]

    # ---------------------------------------------------------
    # Resolve tool
    # ---------------------------------------------------------
    tool = TOOL_REGISTRY.get(tool_name)

    if tool is None:
        state.setdefault(
            "tool_errors",
            [],
        ).append(
            f"No tool registered for investigation step: {tool_name}"
        )

        state["current_step"] = current_step + 1

        if state["current_step"] >= len(plan):
            state["needs_more_investigation"] = False
            state["investigation_complete"] = True

        return state

    repository_id = state["repository_id"]
    query = state["query"]

    identifiers = state.get(
        "identifiers",
        [],
    )

    # ---------------------------------------------------------
    # Execute tool
    # ---------------------------------------------------------
    try:

        # -----------------------------------------------------
        # Symbol search
        # -----------------------------------------------------
        if tool_name == "symbol_search":

            if identifiers:
                results = tool(
                    repository_id=repository_id,
                    symbol=identifiers[0],
                )
            else:
                results = []

        # -----------------------------------------------------
        # Reference search
        # -----------------------------------------------------
        elif tool_name == "reference_search":

            if identifiers:
                results = tool(
                    repository_id=repository_id,
                    symbol=identifiers[0],
                )
            else:
                results = []

        # -----------------------------------------------------
        # Test search
        # -----------------------------------------------------
        elif tool_name == "test_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # -----------------------------------------------------
        # Configuration search
        # -----------------------------------------------------
        elif tool_name == "configuration_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # -----------------------------------------------------
        # Entrypoint search
        # -----------------------------------------------------
        elif tool_name == "entrypoint_search":

            results = tool(
                repository_id=repository_id,
            )

        # -----------------------------------------------------
        # Repository search
        # -----------------------------------------------------
        elif tool_name == "repository_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # -----------------------------------------------------
        # Defensive fallback
        # -----------------------------------------------------
        else:

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # -----------------------------------------------------
        # Ensure results are a list
        # -----------------------------------------------------
        if results is None:
            results = []

        if not isinstance(results, list):
            results = list(results)

        # -----------------------------------------------------
        # Store raw search results
        # -----------------------------------------------------
        state.setdefault(
            "search_results",
            [],
        ).extend(results)

        # -----------------------------------------------------
        # Convert results into structured evidence
        # -----------------------------------------------------
        state["evidence"] = add_evidence(
            state.setdefault(
                "evidence",
                [],
            ),
            results,
            repository_id=repository_id,
            source_tool=tool_name,
        )

        # -----------------------------------------------------
        # Update evidence count
        # -----------------------------------------------------
        state["evidence_count"] = len(
            state["evidence"]
        )

        # -----------------------------------------------------
        # Record successful tool execution
        # -----------------------------------------------------
        state.setdefault(
            "executed_tools",
            [],
        ).append(tool_name)

    except Exception as exc:

        state.setdefault(
            "tool_errors",
            [],
        ).append(
            f"{tool_name}: {exc}"
        )

    # ---------------------------------------------------------
    # Move to next investigation step
    # ---------------------------------------------------------
    state["current_step"] = current_step + 1

    # ---------------------------------------------------------
    # Determine completion
    # ---------------------------------------------------------
    if state["current_step"] >= len(plan):

        state["needs_more_investigation"] = False
        state["investigation_complete"] = True

    else:

        state["needs_more_investigation"] = True
        state["investigation_complete"] = False

    return state