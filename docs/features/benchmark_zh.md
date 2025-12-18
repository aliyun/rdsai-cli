# Sysbench 性能基准测试 (`/benchmark`)

[English](benchmark.md) | [中文](benchmark_zh.md)

`/benchmark` 命令使用 sysbench 运行全面的数据库性能测试，并提供 AI 驱动的分析和优化建议。

## 功能说明

基准测试工作流程执行完整的性能测试周期：

1. **准备阶段** — 创建测试数据（表和行）用于基准测试
2. **运行阶段** — 使用指定的工作负载和并发数执行性能测试
3. **分析阶段** — 收集 MySQL 配置、InnoDB 状态和进程信息
4. **清理阶段** — 删除测试数据（除非指定 `--no-cleanup`）

基准测试完成后，会生成全面的分析报告，包括：
- **性能指标** — TPS（每秒事务数）、QPS（每秒查询数）、延迟统计
- **MySQL 配置分析** — 基于基准测试结果的参数优化建议
- **InnoDB 状态分析** — 缓冲池命中率、锁等待、事务分析
- **瓶颈识别** — CPU 瓶颈、I/O 瓶颈、内存瓶颈、锁竞争分析
- **优化建议** — 按优先级（P0/P1/P2/P3）分类的可操作建议，包含预期影响

## 前置要求

- **必须安装 sysbench** — 从 [sysbench GitHub](https://github.com/akopytov/sysbench) 安装
- **数据库必须存在** — 运行基准测试前创建目标数据库（例如：`CREATE DATABASE testdb;`）
- **已配置 LLM** — 使用 `/setup` 配置 LLM 模型

## 使用方法

```text
# 让代理智能选择测试参数
mysql> /benchmark run

# 快速测试：100 线程，60 秒
mysql> /benchmark --threads=100 --time=60

# 只读工作负载测试
mysql> /benchmark oltp_read_only -t 50 -T 120

# 大数据集测试：10 张表，每张 100 万行
mysql> /benchmark --tables=10 --table-size=1000000

# 自定义测试，包含所有参数
mysql> /benchmark oltp_read_write --threads=200 --time=300 --tables=5 --table-size=500000

# 基准测试后保留测试数据
mysql> /benchmark --no-cleanup

# 显示帮助
mysql> /benchmark --help
```

## 测试类型

- `oltp_read_write` — OLTP 读写工作负载（默认）
- `oltp_read_only` — OLTP 只读工作负载
- `select` — 简单 SELECT 查询
- `insert` — INSERT 操作
- `update_index` — 带索引的 UPDATE 操作
- `delete` — DELETE 操作

## 选项

| 选项                  | 简写 | 描述                                    | 默认值 |
| --------------------- | ---- | --------------------------------------- | ------ |
| `--threads`, `-t`     | `-t` | 并发线程数                              | 1      |
| `--time`, `-T`        | `-T` | 测试持续时间（秒）                      | 60     |
| `--events`, `-e`      | `-e` | 事件总数（替代 --time）                 |        |
| `--tables`            |      | 表数量                                  | 1      |
| `--table-size`        |      | 每张表的行数                            | 10000  |
| `--rate`              |      | 目标每秒事务数（速率限制）              |        |
| `--report-interval`   |      | 报告间隔（秒）                          | 10     |
| `--no-cleanup`        |      | 测试后不清理测试数据                    | false  |
| `--help`, `-h`        | `-h` | 显示帮助信息                            |        |

## 使用场景

- **性能基线** — 在优化前建立性能基线
- **配置调优** — 测试 MySQL 参数更改的影响
- **容量规划** — 了解不同工作负载下的数据库容量
- **优化验证** — 验证优化后的性能改进
- **负载测试** — 测试高并发下的数据库行为
- **瓶颈分析** — 识别 CPU、I/O、内存或锁竞争问题

## 报告结构

基准测试分析报告包括：

1. **基准测试摘要** — 测试配置、TPS/QPS/延迟指标
2. **MySQL 配置分析** — 参数分析和优化建议
3. **InnoDB 状态分析** — 缓冲池指标、锁等待、事务分析
4. **性能瓶颈识别** — 主要瓶颈及证据和影响
5. **优化建议** — 按优先级分类的建议，包含预期影响和风险评估

## 示例输出

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

