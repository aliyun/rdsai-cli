"""MySQL information_schema tool for querying database metadata."""

from pathlib import Path
from typing import Any, Optional, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    info_type: Optional[str] = Field(
        default="tables",
        description="Information type: 'index', 'buffer_pool', 'tablespace', 'tables', 'perf_statistics'",
    )
    table: Optional[str] = Field(
        default=None, description="Table name for specific queries (used with 'index' info_type)"
    )


class InformationSchema(MySQLToolBase):
    name: str = "InformationSchema"
    description: str = load_desc(Path(__file__).parent / "information_schema.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Query information_schema for various database metadata."""
        info_type = params.info_type or "tables"

        if info_type == "index" and params.table:
            sql = f"SELECT * FROM information_schema.STATISTICS WHERE table_name = '{params.table}'"
            columns, rows = self._execute_query(sql)
            return {
                "type": f"Index Statistics for table '{params.table}'",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} index statistics for table '{params.table}'",
            }
        elif info_type == "buffer_pool":
            columns, rows = self._execute_query("SELECT * FROM information_schema.INNODB_BUFFER_POOL_STATS")
            return {
                "type": "InnoDB Buffer Pool Statistics",
                "columns": columns,
                "rows": rows,
                "message": "InnoDB buffer pool statistics retrieved",
            }
        elif info_type == "tablespace":
            columns, rows = self._execute_query("SELECT * FROM information_schema.TABLES")
            return {
                "type": "Table Information",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} tables in information_schema.TABLES",
            }
        else:  # Default to 'tables'
            columns, rows = self._execute_query("SHOW TABLES FROM information_schema")
            return {
                "type": "Information Schema Tables",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} tables in information_schema",
            }
