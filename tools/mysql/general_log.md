Query MySQL general log from the **mysql.general_log** system table for SQL audit and analysis.

**What this tool does:**
- Queries the MySQL **audit log** (mysql.general_log) that records all SQL statements executed on the server
- Shows who executed what SQL and when (audit trail)
- This is a **system log table**, NOT a business data table

**When to use:**
- Security auditing and compliance
- Tracking user activity and database access patterns
- Debugging application behavior
- Investigating SQL execution history

**When NOT to use:**
- ❌ **Querying business data tables** (e.g., orders, users, products) 
- ❌ **Getting data from your tables** - Use direct SQL execution: `SELECT * FROM orders WHERE ...`

**Important:** This tool queries the **audit log** (who ran what SQL), NOT your business data. For querying business tables, execute SELECT statements directly in REPL.

**Parameters:**
- **start_time** (optional): Filter log entries from this time onwards (format: 'YYYY-MM-DD HH:MM:SS')
- **end_time** (optional): Filter log entries up to this time (format: 'YYYY-MM-DD HH:MM:SS')
- **user_host** (optional): Filter by user and host pattern (supports % wildcard, e.g., 'root@%')
- **command_type** (optional): Filter by command type (e.g., 'Query', 'Connect', 'Quit', 'Init DB')
- **sql_pattern** (optional): Filter SQL text by pattern (supports % wildcard)
- **limit** (optional): Maximum number of log entries to return (default: 100, max: 10000)

Returns audit log entries showing event_time, user_host, command_type, and the SQL statement (argument) that was executed.
