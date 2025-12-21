r"""Execute commands implementation (\g, \G)."""

from __future__ import annotations

from ui.backslash.registry import backslash_command
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandPosition,
    CommandResult,
)
from ui.console import console


@backslash_command(
    char="g",
    name="go",
    position=CommandPosition.BOTH,
    category=CommandCategory.QUERY,
)
def cmd_go(ctx: CommandContext) -> CommandResult | None:
    """Send command to mysql server."""
    sql = ctx.sql_before or ctx.args
    if not sql:
        console.print("[yellow]No query to execute.[/yellow]")
        return CommandResult(success=False)

    if not ctx.db_service or not ctx.db_service.is_connected():
        console.print("[red]Not connected to server.[/red]")
        return CommandResult(success=False)

    # Execute and display result
    return _execute_and_display(ctx.db_service, sql, use_vertical=False)


@backslash_command(
    char="G",
    name="ego",
    position=CommandPosition.BOTH,
    category=CommandCategory.QUERY,
)
def cmd_ego(ctx: CommandContext) -> CommandResult | None:
    """Send command to mysql server, display result vertically."""
    sql = ctx.sql_before or ctx.args
    if not sql:
        console.print("[yellow]No query to execute.[/yellow]")
        return CommandResult(success=False)

    if not ctx.db_service or not ctx.db_service.is_connected():
        console.print("[red]Not connected to server.[/red]")
        return CommandResult(success=False)

    # Execute and display result vertically
    return _execute_and_display(ctx.db_service, sql, use_vertical=True)


def _execute_and_display(db_service, sql: str, use_vertical: bool) -> CommandResult:
    """Execute SQL and display result."""
    from ui.formatters.database_formatter import format_and_display_result
    from ui.backslash.commands.warnings import (
        fetch_and_display_warnings,
        get_show_warnings,
    )

    try:
        result = db_service.execute_query(sql)
        format_and_display_result(result, sql, use_vertical=use_vertical)

        # Show warnings if enabled
        if get_show_warnings():
            fetch_and_display_warnings(db_service)

        return CommandResult(success=result.success)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return CommandResult(success=False)
