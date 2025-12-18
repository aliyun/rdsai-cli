# Scenario: SQL Result Explanation with Ctrl+E

[English](sql-result-explanation.md) | [中文](sql-result-explanation_zh.md)

This scenario demonstrates how to use the `Ctrl+E` shortcut to get instant AI-powered explanations of SQL query results and errors, helping you understand query outcomes and troubleshoot issues quickly.

## Example

### Explaining Query Results

After executing a SQL query, press `Ctrl+E` to get an explanation:

```text
mysql> SELECT COUNT(*) as total_users, AVG(age) as avg_age FROM users WHERE status = 'active';
+--------------+----------+
| total_users  | avg_age  |
+--------------+----------+
|       15234  |    28.5  |
+--------------+----------+
(1 row in 0.023 sec) 💡 Ctrl+E: Explain result

# Press Ctrl+E here

🤖 Explaining SQL result...

This query counted 15,234 active users in the database and calculated their average age as 28.5 years. 
The result indicates a substantial user base with a relatively young average age, which could be useful 
for demographic analysis or targeted marketing campaigns.
```

### Explaining Errors

When a query fails, `Ctrl+E` helps you understand the error:

```text
mysql> SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE email = 'test@example.com');
ERROR: Unknown column 'customer_id' in 'where clause' 💡 Ctrl+E: Explain error

# Press Ctrl+E here

🤖 Explaining SQL error...

The error indicates that the column `customer_id` doesn't exist in the `orders` table. This could mean:
1. The column name is incorrect (might be `customerId`, `cust_id`, or similar)
2. The column hasn't been created yet
3. You're querying the wrong table

To fix this, check the table structure with `DESCRIBE orders` or `SHOW CREATE TABLE orders` to see the correct column names.
```

### Explaining Complex Results

For complex queries with multiple joins or aggregations:

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

# Press Ctrl+E here

🤖 Explaining SQL result...

This query identified 2 high-value customers (Alice and Bob) who have placed more than 10 orders. 
Alice has 15 orders totaling $12,500, while Bob has 23 orders totaling $18,900. These customers 
represent your most engaged users and might be good candidates for loyalty programs or special offers.
```

## How It Works

1. **Execute SQL Query** — Run any SQL statement as usual
2. **View Result** — The result is displayed with a hint showing `💡 Ctrl+E: Explain result` or `💡 Ctrl+E: Explain error`
3. **Press Ctrl+E** — Instantly trigger the explain agent
4. **Get Explanation** — The AI analyzes the query context, result data, and provides a clear explanation

The explain agent:
- Uses a dedicated AI model optimized for SQL result explanation
- Has access to the full query context (SQL, columns, rows, execution time, errors)
- Provides concise, actionable explanations (2-3 sentences)
- Responds in your configured language (English/中文)

## Use Cases

- **Understanding Query Results** — Quickly grasp what complex queries return, especially with aggregations, joins, or subqueries
- **Error Troubleshooting** — Get clear explanations of SQL errors and suggestions for fixes
- **Learning SQL** — Use explanations to understand how SQL queries work and what they accomplish
- **Code Review** — Review query results and understand their implications before making decisions
- **Performance Analysis** — Understand why queries return certain results and identify potential issues
- **Data Exploration** — Get context about query results when exploring unfamiliar databases

## When to Use

- After executing complex queries with multiple joins or aggregations
- When query results are unexpected or confusing
- When encountering SQL errors you don't understand
- When learning SQL and need explanations of query behavior
- When reviewing query results for data analysis or reporting

## Requirements

- **LLM Configured** — The explain feature requires an LLM to be configured via `/setup`
- **Query Context** — Works best when there's a recent SQL query result to explain
- **Database Connection** — Requires an active database connection for SQL execution

## Related Commands

- `/setup` — Configure LLM provider (required for explain feature)
- `/help` — View all available commands and shortcuts
- Natural language queries — Ask questions about your data instead of writing SQL
- `EXPLAIN` SQL command — Get MySQL's execution plan for query optimization

## Best Practices

- Use `Ctrl+E` immediately after executing a query while the context is fresh
- For complex queries, review the explanation to ensure you understand the results correctly
- When troubleshooting errors, use `Ctrl+E` to get actionable suggestions
- Combine with natural language queries for deeper analysis: "why did this query return X results?"

## Tips

- The explain hint only appears when LLM is configured
- Explanations are concise (2-3 sentences) for quick understanding
- The explain agent uses the same language as your CLI configuration
- Works with both successful queries and error messages

