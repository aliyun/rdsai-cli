"""Tests for database.service module."""

import pytest
from unittest.mock import MagicMock, patch

from database.service import (
    DatabaseService,
    extract_single_column,
    extract_first_value,
    format_query_context_for_agent,
    create_connection_context,
    create_database_service,
    create_duckdb_connection_context,
    get_service,
    set_service,
    clear_service,
    get_database_client,
    get_current_database,
)
from database.types import (
    ConnectionConfig,
    QueryType,
    QueryStatus,
    LastQueryContext,
    ConnectionStatus,
)
from database.client import TransactionState
from database.errors import DatabaseError, ConnectionError


class TestExtractSingleColumn:
    """Tests for extract_single_column function."""

    def test_extract_from_tuples(self):
        """Test extracting from list of tuples."""
        rows = [("value1",), ("value2",), ("value3",)]
        result = extract_single_column(rows)
        assert result == ["value1", "value2", "value3"]

    def test_extract_from_lists(self):
        """Test extracting from list of lists."""
        rows = [["value1"], ["value2"], ["value3"]]
        result = extract_single_column(rows)
        assert result == ["value1", "value2", "value3"]

    def test_extract_from_single_values(self):
        """Test extracting from single values."""
        rows = ["value1", "value2", "value3"]
        result = extract_single_column(rows)
        assert result == ["value1", "value2", "value3"]

    def test_extract_empty_list(self):
        """Test extracting from empty list."""
        result = extract_single_column([])
        assert result == []


class TestExtractFirstValue:
    """Tests for extract_first_value function."""

    def test_extract_from_tuple(self):
        """Test extracting from tuple."""
        assert extract_first_value(("value1", "value2")) == "value1"

    def test_extract_from_list(self):
        """Test extracting from list."""
        assert extract_first_value(["value1", "value2"]) == "value1"

    def test_extract_from_single_value(self):
        """Test extracting from single value."""
        assert extract_first_value("value1") == "value1"

    def test_extract_none(self):
        """Test extracting from None."""
        assert extract_first_value(None) is None

    def test_extract_from_empty_list(self):
        """Test extracting from empty list."""
        assert extract_first_value([]) is None


class TestFormatQueryContextForAgent:
    """Tests for format_query_context_for_agent function."""

    def test_format_successful_query_with_data(self):
        """Test formatting successful query with data."""
        context = LastQueryContext(
            sql="SELECT * FROM users",
            status=QueryStatus.SUCCESS,
            columns=["id", "name"],
            rows=[(1, "Alice"), (2, "Bob")],
            row_count=2,
            affected_rows=None,
            execution_time=0.123,
        )
        result = format_query_context_for_agent(context)
        assert "SELECT * FROM users" in result
        assert "success" in result
        assert "0.123" in result
        assert "id" in result
        assert "name" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_format_error_query(self):
        """Test formatting error query."""
        context = LastQueryContext(
            sql="SELECT * FROM invalid_table",
            status=QueryStatus.ERROR,
            error_message="Table doesn't exist",
            execution_time=0.045,
        )
        result = format_query_context_for_agent(context)
        assert "SELECT * FROM invalid_table" in result
        assert "error" in result
        assert "Table doesn't exist" in result

    def test_format_empty_result(self):
        """Test formatting query with empty result."""
        context = LastQueryContext(
            sql="SELECT * FROM empty_table",
            status=QueryStatus.SUCCESS,
            columns=["id"],
            rows=[],
            row_count=0,
            execution_time=0.01,
        )
        result = format_query_context_for_agent(context)
        assert "Empty (0 rows)" in result

    def test_format_truncated_result(self):
        """Test formatting query with truncated result."""
        rows = [(i,) for i in range(100)]
        context = LastQueryContext(
            sql="SELECT * FROM large_table",
            status=QueryStatus.SUCCESS,
            columns=["id"],
            rows=rows,
            row_count=100,
            execution_time=0.5,
        )
        result = format_query_context_for_agent(context, max_display_rows=50)
        assert "more rows not shown" in result


