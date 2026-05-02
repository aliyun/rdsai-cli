"""Memory delete tool."""

from pathlib import Path
from typing import override

from loop.toolset import BaseTool, ToolOk, ToolReturnType
from memory.manager import MemoryManager
from pydantic import BaseModel, Field
from tools.utils import load_desc


class DeleteMemoryParams(BaseModel):
    """Parameters for deleting a memory."""

    memory_id: str = Field(description="The ID of the memory to delete.", min_length=1)


class MemoryDelete(BaseTool[DeleteMemoryParams]):
    """Tool for deleting stored memories."""

    name: str = "MemoryDelete"
    description: str = load_desc(Path(__file__).parent / "desc" / "delete_memory.md")
    params: type[DeleteMemoryParams] = DeleteMemoryParams

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    @override
    async def __call__(self, params: DeleteMemoryParams) -> ToolReturnType:
        if self._memory_manager is None:
            return ToolOk(message="Memory system is not available. No embedding model is configured.", brief="")

        deleted = self._memory_manager.delete(params.memory_id)
        if deleted:
            remaining = self._memory_manager.count()
            return ToolOk(
                message=f"Memory {params.memory_id} deleted. {remaining} memories remaining.",
                brief=f"Deleted memory {params.memory_id}",
            )
        return ToolOk(message=f"Memory not found: {params.memory_id}", brief="")
