"""MySQL index tool for analyzing table indexes."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    table_name: str = Field(description="The name of the table to analyze indexes for")


class TableIndex(MySQLToolBase):
    name: str = "TableIndex"
    description: str = load_desc(Path(__file__).parent / "index.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW INDEX to get table index information."""
        if not params.table_name.strip():
            return {"error": "Table name is required", "brief": "Table name is required"}

        columns, rows = self._execute_query(f"SHOW INDEX FROM `{params.table_name}`")

        if rows:
            return {
                "type": f"Indexes for table '{params.table_name}'",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} index entries for table '{params.table_name}'",
            }
        else:
            return {
                "error": (f"No indexes found for table '{params.table_name}' or table does not exist"),
                "brief": f"No indexes for '{params.table_name}'",
            }
