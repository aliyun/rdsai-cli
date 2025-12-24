"""MySQL EXPLAIN tool for analyzing SQL execution plans."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    sql: str = Field(
        description=(
            "The SQL DML statement to analyze with EXPLAIN. "
            "MUST be SELECT, INSERT, UPDATE, or DELETE only. "
            "DO NOT use for SHOW statements (use TableStatus, TableStructure, etc. instead) "
            "or DDL statements (use DDLExecutor instead). "
            "SHOW statements are NOT DML and will cause syntax errors."
        )
    )


class MySQLExplain(MySQLToolBase):
    name: str = "MySQLExplain"
    description: str = load_desc(Path(__file__).parent / "explain.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute EXPLAIN on the provided SQL statement."""
        if not params.sql.strip():
            return {"error": "SQL statement is required", "brief": "SQL statement is required"}

        explain_sql = f"EXPLAIN {params.sql}"
        columns, rows = self._execute_query(explain_sql)

        return {
            "type": "MySQL EXPLAIN Result",
            "columns": columns,
            "rows": rows,
            "message": f"Execution plan generated for SQL: {params.sql[:100]}{'...' if len(params.sql) > 100 else ''}",
        }
