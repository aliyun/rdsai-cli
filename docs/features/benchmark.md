# Sysbench Performance Benchmarking (`/benchmark`)

[English](benchmark.md) | [中文](benchmark_zh.md)

The `/benchmark` command runs comprehensive database performance tests using sysbench, with AI-powered analysis and optimization recommendations.

## What It Does

The benchmark workflow executes a complete performance testing cycle:

1. **Prepare Phase** — Creates test data (tables and rows) for benchmarking
2. **Run Phase** — Executes performance tests with specified workload and concurrency
3. **Analysis Phase** — Collects MySQL configuration, InnoDB status, and process information
4. **Cleanup Phase** — Removes test data (unless `--no-cleanup` is specified)

After benchmark completion, a comprehensive analysis report is generated including:
- **Performance Metrics** — TPS (Transactions Per Second), QPS (Queries Per Second), latency statistics
- **MySQL Configuration Analysis** — Parameter optimization recommendations based on benchmark results
- **InnoDB Status Analysis** — Buffer pool hit rate, lock waits, transaction analysis
- **Bottleneck Identification** — CPU-bound, I/O-bound, memory-bound, lock contention analysis
- **Optimization Recommendations** — Prioritized (P0/P1/P2/P3) actionable recommendations with expected impact

## Prerequisites

