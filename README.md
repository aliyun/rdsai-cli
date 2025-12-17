# RDSAI CLI

---
![img.png](docs/assets/img.png)

RDSAI CLI is a next-generation, AI-powered RDS CLI that transforms how you interact with the database. You describe your intent in natural language or SQL, and the AI agent performs hybrid processing of both: orchestrating diagnostic tools, analyzing execution plans, and executing queries — all without leaving your terminal. From performance troubleshooting to schema exploration, it handles the complexity so you can focus on what truly matters.

## ✨ Features

- **AI Assistant for MySQL** — Ask in natural language (English / 中文均可), get optimized SQL, diagnostics, and explanations
- **Smart SQL Handling** — Auto-detects SQL vs natural language, supports SQL completer, query history, etc. 
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
# Using uv (recommended)
uv tool install --python 3.13 rdsai-cli

# Or using pip
pip install rdsai-cli
```

After installation, the `rdsai` command will be available globally.

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

Connection options:

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

Configuration file:

- Path: `~/.rdsai-cli/config.json`
- Contains: providers, models, language, default model settings

You can edit this JSON manually for advanced setups.

## 📖 Usage

### SQL Execution

Plain SQL is executed directly against MySQL, with results formatted via Rich:

```text
mysql> SELECT COUNT(*) FROM users;
mysql> SHOW CREATE TABLE orders;
mysql> EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';
mysql> SELECT * FROM users LIMIT 10\G   -- vertical format
```

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
| `/research`   |                | Generate comprehensive database schema analysis report      |
| `/benchmark`  |                | Run sysbench performance test with AI-powered analysis      |
| `/mcp`        |                | Manage MCP servers (list/connect/disconnect/enable/disable) |

You can still run shell commands via the built-in shell mode when prefixed appropriately (see in-shell help).

### 🔍 Database Schema Analysis (`/research`)

The `/research` command generates comprehensive database analysis reports powered by AI. It analyzes your database schema, checks compliance against Alibaba Database Development Standards, and provides actionable recommendations.

#### What It Analyzes

- **Database Overview** — Total tables, size, engine distribution, statistics
- **Table Structure** — Columns, data types, primary keys, comments
- **Index Analysis** — Index coverage, redundancy detection, missing indexes, naming compliance
- **Relationship Analysis** — Foreign keys, table relationships, orphan tables
- **Compliance Checking** — Naming conventions, design standards, index design against Alibaba standards
- **Issue Detection** — Prioritized issues (P0/P1/P2/P3) with severity classification
- **Optimization Suggestions** — Specific SQL recommendations with impact analysis

#### Usage

```text
# Analyze entire database
mysql> /research

# Analyze specific tables only
mysql> /research orders users products

# Show help
mysql> /research help
```

#### Use Cases

- **Schema Review** — Before deploying to production, get a comprehensive compliance check
- **Code Review** — Analyze database changes and ensure they meet standards
- **Performance Audit** — Identify missing indexes, redundant indexes, and optimization opportunities
- **Migration Preparation** — Review schema before migrating to ensure best practices
- **Onboarding** — Understand existing database structure and identify issues quickly
- **Compliance Checking** — Ensure database design follows Alibaba Database Development Standards

#### Report Structure

The analysis report includes:

1. **Executive Summary** — Overall compliance score, critical issues count, top priorities
2. **Database Overview** — Statistics, engine distribution, size breakdown
3. **Table Analysis** — Detailed analysis of each table's structure and compliance
4. **Index Analysis** — Index coverage, redundancy, naming compliance, selectivity assessment
5. **Relationship Analysis** — Foreign key relationships and patterns
6. **Compliance Scores** — Breakdown by category (Naming, Table Design, Index Design)
7. **Issues Found** — Prioritized list with severity (P0/P1/P2/P3)
8. **Recommendations** — Actionable SQL fixes with impact analysis and risk assessment

### ⚡ Sysbench Performance Benchmarking (`/benchmark`)

The `/benchmark` command runs comprehensive database performance tests using sysbench, with AI-powered analysis and optimization recommendations.

#### What It Does

The benchmark workflow executes a complete performance testing cycle:

1. **Prepare Phase** — Creates test data (tables and rows) for benchmarking
2. **Run Phase** — Executes performance tests with specified workload and concurrency
3. **Analysis Phase** — Collects MySQL configuration, InnoDB status, and process information
4. **Cleanup Phase** — Removes test data (unless `--no-cleanup` is specified)

After benchmark completion, a comprehensive analysis report is generated including:
- **Performance Metrics** — TPS (Transactions Per Second), QPS (Queries Per Second), latency statistics
- **MySQL Configuration Analysis** — Parameter optimization recommendations based on benchmark results
- **InnoDB Status Analysis** — Buffer pool hit rate, lock waits, transaction analysis
- **Bottleneck Identification** — CPU-bound, I/O-bound, memory-bound, lock contention analysis
- **Optimization Recommendations** — Prioritized (P0/P1/P2/P3) actionable recommendations with expected impact

#### Prerequisites

- **sysbench must be installed** — Install from [sysbench GitHub](https://github.com/akopytov/sysbench)
- **Database must exist** — Create the target database before running benchmarks (e.g., `CREATE DATABASE testdb;`)
- **LLM configured** — Use `/setup` to configure an LLM model

#### Usage

```text
# Let agent intelligently choose test parameters
mysql> /benchmark run

# Quick test with 100 threads for 60 seconds
mysql> /benchmark --threads=100 --time=60

# Read-only workload test
mysql> /benchmark oltp_read_only -t 50 -T 120

# Large dataset test with 10 tables, 1M rows each
mysql> /benchmark --tables=10 --table-size=1000000

# Custom test with all parameters
mysql> /benchmark oltp_read_write --threads=200 --time=300 --tables=5 --table-size=500000

# Keep test data after benchmark
mysql> /benchmark --no-cleanup

# Show help
mysql> /benchmark --help
```

#### Test Types

- `oltp_read_write` — OLTP read-write workload (default)
- `oltp_read_only` — OLTP read-only workload
- `select` — Simple SELECT queries
- `insert` — INSERT operations
- `update_index` — UPDATE operations with index
- `delete` — DELETE operations

#### Options

| Option                  | Short | Description                                    | Default |
| ----------------------- | ----- | ---------------------------------------------- | ------- |
| `--threads`, `-t`       | `-t`  | Number of concurrent threads                   | 1       |
| `--time`, `-T`          | `-T`  | Test duration in seconds                       | 60      |
| `--events`, `-e`        | `-e`  | Total number of events (alternative to --time) |         |
| `--tables`              |       | Number of tables                               | 1       |
| `--table-size`          |       | Number of rows per table                       | 10000   |
| `--rate`                |       | Target transactions per second (rate limiting) |         |
| `--report-interval`     |       | Report interval in seconds                     | 10      |
| `--no-cleanup`          |       | Don't cleanup test data after test            | false   |
| `--help`, `-h`          | `-h`  | Show help message                              |         |

#### Use Cases

- **Performance Baseline** — Establish performance baseline before optimization
- **Configuration Tuning** — Test impact of MySQL parameter changes
- **Capacity Planning** — Understand database capacity under different workloads
- **Optimization Validation** — Verify performance improvements after optimizations
- **Load Testing** — Test database behavior under high concurrency
- **Bottleneck Analysis** — Identify CPU, I/O, memory, or lock contention issues

#### Report Structure

The benchmark analysis report includes:

1. **Benchmark Summary** — Test configuration, TPS/QPS/latency metrics
2. **MySQL Configuration Analysis** — Parameter analysis with optimization recommendations
3. **InnoDB Status Analysis** — Buffer pool metrics, lock waits, transaction analysis
4. **Performance Bottleneck Identification** — Primary bottleneck with evidence and impact
5. **Optimization Recommendations** — Prioritized recommendations with expected impact and risk assessment

### 🔌 MCP (Model Context Protocol) Integration

RDSAI CLI supports connecting to external MCP servers to extend its capabilities. This enables cloud RDS management, API integrations, and more.

#### Quick Start

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

#### MCP Management Commands

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

#### Example: Alibaba Cloud RDS OpenAPI MCP

The [Alibaba Cloud RDS OpenAPI MCP Server](https://github.com/aliyun/alibabacloud-rds-openapi-mcp-server) provides tools for managing cloud RDS instances:

**Available Tools:**

- **Instance Management**: `create_db_instance`, `describe_db_instances`, `describe_db_instance_attribute`, `modify_db_instance_spec`, etc.
- **Monitoring & Logs**: `describe_db_instance_performance`, `describe_monitor_metrics`, `describe_error_logs`, etc.
- **Configuration**: `modify_parameter`, `describe_db_instance_parameters`, `modify_security_ips`, etc.
- **Network & Connection**: `describe_db_instance_net_info`, `allocate_instance_public_connection`, etc.
- **Resources & Planning**: `describe_available_zones`, `describe_available_classes`, `describe_vpcs`, `describe_vswitches`, etc.


#### Configuration Options

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

#### Requirements

- MCP server must be installed and accessible
- For Alibaba Cloud RDS: Valid AccessKey ID and Secret
- Configuration file: `~/.rdsai-cli/mcp.yaml`
- Enabled servers are automatically connected on startup

## 💡 Usage Scenarios

### Scenario 1: Slow Query Analysis & Optimization

```text
mysql> show me slow queries from the last hour and analyze them

