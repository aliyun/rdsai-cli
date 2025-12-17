from __future__ import annotations


class CLIException(Exception):
    """Base exception class for MySQL AI CLI."""

    pass


class ConfigError(CLIException):
    """Configuration error."""

    pass


class Reload(CLIException):
    """Signal to reload configuration and restart the application."""

    pass
