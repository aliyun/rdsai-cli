"""Base configuration and application constants.

This module consolidates:
- Version constants (from constant.py)
- Shared directory paths (from share.py)
- Session management (from session.py)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version as get_package_version
from pathlib import Path

from utils.logging import logger
from database import create_database_connection_context, ConnectionContext

# Backward compatibility alias
DatabaseConnectionContext = ConnectionContext


def _get_version() -> str:
    """Get version from package metadata or pyproject.toml.

    Tries to read version in this order:
    1. From installed package metadata (importlib.metadata)
    2. From pyproject.toml file (development mode)

    Returns:
        Version string with "v" prefix (e.g., "v0.1.2")
    """
    try:
        pkg_version = get_package_version("rdsai-cli")
        # Add "v" prefix if not present
        return pkg_version if pkg_version.startswith("v") else f"v{pkg_version}"
    except PackageNotFoundError:
        pass
    return "UNKNOW"


VERSION = _get_version()
USER_AGENT = f"RDSAI_CLI/{VERSION}"


# ========== Shared Directory ==========


def get_share_dir() -> Path:
    """Get the share directory path.

    Returns:
        Path to the shared directory (~/.rdsai-cli)
    """
    share_dir = Path.home() / ".rdsai-cli"
    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


def get_config_file() -> Path:
    """Get the configuration file path.

    Returns:
        Path to the config file (~/.rdsai-cli/config.json)
    """
    return get_share_dir() / "config.json"


# ========== Session Management ==========


@dataclass(slots=True, kw_only=True)
class Session:
    """A CLI session with SessionID and database connection management.

    Attributes:
        id: Unique session identifier (UUID)
        _db_connection: Current database connection context (mutable)
    """

    id: str
    _db_connection: DatabaseConnectionContext | None = field(default=None, repr=False)

    @property
    def db_connection(self) -> DatabaseConnectionContext | None:
        """Get the current database connection."""
        return self._db_connection

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._db_connection is not None and self._db_connection.is_connected

    def connect(
        self,
        host: str,
        user: str,
        port: int | None = None,
        password: str | None = None,
        database: str | None = None,
        ssl_ca: str | None = None,
        ssl_cert: str | None = None,
        ssl_key: str | None = None,
        ssl_mode: str | None = None,
    ) -> DatabaseConnectionContext:
        """Connect to a database.

        If already connected, disconnects first.

        Args:
            host: Database server hostname
            user: Database username
            port: Database server port (None for default)
            password: Database password
            database: Default database name
            ssl_ca: SSL CA certificate file path
            ssl_cert: SSL client certificate file path
            ssl_key: SSL client private key file path
            ssl_mode: SSL connection mode

        Returns:
            DatabaseConnectionContext with connection status
        """
        # Disconnect existing connection if any
        self.disconnect()

        # Create new connection
        self._db_connection = create_database_connection_context(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl_ca=ssl_ca,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
            ssl_mode=ssl_mode,
        )

        if self._db_connection.is_connected:
            logger.info("Session {id} connected to {host}", id=self.id, host=host)
        else:
            logger.warning(
                "Session {id} failed to connect to {host}: {error}",
                id=self.id,
                host=host,
                error=self._db_connection.error,
            )

        return self._db_connection

    def disconnect(self) -> None:
        """Disconnect from the current database."""
        if self._db_connection and self._db_connection.db_service:
            self._db_connection.db_service.disconnect()
            logger.info("Session {id} disconnected", id=self.id)
        self._db_connection = None

    @staticmethod
    def create_empty() -> Session:
        """Create a new session without database connection.

        Returns:
            New Session instance without database connection
        """
        session_id = str(uuid.uuid4())
        logger.debug("Creating new empty session: {session_id}", session_id=session_id)
        return Session(id=session_id)

    @staticmethod
    def create(
        host: str,
        user: str,
        port: int | None = None,
        password: str | None = None,
        database: str | None = None,
        ssl_ca: str | None = None,
        ssl_cert: str | None = None,
        ssl_key: str | None = None,
        ssl_mode: str | None = None,
    ) -> Session:
        """Create a new session and connect to database.

        Args:
            host: Database server hostname
            user: Database username
            port: Database server port (None for default)
            password: Database password
            database: Default database name
            ssl_ca: SSL CA certificate file path
            ssl_cert: SSL client certificate file path
            ssl_key: SSL client private key file path
            ssl_mode: SSL connection mode

        Returns:
            New Session instance with database connection
        """
        session_id = str(uuid.uuid4())
        logger.debug("Creating new session: {session_id}", session_id=session_id)

        session = Session(id=session_id)

        # Connect to database
        session.connect(
            host=host,
            user=user,
            port=port,
            password=password,
            database=database,
            ssl_ca=ssl_ca,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
            ssl_mode=ssl_mode,
        )

        return session
