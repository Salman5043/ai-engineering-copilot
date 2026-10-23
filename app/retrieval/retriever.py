from __future__ import annotations

from typing import Any
import json
import os
import time
from pathlib import Path


def _profile_emit(record: dict[str, Any]) -> None:
    """Opt-in JSONL profiling; never affect retrieval when disabled."""
    path = os.environ.get("COPILOT_RETRIEVAL_PROFILE_JSONL")
    if not path:
        return
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # Profiling must not break production retrieval.


from app.retrieval.embeddings import embed_query
from app.retrieval.lexical_retriever import lexical_search
from app.retrieval.query_intent import detect_intent
from app.retrieval.query_parser import parse_query
from app.retrieval.reranker import rerank
from app.retrieval.retrieval_strategy import get_strategy
from app.retrieval.vector_store import search


def build_where(
    repository_id: str,
    language: str | None = None,
    symbol_type: str | None = None,
):
    conditions = [
        {
            "repository_id": repository_id,
        }
    ]

    if language:
        conditions.append(
            {
                "language": language,
            }
        )

    if symbol_type:
        conditions.append(
            {
                "symbol_type": symbol_type,
            }
        )

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions,
    }


def _search_candidates(
    *,
    query: str,
    where: dict[str, Any],
    n_results: int,
) -> list[dict[str, Any]]:
    """
    Execute one vector search and normalize its results.

    This helper allows the retriever to perform multiple complementary
    searches while keeping their result format consistent.
    """
    query_embedding = embed_query(query)

    raw_results = search(
        query_embedding=query_embedding,
        n_results=n_results,
        where=where,
    )

    documents = raw_results.get(
        "documents",
        [[]],
    )[0]

    metadatas = raw_results.get(
        "metadatas",
        [[]],
    )[0]

    distances = raw_results.get(
        "distances",
        [[]],
    )[0]

    candidates: list[dict[str, Any]] = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        candidates.append(
            {
                "content": document,
                "metadata": metadata or {},
                "distance": float(distance),
            }
        )

    return candidates


def _candidate_key(
    candidate: dict[str, Any],
) -> str:
    """
    Create a stable identity for a retrieved code chunk.

    Prefer repository, file, symbol, and line metadata. Fall back to
    content when metadata is incomplete.
    """
    metadata = candidate.get("metadata") or {}

    repository_id = str(
        metadata.get("repository_id", "")
    )

    file_path = str(
        metadata.get("file", "")
    )

    symbol = str(
        metadata.get("symbol", "")
    )

    start_line = str(
        metadata.get("start_line", "")
    )

    end_line = str(
        metadata.get("end_line", "")
    )

    content = str(
        candidate.get("content", "")
    )

    if (
        repository_id
        or file_path
        or symbol
        or start_line
        or end_line
    ):
        return "|".join(
            [
                repository_id,
                file_path,
                symbol,
                start_line,
                end_line,
            ]
        )

    return content


