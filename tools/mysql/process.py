"""MySQL process list tool for monitoring database connections."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    """No parameters needed for SHOW PROCESSLIST."""

    pass


class ShowProcess(MySQLToolBase):
    name: str = "ShowProcess"
    description: str = load_desc(Path(__file__).parent / "process.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW PROCESSLIST to get current database connections."""
        columns, rows = self._execute_query("SHOW PROCESSLIST")

        return {
            "type": "MySQL Process List",
            "columns": columns,
            "rows": rows,
            "message": f"Found {len(rows)} active database connections",
        }