class TestDatabaseService:
    """Tests for DatabaseService class."""

    def test_init(self):
        """Test DatabaseService initialization."""
        service = DatabaseService()
        assert service._active_connection is None
        assert service._connection_config is None
        assert service._current_database is None
        assert service._last_query_context is None
        assert not service.is_connected()

    def test_is_connected_false(self):
        """Test is_connected when not connected."""
        service = DatabaseService()
        assert not service.is_connected()

    def test_is_connected_true(self):
        """Test is_connected when connected."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client
        assert service.is_connected()

    @patch("database.service.DatabaseClientFactory")
    @patch("database.service.getpass.getpass")
    def test_connect_success(self, mock_getpass, mock_factory):
        """Test successful connection."""
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchone.return_value = ("test_db",)
        mock_factory.create.return_value = mock_client

        service = DatabaseService()
        config = ConnectionConfig(
            engine="mysql",
            host="localhost",
            port=3306,
            user="test_user",
            password="test_pass",
            database="test_db",
        )

        connection_id = service.connect(config)

        assert service.is_connected()
        assert service._current_database == "test_db"
        assert connection_id is not None
        mock_factory.create.assert_called_once()

    @patch("database.service.DatabaseClientFactory")
    @patch("database.service.getpass.getpass")
    def test_connect_without_database(self, mock_getpass, mock_factory):
        """Test connection without database specified."""
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchone.return_value = (None,)
        mock_factory.create.return_value = mock_client

        service = DatabaseService()
        config = ConnectionConfig(
            engine="mysql",
            host="localhost",
            port=3306,
            user="test_user",
            password="test_pass",
        )

        service.connect(config)
        assert service._current_database is None

    @patch("database.service.DatabaseClientFactory")
    def test_connect_failure(self, mock_factory):
        """Test connection failure."""
        mock_factory.create.side_effect = Exception("Connection failed")

        service = DatabaseService()
        config = ConnectionConfig(
            engine="mysql",
            host="localhost",
            port=3306,
            user="test_user",
            password="test_pass",
        )

        with pytest.raises(ConnectionError):
            service.connect(config)

    def test_disconnect(self):
        """Test disconnection."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client
        service._connection_config = ConnectionConfig(engine="mysql", host="localhost", port=3306, user="test")
        service._current_database = "test_db"

        service.disconnect()

        assert not service.is_connected()
        assert service._active_connection is None
        assert service._connection_config is None
        assert service._current_database is None
        mock_client.close.assert_called_once()

    def test_reconnect(self):
        """Test reconnection."""
        service = DatabaseService()
        config = ConnectionConfig(engine="mysql", host="localhost", port=3306, user="test", password="pass")
        service._connection_config = config

        with patch.object(service, "connect") as mock_connect:
            mock_connect.return_value = "connection_id"
            result = service.reconnect()
            mock_connect.assert_called_once_with(config)
            assert result == "connection_id"

    def test_reconnect_no_config(self):
        """Test reconnection without previous config raises ValueError."""
        service = DatabaseService()
        with pytest.raises(ValueError, match="No previous connection configuration"):
            service.reconnect()

    def test_get_active_connection(self):
        """Test getting active connection."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client
        assert service.get_active_connection() == mock_client

    def test_get_active_connection_none(self):
        """Test getting active connection when not connected."""
        service = DatabaseService()
        assert service.get_active_connection() is None

    def test_get_client_or_raise(self):
        """Test _get_client_or_raise when connected."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client
        assert service._get_client_or_raise() == mock_client

    def test_get_client_or_raise_not_connected(self):
        """Test _get_client_or_raise when not connected raises error."""
        service = DatabaseService()
        with pytest.raises(DatabaseError, match="No active database connection"):
            service._get_client_or_raise()

    def test_get_connection_info_not_connected(self):
        """Test get_connection_info when not connected."""
        service = DatabaseService()
        info = service.get_connection_info()
        assert info == {"connected": False}

    def test_get_connection_info_connected(self):
        """Test get_connection_info when connected."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.get_transaction_state.return_value = TransactionState.NOT_IN_TRANSACTION
        mock_client.get_autocommit.return_value = True
        service._active_connection = mock_client
        service._connection_config = ConnectionConfig(
            engine="mysql",
            host="localhost",
            port=3306,
            user="test_user",
            database="test_db",
        )
        service._connection_id = "test_id"
        service._current_database = "test_db"

        info = service.get_connection_info()
        assert info["connected"] is True
        assert info["connection_id"] == "test_id"
        assert info["engine"] == "mysql"
        assert info["host"] == "localhost"
        assert info["port"] == 3306
        assert info["user"] == "test_user"
        assert info["database"] == "test_db"

    def test_classify_query_select(self):
        """Test query classification for SELECT."""
        service = DatabaseService()
        assert service._classify_query("SELECT * FROM users") == QueryType.SELECT

    def test_classify_query_insert(self):
        """Test query classification for INSERT."""
        service = DatabaseService()
        assert service._classify_query("INSERT INTO users VALUES (1)") == QueryType.INSERT

    def test_classify_query_update(self):
        """Test query classification for UPDATE."""
        service = DatabaseService()
        assert service._classify_query("UPDATE users SET name='test'") == QueryType.UPDATE

    def test_classify_query_delete(self):
        """Test query classification for DELETE."""
        service = DatabaseService()
        assert service._classify_query("DELETE FROM users") == QueryType.DELETE

    def test_classify_query_show(self):
        """Test query classification for SHOW."""
        service = DatabaseService()
        assert service._classify_query("SHOW TABLES") == QueryType.SHOW

    def test_classify_query_use(self):
        """Test query classification for USE."""
        service = DatabaseService()
        assert service._classify_query("USE test_db") == QueryType.USE

    def test_classify_query_other(self):
        """Test query classification for unknown query."""
        service = DatabaseService()
        assert service._classify_query("UNKNOWN COMMAND") == QueryType.OTHER

    def test_classify_query_with_cte(self):
        """Test query classification for CTE (WITH clause)."""
        service = DatabaseService()
        assert service._classify_query("WITH cte AS (SELECT 1) SELECT * FROM cte") == QueryType.SELECT
        assert service._classify_query("WITH RECURSIVE cte AS (SELECT 1) SELECT * FROM cte") == QueryType.SELECT

    def test_classify_query_empty(self):
        """Test query classification for empty query."""
        service = DatabaseService()
        assert service._classify_query("") == QueryType.OTHER
        assert service._classify_query("   ") == QueryType.OTHER

    def test_clean_display_directives(self):
        """Test cleaning display directives."""
        service = DatabaseService()
        assert service._clean_display_directives("SELECT * FROM users\\G") == "SELECT * FROM users"
        assert service._clean_display_directives("SELECT * FROM users\\G;") == "SELECT * FROM users;"
        assert service._clean_display_directives("SELECT * FROM users") == "SELECT * FROM users"

    def test_has_vertical_format_directive(self):
        """Test checking for vertical format directive."""
        service = DatabaseService()
        assert service.has_vertical_format_directive("SELECT * FROM users\\G") is True
        assert service.has_vertical_format_directive("SELECT * FROM users\\G;") is True
        assert service.has_vertical_format_directive("SELECT * FROM users") is False

    def test_extract_database_from_use(self):
        """Test extracting database name from USE statement."""
        service = DatabaseService()
        assert service._extract_database_from_use("USE test_db") == "test_db"
        assert service._extract_database_from_use("USE `test_db`") == "test_db"
        assert service._extract_database_from_use("USE test_db;") == "test_db"
        assert service._extract_database_from_use("SELECT * FROM users") is None

    def test_is_transaction_control_statement(self):
        """Test checking transaction control statements."""
        service = DatabaseService()
        is_txn, qtype = service.is_transaction_control_statement("BEGIN")
        assert is_txn is True
        assert qtype == QueryType.BEGIN

        is_txn, qtype = service.is_transaction_control_statement("COMMIT")
        assert is_txn is True
        assert qtype == QueryType.COMMIT

        is_txn, qtype = service.is_transaction_control_statement("ROLLBACK")
        assert is_txn is True
        assert qtype == QueryType.ROLLBACK

        is_txn, qtype = service.is_transaction_control_statement("SELECT 1")
        assert is_txn is False
        assert qtype is None

    def test_is_sql_statement(self):
        """Test checking if command is SQL statement."""
        service = DatabaseService()
        assert service.is_sql_statement("SELECT * FROM users") is True
        assert service.is_sql_statement("SHOW TABLES") is True
        assert service.is_sql_statement("SHOW DATABASES") is True
        assert service.is_sql_statement("show me slow queries") is False
        assert service.is_sql_statement("INSERT INTO users VALUES (1)") is True
        assert service.is_sql_statement("") is False
        assert service.is_sql_statement("   ") is False

    def test_is_sql_statement_show_with_modifiers(self):
        """Test SHOW statements with optional modifiers (FULL, GLOBAL, SESSION, etc)."""
        service = DatabaseService()
        # SHOW with modifiers should be recognized as SQL
        assert service.is_sql_statement("SHOW FULL PROCESSLIST") is True
        assert service.is_sql_statement("SHOW GLOBAL VARIABLES") is True
        assert service.is_sql_statement("SHOW SESSION STATUS") is True
        assert service.is_sql_statement("SHOW EXTENDED TABLES") is True
        assert service.is_sql_statement("SHOW FULL TABLES FROM information_schema") is True
        assert service.is_sql_statement("SHOW GLOBAL VARIABLES LIKE 'max_connections'") is True
        # Multiple modifiers
        assert service.is_sql_statement("SHOW FULL GLOBAL PROCESSLIST") is True
        assert service.is_sql_statement("SHOW FULL GLOBAL PROCESSLIST;") is True
        # SHOW with invalid target should still be rejected
        assert service.is_sql_statement("SHOW me the tables") is False
        # SHOW alone should be rejected
        assert service.is_sql_statement("SHOW") is False
        assert service.is_sql_statement("SHOW FULL") is False

    def test_execute_query_select(self):
        """Test executing SELECT query."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchall.return_value = [("row1",), ("row2",)]
        mock_client.get_columns.return_value = ["col1"]
        service._active_connection = mock_client

        result = service.execute_query("SELECT * FROM users")

        assert result.success is True
        assert result.query_type == QueryType.SELECT
        assert result.rows == [("row1",), ("row2",)]
        assert result.columns == ["col1"]
        mock_client.execute.assert_called_once()

    def test_execute_query_insert(self):
        """Test executing INSERT query."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.get_row_count.return_value = 1
        service._active_connection = mock_client

        result = service.execute_query("INSERT INTO users VALUES (1)")

        assert result.success is True
        assert result.query_type == QueryType.INSERT
        assert result.affected_rows == 1
        assert result.columns is None

    def test_execute_query_use(self):
        """Test executing USE query."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.get_row_count.return_value = 0
        service._active_connection = mock_client

        result = service.execute_query("USE test_db")

        assert result.success is True
        assert service._current_database == "test_db"

    def test_execute_query_error(self):
        """Test executing query with error."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.side_effect = Exception("Table doesn't exist")
        service._active_connection = mock_client

        result = service.execute_query("SELECT * FROM invalid_table")

        assert result.success is False
        assert result.error is not None
        assert "Table doesn't exist" in result.error

    def test_execute_query_not_connected(self):
        """Test executing query when not connected."""
        service = DatabaseService()
        with pytest.raises(DatabaseError):
            service.execute_query("SELECT 1")

    def test_begin_transaction(self):
        """Test beginning transaction."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client

        service.begin_transaction()
        mock_client.begin_transaction.assert_called_once()

    def test_commit_transaction(self):
        """Test committing transaction."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client

        service.commit_transaction()
        mock_client.commit_transaction.assert_called_once()

    def test_rollback_transaction(self):
        """Test rolling back transaction."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client

        service.rollback_transaction()
        mock_client.rollback_transaction.assert_called_once()

    def test_set_autocommit(self):
        """Test setting autocommit."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client

        service.set_autocommit(False)
        mock_client.set_autocommit.assert_called_once_with(False)

    def test_get_transaction_state(self):
        """Test getting transaction state."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.get_transaction_state.return_value = TransactionState.IN_TRANSACTION
        service._active_connection = mock_client

        state = service.get_transaction_state()
        assert state == TransactionState.IN_TRANSACTION

    def test_get_transaction_state_not_connected(self):
        """Test getting transaction state when not connected."""
        service = DatabaseService()
        assert service.get_transaction_state() is None

    def test_get_autocommit_status(self):
        """Test getting autocommit status."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.get_autocommit.return_value = True
        service._active_connection = mock_client

        assert service.get_autocommit_status() is True

    def test_get_autocommit_status_not_connected(self):
        """Test getting autocommit status when not connected."""
        service = DatabaseService()
        assert service.get_autocommit_status() is None

    def test_get_current_database(self):
        """Test getting current database."""
        service = DatabaseService()
        service._current_database = "test_db"
        mock_client = MagicMock()
        service._active_connection = mock_client

        assert service.get_current_database() == "test_db"

    def test_get_current_database_not_connected(self):
        """Test getting current database when not connected."""
        service = DatabaseService()
        assert service.get_current_database() is None

    def test_get_schema_info(self):
        """Test getting schema info."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchall.return_value = [("table1",), ("table2",)]
        service._active_connection = mock_client
        service._current_database = "test_db"

        schema_info = service.get_schema_info()

        assert schema_info.current_database == "test_db"
        assert "table1" in schema_info.tables
        assert "table2" in schema_info.tables

    def test_change_database(self):
        """Test changing database."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client

        service.change_database("new_db")

        assert service._current_database == "new_db"
        mock_client.change_database.assert_called_once_with("new_db")

    def test_get_databases(self):
        """Test getting databases list."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchall.return_value = [("db1",), ("db2",)]
        service._active_connection = mock_client

        databases = service.get_databases()

        assert "db1" in databases
        assert "db2" in databases

    def test_get_table_structure(self):
        """Test getting table structure."""
        service = DatabaseService()
        mock_client = MagicMock()
        mock_client.execute.return_value = None
        mock_client.fetchall.return_value = [
            (
                "col1",
                "int",
            )
        ]
        service._active_connection = mock_client

        structure = service.get_table_structure("test_table")

        assert len(structure) == 1
        mock_client.execute.assert_called_once()

    def test_last_query_context(self):
        """Test last query context management."""
        service = DatabaseService()
        assert service.get_last_query_context() is None

        service.set_last_query_context(
            sql="SELECT 1",
            status=QueryStatus.SUCCESS,
            columns=["col1"],
            rows=[(1,)],
        )

        context = service.get_last_query_context()
        assert context is not None
        assert context.sql == "SELECT 1"
        assert context.status == QueryStatus.SUCCESS

        consumed = service.consume_last_query_context()
        assert consumed == context
        assert service.get_last_query_context() is None

        service.set_last_query_context(sql="SELECT 2")
        service.clear_last_query_context()
        assert service.get_last_query_context() is None

    def test_context_manager(self):
        """Test context manager usage."""
        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client

        with service:
            assert service.is_connected()

        assert not service.is_connected()
        mock_client.close.assert_called_once()


