"""Main application module for RDS AI CLI."""

from __future__ import annotations

import asyncio
import contextlib
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from config import LLMModel, LLMProvider, Session, get_share_dir, load_config
from llm.llm import create_llm
from loop.agent import load_agent
from loop.agentspec import DEFAULT_AGENT_FILE
from loop.neoloop import NeoLoop
from loop.runtime import Runtime
from tools.mcp.client import get_connection_pool, shutdown_connection_pool
from utils.logging import StreamToLogger, logger

if TYPE_CHECKING:
    from database import ConnectionContext
    from ui import ShellREPL
else:
    ConnectionContext = Any
    ShellREPL = Any

DatabaseConnectionContext = ConnectionContext


def enable_logging(debug: bool = False) -> None:
    logger.add(
        get_share_dir() / "logs" / "rdsai-cli.log",
        level="TRACE" if debug else "INFO",
        rotation="20 MB",
        retention="5 days",
    )


class Application:
    """Main application with lifecycle management.

    Usage:
        async with await Application.create(session, yolo=yolo) as app:
            await app.run()
    """

    @staticmethod
    async def create(
        session: Session,
        *,
        yolo: bool = False,
        config_file: Path | None = None,
    ) -> Application:
        """Create an Application instance.

        Args:
            session: A session created by `Session.create`.
            yolo: Approve all actions without confirmation. Defaults to False.
            config_file: Path to the configuration file. Defaults to None.

        Raises:
            FileNotFoundError: When the agent file is not found.
            ConfigError(CLIException): When the configuration is invalid.
            AgentSpecError(CLIException): When the agent specification is invalid.
        """
        config = load_config(config_file)
        logger.info("Loaded config: {config}", config=config)

        # Load MCP configuration from default path
        from tools.mcp.config import load_mcp_config

        mcp_config = None
        try:
            mcp_config = load_mcp_config()
            if mcp_config:
                enabled_count = len(mcp_config.get_enabled_servers())
                logger.info(
                    "Loaded MCP config with {total} servers ({enabled} enabled)",
                    total=len(mcp_config.servers),
                    enabled=enabled_count,
                )
        except ValueError as e:
            logger.error("Invalid MCP config: {error}", error=e)

        model: LLMModel | None = None
        provider: LLMProvider | None = None

        # use config file
        if config.default_model:
            # no --model specified && default model is set in config
            model = config.models[config.default_model]
            provider = config.providers[model.provider]

        if not model:
            model = LLMModel(provider="", model="", max_context_size=0)
            provider = LLMProvider(type="qwen", base_url="", api_key=SecretStr(""))

        assert provider is not None
        assert model is not None

        if not provider.api_key or not model.model:
            llm = None
        else:
            logger.info("Using LLM provider: {provider}", provider=provider)
            logger.info("Using LLM model: {model}", model=model)
            llm = create_llm(provider, model)

        runtime = await Runtime.create(config, llm, session, mcp_config, yolo)
        agent = await load_agent(DEFAULT_AGENT_FILE, runtime)

        # Create NeoLoop with LangGraph (no Context needed - uses checkpointer)
        loop = NeoLoop(agent)

        return Application(loop, runtime)

    def __init__(
        self,
        _loop: NeoLoop,
        _runtime: Runtime,
    ) -> None:
        self._loop = _loop
        self._runtime = _runtime
        self._mcp_task: asyncio.Task[None] | None = None
        self._mcp_pool = get_connection_pool()

    @property
    def loop(self) -> NeoLoop:
        """Get the NeoLoop instance."""
        return self._loop

    @property
    def session(self) -> Session:
        """Get the Session instance."""
        return self._runtime.session

    @property
    def _db_connection(self) -> DatabaseConnectionContext | None:
        """Get the database connection from session."""
        return self._runtime.session.db_connection

    # --- Async Context Manager ---

    async def __aenter__(self) -> Application:
        """Start all resources."""
        # Start MCP connection pool manager
        await self._mcp_pool.start()

        # Start background task to connect enabled MCP servers (non-blocking)
        self._mcp_task = asyncio.create_task(self._connect_enabled_mcp_servers())

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup all resources."""
        # Clean up database connection
        if self._db_connection and self._db_connection.db_service:
            self._db_connection.db_service.disconnect()

        # Cancel MCP connection task if still running
        if self._mcp_task:
            self._mcp_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._mcp_task

        # Shutdown MCP connection pool (safely closes all connections)
        await self._mcp_pool.shutdown()
        await shutdown_connection_pool()

    # --- Main Run Method ---

    async def run(self) -> bool:
        """Run the interactive shell."""
        from ui import ShellREPL

        welcome_info = self._build_welcome_info()

        with self._app_env():
            db_service = self._db_connection.db_service if self._db_connection else None
            query_history = self._db_connection.query_history if self._db_connection else None

            repl = ShellREPL(
                self._loop,
                welcome_info=welcome_info,
                db_service=db_service,
                query_history=query_history,
            )
            return await repl.run()

    # --- Helper Methods ---

    def _build_welcome_info(self) -> list:
        """Build welcome information for the shell."""
        from config import VERSION
        from ui import WelcomeInfoItem

        welcome_info = [
            WelcomeInfoItem(name="Version", value=VERSION),
            WelcomeInfoItem(name="Session", value=self._runtime.session.id),
        ]
        # Add model information
        if not self._runtime.llm:
            welcome_info.append(
                WelcomeInfoItem(
                    name="Model",
                    value="not set, send /setup to configure",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )
        else:
            welcome_info.append(
                WelcomeInfoItem(
                    name="Model",
                    value=self._loop.model_name,
                    level=WelcomeInfoItem.Level.INFO,
                )
            )
        # Add database connection info
        if self._db_connection and self._db_connection.is_connected:
            welcome_info.append(
                WelcomeInfoItem(
                    name="Database", value=self._db_connection.display_name, level=WelcomeInfoItem.Level.INFO
                )
            )
        elif self._db_connection and not self._db_connection.is_connected:
            # Connection failed - show error message
            error_msg = self._db_connection.error or "Connection failed"
            welcome_info.append(
                WelcomeInfoItem(
                    name="Database",
                    value=f"{error_msg}.\nUse /connect to reconnect.",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )
        else:
            # Not connected - no connection parameters provided
            welcome_info.append(
                WelcomeInfoItem(
                    name="Database",
                    value="Not connected. Use /connect to connect.",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )

        return welcome_info

    @contextlib.contextmanager
    def _app_env(self) -> Generator[None]:
        # to ignore possible warnings from dateparser
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        with contextlib.redirect_stderr(StreamToLogger()):
            yield

    async def _connect_enabled_mcp_servers(self):
        """Connect to enabled MCP servers in the background.

        This runs as a background task and does not block CLI startup.
        """
        from tools.mcp.toolset import connect_and_load_tools

        mcp_config = self._runtime.mcp_config
        if not mcp_config:
            return

        enabled_servers = mcp_config.get_enabled_servers()
        if not enabled_servers:
            return

        logger.info("Starting background connection to {count} enabled MCP server(s)", count=len(enabled_servers))

        for server in enabled_servers:
            try:
                tools = await connect_and_load_tools(server)
                added = self._loop.toolset.add_tools(tools)
                logger.info("Connected to MCP server '{name}', added {count} tools", name=server.name, count=added)
            except asyncio.CancelledError:
                logger.debug("MCP connection task cancelled")
                break
            except Exception as e:
                logger.warning("Failed to connect to MCP server '{name}': {error}", name=server.name, error=str(e))
