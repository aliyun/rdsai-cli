"""Tests for ui.metacmd.connect module - database connection functionality."""

from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch as mock_patch

import pytest

from database.types import ConnectionContext, ConnectionStatus
from ui.metacmd.connect import (
    BaseConnector,
    ConnectionHandler,
    DuckDBConnector,
    MySQLConnector,
    connect,
    disconnect,
)


class TestBaseConnector:
    """Tests for BaseConnector abstract class."""

    def test_base_connector_is_abstract(self):
        """Test that BaseConnector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseConnector()

    def test_base_connector_get_display_name(self):
        """Test BaseConnector default get_display_name implementation."""

        # Create a concrete implementation for testing
        class TestConnector(BaseConnector):
            def can_handle(self, args: list[str]) -> bool:
                return True

            async def connect(self, session, args: list[str]) -> ConnectionContext:
                return ConnectionContext(display_name="test")

        connector = TestConnector()
        connection = ConnectionContext(display_name="test_db")
        assert connector.get_display_name(connection) == "test_db"

    def test_base_connector_get_extra_info(self):
        """Test BaseConnector default get_extra_info implementation."""

        # Create a concrete implementation for testing
        class TestConnector(BaseConnector):
            def can_handle(self, args: list[str]) -> bool:
                return True

            async def connect(self, session, args: list[str]) -> ConnectionContext:
                return ConnectionContext()

        connector = TestConnector()
        connection = ConnectionContext()
        assert connector.get_extra_info(connection) == []


class TestMySQLConnector:
    """Tests for MySQLConnector class."""

    @pytest.fixture
    def connector(self):
        """Create a MySQLConnector instance."""
        return MySQLConnector()

    def test_can_handle_empty_args(self, connector):
        """Test can_handle with empty arguments."""
        assert connector.can_handle([]) is True

    def test_can_handle_empty_string_args(self, connector):
        """Test can_handle with empty string arguments."""
        assert connector.can_handle(["", "  "]) is True

    def test_can_handle_non_empty_args(self, connector):
        """Test can_handle with non-empty arguments."""
        assert connector.can_handle(["file.csv"]) is False
        assert connector.can_handle(["http://example.com/file.csv"]) is False

    @pytest.mark.asyncio
    async def test_connect_form_cancelled(self, connector):
        """Test connect when form is cancelled."""
        from ui.metacmd.setup import _FormResult

        mock_session = MagicMock()
        with mock_patch("ui.metacmd.connect._run_form") as mock_form:
            mock_form.return_value = _FormResult(submitted=False, values={})

            with pytest.raises(ValueError, match="Connection cancelled by user"):
                await connector.connect(mock_session, [])

    @pytest.mark.asyncio
    async def test_connect_missing_host(self, connector):
        """Test connect with missing host."""
        from ui.metacmd.setup import _FormResult

        mock_session = MagicMock()
        with mock_patch("ui.metacmd.connect._run_form") as mock_form:
            mock_form.return_value = _FormResult(
                submitted=True,
                values={"host": "", "port": "3306", "user": "testuser"},
            )

            with pytest.raises(ValueError, match="Host is required"):
                await connector.connect(mock_session, [])

    @pytest.mark.asyncio
    async def test_connect_missing_user(self, connector):
        """Test connect with missing user."""
        from ui.metacmd.setup import _FormResult

        mock_session = MagicMock()
        with mock_patch("ui.metacmd.connect._run_form") as mock_form:
            mock_form.return_value = _FormResult(
                submitted=True,
                values={"host": "localhost", "port": "3306", "user": ""},
            )

            with pytest.raises(ValueError, match="Username is required"):
                await connector.connect(mock_session, [])

    @pytest.mark.asyncio
    async def test_connect_invalid_port(self, connector):
        """Test connect with invalid port."""
        from ui.metacmd.setup import _FormResult

        mock_session = MagicMock()
        with mock_patch("ui.metacmd.connect._run_form") as mock_form:
            mock_form.return_value = _FormResult(
                submitted=True,
                values={"host": "localhost", "port": "invalid", "user": "testuser"},
            )

            with pytest.raises(ValueError, match="Invalid port number"):
                await connector.connect(mock_session, [])

    @pytest.mark.asyncio
    async def test_connect_success(self, connector):
        """Test successful MySQL connection."""
        from ui.metacmd.setup import _FormResult

        mock_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.CONNECTED.value,
            display_name="mysql://localhost",
        )
        mock_session.connect.return_value = mock_connection

        with (
            mock_patch("ui.metacmd.connect._run_form") as mock_form,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_form.return_value = _FormResult(
                submitted=True,
                values={
                    "host": "localhost",
                    "port": "3306",
                    "user": "testuser",
                    "password": "testpass",
                    "database": "testdb",
                },
            )

            result = await connector.connect(mock_session, [])

            assert result == mock_connection
            mock_session.connect.assert_called_once_with(
                host="localhost",
                port=3306,
                user="testuser",
                password="testpass",
                database="testdb",
            )
            mock_console.print.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_default_port(self, connector):
        """Test connect with default port."""
        from ui.metacmd.setup import _FormResult

        mock_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.CONNECTED.value,
            display_name="mysql://localhost",
        )
        mock_session.connect.return_value = mock_connection

        with (
            mock_patch("ui.metacmd.connect._run_form") as mock_form,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_form.return_value = _FormResult(
                submitted=True,
                values={
                    "host": "localhost",
                    "port": "",
                    "user": "testuser",
                    "password": "",
                    "database": "",
                },
            )

            result = await connector.connect(mock_session, [])

            assert result == mock_connection
            mock_session.connect.assert_called_once_with(
                host="localhost",
                port=3306,
                user="testuser",
                password=None,
                database=None,
            )

    def test_get_extra_info(self, connector):
        """Test get_extra_info returns empty list."""
        connection = ConnectionContext()
        assert connector.get_extra_info(connection) == []


class TestDuckDBConnector:
    """Tests for DuckDBConnector class."""

    @pytest.fixture
    def connector(self):
        """Create a DuckDBConnector instance."""
        return DuckDBConnector()

    def test_can_handle_empty_args(self, connector):
        """Test can_handle with empty arguments."""
        assert connector.can_handle([]) is False

    def test_can_handle_file_protocol(self, connector):
        """Test can_handle with file:// protocol."""
        with mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser:
            mock_parser.has_protocol.return_value = True
            assert connector.can_handle(["file:///path/to/file.csv"]) is True

    def test_can_handle_http_protocol(self, connector):
        """Test can_handle with http:// protocol."""
        with mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser:
            mock_parser.has_protocol.return_value = True
            assert connector.can_handle(["http://example.com/file.csv"]) is True

    def test_can_handle_local_file_path(self, connector):
        """Test can_handle with local file path."""
        with mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser:
            mock_parser.has_protocol.return_value = False
            mock_parser.is_local_file_path.return_value = True
            assert connector.can_handle(["file.csv"]) is True

    def test_can_handle_invalid_args(self, connector):
        """Test can_handle with invalid arguments."""
        with mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser:
            mock_parser.has_protocol.return_value = False
            mock_parser.is_local_file_path.return_value = False
            assert connector.can_handle(["invalid"]) is False

    def test_can_handle_empty_strings(self, connector):
        """Test can_handle with empty strings."""
        with mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser:
            assert connector.can_handle(["", "  "]) is False

    @pytest.mark.asyncio
    async def test_connect_file_not_found(self, connector):
        """Test connect when file is not found."""
        mock_session = MagicMock()
        mock_parsed_url = MagicMock()
        mock_parsed_url.is_file_protocol = True
        mock_parsed_url.is_http_protocol = False
        mock_parsed_url.is_duckdb_protocol = False

        with (
            mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_parser.has_protocol.return_value = False
            mock_parser.is_local_file_path.return_value = True
            mock_parser.resolve_file_path.side_effect = ValueError("File not found")

            with pytest.raises(ValueError, match="File not found"):
                await connector.connect(mock_session, ["nonexistent.csv"])

            mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_connect_invalid_url(self, connector):
        """Test connect with invalid URL."""
        mock_session = MagicMock()

        with (
            mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_parser.has_protocol.return_value = False
            mock_parser.is_local_file_path.return_value = False

            with pytest.raises(ValueError, match="Invalid file path or URL"):
                await connector.connect(mock_session, ["invalid"])

            mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_connect_empty_urls(self, connector):
        """Test connect with empty URLs after filtering."""
        mock_session = MagicMock()

        with mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser:
            mock_parser.has_protocol.return_value = False
            mock_parser.is_local_file_path.return_value = False

            with pytest.raises(ValueError, match="At least one file path or URL is required"):
                await connector.connect(mock_session, ["", "  "])

    @pytest.mark.asyncio
    async def test_connect_url_parse_error(self, connector):
        """Test connect when URL parsing fails."""
        mock_session = MagicMock()
        mock_parsed_url = MagicMock()

        with (
            mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_parser.has_protocol.return_value = True
            mock_parser.parse.side_effect = ValueError("Invalid URL format")

            with pytest.raises(ValueError, match="Invalid URL format"):
                await connector.connect(mock_session, ["invalid://url"])

            mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_connect_single_file_success(self, connector):
        """Test successful connection to a single file."""
        from database.duckdb_loader import ParsedDuckDBURL

        mock_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.CONNECTED.value,
            display_name="file.csv",
        )
        mock_parsed_url = MagicMock(spec=ParsedDuckDBURL)
        mock_parsed_url.is_file_protocol = True
        mock_parsed_url.is_http_protocol = False
        mock_parsed_url.is_duckdb_protocol = False
        mock_parsed_url.is_memory = False
        mock_parsed_url.original_url = "file:///path/to/file.csv"

        with (
            mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser,
            mock_patch("database.service.create_duckdb_connection_context") as mock_create,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_parser.has_protocol.return_value = True
            mock_parser.parse.return_value = mock_parsed_url
            mock_create.return_value = mock_connection

            result = await connector.connect(mock_session, ["file:///path/to/file.csv"])

            assert result == mock_connection
            mock_create.assert_called_once_with("file:///path/to/file.csv")
            mock_session.disconnect.assert_called_once()
            assert mock_session._db_connection == mock_connection

    @pytest.mark.asyncio
    async def test_connect_multiple_files_success(self, connector):
        """Test successful connection to multiple files."""
        from database.duckdb_loader import ParsedDuckDBURL

        mock_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.CONNECTED.value,
            display_name="file1.csv, file2.csv",
        )
        mock_parsed_url1 = MagicMock(spec=ParsedDuckDBURL)
        mock_parsed_url1.is_file_protocol = True
        mock_parsed_url1.is_http_protocol = False
        mock_parsed_url1.is_duckdb_protocol = False
        mock_parsed_url1.original_url = "file1.csv"
        mock_parsed_url2 = MagicMock(spec=ParsedDuckDBURL)
        mock_parsed_url2.is_file_protocol = True
        mock_parsed_url2.is_http_protocol = False
        mock_parsed_url2.is_duckdb_protocol = False
        mock_parsed_url2.original_url = "file2.csv"

        with (
            mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser,
            mock_patch("database.service.create_duckdb_connection_context") as mock_create,
            mock_patch("ui.metacmd.connect.console") as mock_console,
        ):
            mock_parser.has_protocol.return_value = False
            mock_parser.is_local_file_path.return_value = True
            mock_parser.resolve_file_path.side_effect = lambda x: f"/resolved/{x}"
            mock_parser.normalize_local_path.side_effect = lambda x: f"file://{x}"
            mock_parser.parse.side_effect = [mock_parsed_url1, mock_parsed_url2]
            mock_create.return_value = mock_connection

            result = await connector.connect(mock_session, ["file1.csv", "file2.csv"])

            assert result == mock_connection
            mock_create.assert_called_once_with(["file:///resolved/file1.csv", "file:///resolved/file2.csv"])

    @pytest.mark.asyncio
    async def test_connect_connection_failed(self, connector):
        """Test connect when connection fails."""
        from database.duckdb_loader import ParsedDuckDBURL

        mock_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.FAILED.value,
            display_name="file.csv",
            error="Connection failed",
        )
        mock_parsed_url = MagicMock(spec=ParsedDuckDBURL)
        mock_parsed_url.is_file_protocol = True
        mock_parsed_url.is_http_protocol = False
        mock_parsed_url.is_duckdb_protocol = False

        with (
            mock_patch("database.duckdb_loader.DuckDBURLParser") as mock_parser,
            mock_patch("database.service.create_duckdb_connection_context") as mock_create,
        ):
            mock_parser.has_protocol.return_value = True
            mock_parser.parse.return_value = mock_parsed_url
            mock_create.return_value = mock_connection

            with pytest.raises(ValueError, match="Connection failed"):
                await connector.connect(mock_session, ["file:///path/to/file.csv"])

    def test_format_file_load_info_with_url(self, connector):
        """Test _format_file_load_info with original URL."""
        result = connector._format_file_load_info(
            table_name="test_table",
            row_count=100,
            column_count=5,
            original_url="file.csv",
        )
        assert "file.csv" in result
        assert "test_table" in result
        assert "100 rows" in result
        assert "5 columns" in result

    def test_format_file_load_info_without_url(self, connector):
        """Test _format_file_load_info without original URL."""
        result = connector._format_file_load_info(
            table_name="test_table",
            row_count=100,
            column_count=5,
        )
        assert "test_table" in result
        assert "100 rows" in result
        assert "5 columns" in result

    def test_get_extra_info_single_file(self, connector):
        """Test get_extra_info with single file load info."""
        mock_db_service = MagicMock()
        mock_db_service._duckdb_load_info = [("test_table", 100, 5)]
        connection = ConnectionContext(db_service=mock_db_service)
        connection._parsed_url = MagicMock()
        connection._parsed_url.original_url = "file.csv"

        extra_info = connector.get_extra_info(connection)
        assert len(extra_info) == 1
        assert "test_table" in extra_info[0]
        assert "file.csv" in extra_info[0]

    def test_get_extra_info_multiple_files(self, connector):
        """Test get_extra_info with multiple files load info."""
        mock_db_service = MagicMock()
        mock_db_service._duckdb_load_info = [
            ("table1", 100, 5),
            ("table2", 200, 3),
        ]
        connection = ConnectionContext(db_service=mock_db_service)
        mock_parsed_url1 = MagicMock()
        mock_parsed_url1.original_url = "file1.csv"
        mock_parsed_url2 = MagicMock()
        mock_parsed_url2.original_url = "file2.csv"
        connection._parsed_urls = [mock_parsed_url1, mock_parsed_url2]

        extra_info = connector.get_extra_info(connection)
        assert len(extra_info) == 2
        assert "table1" in extra_info[0]
        assert "file1.csv" in extra_info[0]
        assert "table2" in extra_info[1]
        assert "file2.csv" in extra_info[1]

    def test_get_extra_info_no_load_info(self, connector):
        """Test get_extra_info when no load info is available."""
        mock_db_service = MagicMock()
        mock_db_service._duckdb_load_info = None
        connection = ConnectionContext(db_service=mock_db_service)

        extra_info = connector.get_extra_info(connection)
        assert extra_info == []

    def test_get_extra_info_backward_compatibility(self, connector):
        """Test get_extra_info with backward compatibility (single parsed_url)."""
        mock_db_service = MagicMock()
        mock_db_service._duckdb_load_info = [("test_table", 100, 5)]
        connection = ConnectionContext(db_service=mock_db_service)
        connection._parsed_url = MagicMock()
        connection._parsed_url.original_url = "file.csv"
        # No _parsed_urls attribute

        extra_info = connector.get_extra_info(connection)
        assert len(extra_info) == 1

    def test_print_supported_formats(self, connector):
        """Test _print_supported_formats prints help information."""
        with mock_patch("ui.metacmd.connect.console") as mock_console:
            connector._print_supported_formats()
            assert mock_console.print.call_count == len(connector._SUPPORTED_FORMATS)


class TestConnectionHandler:
    """Tests for ConnectionHandler class."""

    def setup_method(self):
        """Reset connectors before each test."""
        ConnectionHandler._connectors = []

    def test_register_connector(self):
        """Test register_connector adds connector to list."""
        connector = MySQLConnector()
        ConnectionHandler.register_connector(connector)
        assert connector in ConnectionHandler._connectors

    def test_register_multiple_connectors(self):
        """Test registering multiple connectors."""
        mysql_connector = MySQLConnector()
        duckdb_connector = DuckDBConnector()
        ConnectionHandler.register_connector(mysql_connector)
        ConnectionHandler.register_connector(duckdb_connector)
        assert len(ConnectionHandler._connectors) == 2

    @pytest.mark.asyncio
    async def test_connect_no_connector_available(self):
        """Test connect when no connector can handle the request."""
        mock_session = MagicMock()
        mock_app = MagicMock()

        with mock_patch("ui.metacmd.connect.console") as mock_console:
            await ConnectionHandler.connect(mock_session, mock_app, ["invalid"])

            mock_console.print.assert_called()
            # Check that error message was printed
            assert any("No connector available" in str(call) for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_connect_mysql_success(self):
        """Test connect with MySQL connector."""
        mysql_connector = MySQLConnector()
        ConnectionHandler.register_connector(mysql_connector)

        mock_session = MagicMock()
        mock_app = MagicMock()
        mock_app.prompt_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.CONNECTED.value,
            display_name="mysql://localhost",
        )

        with (
            mock_patch.object(mysql_connector, "connect", new_callable=AsyncMock) as mock_connect,
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            mock_connect.return_value = mock_connection

            await ConnectionHandler.connect(mock_session, mock_app, [])

            mock_connect.assert_called_once_with(mock_session, [])
            mock_console.print.assert_called()
            assert mock_app._db_service == mock_connection.db_service
            assert mock_app._query_history == mock_connection.query_history

    @pytest.mark.asyncio
    async def test_connect_duckdb_success(self):
        """Test connect with DuckDB connector."""
        duckdb_connector = DuckDBConnector()
        ConnectionHandler.register_connector(duckdb_connector)

        mock_session = MagicMock()
        mock_app = MagicMock()
        mock_app.prompt_session = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.CONNECTED.value,
            display_name="file.csv",
        )

        with (
            mock_patch.object(duckdb_connector, "connect", new_callable=AsyncMock) as mock_connect,
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            mock_connect.return_value = mock_connection

            await ConnectionHandler.connect(mock_session, mock_app, ["file.csv"])

            mock_connect.assert_called_once_with(mock_session, ["file.csv"])
            mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_connect_connection_failed(self):
        """Test connect when connection fails."""
        mysql_connector = MySQLConnector()
        ConnectionHandler.register_connector(mysql_connector)

        mock_session = MagicMock()
        mock_app = MagicMock()
        mock_connection = ConnectionContext(
            db_service=MagicMock(),
            query_history=MagicMock(),
            status=ConnectionStatus.FAILED.value,
            display_name="mysql://localhost",
            error="Connection failed",
        )

        with (
            mock_patch.object(mysql_connector, "connect", new_callable=AsyncMock) as mock_connect,
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            mock_connect.return_value = mock_connection

            await ConnectionHandler.connect(mock_session, mock_app, [])

            mock_console.print.assert_called()
            # Check that error message was printed
            assert any("Connection failed" in str(call) for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_connect_value_error(self):
        """Test connect with ValueError (user cancellation)."""
        mysql_connector = MySQLConnector()
        ConnectionHandler.register_connector(mysql_connector)

        mock_session = MagicMock()
        mock_app = MagicMock()

        with (
            mock_patch.object(mysql_connector, "connect", new_callable=AsyncMock) as mock_connect,
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            mock_connect.side_effect = ValueError("Connection cancelled by user")

            await ConnectionHandler.connect(mock_session, mock_app, [])

            # Should print cancellation message
            mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_connect_general_exception(self):
        """Test connect with general exception."""
        mysql_connector = MySQLConnector()
        ConnectionHandler.register_connector(mysql_connector)

        mock_session = MagicMock()
        mock_app = MagicMock()

        with (
            mock_patch.object(mysql_connector, "connect", new_callable=AsyncMock) as mock_connect,
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            mock_connect.side_effect = Exception("Unexpected error")

            await ConnectionHandler.connect(mock_session, mock_app, [])

            mock_console.print.assert_called()
            mock_logger.exception.assert_called_once()

    def test_update_app_references(self):
        """Test _update_app_references updates app correctly."""
        mock_app = MagicMock()
        mock_app.prompt_session = MagicMock()
        mock_db_service = MagicMock()
        mock_query_history = MagicMock()
        connection = ConnectionContext(
            db_service=mock_db_service,
            query_history=mock_query_history,
            status=ConnectionStatus.CONNECTED.value,
        )

        ConnectionHandler._update_app_references(mock_app, connection)

        assert mock_app._db_service == mock_db_service
        assert mock_app._query_history == mock_query_history
        mock_app.prompt_session.refresh_db_service.assert_called_once_with(mock_db_service)

    def test_update_app_references_no_prompt_session(self):
        """Test _update_app_references when prompt_session is None."""
        mock_app = MagicMock()
        mock_app.prompt_session = None
        mock_db_service = MagicMock()
        mock_query_history = MagicMock()
        connection = ConnectionContext(
            db_service=mock_db_service,
            query_history=mock_query_history,
            status=ConnectionStatus.CONNECTED.value,
        )

        # Should not raise an error
        ConnectionHandler._update_app_references(mock_app, connection)

        assert mock_app._db_service == mock_db_service
        assert mock_app._query_history == mock_query_history


class TestConnectCommand:
    """Tests for connect meta command."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ShellREPL app."""
        app = MagicMock()
        app.loop = MagicMock()
        return app

    @pytest.mark.asyncio
    async def test_connect_not_neoloop(self, mock_app):
        """Test connect when loop is not NeoLoop."""
        from loop import Loop

        mock_app.loop = MagicMock(spec=Loop)

        with mock_patch("ui.metacmd.connect.console") as mock_console:
            await connect(mock_app, [])

            mock_console.print.assert_called_with("[red]This command requires NeoLoop runtime[/red]")

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, mock_app):
        """Test connect when already connected."""
        from loop.neoloop import NeoLoop

        mock_app.loop = MagicMock(spec=NeoLoop)
        mock_app.loop.runtime = MagicMock()
        mock_app.loop.runtime.session = MagicMock()
        mock_app.loop.runtime.session.is_connected = True
        mock_app.loop.runtime.session.db_connection = ConnectionContext(display_name="existing_db")

        with (
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.ConnectionHandler.connect") as mock_handler_connect,
        ):
            await connect(mock_app, [])

            mock_console.print.assert_called()
            mock_handler_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_app):
        """Test successful connect command."""
        from loop.neoloop import NeoLoop

        mock_app.loop = MagicMock(spec=NeoLoop)
        mock_app.loop.runtime = MagicMock()
        mock_app.loop.runtime.session = MagicMock()
        mock_app.loop.runtime.session.is_connected = False

        with mock_patch("ui.metacmd.connect.ConnectionHandler.connect") as mock_handler_connect:
            await connect(mock_app, ["file.csv"])

            mock_handler_connect.assert_called_once_with(
                mock_app.loop.runtime.session,
                mock_app,
                ["file.csv"],
            )


class TestDisconnectCommand:
    """Tests for disconnect meta command."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ShellREPL app."""
        app = MagicMock()
        app.loop = MagicMock()
        return app

    def test_disconnect_not_neoloop(self, mock_app):
        """Test disconnect when loop is not NeoLoop."""
        from loop import Loop

        mock_app.loop = MagicMock(spec=Loop)

        with mock_patch("ui.metacmd.connect.console") as mock_console:
            disconnect(mock_app, [])

            mock_console.print.assert_called_with("[red]This command requires NeoLoop runtime[/red]")

    def test_disconnect_not_connected(self, mock_app):
        """Test disconnect when not connected."""
        from loop.neoloop import NeoLoop

        mock_app.loop = MagicMock(spec=NeoLoop)
        mock_app.loop.runtime = MagicMock()
        mock_app.loop.runtime.session = MagicMock()
        mock_app.loop.runtime.session.is_connected = False

        with mock_patch("ui.metacmd.connect.console") as mock_console:
            disconnect(mock_app, [])

            mock_console.print.assert_called_with("[yellow]Not connected to any database[/yellow]")

    def test_disconnect_success(self, mock_app):
        """Test successful disconnect."""
        from loop.neoloop import NeoLoop

        mock_app.loop = MagicMock(spec=NeoLoop)
        mock_app.loop.runtime = MagicMock()
        mock_app.loop.runtime.session = MagicMock()
        mock_app.loop.runtime.session.is_connected = True
        mock_app.loop.runtime.session.db_connection = ConnectionContext(display_name="test_db")
        mock_app.prompt_session = MagicMock()

        with (
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            disconnect(mock_app, [])

            mock_app.loop.runtime.session.disconnect.assert_called_once()
            assert mock_app._db_service is None
            assert mock_app._query_history is None
            mock_app.prompt_session.refresh_db_service.assert_called_once_with(None)
            mock_console.print.assert_called()
            mock_logger.info.assert_called_once()

    def test_disconnect_no_prompt_session(self, mock_app):
        """Test disconnect when prompt_session is None."""
        from loop.neoloop import NeoLoop

        mock_app.loop = MagicMock(spec=NeoLoop)
        mock_app.loop.runtime = MagicMock()
        mock_app.loop.runtime.session = MagicMock()
        mock_app.loop.runtime.session.is_connected = True
        mock_app.loop.runtime.session.db_connection = ConnectionContext(display_name="test_db")
        mock_app.prompt_session = None

        with (
            mock_patch("ui.metacmd.connect.console") as mock_console,
            mock_patch("ui.metacmd.connect.logger") as mock_logger,
        ):
            # Should not raise an error
            disconnect(mock_app, [])

            mock_app.loop.runtime.session.disconnect.assert_called_once()
            assert mock_app._db_service is None
            assert mock_app._query_history is None
