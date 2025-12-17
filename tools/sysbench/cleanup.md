Clean up test data created by sysbench. This tool removes test tables and data from the database.

**When to use:**
- After completing performance tests
- Freeing up database space
- Cleaning up test environment
- Before running new tests with different configurations

**Prerequisites:**
- Test data must exist (created by SysbenchPrepare)
- Database connection must be established
- sysbench must be installed and available in PATH

**Parameters:**
- **test_type**: Test type (default: oltp_read_write). Must match the test_type used in SysbenchPrepare.
- **tables**: Number of tables to cleanup (optional). If not specified, cleans up all tables created by sysbench.

**Note:** Cleanup operations are irreversible. All test data will be permanently deleted.

**Best Practice:** Always cleanup test data after benchmarking to free up resources and avoid confusion with production data.

