from __future__ import annotations

import time
import uuid

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class MCPTrace:
    """
    Represents one MCP operation.

    A trace can represent:
    - tool discovery
    - tool execution
    """

    trace_id: str
    operation: str
    server_name: str

    tool_name: str | None = None

    started_at: str | None = None
    ended_at: str | None = None

    duration_ms: float | None = None

    attempts: int = 0

    success: bool = False
    is_tool_error: bool = False

    error_type: str | None = None
    error_message: str | None = None


class MCPTracer:
    """
    Lightweight in-process MCP execution tracer.

    This intentionally has no external dependency.

    Later this can be adapted to:
    - OpenTelemetry
    - LangSmith
    - Prometheus
    - structured logging
    - persistent execution history
    """

    def __init__(
        self,
        *,
        max_traces: int = 1000,
    ) -> None:
        self.max_traces = max(
            max_traces,
            1,
        )

        self._traces: list[MCPTrace] = []

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def start(
    self,
    *,
    operation: str,
    server_name: str,
    tool_name: str | None = None,
) -> MCPTrace:
        """
        Start a new MCP trace.

        The trace is immediately added to the retained history.
        History is trimmed so that max_traces is always respected.
        """

        trace = MCPTrace(
            trace_id=uuid.uuid4().hex,
            operation=operation,
            server_name=server_name,
            tool_name=tool_name,
            started_at=self._timestamp(),
        )

        self._traces.append(trace)

        self._trim()

        return trace

    def record_attempt(
        self,
        trace: MCPTrace,
    ) -> None:
        """
        Record one MCP execution/discovery attempt.
        """

        trace.attempts += 1

    def complete(
        self,
        trace: MCPTrace,
        *,
        success: bool,
        is_tool_error: bool = False,
        error: Any | None = None,
    ) -> MCPTrace:
        """
        Complete an MCP trace.
        """

        trace.ended_at = self._timestamp()

        if trace.started_at:
            start = datetime.fromisoformat(
                trace.started_at
            )

            end = datetime.fromisoformat(
                trace.ended_at
            )

            trace.duration_ms = (
                end - start
            ).total_seconds() * 1000

        trace.success = success
        trace.is_tool_error = is_tool_error

        if error is not None:
            trace.error_type = type(
                error
            ).__name__

            trace.error_message = str(
                error
            )

        self._trim()

        return trace

    def _trim(self) -> None:
        """
        Keep only the newest max_traces entries.
        """

        if len(self._traces) <= self.max_traces:
            return

        self._traces = self._traces[
            -self.max_traces:
        :]

    def list_traces(self) -> list[MCPTrace]:
        """
        Return all currently retained traces.
        """

        return list(
            self._traces
        )

    def get(
        self,
        trace_id: str,
    ) -> MCPTrace | None:
        """
        Find a trace by ID.
        """

        for trace in self._traces:
            if trace.trace_id == trace_id:
                return trace

        return None

    def clear(self) -> None:
        """
        Remove all retained traces.
        """

        self._traces.clear()

    def snapshot(self) -> list[dict[str, Any]]:
        """
        Return traces as serializable dictionaries.
        """

        return [
            {
                "trace_id": trace.trace_id,
                "operation": trace.operation,
                "server_name": trace.server_name,
                "tool_name": trace.tool_name,
                "started_at": trace.started_at,
                "ended_at": trace.ended_at,
                "duration_ms": trace.duration_ms,
                "attempts": trace.attempts,
                "success": trace.success,
                "is_tool_error": trace.is_tool_error,
                "error_type": trace.error_type,
                "error_message": trace.error_message,
            }
            for trace in self._traces
        ]