"""Tests for loop.runtime module."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from config import Config, Session
from llm.llm import LLM
from loop.runtime import BuiltinSystemPromptArgs, Runtime


class TestBuiltinSystemPromptArgs:
    """Tests for BuiltinSystemPromptArgs dataclass."""

    def test_init(self):
        """Test BuiltinSystemPromptArgs initialization."""
        args = BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en")
        assert args.CLI_NOW == "2024-01-01T00:00:00"
        assert args.CLI_LANGUAGE == "en"


class TestRuntime:
    """Tests for Runtime class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock Config."""
        config = MagicMock(spec=Config)
        config.language = "en"
        return config

    @pytest.fixture
    def mock_session(self):
        """Create a mock Session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        return MagicMock(spec=LLM)

    def test_init(self, mock_config, mock_session):
        """Test Runtime initialization."""
        runtime = Runtime(
            config=mock_config,
            llm=None,
            session=mock_session,
            builtin_args=BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en"),
        )
        assert runtime.config == mock_config
        assert runtime.llm is None
        assert runtime.session == mock_session
        assert runtime.yolo is False
        assert runtime.mcp_config is None

    def test_init_with_llm(self, mock_config, mock_session, mock_llm):
        """Test Runtime initialization with LLM."""
        runtime = Runtime(
            config=mock_config,
            llm=mock_llm,
            session=mock_session,
            builtin_args=BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en"),
        )
        assert runtime.llm == mock_llm

    def test_init_with_yolo(self, mock_config, mock_session):
        """Test Runtime initialization with yolo mode."""
        runtime = Runtime(
            config=mock_config,
            llm=None,
            session=mock_session,
            builtin_args=BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en"),
            yolo=True,
        )
        assert runtime.yolo is True

    def test_set_llm(self, mock_config, mock_session, mock_llm):
        """Test set_llm method."""
        runtime = Runtime(
            config=mock_config,
            llm=None,
            session=mock_session,
            builtin_args=BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en"),
        )
        runtime.set_llm(mock_llm)
        assert runtime.llm == mock_llm

    def test_set_llm_none(self, mock_config, mock_session, mock_llm):
        """Test set_llm with None."""
        runtime = Runtime(
            config=mock_config,
            llm=mock_llm,
            session=mock_session,
            builtin_args=BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en"),
        )
        runtime.set_llm(None)
        assert runtime.llm is None

    def test_set_yolo(self, mock_config, mock_session):
        """Test set_yolo method."""
        runtime = Runtime(
            config=mock_config,
            llm=None,
            session=mock_session,
            builtin_args=BuiltinSystemPromptArgs(CLI_NOW="2024-01-01T00:00:00", CLI_LANGUAGE="en"),
            yolo=False,
        )
        runtime.set_yolo(True)
        assert runtime.yolo is True
        runtime.set_yolo(False)
        assert runtime.yolo is False

    @pytest.mark.asyncio
    async def test_create(self, mock_config, mock_session):
        """Test Runtime.create static method."""
        runtime = await Runtime.create(config=mock_config, llm=None, session=mock_session)
        assert isinstance(runtime, Runtime)
        assert runtime.config == mock_config
        assert runtime.llm is None
        assert runtime.session == mock_session
        assert runtime.yolo is False
        assert isinstance(runtime.builtin_args, BuiltinSystemPromptArgs)
        assert runtime.builtin_args.CLI_LANGUAGE == "en"

    @pytest.mark.asyncio
    async def test_create_with_llm(self, mock_config, mock_session, mock_llm):
        """Test Runtime.create with LLM."""
        runtime = await Runtime.create(config=mock_config, llm=mock_llm, session=mock_session)
        assert runtime.llm == mock_llm

    @pytest.mark.asyncio
    async def test_create_with_yolo(self, mock_config, mock_session):
        """Test Runtime.create with yolo mode."""
        runtime = await Runtime.create(config=mock_config, llm=None, session=mock_session, yolo=True)
        assert runtime.yolo is True

    @pytest.mark.asyncio
    async def test_create_builtin_args_format(self, mock_config, mock_session):
        """Test that Runtime.create formats CLI_NOW correctly."""
        runtime = await Runtime.create(config=mock_config, llm=None, session=mock_session)
        # CLI_NOW should be ISO format datetime string
        assert isinstance(runtime.builtin_args.CLI_NOW, str)
        # Should be parseable as ISO format
        datetime.fromisoformat(runtime.builtin_args.CLI_NOW)

    @pytest.mark.asyncio
    async def test_create_with_mcp_config(self, mock_config, mock_session):
        """Test Runtime.create with MCP config."""
        mock_mcp_config = MagicMock()
        runtime = await Runtime.create(config=mock_config, llm=None, session=mock_session, mcp_config=mock_mcp_config)
        assert runtime.mcp_config == mock_mcp_config
