"""Tests for MemorySave."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.manager import MemoryManager
from memory.models import MemoryCategory
from memory.store import MemoryStore
from tools.memory.save import MemorySave, SaveMemoryParams


@pytest.fixture
def manager(tmp_path):
    store = MemoryStore(tmp_path / "memories.db")
    embedding = MagicMock()
    embedding.is_available = True
    embedding.embed_text = AsyncMock(return_value=[0.1, 0.2])
    yield MemoryManager(store, embedding)
    store.close()


@pytest.mark.asyncio
async def test_save_success(manager):
    tool = MemorySave(manager)
    result = await tool(SaveMemoryParams(category=MemoryCategory.PREFERENCE, content="Prefer UTC", tags=["time"]))
    assert "Memory saved" in result.message
    assert manager.count() == 1


@pytest.mark.asyncio
async def test_save_no_manager():
    tool = MemorySave(None)
    result = await tool(SaveMemoryParams(category=MemoryCategory.NOTE, content="test"))
    assert "not available" in result.message
