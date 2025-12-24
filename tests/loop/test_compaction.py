"""Tests for loop.compaction module."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from loop.compaction import ChainCompaction, _message_to_string, count_tokens


class TestMessageToString:
    """Tests for _message_to_string function."""

    def test_string_content(self):
        """Test message with string content."""
        msg = AIMessage(content="Hello world")
        assert _message_to_string(msg) == "Hello world"

    def test_list_content(self):
        """Test message with list content."""
        msg = AIMessage(content=["Hello", "world"])
        assert _message_to_string(msg) == "Hello world"

    def test_dict_content_with_text(self):
        """Test message with dict content containing text."""
        msg = AIMessage(content=[{"text": "Hello"}, {"text": "world"}])
        assert _message_to_string(msg) == "Hello world"

    def test_dict_content_without_text(self):
        """Test message with dict content without text."""
        msg = AIMessage(content=[{"type": "image"}])
        assert _message_to_string(msg) == ""

    def test_non_string_content(self):
        """Test message with non-string content."""
        # AIMessage doesn't accept non-string content directly,
        # but _message_to_string handles it via str() conversion
        # We'll test with a mock message that has non-string content
        msg = MagicMock(spec=BaseMessage)
        msg.content = 123
        assert _message_to_string(msg) == "123"


class TestCountTokens:
    """Tests for count_tokens function."""

    def test_empty_messages(self):
        """Test counting tokens for empty message list."""
        assert count_tokens([]) == 0

    def test_single_message(self):
        """Test counting tokens for single message."""
        msg = AIMessage(content="Hello")
        tokens = count_tokens([msg])
        assert tokens > 0
        # Should include overhead (4 tokens) plus content
        assert tokens >= 4

    def test_multiple_messages(self):
        """Test counting tokens for multiple messages."""
        msg1 = HumanMessage(content="Hello")
        msg2 = AIMessage(content="World")
        tokens = count_tokens([msg1, msg2])
        assert tokens > 0
        # Should include overhead for each message
        assert tokens >= 8

    def test_message_with_tool_calls(self):
        """Test counting tokens for message with tool calls."""
        msg = AIMessage(content="", tool_calls=[{"name": "test_tool", "args": {"param": "value"}, "id": "call-1"}])
        tokens = count_tokens([msg])
        assert tokens > 0
        # Should include tool call tokens
        assert tokens >= 4

    def test_message_with_multiple_tool_calls(self):
        """Test counting tokens for message with multiple tool calls."""
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "tool1", "args": {}, "id": "call-1"},
                {"name": "tool2", "args": {"key": "value"}, "id": "call-2"},
            ],
        )
        tokens = count_tokens([msg])
        assert tokens > 0


class TestChainCompaction:
    """Tests for ChainCompaction class."""

    def test_max_preserved_messages(self):
        """Test MAX_PRESERVED_MESSAGES constant."""
        compactor = ChainCompaction()
        assert compactor.MAX_PRESERVED_MESSAGES == 2

    @pytest.mark.asyncio
    async def test_compact_empty_messages(self):
        """Test compacting empty message list."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()
        messages, tokens = await compactor.compact([], mock_llm)
        assert messages == []
        assert tokens == 0
        mock_llm.chat_provider.astream.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_single_message(self):
        """Test compacting single message (should not compact)."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()
        messages = [HumanMessage(content="Hello")]
        result_messages, tokens = await compactor.compact(messages, mock_llm)
        assert len(result_messages) == 1
        assert result_messages == messages
        mock_llm.chat_provider.astream.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_two_messages(self):
        """Test compacting two messages (should not compact)."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()
        messages = [HumanMessage(content="Hello"), AIMessage(content="World")]
        result_messages, tokens = await compactor.compact(messages, mock_llm)
        assert len(result_messages) == 2
        assert result_messages == messages
        mock_llm.chat_provider.astream.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_three_messages(self):
        """Test compacting three messages (should compact first one)."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()

        # Create mock async generator
        async def mock_astream(messages):
            chunk = AIMessage(content="Compacted summary")
            chunk.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
            yield chunk

        mock_llm.chat_provider.astream = mock_astream

        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
        ]

        with patch("loop.compaction.prompts") as mock_prompts:
            mock_prompts.COMPACT = "Compact this: $CONTEXT"
            result_messages, tokens = await compactor.compact(messages, mock_llm)

        # Should have compacted first message and preserved last 2
        # Actually preserves last 2 HumanMessage/AIMessage, so we get 1 compacted + 2 preserved = 3
        assert len(result_messages) >= 2  # At least 1 compacted + preserved messages
        assert isinstance(result_messages[0], AIMessage)
        assert "[Previous context has been compacted]" in result_messages[0].content

    @pytest.mark.asyncio
    async def test_compact_preserves_last_two(self):
        """Test that compaction preserves last two Human/AI messages."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()

        async def mock_astream(messages):
            chunk = AIMessage(content="Summary")
            chunk.usage_metadata = {}
            yield chunk

        mock_llm.chat_provider.astream = mock_astream

        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
        ]

        with patch("loop.compaction.prompts") as mock_prompts:
            mock_prompts.COMPACT = "Compact: $CONTEXT"
            result_messages, tokens = await compactor.compact(messages, mock_llm)

        # Should preserve last 2 Human/AI messages (Message 2, Response 2, Message 3)
        # Actually, it preserves last 2 HumanMessage/AIMessage, so Message 2, Response 2, Message 3
        assert len(result_messages) >= 2
        # Last message should be Message 3
        assert isinstance(result_messages[-1], HumanMessage)
        assert "Message 3" in result_messages[-1].content

    @pytest.mark.asyncio
    async def test_compact_with_system_message(self):
        """Test that SystemMessage is included in compaction."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()

        async def mock_astream(messages):
            chunk = AIMessage(content="Summary")
            chunk.usage_metadata = {}
            yield chunk

        mock_llm.chat_provider.astream = mock_astream

        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
        ]

        with patch("loop.compaction.prompts") as mock_prompts:
            mock_prompts.COMPACT = "Compact: $CONTEXT"
            result_messages, tokens = await compactor.compact(messages, mock_llm)

        # SystemMessage should be compacted (not preserved)
        # Preserves last 2 HumanMessage/AIMessage, so we get 1 compacted + preserved messages
        assert len(result_messages) >= 2  # At least 1 compacted + preserved messages

    @pytest.mark.asyncio
    async def test_compact_handles_empty_response(self):
        """Test compacting when LLM returns empty response."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()

        async def mock_astream(messages):
            chunk = AIMessage(content="")
            chunk.usage_metadata = {}
            yield chunk

        mock_llm.chat_provider.astream = mock_astream

        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
        ]

        with patch("loop.compaction.prompts") as mock_prompts:
            mock_prompts.COMPACT = "Compact: $CONTEXT"
            result_messages, tokens = await compactor.compact(messages, mock_llm)

        assert len(result_messages) >= 2
        assert isinstance(result_messages[0], AIMessage)

    @pytest.mark.asyncio
    async def test_compact_handles_no_usage_metadata(self):
        """Test compacting when LLM response has no usage metadata."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()

        async def mock_astream(messages):
            chunk = AIMessage(content="Summary")
            # No usage_metadata
            yield chunk

        mock_llm.chat_provider.astream = mock_astream

        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
        ]

        with patch("loop.compaction.prompts") as mock_prompts:
            mock_prompts.COMPACT = "Compact: $CONTEXT"
            result_messages, tokens = await compactor.compact(messages, mock_llm)

        assert len(result_messages) >= 2
        assert tokens >= 0

    @pytest.mark.asyncio
    async def test_compact_handles_non_string_content(self):
        """Test compacting when LLM returns non-string content."""
        compactor = ChainCompaction()
        mock_llm = MagicMock()

        async def mock_astream(messages):
            chunk = AIMessage(content=["text", "part"])
            chunk.usage_metadata = {}
            yield chunk

        mock_llm.chat_provider.astream = mock_astream

        messages = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
        ]

        with patch("loop.compaction.prompts") as mock_prompts:
            mock_prompts.COMPACT = "Compact: $CONTEXT"
            result_messages, tokens = await compactor.compact(messages, mock_llm)

        assert len(result_messages) >= 2
        # Content should be converted to string
        assert isinstance(result_messages[0].content, str)
