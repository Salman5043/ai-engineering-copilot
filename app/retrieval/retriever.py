from app.retrieval.embeddings import embed_query
from app.retrieval.query_intent import detect_intent
from app.retrieval.query_parser import parse_query
from app.retrieval.retrieval_strategy import get_strategy
from app.retrieval.reranker import rerank
from app.retrieval.vector_store import search


def build_where(
    repository_id: str,
    language: str | None = None,
    symbol_type: str | None = None,
):
    conditions = [
        {
            "repository_id": repository_id
        }
    ]

    if language:
        conditions.append(
            {
                "language": language
            }
        )

    if symbol_type:
        conditions.append(
            {
                "symbol_type": symbol_type
            }
        )

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }


def retrieve(
    repository_id: str,
    query: str,
    top_k: int = 5,
    language: str | None = None,
    symbol_type: str | None = None,
):
    intent = detect_intent(query)
    parsed_query = parse_query(query)
    strategy = get_strategy(intent.name)

    candidate_k = min(
        max(top_k * strategy.candidate_multiplier, 10),
        100,
    )

    query_embedding = embed_query(query)

    where = build_where(
        repository_id=repository_id,
        language=language,
        symbol_type=symbol_type,
    )

    raw_results = search(
        query_embedding=query_embedding,
        n_results=candidate_k,
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

    candidates = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        candidates.append(
            {
                "content": document,
                "metadata": metadata,
                "distance": float(distance),
            }
        )

    ranked = rerank(
        candidates=candidates,
        parsed_query=parsed_query,
        intent=intent,
        strategy=strategy,
    )

    return {
        "intent": intent,
        "parsed_query": parsed_query,
        "results": ranked[:top_k],
    }