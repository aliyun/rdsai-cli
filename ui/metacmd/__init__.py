"""Meta commands for the shell interface."""

from ui.metacmd.registry import (
    MetaCommand,
    MetaCmdFunc,
    SubCommand,
    get_meta_command,
    get_meta_commands,
    meta_command,
)

# Import command modules to trigger registration
from ui.metacmd import basic  # noqa: F401
from ui.metacmd import benchmark  # noqa: F401
from ui.metacmd import connect  # noqa: F401
from ui.metacmd import explain  # noqa: F401
from ui.metacmd import mcp  # noqa: F401
from ui.metacmd import model  # noqa: F401
from ui.metacmd import research  # noqa: F401
from ui.metacmd import setup  # noqa: F401

__all__ = [
    "MetaCommand",
    "MetaCmdFunc",
    "SubCommand",
    "get_meta_command",
    "get_meta_commands",
    "meta_command",
]
