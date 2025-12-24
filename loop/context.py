"""Context injection module for layered context management.

This module implements a layered context injection strategy:
- Layer 1: System Prompt (lightweight, always present) - managed by agent.py
- Layer 2: Context Injection (runtime, injected into user messages) - managed here
- Layer 3: On-Demand Retrieval (via tools like TableStructure, TableIndex)

Context Types:
- DATABASE: Database connection information (host, port, user, current database)
- QUERY: Recent SQL execution results

Injection Strategies:
- DATABASE: Full connection info first time, reminder afterwards
- QUERY: Content-hash based deduplication (skip if unchanged)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from utils.logging import logger


# Reminder template for database context (injected after first turn)
DATABASE_REMINDER = (
    "<database_context>You are connected to a MySQL database. "
    "Refer to earlier messages for connection details.</database_context>"
)


class ContextType(Enum):
    """Supported context types with implicit priority ordering.

    Lower enum value = higher priority.
    """

    DATABASE = auto()  # Database connection info (highest priority in Layer 2)
    QUERY = auto()  # Recent SQL query results


# Default XML-like tags for each context type
CONTEXT_TAGS: dict[ContextType, str] = {
    ContextType.DATABASE: "database_context",
    ContextType.QUERY: "query_context",
}


@dataclass
class ContextEntry:
    """A single context entry with metadata."""

    type: ContextType
    content: str
    tag: Optional[str] = None  # Custom tag, uses default if None
    priority: int = 0  # Higher = more important (for custom ordering)

    def __post_init__(self):
        if self.tag is None:
            self.tag = CONTEXT_TAGS.get(self.type, "context")

    def format(self) -> str:
        """Format as tagged XML-like block."""
        return f"<{self.tag}>\n{self.content}\n</{self.tag}>"


class SessionState:
    """Tracks session-level state for context injection.

    This tracks which context types have been injected in the current
    session to avoid redundant injections in multi-turn conversations.
    """

    def __init__(self):
        self._injected_types: set[ContextType] = set()
        self._cache: dict[ContextType, str] = {}
        self._content_hashes: dict[ContextType, str] = {}  # For deduplication

    def mark_injected(self, context_type: ContextType) -> None:
        """Mark a context type as injected in this session."""
        self._injected_types.add(context_type)

    def is_injected(self, context_type: ContextType) -> bool:
        """Check if context type was already injected."""
        return context_type in self._injected_types

    def cache_content(self, context_type: ContextType, content: str) -> None:
        """Cache content for a context type."""
        self._cache[context_type] = content

    def get_cached(self, context_type: ContextType) -> Optional[str]:
        """Get cached content for a context type."""
        return self._cache.get(context_type)

    def invalidate_cache(self, context_type: Optional[ContextType] = None) -> None:
        """Invalidate cache for a specific type or all types."""
        if context_type is None:
            self._cache.clear()
        elif context_type in self._cache:
            del self._cache[context_type]

    def is_content_changed(self, context_type: ContextType, content: str) -> bool:
        """Check if content has changed since last injection.

        Uses MD5 hash for efficient comparison of potentially large content.

        Args:
            context_type: The type of context
            content: The new content to check

        Returns:
            True if content is different from last injection, False otherwise
        """
        new_hash = hashlib.md5(content.encode()).hexdigest()
        old_hash = self._content_hashes.get(context_type)

        if new_hash == old_hash:
            return False  # Content unchanged

        # Update hash for next comparison
        self._content_hashes[context_type] = new_hash
        return True

    def clear_content_hash(self, context_type: ContextType) -> None:
        """Clear the content hash for a context type."""
        self._content_hashes.pop(context_type, None)

    def reset(self) -> None:
        """Reset all session state."""
        self._injected_types.clear()
        self._cache.clear()
        self._content_hashes.clear()


@dataclass
class InjectedContext:
    """Container for formatted context ready for injection.

    This is the output of ContextManager.build(), containing
    the final formatted context to be injected into user messages.
    """

    parts: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if there's any context to inject."""
        return len(self.parts) == 0

    def format(self) -> str:
        """Format all context parts as a single string."""
        if self.is_empty():
            return ""
        return "\n\n".join(self.parts)

    def wrap_user_input(self, user_input: str) -> str:
        """Wrap user input with injected context.

        Args:
            user_input: The original user input

        Returns:
            User input prefixed with context (if any)
        """
        context_str = self.format()
        if not context_str:
            return user_input
        return f"{context_str}\n\n{user_input}"


