from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.agent.graph import build_investigation_graph
from app.models.schemas import (
    InvestigationEvidence,
    InvestigationRequest,
    InvestigationResponse,
)


router = APIRouter(
    tags=["investigation"],
)


@router.post(
    "/investigate",
    response_model=InvestigationResponse,
)
def investigate(
    request: InvestigationRequest,
) -> InvestigationResponse:
    """
    Start a repository investigation in HITL mode.

    The investigation performs repository analysis and evidence
    collection, then pauses for human approval before the LLM
    generates the final answer.
    """

    try:

        # -----------------------------------------------------
        # Build HITL-enabled graph
        # -----------------------------------------------------

        graph = build_investigation_graph(
            enable_hitl=True,
        )

        # -----------------------------------------------------
        # Create a unique workflow thread
        # -----------------------------------------------------

        thread_id = str(
            uuid4()
        )

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # -----------------------------------------------------
        # Initial state
        # -----------------------------------------------------

        initial_state = {
            "repository_id": request.repository_id,

            "query": request.query,

            "intent": "",

            "intent_confidence": 0.0,

            "identifiers": [],

            "keywords": [],

            "investigation_plan": [],

            "current_step": 0,

            "max_steps": 0,

            "plan_reasons": {},

            "search_results": [],

            "evidence": [],

            "evidence_count": 0,

            "observations": [],

            "hypotheses": [],

            "reasoning": "",

            "reasoning_error": "",

            "answer": "",

            "needs_more_investigation": True,

            "investigation_complete": False,

            "investigation_decision": "",

            "investigation_reason": "",

            "executed_tools": [],

            "tool_errors": [],

            "errors": [],

            # -----------------------------------------------
            # HITL
            # -----------------------------------------------

            "approval_required": False,

            "approval_status": "",

            "approval_message": "",

            "thread_id": thread_id,
        }

        # -----------------------------------------------------
        # Run graph
        # -----------------------------------------------------

        result = graph.invoke(
            initial_state,
            config=config,
        )

        # -----------------------------------------------------
        # Evidence conversion
        # -----------------------------------------------------

        evidence = []

        for item in result.get(
            "evidence",
            [],
        ):

            try:

                evidence.append(
                    InvestigationEvidence(
                        **item
                    )
                )

            except Exception as exc:

                result.setdefault(
                    "errors",
                    [],
                ).append(
                    "Invalid evidence item: "
                    f"{exc}"
                )

        # -----------------------------------------------------
        # Response
        # -----------------------------------------------------

        return InvestigationResponse(
            query=result.get(
                "query",
                request.query,
            ),

            repository_id=result.get(
                "repository_id",
                request.repository_id,
            ),

            intent=result.get(
                "intent",
                "general_search",
            ),

            intent_confidence=result.get(
                "intent_confidence",
                0.0,
            ),

            investigation_plan=result.get(
                "investigation_plan",
                [],
            ),

            executed_tools=result.get(
                "executed_tools",
                [],
            ),

            evidence_count=len(
                evidence
            ),

            evidence=evidence,

            investigation_complete=result.get(
                "investigation_complete",
                False,
            ),

            investigation_decision=result.get(
                "investigation_decision",
                "",
            ),

            investigation_reason=result.get(
                "investigation_reason",
                "",
            ),

            answer=result.get(
                "answer",
                "",
            ),

            reasoning_error=result.get(
                "reasoning_error"
            ),

            errors=result.get(
                "errors",
                [],
            ),

            # -----------------------------------------------
            # HITL
            # -----------------------------------------------

            approval_required=result.get(
                "approval_required",
                False,
            ),

            approval_status=result.get(
                "approval_status",
                "pending",
            ),

            approval_message=result.get(
                "approval_message",
                "",
            ),

            thread_id=thread_id,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Investigation failed: "
                f"{exc}"
            ),
        ) from exc