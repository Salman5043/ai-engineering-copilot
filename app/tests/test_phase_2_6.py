from __future__ import annotations

from unittest.mock import patch

from app.agent.graph import build_investigation_graph
from app.agent.reasoner import (
    build_reasoning_prompt,
    generate_reasoned_answer,
)


def sample_evidence():
    return [
        {
            "evidence_id": "evidence_001",
            "content": (
                "def build_graph():\n"
                "    graph = StateGraph(State)\n"
                "    return graph.compile()"
            ),
            "file": "graph/graph_builder.py",
            "start_line": 8,
            "end_line": 10,
            "language": "python",
            "symbol": "build_graph",
            "symbol_type": "function",
            "source_tool": "symbol_search",
            "repository_id": "repo_test",
        }
    ]


def test_reasoning_prompt_contains_query():
    prompt = build_reasoning_prompt(
        query="Where is the LangGraph workflow created?",
        intent="symbol_lookup",
        evidence=sample_evidence(),
    )

    assert (
        "Where is the LangGraph workflow created?"
        in prompt
    )


def test_reasoning_prompt_contains_evidence():
    prompt = build_reasoning_prompt(
        query="Where is build_graph defined?",
        intent="symbol_lookup",
        evidence=sample_evidence(),
    )

    assert "graph/graph_builder.py" in prompt
    assert "build_graph" in prompt
    assert "StateGraph" in prompt


def test_reasoning_prompt_contains_source_tool():
    prompt = build_reasoning_prompt(
        query="Where is build_graph defined?",
        intent="symbol_lookup",
        evidence=sample_evidence(),
    )

    assert "symbol_search" in prompt


@patch(
    "app.agent.reasoner.get_llm"
)
def test_generate_reasoned_answer(
    mock_get_llm,
):
    class FakeResponse:
        content = (
            "`build_graph` is defined in "
            "`graph/graph_builder.py`."
        )

    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return FakeResponse()

    mock_get_llm.return_value = FakeLLM()

    answer = generate_reasoned_answer(
        query="Where is build_graph defined?",
        intent="symbol_lookup",
        evidence=sample_evidence(),
    )

    assert "build_graph" in answer
    assert "graph/graph_builder.py" in answer


@patch(
    "app.agent.nodes.generate_reasoned_answer"
)
def test_graph_generates_final_answer(
    mock_reasoner,
):
    mock_reasoner.return_value = (
        "`build_graph` is defined in "
        "`graph/graph_builder.py`."
    )

    graph = build_investigation_graph()

    state = {
        "repository_id": "repo_test",
        "query": "Where is build_graph defined?",
    }

    result = graph.invoke(state)

    assert result["investigation_complete"] is True
    assert result["answer"]
    assert "build_graph" in result["answer"]


@patch(
    "app.agent.nodes.generate_reasoned_answer"
)
def test_graph_stores_reasoning(
    mock_reasoner,
):
    mock_reasoner.return_value = (
        "The workflow is created by build_graph."
    )

    graph = build_investigation_graph()

    state = {
        "repository_id": "repo_test",
        "query": "Where is build_graph defined?",
    }

    result = graph.invoke(state)

    assert result["reasoning"] == (
        "The workflow is created by build_graph."
    )