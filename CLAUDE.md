# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RDSAI CLI is an AI-powered database CLI that enables natural language interaction with MySQL databases and files (CSV, Excel). Users can run SQL queries or ask questions in natural language, and the AI agent orchestrates diagnostic tools, analyzes execution plans, and executes queries.

## Development Commands

```bash
# Install dependencies
uv sync --extra dev

# Run the CLI
uv run rdsai

# Run tests
./dev/pytest.sh                          # or: uv run pytest
uv run pytest tests/loop/test_runtime.py # specific test file
uv run pytest -k "test_runtime"          # tests matching pattern

# Code quality (lint + format)
./dev/code-style.sh                      # auto-fix issues
./dev/code-style.sh --check              # check only

# Direct ruff commands
uv run ruff check --fix .                # lint with auto-fix
uv run ruff format .                     # format code
```

## Architecture

### Core Loop (LangGraph-based Agent)

The agent loop is built on LangGraph and lives in `loop/`:

- **`neoloop.py`**: Main agent loop (`NeoLoop`) - manages conversation flow, tool execution, and human-in-the-loop approval
- **`agent.py`**: Agent loading from YAML specs with dependency injection for tools
- **`agentspec.py`**: YAML-based agent specification with inheritance (`extend: default`)
- **`runtime.py`**: Runtime configuration dataclass holding config, LLM, session, and MCP settings
- **`toolset.py`**: Tool system with `BaseTool[T]`, `DynamicToolset` for runtime tool management
- **`nodes.py`**: LangGraph nodes (agent_node, tools_node, should_continue)
- **`state.py`**: LangGraph state definition (`AgentState`)
- **`compaction.py`**: Context compaction for long conversations

Agent specs are YAML files in `prompts/` (e.g., `default_agent.yaml`) that define:
- System prompt path and template arguments
- Tool list as module paths (e.g., `tools.database.select:Select`)
- Inheritance via `extend: default`

### Application Lifecycle

- **`cli.py`**: Entry point using Typer, creates `Session` and runs `Application`
- **`app.py`**: `Application` class manages lifecycle (MCP connections, background tasks, REPL)
- **`config/`**: Configuration loading (`~/.rdsai-cli/config.json`), LLM provider settings

### Database Layer (`database/`)

- **`service.py`**: `DatabaseService` - central class for connection management, query execution, transaction handling
- **`client.py`**: `DatabaseClient` interface and MySQL implementation
- **`duckdb_client.py`**: DuckDB client for file-based data (CSV, Excel)
- **`types.py`**: `QueryResult`, `ConnectionConfig`, `QueryType` enums

Global database service is accessed via `get_service()` / `set_service()`.

### Tools (`tools/`)

Tools are Pydantic-based classes inheriting from `BaseTool[ParamsType]`:

- **`tools/database/`**: SQL execution tools (`Select`, `DDLExecutor`, `MySQLExplain`, etc.)
- **`tools/database/database_base.py`**: `DatabaseToolBase` - common base for database tools
- **`tools/mcp/`**: MCP (Model Context Protocol) integration for external tool servers
- **`tools/sysbench/`**: Performance benchmarking tools
- **`tools/subagent/`**: Sub-agent execution for specialized tasks

### UI Layer (`ui/`)

- **`ui/backslash/`**: Backslash command system (e.g., `/connect`, `/setup`, `/help`)
  - Commands registered via `@backslash_command` decorator in `registry.py`
- **`ui/completers.py`**: Auto-completion for SQL and commands
- **`ui/console.py`**: Rich-based console output

### Events (`events/`)

- **`message.py`**: Event types for UI communication (ApprovalRequest, StatusUpdate, etc.)

## Key Patterns

### Tool Implementation

```python
class MyToolParams(BaseModel):
    query: str = Field(description="The query to execute")

class MyTool(BaseTool[MyToolParams]):
    name = "my_tool"
    description = "Description for LLM"
    params = MyToolParams

    def __init__(self, builtin_args: BuiltinSystemPromptArgs, **kwargs):
        super().__init__(**kwargs)
        # Dependencies injected based on __init__ signature

    async def __call__(self, params: MyToolParams) -> ToolReturnType:
        # Return ToolOk(output=...) or ToolError(message=...)
```

### Backslash Commands

```python
@backslash_command(char="s", name="status", category=CommandCategory.SESSION)
def cmd_status(ctx: CommandContext) -> CommandResult | None:
    '''Get status information from the server.'''
    ...
```

### Testing

Tests mock DuckDB globally via `tests/conftest.py` to prevent segfaults. Use `pytest-asyncio` for async tests.

## Configuration Files

- `~/.rdsai-cli/config.json`: LLM provider settings, API keys
- `mcp.example.yaml`: Example MCP server configuration
- `prompts/default_agent.yaml`: Default agent specification
