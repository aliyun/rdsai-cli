r"""Backslash command system for MySQL CLI.

This module provides MySQL-compatible backslash commands like:
- \s - status
- \. - source (execute SQL file)
- \r - reconnect
- \d - delimiter
- \g - execute
- \G - execute with vertical output
- \? - help
"""

from ui.backslash.registry import (
    BackslashCommand,
    backslash_command,
    get_all_commands,
    get_backslash_command,
    get_commands_by_category,
)
from ui.backslash.parser import (
    BackslashParser,
    ParseResult,
    parse_backslash_command,
)
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandFunc,
    CommandPosition,
    CommandResult,
)

# Import commands to trigger registration
from ui.backslash import commands  # noqa: F401


def execute_backslash_command(
    input_text: str,
    db_service=None,
) -> tuple[bool, CommandResult | None]:
    """
    Parse and execute a backslash command.

    Args:
        input_text: The user input to parse
        db_service: Optional database service for commands that need it

    Returns:
        Tuple of (was_handled, result):
        - was_handled: True if input was a backslash command
        - result: CommandResult if command was executed, None otherwise
    """
    parse_result = parse_backslash_command(input_text)

    if not parse_result.is_backslash_command:
        return False, None

    if parse_result.error:
        from ui.console import console

        console.print(f"[red]{parse_result.error}[/red]")
        return True, CommandResult(success=False, message=parse_result.error)

    if not parse_result.command:
        return True, CommandResult(success=False, message="No command found")

    # Build context
    ctx = CommandContext(
        db_service=db_service,
        sql_buffer=parse_result.sql_before,
        args=parse_result.args,
        raw_input=input_text,
    )

    # Execute command
    try:
        result = parse_result.command.func(ctx)
        return True, result
    except Exception as e:
        from ui.console import console
        from utils.logging import logger

        console.print(f"[red]Command error: {e}[/red]")
        logger.exception("Backslash command execution failed")
        return True, CommandResult(success=False, message=str(e))


__all__ = [
    # Registry
    "BackslashCommand",
    "backslash_command",
    "get_all_commands",
    "get_backslash_command",
    "get_commands_by_category",
    # Parser
    "BackslashParser",
    "ParseResult",
    "parse_backslash_command",
    # Types
    "CommandCategory",
    "CommandContext",
    "CommandFunc",
    "CommandPosition",
    "CommandResult",
    # Execution
    "execute_backslash_command",
]
