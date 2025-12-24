"""Tests for loop.nodes module."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from loop.nodes import (
    get_tool_description,
    needs_approval,
    should_continue,
)
from loop.state import AgentState


class TestNeedsApproval:
    """Tests for needs_approval function."""

    def test_ddl_executor_requires_approval(self):
        """Test that DDLExecutor requires approval."""
        assert needs_approval("DDLExecutor", {}) is True

    def test_sysbench_prepare_requires_approval(self):
        """Test that SysbenchPrepare requires approval."""
        assert needs_approval("SysbenchPrepare", {}) is True

    def test_sysbench_run_requires_approval(self):
        """Test that SysbenchRun requires approval."""
        assert needs_approval("SysbenchRun", {}) is True

    def test_sysbench_cleanup_requires_approval(self):
        """Test that SysbenchCleanup requires approval."""
        assert needs_approval("SysbenchCleanup", {}) is True

    def test_other_tool_no_approval(self):
        """Test that other tools don't require approval."""
        assert needs_approval("SomeOtherTool", {}) is False
        assert needs_approval("QueryTool", {}) is False

    def test_case_sensitive(self):
        """Test that tool name matching is case sensitive."""
        assert needs_approval("ddlexecutor", {}) is False
        assert needs_approval("DDLEXECUTOR", {}) is False
        assert needs_approval("DDLExecutor", {}) is True


class TestGetToolDescription:
    """Tests for get_tool_description function."""

    def test_description_key(self):
        """Test description from 'description' key."""
        args = {"description": "Test description"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: Test description"

    def test_query_key(self):
        """Test description from 'query' key."""
        args = {"query": "SELECT * FROM users"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: SELECT * FROM users"

    def test_sql_key(self):
        """Test description from 'sql' key."""
        args = {"sql": "SELECT 1"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: SELECT 1"

    def test_sql_statement_key(self):
        """Test description from 'sql_statement' key."""
        args = {"sql_statement": "INSERT INTO table VALUES (1)"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: INSERT INTO table VALUES (1)"

    def test_command_key(self):
        """Test description from 'command' key."""
        args = {"command": "ls -la"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: ls -la"

    def test_path_key(self):
        """Test description from 'path' key."""
        args = {"path": "/path/to/file"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: /path/to/file"

    def test_content_key(self):
        """Test description from 'content' key."""
        args = {"content": "Some content"}
        desc = get_tool_description("TestTool", args)
        assert desc == "TestTool: Some content"

    def test_long_description_truncated(self):
        """Test that long descriptions are truncated."""
        long_desc = "a" * 150
        args = {"description": long_desc}
        desc = get_tool_description("TestTool", args)
        assert len(desc) < len(long_desc) + len("TestTool: ")
        assert desc.endswith("...")

    def test_fallback_to_first_key(self):
        """Test fallback to first argument key."""
        args = {"param1": "value1", "param2": "value2"}
        desc = get_tool_description("TestTool", args)
        assert "param1" in desc
        assert "value1" in desc or "..." in desc

    def test_empty_args(self):
        """Test description with empty args."""
        desc = get_tool_description("TestTool", {})
        assert desc == "TestTool"

    def test_none_args(self):
        """Test description with None args."""
        desc = get_tool_description("TestTool", None)
        assert desc == "TestTool"


class TestShouldContinue:
    """Tests for should_continue function."""

    def test_should_continue_with_tool_calls(self):
        """Test should_continue returns 'tools' when AI message has tool calls."""
        state: AgentState = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="I'll help you", tool_calls=[{"name": "test_tool", "args": {}, "id": "call-1"}]),
            ],
            "token_count": 0,
            "step_number": 1,
            "yolo": False,
        }
        result = should_continue(state)
        assert result == "tools"

    def test_should_continue_without_tool_calls(self):
        """Test should_continue returns 'end' when no tool calls."""
        state: AgentState = {
            "messages": [HumanMessage(content="Hello"), AIMessage(content="Hello! How can I help?")],
            "token_count": 0,
            "step_number": 1,
            "yolo": False,
        }
        result = should_continue(state)
        assert result == "end"

    def test_should_continue_with_empty_tool_calls(self):
        """Test should_continue returns 'end' when tool_calls is empty."""
        state: AgentState = {
            "messages": [HumanMessage(content="Hello"), AIMessage(content="Response", tool_calls=[])],
            "token_count": 0,
            "step_number": 1,
            "yolo": False,
        }
        result = should_continue(state)
        assert result == "end"

    def test_should_continue_with_human_message_last(self):
        """Test should_continue returns 'end' when last message is HumanMessage."""
        state: AgentState = {
            "messages": [AIMessage(content="Response"), HumanMessage(content="Follow up")],
            "token_count": 0,
            "step_number": 1,
            "yolo": False,
        }
        result = should_continue(state)
        assert result == "end"

    def test_should_continue_with_tool_message_last(self):
        """Test should_continue returns 'end' when last message is ToolMessage."""
        state: AgentState = {
            "messages": [
                AIMessage(content="Response", tool_calls=[{"name": "tool", "args": {}, "id": "1"}]),
                ToolMessage(content="Result", tool_call_id="1", name="tool"),
            ],
            "token_count": 0,
            "step_number": 1,
            "yolo": False,
        }
        result = should_continue(state)
        assert result == "end"

    def test_should_continue_multiple_tool_calls(self):
        """Test should_continue with multiple tool calls."""
        state: AgentState = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(
                    content="I'll use multiple tools",
                    tool_calls=[
                        {"name": "tool1", "args": {}, "id": "call-1"},
                        {"name": "tool2", "args": {}, "id": "call-2"},
                    ],
                ),
            ],
            "token_count": 0,
            "step_number": 1,
            "yolo": False,
        }
        result = should_continue(state)
        assert result == "tools"
