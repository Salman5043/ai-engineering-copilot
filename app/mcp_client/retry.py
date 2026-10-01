from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetryConfig:
    """
    Configuration for MCP tool retry behavior.
    """

    max_attempts: int = 3
    initial_delay: float = 0.5
    backoff_multiplier: float = 2.0
    max_delay: float = 5.0


@dataclass(frozen=True)
class RetryDecision:
    """
    Describes whether an MCP operation should be retried.
    """

    retry: bool
    reason: str


TRANSIENT_ERROR_KEYWORDS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "temporary failure",
    "connection reset",
    "connection closed",
    "connection refused",
    "broken pipe",
    "transport",
    "server unavailable",
    "service unavailable",
)


NON_RETRYABLE_ERROR_KEYWORDS = (
    "unknown tool",
    "invalid argument",
    "invalid arguments",
    "validation error",
    "required field",
    "missing required",
    "permission denied",
    "access denied",
)


def calculate_retry_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """
    Calculate exponential backoff delay.

    attempt is 1-based.
    """

    delay = (
        config.initial_delay
        * (
            config.backoff_multiplier
            ** max(attempt - 1, 0)
        )
    )

    return min(
        delay,
        config.max_delay,
    )


def classify_error(
    error: Any,
) -> RetryDecision:
    """
    Determine whether an error looks transient.

    This intentionally uses conservative matching:
    unknown tools, validation errors, and permission failures
    should not be retried.
    """

    message = str(error).lower()

    for keyword in NON_RETRYABLE_ERROR_KEYWORDS:
        if keyword in message:
            return RetryDecision(
                retry=False,
                reason=(
                    f"Non-retryable MCP error: "
                    f"{keyword}"
                ),
            )

    for keyword in TRANSIENT_ERROR_KEYWORDS:
        if keyword in message:
            return RetryDecision(
                retry=True,
                reason=(
                    f"Transient MCP error: "
                    f"{keyword}"
                ),
            )

    return RetryDecision(
        retry=False,
        reason="MCP error is not classified as transient.",
    )


def should_retry(
    error: Any,
    *,
    attempt: int,
    config: RetryConfig,
) -> RetryDecision:
    """
    Determine whether another attempt is allowed.
    """

    if attempt >= config.max_attempts:
        return RetryDecision(
            retry=False,
            reason="Maximum MCP retry attempts reached.",
        )

    return classify_error(error)