"""MySQL performance statistics tool for AliSQL Performance Agent data."""

import io
from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field

from loop.runtime import BuiltinSystemPromptArgs
from tools.utils import load_desc
from .base import MySQLToolBase


class Params(BaseModel):
    interval: int = Field(
        default=60, description="Time interval in seconds to retrieve statistics for (default: 60)", ge=1, le=60
    )


class PerfStatistics(MySQLToolBase):
    name: str = "PerfStatistics"
    description: str = load_desc(Path(__file__).parent / "perf_statistics.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Query performance statistics from information_schema.PERF_STATISTICS."""
        sql = f"""
            SELECT
                TIME,
                ROUND(PROCS_CPU_RATIO, 2) as CPU_USAGE,
                ROUND(PROCS_MEM_RATIO, 2) as MEM_USAGE,
                PROCS_IOPS as TOTAL_IOPS,
                ROUND(PROCS_IO_READ_BYTES/1024/1024, 2) as READ_MB,
                ROUND(PROCS_IO_WRITE_BYTES/1024/1024, 2) as WRITE_MB
            FROM information_schema.PERF_STATISTICS
            WHERE TIME >= NOW() - INTERVAL {params.interval} SECOND
            ORDER BY TIME DESC
        """

        columns, rows = self._execute_query(sql)

        if not rows:
            return {
                "data": "No performance statistics data available",
                "message": "No data found for the specified time interval",
            }

        # Generate CSV format output
        output = io.StringIO()

        # CSV headers
        headers = ["TIME", "CPU_USAGE(%)", "MEM_USAGE(%)", "TOTAL_IOPS", "READ_MB", "WRITE_MB"]
        output.write(",".join(headers) + "\n")

        # CSV data rows
        for row in rows:
            csv_row = []
            for value in row:
                if value is None:
                    csv_row.append("")
                else:
                    csv_row.append(str(value))
            output.write(",".join(csv_row) + "\n")

        csv_result = output.getvalue()
        output.close()

        return {
            "data": csv_result,
            "message": f"Performance statistics for last {params.interval} seconds ({len(rows)} data points)",
        }
