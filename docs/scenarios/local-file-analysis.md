# Scenario: Local File Connection & Analysis

[English](local-file-analysis.md) | [中文](local-file-analysis_zh.md)

This scenario demonstrates how to connect to local files (CSV, Parquet, JSON, Excel) and perform data analysis using native SQL queries. You can also use natural language queries for convenience, though SQL remains the primary and most powerful way to interact with your data.

## Example

### Connecting to a Local CSV File

```text
$ rdsai
> /connect sales.csv

Loading data from file...
✓ Connected to sales.csv
✓ Loaded sales.csv → table 'sales' (15234 rows, 8 columns)
```

### Querying Data with SQL

Once connected, you can query the data using native SQL:

```text
> SELECT * FROM sales LIMIT 10

+------------+------------+----------+--------+----------+------------+--------+-------+
| order_id   | date       | product  | amount | quantity | customer_id| region | status|
+------------+------------+----------+--------+----------+------------+--------+-------+
| ORD-001    | 2024-01-15 | Widget A | 99.99  |    2     | CUST-123   | North  | paid  |
| ORD-002    | 2024-01-15 | Widget B | 149.50 |    1     | CUST-456   | South  | paid  |
...
+------------+------------+----------+--------+----------+------------+--------+-------+
(10 rows in 0.012 sec) 💡 Ctrl+E: Explain result
```

### Advanced SQL Queries

You can write complex SQL queries for analysis:

```text
> SELECT product, SUM(amount) as total_sales 
  FROM sales 
  WHERE status = 'paid'
  GROUP BY product 
  ORDER BY total_sales DESC 
  LIMIT 5

+----------+-------------+
| product  | total_sales |
+----------+-------------+
| Widget A |   125000.50 |
| Widget B |    98000.25 |
| Widget C |    75000.00 |
| Widget D |    62000.75 |
| Widget E |    45000.50 |
+----------+-------------+
(5 rows in 0.045 sec)
```

### Connecting Multiple Files

You can connect multiple files for cross-file analysis:

```text
> /connect customers.csv orders.csv products.csv

Loading data from 3 files...
✓ Connected to customers.csv, orders.csv, products.csv
✓ Loaded customers.csv → table 'customers' (5000 rows, 6 columns)
✓ Loaded orders.csv → table 'orders' (15234 rows, 8 columns)
✓ Loaded products.csv → table 'products' (150 rows, 5 columns)
```

### Cross-File Analysis

```text
> SELECT 
    c.customer_id,
    c.name,
    COUNT(o.order_id) as order_count,
    SUM(o.amount) as lifetime_value
  FROM customers c
  LEFT JOIN orders o ON c.customer_id = o.customer_id
  GROUP BY c.customer_id, c.name
  ORDER BY lifetime_value DESC
  LIMIT 10

+------------+------------------+-------------+----------------+
| customer_id| name             | order_count | lifetime_value |
+------------+------------------+-------------+----------------+
| CUST-123   | John Smith       |     45      |   12500.50     |
| CUST-456   | Jane Doe         |     38      |   11200.25     |
...
+------------+------------------+-------------+----------------+
(10 rows in 0.089 sec)
```

### Natural Language Queries

In addition to SQL, you can also use natural language queries for convenience. The system will translate your questions into SQL:

```text
> what are the top 5 products by total sales?

🔧 Executing SQL: 
SELECT product, SUM(amount) as total_sales 
FROM sales 
WHERE status = 'paid'
GROUP BY product 
ORDER BY total_sales DESC 
LIMIT 5

+----------+-------------+
| product  | total_sales |
+----------+-------------+
| Widget A |   125000.50 |
| Widget B |    98000.25 |
| Widget C |    75000.00 |
| Widget D |    62000.75 |
| Widget E |    45000.50 |
+----------+-------------+
(5 rows in 0.045 sec)
```

> Note: While natural language queries are supported, writing SQL directly gives you more control and precision for complex analysis.

## Supported File Formats

- **CSV files** (`.csv`) — Comma-separated values
- **Excel files** (`.xlsx`) — Excel 2007+ format

## Connection Methods

### Local Files

```text
# Bare filename (searches in current directory)
> /connect data.csv

# Absolute path
> /connect /path/to/data.csv

# Relative path
> /connect ./data/data.csv

# Using file:// protocol
> /connect file:///path/to/data.csv
```

### Remote Files

```text
# HTTP
> /connect http://example.com/data.csv

# HTTPS
> /connect https://example.com/data.csv
```

### Multiple Files

```text
# Connect multiple files at once
> /connect file1.csv file2.csv file3.xlsx
```

## Use Cases

- **Data Exploration** — Quickly explore CSV/Excel files without importing into a database
- **Ad-hoc Analysis** — Perform one-off analysis on data files
- **Report Generation** — Generate insights and reports from data files
- **Data Validation** — Check data quality and identify issues
- **Cross-File Analysis** — Join and analyze data from multiple files
- **Quick Prototyping** — Test analysis workflows before database import
- **Data Migration** — Analyze source data before migrating to database

## How It Works

1. **Connect** — Use `/connect` with file path(s) to load data
2. **Auto-Load** — Files are automatically loaded into DuckDB tables
3. **Query** — Use native SQL queries to analyze the data (primary method)
4. **Natural Language** — Optionally use natural language queries for convenience

The system:
- Automatically detects file format (CSV, Parquet, JSON, Excel)
- Creates tables with appropriate column types
- Supports standard SQL queries (SELECT, JOIN, GROUP BY, etc.)
- Can translate natural language questions into SQL queries

## Related Commands

- `/connect` — Connect to files or databases
- `/disconnect` — Disconnect from current data source
- `/help` — View all available commands
- SQL queries — Write native SQL to query your data (recommended)
- Natural language queries — Ask questions in plain English (optional)
- `Ctrl+E` — Explain query results instantly

## Best Practices

- **File Location** — Keep data files in an accessible location or use absolute paths
- **File Size** — Large files (>100MB) may take longer to load
- **Data Types** — Column types are auto-detected; verify if needed
- **Multiple Files** — Use descriptive filenames when connecting multiple files
- **Analysis** — Start with simple queries, then build up to complex analysis

## Tips

- File tables are named based on the filename (e.g., `sales.csv` → `sales` table)
- Use `SHOW TABLES` to see all loaded tables
- Use `DESCRIBE table_name` to see table structure
- Write SQL queries directly to explore and analyze your data (recommended for best control)
- You can also use natural language queries for quick exploration
- Press `Ctrl+E` after queries to get explanations
- Disconnect and reconnect to reload files if data changes

## Limitations

- Files are loaded into memory (in-memory database)
- Very large files (>1GB) may require significant memory
- File modifications require reconnection to reload
- Some Excel features (formulas, macros) are not supported
