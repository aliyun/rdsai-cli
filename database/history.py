"""SQL query history management."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any

from utils.logging import logger


@dataclass
class QueryHistoryEntry:
    """Represents a single query history entry."""

    timestamp: str
    sql: str
    status: str  # 'success' or 'error'
    execution_time: float | None = None
    affected_rows: int | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryHistoryEntry:
        """Create from dictionary representation."""
        return cls(**data)


class QueryHistory:
    """Manages SQL query execution history using deque for efficient operations."""

    def __init__(self, max_entries: int = 100):
        self._entries: deque[QueryHistoryEntry] = deque(maxlen=max_entries)
        self._max_entries = max_entries

    def record_query(
        self,
        sql: str,
        status: str = "success",
        execution_time: float | None = None,
        affected_rows: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record a query execution in history."""
        entry = QueryHistoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sql=sql.strip(),
            status=status,
            execution_time=execution_time,
            affected_rows=affected_rows,
            error_message=error_message,
        )
        self._entries.append(entry)
        logger.debug(f"Recorded query in history: {sql[:50]}...")

    def get_recent_queries(self, limit: int = 10) -> list[QueryHistoryEntry]:
        """Get recent query history entries."""
        if limit <= 0 or not self._entries:
            return []
        return list(self._entries)[-limit:]

    def get_recent_successful_queries(self, limit: int = 5) -> list[str]:
        """Get recent successful SQL queries."""
        successful_queries = []
        for entry in reversed(self._entries):
            if entry.status == "success":
                successful_queries.append(entry.sql)
                if len(successful_queries) >= limit:
                    break
        return successful_queries

    def get_all_entries(self) -> list[QueryHistoryEntry]:
        """Get all history entries as a list."""
        return list(self._entries)

    def clear_history(self) -> None:
        """Clear all query history."""
        self._entries.clear()
        logger.info("Query history cleared")

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about query history."""
        if not self._entries:
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "success_rate": 0.0,
                "average_execution_time": None,
            }

        successful_count = sum(1 for entry in self._entries if entry.status == "success")
        failed_count = len(self._entries) - successful_count

        timed_queries = [entry for entry in self._entries if entry.execution_time is not None]
        avg_time = None
        if timed_queries:
            avg_time = sum(entry.execution_time for entry in timed_queries) / len(timed_queries)

        return {
            "total_queries": len(self._entries),
            "successful_queries": successful_count,
            "failed_queries": failed_count,
            "success_rate": (successful_count / len(self._entries)) * 100,
            "average_execution_time": avg_time,
        }

    def find_queries_by_pattern(self, pattern: str, limit: int = 10) -> list[QueryHistoryEntry]:
        """Find queries matching a pattern (case-insensitive)."""
        pattern_lower = pattern.lower()
        matches = []
        for entry in reversed(self._entries):
            if pattern_lower in entry.sql.lower():
                matches.append(entry)
                if len(matches) >= limit:
                    break
        return matches

    def get_queries_by_status(self, status: str, limit: int = 10) -> list[QueryHistoryEntry]:
        """Get queries with specific status."""
        matches = []
        for entry in reversed(self._entries):
            if entry.status == status:
                matches.append(entry)
                if len(matches) >= limit:
                    break
        return matches

    def to_dict(self) -> dict[str, Any]:
        """Export history to dictionary format."""
        return {"max_entries": self._max_entries, "entries": [entry.to_dict() for entry in self._entries]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryHistory:
        """Import history from dictionary format."""
        max_entries = data.get("max_entries", 100)
        instance = cls(max_entries=max_entries)
        entries = data.get("entries", [])
        for entry_data in entries[-max_entries:]:
            entry = QueryHistoryEntry.from_dict(entry_data)
            instance._entries.append(entry)
        return instance
