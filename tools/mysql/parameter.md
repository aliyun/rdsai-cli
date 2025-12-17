Get MySQL system variable information using SHOW VARIABLES.

**When to use:**
- Performance troubleshooting when system configuration is suspected
- Investigating specific parameter-related issues (timeouts, buffer sizes, etc.)
- DO NOT use for simple schema analysis or basic index review

**Parameters:**
- **parameter_name**: Exact name or wildcard pattern (e.g., 'innodb_buffer_pool_size', '%timeout%')

Shows current values of MySQL system variables for performance analysis and configuration troubleshooting.
