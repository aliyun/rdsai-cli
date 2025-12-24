"""MySQL DDL modification tool for executing SQL changes like CREATE INDEX, etc."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field
from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc

from .base import MySQLToolBase


class Params(BaseModel):
    sql_statement: str = Field(
        description=(
            "The SQL DDL statement to execute (e.g., CREATE INDEX, DROP INDEX, "
            "ALTER TABLE, CREATE TABLE, etc.). "
            "ONLY DDL statements are allowed - DO NOT use for SELECT queries or DML operations (INSERT/UPDATE/DELETE). "
        )
    )
    description: str = Field(description="A brief description of what this SQL modification will do")


class DDLExecutor(MySQLToolBase):
    """Tool for executing MySQL DDL modifications.

    Note: This tool requires user approval, which is handled by
    LangGraph's interrupt mechanism in loop/nodes.py.
    """

    name: str = "DDLExecutor"
    description: str = load_desc(Path(__file__).parent / "sql_ddl.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    def _is_safe_ddl_statement(self, sql: str) -> tuple[bool, str]:
        """Check if the SQL statement is a safe DDL operation.

        Returns:
            tuple: (is_safe, reason_if_not_safe)
        """
        # Remove leading/trailing whitespace and convert to uppercase for checking
        sql_upper = sql.strip().upper()

        # Allow these DDL operations
        allowed_ddl = [
            "CREATE INDEX",
            "CREATE UNIQUE INDEX",
            "DROP INDEX",
            "ALTER TABLE",
            "CREATE TABLE",
            "DROP TABLE",
            "CREATE VIEW",
            "DROP VIEW",
            "CREATE PROCEDURE",
            "DROP PROCEDURE",
            "CREATE FUNCTION",
            "DROP FUNCTION",
            "CREATE TRIGGER",
            "DROP TRIGGER",
        ]

        # Check if statement starts with any allowed DDL
        for ddl in allowed_ddl:
            if sql_upper.startswith(ddl):
                return True, ""

        # Block dangerous operations
        dangerous_operations = [
            "DELETE",
            "UPDATE",
            "INSERT",
            "TRUNCATE",
            "DROP DATABASE",
            "CREATE DATABASE",
            "GRANT",
            "REVOKE",
            "SET",
            "USE",
        ]

        for dangerous in dangerous_operations:
            if sql_upper.startswith(dangerous):
                return False, f"'{dangerous}' operations are not allowed for safety"

        return False, "Only DDL statements (CREATE INDEX, ALTER TABLE, etc.) are allowed"

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute the SQL DDL modification.

        Note: User approval is handled by LangGraph's interrupt mechanism
        before this tool is executed. See loop/nodes.py for details.
        """
        if not params.sql_statement.strip():
            return {"error": "SQL statement is required", "brief": "SQL statement is required"}

        # Check if it's a safe DDL statement
        is_safe, reason = self._is_safe_ddl_statement(params.sql_statement)
        if not is_safe:
            return {"error": f"Unsafe SQL statement: {reason}", "brief": "Unsafe SQL statement"}

        from database import get_current_database, get_database_service

        db_service = get_database_service()

        if not db_service or not db_service.is_connected():
            return {
                "error": ("No database connection available. Please connect to a database first"),
                "brief": "No database connection",
            }

        current_database = get_current_database()

        if not current_database:
            return {
                "error": "No database selected. Please use 'USE database_name' first",
                "brief": "No database selected",
            }

        # Execute the DDL statement using DatabaseService
        # Note: Approval has already been granted via LangGraph interrupt
        result = db_service.execute_query(params.sql_statement)

        if not result.success:
            from .base import ToolQueryError

            raise ToolQueryError(result.error or "DDL execution failed")

        return {
            "message": f"SQL modification executed successfully: {params.description}",
            "sql_executed": params.sql_statement,
            "database": current_database,
            "success": True,
            "affected_rows": result.affected_rows,
        }
