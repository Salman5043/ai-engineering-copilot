from __future__ import annotations

from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    # ---------------------------------------------------------
    # Repository / query
    # ---------------------------------------------------------

    repository_id: str
    query: str

    # ---------------------------------------------------------
    # Query analysis
    # ---------------------------------------------------------

    intent: str
    intent_confidence: float

    identifiers: list[str]
    keywords: list[str]

    # ---------------------------------------------------------
    # Investigation planning
    # ---------------------------------------------------------

    investigation_plan: list[str]
    current_step: int
    max_steps: int

    plan_reasons: dict[str, str]

    # ---------------------------------------------------------
    # Search / retrieval
    # ---------------------------------------------------------

    search_results: list[dict[str, Any]]

    # ---------------------------------------------------------
    # Evidence
    # ---------------------------------------------------------

    evidence: list[dict[str, Any]]
    evidence_count: int

    # ---------------------------------------------------------
    # Reasoning
    # ---------------------------------------------------------

    observations: list[str]
    hypotheses: list[str]

    reasoning: str
    reasoning_error: str

    answer: str

    # ---------------------------------------------------------
    # Investigation control
    # ---------------------------------------------------------

    needs_more_investigation: bool
    investigation_complete: bool

    investigation_decision: str
    investigation_reason: str

    # ---------------------------------------------------------
    # Tool execution
    # ---------------------------------------------------------

    executed_tools: list[str]
    tool_errors: list[str]

    # ---------------------------------------------------------
    # General errors
    # ---------------------------------------------------------

    errors: list[str]

    # ---------------------------------------------------------
    # Phase 2.8 — Human-in-the-Loop
    # ---------------------------------------------------------

    approval_required: bool
    approval_status: str
    approval_message: str

    # ---------------------------------------------------------
    # HITL thread
    # ---------------------------------------------------------

    thread_id: str
    change_proposal_id: str
    change_status: str

    approval_required: bool
    approval_granted: bool

    approval_comment: str

    approval_diff: str

    approval_error: str