"""Database result formatting and display utilities."""

from __future__ import annotations

from typing import Any

from rich.table import Table
from rich.text import Text

from database import QueryResult, QueryType, SchemaInfo, DatabaseError, format_error
from ui.console import console

format_error_for_console = format_error

# Explain hint constants
EXPLAIN_HINT_RESULT = "💡 [dim]Ctrl+E: Explain result[/dim]"
EXPLAIN_HINT_ERROR = "💡 [dim]Ctrl+E: Explain error[/dim]"


def _format_cell(cell):
    if cell is None:
        return "NULL"
    if isinstance(cell, bytes):
        try:
            return cell.decode("utf-8")
        except Exception:
            return cell.hex()
    return str(cell)


def print_table_from_rows(description, rows):
    columns = [desc[0] for desc in description]
    # 计算每列最大宽度
    col_widths = [len(str(col)) for col in columns]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(_format_cell(cell)) if cell is not None else 4)
    col_widths = [w + 2 for w in col_widths]
    sep = "+" + "+".join("-" * w for w in col_widths) + "+"
    print(sep)
    header = "|" + "|".join(" " + str(col).ljust(col_widths[i] - 1) for i, col in enumerate(columns)) + "|"
    print(header)
    print(sep)
    for row in rows:
        print(
            "|"
            + "|".join(
                " " + (_format_cell(cell) if cell is not None else "NULL").ljust(col_widths[i] - 1)
                for i, cell in enumerate(row)
            )
            + "|"
        )
    print(sep)


def print_vertical_table_from_rows(description, rows):
    columns = [desc[0] for desc in description]
    maxlen = max(len(col) for col in columns) if columns else 0
    for idx, row in enumerate(rows, 1):
        print(f"*************************** {idx}. row ***************************")
        for col, cell in zip(columns, row):
            print(f"{col.rjust(maxlen)}: {_format_cell(cell)}")


