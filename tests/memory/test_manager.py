"""Tests for memory manager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory, MemoryEntry
from memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    memory_store = MemoryStore(tmp_path / "memories.db")
    yield memory_store
    memory_store.close()


@pytest.fixture
def embedding():
    mock_embedding = MagicMock()
    mock_embedding.is_available = True
    mock_embedding.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return mock_embedding


@pytest.fixture
def manager(store, embedding):
    return MemoryManager(store, embedding)


@pytest.mark.asyncio
async def test_save_generates_embedding(manager, embedding):
    entry = await manager.save(CreateMemoryRequest(category=MemoryCategory.NOTE, content="test memory"))
    assert entry.embedding == [0.1, 0.2, 0.3]
    embedding.embed_text.assert_called_once_with("test memory")


@pytest.mark.asyncio
async def test_save_without_embedding_service(store):
    embedding = MagicMock()
    embedding.is_available = False
    manager = MemoryManager(store, embedding)
    entry = await manager.save(CreateMemoryRequest(category=MemoryCategory.FACT, content="no embedding"))
    assert entry.embedding == []


@pytest.mark.asyncio
async def test_save_embedding_failure(manager, embedding):
    embedding.embed_text = AsyncMock(side_effect=ValueError("API error"))
    entry = await manager.save(CreateMemoryRequest(category=MemoryCategory.NOTE, content="test"))
    assert entry.embedding == []


@pytest.mark.asyncio
async def test_search_hybrid(manager):
    await manager.save(CreateMemoryRequest(category=MemoryCategory.FACT, content="MySQL uses InnoDB by default"))
    results = await manager.search("MySQL InnoDB", top_k=3)
    assert len(results) == 1
    assert "InnoDB" in results[0].content


@pytest.mark.asyncio
async def test_search_empty_query(manager):
    assert await manager.search("") == []


@pytest.mark.asyncio
async def test_search_no_embedding_fallback(store):
    embedding = MagicMock()
    embedding.is_available = False
    manager = MemoryManager(store, embedding)
    await manager.save(CreateMemoryRequest(category=MemoryCategory.FACT, content="DuckDB is great for analytics"))
    results = await manager.search("DuckDB analytics")
    assert len(results) == 1


def test_delete_list_count_and_format(manager):
    entry = manager._store.save(MemoryEntry(category=MemoryCategory.NOTE, content="to delete"))
    assert manager.count() == 1
    assert manager.list_all()[0].id == entry.id
    assert manager.delete(entry.id) is True
    assert manager.delete("missing") is False

    formatted = manager.format_for_context(
        [MemoryEntry(category=MemoryCategory.PREFERENCE, content="Always use UTC", tags=["timezone"])]
    )
    assert "Relevant memories" in formatted
    assert "Always use UTC" in formatted
    assert manager.format_for_context([]) == ""
