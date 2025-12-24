"""Loop - The AI agent core module.

This module provides the core agent implementation using LangGraph for:
- State management via checkpointing
- Human-in-the-loop via interrupts
- Tool execution and orchestration
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from loop.types import ContentPart
from utils.logging import logger
from events import Stream, StreamMessage, StreamUISide

if TYPE_CHECKING:
    from llm.llm import LLM
    from config import ModelCapability


class LLMNotSet(Exception):
    """Raised when the LLM is not set."""

    pass


class LLMNotSupported(Exception):
    """Raised when the LLM does not have required capabilities."""

    def __init__(self, llm: LLM, capabilities: list[ModelCapability]):
        self.llm = llm
        self.capabilities = capabilities
        capabilities_str = "capability" if len(capabilities) == 1 else "capabilities"
        super().__init__(
            f"LLM model '{llm.model_name}' does not support required {capabilities_str}: {', '.join(capabilities)}."
        )


class MaxStepsReached(Exception):
    """Raised when the maximum number of steps is reached."""

    n_steps: int
    """The number of steps that have been taken."""

    def __init__(self, n_steps: int):
        self.n_steps = n_steps


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """Snapshot of the current loop status."""

    context_usage: float
    """The usage of the context, in percentage."""

    yolo: bool = False
    """Whether YOLO mode (auto-approve all actions) is enabled."""


@runtime_checkable
class Loop(Protocol):
    """Protocol defining the Loop interface."""

    @property
    def name(self) -> str:
        """The name of the loop."""
        ...

    @property
    def model_name(self) -> str:
        """The name of the LLM model used by the loop. Empty string indicates no LLM configured."""
        ...

    @property
    def model_capabilities(self) -> set[ModelCapability] | None:
        """The capabilities of the LLM model used by the loop. None indicates no LLM configured."""
        ...

    @property
    def status(self) -> StatusSnapshot:
        """The current status of the loop. The returned value is immutable."""
        ...

    async def run(self, user_input: str | list[ContentPart]):
        """Run the agent with the given user input.

        Args:
            user_input: The user input to the agent.

        Raises:
            LLMNotSet: When the LLM is not set.
            LLMNotSupported: When the LLM does not have required capabilities.
            ChatProviderError: When the LLM provider returns an error.
            MaxStepsReached: When the maximum number of steps is reached.
            asyncio.CancelledError: When the run is cancelled by user.
        """
        ...


type UILoopFn = Callable[[StreamUISide], Coroutine[Any, Any, None]]
"""A long-running async function to visualize the agent behavior."""


class RunCancelled(Exception):
    """The run was cancelled by the cancel event."""


async def run_loop(
    loop: Loop,
    user_input: str | list[ContentPart],
    ui_loop_fn: UILoopFn,
    cancel_event: asyncio.Event,
) -> None:
    """Run the loop with the given user input, connecting it to the UI loop with a stream.

    `cancel_event` is an outside handle that can be used to cancel the run. When the
    event is set, the run will be gracefully stopped and a `RunCancelled` will be raised.

    Args:
        loop: The loop instance to run.
        user_input: User input to process.
        ui_loop_fn: UI loop function to handle events.
        cancel_event: Event to signal cancellation.

    Raises:
        LLMNotSet: When the LLM is not set.
        LLMNotSupported: When the LLM does not have required capabilities.
        ChatProviderError: When the LLM provider returns an error.
        MaxStepsReached: When the maximum number of steps is reached.
        RunCancelled: When the run is cancelled by the cancel event.
    """
    stream = Stream()
    stream_token = _current_stream.set(stream)

    ui_task = asyncio.create_task(ui_loop_fn(stream.ui_side))

    logger.debug("Starting loop run")
    loop_task = asyncio.create_task(loop.run(user_input))

    cancel_event_task = asyncio.create_task(cancel_event.wait())
    await asyncio.wait(
        [loop_task, cancel_event_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    try:
        if cancel_event.is_set():
            logger.debug("Cancelling the run task")
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                raise RunCancelled from None
        else:
            assert loop_task.done()  # either stop event is set or the run task is done
            cancel_event_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cancel_event_task
            loop_task.result()  # this will raise if any exception was raised in the run task
    finally:
        logger.debug("Shutting down the UI loop")
        # shutting down the stream should break the UI loop
        stream.shutdown()
        try:
            await asyncio.wait_for(ui_task, timeout=0.5)
        except asyncio.QueueShutDown:
            logger.debug("UI loop shut down")
            pass
        except TimeoutError:
            logger.warning("UI loop timed out")
        finally:
            _current_stream.reset(stream_token)


_current_stream = ContextVar[Stream | None]("current_stream", default=None)


def get_stream_or_none() -> Stream | None:
    """Get the current stream or None.

    Expect to be not None when called from anywhere in the agent loop.
    """
    return _current_stream.get()


def stream_send(msg: StreamMessage) -> None:
    """Send a message to the current stream.

    Take this as `print` and `input` for loops.
    Loops should always use this function to send stream messages.
    """
    stream = get_stream_or_none()
    assert stream is not None, "Stream is expected to be set when loop is running"
    stream.loop_side.send(msg)


# Re-export key components for convenience
from loop.state import AgentState, ApprovalInterrupt, InputState
from loop.neoloop import NeoLoop
from loop.runtime import Runtime, BuiltinSystemPromptArgs

__all__ = [
    # Exceptions
    "LLMNotSet",
    "LLMNotSupported",
    "MaxStepsReached",
    "RunCancelled",
    # Types
    "StatusSnapshot",
    "Loop",
    "UILoopFn",
    # State
    "AgentState",
    "ApprovalInterrupt",
    "InputState",
    # Core
    "NeoLoop",
    "Runtime",
    "BuiltinSystemPromptArgs",
    # Functions
    "run_loop",
    "get_stream_or_none",
    "stream_send",
]