🔧 Calling tool: SlowLog
📊 Found 3 slow queries. Slowest: SELECT * FROM orders WHERE status = 'pending' (12.34s)

🔧 Calling tool: MySQLExplain
⚠️ Problem: Full table scan on `orders` (1.5M rows), no index on `status`

💡 Recommendation: CREATE INDEX idx_orders_status ON orders(status);
   Expected: Query time drops from ~12s to <100ms

Would you like me to create this index? [y/N]
```

The AI chains **SlowLog** → **MySQLExplain** → **TableIndex** for complete analysis.

---

### Scenario 2: Lock Wait & Deadlock Troubleshooting

```text
mysql> check for lock waits

🔧 Calling tool: Transaction
🔒 1 Lock Wait Detected:
   • Blocker: Connection 42 (idle 45s, uncommitted transaction)
     Query: UPDATE users SET balance = balance - 100 WHERE id = 1001
   • Waiting: Connection 56 (waiting 15s for row lock)

💡 Suggestion: Connection 42 holds lock but is idle. Consider KILL 42 if safe.
```

The AI combines **Transaction** + **ShowProcess** to trace lock chains.

---

### Scenario 3: Database Schema Analysis & Compliance Review

```text
mysql> /research

Exploring database: ecommerce_db
✓ Explored 12 tables (156 columns, 8 relationships)
Analyzing schema...

📊 Database Analysis Report

## Executive Summary
- Database: ecommerce_db
- Total Tables: 12
- Overall Compliance Score: 72/100 ⚠️
- Critical Issues: 3 (P0/P1)
- Top Priority Actions:
  1. Add primary keys to `user_sessions` and `audit_logs` tables
  2. Fix index naming conventions (5 violations)
  3. Replace `float` with `decimal` in `orders.total_amount`

## Issues Found

🔴 Critical (P0):
- Table `user_sessions` missing primary key
- Table `audit_logs` missing primary key
- Field `orders.total_amount` uses `float` instead of `decimal`

🟡 Warning (P2):
- Index `idx1` on `users` table violates naming convention (should be `idx_user_email`)
- Redundant index: `idx_user_id` is prefix of `idx_user_id_status`
- Missing table comments on 3 tables

## Recommendations

### [P0] Add Primary Keys
**Location**: `user_sessions`, `audit_logs`
**SQL**:
```sql
ALTER TABLE user_sessions ADD COLUMN id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
ALTER TABLE audit_logs ADD COLUMN id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```

The `/research` command analyzes your entire database schema, checks compliance against Alibaba Database Development Standards, and provides prioritized recommendations.

---

### Scenario 4: Performance Benchmarking & Optimization

RDSAI CLI provides AI-powered sysbench benchmarking with comprehensive analysis and optimization recommendations.

