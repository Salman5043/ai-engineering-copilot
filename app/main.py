from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.api.routes_repositories import (
    router as repositories_router,
)
from app.api.routes_search import router as search_router
from app.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


app.include_router(health_router)
app.include_router(repositories_router)
app.include_router(search_router)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }