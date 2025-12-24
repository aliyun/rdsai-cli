"""Pure type definitions for database services.

This module contains type definitions without any runtime dependencies,
avoiding circular import issues between service modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ========== Connection Status ==========


class ConnectionStatus(str, Enum):
    """Database connection status enumeration."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class QueryStatus(str, Enum):
    """Query execution status enumeration."""

    SUCCESS = "success"
    ERROR = "error"


# ========== Query Types ==========


class QueryType(Enum):
    """Types of SQL queries."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    SHOW = "SHOW"
    DESCRIBE = "DESCRIBE"
    DESC = "DESC"
    EXPLAIN = "EXPLAIN"
    USE = "USE"
    SET = "SET"
    BEGIN = "BEGIN"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    TRUNCATE = "TRUNCATE"
    REPLACE = "REPLACE"
    OTHER = "OTHER"


# Query types that return result sets (rows and columns)
RESULT_SET_QUERY_TYPES = frozenset(
    [
        QueryType.SELECT,
        QueryType.SHOW,
        QueryType.DESCRIBE,
        QueryType.DESC,
        QueryType.EXPLAIN,
    ]
)


# ========== Query Result ==========


@dataclass
class QueryResult:
    """Result of a database query."""

    query_type: QueryType
    success: bool
    rows: list[Any]
    columns: list[str] | None = None
    affected_rows: int | None = None
    execution_time: float | None = None
    error: str | None = None

    @property
    def has_data(self) -> bool:
        """Check if result has data rows."""
        return bool(self.rows)

    @property
    def row_count(self) -> int:
        """Get number of rows in result."""
        return len(self.rows) if self.rows else 0


# ========== Schema Info ==========


@dataclass
class SchemaInfo:
    """Database schema information."""

    current_database: str | None
    tables: list[str]
    table_details: dict[str, dict[str, Any]]

    def get_table_names_preview(self, limit: int = 20) -> str:
        """Get formatted preview of table names."""
        if not self.tables:
            return "No tables found"

        if len(self.tables) <= limit:
            return ", ".join(self.tables)
        else:
            preview = ", ".join(self.tables[:limit])
            return f"{preview} (and {len(self.tables) - limit} more)"


# ========== Connection Config ==========


@dataclass
class ConnectionConfig:
    """Database connection configuration."""

    engine: str = "mysql"
    host: str = "localhost"
    port: int | None = None
    user: str = ""
    password: str | None = None
    database: str | None = None
    connection_timeout: int = 10
    ssl_options: dict[str, Any] = field(default_factory=dict)

    # Allowed SSL option keys to prevent accidental override of core config
    _SSL_ALLOWED_KEYS: frozenset = field(
        default=frozenset({"ssl_ca", "ssl_cert", "ssl_key", "ssl_mode", "ssl_verify_cert", "ssl_verify_identity"}),
        init=False,
        repr=False,
    )

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.user:
            raise ValueError("User is required for database connection")

        # Set default ports based on engine
        if self.port is None:
            default_ports = {"mysql": 3306, "postgresql": 5432, "sqlite": None}
            self.port = default_ports.get(self.engine)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for client creation."""
        config_dict = {
            "engine": self.engine,
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
        }

        if self.port is not None:
            config_dict["port"] = self.port

        # Add only allowed SSL options to prevent override of core config
        if self.ssl_options:
            for key, value in self.ssl_options.items():
                if key in self._SSL_ALLOWED_KEYS and value is not None:
                    config_dict[key] = value

        return {k: v for k, v in config_dict.items() if v is not None}


# ========== Last Query Context ==========


@dataclass
class LastQueryContext:
    """Last SQL query result context for agent injection."""

    sql: str
    status: QueryStatus
    columns: list[str] | None = None
    rows: list[Any] | None = None
    row_count: int = 0
    affected_rows: int | None = None
    execution_time: float | None = None
    error_message: str | None = None


# ========== Connection Context ==========


@dataclass
class ConnectionContext:
    """Database connection context with service instances and status info.

    Note: db_service and query_history are typed as Any to avoid circular imports.
    At runtime, they are DatabaseService and QueryHistory instances respectively.
    """

    db_service: Any = None  # DatabaseService instance
    query_history: Any = None  # QueryHistory instance
    status: str = field(default_factory=lambda: ConnectionStatus.DISCONNECTED.value)
    display_name: str = ""
    error: str | None = None

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.status == ConnectionStatus.CONNECTED.value

    @property
    def welcome_level(self) -> str:
        """Get log level for welcome message."""
        return "WARN" if self.status == ConnectionStatus.FAILED.value else "INFO"
