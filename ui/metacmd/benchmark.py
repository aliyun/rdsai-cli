"""Sysbench benchmark command - one-click performance testing."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prompt_toolkit.shortcuts.choice_input import ChoiceInput

from ui.console import console
from ui.metacmd.registry import SubCommand, meta_command

if TYPE_CHECKING:
    from ui.repl import ShellREPL


def _get_sysbench_agent_file() -> Path:
    """Get the path to the sysbench agent configuration file."""
    return Path(__file__).parent.parent.parent / "prompts" / "sysbench_agent.yaml"


_BENCHMARK_HELP = """[cyan]Usage:[/cyan] /benchmark [run|test_type] [options]

[cyan]Description:[/cyan]
  Run sysbench performance test with specified parameters.
  The agent will execute the full workflow: prepare → run → cleanup.
  After benchmark completes, a comprehensive analysis report will be generated
  including performance metrics, MySQL configuration analysis, and optimization recommendations.

[cyan]Subcommands:[/cyan]
  run                    Let agent intelligently choose test parameters

[cyan]Test Types:[/cyan]
  oltp_read_write        OLTP read-write workload (default)
  oltp_read_only         OLTP read-only workload
  select                 Simple SELECT queries
  insert                 INSERT operations
  update_index           UPDATE operations with index
  delete                 DELETE operations

[cyan]Options:[/cyan]
  --threads, -t <N>           Number of concurrent threads (default: 1)
  --time, -T <N>              Test duration in seconds (default: 60)
  --events, -e <N>            Total number of events (alternative to --time)
  --tables <N>                Number of tables (default: 1)
  --table-size <N>            Number of rows per table (default: 10000)
  --rate <N>                  Target transactions per second (rate limiting)
  --report-interval <N>       Report interval in seconds (default: 10)
  --no-cleanup                Don't cleanup test data after test
  --help, -h                  Show this help message

[cyan]Examples:[/cyan]
  /benchmark run                                Let agent choose parameters
  /benchmark --threads=100 --time=60            Quick test with 100 threads
  /benchmark oltp_read_only -t 50 -T 120        Read-only test
  /benchmark --tables=10 --table-size=1000000   Large dataset test
"""


def _parse_benchmark_args(args: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Parse benchmark arguments similar to sysbench command line.

    Returns:
        Tuple of (parsed_params_dict, unparsed_args)
    """
    params: dict[str, Any] = {}
    unparsed: list[str] = []
    i = 0

    # Check for test_type as first positional argument
    # Skip 'run' as it's a subcommand, not a test_type
    if args and not args[0].startswith("--") and args[0] not in ("-h", "--help", "run"):
        params["test_type"] = args[0]
        i = 1

    while i < len(args):
        arg = args[i]

        # Handle --help
        if arg in ("-h", "--help"):
            return {"help": True}, []

        # Handle --key=value format
        if "=" in arg:
            key, value = arg.split("=", 1)
            key = key.lstrip("-")
            params[key.replace("-", "_")] = _parse_value(value)
            i += 1
            continue

        # Handle --key value or -k value format
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                params[key] = _parse_value(args[i + 1])
                i += 2
            else:
                # Boolean flag (like --no-cleanup)
                if key == "no_cleanup":
                    params["no_cleanup"] = True
                else:
                    params[key] = True
                i += 1
        elif arg.startswith("-") and len(arg) == 2:
            # Short option like -t, -T, -e
            key_map = {
                "t": "threads",
                "T": "time",
                "e": "events",
            }
            key = key_map.get(arg[1:], arg[1:])
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                params[key] = _parse_value(args[i + 1])
                i += 2
            else:
                unparsed.append(arg)
                i += 1
        else:
            unparsed.append(arg)
            i += 1

    return params, unparsed


def _parse_value(value: str) -> Any:
    """Parse a string value to appropriate type."""
    # Try integer first
    try:
        return int(value)
    except ValueError:
        pass

    # Try boolean
    if value.lower() in ("true", "yes", "on", "1"):
        return True
    if value.lower() in ("false", "no", "off", "0"):
        return False

    # Return as string
    return value


