from app.retrieval.query_intent import detect_intent
from app.retrieval.query_parser import parse_query
from app.retrieval.reranker import rerank
from app.retrieval.retrieval_strategy import get_strategy


def _candidate(
    *,
    file: str,
    symbol: str = "",
    symbol_type: str = "",
    content: str = "",
    distance: float = 0.8,
):
    return {
        "content": content,
        "metadata": {
            "file": file,
            "symbol": symbol,
            "symbol_type": symbol_type,
        },
        "distance": distance,
    }


def test_exact_definition_beats_reference():
    query = "Where is retrieve defined?"

    intent = detect_intent(query)
    parsed = parse_query(query)
    strategy = get_strategy(intent.name)

    candidates = [
        _candidate(
            file="tests/test_search.py",
            content="retrieve(...) is used here",
            distance=0.4,
        ),
        _candidate(
            file="app/retrieval/retriever.py",
            symbol="retrieve",
            symbol_type="function",
            content="def retrieve(...):",
            distance=0.7,
        ),
    ]

    ranked = rerank(
        candidates,
        parsed,
        intent,
        strategy,
    )

    assert (
        ranked[0]["metadata"]["file"]
        == "app/retrieval/retriever.py"
    )


def test_architecture_query_prefers_graph_definition():
    query = "Where is the LangGraph workflow created?"

    intent = detect_intent(query)
    parsed = parse_query(query)
    strategy = get_strategy(intent.name)

    candidates = [
        _candidate(
            file="app/agent/nodes.py",
            symbol="execute_current_tool",
            symbol_type="function",
            content="LangGraph tool execution happens here",
            distance=0.45,
        ),
        _candidate(
            file="app/agent/graph.py",
            symbol="build_investigation_graph",
            symbol_type="function",
            content=(
                "StateGraph(...)"
                "\nworkflow"
                "\ngraph.compile()"
            ),
            distance=0.60,
        ),
    ]

    ranked = rerank(
        candidates,
        parsed,
        intent,
        strategy,
    )

    assert intent.name == "architecture"
    assert (
        ranked[0]["metadata"]["file"]
        == "app/agent/graph.py"
    )


def test_path_relevance_is_applied():
    query = "Where is MCP retry behavior implemented?"

    intent = detect_intent(query)
    parsed = parse_query(query)
    strategy = get_strategy(intent.name)

    candidates = [
        _candidate(
            file="app/mcp_client/client.py",
            content="MCP client operations",
            distance=0.5,
        ),
        _candidate(
            file="app/mcp_client/retry.py",
            symbol="RetryConfig",
            symbol_type="class",
            content="class RetryConfig:",
            distance=0.7,
        ),
    ]

    ranked = rerank(
        candidates,
        parsed,
        intent,
        strategy,
    )

    assert (
        ranked[0]["metadata"]["file"]
        == "app/mcp_client/retry.py"
    )