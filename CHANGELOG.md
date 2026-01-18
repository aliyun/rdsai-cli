# Changelog

All notable changes to RDSAI CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Agent effectiveness optimization
- Interactive experience improvements
- Security enhancements
- Diagnostic report export

## [v0.1.8] - 2026-01-18

### Added
- **Multi-Source Connection**: DuckDB support for local files and remote data sources
  - Connect to local files: CSV, Parquet, JSON, Excel (.xlsx) formats
  - Connect to remote files via HTTP/HTTPS URLs
  - Support for multiple files simultaneously in a single connection
  - Automatic file format detection and table creation
  - DuckDB database file support (`duckdb://` protocol)
- **Data Analysis Tool**: New `DataAnalyzer` tool for analytical SQL queries
  - Execute analytical SELECT queries on MySQL and DuckDB databases
  - Support for complex queries: CTEs, JOINs, aggregations, window functions
  - Statistical analysis capabilities (COUNT, SUM, AVG, MIN, MAX, STDDEV, etc.)
  - Automatic engine detection (MySQL vs DuckDB)
- **Installation**: One-click installation script
  - Automated installation script (`install.sh`) for easy setup
  - Version option (`--version`, `-v`) to display CLI version
  - Improved installation experience for new users
- **MySQL Tools**: Simplified MySQL utility module
  - Consolidated MySQL tools for better maintainability
  - Enhanced `MySQLSelect` tool for system table queries
  - Enhanced `MySQLShow` tool for SHOW statements
  - New `MySQLDesc` tool for DESCRIBE statements
  - Removed redundant tools in favor of unified approach

### Fixed
- **Connection Handling**: Improved connection interruption handling
  - Fixed issues with handling connection interruptions during database connection
  - Better error messages and recovery mechanisms
  - Improved user experience when connection fails

### Changed
- **Tool Architecture**: Refactored database tool structure
  - Renamed `QueryAnalyzer` to `DataAnalyzer` for clarity
  - Simplified tool registration and configuration
  - Improved tool organization and maintainability
- **UI**: Enhanced connection command prompt messages
  - More informative connection status messages
  - Better feedback for file loading progress
  - Improved error messages for connection failures

### Documentation
- **Scenarios**: Added local file analysis scenario documentation
  - Comprehensive guide for connecting to and analyzing local files
  - Examples for CSV, Parquet, JSON, and Excel file analysis
  - SQL query examples for data exploration
  - Available in both English and Chinese

### Testing
- **Test Coverage**: Enhanced test suite for new features
  - Added comprehensive tests for DuckDB client
  - Added tests for DuckDB file loader
  - Added tests for database service with DuckDB
  - Added tests for connection command with file connectors
  - Improved test infrastructure and mock support

## [v0.1.6] - 2025-12-30

### Added
- **SQL Analysis**: SQL execution plan analysis functionality (`/explain` command)
  - AI-powered execution plan analysis and optimization suggestions
  - Automatic EXPLAIN execution and result formatting
  - Integration with existing explain agent for comprehensive analysis
- **Configuration**: Embedding model configuration support
  - Support for configuring embedding models in LLM settings
  - Multiple embedding provider adapters (OpenAI, Qwen, etc.)
  - Embedding service for text vectorization
- **Meta Commands**: Subcommand support and completion functionality for meta-commands
  - Enhanced command completion with subcommand awareness
  - Improved command discovery and help system
- **Version Management**: Automatic version upgrade check functionality
  - Periodic check for new versions from PyPI
  - Configurable check interval and auto-check settings
  - Upgrade notifications and command suggestions
- **Compatibility**: MySQL 8.0.22+ version compatibility support
  - Enhanced compatibility with newer MySQL versions
  - Improved handling of MySQL-specific features

### Fixed
- **Code Quality**: Fixed whitespace character issues in base.py and replica_status.py
  - Removed trailing whitespace characters
  - Improved code consistency

### Changed
- **Testing**: Enhanced test coverage
  - Added comprehensive unit tests for settings module
  - Added unit tests for upgrade module
  - Improved test infrastructure and coverage

### Documentation
- **Tutorials**: Added complete tutorial documentation (English/中文)
  - Comprehensive getting started guide
  - Step-by-step usage instructions
  - Best practices and examples
- **Features**: Added execution plan analysis feature documentation
  - Detailed feature description and usage guide
  - Examples and use cases
- **Contributing**: Updated contributing guidelines and PR template
  - Enhanced development script instructions
  - Improved PR template with better descriptions and checklists
  - Added development workflow documentation

### Development
- **Tooling**: Added development scripts and templates
  - Code style checking script
  - Pytest execution script
  - PR template for better contribution workflow

## [v0.1.5] - 2025-12-25

### Fixed
- **SQL Detection**: Enhanced SHOW statement detection with support for optional modifiers (FULL, EXTENDED, GLOBAL, SESSION, MASTER, SLAVE, REPLICA)
- **SQL Detection**: Support CTE (Common Table Expressions) queries in SQL statement detection
- **UI**: Improved keyboard interrupt handling and visualization logic

### Changed
- **Performance**: Optimized `is_sql_statement` method complexity
  - Replaced list lookups with frozenset for O(1) lookup performance
  - Optimized token parsing using generator expressions
  - Reduced redundant string operations
- **Code Quality**: Standardized code formatting and string quotation conventions
- **CI/CD**: Migrated from pylint to Ruff for faster linting

### Added
- **Testing**: Added comprehensive test coverage for UI module (completers, prompt, repl)
- **Testing**: Added SQL statement parsing test cases for database service
- **Testing**: Added unit tests for AgentSpec, compaction context, and nodes module
- **Tooling**: Added Ruff configuration file for code quality checks


