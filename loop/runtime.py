"""Agent runtime configuration and initialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from config import Config
from llm.llm import LLM
from config import Session

if TYPE_CHECKING:
    from tools.mcp.config import MCPConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltinSystemPromptArgs:
    """Builtin system prompt arguments."""

    CLI_NOW: str
    CLI_LANGUAGE: str


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
    mcp_config: "MCPConfig | None" = field(default=None)
    yolo: bool = field(default=False)

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
        mcp_config: "MCPConfig | None" = None,
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
        return Runtime(
            config=config,
            llm=llm,
            session=session,
            mcp_config=mcp_config,
            builtin_args=BuiltinSystemPromptArgs(
                CLI_NOW=datetime.now().astimezone().isoformat(),
                CLI_LANGUAGE=config.language,
            ),
            yolo=yolo,
        )