```text
mysql> CREATE DATABASE benchmark_test;
Query OK, 1 row affected (0.01 sec)

mysql> USE benchmark_test;
Database changed

mysql> /benchmark run

Benchmark Configuration:
  Database: benchmark_test
  Mode: Agent will intelligently choose parameters

⚠ Warning: This benchmark will put significant load on the database.
Target database: benchmark_test
Make sure this is appropriate for your environment.

Do you want to proceed with the benchmark on database 'benchmark_test'?
> Yes, start benchmark

Starting benchmark...
The agent will intelligently configure the test and generate analysis report.

🔧 Preparing test data with 1 table, 100,000 rows each...
✓ Successfully prepared 1 table(s) with 100,000 rows each (total: 100,000 rows)

🔧 Executing benchmark with 50 threads for 60 seconds...
Performance test completed for 60 seconds with 50 thread(s) - TPS: 1250.45, QPS: 25009.00, Avg Latency: 39.95ms

🔧 Collecting MySQL configuration and InnoDB status for analysis...

📊 Benchmark Analysis Report

## Benchmark Summary

**Test Configuration:**
- Test Type: oltp_read_write
- Threads: 50
- Duration: 60 seconds
- Tables: 1
- Table Size: 100,000 rows

**Performance Metrics:**
- TPS: 1,250.45 transactions/sec
- QPS: 25,009.00 queries/sec
- Average Latency: 39.95ms

## MySQL Configuration Analysis

### Critical Issues Found:

🔴 **P0 - Buffer Pool Too Small**
- **Current**: innodb_buffer_pool_size = 128MB
- **Impact**: Buffer pool hit rate: 87% (< 99% target)
- **Root Cause**: Buffer pool is too small for workload, causing frequent disk I/O
- **Recommendation**: Increase to 2GB (70% of available RAM)
- **Expected Impact**: TPS improvement from 1,250 to 1,600-1,800 (28-44% improvement)
- **Risk**: Low (can be changed dynamically)
- **SQL**: `SET GLOBAL innodb_buffer_pool_size = 2147483648;`

🟡 **P1 - InnoDB Log File Size Too Small**
- **Current**: innodb_log_file_size = 48MB
- **Impact**: High log write activity, potential write bottleneck
- **Recommendation**: Increase to 256MB
- **Expected Impact**: 10-15% TPS improvement for write-heavy workloads
- **Risk**: Medium (requires MySQL restart)

## InnoDB Status Analysis

**Buffer Pool Metrics:**
- Hit Rate: 87% ⚠️ (Target: > 99%)
- Pages Read: 15,234 (indicates frequent disk reads)
- Pages Written: 8,912

**Lock Analysis:**
- Lock Waits: 0 ✓
- Deadlocks: 0 ✓
- Active Transactions: 12

## Performance Bottleneck Identification

**Primary Bottleneck: I/O-bound**

**Evidence:**
- Buffer pool hit rate: 87% (< 99% target)
- High pages read: 15,234 during test
- Average latency: 39.95ms (higher than expected)

**Impact:** Estimated 30-40% TPS improvement if buffer pool is increased

**Priority:** P0 (Critical)

## Optimization Recommendations

### [P0] Increase InnoDB Buffer Pool Size
**Issue**: Buffer pool too small, causing frequent disk I/O
**Evidence**: Buffer pool hit rate 87%, TPS: 1,250
**Action**: Increase innodb_buffer_pool_size to 2GB
**Expected Impact**: TPS improvement from 1,250 to 1,600-1,800 (28-44%)
**Risk**: Low
**Verification**: Re-run benchmark and compare TPS

### [P1] Optimize InnoDB Log File Size
**Issue**: Log file size too small for write workload
**Evidence**: High log write activity during benchmark
**Action**: Increase innodb_log_file_size to 256MB (requires restart)
**Expected Impact**: 10-15% TPS improvement
**Risk**: Medium

✓ Successfully cleaned up all tables
✓ Benchmark completed.
```

With `/benchmark`, you can:
- **Run automated benchmarks** — Complete workflow from data preparation to cleanup
- **Get AI-powered analysis** — Comprehensive reports with bottleneck identification
- **Receive optimization recommendations** — Prioritized suggestions with expected impact
- **Validate improvements** — Re-run benchmarks to verify optimization results

---

### Scenario 5: Cloud RDS Management with MCP

RDSAI CLI integrates with [Alibaba Cloud RDS OpenAPI MCP Server](https://github.com/aliyun/alibabacloud-rds-openapi-mcp-server) to enable cloud RDS instance management directly from the CLI.

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

With MCP integration, you can:
- **Query RDS instances** — List, describe, and monitor cloud RDS instances
- **Performance monitoring** — Get real-time metrics, slow logs, and SQL insights
- **Instance management** — Create, modify specs, restart instances
- **Security management** — Manage IP whitelists, parameters, and configurations
- **Resource planning** — Query available zones, instance classes, and VPCs


---

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