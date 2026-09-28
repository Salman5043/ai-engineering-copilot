from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    analyze_query,
    create_plan,
    evaluate_current_investigation,
    execute_current_tool,
    generate_answer,
    initialize_investigation,
)
from app.agent.state import InvestigationState


def should_continue(
    state: InvestigationState,
) -> str:
    if state.get(
        "needs_more_investigation",
        False,
    ):
        return "execute_tool"

    return "generate_answer"


def build_investigation_graph():
    graph = StateGraph(
        InvestigationState
    )

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

    graph.add_edge(
        "execute_tool",
        "evaluate_investigation",
    )

    graph.add_conditional_edges(
        "evaluate_investigation",
        should_continue,
        {
            "execute_tool": "execute_tool",
            "generate_answer": "generate_answer",
        },
    )

    graph.add_edge(
        "generate_answer",
        END,
    )

    return graph.compile()