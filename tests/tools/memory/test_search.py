"""Tests for MemorySearch."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory
from memory.store import MemoryStore
from tools.memory.search import MemorySearch, SearchMemoryParams


@pytest.fixture
def manager(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    embedding = MagicMock()
    embedding.is_available = True
    embedding.embed_text = AsyncMock(return_value=[0.1, 0.2])
    yield MemoryManager(store, embedding)
    store.close()


@pytest.mark.asyncio
async def test_search_success(manager):
    await manager.save(CreateMemoryRequest(category=MemoryCategory.FACT, content="MySQL supports CTEs"))
    tool = MemorySearch(manager)
    result = await tool(SearchMemoryParams(query="MySQL CTE"))
    assert "Found" in result.message
    assert "CTEs" in result.brief


@pytest.mark.asyncio
async def test_search_no_results(manager):
    tool = MemorySearch(manager)
    result = await tool(SearchMemoryParams(query="nonexistent_xyz"))
    assert "No memories found" in result.message


@pytest.mark.asyncio
async def test_search_no_manager():
    tool = MemorySearch(None)
    result = await tool(SearchMemoryParams(query="test"))
    assert "not available" in result.message
