# 场景：本地文件连接与分析

[English](local-file-analysis.md) | [中文](local-file-analysis_zh.md)

本场景演示如何使用 RDSAI CLI 连接本地文件（CSV、Parquet、JSON、Excel）并使用原生 SQL 查询进行数据分析。您也可以使用自然语言查询作为辅助方式，但 SQL 仍然是主要且最强大的数据交互方式。

## 示例

### 连接到本地 CSV 文件

```text
$ rdsai
> /connect sales.csv

Loading data from file...
✓ Connected to sales.csv
✓ Loaded sales.csv → table 'sales' (15234 rows, 8 columns)
```

### 使用 SQL 查询数据

连接后，可以使用原生 SQL 查询数据：

```text
> SELECT * FROM sales LIMIT 10

+------------+------------+----------+--------+----------+------------+--------+-------+
| order_id   | date       | product  | amount | quantity | customer_id| region | status|
+------------+------------+----------+--------+----------+------------+--------+-------+
| ORD-001    | 2024-01-15 | Widget A | 99.99  |    2     | CUST-123   | North  | paid  |
| ORD-002    | 2024-01-15 | Widget B | 149.50 |    1     | CUST-456   | South  | paid  |
...
+------------+------------+----------+--------+----------+------------+--------+-------+
(10 rows in 0.012 sec) 💡 Ctrl+E: Explain result
```

### 高级 SQL 查询

可以编写复杂的 SQL 查询进行分析：

```text
> SELECT product, SUM(amount) as total_sales 
  FROM sales 
  WHERE status = 'paid'
  GROUP BY product 
  ORDER BY total_sales DESC 
  LIMIT 5

+----------+-------------+
| product  | total_sales |
+----------+-------------+
| Widget A |   125000.50 |
| Widget B |    98000.25 |
| Widget C |    75000.00 |
| Widget D |    62000.75 |
| Widget E |    45000.50 |
+----------+-------------+
(5 rows in 0.045 sec)
```

### 连接多个文件

可以连接多个文件进行跨文件分析：

```text
> /connect customers.csv orders.csv products.csv

Loading data from 3 files...
✓ Connected to customers.csv, orders.csv, products.csv
✓ Loaded customers.csv → table 'customers' (5000 rows, 6 columns)
✓ Loaded orders.csv → table 'orders' (15234 rows, 8 columns)
✓ Loaded products.csv → table 'products' (150 rows, 5 columns)
```

### 跨文件分析

```text
> SELECT 
    c.customer_id,
    c.name,
    COUNT(o.order_id) as order_count,
    SUM(o.amount) as lifetime_value
  FROM customers c
  LEFT JOIN orders o ON c.customer_id = o.customer_id
  GROUP BY c.customer_id, c.name
  ORDER BY lifetime_value DESC
  LIMIT 10

+------------+------------------+-------------+----------------+
| customer_id| name             | order_count | lifetime_value |
+------------+------------------+-------------+----------------+
| CUST-123   | John Smith       |     45      |   12500.50     |
| CUST-456   | Jane Doe         |     38      |   11200.25     |
...
+------------+------------------+-------------+----------------+
(10 rows in 0.089 sec)
```

### 自然语言查询

除了 SQL，您也可以使用自然语言查询作为辅助方式。系统会将您的问题转换为 SQL：

```text
> what are the top 5 products by total sales?

🔧 Executing SQL: 
SELECT product, SUM(amount) as total_sales 
FROM sales 
WHERE status = 'paid'
GROUP BY product 
ORDER BY total_sales DESC 
LIMIT 5

+----------+-------------+
| product  | total_sales |
+----------+-------------+
| Widget A |   125000.50 |
| Widget B |    98000.25 |
| Widget C |    75000.00 |
| Widget D |    62000.75 |
| Widget E |    45000.50 |
+----------+-------------+
(5 rows in 0.045 sec)
```

> 注意：虽然支持自然语言查询，但对于复杂分析，直接编写 SQL 能提供更好的控制和精确度。

## 支持的文件格式

- **CSV 文件** (`.csv`) — 逗号分隔值文件
- **Excel 文件** (`.xlsx`) — Excel 2007+ 格式

## 连接方式

### 本地文件

```text
# 文件名（在当前目录搜索）
> /connect data.csv

# 绝对路径
> /connect /path/to/data.csv

# 相对路径
> /connect ./data/data.csv

# 使用 file:// 协议
> /connect file:///path/to/data.csv
```

### 远程文件

```text
# HTTP
> /connect http://example.com/data.csv

# HTTPS
> /connect https://example.com/data.csv
```

### 多个文件

```text
# 同时连接多个文件
> /connect file1.csv file2.csv file3.xlsx
```

## 使用场景

- **数据探索** — 快速探索 CSV/Excel 文件，无需导入数据库
- **临时分析** — 对数据文件进行一次性分析
- **报告生成** — 从数据文件生成洞察和报告
- **数据验证** — 检查数据质量并识别问题
- **跨文件分析** — 连接和分析多个文件的数据
- **快速原型** — 在导入数据库之前测试分析工作流
- **数据迁移** — 在迁移到数据库之前分析源数据

## 工作原理

1. **连接** — 使用 `/connect` 和文件路径加载数据
2. **自动加载** — 文件自动加载到 DuckDB 表中
3. **查询** — 使用原生 SQL 查询分析数据（主要方式）
4. **自然语言** — 可选使用自然语言查询作为辅助

系统会：
- 自动检测文件格式（CSV、Parquet、JSON、Excel）
- 创建具有适当列类型的表
- 支持标准 SQL 查询（SELECT、JOIN、GROUP BY 等）
- 可以将自然语言问题转换为 SQL 查询

## 相关命令

- `/connect` — 连接到文件或数据库
- `/disconnect` — 断开当前数据源连接
- `/help` — 查看所有可用命令
- SQL 查询 — 编写原生 SQL 查询数据（推荐）
- 自然语言查询 — 使用自然语言提问（可选）
- `Ctrl+E` — 即时解释查询结果

## 最佳实践

- **文件位置** — 将数据文件保存在可访问的位置或使用绝对路径
- **文件大小** — 大文件（>100MB）可能需要更长的加载时间
- **数据类型** — 列类型是自动检测的；如需要请验证
- **多个文件** — 连接多个文件时使用描述性文件名
- **分析** — 从简单查询开始，然后逐步构建复杂分析

## 提示

- 文件表名基于文件名（例如，`sales.csv` → `sales` 表）
- 使用 `SHOW TABLES` 查看所有已加载的表
- 使用 `DESCRIBE table_name` 查看表结构
- 直接编写 SQL 查询来探索和分析数据（推荐以获得最佳控制）
- 也可以使用自然语言查询进行快速探索
- 查询后按 `Ctrl+E` 获取解释
- 如果数据发生变化，断开并重新连接以重新加载文件

## 限制

- 文件加载到内存中（内存数据库）
- 非常大的文件（>1GB）可能需要大量内存
- 文件修改需要重新连接以重新加载
- 某些 Excel 功能（公式、宏）不受支持
