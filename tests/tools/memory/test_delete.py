"""Tests for MemoryDelete."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory
from memory.store import MemoryStore
from tools.memory.delete import DeleteMemoryParams, MemoryDelete


@pytest.fixture
def manager(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    embedding = MagicMock()
    embedding.is_available = True
    embedding.embed_text = AsyncMock(return_value=[0.1, 0.2])
    yield MemoryManager(store, embedding)
    store.close()


@pytest.mark.asyncio
async def test_delete_success(manager):
    entry = await manager.save(CreateMemoryRequest(category=MemoryCategory.NOTE, content="delete me"))
    tool = MemoryDelete(manager)
    result = await tool(DeleteMemoryParams(memory_id=entry.id))
    assert "deleted" in result.message.lower()
    assert manager.count() == 0


@pytest.mark.asyncio
async def test_delete_not_found(manager):
    tool = MemoryDelete(manager)
    result = await tool(DeleteMemoryParams(memory_id="missing"))
    assert "not found" in result.message.lower()


@pytest.mark.asyncio
async def test_delete_no_manager():
    tool = MemoryDelete(None)
    result = await tool(DeleteMemoryParams(memory_id="any"))
    assert "not available" in result.message
