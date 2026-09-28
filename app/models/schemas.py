from pydantic import BaseModel, Field


class RepositoryIndexRequest(BaseModel):
    repository_path: str = Field(
        min_length=1,
        description="Absolute path to the repository",
    )


class SearchRequest(BaseModel):
    repository_id: str = Field(
        min_length=1,
        description="Repository identifier returned during indexing",
    )

    query: str = Field(
        min_length=1,
        description="Natural-language developer query",
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return",
    )

    language: str | None = Field(
        default=None,
        description="Optional programming language filter",
    )

    symbol_type: str | None = Field(
        default=None,
        description="Optional code symbol filter",
    )


class SearchResult(BaseModel):
    content: str
    file: str
    start_line: int
    end_line: int
    distance: float

    language: str | None = None
    symbol: str | None = None
    symbol_type: str | None = None

    score: float | None = None
    semantic_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    repository_id: str
    intent: str
    intent_confidence: float
    results: list[SearchResult]