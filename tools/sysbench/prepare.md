Prepare test data for sysbench performance testing. This tool creates tables and inserts test data into the database.

**When to use:**
- Before running performance tests with SysbenchRun
- Setting up test environment for benchmarking
- Creating test data for load testing

**Prerequisites:**
- Database connection must be established
- sysbench must be installed and available in PATH
- Database user must have CREATE, INSERT, and SELECT privileges

**Parameters:**
- **test_type**: Test type (default: oltp_read_write). Common types:
  - `oltp_read_write`: OLTP read-write workload
  - `oltp_read_only`: OLTP read-only workload
  - `select`: Simple SELECT queries
  - `insert`: INSERT operations
  - `update_index`: UPDATE operations with index
  - `delete`: DELETE operations
- **tables**: Number of tables to create (default: 1, max: 100)
- **table_size**: Number of rows per table (default: 10000, max: 100000000)
- **threads**: Number of threads for data preparation (default: 1, max: 32)

**Note:** Data preparation can take time depending on table_size and tables. Large datasets may require several minutes.

**Example workflow:**
1. Use SysbenchPrepare to create test data
2. Use SysbenchRun to execute performance tests
3. Use SysbenchCleanup to remove test data

