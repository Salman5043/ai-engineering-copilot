from fastapi import APIRouter

from app.models.schemas import SearchRequest
from app.retrieval.retriever import retrieve


router = APIRouter(
    prefix="/search",
    tags=["search"],
)


@router.post("")
def search_code(request: SearchRequest):

    results = retrieve(
        query=request.query,
        n_results=request.top_k,
    )

    return {
        "query": request.query,
        "results": results,
    }