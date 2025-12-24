"""Backslash command implementations.

Import all command modules to trigger registration.
"""

from ui.backslash.commands import (
    help,  # \?, \h
    status,  # \s
    source,  # \.
    delimiter,  # \d
    connect,  # \r
    execute,  # \g, \G
    quit,  # \q
)

__all__ = [
    "help",
    "status",
    "source",
    "delimiter",
    "connect",
    "execute",
    "quit",
]