class DatabaseResultFormatter:
    """Formats and displays database query results."""

    @staticmethod
    def format_query_result(result: QueryResult, sql: str = "", use_vertical: bool = False) -> None:
        """
        Format and display query result.

        Args:
            result: Query execution result
            sql: Original SQL query (for context)
            use_vertical: Whether to use vertical format (determined by caller)
        """
        if not result.success:
            DatabaseResultFormatter._display_query_error(result)
            return

        if result.query_type in [
            QueryType.SELECT,
            QueryType.SHOW,
            QueryType.DESCRIBE,
            QueryType.DESC,
            QueryType.EXPLAIN,
        ]:
            DatabaseResultFormatter._display_query_data(result, sql, use_vertical)
        else:
            DatabaseResultFormatter._display_command_result(result)

    @staticmethod
    def _display_query_data(result: QueryResult, sql: str, use_vertical: bool) -> None:
        """Display results from SELECT-type queries."""
        if not result.has_data:
            empty_text = f"Empty set ({result.execution_time:.3f} sec)"
            from ui.repl import ShellREPL

            if ShellREPL.is_llm_configured():
                console.print(f"{empty_text} {EXPLAIN_HINT_RESULT}")
            else:
                console.print(empty_text)
            return
        # Use the vertical format flag determined by caller

        if use_vertical:
            # Use existing vertical table formatter
            if result.columns:
                # Convert columns to description format expected by print functions
                description = [(col,) for col in result.columns]
                print_vertical_table_from_rows(description, result.rows)
            else:
                # Fallback for results without column info
                for i, row in enumerate(result.rows, 1):
                    console.print(f"[cyan]Row {i}:[/cyan]")
                    if isinstance(row, (list, tuple)):
                        for j, value in enumerate(row):
                            console.print(f"  Field {j + 1}: {value}")
                    else:
                        console.print(f"  {row}")
                    console.print()
        else:
            # Use existing horizontal table formatter
            if result.columns:
                description = [(col,) for col in result.columns]
                print_table_from_rows(description, result.rows)
            else:
                # Simple table for results without column names
                table = Table()

                # Add columns based on first row
                if result.rows:
                    first_row = result.rows[0]
                    if isinstance(first_row, (list, tuple)):
                        for i in range(len(first_row)):
                            table.add_column(f"Column{i + 1}", style="cyan")
                    else:
                        table.add_column("Value", style="cyan")

                # Add rows
                for row in result.rows:
                    if isinstance(row, (list, tuple)):
                        table.add_row(*[str(cell) for cell in row])
                    else:
                        table.add_row(str(row))

                console.print(table)

        # Show query stats if available
        if result.execution_time:
            timing_text = (
                f"({len(result.rows)} row{'s' if len(result.rows) != 1 else ''} in {result.execution_time:.3f} sec)"
            )
            from ui.repl import ShellREPL

            if ShellREPL.is_llm_configured():
                console.print(f"{timing_text} {EXPLAIN_HINT_RESULT}")
            else:
                console.print(timing_text)

    @staticmethod
    def _display_command_result(result: QueryResult) -> None:
        """Display results from non-SELECT commands."""
        if result.query_type == QueryType.USE:
            row_text = "Database changed"
            console.print(f"[green]✓[/green] {row_text}")
            return
        elif result.affected_rows is not None:
            if result.query_type in [
                QueryType.CREATE,
                QueryType.INSERT,
                QueryType.UPDATE,
                QueryType.DELETE,
                QueryType.REPLACE,
            ]:
                row_text = f"{result.affected_rows} row{'s' if result.affected_rows != 1 else ''} affected"
            else:
                row_text = "Query OK"
        else:
            row_text = "Query OK"
        if result.execution_time:
            row_text += f" ({result.execution_time:.3f} sec)"
        from ui.repl import ShellREPL

        if ShellREPL.is_llm_configured():
            console.print(f"[green]✓[/green] {row_text} {EXPLAIN_HINT_RESULT}")
        else:
            console.print(f"[green]✓[/green] {row_text}")

    @staticmethod
    def _display_query_error(result: QueryResult) -> None:
        """Display query execution error."""
        error_text = f"ERROR: {result.error}"
        from ui.repl import ShellREPL

        if ShellREPL.is_llm_configured():
            console.print(f"[red]{error_text}[/red] {EXPLAIN_HINT_ERROR}")
        else:
            console.print(f"[red]{error_text}[/red]")


class ConnectionInfoFormatter:
    """Formats database connection information."""

    @staticmethod
    def format_connection_info(info: dict[str, Any]) -> None:
        """Display connection information in a table."""
        if not info.get("connected"):
            console.print("[yellow]Not connected to any database.[/yellow]")
            return

        table = Table(title="Database Connection")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        # Format display names and values
        display_mapping = {
            "engine": "Engine",
            "host": "Host",
            "port": "Port",
            "user": "User",
            "database": "Current Database",
            "transaction_state": "Transaction State",
            "autocommit": "Autocommit",
            "ssl_enabled": "SSL Enabled",
        }

        for key, value in info.items():
            if key == "connected":
                continue

            display_name = display_mapping.get(key, key.replace("_", " ").title())

            # Format specific values
            if key == "autocommit":
                display_value = "ON" if value else "OFF"
            elif key == "ssl_enabled":
                display_value = "Yes" if value else "No"
            elif value is None:
                display_value = "Not set"
            else:
                display_value = str(value)

            table.add_row(display_name, display_value)

        console.print(table)


