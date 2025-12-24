"""Tests for database.client module."""

import pytest
from unittest.mock import MagicMock, patch
from database.client import (
    validate_identifier,
    DatabaseClientFactory,
    MySQLClient,
    TransactionState,
)


class TestValidateIdentifier:
    """Tests for validate_identifier function."""

    def test_valid_identifier_plain(self):
        """Test valid plain identifier."""
        assert validate_identifier("test_table") == "test_table"
        assert validate_identifier("test123") == "test123"
        assert validate_identifier("_test") == "_test"
        assert validate_identifier("test$table") == "test$table"

    def test_valid_identifier_with_backticks(self):
        """Test valid identifier with backticks."""
        assert validate_identifier("`test_table`") == "test_table"
        assert validate_identifier("`test-123`") == "test-123"
        assert validate_identifier("`test table`") == "test table"

    def test_invalid_identifier_empty(self):
        """Test empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_identifier("")
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_identifier("   ")

    def test_invalid_identifier_starts_with_number(self):
        """Test identifier starting with number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("123test")

    def test_invalid_identifier_special_chars(self):
        """Test identifier with invalid special characters."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("test-table")
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_identifier("test.table")

    def test_invalid_identifier_embedded_backticks(self):
        """Test identifier with embedded backticks raises ValueError."""
        with pytest.raises(ValueError, match="embedded backticks"):
            validate_identifier("`test`table`")


class TestDatabaseClientFactory:
    """Tests for DatabaseClientFactory class."""

    def test_register_and_create(self):
        """Test registering and creating a client."""

        class MockClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        DatabaseClientFactory.register("test_engine", MockClient)
        client = DatabaseClientFactory.create("test_engine", host="localhost", port=3306)
        assert isinstance(client, MockClient)
        assert client.kwargs["host"] == "localhost"
        assert client.kwargs["port"] == 3306

    def test_create_unsupported_engine(self):
        """Test creating unsupported engine raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported engine"):
            DatabaseClientFactory.create("unknown_engine")

    def test_supported_engines(self):
        """Test getting supported engines list."""
        engines = DatabaseClientFactory.supported_engines()
        assert "mysql" in engines


