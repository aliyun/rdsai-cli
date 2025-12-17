# Scenario: Cloud RDS Management with MCP

This scenario demonstrates how to use MCP integration to manage cloud RDS instances directly from RDSAI CLI.

## Prerequisites

- MCP server configured (see [MCP Integration](../features/mcp.md))
- Alibaba Cloud RDS OpenAPI MCP Server installed
- Valid AccessKey ID and Secret configured

## Example

```text
mysql> /mcp list

# Name  Transport  Enabled  Status            Tools
─────────────────────────────────────────────────────────
1 rds   stdio      ✓       ● Connected       25

mysql> list all my RDS instances

🔧 Calling tool: rds.describe_db_instances
📊 Found 3 RDS instances:
  1. mysql-prod-01 (Running) - MySQL 8.0, 4C8G
  2. mysql-staging-02 (Running) - MySQL 8.0, 2C4G  
  3. mysql-dev-03 (Stopped) - MySQL 5.7, 1C2G

mysql> check performance metrics for mysql-prod-01 from the last hour

🔧 Calling tool: rds.describe_db_instance_performance
📊 Performance Metrics (Last Hour):
  - CPU Usage: 45% (avg), 78% (peak)
  - Memory Usage: 62%
  - IOPS: 1,234 (read), 567 (write)
  - Connections: 156/500

💡 Recommendation: CPU usage is normal, but consider monitoring during peak hours.

mysql> show me slow queries for mysql-prod-01

🔧 Calling tool: rds.describe_slow_log_records
📊 Top 5 Slow Queries:
  1. SELECT * FROM orders WHERE status = 'pending' (avg: 2.3s, count: 45)
  2. UPDATE users SET last_login = NOW() WHERE id = ? (avg: 1.8s, count: 120)
  ...

mysql> modify security IP whitelist for mysql-prod-01 to allow 192.168.1.0/24

🔧 Calling tool: rds.modify_security_ips
⚠️ This will modify the security IP whitelist for mysql-prod-01
Current whitelist: 10.0.0.0/8
New whitelist: 10.0.0.0/8, 192.168.1.0/24

Proceed? [y/N]: y
✓ Security IP whitelist updated successfully
```

## Capabilities

With MCP integration, you can:

- **Query RDS instances** — List, describe, and monitor cloud RDS instances
- **Performance monitoring** — Get real-time metrics, slow logs, and SQL insights
- **Instance management** — Create, modify specs, restart instances
- **Security management** — Manage IP whitelists, parameters, and configurations
- **Resource planning** — Query available zones, instance classes, and VPCs

## Available Tools

The [Alibaba Cloud RDS OpenAPI MCP Server](https://github.com/aliyun/alibabacloud-rds-openapi-mcp-server) provides:

- **Instance Management**: `create_db_instance`, `describe_db_instances`, `describe_db_instance_attribute`, `modify_db_instance_spec`, etc.
- **Monitoring & Logs**: `describe_db_instance_performance`, `describe_monitor_metrics`, `describe_error_logs`, etc.
- **Configuration**: `modify_parameter`, `describe_db_instance_parameters`, `modify_security_ips`, etc.
- **Network & Connection**: `describe_db_instance_net_info`, `allocate_instance_public_connection`, etc.
- **Resources & Planning**: `describe_available_zones`, `describe_available_classes`, `describe_vpcs`, `describe_vswitches`, etc.

## Natural Language Queries

You can use natural language to interact with MCP tools:

```text
mysql> list all my RDS instances
mysql> check performance metrics for mysql-prod-01
mysql> show me slow queries for mysql-prod-01
mysql> modify security IP whitelist to allow 192.168.1.0/24
mysql> create a new MySQL 8.0 instance with 4C8G
mysql> restart mysql-prod-01
```

## Related Documentation

See [MCP Integration](../features/mcp.md) for detailed setup and configuration instructions.

