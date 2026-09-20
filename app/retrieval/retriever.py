from .embeddings import embed_query
from .vector_store import search


def retrieve(
    query: str,
    n_results: int = 5,
) -> list[dict]:

    query_embedding = embed_query(query)

    results = search(
        query_embedding,
        n_results=n_results,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        retrieved.append(
            {
                "content": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return retrieved