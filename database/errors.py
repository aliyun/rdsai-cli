"""Database error handling and custom exceptions.

Simplified error handling with auto-classification based on MySQL error codes.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from utils.logging import logger


# Pre-compiled regex patterns for error message parsing
_RE_TABLE_NAME = re.compile(r"Table '(?:\w+\.)?(\w+)'")
_RE_COLUMN_NAME = re.compile(r"Unknown column '([^']+)'")
_RE_DATABASE_NAME = re.compile(r"Unknown database '([^']+)'")
_RE_USER_NAME = re.compile(r"Access denied for user '([^']+)'")
_RE_DUPLICATE_ENTRY = re.compile(r"Duplicate entry '([^']+')")


# ========== MySQL Error Code Groups ==========

CONNECTION_ERROR_CODES: frozenset[int] = frozenset(
    {
        1042,
        1043,
        1044,
        1045,  # Host/handshake/access errors
        2002,
        2003,
        2005,
        2006,
        2013,
        2026,
        2055,  # Connection errors
    }
)

TRANSACTION_ERROR_CODES: frozenset[int] = frozenset(
    {
        1205,
        1213,
        1223,
        1689,
        1792,
        3101,  # Lock/transaction errors
    }
)

SCHEMA_ERROR_CODES: frozenset[int] = frozenset(
    {
        1007,
        1008,
        1049,
        1050,
        1051,
        1054,  # DB/table/column errors
        1060,
        1061,
        1064,
        1146,
        1215,  # DDL errors
    }
)

ACCESS_DENIED_CODES: frozenset[int] = frozenset(
    {
        1044,
        1045,
        1142,
        1143,
        1227,
        1370,
        1698,  # Permission errors
    }
)

QUERY_ERROR_CODES: frozenset[int] = frozenset(
    {
        1048,
        1062,
        1064,
        1136,
        1216,
        1217,  # Data/constraint errors
        1242,
        1292,
        1364,
        1366,
        1452,
        1453,  # Value errors
    }
)


# ========== Error Severity ==========


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ========== Exception Classes ==========


class DatabaseError(Exception):
    """Base exception for database-related errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        error_code: str | None = None,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.error_code = error_code
        self.original_error = original_error
        self.context = context or {}

    def __str__(self) -> str:
        return self.message


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self,
        message: str,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            error_code="CONNECTION_FAILED",
            original_error=original_error,
            context={"host": host, "port": port, "user": user},
        )


class QueryError(DatabaseError):
    """Raised when SQL query execution fails."""

    def __init__(self, message: str, sql: str | None = None, original_error: Exception | None = None):
        super().__init__(
            message=message,
            error_code="QUERY_FAILED",
            original_error=original_error,
            context={"sql": sql} if sql else {},
        )


class TransactionError(DatabaseError):
    """Raised when transaction operation fails."""

    def __init__(self, message: str, operation: str | None = None, original_error: Exception | None = None):
        super().__init__(
            message=message,
            error_code="TRANSACTION_FAILED",
            original_error=original_error,
            context={"operation": operation} if operation else {},
        )


class SchemaError(DatabaseError):
    """Raised when schema operation fails."""

    def __init__(
        self,
        message: str,
        object_name: str | None = None,
        operation: str | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message=message,
            error_code="SCHEMA_ERROR",
            original_error=original_error,
            context={"object_name": object_name, "operation": operation},
        )


# ========== Error Classification ==========


def _extract_error_code(error: Exception) -> int | None:
    """Extract MySQL error code from exception."""
    if hasattr(error, "errno"):
        return error.errno
    if hasattr(error, "args") and error.args:
        first_arg = error.args[0]
        if isinstance(first_arg, int):
            return first_arg
    return None


def _classify_error_by_code(error_code: int | None) -> str | None:
    """Classify error type based on MySQL error code."""
    if error_code is None:
        return None
    if error_code in CONNECTION_ERROR_CODES or error_code in ACCESS_DENIED_CODES:
        return "connection"
    if error_code in TRANSACTION_ERROR_CODES:
        return "transaction"
    if error_code in SCHEMA_ERROR_CODES:
        return "schema"
    if error_code in QUERY_ERROR_CODES:
        return "query"
    return None


