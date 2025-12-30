# Execution Plan Analysis (`/explain`)

[English](execution-plan-analysis.md) | [中文](execution-plan-analysis_zh.md)

The `/explain` command provides AI-powered analysis of SQL execution plans. It executes `EXPLAIN` on your SQL query and uses AI to analyze the execution plan, identify performance issues, and provide specific optimization suggestions.

## What It Analyzes

- **Key Metrics** — Index usage, scan type, estimated rows scanned, join order and type
- **Performance Issues** — Full table scans, missing index usage, large row counts, inefficient joins
- **Optimization Suggestions** — Specific index recommendations, query rewriting suggestions, join optimization strategies

## Usage

```text
# Analyze a simple query
mysql> /explain SELECT * FROM users WHERE email = 'test@example.com'

# Analyze a complex query with joins
mysql> /explain SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id

# Analyze a query with subqueries
mysql> /explain SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE status = 'active')
```

## Use Cases

### Performance Troubleshooting

Analyze slow queries to identify bottlenecks before optimization:

```text
mysql> /explain SELECT * FROM orders WHERE customer_id = 123 AND status = 'pending'
```

The AI will analyze:
- Whether indexes are being used efficiently
- Scan type (full table scan vs index scan)
- Estimated rows to be scanned
- Potential performance bottlenecks

### Index Optimization

Check if queries are using indexes efficiently and identify missing indexes:

```text
mysql> /explain SELECT * FROM products WHERE name LIKE '%laptop%'
```

The AI will identify:
- Full table scans that could be avoided with proper indexes
- Missing indexes that would improve performance
- Index usage efficiency

### Query Optimization

Get suggestions for rewriting queries to improve performance:

```text
mysql> /explain SELECT u.*, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE u.status = 'active'
```

The AI will suggest:
- Better join strategies
- Query rewriting techniques
- Index recommendations

### Join Analysis

Understand join order and type for multi-table queries:

```text
mysql> /explain SELECT u.name, o.total, p.name 
       FROM users u 
       JOIN orders o ON u.id = o.user_id 
       JOIN products p ON o.product_id = p.id
```

The AI will analyze:
- Join order optimization
- Join type (INNER, LEFT, etc.) efficiency
- Join algorithm recommendations

### Full Table Scan Detection

Identify queries that scan entire tables unnecessarily:

```text
mysql> /explain SELECT * FROM logs WHERE created_at > '2024-01-01'
```

The AI will detect:
- Full table scans (type: ALL)
- Missing indexes on WHERE clause columns
- Suggestions for adding appropriate indexes

### Pre-Deployment Review

Review execution plans for production queries before deployment:

```text
mysql> /explain SELECT COUNT(*) FROM orders WHERE status = 'completed' AND created_at BETWEEN '2024-01-01' AND '2024-12-31'
```

The AI will help ensure:
- Queries are optimized before going to production
- Proper indexes are in place
- No unexpected full table scans


## Analysis Output

The AI provides detailed analysis including:

- **Index Usage Analysis**: Which indexes are used, which are missing
- **Scan Type Analysis**: ALL (full table scan), index, range, ref, etc.
- **Row Estimation**: Estimated rows to be scanned
- **Join Analysis**: Join order, join type, join algorithm
- **Extra Information**: Using index, Using where, Using filesort, etc.
- **Performance Issues**: Prioritized list of issues found
- **Optimization Suggestions**: Specific SQL recommendations

## Requirements

- **Database Connection** — Requires an active database connection via `/connect`
- **LLM Configured** — Requires LLM to be configured via `/setup`
- **Valid SQL** — The SQL statement must be valid and executable

## Examples

### Example 1: Simple Query Analysis

```text
mysql> /explain SELECT * FROM users WHERE id = 100

Analyzing execution plan...

The execution plan shows:
- Index usage: PRIMARY key is used (good)
- Scan type: const (very efficient)
- Estimated rows: 1
- Performance: Excellent - direct index lookup

No optimization needed for this query.
```

### Example 2: Missing Index Detection

```text
mysql> /explain SELECT * FROM orders WHERE customer_email = 'user@example.com'

Analyzing execution plan...

Performance Issues Found:
⚠️ Full table scan detected (type: ALL)
⚠️ Missing index on customer_email column

Optimization Suggestions:
1. Add index: CREATE INDEX idx_customer_email ON orders(customer_email)
2. This will change scan type from ALL to ref, significantly improving performance
```

### Example 3: Join Optimization

```text
mysql> /explain SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id

Analyzing execution plan...

Join Analysis:
- Join type: LEFT JOIN (appropriate for this query)
- Join order: users → orders (optimal)
- Index usage: Both tables use indexes efficiently

Optimization Suggestions:
- Consider adding covering index: CREATE INDEX idx_user_orders ON orders(user_id, id)
- This can eliminate the need to access the orders table for COUNT operations
```

## Best Practices

- **Before Optimization**: Use `/explain` to understand current performance before making changes
- **After Index Creation**: Re-run `/explain` to verify indexes are being used
- **Complex Queries**: Always analyze complex queries with multiple joins before deployment
- **Regular Reviews**: Periodically review execution plans for frequently executed queries
- **Compare Plans**: Use `/explain` before and after optimization to measure improvement


## Tips

- The command works with any valid SQL statement (SELECT, INSERT, UPDATE, DELETE)
- For UPDATE/DELETE queries, `/explain` shows the execution plan without executing the modification
- Use `/explain` on queries you plan to run frequently to ensure they're optimized
- Combine with natural language queries: "why is this query slow?" after using `/explain`

