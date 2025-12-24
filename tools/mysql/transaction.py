"""MySQL transaction tool for diagnosing transaction and lock issues."""

from pathlib import Path
from typing import Any, Optional, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    info_type: Optional[str] = Field(
        default="trx",
        description="Diagnosis type: 'trx' (active transactions), 'locks' (lock details), 'waits' (lock waits)",
    )


class Transaction(MySQLToolBase):
    name: str = "Transaction"
    description: str = load_desc(Path(__file__).parent / "transaction.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Diagnose transaction and lock related information."""
        info_type = params.info_type or "trx"

        if info_type == "locks":
            columns, rows = self._execute_query("SELECT * FROM information_schema.INNODB_LOCKS")
            return {
                "type": "InnoDB Lock Details",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} active locks",
            }
        else:  # Default to 'trx'
            columns, rows = self._execute_query("SELECT * FROM information_schema.INNODB_TRX")
            return {
                "type": "Active InnoDB Transactions",
                "columns": columns,
                "rows": rows,
                "message": f"Found {len(rows)} active transactions",
            }
