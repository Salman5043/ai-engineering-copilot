from __future__ import annotations

from typing import Any

from app.retrieval.retriever import retrieve


class RetrievalResults(list[dict[str, Any]]):
    """List-compatible retrieval results with optional query intent metadata."""

    def __init__(self, values: list[dict[str, Any]], intent: str | None = None):
        super().__init__(values)
        self.intent = intent


def _normalize_result(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif isinstance(result, dict):
        data = dict(result)
    else:
        data = dict(getattr(result, "__dict__", {}))

    metadata = data.get("metadata") or {}
    return {
        "content": data.get("content", ""),
        "file": metadata.get("file", data.get("file", "")),
        "start_line": metadata.get("start_line", data.get("start_line")),
        "end_line": metadata.get("end_line", data.get("end_line")),
        "language": metadata.get("language", data.get("language")),
        "symbol": metadata.get("symbol", data.get("symbol")),
        "symbol_type": metadata.get("symbol_type", data.get("symbol_type")),
        "score": data.get("score"),
        "semantic_score": data.get("semantic_score"),
        "parent_symbol": metadata.get("parent_symbol"),
        "qualified_symbol": metadata.get("qualified_symbol"),
    }


def _intent_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("name")
    elif hasattr(value, "name"):
        value = value.name
    if value is None:
        return None
    if hasattr(value, "value"):
        value = value.value
    return str(value)


def real_repository_retriever(
    repository_id: str,
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    response = retrieve(repository_id=repository_id, query=query, top_k=top_k)
    intent = None
    if isinstance(response, dict):
        results = response.get("results", [])
        intent = _intent_name(response.get("intent"))
    elif isinstance(response, list):
        results = response
    else:
        results = getattr(response, "results", [])
        intent = _intent_name(getattr(response, "intent", None))
    return RetrievalResults([_normalize_result(result) for result in results], intent=intent)