class SchemaFormatter:
    """Formats database schema information."""

    @staticmethod
    def format_database_list(databases: list[str]) -> None:
        """Display list of databases."""
        if not databases:
            console.print("[yellow]No databases found.[/yellow]")
            return

        table = Table(title="Databases")
        table.add_column("Database Name", style="cyan")

        for db_name in databases:
            table.add_row(db_name)

        console.print(table)

    @staticmethod
    def format_table_list(schema_info: SchemaInfo) -> None:
        """Display list of tables."""
        if not schema_info.tables:
            console.print("[yellow]No tables found in current database.[/yellow]")
            return

        table = Table(title=f"Tables in {schema_info.current_database or 'Current Database'}")
        table.add_column("Table Name", style="cyan")

        for table_name in schema_info.tables:
            table.add_row(table_name)

        console.print(table)

    @staticmethod
    def format_table_structure(table_name: str, structure: list[tuple[Any, ...]]) -> None:
        """Display table structure information."""
        if not structure:
            console.print(f"[yellow]No structure information available for table '{table_name}'.[/yellow]")
            return

        table = Table(title=f"Structure of table '{table_name}'")

        # Standard MySQL DESCRIBE output columns
        table.add_column("Field", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Null", style="green")
        table.add_column("Key", style="magenta")
        table.add_column("Default", style="white")
        table.add_column("Extra", style="dim")

        for row in structure:
            table.add_row(*[str(cell) for cell in row])

        console.print(table)


class TransactionFormatter:
    """Formats transaction-related information."""

    @staticmethod
    def format_transaction_status(transaction_state: str, autocommit: bool, title: str = "Transaction Status") -> None:
        """Display transaction status information."""
        table = Table(title=title)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Transaction State", transaction_state)
        table.add_row("Autocommit", "ON" if autocommit else "OFF")

        console.print(table)


class HistoryFormatter:
    """Formats SQL execution history."""

    @staticmethod
    def format_history(history_entries: list[dict[str, Any]], limit: int = 10) -> None:
        """Display SQL execution history."""
        if not history_entries:
            console.print("[yellow]No SQL history available.[/yellow]")
            return

        table = Table(title=f"Recent SQL History (last {len(history_entries)} entries)")
        table.add_column("#", style="dim", width=3)
        table.add_column("Timestamp", style="cyan", width=19)
        table.add_column("SQL", style="white")
        table.add_column("Status", style="green", width=8)

        for i, entry in enumerate(reversed(history_entries), 1):
            sql = entry.get("sql", "")
            truncated_sql = sql[:80] + ("..." if len(sql) > 80 else "")

            status_style = "green" if entry.get("status") == "success" else "red"

            table.add_row(
                str(i),
                entry.get("timestamp", "Unknown"),
                truncated_sql,
                Text(entry.get("status", "Unknown"), style=status_style),
            )

        console.print(table)


class ErrorFormatter:
    """Formats database errors for display."""

    @staticmethod
    def display_error(error: DatabaseError) -> None:
        """Display database error with appropriate formatting."""
        formatted_msg = format_error_for_console(error)
        console.print(f"[red]{formatted_msg}[/red]")

    @staticmethod
    def display_connection_error(error: DatabaseError) -> None:
        """Display connection-specific error."""
        ErrorFormatter.display_error(error)

    @staticmethod
    def display_query_error(error: DatabaseError) -> None:
        """Display query-specific error."""
        ErrorFormatter.display_error(error)


# Convenience functions for common formatting operations
def format_and_display_result(result: QueryResult, sql: str = "", use_vertical: bool = False) -> None:
    """Convenience function to format and display query result."""
    DatabaseResultFormatter.format_query_result(result, sql, use_vertical)


def display_connection_info(info: dict[str, Any]) -> None:
    """Convenience function to display connection information."""
    ConnectionInfoFormatter.format_connection_info(info)


def display_database_error(error: DatabaseError) -> None:
    """Convenience function to display database error."""
    formatted_msg = format_error_for_console(error)
    from ui.repl import ShellREPL

    if ShellREPL.is_llm_configured():
        console.print(f"[red]{formatted_msg}[/red] {EXPLAIN_HINT_ERROR}")
    else:
        console.print(f"[red]{formatted_msg}[/red]")
