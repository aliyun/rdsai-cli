# MCP (Model Context Protocol) Integration

[English](mcp.md) | [中文](mcp_zh.md)

RDSAI CLI supports connecting to external MCP servers to extend its capabilities. This enables cloud RDS management, API integrations, and more.

## Quick Start

1. **Create MCP configuration file** at `~/.rdsai-cli/mcp.yaml`:

> 💡 **Tip**: You can use `mcp.example.yaml` in the project root as a template. Copy it to `~/.rdsai-cli/mcp.yaml` and customize it according to your needs.

```yaml
mcp:
  enabled: true
  servers:
    # Alibaba Cloud RDS OpenAPI MCP Server
    - name: rds
      transport: stdio
      command: uvx
      args:
        - "alibabacloud-rds-openapi-mcp-server@latest"
      env:
        ALIBABA_CLOUD_ACCESS_KEY_ID: "${ACCESS_ID}"
        ALIBABA_CLOUD_ACCESS_KEY_SECRET: "${ACCESS_KEY}"
      include_tools:
        - describe_db_instances
        - describe_db_instance_performance
        - modify_security_ips
        # ... add more tools as needed
```

2. **List configured MCP servers**:

```text
mysql> /mcp list

# Name  Transport  Enabled  Status            Tools
─────────────────────────────────────────────────────────
1 rds   stdio      ✓       ● Connected       25
```

3. **Connect to an MCP server** (if not auto-connected):

```text
mysql> /mcp connect rds
✓ Connected to rds. Loaded 25 tools.
```

4. **Use MCP tools via natural language**:

```text
mysql> list all my RDS instances
mysql> check performance metrics for mysql-prod-01
mysql> show me slow queries for mysql-prod-01
mysql> modify security IP whitelist to allow 192.168.1.0/24
```

## MCP Management Commands

```text
# List all configured MCP servers and their status
mysql> /mcp list
mysql> /mcp ls

# View detailed information about a server
mysql> /mcp view rds
mysql> /mcp info rds

# Connect to an MCP server
mysql> /mcp connect rds

# Disconnect from an MCP server
mysql> /mcp disconnect rds

# Enable/disable a server (updates config file)
mysql> /mcp enable rds
mysql> /mcp disable rds

# Reload MCP configuration from file
mysql> /mcp reload
```

## Example: Alibaba Cloud RDS OpenAPI MCP

The [Alibaba Cloud RDS OpenAPI MCP Server](https://github.com/aliyun/alibabacloud-rds-openapi-mcp-server) provides tools for managing cloud RDS instances:

**Available Tools:**

- **Instance Management**: `create_db_instance`, `describe_db_instances`, `describe_db_instance_attribute`, `modify_db_instance_spec`, etc.
- **Monitoring & Logs**: `describe_db_instance_performance`, `describe_monitor_metrics`, `describe_error_logs`, etc.
- **Configuration**: `modify_parameter`, `describe_db_instance_parameters`, `modify_security_ips`, etc.
- **Network & Connection**: `describe_db_instance_net_info`, `allocate_instance_public_connection`, etc.
- **Resources & Planning**: `describe_available_zones`, `describe_available_classes`, `describe_vpcs`, `describe_vswitches`, etc.

## Configuration Options

**Transport Types:**
- `stdio` — For local command-based servers (e.g., `uvx`, `npx`)
- `sse` — Server-Sent Events for HTTP-based servers
- `streamable_http` — HTTP streaming (recommended for HTTP servers)

**Tool Filtering:**
- `include_tools` — Whitelist specific tools to load
- `exclude_tools` — Blacklist tools to exclude

**Example with tool filtering:**

```yaml
- name: rds
  transport: stdio
  command: uvx
  args:
    - "alibabacloud-rds-openapi-mcp-server@latest"
  env:
    ALIBABA_CLOUD_ACCESS_KEY_ID: "${ACCESS_ID}"
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: "${ACCESS_KEY}"
  # Only load read-only tools
  include_tools:
    - describe_db_instances
    - describe_db_instance_attribute
    - describe_slow_log_records
```

## Requirements

- MCP server must be installed and accessible
- For Alibaba Cloud RDS: Valid AccessKey ID and Secret
- Configuration file: `~/.rdsai-cli/mcp.yaml`
- Enabled servers are automatically connected on startup

