from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.checkpointer import get_checkpointer
from app.agent.nodes import (
    analyze_query,
    create_plan,
    evaluate_current_investigation,
    execute_current_tool,
    generate_answer,
    human_approval,
    initialize_investigation,
)
from app.agent.state import InvestigationState


def should_continue(
    state: InvestigationState,
) -> str:
    """
    Decide whether another investigation tool should run.
    """

    if state.get(
        "needs_more_investigation",
        False,
    ):
        return "execute_tool"

    return "next"


def after_human_approval(
    state: InvestigationState,
) -> str:
    """
    Decide what to do after the human approval state
    has been supplied.
    """

    status = state.get(
        "approval_status",
        "pending",
    )

    if status == "approved":
        return "generate_answer"

    if status == "rejected":
        return END

    # Still pending.
    # The graph should remain at the approval stage.
    return END


def build_investigation_graph(
    *,
    enable_hitl: bool = False,
):
    """
    Build the repository investigation graph.

    Normal mode:
        build_investigation_graph()

    HITL mode:
        build_investigation_graph(enable_hitl=True)

    HITL mode enables LangGraph checkpointing and therefore
    requires a configurable thread_id when invoking the graph.
    """

    graph = StateGraph(
        InvestigationState
    )

    # ---------------------------------------------------------
    # Core nodes
    # ---------------------------------------------------------

    graph.add_node(
        "initialize",
        initialize_investigation,
    )

    graph.add_node(
        "analyze_query",
        analyze_query,
    )

    graph.add_node(
        "create_plan",
        create_plan,
    )

    graph.add_node(
        "execute_tool",
        execute_current_tool,
    )

    graph.add_node(
        "evaluate_investigation",
        evaluate_current_investigation,
    )

    graph.add_node(
        "generate_answer",
        generate_answer,
    )

    # ---------------------------------------------------------
    # Start
    # ---------------------------------------------------------

    graph.add_edge(
        START,
        "initialize",
    )

    graph.add_edge(
        "initialize",
        "analyze_query",
    )

    graph.add_edge(
        "analyze_query",
        "create_plan",
    )

    graph.add_edge(
        "create_plan",
        "execute_tool",
    )

    # ---------------------------------------------------------
    # Tool → evaluator
    # ---------------------------------------------------------

    graph.add_edge(
        "execute_tool",
        "evaluate_investigation",
    )

    # ---------------------------------------------------------
    # Investigation loop
    # ---------------------------------------------------------

    graph.add_conditional_edges(
        "evaluate_investigation",
        should_continue,
        {
            "execute_tool": "execute_tool",

            "next": (
                "human_approval"
                if enable_hitl
                else "generate_answer"
            ),
        },
    )

    # ---------------------------------------------------------
    # HITL
    # ---------------------------------------------------------

    if enable_hitl:

        graph.add_node(
            "human_approval",
            human_approval,
        )

        graph.add_conditional_edges(
            "human_approval",
            after_human_approval,
            {
                "generate_answer": "generate_answer",
                END: END,
            },
        )

    # ---------------------------------------------------------
    # Final answer
    # ---------------------------------------------------------

    graph.add_edge(
        "generate_answer",
        END,
    )

    # ---------------------------------------------------------
    # Compile
    # ---------------------------------------------------------

    if enable_hitl:

        return graph.compile(
            checkpointer=get_checkpointer(),
        )

    # IMPORTANT:
    # Existing Phase 2.1–2.7 tests use graph.invoke()
    # without configurable.thread_id.
    #
    # Therefore normal mode must NOT use a checkpointer.

    return graph.compile()