from fastapi import APIRouter

from app.models.schemas import (
    SearchRequest,
    SearchResult,
)
from app.retrieval.retriever import retrieve


router = APIRouter(
    prefix="",
    tags=["Search"],
)


@router.post(
    "/search",
    response_model=dict,
)
def search_repository(
    request: SearchRequest,
):
    """
    Search the indexed repository.

    Supports:

    - semantic search
    - language filtering
    - symbol-type filtering
    - code-aware reranking
    """

    # ---------------------------------------------------------
    # Build Chroma metadata filter
    # ---------------------------------------------------------

    conditions = []

    if request.language:
        conditions.append(
            {
                "language": request.language
            }
        )

    if request.symbol_type:
        conditions.append(
            {
                "symbol_type": request.symbol_type
            }
        )

    if not conditions:
        where = None

    elif len(conditions) == 1:
        where = conditions[0]

    else:
        where = {
            "$and": conditions
        }

    # ---------------------------------------------------------
    # Retrieve + rerank
    # ---------------------------------------------------------

    results = retrieve(
        query=request.query,
        top_k=request.top_k,
        where=where,
    )

    # ---------------------------------------------------------
    # Format API response
    # ---------------------------------------------------------

    formatted_results = []

    for result in results:
        metadata = result.get(
            "metadata",
            {},
        )

        formatted_results.append(
            SearchResult(
                content=result.get(
                    "content",
                    "",
                ),

                file=metadata.get(
                    "file",
                    "unknown",
                ),

                start_line=int(
                    metadata.get(
                        "start_line",
                        0,
                    )
                ),

                end_line=int(
                    metadata.get(
                        "end_line",
                        0,
                    )
                ),

                distance=float(
                    result.get(
                        "distance",
                        0.0,
                    )
                ),

                language=metadata.get(
                    "language"
                ),

                symbol=metadata.get(
                    "symbol"
                ) or None,

                symbol_type=metadata.get(
                    "symbol_type"
                ) or None,

                semantic_score=result.get(
                    "semantic_score"
                ),

                code_boost=result.get(
                    "code_boost"
                ),

                score=result.get(
                    "score"
                ),
            )
        )

    return {
        "query": request.query,
        "filters": where,
        "results": formatted_results,
    }