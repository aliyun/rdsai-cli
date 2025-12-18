# 场景：性能基准测试与优化

[English](performance-benchmarking.md) | [中文](performance-benchmarking_zh.md)

本场景演示如何使用 `/benchmark` 命令运行全面的性能测试并获得 AI 驱动的优化建议。

## 示例

```text
mysql> CREATE DATABASE benchmark_test;
Query OK, 1 row affected (0.01 sec)

mysql> USE benchmark_test;
Database changed

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

## 使用场景

- **性能基线** — 在优化前建立性能基线
- **配置调优** — 测试 MySQL 参数更改的影响
- **容量规划** — 了解不同工作负载下的数据库容量
- **优化验证** — 验证优化后的性能改进
- **负载测试** — 测试高并发下的数据库行为
- **瓶颈分析** — 识别 CPU、I/O、内存或锁竞争问题

## 您将获得

使用 `/benchmark`，您可以：
- **运行自动化基准测试** — 从数据准备到清理的完整工作流程
- **获得 AI 驱动的分析** — 包含瓶颈识别的全面报告
- **接收优化建议** — 按优先级分类的建议，包含预期影响
- **验证改进** — 重新运行基准测试以验证优化结果

## 相关文档

详细文档请参阅 [Sysbench 性能基准测试 (`/benchmark`)](../features/benchmark_zh.md)。