def _format_param_description(params: dict[str, Any]) -> str:
    """Format parameters as a human-readable description.

    Args:
        params: Dictionary of parameters

    Returns:
        Formatted parameter description string
    """
    param_parts = []

    if "test_type" in params:
        param_parts.append(f"Test type: {params['test_type']}")
    if "tables" in params:
        param_parts.append(f"Tables: {params['tables']}")
    if "table_size" in params:
        param_parts.append(f"Table size: {params['table_size']:,} rows")
    if "threads" in params:
        param_parts.append(f"Threads: {params['threads']}")
    if "time" in params:
        param_parts.append(f"Duration: {params['time']} seconds")
    if "events" in params:
        param_parts.append(f"Events: {params['events']:,}")
    if "rate" in params:
        param_parts.append(f"Rate limit: {params['rate']} TPS")
    if "report_interval" in params and params.get("report_interval", 10) != 10:
        param_parts.append(f"Report interval: {params['report_interval']} seconds")

    return "\n".join(f"- {p}" for p in param_parts)


def _build_tool_params_string(params: dict[str, Any], tool_type: str) -> str:
    """Build parameter string for tool calls.

    Args:
        params: Dictionary of parameters
        tool_type: Type of tool ('prepare', 'run', or 'cleanup')

    Returns:
        Formatted parameter string
    """
    parts = []

    if tool_type == "prepare":
        test_type = params.get("test_type", "oltp_read_write")
        tables = params.get("tables", 1)
        table_size = params.get("table_size", 10000)
        parts.append(f"test_type={test_type}, tables={tables}, table_size={table_size}")
        if "threads" in params:
            parts.append(f"threads={params['threads']}")

    elif tool_type == "run":
        test_type = params.get("test_type", "oltp_read_write")
        tables = params.get("tables", 1)
        parts.append(f"test_type={test_type}, tables={tables}")
        if "threads" in params:
            parts.append(f"threads={params['threads']}")
        if "time" in params:
            parts.append(f"time={params['time']}")
        if "events" in params:
            parts.append(f"events={params['events']}")
        if "rate" in params:
            parts.append(f"rate={params['rate']}")
        if "report_interval" in params and params.get("report_interval", 10) != 10:
            parts.append(f"report_interval={params['report_interval']}")

    elif tool_type == "cleanup":
        test_type = params.get("test_type", "oltp_read_write")
        parts.append(f"test_type={test_type}")

    return ", ".join(parts)


def _build_agent_prompt(params: dict[str, Any] | None, is_run_mode: bool) -> str:
    """Build prompt for agent execution.

    Args:
        params: Parsed parameters dictionary, or None if no parameters
        is_run_mode: Whether running in 'run' mode (let agent choose parameters)

    Returns:
        Formatted prompt string for agent
    """
    if is_run_mode:
        # Run mode: let agent choose parameters (with optional partial params)
        if params:
            param_desc = _format_param_description(params)
            if param_desc:
                return f"""Run sysbench performance test on the current database.

Specified parameters:
{param_desc}

Please intelligently select other unspecified test parameters and execute the benchmark workflow."""

        # No parameters specified, let agent choose all
        return (
            "Run sysbench performance test on the current database. "
            "Please intelligently select test parameters and execute the benchmark workflow."
        )

    elif params:
        # Explicit parameters mode: use specified parameters
        param_desc = _format_param_description(params)
        no_cleanup = params.get("no_cleanup", False)

        cleanup_note = " Keep test data after benchmark." if no_cleanup else ""

        return f"""Run sysbench performance test on the current database with the following configuration:

{param_desc}{cleanup_note}"""

    else:
        # No parameters and not run mode (should not happen, but handle gracefully)
        return (
            "Run sysbench performance test on the current database. "
            "Please intelligently select test parameters and execute the benchmark workflow."
        )


