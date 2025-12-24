"""MCP Toolset - loads and manages tools from MCP servers with persistent connections."""

from __future__ import annotations

from typing import Any

from mcp.types import Tool as MCPToolSchema, ToolAnnotations
from pydantic import BaseModel, Field, create_model

from loop.toolset import BaseTool, ToolError, ToolOk, ToolReturnType
from tools.mcp.client import (
    MCPConnectionPool,
    get_connection_pool,
)
from tools.mcp.config import MCPServerConfig
from utils.logging import logger

# --- Helper functions for schema conversion ---


def _json_type_to_python(json_type: str | list[str] | None, json_schema: dict[str, Any]) -> Any:
    """Convert JSON Schema type to Python type annotation."""
    if json_type is None:
        return Any

    # Handle union types (e.g., ["string", "null"])
    if isinstance(json_type, list):
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            return _json_type_to_python(non_null_types[0], json_schema)
        return Any

    type_mapping: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "null": type(None),
    }

    if json_type in type_mapping:
        return type_mapping[json_type]

    if json_type == "array":
        items = json_schema.get("items", {})
        item_type = items.get("type", "string") if items else "string"
        inner_type = _json_type_to_python(item_type, items)
        return list[inner_type]  # type: ignore[valid-type]

    if json_type == "object":
        return dict[str, Any]

    return Any


def _create_params_model(tool_name: str, tool_schema: MCPToolSchema) -> type[BaseModel]:
    """Dynamically create a Pydantic model from MCP tool schema."""
    input_schema = tool_schema.inputSchema
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    field_definitions: dict[str, Any] = {}

    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type")
        python_type = _json_type_to_python(prop_type, prop_schema)
        description = prop_schema.get("description", "")

        if prop_name in required:
            field_definitions[prop_name] = (
                python_type,
                Field(..., description=description),
            )
        else:
            field_definitions[prop_name] = (
                python_type | None,
                Field(default=None, description=description),
            )

    model_name = f"MCP{tool_name.replace('-', '_').replace('.', '_')}Params"
    return create_model(model_name, **field_definitions)  # type: ignore[call-overload]


# --- MCP Tool ---


class MCPTool(BaseTool[BaseModel]):
    """Wrapper that adapts an MCP tool to the BaseTool interface."""

    name: str
    description: str
    params: type[BaseModel]

    def __init__(
        self,
        tool_schema: MCPToolSchema,
        server_name: str,
        connection_pool: MCPConnectionPool,
        *,
        name_prefix: str | None = None,
    ) -> None:
        super().__init__()

        original_name = tool_schema.name
        if name_prefix:
            self.name = f"{name_prefix}_{original_name}"
        else:
            self.name = original_name

        self.description = tool_schema.description or f"MCP tool: {original_name}"
        self.params = _create_params_model(original_name, tool_schema)

        self._original_name = original_name
        self._server_name = server_name
        self._connection_pool = connection_pool
        self._annotations: ToolAnnotations | None = tool_schema.annotations

    @property
    def annotations(self) -> ToolAnnotations | None:
        """Get tool annotations (readOnly, destructive, etc.)."""
        return self._annotations

    def get_annotations_display(self) -> str:
        """Get a compact display string for annotations."""
        if not self._annotations:
            return ""

        parts: list[str] = []
        if self._annotations.readOnlyHint:
            parts.append("readOnly")
        if self._annotations.destructiveHint:
            parts.append("destructive")
        if self._annotations.idempotentHint:
            parts.append("idempotent")

        return ", ".join(parts) if parts else ""

    async def __call__(self, params: BaseModel) -> ToolReturnType:
        """Execute the MCP tool using the persistent connection."""
        try:
            result = await self._connection_pool.call_tool(
                self._server_name,
                self._original_name,
                params.model_dump(exclude_none=True),
            )
            return ToolOk(
                output=result,
                message=f"MCP tool '{self.name}' executed successfully",
            )

        except KeyError as e:
            logger.error(
                "MCP server '{server}' not connected for tool '{name}'",
                server=self._server_name,
                name=self.name,
            )
            return ToolError(
                message=f"MCP server not connected: {e}",
                brief=f"MCP:{self._server_name} disconnected",
            )

        except Exception as e:
            logger.error(
                "MCP tool '{name}' failed: {error}",
                name=self.name,
                error=str(e),
            )
            return ToolError(
                message=f"MCP tool error: {e}",
                brief=f"MCP:{self._server_name} error",
            )

    def __repr__(self) -> str:
        return f"MCPTool(name={self.name!r}, server={self._server_name!r}, original={self._original_name!r})"


async def connect_and_load_tools(server: MCPServerConfig) -> list[MCPTool]:
    """Connect to an MCP server and load its tools.

    Args:
        server: The server configuration.

    Returns:
        List of MCPTool instances loaded from the server.

    Raises:
        Exception: If connection fails.
    """
    pool = get_connection_pool()

    # Connect to server
    await pool.connect(server)

    # Load tools from this server
    tool_schemas = await pool.list_tools(server.name)
    tools: list[MCPTool] = []

    for schema in tool_schemas:
        # Apply filters
        if server.include_tools and schema.name not in server.include_tools:
            continue
        if server.exclude_tools and schema.name in server.exclude_tools:
            continue

        mcp_tool = MCPTool(
            tool_schema=schema,
            server_name=server.name,
            connection_pool=pool,
        )
        tools.append(mcp_tool)

    logger.info(
        "Connected to MCP server '{name}', loaded {count} tools",
        name=server.name,
        count=len(tools),
    )

    return tools
