from pydantic import BaseModel, Field


class RepositoryIndexRequest(BaseModel):
    repository_path: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class SearchResult(BaseModel):
    content: str
    file: str
    start_line: int
    end_line: int
    distance: float