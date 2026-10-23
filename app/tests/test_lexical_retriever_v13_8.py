"""v13.8 lexical optimizations: parity and repository filtering tests."""
from types import SimpleNamespace

from app.retrieval import lexical_retriever as lr


def _query():
    return SimpleNamespace(
        raw_query="Where is retry behavior implemented?",
        keywords=["retry", "behavior"],
        identifiers=["RetryConfig"],
        definition_targets=["retry"],
    )


def test_prepared_candidate_score_matches_legacy_path():
    query = _query()
    args = dict(file_path="app/mcp_client/retry.py", symbol="RetryConfig",
                content="class RetryConfig: retry failures", parsed_query=query,
                symbol_type="class")
    expected = lr._candidate_score(**args)
    prepared = {
        "terms": lr._query_terms(query),
        "keywords": [lr._meaningful_tokens("retry"), lr._meaningful_tokens("behavior")],
        "identifiers": [lr._meaningful_tokens(lr._CAMEL_BOUNDARY.sub(" ", "RetryConfig"))],
        "definition_targets": [lr._meaningful_tokens("retry")],
        "implementation": lr._is_implementation_query(query),
        "raw_query": query.raw_query,
    }
    tokens = (lr._meaningful_tokens("Retry Config"),
              lr._meaningful_tokens(args["file_path"]),
              lr._meaningful_tokens(args["content"]))
    actual = lr._candidate_score(**args, prepared_query=prepared, prepared_tokens=tokens)
    assert actual == expected


def test_prepared_bm25_matches_legacy_path():
    query = _query()
    records = [
        {"metadata": {"file": "app/mcp_client/retry.py", "symbol": "RetryConfig"},
         "content": "class RetryConfig: retry failures"},
        {"metadata": {"file": "app/mcp_client/client.py", "symbol": "execute_tool"},
         "content": "execute tool with retry"},
    ]
    tokens = [(
        lr._meaningful_tokens(lr._CAMEL_BOUNDARY.sub(" ", r["metadata"]["symbol"])),
        lr._meaningful_tokens(r["metadata"]["file"]),
        lr._meaningful_tokens(r["content"]),
    ) for r in records]
    assert lr._bm25_scores(records, query) == lr._bm25_scores(
        records, query, prepared_terms=lr._query_terms(query), prepared_tokens=tokens)


def test_search_keeps_repository_filter_and_output(monkeypatch):
    class Collection:
        def get(self, **kwargs):
            assert kwargs["where"] == {"repository_id": "repo_123"}
            return {"documents": ["retry configuration", "unrelated text"],
                    "metadatas": [
                        {"file": "app/retry.py", "symbol": "RetryConfig", "language": "python", "symbol_type": "class"},
                        {"file": "app/other.py", "symbol": "other", "language": "python", "symbol_type": "function"},
                    ]}
    monkeypatch.setattr(lr, "get_collection", lambda: Collection())
    results = lr.lexical_search(repository_id="repo_123", parsed_query=_query(),
                                top_k=5, language="python", symbol_type="class")
    assert len(results) == 1
    assert results[0]["metadata"]["file"] == "app/retry.py"
    assert "bm25_score" in results[0]
    assert "retrieval_score" in results[0]
    assert "ranking_signals" in results[0]
