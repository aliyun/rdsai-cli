# 场景：使用 MCP 进行云 RDS 管理

[English](cloud-rds-management.md) | [中文](cloud-rds-management_zh.md)

本场景演示如何使用 MCP 集成直接从 RDSAI CLI 管理云 RDS 实例。

## 前置要求

- 已配置 MCP 服务器（请参阅 [MCP 集成](../features/mcp_zh.md)）
- 已安装阿里云 RDS OpenAPI MCP 服务器
- 已配置有效的 AccessKey ID 和 Secret

## 示例

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

## 功能

通过 MCP 集成，您可以：

- **查询 RDS 实例** — 列出、描述和监控云 RDS 实例
- **性能监控** — 获取实时指标、慢日志和 SQL 洞察
- **实例管理** — 创建、修改规格、重启实例
- **安全管理** — 管理 IP 白名单、参数和配置
- **资源规划** — 查询可用区、实例规格和 VPC

## 可用工具

[阿里云 RDS OpenAPI MCP 服务器](https://github.com/aliyun/alibabacloud-rds-openapi-mcp-server) 提供：

- **实例管理**：`create_db_instance`、`describe_db_instances`、`describe_db_instance_attribute`、`modify_db_instance_spec` 等
- **监控和日志**：`describe_db_instance_performance`、`describe_monitor_metrics`、`describe_error_logs` 等
- **配置**：`modify_parameter`、`describe_db_instance_parameters`、`modify_security_ips` 等
- **网络和连接**：`describe_db_instance_net_info`、`allocate_instance_public_connection` 等
- **资源和规划**：`describe_available_zones`、`describe_available_classes`、`describe_vpcs`、`describe_vswitches` 等

## 自然语言查询

您可以使用自然语言与 MCP 工具交互：

```text
mysql> list all my RDS instances
mysql> check performance metrics for mysql-prod-01
mysql> show me slow queries for mysql-prod-01
mysql> modify security IP whitelist to allow 192.168.1.0/24
mysql> create a new MySQL 8.0 instance with 4C8G
mysql> restart mysql-prod-01
```

## 相关文档

详细的设置和配置说明请参阅 [MCP 集成](../features/mcp_zh.md)。

