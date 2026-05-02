"""Memory system data models."""

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """Memory categories for organizing stored memories."""

    PREFERENCE = "preference"
    DECISION = "decision"
    ENVIRONMENT = "environment"
    FACT = "fact"
    NOTE = "note"


class MemoryEntry(BaseModel):
    """A single memory entry stored in the system."""

    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
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
