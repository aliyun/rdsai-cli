Query MySQL slow log information from the mysql.slow_log table for performance analysis.

**Parameters:**
- **start_time** (optional): Filter queries from this time onwards (format: 'YYYY-MM-DD HH:MM:SS')
- **end_time** (optional): Filter queries up to this time (format: 'YYYY-MM-DD HH:MM:SS')
- **limit** (optional): Maximum number of rows to return (default: 100, max: 10000)

Shows slow query execution details including timing, user, rows examined/sent, and SQL text.
