from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    repository_id: str
    query: str

    intent: str
    intent_confidence: float
    identifiers: list[str]
    keywords: list[str]

    investigation_plan: list[str]
    plan_reasons: dict[str, str]

    current_step: int
    max_steps: int

    search_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    evidence_count: int

    executed_tools: list[str]
    tool_errors: list[str]

    observations: list[str]
    hypotheses: list[str]

    investigation_decision: str
    investigation_reason: str

    reasoning: str
    reasoning_error: str

    answer: str

    needs_more_investigation: bool
    investigation_complete: bool

    errors: list[str]