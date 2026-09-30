from __future__ import annotations

from app.agent.graph import build_investigation_graph


def test_hitl_requires_approval():
    """
    HITL mode should stop before final answer generation
    and mark the investigation as requiring approval.
    """

    graph = build_investigation_graph(
        enable_hitl=True,
    )

    config = {
        "configurable": {
            "thread_id": "test-hitl-approval",
        }
    }

    result = graph.invoke(
        {
            "repository_id": "repo_test",

            "query": (
                "Where is build_graph defined?"
            ),
        },
        config=config,
    )

    assert result is not None

    assert (
        result["approval_required"]
        is True
    )

    assert (
        result["approval_status"]
        == "pending"
    )


def test_hitl_thread_id_is_supported():
    """
    HITL graph should execute with a LangGraph
    configurable thread_id.
    """

    graph = build_investigation_graph(
        enable_hitl=True,
    )

    config = {
        "configurable": {
            "thread_id": "test-hitl-thread",
        }
    }

    result = graph.invoke(
        {
            "repository_id": "repo_test",

            "query": (
                "Where is the application entrypoint?"
            ),
        },
        config=config,
    )

    assert result is not None

    assert (
        result["approval_required"]
        is True
    )


def test_normal_graph_does_not_require_hitl():
    """
    Default graph must remain compatible with
    existing Phase 2.1–2.7 tests.

    No checkpointer and no thread_id should be required.
    """

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "repo_test",

            "query": (
                "Where is build_graph defined?"
            ),
        }
    )

    assert result is not None

    assert (
        result.get(
            "approval_required",
            False,
        )
        is False
    )