class TestMySQLClient:
    """Tests for MySQLClient class."""

    @patch("database.client.mysql.connector.connect")
    def test_init_default_port(self, mock_connect):
        """Test MySQLClient initialization with default port."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=None, user="test_user", password="test_pass", database="test_db")

        assert client._transaction_state == TransactionState.NOT_IN_TRANSACTION
        assert client._autocommit is True
        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["port"] == 3306
        assert call_kwargs["host"] == "localhost"
        assert call_kwargs["user"] == "test_user"
        assert call_kwargs["password"] == "test_pass"
        assert call_kwargs["database"] == "test_db"
        assert call_kwargs["autocommit"] is True

    @patch("database.client.mysql.connector.connect")
    def test_init_custom_port(self, mock_connect):
        """Test MySQLClient initialization with custom port."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3307, user="test_user", password="test_pass")

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["port"] == 3307

    @patch("database.client.mysql.connector.connect")
    def test_init_ssl_config(self, mock_connect):
        """Test MySQLClient initialization with SSL configuration."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(
            host="localhost",
            port=3306,
            user="test_user",
            password="test_pass",
            ssl_ca="/path/to/ca.pem",
            ssl_cert="/path/to/cert.pem",
            ssl_key="/path/to/key.pem",
            ssl_mode="VERIFY_CA",
        )

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["ssl_ca"] == "/path/to/ca.pem"
        assert call_kwargs["ssl_cert"] == "/path/to/cert.pem"
        assert call_kwargs["ssl_key"] == "/path/to/key.pem"
        assert call_kwargs["ssl_verify_cert"] is True
        assert call_kwargs["ssl_verify_identity"] is False

    @patch("database.client.mysql.connector.connect")
    def test_engine_name(self, mock_connect):
        """Test engine_name class method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.engine_name() == "mysql"
        assert MySQLClient.engine_name() == "mysql"

    @patch("database.client.mysql.connector.connect")
    def test_execute(self, mock_connect):
        """Test execute method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        result = client.execute("SELECT 1")
        assert result == mock_cursor
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    @patch("database.client.mysql.connector.connect")
    def test_fetchall(self, mock_connect):
        """Test fetchall method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("row1",), ("row2",)]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        result = client.fetchall()
        assert result == [("row1",), ("row2",)]

    @patch("database.client.mysql.connector.connect")
    def test_fetchone(self, mock_connect):
        """Test fetchone method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("row1",)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        result = client.fetchone()
        assert result == ("row1",)

    @patch("database.client.mysql.connector.connect")
    def test_close(self, mock_connect):
        """Test close method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.close()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("database.client.mysql.connector.connect")
    def test_change_database(self, mock_connect):
        """Test change_database method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.change_database("new_db")
        mock_cursor.execute.assert_called_with("USE `new_db`;")

    @patch("database.client.mysql.connector.connect")
    def test_get_transaction_state(self, mock_connect):
        """Test get_transaction_state method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.get_transaction_state() == TransactionState.NOT_IN_TRANSACTION

    @patch("database.client.mysql.connector.connect")
    def test_begin_transaction(self, mock_connect):
        """Test begin_transaction method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.begin_transaction()
        assert client.get_transaction_state() == TransactionState.IN_TRANSACTION
        assert client._autocommit is False
        assert mock_cursor.execute.call_count == 2

    @patch("database.client.mysql.connector.connect")
    def test_begin_transaction_already_in_transaction(self, mock_connect):
        """Test begin_transaction when already in transaction raises error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.begin_transaction()
        with pytest.raises(Exception, match="Already in transaction"):
            client.begin_transaction()

    @patch("database.client.mysql.connector.connect")
    def test_commit_transaction(self, mock_connect):
        """Test commit_transaction method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.begin_transaction()
        client.commit_transaction()
        assert client.get_transaction_state() == TransactionState.NOT_IN_TRANSACTION
        assert client._autocommit is True

    @patch("database.client.mysql.connector.connect")
    def test_commit_transaction_not_in_transaction(self, mock_connect):
        """Test commit_transaction when not in transaction raises error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        with pytest.raises(Exception, match="Not in transaction"):
            client.commit_transaction()

    @patch("database.client.mysql.connector.connect")
    def test_rollback_transaction(self, mock_connect):
        """Test rollback_transaction method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.begin_transaction()
        client.rollback_transaction()
        assert client.get_transaction_state() == TransactionState.NOT_IN_TRANSACTION
        assert client._autocommit is True

    @patch("database.client.mysql.connector.connect")
    def test_set_autocommit(self, mock_connect):
        """Test set_autocommit method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        # Test setting autocommit to False
        client.set_autocommit(False)
        assert client._autocommit is False
        assert client.get_transaction_state() == TransactionState.IN_TRANSACTION

        # Reset state to allow setting autocommit back to True
        client._transaction_state = TransactionState.NOT_IN_TRANSACTION
        client.set_autocommit(True)
        assert client._autocommit is True
        assert client.get_transaction_state() == TransactionState.NOT_IN_TRANSACTION

    @patch("database.client.mysql.connector.connect")
    def test_set_autocommit_in_transaction(self, mock_connect):
        """Test set_autocommit when in transaction raises error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        client.begin_transaction()
        with pytest.raises(Exception, match="Cannot change autocommit mode"):
            client.set_autocommit(True)

    @patch("database.client.mysql.connector.connect")
    def test_get_autocommit(self, mock_connect):
        """Test get_autocommit method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.get_autocommit() is True

    @patch("database.client.mysql.connector.connect")
    def test_ping(self, mock_connect):
        """Test ping method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.ping.return_value = None
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.ping() is True
        mock_conn.ping.assert_called_once_with(reconnect=False, attempts=1, delay=0)

    @patch("database.client.mysql.connector.connect")
    def test_ping_failure(self, mock_connect):
        """Test ping method when connection fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.ping.side_effect = Exception("Connection lost")
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.ping() is False

    @patch("database.client.mysql.connector.connect")
    def test_get_columns(self, mock_connect):
        """Test get_columns method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",), ("col2",)]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        columns = client.get_columns()
        assert columns == ["col1", "col2"]

    @patch("database.client.mysql.connector.connect")
    def test_get_columns_none(self, mock_connect):
        """Test get_columns when description is None."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        columns = client.get_columns()
        assert columns is None

    @patch("database.client.mysql.connector.connect")
    def test_get_row_count(self, mock_connect):
        """Test get_row_count method."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.get_row_count() == 5

    @patch("database.client.mysql.connector.connect")
    def test_get_row_count_negative(self, mock_connect):
        """Test get_row_count when rowcount is negative."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = -1
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        client = MySQLClient(host="localhost", port=3306, user="test", password="test")
        assert client.get_row_count() == -1
