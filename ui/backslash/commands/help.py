"""Help command implementation."""

from __future__ import annotations

from ui.backslash.registry import backslash_command, get_commands_by_category
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandResult,
)
from ui.console import console


@backslash_command(
    char="?",
    name="help",
    aliases=("h",),
    category=CommandCategory.HELP,
)
def cmd_help(ctx: CommandContext) -> CommandResult | None:
    """Display this help."""
    console.print("\n[bold]List of backslash commands:[/bold]\n")

    by_category = get_commands_by_category()

    # Define display order for categories
    category_order = [
        CommandCategory.HELP,
        CommandCategory.QUERY,
        CommandCategory.CONNECTION,
        CommandCategory.FILE,
        CommandCategory.DISPLAY,
        CommandCategory.SESSION,
    ]

    for category in category_order:
        cmds = by_category.get(category, [])
        if not cmds:
            continue

        console.print(f"[bold dim]{category.value.title()}:[/bold dim]")
        for cmd in sorted(cmds, key=lambda c: c.char or c.name):
            char_display = f"\\{cmd.char}" if cmd.char else ""
            alias_display = ""
            if cmd.aliases:
                alias_display = f" (\\{', \\'.join(cmd.aliases)})"

            console.print(f"  [cyan]{char_display:6}[/cyan]{alias_display:10} {cmd.description}")
        console.print()

    console.print("[dim]For more help, type 'help' followed by a topic.[/dim]\n")
    return None
