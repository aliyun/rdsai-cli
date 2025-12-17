Analyze SQL query execution plan using MySQL EXPLAIN. **ONLY supports DML statements: SELECT, INSERT, UPDATE, DELETE.**

**When to use:**
- Analyze slow SELECT queries to understand index usage and join order
- Check execution plan before running INSERT/UPDATE/DELETE on large tables
- Performance tuning and query optimization
- Debugging query performance issues

**Supported SQL Types (DML ONLY):**
- ✅ **SELECT** - Query execution plans
- ✅ **INSERT** - Insert operation plans
- ✅ **UPDATE** - Update operation plans
- ✅ **DELETE** - Delete operation plans

**NOT Supported - DO NOT USE THIS TOOL FOR:**
- ❌ **SHOW statements** - These are MySQL administrative commands, NOT DML. Use dedicated tools (TableStatus, TableStructure, TableIndex, etc.) or execute directly in REPL
- ❌ **DDL statements** (CREATE, ALTER, DROP, etc.) - Use **DDLExecutor** tool instead
- ❌ **SET commands** - Execute directly in REPL
- ❌ **USE database** - Execute directly in REPL
- ❌ **Any non-DML statement** - This tool ONLY works with DML (SELECT/INSERT/UPDATE/DELETE)

**Important:** EXPLAIN only works with DML statements that access/modify table data. SHOW statements are administrative commands and cannot be analyzed with EXPLAIN.

**Parameters:**
- **sql**: The SQL DML statement to analyze (must be SELECT, INSERT, UPDATE, or DELETE only)

Returns execution plan showing tables accessed, indexes used, join order, and estimated row counts.
