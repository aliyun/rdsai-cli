# MySQL DDL Executor

Execute DDL (Data Definition Language) operations on MySQL databases with user approval.

**Parameters:**
- **sql_statement**: The DDL SQL statement to execute
- **description**: A human-readable description of what the modification will do

**Supported Operations (DDL ONLY):**
- CREATE INDEX / CREATE UNIQUE INDEX
- DROP INDEX
- CREATE TABLE / DROP TABLE
- ALTER TABLE (add/drop columns, constraints, modify columns, etc.)
- CREATE VIEW / DROP VIEW
- CREATE PROCEDURE / DROP PROCEDURE
- CREATE FUNCTION / DROP FUNCTION
- CREATE TRIGGER / DROP TRIGGER

**NOT Supported - DO NOT USE THIS TOOL FOR:**
- ❌ **SELECT queries** - These should be executed directly in the REPL, not through this tool
- ❌ **INSERT, UPDATE, DELETE** - These are DML operations, not DDL
- ❌ **SHOW statements** - Use dedicated tools like TableStructure, TableIndex, etc.
- ❌ **DROP DATABASE, CREATE DATABASE** - Blocked for safety
- ❌ **Any query that reads data** - This tool is ONLY for schema modifications

**When to Use:**
- When you need to modify database schema (add indexes, alter tables, etc.)
- When creating or dropping database objects (tables, views, procedures, etc.)

**When NOT to Use:**
- For reading data - use dedicated analysis tools (TableStructure, TableIndex, etc.)
- For DML operations (INSERT/UPDATE/DELETE) - not supported by this tool

**Safety Features:**
- User approval required for all modifications
- DDL operations only (no DML: INSERT/UPDATE/DELETE)
- Blocks dangerous operations like DROP DATABASE
- Validates SQL statement type before execution

**IMPORTANT: Execute ONE DDL operation at a time.** If you need to perform multiple DDL changes, call this tool once, wait for the result, then decide whether to proceed with the next operation. Do NOT batch multiple DDL calls in a single response.
