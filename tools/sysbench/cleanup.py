"""Sysbench cleanup tool for removing test data."""

from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import SysbenchToolBase


class Params(BaseModel):
    test_type: str = Field(
        default="oltp_read_write", description="Test type: oltp_read_write, oltp_read_only, select, insert, etc."
    )
    tables: int | None = Field(
        default=None, description="Number of tables to cleanup. If not specified, cleans up all tables.", ge=1, le=100
    )


class SysbenchCleanup(SysbenchToolBase):
    name: str = "SysbenchCleanup"
    description: str = load_desc(Path(__file__).parent / "cleanup.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute sysbench cleanup command."""
        try:
            # Build command arguments
            kwargs = {}
            if params.tables:
                kwargs["tables"] = params.tables

            args = self._build_sysbench_args(test_type=params.test_type, command="cleanup", **kwargs)

            # Execute command
            exit_code, stdout, stderr = await self._execute_sysbench_command(
                args,
                timeout=300,  # 5 minutes timeout for cleanup
            )

            if exit_code != 0:
                return {
                    "error": f"sysbench cleanup failed with exit code {exit_code}, {stderr or stdout}",
                    "brief": "Cleanup failed",
                }

            # Parse output and build result
            parsed = self._parse_sysbench_output(stdout, stderr)
            tables_info = f"{params.tables} table(s)" if params.tables else "all tables"

            return {
                "message": f"Successfully cleaned up {tables_info}",
                "output": stdout if stdout else "Cleanup completed successfully.",
                "errors": parsed.get("errors", []),
            }

        except Exception as e:
            return {
                "error": str(e),
                "brief": "Cleanup error",
            }
