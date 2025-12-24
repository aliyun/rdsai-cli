"""Source command implementation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ui.backslash.registry import backslash_command
from ui.backslash.types import (
    CommandCategory,
    CommandContext,
    CommandResult,
)
from ui.console import console
from utils.logging import logger

if TYPE_CHECKING:
    from database import DatabaseService


@backslash_command(
    char=".",
    name="source",
    takes_args=True,
    category=CommandCategory.FILE,
)
def cmd_source(ctx: CommandContext) -> CommandResult | None:
    """Execute an SQL script file. Takes a file name as an argument."""
    if not ctx.args:
        console.print("[red]Usage: \\. <filename> | source <filename>[/red]")
        return CommandResult(success=False)

    filepath = Path(ctx.args).expanduser().resolve()

    if not filepath.exists():
        console.print(f"[red]Failed to open file '{ctx.args}', error: No such file[/red]")
        return CommandResult(success=False)

    if not filepath.is_file():
        console.print(f"[red]Failed to open file '{ctx.args}', error: Is a directory[/red]")
        return CommandResult(success=False)

    if not ctx.db_service or not ctx.db_service.is_connected():
        console.print("[red]Not connected to server.[/red]")
        return CommandResult(success=False)

    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = filepath.read_text(encoding="latin-1")
        except Exception as e:
            console.print(f"[red]Failed to read file: {e}[/red]")
            return CommandResult(success=False)
    except Exception as e:
        console.print(f"[red]Failed to read file: {e}[/red]")
        return CommandResult(success=False)

    # Execute the script
    return _execute_script(ctx.db_service, content, filepath.name)


def _execute_script(
    db_service: DatabaseService,
    content: str,
    filename: str,
) -> CommandResult:
    """Execute SQL script content."""
    from ui.backslash.commands.delimiter import get_delimiter

    statements = _split_sql_statements(content, get_delimiter())

    if not statements:
        console.print(f"[yellow]No statements found in {filename}[/yellow]")
        return CommandResult(success=True)

    console.print(f"[dim]Executing {len(statements)} statement(s) from {filename}...[/dim]")

    success_count = 0
    error_count = 0

    for i, stmt in enumerate(statements, 1):
        stmt = stmt.strip()
        if not stmt:
            continue

        try:
            result = db_service.execute_query(stmt)
            if result.success:
                success_count += 1
                # Show affected rows for non-SELECT statements
                if result.affected_rows is not None and result.affected_rows >= 0:
                    logger.debug(
                        "Statement {i}: {affected} row(s) affected",
                        i=i,
                        affected=result.affected_rows,
                    )
            else:
                error_count += 1
                console.print(f"[red]ERROR at line {i}: {result.error}[/red]")
        except Exception as e:
            error_count += 1
            console.print(f"[red]ERROR at line {i}: {e}[/red]")
            logger.exception("Script execution error at statement {i}", i=i)

    # Summary
    if error_count == 0:
        console.print(f"[green]Query OK, {success_count} statement(s) executed[/green]")
    else:
        console.print(f"[yellow]{success_count} statement(s) succeeded, {error_count} failed[/yellow]")

    return CommandResult(success=error_count == 0)


def _split_sql_statements(content: str, delimiter: str = ";") -> list[str]:
    """
    Split SQL content into individual statements.

    Handles:
    - Standard delimiter (;)
    - Custom delimiters (for stored procedures)
    - DELIMITER commands within the script
    - Comments (-- and #)
    - Multi-line statements
    """
    statements: list[str] = []
    current: list[str] = []
    current_delimiter = delimiter
    in_string: str | None = None
    in_comment = False

    lines = content.split("\n")

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comments at line level
        if not stripped:
            if current:
                current.append(line)
            continue

        if stripped.startswith("--") or stripped.startswith("#"):
            continue

        # Handle DELIMITER command
        if stripped.upper().startswith("DELIMITER"):
            # Flush current statement if any
            if current:
                stmt = "\n".join(current).strip()
                if stmt and not stmt.upper().startswith("DELIMITER"):
                    statements.append(stmt)
                current = []

            # Extract new delimiter
            parts = stripped.split(maxsplit=1)
            if len(parts) > 1:
                current_delimiter = parts[1].strip()
            continue

        # Add line to current statement
        current.append(line)

        # Check if line ends with delimiter (simple check)
        # Note: This is simplified and doesn't handle delimiters inside strings
        if stripped.endswith(current_delimiter):
            stmt = "\n".join(current)
            # Remove the delimiter
            if stmt.rstrip().endswith(current_delimiter):
                stmt = stmt.rstrip()[: -len(current_delimiter)].strip()
            if stmt:
                statements.append(stmt)
            current = []

    # Handle last statement without delimiter
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)

    return statements
