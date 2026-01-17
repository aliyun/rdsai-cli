Execute analytical SQL SELECT queries on MySQL or DuckDB databases for data analysis, exploration, and statistical queries.

**Supported:**
- SELECT queries (including WITH/CTE, JOINs, aggregations, window functions)
- Both MySQL and DuckDB engines (automatically detects engine)

**NOT Supported - DO NOT USE FOR:**
- DML (INSERT, UPDATE, DELETE) or DDL (CREATE, ALTER, DROP) - Use DDLExecutor for MySQL DDL
- EXPLAIN - Use MySQLExplain tool instead
- SHOW statements - Use dedicated MySQL tools or execute directly in REPL

**Parameters:**
- **sql**: SQL SELECT query to execute. Generate SQL appropriate for the connected database engine (check <database_context> for current engine).

Returns query results as structured data (columns and rows) with execution time. Large result sets are truncated for display.
