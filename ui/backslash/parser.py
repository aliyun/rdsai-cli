"""Backslash command parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .registry import get_backslash_command
from .types import BackslashCommand, CommandPosition

if TYPE_CHECKING:
    pass


@dataclass
class ParseResult:
    """Result of parsing input for backslash commands."""

    command: BackslashCommand | None = None
    sql_before: str = ""  # SQL before the command (for SQL_SUFFIX)
    args: str = ""  # Command arguments
    is_backslash_command: bool = False
    error: str = ""


class BackslashParser:
    """Parser for backslash commands."""

    # Match standalone backslash command: \s, \. file.sql, \r db host
    # Captures: (1) command char, (2) rest of line as args
    STANDALONE_PATTERN = re.compile(r"^\\([a-zA-Z.#!?])(.*)$")

    def parse(self, input_text: str) -> ParseResult:
        r"""
        Parse input text for backslash commands.

        Returns ParseResult with:
        - is_backslash_command=True if a valid command was found
        - command: the BackslashCommand object
        - sql_before: SQL before the command (for \G style)
        - args: command arguments
        - error: error message if parsing failed
        """
        input_text = input_text.strip()

        if not input_text:
            return ParseResult()

        # 1. Check for standalone backslash command (\s, \. file.sql, etc.)
        if input_text.startswith("\\"):
            return self._parse_standalone(input_text)

        # 2. Not a backslash command
        return ParseResult()

    def _parse_standalone(self, input_text: str) -> ParseResult:
        """Parse standalone backslash command."""
        match = self.STANDALONE_PATTERN.match(input_text)
        if not match:
            return ParseResult(
                is_backslash_command=True,
                error=f"Invalid backslash command: {input_text[:20]}",
            )

        cmd_char = match.group(1)
        args = match.group(2).strip()

        cmd = get_backslash_command(cmd_char)
        if not cmd:
            return ParseResult(
                is_backslash_command=True,
                error=f"Unknown command: \\{cmd_char}. Type \\? for help.",
            )

        # Check position restriction
        if cmd.position == CommandPosition.SQL_SUFFIX:
            return ParseResult(
                is_backslash_command=True,
                error=f"\\{cmd_char} can only be used at end of SQL statement",
            )

        return ParseResult(
            command=cmd,
            args=args,
            is_backslash_command=True,
        )


# Global parser instance
_parser = BackslashParser()


def parse_backslash_command(input_text: str) -> ParseResult:
    """Parse input for backslash commands using global parser."""
    return _parser.parse(input_text)
