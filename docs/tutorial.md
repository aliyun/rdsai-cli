# RDSAI CLI Complete Tutorial

[English](tutorial.md) | [中文](tutorial_zh.md)

This comprehensive tutorial will guide you from zero to mastery of RDSAI CLI. Whether you're a database administrator, developer, or data analyst, this tutorial will help you efficiently use this AI-powered database tool.

## 📚 Table of Contents

1. [Quick Start](#quick-start)
2. [Basic Operations](#basic-operations)
3. [AI Features](#ai-features)
4. [Advanced Features](#advanced-features)
5. [Best Practices](#best-practices)
6. [FAQ](#faq)

---

## Quick Start

### Step 1: Installation

```bash
# Using uv (recommended)
uv tool install --python 3.13 rdsai-cli

# Or using pip
pip install rdsai-cli
```

### Step 2: Launch CLI

```bash
# Method 1: Start without connection, connect later with /connect
rdsai

# Method 2: Connect directly
rdsai --host localhost -u root -p your_password -D my_database
```

### Step 3: Configure LLM

After launching, first configure AI features:

```text
mysql> /setup
```

Follow the wizard:
1. Select LLM provider (Qwen, OpenAI, DeepSeek, etc.)
2. Enter API key
3. Choose model
4. Save configuration

**Tip**: Configuration is saved in `~/.rdsai-cli/config.json`, which you can manually edit for advanced settings.

---

## Basic Operations

### Connecting to Database

#### Interactive Connection

```text
mysql> /connect
```

You'll be prompted for:
- Host address
- Port (default 3306)
- Username
- Password
- Database name (optional)

#### Command Line Connection

```bash
rdsai --host db.example.com -P 3306 -u admin -p secret -D production_db
```

#### SSL Connection

```bash
rdsai --host db.example.com -u admin -p secret \
  --ssl-mode REQUIRED \
  --ssl-ca /path/to/ca.pem \
  --ssl-cert /path/to/client-cert.pem \
  --ssl-key /path/to/client-key.pem
```

### Executing SQL Queries

#### Basic Queries

```text
mysql> SELECT * FROM users LIMIT 10;
mysql> SHOW TABLES;
mysql> DESCRIBE orders;
```

#### Vertical Format Display

Use `\G` suffix to display results in vertical format:

```text
mysql> SELECT * FROM users WHERE id = 1\G
*************************** 1. row ***************************
        id: 1
     name: Alice
    email: alice@example.com
  created: 2024-01-15 10:30:00
```

#### View Query History

```text
mysql> /history
```

Shows recently executed SQL queries with support for:
- Viewing history
- Re-executing queries
- Copying query statements

### Meta Commands

| Command | Alias | Function |
|---------|-------|----------|
| `/connect` | `/conn` | Connect to database |
| `/disconnect` | `/disconn` | Disconnect |
| `/help` | `/h`, `/?` | Show help |
| `/exit` | `/quit` | Exit CLI |
| `/version` | | Show version |
| `/setup` | | Configure LLM |
| `/reload` | | Reload configuration |
| `/clear` | `/reset` | Clear AI context |
| `/compact` | | Compact AI context |
| `/yolo` | | Toggle YOLO mode |
| `/history` | `/hist` | View query history |
| `/model` | `/models` | Manage LLM models |

---

## AI Features

### Natural Language Queries

The core feature of RDSAI CLI is understanding natural language and executing corresponding database operations.

#### Basic Queries

```text
mysql> show me all tables in the database
mysql> analyze index usage on users table
mysql> check for slow queries from the last hour
mysql> find tables without primary keys
```

#### Complex Analysis

```text
mysql> why is this query slow: SELECT * FROM users WHERE name LIKE '%john%'
mysql> show me the replication status
mysql> check for lock waits and deadlocks
mysql> analyze the performance of the orders table
```

#### Table Design Suggestions

```text
mysql> design an orders table for e-commerce
mysql> create a user table with proper indexes
mysql> suggest improvements for the products table schema
```

### Instant SQL Result Explanation (Ctrl+E)

Press `Ctrl+E` after any SQL query to get AI-powered explanations.

#### Explaining Query Results

```text
mysql> SELECT COUNT(*) as total, AVG(age) as avg_age FROM users WHERE status = 'active';
+-------+---------+
| total | avg_age |
+-------+---------+
|  15234|    28.5  |
+-------+---------+
(1 row) 💡 Ctrl+E: Explain result

# Press Ctrl+E
🤖 Explaining SQL result...

This query found 15,234 active users with an average age of 28.5 years. 
The result indicates a substantial user base with a relatively young demographic.
```

#### Explaining Errors

```text
mysql> SELECT * FROM orders WHERE customer_id = 123;
ERROR: Unknown column 'customer_id' in 'where clause' 💡 Ctrl+E: Explain error

# Press Ctrl+E
🤖 Explaining SQL error...

The column `customer_id` doesn't exist in the `orders` table. Possible reasons:
1. The column name might be different (e.g., `customerId`, `cust_id`)
2. The column hasn't been created yet
3. You're querying the wrong table

To fix: Check the table structure with `DESCRIBE orders` or `SHOW CREATE TABLE orders`.
```

### Database Schema Analysis (/research)

Generate comprehensive database analysis reports:

```text
mysql> /research
```

**Analysis includes**:
- Database overview and statistics
- Table structure analysis
- Index optimization suggestions
- Compliance checking (Alibaba Database Development Standards)
- Issue detection (prioritized)
- Actionable optimization recommendations

**Analyze specific tables**:

```text
mysql> /research orders users products
```

**Use cases**:
- Pre-deployment schema review
- Database checks in code review
- Performance audit and optimization
- Migration preparation

### Performance Benchmarking (/benchmark)

Run AI-powered sysbench performance tests:

```text
mysql> /benchmark
```

**Features**:
- Automated workflow (prepare → run → cleanup)
- MySQL configuration analysis
- InnoDB status analysis
- Bottleneck identification
- Optimization recommendations

**Custom test parameters**:

```text
mysql> /benchmark --tables 10 --table-size 10000 --threads 4
```

---

## Advanced Features

### Model Management (/model)

#### View Available Models

```text
mysql> /model list
```

#### Switch Models

```text
mysql> /model use qwen-max
mysql> /model use gpt-4
```

#### View Model Information

```text
mysql> /model info
```

#### Delete Model Configuration

```text
mysql> /model delete old-model
```

### MCP Integration (/mcp)

MCP (Model Context Protocol) allows you to connect external servers to extend functionality.

#### View MCP Servers

```text
mysql> /mcp list
```

#### Connect MCP Server

```text
mysql> /mcp connect rds-openapi
```

#### Enable/Disable Servers

```text
mysql> /mcp enable rds-openapi
mysql> /mcp disable rds-openapi
```

**Supported MCP servers**:
- Alibaba Cloud RDS OpenAPI (cloud RDS instance management)
- Custom MCP servers

### YOLO Mode

YOLO mode automatically approves all operations without confirmation prompts.

**Enable**:

```text
mysql> /yolo on
```

**Disable**:

```text
mysql> /yolo off
```

**Enable at startup**:

```bash
rdsai --host localhost -u root -p secret --yolo
```

⚠️ **Warning**: Use only in non-production environments or when you fully trust the operations!

### Context Management

#### Clear Context

```text
mysql> /clear
```

Clear all AI context and start fresh.

#### Compact Context

```text
mysql> /compact
```

Compact AI context to save tokens while preserving important information.

### Diagnostic Tools

RDSAI CLI includes multiple diagnostic tools accessible via natural language:

#### Table Analysis

```text
mysql> show me the structure of the users table
mysql> analyze indexes on the orders table
mysql> check table status for products
```

#### Query Analysis

```text
mysql> explain this query: SELECT * FROM users WHERE email = 'test@example.com'
mysql> show me slow queries
mysql> check the process list
```

#### Performance Analysis

```text
mysql> show InnoDB status
mysql> check replication status
mysql> analyze performance statistics
```

#### Transactions and Locks

```text
mysql> check for lock waits
mysql> show current transactions
mysql> analyze deadlocks
```

---

## Best Practices

### 1. Workflow Recommendations

#### Daily Query Workflow

1. **Connect to database**
   ```text
   mysql> /connect
   ```

2. **Explore database structure**
   ```text
   mysql> show me all tables
   mysql> describe the users table
   ```

3. **Execute queries**
   ```text
   mysql> SELECT * FROM users WHERE status = 'active' LIMIT 10;
   ```

4. **Understand results**
   - Press `Ctrl+E` for explanation
   - Or use natural language: "why did this query return these results?"

5. **Optimize queries**
   ```text
   mysql> why is this query slow: [your query]
   mysql> suggest indexes for this query: [your query]
   ```

#### Performance Analysis Workflow

1. **Identify slow queries**
   ```text
   mysql> show me slow queries from the last hour
   ```

2. **Analyze query performance**
   ```text
   mysql> explain this slow query: [query]
   ```

3. **Get optimization suggestions**
   ```text
   mysql> how can I optimize this query: [query]
   ```

4. **Verify optimization**
   ```text
   mysql> /benchmark
   ```

#### Schema Review Workflow

1. **Comprehensive analysis**
   ```text
   mysql> /research
   ```

2. **Review issues**
   - Check the issue list in the report
   - Address by priority (P0/P1/P2/P3)

3. **Apply fixes**
   ```text
   mysql> [execute SQL based on recommendations]
   ```

4. **Verify fixes**
   ```text
   mysql> /research [table_name]
   ```

### 2. Security Practices

#### Production Environment

- ❌ **Don't** use YOLO mode
- ✅ **Always** review DDL/DML operations
- ✅ **Use** SSL connections
- ✅ **Limit** database user permissions

#### Credential Management

- Config file permissions: `chmod 600 ~/.rdsai-cli/config.json`
- Use environment variables for sensitive info (future support)
- Regularly rotate API keys

### 3. Performance Optimization

#### Query Optimization

- Use `EXPLAIN` to analyze query plans
- Leverage AI suggestions for slow queries
- Regularly run `/benchmark` for performance testing

#### Context Management

- Regularly use `/compact` to compress context
- Use `/clear` to start fresh after long sessions
- Avoid accumulating too much history in context

### 4. Learning SQL

#### Learning with AI Explanations

```text
mysql> SELECT u.name, COUNT(o.id) as orders 
       FROM users u 
       LEFT JOIN orders o ON u.id = o.user_id 
       GROUP BY u.id;
# Press Ctrl+E to understand this query
```

#### Let AI Generate Queries

```text
mysql> write a query to find users who haven't placed any orders in the last 30 days
mysql> create a query to calculate monthly revenue by product category
```

#### Optimization Learning

```text
mysql> explain why this query is better: [optimized query]
mysql> compare these two queries: [query1] vs [query2]
```

---

## FAQ

### Connection Issues

**Q: What if connection fails?**

```text
# Check connection info
mysql> /help

# Reconnect
mysql> /connect

# View error details
# Error info is shown in welcome panel
```

**Q: SSL connection configuration?**

```bash
rdsai --host db.example.com -u admin -p secret \
  --ssl-mode VERIFY_CA \
  --ssl-ca /path/to/ca.pem
```

### AI Feature Issues

**Q: Ctrl+E not working?**

1. Confirm LLM is configured: `/setup`
2. Confirm active database connection
3. Confirm recent SQL query was executed

**Q: Natural language queries inaccurate?**

- Use more specific descriptions
- Provide table and column names
- Execute complex queries step by step

**Q: How to switch LLM models?**

```text
mysql> /model list
mysql> /model use [model_name]
```

### Performance Issues

**Q: Queries execute slowly?**

```text
# Analyze query
mysql> explain this query: [your query]

# Check slow query log
mysql> show me slow queries

# Check process list
mysql> show process list
```

**Q: AI responses slow?**

- Check network connection
- Try faster models
- Use `/compact` to reduce context size

### Configuration Issues

**Q: Where are config files?**

- LLM config: `~/.rdsai-cli/config.json`
- MCP config: `~/.rdsai-cli/mcp.yaml` (if used)
- Log files: `~/.rdsai-cli/logs/rdsai-cli.log`

**Q: How to reset configuration?**

```bash
# Backup existing config
cp ~/.rdsai-cli/config.json ~/.rdsai-cli/config.json.bak

# Reconfigure
rdsai
mysql> /setup
```

### Feature Issues

**Q: /research command fails?**

- Confirm database connection is normal
- Check if you have sufficient permissions to access information_schema
- View log file for detailed errors

**Q: What does /benchmark need?**

- Requires sysbench installation
- Requires sufficient database permissions
- Recommended to run in test environment

---

## Advanced Tips

### 1. Combining Commands

```text
# Analyze → Optimize → Verify
mysql> /research orders
mysql> [execute optimizations based on suggestions]
mysql> /research orders  # Verify fixes
```

### 2. Leveraging Query History

```text
mysql> /history
# View history, copy and modify queries
```

### 3. Batch Operations

```text
# Analyze multiple tables
mysql> /research table1 table2 table3

# Batch check indexes
mysql> check indexes on all tables
```

### 4. Exporting Results

While current version doesn't directly support export, you can:
- Use `SELECT ... INTO OUTFILE` (requires file permissions)
- Copy query results to clipboard
- Use redirection: `rdsai ... > output.txt`

### 5. Scripted Usage

```bash
# Non-interactive mode (future support)
echo "SELECT COUNT(*) FROM users;" | rdsai --host localhost -u root -p secret
```

---

## Next Steps

- Read [scenario docs](scenarios/) for specific use cases
- Check [feature docs](features/) for in-depth feature details
- Visit [GitHub](https://github.com/aliyun/rdsai-cli) for latest updates
- Submit Issues to report problems or suggest features

---

**Happy coding!** 🚀

For questions, check the documentation or submit an Issue.

