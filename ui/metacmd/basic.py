"""Basic meta commands: exit, help, version, clear, compact, yolo, history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner

from loop import NeoLoop
from ui.formatters.database_formatter import HistoryFormatter
from ui.console import console
from ui.metacmd.registry import get_meta_commands, meta_command

if TYPE_CHECKING:
    from ui.repl import ShellREPL


@meta_command(aliases=["quit"])
def exit(app: ShellREPL, args: list[str]):
    """Exit the application"""
    # should be handled by `ShellREPL`
    raise NotImplementedError


@meta_command(aliases=["h", "?"])
def help(app: ShellREPL, args: list[str]):
    """Show help information"""
    from rich.table import Table
    from rich.text import Text
    from rich.console import Group

    # Categorize commands
    general_cmds = []
    ai_cmds = []
    db_cmds = []

    for cmd in get_meta_commands():
        if cmd.name in ("setup", "exit", "help", "version", "reload"):
            general_cmds.append(cmd)
        elif cmd.name in ("model", "compact", "clear", "yolo"):
            ai_cmds.append(cmd)
        else:
            db_cmds.append(cmd)

    def make_cmd_table(commands: list, category: str) -> Table:
        """Create a table for a category of commands."""
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=(0, 1),
            collapse_padding=True,
        )
        table.add_column("Command", style="cyan", no_wrap=True, width=24)
        table.add_column("Description", style="default")

        # Add category header as first row
        table.add_row(Text(category, style="dim"), "")

        for cmd in commands:
            cmd_text = Text()
            cmd_text.append(f"/{cmd.name}", style="cyan")
            if cmd.aliases:
                cmd_text.append(f" ({', '.join(cmd.aliases)})", style="dim")
            table.add_row(cmd_text, cmd.description)

        return table

    # Build content parts
    parts = []

    # Header
    parts.append(Text.from_markup("[bold]RDSAI CLI[/bold] - Your intelligent database assistant\n"))
    parts.append(Text.from_markup("Send messages to get AI-powered help with your database tasks.\n"))

    # Commands section
    parts.append(Text.from_markup("\n[bold wheat4]Commands[/bold wheat4]\n"))

    # Command tables
    parts.append(make_cmd_table(general_cmds, "General"))
    parts.append(Text())  # Empty line
    parts.append(make_cmd_table(ai_cmds, "AI"))
    parts.append(Text())  # Empty line
    parts.append(make_cmd_table(db_cmds, "Database"))

    # Current status section
    status_lines: list[str] = []
    status_lines.append("\n[bold wheat4]Current Status[/bold wheat4]\n")

    # YOLO mode
    if isinstance(app.loop, NeoLoop):
        yolo_status = "[green]ON[/green]" if app.loop.runtime.yolo else "[dim]off[/dim]"
        status_lines.append(f"  YOLO Mode:  {yolo_status}")

        # Context usage
        usage = app.loop.status.context_usage
        if usage >= 0:
            usage_pct = f"{usage:.1%}"
            if usage > 0.8:
                usage_text = f"[red]{usage_pct}[/red]"
            elif usage > 0.6:
                usage_text = f"[yellow]{usage_pct}[/yellow]"
            else:
                usage_text = f"[green]{usage_pct}[/green]"
            status_lines.append(f"  Context:    {usage_text}")

    # Database connection
    if app.db_service and app.db_service.is_connected():
        db_info = app.db_service.get_connection_info()
        db_name = db_info.get("database", "-")
        host = db_info.get("host", "")
        port = db_info.get("port", "")
        status_lines.append(f"  Database:   [cyan]{db_name}[/cyan] [dim]({host}:{port})[/dim]")
    else:
        status_lines.append("  Database:   [dim]not connected[/dim]")

    parts.append(Text.from_markup("\n".join(status_lines)))

    console.print(
        Panel(
            Group(*parts),
            title="Help",
            border_style="wheat4",
            expand=False,
            padding=(1, 2),
        )
    )


@meta_command
def version(app: ShellREPL, args: list[str]):
    """Show version information"""
    from config import VERSION

    console.print(f"version {VERSION}")


@meta_command(aliases=["reset"], loop_only=True)
async def clear(app: ShellREPL, args: list[str]):
    """Clear the context (start fresh)"""
    assert isinstance(app.loop, NeoLoop)

    # Reset context by generating a new thread_id
    app.loop.reset_context()
    console.print("[green]✓[/green] Context cleared.")


@meta_command(loop_only=True)
async def compact(app: ShellREPL, args: list[str]):
    """Compact the context to save tokens"""
    assert isinstance(app.loop, NeoLoop)

    spinner = Spinner("dots", text="Compacting context...", style="cyan")

    with Live(spinner, console=console, refresh_per_second=10, transient=True):
        success = await app.loop.compact()

    if success:
        usage = app.loop.status.context_usage
        if usage >= 0:
            console.print(f"[green]✓[/green] Context compacted. Current usage: {usage:.1%}")
        else:
            console.print("[green]✓[/green] Context compacted.")
    else:
        console.print("[yellow]No context to compact or compaction not needed.[/yellow]")


@meta_command(loop_only=True)
async def yolo(app: ShellREPL, args: list[str]):
    """Toggle YOLO mode (auto approve all actions). Usage: \\yolo [on|off]"""
    assert isinstance(app.loop, NeoLoop)

    if args:
        arg = args[0].lower()
        if arg in ("on", "1", "true", "yes"):
            app.loop.runtime.set_yolo(True)
        elif arg in ("off", "0", "false", "no"):
            app.loop.runtime.set_yolo(False)
        else:
            console.print(f"[yellow]Unknown argument: {args[0]}. Use 'on' or 'off'.[/yellow]")
            return
    else:
        # Toggle mode
        current = app.loop.runtime.yolo
        app.loop.runtime.set_yolo(not current)

    if app.loop.runtime.yolo:
        console.print("[green]✓[/green] YOLO mode enabled! Living on the edge...")
    else:
        console.print("[green]✓[/green] YOLO mode disabled. Back to safe mode.")


@meta_command(aliases=["hist"])
def history(app: ShellREPL, args: list[str]):
    """Show SQL query execution history"""
    if not app.query_history:
        console.print("[yellow]No query history available.[/yellow]")
        return

    # Parse limit from args if provided
    limit = 10
    if args:
        try:
            limit = int(args[0])
            if limit <= 0:
                console.print("[red]Limit must be a positive number.[/red]")
                return
        except ValueError:
            console.print("[red]Invalid limit. Usage: /history [limit][/red]")
            return

    # Get recent queries and convert to dict format
    entries = app.query_history.get_recent_queries(limit)
    history_data = [entry.to_dict() for entry in entries]

    HistoryFormatter.format_history(history_data, limit)
