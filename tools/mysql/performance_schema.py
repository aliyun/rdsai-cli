"""MySQL performance_schema tool for detailed performance analysis."""

from pathlib import Path
from typing import Any, Optional, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    info_type: Optional[str] = Field(
        default="tables",
        description=(
            "Information type: 'statements', 'waits', 'table_io', 'table_lock', "
            "'threads', 'users', 'accounts', 'hosts', 'tables', 'memory'"
        ),
    )
    table: Optional[str] = Field(
        default=None,
        description=(
            "Table name for table_io/table_lock queries, or memory analysis type "
            "(by_user, by_host, by_account, by_thread)"
        ),
    )


class PerformanceSchema(MySQLToolBase):
    name: str = "PerformanceSchema"
    description: str = load_desc(Path(__file__).parent / "performance_schema.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Query performance_schema for various performance metrics."""
        info_type = params.info_type or "tables"

        if info_type == "statements":
            sql = "SELECT * FROM performance_schema.events_statements_summary_by_digest LIMIT 100"
            columns, rows = self._execute_query(sql)
            return {
                "type": "Statement Summary by Digest",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} statement summaries",
            }
        elif info_type == "waits":
            sql = "SELECT * FROM performance_schema.events_waits_summary_global_by_event_name"
            columns, rows = self._execute_query(sql)
            return {
                "type": "Wait Events Summary",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} wait event summaries",
            }
        elif info_type == "threads":
            columns, rows = self._execute_query("SELECT * FROM performance_schema.threads")
            return {
                "type": "Thread Information",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} threads",
            }
        elif info_type == "users":
            columns, rows = self._execute_query("SELECT * FROM performance_schema.users")
            return {
                "type": "User Statistics",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} user summaries",
            }
        elif info_type == "accounts":
            columns, rows = self._execute_query("SELECT * FROM performance_schema.accounts")
            return {
                "type": "Account Statistics",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} account summaries",
            }
        elif info_type == "hosts":
            columns, rows = self._execute_query("SELECT * FROM performance_schema.hosts")
            return {
                "type": "Host Statistics",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} host summaries",
            }
        elif info_type == "memory":
            # Support different memory analysis dimensions
            memory_table = "memory_summary_global_by_event_name"
            if params.table == "by_user":
                memory_table = "memory_summary_by_user_by_event_name"
            elif params.table == "by_host":
                memory_table = "memory_summary_by_host_by_event_name"
            elif params.table == "by_account":
                memory_table = "memory_summary_by_account_by_event_name"
            elif params.table == "by_thread":
                memory_table = "memory_summary_by_thread_by_event_name"

            columns, rows = self._execute_query(f"SELECT * FROM performance_schema.{memory_table}")
            return {
                "type": f"Memory Summary - {memory_table}",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} memory summaries from {memory_table}",
            }
        else:  # Default to 'tables'
            columns, rows = self._execute_query("SHOW TABLES FROM performance_schema")
            return {
                "type": "Performance Schema Tables",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} tables in performance_schema",
            }
