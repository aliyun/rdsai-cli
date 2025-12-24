"""Backslash command registry and decorator."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import overload

from .types import (
    BackslashCommand,
    CommandCategory,
    CommandFunc,
    CommandPosition,
)


# Primary name -> BackslashCommand
_commands: dict[str, BackslashCommand] = {}
# Character or alias -> BackslashCommand
_char_map: dict[str, BackslashCommand] = {}


def get_backslash_command(name_or_char: str) -> BackslashCommand | None:
    """Get command by name or shortcut character."""
    # First try char map (single character lookups)
    if len(name_or_char) == 1:
        cmd = _char_map.get(name_or_char)
        if cmd:
            return cmd
    # Then try by name
    return _commands.get(name_or_char)


def get_all_commands() -> list[BackslashCommand]:
    """Get all registered commands."""
    return list(_commands.values())


def get_commands_by_category() -> dict[CommandCategory, list[BackslashCommand]]:
    """Get commands grouped by category."""
    by_category: dict[CommandCategory, list[BackslashCommand]] = {}
    for cmd in _commands.values():
        by_category.setdefault(cmd.category, []).append(cmd)
    return by_category


@overload
def backslash_command(func: CommandFunc, /) -> CommandFunc: ...


@overload
def backslash_command(
    *,
    char: str,
    name: str | None = None,
    takes_args: bool = False,
    position: CommandPosition = CommandPosition.STANDALONE,
    category: CommandCategory = CommandCategory.SESSION,
    aliases: Sequence[str] | None = None,
) -> Callable[[CommandFunc], CommandFunc]: ...


def backslash_command(
    func: CommandFunc | None = None,
    *,
    char: str = "",
    name: str | None = None,
    takes_args: bool = False,
    position: CommandPosition = CommandPosition.STANDALONE,
    category: CommandCategory = CommandCategory.SESSION,
    aliases: Sequence[str] | None = None,
) -> CommandFunc | Callable[[CommandFunc], CommandFunc]:
    r"""
    Decorator to register a backslash command.

    Usage:
        @backslash_command(char="s", name="status")
        def cmd_status(ctx: CommandContext) -> CommandResult | None:
            '''Get status information from the server.'''
            ...

        @backslash_command(char=".", name="source", takes_args=True)
        def cmd_source(ctx: CommandContext) -> CommandResult | None:
            '''Execute an SQL script file.'''
            ...

    Args:
        char: The shortcut character (e.g., "s" for \s)
        name: The command name (defaults to function name without "cmd_" prefix)
        takes_args: Whether the command accepts arguments
        position: Where the command can appear (standalone, sql_suffix, both)
        category: Command category for help organization
        aliases: Additional characters that trigger this command
    """

    def _register(f: CommandFunc) -> CommandFunc:
        cmd_name = name or f.__name__.replace("cmd_", "")
        cmd = BackslashCommand(
            name=cmd_name,
            char=char,
            func=f,
            description=(f.__doc__ or "").strip().split("\n")[0],
            takes_args=takes_args,
            position=position,
            category=category,
            aliases=tuple(aliases) if aliases else (),
        )

        # Register by name
        _commands[cmd_name] = cmd

        # Register by character
        if char:
            _char_map[char] = cmd

        # Register aliases
        for alias in cmd.aliases:
            _char_map[alias] = cmd

        return f

    if func is not None:
        return _register(func)
    return _register
