# Database Schema Analysis (`/research`)

[English](research.md) | [中文](research_zh.md)

The `/research` command generates comprehensive database analysis reports powered by AI. It analyzes your database schema, checks compliance against Alibaba Database Development Standards, and provides actionable recommendations.

## What It Analyzes

- **Database Overview** — Total tables, size, engine distribution, statistics
- **Table Structure** — Columns, data types, primary keys, comments
- **Index Analysis** — Index coverage, redundancy detection, missing indexes, naming compliance
- **Relationship Analysis** — Foreign keys, table relationships, orphan tables
- **Compliance Checking** — Naming conventions, design standards, index design against Alibaba standards
- **Issue Detection** — Prioritized issues (P0/P1/P2/P3) with severity classification
- **Optimization Suggestions** — Specific SQL recommendations with impact analysis

## Usage

```text
# Analyze entire database
mysql> /research

# Analyze specific tables only
mysql> /research orders users products

# Show help
mysql> /research help
```

## Use Cases

- **Schema Review** — Before deploying to production, get a comprehensive compliance check
- **Code Review** — Analyze database changes and ensure they meet standards
- **Performance Audit** — Identify missing indexes, redundant indexes, and optimization opportunities
- **Migration Preparation** — Review schema before migrating to ensure best practices
- **Onboarding** — Understand existing database structure and identify issues quickly
- **Compliance Checking** — Ensure database design follows Alibaba Database Development Standards

## Report Structure

The analysis report includes:

1. **Executive Summary** — Overall compliance score, critical issues count, top priorities
2. **Database Overview** — Statistics, engine distribution, size breakdown
3. **Table Analysis** — Detailed analysis of each table's structure and compliance
4. **Index Analysis** — Index coverage, redundancy, naming compliance, selectivity assessment
5. **Relationship Analysis** — Foreign key relationships and patterns
6. **Compliance Scores** — Breakdown by category (Naming, Table Design, Index Design)
7. **Issues Found** — Prioritized list with severity (P0/P1/P2/P3)
8. **Recommendations** — Actionable SQL fixes with impact analysis and risk assessment

## Example Output

```text
mysql> /research

Exploring database: ecommerce_db
✓ Explored 12 tables (156 columns, 8 relationships)
Analyzing schema...

📊 Database Analysis Report

## Executive Summary
- Database: ecommerce_db
- Total Tables: 12
- Overall Compliance Score: 72/100 ⚠️
- Critical Issues: 3 (P0/P1)
- Top Priority Actions:
  1. Add primary keys to `user_sessions` and `audit_logs` tables
  2. Fix index naming conventions (5 violations)
  3. Replace `float` with `decimal` in `orders.total_amount`

## Issues Found

🔴 Critical (P0):
- Table `user_sessions` missing primary key
- Table `audit_logs` missing primary key
- Field `orders.total_amount` uses `float` instead of `decimal`

🟡 Warning (P2):
- Index `idx1` on `users` table violates naming convention (should be `idx_user_email`)
- Redundant index: `idx_user_id` is prefix of `idx_user_id_status`
- Missing table comments on 3 tables

## Recommendations

### [P0] Add Primary Keys
**Location**: `user_sessions`, `audit_logs`
**SQL**:
```sql
ALTER TABLE user_sessions ADD COLUMN id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
ALTER TABLE audit_logs ADD COLUMN id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```
```

