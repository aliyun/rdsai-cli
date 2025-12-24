"""MySQL table structure tool for analyzing table schema."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    table_name: str = Field(description="The name of the table to get structure information for")


class TableStructure(MySQLToolBase):
    name: str = "TableStructure"
    description: str = load_desc(Path(__file__).parent / "table_structure.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW CREATE TABLE to get table structure."""
        if not params.table_name.strip():
            return {"error": "Table name is required", "brief": "Table name is required"}

        from database import get_current_database

        current_database = get_current_database()

        if not current_database:
            return {
                "error": "No database selected. Please use 'USE database_name' first",
                "brief": "No database selected",
            }

        sql = f"SHOW CREATE TABLE `{current_database}`.`{params.table_name}`"
        columns, rows = self._execute_query(sql)

        if rows and len(rows[0]) > 1:
            row = rows[0]
            return {
                "table_name": params.table_name,
                "data": row[1],  # The CREATE TABLE statement
                "message": f"Table structure retrieved for '{params.table_name}'",
            }
        else:
            return {
                "error": f"Table '{params.table_name}' not found",
                "brief": f"Table '{params.table_name}' not found",
            }
