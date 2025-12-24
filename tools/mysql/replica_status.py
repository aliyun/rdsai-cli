"""MySQL replica status tool for monitoring replication."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    """No parameters needed for SHOW SLAVE STATUS."""

    pass


class ReplicaStatus(MySQLToolBase):
    name: str = "ReplicaStatus"
    description: str = load_desc(Path(__file__).parent / "replica_status.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW SLAVE STATUS to get replication information."""
        columns, rows = self._execute_query("SHOW SLAVE STATUS")

        return {
            "type": "MySQL Replica Status",
            "columns": columns,
            "rows": rows,
            "message": (
                "Replica status retrieved successfully" if rows else "No replica status found (not a replica server)"
            ),
        }
