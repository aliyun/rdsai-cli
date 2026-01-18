Execute MySQL SELECT queries for database diagnostics and system table analysis.

**IMPORTANT: This tool ONLY allows queries on system tables. User table queries are NOT permitted to prevent slow queries and performance issues.**

**When to use:**
- Query system tables ONLY: information_schema, performance_schema, sys, mysql
- InnoDB diagnostics: transactions, locks, buffer pool stats, metrics
- Performance analysis: query statistics, wait events, I/O metrics
- Query logs: slow_log, general_log
- Schema metadata: query information_schema for table/index metadata (but NOT user table data)

**DO NOT use for:**
- ❌ Querying user-created tables (e.g., `SELECT * FROM orders`)
- ❌ Querying user data from any database
- ❌ Any queries that may access business data

**Parameters:**
- **select_statement**: The complete SELECT statement to execute. MUST query system tables only (information_schema, performance_schema, sys, mysql). Include FROM, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT, etc.

**Examples:**
- `SELECT * FROM information_schema.INNODB_TRX` - Active transactions
- `SELECT * FROM information_schema.INNODB_LOCKS` - Current locks
- `SELECT * FROM information_schema.INNODB_BUFFER_POOL_STATS` - Buffer pool statistics
- `SELECT * FROM performance_schema.events_statements_summary_by_digest ORDER BY sum_timer_wait DESC LIMIT 10`
- `SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 100`
- `SELECT * FROM information_schema.TABLES WHERE table_schema='mydb'` - Table metadata (NOT table data)
- `SELECT * FROM sys.schema_table_statistics WHERE table_schema='mydb'` - Statistics (NOT table data)

**Note:** Only SELECT queries on system tables allowed. User table queries are blocked to prevent slow queries. Use MySQLShow for SHOW statements, MySQLDesc for DESCRIBE statements, and DDLExecutor for DDL operations.