def _merge_candidates(
    candidate_groups: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Merge candidates from multiple retrieval strategies.

    Preserve semantic distances, lexical scores, and ranking signals
    when the same chunk appears in more than one candidate group.
    """
    merged: dict[str, dict[str, Any]] = {}

    for candidates in candidate_groups:
        for candidate in candidates:
            key = _candidate_key(candidate)
            incoming = dict(candidate)
            existing = merged.get(key)

            if existing is None:
                merged[key] = incoming
                continue

            combined = dict(existing)

            existing_distance = existing.get("distance")
            incoming_distance = incoming.get("distance")

            # Keep the strongest observed semantic distance.
            # A lexical-only candidate should not acquire a distance
            # merely because it was encountered by lexical retrieval.
            if incoming_distance is not None and (
                existing_distance is None
                or float(incoming_distance)
                < float(existing_distance)
            ):
                combined["distance"] = float(incoming_distance)

            for field, value in incoming.items():
                if field in {
                    "distance",
                    "ranking_signals",
                }:
                    continue

                if (
                    field not in combined
                    or combined[field] in (None, "", [], {})
                ):
                    combined[field] = value

                elif field in {
                    "lexical_score",
                    "bm25_score",
                    "retrieval_score",
                }:
                    try:
                        combined[field] = max(
                            float(combined[field]),
                            float(value),
                        )
                    except (TypeError, ValueError):
                        pass

            existing_signals = (
                existing.get("ranking_signals") or {}
            )
            incoming_signals = (
                incoming.get("ranking_signals") or {}
            )

            signals = dict(existing_signals)

            for signal_name, signal_value in (
                incoming_signals.items()
            ):
                if (
                    isinstance(signal_value, dict)
                    and isinstance(
                        signals.get(signal_name),
                        dict,
                    )
                ):
                    nested = dict(signals[signal_name])
                    nested.update(signal_value)
                    signals[signal_name] = nested

                elif signal_name not in signals:
                    signals[signal_name] = signal_value

            if signals:
                combined["ranking_signals"] = signals

            merged[key] = combined

    return list(merged.values())


def _build_definition_queries(
    *,
    original_query: str,
    definition_targets: list[str],
    concept_candidates: list[str] | None = None,
) -> list[str]:
    queries: list[str] = [original_query]
    seen = {original_query.casefold()}

    def add_query(value: str) -> None:
        value = " ".join(str(value).split()).strip()
        if not value:
            return

        normalized = value.casefold()
        if normalized not in seen:
            seen.add(normalized)
            queries.append(value)

    concepts = [
        " ".join(str(item).split()).strip()
        for item in (concept_candidates or [])
        if str(item).strip()
    ]

    # Prioritize natural-language concepts and meaningful subphrases.
    for concept in concepts:
        if "_" not in concept:
            add_query(f"{concept} definition")
            add_query(f"{concept} implementation")

    # Then try identifier-style forms.
    for concept in concepts:
        if "_" in concept:
            add_query(f"{concept} definition")
            add_query(f"{concept} implementation")

    # Finally, try explicit definition targets.
    for target in definition_targets:
        target = " ".join(str(target).split()).strip()
        if not target:
            continue

        add_query(f"{target} definition")
        add_query(f"{target} implementation")
        add_query(f"{target} function class")

    return queries


def retrieve(
    repository_id: str,
    query: str,
    top_k: int = 5,
    language: str | None = None,
    symbol_type: str | None = None,
):
    """
    Retrieve repository code chunks using semantic and lexical search,
    with definition-aware expansion and code-aware reranking.
    """
    _profile_enabled = bool(os.environ.get("COPILOT_RETRIEVAL_PROFILE_JSONL"))
    _t0 = time.perf_counter()
    _timings: dict[str, float] = {}
    intent = detect_intent(query)
    parsed_query = parse_query(query)
    strategy = get_strategy(intent.name)

    candidate_k = min(
        max(
            top_k * strategy.candidate_multiplier,
            10,
        ),
        100,
    )

    where = build_where(
        repository_id=repository_id,
        language=language,
        symbol_type=symbol_type,
    )

    _timings["query_analysis_ms"] = (time.perf_counter() - _t0) * 1000
    _t = time.perf_counter()

    # ---------------------------------------------------------
    # Primary semantic retrieval
    # ---------------------------------------------------------

    candidate_groups: list[
        list[dict[str, Any]]
    ] = []

    primary_candidates = _search_candidates(
        query=query,
        where=where,
        n_results=candidate_k,
    )

    candidate_groups.append(primary_candidates)
    _timings["primary_semantic_ms"] = (time.perf_counter() - _t) * 1000
    _t = time.perf_counter()

    # ---------------------------------------------------------
    # Definition-aware candidate expansion
    # ---------------------------------------------------------
    #
    # For implementation-location queries, semantic search may
    # favor related concepts rather than the actual definition.
    #
    # Supplemental queries use both concept candidates and
    # definition targets extracted by the query parser.
    # ---------------------------------------------------------

    definition_targets = getattr(
        parsed_query,
        "definition_targets",
        [],
    )

    concept_candidates = getattr(
        parsed_query,
        "concept_candidates",
        [],
    )

    if definition_targets or concept_candidates:
        definition_queries = _build_definition_queries(
            original_query=query,
            definition_targets=definition_targets,
            concept_candidates=concept_candidates,
        )

        # The original query has already been searched.
        supplemental_queries = definition_queries[1:]

        # Bound additional vector-search work.
        max_supplemental_queries = 6

        for definition_query in supplemental_queries[
            :max_supplemental_queries
        ]:
            candidates = _search_candidates(
                query=definition_query,
                where=where,
                n_results=min(
                    max(candidate_k, 10),
                    50,
                ),
            )

            candidate_groups.append(candidates)

    _timings["supplemental_semantic_ms"] = (time.perf_counter() - _t) * 1000
    _t = time.perf_counter()

    # ---------------------------------------------------------
    # Lexical retrieval
    # ---------------------------------------------------------
    #
    # Search indexed symbols, paths, and source text. This
    # provides a complementary candidate source for exact names
    # and repository-specific terminology.
    # ---------------------------------------------------------

    lexical_top_k = min(
        max(candidate_k * 4, 200),
        500,
    )

    lexical_candidates = lexical_search(
        repository_id=repository_id,
        parsed_query=parsed_query,
        top_k=lexical_top_k,
        language=language,
        symbol_type=symbol_type,
    )

    candidate_groups.append(lexical_candidates)
    _timings["lexical_ms"] = (time.perf_counter() - _t) * 1000
    _t = time.perf_counter()

    # ---------------------------------------------------------
    # Merge candidates
    # ---------------------------------------------------------

    candidates = _merge_candidates(candidate_groups)
    _timings["merge_ms"] = (time.perf_counter() - _t) * 1000
    _t = time.perf_counter()

    # ---------------------------------------------------------
    # Code-aware reranking
    # ---------------------------------------------------------

    ranked = rerank(
        candidates=candidates,
        parsed_query=parsed_query,
        intent=intent,
        strategy=strategy,
    )

    _timings["rerank_ms"] = (time.perf_counter() - _t) * 1000
    if _profile_enabled:
        _profile_emit({
            "query": query,
            "intent": getattr(intent, "name", str(intent)),
            "candidate_k": candidate_k,
            "primary_candidates": len(primary_candidates),
            "supplemental_searches": len(candidate_groups) - 2,
            "lexical_candidates": len(lexical_candidates),
            "merged_candidates": len(candidates),
            "total_ms": (time.perf_counter() - _t0) * 1000,
            "stages_ms": {k: round(v, 3) for k, v in _timings.items()},
        })

    return {
        "intent": intent,
        "parsed_query": parsed_query,
        "results": ranked[:top_k],
    }