class ContextManager:
    """Full-featured context manager for layered context injection.

    This manager handles:
    - Multiple context types with priorities
    - Session-aware injection (avoids redundant database connection info injection)
    - Caching for efficiency

    Usage:
        manager = ContextManager()

        # Database connection info is auto-loaded when build() is called
        # You can also manually set it:
        manager.set_database_context(connection_info_string)

        # Update per-turn context
        manager.set_query_context(query_result)

        # Build and inject
        context = manager.build()
        message = context.wrap_user_input(user_input)

        # On session reset
        manager.reset_session()
    """

    def __init__(self):
        """Initialize the context manager."""
        self._entries: dict[ContextType, ContextEntry] = {}
        self._session = SessionState()

    # =========================================================================
    # Layer Management - Add/Update/Remove/Get
    # =========================================================================

    def add(
        self,
        context_type: ContextType,
        content: str,
        *,
        tag: Optional[str] = None,
        priority: int = 0,
    ) -> ContextManager:
        """Add or update a context entry.

        Args:
            context_type: The type of context
            content: The content to inject
            tag: Optional custom XML tag
            priority: Priority for ordering (higher = more important)

        Returns:
            Self for method chaining
        """
        if not content or not content.strip():
            return self

        entry = ContextEntry(
            type=context_type,
            content=content.strip(),
            tag=tag,
            priority=priority,
        )

        self._entries[context_type] = entry
        logger.debug("Context added: type={type}", type=context_type.name)
        return self

    def remove(self, context_type: ContextType) -> bool:
        """Remove a context entry.

        Args:
            context_type: The type of context to remove

        Returns:
            True if removed, False if not found
        """
        if context_type in self._entries:
            del self._entries[context_type]
            logger.debug("Context removed: type={type}", type=context_type.name)
            return True
        return False

    def get(self, context_type: ContextType) -> Optional[ContextEntry]:
        """Get a context entry.

        Args:
            context_type: The type of context to get

        Returns:
            The context entry or None
        """
        return self._entries.get(context_type)

    def has(self, context_type: ContextType) -> bool:
        """Check if a context type exists."""
        return context_type in self._entries

    def clear(self) -> None:
        """Clear all context entries."""
        self._entries.clear()
        logger.debug("All context cleared")

    # =========================================================================
    # Convenience Methods for Common Context Types
    # =========================================================================

    def set_database_context(self, content: str) -> ContextManager:
        """Set database connection context.

        This contains connection information (host, port, user, current database).
        Typically auto-loaded from DatabaseService, but can be manually set.
        """
        return self.add(ContextType.DATABASE, content)

    def set_query_context(self, content: str) -> ContextManager:
        """Set query context (recent SQL results).

        This is updated per-turn based on user's SQL executions.
        """
        return self.add(ContextType.QUERY, content)

    # =========================================================================
    # Session Management
    # =========================================================================

    def reset_session(self) -> None:
        """Reset session state.

        Call this when:
        - User executes /clear command
        - Conversation is restarted
        """
        self._session.reset()
        self._entries.clear()
        logger.debug("Session reset")

    @property
    def is_database_injected(self) -> bool:
        """Check if database context has been injected in this session."""
        return self._session.is_injected(ContextType.DATABASE)

    # =========================================================================
    # Build & Format
    # =========================================================================

    def build(self) -> InjectedContext:
        """Build the final InjectedContext for injection.

        This method:
        1. Autoloads database connection info if not already present
        2. Applies session-aware injection logic:
           - DATABASE: Full connection info first time, reminder afterwards
           - QUERY: Skip if content unchanged (deduplication)
        3. Returns formatted context

        Returns:
            InjectedContext ready for injection
        """
        # Autoload database connection info if not set and not yet injected
        # Also check if connection info has changed (e.g., user switched database)
        current_conn_info = _load_database_connection_info()

        if current_conn_info:
            # Check if connection info has changed
            cached_info = self._session.get_cached(ContextType.DATABASE)
            if cached_info and cached_info != current_conn_info:
                # Connection info changed - clear cache and reset injection flag
                logger.debug("Database connection info changed, resetting injection state")
                self._session.invalidate_cache(ContextType.DATABASE)
                self._session.clear_content_hash(ContextType.DATABASE)
                # Reset injection flag to allow re-injection of full info
                if ContextType.DATABASE in self._session._injected_types:
                    self._session._injected_types.remove(ContextType.DATABASE)
                # Remove existing entry to force reload
                self.remove(ContextType.DATABASE)

            # Load if not set
            if not self.has(ContextType.DATABASE):
                self.set_database_context(current_conn_info)
                # Cache for future use
                self._session.cache_content(ContextType.DATABASE, current_conn_info)
                logger.debug("Database connection info loaded and cached")

        # Build output
        parts: list[str] = []

        # Sort by priority (higher first) and type order
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda x: (-x[1].priority, x[0].value),
        )

        for context_type, entry in sorted_entries:
            # DATABASE: Full connection info first time, reminder afterwards
            if context_type == ContextType.DATABASE:
                if self._session.is_injected(ContextType.DATABASE):
                    # Already injected - add lightweight reminder instead
                    parts.append(DATABASE_REMINDER)
                    logger.debug("Database connection info reminder injected")
                    continue
                else:
                    # First injection - mark as injected
                    self._session.mark_injected(ContextType.DATABASE)
                    logger.debug("Database connection info injected (first time in session)")

            # QUERY: Skip if content unchanged (deduplication)
            elif context_type == ContextType.QUERY:
                if not self._session.is_content_changed(ContextType.QUERY, entry.content):
                    # Content unchanged - skip injection
                    continue

            parts.append(entry.format())

        return InjectedContext(parts=parts)

    def wrap_user_input(self, user_input: str) -> str:
        """Convenience method: build context and wrap user input.

        Args:
            user_input: The original user input

        Returns:
            User input prefixed with context
        """
        return self.build().wrap_user_input(user_input)


def _load_database_connection_info() -> Optional[str]:
    """Load current database connection information.

    Returns:
        Formatted connection info string if connected, None otherwise.
    """
    from database.service import get_service

    db_service = get_service()
    if not db_service or not db_service.is_connected():
        return None

    conn_info = db_service.get_connection_info()

    # Format connection information
    parts = []
    parts.append(f"Host: {conn_info.get('host', 'N/A')}")
    parts.append(f"Port: {conn_info.get('port', 'N/A')}")
    parts.append(f"User: {conn_info.get('user', 'N/A')}")

    database = conn_info.get("database")
    if database:
        parts.append(f"Current Database: {database}")
    else:
        parts.append("Current Database: (none selected)")

    engine = conn_info.get("engine", "mysql")
    parts.append(f"Engine: {engine}")

    return "\n".join(parts)
