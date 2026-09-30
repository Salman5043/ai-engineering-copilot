from __future__ import annotations

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    code: str
    message: str


class FileEntry(BaseModel):
    path: str
    is_directory: bool
    size: int | None = None


class ReadFileResult(BaseModel):
    path: str
    content: str
    start_line: int | None = None
    end_line: int | None = None


class SearchMatch(BaseModel):
    path: str
    line: int
    content: str


class SearchResult(BaseModel):
    query: str
    matches: list[SearchMatch] = Field(default_factory=list)


class RepositoryStructureResult(BaseModel):
    repository_id: str
    root: str
    files: list[str] = Field(default_factory=list)
    directories: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    success: bool
    data: object | None = None
    error: ToolError | None = None