## [v0.1.4] - 2025-12-24

### Changed
- **Dependencies**: Remove unused aiofiles dependency to reduce package size

### Documentation
- Add Python version and license badges to README
- Update README demo examples and usage instructions

## [v0.1.3] - 2025-12-21

### Added
- **Configuration**: Dynamic version detection from package metadata or pyproject.toml
  - Automatically reads version information at runtime
  - Adds "v" prefix to version number for consistent formatting
  - Falls back to "UNKNOWN" when version cannot be determined
  - Updates user agent string to include dynamic version information

### Fixed
- **Security**: Hide database password input in CLI (previously visible in terminal)
- **UI**: Fix prompt display text updates

### Changed
- **UX**: Update prompt display when refreshing database connection
- **Dependencies**: Remove unused aiofiles dependency to reduce package size
- **Code Quality**: 
  - Add pylint configuration file for optimized code checking rules
  - Adjust pylint configuration rules and restrictions
  - Format code and remove extra blank lines
- **CI/CD**:
  - Update Python CI workflow to use uv and new Python version
  - Update Python publish workflow for new version and steps
  - Change Pylint trigger to only pull requests
  - Update Python version matrix and pylint command
  - Modify pylint workflow for Python versions and setup

### Documentation
- Update README_zh.md project description
- Add Chinese README and document translations
- Add Python version and license badges to README
- Update README demo examples and usage instructions

## [v0.1.2] - 2025-12-17

### Added

#### Core Features
- **AI-powered MySQL assistant** with natural language support (English/中文)
- **Interactive TUI shell** with Rich formatting and modern terminal UI
- **Smart SQL detection**: Auto-detect SQL vs natural language input
- **SQL completer**: Intelligent SQL autocomplete with schema awareness
- **Query history**: Track and review SQL execution history via `/history` command
- **Vertical format support**: Use `\G` suffix for vertical table display

#### AI & LLM Integration
- **Multi-LLM support**: Qwen, OpenAI, DeepSeek, Anthropic, Gemini, OpenAI-compatible endpoints
- **Model management**: Switch between models via `/model` command
- **Memory system**: Schema learning and context persistence across sessions
- **Thinking mode**: Toggle transparent reasoning display with `Tab` key (when buffer is empty)
- **Instant SQL Result Explanation**: Press `Ctrl+E` after any SQL query to get AI-powered explanations
  - Dedicated explain agent for SQL result analysis
  - Automatic hint display after query execution (`💡 Ctrl+E: Explain result` or `💡 Ctrl+E: Explain error`)
  - Supports both successful queries and error messages
  - Concise, actionable explanations in user's configured language (English/中文)
  - Works seamlessly with query history and context injection

#### Diagnostic Tools (14+ tools)
- **Table Analysis**: TableStructure, TableIndex, TableStatus
- **Query Analysis**: MySQLExplain, SlowLog, ShowProcess
- **Transaction & Locking**: InnodbStatus, Transaction
- **Schema & Performance**: InformationSchema, PerformanceSchema, PerfStatistics
- **System**: KernelParameter, ReplicaStatus
- **DDL Execution**: DDLExecutor

#### Database Management
- **Database Schema Analysis** (`/research`): Comprehensive schema analysis reports with:
  - AI-powered schema review
  - Index optimization suggestions
  - Compliance checking against Alibaba Database Development Standards
  - Actionable recommendations
- **Performance Benchmarking** (`/benchmark`): AI-powered sysbench performance testing with:
  - Automated workflow (prepare → run → cleanup)
  - Comprehensive analysis reports
  - MySQL configuration analysis
  - InnoDB status analysis
  - Bottleneck identification and optimization recommendations
- **Connection management**: `/connect` and `/disconnect` commands for database connection management
- **Transaction safety**: Warnings for uncommitted transactions on exit

#### Extensibility
- **MCP Integration**: Extend capabilities by connecting to external MCP servers
  - Alibaba Cloud RDS OpenAPI for cloud RDS instance management
  - Monitoring and operations support
  - Custom MCP server integration

#### Security & Safety
- **Read-only mode by default**: DDL/DML operations require explicit confirmation
- **YOLO mode**: Auto-approve for trusted environments (toggle via `/yolo`)
- **SSL/TLS support**: Full SSL configuration options (CA, client cert, key, mode)
- **Transaction safety**: Warnings for uncommitted transactions on exit
- **Credential storage**: Secure storage in `~/.rdsai-cli/config.json` with proper OS permissions

#### Commands & Shortcuts
- `/setup`: Interactive wizard for LLM configuration
- `/init` and `/memory`: Knowledge management commands
- `/connect` and `/disconnect`: Database connection management
- `/model`: Model management (list/use/delete/info)
- `/research`: Database schema analysis
- `/benchmark`: Performance benchmarking
- `/mcp`: MCP server management
- `/yolo`: Toggle YOLO mode
- `/history`: View SQL query execution history
- `/clear` and `/compact`: Context management
- `/help`: Show help and current status
- `/version`: Show CLI version

#### Keyboard Shortcuts
- `Ctrl+E`: Explain SQL result
- `Ctrl+J`: Insert newline
- `Ctrl+C`: Exit/interrupt
- `Tab`: Toggle thinking mode (when buffer is empty)

### Security
- Read-only mode by default
- Explicit confirmation for all write operations
- Transaction safety warnings on exit
- Credential storage in `~/.rdsai-cli/config.json` with proper OS permissions

---
