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
from app.mcp_client.tracing import (
    MCPTracer,
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
    - Record execution traces
    """

    def __init__(
        self,
        config: MCPServerConfig,
        retry_config: RetryConfig | None = None,
        tracer: MCPTracer | None = None,
    ) -> None:
        """
        Initialize the MCP client.
        """

        self.config = config

        self.retry_config = (
            retry_config
            if retry_config is not None
            else RetryConfig()
        )

        self.tracer = (
            tracer
            if tracer is not None
            else MCPTracer()
        )

    def _server_parameters(
        self,
    ) -> StdioServerParameters:
        """
        Build MCP stdio server parameters.
        """

        return StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env,
            cwd=self.config.cwd,
        )

    async def _discover_tools_once(
        self,
    ) -> list[MCPToolDefinition]:
        """
        Perform exactly one MCP tool discovery attempt.

        No retry logic is performed here.
        """

        server_parameters = (
            self._server_parameters()
        )

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

        Transient connection/transport failures are retried.

        Every discovery operation is traced.
        """

        trace = self.tracer.start(
            operation="tool_discovery",
            server_name=self.config.name,
        )

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.retry_config.max_attempts + 1,
        ):
            self.tracer.record_attempt(
                trace
            )

            try:
                tools = (
                    await self._discover_tools_once()
                )

                self.tracer.complete(
                    trace,
                    success=True,
                )

                return tools

            except Exception as exc:
                last_error = exc

                decision = should_retry(
                    exc,
                    attempt=attempt,
                    config=self.retry_config,
                )

                if not decision.retry:
                    self.tracer.complete(
                        trace,
                        success=False,
                        error=exc,
                    )

                    raise

                delay = calculate_retry_delay(
                    attempt,
                    self.retry_config,
                )

                await asyncio.sleep(
                    delay
                )

        if last_error is not None:
            self.tracer.complete(
                trace,
                success=False,
                error=last_error,
            )

            raise last_error

        self.tracer.complete(
            trace,
            success=False,
            error=RuntimeError(
                "MCP tool discovery failed."
            ),
        )

        return []


    async def _call_tool_once(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Perform exactly one MCP tool execution attempt.

        No retry logic is performed here.
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
        Compatibility/test seam for a single MCP execution attempt.
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
        Execute an MCP tool with retry handling and tracing.

        This is the single canonical retry implementation.
        """

        trace = self.tracer.start(
            operation="tool_execution",
            server_name=self.config.name,
            tool_name=tool_name,
        )

        last_error: Exception | None = None

        for attempt in range(
            1,
            self.retry_config.max_attempts + 1,
        ):
            self.tracer.record_attempt(trace)

            try:
                execute_once = self._execute_tool_once

                parameters = inspect.signature(
                    execute_once
                ).parameters

                if len(parameters) == 0:
                    result = await execute_once()
                else:
                    result = await execute_once(
                        tool_name,
                        arguments,
                    )

                is_tool_error = bool(
                    getattr(
                        result,
                        "is_error",
                        False,
                    )
                )

                self.tracer.complete(
                    trace,
                    success=not is_tool_error,
                    is_tool_error=is_tool_error,
                )

                return result

            except Exception as exc:
                last_error = exc

                decision = should_retry(
                    exc,
                    attempt=attempt,
                    config=self.retry_config,
                )

                if not decision.retry:
                    self.tracer.complete(
                        trace,
                        success=False,
                        error=exc,
                    )

                    raise

                delay = calculate_retry_delay(
                    attempt,
                    self.retry_config,
                )

                await asyncio.sleep(delay)

        if last_error is not None:
            self.tracer.complete(
                trace,
                success=False,
                error=last_error,
            )

            raise last_error

        final_error = RuntimeError(
            "MCP tool execution failed."
        )

        self.tracer.complete(
            trace,
            success=False,
            error=final_error,
        )

        raise final_error

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute an MCP tool using the canonical
        traced/retry execution path.
        """

        return await self._execute_tool_with_retry(
            tool_name,
            arguments,
        )

