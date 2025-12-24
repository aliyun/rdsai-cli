"""MySQL general log tool for SQL audit and analysis."""

from pathlib import Path
from typing import Any, Optional, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    start_time: Optional[str] = Field(
        default=None,
        description=(
            "Start time for filtering audit log entries (optional, format: 'YYYY-MM-DD HH:MM:SS'). "
            "This filters the mysql.general_log audit log, NOT business data tables."
        ),
    )
    end_time: Optional[str] = Field(
        default=None,
        description=(
            "End time for filtering audit log entries (optional, format: 'YYYY-MM-DD HH:MM:SS'). "
            "This filters the mysql.general_log audit log, NOT business data tables."
        ),
    )
    user_host: Optional[str] = Field(
        default=None, description="Filter by user and host pattern (supports % wildcard, e.g., 'root@%')"
    )
    command_type: Optional[str] = Field(
        default=None, description="Filter by command type (e.g., 'Query', 'Connect', 'Quit', 'Init DB')"
    )
    sql_pattern: Optional[str] = Field(
        default=None,
        description=(
            "Filter SQL text by pattern (supports % wildcard). "
            "This searches the audit log for SQL statements, NOT business data."
        ),
    )
    limit: int = Field(
        default=100,
        description=(
            "Maximum number of audit log entries to return (default: 100). "
            "DO NOT use this tool to query business data tables."
        ),
        ge=1,
        le=10000,
    )


class GeneralLog(MySQLToolBase):
    name: str = "GeneralLog"
    description: str = load_desc(Path(__file__).parent / "general_log.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Query MySQL general log information from mysql.general_log table."""
        # Build the SQL query
        sql = """
            SELECT event_time, user_host, thread_id, server_id,
                   command_type, argument
            FROM mysql.general_log
        """

        conditions = []
        if params.start_time:
            conditions.append(f"event_time >= '{params.start_time}'")
        if params.end_time:
            conditions.append(f"event_time <= '{params.end_time}'")
        if params.user_host:
            conditions.append(f"user_host LIKE '{params.user_host}'")
        if params.command_type:
            conditions.append(f"command_type = '{params.command_type}'")
        if params.sql_pattern:
            conditions.append(f"argument LIKE '{params.sql_pattern}'")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += f" ORDER BY event_time DESC LIMIT {params.limit}"

        columns, rows = self._execute_query(sql)

        return {
            "type": "MySQL General Log",
            "columns": columns,
            "rows": rows,
            "message": f"Found {len(rows)} general log entries",
        }
