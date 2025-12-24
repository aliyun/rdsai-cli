"""Shell application core - main entry point for the interactive shell."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from database import DatabaseService, QueryHistory
from loop import LLMNotSet, LLMNotSupported, MaxStepsReached, RunCancelled, Loop, run_loop, NeoLoop
from loop.agent import load_agent
from loop.types import ContentPart
from ui.console import console
from ui.metacmd import get_meta_command
from ui.backslash import execute_backslash_command
from ui.prompt import CustomPromptSession
from ui.visualize import visualize
from utils.exceptions import APIStatusError, ChatProviderError, LLMInvocationError
from utils.logging import logger
from utils.term import ensure_new_line


class ShellREPL:
    """Main interactive shell REPL."""

    _current: ShellREPL | None = None

    def __init__(
        self,
        loop: Loop,
        welcome_info: list[WelcomeInfoItem] | None = None,
        db_service: DatabaseService | None = None,
        query_history: QueryHistory | None = None,
    ):
        self.loop = loop
        self._welcome_info = list(welcome_info or [])
        self._db_service = db_service
        self._query_history = query_history
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._exit_warned: bool = False  # Track if user was warned about uncommitted transaction
        self._explain_agent: NeoLoop | None = None  # Cached explain agent instance
        self._prompt_session: CustomPromptSession | None = None  # Reference to prompt session

    @classmethod
    def is_llm_configured(cls) -> bool:
        """Check if LLM is configured in the current REPL session.

        This class method can be called from anywhere to check the LLM configuration
        status of the currently active REPL instance.
        """
        return cls._current is not None and cls._current.llm_configured

    @classmethod
    def _set_current(cls, repl: ShellREPL | None) -> None:
        """Set the current REPL instance (internal use only)."""
        cls._current = repl

    @property
    def db_service(self) -> DatabaseService | None:
        """Get the database service instance."""
        return self._db_service

    @property
    def query_history(self) -> QueryHistory | None:
        """Get the query history instance."""
        return self._query_history

    @property
    def prompt_session(self) -> CustomPromptSession | None:
        """Get the prompt session."""
        return self._prompt_session

    @property
    def llm_configured(self) -> bool:
        """Check if LLM is configured."""
        return (
            isinstance(self.loop, NeoLoop)
            and self.loop.runtime.llm is not None
            and self.loop.runtime.llm.model_name != ""
        )

    @property
    def db_connected(self) -> bool:
        """Check if database is connected."""
        return self._db_service is not None and self._db_service.is_connected()

    async def run(self) -> bool:
        console.clear()
        _print_welcome_info(self.loop.name or "RDSAI CLI", self._welcome_info)

        # Set current REPL instance for global access
        self._set_current(self)

        try:
            with CustomPromptSession(
                status_provider=lambda: self.loop.status,
                db_service=self._db_service,
                on_thinking_toggle=self._on_thinking_toggle,
                on_explain_result=self._explain_last_sql_result,
            ) as prompt_session:
                self._prompt_session = prompt_session
                while True:
                    try:
                        ensure_new_line()
                        user_input = await prompt_session.prompt()
                    except KeyboardInterrupt:
                        logger.debug("Interrupted by Esc key")
                        console.print("[grey50]Tip: press Ctrl-C or send 'exit' to quit[/grey50]")
                        continue
                    except EOFError:
                        logger.debug("Exiting by EOF")
                        if self._check_uncommitted_transaction():
                            continue  # User chose not to exit
                        console.print("Bye!")
                        break

                    if not user_input:
                        continue
                    logger.debug("Got user input: {user_input}", user_input=user_input)

                    if user_input.command in ["exit", "quit", "/exit", "/quit"]:
                        logger.debug("Exiting by meta command")
                        if self._check_uncommitted_transaction():
                            continue  # User chose not to exit
                        console.print("Bye!")
                        break

                    # Reset exit warning flag when user performs other actions
                    self._exit_warned = False

                    if user_input.command.startswith("/"):
                        await self._run_meta_command(user_input.command[1:])
                        continue

                    # Check for backslash commands (\s, \., \q, etc.)
                    if user_input.command.startswith("\\"):
                        handled, should_exit = self._try_backslash_command(user_input.command)
                        if should_exit:
                            if self._check_uncommitted_transaction():
                                continue  # User chose not to exit
                            console.print("Bye!")
                            break
                        if handled:
                            continue

                    # Update current REPL instance (may have changed via /setup or /model)
                    self._set_current(self)

                    # Routing logic:
                    # 1. If LLM not configured, route all input to MySQL
                    # 2. If DB not connected, route all input to LLM
                    # 3. If neither configured, show warning
                    # 4. Otherwise, check if SQL statement and route accordingly

                    if not self.llm_configured and not self.db_connected:
                        console.print("[yellow]Neither LLM nor database connection is configured.[/yellow]")
                        console.print(
                            "[yellow]Use /setup to configure LLM or /connect to connect to a database.[/yellow]"
                        )
                        continue

                    if not self.llm_configured:
                        # LLM not configured, route all input to database
                        if self._db_service and self._db_service.is_connected():
                            if self._db_service.is_sql_statement(user_input.command):
                                logger.debug("Executing SQL: {sql}", sql=user_input.command)
                                self._execute_sql(user_input.command)
                            else:
                                console.print(
                                    "[yellow]This doesn't appear to be a SQL statement. "
                                    "Please configure LLM with /setup to use natural language queries.[/yellow]"
                                )
                        else:
                            console.print("[red]No database connection. Use /connect to connect.[/red]")
                        continue

                    if not self.db_connected:
                        # DB not connected, route all input to LLM
                        await self._run_loop_command(user_input.content)
                        continue

                    # Both configured, check if SQL statement
                    if self._db_service.is_sql_statement(user_input.command):
                        logger.debug("Executing SQL: {sql}", sql=user_input.command)
                        self._execute_sql(user_input.command)
                        continue

                    # Not SQL, route to LLM
                    await self._run_loop_command(user_input.content)
        finally:
            # Clear current REPL instance on exit
            self._set_current(None)
            self._prompt_session = None

        return True

    def _on_thinking_toggle(self, enabled: bool) -> None:
        """Handle thinking mode toggle from prompt session."""
        if isinstance(self.loop, NeoLoop) and self.loop.runtime.llm:
            self.loop.runtime.llm.set_thinking_enabled(enabled)

    async def _explain_last_sql_result(self) -> None:
        """Explain the last SQL execution result using a dedicated agent."""
        # Check if LLM is configured
        if not self.llm_configured:
            console.print("[yellow]LLM not configured. Use /setup to configure a model.[/yellow]")
            return

        # Get last query context
        if not self._db_service:
            console.print("[yellow]No database service available.[/yellow]")
            return

        last_context = self._db_service.get_last_query_context()
        if not last_context:
            console.print("[yellow]No SQL result to explain.[/yellow]")
            return

        # Format query context
        from database.service import format_query_context_for_agent

        context_str = format_query_context_for_agent(last_context)

        # Load or get cached explain agent
        if self._explain_agent is None:
            try:
                explain_agent_file = Path(__file__).parent.parent / "prompts" / "explain_agent.yaml"
                explain_agent = await load_agent(explain_agent_file, self.loop.runtime)
                self._explain_agent = NeoLoop(explain_agent)
            except Exception as e:
                logger.exception("Failed to load explain agent")
                console.print(f"[red]Failed to load explain agent: {e}[/red]")
                return

        # Reset context for fresh conversation
        self._explain_agent.reset_context()

        # Build user message
        from database import QueryStatus

        if last_context.status == QueryStatus.ERROR:
            user_message = "Please explain the cause of this SQL error.\n\n" + context_str
        else:
            user_message = "Please explain the meaning of this SQL execution result.\n\n" + context_str

        # Run the explain agent
        try:
            cancel_event = asyncio.Event()
            await run_loop(
                self._explain_agent,
                user_message,
                lambda stream: visualize(
                    stream,
                    initial_status=self._explain_agent.status,
                    cancel_event=cancel_event,
                    agent_type="explain",
                ),
                cancel_event,
            )
        except Exception as e:
            logger.exception("Failed to explain SQL result")
            console.print(f"[red]Failed to explain result: {e}[/red]")

    async def _run_meta_command(self, command_str: str):
        from exception import Reload

        parts = command_str.split()
        command_name = parts[0]
        command_args = parts[1:]
        command = get_meta_command(command_name)
        if command is None:
            console.print(f"Meta command /{command_name} not found")
            return
        if command.loop_only and not isinstance(self.loop, NeoLoop):
            console.print(f"Meta command /{command_name} not supported")
            return
        logger.debug(
            "Running meta command: {command_name} with args: {command_args}",
            command_name=command_name,
            command_args=command_args,
        )
        try:
            ret = command.func(self, command_args)
            if isinstance(ret, Awaitable):
                await ret
        except LLMNotSet:
            logger.error("LLM not set")
            console.print("[red]LLM not set, send /setup to configure[/red]")
        except ChatProviderError as e:
            logger.exception("LLM provider error:")
            console.print(f"[red]LLM provider error: {e}[/red]")
        except asyncio.CancelledError:
            logger.info("Interrupted by user")
            console.print("[red]Interrupted by user[/red]")
        except Reload:
            # just propagate
            raise
        except Exception as e:
            logger.exception("Meta command error:")
            console.print(f"[red]Error: {e}[/red]")

    async def _run_loop_command(
        self,
        user_input: str | list[ContentPart],
    ) -> bool:
        """
        Run the loop and handle any known exceptions.

        Returns:
            bool: Whether the run is successful.
        """
        cancel_event = asyncio.Event()

        try:
            # Use lambda to pass cancel_event via closure
            await run_loop(
                self.loop,
                user_input,
                lambda stream: visualize(
                    stream,
                    initial_status=self.loop.status,
                    cancel_event=cancel_event,
                ),
                cancel_event,
            )
            return True
        except LLMNotSet:
            logger.error("LLM not set")
            console.print("[red]LLM not set, send /setup to configure[/red]")
        except LLMNotSupported as e:
            # actually unsupported input/mode should already be blocked by prompt session
            logger.error(
                "LLM model '{model_name}' does not support required capabilities: {capabilities}",
                model_name=e.llm.model_name,
                capabilities=", ".join(e.capabilities),
            )
            console.print(f"[red]{e}[/red]")
        except LLMInvocationError as e:
            logger.exception("LLM invocation error:")
            console.print(f"[red]Model error ({e.provider}/{e.model}): {e.original_error or e}[/red]")
        except ChatProviderError as e:
            logger.exception("LLM provider error:")
            if isinstance(e, APIStatusError) and e.status_code == 401:
                console.print("[red]Authorization failed, please check your API key[/red]")
            elif isinstance(e, APIStatusError) and e.status_code == 402:
                console.print("[red]Membership expired, please renew your plan[/red]")
            elif isinstance(e, APIStatusError) and e.status_code == 403:
                console.print("[red]Quota exceeded, please upgrade your plan or retry later[/red]")
            else:
                console.print(f"[red]LLM provider error: {e}[/red]")
        except MaxStepsReached as e:
            logger.warning("Max steps reached: {n_steps}", n_steps=e.n_steps)
            console.print(f"[yellow]Max steps reached: {e.n_steps}[/yellow]")
        except RunCancelled:
            logger.info("Cancelled by user")
            console.print("[red]Interrupted by user[/red]")
        except Exception as e:
            logger.exception("Agent error:")
            console.print(f"[red]Error: {e}[/red]")
        return False

    def _try_backslash_command(self, command: str) -> tuple[bool, bool]:
        """
        Try to execute input as a backslash command.

        Args:
            command: User input to check

        Returns:
            Tuple of (handled, should_exit):
            - handled: True if it was a backslash command
            - should_exit: True if the command requests exit (e.g., \\q)
        """
        handled, result = execute_backslash_command(command, self._db_service)

        if handled:
            logger.debug("Backslash command executed: {command}", command=command)
            # Check if command requests exit
            if result and not result.should_continue:
                return True, True

        return handled, False

    def _execute_sql(self, sql: str) -> None:
        """Execute SQL statement: execute + format + record history."""
        if not self._db_service or not self._db_service.is_connected():
            console.print("[red]No database connection. Use /connect to connect.[/red]")
            return

        from database import DatabaseError, QueryStatus
        from database.service import get_service
        from ui.formatters.database_formatter import format_and_display_result

        # Check if this is a transaction control statement
        is_tx_control, tx_type = self._db_service.is_transaction_control_statement(sql)
        if is_tx_control:
            self._handle_transaction_control(tx_type)
            return

        try:
            # Check if vertical format is requested
            use_vertical = self._db_service.has_vertical_format_directive(sql)

            # Execute query
            result = self._db_service.execute_query(sql)

            # Format and display result
            format_and_display_result(result, sql, use_vertical)

            # Save query result for agent context injection (success or error from result)
            db_svc = get_service()
            if db_svc:
                if result.success:
                    db_svc.set_last_query_context(
                        sql=sql,
                        status=QueryStatus.SUCCESS,
                        columns=result.columns,
                        rows=result.rows,
                        affected_rows=result.affected_rows,
                        execution_time=result.execution_time,
                    )
                else:
                    db_svc.set_last_query_context(
                        sql=sql,
                        status=QueryStatus.ERROR,
                        error_message=result.error,
                    )

            # Record execution in history
            if self._query_history:
                self._query_history.record_query(
                    sql=sql,
                    status="success" if result.success else "error",
                    execution_time=result.execution_time,
                    affected_rows=result.affected_rows,
                    error_message=result.error,
                )

        except DatabaseError as e:
            # Save failed query for agent context injection
            db_svc = get_service()
            if db_svc:
                db_svc.set_last_query_context(
                    sql=sql,
                    status=QueryStatus.ERROR,
                    error_message=str(e),
                )
            # Record failed execution and display error
            if self._query_history:
                self._query_history.record_query(sql, "error", error_message=str(e))
            from ui.formatters.database_formatter import display_database_error

            display_database_error(e)
        except Exception as e:
            # Save failed query for agent context injection
            db_svc = get_service()
            if db_svc:
                db_svc.set_last_query_context(
                    sql=sql,
                    status=QueryStatus.ERROR,
                    error_message=str(e),
                )
            # Handle unexpected errors
            if self._query_history:
                self._query_history.record_query(sql, "error", error_message=str(e))

    def _handle_transaction_control(self, tx_type: Any) -> None:
        """Handle transaction control statements (BEGIN/COMMIT/ROLLBACK)."""
        from database import QueryType, TransactionState

        if not self._db_service:
            return

        current_state = self._db_service.get_transaction_state()

        try:
            if tx_type == QueryType.BEGIN:
                if current_state == TransactionState.IN_TRANSACTION:
                    console.print("[yellow]Warning: Already in transaction[/yellow]")
                    return
                self._db_service.begin_transaction()
                console.print("[green]Transaction started[/green]")

            elif tx_type == QueryType.COMMIT:
                if current_state != TransactionState.IN_TRANSACTION:
                    console.print("[yellow]Warning: No transaction in progress[/yellow]")
                    return
                self._db_service.commit_transaction()
                console.print("[green]Transaction committed[/green]")

            elif tx_type == QueryType.ROLLBACK:
                if current_state not in (TransactionState.IN_TRANSACTION, TransactionState.TRANSACTION_ERROR):
                    console.print("[yellow]Warning: No transaction in progress[/yellow]")
                    return
                self._db_service.rollback_transaction()
                console.print("[green]Transaction rolled back[/green]")

        except Exception as e:
            console.print(f"[red]Transaction error: {e}[/red]")
            logger.exception("Transaction control failed")

    def _check_uncommitted_transaction(self) -> bool:
        """
        Check if there's an uncommitted transaction and prompt user.

        Returns:
            True if user chose not to exit (has uncommitted transaction and wants to stay),
            False if it's safe to exit (no transaction or user confirmed exit).
        """
        from database import TransactionState

        if not self._db_service or not self._db_service.is_connected():
            return False

        current_state = self._db_service.get_transaction_state()
        if current_state not in (TransactionState.IN_TRANSACTION, TransactionState.TRANSACTION_ERROR):
            return False

        # User already warned, allow exit this time
        if self._exit_warned:
            console.print("[yellow]Uncommitted transaction will be lost.[/yellow]")
            return False

        # There's an uncommitted transaction, warn user
        console.print("[yellow]Warning: You have an uncommitted transaction.[/yellow]")
        console.print(
            "[yellow]Use COMMIT to save changes, ROLLBACK to discard, or type 'exit' again to force quit.[/yellow]"
        )
        self._exit_warned = True
        return True


# Welcome screen components

_CLI_BLUE = "sky_blue2"
_LOGO = f"""\
[{_CLI_BLUE}]\
███████╗  ██████╗  ███████╗   █████╗   ██████╗
██   ██║  ██╔══██╗ ██╔════╝  ██╔══██╗  ╚═██╔═╝
███████║  ██║  ██║ ███████╗  ███████║    ██║
██║ ██╔╝  ██║  ██║ ╚════██║  ██╔══██║    ██║
██║  ██║  ██████╔╝ ███████║  ██╔══██║  ██████╗
╚═╝  ╚═╝  ╚═════╝  ╚══════╝  ╚═╝  ╚═╝  ╚═════╝
[{_CLI_BLUE}]\
"""


@dataclass(slots=True)
class WelcomeInfoItem:
    """A single item in the welcome information display."""

    class Level(Enum):
        INFO = "grey50"
        WARN = "yellow"
        ERROR = "red"

    name: str
    value: str
    level: Level = Level.INFO


def _print_welcome_info(name: str, info_items: list[WelcomeInfoItem]) -> None:
    """Print the welcome banner and information."""
    head = Text.from_markup(f"[bold]Welcome to {name}，Your Next-gen AI CLI![/bold]")
    help_text = Text.from_markup("[grey50]Send /help for help information.[/grey50]")

    # Use Table for precise width control
    logo = Text.from_markup(_LOGO)
    table = Table(show_header=False, show_edge=False, box=None, padding=(0, 1), expand=False)
    table.add_column(justify="left")
    table.add_column(justify="left")
    table.add_row(logo)
    table.add_row(Group(head, help_text))

    rows: list[RenderableType] = [table]

    rows.append(Text(""))  # Empty line
    for item in info_items:
        rows.append(Text(f"{item.name}: {item.value}", style=item.level.value))

    console.print(
        Panel(
            Group(*rows),
            border_style=_CLI_BLUE,
            expand=False,
            padding=(1, 2),
        )
    )
