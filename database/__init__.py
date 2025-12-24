"""Database services package.

Simplified architecture with clear module responsibilities:
- types.py: Pure type definitions
- errors.py: Exception classes and error handling
- client.py: Database client abstraction (DatabaseClient, MySQLClient)
- service.py: Core service and global state management
- history.py: Query history management
"""

# Types
from .types import (
    ConnectionConfig,
    ConnectionContext,
    ConnectionStatus,
    LastQueryContext,
    QueryResult,
    QueryStatus,
    QueryType,
    RESULT_SET_QUERY_TYPES,
    SchemaInfo,
)

# Errors
from .errors import (
    ConnectionError,
    DatabaseError,
    ErrorSeverity,
    format_error,
    get_error_brief,
    handle_database_error,
    QueryError,
    SchemaError,
    TransactionError,
)

# Client
from .client import (
    DatabaseClient,
    DatabaseClientFactory,
    MySQLClient,
    TransactionState,
    validate_identifier,
)

# Service (main entry point)
from .service import (
    # Service class
    DatabaseService,
    # Global state management
    clear_service,
    get_current_database,
    get_database_client,
    get_database_service,
    get_service,
    set_database_service,
    set_service,
    # Factory functions
    create_connection_context,
    create_database_connection_context,
    create_database_service,
    # Helper functions
    extract_first_value,
    extract_single_column,
    format_query_context_for_agent,
)

# History
from .history import (
    QueryHistory,
    QueryHistoryEntry,
)

# Schema exploration
from .schema import (
    ColumnInfo,
    DatabaseExplorer,
    DatabaseSchemaSnapshot,
    DatabaseStatistics,
    ForeignKeyInfo,
    IndexInfo,
    TableExploreProgress,
    TableInfo,
    format_snapshot_for_research,
)


__all__ = [
    # Types
    "ConnectionConfig",
    "ConnectionContext",
    "ConnectionStatus",
    "LastQueryContext",
    "QueryResult",
    "QueryStatus",
    "QueryType",
    "RESULT_SET_QUERY_TYPES",
    "SchemaInfo",
    # Errors
    "ConnectionError",
    "DatabaseError",
    "ErrorSeverity",
    "format_error",
    "get_error_brief",
    "handle_database_error",
    "QueryError",
    "SchemaError",
    "TransactionError",
    # Client
    "DatabaseClient",
    "DatabaseClientFactory",
    "MySQLClient",
    "TransactionState",
    "validate_identifier",
    # Service
    "DatabaseService",
    "clear_service",
    "get_current_database",
    "get_database_client",
    "get_database_service",
    "get_service",
    "set_database_service",
    "set_service",
    "create_connection_context",
    "create_database_connection_context",
    "create_database_service",
    "extract_first_value",
    "extract_single_column",
    "format_query_context_for_agent",
    # History
    "QueryHistory",
    "QueryHistoryEntry",
    # Schema exploration
    "ColumnInfo",
    "DatabaseExplorer",
    "DatabaseSchemaSnapshot",
    "DatabaseStatistics",
    "ForeignKeyInfo",
    "IndexInfo",
    "TableExploreProgress",
    "TableInfo",
    "format_snapshot_for_research",
]
