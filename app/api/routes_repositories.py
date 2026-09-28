from fastapi import APIRouter, HTTPException

from app.ingestion.indexer import index_repository
from app.models.schemas import RepositoryIndexRequest


router = APIRouter(
    prefix="/repositories",
    tags=["repositories"],
)


@router.post("/index")
def index_repository_route(
    request: RepositoryIndexRequest,
):
    try:
        result = index_repository(
            request.repository_path
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Repository indexing failed: {exc}",
        ) from exc