"""Meta command registry and decorator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from ui.repl import ShellREPL

type MetaCmdFunc = Callable[["ShellREPL", list[str]], None | Awaitable[None]]
"""
A function that runs as a meta command.

Raises:
    LLMNotSet: When the LLM is not set.
    ChatProviderError: When the LLM provider returns an error.
    asyncio.CancelledError: When the command is interrupted by user.

This is quite similar to the `Loop.run` method.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class SubCommand:
    """A subcommand of a meta command."""

    name: str
    """Primary name of the subcommand."""
    aliases: list[str] = field(default_factory=list)
    """Alternative names for the subcommand."""
    description: str = ""
    """Description of what the subcommand does."""
    arg_completer: Callable[[list[str]], list[str]] | None = None
    """Optional function to provide argument completions. Receives current args, returns list of completions."""

    def all_names(self) -> list[str]:
        """Get all names (primary + aliases) for this subcommand."""
        return [self.name] + self.aliases


@dataclass(frozen=True, slots=True, kw_only=True)
class MetaCommand:
    name: str
    description: str
    func: MetaCmdFunc
    aliases: list[str]
    loop_only: bool
    subcommands: list[SubCommand] = field(default_factory=list)
    """List of subcommands supported by this command."""

    def slash_name(self):
        """/name (aliases)"""
        if self.aliases:
            return f"/{self.name} ({', '.join(self.aliases)})"
        return f"/{self.name}"

    def get_subcommand(self, name: str) -> SubCommand | None:
        """Get a subcommand by name or alias."""
        name_lower = name.lower()
        for subcmd in self.subcommands:
            if subcmd.name.lower() == name_lower or name_lower in [a.lower() for a in subcmd.aliases]:
                return subcmd
        return None


# primary name -> MetaCommand
_meta_commands: dict[str, MetaCommand] = {}
# primary name or alias -> MetaCommand
_meta_command_aliases: dict[str, MetaCommand] = {}


def get_meta_command(name: str) -> MetaCommand | None:
    return _meta_command_aliases.get(name)


def get_meta_commands() -> list[MetaCommand]:
    """Get all unique primary meta commands (without duplicating aliases)."""
    return list(_meta_commands.values())


@overload
def meta_command(func: MetaCmdFunc, /) -> MetaCmdFunc: ...


@overload
def meta_command(
    *,
    name: str | None = None,
    aliases: Sequence[str] | None = None,
    loop_only: bool = False,
    subcommands: Sequence[SubCommand] | None = None,
) -> Callable[[MetaCmdFunc], MetaCmdFunc]: ...


def meta_command(
    func: MetaCmdFunc | None = None,
    *,
    name: str | None = None,
    aliases: Sequence[str] | None = None,
    loop_only: bool = False,
    subcommands: Sequence[SubCommand] | None = None,
) -> (
    MetaCmdFunc
    | Callable[
        [MetaCmdFunc],
        MetaCmdFunc,
    ]
):
    """Decorator to register a meta command with optional custom name, aliases, and subcommands.

    Usage examples:
      @meta_command
      def help(app: App, args: list[str]): ...

      @meta_command(name="run")
      def start(app: App, args: list[str]): ...

      @meta_command(aliases=["h", "?", "assist"])
      def help(app: App, args: list[str]): ...

      @meta_command(
          subcommands=[
              SubCommand(name="check", aliases=[], description="Check for updates"),
              SubCommand(name="auto-check", aliases=["autocheck"], description="Manage auto-check"),
          ]
      )
      def upgrade(app: App, args: list[str]): ...
    """

    def _register(f: MetaCmdFunc):
        primary = name or f.__name__
        alias_list = list(aliases) if aliases else []
        subcmd_list = list(subcommands) if subcommands else []

        # Create the primary command with aliases and subcommands
        cmd = MetaCommand(
            name=primary,
            description=(f.__doc__ or "").strip(),
            func=f,
            aliases=alias_list,
            loop_only=loop_only,
            subcommands=subcmd_list,
        )

        # Register primary command
        _meta_commands[primary] = cmd
        _meta_command_aliases[primary] = cmd

        # Register aliases pointing to the same command
        for alias in alias_list:
            _meta_command_aliases[alias] = cmd

        return f

    if func is not None:
        return _register(func)
    return _register