- **sysbench must be installed** — Install from [sysbench GitHub](https://github.com/akopytov/sysbench)
- **Database must exist** — Create the target database before running benchmarks (e.g., `CREATE DATABASE testdb;`)
- **LLM configured** — Use `/setup` to configure an LLM model

## Usage

```text
# Let agent intelligently choose test parameters
mysql> /benchmark run

# Quick test with 100 threads for 60 seconds
mysql> /benchmark --threads=100 --time=60

# Read-only workload test
mysql> /benchmark oltp_read_only -t 50 -T 120

# Large dataset test with 10 tables, 1M rows each
mysql> /benchmark --tables=10 --table-size=1000000

# Custom test with all parameters
mysql> /benchmark oltp_read_write --threads=200 --time=300 --tables=5 --table-size=500000

# Keep test data after benchmark
mysql> /benchmark --no-cleanup

# Show help
mysql> /benchmark --help
```

## Test Types

- `oltp_read_write` — OLTP read-write workload (default)
- `oltp_read_only` — OLTP read-only workload
- `select` — Simple SELECT queries
- `insert` — INSERT operations
- `update_index` — UPDATE operations with index
- `delete` — DELETE operations

## Options

| Option                  | Short | Description                                    | Default |
| ----------------------- | ----- | ---------------------------------------------- | ------- |
| `--threads`, `-t`       | `-t`  | Number of concurrent threads                   | 1       |
| `--time`, `-T`          | `-T`  | Test duration in seconds                       | 60      |
| `--events`, `-e`        | `-e`  | Total number of events (alternative to --time) |         |
| `--tables`              |       | Number of tables                               | 1       |
| `--table-size`          |       | Number of rows per table                       | 10000   |
| `--rate`                |       | Target transactions per second (rate limiting) |         |
| `--report-interval`     |       | Report interval in seconds                     | 10      |
| `--no-cleanup`          |       | Don't cleanup test data after test            | false   |
| `--help`, `-h`          | `-h`  | Show help message                              |         |

## Use Cases

- **Performance Baseline** — Establish performance baseline before optimization
- **Configuration Tuning** — Test impact of MySQL parameter changes
- **Capacity Planning** — Understand database capacity under different workloads
- **Optimization Validation** — Verify performance improvements after optimizations
- **Load Testing** — Test database behavior under high concurrency
- **Bottleneck Analysis** — Identify CPU, I/O, memory, or lock contention issues

## Report Structure

The benchmark analysis report includes:

1. **Benchmark Summary** — Test configuration, TPS/QPS/latency metrics
2. **MySQL Configuration Analysis** — Parameter analysis with optimization recommendations
3. **InnoDB Status Analysis** — Buffer pool metrics, lock waits, transaction analysis
4. **Performance Bottleneck Identification** — Primary bottleneck with evidence and impact
5. **Optimization Recommendations** — Prioritized recommendations with expected impact and risk assessment

## Example Output

```text
mysql> /benchmark run

Benchmark Configuration:
  Database: benchmark_test
  Mode: Agent will intelligently choose parameters

⚠ Warning: This benchmark will put significant load on the database.
Target database: benchmark_test
Make sure this is appropriate for your environment.

Do you want to proceed with the benchmark on database 'benchmark_test'?
> Yes, start benchmark

Starting benchmark...
The agent will intelligently configure the test and generate analysis report.

🔧 Preparing test data with 1 table, 100,000 rows each...
✓ Successfully prepared 1 table(s) with 100,000 rows each (total: 100,000 rows)

🔧 Executing benchmark with 50 threads for 60 seconds...
Performance test completed for 60 seconds with 50 thread(s) - TPS: 1250.45, QPS: 25009.00, Avg Latency: 39.95ms

🔧 Collecting MySQL configuration and InnoDB status for analysis...

📊 Benchmark Analysis Report

## Benchmark Summary

**Test Configuration:**
- Test Type: oltp_read_write
- Threads: 50
- Duration: 60 seconds
- Tables: 1
- Table Size: 100,000 rows

**Performance Metrics:**
- TPS: 1,250.45 transactions/sec
- QPS: 25,009.00 queries/sec
- Average Latency: 39.95ms

## MySQL Configuration Analysis

### Critical Issues Found:

🔴 **P0 - Buffer Pool Too Small**
- **Current**: innodb_buffer_pool_size = 128MB
- **Impact**: Buffer pool hit rate: 87% (< 99% target)
- **Root Cause**: Buffer pool is too small for workload, causing frequent disk I/O
- **Recommendation**: Increase to 2GB (70% of available RAM)
- **Expected Impact**: TPS improvement from 1,250 to 1,600-1,800 (28-44% improvement)
- **Risk**: Low (can be changed dynamically)
- **SQL**: `SET GLOBAL innodb_buffer_pool_size = 2147483648;`

🟡 **P1 - InnoDB Log File Size Too Small**
- **Current**: innodb_log_file_size = 48MB
- **Impact**: High log write activity, potential write bottleneck
- **Expected Impact**: 10-15% TPS improvement for write-heavy workloads
- **Risk**: Medium (requires MySQL restart)

## InnoDB Status Analysis

**Buffer Pool Metrics:**
- Hit Rate: 87% ⚠️ (Target: > 99%)
- Pages Read: 15,234 (indicates frequent disk reads)
- Pages Written: 8,912

**Lock Analysis:**
- Lock Waits: 0 ✓
- Deadlocks: 0 ✓
- Active Transactions: 12

## Performance Bottleneck Identification

**Primary Bottleneck: I/O-bound**

**Evidence:**
- Buffer pool hit rate: 87% (< 99% target)
- High pages read: 15,234 during test
- Average latency: 39.95ms (higher than expected)

**Impact:** Estimated 30-40% TPS improvement if buffer pool is increased

**Priority:** P0 (Critical)

## Optimization Recommendations

### [P0] Increase InnoDB Buffer Pool Size
**Issue**: Buffer pool too small, causing frequent disk I/O
**Evidence**: Buffer pool hit rate 87%, TPS: 1,250
**Action**: Increase innodb_buffer_pool_size to 2GB
**Expected Impact**: TPS improvement from 1,250 to 1,600-1,800 (28-44%)
**Risk**: Low
**Verification**: Re-run benchmark and compare TPS

### [P1] Optimize InnoDB Log File Size
**Issue**: Log file size too small for write workload
**Evidence**: High log write activity during benchmark
**Action**: Increase innodb_log_file_size to 256MB (requires restart)
**Expected Impact**: 10-15% TPS improvement
**Risk**: Medium

✓ Successfully cleaned up all tables
✓ Benchmark completed.
```

