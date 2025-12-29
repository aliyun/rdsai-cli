"""SQL execution plan analysis command."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loop import NeoLoop, RunCancelled, run_loop
from ui.console import console
from ui.metacmd.registry import meta_command
from ui.visualize import visualize
from utils.logging import logger

if TYPE_CHECKING:
    from ui.repl import ShellREPL


def _format_explain_result(columns: list[str], rows: list[list]) -> str:
    """Format EXPLAIN result as Markdown table.

    Args:
        columns: Column names from EXPLAIN result.
        rows: Row data from EXPLAIN result.

    Returns:
        Formatted Markdown table string.
    """
    if not rows:
        return "No execution plan data."

    # Build Markdown table header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"

    # Build table rows
    table_rows = []
    for row in rows:
        # Convert each cell to string, handle None values
        formatted_row = [str(cell) if cell is not None else "NULL" for cell in row]
        table_rows.append("| " + " | ".join(formatted_row) + " |")

    # Combine header, separator, and rows
    return "\n".join([header, separator] + table_rows)


@meta_command(loop_only=True)
async def explain(app: ShellREPL, args: list[str]):
    """Intelligently analyze SQL execution plan using AI capabilities."""
    # Check if SQL is provided
    if not args:
        console.print("[yellow]Usage: /explain <sql>[/yellow]")
        console.print("[dim]Example: /explain SELECT * FROM users WHERE id = xxx[/dim]")
        return

    # Check database connection
    if not app.db_service or not app.db_service.is_connected():
        console.print("[red]✗[/red] Not connected to a database.")
        console.print("[dim]Use /connect to connect to a database first.[/dim]")
        return

    # Check LLM availability
    if not isinstance(app.loop, NeoLoop):
        console.print("[red]✗[/red] Explain requires agent loop.")
        return

    if not app.loop.runtime.llm:
        console.print("[red]✗[/red] LLM not configured.")
        console.print("[dim]Use /setup to configure an LLM model.[/dim]")
        return

    # Combine arguments as SQL statement
    sql = " ".join(args)

    # Execute EXPLAIN
    try:
        explain_sql = f"EXPLAIN {sql}"
        result = app.db_service.execute_query(explain_sql)

        if not result.success:
            console.print(f"[red]✗[/red] Failed to execute EXPLAIN: {result.error}")
            return

        if not result.columns or not result.rows:
            console.print("[yellow]No execution plan data returned.[/yellow]")
            return

    except Exception as e:
        logger.exception("Failed to execute EXPLAIN")
        console.print(f"[red]✗[/red] Failed to execute EXPLAIN: {e}")
        return

    # Format execution plan result
    formatted_plan = _format_explain_result(result.columns, result.rows)

    # Build analysis prompt
    prompt = f"""Please analyze the following SQL execution plan:

SQL Statement:
{sql}

Execution Plan:
{formatted_plan}

Please provide:
1. Key metrics analysis of the execution plan:
   - Index usage (key field)
   - Scan type (type field: ALL=full table scan, index=index scan, range=range scan, ref=index lookup, etc.)
   - Estimated rows scanned (rows field)
   - Join order and type (if multiple tables are involved)
   - Extra information (Extra field: Using index, Using where, Using filesort, etc.)
2. Potential performance issues (e.g., full table scans, missing index usage, large row counts)
3. Specific optimization suggestions (e.g., adding indexes, rewriting queries)
"""

    # Run analysis using main loop
    console.print("[cyan]Analyzing execution plan...[/cyan]")

    cancel_event = asyncio.Event()

    try:
        await run_loop(
            app.loop,
            prompt,
            lambda stream: visualize(
                stream,
                initial_status=app.loop.status,
                cancel_event=cancel_event,
            ),
            cancel_event,
        )
    except RunCancelled:
        logger.info("Explain cancelled by user")
        console.print("\n[yellow]Explain cancelled by user[/yellow]")
        return
    except Exception as e:
        logger.exception("Explain failed")
        console.print(f"[red]✗[/red] Explain failed: {e}")
        return

    console.print("[green]✓[/green] Execution plan analysis completed.")
