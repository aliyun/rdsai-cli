"""Tests for ui.repl module - core REPL functionality."""

from unittest.mock import MagicMock, patch

import pytest

from database import DatabaseError, QueryResult, QueryType, TransactionState
from loop import Loop, NeoLoop
from loop.runtime import Runtime
from ui.repl import ShellREPL, WelcomeInfoItem


class TestShellREPL:
    """Tests for ShellREPL core methods."""

    @pytest.fixture
    def mock_loop(self):
        """Create a mock Loop."""
        return MagicMock(spec=Loop)

    @pytest.fixture
    def mock_neoloop(self):
        """Create a mock NeoLoop."""
        loop = MagicMock(spec=NeoLoop)
        loop.runtime = MagicMock(spec=Runtime)
        loop.runtime.llm = MagicMock()
        loop.runtime.llm.model_name = "test-model"
        return loop

    @pytest.fixture
    def mock_db_service(self):
        """Create a mock DatabaseService."""
        service = MagicMock()
        service.is_connected.return_value = True
        service.get_transaction_state.return_value = TransactionState.NOT_IN_TRANSACTION
        return service

    @pytest.fixture
    def mock_query_history(self):
        """Create a mock QueryHistory."""
        return MagicMock()

    def test_llm_configured_with_neoloop(self, mock_neoloop):
        """Test llm_configured property with NeoLoop."""
        repl = ShellREPL(mock_neoloop)
        assert repl.llm_configured is True

    def test_llm_configured_without_llm(self, mock_loop):
        """Test llm_configured property without LLM."""
        repl = ShellREPL(mock_loop)
        assert repl.llm_configured is False

    def test_llm_configured_with_empty_model_name(self, mock_neoloop):
        """Test llm_configured property with empty model name."""
        mock_neoloop.runtime.llm.model_name = ""
        repl = ShellREPL(mock_neoloop)
        assert repl.llm_configured is False

    def test_db_connected(self, mock_loop, mock_db_service):
        """Test db_connected property."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        assert repl.db_connected is True

    def test_db_connected_no_service(self, mock_loop):
        """Test db_connected property without service."""
        repl = ShellREPL(mock_loop)
        assert repl.db_connected is False

    def test_db_connected_not_connected(self, mock_loop, mock_db_service):
        """Test db_connected property when not connected."""
        mock_db_service.is_connected.return_value = False
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        assert repl.db_connected is False

    def test_execute_sql_no_connection(self, mock_loop):
        """Test _execute_sql when database is not connected."""
        repl = ShellREPL(mock_loop)
        with patch("ui.repl.console") as mock_console:
            repl._execute_sql("SELECT 1")
            mock_console.print.assert_called_once_with("[red]No database connection. Use /connect to connect.[/red]")

    def test_execute_sql_transaction_control_begin(self, mock_loop, mock_db_service):
        """Test _execute_sql with BEGIN transaction."""
        mock_db_service.is_transaction_control_statement.return_value = (True, QueryType.BEGIN)
        mock_db_service.get_transaction_state.return_value = TransactionState.NOT_IN_TRANSACTION

        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            repl._execute_sql("BEGIN")
            mock_db_service.begin_transaction.assert_called_once()
            mock_console.print.assert_called_with("[green]Transaction started[/green]")

    def test_execute_sql_transaction_control_commit(self, mock_loop, mock_db_service):
        """Test _execute_sql with COMMIT transaction."""
        mock_db_service.is_transaction_control_statement.return_value = (True, QueryType.COMMIT)
        mock_db_service.get_transaction_state.return_value = TransactionState.IN_TRANSACTION

        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            repl._execute_sql("COMMIT")
            mock_db_service.commit_transaction.assert_called_once()
            mock_console.print.assert_called_with("[green]Transaction committed[/green]")

    def test_execute_sql_transaction_control_rollback(self, mock_loop, mock_db_service):
        """Test _execute_sql with ROLLBACK transaction."""
        mock_db_service.is_transaction_control_statement.return_value = (True, QueryType.ROLLBACK)
        mock_db_service.get_transaction_state.return_value = TransactionState.IN_TRANSACTION

        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            repl._execute_sql("ROLLBACK")
            mock_db_service.rollback_transaction.assert_called_once()
            mock_console.print.assert_called_with("[green]Transaction rolled back[/green]")

    def test_execute_sql_success(self, mock_loop, mock_db_service, mock_query_history):
        """Test _execute_sql with successful query."""
        mock_db_service.is_transaction_control_statement.return_value = (False, None)
        mock_db_service.has_vertical_format_directive.return_value = False
        mock_result = QueryResult(
            query_type=QueryType.SELECT,
            success=True,
            columns=["id", "name"],
            rows=[[1, "test"]],
            affected_rows=1,
            execution_time=0.1,
            error=None,
        )
        mock_db_service.execute_query.return_value = mock_result

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)
        with (
            patch("ui.formatters.database_formatter.format_and_display_result") as mock_format,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SELECT * FROM users")

            mock_format.assert_called_once()
            mock_query_history.record_query.assert_called_once()
            assert mock_db_service.set_last_query_context.called

    def test_execute_sql_error(self, mock_loop, mock_db_service, mock_query_history):
        """Test _execute_sql with query error."""
        mock_db_service.is_transaction_control_statement.return_value = (False, None)
        mock_db_service.has_vertical_format_directive.return_value = False
        mock_result = QueryResult(
            query_type=QueryType.SELECT,
            success=False,
            rows=[],
            error="Table not found",
            execution_time=0.0,
            affected_rows=0,
        )
        mock_db_service.execute_query.return_value = mock_result

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)
        with (
            patch("ui.formatters.database_formatter.format_and_display_result") as mock_format,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SELECT * FROM nonexistent")

            mock_format.assert_called_once()
            mock_query_history.record_query.assert_called_once()
            assert mock_db_service.set_last_query_context.called

    def test_execute_sql_database_error(self, mock_loop, mock_db_service, mock_query_history):
        """Test _execute_sql with DatabaseError."""
        mock_db_service.is_transaction_control_statement.return_value = (False, None)
        mock_db_service.has_vertical_format_directive.return_value = False
        mock_db_service.execute_query.side_effect = DatabaseError("Connection failed")

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)
        with (
            patch("ui.formatters.database_formatter.display_database_error") as mock_display,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SELECT * FROM users")

            mock_display.assert_called_once()
            mock_query_history.record_query.assert_called_once()

    def test_handle_transaction_control_begin_already_in_transaction(self, mock_loop, mock_db_service):
        """Test _handle_transaction_control with BEGIN when already in transaction."""
        mock_db_service.get_transaction_state.return_value = TransactionState.IN_TRANSACTION

        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            repl._handle_transaction_control(QueryType.BEGIN)
            mock_console.print.assert_called_with("[yellow]Warning: Already in transaction[/yellow]")
            mock_db_service.begin_transaction.assert_not_called()

    def test_handle_transaction_control_commit_no_transaction(self, mock_loop, mock_db_service):
        """Test _handle_transaction_control with COMMIT when no transaction."""
        mock_db_service.get_transaction_state.return_value = TransactionState.NOT_IN_TRANSACTION

        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            repl._handle_transaction_control(QueryType.COMMIT)
            mock_console.print.assert_called_with("[yellow]Warning: No transaction in progress[/yellow]")
            mock_db_service.commit_transaction.assert_not_called()

    def test_handle_transaction_control_rollback_no_transaction(self, mock_loop, mock_db_service):
        """Test _handle_transaction_control with ROLLBACK when no transaction."""
        mock_db_service.get_transaction_state.return_value = TransactionState.NOT_IN_TRANSACTION

        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            repl._handle_transaction_control(QueryType.ROLLBACK)
            mock_console.print.assert_called_with("[yellow]Warning: No transaction in progress[/yellow]")
            mock_db_service.rollback_transaction.assert_not_called()

    def test_check_uncommitted_transaction_no_service(self, mock_loop):
        """Test _check_uncommitted_transaction without database service."""
        repl = ShellREPL(mock_loop)
        assert repl._check_uncommitted_transaction() is False

    def test_check_uncommitted_transaction_not_connected(self, mock_loop, mock_db_service):
        """Test _check_uncommitted_transaction when not connected."""
        mock_db_service.is_connected.return_value = False
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        assert repl._check_uncommitted_transaction() is False

    def test_check_uncommitted_transaction_no_transaction(self, mock_loop, mock_db_service):
        """Test _check_uncommitted_transaction when no transaction."""
        mock_db_service.get_transaction_state.return_value = TransactionState.NOT_IN_TRANSACTION
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        assert repl._check_uncommitted_transaction() is False

    def test_check_uncommitted_transaction_first_warning(self, mock_loop, mock_db_service):
        """Test _check_uncommitted_transaction first warning."""
        mock_db_service.get_transaction_state.return_value = TransactionState.IN_TRANSACTION
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.console") as mock_console:
            result = repl._check_uncommitted_transaction()
            assert result is True
            assert repl._exit_warned is True
            assert mock_console.print.call_count == 2

    def test_check_uncommitted_transaction_already_warned(self, mock_loop, mock_db_service):
        """Test _check_uncommitted_transaction when already warned."""
        mock_db_service.get_transaction_state.return_value = TransactionState.IN_TRANSACTION
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        repl._exit_warned = True
        with patch("ui.repl.console") as mock_console:
            result = repl._check_uncommitted_transaction()
            assert result is False
            mock_console.print.assert_called_with("[yellow]Uncommitted transaction will be lost.[/yellow]")

    def test_try_backslash_command_handled(self, mock_loop, mock_db_service):
        """Test _try_backslash_command with handled command."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        mock_result = MagicMock()
        mock_result.should_continue = True

        with patch("ui.repl.execute_backslash_command") as mock_execute:
            mock_execute.return_value = (True, mock_result)
            handled, should_exit = repl._try_backslash_command("\\s")
            assert handled is True
            assert should_exit is False

    def test_try_backslash_command_exit(self, mock_loop, mock_db_service):
        """Test _try_backslash_command with exit command."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        mock_result = MagicMock()
        mock_result.should_continue = False

        with patch("ui.repl.execute_backslash_command") as mock_execute:
            mock_execute.return_value = (True, mock_result)
            handled, should_exit = repl._try_backslash_command("\\q")
            assert handled is True
            assert should_exit is True

    def test_try_backslash_command_not_handled(self, mock_loop, mock_db_service):
        """Test _try_backslash_command with unhandled command."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service)
        with patch("ui.repl.execute_backslash_command") as mock_execute:
            mock_execute.return_value = (False, None)
            handled, should_exit = repl._try_backslash_command("SELECT 1")
            assert handled is False
            assert should_exit is False


class TestWelcomeInfoItem:
    """Tests for WelcomeInfoItem dataclass."""

    def test_welcome_info_item_init(self):
        """Test WelcomeInfoItem initialization."""
        item = WelcomeInfoItem(name="Test", value="Value", level=WelcomeInfoItem.Level.INFO)
        assert item.name == "Test"
        assert item.value == "Value"
        assert item.level == WelcomeInfoItem.Level.INFO

    def test_welcome_info_item_default_level(self):
        """Test WelcomeInfoItem with default level."""
        item = WelcomeInfoItem(name="Test", value="Value")
        assert item.level == WelcomeInfoItem.Level.INFO
