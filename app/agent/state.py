from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    # Query context
    repository_id: str
    query: str

    # Query analysis
    intent: str
    intent_confidence: float
    identifiers: list[str]
    keywords: list[str]

    # Investigation planning
    investigation_plan: list[str]
    plan_reasons: dict[str, str]
    current_step: int
    max_steps: int

    # Retrieval / evidence
    search_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]

    # Reasoning
    observations: list[str]
    hypotheses: list[str]

    # Final response
    answer: str

    # Investigation control
    needs_more_investigation: bool
    investigation_complete: bool

    # Errors
    errors: list[str]
    executed_tools: list[str]
    tool_errors: list[str]