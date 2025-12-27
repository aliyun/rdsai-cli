"""Shell completers - meta command and SQL completion."""

from __future__ import annotations

import re
from threading import Lock
from typing import TYPE_CHECKING, Optional, override
from collections.abc import Generator

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from database import DatabaseService


class MetaCommandCompleter(Completer):
    """Completer for meta commands (slash commands) with subcommand support.

    - Shows one line per meta command in the form: "/name (alias1, alias2)"
    - Matches by primary name or any alias while inserting the canonical "/name"
    - Supports subcommand completion: "/command subcommand"
    - Supports argument completion for subcommands with arg_completer
    """

    @override
    def get_completions(self, document, complete_event):
        from ui.metacmd import get_meta_command

        text_before = document.text_before_cursor
        text_after = document.text_after_cursor

        # Only autocomplete when the input buffer has no other content after cursor.
        if text_after.strip():
            return

        # Parse input state
        ends_with_space = text_before.rstrip() != text_before
        parts = text_before.split()
        if not parts or not parts[0].startswith("/"):
            return

        cmd_name = parts[0][1:]
        num_parts = len(parts)

        # Case 1: Only command name (len(parts) == 1)
        if num_parts == 1:
            if ends_with_space:
                # Command followed by space - show subcommands
                yield from self._complete_subcommands(cmd_name)
            else:
                # Completing main command name
                yield from self._complete_main_command(parts[0])
            return

        # Case 2: Command + subcommand/arguments (len(parts) >= 2)
        cmd = get_meta_command(cmd_name)
        if not cmd or not cmd.subcommands:
            return

        # Completing subcommand name (len(parts) == 2 and not ends_with_space)
        if num_parts == 2 and not ends_with_space:
            yield from self._complete_subcommand_name(cmd, parts[1])
            return

        # Completing arguments (len(parts) == 2 with space, or len(parts) >= 3)
        # Get subcommand from parts[1]
        subcmd = cmd.get_subcommand(parts[1]) if num_parts >= 2 else None
        if subcmd and subcmd.arg_completer:
            # Calculate current token and args_so_far based on state
            if ends_with_space:
                current_token = ""
                args_so_far = parts[2:] if num_parts >= 3 else []
            else:
                current_token = parts[-1]
                args_so_far = parts[2:-1] if num_parts >= 3 else []

            yield from self._complete_arguments(subcmd, cmd, current_token, args_so_far)

    @staticmethod
    def _complete_main_command(token: str):
        """Complete main command name."""
        from ui.metacmd import get_meta_commands

        typed = token[1:]
        typed_lower = typed.lower()

        for cmd in sorted(get_meta_commands(), key=lambda c: c.name):
            names = [cmd.name] + list(cmd.aliases)
            if typed == "" or any(n.lower().startswith(typed_lower) for n in names):
                yield Completion(
                    text=f"/{cmd.name}",
                    start_position=-len(token),
                    display=cmd.slash_name(),
                    display_meta=cmd.description,
                )

    @staticmethod
    def _complete_subcommands(cmd_name: str):
        """Show all subcommands for a command."""
        from ui.metacmd import get_meta_command

        cmd = get_meta_command(cmd_name)
        if not cmd or not cmd.subcommands:
            return

        for subcmd in sorted(cmd.subcommands, key=lambda s: s.name):
            display = subcmd.name
            if subcmd.aliases:
                display += f" ({', '.join(subcmd.aliases)})"
            yield Completion(
                text=subcmd.name,
                start_position=0,
                display=display,
                display_meta=subcmd.description or f"Subcommand of /{cmd.name}",
            )

    @staticmethod
    def _complete_subcommand_name(cmd, current_token: str):
        """Complete subcommand name with partial matching."""
        typed_lower = current_token.lower()

        for subcmd in sorted(cmd.subcommands, key=lambda s: s.name):
            names = subcmd.all_names()
            if not current_token or any(n.lower().startswith(typed_lower) for n in names):
                display = subcmd.name
                if subcmd.aliases:
                    display += f" ({', '.join(subcmd.aliases)})"
                yield Completion(
                    text=subcmd.name,
                    start_position=-len(current_token),
                    display=display,
                    display_meta=subcmd.description or f"Subcommand of /{cmd.name}",
                )

    @staticmethod
    def _complete_arguments(subcmd, cmd, current_token: str, args_so_far: list[str]):
        """Complete arguments for a subcommand."""
        typed_lower = current_token.lower()

        try:
            completions = subcmd.arg_completer(args_so_far)
            for comp in completions:
                if not current_token or comp.lower().startswith(typed_lower):
                    yield Completion(
                        text=comp,
                        start_position=-len(current_token),
                        display=comp,
                        display_meta=f"Argument for /{cmd.name} {subcmd.name}",
                    )
        except Exception:
            # If arg_completer fails, don't provide completions
            pass


