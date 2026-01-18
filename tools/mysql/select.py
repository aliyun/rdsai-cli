"""MySQL SELECT query tool for executing SELECT statements."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field
from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc

from .base import MySQLToolBase


class Params(BaseModel):
    select_statement: str = Field(
        description=(
            "The complete SELECT statement to execute. "
            "Examples: 'SELECT * FROM information_schema.TABLES', "
            "'SELECT * FROM mysql.slow_log WHERE start_time > \"2024-01-01\"', "
            "'SELECT * FROM performance_schema.events_statements_summary_by_digest', etc. "
            "The statement MUST start with 'SELECT' (case-insensitive). "
            "DO NOT use for SHOW statements (use MySQLShow instead), DESCRIBE statements (use MySQLDesc instead), "
            "or DDL statements (use DDLExecutor instead). "
            "ONLY SELECT queries are allowed - DML operations (INSERT/UPDATE/DELETE) are NOT permitted."
        )
    )


class MySQLSelect(MySQLToolBase):
    """Tool for executing MySQL SELECT queries.

    This tool provides flexible execution of SELECT statements, allowing the model
    to construct complete queries including FROM, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT, etc.
    """

    name: str = "MySQLSelect"
    description: str = load_desc(Path(__file__).parent / "select.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    def _is_valid_select_statement(self, sql: str) -> tuple[bool, str]:
        """Check if the SQL statement is a valid SELECT statement.

        Returns:
            tuple: (is_valid, reason_if_invalid)
        """
        sql_upper = sql.strip().upper()

        # Must start with SELECT
        if not sql_upper.startswith("SELECT"):
            return False, "Statement must start with 'SELECT'"

        # Block DML operations
        dml_keywords = ["INSERT", "UPDATE", "DELETE", "REPLACE"]
        for dml in dml_keywords:
            if sql_upper.startswith(dml) or f" {dml} " in sql_upper:
                return False, f"DML operation '{dml}' is not allowed. Only SELECT queries are permitted."

        # Block DDL operations
        ddl_keywords = [
            "CREATE TABLE",
            "CREATE INDEX",
            "DROP TABLE",
            "DROP INDEX",
            "ALTER TABLE",
            "TRUNCATE",
        ]
        for ddl in ddl_keywords:
            if ddl in sql_upper:
                return False, f"DDL operation '{ddl}' is not allowed. Use DDLExecutor for DDL operations."

        # Block dangerous operations
        dangerous_keywords = [
            "DROP DATABASE",
            "CREATE DATABASE",
            "GRANT",
            "REVOKE",
            "SET PASSWORD",
        ]

        for dangerous in dangerous_keywords:
            if dangerous in sql_upper:
                return False, f"Statement contains dangerous keyword '{dangerous}' which is not allowed"

        return True, ""

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute the SELECT statement."""
        if not params.select_statement.strip():
            return {"error": "SELECT statement is required", "brief": "SELECT statement is required"}

        # Validate it's a SELECT statement
        is_valid, reason = self._is_valid_select_statement(params.select_statement)
        if not is_valid:
            return {"error": f"Invalid SELECT statement: {reason}", "brief": "Invalid SELECT statement"}

        # Execute the SELECT statement
        columns, rows = self._execute_query(params.select_statement)

        return {
            "columns": columns,
            "rows": rows,
            "message": f"Query executed successfully, found {len(rows)} row(s)",
        }
