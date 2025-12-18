# MCP（模型上下文协议）集成

[English](mcp.md) | [中文](mcp_zh.md)

RDSAI CLI 支持连接到外部 MCP 服务器以扩展其功能。这支持云 RDS 管理、API 集成等功能。

## 快速开始

1. **创建 MCP 配置文件** `~/.rdsai-cli/mcp.yaml`：

> 💡 **提示**：您可以使用项目根目录中的 `mcp.example.yaml` 作为模板。将其复制到 `~/.rdsai-cli/mcp.yaml` 并根据您的需求进行自定义。

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
        # ... 根据需要添加更多工具
```

2. **列出已配置的 MCP 服务器**：

```text
mysql> /mcp list

# Name  Transport  Enabled  Status            Tools
─────────────────────────────────────────────────────────
1 rds   stdio      ✓       ● Connected       25
```

3. **连接到 MCP 服务器**（如果未自动连接）：

```text
mysql> /mcp connect rds
✓ Connected to rds. Loaded 25 tools.
```

4. **通过自然语言使用 MCP 工具**：

```text
mysql> list all my RDS instances
mysql> check performance metrics for mysql-prod-01
mysql> show me slow queries for mysql-prod-01
mysql> modify security IP whitelist to allow 192.168.1.0/24
```

## MCP 管理命令

```text
# 列出所有已配置的 MCP 服务器及其状态
mysql> /mcp list
mysql> /mcp ls

# 查看服务器的详细信息
mysql> /mcp view rds
mysql> /mcp info rds

# 连接到 MCP 服务器
mysql> /mcp connect rds

# 断开与 MCP 服务器的连接
mysql> /mcp disconnect rds

# 启用/禁用服务器（更新配置文件）
mysql> /mcp enable rds
mysql> /mcp disable rds

# 从文件重新加载 MCP 配置
mysql> /mcp reload
```

## 示例：阿里云 RDS OpenAPI MCP

[阿里云 RDS OpenAPI MCP 服务器](https://github.com/aliyun/alibabacloud-rds-openapi-mcp-server) 提供了管理云 RDS 实例的工具：

**可用工具：**

- **实例管理**：`create_db_instance`、`describe_db_instances`、`describe_db_instance_attribute`、`modify_db_instance_spec` 等
- **监控和日志**：`describe_db_instance_performance`、`describe_monitor_metrics`、`describe_error_logs` 等
- **配置**：`modify_parameter`、`describe_db_instance_parameters`、`modify_security_ips` 等
- **网络和连接**：`describe_db_instance_net_info`、`allocate_instance_public_connection` 等
- **资源和规划**：`describe_available_zones`、`describe_available_classes`、`describe_vpcs`、`describe_vswitches` 等

## 配置选项

**传输类型：**
- `stdio` — 用于基于本地命令的服务器（例如 `uvx`、`npx`）
- `sse` — 用于基于 HTTP 的服务器的服务器发送事件
- `streamable_http` — HTTP 流式传输（推荐用于 HTTP 服务器）

**工具过滤：**
- `include_tools` — 白名单，仅加载特定工具
- `exclude_tools` — 黑名单，排除特定工具

**带工具过滤的示例：**

```yaml
- name: rds
  transport: stdio
  command: uvx
  args:
    - "alibabacloud-rds-openapi-mcp-server@latest"
  env:
    ALIBABA_CLOUD_ACCESS_KEY_ID: "${ACCESS_ID}"
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: "${ACCESS_KEY}"
  # 仅加载只读工具
  include_tools:
    - describe_db_instances
    - describe_db_instance_attribute
    - describe_slow_log_records
```

## 要求

- MCP 服务器必须已安装且可访问
- 对于阿里云 RDS：需要有效的 AccessKey ID 和 Secret
- 配置文件：`~/.rdsai-cli/mcp.yaml`
- 启用的服务器在启动时自动连接

