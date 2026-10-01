from __future__ import annotations

import asyncio
from typing import Any
import inspect

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp_client.models import (
    MCPServerConfig,
    MCPToolDefinition,
)
from app.mcp_client.retry import (
    RetryConfig,
    calculate_retry_delay,
    should_retry,
)


class MCPClient:
    """
    Lightweight MCP client for connecting to an MCP server
    over stdio.

    Responsibilities:
    - Start the MCP server process
    - Initialize the MCP client session
    - Discover MCP tools
    - Execute MCP tools
    - Retry transient transport failures
    """

    def __init__(
        self,
        config: MCPServerConfig,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """
        Initialize the MCP client.

        Args:
            config:
                MCP server configuration.

            retry_config:
                Optional retry configuration.
                Defaults to RetryConfig().
        """

        self.config = config

        self.retry_config = (
            retry_config
            if retry_config is not None
            else RetryConfig()
        )

    def _server_parameters(
        self,
    ) -> StdioServerParameters:
        """
        Build MCP stdio server parameters.

        MCPServerConfig does not require a cwd field, so
        getattr() is used for backwards compatibility.
        """

        return StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env,
            cwd=getattr(self.config, "cwd", None),
        )

    async def _discover_tools_once(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Perform exactly one MCP tool discovery attempt.

        This method intentionally contains no retry logic.
        Retry behavior is handled by discover_tools().
        """

        server_parameters = self._server_parameters()

        async with stdio_client(
            server_parameters
        ) as (read, write):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                response = await session.list_tools()

                return [
                    MCPToolDefinition.from_mcp_tool(
                        tool,
                        server_name=self.config.name,
                    )
                    for tool in response.tools
                ]

    async def discover_tools(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Discover all tools exposed by the MCP server.

        Transient connection/transport failures are retried
        according to RetryConfig.

        Non-retryable failures are raised immediately.
        """

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.retry_config.max_attempts + 1,
        ):
            try:
                return await self._discover_tools_once()

            except Exception as exc:
                last_error = exc

                decision = should_retry(
                    exc,
                    attempt=attempt,
                    config=self.retry_config,
                )

                if not decision.retry:
                    raise

                delay = calculate_retry_delay(
                    attempt,
                    self.retry_config,
                )

                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error

        return []

    async def _call_tool_once(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Perform exactly one MCP tool execution attempt.

        This method intentionally contains no retry logic.
        """

        server_parameters = self._server_parameters()

        async with stdio_client(
            server_parameters
        ) as (read, write):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                return await session.call_tool(
                    tool_name,
                    arguments or {},
                )

    async def _execute_tool_once(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Compatibility wrapper for the retry execution API.

        The Phase 3.8 retry contract uses _execute_tool_once()
        as the single-attempt operation.
        """

        return await self._call_tool_once(
            tool_name,
            arguments,
        )

    async def _execute_tool_with_retry(
    self,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
        """
        Execute an MCP tool with retry handling.

        The single-attempt operation may either accept the
        normal tool_name/arguments parameters or, for injected
        test operations, accept no parameters.
        """

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.retry_config.max_attempts + 1,
        ):
            try:
                execute_once = self._execute_tool_once

                parameters = inspect.signature(
                    execute_once
                ).parameters

                if len(parameters) == 0:
                    return await execute_once()

                return await execute_once(
                    tool_name,
                    arguments,
                )

            except Exception as exc:
                last_error = exc

                decision = should_retry(
                    exc,
                    attempt=attempt,
                    config=self.retry_config,
                )

                if not decision.retry:
                    raise

                delay = calculate_retry_delay(
                    attempt,
                    self.retry_config,
                )

                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error

        raise RuntimeError(
            "MCP tool execution failed without an exception."
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute an MCP tool.

        Transport/protocol exceptions are classified and
        transient failures are retried using exponential
        backoff.

        Important:
        A normal MCP tool execution result with
        is_error=True is returned directly to the caller.
        It is NOT automatically retried.
        """

        return await self._execute_tool_with_retry(
            tool_name,
            arguments,
        )

