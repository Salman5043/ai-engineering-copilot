"""Regression tests for v13.4 implementation-location test suppression."""
from types import SimpleNamespace
from app.retrieval.reranker import rerank


def _candidate(file, symbol, content, retrieval_score=0.5):
    return {
        "metadata": {"file": file, "symbol": symbol, "symbol_type": "function", "language": "python"},
        "content": content,
        "distance": 0.5,
        "retrieval_score": retrieval_score,
    }


def _query(raw):
    return SimpleNamespace(raw_query=raw, identifiers=[], keywords=[], definition_targets=[])


def _strategy():
    return SimpleNamespace(
        prefer_definitions=False, prefer_references=False, prefer_symbols=False,
        prefer_tests=False, prefer_configuration=False, prefer_dependencies=False,
        prefer_entrypoints=False, prefer_documentation=False,
        prefer_keyword_overlap=False, prefer_path_relevance=False,
    )


def test_find_code_prefers_implementation_over_test_quote():
    query = _query("Find the code that compiles the LangGraph workflow.")
    test = _candidate("app/tests/test_graph.py", "test_graph", "def test_graph():\n    assert compile_graph()", 0.65)
    source = _candidate("app/agent/graph.py", "compile_graph", "def compile_graph():\n    return None", 0.60)
    ranked = rerank([test, source], query, SimpleNamespace(name="architecture"), _strategy())
    assert ranked[0]["metadata"]["file"] == "app/agent/graph.py"
    assert ranked[1]["ranking_signals"]["implementation_test_penalty"] == -0.55


def test_explicit_test_discovery_does_not_penalize_tests():
    query = _query("Find the code for the tests of graph compilation")
    test = _candidate("app/tests/test_graph.py", "test_graph", "def test_graph():\n    pass")
    ranked = rerank([test], query, SimpleNamespace(name="test_discovery"), _strategy())
    assert ranked[0]["ranking_signals"]["implementation_test_penalty"] == 0.0


def test_general_search_does_not_penalize_tests():
    query = _query("Find the code")
    test = _candidate("app/tests/test_graph.py", "test_graph", "def test_graph():\n    pass")
    ranked = rerank([test], query, SimpleNamespace(name="general_search"), _strategy())
    assert ranked[0]["ranking_signals"]["implementation_test_penalty"] == 0.0
