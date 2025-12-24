"""Connect command implementation."""

from __future__ import annotations

from ui.backslash.registry import backslash_command
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandResult,
)
from ui.console import console
from utils.logging import logger


@backslash_command(
    char="r",
    name="connect",
    takes_args=True,
    category=CommandCategory.CONNECTION,
)
def cmd_connect(ctx: CommandContext) -> CommandResult | None:
    """Reconnect to the server. Optional arguments are db and host."""
    if not ctx.db_service:
        console.print("[red]No database service available.[/red]")
        return CommandResult(success=False)

    # Parse optional arguments: [database] [host]
    args = ctx.args.split() if ctx.args else []
    new_database = args[0] if len(args) > 0 else None
    new_host = args[1] if len(args) > 1 else None

    try:
        if new_host:
            # Connecting to a new host is not supported in this version
            console.print("[yellow]Connecting to a different host is not supported.[/yellow]")
            console.print("[dim]Use command line arguments to specify a different host.[/dim]")
            return CommandResult(success=False)

        if new_database:
            # Change database after reconnection
            pass

        # Perform reconnection
        logger.info("Attempting to reconnect...")
        connection_id = ctx.db_service.reconnect()

        # Change database if specified
        if new_database:
            try:
                ctx.db_service.change_database(new_database)
            except Exception as e:
                console.print(f"[yellow]Connected but failed to change database: {e}[/yellow]")

        # Show connection info
        info = ctx.db_service.get_connection_info()
        console.print(f"Connection id:\t{connection_id or info.get('connection_id', 'N/A')}")
        console.print(f"Current database:\t{info.get('database') or '*** NONE ***'}")

        return None

    except Exception as e:
        console.print(f"[red]Reconnection failed: {e}[/red]")
        logger.exception("Reconnection failed")
        return CommandResult(success=False)


@backslash_command(
    char="x",
    name="resetconnection",
    category=CommandCategory.CONNECTION,
)
def cmd_resetconnection(ctx: CommandContext) -> CommandResult | None:
    """Clean session context."""
    if not ctx.db_service or not ctx.db_service.is_connected():
        console.print("[red]Not connected to server.[/red]")
        return CommandResult(success=False)

    try:
        client = ctx.db_service.get_active_connection()
        if not client:
            console.print("[red]No active connection.[/red]")
            return CommandResult(success=False)

        # Reset connection using mysql_reset_connection equivalent
        # In Python mysql-connector, we can use cmd_reset_connection
        if hasattr(client, "conn") and hasattr(client.conn, "cmd_reset_connection"):
            client.conn.cmd_reset_connection()
            console.print("[green]Connection reset successfully.[/green]")
        else:
            # Fallback: just report that it's not supported
            console.print("[yellow]Reset connection not supported by this driver.[/yellow]")

        return None

    except Exception as e:
        console.print(f"[red]Failed to reset connection: {e}[/red]")
        return CommandResult(success=False)
