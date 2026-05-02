"""SQLite storage layer for the memory system."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.base import get_share_dir
from memory.models import MemoryCategory, MemoryEntry
from utils.logging import logger

MAX_MEMORIES = 1000
DEFAULT_TOP_K = 3


class MemoryStore:
    """SQLite-backed memory store with FTS keyword search."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else get_share_dir() / "memories.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
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
                id UNINDEXED,
                content
            );
            """
        )
        conn.execute("DELETE FROM memories_fts")
        conn.execute("INSERT INTO memories_fts(id, content) SELECT id, content FROM memories")
        conn.commit()
        logger.info("Memory store initialized at {path}", path=self._db_path)

    def save(self, entry: MemoryEntry) -> MemoryEntry:
        """Save a memory entry to the store."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        embedding_blob = json.dumps(entry.embedding).encode("utf-8") if entry.embedding else None

        exists = conn.execute("SELECT 1 FROM memories WHERE id = ?", (entry.id,)).fetchone() is not None
        if exists:
            if not entry.created_at:
                existing = conn.execute("SELECT created_at FROM memories WHERE id = ?", (entry.id,)).fetchone()
                entry.created_at = existing["created_at"]
            entry.updated_at = now
            conn.execute(
                """
                UPDATE memories
                SET category = ?, content = ?, tags = ?, embedding = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    entry.category.value,
                    entry.content,
                    json.dumps(entry.tags),
                    embedding_blob,
                    entry.updated_at,
                    entry.id,
                ),
            )
            conn.execute("DELETE FROM memories_fts WHERE id = ?", (entry.id,))
            conn.execute("INSERT INTO memories_fts(id, content) VALUES (?, ?)", (entry.id, entry.content))
            logger.info("Memory updated: id={id}", id=entry.id)
        else:
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if count >= MAX_MEMORIES:
                oldest = conn.execute("SELECT id FROM memories ORDER BY created_at ASC LIMIT 1").fetchone()
                if oldest:
                    self._delete_by_id(conn, oldest["id"])
                    logger.info("Memory store full, deleted oldest entry: {id}", id=oldest["id"])

            entry.created_at = now
            entry.updated_at = now
            conn.execute(
                """
                INSERT INTO memories (id, category, content, tags, embedding, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.category.value,
                    entry.content,
                    json.dumps(entry.tags),
                    embedding_blob,
                    entry.created_at,
                    entry.updated_at,
                ),
            )
            conn.execute("INSERT INTO memories_fts(id, content) VALUES (?, ?)", (entry.id, entry.content))
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
        """Search memories using FTS keyword matching."""
        if not query.strip():
            return []

        conn = self._get_conn()
        sql = """
            SELECT m.id, m.category, m.content, m.tags, m.embedding, m.created_at, m.updated_at
            FROM memories_fts f
            JOIN memories m ON m.id = f.id
            WHERE memories_fts MATCH ?
        """
        params: list[object] = [self._build_fts_query(query)]
        if category:
            sql += " AND m.category = ?"
            params.append(category.value)
        sql += " ORDER BY rank LIMIT ?"
        params.append(top_k)

        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning("FTS search failed, falling back to LIKE: {error}", error=e)
            return self._fallback_search(query, category, top_k)

        return [self._row_to_entry(row) for row in rows]

    def _build_fts_query(self, query: str) -> str:
        terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
        if not terms:
            escaped_query = query.replace('"', '""')
            return f'"{escaped_query}"'
        quoted_terms = []
        for term in terms:
            escaped_term = term.replace('"', '""')
            quoted_terms.append(f'"{escaped_term}"')
        return " ".join(quoted_terms)

    def _fallback_search(
        self,
        query: str,
        category: Optional[MemoryCategory],
        top_k: int,
    ) -> list[MemoryEntry]:
        conn = self._get_conn()
        sql = "SELECT id, category, content, tags, embedding, created_at, updated_at FROM memories WHERE content LIKE ?"
        params: list[object] = [f"%{query}%"]
        if category:
            sql += " AND category = ?"
            params.append(category.value)
        sql += " ORDER BY created_at DESC LIMIT ?"
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
        """Search memories by cosine similarity to query embedding."""
        if not query_embedding:
            return []

        conn = self._get_conn()
        sql = "SELECT id, category, content, tags, embedding, created_at, updated_at FROM memories"
        params: list[object] = []
        if category:
            sql += " WHERE category = ?"
            params.append(category.value)
        rows = conn.execute(sql, params).fetchall()

        scored: list[tuple[float, MemoryEntry]] = []
        for row in rows:
            entry = self._row_to_entry(row)
            if entry.embedding:
                scored.append((_cosine_sim(query_embedding, entry.embedding), entry))
        scored.sort(key=lambda item: item[0], reverse=True)
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
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

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
        params: list[object] = []
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
        params: list[object] = []
        if category:
            sql += " WHERE category = ?"
            params.append(category.value)
        return conn.execute(sql, params).fetchone()[0]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        embedding_blob = row["embedding"]
        embedding: list[float] = []
        if embedding_blob:
            try:
                embedding = json.loads(embedding_blob.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
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


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
