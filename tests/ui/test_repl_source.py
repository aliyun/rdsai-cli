"""Tests for SOURCE command integration in ShellREPL."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from database import DatabaseService, QueryResult, QueryType, QueryStatus
from database.errors import DatabaseError
from loop import Loop
from ui.repl import ShellREPL


class TestShellREPLSourceIntegration:
    """Tests for SOURCE command integration in ShellREPL."""

    @pytest.fixture
    def mock_loop(self):
        """Create a mock Loop."""
        return MagicMock(spec=Loop)

    @pytest.fixture
    def mock_db_service(self):
        """Create a mock DatabaseService."""
        service = MagicMock(spec=DatabaseService)
        service.is_connected.return_value = True
        service.is_transaction_control_statement.return_value = (False, None)
        service.has_vertical_format_directive.return_value = False
        # Add the callback attribute
        service._source_display_callback = None
        return service

    @pytest.fixture
    def mock_query_history(self):
        """Create a mock QueryHistory."""
        return MagicMock()

    def test_setup_source_callback_on_init(self, mock_loop, mock_db_service):
        """Test that SOURCE callback is set up during ShellREPL initialization."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service)

        # Verify callback was set
        mock_db_service.set_source_display_callback.assert_called_once()

        # Get the callback that was passed
        callback = mock_db_service.set_source_display_callback.call_args[0][0]
        assert callback is not None
        assert callable(callback)

    def test_setup_source_callback_no_db_service(self, mock_loop):
        """Test that callback setup is skipped when no db_service."""
        repl = ShellREPL(mock_loop)

        # Should not raise any error
        assert repl._db_service is None

    def test_execute_sql_source_command_success(self, mock_loop, mock_db_service, mock_query_history):
        """Test executing SOURCE command with successful execution."""
        # Mock SOURCE command result
        source_result = QueryResult(
            query_type=QueryType.SOURCE,
            success=True,
            rows=[],
            affected_rows=2,
            execution_time=0.05,
            error=None,
        )
        mock_db_service.execute_query.return_value = source_result

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        with (
            patch("ui.repl.format_and_display_result") as mock_format,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SOURCE test.sql")

            # SOURCE command should be executed
            mock_db_service.execute_query.assert_called_once_with("SOURCE test.sql")

            # For successful SOURCE commands (success=True, error=None),
            # format_and_display_result should not be called
            # (statements are displayed via callback during execution)
            # The condition `if not result.success and result.error` evaluates to False
            mock_format.assert_not_called()

            # Context and history should be saved
            assert mock_db_service.set_last_query_context.called
            mock_query_history.record_query.assert_called_once()

    def test_execute_sql_source_command_file_error(self, mock_loop, mock_db_service, mock_query_history):
        """Test executing SOURCE command with file-level error."""
        # Mock SOURCE command result with file-level error
        # Using MySQL-style error message format
        source_result = QueryResult(
            query_type=QueryType.SOURCE,
            success=False,
            rows=[],
            execution_time=0.0,
            error="Failed to open file '/nonexistent/file.sql', error: No such file",
        )
        mock_db_service.execute_query.return_value = source_result

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        with (
            patch("ui.repl.format_and_display_result") as mock_format,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SOURCE /nonexistent/file.sql")

            # File-level error should be displayed
            mock_format.assert_called_once()

            # Context and history should be saved
            assert mock_db_service.set_last_query_context.called
            mock_query_history.record_query.assert_called_once()

    def test_execute_sql_source_command_statement_error(self, mock_loop, mock_db_service, mock_query_history):
        """Test executing SOURCE command with statement-level errors."""
        # Mock SOURCE command result with statement-level errors
        # Statement-level errors don't contain "not found", "Usage:", or "permission"
        source_result = QueryResult(
            query_type=QueryType.SOURCE,
            success=False,
            rows=[],
            execution_time=0.05,
            error="Statement 2/3: Table 'test' doesn't exist",
        )
        mock_db_service.execute_query.return_value = source_result

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        with (
            patch("ui.repl.format_and_display_result") as mock_format,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SOURCE test.sql")

            # Statement-level errors should not trigger format_and_display_result
            # (they are displayed via callback during execution, and _is_file_level_error returns False)
            # The error "Statement 2/3: Table 'test' doesn't exist" doesn't match file-level error patterns
            mock_format.assert_not_called()

            # Context and history should still be saved
            assert mock_db_service.set_last_query_context.called
            mock_query_history.record_query.assert_called_once()

    def test_execute_sql_normal_query(self, mock_loop, mock_db_service, mock_query_history):
        """Test that normal queries still work correctly."""
        normal_result = QueryResult(
            query_type=QueryType.SELECT,
            success=True,
            columns=["id"],
            rows=[[1]],
            affected_rows=None,
            execution_time=0.01,
        )
        mock_db_service.execute_query.return_value = normal_result

        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        with (
            patch("ui.repl.format_and_display_result") as mock_format,
            patch("database.service.get_service") as mock_get_service,
        ):
            mock_get_service.return_value = mock_db_service
            repl._execute_sql("SELECT * FROM users")

            # Normal query should be formatted
            mock_format.assert_called_once()

            # Context and history should be saved
            assert mock_db_service.set_last_query_context.called
            mock_query_history.record_query.assert_called_once()

    def test_save_query_context_and_history_success(self, mock_loop, mock_db_service, mock_query_history):
        """Test _save_query_context_and_history with successful result."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        result = QueryResult(
            query_type=QueryType.SELECT,
            success=True,
            columns=["id", "name"],
            rows=[[1, "test"]],
            affected_rows=None,
            execution_time=0.01,
        )

        with patch("database.service.get_service") as mock_get_service:
            mock_get_service.return_value = mock_db_service
            repl._save_query_context_and_history("SELECT * FROM users", result=result)

            # Verify context was saved with success status
            mock_db_service.set_last_query_context.assert_called_once()
            call_args = mock_db_service.set_last_query_context.call_args
            assert call_args[1]["status"] == QueryStatus.SUCCESS
            assert call_args[1]["sql"] == "SELECT * FROM users"

            # Verify history was recorded
            mock_query_history.record_query.assert_called_once()
            history_call = mock_query_history.record_query.call_args
            # Check that sql was passed (either positional or keyword)
            call_str = str(history_call)
            assert "SELECT * FROM users" in call_str
            # Check that status is success (either positional or keyword)
            assert "success" in call_str.lower()

    def test_save_query_context_and_history_error(self, mock_loop, mock_db_service, mock_query_history):
        """Test _save_query_context_and_history with error."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        result = QueryResult(
            query_type=QueryType.SELECT,
            success=False,
            rows=[],
            error="Table not found",
            execution_time=0.0,
        )

        with patch("database.service.get_service") as mock_get_service:
            mock_get_service.return_value = mock_db_service
            repl._save_query_context_and_history("SELECT * FROM invalid", result=result)

            # Verify context was saved with error status
            mock_db_service.set_last_query_context.assert_called_once()
            call_args = mock_db_service.set_last_query_context.call_args
            assert call_args[1]["status"] == QueryStatus.ERROR
            assert call_args[1]["error_message"] == "Table not found"

            # Verify history was recorded with error
            mock_query_history.record_query.assert_called_once()
            history_call = mock_query_history.record_query.call_args
            assert history_call[1]["status"] == "error"

    def test_save_query_context_and_history_exception(self, mock_loop, mock_db_service, mock_query_history):
        """Test _save_query_context_and_history with exception."""
        repl = ShellREPL(mock_loop, db_service=mock_db_service, query_history=mock_query_history)

        error = DatabaseError("Connection failed")

        with patch("database.service.get_service") as mock_get_service:
            mock_get_service.return_value = mock_db_service
            repl._save_query_context_and_history("SELECT * FROM users", error=error)

            # Verify context was saved with error status
            mock_db_service.set_last_query_context.assert_called_once()
            call_args = mock_db_service.set_last_query_context.call_args
            assert call_args[1]["status"] == QueryStatus.ERROR
            assert call_args[1]["error_message"] == "Connection failed"

            # Verify history was recorded with error
            mock_query_history.record_query.assert_called_once()
            history_call = mock_query_history.record_query.call_args
            # Check that sql and error were passed
            call_str = str(history_call)
            assert "SELECT * FROM users" in call_str
            assert "error" in call_str.lower()
            assert "Connection failed" in call_str

    def test_execute_sql_source_callback_invoked(self, mock_loop, mock_db_service):
        """Test that SOURCE callback is invoked during script execution."""
        # Create a temporary SQL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("INSERT INTO test VALUES (1);\n")
            temp_file = Path(f.name)

        try:
            # Set up callback tracking
            callback_calls = []

            def test_callback(result, stmt, use_vertical):
                callback_calls.append((result, stmt, use_vertical))

            mock_db_service._source_display_callback = test_callback

            # Mock the actual script execution
            def mock_execute_query(sql):
                if sql.strip().upper().startswith("SOURCE"):
                    # Simulate script execution with callback
                    if mock_db_service._source_display_callback:
                        stmt_result = QueryResult(
                            query_type=QueryType.INSERT,
                            success=True,
                            rows=[],
                            affected_rows=1,
                            execution_time=0.01,
                        )
                        mock_db_service._source_display_callback(stmt_result, "INSERT INTO test VALUES (1)", False)

                    return QueryResult(
                        query_type=QueryType.SOURCE,
                        success=True,
                        rows=[],
                        affected_rows=1,
                        execution_time=0.02,
                    )
                return QueryResult(
                    query_type=QueryType.OTHER,
                    success=True,
                    rows=[],
                )

            mock_db_service.execute_query.side_effect = mock_execute_query

            repl = ShellREPL(mock_loop, db_service=mock_db_service)

            with patch("database.service.get_service") as mock_get_service:
                mock_get_service.return_value = mock_db_service
                repl._execute_sql(f"SOURCE {temp_file}")

                # Callback should have been called
                assert len(callback_calls) == 1
                assert callback_calls[0][0].query_type == QueryType.INSERT
                assert callback_calls[0][1] == "INSERT INTO test VALUES (1)"

        finally:
            temp_file.unlink()
