"""Memory manager orchestrates storage, embedding, and retrieval."""

from __future__ import annotations

import math
from typing import Optional

from memory.embedding import MemoryEmbedding
from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from memory.store import DEFAULT_TOP_K, MAX_MEMORIES, MemoryStore
from utils.logging import logger


class MemoryManager:
    """Central memory management API."""

    def __init__(self, store: MemoryStore, embedding: MemoryEmbedding) -> None:
        self._store = store
        self._embedding = embedding

    async def save(self, request: CreateMemoryRequest) -> MemoryEntry:
        """Save a new memory entry."""
        entry = MemoryEntry(category=request.category, content=request.content, tags=request.tags)
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
        """Search memories with semantic retrieval when embeddings are available."""
        if not query.strip():
            return []

        if not self._embedding.is_available:
            return self._store.search(query, category=category, top_k=top_k)

        try:
            query_embedding = await self._embedding.embed_text(query)
        except Exception as e:
            logger.warning("Failed to generate query embedding: {error}", error=e)
            return self._store.search(query, category=category, top_k=top_k)

        candidates = self._store.search(query, category=category, top_k=top_k * 3)
        if not candidates:
            return self._store.search_by_embedding(query_embedding, category=category, top_k=top_k)

        if query_embedding:
            scored = []
            for entry in candidates:
                score = _cosine_sim(query_embedding, entry.embedding) if entry.embedding else 0.0
                scored.append((score, entry))
            scored.sort(key=lambda item: item[0], reverse=True)
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
        """Format memories for injection into agent context."""
        if not memories:
            return ""
        lines = ["Relevant memories from previous sessions:"]
        for index, memory in enumerate(memories, 1):
            lines.append(f"  {index}. {memory.format_for_context()}")
        return "\n".join(lines)

    @property
    def max_memories(self) -> int:
        """Maximum number of memories allowed."""
        return MAX_MEMORIES

    def close(self) -> None:
        """Close resources."""
        self._store.close()


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
