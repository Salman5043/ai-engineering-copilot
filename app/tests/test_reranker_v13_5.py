from types import SimpleNamespace
from app.retrieval.query_parser import parse_query
from app.retrieval.reranker import _v13_5_structural_ownership


def _candidate(content, symbol, path="app/core/owner.py", symbol_type="class"):
    return {"content": content, "metadata": {"file": path, "symbol": symbol, "symbol_type": symbol_type, "language": "python"}}


def test_class_owner_has_ast_evidence():
    candidate = _candidate('class ToolRegistry:\n    """Registry that discovers and stores tools."""\n    def discover_tools(self):\n        return []\n', "ToolRegistry")
    score = _v13_5_structural_ownership(candidate, parse_query("Where is the tool registry discovery implemented?"), SimpleNamespace(name="symbol_lookup"))
    assert score > 0


def test_test_file_is_not_boosted():
    candidate = _candidate('class ToolRegistry:\n    """Registry that discovers and stores tools."""\n    def discover_tools(self):\n        return []\n', "ToolRegistry", "app/tests/test_registry.py")
    assert _v13_5_structural_ownership(candidate, parse_query("Where is the tool registry discovery implemented?"), SimpleNamespace(name="symbol_lookup")) == 0


def test_reference_only_function_not_boosted():
    candidate = _candidate('def mention_registry():\n    """Registry discovery example."""\n    return "tool registry"\n', "mention_registry", symbol_type="function")
    assert _v13_5_structural_ownership(candidate, parse_query("Where is the tool registry discovery implemented?"), SimpleNamespace(name="symbol_lookup")) == 0


def test_general_search_not_boosted():
    candidate = _candidate('class ToolRegistry:\n    """Registry that discovers and stores tools."""\n    def discover_tools(self):\n        return []\n', "ToolRegistry")
    assert _v13_5_structural_ownership(candidate, parse_query("Where is the tool registry discovery implemented?"), SimpleNamespace(name="general_search")) == 0
