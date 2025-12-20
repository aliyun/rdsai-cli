"""Quit command implementation."""

from __future__ import annotations

from ui.backslash.registry import backslash_command
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandResult,
)


@backslash_command(
    char="q",
    name="quit",
    category=CommandCategory.SESSION,
)
def cmd_quit(ctx: CommandContext) -> CommandResult:
    """Exit mysql. Same as quit."""
    # Return a special result that signals the main loop to exit
    return CommandResult(success=True, should_continue=False)
