from __future__ import annotations

from app.agent.evidence import add_evidence
from app.agent.evaluator import evaluate_investigation
from app.agent.planner import build_investigation_plan
from app.agent.state import InvestigationState
from app.agent.tools import TOOL_REGISTRY
from app.retrieval.query_intent import detect_intent
from app.retrieval.query_parser import parse_query
from app.agent.reasoner import generate_reasoned_answer

def generate_answer(
    state: InvestigationState,
) -> InvestigationState:
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
            state.get("errors", []) + [error]
        )

        state["answer"] = (
            "The repository investigation completed, "
            "but the reasoning model could not generate "
            "the final answer."
        )

    return state

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

    state["investigation_decision"] = "continue"
    state["investigation_reason"] = (
        "Investigation has not started yet."
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

        if tool_name == "symbol_search":

            if identifiers:
                results = tool(
                    repository_id=repository_id,
                    symbol=identifiers[0],
                )
            else:
                results = []

        elif tool_name == "reference_search":

            if identifiers:
                results = tool(
                    repository_id=repository_id,
                    symbol=identifiers[0],
                )
            else:
                results = []

        elif tool_name == "test_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        elif tool_name == "configuration_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        elif tool_name == "entrypoint_search":

            results = tool(
                repository_id=repository_id,
            )

        elif tool_name == "repository_search":

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        else:

            results = tool(
                repository_id=repository_id,
                query=query,
            )

        # -----------------------------------------------------
        # Normalize result container
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
        # Collect structured evidence
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
    # Advance investigation step
    # ---------------------------------------------------------
    state["current_step"] = current_step + 1

    # Don't decide completion here.
    #
    # Phase 2.5 introduces a separate evaluation node.
    state["needs_more_investigation"] = True
    state["investigation_complete"] = False

    return state


def evaluate_current_investigation(
    state: InvestigationState,
) -> InvestigationState:
    """
    Evaluate the evidence collected so far and determine
    whether the investigation should continue.
    """

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

    if evaluation.decision == "complete":
        state["needs_more_investigation"] = False
        state["investigation_complete"] = True
    else:
        state["needs_more_investigation"] = True
        state["investigation_complete"] = False

    return state