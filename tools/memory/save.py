"""Memory save tool."""

from pathlib import Path
from typing import override

from loop.toolset import BaseTool, ToolOk, ToolReturnType
from memory.manager import MemoryManager
from memory.models import CreateMemoryRequest, MemoryCategory
from pydantic import BaseModel, Field
from tools.utils import load_desc


class SaveMemoryParams(BaseModel):
    """Parameters for saving a memory."""

    category: MemoryCategory = Field(description="Category of the memory")
    content: str = Field(description="The memory content to save. Be specific and concise.", min_length=1, max_length=4000)
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for organizing memories",
    )


class MemorySave(BaseTool[SaveMemoryParams]):
    """Tool for persisting information across sessions."""

    name: str = "MemorySave"
    description: str = load_desc(Path(__file__).parent / "desc" / "save_memory.md")
    params: type[SaveMemoryParams] = SaveMemoryParams

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    @override
    async def __call__(self, params: SaveMemoryParams) -> ToolReturnType:
        if self._memory_manager is None:
            return ToolOk(message="Memory system is not available. No embedding model is configured.", brief="")

        request = CreateMemoryRequest(category=params.category, content=params.content, tags=params.tags)
        entry = await self._memory_manager.save(request)
        new_count = self._memory_manager.count()

        return ToolOk(
            message=f"Memory saved (#{new_count}/{self._memory_manager.max_memories}). ID: {entry.id}",
            brief=f"Saved [{entry.category.value}] {entry.content[:100]}",
        )
