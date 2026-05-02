"""Agent runtime configuration and initialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from config import Config
from llm.llm import LLM
from config import Session

if TYPE_CHECKING:
    from memory.manager import MemoryManager
    from tools.mcp.config import MCPConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinSystemPromptArgs:
    """Builtin system prompt arguments."""

    CLI_NOW: str
    CLI_LANGUAGE: str
    MEMORY_GUIDE: str = ""


@dataclass(slots=True, kw_only=True)
class Runtime:
    """Agent runtime configuration.

    This is a simplified runtime that only contains configuration and LLM.
    State management is handled by LangGraph's checkpointer.
    """

    config: Config
    llm: LLM | None
    session: Session
    builtin_args: BuiltinSystemPromptArgs
    mcp_config: MCPConfig | None = field(default=None)
    yolo: bool = field(default=False)
    memory_manager: MemoryManager | None = field(default=None)

    def set_llm(self, llm: LLM | None) -> None:
        """Switch to a different LLM at runtime.

        Args:
            llm: The new LLM instance to use.
        """
        self.llm = llm

    def set_yolo(self, yolo: bool) -> None:
        """Set the yolo mode (auto-approve all actions).

        Args:
            yolo: Whether to auto-approve all tool executions.
        """
        self.yolo = yolo

    @staticmethod
    async def create(
        config: Config,
        llm: LLM | None,
        session: Session,
        mcp_config: MCPConfig | None = None,
        yolo: bool = False,
    ) -> Runtime:
        """Create a new runtime instance.

        Args:
            config: Application configuration.
            llm: Language model instance (optional).
            session: Current session.
            mcp_config: MCP configuration (optional).
            yolo: Whether to auto-approve all tool executions (optional).

        Returns:
            Initialized Runtime instance.
        """
        memory_manager = _create_memory_manager(config)

        return Runtime(
            config=config,
            llm=llm,
            session=session,
            mcp_config=mcp_config,
            builtin_args=BuiltinSystemPromptArgs(
                CLI_NOW=datetime.now().astimezone().isoformat(),
                CLI_LANGUAGE=config.language,
                MEMORY_GUIDE=_build_memory_guide(memory_manager),
            ),
            yolo=yolo,
            memory_manager=memory_manager,
        )


def _create_memory_manager(config: Config) -> "MemoryManager | None":
    """Create the memory manager when an embedding model is configured."""
    if not getattr(config, "default_embedding_model", ""):
        return None

    try:
        from memory.embedding import MemoryEmbedding
        from memory.manager import MemoryManager
        from memory.store import MemoryStore

        return MemoryManager(MemoryStore(), MemoryEmbedding(config))
    except Exception as e:
        from utils.logging import logger

        logger.warning("Failed to initialize memory manager: {error}", error=e)
        return None


_MEMORY_GUIDE = """
# Memory System

You have access to persistent memory across sessions.

**Memory Tools:**
- `MemorySave`: Save user preferences, important decisions, environment details, and useful facts
- `MemorySearch`: Search previously stored memories
- `MemoryDelete`: Delete outdated or incorrect memories

**Best practices:**
- Save only durable, useful information
- Keep memories specific, concise, and self-contained
- Use appropriate categories and tags
- Do not save transient query results unless they describe stable environment facts
"""


def _build_memory_guide(memory_manager: "MemoryManager | None") -> str:
    """Build the memory usage guide for the system prompt."""
    if memory_manager is None:
        return ""
    return _MEMORY_GUIDE
