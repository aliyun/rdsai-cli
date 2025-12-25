"""Database research command - generate comprehensive database analysis reports."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from database import (
    DatabaseExplorer,
    DatabaseSchemaSnapshot,
    TableExploreProgress,
    format_snapshot_for_research,
)
from ui.console import console
from ui.metacmd.registry import meta_command

if TYPE_CHECKING:
    from ui.repl import ShellREPL


def _get_research_agent_file() -> Path:
    """Get the path to the research agent configuration file."""
    return Path(__file__).parent.parent.parent / "prompts" / "research_agent.yaml"


_RESEARCH_HELP = """[cyan]Usage:[/cyan] /research [table1 table2 ...]

[cyan]Description:[/cyan]
  Generate a comprehensive database analysis report including:
  - Database and table structure overview
  - Index analysis and optimization suggestions
  - Relationship analysis
  - Issues and recommendations

[cyan]Arguments:[/cyan]
  [green](none)[/green]           Analyze entire database
  [green]table1 table2[/green]   Analyze specific tables only

[cyan]Examples:[/cyan]
  /research              Analyze all tables in current database
  /research orders users Analyze only 'orders' and 'users' tables
"""


@meta_command(loop_only=True)
async def research(app: ShellREPL, args: list[str]):
    """Generate database analysis report"""
    from loop import NeoLoop, RunCancelled, run_loop
    from loop.agent import load_agent
    from loop.runtime import Runtime
    from ui.visualize import visualize
    from utils.logging import logger

    # Handle help
    if args and args[0] in ("help", "-h", "--help"):
        console.print(_RESEARCH_HELP)
        return

    # Check database connection
    if not app.db_service or not app.db_service.is_connected():
        console.print("[red]✗[/red] Not connected to a database.")
        console.print("[dim]Use /connect to connect to a database first.[/dim]")
        return

    conn_info = app.db_service.get_connection_info()
    database = conn_info.get("database")
    if not database:
        console.print("[red]✗[/red] No database selected.")
        console.print("[dim]Use 'USE database_name' to select a database.[/dim]")
        return

    # Check LLM availability
    if not isinstance(app.loop, NeoLoop):
        console.print("[red]✗[/red] Research requires NeoLoop.")
        return

    runtime: Runtime = app.loop.runtime
    if not runtime.llm:
        console.print("[red]✗[/red] LLM not configured.")
        console.print("[dim]Use /setup to configure an LLM model.[/dim]")
        return

    # Parse table arguments
    filter_tables = args if args else []

    # Step 1: Explore database schema with progress display
    console.print(f"Exploring database: [cyan]{database}[/cyan]")

    snapshot, total_columns = await _explore_database(app, database, filter_tables)
    if snapshot is None:
        return

    # Print exploration summary
    console.print(
        f"[green]✓[/green] Explored {len(snapshot.tables)} tables "
        f"({total_columns} columns, {len(snapshot.foreign_keys)} relationships)"
    )
    console.print()

    # Step 2: Format snapshot for agent
    schema_context = format_snapshot_for_research(snapshot)

    # Step 3: Build the research prompt with schema context
    if filter_tables:
        table_list = ", ".join(f"`{t}`" for t in filter_tables)
        user_request = f"Analyze the following tables: {table_list}"
    else:
        user_request = f"Analyze the database `{database}` and generate a comprehensive analysis report."

    prompt = f"""<schema_snapshot>
{schema_context}
</schema_snapshot>

{user_request}
"""

    # Step 4: Load research agent
    research_agent_file = _get_research_agent_file()
    if not research_agent_file.exists():
        console.print(f"[red]✗[/red] Research agent configuration not found: {research_agent_file}")
        return

    try:
        research_agent = await load_agent(research_agent_file, runtime)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load research agent: {e}")
        return

    # Step 5: Create and run research loop
    research_loop = NeoLoop(research_agent)

    console.print("[cyan]Analyzing schema...[/cyan]")

    cancel_event = asyncio.Event()

    try:
        await run_loop(
            research_loop,
            prompt,
            lambda stream: visualize(
                stream,
                initial_status=research_loop.status,
                cancel_event=cancel_event,
            ),
            cancel_event,
        )
    except RunCancelled:
        logger.info("Research cancelled by user")
        console.print("\n[yellow]Research cancelled by user[/yellow]")
        return
    except Exception as e:
        logger.exception("Research failed")
        console.print(f"[red]✗[/red] Research failed: {e}")
        return

    console.print("[green]✓[/green] Research completed.")


async def _explore_database(
    app: ShellREPL,
    database: str,
    filter_tables: list[str],
) -> tuple[DatabaseSchemaSnapshot | None, int]:
    """Explore database schema with progress display.

    Args:
        app: The shell REPL instance.
        database: Database name.
        filter_tables: List of table names to filter (empty = all tables).

    Returns:
        Tuple of (snapshot, total_columns) or (None, 0) on failure.
    """
    explorer = DatabaseExplorer(app.db_service)
    snapshot: DatabaseSchemaSnapshot | None = None
    total_columns = 0

    # Progress display state
    progress_lines: list[Text] = []
    max_display_lines = 10
    current_total = 0
    spinner = Spinner("dots", style="cyan")

    def render_progress(current_table: str | None = None, current_idx: int = 0) -> Group:
        """Render current exploration progress."""
        renderables = []

        # Show recent completed tables (with scrolling effect)
        start_idx = max(0, len(progress_lines) - max_display_lines + 1)
        for line in progress_lines[start_idx:]:
            renderables.append(line)

        # Show current table with spinner
        if current_table and current_total > 0:
            current_line = Text()
            current_line.append(f"  [{current_idx}/{current_total}] ", style="dim")
            current_line.append(current_table)
            current_line.append(" ")
            renderables.append(Group(current_line, spinner))

        return Group(*renderables)

    try:
        with Live(render_progress(), console=console, refresh_per_second=10, transient=True) as live:
            # Pass table filter to explorer to filter at database level
            table_filter = filter_tables if filter_tables else None
            for item in explorer.explore_iter(table_filter=table_filter):
                if isinstance(item, TableExploreProgress):
                    # Update total on first iteration
                    if current_total == 0:
                        current_total = item.total

                    # Update display with current table
                    display_idx = len(progress_lines) + 1
                    live.update(render_progress(item.table_name, display_idx))

                    # Add completed line for this table
                    done_line = Text()
                    done_line.append(f"  [{display_idx}/{current_total}] ", style="dim")
                    done_line.append(item.table_name)
                    done_line.append(" ✓", style="green")
                    progress_lines.append(done_line)

                elif isinstance(item, DatabaseSchemaSnapshot):
                    # Snapshot is already filtered at database level, use it directly
                    snapshot = item
                    total_columns = sum(len(t.columns) for t in snapshot.tables)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to explore database: {e}")
        return None, 0

    if snapshot is None:
        console.print("[red]✗[/red] Failed to explore database")
        return None, 0

    return snapshot, total_columns
