from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver


_checkpointer = MemorySaver()


def get_checkpointer():
    """
    Return the shared LangGraph checkpointer.

    MemorySaver is suitable for development/testing.
    A persistent database-backed checkpointer can be introduced
    later for production deployments.
    """
    return _checkpointer