# 场景：慢查询分析与优化

[English](slow-query-analysis.md) | [中文](slow-query-analysis_zh.md)

本场景演示 RDSAI CLI 如何使用 AI 驱动的分析帮助您识别和优化慢查询。

## 示例

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

## 工作原理

AI 链接多个工具进行完整分析：

1. **SlowLog** — 从 MySQL 慢查询日志中识别慢查询
2. **MySQLExplain** — 分析执行计划以查找瓶颈
3. **TableIndex** — 检查现有索引并建议优化

## 使用场景

- 识别消耗过多资源的查询
- 理解查询缓慢的原因（全表扫描、缺失索引等）
- 获得可操作的建议和预期的性能改进
- 自动生成优化 SQL 语句

## 相关命令

- `/history` — 查看 SQL 查询执行历史
- 自然语言查询，如 "why is this query slow: SELECT ..."
- `EXPLAIN` SQL 命令用于手动分析

