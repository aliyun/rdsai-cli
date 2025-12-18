# Scenario: Slow Query Analysis & Optimization

[English](slow-query-analysis.md) | [中文](slow-query-analysis_zh.md)

This scenario demonstrates how RDSAI CLI helps you identify and optimize slow queries using AI-powered analysis.

## Example

```text
mysql> show me slow queries from the last hour and analyze them

🔧 Calling tool: SlowLog
📊 Found 3 slow queries. Slowest: SELECT * FROM orders WHERE status = 'pending' (12.34s)

🔧 Calling tool: MySQLExplain
⚠️ Problem: Full table scan on `orders` (1.5M rows), no index on `status`

💡 Recommendation: CREATE INDEX idx_orders_status ON orders(status);
   Expected: Query time drops from ~12s to <100ms

Would you like me to create this index? [y/N]
```

## How It Works

The AI chains multiple tools for complete analysis:

1. **SlowLog** — Identifies slow queries from MySQL slow query log
2. **MySQLExplain** — Analyzes execution plan to find bottlenecks
3. **TableIndex** — Checks existing indexes and suggests optimizations

## Use Cases

- Identify queries that are consuming excessive resources
- Understand why queries are slow (full table scans, missing indexes, etc.)
- Get actionable recommendations with expected performance improvements
- Automatically generate optimization SQL statements

## Related Commands

- `/history` — View SQL query execution history
- Natural language queries like "why is this query slow: SELECT ..."
- `EXPLAIN` SQL command for manual analysis

