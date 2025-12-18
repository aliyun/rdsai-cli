# Scenario: Lock Wait & Deadlock Troubleshooting

[English](lock-troubleshooting.md) | [中文](lock-troubleshooting_zh.md)

This scenario shows how RDSAI CLI helps diagnose and resolve lock contention issues in MySQL.

## Example

```text
mysql> check for lock waits

🔧 Calling tool: Transaction
🔒 1 Lock Wait Detected:
   • Blocker: Connection 42 (idle 45s, uncommitted transaction)
     Query: UPDATE users SET balance = balance - 100 WHERE id = 1001
   • Waiting: Connection 56 (waiting 15s for row lock)

💡 Suggestion: Connection 42 holds lock but is idle. Consider KILL 42 if safe.
```

## How It Works

The AI combines multiple diagnostic tools:

1. **Transaction** — Identifies lock waits and deadlocks
2. **ShowProcess** — Shows active connections and their queries
3. **Process Analysis** — Traces lock chains and identifies blockers

## Use Cases

- Detect lock contention in real-time
- Identify idle connections holding locks
- Understand lock wait chains
- Get recommendations for resolving deadlocks
- Monitor transaction status and isolation levels

## Related Commands

- Natural language queries like "check for lock waits", "show deadlocks"
- `SHOW PROCESSLIST` SQL command
- `SHOW ENGINE INNODB STATUS` for detailed lock information

## Best Practices

- Always verify before killing connections
- Check transaction isolation levels
- Review application code for long-running transactions
- Monitor lock wait timeouts

