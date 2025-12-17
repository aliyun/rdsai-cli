Delegate task to specialized subagent for execution.

This tool allows the main agent to delegate complex tasks to specialized subagents that have dedicated system prompts and tool sets for specific domains.

Subagents are automatically discovered from the prompts directory. Each subagent has its own configuration file (e.g., `sysbench_agent.yaml`) and can have custom execution logic if needed.

## Parameters

- **subagent** (required): The subagent to delegate to. Available subagents are automatically discovered. Common subagents include:
  - `sysbench`: Database performance testing and benchmarking
- **task_description** (required): Detailed description of the task to be performed.
- **parameters** (optional): Additional parameters for the subagent (specific to each subagent type):
  - For sysbench: `test_type`, `threads`, `time`, `tables`, `table_size`, etc.

## Examples

Delegate performance test:
```
subagent: "sysbench"
task_description: "Execute performance test with 100 threads for 60 seconds"
parameters: {"threads": 100, "time": 60, "test_type": "oltp_read_write"}
```
