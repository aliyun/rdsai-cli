"""DuckDB database client implementation."""

from __future__ import annotations

import duckdb
from typing import Any

from .client import DatabaseClient, TransactionState, validate_identifier
from .duckdb_loader import DuckDBURLParser, ParsedDuckDBURL, DuckDBFileLoader, FileLoadError


class DuckDBClient(DatabaseClient):
    """DuckDB database client implementation."""

    def __init__(
        self,
        url: str | None = None,
        database: str | None = None,
        parsed_url: ParsedDuckDBURL | None = None,
        **kwargs: Any,
    ):
        """
        Initialize DuckDB client.

        Args:
            url: DuckDB connection URL (e.g., "duckdb:///path/to/db.duckdb")
            database: Database file path or ":memory:" for in-memory mode
            parsed_url: Pre-parsed URL information (optional)
            **kwargs: Additional connection parameters
        """
        # Parse URL if provided
        if parsed_url:
            self.parsed_url = parsed_url
        elif url:
            self.parsed_url = DuckDBURLParser.parse(url)
        else:
            # Default to in-memory mode
            self.parsed_url = ParsedDuckDBURL(
                protocol=DuckDBURLParser.SUPPORTED_PROTOCOLS["duckdb"],
                path=":memory:",
                is_memory=True,
            )

        # Determine database path
        if database is not None:
            # Explicit database parameter takes precedence
            if database == ":memory:":
                db_path = ":memory:"
            else:
                db_path = database
        elif self.parsed_url.is_duckdb_protocol:
            # Use path from parsed URL
            db_path = self.parsed_url.path
        else:
            # For file/http/https protocols, use in-memory mode
            db_path = ":memory:"

        # Create DuckDB connection
        if db_path == ":memory:":
            self.conn = duckdb.connect(":memory:")
        else:
            self.conn = duckdb.connect(db_path)

        self.cursor = self.conn.cursor()
        # DuckDB doesn't support transactions, always in NOT_IN_TRANSACTION state
        self._transaction_state = TransactionState.NOT_IN_TRANSACTION
        self._autocommit = True
        self._last_result: Any = None
        self._last_columns: list[str] | None = None
        self._last_rowcount: int = 0

    def execute(self, sql: str) -> Any:
        """Execute a SQL statement."""
        try:
            result = self.cursor.execute(sql)
            self._last_result = result

            # Try to get column names
            try:
                description = result.description
                if description:
                    self._last_columns = [col[0] for col in description]
                else:
                    self._last_columns = None
            except Exception:
                self._last_columns = None

            # Reset row count (will be set when fetchall/fetchone is called)
            # For non-SELECT queries, DuckDB doesn't provide rowcount until after execution
            self._last_rowcount = 0

            return result
        except Exception as e:
            # DuckDB doesn't have transactions, but we keep the state for compatibility
            # Don't change transaction state on error
            raise

    def fetchall(self) -> list[Any]:
        """Fetch all rows from the last query."""
        if self._last_result is None:
            return []
        try:
            rows = self._last_result.fetchall()
            self._last_rowcount = len(rows)
            return rows
        except Exception:
            return []

    def fetchone(self) -> Any | None:
        """Fetch one row from the last query."""
        if self._last_result is None:
            return None
        try:
            return self._last_result.fetchone()
        except Exception:
            return None

    def close(self) -> None:
        """Close the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def change_database(self, database: str) -> None:
        """Change to the specified database.

        Note: DuckDB doesn't have a USE DATABASE command like MySQL.
        This method is a no-op for DuckDB.
        """
        # DuckDB doesn't support changing databases like MySQL
        # Each connection is tied to a specific database file or memory
        pass

    @classmethod
    def engine_name(cls) -> str:
        """Return the engine name."""
        return "duckdb"

    def get_transaction_state(self) -> TransactionState:
        """Get current transaction state.
        
        Note: DuckDB doesn't have transaction support, always returns NOT_IN_TRANSACTION.
        """
        return TransactionState.NOT_IN_TRANSACTION

    def begin_transaction(self) -> None:
        """Begin a new transaction.
        
        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
        # DuckDB doesn't support transactions, do nothing
        pass

    def commit_transaction(self) -> None:
        """Commit the current transaction.
        
        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
        # DuckDB doesn't support transactions, do nothing
        pass

    def rollback_transaction(self) -> None:
        """Rollback the current transaction.
        
        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
        # DuckDB doesn't support transactions, do nothing
        pass

    def set_autocommit(self, enabled: bool) -> None:
        """Set autocommit mode.
        
        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
        # DuckDB doesn't support transactions/autocommit, do nothing
        # But we track the state for compatibility
        self._autocommit = enabled

    def get_autocommit(self) -> bool:
        """Get current autocommit mode.
        
        Note: DuckDB doesn't have transaction support, always returns True.
        """
        return True

    def ping(self, reconnect: bool = False) -> bool:
        """Check if the connection is alive."""
        try:
            self.cursor.execute("SELECT 1")
            return True
        except Exception:
            if reconnect:
                # Try to reconnect (for DuckDB, this means creating a new connection)
                try:
                    if self.parsed_url.is_memory:
                        self.conn = duckdb.connect(":memory:")
                    else:
                        self.conn = duckdb.connect(self.parsed_url.path)
                    self.cursor = self.conn.cursor()
                    return True
                except Exception:
                    return False
            return False

    def get_columns(self) -> list[str] | None:
        """Get column names from the last query result."""
        return self._last_columns

    def get_row_count(self) -> int:
        """Get the number of affected/returned rows from the last operation."""
        # If we haven't fetched rows yet, try to get rowcount from cursor
        if self._last_rowcount == 0 and self._last_result is not None:
            try:
                # For non-SELECT queries, DuckDB may provide rowcount
                rowcount = getattr(self._last_result, "rowcount", None)
                if rowcount is not None and rowcount >= 0:
                    self._last_rowcount = rowcount
            except Exception:
                pass
        return self._last_rowcount

    def load_file(self, table_name: str | None = None) -> tuple[str, int, int]:
        """
        Load file into DuckDB table (for file://, http://, https:// protocols).

        Args:
            table_name: Optional table name (if None, inferred from URL)

        Returns:
            Tuple of (table_name, row_count, column_count)

        Raises:
            FileLoadError: If file loading fails
        """
        if not (self.parsed_url.is_file_protocol or self.parsed_url.is_http_protocol):
            raise FileLoadError(
                f"Cannot load file for protocol: {self.parsed_url.protocol}. "
                "File loading is only supported for file://, http://, and https:// protocols."
            )

        return DuckDBFileLoader.load_file(self.conn, self.parsed_url, table_name)
