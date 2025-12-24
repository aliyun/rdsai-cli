"""MCP configuration models and loading."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from config.base import get_share_dir
from pydantic import BaseModel, Field, model_validator

from utils.logging import logger


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    name: str = Field(..., description="Unique identifier for this server")
    enabled: bool = Field(default=False, description="Whether this server is enabled")
    transport: Literal["stdio", "sse", "streamable_http"] = Field(
        ..., description="Transport type: stdio, sse, or streamable_http"
    )

    # For stdio transport
    command: str | None = Field(default=None, description="Command to run the MCP server")
    args: list[str] = Field(default_factory=list, description="Arguments for the command")
    env: dict[str, str] | None = Field(default=None, description="Environment variables")

    # For SSE / streamable_http transport
    url: str | None = Field(default=None, description="HTTP endpoint URL")

    # For streamable_http transport - optional headers
    headers: dict[str, str] | None = Field(default=None, description="HTTP headers for streamable_http transport")

    # Tool filtering
    include_tools: list[str] | None = Field(default=None, description="Only include these tools (whitelist)")
    exclude_tools: list[str] | None = Field(default=None, description="Exclude these tools (blacklist)")

    # Optional: tool name prefix to avoid conflicts
    tool_prefix: str | None = Field(
        default=None,
        description="Prefix to add to tool names (default: use server name)",
    )

    @model_validator(mode="after")
    def validate_transport_config(self) -> MCPServerConfig:
        """Validate that required fields are set for the transport type."""
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("'command' is required for stdio transport")
        elif self.transport in ("sse", "streamable_http"):
            if not self.url:
                raise ValueError(f"'url' is required for {self.transport} transport")
        return self


class MCPConfig(BaseModel):
    """Global MCP configuration."""

    enabled: bool = Field(default=True, description="Whether MCP integration is enabled")
    servers: list[MCPServerConfig] = Field(default_factory=list, description="List of MCP servers to connect to")

    # Internal: path to the config file (not serialized)
    _config_file: Path | None = None

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_unique_names(self) -> MCPConfig:
        """Ensure all server names are unique."""
        names = [s.name for s in self.servers]
        if len(names) != len(set(names)):
            raise ValueError("MCP server names must be unique")
        return self

    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get a server config by name."""
        for server in self.servers:
            if server.name == name:
                return server
        return None

    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Get all enabled server configs."""
        return [s for s in self.servers if s.enabled]

    def save(self, config_file: Path | None = None) -> None:
        """Save configuration to YAML file.

        Args:
            config_file: Path to save to. Uses original path if not specified.
        """
        target = config_file or self._config_file
        if target is None:
            target = DEFAULT_MCP_CONFIG_PATH

        # Ensure directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Serialize without internal fields
        data = self.model_dump(exclude={"_config_file"})

        with open(target, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

        logger.info("Saved MCP config to: {file}", file=target)


DEFAULT_MCP_CONFIG_PATH = get_share_dir() / "mcp.yaml"


def load_mcp_config(config_file: Path | None = None) -> MCPConfig | None:
    """Load MCP configuration from a YAML file.

    Args:
        config_file: Path to the MCP configuration file.
                    If None, uses default path ~/.rdsai-cli/mcp.yaml.

    Returns:
        Parsed MCPConfig object, or None if no config file exists.

    Raises:
        ValueError: If the config file is invalid.
    """
    # Use default path if not specified
    if config_file is None:
        config_file = DEFAULT_MCP_CONFIG_PATH

    if not config_file.exists():
        logger.debug("MCP config file not found: {file}", file=config_file)
        return None

    logger.info("Loading MCP config from: {file}", file=config_file)

    try:
        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in MCP config file: {e}") from e

    if not data:
        logger.warning("MCP config file is empty, using defaults")
        return MCPConfig()

    # Support both root-level and nested 'mcp' key
    if "mcp" in data:
        data = data["mcp"]

    config = MCPConfig(**data)
    config._config_file = config_file  # Store the source file path
    return config
