"""MCP (Model Context Protocol) integration module.

This module provides integration with MCP servers, allowing the agent
to use tools from external MCP servers alongside local tools.

Features:
- Persistent connection pool for efficient tool execution
- Automatic tool discovery from MCP servers
- Seamless integration with the agent's toolset
"""

from tools.mcp.config import MCPConfig, MCPServerConfig, load_mcp_config

__all__ = [
    "MCPConfig",
    "MCPServerConfig",
    "load_mcp_config",
]
