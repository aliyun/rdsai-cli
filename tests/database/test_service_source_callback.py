"""Tests for SOURCE command display callback mechanism in DatabaseService."""

from unittest.mock import MagicMock
from pathlib import Path
import tempfile

from database.service import DatabaseService
from database.types import QueryResult, QueryType


class TestSourceDisplayCallback:
    """Tests for SOURCE command display callback mechanism."""

    def test_set_source_display_callback(self):
        """Test setting SOURCE display callback."""
        service = DatabaseService()
        callback = MagicMock()

        service.set_source_display_callback(callback)

        assert service._source_display_callback is callback

    def test_set_source_display_callback_none(self):
        """Test setting callback to None clears it."""
        service = DatabaseService()
        callback = MagicMock()

        service.set_source_display_callback(callback)
        assert service._source_display_callback is callback

        service.set_source_display_callback(None)
        assert service._source_display_callback is None

    def test_clear_source_display_callback(self):
        """Test clearing SOURCE display callback."""
        service = DatabaseService()
        callback = MagicMock()

        service.set_source_display_callback(callback)
        assert service._source_display_callback is callback

        service.clear_source_display_callback()
        assert service._source_display_callback is None

    def test_execute_source_command_with_callback(self):
        """Test SOURCE command execution calls callback for each statement."""
        service = DatabaseService()
        callback = MagicMock()
        service.set_source_display_callback(callback)

        # Create a temporary SQL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("INSERT INTO test VALUES (1);\n")
            f.write("INSERT INTO test VALUES (2);\n")
            f.write("SELECT * FROM test;\n")
            temp_file = Path(f.name)

        try:
            # Mock the client for executing statements
            mock_client = MagicMock()
            mock_client.execute.return_value = None
            mock_client.get_row_count.return_value = 1
            mock_client.fetchall.return_value = [(1,), (2,)]
            mock_client.get_columns.return_value = ["id"]
            service._active_connection = mock_client

            # Mock execute_query to avoid recursion
            original_execute_query = service.execute_query

            def mock_execute_query(sql: str):
                if sql.strip().upper().startswith("SOURCE"):
                    return original_execute_query(sql)
                # For individual statements, return a simple result
                return QueryResult(
                    query_type=QueryType.INSERT if "INSERT" in sql.upper() else QueryType.SELECT,
                    success=True,
                    rows=[(1,), (2,)] if "SELECT" in sql.upper() else [],
                    columns=["id"] if "SELECT" in sql.upper() else None,
                    affected_rows=1 if "INSERT" in sql.upper() else None,
                    execution_time=0.01,
                )

            service.execute_query = mock_execute_query

            result = service._execute_source_command(f"SOURCE {temp_file}")

            # Callback should be called for each statement (3 statements)
            assert callback.call_count == 3

            # Verify callback was called with correct arguments
            for call_args in callback.call_args_list:
                args, kwargs = call_args
                assert len(args) == 3
                assert isinstance(args[0], QueryResult)
                assert isinstance(args[1], str)
                assert isinstance(args[2], bool)

            assert result.query_type == QueryType.SOURCE
            assert result.success is True

        finally:
            # Cleanup
            temp_file.unlink()
            service.clear_source_display_callback()

    def test_execute_source_command_without_callback(self):
        """Test SOURCE command execution without callback."""
        service = DatabaseService()

        # Create a temporary SQL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("INSERT INTO test VALUES (1);\n")
            temp_file = Path(f.name)

        try:
            # Mock the client
            mock_client = MagicMock()
            mock_client.execute.return_value = None
            mock_client.get_row_count.return_value = 1
            service._active_connection = mock_client

            # Mock execute_query
            original_execute_query = service.execute_query

            def mock_execute_query(sql: str):
                if sql.strip().upper().startswith("SOURCE"):
                    return original_execute_query(sql)
                return QueryResult(
                    query_type=QueryType.INSERT,
                    success=True,
                    rows=[],
                    affected_rows=1,
                    execution_time=0.01,
                )

            service.execute_query = mock_execute_query

            result = service._execute_source_command(f"SOURCE {temp_file}")

            # Should execute successfully without callback
            assert result.query_type == QueryType.SOURCE
            assert result.success is True

        finally:
            temp_file.unlink()

    def test_execute_source_command_file_not_found(self):
        """Test SOURCE command with file not found error."""
        service = DatabaseService()
        callback = MagicMock()
        service.set_source_display_callback(callback)

        result = service._execute_source_command("SOURCE /nonexistent/file.sql")

        # Callback should not be called for file-level errors
        callback.assert_not_called()

        assert result.query_type == QueryType.SOURCE
        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error.lower() or "No such file" in result.error

    def test_execute_source_command_empty_file(self):
        """Test SOURCE command with empty file."""
        service = DatabaseService()
        callback = MagicMock()
        service.set_source_display_callback(callback)

        # Create an empty temporary SQL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            temp_file = Path(f.name)

        try:
            result = service._execute_source_command(f"SOURCE {temp_file}")

            # Callback should not be called for empty files
            callback.assert_not_called()

            assert result.query_type == QueryType.SOURCE
            assert result.success is True
            assert "No statements found" in result.error

        finally:
            temp_file.unlink()
            service.clear_source_display_callback()

    def test_execute_source_command_statement_error(self):
        """Test SOURCE command with statement-level error."""
        service = DatabaseService()
        callback = MagicMock()
        service.set_source_display_callback(callback)

        # Create a temporary SQL file with invalid statement
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write("INSERT INTO test VALUES (1);\n")
            f.write("SELECT * FROM nonexistent_table;\n")
            temp_file = Path(f.name)

        try:
            mock_client = MagicMock()
            service._active_connection = mock_client

            # Mock execute_query to simulate error on second statement
            call_count = [0]

            def mock_execute_query(sql: str):
                if sql.strip().upper().startswith("SOURCE"):
                    return service._execute_source_command(sql)
                call_count[0] += 1
                if call_count[0] == 1:
                    # First statement succeeds
                    return QueryResult(
                        query_type=QueryType.INSERT,
                        success=True,
                        rows=[],
                        affected_rows=1,
                        execution_time=0.01,
                    )
                else:
                    # Second statement fails
                    return QueryResult(
                        query_type=QueryType.SELECT,
                        success=False,
                        rows=[],
                        error="Table 'nonexistent_table' doesn't exist",
                        execution_time=0.0,
                    )

            service.execute_query = mock_execute_query

            result = service._execute_source_command(f"SOURCE {temp_file}")

            # Callback should be called for both statements (even failed ones)
            assert callback.call_count == 2

            # First call should be successful
            first_call_result = callback.call_args_list[0][0][0]
            assert first_call_result.success is True

            # Second call should be failed
            second_call_result = callback.call_args_list[1][0][0]
            assert second_call_result.success is False

            # Overall result should indicate failure
            assert result.query_type == QueryType.SOURCE
            assert result.success is False

        finally:
            temp_file.unlink()
            service.clear_source_display_callback()
