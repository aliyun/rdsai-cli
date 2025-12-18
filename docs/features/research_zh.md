# Database Schema分析 (`/research`)

[English](research.md) | [中文](research_zh.md)

`/research` 命令生成由 AI 驱动的全面数据库分析报告。它分析您的数据库库表Schema，检查是否符合阿里巴巴数据库开发标准，并提供可操作的建议。

## 分析内容

- **数据库概览** — 总表数、大小、引擎分布、统计信息
- **表结构** — 列、数据类型、主键、注释
- **索引分析** — 索引覆盖、冗余检测、缺失索引、命名合规性
- **关系分析** — 外键、表关系、孤立表
- **合规性检查** — 命名规范、设计标准、索引设计是否符合阿里巴巴标准
- **问题检测** — 按优先级（P0/P1/P2/P3）分类的问题，带严重程度分类
- **优化建议** — 具体的 SQL 建议，包含影响分析

## 使用方法

```text
# 分析整个数据库
mysql> /research

# 仅分析特定表
mysql> /research orders users products

# 显示帮助
mysql> /research help
```

## 使用场景

- **模式审查** — 部署到生产环境前，进行全面的合规性检查
- **代码审查** — 分析数据库更改并确保符合标准
- **性能审计** — 识别缺失索引、冗余索引和优化机会
- **迁移准备** — 迁移前审查模式以确保最佳实践
- **入门指南** — 快速了解现有数据库结构并识别问题
- **合规性检查** — 确保数据库设计遵循阿里巴巴数据库开发标准

## 报告结构

分析报告包括：

1. **执行摘要** — 总体合规性评分、关键问题数量、优先事项
2. **数据库概览** — 统计信息、引擎分布、大小分解
3. **表分析** — 每个表的结构和合规性详细分析
4. **索引分析** — 索引覆盖、冗余、命名合规性、选择性评估
5. **关系分析** — 外键关系和模式
6. **合规性评分** — 按类别分解（命名、表设计、索引设计）
7. **发现的问题** — 按优先级（P0/P1/P2/P3）和严重程度分类的列表
8. **建议** — 可操作的 SQL 修复，包含影响分析和风险评估

## 示例输出

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

