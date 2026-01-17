"""Tests for ui.metacmd.explain module - SQL execution plan analysis."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import QueryResult, QueryType
from loop import NeoLoop, RunCancelled
from loop.runtime import Runtime
from ui.metacmd.explain import _format_explain_result, explain


class TestFormatExplainResult:
    """Tests for _format_explain_result function."""

    def test_format_explain_result_empty_rows(self):
        """Test formatting with empty rows."""
        result = _format_explain_result(["id", "table", "type"], [])
        assert result == "No execution plan data."

    def test_format_explain_result_single_row(self):
        """Test formatting with single row."""
        columns = ["id", "select_type", "table", "type", "key", "rows"]
        rows = [[1, "SIMPLE", "users", "ref", "PRIMARY", 1]]
        result = _format_explain_result(columns, rows)

        assert "id" in result
        assert "select_type" in result
        assert "SIMPLE" in result
        assert "users" in result
        assert "ref" in result
        assert "PRIMARY" in result
        assert "1" in result
        assert result.count("|") > 0  # Should contain table separators

    def test_format_explain_result_multiple_rows(self):
        """Test formatting with multiple rows."""
        columns = ["id", "table", "type"]
        rows = [
            [1, "users", "ref"],
            [2, "orders", "ALL"],
        ]
        result = _format_explain_result(columns, rows)

        assert "users" in result
        assert "orders" in result
        assert "ref" in result
        assert "ALL" in result
        # Should have header, separator, and 2 data rows
        lines = result.split("\n")
        assert len(lines) >= 3

    def test_format_explain_result_with_none_values(self):
        """Test formatting with None values."""
        columns = ["id", "table", "key"]
        rows = [[1, "users", None]]
        result = _format_explain_result(columns, rows)

        assert "NULL" in result
        assert "users" in result

    def test_format_explain_result_markdown_format(self):
        """Test that result is in Markdown table format."""
        columns = ["id", "table"]
        rows = [[1, "users"]]
        result = _format_explain_result(columns, rows)

        # Should have header row
        assert result.startswith("|")
        # Should have separator row with ---
        assert "---" in result
        # Should have data row
        assert "1" in result
        assert "users" in result


class TestExplainCommand:
    """Tests for explain command."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ShellREPL app."""
        app = MagicMock()
        app.db_service = MagicMock()
        app.db_service.is_connected.return_value = True
        app.db_service.execute_query = MagicMock()
        app.loop = MagicMock(spec=NeoLoop)
        app.loop.runtime = MagicMock(spec=Runtime)
        app.loop.runtime.llm = MagicMock()
        app.loop.runtime.llm.model_name = "test-model"
        app.loop.status = MagicMock()
        return app

    @pytest.mark.asyncio
    async def test_explain_no_args(self, mock_app):
        """Test explain command with no arguments."""
        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, [])
            mock_console.print.assert_any_call("[yellow]Usage: /explain <sql>[/yellow]")
            mock_console.print.assert_any_call("[dim]Example: /explain SELECT * FROM users WHERE id = xxx[/dim]")

    @pytest.mark.asyncio
    async def test_explain_no_database_connection(self, mock_app):
        """Test explain command when database is not connected."""
        mock_app.db_service.is_connected.return_value = False

        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, ["SELECT * FROM users"])
            mock_console.print.assert_any_call("[red]✗[/red] Not connected to a database.")
            mock_console.print.assert_any_call("[dim]Use /connect to connect to a database first.[/dim]")

    @pytest.mark.asyncio
    async def test_explain_no_db_service(self, mock_app):
        """Test explain command when db_service is None."""
        mock_app.db_service = None

        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, ["SELECT * FROM users"])
            mock_console.print.assert_any_call("[red]✗[/red] Not connected to a database.")

    @pytest.mark.asyncio
    async def test_explain_not_neoloop(self, mock_app):
        """Test explain command when loop is not NeoLoop."""
        mock_app.loop = MagicMock()  # Not NeoLoop

        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, ["SELECT * FROM users"])
            mock_console.print.assert_any_call("[red]✗[/red] Explain requires agent loop.")

    @pytest.mark.asyncio
    async def test_explain_no_llm(self, mock_app):
        """Test explain command when LLM is not configured."""
        mock_app.loop.runtime.llm = None

        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, ["SELECT * FROM users"])
            mock_console.print.assert_any_call("[red]✗[/red] LLM not configured.")
            mock_console.print.assert_any_call("[dim]Use /setup to configure an LLM model.[/dim]")

    @pytest.mark.asyncio
    async def test_explain_execute_query_failure(self, mock_app):
        """Test explain command when EXPLAIN execution fails."""
        error_result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=False,
            rows=[],
            error="Syntax error",
        )
        mock_app.db_service.execute_query.return_value = error_result

        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, ["SELECT * FROM users"])
            mock_console.print.assert_any_call("[red]✗[/red] Failed to execute EXPLAIN: Syntax error")

    @pytest.mark.asyncio
    async def test_explain_no_execution_plan_data(self, mock_app):
        """Test explain command when no execution plan data is returned."""
        result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=True,
            rows=[],
            columns=None,
        )
        mock_app.db_service.execute_query.return_value = result

        with patch("ui.metacmd.explain.console") as mock_console:
            await explain(mock_app, ["SELECT * FROM users"])
            mock_console.print.assert_any_call("[yellow]No execution plan data returned.[/yellow]")

    @pytest.mark.asyncio
    async def test_explain_execute_query_exception(self, mock_app):
        """Test explain command when execute_query raises an exception."""
        mock_app.db_service.execute_query.side_effect = Exception("Database error")

        with (
            patch("ui.metacmd.explain.console") as mock_console,
            patch("ui.metacmd.explain.logger") as mock_logger,
        ):
            await explain(mock_app, ["SELECT * FROM users"])
            mock_logger.exception.assert_called_once_with("Failed to execute EXPLAIN")
            mock_console.print.assert_any_call("[red]✗[/red] Failed to execute EXPLAIN: Database error")

    @pytest.mark.asyncio
    async def test_explain_success(self, mock_app):
        """Test explain command with successful execution."""
        columns = ["id", "select_type", "table", "type", "key", "rows"]
        rows = [[1, "SIMPLE", "users", "ref", "PRIMARY", 1]]
        result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=True,
            rows=rows,
            columns=columns,
        )
        mock_app.db_service.execute_query.return_value = result

        with (
            patch("ui.metacmd.explain.console") as mock_console,
            patch("ui.metacmd.explain.run_loop", new_callable=AsyncMock) as mock_run_loop,
            patch("ui.metacmd.explain.visualize") as mock_visualize,
            patch("ui.metacmd.explain.asyncio.Event") as mock_event,
        ):
            mock_event.return_value = MagicMock()
            await explain(mock_app, ["SELECT * FROM users WHERE id = 1"])

            # Verify EXPLAIN was called with correct SQL
            mock_app.db_service.execute_query.assert_called_once_with("EXPLAIN SELECT * FROM users WHERE id = 1")

            # Verify run_loop was called
            mock_run_loop.assert_called_once()
            call_args = mock_run_loop.call_args
            assert call_args[0][0] == mock_app.loop  # First arg is loop
            assert "SELECT * FROM users WHERE id = 1" in call_args[0][1]  # Prompt contains SQL
            assert "Execution Plan" in call_args[0][1]  # Prompt contains execution plan

            # Verify console messages
            mock_console.print.assert_any_call("[cyan]Analyzing execution plan...[/cyan]")
            mock_console.print.assert_any_call("[green]✓[/green] Execution plan analysis completed.")

    @pytest.mark.asyncio
    async def test_explain_success_multiple_args(self, mock_app):
        """Test explain command with SQL split across multiple arguments."""
        columns = ["id", "table", "type"]
        rows = [[1, "users", "ref"]]
        result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=True,
            rows=rows,
            columns=columns,
        )
        mock_app.db_service.execute_query.return_value = result

        with (
            patch("ui.metacmd.explain.console") as mock_console,
            patch("ui.metacmd.explain.run_loop", new_callable=AsyncMock) as mock_run_loop,
            patch("ui.metacmd.explain.asyncio.Event") as mock_event,
        ):
            mock_event.return_value = MagicMock()
            await explain(mock_app, ["SELECT", "*", "FROM", "users", "WHERE", "id", "=", "1"])

            # Verify SQL was combined correctly
            mock_app.db_service.execute_query.assert_called_once_with("EXPLAIN SELECT * FROM users WHERE id = 1")
            mock_run_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_explain_cancelled(self, mock_app):
        """Test explain command when user cancels."""
        columns = ["id", "table", "type"]
        rows = [[1, "users", "ref"]]
        result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=True,
            rows=rows,
            columns=columns,
        )
        mock_app.db_service.execute_query.return_value = result

        with (
            patch("ui.metacmd.explain.console") as mock_console,
            patch("ui.metacmd.explain.run_loop", new_callable=AsyncMock) as mock_run_loop,
            patch("ui.metacmd.explain.logger") as mock_logger,
            patch("ui.metacmd.explain.asyncio.Event") as mock_event,
        ):
            mock_event.return_value = MagicMock()
            mock_run_loop.side_effect = RunCancelled()

            await explain(mock_app, ["SELECT * FROM users"])

            mock_logger.info.assert_called_once_with("Explain cancelled by user")
            mock_console.print.assert_any_call("\n[yellow]Explain cancelled by user[/yellow]")

    @pytest.mark.asyncio
    async def test_explain_run_loop_exception(self, mock_app):
        """Test explain command when run_loop raises an exception."""
        columns = ["id", "table", "type"]
        rows = [[1, "users", "ref"]]
        result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=True,
            rows=rows,
            columns=columns,
        )
        mock_app.db_service.execute_query.return_value = result

        with (
            patch("ui.metacmd.explain.console") as mock_console,
            patch("ui.metacmd.explain.run_loop", new_callable=AsyncMock) as mock_run_loop,
            patch("ui.metacmd.explain.logger") as mock_logger,
            patch("ui.metacmd.explain.asyncio.Event") as mock_event,
        ):
            mock_event.return_value = MagicMock()
            mock_run_loop.side_effect = Exception("Run loop error")

            await explain(mock_app, ["SELECT * FROM users"])

            mock_logger.exception.assert_called_once_with("Explain failed")
            mock_console.print.assert_any_call("[red]✗[/red] Explain failed: Run loop error")

    @pytest.mark.asyncio
    async def test_explain_prompt_content(self, mock_app):
        """Test that the prompt contains correct content."""
        columns = ["id", "select_type", "table", "type", "key", "rows", "Extra"]
        rows = [
            [1, "SIMPLE", "users", "ref", "PRIMARY", 1, "Using index"],
        ]
        result = QueryResult(
            query_type=QueryType.EXPLAIN,
            success=True,
            rows=rows,
            columns=columns,
        )
        mock_app.db_service.execute_query.return_value = result

        with (
            patch("ui.metacmd.explain.console"),
            patch("ui.metacmd.explain.run_loop", new_callable=AsyncMock) as mock_run_loop,
            patch("ui.metacmd.explain.asyncio.Event") as mock_event,
        ):
            mock_event.return_value = MagicMock()
            sql = "SELECT * FROM users WHERE id = 1"
            await explain(mock_app, [sql])

            # Get the prompt passed to run_loop
            call_args = mock_run_loop.call_args
            prompt = call_args[0][1]

            # Verify prompt contains SQL statement
            assert sql in prompt
            assert "SQL Statement:" in prompt

            # Verify prompt contains execution plan
            assert "Execution Plan:" in prompt
            assert "id" in prompt
            assert "SIMPLE" in prompt
            assert "users" in prompt
            assert "ref" in prompt
            assert "PRIMARY" in prompt

            # Verify prompt contains analysis requirements
            assert "Key metrics analysis" in prompt
            assert "Index usage" in prompt
            assert "Scan type" in prompt
            assert "Potential performance issues" in prompt
            assert "optimization suggestions" in prompt
