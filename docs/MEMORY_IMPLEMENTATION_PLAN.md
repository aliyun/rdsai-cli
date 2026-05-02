# Memory System Implementation Plan

> **Author**: rdsai-cli PM + Architect  
> **Date**: 2026-05-02  
> **Status**: Ready for Implementation  

---

## Overview

Add cross-session memory capability to rdsai-cli. The agent can remember user preferences, historical decisions, and environment information, and automatically inject relevant memories into subsequent conversations via semantic retrieval.

### Design Constraints

- **No LangGraph graph structure changes** — inject via Runtime + toolset + ContextManager extension points
- **Storage**: SQLite (file-based, zero infra)
- **Embedding**: DashScope `text-embedding-v3` via existing `llm/embedding.py` (`EmbeddingService`)
- **Memory limit**: 1000 entries max
- **Retrieval**: `top_k=3` default
- **Tool files must NOT use** `from __future__ import annotations` (runtime annotation introspection for dependency injection)

### Architecture Diagram

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  NeoLoop    │────▶│ ContextManager   │────▶│  HumanMessage   │
│  .run()     │     │  + MEMORY type   │     │  (wrapped)      │
└──────┬──────┘     └──────────────────┘     └─────────────────┘
       │
       │ retrieves
       ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│MemoryManager│────▶│  SQLiteStore     │────▶│ memories table  │
│  .search()  │     │  (FTS + BLOB)    │     │ + FTS5 index    │
└──────┬──────┘     └────────┬─────────┘     └─────────────────┘
       │                     │
       │                     │ text-embedding-v3
       ▼                     ▼
┌─────────────┐     ┌──────────────────┐
│  Tools      │     │ EmbeddingService │
│ save/search │     │ (llm/embedding)  │
│ delete      │     └──────────────────┘
└─────────────┘
```

---

## Phase 1: Data Models + Storage Layer

**Files**: `memory/models.py`, `memory/store.py`, `memory/__init__.py`

### Phase 1.1: `memory/models.py`

Pydantic data models for memory entries, categories, and creation requests.

```python
"""Memory system data models."""

from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """Memory categories for organizing stored memories."""

    PREFERENCE = "preference"       # User preferences (language, style, etc.)
    DECISION = "decision"           # Historical decisions and their rationale
    ENVIRONMENT = "environment"     # Environment info (DB schema, infra details)
    FACT = "fact"                   # Domain facts learned during conversation
    NOTE = "note"                   # General notes


class MemoryEntry(BaseModel):
    """A single memory entry stored in the system."""

    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""  # ISO format, set by store
    updated_at: str = ""  # ISO format, set by store
    embedding: list[float] = Field(default_factory=list, repr=False)

    def format_for_context(self) -> str:
        """Format this memory for injection into agent context."""
        tags_str = f" [{', '.join(self.tags)}]" if self.tags else ""
        return f"[{self.category.value}{tags_str}] {self.content}"


class CreateMemoryRequest(BaseModel):
    """Request to create a new memory entry."""

    category: MemoryCategory
    content: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
