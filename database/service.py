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
from pathlib import Path
from threading import Lock
from typing import Any, Literal, TYPE_CHECKING
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
        ("SOURCE", QueryType.SOURCE),
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
        # Vector capability state
        self._vector_capability_status: Literal["UNKNOWN", "ENABLED", "DISABLED"] = "UNKNOWN"
        self._vector_capability_error: str | None = None
        # SOURCE command display callback
        self._source_display_callback: Callable[[QueryResult, str, bool], None] | None = None

    # ========== Properties ==========

    @property
    def current_database(self) -> str | None:
        """Get current database name."""
        return self._current_database

    # ========== Vector Capability ==========

    def _detect_vector_capability(self) -> None:
        """Detect vector capability by checking vidx_disabled variable.

        Sets _vector_capability_status to:
        - ENABLED: if vidx_disabled='OFF'
        - DISABLED: if vidx_disabled!='OFF' or variable not found
        - UNKNOWN: if detection fails with exception
        """
        if not self._active_connection:
            self._vector_capability_status = "UNKNOWN"
            self._vector_capability_error = "No active connection"
            return

        try:
            self._active_connection.execute("SHOW VARIABLES LIKE 'vidx_disabled'")
            rows = self._active_connection.fetchall()

            if not rows:
                # Variable not found - vector capability not available
                self._vector_capability_status = "DISABLED"
                self._vector_capability_error = None
                logger.info("Vector capability detected: DISABLED (variable not found)")
                return

            # Get the value from the second column (Variable_name, Value)
            value = rows[0][1].upper() if rows[0][1] else ""
            if value == "OFF":
                self._vector_capability_status = "ENABLED"
                self._vector_capability_error = None
                logger.info("Vector capability detected: ENABLED (vidx_disabled=OFF)")
            else:
                self._vector_capability_status = "DISABLED"
                self._vector_capability_error = None
                logger.info(f"Vector capability detected: DISABLED (vidx_disabled={rows[0][1]})")

        except Exception as e:
            # Detection failed - mark as unknown
            self._vector_capability_status = "UNKNOWN"
            self._vector_capability_error = str(e)
            logger.warning("Vector capability detection failed: {error}", error=e)

    def has_vector_capability(self) -> bool:
        """Check if vector capability is enabled.

        Returns:
            True if vector capability is ENABLED, False otherwise.
        """
        return self._vector_capability_status == "ENABLED"

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

    # ========== SOURCE Command Display Callback ==========

    def set_source_display_callback(self, callback: Callable[[QueryResult, str, bool], None] | None) -> None:
        """Set display callback for SOURCE command statements.

        This callback will be called for each statement executed within a SOURCE command,
        allowing the UI layer to format and display results immediately.

        Args:
            callback: Callback function that takes (result, sql, use_vertical) parameters.
                     If None, clears the callback.
        """
        self._source_display_callback = callback

    def clear_source_display_callback(self) -> None:
        """Clear the SOURCE command display callback."""
        self._source_display_callback = None

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
        client = None

        def _cleanup_client() -> None:
            """Helper to clean up partially created client."""
            if client is not None:
                try:
                    client.close()
                except Exception as e:
                    logger.debug(f"Error closing client during cleanup: {e}")

        def _clear_connection_state() -> None:
            """Helper to clear connection state if it matches the current client."""
            with self._lock:
                if self._active_connection == client:
                    self._active_connection = None
                    self._connection_config = None
                    self._connection_id = None

        try:
            # Prompt for password if needed (may raise KeyboardInterrupt)
            if config.password is None and config.user:
                config.password = getpass.getpass("Enter password: ")

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

            # Detect vector capability
            self._detect_vector_capability()

            logger.info(f"Connected to {config.engine} database at {config.host}:{config.port}")
            self._notify_schema_change()

            return self._connection_id

        except KeyboardInterrupt:
            # Clean up partially created connection
            _cleanup_client()
            _clear_connection_state()

            logger.info("Database connection cancelled by user")
            raise ConnectionError("Connection cancelled by user") from None
        except Exception as e:
            # Clean up partially created connection
            _cleanup_client()

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
                    # Clear vector capability state
                    self._vector_capability_status = "UNKNOWN"
                    self._vector_capability_error = None

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
        sql = self._clean_display_directives(sql)
        query_type = self._classify_query(sql)

        # Special handling for SOURCE command
        if query_type == QueryType.SOURCE:
            return self._execute_source_command(sql)

        client = self._get_client_or_raise()
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

    def _parse_source_path(self, sql: str) -> str:
        """Parse file path from SOURCE command.

        Supports:
        - SOURCE file.sql;
        - SOURCE /path/to/file.sql;
        - SOURCE 'file with spaces.sql';
        - SOURCE "file with spaces.sql";
        - SOURCE ~/scripts/init.sql;
        - SOURCE ./relative/path.sql;

        Args:
            sql: SOURCE command SQL string

        Returns:
            Parsed and normalized file path

        Raises:
            ValueError: If path is empty or invalid
        """
        if not sql or not sql.strip():
            raise ValueError("SOURCE command is empty")

        sql = sql.strip()
        # Remove trailing semicolon if present
        if sql.endswith(";"):
            sql = sql[:-1].rstrip()

        # Extract content after SOURCE keyword (case-insensitive)
        pattern = r"SOURCE\s+(.+)$"
        match = re.search(pattern, sql, re.IGNORECASE)
        if not match:
            raise ValueError("\nUsage: \\. <filename> | source <filename>")

        path_str = match.group(1).strip()
        if not path_str:
            raise ValueError("\nUsage: \\. <filename> | source <filename>")

        # Handle quoted paths
        if (path_str.startswith('"') and path_str.endswith('"')) or (
            path_str.startswith("'") and path_str.endswith("'")
        ):
            quote_char = path_str[0]
            path_str = path_str[1:-1]
            # Handle escaped quotes
            path_str = path_str.replace(f"\\{quote_char}", quote_char)
            path_str = path_str.replace("\\\\", "\\")

        return path_str

    def _read_script_file(self, file_path: str) -> tuple[str, Path]:
        """Read SQL script file content.

        Args:
            file_path: Path to the script file (can be relative or absolute)

        Returns:
            Tuple of (file_content, resolved_path)

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable
            ValueError: If path is invalid or file is a directory
        """
        # Expand user directory (~)
        expanded_path = Path(file_path).expanduser()

        # Resolve to absolute path
        try:
            if expanded_path.is_absolute():
                resolved_path = expanded_path.resolve()
            else:
                # For relative paths, resolve against current working directory
                resolved_path = Path.cwd() / expanded_path
                resolved_path = resolved_path.resolve()
        except (OSError, RuntimeError) as e:
            # Handle errors from resolve() or cwd()
            raise FileNotFoundError(f"Failed to open file '{file_path}', error: {e}") from e

        # Validate file exists
        if not resolved_path.exists():
            raise FileNotFoundError(f"Failed to open file '{file_path}', error: No such file")

        # Validate it's a file, not a directory
        if not resolved_path.is_file():
            raise ValueError(f"Failed to open file '{file_path}', error: Is a directory")

        # Read file content with encoding fallback
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = resolved_path.read_text(encoding="latin-1")
            except Exception as e:
                raise ValueError(f"Failed to read file '{file_path}': {e}") from e
        except PermissionError as e:
            raise PermissionError(f"Failed to open file '{file_path}', error: Permission denied") from e
        except Exception as e:
            raise ValueError(f"Failed to read file '{file_path}': {e}") from e

        return content, resolved_path

    def _split_sql_statements(self, content: str, delimiter: str = ";") -> list[str]:
        """Split SQL content into individual statements.

        Handles:
        - Standard delimiter (;)
        - Custom delimiters (for stored procedures)
        - DELIMITER commands within the script
        - Comments (-- and #)
        - Multi-line statements

        Args:
            content: SQL script content
            delimiter: Statement delimiter (default: ;)

        Returns:
            List of SQL statements
        """
        statements: list[str] = []
        current: list[str] = []
        current_delimiter = delimiter
        in_string: str | None = None

        lines = content.split("\n")

        for line in lines:
            stripped = line.strip()

            # Skip empty lines and comments at line level
            if not stripped:
                if current:
                    current.append(line)
                continue

            if stripped.startswith("--") or stripped.startswith("#"):
                continue

            # Handle DELIMITER command
            if stripped.upper().startswith("DELIMITER"):
                # Flush current statement if any
                if current:
                    stmt = "\n".join(current).strip()
                    if stmt and not stmt.upper().startswith("DELIMITER"):
                        statements.append(stmt)
                    current = []

                # Extract new delimiter
                parts = stripped.split(maxsplit=1)
                if len(parts) > 1:
                    current_delimiter = parts[1].strip()
                continue

            # Add line to current statement
            current.append(line)

            # Check if line ends with delimiter (simple check)
            # Note: This is simplified and doesn't handle delimiters inside strings
            if stripped.endswith(current_delimiter):
                stmt = "\n".join(current)
                # Remove the delimiter
                if stmt.rstrip().endswith(current_delimiter):
                    stmt = stmt.rstrip()[: -len(current_delimiter)].strip()
                if stmt:
                    statements.append(stmt)
                current = []

        # Handle last statement without delimiter
        if current:
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)

        return statements

    def _execute_script(
        self, content: str, filename: str, display_callback: Callable[[QueryResult, str, bool], None] | None = None
    ) -> QueryResult:
        """Execute SQL script content.

        Args:
            content: SQL script content
            filename: Script filename (for display purposes)
            display_callback: Optional callback function to display each statement result.
                            Called as display_callback(result, sql, use_vertical)

        Returns:
            QueryResult with execution summary
        """
        start_time = datetime.now()

        # Split into statements
        statements = self._split_sql_statements(content)

        if not statements:
            logger.debug(f"No statements found in {filename}")
            execution_time = (datetime.now() - start_time).total_seconds()
            return QueryResult(
                query_type=QueryType.SOURCE,
                success=True,
                rows=[],
                execution_time=execution_time,
                error="No statements found in script",
            )

        logger.info(f"Executing {len(statements)} statement(s) from {filename}")

        success_count = 0
        error_count = 0
        total_affected_rows = 0
        errors: list[str] = []

        for i, stmt in enumerate(statements, 1):
            stmt = stmt.strip()
            if not stmt:
                continue

            try:
                result = self.execute_query(stmt)

                # Display result immediately if callback is provided
                # This matches MySQL behavior: each statement shows its result immediately
                if display_callback:
                    use_vertical = self.has_vertical_format_directive(stmt)
                    display_callback(result, stmt, use_vertical)

                if result.success:
                    success_count += 1
                    if result.affected_rows is not None and result.affected_rows >= 0:
                        total_affected_rows += result.affected_rows
                    logger.debug(f"Statement {i}/{len(statements)} executed successfully")
                else:
                    error_count += 1
                    error_msg = f"Statement {i}/{len(statements)}: {result.error}"
                    errors.append(error_msg)
                    logger.warning(f"Statement {i}/{len(statements)} failed: {result.error}")
            except Exception as e:
                error_count += 1
                error_msg = f"Statement {i}/{len(statements)}: {str(e)}"
                errors.append(error_msg)
                logger.exception(f"Script execution error at statement {i}")

        execution_time = (datetime.now() - start_time).total_seconds()

        # Build error message only if there are errors (no summary for successful execution)
        error_message = None
        if error_count > 0:
            error_details = "\n".join(errors)
            if len(errors) > 10:
                error_details = "\n".join(errors[:10]) + f"\n... and {len(errors) - 10} more error(s)"
            error_message = error_details

        logger.info(
            f"Script execution completed: {success_count} succeeded, {error_count} failed in {execution_time:.2f}s"
        )

        return QueryResult(
            query_type=QueryType.SOURCE,
            success=error_count == 0,
            rows=[],
            affected_rows=total_affected_rows if total_affected_rows > 0 else None,
            execution_time=execution_time,
            error=error_message,
        )

    def _execute_source_command(self, sql: str) -> QueryResult:
        """Execute SOURCE command.

        Args:
            sql: SOURCE command SQL string

        Returns:
            QueryResult with execution summary
        """
        try:
            # Parse file path
            file_path = self._parse_source_path(sql)

            # Read file content
            content, resolved_path = self._read_script_file(file_path)

            # Use registered display callback if available
            # Execute script
            return self._execute_script(content, resolved_path.name, display_callback=self._source_display_callback)

        except FileNotFoundError as e:
            return QueryResult(
                query_type=QueryType.SOURCE,
                success=False,
                rows=[],
                execution_time=0.0,
                error=str(e),
            )
        except (ValueError, PermissionError) as e:
            return QueryResult(
                query_type=QueryType.SOURCE,
                success=False,
                rows=[],
                execution_time=0.0,
                error=str(e),
            )
        except Exception as e:
            logger.exception("Unexpected error executing SOURCE command")
            return QueryResult(
                query_type=QueryType.SOURCE,
                success=False,
                rows=[],
                execution_time=0.0,
                error=f"Unexpected error: {str(e)}",
            )

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
    except ConnectionError as e:
        # Check if connection was cancelled by user
        error_msg = str(e)
        if "cancelled by user" in error_msg.lower():
            error_msg = "Connection cancelled by user"
        return ConnectionContext(
            db_service=db_service,
            query_history=query_history,
            status=ConnectionStatus.FAILED.value,
            display_name=f"{database or 'mysql'}://{host}",
            error=error_msg,
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


def _generate_file_display_name(parsed_urls: list, urls: list[str]) -> str:
    """
    Generate user-friendly display name for file connections.

    Args:
        parsed_urls: List of parsed URL objects
        urls: List of original URL strings

    Returns:
        User-friendly display name
    """
    import os

    if not parsed_urls:
        return "Data source"

    primary_parsed_url = parsed_urls[0]

    # Handle in-memory mode
    if primary_parsed_url.is_memory:
        if len(urls) == 1:
            return "In-memory data source"
        else:
            return f"In-memory data source ({len(urls)} files)"

    # Handle DuckDB database file protocol
    if primary_parsed_url.is_duckdb_protocol:
        db_path = primary_parsed_url.path
        if db_path == ":memory:":
            return "In-memory data source"
        # Extract filename from path
        filename = os.path.basename(db_path)
        if filename:
            return f"Database: {filename}"
        return f"Database: {db_path}"

    # Handle file/http/https protocols
    if len(urls) == 1:
        # Single file
        if primary_parsed_url.is_file_protocol:
            # Extract filename from path
            file_path = primary_parsed_url.path
            filename = os.path.basename(file_path)
            if filename:
                return f"File: {filename}"
            return f"File: {file_path}"
        elif primary_parsed_url.is_http_protocol:
            # HTTP/HTTPS URL - show domain or full URL
            url_str = primary_parsed_url.original_url
            try:
                from urllib.parse import urlparse

                parsed = urlparse(url_str)
                domain = parsed.netloc
                if domain:
                    return f"Remote: {domain}"
            except Exception:
                pass
            return f"Remote: {url_str}"
        else:
            # Fallback
            return f"Data source: {primary_parsed_url.original_url}"
    else:
        # Multiple files
        file_count = len([p for p in parsed_urls if p.is_file_protocol or p.is_http_protocol])
        if file_count == len(urls):
            # All are files
            if file_count <= 3:
                # Show file names
                filenames = []
                for parsed_url in parsed_urls:
                    if parsed_url.is_file_protocol:
                        filename = os.path.basename(parsed_url.path)
                        filenames.append(filename)
                    elif parsed_url.is_http_protocol:
                        try:
                            from urllib.parse import urlparse

                            parsed = urlparse(parsed_url.original_url)
                            filename = os.path.basename(parsed.path) or parsed.netloc
                            filenames.append(filename)
                        except Exception:
                            filenames.append("file")
                if filenames:
                    return f"Files: {', '.join(filenames)}"
            return f"{file_count} files"
        else:
            return f"{len(urls)} data sources"


def create_duckdb_connection_context(url: str | list[str]) -> ConnectionContext:
    """Create a DuckDB connection context from URL(s).

    Args:
        url: DuckDB connection URL(s) - can be a single URL string or a list of URLs
            (e.g., "file:///path/to/file.csv", ["file1.csv", "file2.csv"])

    Returns:
        ConnectionContext with connection status
    """
    from .duckdb_loader import DuckDBURLParser, FileLoadError, UnsupportedFileFormatError, ParsedDuckDBURL
    from .duckdb_client import DuckDBClient

    db_service = DatabaseService()
    query_history = QueryHistory(max_entries=100)

    # Normalize input to list
    urls: list[str] = [url] if isinstance(url, str) else url

    try:
        # Parse all URLs
        parsed_urls: list[ParsedDuckDBURL] = []
        for url_str in urls:
            parsed_url = DuckDBURLParser.parse(url_str)
            parsed_urls.append(parsed_url)

        # Use first URL for connection setup (all should use same DuckDB instance)
        primary_parsed_url = parsed_urls[0]

        # Create DuckDB client (use in-memory mode for file/http/https protocols)
        client = DuckDBClient(parsed_url=primary_parsed_url)

        # Create connection config for display purposes
        # DuckDB doesn't require user/password, but ConnectionConfig needs a user for non-duckdb engines
        # We set a placeholder user for duckdb to satisfy the config structure
        connection_config = ConnectionConfig(
            engine="duckdb",
            port=None,
            password=None,
            database=None,
        )

        with db_service._lock:
            db_service._active_connection = client
            db_service._connection_config = connection_config
            # Use first URL for connection ID
            db_service._connection_id = f"duckdb_{primary_parsed_url.url}"

        # Load files if they are file/http/https protocols
        load_info = None
        file_urls = [p for p in parsed_urls if p.is_file_protocol or p.is_http_protocol]

        if file_urls:
            try:
                if len(file_urls) == 1:
                    # Single file
                    table_name, row_count, column_count, _ = client.load_file()
                    load_info = [(table_name, row_count, column_count)]
                else:
                    # Multiple files
                    results = client.load_files(file_urls)
                    load_info = [(r[0], r[1], r[2]) for r in results]
            except (FileLoadError, UnsupportedFileFormatError) as e:
                # Close connection if file loading fails
                client.close()
                raise

        # Set display name using user-friendly format
        display_name = _generate_file_display_name(parsed_urls, urls)

        set_service(db_service)

        context = ConnectionContext(
            db_service=db_service,
            query_history=query_history,
            status=ConnectionStatus.CONNECTED.value,
            display_name=display_name,
        )
        # Store load info in db_service for later retrieval
        if load_info:
            db_service._duckdb_load_info = load_info
        return context

    except Exception as e:
        error_msg = str(e)
        try:
            parsed_urls_for_error = []
            for url_str in urls:
                parsed_url = DuckDBURLParser.parse(url_str)
                parsed_urls_for_error.append(parsed_url)
            display_name = _generate_file_display_name(parsed_urls_for_error, urls)
        except Exception:
            # Fallback display name
            if len(urls) == 1:
                # Try to extract filename
                try:
                    import os

                    filename = os.path.basename(urls[0])
                    if filename:
                        display_name = f"File: {filename}"
                    else:
                        display_name = f"Data source: {urls[0]}"
                except Exception:
                    display_name = f"Data source: {urls[0]}"
            else:
                display_name = f"{len(urls)} data sources"

        return ConnectionContext(
            db_service=db_service,
            query_history=query_history,
            status=ConnectionStatus.FAILED.value,
            display_name=display_name,
            error=error_msg,
        )
