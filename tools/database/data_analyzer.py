"""Data Analyzer tool for executing analytical SQL queries on MySQL and DuckDB."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from loop.toolset import BaseTool, ToolError, ToolOk, ToolReturnType
from tools.utils import ToolResultBuilder, load_desc

from database import (
    get_database_service,
    DatabaseError,
    get_error_brief,
    format_error,
)


class Params(BaseModel):
    sql: str = Field(
        description=(
            "The SQL SELECT query to execute for data analysis. "
            "This tool is designed for analytical queries that analyze data patterns, statistics, aggregations, and insights. "
            "Supports both MySQL and DuckDB engines. "
            "The model should generate appropriate SQL based on the connected database engine. "
            "Only SELECT queries (including WITH/CTE) are supported. "
            "DO NOT use for DML (INSERT/UPDATE/DELETE) or DDL (CREATE/ALTER/DROP) statements."
        )
    )


class DataAnalyzer(BaseTool[Params]):
    """Tool for executing analytical SQL queries for data analysis on MySQL and DuckDB databases."""

    name: str = "DataAnalyzer"
    description: str = load_desc(Path(__file__).parent / "data_analyzer.md")
    params: type[Params] = Params

    # Maximum rows to display in output
    MAX_DISPLAY_ROWS = 500
    # Maximum cell value length before truncation
    MAX_CELL_LENGTH = 100

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._builtin_args = builtin_args

    def _get_database_service(self):
        """Get the current database service."""
        db_service = get_database_service()
        if db_service is None:
            raise ValueError("No database connection available. Please connect to a database first.")
        return db_service

    def _is_select_query(self, sql: str) -> tuple[bool, str]:
        """Check if SQL is a SELECT query (including CTE).

        Returns:
            Tuple of (is_valid, error_message)
        """
        sql_upper = sql.strip().upper()

        # Allow WITH (CTE) and SELECT
        if sql_upper.startswith("SELECT") or sql_upper.startswith("WITH"):
            return True, ""

        # Check for common non-SELECT statements
        forbidden_prefixes = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "ALTER",
            "DROP",
            "TRUNCATE",
            "REPLACE",
            "EXPLAIN",
            "SHOW",
            "DESCRIBE",
            "DESC",
            "USE",
            "SET",
            "BEGIN",
            "COMMIT",
            "ROLLBACK",
            "GRANT",
            "REVOKE",
        ]

        for prefix in forbidden_prefixes:
            if sql_upper.startswith(prefix):
                return False, f"This tool only supports SELECT queries. Found {prefix} statement."

        return False, "This tool only supports SELECT queries (including WITH/CTE)."

    @staticmethod
    def _error_result(error: str, brief: str, sql: str = "", engine: str | None = None) -> dict[str, Any]:
        """Create a standardized error result dictionary."""
        result: dict[str, Any] = {"error": error, "brief": brief}
        if sql:
            result["sql"] = sql
        if engine:
            result["engine"] = engine
        return result

    @staticmethod
    def _format_error_message(error_msg: str, engine: str | None, sql: str, is_engine_mismatch: bool) -> str:
        """Format enhanced error message with context."""
        builder = ToolResultBuilder()
        builder.write(f"Query execution failed: {error_msg}\n\n")

        if engine:
            builder.write(f"Current engine: {engine}\n")

        if sql:
            # Truncate SQL for display
            sql_display = sql[:200] + "..." if len(sql) > 200 else sql
            builder.write(f"SQL: {sql_display}\n")

        if is_engine_mismatch and engine:
            builder.write(
                f"\nNote: This error may be due to SQL syntax not matching the {engine} engine. "
                f"Please check <database_context> for engine-specific SQL requirements.\n"
            )

        return builder.get_output()

    @staticmethod
    def _format_metadata(engine: str, execution_time: float | None, row_count: int) -> str:
        """Format query metadata."""
        builder = ToolResultBuilder()
        builder.write(f"Engine: {engine}\n")

        if execution_time:
            builder.write(f"Execution time: {execution_time:.3f}s\n")

        builder.write(f"Rows returned: {row_count}\n\n")
        return builder.get_output()

    def _format_markdown_table(self, columns: list[str], rows: list[tuple]) -> str:
        """Format query results as Markdown table with truncation."""
        builder = ToolResultBuilder()

        if not columns or not rows:
            builder.write("No data returned.\n")
            return builder.get_output()

        # Limit displayed rows
        display_rows = rows[: self.MAX_DISPLAY_ROWS]
        truncated = len(rows) > self.MAX_DISPLAY_ROWS

        # Write Markdown table header
        builder.write("| " + " | ".join(str(col) for col in columns) + " |\n")
        builder.write("| " + " | ".join("---" for _ in columns) + " |\n")

        # Write table rows with value truncation
        for row in display_rows:
            formatted_cells = []
            for cell in row:
                if cell is None:
                    formatted_cells.append("NULL")
                else:
                    cell_str = str(cell)
                    if len(cell_str) > self.MAX_CELL_LENGTH:
                        cell_str = cell_str[: self.MAX_CELL_LENGTH - 3] + "..."
                    formatted_cells.append(cell_str)
            builder.write("| " + " | ".join(formatted_cells) + " |\n")

        # Add truncation notice if needed
        if truncated:
            remaining = len(rows) - self.MAX_DISPLAY_ROWS
            builder.write(f"\n... ({remaining} more rows not shown. Total: {len(rows)} rows)\n")

        return builder.get_output()

    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute the SQL SELECT query."""
        sql = params.sql.strip()
        if not sql:
            return self._error_result("SQL statement is required", "SQL statement is required")

        # Validate SQL type
        is_valid, error_msg = self._is_select_query(sql)
        if not is_valid:
            return self._error_result(error_msg, "Invalid SQL type", sql=sql)

        # Get database service
        try:
            db_service = self._get_database_service()
        except ValueError as e:
            return self._error_result(str(e), "No database connection", sql=sql)

        # Get engine info
        conn_info = db_service.get_connection_info()
        if not conn_info.get("connected"):
            return self._error_result(
                "No database connection available. Please connect to a database first.",
                "No database connection",
                sql=sql,
            )

        engine = conn_info.get("engine")

        # Execute query
        try:
            result = db_service.execute_query(sql)
        except Exception as e:
            error_str = str(e)
            return self._error_result(
                f"Query execution failed: {error_str}",
                "Query execution error",
                sql=sql,
                engine=engine,
            )

        if not result.success:
            error_msg = result.error or "Query execution failed"
            return self._error_result(
                error_msg,
                get_error_brief(DatabaseError(error_msg)) if error_msg else "Query failed",
                sql=sql,
                engine=engine,
            )

        # Return structured result
        row_count = len(result.rows) if result.rows else 0
        return {
            "columns": result.columns or [],
            "rows": result.rows or [],
            "row_count": row_count,
            "execution_time": result.execution_time,
            "engine": engine,
            "message": (
                f"Query executed successfully on {engine}. "
                f"Returned {row_count} rows"
                + (f" (execution time: {result.execution_time:.3f}s)" if result.execution_time else "")
            ),
        }

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        """Execute the tool with error handling."""
        try:
            result = await self._execute_tool(params)

            if "error" in result:
                error_msg = self._format_error_message(
                    result["error"],
                    result.get("engine"),
                    result.get("sql", ""),
                    result.get("is_engine_mismatch", False),
                )
                return ToolError(
                    message=error_msg,
                    brief=result.get("brief", "Query execution failed"),
                )

            # Format success output
            metadata = self._format_metadata(
                result.get("engine", "unknown"),
                result.get("execution_time"),
                result.get("row_count", 0),
            )

            table = self._format_markdown_table(result.get("columns", []), result.get("rows", []))

            builder = ToolResultBuilder()
            builder.write(metadata)
            builder.write(table)

            return ToolOk(
                output=builder.get_output(),
                message=result.get("message", "Query executed successfully"),
            )

        except ValueError as e:
            # Handle connection/parameter errors
            return ToolError(
                message=str(e),
                brief="Connection error" if "connection" in str(e).lower() else "Invalid parameter",
            )

        except DatabaseError as e:
            # Use structured error classification for precise error messages
            brief = get_error_brief(e)
            message = format_error(e)
            return ToolError(message=message, brief=brief)

        except Exception as e:
            # Fallback for unexpected errors
            return ToolError(
                message=f"Unexpected error: {e}",
                brief="Internal error",
            )
