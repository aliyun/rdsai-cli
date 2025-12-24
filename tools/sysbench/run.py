"""Sysbench run tool for executing performance tests."""

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
    threads: int = Field(default=1, description="Number of concurrent threads", ge=1, le=1000)
    time: int | None = Field(default=None, description="Test duration in seconds", ge=1, le=3600)
    events: int | None = Field(
        default=None, description="Total number of events to execute (alternative to time)", ge=1
    )
    rate: int | None = Field(default=None, description="Target transactions per second (rate limiting)", ge=1)
    report_interval: int = Field(default=10, description="Report interval in seconds", ge=1, le=300)
    tables: int = Field(default=1, description="Number of tables to use", ge=1, le=100)
    table_size: int | None = Field(
        default=None, description="Table size (rows per table). If not specified, uses existing tables.", ge=1000
    )


class SysbenchRun(SysbenchToolBase):
    name: str = "SysbenchRun"
    description: str = load_desc(Path(__file__).parent / "run.md")
    params: type[Params] = Params

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(builtin_args, **kwargs)

    def _build_run_kwargs(self, params: Params) -> dict[str, Any]:
        """Build keyword arguments for sysbench run command.

        Args:
            params: Tool parameters

        Returns:
            Dictionary of keyword arguments for _build_sysbench_args
        """
        kwargs = {
            "tables": params.tables,
            "threads": params.threads,
            "report_interval": params.report_interval,
        }

        # Add optional parameters
        if params.time:
            kwargs["time"] = params.time
        if params.events:
            kwargs["events"] = params.events
        if params.rate:
            kwargs["rate"] = params.rate
        if params.table_size:
            kwargs["table_size"] = params.table_size

        return kwargs

    def _calculate_timeout(self, params: Params) -> int | None:
        """Calculate command timeout based on test parameters.

        Args:
            params: Tool parameters

        Returns:
            Timeout in seconds, or None if not applicable
        """
        if params.time:
            return params.time + 30  # Add 30 seconds buffer
        elif params.events:
            # Estimate timeout based on events (assume at least 100 events/sec)
            return max((params.events // 100) + 30, 60)
        return None

    def _build_result_message(self, params: Params, metrics: dict[str, Any]) -> str:
        """Build result message from parameters and metrics.

        Args:
            params: Tool parameters
            metrics: Parsed performance metrics

        Returns:
            Formatted result message
        """
        # Build duration info
        if params.time:
            duration_info = f"for {params.time} seconds"
        elif params.events:
            duration_info = f"with {params.events:,} events"
        else:
            duration_info = ""

        message = f"Performance test completed {duration_info} with {params.threads} thread(s)"

        # Append metrics if available
        metric_parts = []
        if "tps" in metrics:
            metric_parts.append(f"TPS: {metrics['tps']:.2f}")
        if "qps" in metrics:
            metric_parts.append(f"QPS: {metrics['qps']:.2f}")
        if "avg_latency_ms" in metrics:
            metric_parts.append(f"Avg Latency: {metrics['avg_latency_ms']:.2f}ms")

        if metric_parts:
            message += " - " + ", ".join(metric_parts)

        return message

    @override
    async def _execute_tool(self, params: Params) -> dict[str, Any]:
        """Execute sysbench run command."""
        try:
            # Ensure either time or events is set
            if params.time is None and params.events is None:
                params.time = 60  # Default to 60 seconds

            # Build command arguments
            kwargs = self._build_run_kwargs(params)
            args = self._build_sysbench_args(test_type=params.test_type, command="run", **kwargs)

            # Execute command with calculated timeout
            timeout = self._calculate_timeout(params)
            exit_code, stdout, stderr = await self._execute_sysbench_command(args, timeout=timeout)

            if exit_code != 0:
                return {
                    "error": f"sysbench run failed with exit code {exit_code}, {stderr or stdout}",
                    "brief": "Run failed",
                }

            # Parse output and build result
            parsed = self._parse_sysbench_output(stdout, stderr)
            metrics = parsed.get("metrics", {})
            message = self._build_result_message(params, metrics)

            return {
                "message": message,
                "metrics": metrics,
                "output": stdout if stdout else "Test completed successfully.",
                "errors": parsed.get("errors", []),
            }

        except Exception as e:
            return {
                "error": str(e),
                "brief": "Run error",
            }
