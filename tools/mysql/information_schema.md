Get database metadata from information_schema for analysis and monitoring.

**Parameters:**
- **info_type** (optional): Type of information to retrieve
  - `'tables'` (default): List all information_schema tables
  - `'index'`: Index statistics for a specific table (requires table parameter)
  - `'buffer_pool'`: InnoDB buffer pool statistics
  - `'tablespace'`: Table information from TABLES view
- **table** (optional): Table name (required when info_type='index')
