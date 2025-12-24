"""MCP client connection pool management with Actor pattern.

This module provides persistent connection management for MCP servers,
using an Actor pattern to ensure all AsyncExitStack operations happen
in the same task, satisfying anyio's requirements.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum, auto
from string import Template
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool as MCPToolSchema

from tools.mcp.config import MCPServerConfig
from utils.logging import logger


@dataclass
class MCPConnection:
    """Represents a persistent connection to an MCP server."""

    config: MCPServerConfig
    session: ClientSession
    _exit_stack: AsyncExitStack = field(repr=False)


# --- Command Types for Actor Pattern ---


class CommandType(Enum):
    """Types of commands for the connection manager."""

    CONNECT = auto()
    DISCONNECT = auto()
    SHUTDOWN = auto()


@dataclass
class Command:
    """Base command for the connection manager."""

    type: CommandType
    future: asyncio.Future[Any]


@dataclass
class ConnectCommand(Command):
    """Command to connect to an MCP server."""

    config: MCPServerConfig

    def __init__(self, config: MCPServerConfig, future: asyncio.Future[ClientSession]):
        self.type = CommandType.CONNECT
        self.config = config
        self.future = future


@dataclass
class DisconnectCommand(Command):
    """Command to disconnect from an MCP server."""

    server_name: str

    def __init__(self, server_name: str, future: asyncio.Future[None]):
        self.type = CommandType.DISCONNECT
        self.server_name = server_name
        self.future = future


@dataclass
class ShutdownCommand(Command):
    """Command to shutdown all connections."""

    def __init__(self, future: asyncio.Future[None]):
        self.type = CommandType.SHUTDOWN
        self.future = future


class MCPConnectionPool:
    """Manages persistent connections to MCP servers using Actor pattern.

    All AsyncExitStack operations are performed in a dedicated manager task,
    ensuring compliance with anyio's requirement that context managers must
    be entered and exited in the same task.

    Usage:
        pool = MCPConnectionPool()
        await pool.start()  # Start the manager task
        await pool.connect(server_config)
        session = pool.get_session("server_name")
        # ... use session for tool calls ...
        await pool.shutdown()
    """

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}
        self._connecting: set[str] = set()  # Servers currently being connected
        self._command_queue: asyncio.Queue[Command] = asyncio.Queue()
        self._manager_task: asyncio.Task[None] | None = None
        self._started = asyncio.Event()
        self._shutdown_complete = asyncio.Event()

    @property
    def connected_servers(self) -> list[str]:
        """Get list of connected server names."""
        return list(self._connections.keys())

    @property
    def connecting_servers(self) -> list[str]:
        """Get list of servers currently being connected."""
        return list(self._connecting)

    def is_connected(self, server_name: str) -> bool:
        """Check if a server is connected."""
        return server_name in self._connections

    def is_connecting(self, server_name: str) -> bool:
        """Check if a server is currently being connected."""
        return server_name in self._connecting

    def get_session(self, server_name: str) -> ClientSession:
        """Get the session for a connected server.

        Args:
            server_name: Name of the server.

        Returns:
            The ClientSession for the server.

        Raises:
            KeyError: If the server is not connected.
        """
        if server_name not in self._connections:
            raise KeyError(f"MCP server '{server_name}' is not connected")
        return self._connections[server_name].session

    # --- Lifecycle Management ---

    async def start(self) -> None:
        """Start the connection manager task.

        Must be called before any connect/disconnect operations.
        """
        if self._manager_task is not None:
            logger.debug("MCPConnectionPool already started")
            return

        logger.debug("Starting MCPConnectionPool manager task")
        self._manager_task = asyncio.create_task(self._manager_loop())
        await self._started.wait()
        logger.info("MCPConnectionPool manager task started")

    async def _manager_loop(self) -> None:
        """Main loop for the manager task.

        All AsyncExitStack operations happen in this task.
        """
        self._started.set()
        logger.debug("MCPConnectionPool manager loop started")

        try:
            while True:
                cmd = await self._command_queue.get()

                try:
                    if isinstance(cmd, ConnectCommand):
                        session = await self._do_connect(cmd.config)
                        cmd.future.set_result(session)

                    elif isinstance(cmd, DisconnectCommand):
                        await self._do_disconnect(cmd.server_name)
                        cmd.future.set_result(None)

                    elif isinstance(cmd, ShutdownCommand):
                        await self._do_shutdown()
                        cmd.future.set_result(None)
                        break  # Exit the loop

                except asyncio.CancelledError:
                    # Re-raise to handle task cancellation
                    if not cmd.future.done():
                        cmd.future.cancel()
                    raise

                except Exception as e:
                    logger.error(
                        "Error processing command {type}: {error}",
                        type=cmd.type,
                        error=str(e),
                    )
                    if not cmd.future.done():
                        cmd.future.set_exception(e)

        except asyncio.CancelledError:
            logger.debug("Manager loop cancelled, cleaning up...")
            await self._do_shutdown()
            raise

        finally:
            self._shutdown_complete.set()
            logger.debug("MCPConnectionPool manager loop exited")

    async def connect(self, config: MCPServerConfig) -> ClientSession:
        """Connect to an MCP server.

        Can be called from any task. The actual connection is performed
        in the manager task.

        Args:
            config: Server configuration.

        Returns:
            Connected ClientSession instance.
        """
        # Fast path: already connected
        if config.name in self._connections:
            logger.debug(
                "Reusing existing connection to MCP server: {name}",
                name=config.name,
            )
            return self._connections[config.name].session

        # Ensure manager is running
        if self._manager_task is None:
            raise RuntimeError("MCPConnectionPool not started. Call start() first.")

        # Send command to manager task
        future: asyncio.Future[ClientSession] = asyncio.get_event_loop().create_future()
        await self._command_queue.put(ConnectCommand(config, future))

        return await future

    async def disconnect(self, server_name: str) -> None:
        """Disconnect from a specific server.

        Can be called from any task.

        Args:
            server_name: Name of the server to disconnect.
        """
        if self._manager_task is None:
            logger.warning("MCPConnectionPool not started, nothing to disconnect")
            return

        future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        await self._command_queue.put(DisconnectCommand(server_name, future))

        await future

    async def shutdown(self) -> None:
        """Shutdown all connections and stop the manager task.

        Can be called from any task.
        """
        if self._manager_task is None:
            logger.debug("MCPConnectionPool not started, nothing to shutdown")
            return

        future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        await self._command_queue.put(ShutdownCommand(future))

        try:
            await future
        except asyncio.CancelledError:
            pass

        # Wait for manager task to complete
        await self._shutdown_complete.wait()
        self._manager_task = None

    # --- Internal Operations (executed in manager task) ---

    async def _do_connect(self, config: MCPServerConfig) -> ClientSession:
        """Actually perform the connection (runs in manager task)."""
        # Double-check if already connected
        if config.name in self._connections:
            return self._connections[config.name].session

        # Mark as connecting
        self._connecting.add(config.name)

        try:
            logger.info(
                "Establishing persistent connection to MCP server: {name}",
                name=config.name,
            )

            exit_stack = AsyncExitStack()
            try:
                if config.transport == "stdio":
                    session = await self._connect_stdio(config, exit_stack)
                elif config.transport == "sse":
                    session = await self._connect_sse(config, exit_stack)
                elif config.transport == "streamable_http":
                    session = await self._connect_streamable_http(config, exit_stack)
                else:
                    raise ValueError(f"Invalid transport: {config.transport}")

                connection = MCPConnection(
                    config=config,
                    session=session,
                    _exit_stack=exit_stack,
                )
                self._connections[config.name] = connection

                logger.info(
                    "Successfully connected to MCP server: {name}",
                    name=config.name,
                )
                return session

            except Exception as e:
                # Cleanup on failure
                await exit_stack.aclose()
                logger.error(
                    "Failed to connect to MCP server '{name}': {error}",
                    name=config.name,
                    error=str(e),
                )
                raise

        finally:
            self._connecting.discard(config.name)

    async def _do_disconnect(self, server_name: str) -> None:
        """Actually perform the disconnection (runs in manager task)."""
        if server_name not in self._connections:
            logger.debug(
                "Server '{name}' not connected, nothing to disconnect",
                name=server_name,
            )
            return

        connection = self._connections.pop(server_name)
        logger.debug("Closing MCP connection: {name}", name=server_name)
        await connection._exit_stack.aclose()
        logger.info("Disconnected from MCP server: {name}", name=server_name)

    async def _do_shutdown(self) -> None:
        """Actually perform the shutdown (runs in manager task)."""
        if not self._connections:
            logger.debug("No connections to shutdown")
            return

        logger.info(
            "Shutting down MCP connection pool ({count} connections)",
            count=len(self._connections),
        )

        # Close all connections
        for name, connection in list(self._connections.items()):
            try:
                await connection._exit_stack.aclose()
                logger.debug("Closed MCP connection: {name}", name=name)
            except Exception as e:
                logger.warning(
                    "Error closing MCP connection '{name}': {error}",
                    name=name,
                    error=str(e),
                )

        self._connections.clear()
        logger.info("MCP connection pool shutdown complete")

    # --- Transport-specific Connection Methods ---

    @staticmethod
    async def _connect_stdio(config: MCPServerConfig, exit_stack: AsyncExitStack) -> ClientSession:
        """Connect via stdio transport with persistent process."""
        assert config.command is not None

        # Expand environment variables in env dict
        env = None
        if config.env:
            env = {}
            for key, value in config.env.items():
                # Support ${VAR} and $VAR syntax
                expanded = Template(value).safe_substitute(os.environ)
                env[key] = expanded

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=env,
        )

        # Enter the stdio_client context and keep it open
        # Redirect stderr to suppress uvx installation messages
        read, write = await exit_stack.enter_async_context(stdio_client(server_params, errlog=subprocess.DEVNULL))
        session = await exit_stack.enter_async_context(ClientSession(read, write))

        # Initialize the session
        await session.initialize()

        logger.debug(
            "Connected to MCP server via stdio: {name} (process kept alive)",
            name=config.name,
        )
        return session

    @staticmethod
    async def _connect_sse(config: MCPServerConfig, exit_stack: AsyncExitStack) -> ClientSession:
        """Connect via SSE transport with persistent connection."""
        assert config.url is not None

        read, write = await exit_stack.enter_async_context(sse_client(config.url))
        session = await exit_stack.enter_async_context(ClientSession(read, write))

        await session.initialize()

        logger.debug(
            "Connected to MCP server via SSE: {name}",
            name=config.name,
        )
        return session

    @staticmethod
    async def _connect_streamable_http(config: MCPServerConfig, exit_stack: AsyncExitStack) -> ClientSession:
        """Connect via streamable HTTP transport with persistent connection."""
        assert config.url is not None

        # Build headers if provided
        headers = config.headers or {}

        read, write = await exit_stack.enter_async_context(streamablehttp_client(config.url, headers=headers))
        session = await exit_stack.enter_async_context(ClientSession(read, write))

        await session.initialize()

        logger.debug(
            "Connected to MCP server via streamable_http: {name}",
            name=config.name,
        )
        return session

    # --- Tool Operations ---

    async def list_tools(self, server_name: str) -> list[MCPToolSchema]:
        """List available tools from a connected MCP server.

        Args:
            server_name: Name of the server.

        Returns:
            List of tool schemas.
        """
        session = self.get_session(server_name)
        result = await session.list_tools()
        return list(result.tools)

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        """Call a tool on a connected MCP server.

        Args:
            server_name: Name of the server.
            tool_name: Tool name to call.
            arguments: Tool arguments.

        Returns:
            Tool execution result as string.
        """
        session = self.get_session(server_name)

        logger.debug(
            "Calling MCP tool: {server}/{tool} with args: {args}",
            server=server_name,
            tool=tool_name,
            args=arguments,
        )

        result = await session.call_tool(tool_name, arguments or {})

        # Extract text content from result
        contents = []
        for content in result.content:
            if hasattr(content, "text"):
                contents.append(content.text)
            elif hasattr(content, "data"):
                # Handle binary/blob data
                contents.append(f"[Binary data: {len(content.data)} bytes]")
            else:
                contents.append(str(content))

        return "\n".join(contents)


# Global connection pool instance
_connection_pool: MCPConnectionPool | None = None


def get_connection_pool() -> MCPConnectionPool:
    """Get the global MCP connection pool instance.

    Creates the pool if it doesn't exist.
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = MCPConnectionPool()
    return _connection_pool


async def shutdown_connection_pool() -> None:
    """Shutdown the global connection pool."""
    global _connection_pool
    if _connection_pool is not None:
        await _connection_pool.shutdown()
        _connection_pool = None
