# RDSAI CLI
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/aliyun/rdsai-cli)](https://github.com/aliyun/rdsai-cli/blob/main/LICENSE)

[English](README.md) | [中文](README_zh.md)

---
![image.png](docs/assets/img.png)

RDSAI CLI is a next-generation, AI-powered RDS CLI that transforms how you interact with the database. You describe your intent in natural language or SQL, and the AI agent performs hybrid processing of both: orchestrating diagnostic tools, analyzing execution plans, and executing queries — all without leaving your terminal. From performance troubleshooting to schema exploration, it handles the complexity so you can focus on what truly matters.

## ✨ Features

- **AI Assistant for MySQL** — Ask in natural language (English / 中文均可), get optimized SQL, diagnostics, and explanations
- **Smart SQL Handling** — Auto-detects SQL vs natural language, supports SQL completer, query history, etc. 
- **Instant SQL Result Explanation** — Press `Ctrl+E` after any SQL query to get AI-powered explanations of results or errors, helping you understand query outcomes and troubleshoot issues quickly
- **Multi-Model LLM Support** — Work with multiple providers and models (Qwen, OpenAI, DeepSeek, Anthropic, Gemini, OpenAI-compatible) and switch via `/model`, with thinking mode support for transparent reasoning and decision-making processes
- **Database Schema Analysis** — Generate comprehensive database analysis reports with AI-powered schema review, index optimization suggestions, compliance checking against Alibaba Database Development Standards, and actionable recommendations
- **Sysbench Performance Benchmarking** — AI-powered performance testing with automated workflow (prepare → run → cleanup), comprehensive analysis reports including MySQL configuration analysis, InnoDB status analysis, bottleneck identification, and optimization recommendations
- **MCP (Model Context Protocol) Integration** — Extend capabilities by connecting to external MCP servers, including Alibaba Cloud RDS OpenAPI for cloud RDS instance management, monitoring, and operations
- **Safety First** — Read-only by default; DDL/DML requires confirmation (unless YOLO mode)
- **YOLO Mode** — One toggle to auto-approve all actions when you know what you're doing
- **SSL/TLS Support** — Full SSL configuration (CA, client cert, key, mode)

## 📦 Installation

### Requirements

- Python **3.13+**
- Network access to your RDS instance (currently only MySQL is supported)
- API access to at least one LLM provider (Qwen / OpenAI / DeepSeek / Anthropic / Gemini / OpenAI-compatible)
- **sysbench** (optional, for `/benchmark` command) — Install from [sysbench GitHub](https://github.com/akopytov/sysbench)

### Install from PyPI

We recommend using [uv](https://docs.astral.sh/uv/) as the Python package manager for faster installation and better dependency resolution.
For more installation options, see [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

```bash
# Using uv (recommended - provides isolated environment)
uv tool install --python 3.13 rdsai-cli

# Or using pip (may cause dependency conflicts with other packages)
# Recommended: Use virtual environment: python -m venv .venv && source .venv/bin/activate
pip install rdsai-cli
```

After installation, the `rdsai` command will be available globally. **Note:** Using `pip install` may cause dependency conflicts with other Python packages. We recommend using `uv tool install` or installing in a virtual environment.

### Install from source (for development)

```bash
git clone https://github.com/aliyun/rdsai-cli.git
cd rdsai-cli

# Using uv
uv sync
uv sync --extra dev  # with dev dependencies

# Or using pip
pip install -e ".[dev]"
```

For development installations, use `uv run rdsai` or activate the virtual environment first.

## 🚀 Quick Start

### 1. Launch the CLI

```bash
# Start without connection (interactive mode)
rdsai

# Connect via command line arguments
rdsai --host localhost -u root -p secret -D mydb

# With SSL
rdsai --host db.example.com -u admin -p secret \
  --ssl-mode REQUIRED --ssl-ca /path/to/ca.pem

# Custom port
rdsai --host localhost -P 3307 -u root -p secret
```

You can start the CLI **without any connection parameters** and connect later using the interactive `/connect` command:

```text
$ rdsai
> /connect
# Interactive form will prompt for Host, Port, Username, Password, Database
```

**Connection options:**

| Option       | Short | Description                         | Default |
| ------------ | ----- | ----------------------------------- | ------- |
| `--host`     | `-h`  | Database host                       |         |
| `--user`     | `-u`  | Username                            |         |
| `--password` | `-p`  | Password                            |         |
| `--port`     | `-P`  | Port                                | `3306`  |
| `--database` | `-D`  | Default database                    |         |
| `--yolo`     | `-y`  | Auto-approve all actions            | off     |
| `--ssl-mode` |       | SSL mode                            |         |
| `--ssl-ca`   |       | CA certificate path                 |         |
| `--ssl-cert` |       | Client certificate path             |         |
| `--ssl-key`  |       | Client key path                     |         |

SSL modes: `DISABLED`, `PREFERRED`, `REQUIRED`, `VERIFY_CA`, `VERIFY_IDENTITY`

### 2. Configure LLM

Use the interactive wizard to configure your LLM provider:

```text
mysql> /setup
```

The wizard will walk you through:

1. **Select Platform** — Qwen, OpenAI, DeepSeek, Anthropic, Gemini, or a generic OpenAI-compatible endpoint
2. **Configure API** — Base URL (if needed), API Key, Model Name
3. **Save & Apply** — Configuration is persisted and the shell is reloaded automatically

**Configuration file:**
- Path: `~/.rdsai-cli/config.json`
- Contains: providers, models, language, default model settings

You can edit this JSON manually for advanced setups.

## 📖 Basic Usage

### SQL Execution

Plain SQL is executed directly against MySQL, with results formatted via Rich:

```text
mysql> SELECT COUNT(*) FROM users;
mysql> SHOW CREATE TABLE orders;
mysql> EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';
mysql> SELECT * FROM users LIMIT 10\G   -- vertical format
```

**Quick Explain with Ctrl+E**: After executing any SQL query, press `Ctrl+E` to get an AI-powered explanation of the result or error. This helps you understand:
- What the query result means
- Why a query might be slow or return unexpected results
- The cause of SQL errors and how to fix them

The explain hint (`💡 Ctrl+E: Explain result` or `💡 Ctrl+E: Explain error`) is automatically shown after each query execution.

### Natural Language

Just type what you need; the agent will call tools, run DDL SQL (with confirmation), and explain results:

```text
mysql> analyze index usage on users table
mysql> show me slow queries from the last hour
mysql> check for lock waits
mysql> design an orders table for e-commerce
mysql> why this query is slow: SELECT * FROM users WHERE name LIKE '%john%'
mysql> find tables without primary keys
mysql> show me the replication status
```

The shell automatically:
- Detects whether input is **SQL** or **natural language**
- Records query execution history
- Injects the last query result into the AI context when helpful

### Meta Commands

Meta commands start with `/` and never hit MySQL directly.

| Command       | Alias          | Description                                      |
| ------------- | -------------- | ------------------------------------------------ |
| `/connect`    | `/conn`        | Connect to MySQL database interactively          |
| `/disconnect` | `/disconn`     | Disconnect from current database                 |
| `/help`       | `/h`, `/?`     | Show help and current status                     |
| `/exit`       | `/quit`        | Exit CLI                                         |
| `/version`    |                | Show CLI version                                 |
| `/setup`      |                | Interactive LLM configuration wizard             |
| `/reload`     |                | Reload configuration                             |
| `/clear`      | `/reset`       | Clear AI context (start fresh)                   |
| `/compact`    |                | Compact AI context to save tokens                |
| `/yolo`       |                | Toggle YOLO mode (auto-approve actions)          |
| `/history`    | `/hist`        | Show SQL query execution history                 |
| `/model`      | `/models`      | Manage LLM models (list/use/delete/info)         |
| `/explain`    |                | Analyze SQL execution plan with AI-powered insights        |
| `/research`   |                | Generate comprehensive database schema analysis report      |
| `/benchmark`  |                | Run sysbench performance test with AI-powered analysis      |
| `/mcp`        |                | Manage MCP servers (list/connect/disconnect/enable/disable) |

You can still run shell commands via the built-in shell mode when prefixed appropriately (see in-shell help).

## 📚 Documentation

### Complete Tutorial

- **[Complete Tutorial](docs/tutorial.md)** — Comprehensive guide from beginner to advanced, including quick start, basic operations, AI features, advanced capabilities, best practices, and FAQ

### Core Features

- **[Execution Plan Analysis (`/explain`)](docs/features/execution-plan-analysis.md)** — AI-powered SQL execution plan analysis with performance optimization suggestions
- **[Database Schema Analysis (`/research`)](docs/features/research.md)** — Comprehensive schema analysis and compliance checking against Alibaba Database Development Standards
- **[Performance Benchmarking (`/benchmark`)](docs/features/benchmark.md)** — AI-powered sysbench testing with automated workflow and comprehensive analysis reports
- **[MCP Integration](docs/features/mcp.md)** — Extend capabilities by connecting to external MCP servers for cloud RDS management and more

### Usage Scenarios

- **[SQL Result Explanation with Ctrl+E](docs/scenarios/sql-result-explanation.md)** — Get instant AI-powered explanations of query results and errors using the `Ctrl+E` shortcut
- **[Slow Query Analysis & Optimization](docs/scenarios/slow-query-analysis.md)** — Identify and optimize slow queries using AI-powered analysis
- **[Lock Wait & Deadlock Troubleshooting](docs/scenarios/lock-troubleshooting.md)** — Diagnose and resolve lock contention issues
- **[Database Schema Analysis & Compliance Review](docs/scenarios/schema-analysis.md)** — Comprehensive schema review with compliance checking
- **[Performance Benchmarking & Optimization](docs/scenarios/performance-benchmarking.md)** — Run performance tests and get optimization recommendations
- **[Cloud RDS Management with MCP](docs/scenarios/cloud-rds-management.md)** — Manage cloud RDS instances directly from the CLI

## ⚡ YOLO Mode

YOLO mode skips confirmation prompts for potentially destructive actions (DDL/DML).

```bash
# Enable at startup
rdsai --host localhost -u root -p secret --yolo
```

```text
# Toggle at runtime
mysql> /yolo on
mysql> /yolo off
```

Use this **only** in non-production or when you fully trust the actions being taken.

## 🔒 Security Notes

1. **Read-Only by Default** — The AI runs in a conservative mode; DDL/DML require explicit confirmation unless YOLO is on.
2. **Confirmation Required** — Every write operation surfaces the exact SQL for review before execution.
3. **Credential Storage** — API keys and model settings are stored in `~/.rdsai-cli/config.json`; protect that file with proper OS permissions.
4. **Transaction Safety** — The shell warns you about uncommitted transactions when you attempt to exit.

See [GitHub Issues](https://github.com/aliyun/rdsai-cli/issues) for detailed tracking.

## 🤝 Contributing

We welcome contributions of all kinds! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Code style guidelines
- Pull request process
- Issue reporting

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Enjoy building and debugging RDS systems with an AI agent in your terminal 😁
