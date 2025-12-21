"""LangGraph state definitions for the agent."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Graph state for the agent.

    Attributes:
        messages: Conversation history, automatically accumulated via add_messages reducer.
        token_count: Current token count for context management.
        step_number: Current step number in the agent loop.
        yolo: Whether to skip approval prompts (auto-approve all actions).
    """

    # Conversation history with automatic message accumulation
    messages: Annotated[list[BaseMessage], add_messages]

    # Token count for context window management
    token_count: int

    # Current step number
    step_number: int

    # Auto-approve mode (skip human-in-the-loop)
    yolo: bool


class ApprovalInterrupt(TypedDict):
    """Interrupt payload for tool approval requests."""

    type: str  # "approval"
    tool_name: str
    tool_args: dict[str, Any]
    description: str


class InputState(TypedDict):
    """Input state for starting a new conversation turn."""

    messages: list[BaseMessage]
    yolo: bool
