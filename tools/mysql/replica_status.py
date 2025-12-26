"""MySQL replica status tool for monitoring replication."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    """No parameters needed for SHOW REPLICA STATUS / SHOW SLAVE STATUS."""

    pass


class ReplicaStatus(MySQLToolBase):
    name: str = "ReplicaStatus"
    description: str = load_desc(Path(__file__).parent / "replica_status.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW REPLICA STATUS (MySQL 8.0.22+) or SHOW SLAVE STATUS (older versions) to get replication information."""
        # MySQL 8.0.22+ uses SHOW REPLICA STATUS, older versions use SHOW SLAVE STATUS
        if self._is_mysql_version_at_least(8, 0, 22):
            sql = "SHOW REPLICA STATUS"
        else:
            sql = "SHOW SLAVE STATUS"

        columns, rows = self._execute_query(sql)

        return {
            "type": "MySQL Replica Status",
            "columns": columns,
            "rows": rows,
            "message": (
                "Replica status retrieved successfully" if rows else "No replica status found (not a replica server)"
            ),
        }
