Execute MySQL DESCRIBE/DESC statements for viewing table structure and column information.

**When to use:**
- Viewing table column structure: `DESCRIBE table_name`, `DESC table_name`
- Getting CREATE TABLE statement: `SHOW CREATE TABLE table_name`
- Viewing column details: `SHOW COLUMNS FROM table_name`

**Parameters:**
- **desc_statement**: The complete DESCRIBE, DESC, or SHOW CREATE TABLE/SHOW COLUMNS statement to execute. The model should construct the full statement including the table name.

**Examples:**
- `DESCRIBE users`
- `DESC orders`
- `SHOW CREATE TABLE products`
- `SHOW COLUMNS FROM customers`

**Note:** This tool only accepts DESCRIBE/DESC/SHOW CREATE TABLE/SHOW COLUMNS statements. Use MySQLSelect for SELECT queries and DDLExecutor for DDL operations.
