# 场景：锁等待与死锁故障排除

[English](lock-troubleshooting.md) | [中文](lock-troubleshooting_zh.md)

本场景展示 RDSAI CLI 如何帮助诊断和解决 MySQL 中的锁竞争问题。

## 示例

```text
mysql> check for lock waits

🔧 Calling tool: Transaction
🔒 1 Lock Wait Detected:
   • Blocker: Connection 42 (idle 45s, uncommitted transaction)
     Query: UPDATE users SET balance = balance - 100 WHERE id = 1001
   • Waiting: Connection 56 (waiting 15s for row lock)

💡 Suggestion: Connection 42 holds lock but is idle. Consider KILL 42 if safe.
```

## 工作原理

AI 结合多个诊断工具：

1. **Transaction** — 识别锁等待和死锁
2. **ShowProcess** — 显示活动连接及其查询
3. **Process Analysis** — 跟踪锁链并识别阻塞者

## 使用场景

- 实时检测锁竞争
- 识别持有锁的空闲连接
- 理解锁等待链
- 获得解决死锁的建议
- 监控事务状态和隔离级别

## 相关命令

- 自然语言查询，如 "check for lock waits"、"show deadlocks"
- `SHOW PROCESSLIST` SQL 命令
- `SHOW ENGINE INNODB STATUS` 用于详细的锁信息

## 最佳实践

- 终止连接前始终验证
- 检查事务隔离级别
- 审查应用程序代码中的长时间运行事务
- 监控锁等待超时

