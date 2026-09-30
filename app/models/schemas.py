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




class InvestigationRequest(BaseModel):
    repository_id: str = Field(
        min_length=1,
        description=(
            "Repository identifier returned during indexing"
        ),
    )

    query: str = Field(
        min_length=1,
        description=(
            "Natural-language developer investigation question"
        ),
    )


class InvestigationEvidence(BaseModel):
    evidence_id: str

    content: str

    file: str

    start_line: int | None = None
    end_line: int | None = None

    language: str | None = None

    symbol: str | None = None
    symbol_type: str | None = None

    score: float | None = None
    semantic_score: float | None = None

    source_tool: str

    repository_id: str


class InvestigationResponse(BaseModel):
    # ---------------------------------------------------------
    # Request
    # ---------------------------------------------------------

    query: str
    repository_id: str

    # ---------------------------------------------------------
    # Query analysis
    # ---------------------------------------------------------

    intent: str
    intent_confidence: float

    # ---------------------------------------------------------
    # Investigation
    # ---------------------------------------------------------

    investigation_plan: list[str] = Field(
        default_factory=list
    )

    executed_tools: list[str] = Field(
        default_factory=list
    )

    # ---------------------------------------------------------
    # Evidence
    # ---------------------------------------------------------

    evidence_count: int = 0

    evidence: list[InvestigationEvidence] = Field(
        default_factory=list
    )

    # ---------------------------------------------------------
    # Investigation status
    # ---------------------------------------------------------

    investigation_complete: bool = False

    investigation_decision: str = ""

    investigation_reason: str = ""

    # ---------------------------------------------------------
    # Final answer
    # ---------------------------------------------------------

    answer: str = ""

    # ---------------------------------------------------------
    # Errors
    # ---------------------------------------------------------

    reasoning_error: str | None = None

    errors: list[str] = Field(
        default_factory=list
    )

    # ---------------------------------------------------------
    # Phase 2.8 — HITL
    # ---------------------------------------------------------

    approval_required: bool = False

    approval_status: str = "pending"

    approval_message: str = ""

    thread_id: str | None = None