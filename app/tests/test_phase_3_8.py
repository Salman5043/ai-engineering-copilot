from __future__ import annotations

import pytest

from app.mcp_client.retry import (
    RetryConfig,
    calculate_retry_delay,
    classify_error,
    should_retry,
)
from unittest.mock import AsyncMock

from app.mcp_client.client import MCPClient
from app.mcp_client.models import MCPServerConfig

@pytest.mark.anyio
async def test_mcp_client_retries_transient_failure(
    monkeypatch,
):
    config = MCPServerConfig(
        name="test-server",
        command="uv",
        args=[],
    )

    client = MCPClient(
        config,
        retry_config=RetryConfig(
            max_attempts=3,
            initial_delay=0.0,
            backoff_multiplier=1.0,
        ),
    )

    calls = 0

    async def fake_call():
        nonlocal calls

        calls += 1

        if calls < 3:
            raise RuntimeError(
                "Connection closed"
            )

        return "success"

    client._execute_tool_once = fake_call

    result = await client._execute_tool_with_retry(
        "search_text",
        {},
    )

    assert result == "success"
    assert calls == 3

def test_retry_delay_exponential_backoff():
    config = RetryConfig(
        max_attempts=3,
        initial_delay=0.5,
        backoff_multiplier=2.0,
        max_delay=5.0,
    )

    assert calculate_retry_delay(
        1,
        config,
    ) == 0.5

    assert calculate_retry_delay(
        2,
        config,
    ) == 1.0

    assert calculate_retry_delay(
        3,
        config,
    ) == 2.0


def test_retry_delay_respects_max_delay():
    config = RetryConfig(
        max_attempts=10,
        initial_delay=1.0,
        backoff_multiplier=10.0,
        max_delay=3.0,
    )

    assert calculate_retry_delay(
        4,
        config,
    ) == 3.0


def test_timeout_is_retryable():
    decision = classify_error(
        RuntimeError(
            "Request timed out"
        )
    )

    assert decision.retry is True


def test_connection_error_is_retryable():
    decision = classify_error(
        RuntimeError(
            "Connection closed"
        )
    )

    assert decision.retry is True


def test_invalid_arguments_are_not_retryable():
    decision = classify_error(
        RuntimeError(
            "Invalid arguments"
        )
    )

    assert decision.retry is False


def test_unknown_tool_is_not_retryable():
    decision = classify_error(
        RuntimeError(
            "Unknown tool: search_text"
        )
    )

    assert decision.retry is False


def test_permission_error_is_not_retryable():
    decision = classify_error(
        RuntimeError(
            "Permission denied"
        )
    )

    assert decision.retry is False


def test_unknown_error_is_not_retryable():
    decision = classify_error(
        RuntimeError(
            "Unexpected application failure"
        )
    )

    assert decision.retry is False


def test_max_attempts_prevents_retry():
    config = RetryConfig(
        max_attempts=3
    )

    decision = should_retry(
        RuntimeError(
            "Connection closed"
        ),
        attempt=3,
        config=config,
    )

    assert decision.retry is False