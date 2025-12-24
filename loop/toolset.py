"""Tool system types and execution logic."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, Generic, override

from pydantic import BaseModel

from loop.types import T
from loop.types import ContentPart, ToolCall, FunctionBody


# --- Tool Results ---
class ToolError(BaseModel):
    """Tool execution error result."""

    message: str
    output: str | list[ContentPart] | ContentPart | None = None
    brief: str | None = None


class ToolRuntimeError(ToolError):
    """Runtime error during tool execution."""

    pass


class ToolOk(BaseModel):
    """Successful tool execution result."""

    message: str | None = None
    output: str | list[ContentPart] | ContentPart = ""
    brief: str | None = None


class ToolResult(BaseModel):
    """Result of a tool call execution."""

    tool_call_id: str
    name: str | None = None
    result: ToolOk | ToolError


# Type aliases
ToolReturnType = ToolOk | ToolError
HandleResult = ToolResult


# --- Tool Definitions ---
class BaseTool(Generic[T]):
    """Base class for all tools with typed parameters.

    Usage:
        class MyTool(BaseTool[MyParams]):
            name = "MyTool"
            params = MyParams
            ...

    For tools without strict type checking:
        class MyTool(BaseTool):  # Equivalent to BaseTool[Any]
            ...
    """

    name: str
    description: str
    params: type[T]

    def __init__(self, **kwargs):
        pass

    async def __call__(self, params: T) -> ToolReturnType:
        """Execute the tool with given parameters."""
        raise NotImplementedError

    @property
    def parameters(self) -> dict[str, Any]:
        """Get tool parameter schema."""
        if hasattr(self, "params") and issubclass(self.params, BaseModel):
            return self.params.model_json_schema()
        return {}

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, BaseTool):
            return False
        return self.name == other.name and self.description == other.description and self.parameters == other.parameters

    def __repr__(self) -> str:
        return f"BaseTool(name={self.name!r}, description={self.description!r}, parameters={self.parameters!r})"


# --- Toolsets ---
class Toolset:
    """Collection of tools."""

    tools: list[BaseTool]

    def __init__(self, tools=None):
        self.tools = tools or []

    def __add__(self, other):
        """Add tools to create new toolset."""
        new_tools = list(self.tools)
        if isinstance(other, Toolset):
            new_tools.extend(other.tools)
        elif isinstance(other, list):
            new_tools.extend(other)
        else:
            new_tools.append(other)
        return Toolset(new_tools)

    def __iadd__(self, other):
        """In-place addition to modify self.tools directly."""
        if isinstance(other, Toolset):
            self.tools.extend(other.tools)
        elif isinstance(other, list):
            self.tools.extend(other)
        else:
            self.tools.append(other)
        return self

    def __iter__(self):
        return iter(self.tools)


class SimpleToolset(Toolset):
    """Toolset with built-in tool execution handling."""

    async def handle(self, tool_call: ToolCall) -> HandleResult:
        """Execute a tool call and return the result."""
        fname = tool_call.function.name if isinstance(tool_call.function, FunctionBody) else tool_call.function["name"]
        fargs_str = (
            tool_call.function.arguments
            if isinstance(tool_call.function, FunctionBody)
            else tool_call.function["arguments"]
        )

        try:
            tool_args = json.loads(fargs_str)
        except (json.JSONDecodeError, TypeError):
            return ToolResult(
                tool_call_id=tool_call.id,
                name=fname,
                result=ToolRuntimeError(message=f"Invalid JSON arguments: {fargs_str}"),
            )

        tool_map = {t.name: t for t in self.tools}
        if fname in tool_map:
            tool = tool_map[fname]
            try:
                params_obj = tool.params(**tool_args)
                tool_ret = await tool(params_obj)
                return ToolResult(tool_call_id=tool_call.id, name=fname, result=tool_ret)
            except Exception as e:
                return ToolResult(tool_call_id=tool_call.id, name=fname, result=ToolRuntimeError(message=str(e)))
        else:
            return ToolResult(
                tool_call_id=tool_call.id, name=fname, result=ToolRuntimeError(message=f"Tool {fname} not found")
            )


current_tool_call = ContextVar[ToolCall | None]("current_tool_call", default=None)


def get_current_tool_call_or_none() -> ToolCall | None:
    """
    Get the current tool call or None.
    Expect to be not None when called from a `__call__` method of a tool.
    """
    return current_tool_call.get()


class CustomToolset(SimpleToolset):
    @override
    def handle(self, tool_call: ToolCall) -> HandleResult:
        token = current_tool_call.set(tool_call)
        try:
            return super().handle(tool_call)
        finally:
            current_tool_call.reset(token)


class DynamicToolset(CustomToolset):
    """Toolset that supports dynamic tool management at runtime.

    This class provides explicit methods for adding and removing tools,
    with version tracking for change detection.

    Usage:
        toolset = DynamicToolset()
        toolset.add_tool(my_tool)
        toolset.remove_tools_by(lambda t: t.name.startswith("mcp_"))
    """

    def __init__(self, tools: list[BaseTool] | None = None):
        super().__init__(tools)
        self._version = 0

    @property
    def version(self) -> int:
        """Get the current version number. Increments on each modification."""
        return self._version

    @property
    def tool_names(self) -> list[str]:
        """Get list of all tool names."""
        return [t.name for t in self.tools]

    def has_tool(self, name: str) -> bool:
        """Check if a tool with the given name exists."""
        return any(t.name == name for t in self.tools)

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name, or None if not found."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def add_tool(self, tool: BaseTool) -> bool:
        """Add a single tool.

        Args:
            tool: The tool to add.

        Returns:
            True if added, False if a tool with the same name already exists.
        """
        if self.has_tool(tool.name):
            return False
        self.tools.append(tool)
        self._version += 1
        return True

    def add_tools(self, tools: list[BaseTool]) -> int:
        """Add multiple tools.

        Args:
            tools: List of tools to add.

        Returns:
            Number of tools actually added (excluding duplicates).
        """
        added = 0
        for tool in tools:
            if self.add_tool(tool):
                added += 1
        return added

    def remove_tool(self, name: str) -> bool:
        """Remove a tool by name.

        Args:
            name: Name of the tool to remove.

        Returns:
            True if removed, False if not found.
        """
        for i, tool in enumerate(self.tools):
            if tool.name == name:
                self.tools.pop(i)
                self._version += 1
                return True
        return False

    def remove_tools_by(self, predicate: Callable[[BaseTool], bool]) -> int:
        """Remove tools matching a predicate.

        Args:
            predicate: A function that returns True for tools to remove.

        Returns:
            Number of tools removed.
        """
        original_count = len(self.tools)
        self.tools = [t for t in self.tools if not predicate(t)]
        removed = original_count - len(self.tools)
        if removed > 0:
            self._version += 1
        return removed

    def clear(self) -> int:
        """Remove all tools.

        Returns:
            Number of tools removed.
        """
        count = len(self.tools)
        if count > 0:
            self.tools.clear()
            self._version += 1
        return count
