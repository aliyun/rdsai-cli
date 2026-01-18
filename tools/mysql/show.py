"""MySQL SHOW statement tool for executing various SHOW commands."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field
from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc

from .base import MySQLToolBase


class Params(BaseModel):
    show_statement: str = Field(
        description=(
            "The complete SHOW statement to execute. "
            "Examples: 'SHOW VARIABLES', 'SHOW VARIABLES LIKE \"max_connections\"', "
            "'SHOW PROCESSLIST', 'SHOW TABLE STATUS', 'SHOW INDEX FROM table_name', "
            "'SHOW ENGINE INNODB STATUS', 'SHOW REPLICA STATUS', 'SHOW SLAVE STATUS', etc. "
            "The statement MUST start with 'SHOW' (case-insensitive). "
            "DO NOT use for SELECT queries (use MySQLSelect instead) or DDL statements (use DDLExecutor instead)."
        )
    )


class MySQLShow(MySQLToolBase):
    """Tool for executing MySQL SHOW statements.

    This tool provides flexible execution of various SHOW commands, allowing the model
    to construct the complete SHOW statement with all necessary parameters.
    """

    name: str = "MySQLShow"
    description: str = load_desc(Path(__file__).parent / "show.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    def _is_valid_show_statement(self, sql: str) -> tuple[bool, str]:
        """Check if the SQL statement is a valid SHOW statement.

        Returns:
            tuple: (is_valid, reason_if_invalid)
        """
        sql_upper = sql.strip().upper()

        # Must start with SHOW
        if not sql_upper.startswith("SHOW"):
            return False, "Statement must start with 'SHOW'"

        # Block dangerous operations that might be embedded
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "TRUNCATE",
            "UPDATE",
            "INSERT",
            "CREATE DATABASE",
            "DROP DATABASE",
            "GRANT",
            "REVOKE",
        ]

        for dangerous in dangerous_keywords:
            if dangerous in sql_upper:
                return False, f"Statement contains dangerous keyword '{dangerous}' which is not allowed"

        return True, ""

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute the SHOW statement."""
        if not params.show_statement.strip():
            return {"error": "SHOW statement is required", "brief": "SHOW statement is required"}

        # Validate it's a SHOW statement
        is_valid, reason = self._is_valid_show_statement(params.show_statement)
        if not is_valid:
            return {"error": f"Invalid SHOW statement: {reason}", "brief": "Invalid SHOW statement"}

        # Execute the SHOW statement
        columns, rows = self._execute_query(params.show_statement)

        return {
            "columns": columns,
            "rows": rows,
            "message": f"SHOW statement executed successfully, found {len(rows)} row(s)",
        }
