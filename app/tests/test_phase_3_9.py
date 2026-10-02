from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.mcp_client.client import MCPClient
from app.mcp_client.models import MCPServerConfig
from app.mcp_client.retry import RetryConfig
from app.mcp_client.tracing import (
    MCPTracer,
)


def make_client() -> MCPClient:
    config = MCPServerConfig(
        name="test-server",
        command="uv",
        args=[],
    )

    return MCPClient(
        config,
        retry_config=RetryConfig(
            max_attempts=3,
            initial_delay=0.0,
            backoff_multiplier=1.0,
        ),
    )


def test_tracer_creates_trace():
    tracer = MCPTracer()

    trace = tracer.start(
        operation="tool_execution",
        server_name="test-server",
        tool_name="search_text",
    )

    assert trace.trace_id
    assert trace.operation == "tool_execution"
    assert trace.server_name == "test-server"
    assert trace.tool_name == "search_text"
    assert trace.started_at is not None


def test_tracer_records_attempts():
    tracer = MCPTracer()

    trace = tracer.start(
        operation="tool_execution",
        server_name="test-server",
    )

    tracer.record_attempt(trace)
    tracer.record_attempt(trace)

    assert trace.attempts == 2


def test_tracer_completes_successfully():
    tracer = MCPTracer()

    trace = tracer.start(
        operation="tool_execution",
        server_name="test-server",
    )

    completed = tracer.complete(
        trace,
        success=True,
    )

    assert completed.success is True
    assert completed.ended_at is not None
    assert completed.duration_ms is not None
    assert completed.duration_ms >= 0


def test_tracer_records_error():
    tracer = MCPTracer()

    trace = tracer.start(
        operation="tool_execution",
        server_name="test-server",
    )

    error = RuntimeError(
        "Connection closed"
    )

    tracer.complete(
        trace,
        success=False,
        error=error,
    )

    assert trace.success is False
    assert trace.error_type == "RuntimeError"
    assert trace.error_message == (
        "Connection closed"
    )


def test_tracer_limits_history():
    tracer = MCPTracer(
        max_traces=2
    )

    for _ in range(3):
        tracer.start(
            operation="tool_execution",
            server_name="test-server",
        )

    traces = tracer.list_traces()

    assert len(traces) == 2


def test_tracer_snapshot_is_serializable():
    tracer = MCPTracer()

    trace = tracer.start(
        operation="tool_execution",
        server_name="test-server",
        tool_name="search_text",
    )

    tracer.complete(
        trace,
        success=True,
    )

    snapshot = tracer.snapshot()

    assert len(snapshot) == 1

    item = snapshot[0]

    assert item["trace_id"]
    assert item["operation"] == (
        "tool_execution"
    )
    assert item["tool_name"] == (
        "search_text"
    )
    assert item["success"] is True


def test_tracer_get():
    tracer = MCPTracer()

    trace = tracer.start(
        operation="tool_execution",
        server_name="test-server",
    )

    found = tracer.get(
        trace.trace_id
    )

    assert found is trace


@pytest.mark.anyio
async def test_client_traces_successful_tool():
    client = make_client()

    expected = {
        "is_error": False,
    }

    client._call_tool_once = AsyncMock(
        return_value=expected
    )

    result = await client.call_tool(
        "search_text",
        {},
    )

    assert result == expected

    traces = client.tracer.list_traces()

    assert len(traces) == 1

    trace = traces[0]

    assert trace.operation == (
        "tool_execution"
    )
    assert trace.tool_name == (
        "search_text"
    )
    assert trace.attempts == 1
    assert trace.success is True
    assert trace.is_tool_error is False


@pytest.mark.anyio
async def test_client_traces_mcp_tool_error():
    client = make_client()

    class FakeResult:
        is_error = True

    client._call_tool_once = AsyncMock(
        return_value=FakeResult()
    )

    result = await client.call_tool(
        "search_text",
        {},
    )

    assert result is not None

    traces = client.tracer.list_traces()

    assert len(traces) == 1

    trace = traces[0]

    assert trace.attempts == 1
    assert trace.success is False
    assert trace.is_tool_error is True


@pytest.mark.anyio
async def test_client_traces_retry_attempts():
    client = make_client()

    calls = 0

    async def fake_call(
        tool_name,
        arguments,
    ):
        nonlocal calls

        calls += 1

        if calls < 3:
            raise RuntimeError(
                "Connection closed"
            )

        return {
            "is_error": False
        }

    client._call_tool_once = fake_call

    result = await client.call_tool(
        "search_text",
        {},
    )

    assert result == {
        "is_error": False
    }

    traces = client.tracer.list_traces()

    assert len(traces) == 1

    trace = traces[0]

    assert trace.attempts == 3
    assert trace.success is True
    assert trace.is_tool_error is False


@pytest.mark.anyio
async def test_client_traces_non_retryable_failure():
    client = make_client()

    client._call_tool_once = AsyncMock(
        side_effect=RuntimeError(
            "Invalid arguments"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Invalid arguments",
    ):
        await client.call_tool(
            "search_text",
            {},
        )

    traces = client.tracer.list_traces()

    assert len(traces) == 1

    trace = traces[0]

    assert trace.attempts == 1
    assert trace.success is False
    assert trace.is_tool_error is False
    assert trace.error_type == (
        "RuntimeError"
    )