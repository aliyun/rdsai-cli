# RDSAI CLI
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/aliyun/rdsai-cli)](https://github.com/aliyun/rdsai-cli/blob/main/LICENSE)

[English](README.md) | [中文](README_zh.md)

---
![image.png](docs/assets/img.png)

RDSAI CLI 是一款新一代的 AI 驱动 RDS CLI，它用来改变了您与数据库交互的方式。您可以用自然语言或 SQL 描述您的意图，CLI会对两者进行混合处理：它不仅能智能解析意图，还能主动进行性能诊断、分析执行计划、优化查询语句，甚至在发现问题时提供修复建议等，所有这些操作都无需离开您的终端，从性能故障排除到模式探索，它处理复杂性，让您专注于真正重要的事情。

## ✨ 功能特性

- **MySQL AI 助手** — 使用自然语言提问（支持英文/中文），获得优化的 SQL、诊断和解释
- **智能 SQL 处理** — 自动检测 SQL 与自然语言，支持 SQL 自动补全、查询历史等功能
- **即时 SQL 结果解释** — 执行任何 SQL 查询后按 `Ctrl+E` 即可获得 AI 驱动的结果或错误解释，帮助您快速理解查询结果并排查问题
- **多模型 LLM 支持** — 支持多个提供商和模型（Qwen、OpenAI、DeepSeek、Anthropic、Gemini、OpenAI 兼容），可通过 `/model` 切换，支持思考模式以透明展示推理和决策过程
- **Database Schema分析** — 生成全面的数据库分析报告，包括 AI 驱动的模式审查、索引优化建议、符合阿里巴巴数据库开发标准的合规性检查以及可操作的建议
- **Sysbench 性能基准测试** — AI 驱动的性能测试，自动化工作流程（prepare → run → cleanup），全面的分析报告包括 MySQL 配置分析、InnoDB 状态分析、瓶颈识别和优化建议
- **MCP（模型上下文协议）集成** — 通过连接到外部 MCP 服务器扩展功能，包括阿里云 RDS OpenAPI，用于云 RDS 实例管理、监控和操作
- **安全第一** — 默认只读；DDL/DML 需要确认（除非启用 YOLO 模式）
- **YOLO 模式** — 一键切换，当您知道自己在做什么时自动批准所有操作
- **SSL/TLS 支持** — 完整的 SSL 配置（CA、客户端证书、密钥、模式）

## 📦 安装

### 系统要求

- Python **3.13+**
- 网络访问您的 RDS 实例（目前仅支持 MySQL）
- 至少一个 LLM 提供商的 API 访问权限（Qwen / OpenAI / DeepSeek / Anthropic / Gemini / OpenAI 兼容）
- **sysbench**（可选，用于 `/benchmark` 命令）— 从 [sysbench GitHub](https://github.com/akopytov/sysbench) 安装

### 从 PyPI 安装

我们推荐使用 [uv](https://docs.astral.sh/uv/) 作为 Python 包管理器，以获得更快的安装速度和更好的依赖解析。
更多安装选项，请参阅 [uv 安装指南](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
# 使用 uv（推荐 - 提供隔离环境）
uv tool install --python 3.13 rdsai-cli

# 或使用 pip（可能与其他包产生依赖冲突）
# 推荐：使用虚拟环境：python -m venv .venv && source .venv/bin/activate
pip install rdsai-cli
```

安装后，`rdsai` 命令将在全局可用。**注意：** 使用 `pip install` 可能与其他 Python 包产生依赖冲突。我们推荐使用 `uv tool install` 或在虚拟环境中安装。

### 从源码安装（用于开发）

```bash
git clone https://github.com/aliyun/rdsai-cli.git
cd rdsai-cli

# 使用 uv
uv sync
uv sync --extra dev  # 包含开发依赖

# 或使用 pip
pip install -e ".[dev]"
```

对于开发安装，请使用 `uv run rdsai` 或先激活虚拟环境。

## 🚀 快速开始

### 1. 启动 CLI

```bash
# 不连接启动（交互模式）
rdsai

# 通过命令行参数连接
rdsai --host localhost -u root -p secret -D mydb

# 使用 SSL
rdsai --host db.example.com -u admin -p secret \
  --ssl-mode REQUIRED --ssl-ca /path/to/ca.pem

# 自定义端口
rdsai --host localhost -P 3307 -u root -p secret
```

您可以在**不提供任何连接参数**的情况下启动 CLI，稍后使用交互式 `/connect` 命令连接：

```text
$ rdsai
> /connect
# 交互式表单将提示输入主机、端口、用户名、密码、数据库
```

**连接选项：**

| 选项         | 简写 | 描述               | 默认值 |
| ------------ | ---- | ------------------ | ------ |
| `--host`     | `-h` | 数据库主机         |        |
| `--user`     | `-u` | 用户名             |        |
| `--password` | `-p` | 密码               |        |
| `--port`     | `-P` | 端口               | `3306` |
| `--database` | `-D` | 默认数据库         |        |
| `--yolo`     | `-y` | 自动批准所有操作   | off    |
| `--ssl-mode` |      | SSL 模式           |        |
| `--ssl-ca`   |      | CA 证书路径        |        |
| `--ssl-cert` |      | 客户端证书路径     |        |
| `--ssl-key`  |      | 客户端密钥路径     |        |

SSL 模式：`DISABLED`、`PREFERRED`、`REQUIRED`、`VERIFY_CA`、`VERIFY_IDENTITY`

### 2. 配置 LLM

使用交互式向导配置您的 LLM 提供商：

```text
mysql> /setup
```

向导将引导您完成：

1. **选择平台** — Qwen、OpenAI、DeepSeek、Anthropic、Gemini 或通用 OpenAI 兼容端点
2. **配置 API** — 基础 URL（如需要）、API 密钥、模型名称
3. **保存并应用** — 配置将被持久化，shell 会自动重新加载

**配置文件：**
- 路径：`~/.rdsai-cli/config.json`
- 包含：提供商、模型、语言、默认模型设置

您可以手动编辑此 JSON 文件以进行高级设置。

## 📖 基本使用

### SQL 执行

纯 SQL 直接针对 MySQL 执行，结果通过 Rich 格式化：

```text
mysql> SELECT COUNT(*) FROM users;
mysql> SHOW CREATE TABLE orders;
mysql> EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';
mysql> SELECT * FROM users LIMIT 10\G   -- 垂直格式
```

**使用 Ctrl+E 快速解释**：执行任何 SQL 查询后，按 `Ctrl+E` 即可获得 AI 驱动的结果或错误解释。这有助于您理解：
- 查询结果的含义
- 查询可能缓慢或返回意外结果的原因
- SQL 错误的原因以及如何修复

解释提示（`💡 Ctrl+E: Explain result` 或 `💡 Ctrl+E: Explain error`）会在每次查询执行后自动显示。

### 自然语言

只需输入您需要的内容；Agent将调用工具、运行 DDL SQL（需要确认）并解释结果：

```text
mysql> analyze index usage on users table
mysql> show me slow queries from the last hour
mysql> check for lock waits
mysql> design an orders table for e-commerce
mysql> why this query is slow: SELECT * FROM users WHERE name LIKE '%john%'
mysql> find tables without primary keys
mysql> show me the replication status
```

Shell 会自动：
- 检测输入是 **SQL** 还是 **自然语言**
- 记录查询执行历史
- 在有用时将最后一个查询结果注入 AI 上下文

### 元命令

元命令以 `/` 开头，不会直接访问 MySQL。

| 命令         | 别名          | 描述                                           |
| ------------ | ------------- | ---------------------------------------------- |
| `/connect`   | `/conn`       | 交互式连接到 MySQL 数据库                      |
| `/disconnect`| `/disconn`    | 断开当前数据库连接                             |
| `/help`      | `/h`, `/?`    | 显示帮助和当前状态                             |
| `/exit`      | `/quit`       | 退出 CLI                                       |
| `/version`   |               | 显示 CLI 版本                                  |
| `/setup`     |               | 交互式 LLM 配置向导                            |
| `/reload`    |               | 重新加载配置                                   |
| `/clear`     | `/reset`      | 清除 AI 上下文（重新开始）                     |
| `/compact`   |               | 压缩 AI 上下文以节省 token                     |
| `/yolo`      |               | 切换 YOLO 模式（自动批准操作）                 |
| `/history`   | `/hist`       | 显示 SQL 查询执行历史                          |
| `/model`     | `/models`     | 管理 LLM 模型（列出/使用/删除/信息）           |
| `/research`  |               | 生成全面的数据库模式分析报告                   |
| `/benchmark` |               | 运行 sysbench 性能测试并提供 AI 驱动的分析     |
| `/mcp`       |               | 管理 MCP 服务器（列出/连接/断开/启用/禁用）    |

您仍然可以通过内置的 shell 模式在适当的前缀下运行 shell 命令（请参阅 shell 内帮助）。

## 📚 文档

### 完整教程

- **[完整教程](docs/tutorial_zh.md)** — 从入门到精通的完整使用指南，包含快速开始、基础操作、AI 功能、高级特性、最佳实践和常见问题

### 核心功能

- **[Database Schema分析 (`/research`)](docs/features/research_zh.md)** — 全面的模式分析和符合阿里巴巴数据库开发标准的合规性检查
- **[性能基准测试 (`/benchmark`)](docs/features/benchmark_zh.md)** — AI 驱动的 sysbench 测试，自动化工作流程和全面的分析报告
- **[MCP 集成](docs/features/mcp_zh.md)** — 通过连接到外部 MCP 服务器扩展功能，用于云 RDS 管理等

### 使用场景

- **[使用 Ctrl+E 进行 SQL 结果解释](docs/scenarios/sql-result-explanation_zh.md)** — 使用 `Ctrl+E` 快捷键获得即时的 AI 驱动查询结果和错误解释
- **[慢查询分析与优化](docs/scenarios/slow-query-analysis_zh.md)** — 使用 AI 驱动的分析识别和优化慢查询
- **[锁等待与死锁故障排除](docs/scenarios/lock-troubleshooting_zh.md)** — 诊断和解决锁竞争问题
- **[数据库模式分析与合规性审查](docs/scenarios/schema-analysis_zh.md)** — 全面的模式审查和合规性检查
- **[性能基准测试与优化](docs/scenarios/performance-benchmarking_zh.md)** — 运行性能测试并获得优化建议
- **[使用 MCP 进行云 RDS 管理](docs/scenarios/cloud-rds-management_zh.md)** — 直接从 CLI 管理云 RDS 实例

## ⚡ YOLO 模式

YOLO 模式跳过潜在破坏性操作（DDL/DML）的确认提示。

```bash
# 启动时启用
rdsai --host localhost -u root -p secret --yolo
```

```text
# 运行时切换
mysql> /yolo on
mysql> /yolo off
```

**仅在**非生产环境或您完全信任正在执行的操作时使用此模式。

## 🔒 安全说明

1. **默认只读** — AI 以保守模式运行；除非启用 YOLO，否则 DDL/DML 需要明确确认。
2. **需要确认** — 每个写入操作在执行前都会显示确切的 SQL 以供审查。
3. **凭据存储** — API 密钥和模型设置存储在 `~/.rdsai-cli/config.json` 中；请使用适当的操作系统权限保护该文件。
4. **事务安全** — 当您尝试退出时，shell 会警告您有关未提交的事务。

详细跟踪请参阅 [GitHub Issues](https://github.com/aliyun/rdsai-cli/issues)。

## 🤝 贡献

我们欢迎各种形式的贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解：

- 开发设置
- 代码风格指南
- Pull Request 流程
- 问题报告

## 📜 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

在终端中使用 AI Agent构建和调试 RDS 系统，享受愉快的体验 😁

