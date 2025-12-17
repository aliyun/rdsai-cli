# Changelog

All notable changes to RDSAI CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- PostgreSQL support (planned)
- Diagnostic report export (planned)

## [0.1.0] - 2025-12-12

### Added
- Initial public release
- **AI-powered MySQL assistant** with natural language support
- **14+ diagnostic tools**:
  - TableStructure, TableIndex, TableStatus
  - MySQLExplain, SlowLog, ShowProcess
  - InnodbStatus, Transaction
  - InformationSchema, PerformanceSchema, PerfStatistics
  - KernelParameter, ReplicaStatus
  - DDLExecutor
- **Multi-LLM support**: Qwen, OpenAI, DeepSeek, Anthropic, Gemini, OpenAI-compatible
- **Memory system**: Schema learning and context persistence
- **Interactive TUI shell** with Rich formatting
- **Smart SQL detection**: Auto-detect SQL vs natural language
- **Safety features**: Read-only default, DDL/DML confirmation
- **YOLO mode**: Auto-approve for trusted environments
- **SSL/TLS support**: Full SSL configuration options
- `/setup` wizard for LLM configuration
- `/model` command for model management
- `/init` and `/memory` for knowledge management
- Query history with `/history`

### Security
- Read-only mode by default
- Explicit confirmation for all write operations
- Transaction safety warnings on exit

---

[Unreleased]: https://github.com/rdsai/rdsai-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rdsai/rdsai-cli/releases/tag/v0.1.0
