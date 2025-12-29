# RDSAI CLI 完整教程

[English](tutorial.md) | [中文](tutorial_zh.md)

本教程将带您从零开始，全面掌握 RDSAI CLI 的使用方法。无论您是数据库管理员、开发人员还是数据分析师，本教程都能帮助您高效地使用这个 AI 驱动的数据库工具。

## 📚 目录

1. [快速开始](#快速开始)
2. [基础操作](#基础操作)
3. [AI 功能使用](#ai-功能使用)
4. [高级功能](#高级功能)
5. [最佳实践](#最佳实践)
6. [常见问题](#常见问题)

---

## 快速开始

### 第一步：安装

```bash
# 使用 uv 安装（推荐）
uv tool install --python 3.13 rdsai-cli

# 或使用 pip
pip install rdsai-cli
```

### 第二步：启动 CLI

```bash
# 方式1：不连接启动，稍后使用 /connect 连接
rdsai

# 方式2：直接连接数据库
rdsai --host localhost -u root -p your_password -D my_database
```

### 第三步：配置 LLM

启动后，首先需要配置 AI 功能：

```text
mysql> /setup
```

按照向导完成配置：
1. 选择 LLM 提供商（Qwen、OpenAI、DeepSeek 等）
2. 输入 API 密钥
3. 选择模型
4. 保存配置

**提示**：配置文件保存在 `~/.rdsai-cli/config.json`，您可以手动编辑进行高级配置。

---

## 基础操作

### 连接数据库

#### 交互式连接

```text
mysql> /connect
```

系统会提示您输入：
- 主机地址
- 端口（默认 3306）
- 用户名
- 密码
- 数据库名（可选）

#### 命令行连接

```bash
rdsai --host db.example.com -P 3306 -u admin -p secret -D production_db
```

#### SSL 连接

```bash
rdsai --host db.example.com -u admin -p secret \
  --ssl-mode REQUIRED \
  --ssl-ca /path/to/ca.pem \
  --ssl-cert /path/to/client-cert.pem \
  --ssl-key /path/to/client-key.pem
```

### 执行 SQL 查询

#### 基本查询

```text
mysql> SELECT * FROM users LIMIT 10;
mysql> SHOW TABLES;
mysql> DESCRIBE orders;
```

#### 垂直格式显示

使用 `\G` 后缀以垂直格式显示结果：

```text
mysql> SELECT * FROM users WHERE id = 1\G
*************************** 1. row ***************************
        id: 1
     name: Alice
    email: alice@example.com
  created: 2024-01-15 10:30:00
```

#### 查看查询历史

```text
mysql> /history
```

显示最近执行的 SQL 查询，支持：
- 查看历史记录
- 重新执行查询
- 复制查询语句

### 元命令

| 命令 | 别名 | 功能 |
|------|------|------|
| `/connect` | `/conn` | 连接数据库 |
| `/disconnect` | `/disconn` | 断开连接 |
| `/help` | `/h`, `/?` | 显示帮助 |
| `/exit` | `/quit` | 退出 CLI |
| `/version` | | 显示版本 |
| `/setup` | | 配置 LLM |
| `/reload` | | 重新加载配置 |
| `/clear` | `/reset` | 清除 AI 上下文 |
| `/compact` | | 压缩 AI 上下文 |
| `/yolo` | | 切换 YOLO 模式 |
| `/history` | `/hist` | 查看查询历史 |
| `/model` | `/models` | 管理 LLM 模型 |

---

## AI 功能使用

### 自然语言查询

RDSAI CLI 的核心功能是理解自然语言并执行相应的数据库操作。

#### 基础查询

```text
mysql> show me all tables in the database
mysql> analyze index usage on users table
mysql> check for slow queries from the last hour
mysql> find tables without primary keys
```

#### 复杂分析

```text
mysql> why is this query slow: SELECT * FROM users WHERE name LIKE '%john%'
mysql> show me the replication status
mysql> check for lock waits and deadlocks
mysql> analyze the performance of the orders table
```

#### 表设计建议

```text
mysql> design an orders table for e-commerce
mysql> create a user table with proper indexes
mysql> suggest improvements for the products table schema
```

### 即时 SQL 结果解释（Ctrl+E）

执行任何 SQL 查询后，按 `Ctrl+E` 即可获得 AI 驱动的解释。

#### 解释查询结果

```text
mysql> SELECT COUNT(*) as total, AVG(age) as avg_age FROM users WHERE status = 'active';
+-------+---------+
| total | avg_age |
+-------+---------+
|  15234|    28.5  |
+-------+---------+
(1 row) 💡 Ctrl+E: Explain result

# 按 Ctrl+E
🤖 Explaining SQL result...

This query found 15,234 active users with an average age of 28.5 years. 
The result indicates a substantial user base with a relatively young demographic.
```

#### 解释错误

```text
mysql> SELECT * FROM orders WHERE customer_id = 123;
ERROR: Unknown column 'customer_id' in 'where clause' 💡 Ctrl+E: Explain error

# 按 Ctrl+E
🤖 Explaining SQL error...

The column `customer_id` doesn't exist in the `orders` table. Possible reasons:
1. The column name might be different (e.g., `customerId`, `cust_id`)
2. The column hasn't been created yet
3. You're querying the wrong table

To fix: Check the table structure with `DESCRIBE orders` or `SHOW CREATE TABLE orders`.
```

### 数据库模式分析（/research）

生成全面的数据库分析报告：

```text
mysql> /research
```

**分析内容**：
- 数据库概览和统计信息
- 表结构分析
- 索引优化建议
- 合规性检查（符合阿里巴巴数据库开发标准）
- 问题检测（按优先级分类）
- 可操作的优化建议

**分析特定表**：

```text
mysql> /research orders users products
```

**使用场景**：
- 部署前模式审查
- 代码审查中的数据库检查
- 性能审计和优化
- 迁移准备

### 性能基准测试（/benchmark）

运行 AI 驱动的 sysbench 性能测试：

```text
mysql> /benchmark
```

**功能**：
- 自动化工作流程（prepare → run → cleanup）
- MySQL 配置分析
- InnoDB 状态分析
- 瓶颈识别
- 优化建议

**自定义测试参数**：

```text
mysql> /benchmark --tables 10 --table-size 10000 --threads 4
```

---

## 高级功能

### 模型管理（/model）

#### 查看可用模型

```text
mysql> /model list
```

#### 切换模型

```text
mysql> /model use qwen-max
mysql> /model use gpt-4
```

#### 查看模型信息

```text
mysql> /model info
```

#### 删除模型配置

```text
mysql> /model delete old-model
```

### MCP 集成（/mcp）

MCP（Model Context Protocol）允许您连接外部服务器扩展功能。

#### 查看 MCP 服务器

```text
mysql> /mcp list
```

#### 连接 MCP 服务器

```text
mysql> /mcp connect rds-openapi
```

#### 启用/禁用服务器

```text
mysql> /mcp enable rds-openapi
mysql> /mcp disable rds-openapi
```

**支持的 MCP 服务器**：
- 阿里云 RDS OpenAPI（云 RDS 实例管理）
- 自定义 MCP 服务器

### YOLO 模式

YOLO 模式自动批准所有操作，无需确认提示。

**启用**：

```text
mysql> /yolo on
```

**禁用**：

```text
mysql> /yolo off
```

**启动时启用**：

```bash
rdsai --host localhost -u root -p secret --yolo
```

⚠️ **警告**：仅在非生产环境或完全信任操作时使用！

### 上下文管理

#### 清除上下文

```text
mysql> /clear
```

清除所有 AI 上下文，重新开始对话。

#### 压缩上下文

```text
mysql> /compact
```

压缩 AI 上下文以节省 token，保留重要信息。

### 诊断工具

RDSAI CLI 内置了多个诊断工具，可通过自然语言调用：

#### 表分析

```text
mysql> show me the structure of the users table
mysql> analyze indexes on the orders table
mysql> check table status for products
```

#### 查询分析

```text
mysql> explain this query: SELECT * FROM users WHERE email = 'test@example.com'
mysql> show me slow queries
mysql> check the process list
```

#### 性能分析

```text
mysql> show InnoDB status
mysql> check replication status
mysql> analyze performance statistics
```

#### 事务和锁

```text
mysql> check for lock waits
mysql> show current transactions
mysql> analyze deadlocks
```

---

## 最佳实践

### 1. 工作流程建议

#### 日常查询工作流

1. **连接数据库**
   ```text
   mysql> /connect
   ```

2. **探索数据库结构**
   ```text
   mysql> show me all tables
   mysql> describe the users table
   ```

3. **执行查询**
   ```text
   mysql> SELECT * FROM users WHERE status = 'active' LIMIT 10;
   ```

4. **理解结果**
   - 按 `Ctrl+E` 获得解释
   - 或使用自然语言："为什么这个查询返回了这些结果？"

5. **优化查询**
   ```text
   mysql> why is this query slow: [your query]
   mysql> suggest indexes for this query: [your query]
   ```

#### 性能分析工作流

1. **识别慢查询**
   ```text
   mysql> show me slow queries from the last hour
   ```

2. **分析查询性能**
   ```text
   mysql> explain this slow query: [query]
   ```

3. **获取优化建议**
   ```text
   mysql> how can I optimize this query: [query]
   ```

4. **验证优化**
   ```text
   mysql> /benchmark
   ```

#### 模式审查工作流

1. **全面分析**
   ```text
   mysql> /research
   ```

2. **查看问题**
   - 查看报告中的问题列表
   - 按优先级（P0/P1/P2/P3）处理

3. **应用修复**
   ```text
   mysql> [根据建议执行 SQL]
   ```

4. **验证修复**
   ```text
   mysql> /research [table_name]
   ```

### 2. 安全实践

#### 生产环境

- ❌ **不要**使用 YOLO 模式
- ✅ **总是**审查 DDL/DML 操作
- ✅ **使用**SSL 连接
- ✅ **限制**数据库用户权限

#### 凭据管理

- 配置文件权限：`chmod 600 ~/.rdsai-cli/config.json`
- 使用环境变量存储敏感信息（未来支持）
- 定期轮换 API 密钥

### 3. 性能优化

#### 查询优化

- 使用 `EXPLAIN` 分析查询计划
- 利用 AI 建议优化慢查询
- 定期运行 `/benchmark` 进行性能测试

#### 上下文管理

- 定期使用 `/compact` 压缩上下文
- 长时间会话后使用 `/clear` 重新开始
- 避免在上下文中积累过多历史

### 4. 学习 SQL

#### 使用 AI 解释学习

```text
mysql> SELECT u.name, COUNT(o.id) as orders 
       FROM users u 
       LEFT JOIN orders o ON u.id = o.user_id 
       GROUP BY u.id;
# 按 Ctrl+E 理解这个查询
```

#### 让 AI 生成查询

```text
mysql> write a query to find users who haven't placed any orders in the last 30 days
mysql> create a query to calculate monthly revenue by product category
```

#### 优化学习

```text
mysql> explain why this query is better: [optimized query]
mysql> compare these two queries: [query1] vs [query2]
```

---

## 常见问题

### 连接问题

**Q: 连接失败怎么办？**

```text
# 检查连接信息
mysql> /help

# 重新连接
mysql> /connect

# 查看错误详情
# 错误信息会显示在欢迎面板中
```

**Q: SSL 连接配置？**

```bash
rdsai --host db.example.com -u admin -p secret \
  --ssl-mode VERIFY_CA \
  --ssl-ca /path/to/ca.pem
```

### AI 功能问题

**Q: Ctrl+E 不工作？**

1. 确认已配置 LLM：`/setup`
2. 确认有活动的数据库连接
3. 确认最近执行了 SQL 查询

**Q: 自然语言查询不准确？**

- 使用更具体的描述
- 提供表名和列名
- 分步骤执行复杂查询

**Q: 如何切换 LLM 模型？**

```text
mysql> /model list
mysql> /model use [model_name]
```

### 性能问题

**Q: 查询执行很慢？**

```text
# 分析查询
mysql> explain this query: [your query]

# 检查慢查询日志
mysql> show me slow queries

# 检查进程列表
mysql> show process list
```

**Q: AI 响应慢？**

- 检查网络连接
- 尝试更快的模型
- 使用 `/compact` 减少上下文大小

### 配置问题

**Q: 配置文件在哪里？**

- LLM 配置：`~/.rdsai-cli/config.json`
- MCP 配置：`~/.rdsai-cli/mcp.yaml`（如果使用）
- 日志文件：`~/.rdsai-cli/logs/rdsai-cli.log`

**Q: 如何重置配置？**

```bash
# 备份现有配置
cp ~/.rdsai-cli/config.json ~/.rdsai-cli/config.json.bak

# 重新配置
rdsai
mysql> /setup
```

### 功能问题

**Q: /research 命令失败？**

- 确认数据库连接正常
- 检查是否有足够的权限访问 information_schema
- 查看日志文件了解详细错误

**Q: /benchmark 需要什么？**

- 需要安装 sysbench
- 需要足够的数据库权限
- 建议在测试环境运行

---

## 进阶技巧

### 1. 组合使用命令

```text
# 分析 → 优化 → 验证
mysql> /research orders
mysql> [根据建议执行优化]
mysql> /research orders  # 验证修复
```

### 2. 利用查询历史

```text
mysql> /history
# 查看历史，复制并修改查询
```

### 3. 批量操作

```text
# 分析多个表
mysql> /research table1 table2 table3

# 批量检查索引
mysql> check indexes on all tables
```

### 4. 导出结果

虽然当前版本不直接支持导出，但您可以：
- 使用 `SELECT ... INTO OUTFILE`（需要文件权限）
- 复制查询结果到剪贴板
- 使用重定向：`rdsai ... > output.txt`

### 5. 脚本化使用

```bash
# 非交互模式（未来支持）
echo "SELECT COUNT(*) FROM users;" | rdsai --host localhost -u root -p secret
```

---

## 下一步

- 阅读[场景文档](scenarios/)了解具体使用场景
- 查看[功能文档](features/)深入了解核心功能
- 访问 [GitHub](https://github.com/aliyun/rdsai-cli) 获取最新更新
- 提交 Issue 报告问题或建议功能

---

**祝您使用愉快！** 🚀

如有问题，请查看文档或提交 Issue。

