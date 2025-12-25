"""Core database service with unified connection management and business logic.

This module provides:
- DatabaseService: Main service class for database operations
- Global state management functions
- Factory functions for creating connections
"""

from __future__ import annotations

import getpass
import re
from datetime import datetime
from threading import Lock
from typing import Any, TYPE_CHECKING
from collections.abc import Callable

from .types import (
    ConnectionConfig,
    ConnectionContext,
    ConnectionStatus,
    LastQueryContext,
    QueryResult,
    QueryStatus,
    QueryType,
    SchemaInfo,
    RESULT_SET_QUERY_TYPES,
)
from .client import DatabaseClient, DatabaseClientFactory, TransactionState, validate_identifier
from .errors import ConnectionError, DatabaseError, handle_database_error
from .history import QueryHistory
from utils.logging import logger

if TYPE_CHECKING:
    pass


# ========== Global State ==========

_global_service: DatabaseService | None = None


def get_service() -> DatabaseService | None:
    """Get the global database service instance."""
    return _global_service


def set_service(service: DatabaseService) -> None:
    """Set the global database service instance."""
    global _global_service
    _global_service = service


def clear_service() -> None:
    """Clear the global database service."""
    global _global_service
    _global_service = None


# Convenience aliases for backward compatibility
def get_database_service() -> DatabaseService | None:
    """Get the global database service (alias for get_service)."""
    return _global_service


def set_database_service(service: DatabaseService) -> None:
    """Set the global database service (alias for set_service)."""
    set_service(service)


def get_database_client() -> DatabaseClient | None:
    """Get the current database client."""
    if _global_service and _global_service.is_connected():
        return _global_service.get_active_connection()
    return None


def get_current_database() -> str | None:
    """Get the current database name."""
    if _global_service:
        return _global_service.current_database
    return None


# ========== Callback Type ==========

SchemaChangeCallback = Callable[[], None]


# ========== Helper Functions ==========


def extract_single_column(rows: list[Any]) -> list[str]:
    """Extract single column values from query result rows as strings."""
    result = []
    for row in rows:
        if isinstance(row, (list, tuple)):
            result.append(str(row[0]))
        else:
            result.append(str(row))
    return result


def extract_first_value(row: Any) -> Any | None:
    """Extract the first value from a single row result."""
    if row is None:
        return None
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    return row


# ========== Query Context Management ==========


def format_query_context_for_agent(context: LastQueryContext, max_display_rows: int = 50) -> str:
    """Format the last query context as a string for agent injection."""
    lines = ["[Recent Query Result]", f"SQL: {context.sql}", f"Status: {context.status.value}"]
    if context.execution_time is not None:
        lines.append(f"Execution Time: {context.execution_time:.3f}s")

    if context.status == QueryStatus.ERROR:
        lines.append(f"Error: {context.error_message}")
        lines.append("")
        return "\n".join(lines)

    if context.affected_rows is not None:
        lines.append(f"Affected Rows: {context.affected_rows}")

    if context.columns and context.rows:
        display_rows = context.rows[:max_display_rows]
        truncated = len(context.rows) > max_display_rows

        lines.append(f"Result ({context.row_count} rows):")
        lines.append("")
        lines.append("| " + " | ".join(str(col) for col in context.columns) + " |")
        lines.append("| " + " | ".join("---" for _ in context.columns) + " |")

        for row in display_rows:
            formatted_cells = []
            for cell in row:
                if cell is None:
                    formatted_cells.append("NULL")
                else:
                    cell_str = str(cell)
                    if len(cell_str) > 50:
                        cell_str = cell_str[:47] + "..."
                    formatted_cells.append(cell_str)
            lines.append("| " + " | ".join(formatted_cells) + " |")

        if truncated:
            lines.append(f"... ({context.row_count - max_display_rows} more rows not shown)")
    elif not context.rows:
        lines.append("Result: Empty (0 rows)")

    lines.append("")
    return "\n".join(lines)


# ========== Database Service ==========


