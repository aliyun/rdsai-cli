Get performance information from performance_schema database.

**Parameters:**
- **info_type** (optional): Type of performance data to retrieve
  - `'tables'` (default): List all performance_schema tables
  - `'statements'`: Statement execution summaries
  - `'waits'`: Wait event summaries
  - `'table_io'`: Table I/O wait statistics
  - `'table_lock'`: Table lock wait statistics
  - `'threads'`: Thread information
  - `'users'`: User-level statistics
  - `'accounts'`: Account-level statistics
  - `'hosts'`: Host-level statistics
  - `'memory'`: Memory usage summaries
- **table** (optional): Table name for table_io/table_lock, or memory dimension
