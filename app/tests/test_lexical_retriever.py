from types import SimpleNamespace

import app.retrieval.lexical_retriever as lexical


def _parsed_query(
    *,
    raw_query: str,
    identifiers: list[str],
    keywords: list[str],
    definition_targets: list[str],
):
    return SimpleNamespace(
        raw_query=raw_query,
        identifiers=identifiers,
        keywords=keywords,
        definition_targets=definition_targets,
    )


def test_lexical_search_finds_exact_symbol(monkeypatch):
    class FakeCollection:
        def get(self, *, where, include):
            assert where == {
                "repository_id": "repo_test"
            }

            return {
                "ids": ["1", "2"],
                "documents": [
                    "def retrieve(repository_id, query):\n    ...",
                    "def search(query):\n    ...",
                ],
                "metadatas": [
                    {
                        "file": "app/retrieval/retriever.py",
                        "symbol": "retrieve",
                        "repository_id": "repo_test",
                    },
                    {
                        "file": "app/retrieval/vector_store.py",
                        "symbol": "search",
                        "repository_id": "repo_test",
                    },
                ],
            }

    monkeypatch.setattr(
        lexical,
        "get_collection",
        lambda: FakeCollection(),
    )

    query = _parsed_query(
        raw_query="Where is retrieve implemented?",
        identifiers=["retrieve"],
        keywords=["retrieve", "implemented"],
        definition_targets=["retrieve"],
    )

    results = lexical.lexical_search(
        repository_id="repo_test",
        parsed_query=query,
        top_k=5,
    )

    assert results
    assert (
        results[0]["metadata"]["symbol"]
        == "retrieve"
    )
    assert (
        results[0]["metadata"]["file"]
        == "app/retrieval/retriever.py"
    )


def test_lexical_search_finds_failure_investigator():
    parsed_query = _parsed_query(
        raw_query=(
            "Where is autonomous failure "
            "investigation implemented?"
        ),
        identifiers=[],
        keywords=[
            "autonomous",
            "failure",
            "investigation",
            "implemented",
        ],
        definition_targets=[
            "autonomous failure investigation",
            "investigation",
        ],
    )

    score, signals = lexical._candidate_score(
        file_path="app/changes/failure_investigator.py",
        symbol="FailureInvestigator",
        content=(
            "class FailureInvestigator:\n"
            "    def investigate(self):\n"
            "        ..."
        ),
        parsed_query=parsed_query,
    )

    assert score > 0
    assert "definition_target" in signals


def test_lexical_search_finds_path_tokens(monkeypatch):
    class FakeCollection:
        def get(self, *, where, include):
            return {
                "ids": ["1", "2"],
                "documents": [
                    "class RetryConfig:\n    ...",
                    "class MCPToolRegistry:\n    ...",
                ],
                "metadatas": [
                    {
                        "file": "app/mcp_client/retry.py",
                        "symbol": "RetryConfig",
                        "repository_id": "repo_test",
                    },
                    {
                        "file": "app/mcp_client/registry.py",
                        "symbol": "MCPToolRegistry",
                        "repository_id": "repo_test",
                    },
                ],
            }

    monkeypatch.setattr(
        lexical,
        "get_collection",
        lambda: FakeCollection(),
    )

    query = _parsed_query(
        raw_query="Where is MCP retry behavior implemented?",
        identifiers=[],
        keywords=[
            "mcp",
            "retry",
            "behavior",
            "implemented",
        ],
        definition_targets=[
            "mcp retry behavior",
            "retry",
        ],
    )

    results = lexical.lexical_search(
        repository_id="repo_test",
        parsed_query=query,
        top_k=5,
    )

    assert results
    assert (
        results[0]["metadata"]["file"]
        == "app/mcp_client/retry.py"
    )


def test_lexical_search_respects_top_k(monkeypatch):
    class FakeCollection:
        def get(self, *, where, include):
            return {
                "ids": ["1", "2", "3"],
                "documents": [
                    "retrieve function",
                    "retrieve helper",
                    "retrieve implementation",
                ],
                "metadatas": [
                    {
                        "file": "a.py",
                        "symbol": "retrieve",
                    },
                    {
                        "file": "b.py",
                        "symbol": "retrieve_helper",
                    },
                    {
                        "file": "c.py",
                        "symbol": "retrieve_impl",
                    },
                ],
            }

    monkeypatch.setattr(
        lexical,
        "get_collection",
        lambda: FakeCollection(),
    )

    query = _parsed_query(
        raw_query="retrieve",
        identifiers=["retrieve"],
        keywords=["retrieve"],
        definition_targets=["retrieve"],
    )

    results = lexical.lexical_search(
        repository_id="repo_test",
        parsed_query=query,
        top_k=2,
    )

    assert len(results) == 2