"""Delimiter command implementation."""

from __future__ import annotations

from ui.backslash.registry import backslash_command
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandResult,
)
from ui.console import console


# Global delimiter state
_current_delimiter: str = ";"


def get_delimiter() -> str:
    """Get the current statement delimiter."""
    return _current_delimiter


def set_delimiter(delimiter: str) -> None:
    """Set the statement delimiter."""
    global _current_delimiter
    _current_delimiter = delimiter


@backslash_command(
    char="d",
    name="delimiter",
    takes_args=True,
    category=CommandCategory.QUERY,
)
def cmd_delimiter(ctx: CommandContext) -> CommandResult | None:
    """Set statement delimiter."""
    if not ctx.args:
        # Show current delimiter
        console.print(f"Current delimiter: [cyan]{_current_delimiter}[/cyan]")
        return None

    new_delimiter = ctx.args.strip()

    # Validate delimiter
    if "\\" in new_delimiter:
        console.print("[red]DELIMITER cannot contain a backslash character.[/red]")
        return CommandResult(success=False)

    if not new_delimiter:
        console.print("[red]DELIMITER must be followed by a 'delimiter' character or string.[/red]")
        return CommandResult(success=False)

    # Set new delimiter
    set_delimiter(new_delimiter)
    console.print(f"Delimiter set to: [cyan]{new_delimiter}[/cyan]")
    return None