def handle_database_error(error: Exception, context: dict[str, Any] | None = None) -> DatabaseError:
    """
    Convert generic exception to appropriate DatabaseError.

    Uses MySQL error codes for precise classification, falls back to string matching.

    Args:
        error: The original exception
        context: Additional context information

    Returns:
        The converted DatabaseError
    """
    context = context or {}
    error_code = _extract_error_code(error)
    error_type = _classify_error_by_code(error_code)

    # Create appropriate error based on classification
    if error_type == "connection":
        db_error = ConnectionError(
            message=str(error),
            host=context.get("host"),
            port=context.get("port"),
            user=context.get("user"),
            original_error=error,
        )
    elif error_type == "transaction":
        db_error = TransactionError(message=str(error), operation=context.get("operation"), original_error=error)
    elif error_type == "schema":
        db_error = SchemaError(
            message=str(error),
            object_name=context.get("object_name") or context.get("table_name") or context.get("database"),
            operation=context.get("operation"),
            original_error=error,
        )
    elif error_type == "query" or context.get("sql"):
        db_error = QueryError(message=str(error), sql=context.get("sql"), original_error=error)
    else:
        # Fallback to string matching
        error_str = str(error).lower()
        if "connection" in error_str or "connect" in error_str:
            db_error = ConnectionError(
                message=str(error),
                host=context.get("host"),
                port=context.get("port"),
                user=context.get("user"),
                original_error=error,
            )
        elif "transaction" in error_str:
            db_error = TransactionError(message=str(error), operation=context.get("operation"), original_error=error)
        else:
            db_error = DatabaseError(message=str(error), original_error=error, context=context)

    # Store error code in context
    if error_code is not None:
        db_error.context["mysql_error_code"] = error_code

    # Log the error
    logger.error(f"Database error: {db_error.message}", error_type=db_error.__class__.__name__)

    return db_error


# ========== Error Formatting ==========

# Error code to brief message mapping
_ERROR_BRIEFS: dict[int, str] = {
    # Connection
    1045: "Access denied",
    2002: "Cannot connect",
    2003: "Cannot connect",
    2006: "Connection lost",
    2013: "Connection lost during query",
    # Transaction
    1205: "Lock wait timeout",
    1213: "Deadlock detected",
    # Schema
    1049: "Unknown database",
    1050: "Table already exists",
    1051: "Unknown table",
    1054: "Unknown column",
    1064: "SQL syntax error",
    1146: "Table doesn't exist",
    # Query
    1048: "Column cannot be null",
    1062: "Duplicate entry",
}


def format_error(error: DatabaseError) -> str:
    """Format database error for console display."""
    if isinstance(error, ConnectionError):
        ctx = error.context
        host = ctx.get("host", "unknown")
        port = ctx.get("port", "unknown")
        msg = f"Connection failed to {host}:{port}"
        if error.original_error:
            msg += f": {error.original_error}"
        return msg

    if isinstance(error, QueryError):
        msg = f"Query failed: {error.message}"
        sql = error.context.get("sql")
        if sql:
            sql_preview = sql[:100] + "..." if len(sql) > 100 else sql
            msg += f"\nSQL: {sql_preview}"
        return msg

    if isinstance(error, TransactionError):
        operation = error.context.get("operation", "unknown")
        return f"Transaction {operation} failed: {error.message}"

    if isinstance(error, SchemaError):
        obj_name = error.context.get("object_name", "unknown")
        operation = error.context.get("operation", "operation")
        return f"Schema {operation} failed for '{obj_name}': {error.message}"

    return f"Database error: {error.message}"


def get_error_brief(error: DatabaseError) -> str:
    """Generate a brief error summary for tool output."""
    error_code = error.context.get("mysql_error_code")

    if error_code and error_code in _ERROR_BRIEFS:
        brief = _ERROR_BRIEFS[error_code]
        error_msg = str(error.original_error) if error.original_error else error.message

        # Extract object names from common patterns
        if error_code == 1146:
            match = _RE_TABLE_NAME.search(error_msg)
            if match:
                return f"Table '{match.group(1)}' doesn't exist"
        elif error_code == 1054:
            match = _RE_COLUMN_NAME.search(error_msg)
            if match:
                return f"Unknown column '{match.group(1)}'"
        elif error_code == 1049:
            match = _RE_DATABASE_NAME.search(error_msg)
            if match:
                return f"Unknown database '{match.group(1)}'"
        elif error_code == 1045:
            match = _RE_USER_NAME.search(error_msg)
            if match:
                return f"Access denied for user '{match.group(1)}'"
        elif error_code == 1062:
            match = _RE_DUPLICATE_ENTRY.search(error_msg)
            if match:
                return f"Duplicate entry '{match.group(1)}'"
        return brief

    # Fallback to error type
    if isinstance(error, ConnectionError):
        return "Database connection error"
    if isinstance(error, QueryError):
        return "Query execution failed"
    if isinstance(error, TransactionError):
        return "Transaction error"
    if isinstance(error, SchemaError):
        return "Schema error"
    return "Database error"
