"""MySQL parameter tool for querying system variables."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    param_name: str = Field(description="The name of the MySQL parameter/variable to query")


class KernelParameter(MySQLToolBase):
    name: str = "KernelParameter"
    description: str = load_desc(Path(__file__).parent / "parameter.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute SHOW VARIABLES to get parameter information."""
        if not params.param_name.strip():
            return {"error": "Parameter name is required", "brief": "Parameter name is required"}

        sql = f"SHOW VARIABLES LIKE '{params.param_name}'"
        columns, rows = self._execute_query(sql)

        if not rows:
            return {
                "error": f"Parameter '{params.param_name}' not found",
                "brief": f"Parameter '{params.param_name}' not found",
            }

        if len(rows) == 1:
            # Single result - return simple format
            row = rows[0]
            return {"param_name": row[0], "value": row[1], "message": f"Parameter '{row[0]}' = '{row[1]}'"}
        else:
            # Multiple results - return all parameters
            parameters = [{"name": row[0], "value": row[1]} for row in rows]
            return {
                "pattern": params.param_name,
                "count": len(rows),
                "parameters": parameters,
                "message": f"Found {len(rows)} parameters matching '{params.param_name}'",
            }
