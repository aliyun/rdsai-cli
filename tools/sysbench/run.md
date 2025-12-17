Execute sysbench performance tests. This tool runs the actual benchmark and collects performance metrics.

**When to use:**
- After preparing test data with SysbenchPrepare
- Performance benchmarking and load testing
- Comparing performance under different configurations
- Stress testing database systems

**Prerequisites:**
- Test data must be prepared using SysbenchPrepare
- Database connection must be established
- sysbench must be installed and available in PATH

**Parameters:**
- **test_type**: Test type (default: oltp_read_write). Must match the test_type used in SysbenchPrepare.
- **threads**: Number of concurrent threads (default: 1, max: 1000)
- **time**: Test duration in seconds (default: 60 if not specified, max: 3600). Either time or events must be specified.
- **events**: Total number of events to execute (alternative to time). Either time or events must be specified.
- **rate**: Target transactions per second for rate limiting (optional)
- **report_interval**: Report interval in seconds (default: 10, max: 300)
- **tables**: Number of tables to use (default: 1, max: 100). Must match or be less than tables prepared.
- **table_size**: Table size in rows (optional). If not specified, uses existing tables from prepare.

**Performance Metrics:**
The tool reports:
- **TPS**: Transactions per second
- **QPS**: Queries per second
- **Latency**: Average latency in milliseconds

**Important:**
- Running performance tests can put significant load on the database
- Use appropriate thread counts and durations
- Monitor database resources during testing
- Consider running during maintenance windows for production systems

