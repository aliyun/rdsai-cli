"""Base class for MySQL tools."""

from abc import abstractmethod
from typing import Any

from loop.toolset import BaseTool, ToolError, ToolOk, ToolReturnType
from pydantic import BaseModel
from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import ToolResultBuilder

from database import (
    get_database_service,
    DatabaseError,
    get_error_brief,
    format_error,
)

# Backward compatibility alias
format_error_for_console = format_error


class ToolQueryError(Exception):
    """Query error with pre-formatted message from database service."""

    pass


class MySQLToolBase(BaseTool):
    """Base class for all MySQL database analysis tools."""

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._builtin_args = builtin_args

    def _get_database_service(self):
        """Get the current database service."""
        db_service = get_database_service()
        if db_service is None:
            raise ValueError("No database connection available. Please connect to a database first.")
        return db_service

    def _execute_query(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Execute a SQL query and return columns and rows.

        Returns:
            Tuple of (columns, rows)

        Raises:
            ToolQueryError: When query fails, with pre-formatted error message
        """
        db_service = self._get_database_service()
        result = db_service.execute_query(sql)

        if not result.success:
            raise ToolQueryError(result.error or "Query execution failed")

        return result.columns or [], result.rows

    def _format_table_output(self, columns: list[str], rows: list[tuple], table_name: str = "Result") -> str:
        """Format query results in a compact format for output."""
        if not columns or not rows:
            return f"No data found for {table_name}."

        builder = ToolResultBuilder()

        # Compact header
        builder.write(f"{table_name}: {len(rows)} rows\n")
        builder.write(f"Columns: {', '.join(columns)}\n\n")

        # Show all rows in compact format
        for row in rows:
            values = [str(val) if val is not None else "NULL" for val in row]
            builder.write(f"{' | '.join(values)}\n")

        return builder.get_output()

    def _format_simple_output(self, data: dict[str, Any]) -> str:
        """Format simple key-value data for output."""
        builder = ToolResultBuilder()

        for key, value in data.items():
            if key == "error":
                continue
            builder.write(f"**{key}**: {value}\n")

        return builder.get_output()

    @abstractmethod
    async def _execute_tool(self, params: BaseModel) -> dict[str, Any]:
        """Execute the specific tool logic. Must be implemented by subclasses."""
        pass

    async def __call__(self, params: BaseModel) -> ToolReturnType:
        """Execute the tool with error handling."""
        try:
            result = await self._execute_tool(params)

            if "error" in result:
                return ToolError(message=result["error"], brief=result.get("brief"))

            # Format output based on result structure
            if "columns" in result and "rows" in result:
                output = self._format_table_output(
                    result["columns"], result["rows"], result.get("type", "Query Result")
                )
            elif "data" in result:
                output = result["data"]
            else:
                output = self._format_simple_output(result)

            message = result.get("message", "MySQL tool executed successfully")
            return ToolOk(output=output, message=message)

        except ToolQueryError as e:
            # Query error with pre-formatted message from database service
            error_msg = str(e)
            return ToolError(message=error_msg, brief=error_msg)

        except DatabaseError as e:
            # Use structured error classification for precise error messages
            brief = get_error_brief(e)
            message = format_error_for_console(e)
            return ToolError(message=message, brief=brief)

        except ValueError as e:
            # Handle connection/parameter errors
            return ToolError(
                message=str(e), brief="Connection error" if "connection" in str(e).lower() else "Invalid parameter"
            )

        except Exception as e:
            # Fallback for unexpected errors
            return ToolError(message=f"Unexpected error: {e}", brief="Internal error")
