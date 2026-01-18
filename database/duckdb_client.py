"""DuckDB database client implementation."""

from __future__ import annotations

import os
import duckdb
from typing import Any

from .client import DatabaseClient, TransactionState
from .duckdb_loader import DuckDBURLParser, ParsedDuckDBURL, DuckDBFileLoader, FileLoadError
from utils.logging import logger


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
            db_path = ":memory:" if database == ":memory:" else database
        elif self.parsed_url.is_duckdb_protocol:
            db_path = self.parsed_url.path
        else:
            # For file/http/https protocols, use in-memory mode
            db_path = ":memory:"

        # Create DuckDB connection
        self.conn = duckdb.connect(db_path)
        self.cursor = self.conn.cursor()
        # DuckDB doesn't support transactions, always in NOT_IN_TRANSACTION state
        self._transaction_state = TransactionState.NOT_IN_TRANSACTION
        self._autocommit = True
        self._last_result: Any = None
        self._last_columns: list[str] | None = None
        self._last_rowcount: int = 0
        self._persistent_db_path: str | None = None

    def execute(self, sql: str) -> Any:
        """Execute a SQL statement."""
        result = self.cursor.execute(sql)
        self._last_result = result

        # Try to get column names
        try:
            description = result.description
            self._last_columns = [col[0] for col in description] if description else None
        except Exception:
            self._last_columns = None

        # Reset row count (will be set when fetchall/fetchone is called)
        # For non-SELECT queries, DuckDB doesn't provide rowcount until after execution
        self._last_rowcount = 0

        return result

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

        # Clean up temporary database file if it was created for large files
        if self._persistent_db_path and os.path.exists(self._persistent_db_path):
            try:
                os.remove(self._persistent_db_path)
                logger.debug(f"Cleaned up temporary database file: {self._persistent_db_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary database file {self._persistent_db_path}: {e}")

    def change_database(self, database: str) -> None:
        """Change to the specified database.

        Note: DuckDB doesn't have a USE DATABASE command like MySQL.
        This method is a no-op for DuckDB.
        """
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
        pass

    def commit_transaction(self) -> None:
        """Commit the current transaction.

        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
        pass

    def rollback_transaction(self) -> None:
        """Rollback the current transaction.

        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
        pass

    def set_autocommit(self, enabled: bool) -> None:
        """Set autocommit mode.

        Note: DuckDB doesn't have transaction support, this is a no-op.
        """
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
                return self._reconnect()
            return False

    def _reconnect(self) -> bool:
        """Reconnect to the database."""
        try:
            if self.parsed_url.is_memory:
                self.conn = duckdb.connect(":memory:")
            else:
                self.conn = duckdb.connect(self.parsed_url.path)
            self.cursor = self.conn.cursor()
            return True
        except Exception:
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

    def load_file(self, table_name: str | None = None) -> tuple[str, int, int, str | None]:
        """
        Load file into DuckDB table (for file://, http://, https:// protocols).

        Args:
            table_name: Optional table name (if None, inferred from URL)

        Returns:
            Tuple of (table_name, row_count, column_count, persistent_db_path)
            persistent_db_path is None for small files, path string for large files

        Raises:
            FileLoadError: If file loading fails
        """
        if not (self.parsed_url.is_file_protocol or self.parsed_url.is_http_protocol):
            raise FileLoadError(
                f"Cannot load file for protocol: {self.parsed_url.protocol}. "
                "File loading is only supported for file://, http://, and https:// protocols."
            )

        result = DuckDBFileLoader.load_file(self.conn, self.parsed_url, table_name)
        table_name_result, row_count, column_count, persistent_db_path = result

        # If persistent database was created, switch connection
        if persistent_db_path:
            self._switch_to_persistent_db(persistent_db_path)

        return result

    def load_files(self, parsed_urls: list) -> list[tuple[str, int, int, str | None]]:
        """
        Load multiple files into DuckDB tables (for file://, http://, https:// protocols).

        Args:
            parsed_urls: List of ParsedDuckDBURL objects

        Returns:
            List of tuples (table_name, row_count, column_count, persistent_db_path)
            for each successfully loaded file

        Raises:
            FileLoadError: If file loading fails
        """
        # Validate all URLs are file/http/https protocols
        for parsed_url in parsed_urls:
            if not (parsed_url.is_file_protocol or parsed_url.is_http_protocol):
                raise FileLoadError(
                    f"Cannot load file for protocol: {parsed_url.protocol}. "
                    "File loading is only supported for file://, http://, and https:// protocols."
                )

        results = DuckDBFileLoader.load_files(self.conn, parsed_urls)

        # Check if any file used persistent database
        persistent_db_path = None
        for result in results:
            if result[3] is not None:
                persistent_db_path = result[3]
                break

        # If persistent database was created, switch connection
        if persistent_db_path:
            self._switch_to_persistent_db(persistent_db_path)

        return results

    def _switch_to_persistent_db(self, persistent_db_path: str) -> None:
        """Switch connection to a persistent database file."""
        if self.conn:
            self.conn.close()
        self.conn = duckdb.connect(persistent_db_path)
        self.cursor = self.conn.cursor()
        self.parsed_url.path = persistent_db_path
        self._persistent_db_path = persistent_db_path
