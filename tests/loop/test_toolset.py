"""Tests for loop.toolset module."""

import pytest
from pydantic import BaseModel

from loop.toolset import (
    BaseTool,
    DynamicToolset,
    SimpleToolset,
    ToolError,
    ToolOk,
    ToolResult,
    ToolRuntimeError,
    Toolset,
    get_current_tool_call_or_none,
)
from loop.types import FunctionBody, ToolCall


class MockParams(BaseModel):
    """Test parameters model."""

    name: str
    value: int


class MockTool(BaseTool[MockParams]):
    """Test tool implementation."""

    name = "MockTool"
    description = "A test tool"
    params = MockParams

    async def __call__(self, params: MockParams) -> ToolOk | ToolError:
        return ToolOk(output=f"Result: {params.name}={params.value}")


class ErrorTool(BaseTool[MockParams]):
    """Tool that raises an error."""

    name = "ErrorTool"
    description = "A tool that errors"
    params = MockParams

    async def __call__(self, params: MockParams) -> ToolOk | ToolError:
        return ToolRuntimeError(message="Test error")


class ExceptionTool(BaseTool[MockParams]):
    """Tool that raises an exception."""

    name = "ExceptionTool"
    description = "A tool that raises exception"
    params = MockParams

    async def __call__(self, params: MockParams) -> ToolOk | ToolError:
        raise ValueError("Exception occurred")


class TestBaseTool:
    """Tests for BaseTool class."""

    def test_parameters_property(self):
        """Test parameters property returns schema."""
        tool = MockTool()
        params = tool.parameters
        assert "properties" in params
        assert "name" in params["properties"]
        assert "value" in params["properties"]

    def test_parameters_property_no_params(self):
        """Test parameters property when no params defined."""

        class NoParamsTool(BaseTool):
            name = "NoParams"
            description = "No params"
            params = type(None)  # Use type(None) instead of None

            async def __call__(self, params):
                return ToolOk(output="")

        tool = NoParamsTool()
        # When params is not a BaseModel subclass, should return empty dict
        assert tool.parameters == {}

    def test_eq(self):
        """Test equality comparison."""
        tool1 = MockTool()
        tool2 = MockTool()
        assert tool1 == tool2

        class DifferentTool(BaseTool[MockParams]):
            name = "Different"
            description = "Different"
            params = MockParams

            async def __call__(self, params: MockParams):
                return ToolOk(output="")

        tool3 = DifferentTool()
        assert tool1 != tool3
        assert tool1 != "not a tool"

    def test_repr(self):
        """Test string representation."""
        tool = MockTool()
        repr_str = repr(tool)
        assert "MockTool" in repr_str
        assert "description" in repr_str


class TestToolset:
    """Tests for Toolset class."""

    def test_init_empty(self):
        """Test Toolset initialization with no tools."""
        toolset = Toolset()
        assert len(toolset.tools) == 0

    def test_init_with_tools(self):
        """Test Toolset initialization with tools."""
        tool1 = MockTool()
        tool2 = ErrorTool()
        toolset = Toolset([tool1, tool2])
        assert len(toolset.tools) == 2

    def test_add_toolset(self):
        """Test adding another toolset."""
        toolset1 = Toolset([MockTool()])
        toolset2 = Toolset([ErrorTool()])
        result = toolset1 + toolset2
        assert len(result.tools) == 2
        assert len(toolset1.tools) == 1  # Original unchanged

    def test_iadd_toolset(self):
        """Test in-place addition of toolset."""
        toolset = Toolset([MockTool()])
        toolset += Toolset([ErrorTool()])
        assert len(toolset.tools) == 2

    def test_add_tool(self):
        """Test adding a single tool."""
        toolset = Toolset()
        toolset += MockTool()
        assert len(toolset.tools) == 1

    def test_add_list(self):
        """Test adding a list of tools."""
        toolset = Toolset()
        toolset += [MockTool(), ErrorTool()]
        assert len(toolset.tools) == 2

    def test_iter(self):
        """Test iteration over tools."""
        toolset = Toolset([MockTool(), ErrorTool()])
        tools = list(toolset)
        assert len(tools) == 2


class TestSimpleToolset:
    """Tests for SimpleToolset class."""

    @pytest.mark.asyncio
    async def test_handle_success(self):
        """Test handling successful tool call."""
        toolset = SimpleToolset([MockTool()])
        tool_call = ToolCall(
            id="test-id", function=FunctionBody(name="MockTool", arguments='{"name": "test", "value": 42}')
        )
        result = await toolset.handle(tool_call)
        assert isinstance(result, ToolResult)
        assert result.tool_call_id == "test-id"
        assert result.name == "MockTool"
        assert isinstance(result.result, ToolOk)
        assert "test=42" in result.result.output

    @pytest.mark.asyncio
    async def test_handle_tool_error(self):
        """Test handling tool that returns error."""
        toolset = SimpleToolset([ErrorTool()])
        tool_call = ToolCall(
            id="test-id", function=FunctionBody(name="ErrorTool", arguments='{"name": "test", "value": 42}')
        )
        result = await toolset.handle(tool_call)
        assert isinstance(result.result, ToolRuntimeError)
        assert "Test error" in result.result.message

    @pytest.mark.asyncio
    async def test_handle_exception(self):
        """Test handling tool that raises exception."""
        toolset = SimpleToolset([ExceptionTool()])
        tool_call = ToolCall(
            id="test-id", function=FunctionBody(name="ExceptionTool", arguments='{"name": "test", "value": 42}')
        )
        result = await toolset.handle(tool_call)
        assert isinstance(result.result, ToolRuntimeError)
        assert "Exception occurred" in result.result.message

    @pytest.mark.asyncio
    async def test_handle_tool_not_found(self):
        """Test handling tool not found."""
        toolset = SimpleToolset([MockTool()])
        tool_call = ToolCall(id="test-id", function=FunctionBody(name="NonExistentTool", arguments="{}"))
        result = await toolset.handle(tool_call)
        assert isinstance(result.result, ToolRuntimeError)
        assert "not found" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self):
        """Test handling invalid JSON arguments."""
        toolset = SimpleToolset([MockTool()])
        tool_call = ToolCall(id="test-id", function=FunctionBody(name="MockTool", arguments="invalid json"))
        result = await toolset.handle(tool_call)
        assert isinstance(result.result, ToolRuntimeError)
        assert "Invalid JSON" in result.result.message

    @pytest.mark.asyncio
    async def test_handle_dict_function(self):
        """Test handling tool call with dict function."""
        toolset = SimpleToolset([MockTool()])
        tool_call = ToolCall(id="test-id", function={"name": "MockTool", "arguments": '{"name": "test", "value": 42}'})
        result = await toolset.handle(tool_call)
        assert isinstance(result.result, ToolOk)


