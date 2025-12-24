"""Base class for Sysbench tools."""

import asyncio
import re
import shutil
from abc import abstractmethod
from typing import Any

from pydantic import BaseModel

from loop.runtime import BuiltinSystemPromptArgs
from loop.toolset import BaseTool, ToolError, ToolOk, ToolReturnType
from tools.utils import ToolResultBuilder
from database import get_database_service


class SysbenchToolBase(BaseTool):
    """Base class for all Sysbench performance testing tools."""

    # Regex patterns for parsing sysbench output
    _TPS_PATTERN = re.compile(r"tps:\s*([\d.]+)", re.IGNORECASE)
    _QPS_PATTERN = re.compile(r"qps:\s*([\d.]+)", re.IGNORECASE)
    _LATENCY_PATTERN = re.compile(r"latency\s+\(ms\):\s*avg:\s*([\d.]+)", re.IGNORECASE)

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._builtin_args = builtin_args

    def _get_database_service(self):
        """Get the current database service."""
        db_service = get_database_service()
        if db_service is None:
            raise ValueError("No database connection available. Please connect to a database first.")
        return db_service

    def _get_connection_info(self) -> dict[str, Any]:
        """Get database connection information for sysbench."""
        db_service = self._get_database_service()
        conn_info = db_service.get_connection_info()

        if not conn_info.get("connected"):
            raise ValueError("Not connected to database")

        database = conn_info.get("database")
        if not database:
            raise ValueError(
                "No database selected. Please create or switch to a database first.\n"
                "You can use 'CREATE DATABASE database_name;' to create a database, "
                "or 'USE database_name;' to switch to an existing database."
            )

        return {
            "host": conn_info["host"],
            "port": conn_info["port"],
            "user": conn_info["user"],
            "password": db_service._connection_config.password if db_service._connection_config else None,
            "database": database,
        }

    def _check_sysbench_installed(self) -> bool:
        """Check if sysbench is installed and available."""
        return shutil.which("sysbench") is not None

    def _build_sysbench_args(self, test_type: str, command: str, **kwargs: Any) -> list[str]:
        """Build sysbench command arguments.

        Args:
            test_type: Test type (e.g., 'oltp_read_write', 'oltp_read_only')
            command: Sysbench command (prepare, run, cleanup)
            **kwargs: Additional sysbench parameters

        Returns:
            List of command arguments
        """
        conn_info = self._get_connection_info()

        # Build base command
        args = [
            "sysbench",
            test_type,
            f"--mysql-host={conn_info['host']}",
            f"--mysql-port={conn_info['port']}",
            f"--mysql-user={conn_info['user']}",
            f"--mysql-db={conn_info['database']}",
        ]

        # Add password if available
        if conn_info["password"]:
            args.append(f"--mysql-password={conn_info['password']}")

        # Map parameter names to sysbench option names
        param_mapping = {
            "tables": "--tables",
            "table_size": "--table-size",
            "threads": "--threads",
            "time": "--time",
            "events": "--events",
            "rate": "--rate",
            "report_interval": "--report-interval",
        }

        # Add common parameters
        for param_name, option_name in param_mapping.items():
            if param_name in kwargs:
                args.append(f"{option_name}={kwargs[param_name]}")

        # Add command
        args.append(command)

        return args

    async def _execute_sysbench_command(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        """Execute sysbench command and return exit code, stdout, stderr.

        Args:
            args: Command arguments
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self._check_sysbench_installed():
            raise ValueError(
                "sysbench is not installed or not in PATH. "
                "Please install sysbench first: https://github.com/akopytov/sysbench"
            )

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            exit_code = await process.wait()

            return (
                exit_code,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            if process is not None:
                # Terminate the process on timeout
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Force kill if terminate doesn't work
                    process.kill()
                    await process.wait()
            raise ValueError(f"sysbench command timed out after {timeout} seconds")
        except asyncio.CancelledError:
            # Task was cancelled - terminate the subprocess
            if process is not None:
                try:
                    process.terminate()
                    # Wait briefly for graceful termination
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        # Force kill if terminate doesn't work within 2 seconds
                        process.kill()
                        await process.wait()
                except Exception:
                    # Ignore errors during cleanup
                    pass
            # Re-raise CancelledError to propagate cancellation
            raise
        except Exception as e:
            # Ensure process is terminated on any other error
            if process is not None and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except Exception:
                    try:
                        process.kill()
                        await process.wait()
                    except Exception:
                        pass
            raise ValueError(f"Failed to execute sysbench command: {e}")

    def _parse_sysbench_output(self, stdout: str, stderr: str) -> dict[str, Any]:
        """Parse sysbench output and extract key metrics.

        Args:
            stdout: Standard output from sysbench
            stderr: Standard error from sysbench

        Returns:
            Dictionary with parsed metrics
        """
        result = {
            "raw_output": stdout + stderr,
            "metrics": {},
            "errors": [],
        }

        # Parse metrics from stdout
        for line in stdout.split("\n"):
            # Extract TPS
            tps_match = self._TPS_PATTERN.search(line)
            if tps_match:
                result["metrics"]["tps"] = float(tps_match.group(1))

            # Extract QPS
            qps_match = self._QPS_PATTERN.search(line)
            if qps_match:
                result["metrics"]["qps"] = float(qps_match.group(1))

            # Extract average latency
            latency_match = self._LATENCY_PATTERN.search(line)
            if latency_match:
                result["metrics"]["avg_latency_ms"] = float(latency_match.group(1))

        # Parse error messages from stderr
        if stderr:
            error_lines = [line.strip() for line in stderr.split("\n") if line.strip()]
            if error_lines:
                result["errors"] = error_lines

        return result

    @abstractmethod
    async def _execute_tool(self, params: BaseModel) -> dict[str, Any]:
        """Execute the specific tool logic. Must be implemented by subclasses."""
        pass

    def _format_result_output(self, result: dict[str, Any]) -> str:
        """Format tool result for output.

        Args:
            result: Result dictionary from _execute_tool

        Returns:
            Formatted output string
        """
        builder = ToolResultBuilder()

        if "message" in result:
            builder.write(f"{result['message']}\n\n")

        if "metrics" in result and result["metrics"]:
            builder.write("**Performance Metrics:**\n")
            for key, value in result["metrics"].items():
                builder.write(f"  {key}: {value}\n")
            builder.write("\n")

        if "output" in result:
            builder.write(f"{result['output']}\n")

        if "errors" in result and result["errors"]:
            builder.write("**Warnings/Errors:**\n")
            for error in result["errors"]:
                builder.write(f"  {error}\n")

        return builder.get_output()

    async def __call__(self, params: BaseModel) -> ToolReturnType:
        """Execute the tool with error handling."""
        try:
            result = await self._execute_tool(params)

            if "error" in result:
                return ToolError(message=result["error"], brief=result.get("brief", "Sysbench error"))

            output = self._format_result_output(result)
            message = result.get("message", "Sysbench tool executed successfully")
            return ToolOk(output=output, message=message)

        except asyncio.CancelledError:
            # Re-raise CancelledError to allow proper cancellation propagation
            raise
        except ValueError as e:
            return ToolError(message=str(e), brief="Configuration error")
        except Exception as e:
            return ToolError(message=f"Unexpected error: {e}", brief="Internal error")
