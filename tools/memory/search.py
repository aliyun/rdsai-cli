"""Memory search tool."""

from pathlib import Path
from typing import Optional, override

from loop.toolset import BaseTool, ToolOk, ToolReturnType
from memory.manager import MemoryManager
from memory.models import MemoryCategory
from pydantic import BaseModel, Field
from tools.utils import load_desc


class SearchMemoryParams(BaseModel):
    """Parameters for searching memories."""

    query: str = Field(description="The search query.", min_length=1)
    category: Optional[MemoryCategory] = Field(default=None, description="Optional category filter")
    top_k: int = Field(default=3, description="Maximum number of results to return", ge=1, le=10)


class MemorySearch(BaseTool[SearchMemoryParams]):
    """Tool for searching stored memories."""

    name: str = "MemorySearch"
    description: str = load_desc(Path(__file__).parent / "desc" / "search_memory.md")
    params: type[SearchMemoryParams] = SearchMemoryParams

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    @override
    async def __call__(self, params: SearchMemoryParams) -> ToolReturnType:
        if self._memory_manager is None:
            return ToolOk(message="Memory system is not available. No embedding model is configured.", brief="")

        memories = await self._memory_manager.search(params.query, category=params.category, top_k=params.top_k)
        if not memories:
            return ToolOk(message=f"No memories found for query: '{params.query}'", brief="")

        lines = []
        for memory in memories:
            tags = f" [{', '.join(memory.tags)}]" if memory.tags else ""
            lines.append(f"- {memory.id} [{memory.category.value}{tags}] {memory.content}")

        output = "\n".join(lines)
        return ToolOk(message=f"Found {len(memories)} memories", brief=output, output=output)
