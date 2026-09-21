from pydantic import BaseModel, Field


class RepositoryIndexRequest(BaseModel):
    repository_path: str


class SearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="Natural-language search query",
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

    semantic_score: float | None = None

    code_boost: float | None = None

    score: float | None = None