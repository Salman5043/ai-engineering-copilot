import re

from app.retrieval.embeddings import embed_query
from app.retrieval.vector_store import search


# Common code concepts that are useful when searching repositories.
CODE_CONCEPTS = {
    "langgraph": {
        "stategraph",
        "add_node",
        "add_edge",
        "add_conditional_edges",
        "set_entry_point",
        "compile",
        "graph",
        "workflow",
    },
    "workflow": {
        "workflow",
        "graph",
        "stategraph",
        "compile",
        "add_node",
        "add_edge",
        "conditional_edges",
    },
    "agent": {
        "agent",
        "state",
        "tool",
        "graph",
        "node",
        "invoke",
    },
    "rag": {
        "retriever",
        "embedding",
        "vector",
        "chroma",
        "similarity",
        "document",
        "chunk",
    },
}


def normalize_text(value: str) -> str:
    """Normalize text for matching."""
    value = value.lower()
    value = re.sub(r"[^a-z0-9_]+", " ", value)
    return value


def extract_query_terms(query: str) -> set[str]:
    """
    Extract useful search terms from a natural-language query.
    """
    normalized = normalize_text(query)

    terms = set(normalized.split())

    # Add known code concepts based on the query.
    for concept, related_terms in CODE_CONCEPTS.items():
        if concept in normalized:
            terms.update(related_terms)

    return terms


def calculate_code_boost(
    query: str,
    result: dict,
) -> float:
    """
    Calculate a ranking boost for code-aware matches.

    Higher scores are given when:
    - The symbol name appears in the query.
    - Important code concepts appear in the chunk.
    - The file path contains query terms.
    - The symbol type is relevant.
    """

    metadata = result.get("metadata", {})

    symbol = str(metadata.get("symbol", "") or "")
    symbol_type = str(metadata.get("symbol_type", "") or "")
    file_path = str(metadata.get("file", "") or "")
    content = str(result.get("content", "") or "")

    query_normalized = normalize_text(query)
    query_terms = extract_query_terms(query)

    symbol_normalized = normalize_text(symbol)
    file_normalized = normalize_text(file_path)
    content_normalized = normalize_text(content)

    boost = 0.0

    # ---------------------------------------------------------
    # 1. Exact symbol match
    # ---------------------------------------------------------

    if symbol_normalized and symbol_normalized in query_normalized:
        boost += 0.35

    # ---------------------------------------------------------
    # 2. Strong code concept matches
    # ---------------------------------------------------------

    concept_matches = 0

    for term in query_terms:
        if len(term) < 3:
            continue

        if term in content_normalized:
            concept_matches += 1

    # Cap this contribution so a large function doesn't
    # automatically dominate the ranking.
    boost += min(concept_matches * 0.025, 0.20)

    # ---------------------------------------------------------
    # 3. File path matches
    # ---------------------------------------------------------

    for term in query_terms:
        if len(term) >= 4 and term in file_normalized:
            boost += 0.05

    # ---------------------------------------------------------
    # 4. Symbol type relevance
    # ---------------------------------------------------------

    if symbol_type:
        if "function" in symbol_type:
            boost += 0.03

        elif "class" in symbol_type:
            boost += 0.02

    # ---------------------------------------------------------
    # 5. Important LangGraph signals
    # ---------------------------------------------------------

    langgraph_terms = {
        "stategraph",
        "add_node",
        "add_edge",
        "compile",
        "set_entry_point",
        "add_conditional_edges",
    }

    langgraph_matches = sum(
        1
        for term in langgraph_terms
        if term in content_normalized
    )

    boost += min(langgraph_matches * 0.05, 0.25)

    return boost


def rerank_results(
    query: str,
    results: list[dict],
) -> list[dict]:
    """
    Rerank vector-search results using code-aware signals.

    Chroma distance is lower when results are more similar.
    We convert distance into a similarity score and then
    add code-aware boosts.
    """

    ranked = []

    for result in results:
        distance = float(result.get("distance", 1.0))

        # Cosine distance is approximately:
        # 0 = very similar
        # 1 = less similar
        semantic_score = 1.0 - distance

        code_boost = calculate_code_boost(
            query=query,
            result=result,
        )

        final_score = semantic_score + code_boost

        enriched_result = {
            **result,
            "semantic_score": round(semantic_score, 6),
            "code_boost": round(code_boost, 6),
            "score": round(final_score, 6),
        }

        ranked.append(enriched_result)

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return ranked


def retrieve(
    query: str,
    top_k: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """
    Retrieve and rerank relevant code chunks.

    Pipeline:

        Query
          ↓
        Embedding
          ↓
        ChromaDB retrieval
          ↓
        Code-aware reranking
          ↓
        Final results
    """

    query_embedding = embed_query(query)

    # Retrieve more candidates than requested.
    #
    # Example:
    # top_k = 5
    # retrieve 15 candidates
    #
    # This gives the reranker more candidates to work with.
    candidate_k = min(max(top_k * 3, 10), 50)

    results = search(
        query_embedding=query_embedding,
        n_results=candidate_k,
        where=where,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        metadata = metadata or {}

        output.append(
            {
                "content": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    # Code-aware reranking.
    ranked_results = rerank_results(
        query=query,
        results=output,
    )

    # Return only requested number of results.
    return ranked_results[:top_k]