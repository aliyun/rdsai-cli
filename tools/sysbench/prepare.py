"""Sysbench prepare tool for creating test data."""

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
    tables: int = Field(default=1, description="Number of tables to create", ge=1, le=100)
    table_size: int = Field(default=10000, description="Number of rows per table", ge=1000, le=100000000)
    threads: int = Field(default=1, description="Number of threads for data preparation", ge=1, le=32)


class SysbenchPrepare(SysbenchToolBase):
    name: str = "SysbenchPrepare"
    description: str = load_desc(Path(__file__).parent / "prepare.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute sysbench prepare command."""
        try:
            # Build and execute command
            args = self._build_sysbench_args(
                test_type=params.test_type,
                command="prepare",
                tables=params.tables,
                table_size=params.table_size,
                threads=params.threads,
            )

            exit_code, stdout, stderr = await self._execute_sysbench_command(
                args,
                timeout=7200,  # 2 hour timeout for data preparation
            )

            if exit_code != 0:
                return {
                    "error": f"sysbench prepare failed with exit code {exit_code}, {stderr or stdout}",
                    "brief": "Prepare failed",
                }

            # Parse output and build result
            parsed = self._parse_sysbench_output(stdout, stderr)
            total_rows = params.tables * params.table_size

            return {
                "message": (
                    f"Successfully prepared {params.tables} table(s) "
                    f"with {params.table_size:,} rows each "
                    f"(total: {total_rows:,} rows)"
                ),
                "metrics": {
                    "tables": params.tables,
                    "table_size": params.table_size,
                    "total_rows": total_rows,
                    "threads": params.threads,
                },
                "output": stdout if stdout else "Data preparation completed successfully.",
                "errors": parsed.get("errors", []),
            }

        except Exception as e:
            return {
                "error": str(e),
                "brief": "Prepare error",
            }