class TestGlobalStateFunctions:
    """Tests for global state management functions."""

    def test_get_set_clear_service(self):
        """Test global service management."""
        clear_service()
        assert get_service() is None

        service = DatabaseService()
        set_service(service)
        assert get_service() == service

        clear_service()
        assert get_service() is None

    def test_get_database_client(self):
        """Test getting database client."""
        clear_service()
        assert get_database_client() is None

        service = DatabaseService()
        mock_client = MagicMock()
        service._active_connection = mock_client
        set_service(service)

        assert get_database_client() == mock_client

    def test_get_current_database_global(self):
        """Test getting current database from global service."""
        clear_service()
        assert get_current_database() is None

        service = DatabaseService()
        service._current_database = "test_db"
        set_service(service)

        assert get_current_database() == "test_db"


class TestFactoryFunctions:
    """Tests for factory functions."""

    @patch("database.service.DatabaseService")
    @patch("database.service.set_service")
    def test_create_connection_context_success(self, mock_set_service, mock_service_class):
        """Test creating connection context successfully."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.connect.return_value = "connection_id"

        context = create_connection_context(
            host="localhost",
            port=3306,
            user="test_user",
            password="test_pass",
            database="test_db",
        )

        assert context.status == ConnectionStatus.CONNECTED.value
        assert context.db_service == mock_service
        assert context.query_history is not None

    @patch("database.service.DatabaseService")
    @patch("database.service.set_service")
    def test_create_connection_context_failure(self, mock_set_service, mock_service_class):
        """Test creating connection context with failure."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.connect.side_effect = Exception("Connection failed")

        context = create_connection_context(
            host="localhost",
            port=3306,
            user="test_user",
            password="test_pass",
            database=None,
        )

        assert context.status == ConnectionStatus.FAILED.value
        assert context.error is not None

    def test_create_database_service(self):
        """Test creating database service."""
        service = create_database_service()
        assert isinstance(service, DatabaseService)
        assert not service.is_connected()


