# RDSAI CLI
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/aliyun/rdsai-cli)](https://github.com/aliyun/rdsai-cli/blob/main/LICENSE)

[English](README.md) | [中文](README_zh.md)

---
![image.png](docs/assets/img.png)

RDSAI CLI 是一款新一代的 AI 驱动 RDS CLI，它改变了您与数据库和文件交互的方式。您可以用自然语言或 SQL 描述您的意图，CLI 会对两者进行混合处理：它不仅能智能解析意图，还能主动进行性能诊断、分析执行计划、优化查询语句，甚至在发现问题时提供修复建议等，所有这些操作都无需离开您的终端。

## ✨ 功能特性

- **多数据源连接** — 连接 MySQL 数据库或文件（CSV、Excel），支持本地文件和远程 HTTP/HTTPS URL
- **AI 助手** — 自然语言查询（支持英文/中文），优化的 SQL、诊断和解释
- **智能 SQL** — 自动检测 SQL 与自然语言，查询历史，`Ctrl+E` 即时结果解释
- **多模型 LLM** — 支持 Qwen、OpenAI、DeepSeek、Anthropic、Gemini 和 OpenAI 兼容 API
- **模式分析** — AI 驱动的数据库分析，合规性检查和优化建议
- **性能基准测试** — 自动化 sysbench 测试和全面分析报告
- **MCP 集成** — 通过模型上下文协议服务器扩展功能
- **安全第一** — 默认只读，DDL/DML 需要确认（支持 YOLO 模式）

## 📦 安装

**系统要求：** Python 3.13+，网络访问 RDS 实例（MySQL），LLM 提供商 API 访问权限

```bash
# 一键安装（推荐）
curl -LsSf https://raw.githubusercontent.com/aliyun/rdsai-cli/main/install.sh | sh

# 或使用 uv
uv tool install --python 3.13 rdsai-cli

# 或使用 pip（推荐虚拟环境）
pip install rdsai-cli
```

## 🚀 快速开始

### 1. 启动和连接

```bash
# 不连接启动（交互模式）
rdsai

# 通过命令行连接
rdsai --host localhost -u root -p secret -D mydb

# 连接文件
rdsai
> /connect flights.csv
> /connect https://example.com/data.csv
```

### 2. 配置 LLM

```text
mysql> /setup
```

交互式向导将引导您完成 LLM 提供商配置。配置保存在 `~/.rdsai-cli/config.json`。

### 3. 基本使用

**SQL 执行：**
```text
mysql> SELECT COUNT(*) FROM users;
mysql> EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';
mysql> SELECT * FROM users LIMIT 10\G   -- 按 Ctrl+E 获取 AI 解释
```

**自然语言：**
```text
mysql> analyze index usage on users table
mysql> show me slow queries from the last hour
mysql> design an orders table for e-commerce
mysql> why this query is slow: SELECT * FROM users WHERE name LIKE '%john%'
```

**元命令：**
- `/connect`, `/disconnect` — 连接/断开数据库或文件
- `/setup` — 配置 LLM 提供商
- `/help` — 显示帮助和状态
- `/explain` — 分析 SQL 执行计划
- `/research` — 生成数据库模式分析报告
- `/benchmark` — 运行性能基准测试
- `/yolo` — 切换自动批准模式（谨慎使用）
- `/history` — 显示查询历史
- `/model` — 管理 LLM 模型

## 📚 文档

- **[完整教程](docs/tutorial_zh.md)** — 从入门到精通的完整使用指南
- **[核心功能](docs/features/)** — 执行计划分析、模式分析、基准测试、MCP 集成
- **[使用场景](docs/scenarios/)** — SQL 解释、文件分析、慢查询优化等

## 🔒 安全

- **默认只读** — 除非启用 YOLO 模式，否则 DDL/DML 需要明确确认
- **需要确认** — 每个写入操作在执行前都会显示确切的 SQL 以供审查
- **凭据存储** — API 密钥存储在 `~/.rdsai-cli/config.json`（请使用适当的权限保护）

## 🤝 贡献

我们欢迎各种形式的贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 📜 许可证

MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

在终端中使用 AI Agent 构建和调试 RDS 系统，享受愉快的体验 😁

