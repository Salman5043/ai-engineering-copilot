"""v13.9: profiling must not change lexical retrieval behavior."""
import json
from types import SimpleNamespace
from app.retrieval import lexical_retriever as lr


def _query():
    return SimpleNamespace(raw_query="Where is retry implemented?",
                           keywords=["retry"], identifiers=["RetryConfig"],
                           definition_targets=["retry"])


def test_profile_records_stages_without_changing_results(monkeypatch, tmp_path):
    class Collection:
        def get(self, **kwargs):
            assert kwargs["where"] == {"repository_id": "repo_test"}
            return {"documents": ["retry configuration", "other unrelated text"],
                    "metadatas": [
                        {"file": "app/retry.py", "symbol": "RetryConfig", "symbol_type": "class"},
                        {"file": "app/other.py", "symbol": "other", "symbol_type": "function"},
                    ]}
    monkeypatch.setattr(lr, "get_collection", lambda: Collection())
    monkeypatch.delenv("COPILOT_LEXICAL_PROFILE_JSONL", raising=False)
    baseline = lr.lexical_search(repository_id="repo_test", parsed_query=_query())
    path = tmp_path / "profiles" / "lexical.jsonl"
    monkeypatch.setenv("COPILOT_LEXICAL_PROFILE_JSONL", str(path))
    profiled = lr.lexical_search(repository_id="repo_test", parsed_query=_query())
    assert profiled == baseline
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["candidate_count"] == 2
    assert record["result_count"] == len(profiled)
    for key in ("collection_get_ms", "candidate_scoring_ms", "bm25_ms",
                "normalization_sort_ms", "total_ms"):
        assert record[key] >= 0


def test_profile_empty_result(monkeypatch, tmp_path):
    class Collection:
        def get(self, **kwargs):
            return {"documents": [], "metadatas": []}
    monkeypatch.setattr(lr, "get_collection", lambda: Collection())
    path = tmp_path / "empty.jsonl"
    monkeypatch.setenv("COPILOT_LEXICAL_PROFILE_JSONL", str(path))
    assert lr.lexical_search(repository_id="repo_test", parsed_query=_query()) == []
    assert json.loads(path.read_text().strip())["candidate_count"] == 0
