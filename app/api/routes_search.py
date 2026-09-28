from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)

from app.retrieval.retriever import retrieve


router = APIRouter(
    tags=["search"],
)


@router.post(
    "/search",
    response_model=SearchResponse,
)
def search_repository(
    request: SearchRequest,
):
    try:
        result = retrieve(
            repository_id=request.repository_id,
            query=request.query,
            top_k=request.top_k,
            language=request.language,
            symbol_type=request.symbol_type,
        )

        response_results = []

        for item in result["results"]:
            metadata = item["metadata"]

            response_results.append(
                SearchResult(
                    content=item["content"],
                    file=metadata.get("file", ""),
                    start_line=int(
                        metadata.get("start_line", 0)
                    ),
                    end_line=int(
                        metadata.get("end_line", 0)
                    ),
                    distance=float(
                        item["distance"]
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
                    score=item.get("score"),
                    semantic_score=item.get(
                        "semantic_score"
                    ),
                )
            )

        return SearchResponse(
            query=request.query,
            repository_id=request.repository_id,
            intent=result["intent"].name,
            intent_confidence=result[
                "intent"
            ].confidence,
            results=response_results,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {exc}",
        ) from exc