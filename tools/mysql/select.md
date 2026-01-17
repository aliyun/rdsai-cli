Execute MySQL SELECT queries for database diagnostics and system table analysis.

**When to use:**
- Query system tables: information_schema, performance_schema, sys, mysql
- InnoDB diagnostics: transactions, locks, buffer pool stats, metrics
- Performance analysis: query statistics, wait events, I/O metrics
- Query logs: slow_log, general_log
- User tables: any SELECT queries

**Parameters:**
- **select_statement**: The complete SELECT statement to execute. Include FROM, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT, etc.

**Examples:**
- `SELECT * FROM information_schema.INNODB_TRX` - Active transactions
- `SELECT * FROM information_schema.INNODB_LOCKS` - Current locks
- `SELECT * FROM information_schema.INNODB_BUFFER_POOL_STATS` - Buffer pool statistics
- `SELECT * FROM performance_schema.events_statements_summary_by_digest ORDER BY sum_timer_wait DESC LIMIT 10`
- `SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 100`
- `SELECT * FROM information_schema.TABLES WHERE table_schema='mydb'`
- `SELECT * FROM sys.schema_table_statistics WHERE table_schema='mydb'`

**Note:** Only SELECT queries allowed. Use MySQLShow for SHOW statements, MySQLDesc for DESCRIBE statements, and DDLExecutor for DDL operations.
