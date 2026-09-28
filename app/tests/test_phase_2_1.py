from app.agent.graph import build_investigation_graph


def test_investigation_graph():
    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "test_repo",
            "query": "Where is UserService defined?",
        }
    )

    assert result["intent"] == "symbol_lookup"

    assert "UserService" in result["identifiers"]

    assert result["investigation_plan"]

    assert result["investigation_complete"] is True


def test_function_investigation():
    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "test_repo",
            "query": "How does process_order() work?",
        }
    )

    assert result["intent"] == (
        "function_explanation"
    )

    assert (
        "process_order"
        in result["identifiers"]
    )


def test_reference_investigation():
    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "test_repo",
            "query": "Where is process_order() called?",
        }
    )

    assert result["intent"] == (
        "reference_search"
    )

    assert (
        "reference_search"
        in result["investigation_plan"]
    )