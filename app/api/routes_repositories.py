from fastapi import APIRouter, HTTPException

from app.ingestion.indexer import index_repository
from app.models.schemas import RepositoryIndexRequest


router = APIRouter(
    prefix="/repositories",
    tags=["repositories"],
)


@router.post("/index")
def index(request: RepositoryIndexRequest):

    try:
        result = index_repository(
            request.repository_path
        )

    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "status": "indexed",
        **result,
    }