"""MySQL table status tool for analyzing table statistics."""

from pathlib import Path
from typing import Any, Optional, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    db_name: Optional[str] = Field(
        default=None, description="The name of the database to query (optional, uses current database if not specified)"
    )
    table_name: Optional[str] = Field(
        default=None, description="The name of the table to query (optional, shows all tables if not specified)"
    )


class TableStatus(MySQLToolBase):
    name: str = "TableStatus"
    description: str = load_desc(Path(__file__).parent / "table_status.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW TABLE STATUS to get table statistics."""
        from database import get_current_database

        # Determine database to use
        database = params.db_name or get_current_database()
        if not database:
            return {
                "error": ("No database selected. Please specify db_name or use 'USE database_name' first"),
                "brief": "No database selected",
            }

        # Build the SQL query
        if params.table_name:
            sql = f"SHOW TABLE STATUS FROM `{database}` LIKE '{params.table_name}'"
        else:
            sql = f"SHOW TABLE STATUS FROM `{database}`"

        columns, rows = self._execute_query(sql)

        table_info = f"database '{database}'"
        if params.table_name:
            table_info += f", table '{params.table_name}'"

        return {
            "type": f"Table Status for {table_info}",
            "columns": columns,
            "rows": rows,
            "message": f"Found {len(rows)} table(s) in {table_info}",
        }
