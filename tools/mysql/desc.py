"""MySQL DESCRIBE/DESC tool for describing table structure."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field
from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc

from .base import MySQLToolBase


class Params(BaseModel):
    desc_statement: str = Field(
        description=(
            "The complete DESCRIBE or DESC statement to execute. "
            "Examples: 'DESCRIBE table_name', 'DESC table_name', "
            "'SHOW CREATE TABLE table_name', 'SHOW COLUMNS FROM table_name', etc. "
            "The statement MUST start with 'DESCRIBE', 'DESC', or 'SHOW CREATE TABLE' or 'SHOW COLUMNS' (case-insensitive). "
            "DO NOT use for SELECT queries (use MySQLSelect instead) or DDL statements (use DDLExecutor instead)."
        )
    )


class MySQLDesc(MySQLToolBase):
    """Tool for executing MySQL DESCRIBE/DESC statements.

    This tool provides flexible execution of table structure description commands,
    allowing the model to construct the complete statement with table names.
    """

    name: str = "MySQLDesc"
    description: str = load_desc(Path(__file__).parent / "desc.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    def _is_valid_desc_statement(self, sql: str) -> tuple[bool, str]:
        """Check if the SQL statement is a valid DESCRIBE/DESC statement.

        Returns:
            tuple: (is_valid, reason_if_invalid)
        """
        sql_upper = sql.strip().upper()

        # Must start with DESCRIBE, DESC, or SHOW CREATE TABLE or SHOW COLUMNS
        valid_starts = ["DESCRIBE", "DESC", "SHOW CREATE TABLE", "SHOW COLUMNS"]
        is_valid_start = any(sql_upper.startswith(start) for start in valid_starts)

        if not is_valid_start:
            return False, "Statement must start with 'DESCRIBE', 'DESC', 'SHOW CREATE TABLE', or 'SHOW COLUMNS'"

        # Block dangerous operations
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
        """Execute the DESCRIBE/DESC statement."""
        if not params.desc_statement.strip():
            return {"error": "DESCRIBE statement is required", "brief": "DESCRIBE statement is required"}

        # Validate it's a valid DESCRIBE statement
        is_valid, reason = self._is_valid_desc_statement(params.desc_statement)
        if not is_valid:
            return {"error": f"Invalid DESCRIBE statement: {reason}", "brief": "Invalid DESCRIBE statement"}

        # Execute the statement
        columns, rows = self._execute_query(params.desc_statement)

        return {
            "columns": columns,
            "rows": rows,
            "message": f"Table structure retrieved successfully, found {len(rows)} column(s)",
        }