class TestDuckDBConnectionContext:
    """Tests for DuckDB connection context creation."""

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_single_file(self, mock_parser, mock_client_class):
        """Test creating DuckDB connection context with single file."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_url = ParsedDuckDBURL(
            protocol=DuckDBProtocol.FILE,
            path="/path/to/file.csv",
            original_url="file:///path/to/file.csv",
        )
        mock_parser.parse.return_value = mock_parsed_url

        mock_client = MagicMock()
        mock_client.load_file.return_value = ("table1", 10, 3, None)
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context("file:///path/to/file.csv")

        assert context.status == ConnectionStatus.CONNECTED.value
        assert context.db_service is not None
        assert context.query_history is not None
        mock_client.load_file.assert_called_once()

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_multiple_files(self, mock_parser, mock_client_class):
        """Test creating DuckDB connection context with multiple files."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_urls = [
            ParsedDuckDBURL(
                protocol=DuckDBProtocol.FILE,
                path="/path/to/file1.csv",
                original_url="file:///path/to/file1.csv",
            ),
            ParsedDuckDBURL(
                protocol=DuckDBProtocol.FILE,
                path="/path/to/file2.csv",
                original_url="file:///path/to/file2.csv",
            ),
        ]
        mock_parser.parse.side_effect = mock_parsed_urls

        mock_client = MagicMock()
        mock_client.load_files.return_value = [
            ("table1", 10, 3, None),
            ("table2", 20, 4, None),
        ]
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context(
            [
                "file:///path/to/file1.csv",
                "file:///path/to/file2.csv",
            ]
        )

        assert context.status == ConnectionStatus.CONNECTED.value
        assert context.db_service is not None
        mock_client.load_files.assert_called_once()

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_duckdb_protocol(self, mock_parser, mock_client_class):
        """Test creating DuckDB connection context with duckdb:// protocol."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_url = ParsedDuckDBURL(
            protocol=DuckDBProtocol.DUCKDB,
            path="/path/to/db.duckdb",
            original_url="duckdb:///path/to/db.duckdb",
        )
        mock_parser.parse.return_value = mock_parsed_url

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context("duckdb:///path/to/db.duckdb")

        assert context.status == ConnectionStatus.CONNECTED.value
        assert context.db_service is not None
        # Should not call load_file for duckdb:// protocol
        mock_client.load_file.assert_not_called()
        mock_client.load_files.assert_not_called()

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_memory(self, mock_parser, mock_client_class):
        """Test creating DuckDB connection context with in-memory mode."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_url = ParsedDuckDBURL(
            protocol=DuckDBProtocol.DUCKDB,
            path=":memory:",
            is_memory=True,
            original_url="duckdb://:memory:",
        )
        mock_parser.parse.return_value = mock_parsed_url

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context("duckdb://:memory:")

        assert context.status == ConnectionStatus.CONNECTED.value
        assert context.db_service is not None

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_file_load_error(self, mock_parser, mock_client_class):
        """Test creating DuckDB connection context when file loading fails."""
        from database.duckdb_loader import (
            ParsedDuckDBURL,
            DuckDBProtocol,
            FileLoadError,
        )

        mock_parsed_url = ParsedDuckDBURL(
            protocol=DuckDBProtocol.FILE,
            path="/nonexistent/file.csv",
            original_url="file:///nonexistent/file.csv",
        )
        mock_parser.parse.return_value = mock_parsed_url

        mock_client = MagicMock()
        mock_client.load_file.side_effect = FileLoadError("File not found")
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context("file:///nonexistent/file.csv")

        assert context.status == ConnectionStatus.FAILED.value
        assert context.error is not None
        mock_client.close.assert_called_once()

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_parse_error(self, mock_parser, mock_client_class):
        """Test creating DuckDB connection context when URL parsing fails."""
        mock_parser.parse.side_effect = ValueError("Invalid URL format")

        context = create_duckdb_connection_context("invalid://url")

        assert context.status == ConnectionStatus.FAILED.value
        assert context.error is not None

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_display_name_single_file(self, mock_parser, mock_client_class):
        """Test display name generation for single file."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_url = ParsedDuckDBURL(
            protocol=DuckDBProtocol.FILE,
            path="/path/to/data.csv",
            original_url="file:///path/to/data.csv",
        )
        mock_parser.parse.return_value = mock_parsed_url

        mock_client = MagicMock()
        mock_client.load_file.return_value = ("table1", 10, 3, None)
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context("file:///path/to/data.csv")

        assert context.display_name == "File: data.csv"

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_display_name_multiple_files(self, mock_parser, mock_client_class):
        """Test display name generation for multiple files."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_urls = [
            ParsedDuckDBURL(
                protocol=DuckDBProtocol.FILE,
                path="/path/to/file1.csv",
                original_url="file:///path/to/file1.csv",
            ),
            ParsedDuckDBURL(
                protocol=DuckDBProtocol.FILE,
                path="/path/to/file2.csv",
                original_url="file:///path/to/file2.csv",
            ),
        ]
        mock_parser.parse.side_effect = mock_parsed_urls

        mock_client = MagicMock()
        mock_client.load_files.return_value = [
            ("table1", 10, 3, None),
            ("table2", 20, 4, None),
        ]
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context(
            [
                "file:///path/to/file1.csv",
                "file:///path/to/file2.csv",
            ]
        )

        assert "file1.csv" in context.display_name or "file2.csv" in context.display_name
        assert "Files:" in context.display_name or "2 files" in context.display_name

    @patch("database.duckdb_client.DuckDBClient")
    @patch("database.duckdb_loader.DuckDBURLParser")
    def test_create_duckdb_connection_context_display_name_duckdb(self, mock_parser, mock_client_class):
        """Test display name generation for DuckDB database file."""
        from database.duckdb_loader import ParsedDuckDBURL, DuckDBProtocol

        mock_parsed_url = ParsedDuckDBURL(
            protocol=DuckDBProtocol.DUCKDB,
            path="/path/to/database.duckdb",
            original_url="duckdb:///path/to/database.duckdb",
        )
        mock_parser.parse.return_value = mock_parsed_url

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        context = create_duckdb_connection_context("duckdb:///path/to/database.duckdb")

        assert "database.duckdb" in context.display_name or "Database:" in context.display_name
