"""Tests for database.duckdb_client module."""

import pytest
from unittest.mock import MagicMock, patch

from database.duckdb_client import DuckDBClient
from database.duckdb_loader import (
    ParsedDuckDBURL,
    DuckDBProtocol,
    FileLoadError,
)
from database.client import TransactionState


class TestDuckDBClient:
    """Tests for DuckDBClient class."""

    def test_init_with_url(self):
        """Test DuckDBClient initialization with URL."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient(url="duckdb:///path/to/db.duckdb")

            assert client.parsed_url.protocol == DuckDBProtocol.DUCKDB
            assert client.parsed_url.path == "/path/to/db.duckdb"
            mock_connect.assert_called_once_with("/path/to/db.duckdb")

    def test_init_with_memory_url(self):
        """Test DuckDBClient initialization with in-memory URL."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient(url="duckdb://:memory:")

            assert client.parsed_url.is_memory is True
            mock_connect.assert_called_once_with(":memory:")

    def test_init_with_database_parameter(self):
        """Test DuckDBClient initialization with database parameter."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient(database="/path/to/db.duckdb")

            mock_connect.assert_called_once_with("/path/to/db.duckdb")

    def test_init_with_memory_database(self):
        """Test DuckDBClient initialization with :memory: database."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient(database=":memory:")

            mock_connect.assert_called_once_with(":memory:")

    def test_init_with_parsed_url(self):
        """Test DuckDBClient initialization with parsed URL."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            parsed_url = ParsedDuckDBURL(
                protocol=DuckDBProtocol.DUCKDB,
                path="/path/to/db.duckdb",
                is_memory=False,
            )
            client = DuckDBClient(parsed_url=parsed_url)

            assert client.parsed_url == parsed_url
            mock_connect.assert_called_once_with("/path/to/db.duckdb")

    def test_init_default_memory(self):
        """Test DuckDBClient initialization with no parameters (defaults to memory)."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()

            assert client.parsed_url.is_memory is True
            mock_connect.assert_called_once_with(":memory:")

    def test_init_with_file_protocol(self):
        """Test DuckDBClient initialization with file:// protocol."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient(url="file:///path/to/file.csv")

            # File protocol should use in-memory mode
            mock_connect.assert_called_once_with(":memory:")

    def test_engine_name(self):
        """Test engine_name class method."""
        assert DuckDBClient.engine_name() == "duckdb"

    def test_execute(self):
        """Test execute method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.description = [("col1",), ("col2",)]
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            result = client.execute("SELECT 1")

            assert result == mock_result
            mock_cursor.execute.assert_called_once_with("SELECT 1")
            assert client._last_result == mock_result
            assert client._last_columns == ["col1", "col2"]

    def test_execute_no_description(self):
        """Test execute method when result has no description."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.description = None
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.execute("INSERT INTO table VALUES (1)")

            assert client._last_columns is None

    def test_fetchall(self):
        """Test fetchall method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [("row1",), ("row2",)]
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.execute("SELECT 1")
            result = client.fetchall()

            assert result == [("row1",), ("row2",)]
            assert client._last_rowcount == 2

    def test_fetchall_no_result(self):
        """Test fetchall method when no result available."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            result = client.fetchall()

            assert result == []

    def test_fetchone(self):
        """Test fetchone method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = ("row1",)
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.execute("SELECT 1")
            result = client.fetchone()

            assert result == ("row1",)

    def test_fetchone_no_result(self):
        """Test fetchone method when no result available."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            result = client.fetchone()

            assert result is None

    def test_close(self):
        """Test close method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.close()

            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_change_database(self):
        """Test change_database method (no-op for DuckDB)."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            # Should not raise an error
            client.change_database("new_db")

    def test_get_transaction_state(self):
        """Test get_transaction_state method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            assert client.get_transaction_state() == TransactionState.NOT_IN_TRANSACTION

    def test_begin_transaction(self):
        """Test begin_transaction method (no-op for DuckDB)."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            # Should not raise an error
            client.begin_transaction()

    def test_commit_transaction(self):
        """Test commit_transaction method (no-op for DuckDB)."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            # Should not raise an error
            client.commit_transaction()

    def test_rollback_transaction(self):
        """Test rollback_transaction method (no-op for DuckDB)."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            # Should not raise an error
            client.rollback_transaction()

    def test_set_autocommit(self):
        """Test set_autocommit method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.set_autocommit(False)
            assert client._autocommit is False

    def test_get_autocommit(self):
        """Test get_autocommit method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            # DuckDB always returns True
            assert client.get_autocommit() is True

    def test_ping_success(self):
        """Test ping method when connection is alive."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            assert client.ping() is True

    def test_ping_failure(self):
        """Test ping method when connection fails."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("Connection lost")
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            assert client.ping() is False

    def test_ping_reconnect(self):
        """Test ping method with reconnect option."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = [Exception("Connection lost"), None]
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.parsed_url = ParsedDuckDBURL(
                protocol=DuckDBProtocol.DUCKDB,
                path=":memory:",
                is_memory=True,
            )
            assert client.ping(reconnect=True) is True
            assert mock_connect.call_count == 2

    def test_get_columns(self):
        """Test get_columns method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.description = [("col1",), ("col2",)]
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.execute("SELECT col1, col2 FROM table")
            columns = client.get_columns()

            assert columns == ["col1", "col2"]

    def test_get_row_count(self):
        """Test get_row_count method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [("row1",), ("row2",), ("row3",)]
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.execute("SELECT * FROM table")
            client.fetchall()
            row_count = client.get_row_count()

            assert row_count == 3

    def test_get_row_count_from_cursor(self):
        """Test get_row_count method when getting from cursor."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_result = MagicMock()
            mock_result.rowcount = 5
            mock_cursor.execute.return_value = mock_result
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            client = DuckDBClient()
            client.execute("INSERT INTO table VALUES (1)")
            row_count = client.get_row_count()

            assert row_count == 5

    @patch("database.duckdb_client.DuckDBFileLoader")
    def test_load_file(self, mock_loader):
        """Test load_file method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            mock_loader.load_file.return_value = ("table1", 10, 3, None)

            parsed_url = ParsedDuckDBURL(
                protocol=DuckDBProtocol.FILE,
                path="/path/to/file.csv",
                is_memory=False,
            )
            client = DuckDBClient(parsed_url=parsed_url)
            result = client.load_file()

            assert result == ("table1", 10, 3, None)
            mock_loader.load_file.assert_called_once_with(mock_conn, parsed_url, None)

    @patch("database.duckdb_client.DuckDBFileLoader")
    def test_load_file_with_table_name(self, mock_loader):
        """Test load_file method with table name."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            mock_loader.load_file.return_value = ("custom_table", 5, 2, None)

            parsed_url = ParsedDuckDBURL(
                protocol=DuckDBProtocol.FILE,
                path="/path/to/file.csv",
                is_memory=False,
            )
            client = DuckDBClient(parsed_url=parsed_url)
            result = client.load_file(table_name="custom_table")

            assert result == ("custom_table", 5, 2, None)
            mock_loader.load_file.assert_called_once_with(mock_conn, parsed_url, "custom_table")

    def test_load_file_invalid_protocol(self):
        """Test load_file method with invalid protocol."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            parsed_url = ParsedDuckDBURL(
                protocol=DuckDBProtocol.DUCKDB,
                path="/path/to/db.duckdb",
                is_memory=False,
            )
            client = DuckDBClient(parsed_url=parsed_url)

            with pytest.raises(FileLoadError, match="Cannot load file for protocol"):
                client.load_file()

    @patch("database.duckdb_client.DuckDBFileLoader")
    def test_load_files(self, mock_loader):
        """Test load_files method."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            mock_loader.load_files.return_value = [
                ("table1", 10, 3, None),
                ("table2", 20, 4, None),
            ]

            parsed_urls = [
                ParsedDuckDBURL(
                    protocol=DuckDBProtocol.FILE,
                    path="/path/to/file1.csv",
                    is_memory=False,
                ),
                ParsedDuckDBURL(
                    protocol=DuckDBProtocol.FILE,
                    path="/path/to/file2.csv",
                    is_memory=False,
                ),
            ]
            client = DuckDBClient()
            result = client.load_files(parsed_urls)

            assert result == [("table1", 10, 3, None), ("table2", 20, 4, None)]
            mock_loader.load_files.assert_called_once_with(mock_conn, parsed_urls)

    def test_load_files_invalid_protocol(self):
        """Test load_files method with invalid protocol."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            parsed_urls = [
                ParsedDuckDBURL(
                    protocol=DuckDBProtocol.DUCKDB,
                    path="/path/to/db.duckdb",
                    is_memory=False,
                ),
            ]
            client = DuckDBClient()

            with pytest.raises(FileLoadError, match="Cannot load file for protocol"):
                client.load_files(parsed_urls)

    def test_load_files_mixed_protocols(self):
        """Test load_files method with mixed valid and invalid protocols."""
        with patch("database.duckdb_client.duckdb.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            parsed_urls = [
                ParsedDuckDBURL(
                    protocol=DuckDBProtocol.FILE,
                    path="/path/to/file.csv",
                    is_memory=False,
                ),
                ParsedDuckDBURL(
                    protocol=DuckDBProtocol.DUCKDB,
                    path="/path/to/db.duckdb",
                    is_memory=False,
                ),
            ]
            client = DuckDBClient()

            with pytest.raises(FileLoadError, match="Cannot load file for protocol"):
                client.load_files(parsed_urls)
