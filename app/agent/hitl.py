from __future__ import annotations

from typing import Any

from langgraph.types import interrupt


def request_human_approval(
    *,
    query: str,
    investigation_plan: list[str],
    evidence_count: int,
) -> dict[str, Any]:
    """
    Pause the LangGraph workflow and request human approval.

    The graph will resume when a Command(resume=...) is supplied.
    """

    approval_request = {
        "type": "investigation_approval",
        "message": (
            "The investigation has collected evidence. "
            "Review the investigation before generating the final answer."
        ),
        "query": query,
        "planned_tools": investigation_plan,
        "evidence_count": evidence_count,
        "actions": [
            "approve",
            "reject",
        ],
    }

    decision = interrupt(approval_request)

    if isinstance(decision, dict):
        return decision

    return {
        "action": str(decision),
        "feedback": "",
    }