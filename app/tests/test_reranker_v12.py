"""Structural ownership tests: avoid hardcoded paths and query-specific IDs."""
from types import SimpleNamespace
import pytest
from app.retrieval.reranker import _ownership_evidence

LOOKUP = SimpleNamespace(name="symbol_lookup")

def query(text):
    return SimpleNamespace(raw_query=text, keywords=text.lower().split())

def candidate(symbol, kind, content, file="pkg/example.py"):
    return {"metadata": {"symbol": symbol, "symbol_type": kind,
                          "language": "python", "file": file}, "content": content}

def test_registry_class_owns_registration():
    owner = candidate("MCPToolRegistry", "class", "class MCPToolRegistry:\n    pass")
    helper = candidate("index_mcp_tools", "function", "def index_mcp_tools(tools):\n    return {}")
    q = query("Where are MCP tools registered?")
    assert _ownership_evidence(owner, q, LOOKUP) > _ownership_evidence(helper, q, LOOKUP)

def test_orchestrator_invokes_multiple_query_stages():
    q = query("Where is hybrid semantic and lexical retrieval with reranking implemented?")
    orchestrator = candidate("retrieve", "function", "def retrieve():\n    a = lexical_search()\n    return rerank(a)")
    helper = candidate("rerank", "function", "def rerank(items):\n    return sorted(items)")
    assert _ownership_evidence(orchestrator, q, LOOKUP) > _ownership_evidence(helper, q, LOOKUP)

def test_comments_do_not_count_as_calls():
    q = query("Where is semantic and lexical retrieval implemented?")
    c = candidate("retrieve", "function", "def retrieve():\n    # lexical_search() and semantic_search()\n    return None")
    assert _ownership_evidence(c, q, LOOKUP) == 0

def test_non_symbol_intent_gets_no_bonus():
    c = candidate("MCPToolRegistry", "class", "class MCPToolRegistry:\n    pass")
    assert _ownership_evidence(c, query("Where are tools registered?"), SimpleNamespace(name="architecture")) == 0

def test_registry_bonus_requires_class():
    c = candidate("MCPToolRegistry", "function", "def MCPToolRegistry():\n    return None")
    assert _ownership_evidence(c, query("Where are tools registered?"), LOOKUP) == 0
