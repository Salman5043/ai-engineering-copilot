"""v13.6 bounded AST cache invariants."""
from app.retrieval.reranker import _parse_source_definition, _source_node


def _candidate(content, language="python"):
    return {"content": content, "metadata": {"language": language, "symbol": "example"}}


def test_repeated_source_uses_cached_ast():
    _parse_source_definition.cache_clear()
    candidate = _candidate('def example():\n    return 1\n')
    first = _source_node(candidate)
    second = _source_node(dict(candidate))
    assert first is second
    assert first.name == "example"
    assert _parse_source_definition.cache_info().hits >= 1


def test_invalid_source_is_handled():
    assert _source_node(_candidate("def invalid(:")) is None


def test_non_python_source_is_not_parsed():
    assert _source_node(_candidate("def example(): pass", "javascript")) is None


def test_cache_has_finite_capacity():
    assert _parse_source_definition.cache_info().maxsize == 1024


def test_indented_method_parses():
    node = _source_node(_candidate("    def method(self):\n        return 1\n"))
    assert node.name == "method"
