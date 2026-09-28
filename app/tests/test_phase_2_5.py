from app.agent.evaluator import (
    COMPLETE,
    CONTINUE,
    evaluate_investigation,
)
from app.agent.graph import build_investigation_graph


def make_evidence(
    source_tool: str,
) -> dict:
    return {
        "evidence_id": f"evidence_{source_tool}",
        "content": "example evidence",
        "file": "example.py",
        "start_line": 1,
        "end_line": 10,
        "language": "python",
        "symbol": "example",
        "symbol_type": "function",
        "score": 0.9,
        "semantic_score": 0.8,
        "source_tool": source_tool,
        "repository_id": "repo_123",
    }


def test_reference_search_continues_before_reference_evidence():
    evaluation = evaluate_investigation(
        intent="reference_search",
        evidence=[
            make_evidence("symbol_search"),
        ],
        executed_tools=[
            "symbol_search",
        ],
        current_step=1,
        max_steps=3,
    )

    assert evaluation.decision == CONTINUE


def test_reference_search_completes_after_reference_evidence():
    evaluation = evaluate_investigation(
        intent="reference_search",
        evidence=[
            make_evidence("symbol_search"),
            make_evidence("reference_search"),
        ],
        executed_tools=[
            "symbol_search",
            "reference_search",
        ],
        current_step=2,
        max_steps=3,
    )

    assert evaluation.decision == COMPLETE


def test_symbol_lookup_completes_after_symbol_evidence():
    evaluation = evaluate_investigation(
        intent="symbol_lookup",
        evidence=[
            make_evidence("symbol_search"),
        ],
        executed_tools=[
            "symbol_search",
        ],
        current_step=1,
        max_steps=2,
    )

    assert evaluation.decision == COMPLETE


def test_configuration_requires_configuration_evidence():
    evaluation = evaluate_investigation(
        intent="configuration",
        evidence=[
            make_evidence("repository_search"),
        ],
        executed_tools=[
            "repository_search",
        ],
        current_step=1,
        max_steps=2,
    )

    assert evaluation.decision == CONTINUE


def test_configuration_completes_with_configuration_evidence():
    evaluation = evaluate_investigation(
        intent="configuration",
        evidence=[
            make_evidence("configuration_search"),
        ],
        executed_tools=[
            "configuration_search",
        ],
        current_step=1,
        max_steps=2,
    )

    assert evaluation.decision == COMPLETE


def test_no_remaining_steps_completes():
    evaluation = evaluate_investigation(
        intent="reference_search",
        evidence=[],
        executed_tools=[],
        current_step=3,
        max_steps=3,
    )

    assert evaluation.decision == COMPLETE


def test_general_search_completes_with_evidence():
    evaluation = evaluate_investigation(
        intent="general_search",
        evidence=[
            make_evidence("repository_search"),
        ],
        executed_tools=[
            "repository_search",
        ],
        current_step=1,
        max_steps=1,
    )

    assert evaluation.decision == COMPLETE


def test_evaluation_contains_reason():
    evaluation = evaluate_investigation(
        intent="symbol_lookup",
        evidence=[],
        executed_tools=[],
        current_step=0,
        max_steps=1,
    )

    assert evaluation.reason

def test_graph_records_investigation_decision(
    monkeypatch,
):
    from app.agent import tools

    def fake_symbol_search(**kwargs):
        return [
            make_evidence("symbol_search")
        ]

    monkeypatch.setitem(
        tools.TOOL_REGISTRY,
        "symbol_search",
        fake_symbol_search,
    )

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "repo_123",
            "query": "Where is UserService defined?",
        }
    )

    assert result["investigation_decision"] == COMPLETE
    assert result["investigation_complete"] is True
    assert result["needs_more_investigation"] is False


def test_graph_can_continue_to_next_tool(
    monkeypatch,
):
    from app.agent import tools

    executed = []

    def fake_symbol_search(**kwargs):
        executed.append("symbol_search")

        return [
            make_evidence("symbol_search")
        ]

    def fake_reference_search(**kwargs):
        executed.append("reference_search")

        return [
            make_evidence("reference_search")
        ]

    monkeypatch.setitem(
        tools.TOOL_REGISTRY,
        "symbol_search",
        fake_symbol_search,
    )

    monkeypatch.setitem(
        tools.TOOL_REGISTRY,
        "reference_search",
        fake_reference_search,
    )

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "repo_123",
            "query": "Where is process_order() called?",
        }
    )

    assert "symbol_search" in executed
    assert "reference_search" in executed

    assert result["investigation_complete"] is True

    assert result["investigation_decision"] == COMPLETE