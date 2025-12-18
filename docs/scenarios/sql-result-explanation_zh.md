# 场景：使用 Ctrl+E 进行 SQL 结果解释

[English](sql-result-explanation.md) | [中文](sql-result-explanation_zh.md)

本场景演示如何使用 `Ctrl+E` 快捷键获得即时的 AI 驱动 SQL 查询结果和错误解释，帮助您快速理解查询结果并排查问题。

## 示例

### 解释查询结果

执行 SQL 查询后，按 `Ctrl+E` 获得解释：

```text
mysql> SELECT COUNT(*) as total_users, AVG(age) as avg_age FROM users WHERE status = 'active';
+--------------+----------+
| total_users  | avg_age  |
+--------------+----------+
|       15234  |    28.5  |
+--------------+----------+
(1 row in 0.023 sec) 💡 Ctrl+E: Explain result

# 在此处按 Ctrl+E

🤖 Explaining SQL result...

This query counted 15,234 active users in the database and calculated their average age as 28.5 years. 
The result indicates a substantial user base with a relatively young average age, which could be useful 
for demographic analysis or targeted marketing campaigns.
```

### 解释错误

当查询失败时，`Ctrl+E` 帮助您理解错误：

```text
mysql> SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE email = 'test@example.com');
ERROR: Unknown column 'customer_id' in 'where clause' 💡 Ctrl+E: Explain error

# 在此处按 Ctrl+E

🤖 Explaining SQL error...

The error indicates that the column `customer_id` doesn't exist in the `orders` table. This could mean:
1. The column name is incorrect (might be `customerId`, `cust_id`, or similar)
2. The column hasn't been created yet
3. You're querying the wrong table

To fix this, check the table structure with `DESCRIBE orders` or `SHOW CREATE TABLE orders` to see the correct column names.
```

### 解释复杂结果

对于包含多个连接或聚合的复杂查询：

```text
mysql> SELECT u.name, COUNT(o.id) as order_count, SUM(o.total) as total_spent 
       FROM users u 
       LEFT JOIN orders o ON u.id = o.user_id 
       GROUP BY u.id 
       HAVING COUNT(o.id) > 10;
+----------+-------------+-------------+
| name     | order_count | total_spent |
+----------+-------------+-------------+
| Alice    |      15     |   12500.00  |
| Bob      |      23     |   18900.00  |
+----------+-------------+-------------+
(2 rows in 0.156 sec) 💡 Ctrl+E: Explain result

# 在此处按 Ctrl+E

🤖 Explaining SQL result...

This query identified 2 high-value customers (Alice and Bob) who have placed more than 10 orders. 
Alice has 15 orders totaling $12,500, while Bob has 23 orders totaling $18,900. These customers 
represent your most engaged users and might be good candidates for loyalty programs or special offers.
```

## 工作原理

1. **执行 SQL 查询** — 像往常一样运行任何 SQL 语句
2. **查看结果** — 结果显示时带有提示 `💡 Ctrl+E: Explain result` 或 `💡 Ctrl+E: Explain error`
3. **按 Ctrl+E** — 立即触发解释代理
4. **获得解释** — AI 分析查询上下文、结果数据，并提供清晰的解释

解释代理：
- 使用专为 SQL 结果解释优化的专用 AI 模型
- 可以访问完整的查询上下文（SQL、列、行、执行时间、错误）
- 提供简洁、可操作的解释（2-3 句话）
- 使用您配置的语言（英文/中文）响应

## 使用场景

- **理解查询结果** — 快速掌握复杂查询返回的内容，特别是包含聚合、连接或子查询的查询
- **错误排查** — 获得 SQL 错误的清晰解释和修复建议
- **学习 SQL** — 使用解释来理解 SQL 查询的工作原理及其实现的功能
- **代码审查** — 在做出决策前审查查询结果并理解其含义
- **性能分析** — 理解查询返回特定结果的原因并识别潜在问题
- **数据探索** — 在探索不熟悉的数据库时获得查询结果的上下文

## 何时使用

- 执行包含多个连接或聚合的复杂查询后
- 当查询结果意外或令人困惑时
- 遇到不理解的 SQL 错误时
- 学习 SQL 并需要查询行为解释时
- 为数据分析或报告审查查询结果时

## 要求

- **已配置 LLM** — 解释功能需要通过 `/setup` 配置 LLM
- **查询上下文** — 当有最近的 SQL 查询结果需要解释时效果最佳
- **数据库连接** — 需要活动的数据库连接以执行 SQL

## 相关命令

- `/setup` — 配置 LLM 提供商（解释功能必需）
- `/help` — 查看所有可用命令和快捷键
- 自然语言查询 — 询问有关数据的问题，而不是编写 SQL
- `EXPLAIN` SQL 命令 — 获取 MySQL 的执行计划以优化查询

## 最佳实践

- 执行查询后立即使用 `Ctrl+E`，此时上下文仍然清晰
- 对于复杂查询，查看解释以确保正确理解结果
- 排查错误时，使用 `Ctrl+E` 获得可操作的建议
- 结合自然语言查询进行更深入的分析："为什么这个查询返回了 X 个结果？"

## 提示

- 解释提示仅在配置了 LLM 时出现
- 解释简洁（2-3 句话），便于快速理解
- 解释代理使用与 CLI 配置相同的语言
- 适用于成功的查询和错误消息