```

### Phase 1.2: `memory/store.py`

SQLite storage layer with FTS5 full-text search index. Embeddings stored as JSON BLOB.

**Integration point**: Uses `get_share_dir()` from `config.base` to store the SQLite file at `~/.rdsai-cli/memories.db`.

```python
"""SQLite storage layer for the memory system.

Stores memories in a SQLite database with:
- A 'memories' table with embedding vectors stored as JSON BLOB
- An FTS5 virtual table for keyword search
- Automatic index management for category and tags
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.base import get_share_dir
from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from utils.logging import logger

# Limits
MAX_MEMORIES = 1000
DEFAULT_TOP_K = 3


class MemoryStore:
    """SQLite-backed memory store with FTS keyword search."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = get_share_dir() / "memories.db"
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                embedding BLOB,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                content='memories',
                content_rowid='rowid'
            );
        """)
        # Sync FTS with existing rows
        conn.execute("""
            INSERT OR IGNORE INTO memories_fts(rowid, content)
            SELECT rowid, content FROM memories
            WHERE rowid NOT IN (SELECT rowid FROM memories_fts)
        """)
        conn.commit()
        logger.info("Memory store initialized at {path}", path=self._db_path)

    def save(self, entry: MemoryEntry) -> MemoryEntry:
        """Save a memory entry to the store.

        Enforces MAX_MEMORIES limit by deleting oldest when exceeded.
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()

        if entry.created_at:
            # Update existing
            conn.execute(
                """UPDATE memories SET category=?, content=?, tags=?, embedding=?, updated_at=?
                   WHERE id=?""",
                (
                    entry.category.value,
                    entry.content,
                    json.dumps(entry.tags),
                    json.dumps(entry.embedding).encode("utf-8") if entry.embedding else None,
                    now,
                    entry.id,
                ),
            )
            logger.info("Memory updated: id={id}", id=entry.id)
        else:
            # Enforce limit
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if count >= MAX_MEMORIES:
                oldest = conn.execute(
                    "SELECT id FROM memories ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
                if oldest:
                    self._delete_by_id(conn, oldest["id"])
                    logger.info("Memory store full, deleted oldest entry: {id}", id=oldest["id"])

            entry.created_at = now
            entry.updated_at = now

            conn.execute(
                """INSERT INTO memories (id, category, content, tags, embedding, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.id,
                    entry.category.value,
                    entry.content,
                    json.dumps(entry.tags),
                    json.dumps(entry.embedding).encode("utf-8") if entry.embedding else None,
                    entry.created_at,
                    entry.updated_at,
                ),
            )
            logger.info("Memory saved: id={id}, category={cat}", id=entry.id, cat=entry.category.value)

        conn.commit()
        return entry

    def search(
        self,
        query: str,
        *,
        category: Optional[MemoryCategory] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[MemoryEntry]:
        """Search memories using FTS keyword matching.

        Returns results ordered by FTS rank (relevance).
        """
        conn = self._get_conn()
        if not query.strip():
            return []

        # Build FTS query
        fts_query = self._build_fts_query(query)

        sql = """
            SELECT m.id, m.category, m.content, m.tags, m.embedding, m.created_at, m.updated_at
            FROM memories m
            JOIN memories_fts f ON m.rowid = f.rowid
            WHERE memories_fts MATCH ?
        """
        params: list = [fts_query]

        if category:
            sql += " AND m.category = ?"
            params.append(category.value)

        sql += " ORDER BY f.rank LIMIT ?"
        params.append(top_k)

        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning("FTS search failed, falling back to LIKE: {error}", error=e)
            return self._fallback_search(query, category, top_k)

        return [self._row_to_entry(row) for row in rows]

    def _build_fts_query(self, query: str) -> str:
        """Build a safe FTS5 query string from user input."""
        # Escape FTS special characters
        cleaned = query.replace('"', '""')
        # Wrap in double quotes for phrase matching
        return f'"{cleaned}"'

    def _fallback_search(
        self,
        query: str,
        category: Optional[MemoryCategory],
        top_k: int,
    ) -> list[MemoryEntry]:
        """Fallback LIKE search when FTS fails."""
        conn = self._get_conn()
        sql = "SELECT id, category, content, tags, embedding, created_at, updated_at FROM memories WHERE content LIKE ?"
        params: list = [f"%{query}%"]

        if category:
            sql += " AND category = ?"
            params.append(category.value)

        sql += " LIMIT ?"
        params.append(top_k)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search_by_embedding(
        self,
        query_embedding: list[float],
        *,
        category: Optional[MemoryCategory] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[MemoryEntry]:
        """Search memories by cosine similarity to query embedding.

        Uses SQLite for retrieval + Python for cosine scoring.
        """
        import math

        conn = self._get_conn()
        sql = "SELECT id, category, content, tags, embedding, created_at, updated_at FROM memories"
        params: list = []

        if category:
            sql += " WHERE category = ?"
            params.append(category.value)

        rows = conn.execute(sql, params).fetchall()

        if not rows:
            return []

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored: list[tuple[float, MemoryEntry]] = []
        for row in rows:
            entry = self._row_to_entry(row)
            if entry.embedding:
                sim = cosine_sim(query_embedding, entry.embedding)
                scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry by ID."""
        conn = self._get_conn()
        found = self._delete_by_id(conn, memory_id)
        conn.commit()
        if found:
            logger.info("Memory deleted: id={id}", id=memory_id)
        return found

    def _delete_by_id(self, conn: sqlite3.Connection, memory_id: str) -> bool:
        """Delete by id, also removing from FTS index."""
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        if cursor.rowcount > 0:
            # FTS5 handles deletion via content= trigger
            return True
        return False

    def list_all(
        self,
        *,
        category: Optional[MemoryCategory] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        """List all memories, optionally filtered by category."""
        conn = self._get_conn()
        sql = "SELECT id, category, content, tags, embedding, created_at, updated_at FROM memories"
        params: list = []

        if category:
            sql += " WHERE category = ?"
            params.append(category.value)

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def count(self, *, category: Optional[MemoryCategory] = None) -> int:
        """Count total memories."""
        conn = self._get_conn()
        sql = "SELECT COUNT(*) FROM memories"
        params: list = []
        if category:
            sql += " WHERE category = ?"
            params.append(category.value)
        return conn.execute(sql, params).fetchone()[0]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        """Convert a database row to a MemoryEntry."""
        embedding_blob = row["embedding"]
        embedding: list[float] = []
        if embedding_blob:
            try:
                embedding = json.loads(embedding_blob.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                embedding = []

        return MemoryEntry(
            id=row["id"],
            category=MemoryCategory(row["category"]),
            content=row["content"],
            tags=json.loads(row["tags"]),
            embedding=embedding,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
```

### Phase 1.3: `memory/__init__.py`

```python
"""Memory system for cross-session agent memory."""

from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from memory.store import MemoryStore

__all__ = [
    "CreateMemoryRequest",
    "MemoryCategory",
    "MemoryEntry",
    "MemoryStore",
]
```

---

## Phase 2: Embedding Wrapper

**File**: `memory/embedding.py`

This module wraps the existing `llm.embedding.EmbeddingService` to provide a higher-level interface for the memory system. It reads embedding config from the application config.

**Integration point**: Reuses the existing `EmbeddingService.from_config()` which reads `default_embedding_model`, `embedding_models`, `embedding_providers` from the `Config` object.

```python
"""Embedding wrapper for memory system.

Provides a simplified interface over llm.embedding.EmbeddingService
for generating and comparing memory embeddings.
"""

from typing import Optional

from config import Config
from llm.embedding import EmbeddingService
from utils.logging import logger


class MemoryEmbedding:
    """High-level embedding interface for the memory system.

    Wraps EmbeddingService to handle memory-specific embedding operations.
    Falls back gracefully when no embedding model is configured.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._service: EmbeddingService | None = EmbeddingService.from_config(config)
        if self._service is None:
            logger.warning(
                "No embedding model configured. Memory semantic search will be disabled. "
                "Configure embedding_models in ~/.rdsai-cli/config.json."
            )

    @property
    def is_available(self) -> bool:
        """Whether embedding service is configured and available."""
        return self._service is not None

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector.
            Returns empty list if embedding service is not available.

        Raises:
            ValueError: If embedding generation fails.
        """
        if self._service is None:
            logger.debug("Embedding service not available, returning empty embedding")
            return []
        return await self._service.generate_embedding(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
            Returns empty list if embedding service is not available.
        """
        if self._service is None:
            return []
        return await self._service.generate_embeddings_batch(texts)
```

---

## Phase 3: Memory Manager

**File**: `memory/manager.py`

The central orchestrator that combines store + embedding into a cohesive API.

```python
"""Memory manager — orchestrates storage, embedding, and retrieval."""

from typing import Optional

from memory.embedding import MemoryEmbedding
from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from memory.store import DEFAULT_TOP_K, MAX_MEMORIES, MemoryStore
from utils.logging import logger


class MemoryManager:
    """Central memory management API.

    Coordinates embedding generation, storage, and retrieval.
    Provides the high-level interface used by tools and the agent loop.
    """

    def __init__(self, store: MemoryStore, embedding: MemoryEmbedding) -> None:
        self._store = store
        self._embedding = embedding

    async def save(self, request: CreateMemoryRequest) -> MemoryEntry:
        """Save a new memory entry.

        Automatically generates embedding if the embedding service is available.

        Args:
            request: The memory creation request.

        Returns:
            The saved MemoryEntry with generated ID and timestamps.
        """
        entry = MemoryEntry(
            category=request.category,
            content=request.content,
            tags=request.tags,
        )

        # Generate embedding if available
        if self._embedding.is_available:
            try:
                entry.embedding = await self._embedding.embed_text(request.content)
            except Exception as e:
                logger.warning("Failed to generate embedding for memory: {error}", error=e)
                entry.embedding = []

        return self._store.save(entry)

    async def search(
        self,
        query: str,
        *,
        category: Optional[MemoryCategory] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[MemoryEntry]:
        """Search memories with semantic retrieval.

        If embedding service is available, performs hybrid search:
        1. FTS keyword search to get candidate set (top_k * 3)
        2. Embedding-based re-ranking on candidates
        3. Return top_k results

        Otherwise, falls back to pure FTS keyword search.

        Args:
            query: The search query.
            category: Optional category filter.
            top_k: Number of results to return.

        Returns:
            List of matching MemoryEntry objects.
        """
        if not query.strip():
            return []

        # Pure FTS search (no embedding service)
        if not self._embedding.is_available:
            return self._store.search(query, category=category, top_k=top_k)

        # Hybrid search: FTS candidates + embedding re-rank
        try:
            query_embedding = await self._embedding.embed_text(query)
        except Exception as e:
            logger.warning("Failed to generate query embedding: {error}", error=e)
            return self._store.search(query, category=category, top_k=top_k)

        # Get FTS candidates
        candidates = self._store.search(query, category=category, top_k=top_k * 3)

        if not candidates:
            # FTS found nothing, try embedding search on all
            return self._store.search_by_embedding(query_embedding, category=category, top_k=top_k)

        # Score candidates with embedding
        if query_embedding:
            import math

            def cosine_sim(a: list[float], b: list[float]) -> float:
                dot = sum(x * y for x, y in zip(a, b))
                norm_a = math.sqrt(sum(x * x for x in a))
                norm_b = math.sqrt(sum(x * x for x in b))
                if norm_a == 0 or norm_b == 0:
                    return 0.0
                return dot / (norm_a * norm_b)

            scored = []
            for entry in candidates:
                if entry.embedding:
                    sim = cosine_sim(query_embedding, entry.embedding)
                    scored.append((sim, entry))
                else:
                    scored.append((0.0, entry))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored[:top_k]]

        return candidates[:top_k]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        return self._store.delete(memory_id)

    def list_all(
        self,
        *,
        category: Optional[MemoryCategory] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        """List all memories."""
        return self._store.list_all(category=category, limit=limit, offset=offset)

    def count(self, *, category: Optional[MemoryCategory] = None) -> int:
        """Count total memories."""
        return self._store.count(category=category)

    def format_for_context(self, memories: list[MemoryEntry]) -> str:
        """Format memories for injection into agent context.

        Args:
            memories: List of MemoryEntry objects to format.

        Returns:
            Formatted string suitable for context injection, or empty string.
        """
        if not memories:
            return ""

        lines = ["<memory_context>Relevant memories from previous sessions:"]
        for i, mem in enumerate(memories, 1):
            lines.append(f"  {i}. {mem.format_for_context()}")
        lines.append("</memory_context>")
        return "\n".join(lines)

    @property
    def max_memories(self) -> int:
        """Maximum number of memories allowed."""
        return MAX_MEMORIES

    def close(self) -> None:
        """Close resources."""
        self._store.close()
```

---

## Phase 4: Runtime Extension + App Initialization

### Phase 4.1: `loop/runtime.py` — Add `memory_manager` field

**Integration point**: The Runtime dataclass is `@dataclass(slots=True, kw_only=True)` (not frozen). We add an optional `memory_manager` field with a default of `None`.

```python
"""Agent runtime configuration and initialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from config import Config
from llm.llm import LLM
from config import Session

if TYPE_CHECKING:
    from memory.manager import MemoryManager
    from tools.mcp.config import MCPConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinSystemPromptArgs:
    """Builtin system prompt arguments."""

    CLI_NOW: str
    CLI_LANGUAGE: str


@dataclass(slots=True, kw_only=True)
class Runtime:
    """Agent runtime configuration.

    This is a simplified runtime that only contains configuration and LLM.
    State management is handled by LangGraph's checkpointer.
    """

    config: Config
    llm: LLM | None
    session: Session
    builtin_args: BuiltinSystemPromptArgs
    mcp_config: MCPConfig | None = field(default=None)
    yolo: bool = field(default=False)
    memory_manager: MemoryManager | None = field(default=None)

    def set_llm(self, llm: LLM | None) -> None:
        """Switch to a different LLM at runtime.

        Args:
            llm: The new LLM instance to use.
        """
        self.llm = llm

    def set_yolo(self, yolo: bool) -> None:
        """Set the yolo mode (auto-approve all actions).

        Args:
            yolo: Whether to auto-approve all tool executions.
        """
        self.yolo = yolo

    @staticmethod
    async def create(
        config: Config,
        llm: LLM | None,
        session: Session,
        mcp_config: MCPConfig | None = None,
        yolo: bool = False,
    ) -> Runtime:
        """Create a new runtime instance.

        Args:
            config: Application configuration.
            llm: Language model instance (optional).
            session: Current session.
            mcp_config: MCP configuration (optional).
            yolo: Whether to auto-approve all tool executions (optional).

        Returns:
            Initialized Runtime instance.
        """
        # Initialize memory manager
        memory_manager = _create_memory_manager(config)

        return Runtime(
            config=config,
            llm=llm,
            session=session,
            mcp_config=mcp_config,
            builtin_args=BuiltinSystemPromptArgs(
                CLI_NOW=datetime.now().astimezone().isoformat(),
                CLI_LANGUAGE=config.language,
            ),
            yolo=yolo,
            memory_manager=memory_manager,
        )


def _create_memory_manager(config: Config) -> "MemoryManager | None":
    """Create a MemoryManager if embedding is configured, otherwise None.

    Memory is optional — if no embedding model is configured, the manager
    is not created and memory tools will report that memory is unavailable.
    """
    from config.app import Config

    # Check if embedding is configured
    if not config.default_embedding_model:
        return None

    try:
        from memory.embedding import MemoryEmbedding
        from memory.manager import MemoryManager
        from memory.store import MemoryStore

        store = MemoryStore()
        embedding = MemoryEmbedding(config)
        return MemoryManager(store, embedding)
    except Exception as e:
        from utils.logging import logger

        logger.warning("Failed to initialize memory manager: {error}", error=e)
        return None
```

### Phase 4.2: `app.py` — No code changes needed

The Runtime is already initialized via `Runtime.create()` in `app.py` L113. Since we added memory_manager initialization inside `Runtime.create()`, no changes to `app.py` are needed. The MemoryManager flows through Runtime → Agent → tools via dependency injection.

**However**, we need to add cleanup in `Application.__aexit__`:

```python
# In app.py __aexit__, add after MCP pool shutdown:

# Cleanup memory store
if self._runtime.memory_manager:
    self._runtime.memory_manager.close()
```

### Phase 4.3: `loop/agent.py` — Register memory_manager in tool dependencies

**Integration point**: In `load_agent()`, the `tool_deps` dict is used for dependency injection. Add `MemoryManager` to this dict.

```python
# In loop/agent.py load_agent(), add to tool_deps:
from memory.manager import MemoryManager

tool_deps = {
    ResolvedAgentSpec: agent_spec,
    Runtime: runtime,
    Config: runtime.config,
    BuiltinSystemPromptArgs: runtime.builtin_args,
    Session: runtime.session,
    MemoryManager: runtime.memory_manager,  # <-- NEW
}
```

This enables tools to declare `MemoryManager` as a constructor parameter and receive it via DI.

---

## Phase 5: Context Extension + NeoLoop Injection

### Phase 5.1: `loop/context.py` — Add MEMORY ContextType

**Integration point**: Add `MEMORY` to the `ContextType` enum, `CONTEXT_TAGS` dict, and a convenience method on `ContextManager`.

```python
# In loop/context.py, modify:

class ContextType(Enum):
    """Supported context types with implicit priority ordering.

    Lower enum value = higher priority.
    """

    DATABASE = auto()  # Database connection info (highest priority in Layer 2)
    QUERY = auto()  # Recent SQL query results
    MEMORY = auto()  # Retrieved memories from previous sessions


# Update CONTEXT_TAGS:
CONTEXT_TAGS: dict[ContextType, str] = {
    ContextType.DATABASE: "database_context",
    ContextType.QUERY: "query_context",
    ContextType.MEMORY: "memory_context",
}


# Add convenience method to ContextManager class:
def set_memory_context(self, content: str) -> ContextManager:
    """Set memory context (retrieved memories from previous sessions).

    This is updated per-turn based on semantic search results.
    """
    return self.add(ContextType.MEMORY, content)
```

### Phase 5.2: `loop/neoloop.py` — Inject memories into HumanMessage

**Integration point**: In `NeoLoop.run()` around L196-214, after building the query context but before wrapping user input, retrieve memories and inject them.

```python
# In NeoLoop.run(), after L204 (set_query_context), add:

# Layer 2b: Memory Context (cross-session memories)
# Retrieves relevant memories via semantic search and injects them
if self._runtime.memory_manager:
    try:
        # Extract search query from user input
        search_query = self._extract_memory_query(user_input)
        memories = await self._runtime.memory_manager.search(search_query, top_k=3)
        memory_context = self._runtime.memory_manager.format_for_context(memories)
        if memory_context:
            self._context_manager.set_memory_context(memory_context)
    except Exception as e:
        logger.warning("Memory retrieval failed: {error}", error=e)
```

Add helper method to NeoLoop:

```python
def _extract_memory_query(self, user_input: str | list[ContentPart]) -> str:
    """Extract a search query for memory retrieval from user input.

    For simple string input, uses the input directly.
    For ContentPart list, concatenates text parts.
    """
    if isinstance(user_input, str):
        return user_input
    return " ".join(p.text for p in user_input if hasattr(p, "text"))
```

### Phase 5.3: `loop/context.py` — MEMORY injection logic in `build()`

In `ContextManager.build()`, add handling for `ContextType.MEMORY`:

```python
# In the build() method's sorted_entries loop, add after QUERY handling:

# MEMORY: Always inject if content is present (memories change per query)
elif context_type == ContextType.MEMORY:
    if not entry.content or not entry.content.strip():
        continue
```

---

## Phase 6: Tools + Agent Registration

### Phase 6.1: `tools/memory/__init__.py`

```python
"""Memory tools package."""
```

### Phase 6.2: `tools/memory/save.py`

**CRITICAL**: No `from __future__ import annotations`.

```python
"""Memory save tool — allows the agent to persist information across sessions."""

from typing import override

from loop.toolset import BaseTool, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory
from tools.utils import load_desc
from pathlib import Path


class SaveMemoryParams(BaseModel):
    """Parameters for saving a memory."""

    category: MemoryCategory = Field(
        description="Category of the memory (preference, decision, environment, fact, note)"
    )
    content: str = Field(
        description="The memory content to save. Be specific and concise.",
        min_length=1,
        max_length=4000,
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for organizing memories (e.g., ['mysql', 'performance'])",
    )


class MemorySave(BaseTool[SaveMemoryParams]):
    """Tool for persisting information across sessions."""

    name: str = "MemorySave"
    description: str = load_desc(Path(__file__).parent / "desc" / "memory_save.md")
    params: type[SaveMemoryParams] = SaveMemoryParams

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    @override
    async def __call__(self, params: SaveMemoryParams) -> ToolReturnType:
        if self._memory_manager is None:
            return ToolOk(
                message="Memory system is not available. No embedding model is configured.",
                brief="",
            )

        count = self._memory_manager.count()
        request = CreateMemoryRequest(
            category=params.category,
            content=params.content,
            tags=params.tags,
        )
        entry = await self._memory_manager.save(request)
        new_count = self._memory_manager.count()

        return ToolOk(
            message=f"Memory saved (#{new_count}/{self._memory_manager.max_memories}). ID: {entry.id}",
            brief=f"Saved [{entry.category.value}] {entry.content[:100]}",
        )
```

### Phase 6.3: `tools/memory/search.py`

**CRITICAL**: No `from __future__ import annotations`.

```python
"""Memory search tool — allows the agent to search stored memories."""

from typing import Optional, override

from loop.toolset import BaseTool, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from memory.manager import MemoryManager
from memory.models import MemoryCategory
from tools.utils import load_desc
from pathlib import Path


class SearchMemoryParams(BaseModel):
    """Parameters for searching memories."""

    query: str = Field(
        description="The search query. Use keywords related to what you're looking for.",
        min_length=1,
    )
    category: Optional[MemoryCategory] = Field(
        default=None,
        description="Optional category filter (preference, decision, environment, fact, note)",
    )
    top_k: int = Field(
        default=3,
        description="Maximum number of results to return (1-10)",
        ge=1,
        le=10,
    )


class MemorySearch(BaseTool[SearchMemoryParams]):
    """Tool for searching stored memories."""

    name: str = "MemorySearch"
    description: str = load_desc(Path(__file__).parent / "desc" / "memory_search.md")
    params: type[SearchMemoryParams] = SearchMemoryParams

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    @override
    async def __call__(self, params: SearchMemoryParams) -> ToolReturnType:
        if self._memory_manager is None:
            return ToolOk(
                message="Memory system is not available. No embedding model is configured.",
                brief="",
            )

        memories = await self._memory_manager.search(
            params.query,
            category=params.category,
            top_k=params.top_k,
        )

        if not memories:
            return ToolOk(
                message=f"No memories found for query: '{params.query}'",
                brief="",
            )

        lines = []
        for mem in memories:
            tags = f" [{', '.join(mem.tags)}]" if mem.tags else ""
            lines.append(f"- [{mem.category.value}{tags}] {mem.content}")

        output = "\n".join(lines)
        return ToolOk(
            message=f"Found {len(memories)} memories",
            brief=output,
        )
```

### Phase 6.4: `tools/memory/delete.py`

**CRITICAL**: No `from __future__ import annotations`.

```python
"""Memory delete tool — allows the agent to delete stored memories."""

from typing import override

from loop.toolset import BaseTool, ToolOk, ToolReturnType
from pydantic import BaseModel, Field

from memory.manager import MemoryManager
from tools.utils import load_desc
from pathlib import Path


class DeleteMemoryParams(BaseModel):
    """Parameters for deleting a memory."""

    memory_id: str = Field(
        description="The ID of the memory to delete. Get this from MemorySearch results.",
        min_length=1,
    )


class MemoryDelete(BaseTool[DeleteMemoryParams]):
    """Tool for deleting stored memories."""

    name: str = "MemoryDelete"
    description: str = load_desc(Path(__file__).parent / "desc" / "memory_delete.md")
    params: type[DeleteMemoryParams] = DeleteMemoryParams

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    @override
    async def __call__(self, params: DeleteMemoryParams) -> ToolReturnType:
        if self._memory_manager is None:
            return ToolOk(
                message="Memory system is not available. No embedding model is configured.",
                brief="",
            )

        deleted = self._memory_manager.delete(params.memory_id)
        if deleted:
            remaining = self._memory_manager.count()
            return ToolOk(
                message=f"Memory {params.memory_id} deleted. {remaining} memories remaining.",
                brief=f"Deleted memory {params.memory_id}",
            )
        else:
            return ToolOk(
                message=f"Memory not found: {params.memory_id}",
                brief="",
            )
```

### Phase 6.5: Tool description files

**`tools/memory/desc/memory_save.md`**:
```markdown
Save information to persistent memory for use in future sessions.

**When to use:**
- User states a preference (e.g., "I prefer UTC timezone", "Always show execution plans")
- An important decision is made with rationale (e.g., "Chosen index strategy: composite on (user_id, created_at)")
- Environment information is discovered (e.g., "Production DB has 50M rows in orders table")
- A fact is learned that will be useful later

**DO NOT use for:**
- Transient information that changes every session
- Information already stored in memory
- Simple Q&A that doesn't need persistence

**Parameters:**
- **category**: One of: preference, decision, environment, fact, note
- **content**: The information to remember. Be specific and self-contained.
- **tags**: Optional tags for organization (e.g., ["mysql", "slow-query"])

**Category guide:**
- `preference`: User's style/formatting/language preferences
- `decision`: Important choices with rationale
- `environment`: Infrastructure/schema/environment details
- `fact`: Domain facts discovered during analysis
- `note`: Anything else worth remembering
```

**`tools/memory/desc/memory_search.md`**:
```markdown
Search stored memories from previous sessions.

**When to use:**
- Before starting analysis, check if relevant context was saved previously
- When the user asks about past decisions or preferences
- To recall environment details from previous sessions

**Parameters:**
- **query**: Search keywords. Use terms relevant to what you need.
- **category**: Optional filter by category (preference, decision, environment, fact, note)
- **top_k**: Number of results (1-10, default 3)

**Tips:**
- Use specific keywords for better results
- Filter by category when you know the type of memory needed
- The system uses both keyword and semantic search
```

**`tools/memory/desc/memory_delete.md`**:
```markdown
Delete a memory entry by ID.

**When to use:**
- A stored memory is outdated or incorrect
- The user requests to forget specific information
- Cleaning up duplicate or low-value memories

**Parameters:**
- **memory_id**: The ID of the memory to delete (obtained from MemorySearch)

**Safety:**
- Deletion is permanent and cannot be undone
- Always confirm the memory_id before deleting
```

### Phase 6.6: `prompts/default_agent.yaml` — Register memory tools

```yaml
version: 1
agent:
  name: ""
  system_prompt_path: ./system.md
  tools:
    - "tools.todo:TodoList"
    # Database Analysis Tools
    - "tools.database.sql_ddl:DDLExecutor"
    - "tools.database.explain:MySQLExplain"
    - "tools.database.show:Show"
    - "tools.database.desc:Desc"
    - "tools.database.select:Select"
    # Database Analysis Tool (MySQL & DuckDB)
    - "tools.database.data_analyzer:DataAnalyzer"
    # Subagent Tool
    - "tools.subagent.subagent:Subagent"
    # Memory Tools
    - "tools.memory.save:MemorySave"
    - "tools.memory.search:MemorySearch"
    - "tools.memory.delete:MemoryDelete"
```

### Phase 6.7: `loop/agent.py` — System prompt memory guide

**Integration point**: In `_load_system_prompt()`, after loading the template, we inject a memory usage guide block. The cleanest approach is to add `${MEMORY_GUIDE}` as a new template variable in `BuiltinSystemPromptArgs`.

Add to `BuiltinSystemPromptArgs`:
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinSystemPromptArgs:
    """Builtin system prompt arguments."""

    CLI_NOW: str
    CLI_LANGUAGE: str
    MEMORY_GUIDE: str = ""  # Empty if memory not available
```

Add to `Runtime.create()`:
```python
# In BuiltinSystemPromptArgs creation:
MEMORY_GUIDE=_build_memory_guide(runtime.memory_manager),
```

Add helper function in `loop/agent.py`:
```python
_MEMORY_GUIDE = """
# Memory System

You have access to a persistent memory system that stores information across sessions.
Use it to remember user preferences, important decisions, environment details, and useful facts.

**Memory Tools:**
- `MemorySave`: Save information for future sessions
- `MemorySearch`: Search previously stored memories
- `MemoryDelete`: Delete outdated memories

**When to save memories:**
- User preferences (language, timezone, formatting style)
- Important decisions and their rationale
- Environment details (DB schema, server specs, known issues)
- Domain facts that will be useful later

**When to search memories:**
- At the start of a new session to recall context
- When the user references past conversations
- Before making recommendations (check if preferences exist)

**Best practices:**
- Be specific and concise when saving
- Use appropriate categories and tags
- Don't save transient or obvious information
- Delete outdated memories when you find them
"""


def _build_memory_guide(memory_manager) -> str:
    """Build the memory usage guide for the system prompt.

    Returns the guide text if memory is available, empty string otherwise.
    """
    if memory_manager is None:
        return ""
    return _MEMORY_GUIDE
```

Add to `system.md` (end of file):
```markdown
${MEMORY_GUIDE}
```

And update the `<context_types>` table in system.md:
```markdown
| **Memory Context** | `<memory_context>` | Relevant memories from previous sessions                           |
```

---

## Phase 7: Tests

### Phase 7.1: Test Files Structure

```
tests/memory/
├── __init__.py
├── test_models.py
├── test_store.py
├── test_embedding.py
├── test_manager.py
└── test_tools.py
```

### Phase 7.2: `tests/memory/__init__.py`

```python
"""Tests for the memory system."""
```

### Phase 7.3: `tests/memory/test_models.py`

```python
"""Tests for memory models."""

import pytest

from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry


class TestMemoryCategory:
    def test_all_categories_exist(self):
        assert MemoryCategory.PREFERENCE.value == "preference"
        assert MemoryCategory.DECISION.value == "decision"
        assert MemoryCategory.ENVIRONMENT.value == "environment"
        assert MemoryCategory.FACT.value == "fact"
        assert MemoryCategory.NOTE.value == "note"

    def test_category_from_string(self):
        cat = MemoryCategory("preference")
        assert cat == MemoryCategory.PREFERENCE


class TestMemoryEntry:
    def test_default_id(self):
        entry = MemoryEntry(category=MemoryCategory.NOTE, content="test")
        assert len(entry.id) == 16
        assert entry.id.isalnum()

    def test_custom_id(self):
        entry = MemoryEntry(
            id="custom123",
            category=MemoryCategory.FACT,
            content="test",
        )
        assert entry.id == "custom123"

    def test_default_values(self):
        entry = MemoryEntry(category=MemoryCategory.NOTE, content="test")
        assert entry.tags == []
        assert entry.embedding == []
        assert entry.created_at == ""
        assert entry.updated_at == ""

    def test_format_for_context_no_tags(self):
        entry = MemoryEntry(
            category=MemoryCategory.FACT,
            content="MySQL 8.0 supports window functions",
        )
        assert entry.format_for_context() == "[fact] MySQL 8.0 supports window functions"

    def test_format_for_context_with_tags(self):
        entry = MemoryEntry(
            category=MemoryCategory.ENVIRONMENT,
            content="Production DB on AWS RDS",
            tags=["production", "aws"],
        )
        fmt = entry.format_for_context()
        assert "[environment [production, aws]]" in fmt
        assert "Production DB on AWS RDS" in fmt

    def test_validation_content_too_long(self):
        with pytest.raises(Exception):
            MemoryEntry(
                category=MemoryCategory.NOTE,
                content="x" * 4001,
            )

    def test_validation_empty_content(self):
        with pytest.raises(Exception):
            MemoryEntry(category=MemoryCategory.NOTE, content="")


class TestCreateMemoryRequest:
    def test_minimal(self):
        req = CreateMemoryRequest(
            category=MemoryCategory.NOTE,
            content="test note",
        )
        assert req.category == MemoryCategory.NOTE
        assert req.content == "test note"
        assert req.tags == []

    def test_with_tags(self):
        req = CreateMemoryRequest(
            category=MemoryCategory.DECISION,
            content="Use InnoDB engine",
            tags=["mysql", "engine"],
        )
        assert req.tags == ["mysql", "engine"]
```

### Phase 7.4: `tests/memory/test_store.py`

```python
"""Tests for memory store."""

import os
import tempfile

import pytest

from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from memory.store import MAX_MEMORIES, MemoryStore


@pytest.fixture
def store():
    """Create a temporary memory store."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = MemoryStore(db_path=path)
    yield s
    s.close()
    os.unlink(path)


class TestMemoryStoreInit:
    def test_creates_tables(self, store):
        assert store.count() == 0

    def test_custom_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            s = MemoryStore(db_path=path)
            assert s.count() == 0
            s.close()
        finally:
            os.unlink(path)


class TestMemoryStoreSave:
    def test_save_new_entry(self, store):
        entry = MemoryEntry(category=MemoryCategory.NOTE, content="test")
        result = store.save(entry)
        assert result.id == entry.id
        assert result.created_at != ""
        assert store.count() == 1

    def test_save_with_embedding(self, store):
        entry = MemoryEntry(
            category=MemoryCategory.FACT,
            content="test",
            embedding=[0.1, 0.2, 0.3],
        )
        store.save(entry)
        results = store.list_all()
        assert len(results) == 1
        assert results[0].embedding == [0.1, 0.2, 0.3]

    def test_save_enforces_limit(self, store):
        # Fill up to limit
        for i in range(MAX_MEMORIES):
            store.save(MemoryEntry(category=MemoryCategory.NOTE, content=f"entry {i}"))
        assert store.count() == MAX_MEMORIES

        # Adding one more should delete oldest
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="new entry"))
        assert store.count() == MAX_MEMORIES

        # Oldest entry (entry 0) should be gone
        all_entries = store.list_all(limit=MAX_MEMORIES)
        contents = [e.content for e in all_entries]
        assert "entry 0" not in contents
        assert "new entry" in contents


class TestMemoryStoreSearch:
    def test_fts_search(self, store):
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="MySQL slow query optimization"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="PostgreSQL indexing tips"))

        results = store.search("MySQL slow")
        assert len(results) >= 1
        assert any("MySQL slow query" in r.content for r in results)

    def test_fts_search_with_category(self, store):
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="MySQL performance"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="MySQL tips"))

        results = store.search("MySQL", category=MemoryCategory.FACT)
        assert all(r.category == MemoryCategory.FACT for r in results)

    def test_empty_query(self, store):
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="test"))
        results = store.search("")
        assert results == []

    def test_no_results(self, store):
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="hello world"))
        results = store.search("nonexistent query xyz")
        assert results == []


class TestMemoryStoreDelete:
    def test_delete_existing(self, store):
        entry = store.save(MemoryEntry(category=MemoryCategory.NOTE, content="test"))
        assert store.delete(entry.id) is True
        assert store.count() == 0

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False

    def test_delete_removes_from_search(self, store):
        entry = store.save(MemoryEntry(category=MemoryCategory.FACT, content="unique searchable content"))
        store.delete(entry.id)
        results = store.search("unique searchable")
        assert results == []


class TestMemoryStoreList:
    def test_list_order(self, store):
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="first"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="second"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="third"))

        results = store.list_all(limit=10)
        assert results[0].content == "third"  # newest first
        assert results[2].content == "first"

    def test_list_with_category(self, store):
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="fact1"))
        store.save(MemoryEntry(category=MemoryCategory.NOTE, content="note1"))
        store.save(MemoryEntry(category=MemoryCategory.FACT, content="fact2"))

        results = store.list_all(category=MemoryCategory.FACT)
        assert len(results) == 2
        assert all(r.category == MemoryCategory.FACT for r in results)

    def test_list_pagination(self, store):
        for i in range(10):
            store.save(MemoryEntry(category=MemoryCategory.NOTE, content=f"entry {i}"))

        page1 = store.list_all(limit=3, offset=0)
        page2 = store.list_all(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].content != page2[0].content
```

### Phase 7.5: `tests/memory/test_embedding.py`

```python
"""Tests for memory embedding wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.embedding import MemoryEmbedding


class TestMemoryEmbedding:
    def test_not_available(self):
        """Test when no embedding model is configured."""
        mock_config = MagicMock()
        mock_config.default_embedding_model = ""
        mock_config.embedding_models = {}
        mock_config.embedding_providers = {}

        with patch("memory.embedding.EmbeddingService.from_config", return_value=None):
            emb = MemoryEmbedding(mock_config)
            assert emb.is_available is False

    @pytest.mark.asyncio
    async def test_embed_text_not_available(self):
        """Test embed returns empty list when service unavailable."""
        mock_config = MagicMock()
        mock_config.default_embedding_model = ""
        mock_config.embedding_models = {}
        mock_config.embedding_providers = {}

        with patch("memory.embedding.EmbeddingService.from_config", return_value=None):
            emb = MemoryEmbedding(mock_config)
            result = await emb.embed_text("hello")
            assert result == []

    @pytest.mark.asyncio
    async def test_embed_text_available(self):
        """Test embed delegates to service."""
        mock_config = MagicMock()
        mock_config.default_embedding_model = "text-embedding-v3"
        mock_config.embedding_models = {"text-embedding-v3": MagicMock()}
        mock_config.embedding_providers = {"dashscope": MagicMock()}

        mock_service = AsyncMock()
        mock_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

        with patch("memory.embedding.EmbeddingService.from_config", return_value=mock_service):
            emb = MemoryEmbedding(mock_config)
            assert emb.is_available is True
            result = await emb.embed_text("hello world")
            assert result == [0.1, 0.2, 0.3]
            mock_service.generate_embedding.assert_called_once_with("hello world")

    @pytest.mark.asyncio
    async def test_embed_texts_available(self):
        """Test batch embedding."""
        mock_config = MagicMock()
        mock_config.default_embedding_model = "text-embedding-v3"
        mock_config.embedding_models = {"text-embedding-v3": MagicMock()}
        mock_config.embedding_providers = {"dashscope": MagicMock()}

        mock_service = AsyncMock()
        mock_service.generate_embeddings_batch = AsyncMock(
            return_value=[[0.1], [0.2]]
        )

        with patch("memory.embedding.EmbeddingService.from_config", return_value=mock_service):
            emb = MemoryEmbedding(mock_config)
            result = await emb.embed_texts(["hello", "world"])
            assert result == [[0.1], [0.2]]
```

### Phase 7.6: `tests/memory/test_manager.py`

```python
"""Tests for memory manager."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory
from memory.store import MemoryStore


@pytest.fixture
def temp_store():
    """Create a temporary memory store."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = MemoryStore(db_path=path)
    yield store
    store.close()
    os.unlink(path)


@pytest.fixture
def mock_embedding():
    """Create a mock embedding service."""
    emb = MagicMock()
    emb.is_available = True
    emb.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return emb


@pytest.fixture
def manager(temp_store, mock_embedding):
    """Create a MemoryManager with mock embedding."""
    return MemoryManager(temp_store, mock_embedding)


class TestMemoryManagerSave:
    @pytest.mark.asyncio
    async def test_save_generates_embedding(self, manager, mock_embedding):
        req = CreateMemoryRequest(
            category=MemoryCategory.NOTE,
            content="test memory",
        )
        entry = await manager.save(req)
        assert entry.id is not None
        mock_embedding.embed_text.assert_called_once_with("test memory")

    @pytest.mark.asyncio
    async def test_save_without_embedding_service(self, temp_store):
        """Test save works even when embedding is unavailable."""
        mock_emb = MagicMock()
        mock_emb.is_available = False
        mgr = MemoryManager(temp_store, mock_emb)

        req = CreateMemoryRequest(
            category=MemoryCategory.FACT,
            content="no embedding test",
        )
        entry = await mgr.save(req)
        assert entry.id is not None
        assert entry.embedding == []

    @pytest.mark.asyncio
    async def test_save_embedding_failure(self, manager, mock_embedding):
        """Test save continues even if embedding generation fails."""
        mock_embedding.embed_text = AsyncMock(side_effect=ValueError("API error"))

        req = CreateMemoryRequest(
            category=MemoryCategory.NOTE,
            content="test with error",
        )
        entry = await manager.save(req)
        assert entry.id is not None
        assert entry.embedding == []


class TestMemoryManagerSearch:
    @pytest.mark.asyncio
    async def test_search_hybrid(self, manager):
        # Save with embedding
        req = CreateMemoryRequest(
            category=MemoryCategory.FACT,
            content="MySQL uses InnoDB by default since 5.5",
            tags=["mysql", "innodb"],
        )
        await manager.save(req)

        results = await manager.search("MySQL InnoDB", top_k=3)
        assert len(results) >= 1
        assert "InnoDB" in results[0].content

    @pytest.mark.asyncio
    async def test_search_empty_query(self, manager):
        results = await manager.search("")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_embedding_fallback(self, temp_store):
        """Test search falls back to FTS when embedding unavailable."""
        mock_emb = MagicMock()
        mock_emb.is_available = False
        mgr = MemoryManager(temp_store, mock_emb)

        await mgr.save(CreateMemoryRequest(
            category=MemoryCategory.FACT,
            content="DuckDB is great for analytics",
        ))

        results = await mgr.search("DuckDB analytics")
        assert len(results) >= 1


class TestMemoryManagerDelete:
    def test_delete(self, manager):
        entry = manager._store.save(
            MemoryEntry(category=MemoryCategory.NOTE, content="to delete")
        )
        assert manager.delete(entry.id) is True
        assert manager.count() == 0

    def test_delete_not_found(self, manager):
        assert manager.delete("nonexistent") is False


class TestMemoryManagerList:
    def test_list_all(self, manager):
        manager._store.save(MemoryEntry(category=MemoryCategory.NOTE, content="a"))
        manager._store.save(MemoryEntry(category=MemoryCategory.NOTE, content="b"))
        results = manager.list_all()
        assert len(results) == 2

    def test_count(self, manager):
        manager._store.save(MemoryEntry(category=MemoryCategory.NOTE, content="a"))
        manager._store.save(MemoryEntry(category=MemoryCategory.FACT, content="b"))
        assert manager.count() == 2
        assert manager.count(category=MemoryCategory.FACT) == 1


class TestMemoryManagerFormat:
    def test_format_empty(self, manager):
        assert manager.format_for_context([]) == ""

    def test_format_single(self, manager):
        entry = MemoryEntry(
            category=MemoryCategory.PREFERENCE,
            content="Always use UTC",
            tags=["timezone"],
        )
        result = manager.format_for_context([entry])
        assert "<memory_context>" in result
        assert "Always use UTC" in result
        assert "</memory_context>" in result

    def test_format_multiple(self, manager):
        entries = [
            MemoryEntry(category=MemoryCategory.FACT, content="fact1"),
            MemoryEntry(category=MemoryCategory.NOTE, content="note1"),
        ]
        result = manager.format_for_context(entries)
        assert "1." in result
        assert "2." in result
        assert "fact1" in result
        assert "note1" in result
```

### Phase 7.7: `tests/memory/test_tools.py`

```python
"""Tests for memory tools."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from memory.store import MemoryStore
from tools.memory.save import MemorySave, SaveMemoryParams
from tools.memory.search import MemorySearch, SearchMemoryParams
from tools.memory.delete import MemoryDelete, DeleteMemoryParams


@pytest.fixture
def temp_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = MemoryStore(db_path=path)
    yield store
    store.close()
    os.unlink(path)


@pytest.fixture
def mock_manager(temp_store):
    mock_emb = MagicMock()
    mock_emb.is_available = True
    mock_emb.embed_text = AsyncMock(return_value=[0.1, 0.2])
    return MemoryManager(temp_store, mock_emb)


class TestMemorySave:
    @pytest.mark.asyncio
    async def test_save_success(self, mock_manager):
        tool = MemorySave(memory_manager=mock_manager)
        params = SaveMemoryParams(
            category=MemoryCategory.PREFERENCE,
            content="Prefer dark mode",
            tags=["ui"],
        )
        result = await tool(params)
        assert result.message is not None
        assert "Memory saved" in result.message
        assert mock_manager.count() == 1

    @pytest.mark.asyncio
    async def test_save_no_manager(self):
        tool = MemorySave(memory_manager=None)
        params = SaveMemoryParams(
            category=MemoryCategory.NOTE,
            content="test",
        )
        result = await tool(params)
        assert "not available" in result.message


class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_search_success(self, mock_manager):
        await mock_manager.save(CreateMemoryRequest(
            category=MemoryCategory.FACT,
            content="MySQL 8.0 supports CTEs",
        ))

        tool = MemorySearch(memory_manager=mock_manager)
        params = SearchMemoryParams(query="MySQL CTE")
        result = await tool(params)
        assert "Found" in result.message
        assert "CTEs" in result.brief

    @pytest.mark.asyncio
    async def test_search_no_results(self, mock_manager):
        tool = MemorySearch(memory_manager=mock_manager)
        params = SearchMemoryParams(query="nonexistent_xyz")
        result = await tool(params)
        assert "No memories found" in result.message

    @pytest.mark.asyncio
    async def test_search_no_manager(self):
        tool = MemorySearch(memory_manager=None)
        params = SearchMemoryParams(query="test")
        result = await tool(params)
        assert "not available" in result.message


class TestMemoryDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_manager):
        entry = await mock_manager.save(CreateMemoryRequest(
            category=MemoryCategory.NOTE,
            content="delete me",
        ))

        tool = MemoryDelete(memory_manager=mock_manager)
        params = DeleteMemoryParams(memory_id=entry.id)
        result = await tool(params)
        assert "deleted" in result.message.lower()
        assert mock_manager.count() == 0

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_manager):
        tool = MemoryDelete(memory_manager=mock_manager)
        params = DeleteMemoryParams(memory_id="nonexistent")
        result = await tool(params)
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_delete_no_manager(self):
        tool = MemoryDelete(memory_manager=None)
        params = DeleteMemoryParams(memory_id="any")
        result = await tool(params)
        assert "not available" in result.message
```

---

## Execution Dependency Order

```
Phase 1 ──────────────────────────────────────────────┐
  1.1 memory/models.py                                │
  1.2 memory/store.py ◀──── depends on models.py      │
  1.3 memory/__init__.py ◀── depends on both          │
                                                      │
Phase 2 ──────────────────────────────────────────────┤
  2.1 memory/embedding.py ◀── uses llm/embedding.py   │
                                                      │
Phase 3 ──────────────────────────────────────────────┤
  3.1 memory/manager.py ◀── depends on store + embed  │
                                                      │
Phase 4 ──────────────────────────────────────────────┤
  4.1 loop/runtime.py ◀── depends on manager.py       │
  4.2 app.py ◀────────── depends on runtime.py        │
  4.3 loop/agent.py ◀── depends on manager.py         │
                                                      │
Phase 5 ──────────────────────────────────────────────┤
  5.1 loop/context.py ◀── adds MEMORY ContextType     │
  5.2 loop/neoloop.py ◀── depends on context + runtime│
                                                      │
Phase 6 ──────────────────────────────────────────────┤
  6.1 tools/memory/save.py ◀── depends on manager     │
  6.2 tools/memory/search.py ◀─ depends on manager    │
  6.3 tools/memory/delete.py ◀─ depends on manager    │
  6.4 desc/*.md ◀───────── static files               │
  6.5 prompts/default_agent.yaml ◀ register tools     │
  6.6 loop/agent.py ◀──── system prompt guide         │
  6.7 prompts/system.md ◀── MEMORY_GUIDE template var │
                                                      │
Phase 7 ──────────────────────────────────────────────┘
  7.1 tests/memory/test_models.py
  7.2 tests/memory/test_store.py
  7.3 tests/memory/test_embedding.py
  7.4 tests/memory/test_manager.py
  7.5 tests/memory/test_tools.py
```

---

## Configuration Required

Users must configure an embedding model in `~/.rdsai-cli/config.json`:

```json
{
  "default_embedding_model": "text-embedding-v3",
  "embedding_models": {
    "text-embedding-v3": {
      "provider": "dashscope",
      "model": "text-embedding-v3",
      "max_context_size": 8192
    }
  },
  "embedding_providers": {
    "dashscope": {
      "type": "qwen",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "sk-..."
    }
  }
}
```

Without this configuration, the memory system gracefully degrades:
- `MemoryManager` is `None` in Runtime
- Memory tools return "not available" messages
- No memory context is injected into conversations
- The system is fully functional, just without memory

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `memory/__init__.py` | CREATE | Package exports |
| `memory/models.py` | CREATE | Pydantic models |
| `memory/store.py` | CREATE | SQLite storage |
| `memory/embedding.py` | CREATE | Embedding wrapper |
| `memory/manager.py` | CREATE | Memory orchestrator |
| `loop/runtime.py` | MODIFY | Add `memory_manager` field + init |
| `loop/agent.py` | MODIFY | Add MemoryManager to DI + guide builder |
| `loop/context.py` | MODIFY | Add MEMORY ContextType |
| `loop/neoloop.py` | MODIFY | Inject memories in run() |
| `app.py` | MODIFY | Add memory cleanup in __aexit__ |
| `tools/memory/__init__.py` | CREATE | Package init |
| `tools/memory/save.py` | CREATE | MemorySave tool |
| `tools/memory/search.py` | CREATE | MemorySearch tool |
| `tools/memory/delete.py` | CREATE | MemoryDelete tool |
| `tools/memory/desc/memory_save.md` | CREATE | Tool description |
| `tools/memory/desc/memory_search.md` | CREATE | Tool description |
| `tools/memory/desc/memory_delete.md` | CREATE | Tool description |
| `prompts/default_agent.yaml` | MODIFY | Register memory tools |
| `prompts/system.md` | MODIFY | Add memory context + guide |
| `tests/memory/__init__.py` | CREATE | Test package |
| `tests/memory/test_models.py` | CREATE | Model tests |
| `tests/memory/test_store.py` | CREATE | Store tests |
| `tests/memory/test_embedding.py` | CREATE | Embedding tests |
| `tests/memory/test_manager.py` | CREATE | Manager tests |
| `tests/memory/test_tools.py` | CREATE | Tool tests |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Embedding API failure | Graceful fallback to FTS-only search; empty embedding vectors saved |
| SQLite corruption | WAL mode enabled; file-based allows easy backup/delete |
| Memory bloat | 1000-entry hard limit; oldest auto-deleted |
| Tool loading failure | `SkipThisTool` exception if MemoryManager is None |
| Context token overflow | `format_for_context` is compact; top_k=3 limits injection size |
| FTS5 not available | Automatic fallback to LIKE-based search |
| No embedding config | MemoryManager is None; tools return graceful messages |
