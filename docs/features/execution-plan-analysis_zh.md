# 执行计划分析 (`/explain`)

[English](execution-plan-analysis.md) | [中文](execution-plan-analysis_zh.md)

`/explain` 命令提供 AI 驱动的 SQL 执行计划分析。它会对您的 SQL 查询执行 `EXPLAIN`，并使用 AI 分析执行计划、识别性能问题并提供具体的优化建议。

## 分析内容

- **关键指标** — 索引使用情况、扫描类型、预估扫描行数、连接顺序和类型
- **性能问题** — 全表扫描、缺失索引使用、大量行扫描、低效连接
- **优化建议** — 具体的索引推荐、查询重写建议、连接优化策略

## 使用方法

```text
# 分析简单查询
mysql> /explain SELECT * FROM users WHERE email = 'test@example.com'

# 分析带连接的复杂查询
mysql> /explain SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id

# 分析带子查询的查询
mysql> /explain SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE status = 'active')
```

## 使用场景

### 性能故障排除

分析慢查询以在优化前识别瓶颈：

```text
mysql> /explain SELECT * FROM orders WHERE customer_id = 123 AND status = 'pending'
```

AI 将分析：
- 索引是否被高效使用
- 扫描类型（全表扫描 vs 索引扫描）
- 预估扫描行数
- 潜在性能瓶颈

### 索引优化

检查查询是否高效使用索引并识别缺失的索引：

```text
mysql> /explain SELECT * FROM products WHERE name LIKE '%laptop%'
```

AI 将识别：
- 可以通过适当索引避免的全表扫描
- 可以提高性能的缺失索引
- 索引使用效率

### 查询优化

获取重写查询以提高性能的建议：

```text
mysql> /explain SELECT u.*, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE u.status = 'active'
```

AI 将建议：
- 更好的连接策略
- 查询重写技术
- 索引推荐

### 连接分析

理解多表查询的连接顺序和类型：

```text
mysql> /explain SELECT u.name, o.total, p.name 
       FROM users u 
       JOIN orders o ON u.id = o.user_id 
       JOIN products p ON o.product_id = p.id
```

AI 将分析：
- 连接顺序优化
- 连接类型（INNER、LEFT 等）效率
- 连接算法推荐

### 全表扫描检测

识别不必要扫描整个表的查询：

```text
mysql> /explain SELECT * FROM logs WHERE created_at > '2024-01-01'
```

AI 将检测：
- 全表扫描（type: ALL）
- WHERE 子句列上缺失的索引
- 添加适当索引的建议

### 部署前审查

在部署前审查生产查询的执行计划：

```text
mysql> /explain SELECT COUNT(*) FROM orders WHERE status = 'completed' AND created_at BETWEEN '2024-01-01' AND '2024-12-31'
```

AI 将帮助确保：
- 查询在上线前已优化
- 适当的索引已就位
- 没有意外的全表扫描


## 分析输出

AI 提供详细分析，包括：

- **索引使用分析**：使用了哪些索引，缺失哪些索引
- **扫描类型分析**：ALL（全表扫描）、index、range、ref 等
- **行数估算**：预估扫描的行数
- **连接分析**：连接顺序、连接类型、连接算法
- **额外信息**：Using index、Using where、Using filesort 等
- **性能问题**：发现的问题优先级列表
- **优化建议**：具体的 SQL 推荐

## 要求

- **数据库连接** — 需要通过 `/connect` 建立活动数据库连接
- **LLM 配置** — 需要通过 `/setup` 配置 LLM
- **有效 SQL** — SQL 语句必须有效且可执行

## 示例

### 示例 1：简单查询分析

```text
mysql> /explain SELECT * FROM users WHERE id = 100

Analyzing execution plan...

执行计划显示：
- 索引使用：使用了 PRIMARY 键（良好）
- 扫描类型：const（非常高效）
- 预估行数：1
- 性能：优秀 - 直接索引查找

此查询无需优化。
```

### 示例 2：缺失索引检测

```text
mysql> /explain SELECT * FROM orders WHERE customer_email = 'user@example.com'

Analyzing execution plan...

发现的性能问题：
⚠️ 检测到全表扫描（type: ALL）
⚠️ customer_email 列上缺失索引

优化建议：
1. 添加索引：CREATE INDEX idx_customer_email ON orders(customer_email)
2. 这将把扫描类型从 ALL 改为 ref，显著提高性能
```

### 示例 3：连接优化

```text
mysql> /explain SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id

Analyzing execution plan...

连接分析：
- 连接类型：LEFT JOIN（适合此查询）
- 连接顺序：users → orders（最优）
- 索引使用：两个表都高效使用索引

优化建议：
- 考虑添加覆盖索引：CREATE INDEX idx_user_orders ON orders(user_id, id)
- 这可以消除 COUNT 操作访问 orders 表的需要
```

## 最佳实践

- **优化前**：在做出更改之前使用 `/explain` 了解当前性能
- **创建索引后**：重新运行 `/explain` 以验证索引正在使用
- **复杂查询**：在部署前始终分析具有多个连接的复杂查询
- **定期审查**：定期审查频繁执行查询的执行计划
- **比较计划**：在优化前后使用 `/explain` 以衡量改进

## 提示

- 该命令适用于任何有效的 SQL 语句（SELECT、INSERT、UPDATE、DELETE）
- 对于 UPDATE/DELETE 查询，`/explain` 显示执行计划而不执行修改
- 对计划频繁运行的查询使用 `/explain` 以确保它们已优化
- 与自然语言查询结合使用：在使用 `/explain` 后询问"为什么这个查询很慢？"