class SQLCompleter(Completer):
    """SQL intelligent completion integrated with shell.

    Provides completion for:
    - SQL keywords
    - Table names (from database)
    - Column names (context-aware)
    """

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self._sql_keywords = self._get_sql_keywords()
        self._cached_tables: list[str] = []
        self._cached_columns: dict[str, list[str]] = {}
        self._cache_valid = False
        self._cache_lock = Lock()

    def _get_sql_keywords(self) -> list[str]:
        """Get list of SQL keywords for completion."""
        return [
            # Core SQL keywords
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "FROM",
            "WHERE",
            "JOIN",
            "INNER",
            "LEFT",
            "RIGHT",
            "OUTER",
            "ON",
            "AS",
            "AND",
            "OR",
            "NOT",
            "NULL",
            "IS",
            "LIKE",
            "IN",
            "BETWEEN",
            "EXISTS",
            "ORDER",
            "BY",
            "GROUP",
            "HAVING",
            "LIMIT",
            "OFFSET",
            "DISTINCT",
            "ALL",
            "ANY",
            "SOME",
            "UNION",
            "INTERSECT",
            "EXCEPT",
            "CASE",
            "WHEN",
            "THEN",
            "ELSE",
            "END",
            "IF",
            "IFNULL",
            "ISNULL",
            # DDL keywords
            "CREATE",
            "ALTER",
            "DROP",
            "TABLE",
            "INDEX",
            "VIEW",
            "DATABASE",
            "SCHEMA",
            "COLUMN",
            "CONSTRAINT",
            "PRIMARY",
            "KEY",
            "FOREIGN",
            "REFERENCES",
            "UNIQUE",
            "CHECK",
            "DEFAULT",
            "AUTO_INCREMENT",
            "SERIAL",
            # DML keywords
            "INTO",
            "VALUES",
            "SET",
            "REPLACE",
            "TRUNCATE",
            # Data types
            "INT",
            "INTEGER",
            "BIGINT",
            "SMALLINT",
            "TINYINT",
            "DECIMAL",
            "NUMERIC",
            "FLOAT",
            "DOUBLE",
            "REAL",
            "CHAR",
            "VARCHAR",
            "TEXT",
            "BLOB",
            "DATE",
            "TIME",
            "DATETIME",
            "TIMESTAMP",
            "BOOLEAN",
            "BOOL",
            "JSON",
            "JSONB",
            # Transaction keywords
            "BEGIN",
            "START",
            "TRANSACTION",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT",
            # Utility commands
            "SHOW",
            "DESCRIBE",
            "DESC",
            "EXPLAIN",
            "USE",
            "SET",
            "REVOKE",
            # Functions
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
            "CONCAT",
            "SUBSTRING",
            "LENGTH",
            "UPPER",
            "LOWER",
            "TRIM",
            "NOW",
            "CURRENT_TIMESTAMP",
            "CURRENT_DATE",
        ]

    def get_completions(self, document: Document, complete_event) -> Generator[Completion, None, None]:
        """Get SQL completions based on current context."""
        if not self.db_service.is_connected():
            return

        text = document.text_before_cursor

        # Only provide SQL completions if we detect SQL context
        if not self._is_sql_context(text):
            return

        # Get the current word being typed
        word = self._get_current_word(text)
        if not word:
            return

        word_lower = word.lower()

        # Refresh cache if needed
        self._refresh_cache_if_needed()

        # Generate completions
        completions = []

        # 1. SQL Keywords
        for keyword in self._sql_keywords:
            if keyword.lower().startswith(word_lower):
                completions.append(
                    Completion(text=keyword, start_position=-len(word), display=keyword, display_meta="SQL keyword")
                )

        # 2. Table names
        for table in self._cached_tables:
            if table.lower().startswith(word_lower):
                completions.append(
                    Completion(text=table, start_position=-len(word), display=table, display_meta="table")
                )

        # 3. Column names (context-aware)
        current_table = self._get_current_table_context(text)
        if current_table and current_table in self._cached_columns:
            for column in self._cached_columns[current_table]:
                if column.lower().startswith(word_lower):
                    completions.append(
                        Completion(
                            text=column,
                            start_position=-len(word),
                            display=column,
                            display_meta=f"column ({current_table})",
                        )
                    )
        else:
            # Show columns from all tables if no specific table context
            for table, columns in self._cached_columns.items():
                for column in columns:
                    if column.lower().startswith(word_lower):
                        completions.append(
                            Completion(
                                text=column, start_position=-len(word), display=column, display_meta=f"column ({table})"
                            )
                        )

        # Sort completions: keywords first, then tables, then columns
        def sort_key(comp):
            if comp.display_meta == "SQL keyword":
                return (0, comp.text)
            elif comp.display_meta == "table":
                return (1, comp.text)
            else:
                return (2, comp.text)

        completions.sort(key=sort_key)

        # Limit number of completions to avoid overwhelming user
        yield from completions[:50]

    def _is_sql_context(self, text: str) -> bool:
        """Check if current context suggests SQL input."""
        if not text.strip():
            return False

        # Check for SQL keywords at the beginning
        text_upper = text.strip().upper()
        sql_starters = [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "SHOW",
            "DESCRIBE",
            "DESC",
            "EXPLAIN",
            "USE",
        ]

        for starter in sql_starters:
            if text_upper.startswith(starter):
                return True

        # Check if it looks like a continuation of SQL
        if any(keyword in text_upper for keyword in ["FROM", "WHERE", "JOIN", "SET"]):
            return True

        return False

    def _get_current_word(self, text: str) -> str:
        """Extract the current word being typed."""
        # Find word boundaries
        pattern = r"[A-Za-z0-9_`]+"
        matches = list(re.finditer(pattern, text))

        if not matches:
            return ""

        # Get the last match that ends at or before cursor
        cursor_pos = len(text)
        for match in reversed(matches):
            if match.end() <= cursor_pos:
                # Check if cursor is within this word or immediately after it
                if match.end() == cursor_pos or (match.start() <= cursor_pos <= match.end()):
                    return match.group()
                break

        return ""

    def _get_current_table_context(self, text: str) -> Optional[str]:
        """Try to determine which table is being referenced in current context."""
        text_upper = text.upper()

        # Look for FROM clause
        from_match = re.search(r"\bFROM\s+([A-Za-z0-9_`]+)", text_upper)
        if from_match:
            return from_match.group(1).strip("`")

        # Look for UPDATE statement
        update_match = re.search(r"\bUPDATE\s+([A-Za-z0-9_`]+)", text_upper)
        if update_match:
            return update_match.group(1).strip("`")

        # Look for INSERT INTO
        insert_match = re.search(r"\bINSERT\s+INTO\s+([A-Za-z0-9_`]+)", text_upper)
        if insert_match:
            return insert_match.group(1).strip("`")

        return None

    def _refresh_cache_if_needed(self) -> None:
        """Refresh table and column cache if needed.

        Uses non-blocking lock to avoid blocking UI thread.
        If refresh is already in progress, uses existing cache.
        """
        # Fast path: cache is already valid
        if self._cache_valid:
            return

        # Try to acquire lock without blocking
        # If another thread is refreshing, skip and use existing cache
        if not self._cache_lock.acquire(blocking=False):
            return

        try:
            # Double-check after acquiring lock (another thread may have refreshed)
            if self._cache_valid:
                return

            self._refresh_tables()
            self._refresh_columns()
            self._cache_valid = True
        except Exception:
            # Cache refresh failure - will retry on next call
            pass
        finally:
            self._cache_lock.release()

    def _refresh_tables(self) -> None:
        """Refresh list of tables."""
        if not self.db_service.is_connected():
            return
        try:
            db_client = self.db_service.get_active_connection()
            if not db_client:
                return

            if hasattr(db_client, "engine_name"):
                db_client.execute("SHOW TABLES")

                tables = db_client.fetchall()
                self._cached_tables = [table[0] if isinstance(table, (list, tuple)) else str(table) for table in tables]
        except Exception as e:
            # Could log table refresh failure here if needed
            pass
            self._cached_tables = []

    def _refresh_columns(self) -> None:
        """Refresh column information for tables."""
        if not self.db_service.is_connected() or not self._cached_tables:
            return

        self._cached_columns = {}

        try:
            db_client = self.db_service.get_active_connection()
            if not db_client:
                return

            # Limit to first 10 tables to avoid too much overhead
            for table in self._cached_tables[:10]:
                try:
                    if hasattr(db_client, "engine_name"):
                        db_client.execute(f"DESCRIBE `{table}`")
                        columns = db_client.fetchall()
                        self._cached_columns[table] = [col[0] for col in columns]
                except Exception as e:
                    # Could log column fetch failure here if needed
                    pass
                    continue

        except Exception as e:
            # Could log column refresh failure here if needed
            pass

    def invalidate_cache(self) -> None:
        """Invalidate completion cache (call after DDL operations).

        Thread-safe: acquires lock to ensure consistent state.
        """
        with self._cache_lock:
            self._cache_valid = False
            self._cached_tables = []
            self._cached_columns = {}
