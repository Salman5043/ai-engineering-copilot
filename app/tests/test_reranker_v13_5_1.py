from types import SimpleNamespace
from app.retrieval.query_parser import parse_query
from app.retrieval.reranker import rerank, _v13_5_structural_ownership


def test_ast_owner_signal_still_available():
    candidate = {
        "content": 'class ToolRegistry:\n    """Registry that discovers and stores tools."""\n    def discover_tools(self):\n        return []\n',
        "metadata": {"file": "app/core/registry.py", "symbol": "ToolRegistry", "symbol_type": "class", "language": "python"},
    }
    query = parse_query("Where is the tool registry discovery implemented?")
    assert _v13_5_structural_ownership(candidate, query, SimpleNamespace(name="symbol_lookup")) > 0


def test_delegation_bonus_does_not_stack_with_structural_ownership(monkeypatch):
    import app.retrieval.reranker as module
    candidate = {
        "content": 'def execute_tool_with_retry():\n    """Execute tool retry behavior."""\n    retry_tool()\n    execute_retry()\n',
        "metadata": {"file": "app/core/client.py", "symbol": "execute_tool_with_retry", "symbol_type": "function", "language": "python"},
        "retrieval_score": 0.4,
    }
    monkeypatch.setattr(module, "_delegation_adjustments", lambda *args: {0: 0.40})
    monkeypatch.setattr(module, "_v13_5_structural_ownership", lambda *args: 0.12)
    query = parse_query("Where is tool retry behavior implemented?")
    strategy = SimpleNamespace(
        prefer_keyword_overlap=False, prefer_path_relevance=False,
        prefer_symbols=False, prefer_definitions=False, prefer_references=False,
        prefer_tests=False, prefer_configuration=False, prefer_dependencies=False,
        prefer_entrypoints=False, prefer_documentation=False,
    )
    result = rerank([candidate], query, SimpleNamespace(name="symbol_lookup"), strategy)
    assert result[0]["ranking_signals"]["delegation"] == 0.40
    assert result[0]["ranking_signals"]["v13_5_structural_ownership"] == 0.0
