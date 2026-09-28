from __future__ import annotations

from typing import Any

from app.retrieval.retriever import retrieve


def _normalize_result(result: Any) -> dict[str, Any]:
    """
    Convert a retrieval result into a stable evidence dictionary.

    This keeps the agent layer independent from the exact internal
    representation used by the retrieval layer.
    """

    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif hasattr(result, "__dict__"):
        data = dict(result.__dict__)
    elif isinstance(result, dict):
        data = dict(result)
    else:
        data = {"content": str(result)}

    return {
        "content": data.get("content", ""),
        "file": data.get("file", ""),
        "start_line": data.get("start_line"),
        "end_line": data.get("end_line"),
        "language": data.get("language"),
        "symbol": data.get("symbol"),
        "symbol_type": data.get("symbol_type"),
        "score": data.get("score"),
        "semantic_score": data.get("semantic_score"),
    }


def search_repository(
    repository_id: str,
    query: str,
    top_k: int = 5,
    language: str | None = None,
    symbol_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    General-purpose repository search.

    Uses the existing Phase 1.75 retrieval pipeline.
    """

    response = retrieve(
        repository_id=repository_id,
        query=query,
        top_k=top_k,
        language=language,
        symbol_type=symbol_type,
    )

    results = getattr(response, "results", response)

    return [_normalize_result(result) for result in results]


def find_symbol(
    repository_id: str,
    symbol: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Find where a symbol is defined or implemented.
    """

    return search_repository(
        repository_id=repository_id,
        query=f"Where is {symbol} defined?",
        top_k=top_k,
    )


def find_references(
    repository_id: str,
    symbol: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Find likely references/usages of a symbol.
    """

    return search_repository(
        repository_id=repository_id,
        query=f"Where is {symbol} called or referenced?",
        top_k=top_k,
    )


def find_tests(
    repository_id: str,
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Find tests related to a feature, symbol, or behavior.
    """

    return search_repository(
        repository_id=repository_id,
        query=f"Where are the tests for {query}?",
        top_k=top_k,
    )


def find_configuration(
    repository_id: str,
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Find configuration related to a feature or component.
    """

    return search_repository(
        repository_id=repository_id,
        query=f"Where is the configuration for {query}?",
        top_k=top_k,
    )


def find_entrypoint(
    repository_id: str,
    query: str = "application entrypoint startup main",
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Find likely application entrypoints.
    """

    return search_repository(
        repository_id=repository_id,
        query=query,
        top_k=top_k,
    )


TOOL_REGISTRY = {
    "repository_search": search_repository,
    "symbol_search": find_symbol,
    "reference_search": find_references,
    "test_search": find_tests,
    "configuration_search": find_configuration,
    "entrypoint_search": find_entrypoint,
}