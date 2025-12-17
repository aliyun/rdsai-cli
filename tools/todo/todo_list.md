Manage task breakdown and progress tracking for complex database operations.

**When to use:**
- Multi-table correlation analysis (e.g., cross-table performance diagnosis)
- Complex performance troubleshooting workflows
- Schema design or migration tasks with multiple steps
- Any task with 3+ distinct subtasks or milestones

**DO NOT use for:**
- Simple questions (e.g., "What indexes does table X have?")
- Single-tool operations (e.g., "Show slow queries from today")
- Tasks with only 1-2 steps
- Direct instructions that can be executed immediately

**Parameters:**
- **todos**: List of todo items, each with:
  - **title**: Brief description of the subtask
  - **status**: One of "Pending", "In Progress", or "Done"

**Usage notes:**
- Update the entire list each time (this is a replace operation, not append)
- Mark items "Done" as you complete them
- Keep only one item "In Progress" at a time
- Be flexible: start without todos for simple tasks, add them if complexity emerges