class DatabaseService:
    """Unified database service: connection management + query execution + transactions + schema."""

    # Pattern to match vertical format directive (\G) at end of SQL
    _VERTICAL_FORMAT_PATTERN = r"\s*\\[Gg]\s*;?\s*$"

    # Query type prefixes for efficient classification
    _QUERY_TYPE_PREFIXES: tuple[tuple[str, QueryType], ...] = (
        ("WITH", QueryType.SELECT),  # CTE queries return result sets like SELECT
        ("SELECT", QueryType.SELECT),
        ("INSERT", QueryType.INSERT),
        ("UPDATE", QueryType.UPDATE),
        ("DELETE", QueryType.DELETE),
        ("SHOW", QueryType.SHOW),
        ("SET", QueryType.SET),
        ("CREATE", QueryType.CREATE),
        ("DROP", QueryType.DROP),
        ("ALTER", QueryType.ALTER),
        ("DESCRIBE", QueryType.DESCRIBE),
        ("DESC", QueryType.DESC),
        ("EXPLAIN", QueryType.EXPLAIN),
        ("USE", QueryType.USE),
        ("BEGIN", QueryType.BEGIN),
        ("START TRANSACTION", QueryType.BEGIN),
        ("COMMIT", QueryType.COMMIT),
        ("ROLLBACK", QueryType.ROLLBACK),
        ("GRANT", QueryType.GRANT),
        ("REVOKE", QueryType.REVOKE),
        ("TRUNCATE", QueryType.TRUNCATE),
        ("REPLACE", QueryType.REPLACE),
    )

    # Optional modifiers that can appear before SHOW target keywords
    _OPTIONAL_MODIFIERS: frozenset[str] = frozenset(
        ["FULL", "EXTENDED", "GLOBAL", "SESSION", "MASTER", "SLAVE", "REPLICA"]
    )

    # Valid SHOW statement target keywords
    _VALID_SHOW_TARGETS: frozenset[str] = frozenset(
        [
            "TABLES",
            "SCHEMAS",  # Alias for DATABASES
            "CREATE",
            "INDEX",
            "DATABASES",
            "PROCESSLIST",
            "VARIABLES",
            "STATUS",
            "ENGINE",
            "SLAVE",
            "REPLICA",
            "GRANTS",
            "WARNINGS",
            "ERRORS",
            "TABLE",
            "COLUMNS",
            "FIELDS",
            "KEYS",
            "TRIGGERS",
            "PROCEDURE",
            "FUNCTION",
        ]
    )

    def __init__(self):
        """Initialize database service."""
        self._active_connection: DatabaseClient | None = None
        self._connection_config: ConnectionConfig | None = None
        self._lock = Lock()
        self._connection_id: str | None = None
        self._schema_change_callbacks: list[SchemaChangeCallback] = []
        # Internal state
        self._current_database: str | None = None
        self._last_query_context: LastQueryContext | None = None

    # ========== Properties ==========

    @property
    def current_database(self) -> str | None:
        """Get current database name."""
        return self._current_database

    # ========== Last Query Context ==========

    def get_last_query_context(self) -> LastQueryContext | None:
        """Get the last query context."""
        return self._last_query_context

    def set_last_query_context(
        self,
        sql: str,
        status: QueryStatus = QueryStatus.SUCCESS,
        columns: list[str] | None = None,
        rows: list[Any] | None = None,
        affected_rows: int | None = None,
        execution_time: float | None = None,
        error_message: str | None = None,
        max_rows: int = 100,
    ) -> None:
        """Set the last query context for agent injection."""
        stored_rows = None
        row_count = 0
        if rows:
            stored_rows = rows[:max_rows] if len(rows) > max_rows else rows
            row_count = len(rows)

        self._last_query_context = LastQueryContext(
            sql=sql,
            status=status,
            columns=columns,
            rows=stored_rows,
            row_count=row_count,
            affected_rows=affected_rows,
            execution_time=execution_time,
            error_message=error_message,
        )

    def consume_last_query_context(self) -> LastQueryContext | None:
        """Get and clear the last query context."""
        context = self._last_query_context
        self._last_query_context = None
        return context

    def clear_last_query_context(self) -> None:
        """Clear the last query context."""
        self._last_query_context = None

    # ========== Schema Change Callbacks ==========

    def register_schema_change_callback(self, callback: SchemaChangeCallback) -> None:
        """Register a callback to be notified when schema changes."""
        if callback not in self._schema_change_callbacks:
            self._schema_change_callbacks.append(callback)

    def unregister_schema_change_callback(self, callback: SchemaChangeCallback) -> None:
        """Unregister a schema change callback."""
        if callback in self._schema_change_callbacks:
            self._schema_change_callbacks.remove(callback)

    def _notify_schema_change(self) -> None:
        """Notify all registered callbacks of a schema change."""
        for callback in self._schema_change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Schema change callback failed: {e}")

    # ========== Connection Management ==========

    def is_connected(self) -> bool:
        """Check if connected to database."""
        with self._lock:
            return self._active_connection is not None

    def connect(self, config: ConnectionConfig) -> str:
        """Create a new database connection."""
        if config.password is None and config.user:
            config.password = getpass.getpass("Enter password: ")

        try:
            client = DatabaseClientFactory.create(**config.to_dict())

            with self._lock:
                if self._active_connection:
                    try:
                        self._active_connection.close()
                    except Exception as e:
                        logger.warning(f"Error closing previous connection: {e}")

                self._active_connection = client
                self._connection_config = config
                self._connection_id = f"{config.engine}_{config.host}_{config.port}_{config.user}"

            # Initialize current database
            if config.database:
                self._current_database = config.database
            else:
                try:
                    client.execute("SELECT DATABASE()")
                    result = client.fetchone()
                    self._current_database = extract_first_value(result)
                except Exception as e:
                    logger.warning(f"Failed to get current database after connection: {e}")
                    self._current_database = None

            logger.info(f"Connected to {config.engine} database at {config.host}:{config.port}")
            self._notify_schema_change()

            return self._connection_id

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from the current database."""
        with self._lock:
            if self._active_connection:
                try:
                    client = self._active_connection
                    client.close()
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.error(f"Error closing database connection: {e}")
                finally:
                    self._active_connection = None
                    self._connection_config = None
                    self._connection_id = None
                    self._current_database = None

        self._notify_schema_change()

    def reconnect(self) -> str:
        """Reconnect using the last configuration."""
        if not self._connection_config:
            raise ValueError("No previous connection configuration available")
        logger.info("Attempting to reconnect to database...")
        return self.connect(self._connection_config)

    def get_active_connection(self) -> DatabaseClient | None:
        """Get the current active database connection."""
        with self._lock:
            return self._active_connection

    def _get_client_or_raise(self) -> DatabaseClient:
        """Get the active database client, raising an error if not connected."""
        client = self.get_active_connection()
        if not client:
            raise DatabaseError("No active database connection")
        return client

    def get_connection_info(self) -> dict[str, Any]:
        """Get current connection information."""
        with self._lock:
            if not self._active_connection or not self._connection_config:
                return {"connected": False}

            config = self._connection_config
            client = self._active_connection

            info = {
                "connected": True,
                "connection_id": self._connection_id,
                "engine": config.engine,
                "host": config.host,
                "port": config.port,
                "user": config.user,
                "database": self._current_database,
            }

            if config.ssl_options:
                info["ssl_enabled"] = True

            if client:
                try:
                    info["transaction_state"] = client.get_transaction_state().value
                    info["autocommit"] = client.get_autocommit()
                except Exception as e:
                    logger.warning(f"Failed to get extended connection info: {e}")

            return info

    # ========== Query Execution ==========

    def execute_query(self, sql: str) -> QueryResult:
        """Execute SQL query and return structured result."""
        client = self._get_client_or_raise()

        sql = self._clean_display_directives(sql)
        query_type = self._classify_query(sql)
        start_time = datetime.now()

        try:
            client.execute(sql)

            if query_type in RESULT_SET_QUERY_TYPES:
                rows = client.fetchall()
                columns = client.get_columns()
                affected_rows = None
            else:
                rows = []
                columns = None
                row_count = client.get_row_count()
                affected_rows = row_count if row_count >= 0 else None

            execution_time = (datetime.now() - start_time).total_seconds()

            if query_type == QueryType.USE:
                db_name = self._extract_database_from_use(sql)
                if db_name:
                    self._current_database = db_name
                self._notify_schema_change()

            if query_type in (QueryType.CREATE, QueryType.DROP, QueryType.ALTER):
                self._notify_schema_change()

            return QueryResult(
                query_type=query_type,
                success=True,
                rows=rows if rows is not None else [],
                columns=columns,
                affected_rows=affected_rows,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            db_error = handle_database_error(
                e,
                {
                    "sql": sql[:200] + "..." if len(sql) > 200 else sql,
                    "execution_time": execution_time,
                    "query_type": query_type.value if query_type else None,
                },
            )

            return QueryResult(
                query_type=query_type, success=False, rows=[], execution_time=execution_time, error=str(db_error)
            )

    def has_vertical_format_directive(self, sql: str) -> bool:
        r"""Check if SQL contains vertical format directive (\G)."""
        return bool(re.search(self._VERTICAL_FORMAT_PATTERN, sql))

    def _clean_display_directives(self, sql: str) -> str:
        r"""Remove client display directives (like \G) from SQL."""
        return re.sub(self._VERTICAL_FORMAT_PATTERN, lambda m: ";" if ";" in m.group() else "", sql)

    def _classify_query(self, sql: str) -> QueryType:
        """Classify SQL query type using efficient prefix matching."""
        if not sql or not sql.strip():
            return QueryType.OTHER

        sql_upper = sql.strip().upper()

        for prefix, query_type in self._QUERY_TYPE_PREFIXES:
            if sql_upper.startswith(prefix):
                if len(sql_upper) == len(prefix) or not sql_upper[len(prefix)].isalnum():
                    return query_type

        return QueryType.OTHER

    def is_transaction_control_statement(self, sql: str) -> tuple[bool, QueryType | None]:
        """Check if SQL is a transaction control statement."""
        query_type = self._classify_query(sql)
        if query_type in (QueryType.BEGIN, QueryType.COMMIT, QueryType.ROLLBACK):
            return True, query_type
        return False, None

    def _extract_database_from_use(self, sql: str) -> str | None:
        """Extract database name from USE statement."""
        if not sql or not sql.strip():
            return None
        pattern = r"USE\s+(?:`)?([^`;\s]+)(?:`)?"
        match = re.search(pattern, sql.strip(), re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def is_sql_statement(self, command: str) -> bool:
        """Check if command is a SQL statement using enhanced validation.

        First checks if the command starts with a SQL keyword. For SHOW statements,
        validates that it's followed by a valid SHOW target to prevent natural language
        queries like "show me slow queries" from being treated as SQL.
        """
        if not command:
            return False

        # Step 1: Quick check - does it start with a SQL keyword?
        query_type = self._classify_query(command)
        if query_type == QueryType.OTHER:
            return False  # Not a SQL keyword, definitely not SQL

        # Step 2: Special handling for SHOW statements
        # SHOW is commonly used in natural language (e.g., "show me...")
        # so we need to validate it more strictly
        if query_type == QueryType.SHOW:
            # Cache string processing result to avoid repeated operations
            command_upper = command.strip().upper()
            rest = command_upper[4:].strip()  # After "SHOW"

            if not rest:
                return False  # "SHOW" alone is incomplete

            # Use efficient token parsing with next() and generator expression
            tokens = rest.split()
            target = next(
                (token.rstrip(";") for token in tokens if token not in self._OPTIONAL_MODIFIERS),
                None,
            )

            if target is None:
                return False  # Only modifiers, no actual target

            return target in self._VALID_SHOW_TARGETS

        # Step 3: For other SQL keywords, use basic keyword check
        # This maintains backward compatibility
        return True

    # ========== Transaction Management ==========

    def begin_transaction(self) -> None:
        """Begin a new transaction."""
        client = self._get_client_or_raise()
        try:
            client.begin_transaction()
            logger.debug("Transaction started")
        except Exception as e:
            raise handle_database_error(e, {"operation": "begin"})

    def commit_transaction(self) -> None:
        """Commit current transaction."""
        client = self._get_client_or_raise()
        try:
            client.commit_transaction()
            logger.debug("Transaction committed")
        except Exception as e:
            raise handle_database_error(e, {"operation": "commit"})

    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        client = self._get_client_or_raise()
        try:
            client.rollback_transaction()
            logger.debug("Transaction rolled back")
        except Exception as e:
            raise handle_database_error(e, {"operation": "rollback"})

    def set_autocommit(self, enabled: bool) -> None:
        """Set autocommit mode."""
        client = self._get_client_or_raise()
        try:
            client.set_autocommit(enabled)
            logger.debug(f"Autocommit set to {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            raise handle_database_error(e, {"operation": f"set_autocommit({enabled})"})

    def get_transaction_state(self) -> TransactionState | None:
        """Get current transaction state."""
        client = self.get_active_connection()
        if not client:
            return None
        return client.get_transaction_state()

    def get_autocommit_status(self) -> bool | None:
        """Get current autocommit status."""
        client = self.get_active_connection()
        if not client:
            return None
        return client.get_autocommit()

    def get_current_database(self) -> str | None:
        """Get current database name."""
        if not self.is_connected():
            return None
        return self._current_database

    # ========== Schema Operations ==========

    def get_schema_info(self) -> SchemaInfo:
        """Get comprehensive schema information."""
        self._get_client_or_raise()
        try:
            current_db = self.get_current_database()
            tables = self._get_tables()

            return SchemaInfo(current_database=current_db, tables=tables, table_details={})
        except Exception as e:
            raise handle_database_error(e, {"operation": "get_schema_info"})

    def _get_tables(self) -> list[str]:
        """Get list of tables in current database."""
        client = self.get_active_connection()
        if not client:
            return []

        try:
            client.execute("SHOW TABLES")
            result = client.fetchall()
            return extract_single_column(result)
        except Exception as e:
            logger.warning(f"Failed to get table list: {e}")
            return []

    def get_table_structure(self, table_name: str) -> list[tuple[Any, ...]]:
        """Get structure information for a specific table."""
        client = self._get_client_or_raise()
        validated_name = validate_identifier(table_name)
        try:
            client.execute(f"DESCRIBE `{validated_name}`")
            return client.fetchall()
        except Exception as e:
            raise handle_database_error(e, {"operation": "describe_table", "table_name": table_name})

    def change_database(self, database_name: str) -> None:
        """Change to specified database."""
        client = self._get_client_or_raise()
        try:
            client.change_database(database_name)
            self._current_database = database_name
            logger.info(f"Changed to database: {database_name}")
            self._notify_schema_change()
        except Exception as e:
            raise handle_database_error(e, {"operation": "change_database", "database": database_name})

    def get_databases(self) -> list[str]:
        """Get list of available databases."""
        client = self._get_client_or_raise()
        try:
            client.execute("SHOW DATABASES")
            result = client.fetchall()
            return extract_single_column(result)
        except Exception as e:
            raise handle_database_error(e, {"operation": "show_databases"})

    # ========== Context Manager ==========

    def __enter__(self) -> DatabaseService:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, ensuring connection is closed."""
        self.disconnect()

    def __del__(self) -> None:
        """Cleanup on object destruction."""
        with self._lock:
            if self._active_connection:
                try:
                    self._active_connection.close()
                except Exception:
                    pass


