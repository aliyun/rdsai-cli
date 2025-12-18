# Scenario: Database Schema Analysis & Compliance Review

[English](schema-analysis.md) | [中文](schema-analysis_zh.md)

This scenario demonstrates using the `/research` command to perform comprehensive database schema analysis and compliance checking.

## Example

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

## Use Cases

- **Schema Review** — Before deploying to production, get a comprehensive compliance check
- **Code Review** — Analyze database changes and ensure they meet standards
- **Performance Audit** — Identify missing indexes, redundant indexes, and optimization opportunities
- **Migration Preparation** — Review schema before migrating to ensure best practices
- **Onboarding** — Understand existing database structure and identify issues quickly
- **Compliance Checking** — Ensure database design follows Alibaba Database Development Standards

## What Gets Analyzed

- Database overview (tables, size, engine distribution)
- Table structure (columns, data types, primary keys, comments)
- Index analysis (coverage, redundancy, naming compliance)
- Relationship analysis (foreign keys, table relationships)
- Compliance checking (naming conventions, design standards)
- Issue detection (prioritized P0/P1/P2/P3 issues)
- Optimization suggestions (specific SQL recommendations)

## Related Documentation

See [Database Schema Analysis (`/research`)](../features/research.md) for detailed documentation.

