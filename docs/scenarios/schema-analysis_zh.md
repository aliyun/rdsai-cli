# 场景：数据库模式分析与合规性审查

[English](schema-analysis.md) | [中文](schema-analysis_zh.md)

本场景演示如何使用 `/research` 命令执行全面的数据库模式分析和合规性检查。

## 示例

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

## 使用场景

- **模式审查** — 部署到生产环境前，进行全面的合规性检查
- **代码审查** — 分析数据库更改并确保符合标准
- **性能审计** — 识别缺失索引、冗余索引和优化机会
- **迁移准备** — 迁移前审查模式以确保最佳实践
- **入门指南** — 快速了解现有数据库结构并识别问题
- **合规性检查** — 确保数据库设计遵循阿里巴巴数据库开发标准

## 分析内容

- 数据库概览（表、大小、引擎分布）
- 表结构（列、数据类型、主键、注释）
- 索引分析（覆盖、冗余、命名合规性）
- 关系分析（外键、表关系）
- 合规性检查（命名规范、设计标准）
- 问题检测（按优先级 P0/P1/P2/P3 分类的问题）
- 优化建议（具体的 SQL 建议）

## 相关文档

详细文档请参阅 [数据库模式分析 (`/research`)](../features/research_zh.md)。

