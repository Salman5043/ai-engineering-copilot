from app.agent.graph import build_investigation_graph
from app.agent.tools import (
    find_configuration,
    find_entrypoint,
    find_references,
    find_symbol,
    find_tests,
    search_repository,
)


def test_tool_registry_contains_core_tools():
    from app.agent.tools import TOOL_REGISTRY

    assert "repository_search" in TOOL_REGISTRY
    assert "symbol_search" in TOOL_REGISTRY
    assert "reference_search" in TOOL_REGISTRY
    assert "test_search" in TOOL_REGISTRY
    assert "configuration_search" in TOOL_REGISTRY
    assert "entrypoint_search" in TOOL_REGISTRY


def test_graph_executes_symbol_search(monkeypatch):
    expected = [
        {
            "content": "class UserService:",
            "file": "services/user.py",
            "start_line": 10,
            "end_line": 20,
            "language": "python",
            "symbol": "UserService",
            "symbol_type": "class",
            "score": 0.9,
            "semantic_score": 0.85,
        }
    ]

    def fake_find_symbol(
        repository_id: str,
        symbol: str,
        top_k: int = 5,
    ):
        assert repository_id == "test_repo"
        assert symbol == "UserService"

        return expected

    monkeypatch.setattr(
        "app.agent.nodes.TOOL_REGISTRY",
        {
            "symbol_search": fake_find_symbol,
            "repository_search": lambda **kwargs: [],
        },
    )

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "test_repo",
            "query": "Where is UserService defined?",
        }
    )

    assert "symbol_search" in result["executed_tools"]
    assert result["search_results"] == expected


def test_graph_executes_reference_search(monkeypatch):
    expected = [
        {
            "content": "process_order(order)",
            "file": "orders/service.py",
            "start_line": 25,
            "end_line": 25,
            "language": "python",
            "symbol": None,
            "symbol_type": None,
            "score": 0.8,
            "semantic_score": 0.75,
        }
    ]

    def fake_find_references(
        repository_id: str,
        symbol: str,
        top_k: int = 10,
    ):
        assert repository_id == "test_repo"
        assert symbol == "process_order"

        return expected

    monkeypatch.setattr(
        "app.agent.nodes.TOOL_REGISTRY",
        {
            "symbol_search": lambda **kwargs: [],
            "repository_search": lambda **kwargs: [],
            "reference_search": fake_find_references,
        },
    )

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "test_repo",
            "query": "Where is process_order() called?",
        }
    )

    assert "reference_search" in result["executed_tools"]
    assert result["search_results"] == expected


def test_graph_records_tool_errors(monkeypatch):
    def failing_tool(**kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(
        "app.agent.nodes.TOOL_REGISTRY",
        {
            "symbol_search": failing_tool,
            "repository_search": lambda **kwargs: [],
        },
    )

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "test_repo",
            "query": "Where is UserService defined?",
        }
    )

    assert result["tool_errors"]
    assert "symbol_search" in result["tool_errors"][0]