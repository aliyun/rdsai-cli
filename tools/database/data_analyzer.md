Execute analytical SQL SELECT queries on MySQL or DuckDB databases for data analysis, exploration, and statistical insights.

**Primary Use:**
This tool is designed for data analysis queries that explore patterns, calculate statistics, perform aggregations, and generate insights from data. Use it for analytical queries that help understand data characteristics, trends, and relationships.

**Supported:**
- SELECT queries (including WITH/CTE, JOINs, aggregations, window functions, GROUP BY, ORDER BY)
- Statistical analysis: COUNT, SUM, AVG, MIN, MAX, STDDEV, etc.
- Data exploration: filtering, sorting, grouping, pivoting
- Both MySQL and DuckDB engines (check `<database_context>` for current engine and use appropriate SQL syntax)

**When to use:**
- Data analysis and exploration queries
- Statistical calculations and aggregations
- Trend analysis and pattern discovery
- Data profiling and summary statistics
- Cross-table analysis with JOINs
- Complex analytical queries with CTEs and window functions

**NOT Supported - DO NOT USE FOR:**
- DML (INSERT, UPDATE, DELETE) or DDL (CREATE, ALTER, DROP) - Use DDLExecutor for MySQL DDL
- EXPLAIN - Use MySQLExplain tool instead
- SHOW statements - Use MySQLShow tool instead
- DESCRIBE statements - Use MySQLDesc tool instead
- System table queries for diagnostics - Use MySQLSelect tool instead

**Parameters:**
- **sql**: SQL SELECT query to execute for data analysis. **CRITICAL**: MUST check `<database_context>` for the current database engine (MySQL or DuckDB) and generate SQL using the correct syntax for that engine. Do NOT mix syntax from different engines. Focus on analytical queries that provide insights, statistics, or data exploration.

**Examples:**
- `SELECT COUNT(*) as total, AVG(price) as avg_price FROM products WHERE category='electronics'`
- `SELECT category, SUM(sales) as total_sales FROM orders GROUP BY category ORDER BY total_sales DESC`
- `SELECT customer_id, COUNT(*) as order_count, SUM(amount) as total_spent FROM orders GROUP BY customer_id HAVING order_count > 5`
- `WITH monthly_sales AS (SELECT DATE_FORMAT(order_date, '%Y-%m') as month, SUM(amount) as sales FROM orders GROUP BY month) SELECT * FROM monthly_sales ORDER BY month`

Returns query results as structured data (columns and rows) with execution time. Large result sets are truncated for display.
