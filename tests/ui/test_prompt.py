"""Tests for ui.prompt module - prompt session functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest

from loop import StatusSnapshot
from ui.prompt import (
    CustomPromptSession,
    PromptMode,
    UserInput,
    _HistoryEntry,
    _load_history_entries,
    toast,
)


class TestPromptMode:
    """Tests for PromptMode enum."""

    def test_toggle_agent_to_shell(self):
        """Test toggling from AGENT to SHELL mode."""
        mode = PromptMode.AGENT
        assert mode.toggle() == PromptMode.SHELL

    def test_toggle_shell_to_agent(self):
        """Test toggling from SHELL to AGENT mode."""
        mode = PromptMode.SHELL
        assert mode.toggle() == PromptMode.AGENT

    def test_str_representation(self):
        """Test string representation of PromptMode."""
        assert str(PromptMode.AGENT) == "agent"
        assert str(PromptMode.SHELL) == "shell"


class TestUserInput:
    """Tests for UserInput model."""

    def test_user_input_init(self):
        """Test UserInput initialization."""
        content = []
        user_input = UserInput(mode=PromptMode.AGENT, command="test", content=content)
        assert user_input.mode == PromptMode.AGENT
        assert user_input.command == "test"
        assert user_input.content == content

    def test_user_input_str(self):
        """Test UserInput string representation."""
        user_input = UserInput(mode=PromptMode.AGENT, command="test", content=[])
        assert str(user_input) == "test"

    def test_user_input_bool_true(self):
        """Test UserInput boolean conversion with non-empty command."""
        user_input = UserInput(mode=PromptMode.AGENT, command="test", content=[])
        assert bool(user_input) is True

    def test_user_input_bool_false(self):
        """Test UserInput boolean conversion with empty command."""
        user_input = UserInput(mode=PromptMode.AGENT, command="", content=[])
        assert bool(user_input) is False


class TestHistoryEntry:
    """Tests for _HistoryEntry model."""

    def test_history_entry_init(self):
        """Test _HistoryEntry initialization."""
        entry = _HistoryEntry(content="test command")
        assert entry.content == "test command"

    def test_history_entry_model_dump(self):
        """Test _HistoryEntry model dump."""
        entry = _HistoryEntry(content="test command")
        dumped = entry.model_dump()
        assert dumped == {"content": "test command"}


class TestLoadHistoryEntries:
    """Tests for _load_history_entries function."""

    def test_load_history_entries_file_not_exists(self, tmp_path):
        """Test loading history from non-existent file."""
        history_file = tmp_path / "history.jsonl"
        entries = _load_history_entries(history_file)
        assert entries == []

    def test_load_history_entries_valid_file(self, tmp_path):
        """Test loading history from valid file."""
        history_file = tmp_path / "history.jsonl"
        entries_data = [
            {"content": "SELECT * FROM users"},
            {"content": "SELECT * FROM orders"},
        ]
        with history_file.open("w", encoding="utf-8") as f:
            for entry in entries_data:
                f.write(json.dumps(entry) + "\n")

        entries = _load_history_entries(history_file)
        assert len(entries) == 2
        assert entries[0].content == "SELECT * FROM users"
        assert entries[1].content == "SELECT * FROM orders"

    def test_load_history_entries_invalid_json(self, tmp_path):
        """Test loading history with invalid JSON."""
        history_file = tmp_path / "history.jsonl"
        with history_file.open("w", encoding="utf-8") as f:
            f.write("invalid json\n")
            f.write('{"content": "valid"}\n')

        entries = _load_history_entries(history_file)
        assert len(entries) == 1
        assert entries[0].content == "valid"

    def test_load_history_entries_empty_lines(self, tmp_path):
        """Test loading history with empty lines."""
        history_file = tmp_path / "history.jsonl"
        with history_file.open("w", encoding="utf-8") as f:
            f.write("\n")
            f.write('{"content": "test"}\n')
            f.write("\n")

        entries = _load_history_entries(history_file)
        assert len(entries) == 1
        assert entries[0].content == "test"


class TestCustomPromptSession:
    """Tests for CustomPromptSession core methods."""

    @pytest.fixture
    def mock_status_provider(self):
        """Create a mock status provider."""

        def provider():
            return StatusSnapshot(context_usage=0.5, yolo=False)

        return provider

    @pytest.fixture
    def mock_db_service(self):
        """Create a mock DatabaseService."""
        service = MagicMock()
        service.is_connected.return_value = True
        service.get_connection_info.return_value = {
            "database": "test_db",
            "user": "test_user",
            "transaction_state": "NOT_IN_TRANSACTION",
        }
        return service

    @pytest.fixture
    def prompt_session(self, mock_status_provider, tmp_path):
        """Create a CustomPromptSession instance."""
        with patch("ui.prompt.get_share_dir", return_value=tmp_path):
            session = CustomPromptSession(status_provider=mock_status_provider)
            return session

    def test_format_status_with_yolo(self):
        """Test _format_status with YOLO mode."""
        status = StatusSnapshot(context_usage=0.5, yolo=True)
        result = CustomPromptSession._format_status(status)
        assert "[YOLO]" in result
        assert "context:" in result

    def test_format_status_without_yolo(self):
        """Test _format_status without YOLO mode."""
        status = StatusSnapshot(context_usage=0.3, yolo=False)
        result = CustomPromptSession._format_status(status)
        assert "[YOLO]" not in result
        assert "context: 30.0%" in result

    def test_format_status_context_usage_bounded(self):
        """Test _format_status with context usage bounded."""
        status = StatusSnapshot(context_usage=1.5, yolo=False)  # > 1.0
        result = CustomPromptSession._format_status(status)
        assert "context: 100.0%" in result

        status = StatusSnapshot(context_usage=-0.5, yolo=False)  # < 0.0
        result = CustomPromptSession._format_status(status)
        # When context_usage < 0, the condition `if status.context_usage >= 0` fails
        # so no context part is added, resulting in empty string
        assert result == ""

    def test_append_history_entry_new_entry(self, prompt_session, tmp_path):
        """Test _append_history_entry with new entry."""
        prompt_session._append_history_entry("SELECT * FROM users")
        assert prompt_session._last_history_content == "SELECT * FROM users"

        # Verify file was written
        history_file = prompt_session._history_file
        assert history_file.exists()
        entries = _load_history_entries(history_file)
        assert len(entries) == 1
        assert entries[0].content == "SELECT * FROM users"

    def test_append_history_entry_duplicate(self, prompt_session):
        """Test _append_history_entry with duplicate entry."""
        prompt_session._last_history_content = "SELECT * FROM users"
        prompt_session._append_history_entry("SELECT * FROM users")
        # Should not append duplicate
        assert prompt_session._last_history_content == "SELECT * FROM users"

    def test_append_history_entry_empty(self, prompt_session):
        """Test _append_history_entry with empty entry."""
        prompt_session._append_history_entry("")
        assert prompt_session._last_history_content is None

    def test_append_history_entry_whitespace(self, prompt_session):
        """Test _append_history_entry with whitespace-only entry."""
        prompt_session._append_history_entry("   ")
        assert prompt_session._last_history_content is None

    def test_render_message_with_db(self, prompt_session, mock_db_service):
        """Test _render_message with database connection."""
        prompt_session._db_service = mock_db_service
        result = prompt_session._render_message()
        assert len(result) > 0
        # Check that database indicator is included
        text = "".join([part[1] for part in result])
        assert "test_db" in text or "@test_db" in text

    def test_render_message_without_db(self, prompt_session):
        """Test _render_message without database connection."""
        prompt_session._db_service = None
        result = prompt_session._render_message()
        assert len(result) > 0

    def test_render_message_with_transaction(self, prompt_session, mock_db_service):
        """Test _render_message with active transaction."""
        mock_db_service.get_connection_info.return_value = {
            "database": "test_db",
            "user": "test_user",
            "transaction_state": "IN_TRANSACTION",
        }
        prompt_session._db_service = mock_db_service
        result = prompt_session._render_message()
        text = "".join([part[1] for part in result])
        assert "[TX]" in text

    def test_refresh_db_service(self, prompt_session, mock_db_service):
        """Test refresh_db_service."""
        prompt_session.refresh_db_service(mock_db_service)
        assert prompt_session._db_service == mock_db_service
        assert prompt_session._sql_completer is not None

    def test_refresh_db_service_none(self, prompt_session):
        """Test refresh_db_service with None."""
        prompt_session.refresh_db_service(None)
        assert prompt_session._db_service is None
        assert prompt_session._sql_completer is None

    def test_thinking_enabled_property(self, prompt_session):
        """Test thinking_enabled property."""
        prompt_session._thinking_enabled = True
        assert prompt_session.thinking_enabled is True

        prompt_session._thinking_enabled = False
        assert prompt_session.thinking_enabled is False


class TestToast:
    """Tests for toast notification system."""

    def test_toast_basic(self):
        """Test basic toast notification."""
        from ui.prompt import _toast_queue

        _toast_queue.clear()
        toast("Test message")
        assert len(_toast_queue) == 1
        assert _toast_queue[0].message == "Test message"

    def test_toast_with_topic(self):
        """Test toast with topic (should replace existing)."""
        from ui.prompt import _toast_queue

        _toast_queue.clear()
        toast("First message", topic="test")
        toast("Second message", topic="test")
        assert len(_toast_queue) == 1
        assert _toast_queue[0].message == "Second message"

    def test_toast_immediate(self):
        """Test immediate toast (should be prepended)."""
        from ui.prompt import _toast_queue

        _toast_queue.clear()
        toast("First message")
        toast("Immediate message", immediate=True)
        assert len(_toast_queue) == 2
        assert _toast_queue[0].message == "Immediate message"

    def test_toast_duration_minimum(self):
        """Test toast duration minimum."""
        from ui.prompt import _toast_queue, _REFRESH_INTERVAL

        _toast_queue.clear()
        toast("Test", duration=1.0)  # Less than _REFRESH_INTERVAL
        assert _toast_queue[0].duration >= _REFRESH_INTERVAL
