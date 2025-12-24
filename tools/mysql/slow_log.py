"""MySQL slow log tool for analyzing slow query performance."""

from pathlib import Path
from typing import Any, Optional, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    start_time: Optional[str] = Field(
        default=None, description="Start time for query (optional, format: 'YYYY-MM-DD HH:MM:SS')"
    )
    end_time: Optional[str] = Field(
        default=None, description="End time for query (optional, format: 'YYYY-MM-DD HH:MM:SS')"
    )
    limit: int = Field(default=100, description="Maximum number of rows to return (default: 100)", ge=1, le=10000)


class SlowLog(MySQLToolBase):
    name: str = "SlowLog"
    description: str = load_desc(Path(__file__).parent / "slow_log.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Query MySQL slow log information from mysql.slow_log table."""
        # Build the SQL query
        sql = """
            SELECT start_time, user_host, query_time, lock_time,
                   rows_sent, rows_examined, db, sql_text
            FROM mysql.slow_log
        """

        conditions = []
        if params.start_time:
            conditions.append(f"start_time >= '{params.start_time}'")
        if params.end_time:
            conditions.append(f"start_time <= '{params.end_time}'")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += f" ORDER BY start_time DESC LIMIT {params.limit}"

        columns, rows = self._execute_query(sql)

        return {
            "type": "MySQL Slow Query Log",
            "columns": columns,
            "rows": rows,
            "message": f"Found {len(rows)} slow query entries",
        }
