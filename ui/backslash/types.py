"""Type definitions for backslash commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

if TYPE_CHECKING:
    from database import DatabaseService


class CommandPosition(Enum):
    """Where a command can appear."""

    STANDALONE = "standalone"  # Standalone command: \s
    SQL_SUFFIX = "sql_suffix"  # At end of SQL: SELECT * FROM t\G
    BOTH = "both"  # Both positions allowed


class CommandCategory(Enum):
    """Command categories for help organization."""

    CONNECTION = "connection"  # Connection related: \r
    DISPLAY = "display"  # Display related: \W, \w
    FILE = "file"  # File related: \., \T
    QUERY = "query"  # Query related: \g, \G, \d
    SESSION = "session"  # Session related: \s
    HELP = "help"  # Help commands: \?, \h


@dataclass
class CommandContext:
    """Context passed to command execution."""

    db_service: DatabaseService | None
    sql_buffer: str = ""  # Current SQL buffer (for SQL_SUFFIX commands)
    args: str = ""  # Command arguments
    raw_input: str = ""  # Original raw input


@dataclass
class CommandResult:
    """Result of command execution."""

    success: bool = True
    message: str = ""
    should_continue: bool = True  # Whether to continue the main loop
    output: Any = None  # Optional output data


# Type alias for command functions
CommandFunc = Callable[[CommandContext], CommandResult | None]


@dataclass(frozen=True, slots=True)
class BackslashCommand:
    """Definition of a backslash command."""

    name: str  # Command name: "status", "source", etc.
    char: str  # Shortcut character: "s", ".", etc.
    func: CommandFunc  # Execution function
    description: str  # Help description
    takes_args: bool = False  # Whether command accepts arguments
    position: CommandPosition = CommandPosition.STANDALONE
    category: CommandCategory = CommandCategory.SESSION
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def format_usage(self) -> str:
        """Format command for help display."""
        char_part = f"\\{self.char}" if self.char else ""
        name_part = f" ({self.name})" if self.name != self.char else ""
        return f"{char_part}{name_part}"