@meta_command(
    loop_only=True,
    subcommands=[
        SubCommand(name="run", aliases=[], description="Let agent intelligently choose test parameters"),
    ],
)
async def benchmark(app: ShellREPL, args: list[str]):
    """Run sysbench performance test"""
    from loop import NeoLoop, RunCancelled, run_loop
    from loop.agent import load_agent
    from ui.visualize import visualize
    from utils.logging import logger

    # If no arguments, show help
    if not args:
        console.print(_BENCHMARK_HELP)
        return

    # Check for 'run' subcommand (let agent choose parameters)
    if args[0] == "run":
        # Remove 'run' from args and let agent choose
        remaining_args = args[1:]
        params, unparsed = _parse_benchmark_args(remaining_args)
    else:
        # Parse arguments normally
        params, unparsed = _parse_benchmark_args(args)

    # Handle help
    if params.get("help"):
        console.print(_BENCHMARK_HELP)
        return

    # Warn about unparsed arguments
    if unparsed:
        console.print(f"[yellow]Warning: Unrecognized arguments: {' '.join(unparsed)}[/yellow]")
        console.print("[dim]Use /benchmark --help for usage information.[/dim]\n")

    # Check database connection
    if not app.db_service or not app.db_service.is_connected():
        console.print("[red]✗[/red] Not connected to a database.")
        console.print("[dim]Use /connect to connect to a database first.[/dim]")
        return

    # Check if database is selected
    conn_info = app.db_service.get_connection_info()
    database = conn_info.get("database")
    if not database:
        console.print("[red]✗[/red] No database selected.")
        console.print("[yellow]Please create or switch to a database first.[/yellow]")
        console.print("[yellow]You can use 'CREATE DATABASE database_name;' to create a database,[/yellow]")
        console.print("[yellow]or 'USE database_name;' to switch to an existing database.[/yellow]")
        return

    # Check if sysbench is installed
    if not shutil.which("sysbench"):
        console.print("[red]✗[/red] sysbench is not installed or not in PATH.")
        console.print("[dim]Please install sysbench first: https://github.com/akopytov/sysbench[/dim]")
        return

    # Check LLM availability
    if not isinstance(app.loop, NeoLoop):
        console.print("[red]✗[/red] Benchmark requires NeoLoop.")
        return

    runtime = app.loop.runtime
    if not runtime.llm:
        console.print("[red]✗[/red] LLM not configured.")
        console.print("[dim]Use /setup to configure an LLM model.[/dim]")
        return

    # Load sysbench agent
    sysbench_agent_file = _get_sysbench_agent_file()
    if not sysbench_agent_file.exists():
        console.print(f"[red]✗[/red] Sysbench agent configuration not found: {sysbench_agent_file}")
        return

    try:
        sysbench_agent = await load_agent(sysbench_agent_file, runtime)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load sysbench agent: {e}")
        return

    # Determine if running in 'run' mode (let agent choose parameters)
    is_run_mode = args and args[0] == "run"

    # Display benchmark configuration and ask for confirmation
    console.print("\n[cyan]Benchmark Configuration:[/cyan]")
    console.print(f"  Database: [green]{database}[/green]")

    if is_run_mode:
        console.print("  Mode: [yellow]Agent will intelligently choose parameters[/yellow]")
        if params:
            param_desc = _format_param_description(params)
            if param_desc:
                console.print("  Specified parameters:")
                for line in param_desc.split("\n"):
                    console.print(f"    {line}")
    elif params:
        param_desc = _format_param_description(params)
        if param_desc:
            console.print("  Parameters:")
            for line in param_desc.split("\n"):
                console.print(f"    {line}")
    else:
        console.print("  Mode: [yellow]Agent will intelligently choose parameters[/yellow]")

    console.print("\n[yellow]⚠ Warning:[/yellow] This benchmark will put significant load on the database.")
    console.print(f"[dim]Target database: [bold]{database}[/bold][/dim]")
    console.print("[dim]Make sure this is appropriate for your environment.[/dim]\n")

    # Ask for user confirmation
    try:
        confirm = await ChoiceInput(
            message=f"Do you want to proceed with the benchmark on database '{database}'?",
            options=[
                ("yes", "Yes, start benchmark"),
                ("no", "No, cancel"),
            ],
            default="yes",
        ).prompt_async()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Benchmark cancelled by user.[/yellow]")
        return

    if confirm != "yes":
        console.print("[yellow]Benchmark cancelled.[/yellow]")
        return

    # Build prompt for agent
    prompt = _build_agent_prompt(params, is_run_mode)

    # Create a new loop instance for benchmark with sysbench agent
    benchmark_loop = NeoLoop(sysbench_agent)

    # Display startup message
    console.print("\n[cyan]Starting benchmark...[/cyan]")
    if is_run_mode:
        console.print("[dim]The agent will intelligently configure the test and generate analysis report.[/dim]")
    else:
        console.print("[dim]Analysis report will be generated after benchmark completes.[/dim]")

    cancel_event = asyncio.Event()

    try:
        await run_loop(
            benchmark_loop,
            prompt,
            lambda stream: visualize(
                stream,
                initial_status=benchmark_loop.status,
                cancel_event=cancel_event,
            ),
            cancel_event,
        )
    except RunCancelled:
        logger.info("Benchmark cancelled by user")
        console.print("\n[yellow]Benchmark cancelled by user[/yellow]")
        return
    except Exception as e:
        logger.exception("Benchmark failed")
        console.print(f"[red]✗[/red] Benchmark failed: {e}")
        return

    console.print("\n[green]✓[/green] Benchmark completed.")