# ========== Factory Functions ==========


def create_connection_context(
    host: str,
    port: int | None,
    user: str,
    password: str | None,
    database: str | None,
    ssl_ca: str | None = None,
    ssl_cert: str | None = None,
    ssl_key: str | None = None,
    ssl_mode: str | None = None,
) -> ConnectionContext:
    """Create a database connection context with connected service and query history."""
    ssl_options = {}
    if ssl_ca:
        ssl_options["ssl_ca"] = ssl_ca
    if ssl_cert:
        ssl_options["ssl_cert"] = ssl_cert
    if ssl_key:
        ssl_options["ssl_key"] = ssl_key
    if ssl_mode:
        ssl_options["ssl_mode"] = ssl_mode

    connection_config = ConnectionConfig(
        engine="mysql",
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl_options=ssl_options,
    )

    db_service = DatabaseService()
    query_history = QueryHistory(max_entries=100)

    try:
        db_service.connect(connection_config)
        set_service(db_service)

        return ConnectionContext(
            db_service=db_service,
            query_history=query_history,
            status=ConnectionStatus.CONNECTED.value,
            display_name=f"{database or 'mysql'}://{host}",
        )
    except Exception as e:
        return ConnectionContext(
            db_service=db_service,
            query_history=query_history,
            status=ConnectionStatus.FAILED.value,
            display_name=f"{database or 'mysql'}://{host}",
            error=str(e),
        )


def create_database_service() -> DatabaseService:
    """Create a new database service instance (not connected)."""
    return DatabaseService()


# Alias for backward compatibility
create_database_connection_context = create_connection_context
