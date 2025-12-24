"""Prompt session - user input handling and completion."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import md5
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app_or_none
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.completion import merge_completers
from prompt_toolkit.filters import Condition, has_completions
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.patch_stdout import patch_stdout
from pydantic import BaseModel, ValidationError

from config import get_share_dir
from loop import StatusSnapshot
from loop.types import ContentPart, TextPart
from ui.completers import MetaCommandCompleter, SQLCompleter
from utils.clipboard import is_clipboard_available
from utils.logging import logger


if TYPE_CHECKING:
    from database import DatabaseService

PROMPT_SYMBOL = "🐬"


# Prompt mode and user input types


class PromptMode(Enum):
    """Input mode for the prompt."""

    AGENT = "agent"
    SHELL = "shell"

    def toggle(self) -> PromptMode:
        return PromptMode.SHELL if self == PromptMode.AGENT else PromptMode.AGENT

    def __str__(self) -> str:
        return self.value


class UserInput(BaseModel):
    """Represents user input from the prompt."""

    mode: PromptMode
    command: str
    """The plain text representation of the user input."""
    content: list[ContentPart]
    """The rich content parts."""

    def __str__(self) -> str:
        return self.command

    def __bool__(self) -> bool:
        return bool(self.command)


# History management


class _HistoryEntry(BaseModel):
    content: str


def _load_history_entries(history_file: Path) -> list[_HistoryEntry]:
    """Load history entries from file."""
    entries: list[_HistoryEntry] = []
    if not history_file.exists():
        return entries

    try:
        with history_file.open(encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse user history line; skipping: {line}",
                        line=line,
                    )
                    continue
                try:
                    entry = _HistoryEntry.model_validate(record)
                    entries.append(entry)
                except ValidationError:
                    logger.warning(
                        "Failed to validate user history entry; skipping: {line}",
                        line=line,
                    )
                    continue
    except OSError as exc:
        logger.warning(
            "Failed to load user history file: {file} ({error})",
            file=history_file,
            error=exc,
        )

    return entries


# Toast notification system

_REFRESH_INTERVAL = 1.0


@dataclass(slots=True)
class _ToastEntry:
    """A toast notification entry."""

    topic: str | None
    """There can be only one toast of each non-None topic in the queue."""
    message: str
    duration: float


_toast_queue = deque[_ToastEntry]()
"""The queue of toasts to show, including the one currently being shown (the first one)."""


def toast(
    message: str,
    duration: float = 5.0,
    topic: str | None = None,
    immediate: bool = False,
) -> None:
    """Show a toast notification in the prompt toolbar."""
    duration = max(duration, _REFRESH_INTERVAL)
    entry = _ToastEntry(topic=topic, message=message, duration=duration)
    if topic is not None:
        # Remove existing toasts with the same topic
        for existing in list(_toast_queue):
            if existing.topic == topic:
                _toast_queue.remove(existing)
    if immediate:
        _toast_queue.appendleft(entry)
    else:
        _toast_queue.append(entry)


def _current_toast() -> _ToastEntry | None:
    if not _toast_queue:
        return None
    return _toast_queue[0]


class CustomPromptSession:
    """Custom prompt session with completion, history."""

    def __init__(
        self,
        *,
        status_provider: Callable[[], StatusSnapshot],
        db_service: DatabaseService | None = None,
        on_thinking_toggle: Callable[[bool], None] | None = None,
        on_explain_result: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        history_dir = get_share_dir() / "user-history"
        history_dir.mkdir(parents=True, exist_ok=True)
        work_dir_id = md5(str(Path.cwd()).encode(encoding="utf-8")).hexdigest()
        self._history_file = (history_dir / work_dir_id).with_suffix(".jsonl")
        self._status_provider = status_provider
        self._db_service = db_service
        self._last_history_content: str | None = None
        self._mode: PromptMode = PromptMode.AGENT
        self._attachment_parts: dict[str, ContentPart] = {}
        self._should_exit = False
        self._thinking_enabled = False
        self._on_thinking_toggle = on_thinking_toggle
        self._on_explain_result = on_explain_result
        self._explain_result_requested = False

        history_entries = _load_history_entries(self._history_file)
        history = InMemoryHistory()
        for entry in history_entries:
            history.append_string(entry.content)

        if history_entries:
            # for consecutive deduplication
            self._last_history_content = history_entries[-1].content

        # Build completers
        completers = [
            MetaCommandCompleter(),
        ]

        # Add SQL completer if database service is available
        self._sql_completer: SQLCompleter | None = None
        if self._db_service:
            self._sql_completer = SQLCompleter(self._db_service)
            completers.append(self._sql_completer)
            # Register callback to invalidate cache on schema changes
            self._db_service.register_schema_change_callback(self._on_schema_change)

        self._agent_mode_completer = merge_completers(
            completers,
            deduplicate=True,
        )

        # Build key bindings
        _kb = KeyBindings()
        shortcut_hints: list[str] = []

        @_kb.add("enter", filter=has_completions)
        def _accept_completion(event: KeyPressEvent) -> None:
            """Accept the first completion when Enter is pressed and completions are shown."""
            buff = event.current_buffer
            if buff.complete_state and buff.complete_state.completions:
                # Get the current completion, or use the first one if none is selected
                completion = buff.complete_state.current_completion
                if not completion:
                    completion = buff.complete_state.completions[0]
                buff.apply_completion(completion)

        @_kb.add("c-j", eager=True)
        def _insert_newline(event: KeyPressEvent) -> None:
            """Insert a newline when Ctrl-J is pressed."""
            event.current_buffer.insert_text("\n")

        shortcut_hints.append("ctrl-j: newline")

        # Custom key bindings: Ctrl-C for exit or interrupt
        @_kb.add("c-c", eager=True)
        def _exit_application(event: KeyPressEvent) -> None:
            """Exit application when Ctrl-C is pressed."""
            self._should_exit = True
            event.app.exit()

        # Disable default Ctrl-D behavior
        @_kb.add("c-d", eager=True)
        def _disable_ctrl_d(event: KeyPressEvent) -> None:
            """Disable default Ctrl-D EOF behavior."""
            pass  # Do nothing

        shortcut_hints.append("ctrl-c: exit/interrupt")

        # Ctrl-E to explain last SQL result
        @_kb.add("c-e", eager=True)
        def _explain_result(event: KeyPressEvent) -> None:
            """Explain last SQL result when Ctrl-E is pressed."""
            self._explain_result_requested = True
            # Exit the prompt to return control to the event loop
            event.app.exit()

        # Tab key to toggle thinking mode when buffer is empty
        def _is_buffer_empty_no_completions() -> bool:
            """Check if buffer is empty and no completions are shown."""
            app = get_app_or_none()
            if app is None:
                return False
            buffer = app.current_buffer
            return not buffer.text.strip() and not has_completions()

        @_kb.add("tab", filter=Condition(_is_buffer_empty_no_completions))
        def _toggle_thinking(event: KeyPressEvent) -> None:
            """Toggle thinking mode when Tab is pressed on empty input."""
            self._thinking_enabled = not self._thinking_enabled
            if self._on_thinking_toggle:
                self._on_thinking_toggle(self._thinking_enabled)
            mode_text = "enabled" if self._thinking_enabled else "disabled"
            toast(f" Thinking mode {mode_text}", duration=3.0, topic="thinking", immediate=True)

        if is_clipboard_available():

            @_kb.add("c-v", eager=True)
            def _paste(event: KeyPressEvent) -> None:
                clipboard_data = event.app.clipboard.get_data()
                event.current_buffer.paste_clipboard_data(clipboard_data)

            shortcut_hints.append("ctrl-v: paste")
            clipboard = PyperclipClipboard()
        else:
            clipboard = None

        self._shortcut_hints = shortcut_hints
        self._session = PromptSession(
            message=self._render_message,
            completer=self._agent_mode_completer,
            complete_while_typing=Condition(lambda: self._mode == PromptMode.AGENT),
            key_bindings=_kb,
            clipboard=clipboard,
            history=history,
            reserve_space_for_menu=4,
            bottom_toolbar=self._render_bottom_toolbar,
        )

        @self._session.default_buffer.on_text_changed.add_handler
        def trigger_complete(buffer: Buffer) -> None:
            if buffer.complete_while_typing():
                buffer.start_completion()

        self._status_refresh_task: asyncio.Task | None = None

    @property
    def thinking_enabled(self) -> bool:
        """Whether thinking mode is enabled."""
        return self._thinking_enabled

    def refresh_db_service(self, db_service: DatabaseService | None) -> None:
        """Refresh the database service reference and completers."""
        # Unregister old callback if exists
        if self._db_service and self._sql_completer:
            self._db_service.unregister_schema_change_callback(self._on_schema_change)

        # Update db_service
        self._db_service = db_service

        # Rebuild completers
        completers = [
            MetaCommandCompleter(),
        ]

        # Add SQL completer if database service is available
        self._sql_completer = None
        if self._db_service:
            self._sql_completer = SQLCompleter(self._db_service)
            completers.append(self._sql_completer)
            # Register callback to invalidate cache on schema changes
            self._db_service.register_schema_change_callback(self._on_schema_change)

        self._agent_mode_completer = merge_completers(
            completers,
            deduplicate=True,
        )

        # Update session completer
        self._session.completer = self._agent_mode_completer

        # Trigger immediate refresh of the prompt display
        app = get_app_or_none()
        if app is not None:
            app.invalidate()

    def _render_message(self) -> FormattedText:
        symbol = PROMPT_SYMBOL
        # Add database indicator
        db_indicator = ""
        prefix = "rdsai"
        if self._db_service and self._db_service.is_connected():
            db_info = self._db_service.get_connection_info()
            db_name = db_info.get("database", "db")
            if db_name:
                db_indicator = f"@{db_name}"

                # Add transaction indicator
                tx_state = db_info.get("transaction_state", "NOT_IN_TRANSACTION")
                if tx_state != "NOT_IN_TRANSACTION":
                    db_indicator += "[TX]"
            prefix = db_info.get("user") or prefix

        return FormattedText([("bold", f"{prefix}{db_indicator}{symbol} ")])

    def __enter__(self) -> CustomPromptSession:
        if self._status_refresh_task is not None and not self._status_refresh_task.done():
            return self

        async def _refresh(interval: float) -> None:
            try:
                while True:
                    app = get_app_or_none()
                    if app is not None:
                        app.invalidate()

                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        logger.warning("No running loop found, exiting status refresh task")
                        self._status_refresh_task = None
                        break

                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                # graceful exit
                pass

        self._status_refresh_task = asyncio.create_task(_refresh(_REFRESH_INTERVAL))
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._status_refresh_task is not None and not self._status_refresh_task.done():
            self._status_refresh_task.cancel()
        self._status_refresh_task = None
        self._attachment_parts.clear()

        # Unregister schema change callback
        if self._db_service and self._sql_completer:
            self._db_service.unregister_schema_change_callback(self._on_schema_change)

    def _on_schema_change(self) -> None:
        """Handle schema change events by invalidating SQL completer cache."""
        if self._sql_completer:
            self._sql_completer.invalidate_cache()

    async def prompt(self) -> UserInput:
        """Get user input from the prompt."""
        # Check if we should exit (from Ctrl-C)
        if self._should_exit:
            raise EOFError()

        self._explain_result_requested = False
        with patch_stdout(raw=True):
            command = str(await self._session.prompt_async()).strip()
            command = command.replace("\x00", "")  # just in case null bytes are somehow inserted

        # Check if Ctrl-E was pressed to explain result
        if self._explain_result_requested and self._on_explain_result:
            await self._on_explain_result()
            # Return empty input to continue the loop
            return UserInput(
                mode=self._mode,
                content=[],
                command="",
            )

        # Check again after prompt returns (in case Ctrl-C was pressed during prompt)
        if self._should_exit:
            raise EOFError()

        self._append_history_entry(command)

        # Parse rich content parts
        content: list[ContentPart] = []
        remaining_command = command

        if remaining_command.strip():
            content.append(TextPart(text=remaining_command.strip()))

        return UserInput(
            mode=self._mode,
            content=content,
            command=command,
        )

    def _append_history_entry(self, text: str) -> None:
        """Append an entry to the history file."""
        entry = _HistoryEntry(content=text.strip())
        if not entry.content:
            return

        # skip if same as last entry
        if entry.content == self._last_history_content:
            return

        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            with self._history_file.open("a", encoding="utf-8") as f:
                f.write(entry.model_dump_json(ensure_ascii=False) + "\n")
            self._last_history_content = entry.content
        except OSError as exc:
            logger.warning(
                "Failed to append user history entry: {file} ({error})",
                file=self._history_file,
                error=exc,
            )

    def _render_bottom_toolbar(self) -> FormattedText:
        """Render the bottom toolbar with status information.

        This method must never raise exceptions, as it would cause prompt_toolkit
        to enter an infinite "Press ENTER to continue..." loop.
        """
        try:
            app = get_app_or_none()
            if app is None:
                return FormattedText([])
            columns = app.output.get_size().columns

            fragments: list[tuple[str, str]] = []

            now_text = datetime.now().strftime("%H:%M")
            fragments.extend([("", now_text), ("", " " * 2)])
            columns -= len(now_text) + 2

            status = self._status_provider()
            status_text = self._format_status(status)

            # Add database status
            db_status = ""
            if self._db_service and self._db_service.is_connected():
                db_info = self._db_service.get_connection_info()
                db_name = db_info.get("database", "")
                if db_name:
                    db_status = f" | {db_name}"
                    tx_state = db_info.get("transaction_state", "NOT_IN_TRANSACTION")
                    if tx_state != "NOT_IN_TRANSACTION":
                        db_status += "[TX]"

            current_toast = _current_toast()
            if current_toast is not None:
                fragments.extend([("", current_toast.message), ("", " " * 2)])
                columns -= len(current_toast.message) + 2
                current_toast.duration -= _REFRESH_INTERVAL
                if current_toast.duration <= 0.0:
                    _toast_queue.popleft()
            else:
                shortcuts = [
                    *self._shortcut_hints,
                ]
                for shortcut in shortcuts:
                    full_status_len = len(status_text) + len(db_status)
                    if columns - full_status_len > len(shortcut) + 2:
                        fragments.extend([("", shortcut), ("", " " * 2)])
                        columns -= len(shortcut) + 2
                    else:
                        break

            # Add thinking mode status
            thinking_status = "on" if self._thinking_enabled else "off"
            thinking_text = f"Thinking {thinking_status} (tab)"

            full_status_text = status_text + db_status
            if full_status_text:
                full_status_text += " | "
            full_status_text += thinking_text

            padding = max(1, columns - len(full_status_text))
            fragments.append(("", " " * padding))
            fragments.append(("", full_status_text))

            return FormattedText(fragments)
        except Exception as exc:
            # Fallback to minimal toolbar on any error to prevent infinite loop
            logger.warning(
                "Failed to render bottom toolbar: {error}",
                error=exc,
            )
            return FormattedText([("", "⚠ toolbar error")])

    @staticmethod
    def _format_status(status: StatusSnapshot) -> str:
        """Format the status snapshot for display."""
        parts: list[str] = []

        # Show YOLO mode indicator
        if status.yolo:
            parts.append("[YOLO]")

        # Show context usage
        if status.context_usage >= 0:
            bounded = max(0.0, min(status.context_usage, 1.0))
            parts.append(f"context: {bounded:.1%}")

        return " ".join(parts)
