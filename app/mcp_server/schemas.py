from __future__ import annotations

from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    repository_id: str = Field(
        min_length=1,
        description="Repository identifier.",
    )

    path: str = Field(
        min_length=1,
        description="Repository-relative file path.",
    )

    start_line: int | None = Field(
        default=None,
        ge=1,
        description="First line to return, 1-based.",
    )

    end_line: int | None = Field(
        default=None,
        ge=1,
        description="Last line to return, inclusive.",
    )


class ListFilesInput(BaseModel):
    repository_id: str = Field(
        min_length=1,
        description="Repository identifier.",
    )

    path: str = Field(
        default=".",
        min_length=1,
        description="Repository-relative directory path.",
    )


class SearchTextInput(BaseModel):
    repository_id: str = Field(
        min_length=1,
        description="Repository identifier.",
    )

    query: str = Field(
        min_length=1,
        description="Text to search for.",
    )

    max_results: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of matching lines.",
    )

    case_sensitive: bool = Field(
        default=False,
        description="Whether matching should be case-sensitive.",
    )


class RepositoryStructureInput(BaseModel):
    repository_id: str = Field(
        min_length=1,
        description="Repository identifier.",
    )

    max_files: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of files to return.",
    )