class TestDynamicToolset:
    """Tests for DynamicToolset class."""

    def test_init(self):
        """Test DynamicToolset initialization."""
        toolset = DynamicToolset()
        assert toolset.version == 0
        assert len(toolset.tools) == 0

    def test_version_increments_on_add(self):
        """Test version increments when adding tool."""
        toolset = DynamicToolset()
        initial_version = toolset.version
        toolset.add_tool(MockTool())
        assert toolset.version == initial_version + 1

    def test_tool_names(self):
        """Test tool_names property."""
        toolset = DynamicToolset([MockTool(), ErrorTool()])
        names = toolset.tool_names
        assert "MockTool" in names
        assert "ErrorTool" in names
        assert len(names) == 2

    def test_has_tool(self):
        """Test has_tool method."""
        toolset = DynamicToolset([MockTool()])
        assert toolset.has_tool("MockTool") is True
        assert toolset.has_tool("NonExistent") is False

    def test_get_tool(self):
        """Test get_tool method."""
        tool = MockTool()
        toolset = DynamicToolset([tool])
        assert toolset.get_tool("MockTool") == tool
        assert toolset.get_tool("NonExistent") is None

    def test_add_tool_success(self):
        """Test adding tool successfully."""
        toolset = DynamicToolset()
        result = toolset.add_tool(MockTool())
        assert result is True
        assert toolset.has_tool("MockTool")
        assert toolset.version == 1

    def test_add_tool_duplicate(self):
        """Test adding duplicate tool."""
        toolset = DynamicToolset([MockTool()])
        result = toolset.add_tool(MockTool())
        assert result is False
        assert len(toolset.tools) == 1

    def test_add_tools(self):
        """Test adding multiple tools."""
        toolset = DynamicToolset()
        added = toolset.add_tools([MockTool(), ErrorTool()])
        assert added == 2
        assert len(toolset.tools) == 2

    def test_add_tools_with_duplicates(self):
        """Test adding tools with duplicates."""
        toolset = DynamicToolset([MockTool()])
        added = toolset.add_tools([MockTool(), ErrorTool()])
        assert added == 1  # Only ErrorTool added
        assert len(toolset.tools) == 2

    def test_remove_tool_success(self):
        """Test removing tool successfully."""
        toolset = DynamicToolset([MockTool()])
        result = toolset.remove_tool("MockTool")
        assert result is True
        assert not toolset.has_tool("MockTool")
        assert toolset.version == 1

    def test_remove_tool_not_found(self):
        """Test removing non-existent tool."""
        toolset = DynamicToolset()
        result = toolset.remove_tool("NonExistent")
        assert result is False
        assert toolset.version == 0

    def test_remove_tools_by(self):
        """Test removing tools by predicate."""
        toolset = DynamicToolset([MockTool(), ErrorTool()])
        removed = toolset.remove_tools_by(lambda t: t.name.startswith("Mock"))
        assert removed == 1
        assert not toolset.has_tool("MockTool")
        assert toolset.has_tool("ErrorTool")
        assert toolset.version == 1

    def test_remove_tools_by_no_match(self):
        """Test removing tools by predicate with no matches."""
        toolset = DynamicToolset([MockTool()])
        removed = toolset.remove_tools_by(lambda t: t.name.startswith("Non"))
        assert removed == 0
        assert toolset.version == 0

    def test_clear(self):
        """Test clearing all tools."""
        toolset = DynamicToolset([MockTool(), ErrorTool()])
        removed = toolset.clear()
        assert removed == 2
        assert len(toolset.tools) == 0
        assert toolset.version == 1

    def test_clear_empty(self):
        """Test clearing empty toolset."""
        toolset = DynamicToolset()
        removed = toolset.clear()
        assert removed == 0
        assert toolset.version == 0

    @pytest.mark.asyncio
    async def test_handle_preserves_context(self):
        """Test that handle preserves tool call context."""
        toolset = DynamicToolset([MockTool()])
        tool_call = ToolCall(
            id="test-id", function=FunctionBody(name="MockTool", arguments='{"name": "test", "value": 42}')
        )
        # Context should be set during handle
        result = await toolset.handle(tool_call)
        assert isinstance(result.result, ToolOk)
        # Context should be cleared after handle
        assert get_current_tool_call_or_none() is None
